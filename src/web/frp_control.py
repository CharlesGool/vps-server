"""Privileged FRP edits. Requests arrive on stdin from a transient systemd unit."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import ipaddress
from datetime import date
import time
import unicodedata

try:
    from .console_port import read_rows, write_rows
except ImportError:  # Installed helpers are copied into one flat directory.
    from console_port import read_rows, write_rows


APP_DIR = Path(__file__).resolve().parent
if APP_DIR.parent.name == "src":
    APP_DIR = APP_DIR.parent.parent
CLIENT_DIR = Path(os.environ.get("VPSSRV_FRPC_DIR", "/etc/frp"))
SERVER_CONFIG = Path(os.environ.get("VPSSRV_FRPS_CONFIG", "/etc/vps-server-frps/frps.toml"))
CLIENT_BIN = Path(os.environ.get("VPSSRV_FRPC_BIN", "/usr/local/bin/frpc"))
CLIENT_UNIT = Path(os.environ.get("VPSSRV_FRPC_UNIT", "/etc/systemd/system/frpc@.service"))
SERVER_SETUP_SOURCES = (
    APP_DIR / "installer-source" / "deploy" / "frps" / "setup-frps.sh",
    APP_DIR / "frps" / "setup-frps.sh",
)
REGISTRY = APP_DIR.parent / "PORTS.md"
LOCK = APP_DIR.parent / ".ports.lock"
ASCII_NAME = re.compile(r"[a-zA-Z0-9_-]{1,32}\Z")


def valid_client_name(name):
    return (isinstance(name, str) and 1 <= len(name) <= 32 and
            unicodedata.normalize("NFC", name) == name and
            all(char in "_-" or unicodedata.category(char)[0] in "LN" for char in name))


def client_path(name):
    if not valid_client_name(name):
        raise ValueError("invalid instance name")
    return CLIENT_DIR / ("frpc-" + name + ".toml")


def client_unit(name):
    """Keep legacy ASCII units; map Unicode names to a stable ASCII instance."""
    client_path(name)
    if ASCII_NAME.fullmatch(name):
        return f"frpc@{name}.service"
    suffix = hashlib.sha256(name.encode("utf-8")).hexdigest()[:24]
    return f"frpc@u-{suffix}.service"


def client_alias(name):
    """The existing systemd template uses %i, so Unicode needs an ASCII alias."""
    unit = client_unit(name)
    if ASCII_NAME.fullmatch(name):
        return None
    instance = unit.removeprefix("frpc@").removesuffix(".service")
    return CLIENT_DIR / f"frpc-{instance}.toml"


def _ensure_client_alias(name):
    alias = client_alias(name)
    if alias is None:
        return False
    target = client_path(name).name
    if alias.is_symlink():
        if os.readlink(alias) == target:
            return False
        raise ValueError("FRPC alias occupied")
    if alias.exists():
        raise ValueError("FRPC alias occupied")
    alias.symlink_to(target)
    return True


def _remove_client_alias(name):
    alias = client_alias(name)
    if alias is not None and alias.is_symlink() and os.readlink(alias) == client_path(name).name:
        alias.unlink()


def client_names(directory=None):
    directory = Path(directory) if directory is not None else CLIENT_DIR
    if not directory.is_dir():
        return []
    return sorted(p.name[5:-5] for p in directory.glob("frpc-*.toml")
                  if valid_client_name(p.name[5:-5]) and p.is_file() and not p.is_symlink())


def client_summary(name):
    path = client_path(name)
    text = path.read_text(encoding="utf-8")
    # The editor accepts the documented TCP template. Unsupported existing
    # configs remain readable in the raw editor and are verified by frpc.
    server = re.search(r'^serverAddr\s*=\s*"([^"]+)"', text, re.M)
    port = re.search(r'^serverPort\s*=\s*(\d+)', text, re.M)
    return {"name": name, "server": server.group(1) if server else "",
            "port": int(port.group(1)) if port else None,
            "proxies": text.count("[[proxies]]")}


def structured_client(name):
    """Return editable fields only for the simple TCP/UDP FRPC layout we can preserve."""
    data = {"auth": {}, "proxies": []}
    current = data
    for raw in client_path(name).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[[proxies]]":
            current = {}
            data["proxies"].append(current)
            continue
        match = re.fullmatch(r'([\w.]+)\s*=\s*("(?:[^"\\]|\\.)*"|\d+)\s*(?:#.*)?', line)
        if not match:
            return None
        key, value = match.groups()
        if key.startswith("auth.") and current is data:
            current = data["auth"]
            key = key[5:]
            destination = current
            current = data
        else:
            destination = current
        if key in destination:
            return None
        try:
            destination[key] = json.loads(value)
        except ValueError:
            return None
    allowed = {"serverAddr", "serverPort", "auth", "proxies"}
    if set(data) - allowed or set(data["auth"]) - {"method", "token"}:
        return None
    if not {"serverAddr", "serverPort"} <= set(data) or not {"method", "token"} <= set(data["auth"]):
        return None
    proxies = data.get("proxies", [])
    fields = {"name", "type", "localIP", "localPort", "remotePort"}
    if not isinstance(proxies, list) or any(not isinstance(p, dict) or set(p) - fields or p.get("type") not in ("tcp", "udp") for p in proxies):
        return None
    if any(set(p) != fields for p in proxies):
        return None
    if data.get("auth", {}).get("method") != "token":
        return None
    return data


def build_client(server, port, token, proxies):
    try:
        ipaddress.ip_address(server)
    except ValueError as exc:
        raise ValueError("server IP required") from exc
    if type(port) is not int or not 1 <= port <= 65535 or not isinstance(token, str) or not token or len(token) > 128:
        raise ValueError("invalid server settings")
    if not isinstance(proxies, list) or len(proxies) > 64:
        raise ValueError("invalid proxies")
    lines = [f"serverAddr = {json.dumps(server)}", f"serverPort = {port}",
             'auth.method = "token"', f"auth.token = {json.dumps(token)}"]
    names = set()
    for item in proxies:
        if set(item) != {"name", "type", "localIP", "localPort", "remotePort"}:
            raise ValueError("invalid proxy fields")
        name = item["name"]
        if not isinstance(name, str) or not 1 <= len(name) <= 64 or name in names or item["type"] not in ("tcp", "udp"):
            raise ValueError("invalid proxy")
        names.add(name)
        try:
            ipaddress.ip_address(item["localIP"])
        except ValueError as exc:
            raise ValueError("invalid local IP") from exc
        if any(type(item[key]) is not int or not 1 <= item[key] <= 65535 for key in ("localPort", "remotePort")):
            raise ValueError("invalid proxy port")
        lines.extend(["", "[[proxies]]", f'name = {json.dumps(name)}', f'type = {json.dumps(item["type"])}',
                      f'localIP = {json.dumps(item["localIP"])}', f'localPort = {item["localPort"]}',
                      f'remotePort = {item["remotePort"]}'])
    return "\n".join(lines) + "\n"


def update_structured(name, section, values):
    """Mutate one field group against the latest file under save_client's rollback path."""
    data = structured_client(name)
    if data is None:
        raise ValueError("advanced FRPC configuration")
    auth = data["auth"]
    proxies = data.get("proxies", [])
    if section == "server":
        server = values["server"]
        port = values["port"]
        token = values["token"] or auth["token"]
    else:
        server, port, token = data["serverAddr"], data["serverPort"], auth["token"]
        if section == "add":
            proxies.append(values["proxy"])
        elif section in ("edit", "delete"):
            index = values.get("index")
            if type(index) is not int or not 0 <= index < len(proxies):
                raise ValueError("invalid proxy index")
            if section == "edit":
                proxies[index] = values["proxy"]
            else:
                proxies.pop(index)
        else:
            raise ValueError("invalid proxy section")
    save_client(name, build_client(server, port, token, proxies))


