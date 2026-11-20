"""JSON API for domain forwarding (Caddy + Cloudflare DNS) and the IP certificate.

Reads the module's state directly; every change still goes through the root
helper caddy_sites.py (``domains_apply``). Display texts (certificate, DNS,
access) are built here in the visitor's language, as the old page did.
"""

import time
from datetime import datetime, timezone

import ipaddress

from caddy_sites import (AUTH_USER_RE, CONFIG_DIR, SERVICE, SiteError, certificate_info, console_port, names,
                         normalize_host, read_history, read_sites, read_tokens, reserved_ports, valid_port, zone_of)
from field_errors import FieldError, details
from features.domains import ERRORS, WARNINGS, _read_json, access_entries, listening_ports
from features.modules import module_job_recent


def _host_of(body):
    """(request key, host) the site is added or edited under; host is None when it is not a valid name."""
    zone, key = body.get("zone"), "host"
    raw = body.get("host")
    if zone:
        key, name = "name", str(body.get("name") or "").strip().lower().strip(".")
        raw = f"{name}.{zone}" if name and name != "@" else zone
    try:
        return key, normalize_host(str(raw or "")[:253])
    except SiteError:
        return key, None


def site_problem(body, error):
    """The input caddy_sites.py refused a site or token for, as {"field", "reason"}; {} when not certain.

    The helper reports a code only, so the console checks the same rules again to tell the inputs apart."""
    key, host = _host_of(body)
    if error == "host_invalid":
        return {"field": key, "reason": "required" if not body.get(key) else "format"} if host is None else \
            {"field": "aliases", "reason": "format"}
    if error == "host_exists":
        try:
            sites = read_sites()
        except (OSError, ValueError):
            return {}
        if host is not None and body.get("action") != "edit" and any(host in names(site) for site in sites):
            return {"field": key, "reason": "exists"}
        return {"field": "aliases", "reason": "exists"}
    if error == "port_invalid":
        if body.get("target") == "console":
            return {"field": "target", "reason": "format"}
        port = body.get("port")
        return {"field": "port", "reason": "type" if type(port) is not int else
                "port_in_use" if valid_port(port) and port in reserved_ports() else "range"}
    if error == "allow_invalid":
        for entry in body.get("allowIps") or []:
            try:
                ipaddress.ip_network(str(entry).strip(), strict=False)
            except ValueError:
                if str(entry).strip():
                    return {"field": "allowIps", "reason": "format"}
        return {"field": "allowIps", "reason": "range"}
    if error == "auth_invalid":
        if not AUTH_USER_RE.fullmatch(str(body.get("authUser") or "").strip()):
            return {"field": "authUser", "reason": "format"}
        password = str(body.get("authPassword") or "")
        return {"field": "authPassword", "reason": "required" if not password else "too_short" if len(password) < 8
                else "too_long" if len(password) > 128 else "format"}
    if error == "zone_unknown":
        return {"field": "zone", "reason": "not_found"}
    if error in ("token_invalid", "token_exists"):
        return {"field": "token", "reason": "format" if error == "token_invalid" else "exists"}
    return {}


def _clock(stamp, pattern="%Y-%m-%d %H:%M"):
    return time.strftime(pattern, time.localtime(stamp)) if isinstance(stamp, (int, float)) else ""


