"""End-to-end tests for vps-server. Run with: python3 -m unittest tests/test_app.py

Starts the real Handler/ThreadingHTTPServer from app.py on an ephemeral
loopback port against a throwaway data directory, then drives it over real
HTTP connections.
"""

import atexit
import base64
import html
import http.client
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode, unquote, urlsplit
from unittest.mock import patch

TEST_DATA_DIR = tempfile.mkdtemp(prefix="vpssrv-test-")
# Cleaned up once, when the process exits. This used to happen in one test
# class's tearDownClass, which silently made every later class depend on
# alphabetical class ordering — renaming a class was enough to break an
# unrelated test in a way that only showed up in a full run.
atexit.register(shutil.rmtree, TEST_DATA_DIR, ignore_errors=True)
os.environ["VPSSRV_DATA_DIR"] = TEST_DATA_DIR
os.environ["VPSSRV_HOST"] = "127.0.0.1"
os.environ["VPSSRV_MAX_TEST_MB"] = "20"  # keep the clamp test's payload small and fast
os.environ["VPSSRV_PASSWORD_FILE"] = str(Path(TEST_DATA_DIR) / "admin_password.txt")
os.environ["VPSSRV_CONSOLE_PORT_FILE"] = str(Path(TEST_DATA_DIR) / "console_port.txt")
os.environ["VPSSRV_CERT_DIR"] = str(Path(TEST_DATA_DIR) / "certs")
os.environ["VPSSRV_CONSOLE_TLS"] = "0"  # the shared fixture drives plain HTTP; TLS has its own case

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.web import app  # noqa: E402  (import must follow env setup above)
import frp_control  # noqa: E402


