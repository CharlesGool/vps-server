"""Proxy nodes: console requests in, the sing-box configuration (and node state) out.

Runs node_control.apply_request() for real against temporary files: a fake backend
stands in for systemd, sing-box check and the firewall, and the self-signed
certificate is faked, so no root, sing-box binary or network is needed. Only the
stable parts of the generated document are asserted, not the whole of it.
"""
import base64
import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolation  # noqa: E402,F401

import node_control as nc  # noqa: E402
import node_inventory as ni  # noqa: E402
import tls_cert  # noqa: E402

PROTOCOL_PORTS = {"anytls": 21001, "vmess": 21002, "vless": 21003, "trojan": 21004, "shadowsocks": 21005}
OUTBOUNDS = [{"type": "direct", "tag": "direct"}, {"type": "block", "tag": "block"}]
FOREIGN_RULE = {"protocol": "dns", "action": "hijack-dns"}
CONSOLE_PORT, IPERF_PORT = 9443, 5201
BAD_NAMES = ('a"b', "a\nb", "a\rb", "{name}", '"},"inbounds":[{"type":"socks"', "<script>", " lead", "trail ",
             "", "_x", "-x", "x" * 65, "a/b", "a\\b", "a\x00b", "a:b", 7, None, ["x"])
BAD_SNI = ('www.example.com"', "www.example.com\n", "{http.request.host}", "a b.example.com", " www.example.com",
           "www..example.com", "-www.example.com", "www.exa_mple.com", "", "x" * 254, 7)


class FakeBackend:
    """Records what node_control asks of systemd, sing-box and the firewall."""

    def __init__(self):
        self.checked, self.firewall_calls, self.services = [], [], []

    def check(self, path):
        self.checked.append(json.loads(Path(path).read_text(encoding="utf-8")))

    def active(self, service):
        return False

    def enabled(self, service):
        return True

    def start(self, service):
        self.services.append(("start", service))

    def stop(self, service):
        self.services.append(("stop", service))

    def restart(self, service):
        self.services.append(("restart", service))

    def reconcile(self, **kwargs):
        pass

    def firewall(self, port, opening, protocol="tcp"):
        self.firewall_calls.append((port, opening, protocol))


class NodeConfigCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.config = self.tmp / "proxy" / "config.json"
        self.config.parent.mkdir()
        self.config.write_text(json.dumps({"log": {"level": "warn"}, "inbounds": [], "outbounds": OUTBOUNDS,
                                           "route": {"final": "direct", "rules": [FOREIGN_RULE]}}))
        self.state = self.tmp / "nodes" / "state.json"
        self.lock = self.tmp / "nodes" / "node.lock"
        data = self.tmp / "data"
        data.mkdir()
        (data / "iperf-port.txt").write_text(f"{IPERF_PORT}\n")
        (data / "console_port.txt").write_text(f"{CONSOLE_PORT}\n")
        app = self.tmp / "apps" / "vps-server"       # the port registry lives beside it
        app.mkdir(parents=True)
        self.registry = self.tmp / "apps" / "PORTS.md"
        self.snis = []

        def certificate(cert, key, server_name):
            self.snis.append(server_name)
            Path(cert).write_text("certificate\n")
            Path(key).write_text("key\n")

        for target, value in ((nc, {"APP_DIR": app, "IPERF_PORT_FILE": data / "iperf-port.txt",
                                    "state_data_dir": lambda: data,
                                    "state_console_port_file": lambda: data / "console_port.txt",
                                    "_free_port": lambda port: None}),
                              (tls_cert, {"create_self_signed": certificate})):
            for name, replacement in value.items():
                patcher = mock.patch.object(target, name, replacement)
                patcher.start()
                self.addCleanup(patcher.stop)
        self.backend = FakeBackend()

    # -- helpers --------------------------------------------------------------

    def apply(self, request):
        return nc.apply_request(request, state_path=self.state, config_paths={"proxy": self.config},
                                lock_path=self.lock, backend=self.backend, require_root=False)

    def create(self, protocol, port, name=None, **extra):
        request = {"action": "create", "protocol": protocol, "name": name or f"{protocol} node", "port": port}
        if protocol != "shadowsocks":
            request["sni"] = "www.example.com"
        request.update(extra)
        return self.apply(request)["nodes"][-1]

    def edit(self, node, **changes):
        return self.apply({"action": "edit", "id": node["id"], **changes})

    def document(self):
        return json.loads(self.config.read_text(encoding="utf-8"))

    def nodes(self):
        return json.loads(self.state.read_text(encoding="utf-8"))["nodes"]

    def inbound(self, node):
        found = [item for item in self.document()["inbounds"] if item["tag"] == node["inbound"]["tag"]]
        return found[0] if len(found) == 1 else None

    def rules_for(self, node):
        tag = node["inbound"]["tag"]
        return [rule for rule in self.document()["route"].get("rules", []) if tag in rule.get("inbound", [])]

    def snapshot(self):
        files = [self.config, self.state, self.registry]
        return {str(path): path.read_bytes() if path.exists() else None for path in files}

    def certificates(self):
        root = self.state.parent / "certs"
        return sorted(str(p.relative_to(root)) for p in root.rglob("*.pem")) if root.exists() else []


