#!/usr/bin/env bash
# 独立的 sing-box anytls 单协议安装脚本（Ubuntu/Debian）
# 只装 anytls 一个协议 + 开启 BBR 加速，不依赖第三方一键脚本仓库。
#
# Vendored from Anytsl-Serve v1.2.0 —— 来源与改动记录在 anytls/.upstream-version。
# 与上游的唯一差别是三个名字：服务名、配置目录、二进制路径都带上了 vps-server
# 前缀，这样本项目和 Anytsl-Serve 可以装在同一台机器上而不互相覆盖。
# 环境变量名（ANYTLS_PORT / ANYTLS_PASSWORD / SNI / SERVER_IP）刻意保持上游原样：
# 改名就等于改 vendored 代码，而这正是 vendoring 策略要避免的事。
set -Eeuo pipefail

# ========== 可配置项（可用环境变量覆盖，例如 ANYTLS_PORT=12345 bash setup-anytls.sh）==========
ANYTLS_PORT="${ANYTLS_PORT:-$(( (RANDOM % 20000) + 20000 ))}"
ANYTLS_PASSWORD="${ANYTLS_PASSWORD:-$(openssl rand -base64 16)}"
SNI="${SNI:-www.bing.com}"           # 伪装用的 SNI，客户端 insecure=1 不校验证书，可随意填一个常见域名
SERVER_IP="${SERVER_IP:-}"           # 不填则自动探测公网 IP

INSTALL_DIR=/etc/vps-server-anytls
BIN_PATH=/usr/local/bin/sing-box-vps-server
SERVICE_NAME=vps-server-anytls.service
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 二进制放在仓库根目录，本脚本在 anytls/ 子目录里。
LOCAL_BIN="${SCRIPT_DIR}/../sing-box"

# Anytsl-Serve 自己的服务名是 sing-box-anytls.service。名字不同所以不会互相覆盖，
# 但一台机器上跑两个 anytls 入站几乎一定是失误而不是意图。
UPSTREAM_SERVICE=sing-box-anytls.service

C_G="\033[32m"; C_R="\033[31m"; C_C="\033[36m"; C_0="\033[0m"
log(){ echo -e "${C_C}[*]${C_0} $*"; }
ok(){  echo -e "${C_G}[OK]${C_0} $*"; }
err(){ echo -e "${C_R}[ERR]${C_0} $*" >&2; }

[[ $EUID -eq 0 ]] || { err "请用 root 运行（sudo bash $0）"; exit 1; }

