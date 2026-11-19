"""Tailscale settings and masked values. All command execution is allowlisted in tailscale_control."""

import subprocess
import threading

import tailscale_control as control

_CONNECT_LOCK = threading.Lock()


class TailscaleMixin:
    def apply_tailscale_batch(self, form):
        previous = control.prefs()
        state = control.status().get("BackendState")
        changes = {}
        for name in control.BOOL_SETTINGS:
            if form.get("available_" + name) != ["1"]:
                continue
            if type(previous.get(name)) is not bool or name == "webclient" and state != "Running":
                raise ValueError("Tailscale setting unavailable")
            value = form.get("enabled_" + name) == ["1"]
            if value != previous[name]:
                changes[name] = value
        for kind, name in (("routes", "advertise-routes"), ("exit", "exit-node"),
                           ("relay", "relay-server-port")):
            typed = form[kind + "_value"][0].strip()
            clear = form.get(kind + "_clear") == ["1"]
            if typed and clear:
                raise ValueError("conflicting Tailscale setting")
            if not typed and not clear:
                continue
            value = "" if clear else typed
            if name == "advertise-routes":
                value = control.normalize_routes(value)
            elif name == "exit-node":
                value = control.normalize_exit_node(value)
            elif value and (not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 65535):
                raise ValueError("invalid peer relay port")
            if value != str(previous.get(name) or ""):
                changes[name] = value
        if changes.get("webclient") is True or changes.get("relay-server-port"):
            if state != "Running":
                raise ValueError("Tailscale is not connected")
        old_memory = control.memory_mode()
        new_memory = form.get("memory_enabled") == ["1"] if form.get("memory_available") == ["1"] else old_memory
        reserved = []

        def change_memory(enabled):
            unit = "vps-server-tail-memory-" + self.context.secrets.token_hex(6)
            result = subprocess.run(["systemd-run", "--quiet", "--wait", "--pipe", "--collect",
                                     "--unit=" + unit, "/usr/bin/python3",
                                     str(self.context.WEB_CODE_DIR / "tailscale_control.py"),
                                     "memory", "on" if enabled else "off"], capture_output=True, text=True,
                                    check=False, timeout=90)
            if result.returncode:
                raise RuntimeError("Tailscale memory setting failed")

        try:
            if new_memory != old_memory:
                change_memory(new_memory)
            if changes.get("webclient") is True and self.context.reserve_owned_port(
                    self.context.BASE_DIR, 5252, "vps-server Tailscale Web"):
                reserved.append((5252, "vps-server Tailscale Web"))
            relay = changes.get("relay-server-port")
            if relay and self.context.reserve_owned_port(
                    self.context.BASE_DIR, int(relay), "vps-server Tailscale Relay"):
                reserved.append((int(relay), "vps-server Tailscale Relay"))
            if changes:
                control.set_many(changes)
        except BaseException:
            for port, owner in reversed(reserved):
                self.context.release_owned_port(self.context.BASE_DIR, port, owner)
            if new_memory != old_memory:
                change_memory(old_memory)
            raise
        if changes.get("webclient") is False:
            self.context.release_owned_port(self.context.BASE_DIR, 5252, "vps-server Tailscale Web")
        old_relay = str(previous.get("relay-server-port") or "")
        if old_relay and "relay-server-port" in changes and old_relay != changes["relay-server-port"]:
            self.context.release_owned_port(self.context.BASE_DIR, int(old_relay), "vps-server Tailscale Relay")
        if "webclient" in changes or "relay-server-port" in changes:
            self.context.snapshot_tailscale_ports()


    def tailscale_private_value(self, identifier, field):
        """A masked Tailscale value (addresses, account, current settings); ValueError when there is none."""
        settings_value = identifier in ("tailscale-setting-routes", "tailscale-setting-exit",
                                        "tailscale-setting-relay") and field == "value"
        address_value = (field == "address" and identifier in (
            "tailscale-tailscale_control_server", "tailscale-tailscale_ipv4", "tailscale-tailscale_ipv6",
            "tailscale-tailscale_account", "tailscale-tailscale_public_endpoint")) or (
            field in ("ipv4", "ipv6") and identifier.startswith("tailscale-peer-"))
        if not (settings_value or address_value):
            raise ValueError("unsupported value")
        try:
            snapshot = control.status()
            if settings_value:
                preferences = control.prefs()
                value = preferences["advertise-routes" if identifier.endswith("routes") else
                                    "relay-server-port" if identifier.endswith("relay") else "exit-node"]
            elif identifier == "tailscale-tailscale_control_server":
                value = (snapshot.get("CurrentTailnet") or {})["Name"]
            elif identifier == "tailscale-tailscale_account":
                self_info = snapshot.get("Self") or {}
                value = (snapshot.get("User") or {})[str(self_info.get("UserID"))]["LoginName"]
            elif identifier == "tailscale-tailscale_public_endpoint":
                value = control.netcheck()["GlobalV4"]
            elif identifier.startswith("tailscale-peer-"):
                peer = next(p for p in control.peers(snapshot) if p["id"] == identifier[len("tailscale-peer-"):])
                value = next(address for address in peer["addresses"] if (":" in address) == (field == "ipv6"))
            else:
                ips = (snapshot.get("Self") or {}).get("TailscaleIPs") or []
                value = next(ip for ip in ips if (":" in ip) == identifier.endswith("ipv6"))
        except (OSError, ValueError, RuntimeError, StopIteration, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
            raise ValueError("no such value") from exc
        if value in (None, ""):
            raise ValueError("no such value")
        return str(value)
