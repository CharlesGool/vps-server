#!/usr/bin/env bash
# Install a verified offline Lucky binary; never launch upstream's default credentials.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
INSTALL_LANG="${VPSSRV_DEFAULT_LANG:-en}"
case "$INSTALL_LANG" in
  zh_cn) CATALOG_LANG=zh-CN ;; zh_tw) CATALOG_LANG=zh-TW ;; zh_hk) CATALOG_LANG=zh-HK ;;
  en|hi|es|ar|fr) CATALOG_LANG="$INSTALL_LANG" ;; *) CATALOG_LANG=en ;;
esac
CATALOG_ROOT="${VPSSRV_CATALOG_ROOT:-}"
if [ -z "$CATALOG_ROOT" ]; then
  if [ -d "$SCRIPT_DIR/../../lang/lucky" ]; then CATALOG_ROOT="$SCRIPT_DIR/../../lang"
  else CATALOG_ROOT="${PREFIX:-/root/apps/vps-server}/lang"; fi
fi
msg() {
  local key="$1"; shift
  local fmt
  # shellcheck disable=SC1090
  source "$CATALOG_ROOT/lucky/$CATALOG_LANG.sh"
  printf "$fmt\n" "$@"
}
raw_msg() {
  local key="$1" fmt
  # shellcheck disable=SC1090
  source "$CATALOG_ROOT/lucky/$CATALOG_LANG.sh"
  printf '%s' "$fmt"
}
[ "$(id -u)" -eq 0 ] || { msg root_required >&2; exit 1; }
for key in malformed_current malformed_overwrite invalid_admin_port cannot_reverse reverse_conflict cannot_console cannot_verify_file cannot_frps cannot_forward reserved_conflict unavailable; do
  export "LUCKY_MSG_${key^^}=$(raw_msg "$key")"
done
# The installer copies deploy/lucky/ to PREFIX/lucky/ before invoking it.
# Resolve trailing slashes, '..', and symlinks in an existing install prefix.
PREFIX_DIR="$(cd "${PREFIX:-/root/apps/vps-server}" 2>/dev/null && pwd -P || :)"
if [ "$SCRIPT_DIR" = "$PREFIX_DIR/lucky" ]; then
  BIN="$SCRIPT_DIR/../vendor/lucky/lucky"
else
  BIN="$SCRIPT_DIR/../../third_party/lucky/lucky"
fi
CONFIG=/etc/vps-server-lucky/config.json
UNIT=/etc/systemd/system/vps-server-lucky.service
TARGET=/usr/local/bin/lucky-vps-server
OWNER=/etc/vps-server-lucky/firewall-owned
[ -f "$BIN" ] && [ "$(sha256sum "$BIN" | cut -d' ' -f1)" = 7d3193cf969e8ed041761544b41786bcc368d46b9cf4d4d679a5bc215bd3357a ] || { msg integrity_failure >&2; exit 1; }
# Noninteractive upgrades retain the previous exposure choice unless explicitly changed.
if [ -z "${LUCKY_PUBLIC_ADMIN+x}" ] && [ -f "$CONFIG" ]; then
  LUCKY_PUBLIC_ADMIN="$(python3 - "$CONFIG" <<'PY'
import json, os, sys
try:
    value = json.load(open(sys.argv[1]))['BaseConfigure'].get('AllowInternetaccess', False)
    if type(value) is not bool: raise ValueError('invalid public flag')
    print(int(value))
except (OSError, ValueError, KeyError, TypeError) as exc:
    raise SystemExit(os.environ['LUCKY_MSG_MALFORMED_CURRENT'] % exc)
PY
)" || exit 1
fi
case "${LUCKY_PUBLIC_ADMIN:-0}" in 0|1) ;; *) msg invalid_public >&2; exit 1 ;; esac
if [ "${LUCKY_PUBLIC_ADMIN:-0}" = 1 ]; then
  msg public_warning >&2
  [ "${LUCKY_PUBLIC_CONFIRM:-}" = 'I ACCEPT PUBLIC HTTP' ] || { msg confirm_required >&2; exit 1; }
