"""Scheduled tasks page: list, add, edit, run now, history.

Host dependencies come from ``ConsoleHandler.context``; the scheduler itself
lives in ``scheduler.py``.
"""

import time

import scheduler
from features.backup import local_time

NOTICES = ("saved", "deleted", "started", "toggled")
ERRORS = ("invalid", "not_found", "limit")
DAY_FIELDS = tuple(f"day_{i}" for i in range(7))
FIELDS = ("id", "name", "mode", "n", "unit", "time", "month_day", "expr", "command", "timeout", "notify",
          "enabled") + DAY_FIELDS


def describe_spec(t, spec):
    """A schedule in plain words; a cron expression is shown as it is."""
    mode = spec["mode"]
    if mode == "interval":
        return t["task_describe_interval"].format(n=spec["n"], unit=t["task_unit_" + spec["unit"]])
    if mode == "daily":
        return t["task_describe_daily"].format(time=spec["time"])
    if mode == "weekly":
        # Monday first, Sunday last
        days = t["task_days_sep"].join(t["task_day_" + str(d)] for d in sorted(spec["days"], key=lambda d: (d - 1) % 7))
        return t["task_describe_weekly"].format(days=days, time=spec["time"])
    if mode == "monthly":
        return t["task_describe_monthly"].format(day=spec["day"], time=spec["time"])
    return spec["expr"]


def spec_from_form(form):
    """The schedule a submitted form describes (not yet validated); ScheduleError when the mode is unknown."""
    mode = form.get("mode")
    if mode == "interval":
        return {"mode": mode, "n": form.get("n"), "unit": form.get("unit")}
    if mode == "daily":
        return {"mode": mode, "time": form.get("time")}
    if mode == "weekly":
        return {"mode": mode, "time": form.get("time"),
                "days": [i for i in range(7) if form.get(f"day_{i}") == "1"]}
    if mode == "monthly":
        try:
            day = int(form.get("month_day", ""))
        except ValueError:
            day = 0
        return {"mode": mode, "time": form.get("time"), "day": day}
    if mode == "cron":
        return {"mode": mode, "expr": form.get("expr", "")}
    raise scheduler.ScheduleError("invalid mode")


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
            text = esc(describe_spec(t, spec))
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
            + (f'<span class="sched-when">{esc(describe_spec(t, {"mode": "daily", "time": backup_settings["time"]}))}</span>'
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
                + ('' if enabled else f'<span class="tag">{esc(t["task_disabled"])}</span>')
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
        spec = (scheduler.task_spec(editing) if editing else None) or {"mode": "daily", "time": "03:00"}
        mode = spec["mode"]
        every = spec if mode == "interval" else {"n": 30, "unit": "minutes"}
        at = spec.get("time", "03:00")
        chosen_days = spec.get("days", [1]) if mode == "weekly" else [1]
        month_day = spec.get("day", 1) if mode == "monthly" else 1
        expr = spec.get("expr", "0 3 * * *") if mode == "cron" else "0 3 * * *"

        def group(name, body):
            return (f'<div class="sched-mode is-wide" data-mode="{name}"{"" if mode == name else " hidden"}>{body}</div>')

        mode_options = "".join(
            f'<option value="{m}"{" selected" if m == mode else ""}>{esc(t["task_mode_" + m])}</option>' for m in scheduler.MODES)
        unit_options = "".join(
            f'<option value="{u}"{" selected" if u == every["unit"] else ""}>{esc(t["task_unit_" + u])}</option>'
            for u in scheduler.UNIT_SECONDS)
        day_boxes = "".join(
            f'<label class="sched-check"><input type="checkbox" name="day_{i}" value="1"{" checked" if i in chosen_days else ""}>'
            f'<span>{esc(t["task_day_" + str(i)])}</span></label>' for i in (1, 2, 3, 4, 5, 6, 0))
        time_input = (f'<label class="sched-field"><span>{esc(t["task_time"])}</span>'
                      f'<input type="time" name="time" value="{esc(at, quote=True)}"></label>')
        schedule_groups = (
            group("interval", f'<div class="sched-inline"><span>{esc(t["task_every"])}</span>'
                  f'<input type="number" name="n" min="1" max="9999" value="{every["n"]}" aria-label="{esc(t["task_every"], quote=True)}">'
                  f'<select name="unit" aria-label="{esc(t["task_unit"], quote=True)}">{unit_options}</select></div>')
            + group("daily", time_input)
            + group("weekly", f'<div class="sched-field"><span>{esc(t["task_weekdays"])}</span>'
                    f'<div class="sched-days">{day_boxes}</div></div>')
            + group("monthly", f'<label class="sched-field"><span>{esc(t["task_month_day"])}</span>'
                    f'<input type="number" name="month_day" min="1" max="28" value="{month_day}">'
                    f'<small class="muted">{esc(t["task_month_day_help"])}</small></label>')
            + group("cron", f'<label class="sched-field"><span>{esc(t["task_schedule"])}</span>'
                    f'<input type="text" name="expr" value="{esc(expr, quote=True)}" maxlength="100" spellcheck="false" class="is-mono">'
                    f'<small class="muted">{esc(t["task_schedule_help"])}</small></label>'))
        form = (f'<details class="card wide task-form-card" id="task-form"{" open" if editing else ""}>'
                f'<summary>{esc(t["task_edit_heading"] if editing else t["task_add"])}</summary>'
                f'<form method="post" action="/tasks/save" class="task-form">{hidden}'
                + (f'<input type="hidden" name="id" value="{esc(editing["id"], quote=True)}">' if editing else '')
                + f'<label class="sched-field is-wide"><span>{esc(t["task_name"])}</span>'
                f'<input type="text" name="name" maxlength="{scheduler.NAME_MAX}" value="{esc(value["name"], quote=True)}" required></label>'
                f'<label class="sched-field is-wide"><span>{esc(t["task_mode"])}</span>'
                f'<select name="mode" id="task-mode">{mode_options}</select></label>'
                f'{schedule_groups}'
                f'<p class="muted small is-wide" style="margin:0">{esc(t["task_timezone"])}: {esc(time.tzname[0])}</p>'
                f'<label class="sched-field is-wide"><span>{esc(t["task_command"])}</span>'
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
        if form is None or not {"name", "mode", "command", "timeout"} <= set(form):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        engine = self.context.SCHEDULER
        try:
            timeout = int(form["timeout"])
            notify, enabled = form.get("notify") == "1", form.get("enabled") == "1"
            spec = spec_from_form(form)
            if form.get("id"):
                if not scheduler.TASK_ID_RE.fullmatch(form["id"]):
                    raise scheduler.ScheduleError("bad id")
                engine.edit_task(form["id"], form["name"], spec, form["command"], timeout, notify, enabled)
            else:
                engine.add_task(form["name"], spec, form["command"], timeout, notify, enabled)
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
