"""Admin re-verification for scheduled tasks and backups, the session's version, and the route table.

Scheduled tasks run commands as root and backups hold every secret of the console, so
like the other pages that act on the host (system, processes, file manager, fleet) every
route needs a password session that re-entered the admin password recently. A session
signed in with a certificate only, or an IP session, gets the same refusal those pages give.
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

TASK_AND_BACKUP_ROUTES = [
    ("GET", "tasks"), ("PUT", "tasks/save"), ("POST", "tasks/toggle"), ("POST", "tasks/delete"),
    ("POST", "tasks/run"),
    ("GET", "backup"), ("POST", "backup/create"), ("PUT", "backup/settings"), ("POST", "backup/delete"),
    ("POST", "backup/upload"), ("POST", "backup/inspect"), ("POST", "backup/restore"),
    ("POST", "backup/key/new"), ("PUT", "backup/key"),
]


def load_app():
    state = tempfile.mkdtemp()
    (Path(state) / "admin_password.txt").write_text(PASSWORD + "\n")
    os.environ.update({
        "VPSSRV_STATE_DIR": state, "VPSSRV_DATA_KEY_FILE": str(Path(state) / "no-key"),
        "VPSSRV_CONSOLE_PORT": "28997", "VPSSRV_PUBLIC_ENABLE": "0", "VPSSRV_IPERF_ENABLE": "0",
        "VPSSRV_TRACK_CONNECTIONS": "0", "VPSSRV_VERSION": "unit",
    })
    if str(WEB) not in sys.path:
        sys.path.insert(0, str(WEB))
    if "app" in sys.modules:
        return importlib.reload(sys.modules["app"])
    return importlib.import_module("app")


def request(app, method, path, *, body=None, peer="127.0.0.1", cookie=None):
    """One request through ConsoleHandler without a socket: (status, JSON body or None)."""
    handler = object.__new__(app.ConsoleHandler)
    payload = b"" if body is None else json.dumps(body).encode()
    headers = Message()
    headers["Host"] = "127.0.0.1:28997"
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
    head, _, data = handler.wfile.getvalue().partition(b"\r\n\r\n")
    status = int(head.split(b"\r\n", 1)[0].split()[1])
    json_body = b"application/json" in head.lower() and data
    return status, json.loads(data) if json_body else None


class SecureRoutesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = load_app()

    def ip_session(self):
        """An IP sign-in for an allowlisted LAN address; the allowlist entry is removed after the test."""
        app = self.app
        app.IP_ALLOWLIST.set_enabled(True)
        app.IP_ALLOWLIST.change("192.168.50.7", add=True)
        self.addCleanup(app.IP_ALLOWLIST.change, "192.168.50.7", add=False)
        return app.create_ip_session("192.168.50.7")

    def certificate_session(self):
        # What a certificate sign-in creates: a session that never re-entered the password.
        return self.app.create_session(security_verified=False, ip="127.0.0.1", method="certificate")

    def test_routes_of_tasks_and_backups_are_secure_features(self):
        from features.spa import SECURE_FEATURES, feature_of
        routes = self.app.ConsoleHandler.private_api_routes()
        for key in TASK_AND_BACKUP_ROUTES:
            with self.subTest(route=key):
                self.assertIn(key, routes)
                self.assertIn(feature_of(key[1]), SECURE_FEATURES)
        # Every route of these features is listed above, so none is left unchecked.
        listed = {key for key in routes if feature_of(key[1]) in ("tasks", "backup")}
        self.assertEqual(listed, set(TASK_AND_BACKUP_ROUTES))
        self.assertNotIn("monitor", SECURE_FEATURES)

    def test_unverified_session_gets_the_refusal_other_secure_pages_give(self):
        token = self.certificate_session()
        reference = request(self.app, "GET", "/api/system/processes", cookie=token)
        self.assertEqual(reference, (403, {"error": "security_required"}))
        for method, name in TASK_AND_BACKUP_ROUTES:
            with self.subTest(route=(method, name)):
                self.assertEqual(request(self.app, method, "/api/" + name, body={}, cookie=token), reference)

    def test_ip_session_gets_the_refusal_other_secure_pages_give(self):
        app = self.app
        token = self.ip_session()
        reference = request(app, "GET", "/api/fleet", peer="192.168.50.7", cookie=token)
        self.assertEqual(reference, (403, {"error": "password_session_required"}))
        for method, name in TASK_AND_BACKUP_ROUTES:
            with self.subTest(route=(method, name)):
                self.assertEqual(request(app, method, "/api/" + name, body={}, peer="192.168.50.7", cookie=token),
                                 reference)

    def test_refused_task_save_changes_nothing(self):
        token = self.certificate_session()
        task = {"name": "x", "command": "id", "timeout": 60, "notify": False, "enabled": True,
                "spec": {"mode": "daily", "time": "04:00:00"}}
        before = [item["id"] for item in self.app.SCHEDULER.tasks()]
        self.assertEqual(request(self.app, "PUT", "/api/tasks/save", body=task, cookie=token)[0], 403)
        self.assertEqual([item["id"] for item in self.app.SCHEDULER.tasks()], before)

    def test_verified_session_still_reaches_tasks_and_backups(self):
        # What a password sign-in (or a later re-verification) creates.
        cookie = self.app.create_session(security_verified=True, ip="127.0.0.1", method="password")
        self.assertEqual(request(self.app, "GET", "/api/tasks", cookie=cookie)[0], 200)
        self.assertEqual(request(self.app, "GET", "/api/backup", cookie=cookie)[0], 200)
        # A verified session passes the check; the backup itself does not exist.
        self.assertEqual(request(self.app, "GET", "/backup/download?name=nope.tar.gz", cookie=cookie)[0], 404)

    def test_backup_download_needs_verification(self):
        token = self.certificate_session()
        self.assertEqual(request(self.app, "GET", "/backup/download?name=nope.tar.gz", cookie=token),
                         (403, {"error": "security_required"}))
        ip_token = self.ip_session()
        self.assertEqual(request(self.app, "GET", "/backup/download?name=nope.tar.gz", peer="192.168.50.7",
                                 cookie=ip_token), (403, {"error": "password_session_required"}))


class RouteTableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = load_app()

    def test_console_routes_have_no_duplicates(self):
        routes = self.app.ConsoleHandler.private_api_routes()
        self.assertEqual(routes[("POST", "security/verify")], "api_security_verify")
        self.assertEqual(routes[("PUT", "tasks/save")], "api_tasks_save")

    def test_a_route_claimed_twice_raises(self):
        from features.spa import SpaMixin

        class First:
            API_ROUTES_FIRST = {("GET", "thing"): "api_first"}

        class Second:
            API_ROUTES_SECOND = {("GET", "thing"): "api_second"}

        class Handler(SpaMixin, First, Second):
            pass

        with self.assertRaisesRegex(RuntimeError, "GET thing"):
            Handler.private_api_routes()

    def test_a_table_name_two_mixins_share_raises(self):
        from features.spa import SpaMixin

        class First:
            API_ROUTES_SAME = {("GET", "one"): "api_one"}

        class Second:
            API_ROUTES_SAME = {("GET", "two"): "api_two"}

        class Handler(SpaMixin, First, Second):
            pass

        with self.assertRaisesRegex(RuntimeError, "API_ROUTES_SAME"):
            Handler.private_api_routes()


if __name__ == "__main__":
    unittest.main()
