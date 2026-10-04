#!/usr/bin/env bash
#
# Install vps-server. A fresh install starts with the management console only.
#
#   web      the public reachability page on 80/443 plus the private console
#   iperf3   bundled on amd64, so the console can open a test window
#   anytls   the sing-box anytls proxy (amd64 only)
#   proxy    sing-box vmess/vless/trojan/shadowsocks, any subset (amd64 only)
#   frps     offline FRP server (amd64 only)
#   lucky    offline DDNS and reverse-proxy admin (amd64 only)
#   tailscale  offline-installed Tailscale client (amd64 only)
#
#   sudo bash deploy/install.sh                             # console only
#   sudo VPSSRV_MODULES=web,iperf3 bash deploy/install.sh   # unattended, no prompts
#   sudo VPSSRV_MODULES=web VPSSRV_PUBLIC_ENABLE=0 bash deploy/install.sh   # console only
#   sudo PREFIX=/srv/vpssrv bash deploy/install.sh
#
# Installation uses safe defaults without a browser or terminal questions.
# VPSSRV_MODULES and other environment values may override those defaults.
#
# Re-running a v5.1.1-or-newer installation keeps its persistent state under
# /var/lib/vps-server. Earlier layouts require a deliberate clean install.

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

IPERF_SHA256="f1924a042ef4074b5974b8985a235ad2fcb45d52d02cec46b0dfb45e269b9bf2"

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
            VPSSRV_STATE_DIR VPSSRV_DATA_DIR VPSSRV_PASSWORD_FILE VPSSRV_IP_ALLOWLIST_FILE VPSSRV_AUTH VPSSRV_DEFAULT_LANG
            VPSSRV_LOGIN_MAX_ATTEMPTS VPSSRV_LOGIN_WINDOW_SECONDS VPSSRV_LOGIN_LOCKOUT_SECONDS
            VPSSRV_CERT_DIR VPSSRV_TLS_CERT VPSSRV_TLS_KEY VPSSRV_TRUST_PROXY
            VPSSRV_MAX_TEST_MB VPSSRV_TRACK_CONNECTIONS VPSSRV_CONN_POLL_SECONDS
            VPSSRV_TEST_SECONDS VPSSRV_WARMUP_SECONDS VPSSRV_DOWNLOAD_STREAMS
            VPSSRV_UPLOAD_STREAMS VPSSRV_PING_SAMPLES
            VPSSRV_PROXY_CONFIG VPSSRV_PROXY_SERVICE"
SCRIPT_VARS="PROXY_PROTOCOLS PROXY_SNI PROXY_ANYTLS_PORT PROXY_ANYTLS_PASSWORD
             PROXY_VMESS_PORT PROXY_VMESS_UUID PROXY_VLESS_PORT PROXY_VLESS_UUID
             PROXY_TROJAN_PORT PROXY_TROJAN_PASSWORD PROXY_SS_PORT PROXY_SS_PASSWORD"

# What this install left behind, so the next one can tell what changed.
# Deliberately not the unit file: the unit records only settings that were
# given a value, which says nothing about which settings the version knew of.
STATE_LOCATOR=/etc/vps-server/state-dir
STATE_DIR="${VPSSRV_STATE_DIR:-}"
if [ -z "$STATE_DIR" ] && [ -f "$STATE_LOCATOR" ]; then STATE_DIR="$(cat "$STATE_LOCATOR")"; fi
STATE_DIR="${STATE_DIR:-/var/lib/vps-server}"
STATE_FILE="$STATE_DIR/install-state"
ANYTLS_UNIT="/etc/systemd/system/vps-server-anytls.service"
ANYTLS_CONFIG_PATH="/etc/vps-server-anytls/config.json"
PROXY_UNIT="/etc/systemd/system/vps-server-proxy.service"
PROXY_CONFIG_PATH="/etc/vps-server-proxy/config.json"
FRPS_UNIT="/etc/systemd/system/vps-server-frps.service"
LUCKY_UNIT="/etc/systemd/system/vps-server-lucky.service"
TAILSCALE_UNIT="/etc/systemd/system/vps-server-tailscale.service"

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
      printf 'test-%s' "$(git -C "$SRC_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
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
  [ -f "$STATE_FILE" ] || [ -f "$UNIT_PATH" ] || [ -f "$ANYTLS_UNIT" ] || [ -f "$PROXY_UNIT" ] || [ -f "$FRPS_UNIT" ] || [ -f "$TAILSCALE_UNIT" ] || [ -f "$PREFIX/app.py" ]
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

  STATE_DIR="${VPSSRV_STATE_DIR:-${PREV[VPSSRV_STATE_DIR]:-$STATE_DIR}}"
  STATE_FILE="$STATE_DIR/install-state"

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
    { [ -x "$PREFIX/vendor/iperf3/iperf3" ] || command -v iperf3 >/dev/null 2>&1; } && PREV_MODULES="${PREV_MODULES:+$PREV_MODULES,}iperf3"
    [ -f "$ANYTLS_UNIT" ] && PREV_MODULES="${PREV_MODULES:+$PREV_MODULES,}anytls"
    [ -f "$PROXY_UNIT" ] && PREV_MODULES="${PREV_MODULES:+$PREV_MODULES,}proxy"
    [ -f "$FRPS_UNIT" ] && PREV_MODULES="${PREV_MODULES:+$PREV_MODULES,}frps"
    [ -f "$LUCKY_UNIT" ] && PREV_MODULES="${PREV_MODULES:+$PREV_MODULES,}lucky"
    [ -f "$TAILSCALE_UNIT" ] && PREV_MODULES="${PREV_MODULES:+$PREV_MODULES,}tailscale"
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

