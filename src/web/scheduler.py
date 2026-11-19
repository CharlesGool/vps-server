"""Scheduled tasks: cron schedules, run history and the built-in backup job.

Times are the host's local time, like cron. A task is a shell command run
through ``systemd-run`` (outside the console's read-only sandbox) with a
timeout; a task that is still running is not started again (the skip is
recorded); only the newest runs are kept. The configuration backup is a
second kind of job with its own daily time and retention.
"""

import calendar
import json
import os
import re
import secrets
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import secure_store

HISTORY_PER_TASK = 20
OUTPUT_TAIL = 4096
MAX_TASKS = 50
NAME_MAX = 60
COMMAND_MAX = 2000
TIMEOUT_MIN, TIMEOUT_MAX, TIMEOUT_DEFAULT = 1, 86400, 3600
TASK_ID_RE = re.compile(r"[0-9a-f]{8}")
MACROS = {"@hourly": "0 * * * *", "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
          "@weekly": "0 0 * * 0", "@monthly": "0 0 1 * *", "@yearly": "0 0 1 1 *",
          "@annually": "0 0 1 1 *"}
FIELD_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))
BACKUP_DEFAULTS = {"enabled": True, "spec": {"mode": "daily", "time": "03:00:00"}, "keep": 7}
BACKUP_KEEP_MAX = 100


class ScheduleError(ValueError):
    pass


def _field(text, low, high):
    values = set()
    for part in text.split(","):
        step = 1
        if "/" in part:
            part, step_text = part.split("/", 1)
            if not step_text.isdigit() or not 0 < int(step_text) <= high:
                raise ScheduleError("invalid step")
            step = int(step_text)
        if part == "*":
            start, end = low, high
        elif re.fullmatch(r"\d+-\d+", part):
            start, end = (int(x) for x in part.split("-"))
        elif part.isdigit():
            start = int(part)
            end = high if step != 1 else start
        else:
            raise ScheduleError("invalid field")
        if not (low <= start <= end <= high):
            raise ScheduleError("value out of range")
        values.update(range(start, end + 1, step))
    return values


def parse_cron(text):
    """Five fields (minute hour day month weekday) or a macro such as @daily."""
    if not isinstance(text, str) or len(text) > 100:
        raise ScheduleError("invalid schedule")
    text = MACROS.get(text.strip(), text.strip())
    parts = text.split()
    if len(parts) != 5:
        raise ScheduleError("a schedule has five fields")
    minute, hour, day, month, weekday = (_field(part, *span) for part, span in zip(parts, FIELD_RANGES))
    weekday = {value % 7 for value in weekday}  # 7 is Sunday too
    return {"minute": minute, "hour": hour, "day": day, "month": month, "weekday": weekday,
            "day_any": parts[2].startswith("*"),
            "weekday_any": parts[4].startswith("*")}


def _day_matches(schedule, moment):
    day_ok = moment.day in schedule["day"]
    # cron weekday: Sunday is 0
    weekday_ok = (moment.weekday() + 1) % 7 in schedule["weekday"]
    if schedule["day_any"] and schedule["weekday_any"]:
        return True
    if schedule["day_any"]:
        return weekday_ok
    if schedule["weekday_any"]:
        return day_ok
    return day_ok or weekday_ok  # both restricted: either one, as cron does


def matches(schedule, moment):
    return (moment.minute in schedule["minute"] and moment.hour in schedule["hour"]
            and moment.month in schedule["month"] and _day_matches(schedule, moment))


def next_run(text, after):
    """The first matching minute strictly after ``after`` (naive local time), or None."""
    schedule = parse_cron(text)
    moment = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = moment + timedelta(days=366 * 5)
    while moment < limit:
        if moment.month not in schedule["month"]:
            year, month = (moment.year + 1, 1) if moment.month == 12 else (moment.year, moment.month + 1)
            moment = datetime(year, month, 1)
            continue
        if not _day_matches(schedule, moment):
            moment = datetime(moment.year, moment.month, moment.day) + timedelta(days=1)
            continue
        if moment.hour not in schedule["hour"]:
            moment = moment.replace(minute=0) + timedelta(hours=1)
            continue
        if moment.minute not in schedule["minute"]:
            moment += timedelta(minutes=1)
            continue
        return moment
    return None


