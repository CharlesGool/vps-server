"""Offline Lucky install guards, without invoking a real service or firewall."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools.setup_wizard.setup_wizard import validate

ROOT = Path(__file__).resolve().parents[1]


class LuckyInstallTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'deploy/lucky').mkdir(parents=True)
        (self.root / 'third_party/lucky').mkdir(parents=True)
        shutil.copy2(ROOT / 'third_party/lucky/lucky', self.root / 'third_party/lucky/lucky')
        self.config = self.root / 'config.json'
        self.unit = self.root / 'lucky.service'
        self.binary = self.root / 'installed-lucky'
        self.owner = self.root / 'firewall-owned'
        source = (ROOT / 'deploy/lucky/setup-lucky.sh').read_text()
        source = source.replace('[ "$(id -u)" -eq 0 ]', '[ 0 -eq 0 ]')
        source = source.replace('CONFIG=/etc/vps-server-lucky/config.json', f'CONFIG={self.config}')
        source = source.replace('UNIT=/etc/systemd/system/vps-server-lucky.service', f'UNIT={self.unit}')
        source = source.replace('TARGET=/usr/local/bin/lucky-vps-server', f'TARGET={self.binary}')
        source = source.replace('OWNER=/etc/vps-server-lucky/firewall-owned', f'OWNER={self.owner}')
        source = source.replace('/usr/local/bin/lucky-vps-server', str(self.binary)).replace('/etc/vps-server-lucky/config.json', str(self.config))
        self.script = self.root / 'deploy/lucky/setup-lucky.sh'
        self.script.write_text(source)
        (self.root / 'lucky').mkdir()
        (self.root / 'lucky/setup-lucky.sh').write_text(source)
        (self.root / 'vendor/lucky').mkdir(parents=True)
        shutil.copy2(self.root / 'third_party/lucky/lucky', self.root / 'vendor/lucky/lucky')
        for command in ('ufw', 'firewall-cmd'):
            stub = self.root / command
            stub.write_text('#!/bin/sh\nexit 1\n')
            stub.chmod(0o755)
        mock = self.root / 'systemctl'
        check = ('import json,os,sys; p=sys.argv[1]; d=json.load(open(p))["BaseConfigure"]; '
                 'assert d["AdminAccount"] and d["AdminPassword"] and '
                 '(d["AdminAccount"],d["AdminPassword"]) != ("666","666") and '
                 'os.stat(p).st_mode & 0o777 == 0o600')
        mock.write_text(f'''#!/bin/sh
printf '%s\\n' "$*" >> "{self.root / 'calls'}"
case "$1" in
  restart) python3 -c '{check}' "{self.config}" || exit 1
           touch "{self.root / 'started'}" ;;
  is-active) [ -f "{self.root / 'started'}" ]; exit $? ;;
  is-enabled) exit 1 ;;
esac
exit 0
''')
        mock.chmod(0o755)
        self.env = dict(os.environ, PATH=f'{self.root}:{os.environ["PATH"]}', PREFIX=str(self.root),
                        VPSSRV_CATALOG_ROOT=str(ROOT / 'lang'))

    def run_install(self, script=None, **env):
        return subprocess.run(['bash', str(script or self.script)],
                              capture_output=True, text=True, env=dict(self.env, **env))

    def test_checkout_and_installed_layout_preserve_credentials(self):
        for script in (self.script, self.root / 'lucky/setup-lucky.sh'):
            with self.subTest(script=script):
                result = self.run_install(script)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.binary.read_bytes(), (self.root / 'third_party/lucky/lucky').read_bytes())
                credentials = json.loads(self.config.read_text())['BaseConfigure']
                if script != self.script:
                    self.assertEqual((credentials['AdminAccount'], credentials['AdminPassword']), original)
                else:
                    original = (credentials['AdminAccount'], credentials['AdminPassword'])

    def test_installed_prefix_named_deploy_finds_sibling_vendor(self):
        prefix = self.root / 'alternative/deploy'
        (prefix / 'lucky').mkdir(parents=True)
        (prefix / 'vendor/lucky').mkdir(parents=True)
        script = prefix / 'lucky/setup-lucky.sh'
        shutil.copy2(self.root / 'deploy/lucky/setup-lucky.sh', script)
        shutil.copy2(self.root / 'third_party/lucky/lucky', prefix / 'vendor/lucky/lucky')
        for prefix_arg in (str(prefix), str(prefix) + '/', str(prefix / '..' / 'deploy')):
            with self.subTest(prefix_arg=prefix_arg):
                result = self.run_install(script, PREFIX=prefix_arg)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.binary.read_bytes(), (prefix / 'vendor/lucky/lucky').read_bytes())

    def test_installed_layout_missing_or_mismatched_vendor_fails_before_effects(self):
        script = self.root / 'lucky/setup-lucky.sh'
        vendor = self.root / 'vendor/lucky/lucky'
        vendor.rename(self.root / 'lucky-binary.backup')
        for bad_binary in (False, True):
            with self.subTest(bad_binary=bad_binary):
                if bad_binary:
                    vendor.write_bytes(b'wrong binary')
                result = self.run_install(script)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('integrity failure', result.stderr)
                self.assertFalse(self.config.exists())
                self.assertFalse(self.binary.exists())
                self.assertFalse((self.root / 'calls').exists())

    def test_default_credentials_never_started(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(self.config.read_text())['BaseConfigure']
        self.assertNotEqual((data['AdminAccount'], data['AdminPassword']), ('666', '666'))
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(data['AdminWebListenPort'], 16601)
        self.assertFalse(data['AllowInternetaccess'])

    def test_upgrade_preserves_unrelated_configuration(self):
        original = {'BaseConfigure': {'AdminWebListenPort': 16601, 'AdminAccount': 'custom',
                                     'AdminPassword': 'secure', 'Other': {'keep': True}},
                    'DDNSTaskList': [{'secret': 'dns'}],
                    'ReverseProxyRuleList': [{'ListenPort': 9080, 'Enable': True}], 'Unknown': [1, 2]}
        self.config.write_text(json.dumps(original))
        result = self.run_install(LUCKY_ADMIN_PORT='16602')
        self.assertEqual(result.returncode, 0, result.stderr)
        updated = json.loads(self.config.read_text())
        for key in ('DDNSTaskList', 'ReverseProxyRuleList', 'Unknown'):
            self.assertEqual(updated[key], original[key])
        self.assertEqual(updated['BaseConfigure']['AdminPassword'], 'secure')
        self.assertEqual(updated['BaseConfigure']['Other'], {'keep': True})
        self.config.write_text('{broken')
        self.assertNotEqual(self.run_install().returncode, 0)
        self.assertEqual(self.config.read_text(), '{broken')

    def test_public_requires_server_confirmation(self):
        result = self.run_install(LUCKY_PUBLIC_ADMIN='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unencrypted', result.stderr)
        self.assertFalse(self.config.exists())
        result = self.run_install(LUCKY_PUBLIC_ADMIN='1', LUCKY_PUBLIC_CONFIRM='I ACCEPT PUBLIC HTTP')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(self.config.read_text())['BaseConfigure']['AllowInternetaccess'])

    def test_reserved_port_rejected_before_write(self):
        self.assertNotEqual(self.run_install(LUCKY_ADMIN_PORT='80').returncode, 0)
        self.assertNotEqual(self.run_install(LUCKY_ADMIN_PORT='7000', VPSSRV_CONSOLE_PORT='7000').returncode, 0)
        self.assertFalse(self.config.exists())

    def test_lucky_reverse_proxy_listener_conflict(self):
        self.config.write_text(json.dumps({'BaseConfigure': {'AdminWebListenPort': 16601,
            'AdminAccount': 'custom', 'AdminPassword': 'secure'},
            'ReverseProxyRuleList': [{'ListenPort': 16602, 'Enable': True}]}))
        result = self.run_install(LUCKY_ADMIN_PORT='16602')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('reverse proxy listener', result.stderr)
        self.assertFalse(self.binary.exists())

    def test_firewalld_reload_failure_restores_both_layers_and_owner(self):
        self.config.write_text(json.dumps({'BaseConfigure': {'AdminWebListenPort': 16601,
            'AdminAccount': 'custom', 'AdminPassword': 'secure', 'AllowInternetaccess': True}}))
        self.owner.write_text('firewalld 16601\n')
        permanent = self.root / 'permanent'
        runtime = self.root / 'runtime'
        permanent.write_text('16601\n')
        runtime.write_text('16601\n')
        firewall = self.root / 'firewall-cmd'
        firewall.write_text('''#!/bin/bash
file="$RUNTIME"
if [ "$1" = --permanent ]; then file="$PERMANENT"; shift; fi
port="${1#*=}"
port="${port%/tcp}"
case "$1" in
  --state) exit 0 ;;
  --query-port=*) grep -qx "$port" "$file" ;;
  --add-port=*) { grep -vx "$port" "$file" || :; echo "$port"; } > "$file.tmp"; mv "$file.tmp" "$file" ;;
  --remove-port=*) { grep -vx "$port" "$file" || :; } > "$file.tmp"; mv "$file.tmp" "$file" ;;
  --reload) if [ -f "$FAIL_RELOAD" ]; then rm "$FAIL_RELOAD"; exit 1; fi
            cp "$PERMANENT" "$RUNTIME" ;;
esac
''')
        firewall.chmod(0o755)
        (self.root / 'fail-reload').touch()
        result = self.run_install(LUCKY_ADMIN_PORT='16602', LUCKY_PUBLIC_ADMIN='1',
            LUCKY_PUBLIC_CONFIRM='I ACCEPT PUBLIC HTTP', PERMANENT=str(permanent),
            RUNTIME=str(runtime), FAIL_RELOAD=str(self.root / 'fail-reload'))
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertEqual(permanent.read_text(), '16601\n')
        self.assertEqual(runtime.read_text(), '16601\n')
        self.assertEqual(self.owner.read_text(), 'firewalld 16601\n')
        self.assertEqual(json.loads(self.config.read_text())['BaseConfigure']['AdminWebListenPort'], 16601)

    def test_wizard_selection(self):
        self.assertEqual(validate({'modules': ['lucky']}, '', False)[-2:], ('16601', '0'))
        with self.assertRaisesRegex(ValueError, 'requires Lucky'):
            validate({'modules': ['web'], 'lucky_public': ['1']}, '', False)
        self.assertEqual(validate({'modules': ['lucky'], 'lucky_public': ['1']}, '', False)[-1], '1')


if __name__ == '__main__':
    unittest.main()