fi
STAGE="$(mktemp -d)"; chmod 0700 "$STAGE"
trap 'rm -rf -- "$STAGE"' EXIT
PORT="$(python3 - "$CONFIG" "${LUCKY_ADMIN_PORT:-}" "${LUCKY_PUBLIC_ADMIN:-0}" "${PREFIX:-/root/apps/vps-server}" "$STAGE/config" <<'PY'
import json, os, pathlib, re, secrets, socket, subprocess, sys
config, requested, public, prefix, destination = sys.argv[1:]
path = pathlib.Path(config)
if path.exists():
    try:
        data = json.loads(path.read_text())
        base = data['BaseConfigure']
        if not isinstance(data, dict) or not isinstance(base, dict): raise ValueError('not an object')
        old_port = base['AdminWebListenPort']
        if type(old_port) is not int or not 1 <= old_port <= 65535: raise ValueError('invalid admin port')
        if not isinstance(base['AdminAccount'], str) or not base['AdminAccount'] or not isinstance(base['AdminPassword'], str) or not base['AdminPassword']: raise ValueError('invalid credentials')
        if base['AdminAccount'] == '666' and base['AdminPassword'] == '666': raise ValueError('insecure upstream defaults')
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        raise SystemExit(os.environ['LUCKY_MSG_MALFORMED_OVERWRITE'] % exc)
else:
    old_port = None
    data = {'BaseConfigure': {'AdminAccount': secrets.token_urlsafe(24), 'AdminPassword': secrets.token_urlsafe(32)}}
    base = data['BaseConfigure']
port = requested or str(old_port or 16601)
if not port.isascii() or not port.isdecimal() or not 1 <= int(port) <= 65535:
    raise SystemExit(os.environ['LUCKY_MSG_INVALID_ADMIN_PORT'])
port = int(port)
# Do not move admin onto an existing Lucky reverse proxy listener. Lucky's
# own forward-port expressions may include ranges; leave those untouched.
for rule in data.get('ReverseProxyRuleList', []):
    if not isinstance(rule, dict) or type(rule.get('ListenPort')) is not int:
        raise SystemExit(os.environ['LUCKY_MSG_CANNOT_REVERSE'])
    if port == rule['ListenPort']:
        raise SystemExit(os.environ['LUCKY_MSG_REVERSE_CONFLICT'] % port)
reserved = {80, 443, 5201}
unit = pathlib.Path('/etc/systemd/system/vps-server-web.service')
for key in ('VPSSRV_CONSOLE_PORT', 'VPSSRV_PUBLIC_HTTP_PORT', 'VPSSRV_PUBLIC_HTTPS_PORT', 'VPSSRV_IPERF_PORT'):
    value = os.environ.get(key, '')
    if value.isdecimal(): reserved.add(int(value))
if unit.exists():
    text = unit.read_text()
    for key in ('VPSSRV_CONSOLE_PORT', 'VPSSRV_PUBLIC_HTTP_PORT', 'VPSSRV_PUBLIC_HTTPS_PORT', 'VPSSRV_IPERF_PORT'):
        match = re.search(r'^Environment=' + key + r'=(\d+)$', text, re.M)
        if match: reserved.add(int(match[1]))
console = pathlib.Path(prefix) / 'console_port.txt'
if unit.exists():
    match = re.search(r'^Environment=VPSSRV_CONSOLE_PORT_FILE=(.+)$', unit.read_text(), re.M)
    if match: console = pathlib.Path(match[1])
if console.exists():
    value = console.read_text().strip()
    if not value.isdecimal(): raise SystemExit(os.environ['LUCKY_MSG_CANNOT_CONSOLE'])
    reserved.add(int(value))
for file in ('/etc/vps-server-anytls/config.json', '/etc/vps-server-proxy/config.json'):
    if pathlib.Path(file).exists():
        try: reserved.update(int(i['listen_port']) for i in json.loads(pathlib.Path(file).read_text())['inbounds'])
        except (ValueError, TypeError, KeyError) as exc: raise SystemExit(os.environ['LUCKY_MSG_CANNOT_VERIFY_FILE'] % (file, exc))
frps = pathlib.Path('/etc/vps-server-frps/frps.toml')
if frps.exists():
    match = re.search(r'^bindPort\s*=\s*(\d+)\s*$', frps.read_text(), re.M)
    if not match: raise SystemExit(os.environ['LUCKY_MSG_CANNOT_FRPS'])
    reserved.add(int(match[1]))
