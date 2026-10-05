"""Tailscale operator page. All command execution is allowlisted in tailscale_control."""

import html
import json
import subprocess
from urllib.parse import parse_qs
from urllib.parse import urlsplit

import tailscale_control as control
from features.modules import LOG_LEVELS, log_clear_form, log_cutoffs, log_level_form, service_log_text


class TailscaleMixin:
    def apply_tailscale_batch(self, form):
        previous = control.prefs()
        state = control.status().get("BackendState")
        changes = {}
        for name in control.BOOL_SETTINGS:
            if form.get("available_" + name) != ["1"]:
                continue
            if type(previous.get(name)) is not bool or name == "webclient" and state != "Running":
                raise ValueError("Tailscale setting unavailable")
            value = form.get("enabled_" + name) == ["1"]
            if value != previous[name]:
                changes[name] = value
        for kind, name in (("routes", "advertise-routes"), ("exit", "exit-node"),
                           ("relay", "relay-server-port")):
            typed = form[kind + "_value"][0].strip()
            clear = form.get(kind + "_clear") == ["1"]
            if typed and clear:
                raise ValueError("conflicting Tailscale setting")
            if not typed and not clear:
                continue
            value = "" if clear else typed
            if name == "advertise-routes":
                value = control.normalize_routes(value)
            elif name == "exit-node":
                value = control.normalize_exit_node(value)
            elif value and (not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 65535):
                raise ValueError("invalid peer relay port")
            if value != str(previous.get(name) or ""):
                changes[name] = value
        if changes.get("webclient") is True or changes.get("relay-server-port"):
            if state != "Running":
                raise ValueError("Tailscale is not connected")
        old_memory = control.memory_mode()
        new_memory = form.get("memory_enabled") == ["1"] if form.get("memory_available") == ["1"] else old_memory
        reserved = []

        def change_memory(enabled):
            unit = "vps-server-tail-memory-" + self.context.secrets.token_hex(6)
            result = subprocess.run(["systemd-run", "--quiet", "--wait", "--pipe", "--collect",
                                     "--unit=" + unit, "/usr/bin/python3",
                                     str(self.context.WEB_CODE_DIR / "tailscale_control.py"),
                                     "memory", "on" if enabled else "off"], capture_output=True, text=True,
                                    check=False, timeout=90)
            if result.returncode:
                raise RuntimeError("Tailscale memory setting failed")

        try:
            if new_memory != old_memory:
                change_memory(new_memory)
            if changes.get("webclient") is True and self.context.reserve_owned_port(
                    self.context.BASE_DIR, 5252, "vps-server Tailscale Web"):
                reserved.append((5252, "vps-server Tailscale Web"))
            relay = changes.get("relay-server-port")
            if relay and self.context.reserve_owned_port(
                    self.context.BASE_DIR, int(relay), "vps-server Tailscale Relay"):
                reserved.append((int(relay), "vps-server Tailscale Relay"))
            if changes:
                control.set_many(changes)
        except BaseException:
            for port, owner in reversed(reserved):
                self.context.release_owned_port(self.context.BASE_DIR, port, owner)
            if new_memory != old_memory:
                change_memory(old_memory)
            raise
        if changes.get("webclient") is False:
            self.context.release_owned_port(self.context.BASE_DIR, 5252, "vps-server Tailscale Web")
        old_relay = str(previous.get("relay-server-port") or "")
        if old_relay and "relay-server-port" in changes and old_relay != changes["relay-server-port"]:
            self.context.release_owned_port(self.context.BASE_DIR, int(old_relay), "vps-server Tailscale Relay")
        if "webclient" in changes or "relay-server-port" in changes:
            self.context.snapshot_tailscale_ports()

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
                       ("tailscale_tun", t["tailscale_yes"] if snapshot.get("TUN") is True else
                        t["tailscale_no"] if snapshot.get("TUN") is False else "—"),
                       ("tailscale_ipv4", next((ip for ip in addresses if ":" not in ip), "")),
                       ("tailscale_ipv6", next((ip for ip in addresses if ":" in ip), "")),
                       ("tailscale_account", user.get("LoginName", "")),
                       ("tailscale_public_endpoint", net.get("GlobalV4") or ""))
            facts = "".join(f'<div class="tailscale-fact"><span>{esc(t[key])}</span><strong>' +
                            (self.private_value_control("tailscale-" + key, "address", t, endpoint="/tailscale/private-value")
                            if key in ("tailscale_control_server", "tailscale_ipv4", "tailscale_ipv6", "tailscale_account", "tailscale_public_endpoint") and value else esc(str(value or "—"))) + '</strong></div>'
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
            checks = ((t["tailscale_varies"], net.get("MappingVariesByDestIP")),
                      ("IPv4", net.get("IPv4")), ("IPv6", net.get("IPv6")),
                      ("UDP", net.get("UDP")), ("UPnP", net.get("UPnP")),
                      ("PCP", net.get("PCP")), ("NAT-PMP", net.get("PMP")),
                      (t["tailscale_hairpinning"], net.get("HairPinning")))
            badges = "".join(f'<span class="tailscale-check" data-ok="{str(value is True).lower()}">{esc(name)}: '
                             f'{esc(t["tailscale_yes"] if value is True else t["tailscale_no"] if value is False else "—")}</span>'
                             for name, value in checks)
            content += (f'<div class="tailscale-facts">{facts}</div><h2>{esc(t["tailscale_connectivity"])}</h2>'
                        f'<p>{esc(t["tailscale_derp"])}: {esc(str(net.get("PreferredDERP") or "—"))}</p>'
                        f'<div class="tailscale-checks">{badges}</div>')
            if state == "Running":
                token = self.context.access_csrf_token(self.get_cookie("session"), "tailscale:logout")
                content += (f'<form method="post" action="/tailscale/action" class="tailscale-logout" data-confirm="{esc(t["tailscale_logout_confirm"], quote=True)}">'
                            f'<input type="hidden" name="action" value="logout"><input type="hidden" name="csrf" value="{token}">'
                            '<input type="hidden" name="confirm" value="yes">'
                            f'<button type="submit" class="danger">{esc(t["tailscale_logout"])}</button></form>')
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
            options_html = ""
            for name, label, _ in choices:
                value = settings.get(name)
                checked = 'checked' if value is True else ''
                disabled = 'disabled' if type(value) is not bool or name == "webclient" and state != "Running" else ''
                options_html += (f'<label class="tailscale-option"><input type="checkbox" name="enabled_{name}" value="1" {checked} {disabled}>'
                                 f'<span>{esc(t[label])}</span></label>'
                                 + (f'<input type="hidden" name="available_{name}" value="1">' if not disabled else ''))
            try:
                memory_enabled = control.memory_mode()
            except (OSError, ValueError):
                memory_enabled = None
            options_html += (f'<label class="tailscale-option"><input type="checkbox" name="memory_enabled" value="1" '
                             f'{"checked" if memory_enabled is True else ""} {"disabled" if memory_enabled is None else ""}>'
                             f'<span>{esc(t["tailscale_memory"])}</span></label>'
                             + ('<input type="hidden" name="memory_available" value="1">' if memory_enabled is not None else ''))
            fields_html = ""
            subnets = control.local_subnets()
            exit_nodes = [peer for peer in control.peers(snapshot) if peer["exit_option"] and peer["selector"]]
            for kind, label, current in (("routes", "tailscale_routes", settings.get("advertise-routes", "")),
                                         ("exit", "tailscale_exit_node", settings.get("exit-node", "")),
                                         ("relay", "tailscale_peer_relay", settings.get("relay-server-port", ""))):
                current_html = (f'<span>{esc(t["tailscale_current"])}: '
                                f'{self.private_value_control("tailscale-setting-" + kind, "value", t, endpoint="/tailscale/private-value")}</span>'
                                if current else "")
                field = ('<input name="value" type="number" min="1" max="65535" required>' if kind == "relay" else
                         '<input name="value" value="" maxlength="255">')
                field = field.replace('name="value"', f'name="{kind}_value"').replace(' required', '')
                if kind in ("routes", "exit"):
                    candidates = [(route, route) for route in subnets] if kind == "routes" else [(peer["selector"], peer["name"]) for peer in exit_nodes]
                    if current and str(current) not in [value for value, _ in candidates]:
                        candidates.insert(0, (str(current), str(current)))
                    options = f'<option value="">{esc(t["tailscale_clear"])}</option>' + ''.join(
                        f'<option value="{esc(value, quote=True)}" {"selected" if str(current) == value else ""}>{esc(title)}</option>'
                        for value, title in candidates)
                    field = f'<select name="{kind}_value" data-tailscale-single="{kind}">{options}</select>'
                    clear_control = f'<input type="hidden" name="{kind}_clear" value="{0 if current else 1}">'
                else:
                    clear_control = (f'<label class="tailscale-clear-choice"><input type="checkbox" name="{kind}_clear" value="1" '
                                     f'{"" if current else "disabled"}>{esc(t["tailscale_clear"])}</label>')
                fields_html += (f'<div class="tailscale-setting-card"><label>{esc(t[label])}{field}</label>{current_html}{clear_control}</div>')
            token = self.context.access_csrf_token(self.get_cookie("session"), "tailscale:batch")
            content += (f'<form method="post" action="/tailscale/action" class="tailscale-batch">'
                        f'<input type="hidden" name="action" value="batch"><input type="hidden" name="csrf" value="{token}">'
                        f'<div class="tailscale-options">{options_html}</div><div class="tailscale-setting-fields">{fields_html}</div>'
                        f'<div class="tailscale-save"><button type="submit">{esc(t["frp_save"])}</button></div></form>')
        elif tab == "devices":
            devices = control.peers(snapshot)
            content += (f'<div class="tailscale-head"><h2>{esc(t["tailscale_devices"])} ({len(devices)})</h2>'
                        f'<a class="button-link" href="/tailscale?tab=devices">{esc(t["tailscale_refresh"])}</a></div>')
            if not devices:
                content += f'<p class="muted">{esc(t["tailscale_no_devices"])}</p>'
            else:
                rows = "".join(f'<tr><td>{esc(p["name"])}</td><td>{esc(t["tailscale_online"] if p["online"] else t["tailscale_offline"])}</td>'
                               f'<td><div class="tailscale-peer-addresses">' + "".join(
                                   f'<div class="tailscale-peer-address"><small>{family}</small>'
                                   f'{self.private_value_control("tailscale-peer-" + p["id"], field, t, endpoint="/tailscale/private-value")}</div>'
                                   for family, field, marker in (("IPv4", "ipv4", False), ("IPv6", "ipv6", True))
                                   if p["id"] and any((":" in address) == marker for address in p["addresses"])) +
                               '</div></td>'
                               f'<td>{esc(p["os"])}</td><td>{esc(p["relay"] or "—")}</td>'
                               f'<td>{p["rx"]:,} / {p["tx"]:,}</td><td>{esc(t["tailscale_online"] if p["online"] else p["last_seen"] or "—")}</td></tr>'
                               for p in devices)
                content += (f'<div class="tailscale-table"><table><thead><tr>'
                            + "".join(f'<th scope="col">{esc(t[key])}</th>' for key in
                                      ("tailscale_device", "tailscale_state", "tailscale_address", "tailscale_os", "tailscale_relay", "tailscale_rx_tx", "tailscale_last_seen"))
                            + f'</tr></thead><tbody>{rows}</tbody></table></div>')
        else:
            level = parse_qs(parsed.query).get("level", ["all"])[0]
            if level not in dict(LOG_LEVELS):
                level = "all"
            output = service_log_text(self.context, (control.UNIT,), level, 500,
                                      log_cutoffs(self.context).get("tailscale"))
            content += (f'{"<p class=notice role=status>" + esc(t["logs_clear_done"]) + "</p>" if parse_qs(parsed.query).get("cleared") == ["1"] else ""}'
                        '<div class="logs-actions">' +
                        log_clear_form(self.context, t, self.get_cookie("session"), "tailscale", "tailscale") +
                        '</div>' +
                        log_level_form(t, "/tailscale", {"tab": "logs"}, level) +
                        f'<pre class="logs-output" role="log">{esc((output or t["logs_empty"]) if output is not None else t["logs_unavailable"])}</pre>')
        body = (f'<div class="card wide tailscale-page">{headline}<nav class="log-sources" aria-label="Tailscale">{nav}</nav>'
                f'{content}</div><script src="/static/copy.js"></script><script src="/static/private-values.js"></script>'
                '<script src="/static/tailscale.js" defer></script>'
                '<script src="/static/log-controls.js" defer></script>')
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
                   "connect": {"action", "csrf", "login_server", "auth_key"},
                   "logout": {"action", "csrf", "confirm"},
                   "memory": {"action", "csrf", "enabled"}}
        allowed["batch"] = ({"action", "csrf", "routes_value", "exit_value", "relay_value", "memory_available", "memory_enabled"}
                            | {kind + "_clear" for kind in ("routes", "exit", "relay")}
                            | {prefix + name for name in control.BOOL_SETTINGS for prefix in ("available_", "enabled_")})
        if action not in allowed or set(form) - allowed[action] or any(len(v) != 1 for v in form.values()):
            return self.send_html(400, "Invalid request")
        if action == "batch" and (not {"routes_value", "exit_value", "relay_value"} <= set(form) or
                                  any(value != ["1"] for key, value in form.items()
                                      if key.endswith("_clear") or key.startswith(("available_", "enabled_")) or
                                      key in ("memory_available", "memory_enabled"))):
            return self.send_html(400, "Invalid request")
        if action == "set" and name not in control.BOOL_SETTINGS:
            return self.send_html(400, "Invalid request")
        if action == "logout" and form.get("confirm") != ["yes"]:
            return self.send_html(400, "Invalid request")
        if action == "set" and form.get("enabled", ["1"]) != ["1"]:
            return self.send_html(400, "Invalid request")
        if action == "memory" and form.get("enabled", ["1"]) != ["1"]:
            return self.send_html(400, "Invalid request")
        subject = "tailscale:" + ("set:" + name if action == "set" else action)
        expected = self.context.access_csrf_token(self.get_cookie("session"), subject)
        if not self.context.hmac.compare_digest(form.get("csrf", [""])[0], expected):
            return self.send_html(403, "Forbidden")
        try:
            if action == "batch":
                self.apply_tailscale_batch(form)
            elif action == "set":
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
            elif action == "logout":
                control.call("logout")
            elif action == "memory":
                toggle = "on" if form.get("enabled") == ["1"] else "off"
                unit = "vps-server-tail-memory-" + self.context.secrets.token_hex(6)
                result = subprocess.run(["systemd-run", "--quiet", "--wait", "--pipe", "--collect",
                                         "--unit=" + unit, "/usr/bin/python3",
                                         str(self.context.WEB_CODE_DIR / "tailscale_control.py"),
                                         "memory", toggle], capture_output=True, text=True,
                                        check=False, timeout=90)
                if result.returncode:
                    raise RuntimeError("Tailscale memory setting failed")
            else:
                subprocess.run(["systemctl", "restart", control.UNIT], check=True, timeout=60)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            return self.send_html(400, self.render_page("Tailscale", f'<div class="card"><p class="error">{html.escape(t["tailscale_action_failed"])}</p></div>', lang, back_href="/tailscale"))
        self.redirect("/tailscale?tab=" + ("settings" if action in ("batch", "set", "routes", "exit", "routes-clear", "exit-clear", "relay", "relay-clear", "memory") else "overview"), {"Cache-Control": "no-store"})

    def route_tailscale(self, method, path, parsed, lang, query_lang):
        if method == "GET" and path == "/tailscale":
            self.page_tailscale(lang, query_lang, parsed)
        elif method == "POST" and path == "/tailscale/action":
            self.tailscale_action(lang)
        elif method == "GET" and path == "/tailscale/private-value":
            query = parse_qs(parsed.query)
            identifier = query.get("id", [""])[0]
            settings_value = identifier in ("tailscale-setting-routes", "tailscale-setting-exit", "tailscale-setting-relay") and query.get("field") == ["value"]
            address_value = (query.get("field") == ["address"] and identifier in
                             ("tailscale-tailscale_control_server", "tailscale-tailscale_ipv4", "tailscale-tailscale_ipv6", "tailscale-tailscale_account", "tailscale-tailscale_public_endpoint")) or (
                             query.get("field") in (["ipv4"], ["ipv6"]) and identifier.startswith("tailscale-peer-"))
            if not (settings_value or address_value):
                return self.send_html(400, "Invalid request") or True
            try:
                snapshot = control.status()
                if settings_value:
                    preferences = control.prefs()
                    value = preferences["advertise-routes" if identifier.endswith("routes") else
                                        "relay-server-port" if identifier.endswith("relay") else "exit-node"]
                elif identifier == "tailscale-tailscale_control_server":
                    value = (snapshot.get("CurrentTailnet") or {})["Name"]
                elif identifier == "tailscale-tailscale_account":
                    self_info = snapshot.get("Self") or {}
                    value = (snapshot.get("User") or {})[str(self_info.get("UserID"))]["LoginName"]
                elif identifier == "tailscale-tailscale_public_endpoint":
                    value = control.netcheck()["GlobalV4"]
                elif identifier.startswith("tailscale-peer-"):
                    peer = next(p for p in control.peers(snapshot) if p["id"] == identifier[len("tailscale-peer-"):])
                    value = next(address for address in peer["addresses"] if (":" in address) == (query.get("field") == ["ipv6"]))
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
