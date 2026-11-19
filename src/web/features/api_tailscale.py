"""JSON API for the Tailscale page. Every command still goes through the allowlist in tailscale_control."""

import subprocess
import time
from urllib.parse import urlsplit

import tailscale_control as control
from features.tailscale import _CONNECT_LOCK

SETTING_NAMES = ("accept-dns", "accept-routes", "advertise-exit-node", "exit-node-allow-lan-access",
                 "shields-up", "snat-subnet-routes", "ssh", "webclient")


class TailscaleApiMixin:
    API_ROUTES_TAILSCALE = {
        ("GET", "tailscale"): "api_tailscale",
        ("GET", "tailscale/netcheck"): "api_tailscale_netcheck",
        ("POST", "tailscale/restart"): "api_tailscale_restart",
        ("POST", "tailscale/connect"): "api_tailscale_connect",
        ("POST", "tailscale/logout"): "api_tailscale_logout",
        ("PUT", "tailscale/settings"): "api_tailscale_settings",
    }

    def _tailscale_installed(self):
        return "tailscale" in self.context.installed_modules(self.context.BASE_DIR)

    def tailscale_state(self):
        if not self._tailscale_installed():
            return {"installed": False}
        try:
            snapshot = control.status()
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            return {"installed": True, "available": False}
        state = snapshot.get("BackendState", "Stopped")
        try:
            settings = control.prefs()
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            settings = {}
        try:
            memory = control.memory_mode()
        except (OSError, ValueError):
            memory = None
        self_info = snapshot.get("Self") or {}
        addresses = self_info.get("TailscaleIPs") or []
        user = (snapshot.get("User") or {}).get(str(self_info.get("UserID")), {})
        auth = snapshot.get("AuthURL") or ""
        parsed = urlsplit(auth)
        auth_ok = parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password
        peers = control.peers(snapshot)
        current_routes = str(settings.get("advertise-routes") or "")
        current_exit = str(settings.get("exit-node") or "")
        subnets = list(control.local_subnets())
        if current_routes and current_routes not in subnets:
            subnets.insert(0, current_routes)
        exits = [{"value": peer["selector"], "label": peer["name"]} for peer in peers if peer["exit_option"] and peer["selector"]]
        if current_exit and current_exit not in [item["value"] for item in exits]:
            exits.insert(0, {"value": current_exit, "label": current_exit})
        return {
            "installed": True, "available": True, "state": str(state),
            "version": (snapshot.get("Version") or "").split("-", 1)[0],
            "tun": snapshot.get("TUN") if isinstance(snapshot.get("TUN"), bool) else None,
            "present": {"controlServer": bool((snapshot.get("CurrentTailnet") or {}).get("Name")),
                        "ipv4": any(":" not in ip for ip in addresses), "ipv6": any(":" in ip for ip in addresses),
                        "account": bool(user.get("LoginName"))},
            "authUrl": auth if auth_ok else None,
            "settings": {"bools": {name: settings.get(name) if isinstance(settings.get(name), bool) else None
                                   for name in SETTING_NAMES},
                         "routes": current_routes, "exit": current_exit,
                         "relay": bool(settings.get("relay-server-port")), "memory": memory},
            "subnets": subnets, "exitNodes": exits,
            "devices": [{"id": peer["id"], "name": peer["name"], "online": peer["online"], "os": peer["os"],
                         "relay": peer["relay"], "rx": peer["rx"], "tx": peer["tx"], "lastSeen": peer["last_seen"],
                         "ipv4": bool(peer["id"]) and any(":" not in ip for ip in peer["addresses"]),
                         "ipv6": bool(peer["id"]) and any(":" in ip for ip in peer["addresses"])}
                        for peer in peers],
        }

    def api_tailscale(self):
        return self.api_ok(self.tailscale_state())

    def api_tailscale_netcheck(self):
        """Connectivity checks; slow, so the page asks for them separately."""
        if not self._tailscale_installed():
            return self.api_error(404, "not_found")
        try:
            if control.status().get("BackendState") != "Running":
                return self.api_ok({"running": False})
            net = control.netcheck()
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            return self.api_ok({"running": True, "failed": True})
        checks = {"varies": net.get("MappingVariesByDestIP"), "ipv4": net.get("IPv4"), "ipv6": net.get("IPv6"),
                  "udp": net.get("UDP"), "upnp": net.get("UPnP"), "pcp": net.get("PCP"), "pmp": net.get("PMP"),
                  "hairpinning": net.get("HairPinning")}
        return self.api_ok({"running": True, "derp": str(net.get("PreferredDERP") or ""),
                            "endpoint": bool(net.get("GlobalV4")),
                            "checks": {key: value if isinstance(value, bool) else None for key, value in checks.items()}})

    def _tailscale_done(self, action):
        if not self._tailscale_installed():
            return self.api_error(404, "not_found")
        try:
            action()
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            return self.api_error(400, "tailscale_action_failed")
        return self.api_ok(self.tailscale_state())

    def api_tailscale_restart(self):
        if self.read_json() is None:
            return self.api_error(400, "invalid_request")
        return self._tailscale_done(lambda: subprocess.run(["systemctl", "restart", control.UNIT], check=True, timeout=60))

    def api_tailscale_logout(self):
        if (self.read_json() or {}).get("confirm") is not True:
            return self.api_error(400, "invalid_request")
        return self._tailscale_done(lambda: control.call("logout"))

    def api_tailscale_connect(self):
        body = self.read_json() or {}
        server, key = body.get("loginServer", ""), body.get("authKey", "")
        if not isinstance(server, str) or not isinstance(key, str) or len(server) > 255 or len(key) > 2048:
            return self.api_error(400, "invalid_request")

        def connect():
            # Overlapping `tailscale up` runs reset each other's login, so only one runs at a time.
            if not _CONNECT_LOCK.acquire(blocking=False):
                return
            try:
                try:
                    control.connect(server, key)
                except (RuntimeError, subprocess.TimeoutExpired):
                    # A login URL can be issued while `up` waits for browser approval.
                    for _ in range(10):
                        if control.status().get("AuthURL"):
                            break
                        time.sleep(0.5)
                    else:
                        raise
            finally:
                _CONNECT_LOCK.release()
        return self._tailscale_done(connect)

    def api_tailscale_settings(self):
        """All settings saved together, through the same checks as the old batch form.

        ``bools`` holds the switches the page could change; ``routes`` and ``exit``
        are the chosen value ("" for none); ``relay`` is a new port, "" to clear,
        or null to keep; ``memory`` is null when unavailable.
        """
        body = self.read_json() or {}
        bools, memory = body.get("bools") or {}, body.get("memory")
        if not isinstance(bools, dict) or set(bools) - set(SETTING_NAMES) or \
                any(not isinstance(value, bool) for value in bools.values()) or \
                not (memory is None or isinstance(memory, bool)):
            return self.api_error(400, "invalid_request")
        form = {"routes_value": [""], "exit_value": [""], "relay_value": [""]}
        for name, value in bools.items():
            form["available_" + name] = ["1"]
            if value:
                form["enabled_" + name] = ["1"]
        if memory is not None:
            form["memory_available"] = ["1"]
            if memory:
                form["memory_enabled"] = ["1"]
        try:
            previous = control.prefs()
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            return self.api_error(400, "tailscale_action_failed")
        for kind, name in (("routes", "advertise-routes"), ("exit", "exit-node"), ("relay", "relay-server-port")):
            value = body.get(kind)
            if value is None:
                continue
            if not isinstance(value, str) or len(value) > 255:
                return self.api_error(400, "invalid_request")
            if value.strip():
                form[kind + "_value"] = [value.strip()]
            elif previous.get(name):
                form[kind + "_clear"] = ["1"]
        return self._tailscale_done(lambda: self.apply_tailscale_batch(form))
