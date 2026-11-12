#!/usr/bin/env python3
"""Domain forwarding: subdomain -> local port through Caddy, DNS on Cloudflare.

Caddy owns ports 80 and 443 while this module is on. Each site forwards one
host name to 127.0.0.1:<port> (typically an frps or frpc listener) and gets
its certificate from Caddy's automatic HTTPS (HTTP-01 or TLS-ALPN-01). The
console keeps an A record, and an AAAA record when the host has a public
IPv6 address, for every site on Cloudflare, "DNS only", pointing at this
host's own public address. Nothing asks an outside service for that address.

A site whose port is the console's own port puts the console behind Caddy:
Caddy asks for a client certificate signed by the console's client CA,
connects to the console over loopback TLS and passes the certificate serial
and the visitor's address in headers, with a secret from proxy-key. The
console trusts those headers only on loopback with that secret, and still
decides revocation and whether a certificate is required.

Files (all root-owned):
    /etc/vps-server-caddy/sites.json        sites                       0600
    /etc/vps-server-caddy/cloudflare-tokens.json  Cloudflare API tokens, each
                                            with the zones it can see   0600
    /etc/vps-server-caddy/dns.json          last DNS sync result        0600
    /etc/vps-server-caddy/caddy.json        generated Caddy config      0640 root:vps-server-caddy
    /etc/vps-server-caddy/proxy-key         console proxy secret        0600
    /etc/vps-server-caddy/client-ca.pem     copy of the console client CA 0640 root:vps-server-caddy
    /var/lib/vps-server-caddy               Caddy certificates and ACME accounts

    caddy_sites.py apply    one request as JSON on stdin (root)
    caddy_sites.py render   write caddy.json from sites.json (root)
    caddy_sites.py ddns     update every site's DNS records (root, timer)
"""

import fcntl
import ssl
from datetime import datetime, timezone
import grp
import secrets
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("VPSSRV_CADDY_DIR", "/etc/vps-server-caddy"))
SITES_PATH = CONFIG_DIR / "sites.json"
TOKENS_PATH = CONFIG_DIR / "cloudflare-tokens.json"
# Before several tokens: one token file and the zones it could see.
LEGACY_TOKEN_PATH = CONFIG_DIR / "cloudflare-token"
LEGACY_ZONES_PATH = CONFIG_DIR / "zones.json"
MAX_TOKENS = 20
DNS_PATH = CONFIG_DIR / "dns.json"
HISTORY_PATH = CONFIG_DIR / "dns-history.jsonl"
ALERTED_PATH = CONFIG_DIR / "alerts-sent.json"
HISTORY_LIMIT = 200
CADDY_CONFIG = CONFIG_DIR / "caddy.json"
LOCK_PATH = CONFIG_DIR / "sites.lock"
PROXY_KEY_PATH = CONFIG_DIR / "proxy-key"
CLIENT_CA_COPY = CONFIG_DIR / "client-ca.pem"
DOMAINS_FLAG = CONFIG_DIR / "domains-enabled"
DATA_DIR = Path(os.environ.get("VPSSRV_CADDY_DATA", "/var/lib/vps-server-caddy"))
ACCESS_LOG = DATA_DIR / "logs" / "access.log"
ADMIN_SOCKET = "/run/vps-server-caddy/admin.sock"
SERVICE = "vps-server-caddy.service"
GROUP = "vps-server-caddy"
CF_API = "https://api.cloudflare.com/client/v4"
MAX_SITES = 64
HOST_RE = re.compile(r"(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,61}[a-z0-9]")
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{20,100}")


class SiteError(ValueError):
    """A request the console should show back to the operator (code is a lang key suffix)."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


# -- state ------------------------------------------------------------------

def _write(path, text, mode=0o600, group=None):
    temp = path.with_name(path.name + ".tmp")
    with open(temp, "w", encoding="utf-8") as handle:
        os.fchmod(handle.fileno(), mode)
        if group is not None:
            os.fchown(handle.fileno(), 0, group)
        handle.write(text)
    os.replace(temp, path)


def read_sites(path=SITES_PATH):
    try:
        data = json.loads(Path(path).read_text())
    except FileNotFoundError:
        return []
    sites = data.get("sites") if isinstance(data, dict) else None
    if not isinstance(sites, list):
        raise ValueError("invalid sites.json")
    return [site for site in sites if isinstance(site, dict)
            and (valid_host(site.get("host")) and (valid_port(site.get("port")) or site.get("console") is True)
                 or site.get("ip") is True and site.get("console") is True and valid_ip(site.get("host")))]


def write_sites(sites, path=SITES_PATH):
    _write(Path(path), json.dumps({"sites": sites}, indent=2) + "\n")


def domains_enabled():
    """Domain forwarding's own switch. Caddy also runs for the IP certificate alone."""
    try:
        return DOMAINS_FLAG.read_text().strip() == "1"
    except OSError:
        # Before the switch existed, an enabled Caddy meant domain forwarding was on.
        return subprocess.run(["systemctl", "is-enabled", "--quiet", SERVICE], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, check=False).returncode == 0


def set_domains_enabled(enabled):
    _write(DOMAINS_FLAG, "1\n" if enabled else "0\n")


def ip_enabled(sites=None):
    if sites is None:
        try:
            sites = read_sites()
        except (OSError, ValueError):
            return False
    return any(site.get("ip") and site.get("enabled", True) for site in sites)


