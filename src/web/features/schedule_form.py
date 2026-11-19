"""The "when to run" form shared by scheduled tasks and the scheduled backup.

One way to say it, everywhere. First the kind: repeating, or only once. A repeating schedule
is every so often, every day, every week, every month, or a cron expression; then which day(s)
and the time of day down to the second. A one-time schedule is a date and a time. Pages render
``fields_html`` inside their own form and read it back with ``spec_from_form``;
``scheduler.normalize_spec`` is the only place that validates the result.
"""

import json
import time

import scheduler

DAY_FIELDS = tuple(f"day_{i}" for i in range(7))
FORM_FIELDS = ("kind", "mode", "n", "unit", "time", "date", "month_day", "expr") + DAY_FIELDS
# Monday first, Sunday last, as people read a week.
WEEK_ORDER = (1, 2, 3, 4, 5, 6, 0)
# Which parts of the form each mode needs (``once`` is a kind of its own, the rest are repeating).
PARTS = {"frequency": ("interval", "daily", "weekly", "monthly", "cron"), "interval": ("interval",),
         "weekly": ("weekly",), "monthly": ("monthly",), "time": ("daily", "weekly", "monthly", "once"),
         "date": ("once",), "cron": ("cron",)}


def clock_text(value):
    """``12:30:10`` as given; ``12:30:00`` shortened to ``12:30``."""
    return value[:-3] if value.endswith(":00") else value


def describe(t, spec):
    """A schedule in plain words; a cron expression is shown as it is."""
    mode = spec["mode"]
    if mode == "once":
        return t["task_describe_once"].format(date=spec["date"], time=clock_text(spec["time"]))
    if mode == "interval":
        return t["task_describe_interval"].format(n=spec["n"], unit=t["task_unit_" + spec["unit"]])
    if mode == "daily":
        return t["task_describe_daily"].format(time=clock_text(spec["time"]))
    if mode == "weekly":
        days = t["task_days_sep"].join(t["task_day_" + str(d)] for d in sorted(spec["days"], key=lambda d: (d - 1) % 7))
        return t["task_describe_weekly"].format(days=days, time=clock_text(spec["time"]))
    if mode == "monthly":
        return t["task_describe_monthly"].format(day=spec["day"], time=clock_text(spec["time"]))
    if mode == "yearly":
        return t["task_describe_yearly"].format(month=spec["month"], day=spec["day"], time=clock_text(spec["time"]))
    return spec["expr"]


def spec_from_form(form):
    """The schedule a submitted form describes (not yet validated); ScheduleError for an unknown kind or mode."""
    kind = form.get("kind")
    if kind == "once":
        return {"mode": "once", "date": form.get("date"), "time": form.get("time")}
    if kind != "recurring":
        raise scheduler.ScheduleError("invalid kind")
    mode = form.get("mode")
    if mode == "interval":
        return {"mode": mode, "n": form.get("n"), "unit": form.get("unit")}
    if mode == "daily":
        return {"mode": mode, "time": form.get("time")}
    if mode == "weekly":
        return {"mode": mode, "time": form.get("time"), "days": [i for i in range(7) if form.get(f"day_{i}") == "1"]}
    if mode == "monthly":
        try:
            day = int(form.get("month_day", ""))
        except ValueError:
            day = 0
        return {"mode": mode, "time": form.get("time"), "day": day}
    if mode == "cron":
        return {"mode": mode, "expr": form.get("expr", "")}
    raise scheduler.ScheduleError("invalid mode")


