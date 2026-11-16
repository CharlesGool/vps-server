"""Configuration backup page: create, download, upload, restore, schedule.

Host dependencies come from ``ConsoleHandler.context``. Creating a backup only
reads files, so the console does it itself; restoring writes system files, so
it runs through ``systemd-run`` outside the console's read-only sandbox.
"""

import json
import os
import re
import secrets
import subprocess
import tempfile
import time
from pathlib import Path

import config_backup
import scheduler

MAX_UPLOAD = 256 * 1024 * 1024
UPLOAD_IDLE_TIMEOUT = 60
NOTICES = ("created", "deleted", "settings", "restore_started", "uploaded")
ERRORS = ("failed", "invalid", "not_found", "no_space", "busy")
KIND_KEYS = {"manual": "backup_kind_manual", "scheduled": "backup_kind_scheduled",
             "pre-upgrade": "backup_kind_pre_upgrade", "pre-restore": "backup_kind_pre_restore"}
# Restart order after a restore: meters first (they take their dependents along),
# then the services that read restored files, the console last.
RESTORE_SCRIPT = (
    'set -e; python3 "$1" restore "$2"; systemctl daemon-reload; '
    'for u in vps-server-node-meter vps-server-frps-meter vps-server-traffic-meter '
    'vps-server-tailscale vps-server-caddy vps-server-proxy vps-server-frps; do '
    'systemctl try-restart "$u.service" || true; done; systemctl restart vps-server-web.service')


def human_size(value):
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return str(value)


def local_time(stamp):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(stamp)) if stamp else "—"


