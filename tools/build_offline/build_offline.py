#!/usr/bin/env python3
"""Create a source-and-binaries tarball that needs no Git on the target."""

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TAILSCALE_SHA256 = "50748df1045e60b5b695f19f4c56b0da36c019948b440fb456b6584a50f0d8b9"
NFT_SHA256 = "42eeb9496a173777df2e46d67b32b631e5eb31bbc1a74d2a0fa335f32a46c9eb"


def _tracked_source(destination):
    """Copy only committed files; ignored runtime data never enters the tarball."""
    dirty = subprocess.run(["git", "diff", "--quiet", "HEAD", "--"], cwd=ROOT, check=False)
    if dirty.returncode:
        raise RuntimeError("tracked files differ from HEAD")
    files = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    for raw in files:
        if not raw:
            continue
        relative = Path(os.fsdecode(raw))
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


def build(asset, nft_asset, output, version):
    if not re.fullmatch(r"(?:dev-local|test-[0-9a-f]{7,40}|[0-9]+\.[0-9]+\.[0-9]+)", version):
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
            raise ValueError("formal package version does not match HEAD tag")
    asset = Path(asset).resolve()
    if hashlib.sha256(asset.read_bytes()).hexdigest() != TAILSCALE_SHA256:
        raise ValueError("Tailscale archive checksum mismatch")
    nft_asset = Path(nft_asset).resolve()
    if hashlib.sha256(nft_asset.read_bytes()).hexdigest() != NFT_SHA256:
        raise ValueError("nftables runtime checksum mismatch")
    with tempfile.TemporaryDirectory(prefix="vps-server-offline-") as temporary:
        staged = Path(temporary) / "vps-server"
        staged.mkdir()
        _tracked_source(staged)
        destination = staged / "third_party" / "tailscale" / "tailscale_1.102.4_amd64.tgz"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset, destination)
        nft_destination = staged / "third_party" / "nft" / "nft-runtime-bullseye.tar.gz"
        nft_destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(nft_asset, nft_destination)
        (staged / "config" / "VERSION").write_text(version + "\n")
        output = Path(output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(output, "w:gz") as tar:
            tar.add(staged, arcname="vps-server", recursive=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tailscale-archive", required=True)
    parser.add_argument("--nft-runtime", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    print(build(args.tailscale_archive, args.nft_runtime, args.output, args.version))


if __name__ == "__main__":
    main()
