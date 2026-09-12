#!/usr/bin/env bash
#
# Install vps-server. Three modules, each optional:
#
#   web      the public reachability page on 80/443 plus the private console
#   iperf3   the distro iperf3 package, so the console can open a test window
#   anytls   the sing-box anytls proxy (amd64 only)
#
#   sudo bash install.sh                             # interactive
#   sudo VPSSRV_MODULES=web,iperf3 bash install.sh   # unattended, no prompts
#   sudo VPSSRV_MODULES=web VPSSRV_PUBLIC_ENABLE=0 bash install.sh   # console only
#   sudo PREFIX=/srv/vpssrv bash install.sh
#
# Asks, in this order: the UI language (which this installer's own output then
# switches to), which modules to install, whether to password-protect the
# console (and if so, random or operator-chosen password), and which console
# port to use. Every question is skippable by pre-setting the matching
# VPSSRV_DEFAULT_LANG / VPSSRV_MODULES / VPSSRV_AUTH / VPSSRV_CONSOLE_PORT —
# which is also how unattended installs (`curl | bash`, no TTY) get sane
# defaults with no prompts at all.
#
# Re-running is safe: it refreshes the program files and restarts the service,
# leaving admin_password.txt, console_port.txt, certs/ and data/ alone.

set -euo pipefail

PREFIX="${PREFIX:-/opt/vps-server}"
SERVICE_NAME="${SERVICE_NAME:-vps-server-web}"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Modules, comma-separated. anytls is not in the default set: it is a proxy,
# and nobody should end up running one because they held down Enter.
DEFAULT_MODULES="web,iperf3"

PUBLIC_HTTP_PORT="${VPSSRV_PUBLIC_HTTP_PORT:-80}"
PUBLIC_HTTPS_PORT="${VPSSRV_PUBLIC_HTTPS_PORT:-443}"

INTERACTIVE=0
[ -t 0 ] && INTERACTIVE=1

has_module() {
  case ",${MODULES}," in *",$1,"*) return 0 ;; esac
  return 1
}

# Every VPSSRV_ variable this version carries into the unit file. One list,
# used both to write the unit and to work out what an older install predates.
KNOWN_VARS="VPSSRV_CONSOLE_TLS VPSSRV_CONSOLE_PORT VPSSRV_CONSOLE_PORT_FILE VPSSRV_HOST
            VPSSRV_PUBLIC_ENABLE VPSSRV_PUBLIC_HTTP_PORT VPSSRV_PUBLIC_HTTPS_PORT
            VPSSRV_IPERF_ENABLE VPSSRV_IPERF_PORT VPSSRV_IPERF_DEFAULT_MINUTES
            VPSSRV_IPERF_MAX_MINUTES
            VPSSRV_DATA_DIR VPSSRV_PASSWORD_FILE VPSSRV_AUTH VPSSRV_DEFAULT_LANG
            VPSSRV_CERT_DIR VPSSRV_TLS_CERT VPSSRV_TLS_KEY VPSSRV_TRUST_PROXY
            VPSSRV_MAX_TEST_MB VPSSRV_TRACK_CONNECTIONS VPSSRV_CONN_POLL_SECONDS
            VPSSRV_TEST_SECONDS VPSSRV_WARMUP_SECONDS VPSSRV_DOWNLOAD_STREAMS
            VPSSRV_UPLOAD_STREAMS VPSSRV_PING_SAMPLES
            VPSSRV_ANYTLS_CONFIG VPSSRV_ANYTLS_SERVICE VPSSRV_ANYTLS_SETUP"

# What this install left behind, so the next one can tell what changed.
# Deliberately not the unit file: the unit records only settings that were
# given a value, which says nothing about which settings the version knew of.
STATE_FILE="$PREFIX/.install-state"
ANYTLS_UNIT="/etc/systemd/system/vps-server-anytls.service"
ANYTLS_CONFIG_PATH="/etc/vps-server-anytls/config.json"

