"""Security audit log, remembered login addresses and Bark alerts.

All three keep small private files in the data directory. Nothing here
decides whether a request is allowed; the console records what happened and
optionally pushes a notification for logins from a new address and bans.
"""

import json
import os
import re
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def _atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".security-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


class AuditLog:
    """Append-only JSON lines, trimmed to the newest ``limit`` entries."""

    def __init__(self, path, limit=500):
        self.path = Path(path)
        self.limit = limit
        self.lock = threading.Lock()

    def record(self, event, ip="", detail=""):
        entry = {"t": round(time.time(), 3), "event": str(event), "ip": str(ip or ""),
                 "detail": str(detail or "")[:200]}
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with self.lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                with os.fdopen(fd, "a", encoding="utf-8") as output:
                    output.write(line)
                if self.path.stat().st_size > self.limit * 400:
                    lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
                    if len(lines) > self.limit:
                        _atomic_write(self.path, "".join(lines[-self.limit:]))
            except OSError:
                pass

    def recent(self, count=50):
        with self.lock:
            try:
                lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                return []
        entries = []
        for line in reversed(lines):
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict) and isinstance(entry.get("event"), str):
                entries.append(entry)
            if len(entries) >= count:
                break
        return entries

    def clear(self):
        with self.lock:
            try:
                _atomic_write(self.path, "")
            except OSError:
                pass


class KnownLogins:
    """Source keys (IPv4, or IPv6 /64) that have logged in successfully."""

    LIMIT = 200
    EXPIRE_SECONDS = 90 * 24 * 3600

    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.entries = {}
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(document, dict):
                self.entries = {key: value for key, value in document.items()
                                if isinstance(key, str) and isinstance(value, (int, float))}
        except (OSError, ValueError):
            pass

    def is_known(self, key):
        with self.lock:
            seen = self.entries.get(key)
            return seen is not None and time.time() - seen < self.EXPIRE_SECONDS

    def remember(self, key):
        """Record a successful login; return True if the key was new."""
        with self.lock:
            now = time.time()
            seen = self.entries.get(key)
            new = seen is None or now - seen >= self.EXPIRE_SECONDS
            self.entries[key] = now
            self.entries = {k: v for k, v in self.entries.items() if now - v < self.EXPIRE_SECONDS}
            if len(self.entries) > self.LIMIT:
                keep = sorted(self.entries, key=self.entries.get, reverse=True)[:self.LIMIT]
                self.entries = {k: self.entries[k] for k in keep}
            try:
                _atomic_write(self.path, json.dumps(self.entries) + "\n")
            except OSError:
                pass
            return new

    def count(self):
        with self.lock:
            return len(self.entries)

    def clear(self):
        with self.lock:
            self.entries = {}
            try:
                _atomic_write(self.path, "{}\n")
            except OSError:
                pass


BARK_KEY_RE = re.compile(r"[A-Za-z0-9_-]{1,128}")
DEFAULT_BARK_SERVER = "https://api.day.app"


def valid_bark_server(value):
    try:
        parts = urllib.parse.urlsplit(value)
    except ValueError:
        return False
    return (parts.scheme in ("https", "http") and bool(parts.hostname) and not parts.query
            and not parts.fragment and not parts.username and not parts.password and len(value) <= 200)


class BarkAlerts:
    """Push notifications through a Bark server (https://bark.day.app)."""

    SETTINGS = ("server", "key", "new_ip", "ban")
    REPEAT_SECONDS = 3600

    def __init__(self, path, log=None):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.log = log or (lambda message: None)
        self.server = DEFAULT_BARK_SERVER
        self.key = ""
        self.new_ip = True
        self.ban = True
        self.load_error = False
        self._last_sent = {}
        if self.path.exists():
            try:
                document = json.loads(self.path.read_text(encoding="utf-8"))
                if (not isinstance(document, dict) or set(document) != set(self.SETTINGS) or
                        not valid_bark_server(document["server"]) or
                        not (document["key"] == "" or BARK_KEY_RE.fullmatch(document["key"])) or
                        not isinstance(document["new_ip"], bool) or not isinstance(document["ban"], bool)):
                    raise ValueError("invalid alert settings")
                self.server, self.key = document["server"], document["key"]
                self.new_ip, self.ban = document["new_ip"], document["ban"]
            except (OSError, ValueError, TypeError, KeyError):
                self.load_error = True

    def configured(self):
        with self.lock:
            return bool(self.key)

    def settings(self):
        with self.lock:
            return {"server": self.server, "configured": bool(self.key),
                    "new_ip": self.new_ip, "ban": self.ban}

    def update(self, *, server, key, new_ip, ban, clear_key=False):
        """Save settings. An empty ``key`` keeps the stored one."""
        server = server.strip().rstrip("/") or DEFAULT_BARK_SERVER
        key = key.strip()
        if not valid_bark_server(server) or (key and not BARK_KEY_RE.fullmatch(key)):
            raise ValueError("invalid alert settings")
        with self.lock:
            stored = "" if clear_key else (key or self.key)
            document = {"server": server, "key": stored, "new_ip": bool(new_ip), "ban": bool(ban)}
            _atomic_write(self.path, json.dumps(document) + "\n")
            self.server, self.key, self.new_ip, self.ban = server, stored, bool(new_ip), bool(ban)
            self.load_error = False

    def _post(self, server, key, title, body):
        data = json.dumps({"title": title[:60], "body": body[:200], "group": "vps-server"},
                          ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(f"{server}/{urllib.parse.quote(key, safe='')}", data=data,
                                         headers={"Content-Type": "application/json; charset=utf-8",
                                                  "User-Agent": "vps-server"})
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read(4096)

    def send_test(self, title, body):
        """Send synchronously; return None or a short error description."""
        with self.lock:
            server, key = self.server, self.key
        if not key:
            return "not configured"
        try:
            self._post(server, key, title, body)
            return None
        except (OSError, ValueError, urllib.error.URLError) as exc:
            return type(exc).__name__

    def notify(self, kind, title, body, dedupe=""):
        """Send in the background if ``kind`` ("new_ip" or "ban") is on."""
        with self.lock:
            if not self.key or not getattr(self, kind, False):
                return False
            now = time.time()
            marker = (kind, dedupe)
            if dedupe and now - self._last_sent.get(marker, 0) < self.REPEAT_SECONDS:
                return False
            self._last_sent[marker] = now
            if len(self._last_sent) > 500:
                self._last_sent = {k: v for k, v in self._last_sent.items() if now - v < self.REPEAT_SECONDS}
            server, key = self.server, self.key

        def run():
            try:
                self._post(server, key, title, body)
            except (OSError, ValueError, urllib.error.URLError) as exc:
                self.log(type(exc).__name__)

        threading.Thread(target=run, daemon=True).start()
        return True
