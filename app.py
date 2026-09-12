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
bugged into allowing; an absent route cannot. See DECISIONS.md (2026-09-12)
before considering merging the two.

Standard-library only (see DECISIONS.md). Run with `python3 app.py`.
"""

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
import sqlite3
import ssl
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

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


# Single source of truth for the version. Shown in the UI next to the brand
# and used by the release checklist; bump it in the same commit as the tag.
# This is vps-server's own version, not the vps-webserver release this file was
# vendored from — that tag is recorded in .upstream-version.
VERSION = "0.1.0"

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

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
PUBLIC_ENABLED = os.environ.get("VPSSRV_PUBLIC_ENABLE", "1") == "1"
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
# Login can be turned off at install time (see install.sh) for setups relying
# on the random port alone. The password file is still generated either way
# so flipping this back on later doesn't require a restart-time prompt.
AUTH_ENABLED = os.environ.get("VPSSRV_AUTH", "1") == "1"

# iperf3 window. There is no "leave it running" option on purpose: an
# unauthenticated public `iperf3 -s` lets any stranger saturate the uplink for
# as long as they like, and nothing about the host surfaces that it is
# happening. See DECISIONS.md (2026-09-12).
IPERF_ENABLED = os.environ.get("VPSSRV_IPERF_ENABLE", "1") == "1"
IPERF_PORT = int(os.environ.get("VPSSRV_IPERF_PORT", "5201"))
IPERF_DEFAULT_MINUTES = int(os.environ.get("VPSSRV_IPERF_DEFAULT_MINUTES", "10"))
IPERF_MAX_MINUTES = int(os.environ.get("VPSSRV_IPERF_MAX_MINUTES", "60"))

DATA_DIR.mkdir(parents=True, exist_ok=True)
os.chmod(DATA_DIR, 0o700)

SECRET_FILE = DATA_DIR / "session_secret.txt"
DB_FILE = DATA_DIR / "visitors.db"

SESSION_TTL_SECONDS = 12 * 3600
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
    print(f"Generated initial admin password, see {PASSWORD_FILE}", file=sys.stderr)
    return password


def ensure_console_port():
    """Explicit VPSSRV_CONSOLE_PORT always wins and is never persisted.
    Otherwise pick a random port once and remember it — regenerating on every
    restart would make the console impossible to find again.
    """
    env_port = os.environ.get("VPSSRV_CONSOLE_PORT")
    if env_port:
        return int(env_port)
    if CONSOLE_PORT_FILE.exists():
        return int(CONSOLE_PORT_FILE.read_text().strip())
    port = 20000 + secrets.randbelow(40000)  # 20000-59999
    _write_secret_file(CONSOLE_PORT_FILE, str(port))
    print(f"Generated random console port {port}, see {CONSOLE_PORT_FILE}",
          file=sys.stderr)
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
    part of a Debian/Ubuntu base install. See DECISIONS.md.
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
    print(f"Generated self-signed certificate in {CERT_DIR}", file=sys.stderr)
    return cert, key


ADMIN_PASSWORD = ensure_admin_password()
CONSOLE_PORT = ensure_console_port()
SESSION_SECRET = ensure_session_secret()  # reserved for future cookie signing
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
    print(
        f"Could not {'open' if opening else 'close'} port {port} via {backend}; "
        "adjust the firewall by hand if the test cannot connect.",
        file=sys.stderr,
    )
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

    def __init__(self, port, max_minutes):
        self._port = port
        self._max_minutes = max_minutes
        self._lock = threading.RLock()
        self._proc = None
        self._deadline = 0.0
        self._timer = None

    @property
    def port(self):
        return self._port

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
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        firewall_port(self._port, opening=False)


IPERF_WINDOW = IperfWindow(IPERF_PORT, IPERF_MAX_MINUTES)

# Result keys the console may echo back after a redirect. Whitelisted because
# the key indexes STRINGS: without this, a crafted ?msg= would be a way to
# render any string from the table on an authenticated page.
IPERF_MESSAGE_KEYS = frozenset({
    "iperf_opened", "iperf_extended", "iperf_shut",
    "iperf_disabled", "iperf_missing", "iperf_port_busy",
})

# ---------------------------------------------------------------------------
# Internationalization (English / Simplified Chinese)
# ---------------------------------------------------------------------------

STRINGS = {
    "en": {
        "title": "vps-server",
        "login": "Log in",
        "password": "Password",
        "wrong_password": "Wrong password.",
        "logout": "Log out",
        "dashboard": "Dashboard",
        "speedtest": "Speed test",
        "visitors": "Recent visitors",
        "back": "Back",
        "your_ip": "Your IP as seen by this server",
        "run_test": "Run test",
        "running": "Testing…",
        "download": "Download",
        "upload": "Upload",
        "latency": "Latency",
        "jitter": "Jitter",
        "idle": "—",
        "waiting": "waiting",
        "warmup": "warming up…",
        "measuring": "measuring…",
        "done": "done",
        "test_info": "Latency is measured first over {pings} round trips, then each direction runs for about {sec}s over several parallel connections; the first {warm}s of each are a warmup and not counted.",
        "visitors_heading": "Recent visitors ({n} of last {max} unique IPs)",
        "col_ip": "IP",
        "col_first": "First seen (UTC)",
        "col_last": "Last seen (UTC)",
        "col_hits": "Requests",
        "col_ports": "Ports",
        "col_lastreq": "Last request",
        "no_visits": "No visits recorded yet.",
        "show_all": "All",
        "show_external": "External only",
        "show_inbound": "Inbound only",
        "scope_loopback": "loopback",
        "scope_private": "LAN",
        "col_dir": "Direction",
        "dir_in": "in",
        "dir_out": "out",
        "changelog": "Changelog",
        "changelog_missing": "CHANGELOG.md was not found next to the app, so there is nothing to show here.",
        "changelog_fallback": "The Chinese changelog is not available in this install; showing the English one.",
        "visitors_info": "Covers every device with a TCP connection to this host on any port — established, half-open or closing — sampled from the kernel every {sec}s, plus HTTP requests to this page. \"out\" marks connections this machine opened itself. TCP only: UDP (DNS, VPN, QUIC) and ICMP are not visible to this method, and connections that come and go between two samples can still be missed.",
        "visitors_info_http_only": "Connection tracking is off, so this only covers HTTP requests to this page.",
        "iperf": "iperf3",
        "iperf_heading": "iperf3 window",
        "iperf_minutes": "Minutes",
        "iperf_open": "Open window",
        "iperf_close": "Close now",
        "iperf_state_closed": "Closed. Nothing is listening on port {port}.",
        "iperf_state_open": "Open on port {port} — {mins}m {secs}s left.",
        "iperf_opened": "Window opened.",
        "iperf_extended": "Window extended.",
        "iperf_shut": "Window closed.",
        "iperf_disabled": "The iperf3 window is switched off in this install (VPSSRV_IPERF_ENABLE=0).",
        "iperf_missing": "iperf3 is not installed on this host. Install it with: apt install iperf3",
        "iperf_port_busy": "Port {port} is already in use, so iperf3 could not start.",
        "iperf_howto": "While the window is open, run this on the machine you want to test from:",
        "iperf_info": "The window always closes itself — there is no \"leave it running\" option, because an open iperf3 server lets anyone saturate this host's uplink. Latency is the mean_rtt field of the JSON output; add -u for jitter and packet loss, or -R to measure the other direction.",
        "probe_title": "Reachable",
        "probe_ok": "You reached this host.",
        "probe_your_ip": "Your address, as this server sees it",
        "probe_server_time": "Server time (UTC)",
        "probe_arrived_on": "You arrived on",
        "probe_note": "This page exists so that someone holding nothing but this IP can check whether its web ports answer. It reports nothing else about the host.",
        "probe_iperf": "An iperf3 test window is open on port {port} for another {mins}m {secs}s.",
        "not_found": "404 not found.",
    },
    "zh_cn": {
        "title": "vps-server",
        "login": "登录",
        "password": "密码",
        "wrong_password": "密码错误。",
        "logout": "退出登录",
        "dashboard": "仪表盘",
        "speedtest": "测速",
        "visitors": "最近访问者",
        "back": "返回",
        "your_ip": "服务器看到的你的 IP",
        "run_test": "开始测速",
        "running": "测速中…",
        "download": "下载",
        "upload": "上传",
        "latency": "延迟",
        "jitter": "抖动",
        "idle": "—",
        "waiting": "等待",
        "warmup": "预热中…",
        "measuring": "测量中…",
        "done": "完成",
        "test_info": "先通过 {pings} 次往返测量延迟，然后每个方向通过多条并行连接测约 {sec} 秒；每项前 {warm} 秒为预热，不计入结果。",
        "visitors_heading": "最近访问者（共 {n} 个，最多保留最近 {max} 个不同 IP）",
        "col_ip": "IP",
        "col_first": "首次访问（UTC）",
        "col_last": "最近访问（UTC）",
        "col_hits": "请求数",
        "col_ports": "端口",
        "col_lastreq": "最近一次请求",
        "no_visits": "暂无访问记录。",
        "show_all": "全部",
        "show_external": "仅外部",
        "show_inbound": "仅入站",
        "scope_loopback": "本机",
        "scope_private": "内网",
        "col_dir": "方向",
        "dir_in": "入",
        "dir_out": "出",
        "changelog": "更新日志",
        "changelog_missing": "应用目录下找不到 CHANGELOG.md，因此这里没有内容可显示。",
        "changelog_fallback": "此安装中没有简体中文更新日志，下面显示的是英文版。",
        "visitors_info": "涵盖与本机建立过 TCP 连接的所有设备，不限端口、不限连接状态（已建立、半开、关闭中，每 {sec} 秒从内核采样一次），以及访问本页面的 HTTP 请求。标「出」的是本机主动发起的连接。仅限 TCP：UDP（DNS、VPN、QUIC）和 ICMP 这种方式看不到；在两次采样之间来去的连接仍可能漏掉。",
        "visitors_info_http_only": "连接追踪已关闭，因此这里只包含访问本页面的 HTTP 请求。",
        "iperf": "iperf3",
        "iperf_heading": "iperf3 测试窗口",
        "iperf_minutes": "分钟",
        "iperf_open": "开启窗口",
        "iperf_close": "立即关闭",
        "iperf_state_closed": "已关闭，端口 {port} 上没有任何东西在监听。",
        "iperf_state_open": "已开启，端口 {port} —— 剩余 {mins} 分 {secs} 秒。",
        "iperf_opened": "窗口已开启。",
        "iperf_extended": "窗口已延长。",
        "iperf_shut": "窗口已关闭。",
        "iperf_disabled": "此次安装关闭了 iperf3 窗口（VPSSRV_IPERF_ENABLE=0）。",
        "iperf_missing": "本机没有安装 iperf3。用这条命令装：apt install iperf3",
        "iperf_port_busy": "端口 {port} 已被占用，iperf3 无法启动。",
        "iperf_howto": "窗口开启期间，在你想测试的那台机器上运行：",
        "iperf_info": "窗口一定会自己关闭，没有「一直开着」这个选项——开着的 iperf3 服务端意味着任何人都能跑满这台主机的上行带宽。延迟取 JSON 输出里的 mean_rtt 字段；加 -u 得到抖动和丢包，加 -R 测反方向。",
        "probe_title": "可以访问",
        "probe_ok": "你已经连到这台主机。",
        "probe_your_ip": "服务器看到的你的地址",
        "probe_server_time": "服务器时间（UTC）",
        "probe_arrived_on": "你到达的方式",
        "probe_note": "这个页面的用途只有一个：只拿到这个 IP 的人，可以自己确认它的网页端口通不通。除此之外不透露关于本机的任何信息。",
        "probe_iperf": "iperf3 测试窗口已开启，端口 {port}，还剩 {mins} 分 {secs} 秒。",
        "not_found": "404 未找到。",
    },
    "zh_tw": {
        "title": "vps-server",
        "login": "登入",
        "password": "密碼",
        "wrong_password": "密碼錯誤。",
        "logout": "登出",
        "dashboard": "儀表板",
        "speedtest": "測速",
        "visitors": "最近訪客",
        "back": "返回",
        "your_ip": "伺服器看到的你的 IP",
        "run_test": "開始測速",
        "running": "測速中…",
        "download": "下載",
        "upload": "上傳",
        "latency": "延遲",
        "jitter": "抖動",
        "idle": "—",
        "waiting": "等待",
        "warmup": "預熱中…",
        "measuring": "測量中…",
        "done": "完成",
        "test_info": "先透過 {pings} 次往返測量延遲，然後每個方向透過多條並行連線測約 {sec} 秒；每項前 {warm} 秒為預熱，不計入結果。",
        "visitors_heading": "最近訪客（共 {n} 個，最多保留最近 {max} 個不同 IP）",
        "col_ip": "IP",
        "col_first": "首次造訪（UTC）",
        "col_last": "最近造訪（UTC）",
        "col_hits": "請求數",
        "col_ports": "連接埠",
        "col_lastreq": "最近一次請求",
        "no_visits": "尚無造訪記錄。",
        "show_all": "全部",
        "show_external": "僅外部",
        "show_inbound": "僅入站",
        "scope_loopback": "本機",
        "scope_private": "內網",
        "col_dir": "方向",
        "dir_in": "入",
        "dir_out": "出",
        "changelog": "更新日誌",
        "changelog_missing": "應用程式目錄下找不到 CHANGELOG.md，因此這裡沒有內容可顯示。",
        "changelog_fallback": "此安裝中沒有繁體中文更新日誌，下面顯示的是英文版。",
        "visitors_info": "涵蓋與本機建立過 TCP 連線的所有裝置，不限連接埠、不限連線狀態（已建立、半開、關閉中，每 {sec} 秒從核心取樣一次），以及造訪本頁面的 HTTP 請求。標示「出」的是本機主動發起的連線。僅限 TCP：UDP（DNS、VPN、QUIC）和 ICMP 這種方式看不到；在兩次取樣之間往來的連線仍可能漏掉。",
        "visitors_info_http_only": "連線追蹤已關閉，因此這裡只包含造訪本頁面的 HTTP 請求。",
        "iperf": "iperf3",
        "iperf_heading": "iperf3 測試視窗",
        "iperf_minutes": "分鐘",
        "iperf_open": "開啟視窗",
        "iperf_close": "立即關閉",
        "iperf_state_closed": "已關閉，連接埠 {port} 上沒有任何東西在監聽。",
        "iperf_state_open": "已開啟，連接埠 {port} —— 剩餘 {mins} 分 {secs} 秒。",
        "iperf_opened": "視窗已開啟。",
        "iperf_extended": "視窗已延長。",
        "iperf_shut": "視窗已關閉。",
        "iperf_disabled": "此次安裝關閉了 iperf3 視窗（VPSSRV_IPERF_ENABLE=0）。",
        "iperf_missing": "本機沒有安裝 iperf3。用這條命令裝：apt install iperf3",
        "iperf_port_busy": "連接埠 {port} 已被占用，iperf3 無法啟動。",
        "iperf_howto": "視窗開啟期間，在你想測試的那台機器上執行：",
        "iperf_info": "視窗一定會自己關閉，沒有「一直開著」這個選項——開著的 iperf3 伺服端意味著任何人都能跑滿這台主機的上行頻寬。延遲取 JSON 輸出裡的 mean_rtt 欄位；加 -u 得到抖動和封包遺失，加 -R 測反方向。",
        "probe_title": "可以存取",
        "probe_ok": "你已經連到這台主機。",
        "probe_your_ip": "伺服器看到的你的位址",
        "probe_server_time": "伺服器時間（UTC）",
        "probe_arrived_on": "你到達的方式",
        "probe_note": "這個頁面的用途只有一個：只拿到這個 IP 的人，可以自己確認它的網頁連接埠通不通。除此之外不透露關於本機的任何資訊。",
        "probe_iperf": "iperf3 測試視窗已開啟，連接埠 {port}，還剩 {mins} 分 {secs} 秒。",
        "not_found": "404 找不到。",
    },
}

# Rendered next to each other in the nav as a 3-way switcher (see
# render_lang_switcher) — order here is display order.
LANG_NAMES = {"en": "English", "zh_cn": "简体中文", "zh_tw": "繁體中文"}

# Our internal codes (zh_cn/zh_tw, underscore, matching the project's own
# translated_<lang>/ doc convention) aren't valid BCP-47 <html lang> values —
# that needs a hyphen. Only used for the <html lang="..."> attribute.
HTML_LANG_TAGS = {"zh_cn": "zh-CN", "zh_tw": "zh-TW"}

# With no cookie/query/matching Accept-Language, fall back to this. Validated
# against STRINGS so a typo'd VPSSRV_DEFAULT_LANG can't 500 the whole app.
DEFAULT_LANG = os.environ.get("VPSSRV_DEFAULT_LANG", "en")
if DEFAULT_LANG not in STRINGS:
    DEFAULT_LANG = "en"


def pick_lang(cookie_lang, query_lang, accept_language):
    for candidate in (query_lang, cookie_lang):
        if candidate in STRINGS:
            return candidate
    if accept_language:
        # Only the first (highest-priority) tag matters here.
        primary = accept_language.split(",")[0].strip().lower()
        if primary.startswith("zh"):
            if any(tag in primary for tag in ("tw", "hant", "hk", "mo")):
                return "zh_tw"
            return "zh_cn"
    return DEFAULT_LANG


# ---------------------------------------------------------------------------
# Sessions — in memory; a restart forces re-login, acceptable for this tool.
# ---------------------------------------------------------------------------

_sessions = {}
_sessions_lock = threading.Lock()


def create_session():
    token = secrets.token_urlsafe(32)
    with _sessions_lock:
        _sessions[token] = time.time() + SESSION_TTL_SECONDS
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
            return False
        return True


def destroy_session(token):
    with _sessions_lock:
        _sessions.pop(token, None)


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
    if not observations:
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
            record_connections(observed_connections())
        except Exception as exc:  # never let the poller take the server down
            print(f"connection poller error: {exc}", file=sys.stderr)
        stop_event.wait(CONN_POLL_SECONDS)


init_db()

# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


def render_lang_switcher(lang):
    parts = []
    for code, name in LANG_NAMES.items():
        cls = "lang active" if code == lang else "lang"
        parts.append(f'<a class="{cls}" href="?lang={code}">{html.escape(name)}</a>')
    return "\n".join(parts)


def _inline_md(text):
    """Escape first, then re-introduce only `code` and **bold**.

    Everything is HTML-escaped before any markup is added, so nothing in
    CHANGELOG.md can inject markup into the page.
    """
    out = html.escape(text)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    return out


def render_changelog(markdown):
    """Render the CHANGELOG subset actually used: ##/### headings and - lists."""
    html_parts = []
    in_list = False
    in_item = False
    started = False  # skip the file's maintainer preamble before the first release

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
        if stripped.startswith("## "):
            started = True
            close_list()
            html_parts.append(f"<h2>{_inline_md(stripped[3:])}</h2>")
            continue
        if not started:
            # Notes to whoever maintains CHANGELOG.md are not release notes;
            # the person reading this page wants the versions.
            continue
        if stripped.startswith("### "):
            close_list()
            html_parts.append(f"<h3>{_inline_md(stripped[4:])}</h3>")
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


