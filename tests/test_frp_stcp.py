"""STCP proxy/visitor support in frp_control (no root, no systemd, no frpc binary)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import frp_control as fc  # noqa: E402

KEY = "k" * 32
BASE = {"server": "203.0.113.5", "port": 7000, "token": "tok"}


def build(proxies=(), visitors=()):
    return fc.build_client(BASE["server"], BASE["port"], BASE["token"], list(proxies), list(visitors))


def stcp(name="web", key=KEY):
    return {"name": name, "type": "stcp", "localIP": "127.0.0.1", "localPort": 8080, "secretKey": key}


def visitor(name="v", port=9000, key=KEY):
    return {"name": name, "type": "stcp", "serverName": "web", "secretKey": key,
            "bindAddr": "127.0.0.1", "bindPort": port}


class StcpTest(unittest.TestCase):
    def roundtrip(self, text):
        with tempfile.TemporaryDirectory() as directory:
            old = fc.CLIENT_DIR
            fc.CLIENT_DIR = Path(directory)
            try:
                (Path(directory) / "frpc-t.toml").write_text(text)
                return fc.structured_client("t")
            finally:
                fc.CLIENT_DIR = old

    def test_stcp_has_no_remote_port(self):
        text = build([stcp()])
        self.assertIn('type = "stcp"', text)
        self.assertNotIn("remotePort", text)
        self.assertEqual(fc._local_client_ports(text), set())

    def test_roundtrip_proxy_and_visitor(self):
        tcp = {"name": "t", "type": "tcp", "localIP": "127.0.0.1", "localPort": 1, "remotePort": 2}
        data = self.roundtrip(build([tcp, stcp()], [visitor()]))
        self.assertEqual(data["proxies"], [tcp, stcp()])
        self.assertEqual(data["visitors"], [visitor()])

    def test_visitor_port_always_reserved_even_for_remote_server(self):
        self.assertEqual(fc._local_client_ports(build([], [visitor(port=9000)])), {9000})

    def test_visitor_only_on_loopback(self):
        bad = dict(visitor(), bindAddr="0.0.0.0")
        with self.assertRaises(ValueError):
            build([], [bad])
        self.assertIsNone(self.roundtrip(build([], [visitor()]).replace("127.0.0.1\"\nbindPort", "0.0.0.0\"\nbindPort")))

    def test_rejects_wrong_fields_and_duplicates(self):
        with self.assertRaises(ValueError):
            build([dict(stcp(), remotePort=5)])
        with self.assertRaises(ValueError):
            build([stcp("x")], [visitor("x")])  # proxies and visitors share a namespace
        with self.assertRaises(ValueError):
            build([], [visitor("a", 9000), visitor("b", 9000)])
        with self.assertRaises(ValueError):
            build([stcp(key="a\nb")])

    def test_unmanaged_fields_not_dropped(self):
        text = build([stcp()]) + 'allowUsers = ["x"]\n'
        self.assertIsNone(self.roundtrip(text))

    def test_normalize_generates_and_keeps_secret(self):
        new = {"name": "w", "type": "stcp", "localIP": "127.0.0.1", "localPort": 1, "secretKey": ""}
        made = fc._normalize_proxy(new)
        self.assertGreaterEqual(len(made["secretKey"]), fc.MIN_SECRET)
        self.assertEqual(fc._normalize_proxy(new, made)["secretKey"], made["secretKey"])
        with self.assertRaises(ValueError):
            fc._normalize_proxy(dict(new, secretKey="short"))
        converted = fc._normalize_proxy({"name": "w", "type": "tcp", "localIP": "127.0.0.1", "localPort": 1,
                                         "remotePort": 9, "secretKey": "ignored"})
        self.assertNotIn("secretKey", converted)

    def test_visitor_edit_blank_keeps_secret(self):
        kept = fc._normalize_visitor(dict(visitor(), secretKey=""), visitor())
        self.assertEqual(kept["secretKey"], KEY)
        with self.assertRaises(ValueError):
            fc._normalize_visitor(dict(visitor(), secretKey=""))


if __name__ == "__main__":
    unittest.main()
