#!/usr/bin/env python3
"""Short-lived installer-only selection listener; never runs installation actions."""
import argparse
from contextlib import contextmanager
from datetime import date
import fcntl
import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import signal
import socket
import ssl
import subprocess
import tempfile
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from pathlib import Path

LANGUAGE_TAGS = {'en': 'en', 'zh_cn': 'zh-CN', 'zh_tw': 'zh-TW', 'zh_hk': 'zh-HK',
                 'hi': 'hi', 'es': 'es', 'ar': 'ar', 'fr': 'fr'}
LANGUAGE_NAMES = {'en': 'English', 'zh_cn': '简体中文', 'zh_tw': '繁體中文',
                  'zh_hk': '繁體中文（香港）', 'hi': 'हिन्दी', 'es': 'Español',
                  'ar': 'العربية', 'fr': 'Français'}
CATALOG_DIR = Path(__file__).resolve().parents[2] / 'lang' / 'setup_wizard'
CATALOGS = {code: json.loads((CATALOG_DIR / f'{tag}.json').read_text(encoding='utf-8'))
            for code, tag in LANGUAGE_TAGS.items()}


def _t(key, language='en'):
    return CATALOGS.get(language, CATALOGS['en'])[key]


MODULES = ('web', 'iperf3', 'anytls', 'proxy', 'frps', 'lucky')
PROTOCOLS = ('vmess', 'vless', 'trojan', 'shadowsocks')
LANGUAGES = ('en', 'zh_cn', 'zh_tw', 'zh_hk', 'hi', 'es', 'ar', 'fr')


def validate(form, previous, installed, previous_protocols='', lucky_defaults=('16601', '0')):
    language = form.get('language', ['en'])[0]
    allowed = {'modules', 'protocols', 'policy', 'confirm', 'remove_protocols', 'auth', 'public', 'port', 'language', 'lucky_port', 'lucky_public'}
    if set(form) - allowed or any(len(v) != 1 for v in form.values()):
        raise ValueError(_t('malformed_selection', language))
    def items(key, options):
        raw = form.get(key, [''])[0]
        parts = raw.split(',') if raw else []
        if len(parts) != len(set(parts)) or any(p not in options for p in parts):
            raise ValueError(_t('invalid_item', language) % key)
        return ','.join(p for p in options if p in parts)
    modules = items('modules', MODULES)
    protocols = items('protocols', PROTOCOLS)
    if not modules:
        raise ValueError(_t('select_module', language))
    chosen = modules.split(',')
    if ('iperf3' in chosen and 'web' not in chosen) or (('proxy' in chosen) != bool(protocols)):
        raise ValueError(_t('incompatible_modules', language))
    if not installed and 'web' not in chosen:
        raise ValueError(_t('console_required', language))
    policy = form.get('policy', ['preserve'])[0]
    if policy not in ('preserve', 'reconfigure'):
        raise ValueError(_t('invalid_upgrade_policy', language))
    previous_modules = {module for module in previous.split(',') if module}
    if installed and (policy == 'reconfigure' or previous_modules - set(chosen)) and form.get('confirm') != ['DELETE']:
        raise ValueError(_t('explicit_delete', language))
    removals = ({p for p in previous_protocols.split(',') if p} - set(protocols.split(','))) if installed else set()
    confirmed_removals = set(items('remove_protocols', PROTOCOLS).split(',')) - {''}
    if removals != confirmed_removals:
        raise ValueError(_t('confirm_removal', language) % ', '.join(sorted(removals)))
    auth = form.get('auth', ['1'])[0]
    public = form.get('public', ['1'])[0]
    port = form.get('port', [''])[0]
    if auth not in ('0', '1') or public not in ('0', '1') or language not in LANGUAGES:
        raise ValueError(_t('invalid_setting', language))
    if port and (not port.isascii() or not port.isdecimal() or not 1 <= int(port) <= 65535):
        raise ValueError(_t('invalid_console_port', language))
    lucky_port = form.get('lucky_port', [lucky_defaults[0]])[0]
    lucky_public = form.get('lucky_public', [lucky_defaults[1]])[0]
    if not lucky_port.isascii() or not lucky_port.isdecimal() or not 1 <= int(lucky_port) <= 65535 or lucky_public not in ('0', '1'):
        raise ValueError(_t('invalid_lucky_settings', language))
    if lucky_public == '1' and 'lucky' not in chosen:
        raise ValueError(_t('lucky_requires_module', language))
    return (modules, protocols, policy, auth, public, port, language, lucky_port, lucky_public)


