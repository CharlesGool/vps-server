#!/usr/bin/env python3
"""Fetch and verify the pinned upstream archives on a connected build host."""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TAILSCALE = ("https://pkgs.tailscale.com/stable/tailscale_1.102.4_amd64.tgz",
             "50748df1045e60b5b695f19f4c56b0da36c019948b440fb456b6584a50f0d8b9")
# A fixed snapshot keeps every pinned file downloadable after Debian point
# releases replace them in the live pool.
DEBIAN = "https://snapshot.debian.org/archive/debian/20261020T000000Z/"
NFT_RUNTIME_SHA256 = "1357164ec1f43bfff0ab99b6b13030215e437ecd3b25d7c4b241ae4923613909"
NFT_SOURCES_SHA256 = "ef1400a06c405c717f33c469c10672cd6906c52676faa8a318c3ac716007d217"
# Debian 13 nftables and iptables with their own glibc. The wrappers run them
# through the bundled loader, so the host's older or newer glibc is not used.
PACKAGES = (
    ("pool/main/n/nftables/nftables_1.1.3-1_amd64.deb", "2ddfa61baaf3a76e2c499db9e521ba6affb226f85af0b6fef739f346ac5f0c39"),
    ("pool/main/n/nftables/libnftables1_1.1.3-1_amd64.deb", "c7cbee3dce8452ae5c3c4269f6f52e96b896d36a46ea3c490e0e11e8ff359896"),
    ("pool/main/g/glibc/libc6_2.41-12+deb13u4_amd64.deb", "967aa62605721081c3eb2a17650611a792aa802d76a6511d1840242623d204c9"),
    ("pool/main/g/gmp/libgmp10_6.3.0+dfsg-3_amd64.deb", "d0d0265eb01770f17afd0f7c8c0622f80479dcfbbe13653a0debeec61464e622"),
    ("pool/main/j/jansson/libjansson4_2.14-2+b3_amd64.deb", "60707a62fe6c1228c3389b12a13ca4efd76defc5532473e547a29e99cf7d2a6e"),
    ("pool/main/libm/libmnl/libmnl0_1.0.5-3_amd64.deb", "4ec9c1096e0b954e3bdb03a62314ee7f49999045d3d55be3e4ded520ffc9baf5"),
    ("pool/main/libn/libnftnl/libnftnl11_1.2.9-1_amd64.deb", "1b3eae46bfb9c6ab44e404797fb45278045f926d73974a84097ad47a3e27d983"),
    ("pool/main/i/iptables/libxtables12_1.8.11-2_amd64.deb", "4de5aa59faef5e98d6ba9f5f521a915be5641f224f597862f8d29e8319e8db16"),
    ("pool/main/libe/libedit/libedit2_3.1-20250104-1_amd64.deb", "b002ea172b9c1e34a67bc497c523c67bb74c3f0a4e98113cb083990a1f1d3bfe"),
    ("pool/main/libb/libbsd/libbsd0_0.12.2-2_amd64.deb", "e5a85986fa6bec3307ab1bc860736b478b331882bc45e17675a7bdf88eecb43a"),
    ("pool/main/libm/libmd/libmd0_1.1.0-2+b1_amd64.deb", "7244ec3839b61fac0c1884fe08aaa040f26e8f1f35f1f5d3482eacefd30d1b44"),
    ("pool/main/n/ncurses/libtinfo6_6.5+20250216-2_amd64.deb", "8b9f6a7983e9418564e48a627518de4c03917b56efe68d7f3e93bd8fffa1cc10"),
    ("pool/main/i/iptables/iptables_1.8.11-2_amd64.deb", "95ba166bb68a76ca1513196dd59d91e3c33b2096884c6de80406f302b18a030e"),
    ("pool/main/i/iptables/libip4tc2_1.8.11-2_amd64.deb", "762e4d9c7f86b3fdaefee2baf61ce40073d46d7602651433f2cb7a5eabfb47b4"),
    ("pool/main/i/iptables/libip6tc2_1.8.11-2_amd64.deb", "d5ecaad5595dc88d08f317997beb53a4906c45ea79ee14ec89103f72573e3f99"),
    ("pool/main/libn/libnetfilter-conntrack/libnetfilter-conntrack3_1.1.0-1_amd64.deb", "ffbac5d06fbe432d5171f2eb5b2504968377f27be133f72c81e71250a9957506"),
    ("pool/main/libn/libnfnetlink/libnfnetlink0_1.0.2-3_amd64.deb", "5e4c3c40a04ffdb4139e4bef1136585e151a8eb8c71efa6c7250b636b3c0d1b1"),
    # iproute2 supplies ip and ss for hosts that lack them, with its own libraries.
    ("pool/main/i/iproute2/iproute2_6.15.0-1_amd64.deb", "7b2dcade4a83ded723fcab21c5a53c47f29352c9c5e1661a089a1e481b3fb48a"),
    ("pool/main/libs/libselinux/libselinux1_3.8.1-1_amd64.deb", "68bb8d32bd8d6d7d2f5952a169db03d1484b46ae1e52abccdec42a19dccea5d5"),
    ("pool/main/p/pcre2/libpcre2-8-0_10.46-1~deb13u2_amd64.deb", "1252b96a5bc44bb5db982bef8eb18e54f5047cede2aff641bce4f8e1edb91c3e"),
    ("pool/main/libt/libtirpc/libtirpc3t64_1.3.6+ds-1_amd64.deb", "ef4536c09bf5063554310e22d586ae90990100ba66d2fe7c35660e9e658913b6"),
    ("pool/main/k/krb5/libgssapi-krb5-2_1.21.3-5+deb13u1_amd64.deb", "30847c1fde4240567d7ed3aeab4f655dd591203758b857e85e824045aae70299"),
    ("pool/main/k/krb5/libkrb5-3_1.21.3-5+deb13u1_amd64.deb", "47d71d6a7f2e59b9bae5f89602397594805113b95889ad18fa703cd53abafc97"),
    ("pool/main/k/krb5/libk5crypto3_1.21.3-5+deb13u1_amd64.deb", "7da07ee674b47f1f0be7cc89317c25310086a1f1761217d0f72e6ae2c5a69b84"),
    ("pool/main/k/krb5/libkrb5support0_1.21.3-5+deb13u1_amd64.deb", "3a0acd8b37955c0e102c756b52c97df2a31f67b96453c35dab70df218d309117"),
    ("pool/main/k/keyutils/libkeyutils1_1.6.3-6_amd64.deb", "0b11ad17be0300b63ad4eeb4c6450fed24d34b7b740f23e5363dcb29ee6d5eba"),
    ("pool/main/e/e2fsprogs/libcom-err2_1.47.2-3+b12_amd64.deb", "bd43e020b8fed399db3eebf098111f10fba4c436fff99ccad72cc7e27c9764ec"),
    ("pool/main/libb/libbpf/libbpf1_1.5.0-3_amd64.deb", "04c96ead3024888d80d08c8d08cc8cf4589f4614627acc69519f87ffb5adc1c2"),
    ("pool/main/e/elfutils/libelf1t64_0.192-4_amd64.deb", "94497b7e17b6f574a0605b380d454e20d3f01a9c63b70c2a2263f679d30053e1"),
    ("pool/main/z/zlib/zlib1g_1.3.dfsg+really1.3.1-1+b1_amd64.deb", "015be740d6236ad114582dea500c1d907f29e16d6db00566ca32fb68d71ac90d"),
    ("pool/main/libz/libzstd/libzstd1_1.5.7+dfsg-1_amd64.deb", "2f6a2aeacfc925eba8b00ac9139bc4bfccf8cacb09eb93de067074b26948eef9"),
    ("pool/main/libc/libcap2/libcap2_2.75-10+deb13u1+b3_amd64.deb", "89fc4d34fc7a28ad6f0fcd0c561ab253b9dedf6f77f5a000b47c276c8295bf67"),
)
# iconv modules and manual pages are never loaded by nft or iptables.
PRUNED = ("usr/lib/x86_64-linux-gnu/gconv", "usr/share/man")
WRAPPER = """#!/bin/sh
# Run the bundled {program} with the bundled loader and glibc.
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd) || exit 1
lib="$root/usr/lib/x86_64-linux-gnu"
{setup}exec "$lib/ld-linux-x86-64.so.2" --library-path "$lib" {argv0}"$root/{binary}" "$@"
"""
WRAPPERS = {
    "nft": WRAPPER.format(program="nft", setup="", argv0="", binary="usr/sbin/nft"),
    "iptables": WRAPPER.format(program="iptables", setup='XTABLES_LIBDIR="$lib/xtables"\nexport XTABLES_LIBDIR\n',
                               argv0="--argv0 iptables ", binary="usr/sbin/xtables-nft-multi"),
    "ip": WRAPPER.format(program="ip", setup="", argv0="", binary="usr/bin/ip"),
    "ss": WRAPPER.format(program="ss", setup="", argv0="", binary="usr/bin/ss"),
}


