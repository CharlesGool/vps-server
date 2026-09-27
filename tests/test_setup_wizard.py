import http.client
import hashlib
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
from pathlib import Path
import threading
import time
import unittest
from urllib.parse import urlencode

from tools.setup_wizard.setup_wizard import Wizard, validate


class WizardTests(unittest.TestCase):
    def setUp(self):
        self.server = Wizard(('127.0.0.1', 0), 'web,iperf3,proxy', True, 5, 'vmess')
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_selection)
        self.thread.start()

    def tearDown(self):
        self.server.expires = 0
        self.thread.join(timeout=2)
        self.server.server_close()
        self.assertFalse(self.thread.is_alive())
        # The listening socket must be relinquished after success or expiry.
        with Wizard(('127.0.0.1', self.port)):
            pass

    def request(self, method, path, fields=None, cookie=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=2)
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        if cookie:
            headers['Cookie'] = cookie
        conn.request(method, path, urlencode(fields, doseq=True) if fields is not None else None, headers)
        response = conn.getresponse()
        result = response.status, response.read().decode(), response.getheader('Set-Cookie')
        conn.close()
        return result

    def login(self):
        status, _, cookie = self.request('POST', '/login', {'token': self.server.token})
        self.assertEqual(status, 200)
        return cookie.split(';')[0]

    def fields(self):
        page = self.request('GET', '/', cookie=self.login())[1]
        csrf = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
        return {'csrf': csrf, 'module': ['web', 'iperf3', 'proxy'], 'protocol': ['vmess'],
                'policy': 'preserve', 'auth': '1', 'public': '1', 'port': '', 'language': 'en'}

    def test_auth_csrf_validation_and_atomic_replay(self):
        self.assertEqual(self.request('GET', '/?token=secret')[0], 404)
        self.assertEqual(self.request('POST', '/login', {'token': 'bad'})[0], 403)
        token = self.server.token
        cookie = self.login()
        self.assertEqual(self.request('POST', '/login', {'token': token})[0], 403)
        self.assertIn('name="csrf"', self.request('GET', '/', cookie=cookie)[1])
        fields = {'csrf': self.server.csrf, 'module': ['web', 'iperf3', 'proxy'],
                  'protocol': ['vmess'], 'policy': 'preserve', 'auth': '1', 'public': '1',
                  'port': '', 'language': 'en'}
        self.assertEqual(self.request('POST', '/apply', fields)[0], 403)
        self.assertEqual(self.request('POST', '/apply', dict(fields, csrf='bad'), cookie)[0], 403)
        self.assertEqual(self.request('POST', '/apply', dict(fields, module=['web', 'bogus']), cookie)[0], 400)
        self.assertEqual(self.request('POST', '/apply', dict(fields, module=['web']), cookie)[0], 400)
        self.assertEqual(self.request('POST', '/apply', fields, cookie)[0], 200)
        self.assertEqual(self.server.result[0], 'web,iperf3,proxy')
        self.thread.join(timeout=2)
        self.assertFalse(self.thread.is_alive())
        self.assertEqual(self.server.result[0], 'web,iperf3,proxy')

    def test_installed_protocol_removal_requires_individual_server_confirmation(self):
        self.server.previous_protocols = 'vmess,vless'
        cookie = self.login()
        page = self.request('GET', '/', cookie=cookie)[1]
        self.assertIn('name="protocol" value="vless" checked', page)
        self.assertIn('name="remove_protocol" value="vless"', page)
        fields = {'csrf': self.server.csrf, 'module': ['web', 'iperf3', 'proxy'],
                  'protocol': ['vmess'], 'policy': 'preserve'}
        self.assertEqual(self.request('POST', '/apply', fields, cookie)[0], 400)
        self.assertIsNone(self.server.result)
        # Forged confirmation for the wrong protocol cannot authorize the removal.
        self.assertEqual(self.request('POST', '/apply', dict(fields, remove_protocol=['vmess']), cookie)[0], 400)
        self.assertIsNone(self.server.result)
        self.assertEqual(self.request('POST', '/apply', dict(fields, remove_protocol=['vless']), cookie)[0], 200)
        self.assertEqual(self.server.result[:3], ('web,iperf3,proxy', 'vmess', 'preserve'))

    def test_partial_install_without_prior_proxy_config_needs_no_removal_confirmation(self):
        self.server.previous = ''
        self.server.previous_protocols = ''
        cookie = self.login()
        fields = {'csrf': self.server.csrf, 'module': list(('web', 'iperf3', 'anytls', 'proxy', 'frps', 'lucky')),
                  'protocol': ['vmess', 'vless', 'trojan', 'shadowsocks'], 'policy': 'preserve',
                  'auth': '1', 'public': '1', 'language': 'zh_cn', 'lucky_port': '16601',
                  'lucky_public': '0'}
        status, body, _ = self.request('POST', '/apply', fields, cookie)
        self.assertEqual(status, 200, body)
        self.assertEqual(self.server.result[:3],
                         ('web,iperf3,anytls,proxy,frps,lucky', 'vmess,vless,trojan,shadowsocks', 'preserve'))

    def test_expiry_exits_without_selection(self):
        self.login()
        self.server.expires = time.monotonic() - 1
        self.thread.join(timeout=2)
        self.assertFalse(self.thread.is_alive())
        self.assertIsNone(self.server.result)

    def test_live_port_collision_rejected(self):
        with self.assertRaises(OSError):
            Wizard(('127.0.0.1', self.port))

    def test_upgrade_requires_explicit_confirmation(self):
        fields = {'modules': ['web'], 'protocols': [''], 'policy': ['preserve']}
        with self.assertRaisesRegex(ValueError, 'DELETE'):
            validate(fields, 'web,iperf3,proxy', True)
        fields['confirm'] = ['DELETE']
        self.assertEqual(validate(fields, 'web,iperf3,proxy', True)[0], 'web')
        fields['policy'] = ['reconfigure']
        self.assertEqual(validate(fields, 'web,iperf3,proxy', True)[2], 'reconfigure')
        with self.assertRaises(ValueError):
            validate(dict(fields, port=['70000']), 'web,iperf3,proxy', True)
        with self.assertRaises(ValueError):
            validate(dict(fields, bogus=['x']), 'web,iperf3,proxy', True)


