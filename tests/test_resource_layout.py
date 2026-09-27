"""Offline regression tests for checkout-to-deployment resource paths."""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ResourceLayoutTest(unittest.TestCase):
    def test_copy_stage_web_and_module_only_and_in_place(self):
        source = (ROOT / "deploy/install.sh").read_text()
        functions = []
        for name in ("copy_singbox_binary", "copy_selected_files"):
            match = re.search(rf"^{name}\(\) \{{\n.*?^\}}", source, re.M | re.S)
            self.assertIsNotNone(match)
            functions.append(match.group())
        # Execute only the actual installer's extracted copy stage. None of
        # the prompts, service operations or package installation are sourced.
        stage = ('has_module() { case " $MODULES " in *" $1 "*) return 0;; '
                 '*) return 1;; esac; }\n'
                 'msg() { :; }\n' + '\n'.join(functions) + '\ncopy_selected_files\n')
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for modules in ("web", "web anytls proxy", "anytls", "proxy"):
                with self.subTest(modules=modules):
                    prefix = base / modules.replace(' ', '-')
                    prefix.mkdir()
                    for name in ("data", "certs"):
                        (prefix / name).mkdir()
                        (prefix / name / "sentinel").write_text("keep")
                    for name in ("admin_password.txt", ".install-state"):
                        (prefix / name).write_text("keep")
                    (prefix / "app.py").write_text("existing app")
                    for module in ("anytls", "proxy"):
                        (prefix / module).mkdir()
                        (prefix / module / "sentinel").write_text("keep")
                    subprocess.run(["bash", "-e", "-c", stage], env={
                        "SRC_DIR": str(ROOT), "PREFIX": str(prefix), "MODULES": modules,
                    }, check=True)
                    for name in ("data/sentinel", "certs/sentinel", "admin_password.txt", ".install-state"):
                        self.assertEqual((prefix / name).read_text(), "keep")
                    if "web" in modules:
                        self.assertEqual((prefix / "app.py").read_bytes(), (ROOT / "src/web/app.py").read_bytes())
                        self.assertEqual((prefix / "node_config.py").read_bytes(),
                                         (ROOT / "src/web/node_config.py").read_bytes())
                        cli = subprocess.run(["python3", str(prefix / "node_config.py")],
                                             capture_output=True, text=True)
                        self.assertEqual(cli.returncode, 2)
                        self.assertIn("usage: node_config.py", cli.stderr)
                        self.assertEqual((prefix / "static/third_party/librespeed/speedtest.js").read_bytes(),
                                         (ROOT / "static/third_party/librespeed/speedtest.js").read_bytes())
                    else:
                        self.assertEqual((prefix / "app.py").read_text(), "existing app")
                    self.assertTrue((prefix / "lang/installer/en.sh").is_file())
                    for module in ("anytls", "proxy"):
                        if module in modules:
                            self.assertTrue((prefix / module / f"setup-{module}.sh").is_file())
                            self.assertTrue((prefix / "lang" / module / "en.sh").is_file())
                        elif "web" not in modules:
                            self.assertEqual((prefix / module / "sentinel").read_text(), "keep")
                    if "web" in modules:
                        self.assertTrue((prefix / "systemd/vps-server-web.service").is_file())
                    if "anytls" in modules or "proxy" in modules:
                        self.assertEqual((prefix / "sing-box").read_bytes(),
                                         (ROOT / "third_party/sing-box/sing-box").read_bytes())
                        for metadata in ("LICENSE", "sing-box.version"):
                            self.assertEqual((prefix / "vendor/sing-box" / metadata).read_bytes(),
                                             (ROOT / "third_party/sing-box" / metadata).read_bytes())
                    else:
                        self.assertFalse((prefix / "sing-box").exists())

            # In-place checkout lacks the root binary. Never remove a source
            # directory, but still populate the promised deployed root entry.
            inplace = base / "inplace"
            (inplace / "third_party").mkdir(parents=True)
            (inplace / "third_party/sing-box").mkdir()
            (inplace / "third_party/sing-box/sing-box").write_bytes(b"binary fixture")
            (inplace / "deploy/anytls").mkdir(parents=True)
            (inplace / "deploy/anytls/sentinel").write_text("keep")
            (inplace / "deploy/proxy").mkdir(parents=True)
            (inplace / "deploy/proxy/sentinel").write_text("proxy source")
            (inplace / "app.py").write_text("keep")
            (inplace / "src/web").mkdir(parents=True)
            (inplace / "src/web/app.py").write_text("new app")
            (inplace / "src/web/node_config.py").write_text("new helper")
            for modules in ("anytls", "web proxy"):
                with self.subTest(inplace=modules):
                    subprocess.run(["bash", "-e", "-c", stage], env={
                        "SRC_DIR": str(inplace), "PREFIX": str(inplace), "MODULES": modules,
                    }, check=True)
                    self.assertEqual((inplace / "sing-box").read_bytes(), b"binary fixture")
                    self.assertEqual((inplace / "deploy/anytls/sentinel").read_text(), "keep")
                    if "anytls" in modules:
                        self.assertEqual((inplace / "anytls/sentinel").read_text(), "keep")
                    if "proxy" in modules:
                        self.assertEqual((inplace / "proxy/sentinel").read_text(), "proxy source")
                    if "web" in modules:
                        self.assertEqual((inplace / "app.py").read_text(), "new app")
                        self.assertEqual((inplace / "node_config.py").read_text(), "new helper")
                    else:
                        self.assertEqual((inplace / "app.py").read_text(), "keep")

    def test_installer_resolves_checkout_root_from_deploy_directory(self):
        source = (ROOT / "deploy/install.sh").read_text()
        assignment = re.search(r'^SRC_DIR=".*"$', source, re.M)
        self.assertIsNotNone(assignment)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "deploy").mkdir()
            script = root / "deploy/probe.sh"
            script.write_text('#!/usr/bin/env bash\n' + assignment.group() + '\nprintf "%s" "$SRC_DIR"\n')
            result = subprocess.run(["bash", str(script)], cwd="/", capture_output=True,
                                    text=True, check=True)
            self.assertEqual(result.stdout, str(root))

    def test_deploy_entries_are_available(self):
        for name in ("install.sh", "uninstall.sh"):
            with self.subTest(name=name):
                self.assertTrue((ROOT / "deploy" / name).is_file())

    def test_module_local_binary_in_checkout_and_deployed_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            deployed = Path(directory)
            (deployed / "sing-box").write_bytes(b"installed")
            for module, filename in (("anytls", "setup-anytls.sh"), ("proxy", "setup-proxy.sh")):
                script = (ROOT / "deploy" / module / filename).read_text()
                block = re.search(r'^LOCAL_BIN="\$\{SCRIPT_DIR\}/\.\./sing-box"\nif .*?^fi',
                                  script, re.M | re.S)
                self.assertIsNotNone(block)
                for module_dir, expected in ((ROOT / "deploy" / module, ROOT / "third_party/sing-box/sing-box"),
                                             (deployed / module, deployed / "sing-box")):
                    module_dir.mkdir(exist_ok=True)
                    result = subprocess.run(
                        ["bash", "-c", block.group() + '\nprintf "%s" "$LOCAL_BIN"'],
                        env={"SCRIPT_DIR": str(module_dir)}, capture_output=True, text=True, check=True)
                    self.assertEqual(Path(result.stdout).resolve(), expected)
                    self.assertTrue(expected.is_file())


if __name__ == "__main__":
    unittest.main()