def active_sites(sites):
    """The sites Caddy serves: domain sites only while domain forwarding is on."""
    return sites if domains_enabled() else [site for site in sites if site.get("ip")]


def token_id(token):
    """A short stable id for a token, so pages and requests never carry the token."""
    import hashlib
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


def read_tokens():
    """Cloudflare tokens: [{"id", "token", "name", "zones", "checked_at"?, "error"?}].

    Reads the single token of earlier versions when the list does not exist yet;
    the first change writes the list and removes the old files.
    """
    try:
        data = json.loads(TOKENS_PATH.read_text())
        items = data.get("tokens", []) if isinstance(data, dict) else []
    except FileNotFoundError:
        try:
            token = LEGACY_TOKEN_PATH.read_text().strip()
        except OSError:
            return []
        if not TOKEN_RE.fullmatch(token):
            return []
        try:
            legacy = json.loads(LEGACY_ZONES_PATH.read_text())
        except (OSError, ValueError):
            legacy = {}
        legacy = legacy if isinstance(legacy, dict) else {}
        items = [{"token": token, "name": "", "zones": legacy.get("zones", []),
                  **({"checked_at": legacy["checked_at"]} if "checked_at" in legacy else {})}]
    except (OSError, ValueError):
        return []
    tokens = []
    for item in items:
        if not isinstance(item, dict) or not TOKEN_RE.fullmatch(str(item.get("token", ""))):
            continue
        zones = item.get("zones") if isinstance(item.get("zones"), list) else []
        tokens.append({**item, "id": token_id(item["token"]), "name": str(item.get("name") or "")[:40],
                       "zones": sorted({zone for zone in zones if valid_host(zone)})})
    return tokens


def write_tokens(tokens):
    _write(TOKENS_PATH, json.dumps({"tokens": [{k: v for k, v in item.items() if k != "id"}
                                               for item in tokens]}) + "\n")
    LEGACY_TOKEN_PATH.unlink(missing_ok=True)
    LEGACY_ZONES_PATH.unlink(missing_ok=True)


