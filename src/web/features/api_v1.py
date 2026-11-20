"""The token API (``/api/v1/*``) for scripts and other consoles, and the token settings.

Requests carry ``Authorization: Bearer <token>`` instead of a session cookie.
They skip the session, the same-origin rule and the client-certificate gate
(a script holds no browser certificate), like Clash subscriptions. Wrong
tokens count as failed logins, so the login ban applies. ``read`` tokens see
status; ``write`` tokens may also restart this project's services, start an
upgrade or a backup. A source's own login ban applies to tokens; the global
pause after many failed logins does not, so it cannot lock out the central
management page. See doc/API.md.
"""

import os
import re
import subprocess
from pathlib import Path

import upgrade
from api_tokens import TokenError
from features import api_upgrade
from features.api_system import UNIT_RE, SELF_UNITS, services

# Services a write token may restart: this project's own, installed as unit files
# (a transient job such as the installer or an upgrade is not restarted).
PROJECT_UNIT_RE = re.compile(r"^(vps-server(-[A-Za-z0-9_.-]+)?|frpc@[A-Za-z0-9_.:-]+)\.service$")
UNIT_DIR = Path("/etc/systemd/system")


def restartable(unit):
    if not isinstance(unit, str) or not UNIT_RE.match(unit):
        return False
    if unit not in SELF_UNITS and not PROJECT_UNIT_RE.match(unit):
        return False
    template = unit.split("@", 1)[0] + "@.service" if "@" in unit else unit
    return (UNIT_DIR / template).is_file()


