"""Plan the move from split AnyTLS/proxy services to one proxy service.

The planner does not mutate the host. The installer applies its result only
after preserving the legacy files and checking the complete sing-box config.
"""

import copy
import argparse
import fcntl
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
import uuid

try:
    from .node_state import _read_json, read_inventory
    from .state_paths import data_dir as state_data_dir
except ImportError:
    from node_state import _read_json, read_inventory
    from state_paths import data_dir as state_data_dir

try:
    from .node_inventory import InvalidInventory, _base, _document, import_legacy, migrate_inventory, validate_inventory
except ImportError:  # Installed helpers are copied into one flat directory.
    from node_inventory import InvalidInventory, _base, _document, import_legacy, migrate_inventory, validate_inventory


LEGACY_CERT_ROOT = Path("/etc/vps-server-anytls")
PROXY_ROOT = Path("/etc/vps-server-proxy")


def unified_plan(anytls_document, proxy_document, existing=None,
                 *, legacy_cert_root=LEGACY_CERT_ROOT, proxy_root=PROXY_ROOT):
    """Return (inventory, merged config, certificate copies) without writes."""
    if anytls_document is None:
        raise InvalidInventory("no legacy AnyTLS configuration")
    documents = {"anytls": anytls_document, "proxy": proxy_document}
    documents = {name: _document(value) for name, value in documents.items() if value is not None}
    bases = [_base(document) for document in documents.values()]
    if any(base != bases[0] for base in bases[1:]):
        raise InvalidInventory("legacy service base configurations differ")
    if existing is None:
        inventory = import_legacy(anytls_document, proxy_document,
                                  migration_namespace=str(uuid.uuid4()))
    else:
        inventory = migrate_inventory(copy.deepcopy(existing))
        validate_inventory(inventory)
        for name, document in documents.items():
            expected = [node["inbound"] for node in inventory["nodes"] if node["enabled"] and
                        (node["protocol"] == "anytls") == (name == "anytls")]
            if not isinstance(document, dict) or document.get("inbounds") != expected:
                raise InvalidInventory("legacy configuration differs from node inventory")
    old_root = Path(legacy_cert_root).resolve(strict=False)
    new_root = Path(proxy_root).resolve(strict=False)
    copies = []
    for node in inventory["nodes"]:
        if node["protocol"] != "anytls":
            continue
        tls = node["inbound"]["tls"]
        for field in ("certificate_path", "key_path"):
            source = Path(tls[field])
            resolved = source.resolve(strict=False)
            if old_root not in resolved.parents:
                continue
            destination = new_root / "certs" / node["id"] / source.name
            tls[field] = str(destination)
            copies.append((source, destination))
    validate_inventory(inventory)
    merged = copy.deepcopy(bases[0])
    merged["inbounds"] = [copy.deepcopy(node["inbound"]) for node in inventory["nodes"]
                          if node["enabled"]]
    return inventory, merged, copies


def _regular_file(path):
    info = Path(path).lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise InvalidInventory("unsafe migration input")


def backup_legacy(paths, destination):
    """Keep an exact root-only archive before the first migration write."""
    destination = Path(destination)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    fd, name = tempfile.mkstemp(prefix=".proxy-backup-", dir=destination.parent)
    os.fchmod(fd, 0o600)
    os.close(fd)
    try:
        with tarfile.open(name, "w:gz") as archive:
            for path in paths:
                path = Path(path)
                if path.exists() or path.is_symlink():
                    archive.add(path, arcname=str(path).lstrip("/"), recursive=True)
        os.replace(name, destination)
    finally:
        Path(name).unlink(missing_ok=True)
    return destination


