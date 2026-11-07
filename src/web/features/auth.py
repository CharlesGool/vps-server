"""Auth pages and actions for the operator console.

Host dependencies are supplied by ``ConsoleHandler.context`` so the feature
can be reused with another application context.
"""


class AuthMixin:
    def user_agent(self):
        return (self.headers.get("User-Agent") or "")[:200]

    def audit(self, event, detail=""):
        ip = self.client_ip()
        if event.endswith("_blocked"):
            # A banned client may keep hammering; one line a minute is enough.
            key = (event, self.context.LOGIN_LIMITER.key(ip))
            now = self.context.time.time()
            last = self.context._audit_blocked_seen
            if now - last.get(key, 0) < 60:
                return
            if len(last) > 1000:
                last.clear()
            last[key] = now
        self.context.AUDIT.record(event, ip, detail)

    def _alert_text(self, key, **values):
        label = self.context.server_label() or ""
        return self.context._log_text(key, server=label or "vps-server", **values)

    def login_succeeded(self, method):
        ip = self.client_ip()
        self.context.LOGIN_LIMITER.record_success(ip)
        self.audit("login_ok", method)
        key = self.context.LOGIN_LIMITER.key(ip)
        if self.context.KNOWN_LOGINS.remember(key):
            self.audit("login_new_ip", method)
            self.context.ALERTS.notify("new_ip", self._alert_text("alert_new_ip_title"),
                                       self._alert_text("alert_new_ip_body", ip=ip, method=self.context.STRINGS[
                                           self.context.DEFAULT_LANG].get("sessions_method_" + method, method)),
                                       dedupe=key)

    def login_failed(self, event_name):
        ip = self.client_ip()
        event = self.context.LOGIN_LIMITER.record_failure(ip)
        self.audit(event_name)
        if not event:
            return
        name = ("ban" if event["scope"] == "ip" else "global_ban") + ("" if event["banned"] else "_observed")
        self.audit(name, f'{event["key"]} {event["seconds"]}s')
        if event["banned"]:
            title_key, body_key = (("alert_ban_title", "alert_ban_body") if event["scope"] == "ip" else
                                   ("alert_global_title", "alert_global_body"))
            self.context.ALERTS.notify("ban", self._alert_text(title_key),
                                       self._alert_text(body_key, ip=event["key"], seconds=event["seconds"]),
                                       dedupe=event["scope"] + ":" + event["key"])

    def page_login(self, lang, query_lang, status=200, error=None, next_page="", password_error=True):
        t = self.context.STRINGS[lang]
        if not error and self.context.parse_qs(self.context.urlsplit(self.path).query).get("ip") == ["unavailable"]:
            error = t["login_ip_unavailable"]
            password_error = False
        error_html = f'<p class="error" id="login-error" role="alert">{self.context.html.escape(error)}</p>' if error else ""
        invalid = ' aria-invalid="true" aria-describedby="login-error"' if error and password_error else ""
        next_page = next_page if next_page in ("settings", "preferences", "changelog", "terminal") else ""
        next_input = f'<input type="hidden" name="next" value="{next_page}">' if next_page else ""
        changed = ('<p class="notice" role="status">' + self.context.html.escape(t["password_changed"]) + '</p>'
                   if self.context.parse_qs(self.context.urlsplit(self.path).query).get("changed") == ["1"] else "")
        ip_button = (f'<form method="post" action="/login/ip" class="login-ip-form">'
                     f'<button type="submit">{self.context.html.escape(t["login_ip_access"])}</button></form>')
        password_field = self.context.render_password_field(
            t, "login-password", t["password"], "password",
            f'autocomplete="current-password" autofocus required{invalid}')
        # Certificate login: offered whenever this connection presented an active
        # client certificate; once certificates are required it is the only way in.
        cert_required = self.context.CLIENT_AUTH.required()
        cert_button = (f'<form method="post" action="/login/cert" class="login-form login-cert-form">{next_input}'
                       f'<button type="submit" class="login-submit">{self.context.html.escape(t["login_cert"])}</button></form>'
                       if self.client_certificate() is not None else "")
        password_form = "" if cert_required else f"""
            <form method="post" action="/login" class="login-form">
              {next_input}
              {password_field}
              <button type="submit" class="login-submit">{self.context.html.escape(t['login'])}</button>
            </form>"""
        language_menu = (
            f'<div class="login-language-field app-login-language">'
            f'<details class="language-menu login-language-menu"><summary '
            f'aria-label="{self.context.html.escape(t["login_language"], quote=True)}: {self.context.html.escape(self.context.LANG_NAMES[lang], quote=True)}">'
            f'{self.context.html.escape(self.context.LANG_NAMES[lang])}</summary>'
            f'<div class="language-options">{self.context.render_lang_switcher(lang, "&next=" + next_page if next_page else "")}</div>'
            f'</details></div>')
        body = f"""
        <div class="login-shell">
          <div class="login-panel app-login-card">
            <span class="login-mark" aria-hidden="true">{self.context.ui_icon('lock-keyhole')}</span>
            <h1>{self.context.html.escape(t['login_heading'])}</h1>
            {changed}{error_html}
            {cert_button}{password_form}
            {ip_button}
            <div class="login-footer app-login-footer"><a class="login-version app-login-version" href="/changelog">{self.context.html.escape(self.context.VERSION_LABEL)}</a>{language_menu}</div>
          </div>
        </div>
        """
        headers = self.maybe_lang_cookie(query_lang)
        self.send_html(status, self.render_page(t['login'], body, lang, show_nav=False, bare=True), headers)

    def handle_login(self, lang):
        raw = self.read_body(self.context.LOGIN_BODY_LIMIT)
        ip = self.client_ip()
        allowed, retry_after = self.context.LOGIN_LIMITER.check(ip)
        if not allowed:
            self.audit("login_blocked")
            return self.page_login(
                lang, None, status=429,
                error=self.context.STRINGS[lang]["login_locked"].format(seconds=retry_after),
            )
        form = self.context.parse_qs(raw.decode("utf-8", errors="replace"))
        submitted = form.get("password", [""])[0]
        next_page = form.get("next", [""])[0]
        if self.context.CLIENT_AUTH.required():
            # The password is kept only for re-verifying sensitive actions.
            return self.page_login(lang, None, status=403, next_page=next_page, password_error=False,
                                   error=self.context.STRINGS[lang]["login_password_disabled"])
        if self.context.hmac.compare_digest(submitted.encode("utf-8"), self.context.ADMIN_PASSWORD.encode("utf-8")):
            self.login_succeeded("password")
            previous = self.get_cookie("session")
            if previous:
                self.context.destroy_session(previous)
            token = self.context.create_session(security_verified=True, ip=ip, agent=self.user_agent(),
                                                method="password")
            cookie = (
                f"session={token}; {self.context.SESSION_COOKIE_ATTRS}; "
                f"Max-Age={self.context.SESSION_TTL_SECONDS}"
            )
            destination = ("/settings/security" if next_page == "settings" else
                           "/settings" if next_page == "preferences" else
                           "/terminal" if next_page == "terminal" else
                           "/changelog" if next_page == "changelog" else "/")
            return self.redirect(destination,
                                 {"Set-Cookie": cookie})
        self.login_failed("login_fail")
        self.page_login(lang, None, status=401, error=self.context.STRINGS[lang]["wrong_password"],
                        next_page=next_page)

    def handle_cert_login(self, lang):
        raw = self.read_body(self.context.LOGIN_BODY_LIMIT)
        next_page = self.context.parse_qs(raw.decode("utf-8", errors="replace")).get("next", [""])[0]
        if self.client_certificate() is None:
            return self.page_login(lang, None, status=401, next_page=next_page, password_error=False,
                                   error=self.context.STRINGS[lang]["login_cert_missing"])
        previous = self.get_cookie("session")
        if previous:
            self.context.destroy_session(previous)
        # Not security-verified: the terminal and security settings still ask for the password.
        self.login_succeeded("certificate")
        token = self.context.create_session(ip=self.client_ip(), agent=self.user_agent(), method="certificate")
        cookie = (f"session={token}; {self.context.SESSION_COOKIE_ATTRS}; "
                  f"Max-Age={self.context.SESSION_TTL_SECONDS}")
        destination = ("/settings/verify" if next_page == "settings" else
                       "/settings" if next_page == "preferences" else
                       "/settings/verify?next=terminal" if next_page == "terminal" else
                       "/changelog" if next_page == "changelog" else "/")
        return self.redirect(destination, {"Set-Cookie": cookie, "Cache-Control": "no-store"})

    def page_client_cert_required(self, lang):
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        body = f"""
        <div class="login-shell">
          <div class="login-panel app-login-card">
            <span class="login-mark" aria-hidden="true">{self.context.ui_icon('lock-keyhole')}</span>
            <h1>{esc(t['client_cert_required_title'])}</h1>
            <p class="muted client-cert-gate-text">{esc(t['client_cert_required_text'])}</p>
          </div>
        </div>
        """
        self._close_after_response = True
        self.close_connection = True
        return self.send_html(403, self.render_page(t['client_cert_required_title'], body, lang,
                                                    show_nav=False, bare=True),
                              {"Cache-Control": "no-store"})

    def handle_ip_login(self, lang):
        if self.context.TRUST_PROXY or not self.context.IP_ALLOWLIST.contains(self.client_address[0]):
            return self.redirect("/login?ip=unavailable&next=settings",
                                 {"Cache-Control": "no-store"})
        self.login_succeeded("ip")
        token = self.context.create_ip_session(self.client_address[0], self.user_agent())
        cookie = (f"session={token}; {self.context.SESSION_COOKIE_ATTRS}; "
                  f"Max-Age={self.context.SESSION_TTL_SECONDS}")
        return self.redirect("/", {"Set-Cookie": cookie, "Cache-Control": "no-store"})

    def page_security_verify(self, lang, error=None, status=200, next_page=""):
        t = self.context.STRINGS[lang]
        token = self.get_cookie("session")
        password_field = self.context.render_password_field(
            t, "security-password", t["password"], "password",
            'autocomplete="current-password" required autofocus')
        body = f'''<div class="access-workspace access-verify-workspace"><section class="card access-card">
          <h1>{self.context.html.escape(t['access_verify_heading'])}</h1>
          {f'<p class="error" role="alert">{self.context.html.escape(error)}</p>' if error else ''}
          <form class="access-verify-form" method="post" action="/settings/verify" autocomplete="off">
            <input type="hidden" name="csrf" value="{self.context.access_csrf_token(token, 'verify')}">
            <input type="hidden" name="next" value="{self.context.html.escape(next_page, quote=True)}">
            {password_field}
            <button type="submit">{self.context.html.escape(t['access_verify_button'])}</button>
          </form></section></div>'''
        return self.send_html(status,
                              self.render_page(t['access_verify_heading'], body, lang,
                                               active="home" if next_page == "terminal" else "settings",
                                               back_href='/' if next_page == "terminal" else '/settings'),
                              {"Cache-Control": "no-store"})

    def handle_security_verify(self, lang):
        token = self.get_cookie("session")
        if not self.is_authenticated():
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/x-www-form-urlencoded":
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 < length <= self.context.LOGIN_BODY_LIMIT:
                raise ValueError
            form = self.context.parse_qs(self.rfile.read(length).decode("utf-8"),
                            keep_blank_values=True, strict_parsing=True)
            if set(form) not in ({"csrf", "password"}, {"csrf", "password", "next"}) or any(len(values) != 1 for values in form.values()):
                raise ValueError
        except (UnicodeError, ValueError):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if not self.context.hmac.compare_digest(form["csrf"][0], self.context.access_csrf_token(token, "verify")):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        next_page = form.get("next", [""])[0]
        if next_page not in ("", "frp", "terminal"):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        ip = self.client_ip()
        allowed, retry_after = self.context.LOGIN_LIMITER.check(ip)
        if not allowed:
            self.audit("verify_blocked")
            return self.page_security_verify(lang,
                                             error=self.context.STRINGS[lang]["login_locked"].format(seconds=retry_after),
                                             status=429, next_page=next_page)
        if not self.context.hmac.compare_digest(form["password"][0].encode("utf-8"),
                                                self.context.ADMIN_PASSWORD.encode("utf-8")):
            self.login_failed("verify_fail")
            return self.page_security_verify(lang, error=self.context.STRINGS[lang]["wrong_password"], status=401, next_page=next_page)
        self.context.LOGIN_LIMITER.record_success(ip)
        self.audit("verify_ok", next_page)
        method = self.context._session_meta.get(token, {}).get("method", "password")
        self.context.destroy_session(token)
        new_token = self.context.create_session(security_verified=True, ip=ip, agent=self.user_agent(),
                                                method=method)
        cookie = (f"session={new_token}; {self.context.SESSION_COOKIE_ATTRS}; "
                  f"Max-Age={self.context.SESSION_TTL_SECONDS}")
        return self.redirect("/frpc" if next_page == "frp" else "/terminal" if next_page == "terminal" else "/settings/security",
                             {"Set-Cookie": cookie, "Cache-Control": "no-store"})

    def handle_logout(self):
        token = self.get_cookie("session")
        if token:
            if self.context.session_valid(token) or token in self.context._ip_sessions:
                self.audit("logout")
            self.context.destroy_session(token)
        cookie = f"session=; {self.context.SESSION_COOKIE_ATTRS}; Max-Age=0"
        self.redirect("/login", {"Set-Cookie": cookie})




    def route_login(self, method, path, parsed, lang, query_lang):
        if method == "GET" and path == "/login":
            next_page = self.context.parse_qs(parsed.query).get("next", [""])[0]
            self.page_login(lang, query_lang, next_page=next_page)
        elif method == "POST" and path == "/login":
            self.handle_login(lang)
        elif method == "POST" and path == "/login/ip":
            self.handle_ip_login(lang)
        elif method == "POST" and path == "/login/cert":
            self.handle_cert_login(lang)
        elif method == "GET" and path == "/logout":
            self.handle_logout()
        else:
            return False
        return True



