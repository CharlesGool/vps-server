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
import errno
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


# Source and installed code both live under src/web. The installed root keeps
# only a small entry point and all persistent data remains beside it.
WEB_CODE_DIR = Path(__file__).resolve().parent
BASE_DIR = WEB_CODE_DIR
if BASE_DIR.parent.name == "src" and (BASE_DIR.parent.parent / "README.md").is_file():
    BASE_DIR = BASE_DIR.parent.parent
STATIC_DIR = WEB_CODE_DIR / "static"
sys.path.insert(0, str(WEB_CODE_DIR))
from node_state import read_inventory, _read_json
from node_inventory import advance_reset_interval, reset_interval
from module_manager import MODULES as MANAGED_MODULES, UNITS as MANAGED_UNITS
from module_manager import FEATURES as MANAGED_FEATURES, GROUPS as MANAGED_GROUPS
from module_manager import feature_enabled as module_feature_enabled, log_path as module_log_path
from module_manager import installed_modules, save_status as save_module_status
from module_manager import iperf_binary
from module_manager import status_path as module_status_path, public_listener_enabled, frpc_group_enabled
from console_port import available as console_port_available, read_rows as console_port_rows
from frp_control import (client_names as frpc_names, client_path as frpc_path,
                         client_unit as frpc_unit,
                         client_summary as frpc_summary, structured_client as frpc_structured,
                         build_client as frpc_build)
import features.auth as _feature_auth
import features.modules as _feature_modules
import features.system as _feature_system
import features.iperf as _feature_iperf
from features.iperf_client import IperfClient
import features.portfwd as _feature_portfwd
import features.proxy_service as _feature_proxy
import features.lucky as _feature_lucky
import features.frp as _feature_frp
import features.visitors as _feature_visitors
import features.ui as _feature_ui
from features.identity import read_server_label, save_server_label as write_server_label


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
    files = {"en": "en", "zh_cn": "zh-CN", "es": "es"}
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
PUBLIC_DEFAULT = os.environ.get("VPSSRV_PUBLIC_ENABLE", "1") == "1"
PUBLIC_HTTP_ENABLED = public_listener_enabled(BASE_DIR, "web_http", PUBLIC_DEFAULT)
PUBLIC_HTTPS_ENABLED = public_listener_enabled(BASE_DIR, "web_https", PUBLIC_DEFAULT)
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
IPERF_BINARY = iperf_binary(BASE_DIR)
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


def portfwd_enabled(*args, **kwargs):
    return _feature_modules.portfwd_enabled(sys.modules[__name__], *args, **kwargs)
PORTFWD_MAX_RULES = int(os.environ.get("VPSSRV_PORTFWD_MAX_RULES", "20"))

DATA_DIR.mkdir(parents=True, exist_ok=True)
os.chmod(DATA_DIR, 0o700)

SECRET_FILE = DATA_DIR / "session_secret.txt"
SESSION_STATE_FILE = DATA_DIR / "sessions.json"
DB_FILE = DATA_DIR / "visitors.db"
PORTFWD_STATE_FILE = DATA_DIR / "portfwd.json"

SESSION_TTL_SECONDS = 12 * 3600
SECURITY_PERMISSION_SECONDS = 10 * 60
MAX_VISITOR_ROWS = 1000
DOWNLOAD_CHUNK = 1024 * 1024  # 1 MiB fill buffer, repeated to build the response
LOGIN_BODY_LIMIT = 4096


def _write_secret_file(*args, **kwargs):
    return _feature_auth._write_secret_file(sys.modules[__name__], *args, **kwargs)


def ensure_admin_password(*args, **kwargs):
    return _feature_auth.ensure_admin_password(sys.modules[__name__], *args, **kwargs)


def normalized_ip(*args, **kwargs):
    return _feature_auth.normalized_ip(sys.modules[__name__], *args, **kwargs)


_PRIVATE_LOGIN_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7"))


def normalized_private_ip(*args, **kwargs):
    return _feature_auth.normalized_private_ip(sys.modules[__name__], *args, **kwargs)


def _atomic_private_text(*args, **kwargs):
    return _feature_auth._atomic_private_text(sys.modules[__name__], *args, **kwargs)


