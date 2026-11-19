"""Host resource usage: CPU, memory, disks, load, network, temperatures and GPUs.

Everything comes from /proc, /sys and statvfs, so no package is needed; GPU
figures appear only when ``nvidia-smi`` exists. A sampler thread keeps the
current CPU and network rates (every 5 seconds), a 24-hour history (one point
a minute, saved to ``data/monitor-history.json``) and checks the alert
thresholds kept in ``data/monitor.json``.
"""

import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

try:
    from . import secure_store
except ImportError:  # Installed helpers are copied into one flat directory.
    import secure_store

HISTORY_POINTS = 1440
# The live chart: the last minute, one point per sample.
LIVE_POINTS = 12
SAMPLE_SECONDS = 5
HISTORY_SECONDS = 60
# File systems that hold data; pseudo and in-memory ones are left out.
DISK_TYPES = {"ext2", "ext3", "ext4", "xfs", "btrfs", "zfs", "f2fs", "vfat", "exfat", "ntfs", "ntfs3",
              "jfs", "reiserfs", "nfs", "nfs4", "cifs", "smb3", "fuseblk", "fuse.sshfs"}
DEFAULT_ALERTS = {"enabled": True, "disk": 90, "memory": 95, "cpu": 95, "cpu_minutes": 10, "services": True,
                  "gpu_temp": 85, "gpu_memory": 95}
LIMITS = {"disk": (50, 99), "memory": (50, 99), "cpu": (50, 100), "cpu_minutes": (1, 120),
          "gpu_temp": (50, 110), "gpu_memory": (50, 99)}


def _read(path):
    try:
        return Path(path).read_text()
    except OSError:
        return ""