def _write_secret_file(context, path, value):
    path.write_text(value + "\n")
    context.os.chmod(path, 0o600)

def ensure_admin_password(context, ):
    if context.PASSWORD_FILE.exists():
        return context.PASSWORD_FILE.read_text().strip()
    password = context.secrets.token_urlsafe(15)
    context._write_secret_file(context.PASSWORD_FILE, password)
    print(context._log_text('log_admin_password', path=context.PASSWORD_FILE), file=context.sys.stderr)
    return password

def normalized_ip(context, value):
    """One canonical host address, never a CIDR, zone ID, or forwarded chain."""
    if not isinstance(value, str) or value != value.strip() or "%" in value:
        raise ValueError("invalid IP address")
    address = context.ipaddress.ip_address(value)
    return str(address.ipv4_mapped or address) if isinstance(address, context.ipaddress.IPv6Address) else str(address)

def normalized_private_ip(context, value):
    canonical = context.normalized_ip(value)
    if not any(context.ipaddress.ip_address(canonical) in network for network in context._PRIVATE_LOGIN_NETWORKS):
        raise ValueError("public or non-LAN IP address")
    return canonical

def _atomic_private_text(context, path, value):
    path = context.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = context.tempfile.mkstemp(prefix=".access-", dir=path.parent)
    try:
        context.os.fchmod(fd, 0o600)
        with context.os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(value)
            output.flush()
            context.os.fsync(output.fileno())
        context.os.replace(name, path)
        directory = context.os.open(path.parent, context.os.O_RDONLY | context.os.O_DIRECTORY)
        try:
            context.os.fsync(directory)
        finally:
            context.os.close(directory)
    finally:
        context.Path(name).unlink(missing_ok=True)

