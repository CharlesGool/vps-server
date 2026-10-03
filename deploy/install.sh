#!/usr/bin/env bash
#
# Install vps-server. A fresh install starts with the management console only.
#
#   web      the public reachability page on 80/443 plus the private console
#   iperf3   the distro iperf3 package, so the console can open a test window
#   anytls   the sing-box anytls proxy (amd64 only)
#   proxy    sing-box vmess/vless/trojan/shadowsocks, any subset (amd64 only)
#   frps     offline FRP server (amd64 only)
#   lucky    offline DDNS and reverse-proxy admin (amd64 only)
#
#   sudo bash deploy/install.sh                             # console only
#   sudo VPSSRV_MODULES=web,iperf3 bash deploy/install.sh   # unattended, no prompts
#   sudo VPSSRV_MODULES=web VPSSRV_PUBLIC_ENABLE=0 bash deploy/install.sh   # console only
#   sudo PREFIX=/srv/vpssrv bash deploy/install.sh
#
# Installation uses safe defaults without a browser or terminal questions.
# VPSSRV_MODULES and other environment values may override those defaults.
#
# Re-running is safe: it refreshes the program files and restarts the service,
# leaving admin_password.txt, console_port.txt, certs/ and data/ alone.

set -euo pipefail

ROOT_HOME="$(getent passwd 0 | cut -d: -f6)"
ROOT_HOME="${ROOT_HOME:-/root}"
PREFIX="${PREFIX:-$ROOT_HOME/apps/vps-server}"
SERVICE_NAME="${SERVICE_NAME:-vps-server-web}"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Modules, comma-separated. An explicit VPSSRV_MODULES value still supports
# targeted module jobs and installations with fewer services.
DEFAULT_MODULES="web"

PUBLIC_HTTP_PORT="${VPSSRV_PUBLIC_HTTP_PORT:-80}"
PUBLIC_HTTPS_PORT="${VPSSRV_PUBLIC_HTTPS_PORT:-443}"

INTERACTIVE=0

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
            VPSSRV_PORTFWD_ENABLE VPSSRV_PORTFWD_MAX_RULES
            VPSSRV_DATA_DIR VPSSRV_PASSWORD_FILE VPSSRV_IP_ALLOWLIST_FILE VPSSRV_AUTH VPSSRV_DEFAULT_LANG
            VPSSRV_LOGIN_MAX_ATTEMPTS VPSSRV_LOGIN_WINDOW_SECONDS VPSSRV_LOGIN_LOCKOUT_SECONDS
            VPSSRV_CERT_DIR VPSSRV_TLS_CERT VPSSRV_TLS_KEY VPSSRV_TRUST_PROXY
            VPSSRV_MAX_TEST_MB VPSSRV_TRACK_CONNECTIONS VPSSRV_CONN_POLL_SECONDS
            VPSSRV_TEST_SECONDS VPSSRV_WARMUP_SECONDS VPSSRV_DOWNLOAD_STREAMS
            VPSSRV_UPLOAD_STREAMS VPSSRV_PING_SAMPLES
            VPSSRV_ANYTLS_CONFIG VPSSRV_ANYTLS_SERVICE VPSSRV_ANYTLS_SETUP
            VPSSRV_PROXY_CONFIG VPSSRV_PROXY_SERVICE VPSSRV_PROXY_SETUP"

# What this install left behind, so the next one can tell what changed.
# Deliberately not the unit file: the unit records only settings that were
# given a value, which says nothing about which settings the version knew of.
STATE_FILE="$PREFIX/.install-state"
ANYTLS_UNIT="/etc/systemd/system/vps-server-anytls.service"
ANYTLS_CONFIG_PATH="/etc/vps-server-anytls/config.json"
PROXY_UNIT="/etc/systemd/system/vps-server-proxy.service"
PROXY_CONFIG_PATH="/etc/vps-server-proxy/config.json"
FRPS_UNIT="/etc/systemd/system/vps-server-frps.service"
LUCKY_UNIT="/etc/systemd/system/vps-server-lucky.service"

declare -A PREV=()
PREV_VERSION=""
PREV_MODULES=""
PREV_VARS=""
PREV_STATE_KNOWN=0
UPGRADE=0

# The version being installed. Derived, never hand-written: webui.md §1
# requires the UI to show the real tag, and an untagged build to say so rather
# than impersonate the last release. A constant in the source is wrong the
# moment somebody tags and forgets to edit it, and nothing reports that.
resolve_version() {
  local v
  if git -C "$SRC_DIR" rev-parse --git-dir >/dev/null 2>&1; then
    v="$(git -C "$SRC_DIR" describe --tags --exact-match 2>/dev/null || true)"
    if [ -n "$v" ]; then
      printf '%s' "${v#v}"   # tags carry a leading v, the displayed version does not
    else
      printf 'dev-%s' "$(git -C "$SRC_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
    fi
    return
  fi
  # No git — a tarball, or an export like `git archive`. Fall back to the file
  # committed at release time, which is exactly what that tag contained.
  if [ -f "$SRC_DIR/config/VERSION" ]; then
    tr -d ' \r\n' < "$SRC_DIR/config/VERSION"
    return
  fi
  printf 'dev-unknown'
}
NEW_VERSION="$(resolve_version)"
NEW_VERSION="${NEW_VERSION:-dev-unknown}"

