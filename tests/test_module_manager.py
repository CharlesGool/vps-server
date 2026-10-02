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
    def test_reinstall_discards_only_inventory_from_removed_module(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / 'app'
            (prefix / 'data').mkdir(parents=True)
            state = Path(directory) / 'state.json'
            state.write_text('{"old":"inventory"}')
            inventory = {'nodes': [
                {'protocol': 'anytls', 'id': 'keep'},
                {'protocol': 'vmess', 'id': 'remove'},
            ]}
            with patch.object(module_manager, 'read_inventory', return_value=inventory), \
                 patch.object(module_manager, 'write_inventory') as write:
                module_manager.reconcile_removed_nodes(prefix, {'anytls'}, state_path=state,
                                                       lock_path=Path(directory) / 'node.lock')
            self.assertEqual([node['id'] for node in inventory['nodes']], ['keep'])
            write.assert_called_once_with(inventory, state_path=state)
            backups = list((prefix / 'data').glob('node-inventory-before-reinstall-*.json'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), '{"old":"inventory"}')

    def test_frpc_group_switch_does_not_follow_instance_activity(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            (prefix / 'data').mkdir()
            with patch.object(module_manager, 'frpc_installed', return_value=True), \
                 patch.object(module_manager, 'frpc_names', return_value=[]), \
                 patch.object(module_manager.subprocess, 'run') as run:
                self.assertTrue(module_manager.frpc_group_enabled(prefix))
                module_manager.run_toggle(prefix, 'frpc', False)
                self.assertFalse(module_manager.frpc_group_enabled(prefix))
                module_manager.run_toggle(prefix, 'frpc', True)
                self.assertTrue(module_manager.frpc_group_enabled(prefix))
                run.assert_not_called()
            (prefix / 'data/frpc-group-enabled').unlink()
            (prefix / 'data/frpc-group-active.json').write_text('[]\n')
            self.assertFalse(module_manager.frpc_group_enabled(prefix))

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

    def test_frps_install_does_not_rerun_other_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            source = prefix / 'installer-source/deploy/frps/setup-frps.sh'
            source.parent.mkdir(parents=True)
            source.write_text('#!/bin/sh\n')
            (prefix / '.install-state').write_text('version=test\nmodules=web,proxy\n')
            commands = []

            def run(command, **kwargs):
                commands.append((command, kwargs))
                return type('Result', (), {'returncode': 0})()

            with patch.object(module_manager, 'installed_modules', side_effect=[{'web'}, {'web'}, {'web', 'frps'}]), \
                 patch.object(module_manager.subprocess, 'run', side_effect=run):
                module_manager.run_install(prefix, 'frps')
            installer = [(command, options) for command, options in commands
                         if command[:1] == ['/usr/bin/bash']]
            self.assertEqual(len(installer), 1)
            self.assertEqual(installer[0][0][1], str(source))
            self.assertEqual(installer[0][1]['env']['PREFIX'], str(prefix))
            self.assertEqual(installer[0][1]['stdin'], module_manager.subprocess.DEVNULL)
            self.assertEqual((prefix / '.install-state').read_text(),
                             'version=test\nmodules=web,proxy,frps\n')

    def test_singbox_group_installs_both_services_in_one_run(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            source = prefix / 'installer-source/deploy/install.sh'
            source.parent.mkdir(parents=True)
            source.write_text('#!/bin/sh\n')
            commands = []

            def run(command, **kwargs):
                commands.append((command, kwargs))
                return type('Result', (), {'returncode': 0})()

            with patch.object(module_manager, 'installed_modules', side_effect=[{'web'}, {'web', 'proxy', 'anytls'}]), \
                 patch.object(module_manager, 'reconcile_removed_nodes') as reconcile, \
                 patch.object(module_manager.subprocess, 'run', side_effect=run):
                module_manager.run_install(prefix, 'proxy_nodes')
            installer = [(command, options) for command, options in commands
                         if command[:1] == ['/usr/bin/bash']]
            self.assertEqual(len(installer), 1)
            self.assertEqual(installer[0][1]['env']['VPSSRV_MODULES'], 'web,anytls,proxy')
            reconcile.assert_called_once_with(prefix, {'web'})

    def test_iperf3_install_preserves_other_modules_and_node_files(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            (prefix / 'app.py').write_text('web')
            (prefix / 'data').mkdir()
            state = prefix / '.install-state'
            state.write_text('version=3.0.0\nmodules=web,anytls,proxy,frps\nvars=old\n')
            node = prefix / 'data/node.json'
            node.write_text('{"credential":"unchanged"}')
            commands = []

            def run(command, **_kwargs):
                commands.append(command)
                return type('Result', (), {'returncode': 0})()

            with patch.object(module_manager, 'installed_modules', side_effect=[{'web'}, {'web'}]), \
                 patch.object(module_manager.shutil, 'which', side_effect=[None, '/usr/bin/iperf3']), \
                 patch.object(module_manager.subprocess, 'run', side_effect=run):
                module_manager.run_install(prefix, 'iperf3')
            self.assertEqual(node.read_text(), '{"credential":"unchanged"}')
            self.assertEqual(state.read_text(),
                             'version=3.0.0\nmodules=web,anytls,proxy,frps,iperf3\nvars=old\n')
            self.assertEqual((prefix / 'data/iperf3-enabled').read_text(), '1\n')
            self.assertEqual(commands, [
                ['apt-get', 'update'],
                ['apt-get', 'install', '-y', 'iperf3'],
                ['systemctl', 'restart', 'vps-server-web.service'],
            ])

    def test_public_listeners_keep_independent_state_and_restart_web(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            (prefix / 'data').mkdir()
            (prefix / 'data/web-public-enabled').write_text('0\n')
            calls = []

            def run(command, **_kwargs):
                calls.append(command)
                return type('Result', (), {'returncode': 0})()

            with patch.object(module_manager, 'installed_modules', return_value={'web'}), \
                 patch.object(module_manager.subprocess, 'run', side_effect=run), \
                 patch.object(module_manager, 'wait_public_listener_applied'), \
                 patch.object(module_manager.time, 'sleep'):
                self.assertFalse(module_manager.public_listener_enabled(prefix, 'web_http'))
                self.assertFalse(module_manager.public_listener_enabled(prefix, 'web_https'))
                module_manager.run_toggle(prefix, 'web_http', True)
                self.assertTrue(module_manager.public_listener_enabled(prefix, 'web_http'))
                self.assertFalse(module_manager.public_listener_enabled(prefix, 'web_https'))
                module_manager.run_toggle(prefix, 'web_https', True)
                module_manager.run_toggle(prefix, 'web_http', False)
            self.assertFalse(module_manager.public_listener_enabled(prefix, 'web_http'))
            self.assertTrue(module_manager.public_listener_enabled(prefix, 'web_https'))
            self.assertEqual((prefix / 'data/web-public-enabled').read_text(), '0\n')
            self.assertEqual(len(calls), 3)
            self.assertTrue(all(call == ['systemctl', 'restart', 'vps-server-web.service'] for call in calls))

    def test_occupied_public_port_restores_previous_switch_state(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            (prefix / 'data').mkdir()
            flag = prefix / 'data/web-http-enabled'
            flag.write_text('0\n')
            with patch.object(module_manager.subprocess, 'run') as restart, \
                 patch.object(module_manager, 'wait_public_listener_applied',
                              side_effect=module_manager.PublicPortOccupied(80)):
                with self.assertRaises(module_manager.PublicPortOccupied):
                    module_manager.switch_public_listener(prefix, 'web_http', True)
            self.assertEqual(flag.read_text(), '0\n')
            self.assertEqual(restart.call_count, 2)

    def test_live_listener_report_identifies_occupied_port(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            (prefix / 'data').mkdir()
            (prefix / 'data/public-listeners.json').write_text(
                '{"pid": 22, "http": {"port": 80, "enabled": true, "bound": false, "reason": "occupied"}}')
            with self.assertRaises(module_manager.PublicPortOccupied) as raised:
                module_manager.wait_public_listener_applied(prefix, 'web_http', True, 21)
            self.assertEqual(raised.exception.port, 80)

    def test_later_install_keeps_a_previously_disabled_node_module_off(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            source = prefix / 'installer-source/deploy/frps/setup-frps.sh'
            source.parent.mkdir(parents=True)
            source.write_text('#!/bin/sh\n')
            (prefix / '.install-state').write_text('version=test\nmodules=web,anytls\n')
            commands = []

            def run(command, **_kwargs):
                commands.append(command)
                code = 1 if command[:3] == ['systemctl', 'is-enabled', '--quiet'] else 0
                return type('Result', (), {'returncode': code})()

            with patch.object(module_manager, 'installed_modules',
                              side_effect=[{'web', 'anytls'}, {'web', 'anytls'}, {'web', 'anytls', 'frps'}]), \
                 patch.object(module_manager.subprocess, 'run', side_effect=run):
                module_manager.run_install(prefix, 'frps')
            self.assertEqual(commands, [['/usr/bin/bash', str(source)]])


if __name__ == '__main__':
    unittest.main()
