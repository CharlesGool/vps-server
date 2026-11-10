"""Domain forwarding page: subdomain -> local port through Caddy, DNS on Cloudflare.

Reads the module's state directly; every change goes through the root helper
caddy_sites.py, outside Web's sandbox.
"""

import json
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path

CONFIG_DIR = Path("/etc/vps-server-caddy")
DATA_DIR = Path("/var/lib/vps-server-caddy")
SERVICE = "vps-server-caddy.service"
NOTICES = ("domains_added", "domains_removed", "domains_token_saved", "domains_token_cleared")
ERRORS = ("host_invalid", "port_invalid", "host_exists", "host_missing", "too_many",
          "caddy_rejected", "token_invalid", "invalid", "failed")
WARNINGS = ("dns_auth", "dns_zone", "dns_unreachable", "dns_api", "dns_no_token", "dns_no_address")


def _read_json(path):
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def certificate_expiry(host):
    """When the certificate Caddy holds for host expires, or None."""
    for path in sorted((DATA_DIR / "certificates").glob(f"*/{host}/{host}.crt")):
        try:
            not_after = ssl._ssl._test_decode_cert(str(path))["notAfter"]
            return datetime.fromtimestamp(ssl.cert_time_to_seconds(not_after), timezone.utc)
        except (OSError, ValueError, KeyError, AttributeError):
            continue
    return None


