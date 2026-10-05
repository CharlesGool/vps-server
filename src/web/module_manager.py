"""Privileged, fixed-action module manager for the authenticated console.

The Web process submits only a module name and action. This helper rechecks
installed state and uses the version-matched installer payload; no request
body or shell text becomes a command.
"""

import fcntl
import codecs
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tarfile
import time

try:
    from .state_paths import data_dir as state_data_dir, install_state_file, state_dir
except ImportError:
    from state_paths import data_dir as state_data_dir, install_state_file, state_dir

try:
    from .node_state import STATE_PATH as NODE_STATE_PATH, read_inventory, write_inventory
except ImportError:
    from node_state import STATE_PATH as NODE_STATE_PATH, read_inventory, write_inventory

try:
    from .frp_control import client_names as frpc_names, client_unit as frpc_unit
except ImportError:  # Installed helpers are copied into one flat directory.
    from frp_control import client_names as frpc_names, client_unit as frpc_unit


MODULES = ("web", "iperf3", "proxy", "frps", "lucky", "tailscale")
STANDALONE_MODULES = ("frpc",)
FEATURES = ("speedtest", "portfwd", "visitors", "terminal")
GROUPS = ("proxy_nodes", "frpc")
PUBLIC_LISTENERS = ("web_http", "web_https")
UNITS = {
    "proxy": "vps-server-proxy.service",
    "frps": "vps-server-frps.service",
    "lucky": "vps-server-lucky.service",
    "tailscale": "vps-server-tailscale.service",
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
    data = state_data_dir()
    flag = data / "frpc-group-enabled"
    if flag.is_file():
        return flag.read_text().strip() == "1"
    # Older deployments only wrote this file when the group was switched off.
    return not (data / "frpc-group-active.json").exists()


def installed_modules(prefix):
    state = install_state_file()
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
            for module in ("proxy", "frps", "lucky", "tailscale"):
                if module in recorded and Path(f"/etc/systemd/system/{UNITS[module]}").is_file():
                    present.add(module)
            if frpc_installed():
                present.add("frpc")
            return present
    return set()


def status_path(prefix):
    return state_data_dir() / "module-job.json"


def log_path(prefix):
    return state_data_dir() / "module-job.log"

def history_path(prefix):
    return state_data_dir() / "module-history.log"


class JobOutput:
    def __init__(self, current, history):
        self.current = current
        self.history = history

    def write(self, value):
        self.current.write(value)
        self.history.write(value)
        return len(value)

    def flush(self):
        self.current.flush()
        self.history.flush()


def run_logged(command, *, env=None, timeout):
    """Stream a child into both module logs without passing a fake fd to Popen."""
    process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               bufsize=0)
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    deadline = time.monotonic() + timeout
    try:
        fd = process.stdout.fileno()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            ready, _, _ = select.select([fd], [], [], min(remaining, 1.0))
            if not ready:
                continue
            chunk = os.read(fd, 4096)
            if not chunk:
                break
            sys.stdout.write(decoder.decode(chunk))
            sys.stdout.flush()
        tail = decoder.decode(b"", final=True)
        if tail:
            sys.stdout.write(tail)
            sys.stdout.flush()
        returncode = process.wait(timeout=max(0.1, deadline - time.monotonic()))
        if returncode:
            raise subprocess.CalledProcessError(returncode, command)
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.wait()
        raise
    finally:
        process.stdout.close()


def feature_enabled(prefix, feature):
    if feature not in FEATURES:
        raise ValueError("unknown feature")
    flag = state_data_dir() / f"{feature}-enabled"
    return not flag.is_file() or flag.read_text().strip() != "0"


def public_listener_enabled(prefix, listener, default=True):
    if listener not in PUBLIC_LISTENERS:
        raise ValueError("unknown public listener")
    flag = state_data_dir() / f"{listener.replace('_', '-')}-enabled"
    if flag.is_file():
        return flag.read_text().strip() == "1"
    legacy = state_data_dir() / "web-public-enabled"
    return legacy.read_text().strip() == "1" if legacy.is_file() else default


