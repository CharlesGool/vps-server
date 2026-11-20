"""JSON API for configuration backups and scheduled tasks; both share one schedule format.

Times are formatted on the server in its own time zone, the one schedules run in.
Restoring writes system files, so it still runs through ``systemd-run``.
Tasks run commands as root and backups hold every secret, so like the terminal every
route needs a recent admin re-verification; ``route_api`` checks it (SECURE_FEATURES).
"""

import os
import secrets
import subprocess
import tempfile
from pathlib import Path

import config_backup
import scheduler
import secure_store
from field_errors import FieldError, details, schedule_error
from features import schedule_form
from features.backup import MAX_UPLOAD, RESTORE_SCRIPT, UPLOAD_IDLE_TIMEOUT, local_time


def schedule_problem(error, body):
    """The input a scheduler.ScheduleError from saving a task or the backup settings is about, as a
    FieldError; None when it is about none (too many tasks, an unknown task)."""
    message = str(error)
    if message in ("too many tasks", "unknown task"):
        return None
    if message == "invalid task":
        name, command = body.get("name"), body.get("command")
        if not scheduler.valid_name(name):
            name = name.strip()
            return FieldError("name", "required" if not name else
                              "too_long" if len(name) > scheduler.NAME_MAX else "format", message)
        command = command.strip()
        return FieldError("command", "required" if not command else
                          "too_long" if len(command) > scheduler.COMMAND_MAX else "format", message)
    if message == "invalid timeout":
        return FieldError("timeout", "range", message)
    if message == "invalid retention":
        keep = body.get("keep")
        return FieldError("keep", "type" if isinstance(keep, bool) or not isinstance(keep, (int, str)) else
                          "format" if not str(keep).isdigit() else "range", message)
    return schedule_error(error, body.get("spec"))


def schedule_code(error):
    """The error code for a refused schedule save; unchanged by the field it names."""
    message = str(error)
    return ("limit" if "many" in message else "past" if "passed" in message
            else "not_found" if "unknown" in message else "invalid")


