"""When a daily, weekly, monthly or yearly schedule falls, in naive local time.

Shared by scheduled tasks (scheduler.py) and the traffic reset schedules (node_inventory.py),
so "every month on the 31st at 03:00" means the same thing in both. Pure: no I/O.
A ``spec`` is scheduler.normalize_spec's form: ``{"mode": "daily" | "weekly" | "monthly" |
"yearly", "time": "HH:MM:SS", "days": [0-6, Sunday is 0], "day": 1-31, "month": 1-12}``.
Monthly and yearly days past the end of a month fall on its last day.
"""

import calendar
from datetime import datetime, timedelta


def seconds_of_day(spec):
    hour, minute, second = (int(part) for part in spec["time"].split(":"))
    return hour * 3600 + minute * 60 + second


def day_matches(spec, day):
    """Whether the spec runs on this date (cron weekday numbering: Sunday is 0)."""
    if spec["mode"] == "daily":
        return True
    if spec["mode"] == "weekly":
        return (day.weekday() + 1) % 7 in spec["days"]
    if spec["mode"] == "yearly" and day.month != spec["month"]:
        return False
    return day.day == min(spec["day"], calendar.monthrange(day.year, day.month)[1])


def previous_occurrence(spec, now):
    """The latest run time at or before ``now``, or None."""
    seconds = seconds_of_day(spec)
    for back in range(0, 400):
        day = (now - timedelta(days=back)).date()
        if day_matches(spec, day):
            moment = datetime(day.year, day.month, day.day) + timedelta(seconds=seconds)
            if moment <= now:
                return moment
    return None


def next_occurrence(spec, after):
    """The first run time strictly after ``after``, or None."""
    seconds = seconds_of_day(spec)
    for ahead in range(0, 400):
        day = (after + timedelta(days=ahead)).date()
        if day_matches(spec, day):
            moment = datetime(day.year, day.month, day.day) + timedelta(seconds=seconds)
            if moment > after:
                return moment
    return None
