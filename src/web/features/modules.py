"""Module jobs, service logs and the public page address (the pages are the single-page UI).

Host dependencies are supplied by ``ConsoleHandler.context`` so the feature
can be reused with another application context.
"""

import os
import json
import time


LOG_LEVELS = (("all", "logs_level_all"), ("err", "logs_level_error"),
              ("warning", "logs_level_warning"), ("info", "logs_level_info"),
              ("debug", "logs_level_debug"))


LOG_SOURCES = ("modules", "web", "proxy", "frps", "frpc", "tailscale", "caddy")


def log_cutoffs(context):
    try:
        data = json.loads((context.DATA_DIR / "log-clear.json").read_text())
        if isinstance(data, dict):
            return {key: value for key, value in data.items()
                    if key in LOG_SOURCES and type(value) in (int, float) and 0 < value <= time.time() + 1}
    except (OSError, ValueError):
        pass
    return {}


def service_log_text(context, units, level, limit, since=None):
    if level not in dict(LOG_LEVELS) or not units or not context.shutil.which("journalctl"):
        return None
    command = ["journalctl", "--no-pager", "-o", "short-iso", "-n", str(limit)]
    if level != "all":
        command.extend(("-p", level))
    if since:
        command.append(f"--since=@{since:.6f}")
    for unit in units:
        command.extend(("-u", unit))
    try:
        result = context.subprocess.run(command, capture_output=True, text=True, timeout=15)
        return result.stdout if result.returncode == 0 else None
    except (OSError, context.subprocess.TimeoutExpired):
        return None


def clear_log_source(context, source):
    """Hide the history shown for one log source (or "all"); journald keeps it."""
    if source in ("modules", "all"):
        path = context.module_history_path(context.BASE_DIR)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8"):
            pass
        os.chmod(path, 0o600)
    if source != "modules":
        cutoffs = log_cutoffs(context)
        for key in (LOG_SOURCES[1:] if source == "all" else (source,)):
            cutoffs[key] = time.time()
        context._atomic_private_text(context.DATA_DIR / "log-clear.json",
                                     json.dumps(cutoffs, sort_keys=True) + "\n")


def log_service_units(context):
    """Each service log source and its systemd units, in display order."""
    return (
        ("web", ("vps-server-web.service",)),
        ("proxy", ("vps-server-proxy.service", "vps-server-node-meter.service")),
        ("frps", ("vps-server-frps.service",)),
        ("frpc", tuple(context.frpc_unit(name) for name in context.frpc_names())),
        ("tailscale", ("vps-server-tailscale.service",)),
        ("caddy", ("vps-server-caddy.service", "vps-server-caddy-dns.service")),
    )


def module_history_text(context):
    for path in (context.module_history_path(context.BASE_DIR), context.module_log_path(context.BASE_DIR)):
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            continue
    return ""


def module_job_text(t, job, names):
    """Describe the current module action using a localized display name."""
    if job.get("reason") == "port_occupied" and job.get("state") == "failed":
        return t["module_port_occupied"].format(port=job.get("port", ""))
    if job.get("reason") == "host_check" and job.get("state") == "failed" and isinstance(job.get("codes"), list):
        texts = [t.get("host_check_" + str(code), "") for code in job["codes"]]
        if all(texts):
            return " ".join(texts)
    name = names.get(job.get("module"), t.get("module_" + str(job.get("module", "")),
                                               str(job.get("module", ""))))
    key = "module_action_" + str(job.get("action", "")) + "_" + str(job.get("state", ""))
    return t.get(key, t.get("module_job_" + str(job.get("state", "")), "")).format(name=name)


# Feature pages that offer their own install button, and where the job reports.
INSTALL_PAGES = {"iperf3": "/iperf", "proxy_nodes": "/proxy", "frps": "/frps", "frpc": "/frpc",
                 "tailscale": "/tailscale", "caddy": "/domains", "ipcert": "/ipcert"}


_HOST_FINDINGS = {}


def host_findings(context, t, module):
    """Unmet host needs for a module that is not installed yet, in one line.

    Probing nft can unpack the bundled runtime, so results are kept briefly.
    """
    now = time.monotonic()
    cached = _HOST_FINDINGS.get(module)
    if cached is None or now - cached[0] > 60:
        from host_checks import NFT_CODES, can_install_nft, check
        try:
            # The IP certificate installs the Caddy module.
            findings = check("caddy" if module == "ipcert" else module,
                             source=context.BASE_DIR / "installer-source", prefix=context.BASE_DIR)
        except (OSError, ValueError):
            findings = []
        # A missing nft is installed by the module job itself when apt exists.
        findings = [(level, "nft_auto" if code in NFT_CODES and can_install_nft() else code)
                    for level, code in findings]
        cached = _HOST_FINDINGS[module] = (now, findings)
    return " ".join(t["host_check_" + code] for _level, code in cached[1] if "host_check_" + code in t)


def module_job_recent(job, now, seconds):
    at = job.get("at")
    return type(at) in (int, float) and 0 <= now - at < seconds