declare -A PREV=()
PREV_VERSION=""
PREV_MODULES=""
PREV_VARS=""
PREV_STATE_KNOWN=0
UPGRADE=0

# The version being installed, read from the single source of truth in app.py.
NEW_VERSION="$(sed -n 's/^VERSION = "\(.*\)"$/\1/p' "$SRC_DIR/app.py" 2>/dev/null | head -n1)"
NEW_VERSION="${NEW_VERSION:-unknown}"

unit_env() {
  # One recorded Environment= value from the installed unit, or empty.
  [ -f "$UNIT_PATH" ] || return 0
  sed -n "s/^Environment=$1=//p" "$UNIT_PATH" | tail -n1
}

existing_install() {
  [ -f "$UNIT_PATH" ] || [ -f "$ANYTLS_UNIT" ] || [ -f "$PREFIX/app.py" ]
}

load_previous() {
  local line kv
  if [ -f "$UNIT_PATH" ]; then
    while IFS= read -r line; do
      case "$line" in
        Environment=VPSSRV_*)
          kv="${line#Environment=}"
          PREV["${kv%%=*}"]="${kv#*=}"
          ;;
      esac
    done < "$UNIT_PATH"
  fi

  if [ -f "$STATE_FILE" ]; then
    PREV_STATE_KNOWN=1
    PREV_VERSION="$(sed -n 's/^version=//p' "$STATE_FILE" | tail -n1)"
    PREV_MODULES="$(sed -n 's/^modules=//p' "$STATE_FILE" | tail -n1)"
    PREV_VARS="$(sed -n 's/^vars=//p' "$STATE_FILE" | tail -n1)"
  fi

  # No state file means an install that predates it. That is the case this
  # whole path exists to survive, so work the modules out from what is on
  # disk rather than giving up.
  if [ -z "$PREV_MODULES" ]; then
    [ -f "$UNIT_PATH" ] && PREV_MODULES="web"
    command -v iperf3 >/dev/null 2>&1 && PREV_MODULES="${PREV_MODULES:+$PREV_MODULES,}iperf3"
    [ -f "$ANYTLS_UNIT" ] && PREV_MODULES="${PREV_MODULES:+$PREV_MODULES,}anytls"
  fi
  [ -n "$PREV_MODULES" ] || PREV_MODULES="$DEFAULT_MODULES"
}

# Carry recorded settings forward. Without this, anything chosen at the first
# install and stored only in the unit — a custom public port, TLS on the
# console — silently reverts to its default on the next run, and nothing says
# so. An explicit environment variable on *this* run still wins.
apply_previous() {
  local var kept=0
  for var in $KNOWN_VARS; do
    [ -n "${PREV[$var]:-}" ] || continue
    [ -n "${!var:-}" ] && continue
    export "$var=${PREV[$var]}"
    kept=$((kept + 1))
  done
  msg upgrade_keeping "$kept"
}

# Keep the anytls node as it is. setup-anytls.sh defaults both values to fresh
# randoms, so an upgrade that did not do this would rotate the credentials and
# break every configured client — for no reason anyone asked for.
preserve_anytls() {
  local port password
  [ -f "$ANYTLS_CONFIG_PATH" ] || return 0
  [ -z "${ANYTLS_PORT:-}" ] || return 0
  port="$(python3 -c 'import json,sys
try:
    c = json.load(open(sys.argv[1]))
except Exception:
    raise SystemExit
for i in c.get("inbounds", []):
    if i.get("type") == "anytls":
        print(i.get("listen_port", ""))
        break' "$ANYTLS_CONFIG_PATH" 2>/dev/null || true)"
  password="$(python3 -c 'import json,sys
try:
    c = json.load(open(sys.argv[1]))
except Exception:
    raise SystemExit
for i in c.get("inbounds", []):
    if i.get("type") == "anytls":
        u = (i.get("users") or [{}])[0]
        print(u.get("password", ""))
        break' "$ANYTLS_CONFIG_PATH" 2>/dev/null || true)"
  if [ -n "$port" ] && [ -n "$password" ]; then
    export ANYTLS_PORT="$port" ANYTLS_PASSWORD="$password"
    msg upgrade_anytls_kept "$port"
  fi
}

