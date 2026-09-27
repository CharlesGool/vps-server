"""Offline legacy inventory tests; no installed paths or services are used."""
import copy
import json
from pathlib import Path
import sys
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
from node_inventory import InvalidInventory, import_legacy, render_config, validate_inventory


NAMESPACE = "f42f7406-f6d3-4a7a-84f3-9ac9e435fd86"
BASE = {"log": {"level": "info", "timestamp": True},
        "outbounds": [{"type": "direct", "tag": "direct"}, {"type": "block", "tag": "block"}],
        "route": {"final": "direct"}, "experimental": {"cache_file": {"enabled": False}}}


def inbound(protocol, port, tag):
    item = {"type": protocol, "tag": tag, "listen": "::", "listen_port": port}
    if protocol == "shadowsocks":
        item.update(method="2022-blake3-aes-128-gcm", password="AAAAAAAAAAAAAAAAAAAAAA==")
    else:
        secret = "uuid" if protocol in ("vmess", "vless") else "password"
        item["users"] = [{"name": protocol, secret: "5f601a0f-f0d7-42f9-bc15-c51d72175801" if secret == "uuid" else "old-secret"}]
        item["tls"] = {"enabled": True, "certificate_path": "/etc/old cert/fullchain.pem",
                       "key_path": "/etc/old cert/key.pem"}
    return item


