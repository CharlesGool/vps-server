#!/usr/bin/env bash
set -euo pipefail

PREFIX="${PREFIX:-/root/apps/vps-server}"
ARCHIVE="${1:-$PREFIX/installer-source/third_party/tailscale/tailscale_1.102.4_amd64.tgz}"
SHA256="50748df1045e60b5b695f19f4c56b0da36c019948b440fb456b6584a50f0d8b9"
ROOT="tailscale_1.102.4_amd64"
UNIT=/etc/systemd/system/vps-server-tailscale.service
STATE="${VPSSRV_STATE_DIR:-/var/lib/vps-server}/tailscale"
PORT=41641
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
case "${VPSSRV_DEFAULT_LANG:-en}" in
  zh_cn) CATALOG_LANG=zh-CN ;;
  es) CATALOG_LANG=es ;;
  *) CATALOG_LANG=en ;;
esac
CATALOG_ROOT="${VPSSRV_CATALOG_ROOT:-}"
if [ -z "$CATALOG_ROOT" ]; then
  if [ -d "$SCRIPT_DIR/../../lang/tailscale" ]; then CATALOG_ROOT="$SCRIPT_DIR/../../lang"
  else CATALOG_ROOT="$PREFIX/lang"; fi
fi
msg() {
  local key="$1"; shift
  local fmt
  # shellcheck disable=SC1090
  source "$CATALOG_ROOT/tailscale/$CATALOG_LANG.sh"
  # shellcheck disable=SC2059  # fmt comes from the trusted catalog.
  printf "$fmt\n" "$@"
}

[ "$(id -u)" -eq 0 ] || { msg root_required >&2; exit 1; }
[ -f "$ARCHIVE" ] || { msg asset_missing >&2; exit 1; }
printf '%s  %s\n' "$SHA256" "$ARCHIVE" | sha256sum -c - >/dev/null || { msg integrity_failure >&2; exit 1; }
if systemctl is-active --quiet tailscaled.service; then
  msg daemon_active >&2
  exit 1
fi

export TAILSCALE_MSG_PORT_REGISTERED="$(msg port_registered)"
PORT_ADDED="$(python3 - "$PREFIX" "$PORT" <<'PY'
import os
import fcntl
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]) / 'src' / 'web'))
from console_port import available, read_rows, write_rows

port = int(sys.argv[2])
root = Path(sys.argv[1]).parent
root.mkdir(parents=True, exist_ok=True)
with (root / '.ports.lock').open('a+') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    rows, _ = read_rows(root / 'PORTS.md')
    current = [row for row in rows if row[0] == port]
    if current and current[0][1] != 'vps-server / Tailscale':
        raise SystemExit(os.environ['TAILSCALE_MSG_PORT_REGISTERED'])
    if not current:
        available(port)
        rows.append((port, 'vps-server / Tailscale', '0.0.0.0', date.today().isoformat()))
        write_rows(root / 'PORTS.md', rows)
        print('new')
PY
)"
OPTIONAL_ADDED='[]'
tmp=""
UNIT_EXISTED=0
[ ! -e "$UNIT" ] || UNIT_EXISTED=1
rollback_port() {
  local status=$?
  [ -z "$tmp" ] || rm -rf -- "$tmp"
  if [ "$status" -ne 0 ]; then
    python3 - "$PREFIX" "$OPTIONAL_ADDED" <<'PY' || true
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / 'src' / 'web'))
from console_port import release_owned_port
for port, owner in reversed(json.loads(sys.argv[2])):
    release_owned_port(sys.argv[1], port, owner)
PY
  fi
  if [ "$status" -ne 0 ] && [ "$PORT_ADDED" = new ]; then
    python3 - "$PREFIX" "$PORT" <<'PY' || true
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / 'src' / 'web'))
from console_port import release_owned_port
release_owned_port(sys.argv[1], int(sys.argv[2]), 'vps-server / Tailscale')
PY
  fi
  # Ports first: a cleanup step that fails must not skip their release.
  # A failed first installation then leaves no unit or binaries behind; an
  # existing installation keeps them, as before.
  if [ "$status" -ne 0 ] && [ "$UNIT_EXISTED" = 0 ]; then
    systemctl disable --now vps-server-tailscale.service >/dev/null 2>&1 || true
    rm -f -- "$UNIT" /usr/local/bin/tailscale-vps-server /usr/local/bin/tailscaled-vps-server || true
    systemctl daemon-reload || true
  fi
}
trap rollback_port EXIT
OPTIONAL_ADDED="$(python3 - "$PREFIX" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / 'src' / 'web'))
from module_manager import reserve_saved_tailscale_ports
print(json.dumps(reserve_saved_tailscale_ports(sys.argv[1])))
PY
)"

tmp="$(mktemp -d)"
# tarfile reads gzip itself, so hosts without the tar or gzip binaries work too.
python3 -c 'import sys, tarfile
with tarfile.open(sys.argv[1], "r:gz") as archive:
    for member in sys.argv[3:]:
        archive.extract(member, sys.argv[2])' "$ARCHIVE" "$tmp" "$ROOT/tailscale" "$ROOT/tailscaled"
install -m 0755 "$tmp/$ROOT/tailscale" /usr/local/bin/tailscale-vps-server
install -m 0755 "$tmp/$ROOT/tailscaled" /usr/local/bin/tailscaled-vps-server
mkdir -p -m 0700 "$STATE"
cat > "$UNIT" <<EOF
[Unit]
Description=vps-server Tailscale client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
RuntimeDirectory=vps-server-tailscale
ExecStart=/usr/local/bin/tailscaled-vps-server --state=$STATE/tailscaled.state --socket=/run/vps-server-tailscale/tailscaled.sock --port=$PORT
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable vps-server-tailscale.service
systemctl restart vps-server-tailscale.service
systemctl is-active --quiet vps-server-tailscale.service
python3 - "$PREFIX" <<'PY' || {
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / 'src' / 'web'))
from module_manager import sync_tailscale_ports
sync_tailscale_ports(sys.argv[1])
PY
  systemctl disable --now vps-server-tailscale.service >/dev/null 2>&1 || true
  exit 1
}
