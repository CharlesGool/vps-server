"""Small, allowlisted interface to the locally installed Tailscale client."""

import ipaddress
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


BINARY = "/usr/local/bin/tailscale-vps-server"
UNIT = "vps-server-tailscale.service"
UNIT_PATH = Path("/etc/systemd/system") / UNIT
SOCKET = "/run/vps-server-tailscale/tailscaled.sock"
MEMORY_DROPIN = Path("/etc/systemd/system/vps-server-tailscale.service.d/30-memory.conf")
MEMORY_CONTENT = b"[Service]\nEnvironment=GOGC=10\n"
BOOL_SETTINGS = frozenset(("accept-dns", "accept-routes", "advertise-exit-node",
                           "shields-up", "snat-subnet-routes", "ssh",
                           "exit-node-allow-lan-access", "webclient"))


def call(*args, timeout=15):
    result = subprocess.run([BINARY, "--socket=" + SOCKET, *args], capture_output=True, text=True,
                            timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError("Tailscale command failed")
    return result.stdout


def read_json(*args):
    value = json.loads(call(*args))
    if not isinstance(value, dict):
        raise ValueError("unexpected Tailscale response")
    return value


def status():
    return read_json("status", "--json")


def prefs():
    return read_json("get", "--json")


def netcheck():
    return read_json("netcheck", "--format=json")


def set_bool(name, enabled):
    if name not in BOOL_SETTINGS or type(enabled) is not bool:
        raise ValueError("invalid Tailscale setting")
    call("set", f"--{name}={'true' if enabled else 'false'}")


def normalize_routes(value):
    routes = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        route = ipaddress.ip_network(item, strict=True)
        if route.is_multicast or route.is_unspecified or route.is_loopback:
            raise ValueError("invalid subnet route")
        routes.append(str(route))
    if len(routes) > 16 or len(set(routes)) != len(routes):
        raise ValueError("invalid subnet routes")
    return ",".join(routes)


def set_routes(value):
    call("set", "--advertise-routes=" + normalize_routes(value))


def set_relay_port(value):
    value = value.strip()
    if value and (not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 65535):
        raise ValueError("invalid peer relay port")
    call("set", "--relay-server-port=" + value)


def set_exit_node(value):
    call("set", "--exit-node=" + normalize_exit_node(value))


def normalize_exit_node(value):
    value = value.strip()
    if value and not (re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}", value)
                      or _valid_tail_ip(value)):
        raise ValueError("invalid exit node")
    return value


def set_many(values):
    """Apply one group of validated settings in a single Tailscale request."""
    names = BOOL_SETTINGS | {"advertise-routes", "exit-node", "relay-server-port"}
    if not values or set(values) - names:
        raise ValueError("invalid Tailscale settings")
    flags = []
    for name, value in values.items():
        if name in BOOL_SETTINGS:
            if type(value) is not bool:
                raise ValueError("invalid Tailscale setting")
            flags.append(f"--{name}={'true' if value else 'false'}")
        elif name == "advertise-routes":
            flags.append("--advertise-routes=" + normalize_routes(value))
        elif name == "exit-node":
            flags.append("--exit-node=" + normalize_exit_node(value))
        else:
            value = value.strip()
            if value and (not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 65535):
                raise ValueError("invalid peer relay port")
            flags.append("--relay-server-port=" + value)
    call("set", *flags)


def connect(login_server="", auth_key=""):
    login_server = login_server.strip()
    if login_server:
        url = urlsplit(login_server)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.query or url.fragment or len(login_server) > 255):
            raise ValueError("invalid control server URL")
    if len(auth_key) > 2048 or any(char in auth_key for char in "\r\n\0"):
        raise ValueError("invalid authentication key")
    command = ["up", "--timeout=10s"]
    if login_server:
        command.append("--login-server=" + login_server)
    key_path = None
    try:
        if auth_key:
            with tempfile.NamedTemporaryFile(mode="w", prefix="vps-tailscale-key-", delete=False) as temporary:
                key_path = Path(temporary.name)
                key_path.chmod(0o600)
                temporary.write(auth_key)
            command.append("--auth-key=file:" + str(key_path))
        return call(*command, timeout=13)
    finally:
        if key_path is not None:
            key_path.unlink(missing_ok=True)


