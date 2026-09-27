#!/usr/bin/env bash
# Multi-protocol sing-box proxy module (vmess / vless / trojan / shadowsocks).
#
# First-party to vps-server — NOT vendored from anywhere, unlike
# anytls/setup-anytls.sh. The 2026-09-19 "Support more proxy protocols"
# item in doc/LOG.md#completed-work-history asked whether the already-vendored sing-box binary covers
# vmess/vless/trojan/shadowsocks or a second backend would be needed; it was
# tested directly (each protocol's config passed `sing-box check`, and all
# four ran simultaneously in one process and bound their ports) and does, so
# no second backend was added. See doc/LOG.md#decisions for the reasoning.
#
# Deliberately one service, one config.json, up to four simultaneous
# inbounds — not four separate services like a naive per-protocol clone of
# anytls/setup-anytls.sh would give. Reasons: it is one systemd unit to
# monitor instead of four, one shared self-signed certificate instead of
# three, and it is the shape the pending per-node traffic accounting goal
# (doc/DESIGN.md#design-goals) will want — one process whose inbounds list is already
# the node list.
#
# The vendored sing-box binary (BIN_PATH) is SHARED with anytls/setup-anytls.sh
# — both modules point their own systemd unit at the same installed binary.
# install_singbox() below is intentionally a duplicate of the one in
# setup-anytls.sh, not a shared/sourced function, for the same reason that
# script gives for its own small duplicated helpers: each module must stay
# runnable standalone, whichever one is installed first. uninstall() at the
# bottom checks whether the OTHER module's config still exists before
# deleting the shared binary — deleting it out from under a sibling service
# would take that service down the next time it restarts.
set -Eeuo pipefail

# ========== 可配置项 ==========
PROXY_PROTOCOLS="${PROXY_PROTOCOLS:-vmess,vless,trojan,shadowsocks}"
PROXY_SNI="${PROXY_SNI:-www.bing.com}"
SERVER_IP="${SERVER_IP:-}"

INSTALL_DIR=/etc/vps-server-proxy
BIN_PATH=/usr/local/bin/sing-box-vps-server
SERVICE_NAME=vps-server-proxy.service
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_BIN="${SCRIPT_DIR}/../sing-box"
if [[ -f "${SCRIPT_DIR}/../../third_party/sing-box/sing-box" ]]; then
  LOCAL_BIN="${SCRIPT_DIR}/../../third_party/sing-box/sing-box"
fi

# The anytls module's own paths — read-only checks from here, never written.
ANYTLS_INSTALL_DIR=/etc/vps-server-anytls
ANYTLS_CONFIG="${ANYTLS_INSTALL_DIR}/config.json"

ALL_PROTOCOLS="vmess vless trojan shadowsocks"

# Native catalogs travel with the installed module; the checkout keeps them at
# the repository root. Keep the selected locale consistent with the installer.
if [[ -f "${SCRIPT_DIR}/../lang/proxy/en.sh" ]]; then
  CATALOG_DIR="${SCRIPT_DIR}/../lang/proxy"
else
  CATALOG_DIR="${SCRIPT_DIR}/../../lang/proxy"
fi
PROXY_LANG="${VPSSRV_DEFAULT_LANG:-en}"
case "$PROXY_LANG" in en|zh_cn|zh_tw|zh_hk|hi|es|ar|fr) ;; *) PROXY_LANG=en ;; esac
msg(){
  local key="$1" fmt; shift
  case "$PROXY_LANG" in
    zh_cn) source "$CATALOG_DIR/zh-CN.sh" ;;
    zh_tw) source "$CATALOG_DIR/zh-TW.sh" ;;
    zh_hk) source "$CATALOG_DIR/zh-HK.sh" ;;
    hi) source "$CATALOG_DIR/hi.sh" ;;
    es) source "$CATALOG_DIR/es.sh" ;;
    ar) source "$CATALOG_DIR/ar.sh" ;;
    fr) source "$CATALOG_DIR/fr.sh" ;;
    *) source "$CATALOG_DIR/en.sh" ;;
  esac
  printf "$fmt" "$@"
}

C_G="\033[32m"; C_R="\033[31m"; C_C="\033[36m"; C_0="\033[0m"
log(){ echo -e "${C_C}[*]${C_0} $*"; }
ok(){  echo -e "${C_G}[OK]${C_0} $*"; }
err(){ echo -e "${C_R}[ERR]${C_0} $*" >&2; }

