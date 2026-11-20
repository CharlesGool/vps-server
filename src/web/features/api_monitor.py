"""JSON API for resource usage (home page cards and /monitor) and its alert settings."""

import time

import sysmon


def alerts_problem(value):
    """{"field", "reason"} for the alert setting sysmon.clamp_alerts refuses, or {}."""
    if not isinstance(value, dict):
        return {"field": "alerts", "reason": "required" if value is None else "type"}
    for key in ("enabled", "services"):
        if key in value and not isinstance(value[key], bool):
            return {"field": "alerts." + key, "reason": "type"}
    for key, (low, high) in sysmon.LIMITS.items():
        number = value.get(key, low)
        if isinstance(number, bool) or not isinstance(number, int):
            return {"field": "alerts." + key, "reason": "type"}
        if not low <= number <= high:
            return {"field": "alerts." + key, "reason": "range"}
    return {}

# History is shown as the last 15 minutes, one point a minute (the monitor page's charts and card
# lines); the token API also gives 24 hours as 12 two-hour and 24 hourly averages.
RECENT_BUCKETS = 15
CHART_BUCKETS = 12
TREND_BUCKETS = 24


def gpu_buckets(points, count, span, now=None):
    """Average [time, [[util, mem %, °C] per GPU]] points into ``count`` slots ending now.

    Each slot is [start time, [[util, mem %, °C] per GPU] or None when no point fell in it].
    """
    now = int(now if now is not None else time.time())
    width = span // count
    start = now - width * count
    slots = [[] for _ in range(count)]
    for point in points:
        index = (point[0] - start) // width
        if 0 <= index < count:
            slots[index].append(point[1])
    rows = []
    for index, samples in enumerate(slots):
        cards = min((len(sample) for sample in samples), default=0)
        average = [[round(sum(sample[card][column] for sample in samples) / len(samples), 1) for column in range(3)]
                   for card in range(cards)] if samples else None
        rows.append([start + index * width, average])
    return rows


def buckets(points, count, span=86400, now=None):
    """Average [time, cpu, memory, rx, tx] points into ``count`` equal slots ending now.

    Each slot is (start time, cpu, memory, rx, tx), with None where no point fell in it.
    """
    now = int(now if now is not None else time.time())
    width = span // count
    start = now - width * count
    sums = [[0.0, 0.0, 0.0, 0.0, 0] for _ in range(count)]
    for point in points:
        index = (point[0] - start) // width
        if 0 <= index < count:
            slot = sums[index]
            for column in range(4):
                slot[column] += point[column + 1]
            slot[4] += 1
    rows = []
    for index, (cpu, memory, rx, tx, seen) in enumerate(sums):
        when = start + index * width
        rows.append([when] + ([round(cpu / seen, 1), round(memory / seen, 1), int(rx / seen), int(tx / seen)]
                              if seen else [None, None, None, None]))
    return rows


class MonitorApiMixin:
    API_ROUTES_MONITOR = {
        ("GET", "monitor"): "api_monitor",
        ("GET", "monitor/summary"): "api_monitor_summary",
        ("GET", "monitor/alerts"): "api_monitor_alerts",
        ("PUT", "monitor/alerts"): "api_monitor_alerts_save",
    }

    def monitor_summary(self):
        """Current figures plus the 24-hour history the pages draw."""
        monitor = self.context.MONITOR
        snapshot = monitor.snapshot()
        points = monitor.points()
        snapshot["chart"] = buckets(points, CHART_BUCKETS)
        snapshot["trend"] = buckets(points, TREND_BUCKETS)
        snapshot["recent"] = buckets(points, RECENT_BUCKETS, span=RECENT_BUCKETS * 60)
        snapshot["live"] = monitor.live_points()
        gpu_live, gpu_history = monitor.gpu_points()
        snapshot["gpuLive"] = gpu_live
        snapshot["gpuRecent"] = gpu_buckets(gpu_history, RECENT_BUCKETS, RECENT_BUCKETS * 60)
        hour_ago = next((point for point in reversed(points) if point[0] <= time.time() - 3600), None)
        snapshot["hourAgo"] = {"cpu": hour_ago[1], "memory": hour_ago[2]} if hour_ago else None
        return snapshot

    def api_monitor(self):
        return self.api_ok(self.monitor_summary())

    def api_monitor_summary(self):
        """The home page's four cards, polled every few seconds."""
        return self.api_ok(self.dashboard_resources())

    def api_monitor_alerts(self):
        settings = self.context.MONITOR.settings()
        return self.api_ok({"alerts": settings["alerts"], "barkReady": bool(self.context.ALERTS.keys),
                            "hasGpu": bool(self.context.MONITOR.current.get("gpus"))})

    def api_monitor_alerts_save(self):
        body = self.read_json()
        alerts = sysmon.clamp_alerts(body.get("alerts") if body else None)
        if alerts is None:
            return self.api_error(400, "invalid_request", **(alerts_problem(body.get("alerts")) if body else {}))
        self.context.MONITOR.save_alerts(alerts)
        self.audit("monitor_alerts_saved")
        return self.api_monitor_alerts()