class ProtocolTest(NodeConfigCase):
    def test_one_node_of_each_protocol(self):
        created = {protocol: self.create(protocol, port) for protocol, port in PROTOCOL_PORTS.items()}
        document = self.document()
        self.assertEqual([item["type"] for item in document["inbounds"]], list(PROTOCOL_PORTS))
        self.assertEqual(document["outbounds"], OUTBOUNDS)
        self.assertEqual(document["log"], {"level": "warn"})
        # New nodes reach the public Internet only; rules that are not the nodes' stay last.
        self.assertEqual(document["route"]["final"], "direct")
        self.assertEqual(document["route"]["rules"][-1], FOREIGN_RULE)
        self.assertTrue(all(node.get("access") == {"mode": "internet"} for node in self.nodes()))
        credentials = set()
        for protocol, node in created.items():
            inbound = self.inbound(node)
            port = PROTOCOL_PORTS[protocol]
            tag = "node-" + node["id"].replace("-", "")
            self.assertEqual((inbound["type"], inbound["listen"], inbound["listen_port"], inbound["tag"]),
                             (protocol, "::", port, tag))
            if protocol == "shadowsocks":
                self.assertEqual(inbound["method"], "2022-blake3-aes-128-gcm")
                self.assertEqual(len(base64.b64decode(inbound["password"], validate=True)), 16)
                self.assertNotIn("users", inbound)
                self.assertNotIn("tls", inbound)
                credential = inbound["password"]
            else:
                (user,) = inbound["users"]
                self.assertEqual(user["name"], tag)
                if protocol in ("vmess", "vless"):
                    credential = user["uuid"]
                    self.assertEqual(str(uuid.UUID(credential)), credential)
                    self.assertEqual(user.get("alterId"), 0 if protocol == "vmess" else None)
                    self.assertNotIn("password", user)
                else:
                    credential = user["password"]
                    self.assertGreaterEqual(len(credential), 32)
                    self.assertNotIn("uuid", user)
                tls = inbound["tls"]
                self.assertIs(tls["enabled"], True)
                own = self.state.parent / "certs" / node["id"]
                for key in ("certificate_path", "key_path"):
                    self.assertEqual(Path(tls[key]).parent.parent, own)
                    self.assertTrue(Path(tls[key]).is_file())
            credentials.add(credential)
            self.assertIn((port, True, protocol), self.backend.firewall_calls)
        self.assertEqual(len(credentials), 5)
        self.assertEqual(self.snis, ["www.example.com"] * 4)
        # The seed used for a protocol's first node leaves nothing behind.
        text = self.config.read_text()
        for leftover in ("new-node-seed", "/tmp/new-node", "temporary-"):
            self.assertNotIn(leftover, text)
        # The display name is console state only; sing-box sees generated tags.
        for protocol in PROTOCOL_PORTS:
            self.assertNotIn(f"{protocol} node", text)
        stored = {node["protocol"]: node for node in self.nodes()}
        self.assertEqual({p: (n["port"], n["name"], n["enabled"]) for p, n in stored.items()},
                         {p: (port, f"{p} node", True) for p, port in PROTOCOL_PORTS.items()})
        self.assertEqual([item["inbound"] for item in self.nodes()], document["inbounds"])
        registry = self.registry.read_text()
        for node in created.values():
            self.assertIn(f"| {node['port']} | vps-server proxy {node['id']} |", registry)
        self.assertEqual(self.backend.checked[-1], document)    # what sing-box checked is what was installed

    def test_a_second_node_copies_the_protocol_but_not_its_identity(self):
        first = self.create("vless", 21010)
        second = self.create("vless", 21011, sni="cdn.example.net")
        a, b = self.inbound(first), self.inbound(second)
        self.assertNotEqual(a["tag"], b["tag"])
        self.assertNotEqual(a["users"][0]["uuid"], b["users"][0]["uuid"])
        self.assertNotEqual(a["tls"]["certificate_path"], b["tls"]["certificate_path"])
        self.assertEqual(self.snis, ["www.example.com", "cdn.example.net"])

    def test_disable_and_delete_take_the_inbound_out(self):
        keep = self.create("trojan", 21020)
        gone = self.create("vmess", 21021)
        self.apply({"action": "toggle", "id": gone["id"], "enabled": False})
        self.assertIsNone(self.inbound(gone))
        self.assertIsNotNone(self.inbound(keep))
        self.assertIn((21021, False, "vmess"), self.backend.firewall_calls)
        self.assertNotIn("| 21021 |", self.registry.read_text())
        self.apply({"action": "toggle", "id": gone["id"], "enabled": True})
        self.assertIsNotNone(self.inbound(gone))
        self.apply({"action": "delete", "id": gone["id"]})
        self.assertEqual([node["id"] for node in self.nodes()], [keep["id"]])
        self.assertEqual([item["tag"] for item in self.document()["inbounds"]], [keep["inbound"]["tag"]])
        self.assertFalse((self.state.parent / "certs" / gone["id"]).exists())
        self.assertTrue((self.state.parent / "certs" / keep["id"]).exists())

    def test_reset_changes_port_and_credential_only(self):
        node = self.create("anytls", 21030)
        before = self.inbound(node)
        with mock.patch.object(nc.secrets, "randbelow", return_value=1234):
            self.apply({"action": "reset", "id": node["id"]})
        after = self.inbound(node)
        self.assertEqual(after["listen_port"], 21234)
        self.assertNotEqual(after["users"][0]["password"], before["users"][0]["password"])
        self.assertEqual((after["tag"], after["tls"]), (before["tag"], before["tls"]))


