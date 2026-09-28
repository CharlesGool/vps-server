"""The standalone proxy module must load its native messages in both layouts."""

import re
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/proxy/setup-proxy.sh"
CATALOGS = ROOT / "lang/proxy"
LOCALES = {
    "en": "en.sh", "zh_cn": "zh-CN.sh", "zh_tw": "zh-TW.sh",
    "zh_hk": "zh-HK.sh", "hi": "hi.sh", "es": "es.sh",
    "ar": "ar.sh", "fr": "fr.sh",
}
ENTRY = re.compile(r"^  (\w+)\) fmt='(.*)' ;;$", re.MULTILINE)
FORMAT = re.compile(r"%(?:[0-9]+\$)?[sd]")


class ProxyLocaleTest(unittest.TestCase):
    def test_catalogs_have_matching_keys_and_placeholders(self):
        english = dict(ENTRY.findall((CATALOGS / "en.sh").read_text()))
        self.assertEqual(len(english), 49)
        for filename in LOCALES.values():
            with self.subTest(filename=filename):
                catalog = dict(ENTRY.findall((CATALOGS / filename).read_text()))
                self.assertEqual(list(catalog), list(english))
                for key, value in catalog.items():
                    self.assertEqual(FORMAT.findall(value), FORMAT.findall(english[key]), key)

    def test_loader_works_from_checkout_and_installed_layout(self):
        script = SCRIPT.read_text()
        loader = "# Native catalogs" + script.split("# Native catalogs", 1)[1].split("C_G=", 1)[0]
        with tempfile.TemporaryDirectory() as temporary:
            prefix = Path(temporary)
            (prefix / "proxy").mkdir()
            (prefix / "lang").symlink_to(CATALOGS.parent)
            for directory in (SCRIPT.parent, prefix / "proxy"):
                for locale in LOCALES:
                    with self.subTest(layout=str(directory), locale=locale):
                        command = (f"SCRIPT_DIR={shlex.quote(str(directory))}\n"
                                   f"VPSSRV_DEFAULT_LANG={shlex.quote(locale)}\n"
                                   f"{loader}\nmsg config_written /tmp/config.json vmess")
                        result = subprocess.run(["bash", "-e", "-c", command],
                                                text=True, capture_output=True, check=True)
                        self.assertIn("/tmp/config.json", result.stdout)
                        self.assertIn("vmess", result.stdout)


if __name__ == "__main__":
    unittest.main()
