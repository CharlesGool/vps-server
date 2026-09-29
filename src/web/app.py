#!/usr/bin/env python3
"""vps-server: public reachability page, speed-test console, iperf3 window.

Three listeners in one process, served by two request handlers:

  ProbeHandler    ports 80 and 443, no authentication. Serves one page that
                  says "you reached this host", echoes the caller's source
                  address, and discloses nothing else about the machine.
  ConsoleHandler  a persisted random high port, password-protected. Browser
                  speed test, visitor log, and the iperf3 window control.

The split is a security property, not an organisational one: a request
arriving on 80/443 cannot reach a console route because ProbeHandler has no
such route — not because a check rejected it. An authorization check can be
bugged into allowing; an absent route cannot. See doc/LOG.md#decisions (2026-09-12)
before considering merging the two.

Standard-library only (see doc/LOG.md#decisions). Run with `python3 app.py`.
"""

import base64
import fcntl
import hmac
import html
import http.cookies
import ipaddress
import json
import os
import re
import secrets
import shutil
import signal
import socket
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def load_dotenv(path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


# Checkout imports src.web.app (or runs src/web/app.py); deployment copies this
# implementation to the root as app.py without the checkout entry.
BASE_DIR = Path(__file__).resolve().parent
if BASE_DIR.parent.name == "src" and (BASE_DIR.parent.parent / "README.md").is_file():
    BASE_DIR = BASE_DIR.parent.parent
# The same modules live beside app.py after installation and under src/web in
# a checkout. Keep their imports independent of the caller's working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from node_state import read_inventory, _read_json
from node_inventory import advance_reset_interval, reset_interval
from module_manager import MODULES as MANAGED_MODULES, UNITS as MANAGED_UNITS
from module_manager import FEATURES as MANAGED_FEATURES, GROUPS as MANAGED_GROUPS
from module_manager import feature_enabled as module_feature_enabled, log_path as module_log_path
from module_manager import installed_modules, save_status as save_module_status
from module_manager import status_path as module_status_path
from frp_control import (client_names as frpc_names, client_path as frpc_path,
                         client_summary as frpc_summary, structured_client as frpc_structured,
                         build_client as frpc_build)


def _read_version():
    """The version this build actually is, from the VERSION file beside us.

    Not a constant in this file, on purpose. A hand-written one is wrong the
    moment somebody tags a release and forgets to edit it, and nothing
    reports that — the console just keeps claiming the previous version to
    whoever is looking at it three deploys later.

    An in-place Git checkout reports its exact release tag or dev-<short sha>.
    A flat deployment reads the version stamped by install.sh, or the
    committed release copy when Git metadata is absent. A build that cannot
    establish what it is says so rather than guessing.
    """
    installed_stamp = BASE_DIR / "VERSION"
    if installed_stamp.is_file():
        try:
            return installed_stamp.read_text().strip() or "dev-unknown"
        except OSError:
            return "dev-unknown"
    if (BASE_DIR / ".git").exists():
        tag = subprocess.run(["git", "-C", str(BASE_DIR), "describe", "--tags",
                              "--exact-match", "HEAD"], capture_output=True,
                             text=True, timeout=5, check=False)
        if tag.returncode == 0 and tag.stdout.strip():
            return tag.stdout.strip().removeprefix("v")
        revision = subprocess.run(["git", "-C", str(BASE_DIR), "rev-parse",
                                   "--short=7", "HEAD"], capture_output=True,
                                  text=True, timeout=5, check=False)
        if revision.returncode == 0 and re.fullmatch(r"[0-9a-f]{7,}", revision.stdout.strip()):
            return "dev-" + revision.stdout.strip()
    try:
        value = (BASE_DIR / "config" / "VERSION").read_text().strip()
    except OSError:
        return "dev-unknown"
    return value or "dev-unknown"


def display_version(version):
    return version if version.startswith(("dev-", "test-")) else f"v{version}"


VERSION = _read_version()
VERSION_LABEL = display_version(VERSION)

load_dotenv(BASE_DIR / ".env")

def _load_strings():
    """Load reviewed interface catalogs from the checkout or installed prefix."""
    files = {"en": "en", "zh_cn": "zh-CN", "zh_tw": "zh-TW",
             "zh_hk": "zh-HK", "hi": "hi", "es": "es", "ar": "ar", "fr": "fr"}
    catalogs = {}
    for code, tag in files.items():
        with (BASE_DIR / "lang" / "web" / f"{tag}.json").open(encoding="utf-8") as source:
            catalog = json.load(source)
        if not isinstance(catalog, dict) or not all(isinstance(key, str) and isinstance(value, str)
                                                     for key, value in catalog.items()):
            raise ValueError(f"invalid interface catalog: {tag}")
        catalogs[code] = catalog
    keys = set(catalogs["en"])
    if any(set(catalog) != keys for catalog in catalogs.values()):
        raise ValueError("interface catalog keys differ across languages")
    return catalogs


STRINGS = _load_strings()

# With no cookie/query/matching Accept-Language, fall back to this. Validated
# against STRINGS so a typo'd VPSSRV_DEFAULT_LANG can't 500 the whole app.
DEFAULT_LANG = os.environ.get("VPSSRV_DEFAULT_LANG", "en")
if DEFAULT_LANG not in STRINGS:
    DEFAULT_LANG = "en"



def _log_text(key, **values):
    """Format an operator-visible diagnostic in the configured language."""
    return STRINGS[DEFAULT_LANG][key].format(**values)

HOST = os.environ.get("VPSSRV_HOST", "0.0.0.0")
DATA_DIR = Path(os.environ.get("VPSSRV_DATA_DIR", str(BASE_DIR / "data")))
TRUST_PROXY = os.environ.get("VPSSRV_TRUST_PROXY", "0") == "1"
MAX_TEST_MB = int(os.environ.get("VPSSRV_MAX_TEST_MB", "200"))

# TLS for the console. Off by default: the only certificate this app can
# produce on its own is self-signed, and that means a browser warning to click
# through on every fresh browser for no authentication benefit. Set
# VPSSRV_CONSOLE_TLS=1 to serve the console over HTTPS too (self-signed unless
# VPSSRV_TLS_CERT/VPSSRV_TLS_KEY point at a real certificate).
CONSOLE_TLS = os.environ.get("VPSSRV_CONSOLE_TLS", "0") == "1"
# The console port is resolved by ensure_console_port() further down (it needs
# _write_secret_file, defined below) — with no VPSSRV_CONSOLE_PORT set it
# generates and persists a random port rather than defaulting to 80 or 443,
# which now belong to the public page.
CONSOLE_PORT_FILE = Path(
    os.environ.get("VPSSRV_CONSOLE_PORT_FILE", str(BASE_DIR / "console_port.txt"))
)
CERT_DIR = Path(os.environ.get("VPSSRV_CERT_DIR", str(BASE_DIR / "certs")))
TLS_CERT = os.environ.get("VPSSRV_TLS_CERT", "")
TLS_KEY = os.environ.get("VPSSRV_TLS_KEY", "")

# The public reachability page. Unlike everything else in this file it is meant
# to be found: it answers "are this host's web ports reachable from where you
# are", and that only works if a stranger holding nothing but the IP can load
# it. Hence no auth, and hence the two best-known ports.
#
# There is deliberately no HTTP-to-HTTPS redirect. Upstream had one, but
# redirecting port 80 would destroy the very thing being measured — whether 80
# itself is reachable — by turning a successful plain-HTTP fetch into a hop to
# a port that may well be blocked.
PUBLIC_MODULE_SWITCH = BASE_DIR / "data" / "web-public-enabled"
PUBLIC_ENABLED = (PUBLIC_MODULE_SWITCH.read_text().strip() == "1" if PUBLIC_MODULE_SWITCH.exists()
                  else os.environ.get("VPSSRV_PUBLIC_ENABLE", "1") == "1")
PUBLIC_HTTP_PORT = int(os.environ.get("VPSSRV_PUBLIC_HTTP_PORT", "80"))
PUBLIC_HTTPS_PORT = int(os.environ.get("VPSSRV_PUBLIC_HTTPS_PORT", "443"))

# Speed-test tuning. Defaults follow LibreSpeed's methodology: several parallel
# streams, a duration-based measurement window, and a warmup/grace period whose
# bytes are discarded so TCP slow-start doesn't drag the number down.
TEST_SECONDS = int(os.environ.get("VPSSRV_TEST_SECONDS", "10"))
WARMUP_SECONDS = float(os.environ.get("VPSSRV_WARMUP_SECONDS", "2"))
DOWNLOAD_STREAMS = int(os.environ.get("VPSSRV_DOWNLOAD_STREAMS", "6"))
UPLOAD_STREAMS = int(os.environ.get("VPSSRV_UPLOAD_STREAMS", "3"))
PING_SAMPLES = int(os.environ.get("VPSSRV_PING_SAMPLES", "20"))
OVERHEAD_FACTOR = 1.06  # compensate for TCP/IP/HTTP header overhead

# Connection tracking: poll the kernel TCP table so the visitor log covers
# every device reaching this host, not only those that opened this web page.
TRACK_CONNECTIONS = os.environ.get("VPSSRV_TRACK_CONNECTIONS", "1") == "1"
CONN_POLL_SECONDS = float(os.environ.get("VPSSRV_CONN_POLL_SECONDS", "5"))

# The admin password lives next to the app by default so it is easy to find
# and edit when deploying on another machine (VPSSRV_PASSWORD_FILE overrides).
PASSWORD_FILE = Path(os.environ.get("VPSSRV_PASSWORD_FILE", str(BASE_DIR / "admin_password.txt")))
IP_ALLOWLIST_FILE = Path(os.environ.get("VPSSRV_IP_ALLOWLIST_FILE") or
                         str(DATA_DIR / "login-access.json"))
# Login can be turned off at install time (see install.sh) for setups relying
# on the random port alone. The password file is still generated either way
# so flipping this back on later doesn't require a restart-time prompt.
AUTH_ENABLED = os.environ.get("VPSSRV_AUTH", "1") == "1"

# Login rate limiting — defensive depth, not a fix for a real hole: the
# generated password is secrets.token_urlsafe(15), already far out of brute
# force reach. This only slows down noise and gives a floor against a
# password chosen by hand instead of generated. See doc/LOG.md#decisions (2026-09-22).
LOGIN_MAX_ATTEMPTS = int(os.environ.get("VPSSRV_LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_WINDOW_SECONDS = int(os.environ.get("VPSSRV_LOGIN_WINDOW_SECONDS", "60"))
LOGIN_LOCKOUT_SECONDS = int(os.environ.get("VPSSRV_LOGIN_LOCKOUT_SECONDS", "30"))

# iperf3 window. There is no "leave it running" option on purpose: an
# unauthenticated public `iperf3 -s` lets any stranger saturate the uplink for
# as long as they like, and nothing about the host surfaces that it is
# happening. See doc/LOG.md#decisions (2026-09-12).
IPERF_MODULE_SWITCH = BASE_DIR / "data" / "iperf3-enabled"
IPERF_ENABLED = (IPERF_MODULE_SWITCH.read_text().strip() == "1" if IPERF_MODULE_SWITCH.exists()
                 else os.environ.get("VPSSRV_IPERF_ENABLE", "1") == "1")
IPERF_PORT = int(os.environ.get("VPSSRV_IPERF_PORT", "5201"))
IPERF_PORT_FILE = DATA_DIR / "iperf-port.txt"
IPERF_DEFAULT_MINUTES = int(os.environ.get("VPSSRV_IPERF_DEFAULT_MINUTES", "10"))
IPERF_MAX_MINUTES = int(os.environ.get("VPSSRV_IPERF_MAX_MINUTES", "60"))

# Port forwarding. Unlike the iperf3 window, a forward is configuration, not a
# timed loan of the uplink — it is meant to still be there after a restart or
# a reboot. See PortForwardManager for how that is reconciled with rules
# living in the kernel, which remembers nothing on its own.
PORTFWD_ALLOWED = os.environ.get("VPSSRV_PORTFWD_ENABLE", "1") == "1"


def portfwd_enabled():
    return PORTFWD_ALLOWED and module_feature_enabled(BASE_DIR, "portfwd")
PORTFWD_MAX_RULES = int(os.environ.get("VPSSRV_PORTFWD_MAX_RULES", "20"))

DATA_DIR.mkdir(parents=True, exist_ok=True)
os.chmod(DATA_DIR, 0o700)

SECRET_FILE = DATA_DIR / "session_secret.txt"
DB_FILE = DATA_DIR / "visitors.db"
PORTFWD_STATE_FILE = DATA_DIR / "portfwd.json"

SESSION_TTL_SECONDS = 12 * 3600
SECURITY_PERMISSION_SECONDS = 10 * 60
MAX_VISITOR_ROWS = 1000
DOWNLOAD_CHUNK = 1024 * 1024  # 1 MiB fill buffer, repeated to build the response
LOGIN_BODY_LIMIT = 4096


def _write_secret_file(path, value):
    path.write_text(value + "\n")
    os.chmod(path, 0o600)


def ensure_admin_password():
    if PASSWORD_FILE.exists():
        return PASSWORD_FILE.read_text().strip()
    password = secrets.token_urlsafe(15)
    _write_secret_file(PASSWORD_FILE, password)
    print(_log_text('log_admin_password', path=PASSWORD_FILE), file=sys.stderr)
    return password


def normalized_ip(value):
    """One canonical host address, never a CIDR, zone ID, or forwarded chain."""
    if not isinstance(value, str) or value != value.strip() or "%" in value:
        raise ValueError("invalid IP address")
    address = ipaddress.ip_address(value)
    return str(address.ipv4_mapped or address) if isinstance(address, ipaddress.IPv6Address) else str(address)


_PRIVATE_LOGIN_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7"))


def normalized_private_ip(value):
    canonical = normalized_ip(value)
    if not any(ipaddress.ip_address(canonical) in network for network in _PRIVATE_LOGIN_NETWORKS):
        raise ValueError("public or non-LAN IP address")
    return canonical


def _atomic_private_text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".access-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(value)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


class IpAllowlist:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.addresses = set()
        self.enabled = True
        self.load_error = False
        if self.path.exists():
            try:
                document = json.loads(self.path.read_text(encoding="utf-8"))
                if (not isinstance(document, dict) or
                        set(document) not in ({"allowed_ips"}, {"allowed_ips", "enabled"}) or
                        not isinstance(document.get("enabled", True), bool) or
                        not isinstance(document["allowed_ips"], list) or
                        any(normalized_private_ip(item) != item for item in document["allowed_ips"]) or
                        len(document["allowed_ips"]) != len(set(document["allowed_ips"]))):
                    raise ValueError("invalid IP allowlist")
                self.addresses = set(document["allowed_ips"])
                self.enabled = document.get("enabled", True)
            except (OSError, ValueError, TypeError):
                self.load_error = True

    def contains(self, address):
        try:
            canonical = normalized_private_ip(address)
        except ValueError:
            return False
        with self.lock:
            return self.enabled and canonical in self.addresses

    def is_enabled(self):
        with self.lock:
            return self.enabled

    def set_enabled(self, enabled):
        if not isinstance(enabled, bool):
            raise ValueError("invalid IP access setting")
        with self.lock:
            _atomic_private_text(self.path, json.dumps({"allowed_ips": sorted(self.addresses),
                                                       "enabled": enabled}) + "\n")
            self.enabled = enabled
            self.load_error = False

    def list_addresses(self):
        with self.lock:
            return sorted(self.addresses, key=lambda value: (ipaddress.ip_address(value).version,
                                                               int(ipaddress.ip_address(value))))

    def change(self, address, *, add):
        canonical = normalized_private_ip(address)
        with self.lock:
            candidate = set(self.addresses)
            if add:
                if len(candidate) >= 64 and canonical not in candidate:
                    raise ValueError("IP allowlist is full")
                candidate.add(canonical)
            else:
                if canonical not in candidate:
                    raise ValueError("IP address is not listed")
                candidate.remove(canonical)
            if candidate != self.addresses:
                _atomic_private_text(self.path, json.dumps({"allowed_ips": sorted(candidate),
                                                           "enabled": self.enabled}) + "\n")
                self.addresses = candidate
                self.load_error = False
        return canonical


def ensure_console_port():
    """Explicit VPSSRV_CONSOLE_PORT always wins and is never persisted.
    Otherwise pick a random port once and remember it — regenerating on every
    restart would make the console impossible to find again.
    """
    # "0" means auto, the same as unset — which is what .env.example ships and
    # what the documentation has always said. Treating it as a literal port
    # number binds port 0, and the kernel then hands out a different ephemeral
    # port on every restart, none of them written to the port file. Anyone who
    # copied .env.example to .env got a console that moved every time the
    # service restarted and a summary that could not name it.
    env_port = os.environ.get("VPSSRV_CONSOLE_PORT", "").strip()
    if env_port and env_port != "0":
        return int(env_port)
    if CONSOLE_PORT_FILE.exists():
        return int(CONSOLE_PORT_FILE.read_text().strip())
    port = 20000 + secrets.randbelow(40000)  # 20000-59999
    _write_secret_file(CONSOLE_PORT_FILE, str(port))
    print(_log_text('log_console_port', port=port, path=CONSOLE_PORT_FILE), file=sys.stderr)
    return port


def ensure_session_secret():
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text().strip()
    secret = secrets.token_hex(32)
    _write_secret_file(SECRET_FILE, secret)
    return secret


def ensure_tls_files():
    """Return (cert_path, key_path), generating a self-signed pair if needed.

    Uses the `openssl` CLI because the standard library can't create
    certificates and this project has no third-party dependencies; openssl is
    part of a Debian/Ubuntu base install. See doc/LOG.md#decisions.
    """
    if TLS_CERT and TLS_KEY:
        cert, key = Path(TLS_CERT), Path(TLS_KEY)
        if not cert.exists() or not key.exists():
            raise SystemExit(
                f"VPSSRV_TLS_CERT/VPSSRV_TLS_KEY were set but not found: {cert}, {key}"
            )
        return cert, key

    CERT_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CERT_DIR, 0o700)
    cert, key = CERT_DIR / "cert.pem", CERT_DIR / "key.pem"
    if cert.exists() and key.exists():
        return cert, key

    if not shutil.which("openssl"):
        raise SystemExit(
            "openssl not found — install it (apt install openssl), or point "
            "VPSSRV_TLS_CERT/VPSSRV_TLS_KEY at an existing certificate, or set "
            "VPSSRV_CONSOLE_TLS=0 to serve plain HTTP."
        )
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key), "-out", str(cert),
            "-days", "3650", "-subj", "/CN=vps-server",
            "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.chmod(key, 0o600)
    os.chmod(cert, 0o644)
    print(_log_text('log_certificate', path=CERT_DIR), file=sys.stderr)
    return cert, key


ADMIN_PASSWORD = ensure_admin_password()
IP_ALLOWLIST = IpAllowlist(IP_ALLOWLIST_FILE)
CONSOLE_PORT = ensure_console_port()
SESSION_SECRET = ensure_session_secret()
FILL_BUFFER = os.urandom(DOWNLOAD_CHUNK)

# ---------------------------------------------------------------------------
# Firewall — best effort, for the transient iperf3 port only
#
# Rules are added to the running configuration only, never persisted. That
# matches the window itself: both are gone after a reboot, and neither can
# leave the port open because something crashed before tidying up.
# ---------------------------------------------------------------------------


def _cmd_output(cmd):
    """Stdout of `cmd` if it succeeded, empty string otherwise. Never raises."""
    try:
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            check=False, text=True,
        )
    except OSError:
        return ""
    return result.stdout if result.returncode == 0 else ""


def _run_quiet(cmd):
    try:
        return subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
        ).returncode == 0
    except OSError:
        return False


def module_states(installed=None):
    installed = installed if installed is not None else installed_modules(BASE_DIR)
    states = {
        "speedtest": module_feature_enabled(BASE_DIR, "speedtest"),
        "iperf3": "iperf3" in installed and IPERF_ENABLED,
        "proxy_nodes": any(_run_quiet(["systemctl", "is-enabled", "--quiet", MANAGED_UNITS[item]])
                           for item in ("proxy", "anytls") if item in installed),
        "frps": "frps" in installed and _run_quiet(
            ["systemctl", "is-enabled", "--quiet", MANAGED_UNITS["frps"]]),
        "frpc": any(_run_quiet(["systemctl", "is-active", "--quiet", f"frpc@{name}.service"])
                    for name in frpc_names()),
        "portfwd": portfwd_enabled(),
        "visitors": module_feature_enabled(BASE_DIR, "visitors"),
        "changelog": module_feature_enabled(BASE_DIR, "changelog"),
    }
    states["frp"] = states["frps"] or states["frpc"]
    return states


def firewall_backend():
    """Which firewall is actually running, or None.

    `ufw status` exits 0 whether or not ufw is enabled, so the exit code alone
    would happily "open" a port in a firewall that is not filtering anything
    and report success.
    """
    if shutil.which("ufw") and "Status: active" in _cmd_output(["ufw", "status"]):
        return "ufw"
    if shutil.which("firewall-cmd") and _cmd_output(["firewall-cmd", "--state"]).strip() == "running":
        return "firewalld"
    if shutil.which("iptables"):
        return "iptables"
    return None


def firewall_port(port, opening):
    """Open or close `port`/tcp. Best effort; returns True if a rule was applied.

    A host with no firewall, or one managed by something not handled here,
    must still get a usable window — so a failure is reported to stderr and
    otherwise ignored rather than blocking the operator.
    """
    backend = firewall_backend()
    if backend == "ufw":
        cmd = ["ufw", "allow", f"{port}/tcp"] if opening else \
              ["ufw", "delete", "allow", f"{port}/tcp"]
    elif backend == "firewalld":
        flag = "--add-port" if opening else "--remove-port"
        cmd = ["firewall-cmd", f"{flag}={port}/tcp"]
    elif backend == "iptables":
        flag = "-I" if opening else "-D"
        cmd = ["iptables", flag, "INPUT", "-p", "tcp", "--dport", str(port),
               "-j", "ACCEPT"]
    else:
        return False
    if _run_quiet(cmd):
        return True
    print(_log_text('log_firewall_open' if opening else 'log_firewall_close', port=port, backend=backend), file=sys.stderr)
    return False


# ---------------------------------------------------------------------------
# iperf3 window
# ---------------------------------------------------------------------------


