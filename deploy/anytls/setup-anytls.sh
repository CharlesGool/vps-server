#!/usr/bin/env bash
# 独立的 sing-box anytls 单协议安装脚本（Ubuntu/Debian）
# 只装 anytls 一个协议 + 开启 BBR 加速，不依赖第三方一键脚本仓库。
#
# Vendored from Anytsl-Serve v1.2.0 —— 来源与改动记录在 anytls/.upstream-version。
# 服务名、配置目录、二进制路径都带上了 vps-server 前缀，且本项目
# 增加了本地修正与多语言输出；完整偏差记录见 anytls/.upstream-version。
# 环境变量名（ANYTLS_PORT / ANYTLS_PASSWORD / SNI）刻意保持上游原样：
# 改名就等于改 vendored 代码，而这正是 vendoring 策略要避免的事。
set -Eeuo pipefail

# ========== 可配置项（可用环境变量覆盖，例如 ANYTLS_PORT=12345 bash setup-anytls.sh）==========
ANYTLS_PORT="${ANYTLS_PORT:-$(( (RANDOM % 20000) + 20000 ))}"
ANYTLS_PASSWORD="${ANYTLS_PASSWORD:-$(openssl rand -base64 16)}"
SNI="${SNI:-www.bing.com}"           # 伪装用的 SNI，客户端 insecure=1 不校验证书，可随意填一个常见域名

INSTALL_DIR=/etc/vps-server-anytls
BIN_PATH=/usr/local/bin/sing-box-vps-server
SERVICE_NAME=vps-server-anytls.service
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 仓库内存放在 vendor/；部署后仍位于 PREFIX 根目录。
LOCAL_BIN="${SCRIPT_DIR}/../sing-box"
if [[ -f "${SCRIPT_DIR}/../../third_party/sing-box/sing-box" ]]; then
  LOCAL_BIN="${SCRIPT_DIR}/../../third_party/sing-box/sing-box"
fi

# Anytsl-Serve 自己的服务名是 sing-box-anytls.service。名字不同所以不会互相覆盖，
# 但一台机器上跑两个 anytls 入站几乎一定是失误而不是意图。
UPSTREAM_SERVICE=sing-box-anytls.service

# Native message catalogs are carried with the installed module. The checkout
# keeps this script under deploy/anytls; an installed copy lives under anytls.
if [[ -f "${SCRIPT_DIR}/../lang/anytls/en.sh" ]]; then
  CATALOG_DIR="${SCRIPT_DIR}/../lang/anytls"
else
  CATALOG_DIR="${SCRIPT_DIR}/../../lang/anytls"
fi
ANYTLS_LANG="${VPSSRV_DEFAULT_LANG:-en}"
case "$ANYTLS_LANG" in en|zh_cn|zh_tw|zh_hk|hi|es|ar|fr) ;; *) ANYTLS_LANG=en ;; esac
msg(){
  local key="$1" fmt; shift
  case "$ANYTLS_LANG" in
    zh_cn) source "$CATALOG_DIR/zh-CN.sh" ;;
    zh_tw) source "$CATALOG_DIR/zh-TW.sh" ;;
    zh_hk) source "$CATALOG_DIR/zh-HK.sh" ;;
    hi) source "$CATALOG_DIR/hi.sh" ;;
    es) source "$CATALOG_DIR/es.sh" ;;
    ar) source "$CATALOG_DIR/ar.sh" ;;
    fr) source "$CATALOG_DIR/fr.sh" ;;
    *) source "$CATALOG_DIR/en.sh" ;;
  esac
  # fmt comes from a fixed, repository-owned catalog.
  printf "$fmt" "$@"
}

C_G="\033[32m"; C_R="\033[31m"; C_C="\033[36m"; C_0="\033[0m"
if [[ ${NO_COLOR:-} == 1 ]]; then C_G=""; C_R=""; C_C=""; C_0=""; fi
log(){ echo -e "${C_C}[*]${C_0} $*"; }
ok(){  echo -e "${C_G}[OK]${C_0} $*"; }
err(){ echo -e "${C_R}[ERR]${C_0} $*" >&2; }