def _rows():
    return read_rows(REGISTRY)[0]


def _save_rows(rows):
    write_rows(REGISTRY, rows)


def _free_port(port):
    for family, address in ((socket.AF_INET, "0.0.0.0"), (socket.AF_INET6, "::")):
        for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
            try:
                with socket.socket(family, kind) as sock:
                    sock.bind((address, port))
            except OSError as exc:
                if family == socket.AF_INET6 and exc.errno in (97, 93):
                    continue
                raise ValueError("port unavailable") from exc


def _local_client_ports(content):
    address = re.search(r'^serverAddr\s*=\s*"([^"]+)"\s*$', content, re.M)
    if not address:
        raise ValueError("serverAddr is required")
    host = address[1]
    local = host in {"localhost", socket.gethostname()}
    try:
        for family, kind, protocol, _, address in socket.getaddrinfo(host, 0, type=socket.SOCK_STREAM):
            try:
                with socket.socket(family, kind, protocol) as probe:
                    probe.bind(address)
                local = True
                break
            except OSError:
                continue
    except OSError:
        pass
    if not local:
        return set()
    ports = set()
    values = re.findall(r'^remotePort\s*=\s*(\d+)\s*$', content, re.M)
    if len(values) != len(re.findall(r'^\s*remotePort\s*=', content, re.M)):
        raise ValueError("unsupported same-host remote port syntax")
    for value in values:
        port = int(value)
        if not 1 <= port <= 65535 or port in ports:
            raise ValueError("invalid or duplicate remote port")
        ports.add(port)
    return ports


