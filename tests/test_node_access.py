"""Per-node destination policy: validation, rule generation and editing (pure, offline)."""
import copy
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import node_inventory as ni  # noqa: E402
import node_operations as ops  # noqa: E402


def inventory(*ports):
    inv = {"version": 2, "next_number": 1, "migration_namespace": str(uuid.uuid4()), "migration_hashes": {},
           "base_config": {"log": {"level": "info"}, "outbounds": [{"type": "direct", "tag": "direct"},
                                                                   {"type": "block", "tag": "block"}],
                           "route": {"final": "direct"}},
           "nodes": []}
    for index, port in enumerate(ports):
        seed = {"type": "shadowsocks", "tag": "seed", "listen": "::", "listen_port": port,
                "method": "2022-blake3-aes-128-gcm", "password": "dGVtcG9yYXJ5LWtleS0xNg=="}
        inv = ops.create_node(inv, "shadowsocks", f"n{index}", port, reserved_ports=[], prototype_inbound=seed)
    return inv


class AccessTest(unittest.TestCase):
    def test_destination_parsing(self):
        cases = {"172.22.31.10": ("cidr", "172.22.31.10/32", None),
                 "172.22.31.10:443": ("cidr", "172.22.31.10/32", "443"),
                 "10.0.0.0/24:8000-8100": ("cidr", "10.0.0.0/24", "8000-8100"),
                 "[fd00::/64]:443": ("cidr", "fd00::/64", "443"),
                 "*.Example.com:443": ("suffix", ".example.com", "443"),
                 "Example.com": ("domain", "example.com", None)}
        for text, expected in cases.items():
            self.assertEqual(ni._destination(text), expected, text)
        for bad in ("", "a b", "1.2.3.4:0", "1.2.3.4:70000", "999.1.1.1", "-x.com", "a..com", "1.2.3.4:9-3", "[::1", "*.", "http://x.com"):
            with self.assertRaises(ni.InvalidInventory, msg=bad):
                ni._destination(bad)

    def test_normalize_is_idempotent_and_dedupes(self):
        result = ni.normalize_destinations(["172.22.31.10:443", "172.22.31.10:443", "*.Example.com", "[::1]:80", "10.0.0.0/24"])
        self.assertEqual(result, ["172.22.31.10:443", "*.example.com", "[::1]:80", "10.0.0.0/24"])
        self.assertEqual(ni.normalize_destinations(result), result)
        with self.assertRaises(ni.InvalidInventory):
            ni.normalize_destinations([])
        with self.assertRaises(ni.InvalidInventory):
            ni.normalize_destinations(["1.1.1.%d" % i for i in range(65)])

    def test_unrestricted_adds_no_rules(self):
        config = ni.render_config(inventory(10001))
        self.assertEqual(config["route"], {"final": "direct"})

    def test_internet_rules_precede_final_and_only_hit_that_node(self):
        inv = inventory(10001, 10002)
        first = inv["nodes"][0]
        inv = ops.edit_node(inv, first["id"], {"access": {"mode": "internet"}}, reserved_ports=[])
        rules = ni.render_config(inv)["route"]["rules"]
        tag = inv["nodes"][0]["inbound"]["tag"]
        self.assertTrue(all(rule["inbound"] == [tag] for rule in rules))
        self.assertEqual([r["action"] for r in rules], ["resolve", "reject", "reject"])
        self.assertTrue(rules[1]["ip_is_private"])
        self.assertIn("100.64.0.0/10", rules[2]["ip_cidr"])

    def test_custom_rules_allow_then_reject(self):
        inv = inventory(10001)
        dests = ni.normalize_destinations(["172.22.31.10:443", "*.example.com"])
        inv = ops.edit_node(inv, inv["nodes"][0]["id"], {"access": {"mode": "custom", "destinations": dests}}, reserved_ports=[])
        rules = ni.render_config(inv)["route"]["rules"]
        self.assertEqual(rules[0]["action"], "resolve")
        self.assertEqual(rules[1], {"inbound": [inv["nodes"][0]["inbound"]["tag"]], "ip_cidr": ["172.22.31.10/32"],
                                    "port": [443], "action": "route", "outbound": "direct"})
        self.assertEqual(rules[2]["domain_suffix"], [".example.com"])
        self.assertEqual(rules[-1]["action"], "reject")
        self.assertEqual(len(rules[-1]), 3 - 1)  # inbound + action only: nothing after it can allow

    def test_disabled_node_gets_no_rules_and_removal_clears_them(self):
        inv = inventory(10001)
        node_id = inv["nodes"][0]["id"]
        inv = ops.edit_node(inv, node_id, {"access": {"mode": "internet"}}, reserved_ports=[])
        off = copy.deepcopy(inv)
        off["nodes"][0]["enabled"] = False
        self.assertNotIn("rules", ni.render_config(off)["route"])
        inv = ops.edit_node(inv, node_id, {"access": None}, reserved_ports=[])
        self.assertNotIn("access", inv["nodes"][0])
        self.assertEqual(ni.render_config(inv)["route"], {"final": "direct"})

    def test_apply_access_keeps_foreign_rules_and_is_idempotent(self):
        inv = inventory(10001)
        inv = ops.edit_node(inv, inv["nodes"][0]["id"], {"access": {"mode": "internet"}}, reserved_ports=[])
        config = {"outbounds": inv["base_config"]["outbounds"],
                  "route": {"final": "direct", "rules": [{"domain": ["x.com"], "action": "reject"}]}}
        once = ni.apply_access(copy.deepcopy(config), inv["nodes"])
        twice = ni.apply_access(copy.deepcopy(once), inv["nodes"])
        self.assertEqual(once, twice)
        self.assertEqual(once["route"]["rules"][-1], {"domain": ["x.com"], "action": "reject"})

    def test_deleted_node_rules_are_removed(self):
        inv = inventory(10001, 10002)
        gone, kept = inv["nodes"]
        for node in (gone, kept):
            inv = ops.edit_node(inv, node["id"], {"access": {"mode": "internet"}}, reserved_ports=[])
        config = ni.render_config(inv)
        remaining = ops.delete_node(inv, gone["id"])
        tag = gone["inbound"]["tag"]
        updated = ni.apply_access(copy.deepcopy(config), remaining["nodes"], [tag])
        self.assertFalse([r for r in updated["route"]["rules"] if r["inbound"] == [tag]])
        self.assertTrue([r for r in updated["route"]["rules"] if r["inbound"] == [kept["inbound"]["tag"]]])

    def test_invalid_access_rejected(self):
        inv = inventory(10001)
        node_id = inv["nodes"][0]["id"]
        for bad in ({"mode": "all"}, {"mode": "internet", "destinations": ["1.1.1.1"]}, {"mode": "custom"},
                    {"mode": "custom", "destinations": ["1.1.1.1/32"]}, {"mode": "custom", "destinations": []}, "internet"):
            with self.assertRaises(ni.InvalidInventory, msg=str(bad)):
                ops.edit_node(inv, node_id, {"access": bad}, reserved_ports=[])


if __name__ == "__main__":
    unittest.main()
