#!/usr/bin/env python3
"""Upgrade this host to a signed release.

The installer that ships inside a package cannot vouch for that package, so the
check runs here, in the code that is already installed: download ``SHA256SUMS``
and its signature, verify them with the release key this host has pinned, check
the package's SHA-256 against the signed list, unpack it safely, and only then
run its installer. A package signed by another key (a fork's, or an attacker's)
is refused.

  python3 /root/apps/vps-server/src/web/upgrade.py               # latest release
  python3 /root/apps/vps-server/src/web/upgrade.py --version v6.6.0
  python3 /root/apps/vps-server/src/web/upgrade.py --from /root/downloads   # files already downloaded

A host that has not pinned a key yet needs ``--trust-fingerprint`` with the
fingerprint published by the maintainer; the key is then pinned. Changing the
pinned key later needs ``--accept-key-change`` with the new fingerprint.
Standard library only.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import online_assets  # noqa: E402
import release_trust as trust  # noqa: E402
import secure_store  # noqa: E402
import state_paths  # noqa: E402

DEFAULT_REPO = "CharlesGool/vps-server"
SUMS, SIGNATURE = "SHA256SUMS", "SHA256SUMS.sig"
TAG_RE = re.compile(r"v\d+\.\d+\.\d+")
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
TOP = "vps-server"
MAX_SMALL = 1 << 20


class UpgradeError(Exception):
    pass


def package_name(tag, variant):
    return f"vps-server-{tag}-linux-amd64{'-online' if variant == 'online' else ''}.tar.gz"


def release_url(repo, tag, name):
    return f"https://github.com/{repo}/releases/download/{tag}/{name}"


def installed_version(prefix):
    for candidate in (Path(prefix) / "VERSION", Path(prefix) / "config" / "VERSION"):
        try:
            text = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if re.fullmatch(r"\d+\.\d+\.\d+", text):
            return text
    return None


def fetch_small(url, opener=urllib.request.urlopen):
    """A signature or a checksum list: tiny, and checked afterwards, so any mirror will do."""
    last = None
    for source in online_assets.sources(url):
        try:
            request = urllib.request.Request(source, headers={"User-Agent": "vps-server"})
            with opener(request, timeout=30) as response:
                data = response.read(MAX_SMALL + 1)
            if len(data) > MAX_SMALL:
                raise UpgradeError("unexpectedly large download: " + url)
            return data
        except (OSError, ValueError) as error:
            last = error
    raise UpgradeError(f"download failed: {url}: {last}")


def latest_tag(repo, opener=urllib.request.urlopen):
    request = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest",
                                     headers={"User-Agent": "vps-server", "Accept": "application/vnd.github+json"})
    try:
        with opener(request, timeout=30) as response:
            tag = json.loads(response.read(MAX_SMALL).decode("utf-8")).get("tag_name", "")
    except (OSError, ValueError) as error:
        raise UpgradeError(f"cannot find the latest release ({error}); pass --version vX.Y.Z") from None
    if not TAG_RE.fullmatch(tag):
        raise UpgradeError("the latest release has an unexpected tag; pass --version vX.Y.Z")
    return tag


def safe_extract(archive, destination):
    """Unpack a package; refuse anything that could land outside ``destination``/vps-server."""
    destination = Path(destination).resolve()
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        for member in members:
            parts = Path(member.name).parts
            if not parts or parts[0] != TOP or member.name.startswith("/") or ".." in parts:
                raise UpgradeError("unsafe path in package: " + member.name)
            if member.issym():
                link = Path(member.linkname)
                resolved = (destination / Path(member.name).parent / link).resolve()
                if link.is_absolute() or destination not in resolved.parents and resolved != destination:
                    raise UpgradeError("unsafe link in package: " + member.name)
            elif not (member.isfile() or member.isdir()):
                raise UpgradeError("unsupported entry in package: " + member.name)
        bundle.extraction_filter = getattr(tarfile, "tar_filter", None)
        bundle.extractall(destination)
    root = destination / TOP
    if not (root / "deploy" / "install.sh").is_file():
        raise UpgradeError("the package has no installer")
    return root


def run(args, *, state_dir=None, prefix=None, opener=urllib.request.urlopen, installer=None, out=print):
    """The whole upgrade; returns the process exit code."""
    state = Path(state_dir) if state_dir else state_paths.state_dir()
    prefix = Path(prefix) if prefix else Path(__file__).resolve().parents[2]
    pinned = trust.read_pinned(state)
    if pinned is None and not args.trust_fingerprint:
        raise UpgradeError(
            "this host has not pinned a release key yet; pass --trust-fingerprint with the fingerprint "
            "the maintainer published, or install a signed package once with its installer")
    if not REPO_RE.fullmatch(args.repo):
        raise UpgradeError("invalid repository")
    source_dir = Path(args.source) if args.source else None
    tag = args.version
    if tag is None:
        if source_dir is None:
            tag = latest_tag(args.repo, opener)
        else:
            matches = sorted(p.name for p in source_dir.glob("vps-server-v*-linux-amd64*.tar.gz"))
            found = {m.group(1) for name in matches if (m := re.match(r"vps-server-(v\d+\.\d+\.\d+)-", name))}
            if len(found) != 1:
                raise UpgradeError("cannot tell the version from the files; pass --version")
            tag = found.pop()
    if not TAG_RE.fullmatch(tag):
        raise UpgradeError("invalid version " + tag)
    name = package_name(tag, args.variant)

    current = installed_version(prefix)
    if current and not args.allow_downgrade:
        if trust.version_tuple(tag) < trust.version_tuple(current):
            raise UpgradeError(f"{tag} is older than the installed {current}; --allow-downgrade overrides")
        if trust.version_tuple(tag) == trust.version_tuple(current):
            out(f"Already at {tag}.")
            return 0

    work = Path(tempfile.mkdtemp(prefix=".vps-server-upgrade-", dir=str(prefix.parent)))
    try:
        def small(filename):
            if source_dir is not None:
                path = source_dir / filename
                if not path.is_file():
                    raise UpgradeError(f"missing {path}")
                return path.read_bytes()
            return fetch_small(release_url(args.repo, tag, filename), opener)

        sums_raw, signature = small(SUMS), small(SIGNATURE)
        key = pinned
        entries = None
        if key is not None:
            entries = trust.verify_sums(sums_raw, signature, key)
            out(f"Signature OK (key {trust.fingerprint(key)}).")
        else:
            # First pin: the key comes from the package, and counts only if its
            # fingerprint is the one the operator typed.
            entries = {}
            for line in sums_raw.decode("utf-8", "replace").splitlines():
                found = trust.SUMS_LINE.fullmatch(line.strip())
                if found:
                    entries[found.group(2)] = found.group(1)
        expected = entries.get(name)
        if expected is None:
            raise UpgradeError(f"{name} is not in the signed list")

        archive = work / name
        if source_dir is not None:
            shutil.copyfile(source_dir / name, archive)
            if trust.file_sha256(archive) != expected:
                raise UpgradeError("the package does not match the checksum list")
        else:
            try:
                online_assets._download(release_url(args.repo, tag, name), archive, expected)
            except RuntimeError as error:   # every source failed, or the download did not match its checksum
                raise UpgradeError(str(error)) from None
        out("Package checksum OK.")

        root = safe_extract(archive, work / "unpacked")
        shipped = trust.read_shipped(root)
        if key is None:
            if shipped is None or not trust.same_fingerprint(args.trust_fingerprint, shipped):
                raise UpgradeError("the package's key does not have the fingerprint you gave")
            trust.verify_sums(sums_raw, signature, shipped)
            out(f"Signature OK; pinning key {trust.fingerprint(shipped)}.")
            trust.write_pinned(state, shipped)
            key = shipped
        elif shipped is None:
            raise UpgradeError("the package carries no release key; refusing an unsigned downgrade of trust")
        elif shipped != key and not (args.accept_key_change and trust.same_fingerprint(args.accept_key_change, shipped)):
            raise UpgradeError(
                f"the package ships a different release key ({trust.fingerprint(shipped)}); "
                "if the change is intended pass --accept-key-change with that fingerprint")
        package_version = (root / "config" / "VERSION").read_text(encoding="utf-8").strip()
        if package_version != tag.lstrip("v"):
            raise UpgradeError(f"the package says {package_version}, not {tag}")

        if trust.version_tuple(package_version) < (7, 0, 0) and secure_store.enabled() \
                and any(state == "encrypted" for _path, state in secure_store.status()):
            raise UpgradeError(
                f"{tag} cannot read the console's encrypted state files (introduced in v7.0.0); first run "
                f"`python3 {Path(__file__).resolve().parent / 'secure_store.py'} decrypt-all`, then upgrade again")
        if args.dry_run:
            out(f"Would upgrade {current or '?'} -> {tag}.")
            return 0
        env = dict(os.environ)
        env["VPSSRV_MODULES"] = env.get("VPSSRV_MODULES") or "web"
        if args.accept_key_change:
            env["VPSSRV_ACCEPT_KEY_CHANGE"] = args.accept_key_change
        command = installer or ["bash", str(root / "deploy" / "install.sh")]
        out(f"Installing {tag} ...")
        return subprocess.run(command, env=env, cwd=str(root), check=False).returncode
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", help="release tag such as v6.6.0 (default: the latest release)")
    parser.add_argument("--variant", choices=("offline", "online"), default="offline")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--from", dest="source", help="directory holding SHA256SUMS, SHA256SUMS.sig and the package")
    parser.add_argument("--trust-fingerprint", default="", help="pin the package's release key if it has this fingerprint")
    parser.add_argument("--accept-key-change", default="", help="accept a new release key with this fingerprint")
    parser.add_argument("--allow-downgrade", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="verify everything, install nothing")
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (UpgradeError, trust.TrustError, OSError, tarfile.TarError) as error:
        print(f"Upgrade refused: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