def set_feature(prefix, feature, enabled):
    if feature not in FEATURES:
        raise ValueError("unknown feature")
    flag = state_data_dir() / f"{feature}-enabled"
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
    applied = state_data_dir() / "portfwd-applied.json"
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
    status_file = state_data_dir() / "public-listeners.json"
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
    from console_port import reserve_owned_port, release_owned_port
    key = "VPSSRV_PUBLIC_HTTP_PORT" if listener == "web_http" else "VPSSRV_PUBLIC_HTTPS_PORT"
    default = 80 if listener == "web_http" else 443
    unit_file = Path("/etc/systemd/system/vps-server-web.service")
    try:
        recorded = next((line.split("=", 2)[2] for line in unit_file.read_text().splitlines()
                         if line.startswith("Environment=" + key + "=")), "")
        port = int(recorded or default)
    except (OSError, ValueError) as exc:
        raise RuntimeError("cannot determine public listener port") from exc
    owner = "vps-server Web HTTP" if listener == "web_http" else "vps-server Web HTTPS"
    path = state_data_dir() / f"{listener.replace('_', '-')}-enabled"
    status_file = state_data_dir() / "public-listeners.json"
    try:
        old_pid = json.loads(status_file.read_text()).get("pid")
    except (OSError, ValueError, TypeError):
        old_pid = None
    previous = path.read_bytes() if path.exists() else None
    reserved = reserve_owned_port(prefix, port, owner) if enabled else False
    path.write_text("1\n" if enabled else "0\n")
    os.chmod(path, 0o600)
    try:
        subprocess.run(["systemctl", "restart", "vps-server-web.service"], check=True, timeout=60)
        wait_public_listener_applied(prefix, listener, enabled, old_pid)
        if not enabled:
            release_owned_port(prefix, port, owner)
    except (OSError, ValueError, subprocess.SubprocessError, RuntimeError):
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(previous)
            os.chmod(path, 0o600)
        subprocess.run(["systemctl", "restart", "vps-server-web.service"], check=False, timeout=60)
        if reserved:
            release_owned_port(prefix, port, owner)
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
        kept = [node for node in inventory["nodes"] if "proxy" in installed]
        if len(kept) == len(inventory["nodes"]):
            return
        backup = state_data_dir() / f"node-inventory-before-reinstall-{time.time_ns()}.json"
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
    requested = {"proxy"} if module == "proxy_nodes" else {module}
    source = Path(prefix) / "installer-source" / "deploy" / "install.sh"
    if not source.is_file():
        raise RuntimeError("installer payload unavailable; upgrade from a full checkout first")
    installed = installed_modules(prefix)
    if "web" not in installed:
        raise RuntimeError("the console module is unavailable")
    if requested <= installed:
        raise RuntimeError("module already installed")
    if requested & {"proxy"}:
        if Path("/etc/vps-server-anytls/config.json").is_file():
            raise RuntimeError("legacy AnyTLS service must be migrated by the full installer")
        if "proxy" not in installed:
            subprocess.run(["systemctl", "stop", "vps-server-node-meter.service"],
                           check=False, timeout=60)
        reconcile_removed_nodes(prefix, installed)
    selected = [item for item in MODULES if item in installed or item in requested]
    disabled = [item for item in installed if item in UNITS and
                subprocess.run(["systemctl", "is-enabled", "--quiet", UNITS[item]],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0]
    env = dict(os.environ, PREFIX=str(prefix), VPSSRV_MODULES=','.join(selected),
               TERM="dumb", NO_COLOR="1", DEBIAN_FRONTEND="noninteractive", VPSSRV_INSTALL_WORKER="1")
    env.pop("VPSSRV_INSTALL_JOB_DIR", None)
    env.pop("VPSSRV_SETUP_PUBLIC", None)
    # The installer owns package dependencies, node inventory, service units,
    # preservation of all prior credentials, and the installed-module record.
    try:
        run_logged(["/usr/bin/bash", str(source)], env=env, timeout=900)
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
    state = install_state_file()
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
    switch_web_setting(state_data_dir() / "iperf3-enabled", True)
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
    from console_port import reserve_owned_port, release_owned_port
    config = Path("/etc/vps-server-frps/frps.toml")
    if config.is_file():
        listener = managed_listener("frps")
    else:
        requested = os.environ.get("FRPS_BIND_PORT", "")
        if requested and (not requested.isascii() or not requested.isdecimal()):
            raise ValueError("invalid FRPS bind port")
        listener = (int(requested or "7000"), "vps-server frps")
    reserve_owned_port(prefix, *listener)
    env = dict(os.environ, PREFIX=str(prefix), TERM="dumb", NO_COLOR="1")
    state = install_state_file()
    original_state = state.read_bytes()
    try:
        run_logged(["/usr/bin/bash", str(source)], env=env, timeout=300)
        if managed_listener("frps") != listener:
            raise RuntimeError("FRPS bind port changed during module installation")
        lines = original_state.decode("utf-8").splitlines(keepends=True)
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
    except BaseException:
        if state.read_bytes() != original_state:
            staged = state.with_suffix(".tmp")
            staged.write_bytes(original_state)
            os.chmod(staged, 0o600)
            os.replace(staged, state)
        subprocess.run(["systemctl", "disable", "--now", UNITS["frps"]], check=False, timeout=60)
        release_owned_port(prefix, *listener)
        raise


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
    owned = state_data_dir() / "frpc-binary-owned"
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
        state = state_data_dir() / "frpc-group-active.json"
        flag = state_data_dir() / "frpc-group-enabled"
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
        if "proxy" not in installed_modules(prefix):
            raise RuntimeError("proxy nodes are not installed")
        return run_toggle(prefix, "proxy", enabled)
    if module in FEATURES:
        set_feature(prefix, module, enabled)
        return
    if module not in installed_modules(prefix):
        raise RuntimeError("module is not installed")
    if module == "iperf3":
        target = state_data_dir() / "iperf3-enabled"
        switch_web_setting(target, enabled)
        return
    unit = UNITS[module]
    nodes = []
    if module == "proxy":
        state = Path("/etc/vps-server-nodes/state.json")
        if state.is_file():
            nodes = [node for node in json.loads(state.read_text()).get("nodes", [])
                     if node.get("enabled", True)]
    registered = []
    optional_registered = []
    listener = managed_listener(module) if module in ("frps", "lucky", "tailscale") else None
    listener_registered = False
    if enabled:
        if listener:
            from console_port import reserve_owned_port
            listener_registered = reserve_owned_port(prefix, *listener)
        if module == "tailscale":
            try:
                optional_registered = reserve_saved_tailscale_ports(prefix)
            except BaseException:
                if listener_registered:
                    from console_port import release_owned_port
                    release_owned_port(prefix, *listener)
                raise
        if nodes:
            from node_control import _node_port_row
            try:
                for node in nodes:
                    if _node_port_row(node["port"], node["id"], True):
                        registered.append(node)
            except BaseException:
                for node in reversed(registered):
                    _node_port_row(node["port"], node["id"], False)
                if optional_registered:
                    from console_port import release_owned_port
                    for port, owner in reversed(optional_registered):
                        release_owned_port(prefix, port, owner)
                if listener_registered:
                    from console_port import release_owned_port
                    release_owned_port(prefix, *listener)
                raise
        try:
            subprocess.run(["systemctl", "enable", unit], check=True, timeout=30)
            if module != "proxy" or nodes:
                subprocess.run(["systemctl", "start", unit], check=True, timeout=60)
            if module == "tailscale":
                sync_tailscale_ports(prefix)
            if nodes:
                from node_control import HostBackend
                backend = HostBackend()
                for node in nodes:
                    backend.firewall(node["port"], True, node["protocol"])
        except BaseException:
            subprocess.run(["systemctl", "disable", "--now", unit], check=False, timeout=60)
            if listener:
                from console_port import release_owned_port
                release_owned_port(prefix, *listener)
            if optional_registered:
                from console_port import release_owned_port
                for port, owner in reversed(optional_registered):
                    release_owned_port(prefix, port, owner)
            if registered:
                from node_control import _node_port_row
                for node in reversed(registered):
                    _node_port_row(node["port"], node["id"], False)
            raise
    else:
        if module == "tailscale":
            try:
                snapshot_tailscale_ports()
            except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired):
                pass  # The last saved listener snapshot remains available.
        subprocess.run(["systemctl", "disable", "--now", unit], check=True, timeout=60)
        if module == "tailscale":
            release_tailscale_ports(prefix)
        if listener:
            from console_port import release_owned_port
            release_owned_port(prefix, *listener)
        if nodes:
            from node_control import HostBackend
            backend = HostBackend()
            for node in nodes:
                backend.firewall(node["port"], False, node["protocol"])
            from node_control import _node_port_row
            for node in nodes:
                _node_port_row(node["port"], node["id"], False)


