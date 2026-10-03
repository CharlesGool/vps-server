"""Offline installer/rotation lock regression, using the installer's actual read path."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / "deploy/install.sh").read_text()


def function(name):
    match = re.search(rf"^{name}\(\) \{{\n.*?^\}}", INSTALLER, re.M | re.S)
    assert match, name
    return match.group()


def wait_for(path):
    deadline = time.monotonic() + 10
    while not path.exists():
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out waiting for {path}")
        time.sleep(.01)


class NodeInstallerLockTest(unittest.TestCase):
    def test_web_only_upgrade_locks_before_loading_and_preserving_node_credentials(self):
        # Execute the installer block after module selection, including its lock
        # decision, against temporary install state and a competing rotation.
        block = INSTALLER.split('# 1a. An existing install, if there is one.\n', 1)[1]
        block = block.split('# Re-derived here, because apply_previous', 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock, state, unit, config = (root / name for name in
                                         ('node.lock', 'state', 'unit', 'proxy.json'))
            state.write_text('version=old\nmodules=web\n')
            unit.touch()
            config.write_text(json.dumps({'inbounds': [{'type': 'trojan', 'listen_port': 12345,
                                                       'users': [{'password': 'old-secret'}]}]}))
            script = root / 'upgrade.sh'
            script.write_text('set -e\n' + function('existing_install') + '\n' +
                              function('load_previous') + '\n' + function('apply_previous') + '\n' +
                              function('preserve_anytls') + '\n' + function('preserve_proxy') + '\n' +
                              'msg() { :; }\n'
                              f'PREFIX="{root}"\nUNIT_PATH="{unit}"\nSTATE_FILE="{state}"\n'
                              f'PROXY_CONFIG_PATH="{config}"\nANYTLS_CONFIG_PATH="{root / "absent"}"\n'
                              'ANYTLS_UNIT=/nonexistent/anytls\nPROXY_UNIT=/nonexistent/proxy\n'
                              'FRPS_UNIT=/nonexistent/frps\nLUCKY_UNIT=/nonexistent/lucky\n'
                              'DEFAULT_MODULES=web\nKNOWN_VARS=""\ndeclare -A PREV=()\n'
                              'PREV_MODULES=""\nPREV_VERSION=""\nPREV_STATE_KNOWN=0\n'
                              'MODULES=web\nINTERACTIVE=0\nNEW_VERSION=new\n' +
                              block.replace('/etc/vps-server-node.lock', str(lock)) +
                              f'printf "%s\\n" "$PROXY_TROJAN_PASSWORD" > "{root / "snapshot"}"\n')
            rotate = root / 'rotate.py'
            rotate.write_text('import fcntl,json,sys,time\n'
                              'with open(sys.argv[1],"a+b") as lock:\n'
                              ' fcntl.flock(lock,fcntl.LOCK_EX)\n'
                              ' open(sys.argv[3],"w").close()\n'
                              ' time.sleep(.2)\n'
                              ' p=sys.argv[2]; c=json.load(open(p))\n'
                              ' c["inbounds"][0]["users"][0]["password"]="new-secret"\n'
                              ' json.dump(c,open(p,"w"))\n')
            acquired = root / 'acquired'
            rotation = subprocess.Popen([sys.executable, str(rotate), str(lock), str(config), str(acquired)])
            try:
                wait_for(acquired)
                upgrade = subprocess.Popen(['bash', str(script)])
                try:
                    self.assertEqual(rotation.wait(timeout=10), 0)
                    self.assertEqual(upgrade.wait(timeout=10), 0)
                finally:
                    if upgrade.poll() is None:
                        upgrade.kill()
                        upgrade.wait()
            finally:
                if rotation.poll() is None:
                    rotation.kill()
                    rotation.wait()
            self.assertEqual((root / 'snapshot').read_text().strip(), 'new-secret')

    def test_preserve_and_both_child_applies_share_lock_with_rotation(self):
        anytls = (ROOT / "deploy/anytls/setup-anytls.sh").read_text()
        proxy = (ROOT / "deploy/proxy/setup-proxy.sh").read_text()
        # Extract real child entry lock blocks, not an imitation of flock.
        pattern = r'  if \[\[ -n "\$\{VPSSRV_NODE_LOCK_FD:-\}" \]\]; then\n.*?^  fi'
        child_blocks = []
        for source in (anytls, proxy):
            match = re.search(pattern, source, re.M | re.S)
            self.assertIsNotNone(match)
            child_blocks.append(match.group())
        self.assertRegex(INSTALLER, r'exec \{node_lock\}>/etc/vps-server-node\.lock\n\s*flock -x "\$node_lock"')
        self.assertIn('VPSSRV_NODE_LOCK_FD="${node_lock:-}" VPSSRV_DEFER_NODE_START=1 VPSSRV_EMPTY_NODE_INSTALL=1 bash "$PREFIX/anytls/setup-anytls.sh"', INSTALLER)
        self.assertIn('VPSSRV_NODE_LOCK_FD="${node_lock:-}" VPSSRV_DEFER_NODE_START=1 VPSSRV_EMPTY_NODE_INSTALL=1 bash "$PREFIX/proxy/setup-proxy.sh"', INSTALLER)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = root / "node.lock"
            configs = [root / "anytls.json", root / "proxy.json"]
            for module, block in enumerate(child_blocks):
                for rotation_first in (False, True):
                    with self.subTest(module=module, rotation_first=rotation_first):
                        path = configs[module]
                        kind = "anytls" if module == 0 else "trojan"
                        path.write_text(json.dumps({"inbounds": [{"type": kind, "listen_port": 12345,
                                                                    "users": [{"password": "old-secret"}]}]}))
                        marker, go = root / "snapshot", root / "go"
                        marker.unlink(missing_ok=True)
                        go.unlink(missing_ok=True)
                        preserve = function("preserve_anytls" if module == 0 else "preserve_proxy")
                        preserve = preserve.replace("/etc/vps-server-anytls/config.json" if module == 0
                                                    else "/etc/vps-server-proxy/config.json", str(path))
                        child = root / "child.sh"
                        child.write_text("set -e\n" + block.replace('/etc/vps-server-node.lock', str(lock)) +
                                         '\npython3 - "$CONFIG" "$VALUE" <<\'PY\'\n'
                                         'import json,sys\np=sys.argv[1]\nc=json.load(open(p))\n'
                                         'c["inbounds"][0]["users"][0]["password"]=sys.argv[2]\n'
                                         'json.dump(c,open(p,"w"))\nPY\n')
                        parent = root / "parent.sh"
                        parent.write_text('set -e\nmsg() { :; }\n' + preserve + '\n'
                                          + f'exec {{node_lock}}>"{lock}"\nflock -x "$node_lock"\n'
                                          + (f'ANYTLS_CONFIG_PATH="{path}"\npreserve_anytls\n'
                                             if module == 0 else f'PROXY_CONFIG_PATH="{path}"\npreserve_proxy\n')
                                          + f'touch "{marker}"\nwhile [ ! -e "{go}" ]; do sleep .01; done\n'
                                          + f'VPSSRV_NODE_LOCK_FD="$node_lock" CONFIG="{path}" '
                                          + ('VALUE="$ANYTLS_PASSWORD"' if module == 0 else 'VALUE="$PROXY_TROJAN_PASSWORD"')
                                          + f' bash "{child}"\n')
                        rotate = root / "rotate.py"
                        rotate.write_text('import fcntl,json,sys,time\n'
                                          'with open(sys.argv[1],"a+b") as lock:\n'
                                          ' fcntl.flock(lock,fcntl.LOCK_EX)\n'
                                          ' open(sys.argv[3],"w").close()\n'
                                          ' time.sleep(.15)\n'
                                          ' p=sys.argv[2]; c=json.load(open(p))\n'
                                          ' c["inbounds"][0]["users"][0]["password"]="new-secret"\n'
                                          ' json.dump(c,open(p,"w"))\n')
                        acquired = root / "acquired"
                        acquired.unlink(missing_ok=True)
                        rot_args = [sys.executable, str(rotate), str(lock), str(path), str(acquired)]
                        if rotation_first:
                            rotation = subprocess.Popen(rot_args)
                            wait_for(acquired)
                            upgrade = subprocess.Popen(["bash", str(parent)])
                            self.assertEqual(rotation.wait(timeout=10), 0)
                            wait_for(marker)
                            go.touch()
                            self.assertEqual(upgrade.wait(timeout=10), 0)
                        else:
                            upgrade = subprocess.Popen(["bash", str(parent)])
                            wait_for(marker)
                            rotation = subprocess.Popen(rot_args)
                            time.sleep(.1)
                            self.assertFalse(acquired.exists(), "rotation entered during installer snapshot")
                            go.touch()
                            self.assertEqual(upgrade.wait(timeout=10), 0)
                            self.assertEqual(rotation.wait(timeout=10), 0)
                        self.assertEqual(json.loads(path.read_text())["inbounds"][0]["users"][0]["password"],
                                         "new-secret")


if __name__ == "__main__":
    unittest.main()
