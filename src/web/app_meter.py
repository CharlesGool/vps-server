"""Traffic accounting and limits inside the console: Mini Drive and the speed test.

Both share the console's port with its pages, so the kernel cannot tell their
bytes apart; the console counts what it sends and receives for them instead.
The fields and rules are the same as a sing-box node's (node_accounting.py):
upload is data coming in, download data going out, a traffic cap throttles to
1 Mbps or blocks, speed limits per direction, a validity period and a reset
schedule. Each byte counts once: these transfers cross the network once.

The console is the only writer of the state file. Counts are kept in memory
and added to the file every few seconds, so a crash loses at most that much.
"""

import fcntl
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from node_accounting import advance_cycles, desired_policy
from node_inventory import InvalidInventory, validate_metering

KEYS = {"files": "Mini Drive", "speedtest": "Speed test"}
LIMIT_FIELDS = frozenset(("cap_bytes", "cap_action", "upload_limit_bps", "download_limit_bps",
                          "expiry_count", "expiry_unit", "expires_at", "reset_mode", "next_reset_at"))
FIELDS = frozenset(("id", "key", "name", "enabled", "billable_multiplier", "upload_bytes", "download_bytes",
                    "total_upload_bytes", "total_download_bytes", "counter_epoch")) | LIMIT_FIELDS
FLUSH_SECONDS = 2


class TrafficBlocked(Exception):
    """The feature reached its cap (with "block") or its validity ended."""


def validate(inventory):
    if not isinstance(inventory, dict) or set(inventory) != {"version", "nodes"} or \
            inventory["version"] != 1 or not isinstance(inventory["nodes"], list):
        raise InvalidInventory("invalid console traffic state")
    seen = set()
    for entry in inventory["nodes"]:
        if not isinstance(entry, dict) or set(entry) != FIELDS or entry["key"] not in KEYS or \
                entry["key"] in seen or entry["enabled"] is not True or entry["billable_multiplier"] != 1:
            raise InvalidInventory("invalid console traffic entry")
        seen.add(entry["key"])
        uuid.UUID(entry["id"])
        validate_metering(entry)


def _new(key):
    return {"id": str(uuid.uuid4()), "key": key, "name": KEYS[key], "enabled": True, "billable_multiplier": 1,
            "cap_bytes": None, "cap_action": "throttle", "upload_limit_bps": None,
            "download_limit_bps": None, "expiry_count": None, "expiry_unit": None,
            "expires_at": None, "reset_mode": "none", "next_reset_at": None,
            "upload_bytes": 0, "download_bytes": 0, "total_upload_bytes": 0,
            "total_download_bytes": 0, "counter_epoch": 0}


class AppMeter:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._pending = {key: {"upload": 0, "download": 0} for key in KEYS}
        self._policy = {}
        self._buckets = {}
        self._thread = None

    # -- state --------------------------------------------------------------

    def _load(self):
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
            validate(state)
        except FileNotFoundError:
            state = {"version": 1, "nodes": []}
        present = {entry["key"] for entry in state["nodes"]}
        state["nodes"] += [_new(key) for key in KEYS if key not in present]
        state["nodes"].sort(key=lambda entry: entry["key"])
        return state

    def _save(self, state):
        validate(state)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(state, indent=1), encoding="utf-8")
        os.chmod(temp, 0o600)
        os.replace(temp, self.path)

    @staticmethod
    def _ledger(state):
        return {"version": 1, "nodes": {entry["id"]: {"samples": None, "suspect": False}
                                        for entry in state["nodes"]}}

    def flush(self, now=None):
        """Add the counted bytes, start due cycles, refresh the policy."""
        now = now or datetime.now(timezone.utc)
        with self._lock:
            pending, self._pending = self._pending, {key: {"upload": 0, "download": 0} for key in KEYS}
        try:
            with open(self.path.with_suffix(".lock"), "a+b") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                state = self._load()
                for entry in state["nodes"]:
                    for direction, amount in pending[entry["key"]].items():
                        entry[f"{direction}_bytes"] += amount
                        entry[f"total_{direction}_bytes"] += amount
                state, ledger = advance_cycles(state, self._ledger(state), now=now, validate=validate)
                policy = desired_policy(state, ledger, now=now, validate=validate)
                self._save(state)
        except (OSError, ValueError, InvalidInventory):
            with self._lock:  # Keep the counts for the next try.
                for key, values in pending.items():
                    for direction, amount in values.items():
                        self._pending[key][direction] += amount
            raise
        by_key = {entry["key"]: policy[entry["id"]] for entry in state["nodes"]}
        with self._lock:
            self._policy = by_key
        return state

    def state(self):
        """The entries as stored plus what is counted but not yet written."""
        with self._lock:
            pending = {key: dict(values) for key, values in self._pending.items()}
        state = self._load()
        for entry in state["nodes"]:
            for direction, amount in pending[entry["key"]].items():
                entry[f"{direction}_bytes"] += amount
                entry[f"total_{direction}_bytes"] += amount
        return state

    def entry(self, key):
        return next(entry for entry in self.state()["nodes"] if entry["key"] == key)

    def edit(self, entry_id, request):
        """Change one entry's limits; counters stay."""
        if not isinstance(request, dict) or not request or set(request) - LIMIT_FIELDS:
            raise InvalidInventory("invalid console traffic request")
        with open(self.path.with_suffix(".lock"), "a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = self._load()
            entry = next((item for item in state["nodes"] if item["id"] == entry_id), None)
            if entry is None:
                raise InvalidInventory("unknown console traffic entry")
            entry.update({key: request[key] for key in LIMIT_FIELDS & set(request)})
            self._save(state)
        self.flush()

    def owns(self, entry_id):
        return any(entry["id"] == entry_id for entry in self._load()["nodes"])

    # -- while transferring ----------------------------------------------------

    def start(self):
        """Flush in the background; idempotent."""
        if self._thread is not None:
            return
        def loop():
            while True:
                try:
                    self.flush()
                except Exception as exc:  # The next round retries; the pages still work.
                    print(f"Console traffic accounting failed: {type(exc).__name__}", flush=True)
                time.sleep(FLUSH_SECONDS)
        self._thread = threading.Thread(target=loop, name="app-meter", daemon=True)
        self._thread.start()

    def check(self, key):
        """Raise TrafficBlocked before a transfer starts when the feature is cut off."""
        if self._policy.get(key, {}).get("blocked"):
            raise TrafficBlocked(key)

    def take(self, key, direction, size):
        """Count ``size`` bytes, waiting first when a speed limit applies."""
        policy = self._policy.get(key, {})
        if policy.get("blocked"):
            raise TrafficBlocked(key)
        bps = policy.get(f"{direction}_bps")
        if bps:
            rate = bps / 8
            with self._lock:
                now = time.monotonic()
                start = max(self._buckets.get((key, direction), 0.0), now - 0.5)
                self._buckets[(key, direction)] = start + size / rate
                wait = start + size / rate - now
            if wait > 0:
                time.sleep(wait)
        with self._lock:
            self._pending[key][direction] += size

    def piece(self, key, direction, default):
        """A chunk size that keeps a limited speed even rather than bursty."""
        bps = self._policy.get(key, {}).get(f"{direction}_bps")
        return min(default, max(4096, int(bps / 8 / 8))) if bps else default
