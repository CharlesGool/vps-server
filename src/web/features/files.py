"""Files page (/files) and the public download route (/f/<token>/<name>).

The store itself is file_share.py. Uploads arrive as the raw request body
(files.js sends the file with XMLHttpRequest), so no multipart parsing and
no copy in memory. Download links need no session or client certificate:
the route is dispatched before both checks, like Clash subscriptions.
"""
import re
import time
import urllib.parse

from file_share import GIB, LINK_DAYS, FileShareError

NOTICES = ("files_uploaded", "files_deleted", "files_link_added", "files_link_revoked",
           "files_fetch_started", "files_quota_saved", "files_job_removed", "files_job_cancelled")
ERRORS = ("no_room", "too_many", "empty", "incomplete", "url_invalid", "busy", "not_found",
          "link_invalid", "too_many_links", "quota_invalid", "cancelled", "interrupted", "network")
RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


def human_size(size):
    for unit, step in (("GiB", GIB), ("MiB", 1024 ** 2), ("KiB", 1024)):
        if size >= step:
            return f"{size / step:.1f} {unit}"
    return f"{size} B"


class FilesMixin:
    def files_csrf(self):
        return self.context.access_csrf_token(self.get_cookie("session"), "files")

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
        with open(path, "rb") as handle:
            handle.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = handle.read(min(1024 * 1024, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    # -- console ---------------------------------------------------------

    def route_files(self, method, path, parsed, lang, query_lang):
        if not path.startswith("/files"):
            return False
        if not self.files_enabled():
            if method == "GET" and path == "/files":
                self.redirect("/closed?module=files", {"Cache-Control": "no-store"})
            else:
                self.send_html(404, "Not found", {"Cache-Control": "no-store"})
            return True
        if method == "GET" and path == "/files":
            self.page_files(lang, query_lang, parsed)
            return True
        if method == "GET" and path == "/files/jobs":
            self.files_jobs_json()
            return True
        if method == "POST" and path == "/files/upload":
            self.handle_files_upload(parsed)
            return True
        handlers = {"/files/fetch": self.handle_files_fetch, "/files/delete": self.handle_files_delete,
                    "/files/link": self.handle_files_link, "/files/revoke": self.handle_files_revoke,
                    "/files/quota": self.handle_files_quota, "/files/job": self.handle_files_job}
        if method == "POST" and path in handlers:
            handlers[path]()
            return True
        return False

    def files_form(self):
        raw = self.read_body(self.context.LOGIN_BODY_LIMIT)
        form = self.context.parse_qs(raw.decode("utf-8", errors="replace"))
        values = form.get("csrf", [])
        if len(values) != 1 or not self.context.hmac.compare_digest(values[0], self.files_csrf()):
            return None
        return form

    def files_done(self, notice=None, error=None, anchor=""):
        query = f"error={error}" if error else f"msg={notice}"
        return self.redirect(f"/files?{query}{anchor}", {"Cache-Control": "no-store"})

    def files_link_url(self, entry, link):
        host = self.headers.get("Host", "")
        if not self.context.re.fullmatch(r"[A-Za-z0-9.:\[\]-]{1,255}", host):
            host = "localhost"
        return f"https://{host}/f/{link['token']}/{urllib.parse.quote(entry['name'], safe='')}"

    def page_files(self, lang, query_lang, parsed):
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        store = self.context.FILE_STORE
        query = self.context.parse_qs(parsed.query)
        messages = []
        msg = query.get("msg", [""])[0]
        if msg in NOTICES:
            messages.append(f'<p class="notice" role="status">{esc(t[msg])}</p>')
        error = query.get("error", [""])[0]
        if error in ERRORS:
            messages.append(f'<p class="error" role="alert">{esc(t["files_error_" + error])}</p>')
        data = store.state()
        csrf = esc(self.files_csrf(), quote=True)
        used, quota, free = store.used(data), data["quota"], store.disk_free()
        room = store.room(data)
        percent = min(100, round(used * 100 / quota)) if quota else 100

        def date(stamp):
            return time.strftime("%Y-%m-%d %H:%M", time.localtime(stamp)) if stamp else "—"

        def hidden(**fields):
            return f'<input type="hidden" name="csrf" value="{csrf}">' + "".join(
                f'<input type="hidden" name="{name}" value="{esc(str(value), quote=True)}">'
                for name, value in fields.items())

        usage = (f'<section class="card frp-card files-usage">'
                 f'<div class="frp-instances-head"><h2 class="frp-instances-heading">{esc(t["files_usage"])}</h2>'
                 f'<span class="muted">{esc(t["files_usage_detail"].format(used=human_size(used), quota=human_size(quota), free=human_size(free)))}</span></div>'
                 f'<div class="files-meter" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{percent}" '
                 f'aria-label="{esc(t["files_usage"], quote=True)}"><span style="width:{percent}%"></span></div>'
                 f'<details class="files-quota"><summary>{esc(t["files_quota_change"])}</summary>'
                 f'<form method="post" action="/files/quota" class="files-inline-form">{hidden()}'
                 f'<label>{esc(t["files_quota_label"])}<input type="number" name="quota" min="0.1" max="10240" step="0.1" '
                 f'value="{quota / GIB:g}" required></label>'
                 f'<button type="submit">{esc(t["files_quota_save"])}</button></form>'
                 f'<p class="muted">{esc(t["files_quota_help"])}</p></details></section>')

        add = (f'<section class="card frp-card files-add">'
               f'<div class="frp-instances-head"><h2 class="frp-instances-heading">{esc(t["files_add"])}</h2>'
               f'<span class="muted">{esc(t["files_room"].format(room=human_size(room)))}</span></div>'
               f'<form method="post" action="/files/fetch" class="files-inline-form">{hidden()}'
               f'<label>{esc(t["files_fetch_label"])}<input type="url" name="url" required maxlength="2000" '
               f'placeholder="https://github.com/…/releases/download/…"></label>'
               f'<button type="submit">{esc(t["files_fetch"])}</button></form>'
               f'<p class="muted">{esc(t["files_fetch_help"])}</p>'
               f'<form class="files-upload files-inline-form" data-csrf="{csrf}" data-room="{room}" '
               f'data-too-big="{esc(t["files_error_no_room"], quote=True)}" '
               f'data-failed="{esc(t["files_upload_failed"], quote=True)}">'
               f'<label>{esc(t["files_upload_label"])}<input type="file" name="file" required></label>'
               f'<button type="submit">{esc(t["files_upload"])}</button>'
               f'<progress max="100" value="0" hidden></progress><output class="muted"></output></form>'
               f'</section>')

        jobs = ""
        if data["jobs"]:
            rows = ""
            for job in data["jobs"]:
                state = job.get("state")
                if state == "running":
                    total = job.get("total")
                    detail = (f'{human_size(job.get("bytes", 0))} / {human_size(total)}' if total
                              else human_size(job.get("bytes", 0)))
                    pill = f'<span class="proxy-node-status is-open">{esc(t["files_job_running"])}</span>'
                    action, label = "cancel", t["files_job_cancel"]
                elif state == "done":
                    detail = human_size(job.get("bytes", 0))
                    pill = f'<span class="proxy-node-status is-open">{esc(t["files_job_done"])}</span>'
                    action, label = "remove", t["files_job_remove"]
                else:
                    reason = job.get("error", "")
                    detail = (t["files_error_http"].format(code=reason[5:]) if reason.startswith("http_")
                              else t.get("files_error_" + reason, reason))
                    pill = f'<span class="proxy-node-status is-closed">{esc(t["files_job_failed"])}</span>'
                    action, label = "remove", t["files_job_remove"]
                rows += (f'<li data-job="{esc(job["id"], quote=True)}" data-state="{esc(state or "", quote=True)}">'
                         f'<span class="files-name">{pill} <strong>{esc(job.get("name", ""))}</strong></span>'
                         f'<span class="muted files-job-detail">{esc(detail)}</span>'
                         f'<code class="files-url">{esc(job["url"])}</code>'
                         f'<form method="post" action="/files/job">{hidden(job=job["id"], action=action)}'
                         f'<button type="submit" class="frp-card-edit">{esc(label)}</button></form></li>')
            jobs = (f'<section class="card frp-card files-jobs"><div class="frp-instances-head">'
                    f'<h2 class="frp-instances-heading">{esc(t["files_jobs"])}</h2></div>'
                    f'<ul class="files-list">{rows}</ul></section>')

        links_by_file = {}
        for link in data["links"]:
            links_by_file.setdefault(link["file"], []).append(link)
        day_options = "".join(
            f'<option value="{days}"{" selected" if days == 7 else ""}>'
            f'{esc(t["files_link_forever"] if days == 0 else t["files_link_days"].format(days=days))}</option>'
            for days in LINK_DAYS)
        cards = ""
        for entry in sorted(data["files"], key=lambda item: item["created"], reverse=True):
            link_rows = ""
            for link in links_by_file.get(entry["id"], []):
                url = self.files_link_url(entry, link)
                ident = f'files-link-{link["token"][:12]}'
                limit = link.get("max_downloads")
                count = (t["files_link_count_limit"].format(count=link.get("downloads", 0), limit=limit) if limit
                         else t["files_link_count"].format(count=link.get("downloads", 0)))
                expires = (t["files_link_until"].format(date=date(link["expires"])) if link.get("expires")
                           else t["files_link_forever"])
                link_rows += (f'<li><code id="{ident}" class="files-url">{esc(url)}</code>'
                              f'<span class="muted">{esc(expires)} · {esc(count)}</span>'
                              f'<span class="files-link-actions">'
                              f'<button type="button" class="copybtn frp-card-edit" data-copy="{ident}" '
                              f'data-copied="{esc(t["copied"], quote=True)}">{esc(t["copy"])}</button>'
                              f'<form method="post" action="/files/revoke">{hidden(token=link["token"])}'
                              f'<button type="submit" class="frp-card-edit">{esc(t["files_link_revoke"])}</button>'
                              f'</form></span></li>')
            source = (t["files_source_upload"] if entry.get("source") == "upload"
                      else t["files_source_url"].format(url=entry.get("source", "")))
            cards += (f'<li class="files-entry"><div class="files-entry-head">'
                      f'<span class="files-name"><strong>{esc(entry["name"])}</strong></span>'
                      f'<span class="muted">{esc(human_size(entry["size"]))} · {esc(date(entry["created"]))}</span>'
                      f'<form method="post" action="/files/delete" class="files-delete" '
                      f'data-confirm="{esc(t["files_delete_confirm"].format(name=entry["name"]), quote=True)}">'
                      f'{hidden(file=entry["id"])}<button type="submit" class="node-action-danger frp-card-edit">'
                      f'{esc(t["files_delete"])}</button></form></div>'
                      f'<p class="muted files-source">{esc(source)}</p>'
                      + (f'<ul class="files-links">{link_rows}</ul>' if link_rows else '')
                      + f'<form method="post" action="/files/link" class="files-inline-form files-link-form">'
                      f'{hidden(file=entry["id"])}'
                      f'<label>{esc(t["files_link_expiry"])}<select name="days">{day_options}</select></label>'
                      f'<label>{esc(t["files_link_limit"])}<input type="number" name="max" min="1" max="100000" '
                      f'placeholder="{esc(t["files_link_unlimited"], quote=True)}"></label>'
                      f'<button type="submit">{esc(t["files_link_add"])}</button></form></li>')
        files_card = (f'<section class="card frp-card files-files"><div class="frp-instances-head">'
                      f'<h2 class="frp-instances-heading">{esc(t["files_files"])}</h2>'
                      f'<span class="muted">{esc(t["files_link_help"])}</span></div>'
                      + (f'<ul class="files-list">{cards}</ul>' if cards else
                         f'<p class="muted">{esc(t["files_empty"])}</p>') + '</section>')

        body = (f'<h1>{esc(t["files"])}</h1><div class="frp-workspace files-page">{"".join(messages)}'
                f'{usage}{add}{jobs}{files_card}</div>'
                '<script src="/static/copy.js"></script><script src="/static/files.js" defer></script>')
        return self.send_html(200, self.render_page(t["files"], body, lang, icon="files"),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def files_jobs_json(self):
        data = self.context.FILE_STORE.state()
        jobs = [{"id": job["id"], "state": job.get("state"), "bytes": job.get("bytes", 0),
                 "total": job.get("total")} for job in data["jobs"]]
        return self.send_json(200, {"jobs": jobs})

    def handle_files_upload(self, parsed):
        query = self.context.parse_qs(parsed.query)
        token = query.get("csrf", [""])[0]
        if not token or not self.context.hmac.compare_digest(token, self.files_csrf()):
            return self.send_json(403, {"error": "forbidden"})
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self.send_json(411, {"error": "length_required"})
        try:
            self.context.FILE_STORE.upload(query.get("name", [""])[0], self.rfile, length)
        except FileShareError as exc:
            return self.send_json(400, {"error": exc.code})
        return self.send_json(200, {"ok": True})

    def handle_files_fetch(self):
        form = self.files_form()
        if form is None:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        try:
            self.context.FILE_STORE.start_fetch(form.get("url", [""])[0])
        except FileShareError as exc:
            return self.files_done(error=exc.code)
        return self.files_done("files_fetch_started")

    def handle_files_delete(self):
        form = self.files_form()
        if form is None:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        try:
            self.context.FILE_STORE.delete(form.get("file", [""])[0])
        except FileShareError as exc:
            return self.files_done(error=exc.code)
        return self.files_done("files_deleted")

    def handle_files_link(self):
        form = self.files_form()
        if form is None:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        days, limit = form.get("days", [""])[0], form.get("max", [""])[0].strip()
        try:
            if not days.isdecimal() or (limit and not limit.isdecimal()):
                raise FileShareError("link_invalid")
            self.context.FILE_STORE.add_link(form.get("file", [""])[0], int(days), int(limit) if limit else None)
        except FileShareError as exc:
            return self.files_done(error=exc.code)
        return self.files_done("files_link_added")

    def handle_files_revoke(self):
        form = self.files_form()
        if form is None:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        try:
            self.context.FILE_STORE.revoke_link(form.get("token", [""])[0])
        except FileShareError as exc:
            return self.files_done(error=exc.code)
        return self.files_done("files_link_revoked")

    def handle_files_quota(self):
        form = self.files_form()
        if form is None:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        try:
            quota = int(round(float(form.get("quota", [""])[0]) * GIB))
        except (ValueError, OverflowError):
            return self.files_done(error="quota_invalid")
        try:
            self.context.FILE_STORE.set_quota(quota)
        except FileShareError as exc:
            return self.files_done(error=exc.code)
        return self.files_done("files_quota_saved")

    def handle_files_job(self):
        form = self.files_form()
        if form is None:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        try:
            self.context.FILE_STORE.cancel_job(form.get("job", [""])[0])
        except FileShareError as exc:
            return self.files_done(error=exc.code)
        cancelled = form.get("action", [""])[0] == "cancel"
        return self.files_done("files_job_cancelled" if cancelled else "files_job_removed")
