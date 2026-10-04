#!/usr/bin/env python3
"""Fetch and verify the pinned upstream archives on a connected build host."""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TAILSCALE = ("https://pkgs.tailscale.com/stable/tailscale_1.102.4_amd64.tgz",
             "50748df1045e60b5b695f19f4c56b0da36c019948b440fb456b6584a50f0d8b9")
DEBIAN = "https://deb.debian.org/debian/"
NFT_RUNTIME_SHA256 = "42eeb9496a173777df2e46d67b32b631e5eb31bbc1a74d2a0fa335f32a46c9eb"
NFT_SOURCES_SHA256 = "fce6ca6c5050ff7715c5bd9fedb0160c942e3e5ede7d2702c02f01d920ac6e83"
PACKAGES = (
    ("pool/main/n/nftables/nftables_0.9.8-3.1+deb11u2_amd64.deb", "a00b1bba3985c4a94c85d21e1cc25ced077456c7b1aef567e0892c149e1e5a68"),
    ("pool/main/n/nftables/libnftables1_0.9.8-3.1+deb11u2_amd64.deb", "5e1ee33354c08401f2b88ffb9544fc57385eaf3a63623f54def0adf9a9f93ab0"),
    ("pool/main/libe/libedit/libedit2_3.1-20191231-2+b1_amd64.deb", "ac545f6ad10ba791aca24b09255ad1d6d943e6bc7c5511d5998e104aee51c943"),
    ("pool/main/libm/libmnl/libmnl0_1.0.4-3_amd64.deb", "4581f42e3373cb72f9ea4e88163b17873afca614a6c6f54637e95aa75983ea7c"),
    ("pool/main/libn/libnftnl/libnftnl11_1.1.9-1_amd64.deb", "04da1ce7c71a3b1f3b52a2315e844dda6f7130db0857262d79d983182e86ccd7"),
    ("pool/main/i/iptables/libxtables12_1.8.7-1_amd64.deb", "9702a4be6f267b58c8fc1cfa0747bbefccb8b9a9af2a3547535533fbf2a7c14d"),
    ("pool/main/j/jansson/libjansson4_2.13.1-1.1_amd64.deb", "7025d03e4ad4177a06692bd8e6edcbdebf7fd3897e5f29b70ae968e17e57f6fa"),
    ("pool/main/g/gmp/libgmp10_6.2.1+dfsg-1+deb11u1_amd64.deb", "fc117ccb084a98d25021f7e01e4dfedd414fa2118fdd1e27d2d801d7248aebbc"),
    ("pool/main/n/ncurses/libtinfo6_6.2+20201114-2+deb11u2_amd64.deb", "96ed58b8fd656521e08549c763cd18da6cff1b7801a3a22f29678701a95d7e7b"),
    ("pool/main/libb/libbsd/libbsd0_0.11.3-1+deb11u1_amd64.deb", "6ec5a08a4bb32c0dc316617f4bbefa8654c472d1cd4412ab8995f3955491f4a8"),
    ("pool/main/libm/libmd/libmd0_1.0.3-3_amd64.deb", "9e425b3c128b69126d95e61998e1b5ef74e862dd1fc953d91eebcc315aea62ea"),
)


def verified(path, expected):
    return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected


def download(url, path, digest):
    if verified(path, digest):
        return
    with urllib.request.urlopen(url, timeout=45) as response:
        payload = response.read()
    if hashlib.sha256(payload).hexdigest() != digest:
        raise ValueError(f"checksum mismatch: {path.name}")
    path.write_bytes(payload)


def fetch(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    tailscale = output / "tailscale_1.102.4_amd64.tgz"
    bundled_tailscale = ROOT / "third_party" / "tailscale" / tailscale.name
    if verified(bundled_tailscale, TAILSCALE[1]):
        if bundled_tailscale != tailscale:
            shutil.copy2(bundled_tailscale, tailscale)
    else:
        download(TAILSCALE[0], tailscale, TAILSCALE[1])
    runtime = output / "nft-runtime-bullseye.tar.gz"
    if not verified(runtime, NFT_RUNTIME_SHA256):
        with tempfile.TemporaryDirectory(prefix="vps-nft-build-") as temporary:
            root = Path(temporary) / "root"
            root.mkdir()
            for filename, digest in PACKAGES:
                package = output / Path(filename).name
                download(DEBIAN + filename, package, digest)
                subprocess.run(["dpkg-deb", "-x", str(package), str(root)], check=True)
            subprocess.run(["tar", "--sort=name", "--mtime=@0", "--owner=0", "--group=0",
                            "--numeric-owner", "-czf", str(runtime), "-C", str(root), "."], check=True)
        if not verified(runtime, NFT_RUNTIME_SHA256):
            raise ValueError("assembled nftables runtime checksum mismatch")
    sources = output / "nft-sources-bullseye.tar.gz"
    if not verified(sources, NFT_SOURCES_SHA256):
        manifest = json.loads((ROOT / "third_party" / "nft" / "source-manifest.json").read_text())
        with tempfile.TemporaryDirectory(prefix="vps-nft-source-") as temporary:
            root = Path(temporary) / "root"
            root.mkdir()
            for package, metadata in sorted(manifest["packages"].items()):
                package_dir = root / package
                package_dir.mkdir()
                for item in metadata["files"]:
                    filename = item["name"]
                    if Path(filename).name != filename:
                        raise ValueError("unsafe source filename")
                    target = package_dir / filename
                    download(DEBIAN + metadata["directory"] + "/" + filename,
                             target, item["sha256"])
                    if target.stat().st_size != item["size"]:
                        raise ValueError("source size mismatch")
            subprocess.run(["tar", "--sort=name", "--mtime=@0", "--owner=0", "--group=0",
                            "--numeric-owner", "-czf", str(sources), "-C", str(root), "."], check=True)
        if not verified(sources, NFT_SOURCES_SHA256):
            raise ValueError("assembled nftables source checksum mismatch")
    return tailscale, runtime, sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    for path in fetch(args.output_dir):
        print(path)


if __name__ == "__main__":
    main()
