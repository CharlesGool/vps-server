"""The Vue single-page console (web/dist) and its JSON API.

Pages listed in ``SPA_PAGES`` are served as ``index.html``; the browser then
reads and changes state through ``/api/*``. Every other page is still
rendered by its Python feature until it is migrated.
"""

import re

# Page paths the single-page console handles. Grows as pages are migrated.
SPA_PAGES = {"/", "/login", "/changelog", "/settings", "/settings/security", "/settings/modules", "/settings/logs",
             "/speedtest", "/iperf", "/portfwd", "/visitors", "/terminal", "/files", "/backup", "/backup/restore", "/tasks", "/closed", "/tailscale", "/domains", "/domains/log", "/ipcert", "/frps", "/frpc", "/frpc/edit", "/proxy",
             "/monitor", "/system", "/updates", "/processes", "/services", "/ports",
             "/filemanager", "/fleet"}
# Component and scene samples; only development and test builds have these
# routes, a production build sends them back to the home page.
SPA_PREFIXES = ("/showcase", "/scenes")


def is_spa_page(path):
    return path in SPA_PAGES or any(path == p or path.startswith(p + "/") for p in SPA_PREFIXES)
# Built files at the root of web/dist, besides index.html.
SPA_ROOT_FILES = {"favicon.svg", "appearance.js"}
_ASSET_NAME = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_TYPES = {".js": "application/javascript", ".css": "text/css", ".svg": "image/svg+xml",
          ".woff2": "font/woff2", ".woff": "font/woff", ".png": "image/png", ".json": "application/json"}
API_BODY_LIMIT = 16 * 1024
# API names of the switchable system features: (prefix, feature). The first match wins.
FEATURE_APIS = (("monitor/alerts", "monitor"), ("monitor", "monitor"), ("system/updates", "updates"),
                ("system/processes", "processes"), ("system/services", "services"), ("system/ports", "ports"),
                ("system", "system"), ("fm/", "filemanager"), ("fleet", "fleet"), ("backup", "backup"),
                ("tasks", "tasks"))


def feature_of(name):
    return next((feature for prefix, feature in FEATURE_APIS if name == prefix or name.startswith(prefix + "/")
                 or (prefix.endswith("/") and name.startswith(prefix))), None)


def spa_dir(context):
    return context.BASE_DIR / "web" / "dist"


