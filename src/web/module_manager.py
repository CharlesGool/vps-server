"""Privileged, fixed-action module manager for the authenticated console.

The Web process submits only a module name and action. This helper rechecks
installed state and uses the version-matched installer payload; no request
body or shell text becomes a command.
"""

import fcntl
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time

try:
    from .node_state import STATE_PATH as NODE_STATE_PATH, read_inventory, write_inventory
except ImportError:
    from node_state import STATE_PATH as NODE_STATE_PATH, read_inventory, write_inventory

try:
    from .frp_control import client_names as frpc_names, client_unit as frpc_unit
except ImportError:  # Installed helpers are copied into one flat directory.
    from frp_control import client_names as frpc_names, client_unit as frpc_unit


MODULES = ("web", "iperf3", "anytls", "proxy", "frps", "lucky")
STANDALONE_MODULES = ("frpc",)
FEATURES = ("speedtest", "portfwd", "visitors")
GROUPS = ("proxy_nodes", "frpc")
PUBLIC_LISTENERS = ("web_http", "web_https")
UNITS = {
    "anytls": "vps-server-anytls.service",
    "proxy": "vps-server-proxy.service",
    "frps": "vps-server-frps.service",
    "lucky": "vps-server-lucky.service",
}
FRPC_BINARY = Path("/usr/local/bin/frpc")
FRPC_UNIT = Path("/etc/systemd/system/frpc@.service")
FRPC_CONFIG_DIR = Path("/etc/frp")
FRPC_SHA256 = "f79fff8de3089ec711ff8bdd4b73e00dfe491a1c3d754983c8b0f8d58c21b068"
IPERF_SHA256 = "f1924a042ef4074b5974b8985a235ad2fcb45d52d02cec46b0dfb45e269b9bf2"


def iperf_binary(prefix):
    bundled = Path(prefix) / "vendor" / "iperf3" / "iperf3"
    return str(bundled) if bundled.is_file() else shutil.which("iperf3")


def frpc_installed():
    return FRPC_BINARY.is_file() and FRPC_UNIT.is_file()


def frpc_group_enabled(prefix):
    """The module switch is independent of its individual instance units."""
    data = Path(prefix) / "data"
    flag = data / "frpc-group-enabled"
    if flag.is_file():
        return flag.read_text().strip() == "1"
    # Older deployments only wrote this file when the group was switched off.
    return not (data / "frpc-group-active.json").exists()


def installed_modules(prefix):
    state = Path(prefix) / ".install-state"
    if not state.is_file():
        return set()
    for line in state.read_text(encoding="utf-8").splitlines():
        if line.startswith("modules="):
            recorded = set(line[8:].split(',')) & set(MODULES)
            present = set()
            if "web" in recorded and (Path(prefix) / "app.py").is_file():
                present.add("web")
            if "iperf3" in recorded and iperf_binary(prefix):
                present.add("iperf3")
            for module in ("anytls", "proxy", "frps", "lucky"):
                if module in recorded and Path(f"/etc/systemd/system/{UNITS[module]}").is_file():
                    present.add(module)
            if frpc_installed():
                present.add("frpc")
            return present
    return set()


def status_path(prefix):
    return Path(prefix) / "data" / "module-job.json"


def log_path(prefix):
    return Path(prefix) / "data" / "module-job.log"


def feature_enabled(prefix, feature):
    if feature not in FEATURES:
        raise ValueError("unknown feature")
    flag = Path(prefix) / "data" / f"{feature}-enabled"
    return not flag.is_file() or flag.read_text().strip() != "0"


def public_listener_enabled(prefix, listener, default=True):
    if listener not in PUBLIC_LISTENERS:
        raise ValueError("unknown public listener")
    flag = Path(prefix) / "data" / f"{listener.replace('_', '-')}-enabled"
    if flag.is_file():
        return flag.read_text().strip() == "1"
    legacy = Path(prefix) / "data" / "web-public-enabled"
    return legacy.read_text().strip() == "1" if legacy.is_file() else default


def set_feature(prefix, feature, enabled):
    if feature not in FEATURES:
        raise ValueError("unknown feature")
    flag = Path(prefix) / "data" / f"{feature}-enabled"
    flag.parent.mkdir(parents=True, exist_ok=True)
    previous = flag.read_bytes() if flag.exists() else None
    temp = flag.with_suffix(".tmp")
    temp.write_text("1\n" if enabled else "0\n")
    os.chmod(temp, 0o600)
    os.replace(temp, flag)
    if feature == "portfwd":
        try:
            wait_portfwd_applied(prefix, enabled, flag)
        except Exception:
            if previous is None:
                flag.unlink(missing_ok=True)
            else:
                temp.write_bytes(previous)
                os.chmod(temp, 0o600)
                os.replace(temp, flag)
            raise