default_for() {
  sed -n "s/^$1=//p" "$SRC_DIR/.env.example" | tail -n1
}

# Settings this version understands that the installed one did not. Only
# answerable when the old install recorded its own list; otherwise say so
# rather than presenting a guess as a diff.
prompt_new_settings() {
  local var new="" default value
  if [ "$PREV_STATE_KNOWN" = "0" ]; then
    msg upgrade_vars_unknown
    return 0
  fi
  for var in $KNOWN_VARS; do
    case " $PREV_VARS " in *" $var "*) continue ;; esac
    new="${new:+$new }$var"
  done
  if [ -z "$new" ]; then
    msg upgrade_no_new
    return 0
  fi
  msg upgrade_new_head
  for var in $new; do
    default="$(default_for "$var")"
    if [ "$INTERACTIVE" != "1" ]; then
      msg upgrade_new_item "$var" "${default:-(empty)}"
      continue
    fi
    msg ask_new_var "$var" "${default:-(empty)}"
    read -r value </dev/tty || value=""
    [ -n "$value" ] && export "$var=$value"
  done
}

write_state() {
  {
    printf 'version=%s\n' "$NEW_VERSION"
    printf 'modules=%s\n' "$MODULES"
    printf 'vars=%s\n' "$(echo $KNOWN_VARS)"
  } > "$STATE_FILE"
  chmod 0644 "$STATE_FILE"
}

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
    en:need_root)        fmt='must run as root (try: sudo bash install.sh)\n' ;;
    zh_cn:need_root)     fmt='必须以 root 运行（试试：sudo bash install.sh）\n' ;;
    zh_tw:need_root)     fmt='必須以 root 執行（試試：sudo bash install.sh）\n' ;;

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

    en:pwmode_invalid)   fmt='Answer R (random) or m (set it yourself) — try again.\n' ;;
    zh_cn:pwmode_invalid) fmt='请回答 R（随机）或 m（自己设置）—— 请重试。\n' ;;
    zh_tw:pwmode_invalid) fmt='請回答 R（隨機）或 m（自己設定）—— 請重試。\n' ;;

    en:anytls_failed)    fmt='\nThe anytls module failed to install. The web module above is installed and running; only anytls is missing. Re-run with VPSSRV_MODULES=anytls once the cause is fixed.\n' ;;
    zh_cn:anytls_failed) fmt='\nanytls 模块安装失败。上面的 web 模块已经装好并在运行，缺的只有 anytls。排掉原因后用 VPSSRV_MODULES=anytls 单独重跑即可。\n' ;;
    zh_tw:anytls_failed) fmt='\nanytls 模組安裝失敗。上面的 web 模組已經裝好並在執行，缺的只有 anytls。排除原因後用 VPSSRV_MODULES=anytls 單獨重跑即可。\n' ;;

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

    en:to_remove)        fmt='\nTo remove:\n  sudo PREFIX=%s SERVICE_NAME=%s bash uninstall.sh\n' ;;
    zh_cn:to_remove)     fmt='\n卸载方法：\n  sudo PREFIX=%s SERVICE_NAME=%s bash uninstall.sh\n' ;;
    zh_tw:to_remove)     fmt='\n解除安裝方法：\n  sudo PREFIX=%s SERVICE_NAME=%s bash uninstall.sh\n' ;;

    en:ask_modules)      fmt='Choice [1]: ' ;;
    zh_cn:ask_modules)   fmt='选择 [1]： ' ;;
    zh_tw:ask_modules)   fmt='選擇 [1]： ' ;;

    en:mod_head)         fmt='\nWhich modules?\n  1) web + iperf3   (the reachability page, the console, and bandwidth testing)\n  2) web only       (no iperf3 window)\n  3) web + iperf3 + anytls\n  4) anytls only    (proxy, nothing else)\n' ;;
    zh_cn:mod_head)      fmt='\n安装哪些模块？\n  1) web + iperf3   （可达性页面、控制台、带宽测试）\n  2) 仅 web         （不带 iperf3 窗口）\n  3) web + iperf3 + anytls\n  4) 仅 anytls      （只装代理，别的都不装）\n' ;;
    zh_tw:mod_head)      fmt='\n安裝哪些模組？\n  1) web + iperf3   （可達性頁面、主控台、頻寬測試）\n  2) 僅 web         （不帶 iperf3 視窗）\n  3) web + iperf3 + anytls\n  4) 僅 anytls      （只裝代理，其他都不裝）\n' ;;

    en:modules_are)      fmt='Modules: %s\n' ;;
    zh_cn:modules_are)   fmt='模块：%s\n' ;;
    zh_tw:modules_are)   fmt='模組：%s\n' ;;

    en:port_busy)        fmt='Port %s is already held by another process.\nFree it, or pick different ports with VPSSRV_PUBLIC_HTTP_PORT / VPSSRV_PUBLIC_HTTPS_PORT,\nor set VPSSRV_PUBLIC_ENABLE=0 to skip the public page. Check with:\n  ss -lntp "( sport = :%s )"\n' ;;
    zh_cn:port_busy)     fmt='端口 %s 已被其他进程占用。\n先腾出来，或用 VPSSRV_PUBLIC_HTTP_PORT / VPSSRV_PUBLIC_HTTPS_PORT 换端口，\n或设 VPSSRV_PUBLIC_ENABLE=0 跳过公开页。查占用：\n  ss -lntp "( sport = :%s )"\n' ;;
    zh_tw:port_busy)     fmt='連接埠 %s 已被其他行程占用。\n先騰出來，或用 VPSSRV_PUBLIC_HTTP_PORT / VPSSRV_PUBLIC_HTTPS_PORT 換連接埠，\n或設 VPSSRV_PUBLIC_ENABLE=0 略過公開頁。查占用：\n  ss -lntp "( sport = :%s )"\n' ;;

    en:iperf_installing) fmt='Installing iperf3 from the distro ...\n' ;;
    zh_cn:iperf_installing) fmt='正在从发行版仓库安装 iperf3 ...\n' ;;
    zh_tw:iperf_installing) fmt='正在從發行版套件庫安裝 iperf3 ...\n' ;;

    en:iperf_failed)     fmt='Could not install iperf3. The console will say so when a window is requested; install it by hand with: apt install iperf3\n' ;;
    zh_cn:iperf_failed)  fmt='iperf3 安装失败。请求开窗口时控制台会提示；可手动安装：apt install iperf3\n' ;;
    zh_tw:iperf_failed)  fmt='iperf3 安裝失敗。請求開視窗時主控台會提示；可手動安裝：apt install iperf3\n' ;;

    en:anytls_arch)      fmt='The anytls module needs x86-64; this host is %s. Skipping it — the vendored sing-box binary would not execute here.\n' ;;
    zh_cn:anytls_arch)   fmt='anytls 模块需要 x86-64，本机是 %s，跳过 —— 随仓分发的 sing-box 二进制在这里跑不起来。\n' ;;
    zh_tw:anytls_arch)   fmt='anytls 模組需要 x86-64，本機是 %s，略過 —— 隨儲存庫散布的 sing-box 二進位在這裡無法執行。\n' ;;

    en:anytls_start)     fmt='\nInstalling the anytls module ...\n' ;;
    zh_cn:anytls_start)  fmt='\n正在安装 anytls 模块 ...\n' ;;
    zh_tw:anytls_start)  fmt='\n正在安裝 anytls 模組 ...\n' ;;

    en:line_modules)     fmt='  modules:  %s\n' ;;
    zh_cn:line_modules)  fmt='  模块：    %s\n' ;;
    zh_tw:line_modules)  fmt='  模組：    %s\n' ;;

    en:line_public)      fmt='  public:   http://<this-server>:%s/ and https://<this-server>:%s/ (no login)\n' ;;
    zh_cn:line_public)   fmt='  公开页：  http://<本机地址>:%s/ 和 https://<本机地址>:%s/ （无需登录）\n' ;;
    zh_tw:line_public)   fmt='  公開頁：  http://<本機位址>:%s/ 和 https://<本機位址>:%s/ （無需登入）\n' ;;

    en:line_public_off)  fmt='  public:   disabled (VPSSRV_PUBLIC_ENABLE=0)\n' ;;
    zh_cn:line_public_off) fmt='  公开页：  已关闭（VPSSRV_PUBLIC_ENABLE=0）\n' ;;
    zh_tw:line_public_off) fmt='  公開頁：  已關閉（VPSSRV_PUBLIC_ENABLE=0）\n' ;;

    en:line_iperf)       fmt='  iperf3:   ready, window closed — open one from the console (port %s)\n' ;;
    zh_cn:line_iperf)    fmt='  iperf3：  就绪，窗口关闭中 —— 到控制台开启（端口 %s）\n' ;;
    zh_tw:line_iperf)    fmt='  iperf3：  就緒，視窗關閉中 —— 到主控台開啟（連接埠 %s）\n' ;;

    en:line_iperf_off)   fmt='  iperf3:   not installed\n' ;;
    zh_cn:line_iperf_off) fmt='  iperf3：  未安装\n' ;;
    zh_tw:line_iperf_off) fmt='  iperf3：  未安裝\n' ;;

    en:found_install)    fmt='\nFound an existing install: vps-server %s, modules %s.\n' ;;
    zh_cn:found_install) fmt='\n检测到已安装：vps-server %s，模块 %s。\n' ;;
    zh_tw:found_install) fmt='\n偵測到已安裝：vps-server %s，模組 %s。\n' ;;

    en:ask_upgrade)      fmt='Keep its configuration and upgrade to %s? [Y/n] ' ;;
    zh_cn:ask_upgrade)   fmt='沿用它的配置并升级到 %s？[Y/n] ' ;;
    zh_tw:ask_upgrade)   fmt='沿用它的設定並升級到 %s？[Y/n] ' ;;

    en:reconfigure)      fmt='Reconfiguring from scratch. The console password, port, certificates and visitor log are kept either way.\n' ;;
    zh_cn:reconfigure)   fmt='重新配置。无论哪种方式，控制台密码、端口、证书和访客记录都会保留。\n' ;;
    zh_tw:reconfigure)   fmt='重新設定。無論哪種方式，主控台密碼、連接埠、憑證與訪客記錄都會保留。\n' ;;

    en:upgrade_keeping)  fmt='Carrying %s recorded setting(s) forward.\n' ;;
    zh_cn:upgrade_keeping) fmt='沿用已记录的 %s 项设置。\n' ;;
    zh_tw:upgrade_keeping) fmt='沿用已記錄的 %s 項設定。\n' ;;

    en:upgrade_anytls_kept) fmt='Keeping the existing anytls node on port %s — its password is unchanged, so configured clients keep working.\n' ;;
    zh_cn:upgrade_anytls_kept) fmt='保留现有 anytls 节点，端口 %s —— 密码不变，已配置的客户端继续可用。\n' ;;
    zh_tw:upgrade_anytls_kept) fmt='保留現有 anytls 節點，連接埠 %s —— 密碼不變，已設定的客戶端繼續可用。\n' ;;

    en:upgrade_no_new)   fmt='This version adds no new settings.\n' ;;
    zh_cn:upgrade_no_new) fmt='本版本没有新增配置项。\n' ;;
    zh_tw:upgrade_no_new) fmt='本版本沒有新增設定項。\n' ;;

    en:upgrade_new_head) fmt='\nThis version adds settings the installed one did not have. Press Enter to accept a default:\n' ;;
    zh_cn:upgrade_new_head) fmt='\n本版本新增了旧安装没有的配置项。直接回车即采用默认值：\n' ;;
    zh_tw:upgrade_new_head) fmt='\n本版本新增了舊安裝沒有的設定項。直接按 Enter 即採用預設值：\n' ;;

    en:upgrade_new_item) fmt='  %s = %s (default applied)\n' ;;
    zh_cn:upgrade_new_item) fmt='  %s = %s （已采用默认值）\n' ;;
    zh_tw:upgrade_new_item) fmt='  %s = %s （已採用預設值）\n' ;;

    en:ask_new_var)      fmt='  %s [%s]: ' ;;
    zh_cn:ask_new_var)   fmt='  %s [%s]： ' ;;
    zh_tw:ask_new_var)   fmt='  %s [%s]： ' ;;

    en:upgrade_vars_unknown) fmt='The installed version did not record which settings it supported, so this cannot tell which are new. Everything it did record is carried forward; anything else takes the default documented in .env.example. Re-run and answer "n" above to review every setting.\n' ;;
    zh_cn:upgrade_vars_unknown) fmt='旧安装没有记录它支持哪些配置项，因此无法判断哪些是新增的。它记录过的都会沿用，其余按 .env.example 里的默认值。想逐项复核就重跑一次、在上面回答 n。\n' ;;
    zh_tw:upgrade_vars_unknown) fmt='舊安裝沒有記錄它支援哪些設定項，因此無法判斷哪些是新增的。它記錄過的都會沿用，其餘按 .env.example 裡的預設值。想逐項複核就重跑一次、在上面回答 n。\n' ;;

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
# An existing install already answered this. Adopt its answer before anything
# prints, so the upgrade question below comes out in the language the operator
# chose last time instead of reverting to English on every upgrade.
if [ -z "${VPSSRV_DEFAULT_LANG:-}" ]; then
  PREV_LANG="$(unit_env VPSSRV_DEFAULT_LANG)"
  case "$PREV_LANG" in
    en|zh_cn|zh_tw) VPSSRV_DEFAULT_LANG="$PREV_LANG"; INSTALL_LANG="$PREV_LANG" ;;
  esac