# Preserve every protocol in the unified proxy configuration.
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
    if t == "anytls":
        types.append("anytls")
        print("PROXY_ANYTLS_PORT=%s" % i.get("listen_port", ""))
        print("PROXY_ANYTLS_PASSWORD=%s" % (i.get("users") or [{}])[0].get("password", ""))
    elif t == "vmess":
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
report_new_settings() {
  local var new="" default
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
    msg upgrade_new_item "$var" "${default:-(empty)}"
  done
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
# so placeholders line up across all supported languages; templates that end
# without \n are prompts.
# ---------------------------------------------------------------------------

INSTALL_LANG="${VPSSRV_DEFAULT_LANG:-en}"
case "$INSTALL_LANG" in en|zh_cn|es) ;; *) INSTALL_LANG=en ;; esac

msg() {
  local key="$1"; shift
  local fmt
  # Catalog filenames are fixed here; no user-supplied path is sourced.
  case "$INSTALL_LANG" in
    zh_cn) source "$SRC_DIR/lang/installer/zh-CN.sh" ;;
    es) source "$SRC_DIR/lang/installer/es.sh" ;;
    *) source "$SRC_DIR/lang/installer/en.sh" ;;
  esac
  # shellcheck disable=SC2059  # fmt comes from the trusted catalog.
  printf "$fmt" "$@"
}

# Callers pass already-translated text, e.g. die "$(msg need_root)". Command
# substitution strips msg's trailing newline, so put it back here.
die() { printf '%s%s\n' "$(msg error_prefix)" "$*" >&2; exit 1; }

# The first external-state layout is a versioned baseline. Do not guess how
# to migrate an older installation whose files may already be missing.
prepare_state_layout() {
  STATE_DIR="${VPSSRV_STATE_DIR:-$STATE_DIR}"
  STATE_FILE="$STATE_DIR/install-state"
  if [ "$UPGRADE" = 1 ] && { [ ! -f "$STATE_DIR/.layout-version" ] || [ ! -f "$STATE_FILE" ] || [ ! -f "$STATE_DIR/paths.json" ]; }; then
    die "$(msg legacy_state_unsupported)"
  fi
  if [ -e "$STATE_DIR/.layout-version" ] && [ "$(cat "$STATE_DIR/.layout-version")" != 1 ]; then
    die "$(msg state_layout_invalid)"
  fi
  if [ -f "$STATE_DIR/.layout-version" ] && [ ! -f "$STATE_FILE" ] && [ "$UPGRADE" = 0 ]; then
    die "$(msg state_layout_invalid)"
  fi
  if [ "$UPGRADE" = 0 ] && [ ! -f "$STATE_DIR/.layout-version" ]; then
    for old in "$PREFIX/admin_password.txt" "$PREFIX/console_port.txt" "$PREFIX/data" "$PREFIX/certs" "$PREFIX/.install-state"; do
      [ ! -e "$old" ] && [ ! -L "$old" ] || die "$(msg legacy_state_unsupported)"
    done
    if [ -d "$STATE_DIR" ] && [ -n "$(ls -A "$STATE_DIR")" ]; then
      die "$(msg state_layout_invalid)"
    fi
  fi
  python3 - "$PREFIX" "$STATE_DIR" <<'PY'
from pathlib import Path
import sys
prefix, state = (Path(value) for value in sys.argv[1:])
if not state.is_absolute() or any(char.isspace() for char in str(state)):
    raise SystemExit("invalid state directory")
prefix, state = prefix.resolve(strict=False), state.resolve(strict=False)
if state == prefix or prefix in state.parents or state == Path("/"):
    raise SystemExit("state directory must be outside the application")
PY
  if [ -f "$STATE_LOCATOR" ] && [ "$(cat "$STATE_LOCATOR")" != "$STATE_DIR" ]; then
    die "$(msg state_layout_invalid)"
  fi
  export VPSSRV_STATE_DIR="$STATE_DIR"
}

