"""Mini Drive: the public download route (/f/<token>/<name>) and share links (the page is the single-page UI).

The store itself is file_share.py. Uploads arrive as the raw request body
(files.js sends the file with XMLHttpRequest), so no multipart parsing and
no copy in memory. Download links need no session or client certificate:
the route is dispatched before both checks, like Clash subscriptions.
"""
import re
import urllib.parse


NOTICES = ("files_uploaded", "files_deleted", "files_link_added", "files_link_revoked",
           "files_fetch_started", "files_quota_saved", "files_rate_saved", "files_job_removed", "files_job_cancelled")
ERRORS = ("no_room", "too_many", "empty", "incomplete", "url_invalid", "url_blocked", "busy", "not_found",
          "link_invalid", "too_many_links", "quota_invalid", "rate_invalid", "traffic_blocked", "cancelled", "interrupted", "network")
RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


class FilesMixin:

    def files_enabled(self):
        return self.context.module_feature_enabled(self.context.BASE_DIR, "files")

    # -- public download -------------------------------------------------

    def route_files_public(self, method, path):
        if method not in ("GET", "HEAD") or not path.startswith("/f/"):
            return False
        parts = path.split("/")
        entry = None
        if len(parts) in (3, 4) and self.files_enabled():
            # Only a request that starts at byte 0 counts as a download, so
            # resuming with a Range header does not use up the limit.
            ranged = self.headers.get("Range", "")
            first = not ranged or ranged.strip().startswith("bytes=0-")
            entry = self.context.FILE_STORE.resolve(parts[2], count=method == "GET" and first)
        if entry is not None:
            try:
                self.context.APP_METER.check("files")
            except self.context.TrafficBlocked:
                self.send_response(503)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", "22")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if method == "GET":
                    self.wfile.write(b"Traffic limit reached\n")
                return True
        if entry is None:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", "10")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if method == "GET":
                self.wfile.write(b"Not found\n")
            return True
        self.files_send(entry, method)
        return True

    def files_send(self, entry, method):
        path = self.context.FILE_STORE.blob(entry["id"])
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        match = RANGE_RE.fullmatch(self.headers.get("Range", "").strip())
        if match and (match.group(1) or match.group(2)):
            if match.group(1):
                start = int(match.group(1))
                end = min(int(match.group(2)), size - 1) if match.group(2) else size - 1
            else:  # suffix range: the last N bytes
                start = max(0, size - int(match.group(2)))
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            status = 206
        quoted = urllib.parse.quote(entry["name"], safe="")
        ascii_name = entry["name"].encode("ascii", "replace").decode("ascii").replace("?", "_")
        self.send_response(status)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Content-Disposition", f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quoted}")
        self.send_header("Accept-Ranges", "bytes")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if method == "HEAD":
            return
        store, meter = self.context.FILE_STORE, self.context.APP_METER
        rate = store.state().get("rate_limit", 0)
        # Small pieces under a limit keep the speed even instead of in bursts.
        piece = min(1024 * 1024, max(16 * 1024, rate // 8)) if rate else 1024 * 1024
        with open(path, "rb") as handle:
            handle.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = handle.read(min(piece, meter.piece("files", "download", piece), left))
                if not chunk:
                    break
                store.throttle(len(chunk), rate)
                try:
                    meter.take("files", "download", len(chunk))
                except self.context.TrafficBlocked:
                    break  # Cut off mid-way: the client sees a short download.
                self.wfile.write(chunk)
                left -= len(chunk)

    # -- console ---------------------------------------------------------


    def files_link_url(self, entry, link):
        host = self.headers.get("Host", "")
        if not self.context.re.fullmatch(r"[A-Za-z0-9.:\[\]-]{1,255}", host):
            host = "localhost"
        return f"https://{host}/f/{link['token']}/{urllib.parse.quote(entry['name'], safe='')}"