def read_dns(path=DNS_PATH):
    try:
        data = json.loads(Path(path).read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def valid_host(host):
    return isinstance(host, str) and HOST_RE.fullmatch(host) is not None


def valid_ip(host):
    """A public IPv4 address: an IP site serves the console by address."""
    try:
        address = ipaddress.ip_address(host)
    except (TypeError, ValueError):
        return False
    return address.version == 4 and address.is_global


def valid_port(port):
    return type(port) is int and 1 <= port <= 65535


def normalize_host(raw):
    host = str(raw or "").strip().lower().rstrip(".")
    try:
        host = host.encode("idna").decode("ascii") if not host.isascii() else host
    except UnicodeError as exc:
        raise SiteError("host_invalid") from exc
    if not valid_host(host):
        raise SiteError("host_invalid")
    return host


# -- console ----------------------------------------------------------------

def console_port():
    """The console's current port, or None."""
    try:
        from state_paths import console_port_file
        value = console_port_file().read_text().strip()
        return int(value) if value.isascii() and value.isdecimal() and 1 <= int(value) <= 65535 else None
    except (ImportError, OSError, ValueError):
        return None


def console_client_ca():
    try:
        from state_paths import cert_dir
        return cert_dir() / "client-ca.pem"
    except (ImportError, OSError, ValueError):
        return None


def proxy_key():
    """The secret Caddy shows the console; created on first use."""
    try:
        key = PROXY_KEY_PATH.read_text().strip()
        if len(key) >= 32:
            return key
    except FileNotFoundError:
        pass
    key = secrets.token_urlsafe(32)
    _write(PROXY_KEY_PATH, key + "\n")
    return key


MAX_ALIASES = 8
MAX_ALLOW = 32
AUTH_USER_RE = re.compile(r"[A-Za-z0-9._-]{1,64}")


def names(site):
    """Every host name a site answers: its own and its extra names."""
    return [site["host"], *[alias for alias in site.get("aliases", []) if valid_host(alias)]]


def _guarded(site, route):
    """Wrap a site's route with its access rules: allowed addresses first,
    then a password (never on the console, which has its own login)."""
    routes = []
    allow = [entry for entry in site.get("allow_ips", []) if isinstance(entry, str)]
    if allow:
        routes.append({"match": [{"host": names(site), "not": [{"remote_ip": {"ranges": allow}}]}],
                       "handle": [{"handler": "static_response", "status_code": 403, "body": "Forbidden"}],
                       "terminal": True})
    auth = site.get("auth")
    if isinstance(auth, dict) and auth.get("user") and auth.get("hash") and not site.get("console"):
        route["handle"].insert(0, {"handler": "authentication", "providers": {"http_basic": {
            "accounts": [{"username": auth["user"], "password": auth["hash"]}],
            "hash": {"algorithm": "bcrypt"}, "hash_cache": {}, "realm": site["host"]}}})
    return routes + [route]


def hash_password(password):
    """bcrypt hash from Caddy itself; the password goes through stdin only."""
    result = subprocess.run(["/usr/local/bin/caddy-vps-server", "hash-password"], input=password + "\n",
                            capture_output=True, text=True, timeout=60, check=False)
    value = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    if result.returncode or not value.startswith("$2"):
        raise RuntimeError("cannot hash the password")
    return value


def _console_route(site, port, key):
    return {"match": [{"host": names(site)}],
            "handle": [{"handler": "reverse_proxy",
                        # Overwrite whatever the visitor sent under these names.
                        "headers": {"request": {"set": {
                            "X-Vps-Server-Proxy": [key],
                            "X-Vps-Server-Client-Serial": ["{http.request.tls.client.serial}"],
                            "X-Vps-Server-Client-IP": ["{http.request.remote.host}"]}}},
                        # The console's own certificate is self-signed; this hop stays on loopback.
                        "transport": {"protocol": "http", "tls": {"insecure_skip_verify": True}},
                        "upstreams": [{"dial": f"127.0.0.1:{port}"}]}],
            "terminal": True}


# -- Caddy ------------------------------------------------------------------

def _catalog(tag):
    try:
        return json.loads((Path(__file__).resolve().parents[2] / "lang" / "web" / f"{tag}.json").read_text())
    except (OSError, ValueError):
        return {}


def probe_switches():
    """(http, https): the public reachability page switches from the console's settings."""
    try:
        from module_manager import public_listener_enabled
    except ImportError:
        return False, False
    try:
        prefix = Path(__file__).resolve().parents[2]
        default = _public_default()
        return (public_listener_enabled(prefix, "web_http", default, own_setting=True),
                public_listener_enabled(prefix, "web_https", default, own_setting=True))
    except (OSError, ValueError):
        return False, False


def _public_default():
    """VPSSRV_PUBLIC_ENABLE as the console sees it: its unit first, then the state .env."""
    try:
        unit = Path("/etc/systemd/system/vps-server-web.service").read_text()
        match = re.search(r"^Environment=VPSSRV_PUBLIC_ENABLE=(\S*)$", unit, re.M)
        if match:
            return match[1] == "1"
    except OSError:
        pass
    try:
        from state_paths import state_dir
        for line in (state_dir() / ".env").read_text().splitlines():
            key, _, value = line.strip().partition("=")
            if key.strip() == "VPSSRV_PUBLIC_ENABLE":
                return value.strip() == "1"
    except (ImportError, OSError, ValueError):
        pass
    return True


def probe_handler():
    """The public reachability page, answered by Caddy while it holds 80/443.

    The same one line as the console's own page: the address the server sees,
    in the visitor's first Accept-Language. The console is not involved.
    """
    routes = []
    for tag, pattern in (("zh-CN", "(?i)^\\s*zh"), ("es", "(?i)^\\s*es"), ("en", None)):
        label = _catalog(tag).get("probe_your_ip", "The server sees your IP address")
        sep = "\uff1a" if tag == "zh-CN" else ": "
        route = {"handle": [{"handler": "static_response", "status_code": 200,
                             "body": f"{label}{sep}{{http.request.remote.host}}\n"}]}
        if pattern:
            route["match"] = [{"header_regexp": {"Accept-Language": {"pattern": pattern}}}]
        routes.append(route)
    headers = {"handler": "headers", "response": {
        "set": {"Content-Type": ["text/plain; charset=utf-8"], "Cache-Control": ["no-store"],
                "X-Content-Type-Options": ["nosniff"], "Referrer-Policy": ["no-referrer"]},
        "delete": ["Server"]}}
    return {"handle": [{"handler": "subroute", "routes": [
        {"match": [{"path": ["/"]}], "handle": [headers, {"handler": "subroute", "routes": routes}],
         "terminal": True},
        {"handle": [headers, {"handler": "static_response", "status_code": 404, "body": "not found\n"}]}]}],
        "terminal": True}


def caddy_config(sites, *, console=None, key="", client_ca=None, probe=(False, False)):
    """Caddy's native JSON: one route per host, everything else is dropped.

    console is the console's port; sites marked "console" forward there.
    client_ca, when given, is the PEM file Caddy checks client certificates
    against for those sites.
    """
    abort = {"handle": [{"handler": "static_response", "abort": True}]}
    routes = []
    console_hosts = []
    sites = [site for site in sites if site.get("enabled", True)]
    for site in sites:
        if site.get("ip"):
            continue  # Only its certificate is wanted, for the console's own port.
        if site.get("console"):
            if console is None or not key:
                continue  # No console to reach: leave the name unanswered.
            routes += _guarded(site, _console_route(site, console, key))
            console_hosts += names(site)
        else:
            proxy = {"handler": "reverse_proxy", "upstreams": [{"dial": f"127.0.0.1:{site['port']}"}]}
            if site.get("backend_tls"):
                # A local HTTPS backend (a NAS, a router) usually has a self-signed certificate.
                proxy["transport"] = {"protocol": "http", "tls": {"insecure_skip_verify": True}}
            # Caddy keeps the visitor's Host for HTTP backends but sends the
            # backend's own address to HTTPS ones; make the choice explicit.
            if site.get("upstream_host"):
                proxy["headers"] = {"request": {"set": {"Host": ["{http.reverse_proxy.upstream.hostport}"]}}}
            elif site.get("backend_tls"):
                proxy["headers"] = {"request": {"set": {"Host": ["{http.request.hostport}"]}}}
            routes += _guarded(site, {"match": [{"host": names(site)}], "handle": [proxy], "terminal": True})
    # Access log for every site, read back by the console page.
    ip_hosts = [site["host"] for site in sites if site.get("ip")]
    # The reachability page: any name on 80, and the bare address on 443 when
    # it has its certificate (a client without SNI gets that one).
    probe_https = [{**probe_handler(), "match": [{"host": ip_hosts}]}] if probe[1] and ip_hosts else []
    https = {"listen": [":443"], "routes": routes + probe_https + [abort], "logs": {}}
    client_auth = ({"ca": {"provider": "file", "pem_files": [str(client_ca)]}, "mode": "verify_if_given"}
                   if client_ca else None)
    policies = []
    if console_hosts and client_auth:
        # Ask for a certificate; whether one is required stays the console's call.
        policies += [{"match": {"sni": console_hosts}, "client_authentication": client_auth}, {}]
    if policies:
        https["tls_connection_policies"] = policies
    if probe_https:
        # A browser sends no SNI for an address, so Caddy's strict SNI check
        # (on by default once any policy asks for client certificates) would
        # answer 421. Turning it off is safe here: only the console's names
        # ask for certificates, and the console itself decides per request
        # whether one is required, so a mismatched SNI gains nothing.
        https["strict_sni_host"] = False
    domain_names = [name for site in sites if not site.get("ip") for name in names(site)]
    http_routes = [abort]
    if probe[0]:
        # The page must answer plain HTTP: redirecting would hide whether 80
        # itself is reachable. Domain names keep their redirect, made here.
        https["automatic_https"] = {"disable_redirects": True}
        http_routes = ([{"match": [{"host": domain_names}], "handle": [{
            "handler": "static_response", "status_code": 308,
            "headers": {"Location": ["https://{http.request.host}{http.request.uri}"]}}], "terminal": True}]
            if domain_names else []) + [probe_handler()]
    apps = {"http": {"servers": {
        # Automatic HTTPS adds the HTTP-to-HTTPS redirects and the ACME
        # HTTP challenge to the :80 server; any other host gets nothing.
        "https": https,
        "http": {"listen": [":80"], "routes": http_routes},
    }}}
    if ip_hosts:
        # The address gets a certificate but no site: the console serves it on
        # its own port, and 80/443 answer nothing for the bare address. Let's
        # Encrypt issues address certificates only on its six-day profile.
        apps["tls"] = {"certificates": {"automate": ip_hosts},
                       "automation": {"policies": [
                           {"subjects": ip_hosts, "issuers": [{"module": "acme", "profile": "shortlived"}]}]}}
    return {
        "logging": {"logs": {
            "default": {"exclude": ["http.log.access"]},
            "access": {"include": ["http.log.access"], "encoder": {"format": "json"},
                       "writer": {"output": "file", "filename": str(ACCESS_LOG),
                                  "roll_size_mb": 5, "roll_keep": 2}}}},
        "admin": {"listen": "unix/" + ADMIN_SOCKET},
        "storage": {"module": "file_system", "root": str(DATA_DIR)},
        "apps": apps,
    }


def render(sites=None):
    """Write caddy.json (and the client CA copy); True when either changed."""
    sites = active_sites(read_sites() if sites is None else sites)
    try:
        group = grp.getgrnam(GROUP).gr_gid
    except KeyError:
        group = None
    mode = 0o640 if group is not None else 0o600
    changed = False
    client_ca = None
    has_console = any(site.get("console") for site in sites)
    if has_console:
        source = console_client_ca()
        try:
            pem = source.read_text() if source else ""
        except OSError:
            pem = ""
        if pem:
            try:
                current = CLIENT_CA_COPY.read_text()
            except OSError:
                current = None
            if current != pem:
                _write(CLIENT_CA_COPY, pem, mode, group)
                changed = True
            client_ca = CLIENT_CA_COPY
    text = json.dumps(caddy_config(sites, console=console_port() if has_console else None,
                                   key=proxy_key() if has_console else "", client_ca=client_ca,
                                   probe=probe_switches()),
                      indent=2) + "\n"
    try:
        current = CADDY_CONFIG.read_text()
    except OSError:
        current = None
    if current != text:
        _write(CADDY_CONFIG, text, mode, group)
        changed = True
    return changed


def reload_caddy():
    """Apply caddy.json to a running Caddy; a stopped one reads it at start."""
    if subprocess.run(["systemctl", "is-active", "--quiet", SERVICE], check=False).returncode:
        return
    result = subprocess.run(["systemctl", "reload", SERVICE], capture_output=True, text=True,
                            timeout=60, check=False)
    if result.returncode:
        raise RuntimeError("Caddy rejected the configuration")


# -- addresses --------------------------------------------------------------

def public_address(family):
    """This host's own public address of a family, or None.

    A UDP connect sends nothing; it only asks the kernel which local address
    routes to the outside. Behind NAT that is a private address, and the
    host has no public address of its own to publish.
    """
    target = ("1.1.1.1", 53) if family == socket.AF_INET else ("2606:4700:4700::1111", 53)
    try:
        with socket.socket(family, socket.SOCK_DGRAM) as sock:
            sock.connect(target)
            address = ipaddress.ip_address(sock.getsockname()[0])
    except OSError:
        return None
    return str(address) if address.is_global else None


# -- Cloudflare -------------------------------------------------------------

class CloudflareError(RuntimeError):
    def __init__(self, code, detail=""):
        self.code = code
        super().__init__(detail or code)


def _cf(token, method, path, body=None, opener=None):
    request = urllib.request.Request(
        CF_API + path, method=method,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                 "User-Agent": "vps-server"})
    try:
        with (opener or urllib.request.urlopen)(request, timeout=20) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read())
        except ValueError:
            data = {}
        if exc.code in (401, 403):
            raise CloudflareError("dns_auth") from exc
        if not data:
            raise CloudflareError("dns_api", f"HTTP {exc.code}") from exc
    except (OSError, ValueError) as exc:
        raise CloudflareError("dns_unreachable", type(exc).__name__) from exc
    if not data.get("success"):
        messages = "; ".join(str(item.get("message", "")) for item in data.get("errors", []))
        raise CloudflareError("dns_api", messages[:200])
    return data.get("result")