load_state_env() {
  local line key value env_file="$STATE_DIR/.env"
  if [ ! -f "$env_file" ] && [ "$UPGRADE" = 0 ]; then env_file="$SRC_DIR/.env"; fi
  [ -f "$env_file" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line#"${line%%[![:space:]]*}"}"
    case "$line" in ''|\#*) continue ;; *=*) ;; *) continue ;; esac
    key="${line%%=*}"; value="${line#*=}"
    key="${key%"${key##*[![:space:]]}"}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    case " $KNOWN_VARS $SCRIPT_VARS " in *" $key "*) ;; *) continue ;; esac
    [ "$key" != VPSSRV_STATE_DIR ] || continue
    [ -n "${!key:-}" ] || export "$key=$value"
  done < "$env_file"
}

load_state_paths() {
  local values kv key value
  [ -f "$STATE_DIR/paths.json" ] || return 0
  values="$(python3 - "$STATE_DIR/paths.json" <<'PY'
import json, sys
from pathlib import Path
paths = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for key in ("VPSSRV_DATA_DIR", "VPSSRV_PASSWORD_FILE", "VPSSRV_CONSOLE_PORT_FILE", "VPSSRV_CERT_DIR"):
    value = paths[key]
    if not isinstance(value, str) or not value.startswith("/") or "\n" in value:
        raise SystemExit("invalid persisted path")
    print(key + "=" + value)
PY
)" || die "$(msg state_layout_invalid)"
  while IFS= read -r kv; do
    key="${kv%%=*}"; value="${kv#*=}"
    [ -n "${!key:-}" ] || export "$key=$value"
  done <<< "$values"
}

set_state_defaults() {
  export VPSSRV_DATA_DIR="${VPSSRV_DATA_DIR:-$STATE_DIR/data}"
  export VPSSRV_PASSWORD_FILE="${VPSSRV_PASSWORD_FILE:-$STATE_DIR/admin_password.txt}"
  export VPSSRV_CONSOLE_PORT_FILE="${VPSSRV_CONSOLE_PORT_FILE:-$STATE_DIR/console_port.txt}"
  export VPSSRV_CERT_DIR="${VPSSRV_CERT_DIR:-$STATE_DIR/certs}"
  export VPSSRV_IP_ALLOWLIST_FILE="${VPSSRV_IP_ALLOWLIST_FILE:-$VPSSRV_DATA_DIR/login-access.json}"
  python3 - "$PREFIX" "$VPSSRV_DATA_DIR" "$VPSSRV_PASSWORD_FILE" "$VPSSRV_CONSOLE_PORT_FILE" "$VPSSRV_CERT_DIR" "$VPSSRV_IP_ALLOWLIST_FILE" <<'PY'
from pathlib import Path
import sys
prefix = Path(sys.argv[1]).resolve(strict=False)
for raw in sys.argv[2:]:
    path = Path(raw)
    if not path.is_absolute() or any(char.isspace() for char in raw):
        raise SystemExit("persistent path must be absolute without spaces")
    resolved = path.resolve(strict=False)
    if resolved == prefix or prefix in resolved.parents:
        raise SystemExit("persistent path must be outside the application")
PY
  if [ "$UPGRADE" = 1 ] && [[ ",$PREV_MODULES," == *,web,* ]]; then
    [ -f "$VPSSRV_PASSWORD_FILE" ] && [ -f "$VPSSRV_DATA_DIR/session_secret.txt" ] &&
      [ -d "$VPSSRV_CERT_DIR" ] || die "$(msg state_layout_invalid)"
    if [ ! -f "$VPSSRV_DATA_DIR/console-port-override" ] &&
       [ ! -f "$VPSSRV_CONSOLE_PORT_FILE" ] &&
       { [ -z "${VPSSRV_CONSOLE_PORT:-}" ] || [ "${VPSSRV_CONSOLE_PORT:-0}" = 0 ]; }; then
      die "$(msg state_layout_invalid)"
    fi
  fi
  python3 - "$STATE_DIR/paths.json" "$VPSSRV_DATA_DIR" "$VPSSRV_PASSWORD_FILE" "$VPSSRV_CONSOLE_PORT_FILE" "$VPSSRV_CERT_DIR" <<'PY'
import json, pathlib, sys
record = pathlib.Path(sys.argv[1])
wanted = dict(zip(("VPSSRV_DATA_DIR", "VPSSRV_PASSWORD_FILE", "VPSSRV_CONSOLE_PORT_FILE", "VPSSRV_CERT_DIR"), sys.argv[2:]))
if record.is_file() and json.loads(record.read_text(encoding="utf-8")) != wanted:
    raise SystemExit("persistent paths changed; manual transfer is required")
PY
}

commit_state_layout() {
  mkdir -p "$STATE_DIR/data" "$STATE_DIR/certs" "$VPSSRV_DATA_DIR" "$VPSSRV_CERT_DIR" \
           "$(dirname "$VPSSRV_PASSWORD_FILE")" "$(dirname "$VPSSRV_CONSOLE_PORT_FILE")" \
           "$(dirname "$VPSSRV_IP_ALLOWLIST_FILE")" "$(dirname "$STATE_LOCATOR")"
  chmod 0700 "$STATE_DIR" "$STATE_DIR/data" "$STATE_DIR/certs" "$VPSSRV_DATA_DIR" "$VPSSRV_CERT_DIR"
  if [ ! -f "$STATE_DIR/.env" ] && [ -f "$SRC_DIR/.env" ]; then
    install -m 0600 "$SRC_DIR/.env" "$STATE_DIR/.env"
  fi
  python3 - "$STATE_DIR/paths.json" "$VPSSRV_DATA_DIR" "$VPSSRV_PASSWORD_FILE" "$VPSSRV_CONSOLE_PORT_FILE" "$VPSSRV_CERT_DIR" <<'PY'
import json, os, pathlib, sys, tempfile
record = pathlib.Path(sys.argv[1])
wanted = dict(zip(("VPSSRV_DATA_DIR", "VPSSRV_PASSWORD_FILE", "VPSSRV_CONSOLE_PORT_FILE", "VPSSRV_CERT_DIR"), sys.argv[2:]))
if not record.is_file():
    fd, name = tempfile.mkstemp(prefix=".paths-", dir=record.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(wanted, output, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, record)
    finally:
        pathlib.Path(name).unlink(missing_ok=True)
PY
  if [ ! -f "$STATE_DIR/.layout-version" ]; then
    (umask 077; printf '1\n' > "$STATE_DIR/.layout-version")
  fi
  local locator_tmp
  locator_tmp="$(mktemp "$(dirname "$STATE_LOCATOR")/.state-dir.XXXXXX")"
  chmod 0600 "$locator_tmp"
  printf '%s\n' "$STATE_DIR" > "$locator_tmp"
  mv -f -- "$locator_tmp" "$STATE_LOCATOR"
}

[ "$(id -u)" -eq 0 ] || die "$(msg need_root)"
command -v systemctl >/dev/null 2>&1 || die "$(msg no_systemd)"
command -v python3 >/dev/null 2>&1 || die "$(msg no_python)"
[ "$(uname -s)" = Linux ] && { [ "$(uname -m)" = x86_64 ] || [ "$(uname -m)" = amd64 ]; } || die "$(msg platform_unsupported)"

# Reuse the installed language unless this run explicitly selects another.
if [ -z "${VPSSRV_DEFAULT_LANG:-}" ]; then
  PREV_LANG="$(unit_env VPSSRV_DEFAULT_LANG)"
  case "$PREV_LANG" in
    en|zh_cn|es) INSTALL_LANG="$PREV_LANG" ;;
  esac
  if [ -z "$PREV_LANG" ]; then
    lang_file="$STATE_DIR/.env"
    [ -f "$lang_file" ] || lang_file="$SRC_DIR/.env"
    if [ -f "$lang_file" ]; then
      env_lang="$(sed -n 's/^[[:space:]]*VPSSRV_DEFAULT_LANG[[:space:]]*=[[:space:]]*//p' "$lang_file" | tail -n1)"
      case "$env_lang" in en|zh_cn|es) INSTALL_LANG="$env_lang" ;; esac
    fi
  fi
  if [ -t 0 ] && [ -t 1 ]; then
    case "$INSTALL_LANG" in en) default_choice=1 ;; zh_cn) default_choice=2 ;; es) default_choice=3 ;; esac
    msg language_menu
    while true; do
      msg language_choice "$default_choice"
      IFS= read -r choice || choice=""
      choice="${choice:-$default_choice}"
      case "$choice" in
        1) INSTALL_LANG=en; break ;;
        2) INSTALL_LANG=zh_cn; break ;;
        3) INSTALL_LANG=es; break ;;
        *) msg language_invalid ;;
      esac
    done
  fi
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
fi

