"""Modules pages and actions for the operator console.

Host dependencies are supplied by ``ConsoleHandler.context`` so the feature
can be reused with another application context.
"""

import os
import json
import time


LOG_LEVELS = (("all", "logs_level_all"), ("err", "logs_level_error"),
              ("warning", "logs_level_warning"), ("info", "logs_level_info"),
              ("debug", "logs_level_debug"))


LOG_SOURCES = ("modules", "web", "proxy", "frps", "frpc", "lucky", "tailscale")


def log_cutoffs(context):
    try:
        data = json.loads((context.DATA_DIR / "log-clear.json").read_text())
        if isinstance(data, dict):
            return {key: value for key, value in data.items()
                    if key in LOG_SOURCES and type(value) in (int, float) and 0 < value <= time.time() + 1}
    except (OSError, ValueError):
        pass
    return {}


def service_log_text(context, units, level, limit, since=None):
    if level not in dict(LOG_LEVELS) or not units or not context.shutil.which("journalctl"):
        return None
    command = ["journalctl", "--no-pager", "-o", "short-iso", "-n", str(limit)]
    if level != "all":
        command.extend(("-p", level))
    if since:
        command.append(f"--since=@{since:.6f}")
    for unit in units:
        command.extend(("-u", unit))
    try:
        result = context.subprocess.run(command, capture_output=True, text=True, timeout=15)
        return result.stdout if result.returncode == 0 else None
    except (OSError, context.subprocess.TimeoutExpired):
        return None


def log_level_form(t, action, hidden, level):
    from html import escape
    options = "".join(f'<option value="{value}" {"selected" if level == value else ""}>{escape(t[key])}</option>'
                      for value, key in LOG_LEVELS)
    fields = "".join(f'<input type="hidden" name="{escape(name, quote=True)}" value="{escape(value, quote=True)}">'
                     for name, value in hidden.items())
    return (f'<form class="log-filter" method="get" action="{escape(action, quote=True)}">{fields}'
            f'<label>{escape(t["logs_level"])}<select name="level">{options}</select></label>'
            f'<button type="submit">{escape(t["logs_filter"])}</button></form>')


