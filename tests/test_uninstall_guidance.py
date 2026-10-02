"""Offline checks for missing-module-script uninstall advice; no teardown runs."""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UninstallGuidanceTest(unittest.TestCase):
    def test_catalog_remains_available_after_prefix_removal(self):
        source = (ROOT / "deploy/uninstall.sh").read_text()
        message = re.search(r'^msg\(\) \{\n.*?^\}', source, re.M | re.S)
        self.assertIsNotNone(message)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "lang" / "uninstaller"
            catalog.mkdir(parents=True)
            (catalog / "en.sh").write_text((ROOT / "lang/uninstaller/en.sh").read_text())
            script = (message.group() + '\nmsg removed_unit example.service\n'
                      'rm -rf "$CATALOG_ROOT"\nmsg done\n')
            result = subprocess.run(
                ["bash", "-e", "-c", script],
                env={"INSTALL_LANG": "en", "CATALOG_ROOT": str(root / "lang")},
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Removed example.service", result.stdout)
            self.assertIn("vps-server has been uninstalled", result.stdout)

    def test_missing_anytls_script_preserves_shared_binary_used_by_proxy(self):
        source = (ROOT / "deploy/uninstall.sh").read_text()
        message = re.search(r'^msg\(\) \{\n.*?^\}', source, re.M | re.S)
        branch = re.search(
            r'^if \[ -f "/etc/systemd/system/\$\{ANYTLS_SERVICE\}" \]; then\n.*?^fi',
            source, re.M | re.S)
        self.assertIsNotNone(message)
        self.assertIsNotNone(branch)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            units = root / "units"
            units.mkdir()
            (units / "vps-server-anytls.service").touch()
            (units / "vps-server-proxy.service").touch()
            prefix = root / "installed"
            prefix.mkdir()  # Both modules exist; the anytls setup script is missing.
            (prefix / "proxy").mkdir()
            (prefix / "proxy/setup-proxy.sh").touch()
            isolated_branch = branch.group().replace('/etc/systemd/system/${ANYTLS_SERVICE}',
                                                     '${UNIT_DIR}/${ANYTLS_SERVICE}')
            script = message.group() + '\n' + isolated_branch + '\n'
            for lang, keep, confirm in (
                ("en", "keep", "only after confirming no module uses it"),
                ("zh_cn", "保留", "仅在确认没有模块使用时才清理"),
                ("zh_tw", "保留", "僅在確認沒有模組使用時才清理"),
            ):
                with self.subTest(lang=lang):
                    result = subprocess.run(["bash", "-e", "-c", script],
                                            env={"INSTALL_LANG": lang, "PREFIX": str(prefix),
                                                 "CATALOG_ROOT": str(ROOT / "lang"),
                                                 "UNIT_DIR": str(units),
                                                 "ANYTLS_SERVICE": "vps-server-anytls.service"},
                                            capture_output=True, text=True, check=True)
                    self.assertIn("/usr/local/bin/sing-box-vps-server", result.stdout)
                    self.assertIn("proxy", result.stdout)
                    self.assertIn(keep, result.stdout)
                    self.assertIn(confirm, result.stdout)
                    self.assertNotRegex(result.stdout, r'(?m)^\s*rm\b[^\n]*sing-box-vps-server')

    def test_qrcode_comment_names_existing_vendor_sources(self):
        comment = (ROOT / "src/web/static/qrcode-render.js").read_text().split("// Own code", 1)[0]
        for path in ("src/web/static/third_party/qrcode/qrcode.js", "src/web/static/third_party/qrcode/qrcode-utf8.js"):
            self.assertIn(path, comment)
            self.assertTrue((ROOT / path).is_file())


if __name__ == "__main__":
    unittest.main()