# A legacy AnyTLS module becomes a protocol of the one proxy module. Keep
# the other selected modules and their order without retaining a second unit.
MODULES="$(python3 - "$MODULES" <<'PY'
import sys
modules = []
for module in sys.argv[1].split(','):
    if module == 'anytls':
        module = 'proxy'
    if module and module not in modules:
        modules.append(module)
print(','.join(modules))
PY
)"

prepare_state_layout
load_state_env
load_state_paths
set_state_defaults
commit_state_layout
PASSWORD_WAS_PRESENT=0
[ -f "$VPSSRV_PASSWORD_FILE" ] && PASSWORD_WAS_PRESENT=1
if [ "$UPGRADE" = 1 ]; then
  preserve_proxy
fi
if [ -n "${VPSSRV_DEFAULT_LANG:-}" ]; then
  INSTALL_LANG="$VPSSRV_DEFAULT_LANG"
  case "$INSTALL_LANG" in en|zh_cn|es) ;; *) INSTALL_LANG=en ;; esac
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
  report_new_settings
fi

# Bundled executable assets target x86-64 Linux only.
install_iperf3() {
  local source="$SRC_DIR/third_party/iperf3/iperf3" digest
  [ -f "$source" ] || { msg iperf_failed; return 1; }
  digest="$(sha256sum "$source")"
  [ "${digest%% *}" = "$IPERF_SHA256" ] || { msg iperf_failed; return 1; }
  if [ -x "$PREFIX/vendor/iperf3/iperf3" ]; then
    digest="$(sha256sum "$PREFIX/vendor/iperf3/iperf3")"
    [ "${digest%% *}" = "$IPERF_SHA256" ] && return 0
  fi
  mkdir -p "$PREFIX/vendor/iperf3"
  install -m 755 "$source" "$PREFIX/vendor/iperf3/iperf3.tmp"
  mv -f "$PREFIX/vendor/iperf3/iperf3.tmp" "$PREFIX/vendor/iperf3/iperf3"
}

install_proxy() {
  msg proxy_start "${PROXY_PROTOCOLS:-anytls,vmess,vless,trojan,shadowsocks}"
  if [ -f /etc/vps-server-nodes/state.json ] && [ -f "$PROXY_CONFIG_PATH" ] &&
     [ -f /etc/systemd/system/vps-server-proxy.service ]; then
    return 0
  fi
  # This script owns the one sing-box binary, config, unit, firewall and
  # client-config summary for all five protocols. Every
  # PROXY_<PROTO>_* credential/port var is passed through unset by default —
  # preserve_proxy() above has already exported them on an upgrade, and
  # setup-proxy.sh generates fresh ones itself when they arrive empty.
  PROXY_PROTOCOLS="${PROXY_PROTOCOLS:-}" PROXY_SNI="${PROXY_SNI:-www.bing.com}" \
  PROXY_ANYTLS_PORT="${PROXY_ANYTLS_PORT:-}" PROXY_ANYTLS_PASSWORD="${PROXY_ANYTLS_PASSWORD:-}" \
  PROXY_VMESS_PORT="${PROXY_VMESS_PORT:-}" PROXY_VMESS_UUID="${PROXY_VMESS_UUID:-}" \
  PROXY_VLESS_PORT="${PROXY_VLESS_PORT:-}" PROXY_VLESS_UUID="${PROXY_VLESS_UUID:-}" \
  PROXY_TROJAN_PORT="${PROXY_TROJAN_PORT:-}" PROXY_TROJAN_PASSWORD="${PROXY_TROJAN_PASSWORD:-}" \
  PROXY_SS_PORT="${PROXY_SS_PORT:-}" PROXY_SS_PASSWORD="${PROXY_SS_PASSWORD:-}" \
  VPSSRV_NODE_LOCK_FD="${node_lock:-}" VPSSRV_DEFER_NODE_START=1 VPSSRV_EMPTY_NODE_INSTALL=1 bash "$PREFIX/proxy/setup-proxy.sh"
}