def remove_owned_firewall_rule(owner):
    if not owner.is_file():
        return
    parts = owner.read_text().split()
    if len(parts) != 2 or not parts[1].isascii() or not parts[1].isdigit() or not 1 <= int(parts[1]) <= 65535:
        return
    backend, port = parts
    if backend == "ufw":
        subprocess.run(["ufw", "--force", "delete", "allow", f"{port}/tcp"], check=True, timeout=30)
    elif backend == "firewalld":
        subprocess.run(["firewall-cmd", "--permanent", f"--remove-port={port}/tcp"], check=True, timeout=30)
        subprocess.run(["firewall-cmd", "--reload"], check=True, timeout=30)
    else:
        return
    owner.unlink()


def managed_listener(module):
    """Return the main host listener managed by an optional service."""
    if module == "tailscale":
        return 41641, "vps-server / Tailscale"
    if module == "frps":
        import re
        content = Path("/etc/vps-server-frps/frps.toml").read_text()
        match = re.search(r"^bindPort\s*=\s*(\d+)\s*$", content, re.M)
        if match is None:
            raise ValueError("invalid FRPS bind port")
        return int(match.group(1)), "vps-server frps"
    if module == "lucky":
        data = json.loads(Path("/etc/vps-server-lucky/config.json").read_text())["BaseConfigure"]
        return int(data["AdminWebListenPort"]), "vps-server Lucky"
    return None


