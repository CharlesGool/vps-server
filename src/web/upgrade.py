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
The package variant (offline or online) defaults to the one this host was
installed from, and the installer gets this install's PREFIX and service name.
The installer finishes in a background systemd unit: Ctrl-C only stops
following it, and the unpacked package stays until that unit is done.
Standard library only.
"""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
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
# The installer's own background job (deploy/install.sh) and its result file under PREFIX.
INSTALL_UNIT = "vps-server-install.service"
INSTALL_RESULT = Path(".local") / "install-job" / "exit-code"
UNIT_DIR = Path("/etc/systemd/system")
# Left in a work directory the installer was still reading when this command stopped.
DETACHED = ".installer-running"
WORK_PREFIX = ".vps-server-upgrade-"


class UpgradeError(Exception):
    pass


class LatestError(UpgradeError):
    """The latest release could not be found. ``code``: unreachable, rate_limited, not_found or invalid."""

    def __init__(self, code, detail):
        super().__init__(f"cannot find the latest release ({detail}); pass --version vX.Y.Z")
        self.code, self.detail = code, detail


def package_name(tag, variant):
    return f"vps-server-{tag}-linux-amd64{'-online' if variant == 'online' else ''}.tar.gz"


def release_url(repo, tag, name):
    return f"https://github.com/{repo}/releases/download/{tag}/{name}"


def installed_variant(prefix):
    """``offline`` or ``online``: the package this host was installed from, or None when unknown
    (a source checkout, or a package older than the record)."""
    for candidate in (Path(prefix) / "installer-source" / "config" / "PACKAGE_VARIANT",
                      Path(prefix) / "config" / "PACKAGE_VARIANT"):
        try:
            text = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text in ("offline", "online"):
            return text
    return None


def console_unit(prefix, unit_dir=UNIT_DIR):
    """(PREFIX as the unit file spells it, service name) of the console that runs ``prefix``/app.py, or None.

    The installer writes ``ExecStart=/usr/bin/env python3 $PREFIX/app.py`` into ``$SERVICE_NAME.service``.
    """
    target = (Path(prefix) / "app.py").resolve()
    found = []
    try:
        candidates = sorted(Path(unit_dir).glob("*.service"))
    except OSError:
        return None
    for path in candidates:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            script = line.split()[-1] if line.startswith("ExecStart=") else ""
            if not script.endswith("/app.py"):
                continue
            try:
                same = Path(script).resolve() == target
            except (OSError, RuntimeError):
                same = False
            if same:
                found.append((str(Path(script).parent), path.name[:-len(".service")]))
    found.sort(key=lambda item: item[1] != "vps-server-web")
    return found[0] if found else None


def install_job_running(prefix, runner=subprocess.run):
    """True while the installer's background unit may still read the package it was started from."""
    try:
        state = runner(["systemctl", "show", "-p", "ActiveState", "--value", INSTALL_UNIT],
                       capture_output=True, text=True, timeout=10, check=False).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False
    if state not in ("active", "activating", "reloading", "deactivating"):
        return False
    # The job writes its exit code last; after that it no longer reads the package.
    try:
        return (Path(prefix) / INSTALL_RESULT).stat().st_size == 0
    except OSError:
        return True


def remove_leftovers(parent, prefix, runner=subprocess.run):
    """Remove work directories an earlier run had to leave to a still-running installer."""
    if install_job_running(prefix, runner):
        return
    for path in Path(parent).glob(WORK_PREFIX + "*"):
        if (path / DETACHED).is_file():
            shutil.rmtree(path, ignore_errors=True)


def installed_version(prefix):
    for candidate in (Path(prefix) / "VERSION", Path(prefix) / "config" / "VERSION"):
        try:
            text = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if re.fullmatch(r"\d+\.\d+\.\d+", text):
            return text
    return None


