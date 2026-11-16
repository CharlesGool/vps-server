#!/usr/bin/env python3
"""Configuration backups: what to save, how to store it, how to put it back.

A backup holds the host's configuration and state, never code (it can be
pulled from GitHub again) and never Mini Drive file contents. It is a
``.tar.gz`` with mode 0600 under ``<state dir>/backups``; its members are
stored without the leading ``/`` and a ``manifest`` names the format.

This module uses only the standard library so the installer can run it before
an upgrade (``config_backup.py create --kind pre-upgrade``) and the console can
import it. Restoring writes system files, so the console runs it through
``systemd-run`` instead of from its read-only sandbox.
"""

import argparse
import base64
import errno
import fnmatch
import io
import json
import os
import re
import socket
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crypto_box  # noqa: E402
import release_trust  # noqa: E402
import secure_store  # noqa: E402
import state_paths  # noqa: E402

FORMAT = 1
MANIFEST = ".vps-server-backup.json"
KINDS = ("manual", "scheduled", "pre-upgrade", "pre-restore")
NAME_RE = re.compile(r"config-(\d{8}T\d{6}Z)-(manual|scheduled|pre-upgrade|pre-restore)\.tar\.gz(\.sealed)?")
SEALED_MAGIC = b"VSB1"          # sealed, no key id (backups made before v7.0.1)
SEALED_MAGIC_2 = b"VSB2"        # sealed; the next 16 bytes say which public key it is sealed to
KEY_ID_LEN = 16
RESULT_NAME = "restore-result.json"
SEAL_AAD = b"vps-server configuration backup"
# Never larger than this when restoring: a configuration backup is small.
MAX_RESTORE_BYTES = 512 * 1024 * 1024

# Fixed configuration locations (module config, units, FRPC instances, Caddy
# state). Anything missing on this host is skipped.
SYSTEM_DIRS = (
    "/etc/vps-server", "/etc/vps-server-nodes", "/etc/vps-server-proxy", "/etc/vps-server-traffic",
    "/etc/vps-server-frps", "/etc/vps-server-caddy", "/etc/vps-server-anytls", "/etc/vps-server-lucky",
    "/etc/frp", "/var/lib/vps-server-caddy",
)
SYSTEM_GLOBS = (
    ("/etc/systemd/system", "vps-server-*"),
    ("/etc/systemd/system", "frpc@*"),
    ("/etc/sysctl.d", "99-vps-server-*"),
)


class BackupError(Exception):
    pass


def backup_dir():
    return state_paths.state_dir() / "backups"


def recipient_file():
    return state_paths.data_dir() / "backup-recipient.pub"


def read_recipient():
    """The public key backups are sealed to, or None when none is set."""
    try:
        raw = base64.b64decode(recipient_file().read_text(encoding="ascii").strip(), validate=True)
    except (OSError, ValueError):
        return None
    return raw if len(raw) == 32 else None


def parse_key(text):
    """32 bytes from a base64 key as shown to the operator; BackupError otherwise."""
    try:
        raw = base64.b64decode(text.strip(), validate=True)
    except (ValueError, AttributeError):
        raise BackupError("not a valid key") from None
    if len(raw) != 32:
        raise BackupError("not a valid key")
    return raw


def set_recipient(public):
    recipient_file().parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".recipient-", dir=recipient_file().parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="ascii") as handle:
            handle.write(base64.b64encode(public).decode("ascii") + "\n")
        os.replace(temporary, recipient_file())
    except BaseException:
        _remove(temporary)
        raise


def new_recipient():
    """Make a key pair, keep the public half, hand back the private half (never stored)."""
    private, public = crypto_box.generate_keypair()
    set_recipient(public)
    return base64.b64encode(private).decode("ascii"), base64.b64encode(public).decode("ascii")


def key_id(public):
    """Short identifier of a public key, stored in the header of a sealed backup."""
    import hashlib
    return hashlib.sha256(b"vps-server backup key" + public).digest()[:KEY_ID_LEN]


def public_from_private(private):
    return crypto_box.x25519_public(private)


def key_fingerprint(public):
    import hashlib
    digest = hashlib.sha256(public).hexdigest()[:32]
    return ":".join(digest[i:i + 4] for i in range(0, 32, 4))


def _excluded(path, state, data):
    """Mini Drive contents and earlier backups are not configuration."""
    for skipped in (state / "backups", data / "files"):
        if path == skipped or skipped in path.parents:
            return True
    return False