[[ $EUID -eq 0 ]] || { err "$(msg need_root "$0")"; exit 1; }

# ---------------------------------------------------------------------------
# Shared helpers (deliberately duplicated from setup-anytls.sh — see header)
# ---------------------------------------------------------------------------

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
    if apt-get update -y >"$log_file" 2>&1; then break; fi
    if [[ $attempt -eq 3 ]]; then
      err "$(msg apt_update_failed)"
      cat "$log_file" >&2; rm -f "$log_file"; exit 1
    fi
    log "$(msg apt_retry "$attempt")"
    sleep 2
  done
  if ! apt-get install -y "${missing[@]}" >"$log_file" 2>&1; then
    err "$(msg deps_failed "${missing[*]}")"
    cat "$log_file" >&2; rm -f "$log_file"; exit 1
  fi
  rm -f "$log_file"
  ok "$(msg deps_ready)"
}

install_singbox(){
  if [[ -x "$BIN_PATH" ]]; then
    ok "$(msg singbox_installed "$("$BIN_PATH" version | head -n1)")"
    return 0
  fi
  if [[ -f "$LOCAL_BIN" ]]; then
    log "$(msg local_binary "$LOCAL_BIN")"
    install -m 0755 "$LOCAL_BIN" "$BIN_PATH"
    ok "$(msg install_complete "$("$BIN_PATH" version | head -n1)")"
    return 0
  fi
  if [[ -e "$LOCAL_BIN" ]]; then
    err "$(msg not_regular "$LOCAL_BIN")"
  else
    err "$(msg binary_missing "$LOCAL_BIN" "$BIN_PATH")"
  fi
  exit 1
}

