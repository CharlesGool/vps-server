"""Credential apply transaction tests: mocked service/check, real file swaps and flock."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
from node_config import apply_credential, DegradedNodeChange, InvalidNodeChange


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.paths = {name: root / name / "config.json" for name in ("anytls", "proxy")}
        for path in self.paths.values():
            path.parent.mkdir()
        self.original = {"inbounds": [{"type": "anytls", "listen_port": 12345,
                                       "users": [{"password": "old-secret"}]}],
                         "outbounds": [{"type": "direct", "tag": "direct"}]}
        self.paths["anytls"].write_text(json.dumps(self.original))
        self.binary = root / "sing-box"
        self.binary.write_text("#!/bin/sh\nexit 0\n")
        self.binary.chmod(0o700)
        self.lock = root / "node.lock"
        self.commands = []

    def run_apply(self, effect=None):
        def invoke(argv, **kwargs):
            self.commands.append(argv)
            if argv[1] == "check":
                self.assertEqual(os.stat(argv[3]).st_mode & 0o777, 0o600)
                self.assertEqual(json.loads(Path(argv[3]).read_text())["inbounds"][0]["listen_port"], 12345)
            if effect:
                effect(argv)
            return subprocess.CompletedProcess(argv, 0)
        with patch("node_config.os.geteuid", return_value=0), patch("node_config.subprocess.run", side_effect=invoke):
            return apply_credential("anytls", "new-secret", config_paths=self.paths,
                                    binary=self.binary, lock_path=self.lock)

    def assert_old(self):
        self.assertEqual(json.loads(self.paths["anytls"].read_text()), self.original)
        self.assertEqual(list(self.paths["anytls"].parent.iterdir()), [self.paths["anytls"]])

    def test_success_changes_only_credential_and_keeps_port(self):
        self.run_apply()
        expected = json.loads(json.dumps(self.original))
        expected["inbounds"][0]["users"][0]["password"] = "new-secret"
        self.assertEqual(json.loads(self.paths["anytls"].read_text()), expected)
        self.assertEqual(self.paths["anytls"].stat().st_mode & 0o777, 0o600)
        self.assertEqual([c[1] for c in self.commands], ["check", "restart", "is-active"])

    def test_check_failure_does_not_swap_or_restart(self):
        def fail(argv):
            if argv[1] == "check":
                raise subprocess.CalledProcessError(1, argv)
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_apply(fail)
        self.assert_old()
        self.assertEqual(len(self.commands), 1)

    def test_restart_failure_rolls_back_and_restarts_old(self):
        calls = 0
        def fail(argv):
            nonlocal calls
            if argv[1] == "restart":
                calls += 1
                if calls == 1:
                    raise subprocess.CalledProcessError(1, argv)
        with self.assertRaises(InvalidNodeChange):
            self.run_apply(fail)
        self.assert_old()
        self.assertEqual([c[1] for c in self.commands], ["check", "restart", "restart", "is-active"])

    def test_health_check_failure_rolls_back(self):
        calls = 0
        def fail(argv):
            nonlocal calls
            if argv[1] == "is-active":
                calls += 1
                if calls == 1:
                    raise subprocess.CalledProcessError(3, argv)
        with self.assertRaises(InvalidNodeChange):
            self.run_apply(fail)
        self.assert_old()
        self.assertEqual([c[1] for c in self.commands],
                         ["check", "restart", "is-active", "restart", "is-active"])

    def test_recovery_failure_reports_degraded(self):
        def fail(argv):
            if argv[1] == "restart":
                raise subprocess.CalledProcessError(1, argv)
        with self.assertRaises(DegradedNodeChange):
            self.run_apply(fail)
        self.assert_old()

    def test_lock_is_held_through_restart(self):
        def inspect(argv):
            if argv[1] == "restart":
                with open(self.lock, "a+b") as other:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.run_apply(inspect)

    def test_interrupt_after_swap_restores_old(self):
        def interrupt(argv):
            if argv[1] == "restart":
                if not hasattr(self, "interrupted"):
                    self.interrupted = True
                    raise InterruptedError("signal")
        with self.assertRaises(InvalidNodeChange):
            self.run_apply(interrupt)
        self.assert_old()

    def test_reset_scripts_use_same_lock_before_installed_state_read(self):
        root = Path(__file__).resolve().parents[1]
        for module in ("anytls", "proxy"):
            script = (root / "deploy" / module / f"setup-{module}.sh").read_text()
            reset = script.split("\nreset(){", 1)[1].split("\nmain(){", 1)[0]
            self.assertIn("exec {node_lock}>/etc/vps-server-node.lock", reset)
            self.assertLess(reset.index('flock -x "$node_lock"'), reset.index("install_deps"))

    def test_unprivileged_is_rejected_without_changes(self):
        with patch("node_config.os.geteuid", return_value=1000):
            with self.assertRaises(PermissionError):
                apply_credential("anytls", "new-secret", config_paths=self.paths,
                                 binary=self.binary, lock_path=self.lock)
        self.assert_old()


if __name__ == "__main__":
    unittest.main()