def fields_html(context, t, spec):
    """A fieldset holding every part of the schedule; ``backup.js`` shows the parts the choice needs."""
    esc = context.html.escape
    mode = spec["mode"]
    kind = "once" if mode == "once" else "recurring"
    shown_mode = mode if mode != "once" else "daily"
    every = spec if mode == "interval" else {"n": 30, "unit": "minutes"}
    at = spec.get("time", "03:00:00")
    chosen = spec.get("days", [1]) if mode == "weekly" else [1]
    month_day = spec.get("day", 1) if mode == "monthly" else 1
    expr = spec.get("expr", "0 3 * * *") if mode == "cron" else "0 3 * * *"
    date = spec.get("date", time.strftime("%Y-%m-%d", time.localtime(time.time() + 3600)))
    labels = esc(json.dumps({key: t["ctl_" + key] for key in ("hour", "minute", "second", "year", "month", "day", "calendar",
                                                              "previous", "next")}, ensure_ascii=False), quote=True)

    def part(name, body):
        modes = PARTS[name]
        visible = mode in modes
        return (f'<div class="sched-mode is-wide" data-modes="{" ".join(modes)}"{"" if visible else " hidden"}>{body}</div>')

    kinds = "".join(f'<option value="{k}"{" selected" if k == kind else ""}>{esc(t["task_kind_" + k])}</option>'
                    for k in ("recurring", "once"))
    modes_html = "".join(f'<option value="{m}"{" selected" if m == shown_mode else ""}>{esc(t["task_mode_" + m])}</option>'
                         for m in scheduler.RECURRING)
    units = "".join(f'<option value="{u}"{" selected" if u == every["unit"] else ""}>{esc(t["task_unit_" + u])}</option>'
                    for u in scheduler.UNIT_SECONDS)
    days = "".join(f'<label class="sched-check"><input type="checkbox" name="day_{i}" value="1"{" checked" if i in chosen else ""}>'
                   f'<span>{esc(t["task_dayfull_" + str(i)])}</span></label>' for i in WEEK_ORDER)
    return (
        f'<fieldset class="sched-schedule is-wide"><legend>{esc(t["schedule_title"])}</legend>'
        f'<label class="sched-field"><span>{esc(t["task_kind"])}</span>'
        f'<select name="kind" class="sched-kind-select">{kinds}</select></label>'
        + part("frequency", f'<label class="sched-field"><span>{esc(t["task_mode"])}</span>'
               f'<select name="mode" class="sched-mode-select">{modes_html}</select></label>')
        + part("interval", f'<div class="sched-inline"><span>{esc(t["task_every"])}</span>'
               f'<input type="number" name="n" min="1" max="9999" value="{every["n"]}" aria-label="{esc(t["task_every"], quote=True)}">'
               f'<select name="unit" aria-label="{esc(t["task_unit"], quote=True)}">{units}</select></div>')
        + part("weekly", f'<div class="sched-field"><span>{esc(t["task_weekdays"])}</span><div class="sched-days">{days}</div></div>')
        + part("monthly", f'<label class="sched-field"><span>{esc(t["task_month_day"])}</span>'
               f'<input type="number" name="month_day" min="1" max="28" value="{month_day}">'
               f'<small class="muted">{esc(t["task_month_day_help"])}</small></label>')
        + part("date", f'<label class="sched-field"><span>{esc(t["task_date"])}</span>'
               f'<input type="date" name="date" value="{esc(date, quote=True)}" min="{time.strftime("%Y-%m-%d")}" data-labels="{labels}"></label>')
        + part("time", f'<label class="sched-field"><span>{esc(t["task_time"])}</span>'
               f'<input type="time" name="time" step="1" value="{esc(at, quote=True)}" data-labels="{labels}">'
               f'<small class="muted">{esc(t["task_time_help"])}</small></label>')
        + part("cron", f'<label class="sched-field"><span>{esc(t["task_schedule"])}</span>'
               f'<input type="text" name="expr" value="{esc(expr, quote=True)}" maxlength="100" spellcheck="false" class="is-mono">'
               f'<small class="muted">{esc(t["task_schedule_help"])}</small></label>')
        + f'<p class="muted small">{esc(t["task_timezone"])}: {esc(time.tzname[0])}</p></fieldset>')