enable_bbr(){
  if sysctl net.ipv4.tcp_congestion_control 2>/dev/null | grep -q bbr; then
    ok "$(msg bbr_enabled)"
    return
  fi
  log "$(msg enabling_bbr)"
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

get_ip(){
  [[ -n "$SERVER_IP" ]] && { echo "$SERVER_IP"; return; }
  curl -fsSL4 --max-time 5 https://api.ip.sb/ip 2>/dev/null \
    || curl -fsSL4 --max-time 5 https://ifconfig.me 2>/dev/null \
    || msg ip_lookup_failed
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

open_firewall(){
  local port="$1"
  log "$(msg opening_port "$port")"
  if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw allow "${port}/tcp" >/dev/null 2>&1 || true
  elif command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    firewall-cmd --permanent --add-port="${port}/tcp" >/dev/null 2>&1 || true
    firewall-cmd --reload >/dev/null 2>&1 || true
  elif command -v iptables >/dev/null 2>&1; then
    if ! iptables -C INPUT -p tcp --dport "${port}" -j ACCEPT >/dev/null 2>&1; then
      if ! iptables -I INPUT -p tcp --dport "${port}" -j ACCEPT; then
        err "$(msg iptables_failed "$port")"
        return 0
      fi
    fi
    command -v netfilter-persistent >/dev/null 2>&1 && netfilter-persistent save >/dev/null 2>&1 || true
  else
    err "$(msg firewall_missing "$port")"
    return 0
  fi
}

close_firewall(){
  local port="$1"
  [[ -n "$port" ]] || return 0
  log "$(msg closing_port "$port")"
  if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw delete allow "${port}/tcp" >/dev/null 2>&1 || true
  elif command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    firewall-cmd --permanent --remove-port="${port}/tcp" >/dev/null 2>&1 || true
    firewall-cmd --reload >/dev/null 2>&1 || true
  elif command -v iptables >/dev/null 2>&1; then
    iptables -D INPUT -p tcp --dport "${port}" -j ACCEPT 2>/dev/null || true
    command -v netfilter-persistent >/dev/null 2>&1 && netfilter-persistent save >/dev/null 2>&1 || true
  fi
}

# ---------------------------------------------------------------------------
# Protocol selection
# ---------------------------------------------------------------------------

# Validated, de-duplicated, in ALL_PROTOCOLS order, into the global array
# SELECTED_PROTOCOLS — so config.json's inbounds always come out in the same
# order regardless of how the caller wrote the comma list.
#
# Deliberately NOT "echo the list, let the caller capture it with $(...)".
# `exit 1` inside a command-substitution subshell only kills the subshell —
# the parent script sees a merely-empty captured string and, under `set -e`,
# does not even notice, because the failing exit status belongs to the
# subshell that already exited, not to whatever command consumed its output.
# The first real run of this script did exactly that: an unknown protocol
# name printed its error and then went on to install a service with an EMPTY
# inbounds list. Same class of bug as the 2026-09-21 entry in
# doc/LOG.md#decisions on `prompt_new_settings()` — an exit status quietly absorbed by the wrong
# shell. Setting a global array instead means `exit 1` here really is
# `exit 1` for the whole script.
compute_selected_protocols(){
  local wanted=",${PROXY_PROTOCOLS//[[:space:]]/}," proto
  # Reject unknown tokens outright rather than silently ignoring a typo —
  # The iperf3-only install in doc/LOG.md#completed-work-history illustrates
  # this class of bug: a bad value that looks like it did something.
  local token tokens
  IFS=',' read -ra tokens <<< "${PROXY_PROTOCOLS//[[:space:]]/}"
  for token in "${tokens[@]}"; do
    [[ -z "$token" ]] && continue
    case " $ALL_PROTOCOLS " in
      *" $token "*) ;;
      *) err "$(msg unknown_protocol "$token" "${ALL_PROTOCOLS// /, }")"; exit 1 ;;
    esac
  done
  SELECTED_PROTOCOLS=()
  for proto in $ALL_PROTOCOLS; do
    case "$wanted" in *",${proto},"*) SELECTED_PROTOCOLS+=("$proto") ;; esac
  done
  if [[ ${#SELECTED_PROTOCOLS[@]} -eq 0 ]]; then
    err "$(msg no_protocol "${ALL_PROTOCOLS// /, }" "$PROXY_PROTOCOLS")"
    exit 1
  fi
}

rand_port(){
  # Distinct, non-overlapping 5000-wide ranges per protocol purely so a fresh
  # install's four ports don't collide with each other by construction; this
  # does not check against anything else already listening (including
  # anytls's own 20000-39999 random pick, which these ranges deliberately
  # sit above), same limitation anytls's own random port pick already has.
  #
  # Bases must each leave room for a full width below 65536 — the first cut
  # of this used 10000-wide bases including 60000, and 60000+9999=69999
  # overflowed sing-box's uint16 listen_port, which failed loudly at
  # `sing-box check` (not silently), but only on the third protocol tested.
  local base="$1"
  echo $(( (RANDOM % 5000) + base ))
}

port_var(){ case "$1" in vmess) echo PROXY_VMESS_PORT ;; vless) echo PROXY_VLESS_PORT ;;
  trojan) echo PROXY_TROJAN_PORT ;; shadowsocks) echo PROXY_SS_PORT ;; esac; }
port_default_base(){ case "$1" in vmess) echo 40000 ;; vless) echo 45000 ;;
  trojan) echo 50000 ;; shadowsocks) echo 55000 ;; esac; }

# ---------------------------------------------------------------------------
# Config / service
# ---------------------------------------------------------------------------

cert_paths(){ echo "${INSTALL_DIR}/cert/fullchain.pem ${INSTALL_DIR}/cert/key.pem"; }

ensure_cert(){
  mkdir -p "${INSTALL_DIR}/cert"
  read -r crt key <<< "$(cert_paths)"
  if [[ ! -f "$crt" || ! -f "$key" ]]; then
    log "$(msg generating_cert "$PROXY_SNI")"
    openssl req -x509 -nodes -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 \
      -keyout "$key" -out "$crt" -days 3650 -subj "/CN=${PROXY_SNI}" >/dev/null 2>&1
  fi
}

# One inbound JSON object for a protocol. Credentials/ports are read from the
# PROXY_<PROTO>_* env vars, which by this point are guaranteed to be set —
# either carried over from an existing install (install.sh's preserve_proxy)
# or freshly generated in setup_config() below.
inbound_json(){
  local proto="$1" crt key
  read -r crt key <<< "$(cert_paths)"
  case "$proto" in
    vmess)
      cat <<JSON
{ "type": "vmess", "tag": "vmess-in", "listen": "::", "listen_port": ${PROXY_VMESS_PORT},
  "users": [ { "name": "vmess", "uuid": "${PROXY_VMESS_UUID}", "alterId": 0 } ],
  "tls": { "enabled": true, "certificate_path": "${crt}", "key_path": "${key}" } }
