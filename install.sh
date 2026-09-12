#!/usr/bin/env bash
#
# Install vps-server as a systemd service.
#
#   sudo ./install.sh                 # interactive: language, password, port
#   sudo PREFIX=/srv/vpsws ./install.sh
#   sudo VPSSRV_CONSOLE_PORT=8080 ./install.sh              # fixed port, no prompt
#   sudo VPSSRV_CONSOLE_TLS=1 ./install.sh                  # HTTPS (self-signed unless you supply a cert)
#
# Asks, in this order: the UI language (which this installer's own output
# then switches to), whether to password-protect the web UI (and if so,
# random or operator-chosen password), and which port to listen on (random
# or operator-chosen). Each question is skippable by pre-setting the matching
# VPSSRV_DEFAULT_LANG / VPSSRV_AUTH / VPSSRV_CONSOLE_PORT — also how unattended installs
# (`curl | bash`, no TTY) get sane defaults with no prompts at all.
#
# Re-running is safe: it refreshes the program files and restarts the service,
# leaving admin_password.txt, port.txt, certs/ and data/ alone.

set -euo pipefail

PREFIX="${PREFIX:-/opt/vps-server}"
SERVICE_NAME="${SERVICE_NAME:-vps-server}"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

INTERACTIVE=0
[ -t 0 ] && INTERACTIVE=1

# ---------------------------------------------------------------------------
# Installer output i18n
#
# This installer speaks whatever language the operator picks for the web UI,
# which is why the language question comes first. Every string is a printf
# format, so placeholders line up across all three languages; templates that
# end without \n are prompts.
# ---------------------------------------------------------------------------

INSTALL_LANG="${VPSSRV_DEFAULT_LANG:-en}"
case "$INSTALL_LANG" in en|zh_cn|zh_tw) ;; *) INSTALL_LANG=en ;; esac