install_node_meter() {
  if ! has_module proxy; then
    systemctl disable --now vps-server-node-meter.service >/dev/null 2>&1 || true
    return 0
  fi
  # The installer held the node lock while preserving and applying legacy
  # configs. Release it before init or starting the notify-type meter unit.
  if [ -n "${node_lock:-}" ]; then
    exec {node_lock}>&-
    unset node_lock
  fi
  /usr/bin/python3 "$PREFIX/src/web/nft_runtime.py" check >/dev/null 2>&1 || return 1
  /usr/bin/python3 "$PREFIX/src/web/node_control.py" init || return 1
  local was_proxy=0
  systemctl is-enabled --quiet vps-server-proxy.service && was_proxy=1 || true
  mkdir -p /etc/systemd/system/vps-server-proxy.service.d
  cat > /etc/systemd/system/vps-server-proxy.service.d/node-meter.conf <<EOF
[Unit]
Requires=vps-server-node-meter.service
After=vps-server-node-meter.service
EOF
  cat > /etc/systemd/system/vps-server-node-meter.service <<EOF
[Unit]
Description=vps-server node traffic accounting and limits
After=network-online.target
Wants=network-online.target
Before=vps-server-proxy.service

[Service]
Type=notify
NotifyAccess=main
ExecStart=/usr/bin/python3 $PREFIX/src/web/node_meter.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/etc/vps-server-nodes /etc/vps-server-node.lock

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl stop vps-server-proxy.service >/dev/null 2>&1 || true
  systemctl enable vps-server-node-meter.service || return 1
  systemctl restart vps-server-node-meter.service || return 1
  [ "$was_proxy" = 0 ] || systemctl start vps-server-proxy.service || return 1
}

# A later web install must not displace an already-running frps listener.
# Resolve the effective console port (explicit override, then persisted file)
# after the port prompt, but before any web service stop, copy, or unit change.
check_frps_console_collision() {
if has_module web && [ -f /etc/vps-server-frps/frps.toml ]; then
  console_candidate="${VPSSRV_CONSOLE_PORT:-}"
  if [ -f "$VPSSRV_DATA_DIR/console-port-override" ]; then
    console_candidate="$(tr -d '[:space:]' < "$VPSSRV_DATA_DIR/console-port-override")"
  fi
  console_file="$VPSSRV_CONSOLE_PORT_FILE"
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
  python3 - "$1" <<'PY'
import socket, sys
port = int(sys.argv[1])
for family, host in ((socket.AF_INET, '0.0.0.0'), (socket.AF_INET6, '::')):
    try:
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            probe.bind((host, port))
    except OSError as exc:
        if family == socket.AF_INET6 and exc.errno in (93, 97):
            continue
        raise SystemExit(0)
raise SystemExit(1)
PY
}

first_busy_public_port() {
  local name p enabled flag
  for name in http https; do
    if [ "$name" = http ]; then p="$PUBLIC_HTTP_PORT"; else p="$PUBLIC_HTTPS_PORT"; fi
    flag="$VPSSRV_DATA_DIR/web-${name}-enabled"
    enabled="${VPSSRV_PUBLIC_ENABLE:-0}"
    if [ -f "$flag" ]; then enabled="$(tr -d '[:space:]' < "$flag")"; fi
    if [ "$enabled" = 1 ] && port_held "$p"; then printf '%s' "$p"; return 0; fi
  done
  return 1
}

# The checkout keeps the binary under third_party/, but installed modules still
# expect the shared binary directly under PREFIX. Never copy stateful data.
copy_singbox_binary() {
  [ -f "$SRC_DIR/third_party/sing-box/sing-box" ] || return 1
  printf '%s  %s\n' '68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7' \
    "$SRC_DIR/third_party/sing-box/sing-box" | sha256sum -c - >/dev/null || return 1
  install -m 0755 "$SRC_DIR/third_party/sing-box/sing-box" "$PREFIX/sing-box"
  install -m 0755 "$SRC_DIR/third_party/sing-box/sing-box" /usr/local/bin/sing-box-vps-server
  if [ "$SRC_DIR" != "$(cd "$PREFIX" && pwd)" ]; then
    mkdir -p "$PREFIX/vendor/sing-box"
    cp "$SRC_DIR/third_party/sing-box/LICENSE" "$SRC_DIR/third_party/sing-box/sing-box.version" \
      "$PREFIX/vendor/sing-box/"
  fi
}

