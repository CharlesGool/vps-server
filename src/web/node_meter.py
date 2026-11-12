#!/usr/bin/env python3
"""Per-listener dual-stack traffic counters and 1 Mbps kernel policing.

Only the dedicated inet table is changed. Named counters cover TCP and UDP in
both directions. A shared named quota counts the observed total against half
the configured cap, accounting for both sides of forwarded traffic. A short poll
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

from node_accounting import BILLABLE_MULTIPLIER, advance_cycles, desired_policy, multiplier, update_accounting
from node_inventory import InvalidInventory
from node_state import CONFIG_PATHS, STATE_PATH, _read_json, read_inventory, write_inventory, write_json


TABLE = "vps_server_nodes"
METER_PATH = STATE_PATH.parent / "meter.json"
LOCK_PATH = Path("/etc/vps-server-node.lock")
# Leave room for the token bucket's startup burst and TCP pacing. On the
# deployment host, 125000 admitted about 1.03 Mbps over a 4 MiB transfer.
LIMIT_BYTES_PER_SECOND = 120000


def _name(identifier, family, direction):
    token = identifier.replace("-", "")
    return f"c_{token}_{family}_{direction}"


def _zero_samples(inventory, epoch):
    return {node["id"]: {family: {direction: {"epoch": epoch, "bytes": 0}
                                   for direction in ("upload", "download")}
                         for family in ("ipv4", "ipv6")}
            for node in inventory["nodes"]}


def parse_counters(document, inventory, epoch, *, new_ids=frozenset(), table=TABLE):
    """Decode all four named byte counters for every node, or fail closed."""
    if not isinstance(document, dict) or not isinstance(document.get("nftables"), list):
        raise InvalidInventory("invalid nftables counter JSON")
    found = {}
    for item in document["nftables"]:
        if not isinstance(item, dict) or "counter" not in item:
            continue
        counter = item["counter"]
        if counter.get("family") != "inet" or counter.get("table") != table:
            continue
        name, amount = counter.get("name"), counter.get("bytes")
        if not isinstance(name, str) or type(amount) is not int or amount < 0 or name in found:
            raise InvalidInventory("invalid or duplicate nftables counter")
        found[name] = amount
    snapshots = _zero_samples(inventory, epoch)
    for node in inventory["nodes"]:
        names = [_name(node["id"], family, direction)
                 for family in ("ipv4", "ipv6") for direction in ("upload", "download")]
        if node["id"] in new_ids and not any(name in found for name in names):
            snapshots.pop(node["id"])
            continue
        for family in ("ipv4", "ipv6"):
            for direction in ("upload", "download"):
                name = _name(node["id"], family, direction)
                if name not in found:
                    raise InvalidInventory("missing node counter")
                snapshots[node["id"]][family][direction]["bytes"] = found[name]
    return snapshots


def _policy_key(inventory, policy):
    inputs = [(LIMIT_BYTES_PER_SECOND, multiplier(node), node["id"], node.get("port"),
               node.get("matches"), node["cap_bytes"],
               node["cap_action"], policy[node["id"]]["active"],
               policy[node["id"]]["blocked"], policy[node["id"]]["expired"],
               policy[node["id"]]["capped"],
               policy[node["id"]]["suspect"], policy[node["id"]]["upload_bps"],
               policy[node["id"]]["download_bps"])
              for node in inventory["nodes"]]
    return hashlib.sha256(json.dumps(inputs, separators=(",", ":")).encode()).hexdigest()


def port_matches(port):
    """Traffic to and from a local listener: the node and FRPS default.

    Each match is (family, direction, chain, nft expression, weight). A weight
    of two counts that traffic twice, for packets that cross the host's network
    on both sides (see traffic_meter.py).
    """
    return [(family, direction, chain, f"meta nfproto {family} {protocol} {field} {port}", 1)
            for family in ("ipv4", "ipv6")
            for direction, chain, field in (("upload", "input", "dport"), ("download", "output", "sport"))
            for protocol in ("tcp", "udp")]


def render_rules(inventory, policy, *, replace=False, table=TABLE):
    """Build an atomic nft batch; all identifiers and ports are validated data."""
    lines = []
    if replace:
        lines.append(f"delete table inet {table}")
    lines += [f"add table inet {table}",
              f"add chain inet {table} input {{ type filter hook input priority -50; policy accept; }}",
              f"add chain inet {table} output {{ type filter hook output priority -50; policy accept; }}"]
    if any(match[2] == "forward" for node in inventory["nodes"] for match in node.get("matches") or ()):
        lines.append(f"add chain inet {table} forward {{ type filter hook forward priority -50; policy accept; }}")
    for node in inventory["nodes"]:
        identifier = node["id"]
        stem = identifier.replace("-", "")
        decision = policy[identifier]
        for family in ("ipv4", "ipv6"):
            for direction in ("upload", "download"):
                lines.append(f"add counter inet {table} {_name(identifier, family, direction)}")
        if not decision["active"]:
            continue
        for direction in ("upload", "download"):
            rate = decision[f"{direction}_bps"]
            if rate is not None:
                lines.append(f"add limit inet {table} l_{stem}_{direction} "
                             f"{{ rate over {(rate + 7) // 8} bytes/second "
                             "burst 16384 bytes; }")
        # A named quota is shared across upload/download and both IP families.
        # Keep enforcing the recorded lower bound even when an unobserved
        # interval makes the total uncertain. Only a reached cap or expiry
        # replaces the quota with an unconditional policy.
        quota = node["cap_bytes"] is not None and not (
            decision["capped"] or decision["expired"])
        if quota:
            used = node["upload_bytes"] + node["download_bytes"]
            quota_bytes = max(1, node["cap_bytes"] // multiplier(node))
            lines.append(f"add quota inet {table} q_{stem} "
                         f"{{ over {quota_bytes} bytes used {used} bytes; }}")
            if node["cap_action"] == "throttle":
                for direction in ("upload", "download"):
                    lines.append(f"add limit inet {table} lcap_{stem}_{direction} "
                                 f"{{ rate over {LIMIT_BYTES_PER_SECOND} bytes/second "
                                 "burst 16384 bytes; }")
        matches = node["matches"] if "matches" in node else port_matches(node["port"])
        for family, direction, chain, match, weight in matches:
            if decision["blocked"]:
                lines.append(f"add rule inet {table} {chain} {match} drop")
            elif decision[f"{direction}_bps"] is not None:
                lines.append(f"add rule inet {table} {chain} {match} "
                             f"limit name \"l_{stem}_{direction}\" drop")
            # Repeating the quota and counter rules counts the bytes again.
            for _ in range(weight):
                if quota:
                    tail = ("drop" if node["cap_action"] == "block" else
                            f'limit name "lcap_{stem}_{direction}" drop')
                    lines.append(f"add rule inet {table} {chain} {match} "
                                 f"quota name \"q_{stem}\" {tail}")
                lines.append(f"add rule inet {table} {chain} {match} "
                             f"counter name {_name(identifier, family, direction)}")
    return "\n".join(lines) + "\n"


class NftBackend:
    def __init__(self, table=TABLE):
        self.table = table

    def _run(self, args, *, input=None):
        from nft_runtime import command
        binary, env = command()
        return subprocess.run([binary, *args], input=input, text=True,
                              capture_output=True, timeout=20, env=env)

    @staticmethod
    def _failure(message, result):
        # nft's own last error line is the only clue to why the host refuses.
        lines = [line.strip() for line in (result.stderr or "").splitlines() if line.strip()]
        return RuntimeError(f"{message}: {lines[-1][:200]}" if lines else message)

    def exists(self):
        result = self._run(["-j", "list", "tables"])
        if result.returncode:
            raise self._failure("cannot list nftables tables", result)
        document = json.loads(result.stdout)
        return any(item.get("table", {}).get("family") == "inet" and
                   item.get("table", {}).get("name") == self.table
                   for item in document.get("nftables", []))

    def counters(self):
        result = self._run(["-j", "list", "counters", "table", "inet", self.table])
        if result.returncode:
            raise self._failure("cannot read node counters", result)
        return json.loads(result.stdout)

    def apply(self, batch):
        result = self._run(["-f", "-"], input=batch)
        if result.returncode:
            raise self._failure("cannot install node counter and rate rules", result)


def _ledger(inventory, epoch, *, suspect):
    baseline = _zero_samples(inventory, epoch)
    return {"version": 1, "nodes": {identifier: {"samples": sample, "suspect": suspect}
                                    for identifier, sample in baseline.items()}}


def tick(*, now=None, state_path=STATE_PATH, config_paths=CONFIG_PATHS,
         meter_path=METER_PATH, lock_path=LOCK_PATH, backend=None, lock_held=False,
         table=TABLE, reader=None, writer=None, validate=None):
    """Sample, advance due cycles, reconcile rules, then persist both ledgers.

    The FRPS meter reuses this with its own table, state reader/writer and
    validator; the defaults are the sing-box node inventory.
    """
    now = now or datetime.now(timezone.utc)
    backend = backend or NftBackend(table)
    reader = reader or read_inventory
    writer = writer or write_inventory
    checks = {} if validate is None else {"validate": validate}
    with (nullcontext() if lock_held else open(lock_path, "a+b")) as lock:
        if lock is not None:
            fcntl.flock(lock, fcntl.LOCK_EX)
        inventory = reader(state_path=state_path, config_paths=config_paths)
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
            current_ids = {node["id"] for node in inventory["nodes"]}
            new_ids = current_ids - set(ledger["nodes"])
            ledger["nodes"] = {identifier: entry for identifier, entry in ledger["nodes"].items()
                               if identifier in current_ids}
            if exists:
                snapshots = parse_counters(backend.counters(), inventory, epoch, new_ids=new_ids, table=table)
                inventory, ledger = update_accounting(inventory, ledger, snapshots, **checks)
                # node_control stops the service before a new listener is
                # installed, so its first meter baseline has a known zero.
                zero = _zero_samples(inventory, epoch)
                for identifier in new_ids:
                    ledger["nodes"][identifier] = {"samples": zero[identifier], "suspect": False}
            else:
                # After reboot or an external table deletion, an unobserved
                # interval may have lost bytes. Keep recorded lower bounds
                # and the quota rule, while exposing the accounting gap.
                for entry in ledger["nodes"].values():
                    entry["suspect"] = True
                old_fingerprint = None
        # A new accounting cycle changes the quota's `used` value even when
        # the resulting policy is identical. Rebuild the nft table once so
        # the kernel and the persisted period start at the same zero.
        previous_resets = {node["id"]: node["next_reset_at"] for node in inventory["nodes"]}
        inventory, ledger = advance_cycles(inventory, ledger, now=now, **checks)
        cycle_changed = any(node["next_reset_at"] != previous_resets[node["id"]]
                            for node in inventory["nodes"])
        policy = desired_policy(inventory, ledger, now=now, **checks)
        fingerprint = _policy_key(inventory, policy)
        if not exists or cycle_changed or fingerprint != old_fingerprint:
            backend.apply(render_rules(inventory, policy, replace=exists, table=table))
            if metadata is not None:
                epoch += 1
            baseline = _zero_samples(inventory, epoch)
            for identifier, sample in baseline.items():
                ledger["nodes"].setdefault(identifier, {"samples": None, "suspect": False})["samples"] = sample
        writer(inventory, state_path=state_path)
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
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Node traffic accounting stopped: {exc}", file=sys.stderr, flush=True)
        # Existing rules may have disappeared or become stale. Stop the node
        # units instead of leaving unrestricted traffic running indefinitely.
        for service in ("vps-server-proxy.service",):
            subprocess.run(["systemctl", "stop", service],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=20, check=False)
        return 1


if __name__ == "__main__":
    sys.exit(main())