forward = pathlib.Path(prefix) / 'data/portfwd.json'
if unit.exists():
    match = re.search(r'^Environment=VPSSRV_DATA_DIR=(.+)$', unit.read_text(), re.M)
    if match: forward = pathlib.Path(match[1]) / 'portfwd.json'
if forward.exists():
    try:
        rules = json.loads(forward.read_text())
        reserved.update(int(rule['public_port']) for rule in (rules if isinstance(rules, list) else rules['rules']))
    except (ValueError, TypeError, KeyError) as exc: raise SystemExit(os.environ['LUCKY_MSG_CANNOT_FORWARD'] % exc)
if port in reserved: raise SystemExit(os.environ['LUCKY_MSG_RESERVED_CONFLICT'] % port)
active = subprocess.run(['systemctl', 'is-active', '--quiet', 'vps-server-lucky.service']).returncode == 0
if not (active and port == old_port):
    for family, address in ((socket.AF_INET, '0.0.0.0'), (socket.AF_INET6, '::')):
        try:
            with socket.socket(family) as sock: sock.bind((address, port))
        except OSError as exc:
            if family == socket.AF_INET6 and exc.errno == 97: continue
            raise SystemExit(os.environ['LUCKY_MSG_UNAVAILABLE'] % exc)
base['AdminWebListenPort'] = port
base['AllowInternetaccess'] = public == '1'
# Preserve all other keys, DDNS/reverse-proxy tasks and credentials verbatim.
with open(destination, 'w') as output:
    os.fchmod(output.fileno(), 0o600)
    json.dump(data, output, ensure_ascii=False)
print(port)
PY
)"
ACTIVE=0 ENABLED=0
ADDED_BACKEND="" ADDED_PORT="" REMOVED_BACKEND="" REMOVED_PORT=""
declare -A FIREWALL_BEFORE=()
FIREWALL_DIRTY=0
systemctl is-active --quiet vps-server-lucky.service && ACTIVE=1 || true
systemctl is-enabled --quiet vps-server-lucky.service && ENABLED=1 || true
for name in config binary unit owner; do
  case "$name" in config) file="$CONFIG" ;; binary) file="$TARGET" ;; unit) file="$UNIT" ;; owner) file="$OWNER" ;; esac
  [ ! -e "$file" ] || cp -p -- "$file" "$STAGE/$name.old"
done
rollback() {
  local status=$? name file
  trap - EXIT
  if [ "$status" -ne 0 ]; then
    if [ "$FIREWALL_DIRTY" = 1 ]; then restore_firewalld || msg restore_fw >&2; fi
    if [ -n "$REMOVED_BACKEND" ] && [ "$REMOVED_BACKEND" != firewalld ]; then change_rule "$REMOVED_BACKEND" "$REMOVED_PORT" add || msg restore_old >&2; fi
    if [ -n "$ADDED_BACKEND" ] && [ "$ADDED_BACKEND" != firewalld ]; then change_rule "$ADDED_BACKEND" "$ADDED_PORT" remove || msg remove_new >&2; fi
    for name in config binary unit owner; do
      case "$name" in config) file="$CONFIG" ;; binary) file="$TARGET" ;; unit) file="$UNIT" ;; owner) file="$OWNER" ;; esac
      if [ -e "$STAGE/$name.old" ]; then cp -p -- "$STAGE/$name.old" "$file" || msg restore_file "$file" >&2
      else rm -f -- "$file" || msg remove_file "$file" >&2; fi
    done
    systemctl daemon-reload || true
    if [ "$ENABLED" = 1 ]; then systemctl enable vps-server-lucky.service || true; fi
    if [ "$ACTIVE" = 1 ]; then systemctl restart vps-server-lucky.service || msg restore_service >&2
    else systemctl disable --now vps-server-lucky.service || true; fi
  fi
  rm -rf -- "$STAGE"
  exit "$status"
}
trap rollback EXIT
mkdir -p "$(dirname "$CONFIG")"
install -m 0600 "$STAGE/config" "$CONFIG"
install -m 0755 "$BIN" "$TARGET"
cat > "$UNIT" <<'EOF'
[Unit]
Description=vps-server Lucky DDNS and reverse proxy
After=network.target
[Service]
Type=simple
ExecStart=/usr/local/bin/lucky-vps-server -c /etc/vps-server-lucky/config.json
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable vps-server-lucky.service >/dev/null
systemctl restart vps-server-lucky.service
systemctl is-active --quiet vps-server-lucky.service
# Manage only rules recorded as ours. Never remove an unowned rule.
backend=''
if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q 'Status: active'; then backend=ufw
elif command -v firewall-cmd >/dev/null && firewall-cmd --state >/dev/null 2>&1; then backend=firewalld; fi
if [ "${LUCKY_PUBLIC_ADMIN:-0}" = 1 ] && [ -z "$backend" ]; then
  msg no_firewall >&2
