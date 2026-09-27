#!/usr/bin/env python3
"""Per-listener dual-stack traffic counters and 1 Mbps kernel policing.

Only the dedicated inet table is changed. Named counters cover TCP and UDP in
both directions. A shared named quota starts policing both directions as soon
as their combined transferred bytes exceed the configured cap. A short poll
persists totals and turns date expiry into the same policy.
"""

import fcntl
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

from node_accounting import advance_cycles, desired_policy, update_accounting
from node_inventory import InvalidInventory
from node_state import CONFIG_PATHS, STATE_PATH, _read_json, read_inventory, write_inventory, write_json


TABLE = "vps_server_nodes"
METER_PATH = STATE_PATH.parent / "meter.json"
LOCK_PATH = Path("/etc/vps-server-node.lock")
LIMIT_BYTES_PER_SECOND = 125000  # 1 megabit/s = 125000 bytes/s.


def _name(identifier, family, direction):
    token = identifier.replace("-", "")
    return f"c_{token}_{family}_{direction}"


def _zero_samples(inventory, epoch):
    return {node["id"]: {family: {direction: {"epoch": epoch, "bytes": 0}
                                   for direction in ("upload", "download")}
                         for family in ("ipv4", "ipv6")}
            for node in inventory["nodes"]}


def parse_counters(document, inventory, epoch):
    """Decode all four named byte counters for every node, or fail closed."""
    if not isinstance(document, dict) or not isinstance(document.get("nftables"), list):
        raise InvalidInventory("invalid nftables counter JSON")
    found = {}
    for item in document["nftables"]:
        if not isinstance(item, dict) or "counter" not in item:
            continue
        counter = item["counter"]
        if counter.get("family") != "inet" or counter.get("table") != TABLE:
            continue
        name, amount = counter.get("name"), counter.get("bytes")
        if not isinstance(name, str) or type(amount) is not int or amount < 0 or name in found:
            raise InvalidInventory("invalid or duplicate nftables counter")
        found[name] = amount
    snapshots = _zero_samples(inventory, epoch)
    for node in inventory["nodes"]:
        for family in ("ipv4", "ipv6"):
            for direction in ("upload", "download"):
                name = _name(node["id"], family, direction)
                if name not in found:
                    raise InvalidInventory("missing node counter")
                snapshots[node["id"]][family][direction]["bytes"] = found[name]
    return snapshots


def _policy_key(inventory, policy):
    inputs = [(node["id"], node["port"], node["cap_bytes"],
               policy[node["id"]]["active"], policy[node["id"]]["expired"],
               policy[node["id"]]["capped"], policy[node["id"]]["suspect"])
              for node in inventory["nodes"]]
    return hashlib.sha256(json.dumps(inputs, separators=(",", ":")).encode()).hexdigest()


def render_rules(inventory, policy, *, replace=False):
    """Build an atomic nft batch; all identifiers and ports are validated data."""
    lines = []
    if replace:
        lines.append(f"delete table inet {TABLE}")
    lines += [f"add table inet {TABLE}",
              f"add chain inet {TABLE} input {{ type filter hook input priority -50; policy accept; }}",
              f"add chain inet {TABLE} output {{ type filter hook output priority -50; policy accept; }}"]
    for node in inventory["nodes"]:
        identifier, port = node["id"], node["port"]
        stem = identifier.replace("-", "")
        decision = policy[identifier]
        for family in ("ipv4", "ipv6"):
            for direction in ("upload", "download"):
                lines.append(f"add counter inet {TABLE} {_name(identifier, family, direction)}")
        if not decision["active"]:
            continue
        for direction in ("upload", "download"):
            lines.append(f"add limit inet {TABLE} l_{stem}_{direction} "
                         f"{{ rate over {LIMIT_BYTES_PER_SECOND} bytes/second "
                         "burst 16384 bytes; }")
        # A named quota is shared across upload/download and both IP families.
        # It is needed only while below the cap; once crossed, unconditional
        # directional limits take over on the next reconciliation.
        quota = node["cap_bytes"] is not None and not (
            decision["capped"] or decision["expired"] or decision["suspect"])
        if quota:
            used = node["upload_bytes"] + node["download_bytes"]
            lines.append(f"add quota inet {TABLE} q_{stem} "
                         f"{{ over {node['cap_bytes']} bytes used {used} bytes; }}")
        for family, nft_family in (("ipv4", "ipv4"), ("ipv6", "ipv6")):
            for direction, chain, port_field in (("upload", "input", "dport"),
                                                 ("download", "output", "sport")):
                for protocol in ("tcp", "udp"):
                    match = (f"meta nfproto {nft_family} {protocol} "
                             f"{port_field} {port}")
                    if decision["expired"] or decision["capped"] or decision["suspect"]:
                        lines.append(f"add rule inet {TABLE} {chain} {match} "
                                     f"limit name \"l_{stem}_{direction}\" drop")
                    elif quota:
                        lines.append(f"add rule inet {TABLE} {chain} {match} "
                                     f"quota name \"q_{stem}\" "
                                     f"limit name \"l_{stem}_{direction}\" drop")
                    lines.append(f"add rule inet {TABLE} {chain} {match} "
                                 f"counter name {_name(identifier, family, direction)}")
    return "\n".join(lines) + "\n"


