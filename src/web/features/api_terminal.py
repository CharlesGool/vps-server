"""JSON API for the browser terminal: the WebSocket token, after the admin password check."""


class TerminalApiMixin:
    API_ROUTES_TERMINAL = {("GET", "terminal"): "api_terminal"}

    def api_terminal(self):
        context = self.context
        if not context.AUTH_ENABLED or not context.module_feature_enabled(context.BASE_DIR, "terminal"):
            return self.api_error(403, "feature_closed", url="/closed?module=terminal")
        # Same rule as the security settings: a password session verified in the last minutes.
        if not self._security_allowed():
            return
        return self.api_ok({"token": context.access_csrf_token(self.get_cookie("session"), "terminal")})
