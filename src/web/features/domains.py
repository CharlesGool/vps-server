"""Domain forwarding helpers: the root helper call, Caddy access log and listening ports (the page is the single-page UI).

Reads the module's state directly; every change goes through the root helper
caddy_sites.py, outside Web's sandbox.
"""

import json
import subprocess

from caddy_sites import ACCESS_LOG, read_sites, read_tokens, zone_of
NOTICES = ("domains_added", "domains_removed", "domains_token_saved", "domains_token_cleared",
           "domains_site_enabled", "domains_site_disabled",
           "domains_site_saved")
ERRORS = ("host_invalid", "port_invalid", "host_exists", "host_missing", "too_many", "zone_unknown", "no_public_ip", "allow_invalid", "auth_invalid",
          "caddy_rejected", "token_invalid", "token_rejected", "token_exists", "token_missing", "too_many_tokens", "invalid", "failed")
WARNINGS = ("dns_auth", "dns_zone", "dns_unreachable", "dns_api", "dns_no_token", "dns_no_address")


def _read_json(path):
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def access_entries(host, limit):
    """The newest access-log entries for host, read from the end of Caddy's log."""
    entries = []
    for path in (ACCESS_LOG, *sorted(ACCESS_LOG.parent.glob(ACCESS_LOG.stem + "-*.log"), reverse=True)):
        try:
            with open(path, "rb") as handle:
                handle.seek(0, 2)
                size = handle.tell()
                handle.seek(max(0, size - 2 * 1024 * 1024))
                lines = handle.read().splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict) and (entry.get("request") or {}).get("host", "").split(":")[0] == host:
                entries.append(entry)
                if len(entries) >= limit:
                    return entries
    return entries


def listening_ports():
    """TCP ports something listens on, or None when ss cannot tell."""
    try:
        from console_port import host_tool
        output = subprocess.run([host_tool("ss"), "-H", "-ltn"], capture_output=True, text=True,
                                timeout=5, check=True).stdout
    except (ImportError, OSError, subprocess.SubprocessError):
        return None
    ports = set()
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 4 and fields[3].rsplit(":", 1)[-1].isdecimal():
            ports.add(int(fields[3].rsplit(":", 1)[-1]))
    return ports


class DomainsMixin:

    def domains_apply(self, request):
        """Run one change through the root helper; returns its JSON reply."""
        helper = self.context.WEB_CODE_DIR / "caddy_sites.py"
        command = ["systemd-run", "--pipe", "--wait", "--collect", "--quiet",
                   "--unit=vps-server-domains-edit", "/usr/bin/python3", str(helper), "apply"]
        try:
            result = self.context.subprocess.run(command, input=json.dumps(request).encode("utf-8"),
                                                 capture_output=True, timeout=120, check=False)
            return json.loads(result.stdout.decode("utf-8", "replace").strip().splitlines()[-1])
        except (OSError, ValueError, IndexError, self.context.subprocess.TimeoutExpired):
            return {"ok": False, "error": "failed"}
