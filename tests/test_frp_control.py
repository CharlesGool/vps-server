"""Recovery checks for privileged FRP configuration edits."""

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from src.web import frp_control as control


class FrpControlTest(unittest.TestCase):
    def test_unicode_instance_name_keeps_config_suffix_and_uses_safe_unit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clients = root / 'frp'
            clients.mkdir()
            binary = root / 'frpc'
            binary.touch()
            unit_template = root / 'frpc@.service'
            unit_template.touch()
            registry = root / 'PORTS.md'
            registry.write_text(control.HEADER)
            commands = []

            def run(argv, **_kwargs):
                commands.append(argv)
                return subprocess.CompletedProcess(argv, 0)

            name = '示例-一'
            renamed = '示例-二'
            with patch.object(control, 'CLIENT_DIR', clients), \
                 patch.object(control, 'CLIENT_BIN', binary), \
                 patch.object(control, 'CLIENT_UNIT', unit_template), \
                 patch.object(control, 'REGISTRY', registry), \
                 patch.object(control, 'LOCK', root / '.ports.lock'), \
                 patch.object(control.subprocess, 'run', side_effect=run):
                content = control.build_client('203.0.113.42', 7000, 'example-token', [])
                control.save_client(name, content)
                old_path = clients / f'frpc-{name}.toml'
                old_alias = control.client_alias(name)
                self.assertEqual(old_path.read_text(), content)
                self.assertEqual(old_alias.readlink(), Path(old_path.name))
                self.assertEqual(control.client_names(), [name])
                self.assertRegex(control.client_unit(name), r'^frpc@u-[0-9a-f]{24}\.service$')
                self.assertIn(['systemctl', 'enable', '--now', control.client_unit(name)], commands)
                control.rename_client(name, renamed)
                self.assertFalse(old_path.exists())
                self.assertFalse(old_alias.exists())
                self.assertEqual(control.client_names(), [renamed])
                self.assertEqual(control.client_alias(renamed).readlink(), Path(f'frpc-{renamed}.toml'))
                control.delete_client(renamed)
                self.assertEqual(control.client_names(), [])
                self.assertFalse(control.client_alias(renamed).exists())
                self.assertEqual(len(list(clients.glob('.deleted-frpc-*.toml'))), 1)

        for invalid in ('../frp', 'name/other', 'smile😀', 'a' * 33):
            with self.assertRaises(ValueError):
                control.client_unit(invalid)

    def test_failed_unicode_client_start_removes_config_and_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clients = root / 'frp'
            clients.mkdir()
            binary = root / 'frpc'
            binary.touch()
            unit_template = root / 'frpc@.service'
            unit_template.touch()
            registry = root / 'PORTS.md'
            registry.write_text(control.HEADER)
            name = '示例-一'

            def run(argv, **_kwargs):
                if argv[:3] == ['systemctl', 'enable', '--now']:
                    raise subprocess.CalledProcessError(1, argv)
                return subprocess.CompletedProcess(argv, 0)

            with patch.object(control, 'CLIENT_DIR', clients), \
                 patch.object(control, 'CLIENT_BIN', binary), \
                 patch.object(control, 'CLIENT_UNIT', unit_template), \
                 patch.object(control, 'REGISTRY', registry), \
                 patch.object(control, 'LOCK', root / '.ports.lock'), \
                 patch.object(control.subprocess, 'run', side_effect=run):
                with self.assertRaises(subprocess.CalledProcessError):
                    control.save_client(name, control.build_client('203.0.113.42', 7000,
                                                                   'example-token', []))
                self.assertFalse(control.client_path(name).exists())
                self.assertFalse(control.client_alias(name).is_symlink())

    def test_add_proxy_does_not_require_an_existing_index(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(control, 'CLIENT_DIR', Path(directory)):
            path = Path(directory) / 'frpc-demo.toml'
            path.write_text(control.build_client('203.0.113.42', 7000, 'secret', []))
            proxy = {'name': 'web', 'type': 'tcp', 'localIP': '127.0.0.1',
                     'localPort': 8080, 'remotePort': 18080}
            with patch.object(control, 'save_client') as save:
                control.update_structured('demo', 'add', {'proxy': proxy})
            self.assertEqual(save.call_args.args[0], 'demo')
            self.assertIn('remotePort = 18080', save.call_args.args[1])
            self.assertEqual(save.call_args.args[1].count('[[proxies]]'), 1)

    def test_structured_editor_reads_simple_config_and_rejects_extra_fields(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(control, 'CLIENT_DIR', Path(directory)):
            path = Path(directory) / 'frpc-demo.toml'
            path.write_text('# existing comment\nserverAddr = "203.0.113.42"\nserverPort = 7000\n'
                            'auth.method = "token"\nauth.token = "secret"\n[[proxies]]\n'
                            'name = "web"\ntype = "tcp"\nlocalIP = "127.0.0.1"\n'
                            'localPort = 8080\nremotePort = 18080\n')
            data = control.structured_client('demo')
            self.assertEqual(data['proxies'][0]['remotePort'], 18080)
            self.assertEqual(control.build_client(data['serverAddr'], data['serverPort'],
                                                  data['auth']['token'], data['proxies']).count('[[proxies]]'), 1)
            udp = dict(data['proxies'][0], type='udp')
            path.write_text(control.build_client(data['serverAddr'], data['serverPort'], data['auth']['token'], [udp]))
            self.assertEqual(control.structured_client('demo')['proxies'][0]['type'], 'udp')
            path.write_text(path.read_text() + 'transport.protocol = "websocket"\n')
            self.assertIsNone(control.structured_client('demo'))

    def test_structured_builder_validates_proxy_before_write(self):
        proxy = {'name': 'web', 'type': 'tcp', 'localIP': '127.0.0.1',
                 'localPort': 8080, 'remotePort': 18080}
        with self.assertRaises(ValueError):
            control.build_client('invalid host', 7000, 'secret', [proxy])
        with self.assertRaises(ValueError):
            control.build_client('203.0.113.42', 7000, 'secret', [proxy, proxy])

    def test_same_host_client_ports_are_identified_for_registration(self):
        local = ('serverAddr = "127.0.0.1"\nserverPort = 7000\n'
                 '[[proxies]]\nname = "web"\nremotePort = 18080\n')
        self.assertEqual(control._local_client_ports(local), {18080})
        self.assertEqual(control._local_client_ports(local.replace('127.0.0.1', '192.0.2.10')), set())

    def test_failed_server_edit_releases_new_port_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'frps.toml'
            config.write_text('bindPort = 7000\nauth.token = "old"\n')
            registry = root / 'PORTS.md'
            original = control.HEADER + '| 7000 | vps-server frps | 0.0.0.0 | 2026-09-29 |\n'
            registry.write_text(original)
            setup = root / 'setup-frps.sh'
            setup.write_text('')
            with patch.object(control, 'SERVER_CONFIG', config), \
                 patch.object(control, 'SERVER_SETUP', setup), \
                 patch.object(control, 'REGISTRY', registry), \
                 patch.object(control, 'LOCK', root / '.ports.lock'), \
                 patch.object(control, '_free_port'), \
                 patch.object(control.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'bash')):
                with self.assertRaises(subprocess.CalledProcessError):
                    control.save_server(7001, 'new-token')
            self.assertEqual(registry.read_text(), original)
            self.assertEqual(config.read_text(), 'bindPort = 7000\nauth.token = "old"\n')

    def test_failed_client_verify_restores_existing_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            client_dir = root / 'frp'
            client_dir.mkdir()
            config = client_dir / 'frpc-gz.toml'
            original = 'serverAddr = "remote.example"\nserverPort = 7000\nauth.token = "old"\n'
            config.write_text(original)
            binary = root / 'frpc'
            binary.touch()
            unit = root / 'frpc@.service'
            unit.touch()
            def run(argv, **kwargs):
                if 'verify' in argv:
                    raise subprocess.CalledProcessError(1, argv)
                return subprocess.CompletedProcess(argv, 0)
            with patch.object(control, 'CLIENT_DIR', client_dir), \
                 patch.object(control, 'CLIENT_BIN', binary), \
                 patch.object(control, 'CLIENT_UNIT', unit), \
                 patch.object(control, 'LOCK', root / '.ports.lock'), \
                 patch.object(control.subprocess, 'run', side_effect=run):
                with self.assertRaises(subprocess.CalledProcessError):
                    control.save_client('gz', original.replace('old', 'new'))
            self.assertEqual(config.read_text(), original)
            self.assertEqual(config.stat().st_mode & 0o777, 0o600)

    def test_rename_and_delete_client_preserve_recovery_and_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clients = root / 'frp'
            clients.mkdir()
            old = clients / 'frpc-demo.toml'
            old.write_text('serverAddr = "203.0.113.42"\n')
            registry = root / 'PORTS.md'
            registry.write_text(control.HEADER + '| 18080 | vps-server frpc demo | 0.0.0.0 | 2026-09-29 |\n')
            commands = []
            def run(argv, **kwargs):
                commands.append(argv)
                return subprocess.CompletedProcess(argv, 0)
            with patch.object(control, 'CLIENT_DIR', clients), \
                 patch.object(control, 'REGISTRY', registry), \
                 patch.object(control, 'LOCK', root / '.ports.lock'), \
                 patch.object(control.subprocess, 'run', side_effect=run):
                control.rename_client('demo', 'new')
                self.assertFalse(old.exists())
                self.assertTrue((clients / 'frpc-new.toml').exists())
                self.assertIn('vps-server frpc new', registry.read_text())
                self.assertIn(['systemctl', 'start', 'frpc@new.service'], commands)
                control.delete_client('new')
                self.assertFalse((clients / 'frpc-new.toml').exists())
                self.assertEqual(list(clients.glob('.deleted-frpc-new-*.toml'))[0].read_text(),
                                 'serverAddr = "203.0.113.42"\n')
                self.assertNotIn('vps-server frpc new', registry.read_text())


if __name__ == '__main__':
    unittest.main()