unit_env() {
  # One recorded Environment= value from the installed unit, or empty.
  [ -f "$UNIT_PATH" ] || return 0
  sed -n "s/^Environment=$1=//p" "$UNIT_PATH" | tail -n1
}

existing_install() {
  [ -f "$UNIT_PATH" ] || [ -f "$ANYTLS_UNIT" ] || [ -f "$PROXY_UNIT" ] || [ -f "$FRPS_UNIT" ] || [ -f "$PREFIX/app.py" ]
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
    [ -f "$PROXY_UNIT" ] && PREV_MODULES="${PREV_MODULES:+$PREV_MODULES,}proxy"
    [ -f "$FRPS_UNIT" ] && PREV_MODULES="${PREV_MODULES:+$PREV_MODULES,}frps"
    [ -f "$LUCKY_UNIT" ] && PREV_MODULES="${PREV_MODULES:+$PREV_MODULES,}lucky"
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

# Same reasoning as preserve_anytls(), for every protocol the proxy module
# currently has installed. setup-proxy.sh regenerates a fresh port and
# credential for any PROXY_<PROTO>_PORT/_UUID/_PASSWORD that arrives unset —
# an upgrade that skipped this would rotate every client's config for no
# reason anyone asked for. One python3 call reads back whichever of the four
# protocols are actually present and prints them as KEY=VALUE lines,
# including PROXY_PROTOCOLS itself so the installed protocol *set* survives
# too, not just each one's credentials.
preserve_proxy() {
  [ -f "$PROXY_CONFIG_PATH" ] || return 0
  [ -z "${PROXY_PROTOCOLS:-}" ] || return 0
  local out kv key val
  out="$(python3 -c 'import json,sys
try:
    c = json.load(open(sys.argv[1]))
except Exception:
    raise SystemExit
types = []
for i in c.get("inbounds", []):
    t = i.get("type", "")
    if t == "vmess":
        types.append("vmess")
        print("PROXY_VMESS_PORT=%s" % i.get("listen_port", ""))
        print("PROXY_VMESS_UUID=%s" % (i.get("users") or [{}])[0].get("uuid", ""))
    elif t == "vless":
        types.append("vless")
        print("PROXY_VLESS_PORT=%s" % i.get("listen_port", ""))
        print("PROXY_VLESS_UUID=%s" % (i.get("users") or [{}])[0].get("uuid", ""))
    elif t == "trojan":
        types.append("trojan")
        print("PROXY_TROJAN_PORT=%s" % i.get("listen_port", ""))
        print("PROXY_TROJAN_PASSWORD=%s" % (i.get("users") or [{}])[0].get("password", ""))
    elif t == "shadowsocks":
        types.append("shadowsocks")
        print("PROXY_SS_PORT=%s" % i.get("listen_port", ""))
        print("PROXY_SS_PASSWORD=%s" % i.get("password", ""))
print("PROXY_PROTOCOLS=%s" % ",".join(types))' "$PROXY_CONFIG_PATH" 2>/dev/null || true)"
  [ -n "$out" ] || return 0
  while IFS= read -r kv; do
    [ -n "$kv" ] || continue
    key="${kv%%=*}"; val="${kv#*=}"
    export "$key=$val"
  done <<< "$out"
  if [ -n "${PROXY_PROTOCOLS:-}" ]; then
    msg upgrade_proxy_kept "$PROXY_PROTOCOLS"
  fi
  return 0
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
    if [ -n "$value" ]; then
      export "$var=$value"
    fi
  done
  # A bare `[ -n "$value" ] && export ...` as the loop's last statement would
  # make THIS FUNCTION's own exit status track that test — false whenever the
  # last new setting is left at its default. Called bare (`prompt_new_settings`
  # inside an if-body, not itself exempt from `set -e`), a false there killed
  # the whole installer right after the last prompt: no error, no copy step,
  # no VERSION stamp, no service restart. See doc/LOG.md#decisions (2026-09-21).
  return 0
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
# Installer messages live in lang/installer/. Every string is a printf format,
# so placeholders line up across all three languages; templates that end
# without \n are prompts.
# ---------------------------------------------------------------------------

INSTALL_LANG="${VPSSRV_DEFAULT_LANG:-en}"
case "$INSTALL_LANG" in en|zh_cn|zh_tw|zh_hk|hi|es|ar|fr) ;; *) INSTALL_LANG=en ;; esac

msg() {
  local key="$1"; shift
  local fmt
  # Catalog filenames are fixed here; no user-supplied path is sourced.
  case "$INSTALL_LANG" in
    zh_cn) source "$SRC_DIR/lang/installer/zh-CN.sh" ;;
    zh_tw) source "$SRC_DIR/lang/installer/zh-TW.sh" ;;
    zh_hk) source "$SRC_DIR/lang/installer/zh-HK.sh" ;;
    hi) source "$SRC_DIR/lang/installer/hi.sh" ;;
    es) source "$SRC_DIR/lang/installer/es.sh" ;;
    ar) source "$SRC_DIR/lang/installer/ar.sh" ;;
    fr) source "$SRC_DIR/lang/installer/fr.sh" ;;
    *) source "$SRC_DIR/lang/installer/en.sh" ;;
  esac
  # shellcheck disable=SC2059  # fmt comes from the trusted catalog.
  printf "$fmt" "$@"
}

