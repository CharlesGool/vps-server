"""Offline checks for later module installation and the public-page switch."""

from pathlib import Path
import hashlib
import io
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from src.web import module_manager


class ModuleManagerTests(unittest.TestCase):
    def test_frpc_release_asset_is_verified_before_caching(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            payload = b'release frpc'
            expected = hashlib.sha256(payload).hexdigest()
            with patch.object(module_manager, 'FRPC_SHA256', expected), \
                 patch.object(module_manager, 'urlopen', return_value=io.BytesIO(payload)):
                target = module_manager.download_frpc(prefix)
            self.assertEqual(target.read_bytes(), payload)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            target.unlink()
            with patch.object(module_manager, 'urlopen', return_value=io.BytesIO(b'corrupted')):
                with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                    module_manager.download_frpc(prefix)
            self.assertFalse(target.exists())

    def test_frpc_install_state_depends_on_binary_and_unit_not_instances(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            (prefix / '.install-state').write_text('modules=web\n')
            (prefix / 'app.py').write_text('')
            binary = prefix / 'frpc'
            unit = prefix / 'frpc@.service'
            with patch.object(module_manager, 'FRPC_BINARY', binary), patch.object(module_manager, 'FRPC_UNIT', unit):
                self.assertNotIn('frpc', module_manager.installed_modules(prefix))
                binary.write_bytes(b'frpc')
                self.assertNotIn('frpc', module_manager.installed_modules(prefix))
                unit.write_text('unit')
                self.assertIn('frpc', module_manager.installed_modules(prefix))

    def test_frpc_install_and_uninstall_preserve_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            source = prefix / 'installer-source/third_party/frp/frpc'
            source.parent.mkdir(parents=True)
            source.write_bytes(b'pinned frpc')
            template = prefix / 'installer-source/deploy/systemd/frpc@.service'
            template.parent.mkdir(parents=True)
            template.write_text('[Service]\nExecStart=/usr/local/bin/frpc\n')
            (prefix / 'data').mkdir()
            binary = prefix / 'frpc'
            unit = prefix / 'frpc@.service'
            config_dir = prefix / 'configs'
            config_dir.mkdir()
            config = config_dir / 'frpc-demo.toml'
            config.write_text('serverPort = 7000\n')
            commands = []

            def run(command, **_kwargs):
                commands.append(command)
                return type('Result', (), {'returncode': 0})()

            with patch.object(module_manager, 'FRPC_BINARY', binary), \
                 patch.object(module_manager, 'FRPC_UNIT', unit), \
                 patch.object(module_manager, 'FRPC_CONFIG_DIR', config_dir), \
                 patch.object(module_manager, 'FRPC_SHA256', hashlib.sha256(source.read_bytes()).hexdigest()), \
                 patch.object(module_manager.subprocess, 'run', side_effect=run):
                module_manager.run_install(prefix, 'frpc')
                self.assertTrue(module_manager.frpc_installed())
                self.assertEqual(binary.stat().st_mode & 0o777, 0o755)
                self.assertEqual(unit.read_bytes(), template.read_bytes())
                module_manager.run_uninstall(prefix, 'frpc')
                self.assertFalse(module_manager.frpc_installed())
            self.assertEqual(config.read_text(), 'serverPort = 7000\n')
            archives = list((prefix / 'data').glob('module-backup-frpc-*.tar.gz'))
            self.assertEqual(len(archives), 1)
            with tarfile.open(archives[0]) as archive:
                self.assertEqual(archive.getnames(), ['etc/frp/frpc-demo.toml'])
            self.assertIn(['systemctl', 'disable', '--now', 'frpc@demo.service'], commands)

    def test_builtin_feature_flag_survives_reloading(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            module_manager.set_feature(prefix, 'visitors', False)
            self.assertFalse(module_manager.feature_enabled(prefix, 'visitors'))
            module_manager.set_feature(prefix, 'visitors', True)
            self.assertTrue(module_manager.feature_enabled(prefix, 'visitors'))

    def test_port_forward_switch_waits_for_live_web_without_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            with patch.object(module_manager, 'wait_portfwd_applied') as applied, \
                 patch.object(module_manager.subprocess, 'run') as run:
                module_manager.set_feature(prefix, 'portfwd', False)
            self.assertEqual((prefix / 'data/portfwd-enabled').read_text(), '0\n')
            applied.assert_called_once()
            run.assert_not_called()

    def test_later_install_preserves_web_and_adds_only_the_requested_module(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            source = prefix / 'installer-source/deploy/install.sh'
            source.parent.mkdir(parents=True)
            source.write_text('#!/bin/sh\n')
            commands = []

            def run(command, **kwargs):
                commands.append((command, kwargs))
                return type('Result', (), {'returncode': 0})()

            with patch.object(module_manager, 'installed_modules', side_effect=[{'web'}, {'web', 'frps'}]), \
                 patch.object(module_manager.subprocess, 'run', side_effect=run):
                module_manager.run_install(prefix, 'frps')
            installer = [(command, options) for command, options in commands
                         if command[:1] == ['/usr/bin/bash']]
            self.assertEqual(len(installer), 1)
            self.assertEqual(installer[0][1]['env']['VPSSRV_MODULES'], 'web,frps')
            self.assertEqual(installer[0][1]['env']['PREFIX'], str(prefix))
            self.assertEqual(installer[0][1]['stdin'], module_manager.subprocess.DEVNULL)

    def test_public_page_switch_keeps_web_service_running(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            (prefix / 'data').mkdir()
            calls = []

            def run(command, **_kwargs):
                calls.append(command)
                return type('Result', (), {'returncode': 0})()

            with patch.object(module_manager, 'installed_modules', return_value={'web'}), \
                 patch.object(module_manager.subprocess, 'run', side_effect=run):
                module_manager.run_toggle(prefix, 'web', False)
            self.assertEqual((prefix / 'data/web-public-enabled').read_text(), '0\n')
            self.assertEqual(calls, [['systemctl', 'restart', 'vps-server-web.service']])

    def test_later_install_keeps_a_previously_disabled_node_module_off(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            source = prefix / 'installer-source/deploy/install.sh'
            source.parent.mkdir(parents=True)
            source.write_text('#!/bin/sh\n')
            commands = []

            def run(command, **_kwargs):
                commands.append(command)
                code = 1 if command[:3] == ['systemctl', 'is-enabled', '--quiet'] else 0
                return type('Result', (), {'returncode': code})()

            with patch.object(module_manager, 'installed_modules',
                              side_effect=[{'web', 'anytls'}, {'web', 'anytls', 'frps'}]), \
                 patch.object(module_manager.subprocess, 'run', side_effect=run):
                module_manager.run_install(prefix, 'frps')
            self.assertIn(['systemctl', 'disable', '--now', 'vps-server-anytls.service'], commands)


if __name__ == '__main__':
    unittest.main()
