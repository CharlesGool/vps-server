"""Security audit log, remembered login addresses and Bark alerts.

All three keep small private files in the data directory. Nothing here
decides whether a request is allowed; the console records what happened and
optionally pushes a notification for logins from a new address and bans.
"""

import hashlib
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

import secure_store


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
        line = secure_store.seal_line(json.dumps(entry, ensure_ascii=False), self.path.name) + "\n"
        with self.lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                with os.fdopen(fd, "a", encoding="utf-8") as output:
                    output.write(line)
                if self.path.stat().st_size > self.limit * 700:
                    lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
                    if len(lines) > self.limit:
                        _atomic_write(self.path, "".join(lines[-self.limit:]))
            except (OSError, ValueError):
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
                entry = json.loads(secure_store.open_line(line, self.path.name))
            except ValueError:     # damaged record, or one this host's key cannot open
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
            document = json.loads(secure_store.read_text(self.path))
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
                secure_store.write_text(self.path, json.dumps(self.entries) + "\n")
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
                secure_store.write_text(self.path, "{}\n")
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
    """Push notifications through a Bark server (https://bark.day.app) to one or more device keys.

    Settings are ``{"server", "keys", "new_ip", "ban"}``; files written before several keys
    were possible hold a single ``"key"`` and still load. Every message goes to every key.
    """

    SETTINGS = ("server", "keys", "new_ip", "ban")
    OLD_SETTINGS = ("server", "key", "new_ip", "ban")
    MAX_KEYS = 10
    REPEAT_SECONDS = 3600

    def __init__(self, path, log=None):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.log = log or (lambda message: None)
        self.server = DEFAULT_BARK_SERVER
        self.keys = []
        self.new_ip = True
        self.ban = True
        self.load_error = False
        self._last_sent = {}
        if self.path.exists():
            try:
                document = json.loads(secure_store.read_text(self.path))
                if isinstance(document, dict) and set(document) == set(self.OLD_SETTINGS):
                    document = {**document, "keys": [document["key"]] if document["key"] else []}
                    del document["key"]
                if (not isinstance(document, dict) or set(document) != set(self.SETTINGS) or
                        not valid_bark_server(document["server"]) or
                        not isinstance(document["keys"], list) or len(document["keys"]) > self.MAX_KEYS or
                        any(not isinstance(key, str) or not BARK_KEY_RE.fullmatch(key) for key in document["keys"]) or
                        not isinstance(document["new_ip"], bool) or not isinstance(document["ban"], bool)):
                    raise ValueError("invalid alert settings")
                self.server, self.keys = document["server"], list(dict.fromkeys(document["keys"]))
                self.new_ip, self.ban = document["new_ip"], document["ban"]
            except (OSError, ValueError, TypeError, KeyError):
                self.load_error = True

    @staticmethod
    def key_id(key):
        """A stable handle for one key that does not reveal it."""
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def masked(key):
        """Enough of a key to tell several apart: the first and last four characters."""
        return f"{key[:4]}****{key[-4:]}" if len(key) >= 12 else f"{key[:2]}****"

    def configured(self):
        with self.lock:
            return bool(self.keys)

    def settings(self):
        with self.lock:
            return {"server": self.server, "configured": bool(self.keys),
                    "keys": [{"id": self.key_id(key), "masked": self.masked(key)} for key in self.keys],
                    "new_ip": self.new_ip, "ban": self.ban}

    def _save(self, server, keys, new_ip, ban):
        document = {"server": server, "keys": keys, "new_ip": bool(new_ip), "ban": bool(ban)}
        secure_store.write_text(self.path, json.dumps(document) + "\n")
        self.server, self.keys, self.new_ip, self.ban = server, keys, bool(new_ip), bool(ban)
        self.load_error = False

    def update(self, *, server, key="", new_ip, ban, clear_key=False):
        """Save settings. A non-empty ``key`` is added to the keys; ``clear_key`` removes them all."""
        server = server.strip().rstrip("/") or DEFAULT_BARK_SERVER
        key = key.strip()
        if not valid_bark_server(server) or (key and not BARK_KEY_RE.fullmatch(key)):
            raise ValueError("invalid alert settings")
        with self.lock:
            keys = [] if clear_key else list(self.keys)
            if key and key not in keys:
                if len(keys) >= self.MAX_KEYS:
                    raise ValueError("too many keys")
                keys.append(key)
            self._save(server, keys, new_ip, ban)

    def add_key(self, key):
        key = key.strip() if isinstance(key, str) else ""
        if not BARK_KEY_RE.fullmatch(key):
            raise ValueError("invalid key")
        with self.lock:
            if key in self.keys:
                return False
            if len(self.keys) >= self.MAX_KEYS:
                raise ValueError("too many keys")
            self._save(self.server, [*self.keys, key], self.new_ip, self.ban)
            return True

    def remove_key(self, identifier):
        """Remove the key with this id; False when there is none."""
        with self.lock:
            keys = [key for key in self.keys if self.key_id(key) != identifier]
            if len(keys) == len(self.keys):
                return False
            self._save(self.server, keys, self.new_ip, self.ban)
            return True

    def _post(self, server, key, title, body):
        data = json.dumps({"title": title[:60], "body": body[:200], "group": "vps-server"},
                          ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(f"{server}/{urllib.parse.quote(key, safe='')}", data=data,
                                         headers={"Content-Type": "application/json; charset=utf-8",
                                                  "User-Agent": "vps-server"})
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read(4096)

    def _post_all(self, server, keys, title, body):
        """Send to every key; return the first error's name, or None when all were sent."""
        error = None
        for key in keys:
            try:
                self._post(server, key, title, body)
            except (OSError, ValueError, urllib.error.URLError) as exc:
                error = error or type(exc).__name__
        return error

    def send_test(self, title, body):
        """Send synchronously to every key; return None or a short error description."""
        with self.lock:
            server, keys = self.server, list(self.keys)
        if not keys:
            return "not configured"
        return self._post_all(server, keys, title, body)

    def notify_task(self, title, body):
        """A scheduled job failed: send when a Bark key is set, whatever the other switches say."""
        with self.lock:
            server, keys = self.server, list(self.keys)
        if not keys:
            return False

        def run():
            error = self._post_all(server, keys, title, body)
            if error:
                self.log(error)

        threading.Thread(target=run, daemon=True).start()
        return True

    def notify(self, kind, title, body, dedupe=""):
        """Send in the background if ``kind`` ("new_ip" or "ban") is on."""
        with self.lock:
            if not self.keys or not getattr(self, kind, False):
                return False
            now = time.time()
            marker = (kind, dedupe)
            if dedupe and now - self._last_sent.get(marker, 0) < self.REPEAT_SECONDS:
                return False
            self._last_sent[marker] = now
            if len(self._last_sent) > 500:
                self._last_sent = {k: v for k, v in self._last_sent.items() if now - v < self.REPEAT_SECONDS}
            server, keys = self.server, list(self.keys)

        def run():
            error = self._post_all(server, keys, title, body)
            if error:
                self.log(error)

        threading.Thread(target=run, daemon=True).start()
        return True