# Callers pass already-translated text, e.g. die "$(msg need_root)". Command
# substitution strips msg's trailing newline, so put it back here.
die() { printf '%s%s\n' "$(msg error_prefix)" "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "$(msg need_root)"
command -v systemctl >/dev/null 2>&1 || die "$(msg no_systemd)"
command -v python3 >/dev/null 2>&1 || die "$(msg no_python)"

# Reuse the installed language unless this run explicitly selects another.
if [ -z "${VPSSRV_DEFAULT_LANG:-}" ]; then
  PREV_LANG="$(unit_env VPSSRV_DEFAULT_LANG)"
  case "$PREV_LANG" in
    en|zh_cn|zh_tw|zh_hk|hi|es|ar|fr) INSTALL_LANG="$PREV_LANG" ;;
  esac
fi
# Pass the selected locale to every module setup script.
export VPSSRV_DEFAULT_LANG="$INSTALL_LANG"
MODULES="${VPSSRV_MODULES:-$DEFAULT_MODULES}"

# ---------------------------------------------------------------------------
# 1a. An existing install, if there is one.
# ---------------------------------------------------------------------------
# Keep the credential snapshot and both child applies in one transaction.
# Children inherit this locked descriptor rather than opening a second one
# (which would deadlock against the parent's flock).
# Existing node configs may be read even when only web was requested.
# An existing web-only install without node configs needs no node lock.
case ",$MODULES," in
  *,anytls,*|*,proxy,*) need_node_lock=1 ;;
  *)
    if existing_install && { [ -f "$ANYTLS_CONFIG_PATH" ] || [ -f "$PROXY_CONFIG_PATH" ]; }; then
      need_node_lock=1
    else
      need_node_lock=0
    fi ;;
esac
if [ "$need_node_lock" = 1 ]; then
  exec {node_lock}>/etc/vps-server-node.lock
  flock -x "$node_lock"
fi
if existing_install; then
  load_previous
  # A routine upgrade keeps the modules already chosen on this host. Fresh
  # installs use the console-only default unless the caller selects modules.
  if [ -z "${VPSSRV_MODULES:-}" ]; then MODULES="$PREV_MODULES"; fi
  msg found_install "${PREV_VERSION:-?}" "$PREV_MODULES"
  UPGRADE=1
  apply_previous
  preserve_anytls
  preserve_proxy
fi

if [ "$UPGRADE" = "0" ]; then
  # The public reachability page is optional; only the random-port console
  # answers on a fresh install until the operator enables other features.
  export VPSSRV_PUBLIC_ENABLE="${VPSSRV_PUBLIC_ENABLE:-0}"
fi

# Re-derived here, because apply_previous may have just supplied the values
# these are computed from. Left at their top-of-script values they keep the
# defaults, which is how an upgrade printed ":80" for a page that was really
# listening on 8080 — and, worse, how the port-conflict check below came to
# test port 80 while the install was about to bind 8080.
PUBLIC_HTTP_PORT="${VPSSRV_PUBLIC_HTTP_PORT:-80}"
PUBLIC_HTTPS_PORT="${VPSSRV_PUBLIC_HTTPS_PORT:-443}"

# Check final configuration after upgrade preservation.
if { [ "${VPSSRV_CONSOLE_TLS:-0}" = "1" ] || [ "${VPSSRV_PUBLIC_ENABLE:-1}" = "1" ]; } \
   && ! command -v openssl >/dev/null 2>&1; then
  die "$(msg no_openssl)"
fi

# ---------------------------------------------------------------------------
# 1b. Modules.
# ---------------------------------------------------------------------------
msg modules_are "$MODULES"

# iperf3 is a console button; without the web module there is no console to
# click it from, so this combination has always silently installed nothing
# useful rather than doing what was asked.
if has_module iperf3 && ! has_module web; then
  die "$(msg iperf_web_required)"
fi

if [ "$UPGRADE" = "1" ]; then
  prompt_new_settings
fi

# The vendored sing-box binary is amd64. Skipping the module beats installing
# a binary that cannot execute and failing later with "Exec format error".
# Both anytls and proxy share that one binary, so both need the same guard.
if has_module anytls || has_module proxy || has_module frps || has_module lucky; then
  ARCH="$(uname -m)"
  case "$ARCH" in
    x86_64|amd64) ;;
    *)
      has_module anytls && { msg anytls_arch "$ARCH"; MODULES="${MODULES//anytls/}"; }
      has_module proxy && { msg proxy_arch "$ARCH"; MODULES="${MODULES//proxy/}"; }
      has_module frps && die "$(msg frps_arch)"
      has_module lucky && die "$(msg lucky_arch)"
      ;;
  esac
fi

