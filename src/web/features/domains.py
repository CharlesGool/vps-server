"""Domain forwarding page: subdomain -> local port through Caddy, DNS on Cloudflare.

Reads the module's state directly; every change goes through the root helper
caddy_sites.py, outside Web's sandbox.
"""

import json
import ssl
import time
from datetime import datetime, timezone

from caddy_sites import CONFIG_DIR, DATA_DIR, SERVICE, read_sites
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
            sites = read_sites()
        except (OSError, ValueError):
            sites = []
        dns = _read_json(CONFIG_DIR / "dns.json")
        token_set = (CONFIG_DIR / "cloudflare-token").is_file()
        running = self.context._run_quiet(["systemctl", "is-active", "--quiet", SERVICE])
        csrf = esc(self.domains_csrf(), quote=True)

        def pill(text, state=""):
            return f'<span class="proxy-node-status {state}">{esc(text)}</span>'

        def address(family):
            if not dns.get(family):
                return "<code>—</code>"
            return self.private_value_control(family, "address", t, endpoint="/domains/value")

        checked = dns.get("checked_at")
        checked_text = (time.strftime("%Y-%m-%d %H:%M", time.localtime(checked))
                        if isinstance(checked, (int, float)) else "—")
        dns_error = dns.get("error") if dns.get("error") in WARNINGS and dns.get("error") != "dns_no_token" else None
        overview = (f'<section class="card frp-card">'
                    f'<div class="frp-status-line">'
                    f'{pill(t["node_active"] if running else t["node_stopped"], "is-open" if running else "is-closed")}</div>'
                    f'<dl class="frp-facts frp-server-facts">'
                    f'<div><dt>{esc(t["domains_ipv4"])}</dt><dd>{address("ipv4")}</dd></div>'
                    f'<div><dt>{esc(t["domains_ipv6"])}</dt><dd>{address("ipv6")}</dd></div>'
                    f'<div><dt>{esc(t["domains_dns_checked"])}</dt><dd><code>{esc(checked_text)}</code></dd></div>'
                    f'</dl>'
                    + (f'<p class="error" role="status">{esc(t["domains_" + dns_error])}</p>' if dns_error else '')
                    + '</section>')

        cards = []
        dns_sites = dns.get("sites", {}) if isinstance(dns.get("sites"), dict) else {}
        for site in sites:
            host = site["host"]
            expiry = certificate_expiry(host)
            cert = (pill(t["domains_cert_valid"].format(date=expiry.strftime("%Y-%m-%d")), "is-open") if expiry
                    else pill(t["domains_cert_pending"]))
            state = dns_sites.get(host) or {}
            dns_pill = (pill("DNS " + t["domains_dns_ok"], "is-open") if state.get("ok") else
                        pill(t.get("domains_" + str(state.get("error")), t["domains_dns_pending"]), "is-closed")
                        if state.get("error") else pill("DNS " + t["domains_dns_pending"]))
            cards.append(
                f'<article class="frp-target-card domain-card">'
                f'<div class="frp-target-head"><a class="frp-target-name" href="https://{esc(host, quote=True)}/" '
                f'target="_blank" rel="noopener noreferrer">{esc(host)}</a></div>'
                + (f'<div class="frp-target-meta"><span class="muted">{esc(t["domains_target"])}</span>'
                   f'<span>{esc(t["domains_target_console"])}</span></div>' if site.get("console") else
                   f'<div class="frp-target-meta"><span class="muted">{esc(t["domains_port"])}</span>'
                   f'<code>127.0.0.1</code>{self.private_value_control("site:" + host, "target-port", t, endpoint="/domains/value")}</div>')
                + f'<div class="domain-badges">{cert}{dns_pill}</div>'
                f'<form method="post" action="/domains/remove" class="frp-target-foot domain-remove" '
                f'data-confirm="{esc(t["domains_remove_confirm"].format(host=host), quote=True)}">'
                f'<input type="hidden" name="csrf" value="{csrf}">'
                f'<input type="hidden" name="host" value="{esc(host, quote=True)}">'
                f'<label class="checkline"><input type="checkbox" name="remove_dns" value="1" checked>'
                f'<span>{esc(t["domains_remove_dns"])}</span></label>'
                f'<button type="submit" class="node-action-danger frp-card-edit">{esc(t["domains_remove"])}</button></form>'
                f'</article>')
        grid = ("".join(cards) if cards else f'<p class="muted">{esc(t["domains_none"])}</p>')
        add_form = (f'<p class="muted">{esc(t["domains_add_help"])}</p>'
                    f'<form method="post" action="/domains/add" autocomplete="off">'
                    f'<input type="hidden" name="csrf" value="{csrf}">'
                    f'<label>{esc(t["domains_host"])}<input type="text" name="host" placeholder="nas.example.com" '
                    f'maxlength="253" autocapitalize="none" spellcheck="false" required></label>'
                    f'<label>{esc(t["domains_port"])}<input type="number" name="port" min="1" max="65535" required></label>'
                    f'<button type="submit">{esc(t["domains_add"])}</button></form>')
        # With nothing listed yet the form is the page's purpose: show it, no toggle.
        add = (f'<div class="node-inline-edit domain-add">{add_form}</div>' if not sites else
               f'<details class="node-inline-edit domain-add" '
               f'{"open" if error in ("host_invalid", "port_invalid", "host_exists") else ""}>'
               f'<summary><span>{esc(t["domains_add"])}</span><span>{esc(t["node_cancel"])}</span></summary>'
               f'{add_form}</details>')
        sites_card = (f'<section class="card frp-card">'
                      f'<div class="frp-instances-head"><h2 class="frp-instances-heading">{esc(t["domains_sites"])}</h2></div>'
                      f'{add}<div class="frp-client-grid">{grid}</div></section>')

        token_field = self.context.render_password_field(
            t, "domains-token", t["domains_token"], "token",
            'maxlength="100" autocomplete="off" spellcheck="false" required')
        token_form = (f'<form method="post" action="/domains/token" autocomplete="off">'
                      f'<input type="hidden" name="csrf" value="{csrf}">'
                      f'<div class="frp-password-field">{token_field}</div>'
                      f'<button type="submit">{esc(t["domains_token_save"])}</button></form>')
        clear = (f'<form method="post" action="/domains/token" class="frp-delete-form" '
                 f'data-confirm="{esc(t["domains_token_clear_confirm"], quote=True)}">'
                 f'<input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="clear" value="1">'
                 f'<button type="submit" class="node-action-danger frp-card-edit">{esc(t["domains_token_clear"])}</button></form>'
                 if token_set else '')
        token_card = (f'<section class="card frp-card">'
                      f'<div class="frp-instances-head"><h2 class="frp-instances-heading">{esc(t["domains_cloudflare"])}</h2>'
                      f'{pill(t["domains_token_state_set"] if token_set else t["domains_token_state_missing"], "is-open" if token_set else "is-closed")}</div>'
                      f'<p class="muted">{esc(t["domains_token_help"])}</p>'
                      f'<div class="domains-token-actions">'
                      + (f'<details class="node-inline-edit"><summary><span>{esc(t["domains_token_change"])}</span>'
                         f'<span>{esc(t["node_cancel"])}</span></summary>{token_form}</details>'
                         if token_set else f'<div class="node-inline-edit">{token_form}</div>')
                      + f'{clear}</div></section>')

        body = (f'<h1>{esc(t["domains"])}</h1><div class="frp-workspace domains-page">{"".join(messages)}'
                f'{overview}{sites_card}{token_card}</div>'
                '<script src="/static/copy.js"></script><script src="/static/private-values.js"></script>')
        return self.send_html(200, self.render_page(t["domains"], body, lang, icon="domains"),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def handle_domains_value(self, parsed):
        """Reveal one masked value: the host's public address or a site's port."""
        query = self.context.parse_qs(parsed.query)
        identifier, field = query.get("id", [""])[0], query.get("field", [""])[0]
        value = None
        if set(query) == {"id", "field"} and len(query["id"]) == len(query["field"]) == 1:
            if identifier in ("ipv4", "ipv6") and field == "address":
                value = _read_json(CONFIG_DIR / "dns.json").get(identifier)
            elif identifier.startswith("site:") and field == "target-port":
                try:
                    value = next((str(site["port"]) for site in read_sites()
                              if site["host"] == identifier[5:] and "port" in site), None)
                except (OSError, ValueError):
                    value = None
        if not value:
            return self.send_html(404, "Not found", {"Cache-Control": "no-store"})
        data = json.dumps({"value": value}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

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
        if method == "GET" and path == "/domains/value":
            self.handle_domains_value(parsed)
            return True
        if method == "POST" and path in ("/domains/add", "/domains/remove", "/domains/token"):
            if not self.context.module_states()["caddy"]:
                self.send_html(404, "Not found", {"Cache-Control": "no-store"})
                return True
            {"/domains/add": self.handle_domains_add, "/domains/remove": self.handle_domains_remove,
             "/domains/token": self.handle_domains_token}[path]()
            return True
        return False