def log_clear_form(context, t, token, source, return_to="logs"):
    from html import escape
    csrf = context.access_csrf_token(token, "logs:clear:" + source)
    return (f'<form class="log-clear-form" method="post" action="/settings/logs/clear" '
            f'data-confirm="{escape(t["logs_clear_confirm"], quote=True)}">'
            f'<input type="hidden" name="source" value="{escape(source, quote=True)}">'
            f'<input type="hidden" name="return" value="{escape(return_to, quote=True)}">'
            f'<input type="hidden" name="csrf" value="{escape(csrf, quote=True)}">'
            f'<button type="submit" class="danger">{escape(t["logs_clear"])}</button></form>')


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
    def clear_logs(self):
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/x-www-form-urlencoded":
            return self.send_html(400, "Invalid request")
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 < length <= 1024:
                raise ValueError
            form = self.context.parse_qs(self.rfile.read(length).decode("utf-8"), strict_parsing=True)
            if set(form) != {"source", "return", "csrf"} or any(len(value) != 1 for value in form.values()):
                raise ValueError
        except (UnicodeError, ValueError):
            return self.send_html(400, "Invalid request")
        source = form["source"][0]
        if source not in LOG_SOURCES + ("all",) or form["return"][0] not in ("logs", "tailscale"):
            return self.send_html(400, "Invalid request")
        if form["return"][0] == "tailscale" and source != "tailscale":
            return self.send_html(400, "Invalid request")
        expected = self.context.access_csrf_token(self.get_cookie("session"), "logs:clear:" + source)
        if not self.context.hmac.compare_digest(form["csrf"][0], expected):
            return self.send_html(403, "Forbidden")
        try:
            if source in ("modules", "all"):
                path = self.context.module_history_path(self.context.BASE_DIR)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("w", encoding="utf-8"):
                    pass
                os.chmod(path, 0o600)
            if source != "modules":
                cutoffs = log_cutoffs(self.context)
                for key in (LOG_SOURCES[1:] if source == "all" else (source,)):
                    cutoffs[key] = time.time()
                self.context._atomic_private_text(self.context.DATA_DIR / "log-clear.json",
                                                  json.dumps(cutoffs, sort_keys=True) + "\n")
        except OSError:
            return self.send_html(500, "Could not clear logs")
        destination = ("/tailscale?tab=logs" if form["return"][0] == "tailscale" else
                       "/settings/logs?source=" + source)
        return self.redirect(destination + "&cleared=1" if "?" in destination else destination + "?cleared=1",
                             {"Cache-Control": "no-store"})

    def page_logs(self, lang, query_lang, parsed):
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        source = self.context.parse_qs(parsed.query).get("source", ["all"])[0]
        level = self.context.parse_qs(parsed.query).get("level", ["all"])[0]
        if source == "meter":
            return self.redirect("/settings/logs?source=proxy", {"Cache-Control": "no-store"})
        if level not in dict(LOG_LEVELS):
            level = "all"
        sources = (
            ("all", t["logs_source_all"], ()),
            ("modules", t["logs_source_modules"], ()),
            ("web", "Web", ("vps-server-web.service",)),
            ("proxy", t["logs_source_proxy"], ("vps-server-proxy.service", "vps-server-node-meter.service")),
            ("frps", "FRPS", ("vps-server-frps.service",)),
            ("frpc", "FRPC", tuple(self.context.frpc_unit(name) for name in self.context.frpc_names())),
            ("lucky", "Lucky", ("vps-server-lucky.service",)),
            ("tailscale", "Tailscale", ("vps-server-tailscale.service",)),
        )
        selected = next((item for item in sources if item[0] == source), None)
        if selected is None:
            return self.send_html(404, "Not found", {"Cache-Control": "no-store"})
        cutoffs = log_cutoffs(self.context)
        if source in ("modules", "all"):
            try:
                history = self.context.module_history_path(self.context.BASE_DIR).read_text(encoding="utf-8", errors="replace")
            except FileNotFoundError:
                try:
                    history = self.context.module_log_path(self.context.BASE_DIR).read_text(encoding="utf-8", errors="replace")
                except FileNotFoundError:
                    history = ""
            output = history
        if source == "all":
            sections = []
            for key, label, units in sources[2:]:
                service_output = service_log_text(self.context, units, level, 250, cutoffs.get(key)) if units else ""
                text = ((service_output or t["logs_empty"]) if service_output is not None else t["logs_unavailable"])
                sections.append(f'<section class="logs-group"><h2>{esc(label)}</h2>'
                                f'<pre class="logs-output" role="log">{esc(text)}</pre></section>')
            log_content = (f'{log_level_form(t, "/settings/logs", {"source": source}, level)}'
                           f'<section class="logs-group"><h2>{esc(t["logs_source_modules"])}</h2>'
                           f'<pre class="logs-output" role="log">{esc(history or t["logs_empty"])}</pre></section>'
                           + "".join(sections))
        elif selected[2]:
            output = service_log_text(self.context, selected[2], level, 1000, cutoffs.get(source))
            if output is None:
                output = t["logs_unavailable"]
        else:
            output = ""
        links = "".join(
            f'<a href="/settings/logs?source={key}" {"aria-current=page" if key == source else ""}>{esc(label)}</a>'
            for key, label, _ in sources
        )
        if source != "all":
            log_content = (f'<h2>{esc(selected[1])}</h2>'
                           f'{log_level_form(t, "/settings/logs", {"source": source}, level) if selected[2] else ""}'
                           f'<pre class="logs-output" role="log">{esc(output or t["logs_empty"])}</pre>')
        body = (f'<div class="card wide logs-page"><h1>{esc(t["module_detailed_logs"])}</h1>'
                f'<nav class="log-sources" aria-label="{esc(t["module_detailed_logs"], quote=True)}">{links}</nav>'
                f'{"<p class=notice role=status>" + esc(t["logs_clear_done"]) + "</p>" if self.context.parse_qs(parsed.query).get("cleared") == ["1"] else ""}'
                f'<div class="logs-actions">{log_clear_form(self.context, t, self.get_cookie("session"), source)}'
                f'</div>{log_content}</div>'
                '<script src="/static/log-controls.js" defer></script>')
        return self.send_html(200, self.render_page(t["module_detailed_logs"], body, lang,
                                                    active="module_detailed_logs", back_href="/settings"),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def page_module_not_installed(self, lang, query_lang, title, module_name, active=None):
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        body = (f'<div class="card access-card"><h1>{esc(title)}</h1>'
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

    def module_section(self, lang):
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
        marker = self.context.parse_qs(self.context.urlsplit(self.path).query).get("operation", [""])[0]
        show_operation = marker == f'{job.get("module")}-{job.get("action")}'
        notice_visible = show_operation and (busy or job.get("state") in ("done", "failed") and module_job_recent(job, now, 30))
        catalogue = (
            ("iperf3", t["iperf"], "iperf3"),
            ("proxy_nodes", t["proxy"], "proxy_nodes"),
            ("frps", "FRPS", "frps"),
            ("frpc", "FRPC", "frpc"),
            ("lucky", "Lucky", "lucky"),
            ("tailscale", "Tailscale", "tailscale"),
        )
        cards = []
        for module, title, installable in catalogue:
            if module == "proxy_nodes":
                present = "proxy" in installed
                enabled = present and self.context._run_quiet(
                    ["systemctl", "is-enabled", "--quiet", self.context.MANAGED_UNITS["proxy"]])
            elif module == "frpc":
                present = module in installed
                enabled = present and self.context.frpc_group_enabled(self.context.BASE_DIR)
            elif module == "iperf3":
                present = module in installed
                enabled = present and self.context.IPERF_ENABLED
            elif module in ("frps", "lucky", "tailscale"):
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
        progress_job = (show_operation and job.get("module") in ("iperf3", "proxy_nodes", "frps", "frpc")
                        and job.get("action") in ("install", "uninstall"))
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
        refresh_script = '<script src="/static/module-status.js" defer></script>' if busy or show_operation and (progress_recent or notice_visible) else ''
        body = (f'<section id="settings-modules" class="card access-card preferences-card module-page" data-busy="{str(busy).lower()}"><h2>{esc(t["modules_heading"])}</h2>'
                f'{notice}<div class="module-grid">{"".join(cards)}</div>{progress_html}</section>'
                f'<script src="/static/module-controls.js" defer></script>'
                f'{refresh_script}')
        return body

    def page_modules(self, lang, query_lang):
        return self.redirect("/settings#settings-modules", {"Cache-Control": "no-store"})

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
        allowed = ("iperf3", "proxy_nodes", "frps", "frpc", "lucky", "tailscale") if action in ("install", "uninstall") else (
            "web_http", "web_https", "iperf3", "proxy_nodes", "frps", "frpc", "lucky", "tailscale") + self.context.MANAGED_FEATURES
        if module not in allowed or action not in ("install", "uninstall", "enable", "disable"):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        expected = self.context.access_csrf_token(self.get_cookie("session"), "module:" + module + ":" + action)
        if not self.context.hmac.compare_digest(form["csrf"][0], expected):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        destination = "/" if form.get("return", [""])[0] == "home" else "/settings#settings-modules"
        installed = self.context.installed_modules(self.context.BASE_DIR)
        present = ("proxy" in installed if module == "proxy_nodes" else module in installed)
        if action in ("install", "uninstall") and (action == "install") == present:
            return self.redirect(destination, {"Cache-Control": "no-store"})
        install_source = (self.context.BASE_DIR / "installer-source" / "deploy" / "systemd" / "frpc@.service" if module == "frpc" else
                          self.context.BASE_DIR / "installer-source" / "deploy" / "install.sh")
        if action == "install" and module != "iperf3" and not install_source.is_file():
            return self.send_html(503, esc(self.context.STRINGS[lang]["module_source_missing"]),
                                  {"Cache-Control": "no-store"})
        if action == "install" and module == "tailscale" and not (
                self.context.BASE_DIR / "installer-source" / "third_party" / "tailscale" /
                "tailscale_1.102.4_amd64.tgz").is_file():
            return self.send_html(503, esc(self.context.STRINGS[lang]["module_tailscale_asset_missing"]),
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
        operation_url = (f'/?operation={module}-{action}' if destination == "/" else
                         f'/settings?operation={module}-{action}#settings-modules')
        return self.redirect(operation_url,
                             {"Cache-Control": "no-store"})

    def page_module_closed(self, lang, query_lang, parsed):
        module = self.context.parse_qs(parsed.query).get("module", [""])[0]
        destinations = {"web_http": "/public/http", "web_https": "/public/https",
                        "speedtest": "/speedtest", "iperf3": "/iperf", "proxy_nodes": "/proxy",
                        "frps": "/frps", "frpc": "/frpc", "frp": "/frpc", "lucky": "/lucky", "tailscale": "/tailscale", "portfwd": "/portfwd",
                        "visitors": "/visitors", "terminal": "/terminal", "changelog": "/changelog"}
        if module not in destinations:
            return self.send_html(404, "Not found", {"Cache-Control": "no-store"})
        if self.context.module_states()[module]:
            return self.redirect(destinations[module], {"Cache-Control": "no-store"})
        t = self.context.STRINGS[lang]
        names = {"web_http": t["module_web_http"], "web_https": t["module_web_https"],
                 "speedtest": t["speedtest"], "iperf3": t["iperf"],
                 "proxy_nodes": t["proxy"], "frps": "FRPS", "frpc": "FRPC", "lucky": "Lucky", "tailscale": "Tailscale",
                 "frp": t["frp_heading"], "portfwd": t["portfwd"],
                 "visitors": t["visitors"], "terminal": t["terminal_title"], "changelog": t["changelog"]}
        body = (f'<div class="card access-card"><h1>{self.context.html.escape(names[module])}: '
                f'{self.context.html.escape(t["module_closed_title"])}</h1></div>')
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
            ("lucky", "Lucky", "/lucky", "network", states["lucky"]),
            ("tailscale", "Tailscale", "/tailscale", "waypoints", states["tailscale"]),
            ("portfwd", t["portfwd"], "/portfwd", "route", states["portfwd"]),
            ("visitors", t["visitors"], "/visitors", "users-round", states["visitors"]),
            ("terminal", t["terminal_title"], "/terminal", "activity", states["terminal"]),
            ("changelog", t["changelog"], "/changelog", "scroll-text", states["changelog"]),
            ("logs", t["module_detailed_logs"], "/settings/logs", "scroll-text", True),
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
        marker = self.context.parse_qs(self.context.urlsplit(self.path).query).get("operation", [""])[0]
        show_operation = marker == f'{job.get("module")}-{job.get("action")}'
        tiles = []
        for module, title, href, icon, enabled in items:
            if module == "terminal" and not self.context.AUTH_ENABLED:
                continue
            switch = ""
            if module not in ("settings", "changelog", "logs"):
                action = "disable" if enabled else "enable"
                available = (module not in ("web_http", "web_https") or "web" in installed) and (
                    module != "iperf3" or "iperf3" in installed) and (
                    module != "proxy_nodes" or "proxy" in installed) and (
                    module != "frps" or "frps" in installed) and (
                    module != "frpc" or "frpc" in installed) and (
                    module != "tailscale" or "tailscale" in installed) and (
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
                                      module == "proxy_nodes" and "proxy" in installed or
                                      module in ("frps", "frpc", "lucky", "tailscale") and module in installed)
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
                  if show_operation and (busy or notice_recent) else '')
        body = (f'<div class="card"><h1>{esc(t["home"])}</h1>{notice}'
                f'<div class="tiles">{"".join(tiles)}</div></div>'
                + '<script src="/static/module-controls.js" defer></script>'
                + ('<script src="/static/module-status.js" defer></script>' if busy or show_operation and notice_recent else ''))
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
        elif method == "POST" and path == "/settings/logs/clear":
            self.clear_logs()
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
        "proxy_nodes": "proxy" in installed and context._run_quiet(
            ["systemctl", "is-enabled", "--quiet", context.MANAGED_UNITS["proxy"]]),
        "frps": "frps" in installed and context._run_quiet(
            ["systemctl", "is-enabled", "--quiet", context.MANAGED_UNITS["frps"]]),
        "frpc": "frpc" in installed and context.frpc_group_enabled(context.BASE_DIR),
        "lucky": "lucky" in installed and context._run_quiet(
            ["systemctl", "is-enabled", "--quiet", context.MANAGED_UNITS["lucky"]]),
        "tailscale": "tailscale" in installed and context._run_quiet(
            ["systemctl", "is-enabled", "--quiet", context.MANAGED_UNITS["tailscale"]]),
        "portfwd": context.portfwd_enabled(),
        "visitors": context.module_feature_enabled(context.BASE_DIR, "visitors"),
        "terminal": context.AUTH_ENABLED and context.module_feature_enabled(context.BASE_DIR, "terminal"),
        "changelog": True,
    }
    states["frp"] = states["frps"] or states["frpc"]
    return states