class IpAllowlist(_feature_auth.IpAllowlist):
    context = sys.modules[__name__]


def ensure_console_port(*args, **kwargs):
    return _feature_auth.ensure_console_port(sys.modules[__name__], *args, **kwargs)


def ensure_session_secret(*args, **kwargs):
    return _feature_auth.ensure_session_secret(sys.modules[__name__], *args, **kwargs)


def ensure_tls_files(*args, **kwargs):
    return _feature_auth.ensure_tls_files(sys.modules[__name__], *args, **kwargs)


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


def _cmd_output(*args, **kwargs):
    return _feature_system._cmd_output(sys.modules[__name__], *args, **kwargs)


def _run_quiet(*args, **kwargs):
    return _feature_system._run_quiet(sys.modules[__name__], *args, **kwargs)


def module_states(*args, **kwargs):
    return _feature_modules.module_states(sys.modules[__name__], *args, **kwargs)


def firewall_backend(*args, **kwargs):
    return _feature_system.firewall_backend(sys.modules[__name__], *args, **kwargs)


def firewall_port(*args, **kwargs):
    return _feature_system.firewall_port(sys.modules[__name__], *args, **kwargs)


# ---------------------------------------------------------------------------
# iperf3 window
# ---------------------------------------------------------------------------


class IperfWindow(_feature_iperf.IperfWindow):
    context = sys.modules[__name__]


IPERF_WINDOW = IperfWindow(IPERF_PORT, IPERF_MAX_MINUTES, IPERF_PORT_FILE)
IPERF_CLIENT = IperfClient(find_binary=lambda _: IPERF_BINARY)

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


def _valid_port(*args, **kwargs):
    return _feature_portfwd._valid_port(sys.modules[__name__], *args, **kwargs)


def _valid_target_host(*args, **kwargs):
    return _feature_portfwd._valid_target_host(sys.modules[__name__], *args, **kwargs)


def _portfwd_comment(*args, **kwargs):
    return _feature_portfwd._portfwd_comment(sys.modules[__name__], *args, **kwargs)


def _portfwd_specs(*args, **kwargs):
    return _feature_portfwd._portfwd_specs(sys.modules[__name__], *args, **kwargs)


def _ensure_ip_forward(*args, **kwargs):
    return _feature_portfwd._ensure_ip_forward(sys.modules[__name__], *args, **kwargs)


def portfwd_rule_apply(*args, **kwargs):
    return _feature_portfwd.portfwd_rule_apply(sys.modules[__name__], *args, **kwargs)


class PortForwardManager(_feature_portfwd.PortForwardManager):
    context = sys.modules[__name__]


PORTFWD = PortForwardManager(PORTFWD_STATE_FILE, PORTFWD_MAX_RULES)
PORTFWD_SWITCH_FILE = DATA_DIR / "portfwd-enabled"
PORTFWD_APPLIED_FILE = DATA_DIR / "portfwd-applied.json"


def portfwd_switch_revision(*args, **kwargs):
    return _feature_portfwd.portfwd_switch_revision(sys.modules[__name__], *args, **kwargs)


def publish_portfwd_state(*args, **kwargs):
    return _feature_portfwd.publish_portfwd_state(sys.modules[__name__], *args, **kwargs)


def watch_portfwd_switch(*args, **kwargs):
    return _feature_portfwd.watch_portfwd_switch(sys.modules[__name__], *args, **kwargs)

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
def _cert_common_name(*args, **kwargs):
    return _feature_proxy._cert_common_name(sys.modules[__name__], *args, **kwargs)


def anytls_installed(*args, **kwargs):
    return _feature_proxy.anytls_installed(sys.modules[__name__], *args, **kwargs)


def anytls_node(*args, **kwargs):
    return _feature_proxy.anytls_node(sys.modules[__name__], *args, **kwargs)


def anytls_clash_line(*args, **kwargs):
    return _feature_proxy.anytls_clash_line(sys.modules[__name__], *args, **kwargs)


def anytls_share_link(*args, **kwargs):
    return _feature_proxy.anytls_share_link(sys.modules[__name__], *args, **kwargs)