class IpAllowlist:
    def __init__(self, path):
        self.path = self.context.Path(path)
        self.lock = self.context.threading.RLock()
        self.addresses = set()
        self.enabled = True
        self.load_error = False
        if self.path.exists():
            try:
                document = self.context.json.loads(self.path.read_text(encoding="utf-8"))
                if (not isinstance(document, dict) or
                        set(document) not in ({"allowed_ips"}, {"allowed_ips", "enabled"}) or
                        not isinstance(document.get("enabled", True), bool) or
                        not isinstance(document["allowed_ips"], list) or
                        any(self.context.normalized_private_ip(item) != item for item in document["allowed_ips"]) or
                        len(document["allowed_ips"]) != len(set(document["allowed_ips"]))):
                    raise ValueError("invalid IP allowlist")
                self.addresses = set(document["allowed_ips"])
                self.enabled = document.get("enabled", True)
            except (OSError, ValueError, TypeError):
                self.load_error = True

    def contains(self, address):
        try:
            canonical = self.context.normalized_private_ip(address)
        except ValueError:
            return False
        with self.lock:
            return self.enabled and canonical in self.addresses

    def is_enabled(self):
        with self.lock:
            return self.enabled

    def set_enabled(self, enabled):
        if not isinstance(enabled, bool):
            raise ValueError("invalid IP access setting")
        with self.lock:
            self.context._atomic_private_text(self.path, self.context.json.dumps({"allowed_ips": sorted(self.addresses),
                                                       "enabled": enabled}) + "\n")
            self.enabled = enabled
            self.load_error = False

    def list_addresses(self):
        with self.lock:
            return sorted(self.addresses, key=lambda value: (self.context.ipaddress.ip_address(value).version,
                                                               int(self.context.ipaddress.ip_address(value))))

    def change(self, address, *, add):
        canonical = self.context.normalized_private_ip(address)
        with self.lock:
            candidate = set(self.addresses)
            if add:
                if len(candidate) >= 64 and canonical not in candidate:
                    raise ValueError("IP allowlist is full")
                candidate.add(canonical)
            else:
                if canonical not in candidate:
                    raise ValueError("IP address is not listed")
                candidate.remove(canonical)
            if candidate != self.addresses:
                self.context._atomic_private_text(self.path, self.context.json.dumps({"allowed_ips": sorted(candidate),
                                                           "enabled": self.enabled}) + "\n")
                self.addresses = candidate
                self.load_error = False
        return canonical

