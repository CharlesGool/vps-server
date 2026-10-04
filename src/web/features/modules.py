"""Modules pages and actions for the operator console.

Host dependencies are supplied by ``ConsoleHandler.context`` so the feature
can be reused with another application context.
"""

import os


def module_job_text(t, job, names):
    """Describe the current module action using a localized display name."""
    if job.get("reason") == "port_occupied" and job.get("state") == "failed":
        return t["module_port_occupied"].format(port=job.get("port", ""))
    name = names.get(job.get("module"), t.get("module_" + str(job.get("module", "")),
                                               str(job.get("module", ""))))
    key = "module_action_" + str(job.get("action", "")) + "_" + str(job.get("state", ""))
    return t.get(key, t.get("module_job_" + str(job.get("state", "")), "")).format(name=name)


def module_job_recent(job, now, seconds):
    at = job.get("at")
    return type(at) in (int, float) and 0 <= now - at < seconds


class ModulesMixin:
    def page_logs(self, lang, query_lang, parsed):
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        source = self.context.parse_qs(parsed.query).get("source", ["modules"])[0]
        sources = (
            ("modules", t["logs_source_modules"], ()),
            ("web", "Web", ("vps-server-web.service",)),
            ("meter", t["logs_source_meter"], ("vps-server-node-meter.service",)),
            ("anytls", "AnyTLS", ("vps-server-anytls.service",)),
            ("proxy", "Singbox", ("vps-server-proxy.service",)),
            ("frps", "FRPS", ("vps-server-frps.service",)),
            ("frpc", "FRPC", tuple(self.context.frpc_unit(name) for name in self.context.frpc_names())),
            ("lucky", "Lucky", ("vps-server-lucky.service",)),
        )
        selected = next((item for item in sources if item[0] == source), None)
        if selected is None:
            return self.send_html(404, "Not found", {"Cache-Control": "no-store"})
        if source == "modules":
            try:
                output = self.context.module_history_path(self.context.BASE_DIR).read_text(encoding="utf-8", errors="replace")
            except FileNotFoundError:
                try:
                    output = self.context.module_log_path(self.context.BASE_DIR).read_text(encoding="utf-8", errors="replace")
                except FileNotFoundError:
                    output = ""
        elif selected[2] and self.context.shutil.which("journalctl"):
            try:
                command = ["journalctl", "--no-pager", "-o", "short-iso", "-n", "1000"]
                for unit in selected[2]:
                    command.extend(("-u", unit))
                result = self.context.subprocess.run(command, capture_output=True, text=True, timeout=15)
                output = result.stdout if result.returncode == 0 else t["logs_unavailable"]
            except (OSError, self.context.subprocess.TimeoutExpired):
                output = t["logs_unavailable"]
        else:
            output = ""
        links = "".join(
            f'<a href="/settings/logs?source={key}" {"aria-current=page" if key == source else ""}>{esc(label)}</a>'
            for key, label, _ in sources
        )
        body = (f'<div class="card wide logs-page"><h1>{esc(t["module_detailed_logs"])}</h1>'
                f'<p class="muted">{esc(t["logs_recent_note"])}</p>'
                f'<nav class="log-sources" aria-label="{esc(t["module_detailed_logs"], quote=True)}">{links}</nav>'
                f'<h2>{esc(selected[1])}</h2><pre class="logs-output" role="log">{esc(output or t["logs_empty"])}</pre></div>')
        return self.send_html(200, self.render_page(t["module_detailed_logs"], body, lang,
                                                    active="settings", back_href="/settings/modules"),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def page_module_not_installed(self, lang, query_lang, title, module_name, active=None):
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        body = (f'<div class="card access-card"><h1>{esc(title)}</h1>'
                f'<p class="muted">{esc(t["module_not_installed_help"].format(name=module_name))}</p>'
                f'<a class="button-link" href="/settings/modules">'
                f'{esc(t["module_install"] + " " + module_name)}</a></div>')
        return self.send_html(200, self.render_page(title, body, lang, active=active),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def public_page_url(self, module):
        authority = self.headers.get("Host", "")
        try:
            host = self.context.urlsplit("http://" + authority).hostname
        except ValueError:
            host = None
        if not host or not host.isascii() or not all(c.isalnum() or c in ".:-" for c in host):
            return None
        host = f"[{host}]" if ":" in host else host
        scheme, port = (("http", self.context.PUBLIC_HTTP_PORT) if module == "web_http"
                        else ("https", self.context.PUBLIC_HTTPS_PORT))
        return f"{scheme}://{host}{':' + str(port) if port != (80 if scheme == 'http' else 443) else ''}/"

    def page_modules(self, lang, query_lang):
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        token = self.get_cookie("session")
        installed = self.context.installed_modules(self.context.BASE_DIR)
        job = {}
        try:
            job = self.context.json.loads(self.context.module_status_path(self.context.BASE_DIR).read_text())
        except (OSError, ValueError):
            pass
        now = self.context.time.time()
        busy = job.get("state") in ("queued", "running") and module_job_recent(job, now, 900)
        notice_visible = busy or job.get("state") in ("done", "failed") and module_job_recent(job, now, 30)
        catalogue = (
            ("iperf3", t["iperf"], "iperf3"),
            ("proxy_nodes", t["proxy"], "proxy_nodes"),
            ("frps", "FRPS", "frps"),
            ("frpc", "FRPC", "frpc"),
        )
        cards = []
        for module, title, installable in catalogue:
            if module == "proxy_nodes":
                present = {"proxy", "anytls"} <= installed
                enabled = present and any(self.context._run_quiet(["systemctl", "is-enabled", "--quiet", self.context.MANAGED_UNITS[item]])
                                          for item in ("proxy", "anytls") if item in installed)
            elif module == "frpc":
                present = module in installed
                enabled = present and self.context.frpc_group_enabled(self.context.BASE_DIR)
            elif module == "iperf3":
                present = module in installed
                enabled = present and self.context.IPERF_ENABLED
            elif module == "frps":
                present = module in installed
                enabled = present and self.context._run_quiet(["systemctl", "is-enabled", "--quiet", self.context.MANAGED_UNITS[module]])
            status = (t["module_not_installed"] if not present else
                      t["module_disabled"] if not enabled else t["module_enabled"])
            control = ""
            if installable:
                action = "uninstall" if present else "install"
                label = t["module_uninstall"] if present else t["module_install"]
                confirm = f' data-confirm="{esc(t["module_uninstall_confirm"].format(name=title), quote=True)}"' if present else ""
                control = (f'<form method="post" action="/settings/modules/action">'
                           f'<input type="hidden" name="module" value="{module}">'
                           f'<input type="hidden" name="action" value="{action}">'
                           f'<input type="hidden" name="csrf" value="{self.context.access_csrf_token(token, "module:" + module + ":" + action)}">'
                           f'<button type="submit" class="{"danger" if present else ""}"{confirm} '
                           f'{"disabled" if busy else ""}>{esc(label)}</button></form>')
            cards.append(f'<section class="module-card"><div><h2>{esc(title)}</h2>'
                         f'<p>{esc(status)}</p></div>{control}</section>')
        notice_text = module_job_text(t, job, {key: title for key, title, _ in catalogue})
        notice = (f'<p class="module-notice" role="status" data-expires-at="{0 if busy else (job["at"] + 30) * 1000}">{esc(notice_text)}</p>'
                  if notice_visible else "")
        progress_job = job.get("module") in ("iperf3", "proxy_nodes", "frps", "frpc") and job.get("action") in ("install", "uninstall")
        progress = ""
        progress_recent = False
        last_output = 0
        if progress_job:
            try:
                log_path = self.context.module_log_path(self.context.BASE_DIR)
                modified = log_path.stat().st_mtime
                if modified >= job.get("at", 0) - 2:
                    last_output = int(modified * 1000)
                    progress_recent = self.context.time.time() - modified < 30
                    if progress_recent:
                        progress = "\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:])
            except (OSError, TypeError, ValueError):
                pass
        progress_html = (f'<section class="module-progress" data-last-output="{last_output}" {"hidden" if not progress_recent else ""}>'
                         f'<h2>{esc(t["module_progress"])}</h2><pre role="log">{esc(progress)}</pre></section>'
                         if progress_job else "")
        refresh_script = '<script src="/static/module-status.js" defer></script>' if busy or progress_recent or notice_visible else ''
        body = (f'<div class="card module-page" data-busy="{str(busy).lower()}"><h1>{esc(t["modules_heading"])}</h1>'
                f'<p>{esc(t["modules_note"])}</p>{notice}'
                f'<div class="module-grid">{"".join(cards)}</div>{progress_html}'
                f'<p><a href="/settings/logs">{esc(t["module_detailed_logs"])}</a></p></div>'
                f'<script src="/static/module-controls.js" defer></script>'
                f'{refresh_script}')
        return self.send_html(200, self.render_page(t["modules_heading"], body, lang,
                                                    active="settings", back_href="/settings"),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def handle_module_action(self, lang):
        esc = self.context.html.escape
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/x-www-form-urlencoded":
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 < length <= 1024:
                raise ValueError
            form = self.context.parse_qs(self.rfile.read(length).decode("utf-8"), strict_parsing=True)
            if set(form) not in ({"module", "action", "csrf"}, {"module", "action", "csrf", "return"}) or any(len(v) != 1 for v in form.values()):
                raise ValueError
        except (UnicodeError, ValueError):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        module, action = form["module"][0], form["action"][0]
        allowed = ("iperf3", "proxy_nodes", "frps", "frpc") if action in ("install", "uninstall") else (
            "web_http", "web_https", "iperf3", "proxy_nodes", "frps", "frpc") + self.context.MANAGED_FEATURES
        if module not in allowed or action not in ("install", "uninstall", "enable", "disable"):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        expected = self.context.access_csrf_token(self.get_cookie("session"), "module:" + module + ":" + action)
        if not self.context.hmac.compare_digest(form["csrf"][0], expected):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        destination = "/" if form.get("return", [""])[0] == "home" else "/settings/modules"
        installed = self.context.installed_modules(self.context.BASE_DIR)
        present = ({"proxy", "anytls"} <= installed if module == "proxy_nodes" else module in installed)
        if action in ("install", "uninstall") and (action == "install") == present:
            return self.redirect(destination, {"Cache-Control": "no-store"})
        install_source = (self.context.BASE_DIR / "installer-source" / "deploy" / "systemd" / "frpc@.service" if module == "frpc" else
                          self.context.BASE_DIR / "installer-source" / "deploy" / "install.sh")
        if action == "install" and module != "iperf3" and not install_source.is_file():
            return self.send_html(503, esc(self.context.STRINGS[lang]["module_source_missing"]),
                                  {"Cache-Control": "no-store"})
        helper = self.context.WEB_CODE_DIR / "module_manager.py"
        if not helper.is_file() or not self.context.shutil.which("systemd-run"):
            return self.send_html(503, esc(self.context.STRINGS[lang]["module_source_missing"]),
                                  {"Cache-Control": "no-store"})
        command = ["systemd-run", "--collect", "--unit=vps-server-module-job",
                   "/usr/bin/python3", str(helper), action, module, str(self.context.BASE_DIR)]
        with (self.context.DATA_DIR / "module-request.lock").open("a+b") as request_lock:
            self.context.fcntl.flock(request_lock, self.context.fcntl.LOCK_EX)
            try:
                job = self.context.json.loads(self.context.module_status_path(self.context.BASE_DIR).read_text())
                if job.get("state") in ("queued", "running") and self.context.time.time() - job.get("at", 0) < 900:
                    return self.redirect(destination, {"Cache-Control": "no-store"})
            except (OSError, ValueError, TypeError):
                pass
            if module in self.context.MANAGED_FEATURES and action in ("enable", "disable"):
                if self.context.module_feature_enabled(self.context.BASE_DIR, module) == (action == "enable"):
                    return self.redirect(destination, {"Cache-Control": "no-store"})
            self.context.save_module_status(self.context.BASE_DIR, module, "queued", action=action)
            try:
                result = self.context.subprocess.run(command, stdout=self.context.subprocess.DEVNULL,
                                        stderr=self.context.subprocess.DEVNULL, timeout=10, check=False)
            except (OSError, self.context.subprocess.TimeoutExpired):
                result = None
            if result is None or result.returncode:
                self.context.save_module_status(self.context.BASE_DIR, module, "failed", action=action)
                return self.send_html(503, esc(self.context.STRINGS[lang]["module_job_failed"]),
                                      {"Cache-Control": "no-store"})
        return self.redirect(destination, {"Cache-Control": "no-store"})

    def page_module_closed(self, lang, query_lang, parsed):
        module = self.context.parse_qs(parsed.query).get("module", [""])[0]
        destinations = {"web_http": "/public/http", "web_https": "/public/https",
                        "speedtest": "/speedtest", "iperf3": "/iperf", "proxy_nodes": "/proxy",
                        "frps": "/frps", "frpc": "/frpc", "frp": "/frpc", "portfwd": "/portfwd",
                        "visitors": "/visitors", "changelog": "/changelog"}
        if module not in destinations:
            return self.send_html(404, "Not found", {"Cache-Control": "no-store"})
        if self.context.module_states()[module]:
            return self.redirect(destinations[module], {"Cache-Control": "no-store"})
        t = self.context.STRINGS[lang]
        names = {"web_http": t["module_web_http"], "web_https": t["module_web_https"],
                 "speedtest": t["speedtest"], "iperf3": t["iperf"],
                 "proxy_nodes": t["proxy"], "frps": "FRPS", "frpc": "FRPC",
                 "frp": t["frp_heading"], "portfwd": t["portfwd"],
                 "visitors": t["visitors"], "changelog": t["changelog"]}
        body = (f'<div class="card access-card"><h1>{self.context.html.escape(t["module_closed_title"])}</h1>'
                f'<p>{self.context.html.escape(t["module_closed_help"].format(name=names[module]))}</p></div>')
        return self.send_html(200, self.render_page(t["module_closed_title"], body, lang,
                                                    back_href="/"),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def page_dashboard(self, lang, query_lang):
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        installed = self.context.installed_modules(self.context.BASE_DIR)
        states = self.context.module_states(installed)
        items = (
            ("web_http", t["module_web_http"], "/public/http", "network", states["web_http"]),
            ("web_https", t["module_web_https"], "/public/https", "lock-keyhole", states["web_https"]),
            ("speedtest", t["speedtest"], "/speedtest", "gauge", states["speedtest"]),
            ("iperf3", t["iperf"], "/iperf", "activity", states["iperf3"]),
            ("proxy_nodes", t["proxy"], "/proxy", "network", states["proxy_nodes"]),
            ("frps", "FRPS", "/frps", "radio", states["frps"]),
            ("frpc", "FRPC", "/frpc", "network", states["frpc"]),
            ("portfwd", t["portfwd"], "/portfwd", "route", states["portfwd"]),
            ("visitors", t["visitors"], "/visitors", "users-round", states["visitors"]),
            ("changelog", t["changelog"], "/changelog", "scroll-text", states["changelog"]),
            ("settings", t["settings"], "/settings", "settings-2", True),
        )
        job = {}
        try:
            job = self.context.json.loads(self.context.module_status_path(self.context.BASE_DIR).read_text())
            now = self.context.time.time()
            busy = job.get("state") in ("queued", "running") and module_job_recent(job, now, 900)
            notice_recent = job.get("state") == "failed" and job.get("reason") == "port_occupied" and module_job_recent(job, now, 30)
        except (OSError, ValueError, TypeError):
            busy = False
            notice_recent = False
        tiles = []
        for module, title, href, icon, enabled in items:
            switch = ""
            if module not in ("settings", "changelog"):
                action = "disable" if enabled else "enable"
                available = (module not in ("web_http", "web_https") or "web" in installed) and (
                    module != "iperf3" or "iperf3" in installed) and (
                    module != "proxy_nodes" or bool({"proxy", "anytls"} & installed)) and (
                    module != "frps" or "frps" in installed) and (
                    module != "frpc" or "frpc" in installed) and (
                    module != "portfwd" or self.context.PORTFWD_ALLOWED)
                switch = (f'<form method="post" action="/settings/modules/action" class="tile-switch-form">'
                          f'<input type="hidden" name="module" value="{module}">'
                          f'<input type="hidden" name="action" value="{action}">'
                          f'<input type="hidden" name="return" value="home">'
                          f'<input type="hidden" name="csrf" value="{self.context.access_csrf_token(self.get_cookie("session"), "module:" + module + ":" + action)}">'
                          f'<button type="submit" class="motion-switch" role="switch" aria-label="{esc(title + " " + (t["module_disable"] if enabled else t["module_enable"]), quote=True)}" '
                          f'aria-checked="{str(bool(enabled)).lower()}" {"" if available and not busy else "disabled"}><span aria-hidden="true"></span></button></form>')
            closed = not enabled and (module in self.context.MANAGED_FEATURES or
                                      module == "iperf3" and "iperf3" in installed or
                                      module == "proxy_nodes" and bool({"proxy", "anytls"} & installed) or
                                      module in ("frps", "frpc") and module in installed)
            occupied_port = public_listener_occupied(self.context, module, job)
            detail = (f'<span class="tile-error" role="status">'
                      f'{esc(t["module_port_occupied"].format(port=occupied_port))}</span>'
                      if occupied_port is not None else "")
            target = ("/closed?module=" + module
                      if closed or module in ("web_http", "web_https") and not enabled else href)
            tiles.append(f'<article class="tile{" tile-public" if module in ("web_http", "web_https") else ""}" data-module="{module}"><div class="tile-top">'
                         f'<span class="tile-icon">{self.context.ui_icon(icon)}</span>{switch}</div>'
                         f'<a class="tile-label" href="{target}">{esc(title)}</a>{detail}</article>')
        job_names = {key: title for key, title, *_ in items}
        notice = (f'<p class="module-notice" role="status" data-expires-at="{0 if busy else (job["at"] + 30) * 1000}">{esc(module_job_text(t, job, job_names))}</p>'
                  if busy or notice_recent else '')
        body = (f'<div class="card"><h1>{esc(t["home"])}</h1>{notice}'
                f'<div class="tiles">{"".join(tiles)}</div></div>'
                + '<script src="/static/module-controls.js" defer></script>'
                + ('<script src="/static/module-status.js" defer></script>' if busy or notice_recent else ''))
        self.send_html(200, self.render_page(t['dashboard'], body, lang, active="home"),
                       self.maybe_lang_cookie(query_lang))

    def route_modules(self, method, path, parsed, lang, query_lang):
        if method == "GET" and path == "/":
            self.page_dashboard(lang, query_lang)
            return True
        if method == "GET" and path in ("/public/http", "/public/https"):
            module = "web_http" if path.endswith("http") else "web_https"
            if not self.context.module_states()[module]:
                self.redirect("/closed?module=" + module, {"Cache-Control": "no-store"})
                return True
            destination = self.public_page_url(module)
            if not destination:
                self.send_html(400, "Invalid host", {"Cache-Control": "no-store"})
            else:
                self.redirect(destination, {"Cache-Control": "no-store"})
            return True
        return False

    def route_module_admin(self, method, path, lang, query_lang):
        if method == "GET" and path == "/settings/modules":
            self.page_modules(lang, query_lang)
        elif method == "GET" and path == "/settings/logs":
            self.page_logs(lang, query_lang, self.context.urlsplit(self.path))
        elif method == "POST" and path == "/settings/modules/action":
            self.handle_module_action(lang)
        else:
            return False
        return True


def portfwd_enabled(context, ):
    return context.PORTFWD_ALLOWED and context.module_feature_enabled(context.BASE_DIR, "portfwd")


def public_listener_runtime(context, module):
    if module not in ("web_http", "web_https"):
        return None
    try:
        status = context.json.loads((context.DATA_DIR / "public-listeners.json").read_text())
        if status.get("pid") == os.getpid():
            return status["http" if module == "web_http" else "https"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def public_listener_occupied(context, module, job):
    runtime = public_listener_runtime(context, module)
    if runtime and runtime.get("bound"):
        return None
    if runtime and runtime.get("enabled") and not runtime.get("bound") and runtime.get("reason") == "occupied":
        return runtime.get("port")
    if job.get("module") == module and job.get("state") == "failed" and job.get("reason") == "port_occupied":
        return job.get("port")
    return None

def module_states(context, installed=None):
    installed = installed if installed is not None else context.installed_modules(context.BASE_DIR)
    states = {
        "web_http": "web" in installed and context.PUBLIC_HTTP_ENABLED and
                    (public_listener_runtime(context, "web_http") or {}).get("bound", True),
        "web_https": "web" in installed and context.PUBLIC_HTTPS_ENABLED and
                     (public_listener_runtime(context, "web_https") or {}).get("bound", True),
        "speedtest": context.module_feature_enabled(context.BASE_DIR, "speedtest"),
        "iperf3": "iperf3" in installed and context.IPERF_ENABLED,
        "proxy_nodes": any(context._run_quiet(["systemctl", "is-enabled", "--quiet", context.MANAGED_UNITS[item]])
                           for item in ("proxy", "anytls") if item in installed),
        "frps": "frps" in installed and context._run_quiet(
            ["systemctl", "is-enabled", "--quiet", context.MANAGED_UNITS["frps"]]),
        "frpc": "frpc" in installed and context.frpc_group_enabled(context.BASE_DIR),
        "portfwd": context.portfwd_enabled(),
        "visitors": context.module_feature_enabled(context.BASE_DIR, "visitors"),
        "changelog": True,
    }
    states["frp"] = states["frps"] or states["frpc"]
    return states
