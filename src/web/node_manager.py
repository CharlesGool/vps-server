"""Offline-injectable, journaled legacy-to-single-service cutover.

No host entrypoint or systemctl implementation is provided in this phase. The caller
must explicitly supply a trusted backend and paths; never include exception details
or captured config in user-facing error reports.
"""

import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import uuid

from src.web.node_inventory import import_legacy, render_config


class CutoverError(RuntimeError):
    """Cutover failed; the original state was recovered."""


class DegradedCutover(CutoverError):
    """DEGRADED: recovery failed; journal retained for retry."""


# Backend protocol (injected): status(unit) -> (active, enabled),
# check(binary, staged_config), reload(), start(unit), stop(unit),
# enable(unit), disable(unit), healthy(unit, ports) -> bool.
# healthy must verify both the unit and all expected listeners, not only systemd.
OLD_UNITS = {"anytls": "vps-server-anytls.service", "proxy": "vps-server-proxy.service"}
NEW_UNIT = "vps-server-nodes.service"


def _read(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise CutoverError("unsafe installed file")
    return path.read_bytes()


def _sync_dir(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _stage(path, data):
    fd, name = tempfile.mkstemp(prefix=".nodes-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        return Path(name)
    except BaseException:
        os.unlink(name)
        raise


def _replace(path, data):
    if data is None:
        path.unlink(missing_ok=True)
        _sync_dir(path.parent)
    else:
        staged = _stage(path, data)
        try:
            os.replace(staged, path)
            _sync_dir(path.parent)
        finally:
            staged.unlink(missing_ok=True)


def _blob(data):
    return None if data is None else base64.b64encode(data).decode("ascii")


def _unblob(data):
    return None if data is None else base64.b64decode(data, validate=True)


def _set_status(backend, unit, wanted):
    active, enabled = backend.status(unit)
    if active and not wanted[0]:
        backend.stop(unit)
    elif wanted[0] and not active:
        backend.start(unit)
    if enabled != wanted[1]:
        (backend.enable if wanted[1] else backend.disable)(unit)
    if tuple(backend.status(unit)) != tuple(wanted):
        raise DegradedCutover("DEGRADED: service state not restored")


def _recover(paths, backend, journal):
    """Replay original bytes and statuses; repeatable after abrupt process death."""
    originals = journal["files"]
    units = journal["units"]
    if backend.status(NEW_UNIT)[0]:
        backend.stop(NEW_UNIT)
    for key in ("state", "config", "unit"):
        _replace(paths[key], _unblob(originals[key]))
    backend.reload()
    for unit in (NEW_UNIT, *OLD_UNITS.values()):
        _set_status(backend, unit, units[unit])
    for key in ("state", "config", "unit"):
        if _read(paths[key]) != _unblob(originals[key]):
            raise DegradedCutover("DEGRADED: file not restored")


def cutover(*, paths, backend, unit_bytes, binary, binary_sha256, require_root=True):
    """Explicit injectable cutover. Returns inventory; no host backend is included.

    paths contains lock, journal, state, config, unit, anytls, proxy. Directories
    must already exist in trusted root-only locations. The binary is checked
    against a trusted SHA-256 before the injected backend runs its config check.
    A retained journal is recovered before a retry; changed sources fail closed.
    """
    if require_root and os.geteuid() != 0:
        raise PermissionError("cutover requires root")
    paths = {key: Path(paths[key]) for key in
             ("lock", "journal", "state", "config", "unit", "anytls", "proxy")}
    if paths["journal"].parent != paths["state"].parent or paths["state"].parent != paths["config"].parent:
        raise CutoverError("state paths must share a directory")
    for directory in {p.parent for p in paths.values()}:
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or (require_root and (info.st_uid != 0 or info.st_mode & 0o022)):
            raise CutoverError("unsafe directory")
    if not isinstance(binary_sha256, str) or len(binary_sha256) != 64:
        raise CutoverError("missing trusted binary digest")
    binary = Path(binary)
    info = binary.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not info.st_mode & 0o111 or (require_root and (info.st_uid != 0 or info.st_mode & 0o022)):
        raise CutoverError("unsafe binary")
    if hashlib.sha256(binary.read_bytes()).hexdigest() != binary_sha256:
        raise CutoverError("binary digest mismatch")
    # The lock is shared with node_config and old installer/reset paths.
    with open(paths["lock"], "a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        old_journal = _read(paths["journal"])
        previous = None
        if old_journal is not None:
            try:
                previous = json.loads(old_journal)
                if previous["version"] != 1 or previous["phase"] not in ("pending", "recovered"):
                    raise ValueError()
                if previous["phase"] == "pending":
                    _recover(paths, backend, previous)
                    previous["phase"] = "recovered"
                    _replace(paths["journal"], json.dumps(previous).encode())
            except BaseException as exc:
                raise DegradedCutover("DEGRADED: journal recovery failed") from exc
        originals = {key: _read(paths[key]) for key in ("state", "config", "unit")}
        if any(value is not None for value in originals.values()):
            raise CutoverError("single-service files already present")
        sources = {key: _read(paths[key]) for key in OLD_UNITS}
        if previous is not None and {key: _blob(value) for key, value in sources.items()} != previous["sources"]:
            raise CutoverError("legacy snapshot changed since recovery")
        statuses = {unit: tuple(backend.status(unit)) for unit in (NEW_UNIT, *OLD_UNITS.values())}
        if statuses[NEW_UNIT] != (False, False) or not any(statuses[u][0] for u in OLD_UNITS.values()):
            raise CutoverError("unexpected service state")
        if previous is not None and {u: list(v) for u, v in statuses.items()} != previous["units"]:
            raise CutoverError("legacy service state changed since recovery")
        legacy = {module: statuses[unit] for module, unit in OLD_UNITS.items()}
        boot_enabled = any(enabled for _, enabled in legacy.values())
        if any(not active and enabled for active, enabled in legacy.values()) or any(
                active and not enabled and any(other_enabled for other_module, (_, other_enabled) in legacy.items()
                                           if other_module != module)
                for module, (active, enabled) in legacy.items()):
            raise CutoverError("legacy active and boot-enabled states cannot be preserved by one service")
        namespace = previous["namespace"] if previous else str(uuid.uuid4())
        inventory = import_legacy(sources["anytls"], sources["proxy"], migration_namespace=namespace)
        for node in inventory["nodes"]:
            module = "anytls" if node["protocol"] == "anytls" else "proxy"
            node["enabled"] = legacy[module][0]
        config = render_config(inventory)
        ports = [node["port"] for node in inventory["nodes"] if node["enabled"]]
        if not ports or not isinstance(unit_bytes, bytes) or not unit_bytes:
            raise CutoverError("missing listeners or unit")
        record = {"version": 1, "phase": "pending", "namespace": namespace,
                  "sources": {k: _blob(v) for k, v in sources.items()},
                  "files": {k: _blob(v) for k, v in originals.items()},
                  "units": {u: list(v) for u, v in statuses.items()}}
        _replace(paths["journal"], json.dumps(record).encode())
        staged = {}
        try:
            staged["state"] = _stage(paths["state"], json.dumps(inventory, ensure_ascii=False).encode())
            staged["config"] = _stage(paths["config"], json.dumps(config, ensure_ascii=False).encode())
            staged["unit"] = _stage(paths["unit"], unit_bytes)
            backend.check(binary, staged["config"])
            for key in ("state", "config", "unit"):
                os.replace(staged[key], paths[key])
                _sync_dir(paths[key].parent)
            backend.reload()
            for unit in OLD_UNITS.values():
                if statuses[unit][0]:
                    backend.stop(unit)
            backend.start(NEW_UNIT)
            if not backend.status(NEW_UNIT)[0] or not backend.healthy(NEW_UNIT, ports):
                raise CutoverError("new service health check failed")
            for unit in OLD_UNITS.values():
                if statuses[unit][1]:
                    backend.disable(unit)
            if boot_enabled:
                backend.enable(NEW_UNIT)
            if backend.status(NEW_UNIT) != (True, boot_enabled):
                raise CutoverError("new service state check failed")
            paths["journal"].unlink()
            _sync_dir(paths["journal"].parent)
            return inventory
        except BaseException as exc:
            try:
                _recover(paths, backend, record)
                record["phase"] = "recovered"
                _replace(paths["journal"], json.dumps(record).encode())
            except BaseException as recovery_error:
                raise DegradedCutover("DEGRADED: recovery failed; journal retained") from recovery_error
            raise CutoverError("cutover failed; original state restored") from exc
        finally:
            for stage in staged.values():
                stage.unlink(missing_ok=True)