# Mirrors setup-anytls.sh's get_lan_ips filter. Keeping a second copy of the
# list is a drift risk; the alternative is the console shelling into the
# vendored script to ask, which is worse.
VIRTUAL_IFACE_PREFIXES = ("docker", "br-", "veth", "virbr", "cni", "flannel", "kube")


def local_addresses(*args, **kwargs):
    return _feature_proxy.local_addresses(sys.modules[__name__], *args, **kwargs)


def tailscale_address(*args, **kwargs):
    return _feature_proxy.tailscale_address(sys.modules[__name__], *args, **kwargs)


def address_entries(*args, **kwargs):
    return _feature_proxy.address_entries(sys.modules[__name__], *args, **kwargs)


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
NODE_STATE_PATH = Path("/etc/vps-server-nodes/state.json")
NODE_METER_PATH = NODE_STATE_PATH.parent / "meter.json"
NODE_CONTROL_HELPER = WEB_CODE_DIR / "node_control.py"
NODE_CONTROL_UNIT = "vps-server-node-control.service"
NODE_APPLY_TIMEOUT = 120
NODE_PROTOCOLS = frozenset(("anytls", "vmess", "vless", "trojan", "shadowsocks"))


def node_csrf_token(*args, **kwargs):
    return _feature_proxy.node_csrf_token(sys.modules[__name__], *args, **kwargs)


def node_control_apply(*args, **kwargs):
    return _feature_proxy.node_control_apply(sys.modules[__name__], *args, **kwargs)
# Display order only — config.json's own inbounds order already matches this
# (setup-proxy.sh writes them in ALL_PROTOCOLS order), but a config hand-
# edited or produced some other way should not scramble the console page.
PROXY_PROTOCOL_ORDER = ("vmess", "vless", "trojan", "shadowsocks")


def proxy_installed(*args, **kwargs):
    return _feature_proxy.proxy_installed(sys.modules[__name__], *args, **kwargs)


def proxy_nodes(*args, **kwargs):
    return _feature_proxy.proxy_nodes(sys.modules[__name__], *args, **kwargs)


FRPS_CONFIG = Path(os.environ.get('VPSSRV_FRPS_CONFIG', '/etc/vps-server-frps/frps.toml'))
FRPS_SERVICE = 'vps-server-frps.service'
FRPC_BINARY = Path(os.environ.get('VPSSRV_FRPC_BIN', '/usr/local/bin/frpc'))
FRP_CONTROL_HELPER = WEB_CODE_DIR / 'frp_control.py'
LUCKY_CONFIG = Path(os.environ.get('VPSSRV_LUCKY_CONFIG', '/etc/vps-server-lucky/config.json'))
LUCKY_SERVICE = 'vps-server-lucky.service'


def lucky_admin(*args, **kwargs):
    return _feature_lucky.lucky_admin(sys.modules[__name__], *args, **kwargs)



def frps_node(*args, **kwargs):
    return _feature_frp.frps_node(sys.modules[__name__], *args, **kwargs)


def frpc_connected(*args, **kwargs):
    return _feature_frp.frpc_connected(sys.modules[__name__], *args, **kwargs)


_frpc_probe_lock = threading.Lock()


def frpc_test_connection(*args, **kwargs):
    return _feature_frp.frpc_test_connection(sys.modules[__name__], *args, **kwargs)


def masked_frpc_ip(*args, **kwargs):
    return _feature_frp.masked_frpc_ip(sys.modules[__name__], *args, **kwargs)


def proxy_running(*args, **kwargs):
    return _feature_proxy.proxy_running(sys.modules[__name__], *args, **kwargs)


def proxy_clash_line(*args, **kwargs):
    return _feature_proxy.proxy_clash_line(sys.modules[__name__], *args, **kwargs)


def clash_share_token(*args, **kwargs):
    return _feature_proxy.clash_share_token(sys.modules[__name__], *args, **kwargs)


def clash_lan_host(*args, **kwargs):
    return _feature_proxy.clash_lan_host(sys.modules[__name__], *args, **kwargs)


def is_lan_address(*args, **kwargs):
    return _feature_proxy.is_lan_address(sys.modules[__name__], *args, **kwargs)


def clash_profile(*args, **kwargs):
    return _feature_proxy.clash_profile(sys.modules[__name__], *args, **kwargs)