msg() {
  local key="$1"; shift
  local fmt
  case "$INSTALL_LANG:$key" in
    en:need_root)        fmt='must run as root (try: sudo ./install.sh)\n' ;;
    zh_cn:need_root)     fmt='必须以 root 运行（试试：sudo ./install.sh）\n' ;;
    zh_tw:need_root)     fmt='必須以 root 執行（試試：sudo ./install.sh）\n' ;;

    en:no_systemd)       fmt='systemd not found; this installer targets systemd hosts\n' ;;
    zh_cn:no_systemd)    fmt='找不到 systemd；本安装脚本只支持使用 systemd 的主机\n' ;;
    zh_tw:no_systemd)    fmt='找不到 systemd；本安裝腳本只支援使用 systemd 的主機\n' ;;

    en:no_python)        fmt='python3 not found (apt install python3)\n' ;;
    zh_cn:no_python)     fmt='找不到 python3（apt install python3）\n' ;;
    zh_tw:no_python)     fmt='找不到 python3（apt install python3）\n' ;;

    en:no_openssl)       fmt='openssl not found (apt install openssl), or set VPSSRV_CONSOLE_TLS=0 to serve plain HTTP\n' ;;
    zh_cn:no_openssl)    fmt='找不到 openssl（apt install openssl）；也可以设置 VPSSRV_CONSOLE_TLS=0 改用明文 HTTP\n' ;;
    zh_tw:no_openssl)    fmt='找不到 openssl（apt install openssl）；也可以設定 VPSSRV_CONSOLE_TLS=0 改用純 HTTP\n' ;;

    en:installing)       fmt='Installing to %s ...\n' ;;
    zh_cn:installing)    fmt='正在安装到 %s ...\n' ;;
    zh_tw:installing)    fmt='正在安裝到 %s ...\n' ;;

    en:inplace_skip)     fmt='Source is the install directory — skipping file copy (in-place upgrade).\n' ;;
    zh_cn:inplace_skip)  fmt='源目录就是安装目录 —— 跳过文件拷贝（原地升级）。\n' ;;
    zh_tw:inplace_skip)  fmt='來源目錄就是安裝目錄 —— 略過檔案複製（原地升級）。\n' ;;

    en:missing_app)      fmt='%s/app.py is missing after the copy step\n' ;;
    zh_cn:missing_app)   fmt='拷贝完成后 %s/app.py 仍然不存在\n' ;;
    zh_tw:missing_app)   fmt='複製完成後 %s/app.py 仍然不存在\n' ;;

    en:ask_auth)         fmt='Enable password protection for the web UI? [Y/n] ' ;;
    zh_cn:ask_auth)      fmt='是否为网页开启密码保护？[Y/n] ' ;;
    zh_tw:ask_auth)      fmt='是否為網頁開啟密碼保護？[Y/n] ' ;;

    en:auth_disabled)    fmt='Password protection disabled — anyone who finds the port gets in with no login.\n' ;;
    zh_cn:auth_disabled) fmt='已关闭密码保护 —— 任何人只要找到端口就能直接进入，无需登录。\n' ;;
    zh_tw:auth_disabled) fmt='已關閉密碼保護 —— 任何人只要找到連接埠就能直接進入，無需登入。\n' ;;

    en:ask_pwmode)       fmt='Use a random password, or set one yourself? [R/m] ' ;;
    zh_cn:ask_pwmode)    fmt='使用随机密码，还是自己设置一个？[R=随机/m=手动] ' ;;
    zh_tw:ask_pwmode)    fmt='使用隨機密碼，還是自己設定一個？[R=隨機/m=手動] ' ;;

    en:pw_enter)         fmt='Password: ' ;;
    zh_cn:pw_enter)      fmt='密码： ' ;;
    zh_tw:pw_enter)      fmt='密碼： ' ;;

    en:pw_confirm)       fmt='Confirm password: ' ;;
    zh_cn:pw_confirm)    fmt='确认密码： ' ;;
    zh_tw:pw_confirm)    fmt='確認密碼： ' ;;

    en:pw_mismatch)      fmt='Passwords were empty or did not match — try again.\n' ;;
    zh_cn:pw_mismatch)   fmt='密码为空或两次输入不一致 —— 请重试。\n' ;;
    zh_tw:pw_mismatch)   fmt='密碼為空或兩次輸入不一致 —— 請重試。\n' ;;

    en:ask_port)         fmt='Port to listen on — 1-65535, or press Enter for a random one: ' ;;
    zh_cn:ask_port)      fmt='监听端口 —— 填 1-65535，或直接回车随机生成： ' ;;
    zh_tw:ask_port)      fmt='監聽連接埠 —— 填 1-65535，或直接按 Enter 隨機產生： ' ;;

    en:port_nan)         fmt='Not a number — try again.\n' ;;
    zh_cn:port_nan)      fmt='不是数字 —— 请重试。\n' ;;
    zh_tw:port_nan)      fmt='不是數字 —— 請重試。\n' ;;

    en:port_range)       fmt='Out of range (1-65535) — try again.\n' ;;
    zh_cn:port_range)    fmt='超出范围（1-65535）—— 请重试。\n' ;;
    zh_tw:port_range)    fmt='超出範圍（1-65535）—— 請重試。\n' ;;

    en:container)        fmt='Container detected — omitting systemd sandboxing directives (they fail with 226/NAMESPACE here).\n' ;;
    zh_cn:container)     fmt='检测到容器环境 —— 省略 systemd 沙箱指令（在这里会以 226/NAMESPACE 失败）。\n' ;;
    zh_tw:container)     fmt='偵測到容器環境 —— 略過 systemd 沙箱指令（在這裡會以 226/NAMESPACE 失敗）。\n' ;;

    en:writing_unit)     fmt='Writing %s ...\n' ;;
    zh_cn:writing_unit)  fmt='正在写入 %s ...\n' ;;
    zh_tw:writing_unit)  fmt='正在寫入 %s ...\n' ;;

    en:start_failed)     fmt='\nService failed to start. Recent log:\n' ;;
    zh_cn:start_failed)  fmt='\n服务启动失败。最近的日志：\n' ;;
    zh_tw:start_failed)  fmt='\n服務啟動失敗。最近的日誌：\n' ;;

    en:running)          fmt='\nvps-server is running.\n' ;;
    zh_cn:running)       fmt='\nvps-server 已经在运行。\n' ;;
    zh_tw:running)       fmt='\nvps-server 已經在執行。\n' ;;

    en:line_service)     fmt='  service:  systemctl status %s\n' ;;
    zh_cn:line_service)  fmt='  服务：    systemctl status %s\n' ;;
    zh_tw:line_service)  fmt='  服務：    systemctl status %s\n' ;;

    en:line_url)         fmt='  url:      %s://<this-server>:%s/\n' ;;
    zh_cn:line_url)      fmt='  地址：    %s://<本机地址>:%s/\n' ;;
    zh_tw:line_url)      fmt='  網址：    %s://<本機位址>:%s/\n' ;;

    en:line_url_unknown) fmt='  url:      %s://<this-server>:<port>/   (could not read %s — check journalctl -u %s)\n' ;;
    zh_cn:line_url_unknown) fmt='  地址：    %s://<本机地址>:<端口>/   （读不到 %s —— 请查看 journalctl -u %s）\n' ;;
    zh_tw:line_url_unknown) fmt='  網址：    %s://<本機位址>:<連接埠>/   （讀不到 %s —— 請查看 journalctl -u %s）\n' ;;

    en:line_pw_none)     fmt='  password: none — password protection is disabled (VPSSRV_AUTH=0)\n' ;;
    zh_cn:line_pw_none)  fmt='  密码：    无 —— 密码保护已关闭（VPSSRV_AUTH=0）\n' ;;
    zh_tw:line_pw_none)  fmt='  密碼：    無 —— 密碼保護已關閉（VPSSRV_AUTH=0）\n' ;;

    en:line_pw)          fmt='  password: %s   (stored in %s)\n' ;;
    zh_cn:line_pw)       fmt='  密码：    %s   （保存在 %s）\n' ;;
    zh_tw:line_pw)       fmt='  密碼：    %s   （儲存於 %s）\n' ;;

    en:line_pw_seefile)  fmt='  password: see %s\n' ;;
    zh_cn:line_pw_seefile) fmt='  密码：    见 %s\n' ;;
    zh_tw:line_pw_seefile) fmt='  密碼：    見 %s\n' ;;

    en:line_lang)        fmt='  language: %s (default when no cookie/query/browser match)\n' ;;
    zh_cn:line_lang)     fmt='  语言：    %s （没有 cookie/查询参数/浏览器语言匹配时的默认值）\n' ;;
    zh_tw:line_lang)     fmt='  語言：    %s （沒有 cookie/查詢參數/瀏覽器語言相符時的預設值）\n' ;;

    en:cert_note)        fmt='\nNote: using a self-signed certificate, so browsers will show a warning\nyou must click through. To use a real certificate, set VPSSRV_TLS_CERT\nand VPSSRV_TLS_KEY and re-run this installer.\n' ;;
    zh_cn:cert_note)     fmt='\n注意：使用的是自签证书，浏览器会弹出警告，需要手动点继续。\n想用真实证书的话，设置 VPSSRV_TLS_CERT 和 VPSSRV_TLS_KEY 后\n重新运行本安装脚本。\n' ;;
    zh_tw:cert_note)     fmt='\n注意：使用的是自簽憑證，瀏覽器會跳出警告，需要手動點繼續。\n想使用真實憑證的話，設定 VPSSRV_TLS_CERT 與 VPSSRV_TLS_KEY 後\n重新執行本安裝腳本。\n' ;;

    en:to_remove)        fmt='\nTo remove: sudo ./uninstall.sh\n' ;;
    zh_cn:to_remove)     fmt='\n卸载方法：sudo ./uninstall.sh\n' ;;
    zh_tw:to_remove)     fmt='\n解除安裝方法：sudo ./uninstall.sh\n' ;;

    *) fmt="$key\n" ;;   # unknown key: show it rather than printing nothing
  esac
  # shellcheck disable=SC2059  # fmt is a trusted format string from the table above
  printf "$fmt" "$@"
}

