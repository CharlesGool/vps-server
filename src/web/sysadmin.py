#!/usr/bin/env python3
"""Privileged system changes the console asks for: host name, package upgrades, file operations.

The console runs with ProtectSystem=strict and cannot write outside its own
directories, so it starts this helper with ``systemd-run`` (outside the
sandbox) and passes one JSON request on standard input:

    systemd-run --wait --pipe --collect /usr/bin/python3 sysadmin.py request < request.json

The helper prints one JSON line: ``{"ok": true, ...}`` or ``{"ok": false, "error": "<code>"}``.
Only the actions below exist; there is no way to run an arbitrary command.

``apt-upgrade <log>`` is the exception: the console starts it as its own
transient unit (it runs for minutes) and reads the log file.
"""

import functools
import grp
import json
import os
import pwd
import re
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

HOSTNAME_RE = re.compile(r"^(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
                         r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")
# Paths the file manager never deletes, moves or renames (their contents are fine), nor changes recursively.
PROTECTED = {"/", "/bin", "/boot", "/dev", "/etc", "/home", "/lib", "/lib32", "/lib64", "/libx32", "/media",
             "/mnt", "/opt", "/proc", "/root", "/run", "/sbin", "/srv", "/sys", "/tmp", "/usr", "/var"}
# Kernel and device trees: nothing is written there.
NO_WRITE = ("/proc", "/sys", "/dev")
# Where the data key lives (secure_store.DEFAULT_KEY_FILE); see console_dirs().
KEY_DIR = "/etc/vps-server"
NAME_RE = re.compile(r"^[^/\0]{1,255}$")
USER_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,31}$")
# Free space an extraction leaves on the destination's file system, at least.
EXTRACT_RESERVE = 16 << 20
TAR_FILTER_ERRORS = (tarfile.FilterError,) if hasattr(tarfile, "FilterError") else ()


class Refused(Exception):
    """A request the helper will not carry out; the message is the error code."""


def _inside(path, roots):
    return any(path == root or path.startswith(root.rstrip("/") + "/") for root in roots)


def _resolved(path):
    """``path`` with its parent folders' symbolic links resolved (the last part stays as it is)."""
    if path == "/":
        return path
    return os.path.join(os.path.realpath(os.path.dirname(path)), os.path.basename(path))


@functools.lru_cache(maxsize=1)
def key_dirs():
    """The data key's folder: view-only in the file manager.

    Deleting or overwriting ``/etc/vps-server/data.key`` makes every encrypted
    state file unreadable, so nothing inside it is written, deleted or moved.
    """
    return tuple(sorted({os.path.normpath(KEY_DIR), os.path.normpath(os.path.realpath(KEY_DIR))}))


@functools.lru_cache(maxsize=1)
def console_dirs():
    """The console's own key, state and program folders.

    None of them, nor a folder that holds one, is deleted, moved or renamed, and a
    recursive change does not reach into them. Files inside the state and program
    folders (``.env``, say) may still be edited; the key folder is view-only (key_dirs()).
    """
    found = {KEY_DIR}
    try:
        import state_paths
        found.update({str(state_paths.state_dir()), str(state_paths.data_dir())})
    except (ImportError, OSError, ValueError):
        found.add("/var/lib/vps-server")
    code = Path(__file__).resolve().parent  # <prefix>/src/web when installed
    found.add(str(code.parent.parent if code.parent.name == "src" else code))
    found |= {os.path.realpath(path) for path in found}
    return tuple(sorted(os.path.normpath(path) for path in found if os.path.normpath(path) != "/"))


def _path(value, *, write=True):
    if not isinstance(value, str) or not value.startswith("/") or "\0" in value or len(value) > 4096:
        raise Refused("path_invalid")
    path = os.path.normpath(value)
    if path.startswith("//"):
        path = "/" + path.lstrip("/")
    if write and any(_inside(candidate, NO_WRITE) or _inside(candidate, key_dirs())
                     for candidate in (path, _resolved(path))):
        raise Refused("path_protected")
    return path


