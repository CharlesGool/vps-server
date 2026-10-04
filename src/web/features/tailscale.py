"""Tailscale operator page. All command execution is allowlisted in tailscale_control."""

import html
import json
import subprocess
from urllib.parse import parse_qs
from urllib.parse import urlsplit

import tailscale_control as control


class TailscaleMixin:
    def page_tailscale(self, lang, query_lang, parsed):
        t = self.context.STRINGS[lang]
        esc = html.escape
        tab = parse_qs(parsed.query).get("tab", ["overview"])[0]
        if tab not in ("overview", "settings", "devices", "logs"):
            tab = "overview"
        installed = "tailscale" in self.context.installed_modules(self.context.BASE_DIR)
        if not installed:
            return self.page_module_not_installed(lang, query_lang, "Tailscale", "Tailscale")
        try:
            snapshot = control.status()
            error = ""
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            snapshot, error = {}, t["tailscale_unavailable"]
        try:
            net = control.netcheck() if tab == "overview" and not error and snapshot.get("BackendState") == "Running" else {}
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            net = {}
        try:
            settings = control.prefs() if tab in ("overview", "settings") and not error else {}
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            settings = {}
        nav = "".join(f'<a href="/tailscale?tab={key}" {"aria-current=page" if tab == key else ""}>{esc(t["tailscale_tab_" + key])}</a>'
                      for key in ("overview", "settings", "devices", "logs"))
        state = snapshot.get("BackendState", "Stopped")
        self_info = snapshot.get("Self") or {}
        addresses = self_info.get("TailscaleIPs") or []
        tailnet = snapshot.get("CurrentTailnet") or {}
        user = (snapshot.get("User") or {}).get(str(self_info.get("UserID")), {})
        headline = (f'<div class="tailscale-head"><div><h1>Tailscale</h1><p class="muted">{esc(t["tailscale_state"])}: '
                    f'<strong>{esc(str(state))}</strong></p></div>'
                    f'<form method="post" action="/tailscale/action">'
                    f'<input type="hidden" name="csrf" value="{self.context.access_csrf_token(self.get_cookie("session"), "tailscale:restart")}">'
                    f'<input type="hidden" name="action" value="restart"><button type="submit">{esc(t["tailscale_restart"])}</button></form></div>')
        content = f'<p role="status" class="error">{esc(error)}</p>' if error else ""
        if tab == "overview":
            details = (("tailscale_control_server", tailnet.get("Name") or "—"),
                       ("tailscale_version", snapshot.get("Version") or "—"),
                       ("tailscale_ipv4", next((ip for ip in addresses if ":" not in ip), "")),
                       ("tailscale_ipv6", next((ip for ip in addresses if ":" in ip), "")),
                       ("tailscale_account", user.get("LoginName", "")),
                       ("tailscale_public_endpoint", net.get("GlobalV4") or ""))
            facts = "".join(f'<div class="tailscale-fact"><span>{esc(t[key])}</span><strong>' +
                            (self.private_value_control("tailscale-" + key, "address", t, endpoint="/tailscale/private-value")
                             if key in ("tailscale_ipv4", "tailscale_ipv6", "tailscale_account", "tailscale_public_endpoint") and value else esc(str(value or "—"))) + '</strong></div>'
                            for key, value in details)
            auth_url = snapshot.get("AuthURL") or ""
            if state != "Running":
                token = self.context.access_csrf_token(self.get_cookie("session"), "tailscale:connect")
                content += (f'<form method="post" action="/tailscale/action"><input type="hidden" name="action" value="connect">'
                            f'<input type="hidden" name="csrf" value="{token}">'
                            f'<label>{esc(t["tailscale_login_server"])}<input name="login_server" type="url" placeholder="https://controlplane.tailscale.com" maxlength="255"></label>'
                            f'<label class="password-field">{esc(t["tailscale_auth_key"])}<input name="auth_key" type="password" autocomplete="off" maxlength="2048">'
                            f'<button type="button" class="password-toggle" aria-pressed="false" data-show-label="{esc(t["login_show_password"], quote=True)}" '
                            f'data-hide-label="{esc(t["login_hide_password"], quote=True)}" data-show-accessible="{esc(t["login_show_password"], quote=True)}" '
                            f'data-hide-accessible="{esc(t["login_hide_password"], quote=True)}">{esc(t["login_show_password"])}</button></label>'
                            f'<button type="submit">{esc(t["tailscale_connect"])}</button></form>')
            parsed_auth = urlsplit(auth_url)
            if parsed_auth.scheme == "https" and parsed_auth.hostname and not parsed_auth.username and not parsed_auth.password:
                content += f'<p><a href="{esc(auth_url, quote=True)}" target="_blank" rel="noopener noreferrer">{esc(t["tailscale_authorize"])}</a></p>'
            if state == "Running" and addresses and settings.get("webclient") is True:
                content += (f'<p><button type="button" class="tailscale-web-open" '
                            f'data-error="{esc(t["tailscale_web_open_failed"], quote=True)}">'
                            f'{esc(t["tailscale_open_web"])}</button>'
                            '<span class="error tailscale-web-status" role="status" hidden></span></p>')
            checks = (("IPv4", net.get("IPv4")), ("IPv6", net.get("IPv6")),
                      ("UDP", net.get("UDP")), ("UPnP", net.get("UPnP")),
                      ("PCP", net.get("PCP")), ("NAT-PMP", net.get("PMP")))
            badges = "".join(f'<span class="tailscale-check" data-ok="{str(value is True).lower()}">{esc(name)}: '
                             f'{esc(t["tailscale_yes"] if value is True else t["tailscale_no"] if value is False else "—")}</span>'
                             for name, value in checks)
            content += (f'<div class="tailscale-facts">{facts}</div><h2>{esc(t["tailscale_connectivity"])}</h2>'
                        f'<p>{esc(t["tailscale_derp"])}: {esc(str(net.get("PreferredDERP") or "—"))}</p>'
                        f'<div class="tailscale-checks">{badges}</div>')
        elif tab == "settings":
            choices = (("accept-dns", "tailscale_accept_dns", "RouteAll"),
                       ("accept-routes", "tailscale_accept_routes", "RouteAll"),
                       ("advertise-exit-node", "tailscale_advertise_exit", "AdvertiseExitNode"),
                       ("exit-node-allow-lan-access", "tailscale_exit_lan", "ExitNodeAllowLANAccess"),
                       ("shields-up", "tailscale_shields", "ShieldsUp"),
                       ("snat-subnet-routes", "tailscale_snat", "NoSNAT"),
                       ("ssh", "tailscale_ssh", "RunSSH"),
                       ("webclient", "tailscale_webclient", "RunWebClient"))
            # `tailscale get --json` uses CLI flag names. An unknown value stays
            # unselected instead of implying that an option is disabled.
            for name, label, _ in choices:
                value = settings.get(name)
                checked = 'checked' if value is True else ''
                disabled = 'disabled' if type(value) is not bool or name == "webclient" and state != "Running" else ''
                token = self.context.access_csrf_token(self.get_cookie("session"), "tailscale:set:" + name)
                content += (f'<form method="post" action="/tailscale/action" class="tailscale-setting">'
                            f'<label><input type="checkbox" name="enabled" value="1" {checked} {disabled}>'
                            f'{esc(t[label])}</label><input type="hidden" name="action" value="set">'
                            f'<input type="hidden" name="name" value="{name}"><input type="hidden" name="csrf" value="{token}">'
                            f'<button type="submit" {disabled}>{esc(t["frp_save"])}</button></form>')
            for kind, label, current in (("routes", "tailscale_routes", settings.get("advertise-routes", "")),
                                         ("exit", "tailscale_exit_node", settings.get("exit-node", "")),
                                         ("relay", "tailscale_peer_relay", settings.get("relay-server-port", ""))):
                token = self.context.access_csrf_token(self.get_cookie("session"), "tailscale:" + kind)
                current_html = (f'<span>{esc(t["tailscale_current"])}: '
                                f'{self.private_value_control("tailscale-setting-" + kind, "value", t, endpoint="/tailscale/private-value")}</span>'
                                if current else "")
                clear_token = self.context.access_csrf_token(self.get_cookie("session"), "tailscale:" + kind + "-clear")
                field = ('<input name="value" type="number" min="1" max="65535" required>' if kind == "relay" else
                         '<input name="value" value="" maxlength="255" required>')
                content += (f'<form method="post" action="/tailscale/action" class="tailscale-setting">'
                            f'<label>{esc(t[label])}{field}</label>{current_html}'
                            f'<input type="hidden" name="action" value="{kind}"><input type="hidden" name="csrf" value="{token}">'
                            f'<button type="submit">{esc(t["frp_save"])}</button></form>'
                            f'<form method="post" action="/tailscale/action" class="tailscale-clear">'
                            f'<input type="hidden" name="action" value="{kind}-clear"><input type="hidden" name="csrf" value="{clear_token}">'
                            f'<button type="submit" {"" if current else "disabled"}>{esc(t["tailscale_clear"])}</button></form>')
        elif tab == "devices":
            devices = control.peers(snapshot)
            content += f'<h2>{esc(t["tailscale_devices"])} ({len(devices)})</h2>'
            if not devices:
                content += f'<p class="muted">{esc(t["tailscale_no_devices"])}</p>'
            else:
                rows = "".join(f'<tr><td>{esc(p["name"])}</td><td>{esc(t["tailscale_online"] if p["online"] else t["tailscale_offline"])}</td>'
                               f'<td>{self.private_value_control("tailscale-peer-" + p["id"], "address", t, endpoint="/tailscale/private-value") if p["addresses"] and p["id"] else "—"}</td>'
                               f'<td>{esc(p["os"])}</td><td>{esc(p["relay"] or "—")}</td>'
                               f'<td>{p["rx"]:,} / {p["tx"]:,}</td><td>{esc(p["last_seen"] or "—")}</td></tr>'
                               for p in devices)
                content += (f'<div class="tailscale-table"><table><thead><tr>'
                            + "".join(f'<th scope="col">{esc(t[key])}</th>' for key in
                                      ("tailscale_device", "tailscale_state", "tailscale_address", "tailscale_os", "tailscale_relay", "tailscale_rx_tx", "tailscale_last_seen"))
                            + f'</tr></thead><tbody>{rows}</tbody></table></div>')
        else:
            try:
                result = subprocess.run(["journalctl", "--no-pager", "-o", "short-iso", "-n", "500", "-u", control.UNIT],
                                        capture_output=True, text=True, timeout=15, check=False)
                output = result.stdout if result.returncode == 0 else t["logs_unavailable"]
            except (OSError, subprocess.TimeoutExpired):
                output = t["logs_unavailable"]
            content += f'<pre class="logs-output" role="log">{esc(output or t["logs_empty"])}</pre>'
        body = (f'<div class="card wide tailscale-page">{headline}<nav class="log-sources" aria-label="Tailscale">{nav}</nav>'
                f'{content}</div><script src="/static/copy.js"></script><script src="/static/private-values.js"></script>'
                '<script src="/static/password-fields.js"></script><script src="/static/tailscale.js" defer></script>')
        self.send_html(200, self.render_page("Tailscale", body, lang, back_href="/"),
                       {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def tailscale_action(self, lang):
        t = self.context.STRINGS[lang]
        if "tailscale" not in self.context.installed_modules(self.context.BASE_DIR):
            return self.send_html(404, "Not found")
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/x-www-form-urlencoded":
            return self.send_html(400, "Invalid request")
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 < length <= 8192:
                raise ValueError
            form = parse_qs(self.rfile.read(length).decode("utf-8"), strict_parsing=True,
                            keep_blank_values=True)
        except (UnicodeError, ValueError):
            return self.send_html(400, "Invalid request")
        action = form.get("action", [""])[0]
        name = form.get("name", [""])[0]
        allowed = {"set": {"action", "name", "enabled", "csrf"}, "routes": {"action", "value", "csrf"},
                   "exit": {"action", "value", "csrf"}, "routes-clear": {"action", "csrf"},
                   "exit-clear": {"action", "csrf"}, "relay": {"action", "value", "csrf"},
                   "relay-clear": {"action", "csrf"}, "restart": {"action", "csrf"},
                   "connect": {"action", "csrf", "login_server", "auth_key"}}
        if action not in allowed or set(form) - allowed[action] or any(len(v) != 1 for v in form.values()):
            return self.send_html(400, "Invalid request")
        if action == "set" and name not in control.BOOL_SETTINGS:
            return self.send_html(400, "Invalid request")
        if action == "set" and form.get("enabled", ["1"]) != ["1"]:
            return self.send_html(400, "Invalid request")
        subject = "tailscale:" + ("set:" + name if action == "set" else action)
        expected = self.context.access_csrf_token(self.get_cookie("session"), subject)
        if not self.context.hmac.compare_digest(form.get("csrf", [""])[0], expected):
            return self.send_html(403, "Forbidden")
        try:
            if action == "set":
                enabled = form.get("enabled") == ["1"]
                reserved = False
                if name == "webclient" and enabled:
                    if control.status().get("BackendState") != "Running":
                        raise ValueError("Tailscale is not connected")
                    reserved = self.context.reserve_owned_port(self.context.BASE_DIR, 5252,
                                                               "vps-server Tailscale Web")
                try:
                    control.set_bool(name, enabled)
                except BaseException:
                    if reserved:
                        self.context.release_owned_port(self.context.BASE_DIR, 5252,
                                                        "vps-server Tailscale Web")
                    raise
                if name == "webclient" and not enabled:
                    self.context.release_owned_port(self.context.BASE_DIR, 5252,
                                                    "vps-server Tailscale Web")
                if name == "webclient":
                    self.context.snapshot_tailscale_ports()
            elif action == "routes":
                control.set_routes(form.get("value", [""])[0])
            elif action == "exit":
                control.set_exit_node(form.get("value", [""])[0])
            elif action == "routes-clear":
                control.set_routes("")
            elif action == "exit-clear":
                control.set_exit_node("")
            elif action in ("relay", "relay-clear"):
                previous = str(control.prefs().get("relay-server-port") or "")
                wanted = form.get("value", [""])[0] if action == "relay" else ""
                if wanted:
                    if control.status().get("BackendState") != "Running":
                        raise ValueError("Tailscale is not connected")
                    if not wanted.isascii() or not wanted.isdecimal() or not 1 <= int(wanted) <= 65535:
                        raise ValueError("invalid peer relay port")
                reserved = self.context.reserve_owned_port(self.context.BASE_DIR, int(wanted),
                                                            "vps-server Tailscale Relay") if wanted else False
                try:
                    control.set_relay_port(wanted)
                except BaseException:
                    if reserved:
                        self.context.release_owned_port(self.context.BASE_DIR, int(wanted),
                                                        "vps-server Tailscale Relay")
                    raise
                if previous and previous != wanted:
                    self.context.release_owned_port(self.context.BASE_DIR, int(previous),
                                                    "vps-server Tailscale Relay")
                self.context.snapshot_tailscale_ports()
            elif action == "connect":
                try:
                    control.connect(form.get("login_server", [""])[0], form.get("auth_key", [""])[0])
                except RuntimeError:
                    # A login URL can be issued while `up` waits for browser approval.
                    if not control.status().get("AuthURL"):
                        raise
            else:
                subprocess.run(["systemctl", "restart", control.UNIT], check=True, timeout=60)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            return self.send_html(400, self.render_page("Tailscale", f'<div class="card"><p class="error">{html.escape(t["tailscale_action_failed"])}</p></div>', lang, back_href="/tailscale"))
        self.redirect("/tailscale?tab=" + ("settings" if action in ("set", "routes", "exit", "routes-clear", "exit-clear", "relay", "relay-clear") else "overview"), {"Cache-Control": "no-store"})

    def route_tailscale(self, method, path, parsed, lang, query_lang):
        if method == "GET" and path == "/tailscale":
            self.page_tailscale(lang, query_lang, parsed)
        elif method == "POST" and path == "/tailscale/action":
            self.tailscale_action(lang)
        elif method == "GET" and path == "/tailscale/private-value":
            query = parse_qs(parsed.query)
            identifier = query.get("id", [""])[0]
            settings_value = identifier in ("tailscale-setting-routes", "tailscale-setting-exit", "tailscale-setting-relay") and query.get("field") == ["value"]
            address_value = query.get("field") == ["address"] and (identifier in ("tailscale-tailscale_ipv4", "tailscale-tailscale_ipv6", "tailscale-tailscale_account", "tailscale-tailscale_public_endpoint")
                                                               or identifier.startswith("tailscale-peer-"))
            if not (settings_value or address_value):
                return self.send_html(400, "Invalid request") or True
            try:
                snapshot = control.status()
                if settings_value:
                    preferences = control.prefs()
                    value = preferences["advertise-routes" if identifier.endswith("routes") else
                                        "relay-server-port" if identifier.endswith("relay") else "exit-node"]
                elif identifier == "tailscale-tailscale_account":
                    self_info = snapshot.get("Self") or {}
                    value = (snapshot.get("User") or {})[str(self_info.get("UserID"))]["LoginName"]
                elif identifier == "tailscale-tailscale_public_endpoint":
                    value = control.netcheck()["GlobalV4"]
                elif identifier.startswith("tailscale-peer-"):
                    peer = next(p for p in control.peers(snapshot) if p["id"] == identifier[len("tailscale-peer-"):])
                    value = ", ".join(peer["addresses"])
                else:
                    ips = (snapshot.get("Self") or {}).get("TailscaleIPs") or []
                    value = next(ip for ip in ips if (":" in ip) == identifier.endswith("ipv6"))
            except (OSError, ValueError, RuntimeError, StopIteration, KeyError, TypeError, subprocess.TimeoutExpired):
                return self.send_html(404, "Not found") or True
            data = json.dumps({"value": value}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            return False
        return True