# Callers pass already-translated text, e.g. die "$(msg need_root)". Command
# substitution strips msg's trailing newline, so put it back here.
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Language — asked first, because everything below is printed in it.
#    The question itself is trilingual for obvious reasons.
# ---------------------------------------------------------------------------
if [ -z "${VPSSRV_DEFAULT_LANG:-}" ] && [ "$INTERACTIVE" = "1" ]; then
  echo "Language / 语言 / 語言:"
  echo "  1) English"
  echo "  2) 简体中文 (Simplified Chinese)"
  echo "  3) 繁體中文 (Traditional Chinese)"
  # printf rather than `read -p`: bash only renders a -p prompt when stdin is
  # a terminal, and every other prompt below goes through msg()/printf.
  printf 'Choice / 选择 / 選擇 [1]: '
  read -r lang_choice </dev/tty || lang_choice="1"
  case "$lang_choice" in
    2) VPSSRV_DEFAULT_LANG=zh_cn ;;
    3) VPSSRV_DEFAULT_LANG=zh_tw ;;
    *) VPSSRV_DEFAULT_LANG=en ;;
  esac
  INSTALL_LANG="$VPSSRV_DEFAULT_LANG"
  echo
fi

[ "$(id -u)" -eq 0 ] || die "$(msg need_root)"
command -v systemctl >/dev/null 2>&1 || die "$(msg no_systemd)"
command -v python3 >/dev/null 2>&1 || die "$(msg no_python)"

