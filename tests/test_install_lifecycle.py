"""Installer and uninstaller helpers: reading the admin password, the full-uninstall inventory (temp dirs only)."""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "web"))
import secure_store as ss  # noqa: E402
import uninstall_cleanup  # noqa: E402

ENV_NAMES = ("VPSSRV_DATA_KEY_FILE", "VPSSRV_STATE_DIR", "VPSSRV_DATA_DIR", "VPSSRV_PASSWORD_FILE",
             "VPSSRV_CERT_DIR", "VPSSRV_CONSOLE_PORT_FILE")


class EnvCase(unittest.TestCase):
    def setUp(self):
        self.saved = {name: os.environ.get(name) for name in ENV_NAMES}
        for name in ENV_NAMES:
            os.environ.pop(name, None)
        self.tmp = Path(tempfile.mkdtemp())
        self.state = self.tmp / "state"
        self.state.mkdir()
        self.keyfile = self.tmp / "etc" / "data.key"
        os.environ["VPSSRV_DATA_KEY_FILE"] = str(self.keyfile)
        os.environ["VPSSRV_STATE_DIR"] = str(self.state)
        ss._cache.clear()

    def tearDown(self):
        for name, value in self.saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        ss._cache.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_main(self, module, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = module.main(argv)
        return code, out.getvalue(), err.getvalue()


class ShowPasswordTest(EnvCase):
    def test_encrypted_password_is_printed_in_plain(self):
        ss.init_key()
        password = self.state / "admin_password.txt"
        ss.write_text(password, "s3cret-Pass_word\n")              # as ensure_admin_password writes it
        self.assertTrue(password.read_bytes().startswith(ss.MAGIC))
        code, out, err = self.run_main(ss, ["show-password"])
        self.assertEqual((code, out, err), (0, "s3cret-Pass_word\n", ""))

    def test_plain_password_from_an_older_version(self):
        (self.state / "admin_password.txt").write_text("legacy-plain\n")
        code, out, _ = self.run_main(ss, ["show-password"])
        self.assertEqual((code, out), (0, "legacy-plain\n"))

    def test_follows_the_recorded_password_path(self):
        custom = self.tmp / "elsewhere" / "pw.txt"
        custom.parent.mkdir()
        custom.write_text("custom-path\n")
        (self.state / "paths.json").write_text(
            '{"VPSSRV_PASSWORD_FILE": "%s"}' % custom)
        self.assertEqual(ss.admin_password(), "custom-path")
        os.environ["VPSSRV_PASSWORD_FILE"] = str(self.state / "admin_password.txt")
        (self.state / "admin_password.txt").write_text("from-env\n")
        self.assertEqual(ss.admin_password(), "from-env")           # the installer exports it

    def test_missing_empty_and_undecryptable_fail_without_traceback(self):
        code, out, err = self.run_main(ss, ["show-password"])
        self.assertEqual((code, out), (1, ""))
        self.assertIn("no admin password", err)
        (self.state / "admin_password.txt").write_text("\n")
        code, _, err = self.run_main(ss, ["show-password"])
        self.assertEqual(code, 1)
        self.assertIn("empty", err)
        ss.init_key()
        ss.write_text(self.state / "admin_password.txt", "x")
        self.keyfile.write_text(os.urandom(32).hex() + "\n")
        ss._cache.clear()
        code, out, err = self.run_main(ss, ["show-password"])
        self.assertEqual((code, out), (1, ""))
        self.assertIn("cannot decrypt", err)

    def test_reads_only_the_password(self):
        ss.init_key()
        data = self.state / "data"
        data.mkdir()
        ss.write_text(self.state / "admin_password.txt", "pw\n")
        ss.write_text(data / "sessions.json", "{}")
        before = {path.name: path.read_bytes() for path in (self.state / "admin_password.txt", data / "sessions.json")}
        self.run_main(ss, ["show-password"])
        after = {path.name: path.read_bytes() for path in (self.state / "admin_password.txt", data / "sessions.json")}
        self.assertEqual(before, after)

    def test_command_line(self):
        ss.init_key()
        ss.write_text(self.state / "admin_password.txt", "cli-password\n")
        result = subprocess.run([sys.executable, str(ROOT / "src/web/secure_store.py"), "show-password"],
                                capture_output=True, text=True, env=dict(os.environ), timeout=30)
        self.assertEqual((result.returncode, result.stdout), (0, "cli-password\n"))


class UninstallInventoryTest(EnvCase):
    def test_counts_backups_and_drive_files_inside_the_state_directory(self):
        backups = self.state / "backups"
        backups.mkdir()
        for name in ("config-20261101T000000Z-manual.tar.gz", "config-20261102T000000Z-pre-upgrade.tar.gz.sealed",
                     ".config-partial", "notes.txt"):
            (backups / name).write_bytes(b"x")
        blobs = self.state / "data" / "files" / "blobs"
        blobs.mkdir(parents=True)
        (blobs / "a").write_bytes(b"x" * 1024)
        (blobs / "b").write_bytes(b"x" * 2048)
        self.assertEqual(uninstall_cleanup.data_inventory(self.state), (2, 2, 3072, []))
        code, out, _ = self.run_main(uninstall_cleanup, ["inventory", str(self.state)])
        self.assertEqual((code, out), (0, "backups 2\ndrive 2 3.0KiB\n"))

    def test_paths_outside_the_state_directory_are_reported(self):
        outside = self.tmp / "srv" / "data"
        (outside / "files" / "blobs").mkdir(parents=True)
        (outside / "files" / "blobs" / "kept").write_bytes(b"x")
        (self.state / "paths.json").write_text('{"VPSSRV_DATA_DIR": "%s"}' % outside)
        backups, files, size, kept = uninstall_cleanup.data_inventory(self.state)
        self.assertEqual((backups, files, size, kept), (0, 0, 0, [str(outside)]))   # not deleted, so not listed
        code, out, _ = self.run_main(uninstall_cleanup, ["inventory", str(self.state)])
        self.assertEqual((code, out.splitlines()[-1]), (0, f"outside {outside}"))

    def test_missing_state_directory_and_bad_input(self):
        missing = self.tmp / "gone"
        os.environ["VPSSRV_STATE_DIR"] = str(missing)
        self.assertEqual(uninstall_cleanup.data_inventory(missing), (0, 0, 0, []))
        self.assertEqual(self.run_main(uninstall_cleanup, ["inventory"])[0], 2)
        os.environ["VPSSRV_STATE_DIR"] = str(self.state)
        (self.state / "paths.json").write_text("{not json")
        code, out, err = self.run_main(uninstall_cleanup, ["inventory", str(self.state)])
        self.assertEqual((code, out), (1, ""))
        self.assertIn("uninstall cleanup failed", err)

    def test_sizes(self):
        self.assertEqual(uninstall_cleanup._size(0), "0B")
        self.assertEqual(uninstall_cleanup._size(1536), "1.5KiB")
        self.assertEqual(uninstall_cleanup._size(5 * 1024 ** 3), "5.0GiB")


class InstallerSourceTest(unittest.TestCase):
    """Static checks on the shell scripts that the unit tests cannot run."""

    def test_tailscale_version_lives_only_in_the_dependency_lock(self):
        for name in ("deploy/install.sh", "deploy/tailscale/setup-tailscale.sh", "src/web/features/api_dashboard.py"):
            self.assertNotRegex((ROOT / name).read_text(encoding="utf-8"), r"tailscale_\d+\.\d+\.\d+_amd64", name)

    def test_unused_web_unit_template_is_gone(self):
        self.assertFalse((ROOT / "deploy/systemd/vps-server-web.service").exists())
        self.assertTrue((ROOT / "deploy/systemd/frpc@.service").is_file())


if __name__ == "__main__":
    unittest.main()
