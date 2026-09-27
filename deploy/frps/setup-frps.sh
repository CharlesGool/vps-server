#!/usr/bin/env bash
# Offline frps server installation. Never downloads or changes an existing credential.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
INSTALL_LANG="${VPSSRV_DEFAULT_LANG:-en}"
case "$INSTALL_LANG" in
  zh_cn) CATALOG_LANG=zh-CN ;; zh_tw) CATALOG_LANG=zh-TW ;; zh_hk) CATALOG_LANG=zh-HK ;;
  en|hi|es|ar|fr) CATALOG_LANG="$INSTALL_LANG" ;; *) CATALOG_LANG=en ;;
esac
CATALOG_ROOT="${VPSSRV_CATALOG_ROOT:-}"
if [ -z "$CATALOG_ROOT" ]; then
  if [ -d "$SCRIPT_DIR/../../lang/frps" ]; then CATALOG_ROOT="$SCRIPT_DIR/../../lang"
  else CATALOG_ROOT="${PREFIX:-/opt/vps-server}/lang"; fi
fi
msg() {
  local key="$1"; shift
  local fmt
  # shellcheck disable=SC1090
  source "$CATALOG_ROOT/frps/$CATALOG_LANG.sh"
  printf "$fmt\n" "$@"
}
raw_msg() {
  local key="$1" fmt
  # shellcheck disable=SC1090
  source "$CATALOG_ROOT/frps/$CATALOG_LANG.sh"
  printf '%s' "$fmt"
}
[ "$(id -u)" -eq 0 ] || { msg root_required >&2; exit 1; }
# The installer copies deploy/frps/ to PREFIX/frps/ before invoking it.
# Resolve trailing slashes, '..', and symlinks in an existing install prefix.
PREFIX_DIR="$(cd "${PREFIX:-/opt/vps-server}" 2>/dev/null && pwd -P || :)"
if [ "$SCRIPT_DIR" = "$PREFIX_DIR/frps" ]; then
  BIN="$SCRIPT_DIR/../vendor/frp/frps"
else
  BIN="$SCRIPT_DIR/../../third_party/frp/frps"
fi
CONFIG=/etc/vps-server-frps/frps.toml
UNIT=/etc/systemd/system/vps-server-frps.service
EXPECTED=b95dee2bf29a021c562565cdf2116376b9fa7590361bd36ef57041a04d0e6654
[ -f "$BIN" ] && [ "$(sha256sum "$BIN" | cut -d' ' -f1)" = "$EXPECTED" ] || { msg integrity_failure >&2; exit 1; }
# Inspect existing config and every known reservation before modifying state.
STAGE="$(mktemp -d)"
chmod 0700 "$STAGE"
trap 'rm -rf -- "$STAGE"' EXIT
for key in existing_invalid existing_invalid_detail invalid_bind invalid_token reserved_check forward_check port_conflict port_unavailable; do
  export "FRPS_MSG_${key^^}=$(raw_msg "$key")"
done
PORT="$(python3 - "$CONFIG" "${FRPS_BIND_PORT:-}" "${FRPS_TOKEN:-}" "${PREFIX:-/opt/vps-server}" "$STAGE/config" <<'PY'
import json, os, pathlib, re, secrets, socket, subprocess, sys
def err(key, *args):
    message = os.environ["FRPS_MSG_" + key.upper()]
    return message % args if args else message
config, requested_port, requested_token, prefix = sys.argv[1:5]
existing = pathlib.Path(config).exists()
old = pathlib.Path(config).read_text() if existing else ''
old_port = old_token = ''
if existing:
    if not old:
        raise SystemExit(err('existing_invalid'))
    try:
        import tomllib  # Python 3.11+: parse the entire document, not selected regex lines.
    except ImportError:
        # On older supported Python, accept only the exact flat subset we write.
        # Reject unknown syntax rather than accidentally replacing credentials.
        fields = {}
        string = r'"(?:[^"\\\x00-\x1f]|\\(?:["\\btnfr]|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}))*"'
        for line in old.splitlines():
            match = re.fullmatch(r'\s*(bindAddr|bindPort|auth\.method|auth\.token)\s*=\s*(' + string + r'|[0-9]+)\s*', line)
            if not match or match[1] in fields:
                raise SystemExit(err('existing_invalid'))
            value = match[2]
            fields[match[1]] = json.loads(value) if value.startswith('"') else int(value)
        parsed = {'bindPort': fields.get('bindPort'), 'auth': {'token': fields.get('auth.token')}}
    else:
        try:
            parsed = tomllib.loads(old)
        except (ValueError, UnicodeError) as exc:
            raise SystemExit(err('existing_invalid_detail', exc))
    if not isinstance(parsed, dict) or not isinstance(parsed.get('auth'), dict):
        raise SystemExit(err('existing_invalid'))
    old_port_value = parsed.get('bindPort')
    old_token = parsed.get('auth', {}).get('token')
    if type(old_port_value) is not int or not 1 <= old_port_value <= 65535 or not isinstance(old_token, str) or not old_token or any(c in old_token for c in '\r\n') or any(0xD800 <= ord(c) <= 0xDFFF for c in old_token):
        raise SystemExit(err('existing_invalid'))
    old_port = str(old_port_value)
