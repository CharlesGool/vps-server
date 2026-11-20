"""Upgrading from the console's System page, and the token API's upgrade through the same helper.

No network, no systemd, no installer: subprocess, GitHub and the unit files are faked.
"""
import argparse
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import upgrade as up  # noqa: E402
from test_spa_api import load_app  # noqa: E402
from test_upgrade_command import ConsoleCall, Done  # noqa: E402


class UpgradeHelpersTest(unittest.TestCase):
    def setUp(self):
        from features import api_upgrade
        self.api = api_upgrade
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.context = argparse.Namespace(DATA_DIR=self.tmp, WEB_CODE_DIR=Path("/opt/x/src/web"), VERSION_LABEL="v7.4.0")
        self.calls = []

    def fake(self, states, start_code=0):
        def run(command, **_kwargs):
            self.calls.append(command)
            if command[0] == "systemctl":
                return Done(states.get(command[-1], "inactive") + "\n")
            return Done(returncode=start_code)
        return mock.patch.object(self.api.subprocess, "run", side_effect=run)

    def test_start_runs_the_upgrade_command_in_its_own_unit(self):
        (self.tmp / "upgrade-api.log").write_text("old\nexit 3\n")
        with self.fake({}):
            self.assertIsNone(self.api.start(self.context, "v7.5.0"))
        command = self.calls[-1]
        self.assertEqual(command[:4], ["systemd-run", "--quiet", "--collect", "--unit=vps-server-upgrade"])
        self.assertIn("/opt/x/src/web/upgrade.py --version v7.5.0 >", command[-1])
        self.assertNotIn("--variant", command[-1])                 # the host's own package
        self.assertIn('echo "exit $?" >>', command[-1])
        self.assertEqual((self.tmp / "upgrade-api.log").read_text(), "")
        with self.fake({}):
            self.api.start(self.context, None, "online")
        self.assertIn("upgrade.py --variant online >", self.calls[-1][-1])

    def test_start_refuses_while_an_upgrade_or_install_runs(self):
        for unit in ("vps-server-upgrade", up.INSTALL_UNIT):
            with self.fake({unit: "active"}):
                self.assertEqual(self.api.start(self.context), "busy")
        self.assertFalse(any(command[0] == "systemd-run" for command in self.calls))
        with self.fake({}, start_code=1):
            self.assertEqual(self.api.start(self.context), "failed")

    def test_status_reads_the_log(self):
        (self.tmp / "upgrade-api.log").write_text("Signature OK.\nthe password is x\nexit 0\n")
        with self.fake({}):
            info = self.api.status(self.context)
        self.assertEqual(info, {"running": False, "version": "v7.4.0", "log": "Signature OK.\nexit 0", "lastExit": 0})
        with self.fake({"vps-server-upgrade": "active"}):
            self.assertIsNone(self.api.status(self.context)["lastExit"])

    def test_latest_is_cached_and_compared(self):
        found = []

        def finder(repo, timeout):
            found.append(timeout)
            return "v7.5.0"
        self.api._latest.update(at=0.0, tag=None)
        self.assertEqual(self.api.latest(finder=finder), "v7.5.0")
        self.assertEqual(self.api.latest(finder=finder), "v7.5.0")
        self.assertEqual(found, [self.api.LATEST_TIMEOUT])
        self.api.latest(refresh=True, finder=finder)
        self.assertEqual(len(found), 2)
        self.api._latest.update(at=0.0, tag=None)
        self.assertTrue(self.api.newer("v7.5.0", "7.4.0"))
        self.assertFalse(self.api.newer("v7.4.0", "7.4.0"))
        self.assertIsNone(self.api.newer("v7.4.0", "test-abc1234"))


class ConsoleUpgradeApiTest(ConsoleCall, unittest.TestCase):
    """The System page's upgrade card and the token API through the real handler."""

    @classmethod
    def setUpClass(cls):
        cls.app = load_app()
        from features import api_upgrade, api_v1
        cls.api_upgrade, cls.api_v1 = api_upgrade, api_v1

    def test_the_card_needs_a_verified_session(self):
        self.assertEqual(self.call("GET", "/api/system/upgrade")[0], 401)
        cookie = self.app.create_session(security_verified=False, ip="127.0.0.1", agent="test", method="certificate")
        self.assertEqual(self.call("GET", "/api/system/upgrade", cookie=cookie), (403, {"error": "security_required"}))

    def test_status_latest_and_start(self):
        cookie = self.login()
        with mock.patch.object(self.api_upgrade, "unit_active", return_value=False):
            status, info = self.call("GET", "/api/system/upgrade", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(set(info), {"running", "version", "log", "lastExit", "variant", "pinned"})
        self.api_upgrade._latest.update(at=0.0, tag=None)
        with mock.patch.object(up, "latest_tag", return_value="v7.5.0"):
            self.assertEqual(self.call("GET", "/api/system/upgrade/latest", cookie=cookie),
                             (200, {"latest": "v7.5.0", "newer": None}))      # the test build is "unit"
        self.api_upgrade._latest.update(at=0.0, tag=None)
        with mock.patch.object(up, "latest_tag", side_effect=up.LatestError("rate_limited", "GitHub API: HTTP 403")):
            self.assertEqual(self.call("GET", "/api/system/upgrade/latest", cookie=cookie),
                             (502, {"error": "latest_rate_limited", "detail": "GitHub API: HTTP 403"}))
        self.assertEqual(self.call("POST", "/api/system/upgrade", {"version": "latest; rm"}, cookie=cookie)[0], 400)
        with mock.patch.object(self.api_upgrade, "start", return_value="busy") as start:
            self.assertEqual(self.call("POST", "/api/system/upgrade", {"version": "v7.5.0"}, cookie=cookie),
                             (409, {"error": "busy"}))
        start.assert_called_once_with(self.app, "v7.5.0")
        with mock.patch.object(self.api_upgrade, "start", return_value=None), \
                mock.patch.object(self.api_upgrade, "unit_active", return_value=True):
            status, info = self.call("POST", "/api/system/upgrade", {}, cookie=cookie)
        self.assertEqual((status, info["running"]), (200, True))

    def test_token_upgrade_keeps_the_hosts_own_variant(self):
        token = self.token()
        with mock.patch.object(self.api_upgrade, "start", return_value=None) as start:
            self.assertEqual(self.call("POST", "/api/v1/upgrade", {}, token=token), (200, {"started": True}))
            self.call("POST", "/api/v1/upgrade", {"version": "v7.5.0", "variant": "offline"}, token=token)
        self.assertEqual(start.call_args_list[0].args[1:], (None, None))
        self.assertEqual(start.call_args_list[1].args[1:], ("v7.5.0", "offline"))
        self.assertEqual(self.call("POST", "/api/v1/upgrade", {"variant": "other"}, token=token)[0], 400)


if __name__ == "__main__":
    unittest.main()
