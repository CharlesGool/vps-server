"""Other vps-server consoles this one watches through their token API (the fleet overview).

Each host is saved with its address, an API token (encrypted with the rest of
``data/fleet.json`` when the host has a data key) and how its TLS certificate
is checked: ``ca`` when the certificate was publicly valid when the host was
added (a domain or an IP certificate; it may renew), else ``pin``, the
SHA-256 of the certificate seen then (the console's own self-signed one).
The certificate is checked before the token is sent.
"""

import hashlib
import http.client
import json
import re
import secrets
import socket
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

try:
    from . import secure_store
except ImportError:  # Installed helpers are copied into one flat directory.
    import secure_store

LIMIT = 50
TIMEOUT = 8
CACHE_SECONDS = 15
URL_RE = re.compile(r"^https://(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9.-]{1,253}):(\d{1,5})/?$")


class FleetError(ValueError):
    """A request the fleet refuses; the message is the error code."""


def parse_url(url):
    match = URL_RE.match(url.strip()) if isinstance(url, str) else None
    if not match or not 1 <= int(match.group(2)) <= 65535:
        raise FleetError("url_invalid")
    host = match.group(1).strip("[]")
    return host, int(match.group(2))


def fingerprint_of(der):
    digest = hashlib.sha256(der).hexdigest().upper()
    return ":".join(digest[index:index + 2] for index in range(0, len(digest), 2))


def probe(url):
    """How the certificate at ``url`` can be checked: {"mode", "fingerprint", "subject"}."""
    host, port = parse_url(url)
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT) as raw:
            with ssl.create_default_context().wrap_socket(raw, server_hostname=host) as tls:
                der = tls.getpeercert(binary_form=True)
                return {"mode": "ca", "fingerprint": fingerprint_of(der)}
    except ssl.SSLCertVerificationError:
        pass
    except (OSError, ssl.SSLError):
        raise FleetError("unreachable") from None
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT) as raw:
            with context.wrap_socket(raw, server_hostname=host) as tls:
                return {"mode": "pin", "fingerprint": fingerprint_of(tls.getpeercert(binary_form=True))}
    except (OSError, ssl.SSLError):
        raise FleetError("unreachable") from None


def call(entry, method, path, body=None):
    """One token API request to ``entry``; (status, JSON body). Raises FleetError."""
    host, port = parse_url(entry["url"])
    if entry.get("mode") == "ca":
        context = ssl.create_default_context()
    else:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    connection = http.client.HTTPSConnection(host, port, timeout=TIMEOUT, context=context)
    try:
        try:
            connection.connect()
        except ssl.SSLCertVerificationError:
            raise FleetError("certificate_changed") from None
        if entry.get("mode") != "ca":
            seen = fingerprint_of(connection.sock.getpeercert(binary_form=True))
            if not secrets.compare_digest(seen, entry.get("fingerprint", "")):
                raise FleetError("certificate_changed")
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Authorization": "Bearer " + entry["token"], "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        connection.request(method, "/api/v1/" + path, body=data, headers=headers)
        response = connection.getresponse()
        raw = response.read(1 << 20)
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except ValueError:
            payload = {}
        return response.status, payload
    except (OSError, ssl.SSLError, http.client.HTTPException):
        raise FleetError("unreachable") from None
    finally:
        connection.close()


class Fleet:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.cache = {}

    def _load(self):
        try:
            data = json.loads(secure_store.read_text(self.path))
        except FileNotFoundError:
            return []
        rows = data.get("hosts") if isinstance(data, dict) else None
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    def _save(self, rows):
        secure_store.write_text(self.path, json.dumps({"hosts": rows}, ensure_ascii=False, indent=2))

    def hosts(self):
        with self.lock:
            return self._load()

    @staticmethod
    def public(row):
        return {key: row.get(key) for key in ("id", "name", "url", "mode", "fingerprint", "added")}

    def add(self, name, url, token, mode, fingerprint):
        name = name.strip() if isinstance(name, str) else ""
        if not 1 <= len(name) <= 40:
            raise FleetError("name_invalid")
        parse_url(url)
        if not isinstance(token, str) or not token.startswith("vpss_") or len(token) > 200:
            raise FleetError("token_invalid")
        if mode not in ("ca", "pin") or not isinstance(fingerprint, str) or len(fingerprint) != 95:
            raise FleetError("invalid_request")
        row = {"id": secrets.token_hex(6), "name": name, "url": url.strip().rstrip("/"), "token": token,
               "mode": mode, "fingerprint": fingerprint, "added": int(time.time())}
        status, payload = call(row, "GET", "status")
        if status == 401:
            raise FleetError("token_rejected")
        if status != 200:
            raise FleetError("unreachable")
        with self.lock:
            rows = self._load()
            if len(rows) >= LIMIT:
                raise FleetError("too_many")
            if any(item["url"] == row["url"] for item in rows):
                raise FleetError("exists")
            rows.append(row)
            self._save(rows)
            self.cache[row["id"]] = (time.monotonic(), {"ok": True, "status": payload})
        return self.public(row)

    def remove(self, host_id):
        with self.lock:
            rows = self._load()
            kept = [row for row in rows if row.get("id") != host_id]
            if len(kept) == len(rows):
                raise FleetError("not_found")
            self._save(kept)
            self.cache.pop(host_id, None)

    def _status(self, row):
        try:
            status, payload = call(row, "GET", "status")
        except FleetError as error:
            return {"ok": False, "error": str(error)}
        if status != 200:
            return {"ok": False, "error": "token_rejected" if status in (401, 403) else "unreachable"}
        return {"ok": True, "status": payload}

    def statuses(self, refresh=False):
        rows = self.hosts()
        now = time.monotonic()
        stale = [row for row in rows if refresh or now - self.cache.get(row["id"], (0, None))[0] > CACHE_SECONDS]
        if stale:
            with ThreadPoolExecutor(max_workers=min(16, len(stale))) as pool:
                for row, result in zip(stale, pool.map(self._status, stale)):
                    result["checked"] = int(time.time())
                    self.cache[row["id"]] = (time.monotonic(), result)
        return [{**self.public(row), **self.cache.get(row["id"], (0, {"ok": False, "error": "unreachable"}))[1]}
                for row in rows]

    def action(self, host_ids, action, version=None):
        """Run ``action`` ("upgrade", "backup") on the chosen hosts; {id: result}."""
        rows = [row for row in self.hosts() if row["id"] in host_ids]
        if not rows:
            raise FleetError("not_found")
        if action == "upgrade":
            method, path, body = "POST", "upgrade", ({"version": version} if version else {})
        elif action == "backup":
            method, path, body = "POST", "backup", {}
        else:
            raise FleetError("invalid_request")

        def run(row):
            try:
                status, payload = call(row, method, path, body)
            except FleetError as error:
                return {"ok": False, "error": str(error)}
            if status == 200:
                return {"ok": True}
            return {"ok": False, "error": payload.get("error") or "failed"}
        with ThreadPoolExecutor(max_workers=min(16, len(rows))) as pool:
            results = dict(zip((row["id"] for row in rows), pool.map(run, rows)))
        for host_id in results:
            self.cache.pop(host_id, None)
        return results