port = requested_port or old_port or '7000'
token = requested_token or old_token or secrets.token_urlsafe(32)
if not port.isascii() or not port.isdecimal() or not 1 <= int(port) <= 65535:
    raise SystemExit(err('invalid_bind'))
if not token or any(c in token for c in '\r\n') or any(0xD800 <= ord(c) <= 0xDFFF for c in token):
    raise SystemExit(err('invalid_token'))
port = int(port)
reserved = {80, 443, 5201}
unit = pathlib.Path('/etc/systemd/system/vps-server-web.service')
if os.environ.get('VPSSRV_CONSOLE_PORT', '').isdecimal(): reserved.add(int(os.environ['VPSSRV_CONSOLE_PORT']))
for name in ('VPSSRV_PUBLIC_HTTP_PORT', 'VPSSRV_PUBLIC_HTTPS_PORT', 'VPSSRV_IPERF_PORT'):
    if os.environ.get(name, '').isdecimal(): reserved.add(int(os.environ[name]))
if unit.exists():
    text = unit.read_text()
    for name in ('VPSSRV_PUBLIC_HTTP_PORT', 'VPSSRV_PUBLIC_HTTPS_PORT', 'VPSSRV_CONSOLE_PORT', 'VPSSRV_IPERF_PORT'):
        m = re.search(r'^Environment=' + name + r'=(\d+)$', text, re.M)
        if m: reserved.add(int(m.group(1)))
console = pathlib.Path(prefix) / 'console_port.txt'
if unit.exists():
    m = re.search(r'^Environment=VPSSRV_CONSOLE_PORT_FILE=(.+)$', unit.read_text(), re.M)
    if m: console = pathlib.Path(m.group(1))
if console.exists() and console.read_text().strip().isdecimal(): reserved.add(int(console.read_text().strip()))
for path in ('/etc/vps-server-anytls/config.json', '/etc/vps-server-proxy/config.json'):
    if pathlib.Path(path).exists():
        try:
            reserved.update(int(i['listen_port']) for i in json.loads(pathlib.Path(path).read_text()).get('inbounds', []))
        except (ValueError, KeyError, TypeError) as exc:
            raise SystemExit(err('reserved_check', path, exc))
forward = pathlib.Path(prefix) / 'data' / 'portfwd.json'
# The state location may be overridden by the web unit; inspect that too.
if unit.exists():
    m = re.search(r'^Environment=VPSSRV_DATA_DIR=(.+)$', unit.read_text(), re.M)
    if m: forward = pathlib.Path(m.group(1)) / 'portfwd.json'
if forward.exists():
    try:
        data = json.loads(forward.read_text())
        reserved.update(int(r['public_port']) for r in (data if isinstance(data, list) else data.get('rules', [])))
    except (ValueError, TypeError, KeyError) as exc:
        raise SystemExit(err('forward_check', exc))
if port in reserved:
    raise SystemExit(err('port_conflict', port))
# A service already listening on its unchanged port is safe to upgrade; all
# other listeners are rejected before any file or service is touched.
active = subprocess.run(['systemctl', 'is-active', '--quiet', 'vps-server-frps.service']).returncode == 0
if not (active and str(port) == old_port):
    for family, address in ((socket.AF_INET, '0.0.0.0'), (socket.AF_INET6, '::')):
        try:
            with socket.socket(family) as sock:
                sock.bind((address, port))
        except OSError as exc:
            if family == socket.AF_INET6 and exc.errno in (97,): continue
            raise SystemExit(err('port_unavailable', port, exc))
# Stage without changing installed files until every preflight completes.
path = pathlib.Path(sys.argv[5])
with path.open('w') as output:
    os.fchmod(output.fileno(), 0o600)
    output.write(f'bindAddr = "0.0.0.0"\nbindPort = {port}\nauth.method = "token"\nauth.token = {json.dumps(token, ensure_ascii=True)}\n')
print(port)

PY
)"
# Snapshot all three files and prior service state before the first replacement.
TARGET=/usr/local/bin/frps-vps-server
ACTIVE=0 ENABLED=0
systemctl is-active --quiet vps-server-frps.service && ACTIVE=1 || true
systemctl is-enabled --quiet vps-server-frps.service && ENABLED=1 || true
for name in config binary unit; do
  case "$name" in config) file="$CONFIG" ;; binary) file="$TARGET" ;; unit) file="$UNIT" ;; esac
  if [ -e "$file" ]; then cp -p -- "$file" "$STAGE/$name.old"; fi