def config(items):
    return {**copy.deepcopy(BASE), "inbounds": items}


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.anytls = config([inbound("anytls", 20001, "anytls-in")])
        self.proxy = config([inbound(p, i, p + "-in") for i, p in
                             enumerate(("vmess", "vless", "trojan", "shadowsocks"), 20002)])

    def imported(self):
        return import_legacy(json.dumps(self.anytls).encode(), json.dumps(self.proxy).encode(),
                             migration_namespace=NAMESPACE)

    def test_import_is_stable_and_preserves_fields_and_base(self):
        original = copy.deepcopy((self.anytls, self.proxy))
        state = self.imported()
        self.assertEqual(state, self.imported())
        state["nodes"][0]["upload_bytes"] = 42
        self.assertEqual(import_legacy(self.anytls, self.proxy, migration_namespace=NAMESPACE,
                                       existing=state), state)
        self.assertEqual((self.anytls, self.proxy), original)
        rendered = render_config(state)
        self.assertEqual(rendered["inbounds"], self.anytls["inbounds"] + self.proxy["inbounds"])
        self.assertEqual({k: v for k, v in rendered.items() if k != "inbounds"}, BASE)
        self.assertEqual(len({n["id"] for n in state["nodes"]}), 5)
        self.assertEqual([n["number"] for n in state["nodes"]], [1, 2, 3, 4, 5])
        self.assertEqual(len(state["migration_hashes"]), 2)
        self.proxy["inbounds"][0]["listen_port"] += 1
        with self.assertRaises(InvalidInventory):
            import_legacy(self.anytls, self.proxy, migration_namespace=NAMESPACE, existing=state)

    def test_same_type_different_tags_disabled_and_metadata(self):
        state = self.imported()
        second = copy.deepcopy(state["nodes"][0])
        second.update(id="6c101472-c204-460d-a193-29d72fb5e590", number=6,
                      name="second node", port=30001,
                      enabled=False, cap_bytes=1024, expires_at="2030-01-01T00:00:00+00:00",
                      upload_bytes=200, download_bytes=400, counter_epoch=1)
        second["inbound"]["tag"] = "anytls-second"
        second["inbound"]["listen_port"] = 30001
        state["nodes"].append(second)
        state["next_number"] = 7
        validate_inventory(state)
        second["number"] = 1
        with self.assertRaises(InvalidInventory):
            validate_inventory(state)
        second["number"] = 6
        self.assertEqual(len(state["nodes"]), 6)
        self.assertEqual(len(render_config(state)["inbounds"]), 5)
        state["nodes"][0]["enabled"] = False
        self.assertEqual(len(render_config(state)["inbounds"]), 4)
        second["enabled"] = True
        self.assertEqual(len(render_config(state)["inbounds"]), 5)
        self.assertEqual(render_config(state)["inbounds"][-1]["tag"], "anytls-second")

    def test_invalid_legacy_tags_get_stable_unique_display_names(self):
        invalid_tag = "_legacy"
        colliding_name = "legacy-" + uuid.uuid5(uuid.UUID(NAMESPACE), f"anytls:{invalid_tag}").hex
        self.anytls["inbounds"][0]["tag"] = invalid_tag
        self.proxy["inbounds"][0]["tag"] = colliding_name
        self.proxy["inbounds"][1]["tag"] = "emoji-🚀"
        state = self.imported()
        self.assertEqual([node["name"] for node in state["nodes"][:3]],
                         [colliding_name + "-2", colliding_name,
                          "legacy-" + uuid.uuid5(uuid.UUID(NAMESPACE), "proxy:emoji-🚀").hex])
        self.assertEqual(state, self.imported())
        self.assertEqual(render_config(state)["inbounds"],
                         self.anytls["inbounds"] + self.proxy["inbounds"])
        self.assertEqual(state["nodes"][0]["inbound"]["tag"], invalid_tag)

    def test_legacy_credentials_validate_uuid_and_shadowsocks_key(self):
        for protocol in ("vmess", "vless"):
            for credential in ("not-a-uuid", str(uuid.UUID(int=0))):
                document = copy.deepcopy(self.proxy)
                node = next(item for item in document["inbounds"] if item["type"] == protocol)
                node["users"][0]["uuid"] = credential
                with self.subTest(protocol=protocol, credential=credential), self.assertRaises(InvalidInventory):
                    import_legacy(self.anytls, document, migration_namespace=NAMESPACE)
            document = copy.deepcopy(self.proxy)
            node = next(item for item in document["inbounds"] if item["type"] == protocol)
            node["users"][0]["uuid"] = "5F601A0F-F0D7-42F9-BC15-C51D72175801"
            state = import_legacy(self.anytls, document, migration_namespace=NAMESPACE)
            self.assertEqual(state["nodes"][[n["protocol"] for n in state["nodes"]].index(protocol)]["inbound"]["users"][0]["uuid"],
                             node["users"][0]["uuid"])
        for key in ("invalid", "AAAAAAAAAAAAAAAAAAAAAA=", "AAAAAAAAAAAAAAAAAAAAAA== ",
                    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", "AAAAAAAAAAAAAAAAAAAAAB=="):
            document = copy.deepcopy(self.proxy)
            document["inbounds"][-1]["password"] = key
            with self.subTest(key=key), self.assertRaises(InvalidInventory):
                import_legacy(self.anytls, document, migration_namespace=NAMESPACE)
        state = self.imported()
        self.assertEqual(state["nodes"][-1]["inbound"]["password"], "AAAAAAAAAAAAAAAAAAAAAA==")
        self.anytls["inbounds"][0]["users"][0]["password"] = "x"
        self.proxy["inbounds"][2]["users"][0]["password"] = "y"
        state = self.imported()
        self.assertEqual(state["nodes"][0]["inbound"]["users"][0]["password"], "x")
        self.assertEqual(state["nodes"][3]["inbound"]["users"][0]["password"], "y")

    def test_reject_ambiguous_legacy_inputs(self):
        cases = []
        other = copy.deepcopy(self.proxy)
        other["inbounds"][0]["listen_port"] = 20001
        cases.append((self.anytls, other))
        other = copy.deepcopy(self.proxy)
        other["inbounds"][0]["tag"] = "anytls-in"
        cases.append((self.anytls, other))
        other = copy.deepcopy(self.proxy)
        other["route"]["final"] = "block"
        cases.append((self.anytls, other))
        other = copy.deepcopy(self.proxy)
        other["inbounds"].append(inbound("unknown", 30000, "new"))
        cases.append((self.anytls, other))
        other = copy.deepcopy(self.proxy)
        other["inbounds"][0]["tls"]["certificate_path"] = None
        cases.append((self.anytls, other))
        cases.extend([(None, None), (b'{"inbounds":[],"inbounds":[]}', None),
                      (b'{"inbounds": [', None)])
        for a, b in cases:
            with self.subTest(a=a, b=b), self.assertRaises(InvalidInventory):
                import_legacy(a, b, migration_namespace=NAMESPACE)

    def test_invalid_state_fails_closed(self):
        baseline = self.imported()
        edits = [lambda s: s["nodes"][0].update(name=" invalid "),
                 lambda s: s["nodes"][0].update(name=""),
                 lambda s: s["nodes"][0].update(id=s["nodes"][1]["id"]),
                 lambda s: s["nodes"][0].update(port=30000),
                 lambda s: s["nodes"][0].update(port=True),
                 lambda s: s["nodes"][0].update(cap_bytes=0),
                 lambda s: s["nodes"][0].update(expires_at="tomorrow"),
                 lambda s: s["nodes"][0].update(expires_at="2030-01-01T00:00:00"),
                 lambda s: s["nodes"][0].update(upload_bytes=-1),
                 lambda s: s["nodes"][0].update(enabled=1),
                 lambda s: s["nodes"][0]["inbound"].update(tag="direct")]
        for edit in edits:
            state = copy.deepcopy(baseline)
            edit(state)
            with self.subTest(edit=edit), self.assertRaises(InvalidInventory):
                render_config(state)

    def test_no_filesystem_writes(self):
        from unittest.mock import patch
        with patch("builtins.open", side_effect=AssertionError("filesystem access")), \
             patch("pathlib.Path.open", side_effect=AssertionError("filesystem access")):
            render_config(self.imported())


if __name__ == "__main__":
    unittest.main()
