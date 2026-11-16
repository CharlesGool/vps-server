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

    def total_state(self, now=None):
        """(state, usage per entry id, names) with a due period already started and saved."""
        import total_meter
        now = now or self.context.datetime.now(self.context.timezone.utc)
        info = total_meter.snapshot_full(self.total_entries())
        path = self.context.DATA_DIR / "total-traffic.json"
        state, changed = total_meter.advance(total_meter.read_state(path), info, now)
        if changed:
            total_meter.write_state(path, state)
        return state, info

    def total_meter_bar(self, t):
        """The whole-host traffic bar for the top of the home page; "" if it cannot be computed."""
        import total_meter
        esc = self.context.html.escape
        try:
            state, info = self.total_state()
        except (OSError, ValueError, TypeError):
            return ""
        measured, per_entry = total_meter.period_usage(state, total_meter.lifetimes(info))
        offset = total_meter.calibration(state)
        used = total_meter.calibrated_total(state, measured)
        state_level = total_meter.level(state, used)
        cap = state["cap_bytes"]
        percent = 0 if cap is None else min(100, used * 100 // cap)
        fmt = total_meter.format_bytes
        figure = (f'<strong>{esc(fmt(used))}</strong><span>/ {esc(fmt(cap))} ({used * 100 / cap:.1f}%)</span>' if cap is not None
                  else f'<strong>{esc(fmt(used))}</strong><span>{esc(t["total_no_cap"])}</span>')
        since = state["period_start"][:10]
        reset = (t["total_next_reset"].format(date=state["next_reset_at"][:10]) if state["next_reset_at"]
                 else t["total_no_reset"])
        warning = {"over": t["total_over"], "warn": t["total_warn"]}.get(state_level, "")
        warning = f'<p class="error" role="status">{esc(warning)}</p>' if warning else ""
        query = self.context.parse_qs(self.context.urlsplit(self.path).query).get("total", [""])[0]
        notice = (f'<p class="{"notice" if query == "done" else "error"}" role="status">'
                  f'{esc(t["node_settings_done" if query == "done" else "node_settings_failed"])}</p>'
                  if query in ("done", "failed") else "")
        # Each source gets a bar like the total: its share of the cap, or of the total without a cap.
        basis = cap if cap is not None else used
        rows = []
        for identifier, value in sorted(per_entry.items(), key=lambda item: -item[1]):
            if not value:
                continue
            share = value * 100 / basis if basis else 0
            width = min(100, max(1, round(share)))
            multiplier = info[identifier]["multiplier"]
            # Each page counts raw bytes; the total counts what is billed, so say how the two relate.
            raw = f'{esc(fmt(value // multiplier))} × {multiplier} = ' if multiplier != 1 else ""
            rows.append(
                f'<li class="source-row"><div class="source-row-head"><span class="source-row-name">{esc(info[identifier]["name"])}</span>'
                f'<span class="source-row-value">{raw}<strong>{esc(fmt(value))}</strong> · {share:.1f}%</span></div>'
                f'<div class="meter is-thin" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{width}" '
                f'aria-label="{esc(info[identifier]["name"], quote=True)}"><span style="width:{width}%"></span></div></li>')
        if offset:
            # The operator's calibration is its own row and bar, signed, so it is never mistaken for counted traffic.
            share = abs(offset) * 100 / basis if basis else 0
            width = min(100, max(1, round(share)))
            sign = "+" if offset > 0 else "\u2212"
            label = t["total_calibration_row"].format(date=(state.get("calibrated_at") or "")[:10])
            rows.append(
                f'<li class="source-row"><div class="source-row-head"><span class="source-row-name">{esc(label)}</span>'
                f'<span class="source-row-value"><strong>{sign}{esc(fmt(abs(offset)))}</strong> · {share:.1f}%</span></div>'
                f'<div class="meter is-thin" data-sign="{"positive" if offset > 0 else "negative"}" role="progressbar" '
                f'aria-valuemin="0" aria-valuemax="100" aria-valuenow="{width}" aria-label="{esc(label, quote=True)}">'
                f'<span style="width:{width}%"></span></div></li>')
        breakdown = (f'<div class="source-box"><h3>{esc(t["total_by_source"])}</h3>'
                     f'<p class="total-meter-meta">{esc(t["total_multiplier_note"])}</p>'
                     f'<ul class="source-list">{"".join(rows)}</ul></div>' if rows else "")
        cap_value = "" if cap is None else f'{cap / 1073741824:g}'
        calibrate = (
            f'<dialog class="node-access-dialog" id="total-meter-calibrate" aria-labelledby="total-meter-calibrate-title">'
            f'<form method="post" action="/traffic/total/calibrate">'
            f'<input type="hidden" name="csrf" value="{self.context.access_csrf_token(self.get_cookie("session"), "traffic:calibrate")}">'
            f'<h3 id="total-meter-calibrate-title">{esc(t["total_calibrate_title"])}</h3><div class="node-form-grid">'
            f'<label>{esc(t["total_actual_gib"])}<input type="number" name="actual_gib" min="0" max="100000000" step="any" '
            f'value="{"" if not offset else f"{used / 1073741824:g}"}"></label></div>'
            f'<p class="muted small">{esc(t["total_calibrate_measured"].format(value=fmt(measured)))}</p>'
            f'<p class="muted small">{esc(t["total_calibrate_hint"])}</p>'
            f'<div class="node-dialog-actions"><button type="button" class="node-dialog-cancel" data-dialog-close>{esc(t["node_cancel"])}</button>'
            f'<button type="submit">{esc(t["total_calibrate_save"])}</button></div></form></dialog>')
        dialog = (
            f'<dialog class="node-access-dialog" id="total-meter-settings" aria-labelledby="total-meter-title">'
            f'<form method="post" action="/traffic/total">'
            f'<input type="hidden" name="csrf" value="{self.context.access_csrf_token(self.get_cookie("session"), "traffic:total")}">'
            f'<h3 id="total-meter-title">{esc(t["total_settings"])}</h3><div class="node-form-grid">'
            f'<label>{esc(t["total_cap_gib"])}<input type="number" name="cap_gib" min="0.000001" max="100000000" step="any" '
            f'value="{cap_value}" placeholder="{esc(t["node_unlimited"], quote=True)}"></label>'
            f'<label>{esc(t["total_reset_day"])}<input type="number" name="reset_day" min="0" max="28" value="{state["reset_day"]}"></label>'
            f'</div><p class="muted small">{esc(t["total_hint"])}</p>'
            f'<div class="node-dialog-actions"><button type="button" class="node-dialog-cancel" data-dialog-close>{esc(t["node_cancel"])}</button>'
            f'<button type="submit">{esc(t["total_save"])}</button></div></form></dialog>')
        return (f'<section class="card wide total-meter" aria-label="{esc(t["total_title"], quote=True)}">'
                f'<div class="total-meter-head"><h2>{esc(t["total_title"])}</h2>'
                f'<span class="total-meter-buttons">'
                f'<button type="button" class="node-action" data-dialog-open="total-meter-calibrate">{esc(t["total_calibrate"])}</button>'
                f'<button type="button" class="node-action" data-dialog-open="total-meter-settings">{esc(t["total_settings"])}</button></span></div>'
                f'<p class="total-meter-figure">{figure}</p>'
                f'<div class="meter" data-level="{state_level}" role="progressbar" aria-valuemin="0" aria-valuemax="100" '
                f'aria-valuenow="{percent}"><span style="width:{percent}%"></span></div>'
                f'<p class="total-meter-meta">{esc(t["total_since"].format(date=since))} · {esc(reset)}</p>'
                f'{warning}{notice}{breakdown}{dialog}{calibrate}'
                f'<script src="/static/node-controls.js"></script></section>')

    def handle_total_settings(self):
        import total_meter
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = 0
        if not 0 < length <= 1024 or \
                self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/x-www-form-urlencoded":
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        try:
            form = self.context.parse_qs(self.rfile.read(length).decode("utf-8"),
                                         strict_parsing=True, keep_blank_values=True)
        except (UnicodeError, ValueError):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if set(form) != {"csrf", "cap_gib", "reset_day"} or any(len(v) != 1 for v in form.values()):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if not self.context.hmac.compare_digest(
                form["csrf"][0], self.context.access_csrf_token(self.get_cookie("session"), "traffic:total")):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        try:
            cap, day = total_meter.parse_settings(form["cap_gib"][0], form["reset_day"][0])
            now = self.context.datetime.now(self.context.timezone.utc)
            state, info = self.total_state(now)
            total_meter.write_state(self.context.DATA_DIR / "total-traffic.json",
                                    total_meter.apply_settings(state, cap, day, now, info))
            result = "done"
        except (OSError, ValueError, TypeError):
            result = "failed"
        return self.redirect(f"/?total={result}", {"Cache-Control": "no-store"})

    def handle_total_calibrate(self):
        import total_meter
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = 0
        if not 0 < length <= 1024 or \
                self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/x-www-form-urlencoded":
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        try:
            form = self.context.parse_qs(self.rfile.read(length).decode("utf-8"),
                                         strict_parsing=True, keep_blank_values=True)
        except (UnicodeError, ValueError):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if set(form) != {"csrf", "actual_gib"} or any(len(v) != 1 for v in form.values()):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if not self.context.hmac.compare_digest(
                form["csrf"][0], self.context.access_csrf_token(self.get_cookie("session"), "traffic:calibrate")):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        try:
            actual = total_meter.parse_actual(form["actual_gib"][0])
            now = self.context.datetime.now(self.context.timezone.utc)
            state, info = self.total_state(now)
            measured, _per = total_meter.period_usage(state, total_meter.lifetimes(info))
            total_meter.write_state(self.context.DATA_DIR / "total-traffic.json",
                                    total_meter.apply_calibration(state, actual, measured, now))
            result = "done"
        except (OSError, ValueError, TypeError):
            result = "failed"
        return self.redirect(f"/?total={result}", {"Cache-Control": "no-store"})

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
        if method == "POST" and path == "/traffic/total":
            self.handle_total_settings()
            return True
        if method == "POST" and path == "/traffic/total/calibrate":
            self.handle_total_calibrate()
            return True
        return False