def _walk(root, state, data):
    root = Path(root)
    if not root.exists() or root.is_symlink():
        return
    if _excluded(root, state, data):
        return
    yield root
    if root.is_dir():
        for child in sorted(root.iterdir()):
            yield from _walk(child, state, data)


def config_files(sealed=False):
    """Absolute paths to save, in a stable order."""
    state = state_paths.state_dir()
    data = state_paths.data_dir()
    roots = [state]
    if data != state / "data" and state not in data.parents:
        roots.append(data)
    roots.extend(Path(item) for item in SYSTEM_DIRS)
    for directory, pattern in SYSTEM_GLOBS:
        folder = Path(directory)
        if folder.is_dir():
            roots.extend(sorted(folder.glob(pattern)))
    seen, result = set(), []
    # A plain archive must not carry the key that opens the encrypted state files next to them.
    withheld = None if sealed else secure_store.key_path()
    for root in roots:
        for path in _walk(root, state, data):
            if path not in seen and path != withheld:
                seen.add(path)
                result.append(path)
    return result


def allowed_prefixes():
    state = state_paths.state_dir()
    data = state_paths.data_dir()
    prefixes = [state, data]
    prefixes.extend(Path(item) for item in SYSTEM_DIRS)
    return prefixes


def _version():
    override = os.environ.get("VPSSRV_BACKUP_VERSION", "").strip()
    if override:
        return override
    for candidate in (Path(__file__).resolve().parents[2] / "config" / "VERSION",
                      Path(__file__).resolve().parent / "VERSION"):
        try:
            return candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
    return "unknown"


def publish(temporary, kind, directory=None, suffix=""):
    """Give a finished file its final name without replacing any other backup.

    The name carries the time to the second; when it is taken the time moves
    on by a second. ``os.link`` fails if the name exists, so two backups
    created in the same second (or at the same moment) never overwrite each other.
    """
    directory = Path(directory) if directory else backup_dir()
    moment = datetime.now(timezone.utc)
    for _ in range(3600):
        name = f"config-{moment.strftime('%Y%m%dT%H%M%SZ')}-{kind}.tar.gz{suffix}"
        try:
            os.link(temporary, directory / name)
        except FileExistsError:
            moment += timedelta(seconds=1)
            continue
        _remove(temporary)
        return name
    raise BackupError("too many backups")


def create_backup(kind="manual", directory=None):
    """Write one backup and return its file name."""
    if kind not in KINDS:
        raise BackupError("invalid backup kind")
    directory = Path(directory) if directory else backup_dir()
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    recipient = read_recipient()
    paths = config_files(sealed=recipient is not None)
    descriptor, temporary = tempfile.mkstemp(prefix=".partial-", dir=directory)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            with tarfile.open(fileobj=handle, mode="w:gz") as archive:
                manifest = json.dumps({
                    "format": FORMAT, "version": _version(), "kind": kind,
                    "created": int(time.time()), "host": socket.gethostname(),
                    "files": len(paths)}).encode("utf-8")
                info = tarfile.TarInfo(MANIFEST)
                info.size, info.mtime, info.mode = len(manifest), int(time.time()), 0o600
                archive.addfile(info, io.BytesIO(manifest))
                for path in paths:
                    try:
                        status = path.lstat()
                    except FileNotFoundError:
                        continue
                    if not (path.is_dir() or path.is_file()) or path.is_symlink():
                        continue
                    archive.add(path, arcname=str(path).lstrip("/"), recursive=False)
        if recipient is not None:
            # Seal to the operator's public key: this host can write the backup but never read it back.
            with open(temporary, "rb") as handle:
                sealed = SEALED_MAGIC_2 + key_id(recipient) + crypto_box.seal(recipient, handle.read(), SEAL_AAD)
            with open(temporary, "wb") as handle:
                handle.write(sealed)
        name = publish(temporary, kind, directory, ".sealed" if recipient is not None else "")
    except OSError as exc:
        _remove(temporary)
        raise BackupError("no space left" if exc.errno == errno.ENOSPC else "cannot write backup") from exc
    except BaseException:
        _remove(temporary)
        raise
    return name


