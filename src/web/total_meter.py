"""Whole-host traffic total shown at the top of the home page.

It adds up what every metered feature already counts (sing-box nodes, FRPS and the
kernel/app meters in traffic_meter.py and app_meter.py), with the same billing
multiplier each of them uses. A period runs from the chosen day of each month (UTC, like the
other meters), or, with ``reset_spec``, from each weekly, monthly or yearly point in the host's
local time (the same calendar rules as scheduled tasks). Usage in a period is the growth of each entry's lifetime counter since the
period began, plus what the entry's own current-cycle counters already show when the period is
first recorded, so the total agrees with the per-feature pages instead of starting from zero
at the moment the console first looked.

The count can drift from what the provider bills, so the operator may calibrate it: typing
the usage the provider shows stores the difference as a separate, signed calibration that is
shown on its own bar and cleared when the next period begins.

This is a display and a limit marker only: reaching the limit shows a warning and
does not throttle or stop anything.
"""

import calendar
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import tempfile

MAX_CAP_BYTES = 10 ** 18
WARN_RATIO = 0.8
BILLABLE_MULTIPLIER = 2  # nodes and FRPS forward each byte, so it counts twice (node_accounting.multiplier)


def lifetime_billable(entry):
    """Billable lifetime bytes of one metered entry (upload plus download, times its multiplier)."""
    total = 0
    for key in ("total_upload_bytes", "total_download_bytes"):
        value = entry.get(key, 0)
        if type(value) is not int or value < 0:
            raise ValueError("invalid traffic counter")
        total += value
    return total * entry.get("billable_multiplier", BILLABLE_MULTIPLIER)


def cycle_billable(entry):
    """Billable bytes of the entry's current billing cycle (what its own page shows), or None if it has none."""
    total = 0
    for key in ("upload_bytes", "download_bytes"):
        value = entry.get(key)
        if type(value) is not int or value < 0:
            return None
        total += value
    return total * entry.get("billable_multiplier", BILLABLE_MULTIPLIER)


def snapshot_full(entries):
    """{id: {"lifetime", "cycle", "multiplier", "name"}} for a list of metered entries."""
    info = {}
    for entry in entries:
        identifier = entry.get("id")
        if not isinstance(identifier, str) or identifier in info:
            continue
        info[identifier] = {"lifetime": lifetime_billable(entry), "cycle": cycle_billable(entry),
                            "multiplier": entry.get("billable_multiplier", BILLABLE_MULTIPLIER),
                            "name": str(entry.get("name") or identifier)[:64]}
    return info


def snapshot(entries):
    """({id: lifetime billable bytes}, {id: display name}) for a list of metered entries."""
    info = snapshot_full(entries)
    return ({i: v["lifetime"] for i, v in info.items()}, {i: v["name"] for i, v in info.items()})


def lifetimes(info):
    return {i: v["lifetime"] for i, v in info.items()}


def backfilled_baselines(info):
    """Baselines that make a period count what each entry's current cycle already holds."""
    return {i: max(0, v["lifetime"] - v["cycle"]) if v["cycle"] is not None else v["lifetime"]
            for i, v in info.items()}


def _schedule(spec):
    try:
        import node_inventory
    except ImportError:  # imported as part of a package (tests)
        from . import node_inventory  # type: ignore[no-redef]
    return node_inventory


def valid_spec(spec):
    """A calendar reset spec as saved: weekly, monthly or yearly in schedule_time's form."""
    try:
        return _schedule(spec).reset_schedule(_schedule(spec).schedule_reset_mode(spec)) == spec
    except (ValueError, KeyError, TypeError):
        return False


def period_boundary(now, reset_day, spec=None):
    """The latest boundary at or before now (00:00 UTC on reset_day, or the calendar spec), or None when there is no reset."""
    if spec:
        return _schedule(spec).previous_scheduled_reset(now, spec)
    if not reset_day:
        return None
    candidate = now.replace(day=reset_day, hour=0, minute=0, second=0, microsecond=0)
    if candidate > now:
        year = candidate.year - (candidate.month == 1)
        candidate = candidate.replace(year=year, month=(candidate.month - 2) % 12 + 1)
    return candidate


