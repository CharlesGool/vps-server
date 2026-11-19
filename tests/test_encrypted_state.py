"""The console's state classes with encryption on: nothing readable on disk, nothing lost on reload."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import console_access  # noqa: E402
import file_share  # noqa: E402
import scheduler  # noqa: E402
import secure_store as ss  # noqa: E402
import security_events as se  # noqa: E402


class EncryptedStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ["VPSSRV_DATA_KEY_FILE"] = str(self.tmp / "etc" / "data.key")
        os.environ["VPSSRV_STATE_DIR"] = str(self.tmp / "state")
        ss._cache.clear()
        self.data = self.tmp / "data"
        self.data.mkdir()

    def tearDown(self):
        os.environ.pop("VPSSRV_DATA_KEY_FILE", None)
        os.environ.pop("VPSSRV_STATE_DIR", None)
        ss._cache.clear()

    def encrypted(self, path):
        return Path(path).read_bytes().startswith(ss.MAGIC)

    def test_audit_log_records_ips_encrypted_and_reads_back(self):
        ss.init_key()
        log = se.AuditLog(self.data / "security-audit.jsonl")
        log.record("login_ok", "203.0.113.7", "password")
        log.record("login_fail", "198.51.100.2")
        raw = (self.data / "security-audit.jsonl").read_text()
        self.assertNotIn("203.0.113.7", raw)
        self.assertNotIn("login_ok", raw)
        events = se.AuditLog(self.data / "security-audit.jsonl").recent()
        self.assertEqual([e["event"] for e in events], ["login_fail", "login_ok"])
        self.assertEqual(events[1]["ip"], "203.0.113.7")

    def test_audit_log_trimming_keeps_the_newest_encrypted_records(self):
        ss.init_key()
        log = se.AuditLog(self.data / "security-audit.jsonl", limit=20)
        for i in range(120):
            log.record("event", "192.0.2.1", str(i))
        lines = (self.data / "security-audit.jsonl").read_text().splitlines()
        self.assertLess(len(lines), 120)
        self.assertTrue(all(l.startswith(ss.LINE_PREFIX) for l in lines))
        self.assertEqual(log.recent(1)[0]["detail"], "119")

    def test_audit_log_mixes_old_plain_and_new_encrypted_lines(self):
        path = self.data / "security-audit.jsonl"
        path.write_text('{"t": 1, "event": "old", "ip": "", "detail": ""}\n')
        ss.init_key()
        log = se.AuditLog(path)
        log.record("new")
        self.assertEqual([e["event"] for e in log.recent()], ["new", "old"])

    def test_audit_log_skips_records_it_cannot_open(self):
        ss.init_key()
        log = se.AuditLog(self.data / "security-audit.jsonl")
        log.record("kept")
        (self.data / "security-audit.jsonl").write_text(
            (self.data / "security-audit.jsonl").read_text() + ss.LINE_PREFIX + "AAAA\n")
        self.assertEqual([e["event"] for e in log.recent()], ["kept"])

    def test_known_logins_and_alert_settings_round_trip(self):
        ss.init_key()
        known = se.KnownLogins(self.data / "known-logins.json")
        known.remember("203.0.113.0")
        self.assertTrue(self.encrypted(self.data / "known-logins.json"))
        self.assertTrue(se.KnownLogins(self.data / "known-logins.json").is_known("203.0.113.0"))
        alerts = se.BarkAlerts(self.data / "alerts.json")
        alerts.update(server="https://api.day.app", key="SECRETKEY123", new_ip=True, ban=False)
        raw = (self.data / "alerts.json").read_bytes()
        self.assertNotIn(b"SECRETKEY123", raw)
        again = se.BarkAlerts(self.data / "alerts.json")
        self.assertTrue(again.configured())
        self.assertFalse(again.load_error)

    def test_old_plain_alert_settings_still_load_and_are_encrypted_on_next_save(self):
        path = self.data / "alerts.json"
        path.write_text('{"server": "https://api.day.app", "key": "OLDKEY", "new_ip": true, "ban": true}\n')
        ss.init_key()
        alerts = se.BarkAlerts(path)
        self.assertTrue(alerts.configured())
        alerts.update(server="https://api.day.app", key="", new_ip=False, ban=True)
        self.assertTrue(self.encrypted(path))

    def test_several_bark_keys_are_kept_masked_and_removable(self):
        ss.init_key()
        path = self.data / "alerts.json"
        path.write_text('{"server": "https://api.day.app", "key": "OLDKEY123456789", "new_ip": true, "ban": true}\n')
        alerts = se.BarkAlerts(path)
        self.assertEqual([item["masked"] for item in alerts.settings()["keys"]], ["OLDK****6789"])
        self.assertTrue(alerts.add_key("SECOND_KEY_abcd"))
        self.assertFalse(alerts.add_key("SECOND_KEY_abcd"))               # the same key twice is one key
        with self.assertRaises(ValueError):
            alerts.add_key("not a key!")
        again = se.BarkAlerts(path)
        self.assertEqual([item["masked"] for item in again.settings()["keys"]], ["OLDK****6789", "SECO****abcd"])
        self.assertNotIn(b"SECOND_KEY_abcd", path.read_bytes())
        sent = []
        again._post = lambda server, key, title, body: sent.append(key)
        self.assertIsNone(again.send_test("t", "b"))
        self.assertEqual(sent, ["OLDKEY123456789", "SECOND_KEY_abcd"])
        first = again.settings()["keys"][0]["id"]
        self.assertTrue(again.remove_key(first))
        self.assertFalse(again.remove_key(first))
        self.assertEqual([item["masked"] for item in se.BarkAlerts(path).settings()["keys"]], ["SECO****abcd"])
        self.assertEqual(se.BarkAlerts.masked("short"), "sh****")

    def test_an_undecryptable_alerts_file_is_reported_not_replaced(self):
        ss.init_key()
        path = self.data / "alerts.json"
        se.BarkAlerts(path).update(server="https://api.day.app", key="K1", new_ip=True, ban=True)
        before = path.read_bytes()
        (self.tmp / "etc" / "data.key").write_text(os.urandom(32).hex() + "\n")
        ss._cache.clear()
        broken = se.BarkAlerts(path)
        self.assertTrue(broken.load_error)
        self.assertFalse(broken.configured())
        self.assertEqual(path.read_bytes(), before)

    def test_console_access_list_is_encrypted_and_fails_open_when_unreadable(self):
        ss.init_key()
        path = self.data / "console-access.json"
        access = console_access.ConsoleAccess(path)
        access.add("203.0.113.0/24")
        self.assertTrue(self.encrypted(path))
        self.assertNotIn(b"203.0.113", path.read_bytes())
        self.assertEqual(console_access.ConsoleAccess(path).networks(), ["203.0.113.0/24"])
        (self.tmp / "etc" / "data.key").write_text(os.urandom(32).hex() + "\n")
        ss._cache.clear()
        broken = console_access.ConsoleAccess(path)
        self.assertTrue(broken.allows("198.51.100.9"))            # a damaged list never locks everyone out
        self.assertTrue(broken.load_error)

    def test_file_index_and_scheduled_tasks_are_encrypted(self):
        ss.init_key()
        store = file_share.FileStore(self.data / "files")
        store.set_quota(5 * 1024 ** 3)
        self.assertTrue(self.encrypted(self.data / "files" / "index.json"))
        self.assertEqual(file_share.FileStore(self.data / "files").state()["quota"], 5 * 1024 ** 3)
        engine = scheduler.Scheduler(self.data, backup_action=lambda keep: "x")
        engine.add_task("nightly", {"mode": "daily", "time": "03:00"}, "curl -H 'Authorization: Bearer TOPSECRET' x")
        raw = (self.data / "scheduled-tasks.json").read_bytes()
        self.assertTrue(raw.startswith(ss.MAGIC))
        self.assertNotIn(b"TOPSECRET", raw)
        self.assertEqual(scheduler.Scheduler(self.data, backup_action=lambda keep: "x").tasks()[0]["name"], "nightly")

    def test_migrate_turns_a_whole_old_install_encrypted(self):
        (self.tmp / "state").mkdir()
        (self.tmp / "state" / "admin_password.txt").write_text("oldpassword123\n")
        (self.tmp / "state" / "data").mkdir()
        data = self.tmp / "state" / "data"
        (data / "alerts.json").write_text('{"server": "https://api.day.app", "key": "", "new_ip": true, "ban": true}\n')
        (data / "session_secret.txt").write_text("deadbeef\n")
        (data / "security-audit.jsonl").write_text('{"t": 1, "event": "x", "ip": "1.2.3.4", "detail": ""}\n')
        ss.init_key()
        changed = {p.name for p in ss.migrate()}
        self.assertEqual(changed, {"admin_password.txt", "alerts.json", "session_secret.txt", "security-audit.jsonl"})
        self.assertNotIn("1.2.3.4", (data / "security-audit.jsonl").read_text())
        self.assertEqual(ss.read_text(self.tmp / "state" / "admin_password.txt").strip(), "oldpassword123")


if __name__ == "__main__":
    unittest.main()