def stage_unified(inventory, merged, cert_copies, *, config_path, state_path, binary):
    """Copy certificates, stage both JSON files, then verify with sing-box."""
    import json
    config_path, state_path = Path(config_path), Path(state_path)
    staged = []
    created = []
    try:
        for source, destination in cert_copies:
            source, destination = Path(source), Path(destination)
            _regular_file(source)
            if destination.exists() or destination.is_symlink():
                _regular_file(destination)
                if destination.read_bytes() != source.read_bytes():
                    raise InvalidInventory("migration certificate destination differs")
                continue
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            os.chmod(destination, 0o600)
            created.append(destination)
        for target, value in ((config_path, merged), (state_path, inventory)):
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix=".unified-proxy-", dir=target.parent)
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(value, output, ensure_ascii=False, separators=(",", ":"))
                output.flush()
                os.fsync(output.fileno())
            staged.append(Path(name))
        subprocess.run([str(binary), "check", "-c", str(staged[0])], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        return staged, created
    except BaseException:
        for path in staged + created:
            path.unlink(missing_ok=True)
        raise


def _snapshot(path):
    path = Path(path)
    if not path.exists():
        return None
    _regular_file(path)
    return path.read_bytes(), stat.S_IMODE(path.stat().st_mode)


def _restore(path, snapshot):
    path = Path(path)
    if snapshot is None:
        path.unlink(missing_ok=True)
        return
    data, mode = snapshot
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".proxy-restore-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def switch_unified(staged, created, *, config_path, state_path, meter_path,
                   proxy_unit, legacy_unit, proxy_meter_dropin, backend):
    """Switch services with file and service rollback on cutover failure."""
    paths = [Path(value) for value in
             (config_path, state_path, meter_path, proxy_unit, legacy_unit, proxy_meter_dropin)]
    saved = {path: _snapshot(path) for path in paths}
    old_services = {name: backend.status(name) for name in ("anytls", "proxy", "meter")}
    wanted_enabled = old_services["anytls"][1] or old_services["proxy"][1]
    wanted_active = old_services["anytls"][0] or old_services["proxy"][0]
    try:
        for name in ("anytls", "proxy", "meter"):
            backend.stop(name)
        Path(proxy_meter_dropin).unlink(missing_ok=True)
        os.replace(staged[0], config_path)
        os.replace(staged[1], state_path)
        if not Path(proxy_unit).is_file():
            backend.write_proxy_unit(proxy_unit, config_path)
        backend.reload()
        backend.reconcile(state_path, config_path, meter_path)
        if wanted_enabled:
            backend.enable("proxy")
        else:
            backend.disable("proxy")
        if wanted_active:
            backend.start("proxy")
            if not backend.status("proxy")[0]:
                raise RuntimeError("unified proxy did not become active")
        backend.disable("anytls")
        Path(legacy_unit).unlink(missing_ok=True)
        backend.reload()
    except BaseException:
        backend.stop("proxy")
        backend.stop("meter")
        for path, snapshot in saved.items():
            _restore(path, snapshot)
        backend.reload()
        for name, (active, enabled) in old_services.items():
            if enabled:
                backend.enable(name)
            else:
                backend.disable(name)
            if active:
                backend.start(name)
        for path in created:
            path.unlink(missing_ok=True)
        for path in staged:
            path.unlink(missing_ok=True)
        raise
    # The old config/certificates remain inert until the installer finishes.
    # The root-only archive permits a later manual restoration if needed.
    return saved, old_services


