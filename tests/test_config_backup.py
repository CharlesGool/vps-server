"""Configuration backups: contents, retention, safe restore (temp dirs only)."""
import io
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import config_backup as cb  # noqa: E402


class BackupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.state = self.tmp / "state"
        (self.state / "data" / "files" / "blobs").mkdir(parents=True)
        (self.state / "certs").mkdir()
        (self.state / "data" / "files" / "blobs" / "big").write_bytes(b"x" * 1000)
        (self.state / "data" / "files" / "index.json").write_text("{}")
        (self.state / "data" / "sessions.json").write_text("{}")
        (self.state / "certs" / "key.pem").write_text("SECRET")
        (self.state / "tailscale").mkdir()
        (self.state / "tailscale" / "tailscaled.state").write_text("login")
        self.etc = self.tmp / "etc" / "vps-server-nodes"
        self.etc.mkdir(parents=True)
        (self.etc / "state.json").write_text("{}")
        os.environ["VPSSRV_STATE_DIR"] = str(self.state)
        os.environ.pop("VPSSRV_DATA_DIR", None)
        self.saved = (cb.SYSTEM_DIRS, cb.SYSTEM_GLOBS)
        cb.SYSTEM_DIRS = (str(self.etc),)
        cb.SYSTEM_GLOBS = ()
        self.out = self.tmp / "out"

    def tearDown(self):
        cb.SYSTEM_DIRS, cb.SYSTEM_GLOBS = self.saved
        os.environ.pop("VPSSRV_STATE_DIR", None)

    def names(self, name):
        with tarfile.open(self.out / name) as archive:
            return {m.name for m in archive.getmembers()}

    def test_contains_config_and_tailscale_but_not_drive_files_or_backups(self):
        name = cb.create_backup("manual", self.out)
        names = self.names(name)
        rel = lambda p: str(p).lstrip("/")
        self.assertIn(rel(self.state / "certs" / "key.pem"), names)
        self.assertIn(rel(self.state / "tailscale" / "tailscaled.state"), names)
        self.assertIn(rel(self.etc / "state.json"), names)
        self.assertFalse([n for n in names if "/files/" in n or n.endswith("/files")])
        self.assertIn(cb.MANIFEST, names)

    def test_backup_directory_is_never_included(self):
        inside = self.state / "backups"
        cb.create_backup("manual", inside)
        name = cb.create_backup("manual", self.out)
        self.assertFalse([n for n in self.names(name) if "/backups" in n])

    def test_two_backups_in_the_same_second_do_not_overwrite_each_other(self):
        names = {cb.create_backup("manual", self.out) for _ in range(4)}
        self.assertEqual(len(names), 4)
        self.assertEqual(len(cb.list_backups(self.out)), 4)
        self.assertEqual([p.name for p in self.out.iterdir() if p.name.startswith(".")], [])

    def test_file_mode_and_listing(self):
        name = cb.create_backup("scheduled", self.out)
        self.assertEqual(os.stat(self.out / name).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(self.out).st_mode & 0o777, 0o700)
        listing = cb.list_backups(self.out)
        self.assertEqual([i["name"] for i in listing], [name])
        self.assertEqual(listing[0]["kind"], "scheduled")

    def test_prune_keeps_newest_of_one_kind_only(self):
        for stamp in ("20260101T000000Z", "20260102T000000Z", "20260103T000000Z"):
            (self.out).mkdir(exist_ok=True)
            (self.out / f"config-{stamp}-scheduled.tar.gz").write_bytes(b"x")
        (self.out / "config-20250101T000000Z-manual.tar.gz").write_bytes(b"x")
        removed = cb.prune("scheduled", 2, self.out)
        self.assertEqual(removed, ["config-20260101T000000Z-scheduled.tar.gz"])
        self.assertEqual(len(cb.list_backups(self.out)), 3)

    def test_names_are_validated(self):
        for bad in ("../x", "config-1-manual.tar.gz", "config-20260101T000000Z-evil.tar.gz", 5):
            with self.assertRaises(cb.BackupError):
                cb.backup_path(bad, self.out)

    def test_restore_round_trip_and_pre_restore_backup(self):
        name = cb.create_backup("manual", self.out)
        (self.state / "certs" / "key.pem").write_text("CHANGED")
        (self.etc / "state.json").unlink()
        result = cb.restore(self.out / name, self.out)
        self.assertEqual((self.state / "certs" / "key.pem").read_text(), "SECRET")
        self.assertTrue((self.etc / "state.json").exists())
        self.assertTrue(any(i["kind"] == "pre-restore" for i in cb.list_backups(self.out)))
        self.assertGreater(result["restored"], 0)

    def make(self, entries):
        path = self.tmp / "evil.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            manifest = b'{"format": 1}'
            info = tarfile.TarInfo(cb.MANIFEST)
            info.size = len(manifest)
            archive.addfile(info, io.BytesIO(manifest))
            for name, kind in entries:
                info = tarfile.TarInfo(name)
                if kind == "link":
                    info.type, info.linkname = tarfile.SYMTYPE, "/etc/passwd"
                    archive.addfile(info)
                else:
                    info.size = 1
                    archive.addfile(info, io.BytesIO(b"x"))
        return path

    def test_restore_rejects_paths_outside_configuration(self):
        for name in ("etc/passwd", "../../etc/passwd", "/etc/passwd", "root/.ssh/authorized_keys"):
            with self.assertRaises(cb.BackupError, msg=name):
                cb.validate_archive(self.make([(name, "file")]))
        with self.assertRaises(cb.BackupError):
            cb.validate_archive(self.make([(str(self.state).lstrip("/") + "/x", "link")]))

    def test_restore_rejects_non_backup_and_wrong_format(self):
        junk = self.tmp / "junk.tar.gz"
        junk.write_bytes(b"not a tar")
        with self.assertRaises(cb.BackupError):
            cb.validate_archive(junk)
        path = self.tmp / "nomanifest.tar.gz"
        with tarfile.open(path, "w:gz"):
            pass
        with self.assertRaises(cb.BackupError):
            cb.validate_archive(path)

    def test_systemd_unit_files_are_allowed_only_by_pattern(self):
        cb.SYSTEM_GLOBS = (("/etc/systemd/system", "vps-server-*"),)
        ok = tarfile.TarInfo("etc/systemd/system/vps-server-web.service")
        ok.size = 1
        cb._check_member(ok)
        dropin = tarfile.TarInfo("etc/systemd/system/vps-server-proxy.service.d/x.conf")
        dropin.size = 1
        cb._check_member(dropin)
        bad = tarfile.TarInfo("etc/systemd/system/sshd.service")
        bad.size = 1
        with self.assertRaises(cb.BackupError):
            cb._check_member(bad)


if __name__ == "__main__":
    unittest.main()