fi

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

# openssl generates the first-run self-signed certificate. That is needed
# whenever anything here terminates TLS: the public page always does (port 443
# is half the point of it), and the console does when asked to.
if { [ "${VPSSRV_CONSOLE_TLS:-0}" = "1" ] || [ "${VPSSRV_PUBLIC_ENABLE:-1}" = "1" ]; } \
   && ! command -v openssl >/dev/null 2>&1; then
  die "$(msg no_openssl)"
fi

# ---------------------------------------------------------------------------
# 1a. An existing install, if there is one.
# ---------------------------------------------------------------------------
if existing_install; then
  load_previous
  msg found_install "${PREV_VERSION:-?}" "$PREV_MODULES"
  if [ "$INTERACTIVE" = "1" ]; then
    msg ask_upgrade "$NEW_VERSION"
    read -r upgrade_answer </dev/tty || upgrade_answer="y"
    case "$upgrade_answer" in
      [nN]*) UPGRADE=0 ;;
      *) UPGRADE=1 ;;
    esac
  else
    # Unattended runs upgrade. Silently reconfiguring a host that is already
    # set up is the more destructive of the two defaults, and `curl | bash`
    # cannot be asked.
    UPGRADE=1
  fi
  if [ "$UPGRADE" = "1" ]; then
    apply_previous
    preserve_anytls
  else
    msg reconfigure
  fi
