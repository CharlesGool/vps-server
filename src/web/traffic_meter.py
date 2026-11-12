#!/usr/bin/env python3
"""Traffic accounting and limits for the other features that carry traffic.

Sing-box nodes and FRPS have their own meters (node_meter.py, frps_meter.py).
This one covers what is left, with the same counters, traffic cap (throttle to
1 Mbps or block), speed limits, validity period and reset schedule:

    caddy           domain forwarding: everything Caddy serves on 80 and 443
    iperf3          the iperf3 port
    portfwd:<id>    one port forwarding rule, forwarded packets to and from its target
    frpc:<name>     one FRPC instance, its connection to the FRPS server
    tailscale       the tailscale0 interface; forwarded packets (exit node,
                    subnet routes) count twice, they cross the network twice

Each entry counts its traffic once or twice ("billable_multiplier"): port
forwarding relays every byte in and out again, so twice, like a node; the
others carry it once. Mini Drive and the speed test share the console's port
and are metered inside the console instead (app_meter.py).

An entry stays while its feature may come back (a module switched off or
uninstalled keeps its limits and totals, with no rules); a deleted forwarding
rule or FRPC instance takes its entry with it.

State (root only): /etc/vps-server-traffic/traffic.json holds the entries,
meter.json the meter ledger, one nft table vps_server_traffic. Unlike the node
meter a failure here stops nothing: these features are not built around a
limit, so the meter logs and retries.

    traffic_meter.py run          systemd service loop
    traffic_meter.py apply        read one {"action": "edit", "id": ..., ...} request on stdin
    traffic_meter.py delete-table remove the nft table (uninstall)
"""

import fcntl
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

try:
    from .node_inventory import InvalidInventory, validate_metering
    from .node_state import _read_json, write_json
except ImportError:  # Installed helpers are copied into one flat directory.
    from node_inventory import InvalidInventory, validate_metering
    from node_state import _read_json, write_json

STATE_DIR = Path(os.environ.get("VPSSRV_TRAFFIC_DIR", "/etc/vps-server-traffic"))
STATE_PATH = STATE_DIR / "traffic.json"
METER_PATH = STATE_DIR / "meter.json"
LOCK_PATH = STATE_DIR / "traffic.lock"
TABLE = "vps_server_traffic"
DATA_DIR = Path(os.environ.get("VPSSRV_DATA_DIR", "/var/lib/vps-server/data"))
PREFIX = Path(os.environ.get("VPSSRV_PREFIX", Path(__file__).resolve().parents[2]))
WEB_UNIT = Path("/etc/systemd/system/vps-server-web.service")
CADDY_WANTED = Path("/etc/systemd/system/multi-user.target.wants/vps-server-caddy.service")
FRPC_DIR = Path("/etc/frp")
TAILSCALE_INTERFACE = "tailscale0"
LIMIT_FIELDS = frozenset(("cap_bytes", "cap_action", "upload_limit_bps", "download_limit_bps",
                          "expiry_count", "expiry_unit", "expires_at", "reset_mode", "next_reset_at"))
FIELDS = frozenset(("id", "key", "name", "enabled", "billable_multiplier", "upload_bytes", "download_bytes",
                    "total_upload_bytes", "total_download_bytes", "counter_epoch")) | LIMIT_FIELDS
KEY_RE = re.compile(r"(caddy|iperf3|tailscale|portfwd:[0-9a-f]{1,32}|frpc:[A-Za-z0-9_.-]{1,64})")
RESOLVE_SECONDS = 300
_resolved = {}


def validate(inventory):
    if not isinstance(inventory, dict) or set(inventory) != {"version", "nodes"} or \
            inventory["version"] != 1 or not isinstance(inventory["nodes"], list):
        raise InvalidInventory("invalid traffic state")
    keys = set()
    for entry in inventory["nodes"]:
        if not isinstance(entry, dict) or set(entry) - {"matches"} != FIELDS:
            raise InvalidInventory("invalid traffic entry fields")
        uuid.UUID(entry["id"])
        if not isinstance(entry["key"], str) or not KEY_RE.fullmatch(entry["key"]) or entry["key"] in keys:
            raise InvalidInventory("invalid traffic entry key")
        keys.add(entry["key"])
        if entry["enabled"] is not True or entry["billable_multiplier"] not in (1, 2) or \
                not isinstance(entry["name"], str) or len(entry["name"]) > 80:
            raise InvalidInventory("invalid traffic entry")
        validate_metering(entry)


def new_entry(key, name, multiplier):
    return {"id": str(uuid.uuid4()), "key": key, "name": name, "enabled": True,
            "billable_multiplier": multiplier,
            "cap_bytes": None, "cap_action": "throttle", "upload_limit_bps": None,
            "download_limit_bps": None, "expiry_count": None, "expiry_unit": None,
            "expires_at": None, "reset_mode": "none", "next_reset_at": None,
            "upload_bytes": 0, "download_bytes": 0, "total_upload_bytes": 0,
            "total_download_bytes": 0, "counter_epoch": 0}


