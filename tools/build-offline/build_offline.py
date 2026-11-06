#!/usr/bin/env python3
"""Create a release tarball that needs no Git or curl on the target.

The offline variant carries every binary and system-tool runtime. The large
third-party binaries listed in config/online-assets.json are not committed:
the offline build downloads them into third_party/ (ignored by Git) and checks
each SHA-256 first. The online variant leaves them out; the installer
downloads and verifies them.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "web"))
import online_assets  # noqa: E402
NFT_SHA256 = "1357164ec1f43bfff0ab99b6b13030215e437ecd3b25d7c4b241ae4923613909"
NFT_SOURCES_SHA256 = "ef1400a06c405c717f33c469c10672cd6906c52676faa8a318c3ac716007d217"
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


def build(nft_asset, nft_sources, output, version, variant="offline"):
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
        catalog = online_assets.load(ROOT)
        online_assets.ensure(ROOT, list(catalog))
        nft_asset = Path(nft_asset).resolve()
        if hashlib.sha256(nft_asset.read_bytes()).hexdigest() != NFT_SHA256:
            raise ValueError("nftables runtime checksum mismatch")
        nft_sources = Path(nft_sources).resolve()
        if hashlib.sha256(nft_sources.read_bytes()).hexdigest() != NFT_SOURCES_SHA256:
            raise ValueError("nftables source checksum mismatch")
    with tempfile.TemporaryDirectory(prefix="vps-server-offline-") as temporary:
        staged = Path(temporary) / "vps-server"
        staged.mkdir()
        fetched = _online_only_paths()
        _tracked_source(staged, fetched)
        bundle = ROOT / "web/dist"
        if not all((bundle / name).is_file() for name in ("ui.js", "ui.css")):
            raise ValueError("frontend bundle missing; run npm ci and npm run check in web/")
        shutil.copytree(bundle, staged / "web/dist")
        if offline:
            # ensure() above verified every file; copy them with their modes.
            for relative in sorted(fetched):
                destination = staged / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
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
    parser.add_argument("--nft-runtime")
    parser.add_argument("--nft-sources")
    parser.add_argument("--output", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    if args.variant == "offline" and not (args.nft_runtime and args.nft_sources):
        parser.error("the offline variant needs --nft-runtime and --nft-sources")
    print(build(args.nft_runtime, args.nft_sources,
                args.output, args.version, args.variant))


if __name__ == "__main__":
    main()
