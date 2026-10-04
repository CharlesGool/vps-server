"""Privileged console port changes and the host port registry.

The Web handler accepts a numeric port only. This helper rechecks the host,
persists the choice, restarts Web, and restores the old listener on failure.
"""

import errno
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
from datetime import date

try:
    from .state_paths import data_dir as state_data_dir
except ImportError:
    from state_paths import data_dir as state_data_dir


HEADER = "| Host Port | Project / Service | Bind Address | Registration Date |\n| --- | --- | --- | --- |\n"
ROW = re.compile(r"\|\s*(\d{1,5})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|")
OWNER = "vps-server-web"
UNIT = "vps-server-web.service"


def valid_port(value):
    return type(value) is int and 1024 <= value <= 65535


def read_rows(path):
    raw = path.read_bytes() if path.exists() else None
    text = raw.decode("utf-8") if raw is not None else HEADER
    if not text.startswith(HEADER):
        raise ValueError("invalid port registry")
    rows, seen = [], set()
    for line in text[len(HEADER):].splitlines():
        if not line.strip():
            continue
        match = ROW.fullmatch(line)
        if not match:
            raise ValueError("invalid port registry row")
        port, owner, bind, registered = match.groups()
        port = int(port)
        ipaddress.ip_address(bind)
        date.fromisoformat(registered)
        if not 1 <= port <= 65535 or port in seen:
            raise ValueError("invalid port registry entry")
        seen.add(port)
        rows.append((port, owner, bind, registered))
    return rows, raw