def find_zone(token, host, opener=None):
    """The Cloudflare zone holding host: the longest suffix the token can see."""
    labels = host.split(".")
    for start in range(len(labels) - 1):
        name = ".".join(labels[start:])
        zones = _cf(token, "GET", "/zones?name=" + name, opener=opener)
        if zones:
            return zones[0]["id"]
    raise CloudflareError("dns_zone")


def sync_record(token, zone, host, kind, address, opener=None):
    """Make host's records of one type exactly one pointing at address."""
    records = _cf(token, "GET", f"/zones/{zone}/dns_records?type={kind}&name={host}", opener=opener) or []
    if address is None:
        for record in records:
            _cf(token, "DELETE", f"/zones/{zone}/dns_records/{record['id']}", opener=opener)
        return "removed" if records else "none"
    body = {"type": kind, "name": host, "content": address, "ttl": 1, "proxied": False}
    if not records:
        _cf(token, "POST", f"/zones/{zone}/dns_records", body, opener=opener)
        return "created"
    first, rest = records[0], records[1:]
    for record in rest:
        _cf(token, "DELETE", f"/zones/{zone}/dns_records/{record['id']}", opener=opener)
    if first.get("content") == address and first.get("proxied") is False and not rest:
        return "unchanged"
    _cf(token, "PATCH", f"/zones/{zone}/dns_records/{first['id']}",
        {"content": address, "proxied": False, "ttl": 1}, opener=opener)
    return "updated"


