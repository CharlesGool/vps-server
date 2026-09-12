"""End-to-end tests for vps-server. Run with: python3 -m unittest tests/test_app.py

Starts the real Handler/ThreadingHTTPServer from app.py on an ephemeral
loopback port against a throwaway data directory, then drives it over real
HTTP connections.
"""

import atexit
import http.client
import json
import os
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

    def test_no_console_route_exists_here(self):
        # The security property this whole class exists for. These must 404
        # because ProbeHandler has no such routes — not because a check
        # rejected them. See DECISIONS.md (2026-09-12).
        for path in ("/login", "/logout", "/visitors", "/speedtest",
                     "/speedtest/garbage", "/speedtest/empty", "/speedtest/getip",
                     "/changelog", "/iperf", "/iperf/open", "/iperf/close",
                     "/static/style.css", "/speedtest_worker.js"):
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


if __name__ == "__main__":
    unittest.main()
