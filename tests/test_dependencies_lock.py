"""Offline tests for the vendored-artifact checksum verifier."""

import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from tools.verify_dependencies.verify_dependencies import ROOT, verify


class DependencyLockTest(unittest.TestCase):
    def test_checkout_covers_recorded_vendored_artifacts(self):
        root = Path(__file__).resolve().parents[1]
        lock = root / "config/dependencies.lock.json"
        artifacts = json.loads(lock.read_text(encoding="utf-8"))["artifacts"]
        self.assertEqual({item["path"] for item in artifacts}, {
            "third_party/sing-box/sing-box", "third_party/lucky/lucky", "third_party/frp/frps",
            "static/third_party/librespeed/speedtest.js",
            "static/third_party/librespeed/speedtest_worker.js",
            "static/third_party/qrcode/qrcode.js", "static/third_party/qrcode/qrcode-utf8.js",
        })
        self.assertEqual(ROOT, root)
        with redirect_stdout(StringIO()):
            self.assertTrue(verify(lock, root))
        for name in ("third_party/lucky/lucky", "third_party/frp/frps"):
            entry = next(item for item in artifacts if item["path"] == name)
            self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), entry["sha256"])

    def test_valid_and_modified_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "vendor.js").write_bytes(b"original")
            lock = root / "lock.json"
            lock.write_text(json.dumps({
                "schema_version": 1,
                "artifacts": [{"path": "vendor.js", "sha256": hashlib.sha256(b"original").hexdigest()}],
            }), encoding="utf-8")
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertTrue(verify(lock, root))
                (root / "vendor.js").write_bytes(b"modified")
                self.assertFalse(verify(lock, root))
                (root / "vendor.js").unlink()
                self.assertFalse(verify(lock, root))

    def test_rejects_duplicate_and_escaping_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = root / "lock.json"
            artifact = {"path": "../outside", "sha256": "0" * 64}
            lock.write_text(json.dumps({"schema_version": 1, "artifacts": [artifact]}), encoding="utf-8")
            with redirect_stderr(StringIO()):
                self.assertFalse(verify(lock, root))
            artifact["path"] = "vendor.js"
            lock.write_text(json.dumps({"schema_version": 1, "artifacts": [artifact, artifact]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                verify(lock, root)


if __name__ == "__main__":
    unittest.main()
