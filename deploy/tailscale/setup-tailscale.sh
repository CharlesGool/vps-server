#!/usr/bin/env bash
set -euo pipefail

PREFIX="${PREFIX:-/root/apps/vps-server}"
ARCHIVE="${1:-$PREFIX/installer-source/third_party/tailscale/tailscale_1.102.4_amd64.tgz}"
SHA256="50748df1045e60b5b695f19f4c56b0da36c019948b440fb456b6584a50f0d8b9"
ROOT="tailscale_1.102.4_amd64"
UNIT=/etc/systemd/system/vps-server-tailscale.service
STATE="${VPSSRV_STATE_DIR:-/var/lib/vps-server}/tailscale"
PORT=41641

[ "$(id -u)" -eq 0 ] || { echo 'Root required' >&2; exit 1; }
[ -f "$ARCHIVE" ] || { echo 'Bundled Tailscale asset missing' >&2; exit 1; }
printf '%s  %s\n' "$SHA256" "$ARCHIVE" | sha256sum -c - >/dev/null
if systemctl is-active --quiet tailscaled.service; then
  echo 'An existing Tailscale daemon is active; refusing a second instance' >&2
  exit 1
fi

PORT_ADDED="$(python3 - "$PREFIX" "$PORT" <<'PY'
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
        raise SystemExit('Tailscale port already registered')
    if not current:
        available(port)
        rows.append((port, 'vps-server / Tailscale', '0.0.0.0', date.today().isoformat()))
        write_rows(root / 'PORTS.md', rows)
        print('new')
PY
)"
OPTIONAL_ADDED='[]'
rollback_port() {
  local status=$?
  if [ "$status" -ne 0 ]; then
    python3 - "$PREFIX" "$OPTIONAL_ADDED" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / 'src' / 'web'))
from console_port import release_owned_port
for port, owner in reversed(json.loads(sys.argv[2])):
    release_owned_port(sys.argv[1], port, owner)
PY
  fi
  if [ "$status" -ne 0 ] && [ "$PORT_ADDED" = new ]; then
    python3 - "$PREFIX" "$PORT" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / 'src' / 'web'))
from console_port import release_owned_port
release_owned_port(sys.argv[1], int(sys.argv[2]), 'vps-server / Tailscale')
PY
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
trap 'rm -rf -- "$tmp"' EXIT
tar -xzf "$ARCHIVE" -C "$tmp" "$ROOT/tailscale" "$ROOT/tailscaled"
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
