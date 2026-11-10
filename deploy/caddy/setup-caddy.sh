#!/usr/bin/env bash
# Install the domain forwarding module: a verified Caddy on ports 80 and 443.
# While it is enabled the console's public reachability page stays off; the
# console checks whether vps-server-caddy.service is enabled when it starts.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
INSTALL_LANG="${VPSSRV_DEFAULT_LANG:-en}"
case "$INSTALL_LANG" in
  zh_cn) CATALOG_LANG=zh-CN ;;
  en|es) CATALOG_LANG="$INSTALL_LANG" ;; *) CATALOG_LANG=en ;;
esac
CATALOG_ROOT="${VPSSRV_CATALOG_ROOT:-}"
if [ -z "$CATALOG_ROOT" ]; then
  if [ -d "$SCRIPT_DIR/../../lang/caddy" ]; then CATALOG_ROOT="$SCRIPT_DIR/../../lang"
  else CATALOG_ROOT="${PREFIX:-/root/apps/vps-server}/lang"; fi
fi
msg() {
  local key="$1"; shift
  local fmt=''
  # shellcheck disable=SC1090
  source "$CATALOG_ROOT/caddy/$CATALOG_LANG.sh"
  # shellcheck disable=SC2059  # The catalog holds the format.
  printf "$fmt\n" "$@"
}
[ "$(id -u)" -eq 0 ] || { msg root_required >&2; exit 1; }

PREFIX_DIR="$(cd "${PREFIX:-/root/apps/vps-server}" 2>/dev/null && pwd -P || :)"
if [ "$SCRIPT_DIR" = "$PREFIX_DIR/caddy" ]; then
  BIN="$SCRIPT_DIR/../vendor/caddy/caddy"
else
  BIN="$SCRIPT_DIR/../../third_party/caddy/caddy"
fi
HELPER="${PREFIX_DIR:-${PREFIX:-/root/apps/vps-server}}/src/web/caddy_sites.py"
TARGET=/usr/local/bin/caddy-vps-server
CONFIG_DIR=/etc/vps-server-caddy
DATA_DIR=/var/lib/vps-server-caddy
UNIT=/etc/systemd/system/vps-server-caddy.service
DNS_UNIT=/etc/systemd/system/vps-server-caddy-dns.service
DNS_TIMER=/etc/systemd/system/vps-server-caddy-dns.timer
ACCOUNT=vps-server-caddy
[ -f "$BIN" ] && [ "$(sha256sum "$BIN" | cut -d' ' -f1)" = a563843e11cbce39c557bd429ebb787d56f49d51d9bbb3292cd9b36b37a60cdf ] ||
  { msg integrity_failure >&2; exit 1; }

# Only this project's console may hold 80/443 now; it lets go when Caddy is enabled.
web_pid="$(systemctl show -p MainPID --value vps-server-web.service 2>/dev/null || echo 0)"
caddy_pid="$(systemctl show -p MainPID --value vps-server-caddy.service 2>/dev/null || echo 0)"
for port in 80 443; do
  holders="$(ss -H -ltnp "( sport = :$port )" 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u || true)"
  for pid in $holders; do
    [ "$pid" = "$web_pid" ] || [ "$pid" = "$caddy_pid" ] || { msg port_busy "$port" >&2; exit 1; }
  done
done

getent group "$ACCOUNT" >/dev/null || groupadd --system "$ACCOUNT"
getent passwd "$ACCOUNT" >/dev/null ||
  useradd --system --gid "$ACCOUNT" --home-dir "$DATA_DIR" --no-create-home --shell /usr/sbin/nologin "$ACCOUNT"
install -d -m 0750 -o root -g "$ACCOUNT" "$CONFIG_DIR"
install -d -m 0700 -o "$ACCOUNT" -g "$ACCOUNT" "$DATA_DIR"
install -m 0755 "$BIN" "$TARGET"
/usr/bin/python3 "$HELPER" render
"$TARGET" validate --config "$CONFIG_DIR/caddy.json" >/dev/null

cat > "$UNIT" <<'EOF'
[Unit]
Description=vps-server domain forwarding (Caddy on 80/443)
After=network-online.target vps-server-web.service
Wants=network-online.target
[Service]
Type=notify
User=vps-server-caddy
Group=vps-server-caddy
Environment=HOME=/var/lib/vps-server-caddy XDG_DATA_HOME=/var/lib/vps-server-caddy XDG_CONFIG_HOME=/var/lib/vps-server-caddy
ExecStart=/usr/local/bin/caddy-vps-server run --config /etc/vps-server-caddy/caddy.json
ExecReload=/usr/local/bin/caddy-vps-server reload --config /etc/vps-server-caddy/caddy.json --address unix//run/vps-server-caddy/admin.sock --force
RuntimeDirectory=vps-server-caddy
RuntimeDirectoryMode=0750
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/vps-server-caddy
LimitNOFILE=1048576
TimeoutStopSec=5s
Restart=on-failure
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF
cat > "$DNS_UNIT" <<EOF
[Unit]
Description=vps-server domain forwarding: Cloudflare DNS records
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 $HELPER ddns
EOF
cat > "$DNS_TIMER" <<'EOF'
[Unit]
Description=vps-server domain forwarding: check DNS records every 5 minutes
[Timer]
OnBootSec=1min
OnUnitActiveSec=5min
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload

was_enabled=0
systemctl is-enabled --quiet vps-server-caddy.service && was_enabled=1
systemctl enable vps-server-caddy.service >/dev/null
# The console reads the enabled state at start and leaves 80/443 to Caddy.
if systemctl is-active --quiet vps-server-web.service; then
  systemctl restart vps-server-web.service
fi
if ! systemctl restart vps-server-caddy.service || ! systemctl is-active --quiet vps-server-caddy.service; then
  [ "$was_enabled" = 1 ] || systemctl disable --now vps-server-caddy.service >/dev/null 2>&1 || true
  if systemctl is-active --quiet vps-server-web.service; then systemctl restart vps-server-web.service || true; fi
  msg start_failed >&2
  exit 1
fi
systemctl enable --now vps-server-caddy-dns.timer >/dev/null

# Open 80/443 only in a firewall that is on, and remember which rules are ours.
backend=''
if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q 'Status: active'; then backend=ufw
elif command -v firewall-cmd >/dev/null && firewall-cmd --state >/dev/null 2>&1; then backend=firewalld; fi
if [ -z "$backend" ]; then
  msg no_firewall
else
  for port in 80 443; do
    owner="$CONFIG_DIR/firewall-owned-$port"
    [ ! -f "$owner" ] || continue
    case "$backend" in
      ufw) ufw status | grep -Eq "^${port}/tcp[[:space:]]" && continue
           ufw allow "${port}/tcp" >/dev/null ;;
      firewalld) firewall-cmd --permanent --query-port="${port}/tcp" >/dev/null 2>&1 && continue
                 firewall-cmd --permanent --add-port="${port}/tcp" >/dev/null && firewall-cmd --reload >/dev/null ;;
    esac
    printf '%s %s\n' "$backend" "$port" > "$owner"
  done
fi
msg installed