def valid_name(value):
    return isinstance(value, str) and 1 <= len(value.strip()) <= NAME_MAX \
        and not any(ord(c) < 32 for c in value)


def valid_command(value):
    return isinstance(value, str) and 1 <= len(value.strip()) <= COMMAND_MAX and "\0" not in value


UNIT_SECONDS = {"minutes": 60, "hours": 3600, "days": 86400}
INTERVAL_MAX_SECONDS = 366 * 86400
RECURRING = ("interval", "daily", "weekly", "monthly", "yearly", "cron")
MODES = RECURRING + ("once",)
TIME_RE = re.compile(r"([01]\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?")
# A time-of-day schedule missed by less than this (the console was down or busy) still runs, once.
GRACE_SECONDS = 120
DEFAULT_BACKUP_SPEC = {"mode": "daily", "time": "03:00:00"}


def normalize_spec(spec):
    """A schedule choice as stored: ``interval``, ``daily``, ``weekly``, ``monthly``, ``yearly`` or ``cron``.

    Times are ``HH:MM:SS`` (seconds default to 00). A bare string is a cron expression (the
    oldest form). Monthly and yearly days run up to 31; in a shorter month they fall on its
    last day. Raises ScheduleError.
    """
    if isinstance(spec, str):
        spec = {"mode": "cron", "expr": spec}
    if not isinstance(spec, dict) or spec.get("mode") not in MODES:
        raise ScheduleError("invalid schedule")
    mode = spec["mode"]
    if mode == "interval":
        try:
            n = int(spec.get("n"))
        except (TypeError, ValueError):
            raise ScheduleError("invalid interval") from None
        unit = spec.get("unit")
        if unit not in UNIT_SECONDS or n < 1 or n * UNIT_SECONDS[unit] > INTERVAL_MAX_SECONDS:
            raise ScheduleError("invalid interval")
        return {"mode": "interval", "n": n, "unit": unit}
    if mode == "cron":
        expr = spec.get("expr")
        parse_cron(expr)
        return {"mode": "cron", "expr": expr.strip()}
    at = spec.get("time")
    match = TIME_RE.fullmatch(at) if isinstance(at, str) else None
    if not match:
        raise ScheduleError("invalid time")
    at = f"{match.group(1)}:{match.group(2)}:{match.group(3) or '00'}"
    if mode == "once":
        date = spec.get("date")
        if not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise ScheduleError("invalid date")
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise ScheduleError("invalid date") from None
        return {"mode": "once", "date": date, "time": at}
    if mode == "daily":
        return {"mode": "daily", "time": at}
    if mode == "weekly":
        days = spec.get("days")
        if not isinstance(days, list) or not days or any(
                not isinstance(d, int) or isinstance(d, bool) or not 0 <= d <= 6 for d in days):
            raise ScheduleError("invalid days")
        return {"mode": "weekly", "days": sorted(set(days)), "time": at}
    day = spec.get("day")
    if not isinstance(day, int) or isinstance(day, bool) or not 1 <= day <= 31:
        raise ScheduleError("invalid day")
    if mode == "yearly":
        month = spec.get("month")
        if not isinstance(month, int) or isinstance(month, bool) or not 1 <= month <= 12 or \
                day > calendar.monthrange(2000, month)[1]:
            raise ScheduleError("invalid date")
        return {"mode": "yearly", "month": month, "day": day, "time": at}
    return {"mode": "monthly", "day": day, "time": at}


# Day-of-week/month/year rules shared with the traffic reset schedules (node_inventory).
from schedule_time import day_matches as _day_matches_spec, next_occurrence, previous_occurrence  # noqa: E402,F401