class AccessTest(NodeConfigCase):
    def test_unrestricted_internet_and_custom(self):
        free = self.create("shadowsocks", 21101)
        web = self.create("vless", 21102)
        lan = self.create("trojan", 21103)
        destinations = ["10.0.0.0/24:8000-8100", "*.example.com:443", "nas.lan", "[fd00::1]:22", "192.168.1.5"]
        # A new node starts with "internet"; this one is made unrestricted.
        self.edit(free, access=None)
        self.edit(web, access={"mode": "internet"})
        self.edit(lan, access={"mode": "custom", "destinations": destinations})
        route = self.document()["route"]
        self.assertEqual(route["final"], "direct")
        self.assertEqual(route["rules"][-1], FOREIGN_RULE)       # node rules go first, others are kept
        self.assertEqual(self.rules_for(free), [])
        tag = web["inbound"]["tag"]
        self.assertEqual(self.rules_for(web), [
            {"inbound": [tag], "action": "resolve"},
            {"inbound": [tag], "ip_is_private": True, "action": "reject"},
            {"inbound": [tag], "ip_cidr": ni._NON_PUBLIC, "action": "reject"}])
        tag = lan["inbound"]["tag"]
        rules = self.rules_for(lan)
        self.assertEqual(rules[0], {"inbound": [tag], "action": "resolve"})
        self.assertEqual(rules[-1], {"inbound": [tag], "action": "reject"})
        allowed = [{k: v for k, v in rule.items() if k not in ("inbound", "action", "outbound")} for rule in rules[1:-1]]
        self.assertEqual(allowed, [{"ip_cidr": ["10.0.0.0/24"], "port_range": ["8000:8100"]},
                                   {"domain_suffix": [".example.com"], "port": [443]},
                                   {"domain": ["nas.lan"]},
                                   {"ip_cidr": ["fd00::1/128"], "port": [22]},
                                   {"ip_cidr": ["192.168.1.5/32"]}])
        self.assertTrue(all(rule["action"] == "route" and rule["outbound"] == "direct" for rule in rules[1:-1]))
        for rule in route["rules"][:-1]:
            self.assertEqual(len(rule["inbound"]), 1)            # each rule hits exactly one node
        stored = {node["id"]: node.get("access") for node in self.nodes()}
        self.assertEqual(stored[lan["id"]], {"mode": "custom", "destinations": destinations})
        # Back to unrestricted, then off and deleted: the node's rules go with it.
        self.edit(web, access=None)
        self.assertEqual(self.rules_for(web), [])
        self.assertNotIn("access", next(n for n in self.nodes() if n["id"] == web["id"]))
        self.apply({"action": "toggle", "id": lan["id"], "enabled": False})
        self.assertEqual(self.rules_for(lan), [])
        self.apply({"action": "toggle", "id": lan["id"], "enabled": True})
        self.assertEqual(len(self.rules_for(lan)), len(destinations) + 2)
        self.apply({"action": "delete", "id": lan["id"]})
        self.assertEqual(self.document()["route"], {"final": "direct", "rules": [FOREIGN_RULE]})

    def test_bad_destinations_are_refused(self):
        node = self.create("vless", 21110)
        before = self.snapshot()
        for access in ({"mode": "custom", "destinations": ['evil.com"']},
                       {"mode": "custom", "destinations": ["a.example.com\nb.example.com"]},
                       {"mode": "custom", "destinations": ["{http.request.host}"]},
                       {"mode": "custom", "destinations": ["a.example.com}"]},
                       {"mode": "custom", "destinations": ["1.2.3.4:0"]},
                       {"mode": "custom", "destinations": ["*.Example.com"]},      # not canonical
                       {"mode": "custom", "destinations": []},
                       {"mode": "custom", "destinations": "10.0.0.0/8"},
                       {"mode": "internet", "destinations": ["10.0.0.0/8"]},
                       {"mode": "everything"}, "internet", {"mode": "internet", "extra": 1}):
            with self.assertRaises(ValueError, msg=repr(access)):
                self.edit(node, access=access)
            self.assertEqual(self.snapshot(), before, access)


