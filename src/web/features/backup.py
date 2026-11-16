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
import secure_store
from features import schedule_form

MAX_UPLOAD = 256 * 1024 * 1024
UPLOAD_IDLE_TIMEOUT = 60
NOTICES = ("created", "deleted", "settings", "restore_started", "uploaded", "key_set")
ERRORS = ("failed", "invalid", "not_found", "no_space", "busy", "key_wrong", "key_needed", "ack_needed", "past")
KIND_KEYS = {"manual": "backup_kind_manual", "scheduled": "backup_kind_scheduled",
             "pre-upgrade": "backup_kind_pre_upgrade", "pre-restore": "backup_kind_pre_restore"}
# Restart order after a restore: meters first (they take their dependents along),
# then the services that read restored files, the console last.
RESTORE_SCRIPT = (
    'set -e; python3 "$1" restore "$2"; systemctl daemon-reload; '
    'for u in vps-server-node-meter vps-server-frps-meter vps-server-traffic-meter '
    'vps-server-tailscale vps-server-caddy vps-server-proxy vps-server-frps; do '
    'systemctl try-restart "$u.service" || true; done; systemctl restart vps-server-web.service')
RESTORE_SCRIPT = RESTORE_SCRIPT.replace('python3 "$1" restore "$2";', 'python3 "$1" restore "$2" ${3:+--private-key-file "$3"};')


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
        tones = {"ok": "success", "failed": "danger", "timeout": "warning", "skipped": ""}
        if last:
            last_text = (f'{esc(t["backup_last"])}: {esc(local_time(last["started"]))} '
                         f'<span class="tag" data-tone="{tones[last["status"]]}">{esc(t["task_status_" + last["status"]])}</span>')
        else:
            last_text = f'{esc(t["backup_last"])}: {esc(t["backup_never"])}'
        state_tag = (f'<span class="tag" data-tone="success">{esc(schedule_form.describe(t, settings["spec"]))} · '
                     f'{esc(t["backup_keep"])} {settings["keep"]}</span>' if settings["enabled"]
                     else f'<span class="tag">{esc(t["task_disabled"])}</span>')
        schedule = (f'<section class="card wide sched-card"><div class="sched-card-head">'
                    f'<h2>{esc(t["backup_schedule"])}</h2>{state_tag}</div>'
                    f'<p class="muted small">{esc(t["backup_schedule_help"])}</p>'
                    f'<form method="post" action="/backup/settings" class="task-form">{hidden}'
                    f'<label class="sched-check is-wide"><input type="checkbox" name="enabled" value="1"{" checked" if settings["enabled"] else ""}>'
                    f'<span>{esc(t["backup_enabled"])}</span></label>'
                    + schedule_form.fields_html(self.context, t, settings["spec"])
                    + f'<label class="sched-field"><span>{esc(t["backup_keep"])}</span>'
                    f'<input type="number" name="keep" min="1" max="{scheduler.BACKUP_KEEP_MAX}" value="{settings["keep"]}" required></label>'
                    f'<div class="task-form-actions is-wide"><button type="submit">{esc(t["backup_save"])}</button></div></form>'
                    f'<p class="sched-status">{last_text}'
                    + (f'<span>{esc(t["backup_next"])}: {esc(local_time(following))}</span>' if following else '')
                    + '</p></section>')

        rows = []
        for item in config_backup.list_backups():
            name = esc(item["name"], quote=True)
            tone = {"manual": "", "scheduled": "primary", "pre-upgrade": "success", "pre-restore": "warning"}[item["kind"]]
            rows.append(
                f'<li class="sched-item"><div class="sched-item-main"><div class="sched-item-title">'
                f'<span class="tag" data-tone="{tone}">{esc(t[KIND_KEYS[item["kind"]]])}</span>'
                + (f'<span class="tag" data-tone="success">{esc(t["backup_sealed_tag"])}</span>' if item["sealed"] else '')
                + (f'<span class="tag" data-tone="warning">{esc(t["backup_other_key_tag"])}</span>' if item["key_match"] is False else '')
                + f'<span>{esc(local_time(item["created"]))}</span>'
                f'<span class="sched-item-size">{esc(human_size(item["size"]))}</span></div>'
                f'<div class="sched-item-meta"><code class="sched-code">{esc(item["name"])}</code></div></div>'
                f'<div class="sched-item-actions">'
                f'<a class="files-button" href="/backup/download?name={name}" download>{esc(t["backup_download"])}</a>'
                f'<a class="files-button" href="/backup/restore?name={name}">{esc(t["backup_restore"])}</a>'
                f'<form method="post" action="/backup/delete" class="backup-confirm" '
                f'data-confirm="{esc(t["backup_delete_confirm"], quote=True)}">{hidden}'
                f'<input type="hidden" name="name" value="{name}">'
                f'<button type="submit" class="files-button files-danger">{esc(t["backup_delete"])}</button></form>'
                f'</div></li>')
        listing = (f'<section class="card wide sched-card"><div class="sched-card-head">'
                   f'<h2>{esc(t["backup_list"])}</h2>'
                   f'<form method="post" action="/backup/create" style="margin:0">{hidden}'
                   f'<button type="submit">{esc(t["backup_create"])}</button></form></div>'
                   f'<p class="muted small">{esc(t["backup_contents"])}</p>'
                   + (f'<ul class="sched-list">{"".join(rows)}</ul>' if rows else
                      f'<p class="sched-empty">{esc(t["backup_empty"])}</p>') + '</section>')
        upload = (f'<section class="card wide sched-card"><div class="sched-card-head"><h2>{esc(t["backup_upload"])}</h2></div>'
                  f'<p class="muted small">{esc(t["backup_upload_help"])}</p>'
                  f'<form class="file-pick backup-upload" data-csrf="{csrf}" data-max="{MAX_UPLOAD}" '
                  f'data-too-big="{esc(t["backup_error_invalid"], quote=True)}" '
                  f'data-failed="{esc(t["backup_error_failed"], quote=True)}">'
                  f'<label class="files-pick files-button"><input type="file" accept=".gz,.tar.gz,application/gzip" required>'
                  f'{esc(t["files_choose"])}</label>'
                  f'<span class="files-pick-name" aria-live="polite" data-empty="{esc(t["files_no_file"], quote=True)}">'
                  f'{esc(t["files_no_file"])}</span>'
                  f'<button type="submit">{esc(t["backup_upload_button"])}</button>'
                  f'<output role="status"></output></form></section>')
        recipient = config_backup.read_recipient()
        if recipient is not None:
            key_state = (f'<span class="tag" data-tone="success">{esc(t["backup_enc_on"])}</span>')
            key_text = esc(t["backup_enc_on_text"].format(fp=config_backup.key_fingerprint(recipient)))
        else:
            key_state = f'<span class="tag" data-tone="warning">{esc(t["backup_enc_off"])}</span>'
            key_text = esc(t["backup_enc_off_text"])
        regenerate = (f' data-confirm="{esc(t["backup_enc_regenerate_confirm"], quote=True)}"' if recipient is not None else "")
        key_card = (f'<section class="card wide sched-card"><div class="sched-card-head"><h2>{esc(t["backup_enc_title"])}</h2>{key_state}</div>'
                    f'<p class="muted small">{key_text}</p>'
                    f'<form method="post" action="/backup/key/new" class="backup-confirm"{regenerate} style="margin:0">{hidden}'
                    f'<button type="submit">{esc(t["backup_enc_generate"])}</button></form>'
                    f'<form method="post" action="/backup/key/set" class="sched-form">{hidden}'
                    f'<label class="sched-field"><span>{esc(t["backup_enc_own"])}</span>'
                    f'<input type="text" name="public" class="is-mono" spellcheck="false" autocomplete="off" maxlength="64" required '
                    f'placeholder="{esc(t["backup_enc_own_placeholder"], quote=True)}"></label>'
                    f'<button type="submit">{esc(t["backup_save"])}</button></form></section>')
        try:
            files = secure_store.status()
            encrypted = sum(1 for _path, state in files if state == "encrypted")
            data_text = t["data_enc_on_text"].format(encrypted=encrypted, total=len(files))
            data_state = (f'<span class="tag" data-tone="success">{esc(t["data_enc_on"])}</span>' if secure_store.enabled()
                          else f'<span class="tag" data-tone="warning">{esc(t["data_enc_off"])}</span>')
            if not secure_store.enabled():
                data_text = t["data_enc_off_text"]
        except (OSError, ValueError):
            data_state, data_text = f'<span class="tag" data-tone="danger">{esc(t["data_enc_error"])}</span>', t["data_enc_error_text"]
        data_card = (f'<section class="card wide sched-card"><div class="sched-card-head"><h2>{esc(t["data_enc_title"])}</h2>{data_state}</div>'
                     f'<p class="muted small">{esc(data_text)}</p></section>')
        outcome = config_backup.read_result()
        result_card = ""
        if outcome:
            if outcome["ok"]:
                text = t["backup_result_ok"].format(files=outcome.get("restored", 0), name=outcome.get("name", ""))
                tag = f'<span class="tag" data-tone="success">{esc(t["task_status_ok"])}</span>'
            else:
                text = t["backup_result_failed"].format(name=outcome.get("name", ""), error=outcome.get("error", ""))
                tag = f'<span class="tag" data-tone="danger">{esc(t["task_status_failed"])}</span>'
            result_card = (f'<section class="card wide sched-card"><div class="sched-card-head"><h2>{esc(t["backup_result_title"])}</h2>{tag}</div>'
                           f'<p class="muted small">{esc(local_time(outcome.get("time", 0)))} · {esc(text)}</p></section>')
        body = (f'<h1>{esc(t["backup"])}</h1><div class="frp-workspace files-page">{"".join(messages)}'
                f'{result_card}{schedule}{listing}{key_card}{upload}{data_card}</div>'
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
        elif method == "GET" and path == "/backup/restore":
            self.page_backup_restore(lang, query_lang, self.context.parse_qs(parsed.query).get("name", [""])[0])
        elif method == "POST" and path == "/backup/restore/open":
            self.handle_backup_restore_open(lang, query_lang)
        elif method == "POST" and path == "/backup/restore":
            self.handle_backup_restore()
        elif method == "POST" and path == "/backup/key/new":
            self.handle_backup_key_new(lang)
        elif method == "POST" and path == "/backup/key/set":
            self.handle_backup_key_set()
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
        form = self.backup_form(("enabled", "keep") + schedule_form.FORM_FIELDS)
        if form is None or "kind" not in form or "keep" not in form:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        try:
            settings = scheduler.parse_backup_settings(form.get("enabled") == "1", schedule_form.spec_from_form(form),
                                                       form["keep"], self.context.SCHEDULER.clock())
            self.context.SCHEDULER.save_backup_settings(settings)
        except scheduler.ScheduleError as exc:
            return self.backup_done(error="past" if "passed" in str(exc) else "invalid")
        except OSError:
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
            stored = config_backup.publish(temporary, "manual", suffix=".sealed" if config_backup.is_sealed(temporary) else "")
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
        return self.send_json(200, {"ok": True, "name": stored})

    # -- restore: look first, then confirm ------------------------------------------

    def restore_target(self, name):
        """(path, None) for a listed backup, or (None, error code)."""
        try:
            path = config_backup.backup_path(name)
            config_backup.validate_archive(path)
        except config_backup.BackupError:
            return None, "not_found"
        return path, None

    def render_restore_page(self, lang, query_lang, path, info, private_key="", error=None, status=200):
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        csrf = esc(self.backup_csrf(), quote=True)
        name = esc(path.name, quote=True)
        hidden = f'<input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="name" value="{name}">'
        message = f'<p class="error" role="alert">{esc(t["backup_error_" + error])}</p>' if error else ""
        back = f'<a class="files-button" href="/backup">{esc(t["task_cancel"])}</a>'
        if not info["readable"]:
            # A sealed backup: say what its header says, then ask for the key to look inside.
            note = ""
            if info["key_match"] is False:
                note = f'<p class="error" role="status">{esc(t["backup_restore_other_key"])}</p>'
            elif info["key_match"] is True:
                note = f'<p class="muted small">{esc(t["backup_restore_this_key"])}</p>'
            body = (f'<section class="card wide sched-card"><div class="sched-card-head"><h2>{esc(t["backup_restore_title"])}</h2>'
                    f'<span class="tag" data-tone="success">{esc(t["backup_sealed_tag"])}</span></div>'
                    f'<p><code class="sched-code">{esc(path.name)}</code></p>{message}'
                    f'<p class="muted small">{esc(t["backup_restore_needs_key"])}</p>{note}'
                    f'<form method="post" action="/backup/restore/open" class="sched-form">{hidden}'
                    f'<label class="sched-field"><span>{esc(t["backup_restore_key"])}</span>'
                    f'<input type="password" name="private_key" class="is-mono" autocomplete="off" required spellcheck="false" maxlength="64"></label>'
                    f'<button type="submit">{esc(t["backup_restore_look"])}</button> {back}</form></section>')
        else:
            def row(label, value):
                return f'<div><dt>{esc(label)}</dt><dd>{esc(str(value))}</dd></div>'
            details = (row(t["backup_restore_host"], info["host"] or "?") + row(t["backup_restore_version"], info["version"] or "?")
                       + row(t["backup_restore_kind"], t[KIND_KEYS[info["kind"]]] if info["kind"] in KIND_KEYS else info["kind"])
                       + row(t["backup_restore_created"], local_time(info["created"])) + row(t["backup_restore_files"], info["files"]))
            warnings = ""
            if not info["same_host"]:
                warnings += f'<p class="error" role="status">{esc(t["backup_restore_warn_host"].format(host=info["host"] or "?"))}</p>'
            if info["newer"]:
                warnings += f'<p class="error" role="status">{esc(t["backup_restore_warn_newer"].format(version=info["version"]))}</p>'
            ack = (f'<label class="sched-check"><input type="checkbox" name="ack" value="1" required>'
                   f'<span>{esc(t["backup_restore_ack"])}</span></label>' if info["risky"] else "")
            key_field = (f'<input type="hidden" name="private_key" value="{esc(private_key, quote=True)}">'
                         if info["sealed"] else "")
            body = (f'<section class="card wide sched-card"><div class="sched-card-head"><h2>{esc(t["backup_restore_title"])}</h2>'
                    + (f'<span class="tag" data-tone="success">{esc(t["backup_sealed_tag"])}</span>' if info["sealed"] else "")
                    + f'</div><p><code class="sched-code">{esc(path.name)}</code></p>{message}'
                    f'<dl class="backup-details">{details}</dl>{warnings}'
                    f'<p class="muted small">{esc(t["backup_restore_effect"])}</p>'
                    f'<form method="post" action="/backup/restore" class="sched-form">{hidden}{key_field}{ack}'
                    f'<button type="submit" class="danger">{esc(t["backup_restore_go"])}</button> {back}</form></section>')
        page = f'<h1>{esc(t["backup_restore_title"])}</h1><div class="frp-workspace files-page">{body}</div>'
        return self.send_html(status, self.render_page(t["backup_restore_title"], page, lang, icon="files", back_href="/backup"),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def page_backup_restore(self, lang, query_lang, name):
        path, error = self.restore_target(name)
        if error:
            return self.backup_done(error=error)
        shown = self.context.parse_qs(self.context.urlsplit(self.path).query).get("error", [""])[0]
        return self.render_restore_page(lang, query_lang, path, config_backup.inspect(path),
                                        error=shown if shown in ("ack_needed",) else None)

    def handle_backup_restore_open(self, lang, query_lang):
        form = self.backup_form(("name", "private_key"))
        if form is None or "name" not in form:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        path, error = self.restore_target(form["name"])
        if error:
            return self.backup_done(error=error)
        try:
            key = config_backup.parse_key(form.get("private_key", ""))
            info = config_backup.inspect(path, key)
        except config_backup.BackupError:
            return self.render_restore_page(lang, query_lang, path, config_backup.inspect(path), error="key_wrong", status=200)
        return self.render_restore_page(lang, query_lang, path, info, private_key=form["private_key"].strip())

    def handle_backup_restore(self):
        form = self.backup_form(("name", "private_key", "ack"))
        if form is None or "name" not in form:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        path, error = self.restore_target(form["name"])
        if error:
            return self.backup_done(error=error)
        key_file = None
        try:
            key = None
            if config_backup.is_sealed(path):
                if not form.get("private_key", "").strip():
                    return self.backup_done(error="key_needed")
                key = config_backup.parse_key(form["private_key"])
            # Decided here again, not trusted from the page: a backup from another host or a newer
            # version is restored only when the operator has said so.
            info = config_backup.inspect(path, key)
            if info.get("risky") and form.get("ack") != "1":
                return self.redirect(f"/backup/restore?name={path.name}&error=ack_needed", {"Cache-Control": "no-store"})
            if key is not None:
                descriptor, name = tempfile.mkstemp(prefix=".restore-key-", dir=path.parent)
                with os.fdopen(descriptor, "w", encoding="ascii") as handle:
                    handle.write(form["private_key"].strip() + "\n")
                os.chmod(name, 0o600)
                key_file = name
        except config_backup.BackupError as exc:
            return self.backup_done(error="key_wrong" if "key" in str(exc) else "not_found")
        unit = "vps-server-restore-" + secrets.token_hex(4)
        command = ["systemd-run", "--quiet", "--collect", "--unit=" + unit, "/bin/bash", "-c", RESTORE_SCRIPT, "restore",
                   str(self.context.WEB_CODE_DIR / "config_backup.py"), str(path)]
        if key_file:
            command.append(key_file)
        try:
            subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=30, check=True)
        except (OSError, subprocess.SubprocessError):
            if key_file:
                Path(key_file).unlink(missing_ok=True)
            return self.backup_done(error="failed")
        return self.backup_done("restore_started")

    def handle_backup_key_new(self, lang):
        form = self.backup_form(())
        if form is None:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        try:
            private, public = config_backup.new_recipient()
        except OSError:
            return self.backup_done(error="failed")
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        body = (f'<h1>{esc(t["backup_key_page_title"])}</h1><div class="frp-workspace files-page">'
                f'<section class="card wide sched-card"><p class="error" role="alert">{esc(t["backup_key_page_text"])}</p>'
                + self.context.render_copyable(t, t["backup_key_private"], private, "backup-private-key")
                + self.context.render_copyable(
                    t, f'{t["backup_key_public"]} · {config_backup.key_fingerprint(config_backup.parse_key(public))}',
                    public, "backup-public-key")
                + f'<p><a class="files-button" href="/backup">{esc(t["backup_key_done"])}</a></p></section></div>'
                + '<script src="/static/copy.js"></script>')
        return self.send_html(200, self.render_page(t["backup_key_page_title"], body, lang, icon="files", back_href="/backup"),
                              {"Cache-Control": "no-store"})

    def handle_backup_key_set(self):
        form = self.backup_form(("public",))
        if form is None or "public" not in form:
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        try:
            config_backup.set_recipient(config_backup.parse_key(form["public"]))
        except (config_backup.BackupError, OSError):
            return self.backup_done(error="invalid")
        return self.backup_done("key_set")
