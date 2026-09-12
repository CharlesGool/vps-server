"""End-to-end tests for vps-server. Run with: python3 -m unittest tests/test_app.py

Starts the real Handler/ThreadingHTTPServer from app.py on an ephemeral
loopback port against a throwaway data directory, then drives it over real
HTTP connections.
"""

import atexit
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
from pathlib import Path

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
import app  # noqa: E402  (import must follow env setup above)


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

    def test_nav_shows_all_three_language_links(self):
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/", headers={"Cookie": f"session={session}"})
        body = conn.getresponse().read().decode()
        conn.close()
        self.assertIn("?lang=en", body)
        self.assertIn("?lang=zh_cn", body)
        self.assertIn("?lang=zh_tw", body)

    # -- speed test ----------------------------------------------------
    # Endpoints match LibreSpeed's own garbage.php/empty.php/getIP.php
    # contract exactly (see DECISIONS.md, 2026-08-25) so the vendored
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
        self.assertIn(f"v{app.VERSION}", body)
        conn.close()

    def test_changelog_page_renders_current_version_section(self):
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/changelog", headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        body = resp.read().decode()
        self.assertIn(f"v{app.VERSION}", body)
        self.assertIn("<h2>", body, "changelog headings were not rendered")
        conn.close()

    def test_changelog_follows_language_toggle(self):
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/changelog?lang=zh_cn", headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        body = resp.read().decode()
        conn.close()
        # Discriminate on prose, not on headings: this project's translation
        # convention keeps the section headings (Added / Changed / Fixed) in
        # English in every language, because release-preflight.sh and the
        # GitHub release notes both key off the English file's structure.
        # An "English headings are absent" check would therefore never pass.
        self.assertIn("尚未发布", body)
        self.assertNotIn("Nothing has shipped yet", body)

    def test_changelog_traditional_chinese(self):
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/changelog?lang=zh_tw", headers={"Cookie": f"session={session}"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        body = resp.read().decode()
        conn.close()
        self.assertIn("<h2>", body, "zh_tw changelog headings were not rendered")
        self.assertIn("尚未發布", body)
        self.assertNotIn("Nothing has shipped yet", body)

    def test_changelog_fallback_notice_when_translation_missing(self):
        session = self.login()
        original = app.CHANGELOG_PATHS["zh_cn"]
        app.CHANGELOG_PATHS["zh_cn"] = Path("/nonexistent/CHANGELOG_zh_cn.md")
        try:
            conn = self.connect()
            conn.request("GET", "/changelog?lang=zh_cn", headers={"Cookie": f"session={session}"})
            resp = conn.getresponse()
            body = resp.read().decode()
            conn.close()
            self.assertIn("Nothing has shipped yet", body)  # fell back to English
            self.assertIn(app.STRINGS["zh_cn"]["changelog_fallback"], body)
        finally:
            app.CHANGELOG_PATHS["zh_cn"] = original

    def test_changelog_english_by_default(self):
        session = self.login()
        conn = self.connect()
        conn.request("GET", "/changelog?lang=en", headers={"Cookie": f"session={session}"})
        body = conn.getresponse().read().decode()
        conn.close()
        self.assertIn("Nothing has shipped yet", body)

    def test_changelog_requires_login(self):
        conn = self.connect()
        conn.request("GET", "/changelog")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 302)
        resp.read()
        conn.close()

    def test_changelog_markdown_is_escaped_not_injected(self):
        # CHANGELOG.md is author-controlled, but rendering must still escape:
        # a stray tag in a release note should not become live markup.
        # Content only renders from the first "## " heading onwards.
        out = app.render_changelog(
            "## v1.0.0\n- oops <script>alert(1)</script> and `code`"
        )
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertIn("<code>code</code>", out)

    def test_changelog_renders_headings_and_bullets(self):
        out = app.render_changelog("## v1.0.0\n\n### Added\n- thing **bold**\n")
        self.assertIn("<h2>v1.0.0</h2>", out)
        self.assertIn("<h3>Added</h3>", out)
        self.assertIn("<li>thing <strong>bold</strong>", out)
        # Tags must balance, or the page layout breaks.
        self.assertEqual(out.count("<li>"), out.count("</li>"))
        self.assertEqual(out.count("<ul>"), out.count("</ul>"))

    def test_changelog_skips_maintainer_preamble(self):
        out = app.render_changelog(
            "# Changelog\n\nNotes for maintainers only.\n\n## v1.0.0\n- real change\n"
        )
        self.assertNotIn("maintainers", out)
        self.assertIn("real change", out)


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
        # whether port 80 itself answers. See DECISIONS.md (2026-09-12).
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
                [sys.executable, "-c", f"import app; print({expression})"],
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
        # rejected them. See DECISIONS.md (2026-09-12).
        for path in ("/login", "/logout", "/visitors", "/speedtest",
                     "/speedtest/garbage", "/speedtest/empty", "/speedtest/getip",
                     "/changelog", "/iperf", "/iperf/open", "/iperf/close",
                     "/anytls", "/anytls/reset", "/static/style.css", "/static/copy.js",
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

    def test_page_shows_both_copyable_forms(self):
        resp, body = self.get("/anytls")
        self.assertEqual(resp.status, 200)
        self.assertIn('id="anytls-clash-0"', body)
        self.assertIn('id="anytls-link-0"', body)
        self.assertIn("/static/copy.js", body)

    def test_page_shows_port_password_and_sni_as_fields(self):
        # The operator asked for the same three facts the installer prints,
        # readable without picking them out of the Clash line.
        _, body = self.get("/anytls")
        for key in ("anytls_port", "anytls_password", "anytls_sni"):
            self.assertIn(app.STRINGS["en"][key], body)
        self.assertIn('id="anytls-pw"', body, "the password needs its own copy button")
        self.assertIn("27999", body)
        self.assertIn(self.FAKE_PASSWORD, body)

    def test_one_configuration_block_per_address(self):
        _, body = self.get("/anytls")
        # Whatever this host's interfaces are, every listed address gets its
        # own Clash entry and link rather than one block for a single guess.
        blocks = body.count('class="node-addr"')
        self.assertGreaterEqual(blocks, 1)
        self.assertEqual(body.count('id="anytls-clash-'), blocks)
        self.assertEqual(body.count('id="anytls-link-'), blocks)

    def test_public_address_comes_from_the_file_not_a_lookup(self):
        public_file = self.config.parent / "public-ip.txt"
        public_file.write_text("198.51.100.7\n")
        try:
            self.assertEqual(app.anytls_public_address(), "198.51.100.7")
            _, body = self.get("/anytls")
            self.assertIn("198.51.100.7", body)
            self.assertIn(app.STRINGS["en"]["anytls_public"], body)
        finally:
            public_file.unlink()

    def test_public_address_ignores_the_detection_failure_placeholder(self):
        # get_ip() falls back to a human-readable sentence when the lookup
        # fails; rendering that as an address would be worse than omitting it.
        public_file = self.config.parent / "public-ip.txt"
        public_file.write_text("<自动获取失败，请手动替换为服务器公网IP>\n")
        try:
            self.assertEqual(app.anytls_public_address(), "")
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
        _, body = self.get("/anytls")
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
                             "/anytls?msg=anytls_reset_unconfirmed")
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
                             "/anytls?msg=anytls_reset_done")
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
                                     "/anytls?msg=anytls_reset_unconfirmed")
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
        _, body = self.get("/anytls?msg=anytls_warning")
        self.assertNotIn('class="notice"', body)
        _, body = self.get("/anytls?msg=anytls_reset_done")
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
            _, body = self.get("/anytls")
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
            _, body = self.get("/anytls")
            self.assertIn("is-open", body)
        finally:
            app._run_quiet = original

    def test_nav_and_dashboard_offer_the_page_only_when_installed(self):
        _, body = self.get("/")
        self.assertIn('href="/anytls"', body)

        app.ANYTLS_CONFIG = Path("/nonexistent/config.json")
        _, body = self.get("/")
        self.assertNotIn('href="/anytls"', body,
                         "a link that can only say 'not installed' is worse than none")

    def test_page_is_graceful_when_not_installed(self):
        app.ANYTLS_CONFIG = Path("/nonexistent/config.json")
        resp, body = self.get("/anytls")
        self.assertEqual(resp.status, 200)
        self.assertNotIn(self.FAKE_PASSWORD, body)


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
        text = (self.ROOT / "install.sh").read_text()
        block = re.search(r'^KNOWN_VARS="(.*?)"$', text, re.S | re.M).group(1)
        return set(block.split())

    def app_vars(self):
        text = (self.ROOT / "app.py").read_text()
        return set(re.findall(r'os\.environ\.get\(\s*"(VPSSRV_[A-Z0-9_]+)"', text))

    def test_installer_knows_every_variable_app_reads(self):
        missing = self.app_vars() - self.known_vars()
        self.assertEqual(missing, set(),
                         "add these to KNOWN_VARS in install.sh or an upgrade drops them")

    def test_known_vars_are_all_real(self):
        # The other direction: a name left in KNOWN_VARS after the setting it
        # referred to was removed writes a dead Environment= line forever.
        text = (self.ROOT / "app.py").read_text()
        for var in sorted(self.known_vars()):
            with self.subTest(var=var):
                self.assertIn(var, text, f"{var} is not read anywhere in app.py")

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

    CSS = Path(__file__).resolve().parent.parent / "static" / "style.css"

    def component_rules(self):
        """style.css with the :root and light-override blocks removed."""
        text = self.CSS.read_text()
        kept, depth, skipping = [], 0, False
        for line in text.splitlines():
            if not skipping and (line.startswith(":root {")
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
        defined = set(re.findall(r"^\s*(--[a-z0-9-]+)\s*:", text, re.M))
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

    def test_light_mode_overrides_every_colour_token(self):
        # A token defined only in :root silently keeps its dark value on a
        # light background. Tokens built out of other tokens legitimately
        # carry over; flat colours must not.
        root = self._block(":root {")
        light = self._block("@media (prefers-color-scheme: light)")
        flat = set(re.findall(r"^\s*(--[a-z0-9-]+)\s*:\s*#", root, re.M))
        overridden = set(re.findall(r"^\s*(--[a-z0-9-]+)\s*:", light, re.M))
        self.assertEqual(flat - overridden, set(),
                         "these flat colours have no light-mode value")


if __name__ == "__main__":
    unittest.main()
