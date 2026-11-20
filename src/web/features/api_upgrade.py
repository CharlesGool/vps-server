"""Upgrading this console to a newer release: the System page's card and the token API's ``upgrade``.

Both start ``upgrade.py`` in the transient unit ``vps-server-upgrade``, outside
the console's sandbox, with its output in ``<data dir>/upgrade-api.log``. It
verifies the signed release before it runs the release's installer, which
restarts the console on the way; the page waits for it to come back. The
package variant defaults to the one this host was installed from.
"""

import re
import shlex
import subprocess
import threading
import time
from pathlib import Path

import release_trust
import upgrade

UPGRADE_UNIT = "vps-server-upgrade"
VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")
LOG_NAME = "upgrade-api.log"
LOG_LINES = 40
EXIT_RE = re.compile(r"^exit (\d+)$", re.M)
# The page asks GitHub when it opens: short tries (a mainland host may not reach it at all),
# and the answer is kept a while, so reloading the page does not spend the API's hourly quota.
LATEST_TIMEOUT = 8
LATEST_CACHE_SECONDS = 600
_latest = {"at": 0.0, "tag": None}
_latest_lock = threading.Lock()


def unit_active(unit):
    try:
        state = subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True, timeout=10,
                               check=False).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False
    return state in ("active", "activating")


def log_path(context):
    return Path(context.DATA_DIR) / LOG_NAME


def status(context):
    """Whether an upgrade runs, the running version, the log's last lines and the last exit code."""
    try:
        text = log_path(context).read_text(errors="replace")
    except OSError:
        text = ""
    log = "\n".join(line for line in text.splitlines()[-LOG_LINES:]
                    if "password" not in line.lower() and "密码" not in line)
    running = unit_active(UPGRADE_UNIT)
    codes = EXIT_RE.findall(text)
    return {"running": running, "version": context.VERSION_LABEL, "log": log,
            "lastExit": int(codes[-1]) if codes and not running else None}


def start(context, version=None, variant=None):
    """Start upgrade.py in its own unit. None when started, else an error code: busy or failed."""
    if unit_active(UPGRADE_UNIT) or unit_active(upgrade.INSTALL_UNIT):
        return "busy"
    arguments = ["/usr/bin/python3", str(Path(context.WEB_CODE_DIR) / "upgrade.py")]
    if variant:
        arguments += ["--variant", variant]
    if version:
        arguments += ["--version", version]
    try:
        log_path(context).write_text("")    # no stale lines or exit code before the unit's shell starts
    except OSError:
        pass
    log = shlex.quote(str(log_path(context)))
    script =f'{" ".join(shlex.quote(part) for part in arguments)} > {log} 2>&1; echo "exit $?" >> {log}'
    try:
        result = subprocess.run(["systemd-run", "--quiet", "--collect", "--unit=" + UPGRADE_UNIT,
                                 "/bin/sh", "-c", script], capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return "failed"
    return "failed" if result.returncode else None


def latest(refresh=False, finder=None):
    """The latest release's tag, cached; raises upgrade.LatestError."""
    with _latest_lock:
        if not refresh and _latest["tag"] and time.monotonic() - _latest["at"] < LATEST_CACHE_SECONDS:
            return _latest["tag"]
    tag = (finder or upgrade.latest_tag)(upgrade.DEFAULT_REPO, timeout=LATEST_TIMEOUT)
    with _latest_lock:
        _latest.update(at=time.monotonic(), tag=tag)
    return tag


def newer(tag, current):
    """True when ``tag`` is newer than the running version, None when that is no release (a test build)."""
    if not re.fullmatch(r"\d+\.\d+\.\d+", current or ""):
        return None
    return release_trust.version_tuple(tag) > release_trust.version_tuple(current)


class UpgradeApiMixin:
    API_ROUTES_UPGRADE = {
        ("GET", "system/upgrade"): "api_system_upgrade",
        ("GET", "system/upgrade/latest"): "api_system_upgrade_latest",
        ("POST", "system/upgrade"): "api_system_upgrade_start",
    }

    def _upgrade_info(self):
        context = self.context
        info = status(context)
        info["variant"] = upgrade.installed_variant(context.BASE_DIR)
        # upgrade.py refuses a host without a pinned release key unless given a fingerprint.
        info["pinned"] = release_trust.read_pinned(context.STATE_DIR) is not None
        return info

    def api_system_upgrade(self):
        if not self._security_allowed():
            return
        return self.api_ok(self._upgrade_info())

    def api_system_upgrade_latest(self):
        if not self._security_allowed():
            return
        refresh = (self.query_params().get("refresh") or [""])[0] == "1"
        try:
            tag = latest(refresh)
        except upgrade.LatestError as error:
            return self.api_error(502, "latest_" + error.code, detail=error.detail[-300:])
        return self.api_ok({"latest": tag, "newer": newer(tag, self.context.VERSION)})

    def api_system_upgrade_start(self):
        if not self._security_allowed():
            return
        body = self.read_json()
        version = body.get("version") if body else None
        if body is None or version is not None and (not isinstance(version, str) or not VERSION_RE.match(version)):
            return self.api_error(400, "invalid_request")
        error = start(self.context, version)
        if error:
            return self.api_error(409 if error == "busy" else 500, error)
        self.audit("upgrade_console", version or "latest")
        return self.api_ok(self._upgrade_info())
