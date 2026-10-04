"""Stable paths for host-local state, independent of the installed code tree."""

import os
import json
from pathlib import Path


DEFAULT_STATE_DIR = Path("/var/lib/vps-server")
STATE_LOCATOR = Path("/etc/vps-server/state-dir")


def state_dir():
    value = os.environ.get("VPSSRV_STATE_DIR", "").strip()
    if not value and STATE_LOCATOR.is_file():
        value = STATE_LOCATOR.read_text(encoding="utf-8").strip()
    path = Path(value) if value else DEFAULT_STATE_DIR
    if not path.is_absolute():
        raise ValueError("state directory must be absolute")
    return path


def _path(name, default):
    value = os.environ.get(name)
    if not value:
        record = state_dir() / "paths.json"
        if record.is_file():
            data = json.loads(record.read_text(encoding="utf-8"))
            value = data.get(name)
    path = Path(value) if value else default
    if not path.is_absolute():
        raise ValueError("persistent path must be absolute")
    return path


def data_dir():
    return _path("VPSSRV_DATA_DIR", state_dir() / "data")


def password_file():
    return _path("VPSSRV_PASSWORD_FILE", state_dir() / "admin_password.txt")


def console_port_file():
    return _path("VPSSRV_CONSOLE_PORT_FILE", state_dir() / "console_port.txt")


def cert_dir():
    return _path("VPSSRV_CERT_DIR", state_dir() / "certs")


def install_state_file():
    return state_dir() / "install-state"