class FrpsInstallerTests(unittest.TestCase):
    def test_upgrade_preserves_port_and_token_and_rejects_busy_port(self):
        source = Path(__file__).resolve().parents[1] / 'deploy/frps/setup-frps.sh'
        binary = Path(__file__).resolve().parents[1] / 'third_party/frp/frps'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'deploy/frps').mkdir(parents=True)
            (root / 'third_party/frp').mkdir(parents=True)
            shutil.copy2(binary, root / 'third_party/frp/frps')
            config = root / 'config/frps.toml'
            unit = root / 'frps.service'
            installed = root / 'installed-frps'
            script = source.read_text().replace('CONFIG=/etc/vps-server-frps/frps.toml', f'CONFIG={config}')
            script = script.replace('UNIT=/etc/systemd/system/vps-server-frps.service', f'UNIT={unit}')
            script = script.replace('/usr/local/bin/frps-vps-server', str(installed))
            target = root / 'deploy/frps/setup-frps.sh'
            target.write_text(script)
            mock_id = root / 'id'
            mock_id.write_text('#!/bin/sh\necho 0\n')
            mock_id.chmod(0o755)
            mock = root / 'systemctl'
            mock.write_text('#!/bin/sh\nexit 0\n')
            mock.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + ':' + os.environ['PATH'],
                       PREFIX=str(root), FRPS_BIND_PORT='18751',
                       VPSSRV_CATALOG_ROOT=str(source.parents[2] / 'lang'))
            subprocess.run(['bash', str(target)], env=env, check=True, capture_output=True)
            first = config.read_text()
            self.assertRegex(first, r'auth.token = "[^"]{30,}"')
            env.pop('FRPS_BIND_PORT')
            subprocess.run(['bash', str(target)], env=env, check=True, capture_output=True)
            self.assertEqual(config.read_text(), first)
            with socket.socket() as held:
                held.bind(('127.0.0.1', 0))
                env['FRPS_BIND_PORT'] = str(held.getsockname()[1])
                failed = subprocess.run(['bash', str(target)], env=env, capture_output=True)
                self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(config.read_text(), first)


class FrpsWizardTests(unittest.TestCase):
    def test_frps_selected_without_client_or_web(self):
        self.assertEqual(validate({'modules': ['frps']}, '', False)[0], 'frps')
        self.assertRaisesRegex(ValueError, 'DELETE', validate,
                               {'modules': ['web']}, 'web,frps', True)


class InstallerNonTtyTests(unittest.TestCase):
    def test_missing_modules_fails_before_starting_wizard_or_install(self):
        installer = Path(__file__).resolve().parents[1] / 'deploy/install.sh'
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'called'
            # id is the only privileged preflight; if this test runs without
            # root, spoof its uid check without allowing installation actions.
            fake_id = Path(directory) / 'id'
            fake_id.write_text('#!/bin/sh\n[ "$1" = -u ] && { echo 0; exit 0; }\nexit 1\n')
            fake_id.chmod(0o755)
            fake_python = Path(directory) / 'python3'
            fake_python.write_text('#!/bin/sh\nprintf called > "$MARKER"\nexit 1\n')
            fake_python.chmod(0o755)
            env = dict(os.environ, PATH=directory + os.pathsep + os.environ['PATH'],
                       PREFIX=directory + '/install', MARKER=str(marker))
            env.pop('VPSSRV_MODULES', None)
            result = subprocess.run(['bash', str(installer)], stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, env=env, timeout=3)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Non-interactive installation requires VPSSRV_MODULES', result.stderr)
            self.assertIn('VPSSRV_MODULES=web,iperf3', result.stderr)
            self.assertFalse(marker.exists())
            self.assertFalse((Path(directory) / 'install').exists())


class PublicTlsTests(unittest.TestCase):
    def test_ephemeral_https_and_fingerprint(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        with tempfile.TemporaryDirectory() as directory:
            result = str(Path(directory) / 'selection')
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve().parents[1] / 'tools/setup_wizard/setup_wizard.py'),
                                        '--bind', '0.0.0.0', '--port', str(port), '--public', '--result', result],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                fingerprint = process.stdout.readline().strip().split(': ', 1)[1]
                self.assertIn('https://0.0.0.0:', process.stdout.readline())
                self.assertIn('Replace the wildcard', process.stdout.readline())
                token = process.stdout.readline().strip().split(': ', 1)[1]
                self.assertTrue(token)
                context = ssl._create_unverified_context()
                with socket.create_connection(('127.0.0.1', port), timeout=3) as raw:
                    with context.wrap_socket(raw, server_hostname='localhost') as secure:
                        self.assertEqual(hashlib.sha256(secure.getpeercert(binary_form=True)).hexdigest(), fingerprint)
                self.assertFalse(os.path.exists(result))
            finally:
                process.terminate()
                process.communicate(timeout=5)
            self.assertFalse(os.path.exists(result))


if __name__ == '__main__':
    unittest.main()