install_iperf3() {
  command -v iperf3 >/dev/null 2>&1 && return 0
  msg iperf_installing
  export DEBIAN_FRONTEND=noninteractive

  # Two distinct apt failure modes land here, both transient: apt-get update
  # itself can fail outright (one unreachable repo is enough, even a stale
  # third-party .list unrelated to iperf3), or it can report success while
  # security.debian.org's CDN hands back a stale index whose .deb URLs 404 on
  # install (apt's own "maybe run apt-get update" hints at exactly this). A
  # single retry of update alone fixes neither case reliably; retrying the
  # whole update-then-install pair does, since a later attempt both tolerates
  # an update failure (`|| true` keeps set -e from killing the installer) and
  # has a decent chance of landing on a synced mirror.
  local attempt
  for attempt in 1 2 3; do
    apt-get update -qq || true
    apt-get install -y -qq iperf3 && return 0
    [ "$attempt" -eq 3 ] || sleep 2
  done

  msg iperf_failed
  return 1
}

install_anytls() {
  msg anytls_start
  # Once node identity and limits exist, the UI owns edits. Re-running the
  # legacy setup script would replace per-node TLS paths and desync state.
  if [ -f /etc/vps-server-nodes/state.json ] && [ -f "$ANYTLS_CONFIG_PATH" ] &&
     [ -f /etc/systemd/system/vps-server-anytls.service ]; then
    return 0
  fi
  # Its own script owns everything anytls: deps, binary, config, unit,
  # firewall, BBR, and the client-config summary it prints at the end.
  ANYTLS_PORT="${ANYTLS_PORT:-}" ANYTLS_PASSWORD="${ANYTLS_PASSWORD:-}" \
  SNI="${SNI:-www.bing.com}" \
  VPSSRV_NODE_LOCK_FD="${node_lock:-}" VPSSRV_DEFER_NODE_START=1 VPSSRV_EMPTY_NODE_INSTALL=1 bash "$PREFIX/anytls/setup-anytls.sh"
}

install_proxy() {
  msg proxy_start "${PROXY_PROTOCOLS:-vmess,vless,trojan,shadowsocks}"
  if [ -f /etc/vps-server-nodes/state.json ] && [ -f "$PROXY_CONFIG_PATH" ] &&
     [ -f /etc/systemd/system/vps-server-proxy.service ]; then
    return 0
  fi
  # Same shape as install_anytls(): its own script owns deps, the shared
  # binary, config, unit, firewall and the client-config summary. Every
  # PROXY_<PROTO>_* credential/port var is passed through unset by default —
  # preserve_proxy() above has already exported them on an upgrade, and
  # setup-proxy.sh generates fresh ones itself when they arrive empty.
  PROXY_PROTOCOLS="${PROXY_PROTOCOLS:-}" PROXY_SNI="${PROXY_SNI:-www.bing.com}" \
  PROXY_VMESS_PORT="${PROXY_VMESS_PORT:-}" PROXY_VMESS_UUID="${PROXY_VMESS_UUID:-}" \
  PROXY_VLESS_PORT="${PROXY_VLESS_PORT:-}" PROXY_VLESS_UUID="${PROXY_VLESS_UUID:-}" \
  PROXY_TROJAN_PORT="${PROXY_TROJAN_PORT:-}" PROXY_TROJAN_PASSWORD="${PROXY_TROJAN_PASSWORD:-}" \
  PROXY_SS_PORT="${PROXY_SS_PORT:-}" PROXY_SS_PASSWORD="${PROXY_SS_PASSWORD:-}" \
  VPSSRV_NODE_LOCK_FD="${node_lock:-}" VPSSRV_DEFER_NODE_START=1 VPSSRV_EMPTY_NODE_INSTALL=1 bash "$PREFIX/proxy/setup-proxy.sh"
}

install_node_meter() {
  if ! has_module anytls && ! has_module proxy; then
    systemctl disable --now vps-server-node-meter.service >/dev/null 2>&1 || true
    return 0
  fi
  # The installer held the node lock while preserving and applying legacy
  # configs. Release it before init or starting the notify-type meter unit.
  if [ -n "${node_lock:-}" ]; then
    exec {node_lock}>&-
    unset node_lock
  fi
  if ! command -v nft >/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y -qq nftables || return 1
  fi
  /usr/bin/python3 "$PREFIX/node_control.py" init || return 1
  local was_anytls=0 was_proxy=0
  systemctl is-enabled --quiet vps-server-anytls.service && was_anytls=1 || true
  systemctl is-enabled --quiet vps-server-proxy.service && was_proxy=1 || true
  mkdir -p /etc/systemd/system/vps-server-anytls.service.d \
           /etc/systemd/system/vps-server-proxy.service.d
  for unit in vps-server-anytls vps-server-proxy; do
    cat > "/etc/systemd/system/${unit}.service.d/node-meter.conf" <<EOF
[Unit]
Requires=vps-server-node-meter.service
After=vps-server-node-meter.service
EOF
  done
  cat > /etc/systemd/system/vps-server-node-meter.service <<EOF
[Unit]
Description=vps-server node traffic accounting and limits
After=network-online.target
Wants=network-online.target
Before=vps-server-anytls.service vps-server-proxy.service

[Service]
Type=notify
NotifyAccess=main
ExecStart=/usr/bin/python3 $PREFIX/node_meter.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/etc/vps-server-nodes /etc/vps-server-node.lock

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl stop vps-server-anytls.service vps-server-proxy.service >/dev/null 2>&1 || true
  systemctl enable vps-server-node-meter.service || return 1
  systemctl restart vps-server-node-meter.service || return 1
  [ "$was_anytls" = 0 ] || systemctl start vps-server-anytls.service || return 1
  [ "$was_proxy" = 0 ] || systemctl start vps-server-proxy.service || return 1
}

