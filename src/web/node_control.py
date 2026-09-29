#!/usr/bin/env python3
"""Privileged, locked changes to installed proxy inbounds.

Requests arrive on stdin, never argv. The web process launches this helper in
a transient systemd unit, outside its read-only /etc sandbox. No secret or
certificate material is written to logs or exception messages.
"""

import base64
import copy
from datetime import date, datetime, timezone
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import uuid

from node_inventory import InvalidInventory, validate_inventory
from node_operations import create_node, delete_node, edit_node, set_enabled_by_id
from node_state import CONFIG_PATHS, STATE_PATH, initialize_inventory, read_inventory, write_inventory


LOCK_PATH = Path("/etc/vps-server-node.lock")
BINARY = Path("/usr/local/bin/sing-box-vps-server")
SERVICES = {"anytls": "vps-server-anytls.service", "proxy": "vps-server-proxy.service"}
PROTOCOLS = frozenset(("anytls", "vmess", "vless", "trojan", "shadowsocks"))
APP_DIR = Path(__file__).resolve().parent
IPERF_PORT_FILE = Path(os.environ.get("VPSSRV_DATA_DIR", str(APP_DIR / "data"))) / "iperf-port.txt"
EDIT_FIELDS = frozenset(("name", "port", "credential", "sni", "cap_bytes",
                         "cap_action", "upload_limit_bps", "download_limit_bps",
                         "expiry_count", "expiry_unit", "expires_at",
                         "reset_mode", "next_reset_at"))
_HOST_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\Z")


class NodeControlError(ValueError):
    """The edit was rejected; installed state remains available."""


class DegradedNodeControl(RuntimeError):
    """The edit and recovery both failed; operator intervention is required."""


