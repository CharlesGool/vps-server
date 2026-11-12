"""Small file store with password-free download links (the "files" feature).

Files reach the store by browser upload or by the server fetching a URL
itself, for hosts that cannot reach a source (GitHub, for example) but can
reach this one. Each file can carry any number of links; a link is a random
token with an optional expiry and download limit, and anyone holding it can
download the file without signing in.

Layout under ``<data dir>/files/``: ``index.json`` (files, links, fetch jobs,
quota) and ``blobs/<id>`` (contents). A write in progress reserves its size
against the quota so two uploads cannot both squeeze into the last gigabyte.
"""
import json
import os
import re
import secrets
import shutil
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

GIB = 1024 ** 3
DEFAULT_QUOTA = 5 * GIB
MIN_QUOTA = 100 * 1024 ** 2
MAX_QUOTA = 10 * 1024 * GIB
# Never fill the disk: keep this much free whatever the quota says.
DISK_RESERVE = 500 * 1024 ** 2
MAX_FILES = 500
MAX_LINKS_PER_FILE = 20
MAX_JOBS = 20
# Link lifetimes in minutes, shortest first; 0: no expiry.
LINK_MINUTES = (5, 10, 30, 60, 120, 300, 1440, 10080, 43200, 0)
DEFAULT_LINK_MINUTES = 10080
MAX_DOWNLOADS = 100000
CHUNK = 1024 * 1024
FETCH_TIMEOUT = 60
# An upload whose sender stays silent this long is dropped with its partial file.
UPLOAD_IDLE_TIMEOUT = 120
# Leftover partial files (no write holds them any more) are swept this often.
SWEEP_SECONDS = 600
# Download speed limit for all links together, bytes per second; 0: no limit.
MIN_RATE = 64 * 1024
MAX_RATE = 10 * 1024 * GIB
USER_AGENT = "vps-server-files"
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{32}")
ID_RE = re.compile(r"[0-9a-f]{16}")


