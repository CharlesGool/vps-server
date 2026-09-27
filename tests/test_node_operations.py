"""Offline operations against synthetic legacy inbounds only."""
import copy
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
from node_inventory import InvalidInventory, import_legacy, validate_inventory
from node_operations import (create_node, edit_node, render_effective_config,
                             set_enabled_by_id)
from test_node_inventory import NAMESPACE, config, inbound

NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.inventory = import_legacy(config([inbound("anytls", 20001, "anytls-in")]),
                                       config([inbound(p, i, p + "-in") for i, p in
                                               enumerate(("vmess", "vless", "trojan", "shadowsocks"), 20002)]),
                                       migration_namespace=NAMESPACE)
        self.original = copy.deepcopy(self.inventory)

    def create(self, protocol, port=30000, **kwargs):
        return create_node(self.inventory, protocol, "new node", port,
                           reserved_ports=[40000], **kwargs)

    def test_duplicate_every_protocol_preserves_template_and_old_credential(self):
        for i, old in enumerate(self.inventory["nodes"]):
            with self.subTest(protocol=old["protocol"]):
                result = self.create(old["protocol"], 30000 + i)
                new = result["nodes"][-1]
                validate_inventory(result)
                self.assertEqual(result["nodes"][:-1], self.original["nodes"])
                self.assertNotEqual(new["id"], old["id"])
                self.assertNotEqual(new["inbound"]["tag"], old["inbound"]["tag"])
                self.assertEqual(new["inbound"].get("tls"), old["inbound"].get("tls"))
                before = copy.deepcopy(old["inbound"])
                after = copy.deepcopy(new["inbound"])
                for item in (before, after):
                    item.pop("tag")
                    item.pop("listen_port")
                    if old["protocol"] == "shadowsocks":
                        item.pop("password")
                    else:
                        item["users"][0].pop("name", None)
                        item["users"][0].pop("uuid" if old["protocol"] in ("vmess", "vless") else "password")
                self.assertEqual(after, before)
                self.assertNotEqual(new["inbound"].get("password", new["inbound"].get("users")),
                                    old["inbound"].get("password", old["inbound"].get("users")))
        self.assertEqual(self.inventory, self.original)

    def test_collisions_missing_prototype_and_invalid_template(self):
        for port in (20001, 40000, True, 65536):
            with self.subTest(port=port), self.assertRaises(InvalidInventory):
                self.create("vmess", port)
        with self.assertRaises(InvalidInventory):
            self.create("vmess", prototype_id=self.inventory["nodes"][0]["id"])
        empty = copy.deepcopy(self.inventory)
        empty["nodes"] = [n for n in empty["nodes"] if n["protocol"] != "vmess"]
        with self.assertRaises(InvalidInventory):
            create_node(empty, "vmess", "new", 30000, reserved_ports=[])
        bad = copy.deepcopy(self.inventory)
        bad["nodes"][0]["inbound"]["tls"]["key_path"] = ""
        with self.assertRaises(InvalidInventory):
            create_node(bad, "anytls", "new", 30000, reserved_ports=[])
        with self.assertRaises(InvalidInventory):
            self.create("shadowsocks", expires_at="not UTC")

    def test_random_id_retry_and_failure(self):
        old = uuid.UUID(self.inventory["nodes"][0]["id"])
        fresh = uuid.UUID("baac71a1-165e-447c-b874-a58542189873")
        credential = uuid.UUID("f4df74e1-d656-48e6-9777-d74b94235f47")
        generated = iter((old, fresh, old, credential))
        new = self.create("vmess", uuid_factory=lambda: next(generated))["nodes"][-1]
        self.assertEqual(new["id"], str(fresh))
        self.assertEqual(new["inbound"]["users"][0]["uuid"], str(credential))
        with self.assertRaises(InvalidInventory):
            self.create("vmess", uuid_factory=lambda: old)

    def test_edit_allowlist_cap_and_fail_closed(self):
        node = self.inventory["nodes"][1]
        identifier = node["id"]
        self.inventory["nodes"][1]["upload_bytes"] = 8
        self.inventory["nodes"][1]["download_bytes"] = 2
        updated = edit_node(self.inventory, identifier,
                            {"name": "renamed", "port": 30000, "cap_bytes": 11,
                             "expires_at": "2031-01-01T00:00:00+00:00",
                             "credential": "d7f4aecc-4b17-4f58-b1e2-47fe00400cd2"}, reserved_ports=[])
        self.assertEqual(updated["nodes"][1]["id"], identifier)
        self.assertEqual(updated["nodes"][1]["upload_bytes"], 8)
        self.assertEqual(updated["nodes"][1]["inbound"]["listen_port"], 30000)
        self.assertEqual(self.inventory["nodes"][1]["port"], 20002)
        for cap in (10, 1):
            exhausted = edit_node(self.inventory, identifier, {"cap_bytes": cap}, reserved_ports=[])
            self.assertEqual(exhausted["nodes"][1]["cap_bytes"], cap)
        for change in ({"id": str(uuid.uuid4())}, {"protocol": "trojan"},
                       {"inbound": {}}, {"upload_bytes": 0}, {"enabled": False},
                       {"cap_bytes": 0}, {"port": 20003}, {"port": 40000},
                       {"name": self.inventory["nodes"][0]["name"]},
                       {"credential": "invalid"}, {"expires_at": "2030-01-01"}):
            with self.subTest(change=change), self.assertRaises(InvalidInventory):
                edit_node(self.inventory, identifier, change, reserved_ports=[40000])
        with self.assertRaises(InvalidInventory):
            edit_node(self.inventory, str(uuid.uuid4()), {"name": "x"}, reserved_ports=[])

    def test_disabled_expired_and_exhausted_effective_state(self):
        first, second, third = self.inventory["nodes"][:3]
        first["expires_at"] = "2030-01-01T00:00:00+00:00"
        second["cap_bytes"] = 10
        second["upload_bytes"] = 10
        third["enabled"] = False
        original = copy.deepcopy(self.inventory)
        rendered = render_effective_config(self.inventory, now=NOW)
        self.assertEqual([i["tag"] for i in rendered["inbounds"]],
                         [n["inbound"]["tag"] for n in (second, *self.inventory["nodes"][3:])])
        self.assertEqual(self.inventory, original)
        with self.assertRaises(InvalidInventory):
            set_enabled_by_id(self.inventory, first["id"], True, now=NOW)
        self.assertTrue(set_enabled_by_id(self.inventory, second["id"], True, now=NOW)
                        ["nodes"][1]["enabled"])
        enabled = set_enabled_by_id(self.inventory, third["id"], True, now=NOW)
        self.assertTrue(enabled["nodes"][2]["enabled"])
        disabled = set_enabled_by_id(self.inventory, third["id"], False, now=NOW)
        self.assertFalse(disabled["nodes"][2]["enabled"])
        with self.assertRaises(InvalidInventory):
            render_effective_config(self.inventory, now=datetime(2030, 1, 1))


if __name__ == "__main__":
    unittest.main()