install_deps(){
  log "检查依赖 ..."
  export DEBIAN_FRONTEND=noninteractive

  local pkgs=(curl jq openssl ca-certificates iproute2 procps iptables)
  local missing=()
  local p
  for p in "${pkgs[@]}"; do
    dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p")
  done

  if [[ ${#missing[@]} -eq 0 ]]; then
    ok "依赖已就绪（全部已安装，跳过 apt）"
    return 0
  fi

  log "缺少依赖：${missing[*]}，安装中 ..."

  local log_file attempt
  log_file="$(mktemp)"
  for attempt in 1 2 3; do
    if apt-get update -y >"$log_file" 2>&1; then
      break
    fi
    if [[ $attempt -eq 3 ]]; then
      err "apt-get update 失败（已重试 3 次），无法继续。常见原因：网络不通、apt 源不可达、/etc/apt/sources.list(.d) 配置有误。"
      err "--- apt-get update 输出 ---"
      cat "$log_file" >&2
      rm -f "$log_file"
      exit 1
    fi
    log "apt-get update 第 ${attempt} 次失败，2 秒后重试 ..."
    sleep 2
  done

  if ! apt-get install -y "${missing[@]}" >"$log_file" 2>&1; then
    err "安装依赖失败：${missing[*]}"
    err "--- apt-get install 输出 ---"
    cat "$log_file" >&2
    rm -f "$log_file"
    err "请手动运行 'apt-get install -y ${missing[*]}' 查看具体报错（常见原因：源缺失/损坏、磁盘空间不足、包名在当前发行版下不可用），解决后重新执行本脚本。"
    exit 1
  fi
  rm -f "$log_file"

  ok "依赖就绪"
}

install_singbox(){
  if [[ -x "$BIN_PATH" ]]; then
    ok "sing-box 已安装: $("$BIN_PATH" version | head -n1)"
    return 0
  fi

  # 用 -f 判断，不是上游的 -x。`install -m 0755` 会给目标设好可执行位，源文件
  # 自己可不可执行根本无所谓；而可执行位在 CIFS/SMB 工作副本上存不住，也可能
  # 在打包、解压、传输途中丢掉。用 -x 判断的后果是：文件明明就在那儿，却报
  # 「未找到」——排查的人会去找一个根本没丢的文件。
  if [[ -f "$LOCAL_BIN" ]]; then
    log "发现本地二进制 ${LOCAL_BIN}，安装中 ..."
    install -m 0755 "$LOCAL_BIN" "$BIN_PATH"
    ok "安装完成: $("$BIN_PATH" version | head -n1)"
    return 0
  fi

  if [[ -e "$LOCAL_BIN" ]]; then
    err "${LOCAL_BIN} 存在但不是普通文件，无法安装"
  else
    err "未找到本地二进制 ${LOCAL_BIN}，且 ${BIN_PATH} 也不存在，无法安装"
  fi
  exit 1
}

setup_config(){
  mkdir -p "${INSTALL_DIR}/cert"
  local crt="${INSTALL_DIR}/cert/fullchain.pem" key="${INSTALL_DIR}/cert/key.pem"
  if [[ ! -f "$crt" || ! -f "$key" ]]; then
    log "生成自签证书 (SNI=${SNI}) ..."
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
  ok "配置已写入 ${INSTALL_DIR}/config.json（校验通过）"
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
  systemctl restart "${SERVICE_NAME}"
  sleep 1
  if systemctl is-active --quiet "${SERVICE_NAME}"; then
    ok "服务已启动"
  else
    err "服务启动失败，运行: journalctl -u ${SERVICE_NAME} -e"
    exit 1
  fi
}

open_firewall(){
  log "放行端口 ${ANYTLS_PORT}/tcp ..."
  if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw allow "${ANYTLS_PORT}/tcp" >/dev/null 2>&1 || true
  elif command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    firewall-cmd --permanent --add-port="${ANYTLS_PORT}/tcp" >/dev/null 2>&1 || true
    firewall-cmd --reload >/dev/null 2>&1 || true
  elif command -v iptables >/dev/null 2>&1; then
    iptables -C INPUT -p tcp --dport "${ANYTLS_PORT}" -j ACCEPT 2>/dev/null \
      || iptables -I INPUT -p tcp --dport "${ANYTLS_PORT}" -j ACCEPT
    command -v netfilter-persistent >/dev/null 2>&1 && netfilter-persistent save >/dev/null 2>&1 || true
  else
    err "未找到可用的防火墙管理工具（ufw/firewalld/iptables），已跳过自动放行。"
    err "服务仍已安装并启动；请在系统或云服务商安全组中手动放行 ${ANYTLS_PORT}/tcp。"
    return 0
  fi
  ok "防火墙规则已处理"
}

enable_bbr(){
  if sysctl net.ipv4.tcp_congestion_control 2>/dev/null | grep -q bbr; then
    ok "BBR 已启用"
    return
  fi
  log "开启 BBR ..."
  mkdir -p /etc/sysctl.d
  cat > /etc/sysctl.d/99-bbr.conf <<EOF
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
EOF
  sysctl --system >/dev/null 2>&1 || true
  if sysctl net.ipv4.tcp_congestion_control 2>/dev/null | grep -q bbr; then
    ok "BBR 已启用"
  else
    err "BBR 开启失败（内核可能 <4.9 或未编译 tcp_bbr 模块，需升级内核）"
  fi
}

urlenc(){ jq -rn --arg v "$1" '$v|@uri'; }

get_ip(){
  [[ -n "$SERVER_IP" ]] && { echo "$SERVER_IP"; return; }
  curl -fsSL4 --max-time 5 https://api.ip.sb/ip 2>/dev/null \
    || curl -fsSL4 --max-time 5 https://ifconfig.me 2>/dev/null \
    || echo "<自动获取失败，请手动替换为服务器公网IP>"
}

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
  local wan_ip ts_ip iface ip entries=() entry label

  wan_ip="$(get_ip)"
  entries+=("公网|${wan_ip}")

  while read -r iface ip; do
    entries+=("内网-${iface}|${ip}")
  done < <(get_lan_ips)

  ts_ip="$(get_tailscale_ip)"
  [[ -n "$ts_ip" ]] && entries+=("Tailscale|${ts_ip}")

  echo
  echo "========================================"
  echo " anytls 节点信息"
  echo "========================================"
  echo " 端口: ${ANYTLS_PORT}"
  echo " 密码: ${ANYTLS_PASSWORD}"
  echo " SNI : ${SNI}"

  for entry in "${entries[@]}"; do
    label="${entry%%|*}"
    ip="${entry#*|}"
    echo "----------------------------------------"
    echo " [${label}] ${ip}"
    echo "   Clash: $(clash_line "anytls-${label}" "$ip")"
    echo "   链接  : $(share_link "anytls-${label}" "$ip")"
  done

  echo "========================================"
  echo " 系统加速(BBR): $(sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null)"
  echo " 配置文件: ${INSTALL_DIR}/config.json"
  echo " 服务管理: systemctl {status|restart|stop} ${SERVICE_NAME}"
  echo " 查看节点: bash $0 status"
  echo " 重装/改端口: ANYTLS_PORT=新端口 bash $0"
  echo " 卸载: bash $0 uninstall"
  echo
}

show_installed_node(){
  if [[ ! -f "${INSTALL_DIR}/config.json" ]]; then
    err "未找到已安装节点配置：${INSTALL_DIR}/config.json"
    err "请先运行: bash $0"
    exit 1
  fi

  ANYTLS_PORT="$(jq -er '.inbounds[] | select(.type == "anytls") | .listen_port' "${INSTALL_DIR}/config.json")" \
    || { err "无法从已安装配置读取 anytls 端口"; exit 1; }
  ANYTLS_PASSWORD="$(jq -er '.inbounds[] | select(.type == "anytls") | .users[0].password' "${INSTALL_DIR}/config.json")" \
    || { err "无法从已安装配置读取 anytls 密码"; exit 1; }

  local cert_path
  cert_path="$(jq -r '.inbounds[] | select(.type == "anytls") | .tls.certificate_path // empty' "${INSTALL_DIR}/config.json")"
  if [[ -n "$cert_path" && -f "$cert_path" ]]; then
    SNI="$(openssl x509 -in "$cert_path" -noout -subject 2>/dev/null | sed -n 's/.*CN[[:space:]]*=[[:space:]]*//p')"
  fi
  SNI="${SNI:-<无法读取，请查看证书>}"

  print_result
  if systemctl is-active --quiet "${SERVICE_NAME}"; then
    ok "服务状态: active"
  else
    err "服务状态: inactive（查看日志: journalctl -u ${SERVICE_NAME} -e）"
  fi
}

uninstall(){
  local port=""
  if [[ -f "${INSTALL_DIR}/config.json" ]]; then
    port="$(jq -r '.inbounds[0].listen_port // empty' "${INSTALL_DIR}/config.json" 2>/dev/null || true)"
  fi

  log "停止并禁用服务 ..."
  systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
  systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
  rm -f "/etc/systemd/system/${SERVICE_NAME}"
  systemctl daemon-reload
  systemctl reset-failed 2>/dev/null || true
  ok "服务已移除"

  log "删除二进制和配置 ..."
  rm -f "$BIN_PATH"
  rm -rf "$INSTALL_DIR"
  ok "已删除 ${BIN_PATH} 与 ${INSTALL_DIR}"

  if [[ -n "$port" ]]; then
    log "回收端口 ${port}/tcp 的防火墙规则 ..."
    if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
      ufw delete allow "${port}/tcp" >/dev/null 2>&1 || true
    elif command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
      firewall-cmd --permanent --remove-port="${port}/tcp" >/dev/null 2>&1 || true
      firewall-cmd --reload >/dev/null 2>&1 || true
    elif command -v iptables >/dev/null 2>&1; then
      iptables -D INPUT -p tcp --dport "${port}" -j ACCEPT 2>/dev/null || true
      command -v netfilter-persistent >/dev/null 2>&1 && netfilter-persistent save >/dev/null 2>&1 || true
    else
      log "未找到 ufw/firewalld/iptables，跳过本机防火墙规则清理"
    fi
    ok "防火墙规则已清理"
  else
    log "未找到历史端口信息，跳过防火墙规则清理（如有需要请手动检查 iptables/ufw）"
  fi

  ok "卸载完成"
  echo " 注意: BBR (/etc/sysctl.d/99-bbr.conf) 未回退，它是通用系统优化，与 anytls 无强绑定。"
  echo " 如需一并回退，运行: rm -f /etc/sysctl.d/99-bbr.conf && sysctl --system"
}

# 装之前先确认 Anytsl-Serve 的服务没在跑。两者服务名不同，装上去不会覆盖它，
# 但会多出一个谁都没打算要的 anytls 入站——多占一个端口、多一份要维护的配置，
# 而且出问题时很难看出是哪一个在应答。宁可停下来让人自己决定。
refuse_if_upstream_running(){
  if systemctl is-active --quiet "$UPSTREAM_SERVICE" 2>/dev/null; then
    err "检测到 ${UPSTREAM_SERVICE} 正在运行（那是 Anytsl-Serve 装的）。"
    err "一台机器上两个 anytls 入站几乎一定是失误。二选一后再装本模块："
    err "  想保留 Anytsl-Serve：跳过本模块，只装 web / iperf3。"
    err "  想改用 vps-server  ：先 systemctl disable --now ${UPSTREAM_SERVICE}"
    err "  确实两个都要      ：VPSSRV_ALLOW_DUAL_ANYTLS=1 再跑一次，并自行确保端口不冲突。"
    [[ "${VPSSRV_ALLOW_DUAL_ANYTLS:-0}" == "1" ]] || exit 1
    log "VPSSRV_ALLOW_DUAL_ANYTLS=1，继续安装第二个 anytls 入站。"
  fi
}

main(){
  case "${1:-}" in
    uninstall|--uninstall|-u)
      uninstall
      exit 0
      ;;
    status|show|info|--status|-s)
      install_deps
      show_installed_node
      exit 0
      ;;
  esac
  refuse_if_upstream_running
  install_deps
  install_singbox
  setup_config
  setup_service
  open_firewall
  enable_bbr
  print_result
}
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
