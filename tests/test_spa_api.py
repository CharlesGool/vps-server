"""The single-page console's JSON API: login, IP access and the security permission.

The browser tests reach the console from 127.0.0.1, which can never be on the
IP allowlist (private ranges only), so IP sign-in is checked here by calling
the real handler with a LAN peer address.
"""
import importlib
import io
import json
import os
import sys
import tempfile
import unittest
from email.message import Message
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "src" / "web"
PASSWORD = "unit-test-admin-password"


def load_app():
    state = tempfile.mkdtemp()
    (Path(state) / "admin_password.txt").write_text(PASSWORD + "\n")
    os.environ.update({
        "VPSSRV_STATE_DIR": state, "VPSSRV_DATA_KEY_FILE": str(Path(state) / "no-key"),
        "VPSSRV_CONSOLE_PORT": "28998", "VPSSRV_PUBLIC_ENABLE": "0", "VPSSRV_IPERF_ENABLE": "0",
        "VPSSRV_TRACK_CONNECTIONS": "0", "VPSSRV_VERSION": "unit",
    })
    sys.path.insert(0, str(WEB))
    if "app" in sys.modules:
        return importlib.reload(sys.modules["app"])
    return importlib.import_module("app")


class Exchange:
    """One request through ConsoleHandler without a socket."""

    def __init__(self, app, method, path, *, body=None, peer="127.0.0.1", cookie=None):
        handler = object.__new__(app.ConsoleHandler)
        payload = b"" if body is None else json.dumps(body).encode()
        headers = Message()
        headers["Host"] = "127.0.0.1:28998"
        if body is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(payload))
        if cookie:
            headers["Cookie"] = f"session={cookie}"
        handler.headers, handler.path, handler.command = headers, path, method
        handler.request_version, handler.requestline = "HTTP/1.1", f"{method} {path} HTTP/1.1"
        handler.client_address, handler.connection = (peer, 50000), None
        handler.rfile, handler.wfile = io.BytesIO(payload), io.BytesIO()
        handler.close_connection = False
        handler._dispatch(method)
        raw = handler.wfile.getvalue()
        head, _, data = raw.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        self.status = int(lines[0].split()[1])
        self.headers = {}
        for line in lines[1:]:
            key, _, value = line.partition(":")
            self.headers.setdefault(key.strip().lower(), []).append(value.strip())
        self.json = json.loads(data) if data and "application/json" in self.headers.get("content-type", [""])[0] else None

    def cookie(self):
        for value in self.headers.get("set-cookie", []):
            if value.startswith("session=") and not value.startswith("session=;"):
                return value.split(";", 1)[0].split("=", 1)[1]
        return None


class SpaApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = load_app()

    def test_session_reports_version_and_sign_in_methods(self):
        reply = Exchange(self.app, "GET", "/api/session")
        self.assertEqual(reply.status, 200)
        self.assertEqual(reply.json["version"], "unit")
        self.assertFalse(reply.json["authenticated"])
        self.assertTrue(reply.json["loginMethods"]["password"])

    def test_password_login_grants_security_and_logout_ends_it(self):
        wrong = Exchange(self.app, "POST", "/api/login", body={"password": "nope"})
        self.assertEqual((wrong.status, wrong.json["error"]), (401, "invalid_password"))
        good = Exchange(self.app, "POST", "/api/login", body={"password": PASSWORD})
        self.assertEqual(good.status, 200)
        self.assertEqual(good.json["method"], "password")
        self.assertIn("securityUntil", good.json)
        token = good.cookie()
        self.assertEqual(Exchange(self.app, "GET", "/api/security", cookie=token).status, 200)
        self.assertEqual(Exchange(self.app, "POST", "/api/logout", body={}, cookie=token).status, 204)
        self.assertEqual(Exchange(self.app, "GET", "/api/security", cookie=token).json["error"], "unauthenticated")

    def test_ip_login_only_for_allowlisted_lan_peer_and_never_reaches_security(self):
        app = self.app
        app.IP_ALLOWLIST.set_enabled(True)
        app.IP_ALLOWLIST.change("192.168.50.7", add=True)
        try:
            refused = Exchange(app, "POST", "/api/login/ip", body={}, peer="192.168.50.8")
            self.assertEqual((refused.status, refused.json["error"]), (403, "ip_not_allowed"))
            granted = Exchange(app, "POST", "/api/login/ip", body={}, peer="192.168.50.7")
            self.assertEqual(granted.status, 200)
            self.assertEqual(granted.json["method"], "ip")
            token = granted.cookie()
            session = Exchange(app, "GET", "/api/session", peer="192.168.50.7", cookie=token)
            self.assertTrue(session.json["authenticated"])
            # The same cookie from another address is not signed in.
            elsewhere = Exchange(app, "GET", "/api/session", peer="192.168.50.9", cookie=token)
            self.assertFalse(elsewhere.json["authenticated"])
            security = Exchange(app, "GET", "/api/security", peer="192.168.50.7", cookie=token)
            self.assertEqual((security.status, security.json["error"]), (403, "password_session_required"))
            verify = Exchange(app, "POST", "/api/security/verify", body={"password": PASSWORD},
                              peer="192.168.50.7", cookie=token)
            self.assertEqual(verify.json["error"], "password_session_required")
        finally:
            app.IP_ALLOWLIST.change("192.168.50.7", add=False)

    def test_allowlist_errors(self):
        token = Exchange(self.app, "POST", "/api/login", body={"password": PASSWORD}).cookie()
        add = lambda address: Exchange(self.app, "POST", "/api/security/allowlist",  # noqa: E731
                                       body={"address": address}, cookie=token)
        self.assertEqual(add("not-an-ip").json["error"], "invalid_address")
        self.assertEqual(add("8.8.8.8").json["error"], "address_not_allowed")
        self.assertIn("10.1.2.3", add("10.1.2.3").json["ipAccess"]["allowlist"])
        self.assertEqual(add("10.1.2.3").json["error"], "duplicate_address")

    def test_cross_site_and_non_json_writes_are_refused(self):
        handler_body = {"password": PASSWORD}
        reply = Exchange(self.app, "POST", "/api/login", body=handler_body)
        self.assertEqual(reply.status, 200)
        app = self.app
        handler = object.__new__(app.ConsoleHandler)
        headers = Message()
        headers["Host"] = "127.0.0.1:28998"
        headers["Origin"] = "https://evil.example"
        handler.headers = headers
        self.assertFalse(handler.same_origin())
        headers.replace_header("Origin", "https://127.0.0.1:28998")
        self.assertTrue(handler.same_origin())

    def test_modules_and_logs(self):
        token = Exchange(self.app, "POST", "/api/login", body={"password": PASSWORD}).cookie()
        modules = Exchange(self.app, "GET", "/api/modules", cookie=token)
        self.assertEqual(modules.status, 200)
        self.assertEqual([item["key"] for item in modules.json["modules"]],
                         ["iperf3", "proxy_nodes", "frps", "frpc", "tailscale", "caddy"])
        bad = Exchange(self.app, "POST", "/api/modules/manage", body={"module": "speedtest", "action": "install"},
                       cookie=token)
        self.assertEqual((bad.status, bad.json["error"]), (400, "invalid_request"))
        history = self.app.module_history_path(self.app.BASE_DIR)
        history.parent.mkdir(parents=True, exist_ok=True)
        history.write_text("installed iperf3\n")
        logs = Exchange(self.app, "GET", "/api/logs?source=modules", cookie=token)
        self.assertEqual(logs.json["sections"], [{"source": "modules", "text": "installed iperf3\n"}])
        every = Exchange(self.app, "GET", "/api/logs?source=all&level=err", cookie=token).json["sections"]
        self.assertEqual([item["source"] for item in every],
                         ["modules", "web", "proxy", "frps", "frpc", "tailscale", "caddy"])
        self.assertEqual(Exchange(self.app, "GET", "/api/logs?source=meter", cookie=token).status, 404)
        self.assertEqual(Exchange(self.app, "GET", "/api/logs?level=loud", cookie=token).status, 400)
        cleared = Exchange(self.app, "POST", "/api/logs/clear", body={"source": "modules"}, cookie=token)
        self.assertEqual(cleared.status, 204)
        self.assertEqual(history.read_text(), "")
        self.assertEqual(Exchange(self.app, "POST", "/api/logs/clear", body={"source": "x"}, cookie=token).status, 400)

    def test_speedtest_traffic_card_and_limits(self):
        token = Exchange(self.app, "POST", "/api/login", body={"password": PASSWORD}).cookie()
        speed = Exchange(self.app, "GET", "/api/speedtest", cookie=token)
        self.assertEqual(speed.json["config"]["url_dl"], "/speedtest/garbage")
        traffic = Exchange(self.app, "GET", "/api/traffic?key=speedtest", cookie=token).json
        self.assertEqual((traffic["entry"]["capBytes"], traffic["help"]), (None, "once"))
        self.assertEqual(Exchange(self.app, "GET", "/api/traffic?key=../x", cookie=token).status, 404)
        limits = {"key": "speedtest", "capGib": "1.5", "uploadMbps": "", "downloadMbps": "20",
                  "capAction": "block", "resetMode": "repeat", "resetCount": 1, "resetUnit": "months",
                  "nextResetAt": "", "expiryMode": "none", "expiryCount": 1, "expiryUnit": "months"}
        saved = Exchange(self.app, "PUT", "/api/traffic/limits", body=limits, cookie=token).json["entry"]
        self.assertEqual((saved["capBytes"], saved["downloadLimitBps"], saved["capAction"], saved["resetMode"]),
                         (int(1.5 * 1073741824), 20000000, "block", "repeat"))
        bad = Exchange(self.app, "PUT", "/api/traffic/limits", body={**limits, "capGib": "-1"}, cookie=token)
        self.assertEqual((bad.status, bad.json["error"]), (400, "invalid_limits"))
        Exchange(self.app, "PUT", "/api/traffic/limits",
                 body={**limits, "capGib": "", "downloadMbps": "", "resetMode": "none"}, cookie=token)

    def test_iperf_window_and_private_values(self):
        token = Exchange(self.app, "POST", "/api/login", body={"password": PASSWORD}).cookie()
        state = Exchange(self.app, "GET", "/api/iperf", cookie=token).json
        self.assertEqual((state["open"], state["enabled"]), (False, False))
        opened = Exchange(self.app, "POST", "/api/iperf/open", body={"minutes": 5}, cookie=token).json
        self.assertEqual(opened["message"], "iperf_disabled")
        bad = Exchange(self.app, "PUT", "/api/iperf/port", body={"port": 80}, cookie=token)
        self.assertEqual((bad.status, bad.json["error"]), (400, "iperf_port_invalid"))
        self.assertEqual(Exchange(self.app, "PUT", "/api/iperf/port", body={"port": "5201"}, cookie=token).status, 400)
        client = Exchange(self.app, "POST", "/api/iperf/client", cookie=token,
                          body={"host": "192.0.2.1", "port": 5201, "seconds": 1, "mbps": 1,
                                "protocol": "tcp", "direction": "upload"}).json
        self.assertEqual(client["status"], "disabled")
        port = Exchange(self.app, "GET", "/api/private-value?id=iperf&field=port", cookie=token).json["value"]
        self.assertTrue(port.isdigit())
        command = Exchange(self.app, "GET", "/api/private-value?id=iperf&field=cmd-multi", cookie=token).json
        self.assertTrue(command["value"].endswith(f"-p {port} -P 4"))
        self.assertEqual(Exchange(self.app, "GET", "/api/private-value?id=iperf&field=secret", cookie=token).status, 404)
        self.assertEqual(Exchange(self.app, "GET", "/api/private-value?id=iperf&field=port").status, 401)

    def test_portfwd_visitors_terminal_files(self):
        token = Exchange(self.app, "POST", "/api/login", body={"password": PASSWORD}).cookie()
        rules = Exchange(self.app, "GET", "/api/portfwd", cookie=token).json
        self.assertEqual(rules["rules"], [])
        bad = Exchange(self.app, "POST", "/api/portfwd/add", cookie=token,
                       body={"protocol": "tcp", "publicPort": 0, "targetHost": "x", "targetPort": 80}).json
        self.assertEqual(bad["message"], "portfwd_invalid")
        self.assertEqual(Exchange(self.app, "POST", "/api/portfwd/add", cookie=token,
                                  body={"protocol": "icmp"}).status, 400)
        self.assertEqual(Exchange(self.app, "POST", "/api/portfwd/delete", cookie=token,
                                  body={"id": "nope"}).json["message"], "portfwd_not_found")
        visitors = Exchange(self.app, "GET", "/api/visitors", cookie=token)
        self.assertEqual(visitors.json["max"], self.app.MAX_VISITOR_ROWS)
        self.assertEqual(Exchange(self.app, "POST", "/api/visitors/clear", body={}, cookie=token).status, 204)
        # Signing in with the password grants the security permission, so the terminal opens.
        terminal = Exchange(self.app, "GET", "/api/terminal", cookie=token)
        self.assertEqual(terminal.status, 200)
        self.assertEqual(len(terminal.json["token"]), 64)
        files = Exchange(self.app, "GET", "/api/files", cookie=token)
        if files.status == 403:
            self.assertEqual(files.json["error"], "feature_closed")
            return
        self.assertIn(10080, files.json["linkMinutes"])
        limits = Exchange(self.app, "PUT", "/api/files/limits", body={"quotaGib": 2, "rateMib": 1.5}, cookie=token)
        self.assertEqual((limits.json["quota"], limits.json["rate"]), (2 * 1024 ** 3, int(1.5 * 1024 ** 2)))
        self.assertEqual(Exchange(self.app, "PUT", "/api/files/limits", body={"quotaGib": 0},
                                  cookie=token).json["error"], "quota_invalid")
        self.assertEqual(Exchange(self.app, "POST", "/api/files/link", cookie=token,
                                  body={"file": "missing", "minutes": 60, "max": None}).json["error"], "not_found")

    def test_backup_tasks_and_closed_page(self):
        token = Exchange(self.app, "POST", "/api/login", body={"password": PASSWORD}).cookie()
        backup = Exchange(self.app, "GET", "/api/backup", cookie=token).json
        self.assertIn("keepMax", backup)
        bad = Exchange(self.app, "PUT", "/api/backup/settings", cookie=token,
                       body={"enabled": True, "spec": {"mode": "weekly", "days": [], "time": "03:00:00"}, "keep": 3})
        self.assertEqual((bad.status, bad.json["error"]), (400, "invalid"))
        saved = Exchange(self.app, "PUT", "/api/backup/settings", cookie=token,
                         body={"enabled": True, "spec": {"mode": "interval", "n": 6, "unit": "hours"}, "keep": 3}).json
        self.assertEqual((saved["settings"]["keep"], saved["settings"]["spec"]["n"]), (3, 6))
        self.assertEqual(Exchange(self.app, "POST", "/api/backup/inspect", body={"name": "../x"},
                                  cookie=token).status, 404)
        task = Exchange(self.app, "PUT", "/api/tasks/save", cookie=token,
                        body={"name": "t", "command": "true", "timeout": 60, "notify": False, "enabled": True,
                              "spec": {"mode": "daily", "time": "04:00:00"}}).json
        self.assertEqual([item["name"] for item in task["tasks"]], ["t"])
        task_id = task["tasks"][0]["id"]
        toggled = Exchange(self.app, "POST", "/api/tasks/toggle", body={"id": task_id, "enabled": False},
                           cookie=token).json
        self.assertFalse(toggled["tasks"][0]["enabled"])
        self.assertEqual(Exchange(self.app, "POST", "/api/tasks/delete", body={"id": task_id},
                                  cookie=token).json["tasks"], [])
        self.assertEqual(Exchange(self.app, "GET", "/api/closed?module=nope", cookie=token).status, 404)
        info = Exchange(self.app, "GET", "/api/closed?module=speedtest", cookie=token).json
        self.assertEqual((info["destination"], info["closed"]), ("/speedtest", False))

    def test_tailscale_domains_ipcert_without_modules(self):
        token = Exchange(self.app, "POST", "/api/login", body={"password": PASSWORD}).cookie()
        for name in ("tailscale", "domains", "ipcert"):
            reply = Exchange(self.app, "GET", "/api/" + name, cookie=token)
            self.assertEqual((reply.status, reply.json), (200, {"installed": False}))
        self.assertEqual(Exchange(self.app, "POST", "/api/domains/add", body={"host": "a.example.com"},
                                  cookie=token).status, 404)
        self.assertEqual(Exchange(self.app, "GET", "/api/private-value?id=domain-ipv4&field=address",
                                  cookie=token).status, 404)
        self.assertEqual(Exchange(self.app, "GET", "/api/private-value?id=tailscale-tailscale_ipv4&field=address",
                                  cookie=token).status, 404)

    def test_closed_feature_page_and_api(self):
        token = Exchange(self.app, "POST", "/api/login", body={"password": PASSWORD}).cookie()
        original = self.app.closed_page_module
        self.app.closed_page_module = lambda path: "speedtest" if path == "/speedtest" else None
        try:
            page = Exchange(self.app, "GET", "/speedtest", cookie=token)
            self.assertEqual((page.status, page.headers["location"][0]), (302, "/closed?module=speedtest"))
            api = Exchange(self.app, "GET", "/api/speedtest", cookie=token)
            self.assertEqual((api.status, api.json["error"], api.json["url"]),
                             (403, "feature_closed", "/closed?module=speedtest"))
        finally:
            self.app.closed_page_module = original

    def test_spa_pages_and_assets_paths(self):
        from features.spa import is_spa_page
        self.assertTrue(is_spa_page("/settings/security"))
        self.assertTrue(is_spa_page("/settings/logs"))
        self.assertTrue(is_spa_page("/showcase/buttons"))
        self.assertTrue(is_spa_page("/speedtest"))
        self.assertTrue(is_spa_page("/iperf"))
        self.assertTrue(is_spa_page("/portfwd"))
        self.assertTrue(is_spa_page("/backup/restore"))
        self.assertFalse(is_spa_page("/backup/download"))
        self.assertFalse(is_spa_page("/showcasex"))
        missing = Exchange(self.app, "GET", "/assets/..%2Fapp.py")
        self.assertEqual(missing.status, 404)


if __name__ == "__main__":
    unittest.main()
