"""File manager safety: recursive chmod/chown, archive extraction, the console's own folders,
helper timeouts and upload staging. Runs without root: ownership changes are mocked."""
import grp
import io
import os
import pwd
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import types
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))

import sysadmin  # noqa: E402
from features import api_filemanager, api_system  # noqa: E402

ME = pwd.getpwuid(os.getuid()).pw_name
MY_GROUP = grp.getgrgid(os.getgid()).gr_name


def usage(free, inodes=10 ** 6):
    return types.SimpleNamespace(f_bavail=free // 4096, f_frsize=4096, f_files=10 ** 6, f_favail=inodes)


class HelperCase(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        self.staging = os.path.join(self.root, "staging")
        os.mkdir(self.staging)
        # The console's own folders, here folders inside the temporary tree: a state
        # folder and the data key's folder.
        self.own = os.path.join(self.root, "srv", "vps-server")
        os.makedirs(self.own)
        Path(self.own, ".env").write_text("A=1\n")
        self.keydir = os.path.join(self.root, "etc", "vps-server")
        os.makedirs(self.keydir)
        Path(self.keydir, "data.key").write_bytes(b"k" * 32)
        for name, value in (("console_dirs", (self.own, self.keydir)), ("key_dirs", (self.keydir,))):
            patcher = mock.patch.object(sysadmin, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_op(self, **request):
        return sysadmin.handle(request, self.staging)

    def refused(self, code, **request):
        with self.assertRaises(sysadmin.Refused) as caught:
            self.run_op(**request)
        self.assertEqual(str(caught.exception), code)

    def tree(self):
        top = os.path.join(self.root, "top")
        os.makedirs(os.path.join(top, "a", "b"))
        Path(top, "a", "b", "f.txt").write_text("x")
        Path(top, "g.txt").write_text("y")
        return top


class RecursiveChangesTest(HelperCase):
    def test_recursive_chmod_keeps_folders_enterable(self):
        top = self.tree()
        self.run_op(action="chmod", path=top, mode="644", recursive=True)
        for folder in (top, os.path.join(top, "a"), os.path.join(top, "a", "b")):
            self.assertEqual(stat.S_IMODE(os.stat(folder).st_mode), 0o755, folder)
        for name in (os.path.join(top, "g.txt"), os.path.join(top, "a", "b", "f.txt")):
            self.assertEqual(stat.S_IMODE(os.stat(name).st_mode), 0o644, name)
        self.run_op(action="chmod", path=top, mode="0600", recursive=True)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(top, "a")).st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(top, "g.txt")).st_mode), 0o600)
        # Not recursive: the mode is taken as given, also for a folder.
        self.run_op(action="chmod", path=os.path.join(top, "a"), mode="0644")
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(top, "a")).st_mode), 0o644)
        os.chmod(os.path.join(top, "a"), 0o755)

    def test_system_folders_are_never_changed_recursively(self):
        for path in ("/", "/usr", "/etc", "/var"):
            self.refused("recursive_protected", action="chmod", path=path, mode="644", recursive=True)
            with mock.patch.object(sysadmin.os, "lchown") as lchown:
                self.refused("recursive_protected", action="chown", path=path, user=ME, group=MY_GROUP,
                             recursive=True)
            lchown.assert_not_called()

    def test_walk_stays_on_one_file_system_and_skips_protected_folders(self):
        top = self.tree()
        mount = os.path.join(top, "mnt")
        os.makedirs(os.path.join(mount, "inner"))
        Path(mount, "inner", "h.txt").write_text("z")
        real_lstat = os.lstat

        def lstat(path, *args, **kwargs):
            info = real_lstat(path, *args, **kwargs)
            if str(path) == mount or str(path).startswith(mount + "/"):
                fields = list(info[:10])
                fields[2] = info.st_dev + 1  # st_dev: another file system mounted here
                return os.stat_result(fields)
            return info

        with mock.patch.object(sysadmin.os, "lstat", lstat):
            found = list(sysadmin._tree(top, True))
        self.assertIn(os.path.join(top, "a", "b", "f.txt"), found)
        self.assertFalse([item for item in found if item.startswith(mount)])
        # The console's own folder inside a tree is skipped too.
        found = list(sysadmin._tree(self.root, True))
        self.assertFalse([item for item in found if item.startswith(self.own)])
        self.assertIn(os.path.join(top, "g.txt"), found)

    def test_chown_leaves_items_with_that_owner_alone(self):
        top = self.tree()
        tool = os.path.join(top, "tool")
        Path(tool).write_text("#!/bin/sh\n")
        os.chmod(tool, 0o4755)
        with mock.patch.object(sysadmin.os, "lchown") as lchown:
            answer = self.run_op(action="chown", path=top, user=ME, group=MY_GROUP, recursive=True)
        lchown.assert_not_called()
        self.assertEqual(answer["changed"], 0)
        self.assertEqual(stat.S_IMODE(os.stat(tool).st_mode), 0o4755)
        other = types.SimpleNamespace(pw_uid=os.getuid() + 1)
        with mock.patch.object(sysadmin.pwd, "getpwnam", return_value=other), \
                mock.patch.object(sysadmin.os, "lchown") as lchown:
            answer = self.run_op(action="chown", path=top, user="someone", group=MY_GROUP, recursive=True)
        changed = {call.args[0] for call in lchown.call_args_list}
        self.assertEqual(changed, {top, tool, os.path.join(top, "g.txt"), os.path.join(top, "a"),
                                   os.path.join(top, "a", "b"), os.path.join(top, "a", "b", "f.txt")})
        self.assertEqual(answer["changed"], 6)


