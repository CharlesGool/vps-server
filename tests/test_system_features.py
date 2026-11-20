"""Resource monitor, file helper, API tokens and fleet: logic that needs no root and no network."""
import json
import os
import shutil
import sys
import tarfile
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
os.environ.setdefault("VPSSRV_DATA_KEY_FILE", "/nonexistent/vps-server-test-key")
import api_tokens  # noqa: E402
import fleet  # noqa: E402
import sysadmin  # noqa: E402
import sysmon  # noqa: E402
from features import api_monitor  # noqa: E402


class MonitorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_snapshot_reads_this_host(self):
        monitor = sysmon.Monitor(self.tmp)
        monitor.sample()
        snapshot = monitor.snapshot()
        self.assertGreater(snapshot["memory"]["total"], 0)
        self.assertGreaterEqual(snapshot["cpu"]["cores"], 1)
        self.assertEqual(len(snapshot["load"]), 3)
        self.assertTrue(all(0 <= row["percent"] <= 100 for row in snapshot["disks"]))

    def test_live_points_keep_the_last_minute(self):
        monitor = sysmon.Monitor(self.tmp)
        for _ in range(sysmon.LIVE_POINTS + 3):
            monitor.sample()
        live = monitor.live_points()
        self.assertEqual(len(live), sysmon.LIVE_POINTS)
        self.assertTrue(all(len(point) == 5 for point in live))

    def test_history_is_bucketed(self):
        now = 1_000_000
        points = [[now - 3600 * hour, 10.0 * (hour % 3), 50.0, 100, 200] for hour in range(30)]
        rows = api_monitor.buckets(points, 12, now=now)
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(row[1] is not None for row in rows))
        empty = api_monitor.buckets([], 24, now=now)
        self.assertTrue(all(row[1] is None for row in empty))

    def test_alert_thresholds_are_checked(self):
        self.assertIsNone(sysmon.clamp_alerts({"disk": 10}))
        self.assertIsNone(sysmon.clamp_alerts({"enabled": "yes"}))
        self.assertEqual(sysmon.clamp_alerts({"disk": 80})["disk"], 80)

    def test_alerts_fire_once_a_day(self):
        sent = []
        monitor = sysmon.Monitor(self.tmp, notify=lambda title, body: sent.append(title),
                                 failed_units=lambda: ["vps-server-web.service"])
        snapshot = {"disks": [{"mount": "/", "percent": 95.0}], "memory": {"used": 1, "total": 100},
                    "cpu": {"percent": 1.0}}
        self.assertEqual(sorted(monitor.check_alerts(snapshot)), ["disk:/", "unit:vps-server-web.service"])
        self.assertEqual(monitor.check_alerts(snapshot), [])
        self.assertEqual(len(sent), 2)

    def test_gpu_alerts_and_buckets(self):
        sent = []
        monitor = sysmon.Monitor(self.tmp, notify=lambda title, body: sent.append(body))
        snapshot = {"disks": [], "memory": {"used": 1, "total": 100}, "cpu": {"percent": 1.0},
                    "gpus": [{"name": "RTX 5090", "utilization": 99, "memoryUsed": 98, "memoryTotal": 100, "celsius": 90}]}
        self.assertEqual(sorted(monitor.check_alerts(snapshot)), ["gpu-memory:0", "gpu-temp:0"])
        now = 1_000_000
        points = [[now - 30, [[10, 20, 50], [30, 40, 60]]], [now - 20, [[20, 30, 50], [50, 60, 60]]]]
        rows = api_monitor.gpu_buckets(points, 15, 900, now=now)
        self.assertEqual(rows[-1][1], [[15.0, 25.0, 50.0], [40.0, 50.0, 60.0]])
        self.assertIsNone(rows[0][1])
        self.assertEqual(sysmon.Monitor.gpu_point([{"utilization": None, "memoryUsed": None, "memoryTotal": None, "celsius": None}]), [[0, 0, 0]])

    def test_history_survives_a_restart(self):
        monitor = sysmon.Monitor(self.tmp)
        monitor.record()
        monitor.stop()
        self.assertEqual(len(sysmon.Monitor(self.tmp).points()), 1)


