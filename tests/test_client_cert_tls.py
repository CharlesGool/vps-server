"""Client certificates: the CA named in the TLS request, and the shared macOS rule."""
import ctypes
import os
import json
import plistlib
import shutil
import subprocess
import ssl
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import cert_setup  # noqa: E402
import client_cert as cc  # noqa: E402


def client_ca_names(context):
    """How many CA names the context sends in its certificate request."""
    lib = cc._libssl()
    lib.SSL_CTX_get_client_CA_list.restype = ctypes.c_void_p
    lib.SSL_CTX_get_client_CA_list.argtypes = [ctypes.c_void_p]
    lib.OPENSSL_sk_num.restype = ctypes.c_int
    lib.OPENSSL_sk_num.argtypes = [ctypes.c_void_p]
    pointer = ctypes.c_void_p.from_address(id(context) + object.__basicsize__).value
    names = lib.SSL_CTX_get_client_CA_list(pointer)
    return lib.OPENSSL_sk_num(names) if names else 0


@unittest.skipUnless(cc.openssl_binary(), "needs openssl")
class ClientCaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        os.environ["VPSSRV_DATA_KEY_FILE"] = str(Path(self.tmp) / "no-data.key")
        self.addCleanup(os.environ.pop, "VPSSRV_DATA_KEY_FILE", None)
        self.auth = cc.ClientAuth(Path(self.tmp))

    def test_request_names_the_ca(self):
        if cc._libssl() is None:
            self.skipTest("no libssl through ctypes")
        self.auth.issue("phone")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.assertEqual(client_ca_names(context), 0)
        self.auth.configure(context)
        self.assertEqual(client_ca_names(context), 1)

    def test_mismatched_context_is_left_alone(self):
        self.auth.issue("phone")
        self.assertFalse(cc.advertise_client_ca(object(), self.auth.ca_cert))

    def test_device_certificate_carries_the_organization(self):
        _bundle, _password, entry = self.auth.issue("phone")
        with tempfile.TemporaryDirectory(dir=self.tmp) as work:
            self.auth._sign_client(work, "ab" * 16, 1)
            decoded = ssl._ssl._test_decode_cert(str(Path(work) / "client.pem"))
        subject = dict(pair for group in decoded["subject"] for pair in group)
        self.assertEqual(subject["organizationName"], cc.CLIENT_ORG)
        self.assertTrue(entry["cn"].startswith("vps-server client "))


    def make_legacy_ca(self):
        """A CA as early hosts made it: the shared name, no host."""
        self.auth.cert_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.tmp) as work:
            self.auth._openssl(work, "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                               "-nodes", "-keyout", str(self.auth.ca_key), "-out", str(self.auth.ca_cert),
                               "-days", "30", "-subj", f"/CN={cc.LEGACY_CA_CN}",
                               "-addext", "basicConstraints=critical,CA:TRUE",
                               "-addext", "keyUsage=critical,keyCertSign,cRLSign")
            old = Path(work) / "old"
            old.mkdir()
            self.auth._sign_client(old, "cd" * 16, 1)
            return (old / "client.pem").read_bytes()

    def verifies(self, pem):
        with tempfile.NamedTemporaryFile(dir=self.tmp, suffix=".pem") as handle:
            handle.write(pem)
            handle.flush()
            return subprocess.run([cc.openssl_binary(), "verify", "-CAfile", str(self.auth.ca_cert), handle.name],
                                  capture_output=True).returncode == 0

    def test_legacy_ca_gets_a_host_named_ca_and_stays_trusted(self):
        old_pem = self.make_legacy_ca()
        self.assertEqual(self.auth.issuer_cn(), cc.LEGACY_CA_CN)
        self.auth.issue("mac")
        self.assertEqual(self.auth.issuer_cn(), f"{cc.LEGACY_CA_CN} {cc.host_label()}")
        self.assertEqual(self.auth.ca_cert.read_bytes().count(b"BEGIN CERTIFICATE"), 2)
        self.assertTrue(self.verifies(old_pem))
        with tempfile.TemporaryDirectory(dir=self.tmp) as work:
            self.auth._sign_client(work, "ef" * 16, 1)
            self.assertTrue(self.verifies((Path(work) / "client.pem").read_bytes()))
        if cc._libssl() is not None:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            self.auth.configure(context)
            self.assertEqual(client_ca_names(context), 2)
        bundle = self.auth.ca_cert.read_bytes()
        self.auth.issue("phone")  # replaced once only
        self.assertEqual(self.auth.ca_cert.read_bytes(), bundle)

    def test_failed_self_test_keeps_the_legacy_ca(self):
        self.make_legacy_ca()
        before = self.auth.ca_cert.read_bytes(), self.auth.ca_key.read_bytes()
        self.auth.self_test = lambda: False
        self.assertFalse(self.auth._replace_legacy_ca())
        self.assertEqual((self.auth.ca_cert.read_bytes(), self.auth.ca_key.read_bytes()), before)


class MacosProfileTest(unittest.TestCase):
    T = {"client_cert_autoselect": "auto"}

    def rules(self, profile):
        data = plistlib.loads(profile)
        chrome = next(item for item in data["PayloadContent"] if item["PayloadType"] == "com.google.Chrome")
        return data, chrome["AutoSelectCertificateForUrls"]

    def test_every_host_writes_the_same_rule(self):
        one = self.rules(cert_setup.macos_profile(self.T, "vps-server client a 11111111", "CA a", ["https://a:1"]))[1]
        two = self.rules(cert_setup.macos_profile(self.T, "vps-server client b 22222222", "CA b", ["https://b:2"]))[1]
        self.assertEqual(one, two)
        self.assertEqual(json.loads(one[0]), {"pattern": "*", "filter": {"SUBJECT": {"O": cc.CLIENT_ORG}}})

    def test_rule_only_profile_never_replaces_a_certificate_profile(self):
        with_cert, _ = self.rules(cert_setup.macos_profile(self.T, "vps-server client a 11111111", "CA", [], b"p12"))
        rules_only, _ = self.rules(cert_setup.macos_profile(self.T, "vps-server client a 11111111", "CA", []))
        self.assertNotEqual(with_cert["PayloadIdentifier"], rules_only["PayloadIdentifier"])
        self.assertEqual(rules_only["PayloadIdentifier"], cert_setup.MACOS_RULES_ID)
        self.assertEqual([item["PayloadType"] for item in plistlib.loads(
            cert_setup.macos_profile(self.T, "s 1", "CA", [], b"p12"))["PayloadContent"]][0], "com.apple.security.pkcs12")


if __name__ == "__main__":
    unittest.main()