def once_time(spec):
    """The unix time a one-time spec runs at (local time)."""
    return datetime.strptime(f"{spec['date']} {spec['time']}", "%Y-%m-%d %H:%M:%S").timestamp()


def require_future(spec, now):
    """A one-time schedule must lie ahead; ScheduleError otherwise."""
    if spec["mode"] == "once" and once_time(spec) <= now:
        raise ScheduleError("that time has already passed")


def check_due(spec, now, marker):
    """(action, new marker) for one schedule at ``now`` (a unix time); action is ``"run"``, ``"missed"`` or None.

    ``marker`` is what was remembered at the last start (or at creation): the last start for an
    interval, the minute for cron, the run time for a daily, weekly or monthly spec. Starting from
    the marker means a restart never repeats a run and a long outage makes one run, not a burst.
    """
    mode = spec["mode"]
    if mode == "interval":
        due = marker is not None and now >= marker + spec["n"] * UNIT_SECONDS[spec["unit"]]
        return ("run" if due else None), int(now)
    if mode == "once":
        stamp = once_time(spec)
        if (marker or 0) >= stamp or now < stamp:
            return None, int(stamp)
        # Due. Late by more than the grace period (the console was down) is not run after the fact.
        return ("run" if now - stamp <= GRACE_SECONDS else "missed"), int(stamp)
    moment = datetime.fromtimestamp(now)
    if mode == "cron":
        minute = moment.replace(second=0, microsecond=0)
        fire = (marker or 0) < minute.timestamp() and matches(parse_cron(spec["expr"]), minute)
        return ("run" if fire else None), int(minute.timestamp())
    occurrence = previous_occurrence(spec, moment)
    if occurrence is None:
        return None, None
    stamp = occurrence.timestamp()
    return ("run" if (marker or 0) < stamp and now - stamp <= GRACE_SECONDS else None), int(stamp)


def next_time(spec, marker, now):
    """When a schedule next runs (unix time), or None."""
    mode = spec["mode"]
    if mode == "interval":
        return int((marker if marker is not None else now) + spec["n"] * UNIT_SECONDS[spec["unit"]])
    if mode == "once":
        stamp = once_time(spec)
        return int(stamp) if stamp > now and (marker or 0) < stamp else None
    if mode == "cron":
        moment = next_run(spec["expr"], datetime.fromtimestamp(now))
    else:
        moment = next_occurrence(spec, datetime.fromtimestamp(now))
    return int(moment.timestamp()) if moment else None


def parse_backup_settings(enabled, spec, keep, now=None):
    """The scheduled-backup settings, validated: ``{"enabled", "spec", "keep"}``.

    With ``now`` given (when saving, not when reading what was saved), a one-time spec must lie ahead.
    """
    spec = normalize_spec(spec)
    if now is not None and enabled:
        require_future(spec, now)
    if not isinstance(keep, str) and not isinstance(keep, int) or not str(keep).isdigit() \
            or not 1 <= int(keep) <= BACKUP_KEEP_MAX:
        raise ScheduleError("invalid retention")
    return {"enabled": bool(enabled), "spec": spec, "keep": int(keep)}


def task_spec(task):
    """The spec of a stored task, also for tasks saved before specs existed."""
    try:
        return normalize_spec(task.get("spec") or task.get("schedule"))
    except ScheduleError:
        return None


def _write_json(path, document):
    secure_store.write_text(path, json.dumps(document, ensure_ascii=False) + "\n")


_json_cache = {}


def _read_json(path, default):
    """Parsed JSON, re-read (and decrypted) only when the file changed: the loop looks every second."""
    try:
        info = os.stat(path)
        stamp = (info.st_mtime_ns, info.st_ino, info.st_size)
    except OSError:
        return default
    cached = _json_cache.get(str(path))
    if cached and cached[0] == stamp:
        document = cached[1]
    else:
        try:
            document = json.loads(secure_store.read_text(path))
        except (OSError, ValueError):
            return default
        _json_cache[str(path)] = (stamp, document)
    return json.loads(json.dumps(document)) if isinstance(document, type(default)) else default