def fetch_small(url, opener=urllib.request.urlopen, timeout=30):
    """A signature or a checksum list: tiny, and checked afterwards, so any mirror will do."""
    last = None
    for source in online_assets.sources(url):
        try:
            request = urllib.request.Request(source, headers={"User-Agent": "vps-server"})
            with opener(request, timeout=timeout) as response:
                data = response.read(MAX_SMALL + 1)
            if len(data) > MAX_SMALL:
                raise UpgradeError("unexpectedly large download: " + url)
            return data
        except (OSError, ValueError) as error:
            last = error
    raise UpgradeError(f"download failed: {url}: {last}") from last


def _http_failure(error, where):
    if isinstance(error, urllib.error.HTTPError):
        code = {403: "rate_limited", 429: "rate_limited", 404: "not_found"}.get(error.code, "unreachable")
        return code, f"{where}: HTTP {error.code}"
    return "unreachable", f"{where}: {getattr(error, 'reason', None) or error}"


def latest_tag(repo, opener=urllib.request.urlopen, timeout=30):
    """The tag of the latest release; LatestError says why when there is none.

    The GitHub API first. Hosts that cannot reach it (or are rate limited) read the
    latest release's ``SHA256SUMS`` through ``releases/latest/download``, which the
    download mirrors serve too, and take the version from the package names in it.
    """
    request = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest",
                                     headers={"User-Agent": "vps-server", "Accept": "application/vnd.github+json"})
    try:
        with opener(request, timeout=timeout) as response:
            data = json.loads(response.read(MAX_SMALL).decode("utf-8"))
        tag = data.get("tag_name", "") if isinstance(data, dict) else ""
        if TAG_RE.fullmatch(str(tag)):
            return tag
        code, detail = "invalid", "GitHub API: unexpected tag " + repr(tag)[:40]
    except (OSError, ValueError) as error:   # HTTPError and URLError are OSErrors
        code, detail = _http_failure(error, "GitHub API")
    url = f"https://github.com/{repo}/releases/latest/download/{SUMS}"
    try:
        sums = fetch_small(url, opener, timeout).decode("utf-8", "replace")
    except UpgradeError as error:
        cause = error.__cause__ or error.__context__
        fallback, more = _http_failure(cause, "release download") if cause else ("unreachable", str(error))
        raise LatestError(code if code != "unreachable" else fallback, f"{detail}; {more}") from None
    tags = set(re.findall(r"vps-server-(v\d+\.\d+\.\d+)-linux-", sums))
    if len(tags) != 1:
        raise LatestError("invalid", f"{detail}; the latest {SUMS} names no single version")
    return tags.pop()


def package_key(archive):
    """The release key a package ships (``config/release-key.pub``), read without unpacking anything."""
    wanted = Path(TOP) / trust.SHIPPED
    with tarfile.open(archive, "r:gz") as bundle:
        found = None
        for member in bundle.getmembers():
            if Path(member.name) == wanted:
                found = member      # the last one wins, as it would when unpacking
        if found is None:
            return None
        if not found.isfile() or found.size > 4096:
            raise UpgradeError("unexpected release key entry in package")
        data = bundle.extractfile(found).read()
    return trust.parse_key(data.decode("utf-8", "replace"))


def safe_extract(archive, destination):
    """Unpack a package; refuse anything that could land outside ``destination``/vps-server."""
    destination = Path(destination).resolve()
    # Python before 3.9.17, 3.10.12 and 3.11.4 has no extraction filter, and the check
    # below cannot see a chain of links (d1 -> ., d1/d2 -> .., then d1/d2/x): refuse
    # every link there. Release packages contain none.
    link_filter = getattr(tarfile, "tar_filter", None)
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        for member in members:
            parts = Path(member.name).parts
            if not parts or parts[0] != TOP or member.name.startswith("/") or ".." in parts:
                raise UpgradeError("unsafe path in package: " + member.name)
            if (member.issym() or member.islnk()) and link_filter is None:
                raise UpgradeError("links in packages need a newer Python: " + member.name)
            if member.issym():
                link = Path(member.linkname)
                resolved = (destination / Path(member.name).parent / link).resolve()
                if link.is_absolute() or destination not in resolved.parents and resolved != destination:
                    raise UpgradeError("unsafe link in package: " + member.name)
            elif not (member.isfile() or member.isdir()):
                raise UpgradeError("unsupported entry in package: " + member.name)
        if link_filter is not None:
            bundle.extraction_filter = link_filter
        bundle.extractall(destination)
    root = destination / TOP
    if not (root / "deploy" / "install.sh").is_file():
        raise UpgradeError("the package has no installer")
    return root


