"""JSON API for the file manager: browse the host's file system, read, edit, upload and download.

The file manager reaches every file as root, so like the terminal every call
needs a password-verified session (security settings permission). Reading
happens in the console; anything that writes goes through ``sysadmin.py``
(see features/api_system.py), because the console's own file system view is
read-only. Uploads and edits land in a private staging directory first and
the helper moves them into place.
"""

import grp
import os
import pwd
import secrets
import stat
import tarfile
import time
import urllib.parse
from pathlib import Path

from features.api_system import run_helper, staging_dir

LIST_LIMIT = 5000
EDIT_LIMIT = 1024 * 1024
UPLOAD_IDLE_TIMEOUT = 60
OPS = {"mkdir", "touch", "rename", "move", "copy", "delete", "chmod", "chown", "extract", "compress"}


def _clean(value):
    """An absolute, normalised path, or None."""
    if not isinstance(value, str) or not value.startswith("/") or "\0" in value or len(value) > 4096:
        return None
    path = os.path.normpath(value)
    return "/" + path.lstrip("/") if path.startswith("//") else path


def _owner(uid, gid, cache):
    if ("u", uid) not in cache:
        try:
            cache[("u", uid)] = pwd.getpwuid(uid).pw_name
        except KeyError:
            cache[("u", uid)] = str(uid)
    if ("g", gid) not in cache:
        try:
            cache[("g", gid)] = grp.getgrgid(gid).gr_name
        except KeyError:
            cache[("g", gid)] = str(gid)
    return cache[("u", uid)], cache[("g", gid)]


def entry(path, name, cache):
    full = os.path.join(path, name)
    info = os.lstat(full)
    kind = "link" if stat.S_ISLNK(info.st_mode) else "dir" if stat.S_ISDIR(info.st_mode) else \
        "file" if stat.S_ISREG(info.st_mode) else "other"
    row = {"name": name, "type": kind, "size": info.st_size if kind == "file" else None,
           "modified": int(info.st_mtime), "mode": stat.filemode(info.st_mode),
           "octal": format(stat.S_IMODE(info.st_mode), "04o")}
    row["owner"], row["group"] = _owner(info.st_uid, info.st_gid, cache)
    if kind == "link":
        try:
            row["target"] = os.readlink(full)
            row["targetDir"] = os.path.isdir(full)
        except OSError:
            row["target"], row["targetDir"] = "", False
    return row


def listing(path):
    cache = {}
    names = sorted(os.listdir(path), key=lambda name: name.lower())
    rows = []
    for name in names[:LIST_LIMIT]:
        try:
            rows.append(entry(path, name, cache))
        except OSError:
            continue
    return rows, len(names) > LIST_LIMIT


