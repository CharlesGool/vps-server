"""Configuration backups: contents, retention, safe restore (temp dirs only)."""
import io
import os
import stat
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


class SealedBackupTest(BackupTest):
    """The same fixtures, with an encryption key on the host and a recipient set for backups."""

    def setUp(self):
        super().setUp()
        import secure_store
        self.store = secure_store
        os.environ["VPSSRV_DATA_KEY_FILE"] = str(self.etc / "data.key")
        secure_store._cache.clear()
        secure_store.init_key()

    def tearDown(self):
        os.environ.pop("VPSSRV_DATA_KEY_FILE", None)
        self.store._cache.clear()
        super().tearDown()

    def test_without_a_recipient_the_data_key_stays_out_of_the_archive(self):
        name = cb.create_backup("manual", self.out)
        self.assertFalse(name.endswith(".sealed"))
        self.assertFalse([n for n in self.names(name) if n.endswith("data.key")])
        self.assertIn(str(self.etc / "state.json").lstrip("/"), self.names(name))

    def test_with_a_recipient_the_archive_is_sealed_and_carries_the_key(self):
        private, public = cb.new_recipient()
        name = cb.create_backup("manual", self.out)
        self.assertTrue(name.endswith(".tar.gz.sealed"))
        raw = (self.out / name).read_bytes()
        self.assertTrue(raw.startswith(cb.SEALED_MAGIC_2))
        self.assertNotIn(b"SECRET", raw)
        self.assertTrue(cb.is_sealed(self.out / name))
        self.assertEqual([i["sealed"] for i in cb.list_backups(self.out)], [True])
        self.assertEqual(cb.backup_path(name, self.out).name, name)
        plain = cb.open_sealed_file(self.out / name, cb.parse_key(private))
        with tarfile.open(fileobj=io.BytesIO(plain)) as archive:
            self.assertTrue([m for m in archive.getnames() if m.endswith("data.key")])
        self.assertEqual(cb.key_fingerprint(cb.parse_key(public)), cb.key_fingerprint(cb.read_recipient()))

    def test_only_the_private_key_restores_a_sealed_backup(self):
        private, _ = cb.new_recipient()
        name = cb.create_backup("manual", self.out)
        (self.state / "certs" / "key.pem").write_text("CHANGED")
        with self.assertRaises(cb.BackupError):
            cb.restore(self.out / name, self.out)                                # no key
        other = cb.base64.b64encode(os.urandom(32)).decode()
        with self.assertRaises(cb.BackupError):
            cb.restore(self.out / name, self.out, cb.parse_key(other))          # wrong key
        self.assertEqual((self.state / "certs" / "key.pem").read_text(), "CHANGED")
        result = cb.restore(self.out / name, self.out, cb.parse_key(private))
        self.assertEqual((self.state / "certs" / "key.pem").read_text(), "SECRET")
        self.assertGreater(result["restored"], 0)
        self.assertEqual([p.name for p in self.out.iterdir() if p.name.startswith(".unsealed")], [])

    def test_a_damaged_sealed_backup_is_refused(self):
        private, _ = cb.new_recipient()
        name = cb.create_backup("manual", self.out)
        path = self.out / name
        raw = path.read_bytes()
        path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
        with self.assertRaises(cb.BackupError):
            cb.restore(path, self.out, cb.parse_key(private))
        path.write_bytes(cb.SEALED_MAGIC + b"short")
        with self.assertRaises(cb.BackupError):
            cb.validate_archive(path)

    def test_sealed_backups_name_their_key_and_older_ones_still_open(self):
        private, public = cb.new_recipient()
        name = cb.create_backup("manual", self.out)
        path = self.out / name
        self.assertEqual(cb.sealed_key_id(path), cb.key_id(cb.parse_key(public)))
        self.assertTrue(cb.key_matches(path))
        # a backup made before v7.0.1 has no key id: it still opens, and nothing can be said about its key
        plain = cb.open_sealed_file(path, cb.parse_key(private))
        old = self.out / "config-20200101T000000Z-manual.tar.gz.sealed"
        old.write_bytes(cb.SEALED_MAGIC + cb.crypto_box.seal(cb.parse_key(public), plain, cb.SEAL_AAD))
        self.assertIsNone(cb.sealed_key_id(old))
        self.assertIsNone(cb.key_matches(old))
        self.assertEqual(cb.open_sealed_file(old, cb.parse_key(private)), plain)
        self.assertIsNone([i for i in cb.list_backups(self.out) if i["name"] == old.name][0]["key_match"])
        # after the backup key is replaced, the earlier backups are sealed to another key
        cb.new_recipient()
        self.assertFalse(cb.key_matches(path))
        self.assertFalse([i for i in cb.list_backups(self.out) if i["name"] == name][0]["key_match"])

    def test_inspect_reads_a_plain_backup_and_flags_what_is_risky(self):
        name = cb.create_backup("manual", self.out)
        info = cb.inspect(self.out / name)
        self.assertEqual((info["sealed"], info["readable"], info["same_host"], info["newer"], info["risky"]),
                         (False, True, True, False, False))
        self.assertEqual((info["kind"], info["host"]), ("manual", cb.socket.gethostname()))
        self.assertGreater(info["files"], 0)
        original = cb.socket.gethostname
        cb.socket.gethostname = lambda: "some-other-host"
        try:
            other = cb.inspect(self.out / name)
        finally:
            cb.socket.gethostname = original
        self.assertEqual((other["same_host"], other["risky"]), (False, True))
        os.environ["VPSSRV_BACKUP_VERSION"] = "99.0.0"
        try:
            newer_name = cb.create_backup("manual", self.out)
        finally:
            os.environ.pop("VPSSRV_BACKUP_VERSION", None)
        newer = cb.inspect(self.out / newer_name)
        self.assertEqual((newer["version"], newer["newer"], newer["risky"]), ("99.0.0", True, True))

    def test_inspect_a_sealed_backup_needs_its_key_and_leaves_nothing_behind(self):
        private, _ = cb.new_recipient()
        name = cb.create_backup("manual", self.out)
        locked = cb.inspect(self.out / name)
        self.assertEqual((locked["sealed"], locked["readable"], locked["key_match"]), (True, False, True))
        self.assertNotIn("host", locked)
        opened = cb.inspect(self.out / name, cb.parse_key(private))
        self.assertEqual((opened["readable"], opened["same_host"]), (True, True))
        with self.assertRaises(cb.BackupError):
            cb.inspect(self.out / name, cb.parse_key(cb.base64.b64encode(os.urandom(32)).decode()))
        self.assertEqual([p.name for p in self.out.iterdir() if p.name.startswith(".")], [])

    def test_the_restore_command_records_how_it_went(self):
        self.assertIsNone(cb.read_result())
        name = cb.create_backup("manual", self.out)
        self.assertEqual(cb.main(["restore", str(self.out / name)]), 0)
        result = cb.read_result()
        self.assertTrue(result["ok"])
        self.assertEqual((result["name"], result["restored"] > 0), (name, True))
        self.assertTrue(result["before"].endswith(".tar.gz"))
        junk = self.out / "config-20200101T000000Z-manual.tar.gz"
        junk.write_bytes(b"not a backup")
        self.assertEqual(cb.main(["restore", str(junk)]), 1)
        failed = cb.read_result()
        self.assertFalse(failed["ok"])
        self.assertEqual(failed["name"], junk.name)
        self.assertEqual(stat.S_IMODE(os.stat(cb.result_file()).st_mode), 0o600)

    def test_keys_are_parsed_strictly(self):
        for bad in ("", "not base64!!", "AAAA", cb.base64.b64encode(bytes(33)).decode(), None):
            with self.assertRaises(cb.BackupError, msg=str(bad)):
                cb.parse_key(bad)

    def test_pruning_and_names_cover_sealed_files(self):
        cb.new_recipient()
        names = [cb.create_backup("scheduled", self.out) for _ in range(4)]
        self.assertEqual(len(set(names)), 4)
        self.assertEqual(len(cb.prune("scheduled", 2, self.out)), 2)
        self.assertEqual(len(cb.list_backups(self.out)), 2)


if __name__ == "__main__":
    unittest.main()