def ensure_console_port(context, ):
    """Explicit VPSSRV_CONSOLE_PORT always wins and is never persisted.
    Otherwise pick a random port once and remember it — regenerating on every
    restart would make the console impossible to find again.
    """
    # "0" means auto, the same as unset — which is what .env.example ships and
    # what the documentation has always said. Treating it as a literal port
    # number binds port 0, and the kernel then hands out a different ephemeral
    # port on every restart, none of them written to the port file. Anyone who
    # copied .env.example to .env got a console that moved every time the
    # service restarted and a summary that could not name it.
    override = context.DATA_DIR / "console-port-override"
    if override.exists():
        return int(override.read_text().strip())
    env_port = context.os.environ.get("VPSSRV_CONSOLE_PORT", "").strip()
    if env_port and env_port != "0":
        return int(env_port)
    if context.CONSOLE_PORT_FILE.exists():
        return int(context.CONSOLE_PORT_FILE.read_text().strip())
    registered = {row[0] for row in context.console_port_rows(context.BASE_DIR.parent / "PORTS.md")[0]}
    for _ in range(100):
        port = 20000 + context.secrets.randbelow(40000)  # 20000-59999
        if port in registered:
            continue
        try:
            context.console_port_available(port)
        except ValueError:
            continue
        break
    else:
        raise RuntimeError("no available console port")
    context._write_secret_file(context.CONSOLE_PORT_FILE, str(port))
    print(context._log_text('log_console_port', port=port, path=context.CONSOLE_PORT_FILE), file=context.sys.stderr)
    return port

