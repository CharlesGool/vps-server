#!/usr/bin/env python3
"""Download the pinned binaries an online package leaves out.

The offline package carries every file listed in config/online-assets.json, so
there is nothing to fetch. The online package omits them; this module fills
`third_party/` from the pinned upstream archives, verifying the archive and
each extracted file by SHA-256 before anything is placed. Only python3 is
needed on the host: no curl, tar, gzip or Git.
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
ATTEMPTS = 3
TIMEOUT = 60


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


def _download(url, destination, expected):
    last = None
    for attempt in range(ATTEMPTS):
        if attempt:
            time.sleep(2 * attempt)
        try:
            sha = hashlib.sha256()
            with urllib.request.urlopen(url, timeout=TIMEOUT) as response, open(destination, "wb") as out:
                for chunk in iter(lambda: response.read(1 << 20), b""):
                    sha.update(chunk)
                    out.write(chunk)
            if sha.hexdigest() != expected:
                raise ValueError(f"checksum mismatch: {url}")
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


def ensure(source, components):
    catalog = load(source)
    for name in components:
        if name in catalog:
            ensure_component(source, name, catalog[name])


def main(argv):
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