# A later web install must not displace an already-running frps listener.
# Resolve the effective console port (explicit override, then persisted file)
# after the port prompt, but before any web service stop, copy, or unit change.
check_frps_console_collision() {
if has_module web && [ -f /etc/vps-server-frps/frps.toml ]; then
  console_candidate="${VPSSRV_CONSOLE_PORT:-}"
  if [ -f "$PREFIX/data/console-port-override" ]; then
    console_candidate="$(tr -d '[:space:]' < "$PREFIX/data/console-port-override")"
  fi
  console_file="${VPSSRV_CONSOLE_PORT_FILE:-$PREFIX/console_port.txt}"
  if [ -z "$console_candidate" ] && [ -f "$console_file" ]; then
    console_candidate="$(tr -d '[:space:]' < "$console_file")"
  fi
  if [ -n "$console_candidate" ]; then
    frps_bind="$(python3 - <<'PYFRPS'
import pathlib, sys
try:
    import tomllib
except ImportError:
    tomllib = None
try:
    text = pathlib.Path('/etc/vps-server-frps/frps.toml').read_text()
    if tomllib is None:
        import json, re
        fields = {}
        string = r'"(?:[^"\\\x00-\x1f]|\\(?:["\\btnfr]|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}))*"'
        for line in text.splitlines():
            match = re.fullmatch(r'\s*(bindAddr|bindPort|auth\.method|auth\.token)\s*=\s*(' + string + r'|[0-9]+)\s*', line)
            if not match or match[1] in fields:
                raise ValueError('unsupported or malformed frps configuration')
            fields[match[1]] = json.loads(match[2]) if match[2].startswith('"') else int(match[2])
        data = fields
    else:
        data = tomllib.loads(text)
    port = data['bindPort']
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('invalid bindPort')
    print(port)
except (ValueError, KeyError, OSError) as exc:
    print(f'Cannot verify frps bindPort: {exc}', file=sys.stderr)
    sys.exit(2)
PYFRPS
)" || die "$(msg frps_port_verify)"
    if python3 -c 'import sys; p = sys.argv[1]; sys.exit(0 if p.isascii() and p.isdecimal() and int(p) == int(sys.argv[2]) else 1)' "$console_candidate" "$frps_bind"; then
      die "$(msg frps_console_conflict "$console_candidate")"
    fi
  fi
fi
}

# Refuse to fight for 80/443 rather than letting systemd restart-loop on a
# port that will never be free. Our own listener is excluded by stopping the
# service first — on a re-run it is the process holding the port.
port_held() {
  ss -lnt "( sport = :$1 )" 2>/dev/null | tail -n +2 | grep -q .
}

first_busy_public_port() {
  local p
  for p in "$PUBLIC_HTTP_PORT" "$PUBLIC_HTTPS_PORT"; do
    if port_held "$p"; then printf '%s' "$p"; return 0; fi
  done
  return 1
}

# The checkout keeps the binary under third_party/, but installed modules still
# expect the shared binary directly under PREFIX. Never copy stateful data.
copy_singbox_binary() {
  [ -f "$SRC_DIR/third_party/sing-box/sing-box" ] || return 0
  cp "$SRC_DIR/third_party/sing-box/sing-box" "$PREFIX/sing-box"
  if [ "$SRC_DIR" != "$(cd "$PREFIX" && pwd)" ]; then
    mkdir -p "$PREFIX/vendor/sing-box"
    cp "$SRC_DIR/third_party/sing-box/LICENSE" "$SRC_DIR/third_party/sing-box/sing-box.version" \
      "$PREFIX/vendor/sing-box/"
  fi
}