class FileShareError(Exception):
    """``code`` names a user-facing message: files_error_<code>."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def clean_name(name):
    """A file name safe to show and to send in Content-Disposition."""
    name = str(name).replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(char for char in name if char.isprintable() and char not in '"<>|:*?')
    name = " ".join(name.split()).strip(" .")
    return name[:200] or "file"


def name_from_url(url, disposition=None):
    if disposition:
        match = re.search(r"filename\*=UTF-8''([^;]+)", disposition, re.I)
        if match:
            return clean_name(urllib.parse.unquote(match.group(1)))
        match = re.search(r'filename="?([^";]+)"?', disposition, re.I)
        if match:
            return clean_name(match.group(1))
    path = urllib.parse.urlsplit(url).path
    return clean_name(urllib.parse.unquote(path.rsplit("/", 1)[-1]) or urllib.parse.urlsplit(url).hostname or "file")


class FileStore:
    def __init__(self, root):
        self.root = Path(root)
        self.blobs = self.root / "blobs"
        self.index_path = self.root / "index.json"
        self._lock = threading.RLock()
        self._reserved = {}  # write id -> bytes held against the quota
        self._cancel = set()
        self._recovered = False
        self._swept = 0.0
        # Called with the size of every piece received (upload or server
        # download); the console uses it for traffic accounting and limits.
        self.on_receive = None
        self._rate_lock = threading.Lock()
        self._next_send = 0.0  # when the shared download budget allows the next byte

    # -- index ---------------------------------------------------------

    def _load(self):
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("quota", DEFAULT_QUOTA)
        data.setdefault("files", [])
        data.setdefault("links", [])
        data.setdefault("jobs", [])
        data.setdefault("rate_limit", 0)
        return data

    def _save(self, data):
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        temp = self.index_path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.chmod(temp, 0o600)
        os.replace(temp, self.index_path)

    def state(self):
        """Index snapshot with expired links dropped and stale jobs closed."""
        with self._lock:
            data = self._load()
            now = time.time()
            links = [link for link in data["links"] if not self._link_dead(link, now)]
            changed = len(links) != len(data["links"])
            data["links"] = links
            if not self._recovered:
                # A restart ends every fetch that was running; drop its partial file.
                self._recovered = True
                for job in data["jobs"]:
                    if job.get("state") == "running":
                        job.update(state="failed", error="interrupted", finished=now)
                        changed = True
            if now - self._swept >= SWEEP_SECONDS:
                self._sweep(data)
                self._swept = now
            if changed:
                self._save(data)
            return data

    def _sweep(self, data):
        """Remove partial files that no stored file or running write owns."""
        if not self.blobs.is_dir():
            return
        owned = {item["id"] for item in data["files"]} | set(self._reserved)
        for path in self.blobs.iterdir():
            if path.name not in owned:
                path.unlink(missing_ok=True)

    @staticmethod
    def _link_dead(link, now):
        expires = link.get("expires")
        limit = link.get("max_downloads")
        return bool((expires and now >= expires) or (limit and link.get("downloads", 0) >= limit))

    # -- capacity --------------------------------------------------------

    def used(self, data=None):
        data = data or self._load()
        return sum(item["size"] for item in data["files"]) + sum(self._reserved.values())

    def disk_free(self):
        self.root.mkdir(parents=True, exist_ok=True)
        return shutil.disk_usage(self.root).free

    def room(self, data=None):
        """Bytes a new file may still take: quota left, capped by the disk reserve."""
        data = data or self._load()
        return max(0, min(data["quota"] - self.used(data), self.disk_free() - DISK_RESERVE))

    def set_quota(self, quota):
        if not isinstance(quota, int) or not MIN_QUOTA <= quota <= MAX_QUOTA:
            raise FileShareError("quota_invalid")
        with self._lock:
            data = self._load()
            data["quota"] = quota
            self._save(data)

    def set_rate_limit(self, rate):
        """Limit all link downloads together to ``rate`` bytes per second (0: none)."""
        if not isinstance(rate, int) or rate and not MIN_RATE <= rate <= MAX_RATE:
            raise FileShareError("rate_invalid")
        with self._lock:
            data = self._load()
            data["rate_limit"] = rate
            self._save(data)

    def throttle(self, size, rate):
        """Wait until ``size`` more bytes fit the shared download budget.

        Every download takes its share from one budget, so the limit holds for
        all links together however many run at once.
        """
        if not rate:
            return
        with self._rate_lock:
            now = time.monotonic()
            # Time no download used is not saved up: at most a short burst after idling.
            start = max(self._next_send, now - 0.5)
            self._next_send = start + size / rate
            wait = self._next_send - now
        if wait > 0:
            time.sleep(wait)

    def _reserve(self, size):
        """Hold ``size`` bytes (0 when unknown) for a write; returns its id."""
        with self._lock:
            data = self.state()
            if len(data["files"]) + len(self._reserved) >= MAX_FILES:
                raise FileShareError("too_many")
            if size > self.room(data):
                raise FileShareError("no_room")
            write_id = secrets.token_hex(8)
            while any(item["id"] == write_id for item in data["files"]):
                write_id = secrets.token_hex(8)
            self._reserved[write_id] = size
            return write_id

    def _grow(self, write_id, size):
        """Raise a reservation as an unknown-length write goes on."""
        with self._lock:
            held = self._reserved.get(write_id, 0)
            if size <= held:
                return
            data = self._load()
            if size - held > self.room(data):
                raise FileShareError("no_room")
            self._reserved[write_id] = size

    def _write(self, write_id, reader, expected, progress=None):
        """Copy ``reader`` into the blob for ``write_id``; returns bytes written."""
        self.blobs.mkdir(parents=True, exist_ok=True)
        os.chmod(self.blobs, 0o700)
        path = self.blobs / write_id
        written = 0
        try:
            with open(path, "wb") as handle:
                os.chmod(path, 0o600)
                while expected is None or written < expected:
                    if write_id in self._cancel:
                        raise FileShareError("cancelled")
                    want = CHUNK if expected is None else min(CHUNK, expected - written)
                    chunk = reader.read(want)
                    if not chunk:
                        break
                    if self.on_receive is not None:
                        self.on_receive(len(chunk))
                    if expected is None:
                        self._grow(write_id, written + len(chunk))
                    handle.write(chunk)
                    written += len(chunk)
                    if progress:
                        progress(written)
            if expected is not None and written != expected:
                raise FileShareError("incomplete")
            return written
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    def _commit(self, write_id, name, size, source):
        with self._lock:
            self._reserved.pop(write_id, None)
            data = self._load()
            entry = {"id": write_id, "name": clean_name(name), "size": size,
                     "created": int(time.time()), "source": source}
            data["files"].append(entry)
            self._save(data)
            return entry

    def _release(self, write_id):
        with self._lock:
            self._reserved.pop(write_id, None)
            self._cancel.discard(write_id)

    # -- adding files ----------------------------------------------------

    def upload(self, name, reader, length):
        """Store an upload of exactly ``length`` bytes read from ``reader``."""
        if not isinstance(length, int) or length <= 0:
            raise FileShareError("empty")
        write_id = self._reserve(length)
        try:
            size = self._write(write_id, reader, length)
            return self._commit(write_id, name, size, "upload")
        finally:
            self._release(write_id)

    def start_fetch(self, url):
        """Fetch ``url`` in the background; returns the job entry."""
        url = str(url).strip()
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname or len(url) > 2000:
            raise FileShareError("url_invalid")
        with self._lock:
            data = self.state()
            if sum(job.get("state") == "running" for job in data["jobs"]) >= 3:
                raise FileShareError("busy")
            write_id = self._reserve(0)
            job = {"id": write_id, "url": url, "name": name_from_url(url), "state": "running",
                   "bytes": 0, "total": None, "started": int(time.time())}
            data["jobs"] = [job] + data["jobs"][:MAX_JOBS - 1]
            self._save(data)
        threading.Thread(target=self._fetch, args=(write_id, url), daemon=True).start()
        return job

    def _update_job(self, job_id, **fields):
        with self._lock:
            data = self._load()
            for job in data["jobs"]:
                if job["id"] == job_id:
                    job.update(fields)
            self._save(data)

    def _fetch(self, write_id, url):
        last = [0.0]

        def progress(done):
            now = time.monotonic()
            if now - last[0] >= 1:
                last[0] = now
                self._update_job(write_id, bytes=done)

        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT) as response:
                length = response.headers.get("Content-Length")
                total = int(length) if length and length.isdigit() else None
                name = name_from_url(response.geturl(), response.headers.get("Content-Disposition"))
                self._update_job(write_id, name=name, total=total)
                if total is not None:
                    self._grow(write_id, total)
                size = self._write(write_id, response, total, progress)
            if not size:
                raise FileShareError("empty")
            self._commit(write_id, name, size, url)
            self._update_job(write_id, state="done", bytes=size, finished=int(time.time()))
        except FileShareError as exc:
            self._update_job(write_id, state="failed", error=exc.code, finished=int(time.time()))
        except Exception as exc:  # network, HTTP status, TLS: report the kind only
            code = getattr(exc, "code", None)
            error = f"http_{code}" if isinstance(code, int) else "network"
            self._update_job(write_id, state="failed", error=error, finished=int(time.time()))
        finally:
            self._release(write_id)

    def cancel_job(self, job_id):
        with self._lock:
            data = self._load()
            job = next((item for item in data["jobs"] if item["id"] == job_id), None)
            if job is None:
                raise FileShareError("not_found")
            if job.get("state") == "running":
                self._cancel.add(job_id)
            else:
                data["jobs"] = [item for item in data["jobs"] if item["id"] != job_id]
                self._save(data)

    # -- files and links -------------------------------------------------

    def file(self, file_id, data=None):
        data = data or self._load()
        return next((item for item in data["files"] if item["id"] == file_id), None)

    def blob(self, file_id):
        if not ID_RE.fullmatch(str(file_id)):
            raise FileShareError("not_found")
        return self.blobs / file_id

    def delete(self, file_id):
        with self._lock:
            data = self._load()
            if not self.file(file_id, data):
                raise FileShareError("not_found")
            data["files"] = [item for item in data["files"] if item["id"] != file_id]
            data["links"] = [link for link in data["links"] if link["file"] != file_id]
            self._save(data)
            self.blob(file_id).unlink(missing_ok=True)

    def add_link(self, file_id, minutes, max_downloads=None):
        if minutes not in LINK_MINUTES:
            raise FileShareError("link_invalid")
        if max_downloads is not None and not (isinstance(max_downloads, int) and 1 <= max_downloads <= MAX_DOWNLOADS):
            raise FileShareError("link_invalid")
        with self._lock:
            data = self.state()
            if not self.file(file_id, data):
                raise FileShareError("not_found")
            if sum(link["file"] == file_id for link in data["links"]) >= MAX_LINKS_PER_FILE:
                raise FileShareError("too_many_links")
            now = int(time.time())
            link = {"token": secrets.token_urlsafe(24), "file": file_id, "created": now,
                    "expires": now + minutes * 60 if minutes else None,
                    "max_downloads": max_downloads, "downloads": 0}
            data["links"].append(link)
            self._save(data)
            return link

    def revoke_link(self, token):
        with self._lock:
            data = self._load()
            kept = [link for link in data["links"] if link["token"] != token]
            if len(kept) == len(data["links"]):
                raise FileShareError("not_found")
            data["links"] = kept
            self._save(data)

    def resolve(self, token, count=False):
        """The file behind a live link token, or None. ``count`` records a download."""
        if not TOKEN_RE.fullmatch(str(token)):
            return None
        with self._lock:
            data = self._load()
            now = time.time()
            link = next((item for item in data["links"]
                         if secrets.compare_digest(item["token"], token)), None)
            if link is None or self._link_dead(link, now):
                return None
            entry = self.file(link["file"], data)
            if entry is None or not self.blob(entry["id"]).is_file():
                return None
            if count:
                link["downloads"] = link.get("downloads", 0) + 1
                link["last"] = int(now)
                self._save(data)
            return entry