fi

# ---------------------------------------------------------------------------
# 1b. Modules.
# ---------------------------------------------------------------------------
MODULES="${VPSSRV_MODULES:-}"
if [ -z "$MODULES" ] && [ "$UPGRADE" = "1" ]; then
  MODULES="$PREV_MODULES"   # upgrading means the same modules, not a re-pick
fi
if [ -z "$MODULES" ]; then
  if [ "$INTERACTIVE" = "1" ]; then
    msg mod_head
    msg ask_modules
    read -r mod_choice </dev/tty || mod_choice="1"
    case "$mod_choice" in
      2) MODULES="web" ;;
      3) MODULES="web,iperf3,anytls" ;;
      4) MODULES="anytls" ;;
      *) MODULES="$DEFAULT_MODULES" ;;
    esac
  else
    MODULES="$DEFAULT_MODULES"
  fi
fi
msg modules_are "$MODULES"

if [ "$UPGRADE" = "1" ]; then
  prompt_new_settings
fi

# The vendored sing-box binary is amd64. Skipping the module beats installing
# a binary that cannot execute and failing later with "Exec format error".
if has_module anytls; then
  ARCH="$(uname -m)"
  case "$ARCH" in
    x86_64|amd64) ;;
    *) msg anytls_arch "$ARCH"; MODULES="${MODULES//anytls/}" ;;
  esac
