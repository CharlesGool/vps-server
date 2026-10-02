"""FRPS installation regression checks; all service/filesystem effects are stubbed."""
import fcntl
import os
import pty
from pathlib import Path
import shutil
import subprocess
import tempfile
import termios
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FrpsSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'deploy/frps').mkdir(parents=True)
        (self.root / 'third_party/frp').mkdir(parents=True)
        shutil.copy2(ROOT / 'third_party/frp/frps', self.root / 'third_party/frp/frps')
        self.config = self.root / 'frps.toml'
        self.unit = self.root / 'frps.service'
        self.binary = self.root / 'installed-frps'
        source = (ROOT / 'deploy/frps/setup-frps.sh').read_text()
        for original, replacement in (('CONFIG=/etc/vps-server-frps/frps.toml', f'CONFIG={self.config}'),
                                      ('UNIT=/etc/systemd/system/vps-server-frps.service', f'UNIT={self.unit}'),
                                      ('/usr/local/bin/frps-vps-server', str(self.binary))):
            source = source.replace(original, replacement)
        self.script = self.root / 'deploy/frps/setup-frps.sh'
        self.script.write_text(source)
        (self.root / 'frps').mkdir()
        (self.root / 'frps/setup-frps.sh').write_text(source)
        (self.root / 'vendor/frp').mkdir(parents=True)
        shutil.copy2(self.root / 'third_party/frp/frps', self.root / 'vendor/frp/frps')
        self.stub('ufw', '#!/bin/sh\nexit 1\n')
        self.stub('firewall-cmd', '#!/bin/sh\nexit 1\n')
        self.stub('id', '#!/bin/sh\necho 0\n')
        self.stub('systemctl', '#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\n'
                               'if [ "$1" = restart ] && [ -f "$FAIL_RESTART" ]; then rm "$FAIL_RESTART"; exit 1; fi\n'
                               'exit 0\n')
        self.env = dict(os.environ, PATH=str(self.root) + ':' + os.environ['PATH'],
                        PREFIX=str(self.root), VPSSRV_CATALOG_ROOT=str(ROOT / 'lang'),
                        CALLS=str(self.root / 'calls'),
                        FAIL_RESTART=str(self.root / 'fail-restart'))

    def stub(self, name, content):
        path = self.root / name
        path.write_text(content)
        path.chmod(0o755)

    def run_script(self, script=None, **env):
        return subprocess.run(['bash', str(script or self.script)], env=dict(self.env, **env),
                              capture_output=True, text=True)

    def test_checkout_and_installed_layout_preserve_token(self):
        for script in (self.script, self.root / 'frps/setup-frps.sh'):
            with self.subTest(script=script):
                result = self.run_script(script)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.binary.read_bytes(), (self.root / 'third_party/frp/frps').read_bytes())
                token_line = next(line for line in self.config.read_text().splitlines()
                                  if line.startswith('auth.token = '))
                if script != self.script:
                    self.assertEqual(token_line, original)
                else:
                    original = token_line

    def test_installed_prefix_named_deploy_finds_sibling_vendor(self):
        prefix = self.root / 'alternative/deploy'
        (prefix / 'frps').mkdir(parents=True)
        (prefix / 'vendor/frp').mkdir(parents=True)
        script = prefix / 'frps/setup-frps.sh'
        shutil.copy2(self.script, script)
        shutil.copy2(self.root / 'third_party/frp/frps', prefix / 'vendor/frp/frps')
        for prefix_arg in (str(prefix), str(prefix) + '/', str(prefix / '..' / 'deploy')):
            with self.subTest(prefix_arg=prefix_arg):
                result = self.run_script(script, PREFIX=prefix_arg)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.binary.read_bytes(), (prefix / 'vendor/frp/frps').read_bytes())

    def test_installed_layout_missing_or_mismatched_vendor_fails_before_effects(self):
        script = self.root / 'frps/setup-frps.sh'
        vendor = self.root / 'vendor/frp/frps'
        vendor.rename(self.root / 'frps-binary.backup')
        for bad_binary in (False, True):
            with self.subTest(bad_binary=bad_binary):
                if bad_binary:
                    vendor.write_bytes(b'wrong binary')
                result = self.run_script(script)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('integrity failure', result.stderr)
                self.assertFalse(self.config.exists())
                self.assertFalse(self.binary.exists())
                self.assertFalse((self.root / 'calls').exists())

    def installer_source(self):
        return (ROOT / 'deploy/install.sh').read_text().replace(
            '/etc/vps-server-anytls/config.json', str(self.root / 'anytls.json')).replace(
            '/etc/vps-server-proxy/config.json', str(self.root / 'proxy.json'))

    def test_failed_restart_restores_config_binary_unit_and_prior_service(self):
        self.config.write_text('bindPort = 18751\nauth.token = "old-token"\n')
        self.binary.write_text('old binary')
        self.unit.write_text('old unit')
        (self.root / 'fail-restart').touch()
        result = self.run_script(FRPS_BIND_PORT='18752', FRPS_TOKEN='new-token')
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.read_text(), 'bindPort = 18751\nauth.token = "old-token"\n')
        self.assertEqual(self.binary.read_text(), 'old binary')
        self.assertEqual(self.unit.read_text(), 'old unit')
        self.assertEqual((self.root / 'calls').read_text().count('restart vps-server-frps.service'), 2)

    def test_failed_prior_service_restoration_reports_degraded(self):
        self.config.write_text('bindPort = 18751\nauth.token = "old-token"\n')
        self.stub('systemctl', '#!/bin/sh\n[ "$1" != restart ]\n')
        result = self.run_script(FRPS_BIND_PORT='18752')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DEGRADED: frps rollback or prior service restoration failed', result.stderr)
        self.assertEqual(self.config.read_text(), 'bindPort = 18751\nauth.token = "old-token"\n')

    def test_escaped_token_preserved_and_bad_config_rejected_without_mutation(self):
        self.config.write_text('bindPort = 18751\nauth.token = "a\\\\b\\\"c"\n')
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('auth.token = "a\\\\b\\\"c"', self.config.read_text())
        self.config.write_text('bindPort = 18751\nauth.token = "unterminated\n')
        result = self.run_script(FRPS_TOKEN='replacement')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unterminated', self.config.read_text())

    def test_web_console_conflict_fails_before_web_service_change(self):
        install_root = self.root / 'checkout'
        (install_root / 'deploy').mkdir(parents=True)
        shutil.copytree(ROOT / 'lang/installer', install_root / 'lang/installer')
        script = self.installer_source().replace(
            '/etc/vps-server-frps/frps.toml', str(self.config))
        (install_root / 'deploy/install.sh').write_text(script)
        self.config.write_text('bindPort = 18751\nauth.token = "old-token"\n')
        result = subprocess.run(['bash', str(install_root / 'deploy/install.sh')],
                                env=dict(self.env, VPSSRV_MODULES='web', VPSSRV_CONSOLE_PORT='18751',
                                         VPSSRV_PUBLIC_ENABLE='0', VPSSRV_AUTH='0',
                                         PREFIX=str(self.root / 'new-install')),
                                stdin=subprocess.DEVNULL, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('conflicts with existing frps', result.stderr)
        self.assertFalse((self.root / 'new-install').exists())
        self.assertFalse((self.root / 'calls').exists())

    def test_explicit_console_port_conflict_fails_before_install_changes(self):
        install_root = self.root / 'checkout'
        (install_root / 'deploy').mkdir(parents=True)
        shutil.copytree(ROOT / 'lang/installer', install_root / 'lang/installer')
        script = self.installer_source().replace(
            '/etc/vps-server-frps/frps.toml', str(self.config)).replace(
                'if existing_install; then', 'if false; then')
        (install_root / 'deploy/install.sh').write_text(script)
        self.config.write_text('bindPort = 18751\nauth.token = "old-token"\n')
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        def controlling_tty():
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
        try:
            process = subprocess.Popen(['bash', str(install_root / 'deploy/install.sh')],
                                       env=dict({k: v for k, v in self.env.items()
                                                 if k not in ('VPSSRV_CONSOLE_PORT', 'VPSSRV_CONSOLE_PORT_FILE')},
                                                VPSSRV_MODULES='web', VPSSRV_PUBLIC_ENABLE='0',
                                                VPSSRV_CONSOLE_PORT='18751', VPSSRV_AUTH='0', VPSSRV_DEFAULT_LANG='en',
                                                PREFIX=str(self.root / 'new-install')),
                                       stdin=slave, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, preexec_fn=controlling_tty)
        finally:
            os.close(slave)
        os.write(master, b'18751\n')
        stdout, stderr = process.communicate(timeout=15)
        self.assertNotEqual(process.returncode, 0, stdout.decode())
        self.assertIn('conflicts with existing frps', stderr.decode(), stdout.decode())
        self.assertFalse((self.root / 'new-install').exists())
        self.assertFalse((self.root / 'calls').exists())

    def test_explicit_frps_collision_with_active_public_web_does_not_stop_service(self):
        install_root = self.root / 'checkout'
        (install_root / 'deploy').mkdir(parents=True)
        shutil.copytree(ROOT / 'lang/installer', install_root / 'lang/installer')
        script = self.installer_source().replace(
            '/etc/vps-server-frps/frps.toml', str(self.config)).replace(
                'if existing_install; then', 'if false; then')
        (install_root / 'deploy/install.sh').write_text(script)
        self.config.write_text('bindPort = 18751\nauth.token = "old-token"\n')
        # The previous web service is active and occupies a public port.
        self.stub('ss', '#!/bin/sh\nprintf "State Recv-Q Send-Q Local Address:Port Peer Address:Port\\n"\n'
                        'printf "LISTEN 0 128 0.0.0.0:80 0.0.0.0:*\\n"\n')
        self.stub('systemctl', '#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\n'
                               '[ "$1" = is-active ] || [ "$1" = stop ]\n')
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        def controlling_tty():
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
        try:
            process = subprocess.Popen(['bash', str(install_root / 'deploy/install.sh')],
                                       env=dict({k: v for k, v in self.env.items()
                                                 if k not in ('VPSSRV_CONSOLE_PORT', 'VPSSRV_CONSOLE_PORT_FILE')},
                                                VPSSRV_MODULES='web', VPSSRV_PUBLIC_ENABLE='1',
                                                VPSSRV_CONSOLE_PORT='18751', VPSSRV_AUTH='0', VPSSRV_DEFAULT_LANG='en',
                                                PREFIX=str(self.root / 'new-install')),
                                       stdin=slave, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, preexec_fn=controlling_tty)
        finally:
            os.close(slave)
        os.write(master, b'18751\n')
        stdout, stderr = process.communicate(timeout=15)
        self.assertNotEqual(process.returncode, 0, stdout.decode())
        self.assertIn('conflicts with existing frps', stderr.decode(), stdout.decode())
        self.assertFalse((self.root / 'new-install').exists())
        self.assertFalse((self.root / 'calls').exists(), 'must not stop or probe active web service')

    def test_explicit_lucky_collision_with_active_public_web_does_not_stop_service(self):
        install_root = self.root / 'checkout'
        (install_root / 'deploy').mkdir(parents=True)
        shutil.copytree(ROOT / 'lang/installer', install_root / 'lang/installer')
        lucky = self.root / 'lucky.json'
        lucky.write_text('{"BaseConfigure":{"AdminWebListenPort":18751}}')
        script = self.installer_source().replace(
            '/etc/vps-server-lucky/config.json', str(lucky)).replace(
                'if existing_install; then', 'if false; then')
        (install_root / 'deploy/install.sh').write_text(script)
        self.stub('ss', '#!/bin/sh\nprintf "LISTEN 0 128 0.0.0.0:80 0.0.0.0:*\\n"\n')
        self.stub('systemctl', '#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\n'
                               '[ "$1" = is-active ] || [ "$1" = stop ]\n')
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        def controlling_tty():
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
        try:
            process = subprocess.Popen(['bash', str(install_root / 'deploy/install.sh')],
                env=dict({k: v for k, v in self.env.items()
                          if k not in ('VPSSRV_CONSOLE_PORT', 'VPSSRV_CONSOLE_PORT_FILE')},
                         VPSSRV_MODULES='web', VPSSRV_PUBLIC_ENABLE='1',
                         VPSSRV_CONSOLE_PORT='18751', VPSSRV_AUTH='0', VPSSRV_DEFAULT_LANG='en',
                         PREFIX=str(self.root / 'new-install')),
                stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                preexec_fn=controlling_tty)
        finally:
            os.close(slave)
        os.write(master, b'18751\n')
        stdout, stderr = process.communicate(timeout=15)
        self.assertNotEqual(process.returncode, 0, stdout.decode())
        self.assertIn('conflicts with existing Lucky', stderr.decode())
        self.assertFalse((self.root / 'new-install').exists())
        self.assertFalse((self.root / 'calls').exists())

    def test_owner_write_failure_restores_only_owned_firewall_rules_and_service(self):
        self.config.write_text('bindPort = 18751\nauth.token = "old-token"\n')
        self.unit.write_text('old unit')
        owner = self.root / 'firewall-owned'
        owner.write_text('ufw 18751\n')
        rules = self.root / 'rules'
        rules.write_text('18751\n18753\n')
        self.env['FW_CALLS'] = str(self.root / 'fw-calls')
        self.env['RULES'] = str(rules)
        self.stub('ufw', '#!/bin/sh\nprintf "%s\\n" "$*" >> "$FW_CALLS"\n'
                         'case "$1" in\n'
                         'status) printf "Status: active\\n"; while read -r p; do printf "%s/tcp ALLOW Anywhere\\n" "$p"; done < "$RULES" ;;\n'
                         'allow) p=${2%/tcp}; printf "%s\\n" "$p" >> "$RULES" ;;\n'
                         '--force) p=${4%/tcp}; grep -vx "$p" "$RULES" > "$RULES.tmp"; mv "$RULES.tmp" "$RULES" ;;\n'
                         'esac\n')
        self.stub('mv', '#!/bin/sh\ncase "$3" in */firewall-owned) exit 1 ;; esac\nexec /bin/mv "$@"\n')
        result = self.run_script(FRPS_BIND_PORT='18752')
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertIn('ownership update failed', result.stderr)
        self.assertEqual(owner.read_text(), 'ufw 18751\n')
        self.assertEqual(set(rules.read_text().splitlines()), {'18751', '18753'})
        self.assertIn('allow 18751/tcp', (self.root / 'fw-calls').read_text())
        self.assertIn('delete allow 18752/tcp', (self.root / 'fw-calls').read_text())
        self.assertNotIn('delete allow 18753/tcp', (self.root / 'fw-calls').read_text())
        self.assertEqual(self.config.read_text(), 'bindPort = 18751\nauth.token = "old-token"\n')
        self.assertEqual(self.unit.read_text(), 'old unit')

    def test_owner_write_failure_reports_degraded_if_firewall_restore_fails(self):
        self.config.write_text('bindPort = 18751\nauth.token = "old-token"\n')
        (self.root / 'firewall-owned').write_text('ufw 18751\n')
        rules = self.root / 'rules'
        rules.write_text('18751\n')
        self.env['RULES'] = str(rules)
        self.stub('ufw', '#!/bin/sh\ncase "$1" in\n'
                         'status) printf "Status: active\\n"; while read -r p; do printf "%s/tcp ALLOW Anywhere\\n" "$p"; done < "$RULES" ;;\n'
                         'allow) [ "$2" != 18751/tcp ] || exit 1; printf "%s\\n" "${2%/tcp}" >> "$RULES" ;;\n'
                         '--force) grep -vx "${4%/tcp}" "$RULES" > "$RULES.tmp"; /bin/mv "$RULES.tmp" "$RULES" ;;\n'
                         'esac\n')
        self.stub('mv', '#!/bin/sh\ncase "$3" in */firewall-owned) exit 1 ;; esac\nexec /bin/mv "$@"\n')
        result = self.run_script(FRPS_BIND_PORT='18752')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DEGRADED: frps firewall rollback failed', result.stderr)
        self.assertEqual((self.root / 'firewall-owned').read_text(), 'ufw 18751\n')

    def test_uninstall_removes_only_recorded_firewall_rule(self):
        units = self.root / 'units'
        units.mkdir()
        frps = self.root / 'frps-state'
        frps.mkdir()
        (units / 'vps-server-frps.service').write_text('unit')
        (frps / 'frps.toml').write_text('bindPort = 18751\n')
        script = (ROOT / 'deploy/uninstall.sh').read_text().replace(
            '/etc/systemd/system/', str(units) + '/').replace(
            '/etc/vps-server-frps', str(frps)).replace(
            '/usr/local/bin/frps-vps-server', str(self.binary))
        target = self.root / 'uninstall.sh'
        target.write_text(script)
        self.stub('ufw', '#!/bin/sh\nprintf "%s\\n" "$*" >> "$FW_CALLS"\n')
        self.env['FW_CALLS'] = str(self.root / 'fw-calls')
        env = dict(self.env, PREFIX=str(self.root / 'absent'))
        first = subprocess.run(['bash', str(target)], env=env, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertFalse((self.root / 'fw-calls').exists())
        (units / 'vps-server-frps.service').write_text('unit')
        frps.mkdir()
        (frps / 'firewall-owned').write_text('ufw 18752\n')
        second = subprocess.run(['bash', str(target)], env=env, capture_output=True, text=True)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn('delete allow 18752/tcp', (self.root / 'fw-calls').read_text())

    def test_existing_firewall_rule_is_never_claimed_or_removed(self):
        self.stub('ufw', '#!/bin/sh\nprintf "%s\\n" "$*" >> "$FW_CALLS"\n'
                         'if [ "$1" = status ]; then printf "Status: active\\n18751/tcp ALLOW Anywhere\\n"; fi\n')
        self.env['FW_CALLS'] = str(self.root / 'fw-calls')
        result = self.run_script(FRPS_BIND_PORT='18751')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / 'firewall-owned').exists())
        result = self.run_script(FRPS_BIND_PORT='18752')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('delete allow 18751/tcp', (self.root / 'fw-calls').read_text())
        self.assertEqual((self.root / 'firewall-owned').read_text(), 'ufw 18752\n')
        result = self.run_script(FRPS_BIND_PORT='18753')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('delete allow 18752/tcp', (self.root / 'fw-calls').read_text())


if __name__ == '__main__':
    unittest.main()
