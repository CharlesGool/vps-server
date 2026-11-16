"""Encryption at rest: plain fallback, legacy files, binding, tampering, migration (temp dirs only)."""
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import secure_store as ss  # noqa: E402


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.keyfile = self.tmp / "etc" / "data.key"
        self.data = self.tmp / "state" / "data"
        self.data.mkdir(parents=True)
        os.environ["VPSSRV_DATA_KEY_FILE"] = str(self.keyfile)
        os.environ["VPSSRV_STATE_DIR"] = str(self.tmp / "state")
        os.environ.pop("VPSSRV_DATA_DIR", None)
        ss._cache.clear()

    def tearDown(self):
        for name in ("VPSSRV_DATA_KEY_FILE", "VPSSRV_STATE_DIR"):
            os.environ.pop(name, None)
        ss._cache.clear()

    def test_without_a_key_everything_stays_plain(self):
        path = self.data / "alerts.json"
        ss.write_text(path, '{"key": "abc"}')
        self.assertEqual(path.read_bytes(), b'{"key": "abc"}')
        self.assertEqual(ss.read_text(path), '{"key": "abc"}')
        self.assertFalse(ss.enabled())

    def test_init_makes_a_private_key_once(self):
        self.assertTrue(ss.init_key())
        self.assertEqual(stat.S_IMODE(os.stat(self.keyfile).st_mode), 0o600)
        first = self.keyfile.read_text()
        self.assertFalse(ss.init_key())
        self.assertEqual(self.keyfile.read_text(), first)
        self.assertEqual(len(bytes.fromhex(first.strip())), 32)
        self.assertEqual([p.name for p in self.keyfile.parent.iterdir()], ["data.key"])

    def test_encrypted_round_trip_and_nothing_readable_on_disk(self):
        ss.init_key()
        path = self.data / "alerts.json"
        secret = '{"key": "very-secret-bark-key"}'
        ss.write_text(path, secret)
        raw = path.read_bytes()
        self.assertTrue(raw.startswith(ss.MAGIC))
        self.assertNotIn(b"very-secret", raw)
        self.assertEqual(ss.read_text(path), secret)
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        ss.write_text(path, secret)
        self.assertNotEqual(path.read_bytes(), raw)                 # a fresh nonce every time
        self.assertEqual([p.name for p in self.data.iterdir()], ["alerts.json"])

    def test_a_file_cannot_be_swapped_for_another(self):
        ss.init_key()
        ss.write_text(self.data / "alerts.json", "alerts")
        shutil.copy(self.data / "alerts.json", self.data / "console-access.json")
        with self.assertRaises(ss.SecureStoreError):
            ss.read_text(self.data / "console-access.json")

    def test_tampering_wrong_key_and_missing_key_fail_loudly(self):
        ss.init_key()
        path = self.data / "sessions.json"
        ss.write_text(path, "state")
        raw = path.read_bytes()
        path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
        with self.assertRaises(ss.SecureStoreError):
            ss.read_text(path)
        path.write_bytes(raw[:10])
        with self.assertRaises(ss.SecureStoreError):
            ss.read_text(path)
        path.write_bytes(raw)
        self.assertEqual(ss.read_text(path), "state")
        self.keyfile.write_text(os.urandom(32).hex() + "\n")
        ss._cache.clear()       # a rewrite inside one timestamp tick would otherwise look unchanged
        with self.assertRaises(ss.SecureStoreError):
            ss.read_text(path)
        self.keyfile.unlink()
        with self.assertRaises(ss.SecureStoreError):
            ss.read_text(path)
        self.assertIsInstance(ss.SecureStoreError("x"), ValueError)      # callers that catch ValueError keep working

    def test_a_bad_key_file_is_an_error_not_plain_mode(self):
        self.keyfile.parent.mkdir(parents=True)
        for text in ("nothex", "ab" * 16, ""):
            self.keyfile.write_text(text)
            ss._cache.clear()
            with self.assertRaises(ss.SecureStoreError):
                ss.write_text(self.data / "alerts.json", "x")

    def test_legacy_plain_files_are_read_then_encrypted_by_migrate(self):
        names = ("alerts.json", "sessions.json", "session_secret.txt")
        for name in names:
            (self.data / name).write_text(f"plain {name}")
        ss.init_key()
        self.assertEqual(ss.read_text(self.data / "alerts.json"), "plain alerts.json")
        changed = {p.name for p in ss.migrate()}
        self.assertEqual(changed, set(names))
        for name in names:
            self.assertTrue((self.data / name).read_bytes().startswith(ss.MAGIC))
            self.assertEqual(ss.read_text(self.data / name), f"plain {name}")
        self.assertEqual(ss.migrate(), [])                                   # idempotent
        self.assertEqual({p.name for p in ss.migrate(decrypt_instead=True)}, set(names))
        self.assertEqual((self.data / "alerts.json").read_text(), "plain alerts.json")

    def test_password_file_and_missing_files(self):
        (self.tmp / "state" / "admin_password.txt").write_text("hunter2hunter2\n")
        ss.init_key()
        self.assertIn(self.tmp / "state" / "admin_password.txt", ss.managed_files())
        self.assertEqual([p.name for p in ss.migrate()], ["admin_password.txt"])
        self.assertEqual(ss.read_text(self.tmp / "state" / "admin_password.txt").strip(), "hunter2hunter2")

    def test_log_records_are_encrypted_one_by_one(self):
        ss.init_key()
        line = ss.seal_line('{"ip": "203.0.113.9"}', "security-audit.jsonl")
        self.assertTrue(line.startswith(ss.LINE_PREFIX))
        self.assertNotIn("203.0.113.9", line)
        self.assertEqual(ss.open_line(line, "security-audit.jsonl"), '{"ip": "203.0.113.9"}')
        self.assertEqual(ss.open_line("plain old line", "security-audit.jsonl"), "plain old line")
        with self.assertRaises(ss.SecureStoreError):
            ss.open_line(line, "other.jsonl")
        with self.assertRaises(ss.SecureStoreError):
            ss.open_line(ss.LINE_PREFIX + "!!!", "security-audit.jsonl")

    def test_audit_log_migration_keeps_every_record(self):
        log = self.data / "security-audit.jsonl"
        log.write_text('{"n": 1}\n{"n": 2}\n')
        ss.init_key()
        self.assertEqual([p.name for p in ss.migrate()], ["security-audit.jsonl"])
        lines = log.read_text().splitlines()
        self.assertTrue(all(l.startswith(ss.LINE_PREFIX) for l in lines))
        self.assertEqual([ss.open_line(l, log.name) for l in lines], ['{"n": 1}', '{"n": 2}'])
        self.assertEqual(ss.migrate(), [])
        ss.migrate(decrypt_instead=True)
        self.assertEqual(log.read_text(), '{"n": 1}\n{"n": 2}\n')

    def test_status_reports_each_file(self):
        (self.data / "alerts.json").write_text("{}")
        ss.init_key()
        (self.data / "sessions.json").write_bytes(ss.encrypt(b"{}", "sessions.json"))
        status = dict((Path(p).name, s) for p, s in ss.status())
        self.assertEqual(status, {"alerts.json": "plain", "sessions.json": "encrypted"})


