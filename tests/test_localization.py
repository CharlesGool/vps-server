"""Checks the packaged language catalogs and runtime language selection."""

import json
import os
import re
import string
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / "lang" / "web"
TAGS = ("en", "zh-CN", "zh-TW", "zh-HK", "hi", "es", "ar", "fr")


class LocalizationTest(unittest.TestCase):
    def test_catalogs_have_the_same_keys_and_format_fields(self):
        catalogs = {tag: json.loads((CATALOG_DIR / f"{tag}.json").read_text(encoding="utf-8"))
                    for tag in TAGS}
        english = catalogs["en"]
        self.assertEqual(len(english), 310)
        formatter = string.Formatter()
        def fields(value):
            return {field for _, field, _, _ in formatter.parse(value) if field is not None}
        for tag, catalog in catalogs.items():
            with self.subTest(tag=tag):
                self.assertEqual(list(catalog), list(english))
                for key, value in catalog.items():
                    self.assertEqual(fields(value), fields(english[key]), (tag, key))

    def test_dependency_verifier_catalogs_keep_named_fields(self):
        directory = ROOT / "lang" / "verify_dependencies"
        catalogs = {tag: json.loads((directory / f"{tag}.json").read_text(encoding="utf-8"))
                    for tag in TAGS}
        english = catalogs["en"]
        self.assertEqual(len(english), 7)
        formatter = string.Formatter()
        for tag, catalog in catalogs.items():
            with self.subTest(tag=tag):
                self.assertEqual(list(catalog), list(english))
                for key, value in catalog.items():
                    fields = [field for _, field, _, _ in formatter.parse(value) if field is not None]
                    english_fields = [field for _, field, _, _ in formatter.parse(english[key]) if field is not None]
                    self.assertEqual(fields, english_fields, (tag, key))

    def test_setup_wizard_catalogs_keep_html_and_format_slots(self):
        catalog_dir = ROOT / "lang" / "setup_wizard"
        catalogs = {tag: json.loads((catalog_dir / f"{tag}.json").read_text(encoding="utf-8"))
                    for tag in TAGS}
        english = catalogs["en"]
        self.assertEqual(len(english), 29)
        for tag, catalog in catalogs.items():
            with self.subTest(tag=tag):
                self.assertEqual(list(catalog), list(english))
                for key, value in catalog.items():
                    self.assertEqual(re.findall(r"%(?:s|d)", value),
                                     re.findall(r"%(?:s|d)", english[key]), (tag, key))
                    self.assertEqual(re.findall(r"<[^>]+>", value),
                                     re.findall(r"<[^>]+>", english[key]), (tag, key))

    def test_shell_catalogs_keep_keys_and_printf_shapes(self):
        expected_counts = {"installer": 96, "anytls": 71, "proxy": 49,
                           "frps": 16, "lucky": 23, "uninstaller": 15}
        format_pattern = r"%(?:[0-9]+\$)?[-+ #0]*[0-9.]*(?:s|d|i|u|f|%)"
        for component, expected_count in expected_counts.items():
            catalog_dir = ROOT / "lang" / component
            rows = {}
            for tag in TAGS:
                path = catalog_dir / f"{tag}.sh"
                source = path.read_text(encoding="utf-8")
                result = subprocess.run(["bash", "-n", str(path)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, (component, tag, result.stderr))
                pairs = re.findall(r"^  ([a-z0-9_]+)\) fmt='(.*)' ;;$", source, re.M)
                self.assertEqual(len(pairs), expected_count, (component, tag))
                rows[tag] = dict(pairs)
            english = rows["en"]
            for tag, catalog in rows.items():
                with self.subTest(component=component, tag=tag):
                    self.assertEqual(list(catalog), list(english))
                    for key, value in catalog.items():
                        self.assertEqual(re.findall(format_pattern, value),
                                         re.findall(format_pattern, english[key]), (component, tag, key))
                        self.assertEqual(re.findall(r"\\.", value),
                                         re.findall(r"\\.", english[key]), (component, tag, key))

    def test_runtime_switches_languages_and_uses_local_changelogs(self):
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env.update(VPSSRV_DATA_DIR=directory,
                       VPSSRV_PASSWORD_FILE=str(Path(directory) / "password"),
                       VPSSRV_CONSOLE_PORT_FILE=str(Path(directory) / "port"))
            source = '''from src.web import app
assert app.pick_lang(None, "zh_hk", "") == "zh_hk"
assert app.pick_lang(None, None, "zh-HK,zh;q=0.9") == "zh_hk"
assert app.pick_lang(None, None, "es-ES,es;q=0.9") == "es"
assert 'lang="ar" dir="rtl"' in app.render_page("", "", "ar")
for code, path in app.CHANGELOG_PATHS.items():
    assert path.is_file(), (code, path)
    assert app.changelog_section(path.read_text(encoding="utf-8")), code
'''
            result = subprocess.run([sys.executable, "-c", source], cwd=ROOT, env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
