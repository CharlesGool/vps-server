#!/usr/bin/env bash
#
# Remove the vps-server systemd service and everything it installed.
#
#   sudo bash deploy/uninstall.sh                # stop + disable the service, delete $PREFIX
#   sudo KEEP_DATA=1 bash deploy/uninstall.sh    # keep code and /var/lib/vps-server
#
# A full uninstall removes the code and this project's marked state directory.
# KEEP_DATA=1 retains both for a later reinstall.

set -euo pipefail

PREFIX="${PREFIX:-/root/apps/vps-server}"
SERVICE_NAME="${SERVICE_NAME:-vps-server-web}"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
STATE_LOCATOR=/etc/vps-server/state-dir
STATE_DIR="${VPSSRV_STATE_DIR:-}"
if [ -z "$STATE_DIR" ] && [ -f "$STATE_LOCATOR" ]; then STATE_DIR="$(cat "$STATE_LOCATOR")"; fi
STATE_DIR="${STATE_DIR:-/var/lib/vps-server}"
export VPSSRV_STATE_DIR="$STATE_DIR"
ANYTLS_SERVICE="vps-server-anytls.service"
PROXY_SERVICE="vps-server-proxy.service"
FRPS_SERVICE="vps-server-frps.service"
TAILSCALE_SERVICE="vps-server-tailscale.service"

# Speak the same language the install was set up with. The installer records
# it in the unit file; fall back to the environment, then English.
INSTALL_LANG="${VPSSRV_DEFAULT_LANG:-}"
if [ -z "$INSTALL_LANG" ] && [ -f "$UNIT_PATH" ]; then
  INSTALL_LANG="$(sed -n 's/^Environment=VPSSRV_DEFAULT_LANG=//p' "$UNIT_PATH" | tail -n 1)"
fi
case "$INSTALL_LANG" in en|zh_cn|es) ;; *) INSTALL_LANG=en ;; esac
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
    zh_cn) catalog=zh-CN ;;
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
if [ -f "$STATE_DIR/.layout-version" ] &&
   { [ ! -f "$STATE_LOCATOR" ] || [ "$(cat "$STATE_LOCATOR")" != "$STATE_DIR" ]; }; then
  die "$(msg cleanup_failed)"
fi

# This helper validates PORTS.md before changing services, then removes only
# the FRPC template and data managed by this project. Run it before PREFIX is
# removed because the ownership marker lives in the persistent data directory.
FRPC_CLEANUP="$SCRIPT_DIR/../src/web/uninstall_cleanup.py"
[ -f "$FRPC_CLEANUP" ] || die "$(msg cleanup_failed)"
python3 "$FRPC_CLEANUP" check-ports "$PREFIX" "${KEEP_DATA:-0}" "$SERVICE_NAME" >/dev/null || die "$(msg cleanup_failed)"
frpc_result="$(python3 "$FRPC_CLEANUP" frpc "$PREFIX" "${KEEP_DATA:-0}" "$SERVICE_NAME")" || die "$(msg cleanup_failed)"
case "$frpc_result" in
  removed) msg frpc_removed ;;
  unowned) msg frpc_unowned >&2 ;;
esac

# Stop the project Tailscale daemon before removing its state.
if [ -f "/etc/systemd/system/$TAILSCALE_SERVICE" ]; then
  systemctl disable --now "$TAILSCALE_SERVICE" || die "Tailscale service could not stop"
  rm -f "/etc/systemd/system/$TAILSCALE_SERVICE" \
        /usr/local/bin/tailscale-vps-server /usr/local/bin/tailscaled-vps-server
  systemctl daemon-reload
fi
if [ "${KEEP_DATA:-0}" != 1 ]; then
  memory_dropin=/etc/systemd/system/vps-server-tailscale.service.d/30-memory.conf
  if [ -f "$memory_dropin" ]; then
    rm -f "$memory_dropin"
    rmdir /etc/systemd/system/vps-server-tailscale.service.d 2>/dev/null || true
    systemctl daemon-reload
  fi
fi