class BackupMixin:
    def backup_csrf(self):
        return self.context.access_csrf_token(self.get_cookie("session"), "backup")

    def backup_form(self, fields):
        raw = self.read_body(4096)
        try:
            form = self.context.parse_qs(raw.decode("utf-8"), strict_parsing=True, keep_blank_values=True)
        except (UnicodeError, ValueError):
            return None
        if not set(form) <= set(fields) | {"csrf"} or any(len(v) != 1 for v in form.values()):
            return None
        if "csrf" not in form or not self.context.hmac.compare_digest(form["csrf"][0], self.backup_csrf()):
            return None
        return {key: value[0] for key, value in form.items() if key != "csrf"}

    def backup_done(self, notice=None, error=None):
        query = f"error={error}" if error else f"msg={notice}"
        return self.redirect(f"/backup?{query}", {"Cache-Control": "no-store"})

    def page_backup(self, lang, query_lang, parsed):
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        query = self.context.parse_qs(parsed.query)
        messages = []
        msg = query.get("msg", [""])[0]
        if msg in NOTICES:
            messages.append(f'<p class="notice" role="status">{esc(t["backup_msg_" + msg])}</p>')
        error = query.get("error", [""])[0]
        if error in ERRORS:
            messages.append(f'<p class="error" role="alert">{esc(t["backup_error_" + error])}</p>')
        csrf = esc(self.backup_csrf(), quote=True)
        hidden = f'<input type="hidden" name="csrf" value="{csrf}">'
        engine = self.context.SCHEDULER
        settings = engine.backup_settings()
        last = engine.last_run("backup")
        following = engine.next_backup()
        if last:
            last_text = (f'{esc(local_time(last["started"]))} · '
                         f'{esc(t["task_status_" + last["status"]])}')
        else:
            last_text = esc(t["backup_never"])
        schedule = (f'<section class="card frp-card"><h2 class="frp-instances-heading">{esc(t["backup_schedule"])}</h2>'
                    f'<p class="files-meta">{esc(t["backup_schedule_help"])}</p>'
                    f'<form method="post" action="/backup/settings" class="files-inline" style="flex-wrap:wrap;gap:.75rem;align-items:center">{hidden}'
                    f'<label><input type="checkbox" name="enabled" value="1"{" checked" if settings["enabled"] else ""}> '
                    f'{esc(t["backup_enabled"])}</label>'
                    f'<label>{esc(t["backup_time"])} <input type="time" name="time" value="{esc(settings["time"], quote=True)}" required></label>'
                    f'<label>{esc(t["backup_keep"])} <input type="number" name="keep" min="1" max="{scheduler.BACKUP_KEEP_MAX}" '
                    f'value="{settings["keep"]}" required></label>'
                    f'<button type="submit" class="files-button">{esc(t["backup_save"])}</button></form>'
                    f'<p class="files-meta">{esc(t["backup_last"])}: {last_text}'
                    + (f' · {esc(t["backup_next"])}: {esc(local_time(following))}' if following else '')
                    + f' · {esc(time.tzname[0])}</p></section>')

        rows = []
        for item in config_backup.list_backups():
            name = esc(item["name"], quote=True)
            rows.append(
                f'<li class="files-row"><div class="files-row-main"><strong>{esc(t[KIND_KEYS[item["kind"]]])}</strong>'
                f'<p class="files-meta">{esc(local_time(item["created"]))} · {esc(human_size(item["size"]))} · '
                f'<code>{esc(item["name"])}</code></p></div><div class="files-row-actions">'
                f'<a class="files-button" href="/backup/download?name={name}" download>{esc(t["backup_download"])}</a>'
                f'<form method="post" action="/backup/restore" class="backup-confirm" '
                f'data-confirm="{esc(t["backup_restore_confirm"], quote=True)}">{hidden}'
                f'<input type="hidden" name="name" value="{name}">'
                f'<button type="submit" class="files-button">{esc(t["backup_restore"])}</button></form>'
                f'<form method="post" action="/backup/delete" class="backup-confirm" '
                f'data-confirm="{esc(t["backup_delete_confirm"], quote=True)}">{hidden}'
                f'<input type="hidden" name="name" value="{name}">'
                f'<button type="submit" class="files-button files-danger">{esc(t["backup_delete"])}</button></form>'
                f'</div></li>')
        listing = (f'<section class="card frp-card"><div class="files-usage-head">'
                   f'<h2 class="frp-instances-heading">{esc(t["backup_list"])}</h2>'
                   f'<form method="post" action="/backup/create">{hidden}'
                   f'<button type="submit" class="files-button">{esc(t["backup_create"])}</button></form></div>'
                   f'<p class="files-meta">{esc(t["backup_contents"])}</p>'
                   + (f'<ul class="files-list">{"".join(rows)}</ul>' if rows else
                      f'<p class="files-empty">{esc(t["backup_empty"])}</p>') + '</section>')
        upload = (f'<section class="card frp-card"><h2 class="frp-instances-heading">{esc(t["backup_upload"])}</h2>'
                  f'<p class="files-meta">{esc(t["backup_upload_help"])}</p>'
                  f'<form class="backup-upload" data-csrf="{csrf}" data-max="{MAX_UPLOAD}" '
                  f'data-too-big="{esc(t["backup_error_invalid"], quote=True)}" '
                  f'data-failed="{esc(t["backup_error_failed"], quote=True)}">'
                  f'<input type="file" accept=".gz,.tar.gz,application/gzip" required> '
                  f'<button type="submit" class="files-button">{esc(t["backup_upload_button"])}</button>'
                  f' <output role="status"></output></form></section>')
        body = (f'<h1>{esc(t["backup"])}</h1><div class="frp-workspace files-page">{"".join(messages)}'
                f'{schedule}{listing}{upload}</div>'
                '<script src="/static/backup.js" defer></script>')
        return self.send_html(200, self.render_page(t["backup"], body, lang, icon="files", back_href="/"),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def route_backup(self, method, path, parsed, lang, query_lang):
        if not path.startswith("/backup"):
            return False
        if method == "GET" and path == "/backup":
            self.page_backup(lang, query_lang, parsed)
        elif method == "GET" and path == "/backup/download":
            self.handle_backup_download(parsed)
        elif method == "POST" and path == "/backup/upload":
            self.handle_backup_upload(parsed)
        elif method == "POST" and path == "/backup/create":
            self.handle_backup_create()
        elif method == "POST" and path == "/backup/settings":
            self.handle_backup_settings()
        elif method == "POST" and path == "/backup/delete":
            self.handle_backup_delete()
        elif method == "POST" and path == "/backup/restore":
            self.handle_backup_restore()
        else:
            return False
        return True

    def handle_backup_create(self):
        if self.backup_form(()) is None:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        try:
            config_backup.create_backup("manual")
        except config_backup.BackupError as exc:
            return self.backup_done(error="no_space" if "space" in str(exc) else "failed")
        return self.backup_done("created")

    def handle_backup_settings(self):
        form = self.backup_form(("enabled", "time", "keep"))
        if form is None or "time" not in form or "keep" not in form:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        try:
            settings = scheduler.parse_backup_settings(form.get("enabled") == "1", form["time"], form["keep"])
            self.context.SCHEDULER.save_backup_settings(settings)
        except (scheduler.ScheduleError, OSError):
            return self.backup_done(error="invalid")
        return self.backup_done("settings")

    def handle_backup_delete(self):
        form = self.backup_form(("name",))
        if form is None or "name" not in form:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        try:
            config_backup.delete_backup(form["name"])
        except config_backup.BackupError:
            return self.backup_done(error="not_found")
        return self.backup_done("deleted")

    def handle_backup_download(self, parsed):
        name = self.context.parse_qs(parsed.query).get("name", [""])[0]
        try:
            path = config_backup.backup_path(name)
            size = path.stat().st_size
        except (config_backup.BackupError, OSError):
            return self.send_html(404, "Not found", {"Cache-Control": "no-store"})
        self.send_response(200)
        self.send_header("Content-Type", "application/gzip")
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)
        return None

    def handle_backup_upload(self, parsed):
        token = self.context.parse_qs(parsed.query).get("csrf", [""])[0]
        if not token or not self.context.hmac.compare_digest(token, self.backup_csrf()):
            return self.send_json(403, {"error": "forbidden"})
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self.send_json(411, {"error": "length_required"})
        if not 0 < length <= MAX_UPLOAD:
            return self.send_json(400, {"error": "invalid"})
        directory = config_backup.backup_dir()
        directory.mkdir(parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        descriptor, temporary = tempfile.mkstemp(prefix=".upload-", dir=directory)
        self.connection.settimeout(UPLOAD_IDLE_TIMEOUT)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                remaining = length
                while remaining:
                    chunk = self.rfile.read(min(remaining, 1024 * 1024))
                    if not chunk:
                        raise OSError("short upload")
                    handle.write(chunk)
                    remaining -= len(chunk)
            os.chmod(temporary, 0o600)
            config_backup.validate_archive(temporary)
            config_backup.publish(temporary, "manual")
        except config_backup.BackupError:
            Path(temporary).unlink(missing_ok=True)
            return self.send_json(400, {"error": "invalid"})
        except OSError:
            Path(temporary).unlink(missing_ok=True)
            self.close_connection = True
            return None
        finally:
            try:
                self.connection.settimeout(None)
            except OSError:
                pass
        return self.send_json(200, {"ok": True})

    def handle_backup_restore(self):
        form = self.backup_form(("name",))
        if form is None or "name" not in form:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        try:
            path = config_backup.backup_path(form["name"])
            config_backup.validate_archive(path)
        except config_backup.BackupError:
            return self.backup_done(error="not_found")
        unit = "vps-server-restore-" + secrets.token_hex(4)
        try:
            subprocess.run(["systemd-run", "--quiet", "--collect", "--unit=" + unit, "/bin/bash", "-c",
                            RESTORE_SCRIPT, "restore", str(self.context.WEB_CODE_DIR / "config_backup.py"), str(path)],
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=30, check=True)
        except (OSError, subprocess.SubprocessError):
            return self.backup_done(error="failed")
        return self.backup_done("restore_started")
