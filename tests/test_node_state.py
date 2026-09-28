"""State import preserves node identity and detects out-of-band changes."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
from node_inventory import InvalidInventory
from node_state import initialize_inventory, read_inventory, write_inventory
from test_node_inventory import config, inbound


class NodeStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.state = root / "nodes" / "state.json"
        self.configs = {"anytls": root / "anytls.json", "proxy": root / "proxy.json"}
        self.configs["anytls"].write_text(json.dumps(config([inbound("anytls", 20001, "a")])))
        self.configs["proxy"].write_text(json.dumps(config([inbound("trojan", 20002, "t")])))

    def test_first_import_and_repeat_keep_ids_numbers_and_permissions(self):
        first = initialize_inventory(state_path=self.state, config_paths=self.configs)
        second = initialize_inventory(state_path=self.state, config_paths=self.configs)
        self.assertEqual(first, second)
        self.assertEqual([node["number"] for node in first["nodes"]], [1, 2])
        self.assertEqual(len({node["id"] for node in first["nodes"]}), 2)
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.state.parent.stat().st_mode & 0o777, 0o700)

    def test_metadata_edit_keeps_identity_and_detects_external_config_edit(self):
        inventory = initialize_inventory(state_path=self.state, config_paths=self.configs)
        identifier = inventory["nodes"][0]["id"]
        inventory["nodes"][0]["name"] = "Tokyo"
        write_inventory(inventory, state_path=self.state)
        self.assertEqual(read_inventory(state_path=self.state, config_paths=self.configs)
                         ["nodes"][0]["id"], identifier)
        changed = json.loads(self.configs["anytls"].read_text())
        changed["inbounds"][0]["listen_port"] = 30001
        self.configs["anytls"].write_text(json.dumps(changed))
        with self.assertRaisesRegex(InvalidInventory, "differs"):
            read_inventory(state_path=self.state, config_paths=self.configs)

    def test_new_module_joins_without_renumbering_existing_nodes(self):
        self.configs["proxy"].unlink()
        initial = initialize_inventory(state_path=self.state, config_paths=self.configs)
        first_id = initial["nodes"][0]["id"]
        self.configs["proxy"].write_text(json.dumps(config([inbound("trojan", 20002, "t")])))
        combined = initialize_inventory(state_path=self.state, config_paths=self.configs)
        self.assertEqual([node["number"] for node in combined["nodes"]], [1, 2])
        self.assertEqual(combined["nodes"][0]["id"], first_id)
        self.assertEqual(len(combined["migration_hashes"]), 2)

    def test_version_one_state_migrates_without_reinterpreting_old_expiry(self):
        current = initialize_inventory(state_path=self.state, config_paths=self.configs)
        old = json.loads(json.dumps(current))
        old["version"] = 1
        for node in old["nodes"]:
            for key in ("cap_action", "upload_limit_bps", "download_limit_bps",
                        "expiry_count", "expiry_unit"):
                node.pop(key)
            node["expires_at"] = "2030-01-01T00:00:00+00:00"
        self.state.write_text(json.dumps(old))
        migrated = read_inventory(state_path=self.state, config_paths=self.configs)
        self.assertEqual(migrated["version"], 2)
        self.assertEqual([node["id"] for node in migrated["nodes"]],
                         [node["id"] for node in old["nodes"]])
        self.assertTrue(all(node["cap_action"] == "throttle" and
                            node["expires_at"] is None for node in migrated["nodes"]))
        write_inventory(migrated, state_path=self.state)
        self.assertEqual(json.loads(self.state.read_text())["version"], 2)


if __name__ == "__main__":
    unittest.main()
