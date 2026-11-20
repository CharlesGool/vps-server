"""Keep the unit tests away from an installed console on the machine that runs them.

On a host where vps-server is installed, ``/etc/vps-server/data.key`` and
``/etc/vps-server/state-dir`` exist and only root can read them. A test that
falls back to them fails with a permission error, or as root would read (or
write) the real installation. Importing this module, once per process:

- sets ``VPSSRV_DATA_KEY_FILE`` to a path that does not exist, unless the caller
  already set it, so state files stay plain;
- points ``secure_store.DEFAULT_KEY_FILE`` at that same path, because several
  tests pop the variable in their clean-up and later tests would otherwise fall
  back to the host's key;
- points ``state_paths.STATE_LOCATOR`` at a missing file and
  ``state_paths.DEFAULT_STATE_DIR`` at an empty temporary directory, so a test
  without ``VPSSRV_STATE_DIR`` never resolves to the host's state directory.

``tests/__init__.py`` imports it for ``python3 -m unittest tests.<module>``;
``test_00_isolation.py`` imports it first under ``unittest discover -s tests``
(that mode imports test modules only, never the package).
"""

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))

import secure_store  # noqa: E402
import state_paths  # noqa: E402

KEY_ENV = "VPSSRV_DATA_KEY_FILE"

ROOT = Path(tempfile.mkdtemp(prefix="vps-server-tests-"))
atexit.register(shutil.rmtree, str(ROOT), True)

if not os.environ.get(KEY_ENV):
    os.environ[KEY_ENV] = str(ROOT / "no-data.key")
KEY_FILE = Path(os.environ[KEY_ENV])
secure_store.DEFAULT_KEY_FILE = KEY_FILE

STATE_DIR = ROOT / "state"
STATE_DIR.mkdir()
state_paths.STATE_LOCATOR = ROOT / "no-state-dir"
state_paths.DEFAULT_STATE_DIR = STATE_DIR