stage_nft_runtime() {
  has_module proxy || return 0
  local asset="$SRC_DIR/third_party/nft/nft-runtime-bullseye.tar.gz"
  if [ ! -f "$asset" ]; then
    command -v nft >/dev/null 2>&1 || return 1
    return 0
  fi
  printf '%s  %s\n' '42eeb9496a173777df2e46d67b32b631e5eb31bbc1a74d2a0fa335f32a46c9eb' "$asset" |
    sha256sum -c - >/dev/null || return 1
  mkdir -p "$PREFIX/vendor"
  local staged="$PREFIX/vendor/.nft-staged-$$" previous="$PREFIX/vendor/.nft-previous-$$"
  mkdir -p "$staged"
  tar -xzf "$asset" -C "$staged" || return 1
  [ -f "$staged/usr/sbin/nft" ] || return 1
  if [ -d "$PREFIX/vendor/nft" ]; then mv "$PREFIX/vendor/nft" "$previous"; fi
  mv "$staged" "$PREFIX/vendor/nft"
  VPSSRV_NFT_ROOT="$PREFIX/vendor/nft" /usr/bin/python3 "$SRC_DIR/src/web/nft_runtime.py" check >/dev/null 2>&1 || {
    rm -r -- "$PREFIX/vendor/nft"
    if [ -d "$previous" ]; then mv "$previous" "$PREFIX/vendor/nft"; fi
    return 1
  }
  if [ -d "$previous" ]; then rm -r -- "$previous"; fi
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
    for module in proxy frps lucky tailscale; do
      has_module "$module" || continue
      [ -d "$SRC_DIR/deploy/$module" ] || continue
      mkdir -p "$PREFIX/$module"
      cp -a "$SRC_DIR/deploy/$module/." "$PREFIX/$module/"
    done
  else
    local copy_items item source
    copy_items="lang"
    if has_module web; then
      copy_items="$copy_items systemd README.md LICENSE"
    fi
    has_module proxy && copy_items="$copy_items proxy"
    has_module frps && copy_items="$copy_items frps"
    has_module lucky && copy_items="$copy_items lucky"
    has_module tailscale && copy_items="$copy_items tailscale"
    for item in $copy_items; do
      source="$SRC_DIR/$item"
      case "$item" in systemd|proxy|frps|lucky|tailscale) source="$SRC_DIR/deploy/$item" ;; esac
      [ -e "$source" ] || continue
      rm -rf "${PREFIX:?}/$item"
      cp -r "$source" "$PREFIX/$item"
    done
  fi
  if has_module web || has_module proxy || has_module tailscale || \
     [ -f "$ANYTLS_CONFIG_PATH" ] || [ -f "$PROXY_CONFIG_PATH" ]; then
    if [ "$SRC_DIR" != "$prefix_abs" ]; then
      mkdir -p "$PREFIX/src/web"
      cp "$SRC_DIR/src/web/"*.py "$PREFIX/src/web/"
    fi
  fi
  if has_module web; then
    if [ "$SRC_DIR" != "$prefix_abs" ]; then
      rm -rf "${PREFIX:?}/src/web/features" "${PREFIX:?}/src/web/static"
      cp -r "$SRC_DIR/src/web/features" "$PREFIX/src/web/features"
      cp -r "$SRC_DIR/src/web/static" "$PREFIX/src/web/static"
    fi
    cp "$SRC_DIR/deploy/runtime-entry.py" "$PREFIX/app.py"
  fi
  if has_module web && [ "$SRC_DIR" != "$prefix_abs" ]; then
    # Documentation required by /changelog and third-party notices.
    local doc_items="doc/LOG.md doc/CHANGELOG.md doc/THIRD_PARTY_NOTICES.md
                     doc/en/LOG.md doc/en/CHANGELOG.md
                     doc/es/LOG.md doc/es/CHANGELOG.md"
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
  if has_module web || has_module proxy || [ -f "$ANYTLS_CONFIG_PATH" ] || [ -f "$PROXY_CONFIG_PATH" ]; then
    copy_singbox_binary
  fi
  if has_module lucky; then
    mkdir -p "$PREFIX/vendor/lucky"
    cp "$SRC_DIR/third_party/lucky/lucky" "$SRC_DIR/third_party/lucky/LICENSE" "$SRC_DIR/third_party/lucky/component.txt" "$PREFIX/vendor/lucky/"
  fi
  if has_module tailscale; then
    mkdir -p "$PREFIX/vendor/tailscale"
    cp "$SRC_DIR/third_party/tailscale/tailscale_1.102.4_amd64.tgz" "$PREFIX/vendor/tailscale/"
  fi
  if has_module frps; then
    mkdir -p "$PREFIX/vendor/frp"
    cp "$SRC_DIR/third_party/frp/frps" "$SRC_DIR/third_party/frp/frpc" \
       "$SRC_DIR/third_party/frp/LICENSE" "$SRC_DIR/third_party/frp/component.txt" "$PREFIX/vendor/frp/"
  fi
}

register_optional_listener() {
  local module="$1" unit
  case "$module" in
    frps) unit=vps-server-frps.service ;;
    lucky) unit=vps-server-lucky.service ;;
    *) return 2 ;;
  esac
  python3 - "$PREFIX" "$module" <<'PY' || {
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / 'src' / 'web'))
from console_port import reserve_owned_port
from module_manager import managed_listener
reserve_owned_port(sys.argv[1], *managed_listener(sys.argv[2]), probe=False)
PY
    systemctl disable --now "$unit" >/dev/null 2>&1 || true
    die "$(msg port_registration_failed "$module")"
  }
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

# proxy on its own: nothing below this point applies, since all of
# it exists to install and configure the Python service.
if ! has_module web; then
  stage_nft_runtime || die "$(msg nft_runtime_failed)"
  if [ -f "$ANYTLS_CONFIG_PATH" ]; then
    [ -f "$SRC_DIR/src/web/proxy_migration.py" ] || die "$(msg proxy_migration_failed)"
    PREFIX="$PREFIX" VPSSRV_NFT_ROOT="$PREFIX/vendor/nft" VPSSRV_NODE_LOCK_FD="${node_lock:-}" \
      /usr/bin/python3 "$SRC_DIR/src/web/proxy_migration.py" migrate || die "$(msg proxy_migration_failed)"
  fi
  copy_selected_files
  if has_module proxy; then
    systemctl stop vps-server-proxy.service vps-server-node-meter.service >/dev/null 2>&1 || true
  fi
  PROXY_FAILED=0
  if has_module proxy; then
    install_proxy || PROXY_FAILED=1
  fi
  FRPS_FAILED=0
  if has_module frps; then
    PREFIX="$PREFIX" VPSSRV_CONSOLE_PORT="${VPSSRV_CONSOLE_PORT:-}" bash "$PREFIX/frps/setup-frps.sh" || FRPS_FAILED=1
  fi
  msg to_remove "$PREFIX" "$SERVICE_NAME" "$PREFIX" "$SERVICE_NAME"
  [ "$PROXY_FAILED" = "0" ] || { msg proxy_failed >&2; exit 1; }
  install_node_meter || {
    journalctl -u vps-server-node-meter.service -n 40 --no-pager >&2 || true
    die "$(msg node_meter_failed)"
  }
  [ "$FRPS_FAILED" = "0" ] || die "$(msg frps_install_failed)"
  if has_module lucky; then
    PREFIX="$PREFIX" bash "$PREFIX/lucky/setup-lucky.sh" || die "$(msg lucky_install_failed)"
    register_optional_listener lucky
  fi
  if has_module frps; then register_optional_listener frps; fi
  if has_module tailscale; then
    PREFIX="$PREFIX" VPSSRV_STATE_DIR="$STATE_DIR" bash "$PREFIX/tailscale/setup-tailscale.sh" "$PREFIX/vendor/tailscale/tailscale_1.102.4_amd64.tgz" || die "$(msg tailscale_install_failed)"
  fi
  write_state
  if [ -f "$PREFIX/src/web/proxy_migration.py" ]; then
    PREFIX="$PREFIX" VPSSRV_STATE_DIR="$STATE_DIR" /usr/bin/python3 "$PREFIX/src/web/proxy_migration.py" finalize ||
      die "$(msg proxy_migration_failed)"
  fi
  exit 0