# Copy only program files; state (data, credentials, certs, install state)
# stays in PREFIX. This function is also used by the module-only path.
copy_selected_files() {
  mkdir -p "$PREFIX"
  local prefix_abs
  prefix_abs="$(cd "$PREFIX" && pwd)"
  if [ "$SRC_DIR" = "$prefix_abs" ]; then
    if has_module web; then msg inplace_skip; fi
    # Module setup and uninstall paths use PREFIX/<module> even when the
    # checkout itself is PREFIX. Keep deploy/<module> as tracked source.
    local module
    for module in anytls proxy frps lucky; do
      has_module "$module" || continue
      [ -d "$SRC_DIR/deploy/$module" ] || continue
      mkdir -p "$PREFIX/$module"
      cp -a "$SRC_DIR/deploy/$module/." "$PREFIX/$module/"
    done
  else
    local copy_items item source
    copy_items="lang"
    if has_module web; then
      copy_items="$copy_items static systemd README.md LICENSE"
    fi
    has_module anytls && copy_items="$copy_items anytls"
    has_module proxy && copy_items="$copy_items proxy"
    has_module frps && copy_items="$copy_items frps"
    has_module lucky && copy_items="$copy_items lucky"
    for item in $copy_items; do
      source="$SRC_DIR/$item"
      case "$item" in static) source="$SRC_DIR/src/web/static" ;; systemd|anytls|proxy|frps|lucky) source="$SRC_DIR/deploy/$item" ;; esac
      [ -e "$source" ] || continue
      rm -rf "${PREFIX:?}/$item"
      cp -r "$source" "$PREFIX/$item"
    done
  fi
  if has_module web; then
    # The flat entry point is needed even when PREFIX is the source checkout.
    # Refreshing it on an in-place upgrade changes only an ignored runtime
    # copy, not the tracked implementation under src/web/.
    cp "$SRC_DIR/src/web/app.py" "$PREFIX/app.py"
    cp "$SRC_DIR/src/web/node_config.py" "$PREFIX/node_config.py"
    cp "$SRC_DIR/src/web/module_manager.py" "$PREFIX/module_manager.py"
    cp "$SRC_DIR/src/web/console_port.py" "$PREFIX/console_port.py"
    cp "$SRC_DIR/src/web/frp_control.py" "$PREFIX/frp_control.py"
    # Feature handlers form one versioned unit with the flat Web entry point.
    rm -rf "${PREFIX:?}/features"
    cp -r "$SRC_DIR/src/web/features" "$PREFIX/features"
  fi
  if has_module web && [ "$SRC_DIR" != "$prefix_abs" ]; then
    # Documentation required by /changelog and third-party notices.
    local doc_items="doc/LOG.md doc/CHANGELOG.md doc/THIRD_PARTY_NOTICES.md
                     doc/en/LOG.md doc/en/CHANGELOG.md
                     doc/zh-TW/CHANGELOG.md doc/zh-HK/CHANGELOG.md
                     doc/hi/CHANGELOG.md doc/es/CHANGELOG.md
                     doc/ar/CHANGELOG.md doc/fr/CHANGELOG.md"
    for item in $doc_items; do
      [ -e "$SRC_DIR/$item" ] || continue
      mkdir -p "$PREFIX/$(dirname "$item")"
      rm -f "${PREFIX:?}/$item"
      cp "$SRC_DIR/$item" "$PREFIX/$item"
    done
    [ -f "$SRC_DIR/.env.example" ] && cp "$SRC_DIR/.env.example" "$PREFIX/"
  fi
  # Even in-place installs need the deployed root entry point, not merely
  # the checkout's vendor path. Source and destination are distinct here.
  if has_module anytls || has_module proxy || [ -f "$ANYTLS_CONFIG_PATH" ] || [ -f "$PROXY_CONFIG_PATH" ]; then
    copy_singbox_binary
  fi
  if has_module web || has_module anytls || has_module proxy || \
     [ -f "$ANYTLS_CONFIG_PATH" ] || [ -f "$PROXY_CONFIG_PATH" ]; then
    # The Web UI imports the inventory even without nodes, and the controller
    # also runs for proxy-only installs without the Web UI.
    for item in node_inventory node_operations node_accounting node_state node_control node_meter; do
      if [ -f "$SRC_DIR/src/web/$item.py" ]; then
        cp "$SRC_DIR/src/web/$item.py" "$PREFIX/$item.py"
      fi
    done
  fi
  if has_module lucky; then
    mkdir -p "$PREFIX/vendor/lucky"
    cp "$SRC_DIR/third_party/lucky/lucky" "$SRC_DIR/third_party/lucky/LICENSE" "$SRC_DIR/third_party/lucky/component.txt" "$PREFIX/vendor/lucky/"
  fi
  if has_module frps; then
    mkdir -p "$PREFIX/vendor/frp"
    cp "$SRC_DIR/third_party/frp/frps" "$SRC_DIR/third_party/frp/LICENSE" "$SRC_DIR/third_party/frp/component.txt" "$PREFIX/vendor/frp/"
  fi
}

# Keep a version-matched, root-owned installer payload so the control panel
# can add an omitted module later without depending on the original clone.
# The payload never contains runtime data, certificates, or credentials.
prepare_module_source() {
  has_module web || return 0
  case "$SRC_DIR/" in "$PREFIX_ABS/installer-source/"*) return 0 ;; esac
  local stage item
  stage="$(mktemp -d "$PREFIX/.installer-source.XXXXXX")"
  for item in src deploy tools lang third_party config doc README.md LICENSE .env.example; do
    [ -e "$SRC_DIR/$item" ] && cp -a "$SRC_DIR/$item" "$stage/$item"
  done
  printf '%s\n' "$NEW_VERSION" > "$stage/config/VERSION"
  chown -R root:root "$stage"
  chmod -R go-w "$stage"
  rm -rf -- "$PREFIX/.installer-source-old"
  if [ -d "$PREFIX/installer-source" ]; then
    mv "$PREFIX/installer-source" "$PREFIX/.installer-source-old"
  fi
  mv "$stage" "$PREFIX/installer-source"
  rm -rf -- "$PREFIX/.installer-source-old"
}