def wait_portfwd_applied(prefix, enabled, flag):
    state = flag.stat()
    revision = [state.st_ino, state.st_mtime_ns]
    applied = Path(prefix) / "data" / "portfwd-applied.json"
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            status = json.loads(applied.read_text())
            if status.get("enabled") is enabled and status.get("revision") == revision:
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    raise RuntimeError("Web did not apply the port forwarding switch")


def save_status(prefix, module, state, **details):
    target = status_path(prefix)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps({"module": module, "state": state, "at": int(time.time()), **details}) + "\n")
    os.chmod(temp, 0o600)
    os.replace(temp, target)


class PublicPortOccupied(RuntimeError):
    def __init__(self, port):
        self.port = port
        super().__init__(f"Port {port} is already in use")


def wait_public_listener_applied(prefix, listener, enabled, old_pid):
    status_file = Path(prefix) / "data" / "public-listeners.json"
    name = "http" if listener == "web_http" else "https"
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            status = json.loads(status_file.read_text())
            item = status[name]
            if status["pid"] != old_pid and item["enabled"] == enabled:
                if enabled and not item["bound"]:
                    if item.get("reason") == "occupied":
                        raise PublicPortOccupied(item["port"])
                    raise RuntimeError(f"Port {item['port']} could not start")
                return
        except (OSError, ValueError, KeyError, TypeError):
            pass
        time.sleep(0.1)
    raise RuntimeError("Web did not report the public listener state")