WIZARD_CSS = """
:root { color-scheme:light; --bg:#f5f7f6; --fg:#1d2d35; --muted:#52636b; --border:#d8e1e0; --accent:#365779; --surface:#eef3f2; }
* { box-sizing:border-box; }body { margin:0; min-height:100vh; padding:clamp(1rem,4vw,3rem); background:var(--bg); color:var(--fg); font:16px/1.55 system-ui,-apple-system,'Segoe UI',sans-serif; }
main { max-width:52rem; margin:0 auto; padding:clamp(1.25rem,4vw,2.5rem); border:1px solid var(--border); border-radius:10px; background:white; box-shadow:0 10px 32px rgba(23,45,52,.06); }
h1 { margin:0 0 .6rem; font-size:clamp(1.5rem,3vw,2rem); letter-spacing:-.03em; line-height:1.25; }h2 { margin:1.75rem 0 .75rem; padding-bottom:.45rem; border-bottom:1px solid var(--border); font-size:1.08rem; }
p { color:var(--muted); }form { display:block; }form > br { display:none; }label { display:block; margin:.45rem 0; color:var(--fg); }label:has(input[type=checkbox]) { display:flex; align-items:center; gap:.65rem; min-height:2.75rem; padding:.45rem .65rem; border:1px solid var(--border); border-radius:8px; cursor:pointer; }
input,select { display:block; width:100%; min-height:2.75rem; margin-top:.3rem; padding:.55rem .7rem; border:1px solid var(--border); border-radius:8px; background:white; color:var(--fg); font:inherit; }input[type=checkbox] { width:1rem; min-height:0; margin:0; accent-color:var(--accent); }
button { min-height:2.75rem; margin-top:1rem; padding:.6rem 1rem; border:1px solid var(--accent); border-radius:8px; background:var(--accent); color:white; font:600 .9rem system-ui,sans-serif; cursor:pointer; }button:hover { filter:brightness(1.12); }a { color:var(--accent); }:focus-visible { outline:3px solid var(--accent); outline-offset:3px; }
@media (max-width:35rem) { main { padding:1.2rem; } }
.wizard-choices { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,12rem),1fr)); gap:.45rem; }
.wizard-choices br { display:none; }
.wizard-choices label:has(input[type=checkbox]) { margin:0; }
.wizard-password-toggle { min-height:2.75rem; margin:.5rem 0 0; border-color:var(--border); background:white; color:var(--accent); }
"""


def wizard_document(body, language, nonce=''):
    favicon = base64.b64encode((Path(__file__).resolve().parents[2] / 'static' / 'favicon.svg').read_bytes()).decode('ascii')
    tag = LANGUAGE_TAGS.get(language, 'en')
    direction = ' dir="rtl"' if language == 'ar' else ''
    return (f'<!doctype html><html lang="{tag}"{direction}><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(_t("setup_title", language))}</title>'
            f'<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,{favicon}">'
            f'<style>{WIZARD_CSS}</style></head><body><main>{body}</main>'
            f'<script nonce="{nonce}">'
            f'const field=document.querySelector("input[type=password]");'
            f'if(field){{const button=document.createElement("button");button.type="button";'
            f'button.className="wizard-password-toggle";'
            f'const show={json.dumps(_t("show_password", language))},hide={json.dumps(_t("hide_password", language))};'
            f'button.textContent=show;button.setAttribute("aria-label",show);'
            f'button.setAttribute("aria-pressed","false");field.closest("label").after(button);'
            f'button.addEventListener("click",()=>{{const visible=field.type==="text";'
            f'field.type=visible?"password":"text";button.textContent=visible?show:hide;'
            f'button.setAttribute("aria-label",visible?show:hide);'
            f'button.setAttribute("aria-pressed",String(!visible));}});}}'
            f'const proxy=document.querySelector("input[name=module][value=proxy]");'
            f'const protocols=document.querySelector("[data-proxy-protocols]");'
            f'if(proxy&&protocols){{const sync=()=>{{protocols.hidden=!proxy.checked;}};'
            f'proxy.addEventListener("change",sync);sync();}}'
            f'</script></body></html>')


