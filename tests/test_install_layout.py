"""Exercise the installer's in-place program-file copy without host changes."""

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallLayoutTests(unittest.TestCase):
    def test_in_place_web_install_creates_flat_entry_and_helper(self):
        installer = (ROOT / "deploy/install.sh").read_text()
        function = installer.split("copy_selected_files() {", 1)[1].split("\n}\n", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            source = prefix / "src/web"
            source.mkdir(parents=True)
            (source / "app.py").write_text("entry point\n")
            (source / "node_config.py").write_text("helper\n")
            script = f'''set -euo pipefail
SRC_DIR={prefix}
PREFIX={prefix}
ANYTLS_CONFIG_PATH={prefix}/absent-anytls
PROXY_CONFIG_PATH={prefix}/absent-proxy
has_module() {{ [ "$1" = web ]; }}
msg() {{ :; }}
copy_selected_files() {{{function}
}}
copy_selected_files
'''
            subprocess.run(["bash", "-c", script], check=True, capture_output=True,
                           text=True)
            self.assertEqual((prefix / "app.py").read_text(), "entry point\n")
            self.assertEqual((prefix / "node_config.py").read_text(), "helper\n")


if __name__ == "__main__":
    unittest.main()
