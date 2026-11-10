"""Lucky pages and actions for the operator console.

Host dependencies are supplied by ``ConsoleHandler.context`` so the feature
can be reused with another application context. ``/lucky/`` shows Lucky's
own admin page through ``lucky_proxy``; ``/lucky`` shows its state while it
is stopped.
"""

import lucky_proxy


class LuckyMixin:
    def page_lucky(self, lang, query_lang):
        t = self.context.STRINGS[lang]
        data = self.context.lucky_admin()
        # An uninstall keeps Lucky's configuration, so the file alone does not
        # mean the module is installed; offer the install button instead.
        if data is None or (self.context.STATE_FILE.is_file() and
                            "lucky" not in self.context.installed_modules(self.context.BASE_DIR)):
            return self.page_module_not_installed(lang, query_lang, "Lucky", "Lucky", module="lucky")
        running = (self.context._run_quiet(['systemctl', 'is-active', '--quiet', self.context.LUCKY_SERVICE])
                   and self.context.lucky_listener_active(data['AdminWebListenPort']))
        status = t['node_active'] if running else t['node_stopped']
        esc = self.context.html.escape
        body = (f'<h1>Lucky</h1><div class="card lucky-page" data-active="{esc(t["node_active"], quote=True)}" '
                f'data-stopped="{esc(t["node_stopped"], quote=True)}">'
                f'<dl class="lucky-facts"><div><dt>{esc(t["lucky_admin"])}</dt><dd class="lucky-address" role="status">—</dd></div>'
                f'<div><dt>{esc(t["frps_status"])}</dt><dd class="lucky-state">{esc(status)}</dd></div></dl>'
                f'<div class="lucky-actions"><button type="button" class="lucky-open" '
                f'data-error="{esc(t["lucky_open_failed"], quote=True)}" {"disabled" if not running else ""}>'
                f'{esc(t["lucky_open"])}</button></div><p class="error lucky-open-status" role="status" hidden></p>'
                '</div>'
                '<script src="/static/lucky.js" defer></script>')
        return self.send_html(200, self.render_page('Lucky', body, lang),
                              {**self.maybe_lang_cookie(query_lang), 'Cache-Control': 'no-store'})

    def route_lucky(self, method, path, parsed, lang, query_lang):
        if not self.context.AUTH_ENABLED:
            return False
        if path.startswith("/lucky/"):
            try:
                lucky_proxy.forward(self, self.context, method)
            except lucky_proxy.Unavailable:
                if method == "GET" and path == "/lucky/":
                    self.page_lucky(lang, query_lang)
                else:
                    self.send_json(502, {"error": "Lucky is not running"}, {"Cache-Control": "no-store"})
            return True
        if method == "GET" and path == "/lucky":
            data = self.context.lucky_admin()
            if (data and self.context._run_quiet(['systemctl', 'is-active', '--quiet', self.context.LUCKY_SERVICE])
                    and self.context.lucky_listener_active(data['AdminWebListenPort'])
                    and not (self.context.STATE_FILE.is_file() and
                             "lucky" not in self.context.installed_modules(self.context.BASE_DIR))):
                self.redirect("/lucky/", {"Cache-Control": "no-store"})
            else:
                self.page_lucky(lang, query_lang)
            return True
        if method == "GET" and path == "/lucky-status":
            data = self.context.lucky_admin()
            running = (bool(data) and self.context._run_quiet(
                ['systemctl', 'is-active', '--quiet', self.context.LUCKY_SERVICE])
                       and self.context.lucky_listener_active(data['AdminWebListenPort']))
            self.send_json(200, {"running": running}, {"Cache-Control": "no-store"})
            return True
        return False


def lucky_admin(context, ):
    """Read bootstrap settings, then prefer Lucky's actual admin listener."""
    try:
        base = context.json.loads(context.LUCKY_CONFIG.read_text())['BaseConfigure']
        data = {"AdminWebListenPort": base["AdminWebListenPort"], "_scheme": "http"}
        found = context.detect_lucky_admin()
        if found:
            data["AdminWebListenPort"], data["_scheme"] = found
        port = data['AdminWebListenPort']
        if type(port) is not int or not 1 <= port <= 65535:
            return None
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return None