def list_zones(token, opener=None):
    """Names of the zones the token can see, for picking a main domain."""
    zones = _cf(token, "GET", "/zones?per_page=50", opener=opener) or []
    return sorted({zone["name"] for zone in zones if isinstance(zone.get("name"), str) and valid_host(zone["name"])})


def refresh_zones(item):
    """Read the zones one token can see now; keeps the last list when Cloudflare is unreachable."""
    try:
        item.update({"zones": list_zones(item["token"]), "checked_at": int(time.time())})
        item.pop("error", None)
    except CloudflareError as exc:
        if exc.code == "dns_auth":
            item.update({"zones": [], "checked_at": int(time.time())})
        item["error"] = exc.code
    return item


def save_zones():
    tokens = read_tokens()
    if tokens:
        write_tokens([refresh_zones(item) for item in tokens])


def read_zones():
    """Every main domain some token can manage."""
    return sorted({zone for item in read_tokens() for zone in item["zones"]})


def zone_of(host, zones):
    """The longest known zone host belongs to, or None."""
    matches = [zone for zone in zones if host == zone or host.endswith("." + zone)]
    return max(matches, key=len) if matches else None


def locate(tokens, host, opener=None):
    """(token, zone id) for host: first the token known to see its main domain, then the others."""
    best = zone_of(host, [zone for item in tokens for zone in item["zones"]])
    ordered = sorted(tokens, key=lambda item: best not in item["zones"])
    error = CloudflareError("dns_zone")
    for item in ordered:
        try:
            return item["token"], find_zone(item["token"], host, opener=opener)
        except CloudflareError as exc:
            # A token that cannot reach this domain says nothing about the next one.
            error = exc if error.code == "dns_zone" else error
    raise error


def remove_records(tokens, host, opener=None):
    token, zone = locate(tokens, host, opener=opener)
    for kind in ("A", "AAAA"):
        sync_record(token, zone, host, kind, None, opener=opener)


def sync_dns(sites, tokens, *, addresses=None, opener=None):
    """Point every site at this host. Returns the dns.json document."""
    ipv4, ipv6 = addresses if addresses is not None else (
        public_address(socket.AF_INET), public_address(socket.AF_INET6))
    result = {"checked_at": int(time.time()), "ipv4": ipv4, "ipv6": ipv6, "sites": {}}
    if not tokens:
        result["error"] = "dns_no_token"
        return result
    if ipv4 is None and ipv6 is None:
        result["error"] = "dns_no_address"
        return result
    for host in [name for site in sites if not site.get("ip") for name in names(site)]:
        try:
            token, zone = locate(tokens, host, opener=opener)
            states = [sync_record(token, zone, host, "A", ipv4, opener=opener),
                      sync_record(token, zone, host, "AAAA", ipv6, opener=opener)]
            for kind, state, value in (("A", states[0], ipv4), ("AAAA", states[1], ipv6)):
                if state in ("created", "updated", "removed"):
                    result.setdefault("events", []).append(
                        {"event": "record_" + state, "host": host, "kind": kind, "value": value or ""})
            result["sites"][host] = {"ok": True, "changed": any(s not in ("unchanged", "none") for s in states),
                                     "a": ipv4, "aaaa": ipv6, "checked_at": result["checked_at"]}
        except CloudflareError as exc:
            result["sites"][host] = {"ok": False, "error": exc.code}
    return result


# -- history and alerts -------------------------------------------------------

def record_history(events):
    """Append events to dns-history.jsonl, keeping the last HISTORY_LIMIT."""
    if not events:
        return
    now = int(time.time())
    try:
        lines = HISTORY_PATH.read_text().splitlines()
    except OSError:
        lines = []
    lines += [json.dumps({"t": now, **event}, ensure_ascii=False) for event in events]
    _write(HISTORY_PATH, "\n".join(lines[-HISTORY_LIMIT:]) + "\n")