class SystemdBackend:
    UNITS = {"anytls": "vps-server-anytls.service",
             "proxy": "vps-server-proxy.service",
             "meter": "vps-server-node-meter.service"}

    def _systemctl(self, *args, check=True):
        return subprocess.run(["systemctl", *args], check=check, timeout=60,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def status(self, name):
        unit = self.UNITS[name]
        return (self._systemctl("is-active", "--quiet", unit, check=False).returncode == 0,
                self._systemctl("is-enabled", "--quiet", unit, check=False).returncode == 0)

    def stop(self, name):
        self._systemctl("stop", self.UNITS[name], check=False)
        if self.status(name)[0]:
            raise RuntimeError("service did not stop")

    def start(self, name):
        self._systemctl("start", self.UNITS[name])

    def enable(self, name):
        self._systemctl("enable", self.UNITS[name])

    def disable(self, name):
        self._systemctl("disable", self.UNITS[name], check=False)

    def reload(self):
        self._systemctl("daemon-reload")

    def write_proxy_unit(self, target, config):
        content = (f"[Unit]\nDescription=sing-box unified proxy\n"
                   "After=network-online.target\nWants=network-online.target\n\n"
                   "[Service]\nType=simple\n"
                   f"ExecStart=/usr/local/bin/sing-box-vps-server run -c {config}\n"
                   "Restart=on-failure\nRestartSec=3\nLimitNOFILE=1048576\n\n"
                   "[Install]\nWantedBy=multi-user.target\n")
        target = Path(target)
        fd, name = tempfile.mkstemp(prefix=".proxy-unit-", dir=target.parent)
        try:
            os.fchmod(fd, 0o644)
            with os.fdopen(fd, "w") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            os.replace(name, target)
        finally:
            Path(name).unlink(missing_ok=True)

    def reconcile(self, state_path, config_path, meter_path):
        try:
            from .node_meter import tick
        except ImportError:
            from node_meter import tick
        tick(state_path=state_path, config_paths={"proxy": config_path},
             meter_path=meter_path, lock_held=True)


def migrate_installed():
    """Cut over an installed split service before the installer copies code."""
    if os.geteuid() != 0:
        raise PermissionError("root is required")
    old_root = LEGACY_CERT_ROOT
    old_config = old_root / "config.json"
    if not old_config.is_file():
        return None
    proxy_root = PROXY_ROOT
    proxy_config = proxy_root / "config.json"
    state_path = Path("/etc/vps-server-nodes/state.json")
    meter_path = state_path.parent / "meter.json"
    legacy_unit = Path("/etc/systemd/system/vps-server-anytls.service")
    proxy_unit = Path("/etc/systemd/system/vps-server-proxy.service")
    dropin = Path("/etc/systemd/system/vps-server-proxy.service.d/node-meter.conf")
    binary = Path("/usr/local/bin/sing-box-vps-server")
    if not binary.is_file():
        raise FileNotFoundError(binary)
    lock_path = Path("/etc/vps-server-node.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    inherited = os.environ.get("VPSSRV_NODE_LOCK_FD")
    if inherited:
        fd = int(inherited)
        if os.readlink(f"/proc/self/fd/{fd}") != str(lock_path):
            raise RuntimeError("node lock descriptor differs")
        lock = os.fdopen(fd, "rb", closefd=False)
    else:
        lock = lock_path.open("a+b")
    with lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        old_doc = _read_json(old_config)
        proxy_doc = _read_json(proxy_config)
        existing = _read_json(state_path)
        inventory, merged, copies = unified_plan(old_doc, proxy_doc, existing)
        backup = state_data_dir() / f"proxy-unification-{int(time.time())}.tar.gz"
        backup_legacy((old_root, proxy_root, state_path, meter_path,
                       legacy_unit, proxy_unit, dropin), backup)
        prefix = os.environ.get("PREFIX")
        if not prefix:
            raise RuntimeError("installer prefix required for port registration")
        from console_port import reserve_owned_port, release_owned_port
        added = []
        try:
            for node in inventory["nodes"]:
                if node["enabled"]:
                    owner = "vps-server proxy " + node["id"]
                    if reserve_owned_port(prefix, node["port"], owner, probe=False):
                        added.append((node["port"], owner))
            staged, created = stage_unified(inventory, merged, copies,
                                           config_path=proxy_config, state_path=state_path,
                                           binary=binary)
            switch_unified(staged, created, config_path=proxy_config, state_path=state_path,
                           meter_path=meter_path, proxy_unit=proxy_unit,
                           legacy_unit=legacy_unit, proxy_meter_dropin=dropin,
                           backend=SystemdBackend())
        except BaseException:
            for port, owner in reversed(added):
                release_owned_port(prefix, port, owner)
            raise
        return backup


def finalize_installed(*, old_root=LEGACY_CERT_ROOT, proxy_root=PROXY_ROOT,
                       state_path=Path("/etc/vps-server-nodes/state.json"),
                       legacy_unit=Path("/etc/systemd/system/vps-server-anytls.service"),
                       backup_dir=None, prefix=None):
    """Retire inert split files only after the new install has completed."""
    old_root, proxy_root, state_path, legacy_unit = map(Path, (old_root, proxy_root, state_path, legacy_unit))
    if not (old_root / "config.json").is_file():
        return False
    backup_dir = Path(backup_dir) if backup_dir is not None else state_data_dir()
    if not any(backup_dir.glob("proxy-unification-*.tar.gz")) or legacy_unit.exists():
        raise RuntimeError("legacy proxy migration was not completed")
    inventory = read_inventory(state_path=state_path, config_paths={"proxy": proxy_root / "config.json"})
    if inventory is None or not any(node["protocol"] == "anytls" for node in inventory["nodes"]):
        raise RuntimeError("unified AnyTLS node is missing")
    shutil.rmtree(old_root)
    if prefix is not None:
        old_script = Path(prefix) / "anytls"
        if old_script.is_dir() and not old_script.is_symlink():
            shutil.rmtree(old_script)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("migrate", "finalize"))
    args = parser.parse_args()
    if args.action == "migrate":
        backup = migrate_installed()
        print(f"Unified proxy migration backup: {backup}" if backup else
              "No legacy AnyTLS service to migrate")
    else:
        finalize_installed(prefix=os.environ.get("PREFIX"))


if __name__ == "__main__":
    main()
