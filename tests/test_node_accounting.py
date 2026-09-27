"""Offline listener accounting and desired policy tests."""
import copy
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
from node_inventory import InvalidInventory, import_legacy
from node_accounting import MAX_BYTES, advance_cycles, desired_policy, update_accounting
from test_node_inventory import NAMESPACE, config, inbound

NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)


def counters(v4_up=0, v4_down=0, v6_up=0, v6_down=0, epoch=0):
    values = ((v4_up, v4_down), (v6_up, v6_down))
    return {family: {direction: {"epoch": epoch, "bytes": amount}
                     for direction, amount in zip(("upload", "download"), pair)}
            for family, pair in zip(("ipv4", "ipv6"), values)}


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.inventory = import_legacy(config([inbound("anytls", 20001, "a")]), None,
                                       migration_namespace=NAMESPACE)
        self.identifier = self.inventory["nodes"][0]["id"]
        self.state = {"version": 1, "nodes": {}}
        self.inventory["nodes"][0]["cap_bytes"] = 10

    def update(self, sample, inventory=None, state=None):
        return update_accounting(inventory or self.inventory, state or self.state,
                                 {self.identifier: sample})

    def test_dual_stack_cap_equality_persistent_and_deep_copy(self):
        original = copy.deepcopy(self.inventory)
        raw = counters(3, 2, 4, 1)
        old_raw = copy.deepcopy(raw)
        inventory, state = self.update(raw)
        self.assertEqual(self.inventory, original)
        self.assertEqual(self.state, {"version": 1, "nodes": {}})
        self.assertEqual(raw, old_raw)
        node = inventory["nodes"][0]
        self.assertEqual((node["upload_bytes"], node["download_bytes"]), (7, 3))
        self.assertEqual((node["total_upload_bytes"], node["total_download_bytes"]), (7, 3))
        self.assertEqual(desired_policy(inventory, state, now=NOW)[self.identifier],
                         {"active": True, "expired": False, "capped": True,
                          "upload_bps": 1_000_000, "download_bps": 1_000_000,
                          "suspect": False})
        again, state = self.update(raw, inventory, state)
        self.assertEqual(again, inventory)
        raw["ipv6"]["download"]["bytes"] = 5
        more, state = self.update(raw, again, state)
        self.assertEqual(more["nodes"][0]["download_bytes"], 7)
        self.assertTrue(desired_policy(more, state, now=NOW)[self.identifier]["active"])

    def test_expiry_boundary_disabled_and_uncapped(self):
        inventory, state = self.update(counters(1))
        node = inventory["nodes"][0]
        node["expires_at"] = "2030-01-01T00:00:00+00:00"
        at = desired_policy(inventory, state, now=NOW)[self.identifier]
        self.assertTrue(at["expired"])
        self.assertTrue(at["active"])
        self.assertEqual((at["upload_bps"], at["download_bps"]), (1_000_000, 1_000_000))
        self.assertTrue(desired_policy(inventory, state, now=NOW.replace(year=2029))
                        [self.identifier]["active"])
        node["expires_at"] = None
        node["enabled"] = False
        self.assertFalse(desired_policy(inventory, state, now=NOW)[self.identifier]["active"])
        node["enabled"] = True
        node["cap_bytes"] = None
        self.assertIsNone(desired_policy(inventory, state, now=NOW)[self.identifier]["upload_bps"])

    def test_monthly_cycle_preserves_lifetime_and_lifts_date_throttle(self):
        inventory, state = self.update(counters(7, 5))
        node = inventory["nodes"][0]
        node["reset_mode"] = "monthly"
        node["next_reset_at"] = "2030-01-01T00:00:00+00:00"
        node["expires_at"] = "2029-12-20T00:00:00+00:00"
        self.assertTrue(desired_policy(inventory, state, now=NOW)[self.identifier]["expired"])
        next_inventory, next_state = advance_cycles(inventory, state, now=NOW)
        result = next_inventory["nodes"][0]
        self.assertEqual((result["upload_bytes"], result["download_bytes"]), (0, 0))
        self.assertEqual((result["total_upload_bytes"], result["total_download_bytes"]), (7, 5))
        self.assertEqual(result["expires_at"], "2030-01-20T00:00:00+00:00")
        self.assertEqual(result["next_reset_at"], "2030-02-01T00:00:00+00:00")
        self.assertFalse(desired_policy(next_inventory, next_state, now=NOW)[self.identifier]["expired"])
        self.assertIsNone(desired_policy(next_inventory, next_state, now=NOW)[self.identifier]["upload_bps"])
        with_new_bytes, _ = update_accounting(next_inventory, next_state,
                                              {self.identifier: counters(8, 6)})
        self.assertEqual((with_new_bytes["nodes"][0]["upload_bytes"],
                          with_new_bytes["nodes"][0]["total_upload_bytes"]), (1, 8))

    def test_one_time_reset_clears_deadline_and_does_not_repeat(self):
        inventory, state = self.update(counters(11, 3))
        node = inventory["nodes"][0]
        node["reset_mode"] = "once"
        node["next_reset_at"] = "2030-01-01T00:00:00+00:00"
        node["expires_at"] = "2029-12-30T00:00:00+00:00"
        result, ledger = advance_cycles(inventory, state, now=NOW)
        node = result["nodes"][0]
        self.assertEqual((node["reset_mode"], node["next_reset_at"], node["expires_at"]),
                         ("none", None, None))
        self.assertEqual(node["upload_bytes"], 0)
        self.assertEqual(node["total_upload_bytes"], 11)
        self.assertEqual(advance_cycles(result, ledger, now=NOW), (result, ledger))

    def test_directional_reset_preserves_totals_and_blocks_service(self):
        inventory, state = self.update(counters(8, 4))
        raw = counters(2, 6)
        inventory, state = self.update(raw, inventory, state)
        node = inventory["nodes"][0]
        self.assertEqual((node["upload_bytes"], node["download_bytes"], node["counter_epoch"]),
                         (10, 6, 1))
        self.assertTrue(state["nodes"][self.identifier]["suspect"])
        self.assertTrue(desired_policy(inventory, state, now=NOW)[self.identifier]["active"])
        self.assertEqual(desired_policy(inventory, state, now=NOW)
                         [self.identifier]["upload_bps"], 1_000_000)
        raw["ipv4"]["upload"]["epoch"] = 1
        raw["ipv4"]["upload"]["bytes"] = 3
        inventory, state = self.update(raw, inventory, state)
        self.assertEqual(inventory["nodes"][0]["upload_bytes"], 13)
        self.assertTrue(desired_policy(inventory, state, now=NOW)[self.identifier]["active"])

    def test_missing_metrics_fail_closed_without_zeroing(self):
        self.assertTrue(desired_policy(self.inventory, self.state, now=NOW)
                        [self.identifier]["suspect"])
        inventory, state = self.update(counters(5))
        missing, ledger = update_accounting(inventory, state, {})
        self.assertEqual(missing["nodes"][0]["upload_bytes"], 5)
        self.assertTrue(desired_policy(missing, ledger, now=NOW)[self.identifier]["suspect"])
        self.assertTrue(desired_policy(missing, ledger, now=NOW)[self.identifier]["active"])
        self.assertEqual(desired_policy(missing, ledger, now=NOW)
                         [self.identifier]["download_bps"], 1_000_000)
        partial, ledger = self.update({"ipv4": counters()["ipv4"]}, inventory, state)
        self.assertEqual(partial["nodes"][0]["upload_bytes"], 5)
        self.assertTrue(ledger["nodes"][self.identifier]["suspect"])

    def test_malformed_unknown_duplicate_and_overflow(self):
        for value in (counters(True), counters(-1), counters(MAX_BYTES + 1),
                      {**counters(), "ipv4": {"upload": {"epoch": 0, "bytes": 1},
                                                "download": {"epoch": 0, "bytes": "2"}}}):
            with self.subTest(value=value), self.assertRaises(InvalidInventory):
                self.update(value)
        with self.assertRaises(InvalidInventory):
            update_accounting(self.inventory, self.state, {"unknown": counters()})
        duplicate = copy.deepcopy(self.inventory)
        duplicate["nodes"].append(copy.deepcopy(duplicate["nodes"][0]))
        with self.assertRaises(InvalidInventory):
            update_accounting(duplicate, self.state, {})
        inventory, state = self.update(counters(MAX_BYTES))
        with self.assertRaises(InvalidInventory):
            self.update(counters(MAX_BYTES, 1), inventory, state)
        with self.assertRaises(InvalidInventory):
            desired_policy(self.inventory, self.state, now=datetime(2030, 1, 1))
        with self.assertRaises(InvalidInventory):
            self.update(counters(), inventory, {"version": 1, "nodes": {}})
        initial, ledger = self.update(counters(epoch=1))
        self.assertTrue(ledger["nodes"][self.identifier]["suspect"])
        self.assertTrue(desired_policy(initial, ledger, now=NOW)[self.identifier]["active"])
        with self.assertRaises(InvalidInventory):
            self.update(counters(epoch=0), initial, ledger)
        with self.assertRaises(InvalidInventory):
            self.update({"ipv4": {"upload": {"epoch": 0, "bytes": "bad"}}})
        with self.assertRaises(InvalidInventory):
            self.update({**counters(), "unexpected": {} })


if __name__ == "__main__":
    unittest.main()
