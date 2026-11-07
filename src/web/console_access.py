#!/usr/bin/env python3
"""Limit which source addresses may open a connection to the console.

Off by default. Once on, a connection from an address outside the list is
closed before the TLS handshake, so the login page is not even reachable.
Loopback is always allowed. The list holds single addresses or networks
(CIDR), IPv4 or IPv6, and the switch cannot be turned on, nor an entry
removed, in a way that shuts out the connection making the change.

The file is re-read whenever it changes, so root on the host recovers from
a lockout without restarting the service:
    python3 <prefix>/src/web/console_access.py disable
"""

import ipaddress
import json
import os
import sys
import tempfile
import threading
from pathlib import Path

try:
    from .state_paths import data_dir as default_data_dir
except ImportError:  # Installed helpers are copied into one flat directory.
    from state_paths import data_dir as default_data_dir


LIMIT = 64


class ConsoleAccessError(ValueError):
    """``str(error)`` is the interface string key describing the problem."""


def canonical_network(value):
    """One address or CIDR as a canonical network string, or ConsoleAccessError."""
    if not isinstance(value, str) or value != value.strip() or not value or "%" in value or len(value) > 64:
        raise ConsoleAccessError("console_access_invalid")
    try:
        network = ipaddress.ip_network(value, strict=False)
    except ValueError:
        raise ConsoleAccessError("console_access_invalid") from None
    if isinstance(network, ipaddress.IPv6Network) and network.network_address.ipv4_mapped:
        mapped = network.network_address.ipv4_mapped
        network = ipaddress.ip_network(f"{mapped}/{max(network.prefixlen - 96, 0)}", strict=False)
    if network.prefixlen == 0:
        raise ConsoleAccessError("console_access_too_wide")
    return str(network)


def _address(value):
    try:
        address = ipaddress.ip_address(str(value).split("%", 1)[0])
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        return address.ipv4_mapped
    return address


class ConsoleAccess:
    def __init__(self, path=None):
        self.path = Path(path) if path else default_data_dir() / "console-access.json"
        self._lock = threading.RLock()
        self._stamp = None
        self._enabled = False
        self._networks = []
        self.load_error = False

    def _refresh(self):
        try:
            stat = self.path.stat()
            stamp = (stat.st_mtime_ns, stat.st_size)
        except FileNotFoundError:
            stamp = None
        if stamp == self._stamp and self._stamp is not None:
            return
        self._stamp = stamp
        if stamp is None:
            self._enabled, self._networks, self.load_error = False, [], False
            return
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if (not isinstance(document, dict) or set(document) != {"enabled", "networks"} or
                    not isinstance(document["enabled"], bool) or not isinstance(document["networks"], list) or
                    any(canonical_network(item) != item for item in document["networks"]) or
                    len(document["networks"]) != len(set(document["networks"])) or
                    len(document["networks"]) > LIMIT):
                raise ValueError("invalid console access list")
            self._enabled = document["enabled"]
            self._networks = list(document["networks"])
            self.load_error = False
        except (OSError, ValueError, TypeError):
            # A damaged file must not lock everyone out: treat it as off.
            self._enabled, self._networks, self.load_error = False, [], True

    def _save(self, enabled, networks):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".console-access-", dir=self.path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                output.write(json.dumps({"enabled": enabled, "networks": networks}) + "\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(name, self.path)
        finally:
            Path(name).unlink(missing_ok=True)
        self._stamp = None
        self._refresh()

    def _matches(self, address, networks):
        address = _address(address)
        if address is None:
            return False
        if address.is_loopback:
            return True
        return any(address in ipaddress.ip_network(item) for item in networks)

    def enabled(self):
        with self._lock:
            self._refresh()
            return self._enabled

    def networks(self):
        with self._lock:
            self._refresh()
            return list(self._networks)

    def allows(self, address):
        with self._lock:
            self._refresh()
            return not self._enabled or self._matches(address, self._networks)

    def listed(self, address):
        """Whether the list (ignoring the switch) covers ``address``."""
        with self._lock:
            self._refresh()
            return self._matches(address, self._networks)

    def set_enabled(self, enabled, current=None):
        with self._lock:
            self._refresh()
            if enabled and current is not None and not self._matches(current, self._networks):
                raise ConsoleAccessError("console_access_need_current")
            self._save(bool(enabled), self._networks)

    def add(self, value):
        network = canonical_network(value)
        with self._lock:
            self._refresh()
            if network not in self._networks:
                if len(self._networks) >= LIMIT:
                    raise ConsoleAccessError("console_access_full")
                self._save(self._enabled, self._networks + [network])
        return network

    def remove(self, value, current=None):
        network = canonical_network(value)
        with self._lock:
            self._refresh()
            if network not in self._networks:
                raise ConsoleAccessError("console_access_invalid")
            remaining = [item for item in self._networks if item != network]
            if self._enabled and current is not None and not self._matches(current, remaining):
                raise ConsoleAccessError("console_access_keep_current")
            self._save(self._enabled, remaining)
        return network


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv not in (["status"], ["disable"]):
        raise SystemExit("usage: console_access.py status|disable")
    access = ConsoleAccess()
    if argv == ["disable"]:
        access.set_enabled(False)
        print("Console access limit turned off; every address can reach the console again.")
        return 0
    print(f"enabled: {'yes' if access.enabled() else 'no'}")
    for item in access.networks():
        print(item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