def verified(path, expected):
    return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected


def download(url, path, digest):
    if verified(path, digest):
        return
    # snapshot.debian.org sometimes drops a connection; retry before giving up.
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                payload = response.read()
        except OSError:
            if attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))
            continue
        if hashlib.sha256(payload).hexdigest() != digest:
            raise ValueError(f"checksum mismatch: {path.name}")
        path.write_bytes(payload)
        return


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
    runtime = output / "nft-runtime-trixie.tar.gz"
    if not verified(runtime, NFT_RUNTIME_SHA256):
        with tempfile.TemporaryDirectory(prefix="vps-nft-build-") as temporary:
            root = Path(temporary) / "root"
            root.mkdir()
            root.chmod(0o755)
            for filename, digest in PACKAGES:
                package = output / Path(filename).name
                download(DEBIAN + filename, package, digest)
                subprocess.run(["dpkg-deb", "-x", str(package), str(root)], check=True)
            for pruned in PRUNED:
                shutil.rmtree(root / pruned)
            (root / "bin").mkdir(mode=0o755)
            (root / "bin").chmod(0o755)
            for name, text in WRAPPERS.items():
                wrapper = root / "bin" / name
                wrapper.write_text(text, encoding="utf-8")
                wrapper.chmod(0o755)
            subprocess.run(["tar", "--sort=name", "--mtime=@0", "--owner=0", "--group=0",
                            "--numeric-owner", "-czf", str(runtime), "-C", str(root), "."], check=True)
        if not verified(runtime, NFT_RUNTIME_SHA256):
            raise ValueError("assembled nftables runtime checksum mismatch")
    sources = output / "nft-sources-trixie.tar.gz"
    if not verified(sources, NFT_SOURCES_SHA256):
        manifest = json.loads((ROOT / "third_party" / "nft" / "source-manifest.json").read_text(encoding="utf-8"))
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