class Wizard(HTTPServer):
    allow_reuse_address = True  # TIME_WAIT is not a listener; live bind collisions still fail.

    def __init__(self, address, previous='', installed=False, ttl=300, previous_protocols='', defaults=('1', '1', 'en'), lucky_defaults=('16601', '0')):
        super().__init__(address, Handler)
        self.previous = previous
        self.previous_protocols = previous_protocols
        self.defaults = defaults
        self.lucky_defaults = lucky_defaults
        self.installed = installed
        self.expires = time.monotonic() + ttl
        self.token = secrets.token_urlsafe(32)
        self.session = None
        self.csrf = secrets.token_urlsafe(32)
        self.result = None
        self.timeout = 0.2
        self.tls_context = None
        self.ready_file = None

    def get_request(self):
        connection, address = self.socket.accept()
        connection.settimeout(2)
        if self.tls_context is not None:
            try:
                connection = self.tls_context.wrap_socket(connection, server_side=True)
            except Exception:
                connection.close()
                raise
        return connection, address

    def serve_selection(self):
        while self.result is None and time.monotonic() < self.expires:
            self.handle_request()
        return self.result

    def serve_completion(self):
        self.expires = time.monotonic() + 1800
        ready_since = None
        while time.monotonic() < self.expires:
            if self.ready_file.is_file():
                if ready_since is None:
                    ready_since = time.monotonic()
                elif time.monotonic() - ready_since > 90:
                    break
            self.handle_request()


