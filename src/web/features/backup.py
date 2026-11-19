"""Configuration backups: the download route, restore checks and the restart script (the page is the single-page UI).

Host dependencies come from ``ConsoleHandler.context``. Creating a backup only
reads files, so the console does it itself; restoring writes system files, so
it runs through ``systemd-run`` outside the console's read-only sandbox.
"""

import time

import config_backup

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


def local_time(stamp):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(stamp)) if stamp else "—"


class BackupMixin:


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


    # -- restore: look first, then confirm ------------------------------------------

    def restore_target(self, name):
        """(path, None) for a listed backup, or (None, error code)."""
        try:
            path = config_backup.backup_path(name)
            config_backup.validate_archive(path)
        except config_backup.BackupError:
            return None, "not_found"
        return path, None