def render_page(title, body, lang, active=None, show_nav=True):
    t = STRINGS[lang]
    lang_switcher = render_lang_switcher(lang)
    version_tag = f'<a class="version" href="/changelog">v{VERSION}</a>'
    nav = ""
    if show_nav:
        def link(href, key):
            cls = ' class="active"' if active == key else ""
            return f'<a{cls} href="{href}">{html.escape(t[key])}</a>'

        # No session to end when auth is off — offering "Log out" would be a
        # link to nowhere (the route itself redirects to / in that mode).
        logout_link = (
            f'<a href="/logout">{html.escape(t["logout"])}</a>' if AUTH_ENABLED else ""
        )
        iperf_link = link('/iperf', 'iperf') if IPERF_ENABLED else ""
        nav = f"""
        <nav class="topnav">
          <div class="brandwrap">
            <a class="brand" href="/">{html.escape(t['title'])}</a>
            {version_tag}
          </div>
          <div class="navlinks">
            {link('/speedtest', 'speedtest')}
            {iperf_link}
            {link('/visitors', 'visitors')}
            {link('/changelog', 'changelog')}
            {logout_link}
            {lang_switcher}
          </div>
        </nav>
        """
    else:
        nav = f"""
        <nav class="topnav minimal">
          <div class="brandwrap">
            <span class="brand">{html.escape(t['title'])}</span>
            <span class="version">v{VERSION}</span>
          </div>
          <div class="navlinks">{lang_switcher}</div>
        </nav>
        """
    return f"""<!doctype html>
<html lang="{HTML_LANG_TAGS.get(lang, lang)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} — {html.escape(t['title'])}</title>
<link rel="icon" href="data:,">
<link rel="stylesheet" href="/static/style.css">
</head>
<body>
{nav}
<main>
{body}
</main>
</body>
</html>"""


