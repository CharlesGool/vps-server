"""Contract for the component module and deployed flat module."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AppEntryTest(unittest.TestCase):
    def test_checkout_import_is_the_implementation_and_mutations_are_live(self):
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env.update(VPSSRV_DATA_DIR=directory, VPSSRV_PASSWORD_FILE=str(Path(directory) / "password"),
                       VPSSRV_CONSOLE_PORT_FILE=str(Path(directory) / "port"))
            check = '''from src.web import app
import pathlib
assert app.BASE_DIR == pathlib.Path.cwd()
assert app.VERSION == pathlib.Path("config/VERSION").read_text().strip()
old = app._read_proc_net
app._read_proc_net = lambda path: []
assert app.observed_connections() == {}
app._read_proc_net = old
'''
            result = subprocess.run([sys.executable, "-c", check], cwd=ROOT, env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_deployed_flat_copy_uses_its_own_root(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            shutil.copy2(ROOT / "src/web/app.py", prefix / "app.py")
            for module in ("node_accounting", "node_inventory", "node_state"):
                shutil.copy2(ROOT / "src/web" / f"{module}.py", prefix / f"{module}.py")
            (prefix / "VERSION").write_text("deployed-version\n")
            (prefix / ".env").write_text("VPSSRV_DEFAULT_LANG=zh_tw\n")
            shutil.copytree(ROOT / "lang", prefix / "lang")
            (prefix / "static").mkdir()
            (prefix / "doc").mkdir()
            env = os.environ.copy()
            for key in ("VPSSRV_DEFAULT_LANG", "VPSSRV_DATA_DIR", "VPSSRV_PASSWORD_FILE",
                        "VPSSRV_CONSOLE_PORT_FILE"):
                env.pop(key, None)
            check = '''import app, pathlib
root = pathlib.Path.cwd()
assert app.BASE_DIR == root
assert app.VERSION == "deployed-version"
assert app.DEFAULT_LANG == "zh_tw"
assert app.DATA_DIR == root / "data"
assert app.CHANGELOG_PATHS["zh_tw"] == root / "doc/zh-TW/LOG.md"
assert app.STATIC_FILES["/static/style.css"][1] == root / "static/style.css"
'''
            result = subprocess.run([sys.executable, "-c", check], cwd=prefix, env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
