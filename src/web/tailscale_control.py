"""Small, allowlisted interface to the locally installed Tailscale client."""

import ipaddress
import json
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


BINARY = "/usr/local/bin/tailscale-vps-server"
UNIT = "vps-server-tailscale.service"
SOCKET = "/run/vps-server-tailscale/tailscaled.sock"
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
    value = value.strip()
    if value and not (re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}", value)
                      or _valid_tail_ip(value)):
        raise ValueError("invalid exit node")
    call("set", "--exit-node=" + value)


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
                       "addresses": [str(ip) for ip in peer.get("TailscaleIPs", []) if isinstance(ip, str)],
                       "online": peer.get("Online") is True,
                       "os": str(peer.get("OS") or ""),
                       "relay": str(peer.get("Relay") or ""),
                       "rx": rx,
                       "tx": tx,
                       "last_seen": str(peer.get("LastSeen") or "")})
    return sorted(result, key=lambda peer: (not peer["online"], peer["name"].lower()))