JSON
      ;;
    vless)
      cat <<JSON
{ "type": "vless", "tag": "vless-in", "listen": "::", "listen_port": ${PROXY_VLESS_PORT},
  "users": [ { "name": "vless", "uuid": "${PROXY_VLESS_UUID}" } ],
  "tls": { "enabled": true, "certificate_path": "${crt}", "key_path": "${key}" } }
JSON
      ;;
    trojan)
      cat <<JSON
{ "type": "trojan", "tag": "trojan-in", "listen": "::", "listen_port": ${PROXY_TROJAN_PORT},
  "users": [ { "name": "trojan", "password": "${PROXY_TROJAN_PASSWORD}" } ],
  "tls": { "enabled": true, "certificate_path": "${crt}", "key_path": "${key}" } }
JSON
      ;;
    shadowsocks)
      cat <<JSON
{ "type": "shadowsocks", "tag": "shadowsocks-in", "listen": "::", "listen_port": ${PROXY_SS_PORT},
  "method": "2022-blake3-aes-128-gcm", "password": "${PROXY_SS_PASSWORD}" }
JSON
      ;;
  esac
}

setup_config(){
  local proto inbounds=()
  compute_selected_protocols
  local protocols=("${SELECTED_PROTOCOLS[@]}")
  for proto in vmess vless trojan; do
    ensure_cert
    break
  done
  for proto in "${protocols[@]}"; do
    local pvar uvar
    pvar="$(port_var "$proto")"
    if [[ -z "${!pvar:-}" ]]; then
      printf -v "$pvar" '%s' "$(rand_port "$(port_default_base "$proto")")"
    fi
    case "$proto" in
      vmess)   uvar=PROXY_VMESS_UUID ;;
      vless)   uvar=PROXY_VLESS_UUID ;;
      trojan)  uvar=PROXY_TROJAN_PASSWORD ;;
      shadowsocks) uvar=PROXY_SS_PASSWORD ;;
    esac
    if [[ -z "${!uvar:-}" ]]; then
      if [[ "$proto" == vmess || "$proto" == vless ]]; then
        printf -v "$uvar" '%s' "$("$BIN_PATH" generate uuid)"
      else
        printf -v "$uvar" '%s' "$("$BIN_PATH" generate rand 16 --base64)"
      fi
    fi
    inbounds+=("$(inbound_json "$proto")")
  done

  mkdir -p "$INSTALL_DIR"
  {
    echo '{'
    echo '  "log": { "level": "info", "timestamp": true },'
    echo '  "inbounds": ['
    local i n=${#inbounds[@]}
    for ((i=0; i<n; i++)); do
      echo "    ${inbounds[$i]}$([[ $i -lt $((n-1)) ]] && echo ,)"
    done
    echo '  ],'
    echo '  "outbounds": [ { "type": "direct", "tag": "direct" }, { "type": "block", "tag": "block" } ],'
    echo '  "route": { "final": "direct" }'
    echo '}'
  } > "${INSTALL_DIR}/config.json"

  "$BIN_PATH" check -c "${INSTALL_DIR}/config.json"
  ok "$(msg config_written "${INSTALL_DIR}/config.json" "${protocols[*]}")"
}

setup_service(){
  cat > "/etc/systemd/system/${SERVICE_NAME}" <<EOF
[Unit]
Description=sing-box multi-protocol proxy (vmess/vless/trojan/shadowsocks)
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
    ok "$(msg service_started)"
  else
    err "$(msg service_failed "$SERVICE_NAME")"
    exit 1
  fi
}

# {type: port} for whatever is currently on disk, or empty if not installed.
current_ports_json(){
  [[ -f "${INSTALL_DIR}/config.json" ]] || { echo '{}'; return; }
  jq -c '[.inbounds[] | {(.type): .listen_port}] | add // {}' \
    "${INSTALL_DIR}/config.json" 2>/dev/null || echo '{}'
}