class ModulesMixin:


    def public_page_url(self, module):
        authority = self.headers.get("Host", "")
        try:
            host = self.context.urlsplit("http://" + authority).hostname
        except ValueError:
            host = None
        if not host or not host.isascii() or not all(c.isalnum() or c in ".:-" for c in host):
            return None
        if self.context.CADDY_HOLDS_PUBLIC_PORTS:
            # Caddy answers the page only for this host's address: a domain on
            # 80 is sent on to HTTPS, and on 443 it is a forwarded site.
            try:
                self.context.ipaddress.ip_address(host)
            except ValueError:
                from caddy_sites import public_address
                host = public_address(self.context.socket.AF_INET) or host
        host = f"[{host}]" if ":" in host else host
        scheme, port = (("http", self.context.PUBLIC_HTTP_PORT) if module == "web_http"
                        else ("https", self.context.PUBLIC_HTTPS_PORT))
        return f"{scheme}://{host}{':' + str(port) if port != (80 if scheme == 'http' else 443) else ''}/"


    def closed_module(self, module, lang):
        """(destination page, display name, closed now) for a module that has a "closed" page, else None."""
        destinations = {"web_public": "/public/http", "web_http": "/public/http", "web_https": "/public/https",
                        "speedtest": "/speedtest", "iperf3": "/iperf", "proxy_nodes": "/proxy",
                        "frps": "/frps", "frpc": "/frpc", "frp": "/frpc", "tailscale": "/tailscale", "portfwd": "/portfwd",
                        "caddy": "/domains", "ipcert": "/ipcert",
                        "files": "/files",
                        "visitors": "/visitors", "terminal": "/terminal", "changelog": "/changelog"}
        if module not in destinations:
            return None
        t = self.context.STRINGS[lang]
        names = {"web_public": t["module_web_public"], "web_http": t["module_web_http"], "web_https": t["module_web_https"],
                 "speedtest": t["speedtest"], "iperf3": t["iperf"],
                 "proxy_nodes": t["proxy"], "frps": "FRPS", "frpc": "FRPC", "tailscale": "Tailscale",
                 "caddy": t["domains"], "ipcert": t["ipcert"],
                 "frp": t["frp_heading"], "portfwd": t["portfwd"], "files": t["files"],
                 "visitors": t["visitors"], "terminal": t["terminal_title"], "changelog": t["changelog"]}
        return destinations[module], names[module], not self.context.module_states()[module]


    def public_page_redirect(self, path):
        """Send the operator on to the public page itself, on this host's public address."""
        module = "web_http" if path.endswith("http") else "web_https"
        if not self.context.module_states()[module]:
            return self.redirect("/closed?module=web_public", {"Cache-Control": "no-store"})
        destination = self.public_page_url(module)
        if not destination:
            return self.send_html(400, "Invalid host", {"Cache-Control": "no-store"})
        return self.redirect(destination, {"Cache-Control": "no-store"})


def portfwd_enabled(context, ):
    return context.PORTFWD_ALLOWED and context.module_feature_enabled(context.BASE_DIR, "portfwd")


def public_listener_runtime(context, module):
    if module not in ("web_http", "web_https"):
        return None
    try:
        status = context.json.loads((context.DATA_DIR / "public-listeners.json").read_text())
        if status.get("pid") == os.getpid():
            return status["http" if module == "web_http" else "https"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def public_listener_occupied(context, module, job):
    runtime = public_listener_runtime(context, module)
    if runtime and runtime.get("bound"):
        return None
    if runtime and runtime.get("enabled") and not runtime.get("bound") and runtime.get("reason") == "occupied":
        return runtime.get("port")
    if job.get("module") == module and job.get("state") == "failed" and job.get("reason") == "port_occupied":
        return job.get("port")
    return None

def module_states(context, installed=None):
    installed = installed if installed is not None else context.installed_modules(context.BASE_DIR)
    caddy_running = "caddy" in installed and context._run_quiet(
        ["systemctl", "is-enabled", "--quiet", context.MANAGED_UNITS["caddy"]])
    def public(listener, enabled):
        if context.CADDY_HOLDS_PUBLIC_PORTS:
            # Caddy answers the page; its switch is the console's own setting.
            return context.public_listener_enabled(context.BASE_DIR, listener, context.PUBLIC_DEFAULT,
                                                   own_setting=True)
        return enabled and (public_listener_runtime(context, listener) or {}).get("bound", True)

    states = {
        "web_http": "web" in installed and public("web_http", context.PUBLIC_HTTP_ENABLED),
        "web_https": "web" in installed and public("web_https", context.PUBLIC_HTTPS_ENABLED),
        "speedtest": context.module_feature_enabled(context.BASE_DIR, "speedtest"),
        "iperf3": "iperf3" in installed and context.IPERF_ENABLED,
        "proxy_nodes": "proxy" in installed and context._run_quiet(
            ["systemctl", "is-enabled", "--quiet", context.MANAGED_UNITS["proxy"]]),
        "frps": "frps" in installed and context._run_quiet(
            ["systemctl", "is-enabled", "--quiet", context.MANAGED_UNITS["frps"]]),
        "frpc": "frpc" in installed and context.frpc_group_enabled(context.BASE_DIR),
        "tailscale": "tailscale" in installed and context._run_quiet(
            ["systemctl", "is-enabled", "--quiet", context.MANAGED_UNITS["tailscale"]]),
        "caddy": caddy_running and context.caddy_domains_enabled(),
        "ipcert": caddy_running and context.caddy_ip_enabled(),
        "portfwd": context.portfwd_enabled(),
        "visitors": context.module_feature_enabled(context.BASE_DIR, "visitors"),
        "files": context.module_feature_enabled(context.BASE_DIR, "files"),
        "terminal": context.AUTH_ENABLED and context.module_feature_enabled(context.BASE_DIR, "terminal"),
        "changelog": True,
    }
    states["frp"] = states["frps"] or states["frpc"]
    states["web_public"] = states["web_http"] or states["web_https"]
    return states