fi

install_iperf3() {
  command -v iperf3 >/dev/null 2>&1 && return 0
  msg iperf_installing
  if ! { apt-get update -qq && apt-get install -y -qq iperf3; } >/dev/null 2>&1; then
    msg iperf_failed
    return 0   # a missing iperf3 disables one console button, not the install
  fi
}

install_anytls() {
  msg anytls_start
  # Its own script owns everything anytls: deps, binary, config, unit,
  # firewall, BBR, and the client-config summary it prints at the end.
  ANYTLS_PORT="${ANYTLS_PORT:-}" ANYTLS_PASSWORD="${ANYTLS_PASSWORD:-}" \
  SNI="${SNI:-www.bing.com}" SERVER_IP="${SERVER_IP:-}" \
    bash "$PREFIX/anytls/setup-anytls.sh"
}

# Refuse to fight for 80/443 rather than letting systemd restart-loop on a
# port that will never be free. Our own listener is excluded by stopping the
# service first — on a re-run it is the process holding the port.
port_held() {
  ss -lnt "( sport = :$1 )" 2>/dev/null | tail -n +2 | grep -q .
}

if has_module web && [ "${VPSSRV_PUBLIC_ENABLE:-1}" = "1" ]; then
  systemctl stop "$SERVICE_NAME" >/dev/null 2>&1 || true
  if command -v ss >/dev/null 2>&1; then
    for p in "$PUBLIC_HTTP_PORT" "$PUBLIC_HTTPS_PORT"; do
      if port_held "$p"; then
        die "$(msg port_busy "$p" "$p")"
      fi
    done
  fi
