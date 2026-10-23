#!/usr/bin/env python3
"""Host prerequisites for each module, shared by the installer and the console.

Each finding is a (level, code) pair. "error" stops the module's install
before anything is changed; "warning" only explains a feature that will not
work. Both callers turn the code into their own localized message.
"""

import argparse
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

try:
    from .nft_runtime import bundle_command, lists_tables
except ImportError:  # Installed helpers are copied into one flat directory.
    from nft_runtime import bundle_command, lists_tables


NFT_ASSET = Path("third_party") / "nft" / "nft-runtime-trixie.tar.gz"
TAILSCALE_UNIT = Path("/etc/systemd/system/vps-server-tailscale.service")


def _nft(source, prefix):
    system = shutil.which("nft")
    if system and lists_tables(system):
        return []
    if prefix:
        installed = bundle_command(Path(prefix) / "vendor" / "nft")
        if installed and lists_tables(*installed):
            return []
    asset = Path(source) / NFT_ASSET if source else None
    if asset and asset.is_file():
        with tempfile.TemporaryDirectory() as probe:
            try:  # tarfile reads gzip itself, so no tar or gzip binary is needed.
                with tarfile.open(asset, "r:gz") as archive:
                    archive.extractall(probe)
                bundled = bundle_command(probe)
            except (OSError, tarfile.TarError):
                bundled = None
            if bundled and lists_tables(*bundled):
                return []
    elif not system and not (prefix and bundle_command(Path(prefix) / "vendor" / "nft")):
        return [("error", "nft_missing")]
    return [("error", "nft_unusable")]


def _tailscale():
    findings = []
    try:
        if not stat.S_ISCHR(Path("/dev/net/tun").stat().st_mode):
            raise OSError
    except OSError:
        findings.append(("error", "tun_missing"))
    if not TAILSCALE_UNIT.exists() and subprocess.run(
            ["systemctl", "is-active", "--quiet", "tailscaled.service"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0:
        findings.append(("error", "tailscale_conflict"))
    return findings


def _web(source, prefix):
    # The offline package bundles iptables-nft, ip and ss; a missing host copy
    # only matters when no bundle ships.
    bundled = (prefix and (Path(prefix) / "vendor" / "nft" / "bin" / "iptables").is_file()
               or source and (Path(source) / NFT_ASSET).is_file())
    return [("warning", f"{tool}_missing") for tool in ("iptables", "ss", "ip")
            if not shutil.which(tool) and not bundled]


def check(module, *, source=None, prefix=None):
    """Return the findings for one module; console names are accepted too."""
    if module == "web":
        return _web(source, prefix)
    if module in ("proxy", "proxy_nodes"):
        return _nft(source, prefix)
    if module == "tailscale":
        return _tailscale()
    return []


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--source")
    parser.add_argument("--prefix")
    parser.add_argument("modules", nargs="+")
    args = parser.parse_args(argv)
    failed = False
    for module in args.modules:
        for level, code in check(module, source=args.source, prefix=args.prefix):
            print(level, code)
            failed = failed or level == "error"
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
