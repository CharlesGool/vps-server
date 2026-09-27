"""Pure offline ID-based inventory changes and fail-closed effective rendering.

The caller supplies a consistent snapshot of externally reserved ports. Effective
rendering never changes the persisted desired ``enabled`` state.
"""

import base64
import copy
from datetime import datetime, timezone
import secrets
import uuid

from node_inventory import InvalidInventory, PROTOCOLS, render_config, validate_inventory


_EDITABLE = frozenset({"name", "port", "credential", "cap_bytes", "expires_at",
                       "reset_mode", "next_reset_at"})
_UUID_PROTOCOLS = frozenset({"vmess", "vless"})


def _now(value):
    if (not isinstance(value, datetime) or value.tzinfo is None or
            value.utcoffset() != timezone.utc.utcoffset(value)):
        raise InvalidInventory("now must be a UTC datetime")
    return value


def _reserved(value):
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise InvalidInventory("reserved port snapshot required")
    if any(type(port) is not int or not 1 <= port <= 65535 for port in value):
        raise InvalidInventory("invalid reserved port")
    return set(value)


def _node(inventory, identifier):
    if not isinstance(identifier, str):
        raise InvalidInventory("invalid node ID")
    matches = [node for node in inventory["nodes"] if node["id"] == identifier]
    if len(matches) != 1:
        raise InvalidInventory("node ID not found")
    return matches[0]


def _credential(node):
    inbound = node["inbound"]
    if node["protocol"] == "shadowsocks":
        return inbound["password"]
    return inbound["users"][0]["uuid" if node["protocol"] in _UUID_PROTOCOLS else "password"]


