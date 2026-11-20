"""JSON API for the system pages: host name, processes, services and logs, listening ports,
package updates and SSH logins.

Reading happens here, in the sandboxed console (root, read-only file system).
Changes that write outside the console's own directories go through the
``sysadmin.py`` helper started with ``systemd-run``; systemctl talks to
systemd over D-Bus, so starting and stopping services works from here.
"""

import json
import os
import pwd
import re
import secrets
import shutil
import signal
import subprocess
import time
from pathlib import Path

APT_UNIT = "vps-server-apt-upgrade"
UNIT_RE = re.compile(r"^[A-Za-z0-9@._:\\-]{1,200}\.service$")
# The console's own unit: stopping or disabling it from the console would lock everyone out.
SELF_UNITS = {"vps-server-web.service", "vps-server.service"}
SSH_ACCEPTED = re.compile(r"Accepted (\S+) for (\S+) from (\S+) port (\d+)")
SSH_FAILED = re.compile(r"(?:Failed (\S+) for (?:invalid user )?(\S+)|Invalid user (\S*)) from (\S+) port (\d+)")
SS_USERS = re.compile(r'\("([^"]+)",pid=(\d+)')


def run_helper(context, request, timeout=120):
    """Run one sysadmin.py request outside the sandbox; the helper's JSON answer.

    A request that outlasts ``timeout`` seconds is stopped (its transient unit,
    not just the waiting systemd-run), so a long copy or extraction reported as
    timed out does not go on in the background: ``{"ok": false, "error": "timeout"}``.
    RuntimeMaxSec is the backstop should the console itself go away meanwhile.
    """
    staging = staging_dir(context)
    unit = "vps-server-admin-" + secrets.token_hex(6)
    try:
        result = subprocess.run(["systemd-run", "--quiet", "--wait", "--pipe", "--collect", "--unit=" + unit,
                                 f"--property=RuntimeMaxSec={int(timeout) + 30}",
                                 "/usr/bin/python3", str(context.WEB_CODE_DIR / "sysadmin.py"), "request",
                                 str(staging)],
                                input=json.dumps(request), capture_output=True, text=True, timeout=timeout,
                                check=False)
    except subprocess.TimeoutExpired:
        stop_unit(unit + ".service")
        return {"ok": False, "error": "timeout"}
    except (OSError, subprocess.SubprocessError):
        return {"ok": False, "error": "failed"}
    lines = result.stdout.strip().splitlines()
    try:
        answer = json.loads(lines[-1]) if lines else None
    except ValueError:
        answer = None
    return answer if isinstance(answer, dict) else {"ok": False, "error": "failed"}