def memory_mode():
    if MEMORY_DROPIN.is_symlink():
        raise ValueError("unsafe Tailscale memory drop-in")
    if not MEMORY_DROPIN.exists():
        return False
    if MEMORY_DROPIN.read_bytes() != MEMORY_CONTENT:
        raise ValueError("unrecognized Tailscale memory drop-in")
    return True


def set_memory_mode(enabled):
    if os.geteuid() != 0 or type(enabled) is not bool:
        raise PermissionError("root required")
    if not UNIT_PATH.is_file():
        raise FileNotFoundError("Tailscale service missing")
    if MEMORY_DROPIN.is_symlink():
        raise ValueError("unsafe Tailscale memory drop-in")
    previous = MEMORY_DROPIN.read_bytes() if MEMORY_DROPIN.is_file() else None
    if previous is not None and previous != MEMORY_CONTENT:
        raise ValueError("unrecognized Tailscale memory drop-in")
    if (previous is not None) == enabled:
        return
    MEMORY_DROPIN.parent.mkdir(parents=True, exist_ok=True)

    def replace(value):
        if value is None:
            MEMORY_DROPIN.unlink(missing_ok=True)
            return
        with tempfile.NamedTemporaryFile(mode="wb", dir=MEMORY_DROPIN.parent,
                                         prefix=".memory-", delete=False) as temporary:
            staged = Path(temporary.name)
            os.fchmod(temporary.fileno(), 0o644)
            temporary.write(value)
        try:
            os.replace(staged, MEMORY_DROPIN)
        finally:
            staged.unlink(missing_ok=True)

    try:
        replace(MEMORY_CONTENT if enabled else None)
        subprocess.run(["systemctl", "daemon-reload"], check=True, timeout=30)
        subprocess.run(["systemctl", "restart", UNIT], check=True, timeout=60)
        subprocess.run(["systemctl", "is-active", "--quiet", UNIT], check=True, timeout=10)
    except BaseException:
        replace(previous)
        subprocess.run(["systemctl", "daemon-reload"], check=False, timeout=30)
        subprocess.run(["systemctl", "restart", UNIT], check=False, timeout=60)
        raise


def _valid_tail_ip(value):
    try:
        address = ipaddress.ip_address(value)
        return address in ipaddress.ip_network("100.64.0.0/10") or address in ipaddress.ip_network("fd7a:115c:a1e0::/48")
    except ValueError:
        return False


def peers(snapshot):
    result = []
    peer_map = snapshot.get("Peer") or {}
    if not isinstance(peer_map, dict):
        return result
    for peer in peer_map.values():
        if not isinstance(peer, dict):
            continue
        try:
            rx, tx = int(peer.get("RxBytes") or 0), int(peer.get("TxBytes") or 0)
        except (TypeError, ValueError):
            rx = tx = 0
        result.append({"id": str(peer.get("ID") or ""),
                       "name": str(peer.get("HostName") or peer.get("DNSName") or ""),
                       "exit_option": peer.get("ExitNodeOption") is True,
                       "selector": str(peer.get("DNSName") or "").rstrip("."),
                       "addresses": [str(ip) for ip in peer.get("TailscaleIPs", []) if isinstance(ip, str)],
                       "online": peer.get("Online") is True,
                       "os": str(peer.get("OS") or ""),
                       "relay": str(peer.get("Relay") or ""),
                       "rx": rx,
                       "tx": tx,
                       "last_seen": str(peer.get("LastSeen") or "")})
    return sorted(result, key=lambda peer: (not peer["online"], peer["name"].lower()))


def local_subnets():
    """Suggest directly connected IPv4 networks without changing routing."""
    try:
        result = subprocess.run(["ip", "-j", "-4", "route", "show", "scope", "link"],
                                capture_output=True, text=True, timeout=5, check=True)
        routes = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    found = set()
    for route in routes if isinstance(routes, list) else []:
        if not isinstance(route, dict):
            continue
        try:
            network = ipaddress.ip_network(route.get("dst", ""), strict=True)
        except ValueError:
            continue
        if network.version == 4 and not (network.is_loopback or network.is_multicast or network.is_unspecified):
            found.add(str(network))
    return sorted(found)[:8]


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3 or sys.argv[1] != "memory" or sys.argv[2] not in ("on", "off"):
        raise SystemExit("invalid Tailscale helper action")
    set_memory_mode(sys.argv[2] == "on")
