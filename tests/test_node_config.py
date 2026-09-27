"""Offline inbound candidate checks; no installed files or service are changed."""

import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
from node_config import InvalidNodeChange, check_candidate, prepare_candidate


UUID = "5f601a0f-f0d7-42f9-bc15-c51d72175801"
KEY = "AAAAAAAAAAAAAAAAAAAAAA=="


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.anytls = {"inbounds": [{"type": "anytls", "listen_port": 20000,
                                     "users": [{"password": "old-secret"}]}]}
        self.proxy = {"inbounds": [
            {"type": "vmess", "listen_port": 40000, "users": [{"uuid": UUID}]},
            {"type": "vless", "listen_port": 45000, "users": [{"uuid": UUID}]},
            {"type": "trojan", "listen_port": 50000, "users": [{"password": "old-secret"}]},
            {"type": "shadowsocks", "listen_port": 55000,
             "method": "2022-blake3-aes-128-gcm", "password": KEY}
        ]}

    def candidate(self, protocol="anytls", port=21000, credential="new-secret", reserved=(80, 443, 33333)):
        return prepare_candidate(protocol, port, credential, self.anytls, self.proxy, reserved)

    def test_independent_copy_and_allowlisted_fields(self):
        original = copy.deepcopy(self.anytls)
        module, candidate = self.candidate()
        self.assertEqual(module, "anytls")
        self.assertEqual(candidate["inbounds"][0]["listen_port"], 21000)
        self.assertEqual(candidate["inbounds"][0]["users"][0]["password"], "new-secret")
        self.assertEqual(self.anytls, original)
        module, candidate = self.candidate("shadowsocks", 55555, KEY)
        self.assertEqual((module, candidate["inbounds"][3]["listen_port"]), ("proxy", 55555))

    def test_reject_invalid_inputs_and_collisions(self):
        cases = [
            ("unknown", 21000, "new-secret", ()),
            ("anytls", True, "new-secret", ()),
            ("anytls", 65536, "new-secret", ()),
            ("anytls", 45000, "new-secret", ()),
            ("anytls", 33333, "new-secret", (80, 33333)),
            ("anytls", 21000, "bad\npassword", ()),
            ("vless", 47000, "not-a-uuid", ()),
            ("shadowsocks", 56000, "short", ()),
        ]
        for protocol, port, credential, reserved in cases:
            with self.subTest(protocol=protocol, port=port, credential=credential):
                with self.assertRaises(InvalidNodeChange):
                    self.candidate(protocol, port, credential, reserved)

    def test_fail_closed_on_malformed_installed_state(self):
        self.proxy["inbounds"][0]["listen_port"] = 20000
        with self.assertRaises(InvalidNodeChange):
            self.candidate()
        self.proxy = None
        with self.assertRaises(InvalidNodeChange):
            self.candidate("vmess", 41000, UUID)
        self.anytls["inbounds"][0]["users"].append({"password": "second"})
        with self.assertRaises(InvalidNodeChange):
            self.candidate()

    def test_validation_failure_removes_stage_and_does_not_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "sing-box"
            binary.write_text("#!/bin/sh\nexit 1\n")
            binary.chmod(0o700)
            with self.assertRaises(subprocess.CalledProcessError):
                check_candidate({"inbounds": []}, directory, binary)
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["sing-box"])

    def test_check_uses_0600_stage_without_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "sing-box"
            binary.write_text("#!/bin/sh\nexit 0\n")
            binary.chmod(0o700)
            def inspect(command, **kwargs):
                self.assertEqual(command[:3], [str(binary), "check", "-c"])
                self.assertEqual(os.stat(command[3]).st_mode & 0o777, 0o600)
                self.assertFalse(kwargs.get("shell", False))
            with patch("node_config.subprocess.run", side_effect=inspect):
                check_candidate({"inbounds": []}, directory, binary)
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["sing-box"])


if __name__ == "__main__":
    unittest.main()