def read_history(limit=50):
    try:
        lines = HISTORY_PATH.read_text().splitlines()
    except OSError:
        return []
    events = []
    for line in reversed(lines[-limit:]):
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and isinstance(item.get("event"), str):
            events.append(item)
    return events


ISSUERS = (("letsencrypt", "Let's Encrypt"), ("zerossl", "ZeroSSL"), ("local", "Caddy"))


def certificate_info(host):
    """(expiry, issuer name) of the certificate Caddy holds for host, or None."""
    for path in sorted((DATA_DIR / "certificates").glob(f"*/{host}/{host}.crt")):
        try:
            not_after = ssl._ssl._test_decode_cert(str(path))["notAfter"]
        except (OSError, ValueError, KeyError, AttributeError):
            continue
        source = path.parent.parent.name
        issuer = next((name for key, name in ISSUERS if key in source), source)
        return datetime.fromtimestamp(ssl.cert_time_to_seconds(not_after), timezone.utc), issuer
    return None


def ip_certificate(sites=None):
    """(cert, key) paths Caddy holds for the enabled IP site, or None."""
    try:
        sites = read_sites() if sites is None else sites
    except (OSError, ValueError):
        return None
    for site in sites:
        if site.get("ip") and site.get("enabled", True):
            host = site["host"]
            for cert in sorted((DATA_DIR / "certificates").glob(f"*/{host}/{host}.crt")):
                key = cert.with_suffix(".key")
                if key.is_file():
                    return cert, key
    return None


def _alert_strings():
    """The web catalog in the console's default language, for Bark messages."""
    lang = "en"
    try:
        unit = Path("/etc/systemd/system/vps-server-web.service").read_text()
        match = re.search(r"^Environment=VPSSRV_DEFAULT_LANG=(\S+)$", unit, re.M)
        if match:
            lang = match[1]
    except OSError:
        pass
    tag = {"zh_cn": "zh-CN", "es": "es"}.get(lang, "en")
    try:
        return json.loads((Path(__file__).resolve().parents[2] / "lang" / "web" / f"{tag}.json").read_text())
    except (OSError, ValueError):
        return {}


def send_alerts(alerts):
    """Push (dedupe key, title key, body key, values) alerts through the console's
    Bark settings, each key at most once a day."""
    if not alerts:
        return
    try:
        from state_paths import data_dir
        from security_events import BarkAlerts
        from features.identity import read_server_label
    except ImportError:
        return
    bark = BarkAlerts(data_dir() / "alerts.json")
    if not bark.configured():
        return
    try:
        sent = json.loads(ALERTED_PATH.read_text())
    except (OSError, ValueError):
        sent = {}
    now = time.time()
    strings = _alert_strings()
    server = read_server_label(data_dir()) or "vps-server"
    for key, title, body, values in alerts:
        if now - sent.get(key, 0) < 86400 or title not in strings or body not in strings:
            continue
        if bark.send_test(strings[title].format(server=server), strings[body].format(**values)) is None:
            sent[key] = now
    _write(ALERTED_PATH, json.dumps({k: v for k, v in sent.items() if now - v < 7 * 86400}) + "\n")


# -- requests ---------------------------------------------------------------

def _locked():
    CONFIG_DIR.mkdir(mode=0o750, parents=True, exist_ok=True)
    handle = open(LOCK_PATH, "a+")
    fcntl.flock(handle, fcntl.LOCK_EX)
    return handle


def reserved_ports():
    """Ports a site must not point back at: Caddy itself."""
    return {80, 443}


def _target(request):
    """The target fields of a site from an add or edit request."""
    if request.get("target") == "console" or (request.get("port") == console_port() and console_port()):
        if console_port() is None:
            raise SiteError("port_invalid")
        return {"console": True}
    port = request.get("port")
    if not valid_port(port) or port in reserved_ports():
        raise SiteError("port_invalid")
    return {"port": port, "backend_tls": request.get("backend_tls") is True,
            "upstream_host": request.get("upstream_host") is True}


def _access(request, current=None):
    """Allowed addresses and basic auth from a request; current keeps a stored password."""
    current = current or {}
    allow = []
    for entry in request.get("allow_ips") or []:
        entry = str(entry).strip()
        if not entry:
            continue
        try:
            allow.append(str(ipaddress.ip_network(entry, strict=False)))
        except ValueError as exc:
            raise SiteError("allow_invalid") from exc
    if len(allow) > MAX_ALLOW:
        raise SiteError("allow_invalid")
    result = {"allow_ips": sorted(set(allow), key=allow.index)} if allow else {}
    user = str(request.get("auth_user") or "").strip()
    if user and not request.get("auth_clear"):
        if not AUTH_USER_RE.fullmatch(user):
            raise SiteError("auth_invalid")
        password = str(request.get("auth_password") or "")
        stored = current.get("auth") or {}
        if password:
            if not 8 <= len(password) <= 128:
                raise SiteError("auth_invalid")
            result["auth"] = {"user": user, "hash": hash_password(password)}
        elif stored.get("user") == user and stored.get("hash"):
            result["auth"] = stored
        else:
            raise SiteError("auth_invalid")
    return result


