"""Outbound iperf3 tests use bounded arguments and parse real result fields."""

import json
import subprocess
import unittest
from types import SimpleNamespace

from src.web.features.iperf_client import IperfClient


class IperfClientTest(unittest.TestCase):
    def test_result_is_one_time_and_session_scoped(self):
        client = IperfClient()
        client.remember_result('first', {'status': 'done'}, {'host': '203.0.113.5'})
        self.assertEqual(client.take_result('second'), (None, None))
        self.assertEqual(client.take_result('first'),
                         ({'status': 'done'}, {'host': '203.0.113.5'}))
        self.assertEqual(client.take_result('first'), (None, None))

    def test_udp_reverse_uses_validated_arguments_and_reports_loss(self):
        calls = []

        def run(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(returncode=0, stderr='', stdout=json.dumps({
                'end': {'sum': {'bits_per_second': 12_345_678,
                                'jitter_ms': 1.25, 'lost_percent': 0.5}}}))

        client = IperfClient(runner=run, find_binary=lambda name: '/usr/bin/iperf3')
        result = client.run('2001:db8::1', '5201', 'udp', 'download', '10', '20')
        self.assertEqual(result, {'status': 'done', 'mbps': 12.35,
                                  'jitter_ms': 1.25, 'loss_percent': 0.5})
        self.assertEqual(calls[0][0], ['/usr/bin/iperf3', '--client', '2001:db8::1',
                                       '--port', '5201', '--time', '10', '--bandwidth',
                                       '20M', '--json', '--udp', '--reverse'])
        self.assertLessEqual(calls[0][1]['timeout'], 20)

    def test_invalid_target_and_limits_never_launch_process(self):
        client = IperfClient(runner=lambda *args, **kwargs: self.fail('process launched'),
                             find_binary=lambda name: '/usr/bin/iperf3')
        for host, seconds, mbps in (('127.0.0.1; rm -rf /', '10', '100'),
                                    ('0.0.0.0', '10', '100'),
                                    ('203.0.113.5', '31', '100'),
                                    ('203.0.113.5', '10', '1001')):
            with self.subTest(host=host, seconds=seconds, mbps=mbps):
                self.assertEqual(client.run(host, '5201', 'tcp', 'upload', seconds, mbps),
                                 {'status': 'invalid'})

    def test_timeout_and_missing_binary_have_distinct_statuses(self):
        missing = IperfClient(find_binary=lambda name: None)
        self.assertEqual(missing.run('203.0.113.5', 5201, 'tcp', 'upload', 10, 100),
                         {'status': 'missing'})

        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], kwargs['timeout'])

        client = IperfClient(runner=timeout, find_binary=lambda name: '/usr/bin/iperf3')
        self.assertEqual(client.run('203.0.113.5', 5201, 'tcp', 'upload', 10, 100),
                         {'status': 'timeout'})


if __name__ == '__main__':
    unittest.main()