class CertificateKeyTest(StoreTest):
    """TLS and CA private keys: decrypted only in memory, or in a short-lived private copy."""

    def make_pair(self):
        if not shutil.which("openssl"):
            self.skipTest("openssl not available")
        import subprocess
        cert, key = self.tmp / "cert.pem", self.tmp / "key.pem"
        try:
            subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                            "-nodes", "-keyout", str(key), "-out", str(cert), "-subj", "/CN=localhost", "-days", "2"],
                           check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("openssl cannot make a certificate")
        return cert, key

    def test_plain_and_encrypted_keys_both_load_into_a_tls_context(self):
        import ssl
        cert, key = self.make_pair()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ss.load_cert_chain(context, cert, key)                      # plain key (no data key yet)
        ss.init_key()
        key.write_bytes(ss.encrypt(key.read_bytes(), key.name))
        self.assertNotIn(b"PRIVATE KEY", key.read_bytes())
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ss.load_cert_chain(context, cert, key)                      # encrypted key, memory only
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir() if p.name.startswith(".")), [])

    def test_a_key_that_cannot_be_decrypted_is_an_error(self):
        import ssl
        cert, key = self.make_pair()
        ss.init_key()
        key.write_bytes(ss.encrypt(key.read_bytes(), "other-name.pem"))
        with self.assertRaises(ss.SecureStoreError):
            ss.load_cert_chain(ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER), cert, key)

    def test_decrypted_copy_is_private_and_matches(self):
        ss.init_key()
        path = self.tmp / "client-ca.key"
        ss.write_bytes(path, b"CA PRIVATE KEY BYTES")
        work = self.tmp / "work"
        work.mkdir()
        copy = ss.decrypted_copy(path, work)
        self.assertEqual(copy.read_bytes(), b"CA PRIVATE KEY BYTES")
        self.assertEqual(stat.S_IMODE(os.stat(copy).st_mode), 0o600)
        self.assertTrue(path.read_bytes().startswith(ss.MAGIC))

    def test_certificate_keys_are_managed_files(self):
        certs = self.tmp / "state" / "certs"
        certs.mkdir(parents=True)
        (certs / "key.pem").write_text("TLS KEY")
        (certs / "client-ca.key").write_text("CA KEY")
        ss.init_key()
        self.assertEqual({p.name for p in ss.migrate()}, {"key.pem", "client-ca.key"})
        self.assertEqual(ss.read_text(certs / "client-ca.key"), "CA KEY")


if __name__ == "__main__":
    unittest.main()