def sync_tailscale_ports(prefix):
    """Reserve persisted optional Tailscale listeners after its daemon starts."""
    from console_port import reserve_owned_port, release_owned_port
    from tailscale_control import prefs
    last_error = None
    for _ in range(15):
        try:
            settings = prefs()
            break
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
            last_error = exc
            time.sleep(0.2)
    else:
        raise RuntimeError("Tailscale preferences unavailable") from last_error
    choices = []
    if settings.get("webclient") is True:
        choices.append((5252, "vps-server Tailscale Web"))
    relay = str(settings.get("relay-server-port") or "")
    if relay:
        if not relay.isascii() or not relay.isdecimal() or not 1 <= int(relay) <= 65535:
            raise ValueError("invalid persisted peer relay port")
        choices.append((int(relay), "vps-server Tailscale Relay"))
    added = []
    try:
        for port, owner in choices:
            if reserve_owned_port(prefix, port, owner, probe=False):
                added.append((port, owner))
    except BaseException:
        for port, owner in reversed(added):
            release_owned_port(prefix, port, owner)
        raise
    snapshot_tailscale_ports(settings)


def snapshot_tailscale_ports(settings=None):
    from tailscale_control import prefs
    settings = prefs() if settings is None else settings
    relay = str(settings.get("relay-server-port") or "")
    if relay and (not relay.isascii() or not relay.isdecimal() or not 1 <= int(relay) <= 65535):
        raise ValueError("invalid persisted peer relay port")
    path = state_data_dir() / "tailscale-listeners.json"
    data = {"webclient": settings.get("webclient") is True, "relay_port": int(relay) if relay else None}
    staged = path.with_suffix(".tmp")
    staged.write_text(json.dumps(data) + "\n")
    os.chmod(staged, 0o600)
    os.replace(staged, path)


