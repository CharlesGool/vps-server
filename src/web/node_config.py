"""Sing-box inbound candidate preparation and locked credential-only apply.

Port edits remain offline-only: firewall rules are not transactionally managed.
"""

import copy
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import uuid


def _cli_text(key):
    """Read CLI diagnostics from the installed or checkout web catalog."""
    base = Path(__file__).resolve().parent
    if base.parent.name == "src":
        base = base.parent.parent
    tags = {"en": "en", "zh_cn": "zh-CN", "zh_tw": "zh-TW", "zh_hk": "zh-HK",
            "hi": "hi", "es": "es", "ar": "ar", "fr": "fr"}
    tag = tags.get(os.environ.get("VPSSRV_DEFAULT_LANG", "en"), "en")
    catalog = json.loads((base / "lang" / "web" / f"{tag}.json").read_text(encoding="utf-8"))
    return catalog[key]


PROTOCOLS = frozenset({"anytls", "vmess", "vless", "trojan", "shadowsocks"})
UUID_PROTOCOLS = frozenset({"vmess", "vless"})
PASSWORD_PROTOCOLS = frozenset({"anytls", "trojan"})
# A sing-box 2022-blake3-aes-128-gcm password is a base64-encoded 16-byte key.
_SS_KEY = re.compile(r"[A-Za-z0-9+/]{22}==\Z")


class InvalidNodeChange(ValueError):
    """The requested edit, or the installed state used to assess it, is invalid."""


def _port(value):
    if type(value) is not int or not 1 <= value <= 65535:
        raise InvalidNodeChange("port must be an integer from 1 to 65535")
    return value


def _credential(protocol, value):
    if not isinstance(value, str):
        raise InvalidNodeChange("credential must be a string")
    if protocol in UUID_PROTOCOLS:
        try:
            parsed = uuid.UUID(value)
        except (ValueError, AttributeError) as exc:
            raise InvalidNodeChange("invalid UUID") from exc
        if parsed.int == 0 or str(parsed) != value:
            raise InvalidNodeChange("UUID must be canonical lowercase and nonzero")
    elif protocol in PASSWORD_PROTOCOLS:
        if not 8 <= len(value) <= 128 or not all(33 <= ord(c) <= 126 for c in value):
            raise InvalidNodeChange("password must be 8-128 printable ASCII characters without spaces")
    else:
        if not _SS_KEY.fullmatch(value):
            raise InvalidNodeChange("shadowsocks requires a canonical base64 16-byte key")
        import base64
        if base64.b64encode(base64.b64decode(value)).decode("ascii") != value:
            raise InvalidNodeChange("noncanonical shadowsocks key")


def prepare_candidate(protocol, port, credential, anytls_config, proxy_config, reserved_ports):
    """Return (module, changed document) without touching disk or services.

    Both installed config documents and the reserved local/forward ports must be
    supplied from a consistent snapshot. Fail closed on missing/malformed state;
    the requested protocol must already exist in exactly one installed module.
    """
    if protocol not in PROTOCOLS:
        raise InvalidNodeChange("protocol is not allowlisted")
    _port(port)
    _credential(protocol, credential)
    documents = {"anytls": anytls_config, "proxy": proxy_config}
    target_module = "anytls" if protocol == "anytls" else "proxy"
    if not isinstance(reserved_ports, (list, tuple, set, frozenset)):
        raise InvalidNodeChange("reserved ports snapshot required")
    reserved = {_port(p) for p in reserved_ports}
    inbounds = {}
    occupied = set()
    for module, document in documents.items():
        if document is None:
            continue
        if not isinstance(document, dict) or not isinstance(document.get("inbounds"), list):
            raise InvalidNodeChange("malformed installed configuration")
        for inbound in document["inbounds"]:
            if not isinstance(inbound, dict) or inbound.get("type") not in PROTOCOLS:
                raise InvalidNodeChange("unexpected installed inbound")
            kind = inbound["type"]
            if (module == "anytls") != (kind == "anytls") or kind in inbounds:
                raise InvalidNodeChange("duplicate or misplaced installed inbound")
            existing_port = _port(inbound.get("listen_port"))
            if existing_port in occupied:
                raise InvalidNodeChange("installed inbound port collision")
            occupied.add(existing_port)
            inbounds[kind] = (module, inbound)
    if protocol not in inbounds or inbounds[protocol][0] != target_module:
        raise InvalidNodeChange("requested inbound is not installed")
    old_port = inbounds[protocol][1]["listen_port"]
    if port != old_port and (port in reserved or port in occupied):
        raise InvalidNodeChange("port is reserved or in use by another inbound")
    document = copy.deepcopy(documents[target_module])
    inbound = next(item for item in document["inbounds"] if item["type"] == protocol)
    inbound["listen_port"] = port
    if protocol == "shadowsocks":
        if inbound.get("method") != "2022-blake3-aes-128-gcm":
            raise InvalidNodeChange("unsupported installed shadowsocks method")
        inbound["password"] = credential
    else:
        users = inbound.get("users")
        if not isinstance(users, list) or len(users) != 1 or not isinstance(users[0], dict):
            raise InvalidNodeChange("expected exactly one installed user")
        users[0]["uuid" if protocol in UUID_PROTOCOLS else "password"] = credential
    return target_module, document


