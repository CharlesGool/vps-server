"""JSON API for resource usage (home page cards and /monitor) and its alert settings."""

import time

import sysmon

# History is shown as 12 two-hour buckets (the chart) and 24 hourly ones (the card trend lines).
CHART_BUCKETS = 12
TREND_BUCKETS = 24


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
        snapshot["live"] = monitor.live_points()
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
        return self.api_ok({"alerts": settings["alerts"], "barkReady": bool(self.context.ALERTS.keys)})

    def api_monitor_alerts_save(self):
        body = self.read_json()
        alerts = sysmon.clamp_alerts(body.get("alerts") if body else None)
        if alerts is None:
            return self.api_error(400, "invalid_request")
        self.context.MONITOR.save_alerts(alerts)
        self.audit("monitor_alerts_saved")
        return self.api_monitor_alerts()
