#!/usr/bin/env python3
"""Download the pinned binaries an online package leaves out.

The offline package carries every file listed in config/online-assets.json, so
there is nothing to fetch. The online package omits them; this module fills
`third_party/` from the pinned upstream archives, verifying the archive and
each extracted file by SHA-256 before anything is placed. Only python3 is
needed on the host: no curl, tar, gzip or Git.

GitHub downloads can crawl from mainland China. A source that stays below
MIN_RATE after SLOW_AFTER seconds is dropped for the next one: GitHub itself,
then public GitHub mirrors. Every source is checked against the same SHA-256,
so a mirror can make a download fail but never change what is installed.
VPSSRV_GITHUB_MIRROR puts a mirror prefix of your own first ("none" turns
mirrors off).
"""

import hashlib
import json
import os
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

MANIFEST = Path("config") / "online-assets.json"
ATTEMPTS = 2
TIMEOUT = 60
SLOW_AFTER = 15
MIN_RATE = 200 * 1024
GITHUB_MIRRORS = ("https://gh-proxy.com/", "https://ghfast.top/")


class TooSlow(OSError):
    pass


def _digest(path):
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _verified(path, expected):
    return path.is_file() and _digest(path) == expected


def load(source):
    manifest = Path(source) / MANIFEST
    if not manifest.is_file():
        return {}
    return json.loads(manifest.read_text(encoding="utf-8")).get("components", {})


def known(source, component):
    return component in load(source)


def sources(url, environ=None):
    """The URLs to try for one download, in order."""
    if not url.startswith("https://github.com/"):
        return [url]
    own = (os.environ if environ is None else environ).get("VPSSRV_GITHUB_MIRROR", "").strip()
    if own.lower() == "none":
        return [url]
    mirrors = list(GITHUB_MIRRORS)
    if own.startswith("https://"):
        own = own if own.endswith("/") else own + "/"
        mirrors = [own] + [mirror for mirror in mirrors if mirror != own]
    return [url] + [mirror + url for mirror in mirrors]


def _fetch(url, destination, expected, *, slow_ok, opener=urllib.request.urlopen, clock=time.monotonic):
    sha = hashlib.sha256()
    started, size = clock(), 0
    request = urllib.request.Request(url, headers={"User-Agent": "vps-server"})
    with opener(request, timeout=TIMEOUT) as response, open(destination, "wb") as out:
        for chunk in iter(lambda: response.read(1 << 16), b""):
            sha.update(chunk)
            out.write(chunk)
            size += len(chunk)
            elapsed = clock() - started
            if not slow_ok and elapsed > SLOW_AFTER and size < MIN_RATE * elapsed:
                raise TooSlow(f"too slow: {size // 1024} KiB in {elapsed:.0f} s")
    if sha.hexdigest() != expected:
        raise ValueError(f"checksum mismatch: {url}")


def _download(url, destination, expected, **fetch):
    tries = [source for _attempt in range(ATTEMPTS) for source in sources(url)]
    last = None
    for index, source in enumerate(tries):
        if index:
            time.sleep(1)
        if source != url:
            print(f"Downloading from mirror: {source.split('/')[2]}", flush=True)
        try:
            # The last try keeps any speed: slow is better than nothing.
            _fetch(source, destination, expected, slow_ok=index == len(tries) - 1, **fetch)
            return
        except (OSError, ValueError) as error:
            last = error
    raise RuntimeError(f"download failed: {url}: {last}")


def _place(temp_file, target, expected, mode):
    if _digest(temp_file) != expected:
        raise RuntimeError(f"checksum mismatch: {target.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(temp_file, mode)
    os.replace(temp_file, target)


def ensure_component(source, name, spec):
    source = Path(source)
    pending = [item for item in spec["files"] if not _verified(source / item["path"], item["sha256"])]
    if not pending:
        return
    with tempfile.TemporaryDirectory(prefix=".online-assets-", dir=source) as work:
        archive = Path(work) / "archive"
        _download(spec["url"], archive, spec["archive_sha256"])
        for index, item in enumerate(pending):
            target = source / item["path"]
            staged = Path(work) / f"file-{index}"
            if item["member"] is None:
                os.replace(archive, staged) if len(pending) == 1 else staged.write_bytes(archive.read_bytes())
            else:
                with tarfile.open(archive, "r:gz") as bundle:
                    member = bundle.getmember(item["member"])
                    if not member.isfile():
                        raise RuntimeError(f"unexpected archive member: {item['member']}")
                    with bundle.extractfile(member) as src, open(staged, "wb") as out:
                        for chunk in iter(lambda: src.read(1 << 20), b""):
                            out.write(chunk)
            _place(staged, target, item["sha256"], 0o755 if item["member"] else 0o644)


def missing(source, components):
    """Components with at least one file absent or failing its SHA-256."""
    catalog = load(source)
    return [name for name in components if name in catalog and any(
        not _verified(Path(source) / item["path"], item["sha256"]) for item in catalog[name]["files"])]


def ensure(source, components):
    catalog = load(source)
    for name in components:
        if name in catalog:
            ensure_component(source, name, catalog[name])


def main(argv):
    if argv and argv[0] == "--check":
        # Exit 1 when something must be downloaded, 0 when every file is in place.
        return 1 if len(argv) > 2 and missing(argv[1], argv[2:]) else 0
    if len(argv) < 2:
        return 2
    try:
        ensure(argv[0], argv[1:])
    except (OSError, RuntimeError, KeyError, tarfile.TarError, json.JSONDecodeError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
