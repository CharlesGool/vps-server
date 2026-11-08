#!/usr/bin/env python3
"""Traffic accounting and limits for the FRPS server, the same as a sing-box node.

Every frpc tunnel, and so every byte a visitor sends through FRPS, crosses the
FRPS bindPort. Metering that one port with the node meter's rules gives FRPS the
same upload/download counters, traffic cap (throttle to 1 Mbps or block), speed
limits, validity period and reset schedule as a node. The billable total is
doubled like a node's, because the host also carries the visitor side.

State lives beside frps.toml in /etc/vps-server-frps: traffic.json holds the
one entry (node fields without the sing-box inbound), traffic-meter.json the
meter ledger. The nft table is separate from the node table. When accounting
fails the meter stops FRPS rather than leave its traffic unlimited.

    frps_meter.py run          systemd service loop
    frps_meter.py init         create the entry if missing (root)
    frps_meter.py apply        read one {"action": "edit", ...} request on stdin (root)
    frps_meter.py delete-table remove the nft table (uninstall)
"""

import fcntl
import json
import os
import re
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


STATE_DIR = Path(os.environ.get("VPSSRV_FRPS_STATE_DIR", "/etc/vps-server-frps"))
CONFIG_PATH = STATE_DIR / "frps.toml"
STATE_PATH = STATE_DIR / "traffic.json"
METER_PATH = STATE_DIR / "traffic-meter.json"
LOCK_PATH = STATE_DIR / "traffic.lock"
TABLE = "vps_server_frps"
SERVICE = "vps-server-frps.service"
LIMIT_FIELDS = frozenset(("cap_bytes", "cap_action", "upload_limit_bps", "download_limit_bps",
                          "expiry_count", "expiry_unit", "expires_at", "reset_mode", "next_reset_at"))
FIELDS = frozenset(("id", "number", "name", "port", "enabled", "upload_bytes", "download_bytes",
                    "total_upload_bytes", "total_download_bytes", "counter_epoch")) | LIMIT_FIELDS


def bind_port(config_path=None):
    """The bindPort frps listens on, or None when FRPS is not configured."""
    try:
        text = Path(config_path or CONFIG_PATH).read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"^bindPort\s*=\s*(\d+)\s*$", text, re.M)
    port = int(match.group(1)) if match else 0
    return port if 1 <= port <= 65535 else None


def validate(inventory):
    if not isinstance(inventory, dict) or set(inventory) != {"version", "nodes"} or \
            inventory["version"] != 1 or not isinstance(inventory["nodes"], list) or \
            len(inventory["nodes"]) != 1:
        raise InvalidInventory("invalid FRPS traffic state")
    entry = inventory["nodes"][0]
    if not isinstance(entry, dict) or set(entry) != FIELDS:
        raise InvalidInventory("invalid FRPS traffic fields")
    uuid.UUID(entry["id"])
    if type(entry["port"]) is not int or not 1 <= entry["port"] <= 65535 or entry["enabled"] is not True:
        raise InvalidInventory("invalid FRPS port")
    validate_metering(entry)


def new_state(port):
    entry = {"id": str(uuid.uuid4()), "number": 1, "name": "FRPS", "port": port, "enabled": True,
             "cap_bytes": None, "cap_action": "throttle", "upload_limit_bps": None,
             "download_limit_bps": None, "expiry_count": None, "expiry_unit": None,
             "expires_at": None, "reset_mode": "none", "next_reset_at": None,
             "upload_bytes": 0, "download_bytes": 0, "total_upload_bytes": 0,
             "total_download_bytes": 0, "counter_epoch": 0}
    state = {"version": 1, "nodes": [entry]}
    validate(state)
    return state


def read_state(*, state_path=STATE_PATH, config_paths=None):
    """The entry with its port following frps.toml; None before init or without FRPS."""
    state = _read_json(state_path)
    port = bind_port(Path(state_path).parent / "frps.toml")
    if state is None or port is None:
        return None
    validate(state)
    state["nodes"][0]["port"] = port
    return state


def write_state(state, *, state_path=STATE_PATH):
    validate(state)
    write_json(state, state_path)


def _locked(lock_path):
    Path(lock_path).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    handle = open(lock_path, "a+b")
    fcntl.flock(handle, fcntl.LOCK_EX)
    return handle


def init(*, state_path=STATE_PATH, lock_path=LOCK_PATH):
    with _locked(lock_path):
        if _read_json(state_path) is not None:
            return False
        port = bind_port(Path(state_path).parent / "frps.toml")
        if port is None:
            raise InvalidInventory("FRPS is not configured")
        write_state(new_state(port), state_path=state_path)
        return True


def apply(request, *, state_path=STATE_PATH, lock_path=LOCK_PATH):
    """Change the cap, speed limits, validity or reset schedule; counters stay."""
    if not isinstance(request, dict) or request.get("action") != "edit" or \
            not set(request) - {"action"} or set(request) - {"action"} - LIMIT_FIELDS:
        raise InvalidInventory("invalid FRPS traffic request")
    with _locked(lock_path):
        state = _read_json(state_path)
        if state is None:
            raise InvalidInventory("FRPS traffic state missing")
        validate(state)
        entry = state["nodes"][0]
        for key in LIMIT_FIELDS & set(request):
            entry[key] = request[key]
        write_state(state, state_path=state_path)
        return state


def tick(**kwargs):
    from node_meter import tick as meter_tick
    return meter_tick(state_path=kwargs.pop("state_path", STATE_PATH), config_paths={},
                      meter_path=kwargs.pop("meter_path", METER_PATH),
                      lock_path=kwargs.pop("lock_path", LOCK_PATH), table=TABLE,
                      reader=read_state, writer=write_state, validate=validate, **kwargs)


def delete_table():
    from nft_runtime import command
    binary, env = command()
    return subprocess.run([binary, "delete", "table", "inet", TABLE], capture_output=True,
                          timeout=20, env=env, check=False).returncode


def run():
    from node_meter import _notify_ready
    try:
        init()
        if tick() is None:
            raise RuntimeError("FRPS traffic state not initialized")
        _notify_ready()
        while True:
            time.sleep(2)
            tick()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"FRPS traffic accounting stopped: {exc}", file=sys.stderr, flush=True)
        # Stale or missing rules would leave FRPS unlimited; stop it instead.
        subprocess.run(["systemctl", "stop", SERVICE], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=20, check=False)
        return 1


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv not in (["run"], ["init"], ["apply"], ["delete-table"]):
        print("usage: frps_meter.py run|init|apply|delete-table", file=sys.stderr)
        return 2
    if os.geteuid() != 0:
        return 1
    try:
        if argv == ["run"]:
            return run()
        if argv == ["init"]:
            init()
        elif argv == ["apply"]:
            raw = sys.stdin.buffer.read(4097)
            if len(raw) > 4096:
                return 2
            apply(json.loads(raw))
        else:
            return 0 if delete_table() in (0, 1) else 1
    except (InvalidInventory, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"FRPS traffic {argv[0]} failed: {type(exc).__name__}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