def cpu_times():
    """(busy, total) jiffies over all CPUs."""
    line = _read("/proc/stat").splitlines()[:1]
    if not line or not line[0].startswith("cpu "):
        return None
    values = [int(value) for value in line[0].split()[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    total = sum(values[:8])
    return total - idle, total


def cpu_count():
    return os.cpu_count() or 1


def cpu_model():
    for line in _read("/proc/cpuinfo").splitlines():
        if line.lower().startswith(("model name", "hardware")):
            return line.split(":", 1)[1].strip()
    return ""


def memory():
    info = {}
    for line in _read("/proc/meminfo").splitlines():
        name, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            info[name] = int(parts[0]) * 1024
    total = info.get("MemTotal", 0)
    available = info.get("MemAvailable", info.get("MemFree", 0))
    swap_total = info.get("SwapTotal", 0)
    swap_free = info.get("SwapFree", 0)
    return {"total": total, "used": max(total - available, 0), "available": available,
            "swapTotal": swap_total, "swapUsed": max(swap_total - swap_free, 0)}


def disks():
    """Mounted data file systems, one row per device."""
    rows, seen = [], set()
    for line in _read("/proc/mounts").splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[2] not in DISK_TYPES:
            continue
        device, mount = parts[0], parts[1].replace("\\040", " ")
        if device in seen:
            continue
        try:
            stat = os.statvfs(mount)
        except OSError:
            continue
        total = stat.f_blocks * stat.f_frsize
        if total <= 0:
            continue
        seen.add(device)
        free = stat.f_bavail * stat.f_frsize
        used = total - stat.f_bfree * stat.f_frsize
        rows.append({"mount": mount, "device": device, "type": parts[2], "total": total, "used": used,
                     "free": free, "percent": round(used * 100 / (used + free), 1) if used + free else 0})
    rows.sort(key=lambda row: (row["mount"] != "/", row["mount"]))
    return rows


def load_average():
    values = _read("/proc/loadavg").split()[:3]
    try:
        return [float(value) for value in values]
    except ValueError:
        return [0.0, 0.0, 0.0]


def uptime_seconds():
    try:
        return int(float(_read("/proc/uptime").split()[0]))
    except (IndexError, ValueError):
        return 0


def net_counters():
    """{interface: (rx_bytes, tx_bytes)} without loopback."""
    counters = {}
    for line in _read("/proc/net/dev").splitlines()[2:]:
        name, _, rest = line.partition(":")
        name = name.strip()
        values = rest.split()
        if name == "lo" or len(values) < 9:
            continue
        counters[name] = (int(values[0]), int(values[8]))
    return counters


def temperatures():
    """Sensor readings in °C from hwmon, else thermal zones; empty on most VPS."""
    rows = []
    for hwmon in sorted(Path("/sys/class/hwmon").glob("hwmon*")):
        chip = _read(hwmon / "name").strip() or hwmon.name
        for sensor in sorted(hwmon.glob("temp*_input")):
            try:
                value = int(_read(sensor).strip()) / 1000
            except ValueError:
                continue
            label = _read(hwmon / sensor.name.replace("_input", "_label")).strip()
            if -40 < value < 150:
                rows.append({"name": f"{chip} {label}".strip(), "celsius": round(value, 1)})
    if not rows:
        for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
            try:
                value = int(_read(zone / "temp").strip()) / 1000
            except ValueError:
                continue
            if -40 < value < 150:
                rows.append({"name": _read(zone / "type").strip() or zone.name, "celsius": round(value, 1)})
    return rows[:16]


def gpus():
    """NVIDIA GPUs through nvidia-smi; empty when it is not installed."""
    binary = shutil.which("nvidia-smi")
    if not binary:
        return []
    try:
        output = subprocess.run([binary, "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                                 "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5,
                                check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    rows = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 5:
            continue

        def number(text):
            try:
                return float(text)
            except ValueError:
                return None
        used, total = number(parts[2]), number(parts[3])
        rows.append({"name": parts[0], "utilization": number(parts[1]),
                     "memoryUsed": int(used * 1048576) if used is not None else None,
                     "memoryTotal": int(total * 1048576) if total is not None else None,
                     "celsius": number(parts[4])})
    return rows


def clamp_alerts(value):
    """Validated alert settings, or None when ``value`` is not acceptable."""
    if not isinstance(value, dict):
        return None
    result = dict(DEFAULT_ALERTS)
    for key in ("enabled", "services"):
        if key in value:
            if not isinstance(value[key], bool):
                return None
            result[key] = value[key]
    for key, (low, high) in LIMITS.items():
        if key in value:
            number = value[key]
            if isinstance(number, bool) or not isinstance(number, int) or not low <= number <= high:
                return None
            result[key] = number
    return result


class Monitor:
    """The sampler, its history and the alert checks."""

    def __init__(self, data_dir, notify=None, failed_units=None, texts=None, active=None):
        self.data_dir = Path(data_dir)
        self.history_path = self.data_dir / "monitor-history.json"
        self.settings_path = self.data_dir / "monitor.json"
        self.notify = notify
        # The home switch: closed, the sampler keeps running (cheap) but sends no alerts.
        self.active = active or (lambda: True)
        self.failed_units = failed_units
        self.texts = texts or (lambda key, **values: key)
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.current = {"cpu": 0.0, "rx": 0, "tx": 0, "interfaces": {}, "gpus": []}
        self.history = []
        self.live = []
        # GPUs (only with nvidia-smi): [time, [[utilization %, memory %, °C] per GPU]], same cadence as above
        self.gpu_live = []
        self.gpu_history = []
        self.cpu_high_since = None
        self._last_cpu = cpu_times()
        self._last_net = (time.monotonic(), net_counters())
        self._load_history()

    # -- state ---------------------------------------------------------------

    def _load_history(self):
        try:
            data = json.loads(secure_store.read_text(self.history_path))
        except (OSError, ValueError):
            return
        points = data.get("points") if isinstance(data, dict) else None
        if isinstance(points, list):
            cutoff = time.time() - HISTORY_POINTS * HISTORY_SECONDS
            self.history = [point for point in points if isinstance(point, list) and len(point) == 5
                            and point[0] >= cutoff][-HISTORY_POINTS:]
        gpu = data.get("gpu") if isinstance(data, dict) else None
        if isinstance(gpu, list):
            cutoff = time.time() - HISTORY_POINTS * HISTORY_SECONDS
            self.gpu_history = [point for point in gpu if isinstance(point, list) and len(point) == 2
                                and isinstance(point[1], list) and point[0] >= cutoff][-HISTORY_POINTS:]

    def _save_history(self):
        try:
            secure_store.write_text(self.history_path, json.dumps({"points": self.history, "gpu": self.gpu_history},
                                                                    separators=(",", ":")))
        except (OSError, ValueError):
            pass

    def settings(self):
        try:
            data = json.loads(secure_store.read_text(self.settings_path))
        except (OSError, ValueError):
            data = {}
        alerts = clamp_alerts(data.get("alerts", {}) if isinstance(data, dict) else {}) or dict(DEFAULT_ALERTS)
        return {"alerts": alerts, "sent": data.get("sent", {}) if isinstance(data, dict) else {}}

    def _write_settings(self, data):
        secure_store.write_text(self.settings_path, json.dumps(data, ensure_ascii=False, indent=2))

    def save_alerts(self, alerts):
        with self.lock:
            data = self.settings()
            data["alerts"] = alerts
            self._write_settings(data)

    # -- sampling ------------------------------------------------------------

    @staticmethod
    def gpu_point(rows):
        """[[utilization %, memory %, °C] per GPU] from gpus() rows; unknown values are 0."""
        return [[row["utilization"] or 0,
                 round(row["memoryUsed"] * 100 / row["memoryTotal"], 1) if row["memoryTotal"] and row["memoryUsed"] is not None else 0,
                 row["celsius"] or 0] for row in rows]

    def sample(self):
        """Update the current CPU, network and GPU figures."""
        cards = gpus()
        busy_total = cpu_times()
        now = time.monotonic()
        counters = net_counters()
        with self.lock:
            if busy_total and self._last_cpu:
                busy = busy_total[0] - self._last_cpu[0]
                total = busy_total[1] - self._last_cpu[1]
                if total > 0:
                    self.current["cpu"] = round(max(0.0, min(100.0, busy * 100 / total)), 1)
            self._last_cpu = busy_total
            then, previous = self._last_net
            elapsed = now - then
            if elapsed > 0:
                rates = {}
                for name, (rx, tx) in counters.items():
                    if name in previous:
                        rates[name] = (max(rx - previous[name][0], 0) / elapsed, max(tx - previous[name][1], 0) / elapsed)
                self.current["interfaces"] = {name: {"rx": int(rx), "tx": int(tx)} for name, (rx, tx) in rates.items()}
                self.current["rx"] = int(sum(rx for rx, _ in rates.values()))
                self.current["tx"] = int(sum(tx for _, tx in rates.values()))
            self._last_net = (now, counters)
            mem = memory()
            self.live.append([int(time.time()), self.current["cpu"],
                              round(mem["used"] * 100 / mem["total"], 1) if mem["total"] else 0,
                              self.current["rx"], self.current["tx"]])
            self.live = self.live[-LIVE_POINTS:]
            self.current["gpus"] = cards
            if cards:
                self.gpu_live.append([int(time.time()), self.gpu_point(cards)])
                self.gpu_live = self.gpu_live[-LIVE_POINTS:]

    def snapshot(self):
        """Everything the page shows."""
        mem = memory()
        rows = disks()
        with self.lock:
            current = dict(self.current)
        root = next((row for row in rows if row["mount"] == "/"), rows[0] if rows else None)
        return {"cpu": {"percent": current["cpu"], "cores": cpu_count(), "model": cpu_model()},
                "memory": mem, "disks": rows, "disk": root, "load": load_average(), "uptime": uptime_seconds(),
                "network": {"rx": current["rx"], "tx": current["tx"],
                            "interfaces": [{"name": name, **rates}
                                           for name, rates in sorted(current["interfaces"].items())]},
                "temperatures": temperatures(), "gpus": current["gpus"], "time": int(time.time())}

    def record(self):
        """Append one history point: [time, cpu %, memory %, rx B/s, tx B/s]."""
        mem = memory()
        with self.lock:
            point = [int(time.time()), self.current["cpu"],
                     round(mem["used"] * 100 / mem["total"], 1) if mem["total"] else 0,
                     self.current["rx"], self.current["tx"]]
            self.history.append(point)
            self.history = self.history[-HISTORY_POINTS:]
            if self.current["gpus"]:
                self.gpu_history.append([point[0], self.gpu_point(self.current["gpus"])])
                self.gpu_history = self.gpu_history[-HISTORY_POINTS:]
        return point

    def live_points(self):
        """The last minute: [time, cpu %, memory %, rx B/s, tx B/s] every SAMPLE_SECONDS."""
        with self.lock:
            return list(self.live)

    def points(self):
        with self.lock:
            return list(self.history)

    def gpu_points(self):
        """(live points, per-minute points) for the GPUs."""
        with self.lock:
            return list(self.gpu_live), list(self.gpu_history)

    # -- alerts ---------------------------------------------------------------

    def _alert(self, data, key, title, body, now):
        """Send once per key a day; True when sent."""
        sent = data.setdefault("sent", {})
        if now - sent.get(key, 0) < 86400:
            return False
        sent[key] = now
        if self.notify:
            self.notify(title, body)
        return True

    def check_alerts(self, snapshot=None):
        """Compare the latest figures with the thresholds; return the keys alerted."""
        with self.lock:
            data = self.settings()
        alerts = data["alerts"]
        if not alerts["enabled"]:
            return []
        snapshot = snapshot or self.snapshot()
        now = time.time()
        fired = []
        t = self.texts
        for row in snapshot["disks"]:
            if row["percent"] >= alerts["disk"] and self._alert(
                    data, "disk:" + row["mount"], t("monitor_alert_disk_title"),
                    t("monitor_alert_disk_body", mount=row["mount"], percent=row["percent"]), now):
                fired.append("disk:" + row["mount"])
        mem = snapshot["memory"]
        percent = mem["used"] * 100 / mem["total"] if mem["total"] else 0
        if percent >= alerts["memory"] and self._alert(
                data, "memory", t("monitor_alert_memory_title"),
                t("monitor_alert_memory_body", percent=round(percent, 1)), now):
            fired.append("memory")
        cpu = snapshot["cpu"]["percent"]
        if cpu >= alerts["cpu"]:
            self.cpu_high_since = self.cpu_high_since or now
            if now - self.cpu_high_since >= alerts["cpu_minutes"] * 60 and self._alert(
                    data, "cpu", t("monitor_alert_cpu_title"),
                    t("monitor_alert_cpu_body", percent=cpu, minutes=alerts["cpu_minutes"]), now):
                fired.append("cpu")
        else:
            self.cpu_high_since = None
        for index, card in enumerate(snapshot.get("gpus") or []):
            name = card.get("name") or f"GPU {index}"
            if card.get("celsius") is not None and card["celsius"] >= alerts["gpu_temp"] and self._alert(
                    data, f"gpu-temp:{index}", t("monitor_alert_gpu_temp_title"),
                    t("monitor_alert_gpu_temp_body", name=name, celsius=card["celsius"]), now):
                fired.append(f"gpu-temp:{index}")
            if card.get("memoryTotal") and card.get("memoryUsed") is not None:
                used = round(card["memoryUsed"] * 100 / card["memoryTotal"], 1)
                if used >= alerts["gpu_memory"] and self._alert(
                        data, f"gpu-memory:{index}", t("monitor_alert_gpu_memory_title"),
                        t("monitor_alert_gpu_memory_body", name=name, percent=used), now):
                    fired.append(f"gpu-memory:{index}")
        if alerts["services"] and self.failed_units:
            for unit in self.failed_units():
                if self._alert(data, "unit:" + unit, t("monitor_alert_service_title"),
                               t("monitor_alert_service_body", unit=unit), now):
                    fired.append("unit:" + unit)
        if fired:
            data["sent"] = {key: value for key, value in data.get("sent", {}).items() if now - value < 86400 * 2}
            with self.lock:
                try:
                    self._write_settings(data)
                except (OSError, ValueError):
                    pass
        return fired

    # -- thread ---------------------------------------------------------------

    def run(self):
        last_point = 0.0
        last_save = time.monotonic()
        while not self.stop_event.wait(SAMPLE_SECONDS):
            try:
                self.sample()
                now = time.monotonic()
                if now - last_point >= HISTORY_SECONDS:
                    last_point = now
                    self.record()
                    if self.active():
                        self.check_alerts()
                if now - last_save >= 600:
                    last_save = now
                    self._save_history()
            except Exception as error:  # noqa: BLE001 - the sampler must never die
                print(f"monitor: {error}", flush=True)
        self._save_history()

    def start(self):
        threading.Thread(target=self.run, name="monitor", daemon=True).start()

    def stop(self):
        self.stop_event.set()
        self._save_history()