# TLS is on by default and needs openssl for first-run certificate generation.
if [ "${VPSSRV_CONSOLE_TLS:-0}" = "1" ] && ! command -v openssl >/dev/null 2>&1; then
  die "$(msg no_openssl)"
fi

# ---------------------------------------------------------------------------
# 2. Password protection: on/off, then random vs. operator-chosen.
# ---------------------------------------------------------------------------
MANUAL_PASSWORD=""
if [ -z "${VPSSRV_AUTH:-}" ]; then
  if [ "$INTERACTIVE" = "1" ]; then
    msg ask_auth
    read -r ans </dev/tty || ans="y"
    case "$ans" in
      [nN]*) VPSSRV_AUTH=0 ;;
      *) VPSSRV_AUTH=1 ;;
    esac
  else
    VPSSRV_AUTH=1
  fi
fi
if [ "$VPSSRV_AUTH" = "0" ]; then
  msg auth_disabled
elif [ "$INTERACTIVE" = "1" ] && [ -z "${VPSSRV_PASSWORD_FILE:-}" ] \
     && [ ! -f "$PREFIX/admin_password.txt" ]; then
  msg ask_pwmode
  read -r pwmode </dev/tty || pwmode="r"
  case "$pwmode" in
    [mM]*)
      while :; do
        msg pw_enter
        read -rs MANUAL_PASSWORD </dev/tty; echo
        msg pw_confirm
        read -rs pw_confirm </dev/tty; echo
        if [ -n "$MANUAL_PASSWORD" ] && [ "$MANUAL_PASSWORD" = "$pw_confirm" ]; then
          break
        fi
        msg pw_mismatch
      done
      ;;
  esac
fi

# ---------------------------------------------------------------------------
# 3. Port: random (default, see DECISIONS.md) or an operator-chosen one.
# ---------------------------------------------------------------------------
# One question, not two: an operator looking at a port prompt types a port
# number. Asking "random or custom?" first and *then* for the number meant a
# typed number fell through to the random branch (reported 2026-08-25: the
# operator answered "50" and silently got a random port).
if [ -z "${VPSSRV_CONSOLE_PORT:-}" ] && [ "$INTERACTIVE" = "1" ] \
   && [ ! -f "${VPSSRV_CONSOLE_PORT_FILE:-$PREFIX/port.txt}" ]; then
  while :; do
    msg ask_port
    read -r custom_port </dev/tty || custom_port=""
    # Empty (just Enter) means "random", which is the documented default.
    [ -z "$custom_port" ] && break
    case "$custom_port" in
      *[!0-9]*) msg port_nan; continue ;;
    esac
    if [ "$custom_port" -ge 1 ] && [ "$custom_port" -le 65535 ]; then
      VPSSRV_CONSOLE_PORT="$custom_port"
      break
    fi
    msg port_range
  done
fi

msg installing "$PREFIX"
mkdir -p "$PREFIX"

# Upgrading in place (running the installer from inside PREFIX, e.g. after a
# `git pull` in /opt/vps-server) is a normal thing to do, but the copy loop
# below would then delete each file and immediately fail to copy it from
# itself. Detect it by resolved path and skip the copy entirely — the files
# are already where they need to be.
PREFIX_ABS="$(mkdir -p "$PREFIX" && cd "$PREFIX" && pwd)"
if [ "$SRC_DIR" = "$PREFIX_ABS" ]; then
  msg inplace_skip
else
  # Program files only. Anything stateful (admin_password.txt, certs/, data/)
  # is deliberately excluded so re-running never clobbers an existing install.
  # CHANGELOG.md (English + translated_*/) is shipped because the app serves
  # it at /changelog, so the person you deployed for can see what changed.
  for item in app.py static systemd tests README.md LICENSE CHANGELOG.md \
              translated_zh_cn translated_zh_tw; do
    [ -e "$SRC_DIR/$item" ] || continue
    rm -rf "${PREFIX:?}/$item"
    cp -r "$SRC_DIR/$item" "$PREFIX/"
  done
  [ -f "$SRC_DIR/.env.example" ] && cp "$SRC_DIR/.env.example" "$PREFIX/"
fi