def stop_unit(unit):
    """Stop a transient unit and wait for it to be gone (systemctl talks to systemd over D-Bus)."""
    try:
        subprocess.run(["systemctl", "stop", unit], capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


def staging_dir(context):
    path = Path(context.DATA_DIR) / "fm-staging"
    path.mkdir(mode=0o700, exist_ok=True)
    return path


# -- processes -----------------------------------------------------------------------

def _proc_times():
    times = {}
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        try:
            with open(f"/proc/{entry.name}/stat") as handle:
                text = handle.read()
        except OSError:
            continue
        rest = text[text.rfind(")") + 2:].split()
        times[int(entry.name)] = int(rest[11]) + int(rest[12])
    return times


def processes(sample=0.5):
    """Running processes with CPU % over ``sample`` seconds and resident memory."""
    first = _proc_times()
    total_first = sum(int(value) for value in open("/proc/stat").readline().split()[1:9])
    time.sleep(sample)
    second = _proc_times()
    total_second = sum(int(value) for value in open("/proc/stat").readline().split()[1:9])
    elapsed = max(total_second - total_first, 1)
    cores = os.cpu_count() or 1
    page = os.sysconf("SC_PAGE_SIZE")
    users, rows = {}, []
    for pid, ticks in second.items():
        try:
            with open(f"/proc/{pid}/stat") as handle:
                text = handle.read()
            status = open(f"/proc/{pid}/status").read()
            command = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode("utf-8", "replace").strip()
        except OSError:
            continue
        name = text[text.find("(") + 1:text.rfind(")")]
        rest = text[text.rfind(")") + 2:].split()
        uid = int(re.search(r"^Uid:\s+(\d+)", status, re.M).group(1)) if "Uid:" in status else 0
        if uid not in users:
            try:
                users[uid] = pwd.getpwuid(uid).pw_name
            except KeyError:
                users[uid] = str(uid)
        cpu = (ticks - first.get(pid, ticks)) * 100 * cores / elapsed
        rows.append({"pid": pid, "ppid": int(rest[1]), "name": name, "state": rest[0], "user": users[uid],
                     "cpu": round(cpu, 1), "memory": int(rest[21]) * page, "command": command[:500] or f"[{name}]"})
    return rows


# -- services ----------------------------------------------------------------------------

def services():
    try:
        units = subprocess.run(["systemctl", "list-units", "--type=service", "--all", "--plain", "--no-legend",
                                "--no-pager"], capture_output=True, text=True, timeout=15, check=False).stdout
        files = subprocess.run(["systemctl", "list-unit-files", "--type=service", "--plain", "--no-legend",
                                "--no-pager"], capture_output=True, text=True, timeout=15, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    enabled = {}
    for line in files.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            enabled[parts[0]] = parts[1]
    rows = {}
    for line in units.splitlines():
        parts = line.split(None, 4)
        if len(parts) >= 4 and parts[0].endswith(".service"):
            rows[parts[0]] = {"unit": parts[0], "load": parts[1], "active": parts[2], "sub": parts[3],
                              "description": parts[4] if len(parts) > 4 else "",
                              "enabled": enabled.get(parts[0], "")}
    for unit, state in enabled.items():
        if unit not in rows and "@" not in unit:
            rows[unit] = {"unit": unit, "load": "loaded", "active": "inactive", "sub": "dead", "description": "",
                          "enabled": state}
    return sorted(rows.values(), key=lambda row: row["unit"])


def service_log(unit, lines=200):
    try:
        return subprocess.run(["journalctl", "-u", unit, "-n", str(lines), "-o", "short-iso", "--no-pager"],
                              capture_output=True, text=True, timeout=15, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


# -- ports -------------------------------------------------------------------------------------

def listening_ports(registry_rows):
    owners = {port: owner for port, owner, _bind, _date in registry_rows}
    try:
        output = subprocess.run(["ss", "-H", "-lntup"], capture_output=True, text=True, timeout=10,
                                check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    rows, seen = [], set()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        protocol, local = parts[0], parts[4]
        address, _, port = local.rpartition(":")
        if not port.isdigit():
            continue
        address = address.strip("[]").split("%")[0]
        users = SS_USERS.findall(line)
        key = (protocol, address, port)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"protocol": protocol, "address": address or "*", "port": int(port),
                     "process": users[0][0] if users else "", "pid": int(users[0][1]) if users else None,
                     "owner": owners.get(int(port), "")})
    rows.sort(key=lambda row: (row["port"], row["protocol"]))
    return rows


# -- packages ---------------------------------------------------------------------------------------

def upgradable():
    """[(package, new version, old version)] from apt's cache, or None without apt."""
    if not shutil.which("apt"):
        return None
    try:
        output = subprocess.run(["apt", "list", "--upgradable"], capture_output=True, text=True, timeout=60,
                                check=False, env=dict(os.environ, LANG="C")).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    rows = []
    for line in output.splitlines():
        match = re.match(r"^(\S+?)/\S+\s+(\S+)\s+\S+\s+\[upgradable from: (\S+)\]", line)
        if match:
            rows.append({"package": match.group(1), "version": match.group(2), "current": match.group(3)})
    return rows


def apt_lists_age():
    """Seconds since apt-get update last ran, from its lists directory, or None."""
    try:
        return int(time.time() - Path("/var/lib/apt/lists").stat().st_mtime)
    except OSError:
        return None


# -- SSH logins ---------------------------------------------------------------------------------------

def ssh_logins(days=7, limit=3000):
    """Recent sshd logins: (successes, failures) newest first."""
    text = ""
    if shutil.which("journalctl"):
        try:
            text = subprocess.run(["journalctl", "_COMM=sshd", "--since", f"-{days}d", "-o", "short-iso",
                                   "--no-pager", "-n", str(limit)], capture_output=True, text=True, timeout=30,
                                  check=False).stdout
        except (OSError, subprocess.SubprocessError):
            text = ""
    if not text.strip():
        for name in ("/var/log/auth.log", "/var/log/secure"):
            try:
                text = "\n".join(Path(name).read_text(errors="replace").splitlines()[-limit:])
                break
            except OSError:
                continue
    accepted, failed = [], []
    for line in text.splitlines():
        stamp = line.split(" ", 1)[0]
        match = SSH_ACCEPTED.search(line)
        if match:
            accepted.append({"time": stamp, "method": match.group(1), "user": match.group(2), "ip": match.group(3)})
            continue
        match = SSH_FAILED.search(line)
        if match:
            failed.append({"time": stamp, "user": match.group(2) or match.group(3) or "", "ip": match.group(4)})
    accepted.reverse()
    failed.reverse()
    return accepted, failed


class SystemApiMixin:
    API_ROUTES_SYSTEM = {
        ("GET", "system"): "api_system",
        ("POST", "system/hostname"): "api_system_hostname",
        ("GET", "system/processes"): "api_system_processes",
        ("POST", "system/processes/kill"): "api_system_kill",
        ("GET", "system/services"): "api_system_services",
        ("POST", "system/services/action"): "api_system_service_action",
        ("GET", "system/services/log"): "api_system_service_log",
        ("GET", "system/ports"): "api_system_ports",
        ("GET", "system/updates"): "api_system_updates",
        ("POST", "system/updates/check"): "api_system_updates_check",
        ("POST", "system/updates/upgrade"): "api_system_updates_upgrade",
        ("GET", "visitors/ssh"): "api_system_ssh",
    }

    # -- overview --------------------------------------------------------------------------------

    def api_system(self):
        if not self._security_allowed():
            return
        release = {}
        for line in Path("/etc/os-release").read_text().splitlines() if Path("/etc/os-release").exists() else []:
            key, _, value = line.partition("=")
            release[key] = value.strip('"')
        uname = os.uname()
        return self.api_ok({"hostname": uname.nodename, "os": release.get("PRETTY_NAME", uname.sysname),
                            "kernel": uname.release, "arch": uname.machine})

    def api_system_hostname(self):
        if not self._security_allowed():
            return
        body = self.read_json()
        name = body.get("name") if body else None
        if not isinstance(name, str):
            return self.api_error(400, "invalid_request")
        answer = run_helper(self.context, {"action": "hostname", "name": name.strip()})
        if not answer.get("ok"):
            return self.api_error(400, answer.get("error", "failed"))
        self.audit("hostname_changed", f'{answer.get("old", "")} -> {answer.get("name", "")}')
        return self.api_system()

    # -- processes -----------------------------------------------------------------------------

    def api_system_processes(self):
        if not self._security_allowed():
            return
        return self.api_ok({"rows": processes(), "self": os.getpid()})

    def api_system_kill(self):
        if not self._security_allowed():
            return
        body = self.read_json()
        pid = body.get("pid") if body else None
        force = bool(body.get("force")) if body else False
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 1 or pid in (os.getpid(), os.getppid()):
            return self.api_error(400, "invalid_request")
        try:
            os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
        except ProcessLookupError:
            return self.api_error(404, "not_found")
        except PermissionError:
            return self.api_error(403, "failed")
        self.audit("process_killed", f"{pid}{' (SIGKILL)' if force else ''}")
        return self.api_ok()

    # -- services --------------------------------------------------------------------------------

    def api_system_services(self):
        if not self._security_allowed():
            return
        return self.api_ok({"rows": services(), "protected": sorted(SELF_UNITS)})

    def api_system_service_action(self):
        if not self._security_allowed():
            return
        body = self.read_json()
        unit, action = (body.get("unit"), body.get("action")) if body else (None, None)
        if not isinstance(unit, str) or not UNIT_RE.match(unit) or action not in (
                "start", "stop", "restart", "enable", "disable"):
            return self.api_error(400, "invalid_request")
        if unit in SELF_UNITS and action in ("stop", "disable"):
            return self.api_error(400, "service_protected")
        command = ["systemctl", action, unit] if action in ("start", "stop", "enable", "disable") else \
            ["systemctl", "restart", unit]
        if unit in SELF_UNITS and action == "restart":
            command.insert(1, "--no-block")
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
        except (OSError, subprocess.SubprocessError):
            return self.api_error(500, "failed")
        if result.returncode:
            return self.api_error(400, "service_failed", detail=result.stderr.strip()[-300:])
        self.audit("service_" + action, unit)
        return self.api_system_services()

    def api_system_service_log(self):
        if not self._security_allowed():
            return
        unit = (self.query_params().get("unit") or [""])[0]
        if not UNIT_RE.match(unit):
            return self.api_error(400, "invalid_request")
        return self.api_ok({"unit": unit, "text": service_log(unit)})

    # -- ports ---------------------------------------------------------------------------------------

    def api_system_ports(self):
        if not self._security_allowed():
            return
        try:
            rows = self.context.console_port_rows(self.context.BASE_DIR.parent / "PORTS.md")[0]
        except (OSError, ValueError):
            rows = []
        return self.api_ok({"rows": listening_ports(rows)})

    # -- updates ---------------------------------------------------------------------------------------

    def _apt_log(self):
        return Path(self.context.DATA_DIR) / "apt-upgrade.log"

    def _apt_running(self):
        try:
            state = subprocess.run(["systemctl", "is-active", APT_UNIT], capture_output=True, text=True,
                                   timeout=10, check=False).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return False
        return state in ("active", "activating")

    def api_system_updates(self):
        if not self._security_allowed():
            return
        rows = upgradable()
        log = ""
        try:
            log = "\n".join(self._apt_log().read_text(errors="replace").splitlines()[-200:])
        except OSError:
            pass
        last = re.findall(r"^exit (\d+)$", log, re.M)
        return self.api_ok({"supported": rows is not None, "packages": rows or [], "listsAge": apt_lists_age(),
                            "running": self._apt_running(), "log": log,
                            "lastExit": int(last[-1]) if last else None})

    def api_system_updates_check(self):
        if not self._security_allowed():
            return
        if self._apt_running():
            return self.api_error(409, "busy")
        answer = run_helper(self.context, {"action": "apt-refresh"}, timeout=320)
        if not answer.get("ok"):
            return self.api_error(400, answer.get("error", "failed"))
        return self.api_system_updates()

    def api_system_updates_upgrade(self):
        if not self._security_allowed():
            return
        if self._apt_running():
            return self.api_error(409, "busy")
        try:
            result = subprocess.run(["systemd-run", "--quiet", "--collect", "--unit=" + APT_UNIT,
                                     "/usr/bin/python3", str(self.context.WEB_CODE_DIR / "sysadmin.py"),
                                     "apt-upgrade", str(self._apt_log())],
                                    capture_output=True, text=True, timeout=30, check=False)
        except (OSError, subprocess.SubprocessError):
            return self.api_error(500, "failed")
        if result.returncode:
            return self.api_error(500, "failed")
        self.audit("packages_upgrade")
        time.sleep(1)
        return self.api_system_updates()

    # -- SSH ---------------------------------------------------------------------------------------

    def api_system_ssh(self):
        """SSH logins, shown on the recent visits page (no admin check, like the visitor list)."""
        if self._visitors_closed():
            return
        accepted, failed = ssh_logins()
        counts = {}
        for row in failed:
            counts[row["ip"]] = counts.get(row["ip"], 0) + 1
        top = sorted(counts.items(), key=lambda item: -item[1])[:10]
        return self.api_ok({"accepted": accepted[:200], "failed": failed[:200], "failedTotal": len(failed),
                            "topFailed": [{"ip": ip, "count": count} for ip, count in top]})