[[ $EUID -eq 0 ]] || { err "$(msg need_root "$0")"; exit 1; }

install_deps(){
  log "$(msg checking_deps)"
  export DEBIAN_FRONTEND=noninteractive

  local pkgs=(curl jq openssl ca-certificates iproute2 procps iptables)
  local missing=()
  local p
  for p in "${pkgs[@]}"; do
    dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p")
  done

  if [[ ${#missing[@]} -eq 0 ]]; then
    ok "$(msg deps_installed)"
    return 0
  fi

  log "$(msg deps_missing "${missing[*]}")"

  local log_file attempt
  log_file="$(mktemp)"
  for attempt in 1 2 3; do
    if apt-get update -y 2>&1 | tee "$log_file"; then
      break
    fi
    if [[ $attempt -eq 3 ]]; then
      err "$(msg apt_update_failed)"
      err "$(msg apt_update_output)"
      rm -f "$log_file"
      exit 1
    fi
    log "$(msg apt_update_retry "$attempt")"
    sleep 2
  done

  if ! apt-get install -y "${missing[@]}" 2>&1 | tee "$log_file"; then
    err "$(msg deps_failed "${missing[*]}")"
    err "$(msg apt_install_output)"
    rm -f "$log_file"
    err "$(msg apt_manual "${missing[*]}")"
    exit 1
  fi
  rm -f "$log_file"

  ok "$(msg deps_ready)"
}

install_singbox(){
  if [[ -x "$BIN_PATH" ]]; then
    ok "$(msg singbox_present "$("$BIN_PATH" version | head -n1)")"
    return 0
  fi

  # 用 -f 判断，不是上游的 -x。`install -m 0755` 会给目标设好可执行位，源文件
  # 自己可不可执行根本无所谓；而可执行位在 CIFS/SMB 工作副本上存不住，也可能
  # 在打包、解压、传输途中丢掉。用 -x 判断的后果是：文件明明就在那儿，却报
  # 「未找到」——排查的人会去找一个根本没丢的文件。
  if [[ -f "$LOCAL_BIN" ]]; then
    log "$(msg singbox_local "$LOCAL_BIN")"
    install -m 0755 "$LOCAL_BIN" "$BIN_PATH"
    ok "$(msg singbox_installed "$("$BIN_PATH" version | head -n1)")"
    return 0
  fi

  if [[ -e "$LOCAL_BIN" ]]; then
    err "$(msg singbox_not_file "$LOCAL_BIN")"
  else
    err "$(msg singbox_missing "$LOCAL_BIN" "$BIN_PATH")"
  fi
  exit 1
}

setup_config(){
  mkdir -p "${INSTALL_DIR}/cert"
  local crt="${INSTALL_DIR}/cert/fullchain.pem" key="${INSTALL_DIR}/cert/key.pem"
  if [[ ! -f "$crt" || ! -f "$key" ]]; then
    log "$(msg cert_generating "$SNI")"
    openssl req -x509 -nodes -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 \
      -keyout "$key" -out "$crt" -days 3650 -subj "/CN=${SNI}" >/dev/null 2>&1
  fi

  cat > "${INSTALL_DIR}/config.json" <<JSON
{
  "log": { "level": "info", "timestamp": true },
  "inbounds": [
    {
      "type": "anytls",
      "tag": "anytls-in",
      "listen": "::",
      "listen_port": ${ANYTLS_PORT},
      "users": [ { "name": "anytls", "password": "${ANYTLS_PASSWORD}" } ],
      "tls": { "enabled": true, "certificate_path": "${crt}", "key_path": "${key}" }
    }
  ],
  "outbounds": [
    { "type": "direct", "tag": "direct" },
    { "type": "block", "tag": "block" }
  ],
  "route": { "final": "direct" }
}
JSON

  "$BIN_PATH" check -c "${INSTALL_DIR}/config.json"
  ok "$(msg config_written "${INSTALL_DIR}/config.json")"
}

setup_service(){
  cat > "/etc/systemd/system/${SERVICE_NAME}" <<EOF
[Unit]
Description=sing-box anytls (single protocol)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=${BIN_PATH} run -c ${INSTALL_DIR}/config.json
Restart=on-failure
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable "${SERVICE_NAME}" >/dev/null 2>&1
  if [[ ${VPSSRV_DEFER_NODE_START:-0} == 1 ]]; then
    return 0
  fi
  systemctl restart "${SERVICE_NAME}"
  sleep 1
  if systemctl is-active --quiet "${SERVICE_NAME}"; then
    ok "$(msg service_started)"
  else
    err "$(msg service_failed "$SERVICE_NAME")"
    exit 1
  fi
}

open_firewall(){
  log "$(msg firewall_open "$ANYTLS_PORT")"
  if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw allow "${ANYTLS_PORT}/tcp" >/dev/null 2>&1 || true
  elif command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    firewall-cmd --permanent --add-port="${ANYTLS_PORT}/tcp" >/dev/null 2>&1 || true
    firewall-cmd --reload >/dev/null 2>&1 || true
  elif command -v iptables >/dev/null 2>&1; then
    # stdout 也要丢掉，不只是 stderr：iptables-nft（Ubuntu 22.04 起的默认）
    # 在 -C 命中时会把匹配到的规则原样打出来，于是一行原始 iptables 输出
    # 混进操作者要读的安装摘要里。上游只挡了 stderr，因为规则第一次总是
    # 不存在、-C 总是失败——重复安装才看得见。
    # -I 的失败要接住。ufw / firewalld 两个分支都有 `|| true`，这条没有，而它
    # 是 || 列表的最后一条命令——在 set -Eeuo pipefail 下失败就整个脚本硬退出，
    # 一句提示都没有，而此时服务其实已经起来了。装完看到的是一次「像是失败」
    # 的安装。
    if ! iptables -C INPUT -p tcp --dport "${ANYTLS_PORT}" -j ACCEPT >/dev/null 2>&1; then
      if ! iptables -I INPUT -p tcp --dport "${ANYTLS_PORT}" -j ACCEPT; then
        err "$(msg firewall_iptables_failed "$ANYTLS_PORT")"
        return 0
      fi
    fi
    command -v netfilter-persistent >/dev/null 2>&1 && netfilter-persistent save >/dev/null 2>&1 || true
  else
    err "$(msg firewall_missing)"
    err "$(msg firewall_manual "$ANYTLS_PORT")"
    return 0
  fi
  ok "$(msg firewall_handled)"
}

# 撤掉某个端口的放行规则。原本这段代码内联在 uninstall 里，reset 也需要它——
# 换端口时如果不先撤旧规则，每重置一次就在防火墙里留一条指向没人监听的端口的
# ACCEPT。抄一份的结果是两份迟早不一致，所以提出来共用。
close_firewall(){
  local port="$1"
  [[ -n "$port" ]] || return 0
  log "$(msg firewall_close "$port")"
  if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw delete allow "${port}/tcp" >/dev/null 2>&1 || true
  elif command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    firewall-cmd --permanent --remove-port="${port}/tcp" >/dev/null 2>&1 || true
    firewall-cmd --reload >/dev/null 2>&1 || true
  elif command -v iptables >/dev/null 2>&1; then
    iptables -D INPUT -p tcp --dport "${port}" -j ACCEPT 2>/dev/null || true
    command -v netfilter-persistent >/dev/null 2>&1 && netfilter-persistent save >/dev/null 2>&1 || true
  else
    log "$(msg firewall_cleanup_missing)"
  fi
  ok "$(msg firewall_cleaned)"
}

# 写入新配置、切换服务，然后把防火墙从旧端口挪到新端口。
#
# 顺序是刻意的：先把新状态写成功，再动防火墙。反过来（先撤旧规则再写配置）
# 在写失败时会留下一个跑着但没放行的节点——比没改成更糟。
#
# 旧端口必须在 setup_config 覆盖 config.json **之前**读出来；那之后它就没了，
# 规则会变成指向无人监听端口的孤儿。之前只有 reset 做这件事，于是从安装器的
# 「重新配置」分支换端口时每次都漏一条。
apply_node(){
  local prev_port
  prev_port="$(current_port)"
  setup_config
  setup_service
  if [[ -n "$prev_port" && "$prev_port" != "$ANYTLS_PORT" ]]; then
    close_firewall "$prev_port"
  fi
  open_firewall
}

# 当前已安装节点的端口；没装或读不出来就返回空。
current_port(){
  [[ -f "${INSTALL_DIR}/config.json" ]] || return 0
  jq -r '.inbounds[0].listen_port // empty' "${INSTALL_DIR}/config.json" 2>/dev/null || true
}

enable_bbr(){
  if sysctl net.ipv4.tcp_congestion_control 2>/dev/null | grep -q bbr; then
    ok "$(msg bbr_enabled)"
    return
  fi
  log "$(msg bbr_enabling)"
  mkdir -p /etc/sysctl.d
  cat > /etc/sysctl.d/99-bbr.conf <<EOF
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
EOF
  sysctl --system >/dev/null 2>&1 || true
  if sysctl net.ipv4.tcp_congestion_control 2>/dev/null | grep -q bbr; then
    ok "$(msg bbr_enabled)"
  else
    err "$(msg bbr_failed)"
  fi
}

urlenc(){ jq -rn --arg v "$1" '$v|@uri'; }

get_lan_ips(){
  local iface cidr
  while read -r iface cidr; do
    case "$iface" in
      docker*|br-*|veth*|virbr*|cni*|flannel*|kube*|tailscale*) continue ;;
    esac
    echo "${iface} ${cidr%%/*}"
  done < <(ip -o -4 addr show scope global 2>/dev/null | awk '{print $2, $4}')
}

get_tailscale_ip(){
  if command -v tailscale >/dev/null 2>&1; then
    tailscale ip -4 2>/dev/null | head -n1
  elif ip -o -4 addr show tailscale0 >/dev/null 2>&1; then
    ip -o -4 addr show tailscale0 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -n1
  fi
}

clash_line(){
  local name="$1" server="$2"
  printf -- '- { name: %s, type: anytls, server: %s, port: %s, password: "%s", sni: %s, skip-cert-verify: true, udp: true }\n' \
    "$name" "$server" "$ANYTLS_PORT" "$ANYTLS_PASSWORD" "$SNI"
}

share_link(){
  local name="$1" server="$2"
  printf 'anytls://%s@%s:%s?insecure=1&sni=%s#%s\n' \
    "$(urlenc "$ANYTLS_PASSWORD")" "$server" "$ANYTLS_PORT" "$SNI" "$(urlenc "$name")"
}

print_result(){
  local ts_ip iface ip entries=() entry label seen=()

  is_seen(){ local needle="$1" s; for s in "${seen[@]}"; do [[ "$s" == "$needle" ]] && return 0; done; return 1; }

  rm -f "${INSTALL_DIR}/public-ip.txt"

  while read -r iface ip; do
    is_seen "$ip" && continue
    entries+=("$(msg address_lan "$iface")|${ip}")
    seen+=("$ip")
  done < <(get_lan_ips)

  ts_ip="$(get_tailscale_ip)"
  if [[ -n "$ts_ip" ]] && ! is_seen "$ts_ip"; then
    entries+=("Tailscale|${ts_ip}")
    seen+=("$ts_ip")
  fi

  echo
  echo "========================================"
  echo "$(msg summary_heading)"
  echo "========================================"
  echo "$(msg summary_port "$ANYTLS_PORT")"
  echo "$(msg summary_password "$ANYTLS_PASSWORD")"
  echo "$(msg summary_sni "$SNI")"

  for entry in "${entries[@]}"; do
    label="${entry%%|*}"
    ip="${entry#*|}"
    echo "----------------------------------------"
    echo " [${label}] ${ip}"
    echo "$(msg summary_clash "$(clash_line "anytls-${label}" "$ip")")"
    echo "$(msg summary_link "$(share_link "anytls-${label}" "$ip")")"
  done

  echo "========================================"
  echo "$(msg summary_bbr "$(sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null)")"
  echo "$(msg summary_config "${INSTALL_DIR}/config.json")"
  echo "$(msg summary_service "$SERVICE_NAME")"
  echo "$(msg summary_status "$0")"
  echo "$(msg summary_reinstall "$0")"
  echo "$(msg summary_uninstall "$0")"
  echo
}

show_installed_node(){
  if [[ ! -f "${INSTALL_DIR}/config.json" ]]; then
    err "$(msg installed_config_missing "${INSTALL_DIR}/config.json")"
    err "$(msg install_first "$0")"
    exit 1
  fi

  ANYTLS_PORT="$(jq -er '.inbounds[] | select(.type == "anytls") | .listen_port' "${INSTALL_DIR}/config.json")" \
    || { err "$(msg installed_port_unreadable)"; exit 1; }
  ANYTLS_PASSWORD="$(jq -er '.inbounds[] | select(.type == "anytls") | .users[0].password' "${INSTALL_DIR}/config.json")" \
    || { err "$(msg installed_password_unreadable)"; exit 1; }

  local cert_path
  cert_path="$(jq -r '.inbounds[] | select(.type == "anytls") | .tls.certificate_path // empty' "${INSTALL_DIR}/config.json")"
  if [[ -n "$cert_path" && -f "$cert_path" ]]; then
    SNI="$(openssl x509 -in "$cert_path" -noout -subject 2>/dev/null | sed -n 's/.*CN[[:space:]]*=[[:space:]]*//p')"
  fi
  SNI="${SNI:-$(msg sni_unreadable)}"

  print_result
  if systemctl is-active --quiet "${SERVICE_NAME}"; then
    ok "$(msg service_active)"
  else
    err "$(msg service_inactive "$SERVICE_NAME")"
  fi
}

uninstall(){
  local port=""
  if [[ -f "${INSTALL_DIR}/config.json" ]]; then
    port="$(jq -r '.inbounds[0].listen_port // empty' "${INSTALL_DIR}/config.json" 2>/dev/null || true)"
  fi

  log "$(msg service_stopping)"
  systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
  systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
  rm -f "/etc/systemd/system/${SERVICE_NAME}"
  systemctl daemon-reload
  systemctl reset-failed 2>/dev/null || true
  ok "$(msg service_removed)"

  log "$(msg config_deleting)"
  rm -rf "$INSTALL_DIR"

  # BIN_PATH is now shared with the proxy module (proxy/setup-proxy.sh, added
  # after this script was last vendored — see .upstream-version). Only remove
  # it if that module isn't relying on it too; deleting it out from under a
  # sibling service would take that service down the next time it restarts.
  if [[ ! -f /etc/vps-server-proxy/config.json ]]; then
    rm -f "$BIN_PATH"
    ok "$(msg removed_binary_and_config "$BIN_PATH" "$INSTALL_DIR")"
  else
    ok "$(msg removed_config_keep_binary "$INSTALL_DIR" "$BIN_PATH")"
  fi

  if [[ -n "$port" ]]; then
    close_firewall "$port"
  else
    log "$(msg old_port_missing)"
  fi

  ok "$(msg uninstall_done)"
  echo "$(msg bbr_retained)"
  echo "$(msg bbr_remove)"
}

# 装之前先确认 Anytsl-Serve 的服务没在跑。两者服务名不同，装上去不会覆盖它，
# 但会多出一个谁都没打算要的 anytls 入站——多占一个端口、多一份要维护的配置，
# 而且出问题时很难看出是哪一个在应答。宁可停下来让人自己决定。
refuse_if_upstream_running(){
  if systemctl is-active --quiet "$UPSTREAM_SERVICE" 2>/dev/null; then
    err "$(msg upstream_running "$UPSTREAM_SERVICE")"
    err "$(msg upstream_choose)"
    err "$(msg upstream_keep)"
    err "$(msg upstream_switch "$UPSTREAM_SERVICE")"
    err "$(msg upstream_both)"
    [[ "${VPSSRV_ALLOW_DUAL_ANYTLS:-0}" == "1" ]] || exit 1
    log "$(msg upstream_override)"
  fi
}

# 换一组端口和密码，别的都不动。ANYTLS_PORT / ANYTLS_PASSWORD 在文件顶部已经
# 取到新的随机值（除非调用方钉死了它们），所以这里不需要再生成。
#
# 证书刻意不重新生成：setup_config 只在证书缺失时才签发，于是 SNI 原样保留。
# 重置的是凭据，不是伪装身份。
#
# 旧端口的放行规则在开新端口之前撤掉，顺序不能反——反了就会有一瞬间两个端口
# 同时开着，而且失败时留下的是旧端口开着、新端口也开着。
reset(){
  local old_port
  # Keep this descriptor open through config writes and service restart.
  exec {node_lock}>/etc/vps-server-node.lock
  flock -x "$node_lock"
  # install_deps 必须排在 current_port 前面：读旧端口要用 jq，jq 不在时
  # current_port 会返回空，于是旧端口的规则被静静跳过——正好是这个函数
  # 存在的理由。
  install_deps

  # 先确认真的写得下去，再动防火墙。第一版没有这道检查：它先撤掉旧端口的
  # 放行规则，然后在写 /etc 时失败退出，留下一个跑着但没放行的节点——比
  # 「没重置成」更糟。写不了就一样东西都别碰。
  if ! mkdir -p "${INSTALL_DIR}" 2>/dev/null \
     || ! touch "${INSTALL_DIR}/.writable" 2>/dev/null; then
    err "$(msg reset_config_readonly "$INSTALL_DIR")"
    err "$(msg reset_sandbox)"
    exit 1
  fi
  rm -f "${INSTALL_DIR}/.writable"
  if ! touch /etc/systemd/system/.vps-server-writable 2>/dev/null; then
    err "$(msg reset_systemd_readonly)"
    exit 1
  fi
  rm -f /etc/systemd/system/.vps-server-writable

  old_port="$(current_port)"
  if [[ -n "$old_port" ]]; then
    log "$(msg reset_port "$old_port" "$ANYTLS_PORT")"
  else
    log "$(msg reset_as_install)"
  fi
  install_singbox
  apply_node
  print_result
}

install_without_nodes(){
  mkdir -p "$INSTALL_DIR"
  if [[ ! -f "$INSTALL_DIR/config.json" ]]; then
    cat > "$INSTALL_DIR/config.json" <<'JSON'
{"log":{"level":"info","timestamp":true},"inbounds":[],"outbounds":[{"type":"direct","tag":"direct"},{"type":"block","tag":"block"}],"route":{"final":"direct"}}
JSON
  fi
  "$BIN_PATH" check -c "$INSTALL_DIR/config.json"
  setup_service
  ok "$(msg config_written "$INSTALL_DIR/config.json")"
}

main(){
  case "${1:-}" in
    uninstall|--uninstall|-u)
      uninstall
      exit 0
      ;;
    reset|--reset)
      reset
      exit 0
      ;;
    status|show|info|--status|-s)
      install_deps
      show_installed_node
      exit 0
      ;;
  esac
  # Installer passes its already-locked descriptor across exec. Reflocking
  # that same open description is safe; opening the path again would deadlock.
  if [[ -n "${VPSSRV_NODE_LOCK_FD:-}" ]]; then
    [[ "$VPSSRV_NODE_LOCK_FD" =~ ^[0-9]+$ ]] &&
      [[ "$(readlink "/proc/self/fd/$VPSSRV_NODE_LOCK_FD")" == /etc/vps-server-node.lock ]] || exit 1
    flock -x "$VPSSRV_NODE_LOCK_FD"
  else
    exec {node_lock}>/etc/vps-server-node.lock
    flock -x "$node_lock"
  fi
  refuse_if_upstream_running
  install_deps
  install_singbox
  if [[ ${VPSSRV_EMPTY_NODE_INSTALL:-0} == 1 ]]; then
    install_without_nodes
    enable_bbr
    return
  fi
  apply_node
  enable_bbr
  print_result
}
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