# Whichever path was taken, the app must actually be there before we go on to
# write a unit file pointing at it.
[ -f "$PREFIX/app.py" ] || die "$(msg missing_app "$PREFIX")"

# A manually-chosen password must land on disk before the first start, so
# ensure_admin_password() in app.py finds it already there and never
# generates a random one to replace it.
if [ -n "$MANUAL_PASSWORD" ]; then
  PW_TARGET="${VPSSRV_PASSWORD_FILE:-$PREFIX/admin_password.txt}"
  printf '%s\n' "$MANUAL_PASSWORD" > "$PW_TARGET"
  chmod 600 "$PW_TARGET"
  MANUAL_PASSWORD=""
fi

# Carry over any explicitly provided settings so the unit reproduces them.
ENV_LINES=""
for var in VPSSRV_CONSOLE_TLS VPSSRV_CONSOLE_PORT VPSSRV_CONSOLE_PORT_FILE VPSSRV_REDIRECT_PORT VPSSRV_HOST \
           VPSSRV_DATA_DIR VPSSRV_PASSWORD_FILE VPSSRV_AUTH VPSSRV_DEFAULT_LANG \
           VPSSRV_CERT_DIR VPSSRV_TLS_CERT VPSSRV_TLS_KEY VPSSRV_TRUST_PROXY VPSSRV_MAX_TEST_MB \
           VPSSRV_TEST_SECONDS VPSSRV_WARMUP_SECONDS VPSSRV_DOWNLOAD_STREAMS \
           VPSSRV_UPLOAD_STREAMS VPSSRV_PING_SAMPLES; do
  if [ -n "${!var:-}" ]; then
    ENV_LINES="${ENV_LINES}Environment=${var}=${!var}"$'\n'
  fi
done

# systemd's sandboxing needs mount namespaces, which an unprivileged container
# cannot create (the unit then fails with 226/NAMESPACE). Probe once and only
# emit the hardening directives when they will actually work.
HARDENING=""
if systemd-detect-virt --container >/dev/null 2>&1; then
  msg container
else
  HARDENING="NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=$PREFIX"
fi

msg writing_unit "$UNIT_PATH"
cat > "$UNIT_PATH" <<EOF
[Unit]
Description=vps-server — VPS speed test + recent visitor IP log
After=network.target

[Service]
Type=simple
WorkingDirectory=$PREFIX
ExecStart=/usr/bin/env python3 $PREFIX/app.py
Restart=on-failure
RestartSec=5
User=root
${ENV_LINES}${HARDENING}

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null
systemctl restart "$SERVICE_NAME"

sleep 2
if ! systemctl is-active --quiet "$SERVICE_NAME"; then
  msg start_failed >&2
  journalctl -u "$SERVICE_NAME" -n 20 --no-pager >&2 || true
  exit 1
fi

PW_FILE="${VPSSRV_PASSWORD_FILE:-$PREFIX/admin_password.txt}"
PORT_FILE="${VPSSRV_CONSOLE_PORT_FILE:-$PREFIX/port.txt}"
if [ "${VPSSRV_CONSOLE_TLS:-0}" = "1" ]; then SCHEME=https; else SCHEME=http; fi
# VPSSRV_CONSOLE_PORT, if set, was carried into the unit verbatim. Otherwise app.py
# picked a random port on this first start and persisted it to PORT_FILE.
PORT="${VPSSRV_CONSOLE_PORT:-}"
if [ -z "$PORT" ] && [ -f "$PORT_FILE" ]; then
  PORT="$(cat "$PORT_FILE")"
fi

msg running
msg line_service "$SERVICE_NAME"
if [ -n "$PORT" ]; then
  msg line_url "$SCHEME" "$PORT"
else
  msg line_url_unknown "$SCHEME" "$PORT_FILE" "$SERVICE_NAME"
fi
if [ "$VPSSRV_AUTH" = "0" ]; then
  msg line_pw_none
elif [ -f "$PW_FILE" ]; then
  msg line_pw "$(cat "$PW_FILE")" "$PW_FILE"
else
  msg line_pw_seefile "$PW_FILE"
fi
if [ -n "${VPSSRV_DEFAULT_LANG:-}" ]; then
  msg line_lang "$VPSSRV_DEFAULT_LANG"
fi
if [ "${VPSSRV_CONSOLE_TLS:-0}" = "1" ] && [ -z "${VPSSRV_TLS_CERT:-}" ]; then
  msg cert_note
fi
msg to_remove
