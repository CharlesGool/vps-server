#!/usr/bin/env python3
"""Close Lucky's admin port to everything but this host.

The console shows Lucky's admin page at /lucky/ by connecting to 127.0.0.1,
so nothing else needs the port. Lucky cannot bind to loopback only, so a
separate nft table drops TCP to the admin port unless it arrives on lo. The
rule follows the port Lucky actually uses, also after a change in Lucky's
own settings. Installing Lucky with a public admin page
(LUCKY_PUBLIC_ADMIN=1, AllowInternetaccess) keeps the port open.

    lucky_guard.py sync          match the table to Lucky's admin port (root)
    lucky_guard.py delete-table  remove the table (uninstall)
"""

import json
import os
import subprocess
import sys
from pathlib import Path

TABLE = "vps_server_lucky"
CONFIG = Path(os.environ.get("VPSSRV_LUCKY_CONFIG", "/etc/vps-server-lucky/config.json"))
BINARY = "/usr/local/bin/lucky-vps-server"


def _valid(port):
    return type(port) is int and 1 <= port <= 65535


def desired_port():
    """The admin port to close, or None when the operator chose a public page."""
    try:
        base = json.loads(CONFIG.read_text())["BaseConfigure"]
    except (OSError, ValueError, KeyError, TypeError):
        return None  # Lucky is not installed.
    if base.get("AllowInternetaccess") is True:
        return None
    # Lucky keeps its live settings beside config.json; ask it first.
    try:
        info = subprocess.run([BINARY, "-c", str(CONFIG), "-baseConfInfo"], capture_output=True,
                              text=True, timeout=10, check=True).stdout
        port = json.loads(info)["BaseConfigure"]["AdminWebListenPort"]
        if _valid(port):
            return port
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        pass
    port = base.get("AdminWebListenPort")
    return port if _valid(port) else None


def _nft(args, script=None):
    from nft_runtime import command
    binary, env = command()
    return subprocess.run([binary, *args], input=script, capture_output=True, text=True,
                          timeout=20, env=env, check=False)


def current_port():
    result = _nft(["-j", "list", "table", "inet", TABLE])
    if result.returncode:
        return None
    for item in json.loads(result.stdout).get("nftables", []):
        for expr in item.get("rule", {}).get("expr", []):
            match = expr.get("match", {})
            if match.get("left", {}).get("payload", {}).get("field") == "dport" and _valid(match.get("right")):
                return match["right"]
    return None


def sync():
    """Return "changed" or "unchanged"; raise when nft cannot apply the rule."""
    wanted = desired_port()
    if wanted == current_port():
        return "unchanged"
    if wanted is None:
        delete_table()
        return "changed"
    # Replace the whole table in one transaction: never a moment without the rule.
    script = (f"add table inet {TABLE}\n"
              f"delete table inet {TABLE}\n"
              f"table inet {TABLE} {{\n"
              "  chain input {\n"
              "    type filter hook input priority filter; policy accept;\n"
              f'    iifname != "lo" tcp dport {wanted} drop\n'
              "  }\n"
              "}\n")
    result = _nft(["-f", "-"], script)
    if result.returncode:
        raise RuntimeError("nft rejected the Lucky rule")
    return "changed"


def delete_table():
    return _nft(["delete", "table", "inet", TABLE]).returncode


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv not in (["sync"], ["delete-table"]):
        print("usage: lucky_guard.py sync|delete-table", file=sys.stderr)
        return 2
    if os.geteuid() != 0:
        return 1
    try:
        if argv == ["sync"]:
            print(sync())
            return 0
        return 0 if delete_table() in (0, 1) else 1
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Lucky port guard {argv[0]} failed: {type(exc).__name__}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