class Scheduler:
    """Owns ``scheduled-tasks.json`` (definitions) and ``scheduled-runs.json`` (history)."""

    def __init__(self, data_dir, *, backup_action, notify=None, run_command=None, clock=time.time, active=None):
        self.tasks_path = Path(data_dir) / "scheduled-tasks.json"
        self.runs_path = Path(data_dir) / "scheduled-runs.json"
        self.backup_path = Path(data_dir) / "backup-settings.json"
        self.backup_action = backup_action
        self.notify = notify or (lambda title, body: None)
        self.run_command = run_command or self._systemd_run
        self.clock = clock
        # The home switches: active("tasks") / active("backup") false pauses those schedules (markers stay put).
        self.active = active or (lambda feature: True)
        self.lock = threading.RLock()
        self.running = set()
        self._stop = threading.Event()
        self._thread = None
        
    # -- definitions -----------------------------------------------------

    def tasks(self):
        document = _read_json(self.tasks_path, {})
        return [task for task in document.get("tasks", []) if isinstance(task, dict)]

    def _save_tasks(self, tasks):
        _write_json(self.tasks_path, {"version": 1, "tasks": tasks})

    def add_task(self, name, spec, command, timeout=TIMEOUT_DEFAULT, notify=True, enabled=True):
        task = self._checked(None, name, spec, command, timeout, notify, enabled, int(self.clock()))
        with self.lock:
            tasks = self.tasks()
            if len(tasks) >= MAX_TASKS:
                raise ScheduleError("too many tasks")
            tasks.append(task)
            self._save_tasks(tasks)
        return task["id"]

    def edit_task(self, task_id, name, spec, command, timeout, notify, enabled):
        with self.lock:
            tasks = self.tasks()
            for index, task in enumerate(tasks):
                if task.get("id") == task_id:
                    tasks[index] = self._checked(task_id, name, spec, command, timeout, notify, enabled,
                                                 int(self.clock()))
                    self._save_tasks(tasks)
                    return
        raise ScheduleError("unknown task")

    def set_enabled(self, task_id, enabled):
        with self.lock:
            tasks = self.tasks()
            for task in tasks:
                if task.get("id") == task_id:
                    spec = task_spec(task)
                    if enabled and spec is not None:
                        require_future(spec, self.clock())      # a one-time task whose time has passed cannot be re-armed
                    task["enabled"] = bool(enabled)
                    self._save_tasks(tasks)
                    return
        raise ScheduleError("unknown task")

    def delete_task(self, task_id):
        with self.lock:
            tasks = self.tasks()
            kept = [task for task in tasks if task.get("id") != task_id]
            if len(kept) == len(tasks):
                raise ScheduleError("unknown task")
            self._save_tasks(kept)
            runs = self._runs()
            runs.pop(task_id, None)
            _write_json(self.runs_path, runs)

    @staticmethod
    def _checked(task_id, name, spec, command, timeout, notify, enabled, now):
        if not valid_name(name) or not valid_command(command):
            raise ScheduleError("invalid task")
        spec = normalize_spec(spec)
        if enabled:
            require_future(spec, now)
        timeout = int(timeout)
        if not TIMEOUT_MIN <= timeout <= TIMEOUT_MAX:
            raise ScheduleError("invalid timeout")
        return {"id": task_id or secrets.token_hex(4), "name": name.strip(), "spec": spec,
                "schedule": spec["expr"] if spec["mode"] == "cron" else "", "anchor": now, "done": None,
                "command": command, "timeout": timeout, "notify": bool(notify), "enabled": bool(enabled)}

    # -- backup settings -------------------------------------------------

    def backup_settings(self):
        """``{"enabled", "spec", "keep", "anchor"}``; an older file with ``time`` becomes a daily spec."""
        document = _read_json(self.backup_path, {})
        try:
            spec = document["spec"] if "spec" in document else {
                "mode": "daily", "time": document.get("time", "03:00")}
            settings = parse_backup_settings(document.get("enabled", True), spec, document.get("keep", 7))
        except (ScheduleError, AttributeError, KeyError):
            settings = json.loads(json.dumps(BACKUP_DEFAULTS))
        anchor = document.get("anchor")
        settings["anchor"] = anchor if isinstance(anchor, int) and not isinstance(anchor, bool) else None
        return settings

    def save_backup_settings(self, settings):
        """Save new settings; counting starts now, so a time earlier today does not fire at once."""
        stored = {key: settings[key] for key in ("enabled", "spec", "keep")}
        stored["anchor"] = int(self.clock())
        _write_json(self.backup_path, stored)

    def _store_backup(self, anchor, **changes):
        """Write the backup settings in the current format (dropping any old keys), with a new marker."""
        settings = self.backup_settings()
        document = {key: settings[key] for key in ("enabled", "spec", "keep")}
        document.update(changes)
        document["anchor"] = int(anchor)
        _write_json(self.backup_path, document)

    def _set_backup_anchor(self, stamp):
        self._store_backup(stamp)

    # -- history -----------------------------------------------------------

    def _runs(self):
        return _read_json(self.runs_path, {})

    def runs(self, task_id):
        return list(self._runs().get(task_id, []))

    def _record(self, task_id, entry):
        with self.lock:
            runs = self._runs()
            history = runs.setdefault(task_id, [])
            history.insert(0, entry)
            del history[HISTORY_PER_TASK:]
            _write_json(self.runs_path, runs)

    def last_run(self, task_id):
        history = self.runs(task_id)
        return history[0] if history else None

    # -- running -----------------------------------------------------------

    @staticmethod
    def _systemd_run(command, timeout):
        unit = "vps-server-task-" + secrets.token_hex(4)
        result = subprocess.run(
            ["systemd-run", "--quiet", "--wait", "--pipe", "--collect", "--unit=" + unit,
             f"--property=RuntimeMaxSec={timeout}", "/bin/bash", "-c", command],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout + 15, check=False)
        return result.returncode, result.stdout

    def run_task(self, task_id, trigger="schedule"):
        """Run one task now (blocking). Returns the recorded entry."""
        task = next((item for item in self.tasks() if item.get("id") == task_id), None)
        if task is None:
            raise ScheduleError("unknown task")
        started = int(self.clock())
        with self.lock:
            if task_id in self.running:
                entry = {"started": started, "ended": started, "status": "skipped", "exit": None,
                         "trigger": trigger, "output": "still running"}
                self._record(task_id, entry)
                return entry
            self.running.add(task_id)
        try:
            try:
                code, raw = self.run_command(task["command"], task["timeout"])
                output = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw or "")
                elapsed = self.clock() - started
                if code == 0:
                    status = "ok"
                elif elapsed >= task["timeout"] - 1:
                    status = "timeout"
                else:
                    status = "failed"
            except subprocess.TimeoutExpired:
                code, output, status = None, "", "timeout"
            except (OSError, subprocess.SubprocessError) as exc:
                code, output, status = None, type(exc).__name__, "failed"
            entry = {"started": started, "ended": int(self.clock()), "status": status, "exit": code,
                     "trigger": trigger, "output": output[-OUTPUT_TAIL:]}
            self._record(task_id, entry)
        finally:
            with self.lock:
                self.running.discard(task_id)
        if entry["status"] in ("failed", "timeout") and task.get("notify"):
            self.notify(task["name"], entry["status"] + (f" (exit {entry['exit']})" if entry["exit"] is not None else ""))
        return entry

    def run_backup(self, trigger="schedule"):
        """Create a scheduled backup and prune old ones; record it like a task."""
        settings = self.backup_settings()
        started = int(self.clock())
        try:
            name = self.backup_action(settings["keep"])
            entry = {"started": started, "ended": int(self.clock()), "status": "ok", "exit": 0,
                     "trigger": trigger, "output": name}
        except Exception as exc:  # the action reports its own failures; keep the loop alive
            entry = {"started": started, "ended": int(self.clock()), "status": "failed", "exit": None,
                     "trigger": trigger, "output": str(exc)[:200] or type(exc).__name__}
            self.notify("backup", "failed")
        self._record("backup", entry)
        return entry

    def start_async(self, target, *args):
        threading.Thread(target=target, args=args, daemon=True).start()

    # -- loop ----------------------------------------------------------------

    def _set_anchor(self, task_id, stamp):
        with self.lock:
            tasks = self.tasks()
            for task in tasks:
                if task.get("id") == task_id:
                    task["anchor"] = int(stamp)
                    self._save_tasks(tasks)
                    return

    def _finish_once_task(self, task_id, marker, outcome):
        """A one-time task is over (it ran or was missed): remember when, stop it, keep it listed."""
        with self.lock:
            tasks = self.tasks()
            for task in tasks:
                if task.get("id") == task_id:
                    task.update({"anchor": int(marker), "enabled": False, "done": outcome})
                    self._save_tasks(tasks)
                    return

    def tick(self, now=None):
        """Start whatever is due. Called every second; each schedule decides from its own marker."""
        stamp = now if now is not None else self.clock()
        started = []
        for task in (self.tasks() if self.active("tasks") else []):
            if not task.get("enabled"):
                continue
            spec = task_spec(task)
            if spec is None:
                continue
            marker = task.get("anchor")
            if not isinstance(marker, int):
                self._set_anchor(task["id"], stamp)       # an old task without a marker: count from now
                continue
            action, new_marker = check_due(spec, stamp, marker)
            if action is None:
                continue
            if spec["mode"] == "once":
                self._finish_once_task(task["id"], new_marker, "ran" if action == "run" else "missed")
            else:
                self._set_anchor(task["id"], new_marker)
            if action == "run":
                self.start_async(self.run_task, task["id"])
                started.append(task["id"])
            else:
                self._record(task["id"], {"started": int(stamp), "ended": int(stamp), "status": "skipped", "exit": None,
                                          "trigger": "schedule", "output": "missed"})
        settings = self.backup_settings()
        if settings["enabled"] and self.active("backup"):
            if settings["anchor"] is None:
                self._set_backup_anchor(stamp)
            else:
                action, new_marker = check_due(settings["spec"], stamp, settings["anchor"])
                if action:
                    self._set_backup_anchor(new_marker)
                    if settings["spec"]["mode"] == "once":
                        self._disable_backup_schedule()
                    if action == "run":
                        self.start_async(self.run_backup)
                        started.append("backup")
                    else:
                        self._record("backup", {"started": int(stamp), "ended": int(stamp), "status": "skipped", "exit": None,
                                                "trigger": "schedule", "output": "missed"})
        return started

    def _disable_backup_schedule(self):
        self._store_backup(self.backup_settings()["anchor"] or self.clock(), enabled=False)

    def start(self):
        if self._thread:
            return

        def loop():
            while not self._stop.wait(1):
                try:
                    self.tick()
                except Exception:  # a bad file must not stop the scheduler
                    pass

        self._thread = threading.Thread(target=loop, name="scheduler", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def next_for(self, task):
        spec = task_spec(task)
        if spec is None:
            return None
        try:
            return next_time(spec, task.get("anchor"), self.clock())
        except ScheduleError:
            return None

    def next_backup(self):
        settings = self.backup_settings()
        if not settings["enabled"]:
            return None
        try:
            return next_time(settings["spec"], settings["anchor"], self.clock())
        except ScheduleError:
            return None
