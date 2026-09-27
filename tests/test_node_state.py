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


if __name__ == "__main__":
    unittest.main()