def _sni(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 253 or value != value.strip():
        raise NodeControlError("invalid SNI")
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        pass
    if not all(_HOST_LABEL.fullmatch(label) for label in value.split(".")):
        raise NodeControlError("invalid SNI")
    return value.lower()


def _free_port(port):
    for family, address in ((socket.AF_INET, "0.0.0.0"), (socket.AF_INET6, "::")):
        for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
            try:
                with socket.socket(family, kind) as probe:
                    probe.bind((address, port))
            except OSError as exc:
                # A host may have IPv6 disabled. Other bind failures are real
                # conflicts or permission errors, and fail the edit closed.
                if family == socket.AF_INET6 and exc.errno in (97, 93):
                    continue
                raise NodeControlError("requested port is unavailable") from exc


def _reserved_ports():
    """Keep node listeners clear of fixed ports and persisted DNAT ports."""
    reserved = {80, 443}
    try:
        reserved.add(int(IPERF_PORT_FILE.read_text().strip()))
    except FileNotFoundError:
        reserved.add(int(os.environ.get("VPSSRV_IPERF_PORT", "5201")))
    except (OSError, ValueError) as exc:
        raise NodeControlError("cannot read iperf port") from exc
    for path in (APP_DIR / "console_port.txt",):
        try:
            reserved.add(int(path.read_text().strip()))
        except (OSError, ValueError):
            pass
    state = APP_DIR / "data" / "portfwd.json"
    try:
        rules = json.loads(state.read_text())
    except FileNotFoundError:
        rules = []
    except (OSError, ValueError) as exc:
        raise NodeControlError("cannot read reserved port state") from exc
    if not isinstance(rules, list):
        raise NodeControlError("invalid reserved port state")
    for rule in rules:
        if not isinstance(rule, dict) or type(rule.get("public_port")) is not int:
            raise NodeControlError("invalid reserved port state")
        reserved.add(rule["public_port"])
    return reserved


def _stage(path, payload):
    fd, name = tempfile.mkstemp(prefix=".node-edit-", dir=Path(path).parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        return Path(name)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def _replace(stage, path):
    os.replace(stage, path)
    fd = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _certificate(directory, identifier, sni):
    """Create a fresh per-node self-signed certificate without changing peers."""
    target = Path(directory) / "certs" / identifier / uuid.uuid4().hex
    target.mkdir(mode=0o700, parents=True)
    cert, key = target / "fullchain.pem", target / "key.pem"
    # CN is limited to 64 characters; SAN carries the full requested name.
    try:
        ipaddress.ip_address(sni)
        san = "IP:" + sni
    except ValueError:
        san = "DNS:" + sni
    try:
        subprocess.run(["openssl", "req", "-x509", "-nodes", "-newkey", "ec",
                        "-pkeyopt", "ec_paramgen_curve:prime256v1", "-keyout", str(key),
                        "-out", str(cert), "-days", "3650", "-subj", "/CN=" + sni[:64],
                        "-addext", "subjectAltName=" + san], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        key.chmod(0o600)
        cert.chmod(0o600)
    except BaseException:
        shutil.rmtree(target)
        raise
    return cert, key, target


class HostBackend:
    def check(self, config):
        subprocess.run([str(BINARY), "check", "-c", str(config)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)

    def active(self, service):
        return subprocess.run(["systemctl", "is-active", "--quiet", service],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=10).returncode == 0

    def restart(self, service):
        if not self.enabled(service):
            return
        subprocess.run(["systemctl", "restart", service], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        if not self.active(service):
            raise NodeControlError("node service did not become active")

    def stop(self, service):
        subprocess.run(["systemctl", "stop", service], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)

    def start(self, service):
        if not self.enabled(service):
            return
        subprocess.run(["systemctl", "start", service], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        if not self.active(service):
            raise NodeControlError("node service did not become active")

    def enabled(self, service):
        return subprocess.run(["systemctl", "is-enabled", "--quiet", service],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0

    def reconcile(self, *, state_path, config_paths):
        # The caller already owns LOCK_PATH. The node is stopped during a
        # port change, so no traffic can escape before nft rules are updated.
        from node_meter import tick
        tick(state_path=state_path, config_paths=config_paths,
             meter_path=Path(state_path).parent / "meter.json", lock_held=True)

    def _firewall(self):
        if shutil.which("ufw") and "Status: active" in subprocess.run(
                ["ufw", "status"], capture_output=True, text=True, timeout=10).stdout:
            return "ufw"
        if shutil.which("firewall-cmd") and subprocess.run(
                ["firewall-cmd", "--state"], capture_output=True, timeout=10).returncode == 0:
            return "firewalld"
        if shutil.which("iptables"):
            return "iptables"
        return None

    def firewall(self, port, opening, protocol="tcp"):
        if opening and protocol in ("anytls", "vmess", "vless", "trojan", "shadowsocks"):
            module = "anytls" if protocol == "anytls" else "proxy"
            if not self.enabled(SERVICES[module]):
                return
        backend = self._firewall()
        if backend is None:
            return
        transports = ("tcp", "udp") if protocol == "shadowsocks" else ("tcp",)
        for transport in transports:
            self._firewall_transport(backend, port, opening, transport)
        if backend == "firewalld":
            subprocess.run(["firewall-cmd", "--reload"], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)

    def _firewall_transport(self, backend, port, opening, transport):
        if backend == "ufw":
            if not opening and f"{port}/{transport}" not in subprocess.run(
                    ["ufw", "status"], capture_output=True, text=True,
                    timeout=10, check=True).stdout:
                return
            cmd = ["ufw", "allow", f"{port}/{transport}"] if opening else \
                  ["ufw", "delete", "allow", f"{port}/{transport}"]
        elif backend == "firewalld":
            if not opening and subprocess.run(
                    ["firewall-cmd", "--permanent", f"--query-port={port}/{transport}"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=10).returncode != 0:
                return
            flag = "--add-port" if opening else "--remove-port"
            cmd = ["firewall-cmd", "--permanent", f"{flag}={port}/{transport}"]
        else:
            exists = subprocess.run(["iptables", "-C", "INPUT", "-p", transport,
                                     "--dport", str(port), "-j", "ACCEPT"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=10).returncode == 0
            if (opening and exists) or (not opening and not exists):
                return
            cmd = ["iptables", "-I" if opening else "-D", "INPUT", "-p", transport,
                   "--dport", str(port), "-j", "ACCEPT"]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=20)


def _random_credential(protocol):
    if protocol in ("vmess", "vless"):
        return str(uuid.uuid4())
    if protocol == "shadowsocks":
        return base64.b64encode(secrets.token_bytes(16)).decode("ascii")
    return secrets.token_urlsafe(24)


def _candidate_document(document, old, new):
    result = copy.deepcopy(document)
    matches = [index for index, item in enumerate(result["inbounds"])
               if item["tag"] == old["inbound"]["tag"]]
    if len(matches) != 1:
        raise NodeControlError("installed node is not unique")
    result["inbounds"][matches[0]] = copy.deepcopy(new["inbound"])
    return result


def _default_inbound(protocol, port):
    """An installer-compatible seed when this protocol has no remaining node."""
    inbound = {"type": protocol, "tag": "new-node-seed", "listen": "::",
               "listen_port": port}
    if protocol == "shadowsocks":
        inbound.update(method="2022-blake3-aes-128-gcm",
                       password=base64.b64encode(b"temporary-key-16").decode())
        return inbound
    user = {"name": "new-node-seed"}
    if protocol in ("vmess", "vless"):
        user["uuid"] = str(uuid.uuid4())
        if protocol == "vmess":
            user["alterId"] = 0
    else:
        user["password"] = "temporary-secret"
    inbound["users"] = [user]
    inbound["tls"] = {"enabled": True, "certificate_path": "/tmp/new-node-cert",
                      "key_path": "/tmp/new-node-key"}
    return inbound


def _random_free_port(inventory, reserved):
    for _ in range(100):
        port = 20000 + secrets.randbelow(40000)
        if port not in reserved | {node["port"] for node in inventory["nodes"]}:
            try:
                _free_port(port)
                return port
            except NodeControlError:
                continue
    raise NodeControlError("no random port available")


def _apply_structure_request(request, *, state_path, config_paths, lock_path,
                             backend, require_root):
    if require_root and os.geteuid() != 0:
        raise PermissionError("node control requires root")
    action = request.get("action") if isinstance(request, dict) else None
    if action == "create":
        keys = set(request)
        if not {"action", "protocol", "name", "port"} <= keys or not keys <= {"action", "protocol", "name", "port", "sni", "credential"}:
            raise NodeControlError("invalid create request")
        protocol = request["protocol"]
        if protocol not in PROTOCOLS or (protocol == "shadowsocks") == ("sni" in request):
            raise NodeControlError("invalid create protocol or SNI")
    elif action == "delete":
        if set(request) != {"action", "id"} or not isinstance(request["id"], str):
            raise NodeControlError("invalid delete request")
    elif action == "toggle":
        if (set(request) != {"action", "id", "enabled"} or
                not isinstance(request["id"], str) or type(request["enabled"]) is not bool):
            raise NodeControlError("invalid toggle request")
    else:
        raise NodeControlError("invalid node action")
    backend = backend or HostBackend()
    Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        inventory = read_inventory(state_path=state_path, config_paths=config_paths)
        if inventory is None:
            inventory = initialize_inventory(state_path=state_path, config_paths=config_paths)
        reserved = _reserved_ports()
        certificate_dir = None
        if action == "create":
            module = "anytls" if protocol == "anytls" else "proxy"
            config_path = Path(config_paths[module])
            if not config_path.is_file():
                raise NodeControlError("node module is not installed")
            port = request["port"]
            if port is None:
                port = _random_free_port(inventory, reserved)
            elif type(port) is not int or not 1 <= port <= 65535 or port in reserved | {n["port"] for n in inventory["nodes"]}:
                raise NodeControlError("invalid or reserved node port")
            else:
                _free_port(port)
            template = None if any(n["protocol"] == protocol for n in inventory["nodes"]) else _default_inbound(protocol, port)
            candidate = create_node(inventory, protocol, request["name"], port,
                                    reserved_ports=reserved, prototype_inbound=template,
                                    credential=request.get("credential"))
            new = candidate["nodes"][-1]
            if protocol != "shadowsocks":
                sni = _sni(request["sni"])
                cert, key, certificate_dir = _certificate(Path(state_path).parent, new["id"], sni)
                new["inbound"]["tls"]["certificate_path"] = str(cert)
                new["inbound"]["tls"]["key_path"] = str(key)
                validate_inventory(candidate)
            affected = new
        else:
            matches = [n for n in inventory["nodes"] if n["id"] == request["id"]]
            if len(matches) != 1:
                raise NodeControlError("node ID not found")
            affected = matches[0]
            module = "anytls" if affected["protocol"] == "anytls" else "proxy"
            config_path = Path(config_paths[module])
            if action == "toggle":
                if affected["enabled"] == request["enabled"]:
                    raise NodeControlError("node state has changed")
                candidate = set_enabled_by_id(inventory, affected["id"], request["enabled"],
                                              now=datetime.now(timezone.utc))
                if request["enabled"]:
                    _free_port(affected["port"])
            else:
                candidate = delete_node(inventory, affected["id"])
        document = json.loads(config_path.read_text(encoding="utf-8"))
        proposed = copy.deepcopy(document)
        proposed["inbounds"] = [copy.deepcopy(n["inbound"]) for n in candidate["nodes"]
                                 if n["enabled"] and (n["protocol"] == "anytls") == (module == "anytls")]
        original = config_path.read_bytes()
        meter_path = Path(state_path).parent / "meter.json"
        original_meter = meter_path.read_bytes() if meter_path.exists() else None
        staged = None
        opened = swapped = stopped = state_written = committed = False
        active = backend.active(SERVICES[module])
        try:
            staged = _stage(config_path, json.dumps(proposed, ensure_ascii=False).encode())
            backend.check(staged)
            if action == "create" or (action == "toggle" and request["enabled"]):
                opened = True
                backend.firewall(affected["port"], True, affected["protocol"])
            if active:
                backend.stop(SERVICES[module])
                stopped = True
            _replace(staged, config_path)
            swapped = True
            write_inventory(candidate, state_path=state_path)
            state_written = True
            backend.reconcile(state_path=state_path, config_paths=config_paths)
            # An empty inbound list means every node in this module is off.
            # Keep the unit stopped; starting sing-box without listeners can
            # hit systemd's start limit after repeated toggles.
            if proposed["inbounds"]:
                backend.start(SERVICES[module])
            if action == "delete" or (action == "toggle" and not request["enabled"]):
                backend.firewall(affected["port"], False, affected["protocol"])
            committed = True
            if action == "delete":
                # Only certificates made for this ID live here. A legacy
                # shared certificate sits in its module directory and stays.
                cert_root = Path(state_path).parent / "certs" / affected["id"]
                if not any(str((node["inbound"].get("tls") or {}).get("certificate_path", ""))
                           .startswith(str(cert_root) + os.sep) for node in candidate["nodes"]):
                    shutil.rmtree(cert_root, ignore_errors=True)
            return candidate
        except BaseException as exc:
            if swapped or stopped or state_written:
                try:
                    if swapped:
                        restore = _stage(config_path, original)
                        try:
                            _replace(restore, config_path)
                        finally:
                            restore.unlink(missing_ok=True)
                    write_inventory(inventory, state_path=state_path)
                    if original_meter is None:
                        meter_path.unlink(missing_ok=True)
                    else:
                        restore_meter = _stage(meter_path, original_meter)
                        try:
                            _replace(restore_meter, meter_path)
                        finally:
                            restore_meter.unlink(missing_ok=True)
                    backend.reconcile(state_path=state_path, config_paths=config_paths)
                    if active:
                        backend.start(SERVICES[module])
                    if action == "delete" or (action == "toggle" and not request["enabled"]):
                        backend.firewall(affected["port"], True, affected["protocol"])
                    if opened:
                        backend.firewall(affected["port"], False, affected["protocol"])
                except BaseException as recovery_error:
                    raise DegradedNodeControl("node rollback failed") from recovery_error
            elif opened:
                backend.firewall(affected["port"], False, affected["protocol"])
            raise NodeControlError("node change failed; previous configuration restored") from exc
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)
            if certificate_dir is not None and not committed:
                shutil.rmtree(certificate_dir, ignore_errors=True)


def _apply_iperf_port(request, *, require_root):
    """Update the operator's port registry and persisted iperf3 port together."""
    if require_root and os.geteuid() != 0:
        raise PermissionError("port control requires root")
    if set(request) != {"action", "old_port", "port"}:
        raise NodeControlError("invalid iperf port request")
    old_port, port = request["old_port"], request["port"]
    if type(old_port) is not int or type(port) is not int or not 1024 <= port <= 65535:
        raise NodeControlError("invalid iperf port")
    root = APP_DIR.parent
    registry = root / "PORTS.md"
    state = IPERF_PORT_FILE
    service = "vps-server-iperf3-window"
    header = ("| Host Port | Project / Service | Bind Address | Registration Date |\n"
              "| --- | --- | --- | --- |\n")
    with open(root / ".ports.lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = (int(state.read_text().strip()) if state.exists() else
                   int(os.environ.get("VPSSRV_IPERF_PORT", "5201")))
        if current != old_port or port == old_port:
            raise NodeControlError("stale iperf port")
        raw = registry.read_text(encoding="utf-8")
        if not raw.startswith(header):
            raise NodeControlError("invalid port registry")
        rows = []
        seen_ports = set()
        for line in raw[len(header):].splitlines():
            if not line.strip():
                continue
            match = re.fullmatch(r"\|\s*(\d{1,5})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|", line)
            if not match:
                raise NodeControlError("invalid port registry row")
            registered_port = int(match[1])
            if not 1 <= registered_port <= 65535 or registered_port in seen_ports:
                raise NodeControlError("invalid port registry entry")
            ipaddress.ip_address(match[3])
            date.fromisoformat(match[4])
            seen_ports.add(registered_port)
            rows.append((registered_port, match[2], match[3], match[4]))
        if sum(p == old_port and owner == service for p, owner, _, _ in rows) != 1:
            raise NodeControlError("iperf port is not registered")
        if any(p == port for p, _, _, _ in rows) or port in _reserved_ports():
            raise NodeControlError("requested port is reserved")
        _free_port(port)
        updated = [(port, service, "0.0.0.0", date.today().isoformat())
                   if p == old_port and owner == service else (p, owner, bind, registered)
                   for p, owner, bind, registered in rows]
        registry_bytes = (header + "".join(
            f"| {p} | {owner} | {bind} | {registered} |\n"
            for p, owner, bind, registered in sorted(updated))).encode("utf-8")
        old_state = state.read_bytes() if state.exists() else None
        registry_stage = _stage(registry, registry_bytes)
        try:
            os.chmod(registry_stage, registry.stat().st_mode & 0o777)
            state_stage = _stage(state, f"{port}\n".encode("ascii"))
        except BaseException:
            registry_stage.unlink(missing_ok=True)
            raise
        try:
            _replace(registry_stage, registry)
            try:
                _replace(state_stage, state)
            except BaseException:
                rollback = _stage(registry, raw.encode("utf-8"))
                os.chmod(rollback, registry.stat().st_mode & 0o777)
                try:
                    _replace(rollback, registry)
                except BaseException as exc:
                    raise DegradedNodeControl("iperf port registry rollback failed") from exc
                finally:
                    rollback.unlink(missing_ok=True)
                if old_state is not None:
                    state_rollback = _stage(state, old_state)
                    try:
                        _replace(state_rollback, state)
                    finally:
                        state_rollback.unlink(missing_ok=True)
                else:
                    state.unlink(missing_ok=True)
                raise
        finally:
            registry_stage.unlink(missing_ok=True)
            state_stage.unlink(missing_ok=True)
    return True


def apply_request(request, *, state_path=STATE_PATH, config_paths=CONFIG_PATHS,
                  lock_path=LOCK_PATH, backend=None, require_root=True):
    """Apply one ID-based edit or reset with config, service and state rollback."""
    if isinstance(request, dict) and request.get("action") == "iperf-port":
        return _apply_iperf_port(request, require_root=require_root)
    if isinstance(request, dict) and request.get("action") in ("create", "delete", "toggle"):
        return _apply_structure_request(request, state_path=state_path, config_paths=config_paths,
                                        lock_path=lock_path, backend=backend, require_root=require_root)
    if require_root and os.geteuid() != 0:
        raise PermissionError("node control requires root")
    if not isinstance(request, dict) or set(request) - {"action", "id", *EDIT_FIELDS} or \
            request.get("action") not in ("edit", "reset") or not isinstance(request.get("id"), str):
        raise NodeControlError("invalid node request")
    if request["action"] == "reset" and set(request) != {"action", "id"}:
        raise NodeControlError("reset has unexpected fields")
    backend = backend or HostBackend()
    Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        inventory = read_inventory(state_path=state_path, config_paths=config_paths)
        if inventory is None:
            inventory = initialize_inventory(state_path=state_path, config_paths=config_paths)
        matches = [node for node in inventory["nodes"] if node["id"] == request["id"]]
        if len(matches) != 1:
            raise NodeControlError("node ID not found")
        old = matches[0]
        reserved = _reserved_ports()
        module = "anytls" if old["protocol"] == "anytls" else "proxy"
        config_path = Path(config_paths[module])
        changes = {key: value for key, value in request.items() if key in EDIT_FIELDS - {"sni"}}
        if request["action"] == "reset":
            port = _random_free_port(inventory, reserved)
            changes = {"port": port, "credential": _random_credential(old["protocol"])}
        if not changes and "sni" not in request:
            raise NodeControlError("no changes requested")
        new_port = changes.get("port", old["port"])
        if new_port != old["port"]:
            if new_port in reserved:
                raise NodeControlError("requested port is reserved")
            _free_port(new_port)
        candidate = edit_node(inventory, old["id"], changes, reserved_ports=[])
        new = next(node for node in candidate["nodes"] if node["id"] == old["id"])
        cert_directory = None
        if "sni" in request:
            if old["protocol"] == "shadowsocks":
                raise NodeControlError("SNI does not apply to Shadowsocks")
            requested_sni = _sni(request["sni"])
            cert, key, cert_directory = _certificate(Path(state_path).parent, old["id"], requested_sni)
            new["inbound"]["tls"]["certificate_path"] = str(cert)
            new["inbound"]["tls"]["key_path"] = str(key)
        document = json.loads(config_path.read_text(encoding="utf-8"))
        changed_config = old["enabled"] and new["inbound"] != old["inbound"]
        staged = None
        old_bytes = config_path.read_bytes()
        opened = False
        swapped = False
        stopped = False
        state_written = False
        committed = False
        active = backend.active(SERVICES[module]) if changed_config else False
        try:
            if changed_config:
                proposed = _candidate_document(document, old, new)
                staged = _stage(config_path, json.dumps(proposed, ensure_ascii=False).encode("utf-8"))
                backend.check(staged)
                if new_port != old["port"]:
                    opened = True
                    backend.firewall(new_port, True, old["protocol"])
                    if active:
                        backend.stop(SERVICES[module])
                        stopped = True
                _replace(staged, config_path)
                swapped = True
            write_inventory(candidate, state_path=state_path)
            state_written = True
            backend.reconcile(state_path=state_path, config_paths=config_paths)
            if active:
                if stopped:
                    backend.start(SERVICES[module])
                else:
                    backend.restart(SERVICES[module])
            if old["enabled"] and new_port != old["port"]:
                backend.firewall(old["port"], False, old["protocol"])
            committed = True
            return candidate
        except BaseException as exc:
            if swapped or stopped or state_written:
                try:
                    if swapped:
                        restore = _stage(config_path, old_bytes)
                        try:
                            _replace(restore, config_path)
                        finally:
                            restore.unlink(missing_ok=True)
                    write_inventory(inventory, state_path=state_path)
                    backend.reconcile(state_path=state_path, config_paths=config_paths)
                    if active:
                        (backend.start if stopped else backend.restart)(SERVICES[module])
                    if old["enabled"] and new_port != old["port"]:
                        backend.firewall(old["port"], True, old["protocol"])
                    if opened:
                        backend.firewall(new_port, False, old["protocol"])
                except BaseException as recovery_error:
                    raise DegradedNodeControl("node rollback failed") from recovery_error
            elif opened:
                backend.firewall(new_port, False, old["protocol"])
            raise NodeControlError("node change failed; previous configuration restored") from exc
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)
            if cert_directory is not None and not committed:
                shutil.rmtree(cert_directory, ignore_errors=True)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("init", "apply"):
        return 2
    try:
        if sys.argv[1] == "init":
            if os.geteuid() != 0:
                return 1
            with open(LOCK_PATH, "a+b") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                initialize_inventory()
        else:
            raw = sys.stdin.buffer.read(4097)
            if len(raw) > 4096:
                return 2
            apply_request(json.loads(raw))
    except (InvalidInventory, NodeControlError, DegradedNodeControl, OSError,
            subprocess.SubprocessError, ValueError):
        # Detailed errors can contain paths or config facts. The console uses
        # its own localized status message and journalctl for diagnostics.
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