def _aliases(request, sites, host):
    """Extra names for a site: valid, not the site's own, not used by another site."""
    taken = {name for site in sites if site["host"] != host for name in names(site)}
    result = []
    for raw in request.get("aliases") or []:
        if not str(raw).strip():
            continue
        name = normalize_host(raw)
        if name == host or name in result:
            continue
        if name in taken:
            raise SiteError("host_exists")
        result.append(name)
    if len(result) > MAX_ALIASES:
        raise SiteError("too_many")
    return result


def _replace_site(sites, host, change):
    """Apply change(site) -> new site to host, reload Caddy, roll back on refusal."""
    index = next((i for i, site in enumerate(sites) if site["host"] == host), None)
    if index is None:
        raise SiteError("host_missing")
    updated = list(sites)
    updated[index] = change(dict(sites[index]))
    write_sites(updated)
    render(updated)
    try:
        reload_caddy()
    except RuntimeError:
        write_sites(sites)
        render(sites)
        raise SiteError("caddy_rejected")
    return updated


def apply(request):
    """Change sites or tokens; returns {"ok": bool, "error": code?, "warning": code?}."""
    action = request.get("action")
    with _locked():
        sites = read_sites()
        token = read_tokens()
        warning = None
        if action == "add":
            zone = request.get("zone")
            if zone:
                if zone not in read_zones():
                    raise SiteError("zone_unknown")
                name = str(request.get("name") or "").strip().lower().strip(".")
                host = normalize_host(f"{name}.{zone}" if name and name != "@" else zone)
            else:
                host = normalize_host(request.get("host"))
                zone = zone_of(host, read_zones())
            target = _target(request)
            site = {"host": host, **target,
                    **_access(request if not target.get("console") else {**request, "auth_user": ""})}
            aliases = _aliases(request, sites, host)
            if aliases:
                site["aliases"] = aliases
            site.update({"zone": zone, "added_at": int(time.time())} if zone else {"added_at": int(time.time())})
            if any(host in names(other) for other in sites):
                raise SiteError("host_exists")
            if len(sites) >= MAX_SITES:
                raise SiteError("too_many")
            previous = list(sites)
            sites.append(site)
            write_sites(sites)
            render(sites)
            try:
                reload_caddy()
            except RuntimeError:
                write_sites(previous)
                render(previous)
                raise SiteError("caddy_rejected")
            dns = sync_dns([sites[-1]], token)
            record_history([{"event": "site_added", "host": host}] + dns.pop("events", []))
            _merge_dns(dns, sites)
            warning = dns.get("error") or (dns["sites"].get(host) or {}).get("error")
        elif action == "remove":
            raw = str(request.get("host") or "").strip()
            host = raw if valid_ip(raw) else normalize_host(raw)
            removed = next((site for site in sites if site["host"] == host), None)
            if removed is None:
                raise SiteError("host_missing")
            sites = [site for site in sites if site["host"] != host]
            write_sites(sites)
            render(sites)
            reload_caddy()
            if request.get("remove_dns") and token and valid_host(host):
                for name in names(removed):
                    try:
                        remove_records(token, name)
                    except CloudflareError as exc:
                        warning = exc.code
            record_history([{"event": "site_removed", "host": host}])
            state = read_dns()
            for name in names(removed):
                state.get("sites", {}).pop(name, None)
            _write(DNS_PATH, json.dumps(state) + "\n")
        elif action in ("enable", "disable"):
            host = normalize_host(request.get("host"))
            _replace_site(sites, host, lambda site: {**site, "enabled": action == "enable"})
            record_history([{"event": "site_" + action + "d", "host": host}])
        elif action == "edit":
            host = normalize_host(request.get("host"))
            current = next((site for site in sites if site["host"] == host), None)
            if current is None:
                raise SiteError("host_missing")
            target = _target(request)
            # The console has its own login: a site in front of it takes no password.
            access = _access(request if not target.get("console") else {**request, "auth_user": ""}, current)
            aliases = _aliases(request, sites, host)
            keep = ("host", "zone", "added_at", "enabled")
            updated = _replace_site(sites, host, lambda site: {
                **{k: site[k] for k in keep if k in site}, **target, **access,
                **({"aliases": aliases} if aliases else {})})
            record_history([{"event": "site_edited", "host": host}])
            old_names, new_names = set(names(current)), set(names({"host": host, "aliases": aliases}))
            if token:
                for name in sorted(old_names - new_names):
                    try:
                        remove_records(token, name)
                    except CloudflareError:
                        pass
                added = [{"host": name} for name in sorted(new_names - old_names)]
                if added:
                    dns = sync_dns(added, token)
                    record_history(dns.pop("events", []))
                    _merge_dns(dns, [{"host": n} for site in updated for n in names(site)])
                    warning = dns.get("error") or next((v.get("error") for v in dns["sites"].values()
                                                        if not v.get("ok")), None)
        elif action == "ip":
            # HTTPS for the console at this host's own public IPv4 address.
            previous = list(sites)
            sites = [site for site in sites if not site.get("ip")]
            if request.get("enable"):
                address = public_address(socket.AF_INET)
                if address is None:
                    raise SiteError("no_public_ip")
                if console_port() is None:
                    raise SiteError("port_invalid")
                sites.append({"host": address, "console": True, "ip": True, "added_at": int(time.time())})
            write_sites(sites)
            render(sites)
            try:
                reload_caddy()
            except RuntimeError:
                write_sites(previous)
                render(previous)
                raise SiteError("caddy_rejected")
        elif action == "token_add":
            value = str(request.get("token") or "").strip()
            name = " ".join(str(request.get("name") or "").split())[:40]
            if not TOKEN_RE.fullmatch(value):
                raise SiteError("token_invalid")
            if any(item["token"] == value for item in token):
                raise SiteError("token_exists")
            if len(token) >= MAX_TOKENS:
                raise SiteError("too_many_tokens")
            item = refresh_zones({"token": value, "name": name, "added_at": int(time.time())})
            if item.get("error") == "dns_auth":
                raise SiteError("token_rejected")  # Unreachable is kept: it may work later.
            token.append({**item, "id": token_id(value)})
            write_tokens(token)
            dns = sync_dns(sites, token)
            _write(DNS_PATH, json.dumps(dns) + "\n")
            failed = [state.get("error") for state in dns["sites"].values() if not state.get("ok")]
            warning = item.get("error") or dns.get("error") or (failed[0] if failed else None)
        elif action == "token_remove":
            kept = [item for item in token if item["id"] != request.get("id")]
            if len(kept) == len(token):
                raise SiteError("token_missing")
            write_tokens(kept)
        else:
            raise SiteError("invalid")
    return {"ok": True, **({"warning": warning} if warning else {})}


