"""Scheduled tasks: cron schedules, run history and the built-in backup job.

Times are the host's local time, like cron. A task is a shell command run
through ``systemd-run`` (outside the console's read-only sandbox) with a
timeout; a task that is still running is not started again (the skip is
recorded); only the newest runs are kept. The configuration backup is a
second kind of job with its own daily time and retention.
"""

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
BACKUP_DEFAULTS = {"enabled": True, "time": "03:00", "keep": 7}
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


def parse_backup_settings(enabled, at, keep):
    if not isinstance(at, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", at):
        raise ScheduleError("invalid time")
    if not isinstance(keep, str) and not isinstance(keep, int) or not str(keep).isdigit() \
            or not 1 <= int(keep) <= BACKUP_KEEP_MAX:
        raise ScheduleError("invalid retention")
    return {"enabled": bool(enabled), "time": at, "keep": int(keep)}


UNIT_SECONDS = {"minutes": 60, "hours": 3600, "days": 86400}
INTERVAL_MAX_SECONDS = 366 * 86400
MODES = ("interval", "daily", "weekly", "monthly", "cron")
TIME_RE = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")


def normalize_spec(spec):
    """A schedule choice as stored: ``interval``, ``daily``, ``weekly``, ``monthly`` or ``cron``.

    A bare string is a cron expression (the older form). Raises ScheduleError.
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
    if mode == "daily":
        return {"mode": "daily", "time": at}
    if mode == "weekly":
        days = spec.get("days")
        if not isinstance(days, list) or not days or any(
                not isinstance(d, int) or isinstance(d, bool) or not 0 <= d <= 6 for d in days):
            raise ScheduleError("invalid days")
        return {"mode": "weekly", "days": sorted(set(days)), "time": at}
    day = spec.get("day")
    if not isinstance(day, int) or isinstance(day, bool) or not 1 <= day <= 28:
        raise ScheduleError("invalid day")
    return {"mode": "monthly", "day": day, "time": at}


def cron_for(spec):
    """The cron expression for a non-interval spec; None for an interval."""
    mode = spec["mode"]
    if mode == "interval":
        return None
    if mode == "cron":
        return spec["expr"]
    hour, minute = (int(part) for part in spec["time"].split(":"))
    if mode == "daily":
        return f"{minute} {hour} * * *"
    if mode == "weekly":
        return f"{minute} {hour} * * " + ",".join(str(d) for d in spec["days"])
    return f"{minute} {hour} {spec['day']} * *"


def task_spec(task):
    """The spec of a stored task, also for tasks saved before specs existed."""
    try:
        return normalize_spec(task.get("spec") or task.get("schedule"))
    except ScheduleError:
        return None


def _write_json(path, document):
    secure_store.write_text(path, json.dumps(document, ensure_ascii=False) + "\n")


def _read_json(path, default):
    try:
        document = json.loads(secure_store.read_text(path))
    except (OSError, ValueError):
        return default
    return document if isinstance(document, type(default)) else default


class Scheduler:
    """Owns ``scheduled-tasks.json`` (definitions) and ``scheduled-runs.json`` (history)."""

    def __init__(self, data_dir, *, backup_action, notify=None, run_command=None, clock=time.time):
        self.tasks_path = Path(data_dir) / "scheduled-tasks.json"
        self.runs_path = Path(data_dir) / "scheduled-runs.json"
        self.backup_path = Path(data_dir) / "backup-settings.json"
        self.backup_action = backup_action
        self.notify = notify or (lambda title, body: None)
        self.run_command = run_command or self._systemd_run
        self.clock = clock
        self.lock = threading.RLock()
        self.running = set()
        self._stop = threading.Event()
        self._thread = None
        self._last_minute = None

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
        timeout = int(timeout)
        if not TIMEOUT_MIN <= timeout <= TIMEOUT_MAX:
            raise ScheduleError("invalid timeout")
        return {"id": task_id or secrets.token_hex(4), "name": name.strip(), "spec": spec,
                "schedule": cron_for(spec) or "", "anchor": now,
                "command": command, "timeout": timeout, "notify": bool(notify), "enabled": bool(enabled)}

    # -- backup settings -------------------------------------------------

    def backup_settings(self):
        document = _read_json(self.backup_path, {})
        try:
            return parse_backup_settings(document.get("enabled", True), document.get("time", "03:00"),
                                         document.get("keep", 7))
        except (ScheduleError, AttributeError):
            return dict(BACKUP_DEFAULTS)

    def save_backup_settings(self, settings):
        _write_json(self.backup_path, settings)

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

    def tick(self, now=None):
        """Start whatever is due. Interval tasks are checked on every call; cron tasks once per minute."""
        stamp = now if now is not None else self.clock()
        moment = datetime.fromtimestamp(stamp)
        minute = moment.replace(second=0, microsecond=0)
        new_minute = minute != self._last_minute
        self._last_minute = minute
        started = []
        for task in self.tasks():
            if not task.get("enabled"):
                continue
            spec = task_spec(task)
            if spec is None:
                continue
            if spec["mode"] == "interval":
                anchor = task.get("anchor")
                if not isinstance(anchor, int):
                    self._set_anchor(task["id"], stamp)
                    continue
                if stamp >= anchor + spec["n"] * UNIT_SECONDS[spec["unit"]]:
                    # The next interval counts from now, so a long outage makes one run, not a burst.
                    self._set_anchor(task["id"], stamp)
                    self.start_async(self.run_task, task["id"])
                    started.append(task["id"])
            elif new_minute and matches(parse_cron(cron_for(spec)), minute) \
                    and not self._ran_since(task["id"], minute.timestamp()):
                self.start_async(self.run_task, task["id"])
                started.append(task["id"])
        if new_minute:
            settings = self.backup_settings()
            if settings["enabled"] and minute.strftime("%H:%M") == settings["time"] \
                    and not self._ran_since("backup", minute.timestamp()):
                self.start_async(self.run_backup)
                started.append("backup")
        return started

    def _ran_since(self, task_id, stamp):
        """True when a scheduled run already started in this minute (the console restarted inside it)."""
        last = self.last_run(task_id)
        return bool(last and last.get("trigger") == "schedule" and last["started"] >= stamp)

    def start(self):
        if self._thread:
            return

        def loop():
            while not self._stop.wait(10):
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
        if spec["mode"] == "interval":
            anchor = task.get("anchor")
            base = anchor if isinstance(anchor, int) else self.clock()
            return int(base + spec["n"] * UNIT_SECONDS[spec["unit"]])
        try:
            moment = next_run(cron_for(spec), datetime.fromtimestamp(self.clock()))
        except ScheduleError:
            return None
        return int(moment.timestamp()) if moment else None

    def next_backup(self):
        settings = self.backup_settings()
        if not settings["enabled"]:
            return None
        hour, minute = (int(part) for part in settings["time"].split(":"))
        return self.next_for({"spec": {"mode": "cron", "expr": f"{minute} {hour} * * *"}})