class ConsoleFoldersTest(HelperCase):
    def test_the_console_folders_stay_and_the_key_folder_is_view_only(self):
        key = os.path.join(self.keydir, "data.key")
        # The folders themselves, and a folder that holds one, are not deleted or moved.
        self.refused("path_protected", action="delete", paths=[self.own])
        self.refused("path_protected", action="delete", paths=[self.keydir])
        self.refused("path_protected", action="delete", paths=[os.path.dirname(self.own)])  # holds it
        self.refused("path_protected", action="move", paths=[self.own], destination=self.root)
        # Nothing in the key folder is written, deleted or moved.
        self.refused("path_protected", action="delete", paths=[key])
        self.refused("path_protected", action="rename", path=key, name="old.key")
        self.refused("path_protected", action="move", paths=[key], destination=self.root)
        self.refused("path_protected", action="mkdir", path=os.path.join(self.keydir, "x"))
        self.refused("path_protected", action="chmod", path=key, mode="0644")
        staged = os.path.join(self.staging, "up-1")
        Path(staged).write_text("new")
        self.refused("path_protected", action="write", staging=staged, path=key, overwrite=True)
        # A link whose folder resolves into it does not get around that.
        os.symlink(self.keydir, os.path.join(self.root, "alias"))
        self.refused("path_protected", action="touch", path=os.path.join(self.root, "alias", "y"))
        self.assertEqual(Path(key).read_bytes(), b"k" * 32)
        # Copying out of it still works.
        backup = os.path.join(self.root, "backup")
        os.mkdir(backup)
        self.run_op(action="copy", paths=[key], destination=backup)
        self.assertEqual(Path(backup, "data.key").read_bytes(), b"k" * 32)
        self.refused("path_protected", action="copy", paths=[key], destination=self.keydir)
        # Files in the state folder can still be edited.
        self.run_op(action="write", staging=staged, path=os.path.join(self.own, ".env"), overwrite=True)
        self.assertEqual(Path(self.own, ".env").read_text(), "new")



class ConsoleFoldersDefaultTest(unittest.TestCase):
    def test_default_list_has_the_key_state_and_program_folders(self):
        state = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, state, True)
        sysadmin.console_dirs.cache_clear()
        self.addCleanup(sysadmin.console_dirs.cache_clear)
        with mock.patch.dict(os.environ, {"VPSSRV_STATE_DIR": state}):
            os.environ.pop("VPSSRV_DATA_DIR", None)
            found = sysadmin.console_dirs()
        self.assertIn("/etc/vps-server", found)
        self.assertIn(state, found)
        self.assertIn(os.path.join(state, "data"), found)
        self.assertIn(str(Path(sysadmin.__file__).resolve().parents[2]), found)
        self.assertNotIn("/", found)