def ensure_session_secret(context, ):
    if context.SECRET_FILE.exists():
        return context.SECRET_FILE.read_text().strip()
    secret = context.secrets.token_hex(32)
    context._write_secret_file(context.SECRET_FILE, secret)
    return secret

def ensure_tls_files(context, ):
    """Return (cert_path, key_path), generating a self-signed pair if needed.

    Uses the bundled sing-box generator so an offline target needs no
    separate OpenSSL CLI package.
    """
    if context.TLS_CERT and context.TLS_KEY:
        cert, key = context.Path(context.TLS_CERT), context.Path(context.TLS_KEY)
        if not cert.exists() or not key.exists():
            raise SystemExit(
                f"VPSSRV_TLS_CERT/VPSSRV_TLS_KEY were set but not found: {cert}, {key}"
            )
        return cert, key

    context.CERT_DIR.mkdir(parents=True, exist_ok=True)
    context.os.chmod(context.CERT_DIR, 0o700)
    cert, key = context.CERT_DIR / "cert.pem", context.CERT_DIR / "key.pem"
    if cert.exists() and key.exists():
        return cert, key

    from tls_cert import create_self_signed
    create_self_signed(cert, key, "localhost")
    print(context._log_text('log_certificate', path=context.CERT_DIR), file=context.sys.stderr)
    return cert, key

def pick_lang(context, cookie_lang, query_lang, accept_language):
    for candidate in (query_lang, cookie_lang):
        if candidate in context.STRINGS:
            return candidate
    if accept_language:
        # Only the first (highest-priority) tag matters here.
        primary = accept_language.split(",")[0].strip().lower()
        if primary.startswith("zh"):
            return "zh_cn"
        for code in ("es", "en"):
            if primary == code or primary.startswith(code + "-"):
                return code
    return context.DEFAULT_LANG

def _new_meta(context, ip, agent, method):
    now = context.time.time()
    return {"created": now, "seen": now, "ip": str(ip or "")[:64],
            "agent": str(agent or "")[:200], "method": method}


def create_session(context, *, security_verified=False, ip="", agent="", method="password"):
    token = context.secrets.token_urlsafe(32)
    with context._sessions_lock:
        context._sessions[token] = context.time.time() + context.SESSION_TTL_SECONDS
        context._session_meta[token] = _new_meta(context, ip, agent, method)
        if security_verified:
            context._security_sessions[token] = context.time.time() + context.SECURITY_PERMISSION_SECONDS
        save_sessions(context)
    return token


def save_sessions(context):
    """Call while holding the session lock; keep login state across Web restarts."""
    state = {"password": context.hmac.new(context.SESSION_SECRET.encode(),
             context.ADMIN_PASSWORD.encode(), "sha256").hexdigest(),
             "sessions": context._sessions, "ip_sessions": context._ip_sessions,
             "security_sessions": context._security_sessions,
             "meta": context._session_meta}
    context._atomic_private_text(context.SESSION_STATE_FILE, context.json.dumps(state))
    context._sessions_saved_at = context.time.time()


def load_sessions(context):
    try:
        state = context.json.loads(context.SESSION_STATE_FILE.read_text())
        password_tag = context.hmac.new(context.SESSION_SECRET.encode(),
                       context.ADMIN_PASSWORD.encode(), "sha256").hexdigest()
        if not context.hmac.compare_digest(state["password"], password_tag):
            return
        now = context.time.time()
        context._sessions.update({token: expiry for token, expiry in state["sessions"].items()
                                  if isinstance(token, str) and isinstance(expiry, (int, float)) and expiry > now})
        context._ip_sessions.update({token: (entry[0], entry[1])
                                     for token, entry in state["ip_sessions"].items()
                                     if isinstance(token, str) and isinstance(entry, list) and len(entry) == 2
                                     and isinstance(entry[0], str) and isinstance(entry[1], (int, float)) and entry[1] > now})
        context._security_sessions.update({token: expiry for token, expiry in state["security_sessions"].items()
                                           if token in context._sessions and isinstance(expiry, (int, float)) and expiry > now})
        meta = state.get("meta", {})
        if isinstance(meta, dict):
            for token, entry in meta.items():
                if ((token in context._sessions or token in context._ip_sessions) and isinstance(entry, dict)
                        and all(isinstance(entry.get(field), (int, float)) for field in ("created", "seen"))
                        and all(isinstance(entry.get(field), str) for field in ("ip", "agent", "method"))):
                    context._session_meta[token] = {field: entry[field] for field in
                                                    ("created", "seen", "ip", "agent", "method")}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass


