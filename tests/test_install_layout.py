"""Exercise the installer's in-place program-file copy without host changes."""

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallLayoutTests(unittest.TestCase):
    def test_empty_proxy_config_is_valid_when_preserving_an_upgrade(self):
        installer = (ROOT / "deploy/install.sh").read_text()
        function = installer.split("preserve_proxy() {", 1)[1].split("\n}\n", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'proxy.json'
            config.write_text('{"inbounds": []}')
            script = f'''set -euo pipefail
PROXY_CONFIG_PATH={config}
msg() {{ :; }}
preserve_proxy() {{{function}
}}
preserve_proxy
'''
            subprocess.run(['bash', '-c', script], check=True, capture_output=True, text=True)

    def test_in_place_install_prepares_frpc_module_source_without_runtime_data(self):
        installer = (ROOT / "deploy/install.sh").read_text()
        function = installer.split("prepare_module_source() {", 1)[1].split("\n}\n", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            for relative in ("deploy/systemd/frpc@.service", "deploy/install.sh",
                             "config/VERSION", "src/web/app.py", "third_party/frp/frps"):
                path = prefix / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(relative)
            (prefix / "admin_password.txt").write_text("private")
            (prefix / "data").mkdir()
            (prefix / "data/session").write_text("private")
            script = f'''set -euo pipefail
SRC_DIR={prefix}
PREFIX={prefix}
PREFIX_ABS={prefix}
NEW_VERSION=dev-test
has_module() {{ [ "$1" = web ]; }}
chown() {{ :; }}
prepare_module_source() {{{function}
}}
prepare_module_source
'''
            subprocess.run(["bash", "-c", script], check=True, capture_output=True, text=True)
            payload = prefix / "installer-source"
            self.assertEqual((payload / "deploy/systemd/frpc@.service").read_text(),
                             "deploy/systemd/frpc@.service")
            self.assertEqual((payload / "config/VERSION").read_text(), "dev-test\n")
            self.assertFalse((payload / "admin_password.txt").exists())
            self.assertFalse((payload / "data").exists())
            self.assertEqual((prefix / "admin_password.txt").read_text(), "private")
            subprocess.run(["bash", "-c", script], check=True, capture_output=True, text=True)
            self.assertTrue((payload / "deploy/systemd/frpc@.service").is_file())

    def test_in_place_install_stages_frps_and_lucky_binaries(self):
        installer = (ROOT / "deploy/install.sh").read_text()
        function = installer.split("copy_selected_files() {", 1)[1].split("\n}\n", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            for module, executable in (("frp", "frps"), ("lucky", "lucky")):
                source = prefix / "third_party" / module
                source.mkdir(parents=True)
                (source / executable).write_text(f"{module} binary\n")
                (source / "LICENSE").write_text("license\n")
                (source / "component.txt").write_text("component\n")
                (prefix / "deploy" / ("frps" if module == "frp" else module)).mkdir(parents=True)
            script = f'''set -euo pipefail
SRC_DIR={prefix}
PREFIX={prefix}
ANYTLS_CONFIG_PATH={prefix}/absent-anytls
PROXY_CONFIG_PATH={prefix}/absent-proxy
MODULES=frps,lucky
has_module() {{ case ",$MODULES," in *",$1,"*) return 0 ;; esac; return 1; }}
msg() {{ :; }}
copy_selected_files() {{{function}
}}
copy_selected_files
'''
            subprocess.run(["bash", "-c", script], check=True, capture_output=True, text=True)
            for module, executable in (("frp", "frps"), ("lucky", "lucky")):
                self.assertEqual((prefix / "vendor" / module / executable).read_text(),
                                 f"{module} binary\n")

    def test_in_place_web_install_creates_flat_entry_and_helper(self):
        installer = (ROOT / "deploy/install.sh").read_text()
        function = installer.split("copy_selected_files() {", 1)[1].split("\n}\n", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            source = prefix / "src/web"
            source.mkdir(parents=True)
            (source / "app.py").write_text("entry point\n")
            (source / "node_config.py").write_text("helper\n")
            (source / "module_manager.py").write_text("module helper\n")
            (source / "frp_control.py").write_text("frp helper\n")
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
            self.assertEqual((prefix / "module_manager.py").read_text(), "module helper\n")
            self.assertEqual((prefix / "frp_control.py").read_text(), "frp helper\n")


if __name__ == "__main__":
    unittest.main()
