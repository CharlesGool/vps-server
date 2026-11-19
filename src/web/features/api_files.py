"""JSON API for the mini drive: usage, files, share links, URL fetch jobs and uploads.

Uploads arrive as the raw request body (application/octet-stream), so no
multipart parsing and no copy in memory; the public /f/ download route is
unchanged.
"""

from file_share import DEFAULT_LINK_MINUTES, GIB, LINK_MINUTES, UPLOAD_IDLE_TIMEOUT, FileShareError


class FilesApiMixin:
    API_ROUTES_FILES = {
        ("GET", "files"): "api_files",
        ("POST", "files/upload"): "api_files_upload",
        ("POST", "files/fetch"): "api_files_fetch",
        ("POST", "files/delete"): "api_files_delete",
        ("POST", "files/link"): "api_files_link",
        ("POST", "files/revoke"): "api_files_revoke",
        ("PUT", "files/limits"): "api_files_limits",
        ("POST", "files/job"): "api_files_job",
    }

    def files_state(self, message=None):
        store = self.context.FILE_STORE
        data = store.state()
        links = {}
        for link in data["links"]:
            links.setdefault(link["file"], []).append(link)
        files = []
        for entry in sorted(data["files"], key=lambda item: item["created"], reverse=True):
            files.append({
                "id": entry["id"], "name": entry["name"], "size": entry["size"], "created": entry["created"],
                "source": entry.get("source", ""),
                "links": [{"token": link["token"], "url": self.files_link_url(entry, link),
                           "expires": link.get("expires"), "downloads": link.get("downloads", 0),
                           "max": link.get("max_downloads")} for link in links.get(entry["id"], [])],
            })
        jobs = [{"id": job["id"], "name": job.get("name", ""), "url": job["url"], "state": job.get("state"),
                 "bytes": job.get("bytes", 0), "total": job.get("total"), "error": job.get("error", "")}
                for job in data["jobs"]]
        return {"used": store.used(data), "quota": data["quota"], "room": store.room(data),
                "diskFree": store.disk_free(), "rate": data.get("rate_limit", 0),
                "linkMinutes": list(LINK_MINUTES), "defaultLinkMinutes": DEFAULT_LINK_MINUTES,
                "files": files, "jobs": jobs, "message": message}

    def _files_closed(self):
        if not self.files_enabled():
            self.api_error(403, "feature_closed", url="/closed?module=files")
            return True
        return False

    def _files_call(self, action, message):
        """Run one store change; FileShareError codes go back as the error."""
        try:
            action()
        except FileShareError as exc:
            return self.api_error(400, exc.code)
        return self.api_ok(self.files_state(message))

    def api_files(self):
        if not self._files_closed():
            self.api_ok(self.files_state())

    def api_files_upload(self):
        context = self.context
        if self._files_closed():
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/octet-stream":
            return self.api_error(400, "invalid_request")
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self.api_error(411, "length_required")
        try:
            context.APP_METER.check("files")
        except context.TrafficBlocked:
            return self.api_error(400, "traffic_blocked")
        name = context.parse_qs(context.urlsplit(self.path).query).get("name", [""])[0]
        # Without a limit a sender that goes silent would hold its partial file and its share of the quota forever.
        if self.connection is not None:
            self.connection.settimeout(UPLOAD_IDLE_TIMEOUT)
        try:
            context.FILE_STORE.upload(name, self.rfile, length)
        except FileShareError as exc:
            return self.api_error(400, exc.code)
        except OSError:
            # The sender went away; the partial file is already removed.
            self.close_connection = True
            return None
        finally:
            if self.connection is not None:
                try:
                    self.connection.settimeout(None)
                except OSError:
                    pass
        return self.api_ok(self.files_state("files_uploaded"))

    def api_files_fetch(self):
        context = self.context
        if self._files_closed():
            return
        url = (self.read_json() or {}).get("url")
        if not isinstance(url, str):
            return self.api_error(400, "invalid_request")
        try:
            context.APP_METER.check("files")
        except context.TrafficBlocked:
            return self.api_error(400, "traffic_blocked")
        return self._files_call(lambda: context.FILE_STORE.start_fetch(url), "files_fetch_started")

    def _files_text(self, name):
        value = (self.read_json() or {}).get(name)
        return value if isinstance(value, str) else None

    def api_files_delete(self):
        if self._files_closed():
            return
        file_id = self._files_text("file")
        if file_id is None:
            return self.api_error(400, "invalid_request")
        return self._files_call(lambda: self.context.FILE_STORE.delete(file_id), "files_deleted")

    def api_files_link(self):
        if self._files_closed():
            return
        body = self.read_json() or {}
        file_id, minutes, limit = body.get("file"), body.get("minutes"), body.get("max")
        if (not isinstance(file_id, str) or type(minutes) is not int or
                not (limit is None or type(limit) is int)):
            return self.api_error(400, "link_invalid")
        return self._files_call(lambda: self.context.FILE_STORE.add_link(file_id, minutes, limit), "files_link_added")

    def api_files_revoke(self):
        if self._files_closed():
            return
        token = self._files_text("token")
        if token is None:
            return self.api_error(400, "invalid_request")
        return self._files_call(lambda: self.context.FILE_STORE.revoke_link(token), "files_link_revoked")

    def api_files_limits(self):
        """Quota (GiB) and download speed (MiB/s, null for none), saved together."""
        if self._files_closed():
            return
        body = self.read_json() or {}
        quota, rate = body.get("quotaGib"), body.get("rateMib")
        if isinstance(quota, bool) or not isinstance(quota, (int, float)):
            return self.api_error(400, "quota_invalid")
        if rate is not None and (isinstance(rate, bool) or not isinstance(rate, (int, float))):
            return self.api_error(400, "rate_invalid")
        store = self.context.FILE_STORE

        def save():
            try:
                quota_bytes = int(round(quota * GIB))
                rate_bytes = int(round(rate * 1024 ** 2)) if rate else 0
            except (ValueError, OverflowError) as exc:
                raise FileShareError("quota_invalid") from exc
            store.set_quota(quota_bytes)
            store.set_rate_limit(rate_bytes)
        return self._files_call(save, "files_quota_saved")

    def api_files_job(self):
        if self._files_closed():
            return
        body = self.read_json() or {}
        job, action = body.get("job"), body.get("action")
        if not isinstance(job, str) or action not in ("cancel", "remove"):
            return self.api_error(400, "invalid_request")
        return self._files_call(lambda: self.context.FILE_STORE.cancel_job(job),
                                "files_job_cancelled" if action == "cancel" else "files_job_removed")