fi

# anytls on its own: nothing below this point applies, since all of it exists
# to install and configure the Python service.
if ! has_module web; then
  mkdir -p "$PREFIX"
  PREFIX_ABS_EARLY="$(cd "$PREFIX" && pwd)"
  if [ "$SRC_DIR" != "$PREFIX_ABS_EARLY" ]; then
    for item in anytls sing-box; do
      [ -e "$SRC_DIR/$item" ] || continue
      rm -rf "${PREFIX:?}/$item"
      cp -r "$SRC_DIR/$item" "$PREFIX/"
    done
  fi
  ANYTLS_FAILED=0
  if has_module anytls; then
    install_anytls || ANYTLS_FAILED=1
  fi
  [ "$ANYTLS_FAILED" = "0" ] && write_state
  msg to_remove "$PREFIX" "$SERVICE_NAME"
  [ "$ANYTLS_FAILED" = "0" ] || { msg anytls_failed >&2; exit 1; }
  exit 0
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
  # Anything that is not R or M is re-asked rather than quietly treated as
  # "random". An operator who types something else has not chosen random —
  # they have misread the question, and silently handing them a generated
  # password looks identical to having honoured an answer. This is the same
  # mistake the port prompt made (vps-webserver DECISIONS.md, 2026-08-25:
  # the operator answered "50" and got a random port).
  while :; do
    msg ask_pwmode
    read -r pwmode </dev/tty || pwmode="r"
    case "$pwmode" in
      ""|[rR]*) break ;;
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
        break
        ;;
      *) msg pwmode_invalid ;;
    esac
  done