class IperfWindow:
    """A time-boxed `iperf3 -s`, opened from the console and self-closing.

    The state lives in memory and nowhere else. If the service dies, the
    window dies with it — the safe direction to fail. A restart never
    resurrects a window somebody opened and forgot about.
    """

    def __init__(self, port, max_minutes, port_file=None):
        self._port_file = Path(port_file) if port_file else None
        self._port = port
        if self._port_file and self._port_file.exists():
            try:
                saved = int(self._port_file.read_text().strip())
                if 1 <= saved <= 65535:
                    self._port = saved
            except (OSError, ValueError):
                pass
        self._max_minutes = max_minutes
        self._lock = threading.RLock()
        self._proc = None
        self._deadline = 0.0
        self._timer = None

    @property
    def port(self):
        with self._lock:
            return self._port

    def set_port(self, port, commit=None):
        """Change the port while closed; persist it for the next restart."""
        if type(port) is not int or not 1 <= port <= 65535:
            return False
        with self._lock:
            self._reap()
            if self._proc is not None:
                return False
            if commit is not None:
                if not commit(self._port):
                    return False
            elif self._port_file:
                stage = self._port_file.with_suffix(".tmp")
                try:
                    stage.write_text(str(port) + "\n")
                    os.chmod(stage, 0o600)
                    stage.replace(self._port_file)
                except OSError:
                    stage.unlink(missing_ok=True)
                    return False
            self._port = port
            return True

    def state(self):
        """(is_open, remaining_seconds), reaping an iperf3 that died on its own."""
        with self._lock:
            self._reap()
            if self._proc is None:
                return False, 0
            return True, max(0, int(self._deadline - time.time()))

    def open(self, minutes):
        """Open or extend a window. Returns (ok, key) where key is a STRINGS key."""
        if not IPERF_ENABLED:
            return False, "iperf_disabled"
        if not shutil.which("iperf3"):
            return False, "iperf_missing"
        try:
            minutes = int(minutes)
        except (TypeError, ValueError):
            minutes = IPERF_DEFAULT_MINUTES
        minutes = max(1, min(minutes, self._max_minutes))

        with self._lock:
            self._reap()
            if self._proc is not None:
                # Already open. Extend it instead of spawning a second server
                # on the same port, which would only fail to bind.
                self._deadline = time.time() + minutes * 60
                self._arm()
                return True, "iperf_extended"
            try:
                proc = subprocess.Popen(
                    ["iperf3", "--server", "--port", str(self._port)],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError:
                return False, "iperf_missing"
            # iperf3 exits straight away if the port is taken. Without this
            # pause the console would report an open window that is not
            # listening to anything.
            time.sleep(0.3)
            if proc.poll() is not None:
                return False, "iperf_port_busy"
            self._proc = proc
            self._deadline = time.time() + minutes * 60
            firewall_port(self._port, opening=True)
            self._arm()
            return True, "iperf_opened"

    def close(self):
        with self._lock:
            self._close()

    # -- internals; every one of these runs under self._lock ---------------

    def _arm(self):
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(
            max(0.0, self._deadline - time.time()), self._expire
        )
        self._timer.daemon = True
        self._timer.start()

    def _expire(self):
        with self._lock:
            # An open() between this timer firing and acquiring the lock may
            # have pushed the deadline out. Only close if time really is up.
            if self._proc is not None and time.time() >= self._deadline - 0.5:
                self._close()

    def _reap(self):
        if self._proc is not None and self._proc.poll() is not None:
            self._proc = None
            self._deadline = 0.0
            firewall_port(self._port, opening=False)

    def _close(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        proc, self._proc = self._proc, None
        self._deadline = 0.0
        if proc is None:
            return
        # Withdraw the rule whatever happens to the process. A child that will
        # not die within ten seconds is a problem; a firewall left open for a
        # window this object already reports as closed is a worse one, and
        # letting TimeoutExpired escape here produced exactly that — the state
        # said shut, the port stayed open.
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(_log_text('log_iperf_stuck', pid=proc.pid), file=sys.stderr)
        finally:
            firewall_port(self._port, opening=False)


IPERF_WINDOW = IperfWindow(IPERF_PORT, IPERF_MAX_MINUTES, IPERF_PORT_FILE)

# ---------------------------------------------------------------------------
# Port forwarding — persistent iptables DNAT rules, console-managed
#
# A forward relays a public TCP/UDP port on this host to a device reachable
# over Tailscale or the LAN — the way a box with a public IP can stand in for
# one that has none. Unlike the iperf3 window this is meant to survive a
# restart, so the rule set lives in PORTFWD_STATE_FILE and is (re-)applied to
# iptables every time this process starts, never trusted to still be sitting
# in the kernel's tables from before. See doc/DESIGN.md#data-design and doc/LOG.md#decisions
# (2026-09-19).
# ---------------------------------------------------------------------------

PORTFWD_TAG_PREFIX = "vps-server-portfwd-"


def _valid_port(value):
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    return port if 1 <= port <= 65535 else None


def _valid_target_host(value):
    # IPv4 only, matching every other address-handling function in this file
    # (local_addresses(), tailscale_address()) — and a literal address is
    # required anyway, since iptables --to-destination cannot take a hostname.
    try:
        ipaddress.IPv4Address(value)
    except ValueError:
        return False
    return True


def _portfwd_comment(rule_id):
    return f"{PORTFWD_TAG_PREFIX}{rule_id}"


def _portfwd_specs(rule):
    """[(table, chain, match-args, action-args)] for one rule.

    The same list builds both the -A and the -D command for a rule — only the
    verb differs — so closing a rule can never drift from opening it by one
    flag the way two hand-written copies eventually would.
    """
    comment = _portfwd_comment(rule["id"])
    protocols = ["tcp", "udp"] if rule["protocol"] == "both" else [rule["protocol"]]
    specs = []
    for proto in protocols:
        specs.append(("nat", "PREROUTING",
            ["-p", proto, "--dport", str(rule["public_port"])],
            ["-m", "comment", "--comment", comment, "-j", "DNAT",
             "--to-destination", f'{rule["target_host"]}:{rule["target_port"]}']))
        specs.append(("nat", "POSTROUTING",
            ["-p", proto, "-d", rule["target_host"], "--dport", str(rule["target_port"])],
            ["-m", "comment", "--comment", comment, "-j", "MASQUERADE"]))
        specs.append(("filter", "FORWARD",
            ["-p", proto, "-d", rule["target_host"], "--dport", str(rule["target_port"])],
            ["-m", "comment", "--comment", comment, "-j", "ACCEPT"]))
        specs.append(("filter", "FORWARD",
            ["-p", proto, "-s", rule["target_host"], "--sport", str(rule["target_port"])],
            ["-m", "comment", "--comment", comment, "-j", "ACCEPT"]))
    return specs


def _ensure_ip_forward():
    """Turn on net.ipv4.ip_forward if it is not already on.

    Never turned back off: it is a single host-wide toggle, and other
    software already running here (Docker, for one) may depend on it too.
    Symmetrically closing it when the last forward is removed would risk
    breaking whatever else asked for it first — see doc/LOG.md#decisions.
    """
    try:
        current = Path("/proc/sys/net/ipv4/ip_forward").read_text().strip()
    except OSError:
        return
    if current != "1":
        _run_quiet(["sysctl", "-w", "net.ipv4.ip_forward=1"])


def portfwd_rule_apply(rule, opening):
    """Add (opening=True) or withdraw (opening=False) one rule's iptables state.

    Best effort, like firewall_port(): a host with no iptables must not block
    the console, so failure is reported to stderr and otherwise swallowed.
    Withdrawal ignores failure outright — the rule may simply not be present,
    which is the normal case the first time a rule is ever applied.
    """
    if not shutil.which("iptables"):
        print(_log_text('log_iptables_missing'), file=sys.stderr)
        return False
    ok = True
    for table, chain, match, action in _portfwd_specs(rule):
        verb = "-A" if opening else "-D"
        cmd = ["iptables", "-t", table, verb, chain, *match, *action]
        if not _run_quiet(cmd) and opening:
            ok = False
    if not ok:
        print(_log_text('log_portfwd_apply', rule_id=rule['id']), file=sys.stderr)
    return ok


class PortForwardManager:
    """Console-configured DNAT rules, one process-wide instance (PORTFWD).

    State is plain JSON, read into memory once and rewritten on every change.
    A rule's `enabled` flag is the source of truth for whether it should be
    live; whether it actually IS live in the kernel right now is never read
    back from iptables, only driven forward from here — see load().
    """

    def __init__(self, state_file, max_rules):
        self._state_file = state_file
        self._max_rules = max_rules
        self._lock = threading.RLock()
        self._rules = self._read()

    def _read(self):
        try:
            data = json.loads(self._state_file.read_text())
        except (OSError, ValueError):
            return []
        return data if isinstance(data, list) else []

    def _write(self):
        tmp = self._state_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._rules, indent=2))
        tmp.replace(self._state_file)

    def list_rules(self):
        with self._lock:
            return list(self._rules)

    def reserved_ports(self, exclude_id=None):
        """Every public port this install already answers on.

        Checked before a forward is added or re-enabled — DNAT would
        otherwise silently steal traffic meant for the console, the public
        page, the iperf3 window, the anytls node, or any installed proxy
        protocol.
        """
        reserved = {PUBLIC_HTTP_PORT, PUBLIC_HTTPS_PORT, CONSOLE_PORT}
        if IPERF_ENABLED:
            reserved.add(IPERF_WINDOW.port)
        node = anytls_node()
        if node and node.get("port"):
            try:
                reserved.add(int(node["port"]))
            except (TypeError, ValueError):
                pass
        frps = frps_node()
        if frps:
            reserved.add(frps['port'])
        lucky = lucky_admin()
        if lucky:
            reserved.add(lucky['AdminWebListenPort'])
        for pnode in proxy_nodes():
            if pnode.get("port"):
                try:
                    reserved.add(int(pnode["port"]))
                except (TypeError, ValueError):
                    pass
        with self._lock:
            for r in self._rules:
                if r["id"] != exclude_id:
                    reserved.add(r["public_port"])
        return reserved

    def add(self, protocol, public_port, target_host, target_port, label):
        if not portfwd_enabled():
            return None, "portfwd_module_disabled"
        with self._lock:
            if len(self._rules) >= self._max_rules:
                return None, "portfwd_limit"
            if public_port in self.reserved_ports():
                return None, "portfwd_port_taken"
            rule = {
                "id": secrets.token_hex(4),
                "label": label[:80],
                "protocol": protocol,
                "public_port": public_port,
                "target_host": target_host,
                "target_port": target_port,
                "enabled": True,
                "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            self._rules.append(rule)
            self._write()
            _ensure_ip_forward()
            portfwd_rule_apply(rule, opening=True)
            return rule, "portfwd_added"

    def remove(self, rule_id):
        with self._lock:
            rule = next((r for r in self._rules if r["id"] == rule_id), None)
            if rule is None:
                return "portfwd_not_found"
            if rule["enabled"]:
                portfwd_rule_apply(rule, opening=False)
            self._rules = [r for r in self._rules if r["id"] != rule_id]
            self._write()
            return "portfwd_removed"

    def set_enabled(self, rule_id, enabled):
        with self._lock:
            rule = next((r for r in self._rules if r["id"] == rule_id), None)
            if rule is None:
                return "portfwd_not_found"
            if rule["enabled"] == enabled:
                return "portfwd_enabled" if enabled else "portfwd_disabled"
            if enabled and rule["public_port"] in self.reserved_ports(exclude_id=rule_id):
                return "portfwd_port_taken"
            rule["enabled"] = enabled
            self._write()
            if enabled:
                _ensure_ip_forward()
                portfwd_rule_apply(rule, opening=True)
            else:
                portfwd_rule_apply(rule, opening=False)
            return "portfwd_enabled" if enabled else "portfwd_disabled"

    def load(self):
        """Reapply every enabled rule at process startup.

        The kernel remembers nothing across a reboot, and may still hold last
        run's rules if this is only a service restart — so each enabled rule
        is withdrawn before it is (re-)added, which is safe to do unconditio-
        nally whether the rule was already present or not.
        """
        with self._lock:
            if any(r["enabled"] for r in self._rules):
                _ensure_ip_forward()
            for rule in self._rules:
                if rule["enabled"]:
                    portfwd_rule_apply(rule, opening=False)
                    portfwd_rule_apply(rule, opening=True)

    def shutdown(self):
        """Withdraw every enabled rule's kernel state on a clean stop.

        Deliberately not marked disabled in PORTFWD_STATE_FILE: restarting
        the service, or the host, must bring every one of these straight back
        via load(), the same fail-safe direction the iperf3 window already
        takes — if the thing managing the state is not running, the state
        must not silently outlive it.
        """
        with self._lock:
            for rule in self._rules:
                if rule["enabled"]:
                    portfwd_rule_apply(rule, opening=False)


PORTFWD = PortForwardManager(PORTFWD_STATE_FILE, PORTFWD_MAX_RULES)
PORTFWD_SWITCH_FILE = DATA_DIR / "portfwd-enabled"
PORTFWD_APPLIED_FILE = DATA_DIR / "portfwd-applied.json"


def portfwd_switch_revision():
    try:
        state = PORTFWD_SWITCH_FILE.stat()
        return [state.st_ino, state.st_mtime_ns]
    except FileNotFoundError:
        return [0, 0]


def publish_portfwd_state(enabled):
    target = PORTFWD_APPLIED_FILE
    temporary = target.with_suffix(".tmp")
    revision = portfwd_switch_revision()
    temporary.write_text(json.dumps({"enabled": enabled, "revision": revision}) + "\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, target)
    return revision


def watch_portfwd_switch(stop_event):
    active = portfwd_enabled()
    revision = publish_portfwd_state(active)
    while not stop_event.wait(0.2):
        desired = portfwd_enabled()
        if desired != active:
            try:
                if desired:
                    PORTFWD.load()
                else:
                    PORTFWD.shutdown()
            except Exception as exc:
                print(f"Port forward switch reconciliation failed: {exc}", file=sys.stderr)
                continue
            active = desired
        if portfwd_switch_revision() != revision:
            revision = publish_portfwd_state(active)

# ---------------------------------------------------------------------------
# anytls node, read-only
#
# The console can show the installed anytls node so its client configuration
# can be copied without going back to the terminal. Everything below returns
# the node PASSWORD, so it must only ever reach ConsoleHandler — which is
# behind the login — and never ProbeHandler, which has no route to it.
#
# Nothing here writes: to change the node, re-run anytls/setup-anytls.sh.
# ---------------------------------------------------------------------------

ANYTLS_CONFIG = Path(
    os.environ.get("VPSSRV_ANYTLS_CONFIG", "/etc/vps-server-anytls/config.json")
)
ANYTLS_SERVICE = os.environ.get("VPSSRV_ANYTLS_SERVICE", "vps-server-anytls.service")
ANYTLS_SETUP = Path(
    os.environ.get("VPSSRV_ANYTLS_SETUP", str(BASE_DIR / "anytls" / "setup-anytls.sh"))
)
# Generous: the script may hit apt, openssl and a service restart. A web
# request blocking for a few seconds is fine for an operator action; blocking
# forever because systemd is wedged is not.
ANYTLS_RESET_TIMEOUT = 120
# Fixed, so two resets cannot run at once. It also has to be stoppable by name
# when the timeout fires; see anytls_reset().
ANYTLS_RESET_UNIT = "vps-server-anytls-reset.service"


def _cert_common_name(path):
    """Read the node's requested server name from SAN, then legacy CN."""
    if not path or not shutil.which("openssl"):
        return ""
    san = _cmd_output(["openssl", "x509", "-in", path, "-noout", "-ext", "subjectAltName"])
    match = re.search(r"(?:DNS:|IP Address:)([^,\s]+)", san)
    if match:
        return match.group(1).strip()
    out = _cmd_output(["openssl", "x509", "-in", path, "-noout", "-subject"])
    match = re.search(r"CN\s*=\s*([^,/\n]+)", out)
    return match.group(1).strip() if match else ""


def anytls_installed():
    """Cheap check for the nav and the dashboard tile — no parsing, no subprocess."""
    return ANYTLS_CONFIG.is_file()


def anytls_node():
    """The installed node's parameters, or None if the module is not installed."""
    try:
        config = json.loads(ANYTLS_CONFIG.read_text())
    except (OSError, ValueError):
        return None
    for inbound in config.get("inbounds", []):
        if inbound.get("type") != "anytls":
            continue
        users = inbound.get("users") or [{}]
        tls = inbound.get("tls") or {}
        return {
            "port": inbound.get("listen_port", ""),
            "password": users[0].get("password", ""),
            "sni": _cert_common_name(tls.get("certificate_path", "")),
            "running": _run_quiet(["systemctl", "is-active", "--quiet", ANYTLS_SERVICE]),
        }
    return None


def anytls_clash_line(node, host, name):
    """One Clash proxy entry. Same shape setup-anytls.sh prints, so a config
    assembled from either source looks the same.
    """
    return (
        f'- {{ name: {name}, type: anytls, server: {host}, port: {node["port"]}, '
        f'password: {json.dumps(node["password"])}, sni: {json.dumps(node["sni"])}, '
        f'skip-cert-verify: true, udp: true }}'
    )


def anytls_share_link(node, host, name):
    return (
        f'anytls://{quote(node["password"], safe="")}@{host}:{node["port"]}'
        f'?insecure=1&sni={node["sni"]}#{quote(name, safe="")}'
    )


# Mirrors setup-anytls.sh's get_lan_ips filter. Keeping a second copy of the
# list is a drift risk; the alternative is the console shelling into the
# vendored script to ask, which is worse.
VIRTUAL_IFACE_PREFIXES = ("docker", "br-", "veth", "virbr", "cni", "flannel", "kube")


def local_addresses():
    """[(interface, address)] for real interfaces.

    Read from the kernel's own list without an outbound request.
    """
    found = []
    output = _cmd_output(["ip", "-o", "-4", "addr", "show", "scope", "global"])
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        iface, cidr = parts[1], parts[3]
        if iface.startswith(VIRTUAL_IFACE_PREFIXES) or iface.startswith("tailscale"):
            continue
        found.append((iface, cidr.split("/")[0]))
    return found


def tailscale_address():
    for line in _cmd_output(["ip", "-o", "-4", "addr", "show", "tailscale0"]).splitlines():
        parts = line.split()
        if len(parts) >= 4:
            return parts[3].split("/")[0]
    return ""


def address_entries(t):
    """Show host interface addresses and the optional Tailscale address."""
    entries = []
    seen = set()
    for iface, address in local_addresses():
        if address in seen:
            continue
        entries.append((t["anytls_lan"].format(iface=iface), address))
        seen.add(address)
    tailscale = tailscale_address()
    if tailscale and tailscale not in seen:
        entries.append(("Tailscale", tailscale))
        seen.add(tailscale)
    return entries


def anytls_reset_command():
    """argv for a reset, run outside this service's sandbox where possible.

    The unit this process runs under has ProtectSystem=strict with only
    ReadWritePaths=$PREFIX, so /etc is read-only to it — and a reset has to
    write /etc/vps-server-anytls and a unit file. Running it inside the
    sandbox fails partway through, after the old port's firewall rule is
    already gone.

    The fix is not to widen this service's write access for the lifetime of
    the install so that one button works. It is to hand the privileged work to
    a transient unit, which systemd starts outside our sandbox. The fixed unit
    name also serialises resets; --collect reaps it either way.

    Without systemd-run — a container, a stripped image — run it directly.
    Hardening is omitted in exactly those environments anyway, so the direct
    call is the one that works there.
    """
    direct = ["bash", str(ANYTLS_SETUP), "reset"]
    if shutil.which("systemd-run"):
        return ["systemd-run", "--pipe", "--wait", "--collect",
                f"--unit={ANYTLS_RESET_UNIT}", *direct]
    return direct


def anytls_reset():
    """Rotate the node's port and password. Returns a STRINGS key.

    The console deliberately does not write anytls state itself:
    setup-anytls.sh owns it, including the part that is easy to get wrong —
    withdrawing the old port's firewall rule before opening the new one.
    Duplicating that here would leave two copies to drift apart.
    """
    if not ANYTLS_SETUP.is_file():
        return "anytls_reset_missing"
    try:
        result = subprocess.run(
            anytls_reset_command(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=ANYTLS_RESET_TIMEOUT,
            check=False,
            text=True,
        )
    except subprocess.TimeoutExpired:
        # The timeout kills the systemd-run client, not the unit it asked
        # systemd to start — that runs outside this process tree and would
        # carry on, possibly rotating the credentials minutes after the
        # console reported a timeout. The fixed unit name would then make the
        # retry this message suggests fail with "unit already exists", which
        # says nothing about what actually happened.
        _run_quiet(["systemctl", "stop", ANYTLS_RESET_UNIT])
        return "anytls_reset_timeout"
    except OSError:
        return "anytls_reset_missing"
    if result.returncode != 0:
        # The script's own diagnostics are the useful part and the console
        # cannot improve on them, so put them where an operator will look
        # rather than flattening everything into one generic failure.
        print(_log_text('log_anytls_reset', code=result.returncode, output=result.stdout), file=sys.stderr)
        return "anytls_reset_failed"
    return "anytls_reset_done"


# ---------------------------------------------------------------------------
# proxy nodes (vmess/vless/trojan/shadowsocks), read-only
#
# Same shape as the anytls block above, generalized to sing-box's multiple
# inbounds sharing ONE service/config (proxy/setup-proxy.sh's own design —
# see doc/LOG.md#completed-work-history and doc/LOG.md#decisions):
# a single install can have any subset of the four protocols, so proxy_nodes() returns a list instead of the single
# dict anytls_node() returns.
#
# Nothing here writes: to change the node set, re-run proxy/setup-proxy.sh.
# ---------------------------------------------------------------------------

PROXY_CONFIG = Path(
    os.environ.get("VPSSRV_PROXY_CONFIG", "/etc/vps-server-proxy/config.json")
)
PROXY_SERVICE = os.environ.get("VPSSRV_PROXY_SERVICE", "vps-server-proxy.service")
PROXY_SETUP = Path(
    os.environ.get("VPSSRV_PROXY_SETUP", str(BASE_DIR / "proxy" / "setup-proxy.sh"))
)
PROXY_RESET_TIMEOUT = 120
PROXY_RESET_UNIT = "vps-server-proxy-reset.service"
NODE_STATE_PATH = Path("/etc/vps-server-nodes/state.json")
NODE_METER_PATH = NODE_STATE_PATH.parent / "meter.json"
NODE_CONTROL_HELPER = BASE_DIR / "node_control.py"
NODE_CONTROL_UNIT = "vps-server-node-control.service"
NODE_CONFIG_HELPER = BASE_DIR / "node_config.py"  # installed, root-owned helper
NODE_APPLY_UNIT = "vps-server-node-apply.service"
NODE_APPLY_TIMEOUT = 120
NODE_APPLY_BODY_LIMIT = 1024
NODE_PROTOCOLS = frozenset(("anytls", "vmess", "vless", "trojan", "shadowsocks"))


def node_csrf_token(session, protocol):
    return hmac.new(SESSION_SECRET.encode(),
                    f"node-apply:{session}:{protocol}".encode(), "sha256").hexdigest()


def node_apply(protocol, credential):
    """Use the installed privileged helper, never putting credentials in argv."""
    if not NODE_CONFIG_HELPER.is_file():
        return "node_apply_failed"
    direct = ["/usr/bin/python3", str(NODE_CONFIG_HELPER), protocol]
    systemd_run = shutil.which("systemd-run")
    if not systemd_run and Path("/run/systemd/system").exists():
        return "node_apply_failed"  # never run inside the production web sandbox
    command = (["systemd-run", "--pipe", "--wait", "--collect",
                f"--unit={NODE_APPLY_UNIT}", *direct]
               if systemd_run else direct)
    try:
        result = subprocess.run(command, input=credential.encode("utf-8"),
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=NODE_APPLY_TIMEOUT, check=False)
    except subprocess.TimeoutExpired:
        if command[0] == "systemd-run":
            _run_quiet(["systemctl", "stop", NODE_APPLY_UNIT])
        return "node_apply_failed"
    except OSError:
        return "node_apply_failed"
    return "node_apply_done" if result.returncode == 0 else "node_apply_failed"


def node_control_apply(request):
    """Send one ID-based edit to the privileged transactional helper."""
    if not NODE_CONTROL_HELPER.is_file():
        return False
    direct = ["/usr/bin/python3", str(NODE_CONTROL_HELPER), "apply"]
    systemd_run = shutil.which("systemd-run")
    if not systemd_run and Path("/run/systemd/system").exists():
        return False
    command = (["systemd-run", "--pipe", "--wait", "--collect",
                f"--setenv=VPSSRV_DATA_DIR={DATA_DIR}",
                f"--setenv=VPSSRV_IPERF_PORT={IPERF_PORT}",
                f"--unit={NODE_CONTROL_UNIT}", *direct]
               if systemd_run else direct)
    try:
        result = subprocess.run(command, input=json.dumps(request).encode("utf-8"),
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=NODE_APPLY_TIMEOUT, check=False)
    except subprocess.TimeoutExpired:
        if systemd_run:
            _run_quiet(["systemctl", "stop", NODE_CONTROL_UNIT])
        return False
    except OSError:
        return False
    return result.returncode == 0
# Display order only — config.json's own inbounds order already matches this
# (setup-proxy.sh writes them in ALL_PROTOCOLS order), but a config hand-
# edited or produced some other way should not scramble the console page.
PROXY_PROTOCOL_ORDER = ("vmess", "vless", "trojan", "shadowsocks")


def proxy_installed():
    """Cheap check for the nav and the dashboard tile — no parsing, no subprocess."""
    return PROXY_CONFIG.is_file()


def proxy_nodes():
    """[{type, port, secret}] for every installed protocol, in display order.

    `secret` is the uuid for vmess/vless or the password for trojan/
    shadowsocks — one field name regardless of protocol, since exactly one of
    "the identifier IS the credential" is true for all four and the caller
    (page_proxy) already knows which is which from `type`.
    """
    try:
        config = json.loads(PROXY_CONFIG.read_text())
    except (OSError, ValueError):
        return []
    nodes = []
    for inbound in config.get("inbounds", []):
        proto = inbound.get("type")
        if proto not in PROXY_PROTOCOL_ORDER:
            continue
        users = inbound.get("users") or [{}]
        user0 = users[0]
        if proto in ("vmess", "vless"):
            secret = user0.get("uuid", "")
        elif proto == "trojan":
            secret = user0.get("password", "")
        else:  # shadowsocks: password sits on the inbound itself, not a user
            secret = inbound.get("password", "")
        tls = inbound.get("tls") or {}
        nodes.append({"type": proto, "port": inbound.get("listen_port", ""),
                      "secret": secret,
                      "sni": _cert_common_name(tls.get("certificate_path", ""))
                      if proto != "shadowsocks" else ""})
    order = {p: i for i, p in enumerate(PROXY_PROTOCOL_ORDER)}
    nodes.sort(key=lambda n: order.get(n["type"], len(PROXY_PROTOCOL_ORDER)))
    return nodes


FRPS_CONFIG = Path(os.environ.get('VPSSRV_FRPS_CONFIG', '/etc/vps-server-frps/frps.toml'))
FRPS_SERVICE = 'vps-server-frps.service'
FRPC_BINARY = Path(os.environ.get('VPSSRV_FRPC_BIN', '/usr/local/bin/frpc'))
FRP_CONTROL_HELPER = BASE_DIR / 'frp_control.py'
LUCKY_CONFIG = Path(os.environ.get('VPSSRV_LUCKY_CONFIG', '/etc/vps-server-lucky/config.json'))
LUCKY_SERVICE = 'vps-server-lucky.service'


def lucky_admin():
    """Never expose Lucky credentials without console authentication."""
    try:
        data = json.loads(LUCKY_CONFIG.read_text())['BaseConfigure']
        port = data['AdminWebListenPort']
        if type(port) is not int or not 1 <= port <= 65535:
            return None
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return None



def frps_node():
    """Read-only server parameters; do not expose them outside an authenticated console."""
    try:
        text = FRPS_CONFIG.read_text()
        fields = dict(re.findall(r'^([\w.]+)\s*=\s*(.+?)\s*$', text, re.M))
        port = int(fields['bindPort'])
        token = json.loads(fields['auth.token'])
        if not 1 <= port <= 65535 or not token:
            return None
        return {'address': fields.get('bindAddr', '"0.0.0.0"').strip('"'),
                'port': port, 'token': token}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def frpc_connected(name, server, port):
    """Check this instance's established TCP socket to its configured server."""
    try:
        pid_text = subprocess.run(['systemctl', 'show', '-P', 'MainPID', f'frpc@{name}.service'],
                                  capture_output=True, text=True, timeout=3, check=True).stdout.strip()
        pid = int(pid_text)
        if pid <= 0 or not server or not port:
            return False
        output = subprocess.run(['ss', '-Htnp', 'state', 'established'], capture_output=True,
                                text=True, timeout=3, check=True).stdout
        destinations = {address[4][0] for address in socket.getaddrinfo(server, port, type=socket.SOCK_STREAM)}
        for line in output.splitlines():
            if f'pid={pid},' not in line:
                continue
            peer = line.split()[3].rsplit(':', 1)
            if len(peer) == 2 and peer[1] == str(port) and peer[0].strip('[]') in destinations:
                return True
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        pass
    return False


_frpc_probe_lock = threading.Lock()


def frpc_test_connection(name):
    """Make a separate proxy-free FRPC login using the saved server credentials."""
    if not _frpc_probe_lock.acquire(blocking=False):
        return None
    try:
        config = frpc_structured(name)
        if config is None or not FRPC_BINARY.is_file():
            return False
        content = frpc_build(config['serverAddr'], config['serverPort'], config['auth']['token'], [])
        with tempfile.TemporaryDirectory(prefix='vps-frpc-probe-') as directory:
            path = Path(directory) / 'frpc.toml'
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                stream.write(content)
            try:
                result = subprocess.run([str(FRPC_BINARY), '-c', str(path)],
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        timeout=7, check=False)
                output = result.stdout or b''
            except subprocess.TimeoutExpired as exc:
                output = exc.stdout or b''
        return b'login to server success' in output
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return False
    finally:
        _frpc_probe_lock.release()


def masked_frpc_ip(address):
    try:
        parsed = ipaddress.ip_address(address)
        parts = str(parsed).split('.' if parsed.version == 4 else ':')
        return '.'.join(parts[:2] + ['*', '*']) if parsed.version == 4 else ':'.join(parts[:4]) + ':…'
    except ValueError:
        return '••••••'


def proxy_running():
    return _run_quiet(["systemctl", "is-active", "--quiet", PROXY_SERVICE])


def proxy_clash_line(node, sni, host, name):
    proto, port, secret = node["type"], node["port"], node["secret"]
    if proto == "vmess":
        return (f'- {{ name: {name}, type: vmess, server: {host}, port: {port}, '
                f'uuid: {secret}, alterId: 0, cipher: auto, tls: true, '
                f'skip-cert-verify: true, servername: {json.dumps(sni)}, udp: true }}')
    if proto == "vless":
        return (f'- {{ name: {name}, type: vless, server: {host}, port: {port}, '
                f'uuid: {secret}, network: tcp, tls: true, skip-cert-verify: true, '
                f'servername: {json.dumps(sni)}, udp: true }}')
    if proto == "trojan":
        return (f'- {{ name: {name}, type: trojan, server: {host}, port: {port}, '
                f'password: {json.dumps(secret)}, sni: {json.dumps(sni)}, skip-cert-verify: true, udp: true }}')
    return (f'- {{ name: {name}, type: ss, server: {host}, port: {port}, '
            f'cipher: 2022-blake3-aes-128-gcm, password: {json.dumps(secret)}, udp: true }}')


def clash_share_token(node):
    """A capability URL changes when this node's connection details change."""
    material = json.dumps({"id": node["id"], "name": node["name"],
                           "inbound": node["inbound"]}, sort_keys=True,
                          separators=(",", ":")).encode()
    return hmac.new(SESSION_SECRET.encode(), b"clash-profile-v1:" + material,
                    "sha256").hexdigest()


def clash_lan_host(host):
    """Use a real private IPv4 address for same-LAN import links."""
    addresses = [address for _, address in local_addresses()]
    if host in addresses and is_lan_address(host):
        return host
    for address in addresses:
        if is_lan_address(address):
            return address
    return None


def is_lan_address(value):
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return address.version == 4 and any(address in network for network in (
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16")))


def clash_profile(node, host):
    """A complete single-node Mihomo profile, not just a proxy YAML entry."""
    inbound, protocol = node["inbound"], node["protocol"]
    name = json.dumps(node["name"], ensure_ascii=False)
    if protocol == "anytls":
        line = anytls_clash_line({"port": node["port"],
                                 "password": inbound["users"][0]["password"],
                                 "sni": _cert_common_name(inbound["tls"]["certificate_path"])},
                                host, name)
    else:
        secret = (inbound["password"] if protocol == "shadowsocks" else
                  inbound["users"][0]["uuid" if protocol in ("vmess", "vless")
                                       else "password"])
        sni = ("" if protocol == "shadowsocks" else
               _cert_common_name(inbound["tls"]["certificate_path"]))
        line = proxy_clash_line({"type": protocol, "port": node["port"],
                                 "secret": secret}, sni, host, name)
    return ("mixed-port: 7890\nallow-lan: false\nmode: rule\nlog-level: warning\n"
            f"proxies:\n  {line}\n"
            "proxy-groups:\n  - name: NODE\n    type: select\n    proxies:\n"
            f"      - {name}\n      - DIRECT\n"
            "rules:\n  - MATCH,NODE\n")


def proxy_share_link(node, sni, host, name):
    proto, port, secret = node["type"], node["port"], node["secret"]
    if proto == "vmess":
        payload = {
            "v": "2", "ps": name, "add": host, "port": str(port), "id": secret,
            "aid": "0", "net": "tcp", "type": "none", "host": "", "path": "",
            "tls": "tls", "sni": sni, "scy": "auto",
        }
        blob = base64.b64encode(json.dumps(payload).encode()).decode()
        return f"vmess://{blob}"
    if proto == "vless":
        return (f'vless://{secret}@{host}:{port}?encryption=none&security=tls'
                f'&sni={quote(sni, safe="")}&allowInsecure=1&type=tcp#{quote(name, safe="")}')
    if proto == "trojan":
        return (f'trojan://{quote(secret, safe="")}@{host}:{port}'
                f'?sni={quote(sni, safe="")}&allowInsecure=1#{quote(name, safe="")}')
    blob = base64.b64encode(f"2022-blake3-aes-128-gcm:{secret}".encode()).decode()
    return f"ss://{blob}@{host}:{port}#{quote(name, safe='')}"


def proxy_reset_command(protocol=None):
    """Same sandboxing workaround as anytls_reset_command() — see its
    docstring. ConsoleHandler's unit has ProtectSystem=strict, so a reset has
    to run outside this process's own sandbox to reach /etc.

    `protocol`, when given, rotates only that one protocol's port and
    credential — setup-proxy.sh's `reset <protocol>` form, added after an
    operator pointed out that a single "reset everything" button forces
    rotating protocols nobody asked to touch. `None` keeps the old
    "reset everything currently installed" behaviour.
    """
    direct = ["bash", str(PROXY_SETUP), "reset"]
    if protocol:
        direct.append(protocol)
    if shutil.which("systemd-run"):
        return ["systemd-run", "--pipe", "--wait", "--collect",
                f"--unit={PROXY_RESET_UNIT}", *direct]
    return direct


def proxy_reset(protocol=None):
    """Rotate one protocol's (or, with no argument, every currently-
    installed protocol's) port and credential. Returns a STRINGS key. Same
    non-duplication reasoning as anytls_reset(): setup-proxy.sh owns the
    state, including which protocol set survives a reset (it reads that
    back from the config it is about to overwrite).
    """
    if not PROXY_SETUP.is_file():
        return "proxy_reset_missing"
    try:
        result = subprocess.run(
            proxy_reset_command(protocol),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=PROXY_RESET_TIMEOUT,
            check=False,
            text=True,
        )
    except subprocess.TimeoutExpired:
        _run_quiet(["systemctl", "stop", PROXY_RESET_UNIT])
        return "proxy_reset_timeout"
    except OSError:
        return "proxy_reset_missing"
    if result.returncode != 0:
        print(_log_text('log_proxy_reset', code=result.returncode, output=result.stdout), file=sys.stderr)
        return "proxy_reset_failed"
    return "proxy_reset_done"


def render_copyable(t, label, value, ident):
    return f"""
    <div class="copyrow">
      <div class="copyhead">
        <span>{html.escape(label)}</span>
        <button type="button" class="copybtn" data-copy="{ident}"
                data-copied="{html.escape(t['copied'])}"
                >{html.escape(t['copy'])}</button>
      </div>
      <pre class="cmd" id="{ident}">{html.escape(value)}</pre>
    </div>
    """

# Result keys the console may echo back after a redirect. Whitelisted because
# the key indexes STRINGS: without this, a crafted ?msg= would be a way to
# render any string from the table on an authenticated page.
IPERF_MESSAGE_KEYS = frozenset({
    "iperf_opened", "iperf_extended", "iperf_shut",
    "iperf_disabled", "iperf_missing", "iperf_port_busy",
    "iperf_port_saved", "iperf_port_invalid",
})

ANYTLS_MESSAGE_KEYS = frozenset({
    "anytls_reset_done", "anytls_reset_unconfirmed", "anytls_reset_failed",
    "anytls_reset_timeout", "anytls_reset_missing",
})

NODE_APPLY_MESSAGE_KEYS = frozenset({"node_apply_done", "node_apply_failed",
                                     "node_settings_done", "node_settings_failed", "node_reset_done",
                                     "node_created", "node_deleted"})

PROXY_MESSAGE_KEYS = frozenset({
    "proxy_reset_done", "proxy_reset_unconfirmed", "proxy_reset_failed",
    "proxy_reset_timeout", "proxy_reset_missing",
})

PORTFWD_MESSAGE_KEYS = frozenset({
    "portfwd_added", "portfwd_removed", "portfwd_enabled", "portfwd_disabled",
    "portfwd_invalid", "portfwd_port_taken", "portfwd_limit", "portfwd_not_found",
    "portfwd_module_disabled",
})

# ---------------------------------------------------------------------------
# Internationalization (English / Simplified Chinese / Traditional Chinese)
# ---------------------------------------------------------------------------


# Rendered in the navigation in display order.
LANG_NAMES = {"en": "English", "zh_cn": "简体中文", "zh_tw": "繁體中文",
              "zh_hk": "繁體中文 (香港)", "hi": "हिन्दी", "es": "Español",
              "ar": "العربية", "fr": "Français"}

# The runtime language codes (zh_cn/zh_tw, with underscores) are legacy
# identifiers; documentation directories use BCP-47 tags. These codes
# aren't valid BCP-47 <html lang> values — that
# needs a hyphen. Only used for the <html lang="..."> attribute.
HTML_LANG_TAGS = {"zh_cn": "zh-CN", "zh_tw": "zh-TW", "zh_hk": "zh-HK"}
RTL_ATTR = {"ar": ' dir="rtl"'}


def pick_lang(cookie_lang, query_lang, accept_language):
    for candidate in (query_lang, cookie_lang):
        if candidate in STRINGS:
            return candidate
    if accept_language:
        # Only the first (highest-priority) tag matters here.
        primary = accept_language.split(",")[0].strip().lower()
        if primary.startswith("zh"):
            if "hk" in primary or "mo" in primary:
                return "zh_hk"
            if "tw" in primary or "hant" in primary:
                return "zh_tw"
            return "zh_cn"
        for code in ("hi", "es", "ar", "fr", "en"):
            if primary == code or primary.startswith(code + "-"):
                return code
    return DEFAULT_LANG


# ---------------------------------------------------------------------------
# Sessions — in memory; a restart forces re-login, acceptable for this tool.
# ---------------------------------------------------------------------------

_sessions = {}
_ip_sessions = {}
_security_sessions = {}
_sessions_lock = threading.Lock()


def create_session(*, security_verified=False):
    token = secrets.token_urlsafe(32)
    with _sessions_lock:
        _sessions[token] = time.time() + SESSION_TTL_SECONDS
        if security_verified:
            _security_sessions[token] = time.time() + SECURITY_PERMISSION_SECONDS
    return token


def session_valid(token):
    if not token:
        return False
    with _sessions_lock:
        expiry = _sessions.get(token)
        if expiry is None:
            return False
        if expiry < time.time():
            del _sessions[token]
            _security_sessions.pop(token, None)
            return False
        return True


def security_settings_valid(token):
    if not session_valid(token):
        return False
    with _sessions_lock:
        expiry = _security_sessions.get(token, 0)
        if expiry <= time.time():
            _security_sessions.pop(token, None)
            return False
        return True


def create_ip_session(address):
    token = secrets.token_urlsafe(32)
    with _sessions_lock:
        _ip_sessions[token] = (address, time.time() + SESSION_TTL_SECONDS)
    return token


def ip_session_valid(token, address):
    if not token or TRUST_PROXY or not IP_ALLOWLIST.contains(address):
        return False
    with _sessions_lock:
        entry = _ip_sessions.get(token)
        if entry is None:
            return False
        saved_address, expiry = entry
        if expiry < time.time():
            del _ip_sessions[token]
            return False
        return hmac.compare_digest(saved_address, address)


def destroy_session(token):
    with _sessions_lock:
        _sessions.pop(token, None)
        _ip_sessions.pop(token, None)
        _security_sessions.pop(token, None)


def access_csrf_token(session, action):
    return hmac.new(SESSION_SECRET.encode(),
                    f"access:{session}:{action}".encode(), "sha256").hexdigest()


_password_lock = threading.Lock()


def change_admin_password(replacement):
    global ADMIN_PASSWORD
    if not isinstance(replacement, str) or not 12 <= len(replacement) <= 128 or \
            replacement != replacement.strip() or any(ord(char) < 32 for char in replacement):
        raise ValueError("invalid new password")
    with _password_lock:
        _atomic_private_text(PASSWORD_FILE, replacement + "\n")
        ADMIN_PASSWORD = replacement
        with _sessions_lock:
            _sessions.clear()
            _ip_sessions.clear()
            _security_sessions.clear()


# ---------------------------------------------------------------------------
# Login rate limiting — per source IP, in memory, reset by a restart just
# like sessions are. A lockout is cleared by a successful login or by
# waiting it out; it is never permanent, so a forgetful operator cannot
# lock themselves out for good.
# ---------------------------------------------------------------------------


class LoginRateLimiter:
    def __init__(self, max_attempts, window_seconds, lockout_seconds):
        self._max_attempts = max_attempts
        self._window = window_seconds
        self._lockout = lockout_seconds
        self._lock = threading.Lock()
        self._failures = {}       # ip -> [failure timestamps within window]
        self._locked_until = {}   # ip -> unix time the lockout ends

    def check(self, ip):
        """(allowed, retry_after_seconds). retry_after is 0 when allowed."""
        with self._lock:
            until = self._locked_until.get(ip)
            if until is None:
                return True, 0
            remaining = until - time.time()
            if remaining <= 0:
                del self._locked_until[ip]
                self._failures.pop(ip, None)
                return True, 0
            return False, int(remaining) + 1

    def record_failure(self, ip):
        with self._lock:
            now = time.time()
            attempts = [t for t in self._failures.get(ip, []) if now - t < self._window]
            attempts.append(now)
            if len(attempts) >= self._max_attempts:
                self._locked_until[ip] = now + self._lockout
                self._failures.pop(ip, None)
            else:
                self._failures[ip] = attempts
            self._prune(now)

    def record_success(self, ip):
        with self._lock:
            self._failures.pop(ip, None)
            self._locked_until.pop(ip, None)

    def _prune(self, now):
        # Runs on every failure, not on a timer: cheap, and keeps a scan
        # hammering many source IPs from growing these dicts without bound.
        for ip in [i for i, until in self._locked_until.items() if until < now]:
            del self._locked_until[ip]
        for ip in [i for i, ts in self._failures.items()
                   if not any(now - t < self._window for t in ts)]:
            del self._failures[ip]


LOGIN_LIMITER = LoginRateLimiter(LOGIN_MAX_ATTEMPTS, LOGIN_WINDOW_SECONDS, LOGIN_LOCKOUT_SECONDS)


# ---------------------------------------------------------------------------
# Visitor log — one row per IP (deduplicated), trimmed to the newest
# MAX_VISITOR_ROWS unique IPs after each write.
#
# Two independent sources feed it:
#   * HTTP requests to this app (method/path/status are recorded), and
#   * the kernel's TCP table, polled in the background, which catches every
#     device connecting to *any* listening port on this host — SSH, other
#     services, port scans — not just the ones that opened this web page.
# ---------------------------------------------------------------------------

_db_lock = threading.Lock()


def ip_scope(ip):
    """Classify an address so the UI can filter loopback/LAN noise out."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return "public"
    if addr.is_loopback:
        return "loopback"
    if addr.is_private or addr.is_link_local:
        return "private"
    return "public"


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS visitors (
                ip          TEXT PRIMARY KEY,
                first_seen  TEXT NOT NULL,
                last_seen   TEXT NOT NULL,
                hits        INTEGER NOT NULL,
                last_method TEXT NOT NULL,
                last_path   TEXT NOT NULL,
                last_status INTEGER NOT NULL
            )
            """
        )
        # Migrate databases created before connection tracking existed. Adding
        # columns one at a time keeps existing visitor history intact.
        existing = {row[1] for row in conn.execute("PRAGMA table_info(visitors)")}
        for column, ddl in (
            ("conn_seen", "ALTER TABLE visitors ADD COLUMN conn_seen INTEGER NOT NULL DEFAULT 0"),
            ("ports", "ALTER TABLE visitors ADD COLUMN ports TEXT NOT NULL DEFAULT ''"),
            ("scope", "ALTER TABLE visitors ADD COLUMN scope TEXT NOT NULL DEFAULT 'public'"),
            ("direction", "ALTER TABLE visitors ADD COLUMN direction TEXT NOT NULL DEFAULT 'in'"),
        ):
            if column not in existing:
                conn.execute(ddl)
        # Backfill scope for rows that predate the column.
        for (ip,) in conn.execute("SELECT ip FROM visitors WHERE scope = 'public'").fetchall():
            conn.execute("UPDATE visitors SET scope = ? WHERE ip = ?", (ip_scope(ip), ip))


def _trim(conn):
    conn.execute(
        "DELETE FROM visitors WHERE ip NOT IN "
        "(SELECT ip FROM visitors ORDER BY last_seen DESC LIMIT ?)",
        (MAX_VISITOR_ROWS,),
    )


def log_visit(ip, method, path, status):
    if not module_feature_enabled(BASE_DIR, "visitors"):
        return
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _db_lock, sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO visitors (ip, first_seen, last_seen, hits, last_method,
                                  last_path, last_status, scope)
            VALUES (?, ?, ?, 1, ?, ?, ?, ?)
            ON CONFLICT(ip) DO UPDATE SET
                last_seen   = excluded.last_seen,
                hits        = hits + 1,
                last_method = excluded.last_method,
                last_path   = excluded.last_path,
                last_status = excluded.last_status
            """,
            (ip, ts, ts, method, path[:512], status, ip_scope(ip)),
        )
        _trim(conn)


def record_connections(observations):
    """Record remote IPs seen in the kernel TCP table.

    `observations` maps an IP to {"ports": set, "inbound": bool}. These rows
    carry no method/path — the peer did not necessarily speak HTTP.
    """
    if not observations or not module_feature_enabled(BASE_DIR, "visitors"):
        return
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _db_lock, sqlite3.connect(DB_FILE) as conn:
        for ip, entry in observations.items():
            port_text = ",".join(str(p) for p in sorted(entry["ports"])[:8])
            direction = "in" if entry["inbound"] else "out"
            conn.execute(
                """
                INSERT INTO visitors (ip, first_seen, last_seen, hits, last_method,
                                      last_path, last_status, conn_seen, ports,
                                      scope, direction)
                VALUES (?, ?, ?, 0, '', '', 0, 1, ?, ?, ?)
                ON CONFLICT(ip) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    conn_seen = conn_seen + 1,
                    ports     = excluded.ports,
                    -- once a peer has ever connected in, it stays a visitor
                    direction = CASE WHEN visitors.direction = 'in' THEN 'in'
                                     ELSE excluded.direction END
                """,
                (ip, ts, ts, port_text, ip_scope(ip), direction),
            )
        _trim(conn)


def recent_visitors(limit=MAX_VISITOR_ROWS):
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT ip, first_seen, last_seen, hits, conn_seen, ports, scope, "
            "direction, last_method, last_path, last_status "
            "FROM visitors ORDER BY last_seen DESC LIMIT ?",
            (limit,),
        ).fetchall()


# ---------------------------------------------------------------------------
# Kernel TCP table polling
# ---------------------------------------------------------------------------

TCP_LISTEN = "0A"

# States that mean "a real peer is or was on the other end of this socket".
# Counting only ESTABLISHED missed two useful cases: SYN_RECV is a half-open
# connection (what a SYN scan leaves behind), and the closing states are
# connections that already finished — including them recovers short-lived
# connections that would otherwise vanish between two polls.
#   01 ESTABLISHED  03 SYN_RECV   04 FIN_WAIT1  05 FIN_WAIT2
#   06 TIME_WAIT    08 CLOSE_WAIT 09 LAST_ACK   0B CLOSING
# Deliberately excluded: 02 SYN_SENT (our own outbound attempt, may never
# connect), 07 CLOSE (dead socket), 0A LISTEN (our own listener).
TCP_PEER_STATES = frozenset({"01", "03", "04", "05", "06", "08", "09", "0B"})


def _decode_addr(field):
    """Decode a `/proc/net/tcp[6]` hex address into (ip, port).

    Addresses are stored as little-endian 32-bit words, so each 8-hex-digit
    group has to be byte-swapped before it means anything.
    """
    hex_addr, _, hex_port = field.partition(":")
    port = int(hex_port, 16)
    raw = bytes.fromhex(hex_addr)
    words = [raw[i:i + 4][::-1] for i in range(0, len(raw), 4)]
    packed = b"".join(words)
    addr = ipaddress.ip_address(packed)
    # ::ffff:1.2.3.4 is the same machine as 1.2.3.4; show the familiar form.
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return str(addr), port


def _read_proc_net(path):
    try:
        with open(path, "r") as fh:
            return fh.read().splitlines()[1:]  # drop the header row
    except OSError:
        return []


def observed_connections():
    """Remote IP -> {"ports": set(local ports), "inbound": bool}.

    Every TCP socket with a real peer is reported, whatever the port and
    whatever the connection state (see TCP_PEER_STATES) — that is the point:
    any device that talked to this machine should show up, not only the ones
    that hit a port we happen to be listening on right now. UDP and ICMP are
    *not* covered; the kernel keeps no peer address for them.

    Direction is still derived (local port in the listening set == someone
    connected to us) so that our *own* outbound connections — a git pull, an
    API call — are visible but not mislabelled as visitors.
    """
    listening = set()
    established = []
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        for line in _read_proc_net(path):
            parts = line.split()
            if len(parts) < 4:
                continue
            local, remote, state = parts[1], parts[2], parts[3]
            try:
                if state == TCP_LISTEN:
                    listening.add(_decode_addr(local)[1])
                elif state in TCP_PEER_STATES:
                    established.append((_decode_addr(local), _decode_addr(remote)))
            except (ValueError, IndexError):
                continue  # a malformed row must not kill the poller

    observations = {}
    for (_, local_port), (remote_ip, remote_port) in established:
        inbound = local_port in listening
        entry = observations.setdefault(remote_ip, {"ports": set(), "inbound": False})
        # Record the port that identifies the service being used: ours when
        # they connected in, theirs when we connected out.
        entry["ports"].add(local_port if inbound else remote_port)
        if inbound:
            entry["inbound"] = True
    return observations


def connection_poller(stop_event):
    while not stop_event.is_set():
        try:
            if module_feature_enabled(BASE_DIR, "visitors"):
                record_connections(observed_connections())
        except Exception as exc:  # never let the poller take the server down
            print(_log_text('log_connection_poller', error=exc), file=sys.stderr)
        stop_event.wait(CONN_POLL_SECONDS)


init_db()

# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


def render_lang_switcher(lang, suffix=""):
    parts = []
    for code, name in LANG_NAMES.items():
        cls = "lang active" if code == lang else "lang"
        parts.append(f'<a class="{cls}" href="?lang={code}{suffix}">{html.escape(name)}</a>')
    return "\n".join(parts)


def render_password_field(t, ident, label, name, attributes="", hint=""):
    """Render one independently revealable, initially masked input."""
    field_id = html.escape(ident, quote=True)
    field_label = html.escape(label)
    show = html.escape(t["login_show_password"])
    hide = html.escape(t["login_hide_password"])
    accessible_show = html.escape(f'{t["login_show_password"]} {label}', quote=True)
    accessible_hide = html.escape(f'{t["login_hide_password"]} {label}', quote=True)
    return (f'<label class="password-label" for="{field_id}">{field_label}</label>'
            f'<div class="password-field">'
            f'<input id="{field_id}" type="password" name="{html.escape(name, quote=True)}" {attributes}>'
            f'<button type="button" class="password-toggle" aria-controls="{field_id}" '
            f'aria-pressed="false" aria-label="{accessible_show}" '
            f'data-show-label="{show}" data-hide-label="{hide}" '
            f'data-show-accessible="{accessible_show}" data-hide-accessible="{accessible_hide}">'
            f'{show}</button></div>{hint}')


def _inline_md(text):
    """Escape first, then re-introduce only `code` and **bold**.

    Everything is HTML-escaped before any markup is added, so nothing in
    LOG.md can inject markup into the page.
    """
    out = html.escape(text)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    return out


def changelog_section(markdown):
    """Return only LOG.md's Changelog body, or None when it is absent/empty."""
    match = re.search(r"^## (?:Changelog|变更日志|變更紀錄|變更記錄|परिवर्तन सूची|Historial de cambios|سجل التغييرات|Historique des modifications)[ \t]*$", markdown, re.MULTILINE)
    if not match:
        return None
    tail = markdown[match.end():]
    next_section = re.search(r"^## [^#]", tail, re.MULTILINE)
    section = tail[:next_section.start()] if next_section else tail
    return section if re.search(r"^### v[^\s]+", section, re.MULTILINE) else None


def development_updates_section(markdown):
    """Select the public test-build notes without exposing Handoff details."""
    match = re.search(r"^## Development Updates[ \t]*$", markdown, re.MULTILINE)
    if not match:
        return None
    tail = markdown[match.end():]
    next_section = re.search(r"^## [^#]", tail, re.MULTILINE)
    section = tail[:next_section.start()] if next_section else tail
    return section if re.search(r"^- ", section, re.MULTILINE) else None


def render_changelog(markdown):
    """Render LOG's changelog headings and lists after selecting its section."""
    html_parts = []
    in_list = False
    in_item = False
    in_comment = False
    started = False  # skip notes before the first version

    def close_list():
        nonlocal in_list, in_item
        if in_item:
            html_parts.append("</li>")
            in_item = False
        if in_list:
            html_parts.append("</ul>")
            in_list = False

    for raw in markdown.splitlines():
        stripped = raw.strip()
        # A comment is, by definition, not for the reader. Without this the
        # maintainer's note at the foot of the file came out as a run of
        # paragraphs on the changelog page — escaped `<!--` and all — because
        # every line it contains falls through to the plain-paragraph branch.
        if in_comment:
            if "-->" in stripped:
                in_comment = False
            continue
        if stripped.startswith("<!--"):
            if "-->" not in stripped:
                in_comment = True
            continue
        if stripped.startswith(("### v", "### dev-", "### test-")):
            started = True
            close_list()
            html_parts.append(f"<h2>{_inline_md(stripped[4:])}</h2>")
            continue
        if not started:
            continue
        if stripped.startswith("#### "):
            close_list()
            html_parts.append(f"<h3>{_inline_md(stripped[5:])}</h3>")
        elif stripped.startswith("- "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            if in_item:
                html_parts.append("</li>")
            html_parts.append(f"<li>{_inline_md(stripped[2:])}")
            in_item = True
        elif not stripped:
            close_list()
        elif in_item:
            # A wrapped bullet: keep it inside the same <li>.
            html_parts.append(f" {_inline_md(stripped)}")
        else:
            html_parts.append(f"<p>{_inline_md(stripped)}</p>")
    close_list()
    return "\n".join(html_parts)


_UI_ICON_NAMES = frozenset({"activity", "gauge", "timer", "network", "route", "users-round", "scroll-text", "log-out", "server", "settings-2", "radio", "lock-keyhole"})
_UI_ICON_CACHE = {}


def ui_icon(name):
    """Inline a bundled, trusted icon so it inherits text color."""
    if name not in _UI_ICON_NAMES:
        raise ValueError("unknown UI icon")
    if name not in _UI_ICON_CACHE:
        source = (BASE_DIR / "static" / "icons" / "lucide" / f"{name}.svg").read_text(encoding="utf-8")
        _UI_ICON_CACHE[name] = source.replace("<svg", '<svg class="ui-icon" aria-hidden="true" focusable="false"', 1)
    return _UI_ICON_CACHE[name]


def render_theme_menu(lang):
    t = STRINGS[lang]
    theme_options = "".join(
        f'<button type="button" data-theme-choice="{choice}" aria-pressed="{str(choice == "slate-blue").lower()}">'
        f'<span class="theme-swatch theme-swatch-{choice}" aria-hidden="true"></span>{html.escape(t[key])}</button>'
        for choice, key in (("slate-blue", "theme_slate_blue"), ("sage", "theme_sage"),
                            ("teal", "theme_teal"), ("plum", "theme_plum"),
                            ("ocean", "theme_ocean"), ("olive", "theme_olive"),
                            ("terracotta", "theme_terracotta"), ("indigo", "theme_indigo"))
    )
    return (f'<details class="theme-menu"><summary>{html.escape(t["theme_label"])}</summary>'
            f'<div class="theme-options" role="group" aria-label="{html.escape(t["theme_label"], quote=True)}">'
            f'{theme_options}</div></details>')


def render_page(title, body, lang, active=None, show_nav=True, password_authenticated=False,
                ip_authenticated=False, bare=False, back_href=None):
    t = STRINGS[lang]
    favicon = ('login' if bare else 'modules' if title == t['modules_heading'] else
               'security' if back_href == '/settings' else
               active if active in ('home', 'speedtest', 'iperf', 'proxy', 'portfwd',
                                    'visitors', 'changelog', 'settings') else
               'frp' if title in (t['frp_heading'], t['frps_heading'], t['frp_client_heading'])
               or back_href in ('/frps', '/frpc') else 'lucky' if title == 'Lucky' else 'home')
    version_tag = f'<a class="version" href="/changelog">{html.escape(VERSION_LABEL)}</a>'
    nav = ""
    if show_nav:
        def link(href, key):
            cls = ' class="active"' if active == key else ""
            current = ' aria-current="page"' if active == key else ""
            icons = {"home": "server", "changelog": "scroll-text", "settings": "settings-2"}
            return f'<a{cls}{current} href="{href}">{ui_icon(icons[key])}<span>{html.escape(t[key])}</span></a>'

        # No session to end when auth is off — offering "Log out" would be a
        # link to nowhere (the route itself redirects to / in that mode).
        logout_link = (f'<a href="/logout">{ui_icon("log-out")}<span>{html.escape(t["logout"])}</span></a>'
                       if AUTH_ENABLED and (password_authenticated or ip_authenticated) else "")
        nav = f"""
        <nav class="topnav" aria-label="{html.escape(t['nav_label'], quote=True)}">
          <div class="brandwrap">
            <a class="brand" href="/">{ui_icon('server')}<span>{html.escape(t['title'])}</span></a>
            {version_tag}
          </div>
          <div class="navlinks">
            {link('/', 'home')}
            {link('/changelog', 'changelog')}
            {link('/settings', 'settings') if AUTH_ENABLED and (password_authenticated or ip_authenticated) else ''}
            {logout_link}
          </div>
        </nav>
        """
    elif bare:
        nav = (f'<header class="app-login-header"><a class="app-login-brand" href="/">'
               f'{ui_icon("server")}<span>{html.escape(t["title"])}</span></a></header>')
    elif not bare:
        lang_menu = (f'<details class="language-menu"><summary>{html.escape(LANG_NAMES[lang])}</summary>'
                     f'<div class="language-options">{render_lang_switcher(lang)}</div></details>')
        theme_menu = render_theme_menu(lang)
        nav = f"""
        <nav class="topnav minimal" aria-label="{html.escape(t['nav_label'], quote=True)}">
          <div class="brandwrap">
            <a class="brand" href="/">{ui_icon('server')}<span>{html.escape(t['title'])}</span></a>
            <span class="version">{html.escape(VERSION_LABEL)}</span>
          </div>
          <div class="navlinks">{theme_menu}{lang_menu}</div>
        </nav>
        """
    if show_nav and active != 'home':
        destination = back_href or '/'
        destination_label = (t['access_security'] if destination == '/settings/security' else
                             t['settings'] if destination == '/settings' else
                             t['frps_heading'] if destination == '/frps' else
                             t['frp_client_heading'] if destination == '/frpc' else
                             t['frp_heading'] if destination == '/frp' else t['dashboard'])
        body = (f'<a class="page-back" href="{html.escape(destination, quote=True)}">'
                f'{html.escape(t["back_to"].format(destination=destination_label))}</a>' + body)
    history_guard = ('<script src="/static/auth-history.js"></script>'
                     if password_authenticated or ip_authenticated else '')
    return f"""<!doctype html>
<html lang="{HTML_LANG_TAGS.get(lang, lang)}"{RTL_ATTR.get(lang, "")}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} — {html.escape(t['title'])}</title>
<link rel="icon" type="image/svg+xml" href="/static/favicon-{favicon}.svg">
<script src="/static/layout-motion.js"></script>
{history_guard}
<script>try{{var v=localStorage.getItem('vps-server-theme');if(['slate-blue','sage','teal','plum','ocean','olive','terracotta','indigo'].indexOf(v)>=0)document.documentElement.dataset.theme=v;if(localStorage.getItem('vps-server-mode')==='dark')document.documentElement.classList.add('dark')}}catch(e){{}}</script>
<link rel="stylesheet" href="/static/style.css">
<script src="/static/theme.js" defer></script>
<script src="/static/password-fields.js" defer></script>
<script src="/static/reference-select.js" defer></script>
</head>
<body{' class="login-page"' if bare else ''}>
{nav}
<main{' class="app-login-main"' if bare else ''}>
{body}
</main>
</body>
</html>"""


CHANGELOG_PATHS = {
    code: BASE_DIR / "doc" / tag / "LOG.md"
    for code, tag in (("zh_cn", "zh-CN"), ("zh_tw", "zh-TW"),
                      ("zh_hk", "zh-HK"), ("hi", "hi"), ("es", "es"),
                      ("ar", "ar"), ("fr", "fr"))
}

STATIC_FILES = {
    "/static/style.css": ("text/css", BASE_DIR / "static" / "style.css"),
    "/static/theme.js": ("application/javascript", BASE_DIR / "static" / "theme.js"),
    "/static/password-fields.js": ("application/javascript", BASE_DIR / "static" / "password-fields.js"),
    "/static/access-settings.js": ("application/javascript", BASE_DIR / "static" / "access-settings.js"),
    "/static/settings-sections.js": ("application/javascript", BASE_DIR / "static" / "settings-sections.js"),
    "/static/module-status.js": ("application/javascript", BASE_DIR / "static" / "module-status.js"),
    "/static/module-controls.js": ("application/javascript", BASE_DIR / "static" / "module-controls.js"),
    "/static/reference-select.js": ("application/javascript", BASE_DIR / "static" / "reference-select.js"),
    "/static/frp-editor.js": ("application/javascript", BASE_DIR / "static" / "frp-editor.js"),
    "/static/layout-motion.js": ("application/javascript", BASE_DIR / "static" / "layout-motion.js"),
    "/static/auth-history.js": ("application/javascript", BASE_DIR / "static" / "auth-history.js"),
    "/favicon.ico": ("image/svg+xml", BASE_DIR / "static" / "favicon.svg"),
    **{f"/static/favicon-{page}.svg": ("image/svg+xml", BASE_DIR / "static" / f"favicon-{page}.svg")
       for page in ("home", "speedtest", "iperf", "proxy", "portfwd", "visitors",
                    "changelog", "settings", "security", "modules", "frp", "lucky", "login")},
    "/static/fonts/inter-latin-400.woff2": ("font/woff2", BASE_DIR / "static" / "fonts" / "inter-latin-400.woff2"),
    "/static/fonts/inter-latin-600.woff2": ("font/woff2", BASE_DIR / "static" / "fonts" / "inter-latin-600.woff2"),
    "/static/fonts/inter-latin-700.woff2": ("font/woff2", BASE_DIR / "static" / "fonts" / "inter-latin-700.woff2"),
    "/static/fonts/noto-sans-sc-400.woff2": ("font/woff2", BASE_DIR / "static" / "fonts" / "noto-sans-sc-400.woff2"),
    "/static/fonts/noto-sans-sc-700.woff2": ("font/woff2", BASE_DIR / "static" / "fonts" / "noto-sans-sc-700.woff2"),
    "/static/speedtest.js": ("application/javascript", BASE_DIR / "static" / "third_party" / "librespeed" / "speedtest.js"),
    "/static/speedtest-ui.js": ("application/javascript", BASE_DIR / "static" / "speedtest-ui.js"),
    "/static/visitors.js": ("application/javascript", BASE_DIR / "static" / "visitors.js"),
    "/static/copy.js": ("application/javascript", BASE_DIR / "static" / "copy.js"),
    "/static/private-values.js": ("application/javascript", BASE_DIR / "static" / "private-values.js"),
    "/static/node-controls.js": ("application/javascript", BASE_DIR / "static" / "node-controls.js"),
    "/static/qrcode.js": ("application/javascript", BASE_DIR / "static" / "third_party" / "qrcode" / "qrcode.js"),
    "/static/qrcode-utf8.js": ("application/javascript", BASE_DIR / "static" / "third_party" / "qrcode" / "qrcode-utf8.js"),
    "/static/qrcode-render.js": ("application/javascript", BASE_DIR / "static" / "qrcode-render.js"),
    "/static/iperf-countdown.js": ("application/javascript", BASE_DIR / "static" / "iperf-countdown.js"),
    # speedtest.js spawns `new Worker("speedtest_worker.js?r=...")`. That call
    # runs in the *page's* context, so the browser resolves it relative to the
    # page URL (/speedtest), not relative to /static/speedtest.js — it lands
    # on /speedtest_worker.js, not /static/speedtest_worker.js. Serving it at
    # both paths sidesteps relying on that resolution quirk.
    "/speedtest_worker.js": ("application/javascript", BASE_DIR / "static" / "third_party" / "librespeed" / "speedtest_worker.js"),
}

# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------


class ConsoleHandler(BaseHTTPRequestHandler):
    """The authenticated console, on its own hard-to-guess port.

    Every route that does anything lives here. ProbeHandler, further down,
    deliberately shares none of it.
    """

    # No version suffix: the console is not meant to be inventoried by
    # whatever finds the port.
    server_version = "vps-server"
    # HTTP/1.1 keep-alive matters beyond convenience here: every speed-test
    # request that instead paid a fresh TCP+TLS handshake was measuring
    # connection setup, not throughput — the likely cause of the wildly low
    # upload numbers the hand-rolled test used to produce. LibreSpeed's own
    # docs also assume a persistent connection for accurate ping timing.
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass  # every request is recorded in the visitor log instead

    def version_string(self):
        # The base class appends sys_version to server_version, so setting the
        # latter alone still answers "Server: vps-server Python/3.10.12".
        return self.server_version

    def send_response(self, code, message=None):
        self._last_status = code
        super().send_response(code, message)
        if getattr(self, "_close_after_response", False):
            self.send_header("Connection", "close")

    def end_headers(self):
        # Once the headers are out, the response is committed: anything that
        # goes wrong afterwards must not try to send a second one.
        self._body_started = True
        super().end_headers()

    # -- helpers ---------------------------------------------------------

    def get_cookie(self, name):
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        jar = http.cookies.SimpleCookie()
        jar.load(raw)
        morsel = jar.get(name)
        return morsel.value if morsel else None

    def is_authenticated(self):
        if not AUTH_ENABLED:
            return True
        token = self.get_cookie("session")
        return session_valid(token) or ip_session_valid(token, self.client_address[0])

    def is_password_authenticated(self):
        return AUTH_ENABLED and session_valid(self.get_cookie("session"))

    def render_page(self, title, body, lang, active=None, show_nav=True, bare=False, back_href=None):
        return render_page(title, body, lang, active, show_nav,
                           password_authenticated=self.is_password_authenticated(),
                           ip_authenticated=ip_session_valid(self.get_cookie("session"),
                                                             self.client_address[0]), bare=bare,
                           back_href=back_href)

    def client_ip(self):
        if TRUST_PROXY:
            xff = self.headers.get("X-Forwarded-For")
            if xff:
                return xff.split(",")[0].strip()
        return self.client_address[0]

    def resolve_lang(self, parsed):
        query_lang = parse_qs(parsed.query).get("lang", [None])[0]
        cookie_lang = self.get_cookie("lang")
        accept = self.headers.get("Accept-Language", "")
        return pick_lang(cookie_lang, query_lang, accept), query_lang

    def send_html(self, status, body, extra_headers=None):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status, obj):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location, extra_headers=None):
        self.send_response(302)
        self.send_header("Location", location)
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def read_body(self, limit):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0
        length = max(0, min(length, limit))
        return self.rfile.read(length) if length else b""

    def maybe_lang_cookie(self, query_lang):
        # Persist an explicit ?lang= choice so it sticks across pages.
        if query_lang in STRINGS:
            return {"Set-Cookie": f"lang={query_lang}; Path=/; Max-Age={365 * 24 * 3600}; SameSite=Lax"}
        return {}

    # -- dispatch ----------------------------------------------------------

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def _dispatch(self, method):
        parsed = urlsplit(self.path)
        path = parsed.path
        self._last_status = 200
        self._body_started = False
        # A rejected form can leave its POST body unread. Never parse those
        # bytes as the next HTTP/1.1 request on the same connection.
        self._close_after_response = method == "POST" and path != "/speedtest/empty"
        if self._close_after_response:
            self.close_connection = True
        try:
            self._route(method, path, parsed)
        except (BrokenPipeError, ConnectionResetError):
            self._last_status = 0  # client disconnected mid-stream, not a real outcome
        except Exception:
            self._last_status = 500
            # Only when nothing has been sent yet. /speedtest/garbage streams
            # hundreds of megabytes after its headers are out; an SSLError or
            # timeout partway through used to land here and append a second
            # status line and a JSON body into the middle of a response whose
            # Content-Length promised raw bytes — a reply no client can parse.
            if not self._body_started:
                try:
                    self.send_json(500, {"error": "internal server error"})
                except Exception:
                    pass
            else:
                self.close_connection = True
        finally:
            if self._last_status:
                # A failure to record the visit must not take down a request
                # that otherwise succeeded. Raising here escapes into
                # socketserver, which kills the keep-alive connection — and
                # the speed test depends on that connection staying up.
                try:
                    logged_path = "/clash/sub/[redacted]" if path.startswith("/clash/sub/") else path
                    log_visit(self.client_ip(), method, logged_path, self._last_status)
                except Exception as exc:
                    print(_log_text('log_visitor_write', error=exc), file=sys.stderr)

    def _route(self, method, path, parsed):
        if path.startswith("/static/") or path in ("/speedtest_worker.js", "/favicon.ico"):
            return self.serve_static(path)

        if method == "GET" and path.startswith("/clash/sub/"):
            return self.handle_clash_subscription(path)

        lang, query_lang = self.resolve_lang(parsed)

        # With auth off there is nothing to log in or out of: a login form
        # that accepts nothing and a logout link that ends no session are
        # both dead ends, so send those paths back to the dashboard.
        if path in ("/login", "/login/ip", "/logout") and not AUTH_ENABLED:
            return self.redirect("/")
        if path.startswith("/settings") and not AUTH_ENABLED:
            return self.send_html(404, "Not found", {"Cache-Control": "no-store"})

        if method == "GET" and path == "/login":
            next_page = parse_qs(parsed.query).get("next", [""])[0]
            return self.page_login(lang, query_lang, next_page=next_page)
        if method == "POST" and path == "/login":
            return self.handle_login(lang)
        if method == "POST" and path == "/login/ip":
            return self.handle_ip_login(lang)
        if method == "GET" and path == "/logout":
            return self.handle_logout()

        if not self.is_authenticated():
            destination = ("/login?next=changelog" if path == "/changelog" else
                           "/login?next=preferences" if path == "/settings" else
                           "/login?next=settings" if path.startswith("/settings") else "/login")
            return self.redirect(destination)

        page_modules = {"/speedtest": "speedtest", "/iperf": "iperf3", "/proxy": "proxy_nodes",
                        "/portfwd": "portfwd", "/visitors": "visitors",
                        "/changelog": "changelog"}
        if method == "GET" and path in page_modules:
            module = page_modules[path]
            installed = installed_modules(BASE_DIR)
            managed_present = (module == "iperf3" and "iperf3" in installed or
                               module == "proxy_nodes" and bool({"proxy", "anytls"} & installed) or
                               module == "frp" and (bool({"frps", "frpc"} & installed) or bool(frpc_names())))
            if (module in MANAGED_FEATURES or managed_present) and not module_states(installed)[module]:
                return self.redirect(f"/closed?module={module}", {"Cache-Control": "no-store"})
        if method == "GET" and path == "/closed":
            return self.page_module_closed(lang, query_lang, parsed)
        for feature, prefix in (("speedtest", "/speedtest"), ("visitors", "/visitors"),
                                ("changelog", "/changelog"), ("portfwd", "/portfwd")):
            enabled = portfwd_enabled() if feature == "portfwd" else module_feature_enabled(BASE_DIR, feature)
            if path.startswith(prefix + "/") and not enabled:
                return self.send_html(404, "Not found", {"Cache-Control": "no-store"})

        if path == "/settings/verify" and method == "GET":
            next_page = parse_qs(parsed.query).get("next", [""])[0]
            return self.page_security_verify(lang, next_page="frp" if next_page == "frp" else "")
        if path == "/settings/verify" and method == "POST":
            return self.handle_security_verify(lang)
        security_path = path == "/settings/security" or path in (
            "/settings/ip/add", "/settings/ip/remove", "/settings/ip/toggle", "/settings/password")
        if security_path and not security_settings_valid(self.get_cookie("session")):
            if method == "GET":
                target = "/settings/verify?next=frp" if path.startswith("/frp/") else "/settings/verify"
                return self.redirect(target, {"Cache-Control": "no-store"})
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        if method == "GET" and path == "/settings":
            return self.page_preferences(lang, query_lang)
        if method == "GET" and path == "/settings/security":
            return self.page_settings(lang, query_lang, parsed)
        if method == "GET" and path == "/settings/modules":
            return self.page_modules(lang, query_lang)
        if method == "POST" and path == "/settings/modules/action":
            return self.handle_module_action(lang)
        if method == "POST" and path in ("/settings/ip/add", "/settings/ip/remove", "/settings/ip/toggle",
                                         "/settings/password"):
            return self.handle_settings_post(path)

        if method == "GET" and path == "/":
            return self.page_dashboard(lang, query_lang)
        if method == "GET" and path == "/speedtest":
            return self.page_speedtest(lang, query_lang)
        if method == "GET" and path == "/speedtest/garbage":
            return self.handle_speedtest_garbage(parsed)
        if method == "GET" and path == "/speedtest/empty":
            return self.handle_speedtest_ping()
        if method == "POST" and path == "/speedtest/empty":
            return self.handle_speedtest_upload()
        if method == "GET" and path == "/speedtest/getip":
            return self.handle_speedtest_getip()
        # /anytls used to be its own page; it now lives on /proxy alongside
        # every other protocol (see page_proxy()'s docstring). Redirected
        # rather than dropped, for anyone with the old URL bookmarked.
        if method == "GET" and path == "/anytls":
            return self.redirect("/proxy")
        if method == "POST" and path == "/anytls/reset":
            return self.handle_anytls_reset()
        if method == "GET" and path == "/lucky" and AUTH_ENABLED:
            return self.page_lucky(lang, query_lang)
        if method == "GET" and path == "/frps" and AUTH_ENABLED:
            return self.page_frps(lang, query_lang)
        if method == "GET" and path == "/frpc" and AUTH_ENABLED:
            return self.page_frpc(lang, query_lang)
        if method == "GET" and path == "/frp" and AUTH_ENABLED:
            target = '/frps?edit=server' if parse_qs(parsed.query).get('edit') == ['server'] else '/frpc'
            return self.redirect(target, {'Cache-Control': 'no-store'})
        if method == "GET" and path == "/frp/server/edit" and AUTH_ENABLED:
            return self.page_frps_edit(lang)
        if method == "GET" and path == "/frp/client/edit" and AUTH_ENABLED:
            return self.page_frpc_edit(lang, parsed)
        if method == "GET" and path == "/frp/client/address" and AUTH_ENABLED:
            return self.frpc_address_value(parsed)
        if method == "GET" and path == "/frp/client/value" and AUTH_ENABLED:
            return self.frpc_private_value(parsed)
        if method == "POST" and path == "/frp/client/test" and AUTH_ENABLED:
            return self.handle_frpc_test()
        if method == "POST" and path in ("/frp/server/save", "/frp/client/toggle",
                                         "/frp/client/card-toggle", "/frp/client/rename",
                                         "/frp/client/delete", "/frp/server/toggle",
                                         "/frp/client/structured") and AUTH_ENABLED:
            return self.handle_frp_edit(path, lang)
        if method == "GET" and path == "/proxy":
            if not AUTH_ENABLED:
                return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
            return self.page_proxy(lang, query_lang)
        if method == "GET" and path == "/proxy/private-value":
            if not AUTH_ENABLED:
                return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
            return self.handle_proxy_private_value(parsed)
        if method == "POST" and path == "/proxy/reset":
            return self.handle_proxy_reset()
        if method == "POST" and path in ("/proxy/node/edit", "/proxy/node/limits",
                                         "/proxy/node/reset", "/proxy/node/create",
                                         "/proxy/node/delete", "/proxy/node/toggle"):
            if not AUTH_ENABLED:
                return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
            return self.handle_node_control(path.rsplit("/", 1)[-1])
        if method == "POST" and path == "/proxy/apply":
            if not AUTH_ENABLED:
                return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
            return self.handle_node_apply()
        if method == "GET" and path == "/iperf":
            return self.page_iperf(lang, query_lang)
        if method == "POST" and path == "/iperf/open":
            return self.handle_iperf_open()
        if method == "POST" and path == "/iperf/close":
            return self.handle_iperf_close()
        if method == "POST" and path == "/iperf/port":
            return self.handle_iperf_port()
        if method == "GET" and path == "/portfwd":
            return self.page_portfwd(lang, query_lang)
        if method == "POST" and path == "/portfwd/add":
            return self.handle_portfwd_add()
        if method == "POST" and path == "/portfwd/enable":
            return self.handle_portfwd_enable()
        if method == "POST" and path == "/portfwd/disable":
            return self.handle_portfwd_disable()
        if method == "POST" and path == "/portfwd/delete":
            return self.handle_portfwd_delete()
        if method == "GET" and path == "/visitors":
            return self.page_visitors(lang, query_lang)
        if method == "GET" and path == "/changelog":
            return self.page_changelog(lang, query_lang)

        self.send_html(404, self.render_page(STRINGS[lang]["not_found"],
                                        f'<div class="card"><p>{STRINGS[lang]["not_found"]}</p></div>',
                                        lang, show_nav=self.is_authenticated()))

    # -- static --------------------------------------------------------

    def serve_static(self, path):
        entry = STATIC_FILES.get(path)
        if not entry:
            return self.send_html(404, "not found")
        content_type, file_path = entry
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    # -- auth ------------------------------------------------------------

    def page_login(self, lang, query_lang, status=200, error=None, next_page="", password_error=True):
        t = STRINGS[lang]
        if not error and parse_qs(urlsplit(self.path).query).get("ip") == ["unavailable"]:
            error = t["login_ip_unavailable"]
            password_error = False
        error_html = f'<p class="error" id="login-error" role="alert">{html.escape(error)}</p>' if error else ""
        invalid = ' aria-invalid="true" aria-describedby="login-error"' if error and password_error else ""
        next_page = next_page if next_page in ("settings", "preferences", "changelog") else ""
        next_input = f'<input type="hidden" name="next" value="{next_page}">' if next_page else ""
        notice = (f'<p class="muted small">{html.escape(t["admin_sign_in_note"])}</p>'
                  if next_page == "settings" else "")
        changed = ('<p class="notice" role="status">' + html.escape(t["password_changed"]) + '</p>'
                   if parse_qs(urlsplit(self.path).query).get("changed") == ["1"] else "")
        ip_button = (f'<form method="post" action="/login/ip" class="login-ip-form">'
                     f'<button type="submit">{html.escape(t["login_ip_access"])}</button></form>')
        password_field = render_password_field(
            t, "login-password", t["password"], "password",
            f'autocomplete="current-password" autofocus required{invalid}')
        language_menu = (
            f'<div class="login-language-field app-login-language">'
            f'<details class="language-menu login-language-menu"><summary '
            f'aria-label="{html.escape(t["login_language"], quote=True)}: {html.escape(LANG_NAMES[lang], quote=True)}">'
            f'{html.escape(LANG_NAMES[lang])}</summary>'
            f'<div class="language-options">{render_lang_switcher(lang, "&next=" + next_page if next_page else "")}</div>'
            f'</details></div>')
        body = f"""
        <div class="login-shell">
          <div class="login-panel app-login-card">
            <span class="login-mark" aria-hidden="true">{ui_icon('lock-keyhole')}</span>
            <h1>{html.escape(t['login_heading'])}</h1>
            <p class="login-intro">{html.escape(t['login_intro'])}</p>
            {changed}{notice}{error_html}
            <form method="post" action="/login" class="login-form">
              {next_input}
              {password_field}
              <button type="submit" class="login-submit">{html.escape(t['login'])}</button>
            </form>
            {ip_button}
            <div class="login-footer app-login-footer"><a class="login-version app-login-version" href="/changelog">{html.escape(VERSION_LABEL)}</a>{language_menu}</div>
          </div>
        </div>
        """
        headers = self.maybe_lang_cookie(query_lang)
        self.send_html(status, self.render_page(t['login'], body, lang, show_nav=False, bare=True), headers)

    def handle_login(self, lang):
        raw = self.read_body(LOGIN_BODY_LIMIT)
        ip = self.client_address[0]
        allowed, retry_after = LOGIN_LIMITER.check(ip)
        if not allowed:
            return self.page_login(
                lang, None, status=429,
                error=STRINGS[lang]["login_locked"].format(seconds=retry_after),
            )
        form = parse_qs(raw.decode("utf-8", errors="replace"))
        submitted = form.get("password", [""])[0]
        next_page = form.get("next", [""])[0]
        if hmac.compare_digest(submitted, ADMIN_PASSWORD):
            LOGIN_LIMITER.record_success(ip)
            previous = self.get_cookie("session")
            if previous:
                destroy_session(previous)
            token = create_session(security_verified=True)
            cookie = (
                f"session={token}; Path=/; HttpOnly; SameSite=Strict; "
                f"Max-Age={SESSION_TTL_SECONDS}"
            )
            destination = ("/settings/security" if next_page == "settings" else
                           "/settings" if next_page == "preferences" else
                           "/changelog" if next_page == "changelog" else "/")
            return self.redirect(destination,
                                 {"Set-Cookie": cookie})
        LOGIN_LIMITER.record_failure(ip)
        self.page_login(lang, None, status=401, error=STRINGS[lang]["wrong_password"],
                        next_page=next_page)

    def handle_ip_login(self, lang):
        if TRUST_PROXY or not IP_ALLOWLIST.contains(self.client_address[0]):
            return self.redirect("/login?ip=unavailable&next=settings",
                                 {"Cache-Control": "no-store"})
        token = create_ip_session(self.client_address[0])
        cookie = (f"session={token}; Path=/; HttpOnly; SameSite=Strict; "
                  f"Max-Age={SESSION_TTL_SECONDS}")
        return self.redirect("/", {"Set-Cookie": cookie, "Cache-Control": "no-store"})

    def page_security_verify(self, lang, error=None, status=200, next_page=""):
        t = STRINGS[lang]
        token = self.get_cookie("session")
        password_field = render_password_field(
            t, "security-password", t["password"], "password",
            'autocomplete="current-password" required autofocus')
        body = f'''<div class="access-workspace access-verify-workspace"><section class="card access-card">
          <h1>{html.escape(t['access_verify_heading'])}</h1>
          <p>{html.escape(t['access_verify_note'])}</p>
          {f'<p class="error" role="alert">{html.escape(error)}</p>' if error else ''}
          <form class="access-verify-form" method="post" action="/settings/verify" autocomplete="off">
            <input type="hidden" name="csrf" value="{access_csrf_token(token, 'verify')}">
            <input type="hidden" name="next" value="{html.escape(next_page, quote=True)}">
            {password_field}
            <button type="submit">{html.escape(t['access_verify_button'])}</button>
          </form></section></div>'''
        return self.send_html(status,
                              self.render_page(t['access_verify_heading'], body, lang, active="settings", back_href='/settings'),
                              {"Cache-Control": "no-store"})

    def handle_security_verify(self, lang):
        token = self.get_cookie("session")
        if not self.is_authenticated():
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/x-www-form-urlencoded":
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 < length <= LOGIN_BODY_LIMIT:
                raise ValueError
            form = parse_qs(self.rfile.read(length).decode("utf-8"),
                            keep_blank_values=True, strict_parsing=True)
            if set(form) not in ({"csrf", "password"}, {"csrf", "password", "next"}) or any(len(values) != 1 for values in form.values()):
                raise ValueError
        except (UnicodeError, ValueError):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if not hmac.compare_digest(form["csrf"][0], access_csrf_token(token, "verify")):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        next_page = form.get("next", [""])[0]
        if next_page not in ("", "frp"):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        ip = self.client_address[0]
        allowed, retry_after = LOGIN_LIMITER.check(ip)
        if not allowed:
            return self.page_security_verify(lang,
                                             error=STRINGS[lang]["login_locked"].format(seconds=retry_after),
                                             status=429, next_page=next_page)
        if not hmac.compare_digest(form["password"][0], ADMIN_PASSWORD):
            LOGIN_LIMITER.record_failure(ip)
            return self.page_security_verify(lang, error=STRINGS[lang]["wrong_password"], status=401, next_page=next_page)
        LOGIN_LIMITER.record_success(ip)
        destroy_session(token)
        new_token = create_session(security_verified=True)
        cookie = (f"session={new_token}; Path=/; HttpOnly; SameSite=Strict; "
                  f"Max-Age={SESSION_TTL_SECONDS}")
        return self.redirect("/frpc" if next_page == "frp" else "/settings/security",
                             {"Set-Cookie": cookie, "Cache-Control": "no-store"})

    def handle_logout(self):
        token = self.get_cookie("session")
        if token:
            destroy_session(token)
        cookie = "session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
        self.redirect("/login", {"Set-Cookie": cookie})

    def page_preferences(self, lang, query_lang):
        t = STRINGS[lang]
        esc = html.escape
        themes = "".join(
            f'<button type="button" class="preferences-choice" data-theme-choice="{choice}" '
            f'aria-pressed="{str(choice == "slate-blue").lower()}">'
            f'<span class="theme-swatch theme-swatch-{choice}" aria-hidden="true"></span>'
            f'{esc(t[key])}</button>'
            for choice, key in (("slate-blue", "theme_slate_blue"), ("sage", "theme_sage"),
                                ("teal", "theme_teal"), ("plum", "theme_plum"),
                                ("ocean", "theme_ocean"), ("olive", "theme_olive"),
                                ("terracotta", "theme_terracotta"), ("indigo", "theme_indigo")))
        modes = "".join(
            f'<button type="button" class="preferences-choice" data-mode-choice="{mode}" '
            f'aria-pressed="{str(mode == "light").lower()}">{esc(t[key])}</button>'
            for mode, key in (("light", "appearance_light"), ("dark", "appearance_dark")))
        languages = "".join(
            f'<a class="preferences-choice" href="/settings?lang={code}"'
            + (' aria-current="true"' if code == lang else '')
            + f'>{esc(name)}</a>' for code, name in LANG_NAMES.items())
        body = f'''<div class="access-workspace preferences-workspace">
          <h1 class="access-page-title">{esc(t['settings'])}</h1>
          <div class="settings-layout"><nav class="section-nav" aria-label="{esc(t['settings'], quote=True)}">
            <a href="#settings-appearance" aria-current="location">{esc(t['theme_label'])}</a>
            <a href="#settings-language">{esc(t['login_language'])}</a>
            <a href="#settings-modules">{esc(t['modules_heading'])}</a>
            <a href="#settings-security">{esc(t['access_security'])}</a>
          </nav><div class="settings-content">
            <section id="settings-appearance" class="card access-card preferences-card"><h2>{esc(t['theme_label'])}</h2>
              <div class="preferences-mode"><h3>{esc(t['appearance_mode'])}</h3>
                <div class="preferences-choices" role="group" aria-label="{esc(t['appearance_mode'], quote=True)}">{modes}</div></div>
              <h3 class="preferences-group-title">{esc(t['theme_color'])}</h3>
              <div class="preferences-choices" role="group" aria-label="{esc(t['theme_color'], quote=True)}">{themes}</div>
            </section>
            <section id="settings-language" class="card access-card preferences-card"><h2>{esc(t['login_language'])}</h2>
              <div class="preferences-choices" aria-label="{esc(t['login_language'], quote=True)}">{languages}</div>
            </section>
            <section id="settings-modules" class="card access-card preferences-card"><h2>{esc(t['modules_heading'])}</h2>
              <p>{esc(t['modules_note'])}</p><a class="module-manage" href="/settings/modules">{esc(t['modules_manage'])}</a>
            </section>
            <section id="settings-security" class="card access-card preferences-card preferences-security-card">
              <span class="preferences-security-heading">{ui_icon('lock-keyhole')}<h2>{esc(t['access_security'])}</h2></span>
              <span class="preferences-security-details"><span>{esc(t['access_ips'])}</span><span>{esc(t['access_password'])}</span></span>
              <a class="preferences-security-enter" href="/settings/security">{esc(t['access_enter_security'])}</a>
            </section>
          </div></div></div><script src="/static/settings-sections.js" defer></script>'''
        return self.send_html(200, self.render_page(t['settings'], body, lang, active="settings"),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def page_settings(self, lang, query_lang, parsed):
        t = STRINGS[lang]
        esc = html.escape
        token = self.get_cookie("session")
        addresses = IP_ALLOWLIST.list_addresses()
        message = parse_qs(parsed.query).get("msg", [""])[0]
        allowed_messages = {"access_ip_added", "access_ip_removed", "access_ip_invalid",
                            "access_ip_error", "access_password_invalid", "access_ip_enabled", "access_ip_disabled"}
        feedback = (f'<p class="{"notice" if message in ("access_ip_added", "access_ip_removed", "access_ip_enabled", "access_ip_disabled") else "error"}" role="status">'
                    f'{esc(t[message])}</p>') if message in allowed_messages else ""
        load_warning = f'<p class="error" role="alert">{esc(t["access_load_error"])}</p>' if IP_ALLOWLIST.load_error else ""
        rows = "".join(
            f'<li><code>{esc(address)}</code><form method="post" action="/settings/ip/remove">'
            f'<input type="hidden" name="ip" value="{esc(address, quote=True)}">'
            f'<input type="hidden" name="csrf" value="{access_csrf_token(token, "ip-remove")}">'
            f'<button type="submit" class="access-remove" aria-label="{esc(t["access_remove_ip"].format(ip=address), quote=True)}">'
            f'{esc(t["access_remove"])}</button></form></li>' for address in addresses)
        if not rows:
            rows = f'<li class="muted">{esc(t["access_ip_empty"])}</li>'
        new_password_field = render_password_field(
            t, "access-new-password", t["access_new_password"], "new",
            'autocomplete="new-password" minlength="12" maxlength="128" required')
        confirm_password_field = render_password_field(
            t, "access-confirm-password", t["access_confirm_password"], "confirm",
            'autocomplete="new-password" minlength="12" maxlength="128" required')
        body = f'''<div class="access-workspace">
          <h1 class="access-page-title">{esc(t['access_heading'])}</h1>{feedback}
          <div class="settings-layout"><nav class="section-nav" aria-label="{esc(t['access_heading'], quote=True)}">
            <a href="#security-ips" aria-current="location">{esc(t['access_ips'])}</a>
            <a href="#security-password">{esc(t['access_password'])}</a>
          </nav><div class="settings-content"><section id="security-ips" class="access-card access-ip-card">
            <header class="access-card-header"><div><p class="access-eyebrow">{esc(t['access_security'])}</p>
              <h2>{esc(t['access_ips'])}</h2></div>{ui_icon('lock-keyhole')}</header>
            <div class="access-card-body"><p>{esc(t['access_ip_note'])}</p>
              <p>{esc(t['access_ip_shared_note'])}</p>{load_warning}
            <form method="post" action="/settings/ip/toggle" class="access-toggle-form">
              <input type="hidden" name="csrf" value="{access_csrf_token(token, 'ip-toggle')}">
              <input type="hidden" name="enabled" value="{'0' if IP_ALLOWLIST.is_enabled() else '1'}">
              <span>{esc(t['access_ip_switch'])}</span>
              <button type="submit" aria-label="{esc(t['access_ip_disable'] if IP_ALLOWLIST.is_enabled() else t['access_ip_enable'], quote=True)}"
                aria-pressed="{'true' if IP_ALLOWLIST.is_enabled() else 'false'}">{esc(t['access_ip_disable'] if IP_ALLOWLIST.is_enabled() else t['access_ip_enable'])}</button>
            </form>
            <ul class="access-ip-list">{rows}</ul>
            <form method="post" action="/settings/ip/add" class="access-ip-form">
              <input type="hidden" name="csrf" value="{access_csrf_token(token, 'ip-add')}">
              <label class="sr-only" for="access-new-ip">{esc(t['access_ip_address'])}</label>
              <input id="access-new-ip" name="ip" placeholder="192.168.1.10 / fd12::1" required spellcheck="false" autocomplete="off">
              <button type="submit">{esc(t['access_add'])}</button>
            </form>
            </div>
          </section>
          <section id="security-password" class="card access-card"><h2>{esc(t['access_password'])}</h2>
            <form method="post" action="/settings/password" autocomplete="off">
              <input type="hidden" name="csrf" value="{access_csrf_token(token, 'password')}">
              {new_password_field}
              {confirm_password_field}
              <button type="submit">{esc(t['access_change_password'])}</button>
            </form>
          </section></div></div><script src="/static/access-settings.js" defer></script>
          <script src="/static/settings-sections.js" defer></script></div>'''
        return self.send_html(200, self.render_page(t['settings'], body, lang, active="settings", back_href='/settings'),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def handle_settings_post(self, path):
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = 0
        if (not 0 < length <= 4096 or
                self.headers.get("Content-Type", "").split(";", 1)[0].strip() !=
                "application/x-www-form-urlencoded"):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        try:
            form = parse_qs(self.rfile.read(length).decode("utf-8"), strict_parsing=True,
                            keep_blank_values=True)
        except (UnicodeError, ValueError):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if any(len(values) != 1 for values in form.values()):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        action = {"/settings/ip/add": "ip-add", "/settings/ip/remove": "ip-remove",
                  "/settings/ip/toggle": "ip-toggle",
                  "/settings/password": "password"}[path]
        expected = ({"csrf", "new", "confirm"} if action == "password" else
                    {"csrf", "enabled"} if action == "ip-toggle" else {"csrf", "ip"})
        if set(form) != expected:
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if not hmac.compare_digest(form["csrf"][0],
                                   access_csrf_token(self.get_cookie("session"), action)):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        if action == "password":
            if form["new"][0] != form["confirm"][0]:
                key = "access_password_invalid"
            else:
                try:
                    change_admin_password(form["new"][0])
                    key = ""
                except (OSError, ValueError):
                    key = "access_password_invalid"
            if not key:
                cookie = "session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
                return self.redirect("/login?changed=1", {"Set-Cookie": cookie})
        elif action == "ip-toggle":
            if form["enabled"][0] not in ("0", "1"):
                return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
            try:
                IP_ALLOWLIST.set_enabled(form["enabled"][0] == "1")
                key = "access_ip_enabled" if IP_ALLOWLIST.is_enabled() else "access_ip_disabled"
            except OSError:
                key = "access_ip_error"
        else:
            try:
                IP_ALLOWLIST.change(form["ip"][0], add=action == "ip-add")
                key = "access_ip_added" if action == "ip-add" else "access_ip_removed"
            except ValueError:
                key = "access_ip_invalid"
            except OSError:
                key = "access_ip_error"
        return self.redirect(f"/settings/security?msg={key}", {"Cache-Control": "no-store"})

    def page_modules(self, lang, query_lang):
        t = STRINGS[lang]
        esc = html.escape
        token = self.get_cookie("session")
        installed = installed_modules(BASE_DIR)
        job = {}
        try:
            job = json.loads(module_status_path(BASE_DIR).read_text())
        except (OSError, ValueError):
            pass
        busy = job.get("state") in ("queued", "running") and time.time() - job.get("at", 0) < 900
        catalogue = (
            ("speedtest", t["speedtest"], None),
            ("iperf3", t["iperf"], "iperf3"),
            ("proxy_nodes", t["proxy"], "proxy_nodes"),
            ("frps", "FRPS", "frps"),
            ("frpc", "FRPC", "frpc"),
            ("portfwd", t["portfwd"], None),
            ("visitors", t["visitors"], None),
            ("changelog", t["changelog"], None),
            ("settings", t["settings"], None),
        )
        cards = []
        for module, title, installable in catalogue:
            if module == "proxy_nodes":
                present = {"proxy", "anytls"} <= installed
                enabled = present and any(_run_quiet(["systemctl", "is-enabled", "--quiet", MANAGED_UNITS[item]])
                                          for item in ("proxy", "anytls") if item in installed)
            elif module == "frpc":
                present = module in installed
                names = frpc_names() if present else []
                enabled = any(_run_quiet(["systemctl", "is-active", "--quiet", f"frpc@{name}.service"])
                              for name in names)
            elif module == "iperf3":
                present = module in installed
                enabled = present and IPERF_ENABLED
            elif module == "frps":
                present = module in installed
                enabled = present and _run_quiet(["systemctl", "is-enabled", "--quiet", MANAGED_UNITS[module]])
            elif module == "settings":
                present = enabled = True
            else:
                present = True
                enabled = module_feature_enabled(BASE_DIR, module)
            status = (t["module_not_installed"] if not present else
                      t["module_no_instances"] if module == "frpc" and not names else
                      t["module_enabled"] if enabled else t["module_disabled"])
            control = ""
            if installable:
                action = "uninstall" if present else "install"
                label = t["module_uninstall"] if present else t["module_install"]
                confirm = f' data-confirm="{esc(t["module_uninstall_confirm"].format(name=title), quote=True)}"' if present else ""
                control = (f'<form method="post" action="/settings/modules/action">'
                           f'<input type="hidden" name="module" value="{module}">'
                           f'<input type="hidden" name="action" value="{action}">'
                           f'<input type="hidden" name="csrf" value="{access_csrf_token(token, "module:" + module + ":" + action)}">'
                           f'<button type="submit" class="{"danger" if present else ""}"{confirm} '
                           f'{"disabled" if busy else ""}>{esc(label)}</button></form>')
            if module == "frpc" and present and not names:
                control += f'<a class="button-link" href="/frp/client/edit">{esc(t["frp_new_client"])}</a>'
            cards.append(f'<section class="module-card"><div><h2>{esc(title)}</h2>'
                         f'<p>{esc(status)}</p></div>{control}</section>')
        notice = (f'<p class="module-notice" role="status">{esc(t["module_job_" + job["state"]])}: '
                  f'{esc(t.get("module_" + job.get("module", ""), job.get("module", "").upper()))}</p>'
                  if job.get("state") in ("queued", "running", "done", "failed") else "")
        refresh_script = '<script src="/static/module-status.js" defer></script>' if busy else ''
        try:
            log = module_log_path(BASE_DIR).read_text(encoding="utf-8", errors="replace")[-30000:]
        except OSError:
            log = ""
        log_html = (f'<section class="module-log"><h2>{esc(t["module_log"])}</h2>'
                    f'<pre role="log">{esc(log)}</pre></section>') if log else ""
        body = (f'<div class="card module-page"><h1>{esc(t["modules_heading"])}</h1>'
                f'<p>{esc(t["modules_note"])}</p>{notice}'
                f'<div class="module-grid">{"".join(cards)}</div>{log_html}</div>'
                f'<script src="/static/module-controls.js" defer></script>'
                f'{refresh_script}')
        return self.send_html(200, self.render_page(t["modules_heading"], body, lang,
                                                    active="settings", back_href="/settings"),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def handle_module_action(self, lang):
        esc = html.escape
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/x-www-form-urlencoded":
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 < length <= 1024:
                raise ValueError
            form = parse_qs(self.rfile.read(length).decode("utf-8"), strict_parsing=True)
            if set(form) not in ({"module", "action", "csrf"}, {"module", "action", "csrf", "return"}) or any(len(v) != 1 for v in form.values()):
                raise ValueError
        except (UnicodeError, ValueError):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        module, action = form["module"][0], form["action"][0]
        allowed = ("iperf3", "proxy_nodes", "frps", "frpc") if action in ("install", "uninstall") else (
            "iperf3", "proxy_nodes", "frps", "frpc") + MANAGED_FEATURES
        if module not in allowed or action not in ("install", "uninstall", "enable", "disable"):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        expected = access_csrf_token(self.get_cookie("session"), "module:" + module + ":" + action)
        if not hmac.compare_digest(form["csrf"][0], expected):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        destination = "/" if form.get("return", [""])[0] == "home" else "/settings/modules"
        installed = installed_modules(BASE_DIR)
        present = ({"proxy", "anytls"} <= installed if module == "proxy_nodes" else module in installed)
        if action in ("install", "uninstall") and (action == "install") == present:
            return self.redirect(destination, {"Cache-Control": "no-store"})
        install_source = (BASE_DIR / "installer-source" / "deploy" / "systemd" / "frpc@.service" if module == "frpc" else
                          BASE_DIR / "installer-source" / "deploy" / "install.sh")
        if action == "install" and not install_source.is_file():
            return self.send_html(503, esc(STRINGS[lang]["module_source_missing"]),
                                  {"Cache-Control": "no-store"})
        helper = BASE_DIR / "module_manager.py"
        if not helper.is_file() or not shutil.which("systemd-run"):
            return self.send_html(503, esc(STRINGS[lang]["module_source_missing"]),
                                  {"Cache-Control": "no-store"})
        command = ["systemd-run", "--collect", "--unit=vps-server-module-job",
                   "/usr/bin/python3", str(helper), action, module, str(BASE_DIR)]
        with (DATA_DIR / "module-request.lock").open("a+b") as request_lock:
            fcntl.flock(request_lock, fcntl.LOCK_EX)
            try:
                job = json.loads(module_status_path(BASE_DIR).read_text())
                if job.get("state") in ("queued", "running") and time.time() - job.get("at", 0) < 900:
                    return self.redirect(destination, {"Cache-Control": "no-store"})
            except (OSError, ValueError, TypeError):
                pass
            if module in MANAGED_FEATURES and action in ("enable", "disable"):
                if module_feature_enabled(BASE_DIR, module) == (action == "enable"):
                    return self.redirect(destination, {"Cache-Control": "no-store"})
            save_module_status(BASE_DIR, module, "queued")
            try:
                result = subprocess.run(command, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, timeout=10, check=False)
            except (OSError, subprocess.TimeoutExpired):
                result = None
            if result is None or result.returncode:
                save_module_status(BASE_DIR, module, "failed")
                return self.send_html(503, esc(STRINGS[lang]["module_job_failed"]),
                                      {"Cache-Control": "no-store"})
        return self.redirect(destination, {"Cache-Control": "no-store"})

    def page_module_closed(self, lang, query_lang, parsed):
        module = parse_qs(parsed.query).get("module", [""])[0]
        destinations = {"speedtest": "/speedtest", "iperf3": "/iperf", "proxy_nodes": "/proxy",
                        "frps": "/frps", "frpc": "/frpc", "frp": "/frpc", "portfwd": "/portfwd",
                        "visitors": "/visitors", "changelog": "/changelog"}
        if module not in destinations:
            return self.send_html(404, "Not found", {"Cache-Control": "no-store"})
        if module_states()[module]:
            return self.redirect(destinations[module], {"Cache-Control": "no-store"})
        t = STRINGS[lang]
        names = {"speedtest": t["speedtest"], "iperf3": t["iperf"],
                 "proxy_nodes": t["proxy"], "frps": "FRPS", "frpc": "FRPC",
                 "frp": t["frp_heading"], "portfwd": t["portfwd"],
                 "visitors": t["visitors"], "changelog": t["changelog"]}
        body = (f'<div class="card access-card"><h1>{html.escape(t["module_closed_title"])}</h1>'
                f'<p>{html.escape(t["module_closed_help"].format(name=names[module]))}</p></div>')
        return self.send_html(200, self.render_page(t["module_closed_title"], body, lang,
                                                    active="home", back_href="/"),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    # -- dashboard ---------------------------------------------------------

    def page_dashboard(self, lang, query_lang):
        t = STRINGS[lang]
        esc = html.escape
        installed = installed_modules(BASE_DIR)
        states = module_states(installed)
        items = (
            ("speedtest", t["speedtest"], "/speedtest", "gauge", states["speedtest"]),
            ("iperf3", t["iperf"], "/iperf", "activity", states["iperf3"]),
            ("proxy_nodes", t["proxy"], "/proxy", "network", states["proxy_nodes"]),
            ("frps", "FRPS", "/frps", "radio", states["frps"]),
            ("frpc", "FRPC", "/frpc", "network", states["frpc"]),
            ("portfwd", t["portfwd"], "/portfwd", "route", states["portfwd"]),
            ("visitors", t["visitors"], "/visitors", "users-round", states["visitors"]),
            ("changelog", t["changelog"], "/changelog", "scroll-text", states["changelog"]),
            ("settings", t["settings"], "/settings", "settings-2", True),
        )
        try:
            job = json.loads(module_status_path(BASE_DIR).read_text())
            busy = job.get("state") in ("queued", "running") and time.time() - job.get("at", 0) < 900
        except (OSError, ValueError, TypeError):
            busy = False
        tiles = []
        for module, title, href, icon, enabled in items:
            switch = ""
            if module != "settings":
                action = "disable" if enabled else "enable"
                available = (module != "iperf3" or "iperf3" in installed) and (
                    module != "proxy_nodes" or bool({"proxy", "anytls"} & installed)) and (
                    module != "frps" or "frps" in installed) and (
                    module != "frpc" or bool(frpc_names())) and (
                    module != "portfwd" or PORTFWD_ALLOWED)
                switch = (f'<form method="post" action="/settings/modules/action" class="tile-switch-form">'
                          f'<input type="hidden" name="module" value="{module}">'
                          f'<input type="hidden" name="action" value="{action}">'
                          f'<input type="hidden" name="return" value="home">'
                          f'<input type="hidden" name="csrf" value="{access_csrf_token(self.get_cookie("session"), "module:" + module + ":" + action)}">'
                          f'<button type="submit" class="motion-switch" role="switch" aria-label="{esc(title + " " + (t["module_disable"] if enabled else t["module_enable"]), quote=True)}" '
                          f'aria-checked="{str(bool(enabled)).lower()}" {"" if available and not busy else "disabled"}><span aria-hidden="true"></span></button></form>')
            closed = not enabled and (module in MANAGED_FEATURES or
                                      module == "iperf3" and "iperf3" in installed or
                                      module == "proxy_nodes" and bool({"proxy", "anytls"} & installed) or
                                      module in ("frps", "frpc") and module in installed)
            tiles.append(f'<article class="tile" data-module="{module}"><div class="tile-top">'
                         f'<span class="tile-icon">{ui_icon(icon)}</span>{switch}</div>'
                         f'<a class="tile-label" href="{"/closed?module=" + module if closed else href}">{esc(title)}</a></article>')
        notice = f'<p class="module-notice" role="status">{esc(t["module_job_running"])}</p>' if busy else ''
        body = (f'<div class="card"><h1>{esc(t["home"])}</h1>{notice}'
                f'<div class="tiles">{"".join(tiles)}</div></div>'
                + '<script src="/static/module-controls.js" defer></script>'
                + ('<script src="/static/module-status.js" defer></script>' if busy else ''))
        self.send_html(200, self.render_page(t['dashboard'], body, lang, active="home"),
                       self.maybe_lang_cookie(query_lang))

    # -- speed test ----------------------------------------------------

    def page_speedtest(self, lang, query_lang):
        t = STRINGS[lang]
        ip = html.escape(self.client_ip())
        config = {
            # Maps onto LibreSpeed's own Settings keys — see vps-webserver
            # DECISIONS.md (2026-08-25, "Vendor LibreSpeed's official test engine").
            "urlDl": "/speedtest/garbage",
            "urlUl": "/speedtest/empty",
            "urlPing": "/speedtest/empty",
            "urlGetIp": "/speedtest/getip",
            # "P_D_U": ping+jitter, download, upload. No "I" (IP lookup) —
            # the IP is already server-rendered above, so skip the extra
            # round trip.
            "testOrder": "P_D_U",
            "timeDlMax": TEST_SECONDS,
            "timeUlMax": TEST_SECONDS,
            "warmup": WARMUP_SECONDS,
            "pingSamples": PING_SAMPLES,
            "downloadStreams": DOWNLOAD_STREAMS,
            "uploadStreams": UPLOAD_STREAMS,
            "overhead": OVERHEAD_FACTOR,
            "chunkSizeMiB": min(100, MAX_TEST_MB),
        }
        i18n = {k: t[k] for k in ("run_test", "running", "download", "upload",
                                  "latency", "jitter", "waiting", "warmup",
                                  "measuring", "done", "idle")}
        body = f"""
        <div class="card">
          <h1>{html.escape(t['speedtest'])}</h1>
          <p class="muted">{html.escape(t['your_ip'])}: <strong>{ip}</strong></p>
          <div class="gauges latency-row">
            <div class="gauge small-gauge">
              <div class="gauge-label">⏱ {html.escape(t['latency'])}</div>
              <div class="gauge-value" id="latency-value">{html.escape(t['idle'])}</div>
              <div class="gauge-unit">ms</div>
              <div class="gauge-state muted" id="latency-state">{html.escape(t['waiting'])}</div>
            </div>
            <div class="gauge small-gauge">
              <div class="gauge-label">〜 {html.escape(t['jitter'])}</div>
              <div class="gauge-value" id="jitter-value">{html.escape(t['idle'])}</div>
              <div class="gauge-unit">ms</div>
              <div class="gauge-state muted" id="jitter-state">&nbsp;</div>
            </div>
          </div>
          <div class="gauges">
            <div class="gauge">
              <div class="gauge-label">⬇ {html.escape(t['download'])}</div>
              <div class="gauge-value" id="download-value">{html.escape(t['idle'])}</div>
              <div class="gauge-unit">Mbps</div>
              <div class="bar"><span id="download-bar"></span></div>
              <div class="gauge-state muted" id="download-state">{html.escape(t['waiting'])}</div>
            </div>
            <div class="gauge">
              <div class="gauge-label">⬆ {html.escape(t['upload'])}</div>
              <div class="gauge-value" id="upload-value">{html.escape(t['idle'])}</div>
              <div class="gauge-unit">Mbps</div>
              <div class="bar"><span id="upload-bar"></span></div>
              <div class="gauge-state muted" id="upload-state">{html.escape(t['waiting'])}</div>
            </div>
          </div>
          <button id="run">{html.escape(t['run_test'])}</button>
        </div>
        <script id="speedtest-config" type="application/json">{json.dumps(config)}</script>
        <script id="speedtest-i18n" type="application/json">{json.dumps(i18n)}</script>
        <script src="/static/speedtest.js"></script>
        <script src="/static/speedtest-ui.js"></script>
        """
        self.send_html(200, self.render_page(t['speedtest'], body, lang, active="speedtest"),
                       self.maybe_lang_cookie(query_lang))

    # These three implement LibreSpeed's own client/server contract exactly
    # (garbage.php / empty.php / getIP.php equivalents) rather than a
    # hand-rolled protocol — see vps-webserver DECISIONS.md (2026-08-25). Header set and
    # ckSize clamping match the reference PHP backend byte-for-byte so the
    # vendored speedtest.js/speedtest_worker.js need no server-side quirks.

    def handle_speedtest_garbage(self, parsed):
        q = parse_qs(parsed.query)
        try:
            chunks = int(q.get("ckSize", ["4"])[0])
        except ValueError:
            chunks = 4
        if chunks <= 0:
            chunks = 4
        # Upstream clamps at 1024 (1 GiB); MAX_TEST_MB is our own additional
        # ceiling on top of that.
        chunks = min(chunks, 1024, MAX_TEST_MB)

        self.send_response(200)
        self.send_header("Content-Description", "File Transfer")
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", "attachment; filename=random.dat")
        self.send_header("Content-Transfer-Encoding", "binary")
        self.send_header("Content-Length", str(chunks * DOWNLOAD_CHUNK))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0")
        self.send_header("Cache-Control", "post-check=0, pre-check=0")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        for _ in range(chunks):
            self.wfile.write(FILL_BUFFER)

    def handle_speedtest_ping(self):
        """GET on the same endpoint upload POSTs to — LibreSpeed times the
        round trip of downloading this empty response itself; there is no
        separate ping protocol. See doc.md in the upstream repo.
        """
        self.send_response(200)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0")
        self.send_header("Cache-Control", "post-check=0, pre-check=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def handle_speedtest_upload(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0
        length = max(0, min(length, MAX_TEST_MB * 1024 * 1024 + 1024))

        remaining = length
        buf = bytearray(DOWNLOAD_CHUNK)
        view = memoryview(buf)
        while remaining > 0:
            n = self.rfile.readinto(view[: min(len(buf), remaining)])
            if not n:
                break
            remaining -= n

        # The client only checks the HTTP status, never the response body.
        self.send_response(200)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0")
        self.send_header("Cache-Control", "post-check=0, pre-check=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def handle_speedtest_getip(self):
        # No ISP/geolocation lookup — that would need an outbound call to a
        # third party, which conflicts with the zero-dependency design (see
        # vps-webserver DECISIONS.md, "Zero third-party runtime dependencies").
        self.send_json(200, {"processedString": self.client_ip(), "rawIspInfo": ""})

    # -- iperf3 window -------------------------------------------------

    def page_iperf(self, lang, query_lang):
        t = STRINGS[lang]
        port = IPERF_WINDOW.port
        is_open, remaining = IPERF_WINDOW.state()

        notice = ""
        key = parse_qs(urlsplit(self.path).query).get("msg", [""])[0]
        if key in IPERF_MESSAGE_KEYS:
            cls = "error" if key == "iperf_port_invalid" else "notice"
            notice = f'<p class="{cls}">{html.escape(t[key].format(port="••••••"))}</p>'

        countdown_script = ""
        if is_open:
            # The countdown used to be a static string baked in at render
            # time — an operator reported it never moving, only a manual
            # reload showed a new value. deadline is an absolute Unix
            # timestamp so /static/iperf-countdown.js can tick the visible
            # minutes/seconds down every second without another request,
            # and reload once it reaches zero (the window has actually
            # closed itself server-side by then). None of the interpolated
            # values are attacker-controlled — port is server config, mins/
            # secs are ints — so building this without html.escape is safe;
            # escaping it would also escape the <span> tags the script needs.
            deadline = int(time.time()) + remaining
            state = t["iperf_state_open"].format(
                port='••••••',
                mins=f'<span id="iperf-mins">{remaining // 60}</span>',
                secs=f'<span id="iperf-secs">{remaining % 60}</span>',
            )
            state_attr = f' data-iperf-deadline="{deadline}"'
            countdown_script = '<script src="/static/iperf-countdown.js"></script>'
            # While a window is open, submitting the same form pushes the
            # deadline out rather than starting a second server. Labelling it
            # "open" then leaves two buttons that look like they compete; the
            # pair only reads correctly as extend / close.
            open_label = t["iperf_extend"]
            close_form = f"""
            <form method="post" action="/iperf/close">
              <button type="submit" class="danger">{html.escape(t['iperf_close'])}</button>
            </form>
            """
        else:
            state = html.escape(t["iperf_state_closed"].format(port='••••••'))
            state_attr = ""
            open_label = t["iperf_open"]
            close_form = ""

        commands = ''.join(
            f'<div class="copyrow"><div class="copyhead">{html.escape(t[label])}</div>'
            f'{self.private_value_control("iperf", field, t, copy=True)}</div>'
            for label, field in (("iperf_cmd_default", "cmd-default"),
                                 ("iperf_cmd_reverse", "cmd-reverse"),
                                 ("iperf_cmd_udp", "cmd-udp")))

        body = f"""
        <div class="card">
          <h1>{html.escape(t['iperf_heading'])}</h1>
          {notice}
          <div class="iperf-facts">
            <div class="iperf-fact"><span>{html.escape(t['iperf_status'])}</span><strong class="iperf-state {'is-open' if is_open else 'is-closed'}"{state_attr}>{state}</strong></div>
            <div class="iperf-fact"><span>{html.escape(t['iperf_port'])}</span><strong>{self.private_value_control('iperf', 'port', t)}</strong></div>
          </div>
          <form method="post" action="/iperf/port" class="iperf-port-form">
            <label>{html.escape(t['iperf_change_port'])}<input type="number" name="port" min="1024" max="65535" placeholder="••••••" required {'disabled' if is_open else ''}></label>
            <button type="submit" {'disabled' if is_open else ''}>{html.escape(t['iperf_save_port'])}</button>
          </form>
          <div class="iperf-actions">
            <form method="post" action="/iperf/open" class="inline-form">
              <label>{html.escape(t['iperf_minutes'])}
                <input type="number" name="minutes" min="1" max="{IPERF_MAX_MINUTES}"
                       value="{IPERF_DEFAULT_MINUTES}" required>
              </label>
              <button type="submit">{html.escape(open_label)}</button>
            </form>
            {close_form}
          </div>
          <p class="muted">{html.escape(t['iperf_howto'])}</p>
          {commands}
        </div>
        <script src="/static/copy.js"></script>
        <script src="/static/private-values.js"></script>
        {countdown_script}
        """
        self.send_html(200, self.render_page(t['iperf_heading'], body, lang, active="iperf"),
                       self.maybe_lang_cookie(query_lang))

    def handle_iperf_open(self):
        raw = self.read_body(LOGIN_BODY_LIMIT)
        form = parse_qs(raw.decode("utf-8", errors="replace"))
        minutes = form.get("minutes", [str(IPERF_DEFAULT_MINUTES)])[0]
        _, key = IPERF_WINDOW.open(minutes)
        self.redirect(f"/iperf?msg={key}")

    def handle_iperf_close(self):
        self.read_body(LOGIN_BODY_LIMIT)  # drain: keep-alive needs the body gone
        IPERF_WINDOW.close()
        self.redirect("/iperf?msg=iperf_shut")

    def handle_iperf_port(self):
        raw = self.read_body(LOGIN_BODY_LIMIT)
        try:
            form = parse_qs(raw.decode("utf-8"), strict_parsing=True)
            if set(form) != {"port"} or len(form["port"]) != 1:
                raise ValueError("invalid form")
            port = int(form["port"][0])
            if not 1024 <= port <= 65535:
                raise ValueError("invalid port")
            if port != IPERF_WINDOW.port:
                if port in PORTFWD.reserved_ports():
                    raise ValueError("reserved port")
                for family, address in ((socket.AF_INET, "0.0.0.0"), (socket.AF_INET6, "::")):
                    try:
                        with socket.socket(family, socket.SOCK_STREAM) as probe:
                            probe.bind((address, port))
                    except OSError as exc:
                        if family == socket.AF_INET6 and exc.errno in (97, 93):
                            continue
                        raise ValueError("busy port") from exc
            if not IPERF_WINDOW.set_port(
                    port, commit=lambda old: node_control_apply(
                        {"action": "iperf-port", "old_port": old, "port": port})):
                raise ValueError("active window or persistence failure")
        except (UnicodeError, ValueError):
            return self.redirect("/iperf?msg=iperf_port_invalid")
        return self.redirect("/iperf?msg=iperf_port_saved")

    # -- port forwarding -------------------------------------------------

    def page_portfwd(self, lang, query_lang):
        t = STRINGS[lang]
        notice = ""
        key = parse_qs(urlsplit(self.path).query).get("msg", [""])[0]
        if key in PORTFWD_MESSAGE_KEYS:
            cls = "notice" if key in (
                "portfwd_added", "portfwd_removed", "portfwd_enabled", "portfwd_disabled",
            ) else "error"
            notice = f'<p class="{cls}">{html.escape(t[key].format(max=PORTFWD_MAX_RULES))}</p>'

        rows = []
        for rule in PORTFWD.list_rules():
            label = html.escape(rule["label"] or rule["id"])
            proto = html.escape(rule["protocol"].upper())
            state_cls = "is-open" if rule["enabled"] else "is-closed"
            state_label = t["portfwd_state_on"] if rule["enabled"] else t["portfwd_state_off"]
            toggle_action = "/portfwd/disable" if rule["enabled"] else "/portfwd/enable"
            toggle_label = t["portfwd_disable"] if rule["enabled"] else t["portfwd_enable"]
            rows.append(f"""
            <div class="node-addr">
              <h2>{label}</h2>
              <p class="iperf-state {state_cls}">{html.escape(state_label)}
                &mdash; {proto} :{self.private_value_control('forward-' + rule['id'], 'public-port', t)} {html.escape(t['portfwd_via'])}
                {html.escape(rule['target_host'])}:{self.private_value_control('forward-' + rule['id'], 'target-port', t)}</p>
              <div class="iperf-actions">
                <form method="post" action="{toggle_action}" class="inline-form">
                  <input type="hidden" name="id" value="{html.escape(rule['id'])}">
                  <button type="submit">{html.escape(toggle_label)}</button>
                </form>
                <form method="post" action="/portfwd/delete" class="inline-form">
                  <input type="hidden" name="id" value="{html.escape(rule['id'])}">
                  <button type="submit" class="danger">{html.escape(t['portfwd_delete'])}</button>
                </form>
              </div>
            </div>
            """)
        rules_html = "".join(rows) if rows else f'<p class="muted">{html.escape(t["portfwd_none"])}</p>'

        add_form = ""
        if portfwd_enabled():
            add_form = f"""
            <div class="node-addr">
              <h2>{html.escape(t['portfwd_add'])}</h2>
              <form method="post" action="/portfwd/add" class="inline-form">
                <label>{html.escape(t['portfwd_label'])}
                  <input type="text" name="label" maxlength="80">
                </label>
                <fieldset class="protocol-choice">
                  <legend>{html.escape(t['portfwd_protocol'])}</legend>
                  <label><input type="radio" name="protocol" value="tcp" checked> TCP</label>
                  <label><input type="radio" name="protocol" value="udp"> UDP</label>
                  <label><input type="radio" name="protocol" value="both"> TCP+UDP</label>
                </fieldset>
                <label>{html.escape(t['portfwd_public_port'])}
                  <input type="number" name="public_port" min="1" max="65535" required>
                </label>
                <label>{html.escape(t['portfwd_target_host'])}
                  <input type="text" name="target_host" placeholder="100.x.x.x" required>
                </label>
                <label>{html.escape(t['portfwd_target_port'])}
                  <input type="number" name="target_port" min="1" max="65535" required>
                </label>
                <button type="submit">{html.escape(t['portfwd_add'])}</button>
              </form>
            </div>
            """

        body = f"""
        <div class="card wide">
          <h1>{html.escape(t['portfwd_heading'])}</h1>
          {notice}
          <p class="muted">{html.escape(t['portfwd_intro'])}</p>
          {rules_html}
          {add_form}
        </div>
        <script src="/static/private-values.js"></script>
        """
        self.send_html(200, self.render_page(t['portfwd_heading'], body, lang, active="portfwd"),
                       self.maybe_lang_cookie(query_lang))

    def handle_portfwd_add(self):
        raw = self.read_body(LOGIN_BODY_LIMIT)
        form = parse_qs(raw.decode("utf-8", errors="replace"))
        protocol = form.get("protocol", ["tcp"])[0]
        if protocol not in ("tcp", "udp", "both"):
            protocol = "tcp"
        label = form.get("label", [""])[0].strip()
        public_port = _valid_port(form.get("public_port", [""])[0])
        target_port = _valid_port(form.get("target_port", [""])[0])
        target_host = form.get("target_host", [""])[0].strip()
        if public_port is None or target_port is None or not _valid_target_host(target_host):
            return self.redirect("/portfwd?msg=portfwd_invalid")
        _, key = PORTFWD.add(protocol, public_port, target_host, target_port, label)
        self.redirect(f"/portfwd?msg={key}")

    def handle_portfwd_enable(self):
        raw = self.read_body(LOGIN_BODY_LIMIT)
        form = parse_qs(raw.decode("utf-8", errors="replace"))
        key = PORTFWD.set_enabled(form.get("id", [""])[0], True)
        self.redirect(f"/portfwd?msg={key}")

    def handle_portfwd_disable(self):
        raw = self.read_body(LOGIN_BODY_LIMIT)
        form = parse_qs(raw.decode("utf-8", errors="replace"))
        key = PORTFWD.set_enabled(form.get("id", [""])[0], False)
        self.redirect(f"/portfwd?msg={key}")

    def handle_portfwd_delete(self):
        raw = self.read_body(LOGIN_BODY_LIMIT)
        form = parse_qs(raw.decode("utf-8", errors="replace"))
        key = PORTFWD.remove(form.get("id", [""])[0])
        self.redirect(f"/portfwd?msg={key}")

    # -- anytls node ----------------------------------------------------

    def page_lucky(self, lang, query_lang):
        t = STRINGS[lang]
        data = lucky_admin()
        if data is None:
            return self.send_html(404, self.render_page('Lucky', f'<div class="card">{html.escape(t["lucky_not_installed"])}</div>', lang))
        public = data.get('AllowInternetaccess') is True
        address = t['lucky_server_address'] if public else 'localhost'
        status = t['node_active'] if _run_quiet(['systemctl', 'is-active', '--quiet', LUCKY_SERVICE]) else t['node_stopped']
        body = (f'<div class="card"><h1>Lucky</h1><p>{html.escape(t["lucky_admin_note"])}</p>'
                f'<p>{html.escape(t["lucky_admin"])}: {html.escape(address)}: '
                f'{self.private_value_control("lucky", "port", t)}</p>'
                f'{"<p>" + html.escape(t["lucky_ssh_tunnel"]) + "</p>" if not public else ""}'
                f'<p>{html.escape(t["frps_status"])}: {html.escape(status)}</p>'
                f'<p>{html.escape(t["lucky_account"])}: {self.private_value_control("lucky", "account", t)}</p>'
                f'<p>{html.escape(t["lucky_password"])}: {self.private_value_control("lucky", "credential", t, copy=True)}</p>'
                '</div><script src="/static/copy.js"></script><script src="/static/private-values.js"></script>')
        return self.send_html(200, self.render_page('Lucky', body, lang),
                              {**self.maybe_lang_cookie(query_lang), 'Cache-Control': 'no-store'})

    def page_frps(self, lang, query_lang):
        t = STRINGS[lang]
        node = frps_node()
        esc = html.escape
        if node is None:
            server = f'<p class="muted">{esc(t["frps_not_installed"])}</p>'
        else:
            running = _run_quiet(['systemctl', 'is-active', '--quiet', FRPS_SERVICE])
            status = t['node_active'] if running else t['frp_not_running']
            addresses = address_entries(t)
            address_list = (f'<div class="frp-addresses"><h3>{esc(t["frp_addresses"])}</h3><ul>' +
                            ''.join(f'<li><span>{esc(label)}</span><code>{esc(address)}</code></li>'
                                    for label, address in addresses) + '</ul></div>') if addresses else ''
            toggle_action = 'disable' if running else 'enable'
            toggle = (f'<form method="post" action="/frp/server/toggle" class="node-toggle-form">'
                      f'<input type="hidden" name="action" value="{toggle_action}">'
                      f'<input type="hidden" name="csrf" value="{access_csrf_token(self.get_cookie("session"), "frp:server:" + toggle_action)}">'
                      f'<button type="submit" class="node-toggle" role="switch" aria-checked="{str(running).lower()}" '
                      f'aria-label="{esc(t["frp_stop_server"] if running else t["frp_start_server"], quote=True)}"><span></span></button></form>')
            inline_token = render_password_field(t, 'frps-inline-token', t['frps_token'], 'token',
                                                 'maxlength="128" autocomplete="new-password"')
            edit = (f'<details class="node-inline-edit frp-inline-edit" {"open" if parse_qs(urlsplit(self.path).query).get("edit") == ["server"] else ""}><summary><span>{esc(t["frp_edit_server"])}</span>'
                    f'<span>{esc(t["node_cancel"])}</span></summary><form method="post" action="/frp/server/save" autocomplete="off">'
                    f'<input type="hidden" name="csrf" value="{access_csrf_token(self.get_cookie("session"), "frp:server")}">'
                    f'<label>{esc(t["proxy_port"])}<input type="number" name="port" min="1" max="65535" '
                    f'placeholder="{esc(t["frp_port_keep"], quote=True)}"></label>'
                    f'{inline_token}'
                    f'<p class="muted small">{esc(t["frp_token_keep"])}</p><button type="submit">{esc(t["frp_save"])}</button>'
                    f'</form></details>')
            edit_entry = edit
            server = (f'<div class="frp-status-line"><span class="proxy-node-status {"is-open" if running else "is-closed"}">{esc(status)}</span>{toggle}</div>'
                      f'{edit_entry}'
                      f'<dl class="frp-facts"><div><dt>{esc(t["frps_status"])}</dt><dd>{esc(status)}</dd></div>'
                      f'<div><dt>{esc(t["frps_bind"])}</dt><dd><code>{esc(node["address"])}</code></dd></div>'
                      f'<div><dt>{esc(t["proxy_port"])}</dt><dd>{self.private_value_control("frps", "port", t)}</dd></div>'
                      f'<div><dt>{esc(t["frps_token"])}</dt><dd>{self.private_value_control("frps", "credential", t, copy=True)}</dd></div></dl>'
                      f'{address_list}')
        message = parse_qs(urlsplit(self.path).query).get("msg", [""])[0]
        feedback = (f'<p class="{"notice" if message == "done" else "error"}" role="status">'
                    f'{esc(t["frp_saved"] if message == "done" else t["frp_save_failed"])}</p>') if message in ("done", "failed") else ""
        body = (f'<div class="frp-workspace"><div class="frp-heading"><h1>{esc(t["frps_heading"])}</h1></div>{feedback}'
                f'<section class="card frp-card"><div class="frp-card-head">{ui_icon("server")}'
                f'<h2>{esc(t["frps_heading"])}</h2></div>{server}</section></div>'
                '<script src="/static/copy.js"></script><script src="/static/private-values.js"></script>'
                '<script src="/static/password-fields.js"></script>')
        return self.send_html(200, self.render_page(t["frps_heading"], body, lang),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def page_frpc(self, lang, query_lang):
        t = STRINGS[lang]
        esc = html.escape
        clients = []
        for name in frpc_names():
            try:
                item = frpc_summary(name)
            except (OSError, ValueError):
                continue
            connected = frpc_connected(name, item['server'], item['port'])
            running_client = _run_quiet(['systemctl', 'is-active', '--quiet', f'frpc@{name}.service'])
            toggle_action = 'disable' if running_client else 'enable'
            state = t['frp_connected'] if connected else t['frp_disconnected']
            clients.append(f'<article class="frp-target-card"><div class="frp-target-head">'
                           f'<strong class="frp-target-name">{esc(name)}</strong>'
                           f'<form method="post" action="/frp/client/card-toggle" class="node-toggle-form">'
                           f'<input type="hidden" name="name" value="{esc(name, quote=True)}">'
                           f'<input type="hidden" name="action" value="{toggle_action}">'
                           f'<input type="hidden" name="csrf" value="{access_csrf_token(self.get_cookie("session"), "frp:toggle:" + name + ":" + toggle_action)}">'
                           f'<button type="submit" class="node-toggle" role="switch" aria-checked="{str(running_client).lower()}" '
                           f'aria-label="{esc(t["frp_stop_client"] if running_client else t["frp_start_client"], quote=True)}"><span aria-hidden="true"></span></button></form>'
                           f'<span class="proxy-node-status {"is-open" if connected else "is-closed"}" '
                           f'data-frpc-state aria-live="polite">{esc(state)}</span>'
                           f'<button type="button" class="frp-test-connection" data-name="{esc(name, quote=True)}" '
                           f'data-csrf="{access_csrf_token(self.get_cookie("session"), "frp:test:" + name)}" '
                           f'data-testing="{esc(t["frp_testing"], quote=True)}" '
                           f'data-connected="{esc(t["frp_connected"], quote=True)}" '
                           f'data-disconnected="{esc(t["frp_disconnected"], quote=True)}" '
                           f'data-failed="{esc(t["frp_test_failed"], quote=True)}">'
                           f'{esc(t["frp_test_connection"])}</button>'
                           f'<a class="button-link frp-card-edit" href="/frp/client/edit?name={quote(name)}">{esc(t["frp_edit_client_button"])}</a></div>'
                           f'<div class="frp-target-meta"><button type="button" class="frp-fact-reveal frp-card-ip" '
                           f'data-name="{esc(name, quote=True)}" data-field="server" '
                           f'data-masked="{esc(masked_frpc_ip(item["server"]), quote=True)}" '
                           f'data-show="{esc(t["login_show_password"], quote=True)}" '
                           f'data-hide="{esc(t["login_hide_password"], quote=True)}" '
                           f'data-label="{esc(t["frp_server_ip"], quote=True)}" aria-pressed="false" '
                           f'aria-label="{esc(t["login_show_password"] + " " + t["frp_server_ip"], quote=True)}">'
                           f'<code>{esc(masked_frpc_ip(item["server"]))}</code></button></div>'
                           f'<div class="frp-target-foot"><span class="muted small">{item["proxies"]} {esc(t["frp_proxies"])}</span>'
                           f'<button type="button" class="node-action node-action-danger frp-client-delete-open" '
                           f'data-dialog-open="frp-delete-{esc(name, quote=True)}">{esc(t["frp_delete_client"])}</button></div>'
                           f'<dialog class="node-confirm-dialog" id="frp-delete-{esc(name, quote=True)}" '
                           f'aria-labelledby="frp-delete-title-{esc(name, quote=True)}"><form method="post" action="/frp/client/delete">'
                           f'<h3 id="frp-delete-title-{esc(name, quote=True)}">{esc(t["frp_delete_client"])}</h3>'
                           f'<p>{esc(t["frp_delete_client_confirm"].format(name=name))}</p>'
                           f'<input type="hidden" name="name" value="{esc(name, quote=True)}">'
                           f'<input type="hidden" name="csrf" value="{access_csrf_token(self.get_cookie("session"), "frp:delete:" + name)}">'
                           f'<div class="node-dialog-actions"><button type="button" data-dialog-close>{esc(t["node_cancel"])}</button>'
                           f'<button type="submit" class="danger">{esc(t["frp_delete_client"])}</button></div>'
                           f'</form></dialog></article>')
        client_list = ''.join(clients) if clients else f'<p class="muted">{esc(t["frp_no_clients"])}</p>'
        client_installed = "frpc" in installed_modules(BASE_DIR)
        availability = '' if client_installed else f'<p class="error">{esc(t["frp_client_binary_missing"])}</p>'
        message = parse_qs(urlsplit(self.path).query).get('msg', [''])[0]
        feedback = (f'<p class="{"notice" if message == "done" else "error"}" role="status">'
                    f'{esc(t["frp_saved"] if message == "done" else t["frp_save_failed"])}</p>') if message in ('done', 'failed') else ''
        body = (f'<div class="frp-workspace"><div class="frp-heading"><h1>{esc(t["frp_client_heading"])}</h1></div>{feedback}'
                f'<section class="card frp-card"><div class="frp-card-head">{ui_icon("network")}'
                f'<h2>{esc(t["frp_client_heading"])}</h2></div>{availability}'
                f'<h3>{esc(t["frp_instances"])}</h3>{client_list}'
                f'<p><a class="button-link" href="{"/frp/client/edit" if client_installed else "/settings/modules"}">'
                f'{esc(t["frp_new_client"] if client_installed else t["module_install"] + " FRPC")}</a></p>'
                '</section></div>'
                '<script src="/static/frp-editor.js" defer></script>')
        return self.send_html(200, self.render_page(t["frp_client_heading"], body, lang),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def page_frps_edit(self, lang):
        return self.redirect('/frps?edit=server', {'Cache-Control': 'no-store'})

    def page_frpc_edit(self, lang, parsed):
        t, esc = STRINGS[lang], html.escape
        name = parse_qs(parsed.query).get('name', [''])[0]
        if not name and "frpc" not in installed_modules(BASE_DIR):
            return self.redirect('/settings/modules', {'Cache-Control': 'no-store'})
        if name:
            try:
                if not frpc_path(name).is_file() or frpc_path(name).is_symlink():
                    raise ValueError
            except (OSError, ValueError):
                return self.send_html(404, 'FRPC instance missing', {'Cache-Control': 'no-store'})
        structured = None
        if name:
            try:
                structured = frpc_structured(name)
            except (OSError, ValueError, KeyError, TypeError):
                pass
        rename = (f'<details class="node-inline-edit frp-rename"><summary><span>{esc(t["frp_rename_client"])}</span>'
                  f'<span>{esc(t["node_cancel"])}</span></summary><form method="post" action="/frp/client/rename">'
                  f'<input type="hidden" name="name" value="{esc(name, quote=True)}">'
                  f'<input type="hidden" name="csrf" value="{access_csrf_token(self.get_cookie("session"), "frp:rename:" + name)}">'
                  f'<label>{esc(t["frp_instance_name"])}<input name="newName" pattern="[A-Za-z0-9_-]{{1,32}}" '
                  f'maxlength="32" value="{esc(name, quote=True)}" required></label>'
                  f'<button type="submit">{esc(t["frp_save"])}</button></form></details>') if name else ''
        message = parse_qs(parsed.query).get('msg', [''])[0]
        feedback = (f'<p class="{"notice" if message == "done" else "error"}" role="status">'
                    f'{esc(t["frp_saved"] if message == "done" else t["frp_save_failed"])}</p>') if message in ('done', 'failed') else ''
        editor = (self.frpc_structured_editor(lang, name, structured) if structured else
                  self.frpc_create_editor(lang) if not name else
                  f'<p class="error">{esc(t["frp_unsupported_config"])}</p>')
        body = (f'<div class="card wide frp-edit"><h1>{esc(name if name else t["frp_new_client"])}</h1>'
                f'{rename}{feedback}<div class="frp-structured">{editor}</div></div>')
        if name:
            body += '<script src="/static/frp-editor.js" defer></script>'
        body += '<script src="/static/password-fields.js"></script>'
        return self.send_html(200, self.render_page(name if name else t['frp_new_client'], body, lang, back_href='/frpc'),
                              {'Cache-Control': 'no-store'})

    def frpc_structured_editor(self, lang, name, config):
        t, esc = STRINGS[lang], html.escape
        def hint(label_key, help_key, suffix):
            ident = f'frp-help-{name}-{suffix}'
            return (f'<span class="info-popover-wrap frp-info-wrap"><button type="button" '
                    f'class="frp-info-trigger" aria-describedby="{esc(ident, quote=True)}" '
                    f'aria-expanded="false">{esc(t[label_key])}</button>'
                    f'<span class="info-popover" id="{esc(ident, quote=True)}" role="tooltip">'
                    f'<strong>{esc(t[label_key])}</strong><p>{esc(t[help_key])}</p></span></span>')
        def reveal(field, masked, label):
            return (f'<button type="button" class="frp-fact-reveal" data-name="{esc(name, quote=True)}" '
                    f'data-field="{field}" data-masked="{esc(masked, quote=True)}" '
                    f'data-show="{esc(t["login_show_password"], quote=True)}" '
                    f'data-hide="{esc(t["login_hide_password"], quote=True)}" '
                    f'data-label="{esc(label, quote=True)}" aria-pressed="false" '
                    f'aria-label="{esc(t["login_show_password"] + " " + label, quote=True)}">'
                    f'<code>{esc(masked)}</code></button>')
        server_token_field = render_password_field(t, 'frpc-server-token', t['frps_token'], 'token',
                                                   f'maxlength="128" autocomplete="new-password" data-load-token="{esc(name, quote=True)}"')
        base = (f'<input type="hidden" name="name" value="{esc(name, quote=True)}">'
                f'<input type="hidden" name="csrf" value="{access_csrf_token(self.get_cookie("session"), "frp:structured:" + name)}">')
        server = (f'<section class="frp-edit-section"><h2>{esc(t["frp_server_settings"])}</h2>'
                  f'<details class="node-inline-edit"><summary><span>{esc(t["frp_edit_target"])}</span><span>{esc(t["node_cancel"])}</span></summary>'
                  f'<form method="post" action="/frp/client/structured" autocomplete="off">{base}'
                  f'<input type="hidden" name="section" value="server">'
                  f'<label>{esc(t["frp_server_ip"])}<input name="server" data-load-address="{esc(name, quote=True)}" required></label>'
                  f'<label>{esc(t["proxy_port"])}<input type="number" name="port" min="1" max="65535" '
                  f'data-load-port="{esc(name, quote=True)}" required></label>'
                  f'{server_token_field}'
                  f'<button type="submit">{esc(t["frp_save"])}</button>'
                  f'</form></details><dl class="frp-facts frp-server-facts"><div><dt>{esc(t["frp_server_ip"])}</dt>'
                  f'<dd>{reveal("server", masked_frpc_ip(config["serverAddr"]), t["frp_server_ip"])}</dd></div>'
                  f'<div><dt>{esc(t["proxy_port"])}</dt><dd>{reveal("port", "••••••", t["proxy_port"])}</dd></div>'
                  f'<div><dt>{esc(t["frps_token"])}</dt><dd>{reveal("token", "••••••", t["frps_token"])}</dd></div></dl></section>')
        proxy_fields = [('proxy_name', 'name', 'text'), ('proxy_type', 'type', 'text'),
                        ('frp_local_ip', 'localIP', 'text'), ('frp_local_port', 'localPort', 'number'),
                        ('frp_server_port', 'remotePort', 'number')]
        help_keys = {'localIP': 'frp_local_ip_help', 'localPort': 'frp_local_port_help',
                     'remotePort': 'frp_server_port_help'}
        def fields(proxy, suffix):
            result = []
            for label, key, kind in proxy_fields:
                if key == 'type':
                    current = proxy.get('type', 'tcp')
                    options = ''.join(f'<option value="{value}" {"selected" if current == value else ""}>{value.upper()}</option>'
                                      for value in ('tcp', 'udp'))
                    result.append(f'<label>{esc(t[label])}<select name="type">{options}</select></label>')
                else:
                    title = (hint(label, help_keys[key], f'{suffix}-{key}') if key in help_keys else
                             f'<label for="frp-{esc(suffix, quote=True)}-{key}">{esc(t[label])}</label>')
                    result.append(f'<div class="frp-field">{title}'
                                  f'<input id="frp-{esc(suffix, quote=True)}-{key}" name="{"proxyName" if key == "name" else key}" '
                                  f'type="{kind}" aria-label="{esc(t[label], quote=True)}" '
                                  f'value="{esc(str(proxy.get(key, "")), quote=True)}" required></div>')
            return ''.join(result)
        cards = []
        for index, proxy in enumerate(config.get('proxies', [])):
            cards.append(f'<section class="frp-proxy-card"><details class="node-inline-edit"><summary>'
                         f'<span>{esc(t["frp_edit_proxy"])}</span><span>{esc(t["node_cancel"])}</span></summary>'
                         f'<form method="post" action="/frp/client/structured">{base}'
                         f'<input type="hidden" name="section" value="edit"><input type="hidden" name="index" value="{index}">'
                         f'{fields(proxy, str(index))}<button type="submit">{esc(t["frp_save"])}</button></form></details>'
                         f'<div class="frp-proxy-facts"><strong>{esc(proxy["name"])}</strong>'
                         f'<dl class="frp-proxy-fields"><div><dt>{esc(t["proxy_type"])}</dt><dd>{esc(proxy["type"].upper())}</dd></div>'
                         f'<div><dt>{hint("frp_local_ip", "frp_local_ip_help", f"fact-{index}-ip")}</dt><dd><code>{esc(proxy["localIP"])}</code></dd></div>'
                         f'<div><dt>{hint("frp_local_port", "frp_local_port_help", f"fact-{index}-local-port")}</dt><dd>{proxy["localPort"]}</dd></div>'
                         f'<div><dt>{hint("frp_server_port", "frp_server_port_help", f"fact-{index}-server-port")}</dt><dd>{proxy["remotePort"]}</dd></div></dl></div>'
                         f'<form method="post" action="/frp/client/structured" class="frp-delete-form" data-confirm="{esc(t["frp_delete_confirm"], quote=True)}">{base}'
                         f'<input type="hidden" name="section" value="delete"><input type="hidden" name="index" value="{index}">'
                         f'<button type="submit" class="node-action">{esc(t["frp_delete_proxy"])}</button></form></section>')
        empty = f'<p class="muted">{esc(t["frp_no_proxies"])}</p>' if not cards else ''
        add = (f'<details class="node-inline-edit frp-add-proxy"><summary><span>{esc(t["frp_add_proxy"])}</span>'
               f'<span>{esc(t["node_cancel"])}</span></summary><form method="post" action="/frp/client/structured">{base}'
               f'<input type="hidden" name="section" value="add">{fields({}, "new")}'
               f'<button type="submit">{esc(t["frp_add_proxy"])}</button></form></details>')
        return server + f'<section class="frp-edit-section"><h2>{esc(t["frp_proxy_list_heading"])}</h2>{"".join(cards)}{empty}{add}</section>'

    def frpc_create_editor(self, lang):
        t, esc = STRINGS[lang], html.escape
        token_field = render_password_field(t, 'frpc-new-token', t['frps_token'], 'token',
                                            'maxlength="128" required autocomplete="new-password"')
        return (f'<section class="frp-edit-section"><h2>{esc(t["frp_server_settings"])}</h2>'
                f'<form method="post" action="/frp/client/structured" autocomplete="off">'
                f'<input type="hidden" name="section" value="create">'
                f'<input type="hidden" name="csrf" value="{access_csrf_token(self.get_cookie("session"), "frp:structured:new")}">'
                f'<label>{esc(t["frp_instance_name"])}<input name="name" pattern="[A-Za-z0-9_-]{{1,32}}" maxlength="32" required></label>'
                f'<label>{esc(t["frp_server_ip"])}<input name="server" required></label>'
                f'<label>{esc(t["proxy_port"])}<input type="number" name="port" min="1" max="65535" required></label>'
                f'{token_field}<button type="submit">{esc(t["frp_new_client"])}</button></form></section>')

    def frpc_address_value(self, parsed):
        name = parse_qs(parsed.query).get('name', [''])[0]
        try:
            if frpc_path(name).is_symlink():
                raise ValueError
            address = frpc_summary(name)['server']
            if not address:
                raise ValueError
        except (OSError, ValueError):
            return self.send_html(404, 'FRPC instance missing', {'Cache-Control': 'no-store'})
        body = json.dumps({'value': address}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def frpc_private_value(self, parsed):
        query = parse_qs(parsed.query)
        if set(query) != {'name', 'field'} or any(len(values) != 1 for values in query.values()):
            return self.send_html(400, 'Invalid request', {'Cache-Control': 'no-store'})
        name, field = query['name'][0], query['field'][0]
        if field not in ('server', 'port', 'token'):
            return self.send_html(400, 'Invalid request', {'Cache-Control': 'no-store'})
        try:
            if frpc_path(name).is_symlink():
                raise ValueError
            config = frpc_structured(name)
            if config is None:
                raise ValueError
            value = (config['serverAddr'] if field == 'server' else
                     str(config['serverPort']) if field == 'port' else config['auth']['token'])
        except (OSError, ValueError, KeyError, TypeError):
            return self.send_html(404, 'FRPC instance missing', {'Cache-Control': 'no-store'})
        body = json.dumps({'value': value}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()
        self.wfile.write(body)

    def handle_frpc_test(self):
        if self.headers.get('Content-Type', '').split(';', 1)[0].strip() != 'application/x-www-form-urlencoded':
            return self.send_html(400, 'Invalid request', {'Cache-Control': 'no-store'})
        try:
            length = int(self.headers.get('Content-Length', ''))
            if not 0 < length <= 1024:
                raise ValueError
            form = parse_qs(self.rfile.read(length).decode('utf-8'), strict_parsing=True)
            if set(form) != {'name', 'csrf'} or any(len(values) != 1 for values in form.values()):
                raise ValueError
            name = form['name'][0]
            path = frpc_path(name)
            if not path.is_file() or path.is_symlink():
                raise ValueError
        except (OSError, UnicodeError, ValueError):
            return self.send_html(400, 'Invalid request', {'Cache-Control': 'no-store'})
        expected = access_csrf_token(self.get_cookie('session'), 'frp:test:' + name)
        if not hmac.compare_digest(form['csrf'][0], expected):
            return self.send_html(403, 'Forbidden', {'Cache-Control': 'no-store'})
        connected = frpc_test_connection(name)
        if connected is None:
            return self.send_html(429, 'Connection test in progress', {'Cache-Control': 'no-store'})
        body = json.dumps({'connected': connected}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def handle_frp_edit(self, path, lang):
        if self.headers.get('Content-Type', '').split(';', 1)[0].strip() != 'application/x-www-form-urlencoded':
            return self.send_html(400, 'Invalid request', {'Cache-Control': 'no-store'})
        try:
            length = int(self.headers.get('Content-Length', ''))
            if not 0 < length <= 32768:
                raise ValueError
            form = parse_qs(self.rfile.read(length).decode('utf-8'), strict_parsing=True, keep_blank_values=True)
            structured = path.endswith('client/structured')
            section = form.get('section', [''])[0]
            required = ({'csrf', 'port', 'token'} if path.endswith('server/save') else
                        {'csrf', 'name', 'newName'} if path.endswith('client/rename') else
                        {'csrf', 'name'} if path.endswith('client/delete') else
                        {'csrf', 'name', 'section', 'server', 'port', 'token'} if structured and section in ('server', 'create') else
                        {'csrf', 'name', 'section', 'index'} if structured and section == 'delete' else
                        {'csrf', 'name', 'section', 'proxyName', 'type', 'localIP', 'localPort', 'remotePort'} if structured and section == 'add' else
                        {'csrf', 'name', 'section', 'index', 'type', 'localIP', 'localPort', 'remotePort', 'proxyName'} if structured and section == 'edit' else
                        {'csrf', 'action'} if path.endswith('server/toggle') else
                        {'csrf', 'name', 'action'})
            if set(form) != required or any(len(v) != 1 for v in form.values()):
                raise ValueError
            name = form.get('name', [''])[0]
            if path.endswith('server/save'):
                action = 'frp:server'
                node = frps_node()
                if node is None:
                    raise ValueError
                request = {'action': 'server', 'port': int(form['port'][0]) if form['port'][0] else node['port'],
                           'token': form['token'][0] or node['token']}
            elif path.endswith('client/rename'):
                if not frpc_path(name).is_file() or frpc_path(name).is_symlink():
                    raise ValueError
                new_name = form['newName'][0]
                frpc_path(new_name)
                action = 'frp:rename:' + name
                request = {'action': 'rename-client', 'name': name, 'new_name': new_name}
            elif path.endswith('client/delete'):
                if not frpc_path(name).is_file() or frpc_path(name).is_symlink():
                    raise ValueError
                action = 'frp:delete:' + name
                request = {'action': 'delete-client', 'name': name}
            elif structured:
                if section not in ('server', 'add', 'edit', 'delete', 'create') or (section != 'create' and not frpc_path(name).is_file()):
                    raise ValueError
                action = 'frp:structured:' + (name if section != 'create' else 'new')
                values = {'index': int(form['index'][0])} if section in ('edit', 'delete') else {}
                if section in ('server', 'create'):
                    values.update(server=form['server'][0], port=int(form['port'][0]), token=form['token'][0])
                elif section != 'delete':
                    values['proxy'] = {'name': form['proxyName'][0], 'type': form['type'][0],
                                       'localIP': form['localIP'][0], 'localPort': int(form['localPort'][0]),
                                       'remotePort': int(form['remotePort'][0])}
                request = {'action': 'create-structured-client' if section == 'create' else 'structured-client',
                           'name': name, 'section': section, 'values': values}
            elif path.endswith('server/toggle'):
                state = form['action'][0]
                if state not in ('enable', 'disable') or frps_node() is None:
                    raise ValueError
                action = 'frp:server:' + state
                request = {'action': 'server-' + state}
            else:
                state = form['action'][0]
                if state not in ('enable', 'disable') or not frpc_path(name).is_file() or frpc_path(name).is_symlink():
                    raise ValueError
                action = 'frp:toggle:' + name + ':' + state
                request = {'action': state, 'name': name}
        except (UnicodeError, ValueError, OSError):
            return self.send_html(400, 'Invalid request', {'Cache-Control': 'no-store'})
        if not hmac.compare_digest(form['csrf'][0], access_csrf_token(self.get_cookie('session'), action)):
            return self.send_html(403, 'Forbidden', {'Cache-Control': 'no-store'})
        if not FRP_CONTROL_HELPER.is_file():
            return self.send_html(503, 'FRP helper unavailable', {'Cache-Control': 'no-store'})
        direct = ['/usr/bin/python3', str(FRP_CONTROL_HELPER)]
        systemd_run = shutil.which('systemd-run')
        if not systemd_run and Path('/run/systemd/system').exists():
            return self.send_html(503, 'FRP helper unavailable', {'Cache-Control': 'no-store'})
        command = (['systemd-run', '--pipe', '--wait', '--collect', '--unit=vps-server-frp-control.service', *direct]
                   if systemd_run else direct)
        try:
            result = subprocess.run(command, input=json.dumps(request).encode(),
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=180, check=False)
        except subprocess.TimeoutExpired:
            if systemd_run:
                _run_quiet(['systemctl', 'stop', 'vps-server-frp-control.service'])
            result = None
        except OSError:
            result = None
        if path.endswith('client/rename') and result and result.returncode == 0:
            name = new_name
        target = ('/frp/client/edit?name=' + quote(name) if path in ('/frp/client/structured', '/frp/client/toggle', '/frp/client/rename') else
                  '/frps' if path.startswith('/frp/server/') else '/frpc')
        return self.redirect(target + ('&' if '?' in target else '?') + 'msg=' +
                             ('done' if result and result.returncode == 0 else 'failed'),
                             {'Cache-Control': 'no-store'})

    def page_proxy(self, lang, query_lang):
        """Show all installed proxy protocols in a single operator view."""
        t = STRINGS[lang]
        anytls = anytls_node()
        nodes = proxy_nodes()
        try:
            inventory = read_inventory(state_path=NODE_STATE_PATH,
                                       config_paths={"anytls": ANYTLS_CONFIG,
                                                     "proxy": PROXY_CONFIG})
            managed = {node["protocol"]: node for node in inventory["nodes"]} if inventory else {}
            meter = _read_json(NODE_METER_PATH) or {}
            meter_nodes = meter.get("ledger", {}).get("nodes", {})
            if inventory is not None:
                return self.page_managed_nodes(lang, query_lang, inventory, meter_nodes)
        except (OSError, ValueError, TypeError, AttributeError):
            managed, meter_nodes = {}, {}
        legacy_controls = not NODE_STATE_PATH.exists()
        if anytls is None and not nodes:
            body = f"""
            <div class="card">
              <h1>{html.escape(t['proxy_heading'])}</h1>
              <p class="muted">{html.escape(t['proxy_not_installed'])}</p>
            </div>
            """
            return self.send_html(
                200, self.render_page(t['proxy_heading'], body, lang, active="proxy"),
                {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"},
            )

        host = (self.headers.get("Host") or "").split(":")[0] or "<server-ip>"
        lan_host = clash_lan_host(host) if AUTH_ENABLED else None

        notice = ""
        key = parse_qs(urlsplit(self.path).query).get("msg", [""])[0]
        if key in ANYTLS_MESSAGE_KEYS:
            cls = "notice" if key == "anytls_reset_done" else "error"
            notice = (f'<p class="{cls}">'
                      f'{html.escape(t[key].format(service=ANYTLS_SERVICE))}</p>')
        elif key in NODE_APPLY_MESSAGE_KEYS:
            cls = "notice" if key in ("node_apply_done", "node_settings_done", "node_reset_done") else "error"
            notice = f'<p class="{cls}">{html.escape(t[key])}</p>'
        elif key in PROXY_MESSAGE_KEYS:
            cls = "notice" if key == "proxy_reset_done" else "error"
            notice = (f'<p class="{cls}">'
                      f'{html.escape(t[key].format(service=PROXY_SERVICE))}</p>')

        sections = []

        if anytls is not None:
            if anytls["running"]:
                state = t["anytls_state_running"].format(port='••••••')
                state_class = "is-open"
            else:
                state = t["anytls_state_stopped"].format(
                    port='••••••', service=ANYTLS_SERVICE
                )
                state_class = "is-closed"
            health = ("" if anytls["running"] else
                      f'<p class="proxy-node-health warn">{html.escape(state)}</p>')
            entries = address_entries(t)
            blocks = []
            for label, address in entries:
                blocks.append(f"""
                <div class="node-address"><span>{html.escape(label)}</span>
                  <code>{html.escape(address)}</code></div>
                """)
            sections.append(f"""
            <article class="proxy-node">
              <header class="proxy-node-header">
                <div><span class="proxy-node-protocol">anytls</span><h2>{html.escape(managed['anytls']['name'] if 'anytls' in managed else 'anytls')}</h2></div>
                <span class="proxy-node-status {state_class}">{html.escape(t['node_active'] if anytls['running'] else t['node_stopped'])}</span>
              </header>
              {health}
              <dl class="kv proxy-node-facts">
                <dt>{html.escape(t['anytls_port'])}</dt>
                <dd>{self.private_value_control('legacy-anytls', 'port', t)}</dd>
                <dt>{html.escape(t['anytls_password'])}</dt>
                <dd class="secret">{self.private_value_control('legacy-anytls', 'credential', t, copy=True)}</dd>
                <dt>{html.escape(t['anytls_sni'])}</dt>
                <dd>{html.escape(anytls['sni'] or '—')}</dd>
              </dl>
              <div class="proxy-node-addresses">{"".join(blocks)}</div>
              {self.node_metrics(managed.get('anytls'), meter_nodes, t)}
              {self.node_clash_share(managed.get('anytls'), lan_host, t)}
              <details class="proxy-node-settings">
                <summary>{html.escape(t['node_manage'])}</summary>
                {self.node_settings_form('anytls', anytls['port'], anytls['sni'], managed.get('anytls'), t)}
                {self.node_credential_form('anytls', t['anytls_password'], t) if legacy_controls else ''}
                {f'''
                <form method="post" action="/anytls/reset" class="proxy-node-reset">
                  <label class="checkline">
                    <input type="checkbox" name="confirm" value="yes" required>
                    <span>{html.escape(t['anytls_reset_confirm'])}</span>
                  </label>
                  <button type="submit" class="danger">{html.escape(t['anytls_reset'])}</button>
                </form>
                ''' if legacy_controls else ''}
              </details>
            </article>
            """)

        if nodes:
            proxy_entries = address_entries(t)
            if proxy_running():
                proxy_state = t["proxy_state_running"]
                proxy_state_class = "is-open"
            else:
                proxy_state = t["proxy_state_stopped"].format(service=PROXY_SERVICE)
                proxy_state_class = "is-closed"
            proxy_health = ("" if proxy_state_class == "is-open" else
                            f'<p class="proxy-node-health warn">{html.escape(proxy_state)}</p>')
            for node in nodes:
                proto = node["type"]
                secret_label = (
                    t["proxy_uuid"] if proto in ("vmess", "vless") else t["proxy_password"]
                )
                sni_row = ""
                if proto != "shadowsocks":
                    sni_row = f"""
                    <dt>{html.escape(t['proxy_sni'])}</dt>
                    <dd>{html.escape(node['sni'] or '—')}</dd>
                    """
                blocks = []
                for label, address in proxy_entries:
                    blocks.append(f"""
                    <div class="node-address"><span>{html.escape(label)}</span>
                      <code>{html.escape(address)}</code></div>
                    """)
                sections.append(f"""
                <article class="proxy-node">
                  <header class="proxy-node-header">
                    <div><span class="proxy-node-protocol">{html.escape(proto)}</span>
                      <h2>{html.escape(managed[proto]['name'] if proto in managed else proto)}</h2></div>
                    <span class="proxy-node-status {proxy_state_class}">{html.escape(t['node_active'] if proxy_state_class == 'is-open' else t['node_stopped'])}</span>
                  </header>
                  {proxy_health}
                  <dl class="kv proxy-node-facts">
                    <dt>{html.escape(t['proxy_port'])}</dt>
                    <dd>{self.private_value_control('legacy-' + proto, 'port', t)}</dd>
                    <dt>{html.escape(secret_label)}</dt>
                    <dd class="secret">{self.private_value_control('legacy-' + proto, 'credential', t, copy=True)}</dd>
                    {sni_row}
                  </dl>
                  <div class="proxy-node-addresses">{"".join(blocks)}</div>
                  {self.node_metrics(managed.get(proto), meter_nodes, t)}
                  {self.node_clash_share(managed.get(proto), lan_host, t)}
                  <details class="proxy-node-settings">
                    <summary>{html.escape(t['node_manage'])}</summary>
                    {self.node_settings_form(proto, node['port'], node['sni'], managed.get(proto), t)}
                    {self.node_credential_form(proto, secret_label, t) if legacy_controls else ''}
                    {f'''
                    <form method="post" action="/proxy/reset" class="proxy-node-reset">
                      <input type="hidden" name="protocol" value="{html.escape(proto)}">
                      <label class="checkline">
                        <input type="checkbox" name="confirm" value="yes" required>
                        <span>{html.escape(t['anytls_reset_confirm'])}</span>
                      </label>
                      <button type="submit" class="danger">{html.escape(t['proxy_reset'])}</button>
                    </form>
                    ''' if legacy_controls else ''}
                  </details>
                </article>
                """)

        running_count = int(bool(anytls and anytls['running'])) + (len(nodes) if nodes and proxy_running() else 0)
        body = f"""
        <div class="proxy-workspace">
          <header class="proxy-overview">
            <div><p class="proxy-eyebrow">{html.escape(t['node_overview'])}</p>
              <h1>{html.escape(t['proxy_heading'])}</h1>
              </div>
            <div class="proxy-summary" aria-label="{html.escape(t['node_summary'])}">
              <div><strong>{len(sections)}</strong><span>{html.escape(t['node_total'])}</span></div>
              <div><strong>{running_count}</strong><span>{html.escape(t['node_active'])}</span></div>
            </div>
          </header>
          {notice}
          <div class="proxy-node-grid">{"".join(sections)}</div>
        </div>
        <script src="/static/copy.js"></script>
        <script src="/static/private-values.js"></script>
        {'''<script src="/static/qrcode.js"></script>
        <script src="/static/qrcode-utf8.js"></script>
        <script src="/static/qrcode-render.js"></script>''' if lan_host and managed else ''}
        """
        self.send_html(200, self.render_page(t['proxy_heading'], body, lang, active="proxy"),
                       {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def page_managed_nodes(self, lang, query_lang, inventory, meter_nodes):
        """Render each installed inbound by stable ID, including duplicates."""
        t = STRINGS[lang]
        esc = html.escape
        session = self.get_cookie("session")
        host = (self.headers.get("Host") or "").split(":")[0]
        lan_host = clash_lan_host(host) if AUTH_ENABLED else None
        key = parse_qs(urlsplit(self.path).query).get("msg", [""])[0]
        notice = (f'<p class="{"error" if key == "node_settings_failed" else "notice"}">'
                  f'{esc(t[key])}</p>') if key in NODE_APPLY_MESSAGE_KEYS else ""
        cards = []
        running = {"anytls": bool(anytls_node() and anytls_node()["running"]),
                   "proxy": proxy_running()}
        addresses_available = address_entries(t)
        for node in sorted(inventory["nodes"], key=lambda item: item["number"]):
            protocol = node["protocol"]
            module = "anytls" if protocol == "anytls" else "proxy"
            identifier = node["id"]
            token = node_csrf_token(session, identifier)
            inbound = node["inbound"]
            sni = _cert_common_name(inbound["tls"]["certificate_path"]) if protocol != "shadowsocks" else ""
            sni_fact = (f'<div class="node-fact"><dt>{esc(t["proxy_sni"])}</dt><dd>{esc(sni or "—")}</dd></div>'
                        if protocol != "shadowsocks" else
                        f'<div class="node-fact"><dt>{esc(t["proxy_sni"])}</dt><dd>{esc(t["node_not_applicable"])}</dd></div>')
            sni_input = (f'<label>{esc(t["proxy_sni"])}<input name="sni" value="{esc(sni, quote=True)}" required></label>'
                         if protocol != "shadowsocks" else "")
            addresses = "".join(f'<div class="node-address"><span>{esc(label)}</span><code>{esc(value)}</code></div>'
                                for label, value in addresses_available)
            cap = "" if node["cap_bytes"] is None else str(Decimal(node["cap_bytes"]) / 1073741824)
            upload_speed = "" if node["upload_limit_bps"] is None else str(Decimal(node["upload_limit_bps"]) / 1000000)
            download_speed = "" if node["download_limit_bps"] is None else str(Decimal(node["download_limit_bps"]) / 1000000)
            interval = reset_interval(node["reset_mode"])
            reset_choice = "none" if node["reset_mode"] == "none" else "once" if node["reset_mode"] == "once" else "repeat"
            reset_count, reset_unit = (interval[0], interval[1]) if interval else (1, "months")
            next_reset = node["next_reset_at"][:16] if node["reset_mode"] == "once" and node["next_reset_at"] else ""
            def radios(name, options, selected):
                return "".join(f'<label class="node-radio"><input type="radio" name="{name}" value="{value}"'
                               f'{" checked" if value == selected else ""}><span>{esc(t[key])}</span></label>'
                               for value, key in options)
            units = (("days", "node_days"), ("months", "node_months"), ("years", "node_years"))
            reset_modes = (("none", "node_reset_none"), ("repeat", "node_reset_repeat")) + \
                          ((("once", "node_reset_once"),) if reset_choice == "once" else ())
            is_active = node["enabled"] and running[module]
            status_key = "node_disabled" if not node["enabled"] else ("node_active" if is_active else "node_stopped")
            status_class = "is-open" if is_active else "is-closed"
            toggle_label = t["node_disable"] if node["enabled"] else t["node_enable"]
            cards.append(f'''
            <article class="proxy-node managed-node">
              <header class="proxy-node-header"><div><span class="proxy-node-protocol">#{node['number']} · {esc(protocol)}</span>
                <h2>{esc(node['name'])}</h2></div>
                <div class="node-header-controls"><span class="proxy-node-status {status_class}">{esc(t[status_key])}</span>
                  <form method="post" action="/proxy/node/toggle" class="node-toggle-form">
                    <input type="hidden" name="id" value="{identifier}"><input type="hidden" name="csrf" value="{token}">
                    <input type="hidden" name="enabled" value="{'no' if node['enabled'] else 'yes'}">
                    <button type="submit" role="switch" aria-checked="{'true' if node['enabled'] else 'false'}" aria-label="{esc(toggle_label, quote=True)}" title="{esc(toggle_label, quote=True)}" class="node-toggle" ><span aria-hidden="true"></span></button>
                  </form></div></header>
              <section class="node-connection"><details class="node-inline-edit" data-node-edit-id="{identifier}"><summary><span>{esc(t['node_manage'])}</span><span>{esc(t['node_cancel'])}</span></summary>
                <form method="post" action="/proxy/node/edit" autocomplete="off" class="node-inline-form">
                  <input type="hidden" name="id" value="{identifier}"><input type="hidden" name="csrf" value="{token}">
                  <div class="node-form-grid">
                    <label>{esc(t['node_name'])}<input name="name" maxlength="64" value="{esc(node['name'], quote=True)}" required></label>
                    <label>{esc(t['proxy_port'])}<input type="number" name="port" min="1" max="65535" data-node-edit-port placeholder="{esc(t['node_keep_port'], quote=True)}"></label>
                    <div class="node-form-field">{render_password_field(t, 'node-credential-' + identifier, t['node_credential'], 'credential', 'value="" data-node-edit-credential placeholder="' + esc(t['node_keep_credential'], quote=True) + '" autocomplete="new-password"')}</div>
                    {sni_input}
                  </div><button type="submit">{esc(t['node_save_settings'])}</button>
                </form>
              </details>
              <dl class="proxy-node-facts">
                <div class="node-fact"><dt>{esc(t['proxy_port'])}</dt><dd>{self.private_value_control(identifier, 'port', t)}</dd></div>
                {sni_fact}
                <div class="node-fact node-fact-secret"><dt>{esc(t['node_credential'])}</dt><dd class="secret">{self.private_value_control(identifier, 'credential', t, copy=True)}</dd></div>
              </dl></section>
              <div class="proxy-node-addresses">{addresses}</div>
              {self.node_metrics(node, meter_nodes, t)}
              {self.node_clash_share(node, lan_host, t)}
              <div class="node-secondary">
                <button type="button" class="node-action node-access-open" data-dialog-open="node-access-{identifier}">{esc(t['node_limit_manage'])}</button>
                <div class="node-destructive-actions"><button type="button" class="node-action node-action-danger" data-dialog-open="node-reset-{identifier}">{esc(t['node_random_reset'])}</button>
                <button type="button" class="node-action node-action-danger" data-dialog-open="node-delete-{identifier}">{esc(t['node_delete'])}</button></div>
              </div>
              <dialog class="node-access-dialog" id="node-access-{identifier}" aria-labelledby="node-access-title-{identifier}">
                  <form method="post" action="/proxy/node/limits">
                    <input type="hidden" name="id" value="{identifier}"><input type="hidden" name="csrf" value="{token}">
                    <h3 id="node-access-title-{identifier}">{esc(t['node_limit_manage'])}</h3>
                    <div class="node-form-grid">
                      <label>{esc(t['node_cap_gib'])}<input type="number" name="cap_gib" min="0.000001" max="100000000" step="any" value="{cap}" placeholder="{esc(t['node_unlimited'], quote=True)}"></label>
                      <label>{esc(t['node_upload_speed'])}<input type="number" name="upload_mbps" min="0.001" max="10000000" step="any" value="{upload_speed}" placeholder="{esc(t['node_unlimited'], quote=True)}"></label>
                      <label>{esc(t['node_download_speed'])}<input type="number" name="download_mbps" min="0.001" max="10000000" step="any" value="{download_speed}" placeholder="{esc(t['node_unlimited'], quote=True)}"></label>
                    </div>
                    <fieldset class="node-reset-cycle"><legend>{esc(t['node_cap_action'])}</legend>{radios('cap_action', (("throttle", "node_cap_slow"), ("block", "node_cap_block")), node['cap_action'])}</fieldset>
                    <fieldset class="node-reset-cycle"><legend>{esc(t['node_reset_schedule'])}</legend>{radios('reset_mode', reset_modes, reset_choice)}</fieldset>
                    <div class="node-duration"><label>{esc(t['node_reset_every'])}<input type="number" name="reset_count" min="1" max="9999" value="{reset_count}"></label>
                      <fieldset class="node-reset-cycle"><legend>{esc(t['node_reset_unit'])}</legend>{radios('reset_unit', units, reset_unit)}</fieldset></div>
                    {'<label>' + esc(t['node_reset_time_utc']) + '<input type="datetime-local" name="next_reset_at" value="' + next_reset + '"></label>' if reset_choice == 'once' else '<input type="hidden" name="next_reset_at" value="">'}
                    <fieldset class="node-reset-cycle"><legend>{esc(t['node_validity'])}</legend>{radios('expiry_mode', (("none", "node_validity_none"), ("set", "node_validity_set")), 'set' if node['expiry_count'] else 'none')}</fieldset>
                    <div class="node-duration"><label>{esc(t['node_validity_length'])}<input type="number" name="expiry_count" min="1" max="9999" value="{node['expiry_count'] or 1}"></label>
                      <fieldset class="node-reset-cycle"><legend>{esc(t['node_validity_unit'])}</legend>{radios('expiry_unit', units, node['expiry_unit'] or 'months')}</fieldset></div>
                    <div class="node-dialog-actions"><button type="button" class="node-dialog-cancel" data-dialog-close>{esc(t['node_cancel'])}</button>
                    <button type="submit">{esc(t['node_save_limits'])}</button></div>
                  </form>
              </dialog>
              <dialog class="node-confirm-dialog" id="node-reset-{identifier}" aria-labelledby="node-reset-title-{identifier}">
                <form method="post" action="/proxy/node/reset">
                  <input type="hidden" name="id" value="{identifier}"><input type="hidden" name="csrf" value="{token}"><input type="hidden" name="confirm" value="yes">
                  <h3 id="node-reset-title-{identifier}">{esc(t['node_random_reset'])}</h3>
                  <p>{esc(t['node_random_confirm'])}</p>
                  <div class="node-dialog-actions"><button type="button" class="node-dialog-cancel" data-dialog-close>{esc(t['node_cancel'])}</button><button type="submit" class="danger">{esc(t['node_random_reset'])}</button></div>
                </form>
              </dialog>
              <dialog class="node-confirm-dialog" id="node-delete-{identifier}" aria-labelledby="node-delete-title-{identifier}">
                <form method="post" action="/proxy/node/delete">
                  <input type="hidden" name="id" value="{identifier}"><input type="hidden" name="csrf" value="{token}"><input type="hidden" name="confirm" value="yes">
                  <h3 id="node-delete-title-{identifier}">{esc(t['node_delete'])}</h3>
                  <p>{esc(t['node_delete_confirm'])}</p>
                  <div class="node-dialog-actions"><button type="button" class="node-dialog-cancel" data-dialog-close>{esc(t['node_cancel'])}</button><button type="submit" class="danger">{esc(t['node_delete'])}</button></div>
                </form>
              </dialog>
            </article>''')
        protocols = (["anytls"] if ANYTLS_CONFIG.is_file() else []) + \
                    (["vmess", "vless", "trojan", "shadowsocks"] if PROXY_CONFIG.is_file() else [])
        protocol_choices = "".join(f'<label class="node-radio"><input type="radio" name="protocol" value="{value}"'
                                   f'{" checked" if index == 0 else ""}><span>{esc(value)}</span></label>'
                                   for index, value in enumerate(protocols))
        create = (f'''<details class="node-create"><summary><span>{esc(t['node_create'])}</span><span>{esc(t['node_cancel'])}</span></summary>
          <form method="post" action="/proxy/node/create" data-node-create
                data-credential-password="{esc(t['node_credential_password_hint'], quote=True)}"
                data-credential-uuid="{esc(t['node_credential_uuid_hint'], quote=True)}"
                data-credential-ss="{esc(t['node_credential_ss_hint'], quote=True)}">
            <input type="hidden" name="csrf" value="{node_csrf_token(session, 'create')}">
            <fieldset class="node-reset-cycle"><legend>{esc(t['node_protocol'])}</legend>{protocol_choices}</fieldset>
            <div class="node-form-grid">
              <label>{esc(t['node_name'])}<input name="name" maxlength="64" required></label>
              <label>{esc(t['proxy_port'])}<input type="number" name="port" min="1" max="65535" placeholder="{esc(t['node_random_port'], quote=True)}"></label>
              <div class="node-form-field">{render_password_field(t, 'node-create-credential', t['node_credential'], 'credential', 'value="" placeholder="' + esc(t['node_credential_random'], quote=True) + '" autocomplete="new-password"', '<small class="node-field-hint" data-credential-hint>' + esc(t['node_credential_password_hint']) + '</small>')}</div>
              <label data-sni-field>{esc(t['proxy_sni'])}<input name="sni" value="www.bing.com" placeholder="{esc(t['node_sni_optional'], quote=True)}"></label>
            </div><button type="submit">{esc(t['node_create'])}</button>
          </form></details>''' if protocols else "")
        count = len(cards)
        active_count = sum(bool(n["enabled"] and running["anytls" if n["protocol"] == "anytls" else "proxy"])
                           for n in inventory["nodes"])
        qr_scripts = ('<script src="/static/qrcode.js"></script><script src="/static/qrcode-utf8.js"></script>'
                      '<script src="/static/qrcode-render.js"></script>') if lan_host and cards else ''
        empty_state = ''.join(cards) if cards else f'<p class="muted">{esc(t["node_empty"])}</p>'
        body = f'''<div class="proxy-workspace"><header class="proxy-overview">
          <div><p class="proxy-eyebrow">{esc(t['node_overview'])}</p><h1>{esc(t['proxy_heading'])}</h1></div>
          <div class="proxy-summary" aria-label="{esc(t['node_summary'])}">
            <div><strong>{count}</strong><span>{esc(t['node_total'])}</span></div>
            <div><strong>{active_count}</strong><span>{esc(t['node_active'])}</span></div></div></header>
          {notice}{create}<div class="proxy-node-grid managed-node-grid">{empty_state}</div></div>
          <script src="/static/copy.js"></script>
          <script src="/static/private-values.js"></script>
          <script src="/static/node-controls.js"></script>
          {qr_scripts}'''
        return self.send_html(200, self.render_page(t['proxy_heading'], body, lang, active="proxy"),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def private_value_control(self, identifier, field, t, copy=False):
        esc = html.escape
        return (f'<span class="private-value" data-private-id="{esc(identifier, quote=True)}" '
                f'data-private-field="{field}" data-show="{esc(t["login_show_password"], quote=True)}" '
                f'data-hide="{esc(t["login_hide_password"], quote=True)}" '
                f'data-error="{esc(t["private_value_failed"], quote=True)}">'
                f'<code data-private-text>••••••</code>'
                f'<button type="button" class="private-reveal" aria-pressed="false">{esc(t["login_show_password"])}</button>'
                + (f'<button type="button" class="private-copy" data-copied="{esc(t["copied"], quote=True)}" data-error="{esc(t["private_copy_failed"], quote=True)}">{esc(t["copy"])}</button>' if copy else '')
                + '</span>')

    def node_clash_share(self, node, lan_host, t):
        if node is None or lan_host is None:
            return ""
        return f'''<div class="node-share" data-share-id="{html.escape(node['id'], quote=True)}">
          <button type="button" class="private-share-copy" data-copied="{html.escape(t['copied'], quote=True)}" data-error="{html.escape(t['private_copy_failed'], quote=True)}"
            aria-label="{html.escape(t['node_clash_copy_label'], quote=True)}">{html.escape(t['copy'])}</button>
          <button type="button" class="node-import private-share-import" data-error="{html.escape(t['private_value_failed'], quote=True)}">{html.escape(t['node_clash_import'])}</button>
          <details class="qr-details"><summary>{html.escape(t['node_clash_qr'])}</summary>
            <div class="qr" data-private-qr data-error="{html.escape(t['private_value_failed'], quote=True)}"></div>
          </details>
        </div>'''

    def handle_proxy_private_value(self, parsed):
        query = parse_qs(parsed.query)
        identifier = query.get('id', [''])[0]
        field = query.get('field', [''])[0]
        if len(query.get('id', [])) != 1 or len(query.get('field', [])) != 1 or field not in ('port', 'credential', 'share', 'cmd-default', 'cmd-reverse', 'cmd-udp', 'public-port', 'target-port', 'account'):
            return self.send_html(400, 'Invalid request', {'Cache-Control': 'no-store'})
        try:
            if identifier == 'lucky' and field in ('port', 'account', 'credential'):
                data = lucky_admin()
                if data is None:
                    raise ValueError('no Lucky admin')
                value = str(data['AdminWebListenPort'] if field == 'port' else
                            data.get('AdminAccount', '') if field == 'account' else
                            data.get('AdminPassword', ''))
            elif identifier == 'iperf' and field in ('port', 'cmd-default', 'cmd-reverse', 'cmd-udp'):
                host = (self.headers.get('Host') or '').split(':')[0] or '<server-ip>'
                suffix = {'cmd-default': '', 'cmd-reverse': ' -R', 'cmd-udp': ' -u -b 100M'}
                value = (str(IPERF_WINDOW.port) if field == 'port' else
                         f'iperf3 -c {host} -p {IPERF_WINDOW.port}{suffix[field]} --json')
            elif identifier.startswith('forward-') and field in ('public-port', 'target-port'):
                rule = next(item for item in PORTFWD.list_rules() if item['id'] == identifier[8:])
                value = str(rule['public_port' if field == 'public-port' else 'target_port'])
            elif identifier == 'frps' and field in ('port', 'credential'):
                node = frps_node()
                if node is None:
                    raise ValueError('no frps node')
                value = str(node['port'] if field == 'port' else node['token'])
            elif identifier.startswith('legacy-') and field in ('port', 'credential'):
                protocol = identifier.removeprefix('legacy-')
                node = (anytls_node() if protocol == 'anytls' else
                        next(item for item in proxy_nodes() if item['type'] == protocol))
                if node is None:
                    raise ValueError('no legacy node')
                value = str(node['port'] if field == 'port' else
                            node['password'] if protocol == 'anytls' else node['secret'])
            else:
                value = self.managed_private_value(identifier, field)
        except (OSError, ValueError, TypeError, KeyError, StopIteration):
            return self.send_html(404, 'Not found', {'Cache-Control': 'no-store'})
        data = json.dumps({'value': value}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def managed_private_value(self, identifier, field):
        try:
            inventory = read_inventory(state_path=NODE_STATE_PATH,
                                       config_paths={'anytls': ANYTLS_CONFIG, 'proxy': PROXY_CONFIG})
            node = next(item for item in inventory['nodes'] if item['id'] == identifier)
            if field == 'port':
                value = str(node['port'])
            elif field == 'credential':
                inbound = node['inbound']
                protocol = node['protocol']
                value = (inbound['password'] if protocol == 'shadowsocks' else
                         inbound['users'][0]['uuid' if protocol in ('vmess', 'vless') else 'password'])
            elif field == 'share':
                host = clash_lan_host((self.headers.get('Host') or '').split(':')[0])
                if host is None:
                    raise ValueError('no LAN address')
                scheme = 'https' if CONSOLE_TLS else 'http'
                value = (f'{scheme}://{host}:{CONSOLE_PORT}/clash/sub/'
                         f'{identifier}/{clash_share_token(node)}')
            else:
                raise ValueError('unsupported node value')
            return value
        except (OSError, ValueError, TypeError, KeyError, StopIteration):
            raise ValueError('no managed node')

    def handle_clash_subscription(self, path):
        parts = path.split("/")
        peer = ipaddress.ip_address(self.client_address[0])
        if (not AUTH_ENABLED or len(parts) != 5 or parts[:3] != ["", "clash", "sub"] or
                not re.fullmatch(r"[0-9a-f]{64}", parts[4]) or
                not (is_lan_address(str(peer)) or peer.is_loopback)):
            return self.send_html(404, "Not found", {"Cache-Control": "no-store"})
        try:
            inventory = read_inventory(state_path=NODE_STATE_PATH,
                                       config_paths={"anytls": ANYTLS_CONFIG,
                                                     "proxy": PROXY_CONFIG})
            matches = [node for node in inventory["nodes"] if node["id"] == parts[3]]
            if not matches and parts[3] in NODE_PROTOCOLS:
                # Previously issued links named the protocol. Preserve the
                # oldest matching node until its token changes or it is removed.
                matches = sorted((node for node in inventory["nodes"]
                                  if node["protocol"] == parts[3]), key=lambda node: node["number"])
            node = matches[0]
            if not hmac.compare_digest(parts[4], clash_share_token(node)):
                raise ValueError("stale link")
            host = clash_lan_host("")
            if host is None:
                raise ValueError("no LAN address")
            data = clash_profile(node, host).encode("utf-8")
        except (OSError, ValueError, TypeError, KeyError, StopIteration, IndexError):
            return self.send_html(404, "Not found", {"Cache-Control": "no-store"})
        self.send_response(200)
        self.send_header("Content-Type", "text/yaml; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def node_metrics(self, node, meter_nodes, t):
        if node is None:
            return ""
        def size(value):
            return f"{value / 1048576:.1f} MiB"
        used = node["upload_bytes"] + node["download_bytes"]
        cap = node["cap_bytes"]
        try:
            suspect = bool(meter_nodes[node["id"]]["suspect"])
        except (KeyError, TypeError):
            suspect = True
        remaining = ((datetime.fromisoformat(node["expires_at"]) - datetime.now(timezone.utc)).total_seconds()
                     if node["expires_at"] else None)
        expired = remaining is not None and remaining <= 0
        capped = cap is not None and used >= cap
        blocked = expired or (capped and node["cap_action"] == "block")
        limited = suspect or (capped and not blocked)
        limit = t["node_blocked"] if blocked else t["node_limited"] if limited else t["node_normal"]
        cap_label = f"{cap / 1073741824:g} GiB" if cap is not None else t["node_unlimited"]
        reset_label = node["next_reset_at"][:16].replace("T", " ") + " UTC" if node["next_reset_at"] else t["node_no_reset"]
        speed = lambda direction: (f'{node[direction + "_limit_bps"] / 1000000:g} Mbps' if node[direction + "_limit_bps"] is not None else t["node_unlimited"])
        validity_label = (t["node_validity_expired"] if expired else
                          t["node_remaining_hours"].format(count=max(1, int((remaining + 3599) // 3600)))
                          if remaining < 86400 else
                          t["node_remaining_days"].format(count=max(1, int((remaining + 86399) // 86400)))) if remaining is not None else ""
        validity = (f'<div class="node-validity-stat"><small>{html.escape(t["node_validity"])}</small>'
                    f'<strong>{html.escape(validity_label)}</strong></div>' if remaining is not None else "")
        return f'''<section class="node-usage" aria-label="{html.escape(t['node_traffic'])}">
          <div class="node-usage-heading"><h3>{html.escape(t['node_traffic'])}</h3>
            <span class="node-limit {'is-limited' if limited or blocked else ''}">{html.escape(limit)}</span></div>
          <div class="node-stats">
            <div><small>{html.escape(t['node_upload'])}</small><strong>{size(node['upload_bytes'])}</strong><small>{html.escape(speed('upload'))}</small></div>
            <div><small>{html.escape(t['node_download'])}</small><strong>{size(node['download_bytes'])}</strong><small>{html.escape(speed('download'))}</small></div>
            <div><small>{html.escape(t['node_cap'])}</small><strong>{html.escape(cap_label)}</strong></div>
            <div><small>{html.escape(t['node_next_reset'])}</small><strong>{html.escape(reset_label)}</strong></div>
            {validity}
          </div>
        </section>'''

    def node_settings_form(self, protocol, port, sni, node, t):
        if node is None:
            return ""
        token = node_csrf_token(self.get_cookie("session"), protocol)
        cap = "" if node["cap_bytes"] is None else str(Decimal(node["cap_bytes"]) / 1073741824)
        expiry = node["expires_at"][:16] if node["expires_at"] else ""
        next_reset = node["next_reset_at"][:16] if node["reset_mode"] == "once" and node["next_reset_at"] else ""
        options = "".join(f'<option value="{mode}"{" selected" if mode == node["reset_mode"] else ""}>{html.escape(t[key])}</option>'
                          for mode, key in (("none", "node_reset_none"), ("monthly", "node_reset_monthly"), ("once", "node_reset_once")))
        sni_field = (f'<label>{html.escape(t["proxy_sni"])}<input name="sni" value="{html.escape(sni, quote=True)}" required></label>'
                     if protocol != "shadowsocks" else
                     f'<p class="muted">{html.escape(t["proxy_sni"])}: {html.escape(t["node_not_applicable"])}</p>')
        return f'''<form method="post" action="/proxy/node/edit" autocomplete="off" class="node-settings-form">
          <input type="hidden" name="protocol" value="{html.escape(protocol)}">
          <input type="hidden" name="csrf" value="{token}">
          <div class="node-form-grid">
            <label>{html.escape(t['node_name'])}<input name="name" maxlength="64" value="{html.escape(node['name'], quote=True)}" required></label>
            <label>{html.escape(t['proxy_port'])}<input type="number" name="port" min="1" max="65535" value="{port}" required></label>
            <div class="node-form-field">{render_password_field(t, 'legacy-credential-' + protocol, t['node_credential'], 'credential', 'value="" placeholder="' + html.escape(t['node_keep_credential'], quote=True) + '" autocomplete="new-password"')}</div>
            {sni_field}
            <label>{html.escape(t['node_cap_gib'])}<input type="number" name="cap_gib" min="0.000001" max="100000000" step="any" value="{cap}" placeholder="{html.escape(t['node_unlimited'], quote=True)}"></label>
            <label>{html.escape(t['node_expiry_utc'])}<input type="datetime-local" name="expires_at" value="{expiry}"></label>
            <label>{html.escape(t['node_reset_schedule'])}<select name="reset_mode">{options}</select></label>
            <label>{html.escape(t['node_reset_time_utc'])}<input type="datetime-local" name="next_reset_at" value="{next_reset}"></label>
          </div><button type="submit">{html.escape(t['node_save_settings'])}</button>
        </form>
        <form method="post" action="/proxy/node/reset" class="proxy-node-reset">
          <input type="hidden" name="protocol" value="{html.escape(protocol)}">
          <input type="hidden" name="csrf" value="{token}">
          <label class="checkline"><input type="checkbox" name="confirm" value="yes" required>
            <span>{html.escape(t['node_random_confirm'])}</span></label>
          <button type="submit" class="danger">{html.escape(t['node_random_reset'])}</button>
        </form>'''

    def node_credential_form(self, protocol, label, t):
        token = node_csrf_token(self.get_cookie("session"), protocol)
        return f"""
        <form method="post" action="/proxy/apply" autocomplete="off">
          <input type="hidden" name="protocol" value="{html.escape(protocol)}">
          <input type="hidden" name="csrf" value="{token}">
          {render_password_field(t, 'legacy-reset-' + protocol, label, 'credential', 'autocomplete="off" required')}
          <button type="submit">{html.escape(t['node_save_credential'])}</button>
        </form>
        """

    def handle_node_control(self, action):
        """Validate the browser request, then identify the node only on server."""
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = 0
        if (not 0 < length <= 4096 or
                self.headers.get("Content-Type", "").split(";", 1)[0].strip() !=
                "application/x-www-form-urlencoded"):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        try:
            form = parse_qs(self.rfile.read(length).decode("utf-8"),
                            strict_parsing=True, keep_blank_values=True)
        except (UnicodeError, ValueError):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if any(len(values) != 1 for values in form.values()):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        session = self.get_cookie("session")
        identifier = form.get("id", [""])[0]
        protocol = form.get("protocol", [""])[0]
        csrf_subject = "create" if action == "create" else identifier
        if not hmac.compare_digest(form.get("csrf", [""])[0],
                                   node_csrf_token(session, csrf_subject)):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        expected = {
            "create": {"protocol", "csrf", "name", "port", "sni", "credential"},
            "edit": {"id", "csrf", "name", "port", "credential"},
            "limits": {"id", "csrf", "cap_gib", "upload_mbps", "download_mbps",
                       "cap_action", "expiry_mode", "expiry_count", "expiry_unit",
                       "reset_mode", "reset_count", "reset_unit", "next_reset_at"},
            "reset": {"id", "csrf", "confirm"},
            "delete": {"id", "csrf", "confirm"},
            "toggle": {"id", "csrf", "enabled"},
        }.get(action)
        if action == "edit":
            try:
                inventory = read_inventory(state_path=NODE_STATE_PATH,
                                           config_paths={"anytls": ANYTLS_CONFIG, "proxy": PROXY_CONFIG})
                node = next(node for node in inventory["nodes"] if node["id"] == identifier)
            except (OSError, ValueError, TypeError, StopIteration):
                return self.redirect("/proxy?msg=node_settings_failed")
            if node["protocol"] != "shadowsocks":
                expected = expected | {"sni"}
        if set(form) != expected:
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if action in ("reset", "delete") and form["confirm"][0] != "yes":
            return self.redirect("/proxy?msg=node_settings_failed")
        if action == "toggle" and form["enabled"][0] not in ("yes", "no"):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if action == "create":
            if protocol not in NODE_PROTOCOLS:
                return self.redirect("/proxy?msg=node_settings_failed")
            try:
                port = int(form["port"][0]) if form["port"][0] else None
                request = {"action": "create", "protocol": protocol,
                           "name": form["name"][0], "port": port}
                if form["credential"][0]:
                    request["credential"] = form["credential"][0]
                if protocol != "shadowsocks":
                    request["sni"] = form["sni"][0].strip() or "www.bing.com"
            except ValueError:
                return self.redirect("/proxy?msg=node_settings_failed")
        else:
            request = {"action": "edit" if action == "limits" else action, "id": identifier}
        if action == "toggle":
            request["enabled"] = form["enabled"][0] == "yes"
        if action == "edit":
            try:
                request["name"] = form["name"][0]
                request["port"] = int(form["port"][0]) if form["port"][0] else node["port"]
                credential = form["credential"][0]
                if credential:
                    request["credential"] = credential
                if node["protocol"] != "shadowsocks":
                    sni = form["sni"][0]
                    current = _cert_common_name(node["inbound"]["tls"]["certificate_path"])
                    if sni != current:
                        request["sni"] = sni
            except (ValueError, KeyError):
                return self.redirect("/proxy?msg=node_settings_failed")
        elif action == "limits":
            try:
                cap = form["cap_gib"][0].strip()
                if cap:
                    amount = Decimal(cap)
                    if not amount.is_finite() or not 0 < amount <= 100000000:
                        raise ValueError("invalid cap")
                    request["cap_bytes"] = int(amount * 1073741824)
                else:
                    request["cap_bytes"] = None
                def speed(value):
                    if not value.strip():
                        return None
                    amount = Decimal(value)
                    if not amount.is_finite() or not Decimal("0.001") <= amount <= 10000000:
                        raise ValueError("invalid speed")
                    result = int(amount * 1000000)
                    if result < 1000:
                        raise ValueError("invalid speed")
                    return result
                request["upload_limit_bps"] = speed(form["upload_mbps"][0])
                request["download_limit_bps"] = speed(form["download_mbps"][0])
                if form["cap_action"][0] not in ("throttle", "block"):
                    raise ValueError("invalid cap action")
                request["cap_action"] = form["cap_action"][0]
                now = datetime.now(timezone.utc)
                def duration(count_value, unit_value):
                    count = int(count_value)
                    if not 1 <= count <= 9999 or unit_value not in ("days", "months", "years"):
                        raise ValueError("invalid duration")
                    anchor = "-" if unit_value == "days" else str(now.day) if unit_value == "months" else now.strftime("%m-%d")
                    mode = f"every:{count}:{unit_value}:{anchor}"
                    return count, unit_value, mode, advance_reset_interval(now, mode).isoformat()
                def date_value(value):
                    if not value:
                        return None
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", value):
                        raise ValueError("invalid date")
                    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).isoformat()
                expiry_mode = form["expiry_mode"][0]
                current = read_inventory(state_path=NODE_STATE_PATH,
                                         config_paths={"anytls": ANYTLS_CONFIG, "proxy": PROXY_CONFIG})
                existing = next(node for node in current["nodes"] if node["id"] == identifier)
                if expiry_mode == "set":
                    count, unit, _, due = duration(form["expiry_count"][0], form["expiry_unit"][0])
                    if (existing["expiry_count"], existing["expiry_unit"]) != (count, unit):
                        request.update(expiry_count=count, expiry_unit=unit, expires_at=due)
                elif expiry_mode == "none":
                    if existing["expiry_count"] is not None:
                        request.update(expiry_count=None, expiry_unit=None, expires_at=None)
                else:
                    raise ValueError("invalid expiry mode")
                mode = form["reset_mode"][0]
                if mode not in ("none", "repeat", "once"):
                    raise ValueError("invalid reset mode")
                if mode == "repeat":
                    _, _, request["reset_mode"], request["next_reset_at"] = duration(
                        form["reset_count"][0], form["reset_unit"][0])
                elif mode == "once":
                    request["reset_mode"] = "once"
                    request["next_reset_at"] = date_value(form["next_reset_at"][0])
                    if request["next_reset_at"] is None or \
                            datetime.fromisoformat(request["next_reset_at"]) <= now:
                        raise ValueError("reset must be future")
                else:
                    request["reset_mode"] = "none"
                    request["next_reset_at"] = None
            except (ValueError, InvalidOperation, OverflowError, KeyError, InvalidInventory,
                    TypeError, StopIteration):
                return self.redirect("/proxy?msg=node_settings_failed")
        success = node_control_apply(request)
        key = ({"reset": "node_reset_done", "create": "node_created", "delete": "node_deleted"}
               .get(action, "node_settings_done")) if success else "node_settings_failed"
        return self.redirect(f"/proxy?msg={key}", {"Cache-Control": "no-store"})

    def handle_node_apply(self):
        # Reject oversized/ambiguous forms before parsing or invoking the helper.
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = 0
        if (not 0 < length <= NODE_APPLY_BODY_LIMIT or
                self.headers.get("Content-Type", "").split(";", 1)[0].strip() !=
                "application/x-www-form-urlencoded"):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        try:
            form = parse_qs(self.rfile.read(length).decode("utf-8"),
                            strict_parsing=True, keep_blank_values=True)
        except (UnicodeError, ValueError):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if set(form) != {"protocol", "credential", "csrf"} or any(len(v) != 1 for v in form.values()):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        protocol = form["protocol"][0]
        session = self.get_cookie("session")
        if protocol not in NODE_PROTOCOLS or not hmac.compare_digest(
                form["csrf"][0], node_csrf_token(session, protocol)):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        credential = form["credential"][0]
        if not credential or len(credential.encode("utf-8")) > 128:
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if NODE_STATE_PATH.exists():
            return self.send_html(410, "Use node settings", {"Cache-Control": "no-store"})
        self.redirect(f"/proxy?msg={node_apply(protocol, credential)}",
                      {"Cache-Control": "no-store"})

    def handle_anytls_reset(self):
        if NODE_STATE_PATH.exists():
            return self.send_html(410, "Use node settings", {"Cache-Control": "no-store"})
        raw = self.read_body(LOGIN_BODY_LIMIT)
        form = parse_qs(raw.decode("utf-8", errors="replace"))
        # Checked on the server, not just by the `required` attribute: this
        # rotates live credentials and every client configured against the old
        # ones stops working. A bare button would put that one mis-click away,
        # and `required` is trivially bypassed by anything that is not a
        # browser.
        if form.get("confirm", [""])[0] != "yes":
            return self.redirect("/proxy?msg=anytls_reset_unconfirmed")
        self.redirect(f"/proxy?msg={anytls_reset()}")

    def handle_proxy_reset(self):
        if NODE_STATE_PATH.exists():
            return self.send_html(410, "Use node settings", {"Cache-Control": "no-store"})
        raw = self.read_body(LOGIN_BODY_LIMIT)
        form = parse_qs(raw.decode("utf-8", errors="replace"))
        if form.get("confirm", [""])[0] != "yes":
            return self.redirect("/proxy?msg=proxy_reset_unconfirmed")
        # Validated against the known set rather than passed through
        # verbatim: this reaches a subprocess argv, not a shell string, so
        # injection is not the risk — a typo or forged value silently
        # resetting nothing (or everything, via the empty-string "reset all"
        # path) would be.
        protocol = form.get("protocol", [""])[0]
        if protocol and protocol not in PROXY_PROTOCOL_ORDER:
            return self.redirect("/proxy?msg=proxy_reset_unconfirmed")
        self.redirect(f"/proxy?msg={proxy_reset(protocol or None)}")

    # -- visitor log ---------------------------------------------------

    def page_changelog(self, lang, query_lang):
        t = STRINGS[lang]
        # Follow the UI language. If the translation is missing (it lags the
        # English file between releases), fall back rather than show nothing —
        # but say which file is actually on screen.
        localized = CHANGELOG_PATHS.get(lang)
        path = localized if localized and localized.exists() else BASE_DIR / "doc" / "LOG.md"
        notice = ""
        if localized and path != localized:
            notice = f'<p class="muted small">{html.escape(t["changelog_fallback"])}</p>'

        source = path.read_text(encoding="utf-8") if path.exists() else ""
        section = changelog_section(source)
        development = ""
        if VERSION.startswith(("dev-", "test-")):
            updates = development_updates_section(source)
            if not updates and path != BASE_DIR / "doc" / "LOG.md":
                english = BASE_DIR / "doc" / "LOG.md"
                updates = development_updates_section(english.read_text(encoding="utf-8")) if english.exists() else None
                if updates:
                    development = f'<p class="muted small">{html.escape(t["development_fallback"])}</p>'
            if updates:
                development += render_changelog(f"### {VERSION_LABEL}\n{updates}")
        if section:
            content = development + notice + render_changelog(section)
        else:
            # Missing file or section must not render other LOG modules as release notes.
            content = development + f'<p class="muted">{html.escape(t["changelog_missing"])}</p>'
        body = f"""
        <div class="card wide">
          <h1>{html.escape(t['changelog'])} <span class="version-inline">{html.escape(VERSION_LABEL)}</span></h1>
          <div class="changelog">
          {content}
          </div>
        </div>
        """
        self.send_html(200, self.render_page(t['changelog'], body, lang, active="changelog"),
                       self.maybe_lang_cookie(query_lang))

    def page_visitors(self, lang, query_lang):
        t = STRINGS[lang]
        rows = recent_visitors()

        def render_row(r):
            scope = r["scope"]
            badge = ""
            if scope in ("loopback", "private"):
                badge = f' <span class="badge">{html.escape(t["scope_" + scope])}</span>'
            if r["hits"]:
                lastreq = html.escape(
                    f'{r["last_method"]} {r["last_path"]} → {r["last_status"]}'
                )
            else:
                lastreq = '<span class="muted">—</span>'
            direction = r["direction"] or "in"
            dir_html = (
                f'<span class="dir dir-{direction}">'
                f'{html.escape(t["dir_" + direction])}</span>'
            )
            return (
                f'<tr data-scope="{html.escape(scope)}" data-dir="{html.escape(direction)}">'
                f'<td>{html.escape(r["ip"])}{badge}</td>'
                f'<td>{dir_html}</td>'
                f'<td>{html.escape(r["first_seen"])}</td>'
                f'<td>{html.escape(r["last_seen"])}</td>'
                f'<td class="num">{r["hits"]}</td>'
                f'<td class="num ports">{html.escape(r["ports"] or "—")}</td>'
                f'<td class="lastreq">{lastreq}</td>'
                "</tr>"
            )

        if not rows:
            table_rows = f'<tr><td colspan="7">{html.escape(t["no_visits"])}</td></tr>'
        else:
            table_rows = "\n".join(render_row(r) for r in rows)

        heading = t["visitors_heading"].format(n=len(rows), max=MAX_VISITOR_ROWS)
        body = f"""
        <div class="card wide">
          <h1>{html.escape(heading)}</h1>
          <div class="filters">
            <button type="button" class="chip active" data-filter="all">{html.escape(t['show_all'])}</button>
            <button type="button" class="chip" data-filter="inbound">{html.escape(t['show_inbound'])}</button>
            <button type="button" class="chip" data-filter="public">{html.escape(t['show_external'])}</button>
          </div>
          <div class="table-scroll">
          <table id="visitors">
            <thead><tr>
              <th>{html.escape(t['col_ip'])}</th>
              <th>{html.escape(t['col_dir'])}</th>
              <th>{html.escape(t['col_first'])}</th>
              <th>{html.escape(t['col_last'])}</th>
              <th class="num">{html.escape(t['col_hits'])}</th>
              <th class="num">{html.escape(t['col_ports'])}</th>
              <th>{html.escape(t['col_lastreq'])}</th>
            </tr></thead>
            <tbody>
            {table_rows}
            </tbody>
          </table>
          </div>
        </div>
        <script src="/static/visitors.js"></script>
        """
        self.send_html(200, self.render_page(t['visitors'], body, lang, active="visitors"),
                       self.maybe_lang_cookie(query_lang))


# ---------------------------------------------------------------------------
# Public reachability page
#
# Two paths, two methods, no session, no query string, no request body. That
# narrowness *is* the security boundary: a request arriving on 80 or 443
# cannot reach a console route because no such route exists on this class.
# Read doc/LOG.md#decisions (2026-09-12) before adding anything here.
#
# The stylesheet is inlined rather than served from /static/, so this listener
# has no file-serving route at all.
# ---------------------------------------------------------------------------

PROBE_CSS = """
:root { color-scheme: light; --bg:#f5f7f6; --fg:#1d2d35; --muted:#52636b; --border:#d8e1e0; --accent:#365779; --success:#236b4d; --surface:#eef3f2; }
* { box-sizing: border-box; }
body { display: grid; place-items: center; min-height: 100vh; margin: 0; padding: 1rem; background: var(--bg); color: var(--fg); font: 16px/1.55 system-ui, -apple-system, 'Segoe UI', sans-serif; }
main { width: min(100%, 36rem); padding: clamp(1.5rem, 4vw, 2.5rem); border: 1px solid var(--border); border-radius: 10px; background: white; box-shadow: 0 10px 32px rgba(23,45,52,.06); }
h1 { display: flex; align-items: center; gap: .65rem; margin: 0 0 .5rem; font-size: clamp(1.45rem, 3vw, 1.8rem); line-height: 1.25; letter-spacing: -.03em; }
p { margin: .5rem 0; }.ok { display: grid; place-items: center; width: 2rem; height: 2rem; flex: none; border-radius: 7px; background: var(--surface); color: var(--success); }
dl { display: grid; grid-template-columns: minmax(8rem, auto) 1fr; gap: .6rem 1rem; margin: 1.5rem 0 0; padding-top: 1.25rem; border-top: 1px solid var(--border); }
dt,.note { color: var(--muted); }dd { margin: 0; overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }.note { margin-top: 1.5rem; font-size: .85rem; }
.iperf { margin: 1.25rem 0 0; padding: .75rem 1rem; border-radius: 8px; background: var(--surface); color: var(--success); font-size: .9rem; }
@media (max-width: 30rem) { dl { grid-template-columns: 1fr; gap: .1rem; }dt:not(:first-child) { margin-top: .6rem; } }
"""

class ProbeHandler(BaseHTTPRequestHandler):
    """The unauthenticated page on 80 and 443."""

    # No version string: whoever scans this port learns that something
    # answered, which is the entire point, and nothing more.
    server_version = "vps-server"
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass  # requests go to the visitor log instead

    def version_string(self):
        # Without this the base class appends sys_version and the page that
        # promises to disclose nothing about the host answers
        # "Server: vps-server Python/3.10.12" to any anonymous HEAD.
        return self.server_version

    def send_response(self, code, message=None):
        self._last_status = code
        super().send_response(code, message)

    def client_ip(self):
        if TRUST_PROXY:
            xff = self.headers.get("X-Forwarded-For")
            if xff:
                return xff.split(",")[0].strip()
        return self.client_address[0]

    def do_GET(self):
        self._dispatch(send_body=True)

    def do_HEAD(self):
        self._dispatch(send_body=False)

    def _dispatch(self, send_body):
        self._last_status = 200
        path = urlsplit(self.path).path
        try:
            if path == "/":
                body = self._page().encode("utf-8")
                self._send(200, body, "text/html; charset=utf-8", send_body)
            elif path == "/favicon.ico":
                self._send(200, (BASE_DIR / "static" / "favicon.svg").read_bytes(), "image/svg+xml", send_body)
            else:
                self._send(404, b"not found\n", "text/plain; charset=utf-8", send_body)
        except (BrokenPipeError, ConnectionResetError):
            self._last_status = 0  # client hung up; not a real outcome
        finally:
            if self._last_status:
                # This listener is the one strangers reach, so it is the one
                # most likely to be hitting a full disk or a busy database.
                # Failing to record a visit is not a reason to drop the
                # connection that was successfully served.
                try:
                    log_visit(self.client_ip(), self.command, path, self._last_status)
                except Exception as exc:
                    print(_log_text('log_visitor_write', error=exc), file=sys.stderr)

    def _send(self, status, body, content_type, send_body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        if send_body and body:
            self.wfile.write(body)

    def _page(self):
        # No cookie and no ?lang= here — the page has no navigation and sets
        # nothing. Accept-Language is all there is to go on, which is right for
        # a stranger who was handed an IP and nothing else.
        lang = pick_lang(None, None, self.headers.get("Accept-Language", ""))
        t = STRINGS[lang]
        # self.server is the listener this request actually arrived on, so the
        # port is the real one even with several running.
        arrived_port = self.server.server_address[1]
        scheme = "HTTPS" if getattr(self.server, "is_tls", False) else "HTTP"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        iperf_html = ""
        if IPERF_ENABLED:
            is_open, remaining = IPERF_WINDOW.state()
            if is_open:
                # Advertised on purpose: a tester who cannot see that the
                # window is open has no way to know when to connect, and the
                # window is deliberately open anyway.
                text = t["probe_iperf"].format(
                    port=IPERF_WINDOW.port, mins=remaining // 60, secs=remaining % 60
                )
                iperf_html = f'<p class="iperf">{html.escape(text)}</p>'

        return f"""<!doctype html>
<html lang="{HTML_LANG_TAGS.get(lang, lang)}"{RTL_ATTR.get(lang, "")}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(t['probe_title'])}</title>
<link rel="icon" type="image/svg+xml" href="/favicon.ico">
<style>{PROBE_CSS}</style>
</head>
<body>
<main>
<h1><span class="ok">&#10003;</span> {html.escape(t['probe_title'])}</h1>
<p>{html.escape(t['probe_ok'])}</p>
{iperf_html}
<dl>
  <dt>{html.escape(t['probe_your_ip'])}</dt><dd>{html.escape(self.client_ip())}</dd>
  <dt>{html.escape(t['probe_arrived_on'])}</dt><dd>{scheme} :{arrived_port}</dd>
  <dt>{html.escape(t['probe_server_time'])}</dt><dd>{now}</dd>
</dl>
<p class="note">{html.escape(t['probe_note'])}</p>
</main>
</body>
</html>"""


def serve_forever_in_thread(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def make_server(port, handler, tls):
    server = ThreadingHTTPServer((HOST, port), handler)
    server.daemon_threads = True
    server.is_tls = tls
    if tls:
        cert, key = ensure_tls_files()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=str(cert), keyfile=str(key))
        server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


def start_public_listeners(servers):
    """Bind the reachability page on both public ports. Best effort, each
    independently: "443 refused but 80 answered" is itself a useful answer for
    whoever is testing, so one failed bind must not take the other down — nor
    the console, which is the only way to fix anything.
    """
    for port, tls in ((PUBLIC_HTTP_PORT, False), (PUBLIC_HTTPS_PORT, True)):
        if port == CONSOLE_PORT:
            print(_log_text('log_public_conflict', port=port), file=sys.stderr)
            continue
        try:
            server = make_server(port, ProbeHandler, tls)
        except (OSError, SystemExit) as exc:
            print(_log_text('log_public_bind', port=port, error=exc), file=sys.stderr)
            continue
        servers.append(server)
        serve_forever_in_thread(server)
        print(_log_text('log_reachability', scheme='https' if tls else 'http', host=HOST, port=port), file=sys.stderr)


def main():
    servers = []
    stop_event = threading.Event()

    # Installed before any listener setup, not just around serve_forever():
    # a signal arriving while start_public_listeners()/PORTFWD.load() are
    # still running used to fall outside the old try/finally entirely, so
    # cleanup never ran for whatever had already come up by then. An open
    # window is a live child process plus a firewall rule, and systemd sends
    # SIGTERM on stop and restart — without this the iperf3 child would
    # outlive the service and the rule would be left behind.
    def request_shutdown(signum, frame):
        raise KeyboardInterrupt

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, request_shutdown)
        except ValueError:
            pass  # not on the main thread; the tests import this module

    try:
        console = make_server(CONSOLE_PORT, ConsoleHandler, CONSOLE_TLS)
        servers.append(console)
        print(_log_text('log_console', scheme='https' if CONSOLE_TLS else 'http', host=HOST, port=CONSOLE_PORT), file=sys.stderr)

        if PUBLIC_ENABLED:
            start_public_listeners(servers)

        if TRACK_CONNECTIONS:
            if os.path.exists("/proc/net/tcp"):
                threading.Thread(
                    target=connection_poller, args=(stop_event,), daemon=True
                ).start()
                print(_log_text('log_tracking', seconds=CONN_POLL_SECONDS), file=sys.stderr)
            else:
                print(_log_text('log_tracking_unavailable'), file=sys.stderr)

        if IPERF_ENABLED and not shutil.which("iperf3"):
            print(_log_text('log_iperf_missing'), file=sys.stderr)

        if portfwd_enabled():
            PORTFWD.load()
            active = sum(1 for r in PORTFWD.list_rules() if r["enabled"])
            if active:
                print(_log_text('log_portfwd_reapplied', count=active, path=PORTFWD_STATE_FILE), file=sys.stderr)
        threading.Thread(target=watch_portfwd_switch, args=(stop_event,), daemon=True).start()

        console.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # A second SIGTERM arriving while this block is still running (e.g.
        # mid-IPERF_WINDOW.close()) would otherwise raise a fresh
        # KeyboardInterrupt into the middle of cleanup and escape before the
        # firewall rule is withdrawn. The process is exiting either way, so
        # further signals are simply ignored from here on.
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(sig, signal.SIG_IGN)
            except ValueError:
                pass
        stop_event.set()
        IPERF_WINDOW.close()
        if portfwd_enabled():
            PORTFWD.shutdown()
        for s in servers:
            # shutdown() before server_close(): the public listeners are
            # still spinning in their own serve_forever_in_thread() loop, and
            # closing the socket out from under that loop logged an OSError
            # traceback on every restart. serve_forever() itself always marks
            # its own shutdown event on the way out (even via exception), so
            # calling shutdown() on the console server here — whose
            # serve_forever() already returned on this thread — is a no-op,
            # not a deadlock.
            s.shutdown()
            s.server_close()


if __name__ == "__main__":
    main()