class TokenApiMixin:
    API_ROUTES_TOKENS = {
        ("GET", "security/tokens"): "api_security_tokens",
        ("POST", "security/tokens"): "api_security_tokens_create",
        ("POST", "security/tokens/delete"): "api_security_tokens_delete",
    }
    V1_ROUTES = {
        ("GET", "status"): ("read", "v1_status"),
        ("GET", "monitor"): ("read", "v1_monitor"),
        ("GET", "services"): ("read", "v1_services"),
        ("GET", "upgrade"): ("read", "v1_upgrade_status"),
        ("POST", "services/restart"): ("write", "v1_service_restart"),
        ("POST", "upgrade"): ("write", "v1_upgrade"),
        ("POST", "backup"): ("write", "v1_backup"),
    }

    # -- settings (session API) ---------------------------------------------------------

    def api_security_tokens(self):
        if not self._security_allowed():
            return
        return self.api_ok({"tokens": self.context.API_TOKENS.listing()})

    def api_security_tokens_create(self):
        if not self._security_allowed():
            return
        body = self.read_json()
        if body is None:
            return self.api_error(400, "invalid_request")
        try:
            token, row = self.context.API_TOKENS.create(body.get("name"), body.get("scope"))
        except TokenError as error:
            return self.api_error(400, str(error))
        self.audit("api_token_created", f'{row["name"]} ({row["scope"]})')
        return self.api_ok({"token": token, "tokens": self.context.API_TOKENS.listing()})

    def api_security_tokens_delete(self):
        if not self._security_allowed():
            return
        body = self.read_json()
        try:
            self.context.API_TOKENS.delete(body.get("id") if body else None)
        except TokenError as error:
            return self.api_error(404, str(error))
        self.audit("api_token_deleted")
        return self.api_ok({"tokens": self.context.API_TOKENS.listing()})

    # -- dispatch ----------------------------------------------------------------------------

    def route_token_api(self, method, path):
        """Handle /api/v1/*; True when handled."""
        if not path.startswith("/api/v1/"):
            return False
        context = self.context
        # Being managed is half of the central management page; its home switch closes both halves.
        if not context.module_feature_enabled(context.BASE_DIR, "fleet"):
            self.api_error(403, "feature_closed")
            return True
        ip = self.client_ip()
        allowed, retry_after = context.LOGIN_LIMITER.check(ip, global_pause=False)
        if not allowed:
            self.api_error(429, "too_many_attempts", retryAfter=retry_after)
            return True
        header = self.headers.get("Authorization", "")
        token = header[7:].strip() if header[:7].lower() == "bearer " else ""
        entry = context.API_TOKENS.verify(token, ip)
        if entry is None:
            self.login_failed("api_token_fail")
            self.api_error(401, "unauthenticated")
            return True
        route = self.V1_ROUTES.get((method, path[len("/api/v1/"):]))
        if route is None:
            self.api_error(404, "not_found")
            return True
        scope, handler = route
        if scope == "write" and entry.get("scope") != "write":
            self.api_error(403, "read_only_token")
            return True
        self._token_entry = entry
        getattr(self, handler)()
        return True

    # -- read ---------------------------------------------------------------------------------------

    def v1_status(self):
        context = self.context
        summary = self.monitor_summary()
        for key in ("chart", "trend"):
            summary.pop(key, None)
        try:
            total = self.dashboard_total()
        except Exception:  # noqa: BLE001 - status must answer even when the meter cannot
            total = None
        uname = os.uname()
        watched = [row for row in services() if row["unit"].startswith(("vps-server", "frpc", "tailscaled"))]
        return self.api_ok({"hostname": uname.nodename, "version": context.VERSION_LABEL,
                            "serverLabel": context.server_label(), "kernel": uname.release,
                            "resources": summary, "traffic": total,
                            "services": [{key: row[key] for key in ("unit", "active", "sub", "enabled")}
                                         for row in watched],
                            "failed": context.failed_units()})

    def v1_monitor(self):
        return self.api_ok(self.monitor_summary())

    def v1_services(self):
        return self.api_ok({"rows": services()})

    def v1_upgrade_status(self):
        info = api_upgrade.status(self.context)
        info["variant"] = upgrade.installed_variant(self.context.BASE_DIR)
        return self.api_ok(info)

    # -- write -----------------------------------------------------------------------------------------

    def v1_service_restart(self):
        body = self.read_json()
        unit = body.get("unit") if body else None
        if not isinstance(unit, str) or not UNIT_RE.match(unit):
            return self.api_error(400, "invalid_request")
        if not restartable(unit):
            return self.api_error(403, "unit_not_allowed")
        # try-restart: a stopped service stays stopped; "restart" would start any unit.
        command = ["systemctl", "try-restart", unit]
        if unit in SELF_UNITS:
            command.insert(1, "--no-block")
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
        except (OSError, subprocess.SubprocessError):
            return self.api_error(500, "failed")
        if result.returncode:
            return self.api_error(400, "service_failed", detail=result.stderr.strip()[-300:])
        self.audit("service_restart", f'{unit} (API: {self._token_entry.get("name")})')
        return self.api_ok()

    def v1_upgrade(self):
        body = self.read_json() or {}
        version = body.get("version")
        # Without a variant, the package this host was installed from (an offline host stays offline).
        variant = body.get("variant")
        if version is not None and (not isinstance(version, str) or not api_upgrade.VERSION_RE.match(version)):
            return self.api_error(400, "invalid_request")
        if variant not in (None, "online", "offline"):
            return self.api_error(400, "invalid_request")
        error = api_upgrade.start(self.context, version, variant)
        if error:
            return self.api_error(409 if error == "busy" else 500, error)
        self.audit("upgrade_started", f'{version or "latest"} (API: {self._token_entry.get("name")})')
        return self.api_ok({"started": True})

    def v1_backup(self):
        import config_backup
        if not self.context.module_feature_enabled(self.context.BASE_DIR, "backup"):
            return self.api_error(403, "feature_closed")
        try:
            name = config_backup.create_backup("manual")
        except (OSError, ValueError, RuntimeError):
            return self.api_error(500, "failed")
        self.audit("backup_created", f'{name} (API: {self._token_entry.get("name")})')
        return self.api_ok({"name": name})