def _remove(path):
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def list_backups(directory=None):
    """Newest first: name, kind, created (unix), size."""
    directory = Path(directory) if directory else backup_dir()
    items = []
    try:
        entries = list(directory.iterdir())
    except FileNotFoundError:
        return []
    for entry in entries:
        match = NAME_RE.fullmatch(entry.name)
        if not match or not entry.is_file() or entry.is_symlink():
            continue
        created = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        items.append({"name": entry.name, "kind": match.group(2), "sealed": bool(match.group(3)),
                      "key_match": key_matches(entry) if match.group(3) else None,
                      "created": int(created.timestamp()), "size": entry.stat().st_size})
    items.sort(key=lambda item: item["name"], reverse=True)
    return items


def backup_path(name, directory=None):
    """The file for a listed backup name; raises for anything else."""
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise BackupError("invalid backup name")
    path = (Path(directory) if directory else backup_dir()) / name
    if not path.is_file() or path.is_symlink():
        raise BackupError("backup not found")
    return path


def delete_backup(name, directory=None):
    _remove(backup_path(name, directory))


def prune(kind, keep, directory=None):
    """Keep the newest ``keep`` backups of one kind; return the names removed."""
    removed = []
    for item in [entry for entry in list_backups(directory) if entry["kind"] == kind][max(keep, 0):]:
        _remove((Path(directory) if directory else backup_dir()) / item["name"])
        removed.append(item["name"])
    return removed


def is_sealed(path):
    try:
        with open(path, "rb") as handle:
            return handle.read(4) in (SEALED_MAGIC, SEALED_MAGIC_2)
    except OSError:
        return False


