"""Settings pages, changes, and route handling."""


class SettingsMixin:
    def page_preferences(self, lang, query_lang):
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        label = self.context.server_label()
        message = self.context.parse_qs(self.context.urlsplit(self.path).query).get("msg", [""])[0]
        label_feedback = (f'<p class="{"notice" if message == "server_label_saved" else "error"}" role="status">'
                          f'{esc(t[message])}</p>' if message in
                          ("server_label_saved", "server_label_invalid", "server_label_error") else "")
        port_feedback = (f'<p class="{"notice" if message == "console_port_started" else "error"}" role="status">'
                         f'{esc(t[message])}</p>' if message in
                         ("console_port_started", "console_port_invalid", "console_port_error") else "")
        try:
            port_job = self.context.json.loads((self.context.DATA_DIR / "console-port-job.json").read_text())
        except (OSError, ValueError):
            port_job = {}
        if port_job.get("state") == "failed":
            port_feedback += f'<p class="error" role="alert">{esc(t["console_port_error"])} {esc(port_job.get("reason", ""))}</p>'
        themes = "".join(
            f'<button type="button" class="preferences-choice" data-theme-choice="{choice}" '
            f'aria-pressed="{str(choice == "slate-blue").lower()}">'
            f'<span class="theme-swatch theme-swatch-{choice}" aria-hidden="true"></span>'
            f'{esc(t[key])}</button>'
            for choice, key in (("slate-blue", "theme_slate_blue"), ("sage", "theme_sage"),
                                ("teal", "theme_teal"), ("plum", "theme_plum"),
                                ("ocean", "theme_ocean"), ("olive", "theme_olive"),
                                ("terracotta", "theme_terracotta"), ("indigo", "theme_indigo")))
        modes = "".join(
            f'<button type="button" class="preferences-choice" data-mode-choice="{mode}" '
            f'aria-pressed="{str(mode == "light").lower()}">{esc(t[key])}</button>'
            for mode, key in (("light", "appearance_light"), ("dark", "appearance_dark"), ("system", "appearance_system")))
        languages = "".join(
            f'<a class="preferences-choice" href="/settings?lang={code}"'
            + (' aria-current="true"' if code == lang else '')
            + f'>{esc(name)}</a>' for code, name in self.context.LANG_NAMES.items())
        modules = self.module_section(lang)
        body = f'''<div class="access-workspace preferences-workspace">
          <h1 class="access-page-title">{esc(t['settings'])}</h1>
          <div class="settings-layout"><nav class="section-nav" aria-label="{esc(t['settings'], quote=True)}">
            <a href="#settings-identity" aria-current="location">{esc(t['server_label_heading'])}</a>
            <a href="#settings-console-port">{esc(t['console_port_heading'])}</a>
            <a href="#settings-appearance">{esc(t['theme_label'])}</a>
            <a href="#settings-language">{esc(t['login_language'])}</a>
            <a href="#settings-modules">{esc(t['modules_heading'])}</a>
            <a href="#settings-security">{esc(t['access_security'])}</a>
          </nav><div class="settings-content">
            <section id="settings-identity" class="card access-card preferences-card"><h2>{esc(t['server_label_heading'])}</h2>
              {label_feedback}
              <form method="post" action="/settings/server-label" class="server-label-form">
                <input type="hidden" name="csrf" value="{self.context.access_csrf_token(self.get_cookie('session'), 'server-label')}">
                <label for="server-label-input">{esc(t['server_label_field'])}</label>
                <input id="server-label-input" name="label" maxlength="40" value="{esc(label, quote=True)}" autocomplete="off">
                <button type="submit">{esc(t['server_label_save'])}</button>
              </form>
            </section>
            <section id="settings-console-port" class="card access-card preferences-card">
              <h2>{esc(t['console_port_heading'])}</h2>
              {port_feedback}
              <form method="post" action="/settings/console-port" class="server-label-form">
                <input type="hidden" name="csrf" value="{self.context.access_csrf_token(self.get_cookie('session'), 'console-port')}">
                <label for="console-port-input">{esc(t['console_port_field'])}</label>
                <input id="console-port-input" name="port" type="number" min="1024" max="65535" required value="{self.context.CONSOLE_PORT}">
                <button type="submit">{esc(t['console_port_save'])}</button>
              </form>
            </section>
            <section id="settings-appearance" class="card access-card preferences-card"><h2>{esc(t['theme_label'])}</h2>
              <div class="preferences-mode"><h3>{esc(t['appearance_mode'])}</h3>
                <div class="preferences-choices" role="group" aria-label="{esc(t['appearance_mode'], quote=True)}">{modes}</div></div>
              <h3 class="preferences-group-title">{esc(t['theme_color'])}</h3>
              <div class="preferences-choices" role="group" aria-label="{esc(t['theme_color'], quote=True)}">{themes}</div>
            </section>
            <section id="settings-language" class="card access-card preferences-card"><h2>{esc(t['login_language'])}</h2>
              <div class="preferences-choices" aria-label="{esc(t['login_language'], quote=True)}">{languages}</div>
            </section>
            {modules}
            <section id="settings-security" class="card access-card preferences-card preferences-security-card">
              <span class="preferences-security-heading">{self.context.ui_icon('lock-keyhole')}<h2>{esc(t['access_security'])}</h2></span>
              <span class="preferences-security-details"><span>{esc(t['access_ips'])}</span><span>{esc(t['access_password'])}</span></span>
              <a class="preferences-security-enter" href="/settings/security">{esc(t['access_enter_security'])}</a>
            </section>
          </div></div></div>'''
        return self.send_html(200, self.render_page(t['settings'], body, lang, active="settings"),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def page_settings(self, lang, query_lang, parsed):
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        token = self.get_cookie("session")
        addresses = self.context.IP_ALLOWLIST.list_addresses()
        message = self.context.parse_qs(parsed.query).get("msg", [""])[0]
        notices = {"access_ip_added", "access_ip_removed", "access_ip_enabled", "access_ip_disabled",
                   "client_cert_enabled", "client_cert_disabled", "client_cert_revoked_msg",
                   "login_ban_enabled", "login_ban_disabled", "login_ban_cleared",
                   "console_access_enabled", "console_access_disabled", "console_access_added",
                   "console_access_removed", "sessions_revoked", "alerts_saved", "alerts_key_cleared",
                   "alerts_test_sent"}
        allowed_messages = notices | {"access_ip_invalid", "access_ip_error", "access_password_invalid",
                                      "client_cert_need_current", "client_cert_keep_current",
                                      "client_cert_error", "client_cert_openssl_missing",
                                      "client_cert_name_invalid", "login_ban_error",
                                      "console_access_invalid", "console_access_too_wide",
                                      "console_access_full", "console_access_need_current",
                                      "console_access_keep_current", "console_access_error",
                                      "sessions_none", "sessions_use_logout", "alerts_invalid",
                                      "alerts_error", "alerts_test_failed", "alerts_not_configured"}
        feedback = (f'<p class="{"notice" if message in notices else "error"}" role="status">'
                    f'{esc(t[message])}</p>') if message in allowed_messages else ""
        load_warning = f'<p class="error" role="alert">{esc(t["access_load_error"])}</p>' if self.context.IP_ALLOWLIST.load_error else ""
        rows = "".join(
            f'<li><code>{esc(address)}</code><form method="post" action="/settings/ip/remove">'
            f'<input type="hidden" name="ip" value="{esc(address, quote=True)}">'
            f'<input type="hidden" name="csrf" value="{self.context.access_csrf_token(token, "ip-remove")}">'
            f'<button type="submit" class="access-remove" aria-label="{esc(t["access_remove_ip"].format(ip=address), quote=True)}">'
            f'{esc(t["access_remove"])}</button></form></li>' for address in addresses)
        if not rows:
            rows = f'<li class="muted">{esc(t["access_ip_empty"])}</li>'
        new_password_field = self.context.render_password_field(
            t, "access-new-password", t["access_new_password"], "new",
            'autocomplete="new-password" minlength="12" maxlength="128" required')
        confirm_password_field = self.context.render_password_field(
            t, "access-confirm-password", t["access_confirm_password"], "confirm",
            'autocomplete="new-password" minlength="12" maxlength="128" required')
        body = f'''<div class="access-workspace">
          <h1 class="access-page-title">{esc(t['access_heading'])}</h1>{feedback}
          <div class="settings-layout"><nav class="section-nav" aria-label="{esc(t['access_heading'], quote=True)}">
            <a href="#security-ips" aria-current="location">{esc(t['access_ips'])}</a>
            <a href="#security-client-cert">{esc(t['access_client_cert'])}</a>
            <a href="#security-login-ban">{esc(t['login_ban_heading'])}</a>
            <a href="#security-console-access">{esc(t['console_access_heading'])}</a>
            <a href="#security-sessions">{esc(t['sessions_heading'])}</a>
            <a href="#security-alerts">{esc(t['alerts_heading'])}</a>
            <a href="#security-audit">{esc(t['audit_heading'])}</a>
            <a href="#security-password">{esc(t['access_password'])}</a>
          </nav><div class="settings-content"><section id="security-ips" class="access-card access-ip-card">
            <header class="access-card-header"><div><p class="access-eyebrow">{esc(t['access_security'])}</p>
              <h2>{esc(t['access_ips'])}</h2></div>{self.context.ui_icon('lock-keyhole')}</header>
            <div class="access-card-body">{load_warning}
            <form method="post" action="/settings/ip/toggle" class="access-toggle-form">
              <input type="hidden" name="csrf" value="{self.context.access_csrf_token(token, 'ip-toggle')}">
              <input type="hidden" name="enabled" value="{'0' if self.context.IP_ALLOWLIST.is_enabled() else '1'}">
              <span>{esc(t['access_ip_switch'])}</span>
              <button type="submit" aria-label="{esc(t['access_ip_disable'] if self.context.IP_ALLOWLIST.is_enabled() else t['access_ip_enable'], quote=True)}"
                aria-pressed="{'true' if self.context.IP_ALLOWLIST.is_enabled() else 'false'}">{esc(t['access_ip_disable'] if self.context.IP_ALLOWLIST.is_enabled() else t['access_ip_enable'])}</button>
            </form>
            <ul class="access-ip-list">{rows}</ul>
            <form method="post" action="/settings/ip/add" class="access-ip-form">
              <input type="hidden" name="csrf" value="{self.context.access_csrf_token(token, 'ip-add')}">
              <label class="sr-only" for="access-new-ip">{esc(t['access_ip_address'])}</label>
              <input id="access-new-ip" name="ip" placeholder="192.168.1.10 / fd12::1" required spellcheck="false" autocomplete="off">
              <button type="submit">{esc(t['access_add'])}</button>
            </form>
            </div>
          </section>
          {self.render_client_cert_card(t, token)}
          {self.render_login_ban_card(t, token)}
          {self.render_console_access_card(t, token)}
          {self.render_sessions_card(t, token)}
          {self.render_alerts_card(t, token)}
          {self.render_audit_card(t)}
          <section id="security-password" class="card access-card"><h2>{esc(t['access_password'])}</h2>
            <form method="post" action="/settings/password" autocomplete="off">
              <input type="hidden" name="csrf" value="{self.context.access_csrf_token(token, 'password')}">
              {new_password_field}
              {confirm_password_field}
              <button type="submit">{esc(t['access_change_password'])}</button>
            </form>
          </section></div></div><script src="/static/access-settings.js" defer></script>
          </div>'''
        return self.send_html(200, self.render_page(t['settings'], body, lang, active="settings", back_href='/settings'),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def security_duration(self, t, seconds):
        seconds = int(seconds)
        if seconds >= 3600 and seconds % 3600 == 0:
            return t["security_hours"].format(count=seconds // 3600)
        if seconds >= 3600:
            return t["security_hours"].format(count=round(seconds / 3600, 1))
        if seconds >= 60 and seconds % 60 == 0:
            return t["security_minutes"].format(count=seconds // 60)
        return t["security_seconds"].format(count=seconds)

    def security_time(self, value):
        return self.context.time.strftime("%Y-%m-%d %H:%M:%S", self.context.time.localtime(value or 0))

    def security_card(self, t, ident, heading, body):
        esc = self.context.html.escape
        return f'''<section id="{ident}" class="access-card access-ip-card">
            <header class="access-card-header"><div><p class="access-eyebrow">{esc(t['access_security'])}</p>
              <h2>{esc(heading)}</h2></div>{self.context.ui_icon('lock-keyhole')}</header>
            <div class="access-card-body">{body}</div>
          </section>'''

    def security_toggle(self, t, action, csrf_action, label, enabled):
        esc = self.context.html.escape
        token = self.get_cookie("session")
        return (f'<form method="post" action="{action}" class="access-toggle-form">'
                f'<input type="hidden" name="csrf" value="{self.context.access_csrf_token(token, csrf_action)}">'
                f'<input type="hidden" name="enabled" value="{"0" if enabled else "1"}">'
                f'<span>{esc(label)}</span>'
                f'<button type="submit" aria-pressed="{"true" if enabled else "false"}">'
                f'{esc(t["access_ip_disable"] if enabled else t["access_ip_enable"])}</button></form>')

    def security_button(self, action, csrf_action, label, fields=None, css=""):
        esc = self.context.html.escape
        token = self.get_cookie("session")
        hidden = "".join(f'<input type="hidden" name="{esc(name, quote=True)}" value="{esc(value, quote=True)}">'
                         for name, value in (fields or {}).items())
        return (f'<form method="post" action="{action}">{hidden}'
                f'<input type="hidden" name="csrf" value="{self.context.access_csrf_token(token, csrf_action)}">'
                f'<button type="submit"{f" class={chr(34)}{css}{chr(34)}" if css else ""}>{esc(label)}</button></form>')

    def render_login_ban_card(self, t, token):
        esc = self.context.html.escape
        limiter = self.context.LOGIN_LIMITER
        enabled = limiter.is_enabled()
        rule = t["login_ban_rule"].format(window=limiter.window_seconds, count=limiter.max_attempts,
                                          first=self.security_duration(t, limiter.lockout_seconds),
                                          max=self.security_duration(t, limiter.lockout_max_seconds))
        global_rule = ""
        if limiter.global_max_attempts > 0:
            state, left = limiter.global_state()
            status = ("" if state == "normal" else " " + (
                t["login_global_active"] if state == "banned" else t["login_global_flagged"]
            ).format(seconds=left))
            global_rule = (f'<p>{esc(t["login_global_rule"].format(window=limiter.window_seconds, count=limiter.global_max_attempts, duration=self.security_duration(t, limiter.global_lockout_seconds)))}'
                           f'<strong>{esc(status)}</strong></p>')
        load_warning = f'<p class="error" role="alert">{esc(t["login_ban_load_error"])}</p>' if limiter.load_error else ""
        rows = ""
        for row in limiter.snapshot():
            state = (t["login_ban_state_banned"].format(seconds=row["remaining"]) if row["state"] == "banned" else
                     t["login_ban_state_flagged"].format(seconds=row["remaining"]) if row["state"] == "flagged" else
                     t["login_ban_state_normal"])
            counts = t["login_ban_counts"].format(recent=row["recent"], total=row["total"],
                                                  triggered=row["triggered"], last=self.security_time(row["last"]))
            rows += (f'<li><span><code>{esc(row["ip"])}</code> <span class="muted">{esc(counts)}</span></span>'
                     f'<span class="{"error" if row["state"] == "banned" else "muted"}">{esc(state)}</span></li>')
        if not rows:
            rows = f'<li class="muted">{esc(t["login_ban_empty"])}</li>'
        body = (f'{load_warning}<p>{esc(rule)}</p>{global_rule}'
                f'{self.security_toggle(t, "/settings/login-ban/toggle", "login-ban-toggle", t["login_ban_switch"], enabled)}'
                f'<p class="muted">{esc(t["login_ban_observe_hint"])}</p>'
                f'<ul class="access-ip-list">{rows}</ul>'
                f'{self.security_button("/settings/login-ban/clear", "login-ban-clear", t["login_ban_clear"])}')
        return self.security_card(t, "security-login-ban", t["login_ban_heading"], body)

    def render_console_access_card(self, t, token):
        esc = self.context.html.escape
        access = self.context.CONSOLE_ACCESS
        enabled = access.enabled()
        current = self.client_ip()
        current_note = t["console_access_current"].format(
            ip=current, state=t["console_access_listed"] if access.listed(current) else t["console_access_unlisted"])
        load_warning = f'<p class="error" role="alert">{esc(t["console_access_load_error"])}</p>' if access.load_error else ""
        rows = "".join(
            f'<li><code>{esc(item)}</code>'
            f'{self.security_button("/settings/console-access/remove", "console-access-remove", t["access_remove"], {"network": item}, "access-remove")}</li>'
            for item in access.networks())
        if not rows:
            rows = f'<li class="muted">{esc(t["console_access_empty"])}</li>'
        add_current = ("" if access.listed(current) else
                       self.security_button("/settings/console-access/add", "console-access-add",
                                            t["console_access_add_current"], {"network": current}))
        recovery = f"python3 {self.context.WEB_CODE_DIR / 'console_access.py'} disable"
        body = (f'{load_warning}<p>{esc(t["console_access_intro"])}</p>'
                f'<p><strong>{esc(current_note)}</strong></p>'
                f'{self.security_toggle(t, "/settings/console-access/toggle", "console-access-toggle", t["console_access_switch"], enabled)}'
                f'<ul class="access-ip-list">{rows}</ul>'
                f'<form method="post" action="/settings/console-access/add" class="access-ip-form">'
                f'<input type="hidden" name="csrf" value="{self.context.access_csrf_token(token, "console-access-add")}">'
                f'<label class="sr-only" for="console-access-network">{esc(t["console_access_address"])}</label>'
                f'<input id="console-access-network" name="network" placeholder="203.0.113.5 / 198.51.100.0/24 / 2001:db8::/48" '
                f'required spellcheck="false" autocomplete="off">'
                f'<button type="submit">{esc(t["console_access_add"])}</button></form>{add_current}'
                f'<p class="muted">{esc(t["console_access_recovery"])}</p><pre class="logs-output">{esc(recovery)}</pre>')
        return self.security_card(t, "security-console-access", t["console_access_heading"], body)

    def describe_agent(self, agent):
        browser = next((name for pattern, name in ((r"Edg/", "Edge"), (r"OPR/|Opera", "Opera"),
                                                   (r"Firefox/", "Firefox"), (r"Chrome/|CriOS/", "Chrome"),
                                                   (r"Safari/", "Safari"), (r"curl/", "curl"))
                        if self.context.re.search(pattern, agent)), "")
        system = next((name for pattern, name in ((r"Android", "Android"), (r"iPhone|iPad|iOS", "iOS"),
                                                  (r"Windows", "Windows"), (r"Mac OS X|Macintosh", "macOS"),
                                                  (r"Linux", "Linux"))
                       if self.context.re.search(pattern, agent)), "")
        return " · ".join(part for part in (browser, system) if part) or agent[:40]

    def render_sessions_card(self, t, token):
        esc = self.context.html.escape
        idle = self.context.SESSION_IDLE_SECONDS
        intro = (t["sessions_intro"] if idle > 0 else t["sessions_intro_no_idle"]).format(
            ttl=self.security_duration(t, self.context.SESSION_TTL_SECONDS),
            idle=self.security_duration(t, idle) if idle > 0 else "")
        rows = ""
        sessions = self.context.list_sessions(token)
        for row in sessions:
            method = t.get("sessions_method_" + row["method"], row["method"])
            device = self.describe_agent(row["agent"]) or t["sessions_unknown_device"]
            meta = t["sessions_row"].format(ip=row["ip"] or "-", created=self.security_time(row["created"]),
                                            seen=self.security_time(row["seen"]))
            action = (f'<span class="muted">{esc(t["sessions_current"])}</span>' if row["current"] else
                      self.security_button("/settings/sessions/revoke", "session-revoke", t["sessions_revoke"],
                                           {"id": row["id"]}, "access-remove"))
            rows += (f'<li><span><strong>{esc(device)}</strong> <span class="muted">{esc(method)}</span><br>'
                     f'<span class="muted">{esc(meta)}</span></span>{action}</li>')
        if not rows:
            rows = f'<li class="muted">{esc(t["sessions_empty"])}</li>'
        others = (self.security_button("/settings/sessions/revoke-others", "session-revoke-others",
                                       t["sessions_revoke_others"])
                  if any(not row["current"] for row in sessions) else "")
        body = f'<p>{esc(intro)}</p><ul class="access-ip-list">{rows}</ul>{others}'
        return self.security_card(t, "security-sessions", t["sessions_heading"], body)

    def render_alerts_card(self, t, token):
        esc = self.context.html.escape
        alerts = self.context.ALERTS
        settings = alerts.settings()
        load_warning = f'<p class="error" role="alert">{esc(t["alerts_load_error"])}</p>' if alerts.load_error else ""
        key_field = self.context.render_password_field(
            t, "alerts-key", t["alerts_key"], "key",
            f'autocomplete="off" spellcheck="false" maxlength="128" '
            f'placeholder="{esc(t["alerts_key_keep"] if settings["configured"] else "", quote=True)}"')
        status = t["alerts_status_on"] if settings["configured"] else t["alerts_status_off"]
        checks = "".join(
            f'<label class="tailscale-option"><input type="checkbox" name="{name}" value="1"'
            f'{" checked" if settings[name] else ""}> {esc(t["alerts_on_" + name])}</label>'
            for name in ("new_ip", "ban"))
        extra = ""
        if settings["configured"]:
            extra = (self.security_button("/settings/alerts/test", "alerts-test", t["alerts_test"]) +
                     self.security_button("/settings/alerts/clear-key", "alerts-clear-key", t["alerts_clear_key"],
                                          css="access-remove"))
        body = (f'{load_warning}<p>{esc(t["alerts_intro"])}</p><p><strong>{esc(status)}</strong></p>'
                f'<form method="post" action="/settings/alerts" autocomplete="off">'
                f'<input type="hidden" name="csrf" value="{self.context.access_csrf_token(token, "alerts-save")}">'
                f'<label for="alerts-server">{esc(t["alerts_server"])}</label>'
                f'<input id="alerts-server" name="server" value="{esc(settings["server"], quote=True)}" '
                f'required spellcheck="false" autocomplete="off" maxlength="200">'
                f'{key_field}{checks}<button type="submit">{esc(t["alerts_save"])}</button></form>{extra}')
        return self.security_card(t, "security-alerts", t["alerts_heading"], body)

    def render_audit_card(self, t):
        esc = self.context.html.escape
        rows = ""
        for entry in self.context.AUDIT.recent(50):
            event = entry.get("event", "")
            label = t.get("audit_" + event, event)
            detail = entry.get("detail", "")
            detail = t.get("sessions_method_" + detail, detail)
            rows += (f'<li><span><strong>{esc(label)}</strong> <code>{esc(entry.get("ip", ""))}</code>'
                     f'{(" <span class=" + chr(34) + "muted" + chr(34) + ">" + esc(detail) + "</span>") if detail else ""}</span>'
                     f'<span class="muted">{esc(self.security_time(entry.get("t", 0)))}</span></li>')
        if not rows:
            rows = f'<li class="muted">{esc(t["audit_empty"])}</li>'
        body = f'<p>{esc(t["audit_intro"])}</p><ul class="access-ip-list">{rows}</ul>'
        return self.security_card(t, "security-audit", t["audit_heading"], body)

    def render_client_cert_card(self, t, token):
        esc = self.context.html.escape
        auth = self.context.CLIENT_AUTH
        required = auth.required()
        current = self.client_certificate()
        status = (t["client_cert_current_ok"].format(name=current.get("name", "")) if current
                  else t["client_cert_current_none"])
        rows = ""
        for item in reversed(auth.certificates()):
            created = self.context.time.strftime("%Y-%m-%d", self.context.time.localtime(item.get("created", 0)))
            meta = f'{item["serial"][:8]} · {created}'
            if item.get("revoked"):
                action = f'<span class="muted">{esc(t["client_cert_revoked"])}</span>'
            else:
                action = (f'<form method="post" action="/settings/client-cert/revoke">'
                          f'<input type="hidden" name="serial" value="{esc(item["serial"], quote=True)}">'
                          f'<input type="hidden" name="csrf" value="{self.context.access_csrf_token(token, "cert-revoke")}">'
                          f'<button type="submit" class="access-remove">{esc(t["client_cert_revoke"])}</button></form>')
            rows += (f'<li><span><strong>{esc(item.get("name", ""))}</strong> '
                     f'<code>{esc(meta)}</code></span>{action}</li>')
        if not rows:
            rows = f'<li class="muted">{esc(t["client_cert_list_empty"])}</li>'
        hint = ""
        if not current and any(not item.get("revoked") for item in auth.certificates()):
            hint = f'<p class="muted">{esc(t["client_cert_current_none_hint"])}</p>'
        return f'''<section id="security-client-cert" class="access-card access-ip-card">
            <header class="access-card-header"><div><p class="access-eyebrow">{esc(t['access_security'])}</p>
              <h2>{esc(t['access_client_cert'])}</h2></div>{self.context.ui_icon('lock-keyhole')}</header>
            <div class="access-card-body">
            <p>{esc(t['client_cert_intro'])}</p>
            <p>{esc(status)}</p>{hint}
            <form method="post" action="/settings/client-cert/toggle" class="access-toggle-form">
              <input type="hidden" name="csrf" value="{self.context.access_csrf_token(token, 'cert-toggle')}">
              <input type="hidden" name="enabled" value="{'0' if required else '1'}">
              <span>{esc(t['client_cert_switch'])}</span>
              <button type="submit" aria-pressed="{'true' if required else 'false'}">{esc(t['access_ip_disable'] if required else t['access_ip_enable'])}</button>
            </form>
            <ul class="access-ip-list">{rows}</ul>
            <form method="post" action="/settings/client-cert/issue" class="access-ip-form">
              <input type="hidden" name="csrf" value="{self.context.access_csrf_token(token, 'cert-issue')}">
              <label class="sr-only" for="client-cert-name">{esc(t['client_cert_name'])}</label>
              <input id="client-cert-name" name="name" placeholder="{esc(t['client_cert_name'], quote=True)}" required maxlength="40" autocomplete="off">
              <button type="submit">{esc(t['client_cert_issue'])}</button>
            </form>
            </div>
          </section>'''

    def page_client_cert_issued(self, lang, bundle, password, entry):
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        filename = "vps-server-" + entry["serial"][:8] + ".p12"
        href = "data:application/x-pkcs12;base64," + self.context.base64.b64encode(bundle).decode("ascii")
        os_items = "".join(f"<li>{esc(t[key])}</li>" for key in (
            "client_cert_os_windows", "client_cert_os_macos", "client_cert_os_android",
            "client_cert_os_ios", "client_cert_os_firefox"))
        body = f'''<div class="access-workspace"><section class="card access-card client-cert-issued">
          <h1>{esc(t['client_cert_issued_heading'])}</h1>
          <p>{esc(t['client_cert_issued_text'])}</p>
          <p>{esc(t['client_cert_password'])}: <code>{esc(password)}</code></p>
          <h2>{esc(t['client_cert_steps_title'])}</h2>
          <ol class="client-cert-steps">
            <li><p>{esc(t['client_cert_step_download'])}</p>
              <p><a class="button-link" href="{href}" download="{esc(filename, quote=True)}">{esc(t['client_cert_download'])}</a></p></li>
            <li><p>{esc(t['client_cert_step_import'])}</p><ul>{os_items}</ul></li>
            <li><p>{esc(t['client_cert_step_restart'])}</p></li>
            <li><p>{esc(t['client_cert_step_verify'])}</p></li>
          </ol>
          <p><a href="/settings/security#security-client-cert">{esc(t['client_cert_back'])}</a></p>
        </section></div>'''
        return self.send_html(200, self.render_page(t['client_cert_issued_heading'], body, lang, active="settings",
                                                    back_href='/settings/security'),
                              {"Cache-Control": "no-store"})

    def handle_client_cert_post(self, path, lang):
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = 0
        if (not 0 < length <= 4096 or
                self.headers.get("Content-Type", "").split(";", 1)[0].strip() !=
                "application/x-www-form-urlencoded"):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        try:
            form = self.context.parse_qs(self.rfile.read(length).decode("utf-8"), strict_parsing=True,
                                         keep_blank_values=True)
        except (UnicodeError, ValueError):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        action, field = {"/settings/client-cert/issue": ("cert-issue", "name"),
                         "/settings/client-cert/revoke": ("cert-revoke", "serial"),
                         "/settings/client-cert/toggle": ("cert-toggle", "enabled")}[path]
        if set(form) != {"csrf", field} or any(len(values) != 1 for values in form.values()):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if not self.context.hmac.compare_digest(form["csrf"][0],
                                                self.context.access_csrf_token(self.get_cookie("session"), action)):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        auth = self.context.CLIENT_AUTH
        value = form[field][0]
        current = self.client_certificate()
        try:
            if action == "cert-issue":
                bundle, password, entry = auth.issue(value)
                self.audit("cert_issued", value)
                return self.page_client_cert_issued(lang, bundle, password, entry)
            if action == "cert-revoke":
                # Revoking the certificate in use while it is required locks this browser out.
                if auth.required() and current and current["serial"] == value:
                    raise self.context.ClientCertError("client_cert_keep_current")
                auth.revoke(value)
                self.audit("cert_revoked", value[:8])
                key = "client_cert_revoked_msg"
            else:
                if value not in ("0", "1"):
                    return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
                # Only a browser that already holds an active certificate may require one.
                if value == "1" and current is None:
                    raise self.context.ClientCertError("client_cert_need_current")
                auth.set_required(value == "1")
                self.audit("cert_required_on" if value == "1" else "cert_required_off")
                key = "client_cert_enabled" if value == "1" else "client_cert_disabled"
        except self.context.ClientCertError as exc:
            key = exc.code
        except OSError:
            key = "client_cert_error"
        return self.redirect(f"/settings/security?msg={key}#security-client-cert", {"Cache-Control": "no-store"})

    SECURITY_POSTS = {
        "/settings/ip/add": ("ip-add", ({"csrf", "ip"},)),
        "/settings/ip/remove": ("ip-remove", ({"csrf", "ip"},)),
        "/settings/ip/toggle": ("ip-toggle", ({"csrf", "enabled"},)),
        "/settings/password": ("password", ({"csrf", "new", "confirm"},)),
        "/settings/login-ban/toggle": ("login-ban-toggle", ({"csrf", "enabled"},)),
        "/settings/login-ban/clear": ("login-ban-clear", ({"csrf"},)),
        "/settings/console-access/toggle": ("console-access-toggle", ({"csrf", "enabled"},)),
        "/settings/console-access/add": ("console-access-add", ({"csrf", "network"},)),
        "/settings/console-access/remove": ("console-access-remove", ({"csrf", "network"},)),
        "/settings/sessions/revoke": ("session-revoke", ({"csrf", "id"},)),
        "/settings/sessions/revoke-others": ("session-revoke-others", ({"csrf"},)),
        "/settings/alerts": ("alerts-save", tuple({"csrf", "server", "key"} | set(extra)
                                                   for extra in ((), ("new_ip",), ("ban",), ("new_ip", "ban")))),
        "/settings/alerts/test": ("alerts-test", ({"csrf"},)),
        "/settings/alerts/clear-key": ("alerts-clear-key", ({"csrf"},)),
    }

    def handle_settings_post(self, path):
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = 0
        if (not 0 < length <= 4096 or
                self.headers.get("Content-Type", "").split(";", 1)[0].strip() !=
                "application/x-www-form-urlencoded"):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        try:
            form = self.context.parse_qs(self.rfile.read(length).decode("utf-8"), strict_parsing=True,
                            keep_blank_values=True)
        except (UnicodeError, ValueError):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if any(len(values) != 1 for values in form.values()):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        action, expected = self.SECURITY_POSTS[path]
        if set(form) not in expected:
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        token = self.get_cookie("session")
        if not self.context.hmac.compare_digest(form["csrf"][0], self.context.access_csrf_token(token, action)):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        if "enabled" in form and form["enabled"][0] not in ("0", "1"):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        enabled = form.get("enabled", [""])[0] == "1"
        anchor = ""
        if action == "password":
            if form["new"][0] != form["confirm"][0]:
                key = "access_password_invalid"
            else:
                try:
                    self.context.change_admin_password(form["new"][0])
                    key = ""
                except (OSError, ValueError):
                    key = "access_password_invalid"
            if not key:
                self.audit("password_changed")
                cookie = f"session=; {self.context.SESSION_COOKIE_ATTRS}; Max-Age=0"
                return self.redirect("/login?changed=1", {"Set-Cookie": cookie})
        elif action == "login-ban-toggle":
            anchor = "#security-login-ban"
            try:
                self.context.LOGIN_LIMITER.set_enabled(enabled)
                self.audit("login_ban_on" if enabled else "login_ban_off")
                key = "login_ban_enabled" if enabled else "login_ban_disabled"
            except OSError:
                key = "login_ban_error"
        elif action == "login-ban-clear":
            anchor = "#security-login-ban"
            self.context.LOGIN_LIMITER.clear()
            self.audit("login_ban_cleared")
            key = "login_ban_cleared"
        elif action.startswith("console-access-"):
            anchor = "#security-console-access"
            access = self.context.CONSOLE_ACCESS
            try:
                if action == "console-access-toggle":
                    access.set_enabled(enabled, current=self.client_ip())
                    self.audit("console_access_on" if enabled else "console_access_off")
                    key = "console_access_enabled" if enabled else "console_access_disabled"
                elif action == "console-access-add":
                    network = access.add(form["network"][0].strip())
                    self.audit("console_access_added", network)
                    key = "console_access_added"
                else:
                    network = access.remove(form["network"][0], current=self.client_ip())
                    self.audit("console_access_removed", network)
                    key = "console_access_removed"
            except self.context.ConsoleAccessError as exc:
                key = str(exc)
            except OSError:
                key = "console_access_error"
        elif action == "session-revoke":
            anchor = "#security-sessions"
            if self.context.session_id(token) == form["id"][0]:
                key = "sessions_use_logout"
            else:
                count = self.context.revoke_sessions(session_ids={form["id"][0]})
                if count:
                    self.audit("session_revoked")
                key = "sessions_revoked" if count else "sessions_none"
        elif action == "session-revoke-others":
            anchor = "#security-sessions"
            count = self.context.revoke_sessions(keep=token)
            if count:
                self.audit("sessions_revoked_others", str(count))
            key = "sessions_revoked" if count else "sessions_none"
        elif action.startswith("alerts-"):
            anchor = "#security-alerts"
            alerts = self.context.ALERTS
            try:
                if action == "alerts-save":
                    alerts.update(server=form["server"][0], key=form["key"][0],
                                  new_ip="new_ip" in form, ban="ban" in form)
                    self.audit("alerts_saved")
                    key = "alerts_saved"
                elif action == "alerts-clear-key":
                    settings = alerts.settings()
                    alerts.update(server=settings["server"], key="", new_ip=settings["new_ip"],
                                  ban=settings["ban"], clear_key=True)
                    self.audit("alerts_key_cleared")
                    key = "alerts_key_cleared"
                else:
                    error = alerts.send_test(self._alert_text("alert_test_title"),
                                             self._alert_text("alert_test_body"))
                    key = "alerts_test_sent" if error is None else (
                        "alerts_not_configured" if error == "not configured" else "alerts_test_failed")
            except ValueError:
                key = "alerts_invalid"
            except OSError:
                key = "alerts_error"
        elif action == "ip-toggle":
            try:
                self.context.IP_ALLOWLIST.set_enabled(enabled)
                self.audit("ip_login_on" if enabled else "ip_login_off")
                key = "access_ip_enabled" if self.context.IP_ALLOWLIST.is_enabled() else "access_ip_disabled"
            except OSError:
                key = "access_ip_error"
        else:
            try:
                address = self.context.IP_ALLOWLIST.change(form["ip"][0], add=action == "ip-add")
                self.audit("ip_login_added" if action == "ip-add" else "ip_login_removed", address)
                key = "access_ip_added" if action == "ip-add" else "access_ip_removed"
            except ValueError:
                key = "access_ip_invalid"
            except OSError:
                key = "access_ip_error"
        return self.redirect(f"/settings/security?msg={key}{anchor}", {"Cache-Control": "no-store"})

    def route_settings(self, method, path, parsed, lang, query_lang):
        if method == "POST" and path == "/settings/console-port":
            self.handle_console_port(lang)
            return True
        if method == "POST" and path == "/settings/server-label":
            self.handle_server_label()
            return True
        if path == "/settings/verify":
            if method == "GET":
                next_page = self.context.parse_qs(parsed.query).get("next", [""])[0]
                self.page_security_verify(lang, next_page=next_page if next_page in ("frp", "terminal") else "")
                return True
            if method == "POST":
                self.handle_security_verify(lang)
                return True
        security_path = path == "/settings/security" or path in self.SECURITY_POSTS or path in (
            "/settings/client-cert/issue", "/settings/client-cert/revoke", "/settings/client-cert/toggle")
        if security_path and not self.context.security_settings_valid(self.get_cookie("session")):
            if method == "GET":
                target = "/settings/verify?next=frp" if path.startswith("/frp/") else "/settings/verify"
                self.redirect(target, {"Cache-Control": "no-store"})
            else:
                self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
            return True
        if method == "GET" and path == "/settings":
            self.page_preferences(lang, query_lang)
        elif method == "GET" and path == "/settings/security":
            self.page_settings(lang, query_lang, parsed)
        elif method == "POST" and path in self.SECURITY_POSTS:
            self.handle_settings_post(path)
        elif method == "POST" and path in ("/settings/client-cert/issue", "/settings/client-cert/revoke",
                                                "/settings/client-cert/toggle"):
            self.handle_client_cert_post(path, lang)
        else:
            return False
        return True

    def handle_console_port(self, lang):
        t = self.context.STRINGS[lang]
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/x-www-form-urlencoded":
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 < length <= 1024:
                raise ValueError
            form = self.context.parse_qs(self.rfile.read(length).decode("utf-8"),
                                         strict_parsing=True, keep_blank_values=True)
            if set(form) != {"csrf", "port"} or any(len(values) != 1 for values in form.values()):
                raise ValueError
        except (UnicodeError, ValueError):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        expected = self.context.access_csrf_token(self.get_cookie("session"), "console-port")
        if not self.context.hmac.compare_digest(form["csrf"][0], expected):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        try:
            port = int(form["port"][0])
            if not 1024 <= port <= 65535 or port == self.context.CONSOLE_PORT:
                raise ValueError
            host = self.context.urlsplit("http://" + self.headers.get("Host", "")).hostname
            if not host or not host.isascii() or not all(c.isalnum() or c in ".:-" for c in host):
                raise ValueError
        except ValueError:
            return self.redirect("/settings?msg=console_port_invalid#settings-console-port",
                                 {"Cache-Control": "no-store"})
        helper = self.context.WEB_CODE_DIR / "console_port.py"
        if not helper.is_file() or not self.context.shutil.which("systemd-run"):
            return self.redirect("/settings?msg=console_port_error#settings-console-port",
                                 {"Cache-Control": "no-store"})
        command = ["systemd-run", "--collect", "--unit=vps-server-console-port-job",
                   "/usr/bin/python3", str(helper), "change", str(self.context.BASE_DIR),
                   str(self.context.CONSOLE_PORT), str(port), str(self.context.CONSOLE_PORT_FILE)]
        try:
            result = self.context.subprocess.run(command, stdout=self.context.subprocess.DEVNULL,
                                                 stderr=self.context.subprocess.DEVNULL,
                                                 timeout=10, check=False)
            if result.returncode:
                raise OSError("could not start console port change")
        except (OSError, self.context.subprocess.TimeoutExpired):
            return self.redirect("/settings?msg=console_port_error#settings-console-port",
                                 {"Cache-Control": "no-store"})
        host = f"[{host}]" if ":" in host else host
        scheme = "https" if self.context.CONSOLE_TLS else "http"
        destination = f"{scheme}://{host}:{port}/settings#settings-console-port"
        old = f"{scheme}://{host}:{self.context.CONSOLE_PORT}/settings#settings-console-port"
        esc = self.context.html.escape
        body = (f'<div class="card access-card"><h1>{esc(t["console_port_heading"])}</h1>'
                f'<p>{esc(t["console_port_started"])}</p>'
                f'<p><a class="button-link" href="{esc(destination, quote=True)}">{esc(t["console_port_open_new"])}</a></p>'
                f'<p><a href="{esc(old, quote=True)}">{esc(t["console_port_return_old"])}</a></p></div>')
        return self.send_html(200, self.render_page(t["console_port_heading"], body, lang,
                                                    active="settings"), {"Cache-Control": "no-store"})

    def handle_server_label(self):
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/x-www-form-urlencoded":
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 < length <= 1024:
                raise ValueError
            form = self.context.parse_qs(self.rfile.read(length).decode("utf-8"),
                                         strict_parsing=True, keep_blank_values=True)
            if set(form) != {"csrf", "label"} or any(len(values) != 1 for values in form.values()):
                raise ValueError
        except (UnicodeError, ValueError):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        expected = self.context.access_csrf_token(self.get_cookie("session"), "server-label")
        if not self.context.hmac.compare_digest(form["csrf"][0], expected):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        try:
            self.context.save_server_label(form["label"][0])
            message = "server_label_saved"
        except ValueError:
            message = "server_label_invalid"
        except OSError:
            message = "server_label_error"
        return self.redirect("/settings?msg=" + message + "#settings-identity",
                             {"Cache-Control": "no-store"})