def _merge_dns(update, sites):
    state = read_dns()
    merged = {host: value for host, value in state.get("sites", {}).items()
              if any(host in names(site) for site in sites)}
    merged.update(update.get("sites", {}))
    state.update({key: update[key] for key in ("checked_at", "ipv4", "ipv6") if key in update})
    if update.get("error"):
        state["error"] = update["error"]
    else:
        state.pop("error", None)
    state["sites"] = merged
    _write(DNS_PATH, json.dumps(state) + "\n")


def ddns():
    with _locked():
        sites = read_sites()
        active = active_sites(sites)
        token = read_tokens()
        previous = read_dns()
        addresses = (public_address(socket.AF_INET), public_address(socket.AF_INET6))
        unchanged = (previous.get("ipv4"), previous.get("ipv6")) == addresses and not previous.get("error") \
            and all((previous.get("sites", {}).get(name) or {}).get("ok")
                    for site in active if not site.get("ip") for name in names(site))
        events, alerts = [], []
        # No address at all is a routing hiccup, not a move: report nothing.
        if previous.get("checked_at") and any(addresses) and (previous.get("ipv4"), previous.get("ipv6")) != addresses:
            events.append({"event": "ip_changed", "old": f'{previous.get("ipv4") or "-"} {previous.get("ipv6") or ""}'.strip(),
                           "value": f'{addresses[0] or "-"} {addresses[1] or ""}'.strip()})
            alerts.append((f"ip:{addresses}", "domains_alert_ip_title", "domains_alert_ip_body",
                           {"old": events[-1]["old"], "new": events[-1]["value"]}))
        # Certificates Caddy should have renewed by now (an address's lasts six days).
        for site in active:
            info = certificate_info(site["host"]) if site.get("enabled", True) else None
            if info:
                left = (info[0] - datetime.now(timezone.utc)).total_seconds() / 86400
                if left < (1 if site.get("ip") else 7):
                    alerts.append((f'cert:{site["host"]}', "domains_alert_cert_title", "domains_alert_cert_body",
                                   {"host": site["host"], "date": info[0].strftime("%Y-%m-%d %H:%M")}))
        # Follow a new public address for the IP site.
        address = public_address(socket.AF_INET)
        for site in sites:
            if site.get("ip") and address and site["host"] != address:
                site["host"] = address
                write_sites(sites)
        # Follow a new console port or client CA.
        if render(sites):
            try:
                reload_caddy()
            except RuntimeError:
                pass
        # Ask Cloudflare only when the address moved, something failed, or
        # every hour as a check against edits made outside the console.
        if unchanged and time.time() - previous.get("checked_at", 0) < 3600:
            record_history(events)
            send_alerts(alerts)
            return previous
        state = sync_dns(active, token, addresses=addresses)
        events += state.pop("events", [])
        for host, result in state["sites"].items():
            if not result.get("ok") and (previous.get("sites", {}).get(host) or {}).get("ok", True):
                events.append({"event": "dns_failed", "host": host, "value": result.get("error", "")})
                alerts.append((f"dns:{host}:{result.get('error')}", "domains_alert_dns_title",
                               "domains_alert_dns_body", {"host": host}))
        _write(DNS_PATH, json.dumps(state) + "\n")
        record_history(events)
        send_alerts(alerts)
        if token:
            save_zones()  # Hourly at most: pick up zones added in Cloudflare.
        return state


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv not in (["apply"], ["render"], ["ddns"], ["zones"]):
        print("usage: caddy_sites.py apply|render|ddns|zones", file=sys.stderr)
        return 2
    if os.geteuid() != 0:
        return 1
    try:
        if argv == ["apply"]:
            raw = sys.stdin.buffer.read(4097)
            if len(raw) > 4096:
                raise SiteError("invalid")
            print(json.dumps(apply(json.loads(raw))))
        elif argv == ["render"]:
            render()
        elif argv == ["zones"]:
            save_zones()
            print(json.dumps(read_zones()))
        else:
            state = ddns()
            if state.get("error") or any(not s.get("ok") for s in state.get("sites", {}).values()):
                print(f"DNS sync incomplete: {state.get('error') or 'see console'}", file=sys.stderr)
    except SiteError as exc:
        print(json.dumps({"ok": False, "error": exc.code}))
        return 3
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"ok": False, "error": "failed"}))
        print(f"Domain forwarding {argv[0]} failed: {type(exc).__name__}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