class ExtractTest(HelperCase):
    def setUp(self):
        super().setUp()
        self.dest = os.path.join(self.root, "dest")
        os.mkdir(self.dest)

    def chain_tar(self):
        """The symbolic link chain d1 -> ., d1/d2 -> .., then d1/d2/escaped.txt."""
        path = os.path.join(self.root, "chain.tar")
        with tarfile.open(path, "w") as bundle:
            for name, target in (("d1", "."), ("d1/d2", "..")):
                info = tarfile.TarInfo(name)
                info.type, info.linkname = tarfile.SYMTYPE, target
                bundle.addfile(info)
            info = tarfile.TarInfo("d1/d2/escaped.txt")
            info.size = 8
            bundle.addfile(info, io.BytesIO(b"escaped\n"))
        return path

    def test_link_chain_never_writes_outside(self):
        archive = self.chain_tar()
        if sysadmin._tar_filter():
            self.refused("archive_unsafe", action="extract", path=archive, destination=self.dest)
            self.assertFalse(os.path.exists(os.path.join(self.root, "escaped.txt")))
        with mock.patch.object(sysadmin, "_tar_filter", return_value=False):
            self.refused("archive_links", action="extract", path=archive, destination=self.dest)
        self.assertFalse(os.path.exists(os.path.join(self.root, "escaped.txt")))

    def test_without_the_filter_links_and_devices_are_refused(self):
        hard = os.path.join(self.root, "hard.tar")
        with tarfile.open(hard, "w") as bundle:
            info = tarfile.TarInfo("a.txt")
            info.size = 1
            bundle.addfile(info, io.BytesIO(b"a"))
            info = tarfile.TarInfo("b.txt")
            info.type, info.linkname = tarfile.LNKTYPE, "a.txt"
            bundle.addfile(info)
        fifo = os.path.join(self.root, "fifo.tar")
        with tarfile.open(fifo, "w") as bundle:
            info = tarfile.TarInfo("pipe")
            info.type = tarfile.FIFOTYPE
            bundle.addfile(info)
        with mock.patch.object(sysadmin, "_tar_filter", return_value=False):
            self.refused("archive_links", action="extract", path=hard, destination=self.dest)
            self.refused("archive_unsafe", action="extract", path=fifo, destination=self.dest)
        self.assertEqual(os.listdir(self.dest), [])

    def test_without_the_filter_plain_archives_extract_without_set_id_bits(self):
        archive = os.path.join(self.root, "plain.tar.gz")
        with tarfile.open(archive, "w:gz") as bundle:
            info = tarfile.TarInfo("bin/tool")
            info.size, info.mode = 3, 0o4777
            bundle.addfile(info, io.BytesIO(b"abc"))
        with mock.patch.object(sysadmin, "_tar_filter", return_value=False):
            self.run_op(action="extract", path=archive, destination=self.dest)
        tool = os.path.join(self.dest, "bin", "tool")
        self.assertEqual(Path(tool).read_bytes(), b"abc")
        self.assertEqual(stat.S_IMODE(os.stat(tool).st_mode), 0o755)

    def test_zip_member_paths_are_checked(self):
        for name in ("a/../../b.txt", "a/../b.txt", "/abs.txt"):
            archive = os.path.join(self.root, "bad.zip")
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr(name, "x")
            self.refused("archive_unsafe", action="extract", path=archive, destination=self.dest)
        # A link already in the destination does not lead the archive out of it.
        outside = os.path.join(self.root, "outside")
        os.mkdir(outside)
        os.symlink(outside, os.path.join(self.dest, "sub"))
        archive = os.path.join(self.root, "via-link.zip")
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("sub/new.txt", "x")
        self.refused("archive_unsafe", action="extract", path=archive, destination=self.dest)
        self.assertEqual(os.listdir(outside), [])

    def test_declared_size_must_fit_with_room_to_spare(self):
        archive = os.path.join(self.root, "zeros.zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("zeros.bin", b"\0" * (20 << 20))
        self.assertLess(os.path.getsize(archive), 1 << 20)
        with mock.patch.object(sysadmin.os, "statvfs", return_value=usage(30 << 20)):
            self.refused("no_room", action="extract", path=archive, destination=self.dest)
        small = os.path.join(self.root, "small.tar")
        with tarfile.open(small, "w") as bundle:
            info = tarfile.TarInfo("one.txt")
            info.size = 1
            bundle.addfile(info, io.BytesIO(b"1"))
        with mock.patch.object(sysadmin.os, "statvfs", return_value=usage(1 << 20)):
            self.refused("no_room", action="extract", path=small, destination=self.dest)
        with mock.patch.object(sysadmin.os, "statvfs", return_value=usage(1 << 30, inodes=0)):
            self.refused("no_room", action="extract", path=small, destination=self.dest)
        self.assertEqual(os.listdir(self.dest), [])
        with mock.patch.object(sysadmin.os, "statvfs", return_value=usage(1 << 30)):
            self.run_op(action="extract", path=archive, destination=self.dest)
        self.assertEqual(os.path.getsize(os.path.join(self.dest, "zeros.bin")), 20 << 20)

    def test_extracting_into_the_key_folder_is_refused(self):
        small = os.path.join(self.root, "small.tar")
        with tarfile.open(small, "w") as bundle:
            info = tarfile.TarInfo("one.txt")
            info.size = 1
            bundle.addfile(info, io.BytesIO(b"1"))
        self.refused("path_protected", action="extract", path=small, destination=self.keydir)


class HelperTimeoutTest(unittest.TestCase):
    def test_a_request_that_outlasts_its_time_is_stopped(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        context = types.SimpleNamespace(DATA_DIR=root, WEB_CODE_DIR=Path("/opt/x/src/web"))
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            if command[0] == "systemd-run":
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])
            return subprocess.CompletedProcess(command, 0, "", "")

        with mock.patch.object(api_system.subprocess, "run", run):
            answer = api_system.run_helper(context, {"action": "copy"}, timeout=1800)
        self.assertEqual(answer, {"ok": False, "error": "timeout"})
        unit = next(arg for arg in calls[0] if arg.startswith("--unit="))[len("--unit="):]
        self.assertTrue(unit.startswith("vps-server-admin-"))
        self.assertIn("--property=RuntimeMaxSec=1830", calls[0])
        self.assertEqual(calls[1], ["systemctl", "stop", unit + ".service"])