class SysadminFilesTest(unittest.TestCase):
    """The helper's file operations, called directly (the root check is only in main())."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.staging = os.path.join(self.root, "staging")
        os.mkdir(self.staging)

    def run_op(self, **request):
        return sysadmin.handle(request, self.staging)

    def test_create_rename_copy_move_delete(self):
        folder = os.path.join(self.root, "a")
        self.run_op(action="mkdir", path=folder)
        self.run_op(action="touch", path=os.path.join(folder, "f.txt"))
        self.run_op(action="rename", path=os.path.join(folder, "f.txt"), name="g.txt")
        target = os.path.join(self.root, "b")
        os.mkdir(target)
        self.run_op(action="copy", paths=[folder], destination=target)
        self.assertTrue(os.path.isfile(os.path.join(target, "a", "g.txt")))
        self.run_op(action="move", paths=[os.path.join(folder, "g.txt")], destination=target)
        self.assertTrue(os.path.isfile(os.path.join(target, "g.txt")))
        self.run_op(action="delete", paths=[folder, os.path.join(target, "g.txt")])
        self.assertFalse(os.path.exists(folder))

    def test_refusals(self):
        with self.assertRaises(sysadmin.Refused):
            self.run_op(action="delete", paths=["/etc"])
        with self.assertRaises(sysadmin.Refused):
            self.run_op(action="mkdir", path="/proc/x")
        with self.assertRaises(sysadmin.Refused):
            self.run_op(action="rename", path=os.path.join(self.root, "x"), name="../y")
        with self.assertRaises(sysadmin.Refused):
            self.run_op(action="mkdir", path="relative/path")
        folder = os.path.join(self.root, "c")
        os.mkdir(folder)
        with self.assertRaises(sysadmin.Refused):
            self.run_op(action="move", paths=[folder], destination=folder)
        with self.assertRaises(sysadmin.Refused):
            self.run_op(action="chmod", path=folder, mode="999")
        with self.assertRaises(sysadmin.Refused):
            self.run_op(action="unknown")

    def test_write_from_staging_keeps_mode(self):
        path = os.path.join(self.root, "conf")
        Path(path).write_text("old")
        os.chmod(path, 0o600)
        staged = os.path.join(self.staging, "up-1")
        Path(staged).write_text("new")
        with self.assertRaises(sysadmin.Refused):
            self.run_op(action="write", staging=staged, path=path)
        self.run_op(action="write", staging=staged, path=path, overwrite=True)
        self.assertEqual(Path(path).read_text(), "new")
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertFalse(os.path.exists(staged))
        with self.assertRaises(sysadmin.Refused):
            self.run_op(action="write", staging=path, path=os.path.join(self.root, "other"))

    def test_compress_and_extract(self):
        folder = os.path.join(self.root, "data")
        os.mkdir(folder)
        Path(folder, "one.txt").write_text("1")
        for kind in ("zip", "tar.gz"):
            archive = os.path.join(self.root, f"data.{kind}")
            self.run_op(action="compress", paths=[folder], target=archive, format=kind)
            out = os.path.join(self.root, "out-" + kind.replace(".", ""))
            os.mkdir(out)
            self.run_op(action="extract", path=archive, destination=out)
            self.assertEqual(Path(out, "data", "one.txt").read_text(), "1")

    def test_unsafe_archives_are_refused(self):
        bad_zip = os.path.join(self.root, "bad.zip")
        with zipfile.ZipFile(bad_zip, "w") as bundle:
            bundle.writestr("../escape.txt", "x")
        bad_tar = os.path.join(self.root, "bad.tar")
        with tarfile.open(bad_tar, "w") as bundle:
            info = tarfile.TarInfo("link")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            bundle.addfile(info)
        out = os.path.join(self.root, "out")
        os.mkdir(out)
        for archive in (bad_zip, bad_tar):
            with self.assertRaises(sysadmin.Refused):
                self.run_op(action="extract", path=archive, destination=out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "escape.txt")))

    def test_hosts_file_round_trip(self):
        original = ["127.0.0.1\tlocalhost", "192.168.1.29\told-host", "# keep old-host here",
                    "::1     localhost ip6-localhost ip6-loopback"]
        renamed = sysadmin.rename_in_hosts(original, "old-host", "vps-new")
        self.assertEqual(renamed[1], "192.168.1.29\tvps-new")
        self.assertEqual(renamed[2], "# keep old-host here")
        self.assertEqual(len(renamed), len(original))
        self.assertEqual(sysadmin.rename_in_hosts(renamed, "vps-new", "old-host"), original)
        debian = ["127.0.0.1 localhost", "127.0.1.1 old.example.net old"]
        self.assertEqual(sysadmin.rename_in_hosts(debian, "old", "new")[1], "127.0.1.1 old.example.net new")
        self.assertEqual(sysadmin.rename_in_hosts(["127.0.0.1 localhost"], "gone", "new"),
                         ["127.0.0.1 localhost", "127.0.1.1\tnew"])

    def test_hostname_is_validated(self):
        for name in ("bad_name", "-x", "a" * 64, "", "a..b"):
            with self.assertRaises(sysadmin.Refused):
                sysadmin.set_hostname({"name": name})


class TokensTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.tokens = api_tokens.ApiTokens(Path(self.tmp) / "api-tokens.json")

    def test_create_verify_delete(self):
        token, row = self.tokens.create("script", "read")
        self.assertTrue(token.startswith("vpss_"))
        stored = (Path(self.tmp) / "api-tokens.json").read_text()
        self.assertNotIn(token, stored)
        entry = self.tokens.verify(token, "198.51.100.1")
        self.assertEqual(entry["scope"], "read")
        self.assertEqual(self.tokens.listing()[0]["lastIp"], "198.51.100.1")
        self.assertIsNone(self.tokens.verify(token + "x", "198.51.100.1"))
        self.assertIsNone(self.tokens.verify("not-a-token", "198.51.100.1"))
        self.tokens.delete(row["id"])
        self.assertIsNone(self.tokens.verify(token, "198.51.100.1"))

    def test_limits(self):
        with self.assertRaises(api_tokens.TokenError):
            self.tokens.create("", "read")
        with self.assertRaises(api_tokens.TokenError):
            self.tokens.create("x", "admin")
        for index in range(api_tokens.LIMIT):
            self.tokens.create(f"t{index}", "read")
        with self.assertRaises(api_tokens.TokenError):
            self.tokens.create("one more", "read")


class FleetTest(unittest.TestCase):
    def test_urls(self):
        self.assertEqual(fleet.parse_url("https://203.0.113.5:20000"), ("203.0.113.5", 20000))
        self.assertEqual(fleet.parse_url("https://[2001:db8::1]:443/"), ("2001:db8::1", 443))
        for url in ("http://a:1", "https://a", "https://a:1/path", "https://a:99999", None):
            with self.assertRaises(fleet.FleetError):
                fleet.parse_url(url)

    def test_fingerprint_format(self):
        self.assertEqual(len(fleet.fingerprint_of(b"x")), 95)

    def test_add_checks_before_connecting(self):
        store = fleet.Fleet(Path(tempfile.mkdtemp()) / "fleet.json")
        with self.assertRaises(fleet.FleetError):
            store.add("", "https://a:1", "vpss_x", "pin", "0" * 95)
        with self.assertRaises(fleet.FleetError):
            store.add("a", "https://a:1", "token", "pin", "0" * 95)
        with self.assertRaises(fleet.FleetError):
            store.add("a", "https://a:1", "vpss_x", "other", "0" * 95)


if __name__ == "__main__":
    unittest.main()
