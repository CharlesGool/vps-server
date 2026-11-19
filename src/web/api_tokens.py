"""API tokens for scripts and other consoles (``Authorization: Bearer <token>``).

Only a token's SHA-256 is stored (``data/api-tokens.json``, encrypted when the
host has a data key); the token itself is shown once when it is made. Each
token is ``read`` (status only) or ``write`` (also restarts services, starts
upgrades and backups).
"""

import hashlib
import json
import secrets
import threading
import time
from pathlib import Path

try:
    from . import secure_store
except ImportError:  # Installed helpers are copied into one flat directory.
    import secure_store

PREFIX = "vpss_"
LIMIT = 20
SCOPES = ("read", "write")
TOUCH_SECONDS = 60


def _digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TokenError(ValueError):
    """A request the token store refuses; the message is the error code."""


class ApiTokens:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()

    def _load(self):
        try:
            data = json.loads(secure_store.read_text(self.path))
        except FileNotFoundError:
            return []
        rows = data.get("tokens") if isinstance(data, dict) else None
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    def _save(self, rows):
        secure_store.write_text(self.path, json.dumps({"tokens": rows}, ensure_ascii=False, indent=2))

    def listing(self):
        with self.lock:
            return [{key: row.get(key) for key in ("id", "name", "scope", "created", "lastUsed", "lastIp", "hint")}
                    for row in self._load()]

    def create(self, name, scope):
        name = name.strip() if isinstance(name, str) else ""
        if not 1 <= len(name) <= 40:
            raise TokenError("name_invalid")
        if scope not in SCOPES:
            raise TokenError("invalid_request")
        token = PREFIX + secrets.token_urlsafe(32)
        with self.lock:
            rows = self._load()
            if len(rows) >= LIMIT:
                raise TokenError("too_many")
            row = {"id": secrets.token_hex(6), "name": name, "scope": scope, "hash": _digest(token),
                   "hint": token[:9] + "…" + token[-4:], "created": int(time.time()), "lastUsed": None,
                   "lastIp": None}
            rows.append(row)
            self._save(rows)
        return token, {key: row[key] for key in ("id", "name", "scope", "created", "lastUsed", "lastIp", "hint")}

    def delete(self, token_id):
        with self.lock:
            rows = self._load()
            kept = [row for row in rows if row.get("id") != token_id]
            if len(kept) == len(rows):
                raise TokenError("not_found")
            self._save(kept)

    def verify(self, token, ip):
        """The token's entry when it is valid, else None; records when and from where it was used."""
        if not isinstance(token, str) or not token.startswith(PREFIX) or len(token) > 200:
            return None
        digest = _digest(token)
        with self.lock:
            try:
                rows = self._load()
            except (OSError, ValueError):
                return None
            match = next((row for row in rows if secrets.compare_digest(row.get("hash", ""), digest)), None)
            if match is None:
                return None
            now = int(time.time())
            if not match.get("lastUsed") or now - match["lastUsed"] >= TOUCH_SECONDS or match.get("lastIp") != ip:
                match["lastUsed"], match["lastIp"] = now, ip
                try:
                    self._save(rows)
                except (OSError, ValueError):
                    pass
            return dict(match)
