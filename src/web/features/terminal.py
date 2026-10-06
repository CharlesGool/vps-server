"""Browser terminal page; PTY handling is isolated in terminal_session."""

import terminal_session


class TerminalMixin:
    def page_terminal(self, lang, query_lang):
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        if not self.context.AUTH_ENABLED or not self.context.module_feature_enabled(self.context.BASE_DIR, "terminal"):
            return self.send_html(404, "Not found")
        token = self.get_cookie("session")
        if not self.context.security_settings_valid(token):
            return self.page_security_verify(lang, next_page="terminal")
        ws_token = self.context.access_csrf_token(token, "terminal")
        body = (f'<h1>{esc(t["terminal_title"])}</h1>'
                f'<div class="card wide terminal-page" data-token="{esc(ws_token, quote=True)}" '
                f'data-disconnected="{esc(t["terminal_disconnected"], quote=True)}">'
                '<p class="terminal-status" role="status"></p>'
                '<div class="terminal-frame"><div class="terminal-screen" tabindex="0"></div></div></div>'
                '<link rel="stylesheet" href="/static/third_party/xterm/xterm.css">'
                '<script src="/static/third_party/xterm/xterm.js"></script>'
                '<script src="/static/third_party/xterm/addon-fit.js"></script>'
                '<script src="/static/terminal.js" defer></script>')
        return self.send_html(200, self.render_page(t["terminal_title"], body, lang, back_href="/"),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def route_terminal(self, method, path, parsed, lang, query_lang):
        if method == "GET" and path == "/terminal":
            self.page_terminal(lang, query_lang)
            return True
        if method == "GET" and path == "/terminal/ws":
            terminal_session.serve(self, self.context, parsed)
            return True
        return False