# Same ordering rationale as setup-anytls.sh's apply_node(): write the new
# state fully before touching the firewall, and read the old ports before
# overwriting config.json — after that they are gone.
apply_node(){
  local prev prev_ports=() new_ports=() proto
  prev="$(current_ports_json)"
  setup_config
  setup_service
  for proto in $ALL_PROTOCOLS; do
    local old
    old="$(jq -r --arg t "$proto" '.[$t] // empty' <<<"$prev")"
    [[ -n "$old" ]] && prev_ports+=("$old")
  done
  compute_selected_protocols
  local protocols=("${SELECTED_PROTOCOLS[@]}")
  for proto in "${protocols[@]}"; do
    local pvar; pvar="$(port_var "$proto")"
    new_ports+=("${!pvar}")
  done
  local p
  for p in "${prev_ports[@]}"; do
    if [[ ! " ${new_ports[*]} " == *" $p "* ]]; then
      close_firewall "$p"
    fi
  done
  for p in "${new_ports[@]}"; do
    open_firewall "$p"
  done
}

clash_line(){
  local proto="$1" name="$2" server="$3"
  case "$proto" in
    vmess)
      printf -- '- { name: %s, type: vmess, server: %s, port: %s, uuid: %s, alterId: 0, cipher: auto, tls: true, skip-cert-verify: true, servername: %s, udp: true }\n' \
        "$name" "$server" "$PROXY_VMESS_PORT" "$PROXY_VMESS_UUID" "$PROXY_SNI"
      ;;
    vless)
      printf -- '- { name: %s, type: vless, server: %s, port: %s, uuid: %s, network: tcp, tls: true, skip-cert-verify: true, servername: %s, udp: true }\n' \
        "$name" "$server" "$PROXY_VLESS_PORT" "$PROXY_VLESS_UUID" "$PROXY_SNI"
      ;;
    trojan)
      printf -- '- { name: %s, type: trojan, server: %s, port: %s, password: "%s", sni: %s, skip-cert-verify: true, udp: true }\n' \
        "$name" "$server" "$PROXY_TROJAN_PORT" "$PROXY_TROJAN_PASSWORD" "$PROXY_SNI"
      ;;
    shadowsocks)
      printf -- '- { name: %s, type: ss, server: %s, port: %s, cipher: 2022-blake3-aes-128-gcm, password: "%s", udp: true }\n' \
        "$name" "$server" "$PROXY_SS_PORT" "$PROXY_SS_PASSWORD"
      ;;
  esac
}

share_link(){
  local proto="$1" name="$2" server="$3"
  case "$proto" in
    vmess)
      jq -cn --arg ps "$name" --arg add "$server" --arg port "$PROXY_VMESS_PORT" \
        --arg id "$PROXY_VMESS_UUID" --arg sni "$PROXY_SNI" \
        '{v:"2",ps:$ps,add:$add,port:$port,id:$id,aid:"0",net:"tcp",type:"none",host:"",path:"",tls:"tls",sni:$sni,scy:"auto"}' \
        | tr -d '\n' | base64 -w0 | sed 's/^/vmess:\/\//'
      ;;
    vless)
      printf 'vless://%s@%s:%s?encryption=none&security=tls&sni=%s&allowInsecure=1&type=tcp#%s\n' \
        "$PROXY_VLESS_UUID" "$server" "$PROXY_VLESS_PORT" "$PROXY_SNI" "$(urlenc "$name")"
      ;;
    trojan)
      printf 'trojan://%s@%s:%s?sni=%s&allowInsecure=1#%s\n' \
        "$(urlenc "$PROXY_TROJAN_PASSWORD")" "$server" "$PROXY_TROJAN_PORT" "$PROXY_SNI" "$(urlenc "$name")"
      ;;
    shadowsocks)
      printf 'ss://%s@%s:%s#%s\n' \
        "$(printf '2022-blake3-aes-128-gcm:%s' "$PROXY_SS_PASSWORD" | base64 -w0)" \
        "$server" "$PROXY_SS_PORT" "$(urlenc "$name")"
      ;;
  esac
}