class FileManagerApiMixin:
    API_ROUTES_FILEMANAGER = {
        ("GET", "fm/list"): "api_fm_list",
        ("GET", "fm/read"): "api_fm_read",
        ("GET", "fm/download"): "api_fm_download",
        ("POST", "fm/upload"): "api_fm_upload",
        ("POST", "fm/save"): "api_fm_save",
        ("POST", "fm/op"): "api_fm_op",
    }

    def _fm_path(self, name="path"):
        return _clean((self.query_params().get(name) or [""])[0])

    def api_fm_list(self):
        if not self._security_allowed():
            return
        path = self._fm_path() or "/"
        if not os.path.isdir(path):
            return self.api_error(404, "not_found")
        try:
            rows, truncated = listing(path)
        except PermissionError:
            return self.api_error(403, "denied")
        except OSError:
            return self.api_error(404, "not_found")
        try:
            usage = os.statvfs(path)
            free = usage.f_bavail * usage.f_frsize
        except OSError:
            free = None
        return self.api_ok({"path": path, "rows": rows, "truncated": truncated, "free": free,
                            "users": sorted({row["owner"] for row in rows} | {"root"}),
                            "groups": sorted({row["group"] for row in rows} | {"root"})})

    def api_fm_read(self):
        if not self._security_allowed():
            return
        path = self._fm_path()
        if not path or not os.path.isfile(path):
            return self.api_error(404, "not_found")
        if os.path.getsize(path) > EDIT_LIMIT:
            return self.api_error(400, "too_large")
        try:
            data = Path(path).read_bytes()
        except OSError:
            return self.api_error(403, "denied")
        if b"\0" in data:
            return self.api_error(400, "binary")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return self.api_error(400, "binary")
        return self.api_ok({"path": path, "text": text, "modified": int(os.path.getmtime(path))})

    def _attachment(self, name):
        ascii_name = name.encode("ascii", "replace").decode().replace('"', "_").replace("?", "_") or "download"
        return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{urllib.parse.quote(name)}"

    def api_fm_download(self):
        if not self._security_allowed():
            return
        path = self._fm_path()
        if not path or not os.path.exists(path):
            return self.api_error(404, "not_found")
        name = os.path.basename(path) or "root"
        self.audit("file_download", path)
        if os.path.isdir(path):
            # Folders go out as a tar.gz written straight to the connection (no size known in advance).
            self.send_response(200)
            self.send_header("Content-Type", "application/gzip")
            self.send_header("Content-Disposition", self._attachment(name + ".tar.gz"))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            try:
                with tarfile.open(fileobj=self.wfile, mode="w|gz") as bundle:
                    bundle.add(path, arcname=name)
            except OSError:
                pass
            return None
        try:
            handle = open(path, "rb")
        except OSError:
            return self.api_error(403, "denied")
        with handle:
            size = os.fstat(handle.fileno()).st_size
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Disposition", self._attachment(name))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                while True:
                    chunk = handle.read(1 << 20)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            except OSError:
                self.close_connection = True
        return None

    def _stage(self, source, length):
        """Copy ``length`` bytes from ``source`` into a new staging file; its path."""
        target = staging_dir(self.context) / ("up-" + secrets.token_hex(8))
        left = length
        try:
            with open(target, "xb") as handle:
                os.chmod(target, 0o600)
                while left > 0:
                    chunk = source.read(min(left, 1 << 20))
                    if not chunk:
                        raise OSError("incomplete")
                    handle.write(chunk)
                    left -= len(chunk)
        except OSError:
            target.unlink(missing_ok=True)
            raise
        return target

    def _place(self, staged, path, overwrite):
        answer = run_helper(self.context, {"action": "write", "staging": str(staged), "path": path,
                                           "overwrite": overwrite}, timeout=600)
        if not answer.get("ok"):
            staged.unlink(missing_ok=True)
        return answer

    def api_fm_upload(self):
        if not self._security_allowed():
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/octet-stream":
            return self.api_error(400, "invalid_request")
        directory = self._fm_path("dir")
        name = (self.query_params().get("name") or [""])[0]
        overwrite = (self.query_params().get("overwrite") or [""])[0] == "1"
        if not directory or not name or "/" in name or name in (".", "..") or len(name) > 255:
            return self.api_error(400, "name_invalid")
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self.api_error(411, "length_required")
        try:
            free = os.statvfs(directory)
            if length > free.f_bavail * free.f_frsize:
                return self.api_error(400, "no_room")
        except OSError:
            return self.api_error(404, "not_found")
        if self.connection is not None:
            self.connection.settimeout(UPLOAD_IDLE_TIMEOUT)
        try:
            staged = self._stage(self.rfile, length)
        except OSError:
            self.close_connection = True
            return None
        finally:
            if self.connection is not None:
                try:
                    self.connection.settimeout(None)
                except OSError:
                    pass
        path = os.path.join(directory, name)
        answer = self._place(staged, path, overwrite)
        if not answer.get("ok"):
            return self.api_error(400, answer.get("error", "failed"))
        self.audit("file_upload", path)
        return self.api_ok({"path": path})

    def api_fm_save(self):
        if not self._security_allowed():
            return
        body = self.read_json_large(EDIT_LIMIT * 4 + 4096)
        if body is None or not isinstance(body.get("text"), str):
            return self.api_error(400, "invalid_request")
        path = _clean(body.get("path"))
        if not path:
            return self.api_error(400, "invalid_request")
        data = body["text"].encode("utf-8")
        if len(data) > EDIT_LIMIT:
            return self.api_error(400, "too_large")
        modified = body.get("modified")
        if isinstance(modified, int) and os.path.exists(path) and int(os.path.getmtime(path)) != modified:
            return self.api_error(409, "changed")
        import io
        staged = self._stage(io.BytesIO(data), len(data))
        answer = self._place(staged, path, True)
        if not answer.get("ok"):
            return self.api_error(400, answer.get("error", "failed"))
        self.audit("file_saved", path)
        return self.api_ok({"path": path, "modified": int(os.path.getmtime(path))})

    def api_fm_op(self):
        if not self._security_allowed():
            return
        body = self.read_json()
        if body is None or body.get("action") not in OPS:
            return self.api_error(400, "invalid_request")
        answer = run_helper(self.context, body, timeout=1800)
        if not answer.get("ok"):
            return self.api_error(400, answer.get("error", "failed"))
        self.audit("file_" + body["action"], str(body.get("path") or ",".join(map(str, body.get("paths") or []))))
        answer.pop("ok", None)
        return self.api_ok(answer)

    def staging_cleanup(self, older=86400):
        """Drop staging files left by interrupted requests."""
        now = time.time()
        for item in staging_dir(self.context).glob("up-*"):
            try:
                if now - item.stat().st_mtime > older:
                    item.unlink()
            except OSError:
                pass
