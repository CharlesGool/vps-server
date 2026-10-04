"""Proxy and AnyTLS service operations with an injected host context."""


def _cert_common_name(context, path):
    """Read the node's requested server name from SAN, then legacy CN."""
    if not path:
        return ""
    try:
        from ssl import _ssl
        decoded = _ssl._test_decode_cert(path)
        sans = decoded.get("subjectAltName") or ()
        if sans:
            return sans[0][1]
        return next(value for group in decoded.get("subject", ()) for name, value in group if name == "commonName")
    except (OSError, ValueError, StopIteration):
        return ""

def anytls_installed(context, ):
    """Whether the unified proxy configuration contains an AnyTLS inbound."""
    return anytls_node(context) is not None

def anytls_node(context, ):
    """The installed node's parameters, or None if the module is not installed."""
    try:
        config = context.json.loads(context.PROXY_CONFIG.read_text())
    except (OSError, ValueError):
        return None
    for inbound in config.get("inbounds", []):
        if inbound.get("type") != "anytls":
            continue
        users = inbound.get("users") or [{}]
        tls = inbound.get("tls") or {}
        return {
            "port": inbound.get("listen_port", ""),
            "password": users[0].get("password", ""),
            "sni": context._cert_common_name(tls.get("certificate_path", "")),
            "running": context._run_quiet(["systemctl", "is-active", "--quiet", context.PROXY_SERVICE]),
        }
    return None

def anytls_clash_line(context, node, host, name):
    """One Clash proxy entry. Same shape setup-anytls.sh prints, so a config
    assembled from either source looks the same.
    """
    return (
        f'- {{ name: {name}, type: anytls, server: {host}, port: {node["port"]}, '
        f'password: {context.json.dumps(node["password"])}, sni: {context.json.dumps(node["sni"])}, '
        f'skip-cert-verify: true, udp: true }}'
    )

def anytls_share_link(context, node, host, name):
    return (
        f'anytls://{context.quote(node["password"], safe="")}@{host}:{node["port"]}'
        f'?insecure=1&sni={node["sni"]}#{context.quote(name, safe="")}'
    )

def local_addresses(context, ):
    """[(interface, address)] for real interfaces.

    Read from the kernel's own list without an outbound request.
    """
    found = []
    output = context._cmd_output(["ip", "-o", "-4", "addr", "show", "scope", "global"])
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        iface, cidr = parts[1], parts[3]
        if iface.startswith(context.VIRTUAL_IFACE_PREFIXES) or iface.startswith("tailscale"):
            continue
        found.append((iface, cidr.split("/")[0]))
    return found

def tailscale_address(context, ):
    for line in context._cmd_output(["ip", "-o", "-4", "addr", "show", "tailscale0"]).splitlines():
        parts = line.split()
        if len(parts) >= 4:
            return parts[3].split("/")[0]
    return ""

def address_entries(context, t):
    """Show host interface addresses and the optional Tailscale address."""
    entries = []
    seen = set()
    for iface, address in context.local_addresses():
        if address in seen:
            continue
        entries.append((t["anytls_lan"].format(iface=iface), address))
        seen.add(address)
    tailscale = context.tailscale_address()
    if tailscale and tailscale not in seen:
        entries.append(("Tailscale", tailscale))
        seen.add(tailscale)
    return entries

def node_csrf_token(context, session, protocol):
    return context.hmac.new(context.SESSION_SECRET.encode(),
                    f"node-apply:{session}:{protocol}".encode(), "sha256").hexdigest()

def node_control_apply(context, request):
    """Send one ID-based edit to the privileged transactional helper."""
    if not context.NODE_CONTROL_HELPER.is_file():
        return False
    direct = ["/usr/bin/python3", str(context.NODE_CONTROL_HELPER), "apply"]
    systemd_run = context.shutil.which("systemd-run")
    if not systemd_run and context.Path("/run/systemd/system").exists():
        return False
    command = (["systemd-run", "--pipe", "--wait", "--collect",
                f"--setenv=VPSSRV_DATA_DIR={context.DATA_DIR}",
                f"--setenv=VPSSRV_IPERF_PORT={context.IPERF_PORT}",
                f"--unit={context.NODE_CONTROL_UNIT}", *direct]
               if systemd_run else direct)
    try:
        result = context.subprocess.run(command, input=context.json.dumps(request).encode("utf-8"),
                                stdout=context.subprocess.DEVNULL, stderr=context.subprocess.DEVNULL,
                                timeout=context.NODE_APPLY_TIMEOUT, check=False)
    except context.subprocess.TimeoutExpired:
        if systemd_run:
            context._run_quiet(["systemctl", "stop", context.NODE_CONTROL_UNIT])
        print("node control apply failed: timeout", file=context.sys.stderr)
        return False
    except OSError:
        print("node control apply failed: helper unavailable", file=context.sys.stderr)
        return False
    if result.returncode:
        action = request.get("action") if isinstance(request, dict) else None
        action = action if action in ("create", "delete", "toggle", "edit", "reset", "iperf-port") else "unknown"
        print(f"node control {action} failed: exit {result.returncode}", file=context.sys.stderr)
        return False
    return True

def proxy_installed(context, ):
    """Cheap check for the nav and the dashboard tile — no parsing, no subprocess."""
    return context.PROXY_CONFIG.is_file()