def _idle_expired(context, token, now):
    """Whether ``token`` went unused longer than the idle limit (lock held)."""
    if context.SESSION_IDLE_SECONDS <= 0:
        return False
    meta = context._session_meta.get(token)
    if meta is None:
        # Sessions saved before session details existed: start the clock now.
        context._session_meta[token] = _new_meta(context, "", "", "password")
        return False
    return now - meta["seen"] > context.SESSION_IDLE_SECONDS


def _drop(context, token):
    context._sessions.pop(token, None)
    context._ip_sessions.pop(token, None)
    context._security_sessions.pop(token, None)
    context._session_meta.pop(token, None)


def session_valid(context, token):
    if not token:
        return False
    with context._sessions_lock:
        expiry = context._sessions.get(token)
        if expiry is None:
            return False
        now = context.time.time()
        if expiry < now or _idle_expired(context, token, now):
            _drop(context, token)
            save_sessions(context)
            return False
        return True

def security_settings_valid(context, token):
    if not context.session_valid(token):
        return False
    with context._sessions_lock:
        expiry = context._security_sessions.get(token, 0)
        if expiry <= context.time.time():
            context._security_sessions.pop(token, None)
            save_sessions(context)
            return False
        return True

def create_ip_session(context, address, agent=""):
    token = context.secrets.token_urlsafe(32)
    with context._sessions_lock:
        context._ip_sessions[token] = (address, context.time.time() + context.SESSION_TTL_SECONDS)
        context._session_meta[token] = _new_meta(context, address, agent, "ip")
        save_sessions(context)
    return token

def ip_session_valid(context, token, address):
    if not token or context.TRUST_PROXY or not context.IP_ALLOWLIST.contains(address):
        return False
    with context._sessions_lock:
        entry = context._ip_sessions.get(token)
        if entry is None:
            return False
        saved_address, expiry = entry
        now = context.time.time()
        if expiry < now or _idle_expired(context, token, now):
            _drop(context, token)
            save_sessions(context)
            return False
        return context.hmac.compare_digest(saved_address, address)

def touch_session(context, token):
    """Mark ``token`` as used now; saved to disk at most once a minute."""
    if not token:
        return
    with context._sessions_lock:
        meta = context._session_meta.get(token)
        if meta is None or (token not in context._sessions and token not in context._ip_sessions):
            return
        now = context.time.time()
        meta["seen"] = now
        if now - getattr(context, "_sessions_saved_at", 0) >= 60:
            save_sessions(context)

def session_id(context, token):
    """A stable, non-secret handle for one session, safe to put in a page."""
    return context.hmac.new(context.SESSION_SECRET.encode(), f"sid:{token}".encode(),
                            "sha256").hexdigest()[:20]

def list_sessions(context, current=None):
    """Active sessions, most recently used first."""
    with context._sessions_lock:
        now = context.time.time()
        rows = []
        for token in list(context._sessions) + list(context._ip_sessions):
            expiry = context._sessions.get(token) or context._ip_sessions.get(token, ("", 0))[1]
            if expiry < now or _idle_expired(context, token, now):
                continue
            meta = context._session_meta.get(token, {})
            rows.append({"id": session_id(context, token), "current": token == current,
                         "ip": meta.get("ip", ""), "agent": meta.get("agent", ""),
                         "method": meta.get("method", "password"),
                         "created": meta.get("created", 0), "seen": meta.get("seen", 0)})
    return sorted(rows, key=lambda row: (not row["current"], -row["seen"]))

def revoke_sessions(context, *, session_ids=None, keep=None):
    """End sessions by id, or every session except ``keep``; return the count."""
    with context._sessions_lock:
        tokens = [token for token in list(context._sessions) + list(context._ip_sessions)
                  if token != keep and (session_ids is None or session_id(context, token) in session_ids)]
        for token in tokens:
            _drop(context, token)
        if tokens:
            save_sessions(context)
    return len(tokens)

def destroy_session(context, token):
    with context._sessions_lock:
        _drop(context, token)
        save_sessions(context)

def access_csrf_token(context, session, action):
    return context.hmac.new(context.SESSION_SECRET.encode(),
                    f"access:{session}:{action}".encode(), "sha256").hexdigest()