fi

# ---------------------------------------------------------------------------
# 2. Password protection and the console port use noninteractive defaults.
# ---------------------------------------------------------------------------
VPSSRV_AUTH="${VPSSRV_AUTH:-1}"
if [ "$VPSSRV_AUTH" = "0" ]; then
  msg auth_disabled
fi

check_frps_console_collision

# Preserve the installed Lucky admin listener even on a web-only rerun.
# Resolve the console choice after the prompt and before probing/stopping web.
if has_module web && [ -f /etc/vps-server-lucky/config.json ]; then
  console_candidate="${VPSSRV_CONSOLE_PORT:-}"
  if [ -f "$VPSSRV_DATA_DIR/console-port-override" ]; then
    console_candidate="$(tr -d '[:space:]' < "$VPSSRV_DATA_DIR/console-port-override")"
  fi
  console_file="$VPSSRV_CONSOLE_PORT_FILE"
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
if has_module web; then
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
  mkdir -p "$VPSSRV_DATA_DIR"
  chmod 700 "$VPSSRV_DATA_DIR"
  for feature in speedtest portfwd visitors; do
    printf '0\n' > "$VPSSRV_DATA_DIR/$feature-enabled"
    chmod 600 "$VPSSRV_DATA_DIR/$feature-enabled"
  done
fi

# In-place upgrades skip same-source directory copies but still install the
# root binary when a sing-box module is selected.
PREFIX_ABS="$(cd "$PREFIX" && pwd)"
stage_nft_runtime || die "$(msg nft_runtime_failed)"
if [ -f "$ANYTLS_CONFIG_PATH" ]; then
  [ -f "$SRC_DIR/src/web/proxy_migration.py" ] || die "$(msg proxy_migration_failed)"
  [ -x /usr/local/bin/sing-box-vps-server ] &&
    VPSSRV_NFT_ROOT="$PREFIX/vendor/nft" /usr/bin/python3 "$SRC_DIR/src/web/nft_runtime.py" check >/dev/null 2>&1 ||
    die "$(msg proxy_migration_failed)"
  PREFIX="$PREFIX" VPSSRV_NFT_ROOT="$PREFIX/vendor/nft" VPSSRV_NODE_LOCK_FD="${node_lock:-}" /usr/bin/python3 "$SRC_DIR/src/web/proxy_migration.py" migrate ||
    die "$(msg proxy_migration_failed)"
fi
copy_selected_files
prepare_module_source
if has_module lucky; then
  PREFIX="$PREFIX" bash "$PREFIX/lucky/setup-lucky.sh" || die "$(msg lucky_install_failed)"
  register_optional_listener lucky
fi
if has_module tailscale; then
  PREFIX="$PREFIX" VPSSRV_STATE_DIR="$STATE_DIR" bash "$PREFIX/tailscale/setup-tailscale.sh" "$PREFIX/vendor/tailscale/tailscale_1.102.4_amd64.tgz" || die "$(msg tailscale_install_failed)"
fi
if has_module frps; then
  PREFIX="$PREFIX" VPSSRV_CONSOLE_PORT="${VPSSRV_CONSOLE_PORT:-}" bash "$PREFIX/frps/setup-frps.sh" || die "$(msg frps_install_failed)"
  register_optional_listener frps
fi

# Whichever path was taken, the app must actually be there before we go on to
# write a unit file pointing at it.
[ -f "$PREFIX/app.py" ] || die "$(msg missing_app "$PREFIX")"

# Stamp the resolved version where app.py reads it. Skipped for an in-place
# upgrade: there $PREFIX *is* the checkout, and writing a derived value into
# it would dirty the working tree of whoever is developing there.
if [ "$SRC_DIR" != "$PREFIX_ABS" ]; then
  printf '%s\n' "$NEW_VERSION" > "$PREFIX/VERSION"
  mkdir -p "$PREFIX/config"
  printf '%s\n' "$NEW_VERSION" > "$PREFIX/config/VERSION"
fi

# The Web process changes runtime forwards and public listeners. Give its
# sandbox access only to the shared registry and lock, not sibling projects.
python3 - "$PREFIX" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, str(Path(sys.argv[1]) / 'src' / 'web'))
from console_port import read_rows, write_rows
root = Path(sys.argv[1]).parent
root.mkdir(parents=True, exist_ok=True)
registry = root / 'PORTS.md'
rows, _ = read_rows(registry)
if not registry.exists():
    write_rows(registry, rows)