def proxy_nodes(context, ):
    """[{type, port, secret}] for every installed protocol, in display order.

    `secret` is the uuid for vmess/vless or the password for trojan/
    shadowsocks — one field name regardless of protocol, since exactly one of
    "the identifier IS the credential" is true for all four and the caller
    (page_proxy) already knows which is which from `type`.
    """
    try:
        config = context.json.loads(context.PROXY_CONFIG.read_text())
    except (OSError, ValueError):
        return []
    nodes = []
    for inbound in config.get("inbounds", []):
        proto = inbound.get("type")
        if proto not in context.PROXY_PROTOCOL_ORDER:
            continue
        users = inbound.get("users") or [{}]
        user0 = users[0]
        if proto in ("vmess", "vless"):
            secret = user0.get("uuid", "")
        elif proto == "trojan":
            secret = user0.get("password", "")
        else:  # shadowsocks: password sits on the inbound itself, not a user
            secret = inbound.get("password", "")
        tls = inbound.get("tls") or {}
        nodes.append({"type": proto, "port": inbound.get("listen_port", ""),
                      "secret": secret,
                      "sni": context._cert_common_name(tls.get("certificate_path", ""))
                      if proto != "shadowsocks" else ""})
    order = {p: i for i, p in enumerate(context.PROXY_PROTOCOL_ORDER)}
    nodes.sort(key=lambda n: order.get(n["type"], len(context.PROXY_PROTOCOL_ORDER)))
    return nodes

def proxy_running(context, ):
    return context._run_quiet(["systemctl", "is-active", "--quiet", context.PROXY_SERVICE])

def proxy_clash_line(context, node, sni, host, name):
    proto, port, secret = node["type"], node["port"], node["secret"]
    if proto == "vmess":
        return (f'- {{ name: {name}, type: vmess, server: {host}, port: {port}, '
                f'uuid: {secret}, alterId: 0, cipher: auto, tls: true, '
                f'skip-cert-verify: true, servername: {context.json.dumps(sni)}, udp: true }}')
    if proto == "vless":
        return (f'- {{ name: {name}, type: vless, server: {host}, port: {port}, '
                f'uuid: {secret}, network: tcp, tls: true, skip-cert-verify: true, '
                f'servername: {context.json.dumps(sni)}, udp: true }}')
    if proto == "trojan":
        return (f'- {{ name: {name}, type: trojan, server: {host}, port: {port}, '
                f'password: {context.json.dumps(secret)}, sni: {context.json.dumps(sni)}, skip-cert-verify: true, udp: true }}')
    return (f'- {{ name: {name}, type: ss, server: {host}, port: {port}, '
            f'cipher: 2022-blake3-aes-128-gcm, password: {context.json.dumps(secret)}, udp: true }}')

def clash_share_token(context, node):
    """A capability URL changes when this node's connection details change."""
    material = context.json.dumps({"id": node["id"], "name": node["name"],
                           "inbound": node["inbound"]}, sort_keys=True,
                          separators=(",", ":")).encode()
    return context.hmac.new(context.SESSION_SECRET.encode(), b"clash-profile-v1:" + material,
                    "sha256").hexdigest()

def clash_lan_host(context, host):
    """Use a real private IPv4 address for same-LAN import links."""
    addresses = [address for _, address in context.local_addresses()]
    if host in addresses and context.is_lan_address(host):
        return host
    for address in addresses:
        if context.is_lan_address(address):
            return address
    return None

def is_lan_address(context, value):
    try:
        address = context.ipaddress.ip_address(value)
    except ValueError:
        return False
    return address.version == 4 and any(address in network for network in (
        context.ipaddress.ip_network("10.0.0.0/8"),
        context.ipaddress.ip_network("172.16.0.0/12"),
        context.ipaddress.ip_network("192.168.0.0/16")))

def clash_profile(context, node, host):
    """A complete single-node Mihomo profile, not just a proxy YAML entry."""
    inbound, protocol = node["inbound"], node["protocol"]
    name = context.json.dumps(node["name"], ensure_ascii=False)
    if protocol == "anytls":
        line = context.anytls_clash_line({"port": node["port"],
                                 "password": inbound["users"][0]["password"],
                                 "sni": context._cert_common_name(inbound["tls"]["certificate_path"])},
                                host, name)
    else:
        secret = (inbound["password"] if protocol == "shadowsocks" else
                  inbound["users"][0]["uuid" if protocol in ("vmess", "vless")
                                       else "password"])
        sni = ("" if protocol == "shadowsocks" else
               context._cert_common_name(inbound["tls"]["certificate_path"]))
        line = context.proxy_clash_line({"type": protocol, "port": node["port"],
                                 "secret": secret}, sni, host, name)
    return ("mixed-port: 7890\nallow-lan: false\nmode: rule\nlog-level: warning\n"
            f"proxies:\n  {line}\n"
            "proxy-groups:\n  - name: NODE\n    type: select\n    proxies:\n"
            f"      - {name}\n      - DIRECT\n"
            "rules:\n  - MATCH,NODE\n")

def proxy_share_link(context, node, sni, host, name):
    proto, port, secret = node["type"], node["port"], node["secret"]
    if proto == "vmess":
        payload = {
            "v": "2", "ps": name, "add": host, "port": str(port), "id": secret,
            "aid": "0", "net": "tcp", "type": "none", "host": "", "path": "",
            "tls": "tls", "sni": sni, "scy": "auto",
        }
        blob = context.base64.b64encode(context.json.dumps(payload).encode()).decode()
        return f"vmess://{blob}"
    if proto == "vless":
        return (f'vless://{secret}@{host}:{port}?encryption=none&security=tls'
                f'&sni={context.quote(sni, safe="")}&allowInsecure=1&type=tcp#{context.quote(name, safe="")}')
    if proto == "trojan":
        return (f'trojan://{context.quote(secret, safe="")}@{host}:{port}'
                f'?sni={context.quote(sni, safe="")}&allowInsecure=1#{context.quote(name, safe="")}')
    blob = context.base64.b64encode(f"2022-blake3-aes-128-gcm:{secret}".encode()).decode()
    return f"ss://{blob}@{host}:{port}#{context.quote(name, safe='')}"