class LimitTest(NodeConfigCase):
    def test_speed_limits_are_node_state_not_sing_box_config(self):
        node = self.create("vmess", 21201)
        config = self.config.read_bytes()
        checks, services = len(self.backend.checked), list(self.backend.services)
        self.edit(node, upload_limit_bps=5_000_000, download_limit_bps=20_000_000, cap_bytes=10 ** 10,
                  cap_action="block")
        stored = self.nodes()[0]
        self.assertEqual((stored["upload_limit_bps"], stored["download_limit_bps"], stored["cap_bytes"],
                          stored["cap_action"]), (5_000_000, 20_000_000, 10 ** 10, "block"))
        # The shaper enforces limits; sing-box is neither rewritten nor restarted for them.
        self.assertEqual(self.config.read_bytes(), config)
        self.assertEqual(len(self.backend.checked), checks)
        self.assertEqual(self.backend.services, services)
        self.edit(node, upload_limit_bps=None, download_limit_bps=None)
        self.assertEqual((self.nodes()[0]["upload_limit_bps"], self.nodes()[0]["download_limit_bps"]), (None, None))

    def test_bad_limits_are_refused(self):
        node = self.create("trojan", 21202)
        before = self.snapshot()
        for changes in ({"upload_limit_bps": 999}, {"download_limit_bps": 10 ** 13 + 1}, {"upload_limit_bps": -1},
                        {"upload_limit_bps": "5000000"}, {"download_limit_bps": True}, {"upload_limit_bps": 1.5e6},
                        {"cap_bytes": 0}, {"cap_bytes": "1"}, {"cap_action": "drop"}, {"speed": 1}):
            with self.assertRaises(ValueError, msg=repr(changes)):
                self.edit(node, **changes)
            self.assertEqual(self.snapshot(), before, changes)


