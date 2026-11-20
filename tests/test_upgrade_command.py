"""The upgrade command's install handling and the token API's limits.

No network, no systemd, no installer: subprocess, GitHub and the unit files are faked.
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
os.environ.setdefault("VPSSRV_DATA_KEY_FILE", "/nonexistent/vps-server-test-key")
import release_trust as rt  # noqa: E402
import upgrade as up  # noqa: E402
from test_spa_api import load_app  # noqa: E402
from test_upgrade import Signer, make_package  # noqa: E402


class Done:
    """A finished subprocess.run result."""

    def __init__(self, stdout="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, "", returncode


def systemctl(states):
    """A runner that answers ``systemctl show/is-active <unit>`` from ``states``."""
    def run(command, **_kwargs):
        return Done(states.get(command[-1], "inactive") + "\n")
    return run


class Response:
    def __init__(self, data):
        self.data = data

    def read(self, limit=-1):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(url, code):
    return urllib.error.HTTPError(url, code, "error", Message(), io.BytesIO(b""))


class UpgradeCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.signer = Signer(str(self.tmp))
        self.state = self.tmp / "state"
        self.prefix = self.tmp / "srv" / "console"
        (self.prefix / "config").mkdir(parents=True)
        (self.prefix / "config" / "VERSION").write_text("6.5.0\n")
        (self.prefix / "app.py").write_text("")
        self.units = self.tmp / "units"
        self.units.mkdir()
        self.release = self.tmp / "release"
        self.release.mkdir()
        self.log = []
        rt.write_pinned(self.state, self.signer.public)

    def publish(self, variant="offline", sign=None, **package):
        name = up.package_name("v6.6.0", variant)
        make_package(self.release / name, "v6.6.0", self.signer.public, **package)
        sums = f"{rt.file_sha256(self.release / name)}  {name}\n".encode()
        (self.release / "SHA256SUMS").write_bytes(sums)
        (self.release / "SHA256SUMS.sig").write_bytes(self.signer.sign(sign or sums))
        return name

    def args(self, **over):
        values = dict(version=None, variant=None, repo=up.DEFAULT_REPO, source=str(self.release),
                      trust_fingerprint="", accept_key_change="", allow_downgrade=False, dry_run=False)
        values.update(over)
        return argparse.Namespace(**values)

    def go(self, installer=None, runner=None, **over):
        record = self.tmp / "env"
        installer = installer or ["sh", "-c", 'echo "$PREFIX|${SERVICE_NAME:-}" > "$0"', str(record)]
        code = up.run(self.args(**over), state_dir=self.state, prefix=self.prefix, installer=installer,
                      out=self.log.append, unit_dir=self.units, runner=runner or systemctl({}))
        return code, record.read_text().strip() if record.exists() else None

    def leftovers(self):
        return sorted(p for p in self.prefix.parent.iterdir() if p.name.startswith(up.WORK_PREFIX))

    # -- PREFIX and SERVICE_NAME -----------------------------------------------------------

    def test_the_installer_gets_this_installs_prefix_and_service(self):
        self.publish()
        (self.units / "ssh.service").write_text("[Service]\nExecStart=/usr/sbin/sshd -D\n")
        (self.units / "my-console.service").write_text(f"[Service]\nExecStart=/usr/bin/env python3 {self.prefix}/app.py\n")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PREFIX", None)
            os.environ.pop("SERVICE_NAME", None)
            self.assertEqual(self.go(), (0, f"{self.prefix}|my-console"))
            os.environ["PREFIX"] = "/somewhere/else"                 # an explicit PREFIX still wins
            self.assertEqual(self.go()[1], "/somewhere/else|my-console")

    def test_without_a_unit_the_prefix_is_where_the_command_lives(self):
        self.publish()
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PREFIX", None)
            os.environ.pop("SERVICE_NAME", None)
            self.assertEqual(self.go(), (0, f"{self.prefix}|"))

    def test_console_unit_prefers_the_default_name(self):
        line = f"[Service]\nExecStart=/usr/bin/env python3 {self.prefix}/app.py\n"
        (self.units / "a-copy.service").write_text(line)
        (self.units / "vps-server-web.service").write_text(line)
        self.assertEqual(up.console_unit(self.prefix, self.units), (str(self.prefix), "vps-server-web"))
        self.assertIsNone(up.console_unit(self.tmp / "other", self.units))

    # -- package variant ---------------------------------------------------------------------

    def test_the_variant_defaults_to_the_installed_one(self):
        self.assertIsNone(up.installed_variant(self.prefix))
        (self.prefix / "installer-source" / "config").mkdir(parents=True)
        (self.prefix / "installer-source" / "config" / "PACKAGE_VARIANT").write_text("online\n")
        self.assertEqual(up.installed_variant(self.prefix), "online")
        self.publish("online")
        self.assertEqual(self.go()[0], 0)
        self.assertIn("Installing v6.6.0 (online) ...", self.log)
        self.publish("offline")                    # the online package is no longer listed
        with self.assertRaises(up.UpgradeError):
            self.go()
        self.assertEqual(self.go(variant="offline")[0], 0)

    # -- the installer's background job ----------------------------------------------------

    def test_ctrl_c_leaves_the_package_to_a_running_installer(self):
        self.publish()
        running = systemctl({up.INSTALL_UNIT: "active"})
        with mock.patch.object(up.subprocess, "run", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.go(runner=running)
        kept = self.leftovers()
        self.assertEqual(len(kept), 1)
        self.assertTrue((kept[0] / up.DETACHED).is_file())
        self.assertTrue((kept[0] / "unpacked" / "vps-server" / "deploy" / "install.sh").is_file())
        self.assertTrue(any("still running in the background" in line for line in self.log))
        # The next run leaves it alone while the job runs, and removes it once the job is over.
        self.assertEqual(self.go(runner=running)[0], 0)
        self.assertIn(kept[0], self.leftovers())
        self.assertEqual(self.go()[0], 0)
        self.assertEqual(self.leftovers(), [])

    def test_a_finished_job_frees_the_package_even_while_its_unit_winds_down(self):
        self.publish()
        result = self.prefix / up.INSTALL_RESULT
        result.parent.mkdir(parents=True)
        result.write_text("0\n")
        self.assertEqual(self.go(runner=systemctl({up.INSTALL_UNIT: "deactivating"}))[0], 0)
        self.assertEqual(self.leftovers(), [])
        result.write_text("")
        self.assertTrue(up.install_job_running(self.prefix, systemctl({up.INSTALL_UNIT: "active"})))
        self.assertFalse(up.install_job_running(self.prefix, systemctl({})))

        def missing(*_args, **_kwargs):
            raise FileNotFoundError("systemctl")
        self.assertFalse(up.install_job_running(self.prefix, missing))

    def test_main_turns_a_stop_signal_into_a_clean_exit(self):
        with mock.patch.object(up, "run", side_effect=KeyboardInterrupt), \
                mock.patch.object(up.signal, "signal") as handlers, mock.patch.object(sys, "stderr", io.StringIO()), \
                mock.patch.object(up.signal, "getsignal", return_value=up.signal.SIG_DFL):
            self.assertEqual(up.main([]), 130)
        self.assertEqual({call.args[0] for call in handlers.call_args_list}, {up.signal.SIGTERM, up.signal.SIGHUP})

    # -- trust before unpacking ----------------------------------------------------------------

    def test_first_pin_checks_key_and_signature_before_unpacking(self):
        (self.state / rt.PINNED_NAME).unlink()
        self.publish(sign=b"something else")
        with mock.patch.object(up, "safe_extract", wraps=up.safe_extract) as extract:
            with self.assertRaises(rt.TrustError):
                self.go(trust_fingerprint=rt.fingerprint(self.signer.public))
            with self.assertRaises(up.UpgradeError):
                self.go(trust_fingerprint=rt.fingerprint(bytes(range(32))))
            self.assertEqual(extract.call_count, 0)
            self.publish()
            self.assertEqual(self.go(trust_fingerprint=rt.fingerprint(self.signer.public))[0], 0)
            self.assertEqual(extract.call_count, 1)
        self.assertEqual(rt.read_pinned(self.state), self.signer.public)

    def test_package_key_reads_the_archive_only(self):
        archive = self.tmp / "p.tar.gz"
        make_package(archive, "v6.6.0", self.signer.public)
        self.assertEqual(up.package_key(archive), self.signer.public)
        make_package(archive, "v6.6.0", None)
        self.assertIsNone(up.package_key(archive))
        link = tarfile.TarInfo("vps-server/config/release-key.pub")
        link.type, link.linkname = tarfile.SYMTYPE, "/etc/passwd"
        make_package(archive, "v6.6.0", None, extra=[(link, None)])
        with self.assertRaises(up.UpgradeError):
            up.package_key(archive)

    def link_package(self, *links):
        archive = self.tmp / "links.tar.gz"
        extra = []
        for name, kind, target in links:
            info = tarfile.TarInfo(name)
            if kind == "file":
                info.size = len(target)
                extra.append((info, target))
            else:
                info.type, info.linkname = (tarfile.SYMTYPE if kind == "sym" else tarfile.LNKTYPE), target
                extra.append((info, None))
        make_package(archive, "v6.6.0", self.signer.public, extra=extra)
        return archive

    def test_without_tarfile_filters_every_link_is_refused(self):
        for links in ([("vps-server/latest", "sym", "config/VERSION")],
                      [("vps-server/hard", "hard", "vps-server/config/VERSION")]):
            archive = self.link_package(*links)
            target = self.tmp / "out"
            with mock.patch.object(up.tarfile, "tar_filter", None, create=True):
                with self.assertRaises(up.UpgradeError):
                    up.safe_extract(archive, target)
            self.assertFalse(target.exists() and any(target.iterdir()))

    @unittest.skipUnless(getattr(tarfile, "tar_filter", None), "needs tarfile filters")
    def test_a_chain_of_links_cannot_escape(self):
        archive = self.link_package(("vps-server/a", "sym", "."), ("vps-server/a/b", "sym", ".."),
                                    ("vps-server/a/b/c", "sym", ".."), ("vps-server/a/b/c/escaped", "file", b"x"))
        target = self.tmp / "deep" / "out"
        target.mkdir(parents=True)
        with self.assertRaises((up.UpgradeError, tarfile.TarError)):
            up.safe_extract(archive, target)
        self.assertFalse((self.tmp / "deep" / "escaped").exists())
        self.assertFalse((self.tmp / "escaped").exists())

    # -- the latest release ------------------------------------------------------------------------

    def test_latest_tag_from_the_api(self):
        def opener(request, timeout=0):
            self.assertEqual(timeout, 5)
            return Response(json.dumps({"tag_name": "v7.5.0"}).encode())
        self.assertEqual(up.latest_tag("a/b", opener, timeout=5), "v7.5.0")

    def test_latest_tag_falls_back_to_the_release_checksums(self):
        seen = []

        def opener(request, timeout=0):
            seen.append(request.full_url)
            if "api.github.com" in request.full_url:
                raise http_error(request.full_url, 403)
            return Response(b"%s  vps-server-v7.5.0-linux-amd64.tar.gz\n%s  vps-server-v7.5.0-linux-amd64-online.tar.gz\n"
                            % (b"a" * 64, b"b" * 64))
        with mock.patch.dict(os.environ, {"VPSSRV_GITHUB_MIRROR": "none"}):
            self.assertEqual(up.latest_tag("a/b", opener), "v7.5.0")
        self.assertEqual(seen[1], "https://github.com/a/b/releases/latest/download/SHA256SUMS")

    def test_latest_tag_says_why_it_failed(self):
        def unreachable(request, timeout=0):
            raise urllib.error.URLError("timed out")

        def missing(request, timeout=0):
            raise http_error(request.full_url, 404)

        def limited(request, timeout=0):
            if "api.github.com" in request.full_url:
                raise http_error(request.full_url, 403)
            raise urllib.error.URLError("timed out")

        def odd(request, timeout=0):
            if "api.github.com" in request.full_url:
                return Response(b'{"tag_name": "nightly"}')
            return Response(b"")
        with mock.patch.dict(os.environ, {"VPSSRV_GITHUB_MIRROR": "none"}):
            for opener, code in ((unreachable, "unreachable"), (missing, "not_found"), (limited, "rate_limited"),
                                 (odd, "invalid")):
                with self.assertRaises(up.LatestError, msg=code) as caught:
                    up.latest_tag("a/b", opener)
                self.assertEqual(caught.exception.code, code)
                self.assertIn("--version", str(caught.exception))


class ConsoleCall:
    """Requests through the real console handler."""

    def setUp(self):
        self.app.LOGIN_LIMITER.clear()
        self.addCleanup(self.app.LOGIN_LIMITER.clear)

    def call(self, method, path, body=None, cookie=None, token=None, peer="127.0.0.1"):
        handler = object.__new__(self.app.ConsoleHandler)
        payload = b"" if body is None else json.dumps(body).encode()
        headers = Message()
        headers["Host"] = "127.0.0.1:28998"
        if body is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(payload))
        if cookie:
            headers["Cookie"] = f"session={cookie}"
        if token:
            headers["Authorization"] = "Bearer " + token
        handler.headers, handler.path, handler.command = headers, path, method
        handler.request_version, handler.requestline = "HTTP/1.1", f"{method} {path} HTTP/1.1"
        handler.client_address, handler.connection = (peer, 50000), None
        handler.rfile, handler.wfile = io.BytesIO(payload), io.BytesIO()
        handler.close_connection = False
        handler._dispatch(method)
        head, _, data = handler.wfile.getvalue().partition(b"\r\n\r\n")
        status = int(head.split(b" ", 2)[1])
        return status, (json.loads(data) if data.startswith(b"{") else None)

    def login(self):
        """A password session that has just been verified, as after the admin password prompt."""
        return self.app.create_session(security_verified=True, ip="127.0.0.1", agent="test", method="password")

    def token(self, scope="write"):
        return self.app.API_TOKENS.create("unit-" + scope + str(time.monotonic_ns())[-6:], scope)[0]


class TokenApiTest(ConsoleCall, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = load_app()
        from features import api_v1
        cls.api_v1 = api_v1

    def test_token_restart_is_limited_to_this_projects_running_services(self):
        token = self.token()
        units = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, units, True)
        for name in ("vps-server-proxy.service", "frpc@.service", "vps-server-web.service"):
            (units / name).write_text("[Service]\n")
        commands = []

        def run(command, **_kwargs):
            commands.append(command)
            return Done()
        with mock.patch.object(self.api_v1, "UNIT_DIR", units), \
                mock.patch.object(self.api_v1.subprocess, "run", side_effect=run):
            for unit in ("systemd-poweroff.service", "ssh.service", "vps-server-install.service",
                         "vps-server-upgrade.service", "tailscaled.service"):
                self.assertEqual(self.call("POST", "/api/v1/services/restart", {"unit": unit}, token=token),
                                 (403, {"error": "unit_not_allowed"}), unit)
            for unit in ("vps-server-proxy.service", "frpc@home.service"):
                self.assertEqual(self.call("POST", "/api/v1/services/restart", {"unit": unit}, token=token)[0], 204)
            self.call("POST", "/api/v1/services/restart", {"unit": "vps-server-web.service"}, token=token)
        self.assertEqual(commands, [["systemctl", "try-restart", "vps-server-proxy.service"],
                                    ["systemctl", "try-restart", "frpc@home.service"],
                                    ["systemctl", "--no-block", "try-restart", "vps-server-web.service"]])

    def test_tokens_skip_the_global_pause_but_not_their_own_ban(self):
        token = self.token("read")
        limiter = self.app.LOGIN_LIMITER
        limiter._global_until = time.time() + 300
        self.assertFalse(limiter.check("198.51.100.7")[0])
        self.assertTrue(limiter.check("198.51.100.7", global_pause=False)[0])
        with mock.patch.object(self.api_v1, "services", return_value=[]):
            self.assertEqual(self.call("GET", "/api/v1/services", token=token)[0], 200)
            limiter._locked_until[limiter.key("127.0.0.1")] = time.time() + 300
            self.assertEqual(self.call("GET", "/api/v1/services", token=token)[0], 429)
        limiter.clear()
        self.assertEqual(self.call("GET", "/api/v1/services", token="vpss_wrong")[0], 401)
        self.assertEqual(limiter.snapshot()[0]["total"], 1)                      # a wrong token still counts


if __name__ == "__main__":
    unittest.main()
