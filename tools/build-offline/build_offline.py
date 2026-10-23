#!/usr/bin/env python3
"""Create a release tarball that needs no Git or curl on the target.

The offline variant carries every binary and system-tool runtime. The online
variant leaves out the large third-party binaries listed in
config/online-assets.json; the installer downloads and verifies them.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TAILSCALE_SHA256 = "50748df1045e60b5b695f19f4c56b0da36c019948b440fb456b6584a50f0d8b9"
NFT_SHA256 = "7b3e499cd663f4ac77c14a0f6806ee44e3455d35cbca134e65b666b9c6cbe033"
NFT_SOURCES_SHA256 = "99b4ef60318a9fc5d68168fee5259ae91576779bd759c103a2f5c8ac5c0fc30a"
VARIANTS = ("offline", "online")


def _online_only_paths():
    """Binaries the online variant downloads at install time instead of shipping."""
    manifest = json.loads((ROOT / "config" / "online-assets.json").read_text(encoding="utf-8"))
    return {item["path"] for spec in manifest["components"].values() for item in spec["files"]}


def _tracked_source(destination, exclude=frozenset()):
    """Copy only committed files; ignored runtime data never enters the tarball."""
    dirty = subprocess.run(["git", "diff", "--quiet", "HEAD", "--"], cwd=ROOT, check=False)
    if dirty.returncode:
        raise RuntimeError("tracked files differ from HEAD")
    files = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    for raw in files:
        if not raw:
            continue
        relative = Path(os.fsdecode(raw))
        if relative.as_posix() in exclude:
            continue
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            link = os.readlink(source)
            if Path(link).is_absolute() or ".." in Path(link).parts:
                raise ValueError("unsafe tracked symlink")
            target.symlink_to(link)
        elif source.is_file():
            shutil.copy2(source, target)
        else:
            raise ValueError("tracked source is missing or not a file")


def build(asset, nft_asset, nft_sources, output, version, variant="offline"):
    if variant not in VARIANTS:
        raise ValueError("invalid package variant")
    if not re.fullmatch(r"(?:dev-local|test-[0-9a-f]{7,40}|[0-9]+\.[0-9]+\.[0-9]+(?:-test\.[0-9]+)?)", version):
        raise ValueError("invalid package version")
    if version.startswith("test-"):
        short = subprocess.check_output(["git", "rev-parse", "--short=7", "HEAD"],
                                        cwd=ROOT, text=True).strip()
        if version != "test-" + short:
            raise ValueError("test package version does not match HEAD")
    elif version != "dev-local":
        tag = subprocess.run(["git", "describe", "--tags", "--exact-match", "HEAD"],
                             cwd=ROOT, capture_output=True, text=True, check=False)
        if tag.returncode or tag.stdout.strip() != "v" + version:
            raise ValueError("tagged package version does not match HEAD tag")
    offline = variant == "offline"
    if offline:
        asset = Path(asset).resolve()
        if hashlib.sha256(asset.read_bytes()).hexdigest() != TAILSCALE_SHA256:
            raise ValueError("Tailscale archive checksum mismatch")
        nft_asset = Path(nft_asset).resolve()
        if hashlib.sha256(nft_asset.read_bytes()).hexdigest() != NFT_SHA256:
            raise ValueError("nftables runtime checksum mismatch")
        nft_sources = Path(nft_sources).resolve()
        if hashlib.sha256(nft_sources.read_bytes()).hexdigest() != NFT_SOURCES_SHA256:
            raise ValueError("nftables source checksum mismatch")
    with tempfile.TemporaryDirectory(prefix="vps-server-offline-") as temporary:
        staged = Path(temporary) / "vps-server"
        staged.mkdir()
        _tracked_source(staged, frozenset() if offline else _online_only_paths())
        bundle = ROOT / "web/dist"
        if not all((bundle / name).is_file() for name in ("ui.js", "ui.css")):
            raise ValueError("frontend bundle missing; run npm ci and npm run check in web/")
        shutil.copytree(bundle, staged / "web/dist")
        if offline:
            destination = staged / "third_party" / "tailscale" / "tailscale_1.102.4_amd64.tgz"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(asset, destination)
            nft_destination = staged / "third_party" / "nft" / "nft-runtime-trixie.tar.gz"
            nft_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(nft_asset, nft_destination)
            shutil.copy2(nft_sources, staged / "third_party" / "nft" / "nft-sources-trixie.tar.gz")
        (staged / "config" / "VERSION").write_text(version + "\n", encoding="utf-8")
        (staged / "config" / "PACKAGE_VARIANT").write_text(variant + "\n", encoding="utf-8")
        output = Path(output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(output, "w:gz") as tar:
            tar.add(staged, arcname="vps-server", recursive=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=VARIANTS, default="offline")
    parser.add_argument("--tailscale-archive")
    parser.add_argument("--nft-runtime")
    parser.add_argument("--nft-sources")
    parser.add_argument("--output", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    if args.variant == "offline" and not (args.tailscale_archive and args.nft_runtime and args.nft_sources):
        parser.error("the offline variant needs --tailscale-archive, --nft-runtime and --nft-sources")
    print(build(args.tailscale_archive, args.nft_runtime, args.nft_sources,
                args.output, args.version, args.variant))


if __name__ == "__main__":
    main()