def atomic_bytes(path, payload, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".console-port-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def serialize_rows(rows):
    payload = HEADER + "".join(f"| {port} | {owner} | {bind} | {registered} |\n"
                               for port, owner, bind, registered in sorted(rows))
    return payload.encode("utf-8")


def write_rows(path, rows):
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    atomic_bytes(path, serialize_rows(rows), mode)


def reserve_owned_port(prefix, port, owner, *, probe=True):
    """Reserve a host port for an already validated internal service name."""
    if type(port) is not int or not 1 <= port <= 65535 or not re.fullmatch(r"[A-Za-z0-9 /_.-]+", owner):
        raise ValueError("invalid port reservation")
    root = Path(prefix).parent
    with (root / ".ports.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = root / "PORTS.md"
        rows, _ = read_rows(path)
        existing = [row for row in rows if row[0] == port]
        if existing:
            if existing[0][1] == owner:
                return False
            raise ValueError("port registered to another service")
        if probe:
            available(port)
        rows.append((port, owner, "0.0.0.0", date.today().isoformat()))
        write_rows(path, rows)
        return True


def release_owned_port(prefix, port, owner):
    if type(port) is not int or not 1 <= port <= 65535 or not re.fullmatch(r"[A-Za-z0-9 /_.-]+", owner):
        raise ValueError("invalid port reservation")
    root = Path(prefix).parent
    with (root / ".ports.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = root / "PORTS.md"
        rows, _ = read_rows(path)
        existing = [row for row in rows if row[0] == port]
        if not existing:
            return False
        if existing[0][1] != owner:
            raise ValueError("port registered to another service")
        write_rows(path, [row for row in rows if row[0] != port])
        return True


def available(port):
    """Probe TCP and UDP on both wildcard families before taking a port."""
    for family, address in ((socket.AF_INET, "0.0.0.0"), (socket.AF_INET6, "::")):
        for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
            try:
                with socket.socket(family, kind) as sock:
                    sock.bind((address, port))
            except OSError as exc:
                if family == socket.AF_INET6 and exc.errno in (errno.EAFNOSUPPORT, errno.EPROTONOSUPPORT):
                    continue
                raise ValueError("port unavailable") from exc


def reserved_ports(prefix):
    data = state_data_dir()
    ports = {80, 443, 5201}
    iperf = data / "iperf-port.txt"
    if iperf.exists():
        ports.add(int(iperf.read_text().strip()))
    rules = data / "portfwd.json"
    if rules.exists():
        for rule in json.loads(rules.read_text()):
            ports.add(int(rule["public_port"]))
    for config in (Path("/etc/vps-server-anytls/config.json"), Path("/etc/vps-server-proxy/config.json")):
        if config.exists():
            for inbound in json.loads(config.read_text()).get("inbounds", []):
                if "listen_port" in inbound:
                    ports.add(int(inbound["listen_port"]))
    frps = Path("/etc/vps-server-frps/frps.toml")
    if frps.exists():
        match = re.search(r"^bindPort\s*=\s*(\d+)\s*$", frps.read_text(), re.M)
        if not match:
            raise ValueError("cannot read FRPS port")
        ports.add(int(match[1]))
    lucky = Path("/etc/vps-server-lucky/config.json")
    if lucky.exists():
        ports.add(int(json.loads(lucky.read_text())["BaseConfigure"]["AdminWebListenPort"]))
    return ports


def healthy(port, unit=UNIT):
    if subprocess.run(["systemctl", "is-active", "--quiet", unit], check=False).returncode:
        return False
    pid = subprocess.run(["systemctl", "show", "--value", "-p", "MainPID", unit],
                         check=False, capture_output=True, text=True).stdout.strip()
    if not pid.isdecimal() or int(pid) < 1:
        return False
    try:
        listeners = subprocess.run(["ss", "-H", "-ltnp", "sport", "=", f":{port}"],
                                   check=False, capture_output=True, text=True)
        if listeners.returncode == 0:
            return f"pid={pid}," in listeners.stdout
    except OSError:
        pass
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def wait_healthy(port, seconds=20, unit=UNIT):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if healthy(port, unit):
            return
        time.sleep(0.25)
    raise RuntimeError("console did not bind the requested port")


def write_job(prefix, state, port, reason=""):
    path = state_data_dir() / "console-port-job.json"
    atomic_bytes(path, (json.dumps({"state": state, "port": port, "reason": reason}) + "\n").encode())


def change_port(prefix, old, new, port_file, *, restart=None, wait=None, probe=None):
    if not valid_port(old) or not valid_port(new) or new == old:
        raise ValueError("invalid console port")
    prefix, port_file = Path(prefix), Path(port_file)
    override = state_data_dir() / "console-port-override"
    registry = prefix.parent / "PORTS.md"
    restart = restart or (lambda: subprocess.run(["systemctl", "restart", UNIT], check=True, timeout=60))
    wait = wait or wait_healthy
    probe = probe or available
    with (prefix.parent / ".ports.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = (int(override.read_text().strip()) if override.exists() else
                   int(port_file.read_text().strip()) if port_file.exists() else old)
        if current != old:
            raise ValueError("console port changed before request was applied")
        rows, original_registry = read_rows(registry)
        old_rows = [row for row in rows if row[0] == old]
        if old_rows and old_rows[0][1] != OWNER:
            raise ValueError("current console port belongs to another service")
        if any(row[0] == new for row in rows) or new in reserved_ports(prefix):
            raise ValueError("port reserved")
        probe(new)
        original_port = port_file.read_bytes() if port_file.exists() else None
        original_override = override.read_bytes() if override.exists() else None
        replacement = [row for row in rows if row[0] != old]
        replacement.append((new, OWNER, "0.0.0.0", date.today().isoformat()))
        changed = False
        try:
            changed = True
            write_rows(registry, replacement)
            atomic_bytes(port_file, f"{new}\n".encode())
            atomic_bytes(override, f"{new}\n".encode())
            restart()
            wait(new)
        except BaseException:
            if changed:
                if original_registry is None:
                    registry.unlink(missing_ok=True)
                else:
                    atomic_bytes(registry, original_registry,
                                 registry.stat().st_mode & 0o777)
                for path, original in ((port_file, original_port), (override, original_override)):
                    if original is None:
                        path.unlink(missing_ok=True)
                    else:
                        atomic_bytes(path, original)
                restart()
                wait(old)
            raise


def register_current(prefix, port, unit=UNIT):
    """Record an already-running Web listener after installation."""
    if not valid_port(port):
        raise ValueError("invalid console port")
    prefix = Path(prefix)
    registry = prefix.parent / "PORTS.md"
    with (prefix.parent / ".ports.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows, _ = read_rows(registry)
        owners = [row[1] for row in rows if row[0] == port]
        if owners:
            if owners == [OWNER]:
                return
            raise ValueError("console port registered to another service")
        if not healthy(port, unit):
            raise RuntimeError("console is not listening")
        rows.append((port, OWNER, "0.0.0.0", date.today().isoformat()))
        write_rows(registry, rows)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) == 4 and args[0] in ("reserve", "release"):
        action, prefix, raw_port, owner = args
        if not raw_port.isascii() or not raw_port.isdecimal():
            raise ValueError("invalid port")
        changed = (reserve_owned_port(prefix, int(raw_port), owner) if action == "reserve"
                   else release_owned_port(prefix, int(raw_port), owner))
        print("changed" if changed else "unchanged")
    elif len(args) == 4 and args[0] == "register" and re.fullmatch(r"[A-Za-z0-9@_.-]+\.service", args[3]):
        register_current(args[1], int(args[2]), args[3])
    elif len(args) == 5 and args[0] == "change":
        _, prefix, old, new, port_file = args
        time.sleep(2)  # Let the browser receive the response before Web restarts.
        write_job(prefix, "running", int(new))
        try:
            change_port(prefix, int(old), int(new), port_file)
        except Exception as exc:
            write_job(prefix, "failed", int(new), str(exc))
            raise
        write_job(prefix, "done", int(new))
    else:
        raise SystemExit("invalid console port action")


if __name__ == "__main__":
    main()
