"""Dual-stack counter attribution and policy reconciliation without host nft."""

import json
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
from node_meter import LIMIT_BYTES_PER_SECOND, TABLE, parse_counters, render_rules, tick
from node_operations import create_node, delete_node
from node_state import initialize_inventory, read_inventory, write_inventory
from test_node_inventory import config, inbound


NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)


class FakeNft:
    def __init__(self):
        self.present = False
        self.values = {}
        self.batches = []

    def exists(self):
        return self.present

    def counters(self):
        return {"nftables": [{"counter": {"family": "inet", "table": TABLE,
                                           "name": name, "bytes": value}}
                             for name, value in self.values.items()]}

    def apply(self, batch):
        self.batches.append(batch)
        self.present = True
        self.values = {name: 0 for name in re.findall(r'^add counter inet ' + TABLE +
                                                      r' (\w+)$', batch, re.M)}


class MeterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.state = root / "nodes" / "state.json"
        self.meter = root / "nodes" / "meter.json"
        self.lock = root / "lock"
        self.configs = {"anytls": root / "anytls.json", "proxy": root / "proxy.json"}
        self.configs["anytls"].write_text(json.dumps(config([inbound("anytls", 20001, "a")])))
        self.configs["proxy"].write_text(json.dumps(config([inbound("trojan", 20002, "t")])))
        self.inventory = initialize_inventory(state_path=self.state, config_paths=self.configs)
        self.backend = FakeNft()

    def sample(self, now=NOW):
        return tick(now=now, state_path=self.state, config_paths=self.configs,
                    meter_path=self.meter, lock_path=self.lock, backend=self.backend)

    def test_shared_quota_and_per_direction_limits_cover_tcp_udp_ipv4_ipv6(self):
        node = self.inventory["nodes"][0]
        node["cap_bytes"] = 10
        write_inventory(self.inventory, state_path=self.state)
        policy = self.sample()
        self.assertIsNone(policy[node["id"]]["upload_bps"])
        batch = self.backend.batches[-1]
        stem = node["id"].replace("-", "")
        self.assertIn(f"add quota inet {TABLE} q_{stem} {{ over 10 bytes used 0 bytes; }}", batch)
        self.assertIn(f"rate over {LIMIT_BYTES_PER_SECOND} bytes/second", batch)
        for family in ("ipv4", "ipv6"):
            for protocol in ("tcp", "udp"):
                self.assertIn(f"meta nfproto {family} {protocol} dport 20001", batch)
                self.assertIn(f"meta nfproto {family} {protocol} sport 20001", batch)
        up = f"c_{stem}_ipv4_upload"
        down = f"c_{stem}_ipv6_download"
        self.backend.values[up] = 6
        self.backend.values[down] = 4
        policy = self.sample()
        self.assertTrue(policy[node["id"]]["capped"])
        self.assertEqual((policy[node["id"]]["upload_bps"],
                          policy[node["id"]]["download_bps"]), (1_000_000, 1_000_000))
        result = read_inventory(state_path=self.state, config_paths=self.configs)["nodes"][0]
        self.assertEqual((result["upload_bytes"], result["download_bytes"]), (6, 4))
        self.assertEqual((result["total_upload_bytes"], result["total_download_bytes"]), (6, 4))
        self.assertIn(f'limit name "l_{stem}_upload" drop', self.backend.batches[-1])

    def test_table_loss_keeps_totals_and_polices_until_reset(self):
        identifier = self.inventory["nodes"][0]["id"]
        self.sample()
        key = f"c_{identifier.replace('-', '')}_ipv4_upload"
        self.backend.values[key] = 100
        self.sample()
        self.backend.present = False  # reboot or external deletion
        policy = self.sample()
        self.assertTrue(policy[identifier]["suspect"])
        self.assertEqual(policy[identifier]["upload_bps"], 1_000_000)
        self.assertEqual(read_inventory(state_path=self.state, config_paths=self.configs)
                         ["nodes"][0]["total_upload_bytes"], 100)

    def test_missing_directional_counter_is_rejected(self):
        self.sample()
        self.backend.values.pop(next(iter(self.backend.values)))
        with self.assertRaisesRegex(ValueError, "missing node counter"):
            self.sample()

    def test_rate_change_reinstalls_rules_for_existing_nodes(self):
        self.inventory["nodes"][0]["cap_bytes"] = 100
        write_inventory(self.inventory, state_path=self.state)
        self.sample()
        self.assertEqual(len(self.backend.batches), 1)
        with patch("node_meter.LIMIT_BYTES_PER_SECOND", LIMIT_BYTES_PER_SECOND - 1000):
            self.sample()
        self.assertEqual(len(self.backend.batches), 2)
        self.assertIn(f"rate over {LIMIT_BYTES_PER_SECOND - 1000} bytes/second",
                      self.backend.batches[-1])

    def test_per_direction_speeds_and_cap_block_apply_to_both_families(self):
        node = self.inventory["nodes"][0]
        node.update(cap_bytes=10, cap_action="block",
                    upload_limit_bps=2_000_000, download_limit_bps=500_000)
        write_inventory(self.inventory, state_path=self.state)
        policy = self.sample()
        self.assertEqual((policy[node["id"]]["upload_bps"],
                          policy[node["id"]]["download_bps"]), (2_000_000, 500_000))
        batch = self.backend.batches[-1]
        self.assertIn("rate over 250000 bytes/second", batch)
        self.assertIn("rate over 62500 bytes/second", batch)
        self.assertIn("quota name", batch)
        self.assertIn("drop", batch)
        stem = node["id"].replace("-", "")
        self.backend.values[f"c_{stem}_ipv4_upload"] = 10
        policy = self.sample()
        self.assertTrue(policy[node["id"]]["blocked"])
        batch = self.backend.batches[-1]
        self.assertIn("meta nfproto ipv4 tcp dport 20001 drop", batch)
        self.assertIn("meta nfproto ipv6 udp sport 20001 drop", batch)

    def test_added_and_deleted_nodes_reconcile_without_losing_survivor_usage(self):
        self.sample()
        original = self.inventory["nodes"][0]
        stem = original["id"].replace("-", "")
        self.backend.values[f"c_{stem}_ipv4_upload"] = 120
        added = create_node(self.inventory, "anytls", "Second", 30001,
                            reserved_ports=set())
        new_id = added["nodes"][-1]["id"]
        self.configs["anytls"].write_text(json.dumps(config(
            [node["inbound"] for node in added["nodes"] if node["protocol"] == "anytls"])))
        write_inventory(added, state_path=self.state)
        policy = self.sample()
        self.assertFalse(policy[new_id]["suspect"])
        current = read_inventory(state_path=self.state, config_paths=self.configs)
        self.assertEqual(current["nodes"][0]["total_upload_bytes"], 120)
        removed = delete_node(current, new_id)
        self.configs["anytls"].write_text(json.dumps(config(
            [node["inbound"] for node in removed["nodes"] if node["protocol"] == "anytls"])))
        write_inventory(removed, state_path=self.state)
        self.sample()
        ledger = json.loads(self.meter.read_text())["ledger"]["nodes"]
        self.assertNotIn(new_id, ledger)
        self.assertEqual(read_inventory(state_path=self.state, config_paths=self.configs)
                         ["nodes"][0]["total_upload_bytes"], 120)


if __name__ == "__main__":
    unittest.main()