print_result(){
  local wan_ip ts_ip iface ip entries=() entry label proto
  compute_selected_protocols
  local protocols=("${SELECTED_PROTOCOLS[@]}")

  wan_ip="$(get_ip)"
  entries+=("$(msg public_network)|${wan_ip}")
  if [[ "$wan_ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    printf '%s\n' "$wan_ip" > "${INSTALL_DIR}/public-ip.txt"
    chmod 0644 "${INSTALL_DIR}/public-ip.txt"
  fi
  while read -r iface ip; do
    entries+=("$(msg private_network)-${iface}|${ip}")
  done < <(get_lan_ips)
  ts_ip="$(get_tailscale_ip)"
  [[ -n "$ts_ip" ]] && entries+=("Tailscale|${ts_ip}")

  echo
  echo "========================================"
  echo "$(msg result_heading "$SERVICE_NAME")"
  echo "$(msg enabled_protocols "${protocols[*]}")"
  echo "========================================"
  for proto in "${protocols[@]}"; do
    local pvar; pvar="$(port_var "$proto")"
    echo "----------------------------------------"
    echo "$(msg protocol_port "$proto" "${!pvar}")"
    for entry in "${entries[@]}"; do
      label="${entry%%|*}"; ip="${entry#*|}"
      echo "   [${label}] ${ip}"
      echo "     Clash: $(clash_line "$proto" "${proto}-${label}" "$ip")"
      echo "$(msg share_link_label)$(share_link "$proto" "${proto}-${label}" "$ip")"
    done
  done
  echo "========================================"
  echo "$(msg config_file "${INSTALL_DIR}/config.json")"
  echo "$(msg service_management "$SERVICE_NAME")"
  echo "$(msg view_node "$0")"
  echo "$(msg reset_node "$0")"
  echo "$(msg uninstall_hint "$0")"
  echo
}

load_installed_vars(){
  [[ -f "${INSTALL_DIR}/config.json" ]] || return 1
  local proto
  for proto in $ALL_PROTOCOLS; do
    case "$proto" in
      vmess)
        PROXY_VMESS_PORT="$(jq -r '.inbounds[]|select(.type=="vmess")|.listen_port//empty' "${INSTALL_DIR}/config.json")"
        PROXY_VMESS_UUID="$(jq -r '.inbounds[]|select(.type=="vmess")|.users[0].uuid//empty' "${INSTALL_DIR}/config.json")"
        ;;
      vless)
        PROXY_VLESS_PORT="$(jq -r '.inbounds[]|select(.type=="vless")|.listen_port//empty' "${INSTALL_DIR}/config.json")"
        PROXY_VLESS_UUID="$(jq -r '.inbounds[]|select(.type=="vless")|.users[0].uuid//empty' "${INSTALL_DIR}/config.json")"
        ;;
      trojan)
        PROXY_TROJAN_PORT="$(jq -r '.inbounds[]|select(.type=="trojan")|.listen_port//empty' "${INSTALL_DIR}/config.json")"
        PROXY_TROJAN_PASSWORD="$(jq -r '.inbounds[]|select(.type=="trojan")|.users[0].password//empty' "${INSTALL_DIR}/config.json")"
        ;;
      shadowsocks)
        PROXY_SS_PORT="$(jq -r '.inbounds[]|select(.type=="shadowsocks")|.listen_port//empty' "${INSTALL_DIR}/config.json")"
        PROXY_SS_PASSWORD="$(jq -r '.inbounds[]|select(.type=="shadowsocks")|.password//empty' "${INSTALL_DIR}/config.json")"
        ;;
    esac
  done
  PROXY_PROTOCOLS="$(jq -r '[.inbounds[].type] | join(",")' "${INSTALL_DIR}/config.json")"
  return 0
}

show_installed_node(){
  if ! load_installed_vars; then
    err "$(msg config_not_found "${INSTALL_DIR}/config.json")"
    err "$(msg run_first "$0")"
    exit 1
  fi
  print_result
  if systemctl is-active --quiet "${SERVICE_NAME}"; then
    ok "$(msg service_active)"
  else
    err "$(msg service_inactive "$SERVICE_NAME")"
  fi
}