done
rollback() {
  local status=$?
  trap - EXIT
  if [ "$status" -ne 0 ]; then
    local degraded=0 name file
    for name in config binary unit; do
      case "$name" in config) file="$CONFIG" ;; binary) file="$TARGET" ;; unit) file="$UNIT" ;; esac
      if [ -f "$STAGE/$name.old" ]; then
        cp -p -- "$STAGE/$name.old" "$file" || degraded=1
      else
        rm -f -- "$file" || degraded=1
      fi
    done
    systemctl daemon-reload || degraded=1
    if [ "$ENABLED" = 1 ]; then
      systemctl enable vps-server-frps.service >/dev/null || degraded=1
    elif [ -f "$STAGE/unit.old" ]; then
      systemctl disable vps-server-frps.service >/dev/null || degraded=1
    fi
    if [ "$ACTIVE" = 1 ]; then
      systemctl restart vps-server-frps.service || degraded=1
      systemctl is-active --quiet vps-server-frps.service || degraded=1
    else
      systemctl stop vps-server-frps.service || degraded=1
    fi
    if [ "$degraded" = 1 ]; then msg rollback_degraded >&2; fi
  fi
  rm -rf -- "$STAGE"
  exit "$status"
}
trap rollback EXIT
mkdir -p "$(dirname "$CONFIG")"
install -m 0600 "$STAGE/config" "$CONFIG"
install -m 0755 "$BIN" /usr/local/bin/frps-vps-server
cat > "$UNIT" <<'EOF'
[Unit]
Description=vps-server frps server
After=network.target
[Service]
Type=simple
ExecStart=/usr/local/bin/frps-vps-server -c /etc/vps-server-frps/frps.toml
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable vps-server-frps.service >/dev/null
systemctl restart vps-server-frps.service
systemctl is-active --quiet vps-server-frps.service || { msg start_failed >&2; exit 1; }
# Firewall ownership records only rules this installer actually created.
OWNER="$(dirname "$CONFIG")/firewall-owned"
old_backend="" old_port=""
if [ -f "$OWNER" ]; then read -r old_backend old_port < "$OWNER" || true; fi
backend=""
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q 'Status: active'; then
  backend=ufw
elif command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
  backend=firewalld
fi
rule_exists() {
  case "$1" in
    ufw) ufw status 2>/dev/null | grep -Eq "^${2}/tcp[[:space:]]" ;;
    firewalld) firewall-cmd --permanent --query-port="${2}/tcp" >/dev/null 2>&1 ;;
    *) return 1 ;;
  esac
}
rule_change() {
  case "$1:$3" in
    ufw:add) ufw allow "${2}/tcp" >/dev/null ;;
    ufw:remove) ufw --force delete allow "${2}/tcp" >/dev/null ;;
    firewalld:add) firewall-cmd --permanent --add-port="${2}/tcp" >/dev/null && firewall-cmd --reload >/dev/null ;;
    firewalld:remove) firewall-cmd --permanent --remove-port="${2}/tcp" >/dev/null && firewall-cmd --reload >/dev/null ;;
  esac
}
if [ "$old_backend $old_port" != "$backend $PORT" ]; then
  added=0 old_rule_present=0
  if [ -n "$old_backend" ] && rule_exists "$old_backend" "$old_port"; then old_rule_present=1; fi
  if [ -n "$backend" ] && ! rule_exists "$backend" "$PORT"; then
    if rule_change "$backend" "$PORT" add; then
      added=1
    else
      msg firewall_allow >&2
    fi
  fi
  removed=1
  if [ -n "$old_backend" ]; then
    if ! rule_change "$old_backend" "$old_port" remove; then
      removed=0
      msg firewall_remove >&2
    fi
  fi
  rollback_firewall() {
    local degraded=0
    # Restore only a rule that was present and owned before this transaction.
    if [ "$old_rule_present" = 1 ] && ! rule_exists "$old_backend" "$old_port"; then
      rule_change "$old_backend" "$old_port" add || degraded=1
    fi
    # Never delete a pre-existing rule; added tracks only our successful add.
    if [ "$added" = 1 ]; then
      rule_change "$backend" "$PORT" remove || degraded=1
    fi
    if [ "$degraded" = 1 ]; then msg firewall_rollback >&2; fi
  }
  if [ "$removed" = 1 ]; then
    # Stage the ownership update so a failed write cannot leave a partial record.
    owner_updated=0
    if [ "$added" = 1 ]; then
      if printf '%s %s\n' "$backend" "$PORT" > "$STAGE/owner.new" &&
         mv -- "$STAGE/owner.new" "$OWNER"; then owner_updated=1; fi
    elif rm -f -- "$OWNER"; then
      owner_updated=1
    fi
    if [ "$owner_updated" = 0 ]; then
      msg ownership_failed >&2
      rollback_firewall
      exit 1
    fi
  else
    rollback_firewall
  fi
fi