CHANGELOG_PATHS = {
    "zh_cn": BASE_DIR / "translated_zh_cn" / "CHANGELOG_zh_cn.md",
    "zh_tw": BASE_DIR / "translated_zh_tw" / "CHANGELOG_zh_tw.md",
}

STATIC_FILES = {
    "/static/style.css": ("text/css", BASE_DIR / "static" / "style.css"),
    "/static/speedtest.js": ("application/javascript", BASE_DIR / "static" / "speedtest.js"),
    "/static/speedtest-ui.js": ("application/javascript", BASE_DIR / "static" / "speedtest-ui.js"),
    "/static/visitors.js": ("application/javascript", BASE_DIR / "static" / "visitors.js"),
    # speedtest.js spawns `new Worker("speedtest_worker.js?r=...")`. That call
    # runs in the *page's* context, so the browser resolves it relative to the
    # page URL (/speedtest), not relative to /static/speedtest.js — it lands
    # on /speedtest_worker.js, not /static/speedtest_worker.js. Serving it at
    # both paths sidesteps relying on that resolution quirk.
    "/speedtest_worker.js": ("application/javascript", BASE_DIR / "static" / "speedtest_worker.js"),
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

    def send_response(self, code, message=None):
        self._last_status = code
        super().send_response(code, message)

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
        return session_valid(self.get_cookie("session"))

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
        try:
            self._route(method, path, parsed)
        except (BrokenPipeError, ConnectionResetError):
            self._last_status = 0  # client disconnected mid-stream, not a real outcome
        except Exception:
            self._last_status = 500
            try:
                self.send_json(500, {"error": "internal server error"})
            except Exception:
                pass
        finally:
            if self._last_status:
                log_visit(self.client_ip(), method, path, self._last_status)

    def _route(self, method, path, parsed):
        if path.startswith("/static/") or path == "/speedtest_worker.js":
            return self.serve_static(path)

        lang, query_lang = self.resolve_lang(parsed)

        # With auth off there is nothing to log in or out of: a login form
        # that accepts nothing and a logout link that ends no session are
        # both dead ends, so send those paths back to the dashboard.
        if path in ("/login", "/logout") and not AUTH_ENABLED:
            return self.redirect("/")

        if method == "GET" and path == "/login":
            return self.page_login(lang, query_lang)
        if method == "POST" and path == "/login":
            return self.handle_login(lang)
        if method == "GET" and path == "/logout":
            return self.handle_logout()

        if not self.is_authenticated():
            return self.redirect("/login")

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
        if method == "GET" and path == "/iperf":
            return self.page_iperf(lang, query_lang)
        if method == "POST" and path == "/iperf/open":
            return self.handle_iperf_open()
        if method == "POST" and path == "/iperf/close":
            return self.handle_iperf_close()
        if method == "GET" and path == "/visitors":
            return self.page_visitors(lang, query_lang)
        if method == "GET" and path == "/changelog":
            return self.page_changelog(lang, query_lang)

        self.send_html(404, render_page(STRINGS[lang]["not_found"],
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

    def page_login(self, lang, query_lang, status=200, error=None):
        t = STRINGS[lang]
        error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
        body = f"""
        <div class="card narrow">
          <h1>{html.escape(t['login'])}</h1>
          {error_html}
          <form method="post" action="/login">
            <label>{html.escape(t['password'])}
              <input type="password" name="password" autocomplete="current-password" autofocus required>
            </label>
            <button type="submit">{html.escape(t['login'])}</button>
          </form>
        </div>
        """
        headers = self.maybe_lang_cookie(query_lang)
        self.send_html(status, render_page(t['login'], body, lang, show_nav=False), headers)

    def handle_login(self, lang):
        raw = self.read_body(LOGIN_BODY_LIMIT)
        form = parse_qs(raw.decode("utf-8", errors="replace"))
        submitted = form.get("password", [""])[0]
        if hmac.compare_digest(submitted, ADMIN_PASSWORD):
            token = create_session()
            cookie = (
                f"session={token}; Path=/; HttpOnly; SameSite=Strict; "
                f"Max-Age={SESSION_TTL_SECONDS}"
            )
            return self.redirect("/", {"Set-Cookie": cookie})
        self.page_login(lang, None, status=401, error=STRINGS[lang]["wrong_password"])

    def handle_logout(self):
        token = self.get_cookie("session")
        if token:
            destroy_session(token)
        cookie = "session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
        self.redirect("/login", {"Set-Cookie": cookie})

    # -- dashboard ---------------------------------------------------------

    def page_dashboard(self, lang, query_lang):
        t = STRINGS[lang]
        iperf_tile = ""
        if IPERF_ENABLED:
            is_open, _ = IPERF_WINDOW.state()
            iperf_tile = f"""
            <a class="tile" href="/iperf">
              <span class="tile-icon">{'🟢' if is_open else '📡'}</span>
              <span class="tile-label">{html.escape(t['iperf'])}</span>
            </a>
            """
        body = f"""
        <div class="card">
          <h1>{html.escape(t['dashboard'])}</h1>
          <div class="tiles">
            <a class="tile" href="/speedtest">
              <span class="tile-icon">⚡</span>
              <span class="tile-label">{html.escape(t['speedtest'])}</span>
            </a>
            {iperf_tile}
            <a class="tile" href="/visitors">
              <span class="tile-icon">📋</span>
              <span class="tile-label">{html.escape(t['visitors'])}</span>
            </a>
          </div>
        </div>
        """
        self.send_html(200, render_page(t['dashboard'], body, lang, active=None),
                       self.maybe_lang_cookie(query_lang))

    # -- speed test ----------------------------------------------------

    def page_speedtest(self, lang, query_lang):
        t = STRINGS[lang]
        ip = html.escape(self.client_ip())
        config = {
            # Maps onto LibreSpeed's own Settings keys — see DECISIONS.md
            # (2026-08-25, "Vendor LibreSpeed's official test engine").
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
        info = t["test_info"].format(sec=TEST_SECONDS, warm=int(WARMUP_SECONDS),
                                     pings=PING_SAMPLES)
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
          <p class="muted small">{html.escape(info)}</p>
        </div>
        <script id="speedtest-config" type="application/json">{json.dumps(config)}</script>
        <script id="speedtest-i18n" type="application/json">{json.dumps(i18n)}</script>
        <script src="/static/speedtest.js"></script>
        <script src="/static/speedtest-ui.js"></script>
        """
        self.send_html(200, render_page(t['speedtest'], body, lang, active="speedtest"),
                       self.maybe_lang_cookie(query_lang))

    # These three implement LibreSpeed's own client/server contract exactly
    # (garbage.php / empty.php / getIP.php equivalents) rather than a
    # hand-rolled protocol — see DECISIONS.md (2026-08-25). Header set and
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
        # DECISIONS.md, "Zero third-party runtime dependencies").
        self.send_json(200, {"processedString": self.client_ip(), "rawIspInfo": ""})

    # -- iperf3 window -------------------------------------------------

    def page_iperf(self, lang, query_lang):
        t = STRINGS[lang]
        port = IPERF_WINDOW.port
        is_open, remaining = IPERF_WINDOW.state()

        notice = ""
        key = parse_qs(urlsplit(self.path).query).get("msg", [""])[0]
        if key in IPERF_MESSAGE_KEYS:
            notice = f'<p class="notice">{html.escape(t[key].format(port=port))}</p>'

        if is_open:
            state = t["iperf_state_open"].format(
                port=port, mins=remaining // 60, secs=remaining % 60
            )
            close_form = f"""
            <form method="post" action="/iperf/close">
              <button type="submit" class="danger">{html.escape(t['iperf_close'])}</button>
            </form>
            """
        else:
            state = t["iperf_state_closed"].format(port=port)
            close_form = ""

        # The Host header is what the operator actually typed to get here, so
        # it is the address their tester should aim at too. It is only echoed
        # into a command example, and it is escaped.
        host = (self.headers.get("Host") or "").split(":")[0] or "<server-ip>"
        command = f"iperf3 -c {host} -p {port} --json"

        body = f"""
        <div class="card">
          <h1>{html.escape(t['iperf_heading'])}</h1>
          {notice}
          <p class="iperf-state {'is-open' if is_open else 'is-closed'}">{html.escape(state)}</p>
          <form method="post" action="/iperf/open" class="inline-form">
            <label>{html.escape(t['iperf_minutes'])}
              <input type="number" name="minutes" min="1" max="{IPERF_MAX_MINUTES}"
                     value="{IPERF_DEFAULT_MINUTES}" required>
            </label>
            <button type="submit">{html.escape(t['iperf_open'])}</button>
          </form>
          {close_form}
          <p class="muted">{html.escape(t['iperf_howto'])}</p>
          <pre class="cmd">{html.escape(command)}</pre>
          <p class="muted small">{html.escape(t['iperf_info'])}</p>
        </div>
        """
        self.send_html(200, render_page(t['iperf_heading'], body, lang, active="iperf"),
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

    # -- visitor log ---------------------------------------------------

    def page_changelog(self, lang, query_lang):
        t = STRINGS[lang]
        # Follow the UI language. If the translation is missing (it lags the
        # English file between releases), fall back rather than show nothing —
        # but say which file is actually on screen.
        localized = CHANGELOG_PATHS.get(lang)
        path = localized if localized and localized.exists() else BASE_DIR / "CHANGELOG.md"
        notice = ""
        if localized and path != localized:
            notice = f'<p class="muted small">{html.escape(t["changelog_fallback"])}</p>'

        if path.exists():
            content = notice + render_changelog(path.read_text(encoding="utf-8"))
        else:
            # Shipped installs might not carry the file; say so rather than
            # rendering a blank page that looks like "no changes ever".
            content = f'<p class="muted">{html.escape(t["changelog_missing"])}</p>'
        body = f"""
        <div class="card wide">
          <h1>{html.escape(t['changelog'])} <span class="version-inline">v{VERSION}</span></h1>
          <div class="changelog">
          {content}
          </div>
        </div>
        """
        self.send_html(200, render_page(t['changelog'], body, lang, active="changelog"),
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
        info = (
            t["visitors_info"].format(sec=f"{CONN_POLL_SECONDS:g}")
            if TRACK_CONNECTIONS
            else t["visitors_info_http_only"]
        )
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
          <p class="muted small">{html.escape(info)}</p>
        </div>
        <script src="/static/visitors.js"></script>
        """
        self.send_html(200, render_page(t['visitors'], body, lang, active="visitors"),
                       self.maybe_lang_cookie(query_lang))


# ---------------------------------------------------------------------------
# Public reachability page
#
# Two paths, two methods, no session, no query string, no request body. That
# narrowness *is* the security boundary: a request arriving on 80 or 443
# cannot reach a console route because no such route exists on this class.
# Read DECISIONS.md (2026-09-12) before adding anything here.
#
# The stylesheet is inlined rather than served from /static/, so this listener
# has no file-serving route at all.
# ---------------------------------------------------------------------------

PROBE_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; display: flex; align-items: center;
       justify-content: center; padding: 1.5rem;
       font: 16px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
       background: #f4f6f8; color: #1a1d21; }
main { width: 100%; max-width: 34rem; background: #fff; border-radius: 14px;
       padding: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,.12); }
h1 { margin: 0 0 .25rem; font-size: 1.5rem; display: flex; gap: .5rem;
     align-items: center; }
.ok { color: #0a7d32; }
dl { display: grid; grid-template-columns: auto 1fr; gap: .4rem 1rem;
     margin: 1.5rem 0 0; }
dt { color: #5a6570; }
dd { margin: 0; font-variant-numeric: tabular-nums; word-break: break-all; }
.note { margin: 1.5rem 0 0; font-size: .85rem; color: #5a6570; }
.iperf { margin: 1.25rem 0 0; padding: .75rem 1rem; border-radius: 8px;
         background: #e7f6ec; color: #0a5d27; font-size: .9rem; }
@media (prefers-color-scheme: dark) {
  body { background: #15181c; color: #e6e9ec; }
  main { background: #1e2227; box-shadow: none; }
  dt, .note { color: #9aa4ae; }
  .ok { color: #4ade80; }
  .iperf { background: #16301f; color: #86efac; }
}
"""


class ProbeHandler(BaseHTTPRequestHandler):
    """The unauthenticated page on 80 and 443."""

    # No version string: whoever scans this port learns that something
    # answered, which is the entire point, and nothing more.
    server_version = "vps-server"
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass  # requests go to the visitor log instead

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
                self._send(204, b"", "image/x-icon", send_body)
            else:
                self._send(404, b"not found\n", "text/plain; charset=utf-8", send_body)
        except (BrokenPipeError, ConnectionResetError):
            self._last_status = 0  # client hung up; not a real outcome
        finally:
            if self._last_status:
                log_visit(self.client_ip(), self.command, path, self._last_status)

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
<html lang="{HTML_LANG_TAGS.get(lang, lang)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(t['probe_title'])}</title>
<link rel="icon" href="data:,">
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
            print(
                f"Public port {port} is also the console port; "
                "skipping that public listener.",
                file=sys.stderr,
            )
            continue
        try:
            server = make_server(port, ProbeHandler, tls)
        except (OSError, SystemExit) as exc:
            print(
                f"Could not bind public port {port} ({exc}); continuing without it. "
                "Something else may already hold it — check `ss -lntp`.",
                file=sys.stderr,
            )
            continue
        servers.append(server)
        serve_forever_in_thread(server)
        print(
            f"Reachability page on {'https' if tls else 'http'}://{HOST}:{port}",
            file=sys.stderr,
        )


def main():
    servers = []
    stop_event = threading.Event()

    console = make_server(CONSOLE_PORT, ConsoleHandler, CONSOLE_TLS)
    servers.append(console)
    print(
        f"Console on {'https' if CONSOLE_TLS else 'http'}://{HOST}:{CONSOLE_PORT}",
        file=sys.stderr,
    )

    if PUBLIC_ENABLED:
        start_public_listeners(servers)

    if TRACK_CONNECTIONS:
        if os.path.exists("/proc/net/tcp"):
            threading.Thread(
                target=connection_poller, args=(stop_event,), daemon=True
            ).start()
            print(
                f"Tracking inbound connections from the kernel TCP table "
                f"every {CONN_POLL_SECONDS:g}s",
                file=sys.stderr,
            )
        else:
            print(
                "VPSSRV_TRACK_CONNECTIONS=1 but /proc/net/tcp is unavailable; "
                "the visitor log will only cover requests to this web app.",
                file=sys.stderr,
            )

    if IPERF_ENABLED and not shutil.which("iperf3"):
        print(
            "VPSSRV_IPERF_ENABLE=1 but iperf3 is not installed; the console "
            "will say so when a window is requested (apt install iperf3).",
            file=sys.stderr,
        )

    # An open window is a live child process plus a firewall rule. systemd
    # sends SIGTERM on stop and restart; without this the iperf3 child would
    # outlive the service and the rule would be left behind.
    def request_shutdown(signum, frame):
        raise KeyboardInterrupt

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, request_shutdown)
        except ValueError:
            pass  # not on the main thread; the tests import this module

    try:
        console.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        IPERF_WINDOW.close()
        for s in servers:
            s.server_close()


if __name__ == "__main__":
    main()
