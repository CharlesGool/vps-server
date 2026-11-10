#!/usr/bin/env python3
"""Domain forwarding: subdomain -> local port through Caddy, DNS on Cloudflare.

Caddy owns ports 80 and 443 while this module is on. Each site forwards one
host name to 127.0.0.1:<port> (typically an frps or frpc listener) and gets
its certificate from Caddy's automatic HTTPS (HTTP-01 or TLS-ALPN-01). The
console keeps an A record, and an AAAA record when the host has a public
IPv6 address, for every site on Cloudflare, "DNS only", pointing at this
host's own public address. Nothing asks an outside service for that address.

Files (all root-owned):
    /etc/vps-server-caddy/sites.json        sites                       0600
    /etc/vps-server-caddy/cloudflare-token  Cloudflare API token        0600
    /etc/vps-server-caddy/dns.json          last DNS sync result        0600
    /etc/vps-server-caddy/caddy.json        generated Caddy config      0640 root:vps-server-caddy
    /var/lib/vps-server-caddy               Caddy certificates and ACME accounts

    caddy_sites.py apply    one request as JSON on stdin (root)
    caddy_sites.py render   write caddy.json from sites.json (root)
    caddy_sites.py ddns     update every site's DNS records (root, timer)
"""

import fcntl
import grp
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
TOKEN_PATH = CONFIG_DIR / "cloudflare-token"
DNS_PATH = CONFIG_DIR / "dns.json"
CADDY_CONFIG = CONFIG_DIR / "caddy.json"
LOCK_PATH = CONFIG_DIR / "sites.lock"
DATA_DIR = Path(os.environ.get("VPSSRV_CADDY_DATA", "/var/lib/vps-server-caddy"))
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
    return [site for site in sites if isinstance(site, dict) and valid_host(site.get("host"))
            and valid_port(site.get("port"))]


def write_sites(sites, path=SITES_PATH):
    _write(Path(path), json.dumps({"sites": sites}, indent=2) + "\n")


def read_token(path=TOKEN_PATH):
    try:
        token = Path(path).read_text().strip()
    except FileNotFoundError:
        return ""
    return token if TOKEN_RE.fullmatch(token) else ""