# -- what each feature looks like right now ---------------------------------------

def _unit_env(name):
    try:
        text = WEB_UNIT.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(rf"^Environment={re.escape(name)}=(\S+)\s*$", text, re.M)
    return match.group(1) if match else None


def _installed():
    try:
        from module_manager import installed_modules
        return installed_modules(str(PREFIX))
    except Exception:  # A broken install state must not stop metering the rest.
        return set()


def _iperf_port():
    for value in (_read_text(DATA_DIR / "iperf-port.txt"), _unit_env("VPSSRV_IPERF_PORT"), "5201"):
        if value and value.isdigit() and 1 <= int(value) <= 65535:
            return int(value)
    return None


def _read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _port_forward_rules():
    try:
        rules = json.loads((DATA_DIR / "portfwd.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    switch = _read_text(DATA_DIR / "portfwd-enabled")
    on = switch != "0" and _unit_env("VPSSRV_PORTFWD_ENABLE") != "0"
    found = []
    for rule in rules if isinstance(rules, list) else []:
        try:
            target = str(ipaddress.IPv4Address(rule["target_host"]))
            port = int(rule["target_port"])
            protocols = ["tcp", "udp"] if rule["protocol"] == "both" else [rule["protocol"]]
            if not re.fullmatch(r"[0-9a-f]{1,32}", rule["id"]) or not 1 <= port <= 65535 or \
                    set(protocols) - {"tcp", "udp"}:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        label = str(rule.get("label") or "")[:60] or f'{rule.get("public_port")} → {target}:{port}'
        found.append((rule["id"], label, target, port, protocols, on and rule.get("enabled") is True))
    return found


def _resolve(host):
    """IPv4 and IPv6 addresses of an FRPS server, refreshed every few minutes."""
    now = time.monotonic()
    cached = _resolved.get(host)
    if cached and now - cached[0] < RESOLVE_SECONDS:
        return cached[1]
    try:
        literal = ipaddress.ip_address(host)
        addresses = [str(literal)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
            addresses = sorted({info[4][0] for info in infos})
        except OSError:
            addresses = cached[1] if cached else []
    _resolved[host] = (now, addresses)
    return addresses


def _frpc_instances():
    try:
        from frp_control import client_names
        names = client_names(FRPC_DIR)
    except Exception:
        return []
    found = []
    for name in names:
        text = _read_text(FRPC_DIR / f"frpc-{name}.toml") or ""
        server = re.search(r'^serverAddr\s*=\s*"([^"]+)"', text, re.M)
        port = re.search(r"^serverPort\s*=\s*(\d+)", text, re.M)
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", name):
            continue
        addresses = _resolve(server.group(1)) if server else []
        number = int(port.group(1)) if port else 7000
        found.append((name, addresses if 1 <= number <= 65535 else [], number))
    return found


def _nfproto(address):
    return "ipv6" if ":" in address else "ipv4"


def live_entries():
    """{key: (display name, multiplier, matches)} for every feature present now.

    matches is empty while the feature is installed but off: the entry keeps
    its totals and limits and simply sees no traffic.
    """
    live = {}
    installed = _installed()
    if "caddy" in installed or CADDY_WANTED.exists():
        matches = []
        if CADDY_WANTED.exists():
            for family in ("ipv4", "ipv6"):
                for direction, chain, field in (("upload", "input", "dport"), ("download", "output", "sport")):
                    matches.append((family, direction, chain, f"meta nfproto {family} tcp {field} {{ 80, 443 }}", 1))
                    matches.append((family, direction, chain, f"meta nfproto {family} udp {field} 443", 1))
        live["caddy"] = ("Caddy", 1, matches)
    if "iperf3" in installed:
        port = _iperf_port()
        matches = [(family, direction, chain, f"meta nfproto {family} {protocol} {field} {port}", 1)
                   for family in ("ipv4", "ipv6")
                   for direction, chain, field in (("upload", "input", "dport"), ("download", "output", "sport"))
                   for protocol in ("tcp", "udp")] if port else []
        live["iperf3"] = ("iPerf3", 1, matches)
    if "tailscale" in installed:
        name = TAILSCALE_INTERFACE
        matches = []
        for family in ("ipv4", "ipv6"):
            proto = f"meta nfproto {family}"
            matches += [(family, "upload", "input", f'{proto} iifname "{name}"', 1),
                        (family, "download", "output", f'{proto} oifname "{name}"', 1),
                        # Exit node and subnet routes: the tunnel side and the
                        # internet side are both this host's traffic.
                        (family, "upload", "forward", f'{proto} iifname "{name}"', 2),
                        (family, "download", "forward", f'{proto} oifname "{name}"', 2)]
        live["tailscale"] = ("Tailscale", 1, matches)
    for rule_id, label, target, port, protocols, active in _port_forward_rules():
        matches = [("ipv4", direction, "forward",
                    f"meta nfproto ipv4 ip {side}addr {target} {protocol} {side[0]}port {port}", 1)
                   for protocol in protocols
                   for direction, side in (("upload", "d"), ("download", "s"))] if active else []
        live[f"portfwd:{rule_id}"] = (label, 2, matches)
    for name, addresses, port in _frpc_instances():
        matches = []
        for address in addresses:
            family = _nfproto(address)
            field = "ip6" if family == "ipv6" else "ip"
            for protocol in ("tcp", "udp"):
                matches += [(family, "upload", "output",
                             f"meta nfproto {family} {field} daddr {address} {protocol} dport {port}", 1),
                            (family, "download", "input",
                             f"meta nfproto {family} {field} saddr {address} {protocol} sport {port}", 1)]
        live[f"frpc:{name}"] = (name, 1, matches)
    return live


# -- state -------------------------------------------------------------------------

def _stored():
    state = _read_json(STATE_PATH)
    if state is None:
        return {"version": 1, "nodes": []}
    validate(state)
    return state


def read_state(*, state_path=None, config_paths=None):
    """Stored entries joined with what each feature looks like now, for one tick."""
    state = _stored()
    live = live_entries()
    entries = {entry["key"]: entry for entry in state["nodes"]}
    nodes = []
    for key in sorted(set(entries) | set(live)):
        entry = entries.get(key)
        if key not in live:
            # A deleted forwarding rule or FRPC instance is gone for good; a
            # module that is off or removed may come back with its limits.
            if key.startswith(("portfwd:", "frpc:")):
                continue
            nodes.append({**entry, "matches": []})
            continue
        name, multiplier, matches = live[key]
        entry = entry or new_entry(key, name, multiplier)
        nodes.append({**entry, "name": name[:80], "billable_multiplier": multiplier, "matches": matches})
    inventory = {"version": 1, "nodes": nodes}
    validate(inventory)
    return inventory


def write_state(inventory, *, state_path=None):
    stored = {"version": 1, "nodes": [{k: v for k, v in entry.items() if k != "matches"}
                                      for entry in inventory["nodes"]]}
    validate(stored)
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    write_json(stored, STATE_PATH)


def _locked():
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    handle = open(LOCK_PATH, "a+b")
    fcntl.flock(handle, fcntl.LOCK_EX)
    return handle


def apply(request):
    """Change one entry's cap, speed limits, validity or reset schedule; counters stay."""
    if not isinstance(request, dict) or request.get("action") != "edit" or \
            not isinstance(request.get("id"), str) or \
            set(request) - {"action", "id"} - LIMIT_FIELDS or not set(request) - {"action", "id"}:
        raise InvalidInventory("invalid traffic request")
    with _locked():
        state = _stored()
        entry = next((item for item in state["nodes"] if item["id"] == request["id"]), None)
        if entry is None:
            raise InvalidInventory("unknown traffic entry")
        for key in LIMIT_FIELDS & set(request):
            entry[key] = request[key]
        validate(state)
        write_json(state, STATE_PATH)
        return state


def tick(**kwargs):
    from node_meter import tick as meter_tick
    return meter_tick(state_path=STATE_PATH, config_paths={}, meter_path=METER_PATH, lock_path=LOCK_PATH,
                      table=TABLE, reader=read_state, writer=write_state, validate=validate, **kwargs)


def delete_table():
    from nft_runtime import command
    binary, env = command()
    return subprocess.run([binary, "delete", "table", "inet", TABLE], capture_output=True,
                          timeout=20, env=env, check=False).returncode


def run():
    from node_meter import _notify_ready
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    notified = False
    failing = None
    while True:
        try:
            tick()
            failing = None
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, InvalidInventory) as exc:
            message = f"{type(exc).__name__}: {exc}"[:300]
            if message != failing:  # Say it once, not every two seconds.
                print(f"Traffic accounting failed, retrying: {message}", file=sys.stderr, flush=True)
                failing = message
            time.sleep(28)
        if not notified:
            _notify_ready()
            notified = True
        time.sleep(2)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv not in (["run"], ["apply"], ["delete-table"]):
        print("usage: traffic_meter.py run|apply|delete-table", file=sys.stderr)
        return 2
    if os.geteuid() != 0:
        return 1
    try:
        if argv == ["run"]:
            return run()
        if argv == ["apply"]:
            raw = sys.stdin.buffer.read(4097)
            if len(raw) > 4096:
                return 2
            apply(json.loads(raw))
        else:
            return 0 if delete_table() in (0, 1) else 1
    except (InvalidInventory, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Traffic {argv[0]} failed: {type(exc).__name__}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