def check_candidate(document, config_dir, binary):
    """Check a 0600 staged JSON document with installed sing-box; never apply it.

    The caller supplies trusted paths, not request data. The temporary file is
    always removed, including after check failure. No shell is involved.
    """
    config_dir = Path(config_dir)
    binary = Path(binary)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise InvalidNodeChange("sing-box binary is unavailable")
    fd, name = tempfile.mkstemp(prefix=".node-check-", suffix=".json", dir=config_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as staged:
            json.dump(document, staged, ensure_ascii=False)
            staged.flush()
            os.fsync(staged.fileno())
        subprocess.run([str(binary), "check", "-c", name], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)
    finally:
        os.unlink(name)


CONFIG_PATHS = {"anytls": Path("/etc/vps-server-anytls/config.json"),
                "proxy": Path("/etc/vps-server-proxy/config.json")}
BINARY = Path("/usr/local/bin/sing-box-vps-server")
# /etc is root-owned; a predictable lock in world-writable /run/lock is unsafe.
LOCK_PATH = Path("/etc/vps-server-node.lock")
SERVICES = {"anytls": "vps-server-anytls.service", "proxy": "vps-server-proxy.service"}


class DegradedNodeChange(RuntimeError):
    """Commit failed and old configuration/service could not be restored."""


def _write_stage(path, payload):
    fd, name = tempfile.mkstemp(prefix=".node-apply-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as staged:
            staged.write(payload)
            staged.flush()
            os.fsync(staged.fileno())
        return Path(name)
    except BaseException:
        os.unlink(name)
        raise


def _replace(stage, path):
    os.replace(stage, path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _service(command, service):
    subprocess.run(["systemctl", command, service], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)


def _read_config(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None, None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise InvalidNodeChange("installed config must be a regular unlinked file")
    data = path.read_bytes()
    return json.loads(data), data


def apply_credential(protocol, credential, *, config_paths=CONFIG_PATHS,
                     binary=BINARY, lock_path=LOCK_PATH):
    """Rotate one installed credential, under the lock also used by reset scripts.

    The installed port is used unchanged; no firewall operations are performed.
    Callers must be privileged; this is not a web authorization boundary.
    """
    if os.geteuid() != 0:
        raise PermissionError("node apply requires root")
    if protocol not in PROTOCOLS:
        raise InvalidNodeChange("protocol is not allowlisted")
    _credential(protocol, credential)
    with open(lock_path, "a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        documents = {}
        originals = {}
        for module, path in config_paths.items():
            documents[module], originals[module] = _read_config(Path(path))
        target = "anytls" if protocol == "anytls" else "proxy"
        document = documents[target]
        if not isinstance(document, dict) or not isinstance(document.get("inbounds"), list):
            raise InvalidNodeChange("requested inbound is not installed")
        matching = [item for item in document["inbounds"]
                    if isinstance(item, dict) and item.get("type") == protocol]
        if len(matching) != 1:
            raise InvalidNodeChange("requested inbound is not uniquely installed")
        port = _port(matching[0].get("listen_port"))
        module, candidate = prepare_candidate(protocol, port, credential,
                                              documents["anytls"], documents["proxy"], ())
        path = Path(config_paths[module])
        if not Path(binary).is_file() or not os.access(binary, os.X_OK):
            raise InvalidNodeChange("sing-box binary is unavailable")
        stage = _write_stage(path, json.dumps(candidate, ensure_ascii=False).encode("utf-8"))
        try:
            subprocess.run([str(binary), "check", "-c", str(stage)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            def interrupted(signum, frame):
                raise InterruptedError("node apply interrupted")
            previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
            for sig in previous:
                signal.signal(sig, interrupted)
            swapped = False
            try:
                swapped = True  # also restore if a signal lands immediately after replace
                _replace(stage, path)
                _service("restart", SERVICES[module])
                _service("is-active", SERVICES[module])
            except BaseException as exc:
                if swapped:
                    # Do not let a second catchable signal interrupt recovery.
                    for sig in previous:
                        signal.signal(sig, signal.SIG_IGN)
                    try:
                        recovery = _write_stage(path, originals[module])
                        try:
                            _replace(recovery, path)
                        finally:
                            recovery.unlink(missing_ok=True)
                        _service("restart", SERVICES[module])
                        _service("is-active", SERVICES[module])
                    except BaseException as restore_error:
                        raise DegradedNodeChange("DEGRADED: old config/service recovery failed") from restore_error
                raise InvalidNodeChange("credential apply failed; old config/service restored") from exc
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
        finally:
            stage.unlink(missing_ok=True)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in PROTOCOLS:
        print(_cli_text("node_config_usage"), file=sys.stderr)
        return 2
    # Bound stdin; never print it, put it on argv, or include it in subprocess output.
    raw = sys.stdin.buffer.read(130)
    if raw.endswith(b"\n"):
        raw = raw[:-1]
    try:
        apply_credential(sys.argv[1], raw.decode("utf-8"))
    except (ValueError, OSError, subprocess.SubprocessError, DegradedNodeChange) as exc:
        print(_cli_text("node_config_degraded" if isinstance(exc, DegradedNodeChange) else "node_config_rejected"), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
