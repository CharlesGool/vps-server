"""Scheduled tasks page: list, add, edit, run now, history.

Host dependencies come from ``ConsoleHandler.context``; the scheduler itself
lives in ``scheduler.py``.
"""

import time

import scheduler
from features import schedule_form
from features.backup import local_time

NOTICES = ("saved", "deleted", "started", "toggled")
ERRORS = ("invalid", "not_found", "limit", "past")
FIELDS = ("id", "name", "command", "timeout", "notify", "enabled") + schedule_form.FORM_FIELDS


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

        tones = {"ok": "success", "failed": "danger", "timeout": "warning", "skipped": ""}

        def status_tag(entry):
            if not entry:
                return f'<span class="tag">{esc(t["task_never"])}</span>'
            return f'<span class="tag" data-tone="{tones[entry["status"]]}">{esc(t["task_status_" + entry["status"]])}</span>'

        def last_line(entry):
            return (f'<span>{esc(t["task_last"])}: {esc(local_time(entry["started"]))}</span>' if entry else "")

        def history(task_id):
            runs = engine.runs(task_id)
            if not runs:
                return ""
            lines = []
            for entry in runs:
                exit_text = f'<span>{esc(t["task_exit"])} {entry["exit"]}</span>' if entry.get("exit") is not None else ""
                output = f'<pre class="sched-output">{esc(entry["output"])}</pre>' if entry.get("output") else ""
                lines.append(
                    f'<li class="sched-run"><div class="sched-run-head">{status_tag(entry)}'
                    f'<span>{esc(local_time(entry["started"]))}</span>{exit_text}'
                    f'<span>{esc(t["task_trigger_" + entry.get("trigger", "schedule")])}</span></div>{output}</li>')
            return (f'<details class="sched-runs"><summary>{esc(t["task_history"])} ({len(runs)})</summary>'
                    f'<ul class="sched-run-list">{"".join(lines)}</ul></details>')

        def when_html(task):
            spec = scheduler.task_spec(task)
            if spec is None:
                return ""
            text = esc(schedule_form.describe(t, spec))
            return f'<code class="sched-code">{text}</code>' if spec["mode"] == "cron" else f'<span class="sched-when">{text}</span>'

        items = []
        backup_settings = engine.backup_settings()
        following = engine.next_backup()
        items.append(
            f'<li class="sched-item"><div class="sched-item-main"><div class="sched-item-title">'
            f'<span>{esc(t["task_builtin_backup"])}</span><span class="tag" data-tone="primary">{esc(t["task_builtin"])}</span>'
            f'{status_tag(engine.last_run("backup"))}'
            + ('' if backup_settings["enabled"] else f'<span class="tag">{esc(t["task_disabled"])}</span>')
            + f'</div><div class="sched-item-meta">'
            + (f'<span class="sched-when">{esc(schedule_form.describe(t, backup_settings["spec"]))}</span>'
               if backup_settings["enabled"] else '')
            + (f'<span>{esc(t["task_next"])}: {esc(local_time(following))}</span>' if following else '')
            + f'{last_line(engine.last_run("backup"))}</div>{history("backup")}</div>'
            f'<div class="sched-item-actions"><a class="files-button" href="/backup">{esc(t["task_open"])}</a></div></li>')
        for task in tasks:
            task_id = esc(task["id"], quote=True)
            enabled = bool(task.get("enabled"))
            next_stamp = engine.next_for(task) if enabled else None
            run = engine.last_run(task["id"])
            switch_label = esc(task["name"] + " " + (t["task_disable"] if enabled else t["task_enable"]), quote=True)
            items.append(
                f'<li class="sched-item"><div class="sched-item-main"><div class="sched-item-title">'
                f'<span>{esc(task["name"])}</span>{status_tag(run)}'
                + (f'<span class="tag" data-tone="{"success" if task.get("done") == "ran" else "warning"}">{esc(t["task_done_" + task["done"]])}</span>'
                   if task.get("done") in ("ran", "missed") else '' if enabled else f'<span class="tag">{esc(t["task_disabled"])}</span>')
                + f'</div><div class="sched-item-meta">{when_html(task)}'
                + (f'<span>{esc(t["task_next"])}: {esc(local_time(next_stamp))}</span>' if next_stamp else '')
                + f'{last_line(run)}</div>'
                f'<pre class="sched-command">{esc(task["command"])}</pre>{history(task["id"])}</div>'
                f'<div class="sched-item-actions">'
                f'<form method="post" action="/tasks/toggle">{hidden}<input type="hidden" name="id" value="{task_id}">'
                f'<input type="hidden" name="enabled" value="{0 if enabled else 1}">'
                f'<button type="submit" class="motion-switch" role="switch" aria-label="{switch_label}" '
                f'aria-checked="{str(enabled).lower()}"><span aria-hidden="true"></span></button></form>'
                f'<form method="post" action="/tasks/run">{hidden}<input type="hidden" name="id" value="{task_id}">'
                f'<button type="submit" class="files-button">{esc(t["task_run"])}</button></form>'
                f'<a class="files-button" href="/tasks?edit={task_id}#task-form">{esc(t["task_edit"])}</a>'
                f'<form method="post" action="/tasks/delete" class="backup-confirm" '
                f'data-confirm="{esc(t["task_delete_confirm"].format(name=task["name"]), quote=True)}">{hidden}'
                f'<input type="hidden" name="id" value="{task_id}">'
                f'<button type="submit" class="files-button files-danger">{esc(t["task_delete"])}</button></form>'
                f'</div></li>')
        listing = (f'<section class="card wide sched-card">'
                   f'<ul class="sched-list">{"".join(items)}</ul></section>')

        value = editing or {"name": "", "command": "", "timeout": scheduler.TIMEOUT_DEFAULT,
                            "notify": True, "enabled": True}
        spec = (scheduler.task_spec(editing) if editing else None) or {"mode": "daily", "time": "03:00:00"}
        form = (f'<details class="card wide task-form-card" id="task-form"{" open" if editing else ""}>'
                f'<summary>{esc(t["task_edit_heading"] if editing else t["task_add"])}</summary>'
                f'<form method="post" action="/tasks/save" class="task-form">{hidden}'
                + (f'<input type="hidden" name="id" value="{esc(editing["id"], quote=True)}">' if editing else '')
                + f'<label class="sched-field is-wide"><span>{esc(t["task_name"])}</span>'
                f'<input type="text" name="name" maxlength="{scheduler.NAME_MAX}" value="{esc(value["name"], quote=True)}" required></label>'
                + schedule_form.fields_html(self.context, t, spec)
                + f'<label class="sched-field is-wide"><span>{esc(t["task_command"])}</span>'
                f'<textarea name="command" rows="4" maxlength="{scheduler.COMMAND_MAX}" spellcheck="false" required>'
                f'{esc(value["command"])}</textarea></label>'
                f'<label class="sched-field"><span>{esc(t["task_timeout"])}</span>'
                f'<input type="number" name="timeout" min="{scheduler.TIMEOUT_MIN}" max="{scheduler.TIMEOUT_MAX}" '
                f'value="{value["timeout"]}" required></label>'
                f'<div class="task-form-checks">'
                f'<label class="sched-check"><input type="checkbox" name="notify" value="1"{" checked" if value.get("notify") else ""}>'
                f'<span>{esc(t["task_notify"])}</span></label>'
                f'<label class="sched-check"><input type="checkbox" name="enabled" value="1"{" checked" if value.get("enabled") else ""}>'
                f'<span>{esc(t["task_enabled"])}</span></label></div>'
                f'<p class="muted small is-wide" style="margin:0">{esc(t["task_run_as_root"])}</p>'
                f'<div class="task-form-actions is-wide"><button type="submit">{esc(t["task_save"])}</button>'
                + (f'<a class="files-button" href="/tasks">{esc(t["task_cancel"])}</a>' if editing else '')
                + '</div></form></details>')
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
        if form is None or not {"name", "kind", "command", "timeout"} <= set(form):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        engine = self.context.SCHEDULER
        try:
            timeout = int(form["timeout"])
            notify, enabled = form.get("notify") == "1", form.get("enabled") == "1"
            spec = schedule_form.spec_from_form(form)
            if form.get("id"):
                if not scheduler.TASK_ID_RE.fullmatch(form["id"]):
                    raise scheduler.ScheduleError("bad id")
                engine.edit_task(form["id"], form["name"], spec, form["command"], timeout, notify, enabled)
            else:
                engine.add_task(form["name"], spec, form["command"], timeout, notify, enabled)
        except scheduler.ScheduleError as exc:
            return self.tasks_done(error="limit" if "many" in str(exc) else "past" if "passed" in str(exc) else "invalid")
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
        except scheduler.ScheduleError as exc:
            return self.tasks_done(error="past" if "passed" in str(exc) else "not_found")
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
