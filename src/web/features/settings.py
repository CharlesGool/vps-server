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
            for mode, key in (("light", "appearance_light"), ("dark", "appearance_dark")))
        languages = "".join(
            f'<a class="preferences-choice" href="/settings?lang={code}"'
            + (' aria-current="true"' if code == lang else '')
            + f'>{esc(name)}</a>' for code, name in self.context.LANG_NAMES.items())
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
              <p class="muted">{esc(t['server_label_note'])}</p>{label_feedback}
              <form method="post" action="/settings/server-label" class="server-label-form">
                <input type="hidden" name="csrf" value="{self.context.access_csrf_token(self.get_cookie('session'), 'server-label')}">
                <label for="server-label-input">{esc(t['server_label_field'])}</label>
                <input id="server-label-input" name="label" maxlength="40" value="{esc(label, quote=True)}" autocomplete="off">
                <button type="submit">{esc(t['server_label_save'])}</button>
              </form>
            </section>
            <section id="settings-console-port" class="card access-card preferences-card">
              <h2>{esc(t['console_port_heading'])}</h2>
              <p class="muted">{esc(t['console_port_note'])}</p>{port_feedback}
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
            <section id="settings-modules" class="card access-card preferences-card"><h2>{esc(t['modules_heading'])}</h2>
              <p>{esc(t['modules_note'])}</p><a class="module-manage" href="/settings/modules">{esc(t['modules_manage'])}</a>
            </section>
            <section id="settings-security" class="card access-card preferences-card preferences-security-card">
              <span class="preferences-security-heading">{self.context.ui_icon('lock-keyhole')}<h2>{esc(t['access_security'])}</h2></span>
              <span class="preferences-security-details"><span>{esc(t['access_ips'])}</span><span>{esc(t['access_password'])}</span></span>
              <a class="preferences-security-enter" href="/settings/security">{esc(t['access_enter_security'])}</a>
            </section>
          </div></div></div><script src="/static/settings-sections.js" defer></script>'''
        return self.send_html(200, self.render_page(t['settings'], body, lang, active="settings"),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def page_settings(self, lang, query_lang, parsed):
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        token = self.get_cookie("session")
        addresses = self.context.IP_ALLOWLIST.list_addresses()
        message = self.context.parse_qs(parsed.query).get("msg", [""])[0]
        allowed_messages = {"access_ip_added", "access_ip_removed", "access_ip_invalid",
                            "access_ip_error", "access_password_invalid", "access_ip_enabled", "access_ip_disabled"}
        feedback = (f'<p class="{"notice" if message in ("access_ip_added", "access_ip_removed", "access_ip_enabled", "access_ip_disabled") else "error"}" role="status">'
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
            <a href="#security-password">{esc(t['access_password'])}</a>
          </nav><div class="settings-content"><section id="security-ips" class="access-card access-ip-card">
            <header class="access-card-header"><div><p class="access-eyebrow">{esc(t['access_security'])}</p>
              <h2>{esc(t['access_ips'])}</h2></div>{self.context.ui_icon('lock-keyhole')}</header>
            <div class="access-card-body"><p>{esc(t['access_ip_note'])}</p>
              <p>{esc(t['access_ip_shared_note'])}</p>{load_warning}
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
          <section id="security-password" class="card access-card"><h2>{esc(t['access_password'])}</h2>
            <form method="post" action="/settings/password" autocomplete="off">
              <input type="hidden" name="csrf" value="{self.context.access_csrf_token(token, 'password')}">
              {new_password_field}
              {confirm_password_field}
              <button type="submit">{esc(t['access_change_password'])}</button>
            </form>
          </section></div></div><script src="/static/access-settings.js" defer></script>
          <script src="/static/settings-sections.js" defer></script></div>'''
        return self.send_html(200, self.render_page(t['settings'], body, lang, active="settings", back_href='/settings'),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

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
        action = {"/settings/ip/add": "ip-add", "/settings/ip/remove": "ip-remove",
                  "/settings/ip/toggle": "ip-toggle",
                  "/settings/password": "password"}[path]
        expected = ({"csrf", "new", "confirm"} if action == "password" else
                    {"csrf", "enabled"} if action == "ip-toggle" else {"csrf", "ip"})
        if set(form) != expected:
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if not self.context.hmac.compare_digest(form["csrf"][0],
                                   self.context.access_csrf_token(self.get_cookie("session"), action)):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
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
                cookie = "session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
                return self.redirect("/login?changed=1", {"Set-Cookie": cookie})
        elif action == "ip-toggle":
            if form["enabled"][0] not in ("0", "1"):
                return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
            try:
                self.context.IP_ALLOWLIST.set_enabled(form["enabled"][0] == "1")
                key = "access_ip_enabled" if self.context.IP_ALLOWLIST.is_enabled() else "access_ip_disabled"
            except OSError:
                key = "access_ip_error"
        else:
            try:
                self.context.IP_ALLOWLIST.change(form["ip"][0], add=action == "ip-add")
                key = "access_ip_added" if action == "ip-add" else "access_ip_removed"
            except ValueError:
                key = "access_ip_invalid"
            except OSError:
                key = "access_ip_error"
        return self.redirect(f"/settings/security?msg={key}", {"Cache-Control": "no-store"})

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
                self.page_security_verify(lang, next_page="frp" if next_page == "frp" else "")
                return True
            if method == "POST":
                self.handle_security_verify(lang)
                return True
        security_path = path == "/settings/security" or path in (
            "/settings/ip/add", "/settings/ip/remove", "/settings/ip/toggle", "/settings/password")
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
        elif method == "POST" and path in ("/settings/ip/add", "/settings/ip/remove",
                                                "/settings/ip/toggle", "/settings/password"):
            self.handle_settings_post(path)
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
