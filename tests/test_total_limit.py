"""The host total's cap action: the console's decision, the shared file, and the shared policy."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import app_meter  # noqa: E402
import node_accounting as na  # noqa: E402
import total_meter as tm  # noqa: E402

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
GIB = 1073741824


def state(cap=10 * GIB, action=None, alerted=None):
    value = tm.new_state({}, NOW, cap, 1)
    if action:
        value["cap_action"] = action
    if alerted is not None:
        value["alerted"] = alerted
    return tm.validate(value)


def policy(host, entry=None):
    entry = entry or app_meter._new("files")
    inventory = {"version": 1, "nodes": [entry]}
    ledger = {"version": 1, "nodes": {entry["id"]: {"samples": None, "suspect": False}}}
    return na.desired_policy(inventory, ledger, now=NOW, validate=app_meter.validate, host=host)[entry["id"]]


class DecisionTest(unittest.TestCase):
    def test_notify_is_default_and_never_enforces(self):
        self.assertEqual(tm.cap_action(state()), "notify")
        self.assertIsNone(tm.enforced(state(), 11 * GIB))

    def test_enforces_only_when_over(self):
        self.assertIsNone(tm.enforced(state(action="block"), 9 * GIB))
        self.assertEqual(tm.enforced(state(action="block"), 10 * GIB), "block")
        self.assertEqual(tm.enforced(state(action="throttle"), 12 * GIB), "throttle")
        self.assertIsNone(tm.enforced(state(cap=None, action="block"), 12 * GIB))

    def test_alerts_once_per_level(self):
        self.assertEqual(tm.due_alerts(state(), 5 * GIB), [])
        self.assertEqual(tm.due_alerts(state(), 9 * GIB), ["warn"])
        self.assertEqual(tm.due_alerts(state(), 10 * GIB), ["warn", "over"])
        self.assertEqual(tm.due_alerts(state(alerted=["warn"]), 10 * GIB), ["over"])
        self.assertEqual(tm.due_alerts(state(alerted=["warn", "over"]), 10 * GIB), [])

    def test_new_period_and_new_cap_alert_again(self):
        old = {**state(action="block", alerted=["warn", "over"]), "next_reset_at": (NOW - timedelta(seconds=1)).isoformat()}
        new, changed = tm.advance(old, {}, NOW)
        self.assertTrue(changed)
        self.assertEqual(new["alerted"], [])
        self.assertEqual(new["cap_action"], "block")
        updated = tm.apply_settings(state(alerted=["warn"]), 20 * GIB, 1, NOW)
        self.assertEqual(updated["alerted"], [])
        self.assertEqual(updated["cap_action"], "notify")
        self.assertEqual(tm.apply_settings(state(), 10 * GIB, 1, NOW, action="throttle")["cap_action"], "throttle")
        with self.assertRaises(ValueError):
            tm.apply_settings(state(), 10 * GIB, 1, NOW, action="drop")

    def test_validate_rejects_odd_fields(self):
        with self.assertRaises(ValueError):
            tm.validate({**state(), "cap_action": "drop"})
        with self.assertRaises(ValueError):
            tm.validate({**state(), "alerted": ["sometimes"]})


class LimitFileTest(unittest.TestCase):
    def test_round_trip_expiry_and_removal(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(tm.host_limit(NOW, folder))
            until = (NOW + timedelta(days=3)).isoformat()
            self.assertTrue(tm.write_limit(folder, "block", until))
            self.assertFalse(tm.write_limit(folder, "block", until))
            self.assertEqual(tm.host_limit(NOW, folder), "block")
            self.assertIsNone(tm.host_limit(NOW + timedelta(days=3), folder))
            self.assertTrue(tm.write_limit(folder, "throttle", None))
            self.assertEqual(tm.host_limit(NOW, folder), "throttle")
            self.assertTrue(tm.write_limit(folder, None, None))
            self.assertFalse(tm.write_limit(folder, None, None))
            self.assertIsNone(tm.host_limit(NOW, folder))

    def test_odd_file_means_no_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            for text in ("not json", json.dumps({"action": "drop", "until": None}), json.dumps([1])):
                (Path(folder) / tm.LIMIT_FILE).write_text(text)
                self.assertIsNone(tm.host_limit(NOW, folder))


class SharedPolicyTest(unittest.TestCase):
    def test_host_limit_applies_like_an_own_cap(self):
        free = policy(None)
        self.assertFalse(free["blocked"])
        self.assertIsNone(free["upload_bps"])
        slow = policy("throttle")
        self.assertFalse(slow["blocked"])
        self.assertEqual((slow["upload_bps"], slow["download_bps"]), (na.LIMIT_BPS, na.LIMIT_BPS))
        stopped = policy("block")
        self.assertTrue(stopped["blocked"])
        self.assertIsNone(stopped["upload_bps"])

    def test_stricter_of_own_and_host_wins(self):
        entry = {**app_meter._new("files"), "cap_bytes": 1, "cap_action": "block", "upload_bytes": 5,
                 "total_upload_bytes": 5}
        self.assertTrue(policy("throttle", entry)["blocked"])
        entry = {**app_meter._new("files"), "upload_limit_bps": 100_000}
        self.assertEqual(policy("throttle", entry)["upload_bps"], 100_000)
        entry = {**app_meter._new("files"), "upload_limit_bps": 50_000_000}
        self.assertEqual(policy("throttle", entry)["upload_bps"], na.LIMIT_BPS)

    def test_rejects_unknown_host_action(self):
        with self.assertRaises(ValueError):
            policy("drop")


if __name__ == "__main__":
    unittest.main()