def change_admin_password(context, replacement):
    if not isinstance(replacement, str) or not 12 <= len(replacement) <= 128 or \
            replacement != replacement.strip() or any(ord(char) < 32 for char in replacement):
        raise ValueError("invalid new password")
    with context._password_lock:
        context._atomic_private_text(context.PASSWORD_FILE, replacement + "\n")
        context.ADMIN_PASSWORD = replacement
        with context._sessions_lock:
            context._sessions.clear()
            context._ip_sessions.clear()
            context._security_sessions.clear()
            context._session_meta.clear()
            save_sessions(context)

class LoginRateLimiter:
    """Failed-login counting with an optional, escalating temporary ban.

    Failures are counted per source key: an IPv4 address, or the /64 an
    IPv6 address belongs to, since one IPv6 host can rotate through a whole
    /64. Each repeat ban of the same key within a day lasts ten times longer
    than the last, up to ``lockout_max_seconds``. A global limit pauses
    password login for keys that never logged in successfully when failures
    from all keys together pass ``global_max_attempts`` within the window.

    The ban switch is persisted in ``state_path`` and defaults to on. With
    the ban off, failures are still counted and threshold hits still
    recorded, so detection can be tested without locking the tester out;
    such a hit is only flagged, and turning the ban back on does not turn
    an old flag into a lockout.
    """

    STATS_LIMIT = 100
    STRIKE_RESET_SECONDS = 24 * 3600
    ESCALATION = 10

    def __init__(self, max_attempts, window_seconds, lockout_seconds, state_path=None, *,
                 lockout_max_seconds=None, global_max_attempts=0, global_lockout_seconds=300,
                 is_known=None):
        self._max_attempts = max_attempts
        self._window = window_seconds
        self._lockout = lockout_seconds
        self._lockout_max = max(lockout_max_seconds or lockout_seconds, lockout_seconds)
        self._global_max = global_max_attempts
        self._global_lockout = global_lockout_seconds
        self._is_known = is_known or (lambda key: False)
        self._lock = self.context.threading.Lock()
        self._failures = {}       # key -> [failure timestamps within window]
        self._locked_until = {}   # key -> unix time the lockout ends (ban on)
        self._flagged_until = {}  # key -> same, but only displayed (ban off)
        self._strikes = {}        # key -> (bans so far, time of the last one)
        self._stats = {}          # key -> {"total", "triggered", "last"}
        self._global_failures = []
        self._global_until = 0
        self._global_flagged_until = 0
        self._state_path = self.context.Path(state_path) if state_path else None
        self.enabled = True
        self.load_error = False
        if self._state_path and self._state_path.exists():
            try:
                document = self.context.json.loads(self._state_path.read_text(encoding="utf-8"))
                if not isinstance(document, dict) or set(document) != {"enabled"} or \
                        not isinstance(document["enabled"], bool):
                    raise ValueError("invalid login ban state")
                self.enabled = document["enabled"]
            except (OSError, ValueError, TypeError):
                self.load_error = True

    @classmethod
    def key(cls, ip):
        """The address failures are counted under: IPv4 itself, IPv6 by /64."""
        ipaddress = cls.context.ipaddress
        try:
            address = ipaddress.ip_address(ip)
        except ValueError:
            return str(ip)
        if isinstance(address, ipaddress.IPv6Address):
            if address.ipv4_mapped:
                return str(address.ipv4_mapped)
            return str(ipaddress.ip_network(f"{address}/64", strict=False))
        return str(address)

    @property
    def max_attempts(self):
        return self._max_attempts

    @property
    def window_seconds(self):
        return self._window

    @property
    def lockout_seconds(self):
        return self._lockout

    @property
    def lockout_max_seconds(self):
        return self._lockout_max

    @property
    def global_max_attempts(self):
        return self._global_max

    @property
    def global_lockout_seconds(self):
        return self._global_lockout

    def is_enabled(self):
        with self._lock:
            return self.enabled

    def set_enabled(self, enabled):
        if not isinstance(enabled, bool):
            raise ValueError("invalid login ban setting")
        with self._lock:
            if self._state_path:
                self.context._atomic_private_text(self._state_path,
                                                  self.context.json.dumps({"enabled": enabled}) + "\n")
            self.enabled = enabled
            self.load_error = False
            # Switching either way starts from a clean slate: no surprise
            # lockout from flags gathered while off, no stale lockout left.
            self._reset_active()

    def _reset_active(self):
        self._locked_until.clear()
        self._flagged_until.clear()
        self._failures.clear()
        self._strikes.clear()
        self._global_failures = []
        self._global_until = self._global_flagged_until = 0

    def check(self, ip):
        """(allowed, retry_after_seconds). retry_after is 0 when allowed."""
        key = self.key(ip)
        with self._lock:
            if not self.enabled:
                return True, 0
            now = self.context.time.time()
            remaining = self._locked_until.get(key, 0) - now
            if remaining <= 0:
                self._locked_until.pop(key, None)
            if self._global_until > now and not self._is_known(key):
                remaining = max(remaining, self._global_until - now)
            if remaining <= 0:
                return True, 0
            return False, int(remaining) + 1

    def record_failure(self, ip):
        """Count one failure.

        Returns None, or a dict describing the threshold hit this failure
        caused: {"scope": "ip" | "global", "key", "seconds", "banned"}.
        """
        key = self.key(ip)
        event = None
        with self._lock:
            now = self.context.time.time()
            enabled = self.enabled
            stats = self._stats.setdefault(key, {"total": 0, "triggered": 0, "last": 0})
            stats["total"] += 1
            stats["last"] = now
            attempts = [t for t in self._failures.get(key, []) if now - t < self._window]
            attempts.append(now)
            if len(attempts) >= self._max_attempts:
                strikes, last = self._strikes.get(key, (0, 0))
                strikes = strikes + 1 if now - last < self.STRIKE_RESET_SECONDS else 1
                self._strikes[key] = (strikes, now)
                seconds = min(self._lockout * self.ESCALATION ** (strikes - 1), self._lockout_max)
                stats["triggered"] += 1
                (self._locked_until if enabled else self._flagged_until)[key] = now + seconds
                self._failures.pop(key, None)
                event = {"scope": "ip", "key": key, "seconds": int(seconds), "banned": enabled}
            else:
                self._failures[key] = attempts
            if self._global_max > 0:
                self._global_failures = [t for t in self._global_failures if now - t < self._window]
                self._global_failures.append(now)
                active = max(self._global_until, self._global_flagged_until) > now
                if len(self._global_failures) >= self._global_max and not active:
                    if enabled:
                        self._global_until = now + self._global_lockout
                    else:
                        self._global_flagged_until = now + self._global_lockout
                    self._global_failures = []
                    if event is None:
                        event = {"scope": "global", "key": key, "seconds": int(self._global_lockout),
                                 "banned": enabled}
            self._prune(now)
        if event:
            log_key = (("log_login_ban" if event["banned"] else "log_login_ban_observed")
                       if event["scope"] == "ip" else
                       ("log_login_global" if event["banned"] else "log_login_global_observed"))
            print(self.context._log_text(log_key, ip=event["key"], count=self._max_attempts,
                                         seconds=event["seconds"]), file=self.context.sys.stderr)
        return event

    def record_success(self, ip):
        key = self.key(ip)
        with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)
            self._flagged_until.pop(key, None)
            self._strikes.pop(key, None)

    def clear(self):
        with self._lock:
            self._reset_active()
            self._stats.clear()

    def global_state(self):
        """("banned" | "flagged" | "normal", seconds left)."""
        with self._lock:
            now = self.context.time.time()
            if self._global_until > now:
                return "banned", int(self._global_until - now) + 1
            if self._global_flagged_until > now:
                return "flagged", int(self._global_flagged_until - now) + 1
            return "normal", 0

    def snapshot(self):
        """Rows for the security page, most recent failure first."""
        with self._lock:
            now = self.context.time.time()
            rows = []
            for key, stats in self._stats.items():
                locked = self._locked_until.get(key, 0) - now
                flagged = self._flagged_until.get(key, 0) - now
                left = max(locked, flagged)
                rows.append({
                    "ip": key,
                    "recent": len([t for t in self._failures.get(key, []) if now - t < self._window]),
                    "total": stats["total"],
                    "triggered": stats["triggered"],
                    "last": stats["last"],
                    "state": "banned" if locked > 0 else "flagged" if flagged > 0 else "normal",
                    "remaining": int(left) + 1 if left > 0 else 0,
                })
            return sorted(rows, key=lambda row: row["last"], reverse=True)

    def _prune(self, now):
        # Runs on every failure, not on a timer: cheap, and keeps a scan
        # hammering many source IPs from growing these dicts without bound.
        for table in (self._locked_until, self._flagged_until):
            for key in [k for k, until in table.items() if until < now]:
                del table[key]
        for key in [k for k, ts in self._failures.items()
                    if not any(now - t < self._window for t in ts)]:
            del self._failures[key]
        for key in [k for k, (_, last) in self._strikes.items() if now - last >= self.STRIKE_RESET_SECONDS]:
            del self._strikes[key]
        if len(self._stats) > self.STATS_LIMIT:
            keep = sorted(self._stats, key=lambda k: self._stats[k]["last"], reverse=True)[:self.STATS_LIMIT]
            self._stats = {key: self._stats[key] for key in keep}


def ip_scope(context, ip):
    """Classify an address so the UI can filter loopback/LAN noise out."""
    try:
        addr = context.ipaddress.ip_address(ip)
    except ValueError:
        return "public"
    if addr.is_loopback:
        return "loopback"
    if addr.is_private or addr.is_link_local:
        return "private"
    return "public"
