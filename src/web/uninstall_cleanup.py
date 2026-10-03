#!/usr/bin/env python3
"""Finish a full uninstall without touching other projects' FRP or ports."""

import fcntl
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys

from console_port import read_rows, write_rows
from frp_control import client_names, client_unit, valid_client_name


FRPC_SHA256 = "f79fff8de3089ec711ff8bdd4b73e00dfe491a1c3d754983c8b0f8d58c21b068"
SOURCE_TEMPLATE = Path(__file__).resolve().parents[2] / "deploy/systemd/frpc@.service"
FRPC_DIR = Path("/etc/frp")
FRPC_UNIT = Path("/etc/systemd/system/frpc@.service")
FRPC_BINARY = Path("/usr/local/bin/frpc")
UNITS = ("vps-server-anytls.service", "vps-server-proxy.service",
         "vps-server-frps.service", "vps-server-lucky.service",
         "vps-server-node-meter.service")


class CleanupError(RuntimeError):
    pass


def _run(command, *, run=subprocess.run, capture=False):
    result = run(command, check=False, timeout=60,
                 stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL, text=capture)
    return result


def _instances(directory):
    """Only names accepted by the console and its systemd template."""
    return set(client_names(directory))


def _aliases(directory):
    """Only aliases whose name matches the project's Unicode-name mapping."""
    for path in directory.glob("frpc-u-*.toml"):
        if not path.is_symlink():
            continue
        target = os.readlink(path)
        if "/" in target or not target.startswith("frpc-") or not target.endswith(".toml"):
            continue
        name = target[5:-5]
        if valid_client_name(name) and path.name == client_unit(name).replace("frpc@", "frpc-").replace(".service", ".toml"):
            yield path


def cleanup_frpc(prefix, keep_data, *, directory=FRPC_DIR, unit=FRPC_UNIT,
                 binary=FRPC_BINARY, template=SOURCE_TEMPLATE, run=subprocess.run,
                 require_root=True):
    """Remove this project's FRPC service; purge its configs on full uninstall.

    A changed service template is not ours to remove. The same rule protects
    unrelated FRPC installations that use this host's global paths.
    """
    if require_root and os.geteuid() != 0:
        raise PermissionError("root required")
    prefix, directory, unit, binary, template = map(Path, (prefix, directory, unit, binary, template))
    if directory.is_symlink():
        raise CleanupError("FRPC configuration directory is a symlink")
    marker = prefix / "data/frpc-binary-owned"
    owned_binary = marker.is_file() and marker.read_text().strip() == FRPC_SHA256
    matching_unit = (unit.is_file() and not unit.is_symlink() and
                     template.is_file() and unit.read_bytes() == template.read_bytes())
    if not unit.exists() and not owned_binary:
        if not directory.is_dir() or (not _instances(directory) and
                not any(directory.glob(".deleted-frpc-*.toml")) and
                not any(_aliases(directory))):
            return None
    if unit.exists() and not matching_unit:
        if owned_binary:
            raise CleanupError("FRPC service template changed")
        return False
    if not matching_unit and not owned_binary:
        return False
    if binary.exists() and (binary.is_symlink() or not binary.is_file() or
            hashlib.sha256(binary.read_bytes()).hexdigest() != FRPC_SHA256):
        raise CleanupError("FRPC binary changed")

    names = _instances(directory)
    services = {client_unit(name) for name in names}
    listed = _run(["systemctl", "list-units", "--all", "--plain", "--no-legend",
                   "frpc@*.service"], run=run, capture=True)
    if listed.returncode:
        raise CleanupError("could not enumerate FRPC instances")
    for line in listed.stdout.splitlines():
        fields = line.split()
        candidate = fields[1] if fields and fields[0] == "●" and len(fields) > 1 else fields[0] if fields else ""
        if re.fullmatch(r"frpc@[A-Za-z0-9_-]+\.service", candidate):
            services.add(candidate)
    for service in sorted(services):
        _run(["systemctl", "disable", "--now", service], run=run)
        if _run(["systemctl", "is-active", "--quiet", service], run=run).returncode == 0:
            raise CleanupError("FRPC instance remains active")

    if matching_unit:
        unit.unlink()
        if _run(["systemctl", "daemon-reload"], run=run).returncode:
            unit.write_bytes(template.read_bytes())
            _run(["systemctl", "daemon-reload"], run=run)
            raise CleanupError("could not reload systemd after FRPC removal")

    if binary.is_file():
        binary.unlink()
        marker.unlink(missing_ok=True)

    if not keep_data and directory.is_dir():
        for name in names:
            path = directory / f"frpc-{name}.toml"
            if path.is_file() and not path.is_symlink():
                path.unlink()
        for alias in _aliases(directory):
            alias.unlink()
        for path in directory.glob(".deleted-frpc-*.toml"):
            if path.is_file() and not path.is_symlink():
                path.unlink()
        try:
            directory.rmdir()
        except OSError:
            pass  # Keep unrelated files in /etc/frp.
    return True


def _project_owner(owner, service_name):
    return (owner == service_name or owner == "vps-server" or
            owner.startswith("vps-server-") or owner.startswith("vps-server "))


def cleanup_ports(prefix, service_name, *, registry=None, run=subprocess.run,
                  require_root=True, check_only=False,
                  frpc_unit=FRPC_UNIT, template=SOURCE_TEMPLATE,
                  preserve_frpc=False):
    """Release only this project's rows after every managed service stops."""
    if require_root and os.geteuid() != 0:
        raise PermissionError("root required")
    prefix = Path(prefix)
    registry = Path(registry) if registry is not None else prefix.parent / "PORTS.md"
    if registry.is_symlink():
        raise CleanupError("port registry is a symlink")
    if not registry.exists():
        return 0
    if not re.fullmatch(r"[A-Za-z0-9@_.-]+", service_name):
        raise CleanupError("invalid service name")
    rows, _ = read_rows(registry)
    if check_only:
        return sum(_project_owner(row[1], service_name) for row in rows)
    frpc_unit, template = Path(frpc_unit), Path(template)
    foreign_frpc = (preserve_frpc or frpc_unit.is_symlink() or
                    (frpc_unit.is_file() and
                     (not template.is_file() or frpc_unit.read_bytes() != template.read_bytes())))
    for service in (service_name + ".service", *UNITS):
        if _run(["systemctl", "is-active", "--quiet", service], run=run).returncode == 0:
            raise CleanupError("managed service remains active")
    lock_path = registry.parent / ".ports.lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows, _ = read_rows(registry)
        kept = [row for row in rows if not _project_owner(row[1], service_name) or
                (foreign_frpc and row[1].startswith("vps-server frpc "))]
        if len(kept) != len(rows):
            write_rows(registry, kept)
        return len(rows) - len(kept)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if (len(argv) not in (4, 5) or argv[0] not in ("check-ports", "frpc", "ports") or
            argv[2] not in ("0", "1") or (len(argv) == 5 and
            (argv[0] != "ports" or argv[4] not in ("removed", "unowned", "absent")))):
        return 2
    action, prefix, keep, service = argv[:4]
    try:
        if action == "frpc":
            outcome = cleanup_frpc(prefix, keep == "1")
            print("removed" if outcome is True else "unowned" if outcome is False else "absent")
        else:
            print(cleanup_ports(prefix, service, check_only=action == "check-ports",
                                preserve_frpc=len(argv) == 5 and argv[4] == "unowned"))
    except (CleanupError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"uninstall cleanup failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