class FakeUploadHandler(api_filemanager.FileManagerApiMixin):
    def __init__(self, context, directory, length):
        self.context = context
        self.headers = {"Content-Type": "application/octet-stream", "Content-Length": str(length)}
        self.params = {"dir": [directory], "name": ["f.bin"]}
        self.connection = None
        self.errors = []

    def _security_allowed(self):
        return True

    def query_params(self):
        return self.params

    def api_error(self, status, code, **_):
        self.errors.append((status, code))


class StagingTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.context = types.SimpleNamespace(DATA_DIR=self.root)
        self.staging = api_system.staging_dir(self.context)

    def leftovers(self):
        old = self.staging / "up-old"
        old.write_bytes(b"x")
        stamp = time.time() - api_filemanager.STAGING_MAX_AGE - 60
        os.utime(old, (stamp, stamp))
        (self.staging / "up-new").write_bytes(b"y")
        return old

    def test_cleanup_drops_only_old_staging_files(self):
        old = self.leftovers()
        api_filemanager.cleanup_staging(self.context)
        self.assertFalse(old.exists())
        self.assertTrue((self.staging / "up-new").exists())

    def test_upload_checks_both_file_systems_and_cleans_up_first(self):
        old = self.leftovers()
        target = os.path.join(self.root, "target")
        os.mkdir(target)
        with mock.patch.object(api_filemanager.os, "statvfs", return_value=usage(100 << 20)):
            # One file system holds the staging copy and the final one: room for both is needed.
            self.assertTrue(api_filemanager.upload_fits(self.context, target, 40 << 20))
            self.assertFalse(api_filemanager.upload_fits(self.context, target, 60 << 20))
            handler = FakeUploadHandler(self.context, target, 60 << 20)
            handler.api_fm_upload()
        self.assertEqual(handler.errors, [(400, "no_room")])
        self.assertFalse(old.exists())
        # Separate file systems: each must hold one copy; a small state partition is enough to refuse.
        real_stat = os.stat
        devices = {str(self.staging): 1, target: 2}

        def fake_stat(path, *args, **kwargs):
            info = real_stat(path, *args, **kwargs)
            fields = list(info[:10])
            fields[2] = devices.get(str(path), info.st_dev)
            return os.stat_result(fields)

        def fake_statvfs(path):
            return usage((50 << 20) if str(path) == str(self.staging) else (1 << 30))

        with mock.patch.object(api_filemanager.os, "stat", fake_stat), \
                mock.patch.object(api_filemanager.os, "statvfs", fake_statvfs):
            self.assertTrue(api_filemanager.upload_fits(self.context, target, 40 << 20))
            self.assertFalse(api_filemanager.upload_fits(self.context, target, 60 << 20))


if __name__ == "__main__":
    unittest.main()
