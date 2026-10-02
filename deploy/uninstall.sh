#!/usr/bin/env bash
#
# Remove the vps-server systemd service and everything it installed.
#
#   sudo bash deploy/uninstall.sh                # stop + disable the service, delete $PREFIX
#   sudo KEEP_DATA=1 bash deploy/uninstall.sh    # keep $PREFIX (password, certs, visitor log)
#
# Uninstalling means uninstalling: $PREFIX — including the admin password,
# the generated port, certificates and the visitor log — is deleted by
# default. Pass KEEP_DATA=1 to leave it behind (e.g. to reinstall later and
# keep the visitor history).

set -euo pipefail

PREFIX="${PREFIX:-/root/apps/vps-server}"
SERVICE_NAME="${SERVICE_NAME:-vps-server-web}"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
ANYTLS_SERVICE="vps-server-anytls.service"
PROXY_SERVICE="vps-server-proxy.service"
FRPS_SERVICE="vps-server-frps.service"

# Speak the same language the install was set up with. The installer records
# it in the unit file; fall back to the environment, then English.
INSTALL_LANG="${VPSSRV_DEFAULT_LANG:-}"
if [ -z "$INSTALL_LANG" ] && [ -f "$UNIT_PATH" ]; then
  INSTALL_LANG="$(sed -n 's/^Environment=VPSSRV_DEFAULT_LANG=//p' "$UNIT_PATH" | tail -n 1)"
fi
case "$INSTALL_LANG" in en|zh_cn|zh_tw|zh_hk|hi|es|ar|fr) ;; *) INSTALL_LANG=en ;; esac
export VPSSRV_DEFAULT_LANG="$INSTALL_LANG"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
CATALOG_ROOT="${VPSSRV_CATALOG_ROOT:-}"
if [ -z "$CATALOG_ROOT" ]; then
  if [ -d "$SCRIPT_DIR/../lang/uninstaller" ]; then CATALOG_ROOT="$SCRIPT_DIR/../lang"
  else CATALOG_ROOT="$PREFIX/lang"; fi
fi

msg() {
  local key="$1"; shift
  local fmt catalog
  case "$INSTALL_LANG" in
    zh_cn) catalog=zh-CN ;; zh_tw) catalog=zh-TW ;; zh_hk) catalog=zh-HK ;;
    *) catalog="$INSTALL_LANG" ;;
  esac
  # Keep the catalog in memory: a full uninstall removes PREFIX before the
  # final messages, and the installed catalog may live under PREFIX/lang.
  if [ -z "${CATALOG_CONTENTS+x}" ]; then
    CATALOG_CONTENTS="$(cat "$CATALOG_ROOT/uninstaller/$catalog.sh")"
  fi
  # shellcheck disable=SC1090
  source /dev/stdin <<< "$CATALOG_CONTENTS"
  printf "$fmt" "$@"
}

die() { msg error_prefix "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "$(msg need_root)"

# Lucky configuration contains DDNS and proxy tasks; never delete it automatically.
if [ -f /etc/systemd/system/vps-server-lucky.service ] || [ -f /etc/vps-server-lucky/firewall-owned ]; then
  systemctl disable --now vps-server-lucky.service 2>/dev/null || true
  lucky_owner=/etc/vps-server-lucky/firewall-owned
  if [ -f "$lucky_owner" ]; then
    read -r backend port < "$lucky_owner" || true
    removed=0
    if [[ "$port" =~ ^[0-9]+$ ]] && [ "$port" -ge 1 ] && [ "$port" -le 65535 ]; then
      case "$backend" in
        ufw) ufw --force delete allow "${port}/tcp" >/dev/null && removed=1 || true ;;
        firewalld) firewall-cmd --permanent --remove-port="${port}/tcp" >/dev/null && firewall-cmd --reload >/dev/null && removed=1 || true ;;
      esac
    fi
    if [ "$removed" = 1 ]; then rm -f "$lucky_owner"; fi
    [ ! -f "$lucky_owner" ] || msg lucky_fw_retained >&2
  fi
  rm -f /etc/systemd/system/vps-server-lucky.service /usr/local/bin/lucky-vps-server
  systemctl daemon-reload
  msg lucky_config_retained >&2
fi

