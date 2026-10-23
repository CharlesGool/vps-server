"""Locate nft and iptables: a working host command first, else the bundle.

The offline package carries Debian 13 nft, iptables-nft, ip and ss with their
own loader and glibc, so `bin/nft`, `bin/iptables`, `bin/ip` and `bin/ss` run
on older and newer hosts alike and on hosts where none of them is installed.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = Path(os.environ.get("VPSSRV_NFT_ROOT") or ROOT / "vendor" / "nft")
_SELECTED = None
_IPTABLES = None


def _works(args, env=None):
    try:
        return subprocess.run(args, capture_output=True, timeout=10, check=False,
                              env=env).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def lists_tables(binary, env=None):
    """`--version` succeeds even when nft cannot read the host ruleset, e.g.
    an old nft on a host with newer iptables-nft rules."""
    return _works([binary, "-j", "list", "tables"], env)


def bundle_command(root, program="nft"):
    wrapper = Path(root) / "bin" / program
    if not wrapper.is_file():
        return None
    return str(wrapper), dict(os.environ)


def command():
    global _SELECTED
    if _SELECTED is not None:
        return _SELECTED
    system = shutil.which("nft")
    if system and lists_tables(system):
        _SELECTED = (system, dict(os.environ))
        return _SELECTED
    bundled = bundle_command(BUNDLE)
    if bundled:
        _SELECTED = bundled
        return _SELECTED
    raise FileNotFoundError("nftables runtime unavailable")


def tool(name):
    """Command to run for a helper such as ip or ss: the host's when present,
    else the bundled copy, else the bare name so callers see the usual error."""
    system = shutil.which(name)
    if system:
        return system
    bundled = bundle_command(BUNDLE, name)
    return bundled[0] if bundled else name


def iptables_command():
    """Return the iptables to run, or None when no copy can read the rules.

    Only a working result is kept, so a host that gains iptables later is
    picked up without restarting the console.
    """
    global _IPTABLES
    if _IPTABLES is not None:
        return _IPTABLES
    candidates = [shutil.which("iptables")]
    bundled = bundle_command(BUNDLE, "iptables")
    candidates.append(bundled[0] if bundled else None)
    for candidate in candidates:
        if candidate and _works([candidate, "-w", "5", "-S", "INPUT"]):
            _IPTABLES = candidate
            return candidate
    return None


def main(args):
    if args == ["iptables-path"]:
        path = iptables_command()
        if path:
            print(path)
        return 0 if path else 1
    if args not in (["check"], ["delete-table"]):
        return 2
    binary, env = command()
    if args == ["check"]:
        return 0 if lists_tables(binary, env) else 1
    return subprocess.run([binary, "delete", "table", "inet", "vps_server_nodes"],
                          env=env, timeout=20, check=False).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
