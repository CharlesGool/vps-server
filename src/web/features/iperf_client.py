"""Bounded iperf3 client tests against an operator-selected server.

This module has no dependency on the Web entry point. A host application can
construct IperfClient and present its result through its own interface.
"""

import ipaddress
import json
import shutil
import subprocess
import threading
import time


class IperfClient:
    def __init__(self, runner=None, find_binary=None):
        self._runner = runner or subprocess.run
        self._find_binary = find_binary or shutil.which
        self._lock = threading.Lock()
        self._results_lock = threading.Lock()
        self._results = {}

    def remember_result(self, session, result, values):
        """Keep one short-lived result for the redirect back to the form."""
        now = time.monotonic()
        with self._results_lock:
            self._results = {key: entry for key, entry in self._results.items()
                             if now - entry[0] < 120}
            if len(self._results) >= 32:
                oldest = min(self._results, key=lambda key: self._results[key][0])
                del self._results[oldest]
            self._results[session] = (now, result, values)

    def take_result(self, session):
        with self._results_lock:
            entry = self._results.pop(session, None)
        return (entry[1], entry[2]) if entry and time.monotonic() - entry[0] < 120 else (None, None)

    def run(self, host, port, protocol, direction, seconds, mbps):
        """Run one bounded test; return a display-ready status and metrics."""
        try:
            address = ipaddress.ip_address(host)
            port, seconds, mbps = int(port), int(seconds), int(mbps)
            if (address.is_unspecified or address.is_multicast or '%' in host or
                    not 1 <= port <= 65535 or not 1 <= seconds <= 30 or
                    not 1 <= mbps <= 1000 or protocol not in ('tcp', 'udp') or
                    direction not in ('upload', 'download')):
                raise ValueError('invalid test parameters')
        except (ValueError, TypeError):
            return {'status': 'invalid'}

        binary = self._find_binary('iperf3')
        if not binary:
            return {'status': 'missing'}
        if not self._lock.acquire(blocking=False):
            return {'status': 'busy'}
        try:
            command = [binary, '--client', str(address), '--port', str(port),
                       '--time', str(seconds), '--bandwidth', f'{mbps}M', '--json']
            if protocol == 'udp':
                command.append('--udp')
            if direction == 'download':
                command.append('--reverse')
            try:
                completed = self._runner(command, stdin=subprocess.DEVNULL,
                                         capture_output=True, text=True,
                                         timeout=seconds + 10, check=False)
            except subprocess.TimeoutExpired:
                return {'status': 'timeout'}
            except OSError:
                return {'status': 'failed'}

            try:
                data = json.loads(completed.stdout)
            except (ValueError, TypeError):
                data = {}
            if not isinstance(data, dict):
                data = {}
            if completed.returncode or data.get('error'):
                detail = data.get('error') or completed.stderr or ''
                detail = ''.join(char for char in str(detail) if char.isprintable())[:200]
                return {'status': 'failed', 'detail': detail}

            end = data.get('end') or {}
            if not isinstance(end, dict):
                return {'status': 'failed'}
            summary = (end.get('sum') if protocol == 'udp' else end.get('sum_received')) or {}
            if not summary:
                summary = end.get('sum_received') or end.get('sum_sent') or {}
            if not isinstance(summary, dict):
                return {'status': 'failed'}
            try:
                speed = float(summary['bits_per_second']) / 1_000_000
                if not 0 <= speed < float('inf'):
                    raise ValueError('invalid throughput')
            except (KeyError, TypeError, ValueError, OverflowError):
                return {'status': 'failed'}
            result = {'status': 'done', 'mbps': round(speed, 2)}
            if protocol == 'udp':
                for source, target in (('jitter_ms', 'jitter_ms'),
                                       ('lost_percent', 'loss_percent')):
                    if source in summary:
                        try:
                            value = float(summary[source])
                            if 0 <= value < float('inf'):
                                result[target] = round(value, 2)
                        except (TypeError, ValueError, OverflowError):
                            pass
            else:
                sent = end.get('sum_sent') or {}
                if isinstance(sent, dict) and 'retransmits' in sent:
                    try:
                        result['retransmits'] = max(0, int(sent['retransmits']))
                    except (TypeError, ValueError, OverflowError):
                        pass
            return result
        finally:
            self._lock.release()
