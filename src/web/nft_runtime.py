"""Locate the checked, private nftables runtime bundled for offline hosts."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = Path(os.environ.get("VPSSRV_NFT_ROOT") or ROOT / "vendor" / "nft")


def command():
    binary = BUNDLE / "usr" / "sbin" / "nft"
    if binary.is_file():
        env = dict(os.environ)
        paths = (BUNDLE / "lib" / "x86_64-linux-gnu",
                 BUNDLE / "usr" / "lib" / "x86_64-linux-gnu")
        env["LD_LIBRARY_PATH"] = ":".join(str(path) for path in paths) + ":" + env.get("LD_LIBRARY_PATH", "")
        return str(binary), env
    system = shutil.which("nft")
    if system:
        return system, dict(os.environ)
    raise FileNotFoundError("nftables runtime unavailable")


def main(args):
    if args not in (["check"], ["delete-table"]):
        return 2
    binary, env = command()
    command_args = (["--version"] if args == ["check"] else
                    ["delete", "table", "inet", "vps_server_nodes"])
    return subprocess.run([binary, *command_args], env=env, timeout=20, check=False).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