def _set_credential(node, value):
    if not isinstance(value, str) or not value:
        raise InvalidInventory("invalid credential")
    protocol = node["protocol"]
    if protocol in _UUID_PROTOCOLS:
        try:
            parsed = uuid.UUID(value)
        except (ValueError, AttributeError) as exc:
            raise InvalidInventory("invalid credential UUID") from exc
        if parsed.int == 0 or str(parsed) != value:
            raise InvalidInventory("credential UUID must be canonical and nonzero")
    elif protocol == "shadowsocks":
        if node["inbound"]["method"] != "2022-blake3-aes-128-gcm":
            raise InvalidInventory("unsupported shadowsocks method")
        try:
            key = base64.b64decode(value, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise InvalidInventory("invalid shadowsocks key") from exc
        if len(key) != 16 or base64.b64encode(key).decode("ascii") != value:
            raise InvalidInventory("shadowsocks requires a canonical 16-byte key")
    elif not 8 <= len(value) <= 128 or not all(33 <= ord(c) <= 126 for c in value):
        raise InvalidInventory("password must be 8-128 printable non-space ASCII characters")
    if protocol == "shadowsocks":
        node["inbound"]["password"] = value
    else:
        node["inbound"]["users"][0]["uuid" if protocol in _UUID_PROTOCOLS else "password"] = value


def _unique_credential(inventory, node):
    value = _credential(node)
    if any(other is not node and _credential(other) == value for other in inventory["nodes"]):
        raise InvalidInventory("credential already in use")


def _port_available(inventory, port, reserved, current=None):
    if type(port) is not int or not 1 <= port <= 65535:
        raise InvalidInventory("invalid port")
    if port in reserved or any(node is not current and node["port"] == port for node in inventory["nodes"]):
        raise InvalidInventory("port already in use or reserved")


def _expiry(value):
    if value is None:
        return
    if not isinstance(value, str):
        raise InvalidInventory("invalid expiry")
    try:
        date = datetime.fromisoformat(value)
    except ValueError as exc:
        raise InvalidInventory("invalid expiry") from exc
    if date.tzinfo is None or date.utcoffset() != timezone.utc.utcoffset(date):
        raise InvalidInventory("expiry must be UTC")


def _effective(node, now):
    # Quota and date limits change bandwidth policy, never inbound presence.
    return node["enabled"]


def _new_uuid(factory):
    value = factory()
    if not isinstance(value, uuid.UUID) or value.int == 0:
        raise InvalidInventory("UUID generator returned an invalid value")
    return str(value)


def create_node(inventory, protocol, name, port, *, reserved_ports, prototype_id=None,
                cap_bytes=None, expires_at=None, reset_mode="none", next_reset_at=None,
                uuid_factory=uuid.uuid4):
    """Copy one same-protocol inbound, replacing its identity and secret."""
    validate_inventory(inventory)
    reserved = _reserved(reserved_ports)
    if protocol not in PROTOCOLS:
        raise InvalidInventory("unsupported protocol")
    _port_available(inventory, port, reserved)
    templates = [node for node in inventory["nodes"] if node["protocol"] == protocol]
    if prototype_id is not None:
        prototype = _node(inventory, prototype_id)
        if prototype["protocol"] != protocol:
            raise InvalidInventory("prototype protocol differs")
    elif templates:
        prototype = templates[0]
    else:
        raise InvalidInventory("same-protocol prototype required")
    if protocol == "shadowsocks" and prototype["inbound"]["method"] != "2022-blake3-aes-128-gcm":
        raise InvalidInventory("unsupported shadowsocks method")
    # Existing TLS references are copied, never synthesized or read from disk.
    candidate = copy.deepcopy(inventory)
    for _ in range(32):
        identifier = _new_uuid(uuid_factory)
        tag = "node-" + identifier.replace("-", "")
        if (all(n["id"] != identifier and _credential(n) != identifier and
                n["inbound"]["tag"] != tag and
                (n["protocol"] == "shadowsocks" or n["inbound"]["users"][0].get("name") != tag)
                for n in candidate["nodes"]) and
            all(item["tag"] != tag for item in candidate["base_config"]["outbounds"])):
            break
    else:
        raise InvalidInventory("cannot generate unique node identity")
    inbound = copy.deepcopy(prototype["inbound"])
    inbound["tag"] = tag
    inbound["listen_port"] = port
    if protocol != "shadowsocks":
        inbound["users"][0]["name"] = tag
    node = {"id": identifier, "number": candidate["next_number"],
            "name": name, "protocol": protocol, "port": port,
            "inbound": inbound, "enabled": True, "cap_bytes": cap_bytes,
            "expires_at": expires_at, "reset_mode": reset_mode,
            "next_reset_at": next_reset_at,
            "upload_bytes": 0, "download_bytes": 0,
            "total_upload_bytes": 0, "total_download_bytes": 0,
            "counter_epoch": 0}
    candidate["nodes"].append(node)
    candidate["next_number"] += 1
    for _ in range(32):
        secret = (base64.b64encode(secrets.token_bytes(16)).decode("ascii") if protocol == "shadowsocks"
                  else _new_uuid(uuid_factory) if protocol in _UUID_PROTOCOLS
                  else secrets.token_urlsafe(32))
        _set_credential(node, secret)
        if secret != identifier and all(_credential(other) != secret and other["id"] != secret
                                        for other in candidate["nodes"][:-1]):
            break
    else:
        raise InvalidInventory("cannot generate unique credential")
    validate_inventory(candidate)
    return candidate


def edit_node(inventory, identifier, changes, *, reserved_ports):
    """Edit only public metadata, port and credential; counters and ID are immutable."""
    validate_inventory(inventory)
    reserved = _reserved(reserved_ports)
    if not isinstance(changes, dict) or not changes or not set(changes) <= _EDITABLE:
        raise InvalidInventory("unsupported edit fields")
    candidate = copy.deepcopy(inventory)
    node = _node(candidate, identifier)
    if "port" in changes:
        port = changes["port"]
        if port != node["port"]:
            _port_available(candidate, port, reserved, node)
        elif port in reserved:
            raise InvalidInventory("port externally reserved")
        node["port"] = port
        node["inbound"]["listen_port"] = port
    if "credential" in changes:
        _set_credential(node, changes["credential"])
        _unique_credential(candidate, node)
    for key in ("name", "cap_bytes", "expires_at", "reset_mode", "next_reset_at"):
        if key in changes:
            node[key] = changes[key]
    _expiry(node["expires_at"])
    if node["cap_bytes"] is not None and (type(node["cap_bytes"]) is not int or
                                          node["cap_bytes"] <= 0):
        raise InvalidInventory("cap must be positive")
    validate_inventory(candidate)
    return candidate


def set_enabled_by_id(inventory, identifier, enabled, *, now):
    validate_inventory(inventory)
    _now(now)
    if type(enabled) is not bool:
        raise InvalidInventory("enabled must be boolean")
    candidate = copy.deepcopy(inventory)
    node = _node(candidate, identifier)
    if enabled:
        node["enabled"] = True
    else:
        node["enabled"] = False
    validate_inventory(candidate)
    return candidate


def render_effective_config(inventory, *, now):
    """Render enabled inbounds; caps and dates are enforced by a shaper."""
    validate_inventory(inventory)
    _now(now)
    candidate = copy.deepcopy(inventory)
    for node in candidate["nodes"]:
        node["enabled"] = _effective(node, now)
    return render_config(candidate)
