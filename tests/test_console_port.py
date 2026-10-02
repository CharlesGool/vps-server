"""Console port changes keep the listener record and application in sync."""

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.web import console_port


class ConsolePortTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.prefix = self.root / "vps-server"
        (self.prefix / "data").mkdir(parents=True)
        self.port_file = self.prefix / "console_port.txt"
        self.port_file.write_text("44816\n")
        console_port.write_rows(self.root / "PORTS.md", [
            (44816, console_port.OWNER, "0.0.0.0", date.today().isoformat()),
            (5201, "iperf3", "0.0.0.0", date.today().isoformat()),
        ])

    def test_success_replaces_only_own_port(self):
        calls = []
        with patch.object(console_port, "reserved_ports", return_value={80, 443, 5201}):
            console_port.change_port(self.prefix, 44816, 44817, self.port_file,
                                     restart=lambda: calls.append("restart"),
                                     wait=lambda port: calls.append(port),
                                     probe=lambda port: calls.append(("probe", port)))
        rows, _ = console_port.read_rows(self.root / "PORTS.md")
        self.assertEqual({row[0] for row in rows}, {5201, 44817})
        self.assertEqual(self.port_file.read_text(), "44817\n")
        self.assertEqual((self.prefix / "data/console-port-override").read_text(), "44817\n")
        self.assertEqual(calls, [("probe", 44817), "restart", 44817])

    def test_failed_listener_restores_old_port_and_record(self):
        original = (self.root / "PORTS.md").read_bytes()
        waits = []

        def wait(port):
            waits.append(port)
            if port == 44817:
                raise RuntimeError("new listener failed")

        with patch.object(console_port, "reserved_ports", return_value={80, 443, 5201}):
            with self.assertRaisesRegex(RuntimeError, "new listener failed"):
                console_port.change_port(self.prefix, 44816, 44817, self.port_file,
                                         restart=lambda: None, wait=wait, probe=lambda port: None)
        self.assertEqual(waits, [44817, 44816])
        self.assertEqual((self.root / "PORTS.md").read_bytes(), original)
        self.assertEqual(self.port_file.read_text(), "44816\n")
        self.assertFalse((self.prefix / "data/console-port-override").exists())

    def test_reserved_port_never_changes_listener(self):
        with patch.object(console_port, "reserved_ports", return_value={443, 44817}):
            with self.assertRaisesRegex(ValueError, "reserved"):
                console_port.change_port(self.prefix, 44816, 44817, self.port_file,
                                         restart=lambda: self.fail("must not restart"),
                                         probe=lambda port: self.fail("must not probe"))
        self.assertEqual(self.port_file.read_text(), "44816\n")