class DomainsApiMixin:
    API_ROUTES_DOMAINS = {
        ("GET", "domains"): "api_domains",
        ("POST", "domains/add"): "api_domains_add",
        ("PUT", "domains/edit"): "api_domains_edit",
        ("POST", "domains/toggle"): "api_domains_toggle",
        ("POST", "domains/remove"): "api_domains_remove",
        ("POST", "domains/token"): "api_domains_token",
        ("POST", "domains/token/remove"): "api_domains_token_remove",
        ("GET", "domains/log"): "api_domains_log",
        ("GET", "ipcert"): "api_ipcert",
    }

    def _domains_t(self):
        lang, _ = self.resolve_lang(self.context.urlsplit(self.path))
        return self.context.STRINGS[lang]

    def _caddy_ready(self):
        """None when the page can be used, else the error already sent."""
        if "caddy" not in self.context.installed_modules(self.context.BASE_DIR):
            return False
        if not self.context.module_states()["caddy"]:
            self.api_error(403, "feature_closed", url="/closed?module=caddy")
            return None
        return True

    def domains_private_value(self, identifier, field):
        """The host's public address (``domain-ipv4``) or a site's port (``domain-site:<host>``)."""
        if identifier in ("domain-ipv4", "domain-ipv6") and field == "address":
            value = _read_json(CONFIG_DIR / "dns.json").get(identifier[7:])
        elif identifier.startswith("domain-site:") and field == "target-port":
            try:
                value = next((str(site["port"]) for site in read_sites()
                              if site["host"] == identifier[12:] and "port" in site), None)
            except (OSError, ValueError):
                value = None
        else:
            value = None
        if not value:
            raise ValueError("no such value")
        return str(value)

    def domains_state(self, message=None, warning=None):
        t = self._domains_t()
        try:
            sites = [site for site in read_sites() if not site.get("ip")]  # the IP certificate has its own page
        except (OSError, ValueError):
            sites = []
        dns = _read_json(CONFIG_DIR / "dns.json")
        tokens = read_tokens()
        zones = sorted({zone for item in tokens for zone in item["zones"]})
        listening = listening_ports()
        dns_sites = dns.get("sites", {}) if isinstance(dns.get("sites"), dict) else {}
        groups = {}
        for site in sites:
            groups.setdefault(site.get("zone") or zone_of(site["host"], zones) or "", []).append(site)

        def site_json(site):
            host = site["host"]
            zone = site.get("zone") or zone_of(host, zones)
            enabled = site.get("enabled", True)
            badges = [] if enabled else [{"tone": "neutral", "text": t["domains_site_off"]}]
            if not site.get("console") and enabled and listening is not None and site.get("port") not in listening:
                badges.append({"tone": "destructive", "text": t["domains_port_idle"]})
            cert = certificate_info(host)
            if cert:
                expiry, issuer = cert
                days = (expiry - datetime.now(timezone.utc)).days
                cert_text = t["domains_cert_detail"].format(issuer=issuer, date=expiry.strftime("%Y-%m-%d"), days=days)
                badges.append({"tone": "success" if days >= 14 else "warning", "text": t["domains_cert_ok"]})
            else:
                cert_text = t["domains_cert_pending_detail"]
                badges.append({"tone": "neutral", "text": t["domains_cert_pending"]})
            state = dns_sites.get(host) or {}
            if state.get("ok"):
                kinds = " + ".join(kind for kind, key in (("A", "a"), ("AAAA", "aaaa")) if state.get(key)) or "A"
                dns_text = t["domains_dns_detail"].format(
                    kinds=kinds, time=_clock(state.get("checked_at") or dns.get("checked_at") or 0))
                badges.append({"tone": "success", "text": "DNS " + t["domains_dns_ok"]})
            elif state.get("error"):
                dns_text = t.get("domains_" + str(state["error"]), t["domains_dns_pending"])
                badges.append({"tone": "destructive", "text": "DNS " + t["domains_dns_failed"]})
            else:
                dns_text = t["domains_dns_manual"] if not tokens else t["domains_dns_pending"]
                badges.append({"tone": "neutral", "text": "DNS " + t["domains_dns_pending"]})
            auth_user = (site.get("auth") or {}).get("user") if not site.get("console") else None
            access = []
            if site.get("allow_ips"):
                access.append(t["domains_allow_detail"].format(list=", ".join(site["allow_ips"])))
            if auth_user:
                access.append(t["domains_auth_detail"].format(user=auth_user))
            alias_states = [dns_sites.get(name) or {} for name in site.get("aliases", [])]
            aliases_text = (", ".join(site.get("aliases", [])) + " · DNS " + (
                t["domains_dns_ok"] if all(item.get("ok") for item in alias_states)
                else t["domains_dns_failed"] if any(item.get("error") for item in alias_states)
                else t["domains_dns_pending"])) if site.get("aliases") else ""
            options = [t[key] for key, on in (("domains_backend_tls_short", site.get("backend_tls")),
                                               ("domains_upstream_host_short", site.get("upstream_host"))) if on]
            return {
                "host": host, "zone": zone or "", "enabled": enabled, "console": bool(site.get("console")),
                "hasPort": "port" in site, "scheme": "https" if site.get("backend_tls") else "http",
                "backendTls": bool(site.get("backend_tls")), "upstreamHost": bool(site.get("upstream_host")),
                "options": " · ".join(options),
                "aliases": list(site.get("aliases", [])), "allowIps": list(site.get("allow_ips", [])),
                "authUser": (site.get("auth") or {}).get("user") or "",
                "addedAt": _clock(site.get("added_at"), "%Y-%m-%d") or "—",
                "badges": badges, "certText": cert_text, "dnsText": dns_text, "aliasesText": aliases_text,
                "accessText": " · ".join(access) or t["domains_access_open"],
            }

        history = [{"time": _clock(item.get("t", 0), "%m-%d %H:%M"),
                    "text": t.get("domains_event_" + item["event"], item["event"]).format(
                        host=item.get("host", ""), kind=item.get("kind", ""), value=item.get("value", ""),
                        old=item.get("old", ""))} for item in read_history(30)]
        return {
            "installed": True,
            "running": self.context._run_quiet(["systemctl", "is-active", "--quiet", SERVICE]),
            "dns": {"ipv4": bool(dns.get("ipv4")), "ipv6": bool(dns.get("ipv6")),
                    "checked": _clock(dns.get("checked_at")) or "—",
                    "error": dns.get("error") if dns.get("error") in WARNINGS and dns.get("error") != "dns_no_token" else None},
            "history": history,
            "zones": zones,
            "consoleTarget": bool(console_port()),
            "groups": [{"zone": zone, "sites": [site_json(site) for site in sorted(groups[zone], key=lambda s: s["host"])]}
                       for zone in sorted(groups, key=lambda name: (name == "", name))],
            "tokens": [{"id": item["id"], "name": item["name"] or t["domains_token_default_name"].format(number=index),
                        "state": "auth" if item.get("error") == "dns_auth" else "unreachable" if item.get("error") else "ok",
                        "checked": _clock(item.get("checked_at")),
                        "zones": [{"zone": zone, "sites": len(groups.get(zone, []))} for zone in item["zones"]]}
                       for index, item in enumerate(tokens, 1)],
            "message": message, "warning": warning,
        }

    def api_domains(self):
        ready = self._caddy_ready()
        if ready is None:
            return
        return self.api_ok(self.domains_state() if ready else {"installed": False})

    def _domains_reply(self, reply, success, body=None):
        """The page state after a change, or its error; with ``body``, the input an error is about."""
        if reply.get("ok"):
            warning = reply.get("warning") if reply.get("warning") in WARNINGS else None
            return self.api_ok(self.domains_state(success, warning))
        error = reply.get("error") if reply.get("error") in ERRORS else "failed"
        return self.api_error(400, error, **(site_problem(body, error) if body is not None else {}))

    def _domains_body(self):
        if self._caddy_ready() is not True:
            if "caddy" not in self.context.installed_modules(self.context.BASE_DIR):
                self.api_error(404, "not_found")
            return None
        body = self.read_json()
        if body is None:
            self.api_error(400, "invalid_request")
        return body

    @staticmethod
    def _domains_target(body):
        """The site settings shared by adding and editing, as caddy_sites.py takes them; FieldError when a
        value has the wrong type (answered as ``port_invalid``, the code this has always had)."""
        def lines(name, limit):
            value = body.get(name) or []
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise FieldError(name, "type")
            return [item.strip()[:253] for item in value if item.strip()][:limit]
        request = {"target": "console" if body.get("target") == "console" else "port",
                   "aliases": lines("aliases", 16), "allow_ips": lines("allowIps", 64),
                   "auth_user": str(body.get("authUser") or "")[:64],
                   "auth_password": str(body.get("authPassword") or "")[:128],
                   "auth_clear": body.get("authClear") is True}
        if request["target"] == "port":
            port = body.get("port")
            if type(port) is not int:
                raise FieldError("port", "required" if port is None else "type")
            request.update(port=port, backend_tls=body.get("backendTls") is True,
                           upstream_host=body.get("upstreamHost") is True)
        return request

    def api_domains_add(self):
        body = self._domains_body()
        if body is None:
            return
        try:
            request = self._domains_target(body)
        except FieldError as exc:
            return self.api_error(400, "port_invalid", **details(exc))
        request["action"] = "add"
        if body.get("zone"):
            request.update(zone=str(body["zone"])[:253], name=str(body.get("name") or "")[:200])
        else:
            request["host"] = str(body.get("host") or "")[:253]
        return self._domains_reply(self.domains_apply(request), "domains_added", body)

    def api_domains_edit(self):
        body = self._domains_body()
        if body is None:
            return
        try:
            request = self._domains_target(body)
        except FieldError as exc:
            return self.api_error(400, "port_invalid", **details(exc))
        request.update(action="edit", host=str(body.get("host") or "")[:253])
        return self._domains_reply(self.domains_apply(request), "domains_site_saved", {**body, "action": "edit"})

    def api_domains_toggle(self):
        body = self._domains_body()
        if body is None:
            return
        enable = body.get("enable") is True
        reply = self.domains_apply({"action": "enable" if enable else "disable", "host": str(body.get("host") or "")[:253]})
        return self._domains_reply(reply, "domains_site_enabled" if enable else "domains_site_disabled")

    def api_domains_remove(self):
        body = self._domains_body()
        if body is None:
            return
        reply = self.domains_apply({"action": "remove", "host": str(body.get("host") or "")[:253],
                                    "remove_dns": body.get("removeDns") is True})
        return self._domains_reply(reply, "domains_removed")

    def api_domains_token(self):
        body = self._domains_body()
        if body is None:
            return
        reply = self.domains_apply({"action": "token_add", "token": str(body.get("token") or "")[:200],
                                    "name": str(body.get("name") or "")[:80]})
        return self._domains_reply(reply, "domains_token_saved", body)

    def api_domains_token_remove(self):
        body = self._domains_body()
        if body is None:
            return
        reply = self.domains_apply({"action": "token_remove", "id": str(body.get("id") or "")[:40]})
        return self._domains_reply(reply, "domains_token_cleared")

    def api_domains_log(self):
        """The last requests Caddy logged for one site, newest first."""
        ready = self._caddy_ready()
        if ready is None:
            return None
        if not ready:
            return self.api_error(404, "not_found")
        host = self.context.parse_qs(self.context.urlsplit(self.path).query).get("host", [""])[0]
        try:
            known = {site["host"] for site in read_sites()}
        except (OSError, ValueError):
            known = set()
        if host not in known:
            return self.api_error(404, "not_found")
        rows = []
        for index, entry in enumerate(access_entries(host, 200)):
            request = entry.get("request") or {}
            duration = entry.get("duration")
            rows.append({"id": index, "time": _clock(entry.get("ts"), "%m-%d %H:%M:%S") or "—",
                         "client": str(request.get("client_ip") or request.get("remote_ip") or ""),
                         "method": str(request.get("method", "")), "path": str(request.get("uri", ""))[:200],
                         "status": entry.get("status") if isinstance(entry.get("status"), int) else None,
                         "duration": f"{duration * 1000:.0f} ms" if isinstance(duration, (int, float)) else ""})
        return self.api_ok({"host": host, "rows": rows})

    def api_ipcert(self):
        """HTTPS for the console at this host's public IPv4; switched on and off as a module job."""
        context = self.context
        if "caddy" not in context.installed_modules(context.BASE_DIR):
            return self.api_ok({"installed": False})
        t = self._domains_t()
        enabled = context.module_states()["ipcert"]
        try:
            ip_site = next((site for site in read_sites() if site.get("ip")), None)
        except (OSError, ValueError):
            ip_site = None
        facts = None
        if enabled and ip_site:
            cert = certificate_info(ip_site["host"])
            facts = {"url": f'https://{ip_site["host"]}:{console_port() or context.CONSOLE_PORT}/',
                     "issuer": cert[1] if cert else t["ipcert_pending_short"],
                     "expires": t["ipcert_expires_value"].format(
                         date=cert[0].strftime("%Y-%m-%d %H:%M"),
                         days=(cert[0] - datetime.now(timezone.utc)).days) if cert else "—"}
        job = self._module_job()
        now = context.time.time()
        running = (job.get("module") == "ipcert" and job.get("state") in ("queued", "running")
                   and module_job_recent(job, now, 900))
        failed = job.get("module") == "ipcert" and job.get("state") == "failed" and module_job_recent(job, now, 60)
        return self.api_ok({"installed": True, "enabled": enabled, "facts": facts,
                            "job": "running" if running else "failed" if failed else None})