fi
rule_exists() {
  case "$1" in ufw) ufw status | grep -Eq "^${2}/tcp[[:space:]]" ;; firewalld) firewall-cmd --permanent --query-port="${2}/tcp" >/dev/null ;; *) return 1 ;; esac
}
change_rule() {
  case "$1:$3" in ufw:add) ufw allow "${2}/tcp" >/dev/null ;; ufw:remove) ufw --force delete allow "${2}/tcp" >/dev/null ;; firewalld:add) firewall-cmd --permanent --add-port="${2}/tcp" >/dev/null && firewall-cmd --reload >/dev/null ;; firewalld:remove) firewall-cmd --permanent --remove-port="${2}/tcp" >/dev/null && firewall-cmd --reload >/dev/null ;; esac
}
# A successful permanent mutation followed by a failed reload still needs
# rollback. Capture both layers before the first command changes either one.
snapshot_firewalld() {
  local port=$1 permanent=0 runtime=0
  [ -z "${FIREWALL_BEFORE[$port]+x}" ] || return 0
  firewall-cmd --permanent --query-port="${port}/tcp" >/dev/null 2>&1 && permanent=1
  firewall-cmd --query-port="${port}/tcp" >/dev/null 2>&1 && runtime=1
  FIREWALL_BEFORE[$port]="$permanent $runtime"
}
restore_firewalld() {
  local port permanent runtime failed=0
  for port in "${!FIREWALL_BEFORE[@]}"; do
    read -r permanent runtime <<< "${FIREWALL_BEFORE[$port]}"
    if [ "$permanent" = 1 ]; then
      firewall-cmd --permanent --add-port="${port}/tcp" >/dev/null || failed=1
    else
      firewall-cmd --permanent --remove-port="${port}/tcp" >/dev/null || failed=1
    fi
  done
  firewall-cmd --reload >/dev/null || failed=1
  for port in "${!FIREWALL_BEFORE[@]}"; do
    read -r permanent runtime <<< "${FIREWALL_BEFORE[$port]}"
    if [ "$runtime" = 1 ]; then
      firewall-cmd --add-port="${port}/tcp" >/dev/null || failed=1
    else
      firewall-cmd --remove-port="${port}/tcp" >/dev/null || failed=1
    fi
  done
  [ "$failed" = 0 ]
}
old_backend='' old_port=''
[ ! -f "$STAGE/owner.old" ] || read -r old_backend old_port < "$STAGE/owner.old" || true
wanted=''
[ "${LUCKY_PUBLIC_ADMIN:-0}" = 0 ] || wanted="$backend"
if [ -n "$wanted" ] && [ "$old_backend $old_port" != "$wanted $PORT" ] && ! rule_exists "$wanted" "$PORT"; then
  if [ "$wanted" = firewalld ]; then snapshot_firewalld "$PORT"; FIREWALL_DIRTY=1; fi
  ADDED_BACKEND="$wanted" ADDED_PORT="$PORT"
  change_rule "$wanted" "$PORT" add
fi
if [ -n "$old_backend" ] && [ "$old_backend $old_port" != "$wanted $PORT" ]; then
  if [ "$old_backend" = firewalld ]; then snapshot_firewalld "$old_port"; FIREWALL_DIRTY=1; fi
  REMOVED_BACKEND="$old_backend" REMOVED_PORT="$old_port"
  change_rule "$old_backend" "$old_port" remove
fi
if [ -n "$wanted" ] && { [ "$old_backend $old_port" = "$wanted $PORT" ] || [ "$ADDED_BACKEND $ADDED_PORT" = "$wanted $PORT" ]; }; then
  printf '%s %s\n' "$wanted" "$PORT" > "$OWNER"
else
  rm -f "$OWNER"
fi