class SpaMixin:
    # -- files ---------------------------------------------------------------

    def serve_spa_file(self, path):
        """Serve /assets/<name> and the few root files; True when handled."""
        if path.startswith("/assets/"):
            name, relative, cache = path[len("/assets/"):], None, "public, max-age=31536000, immutable"
            if _ASSET_NAME.match(name):
                relative = ("assets", name)
        elif path.lstrip("/") in SPA_ROOT_FILES:
            relative, cache = (path.lstrip("/"),), "no-cache"
        else:
            return False
        file_path = spa_dir(self.context).joinpath(*relative) if relative else None
        content_type = _TYPES.get(file_path.suffix) if file_path else None
        if not content_type or not file_path.is_file():
            self.send_html(404, "not found")
            return True
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(data)
        return True

    def serve_spa_page(self):
        index = spa_dir(self.context) / "index.html"
        try:
            data = index.read_bytes()
        except OSError:
            return self.send_html(503, "Console UI is not built", {"Cache-Control": "no-store"})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def notice_page(self, status, title, text, lang, headers=None):
        """A small standalone page for the few answers that are not the single-page UI
        (an unknown path, a device without the required certificate). Light and dark follow the system."""
        esc = self.context.html.escape
        html_lang = {"zh_cn": "zh-CN", "en": "en", "es": "es"}.get(lang, "en")
        page = (f'<!doctype html><html lang="{html_lang}"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width, initial-scale=1">'
                f'<title>{esc(title)}</title><link rel="icon" href="/favicon.svg">'
                '<style>:root{color-scheme:light dark;--bg:#f7f8fb;--card:#fff;--fg:#1d2433;--muted:#5b6474;--line:#dde2ea}'
                '@media (prefers-color-scheme:dark){:root{--bg:#0f1218;--card:#171b23;--fg:#e6e9ef;--muted:#a0a8b6;--line:#2a303b}}'
                'body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--fg);'
                'font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}'
                'main{box-sizing:border-box;width:min(100% - 32px,480px);padding:24px;border:1px solid var(--line);'
                'border-radius:12px;background:var(--card)}h1{margin:0 0 8px;font-size:24px;line-height:32px}'
                'p{margin:0;color:var(--muted)}a{color:inherit}</style></head>'
                f'<body><main><h1>{esc(title)}</h1><p>{esc(text)}</p></main></body></html>')
        return self.send_html(status, page, {"Cache-Control": "no-store", **(headers or {})})

    # -- JSON helpers ----------------------------------------------------------

    def query_params(self):
        return self.context.parse_qs(self.context.urlsplit(self.path).query)

    def api_error(self, status, code, **extra):
        return self.send_json(status, {"error": code, **extra}, {"Cache-Control": "no-store"})

    def api_ok(self, obj=None, headers=None):
        if obj is None:
            self.send_response(204)
            self.send_header("Cache-Control", "no-store")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        return self.send_json(200, obj, {"Cache-Control": "no-store", **(headers or {})})

    def same_origin(self):
        """Browsers send Origin on cross-site requests; refuse those that do not match."""
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        host = self.headers.get("Host", "")
        return origin in (f"https://{host}", f"http://{host}")

    def read_json_large(self, limit):
        """read_json for the few requests that carry a whole file (the file manager's editor)."""
        return self.read_json(limit)

    def read_json(self, limit=API_BODY_LIMIT):
        """The request's JSON object, or None. Requiring application/json keeps
        other sites from posting here without a CORS preflight."""
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            return None
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            return None
        if not 0 < length <= limit:
            return None
        try:
            value = self.context.json.loads(self.rfile.read(length).decode("utf-8"))
            # JSON escapes can carry lone surrogates ("\\udc80") that no UTF-8 text has; refuse them here
            # rather than fail later wherever a value is encoded.
            self.context.json.dumps(value, ensure_ascii=False).encode("utf-8")
        except (UnicodeError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    # -- session -----------------------------------------------------------------

    def session_cookie(self, token):
        return {"Set-Cookie": f"session={token}; {self.context.SESSION_COOKIE_ATTRS}; "
                              f"Max-Age={self.context.SESSION_TTL_SECONDS}"}

    def session_info(self, token=None):
        context = self.context
        token = token if token is not None else self.get_cookie("session")
        password = context.AUTH_ENABLED and context.session_valid(token)
        ip = context.AUTH_ENABLED and not password and context.ip_session_valid(token, self.peer_ip())
        info = {"version": context.VERSION_LABEL, "login": context.AUTH_ENABLED,
                "authenticated": (not context.AUTH_ENABLED) or password or ip,
                "loginMethods": {"password": context.CLIENT_AUTH.password_login_allowed(),
                                 "certificate": context.CLIENT_AUTH.cert_login_allowed(),
                                 "certificatePresented": self.client_certificate() is not None}}
        if password:
            info["method"] = context._session_meta.get(token, {}).get("method", "password")
            if context.security_settings_valid(token):
                until = context._security_sessions.get(token, 0)
                info["securityUntil"] = context.datetime.fromtimestamp(until, context.timezone.utc).isoformat()
        elif ip:
            info["method"] = "ip"
        if info["authenticated"]:
            info["serverLabel"] = context.server_label()
        return info

    def route_api(self, method, path):
        """Dispatch /api/*; True when handled."""
        if not path.startswith("/api/"):
            return False
        name = path[len("/api/"):]
        if method != "GET" and not self.same_origin():
            return self.api_error(403, "cross_origin") or True
        public = {("GET", "session"): self.api_session, ("POST", "login"): self.api_login,
                  ("POST", "login/ip"): self.api_login_ip, ("POST", "login/cert"): self.api_login_cert,
                  ("POST", "logout"): self.api_logout}
        handler = public.get((method, name))
        if handler:
            handler()
            return True
        if not self.is_authenticated():
            self.api_error(401, "unauthenticated")
            return True
        handler = self.private_api_routes().get((method, name))
        feature = feature_of(name) if handler else None
        if feature and not self.context.module_feature_enabled(self.context.BASE_DIR, feature):
            self.api_error(403, "feature_closed", url="/closed?module=" + feature)
            return True
        if handler:
            getattr(self, handler)()
        else:
            self.api_error(404, "not_found")
        return True

    API_ROUTES_SESSION = {("POST", "security/verify"): "api_security_verify"}

    @classmethod
    def private_api_routes(cls):
        """Merge every mixin's API_ROUTES_* table: {(method, name): handler name}."""
        routes = getattr(cls, "_api_routes", None)
        if routes is None:
            routes = {}
            for attribute in dir(cls):
                if attribute.startswith("API_ROUTES_"):
                    routes.update(getattr(cls, attribute))
            cls._api_routes = routes
        return routes

    def api_session(self):
        return self.api_ok(self.session_info())

    def _check_limiter(self, blocked_event):
        allowed, retry_after = self.context.LOGIN_LIMITER.check(self.client_ip())
        if not allowed:
            self.audit(blocked_event)
            self.api_error(429, "too_many_attempts", retryAfter=retry_after)
        return allowed

    def _password_matches(self, submitted):
        return isinstance(submitted, str) and self.context.hmac.compare_digest(
            submitted.encode("utf-8"), self.context.ADMIN_PASSWORD.encode("utf-8"))

    def _start_session(self, method, security_verified):
        previous = self.get_cookie("session")
        if previous:
            self.context.destroy_session(previous)
        token = self.context.create_session(security_verified=security_verified, ip=self.client_ip(),
                                            agent=self.user_agent(), method=method)
        return self.api_ok(self.session_info(token), self.session_cookie(token))

    def api_login(self):
        if not self.context.AUTH_ENABLED:
            return self.api_error(404, "not_found")
        body = self.read_json()
        if body is None:
            return self.api_error(400, "invalid_request")
        if not self._check_limiter("login_blocked"):
            return
        if not self.context.CLIENT_AUTH.password_login_allowed():
            return self.api_error(403, "password_disabled")
        if not self._password_matches(body.get("password")):
            self.login_failed("login_fail")
            return self.api_error(401, "invalid_password")
        self.login_succeeded("password")
        return self._start_session("password", security_verified=True)

    def api_login_cert(self):
        if not self.context.AUTH_ENABLED:
            return self.api_error(404, "not_found")
        if not self.context.CLIENT_AUTH.cert_login_allowed():
            return self.api_error(403, "certificate_disabled")
        if self.client_certificate() is None:
            return self.api_error(401, "certificate_missing")
        self.login_succeeded("certificate")
        # Not security-verified: the terminal and security settings still ask for the password.
        return self._start_session("certificate", security_verified=False)

    def api_login_ip(self):
        context = self.context
        if not context.AUTH_ENABLED:
            return self.api_error(404, "not_found")
        address = self.client_address[0]
        if context.TRUST_PROXY or self.caddy_proxied() or not context.IP_ALLOWLIST.contains(address):
            return self.api_error(403, "ip_not_allowed")
        self.login_succeeded("ip")
        token = context.create_ip_session(address, self.user_agent())
        return self.api_ok(self.session_info(token), self.session_cookie(token))

    def api_logout(self):
        token = self.get_cookie("session")
        if token:
            if self.context.session_valid(token) or token in self.context._ip_sessions:
                self.audit("logout")
            self.context.destroy_session(token)
        return self.api_ok(None, {"Set-Cookie": f"session=; {self.context.SESSION_COOKIE_ATTRS}; Max-Age=0"})

    def api_security_verify(self):
        context = self.context
        token = self.get_cookie("session")
        if not context.session_valid(token):
            # IP-only sessions never get security permission.
            return self.api_error(403, "password_session_required")
        body = self.read_json()
        if body is None:
            return self.api_error(400, "invalid_request")
        if not self._check_limiter("verify_blocked"):
            return
        if not self._password_matches(body.get("password")):
            self.login_failed("verify_fail")
            return self.api_error(401, "invalid_password")
        context.LOGIN_LIMITER.record_success(self.client_ip())
        self.audit("verify_ok")
        method = context._session_meta.get(token, {}).get("method", "password")
        return self._start_session(method, security_verified=True)