def next_reset(now, reset_day, spec=None):
    """The next boundary strictly after now: 00:00 UTC on reset_day (1-28), the calendar spec, or None for never."""
    if spec:
        return _schedule(spec).next_scheduled_reset(now, spec)
    if not reset_day:
        return None
    if type(reset_day) is not int or not 1 <= reset_day <= 28:
        raise ValueError("invalid reset day")
    candidate = now.replace(day=reset_day, hour=0, minute=0, second=0, microsecond=0)
    if candidate <= now:
        year = candidate.year + (candidate.month == 12)
        candidate = candidate.replace(year=year, month=candidate.month % 12 + 1)
    return candidate


DEFAULT_RESET_DAY = 1


def new_state(info, now, cap_bytes=None, reset_day=DEFAULT_RESET_DAY, spec=None):
    """A period that starts at the latest boundary and already counts each entry's current cycle."""
    nxt = next_reset(now, reset_day, spec)
    start = period_boundary(now, reset_day, spec) or now
    state = {"version": 3, "cap_bytes": cap_bytes, "reset_day": 0 if spec else reset_day,
             "period_start": start.isoformat(), "next_reset_at": nxt.isoformat() if nxt else None,
             "baselines": backfilled_baselines(info), "calibration_bytes": 0, "calibrated_at": None}
    if spec:
        state["reset_spec"] = spec
    return state


def validate(state):
    base = {"version", "cap_bytes", "reset_day", "period_start", "next_reset_at", "baselines"}
    if not isinstance(state, dict) or state.get("version") not in (1, 2, 3) or \
            set(state) - {"reset_spec"} != (base | {"calibration_bytes", "calibrated_at"} if state.get("version") == 3 else base):
        raise ValueError("invalid total traffic state")
    if "reset_spec" in state and (state["reset_day"] != 0 or not valid_spec(state["reset_spec"])):
        raise ValueError("invalid reset schedule")
    if state["version"] == 3:
        offset = state["calibration_bytes"]
        if type(offset) is not int or abs(offset) > MAX_CAP_BYTES:
            raise ValueError("invalid calibration")
        if state["calibrated_at"] is not None:
            datetime.fromisoformat(state["calibrated_at"])
    cap = state["cap_bytes"]
    if cap is not None and (type(cap) is not int or not 1 <= cap <= MAX_CAP_BYTES):
        raise ValueError("invalid cap")
    day = state["reset_day"]
    if type(day) is not int or not (day == 0 or 1 <= day <= 28):
        raise ValueError("invalid reset day")
    datetime.fromisoformat(state["period_start"])
    if state["next_reset_at"] is not None:
        datetime.fromisoformat(state["next_reset_at"])
    baselines = state["baselines"]
    if not isinstance(baselines, dict) or any(not isinstance(k, str) or type(v) is not int or v < 0
                                              for k, v in baselines.items()):
        raise ValueError("invalid baselines")
    return state


def advance(state, info, now):
    """Start a new period when one is due; returns (state, changed).

    A first record, and a version-1 state (whose period began whenever the console happened to
    look), are rebuilt from the entries' current cycles, keeping the cap and reset day.
    """
    if state is None:
        return new_state(info, now), True
    if state["version"] == 1:
        return new_state(info, now, state["cap_bytes"], state["reset_day"], state.get("reset_spec")), True
    if state["version"] == 2:
        # A period that was already rebuilt from the cycles; it only lacks the calibration fields.
        return {**state, "version": 3, "calibration_bytes": 0, "calibrated_at": None}, True
    if state["next_reset_at"] is not None and now >= datetime.fromisoformat(state["next_reset_at"]):
        nxt = next_reset(now, state["reset_day"], state.get("reset_spec"))
        return {**state, "period_start": now.isoformat(), "next_reset_at": nxt.isoformat() if nxt else None,
                "baselines": lifetimes(info), "calibration_bytes": 0, "calibrated_at": None}, True
    return state, False


