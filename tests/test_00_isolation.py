"""The test run never reaches an installed console's data key or state directory.

The file name sorts first, so ``unittest discover -s tests`` imports it (and so
``_isolation``) before any other test module.
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
import _isolation  # noqa: E402

import secure_store  # noqa: E402
import state_paths  # noqa: E402

HOST_KEY = Path("/etc/vps-server/data.key")
PROBE = ("import json, os, sys; sys.path.insert(0, sys.argv[1]); import _isolation, secure_store; "
         "print(json.dumps([os.environ['VPSSRV_DATA_KEY_FILE'], str(secure_store.DEFAULT_KEY_FILE)]))")


def probe(**env):
    clean = {k: v for k, v in os.environ.items() if k != _isolation.KEY_ENV}
    out = subprocess.run([sys.executable, "-c", PROBE, str(TESTS)], env={**clean, **env},
                         capture_output=True, text=True, check=True, timeout=60).stdout
    return json.loads(out)


class IsolationTest(unittest.TestCase):
    def test_the_data_key_never_falls_back_to_the_host(self):
        self.assertNotEqual(secure_store.key_path(), HOST_KEY)
        # Tests that pop the variable in their clean-up must not expose the host key to the next test.
        with mock.patch.dict(os.environ):
            os.environ.pop(_isolation.KEY_ENV, None)
            self.assertEqual(secure_store.key_path(), _isolation.KEY_FILE)
            if not _isolation.KEY_FILE.exists():
                self.assertIsNone(secure_store.load_key())
                self.assertFalse(secure_store.enabled())

    def test_the_state_directory_never_falls_back_to_the_host(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("VPSSRV_STATE_DIR", None)
            self.assertEqual(state_paths.state_dir(), _isolation.STATE_DIR)
        self.assertFalse(state_paths.STATE_LOCATOR.exists())

    def test_a_missing_key_file_gets_a_temporary_path_and_an_explicit_one_is_kept(self):
        variable, default = probe()
        self.assertEqual(variable, default)
        self.assertNotEqual(Path(variable), HOST_KEY)
        self.assertFalse(Path(variable).exists())
        # check-server.mjs sets its own path; the helper only fills in a missing one.
        self.assertEqual(probe(VPSSRV_DATA_KEY_FILE="/nonexistent/explicit.key"),
                         ["/nonexistent/explicit.key", "/nonexistent/explicit.key"])


if __name__ == "__main__":
    unittest.main()
