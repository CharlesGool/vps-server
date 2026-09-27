"""Offline fault and journal replay tests: never call systemctl or a real binary."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from src.web.node_manager import cutover, CutoverError, DegradedCutover, NEW_UNIT, OLD_UNITS


class FakeBackend:
    def __init__(self):
        self.states = {NEW_UNIT: (False, False), OLD_UNITS['anytls']: (True, True),
                       OLD_UNITS['proxy']: (True, True)}
        self.fault = None
        self.calls = []
        self.expected_ports = [4443, 5443]

    def action(self, name):
        self.calls.append(name)
        if name == self.fault:
            raise RuntimeError('injected')

    def status(self, unit):
        return self.states[unit]

    def check(self, binary, config):
        self.action('check')
        assert json.loads(config.read_bytes())['inbounds']

    def reload(self):
        self.action('reload')

    def healthy(self, unit, ports):
        self.action('healthy')
        return unit == NEW_UNIT and ports == self.expected_ports

    def start(self, unit):
        self.action('start:' + unit)
        self.states[unit] = (True, self.states[unit][1])

    def stop(self, unit):
        self.action('stop:' + unit)
        self.states[unit] = (False, self.states[unit][1])

    def enable(self, unit):
        self.action('enable:' + unit)
        self.states[unit] = (self.states[unit][0], True)

    def disable(self, unit):
        self.action('disable:' + unit)
        self.states[unit] = (self.states[unit][0], False)


class CutoverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.paths = {key: root / key for key in ('lock', 'journal', 'state', 'config', 'unit', 'anytls', 'proxy')}
        self.binary = root / 'binary'
        self.binary.write_bytes(b'fake verified binary')
        self.binary.chmod(0o700)
        self.digest = hashlib.sha256(self.binary.read_bytes()).hexdigest()
        base = {'outbounds': [{'type': 'direct', 'tag': 'direct'}]}
        for module, kind, port in [('anytls', 'anytls', 4443), ('proxy', 'trojan', 5443)]:
            self.paths[module].write_text(json.dumps({**base, 'inbounds': [{
                'type': kind, 'tag': kind, 'listen_port': port,
                'users': [{'password': 'secret'}],
                'tls': {'certificate_path': '/old/cert', 'key_path': '/old/key'}}]}))
        self.backend = FakeBackend()
        self.original = dict(self.backend.states)

    def run_cutover(self):
        return cutover(paths=self.paths, backend=self.backend, unit_bytes=b'[Service]\nExecStart=fake\n',
                       binary=self.binary, binary_sha256=self.digest, require_root=False)

    def assert_restored(self):
        self.assertEqual(self.backend.states, self.original)
        self.assertFalse(self.paths['state'].exists())
        self.assertFalse(self.paths['config'].exists())
        self.assertFalse(self.paths['unit'].exists())
        self.assertTrue(self.paths['journal'].exists())

    def test_unified_unit_preserves_legacy_nofile_limit(self):
        unit = Path(__file__).resolve().parents[1] / 'deploy/systemd/vps-server-nodes.service'
        self.assertIn('LimitNOFILE=1048576', unit.read_text().splitlines())

    def test_success_keeps_legacy_configs_and_permissions(self):
        originals = [self.paths[x].read_bytes() for x in ('anytls', 'proxy')]
        inventory = self.run_cutover()
        self.assertEqual([n['port'] for n in inventory['nodes']], [4443, 5443])
        self.assertEqual(originals, [self.paths[x].read_bytes() for x in ('anytls', 'proxy')])
        self.assertFalse(self.paths['journal'].exists())
        for key in ('state', 'config', 'unit'):
            self.assertEqual(self.paths[key].stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.backend.states[NEW_UNIT], (True, True))

    def test_stopped_disabled_listener_stays_off_with_active_enabled(self):
        for active_module, port in [('anytls', 4443), ('proxy', 5443)]:
            with self.subTest(active_module=active_module):
                self.backend.states = {NEW_UNIT: (False, False), **{
                    unit: (module == active_module, module == active_module)
                    for module, unit in OLD_UNITS.items()}}
                self.backend.expected_ports = [port]
                inventory = self.run_cutover()
                self.assertEqual([node['enabled'] for node in inventory['nodes']],
                                 [module == active_module for module in OLD_UNITS])
                self.assertEqual([inbound['listen_port'] for inbound in
                                  json.loads(self.paths['config'].read_text())['inbounds']], [port])
                self.assertEqual(self.backend.states[NEW_UNIT], (True, True))
                for module, unit in OLD_UNITS.items():
                    if module != active_module:
                        self.assertNotIn('stop:' + unit, self.backend.calls)
                for key in ('state', 'config', 'unit'):
                    self.paths[key].unlink()
                self.backend.calls.clear()

    def test_active_disabled_preserves_disabled_boot_state(self):
        for active_modules, ports in [(('anytls',), [4443]),
                                      (('proxy',), [5443]),
                                      (('anytls', 'proxy'), [4443, 5443])]:
            with self.subTest(active_modules=active_modules):
                self.backend.states = {NEW_UNIT: (False, False), **{
                    unit: (module in active_modules, False) for module, unit in OLD_UNITS.items()}}
                self.backend.expected_ports = ports
                inventory = self.run_cutover()
                self.assertEqual([node['enabled'] for node in inventory['nodes']],
                                 [module in active_modules for module in OLD_UNITS])
                self.assertEqual([inbound['listen_port'] for inbound in
                                  json.loads(self.paths['config'].read_text())['inbounds']], ports)
                self.assertEqual(self.backend.states[NEW_UNIT], (True, False))
                self.assertNotIn('enable:' + NEW_UNIT, self.backend.calls)
                for key in ('state', 'config', 'unit'):
                    self.paths[key].unlink()
                self.backend.calls.clear()

    def test_mixed_active_boot_states_fail_before_journal_or_service_change(self):
        cases = [((True, True), (False, True)),
                 ((False, True), (True, True)),
                 ((True, False), (False, True)),
                 ((False, True), (True, False)),
                 ((True, False), (True, True)),
                 ((True, True), (True, False))]
        for anytls, proxy in cases:
            with self.subTest(anytls=anytls, proxy=proxy):
                self.backend.states[OLD_UNITS['anytls']] = anytls
                self.backend.states[OLD_UNITS['proxy']] = proxy
                self.backend.calls.clear()
                with self.assertRaisesRegex(CutoverError, 'cannot be preserved'):
                    self.run_cutover()
                self.assertFalse(self.paths['journal'].exists())
                self.assertFalse(any(self.paths[key].exists() for key in ('state', 'config', 'unit')))
                self.assertEqual(self.backend.states[OLD_UNITS['anytls']], anytls)
                self.assertEqual(self.backend.states[OLD_UNITS['proxy']], proxy)
                self.assertEqual(self.backend.calls, [])

    def test_mixed_listener_failure_rolls_back_disabled_service_state(self):
        self.backend.states[OLD_UNITS['anytls']] = (False, False)
        self.backend.states[OLD_UNITS['proxy']] = (True, False)
        self.original = dict(self.backend.states)
        self.backend.expected_ports = [5443]
        self.backend.fault = 'healthy'
        with self.assertRaises(CutoverError):
            self.run_cutover()
        self.assert_restored()
        self.backend.fault = None
        self.run_cutover()
        self.assertEqual(self.backend.states[NEW_UNIT], (True, False))

    def test_check_failure_rollback_and_retry_stable_ids(self):
        self.backend.fault = 'check'
        with self.assertRaises(CutoverError):
            self.run_cutover()
        self.assert_restored()
        self.assertFalse(any(call.startswith('stop:') for call in self.backend.calls))
        namespace = json.loads(self.paths['journal'].read_text())['namespace']
        self.backend.fault = None
        inventory = self.run_cutover()
        self.assertEqual(inventory['migration_namespace'], namespace)

    def test_stop_failure_and_retry(self):
        self.backend.fault = 'stop:' + OLD_UNITS['proxy']
        with self.assertRaises(CutoverError):
            self.run_cutover()
        self.assert_restored()
        self.backend.fault = None
        self.run_cutover()
        self.assertEqual(self.backend.states[NEW_UNIT], (True, True))

    def test_start_failure_and_rollback(self):
        self.backend.fault = 'start:' + NEW_UNIT
        with self.assertRaises(CutoverError):
            self.run_cutover()
        self.assert_restored()

    def test_health_failure_restores_both_old_units(self):
        self.backend.fault = 'healthy'
        with self.assertRaises(CutoverError):
            self.run_cutover()
        self.assert_restored()

    def test_recovery_failure_retains_journal_then_retry(self):
        self.backend.fault = 'stop:' + OLD_UNITS['proxy']
        with self.assertRaises(CutoverError):
            self.run_cutover()
        record = json.loads(self.paths['journal'].read_text())
        record['phase'] = 'pending'  # simulate interruption before recovery completed
        self.paths['journal'].write_text(json.dumps(record))
        self.backend.states[NEW_UNIT] = (True, False)
        self.backend.fault = 'stop:' + NEW_UNIT
        with self.assertRaises(DegradedCutover):
            self.run_cutover()
        self.assertEqual(json.loads(self.paths['journal'].read_text())['phase'], 'pending')
        self.backend.fault = None
        self.run_cutover()
        self.assertEqual(self.backend.states[NEW_UNIT], (True, True))

    def test_changed_legacy_after_recovery_fails_closed(self):
        self.backend.fault = 'check'
        with self.assertRaises(CutoverError):
            self.run_cutover()
        self.backend.fault = None
        self.paths['proxy'].write_text(self.paths['proxy'].read_text() + ' ')
        with self.assertRaises(CutoverError):
            self.run_cutover()
        self.assert_restored()


if __name__ == '__main__':
    unittest.main()
