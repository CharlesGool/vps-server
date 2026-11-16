"""Release signatures: Ed25519 verification, key pinning and the installer policy (offline)."""
import base64
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import ed25519  # noqa: E402
import release_trust as rt  # noqa: E402

# Made with OpenSSL 3: openssl pkeyutl -sign -rawin over MESSAGE.
PUB = base64.b64decode("O/sOW9XwaQu1wMGKKDiIhOkmTfDYRV8H/UhqrGlXNoQ=")
SIG = base64.b64decode("lfRJMbJrZHAkHpU5XcgAPLVHyvSvxuxTdcjsHw2nnRt0qML9qQJxxcjZu5QELbGttvA7fafI099IBWaSitBoBA==")
MESSAGE = b"vps-server test vector\n"
OTHER = bytes(range(32))


def openssl_sign(message):
    """(public key, signature) for a fresh key, or None when OpenSSL cannot do Ed25519."""
    if not shutil.which("openssl"):
        return None
    with tempfile.TemporaryDirectory() as tmp:
        key, msg, out = (os.path.join(tmp, n) for n in ("k.pem", "m", "s"))
        with open(msg, "wb") as handle:
            handle.write(message)
        try:
            subprocess.run(["openssl", "genpkey", "-algorithm", "ED25519", "-out", key], check=True, capture_output=True)
            der = subprocess.run(["openssl", "pkey", "-in", key, "-pubout", "-outform", "DER"],
                                 check=True, capture_output=True).stdout
            subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey", key, "-rawin", "-in", msg, "-out", out],
                           check=True, capture_output=True)
        except (subprocess.CalledProcessError, OSError):
            return None
        with open(out, "rb") as handle:
            return der[-32:], handle.read()


class Ed25519Test(unittest.TestCase):
    def test_openssl_vector(self):
        self.assertTrue(ed25519.verify(PUB, MESSAGE, SIG))

    def test_any_change_is_rejected(self):
        self.assertFalse(ed25519.verify(PUB, MESSAGE + b" ", SIG))
        self.assertFalse(ed25519.verify(PUB, MESSAGE, SIG[:-1] + bytes([SIG[-1] ^ 1])))
        self.assertFalse(ed25519.verify(PUB, MESSAGE, bytes([SIG[0] ^ 1]) + SIG[1:]))
        self.assertFalse(ed25519.verify(OTHER, MESSAGE, SIG))

    def test_malformed_inputs_are_rejected_not_raised(self):
        for key, sig in ((PUB[:31], SIG), (PUB + b"x", SIG), (PUB, SIG[:63]), (PUB, SIG + b"x"), (b"", b""),
                         (None, SIG), (PUB, None), ("text", SIG)):
            self.assertFalse(ed25519.verify(key, MESSAGE, sig))
        # a scalar S at or above the group order is not a valid signature
        big = (ed25519.Q).to_bytes(32, "little")
        self.assertFalse(ed25519.verify(PUB, MESSAGE, SIG[:32] + big))
        # a point that is not on the curve
        self.assertFalse(ed25519.verify(bytes([2]) + bytes(31), MESSAGE, SIG))

    def test_fresh_openssl_keys_agree(self):
        for message in (b"a", b"SHA256SUMS\n" * 50):
            made = openssl_sign(message)
            if made is None:
                self.skipTest("openssl with Ed25519 not available")
            key, signature = made
            self.assertTrue(ed25519.verify(key, message, signature))
            self.assertFalse(ed25519.verify(key, message + b"x", signature))


class KeyTest(unittest.TestCase):
    def test_round_trip_and_comment(self):
        text = rt.format_key(PUB)
        self.assertEqual(rt.parse_key(text), PUB)
        self.assertEqual(rt.parse_key(text.strip() + " vps-server-release\n"), PUB)

    def test_bad_keys(self):
        for text in ("", "ed25519", "rsa AAAA", "ed25519 !!!!", "ed25519 " + base64.b64encode(b"short").decode(),
                     "ed25519 " + base64.b64encode(bytes(33)).decode()):
            with self.assertRaises(rt.TrustError, msg=text):
                rt.parse_key(text)

    def test_fingerprint_form_and_matching(self):
        fp = rt.fingerprint(PUB)
        self.assertRegex(fp, r"([0-9a-f]{4}:){7}[0-9a-f]{4}")
        self.assertTrue(rt.same_fingerprint(fp, PUB))
        self.assertTrue(rt.same_fingerprint(fp.upper().replace(":", " "), PUB))
        self.assertFalse(rt.same_fingerprint(fp, OTHER))
        self.assertFalse(rt.same_fingerprint("", PUB))
        self.assertFalse(rt.same_fingerprint("ffa9", PUB))  # too short to be a fingerprint