class IpAllowlistTest(unittest.TestCase):
    def test_only_private_hosts_can_be_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            allowlist = app.IpAllowlist(Path(directory) / "login-access.json")
            for address in ("8.8.8.8", "127.0.0.1", "169.254.2.3", "100.101.102.104",
                            "10.0.0.0/8", "192.168.1.2, 8.8.8.8", "fe80::1"):
                with self.subTest(address=address), self.assertRaises(ValueError):
                    allowlist.change(address, add=True)
            self.assertEqual(allowlist.change("192.168.1.2", add=True), "192.168.1.2")
            allowlist.change("fd12::1", add=True)
            self.assertTrue(allowlist.contains("192.168.1.2"))
            self.assertFalse(allowlist.contains("100.101.102.104"))
            self.assertEqual(app.IpAllowlist(allowlist.path).list_addresses(),
                             ["192.168.1.2", "fd12::1"])
            allowlist.set_enabled(False)
            self.assertFalse(allowlist.contains("192.168.1.2"))
            self.assertFalse(app.IpAllowlist(allowlist.path).is_enabled())
            self.assertEqual(allowlist.path.stat().st_mode & 0o777, 0o600)

    def test_old_allowlist_keeps_private_entries_and_drops_unsafe_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "login-access.json"
            path.write_text('{"allowed_ips":["10.2.3.4"]}')
            self.assertTrue(app.IpAllowlist(path).contains("10.2.3.4"))
            path.write_text('{"allowed_ips":["10.2.3.4","8.8.8.8"]}')
            self.assertFalse(app.IpAllowlist(path).contains("8.8.8.8"))

    def test_damaged_list_fails_closed_without_breaking_password_login(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "login-access.json"
            path.write_text('{"allowed_ips":["8.8.8.8"]}')
            allowlist = app.IpAllowlist(path)
            self.assertTrue(allowlist.load_error)
            self.assertFalse(allowlist.contains("8.8.8.8"))
            allowlist.change("10.1.2.3", add=True)
            self.assertFalse(allowlist.load_error)
            self.assertEqual(app.IpAllowlist(path).list_addresses(), ["10.1.2.3"])

    def test_ip_session_is_bound_to_peer_and_allowlist(self):
        token = app.create_ip_session("192.168.1.20")
        try:
            with patch.object(app.IP_ALLOWLIST, "contains", return_value=True):
                self.assertTrue(app.ip_session_valid(token, "192.168.1.20"))
                self.assertFalse(app.ip_session_valid(token, "192.168.1.21"))
                with patch.object(app, "TRUST_PROXY", True):
                    self.assertFalse(app.ip_session_valid(token, "192.168.1.20"))
            self.assertFalse(app.ip_session_valid(token, "192.168.1.20"))
        finally:
            app.destroy_session(token)


class ConsoleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.ConsoleHandler)
        cls.server.daemon_threads = True
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.password = app.ADMIN_PASSWORD

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def connect(self):
        return http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)

    def login(self):
        conn = self.connect()
        conn.request(
            "POST",
            "/login",
            body=f"password={self.password}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp = conn.getresponse()
        self.assertEqual(resp.status, 302)
        cookie_header = resp.getheader("Set-Cookie")
        resp.read()
        conn.close()
        jar = SimpleCookie()
        jar.load(cookie_header)
        return jar["session"].value

    def test_module_manager_uses_ordinary_session_but_checks_csrf(self):
        ordinary = app.create_session()
        elevated = app.create_session(security_verified=True)
        try:
            conn = self.connect()
            conn.request("GET", "/settings/modules", headers={"Cookie": f"session={ordinary}"})
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            response.read()
            conn.close()
            conn = self.connect()
            conn.request("GET", "/settings/modules", headers={"Cookie": f"session={elevated}"})
            response = conn.getresponse()
            body = response.read().decode()
            self.assertEqual(response.status, 200)
            self.assertIn('Modules', body)
            self.assertIn('action="/settings/modules/action"', body)
            self.assertEqual(body.count('class="module-card"'), 4)
            self.assertNotIn('<h2>HTTP page</h2>', body)
            self.assertNotIn('<h2>HTTPS page</h2>', body)
            self.assertNotIn('<h2>AnyTLS</h2>', body)
            self.assertNotIn('<h2>Lucky</h2>', body)
            conn.close()
            conn = self.connect()
            conn.request("GET", "/", headers={"Cookie": f"session={ordinary}"})
            dashboard = conn.getresponse().read().decode()
            conn.close()
            self.assertEqual(dashboard.count('data-module='), 11)
            self.assertEqual(dashboard.count('role="switch"'), 9)
            self.assertIn('data-module="web_http"', dashboard)
            self.assertIn('data-module="web_https"', dashboard)
            body = urlencode({"module": "frps", "action": "install", "csrf": "invalid"})
            conn = self.connect()
            conn.request("POST", "/settings/modules/action", body,
                         {"Cookie": f"session={elevated}", "Content-Type": "application/x-www-form-urlencoded"})
            response = conn.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
            conn.close()
        finally:
            app.destroy_session(ordinary)
            app.destroy_session(elevated)

    def test_changelog_is_always_available_without_a_switch(self):
        session = app.create_session()
        try:
            self.assertTrue(app.module_states()["changelog"])
            for path, pattern in (
                ('/', r'<article class="tile" data-module="changelog">(.*?)</article>'),
            ):
                conn = self.connect()
                conn.request('GET', path, headers={'Cookie': f'session={session}'})
                response = conn.getresponse()
                body = response.read().decode()
                conn.close()
                self.assertEqual(response.status, 200)
                card = re.search(pattern, body, re.S)
                self.assertIsNotNone(card)
                self.assertNotIn('role="switch"', card[0])
                self.assertNotIn('name="module" value="changelog"', card[0])

            body = urlencode({'module': 'changelog', 'action': 'disable',
                              'csrf': app.access_csrf_token(session, 'module:changelog:disable')})
            conn = self.connect()
            conn.request('POST', '/settings/modules/action', body,
                         {'Cookie': f'session={session}',
                          'Content-Type': 'application/x-www-form-urlencoded'})
            response = conn.getresponse()
            response.read()
            conn.close()
            self.assertEqual(response.status, 400)
        finally:
            app.destroy_session(session)

    def test_public_page_has_separate_http_and_https_switches(self):
        session = app.create_session()
        try:
            for http_enabled, https_enabled in ((True, False), (False, True)):
                with self.subTest(http=http_enabled, https=https_enabled), \
                     patch.object(app, 'PUBLIC_HTTP_ENABLED', http_enabled), \
                     patch.object(app, 'PUBLIC_HTTPS_ENABLED', https_enabled), \
                     patch.object(app, 'installed_modules', return_value={'web'}):
                    conn = self.connect()
                    conn.request('GET', '/settings/modules?lang=en',
                                 headers={'Cookie': f'session={session}'})
                    response = conn.getresponse()
                    body = response.read().decode()
                    conn.close()
                    self.assertEqual(response.status, 200)
                    self.assertNotIn('name="module" value="web_http"', body)
                    self.assertNotIn('name="module" value="web_https"', body)
                    conn = self.connect()
                    conn.request('GET', '/?lang=en', headers={'Cookie': f'session={session}'})
                    response = conn.getresponse()
                    dashboard = response.read().decode()
                    conn.close()
                    self.assertEqual(response.status, 200)
                    for module, enabled in (('web_http', http_enabled), ('web_https', https_enabled)):
                        tile = re.search(r'<article class="tile tile-public" data-module="' + module + r'">.*?</article>', dashboard, re.S)
                        self.assertIsNotNone(tile)
                        self.assertIn(f'aria-checked="{str(enabled).lower()}"', tile[0])
                        destination = ('/public/' + ('http' if module == 'web_http' else 'https')
                                       if enabled else '/closed?module=' + module)
                        self.assertIn(f'href="{destination}"', tile[0])
                        conn = self.connect()
                        conn.request('GET', '/public/' + ('http' if module == 'web_http' else 'https'),
                                     headers={'Cookie': f'session={session}'})
                        response = conn.getresponse()
                        self.assertEqual(response.status, 302)
                        self.assertEqual(response.getheader('Location'),
                                         ('http://127.0.0.1/' if module == 'web_http' else 'https://127.0.0.1/')
                                         if enabled else '/closed?module=' + module)
                        response.read()
                        conn.close()
        finally:
            app.destroy_session(session)

    def test_public_page_switch_submits_to_module_job(self):
        session = app.create_session()
        try:
            conn = self.connect()
            conn.request('GET', '/settings?lang=en',
                         headers={'Cookie': f'session={session}'})
            response = conn.getresponse()
            page = response.read().decode()
            conn.close()
            self.assertEqual(response.status, 200)
            self.assertIn('action="/settings/console-port"', page)
            with tempfile.TemporaryDirectory() as directory:
                prefix = Path(directory)
                (prefix / 'module_manager.py').write_text('')
                token = app.access_csrf_token(session, 'module:web_http:disable')
                body = urlencode({'module': 'web_http', 'action': 'disable', 'csrf': token})
                with patch.object(app, 'BASE_DIR', prefix), \
                     patch.object(app, 'installed_modules', return_value={'web'}), \
                     patch.object(app, 'module_status_path', return_value=prefix / 'missing-job'), \
                     patch.object(app, 'save_module_status') as save, \
                     patch.object(app.shutil, 'which', return_value='/usr/bin/systemd-run'), \
                     patch.object(app.subprocess, 'run', return_value=type('Result', (), {'returncode': 0})()) as run:
                    conn = self.connect()
                    conn.request('POST', '/settings/modules/action', body,
                                 {'Cookie': f'session={session}',
                                  'Content-Type': 'application/x-www-form-urlencoded'})
                    response = conn.getresponse()
                    response.read()
                    conn.close()
                self.assertEqual(response.status, 302)
                save.assert_called_once_with(prefix, 'web_http', 'queued', action='disable')
                self.assertEqual(run.call_args.args[0][-3:], ['disable', 'web_http', str(prefix)])
        finally:
            app.destroy_session(session)

    def test_public_listener_startup_obeys_each_switch(self):
        for http_enabled, https_enabled, expected in (
            (True, False, [(app.PUBLIC_HTTP_PORT, False)]),
            (False, True, [(app.PUBLIC_HTTPS_PORT, True)]),
            (False, False, []),
        ):
            with self.subTest(http=http_enabled, https=https_enabled), \
                 patch.object(app, 'PUBLIC_HTTP_ENABLED', http_enabled), \
                 patch.object(app, 'PUBLIC_HTTPS_ENABLED', https_enabled), \
                 patch.object(app, 'make_server', side_effect=lambda port, handler, tls: object()) as make, \
                 patch.object(app, 'serve_forever_in_thread'):
                servers = []
                status = app.start_public_listeners(servers)
                self.assertEqual([(call.args[0], call.args[2]) for call in make.call_args_list], expected)
                self.assertEqual(len(servers), len(expected))
                self.assertEqual(status['http']['bound'], http_enabled)
                self.assertEqual(status['https']['bound'], https_enabled)

    def test_occupied_public_port_is_named_on_home_and_modules(self):
        session = app.create_session()
        with tempfile.TemporaryDirectory() as directory:
            status = Path(directory) / 'module-job.json'
            status.write_text(json.dumps({'module': 'web_http', 'state': 'failed',
                                          'reason': 'port_occupied', 'port': 80}))
            try:
                with patch.object(app, 'module_status_path', return_value=status), \
                     patch.object(app, 'installed_modules', return_value={'web'}), \
                     patch.object(app, 'PUBLIC_HTTP_ENABLED', False):
                    for route in ('/', '/settings/modules'):
                        conn = self.connect()
                        conn.request('GET', route, headers={'Cookie': f'session={session}'})
                        response = conn.getresponse()
                        body = response.read().decode()
                        conn.close()
                        self.assertEqual(response.status, 200)
                        self.assertIn('Port 80 is already in use.', body)
            finally:
                app.destroy_session(session)

    def test_public_listener_reports_bind_conflict(self):
        with patch.object(app, 'PUBLIC_HTTP_ENABLED', True), \
             patch.object(app, 'PUBLIC_HTTPS_ENABLED', False), \
             patch.object(app, 'make_server', side_effect=OSError(98, 'Address already in use')):
            status = app.start_public_listeners([])
        self.assertFalse(status['http']['bound'])
        self.assertEqual(status['http']['reason'], 'occupied')
        self.assertFalse(status['https']['enabled'])

    def test_frpc_module_shows_install_only_when_program_or_unit_is_missing(self):
        session = app.create_session()
        try:
            for installed, expected_action in (({'web'}, 'install'), ({'web', 'frpc'}, 'uninstall')):
                with self.subTest(expected_action=expected_action), \
                     patch.object(app, 'installed_modules', return_value=installed), \
                     patch.object(app, 'frpc_names', return_value=[]):
                    conn = self.connect()
                    conn.request('GET', '/settings/modules?lang=en',
                                 headers={'Cookie': f'session={session}'})
                    response = conn.getresponse()
                    body = response.read().decode()
                    conn.close()
                    self.assertEqual(response.status, 200)
                    card = re.search(r'<section class="module-card"><div><h2>FRPC</h2>(.*?)</section>',
                                     body, re.S)
                    self.assertIsNotNone(card)
                    self.assertIn(f'name="action" value="{expected_action}"', card[0])
                    if expected_action == 'install':
                        self.assertIn('Not installed', card[0])
                        self.assertNotIn('href="/frp/client/edit"', card[0])
                    else:
                        self.assertIn('Installed, no server instances', card[0])
                        self.assertIn('href="/frp/client/edit"', card[0])
        finally:
            app.destroy_session(session)

    def test_frpc_home_stays_enabled_when_every_instance_is_stopped(self):
        session = app.create_session()
        try:
            with patch.object(app, 'installed_modules', return_value={'web', 'frpc'}), \
                 patch.object(app, 'frpc_names', return_value=['demo']), \
                 patch.object(app, '_run_quiet', return_value=False):
                self.assertTrue(app.module_states()['frpc'])
                conn = self.connect()
                conn.request('GET', '/', headers={'Cookie': f'session={session}'})
                response = conn.getresponse()
                body = response.read().decode()
                conn.close()
                card = re.search(r'<article class="tile" data-module="frpc">(.*?)</article>', body, re.S)
                self.assertIsNotNone(card)
                self.assertIn('aria-checked="true"', card[0])
                self.assertIn('href="/frpc"', card[0])
        finally:
            app.destroy_session(session)

    def test_login_session_survives_web_state_reload(self):
        token = app.create_session(security_verified=True)
        try:
            with app._sessions_lock:
                app._sessions.clear()
                app._security_sessions.clear()
                app._ip_sessions.clear()
                app._feature_auth.load_sessions(app)
            self.assertTrue(app.session_valid(token))
            self.assertTrue(app.security_settings_valid(token))
            self.assertEqual(app.SESSION_STATE_FILE.stat().st_mode & 0o777, 0o600)
        finally:
            app.destroy_session(token)

    def test_login_page_has_accessible_password_control(self):
        conn = self.connect()
        conn.request("GET", "/login")
        response = conn.getresponse()
        body = response.read().decode()
        conn.close()
        self.assertEqual(response.status, 200)
        self.assertIn('autocomplete="current-password"', body)
        self.assertIn('class="app-login-header"', body)
        self.assertIn('class="app-login-brand" href="/"', body)
        self.assertIn('class="password-toggle" aria-controls="login-password"', body)
        self.assertIn('aria-pressed="false" aria-label="Show Password"', body)
        self.assertIn('class="language-menu login-language-menu"', body)
        self.assertIn('class="login-footer app-login-footer"', body)
        self.assertIn('class="login-version app-login-version" href="/changelog"', body)
        self.assertIn('action="/login/ip"', body)
        self.assertIn('/static/password-fields.js', body)
        self.assertNotIn('/static/auth-history.js', body)
        conn = self.connect()
        conn.request("POST", "/login/ip", body="")
        response = conn.getresponse()
        self.assertEqual((response.status, response.getheader("Location")),
                         (302, "/login?ip=unavailable&next=settings"))
        response.read()
        conn.close()
        conn = self.connect()
        conn.request("GET", "/login?ip=unavailable&next=settings")
        response = conn.getresponse()
        denied = response.read().decode()
        conn.close()
        self.assertEqual(response.status, 200)
        self.assertIn("This IP cannot use password-free access", denied)
        self.assertIn('name="next" value="settings"', denied)
        self.assertNotIn('aria-invalid="true"', denied)

    def test_console_port_setting_submits_a_checked_background_job(self):
        session = app.create_session()
        try:
            with tempfile.TemporaryDirectory() as directory:
                prefix = Path(directory)
                (prefix / 'console_port.py').write_text('helper')
                with patch.object(app, 'BASE_DIR', prefix), \
                     patch.object(app.shutil, 'which', return_value='/usr/bin/systemd-run'), \
                     patch.object(app.ConsoleHandler, 'render_page', side_effect=lambda title, body, lang, **kwargs: body), \
                     patch.object(app.subprocess, 'run', return_value=type('Result', (), {'returncode': 0})()) as run:
                    body = urlencode({'csrf': app.access_csrf_token(session, 'console-port'),
                                      'port': '60001'})
                    conn = self.connect()
                    conn.request('POST', '/settings/console-port', body,
                                 {'Cookie': f'session={session}',
                                  'Content-Type': 'application/x-www-form-urlencoded',
                                  'Host': '127.0.0.1:44816'})
                    response = conn.getresponse()
                    result = response.read().decode()
                    conn.close()
                    self.assertEqual(response.status, 200)
                    self.assertIn('http://127.0.0.1:60001/settings', result)
                    self.assertEqual(run.call_args.args[0][-5:],
                                     ['change', str(prefix), str(app.CONSOLE_PORT), '60001',
                                      str(app.CONSOLE_PORT_FILE)])
        finally:
            app.destroy_session(session)

    def test_server_label_uses_ordinary_settings_and_updates_brand_and_title(self):
        session = app.create_session()
        with tempfile.TemporaryDirectory() as directory, patch.object(app, 'DATA_DIR', Path(directory)):
            try:
                def request(method, path, form=None):
                    conn = self.connect()
                    body = urlencode(form) if form is not None else None
                    headers = {'Cookie': f'session={session}'}
                    if body is not None:
                        headers['Content-Type'] = 'application/x-www-form-urlencoded'
                    conn.request(method, path, body, headers)
                    response = conn.getresponse()
                    result = response.status, response.getheader('Location'), response.read().decode()
                    conn.close()
                    return result

                status, _, page = request('GET', '/settings')
                self.assertEqual(status, 200)
                self.assertIn('action="/settings/server-label"', page)
                self.assertNotIn('class="server-label"', page)
                form = {'csrf': app.access_csrf_token(session, 'server-label'), 'label': '阿里云-广州'}
                self.assertEqual(request('POST', '/settings/server-label',
                                         {'csrf': 'wrong', 'label': 'test'})[0], 403)
                self.assertEqual(request('POST', '/settings/server-label', form)[:2],
                                 (302, '/settings?msg=server_label_saved#settings-identity'))
                self.assertEqual(app.server_label(), '阿里云-广州')
                self.assertEqual((Path(directory) / 'server-label.txt').stat().st_mode & 0o777, 0o600)
                status, _, home = request('GET', '/')
                self.assertEqual(status, 200)
                self.assertIn('<span class="server-label" title="阿里云-广州">阿里云-广州</span>', home)
                self.assertIn('<title>阿里云-广州 — Home — vps-server</title>', home)
                self.assertEqual(request('POST', '/settings/server-label',
                                         {**form, 'label': '<script>'})[1],
                                 '/settings?msg=server_label_invalid#settings-identity')
                self.assertEqual(app.server_label(), '阿里云-广州')
                self.assertEqual(request('POST', '/settings/server-label',
                                         {**form, 'label': ''})[0], 302)
                self.assertEqual(app.server_label(), '')
            finally:
                app.destroy_session(session)

    def test_access_settings_reject_public_ips_and_require_password_session(self):
        with tempfile.TemporaryDirectory() as directory:
            allowlist = app.IpAllowlist(Path(directory) / "login-access.json")
            password_file = Path(directory) / "password.txt"
            with patch.object(app, "IP_ALLOWLIST", allowlist), \
                 patch.object(app, "PASSWORD_FILE", password_file), \
                 patch.object(app, "ADMIN_PASSWORD", self.password):
                def request(method, path, form=None, session=None, headers=None):
                    connection = self.connect()
                    all_headers = dict(headers or {})
                    if session:
                        all_headers["Cookie"] = f"session={session}"
                    body = urlencode(form) if form is not None else None
                    if body is not None:
                        all_headers["Content-Type"] = "application/x-www-form-urlencoded"
                    connection.request(method, path, body=body, headers=all_headers)
                    response = connection.getresponse()
                    result = response.status, response.getheader("Location"), response.read().decode()
                    connection.close()
                    return result
                self.assertEqual(request("GET", "/settings")[:2], (302, "/login?next=preferences"))
                self.assertEqual(request("GET", "/settings/security")[:2],
                                 (302, "/login?next=settings"))
                status, _, login_page = request("GET", "/login?next=preferences")
                self.assertEqual(status, 200)
                self.assertIn('name="next" value="preferences"', login_page)
                self.assertNotIn("Enter the admin password to manage access settings", login_page)
                self.assertEqual(request("POST", "/login", {"password": self.password,
                                                             "next": "preferences"})[:2],
                                 (302, "/settings"))
                session = self.login()
                status, _, page = request("GET", "/settings", session=session)
                self.assertEqual(status, 200)
                self.assertIn('href="/settings/security"', page)
                self.assertIn('id="settings-security"', page)
                self.assertIn('href="#settings-security"', page)
                self.assertIn('href="/settings/security"', page)
                self.assertIn('href="/settings?lang=zh_cn"', page)
                self.assertIn('data-theme-choice="sage"', page)
                self.assertNotIn('action="/settings/ip/add"', page)
                status, _, page = request("GET", "/settings/security", session=session)
                self.assertEqual(status, 200)
                self.assertIn("Specified IP password-free access", page)
                self.assertIn('action="/settings/ip/add"', page)
                self.assertIn('placeholder="192.168.1.10 / fd12::1"', page)
                self.assertIn('action="/settings/ip/toggle"', page)
                self.assertNotIn('name="current"', page)
                csrf = app.access_csrf_token(session, "ip-add")
                self.assertEqual(request("POST", "/settings/ip/add",
                                         {"csrf": csrf, "ip": "8.8.8.8"}, session)[:2],
                                 (302, "/settings/security?msg=access_ip_invalid"))
                self.assertEqual(allowlist.list_addresses(), [])
                self.assertEqual(request("POST", "/settings/ip/add",
                                         {"csrf": csrf, "ip": "192.168.7.21"}, session)[:2],
                                 (302, "/settings/security?msg=access_ip_added"))
                self.assertEqual(allowlist.list_addresses(), ["192.168.7.21"])
                self.assertEqual(request("POST", "/settings/ip/add",
                                         {"csrf": csrf, "ip": "fd12::1"}, session)[:2],
                                 (302, "/settings/security?msg=access_ip_added"))
                toggle = app.access_csrf_token(session, "ip-toggle")
                self.assertEqual(request("POST", "/settings/ip/toggle",
                                         {"csrf": toggle, "enabled": "0"}, session)[:2],
                                 (302, "/settings/security?msg=access_ip_disabled"))
                self.assertFalse(allowlist.contains("192.168.7.21"))
                self.assertFalse(app.IpAllowlist(allowlist.path).is_enabled())
                self.assertEqual(request("POST", "/settings/ip/toggle",
                                         {"csrf": toggle, "enabled": "1"}, session)[:2],
                                 (302, "/settings/security?msg=access_ip_enabled"))
                self.assertTrue(allowlist.contains("fd12::1"))
                status, _, page = request("GET", "/settings/security", session=session)
                self.assertEqual(status, 200)
                self.assertIn('class="access-remove"', page)
                self.assertEqual(request("POST", "/settings/password",
                                         {"csrf": app.access_csrf_token(session, "password"),
                                          "new": "new-password-1234",
                                          "confirm": "new-password-1234"}, session)[:2],
                                 (302, "/login?changed=1"))
                self.assertEqual(password_file.read_text().strip(), "new-password-1234")
                self.assertFalse(app.session_valid(session))

    def test_security_permission_expires_and_password_challenge_rotates_session(self):
        session = self.login()
        try:
            with app._sessions_lock:
                app._security_sessions[session] = time.time() - 1
            conn = self.connect()
            conn.request("GET", "/settings/security", headers={"Cookie": f"session={session}"})
            response = conn.getresponse()
            self.assertEqual((response.status, response.getheader("Location")),
                             (302, "/settings/verify"))
            response.read()
            conn.close()

            def post(path, fields):
                connection = self.connect()
                connection.request("POST", path, body=urlencode(fields), headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Cookie": f"session={session}"})
                response = connection.getresponse()
                result = response.status, response.getheader("Location"), response.getheader("Set-Cookie")
                response.read()
                connection.close()
                return result

            self.assertEqual(post("/settings/ip/add", {"csrf": app.access_csrf_token(session, "ip-add"),
                                                          "ip": "10.2.3.4"})[0], 403)
            csrf = app.access_csrf_token(session, "verify")
            self.assertEqual(post("/settings/verify", {"csrf": csrf, "password": "wrong"})[0], 401)
            status, location, cookie = post("/settings/verify", {"csrf": csrf,
                                                                   "password": self.password})
            self.assertEqual((status, location), (302, "/settings/security"))
            jar = SimpleCookie()
            jar.load(cookie)
            new_session = jar["session"].value
            self.assertNotEqual(session, new_session)
            self.assertFalse(app.session_valid(session))
            self.assertTrue(app.security_settings_valid(new_session))
            app.destroy_session(new_session)
        finally:
            app.destroy_session(session)

    def test_ip_admission_uses_peer_not_forwarded_header_and_cannot_edit_access(self):
        with tempfile.TemporaryDirectory() as directory:
            allowlist = app.IpAllowlist(Path(directory) / "login-access.json")
            allowlist.change("192.168.7.21", add=True)
            with patch.object(app, "IP_ALLOWLIST", allowlist), patch.object(app, "TRUST_PROXY", True):
                conn = self.connect()
                conn.request("GET", "/", headers={"X-Forwarded-For": "192.168.7.21"})
                response = conn.getresponse()
                self.assertEqual((response.status, response.getheader("Location")), (302, "/login"))
                response.read()
                conn.close()
                with patch.object(app, "TRUST_PROXY", False), \
                     patch.object(allowlist, "contains", return_value=True):
                    conn = self.connect()
                    conn.request("GET", "/")
                    response = conn.getresponse()
                    self.assertEqual((response.status, response.getheader("Location")), (302, "/login"))
                    response.read()
                    conn.close()
                    conn = self.connect()
                    conn.request("GET", "/login")
                    response = conn.getresponse()
                    self.assertIn('action="/login/ip"', response.read().decode())
                    conn.close()
                    conn = self.connect()
                    conn.request("POST", "/login/ip", body="", headers={"Content-Type": "application/x-www-form-urlencoded"})
                    response = conn.getresponse()
                    self.assertEqual((response.status, response.getheader("Location")), (302, "/"))
                    cookie = SimpleCookie()
                    cookie.load(response.getheader("Set-Cookie"))
                    ip_token = cookie["session"].value
                    self.assertFalse(app.session_valid(ip_token))
                    response.read()
                    conn.close()
                    conn = self.connect()
                    conn.request("GET", "/", headers={"Cookie": f"session={ip_token}"})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    dashboard = response.read().decode()
                    self.assertIn('href="/settings"', dashboard)
                    self.assertNotIn('href="/login?next=settings"', dashboard)
                    conn.close()
                    conn = self.connect()
                    conn.request("GET", "/settings", headers={"Cookie": f"session={ip_token}"})
                    response = conn.getresponse()
                    preferences = response.read().decode()
                    self.assertEqual(response.status, 200)
                    self.assertIn('href="/settings/security"', preferences)
                    self.assertNotIn('action="/settings/ip/add"', preferences)
                    conn.close()
                    conn = self.connect()
                    conn.request("GET", "/settings/security", headers={"Cookie": f"session={ip_token}"})
                    response = conn.getresponse()
                    self.assertEqual((response.status, response.getheader("Location")),
                                     (302, "/settings/verify"))
                    response.read()
                    conn.close()
                    conn = self.connect()
                    conn.request("GET", "/settings/verify", headers={"Cookie": f"session={ip_token}"})
                    response = conn.getresponse()
                    challenge = response.read().decode()
                    self.assertEqual(response.status, 200)
                    self.assertIn('action="/settings/verify"', challenge)
                    self.assertIn('class="access-verify-form"', challenge)
                    self.assertNotIn('action="/settings/ip/add"', challenge)
                    conn.close()
                    conn = self.connect()
                    conn.request("POST", "/settings/ip/add", body="ip=10.0.0.2&csrf=no",
                                 headers={"Content-Type": "application/x-www-form-urlencoded",
                                          "Cookie": f"session={ip_token}"})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 403)
                    response.read()
                    conn.close()
                self.assertFalse(app.ip_session_valid(ip_token, "127.0.0.1"))
                app.destroy_session(ip_token)
            with patch.object(app, "IP_ALLOWLIST", allowlist), patch.object(app, "TRUST_PROXY", False):
                conn = self.connect()
                conn.request("GET", "/", headers={"X-Forwarded-For": "192.168.7.21"})
                response = conn.getresponse()
                self.assertEqual((response.status, response.getheader("Location")), (302, "/login"))
                response.read()
                conn.close()

    def test_managed_node_page_and_edit_request(self):
        identifier = "12345678-1234-4234-8234-123456789abc"
        node = {"id": identifier, "number": 7, "name": "Tokyo node",
                "protocol": "anytls", "port": 25001, "enabled": True,
                "inbound": {"users": [{"password": "test-secret"}],
                            "tls": {"certificate_path": "/missing/cert.pem"}},
                "cap_bytes": 10485760, "upload_bytes": 1048576,
                "download_bytes": 2097152, "expires_at": None, "expiry_count": None, "expiry_unit": None,
                "cap_action": "throttle", "upload_limit_bps": None, "download_limit_bps": None,
                "reset_mode": "monthly", "next_reset_at": "2030-02-01T00:00:00+00:00"}
        applied = []
        session = self.login()
        state_file = Path(TEST_DATA_DIR) / "managed-node-state.json"
        state_file.write_text("{}")
        with patch.object(app, "read_inventory", return_value={"nodes": [node]}), \
             patch.object(app, "NODE_STATE_PATH", state_file), \
             patch.object(app, "_read_json", return_value={"ledger": {"nodes": {
                 identifier: {"suspect": False}}}}), \
             patch.object(app, "anytls_node", return_value={"running": True,
                 "port": 25001, "password": "test-secret", "sni": "example.org"}), \
             patch.object(app, "proxy_nodes", return_value=[]), \
             patch.object(app, "address_entries", return_value=[]), \
             patch.object(app, "node_control_apply", side_effect=lambda request: applied.append(request) or True):
            conn = self.connect()
            conn.request("GET", "/proxy", headers={"Cookie": f"session={session}"})
            response = conn.getresponse()
            body = response.read().decode()
            conn.close()
            self.assertEqual(response.status, 200)
            self.assertIn("Tokyo node", body)
            self.assertIn("#7", body)
            self.assertIn("1.0 MiB", body)
            self.assertIn('action="/proxy/node/edit"', body)
            self.assertIn('action="/proxy/node/toggle"', body)
            self.assertIn('role="switch" aria-checked="true"', body)
            self.assertNotIn('action="/anytls/reset"', body)
            self.assertNotIn(f'>{identifier}<', body)

            form = urlencode({"id": identifier, "csrf": app.node_csrf_token(session, identifier),
                              "name": "New name", "port": "25002", "credential": "",
                              "sni": "example.org"})
            conn = self.connect()
            conn.request("POST", "/proxy/node/edit", body=form,
                         headers={"Cookie": f"session={session}",
                                  "Content-Type": "application/x-www-form-urlencoded"})
            response = conn.getresponse()
            response.read()
            conn.close()
            self.assertEqual(response.status, 302)
            self.assertEqual(len(applied), 1)
            self.assertEqual(applied[0]["id"], identifier)
            self.assertEqual(applied[0]["name"], "New name")

            limits = urlencode({"id": identifier, "csrf": app.node_csrf_token(session, identifier),
                                "cap_gib": "12", "upload_mbps": "2.5", "download_mbps": "0.5",
                                "cap_action": "block", "expiry_mode": "set", "expiry_count": "6",
                                "expiry_unit": "months", "reset_mode": "repeat",
                                "reset_count": "1", "reset_unit": "months", "next_reset_at": ""})
            conn = self.connect()
            conn.request("POST", "/proxy/node/limits", body=limits,
                         headers={"Cookie": f"session={session}",
                                  "Content-Type": "application/x-www-form-urlencoded"})
            response = conn.getresponse()
            response.read()
            conn.close()
            self.assertEqual(response.status, 302)
            self.assertEqual(applied[1]["cap_bytes"], 12 * 1073741824)
            self.assertEqual(applied[1]["upload_limit_bps"], 2_500_000)
            self.assertEqual(applied[1]["download_limit_bps"], 500_000)
            self.assertEqual(applied[1]["cap_action"], "block")
            self.assertEqual(applied[1]["expiry_count"], 6)
            self.assertTrue(applied[1]["reset_mode"].startswith("every:1:months:"))

            toggle = urlencode({"id": identifier, "csrf": app.node_csrf_token(session, identifier),
                                "enabled": "no"})
            conn = self.connect()
            conn.request("POST", "/proxy/node/toggle", body=toggle,
                         headers={"Cookie": f"session={session}",
                                  "Content-Type": "application/x-www-form-urlencoded"})
            response = conn.getresponse()
            response.read()
            conn.close()
            self.assertEqual(response.status, 302)
            self.assertEqual(applied[2], {"action": "toggle", "id": identifier, "enabled": False})

    def test_clash_subscription_is_single_node_and_revoked_on_edit(self):
        node = {"id": "12345678-1234-4234-8234-123456789abc", "number": 1,
                "name": "Office node", "protocol": "anytls", "port": 25001, "enabled": True,
                "inbound": {"type": "anytls", "listen_port": 25001,
                            "users": [{"password": "test-secret"}],
                            "tls": {"certificate_path": "/missing/cert.pem"}},
                "cap_bytes": None, "upload_bytes": 0, "download_bytes": 0,
                "expires_at": None, "expiry_count": None, "expiry_unit": None,
                "cap_action": "throttle", "upload_limit_bps": None, "download_limit_bps": None,
                "reset_mode": "none", "next_reset_at": None}
        state_file = Path(TEST_DATA_DIR) / "clash-node-state.json"
        state_file.write_text("{}")
        path = f"/clash/sub/{node['id']}/{app.clash_share_token(node)}"
        with patch.object(app, "read_inventory", return_value={"nodes": [node]}), \
             patch.object(app, "NODE_STATE_PATH", state_file), \
             patch.object(app, "anytls_node", return_value={"running": True, "port": 25001,
                                                             "password": "test-secret", "sni": "example.org"}), \
             patch.object(app, "proxy_nodes", return_value=[]), \
             patch.object(app, "local_addresses", return_value=[("eth0", "192.168.50.23")]), \
             patch.object(app, "_cert_common_name", return_value="example.org"):
            conn = self.connect()
            conn.request("GET", "/proxy", headers={"Cookie": "session=" + self.login()})
            response = conn.getresponse()
            page = response.read().decode()
            conn.close()
            self.assertEqual(response.status, 200)
            self.assertIn("Traffic cap (GiB)", page)
            self.assertIn('name="cap_gib"', page)
            self.assertIn('class="node-import private-share-import"', page)
            self.assertIn('class="private-share-copy"', page)
            self.assertLess(page.index('class="private-share-copy"'), page.index('class="node-import private-share-import"'))
            self.assertIn("/static/qrcode-render.js", page)
            self.assertNotIn(path, page)
            self.assertNotIn('test-secret', page)
            self.assertNotIn('25001', page)
            self.assertNotIn(f'>{node["id"]}<', page)
            session = self.login()
            conn = self.connect()
            conn.request("GET", f"/proxy/private-value?id={node['id']}&field=share",
                         headers={"Cookie": "session=" + session})
            response = conn.getresponse()
            copied = json.loads(response.read())["value"]
            conn.close()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Cache-Control"), "no-store")
            self.assertEqual(copied, f"http://192.168.50.23:{app.CONSOLE_PORT}{path}")
            conn = self.connect()
            conn.request("GET", f"/proxy/private-value?id={node['id']}&field=credential")
            response = conn.getresponse()
            response.read()
            conn.close()
            self.assertEqual(response.status, 302)
            conn = self.connect()
            conn.request("GET", path)
            response = conn.getresponse()
            profile = response.read().decode()
            conn.close()
            self.assertEqual(response.status, 200)
            self.assertIn("text/yaml", response.getheader("Content-Type"))
            self.assertEqual(response.getheader("Cache-Control"), "no-store")
            self.assertIn("mixed-port: 7890", profile)
            self.assertIn("server: 192.168.50.23", profile)
            self.assertIn('name: "Office node"', profile)
            self.assertIn('password: "test-secret"', profile)
            self.assertIn("- MATCH,NODE", profile)
            node["name"] = "Renamed node"
            conn = self.connect()
            conn.request("GET", path)
            response = conn.getresponse()
            response.read()
            conn.close()
            self.assertEqual(response.status, 404)

    def test_node_create_delete_forms_use_stable_ids(self):
        identifier = "12345678-1234-4234-8234-123456789abc"
        node = {"id": identifier, "number": 3, "name": "First", "protocol": "shadowsocks",
                "port": 24001, "enabled": True, "inbound": {"password": "test-key"},
                "cap_bytes": None, "upload_bytes": 0, "download_bytes": 0,
                "expires_at": None, "expiry_count": None, "expiry_unit": None,
                "cap_action": "throttle", "upload_limit_bps": None, "download_limit_bps": None,
                "reset_mode": "none", "next_reset_at": None}
        second = {**node, "id": "22345678-1234-4234-8234-123456789abc",
                  "number": 4, "name": "Second", "port": 24002}
        state_file = Path(TEST_DATA_DIR) / "multi-node-state.json"
        state_file.write_text("{}")
        config_file = Path(TEST_DATA_DIR) / "multi-proxy.json"
        config_file.write_text("{}")
        applied = []
        session = self.login()
        with patch.object(app, "read_inventory", return_value={"nodes": [node, second]}), \
             patch.object(app, "NODE_STATE_PATH", state_file), \
             patch.object(app, "PROXY_CONFIG", config_file), \
             patch.object(app, "anytls_node", return_value=None), \
             patch.object(app, "proxy_running", return_value=True), \
             patch.object(app, "address_entries", return_value=[]), \
             patch.object(app, "node_control_apply", side_effect=lambda request: applied.append(request) or True):
            conn = self.connect()
            conn.request("GET", "/proxy", headers={"Cookie": f"session={session}"})
            response = conn.getresponse()
            page = response.read().decode()
            conn.close()
            self.assertEqual(response.status, 200)
            self.assertIn("First", page)
            self.assertIn("Second", page)
            self.assertIn('action="/proxy/node/create"', page)
            self.assertEqual(page.count('action="/proxy/node/delete"'), 2)
            self.assertEqual(page.count('class="node-confirm-dialog"'), 4)
            self.assertEqual(page.count('class="node-access-dialog"'), 2)
            self.assertEqual(page.count('action="/proxy/node/limits"'), 2)
            self.assertIn('data-dialog-open="node-access-12345678-1234-4234-8234-123456789abc"', page)
            self.assertNotIn('<details><summary>Access management</summary>', page)
            self.assertNotIn('type="checkbox" name="confirm"', page)
            self.assertIn('name="credential" value=""', page)
            self.assertIn('name="sni" value="www.bing.com"', page)
            for path, form in (
                ("/proxy/node/create", {"protocol": "shadowsocks", "name": "Third",
                                         "port": "", "sni": "", "credential": "",
                                         "csrf": app.node_csrf_token(session, "create")}),
                ("/proxy/node/create", {"protocol": "anytls", "name": "Fourth",
                                         "port": "25003", "sni": "", "credential": "manual-anytls-secret",
                                         "csrf": app.node_csrf_token(session, "create")}),
                ("/proxy/node/delete", {"id": second["id"], "confirm": "yes",
                                         "csrf": app.node_csrf_token(session, second["id"])}),
            ):
                conn = self.connect()
                conn.request("POST", path, body=urlencode(form),
                             headers={"Cookie": f"session={session}",
                                      "Content-Type": "application/x-www-form-urlencoded"})
                response = conn.getresponse()
                response.read()
                conn.close()
                self.assertEqual(response.status, 302)
        self.assertEqual(applied[0], {"action": "create", "protocol": "shadowsocks",
                                      "name": "Third", "port": None})
        self.assertEqual(applied[1], {"action": "create", "protocol": "anytls", "name": "Fourth",
                                      "port": 25003, "sni": "www.bing.com",
                                      "credential": "manual-anytls-secret"})
        self.assertEqual(applied[2], {"action": "delete", "id": second["id"]})

    def test_clash_profile_escapes_custom_password(self):
        password = 'quote" and\nline'
        node = {"protocol": "trojan", "name": "Node", "port": 24000,
                "inbound": {"users": [{"password": password}],
                            "tls": {"certificate_path": "/missing/cert.pem"}}}
        with patch.object(app, "_cert_common_name", return_value="example.org"):
            profile = app.clash_profile(node, "192.168.50.23")
        self.assertIn("password: " + json.dumps(password), profile)
        self.assertNotIn(password, profile)

    def test_frps_panel_requires_auth_and_never_appears_on_auth_off_console(self):
        config = Path(TEST_DATA_DIR) / 'frps.toml'
        config.write_text('bindAddr = "0.0.0.0"\nbindPort = 7000\nauth.token = "test-frps-secret"\n')
        with patch.object(app, 'FRPS_CONFIG', config):
            conn = self.connect()
            conn.request('GET', '/frps')
            response = conn.getresponse()
            self.assertEqual(response.status, 302)
            self.assertNotIn(b'test-frps-secret', response.read())
            conn.close()
            cookie = self.login()
            conn = self.connect()
            conn.request('GET', '/frps', headers={'Cookie': 'session=' + cookie})
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader('Cache-Control'), 'no-store')
            body = response.read()
            self.assertNotIn(b'test-frps-secret', body)
            self.assertNotIn(b'7000', body)
            self.assertNotIn(b'FRPC client', body)
            self.assertIn(b'/static/favicon-frp.svg', body)
            conn.close()
            conn = self.connect()
            conn.request('GET', '/static/favicon-frp.svg')
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader('Content-Type'), 'image/svg+xml')
            self.assertIn(b'<svg', response.read())
            conn.close()
            conn = self.connect()
            conn.request('GET', '/proxy/private-value?id=frps&field=credential',
                         headers={'Cookie': 'session=' + cookie})
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())['value'], 'test-frps-secret')
            conn.close()
            with patch.object(app, 'AUTH_ENABLED', False):
                conn = self.connect()
                conn.request('GET', '/frps')
                response = conn.getresponse()
                self.assertNotIn(b'test-frps-secret', response.read())
                conn.close()

    def test_frp_page_explains_missing_server_without_exposing_client_template(self):
        cookie = self.login()
        with patch.object(app, 'FRPS_CONFIG', Path(TEST_DATA_DIR) / 'missing-frps.toml'):
            conn = self.connect()
            conn.request('GET', '/frps', headers={'Cookie': 'session=' + cookie})
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            body = response.read()
            self.assertIn(b'FRPS is not installed', body)
            self.assertNotIn(b'data-private-field="frpc-config"', body)
            conn.close()

    def test_removed_modules_show_the_same_install_page(self):
        cookie = self.login()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.install-state').write_text('modules=web\n')
            with patch.object(app, 'BASE_DIR', root), \
                 patch.object(app, 'installed_modules', return_value={'web'}), \
                 patch.object(app, 'ui_icon', return_value='<svg></svg>'), \
                 patch.object(app, 'frps_node', return_value={'port': 7000}), \
                 patch.object(app, 'frpc_names', return_value=['demo']):
                for path, name in (('/iperf', 'iperf3'), ('/frps', 'FRPS'),
                                   ('/frpc', 'FRPC'), ('/proxy', 'Singbox')):
                    with self.subTest(path=path):
                        conn = self.connect()
                        conn.request('GET', path + '?lang=zh_cn',
                                     headers={'Cookie': 'session=' + cookie})
                        response = conn.getresponse()
                        body = response.read().decode()
                        conn.close()
                        self.assertEqual(response.status, 200)
                        self.assertIn('<div class="card access-card">', body)
                        self.assertIn('本机未安装 ' + name, body)
                        self.assertIn('安装 ' + name + '</a>', body)
                        self.assertIn('href="/settings/modules"', body)
                        self.assertNotIn('frp-target-card', body)
                        self.assertNotIn('iperf-client-form', body)

    def test_closed_page_has_a_return_home_button(self):
        cookie = self.login()
        with patch.object(app, 'module_states', return_value={'portfwd': False}):
            conn = self.connect()
            conn.request('GET', '/closed?module=portfwd&lang=zh_cn',
                         headers={'Cookie': 'session=' + cookie})
            response = conn.getresponse()
            body = response.read().decode()
            conn.close()
        self.assertEqual(response.status, 200)
        self.assertIn('<a class="page-back" href="/">返回首页</a>', body)
        self.assertIn('页面已关闭', body)

    def test_frps_and_frpc_have_separate_pages(self):
        cookie = self.login()
        config = Path(TEST_DATA_DIR) / 'separate-frps.toml'
        config.write_text('bindAddr = "0.0.0.0"\nbindPort = 7000\nauth.token = "separate-secret"\n')
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(app, 'FRPS_CONFIG', config), \
             patch.object(frp_control, 'CLIENT_DIR', Path(directory)):
            (Path(directory) / 'frpc-demo.toml').write_text(
                frp_control.build_client('203.0.113.42', 7000, 'client-secret', []))
            for path, expected, excluded in (('/frps', 'FRPS server', 'frp-target-card'),
                                             ('/frpc', 'FRPC client', 'frps-inline-token')):
                conn = self.connect()
                conn.request('GET', path + '?lang=en', headers={'Cookie': 'session=' + cookie})
                response = conn.getresponse()
                body = response.read().decode()
                conn.close()
                self.assertEqual(response.status, 200)
                self.assertIn(expected, body)
                self.assertNotIn(excluded, body)
            conn = self.connect()
            conn.request('GET', '/frp', headers={'Cookie': 'session=' + cookie})
            response = conn.getresponse()
            self.assertEqual(response.status, 302)
            self.assertEqual(response.getheader('Location'), '/frpc')
            response.read()
            conn.close()

    def test_frpc_editor_uses_ordinary_session_and_reveals_token_on_request(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(frp_control, 'CLIENT_DIR', Path(directory)):
            config = Path(directory) / 'frpc-demo.toml'
            config.write_text('serverAddr = "203.0.113.42"\nserverPort = 7000\n'
                              'auth.method = "token"\nauth.token = "private-example-token"\n'
                              '[[proxies]]\nname = "web"\ntype = "tcp"\nlocalIP = "127.0.0.1"\n'
                              'localPort = 8080\nremotePort = 18080\n')
            ordinary = app.create_session()
            try:
                def request(path, cookie):
                    conn = self.connect()
                    conn.request('GET', path, headers={'Cookie': 'session=' + cookie})
                    response = conn.getresponse()
                    result = response.status, response.getheader('Location'), response.read().decode()
                    conn.close()
                    return result
                status, _, editor = request('/frp/client/edit?name=demo', ordinary)
                self.assertEqual(status, 200)
                self.assertNotIn('private-example-token', editor)
                self.assertIn('frp-fact-reveal', editor)
                self.assertIn('18080', editor)
                self.assertNotIn('frp-advanced', editor)
                status, _, value = request('/frp/client/value?name=demo&field=token', ordinary)
                self.assertEqual(status, 200)
                self.assertIn('private-example-token', json.loads(value)['value'])
                self.assertEqual(request('/frp/client/value?name=demo&field=token', '')[0], 302)
                status, _, overview = request('/frpc', ordinary)
                self.assertEqual(status, 200)
                self.assertIn('demo', overview)
                self.assertNotIn('private-example-token', overview)
                self.assertIn('frp-target-card', overview)
                self.assertIn('frp-card-ip', overview)
                self.assertNotIn('frp-reveal-ip', overview)
                self.assertIn('frp-test-connection', overview)
                csrf = app.access_csrf_token(ordinary, 'frp:test:demo')
                with patch.object(app, 'frpc_test_connection', return_value=True):
                    conn = self.connect()
                    body = urlencode({'name': 'demo', 'csrf': csrf})
                    conn.request('POST', '/frp/client/test', body=body,
                                 headers={'Cookie': 'session=' + ordinary,
                                          'Content-Type': 'application/x-www-form-urlencoded'})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertTrue(json.loads(response.read())['connected'])
                    conn.close()
                from subprocess import CompletedProcess
                save = urlencode({'name': 'demo', 'section': 'server', 'server': '203.0.113.42',
                                  'port': '7000', 'token': '',
                                  'csrf': app.access_csrf_token(ordinary, 'frp:structured:demo')})
                with patch.object(app, 'FRP_CONTROL_HELPER', Path(__file__).resolve().parents[1] / 'src/web/frp_control.py'), \
                     patch.object(app.shutil, 'which', return_value='/usr/bin/systemd-run'), \
                     patch.object(app.subprocess, 'run', return_value=CompletedProcess([], 0)):
                    conn = self.connect()
                    conn.request('POST', '/frp/client/structured', body=save,
                                 headers={'Cookie': 'session=' + ordinary,
                                          'Content-Type': 'application/x-www-form-urlencoded'})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 302)
                    self.assertEqual(response.getheader('Location'),
                                     '/frp/client/edit?name=demo&msg=done')
                    response.read()
                    conn.close()
            finally:
                app.destroy_session(ordinary)

    def test_frpc_connection_uses_peer_column_of_established_socket(self):
        from subprocess import CompletedProcess
        def command(argv, **kwargs):
            if argv[0] == 'systemctl':
                return CompletedProcess(argv, 0, '12345\n', '')
            return CompletedProcess(argv, 0,
                                    '0 0 192.0.2.10:33772 203.0.113.42:7000 users:(("frpc",pid=12345,fd=5))\n', '')
        with patch.object(app.subprocess, 'run', side_effect=command):
            self.assertTrue(app.frpc_connected('demo', '203.0.113.42', 7000))
            self.assertFalse(app.frpc_connected('demo', '203.0.113.42', 7001))

    def test_failed_unicode_frpc_creation_returns_to_new_instance_form(self):
        from subprocess import CompletedProcess
        session = app.create_session()
        try:
            body = urlencode({'name': '示例-一', 'section': 'create',
                              'server': '203.0.113.42', 'port': '7000',
                              'token': 'example-token',
                              'csrf': app.access_csrf_token(session, 'frp:structured:new')})
            with patch.object(app, 'FRP_CONTROL_HELPER', Path(__file__).resolve().parents[1] / 'src/web/frp_control.py'), \
                 patch.object(app.shutil, 'which', return_value='/usr/bin/systemd-run'), \
                 patch.object(app.subprocess, 'run', return_value=CompletedProcess([], 1)):
                conn = self.connect()
                conn.request('POST', '/frp/client/structured', body=body,
                             headers={'Cookie': 'session=' + session,
                                      'Content-Type': 'application/x-www-form-urlencoded'})
                response = conn.getresponse()
                self.assertEqual(response.status, 302)
                self.assertEqual(response.getheader('Location'), '/frp/client/edit?msg=failed')
                response.read()
                conn.close()
        finally:
            app.destroy_session(session)

    def test_frpc_connection_probe_requires_successful_login_log(self):
        from subprocess import TimeoutExpired
        config = {'serverAddr': '203.0.113.42', 'serverPort': 7000,
                  'auth': {'method': 'token', 'token': 'private-token'}, 'proxies': []}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(app, 'FRPC_BINARY', Path(directory) / 'frpc'), \
             patch.object(app, 'frpc_structured', return_value=config), \
             patch.object(app.subprocess, 'run') as run:
            app.FRPC_BINARY.touch()
            run.side_effect = TimeoutExpired('frpc', 7, output=b'login to server success')
            self.assertTrue(app.frpc_test_connection('demo'))
            run.side_effect = TimeoutExpired('frpc', 7, output=b'login to the server failed')
            self.assertFalse(app.frpc_test_connection('demo'))

    def test_lucky_credentials_only_on_authenticated_console(self):
        config = Path(TEST_DATA_DIR) / 'lucky.json'
        config.write_text(json.dumps({'BaseConfigure': {'AdminWebListenPort': 16601,
            'AdminAccount': 'test-lucky-account', 'AdminPassword': 'test-lucky-secret',
            'AllowInternetaccess': False}}))
        with patch.object(app, 'LUCKY_CONFIG', config):
            conn = self.connect()
            conn.request('GET', '/lucky')
            response = conn.getresponse()
            self.assertEqual(response.status, 302)
            self.assertNotIn(b'test-lucky-secret', response.read())
            conn.close()
            conn = self.connect()
            cookie = self.login()
            conn.request('GET', '/lucky', headers={'Cookie': 'session=' + cookie})
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader('Cache-Control'), 'no-store')
            body = response.read()
            self.assertNotIn(b'test-lucky-secret', body)
            self.assertNotIn(b'test-lucky-account', body)
            self.assertNotIn(b'16601', body)
            conn.close()
            conn = self.connect()
            conn.request('GET', '/proxy/private-value?id=lucky&field=credential',
                         headers={'Cookie': 'session=' + cookie})
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())['value'], 'test-lucky-secret')
            conn.close()
            with patch.object(app, 'AUTH_ENABLED', False):
                conn = self.connect()
                conn.request('GET', '/lucky')
                response = conn.getresponse()
                self.assertNotIn(b'test-lucky-secret', response.read())
                conn.close()

    # -- auth --------------------------------------------------------------

    def test_root_redirects_when_unauthenticated(self):
        conn = self.connect()
        conn.request("GET", "/")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 302)
        self.assertEqual(resp.getheader("Location"), "/login")
        resp.read()
        conn.close()

    def test_login_wrong_password(self):
        conn = self.connect()
        conn.request(
            "POST",
            "/login",
            body="password=not-the-password",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp = conn.getresponse()
        self.assertEqual(resp.status, 401)
        resp.read()
        conn.close()

    def test_login_then_dashboard(self):
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/", headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        body = resp.read().decode()
        self.assertIn("Speed test", body)
        self.assertIn("Recent visitors", body)
        self.assertIn("Home", body)
        nav = body.split('</nav>', 1)[0]
        self.assertEqual(nav.count('href="/"'), 2)
        self.assertLess(nav.rfind('href="/"'), nav.rfind('href="/changelog"'))
        self.assertNotIn('href="/speedtest"', nav)
        self.assertIn('href="/speedtest"', body)
        self.assertIn('href="/frps"', body)
        self.assertIn('href="/frpc"', body)
        self.assertIn('/static/auth-history.js', body)
        self.assertIn('aria-current="page" href="/"', nav)
        conn.close()

    def test_logout_invalidates_session(self):
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/logout", headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 302)
        resp.read()
        conn.close()

        conn = self.connect()
        conn.request("GET", "/", headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 302)
        self.assertEqual(resp.getheader("Location"), "/login")
        resp.read()
        conn.close()

    # -- i18n --------------------------------------------------------------

    def test_language_toggle_to_simplified_chinese(self):
        conn = self.connect()
        conn.request("GET", "/login?lang=zh_cn")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        body = resp.read().decode()
        self.assertIn("登录", body)  # Simplified "log in"
        self.assertIn('<html lang="zh-CN">', body)
        # ?lang=zh_cn should be persisted as a cookie
        self.assertIn("lang=zh_cn", resp.getheader("Set-Cookie") or "")
        conn.close()

    def test_language_toggle_to_traditional_chinese(self):
        conn = self.connect()
        conn.request("GET", "/login?lang=zh_tw")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        body = resp.read().decode()
        self.assertIn("登入", body)  # Traditional "log in"
        self.assertIn('<html lang="zh-TW">', body)
        self.assertIn("lang=zh_tw", resp.getheader("Set-Cookie") or "")
        conn.close()

    def test_default_language_is_english(self):
        conn = self.connect()
        conn.request("GET", "/login")
        resp = conn.getresponse()
        body = resp.read().decode()
        self.assertIn("Log in", body)
        self.assertIn('<html lang="en">', body)
        conn.close()

    def test_default_lang_env_overrides_fallback(self):
        # No cookie/query/matching Accept-Language -> falls back to
        # app.DEFAULT_LANG (VPSSRV_DEFAULT_LANG at startup, install.sh asks).
        original = app.DEFAULT_LANG
        app.DEFAULT_LANG = "zh_tw"
        try:
            conn = self.connect()
            conn.request("GET", "/login")
            body = conn.getresponse().read().decode()
            conn.close()
            self.assertIn("登入", body)
        finally:
            app.DEFAULT_LANG = original

    def test_accept_language_sniffs_traditional_vs_simplified(self):
        conn = self.connect()
        conn.request("GET", "/login", headers={"Accept-Language": "zh-TW,zh;q=0.9"})
        body = conn.getresponse().read().decode()
        conn.close()
        self.assertIn("登入", body)

        conn = self.connect()
        conn.request("GET", "/login", headers={"Accept-Language": "zh-CN,zh;q=0.9"})
        body = conn.getresponse().read().decode()
        conn.close()
        self.assertIn("登录", body)

    def test_settings_shows_language_choices_outside_navigation(self):
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/", headers={"Cookie": f"session={session}"})
        body = conn.getresponse().read().decode()
        conn.close()
        self.assertNotIn('class="language-menu"', body)
        self.assertNotIn('class="theme-menu"', body)
        conn = self.connect()
        conn.request("GET", "/settings", headers={"Cookie": f"session={session}"})
        body = conn.getresponse().read().decode()
        conn.close()
        self.assertIn("/settings?lang=en", body)
        self.assertIn("/settings?lang=zh_cn", body)
        self.assertIn("/settings?lang=zh_tw", body)

    # -- speed test ----------------------------------------------------
    # Endpoints match LibreSpeed's own garbage.php/empty.php/getIP.php
    # contract exactly (see vps-webserver DECISIONS.md, 2026-08-25) so the vendored
    # static/speedtest.js + speedtest_worker.js need no server-side quirks.

    def test_speedtest_garbage_returns_requested_chunks(self):
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/speedtest/garbage?ckSize=2",
                     headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.getheader("Content-Disposition"),
                          "attachment; filename=random.dat")
        data = resp.read()
        self.assertEqual(len(data), 2 * app.DOWNLOAD_CHUNK)
        conn.close()

    def test_speedtest_garbage_defaults_to_4_chunks(self):
        # Matches the reference garbage.php: missing/invalid ckSize -> 4.
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/speedtest/garbage",
                     headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        self.assertEqual(int(resp.getheader("Content-Length")), 4 * app.DOWNLOAD_CHUNK)
        resp.read()
        conn.close()

    def test_speedtest_garbage_clamped_to_max(self):
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/speedtest/garbage?ckSize=99999",
                     headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        expected = app.MAX_TEST_MB * app.DOWNLOAD_CHUNK
        self.assertEqual(int(resp.getheader("Content-Length")), expected)
        data = resp.read()
        self.assertEqual(len(data), expected)
        conn.close()

    def test_speedtest_empty_upload_reads_and_discards_body(self):
        # The client only checks the HTTP status of an upload, never the
        # response body — see handle_speedtest_upload.
        session = self.login()
        payload = os.urandom(512 * 1024)
        conn = self.connect()
        conn.request(
            "POST",
            "/speedtest/empty",
            body=payload,
            headers={
                "Cookie": f"session={session}",
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(payload)),
            },
        )
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        resp.read()
        conn.close()

    def test_speedtest_empty_ping_returns_no_body(self):
        # Latency is measured by timing this round trip, so a body would make
        # it measure transfer time instead.
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/speedtest/empty", headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.read(), b"")
        conn.close()

    def test_speedtest_getip_returns_client_ip(self):
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/speedtest/getip", headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        result = json.loads(resp.read())
        self.assertEqual(result["processedString"], "127.0.0.1")
        self.assertEqual(result["rawIspInfo"], "")
        conn.close()

    def test_speedtest_empty_requires_login(self):
        conn = self.connect()
        conn.request("GET", "/speedtest/empty")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 302)
        self.assertEqual(resp.getheader("Location"), "/login")
        resp.read()
        conn.close()

    def test_speedtest_page_exposes_latency_widgets(self):
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/speedtest", headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        body = resp.read().decode()
        self.assertIn('id="latency-value"', body)
        self.assertIn('id="jitter-value"', body)
        self.assertIn('"pingSamples"', body)
        self.assertIn("/static/speedtest-ui.js", body)
        conn.close()

    def test_speedtest_worker_served_at_site_root(self):
        # speedtest.js resolves `new Worker("speedtest_worker.js")` relative
        # to the *page* URL (/speedtest), not to /static/ — see the
        # STATIC_FILES comment in app.py.
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/speedtest_worker.js", headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertIn(b"LibreSpeed", resp.read())
        conn.close()

    def test_vendored_static_urls_in_checkout_and_deployment(self):
        session = self.login()
        paths = {
            "/static/speedtest.js": "librespeed/speedtest.js",
            "/speedtest_worker.js": "librespeed/speedtest_worker.js",
            "/static/qrcode.js": "qrcode/qrcode.js",
            "/static/qrcode-utf8.js": "qrcode/qrcode-utf8.js",
        }
        repo_static = Path(__file__).resolve().parents[1] / "src/web/static"
        for url, relative in paths.items():
            self.assertEqual(app.STATIC_FILES[url][1], repo_static / "third_party" / relative)
            self.assertTrue(app.STATIC_FILES[url][1].is_file())
        for url, relative in paths.items():
            with self.subTest(layout="checkout", url=url):
                conn = self.connect()
                conn.request("GET", url, headers={"Cookie": f"session={session}"})
                resp = conn.getresponse()
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.read(), (repo_static / "third_party" / relative).read_bytes())
                conn.close()
        with tempfile.TemporaryDirectory() as directory:
            # A fresh process imports the copied app.py, so its BASE_DIR and
            # STATIC_FILES are computed from the deployment, not patched here.
            prefix = Path(directory)
            shutil.copy2(repo_static.parents[2] / "src" / "web" / "app.py", prefix / "app.py")
            for module in ("node_accounting", "node_inventory", "node_state", "module_manager", "console_port", "frp_control"):
                shutil.copy2(repo_static.parents[2] / "src" / "web" / f"{module}.py", prefix / f"{module}.py")
            shutil.copytree(repo_static.parents[2] / "src" / "web" / "features", prefix / "features")
            shutil.copytree(repo_static, prefix / "static")
            shutil.copytree(repo_static.parents[2] / "lang", prefix / "lang")
            check = '''import app, http.client, json, threading
from http.server import ThreadingHTTPServer
from pathlib import Path
paths = json.loads(__import__("os").environ["TEST_STATIC_PATHS"])
server = ThreadingHTTPServer(("127.0.0.1", 0), app.ConsoleHandler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    for url, relative in paths.items():
        expected = app.STATIC_DIR / "third_party" / relative
        assert app.STATIC_FILES[url][1] == expected, url
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port)
        conn.request("GET", url)
        response = conn.getresponse()
        assert response.status == 200, (url, response.status)
        assert response.read() == expected.read_bytes(), url
        conn.close()
finally:
    server.shutdown()
    server.server_close()
'''
            env = os.environ.copy()
            env.update(PYTHONPATH=str(prefix), VPSSRV_DATA_DIR=str(prefix / "data"),
                       VPSSRV_PASSWORD_FILE=str(prefix / "password"), VPSSRV_AUTH="0",
                       VPSSRV_TRACK_CONNECTIONS="0", TEST_STATIC_PATHS=json.dumps(paths))
            result = subprocess.run([sys.executable, "-c", check], cwd=prefix,
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_speedtest_requires_login(self):
        conn = self.connect()
        conn.request("GET", "/speedtest/garbage?ckSize=1")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 302)
        self.assertEqual(resp.getheader("Location"), "/login")
        resp.read()
        conn.close()

    # -- visitor log (deduplicated by IP) ---------------------------------

    def test_visitor_log_dedups_by_ip(self):
        # Same IP hitting multiple times must collapse to one row with a
        # rising hit count, not one row per request.
        app.log_visit("198.51.100.7", "GET", "/a", 200)
        app.log_visit("198.51.100.7", "GET", "/b", 200)
        app.log_visit("198.51.100.7", "POST", "/c", 302)
        rows = [r for r in app.recent_visitors() if r["ip"] == "198.51.100.7"]
        self.assertEqual(len(rows), 1)
        self.assertGreaterEqual(rows[0]["hits"], 3)
        self.assertEqual(rows[0]["last_path"], "/c")
        self.assertEqual(rows[0]["last_status"], 302)

    def test_disabling_visitors_stops_http_and_tcp_recording(self):
        ip = "192.0.2.211"
        with patch.object(app, "module_feature_enabled", return_value=False):
            app.log_visit(ip, "GET", "/hidden", 200)
            app.record_connections({ip: {"ports": {443}, "inbound": True}})
        self.assertFalse(any(row["ip"] == ip for row in app.recent_visitors()))

    def test_visitor_log_trims_to_max_unique_ips(self):
        for i in range(app.MAX_VISITOR_ROWS + 5):
            app.log_visit(f"10.1.{i // 256}.{i % 256}", "GET", "/probe", 200)
        rows = app.recent_visitors(limit=app.MAX_VISITOR_ROWS + 50)
        self.assertLessEqual(len(rows), app.MAX_VISITOR_ROWS)

    def test_visitor_page_shows_ip(self):
        # Record a known IP synchronously right before rendering, so this does
        # not depend on the handler's async visit-logging or on surviving a
        # trim triggered by another test's bulk inserts.
        app.log_visit("192.0.2.55", "GET", "/probe", 200)
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/visitors", headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        body = resp.read().decode()
        self.assertIn("192.0.2.55", body)
        conn.close()


