#!/usr/bin/env python3
"""Host prerequisites for each module, shared by the installer and the console.

Each finding is a (level, code) pair. "error" stops the module's install
before anything is changed; "warning" only explains a feature that will not
work. Both callers turn the code into their own localized message.
"""

import argparse
import os
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
# Name the extraction filter so Python 3.12 and 3.13 do not warn and every
# version unpacks the runtime the same way. "tar" keeps its relative symlinks;
# Pythons without extraction filters get None and behave as before.
TAR_FILTER = getattr(tarfile, "tar_filter", None)
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
                    archive.extraction_filter = TAR_FILTER
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


# Host baseline every install needs. Each floor is the oldest version that has
# what the shipped code uses; stock Debian 11 / Ubuntu 22.04 meet all of them.
BASH_MIN = (4, 1)        # `exec {fd}>` file-descriptor variables
SYSTEMD_MIN = 240        # systemd-run --pipe/--collect/--wait, StandardOutput=append:
SQLITE_MIN = (3, 24)     # UPSERT (ON CONFLICT ... DO UPDATE) in the visitor log
LIBSSL_MIN = (1, 1, 1)   # console TLS 1.3 and client-certificate verification
BASE_TOOLS = ("flock", "sha256sum", "base64", "getent", "install", "mktemp", "systemd-run")


def _first_version(text):
    import re
    match = re.search(r"(\d+(?:\.\d+)*)", text or "")
    return tuple(int(part) for part in match.group(1).split(".")) if match else None


def _output(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=10, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _core(source):
    import sqlite3
    import ssl
    findings = []
    bash = _first_version(_output(["bash", "-c", "echo $BASH_VERSION"]))
    if not bash or bash < BASH_MIN:
        findings.append(("error", "bash_old"))
    systemd = _first_version(_output(["systemctl", "--version"]).replace("systemd ", ""))
    if not systemd or systemd[0] < SYSTEMD_MIN:
        findings.append(("error", "systemd_old"))
    if sqlite3.sqlite_version_info < SQLITE_MIN:
        findings.append(("error", "sqlite_old"))
    if ssl.OPENSSL_VERSION_INFO < LIBSSL_MIN:
        findings.append(("error", "libssl_old"))
    if any(not shutil.which(tool) for tool in BASE_TOOLS):
        findings.append(("error", "base_tools_missing"))
    variant = Path(source) / "config" / "PACKAGE_VARIANT" if source else None
    if variant and variant.is_file() and variant.read_text().strip() == "online":
        # The online package downloads its binaries over HTTPS with the host CA store.
        if not ssl.create_default_context().cert_store_stats().get("x509_ca"):
            findings.append(("error", "ca_missing"))
    return findings


NFT_CODES = ("nft_missing", "nft_unusable")


def can_install_nft():
    """True when the distribution's nftables can be installed with apt."""
    return shutil.which("apt-get") is not None


def install_nft():
    """Install the distribution's nftables with apt; True when apt succeeded.

    Used by both the installer and the console module job, so the operator
    does not have to open a terminal when the host lacks a usable nft.
    """
    apt = shutil.which("apt-get")
    if not apt:
        return False
    env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
    for args in (["update", "-qq"], ["install", "-y", "-qq", "nftables"]):
        try:
            if subprocess.run([apt, *args], env=env, check=False, timeout=900).returncode != 0:
                return False
        except (OSError, subprocess.TimeoutExpired):
            return False
    return True


def check(module, *, source=None, prefix=None):
    """Return the findings for one module; console names are accepted too."""
    if module == "core":
        return _core(source)
    if module == "web":
        return _web(source, prefix)
    if module in ("proxy", "proxy_nodes", "frps"):  # frps traffic is metered with nft
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