# anytls/proxy on their own: nothing below this point applies, since all of
# it exists to install and configure the Python service.
if ! has_module web; then
  copy_selected_files
  if has_module anytls || has_module proxy; then
    systemctl stop vps-server-anytls.service vps-server-proxy.service vps-server-node-meter.service >/dev/null 2>&1 || true
  fi
  ANYTLS_FAILED=0
  if has_module anytls; then
    install_anytls || ANYTLS_FAILED=1
  fi
  PROXY_FAILED=0
  if has_module proxy; then
    install_proxy || PROXY_FAILED=1
  fi
  FRPS_FAILED=0
  if has_module frps; then
    PREFIX="$PREFIX" VPSSRV_CONSOLE_PORT="${VPSSRV_CONSOLE_PORT:-}" bash "$PREFIX/frps/setup-frps.sh" || FRPS_FAILED=1
  fi
  msg to_remove "$PREFIX" "$SERVICE_NAME"
  [ "$ANYTLS_FAILED" = "0" ] || { msg anytls_failed >&2; exit 1; }
  [ "$PROXY_FAILED" = "0" ] || { msg proxy_failed >&2; exit 1; }
  install_node_meter || {
    journalctl -u vps-server-node-meter.service -n 40 --no-pager >&2 || true
    die "$(msg node_meter_failed)"
  }
  [ "$FRPS_FAILED" = "0" ] || die "$(msg frps_install_failed)"
  if has_module lucky; then
    PREFIX="$PREFIX" bash "$PREFIX/lucky/setup-lucky.sh" || die "$(msg lucky_install_failed)"
  fi
  write_state
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
          # The || fallbacks are not decoration: under set -e a bare failing
          # read — Ctrl-D at the prompt, a momentarily unavailable /dev/tty —
          # kills the whole installer instead of reaching the retry below.
          # Every other read in this file has one; these two were missed.
          msg pw_enter
          read -rs MANUAL_PASSWORD </dev/tty || MANUAL_PASSWORD=""; echo
          msg pw_confirm
          read -rs pw_confirm </dev/tty || pw_confirm=""; echo
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
# 3. Port: random (default, see doc/LOG.md#decisions) or an operator-chosen one.
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

check_frps_console_collision

# Preserve the installed Lucky admin listener even on a web-only rerun.
# Resolve the console choice after the prompt and before probing/stopping web.
if has_module web && [ -f /etc/vps-server-lucky/config.json ]; then
  console_candidate="${VPSSRV_CONSOLE_PORT:-}"
  if [ -f "$PREFIX/data/console-port-override" ]; then
    console_candidate="$(tr -d '[:space:]' < "$PREFIX/data/console-port-override")"
  fi
  console_file="${VPSSRV_CONSOLE_PORT_FILE:-$PREFIX/console_port.txt}"
  if [ -z "$console_candidate" ] && [ -f "$console_file" ]; then
    console_candidate="$(tr -d '[:space:]' < "$console_file")"
  fi
  if [ -n "$console_candidate" ]; then
    lucky_port="$(python3 - <<'PYLUCKY'
import json, sys
try:
    base = json.load(open('/etc/vps-server-lucky/config.json'))['BaseConfigure']
    port = base['AdminWebListenPort']
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('invalid admin port')
    print(port)
except (OSError, ValueError, KeyError, TypeError) as exc:
    print(f'Cannot verify Lucky admin port: {exc}', file=sys.stderr)
    sys.exit(2)
PYLUCKY
)" || die "$(msg lucky_port_verify)"
    if python3 -c 'import sys; p = sys.argv[1]; sys.exit(0 if p.isascii() and p.isdecimal() and int(p) == int(sys.argv[2]) else 1)' "$console_candidate" "$lucky_port"; then
      die "$(msg lucky_console_conflict "$console_candidate")"
    fi
  fi
fi

# Check before stopping anything, and put the service back if stopping it did
# not help. A console/frps conflict must be rejected before this block can
# stop an existing web service. On a re-run our own service may hold 80/443.
if has_module web && [ "${VPSSRV_PUBLIC_ENABLE:-1}" = "1" ] \
   && command -v ss >/dev/null 2>&1; then
  busy_port="$(first_busy_public_port || true)"
  if [ -n "$busy_port" ]; then
    if systemctl is-active --quiet "$SERVICE_NAME"; then
      # Most likely we are the holder, from the last install. Stopping is
      # safe because a successful run restarts it after installing.
      systemctl stop "$SERVICE_NAME" >/dev/null 2>&1 || true
      sleep 1
      busy_port="$(first_busy_public_port || true)"
      if [ -n "$busy_port" ]; then
        systemctl start "$SERVICE_NAME" >/dev/null 2>&1 || true
        die "$(msg port_busy "$busy_port" "$busy_port")"
      fi
    else
      die "$(msg port_busy "$busy_port" "$busy_port")"
    fi
  else
    systemctl stop "$SERVICE_NAME" >/dev/null 2>&1 || true
  fi
fi

msg installing "$PREFIX"
mkdir -p "$PREFIX"
if [ "$UPGRADE" = "0" ] && has_module web; then
  mkdir -p "$PREFIX/data"
  chmod 700 "$PREFIX/data"
  for feature in speedtest portfwd visitors; do
    printf '0\n' > "$PREFIX/data/$feature-enabled"
    chmod 600 "$PREFIX/data/$feature-enabled"
  done
fi

# In-place upgrades skip same-source directory copies but still install the
# root binary when a sing-box module is selected.
PREFIX_ABS="$(cd "$PREFIX" && pwd)"
copy_selected_files
prepare_module_source
if has_module lucky; then
  PREFIX="$PREFIX" bash "$PREFIX/lucky/setup-lucky.sh" || die "$(msg lucky_install_failed)"
fi
if has_module frps; then
  PREFIX="$PREFIX" VPSSRV_CONSOLE_PORT="${VPSSRV_CONSOLE_PORT:-}" bash "$PREFIX/frps/setup-frps.sh" || die "$(msg frps_install_failed)"
