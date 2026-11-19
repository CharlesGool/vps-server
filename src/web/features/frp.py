"""FRP helpers: FRPS state and meter, FRPC connection checks (the pages are the single-page UI).

Host dependencies are supplied by ``ConsoleHandler.context`` so the feature
can be reused with another application context.
"""


def _host_tool(name):
    try:
        from nft_runtime import tool
    except ImportError:
        from ..nft_runtime import tool
    return tool(name)


def frps_traffic_state(context):
    """(entry, meter ledger nodes) for the FRPS page, or None before the meter starts."""
    state = context._read_json(context.FRPS_TRAFFIC_PATH)
    if state is None:
        return None
    context.frps_meter.validate(state)
    meter = context._read_json(context.FRPS_METER_PATH) or {}
    return state["nodes"][0], meter.get("ledger", {}).get("nodes", {})


def frps_traffic_apply(context, request):
    """Send one limits edit to the privileged FRPS meter helper."""
    direct = ["/usr/bin/python3", str(context.WEB_CODE_DIR / "frps_meter.py"), "apply"]
    systemd_run = context.shutil.which("systemd-run")
    command = (["systemd-run", "--pipe", "--wait", "--collect", "--quiet",
                "--unit=vps-server-frps-traffic-edit.service", *direct] if systemd_run else direct)
    try:
        result = context.subprocess.run(command, input=context.json.dumps(request).encode("utf-8"),
                                        stdout=context.subprocess.DEVNULL, stderr=context.subprocess.DEVNULL,
                                        timeout=context.NODE_APPLY_TIMEOUT, check=False)
    except (OSError, context.subprocess.TimeoutExpired):
        print("FRPS traffic apply failed: helper unavailable or timed out", file=context.sys.stderr)
        return False
    if result.returncode:
        print(f"FRPS traffic apply failed: exit {result.returncode}", file=context.sys.stderr)
        return False
    return True


def frps_node(context, ):
    """Read-only server parameters; do not expose them outside an authenticated console."""
    try:
        text = context.FRPS_CONFIG.read_text()
        fields = dict(context.re.findall(r'^([\w.]+)\s*=\s*(.+?)\s*$', text, context.re.M))
        port = int(fields['bindPort'])
        token = context.json.loads(fields['auth.token'])
        if not 1 <= port <= 65535 or not token:
            return None
        return {'address': fields.get('bindAddr', '"0.0.0.0"').strip('"'),
                'port': port, 'token': token}
    except (OSError, ValueError, KeyError, TypeError):
        return None

def frpc_connected(context, name, server, port):
    """Check this instance's established TCP socket to its configured server."""
    try:
        pid_text = context.subprocess.run(['systemctl', 'show', '-p', 'MainPID', '--value', context.frpc_unit(name)],
                                  capture_output=True, text=True, timeout=3, check=True).stdout.strip()
        pid = int(pid_text)
        if pid <= 0 or not server or not port:
            return False
        output = context.subprocess.run([_host_tool('ss'), '-Htnp', 'state', 'established'], capture_output=True,
                                text=True, timeout=3, check=True).stdout
        destinations = {address[4][0] for address in context.socket.getaddrinfo(server, port, type=context.socket.SOCK_STREAM)}
        for line in output.splitlines():
            if f'pid={pid},' not in line:
                continue
            peer = line.split()[3].rsplit(':', 1)
            if len(peer) == 2 and peer[1] == str(port) and peer[0].strip('[]') in destinations:
                return True
    except (OSError, ValueError, IndexError, context.subprocess.SubprocessError):
        pass
    return False

def frpc_test_connection(context, name):
    """Make a separate proxy-free FRPC login using the saved server credentials."""
    if not context._frpc_probe_lock.acquire(blocking=False):
        return None
    try:
        config = context.frpc_structured(name)
        if config is None or not context.FRPC_BINARY.is_file():
            return False
        content = context.frpc_build(config['serverAddr'], config['serverPort'], config['auth']['token'], [])
        with context.tempfile.TemporaryDirectory(prefix='vps-frpc-probe-') as directory:
            path = context.Path(directory) / 'frpc.toml'
            descriptor = context.os.open(path, context.os.O_WRONLY | context.os.O_CREAT | context.os.O_EXCL, 0o600)
            with context.os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                stream.write(content)
            try:
                result = context.subprocess.run([str(context.FRPC_BINARY), '-c', str(path)],
                                        stdout=context.subprocess.PIPE, stderr=context.subprocess.STDOUT,
                                        timeout=7, check=False)
                output = result.stdout or b''
            except context.subprocess.TimeoutExpired as exc:
                output = exc.stdout or b''
        return b'login to server success' in output
    except (OSError, ValueError, KeyError, TypeError, context.subprocess.SubprocessError):
        return False
    finally:
        context._frpc_probe_lock.release()