fi

# ---------------------------------------------------------------------------
# 3. Port: random (default, see DECISIONS.md) or an operator-chosen one.
# ---------------------------------------------------------------------------
# One question, not two: an operator looking at a port prompt types a port
# number. Asking "random or custom?" first and *then* for the number meant a
# typed number fell through to the random branch (reported 2026-08-25: the
# operator answered "50" and silently got a random port).
if [ -z "${VPSSRV_CONSOLE_PORT:-}" ] && [ "$INTERACTIVE" = "1" ] \
   && [ ! -f "${VPSSRV_CONSOLE_PORT_FILE:-$PREFIX/console_port.txt}" ]; then
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
  COPY_ITEMS="app.py static systemd tests README.md LICENSE LICENSES
              THIRD_PARTY_NOTICES.md CHANGELOG.md
              translated_zh_cn translated_zh_tw"
  # The sing-box binary is ~57 MB. Copying it into an install that will never
  # run anytls is pure waste, so it travels with its module.
  has_module anytls && COPY_ITEMS="$COPY_ITEMS anytls sing-box"
  for item in $COPY_ITEMS; do
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
for var in $KNOWN_VARS; do
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

has_module iperf3 && install_iperf3

msg writing_unit "$UNIT_PATH"
cat > "$UNIT_PATH" <<EOF
[Unit]
Description=vps-server — public reachability page, speed-test console, iperf3 window
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
PORT_FILE="${VPSSRV_CONSOLE_PORT_FILE:-$PREFIX/console_port.txt}"
if [ "${VPSSRV_CONSOLE_TLS:-0}" = "1" ]; then SCHEME=https; else SCHEME=http; fi
# VPSSRV_CONSOLE_PORT, if set, was carried into the unit verbatim. Otherwise app.py
# picked a random port on this first start and persisted it to PORT_FILE.
PORT="${VPSSRV_CONSOLE_PORT:-}"
if [ -z "$PORT" ] && [ -f "$PORT_FILE" ]; then
  PORT="$(cat "$PORT_FILE")"
fi

# Written only once the service is confirmed healthy, so a failed install does
# not leave behind a record claiming it succeeded.
write_state

msg running
msg line_modules "$MODULES"
msg line_service "$SERVICE_NAME"
if [ "${VPSSRV_PUBLIC_ENABLE:-1}" = "1" ]; then
  msg line_public "$PUBLIC_HTTP_PORT" "$PUBLIC_HTTPS_PORT"
else
  msg line_public_off
fi
if [ -n "$PORT" ]; then
  msg line_url "$SCHEME" "$PORT"
else
  msg line_url_unknown "$SCHEME" "$PORT_FILE" "$SERVICE_NAME"
fi
if command -v iperf3 >/dev/null 2>&1; then
  msg line_iperf "${VPSSRV_IPERF_PORT:-5201}"
else
  msg line_iperf_off
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

# Last, and after the web service is confirmed healthy: the anytls script
# prints a client-configuration block of its own, and burying that above the
# web summary would make it easy to miss.
# `has_module anytls && install_anytls` looks equivalent, but under `set -e` a
# failing install_anytls kills the script right here — before the teardown hint
# is printed, and with a non-zero exit that makes the already-installed and
# already-running web module look like it failed too. That is exactly what
# happened on the first anytls install attempt.
ANYTLS_FAILED=0
if has_module anytls; then
  install_anytls || ANYTLS_FAILED=1
fi

msg to_remove "$PREFIX" "$SERVICE_NAME"

if [ "$ANYTLS_FAILED" = "1" ]; then
  msg anytls_failed >&2
  exit 1
fi
