#!/usr/bin/env bash
#
# Remove the vps-server systemd service and everything it installed.
#
#   sudo ./uninstall.sh                # stop + disable the service, delete $PREFIX
#   sudo KEEP_DATA=1 ./uninstall.sh    # keep $PREFIX (password, certs, visitor log)
#
# Uninstalling means uninstalling: $PREFIX — including the admin password,
# the generated port, certificates and the visitor log — is deleted by
# default. Pass KEEP_DATA=1 to leave it behind (e.g. to reinstall later and
# keep the visitor history).

set -euo pipefail

PREFIX="${PREFIX:-/opt/vps-server}"
SERVICE_NAME="${SERVICE_NAME:-vps-server-web}"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
ANYTLS_SERVICE="vps-server-anytls.service"

# Speak the same language the install was set up with. The installer records
# it in the unit file; fall back to the environment, then English.
INSTALL_LANG="${VPSSRV_DEFAULT_LANG:-}"
if [ -z "$INSTALL_LANG" ] && [ -f "$UNIT_PATH" ]; then
  INSTALL_LANG="$(sed -n 's/^Environment=VPSSRV_DEFAULT_LANG=//p' "$UNIT_PATH" | tail -n 1)"
fi
case "$INSTALL_LANG" in en|zh_cn|zh_tw) ;; *) INSTALL_LANG=en ;; esac

msg() {
  local key="$1"; shift
  local fmt
  case "$INSTALL_LANG:$key" in
    en:need_root)      fmt='must run as root (try: sudo ./uninstall.sh)\n' ;;
    zh_cn:need_root)   fmt='必须以 root 运行（试试：sudo ./uninstall.sh）\n' ;;
    zh_tw:need_root)   fmt='必須以 root 執行（試試：sudo ./uninstall.sh）\n' ;;

    en:removed_unit)   fmt='Removed %s\n' ;;
    zh_cn:removed_unit) fmt='已删除 %s\n' ;;
    zh_tw:removed_unit) fmt='已刪除 %s\n' ;;

    en:no_unit)        fmt='No unit file at %s — nothing to remove.\n' ;;
    zh_cn:no_unit)     fmt='%s 不存在 —— 没有需要删除的 unit 文件。\n' ;;
    zh_tw:no_unit)     fmt='%s 不存在 —— 沒有需要刪除的 unit 檔案。\n' ;;

    en:purged)         fmt='Deleted %s (admin password, port, certificates and visitor log are gone).\n' ;;
    zh_cn:purged)      fmt='已删除 %s（管理员密码、端口、证书和访问日志都已清除）。\n' ;;
    zh_tw:purged)      fmt='已刪除 %s（管理員密碼、連接埠、憑證與訪客記錄都已清除）。\n' ;;

    en:kept)           fmt='Kept %s — admin password, port, certificates and visitor log are still there.\n' ;;
    zh_cn:kept)        fmt='已保留 %s —— 管理员密码、端口、证书和访问日志都还在。\n' ;;
    zh_tw:kept)        fmt='已保留 %s —— 管理員密碼、連接埠、憑證與訪客記錄都還在。\n' ;;

    en:nothing_left)   fmt='%s does not exist — nothing to delete.\n' ;;
    zh_cn:nothing_left) fmt='%s 不存在 —— 没有需要删除的数据。\n' ;;
    zh_tw:nothing_left) fmt='%s 不存在 —— 沒有需要刪除的資料。\n' ;;

    en:anytls_removing) fmt='Removing the anytls module (%s) ...\n' ;;
    zh_cn:anytls_removing) fmt='正在卸载 anytls 模块（%s）...\n' ;;
    zh_tw:anytls_removing) fmt='正在解除安裝 anytls 模組（%s）...\n' ;;

    en:anytls_orphan)  fmt='%s is installed but %s/anytls/setup-anytls.sh is gone, so it cannot be removed automatically.\nRemove it by hand:\n  systemctl disable --now %s\n  rm -f /etc/systemd/system/%s /usr/local/bin/sing-box-vps-server\n  rm -rf /etc/vps-server-anytls\n' ;;
    zh_cn:anytls_orphan) fmt='%s 已安装，但 %s/anytls/setup-anytls.sh 已不存在，无法自动卸载。\n请手动清理：\n  systemctl disable --now %s\n  rm -f /etc/systemd/system/%s /usr/local/bin/sing-box-vps-server\n  rm -rf /etc/vps-server-anytls\n' ;;
    zh_tw:anytls_orphan) fmt='%s 已安裝，但 %s/anytls/setup-anytls.sh 已不存在，無法自動解除安裝。\n請手動清理：\n  systemctl disable --now %s\n  rm -f /etc/systemd/system/%s /usr/local/bin/sing-box-vps-server\n  rm -rf /etc/vps-server-anytls\n' ;;

    en:done)           fmt='\nvps-server has been uninstalled.\n' ;;
    zh_cn:done)        fmt='\nvps-server 已卸载完成。\n' ;;
    zh_tw:done)        fmt='\nvps-server 已解除安裝完成。\n' ;;

    *) fmt="$key\n" ;;
  esac
  # shellcheck disable=SC2059  # fmt is a trusted format string from the table above
  printf "$fmt" "$@"
}

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "$(msg need_root)"

# The anytls module goes first, and specifically before $PREFIX is deleted:
# its own teardown script lives inside $PREFIX, so the other order would take
# the uninstaller away and leave a running service nobody can remove.
if [ -f "/etc/systemd/system/${ANYTLS_SERVICE}" ]; then
  if [ -f "$PREFIX/anytls/setup-anytls.sh" ]; then
    msg anytls_removing "$ANYTLS_SERVICE"
    bash "$PREFIX/anytls/setup-anytls.sh" uninstall || true
  else
    msg anytls_orphan "$ANYTLS_SERVICE" "$PREFIX" "$ANYTLS_SERVICE" "$ANYTLS_SERVICE"
  fi
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