@contextmanager
def reserved_listener(bind, port, apps_root, *wizard_args):
    """Bind first, register before serving, and release on every exit path."""
    if not apps_root:
        with Wizard((bind, port), *wizard_args) as server:
            yield server
        return
    root = Path(apps_root)
    root.mkdir(parents=True, exist_ok=True)
    registry = root / 'PORTS.md'
    header = '| Host Port | Project / Service | Bind Address | Registration Date |\n| --- | --- | --- | --- |\n'
    lock_file = root / '.ports.lock'
    with lock_file.open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        content = registry.read_text() if registry.exists() else header
        if not content.startswith(header):
            raise ValueError('Invalid port registry')
        rows = content[len(header):].splitlines()
        used = set()
        for row in rows:
            match = re.fullmatch(r'\|\s*(\d{1,5})\s*\|\s*[^|]+\|\s*[^|]+\|\s*\d{4}-\d{2}-\d{2}\s*\|', row)
            if not match or int(match[1]) in used:
                raise ValueError('Invalid port registry row')
            used.add(int(match[1]))
        candidates = ([port] if port else [20000 + secrets.randbelow(40000) for _ in range(100)])
        server = None
        for candidate in candidates:
            if candidate in used:
                continue
            try:
                # A temporary TCP listener still owns a host-port number; do
                # not reuse a UDP assignment already active on that number.
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
                    udp.bind(('0.0.0.0', candidate))
                server = Wizard((bind, candidate), *wizard_args)
                break
            except OSError:
                if port:
                    raise
        if server is None:
            raise OSError('No setup port available')
        assigned = server.server_address[1]
        row = f'| {assigned} | vps-server setup | {bind} | {date.today().isoformat()} |'
        stage = registry.with_name('.PORTS.setup.tmp')
        try:
            stage.write_text(header + ''.join(item + '\n' for item in rows if item.strip()) + row + '\n')
            os.replace(stage, registry)
        except BaseException:
            server.server_close()
            stage.unlink(missing_ok=True)
            raise
    try:
        with server:
            yield server
    finally:
        with lock_file.open('a+b') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if registry.is_file():
                lines = registry.read_text().splitlines(keepends=True)
                remaining = [line for line in lines[2:] if line.strip() != row]
                stage = registry.with_name('.PORTS.setup.tmp')
                stage.write_text(''.join(lines[:2] + remaining))
                os.replace(stage, registry)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # No request path, token, cookie or form data in logs.

    def reply(self, status, body, cookie=None):
        nonce = secrets.token_urlsafe(16)
        content = wizard_document(body, self.server.defaults[2], nonce).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy',
                         f"default-src 'none'; style-src 'unsafe-inline'; img-src data:; script-src 'nonce-{nonce}'; form-action 'self'")
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(content)

    def authorized(self):
        cookies = self.headers.get('Cookie', '').split('; ')
        return self.server.session is not None and any(
            hmac.compare_digest(c, 'wizard=' + self.server.session) for c in cookies)

    def do_GET(self):
        if self.path != '/' or time.monotonic() >= self.server.expires:
            return self.reply(404, _t('unavailable', self.server.defaults[2]))
        if not self.authorized():
            return self.reply(200, _t('access_page', self.server.defaults[2]))
        if self.server.result is not None:
            if self.server.ready_file and self.server.ready_file.is_file():
                url = self.server.ready_file.read_text().strip()
                if url.startswith(('http://', 'https://')):
                    body = _t('setup_ready', self.server.defaults[2]) % html.escape(url, quote=True)
                else:
                    body = _t('setup_ready_terminal', self.server.defaults[2])
            else:
                body = _t('setup_progress', self.server.defaults[2])
            return self.reply(200, body)
        previous = self.server.previous if self.server.installed else 'web,iperf3'
        module_inputs = ''.join('<label><input type="checkbox" name="module" value="%s" %s>%s</label><br>' %
                                (m, 'checked' if m in previous.split(',') else '',
                                 html.escape(_t('module_' + m, self.server.defaults[2]))) for m in MODULES)
        protocol_inputs = ''.join('<label><input type="checkbox" name="protocol" value="%s" %s>%s</label><br>' %
                                  (p, 'checked' if p in self.server.previous_protocols.split(',') else '', p) for p in PROTOCOLS)
        removal_inputs = ''.join(
            _t('remove_protocol', self.server.defaults[2]) % (p, p)
            for p in PROTOCOLS if p in self.server.previous_protocols.split(','))
        # Checkbox lists are sent separately; only known names are accepted by POST.
        auth, public, language = self.server.defaults
        language_options = ''.join('<option value="%s" %s>%s</option>' %
                                   (lang, 'selected' if language == lang else '', LANGUAGE_NAMES[lang])
                                   for lang in LANGUAGES)
        if self.server.installed:
            body = _t('setup_form', language) % (
                        self.server.installed, html.escape(previous), self.server.csrf, module_inputs, protocol_inputs, removal_inputs,
                        'selected' if auth == '1' else '', 'selected' if auth == '0' else '',
                        'selected' if public == '1' else '', 'selected' if public == '0' else '',
                        language_options,
                        html.escape(self.server.lucky_defaults[0]),
                        'selected' if self.server.lucky_defaults[1] == '0' else '',
                        'selected' if self.server.lucky_defaults[1] == '1' else '')
        else:
            body = _t('first_run_form', language) % (self.server.csrf, module_inputs,
                                                    protocol_inputs, language_options)
        self.reply(200, body)

    def do_POST(self):
        if self.path not in ('/login', '/apply') or time.monotonic() >= self.server.expires or self.server.result is not None:
            return self.reply(410, _t('unavailable', self.server.defaults[2]))
        length = self.headers.get('Content-Length', '')
        if not length.isascii() or not length.isdecimal() or int(length) > 4096:
            return self.reply(400, _t('invalid_request', self.server.defaults[2]))
        try:
            raw = self.rfile.read(int(length)).decode('utf-8', 'strict')
            form = parse_qs(raw, keep_blank_values=True, strict_parsing=True, max_num_fields=30)
        except (UnicodeError, ValueError):
            return self.reply(400, _t('invalid_request', self.server.defaults[2]))
        if self.path == '/login':
            if set(form) != {'token'} or len(form['token']) != 1 or self.server.session is not None or not hmac.compare_digest(form['token'][0], self.server.token):
                return self.reply(403, _t('access_denied', self.server.defaults[2]))
            self.server.token = ''
            self.server.session = secrets.token_urlsafe(32)
            cookie = 'wizard=' + self.server.session + '; HttpOnly; SameSite=Strict; Path=/'
            if isinstance(self.connection, ssl.SSLSocket):
                cookie += '; Secure'
            return self.reply(200, _t('access_granted', self.server.defaults[2]), cookie)
        if not self.authorized() or 'csrf' not in form or len(form['csrf']) != 1 or not hmac.compare_digest(form['csrf'][0], self.server.csrf):
            return self.reply(403, _t('access_denied', self.server.defaults[2]))
        try:
            normalized = {k: v for k, v in form.items() if k not in ('csrf', 'module', 'protocol', 'remove_protocol')}
            if (any(x not in MODULES for x in form.get('module', [])) or
                    any(x not in PROTOCOLS for x in form.get('protocol', []) + form.get('remove_protocol', []))):
                raise ValueError(_t('invalid_checkbox', self.server.defaults[2]))
            normalized['modules'] = [','.join(form.get('module', []))]
            normalized['protocols'] = [','.join(form.get('protocol', []))]
            normalized['remove_protocols'] = [','.join(form.get('remove_protocol', []))]
            selection = validate(normalized, self.server.previous, self.server.installed,
                                 self.server.previous_protocols, self.server.lucky_defaults)
        except ValueError as exc:
            return self.reply(400, html.escape(str(exc)))
        self.server.result = selection
        if self.server.ready_file is None:
            self.server.session = None
        self.server.csrf = ''
        key = 'selection_pending' if self.server.ready_file is not None else 'selection_accepted'
        self.reply(200, _t(key, self.server.defaults[2]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bind', required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--public', action='store_true')
    parser.add_argument('--previous', default='')
    parser.add_argument('--proxy-config', default='')
    parser.add_argument('--auth-default', choices=('0', '1'), default='1')
    parser.add_argument('--public-default', choices=('0', '1'), default='1')
    parser.add_argument('--language-default', choices=LANGUAGES, default='en')
    parser.add_argument('--installed', action='store_true')
    parser.add_argument('--lucky-config', default='')
    parser.add_argument('--result', required=True)
    parser.add_argument('--ready-file', default='')
    parser.add_argument('--apps-root', default='')
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535 or not 1 <= args.timeout <= 900:
        parser.error(_t('invalid_port_timeout', args.language_default))
    if not args.public and args.bind not in ('127.0.0.1', '::1'):
        parser.error(_t('bind_requires_https', args.language_default))
    if args.public and args.bind in ('127.0.0.1', '::1'):
        parser.error(_t('public_requires_bind', args.language_default))
    previous_protocols = ''
    if args.installed and args.proxy_config and os.path.isfile(args.proxy_config):
        with open(args.proxy_config, encoding='utf-8') as config:
            inbounds = json.load(config)['inbounds']
        previous_protocols = ','.join(p for p in PROTOCOLS if any(i.get('type') == p for i in inbounds))
    lucky_defaults = ('16601', '0')
    if args.installed and args.lucky_config and os.path.isfile(args.lucky_config):
        with open(args.lucky_config, encoding='utf-8') as config:
            base = json.load(config)['BaseConfigure']
        port = base['AdminWebListenPort']
        public = base.get('AllowInternetaccess', False)
        if type(port) is not int or not 1 <= port <= 65535 or type(public) is not bool:
            parser.error(_t('malformed_lucky_config', args.language_default))
        lucky_defaults = (str(port), str(int(public)))
    def stop(_signum, _frame):
        raise SystemExit('Wizard interrupted; no installation performed')
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with tempfile.TemporaryDirectory(prefix='vpssrv-wizard-') as temp:
        with reserved_listener(args.bind, args.port, args.apps_root, args.previous, args.installed, args.timeout,
                               previous_protocols, (args.auth_default, args.public_default, args.language_default), lucky_defaults) as server:
            if args.ready_file:
                server.ready_file = Path(args.ready_file)
            if args.public:
                cert, key = os.path.join(temp, 'cert.pem'), os.path.join(temp, 'key.pem')
                subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                                '-subj', '/CN=vpssrv-setup', '-keyout', key, '-out', cert],
                               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                os.chmod(key, 0o600)
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(cert, key)
                server.tls_context = context
                der = ssl.PEM_cert_to_DER_cert(open(cert, encoding='ascii').read())
                print(_t('certificate_fingerprint', args.language_default), hashlib.sha256(der).hexdigest(), flush=True)
            print(_t('setup_url', args.language_default) % ('https' if args.public else 'http', args.bind, server.server_address[1]), flush=True)
            if args.bind in ('0.0.0.0', '::'):
                print(_t('wildcard_note', args.language_default), flush=True)
            print(_t('access_token', args.language_default), server.token, flush=True)
            print(_t('expires', args.language_default) % args.timeout, flush=True)
            selected = server.serve_selection()
            if selected is None:
                raise SystemExit('Wizard expired or interrupted; no installation performed')
            # All fields have been reduced to fixed choices or decimal digits. No shell evaluation.
            temporary_result = args.result + '.tmp'
            with open(temporary_result, 'x', encoding='ascii') as output:
                output.write('\n'.join(selected) + '\n')
            os.replace(temporary_result, args.result)
            if server.ready_file is not None:
                server.serve_completion()
    if args.ready_file:
        import shutil
        shutil.rmtree(Path(args.ready_file).parent, ignore_errors=True)


if __name__ == '__main__':
    main()