uninstall(){
  local ports=()
  if [[ -f "${INSTALL_DIR}/config.json" ]]; then
    while read -r p; do [[ -n "$p" ]] && ports+=("$p"); done \
      < <(jq -r '.inbounds[].listen_port' "${INSTALL_DIR}/config.json" 2>/dev/null || true)
  fi

  log "$(msg stopping_service)"
  systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
  systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
  rm -f "/etc/systemd/system/${SERVICE_NAME}"
  systemctl daemon-reload
  systemctl reset-failed 2>/dev/null || true
  ok "$(msg service_removed)"

  log "$(msg deleting_config)"
  rm -rf "$INSTALL_DIR"

  # Only remove the shared binary if the anytls module isn't relying on it
  # too. See the file header for why this check exists.
  if [[ ! -f "$ANYTLS_CONFIG" ]]; then
    rm -f "$BIN_PATH"
    ok "$(msg binary_deleted "$BIN_PATH")"
  else
    log "$(msg binary_kept "$BIN_PATH")"
  fi

  local p
  for p in "${ports[@]}"; do close_firewall "$p"; done
  ok "$(msg uninstall_complete)"
}

# Rotate whatever is currently installed. PROXY_PROTOCOLS may be overridden
# by the caller to add/drop a protocol at the same time; otherwise it is left
# as whatever is already on disk.
# $1, if given, is a single protocol name: only ITS port and credential are
# rotated, everything else (other protocols' ports/credentials, and the
# installed protocol set itself) is loaded from disk and left untouched.
# With no argument, every currently-installed protocol is rotated — the
# original behaviour, kept for `bash setup-proxy.sh reset` from a terminal.
#
# The console's per-protocol reset buttons (added after an operator pointed
# out that one "reset everything" button forces rotating protocols nobody
# asked to rotate) always pass $1, so a credential leak on one protocol does
# not force re-configuring every client using the others.
reset(){
  local target="${1:-}"
  # Keep this descriptor open through config writes and service restart.
  exec {node_lock}>/etc/vps-server-node.lock
  flock -x "$node_lock"
  install_deps
  if ! mkdir -p "${INSTALL_DIR}" 2>/dev/null || ! touch "${INSTALL_DIR}/.writable" 2>/dev/null; then
    err "$(msg install_dir_readonly "$INSTALL_DIR")"
    err "$(msg sandbox_hint)"
    exit 1
  fi
  rm -f "${INSTALL_DIR}/.writable"
  if ! touch /etc/systemd/system/.vps-server-writable 2>/dev/null; then
    err "$(msg systemd_dir_readonly)"
    exit 1
  fi
  rm -f /etc/systemd/system/.vps-server-writable

  if [[ -n "$target" ]]; then
    case " $ALL_PROTOCOLS " in
      *" $target "*) ;;
      *) err "$(msg unknown_protocol "$target" "${ALL_PROTOCOLS// /, }")"; exit 1 ;;
    esac
    if ! load_installed_vars; then
      err "$(msg config_not_found "${INSTALL_DIR}/config.json")"
      exit 1
    fi
    case "$target" in
      vmess)   unset PROXY_VMESS_PORT PROXY_VMESS_UUID ;;
      vless)   unset PROXY_VLESS_PORT PROXY_VLESS_UUID ;;
      trojan)  unset PROXY_TROJAN_PORT PROXY_TROJAN_PASSWORD ;;
      shadowsocks) unset PROXY_SS_PORT PROXY_SS_PASSWORD ;;
    esac
  else
    local had_config=0
    [[ -f "${INSTALL_DIR}/config.json" ]] && had_config=1
    if [[ "$had_config" == "1" && -z "${PROXY_PROTOCOLS_OVERRIDDEN:-}" ]]; then
      PROXY_PROTOCOLS="$(jq -r '[.inbounds[].type] | join(",")' "${INSTALL_DIR}/config.json")"
    fi
    # Force fresh credentials/ports for every selected protocol: unset any
    # value load_installed_vars might have set, since a caller-visible
    # "reset" that silently kept the old password would not be a reset.
    unset PROXY_VMESS_PORT PROXY_VMESS_UUID PROXY_VLESS_PORT PROXY_VLESS_UUID \
          PROXY_TROJAN_PORT PROXY_TROJAN_PASSWORD PROXY_SS_PORT PROXY_SS_PASSWORD
  fi

  install_singbox
  apply_node
  print_result
}

main(){
  case "${1:-}" in
    uninstall|--uninstall|-u) uninstall; exit 0 ;;
    reset|--reset) reset "${2:-}"; exit 0 ;;
    status|show|info|--status|-s) install_deps; show_installed_node; exit 0 ;;
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
  install_deps
  install_singbox
  apply_node
  enable_bbr
  print_result
}
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