fi

# Whichever path was taken, the app must actually be there before we go on to
# write a unit file pointing at it.
[ -f "$PREFIX/app.py" ] || die "$(msg missing_app "$PREFIX")"

# Stamp the resolved version where app.py reads it. Skipped for an in-place
# upgrade: there $PREFIX *is* the checkout, and writing a derived value into
# it would dirty the working tree of whoever is developing there.
if [ "$SRC_DIR" != "$PREFIX_ABS" ]; then
  printf '%s\n' "$NEW_VERSION" > "$PREFIX/VERSION"
fi

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

if has_module iperf3; then
  install_iperf3 || exit 1
fi

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
PORT=""
if [ -f "$PREFIX/data/console-port-override" ]; then
  PORT="$(cat "$PREFIX/data/console-port-override")"
else
  PORT="${VPSSRV_CONSOLE_PORT:-}"
fi
if [ -z "$PORT" ] && [ -f "$PORT_FILE" ]; then
  PORT="$(cat "$PORT_FILE")"
fi
if has_module web && [ -n "$PORT" ]; then
  python3 "$PREFIX/console_port.py" register "$PREFIX" "$PORT" "$SERVICE_NAME.service" || {
    systemctl stop "$SERVICE_NAME" >/dev/null 2>&1 || true
    die "$(msg port_busy "$PORT" "$PORT")"
  }
fi

# The summary used to print a literal "<this-server>" and leave the operator to
# substitute it by hand. Read the real addresses instead. `ip route get` reports
# the source address the kernel would actually use to leave the box, which is
# the one worth putting first when several are present. Everything below is
# best-effort: no `ip`, no route, no addresses — any of those just restores the
# old placeholder rather than failing an install that otherwise succeeded.
primary_ip() {
  ip -4 route get 1.1.1.1 2>/dev/null |
    awk '{for (i = 1; i < NF; i++) if ($i == "src") { print $(i + 1); exit }}'
}

# Same interface filter as anytls/setup-anytls.sh: container and bridge
# interfaces are not addresses anyone wants pasted into a browser. Unlike that
# script, VPN interfaces are kept — a Tailscale or ZeroTier address is often
# exactly how the console gets reached, and each line is labelled with its
# interface so it is clear which network it belongs to.
other_ips() {
  local primary="$1" iface addr
  while read -r iface addr; do
    case "$iface" in
      lo|docker*|br-*|veth*|virbr*|cni*|flannel*|kube*) continue ;;
    esac
    [ "$addr" = "$primary" ] && continue
    printf '%s (%s)\n' "$addr" "$iface"
  done < <(ip -o -4 addr show scope global 2>/dev/null |
    awk '{split($4, a, "/"); print $2, a[1]}')
}

HOST="$(primary_ip || true)"
if [ -z "$HOST" ]; then
  HOST="$(msg host_placeholder)"
  OTHER_IPS=""
else
  # Comma-joined, because each entry already contains a space before its
  # "(iface)" label — space-separating them would read as one long run.
  OTHER_IPS="$(other_ips "$HOST" | paste -sd ',' - | sed 's/,/, /g' || true)"
fi

msg running
msg line_modules "$MODULES"
msg line_service "$SERVICE_NAME"
if [ "${VPSSRV_PUBLIC_ENABLE:-1}" = "1" ]; then
  msg line_public "$HOST" "$PUBLIC_HTTP_PORT" "$HOST" "$PUBLIC_HTTPS_PORT"
else
  msg line_public_off
fi
if [ -n "$PORT" ]; then
  msg line_url "$SCHEME" "$HOST" "$PORT"
else
  msg line_url_unknown "$SCHEME" "$HOST" "$PORT_FILE" "$SERVICE_NAME"
fi
[ -n "$OTHER_IPS" ] && msg line_also "$OTHER_IPS"
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

# Last, and after the web service is confirmed healthy: the anytls/proxy
# scripts each print a client-configuration block of their own, and burying
# that above the web summary would make it easy to miss.
# `has_module anytls && install_anytls` looks equivalent, but under `set -e` a
# failing install_anytls kills the script right here — before the teardown hint
# is printed, and with a non-zero exit that makes the already-installed and
# already-running web module look like it failed too. That is exactly what
# happened on the first anytls install attempt. Same reasoning applies to proxy.
if has_module anytls || has_module proxy; then
  systemctl stop vps-server-anytls.service vps-server-proxy.service vps-server-node-meter.service >/dev/null 2>&1 || true
fi
ANYTLS_FAILED=0
if has_module anytls; then
  install_anytls || ANYTLS_FAILED=1
fi
PROXY_FAILED=0
if has_module proxy; then
  install_proxy || PROXY_FAILED=1
fi

msg to_remove "$PREFIX" "$SERVICE_NAME"

if [ "$ANYTLS_FAILED" = "1" ]; then
  msg anytls_failed >&2
  exit 1
fi
if [ "$PROXY_FAILED" = "1" ]; then
  msg proxy_failed >&2
  exit 1
fi
install_node_meter || {
  journalctl -u vps-server-node-meter.service -n 40 --no-pager >&2 || true
  die "$(msg node_meter_failed)"
}
write_state
