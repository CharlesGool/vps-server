"""AnyTLS catalog parity and installed/check-out loader behavior."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/anytls/setup-anytls.sh"
CATALOG_DIR = ROOT / "lang/anytls"
LANGUAGES = {
    "en": "en.sh", "zh_cn": "zh-CN.sh", "zh_tw": "zh-TW.sh",
    "zh_hk": "zh-HK.sh", "hi": "hi.sh", "es": "es.sh",
    "ar": "ar.sh", "fr": "fr.sh",
}


def catalog(path):
    return dict(re.findall(r"^  ([a-z_0-9]+)\) fmt='(.*?)' ;;$", path.read_text(), re.M))


class AnyTLSCatalogTest(unittest.TestCase):
    def test_catalog_keys_and_printf_formats_match(self):
        source = SCRIPT.read_text()
        used = set(re.findall(r"\$\(msg ([a-z_0-9]+)", source))
        english = catalog(CATALOG_DIR / "en.sh")
        self.assertEqual(used, set(english))
        for name in LANGUAGES.values():
            with self.subTest(name=name):
                path = CATALOG_DIR / name
                subprocess.run(["bash", "-n", str(path)], check=True)
                data = catalog(path)
                self.assertEqual(list(data), list(english))
                for key in english:
                    pattern = r"%(?:[0-9.]*[a-zA-Z%])"
                    self.assertEqual(re.findall(pattern, data[key]),
                                     re.findall(pattern, english[key]), key)
                    self.assertEqual(re.findall(r"\\[a-zA-Z0-9]", data[key]),
                                     re.findall(r"\\[a-zA-Z0-9]", english[key]), key)

    def test_checkout_catalog_loader_and_messages(self):
        source = SCRIPT.read_text()
        start = source.index('if [[ -f "${SCRIPT_DIR}/../lang/anytls/en.sh" ]]')
        end = source.index('\nC_G=', start)
        loader = source[start:end]
        with tempfile.TemporaryDirectory() as directory:
            deployed = Path(directory)
            (deployed / "anytls").mkdir()
            shutil.copytree(CATALOG_DIR, deployed / "lang/anytls")
            for layout, script_dir in (("checkout", SCRIPT.parent),
                                       ("deployed", deployed / "anytls")):
                for language, filename in LANGUAGES.items():
                    with self.subTest(layout=layout, language=language):
                        command = (f'SCRIPT_DIR={str(script_dir)!r}\n'
                                   f'VPSSRV_DEFAULT_LANG={language!r}\n'
                                   + loader + '\nmsg summary_port 443\n')
                        result = subprocess.run(["bash", "-e", "-c", command],
                                                capture_output=True, text=True, check=True)
                        expected = catalog(CATALOG_DIR / filename)["summary_port"] % "443"
                        self.assertEqual(result.stdout, expected)


if __name__ == "__main__":
    unittest.main()
