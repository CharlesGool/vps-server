"""Lucky pages and actions for the operator console.

Host dependencies are supplied by ``ConsoleHandler.context`` so the feature
can be reused with another application context.
"""


class LuckyMixin:
    def page_lucky(self, lang, query_lang):
        t = self.context.STRINGS[lang]
        data = self.context.lucky_admin()
        if data is None:
            return self.page_module_not_installed(lang, query_lang, "Lucky", "Lucky")
        running = (self.context._run_quiet(['systemctl', 'is-active', '--quiet', self.context.LUCKY_SERVICE])
                   and self.context.lucky_listener_active(data['AdminWebListenPort']))
        status = t['node_active'] if running else t['node_stopped']
        body = (f'<div class="card lucky-page" data-active="{self.context.html.escape(t["node_active"], quote=True)}" '
                f'data-stopped="{self.context.html.escape(t["node_stopped"], quote=True)}"><h1>Lucky</h1>'
                f'<p>{self.context.html.escape(t["lucky_admin"])}: <span class="lucky-address" role="status">—</span></p>'
                f'<p>{self.context.html.escape(t["frps_status"])}: <span class="lucky-state">{self.context.html.escape(status)}</span></p>'
                f'<button type="button" class="lucky-open" '
                f'data-error="{self.context.html.escape(t["lucky_open_failed"], quote=True)}" {"disabled" if not running else ""}>'
                f'{self.context.html.escape(t["lucky_open"])}</button><p class="error lucky-open-status" role="status" hidden></p>'
                '</div>'
                '<script src="/static/lucky.js" defer></script>')
        return self.send_html(200, self.render_page('Lucky', body, lang),
                              {**self.maybe_lang_cookie(query_lang), 'Cache-Control': 'no-store'})

    def route_lucky(self, method, path, parsed, lang, query_lang):
        if method == "GET" and path == "/lucky" and self.context.AUTH_ENABLED:
            self.page_lucky(lang, query_lang)
            return True
        if method == "GET" and path == "/lucky/status" and self.context.AUTH_ENABLED:
            data = self.context.lucky_admin()
            running = (bool(data) and self.context._run_quiet(
                ['systemctl', 'is-active', '--quiet', self.context.LUCKY_SERVICE])
                       and self.context.lucky_listener_active(data['AdminWebListenPort']))
            self.send_json(200, {"port": data['AdminWebListenPort'] if data else None,
                                 "scheme": data.get('_scheme', 'http') if data else 'http',
                                 "running": running}, {"Cache-Control": "no-store"})
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
