"""Port forwarding rules: DNAT only for this host's own addresses, and the upgrade from the older form.

A fake iptables keeps the rule set in memory; no root or iptables is needed.
"""
import json
import shutil
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))

import nft_runtime  # noqa: E402
from features import portfwd  # noqa: E402

RULE = {"id": "ab12cd34", "label": "web", "protocol": "both", "public_port": 8080,
        "target_host": "10.0.0.5", "target_port": 80, "enabled": True}


class FakeIptables:
    def __init__(self):
        self.rules = []

    def __call__(self, command):
        _binary, _t, table, verb, chain, *spec = command
        key = (table, chain, tuple(spec))
        if verb == "-A":
            self.rules.append(key)
            return True
        if verb == "-C":
            return key in self.rules
        if verb == "-D" and key in self.rules:
            self.rules.remove(key)
            return True
        return False

    def chain(self, name):
        return [spec for _table, chain, spec in self.rules if chain == name]


def make_context(iptables):
    context = types.SimpleNamespace(PORTFWD_TAG_PREFIX="vps-server-portfwd-", sys=sys,
                                    _log_text=lambda key, **values: key, _run_quiet=iptables)
    context._portfwd_comment = lambda rule_id: portfwd._portfwd_comment(context, rule_id)
    context._portfwd_specs = lambda rule, legacy=False: portfwd._portfwd_specs(context, rule, legacy)
    context.portfwd_rule_apply = lambda rule, opening: portfwd.portfwd_rule_apply(context, rule, opening)
    return context


class PortForwardRulesTest(unittest.TestCase):
    def setUp(self):
        self.iptables = FakeIptables()
        self.context = make_context(self.iptables)
        patcher = mock.patch.object(nft_runtime, "iptables_command", return_value="iptables")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_dnat_matches_only_local_destinations(self):
        prerouting = [spec for table, chain, spec, _action in portfwd._portfwd_specs(self.context, RULE)
                      if chain == "PREROUTING"]
        self.assertEqual(len(prerouting), 2)
        for spec in prerouting:
            self.assertEqual(spec[-4:], ["-m", "addrtype", "--dst-type", "LOCAL"])
        self.assertTrue(portfwd.portfwd_rule_apply(self.context, RULE, True))
        self.assertEqual(len(self.iptables.rules), 8)
        for spec in self.iptables.chain("PREROUTING"):
            self.assertIn("addrtype", spec)
        # Withdrawing uses the very same arguments, so nothing is left behind.
        self.assertTrue(portfwd.portfwd_rule_apply(self.context, RULE, False))
        self.assertEqual(self.iptables.rules, [])

    def test_withdrawing_also_removes_the_older_form(self):
        for table, chain, match, action in portfwd._portfwd_specs(self.context, RULE, legacy=True):
            self.iptables.rules.append((table, chain, tuple(match + action)))
        self.assertTrue(all("addrtype" not in spec for spec in self.iptables.chain("PREROUTING")))
        self.assertTrue(portfwd.portfwd_rule_apply(self.context, RULE, False))
        self.assertEqual(self.iptables.rules, [])

    def test_startup_replay_replaces_rules_written_by_an_older_version(self):
        for table, chain, match, action in portfwd._portfwd_specs(self.context, RULE, legacy=True):
            self.iptables.rules.append((table, chain, tuple(match + action)))
        state = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, state, True)
        (state / "portfwd.json").write_text(json.dumps([RULE]))
        self.context.threading = threading
        self.context.json = json
        self.context.BASE_DIR = state
        self.context._ensure_ip_forward = lambda: True
        self.context.reserve_owned_port = lambda *args: True
        self.context.release_owned_port = lambda *args: True

        class Manager(portfwd.PortForwardManager):
            context = self.context

        manager = Manager(state / "portfwd.json", 20)
        self.assertTrue(manager.load())
        prerouting = self.iptables.chain("PREROUTING")
        self.assertEqual(len(prerouting), 2)
        self.assertTrue(all("addrtype" in spec for spec in prerouting))
        self.assertEqual(len(self.iptables.rules), 8)
        manager.shutdown()
        self.assertEqual(self.iptables.rules, [])


if __name__ == "__main__":
    unittest.main()