class HostileInputTest(NodeConfigCase):
    def test_bad_names_are_refused_and_leave_nothing_behind(self):
        self.create("shadowsocks", 21300)
        before, certs = self.snapshot(), self.certificates()
        for name in BAD_NAMES:
            for protocol in ("shadowsocks", "trojan"):
                with self.assertRaises(ValueError, msg=repr(name)):
                    self.apply({"action": "create", "protocol": protocol, "name": name, "port": 21301,
                                **({} if protocol == "shadowsocks" else {"sni": "www.example.com"})})
                self.assertEqual(self.snapshot(), before, repr(name))
                self.assertEqual(self.certificates(), certs)

    def test_renaming(self):
        node = self.create("vless", 21310)
        config = self.config.read_bytes()
        for name in BAD_NAMES:
            with self.assertRaises(ValueError, msg=repr(name)):
                self.edit(node, name=name)
        self.edit(node, name="香港 节点-1.b")
        self.assertEqual(self.nodes()[0]["name"], "香港 节点-1.b")
        self.assertEqual(self.config.read_bytes(), config)     # a name never reaches sing-box

    def test_bad_sni_is_refused(self):
        self.create("shadowsocks", 21319)          # the first request creates the node state
        before = self.snapshot()
        for sni in BAD_SNI:
            with self.assertRaises(ValueError, msg=repr(sni)):
                self.create("anytls", 21320, sni=sni)
            self.assertEqual(self.snapshot(), before, repr(sni))
        self.assertEqual(self.certificates(), [])
        self.assertEqual(self.snis, [])
        node = self.create("anytls", 21320, sni="WWW.Example.COM")
        self.assertEqual(self.snis, ["www.example.com"])
        node = self.create("trojan", 21321, sni="203.0.113.9")
        self.assertEqual(self.snis[-1], "203.0.113.9")
        self.assertIsNotNone(self.inbound(node))

    def test_an_ipv6_scope_is_not_an_sni(self):
        # _sni() accepts anything ipaddress accepts, and since Python 3.9 that includes an
        # IPv6 scope ID with arbitrary text after "%": quotes, braces, "&", "#". The value
        # would become the certificate name and the Clash profile's servername.
        for sni in ('fe80::1%"}{', "fe80::1%&security=none#x", "fe80::1%eth0"):
            with self.assertRaises(ValueError, msg=repr(sni)):
                self.create("anytls", 21325, sni=sni)

    def test_credentials_are_escaped_or_refused(self):
        password = 'p"a{s}s\\w0rd\'<>&'
        node = self.create("trojan", 21330, credential=password)
        self.assertEqual(self.inbound(node)["users"][0]["password"], password)   # JSON round trip intact
        before = self.snapshot()
        for protocol, credential in (("trojan", "pass word1"), ("trojan", "pass\nword1"), ("trojan", "short"),
                                     ("anytls", "pässword1"), ("vless", "not-a-uuid"),
                                     ("vless", str(uuid.uuid4()).upper()), ("vless", str(uuid.UUID(int=0))),
                                     ("shadowsocks", base64.b64encode(b"x" * 32).decode()),
                                     ("shadowsocks", "a2V5\n"), ("trojan", password)):   # last one: already used
            with self.assertRaises(ValueError, msg=(protocol, credential)):
                self.create(protocol, 21331, credential=credential)
            self.assertEqual(self.snapshot(), before, (protocol, credential))

    def test_malformed_requests_are_refused(self):
        self.create("vless", 21340)
        before = self.snapshot()
        requests = [
            {"action": "create", "protocol": "socks", "name": "n", "port": 21341},
            {"action": "create", "protocol": "shadowsocks", "name": "n", "port": 21341, "sni": "www.example.com"},
            {"action": "create", "protocol": "vless", "name": "n", "port": 21341},          # TLS needs an SNI
            {"action": "create", "protocol": "vless", "name": "n", "port": 21341, "sni": "www.example.com",
             "inbound": {"type": "socks"}},                                                 # no raw inbounds
            {"action": "create", "protocol": "trojan", "name": "n", "port": "21341", "sni": "www.example.com"},
            {"action": "create", "protocol": "trojan", "name": "n", "port": True, "sni": "www.example.com"},
            {"action": "edit", "id": "../../etc/passwd", "name": "n"},
            {"action": "edit", "id": self.nodes()[0]["id"], "inbound": {"listen": "0.0.0.0"}},
            {"action": "toggle", "id": self.nodes()[0]["id"], "enabled": "false"},
            {"action": "reset", "id": self.nodes()[0]["id"], "port": 1},
            {"action": "install"}, ["create"],
        ]
        for port in (80, 443, CONSOLE_PORT, IPERF_PORT, 21340, 0, 65536):
            requests.append({"action": "create", "protocol": "trojan", "name": "n", "port": port,
                             "sni": "www.example.com"})
        for request in requests:
            with self.assertRaises(ValueError, msg=repr(request)):
                self.apply(request)
            self.assertEqual(self.snapshot(), before, repr(request))



if __name__ == "__main__":
    unittest.main()