def period_usage(state, snap):
    """Billable bytes used since the period began, in total and per entry id."""
    per_entry = {identifier: max(0, value - state["baselines"].get(identifier, 0))
                 for identifier, value in snap.items()}
    return sum(per_entry.values()), per_entry


def calibration(state):
    return state.get("calibration_bytes", 0)


def calibrated_total(state, measured):
    """What the period has used once the operator's calibration is applied (never below zero)."""
    return max(0, measured + calibration(state))


def apply_calibration(state, actual_bytes, measured, now):
    """Store the difference between the usage the provider shows and what was counted.

    ``actual_bytes`` None clears the calibration. ``measured`` is the count without calibration.
    """
    if actual_bytes is None:
        return {**state, "calibration_bytes": 0, "calibrated_at": None}
    if type(actual_bytes) is not int or not 0 <= actual_bytes <= MAX_CAP_BYTES:
        raise ValueError("invalid actual usage")
    return {**state, "calibration_bytes": actual_bytes - measured, "calibrated_at": now.isoformat()}


def parse_actual(actual_gib):
    """Bytes from the form text; None for blank (clear the calibration); ValueError on anything odd."""
    text = (actual_gib or "").strip()
    if not text:
        return None
    value = float(text)
    if not math.isfinite(value) or value < 0:
        raise ValueError("usage must not be negative")
    actual = int(value * 1073741824)
    if actual > MAX_CAP_BYTES:
        raise ValueError("usage out of range")
    return actual


def level(state, used):
    cap = state["cap_bytes"]
    if cap is None:
        return "none"
    return "over" if used >= cap else "warn" if used >= cap * WARN_RATIO else "ok"


def parse_settings(cap_gib, reset_day):
    """(cap_bytes or None, reset_day) from the form text; ValueError on anything odd. See parse_spec for calendar resets."""
    cap_text = (cap_gib or "").strip()
    cap = None
    if cap_text:
        value = float(cap_text)
        if not math.isfinite(value) or value <= 0:
            raise ValueError("cap must be positive")
        cap = int(value * 1073741824)
        if not 1 <= cap <= MAX_CAP_BYTES:
            raise ValueError("cap out of range")
    day_text = (reset_day or "0").strip() or "0"
    if not day_text.isdigit() or not (int(day_text) == 0 or 1 <= int(day_text) <= 28):
        raise ValueError("invalid reset day")
    return cap, int(day_text)


def parse_spec(spec):
    """A calendar reset from the browser: None (use the reset day), or a weekly, monthly or yearly spec."""
    if spec is None:
        return None
    try:
        import scheduler
    except ImportError:  # imported as part of a package (tests)
        from . import scheduler  # type: ignore[no-redef]
    try:
        spec = scheduler.normalize_spec(spec)
    except scheduler.ScheduleError as exc:
        raise ValueError("invalid reset schedule") from exc
    if spec["mode"] not in ("weekly", "monthly", "yearly"):
        raise ValueError("reset schedule must be weekly, monthly or yearly")
    return spec


def apply_settings(state, cap_bytes, reset_day, now, info=None, spec=None):
    """New cap and reset (a day of the month in UTC, or a calendar spec, which wins).

    A changed reset re-bases the period on the new boundary.
    """
    if spec:
        reset_day = 0
    changed = state["reset_day"] != reset_day or state.get("reset_spec") != spec
    if changed and info is not None:
        return new_state(info, now, cap_bytes, reset_day, spec)
    nxt = next_reset(now, reset_day, spec) if changed else (
        datetime.fromisoformat(state["next_reset_at"]) if state["next_reset_at"] else None)
    updated = {key: value for key, value in state.items() if key != "reset_spec"}
    updated.update(cap_bytes=cap_bytes, reset_day=reset_day, next_reset_at=nxt.isoformat() if nxt else None)
    if spec:
        updated["reset_spec"] = spec
    return updated


def format_bytes(value):
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.2f} {unit}"
        size /= 1024


def read_state(path):
    try:
        return validate(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return None


def write_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".total-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(validate(state), stream, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