# KEEP_DATA preserves Lucky tasks; a full uninstall removes its entire config directory.
if [ -f /etc/systemd/system/vps-server-lucky.service ] || [ -f /etc/vps-server-lucky/firewall-owned ]; then
  if [ -f /etc/systemd/system/vps-server-lucky.service ]; then
    systemctl disable --now vps-server-lucky.service || die "$(msg cleanup_failed)"
  fi
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
    if [ -f "$lucky_owner" ]; then
      msg lucky_fw_retained >&2
      [ "${KEEP_DATA:-0}" = 1 ] || exit 1
    fi
  fi
  rm -f /etc/systemd/system/vps-server-lucky.service /usr/local/bin/lucky-vps-server
  systemctl daemon-reload
  if [ "${KEEP_DATA:-0}" = 1 ]; then msg lucky_config_retained >&2; fi
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
    if [ -f "$frps_owner" ]; then
      msg frps_fw_retained >&2
      [ "${KEEP_DATA:-0}" = 1 ] || exit 1
    fi
  fi
  rm -f "/etc/systemd/system/$FRPS_SERVICE" /usr/local/bin/frps-vps-server
  if [ "${KEEP_DATA:-0}" != 1 ]; then rm -f /etc/vps-server-frps/frps.toml; fi
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
  if [ -f "$PREFIX/src/web/nft_runtime.py" ]; then
    python3 "$PREFIX/src/web/nft_runtime.py" delete-table >/dev/null 2>&1 || true
  elif command -v nft >/dev/null 2>&1; then
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
if [ "${KEEP_DATA:-0}" != "1" ] && [ -d /etc/vps-server-anytls ] && [ ! -L /etc/vps-server-anytls ]; then
  python3 - <<'PY'
from pathlib import Path
import shutil
target = Path('/etc/vps-server-anytls')
if target.is_dir() and not target.is_symlink():
    shutil.rmtree(target)
PY
fi

if [ -f "/etc/systemd/system/${PROXY_SERVICE}" ]; then
  if [ -f "$PREFIX/proxy/setup-proxy.sh" ]; then
    msg proxy_removing "$PROXY_SERVICE"
    PREFIX="$PREFIX" VPSSRV_KEEP_CONFIG="${KEEP_DATA:-0}" bash "$PREFIX/proxy/setup-proxy.sh" uninstall || true
  else
    msg proxy_orphan "$PROXY_SERVICE" "$PREFIX" "$PROXY_SERVICE" "$PROXY_SERVICE"
  fi
fi
rm -f /usr/local/bin/sing-box-vps-server

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

# Purge project-owned module data even when its unit was already removed.
# Do not follow symlinks into another application's directories.
if [ "${KEEP_DATA:-0}" != 1 ]; then
  for module_unit in "$ANYTLS_SERVICE" "$PROXY_SERVICE" "$FRPS_SERVICE" "$TAILSCALE_SERVICE" vps-server-lucky.service; do
    if [ -f "/etc/systemd/system/$module_unit" ]; then
      systemctl disable --now "$module_unit" || die "$(msg cleanup_failed)"
      rm -f "/etc/systemd/system/$module_unit"
    fi
  done
  systemctl daemon-reload
  rm -f /usr/local/bin/tailscale-vps-server /usr/local/bin/tailscaled-vps-server \
        /usr/local/bin/lucky-vps-server /usr/local/bin/frps-vps-server
  for module_config in /etc/vps-server-lucky /etc/vps-server-frps /etc/vps-server-proxy; do
    rm -rf -- "$module_config"
  done
fi

# All vps-server listeners have stopped. Keep other projects' PORTS.md rows.
released="$(python3 "$FRPC_CLEANUP" ports "$PREFIX" "${KEEP_DATA:-0}" "$SERVICE_NAME" "$frpc_result")" || die "$(msg cleanup_failed)"
msg ports_released "$released"

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

if [ "${KEEP_DATA:-0}" != "1" ] && [ -f "$STATE_DIR/.layout-version" ] &&
   [ "$(cat "$STATE_DIR/.layout-version")" = 1 ]; then
  python3 - "$PREFIX" "$STATE_DIR" <<'PY'
from pathlib import Path
import sys
prefix, state = (Path(value).resolve(strict=False) for value in sys.argv[1:])
if state == Path('/') or state == prefix or prefix in state.parents:
    raise SystemExit('unsafe state directory')
PY
  rm -rf -- "$STATE_DIR"
  if [ -f "$STATE_LOCATOR" ]; then rm -f -- "$STATE_LOCATOR"; fi
  rmdir "$(dirname "$STATE_LOCATOR")" 2>/dev/null || true
fi

msg "done"