def reserve_saved_tailscale_ports(prefix):
    from console_port import reserve_owned_port, release_owned_port
    path = state_data_dir() / "tailscale-listeners.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text())
    if type(data.get("webclient")) is not bool or (data.get("relay_port") is not None and
            (type(data["relay_port"]) is not int or not 1 <= data["relay_port"] <= 65535)):
        raise ValueError("invalid Tailscale listener snapshot")
    choices = []
    if data["webclient"]:
        choices.append((5252, "vps-server Tailscale Web"))
    if data["relay_port"] is not None:
        choices.append((data["relay_port"], "vps-server Tailscale Relay"))
    added = []
    try:
        for port, owner in choices:
            if reserve_owned_port(prefix, port, owner):
                added.append((port, owner))
    except BaseException:
        for port, owner in reversed(added):
            release_owned_port(prefix, port, owner)
        raise
    return added


def release_tailscale_ports(prefix):
    from console_port import read_rows, write_rows
    root = Path(prefix).parent
    registry = root / "PORTS.md"
    with (root / ".ports.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows, _ = read_rows(registry)
        kept = [row for row in rows if row[1] not in
                ("vps-server Tailscale Web", "vps-server Tailscale Relay")]
        if len(kept) != len(rows):
            write_rows(registry, kept)


def run_uninstall(prefix, module):
    """Remove an optional module after retaining its configuration locally."""
    if module == "frpc":
        return uninstall_frpc(prefix)
    if module not in ("iperf3", "proxy_nodes", "frps", "lucky", "tailscale"):
        raise ValueError("module cannot be uninstalled separately")
    present = installed_modules(prefix)
    targets = ({"proxy"} & present) if module == "proxy_nodes" else {module} & present
    if not targets:
        raise RuntimeError("module is not installed")
    archive = state_data_dir() / f"module-backup-{module}-{int(time.time())}.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        paths = {"proxy": "/etc/vps-server-proxy",
                 "frps": "/etc/vps-server-frps", "lucky": "/etc/vps-server-lucky",
                 "tailscale": str(state_dir() / "tailscale")}
        for item in targets:
            path = Path(paths[item]) if item in paths else None
            if path and path.exists():
                output.add(path, arcname=f"etc/{path.name}")
        if module == "tailscale":
            memory = Path("/etc/systemd/system/vps-server-tailscale.service.d/30-memory.conf")
            if memory.is_file() and not memory.is_symlink():
                output.add(memory, arcname="etc/systemd/system/vps-server-tailscale.service.d/30-memory.conf")
        if module == "proxy_nodes":
            state_path = Path("/etc/vps-server-nodes/state.json")
            if state_path.is_file():
                output.add(state_path, arcname="etc/vps-server-nodes/state.json")
    os.chmod(archive, 0o600)
    print(f"Configuration backup: {archive}", flush=True)
    if module == "iperf3":
        switch_web_setting(state_data_dir() / "iperf3-enabled", False)
        bundled = Path(prefix) / "vendor" / "iperf3" / "iperf3"
        if bundled.is_file() and hashlib.sha256(bundled.read_bytes()).hexdigest() == IPERF_SHA256:
            bundled.unlink()
    elif module == "proxy_nodes":
        subprocess.run(["systemctl", "stop", "vps-server-node-meter.service"],
                       check=False, timeout=60)
        node_state = Path("/etc/vps-server-nodes/state.json")
        proxy_nodes = json.loads(node_state.read_text()).get("nodes", []) if node_state.is_file() else []
        script = Path(prefix) / "proxy" / "setup-proxy.sh"
        run_logged(["/usr/bin/bash", str(script), "uninstall"], timeout=180)
        from node_control import _node_port_row
        for node in proxy_nodes:
            _node_port_row(node["port"], node["id"], False)
        reconcile_removed_nodes(prefix, present - targets)
        if "proxy" not in (present - targets):
            subprocess.run(["systemctl", "disable", "--now", "vps-server-node-meter.service"],
                           check=False, timeout=60)
            subprocess.run([sys.executable, str(Path(prefix) / "src" / "web" / "nft_runtime.py"),
                            "delete-table"], check=False, timeout=20)
    elif module == "frps":
        subprocess.run(["systemctl", "disable", "--now", UNITS["frps"]], check=True, timeout=60)
        from console_port import release_owned_port
        release_owned_port(prefix, *managed_listener("frps"))
        remove_owned_firewall_rule(Path("/etc/vps-server-frps/firewall-owned"))
        Path(f"/etc/systemd/system/{UNITS['frps']}").unlink(missing_ok=True)
        subprocess.run(["systemctl", "daemon-reload"], check=True, timeout=30)
        # Keep bind port and token so a later reinstall can restore clients.
        Path("/usr/local/bin/frps-vps-server").unlink(missing_ok=True)
    elif module == "lucky":
        subprocess.run(["systemctl", "disable", "--now", UNITS["lucky"]], check=True, timeout=60)
        from console_port import release_owned_port
        release_owned_port(prefix, *managed_listener("lucky"))
        remove_owned_firewall_rule(Path("/etc/vps-server-lucky/firewall-owned"))
        Path(f"/etc/systemd/system/{UNITS['lucky']}").unlink(missing_ok=True)
        subprocess.run(["systemctl", "daemon-reload"], check=True, timeout=30)
        # Lucky owns DDNS and proxy settings; leave its config in place.
        Path("/usr/local/bin/lucky-vps-server").unlink(missing_ok=True)
    elif module == "tailscale":
        try:
            snapshot_tailscale_ports()
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired):
            pass
        subprocess.run(["systemctl", "disable", "--now", UNITS["tailscale"]], check=True, timeout=60)
        release_tailscale_ports(prefix)
        from console_port import release_owned_port
        release_owned_port(prefix, *managed_listener("tailscale"))
        Path(f"/etc/systemd/system/{UNITS['tailscale']}").unlink(missing_ok=True)
        subprocess.run(["systemctl", "daemon-reload"], check=True, timeout=30)
        # Keep device identity and tailnet settings for a later reinstall.
        Path("/usr/local/bin/tailscale-vps-server").unlink(missing_ok=True)
        Path("/usr/local/bin/tailscaled-vps-server").unlink(missing_ok=True)
    state = install_state_file()
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
    archive = state_data_dir() / f"module-backup-frpc-{int(time.time())}.tar.gz"
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
    owned = state_data_dir() / "frpc-binary-owned"
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
    if os.geteuid() != 0 or not (install_state_file()).is_file():
        raise SystemExit("root and an installed console are required")
    lock_path = state_data_dir() / "module-job.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        log = log_path(prefix)
        history = history_path(prefix)
        with log.open("w", encoding="utf-8", buffering=1) as current, \
                history.open("a", encoding="utf-8", buffering=1) as archive:
            os.chmod(log, 0o600)
            os.chmod(history, 0o600)
            output = JobOutput(current, archive)
            with redirect_stdout(output), redirect_stderr(output):
                print(f"=== {datetime.now(timezone.utc).isoformat(timespec='seconds')} {action} {module} ===", flush=True)
                save_status(prefix, module, "running", action=action)
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
                except Exception as exc:
                    print(f"Error: {type(exc).__name__}", flush=True)
                    save_status(prefix, module, "failed", action=action)
                    raise SystemExit(1)
                save_status(prefix, module, "done", action=action)
                print(f"Completed: {action} {module}", flush=True)


if __name__ == "__main__":
    main()