class ChangelogAndVersionTest(unittest.TestCase):
    """The /changelog page and the version badge in the nav bar."""

    @classmethod
    def setUpClass(cls):
        # Own fixture: unittest orders classes alphabetically, so this one runs
        # before ConsoleTest and cannot borrow its server.
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.ConsoleHandler)
        cls.server.daemon_threads = True
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def connect(self):
        return http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)

    def login(self):
        conn = self.connect()
        conn.request(
            "POST",
            "/login",
            body=f"password={app.ADMIN_PASSWORD}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp = conn.getresponse()
        jar = SimpleCookie()
        jar.load(resp.getheader("Set-Cookie"))
        resp.read()
        conn.close()
        return jar["session"].value

    def test_version_badge_rendered_in_nav(self):
        conn = self.connect()
        conn.request("GET", "/login")
        body = conn.getresponse().read().decode()
        self.assertIn(app.VERSION_LABEL, body)
        conn.close()

    def require_log_files(self, *paths):
        if any(not Path(path).is_file() for path in paths):
            self.skipTest("LOG translations are omitted from the code-only test checkout")

    def changelog_sentinel(self, path):
        """A distinctive phrase from the file that should have been rendered.

        Taken from the LOG release section at test time so changes to the
        release prose do not invalidate a page-rendering test.
        """
        section = app.changelog_section(Path(path).read_text(encoding="utf-8"))
        self.assertIsNotNone(section, f"no changelog section in {path}")
        release = re.split(r"^### v[^\n]*$", section, maxsplit=1, flags=re.M)
        self.assertEqual(len(release), 2, f"no version section in {path}")
        for line in release[1].splitlines():
            s = line.strip().removeprefix("- ")
            if not s or s.startswith(("#", ">", "<", "|")):
                continue
            # Inline code becomes HTML; use only a long prose span outside it.
            for prose in re.split(r"`[^`]*`", s):
                prose = prose.strip()
                if len(prose) >= 18:
                    return prose[:18]
        self.fail(f"no prose under the first version heading in {path}")

    def test_maintainer_comments_are_not_rendered(self):
        # An HTML comment in a release section must not become visible prose.
        session = self.login()
        for lang in ("en", "zh_cn", "zh_tw"):
            with self.subTest(lang=lang):
                conn = self.connect()
                conn.request("GET", f"/changelog?lang={lang}",
                             headers={"Cookie": f"session={session}"})
                body = conn.getresponse().read().decode()
                conn.close()
                # Assert on text that only ever appears inside the comment.
                # Checking for an escaped `<!--` looked stronger and was
                # wrong: the v1.0.1 release note describes this very bug and
                # quotes the delimiters, so the page legitimately contains
                # them and the test flagged its own changelog entry.
                self.assertNotIn("release-preflight.sh", body,
                                 "the comment's contents leaked into the page")
                self.assertNotIn("locates the current section", body)

    def test_changelog_page_renders_current_version_section(self):
        self.require_log_files("doc/en/CHANGELOG.md")
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/changelog", headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        body = resp.read().decode()
        self.assertIn(app.VERSION_LABEL, body)
        self.assertIn("<h2>", body, "changelog headings were not rendered")
        conn.close()

    def test_changelog_follows_language_toggle(self):
        self.require_log_files("doc/en/CHANGELOG.md", "doc/CHANGELOG.md")
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/changelog?lang=zh_cn", headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        body = resp.read().decode()
        conn.close()
        self.assertIn(self.changelog_sentinel("doc/CHANGELOG.md"), body)
        self.assertNotIn(self.changelog_sentinel("doc/en/CHANGELOG.md"), body)
        self.assertNotIn(app.STRINGS["zh_cn"]["changelog_fallback"], body)

    def test_changelog_traditional_chinese(self):
        self.require_log_files("doc/en/CHANGELOG.md", "doc/zh-TW/CHANGELOG.md")
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/changelog?lang=zh_tw", headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        body = resp.read().decode()
        conn.close()
        self.assertIn("<h2>", body, "zh_tw changelog headings were not rendered")
        self.assertIn(self.changelog_sentinel("doc/zh-TW/CHANGELOG.md"), body)
        self.assertNotIn(self.changelog_sentinel("doc/en/CHANGELOG.md"), body)
        self.assertNotIn(app.STRINGS["zh_tw"]["changelog_fallback"], body)

    def test_changelog_fallback_notice_when_translation_missing(self):
        self.require_log_files("doc/en/CHANGELOG.md", "doc/CHANGELOG.md", "doc/zh-TW/CHANGELOG.md")
        session = self.login()
        for lang in ("zh_cn", "zh_tw"):
            with self.subTest(lang=lang):
                original = app.CHANGELOG_PATHS[lang]
                app.CHANGELOG_PATHS[lang] = Path(f"/nonexistent/LOG_{lang}.md")
                try:
                    conn = self.connect()
                    conn.request("GET", f"/changelog?lang={lang}",
                                 headers={"Cookie": f"session={session}"})
                    resp = conn.getresponse()
                    body = resp.read().decode()
                    conn.close()
                    self.assertIn(self.changelog_sentinel("doc/en/CHANGELOG.md"), body)
                    self.assertNotIn(self.changelog_sentinel("doc/CHANGELOG.md" if lang == "zh_cn" else "doc/zh-TW/CHANGELOG.md"), body)
                    self.assertIn(app.STRINGS[lang]["changelog_fallback"], body)
                finally:
                    app.CHANGELOG_PATHS[lang] = original

    def test_changelog_missing_section_does_not_show_other_log_sections(self):
        session = self.login()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "LOG.md"
            path.write_text("## Bugs\n- private detail\n## Decisions\n- no release\n")
            original = app.CHANGELOG_PATHS["zh_cn"]
            app.CHANGELOG_PATHS["zh_cn"] = path
            try:
                conn = self.connect()
                conn.request("GET", "/changelog?lang=zh_cn",
                             headers={"Cookie": f"session={session}"})
                body = conn.getresponse().read().decode()
                conn.close()
                self.assertIn(app.STRINGS["zh_cn"]["changelog_missing"], body)
                self.assertNotIn("private detail", body)
                self.assertNotIn("no release", body)
            finally:
                app.CHANGELOG_PATHS["zh_cn"] = original

    def test_changelog_english_by_default(self):
        self.require_log_files("doc/en/CHANGELOG.md", "doc/CHANGELOG.md", "doc/zh-TW/CHANGELOG.md")
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/changelog?lang=en", headers={"Cookie": f"session={session}"})
        body = conn.getresponse().read().decode()
        conn.close()
        self.assertIn(self.changelog_sentinel("doc/en/CHANGELOG.md"), body)
        self.assertNotIn(self.changelog_sentinel("doc/CHANGELOG.md"), body)
        self.assertNotIn(self.changelog_sentinel("doc/zh-TW/CHANGELOG.md"), body)

    def test_changelog_requires_login(self):
        conn = self.connect()
        conn.request("GET", "/changelog")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 302)
        self.assertEqual(resp.getheader("Location"), "/login?next=changelog")
        resp.read()
        conn.close()

    def test_login_version_link_returns_to_changelog(self):
        conn = self.connect()
        conn.request("GET", "/login?next=changelog")
        page = conn.getresponse().read().decode()
        conn.close()
        self.assertIn('name="next" value="changelog"', page)
        self.assertIn('href="/changelog"', page)

        conn = self.connect()
        conn.request("POST", "/login",
                     body=urlencode({"password": app.ADMIN_PASSWORD, "next": "changelog"}),
                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        response = conn.getresponse()
        self.assertEqual(response.status, 302)
        self.assertEqual(response.getheader("Location"), "/changelog")
        response.read()
        conn.close()

    def test_development_changelog_shows_formal_notes_without_old_draft(self):
        self.require_log_files("doc/CHANGELOG.md")
        session = self.login()
        with patch.object(app, "VERSION", "dev-test123"), patch.object(app, "VERSION_LABEL", "dev-test123"):
            conn = self.connect()
            conn.request("GET", "/changelog?lang=zh_cn", headers={"Cookie": f"session={session}"})
            response = conn.getresponse()
            body = response.read().decode()
            conn.close()
        self.assertEqual(response.status, 200)
        self.assertNotIn("<h2>dev-test123</h2>", body)
        self.assertIn(self.changelog_sentinel("doc/CHANGELOG.md"), body)
        self.assertNotIn("Test deployment (2026-09-28)", body)

    def test_test_candidate_shows_its_identifier_without_stale_notes(self):
        self.require_log_files("doc/en/CHANGELOG.md")
        self.assertEqual(app.display_version("test-95ca649"), "test-95ca649")
        self.assertEqual(app.display_version("3.0.0"), "v3.0.0")
        session = self.login()
        with patch.object(app, "VERSION", "test-95ca649"), patch.object(app, "VERSION_LABEL", "test-95ca649"):
            conn = self.connect()
            conn.request("GET", "/changelog", headers={"Cookie": f"session={session}"})
            response = conn.getresponse()
            body = response.read().decode()
            conn.close()
        self.assertEqual(response.status, 200)
        self.assertIn("test-95ca649", body)
        self.assertNotIn("<h2>test-95ca649</h2>", body)
        self.assertIn(self.changelog_sentinel("doc/en/CHANGELOG.md"), body)
        self.assertIn("v5.0.0", body)

    def test_changelog_markdown_is_escaped_not_injected(self):
        # LOG.md is author-controlled, but rendering must still escape tags.
        out = app.render_changelog(
            "### v1.0.0\n- oops <script>alert(1)</script> and `code`"
        )
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertIn("<code>code</code>", out)

    def test_changelog_renders_headings_and_bullets(self):
        out = app.render_changelog("### v1.0.0\n\n#### Added\n- thing **bold**\n")
        self.assertIn("<h2>v1.0.0</h2>", out)
        self.assertIn("<h3>Added</h3>", out)
        self.assertIn("<li>thing <strong>bold</strong>", out)
        # Tags must balance, or the page layout breaks.
        self.assertEqual(out.count("<li>"), out.count("</li>"))
        self.assertEqual(out.count("<ul>"), out.count("</ul>"))

    def test_changelog_skips_maintainer_preamble(self):
        out = app.render_changelog(
            "Notes for maintainers only.\n\n### v1.0.0\n- real change\n"
        )
        self.assertNotIn("maintainers", out)
        self.assertIn("real change", out)

    def test_changelog_section_excludes_other_modules_and_escapes_html(self):
        source = "## Bugs\n- secret <script>x</script>\n## Changelog\n\n### v1.2.0 — 2026-09-22\n#### Fixed\n- safe <script>x</script>\n## Decisions\n- private detail\n"
        section = app.changelog_section(source)
        self.assertIsNotNone(section)
        out = app.render_changelog(section)
        self.assertIn("<h2>v1.2.0", out)
        self.assertIn("<h3>Fixed</h3>", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertNotIn("<script>", out)
        self.assertNotIn("secret", out)
        self.assertNotIn("private detail", out)

    def test_changelog_comment_is_not_rendered(self):
        out = app.render_changelog("### v1.2.0\n#### Fixed\n- visible\n<!-- private release-preflight.sh -->\n")
        self.assertIn("visible", out)
        self.assertNotIn("release-preflight.sh", out)

    def test_changelog_section_missing_or_empty(self):
        self.assertIsNone(app.changelog_section("## Bugs\n- not release notes\n"))
        self.assertIsNone(app.changelog_section("## Changelog\n\n## Decisions\n- no release\n"))
        self.assertIsNone(app.changelog_section("## Changelog\nnotes without a version\n"))

    def test_installer_copies_current_changelog_and_not_historical_log_translations(self):
        installer = Path("deploy/install.sh").read_text()
        items = re.search(r'^    local doc_items="([^\"]+)"', installer, re.MULTILINE)
        self.assertIsNotNone(items)
        self.assertIn("doc/LOG.md", items.group(1))
        self.assertIn("doc/CHANGELOG.md", items.group(1))
        self.assertIn("doc/zh-TW/CHANGELOG.md", items.group(1))
        self.assertNotIn("doc/zh-TW/LOG.md", items.group(1))


class ConnectionTrackingTest(unittest.TestCase):
    """Reading the kernel TCP table — the source that catches SSH etc."""

    def test_decodes_little_endian_ipv4_address(self):
        # /proc/net/tcp stores addresses as little-endian words.
        self.assertEqual(app._decode_addr("0100007F:1F90"), ("127.0.0.1", 8080))
        self.assertEqual(app._decode_addr("00000000:0016"), ("0.0.0.0", 22))

    def test_decodes_ipv4_mapped_ipv6_to_familiar_form(self):
        # ::ffff:127.0.0.1 is the same host as 127.0.0.1; don't show two rows.
        ip, port = app._decode_addr("0000000000000000FFFF00000100007F:0050")
        self.assertEqual((ip, port), ("127.0.0.1", 80))

    def test_scope_classification(self):
        self.assertEqual(app.ip_scope("127.0.0.1"), "loopback")
        self.assertEqual(app.ip_scope("::1"), "loopback")
        self.assertEqual(app.ip_scope("192.168.1.5"), "private")
        self.assertEqual(app.ip_scope("10.0.0.9"), "private")
        self.assertEqual(app.ip_scope("8.8.8.8"), "public")
        self.assertEqual(app.ip_scope("not-an-ip"), "public")

    def test_records_every_peer_and_labels_direction(self):
        # Every connected device is recorded whatever the port; direction
        # distinguishes "they connected to us" from "we connected out".
        listening_line = "  0: 00000000:0016 00000000:0000 0A 0 0 0"
        inbound_line = "  1: 0100007F:0016 0200007F:C001 01 0 0 0"
        # 08080808 is 8.8.8.8 once byte-swapped out of little-endian order.
        outbound_line = "  2: 0100007F:C002 08080808:01BB 01 0 0 0"
        fake = [listening_line, inbound_line, outbound_line]

        original = app._read_proc_net
        app._read_proc_net = lambda path: fake if path.endswith("tcp") else []
        try:
            observed = app.observed_connections()
        finally:
            app._read_proc_net = original

        self.assertIn("127.0.0.2", observed, "inbound connection to :22 was missed")
        self.assertTrue(observed["127.0.0.2"]["inbound"])
        self.assertEqual(observed["127.0.0.2"]["ports"], {22})

        # The outbound peer is still reported (nothing is dropped by port),
        # but flagged as not inbound so it isn't presented as a visitor.
        self.assertIn("8.8.8.8", observed, "peer on a non-listening port was dropped")
        self.assertFalse(observed["8.8.8.8"]["inbound"])
        self.assertEqual(observed["8.8.8.8"]["ports"], {443})

    def test_records_half_open_and_closing_connections(self):
        # SYN_RECV is what a SYN scan leaves behind; TIME_WAIT is a connection
        # that already finished. Both are real peers and must be recorded, or
        # short-lived connections vanish between polls.
        lines = [
            "  0: 00000000:0016 00000000:0000 0A 0 0 0",  # LISTEN :22
            "  1: 0100007F:0016 0200007F:C001 03 0 0 0",  # SYN_RECV  (half-open)
            "  2: 0100007F:0016 0300007F:C002 06 0 0 0",  # TIME_WAIT (closed)
            "  3: 0100007F:0016 0400007F:C003 08 0 0 0",  # CLOSE_WAIT
        ]
        original = app._read_proc_net
        app._read_proc_net = lambda path: lines if path.endswith("tcp") else []
        try:
            observed = app.observed_connections()
        finally:
            app._read_proc_net = original

        for ip in ("127.0.0.2", "127.0.0.3", "127.0.0.4"):
            self.assertIn(ip, observed, f"{ip} in a non-ESTABLISHED state was dropped")
            self.assertTrue(observed[ip]["inbound"])

    def test_ignores_our_own_pending_and_dead_sockets(self):
        lines = [
            "  0: 0100007F:C001 08080808:01BB 02 0 0 0",  # SYN_SENT: our attempt
            "  1: 0100007F:C002 08080404:01BB 07 0 0 0",  # CLOSE: dead socket
        ]
        original = app._read_proc_net
        app._read_proc_net = lambda path: lines if path.endswith("tcp") else []
        try:
            observed = app.observed_connections()
        finally:
            app._read_proc_net = original
        self.assertEqual(observed, {}, "a pending or dead socket was logged as a peer")

    def test_inbound_wins_when_a_peer_is_both(self):
        app.record_connections({"198.51.100.5": {"ports": {9000}, "inbound": False}})
        app.record_connections({"198.51.100.5": {"ports": {22}, "inbound": True}})
        app.record_connections({"198.51.100.5": {"ports": {9000}, "inbound": False}})
        row = next(r for r in app.recent_visitors() if r["ip"] == "198.51.100.5")
        self.assertEqual(row["direction"], "in", "a known visitor was downgraded to outbound")

    def test_malformed_rows_do_not_break_the_poller(self):
        original = app._read_proc_net
        app._read_proc_net = lambda path: (
            ["garbage", "  1: ZZZZ:ZZZZ QQQQ:QQQQ 01 0 0 0"] if path.endswith("tcp") else []
        )
        try:
            self.assertEqual(app.observed_connections(), {})
        finally:
            app._read_proc_net = original

    def test_record_connections_upserts_and_keeps_http_details(self):
        app.log_visit("203.0.113.9", "GET", "/dash", 200)
        app.record_connections({"203.0.113.9": {"ports": {22, 443}, "inbound": True}})
        row = next(r for r in app.recent_visitors() if r["ip"] == "203.0.113.9")
        # The HTTP detail survives, and the connection observation is added.
        self.assertEqual(row["last_path"], "/dash")
        self.assertGreaterEqual(row["hits"], 1)
        self.assertGreaterEqual(row["conn_seen"], 1)
        self.assertEqual(row["ports"], "22,443")
        # 203.0.113.0/24 is RFC 5737 documentation space, which Python's
        # ipaddress (correctly) reports as not-globally-routable.
        self.assertEqual(row["scope"], "private")

    def test_connection_only_ip_has_no_http_details(self):
        app.record_connections({"198.51.100.77": {"ports": {22}, "inbound": True}})
        row = next(r for r in app.recent_visitors() if r["ip"] == "198.51.100.77")
        self.assertEqual(row["hits"], 0)
        self.assertEqual(row["last_path"], "")
        self.assertEqual(row["ports"], "22")


class TlsTest(unittest.TestCase):
    """Certificate generation and the plain-HTTP -> HTTPS redirect."""

    def test_generates_self_signed_cert(self):
        cert, key = app.ensure_tls_files()
        self.assertTrue(cert.exists(), "certificate was not created")
        self.assertTrue(key.exists(), "private key was not created")
        self.assertIn(b"BEGIN CERTIFICATE", cert.read_bytes())
        # The private key must not be world-readable.
        self.assertEqual(oct(key.stat().st_mode & 0o777), "0o600")

    def test_reuses_existing_cert(self):
        cert, key = app.ensure_tls_files()
        first = cert.read_bytes()
        cert2, _ = app.ensure_tls_files()
        self.assertEqual(cert2, cert)
        self.assertEqual(cert2.read_bytes(), first, "certificate was regenerated")

    def test_https_serves_the_console(self):
        # There is deliberately no HTTP-to-HTTPS redirect listener left to
        # test: port 80 now belongs to the public reachability page, and
        # redirecting it would destroy the very thing that page measures —
        # whether port 80 itself answers. See doc/LOG.md#decisions (2026-09-12).
        import ssl as _ssl

        context = _ssl.SSLContext(_ssl.PROTOCOL_TLS_SERVER)
        cert, key = app.ensure_tls_files()
        context.load_cert_chain(certfile=str(cert), keyfile=str(key))

        https = ThreadingHTTPServer(("127.0.0.1", 0), app.ConsoleHandler)
        https.daemon_threads = True
        https.socket = context.wrap_socket(https.socket, server_side=True)
        https_port = https.server_address[1]
        threading.Thread(target=https.serve_forever, daemon=True).start()

        try:
            # Self-signed, so verification is deliberately off.
            client_ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
            client_ctx.check_hostname = False
            client_ctx.verify_mode = _ssl.CERT_NONE
            conn = http.client.HTTPSConnection(
                "127.0.0.1", https_port, context=client_ctx, timeout=10
            )
            conn.request("GET", "/")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 302)  # unauthenticated -> /login
            resp.read()
            conn.close()
        finally:
            https.shutdown()
            https.server_close()


class PortTest(unittest.TestCase):
    """ensure_console_port(): random-once-and-persist, explicit VPSSRV_CONSOLE_PORT wins."""

    def setUp(self):
        self.port_file = Path(TEST_DATA_DIR) / f"port-test-{id(self)}.txt"
        self.port_file.unlink(missing_ok=True)
        self.original_port_file = app.CONSOLE_PORT_FILE
        app.CONSOLE_PORT_FILE = self.port_file

    def tearDown(self):
        app.CONSOLE_PORT_FILE = self.original_port_file
        self.port_file.unlink(missing_ok=True)
        os.environ.pop("VPSSRV_CONSOLE_PORT", None)

    def test_generates_and_persists_a_random_port(self):
        first = app.ensure_console_port()
        second = app.ensure_console_port()
        self.assertEqual(first, second, "port must not change across restarts")
        self.assertTrue(20000 <= first <= 59999)
        self.assertEqual(int(self.port_file.read_text().strip()), first)

    def test_literal_zero_means_auto_not_port_zero(self):
        # .env.example ships VPSSRV_CONSOLE_PORT=0 and three documents call 0
        # "generate one and remember it". The code used to read "0" as truthy
        # and bind port 0, which the kernel answers with a different ephemeral
        # port on every restart, written to no file — a console that moved
        # each time the service came back, for anyone who copied the example.
        os.environ["VPSSRV_CONSOLE_PORT"] = "0"
        try:
            port = app.ensure_console_port()
            self.assertNotEqual(port, 0)
            self.assertGreaterEqual(port, 20000)
            self.assertTrue(self.port_file.exists(), "the chosen port must be remembered")
            self.assertEqual(app.ensure_console_port(), port, "and must not move")
        finally:
            os.environ.pop("VPSSRV_CONSOLE_PORT", None)

    def test_explicit_env_port_wins_and_is_not_persisted(self):
        os.environ["VPSSRV_CONSOLE_PORT"] = "54321"
        self.assertEqual(app.ensure_console_port(), 54321)
        self.assertFalse(self.port_file.exists())


class AuthDisabledTest(unittest.TestCase):
    """VPSSRV_AUTH=0 (install-time opt-out) bypasses the login gate."""

    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.ConsoleHandler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        app.AUTH_ENABLED = False

    def tearDown(self):
        app.AUTH_ENABLED = True
        self.server.shutdown()
        self.server.server_close()

    def test_root_reachable_without_a_session(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        resp.read()
        conn.close()

    def test_speedtest_endpoints_reachable_without_a_session(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/speedtest/empty")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        resp.read()
        conn.close()

    def test_login_and_logout_redirect_to_dashboard(self):
        # There is no session to start or end, so a login form and a logout
        # link are both dead ends — visiting either goes back to the app.
        for path in ("/login", "/logout"):
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
            conn.request("GET", path)
            resp = conn.getresponse()
            self.assertEqual(resp.status, 302, path)
            self.assertEqual(resp.getheader("Location"), "/", path)
            resp.read()
            conn.close()

    def test_frps_token_not_exposed_when_auth_disabled(self):
        config = Path(TEST_DATA_DIR) / 'frps-off.toml'
        config.write_text('bindPort = 7000\nauth.token = "auth-off-frps-secret"\n')
        with patch.object(app, 'FRPS_CONFIG', config):
            for path in ('/', '/frps', '/frp', '/frp/client/config?name=demo'):
                conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
                conn.request('GET', path)
                resp = conn.getresponse()
                self.assertNotIn(b'auth-off-frps-secret', resp.read())
                conn.close()

    def test_nav_hides_the_logout_link(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/")
        body = conn.getresponse().read().decode()
        conn.close()
        self.assertNotIn('href="/logout"', body)
        # The rest of the nav is still there.
        self.assertIn('href="/speedtest"', body)


class StartupDefaultsTest(unittest.TestCase):
    """Defaults are read from the environment at import time, so they can only
    be checked in a fresh interpreter. All three assertions below cover
    operator-reported regressions (2026-08-25).
    """

    def _probe(self, expression, extra_env=None):
        env = dict(os.environ)
        for key in ("VPSSRV_CONSOLE_TLS", "VPSSRV_CONSOLE_PORT", "VPSSRV_DEFAULT_LANG"):
            env.pop(key, None)
        tmp = tempfile.mkdtemp(prefix="vpssrv-probe-")
        env["VPSSRV_DATA_DIR"] = tmp
        env["VPSSRV_PASSWORD_FILE"] = str(Path(tmp) / "admin_password.txt")
        env["VPSSRV_CONSOLE_PORT_FILE"] = str(Path(tmp) / "console_port.txt")
        env["VPSSRV_CERT_DIR"] = str(Path(tmp) / "certs")
        env.update(extra_env or {})
        repo_root = str(Path(__file__).resolve().parent.parent)
        try:
            result = subprocess.run(
                [sys.executable, "-c", f"from src.web import app; print({expression})"],
                cwd=repo_root, env=env, capture_output=True, text=True, timeout=60,
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_tls_is_off_by_default(self):
        # Plain HTTP by default: the only cert this app can make on its own is
        # self-signed, which just trains operators to click through warnings.
        self.assertEqual(self._probe("app.CONSOLE_TLS"), "False")

    def test_tls_can_still_be_turned_on(self):
        self.assertEqual(self._probe("app.CONSOLE_TLS", {"VPSSRV_CONSOLE_TLS": "1"}), "True")

    def test_explicit_port_is_honoured_verbatim(self):
        # Regression: an operator-chosen port was being ignored in favour of a
        # random one (the cause was install.sh's prompt, but pin the app side).
        self.assertEqual(self._probe("app.CONSOLE_PORT", {"VPSSRV_CONSOLE_PORT": "51234"}), "51234")


class SignalShutdownTest(unittest.TestCase):
    """main() must exit promptly on SIGTERM once it is actually serving —
    the real process, not just the ConsoleHandler class other tests drive
    directly, since this is exercising main()'s own try/finally.
    """

    def test_sigterm_after_startup_exits_promptly(self):
        tmp = tempfile.mkdtemp(prefix="vpssrv-signal-test-")
        port_file = Path(tmp) / "console_port.txt"
        env = dict(os.environ)
        env.update({
            "VPSSRV_DATA_DIR": tmp,
            "VPSSRV_HOST": "127.0.0.1",
            "VPSSRV_PUBLIC_ENABLE": "0",
            "VPSSRV_IPERF_ENABLE": "0",
            "VPSSRV_PORTFWD_ENABLE": "0",
            "VPSSRV_CONSOLE_PORT": "0",
            "VPSSRV_CONSOLE_PORT_FILE": str(port_file),
            "VPSSRV_PASSWORD_FILE": str(Path(tmp) / "admin_password.txt"),
            "VPSSRV_CERT_DIR": str(Path(tmp) / "certs"),
            "VPSSRV_TRACK_CONNECTIONS": "0",
        })
        repo_root = str(Path(__file__).resolve().parent.parent)
        proc = subprocess.Popen(
            [sys.executable, "src/web/app.py"],
            cwd=repo_root, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            port = None
            deadline = time.time() + 10
            while time.time() < deadline:
                if proc.poll() is not None:
                    self.fail("server exited before it started listening")
                if port_file.exists():
                    try:
                        port = int(port_file.read_text().strip())
                        break
                    except ValueError:
                        pass
                time.sleep(0.1)
            self.assertIsNotNone(port, "console never wrote its port file")

            for _ in range(50):
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                self.fail("console port never accepted a connection")

            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                self.fail("process did not exit within 5s of SIGTERM")
            self.assertEqual(proc.returncode, 0)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            shutil.rmtree(tmp, ignore_errors=True)


class LoginRateLimitTest(unittest.TestCase):
    """LoginRateLimiter in isolation — mocked into app.LOGIN_LIMITER so
    other test classes' logins (all from 127.0.0.1) never share a counter
    with these deliberately-triggered failures.
    """

    def setUp(self):
        self.original_limiter = app.LOGIN_LIMITER
        app.LOGIN_LIMITER = app.LoginRateLimiter(
            max_attempts=3, window_seconds=60, lockout_seconds=2
        )

    def tearDown(self):
        app.LOGIN_LIMITER = self.original_limiter

    def test_allows_attempts_under_the_limit(self):
        limiter = app.LOGIN_LIMITER
        limiter.record_failure("1.2.3.4")
        limiter.record_failure("1.2.3.4")
        allowed, retry_after = limiter.check("1.2.3.4")
        self.assertTrue(allowed)
        self.assertEqual(retry_after, 0)

    def test_locks_out_after_max_attempts(self):
        limiter = app.LOGIN_LIMITER
        for _ in range(3):
            limiter.record_failure("1.2.3.4")
        allowed, retry_after = limiter.check("1.2.3.4")
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 0)

    def test_success_clears_the_lockout(self):
        limiter = app.LOGIN_LIMITER
        for _ in range(3):
            limiter.record_failure("1.2.3.4")
        self.assertFalse(limiter.check("1.2.3.4")[0])
        limiter.record_success("1.2.3.4")
        self.assertTrue(limiter.check("1.2.3.4")[0])

    def test_lockout_expires_on_its_own(self):
        limiter = app.LOGIN_LIMITER
        for _ in range(3):
            limiter.record_failure("1.2.3.4")
        self.assertFalse(limiter.check("1.2.3.4")[0])
        time.sleep(2.1)
        self.assertTrue(limiter.check("1.2.3.4")[0])

    def test_different_ips_tracked_independently(self):
        limiter = app.LOGIN_LIMITER
        for _ in range(3):
            limiter.record_failure("1.2.3.4")
        self.assertFalse(limiter.check("1.2.3.4")[0])
        self.assertTrue(limiter.check("5.6.7.8")[0])

    def test_failures_outside_the_window_do_not_count(self):
        limiter = app.LoginRateLimiter(max_attempts=3, window_seconds=0.1, lockout_seconds=5)
        limiter.record_failure("1.2.3.4")
        time.sleep(0.2)
        limiter.record_failure("1.2.3.4")
        limiter.record_failure("1.2.3.4")
        # The first failure aged out of the window, so only 2 of 3 still count.
        self.assertTrue(limiter.check("1.2.3.4")[0])


class LoginRateLimitHttpTest(unittest.TestCase):
    """The real /login route, driven over HTTP, actually returns 429 once
    locked out — not just that the limiter object itself works.
    """

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.ConsoleHandler)
        cls.server.daemon_threads = True
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.original_limiter = app.LOGIN_LIMITER
        app.LOGIN_LIMITER = app.LoginRateLimiter(
            max_attempts=2, window_seconds=60, lockout_seconds=30
        )

    def tearDown(self):
        app.LOGIN_LIMITER = self.original_limiter

    def attempt(self, password):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request(
            "POST", "/login", body=f"password={password}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp = conn.getresponse()
        resp.read()
        conn.close()
        return resp.status

    def test_locked_out_after_configured_attempts(self):
        self.assertEqual(self.attempt("wrong-1"), 401)
        self.assertEqual(self.attempt("wrong-2"), 401)
        # Third attempt, even with the correct password, is refused outright.
        self.assertEqual(self.attempt(app.ADMIN_PASSWORD), 429)


class ProbePageTest(unittest.TestCase):
    """The public page on 80/443: what it shows, and what it refuses to be."""

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.ProbeHandler)
        cls.server.daemon_threads = True
        cls.server.is_tls = False
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def connect(self):
        return http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)

    def get(self, path, headers=None):
        conn = self.connect()
        conn.request("GET", path, headers=headers or {})
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()
        return resp, body

    def test_lucky_route_is_absent_from_public_listener(self):
        config = Path(TEST_DATA_DIR) / 'public-lucky.json'
        config.write_text(json.dumps({'BaseConfigure': {'AdminWebListenPort': 16601,
            'AdminAccount': 'admin', 'AdminPassword': 'public-lucky-secret'}}))
        with patch.object(app, 'LUCKY_CONFIG', config):
            for path in ('/', '/lucky'):
                response, body = self.get(path)
                self.assertNotIn('public-lucky-secret', body)
                if path == '/lucky':
                    self.assertEqual(response.status, 404)

    def test_frps_route_is_absent_from_public_listener(self):
        config = Path(TEST_DATA_DIR) / 'frps-public.toml'
        config.write_text('bindPort = 7000\nauth.token = "public-frps-secret"\n')
        with patch.object(app, 'FRPS_CONFIG', config):
            for path in ('/', '/frps', '/frp', '/frp/client/config?name=demo'):
                response, body = self.get(path)
                self.assertNotIn('public-frps-secret', body)
                if path != '/':
                    self.assertEqual(response.status, 404)

    def test_root_reports_reachability_without_any_session(self):
        resp, body = self.get("/")
        self.assertEqual(resp.status, 200)
        self.assertIn("Reachable", body)
        self.assertIn("127.0.0.1", body, "the caller's own address is the point")
        self.assertIn(f":{self.port}", body, "the arrival port must be the real one")

    def test_server_header_names_no_interpreter_version(self):
        # BaseHTTPRequestHandler appends sys_version to server_version, so
        # setting server_version alone still answered
        # "Server: vps-server Python/3.10.12" — a precise interpreter version,
        # to anyone who runs curl -I against the IP, from the one page that
        # promises to disclose nothing about the host.
        resp, _ = self.get("/")
        server = resp.getheader("Server") or ""
        self.assertEqual(server, "vps-server")
        self.assertNotIn("Python", server)

    def test_no_console_route_exists_here(self):
        # The security property this whole class exists for. These must 404
        # because ProbeHandler has no such routes — not because a check
        # rejected them. See doc/LOG.md#decisions (2026-09-12).
        for path in ("/login", "/logout", "/visitors", "/speedtest",
                     "/speedtest/garbage", "/speedtest/empty", "/speedtest/getip",
                     "/changelog", "/iperf", "/iperf/open", "/iperf/close",
                     "/anytls", "/anytls/reset", "/proxy", "/proxy/reset",
                     "/static/style.css", "/static/copy.js",
                     "/speedtest_worker.js"):
            with self.subTest(path=path):
                resp, _ = self.get(path)
                self.assertEqual(resp.status, 404, f"{path} answered on the public port")

    def test_sets_no_cookie_and_leaks_no_server_version(self):
        resp, _ = self.get("/")
        self.assertIsNone(resp.getheader("Set-Cookie"))
        self.assertNotIn(app.VERSION, resp.getheader("Server") or "")

    def test_head_is_supported_and_has_no_body(self):
        conn = self.connect()
        conn.request("HEAD", "/")
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        self.assertEqual(resp.status, 200)
        self.assertEqual(body, b"")
        self.assertNotEqual(resp.getheader("Content-Length"), "0")

    def test_post_is_not_implemented(self):
        conn = self.connect()
        conn.request("POST", "/", body="x=1")
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 501)

    def test_accept_language_is_honoured(self):
        _, body = self.get("/", {"Accept-Language": "zh-TW,zh;q=0.9"})
        self.assertIn("可以存取", body)
        _, body = self.get("/", {"Accept-Language": "zh-CN,zh;q=0.9"})
        self.assertIn("可以访问", body)


@unittest.skipUnless(shutil.which("iperf3"), "iperf3 is not installed")
class IperfWindowTest(unittest.TestCase):
    """The window opens, self-closes, and never leaves a process behind."""

    def setUp(self):
        # Never touch the host firewall from a test. The real call is
        # exercised by hand; here it would add an ACCEPT rule to whatever
        # machine happens to run the suite.
        self.original_firewall = app.firewall_port
        self.calls = []
        app.firewall_port = lambda port, opening: self.calls.append((port, opening)) or True
        self.window = app.IperfWindow(port=15299, max_minutes=5)

    def tearDown(self):
        self.window.close()
        app.firewall_port = self.original_firewall

    def test_starts_closed(self):
        is_open, remaining = self.window.state()
        self.assertFalse(is_open)
        self.assertEqual(remaining, 0)

    def test_open_then_close_leaves_no_process(self):
        ok, key = self.window.open(1)
        self.assertTrue(ok, key)
        self.assertEqual(key, "iperf_opened")
        is_open, remaining = self.window.state()
        self.assertTrue(is_open)
        self.assertGreater(remaining, 0)
        proc = self.window._proc
        self.assertIsNone(proc.poll(), "iperf3 should still be running")

        self.window.close()
        self.assertFalse(self.window.state()[0])
        self.assertIsNotNone(proc.poll(), "iperf3 was not terminated")
        self.assertEqual(self.calls, [(15299, True), (15299, False)],
                         "the firewall rule must be withdrawn as well")

    def test_opening_twice_extends_rather_than_spawning_a_second_server(self):
        self.assertEqual(self.window.open(1)[1], "iperf_opened")
        first_proc = self.window._proc
        self.assertEqual(self.window.open(5)[1], "iperf_extended")
        self.assertIs(self.window._proc, first_proc, "a second iperf3 was spawned")
        self.assertGreater(self.window.state()[1], 60)

    def test_duration_is_clamped_to_the_maximum(self):
        self.window.open(9999)
        self.assertLessEqual(self.window.state()[1], 5 * 60)

    def test_garbage_duration_falls_back_to_the_default(self):
        ok, _ = self.window.open("not a number")
        self.assertTrue(ok)
        self.assertGreater(self.window.state()[1], 0)

    def test_a_window_that_ran_out_reports_closed(self):
        self.window.open(1)
        # Expire it without waiting a real minute: move the deadline into the
        # past and let the reap path notice, exactly as the timer would.
        with self.window._lock:
            self.window._deadline = time.time() - 1
            self.window._expire()
        self.assertFalse(self.window.state()[0])
        self.assertIn((15299, False), self.calls)


class AnytlsPageTest(unittest.TestCase):
    """The console's anytls node page: what it reads, and what it must not leak."""

    FAKE_PASSWORD = "TEST-PASSWORD-NOT-REAL"
    FAKE_SNI = "www.example.invalid"

    @classmethod
    def setUpClass(cls):
        cls.dir = Path(TEST_DATA_DIR) / "anytls"
        (cls.dir / "cert").mkdir(parents=True, exist_ok=True)
        cls.cert = cls.dir / "cert" / "fullchain.pem"
        key = cls.dir / "cert" / "key.pem"
        # The SNI is only recoverable from the certificate's CN, so the
        # fixture has to be a real certificate rather than a stub file.
        subprocess.run(
            ["openssl", "req", "-x509", "-nodes", "-newkey", "ec",
             "-pkeyopt", "ec_paramgen_curve:prime256v1",
             "-keyout", str(key), "-out", str(cls.cert), "-days", "1",
             "-subj", f"/CN={cls.FAKE_SNI}"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        cls.config = cls.dir / "config.json"
        cls.config.write_text(json.dumps({
            "inbounds": [{
                "type": "anytls",
                "listen_port": 27999,
                "users": [{"name": "anytls", "password": cls.FAKE_PASSWORD}],
                "tls": {"enabled": True, "certificate_path": str(cls.cert)},
            }],
        }))

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.ConsoleHandler)
        cls.server.daemon_threads = True
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.password = app.ADMIN_PASSWORD

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.original_config = app.ANYTLS_CONFIG
        app.ANYTLS_CONFIG = self.config

    def tearDown(self):
        app.ANYTLS_CONFIG = self.original_config

    def login(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/login", body=f"password={self.password}",
                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        resp = conn.getresponse()
        cookie_header = resp.getheader("Set-Cookie")
        resp.read()
        conn.close()
        jar = SimpleCookie()
        jar.load(cookie_header)
        return jar["session"].value

    def get(self, path):
        session = self.login()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", path, headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()
        return resp, body

    # -- reading the installed node ---------------------------------------

    def test_reads_port_password_and_sni(self):
        node = app.anytls_node()
        self.assertEqual(node["port"], 27999)
        self.assertEqual(node["password"], self.FAKE_PASSWORD)
        self.assertEqual(node["sni"], self.FAKE_SNI,
                         "SNI must come back from the certificate CN")

    def test_absent_config_is_not_an_error(self):
        app.ANYTLS_CONFIG = Path("/nonexistent/config.json")
        self.assertIsNone(app.anytls_node())
        self.assertFalse(app.anytls_installed())

    def test_malformed_config_is_not_an_error(self):
        broken = self.dir / "broken.json"
        broken.write_text("{ this is not json")
        app.ANYTLS_CONFIG = broken
        self.assertIsNone(app.anytls_node(), "a bad config must not 500 the console")

    def test_clash_line_and_share_link_shapes(self):
        node = app.anytls_node()
        clash = app.anytls_clash_line(node, "198.51.100.7", "n")
        self.assertIn("type: anytls", clash)
        self.assertIn("server: 198.51.100.7", clash)
        self.assertIn("port: 27999", clash)
        self.assertIn(f'password: "{self.FAKE_PASSWORD}"', clash)
        self.assertIn("skip-cert-verify: true", clash)

        link = app.anytls_share_link(node, "198.51.100.7", "n")
        self.assertTrue(link.startswith("anytls://"))
        self.assertIn("@198.51.100.7:27999", link)
        self.assertIn("insecure=1", link)
        self.assertIn(f"sni={self.FAKE_SNI}", link)

    def test_share_link_percent_encodes_the_password(self):
        # Real generated passwords are base64 and routinely contain / and +,
        # which would otherwise break the URL.
        node = dict(app.anytls_node(), password="a/b+c=")
        link = app.anytls_share_link(node, "198.51.100.7", "n")
        self.assertIn("a%2Fb%2Bc%3D@", link)
        self.assertNotIn("a/b+c=@", link)

    # -- the page ---------------------------------------------------------

    def test_page_hides_anytls_share_link_qr_and_clash(self):
        resp, body = self.get("/proxy")
        self.assertEqual(resp.status, 200)
        self.assertNotIn('id="anytls-clash-', body)
        self.assertNotIn(app.STRINGS["en"]["anytls_clash"], body)
        self.assertNotIn('id="anytls-link-', body)
        self.assertNotIn('data-qr-text=', body)
        self.assertNotIn('class="qr-details"', body)
        self.assertNotIn('anytls://', body)
        self.assertIn("/static/copy.js", body)

    def test_page_shows_port_password_and_sni_as_fields(self):
        # Keep the installer facts readable as separate fields.
        _, body = self.get("/proxy")
        for key in ("anytls_port", "anytls_password", "anytls_sni"):
            self.assertIn(app.STRINGS["en"][key], body)
        self.assertIn('data-private-id="legacy-anytls"', body)
        self.assertNotIn("27999", body)
        self.assertNotIn(self.FAKE_PASSWORD, body)

    def test_page_keeps_addresses_without_share_links_or_qr_scripts(self):
        with patch.object(app, "local_addresses", return_value=[("eth0", "192.168.1.8")]), \
             patch.object(app, "tailscale_address", return_value="100.64.0.8"):
            _, body = self.get("/proxy")
        self.assertIn("192.168.1.8", body)
        self.assertIn("100.64.0.8", body)
        self.assertNotIn('id="anytls-link-', body)
        self.assertNotIn('data-qr-text=', body)
        for script in ("/static/qrcode.js", "/static/qrcode-utf8.js",
                       "/static/qrcode-render.js"):
            self.assertNotIn(f'<script src="{script}"', body)

    def test_public_address_file_is_not_displayed(self):
        public_file = self.config.parent / "public-ip.txt"
        public_file.write_text("198.51.100.7\n")
        try:
            with patch.object(app, "local_addresses", return_value=[("eth0", "192.168.1.8")]), \
                 patch.object(app, "tailscale_address", return_value=""):
                _, body = self.get("/proxy")
            self.assertNotIn("198.51.100.7", body)
            self.assertIn("192.168.1.8", body)
        finally:
            public_file.unlink()

    # -- rotating the credentials -----------------------------------------

    def post(self, path, body):
        session = self.login()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", path, body=body, headers={
            "Cookie": f"session={session}",
            "Content-Type": "application/x-www-form-urlencoded",
        })
        resp = conn.getresponse()
        resp.read()
        conn.close()
        return resp

    def test_reset_form_requires_a_confirmation(self):
        _, body = self.get("/proxy")
        self.assertIn('action="/anytls/reset"', body)
        self.assertIn('name="confirm"', body)
        self.assertIn(app.STRINGS["en"]["anytls_reset_confirm"], body)

    def test_unconfirmed_reset_changes_nothing(self):
        # The real thing is stubbed throughout this class: letting a test run
        # setup-anytls.sh would rotate the credentials of whatever node the
        # machine running the suite happens to have installed.
        called = []
        original = app.anytls_reset
        app.anytls_reset = lambda: called.append(1) or "anytls_reset_done"
        try:
            resp = self.post("/anytls/reset", "")
            self.assertEqual(resp.status, 302)
            self.assertEqual(resp.getheader("Location"),
                             "/proxy?msg=anytls_reset_unconfirmed")
            self.assertEqual(called, [], "the node must not be touched")
        finally:
            app.anytls_reset = original

    def test_confirmed_reset_runs_once(self):
        called = []
        original = app.anytls_reset
        app.anytls_reset = lambda: called.append(1) or "anytls_reset_done"
        try:
            resp = self.post("/anytls/reset", "confirm=yes")
            self.assertEqual(resp.getheader("Location"),
                             "/proxy?msg=anytls_reset_done")
            self.assertEqual(len(called), 1)
        finally:
            app.anytls_reset = original

    def test_a_forged_confirmation_value_is_rejected(self):
        called = []
        original = app.anytls_reset
        app.anytls_reset = lambda: called.append(1) or "anytls_reset_done"
        try:
            for body in ("confirm=1", "confirm=true", "confirm=on", "confirm="):
                with self.subTest(body=body):
                    resp = self.post("/anytls/reset", body)
                    self.assertEqual(resp.getheader("Location"),
                                     "/proxy?msg=anytls_reset_unconfirmed")
            self.assertEqual(called, [])
        finally:
            app.anytls_reset = original

    def test_reset_runs_outside_this_service_sandbox(self):
        # The unit has ProtectSystem=strict with ReadWritePaths=$PREFIX only,
        # so /etc is read-only here — and the reset must write
        # /etc/vps-server-anytls and a unit file. Running it in-process failed
        # partway, after the old port's firewall rule had already been pulled.
        original = app.shutil.which
        app.shutil.which = lambda name: "/usr/bin/systemd-run" if name == "systemd-run" else None
        try:
            cmd = app.anytls_reset_command()
            self.assertEqual(cmd[0], "systemd-run")
            self.assertIn("--wait", cmd)
            self.assertIn("--pipe", cmd)
            self.assertIn("--collect", cmd)
            self.assertEqual(cmd[-2:], [str(app.ANYTLS_SETUP), "reset"])
        finally:
            app.shutil.which = original

    def test_reset_falls_back_to_a_direct_call_without_systemd_run(self):
        # Containers and stripped images have no systemd-run — and are also
        # where the hardening is omitted, so a direct call works there.
        original = app.shutil.which
        app.shutil.which = lambda name: None
        try:
            self.assertEqual(app.anytls_reset_command(),
                             ["bash", str(app.ANYTLS_SETUP), "reset"])
        finally:
            app.shutil.which = original

    def test_reset_reports_a_missing_script_rather_than_crashing(self):
        original = app.ANYTLS_SETUP
        app.ANYTLS_SETUP = Path("/nonexistent/setup-anytls.sh")
        try:
            self.assertEqual(app.anytls_reset(), "anytls_reset_missing")
        finally:
            app.ANYTLS_SETUP = original

    def test_reset_result_messages_are_whitelisted(self):
        # Same guard as the iperf page: the key indexes STRINGS, so an
        # arbitrary ?msg= would otherwise render chosen text on the page.
        _, body = self.get("/proxy?msg=anytls_warning")
        self.assertNotIn('class="notice"', body)
        _, body = self.get("/proxy?msg=anytls_reset_done")
        self.assertIn('class="notice"', body)

    def test_local_addresses_skip_virtual_interfaces(self):
        for iface, address in app.local_addresses():
            self.assertFalse(iface.startswith(app.VIRTUAL_IFACE_PREFIXES),
                             f"{iface} is a virtual interface and should be filtered")
            self.assertRegex(address, r"^\d+\.\d+\.\d+\.\d+$")

    def test_page_reports_a_stopped_service_as_stopped(self):
        # Point at a unit that cannot exist rather than trusting the host's
        # state. The first version of this test assumed nothing named
        # vps-server-anytls.service was running, which made it pass or fail
        # depending on what the developer happened to have installed.
        original = app.ANYTLS_SERVICE
        app.ANYTLS_SERVICE = "vps-server-anytls-does-not-exist.service"
        try:
            self.assertFalse(app.anytls_node()["running"])
            _, body = self.get("/proxy")
            self.assertIn("is-closed", body)
            self.assertIn("vps-server-anytls-does-not-exist.service", body,
                          "the page should name the unit to check")
        finally:
            app.ANYTLS_SERVICE = original

    def test_page_reports_a_running_service_as_running(self):
        original = app._run_quiet
        app._run_quiet = lambda cmd: True
        try:
            self.assertTrue(app.anytls_node()["running"])
            _, body = self.get("/proxy")
            self.assertIn("is-open", body)
        finally:
            app._run_quiet = original

    def test_dashboard_keeps_proxy_card_available_for_installation(self):
        _, body = self.get("/")
        self.assertIn('href="/proxy"', body)

        app.ANYTLS_CONFIG = Path("/nonexistent/config.json")
        _, body = self.get("/")
        self.assertIn('href="/proxy"', body)

    def test_page_is_graceful_when_not_installed(self):
        app.ANYTLS_CONFIG = Path("/nonexistent/config.json")
        resp, body = self.get("/proxy")
        self.assertEqual(resp.status, 200)
        self.assertNotIn(self.FAKE_PASSWORD, body)


class ProxyPageTest(unittest.TestCase):
    """The console's multi-protocol proxy page: parsing, links, and the page."""

    FAKE_VMESS_UUID = "11111111-1111-1111-1111-111111111111"
    FAKE_VLESS_UUID = "22222222-2222-2222-2222-222222222222"
    FAKE_TROJAN_PASSWORD = "TEST-TROJAN-PASSWORD"
    FAKE_SS_PASSWORD = "TEST-SS-PASSWORD"
    FAKE_SNI = "www.example.invalid"

    @classmethod
    def setUpClass(cls):
        cls.dir = Path(TEST_DATA_DIR) / "proxy"
        (cls.dir / "cert").mkdir(parents=True, exist_ok=True)
        cls.cert = cls.dir / "cert" / "fullchain.pem"
        key = cls.dir / "cert" / "key.pem"
        subprocess.run(
            ["openssl", "req", "-x509", "-nodes", "-newkey", "ec",
             "-pkeyopt", "ec_paramgen_curve:prime256v1",
             "-keyout", str(key), "-out", str(cls.cert), "-days", "1",
             "-subj", f"/CN={cls.FAKE_SNI}"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        cls.config = cls.dir / "config.json"
        cls.config.write_text(json.dumps({
            "inbounds": [
                {"type": "vmess", "listen_port": 41001,
                 "users": [{"name": "vmess", "uuid": cls.FAKE_VMESS_UUID, "alterId": 0}],
                 "tls": {"enabled": True, "certificate_path": str(cls.cert)}},
                {"type": "vless", "listen_port": 45001,
                 "users": [{"name": "vless", "uuid": cls.FAKE_VLESS_UUID}],
                 "tls": {"enabled": True, "certificate_path": str(cls.cert)}},
                {"type": "trojan", "listen_port": 50001,
                 "users": [{"name": "trojan", "password": cls.FAKE_TROJAN_PASSWORD}],
                 "tls": {"enabled": True, "certificate_path": str(cls.cert)}},
                {"type": "shadowsocks", "listen_port": 55001,
                 "method": "2022-blake3-aes-128-gcm", "password": cls.FAKE_SS_PASSWORD},
            ],
        }))

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.ConsoleHandler)
        cls.server.daemon_threads = True
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.password = app.ADMIN_PASSWORD

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.original_config = app.PROXY_CONFIG
        app.PROXY_CONFIG = self.config

    def tearDown(self):
        app.PROXY_CONFIG = self.original_config

    def login(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/login", body=f"password={self.password}",
                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        resp = conn.getresponse()
        cookie_header = resp.getheader("Set-Cookie")
        resp.read()
        conn.close()
        jar = SimpleCookie()
        jar.load(cookie_header)
        return jar["session"].value

    def get(self, path):
        session = self.login()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", path, headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()
        return resp, body

    def post(self, path, body):
        session = self.login()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", path, body=body, headers={
            "Cookie": f"session={session}",
            "Content-Type": "application/x-www-form-urlencoded",
        })
        resp = conn.getresponse()
        resp.read()
        conn.close()
        return resp

    # -- credential-only apply ---------------------------------------------

    def request_apply(self, session=None, fields=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if session is not None:
            headers["Cookie"] = f"session={session}"
        conn.request("POST", "/proxy/apply", body=urlencode(fields or {}), headers=headers)
        response = conn.getresponse()
        status, location, cache = (response.status, response.getheader("Location"),
                                   response.getheader("Cache-Control"))
        body = response.read()
        conn.close()
        return status, location, cache, body

    def test_node_apply_requires_auth_and_session_even_when_auth_off(self):
        session = self.login()
        fields = {"protocol": "vmess", "credential": self.FAKE_VMESS_UUID,
                  "csrf": app.node_csrf_token(session, "vmess")}
        with patch.object(app, "node_apply") as apply:
            self.assertNotEqual(self.request_apply(fields=fields)[0], 200)
            with patch.object(app, "AUTH_ENABLED", False):
                self.assertEqual(self.request_apply(session, fields)[0], 403)
                conn = http.client.HTTPConnection("127.0.0.1", self.port)
                conn.request("GET", "/proxy", headers={"Cookie": f"session={session}"})
                resp = conn.getresponse()
                self.assertEqual(resp.status, 403)
                resp.read()
                conn.close()
            apply.assert_not_called()

    def test_node_apply_csrf_rejects_forgery_missing_and_other_session(self):
        session, other = self.login(), self.login()
        fields = {"protocol": "vmess", "credential": self.FAKE_VMESS_UUID}
        with patch.object(app, "node_apply") as apply:
            for csrf in ("", "forged", app.node_csrf_token(other, "vmess"),
                         app.node_csrf_token(session, "vless")):
                status, _, _, _ = self.request_apply(session, {**fields, "csrf": csrf})
                self.assertEqual(status, 403)
            apply.assert_not_called()

    def test_node_apply_has_no_public_route(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), app.ProbeHandler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1])
            conn.request("POST", "/proxy/apply", body="credential=secret")
            response = conn.getresponse()
            self.assertNotEqual(response.status, 200)
            self.assertNotIn(b"secret", response.read())
            conn.close()
        finally:
            server.shutdown()
            server.server_close()

    def test_node_apply_only_accepts_exact_fields_and_protocol(self):
        session = self.login()
        fields = {"protocol": "bogus", "credential": "secret",
                  "csrf": app.node_csrf_token(session, "bogus")}
        with patch.object(app, "node_apply") as apply:
            self.assertEqual(self.request_apply(session, fields)[0], 403)
            fields["protocol"] = "vmess"
            fields["csrf"] = app.node_csrf_token(session, "vmess")
            self.assertEqual(self.request_apply(session, {**fields, "port": "99"})[0], 400)
            self.assertEqual(self.request_apply(session, {**fields, "credential": "x" * 2000})[0], 400)
            apply.assert_not_called()

    def test_node_apply_form_wiring_and_stdin_no_secret_in_location_or_argv(self):
        session = self.login()
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", "/proxy", headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        page = resp.read().decode()
        self.assertEqual(resp.getheader("Cache-Control"), "no-store")
        conn.close()
        self.assertEqual(page.count('action="/proxy/apply"'), 4 + int(app.anytls_node() is not None))
        self.assertEqual(page.count('class="proxy-node-settings"'), 4 + int(app.anytls_node() is not None))
        helper = self.dir / "node_config.py"
        helper.write_text("# test helper path\n")
        secret = "new-secret-value"
        fields = {"protocol": "trojan", "credential": secret,
                  "csrf": app.node_csrf_token(session, "trojan")}
        with patch.object(app, "NODE_CONFIG_HELPER", helper), \
             patch.object(app.shutil, "which", return_value="/usr/bin/systemd-run"), \
             patch.object(app.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            status, location, cache, body = self.request_apply(session, fields)
            self.assertEqual((status, location, cache),
                             (302, "/proxy?msg=node_apply_done", "no-store"))
            self.assertNotIn(secret.encode(), body)
            argv = run.call_args.args[0]
            self.assertEqual(argv[:4], ["systemd-run", "--pipe", "--wait", "--collect"])
            self.assertEqual(argv[-3:], ["/usr/bin/python3", str(helper), "trojan"])
            self.assertNotIn(secret, " ".join(argv) + location)
            self.assertEqual(run.call_args.kwargs["input"], secret.encode())

    def test_node_apply_failure_never_exposes_helper_exception(self):
        helper = self.dir / "node_config.py"
        helper.write_text("# test helper path\n")
        with patch.object(app, "NODE_CONFIG_HELPER", helper), \
             patch.object(app.shutil, "which", return_value="/usr/bin/systemd-run"), \
             patch.object(app.subprocess, "run", side_effect=OSError("sensitive detail")):
            self.assertEqual(app.node_apply("vmess", "private-value"), "node_apply_failed")

    # -- reading the installed nodes ---------------------------------------

    def test_reads_all_four_protocols_in_order(self):
        nodes = app.proxy_nodes()
        self.assertEqual([n["type"] for n in nodes],
                         ["vmess", "vless", "trojan", "shadowsocks"])

    def test_secret_field_matches_each_protocol(self):
        nodes = {n["type"]: n for n in app.proxy_nodes()}
        self.assertEqual(nodes["vmess"]["secret"], self.FAKE_VMESS_UUID)
        self.assertEqual(nodes["vless"]["secret"], self.FAKE_VLESS_UUID)
        self.assertEqual(nodes["trojan"]["secret"], self.FAKE_TROJAN_PASSWORD)
        self.assertEqual(nodes["shadowsocks"]["secret"], self.FAKE_SS_PASSWORD)

    def test_absent_config_is_not_an_error(self):
        app.PROXY_CONFIG = Path("/nonexistent/config.json")
        self.assertEqual(app.proxy_nodes(), [])
        self.assertFalse(app.proxy_installed())

    def test_malformed_config_is_not_an_error(self):
        broken = self.dir / "broken.json"
        broken.write_text("{ this is not json")
        app.PROXY_CONFIG = broken
        self.assertEqual(app.proxy_nodes(), [], "a bad config must not 500 the console")

    def test_unknown_inbound_types_are_ignored(self):
        odd = self.dir / "odd.json"
        odd.write_text(json.dumps({"inbounds": [
            {"type": "hysteria2", "listen_port": 1},
            {"type": "vmess", "listen_port": 41001,
             "users": [{"uuid": self.FAKE_VMESS_UUID}]},
        ]}))
        app.PROXY_CONFIG = odd
        nodes = app.proxy_nodes()
        self.assertEqual([n["type"] for n in nodes], ["vmess"])

    # -- clash lines and share links, one per protocol scheme --------------

    def test_vmess_share_link_is_a_valid_base64_json_blob(self):
        node = {"type": "vmess", "port": 41001, "secret": self.FAKE_VMESS_UUID}
        link = app.proxy_share_link(node, self.FAKE_SNI, "198.51.100.7", "n")
        self.assertTrue(link.startswith("vmess://"))
        payload = json.loads(base64.b64decode(link[len("vmess://"):]))
        self.assertEqual(payload["add"], "198.51.100.7")
        self.assertEqual(payload["port"], "41001")
        self.assertEqual(payload["id"], self.FAKE_VMESS_UUID)
        self.assertEqual(payload["sni"], self.FAKE_SNI)
        self.assertEqual(payload["tls"], "tls")

    def test_vless_share_link_shape(self):
        node = {"type": "vless", "port": 45001, "secret": self.FAKE_VLESS_UUID}
        link = app.proxy_share_link(node, self.FAKE_SNI, "198.51.100.7", "n")
        self.assertTrue(link.startswith(f"vless://{self.FAKE_VLESS_UUID}@198.51.100.7:45001"))
        self.assertIn("security=tls", link)
        self.assertIn(f"sni={self.FAKE_SNI}", link)

    def test_trojan_share_link_percent_encodes_the_password(self):
        node = {"type": "trojan", "port": 50001, "secret": "a/b+c="}
        link = app.proxy_share_link(node, self.FAKE_SNI, "198.51.100.7", "n")
        self.assertIn("a%2Fb%2Bc%3D@", link)
        self.assertNotIn("a/b+c=@", link)

    def test_shadowsocks_share_link_is_method_colon_password_base64(self):
        node = {"type": "shadowsocks", "port": 55001, "secret": self.FAKE_SS_PASSWORD}
        link = app.proxy_share_link(node, "", "198.51.100.7", "n")
        self.assertTrue(link.startswith("ss://"))
        userinfo = link[len("ss://"):].split("@")[0]
        decoded = base64.b64decode(userinfo).decode()
        self.assertEqual(decoded, f"2022-blake3-aes-128-gcm:{self.FAKE_SS_PASSWORD}")

    def test_clash_lines_use_the_right_type_per_protocol(self):
        nodes = {n["type"]: n for n in app.proxy_nodes()}
        self.assertIn("type: vmess", app.proxy_clash_line(nodes["vmess"], self.FAKE_SNI, "h", "n"))
        self.assertIn("type: vless", app.proxy_clash_line(nodes["vless"], self.FAKE_SNI, "h", "n"))
        self.assertIn("type: trojan", app.proxy_clash_line(nodes["trojan"], self.FAKE_SNI, "h", "n"))
        self.assertIn("type: ss", app.proxy_clash_line(nodes["shadowsocks"], "", "h", "n"))

    # -- the page ---------------------------------------------------------

    def test_page_shows_one_section_per_protocol(self):
        _, body = self.get("/proxy")
        for proto in ("vmess", "vless", "trojan", "shadowsocks"):
            self.assertIn(f"<h2>{proto}</h2>", body)

    def test_page_shows_ports_secrets_and_sni_without_clash_configuration(self):
        _, body = self.get("/proxy")
        for port in ("41001", "45001", "50001", "55001"):
            self.assertNotIn(port, body)
        for secret in (self.FAKE_VMESS_UUID, self.FAKE_VLESS_UUID,
                       self.FAKE_TROJAN_PASSWORD, self.FAKE_SS_PASSWORD):
            self.assertNotIn(secret, body)
        self.assertIn(self.FAKE_SNI, body)
        self.assertNotIn('id="proxy-vmess-clash-', body)
        self.assertNotIn('id="proxy-vless-clash-', body)
        self.assertNotIn('id="proxy-trojan-clash-', body)
        self.assertNotIn('id="proxy-shadowsocks-clash-', body)
        for proto in ("vmess", "vless", "trojan", "shadowsocks"):
            self.assertNotIn(f'id="proxy-{proto}-link-', body)
            self.assertIn(f'data-private-id="legacy-{proto}"', body)
        self.assertIn(app.STRINGS["en"]["anytls_lan"].format(iface="eth0"), body)

    def test_page_hides_proxy_share_links_and_qr(self):
        resp, body = self.get("/proxy")
        self.assertEqual(resp.status, 200)
        self.assertNotIn('data-qr-text=', body)
        self.assertNotIn('class="qr-details"', body)
        for scheme in ("vmess://", "vless://", "trojan://", "ss://"):
            self.assertNotIn(scheme, body)
        for script in ("/static/qrcode.js", "/static/qrcode-utf8.js",
                       "/static/qrcode-render.js"):
            self.assertNotIn(f'<script src="{script}"', body)

    def test_dashboard_keeps_proxy_card_available_for_installation(self):
        _, body = self.get("/")
        self.assertIn('href="/proxy"', body)

        # /proxy shows anytls too now (see page_proxy()'s docstring), so
        # hiding the link needs BOTH modules absent — anytls_installed()
        # checks the real, unmocked ANYTLS_CONFIG default, which genuinely
        # exists on some hosts (this one included).
        original_anytls_config = app.ANYTLS_CONFIG
        app.PROXY_CONFIG = Path("/nonexistent/config.json")
        app.ANYTLS_CONFIG = Path("/nonexistent/config.json")
        try:
            _, body = self.get("/")
            self.assertIn('href="/proxy"', body)
        finally:
            app.ANYTLS_CONFIG = original_anytls_config

    def test_page_is_graceful_when_not_installed(self):
        original_anytls_config = app.ANYTLS_CONFIG
        app.PROXY_CONFIG = Path("/nonexistent/config.json")
        app.ANYTLS_CONFIG = Path("/nonexistent/config.json")
        try:
            resp, body = self.get("/proxy")
            self.assertEqual(resp.status, 200)
            self.assertNotIn(self.FAKE_TROJAN_PASSWORD, body)
        finally:
            app.ANYTLS_CONFIG = original_anytls_config

    # -- rotating the credentials -------------------------------------------

    def test_reset_form_requires_a_confirmation(self):
        _, body = self.get("/proxy")
        self.assertIn('action="/proxy/reset"', body)
        self.assertIn('name="confirm"', body)

    def test_each_protocol_has_its_own_reset_form(self):
        # One combined "reset everything" button used to force rotating
        # protocols nobody asked to touch — reported by an operator. Each
        # protocol section now carries its own hidden protocol field.
        _, body = self.get("/proxy")
        for proto in ("vmess", "vless", "trojan", "shadowsocks"):
            self.assertIn(f'<input type="hidden" name="protocol" value="{proto}">', body)
        self.assertEqual(
            body.count('action="/proxy/reset"'), 4,
            "one reset form per protocol, not one shared form",
        )

    def test_unconfirmed_reset_changes_nothing(self):
        called = []
        original = app.proxy_reset
        app.proxy_reset = lambda protocol=None: called.append(protocol) or "proxy_reset_done"
        try:
            resp = self.post("/proxy/reset", "protocol=vmess")
            self.assertEqual(resp.status, 302)
            self.assertEqual(resp.getheader("Location"),
                             "/proxy?msg=proxy_reset_unconfirmed")
            self.assertEqual(called, [], "the nodes must not be touched")
        finally:
            app.proxy_reset = original

    def test_confirmed_reset_runs_once_for_the_given_protocol(self):
        called = []
        original = app.proxy_reset
        app.proxy_reset = lambda protocol=None: called.append(protocol) or "proxy_reset_done"
        try:
            resp = self.post("/proxy/reset", "confirm=yes&protocol=trojan")
            self.assertEqual(resp.getheader("Location"), "/proxy?msg=proxy_reset_done")
            self.assertEqual(called, ["trojan"],
                             "only the named protocol may be touched")
        finally:
            app.proxy_reset = original

    def test_an_unknown_protocol_is_rejected(self):
        called = []
        original = app.proxy_reset
        app.proxy_reset = lambda protocol=None: called.append(protocol) or "proxy_reset_done"
        try:
            resp = self.post("/proxy/reset", "confirm=yes&protocol=bogus")
            self.assertEqual(resp.getheader("Location"),
                             "/proxy?msg=proxy_reset_unconfirmed")
            self.assertEqual(called, [], "an unrecognised protocol must not reach the script")
        finally:
            app.proxy_reset = original

    def test_reset_command_targets_only_the_given_protocol(self):
        original = app.shutil.which
        app.shutil.which = lambda name: None  # exercise the direct-call form
        try:
            cmd = app.proxy_reset_command("vmess")
            self.assertEqual(cmd, ["bash", str(app.PROXY_SETUP), "reset", "vmess"])
            # No argument still means "reset everything currently installed" —
            # the pre-existing behaviour, kept for the terminal / VPSSRV_
            # scriptable path, not exposed anywhere in the console UI any more.
            self.assertEqual(app.proxy_reset_command(),
                             ["bash", str(app.PROXY_SETUP), "reset"])
        finally:
            app.shutil.which = original

    # -- reserved_ports() awareness ------------------------------------------

    def test_portfwd_reserves_every_installed_proxy_port(self):
        mgr = app.PortForwardManager(self.dir / "portfwd.json", 10)
        reserved = mgr.reserved_ports()
        for port in (41001, 45001, 50001, 55001):
            self.assertIn(port, reserved,
                         "a port-forward rule must not be able to steal a proxy port")

    # -- the anytls+proxy merge ---------------------------------------------

    def test_anytls_and_proxy_share_one_page_in_node_grid(self):
        # Both modules appear in one workspace, with one card per node and
        # one navigation entry for the whole page.
        anytls_dir = Path(TEST_DATA_DIR) / "anytls-merge"
        (anytls_dir / "cert").mkdir(parents=True, exist_ok=True)
        cert = anytls_dir / "cert" / "fullchain.pem"
        key = anytls_dir / "cert" / "key.pem"
        subprocess.run(
            ["openssl", "req", "-x509", "-nodes", "-newkey", "ec",
             "-pkeyopt", "ec_paramgen_curve:prime256v1",
             "-keyout", str(key), "-out", str(cert), "-days", "1",
             "-subj", "/CN=merge.example.invalid"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        anytls_config = anytls_dir / "config.json"
        anytls_config.write_text(json.dumps({
            "inbounds": [{
                "type": "anytls", "listen_port": 28111,
                "users": [{"name": "anytls", "password": "MERGE-TEST-PW"}],
                "tls": {"enabled": True, "certificate_path": str(cert)},
            }],
        }))
        original_anytls_config = app.ANYTLS_CONFIG
        app.ANYTLS_CONFIG = anytls_config
        try:
            _, body = self.get("/proxy")
            self.assertIn("<h2>anytls</h2>", body)
            for proto in ("vmess", "vless", "trojan", "shadowsocks"):
                self.assertIn(f"<h2>{proto}</h2>", body)
            self.assertEqual(body.count('class="proxy-workspace"'), 1)
            self.assertEqual(body.count('class="proxy-node"'), 5)
            self.assertIn('class="proxy-node-grid"', body)
            # Function navigation lives on the Dashboard, not in the global header.
            self.assertEqual(body.count('href="/proxy"'), 0)
            self.assertIn('href="/"', body)
        finally:
            app.ANYTLS_CONFIG = original_anytls_config

    def test_anytls_reset_redirects_to_the_merged_page(self):
        original = app.anytls_reset
        app.anytls_reset = lambda: "anytls_reset_done"
        try:
            resp = self.post("/anytls/reset", "confirm=yes")
            self.assertEqual(resp.getheader("Location"), "/proxy?msg=anytls_reset_done")
        finally:
            app.anytls_reset = original

    def test_old_anytls_url_redirects_to_the_merged_page(self):
        session = self.login()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/anytls", headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 302)
        self.assertEqual(resp.getheader("Location"), "/proxy")


class PortForwardManagerTest(unittest.TestCase):
    """add/remove/enable never touch a real iptables — every case here mocks
    portfwd_rule_apply and _ensure_ip_forward, the same way IperfWindowTest
    stubs firewall_port. Persistence and the reserved-port math are what this
    actually exercises.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="vpssrv-portfwd-test-")
        self.original_apply = app.portfwd_rule_apply
        self.original_ensure = app._ensure_ip_forward
        self.calls = []
        app.portfwd_rule_apply = (
            lambda rule, opening: self.calls.append((rule["id"], opening)) or True
        )
        app._ensure_ip_forward = lambda: None
        self.manager = app.PortForwardManager(Path(self.tmp) / "portfwd.json", max_rules=3)

    def tearDown(self):
        app.portfwd_rule_apply = self.original_apply
        app._ensure_ip_forward = self.original_ensure
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_persists_and_applies(self):
        rule, key = self.manager.add("tcp", 25565, "100.64.1.2", 25565, "game")
        self.assertEqual(key, "portfwd_added")
        self.assertIsNotNone(rule)
        self.assertEqual(self.calls, [(rule["id"], True)])
        self.assertEqual(len(self.manager.list_rules()), 1)

    def test_add_rejects_a_reserved_public_port(self):
        rule, key = self.manager.add("tcp", app.CONSOLE_PORT, "100.64.1.2", 80, "")
        self.assertIsNone(rule)
        self.assertEqual(key, "portfwd_port_taken")
        self.assertEqual(self.calls, [])

    def test_add_rejects_a_public_port_already_used_by_another_rule(self):
        self.manager.add("tcp", 25565, "100.64.1.2", 25565, "")
        rule, key = self.manager.add("udp", 25565, "100.64.1.3", 999, "")
        self.assertIsNone(rule)
        self.assertEqual(key, "portfwd_port_taken")

    def test_add_enforces_the_rule_limit(self):
        for i in range(3):
            self.manager.add("tcp", 20000 + i, "100.64.1.2", 1000 + i, "")
        rule, key = self.manager.add("tcp", 20099, "100.64.1.2", 1099, "")
        self.assertIsNone(rule)
        self.assertEqual(key, "portfwd_limit")

    def test_remove_withdraws_and_deletes(self):
        rule, _ = self.manager.add("tcp", 25565, "100.64.1.2", 25565, "")
        key = self.manager.remove(rule["id"])
        self.assertEqual(key, "portfwd_removed")
        self.assertEqual(self.manager.list_rules(), [])
        self.assertEqual(self.calls, [(rule["id"], True), (rule["id"], False)])

    def test_disable_then_enable_round_trips(self):
        rule, _ = self.manager.add("tcp", 25565, "100.64.1.2", 25565, "")
        self.assertEqual(self.manager.set_enabled(rule["id"], False), "portfwd_disabled")
        self.assertFalse(self.manager.list_rules()[0]["enabled"])
        self.assertEqual(self.manager.set_enabled(rule["id"], True), "portfwd_enabled")
        self.assertTrue(self.manager.list_rules()[0]["enabled"])
        self.assertEqual(
            self.calls,
            [(rule["id"], True), (rule["id"], False), (rule["id"], True)],
        )

    def test_a_disabled_rule_still_reserves_its_own_port(self):
        # One public port maps to at most one configured rule, disabled or
        # not — otherwise re-enabling either one later would be a race.
        rule, _ = self.manager.add("tcp", 25565, "100.64.1.2", 25565, "")
        self.manager.set_enabled(rule["id"], False)
        other, key = self.manager.add("udp", 25565, "100.64.1.3", 1, "")
        self.assertIsNone(other)
        self.assertEqual(key, "portfwd_port_taken")

    def test_enabling_is_refused_if_the_port_became_reserved_meanwhile(self):
        rule, _ = self.manager.add("tcp", 25565, "100.64.1.2", 25565, "")
        self.manager.set_enabled(rule["id"], False)
        original_anytls_node = app.anytls_node
        app.anytls_node = lambda: {"port": 25565}
        try:
            key = self.manager.set_enabled(rule["id"], True)
        finally:
            app.anytls_node = original_anytls_node
        self.assertEqual(key, "portfwd_port_taken")

    def test_state_survives_a_fresh_instance(self):
        self.manager.add("tcp", 25565, "100.64.1.2", 25565, "relayed game")
        reloaded = app.PortForwardManager(Path(self.tmp) / "portfwd.json", max_rules=3)
        self.assertEqual(reloaded.list_rules(), self.manager.list_rules())

    def test_load_reapplies_only_enabled_rules_withdraw_then_add(self):
        r1, _ = self.manager.add("tcp", 25565, "100.64.1.2", 25565, "")
        r2, _ = self.manager.add("tcp", 25566, "100.64.1.3", 25566, "")
        self.manager.set_enabled(r2["id"], False)
        self.calls.clear()
        self.manager.load()
        self.assertEqual(self.calls, [(r1["id"], False), (r1["id"], True)])

    def test_shutdown_withdraws_only_enabled_rules_without_flipping_state(self):
        r1, _ = self.manager.add("tcp", 25565, "100.64.1.2", 25565, "")
        r2, _ = self.manager.add("tcp", 25566, "100.64.1.3", 25566, "")
        self.manager.set_enabled(r2["id"], False)
        self.calls.clear()
        self.manager.shutdown()
        self.assertEqual(self.calls, [(r1["id"], False)])
        # A restart must bring r1 straight back, so shutdown must not have
        # rewritten its enabled flag to False.
        reloaded = [r for r in self.manager.list_rules() if r["id"] == r1["id"]][0]
        self.assertTrue(reloaded["enabled"])


class PortForwardConsoleTest(unittest.TestCase):
    """The /portfwd routes, driven over real HTTP against a live handler."""

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.ConsoleHandler)
        cls.server.daemon_threads = True
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.password = app.ADMIN_PASSWORD

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.original_apply = app.portfwd_rule_apply
        self.original_ensure = app._ensure_ip_forward
        self.calls = []
        app.portfwd_rule_apply = (
            lambda rule, opening: self.calls.append((rule["id"], opening)) or True
        )
        app._ensure_ip_forward = lambda: None
        self.tmp = tempfile.mkdtemp(prefix="vpssrv-portfwd-http-test-")
        app.PORTFWD = app.PortForwardManager(Path(self.tmp) / "portfwd.json", max_rules=3)

    def tearDown(self):
        app.portfwd_rule_apply = self.original_apply
        app._ensure_ip_forward = self.original_ensure
        shutil.rmtree(self.tmp, ignore_errors=True)

    def connect(self):
        return http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)

    def session_cookie(self):
        conn = self.connect()
        conn.request(
            "POST", "/login", body=f"password={self.password}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp = conn.getresponse()
        cookie_header = resp.getheader("Set-Cookie")
        resp.read()
        conn.close()
        jar = SimpleCookie()
        jar.load(cookie_header)
        return jar["session"].value

    def post(self, path, body, cookie):
        conn = self.connect()
        conn.request(
            "POST", path, body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Cookie": f"session={cookie}"},
        )
        resp = conn.getresponse()
        location = resp.getheader("Location")
        resp.read()
        conn.close()
        return resp.status, location

    def get(self, path, cookie):
        conn = self.connect()
        conn.request("GET", path, headers={"Cookie": f"session={cookie}"})
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()
        return resp, body

    def test_add_then_list_then_delete(self):
        cookie = self.session_cookie()
        status, location = self.post(
            "/portfwd/add",
            "protocol=tcp&public_port=25565&target_host=100.64.1.2&target_port=25565&label=game",
            cookie,
        )
        self.assertEqual(status, 302)
        self.assertEqual(location, "/portfwd?msg=portfwd_added")
        self.assertEqual(self.calls, [(app.PORTFWD.list_rules()[0]["id"], True)])

        resp, body = self.get("/portfwd", cookie)
        self.assertEqual(resp.status, 200)
        self.assertIn("game", body)
        self.assertNotIn("25565", body)
        self.assertIn('data-private-field="public-port"', body)

        rule_id = app.PORTFWD.list_rules()[0]["id"]
        status, location = self.post("/portfwd/delete", f"id={rule_id}", cookie)
        self.assertEqual(status, 302)
        self.assertEqual(location, "/portfwd?msg=portfwd_removed")
        self.assertEqual(app.PORTFWD.list_rules(), [])

    def test_add_rejects_an_invalid_target_host(self):
        cookie = self.session_cookie()
        status, location = self.post(
            "/portfwd/add",
            "protocol=tcp&public_port=25565&target_host=not-an-ip&target_port=25565",
            cookie,
        )
        self.assertEqual(status, 302)
        self.assertEqual(location, "/portfwd?msg=portfwd_invalid")
        self.assertEqual(app.PORTFWD.list_rules(), [])

    def test_disable_then_enable_over_http(self):
        cookie = self.session_cookie()
        self.post(
            "/portfwd/add",
            "protocol=udp&public_port=30000&target_host=100.64.1.9&target_port=30000",
            cookie,
        )
        rule_id = app.PORTFWD.list_rules()[0]["id"]
        status, location = self.post("/portfwd/disable", f"id={rule_id}", cookie)
        self.assertEqual((status, location), (302, "/portfwd?msg=portfwd_disabled"))
        self.assertFalse(app.PORTFWD.list_rules()[0]["enabled"])
        status, location = self.post("/portfwd/enable", f"id={rule_id}", cookie)
        self.assertEqual((status, location), (302, "/portfwd?msg=portfwd_enabled"))
        self.assertTrue(app.PORTFWD.list_rules()[0]["enabled"])

    def test_unauthenticated_request_is_redirected_to_login(self):
        conn = self.connect()
        conn.request("GET", "/portfwd")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 302)
        self.assertEqual(resp.getheader("Location"), "/login")
        resp.read()
        conn.close()


class IperfLabelTest(unittest.TestCase):
    """An open window turns the submit button into "extend", not a second "open"."""

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.ConsoleHandler)
        cls.server.daemon_threads = True
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.password = app.ADMIN_PASSWORD

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _page(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/login", body=f"password={self.password}",
                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        resp = conn.getresponse()
        jar = SimpleCookie()
        jar.load(resp.getheader("Set-Cookie"))
        resp.read()
        conn.request("GET", "/iperf",
                     headers={"Cookie": f"session={jar['session'].value}"})
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()
        return body

    def test_closed_window_offers_open_only(self):
        body = self._page()
        self.assertIn(app.STRINGS["en"]["iperf_open"], body)
        self.assertNotIn(app.STRINGS["en"]["iperf_extend"], body)
        self.assertNotIn(app.STRINGS["en"]["iperf_close"], body)
        self.assertIn('class="iperf-facts"', body)
        self.assertIn('class="iperf-panels"', body)
        self.assertIn('<h1>iperf3 server</h1>', body)
        self.assertIn('<h2>iperf3 client</h2>', body)
        self.assertIn('action="/iperf/port"', body)
        self.assertIn('action="/iperf/client"', body)

    def test_outbound_test_requires_csrf_and_renders_result(self):
        session = app.create_session()
        try:
            fields = {'host': '203.0.113.5', 'port': '5201', 'seconds': '10',
                      'mbps': '100', 'protocol': 'tcp', 'direction': 'upload',
                      'csrf': 'incorrect'}

            def post():
                conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
                conn.request('POST', '/iperf/client', body=urlencode(fields),
                             headers={'Cookie': f'session={session}',
                                      'Content-Type': 'application/x-www-form-urlencoded'})
                response = conn.getresponse()
                status, body = response.status, response.read().decode()
                conn.close()
                return status, body

            with patch.object(app.IPERF_CLIENT, 'run', return_value={'status': 'done', 'mbps': 81.5}) as run:
                self.assertEqual(post()[0], 403)
                run.assert_not_called()
                fields['csrf'] = app.access_csrf_token(session, 'iperf-client')
                with patch.object(app, 'IPERF_ENABLED', True):
                    status, body = post()
                self.assertEqual(status, 302)
                run.assert_called_once_with('203.0.113.5', '5201', 'tcp',
                                            'upload', '10', '100')
                conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
                conn.request('GET', '/iperf?client=done',
                             headers={'Cookie': f'session={session}'})
                response = conn.getresponse()
                body = response.read().decode()
                conn.close()
                self.assertEqual(response.status, 200)
                self.assertIn('81.50 Mbit/s', body)
                self.assertEqual(app.IPERF_CLIENT.take_result(session), (None, None))
        finally:
            app.destroy_session(session)

    def test_port_can_be_changed_and_persists(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            new_port = probe.getsockname()[1]
        state_file = Path(TEST_DATA_DIR) / "iperf-port-test.txt"
        state_file.unlink(missing_ok=True)
        original = app.IPERF_WINDOW
        app.IPERF_WINDOW = app.IperfWindow(5201, 5, state_file)
        try:
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
            conn.request("POST", "/login", body=f"password={self.password}",
                         headers={"Content-Type": "application/x-www-form-urlencoded"})
            response = conn.getresponse()
            jar = SimpleCookie()
            jar.load(response.getheader("Set-Cookie"))
            response.read()
            def save_port(request):
                self.assertEqual(request, {"action": "iperf-port", "old_port": 5201,
                                           "port": new_port})
                state_file.write_text(str(new_port) + "\n")
                return True
            with patch.object(app.PORTFWD, "reserved_ports", return_value={5201}), \
                 patch.object(app, "node_control_apply", side_effect=save_port):
                conn.request("POST", "/iperf/port", body=f"port={new_port}",
                             headers={"Cookie": f"session={jar['session'].value}",
                                      "Content-Type": "application/x-www-form-urlencoded"})
                response = conn.getresponse()
                self.assertEqual(response.getheader("Location"), "/iperf?msg=iperf_port_saved")
                response.read()
            conn.close()
            self.assertEqual(app.IPERF_WINDOW.port, new_port)
            self.assertEqual(app.IperfWindow(5201, 5, state_file).port, new_port)
        finally:
            app.IPERF_WINDOW = original
            state_file.unlink(missing_ok=True)

    @unittest.skipUnless(shutil.which("iperf3"), "iperf3 is not installed")
    def test_open_window_offers_extend_and_close(self):
        original = app.IPERF_WINDOW
        app.IPERF_WINDOW = app.IperfWindow(port=15298, max_minutes=5)
        original_firewall = app.firewall_port
        app.firewall_port = lambda port, opening: True
        try:
            ok, key = app.IPERF_WINDOW.open(1)
            self.assertTrue(ok, key)
            body = self._page()
            self.assertIn(app.STRINGS["en"]["iperf_extend"], body)
            self.assertIn(app.STRINGS["en"]["iperf_close"], body)
            self.assertNotIn(
                f'>{app.STRINGS["en"]["iperf_open"]}</button>', body,
                "two buttons both reading 'open' is what this test exists to prevent",
            )
        finally:
            app.IPERF_WINDOW.close()
            app.IPERF_WINDOW = original
            app.firewall_port = original_firewall

    @unittest.skipUnless(shutil.which("iperf3"), "iperf3 is not installed")
    def test_open_window_carries_a_live_countdown(self):
        # A static "9m 59s left" baked in at render time and never updated —
        # reported by an operator watching the page — is what this guards
        # against: the page must ship enough for JS to tick the number down
        # itself rather than relying on a manual reload.
        original = app.IPERF_WINDOW
        app.IPERF_WINDOW = app.IperfWindow(port=15299, max_minutes=5)
        original_firewall = app.firewall_port
        app.firewall_port = lambda port, opening: True
        try:
            ok, key = app.IPERF_WINDOW.open(1)
            self.assertTrue(ok, key)
            body = self._page()
            self.assertIn("data-iperf-deadline=", body)
            self.assertIn('id="iperf-mins"', body)
            self.assertIn('id="iperf-secs"', body)
            self.assertIn("/static/iperf-countdown.js", body)
        finally:
            app.IPERF_WINDOW.close()
            app.IPERF_WINDOW = original
            app.firewall_port = original_firewall

    def test_closed_window_has_no_countdown_script(self):
        body = self._page()
        self.assertNotIn("data-iperf-deadline=", body)
        self.assertNotIn("/static/iperf-countdown.js", body)

    def test_page_offers_speed_single_and_multi_commands(self):
        body = self._page()
        port = app.IPERF_WINDOW.port
        self.assertNotIn(f"iperf3 -c 127.0.0.1 -p {port}", body)
        for field in ('cmd-speed', 'cmd-single', 'cmd-multi'):
            self.assertIn(f'data-private-field="{field}"', body)
        for key in ("iperf_cmd_speed", "iperf_cmd_single", "iperf_cmd_multi"):
            self.assertIn(app.STRINGS["en"][key], body)

    def test_revealed_commands_use_simple_stream_presets(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/login", body=f"password={self.password}",
                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        response = conn.getresponse()
        jar = SimpleCookie()
        jar.load(response.getheader("Set-Cookie"))
        response.read()
        port = app.IPERF_WINDOW.port
        for field, suffix in (("cmd-speed", ""), ("cmd-single", " -P 1"),
                              ("cmd-multi", " -P 4")):
            conn.request("GET", f"/proxy/private-value?id=iperf&field={field}",
                         headers={"Cookie": f"session={jar['session'].value}",
                                  "Host": "198.51.100.9:44816"})
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())["value"],
                             f"iperf3 -c 198.51.100.9 -p {port}{suffix}")
        conn.close()


class InstallerContractTest(unittest.TestCase):
    """install.sh and app.py have to agree on the set of settings.

    The installer carries settings across an upgrade by replaying the
    `Environment=` lines it wrote last time, and the list it writes is
    KNOWN_VARS. A variable app.py reads but KNOWN_VARS omits is therefore
    silently dropped on every upgrade: the operator sets it once, it works,
    and the next `install.sh` quietly reverts it with nothing to report.
    """

    ROOT = Path(__file__).resolve().parent.parent

    def known_vars(self):
        text = (self.ROOT / "deploy/install.sh").read_text()
        block = re.search(r'^KNOWN_VARS="(.*?)"$', text, re.S | re.M).group(1)
        return set(block.split())

    def app_vars(self):
        text = (self.ROOT / "src" / "web" / "app.py").read_text()
        return set(re.findall(r'os\.environ\.get\(\s*"(VPSSRV_[A-Z0-9_]+)"', text))

    def test_installer_knows_every_variable_app_reads(self):
        missing = self.app_vars() - self.known_vars()
        self.assertEqual(missing, set(),
                         "add these to KNOWN_VARS in install.sh or an upgrade drops them")

    def test_known_vars_are_all_real(self):
        # The other direction: a name left in KNOWN_VARS after the setting it
        # referred to was removed writes a dead Environment= line forever.
        text = (self.ROOT / "src" / "web" / "app.py").read_text()
        for var in sorted(self.known_vars()):
            with self.subTest(var=var):
                self.assertIn(var, text, f"{var} is not read anywhere in app.py")

    def test_version_file_agrees_with_latest_log_release(self):
        if not (self.ROOT / "doc" / "CHANGELOG.md").is_file():
            self.skipTest("CHANGELOG.md is omitted from the code-only test checkout")
        # The UI reads VERSION; CHANGELOG is the sole release-history source.
        # Unreleased branch work must not appear as a newer tagged release.
        version = (self.ROOT / "config/VERSION").read_text().strip()
        section = app.changelog_section((self.ROOT / "doc" / "CHANGELOG.md").read_text())
        self.assertIsNotNone(section)
        latest = re.search(r"^### (v[^ ]+) [—-] \d{4}-\d{2}-\d{2}$", section, re.M)
        self.assertIsNotNone(latest, "CHANGELOG has no dated release heading")
        self.assertEqual(f"v{version}", latest.group(1),
                         "VERSION and CHANGELOG name different latest releases")

    def test_version_is_not_a_constant_in_the_source(self):
        # webui.md §1: the displayed version must come from the real tag, so
        # that an untagged build says dev-<sha> instead of impersonating the
        # last release. A literal here is wrong the moment somebody tags and
        # forgets to edit it, with nothing to report it.
        source = (self.ROOT / "src" / "web" / "app.py").read_text()
        self.assertNotRegex(source, r'^VERSION\s*=\s*["\']',
                            "VERSION must be derived, not written in app.py")
        self.assertIn("_read_version()", source)

    def test_installed_version_stamp_takes_priority_over_bundled_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            (root / "config" / "VERSION").write_text("2.0.0\n")
            (root / "VERSION").write_text("dev-testbuild\n")
            (root / ".git").mkdir()
            with patch.object(app, "BASE_DIR", root):
                self.assertEqual(app._read_version(), "dev-testbuild")
                (root / "VERSION").unlink()
                with patch.object(app.subprocess, "run") as git:
                    git.return_value.returncode = 1
                    self.assertEqual(app._read_version(), "2.0.0")

    def test_no_documented_variable_is_ignored_by_the_code(self):
        # The other drift direction: a VPSSRV_ name in .env.example that
        # nothing reads is worse than an undocumented one, because it reads
        # like a supported setting. `VPSSRV_PREFIX` sat there for a while;
        # the installer has always taken a bare `PREFIX`, so setting the
        # documented name in .env did nothing at all.
        documented = set(re.findall(r"^(VPSSRV_[A-Z0-9_]+)=",
                                    (self.ROOT / ".env.example").read_text(), re.M))
        unused = documented - self.known_vars() - self.app_vars()
        self.assertEqual(unused, set(),
                         "documented in .env.example but read by nothing")

    def test_every_known_var_has_a_documented_default(self):
        # prompt_new_settings offers the .env.example value as the default for
        # a setting the installed version predates. A variable missing from
        # that file gets offered as "(empty)", which tells the operator
        # nothing about what they are agreeing to.
        documented = set(re.findall(r"^([A-Z][A-Z0-9_]*)=",
                                    (self.ROOT / ".env.example").read_text(), re.M))
        undocumented = self.known_vars() - documented
        self.assertEqual(undocumented, set(),
                         "these have no default in .env.example")


class StylesheetTest(unittest.TestCase):
    """Colour literals must stay inside the token blocks.

    A hex written straight into a component rule cannot follow the theme, so
    it is correct in whichever mode it was eyeballed in and wrong in the other.
    Every light-mode contrast failure found on 2026-09-12 was exactly that,
    and nothing reports it — the page just renders badly for whoever has the
    other colour scheme.
    """

    CSS = Path(__file__).resolve().parent.parent / "src/web/static" / "style.css"

    def component_rules(self):
        """style.css with the :root and light-override blocks removed."""
        text = self.CSS.read_text()
        kept, depth, skipping = [], 0, False
        for line in text.splitlines():
            if not skipping and (line.startswith(":root")
                                 or line.startswith("@media (prefers-color-scheme")):
                skipping, depth = True, 0
            if skipping:
                depth += line.count("{") - line.count("}")
                if depth <= 0:
                    skipping = False
                continue
            kept.append(line)
        return "\n".join(kept)

    def test_no_raw_hex_in_component_rules(self):
        stray = re.findall(r"#[0-9a-fA-F]{3,8}\b", self.component_rules())
        self.assertEqual(stray, [], f"use a token instead of {stray}")

    def test_every_token_used_is_defined(self):
        text = self.CSS.read_text()
        used = set(re.findall(r"var\((--[a-z0-9-]+)\)", text))
        defined = set(re.findall(r"(--[a-z0-9-]+)\s*:", text))
        self.assertEqual(used - defined, set(), "undefined custom properties")

    def _block(self, opener):
        """The body of the block introduced by `opener`, by brace depth.

        Counting braces rather than pattern-matching the closing lines: the
        first version of this test used a regex ending in "\\n}\\n}" and broke
        the moment the nested brace was indented, which says nothing about the
        stylesheet and everything about the regex.
        """
        lines = self.CSS.read_text().splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith(opener))
        depth, body = 0, []
        for line in lines[start:]:
            depth += line.count("{") - line.count("}")
            body.append(line)
            if depth == 0 and len(body) > 1:
                break
        return "\n".join(body)

    def test_accent_themes_preserve_contrast_tokens(self):
        root = self._block(":root {")
        for token in ("--bg", "--fg", "--card-bg", "--card-border", "--on-accent", "--accent"):
            self.assertIn(token + ":", root)
        for theme in ("sage", "teal", "plum"):
            block = self._block(f':root[data-theme="{theme}"]')
            self.assertIn("--accent:", block)
            self.assertIn("--accent-strong:", block)


if __name__ == "__main__":
    unittest.main()