class DomainsMixin:
    def domains_csrf(self):
        return self.context.access_csrf_token(self.get_cookie("session"), "domains")

    def domains_apply(self, request):
        """Run one change through the root helper; returns its JSON reply."""
        helper = self.context.WEB_CODE_DIR / "caddy_sites.py"
        command = ["systemd-run", "--pipe", "--wait", "--collect", "--quiet",
                   "--unit=vps-server-domains-edit", "/usr/bin/python3", str(helper), "apply"]
        try:
            result = self.context.subprocess.run(command, input=json.dumps(request).encode("utf-8"),
                                                 capture_output=True, timeout=120, check=False)
            return json.loads(result.stdout.decode("utf-8", "replace").strip().splitlines()[-1])
        except (OSError, ValueError, IndexError, self.context.subprocess.TimeoutExpired):
            return {"ok": False, "error": "failed"}

    def page_domains(self, lang, query_lang, parsed):
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        if "caddy" not in self.context.installed_modules(self.context.BASE_DIR):
            return self.page_module_not_installed(lang, query_lang, t["domains"], t["domains"], module="caddy")
        if not self.context.module_states()["caddy"]:
            return self.redirect("/closed?module=caddy", {"Cache-Control": "no-store"})
        query = self.context.parse_qs(parsed.query)
        messages = []
        msg = query.get("msg", [""])[0]
        if msg in NOTICES:
            messages.append(f'<p class="notice" role="status">{esc(t[msg])}</p>')
        error = query.get("error", [""])[0]
        if error in ERRORS:
            messages.append(f'<p class="error" role="alert">{esc(t["domains_error_" + error])}</p>')
        warning = query.get("warning", [""])[0]
        if warning in WARNINGS:
            messages.append(f'<p class="error" role="status">{esc(t["domains_" + warning])}</p>')

        try:
            sites = json.loads((CONFIG_DIR / "sites.json").read_text()).get("sites", [])
        except (OSError, ValueError, AttributeError):
            sites = []
        dns = _read_json(CONFIG_DIR / "dns.json")
        token_set = (CONFIG_DIR / "cloudflare-token").is_file()
        running = self.context._run_quiet(["systemctl", "is-active", "--quiet", SERVICE])
        csrf = esc(self.domains_csrf(), quote=True)

        checked = dns.get("checked_at")
        checked_text = (time.strftime("%Y-%m-%d %H:%M", time.localtime(checked))
                        if isinstance(checked, (int, float)) else "—")
        facts = (f'<dl class="lucky-facts">'
                 f'<div><dt>{esc(t["frps_status"])}</dt><dd>{esc(t["node_active"] if running else t["node_stopped"])}</dd></div>'
                 f'<div><dt>{esc(t["domains_ipv4"])}</dt><dd>{esc(dns.get("ipv4") or "—")}</dd></div>'
                 f'<div><dt>{esc(t["domains_ipv6"])}</dt><dd>{esc(dns.get("ipv6") or "—")}</dd></div>'
                 f'<div><dt>{esc(t["domains_dns_checked"])}</dt><dd>{esc(checked_text)}</dd></div>'
                 f'</dl>')
        if dns.get("error") in WARNINGS and dns.get("error") != "dns_no_token":
            facts += f'<p class="error" role="status">{esc(t["domains_" + dns["error"]])}</p>'

        token_form = (f'<div class="node-addr"><h2>{esc(t["domains_cloudflare"])}</h2>'
                      f'<p class="muted">{esc(t["domains_token_help"])}</p>'
                      f'<p>{esc(t["domains_token_set"] if token_set else t["domains_token_missing"])}</p>'
                      f'<form method="post" action="/domains/token" class="portfwd-add-form">'
                      f'<input type="hidden" name="csrf" value="{csrf}">'
                      f'<label>{esc(t["domains_token"])}<input type="password" name="token" autocomplete="off" '
                      f'maxlength="100" {"" if token_set else "required"}></label>'
                      f'<div class="iperf-actions"><button type="submit">{esc(t["domains_token_save"])}</button>'
                      + (f'<button type="submit" name="clear" value="1" class="danger">{esc(t["domains_token_clear"])}</button>'
                         if token_set else '') +
                      '</div></form></div>')

        rows = []
        dns_sites = dns.get("sites", {}) if isinstance(dns.get("sites"), dict) else {}
        for site in sites:
            host, port = str(site.get("host", "")), site.get("port")
            expiry = certificate_expiry(host)
            cert = (t["domains_cert_valid"].format(date=expiry.strftime("%Y-%m-%d")) if expiry
                    else t["domains_cert_pending"])
            state = dns_sites.get(host) or {}
            dns_text = (t["domains_dns_ok"] if state.get("ok") else
                        t.get("domains_" + str(state.get("error")), t["domains_dns_pending"]) if state else
                        t["domains_dns_pending"])
            rows.append(
                f'<div class="node-addr"><h2>{esc(host)}</h2>'
                f'<p>https://{esc(host)} &rarr; 127.0.0.1:{esc(str(port))}</p>'
                f'<p class="muted">{esc(t["domains_certificate"])}: {esc(cert)} · DNS: {esc(dns_text)}</p>'
                f'<form method="post" action="/domains/remove" class="inline-form" '
                f'data-confirm="{esc(t["domains_remove_confirm"].format(host=host), quote=True)}">'
                f'<input type="hidden" name="csrf" value="{csrf}">'
                f'<input type="hidden" name="host" value="{esc(host, quote=True)}">'
                f'<label><input type="checkbox" name="remove_dns" value="1" checked> {esc(t["domains_remove_dns"])}</label>'
                f'<button type="submit" class="danger">{esc(t["domains_remove"])}</button></form></div>')
        sites_html = "".join(rows) if rows else f'<p class="muted">{esc(t["domains_none"])}</p>'

        add_form = (f'<div class="node-addr"><h2>{esc(t["domains_add"])}</h2>'
                    f'<p class="muted">{esc(t["domains_add_help"])}</p>'
                    f'<form method="post" action="/domains/add" class="portfwd-add-form">'
                    f'<input type="hidden" name="csrf" value="{csrf}">'
                    f'<label>{esc(t["domains_host"])}<input type="text" name="host" placeholder="nas.example.com" '
                    f'maxlength="253" autocapitalize="none" spellcheck="false" required></label>'
                    f'<label>{esc(t["domains_port"])}<input type="number" name="port" min="1" max="65535" required></label>'
                    f'<button type="submit">{esc(t["domains_add"])}</button></form></div>')

        body = (f'<div class="card wide"><h1>{esc(t["domains"])}</h1>{"".join(messages)}{facts}'
                f'{sites_html}{add_form}{token_form}</div>')
        return self.send_html(200, self.render_page(t["domains"], body, lang, icon="domains"),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def domains_form(self):
        raw = self.read_body(self.context.LOGIN_BODY_LIMIT)
        form = self.context.parse_qs(raw.decode("utf-8", errors="replace"))
        values = form.get("csrf", [])
        if len(values) != 1 or not self.context.hmac.compare_digest(values[0], self.domains_csrf()):
            return None
        return form

    def domains_finish(self, reply, success):
        if reply.get("ok"):
            target = f"/domains?msg={success}"
            if reply.get("warning") in WARNINGS:
                target += f"&warning={reply['warning']}"
        else:
            error = reply.get("error") if reply.get("error") in ERRORS else "failed"
            target = f"/domains?error={error}"
        return self.redirect(target, {"Cache-Control": "no-store"})

    def handle_domains_add(self):
        form = self.domains_form()
        if form is None:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        port = form.get("port", [""])[0].strip()
        if not port.isascii() or not port.isdecimal():
            return self.domains_finish({"ok": False, "error": "port_invalid"}, "")
        reply = self.domains_apply({"action": "add", "host": form.get("host", [""])[0][:253],
                                    "port": int(port)})
        return self.domains_finish(reply, "domains_added")

    def handle_domains_remove(self):
        form = self.domains_form()
        if form is None:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        reply = self.domains_apply({"action": "remove", "host": form.get("host", [""])[0][:253],
                                    "remove_dns": form.get("remove_dns", [""])[0] == "1"})
        return self.domains_finish(reply, "domains_removed")

    def handle_domains_token(self):
        form = self.domains_form()
        if form is None:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        clear = form.get("clear", [""])[0] == "1"
        token = "" if clear else form.get("token", [""])[0][:200]
        reply = self.domains_apply({"action": "token", "token": token})
        return self.domains_finish(reply, "domains_token_cleared" if clear else "domains_token_saved")

    def route_domains(self, method, path, parsed, lang, query_lang):
        if not self.context.AUTH_ENABLED:
            return False
        if method == "GET" and path == "/domains":
            self.page_domains(lang, query_lang, parsed)
            return True
        if method == "POST" and path in ("/domains/add", "/domains/remove", "/domains/token"):
            if not self.context.module_states()["caddy"]:
                self.send_html(404, "Not found", {"Cache-Control": "no-store"})
                return True
            {"/domains/add": self.handle_domains_add, "/domains/remove": self.handle_domains_remove,
             "/domains/token": self.handle_domains_token}[path]()
            return True
        return False
