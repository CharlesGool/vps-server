"""Offline, lower-bound listener-port traffic accounting and desired policy.

Upload is client -> server; download is server -> client. The caller must supply
one isolated counter per node's unique listener port, family and direction.
Counters are unsigned 64-bit bytes with a monotonically increasing epoch. An
unobserved interval or reset cannot recover lost bytes: suspicion is sticky and
requests a 1 Mbps safety limit until a new cycle begins.
No kernel rules are read or installed here.
"""

import calendar
import copy
from datetime import datetime, timezone

from node_inventory import InvalidInventory, validate_inventory

MAX_BYTES = (1 << 64) - 1
FAMILIES = ("ipv4", "ipv6")
DIRECTIONS = ("upload", "download")
LIMIT_BPS = 1_000_000


def _uint(value):
    if type(value) is not int or not 0 <= value <= MAX_BYTES:
        raise InvalidInventory("counter must be an unsigned 64-bit integer")
    return value


def _sample(value):
    if not isinstance(value, dict) or set(value) != {"epoch", "bytes"}:
        raise InvalidInventory("invalid directional counter sample")
    return {"epoch": _uint(value["epoch"]), "bytes": _uint(value["bytes"])}


def _samples(value):
    if not isinstance(value, dict) or set(value) != set(FAMILIES):
        raise InvalidInventory("both address families required")
    if any(not isinstance(value[family], dict) or
           set(value[family]) != set(DIRECTIONS) for family in FAMILIES):
        raise InvalidInventory("both counter directions required")
    return {family: {direction: _sample(value[family][direction])
                     for direction in DIRECTIONS} for family in FAMILIES}


def _state(inventory, state):
    if not isinstance(state, dict) or set(state) != {"version", "nodes"} or \
            type(state["version"]) is not int or state["version"] != 1 or \
            not isinstance(state["nodes"], dict):
        raise InvalidInventory("invalid accounting state")
    ids = {node["id"] for node in inventory["nodes"]}
    if not set(state["nodes"]) <= ids:
        raise InvalidInventory("unknown accounting node ID")
    for node in inventory["nodes"]:
        for direction in DIRECTIONS:
            _uint(node[f"{direction}_bytes"])
            _uint(node[f"total_{direction}_bytes"])
        _uint(node["counter_epoch"])
        _uint(node["upload_bytes"] + node["download_bytes"])
        entry = state["nodes"].get(node["id"])
        if entry is None:
            if node["upload_bytes"] or node["download_bytes"] or node["counter_epoch"]:
                raise InvalidInventory("missing baseline for previously accounted node")
            continue
        if not isinstance(entry, dict) or set(entry) != {"samples", "suspect"} or \
                type(entry["suspect"]) is not bool:
            raise InvalidInventory("invalid accounting entry")
        if entry["samples"] is not None:
            _samples(entry["samples"])


def _now(now):
    if not isinstance(now, datetime) or now.tzinfo is None or \
            now.utcoffset() != timezone.utc.utcoffset(now):
        raise InvalidInventory("now must be a UTC datetime")