def _reserve_client_ports(name, wanted, current):
    rows = _rows()
    owner = "vps-server frpc " + name
    for port in wanted - current:
        if any(row[0] == port for row in rows):
            raise ValueError("remote port registered")
        _free_port(port)
    for port in current:
        if not any(row[0] == port and row[1] == owner for row in rows):
            raise ValueError("current remote port is not registered to this instance")
    rows.extend((port, owner, "0.0.0.0", date.today().isoformat()) for port in wanted - current)
    if wanted - current:
        _save_rows(rows)


def _release_client_ports(name, ports):
    if ports:
        owner = "vps-server frpc " + name
        _save_rows([row for row in _rows() if not (row[0] in ports and row[1] == owner)])


def _write_private(path, content):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".frp-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def save_server(port, token):
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("invalid port")
    if not isinstance(token, str) or not 1 <= len(token) <= 128 or "\n" in token or "\r" in token:
        raise ValueError("invalid token")
    old = SERVER_CONFIG.read_text(encoding="utf-8")
    match = re.search(r"^bindPort\s*=\s*(\d+)\s*$", old, re.M)
    if not match:
        raise ValueError("unsupported FRPS config")
    old_port = int(match[1])
    setup = next((path for path in SERVER_SETUP_SOURCES if path.is_file()), None)
    if setup is None:
        raise ValueError("FRPS installer unavailable")
    with LOCK.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows = _rows()
        owner = "vps-server frps"
        current = next((row for row in rows if row[0] == old_port), None)
        if current is not None and current[1] != owner:
            raise ValueError("FRPS port registered to another service")
        if current is None:
            address = re.search(r'^bindAddr\s*=\s*"([^"]+)"', old, re.M)
            bind = address[1] if address else "0.0.0.0"
            ipaddress.ip_address(bind)
            rows.append((old_port, owner, bind, date.today().isoformat()))
            _save_rows(rows)
        if port != old_port:
            if any(row[0] == port for row in rows):
                raise ValueError("port registered")
            _free_port(port)
            rows.append((port, owner, "0.0.0.0", date.today().isoformat()))
            _save_rows(rows)
        try:
            env = dict(os.environ, PREFIX=str(APP_DIR), FRPS_BIND_PORT=str(port), FRPS_TOKEN=token)
            subprocess.run(["bash", str(setup)], env=env, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        except BaseException:
            if port != old_port:
                _save_rows([row for row in _rows() if not (row[0] == port and row[1] == owner)])
            raise
        if port != old_port:
            rows = _rows()
            _save_rows([row for row in rows if not (row[0] == old_port and row[1] == owner)])


def save_client(name, content):
    path = client_path(name)
    if path.is_symlink():
        raise ValueError("symlink config rejected")
    if not CLIENT_BIN.is_file() or not CLIENT_UNIT.is_file():
        raise ValueError("FRPC is unavailable")
    if not isinstance(content, str) or not 1 <= len(content.encode("utf-8")) <= 16384:
        raise ValueError("invalid config length")
    with LOCK.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        old = path.read_text(encoding="utf-8") if path.exists() else None
        old_ports = _local_client_ports(old) if old else set()
        new_ports = _local_client_ports(content)
        unit = client_unit(name)
        was_active = subprocess.run(["systemctl", "is-active", "--quiet", unit]).returncode == 0
        was_enabled = subprocess.run(["systemctl", "is-enabled", "--quiet", unit]).returncode == 0
        _write_private(path, content)
        alias_created = False
        try:
            subprocess.run([str(CLIENT_BIN), "verify", "-c", str(path)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            alias_created = _ensure_client_alias(name)
            if old is None or was_active:
                _reserve_client_ports(name, new_ports, old_ports if was_active else set())
            if old is None:
                subprocess.run(["systemctl", "enable", "--now", unit], check=True, timeout=60,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif was_active:
                subprocess.run(["systemctl", "restart", unit], check=True, timeout=60,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if old is None or was_active:
                subprocess.run(["systemctl", "is-active", "--quiet", unit], check=True)
        except BaseException:
            if alias_created:
                _remove_client_alias(name)
            if old is None or was_active:
                _release_client_ports(name, new_ports - (old_ports if was_active else set()))
            if old is None:
                subprocess.run(["systemctl", "disable", "--now", unit], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                path.unlink(missing_ok=True)
            else:
                _write_private(path, old)
                if was_active:
                    subprocess.run(["systemctl", "restart", unit], check=False,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if not was_enabled:
                    subprocess.run(["systemctl", "disable", unit], check=False,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            raise
        if was_active:
            _release_client_ports(name, old_ports - new_ports)


def toggle_client(name, enable):
    path = client_path(name)
    if not path.is_file() or path.is_symlink():
        raise ValueError("FRPC instance missing")
    unit = client_unit(name)
    with LOCK.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ports = _local_client_ports(path.read_text(encoding="utf-8"))
        if enable:
            _reserve_client_ports(name, ports, set())
        try:
            subprocess.run(["systemctl", "enable" if enable else "disable", "--now", unit],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        except BaseException:
            if enable:
                _release_client_ports(name, ports)
            raise
        if not enable:
            _release_client_ports(name, ports)


def rename_client(name, new_name):
    """Move one template instance, preserving its running and boot states."""
    old_path, new_path = client_path(name), client_path(new_name)
    if name == new_name:
        return
    if not old_path.is_file() or old_path.is_symlink() or new_path.exists() or new_path.is_symlink():
        raise ValueError("FRPC instance missing or destination occupied")
    old_unit, new_unit = client_unit(name), client_unit(new_name)
    with LOCK.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not old_path.is_file() or old_path.is_symlink() or new_path.exists() or new_path.is_symlink():
            raise ValueError("FRPC instance changed")
        rows = _rows()
        was_active = subprocess.run(["systemctl", "is-active", "--quiet", old_unit]).returncode == 0
        was_enabled = subprocess.run(["systemctl", "is-enabled", "--quiet", old_unit]).returncode == 0
        moved = False
        new_alias_created = False
        try:
            subprocess.run(["systemctl", "disable", "--now", old_unit], check=True, timeout=60)
            os.replace(old_path, new_path)
            moved = True
            new_alias_created = _ensure_client_alias(new_name)
            _save_rows([(port, "vps-server frpc " + new_name if owner == "vps-server frpc " + name else owner,
                         bind, recorded) for port, owner, bind, recorded in rows])
            if was_enabled:
                subprocess.run(["systemctl", "enable", new_unit], check=True, timeout=60)
            if was_active:
                subprocess.run(["systemctl", "start", new_unit], check=True, timeout=60)
                subprocess.run(["systemctl", "is-active", "--quiet", new_unit], check=True)
            _remove_client_alias(name)
        except BaseException:
            subprocess.run(["systemctl", "disable", "--now", new_unit], check=False, timeout=60)
            if new_alias_created:
                _remove_client_alias(new_name)
            if moved:
                os.replace(new_path, old_path)
            _save_rows(rows)
            if was_enabled:
                subprocess.run(["systemctl", "enable", old_unit], check=False, timeout=60)
            if was_active:
                subprocess.run(["systemctl", "start", old_unit], check=False, timeout=60)
            raise


def delete_client(name):
    """Remove an instance from the UI, retaining a private recovery copy."""
    path = client_path(name)
    if not path.is_file() or path.is_symlink():
        raise ValueError("FRPC instance missing")
    unit = client_unit(name)
    with LOCK.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not path.is_file() or path.is_symlink():
            raise ValueError("FRPC instance changed")
        rows = _rows()
        was_active = subprocess.run(["systemctl", "is-active", "--quiet", unit]).returncode == 0
        was_enabled = subprocess.run(["systemctl", "is-enabled", "--quiet", unit]).returncode == 0
        archive = CLIENT_DIR / f".deleted-frpc-{name}-{time.time_ns()}.toml"
        moved = False
        try:
            subprocess.run(["systemctl", "disable", "--now", unit], check=True, timeout=60)
            os.replace(path, archive)
            moved = True
            _save_rows([row for row in rows if row[1] != "vps-server frpc " + name])
            _remove_client_alias(name)
        except BaseException:
            if moved:
                os.replace(archive, path)
            _save_rows(rows)
            if was_enabled:
                subprocess.run(["systemctl", "enable", unit], check=False, timeout=60)
            if was_active:
                subprocess.run(["systemctl", "start", unit], check=False, timeout=60)
            raise


def toggle_server(enable):
    if not SERVER_CONFIG.is_file():
        raise ValueError("FRPS is unavailable")
    unit = "vps-server-frps.service"
    subprocess.run(["systemctl", "enable" if enable else "disable", "--now", unit],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
    expected = "active" if enable else "inactive"
    actual = subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True, timeout=10)
    if actual.stdout.strip() != expected:
        raise ValueError("FRPS state did not change")


def main():
    if os.geteuid() != 0:
        raise ValueError("root required")
    request = json.load(sys.stdin)
    action = request.get("action")
    if action == "server":
        save_server(request.get("port"), request.get("token"))
    elif action == "client":
        save_client(request.get("name"), request.get("content"))
    elif action in ("enable", "disable"):
        toggle_client(request.get("name"), action == "enable")
    elif action in ("server-enable", "server-disable"):
        toggle_server(action == "server-enable")
    elif action == "structured-client":
        update_structured(request.get("name"), request.get("section"), request.get("values"))
    elif action == "create-structured-client":
        values = request.get("values")
        if not isinstance(values, dict) or client_path(request.get("name")).exists():
            raise ValueError("invalid new instance")
        save_client(request["name"], build_client(values.get("server"), values.get("port"),
                                                  values.get("token"), []))
    elif action == "rename-client":
        rename_client(request.get("name"), request.get("new_name"))
    elif action == "delete-client":
        delete_client(request.get("name"))
    else:
        raise ValueError("invalid action")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(type(exc).__name__, file=sys.stderr)
        raise SystemExit(1)