def sealed_key_id(path):
    """The key id a sealed backup names, or None (older format, or not sealed)."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(4 + KEY_ID_LEN)
    except OSError:
        return None
    return head[4:] if head[:4] == SEALED_MAGIC_2 and len(head) == 4 + KEY_ID_LEN else None


def key_matches(path):
    """True/False: sealed to the key now set for backups; None when that cannot be told."""
    wanted, recipient = sealed_key_id(path), read_recipient()
    if wanted is None or recipient is None:
        return None
    return wanted == key_id(recipient)


def _sealed_body(blob):
    """The sealed box inside a sealed backup file, whichever format it has."""
    if blob[:4] == SEALED_MAGIC_2:
        return blob[4 + KEY_ID_LEN:]
    if blob[:4] == SEALED_MAGIC:
        return blob[4:]
    raise BackupError("not a sealed backup")


def open_sealed_file(path, private_key):
    """The plain ``.tar.gz`` bytes inside a sealed backup; BackupError for the wrong key or a damaged file."""
    try:
        with open(path, "rb") as handle:
            blob = handle.read()
        return crypto_box.open_sealed(private_key, _sealed_body(blob), SEAL_AAD)
    except crypto_box.CryptoError:
        raise BackupError("wrong key or damaged backup") from None
    except OSError as exc:
        raise BackupError("cannot read backup") from exc


def validate_archive(path):
    """Check an uploaded or stored archive; return its manifest (None for a sealed one: only its owner can look inside)."""
    if is_sealed(path):
        if Path(path).stat().st_size < 4 + 32 + 12 + 16 + 1:
            raise BackupError("not a valid backup")
        return None
    try:
        with tarfile.open(path, "r:gz") as archive:
            manifest = None
            total = 0
            for member in archive:
                if member.name == MANIFEST:
                    manifest = json.loads(archive.extractfile(member).read(65536).decode("utf-8"))
                    continue
                _check_member(member)
                total += member.size
                if total > MAX_RESTORE_BYTES:
                    raise BackupError("backup too large")
    except (tarfile.TarError, OSError, ValueError, EOFError) as exc:
        raise BackupError("not a valid backup") from exc
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
        raise BackupError("not a valid backup")
    return manifest


def _check_member(member):
    if not (member.isfile() or member.isdir()):
        raise BackupError("unsupported entry in backup")
    name = member.name
    if not name or name.startswith("/") or ".." in Path(name).parts:
        raise BackupError("unsafe path in backup")
    target = Path("/") / name
    if not any(target == prefix or prefix in target.parents for prefix in allowed_prefixes()) \
            and not _system_file_allowed(target):
        raise BackupError("path outside configuration: " + name)


def _system_file_allowed(target):
    for directory, pattern in SYSTEM_GLOBS:
        base = Path(directory)
        if base in target.parents and fnmatch.fnmatchcase(target.relative_to(base).parts[0], pattern):
            return True
    return False


def restore(path, directory=None, private_key=None):
    """Put a backup's files back. Takes a ``pre-restore`` backup first.

    A sealed backup needs the private key it was sealed for.
    """
    plain = None
    if is_sealed(path):
        if private_key is None:
            raise BackupError("this backup is sealed; its private key is needed")
        descriptor, plain = tempfile.mkstemp(prefix=".unsealed-", dir=Path(path).parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(open_sealed_file(path, private_key))
            os.chmod(plain, 0o600)
            return _restore_plain(plain, directory)
        finally:
            _remove(plain)
    return _restore_plain(path, directory)


def _restore_plain(path, directory):
    manifest = validate_archive(path)
    before = create_backup("pre-restore", directory)
    count = 0
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            if member.name == MANIFEST:
                continue
            target = Path("/") / member.name
            if target == release_trust.pinned_path(state_paths.state_dir()):
                # The key that signs upgrades is pinned on this host; a backup (which may have
                # come from anywhere) must not be able to swap it for another.
                continue
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                os.chmod(target, member.mode & 0o777)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix=".restore-", dir=target.parent)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    source = archive.extractfile(member)
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
                os.chmod(temporary, member.mode & 0o777)
                os.replace(temporary, target)
            except BaseException:
                _remove(temporary)
                raise
            count += 1
    return {"restored": count, "before": before, "version": manifest.get("version", "")}


def _version_tuple(text):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(text).strip())
    return tuple(int(part) for part in match.groups()) if match else None


def inspect(path, private_key=None):
    """What restoring ``path`` would do, without doing it.

    A sealed backup can only be looked into with its private key; without one only what its
    header says (whether it is sealed to the current key) is known. Raises BackupError for a
    backup that is damaged, unsafe or sealed to another key than ``private_key``.
    """
    path = Path(path)
    sealed = is_sealed(path)
    info = {"sealed": sealed, "readable": False, "key_match": key_matches(path) if sealed else None,
            "size": path.stat().st_size}
    if sealed and private_key is None:
        return info
    plain = path
    unsealed = None
    try:
        if sealed:
            descriptor, name = tempfile.mkstemp(prefix=".inspect-", dir=path.parent)
            unsealed = Path(name)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(open_sealed_file(path, private_key))
            plain = unsealed
        manifest = validate_archive(plain)
    finally:
        if unsealed is not None:
            _remove(unsealed)
    here = _version_tuple(_version())
    theirs = _version_tuple(manifest.get("version", ""))
    host = str(manifest.get("host", ""))
    info.update({"readable": True, "host": host, "version": str(manifest.get("version", "")),
                 "kind": str(manifest.get("kind", "")), "created": int(manifest.get("created", 0) or 0),
                 "files": int(manifest.get("files", 0) or 0),
                 "same_host": host == socket.gethostname(),
                 "newer": bool(here and theirs and theirs > here)})
    info["risky"] = bool(not info["same_host"] or info["newer"])
    return info


def result_file():
    return state_paths.state_dir() / RESULT_NAME


def write_result(result):
    descriptor, temporary = tempfile.mkstemp(prefix=".result-", dir=result_file().parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False)
        os.replace(temporary, result_file())
    except BaseException:
        _remove(temporary)
        raise


def read_result():
    """The outcome of the last restore, or None."""
    try:
        data = json.loads(result_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("ok"), bool) else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--kind", choices=KINDS, default="manual")
    create.add_argument("--keep", type=int, default=0, help="keep this many of the kind afterwards (0 = all)")
    sub.add_parser("list")
    restore_parser = sub.add_parser("restore")
    restore_parser.add_argument("archive")
    restore_parser.add_argument("--private-key-file", help="file holding the private key of a sealed backup (deleted afterwards)")
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            name = create_backup(args.kind)
            if args.keep > 0:
                prune(args.kind, args.keep)
            print(name)
        elif args.command == "list":
            for item in list_backups():
                print(item["name"], item["size"])
        else:
            key = None
            started = int(time.time())
            if args.private_key_file:
                try:
                    key = parse_key(Path(args.private_key_file).read_text(encoding="ascii"))
                except BackupError as exc:
                    write_result({"ok": False, "time": started, "name": Path(args.archive).name, "error": str(exc)})
                    raise
                finally:
                    _remove(args.private_key_file)
            try:
                done = restore(args.archive, private_key=key)
            except BackupError as exc:
                write_result({"ok": False, "time": started, "name": Path(args.archive).name, "error": str(exc)})
                raise
            write_result({"ok": True, "time": started, "name": Path(args.archive).name, **done})
            print(json.dumps(done))
    except BackupError as exc:
        print("backup failed:", exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