def update_accounting(inventory, state, snapshots):
    """Return new (inventory, state). Missing ID/metrics mark suspect, never zero.

    snapshots maps node ID to both families, each with upload/download
    {"epoch": unsigned integer, "bytes": unsigned integer}. A missing ID or
    None denotes unavailable metrics. Partial family/direction data also marks
    that node suspect; malformed *present* samples are rejected atomically.
    Same-epoch decreases and new epochs add the new raw value as a lower bound,
    preserve accumulated totals, and mark suspect (reset gaps are unknowable).
    """
    validate_inventory(inventory)
    _state(inventory, state)
    if not isinstance(snapshots, dict):
        raise InvalidInventory("counter snapshot mapping required")
    ids = {node["id"] for node in inventory["nodes"]}
    if not set(snapshots) <= ids:
        raise InvalidInventory("unknown counter node ID")
    result, ledger = copy.deepcopy(inventory), copy.deepcopy(state)
    for node in result["nodes"]:
        identifier = node["id"]
        entry = ledger["nodes"].setdefault(identifier, {"samples": None, "suspect": False})
        raw = snapshots.get(identifier)
        if raw is None:
            entry["suspect"] = True
            continue
        if isinstance(raw, dict) and set(raw) <= set(FAMILIES) and all(
                isinstance(values, dict) and set(values) <= set(DIRECTIONS)
                for values in raw.values()) and (set(raw) != set(FAMILIES) or any(
                    set(raw[family]) != set(DIRECTIONS) for family in FAMILIES)):
            for values in raw.values():
                for sample in values.values():
                    _sample(sample)
            entry["suspect"] = True
            continue
        current = _samples(raw)
        old = entry["samples"]
        for family in FAMILIES:
            for direction in DIRECTIONS:
                sample = current[family][direction]
                previous = old[family][direction] if old is not None else None
                if previous is not None and sample["epoch"] < previous["epoch"]:
                    raise InvalidInventory("counter epoch regressed")
                if previous is None:
                    # Only a newly installed epoch-zero counter has a known origin.
                    if sample["epoch"] != 0:
                        entry["suspect"] = True
                    delta = sample["bytes"]
                elif sample["epoch"] != previous["epoch"] or sample["bytes"] < previous["bytes"]:
                    entry["suspect"] = True
                    delta = sample["bytes"]
                    node["counter_epoch"] = _uint(node["counter_epoch"] + 1)
                else:
                    delta = sample["bytes"] - previous["bytes"]
                node[f"{direction}_bytes"] = _uint(node[f"{direction}_bytes"] + delta)
                node[f"total_{direction}_bytes"] = _uint(node[f"total_{direction}_bytes"] + delta)
        _uint(node["upload_bytes"] + node["download_bytes"])
        entry["samples"] = current
    validate_inventory(result)
    return result, ledger


def desired_policy(inventory, state, *, now):
    """Return per-ID decisions; caps and dates both request a 1 Mbps limit."""
    validate_inventory(inventory)
    _state(inventory, state)
    _now(now)
    policy = {}
    for node in inventory["nodes"]:
        entry = state["nodes"].get(node["id"])
        suspect = entry is None or entry["suspect"] or entry["samples"] is None
        expired = (node["expires_at"] is not None and
                   datetime.fromisoformat(node["expires_at"]) <= now)
        used = node["upload_bytes"] + node["download_bytes"]
        capped = node["cap_bytes"] is not None and used >= node["cap_bytes"]
        active = node["enabled"]
        throttled = capped or expired or suspect
        policy[node["id"]] = {"active": active, "expired": expired,
                              "capped": capped,
                              "upload_bps": LIMIT_BPS if active and throttled else None,
                              "download_bps": LIMIT_BPS if active and throttled else None,
                              "suspect": suspect}
    return policy


def _month_after(value):
    """Advance a UTC date one month, clamping the day when necessary."""
    year = value.year + (value.month == 12)
    month = value.month % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def advance_cycles(inventory, state, *, now):
    """Start due cycles after the latest counter sample has been persisted.

    Period totals clear; lifetime totals and the last kernel-counter baseline do
    not. A one-time reset clears its date deadline. Monthly resets move a date
    deadline by the same number of calendar months as the reset boundary.
    """
    validate_inventory(inventory)
    _state(inventory, state)
    _now(now)
    result, ledger = copy.deepcopy(inventory), copy.deepcopy(state)
    for node in result["nodes"]:
        if node["next_reset_at"] is None:
            continue
        due = datetime.fromisoformat(node["next_reset_at"])
        if due > now:
            continue
        mode = node["reset_mode"]
        if mode == "once":
            node["reset_mode"] = "none"
            node["next_reset_at"] = None
            node["expires_at"] = None
        else:
            months = 0
            while due <= now:
                due = _month_after(due)
                months += 1
            node["next_reset_at"] = due.isoformat()
            if node["expires_at"] is not None:
                expiry = datetime.fromisoformat(node["expires_at"])
                for _ in range(months):
                    expiry = _month_after(expiry)
                node["expires_at"] = expiry.isoformat()
        node["upload_bytes"] = node["download_bytes"] = 0
        entry = ledger["nodes"].get(node["id"])
        if entry is not None and entry["samples"] is not None:
            entry["suspect"] = False
    validate_inventory(result)
    return result, ledger