def proxy_share_link(*args, **kwargs):
    return _feature_proxy.proxy_share_link(sys.modules[__name__], *args, **kwargs)


def render_copyable(*args, **kwargs):
    return _feature_ui.render_copyable(sys.modules[__name__], *args, **kwargs)

# Result keys the console may echo back after a redirect. Whitelisted because
# the key indexes STRINGS: without this, a crafted ?msg= would be a way to
# render any string from the table on an authenticated page.
IPERF_MESSAGE_KEYS = frozenset({
    "iperf_opened", "iperf_extended", "iperf_shut",
    "iperf_disabled", "iperf_missing", "iperf_port_busy",
    "iperf_port_saved", "iperf_port_invalid",
})

NODE_APPLY_MESSAGE_KEYS = frozenset({"node_settings_done", "node_settings_failed",
                                     "node_reset_done", "node_created", "node_deleted"})

PORTFWD_MESSAGE_KEYS = frozenset({
    "portfwd_added", "portfwd_removed", "portfwd_enabled", "portfwd_disabled",
    "portfwd_invalid", "portfwd_apply_failed", "portfwd_port_taken", "portfwd_limit", "portfwd_not_found",
    "portfwd_module_disabled",
})

# ---------------------------------------------------------------------------
# Internationalization (English / Simplified Chinese / Spanish)
# ---------------------------------------------------------------------------


# Rendered in the navigation in display order.
LANG_NAMES = {"en": "English", "zh_cn": "简体中文", "es": "Español"}

# The runtime code zh_cn is a legacy identifier; HTML uses BCP-47.
HTML_LANG_TAGS = {"zh_cn": "zh-CN"}
RTL_ATTR = {}


def pick_lang(*args, **kwargs):
    return _feature_auth.pick_lang(sys.modules[__name__], *args, **kwargs)


# ---------------------------------------------------------------------------
# Sessions are cached in memory and restored from a private file on restart.
# ---------------------------------------------------------------------------

_sessions = {}
_ip_sessions = {}
_security_sessions = {}
_sessions_lock = threading.Lock()
_feature_auth.load_sessions(sys.modules[__name__])


def create_session(*args, **kwargs):
    return _feature_auth.create_session(sys.modules[__name__], *args, **kwargs)


def session_valid(*args, **kwargs):
    return _feature_auth.session_valid(sys.modules[__name__], *args, **kwargs)


def security_settings_valid(*args, **kwargs):
    return _feature_auth.security_settings_valid(sys.modules[__name__], *args, **kwargs)


def create_ip_session(*args, **kwargs):
    return _feature_auth.create_ip_session(sys.modules[__name__], *args, **kwargs)


def ip_session_valid(*args, **kwargs):
    return _feature_auth.ip_session_valid(sys.modules[__name__], *args, **kwargs)


def destroy_session(*args, **kwargs):
    return _feature_auth.destroy_session(sys.modules[__name__], *args, **kwargs)


def access_csrf_token(*args, **kwargs):
    return _feature_auth.access_csrf_token(sys.modules[__name__], *args, **kwargs)


_password_lock = threading.Lock()


def change_admin_password(*args, **kwargs):
    return _feature_auth.change_admin_password(sys.modules[__name__], *args, **kwargs)


# ---------------------------------------------------------------------------
# Login rate limiting — per source IP, in memory, reset by a restart just
# like sessions are. A lockout is cleared by a successful login or by
# waiting it out; it is never permanent, so a forgetful operator cannot
# lock themselves out for good.
# ---------------------------------------------------------------------------


class LoginRateLimiter(_feature_auth.LoginRateLimiter):
    context = sys.modules[__name__]


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


def ip_scope(*args, **kwargs):
    return _feature_auth.ip_scope(sys.modules[__name__], *args, **kwargs)


def init_db(*args, **kwargs):
    return _feature_visitors.init_db(sys.modules[__name__], *args, **kwargs)


def _trim(*args, **kwargs):
    return _feature_visitors._trim(sys.modules[__name__], *args, **kwargs)


def log_visit(*args, **kwargs):
    return _feature_visitors.log_visit(sys.modules[__name__], *args, **kwargs)


