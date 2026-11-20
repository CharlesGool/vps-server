"""JSON API for the security settings page.

Every route needs a password session with a recent admin re-verification
(``security_settings_valid``), the same rule the server-rendered page used.
Each change returns the whole page state so the page never shows stale data.
"""

from security_events import DEFAULT_BARK_SERVER, valid_bark_server


class SecurityApiMixin:
    API_ROUTES_SECURITY = {
        ("GET", "security"): "api_security",
        ("PUT", "security/password"): "api_security_password",
        ("PUT", "security/ip-access"): "api_security_ip_access",
        ("POST", "security/allowlist"): "api_security_allowlist_add",
        ("POST", "security/allowlist/remove"): "api_security_allowlist_remove",
        ("PUT", "security/login-mode"): "api_security_login_mode",
        ("POST", "security/certificates"): "api_security_cert_issue",
        ("POST", "security/certificates/revoke"): "api_security_cert_revoke",
        ("POST", "security/certificates/delete"): "api_security_cert_delete",
        ("PUT", "security/login-ban"): "api_security_login_ban",
        ("POST", "security/login-ban/clear"): "api_security_login_ban_clear",
        ("PUT", "security/console-access"): "api_security_console_access",
        ("POST", "security/console-access/add"): "api_security_console_access_add",
        ("POST", "security/console-access/remove"): "api_security_console_access_remove",
        ("POST", "security/sessions/revoke"): "api_security_session_revoke",
        ("POST", "security/sessions/revoke-others"): "api_security_sessions_revoke_others",
        ("PUT", "security/alerts"): "api_security_alerts",
        ("POST", "security/alerts/test"): "api_security_alerts_test",
        ("POST", "security/alerts/keys"): "api_security_alerts_key_add",
        ("POST", "security/alerts/keys/delete"): "api_security_alerts_key_delete",
    }

    # -- state -------------------------------------------------------------------

    def _security_allowed(self):
        token = self.get_cookie("session")
        if not self.context.session_valid(token):
            self.api_error(403, "password_session_required")
            return False
        if not self.context.security_settings_valid(token):
            self.api_error(403, "security_required")
            return False
        return True

    def _cert_setup_files(self, entry, bundle=None):
        """The one-click setup scripts for ``entry`` as downloadable files."""
        import cert_setup
        from client_cert import subject_cn
        patterns = self.cert_autoselect_patterns()
        if not patterns:
            return []
        lang, _ = self.resolve_lang(self.context.urlsplit(self.path))
        t = self.context.STRINGS[lang]
        subject, issuer = subject_cn(entry), self.context.CLIENT_AUTH.issuer_cn()
        files = []
        for system, build, mime in (("windows", cert_setup.windows_script, "application/octet-stream"),
                                    ("macos", cert_setup.macos_profile, "application/x-apple-aspen-config"),
                                    ("linux", cert_setup.linux_script, "application/octet-stream")):
            data = build(t, subject, issuer, patterns, bundle)
            files.append({"system": system, "name": cert_setup.file_name(system, subject), "type": mime,
                          "data": self.context.base64.b64encode(data).decode("ascii")})
        return files

    def security_state(self):
        context = self.context
        token = self.get_cookie("session")
        limiter, access, alerts, auth = (context.LOGIN_LIMITER, context.CONSOLE_ACCESS, context.ALERTS,
                                         context.CLIENT_AUTH)
        current_cert = self.client_certificate()
        client = self.client_ip()
        global_state, global_left = limiter.global_state() if limiter.global_max_attempts > 0 else ("normal", 0)
        alert_settings = alerts.settings()
        until = context._security_sessions.get(token, 0)
        return {
            "securityUntil": context.datetime.fromtimestamp(until, context.timezone.utc).isoformat(),
            "ipAccess": {"enabled": context.IP_ALLOWLIST.is_enabled(),
                         "allowlist": context.IP_ALLOWLIST.list_addresses(),
                         "loadError": bool(context.IP_ALLOWLIST.load_error)},
            "certificates": {
                "mode": auth.mode(), "modes": list(context.LOGIN_MODES),
                "current": ({"name": current_cert.get("name", ""), "serial": current_cert["serial"]}
                            if current_cert else None),
                "currentSetup": self._cert_setup_files(current_cert) if current_cert else [],
                "items": [{"name": item.get("name", ""), "serial": item["serial"],
                           "created": item.get("created", 0), "revoked": bool(item.get("revoked"))}
                          for item in reversed(auth.certificates())],
            },
            "loginBan": {
                "enabled": limiter.is_enabled(), "loadError": bool(limiter.load_error),
                "window": limiter.window_seconds, "maxAttempts": limiter.max_attempts,
                "lockout": limiter.lockout_seconds, "lockoutMax": limiter.lockout_max_seconds,
                "globalMaxAttempts": limiter.global_max_attempts, "globalLockout": limiter.global_lockout_seconds,
                "globalState": global_state, "globalRemaining": global_left,
                "sources": [{"ip": row["ip"], "state": row["state"], "remaining": row["remaining"],
                             "recent": row["recent"], "total": row["total"], "triggered": row["triggered"],
                             "last": row["last"]} for row in limiter.snapshot()],
            },
            "consoleAccess": {
                "enabled": access.enabled(), "loadError": bool(access.load_error),
                "networks": access.networks(), "current": client, "currentListed": access.listed(client),
                "recovery": f"python3 {context.WEB_CODE_DIR / 'console_access.py'} disable",
            },
            "sessions": {
                "ttl": context.SESSION_TTL_SECONDS, "idle": context.SESSION_IDLE_SECONDS,
                "items": [{**row, "device": self.describe_agent(row["agent"])}
                          for row in context.list_sessions(token)],
            },
            "alerts": {"server": alert_settings["server"], "configured": alert_settings["configured"],
                       "keys": alert_settings["keys"],
                       "newIp": alert_settings["new_ip"], "ban": alert_settings["ban"],
                       "loadError": bool(alerts.load_error)},
            "audit": context.AUDIT.recent(50),
        }

    def _security_reply(self, notice=None):
        state = self.security_state()
        if notice:
            state["notice"] = notice
        return self.api_ok(state)

    def _security_body(self):
        """The JSON body after the permission check, or None (response already sent)."""
        if not self._security_allowed():
            return None
        body = self.read_json()
        if body is None:
            self.api_error(400, "invalid_request")
        return body

    # -- routes ------------------------------------------------------------------

    def api_security(self):
        if self._security_allowed():
            self._security_reply()

    def api_security_password(self):
        body = self._security_body()
        if body is None:
            return
        password, confirm = body.get("password"), body.get("confirm")
        if not isinstance(password, str) or password != confirm:
            return self.api_error(400, "password_mismatch", field="confirm")
        try:
            self.context.change_admin_password(password)
        except ValueError:
            return self.api_error(400, "weak_password", field="password", reason=(
                "too_short" if len(password) < 12 else "too_long" if len(password) > 128 else "format"))
        except OSError:
            return self.api_error(500, "failed")
        self.audit("password_changed")
        # Every session ends with the old password, this one included.
        return self.api_ok(None, {"Set-Cookie": f"session=; {self.context.SESSION_COOKIE_ATTRS}; Max-Age=0"})

    def api_security_ip_access(self):
        body = self._security_body()
        if body is None:
            return
        if not isinstance(body.get("enabled"), bool):
            return self.api_error(400, "invalid_request")
        try:
            self.context.IP_ALLOWLIST.set_enabled(body["enabled"])
        except OSError:
            return self.api_error(500, "failed")
        self.audit("ip_login_on" if body["enabled"] else "ip_login_off")
        return self._security_reply()

    def _ip_change(self, add):
        body = self._security_body()
        if body is None:
            return
        address = body.get("address")
        if not isinstance(address, str):
            return self.api_error(400, "invalid_request", field="address", reason="required" if address is None else "type")
        context = self.context
        try:
            context.ipaddress.ip_address(address.strip())
        except ValueError:
            return self.api_error(400, "invalid_address", field="address", reason="format" if address.strip() else "required")
        try:
            canonical = context.normalized_private_ip(address.strip())
        except ValueError:
            return self.api_error(400, "address_not_allowed", field="address")
        if add and canonical in context.IP_ALLOWLIST.list_addresses():
            return self.api_error(400, "duplicate_address", field="address", reason="exists")
        try:
            context.IP_ALLOWLIST.change(canonical, add=add)
        except ValueError:
            return self.api_error(400, "allowlist_full" if add else "invalid_address")
        except OSError:
            return self.api_error(500, "failed")
        self.audit("ip_login_added" if add else "ip_login_removed", canonical)
        return self._security_reply()

    def api_security_allowlist_add(self):
        return self._ip_change(True)

    def api_security_allowlist_remove(self):
        return self._ip_change(False)

    def api_security_login_mode(self):
        body = self._security_body()
        if body is None:
            return
        mode = body.get("mode")
        if mode not in self.context.LOGIN_MODES:
            return self.api_error(400, "invalid_request", field="mode", reason="format" if mode else "required")
        # Only a browser that already holds an active certificate may demand one.
        if mode in ("cert", "both") and self.client_certificate() is None:
            return self.api_error(400, "client_cert_need_current")
        try:
            self.context.CLIENT_AUTH.set_mode(mode)
        except self.context.ClientCertError as exc:
            return self.api_error(400, exc.code)
        except OSError:
            return self.api_error(500, "client_cert_error")
        self.audit("login_mode_changed", mode)
        return self._security_reply()

    def api_security_cert_issue(self):
        body = self._security_body()
        if body is None:
            return
        name = body.get("name")
        if not isinstance(name, str):
            return self.api_error(400, "invalid_request", field="name", reason="required" if name is None else "type")
        try:
            bundle, password, entry = self.context.CLIENT_AUTH.issue(name)
        except self.context.ClientCertError as exc:
            return self.api_error(400, exc.code, **({"field": "name", "reason": "format"}
                                                    if exc.code == "client_cert_name_invalid" else {}))
        except OSError:
            return self.api_error(500, "client_cert_error")
        self.audit("cert_issued", name)
        state = self.security_state()
        state["issued"] = {
            "name": entry.get("name", ""), "serial": entry["serial"], "password": password,
            "bundle": {"name": "vps-server-" + entry["serial"][:8] + ".p12", "type": "application/x-pkcs12",
                       "data": self.context.base64.b64encode(bundle).decode("ascii")},
            "setup": self._cert_setup_files(entry, bundle),
        }
        return self.api_ok(state)

    def api_security_cert_revoke(self):
        body = self._security_body()
        if body is None:
            return
        serial = body.get("serial")
        if not isinstance(serial, str):
            return self.api_error(400, "invalid_request")
        auth, current = self.context.CLIENT_AUTH, self.client_certificate()
        # Revoking the certificate in use while it is required locks this browser out.
        if auth.required() and current and current["serial"] == serial:
            return self.api_error(400, "client_cert_keep_current")
        try:
            auth.revoke(serial)
        except self.context.ClientCertError as exc:
            return self.api_error(400, exc.code)
        except OSError:
            return self.api_error(500, "client_cert_error")
        self.audit("cert_revoked", serial[:8])
        return self._security_reply()

    def api_security_cert_delete(self):
        body = self._security_body()
        if body is None:
            return
        serial = body.get("serial")
        if not isinstance(serial, str):
            return self.api_error(400, "invalid_request")
        try:
            self.context.CLIENT_AUTH.delete(serial)
        except self.context.ClientCertError as exc:
            return self.api_error(400, exc.code)
        except OSError:
            return self.api_error(500, "client_cert_error")
        self.audit("cert_deleted", serial[:8])
        return self._security_reply()

    def api_security_login_ban(self):
        body = self._security_body()
        if body is None:
            return
        if not isinstance(body.get("enabled"), bool):
            return self.api_error(400, "invalid_request")
        try:
            self.context.LOGIN_LIMITER.set_enabled(body["enabled"])
        except OSError:
            return self.api_error(500, "login_ban_error")
        self.audit("login_ban_on" if body["enabled"] else "login_ban_off")
        return self._security_reply()

    def api_security_login_ban_clear(self):
        if self._security_allowed():
            self.context.LOGIN_LIMITER.clear()
            self.audit("login_ban_cleared")
            self._security_reply()

    def _console_access(self, change, field=None):
        """Run one change to the console access list; ``field`` is the request key an invalid value is in."""
        body = self._security_body()
        if body is None:
            return
        try:
            change(self.context.CONSOLE_ACCESS, body)
        except self.context.ConsoleAccessError as exc:
            reason = {"console_access_invalid": "format", "console_access_too_wide": "range"}.get(str(exc))
            return self.api_error(400, str(exc), **({"field": field, "reason": reason} if field and reason else {}))
        except (TypeError, KeyError, AttributeError):
            return self.api_error(400, "invalid_request")
        except OSError:
            return self.api_error(500, "console_access_error")
        return self._security_reply()

    def api_security_console_access(self):
        def change(access, body):
            if not isinstance(body.get("enabled"), bool):
                raise TypeError
            access.set_enabled(body["enabled"], current=self.client_ip())
            self.audit("console_access_on" if body["enabled"] else "console_access_off")
        return self._console_access(change)

    def api_security_console_access_add(self):
        def change(access, body):
            network = access.add(str(body["network"]).strip())
            self.audit("console_access_added", network)
        return self._console_access(change, "network")

    def api_security_console_access_remove(self):
        def change(access, body):
            network = access.remove(str(body["network"]), current=self.client_ip())
            self.audit("console_access_removed", network)
        return self._console_access(change)

    def api_security_session_revoke(self):
        body = self._security_body()
        if body is None:
            return
        token = self.get_cookie("session")
        target = body.get("id")
        if not isinstance(target, str):
            return self.api_error(400, "invalid_request")
        if self.context.session_id(token) == target:
            return self.api_error(400, "sessions_use_logout")
        if self.context.revoke_sessions(session_ids={target}):
            self.audit("session_revoked")
        return self._security_reply()

    def api_security_sessions_revoke_others(self):
        if self._security_allowed():
            count = self.context.revoke_sessions(keep=self.get_cookie("session"))
            if count:
                self.audit("sessions_revoked_others", str(count))
            self._security_reply()

    def api_security_alerts(self):
        body = self._security_body()
        if body is None:
            return
        server, key = body.get("server"), body.get("key", "")
        for name, value, kind in (("server", server, str), ("key", key, str), ("newIp", body.get("newIp"), bool),
                                  ("ban", body.get("ban"), bool)):
            if not isinstance(value, kind):
                return self.api_error(400, "invalid_request", field=name, reason="type")
        try:
            self.context.ALERTS.update(server=server, key=key, new_ip=body["newIp"], ban=body["ban"])
        except ValueError as exc:
            # Too many keys names no single input; otherwise the server or the key is not valid.
            field = (None if str(exc) != "invalid alert settings" else
                     "server" if not valid_bark_server(server.strip().rstrip("/") or DEFAULT_BARK_SERVER) else "key")
            return self.api_error(400, "alerts_invalid", **({"field": field, "reason": "format"} if field else {}))
        except OSError:
            return self.api_error(500, "alerts_error")
        self.audit("alerts_saved")
        return self._security_reply()

    def api_security_alerts_test(self):
        if not self._security_allowed():
            return
        error = self.context.ALERTS.send_test(self._alert_text("alert_test_title"),
                                              self._alert_text("alert_test_body"))
        if error is not None:
            return self.api_error(400, "alerts_not_configured" if error == "not configured" else "alerts_test_failed")
        return self._security_reply("alerts_test_sent")

    def api_security_alerts_key_add(self):
        body = self._security_body()
        if body is None:
            return
        try:
            self.context.ALERTS.add_key(body.get("key"))
        except ValueError as exc:
            return self.api_error(400, "alerts_invalid", **({"field": "key", "reason": "format" if body.get("key") else "required"}
                                                            if str(exc) == "invalid key" else {}))
        except OSError:
            return self.api_error(500, "alerts_error")
        self.audit("alerts_key_added")
        return self._security_reply()

    def api_security_alerts_key_delete(self):
        body = self._security_body()
        if body is None:
            return
        identifier = body.get("id")
        if not isinstance(identifier, str):
            return self.api_error(400, "invalid_request")
        try:
            removed = self.context.ALERTS.remove_key(identifier)
        except OSError:
            return self.api_error(500, "alerts_error")
        if not removed:
            return self.api_error(404, "not_found")
        self.audit("alerts_key_cleared")
        return self._security_reply()
