"""Schedules in plain words, shared by scheduled tasks and the scheduled backup.

The single-page UI has the form itself; ``scheduler.normalize_spec`` is the only
place that validates what it sends.
"""


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
