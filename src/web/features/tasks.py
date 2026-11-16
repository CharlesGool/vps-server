"""Scheduled tasks page: list, add, edit, run now, history.

Host dependencies come from ``ConsoleHandler.context``; the scheduler itself
lives in ``scheduler.py``.
"""

import time

import scheduler
from features.backup import local_time

NOTICES = ("saved", "deleted", "started", "toggled")
ERRORS = ("invalid", "not_found", "limit")
PRESETS = (("*/5 * * * *", "task_preset_5min"), ("0 * * * *", "task_preset_hourly"),
           ("0 3 * * *", "task_preset_daily"), ("0 3 * * 0", "task_preset_weekly"),
           ("0 3 1 * *", "task_preset_monthly"))
FIELDS = ("id", "name", "schedule", "command", "timeout", "notify", "enabled")


class TasksMixin:
    def tasks_csrf(self):
        return self.context.access_csrf_token(self.get_cookie("session"), "tasks")

    def tasks_form(self, fields):
        raw = self.read_body(8192)
        try:
            form = self.context.parse_qs(raw.decode("utf-8"), strict_parsing=True, keep_blank_values=True)
        except (UnicodeError, ValueError):
            return None
        if not set(form) <= set(fields) | {"csrf"} or any(len(v) != 1 for v in form.values()):
            return None
        if "csrf" not in form or not self.context.hmac.compare_digest(form["csrf"][0], self.tasks_csrf()):
            return None
        return {key: value[0] for key, value in form.items() if key != "csrf"}

    def tasks_done(self, notice=None, error=None):
        query = f"error={error}" if error else f"msg={notice}"
        return self.redirect(f"/tasks?{query}", {"Cache-Control": "no-store"})

    def page_tasks(self, lang, query_lang, parsed):
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        engine = self.context.SCHEDULER
        query = self.context.parse_qs(parsed.query)
        messages = []
        msg = query.get("msg", [""])[0]
        if msg in NOTICES:
            messages.append(f'<p class="notice" role="status">{esc(t["task_msg_" + msg])}</p>')
        error = query.get("error", [""])[0]
        if error in ERRORS:
            messages.append(f'<p class="error" role="alert">{esc(t["task_error_" + error])}</p>')
        csrf = esc(self.tasks_csrf(), quote=True)
        hidden = f'<input type="hidden" name="csrf" value="{csrf}">'
        tasks = engine.tasks()
        editing = next((task for task in tasks if task.get("id") == query.get("edit", [""])[0]), None)

        def status_text(entry):
            if not entry:
                return esc(t["task_never"])
            return f'{esc(local_time(entry["started"]))} · {esc(t["task_status_" + entry["status"]])}'

        def history(task_id):
            runs = engine.runs(task_id)
            if not runs:
                return ""
            lines = []
            for entry in runs:
                exit_text = f' · {esc(t["task_exit"])} {entry["exit"]}' if entry.get("exit") is not None else ""
                output = (f'<pre class="files-meta" style="white-space:pre-wrap;overflow-wrap:anywhere;margin:.25rem 0">'
                          f'{esc(entry.get("output", ""))}</pre>' if entry.get("output") else "")
                lines.append(f'<li><span>{esc(local_time(entry["started"]))} · {esc(t["task_status_" + entry["status"]])}'
                             f'{exit_text} · {esc(t["task_trigger_" + entry.get("trigger", "schedule")])}</span>{output}</li>')
            return (f'<details><summary>{esc(t["task_history"])} ({len(runs)})</summary>'
                    f'<ul class="files-list">{"".join(lines)}</ul></details>')

        cards = []
        backup_settings = engine.backup_settings()
        following = engine.next_backup()
        cards.append(
            f'<li class="files-row"><div class="files-row-main"><strong>{esc(t["task_builtin_backup"])}</strong> '
            f'<span class="files-meta">({esc(t["task_builtin"])})</span>'
            f'<p class="files-meta">{esc(backup_settings["time"] if backup_settings["enabled"] else t["task_disabled"])}'
            + (f' · {esc(t["task_next"])}: {esc(local_time(following))}' if following else '')
            + f' · {esc(t["task_last"])}: {status_text(engine.last_run("backup"))}</p>'
            f'{history("backup")}</div><div class="files-row-actions">'
            f'<a class="files-button" href="/backup">{esc(t["task_open"])}</a></div></li>')
        for task in tasks:
            task_id = esc(task["id"], quote=True)
            next_stamp = engine.next_for(task) if task.get("enabled") else None
            toggle_label = t["task_disable"] if task.get("enabled") else t["task_enable"]
            cards.append(
                f'<li class="files-row"><div class="files-row-main"><strong>{esc(task["name"])}</strong>'
                f'{"" if task.get("enabled") else " <span class=files-meta>(" + esc(t["task_disabled"]) + ")</span>"}'
                f'<p class="files-meta"><code>{esc(task["schedule"])}</code>'
                + (f' · {esc(t["task_next"])}: {esc(local_time(next_stamp))}' if next_stamp else '')
                + f' · {esc(t["task_last"])}: {status_text(engine.last_run(task["id"]))}</p>'
                f'<p class="files-meta"><code style="overflow-wrap:anywhere">{esc(task["command"])}</code></p>'
                f'{history(task["id"])}</div><div class="files-row-actions">'
                f'<form method="post" action="/tasks/run">{hidden}<input type="hidden" name="id" value="{task_id}">'
                f'<button type="submit" class="files-button">{esc(t["task_run"])}</button></form>'
                f'<form method="post" action="/tasks/toggle">{hidden}<input type="hidden" name="id" value="{task_id}">'
                f'<input type="hidden" name="enabled" value="{0 if task.get("enabled") else 1}">'
                f'<button type="submit" class="files-button">{esc(toggle_label)}</button></form>'
                f'<a class="files-button" href="/tasks?edit={task_id}#task-form">{esc(t["task_edit"])}</a>'
                f'<form method="post" action="/tasks/delete" class="backup-confirm" '
                f'data-confirm="{esc(t["task_delete_confirm"].format(name=task["name"]), quote=True)}">{hidden}'
                f'<input type="hidden" name="id" value="{task_id}">'
                f'<button type="submit" class="files-button files-danger">{esc(t["task_delete"])}</button></form>'
                f'</div></li>')
        listing = (f'<section class="card frp-card"><h2 class="frp-instances-heading">{esc(t["tasks"])}</h2>'
                   f'<ul class="files-list">{"".join(cards)}</ul></section>')

        value = editing or {"name": "", "schedule": "0 3 * * *", "command": "", "timeout": scheduler.TIMEOUT_DEFAULT,
                            "notify": True, "enabled": True}
        presets = "".join(f'<option value="{esc(cron, quote=True)}">{esc(t[key])} — {esc(cron)}</option>'
                          for cron, key in PRESETS)
        form = (f'<section class="card frp-card" id="task-form">'
                f'<h2 class="frp-instances-heading">{esc(t["task_edit_heading"] if editing else t["task_add"])}</h2>'
                f'<form method="post" action="/tasks/save" class="tasks-form" style="display:grid;gap:.75rem">{hidden}'
                + (f'<input type="hidden" name="id" value="{esc(editing["id"], quote=True)}">' if editing else '')
                + f'<label>{esc(t["task_name"])}<input type="text" name="name" maxlength="{scheduler.NAME_MAX}" '
                f'value="{esc(value["name"], quote=True)}" required></label>'
                f'<label>{esc(t["task_schedule"])}<input type="text" name="schedule" id="task-schedule" '
                f'value="{esc(value["schedule"], quote=True)}" maxlength="100" required spellcheck="false"></label>'
                f'<label>{esc(t["task_preset"])}<select id="task-preset"><option value="">—</option>{presets}</select></label>'
                f'<p class="files-meta">{esc(t["task_schedule_help"])} {esc(t["task_timezone"])}: {esc(time.tzname[0])}</p>'
                f'<label>{esc(t["task_command"])}<textarea name="command" rows="4" maxlength="{scheduler.COMMAND_MAX}" '
                f'spellcheck="false" required>{esc(value["command"])}</textarea></label>'
                f'<label>{esc(t["task_timeout"])}<input type="number" name="timeout" min="{scheduler.TIMEOUT_MIN}" '
                f'max="{scheduler.TIMEOUT_MAX}" value="{value["timeout"]}" required></label>'
                f'<label><input type="checkbox" name="notify" value="1"{" checked" if value.get("notify") else ""}> '
                f'{esc(t["task_notify"])}</label>'
                f'<label><input type="checkbox" name="enabled" value="1"{" checked" if value.get("enabled") else ""}> '
                f'{esc(t["task_enabled"])}</label>'
                f'<p class="files-meta">{esc(t["task_run_as_root"])}</p>'
                f'<div><button type="submit" class="files-button">{esc(t["task_save"])}</button>'
                + (f' <a class="files-button" href="/tasks">{esc(t["task_cancel"])}</a>' if editing else '')
                + '</div></form></section>')
        body = (f'<h1>{esc(t["tasks"])}</h1><div class="frp-workspace files-page">{"".join(messages)}'
                f'{listing}{form}</div><script src="/static/backup.js" defer></script>')
        return self.send_html(200, self.render_page(t["tasks"], body, lang, icon="home", back_href="/"),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def route_tasks(self, method, path, parsed, lang, query_lang):
        if not path.startswith("/tasks"):
            return False
        if method == "GET" and path == "/tasks":
            self.page_tasks(lang, query_lang, parsed)
        elif method == "POST" and path == "/tasks/save":
            self.handle_tasks_save()
        elif method == "POST" and path == "/tasks/toggle":
            self.handle_tasks_toggle()
        elif method == "POST" and path == "/tasks/delete":
            self.handle_tasks_delete()
        elif method == "POST" and path == "/tasks/run":
            self.handle_tasks_run()
        else:
            return False
        return True

    def handle_tasks_save(self):
        form = self.tasks_form(FIELDS)
        if form is None or not {"name", "schedule", "command", "timeout"} <= set(form):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        engine = self.context.SCHEDULER
        try:
            timeout = int(form["timeout"])
            notify, enabled = form.get("notify") == "1", form.get("enabled") == "1"
            if form.get("id"):
                if not scheduler.TASK_ID_RE.fullmatch(form["id"]):
                    raise scheduler.ScheduleError("bad id")
                engine.edit_task(form["id"], form["name"], form["schedule"], form["command"], timeout, notify, enabled)
            else:
                engine.add_task(form["name"], form["schedule"], form["command"], timeout, notify, enabled)
        except scheduler.ScheduleError as exc:
            return self.tasks_done(error="limit" if "many" in str(exc) else "invalid")
        except (ValueError, OSError):
            return self.tasks_done(error="invalid")
        return self.tasks_done("saved")

    def tasks_id(self, form):
        if form is None or not scheduler.TASK_ID_RE.fullmatch(form.get("id", "")):
            return None
        return form["id"]

    def handle_tasks_toggle(self):
        form = self.tasks_form(("id", "enabled"))
        task_id = self.tasks_id(form)
        if task_id is None or form.get("enabled") not in ("0", "1"):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        try:
            self.context.SCHEDULER.set_enabled(task_id, form["enabled"] == "1")
        except scheduler.ScheduleError:
            return self.tasks_done(error="not_found")
        return self.tasks_done("toggled")

    def handle_tasks_delete(self):
        form = self.tasks_form(("id",))
        task_id = self.tasks_id(form)
        if task_id is None:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        try:
            self.context.SCHEDULER.delete_task(task_id)
        except scheduler.ScheduleError:
            return self.tasks_done(error="not_found")
        return self.tasks_done("deleted")

    def handle_tasks_run(self):
        form = self.tasks_form(("id",))
        task_id = self.tasks_id(form)
        if task_id is None:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        engine = self.context.SCHEDULER
        if not any(task.get("id") == task_id for task in engine.tasks()):
            return self.tasks_done(error="not_found")
        engine.start_async(engine.run_task, task_id, "manual")
        return self.tasks_done("started")