def record_connections(*args, **kwargs):
    return _feature_visitors.record_connections(sys.modules[__name__], *args, **kwargs)


def recent_visitors(*args, **kwargs):
    return _feature_visitors.recent_visitors(sys.modules[__name__], *args, **kwargs)


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


def _decode_addr(*args, **kwargs):
    return _feature_visitors._decode_addr(sys.modules[__name__], *args, **kwargs)


def _read_proc_net(*args, **kwargs):
    return _feature_visitors._read_proc_net(sys.modules[__name__], *args, **kwargs)


def observed_connections(*args, **kwargs):
    return _feature_visitors.observed_connections(sys.modules[__name__], *args, **kwargs)


def connection_poller(*args, **kwargs):
    return _feature_visitors.connection_poller(sys.modules[__name__], *args, **kwargs)


init_db()

# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


def render_lang_switcher(*args, **kwargs):
    return _feature_ui.render_lang_switcher(sys.modules[__name__], *args, **kwargs)


def render_password_field(*args, **kwargs):
    return _feature_ui.render_password_field(sys.modules[__name__], *args, **kwargs)


def _inline_md(*args, **kwargs):
    return _feature_ui._inline_md(sys.modules[__name__], *args, **kwargs)


def changelog_section(*args, **kwargs):
    return _feature_ui.changelog_section(sys.modules[__name__], *args, **kwargs)


def development_updates_section(*args, **kwargs):
    return _feature_ui.development_updates_section(sys.modules[__name__], *args, **kwargs)


def render_changelog(*args, **kwargs):
    return _feature_ui.render_changelog(sys.modules[__name__], *args, **kwargs)


_UI_ICON_NAMES = frozenset({"activity", "gauge", "timer", "network", "route", "users-round", "scroll-text", "log-out", "server", "settings-2", "radio", "lock-keyhole"})
_UI_ICON_CACHE = {}


def ui_icon(*args, **kwargs):
    return _feature_ui.ui_icon(sys.modules[__name__], *args, **kwargs)


def render_theme_menu(*args, **kwargs):
    return _feature_ui.render_theme_menu(sys.modules[__name__], *args, **kwargs)


def render_page(*args, **kwargs):
    return _feature_ui.render_page(sys.modules[__name__], *args, **kwargs)


def server_label():
    return read_server_label(DATA_DIR)


def save_server_label(value):
    write_server_label(DATA_DIR, value)


CHANGELOG_PATHS = {
    code: BASE_DIR / "doc" / (tag or "") / "CHANGELOG.md"
    for code, tag in (("en", "en"), ("zh_cn", None), ("es", "es"))
}
CHANGELOG_PATHS["zh_cn"] = BASE_DIR / "doc" / "CHANGELOG.md"