class ScheduleApiMixin:
    API_ROUTES_SCHEDULE = {
        ("GET", "backup"): "api_backup",
        ("POST", "backup/create"): "api_backup_create",
        ("PUT", "backup/settings"): "api_backup_settings",
        ("POST", "backup/delete"): "api_backup_delete",
        ("POST", "backup/upload"): "api_backup_upload",
        ("POST", "backup/inspect"): "api_backup_inspect",
        ("POST", "backup/restore"): "api_backup_restore",
        ("POST", "backup/key/new"): "api_backup_key_new",
        ("PUT", "backup/key"): "api_backup_key_set",
        ("GET", "tasks"): "api_tasks",
        ("PUT", "tasks/save"): "api_tasks_save",
        ("POST", "tasks/toggle"): "api_tasks_toggle",
        ("POST", "tasks/delete"): "api_tasks_delete",
        ("POST", "tasks/run"): "api_tasks_run",
    }

    def _schedule_t(self):
        lang, _ = self.resolve_lang(self.context.urlsplit(self.path))
        return self.context.STRINGS[lang]

    @staticmethod
    def _run_json(entry):
        if not entry:
            return None
        return {"status": entry["status"], "started": local_time(entry["started"]), "exit": entry.get("exit"),
                "trigger": entry.get("trigger", "schedule"), "output": entry.get("output", "")}

    # -- backups -----------------------------------------------------------------

    def backup_state(self, message=None):
        t = self._schedule_t()
        engine = self.context.SCHEDULER
        settings = engine.backup_settings()
        following = engine.next_backup()
        recipient = config_backup.read_recipient()
        try:
            files = secure_store.status()
            data = {"state": "on" if secure_store.enabled() else "off",
                    "encrypted": sum(1 for _path, state in files if state == "encrypted"), "total": len(files)}
        except (OSError, ValueError):
            data = {"state": "error", "encrypted": 0, "total": 0}
        outcome = config_backup.read_result()
        return {
            "settings": {"enabled": settings["enabled"], "spec": settings["spec"], "keep": settings["keep"],
                         "text": schedule_form.describe(t, settings["spec"])},
            "keepMax": scheduler.BACKUP_KEEP_MAX,
            "last": self._run_json(engine.last_run("backup")),
            "next": local_time(following) if following else None,
            "backups": [{"name": item["name"], "kind": item["kind"], "sealed": item["sealed"],
                         "keyMatch": item["key_match"], "created": local_time(item["created"]), "size": item["size"]}
                        for item in config_backup.list_backups()],
            "encryption": {"on": recipient is not None,
                           "fingerprint": config_backup.key_fingerprint(recipient) if recipient is not None else None},
            "data": data,
            "result": ({"ok": outcome["ok"], "time": local_time(outcome.get("time", 0)),
                        "name": outcome.get("name", ""), "restored": outcome.get("restored", 0),
                        "error": outcome.get("error", "")} if outcome else None),
            "timezone": self.context.time.tzname[0],
            "message": message,
        }

    def api_backup(self):
        return self.api_ok(self.backup_state())

    def api_backup_create(self):
        if self.read_json() is None:
            return self.api_error(400, "invalid_request")
        try:
            config_backup.create_backup("manual")
        except config_backup.BackupError as exc:
            return self.api_error(500, "no_space" if "space" in str(exc) else "failed")
        return self.api_ok(self.backup_state("created"))

    def api_backup_settings(self):
        body = self.read_json() or {}
        try:
            settings = scheduler.parse_backup_settings(body.get("enabled") is True, body.get("spec"),
                                                       body.get("keep"), self.context.SCHEDULER.clock())
            self.context.SCHEDULER.save_backup_settings(settings)
        except scheduler.ScheduleError as exc:
            return self.api_error(400, "past" if "passed" in str(exc) else "invalid",
                                  **details(schedule_problem(exc, body)))
        except OSError:
            return self.api_error(500, "failed")
        return self.api_ok(self.backup_state("settings"))

    def _backup_name(self):
        name = (self.read_json() or {}).get("name")
        return name if isinstance(name, str) else None

    def api_backup_delete(self):
        name = self._backup_name()
        try:
            config_backup.delete_backup(name or "")
        except config_backup.BackupError:
            return self.api_error(404, "not_found")
        return self.api_ok(self.backup_state("deleted"))

    def api_backup_upload(self):
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/octet-stream":
            return self.api_error(400, "invalid_request")
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self.api_error(411, "length_required")
        if not 0 < length <= MAX_UPLOAD:
            return self.api_error(400, "invalid")
        directory = config_backup.backup_dir()
        directory.mkdir(parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        descriptor, temporary = tempfile.mkstemp(prefix=".upload-", dir=directory)
        if self.connection is not None:
            self.connection.settimeout(UPLOAD_IDLE_TIMEOUT)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                remaining = length
                while remaining:
                    chunk = self.rfile.read(min(remaining, 1024 * 1024))
                    if not chunk:
                        raise OSError("short upload")
                    handle.write(chunk)
                    remaining -= len(chunk)
            os.chmod(temporary, 0o600)
            config_backup.validate_archive(temporary)
            config_backup.publish(temporary, "manual", suffix=".sealed" if config_backup.is_sealed(temporary) else "")
        except config_backup.BackupError:
            Path(temporary).unlink(missing_ok=True)
            return self.api_error(400, "invalid")
        except OSError:
            Path(temporary).unlink(missing_ok=True)
            self.close_connection = True
            return None
        finally:
            if self.connection is not None:
                try:
                    self.connection.settimeout(None)
                except OSError:
                    pass
        return self.api_ok(self.backup_state("uploaded"))

    def _restore_request(self):
        """(path, key text, body) of a restore request, or an error already sent."""
        body = self.read_json() or {}
        name, key = body.get("name"), body.get("privateKey") or ""
        if not isinstance(name, str) or not isinstance(key, str):
            self.api_error(400, "invalid_request")
            return None
        path, error = self.restore_target(name)
        if error:
            self.api_error(404, error)
            return None
        return path, key.strip(), body

    def api_backup_inspect(self):
        """What a backup holds; a sealed one needs its private key to look inside."""
        request = self._restore_request()
        if request is None:
            return
        path, key, _body = request
        try:
            info = config_backup.inspect(path, config_backup.parse_key(key) if key else None)
        except config_backup.BackupError:
            return self.api_error(400, "key_wrong")
        return self.api_ok({"name": path.name, "sealed": info["sealed"], "readable": info["readable"],
                            "keyMatch": info.get("key_match"), "host": info.get("host"),
                            "version": info.get("version"), "kind": info.get("kind"),
                            "created": local_time(info["created"]) if info.get("created") else None,
                            "files": info.get("files"), "sameHost": info.get("same_host"),
                            "newer": info.get("newer"), "risky": info.get("risky", False)})

    def api_backup_restore(self):
        request = self._restore_request()
        if request is None:
            return
        path, key_text, body = request
        key_file = None
        try:
            key = None
            if config_backup.is_sealed(path):
                if not key_text:
                    return self.api_error(400, "key_needed")
                key = config_backup.parse_key(key_text)
            # Decided here again, not trusted from the page: a backup from another host or a newer
            # version is restored only when the operator has said so.
            info = config_backup.inspect(path, key)
            if info.get("risky") and body.get("ack") is not True:
                return self.api_error(400, "ack_needed")
            if key is not None:
                descriptor, name = tempfile.mkstemp(prefix=".restore-key-", dir=path.parent)
                with os.fdopen(descriptor, "w", encoding="ascii") as handle:
                    handle.write(key_text + "\n")
                os.chmod(name, 0o600)
                key_file = name
        except config_backup.BackupError as exc:
            return self.api_error(400, "key_wrong" if "key" in str(exc) else "not_found")
        unit = "vps-server-restore-" + secrets.token_hex(4)
        command = ["systemd-run", "--quiet", "--collect", "--unit=" + unit, "/bin/bash", "-c", RESTORE_SCRIPT, "restore",
                   str(self.context.WEB_CODE_DIR / "config_backup.py"), str(path)]
        if key_file:
            command.append(key_file)
        try:
            subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=30, check=True)
        except (OSError, subprocess.SubprocessError):
            if key_file:
                Path(key_file).unlink(missing_ok=True)
            return self.api_error(500, "failed")
        return self.api_ok(self.backup_state("restore_started"))

    def api_backup_key_new(self):
        """A new key pair; the private key is shown once and never stored here."""
        if self.read_json() is None:
            return self.api_error(400, "invalid_request")
        try:
            private, public = config_backup.new_recipient()
        except OSError:
            return self.api_error(500, "failed")
        return self.api_ok({"private": private, "public": public,
                            "fingerprint": config_backup.key_fingerprint(config_backup.parse_key(public))})

    def api_backup_key_set(self):
        public = (self.read_json() or {}).get("public")
        try:
            key = config_backup.parse_key(public if isinstance(public, str) else "")
        except config_backup.BackupError:
            return self.api_error(400, "invalid", field="public", reason="format" if public else "required")
        try:
            config_backup.set_recipient(key)
        except (config_backup.BackupError, OSError):
            return self.api_error(400, "invalid")
        return self.api_ok(self.backup_state("key_set"))

    # -- scheduled tasks ------------------------------------------------------------

    def tasks_state(self, message=None):
        t = self._schedule_t()
        engine = self.context.SCHEDULER
        backup = engine.backup_settings()
        following = engine.next_backup()
        tasks = []
        for task in engine.tasks():
            enabled = bool(task.get("enabled"))
            spec = scheduler.task_spec(task)
            next_stamp = engine.next_for(task) if enabled else None
            tasks.append({
                "id": task["id"], "name": task["name"], "command": task["command"], "timeout": task["timeout"],
                "notify": bool(task.get("notify")), "enabled": enabled, "spec": spec,
                "text": schedule_form.describe(t, spec) if spec else "",
                "next": local_time(next_stamp) if next_stamp else None, "done": task.get("done"),
                "last": self._run_json(engine.last_run(task["id"])),
                "runs": [self._run_json(entry) for entry in engine.runs(task["id"])],
            })
        return {
            "backup": {"enabled": backup["enabled"], "text": schedule_form.describe(t, backup["spec"]),
                       "next": local_time(following) if following else None,
                       "last": self._run_json(engine.last_run("backup")),
                       "runs": [self._run_json(entry) for entry in engine.runs("backup")]},
            "tasks": tasks,
            "limits": {"nameMax": scheduler.NAME_MAX, "commandMax": scheduler.COMMAND_MAX,
                       "timeoutMin": scheduler.TIMEOUT_MIN, "timeoutMax": scheduler.TIMEOUT_MAX,
                       "timeoutDefault": scheduler.TIMEOUT_DEFAULT},
            "timezone": self.context.time.tzname[0],
            "message": message,
        }

    def api_tasks(self):
        return self.api_ok(self.tasks_state())

    def _task_id(self, body):
        task_id = (body or {}).get("id")
        return task_id if isinstance(task_id, str) and scheduler.TASK_ID_RE.fullmatch(task_id) else None

    def api_tasks_save(self):
        body = self.read_json() or {}
        name, command, timeout = body.get("name"), body.get("command"), body.get("timeout")
        for key, value in (("name", name), ("command", command)):
            if not isinstance(value, str):
                return self.api_error(400, "invalid", field=key, reason="required" if value is None else "type")
        if type(timeout) is not int:
            return self.api_error(400, "invalid", field="timeout", reason="required" if timeout is None else "type")
        if body.get("id") is not None and self._task_id(body) is None:
            return self.api_error(400, "invalid")
        engine = self.context.SCHEDULER
        notify, enabled = body.get("notify") is True, body.get("enabled") is True
        try:
            if body.get("id"):
                engine.edit_task(body["id"], name, body.get("spec"), command, timeout, notify, enabled)
            else:
                engine.add_task(name, body.get("spec"), command, timeout, notify, enabled)
        except scheduler.ScheduleError as exc:
            return self.api_error(400, schedule_code(exc), **details(schedule_problem(exc, body)))
        except (ValueError, OSError):
            return self.api_error(400, "invalid")
        return self.api_ok(self.tasks_state("saved"))

    def api_tasks_toggle(self):
        body = self.read_json()
        task_id = self._task_id(body)
        if task_id is None or not isinstance(body.get("enabled"), bool):
            return self.api_error(400, "invalid")
        try:
            self.context.SCHEDULER.set_enabled(task_id, body["enabled"])
        except scheduler.ScheduleError as exc:
            return self.api_error(400, "past" if "passed" in str(exc) else "not_found")
        return self.api_ok(self.tasks_state("toggled"))

    def api_tasks_delete(self):
        task_id = self._task_id(self.read_json())
        if task_id is None:
            return self.api_error(400, "invalid")
        try:
            self.context.SCHEDULER.delete_task(task_id)
        except scheduler.ScheduleError:
            return self.api_error(404, "not_found")
        return self.api_ok(self.tasks_state("deleted"))

    def api_tasks_run(self):
        task_id = self._task_id(self.read_json())
        engine = self.context.SCHEDULER
        if task_id is None or not any(task.get("id") == task_id for task in engine.tasks()):
            return self.api_error(404, "not_found")
        engine.start_async(engine.run_task, task_id, "manual")
        return self.api_ok(self.tasks_state("started"))