def switch_web_setting(path, enabled):
    previous = path.read_bytes() if path.exists() else None
    path.write_text("1\n" if enabled else "0\n")
    os.chmod(path, 0o600)
    try:
        subprocess.run(["systemctl", "restart", "vps-server-web.service"], check=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(previous)
            os.chmod(path, 0o600)
        subprocess.run(["systemctl", "restart", "vps-server-web.service"], check=False, timeout=60)
        raise


def switch_public_listener(prefix, listener, enabled):
    path = Path(prefix) / "data" / f"{listener.replace('_', '-')}-enabled"
    status_file = Path(prefix) / "data" / "public-listeners.json"
    try:
        old_pid = json.loads(status_file.read_text()).get("pid")
    except (OSError, ValueError, TypeError):
        old_pid = None
    previous = path.read_bytes() if path.exists() else None
    path.write_text("1\n" if enabled else "0\n")
    os.chmod(path, 0o600)
    try:
        subprocess.run(["systemctl", "restart", "vps-server-web.service"], check=True, timeout=60)
        wait_public_listener_applied(prefix, listener, enabled, old_pid)
    except (OSError, subprocess.SubprocessError, RuntimeError):
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(previous)
            os.chmod(path, 0o600)
        subprocess.run(["systemctl", "restart", "vps-server-web.service"], check=False, timeout=60)
        raise


def reconcile_removed_nodes(prefix, installed, *, state_path=NODE_STATE_PATH,
                            lock_path=Path("/etc/vps-server-node.lock")):
    """Discard inventory entries left by a previously removed node module.

    Preserve the original inventory before changing it. Configurations of
    still-installed modules remain protected by the normal inventory checks.
    """
    state_path = Path(state_path)
    with Path(lock_path).open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        inventory = read_inventory(state_path=state_path, check_installed=False)
        if inventory is None:
            return
        kept = [node for node in inventory["nodes"] if
                ("anytls" if node["protocol"] == "anytls" else "proxy") in installed]
        if len(kept) == len(inventory["nodes"]):
            return
        backup = Path(prefix) / "data" / f"node-inventory-before-reinstall-{time.time_ns()}.json"
        backup.write_bytes(state_path.read_bytes())
        os.chmod(backup, 0o600)
        inventory["nodes"] = kept
        write_inventory(inventory, state_path=state_path)
        print(f"Preserved removed node inventory: {backup}", flush=True)


def run_install(prefix, module):
    if module == "frpc":
        return install_frpc(prefix)
    if module == "iperf3":
        return install_iperf3(prefix)
    if module == "frps":
        return install_frps(prefix)
    requested = {"proxy", "anytls"} if module == "proxy_nodes" else {module}
    source = Path(prefix) / "installer-source" / "deploy" / "install.sh"
    if not source.is_file():
        raise RuntimeError("installer payload unavailable; upgrade from a full checkout first")
    installed = installed_modules(prefix)
    if "web" not in installed:
        raise RuntimeError("the console module is unavailable")
    if requested <= installed:
        raise RuntimeError("module already installed")
    if requested & {"proxy", "anytls"}:
        if not ({"proxy", "anytls"} & installed):
            subprocess.run(["systemctl", "stop", "vps-server-node-meter.service"],
                           check=False, timeout=60)
        reconcile_removed_nodes(prefix, installed)
    selected = [item for item in MODULES if item in installed or item in requested]
    disabled = [item for item in installed if item in UNITS and
                subprocess.run(["systemctl", "is-enabled", "--quiet", UNITS[item]],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0]
    env = dict(os.environ, PREFIX=str(prefix), VPSSRV_MODULES=','.join(selected),
               TERM="dumb", NO_COLOR="1", DEBIAN_FRONTEND="noninteractive")
    env.pop("VPSSRV_SETUP_PUBLIC", None)
    # The installer owns package dependencies, node inventory, service units,
    # preservation of all prior credentials, and the installed-module record.
    try:
        subprocess.run(["/usr/bin/bash", str(source)], env=env,
                       stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=subprocess.STDOUT,
                       check=True, timeout=900)
    finally:
        # A module install must not silently re-enable a prior module.
        for item in disabled:
            subprocess.run(["systemctl", "disable", "--now", UNITS[item]], check=True, timeout=60)
        # The installer may have stopped Web while checking listeners.
        if subprocess.run(["systemctl", "is-active", "--quiet", "vps-server-web.service"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
            subprocess.run(["systemctl", "start", "vps-server-web.service"], check=True, timeout=60)
    if not requested <= installed_modules(prefix):
        raise RuntimeError("module was not recorded as installed")


def install_iperf3(prefix):
    """Install the verified offline binary without touching existing nodes."""
    prefix = Path(prefix)
    if "web" not in installed_modules(prefix):
        raise RuntimeError("the console module is unavailable")
    if "iperf3" in installed_modules(prefix):
        raise RuntimeError("module already installed")
    state = prefix / ".install-state"
    if not state.is_file():
        raise RuntimeError("installed-module record is unavailable")
    lines = state.read_text(encoding="utf-8").splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith("modules="):
            modules = line.removeprefix("modules=").strip().split(",")
            if "iperf3" not in modules:
                modules.append("iperf3")
            lines[index] = "modules=" + ",".join(modules) + "\n"
            break
    else:
        raise RuntimeError("installed-module record has no modules field")
    source = prefix / "installer-source" / "third_party" / "iperf3" / "iperf3"
    if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != IPERF_SHA256:
        raise RuntimeError("verified bundled iperf3 is unavailable")
    destination = prefix / "vendor" / "iperf3" / "iperf3"
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = destination.with_suffix(".tmp")
    try:
        shutil.copyfile(source, staged)
        os.chmod(staged, 0o755)
        os.replace(staged, destination)
    finally:
        staged.unlink(missing_ok=True)
    switch_web_setting(prefix / "data" / "iperf3-enabled", True)
    temp = state.with_suffix(".tmp")
    temp.write_text("".join(lines), encoding="utf-8")
    os.chmod(temp, state.stat().st_mode & 0o777)
    os.replace(temp, state)


def install_frps(prefix):
    """Install FRPS without touching unrelated node services or credentials."""
    prefix = Path(prefix)
    if "web" not in installed_modules(prefix):
        raise RuntimeError("the console module is unavailable")
    if "frps" in installed_modules(prefix):
        raise RuntimeError("module already installed")
    source = prefix / "installer-source" / "deploy" / "frps" / "setup-frps.sh"
    if not source.is_file():
        raise RuntimeError("installer payload unavailable; upgrade from a full checkout first")
    env = dict(os.environ, PREFIX=str(prefix), TERM="dumb", NO_COLOR="1")
    subprocess.run(["/usr/bin/bash", str(source)], env=env,
                   stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=subprocess.STDOUT,
                   check=True, timeout=300)
    state = prefix / ".install-state"
    lines = state.read_text(encoding="utf-8").splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith("modules="):
            selected = set(line.removeprefix("modules=").strip().split(",")) | {"frps"}
            lines[index] = "modules=" + ",".join(item for item in MODULES if item in selected) + "\n"
            break
    else:
        raise RuntimeError("installed-module record has no modules field")
    staged = state.with_suffix(".tmp")
    staged.write_text("".join(lines), encoding="utf-8")
    os.chmod(staged, state.stat().st_mode & 0o777)
    os.replace(staged, state)
    if "frps" not in installed_modules(prefix):
        raise RuntimeError("FRPS service was not recorded as installed")


def install_frpc(prefix):
    """Install the pinned client and service template without creating a connection."""
    if frpc_installed():
        raise RuntimeError("FRPC is already installed")
    template = Path(prefix) / "installer-source" / "deploy" / "systemd" / "frpc@.service"
    if not template.is_file():
        raise RuntimeError("FRPC service template is unavailable")
    source = Path(prefix) / "vendor" / "frp" / "frpc"
    bundled = Path(prefix) / "installer-source" / "third_party" / "frp" / "frpc"
    if not source.is_file():
        source = bundled
    if not source.is_file():
        raise RuntimeError("bundled FRPC binary is unavailable")
    if hashlib.sha256(source.read_bytes()).hexdigest() != FRPC_SHA256:
        raise RuntimeError("FRPC binary checksum mismatch")
    if FRPC_BINARY.exists() and hashlib.sha256(FRPC_BINARY.read_bytes()).hexdigest() != FRPC_SHA256:
        raise RuntimeError("An existing FRPC binary differs from the bundled version")
    if FRPC_UNIT.exists() and FRPC_UNIT.read_bytes() != template.read_bytes():
        raise RuntimeError("An existing FRPC service template differs from the bundled version")
    created_binary = not FRPC_BINARY.exists()
    created_unit = not FRPC_UNIT.exists()
    owned = Path(prefix) / "data" / "frpc-binary-owned"
    try:
        if created_binary:
            staged = FRPC_BINARY.with_suffix(".tmp")
            shutil.copyfile(source, staged)
            os.chmod(staged, 0o755)
            os.replace(staged, FRPC_BINARY)
        if created_unit:
            staged = FRPC_UNIT.with_suffix(".tmp")
            shutil.copyfile(template, staged)
            os.chmod(staged, 0o644)
            os.replace(staged, FRPC_UNIT)
        FRPC_CONFIG_DIR.mkdir(mode=0o700, exist_ok=True)
        subprocess.run(["systemctl", "daemon-reload"], check=True, timeout=30)
        if created_binary:
            owned.write_text(FRPC_SHA256 + "\n")
            os.chmod(owned, 0o600)
    except BaseException:
        if created_binary:
            owned.unlink(missing_ok=True)
        FRPC_UNIT.with_suffix(".tmp").unlink(missing_ok=True)
        FRPC_BINARY.with_suffix(".tmp").unlink(missing_ok=True)
        if created_unit:
            FRPC_UNIT.unlink(missing_ok=True)
        if created_binary:
            FRPC_BINARY.unlink(missing_ok=True)
        raise
    print("FRPC installed.", flush=True)


def run_toggle(prefix, module, enabled):
    if module in PUBLIC_LISTENERS:
        if "web" not in installed_modules(prefix):
            raise RuntimeError("the console module is unavailable")
        # Let the console return its redirect before the Web unit restarts.
        time.sleep(2)
        switch_public_listener(prefix, module, enabled)
        return
    if module == "frpc":
        if not frpc_installed():
            raise RuntimeError("FRPC is not installed")
        names = frpc_names(FRPC_CONFIG_DIR)
        state = Path(prefix) / "data" / "frpc-group-active.json"
        flag = Path(prefix) / "data" / "frpc-group-enabled"
        if enabled:
            saved = json.loads(state.read_text()) if state.is_file() else []
            for name in names:
                if name in saved:
                    subprocess.run(["systemctl", "enable", "--now", frpc_unit(name)], check=True, timeout=60)
            state.unlink(missing_ok=True)
            flag.write_text("1\n")
            os.chmod(flag, 0o600)
        else:
            active = [name for name in names if subprocess.run(
                ["systemctl", "is-active", "--quiet", frpc_unit(name)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0]
            state.write_text(json.dumps(active) + "\n")
            os.chmod(state, 0o600)
            for name in names:
                subprocess.run(["systemctl", "disable", "--now", frpc_unit(name)], check=True, timeout=60)
            flag.write_text("0\n")
            os.chmod(flag, 0o600)
        return
    if module == "proxy_nodes":
        present = installed_modules(prefix) & {"proxy", "anytls"}
        if not present:
            raise RuntimeError("proxy nodes are not installed")
        for item in ("proxy", "anytls"):
            if item in present:
                run_toggle(prefix, item, enabled)
        return
    if module in FEATURES:
        set_feature(prefix, module, enabled)
        return
    if module not in installed_modules(prefix):
        raise RuntimeError("module is not installed")
    if module == "iperf3":
        target = Path(prefix) / "data" / "iperf3-enabled"
        switch_web_setting(target, enabled)
        return
    unit = UNITS[module]
    nodes = []
    if module in ("anytls", "proxy"):
        state = Path("/etc/vps-server-nodes/state.json")
        if state.is_file():
            nodes = [node for node in json.loads(state.read_text()).get("nodes", [])
                     if node.get("enabled", True) and
                     (node.get("protocol") == "anytls") == (module == "anytls")]
    if enabled:
        subprocess.run(["systemctl", "enable", unit], check=True, timeout=30)
        try:
            if module not in ("anytls", "proxy") or nodes:
                subprocess.run(["systemctl", "start", unit], check=True, timeout=60)
            if nodes:
                from node_control import HostBackend
                backend = HostBackend()
                for node in nodes:
                    backend.firewall(node["port"], True, node["protocol"])
        except BaseException:
            subprocess.run(["systemctl", "disable", "--now", unit], check=False, timeout=60)
            raise
    else:
        subprocess.run(["systemctl", "disable", "--now", unit], check=True, timeout=60)
        if nodes:
            from node_control import HostBackend
            backend = HostBackend()
            for node in nodes:
                backend.firewall(node["port"], False, node["protocol"])


def run_uninstall(prefix, module):
    """Remove an optional module after retaining its configuration locally."""
    if module == "frpc":
        return uninstall_frpc(prefix)
    if module not in ("iperf3", "proxy_nodes", "frps"):
        raise ValueError("module cannot be uninstalled separately")
    present = installed_modules(prefix)
    targets = ({"proxy", "anytls"} & present) if module == "proxy_nodes" else {module} & present
    if not targets:
        raise RuntimeError("module is not installed")
    archive = Path(prefix) / "data" / f"module-backup-{module}-{int(time.time())}.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        paths = {"proxy": "/etc/vps-server-proxy", "anytls": "/etc/vps-server-anytls",
                 "frps": "/etc/vps-server-frps"}
        for item in targets:
            path = Path(paths[item]) if item in paths else None
            if path and path.exists():
                output.add(path, arcname=f"etc/{path.name}")
        if module == "proxy_nodes":
            state_path = Path("/etc/vps-server-nodes/state.json")
            if state_path.is_file():
                output.add(state_path, arcname="etc/vps-server-nodes/state.json")
    os.chmod(archive, 0o600)
    print(f"Configuration backup: {archive}", flush=True)
    if module == "iperf3":
        switch_web_setting(Path(prefix) / "data" / "iperf3-enabled", False)
        bundled = Path(prefix) / "vendor" / "iperf3" / "iperf3"
        if bundled.is_file() and hashlib.sha256(bundled.read_bytes()).hexdigest() == IPERF_SHA256:
            bundled.unlink()
    elif module == "proxy_nodes":
        subprocess.run(["systemctl", "stop", "vps-server-node-meter.service"],
                       check=False, timeout=60)
        for item in ("proxy", "anytls"):
            if item in targets:
                script = Path(prefix) / item / f"setup-{item}.sh"
                subprocess.run(["/usr/bin/bash", str(script), "uninstall"],
                               stdout=sys.stdout, stderr=subprocess.STDOUT, check=True, timeout=180)
        reconcile_removed_nodes(prefix, present - targets)
        if not ({"proxy", "anytls"} & (present - targets)):
            subprocess.run(["systemctl", "disable", "--now", "vps-server-node-meter.service"],
                           check=False, timeout=60)
    elif module == "frps":
        subprocess.run(["systemctl", "disable", "--now", UNITS["frps"]], check=True, timeout=60)
        owner = Path("/etc/vps-server-frps/firewall-owned")
        if owner.is_file():
            parts = owner.read_text().split()
            if len(parts) == 2 and parts[1].isascii() and parts[1].isdigit() and 1 <= int(parts[1]) <= 65535:
                backend, port = parts
                if backend == "ufw":
                    subprocess.run(["ufw", "--force", "delete", "allow", f"{port}/tcp"], check=True, timeout=30)
                    owner.unlink()
                elif backend == "firewalld":
                    subprocess.run(["firewall-cmd", "--permanent", f"--remove-port={port}/tcp"], check=True, timeout=30)
                    subprocess.run(["firewall-cmd", "--reload"], check=True, timeout=30)
                    owner.unlink()
        Path(f"/etc/systemd/system/{UNITS['frps']}").unlink(missing_ok=True)
        subprocess.run(["systemctl", "daemon-reload"], check=True, timeout=30)
        # Keep bind port and token so a later reinstall can restore clients.
        Path("/usr/local/bin/frps-vps-server").unlink(missing_ok=True)
    state = Path(prefix) / ".install-state"
    lines = state.read_text().splitlines()
    kept = present - targets
    next_state = "\n".join("modules=" + ",".join(item for item in MODULES if item in kept)
                           if line.startswith("modules=") else line for line in lines) + "\n"
    staged = state.with_suffix(".tmp")
    staged.write_text(next_state)
    os.chmod(staged, 0o600)
    os.replace(staged, state)


def uninstall_frpc(prefix):
    """Remove the local client service; preserve every server configuration."""
    if not frpc_installed():
        raise RuntimeError("FRPC is not installed")
    template = Path(prefix) / "installer-source" / "deploy" / "systemd" / "frpc@.service"
    if not template.is_file() or FRPC_UNIT.read_bytes() != template.read_bytes():
        raise RuntimeError("FRPC service template changed; refusing to remove it")
    configs = sorted(FRPC_CONFIG_DIR.glob("frpc-*.toml"))
    names = frpc_names(FRPC_CONFIG_DIR)
    archive = Path(prefix) / "data" / f"module-backup-frpc-{int(time.time())}.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        for config in configs:
            if config.is_file() and not config.is_symlink():
                output.add(config, arcname=f"etc/frp/{config.name}")
    os.chmod(archive, 0o600)
    print(f"Configuration backup: {archive}", flush=True)
    for name in names:
        subprocess.run(["systemctl", "disable", "--now", frpc_unit(name)], check=True, timeout=60)
    FRPC_UNIT.unlink()
    try:
        subprocess.run(["systemctl", "daemon-reload"], check=True, timeout=30)
    except BaseException:
        shutil.copyfile(template, FRPC_UNIT)
        os.chmod(FRPC_UNIT, 0o644)
        subprocess.run(["systemctl", "daemon-reload"], check=False, timeout=30)
        raise
    owned = Path(prefix) / "data" / "frpc-binary-owned"
    if owned.is_file() and owned.read_text().strip() == FRPC_SHA256 and FRPC_BINARY.is_file():
        if hashlib.sha256(FRPC_BINARY.read_bytes()).hexdigest() == FRPC_SHA256:
            FRPC_BINARY.unlink()
            owned.unlink()
    print("FRPC service removed; server configurations retained.", flush=True)


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) != 3 or argv[0] not in ("install", "enable", "disable", "uninstall") or argv[1] not in MODULES + STANDALONE_MODULES + FEATURES + GROUPS + PUBLIC_LISTENERS:
        raise SystemExit("invalid module action")
    action, module, prefix = argv
    if module in PUBLIC_LISTENERS and action not in ("enable", "disable"):
        raise SystemExit("invalid public listener action")
    prefix = str(Path(prefix).resolve(strict=True))
    if os.geteuid() != 0 or not (Path(prefix) / ".install-state").is_file():
        raise SystemExit("root and an installed console are required")
    lock_path = Path(prefix) / "data" / "module-job.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        log = log_path(prefix)
        with log.open("w", encoding="utf-8", buffering=1) as output, redirect_stdout(output), redirect_stderr(output):
            os.chmod(log, 0o600)
            save_status(prefix, module, "running", action=action)
            print(f"{action} {module}", flush=True)
            try:
                if action == "install":
                    run_install(prefix, module)
                elif action == "uninstall":
                    run_uninstall(prefix, module)
                else:
                    run_toggle(prefix, module, action == "enable")
            except PublicPortOccupied as exc:
                print(f"Error: {exc}", flush=True)
                save_status(prefix, module, "failed", action=action,
                            reason="port_occupied", port=exc.port)
                raise SystemExit(1)
            except (OSError, RuntimeError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as exc:
                print(f"Error: {exc}", flush=True)
                save_status(prefix, module, "failed", action=action)
                raise SystemExit(1)
            save_status(prefix, module, "done", action=action)


if __name__ == "__main__":
    main()
