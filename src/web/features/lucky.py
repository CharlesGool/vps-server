"""Lucky pages and actions for the operator console.

Host dependencies are supplied by ``ConsoleHandler.context`` so the feature
can be reused with another application context.
"""


class LuckyMixin:
    def page_lucky(self, lang, query_lang):
        t = self.context.STRINGS[lang]
        data = self.context.lucky_admin()
        if data is None:
            return self.send_html(404, self.render_page('Lucky', f'<div class="card">{self.context.html.escape(t["lucky_not_installed"])}</div>', lang))
        public = data.get('AllowInternetaccess') is True
        address = t['lucky_server_address'] if public else 'localhost'
        status = t['node_active'] if self.context._run_quiet(['systemctl', 'is-active', '--quiet', self.context.LUCKY_SERVICE]) else t['node_stopped']
        body = (f'<div class="card"><h1>Lucky</h1><p>{self.context.html.escape(t["lucky_admin_note"])}</p>'
                f'<p>{self.context.html.escape(t["lucky_admin"])}: {self.context.html.escape(address)}: '
                f'{self.private_value_control("lucky", "port", t)}</p>'
                f'{"<p>" + self.context.html.escape(t["lucky_ssh_tunnel"]) + "</p>" if not public else ""}'
                f'<p>{self.context.html.escape(t["frps_status"])}: {self.context.html.escape(status)}</p>'
                f'<p>{self.context.html.escape(t["lucky_account"])}: {self.private_value_control("lucky", "account", t)}</p>'
                f'<p>{self.context.html.escape(t["lucky_password"])}: {self.private_value_control("lucky", "credential", t, copy=True)}</p>'
                '</div><script src="/static/copy.js"></script><script src="/static/private-values.js"></script>')
        return self.send_html(200, self.render_page('Lucky', body, lang),
                              {**self.maybe_lang_cookie(query_lang), 'Cache-Control': 'no-store'})

    def route_lucky(self, method, path, parsed, lang, query_lang):
        if method == "GET" and path == "/lucky" and self.context.AUTH_ENABLED:
            self.page_lucky(lang, query_lang)
            return True
        return False


def lucky_admin(context, ):
    """Never expose Lucky credentials without console authentication."""
    try:
        data = context.json.loads(context.LUCKY_CONFIG.read_text())['BaseConfigure']
        port = data['AdminWebListenPort']
        if type(port) is not int or not 1 <= port <= 65535:
            return None
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return None
