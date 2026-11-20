"""Traffic entries for the features metered by traffic_meter.py and app_meter.py, and the host total.

Each card shows the same usage numbers as a sing-box node and opens the same
limits dialog. Limits of console-metered features (Mini Drive, speed test) are
saved here; the others go to the root helper traffic_meter.py.
"""

import json
import threading
from pathlib import Path

TRAFFIC_DIR = Path("/etc/vps-server-traffic")
# Where the limits form returns to, by the page that showed the card.
BACK = {"files": "/files", "speedtest": "/speedtest", "domains": "/domains", "iperf": "/iperf",
        "portfwd": "/portfwd", "frpc": "/frpc", "tailscale": "/tailscale"}
LIMIT_FORM = {"id", "csrf", "cap_gib", "upload_mbps", "download_mbps", "cap_action", "expiry_mode",
              "expiry_count", "expiry_unit", "reset_mode", "reset_count", "reset_unit", "next_reset_at"}
APP_KEYS = ("files", "speedtest")
# total-traffic.json is read, changed and written by request threads and the 30-second check.
TOTAL_LOCK = threading.RLock()


def _read(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def kernel_entries():
    """(entries by key, meter ledger nodes) from the traffic meter, or ({}, {}) before it runs."""
    state = _read(TRAFFIC_DIR / "traffic.json")
    if state is None:
        return {}, {}
    try:
        from traffic_meter import validate
        validate(state)
    except Exception:
        return {}, {}
    ledger = ((_read(TRAFFIC_DIR / "meter.json") or {}).get("ledger") or {}).get("nodes") or {}
    return {entry["key"]: entry for entry in state["nodes"]}, ledger


class TrafficMixin:
    def total_entries(self):
        """Every metered entry the console can read: nodes, FRPS, kernel meters and app meters."""
        context = self.context
        entries = []
        try:
            inventory = context.read_inventory(state_path=context.NODE_STATE_PATH,
                                               config_paths={"proxy": context.PROXY_CONFIG})
            entries += (inventory or {}).get("nodes", [])
        except Exception:
            pass
        try:
            frps = context.frps_traffic_state()
            if frps:
                entries.append({**frps[0], "name": "FRPS"})
        except Exception:
            pass
        entries += list(kernel_entries()[0].values())
        try:
            entries += list(context.APP_METER.state()["nodes"])
        except Exception:
            pass
        return entries

    def total_state(self, now=None, persist=False):
        """(state, usage per entry id, names) with a due period already started and saved.

        Each entry's usage is remembered in the state (total_meter.observe); ``persist`` also
        saves that record, which the 30-second check does, so a deleted or unreadable entry
        keeps counting. Callers that change the state hold TOTAL_LOCK around this and the write.
        """
        import total_meter
        now = now or self.context.datetime.now(self.context.timezone.utc)
        with TOTAL_LOCK:
            info = total_meter.snapshot_full(self.total_entries())
            path = self.context.DATA_DIR / "total-traffic.json"
            state, changed = total_meter.advance(total_meter.read_state(path), info, now)
            state, observed = total_meter.observe(state, info)
            if changed or (observed and persist):
                total_meter.write_state(path, state)
        return state, info

    def total_enforce(self, now=None):
        """Apply the total's cap action and send its alerts; the console calls this every 30 seconds.

        Writes total-limit.json for the meters (see total_meter.py) and notifies at 80% and at the
        cap once per period. Returns the enforced action, or None.
        """
        import total_meter
        context = self.context
        now = now or context.datetime.now(context.timezone.utc)
        with TOTAL_LOCK:
            state, info = self.total_state(now, persist=True)
            measured, _per = total_meter.period_usage(state, total_meter.lifetimes(info))
            used = total_meter.calibrated_total(state, measured)
            action = total_meter.enforced(state, used)
            total_meter.write_limit(context.DATA_DIR, action, state["next_reset_at"] if action else None)
            due = total_meter.due_alerts(state, used)
            if due:
                total_meter.write_state(context.DATA_DIR / "total-traffic.json",
                                        {**state, "alerted": [*state.get("alerted", []), *due]})
        if due:
            top = due[-1]
            text = context._log_text
            values = {"used": total_meter.format_bytes(used), "cap": total_meter.format_bytes(state["cap_bytes"]),
                      "action": text(f"total_action_{total_meter.cap_action(state)}")}
            context.ALERTS.notify_task(text(f"total_alert_{top}_title"), text(f"total_alert_{top}_body", **values))
        return action

    def traffic_entry(self, key):
        """(entry, meter ledger nodes) for one metered feature, or None until it is metered."""
        if key in APP_KEYS:
            try:
                entry = self.context.APP_METER.entry(key)
            except Exception:
                return None
            # Counted by this process: nothing is ever unobserved.
            return entry, {entry["id"]: {"samples": {}, "suspect": False}}
        entries, ledger = kernel_entries()
        if key.startswith("frpc:"):
            # FRPC instances are counted per server (see traffic_meter.py).
            try:
                from traffic_meter import frpc_server_key
                key = frpc_server_key(key[5:]) or key
            except Exception:
                return None
        entry = entries.get(key)
        return None if entry is None else (entry, ledger)


    def traffic_meter_apply(self, request):
        context = self.context
        direct = ["/usr/bin/python3", str(context.WEB_CODE_DIR / "traffic_meter.py"), "apply"]
        command = (["systemd-run", "--pipe", "--wait", "--collect", "--quiet",
                    "--unit=vps-server-traffic-edit.service", *direct]
                   if context.shutil.which("systemd-run") else direct)
        try:
            result = context.subprocess.run(command, input=json.dumps(request).encode("utf-8"),
                                            stdout=context.subprocess.DEVNULL, stderr=context.subprocess.DEVNULL,
                                            timeout=context.NODE_APPLY_TIMEOUT, check=False)
        except (OSError, context.subprocess.TimeoutExpired):
            return False
        return result.returncode == 0