def _changeable(path):
    """A path that may itself be deleted, moved or renamed."""
    for candidate in (path, _resolved(path)):
        if candidate in PROTECTED or any(_inside(own, (candidate,)) for own in console_dirs()):
            raise Refused("path_protected")
    return path


def _absent(path):
    if os.path.lexists(path):
        raise Refused("exists")


def _staging(value, staging_root):
    path = _path(value, write=False)
    root = os.path.normpath(staging_root)
    if not path.startswith(root + "/") or os.path.islink(path) or not os.path.isfile(path):
        raise Refused("staging_invalid")
    return path


def _target_in(directory, name):
    if not isinstance(name, str) or not NAME_RE.match(name) or name in (".", ".."):
        raise Refused("name_invalid")
    return os.path.join(directory, name)


# -- host name -------------------------------------------------------------------

def set_hostname(request):
    name = request.get("name")
    if not isinstance(name, str) or not HOSTNAME_RE.match(name):
        raise Refused("hostname_invalid")
    old = os.uname().nodename
    result = subprocess.run(["hostnamectl", "set-hostname", name], capture_output=True, text=True, timeout=30,
                            check=False)
    if result.returncode:
        raise Refused("hostname_failed")
    hosts = Path("/etc/hosts")
    try:
        lines = hosts.read_text().splitlines()
    except OSError:
        lines = []
    changed = rename_in_hosts(lines, old, name)
    _write_atomic(hosts, ("\n".join(changed) + "\n").encode(), keep=hosts)
    return {"old": old, "name": name}


def rename_in_hosts(lines, old, name):
    """/etc/hosts with ``old`` replaced by ``name`` wherever it is a whole entry.

    Comments, localhost lines and other aliases stay as they are. Only when the
    old name appears nowhere is a ``127.0.1.1 <name>`` line added (the Debian
    convention), so the host can still resolve its own name.
    """
    old_re = re.compile(r"(?<![A-Za-z0-9.-])" + re.escape(old) + r"(?![A-Za-z0-9.-])") if old else None
    changed, found = [], False
    for line in lines:
        content, hash_mark, comment = line.partition("#")
        fields = content.split()
        if old_re and old != "localhost" and len(fields) > 1 and old_re.search(content):
            line = old_re.sub(name, content) + hash_mark + comment
            found = True
        elif len(fields) > 1 and name in fields[1:]:
            found = True
        changed.append(line)
    if not found:
        changed.append("127.0.1.1\t" + name)
    return changed


def _write_atomic(path, data, keep=None):
    path = Path(path)
    temporary = path.with_name(f".{path.name}.vps-server-{os.getpid()}")
    with open(temporary, "wb") as handle:
        handle.write(data)
    if keep is not None and keep.exists():
        info = keep.stat()
        os.chmod(temporary, stat.S_IMODE(info.st_mode))
        os.chown(temporary, info.st_uid, info.st_gid)
    os.replace(temporary, path)


# -- packages ---------------------------------------------------------------------

def apt_upgrade(log_path):
    """apt-get update then upgrade, every line of output into ``log_path``; exit status as the result."""
    env = dict(os.environ, DEBIAN_FRONTEND="noninteractive", APT_LISTCHANGES_FRONTEND="none")
    with open(log_path, "w", buffering=1) as log:
        for command in (["apt-get", "update"],
                        ["apt-get", "-y", "-o", "Dpkg::Options::=--force-confdef",
                         "-o", "Dpkg::Options::=--force-confold", "upgrade"]):
            log.write("$ " + " ".join(command) + "\n")
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env, check=False,
                                    stdin=subprocess.DEVNULL)
            if result.returncode:
                log.write(f"exit {result.returncode}\n")
                return result.returncode
        log.write("exit 0\n")
    return 0