def read_dns(path=DNS_PATH):
    try:
        data = json.loads(Path(path).read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def valid_host(host):
    return isinstance(host, str) and HOST_RE.fullmatch(host) is not None


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


# -- Caddy ------------------------------------------------------------------

def caddy_config(sites):
    """Caddy's native JSON: one route per host, everything else is dropped."""
    abort = {"handle": [{"handler": "static_response", "abort": True}]}
    routes = [{"match": [{"host": [site["host"]]}],
               "handle": [{"handler": "reverse_proxy",
                           "upstreams": [{"dial": f"127.0.0.1:{site['port']}"}]}],
               "terminal": True}
              for site in sites]
    return {
        "admin": {"listen": "unix/" + ADMIN_SOCKET},
        "storage": {"module": "file_system", "root": str(DATA_DIR)},
        "apps": {"http": {"servers": {
            # Automatic HTTPS adds the HTTP-to-HTTPS redirects and the ACME
            # HTTP challenge to the :80 server; any other host gets nothing.
            "https": {"listen": [":443"], "routes": routes + [abort]},
            "http": {"listen": [":80"], "routes": [abort]},
        }}},
    }


def render(sites=None):
    sites = read_sites() if sites is None else sites
    try:
        group = grp.getgrnam(GROUP).gr_gid
    except KeyError:
        group = None
    _write(CADDY_CONFIG, json.dumps(caddy_config(sites), indent=2) + "\n",
           0o640 if group is not None else 0o600, group)


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


def remove_records(token, host, opener=None):
    zone = find_zone(token, host, opener=opener)
    for kind in ("A", "AAAA"):
        sync_record(token, zone, host, kind, None, opener=opener)


def sync_dns(sites, token, *, addresses=None, opener=None):
    """Point every site at this host. Returns the dns.json document."""
    ipv4, ipv6 = addresses if addresses is not None else (
        public_address(socket.AF_INET), public_address(socket.AF_INET6))
    result = {"checked_at": int(time.time()), "ipv4": ipv4, "ipv6": ipv6, "sites": {}}
    if not token:
        result["error"] = "dns_no_token"
        return result
    if ipv4 is None and ipv6 is None:
        result["error"] = "dns_no_address"
        return result
    for site in sites:
        host = site["host"]
        try:
            zone = find_zone(token, host, opener=opener)
            states = [sync_record(token, zone, host, "A", ipv4, opener=opener),
                      sync_record(token, zone, host, "AAAA", ipv6, opener=opener)]
            result["sites"][host] = {"ok": True, "changed": any(s not in ("unchanged", "none") for s in states)}
        except CloudflareError as exc:
            result["sites"][host] = {"ok": False, "error": exc.code}
    return result


# -- requests ---------------------------------------------------------------

def _locked():
    CONFIG_DIR.mkdir(mode=0o750, parents=True, exist_ok=True)
    handle = open(LOCK_PATH, "a+")
    fcntl.flock(handle, fcntl.LOCK_EX)
    return handle


def reserved_ports():
    """Ports a site must not point back at: Caddy itself."""
    return {80, 443}


def apply(request):
    """Change sites or the token; returns {"ok": bool, "error": code?, "warning": code?}."""
    action = request.get("action")
    with _locked():
        sites = read_sites()
        token = read_token()
        warning = None
        if action == "add":
            host = normalize_host(request.get("host"))
            port = request.get("port")
            if not valid_port(port) or port in reserved_ports():
                raise SiteError("port_invalid")
            if any(site["host"] == host for site in sites):
                raise SiteError("host_exists")
            if len(sites) >= MAX_SITES:
                raise SiteError("too_many")
            previous = list(sites)
            sites.append({"host": host, "port": port})
            write_sites(sites)
            render(sites)
            try:
                reload_caddy()
            except RuntimeError:
                write_sites(previous)
                render(previous)
                raise SiteError("caddy_rejected")
            dns = sync_dns([sites[-1]], token)
            _merge_dns(dns, sites)
            warning = dns.get("error") or (dns["sites"].get(host) or {}).get("error")
        elif action == "remove":
            host = normalize_host(request.get("host"))
            if not any(site["host"] == host for site in sites):
                raise SiteError("host_missing")
            sites = [site for site in sites if site["host"] != host]
            write_sites(sites)
            render(sites)
            reload_caddy()
            if request.get("remove_dns") and token:
                try:
                    remove_records(token, host)
                except CloudflareError as exc:
                    warning = exc.code
            state = read_dns()
            state.get("sites", {}).pop(host, None)
            _write(DNS_PATH, json.dumps(state) + "\n")
        elif action == "token":
            value = str(request.get("token") or "").strip()
            if value and not TOKEN_RE.fullmatch(value):
                raise SiteError("token_invalid")
            if value:
                _write(TOKEN_PATH, value + "\n")
                dns = sync_dns(sites, value)
                _write(DNS_PATH, json.dumps(dns) + "\n")
                failed = [state.get("error") for state in dns["sites"].values() if not state.get("ok")]
                warning = dns.get("error") or (failed[0] if failed else None)
            else:
                TOKEN_PATH.unlink(missing_ok=True)
        else:
            raise SiteError("invalid")
    return {"ok": True, **({"warning": warning} if warning else {})}


def _merge_dns(update, sites):
    state = read_dns()
    merged = {host: value for host, value in state.get("sites", {}).items()
              if any(site["host"] == host for site in sites)}
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
        token = read_token()
        previous = read_dns()
        addresses = (public_address(socket.AF_INET), public_address(socket.AF_INET6))
        unchanged = (previous.get("ipv4"), previous.get("ipv6")) == addresses and not previous.get("error") \
            and all((previous.get("sites", {}).get(site["host"]) or {}).get("ok") for site in sites)
        # Ask Cloudflare only when the address moved, something failed, or
        # every hour as a check against edits made outside the console.
        if unchanged and time.time() - previous.get("checked_at", 0) < 3600:
            return previous
        state = sync_dns(sites, token, addresses=addresses)
        _write(DNS_PATH, json.dumps(state) + "\n")
        return state


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv not in (["apply"], ["render"], ["ddns"]):
        print("usage: caddy_sites.py apply|render|ddns", file=sys.stderr)
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
