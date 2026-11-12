"""Traffic cards for the features metered by traffic_meter.py and app_meter.py.

Each card shows the same usage numbers as a sing-box node and opens the same
limits dialog. Limits of console-metered features (Mini Drive, speed test) are
saved here; the others go to the root helper traffic_meter.py.
"""

import json
from pathlib import Path

TRAFFIC_DIR = Path("/etc/vps-server-traffic")
# Where the limits form returns to, by the page that showed the card.
BACK = {"files": "/files", "speedtest": "/speedtest", "domains": "/domains", "iperf": "/iperf",
        "portfwd": "/portfwd", "frpc": "/frpc", "tailscale": "/tailscale"}
LIMIT_FORM = {"id", "csrf", "cap_gib", "upload_mbps", "download_mbps", "cap_action", "expiry_mode",
              "expiry_count", "expiry_unit", "reset_mode", "reset_count", "reset_unit", "next_reset_at"}
APP_KEYS = ("files", "speedtest")


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
    def traffic_csrf(self):
        return self.context.access_csrf_token(self.get_cookie("session"), "traffic:limits")

    def traffic_card(self, t, key, back, *, card=True):
        """Usage and the limits dialog for one metered feature; "" until it is metered."""
        esc = self.context.html.escape
        if key in APP_KEYS:
            try:
                entry = self.context.APP_METER.entry(key)
            except Exception:
                return ""
            # Counted by this process: nothing is ever unobserved.
            ledger = {entry["id"]: {"samples": {}, "suspect": False}}
        else:
            entries, ledger = kernel_entries()
            if key.startswith("frpc:"):
                # FRPC instances are counted per server (see traffic_meter.py).
                try:
                    from traffic_meter import frpc_server_key
                    key = frpc_server_key(key[5:]) or key
                except Exception:
                    return ""
            entry = entries.get(key)
            if entry is None:
                return ""
        identifier = entry["id"]
        t = {**t, "node_limit_manage": t["traffic_limit_manage"]}  # Not access, only traffic, here.
        query = self.context.parse_qs(self.context.urlsplit(self.path).query)
        notice = ""
        if query.get("traffic", [""])[0] in ("done", "failed") and query.get("entry", [""])[0] == identifier:
            done = query["traffic"][0] == "done"
            notice = (f'<p class="{"notice" if done else "error"}" role="status">'
                      f'{esc(t["node_settings_done" if done else "node_settings_failed"])}</p>')
        script = ""
        if not getattr(self, "_traffic_script_added", False):
            self._traffic_script_added = True
            script = '<script src="/static/node-controls.js"></script>'
        shared = ""
        if key.startswith("frpcsrv:") and ", " in entry["name"]:
            shared = f'<p class="muted traffic-help">{esc(t["traffic_frpc_shared"].format(names=entry["name"]))}</p>'
        help_key = ("traffic_help_tailscale" if key == "tailscale" else
                    "traffic_help_twice" if entry.get("billable_multiplier", 2) == 2 else "traffic_help_once")
        body = (f'{notice}{self.node_metrics(entry, ledger, t)}'
                f'<p class="muted traffic-help">{esc(t[help_key])}</p>{shared}'
                f'<div class="node-secondary"><button type="button" class="node-action node-access-open" '
                f'data-dialog-open="node-access-{identifier}">{esc(t["node_limit_manage"])}</button></div>'
                f'{self.node_limits_dialog(entry, identifier, self.traffic_csrf(), "/traffic/limits?back=" + back, t)}'
                f'{script}')
        return f'<section class="card frp-card traffic-card">{body}</section>' if card else \
            f'<div class="traffic-card">{body}</div>'

    def handle_traffic_limits(self, parsed):
        back = self.context.parse_qs(parsed.query).get("back", [""])[0]
        if back not in BACK:
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = 0
        if not 0 < length <= 4096 or \
                self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/x-www-form-urlencoded":
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        try:
            form = self.context.parse_qs(self.rfile.read(length).decode("utf-8"),
                                         strict_parsing=True, keep_blank_values=True)
        except (UnicodeError, ValueError):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if set(form) != LIMIT_FORM or any(len(values) != 1 for values in form.values()):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if not self.context.hmac.compare_digest(form["csrf"][0], self.traffic_csrf()):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        identifier = form["id"][0]
        app_entry = next((entry for entry in self.context.APP_METER.state()["nodes"]
                          if entry["id"] == identifier), None)
        kernel = None if app_entry else next(
            (entry for entry in kernel_entries()[0].values() if entry["id"] == identifier), None)
        done = False
        try:
            existing = app_entry or kernel
            if existing is None:
                raise ValueError("unknown traffic entry")
            request = self.node_limits_request(form, existing)
            if app_entry:
                self.context.APP_METER.edit(identifier, request)
                done = True
            else:
                done = self.traffic_meter_apply({"action": "edit", "id": identifier, **request})
        except (ValueError, self.context.InvalidOperation, OverflowError, KeyError,
                self.context.InvalidInventory, TypeError, OSError):
            done = False
        state = "done" if done else "failed"
        return self.redirect(f"{BACK[back]}?traffic={state}&entry={identifier}", {"Cache-Control": "no-store"})

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

    def route_traffic(self, method, path, parsed, lang, query_lang):
        if method == "POST" and path == "/traffic/limits":
            self.handle_traffic_limits(parsed)
            return True
        return False
