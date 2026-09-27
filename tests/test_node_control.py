"""Privileged node edits with rollback against disposable configs and a fake host."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
from node_control import NodeControlError, apply_request
from node_state import initialize_inventory, read_inventory
from test_node_inventory import config, inbound


class FakeHost:
    def __init__(self):
        self.calls = []
        self.fail = None

    def _call(self, name):
        self.calls.append(name)
        if self.fail == name:
            self.fail = None
            raise RuntimeError("injected host failure")

    def active(self, service):
        return True

    def check(self, path):
        self._call("check")
        assert json.loads(Path(path).read_text())["inbounds"]

    def restart(self, service):
        self._call("restart")

    def stop(self, service):
        self._call("stop")

    def start(self, service):
        self._call("start")

    def reconcile(self, **kwargs):
        self._call("reconcile")

    def firewall(self, port, opening, protocol="tcp"):
        self._call(("open:" if opening else "close:") + str(port))


class NodeControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.state = root / "nodes" / "state.json"
        self.lock = root / "lock"
        self.configs = {"anytls": root / "anytls.json", "proxy": root / "proxy.json"}
        self.configs["anytls"].write_text(json.dumps(config([inbound("anytls", 20001, "a")])))
        self.configs["proxy"].write_text(json.dumps(config([inbound("trojan", 20002, "t")])))
        self.inventory = initialize_inventory(state_path=self.state, config_paths=self.configs)
        self.host = FakeHost()
        self.identifier = self.inventory["nodes"][0]["id"]

    def apply(self, request):
        return apply_request(request, state_path=self.state, config_paths=self.configs,
                             lock_path=self.lock, backend=self.host, require_root=False)

    def test_name_and_limits_change_state_without_restarting_service(self):
        updated = self.apply({"action": "edit", "id": self.identifier, "name": "Tokyo",
                              "cap_bytes": 1000000, "reset_mode": "monthly",
                              "next_reset_at": "2030-02-01T00:00:00+00:00"})
        self.assertEqual(updated["nodes"][0]["name"], "Tokyo")
        self.assertEqual(updated["nodes"][0]["number"], 1)
        self.assertEqual(updated["nodes"][0]["id"], self.identifier)
        self.assertEqual(self.host.calls, ["reconcile"])
        self.assertEqual(read_inventory(state_path=self.state, config_paths=self.configs), updated)

    def test_port_and_credential_commit_only_after_service_health(self):
        with patch("node_control._free_port"):
            updated = self.apply({"action": "edit", "id": self.identifier,
                                  "port": 30001, "credential": "new-secret-value"})
        self.assertEqual([inbound["listen_port"] for inbound in
                          json.loads(self.configs["anytls"].read_text())["inbounds"]], [30001])
        self.assertEqual(updated["nodes"][0]["inbound"]["users"][0]["password"],
                         "new-secret-value")
        self.assertEqual(self.host.calls,
                         ["check", "open:30001", "stop", "reconcile", "start", "close:20001"])

    def test_restart_failure_restores_config_and_state(self):
        old_config = self.configs["anytls"].read_bytes()
        old_state = copy.deepcopy(self.inventory)
        self.host.fail = "start"
        with patch("node_control._free_port"), self.assertRaises(NodeControlError):
            self.apply({"action": "edit", "id": self.identifier,
                        "port": 30001, "credential": "new-secret-value"})
        self.assertEqual(self.configs["anytls"].read_bytes(), old_config)
        self.assertEqual(read_inventory(state_path=self.state, config_paths=self.configs), old_state)
        self.assertEqual(self.host.calls,
                         ["check", "open:30001", "stop", "reconcile", "start",
                          "reconcile", "start", "open:20001", "close:30001"])

    def test_reset_rotates_port_and_secret_but_preserves_tls(self):
        old_tls = copy.deepcopy(self.inventory["nodes"][0]["inbound"]["tls"])
        with patch("node_control.secrets.randbelow", return_value=12345), \
             patch("node_control._free_port"):
            updated = self.apply({"action": "reset", "id": self.identifier})
        node = updated["nodes"][0]
        self.assertEqual(node["port"], 32345)
        self.assertNotEqual(node["inbound"]["users"][0]["password"],
                            self.inventory["nodes"][0]["inbound"]["users"][0]["password"])
        self.assertEqual(node["inbound"]["tls"], old_tls)

    def test_rejects_unrequested_fields_and_shadowsocks_sni(self):
        with self.assertRaises(NodeControlError):
            self.apply({"action": "edit", "id": self.identifier, "enabled": False})
        self.configs["proxy"].write_text(json.dumps(config([inbound("shadowsocks", 20002, "s")])))
        # Imported state is intentionally bound to the original installed
        # inbound, so an external protocol change is rejected before editing.
        with self.assertRaisesRegex(ValueError, "differs"):
            self.apply({"action": "edit", "id": self.identifier, "sni": "example.com"})


if __name__ == "__main__":
    unittest.main()