class NftBackend:
    def _run(self, args, *, input=None):
        return subprocess.run(["nft", *args], input=input, text=True,
                              capture_output=True, timeout=20)

    def exists(self):
        result = self._run(["-j", "list", "tables"])
        if result.returncode:
            raise RuntimeError("cannot list nftables tables")
        document = json.loads(result.stdout)
        return any(item.get("table", {}).get("family") == "inet" and
                   item.get("table", {}).get("name") == TABLE
                   for item in document.get("nftables", []))

    def counters(self):
        result = self._run(["-j", "list", "counters", "table", "inet", TABLE])
        if result.returncode:
            raise RuntimeError("cannot read node counters")
        return json.loads(result.stdout)

    def apply(self, batch):
        result = self._run(["-f", "-"], input=batch)
        if result.returncode:
            raise RuntimeError("cannot install node counter and rate rules")


def _ledger(inventory, epoch, *, suspect):
    baseline = _zero_samples(inventory, epoch)
    return {"version": 1, "nodes": {identifier: {"samples": sample, "suspect": suspect}
                                    for identifier, sample in baseline.items()}}


def tick(*, now=None, state_path=STATE_PATH, config_paths=CONFIG_PATHS,
         meter_path=METER_PATH, lock_path=LOCK_PATH, backend=None, lock_held=False):
    """Sample, advance due cycles, reconcile rules, then persist both ledgers."""
    now = now or datetime.now(timezone.utc)
    backend = backend or NftBackend()
    with (nullcontext() if lock_held else open(lock_path, "a+b")) as lock:
        if lock is not None:
            fcntl.flock(lock, fcntl.LOCK_EX)
        inventory = read_inventory(state_path=state_path, config_paths=config_paths)
        if inventory is None:
            return None
        metadata = _read_json(meter_path)
        exists = backend.exists()
        if metadata is None:
            epoch = 0
            if exists:
                # An unowned table with our name is never adopted blindly.
                raise RuntimeError("node table exists without accounting state")
            ledger = _ledger(inventory, epoch, suspect=False)
            old_fingerprint = None
        else:
            if set(metadata) != {"version", "epoch", "fingerprint", "ledger"} or \
                    metadata["version"] != 1 or type(metadata["epoch"]) is not int or \
                    metadata["epoch"] < 0 or not isinstance(metadata["fingerprint"], str):
                raise InvalidInventory("invalid meter state")
            epoch = metadata["epoch"]
            ledger = metadata["ledger"]
            old_fingerprint = metadata["fingerprint"]
            if exists:
                snapshots = parse_counters(backend.counters(), inventory, epoch)
                inventory, ledger = update_accounting(inventory, ledger, snapshots)
            else:
                # After reboot or an external table deletion, an unobserved
                # interval may have lost bytes. Keep lifetime lower bounds and
                # police at 1 Mbps until the next configured reset.
                for entry in ledger["nodes"].values():
                    entry["suspect"] = True
                old_fingerprint = None
        inventory, ledger = advance_cycles(inventory, ledger, now=now)
        policy = desired_policy(inventory, ledger, now=now)
        fingerprint = _policy_key(inventory, policy)
        if not exists or fingerprint != old_fingerprint:
            backend.apply(render_rules(inventory, policy, replace=exists))
            if metadata is not None:
                epoch += 1
            baseline = _zero_samples(inventory, epoch)
            for identifier, sample in baseline.items():
                ledger["nodes"].setdefault(identifier, {"samples": None, "suspect": False})["samples"] = sample
        write_inventory(inventory, state_path=state_path)
        write_json({"version": 1, "epoch": epoch, "fingerprint": fingerprint,
                    "ledger": ledger}, meter_path)
        return policy


def _notify_ready():
    address = os.environ.get("NOTIFY_SOCKET")
    if not address:
        return
    if address.startswith("@"):
        address = "\0" + address[1:]
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
        sock.connect(address)
        sock.sendall(b"READY=1")


def main():
    if os.geteuid() != 0:
        return 1
    try:
        if tick() is None:
            raise RuntimeError("node inventory not initialized")
        _notify_ready()
        while True:
            time.sleep(2)
            tick()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        # Existing rules may have disappeared or become stale. Stop the node
        # units instead of leaving unrestricted traffic running indefinitely.
        for service in ("vps-server-anytls.service", "vps-server-proxy.service"):
            subprocess.run(["systemctl", "stop", service],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=20, check=False)
        return 1


if __name__ == "__main__":
    sys.exit(main())