def apt_refresh(_request):
    """apt-get update, so the list of upgradable packages is current."""
    env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
    try:
        result = subprocess.run(["apt-get", "-q", "update"], capture_output=True, text=True, env=env,
                                timeout=300, check=False, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        raise Refused("apt_failed") from None
    if result.returncode:
        raise Refused("apt_failed")
    return {}


# -- files -------------------------------------------------------------------------

def fs_mkdir(request):
    path = _path(request.get("path"))
    _absent(path)
    os.mkdir(path, 0o755)
    return {"path": path}


def fs_touch(request):
    path = _path(request.get("path"))
    _absent(path)
    with open(path, "x"):
        pass
    os.chmod(path, 0o644)
    return {"path": path}


def fs_rename(request):
    source = _changeable(_path(request.get("path")))
    target = _target_in(os.path.dirname(source), request.get("name"))
    _absent(target)
    os.rename(source, target)
    return {"path": target}


def _into(request, *, write=True):
    destination = _path(request.get("destination"))
    if not os.path.isdir(destination):
        raise Refused("destination_invalid")
    paths = request.get("paths")
    if not isinstance(paths, list) or not 1 <= len(paths) <= 200:
        raise Refused("path_invalid")
    return destination, [_path(path, write=write) for path in paths]


def fs_move(request):
    destination, sources = _into(request)
    moved = []
    for source in sources:
        _changeable(source)
        target = os.path.join(destination, os.path.basename(source))
        if destination == source or destination.startswith(source + "/"):
            raise Refused("destination_invalid")
        _absent(target)
        shutil.move(source, target)
        moved.append(target)
    return {"paths": moved}


def fs_copy(request):
    # The key folder is view-only, but copying out of it (a backup, say) is fine.
    destination, sources = _into(request, write=False)
    for source in sources:
        if _inside(source, NO_WRITE):
            raise Refused("path_protected")
    copied = []
    for source in sources:
        target = os.path.join(destination, os.path.basename(source))
        if destination == source or destination.startswith(source + "/"):
            raise Refused("destination_invalid")
        _absent(target)
        if os.path.isdir(source) and not os.path.islink(source):
            shutil.copytree(source, target, symlinks=True)
        else:
            shutil.copy2(source, target, follow_symlinks=False)
        copied.append(target)
    return {"paths": copied}


def fs_delete(request):
    paths = request.get("paths")
    if not isinstance(paths, list) or not 1 <= len(paths) <= 200:
        raise Refused("path_invalid")
    targets = [_changeable(_path(path)) for path in paths]
    for target in targets:
        if os.path.isdir(target) and not os.path.islink(target):
            shutil.rmtree(target)
        elif os.path.lexists(target):
            os.unlink(target)
    return {"deleted": len(targets)}


def _walk(path, recursive):
    yield path
    if recursive and os.path.isdir(path) and not os.path.islink(path):
        for root, dirs, files in os.walk(path):
            for name in dirs + files:
                yield os.path.join(root, name)


def _changeable_below(path, device):
    """Whether something met while walking a tree may be changed: same file system, not protected."""
    if _inside(path, NO_WRITE) or _inside(path, console_dirs()):
        return False
    try:
        return os.lstat(path).st_dev == device
    except OSError:
        return False


def _tree(path, recursive):
    """``path`` and, when ``recursive``, what lies below it that a recursive change may touch.

    Links are listed but never followed. Other file systems mounted inside (and
    everything on them), the kernel trees and the console's own folders are skipped.
    """
    yield path
    if not recursive or os.path.islink(path) or not os.path.isdir(path):
        return
    device = os.lstat(path).st_dev
    for root, dirs, files in os.walk(path):
        dirs[:] = [name for name in dirs if _changeable_below(os.path.join(root, name), device)]
        for name in dirs + [name for name in files if _changeable_below(os.path.join(root, name), device)]:
            yield os.path.join(root, name)


def _recursive(request, path):
    """Whether a chmod/chown request is recursive; never for a system folder such as /usr."""
    recursive = bool(request.get("recursive"))
    if recursive and (path in PROTECTED or _resolved(path) in PROTECTED):
        raise Refused("recursive_protected")
    return recursive


def fs_chmod(request):
    path = _path(request.get("path"))
    mode = request.get("mode")
    if not isinstance(mode, str) or not re.fullmatch(r"[0-7]{3,4}", mode):
        raise Refused("mode_invalid")
    mode = int(mode, 8)
    recursive = _recursive(request, path)
    # Recursively, folders get the search (x) bit wherever they get the read bit, like chmod's
    # "X": 644 leaves files at 644 and folders at 755, so the tree can still be entered.
    folder_mode = mode | ((mode & 0o444) >> 2) if recursive else mode
    changed = 0
    for item in _tree(path, recursive):
        info = os.lstat(item)
        if stat.S_ISLNK(info.st_mode):
            continue
        os.chmod(item, folder_mode if stat.S_ISDIR(info.st_mode) else mode)
        changed += 1
    return {"path": path, "changed": changed}


def fs_chown(request):
    path = _path(request.get("path"))
    user, group = request.get("user"), request.get("group")
    try:
        uid = pwd.getpwnam(user).pw_uid if isinstance(user, str) and USER_RE.match(user) else None
        gid = grp.getgrnam(group).gr_gid if isinstance(group, str) and USER_RE.match(group) else None
    except KeyError:
        raise Refused("owner_invalid") from None
    if uid is None or gid is None:
        raise Refused("owner_invalid")
    changed = 0
    for item in _tree(path, _recursive(request, path)):
        info = os.lstat(item)
        # Linux clears set-user-ID, set-group-ID and file capabilities on every chown, even by
        # root and even to the same owner: leave what already belongs to uid:gid untouched.
        if (info.st_uid, info.st_gid) != (uid, gid):
            os.lchown(item, uid, gid)
            changed += 1
    return {"path": path, "changed": changed}


def fs_write(request, staging_root):
    """Put an uploaded or edited file (a staging copy) at ``path``."""
    source = _staging(request.get("staging"), staging_root)
    path = _path(request.get("path"))
    existing = os.path.lexists(path)
    if existing and not request.get("overwrite"):
        raise Refused("exists")
    if existing and (os.path.islink(path) or not os.path.isfile(path)):
        raise Refused("not_a_file")
    if not os.path.isdir(os.path.dirname(path)):
        raise Refused("destination_invalid")
    temporary = os.path.join(os.path.dirname(path), f".{os.path.basename(path)}.vps-server-{os.getpid()}")
    try:
        shutil.copyfile(source, temporary)
        if existing:
            info = os.stat(path)
            os.chmod(temporary, stat.S_IMODE(info.st_mode))
            os.chown(temporary, info.st_uid, info.st_gid)
        else:
            os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    except BaseException:  # also a stop on timeout (SIGTERM): no half-written copy is left behind
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    os.unlink(source)
    return {"path": path}


def _safe_member(destination, name):
    """Where member ``name`` lands; it must stay inside ``destination``, also past existing links."""
    target = os.path.normpath(os.path.join(destination, name))
    if not _inside(target, (destination,)):
        raise Refused("archive_unsafe")
    if target != destination and not _inside(os.path.realpath(os.path.dirname(target)),
                                             (os.path.realpath(destination),)):
        raise Refused("archive_unsafe")
    return target


def _tar_filter():
    """Whether tarfile has the "data" extraction filter (Python 3.12, 3.11.4, 3.10.12, 3.9.17 and later)."""
    return hasattr(tarfile, "data_filter")


def _room(destination, size, count):
    """Refuse an extraction whose declared size would (nearly) fill the destination's file system."""
    usage = os.statvfs(destination)
    needed = size + count * usage.f_frsize + max(size // 20, EXTRACT_RESERVE)
    if needed > usage.f_bavail * usage.f_frsize or (usage.f_files and count > usage.f_favail):
        raise Refused("no_room")


def fs_extract(request):
    archive = _path(request.get("path"), write=False)
    destination = _path(request.get("destination"))
    if not os.path.isdir(destination):
        raise Refused("destination_invalid")
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            members = bundle.infolist()
            for info in members:
                # zipfile drops "..", "." and empty parts on its own; refuse instead, so the
                # place checked here is the place it writes to.
                if info.filename.startswith("/") or ".." in info.filename.split("/"):
                    raise Refused("archive_unsafe")
                target = _safe_member(destination, info.filename)
                if os.path.lexists(target) and not info.is_dir():
                    raise Refused("exists")
            # The sizes are binding: zipfile stops reading a member at its declared size.
            _room(destination, sum(info.file_size for info in members), len(members))
            bundle.extractall(destination)
    elif tarfile.is_tarfile(archive):
        with tarfile.open(archive) as bundle:
            members = bundle.getmembers()
            filtered = _tar_filter()
            for member in members:
                target = _safe_member(destination, member.name)
                if member.issym() or member.islnk():
                    # Without the data filter nothing checks where a chain of links really points
                    # (d1 -> ., d1/d2 -> .., d1/d2/x writes outside), so archives with links are refused.
                    if not filtered:
                        raise Refused("archive_links")
                    base = os.path.dirname(member.name) if member.issym() else ""
                    _safe_member(destination, os.path.join(base, member.linkname))
                if member.isdev():
                    raise Refused("archive_unsafe")
                if os.path.lexists(target) and not member.isdir():
                    raise Refused("exists")
            _room(destination, sum(member.size for member in members if member.isreg()), len(members))
            if filtered:
                try:
                    bundle.extractall(destination, filter="data")
                except TAR_FILTER_ERRORS:
                    raise Refused("archive_unsafe") from None
            else:
                for member in members:
                    # Roughly what the data filter does: no set-ID bits, no group/other write,
                    # owned by root rather than by whatever user the archive names.
                    member.mode &= 0o755
                    member.uid = member.gid = 0
                    member.uname = member.gname = "root"
                bundle.extractall(destination, members=members)
    else:
        raise Refused("archive_invalid")
    return {"path": destination}


def fs_compress(request):
    paths = request.get("paths")
    if not isinstance(paths, list) or not 1 <= len(paths) <= 200:
        raise Refused("path_invalid")
    sources = [_path(path, write=False) for path in paths]
    target = _path(request.get("target"))
    kind = request.get("format")
    _absent(target)
    base = os.path.dirname(sources[0])
    if kind == "zip":
        with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED) as bundle:
            for source in sources:
                for item in _walk(source, True):
                    arcname = os.path.relpath(item, base)
                    if os.path.islink(item):
                        continue
                    bundle.write(item, arcname)
    elif kind == "tar.gz":
        with tarfile.open(target, "x:gz") as bundle:
            for source in sources:
                bundle.add(source, arcname=os.path.relpath(source, base))
    else:
        raise Refused("format_invalid")
    os.chmod(target, 0o644)
    return {"path": target}


ACTIONS = {"hostname": set_hostname, "apt-refresh": apt_refresh, "mkdir": fs_mkdir, "touch": fs_touch, "rename": fs_rename,
           "move": fs_move, "copy": fs_copy, "delete": fs_delete, "chmod": fs_chmod, "chown": fs_chown,
           "extract": fs_extract, "compress": fs_compress}


def handle(request, staging_root):
    if not isinstance(request, dict):
        raise Refused("invalid_request")
    action = request.get("action")
    if action == "write":
        return fs_write(request, staging_root)
    handler = ACTIONS.get(action)
    if handler is None:
        raise Refused("invalid_request")
    return handler(request)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if os.geteuid() != 0:
        print(json.dumps({"ok": False, "error": "not_root"}))
        return 1
    if len(argv) == 2 and argv[0] == "apt-upgrade":
        return apt_upgrade(argv[1])
    if len(argv) != 2 or argv[0] != "request":
        print("usage: sysadmin.py request <staging dir> < request.json | apt-upgrade <log>", file=sys.stderr)
        return 2
    # The console stops this unit when a request outlasts its time; exit through the clean-up paths.
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(128 + signum))
    try:
        request = json.loads(sys.stdin.read(1 << 20))
        result = {"ok": True, **handle(request, argv[1])}
    except Refused as refused:
        result = {"ok": False, "error": str(refused)}
    except FileNotFoundError:
        result = {"ok": False, "error": "not_found"}
    except FileExistsError:
        result = {"ok": False, "error": "exists"}
    except (PermissionError, IsADirectoryError, NotADirectoryError, OSError, ValueError,
            tarfile.TarError, zipfile.BadZipFile) as error:
        result = {"ok": False, "error": "failed", "detail": type(error).__name__}
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
