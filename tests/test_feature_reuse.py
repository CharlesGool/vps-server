"""A feature can be imported and hosted without this application's entry point."""

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FeatureReuseTest(unittest.TestCase):
    def test_frp_feature_accepts_another_host_context(self):
        source = '''import ipaddress, sys
from types import SimpleNamespace
from features.frp import FrpMixin, masked_frpc_ip
assert "app" not in sys.modules

context = SimpleNamespace(AUTH_ENABLED=True, ipaddress=ipaddress)
assert masked_frpc_ip(context, "203.0.113.14") == "203.0.*.*"

class OtherProjectHandler(FrpMixin):
    context = context
    def page_frpc(self, lang, query_lang):
        self.seen = (lang, query_lang)

handler = OtherProjectHandler()
assert handler.route_frp("GET", "/frpc", None, "en", None) is True
assert handler.seen == ("en", None)
'''
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src/web")
        result = subprocess.run([sys.executable, "-c", source], cwd=ROOT,
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