(root / '.ports.lock').touch(exist_ok=True)
PY
NEW_PUBLIC_PORTS="$(python3 - "$PREFIX" "$PUBLIC_HTTP_PORT" "$PUBLIC_HTTPS_PORT" "${VPSSRV_PUBLIC_ENABLE:-1}" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / 'src' / 'web'))
from console_port import reserve_owned_port, release_owned_port
from module_manager import public_listener_enabled
prefix = Path(sys.argv[1])
choices = (('web_http', int(sys.argv[2]), 'vps-server Web HTTP'),
           ('web_https', int(sys.argv[3]), 'vps-server Web HTTPS'))
new = []
try:
    for name, port, owner in choices:
        if public_listener_enabled(prefix, name, sys.argv[4] == '1'):
            if reserve_owned_port(prefix, port, owner, probe=False):
                new.append((name, port, owner))
except BaseException:
    for _, port, owner in reversed(new):
        release_owned_port(prefix, port, owner)
    raise
for name, _, _ in new:
    print(name)
PY
)" || die "Public listener port registration failed"
release_new_public_ports() {
  python3 - "$PREFIX" "$PUBLIC_HTTP_PORT" "$PUBLIC_HTTPS_PORT" "$NEW_PUBLIC_PORTS" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / 'src' / 'web'))
from console_port import release_owned_port
for name, port, owner in (('web_http', int(sys.argv[2]), 'vps-server Web HTTP'),
                          ('web_https', int(sys.argv[3]), 'vps-server Web HTTPS')):
    if name in sys.argv[4].split():
        release_owned_port(sys.argv[1], port, owner)
PY
}

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
ReadWritePaths=$PREFIX
ReadWritePaths=$STATE_DIR
ReadWritePaths=$VPSSRV_DATA_DIR
ReadWritePaths=$(dirname "$VPSSRV_PASSWORD_FILE")
ReadWritePaths=$(dirname "$VPSSRV_CONSOLE_PORT_FILE")
ReadWritePaths=$VPSSRV_CERT_DIR
ReadWritePaths=$(dirname "$VPSSRV_IP_ALLOWLIST_FILE")"
  HARDENING="$HARDENING
ReadWritePaths=$(dirname "$PREFIX")/PORTS.md
ReadWritePaths=$(dirname "$PREFIX")/.ports.lock"
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
systemctl restart "$SERVICE_NAME" || { release_new_public_ports; die "$(msg web_start_failed)"; }

sleep 2
if ! systemctl is-active --quiet "$SERVICE_NAME"; then
  release_new_public_ports
  msg start_failed >&2
  journalctl -u "$SERVICE_NAME" -n 20 --no-pager >&2 || true
  exit 1
fi

PW_FILE="$VPSSRV_PASSWORD_FILE"
PORT_FILE="$VPSSRV_CONSOLE_PORT_FILE"
if [ "${VPSSRV_CONSOLE_TLS:-0}" = "1" ]; then SCHEME=https; else SCHEME=http; fi
# VPSSRV_CONSOLE_PORT, if set, was carried into the unit verbatim. Otherwise app.py
# picked a random port on this first start and persisted it to PORT_FILE.
PORT=""
if [ -f "$VPSSRV_DATA_DIR/console-port-override" ]; then
  PORT="$(cat "$VPSSRV_DATA_DIR/console-port-override")"
else
  PORT="${VPSSRV_CONSOLE_PORT:-}"
fi
if [ -z "$PORT" ] && [ -f "$PORT_FILE" ]; then
  PORT="$(cat "$PORT_FILE")"
fi
if has_module web && [ -n "$PORT" ]; then
  python3 "$PREFIX/src/web/console_port.py" register "$PREFIX" "$PORT" "$SERVICE_NAME.service" || {
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
if [ -x "$PREFIX/vendor/iperf3/iperf3" ] || command -v iperf3 >/dev/null 2>&1; then
  msg line_iperf "${VPSSRV_IPERF_PORT:-5201}"
else
  msg line_iperf_off
fi
if [ "$VPSSRV_AUTH" = "0" ]; then
  msg line_pw_none
elif [ -f "$PW_FILE" ]; then
  if [ "$PASSWORD_WAS_PRESENT" = 1 ]; then msg line_pw_preserved "$PW_FILE"
  else msg line_pw "$(cat "$PW_FILE")" "$PW_FILE"; fi
else
  msg line_pw_seefile "$PW_FILE"
fi
if [ -n "${VPSSRV_DEFAULT_LANG:-}" ]; then
  msg line_lang "$VPSSRV_DEFAULT_LANG"
fi
if [ "${VPSSRV_CONSOLE_TLS:-0}" = "1" ] && [ -z "${VPSSRV_TLS_CERT:-}" ]; then
  msg cert_note
fi

# Install proxy after Web has reported its own status.
if has_module proxy; then
  systemctl stop vps-server-proxy.service vps-server-node-meter.service >/dev/null 2>&1 || true
fi
PROXY_FAILED=0
if has_module proxy; then
  install_proxy || PROXY_FAILED=1
fi

msg to_remove "$PREFIX" "$SERVICE_NAME" "$PREFIX" "$SERVICE_NAME"

if [ "$PROXY_FAILED" = "1" ]; then
  msg proxy_failed >&2
  exit 1
fi
install_node_meter || {
  journalctl -u vps-server-node-meter.service -n 40 --no-pager >&2 || true
  die "$(msg node_meter_failed)"
}
write_state
PREFIX="$PREFIX" VPSSRV_STATE_DIR="$STATE_DIR" /usr/bin/python3 "$PREFIX/src/web/proxy_migration.py" finalize ||
  die "$(msg proxy_migration_failed)"