class SumsTest(unittest.TestCase):
    sums = (b"a" * 64 + b"  vps-server-v1.2.3-linux-amd64.tar.gz\n" + b"b" * 64 + b" *vps-server-v1.2.3-linux-amd64-online.tar.gz\n")

    def signed(self, text):
        made = openssl_sign(text)
        if made is None:
            self.skipTest("openssl with Ed25519 not available")
        return made

    def test_valid_signature_returns_entries(self):
        key, sig = self.signed(self.sums)
        entries = rt.verify_sums(self.sums, sig, key)
        self.assertEqual(entries["vps-server-v1.2.3-linux-amd64.tar.gz"], "a" * 64)
        self.assertEqual(entries["vps-server-v1.2.3-linux-amd64-online.tar.gz"], "b" * 64)
        self.assertEqual(rt.verify_sums(self.sums, base64.b64encode(sig) + b"\n", key), entries)

    def test_tampered_sums_or_wrong_key_are_refused(self):
        key, sig = self.signed(self.sums)
        with self.assertRaises(rt.TrustError):
            rt.verify_sums(self.sums.replace(b"a" * 64, b"c" * 64), sig, key)
        with self.assertRaises(rt.TrustError):
            rt.verify_sums(self.sums, sig, OTHER)
        with self.assertRaises(rt.TrustError):
            rt.verify_sums(self.sums, b"not a signature", key)
        with self.assertRaises(rt.TrustError):
            rt.verify_sums(self.sums, sig[:10], key)

    def test_malformed_but_signed_sums_are_refused(self):
        for text in (b"\n", b"nothex  file\n", b"a" * 64 + b"  ../evil\n", b"a" * 64 + b" file name\n"):
            key, sig = self.signed(text)
            with self.assertRaises(rt.TrustError, msg=text):
                rt.verify_sums(text, sig, key)


class SignToolTest(unittest.TestCase):
    """tools/sign-release talks to a remote host; here the runner is replaced."""

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "sign-release"))
        import sign_release
        self.tool = sign_release

    def test_remote_command_quotes_paths_and_never_writes_the_key_locally(self):
        script = self.tool.remote_script("/keys/my dir; rm -rf /", "signing-key.pem", "passphrase.txt")
        self.assertIn("'/keys/my dir; rm -rf //signing-key.pem'".replace("//", "/"), script)
        self.assertIn("-passin file:", script)
        self.assertIn("-rawin", script)
        self.assertNotIn("passphrase.txt |", script)

    def test_sign_returns_the_decoded_signature_and_reports_failures(self):
        calls = []

        class Done:
            returncode, stdout, stderr = 0, base64.b64encode(SIG), b""

        def runner(command, **kwargs):
            calls.append((command, kwargs["input"]))
            return Done

        self.assertEqual(self.tool.sign(b"data", "nas", "/k", runner=runner), SIG)
        self.assertEqual(calls[0][0][:2], ["ssh", "nas"])
        self.assertEqual(calls[0][1], b"data")

        class Failed:
            returncode, stdout, stderr = 1, b"", b"bad passphrase"

        with self.assertRaises(SystemExit):
            self.tool.sign(b"data", "nas", "/k", runner=lambda *a, **k: Failed)


class PolicyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.state = self.tmp / "state"
        self.package = self.tmp / "pkg"
        (self.package / "config").mkdir(parents=True)

    def ship(self, raw):
        (self.package / "config" / "release-key.pub").write_text(rt.format_key(raw))

    def test_decide_table(self):
        self.assertEqual(rt.decide(None, None), "unsigned")
        self.assertEqual(rt.decide(None, PUB), "pin")
        self.assertEqual(rt.decide(PUB, PUB), "ok")
        self.assertEqual(rt.decide(PUB, OTHER), "changed")
        self.assertEqual(rt.decide(PUB, None), "unsigned-refused")

    def test_first_signed_install_pins_and_private_file(self):
        self.ship(PUB)
        code, verdict, *_ = rt.installer_check(self.state, self.package)
        self.assertEqual((code, verdict), (0, "pin"))
        self.assertIsNone(rt.read_pinned(self.state))               # check never writes
        self.assertEqual(rt.install_pin(self.state, self.package), PUB)
        self.assertEqual(rt.read_pinned(self.state), PUB)
        self.assertEqual(stat.S_IMODE(os.stat(rt.pinned_path(self.state)).st_mode), 0o600)
        self.assertEqual(rt.installer_check(self.state, self.package)[:2], (0, "ok"))

    def test_other_signers_and_unsigned_packages_are_refused_once_pinned(self):
        rt.write_pinned(self.state, PUB)
        self.ship(OTHER)
        self.assertEqual(rt.installer_check(self.state, self.package)[:2], (3, "changed"))
        (self.package / "config" / "release-key.pub").unlink()
        self.assertEqual(rt.installer_check(self.state, self.package)[:2], (3, "unsigned-refused"))

    def test_key_change_needs_the_new_fingerprint(self):
        rt.write_pinned(self.state, PUB)
        self.ship(OTHER)
        for wrong in ("", rt.fingerprint(PUB), "0000:0000:0000:0000:0000:0000:0000:0000"):
            self.assertEqual(rt.installer_check(self.state, self.package, wrong)[0], 3, wrong)
        self.assertEqual(rt.installer_check(self.state, self.package, rt.fingerprint(OTHER))[:2], (0, "accepted"))
        rt.install_pin(self.state, self.package)
        self.assertEqual(rt.read_pinned(self.state), OTHER)

    def test_unpinned_unsigned_package_installs_and_pins_nothing(self):
        self.assertEqual(rt.installer_check(self.state, self.package)[:2], (0, "unsigned"))
        self.assertIsNone(rt.install_pin(self.state, self.package))
        self.assertFalse(rt.pinned_path(self.state).exists())

    def test_versions(self):
        self.assertLess(rt.version_tuple("v6.5.0"), rt.version_tuple("6.10.0"))
        self.assertEqual(rt.version_tuple("v1.2.3"), (1, 2, 3))
        for bad in ("", "v1.2", "1.2.3-test.1", "latest"):
            with self.assertRaises(rt.TrustError, msg=bad):
                rt.version_tuple(bad)


if __name__ == "__main__":
    unittest.main()