def run(args, *, state_dir=None, prefix=None, opener=urllib.request.urlopen, installer=None, out=print,
        unit_dir=UNIT_DIR, runner=subprocess.run):
    """The whole upgrade; returns the process exit code."""
    state = Path(state_dir) if state_dir else state_paths.state_dir()
    prefix = Path(prefix) if prefix else Path(__file__).resolve().parents[2]
    # The installer defaults to /root/apps/vps-server and vps-server-web: name this install's own.
    install_prefix, service = console_unit(prefix, unit_dir) or (str(prefix), None)
    install_prefix = os.environ.get("PREFIX") or install_prefix
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
    variant = args.variant or installed_variant(prefix) or "offline"
    name = package_name(tag, variant)

    current = installed_version(prefix)
    if current and not args.allow_downgrade:
        if trust.version_tuple(tag) < trust.version_tuple(current):
            raise UpgradeError(f"{tag} is older than the installed {current}; --allow-downgrade overrides")
        if trust.version_tuple(tag) == trust.version_tuple(current):
            out(f"Already at {tag}.")
            return 0

    remove_leftovers(prefix.parent, install_prefix, runner)
    work = Path(tempfile.mkdtemp(prefix=WORK_PREFIX, dir=str(prefix.parent)))
    detached = False
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
            # fingerprint is the one the operator typed. It is read from the archive
            # and checks this signature below, before anything is unpacked.
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

        # Every trust decision is made before anything is unpacked.
        shipped = package_key(archive)
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
        root = safe_extract(archive, work / "unpacked")
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
        env.setdefault("PREFIX", install_prefix)
        if service:
            env.setdefault("SERVICE_NAME", service)
        if args.accept_key_change:
            env["VPSSRV_ACCEPT_KEY_CHANGE"] = args.accept_key_change
        command = installer or ["bash", str(root / "deploy" / "install.sh")]
        out(f"Installing {tag} ({variant}) ...")
        try:
            return subprocess.run(command, env=env, cwd=str(root), check=False).returncode
        finally:
            # Ctrl-C, a closed terminal or a stopped unit ends only the view: the installer
            # goes on in its own unit and still reads the unpacked package.
            detached = install_job_running(install_prefix, runner)
    finally:
        if detached:
            try:
                (work / DETACHED).touch()
                out(f"The installer is still running in the background ({INSTALL_UNIT}); its log is "
                    f"{Path(install_prefix) / INSTALL_RESULT.parent / 'install.log'}. {work} is kept until it "
                    f"finishes and removed by the next upgrade.")
            except OSError:     # the marker, or a terminal that is already gone
                pass
        else:
            shutil.rmtree(work, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", help="release tag such as v6.6.0 (default: the latest release)")
    parser.add_argument("--variant", choices=("offline", "online"),
                        help="package variant (default: the one this host was installed from, else offline)")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--from", dest="source", help="directory holding SHA256SUMS, SHA256SUMS.sig and the package")
    parser.add_argument("--trust-fingerprint", default="", help="pin the package's release key if it has this fingerprint")
    parser.add_argument("--accept-key-change", default="", help="accept a new release key with this fingerprint")
    parser.add_argument("--allow-downgrade", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="verify everything, install nothing")
    args = parser.parse_args(argv)

    def stop(_signum, _frame):
        raise KeyboardInterrupt
    # A closed terminal or `systemctl stop` must still leave through run()'s cleanup (nohup is respected).
    for number in (signal.SIGTERM, signal.SIGHUP):
        if signal.getsignal(number) != signal.SIG_IGN:
            signal.signal(number, stop)
    try:
        return run(args)
    except (UpgradeError, trust.TrustError, OSError, tarfile.TarError) as error:
        print(f"Upgrade refused: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