STATIC_FILES = {
    "/static/style.css": ("text/css", STATIC_DIR / "style.css"),
    "/static/theme.js": ("application/javascript", STATIC_DIR / "theme.js"),
    "/static/password-fields.js": ("application/javascript", STATIC_DIR / "password-fields.js"),
    "/static/access-settings.js": ("application/javascript", STATIC_DIR / "access-settings.js"),
    "/static/settings-sections.js": ("application/javascript", STATIC_DIR / "settings-sections.js"),
    "/static/module-status.js": ("application/javascript", STATIC_DIR / "module-status.js"),
    "/static/module-controls.js": ("application/javascript", STATIC_DIR / "module-controls.js"),
    "/static/reference-select.js": ("application/javascript", STATIC_DIR / "reference-select.js"),
    "/static/frp-editor.js": ("application/javascript", STATIC_DIR / "frp-editor.js"),
    "/static/layout-motion.js": ("application/javascript", STATIC_DIR / "layout-motion.js"),
    "/static/auth-history.js": ("application/javascript", STATIC_DIR / "auth-history.js"),
    "/favicon.ico": ("image/svg+xml", STATIC_DIR / "favicon.svg"),
    **{f"/static/favicon-{page}.svg": ("image/svg+xml", STATIC_DIR / f"favicon-{page}.svg")
       for page in ("home", "speedtest", "iperf", "proxy", "portfwd", "visitors",
                    "changelog", "settings", "security", "modules", "frp", "lucky", "login")},
    "/static/fonts/inter-latin-400.woff2": ("font/woff2", STATIC_DIR / "fonts" / "inter-latin-400.woff2"),
    "/static/fonts/inter-latin-600.woff2": ("font/woff2", STATIC_DIR / "fonts" / "inter-latin-600.woff2"),
    "/static/fonts/inter-latin-700.woff2": ("font/woff2", STATIC_DIR / "fonts" / "inter-latin-700.woff2"),
    "/static/fonts/noto-sans-sc-400.woff2": ("font/woff2", STATIC_DIR / "fonts" / "noto-sans-sc-400.woff2"),
    "/static/fonts/noto-sans-sc-700.woff2": ("font/woff2", STATIC_DIR / "fonts" / "noto-sans-sc-700.woff2"),
    "/static/speedtest.js": ("application/javascript", STATIC_DIR / "third_party" / "librespeed" / "speedtest.js"),
    "/static/speedtest-ui.js": ("application/javascript", STATIC_DIR / "speedtest-ui.js"),
    "/static/visitors.js": ("application/javascript", STATIC_DIR / "visitors.js"),
    "/static/copy.js": ("application/javascript", STATIC_DIR / "copy.js"),
    "/static/private-values.js": ("application/javascript", STATIC_DIR / "private-values.js"),
    "/static/node-controls.js": ("application/javascript", STATIC_DIR / "node-controls.js"),
    "/static/qrcode.js": ("application/javascript", STATIC_DIR / "third_party" / "qrcode" / "qrcode.js"),
    "/static/qrcode-utf8.js": ("application/javascript", STATIC_DIR / "third_party" / "qrcode" / "qrcode-utf8.js"),
    "/static/qrcode-render.js": ("application/javascript", STATIC_DIR / "qrcode-render.js"),
    "/static/iperf-countdown.js": ("application/javascript", STATIC_DIR / "iperf-countdown.js"),
    # speedtest.js spawns `new Worker("speedtest_worker.js?r=...")`. That call
    # runs in the *page's* context, so the browser resolves it relative to the
    # page URL (/speedtest), not relative to /static/speedtest.js — it lands
    # on /speedtest_worker.js, not /static/speedtest_worker.js. Serving it at
    # both paths sidesteps relying on that resolution quirk.
    "/speedtest_worker.js": ("application/javascript", STATIC_DIR / "third_party" / "librespeed" / "speedtest_worker.js"),
}

# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------


from features.auth import AuthMixin
from features.settings import SettingsMixin
from features.modules import ModulesMixin
from features.speedtest import SpeedtestMixin
from features.iperf import IperfMixin
from features.portfwd import PortfwdMixin
from features.lucky import LuckyMixin
from features.frp import FrpMixin
from features.proxy import ProxyMixin
from features.changelog import ChangelogMixin
from features.visitors import VisitorsMixin
from features.public import PublicMixin

