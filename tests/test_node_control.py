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
        self.active_result = True

    def _call(self, name):
        self.calls.append(name)
        if self.fail == name:
            self.fail = None
            raise RuntimeError("injected host failure")

    def active(self, service):
        return self.active_result

    def check(self, path):
        self._call("check")
        assert isinstance(json.loads(Path(path).read_text())["inbounds"], list)

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

    def test_create_duplicate_and_delete_last_listener(self):
        with patch("node_control._free_port"):
            created = self.apply({"action": "create", "protocol": "anytls",
                                  "name": "Second node", "port": 30001, "sni": "example.org",
                                  "credential": "manual-anytls-secret"})
        self.assertEqual([node["number"] for node in created["nodes"]], [1, 2, 3])
        self.assertEqual(created["nodes"][-1]["inbound"]["users"][0]["password"],
                         "manual-anytls-secret")
        self.assertEqual(len(json.loads(self.configs["anytls"].read_text())["inbounds"]), 2)
        first_removed = self.apply({"action": "delete", "id": self.identifier})
        self.assertEqual([node["number"] for node in first_removed["nodes"]], [1, 2])
        second_id = created["nodes"][-1]["id"]
        cert_root = self.state.parent / "certs" / second_id
        self.assertTrue(cert_root.is_dir())
        all_removed = self.apply({"action": "delete", "id": second_id})
        self.assertEqual([node["number"] for node in all_removed["nodes"]], [1])
        self.assertEqual(json.loads(self.configs["anytls"].read_text())["inbounds"], [])
        self.assertFalse(cert_root.exists())
        self.assertEqual(read_inventory(state_path=self.state, config_paths=self.configs), all_removed)

    def test_toggle_removes_only_target_listener_and_preserves_identity(self):
        original = copy.deepcopy(self.inventory["nodes"][0])
        disabled = self.apply({"action": "toggle", "id": self.identifier, "enabled": False})
        self.assertFalse(disabled["nodes"][0]["enabled"])
        self.assertEqual(disabled["nodes"][0]["id"], original["id"])
        self.assertEqual(json.loads(self.configs["anytls"].read_text())["inbounds"], [])
        self.assertEqual(self.host.calls, ["check", "stop", "reconcile", "close:20001"])
        self.assertEqual(read_inventory(state_path=self.state, config_paths=self.configs), disabled)
        with patch("node_control._free_port"):
            edited = self.apply({"action": "edit", "id": self.identifier,
                                 "name": "Paused node", "port": 30001,
                                 "credential": "paused-node-secret"})
        self.assertFalse(edited["nodes"][0]["enabled"])
        self.assertEqual(json.loads(self.configs["anytls"].read_text())["inbounds"], [])
        self.host.calls.clear()
        self.host.active_result = False
        with patch("node_control._free_port"):
            enabled = self.apply({"action": "toggle", "id": self.identifier, "enabled": True})
        self.assertEqual(enabled["nodes"][0]["id"], original["id"])
        self.assertEqual(enabled["nodes"][0]["port"], 30001)
        self.assertEqual(enabled["nodes"][0]["inbound"]["users"][0]["password"],
                         "paused-node-secret")
        self.assertEqual(len(json.loads(self.configs["anytls"].read_text())["inbounds"]), 1)
        self.assertEqual(self.host.calls, ["check", "open:30001", "reconcile", "start"])

    def test_toggle_start_failure_restores_disabled_listener(self):
        self.apply({"action": "toggle", "id": self.identifier, "enabled": False})
        self.host.calls.clear()
        self.host.active_result = False
        self.host.fail = "start"
        with patch("node_control._free_port"), self.assertRaises(NodeControlError):
            self.apply({"action": "toggle", "id": self.identifier, "enabled": True})
        self.assertFalse(read_inventory(state_path=self.state, config_paths=self.configs)["nodes"][0]["enabled"])
        self.assertEqual(len(json.loads(self.configs["anytls"].read_text())["inbounds"]), 0)
        self.assertIn("open:20001", self.host.calls)

    def test_create_new_protocol_and_rollback_on_restart_failure(self):
        original_config = self.configs["proxy"].read_bytes()
        original_state = copy.deepcopy(self.inventory)
        self.host.fail = "start"
        with patch("node_control._free_port"), self.assertRaises(NodeControlError):
            self.apply({"action": "create", "protocol": "shadowsocks",
                        "name": "New shadowsocks", "port": 30002})
        self.assertEqual(self.configs["proxy"].read_bytes(), original_config)
        self.assertEqual(read_inventory(state_path=self.state, config_paths=self.configs), original_state)
        with patch("node_control._free_port"):
            created = self.apply({"action": "create", "protocol": "shadowsocks",
                                  "name": "New shadowsocks", "port": 30002})
        self.assertEqual(created["nodes"][-1]["protocol"], "shadowsocks")


class IperfPortRegistryTests(unittest.TestCase):
    def test_runtime_port_change_updates_registry_and_state(self):
        import node_control
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = root / "vps-server"
            (app_dir / "data").mkdir(parents=True)
            registry = root / "PORTS.md"
            registry.write_text("| Host Port | Project / Service | Bind Address | Registration Date |\n"
                                "| --- | --- | --- | --- |\n"
                                "| 5201 | vps-server-iperf3-window | 0.0.0.0 | 2026-09-27 |\n")
            request = {"action": "iperf-port", "old_port": 5201, "port": 15299}
            with patch.object(node_control, "APP_DIR", app_dir), \
                 patch.object(node_control, "IPERF_PORT_FILE", app_dir / "data" / "iperf-port.txt"), \
                 patch.object(node_control, "_free_port"), \
                 patch.object(node_control, "_reserved_ports", return_value={80, 443, 5201}):
                self.assertTrue(apply_request(request, require_root=False))
                self.assertEqual((app_dir / "data" / "iperf-port.txt").read_text(), "15299\n")
                self.assertIn("| 15299 | vps-server-iperf3-window |", registry.read_text())
                self.assertNotIn("| 5201 |", registry.read_text())
                with self.assertRaises(NodeControlError):
                    apply_request(request, require_root=False)


if __name__ == "__main__":
    unittest.main()