if [ -f "/etc/systemd/system/$FRPS_SERVICE" ] || [ -f /etc/vps-server-frps/firewall-owned ]; then
  if [ -f "/etc/systemd/system/$FRPS_SERVICE" ]; then
    systemctl disable --now "$FRPS_SERVICE" || true
  fi
  frps_owner=/etc/vps-server-frps/firewall-owned
  if [ -f "$frps_owner" ]; then
    read -r backend port < "$frps_owner" || true
    if [[ "$port" =~ ^[0-9]+$ ]] && [ "$port" -ge 1 ] && [ "$port" -le 65535 ]; then
      removed=0
      case "$backend" in
        ufw) ufw --force delete allow "${port}/tcp" >/dev/null && removed=1 || true ;;
        firewalld) firewall-cmd --permanent --remove-port="${port}/tcp" >/dev/null && firewall-cmd --reload >/dev/null && removed=1 || true ;;
      esac
      if [ "$removed" = 1 ]; then rm -f "$frps_owner"; fi
    fi
    [ ! -f "$frps_owner" ] || msg frps_fw_retained >&2
  fi
  rm -f "/etc/systemd/system/$FRPS_SERVICE" /usr/local/bin/frps-vps-server /etc/vps-server-frps/frps.toml
  if [ ! -f "$frps_owner" ]; then rmdir /etc/vps-server-frps 2>/dev/null || true; fi
  systemctl daemon-reload
fi

# The anytls and proxy modules go first, and specifically before $PREFIX is
# deleted: their own teardown scripts live inside $PREFIX, so the other order
# would take the uninstaller away and leave a running service nobody can
# remove. anytls goes before proxy so that if only anytls's config still
# exists when proxy tears down, proxy's own shared-binary check (see
# proxy/setup-proxy.sh) sees the correct, already-updated state.
if [ -f /etc/systemd/system/vps-server-node-meter.service ]; then
  systemctl disable --now vps-server-node-meter.service 2>/dev/null || true
  if command -v nft >/dev/null 2>&1; then
    nft delete table inet vps_server_nodes 2>/dev/null || true
  fi
  rm -f /etc/systemd/system/vps-server-node-meter.service \
        /etc/systemd/system/vps-server-anytls.service.d/node-meter.conf \
        /etc/systemd/system/vps-server-proxy.service.d/node-meter.conf
  rmdir /etc/systemd/system/vps-server-anytls.service.d \
        /etc/systemd/system/vps-server-proxy.service.d 2>/dev/null || true
  systemctl daemon-reload
fi
if [ -f "/etc/systemd/system/${ANYTLS_SERVICE}" ]; then
  if [ -f "$PREFIX/anytls/setup-anytls.sh" ]; then
    msg anytls_removing "$ANYTLS_SERVICE"
    bash "$PREFIX/anytls/setup-anytls.sh" uninstall || true
  else
    msg anytls_orphan "$ANYTLS_SERVICE" "$PREFIX" "$ANYTLS_SERVICE" "$ANYTLS_SERVICE"
  fi
fi

if [ -f "/etc/systemd/system/${PROXY_SERVICE}" ]; then
  if [ -f "$PREFIX/proxy/setup-proxy.sh" ]; then
    msg proxy_removing "$PROXY_SERVICE"
    bash "$PREFIX/proxy/setup-proxy.sh" uninstall || true
  else
    msg proxy_orphan "$PROXY_SERVICE" "$PREFIX" "$PROXY_SERVICE" "$PROXY_SERVICE"
  fi
fi

if [ "${KEEP_DATA:-0}" != "1" ]; then
  rm -rf /etc/vps-server-nodes
  rm -f /etc/vps-server-node.lock
fi

if systemctl list-unit-files "${SERVICE_NAME}.service" >/dev/null 2>&1; then
  systemctl stop "$SERVICE_NAME" 2>/dev/null || true
  systemctl disable "$SERVICE_NAME" 2>/dev/null || true
fi

if [ -f "$UNIT_PATH" ]; then
  rm -f "$UNIT_PATH"
  systemctl daemon-reload
  msg removed_unit "$UNIT_PATH"
else
  msg no_unit "$UNIT_PATH"
fi

if [ "${KEEP_DATA:-0}" = "1" ]; then
  if [ -d "$PREFIX" ]; then
    msg kept "$PREFIX"
  else
    msg nothing_left "$PREFIX"
  fi
elif [ -d "$PREFIX" ]; then
  rm -rf "${PREFIX:?}"
  msg purged "$PREFIX"
else
  msg nothing_left "$PREFIX"
fi

msg "done"