class ConsoleHandler(AuthMixin, SettingsMixin, ModulesMixin, SpeedtestMixin, IperfMixin,
                     PortfwdMixin, LuckyMixin, FrpMixin, ProxyMixin,
                     ChangelogMixin, VisitorsMixin, BaseHTTPRequestHandler):
    """The authenticated console, on its own hard-to-guess port.

    Every route that does anything lives here. ProbeHandler, further down,
    deliberately shares none of it.
    """
    context = sys.modules[__name__]

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
        except Exception as exc:
            self._last_status = 500
            # Request paths and exception messages may contain subscription
            # tokens or configuration values. Log only safe diagnostic facts.
            print(f"Console {method} failed: {type(exc).__name__}", file=sys.stderr)
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

        if self.route_proxy_public(method, path):
            return

        lang, query_lang = self.resolve_lang(parsed)

        # With auth off there is nothing to log in or out of: a login form
        # that accepts nothing and a logout link that ends no session are
        # both dead ends, so send those paths back to the dashboard.
        if path in ("/login", "/login/ip", "/logout") and not AUTH_ENABLED:
            return self.redirect("/")
        if path.startswith("/settings") and not AUTH_ENABLED:
            return self.send_html(404, "Not found", {"Cache-Control": "no-store"})

        if self.route_login(method, path, parsed, lang, query_lang):
            return

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
                                ("portfwd", "/portfwd")):
            enabled = portfwd_enabled() if feature == "portfwd" else module_feature_enabled(BASE_DIR, feature)
            if path.startswith(prefix + "/") and not enabled:
                return self.send_html(404, "Not found", {"Cache-Control": "no-store"})

        if self.route_settings(method, path, parsed, lang, query_lang):
            return
        if self.route_module_admin(method, path, lang, query_lang):
            return

        for route in (self.route_modules, self.route_speedtest, self.route_proxy,
                      self.route_lucky, self.route_frp, self.route_iperf,
                      self.route_portfwd, self.route_visitors, self.route_changelog):
            if route(method, path, parsed, lang, query_lang):
                return

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













    # -- dashboard ---------------------------------------------------------


    # -- speed test ----------------------------------------------------


    # These three implement LibreSpeed's own client/server contract exactly
    # (garbage.php / empty.php / getIP.php equivalents) rather than a
    # hand-rolled protocol — see vps-webserver DECISIONS.md (2026-08-25). Header set and
    # ckSize clamping match the reference PHP backend byte-for-byte so the
    # vendored speedtest.js/speedtest_worker.js need no server-side quirks.





    # -- iperf3 window -------------------------------------------------





    # -- port forwarding -------------------------------------------------






    # -- anytls node ----------------------------------------------------


























    # -- visitor log ---------------------------------------------------




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

PROBE_CSS = (STATIC_DIR / "styles/public.css").read_text()

class ProbeHandler(PublicMixin, BaseHTTPRequestHandler):
    """The unauthenticated page on 80 and 443."""
    context = sys.modules[__name__]


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
    result = {}
    for port, tls, enabled in ((PUBLIC_HTTP_PORT, False, PUBLIC_HTTP_ENABLED),
                               (PUBLIC_HTTPS_PORT, True, PUBLIC_HTTPS_ENABLED)):
        name = "https" if tls else "http"
        result[name] = {"port": port, "enabled": enabled, "bound": False, "reason": ""}
        if not enabled:
            continue
        if port == CONSOLE_PORT:
            print(_log_text('log_public_conflict', port=port), file=sys.stderr)
            result[name]["reason"] = "occupied"
            continue
        try:
            server = make_server(port, ProbeHandler, tls)
        except (OSError, SystemExit) as exc:
            print(_log_text('log_public_bind', port=port, error=exc), file=sys.stderr)
            result[name]["reason"] = "occupied" if isinstance(exc, OSError) and exc.errno == errno.EADDRINUSE else "failed"
            continue
        servers.append(server)
        serve_forever_in_thread(server)
        result[name]["bound"] = True
        print(_log_text('log_reachability', scheme='https' if tls else 'http', host=HOST, port=port), file=sys.stderr)
    return result


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
            pass  # signal handlers can only be installed on the main thread

    try:
        console = make_server(CONSOLE_PORT, ConsoleHandler, CONSOLE_TLS)
        servers.append(console)
        print(_log_text('log_console', scheme='https' if CONSOLE_TLS else 'http', host=HOST, port=CONSOLE_PORT), file=sys.stderr)

        listener_status = start_public_listeners(servers)
        status_file = DATA_DIR / "public-listeners.json"
        status_file.parent.mkdir(parents=True, exist_ok=True)
        temp_status = status_file.with_suffix(".tmp")
        temp_status.write_text(json.dumps({"pid": os.getpid(), **listener_status}) + "\n")
        os.chmod(temp_status, 0o600)
        os.replace(temp_status, status_file)

        if TRACK_CONNECTIONS:
            if os.path.exists("/proc/net/tcp"):
                threading.Thread(
                    target=connection_poller, args=(stop_event,), daemon=True
                ).start()
                print(_log_text('log_tracking', seconds=CONN_POLL_SECONDS), file=sys.stderr)
            else:
                print(_log_text('log_tracking_unavailable'), file=sys.stderr)

        if IPERF_ENABLED and not IPERF_BINARY:
            print(_log_text('log_iperf_missing'), file=sys.stderr)

        if portfwd_enabled():
            PORTFWD.load()
            active = sum(1 for r in PORTFWD.list_rules() if r["applied"])
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
