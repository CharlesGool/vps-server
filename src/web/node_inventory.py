"""Pure, offline versioned sing-box inventory import and rendering.

The caller owns durable, root-only storage and must persist the migration namespace
before import; this module neither reads nor writes installed configuration.
"""

from __future__ import annotations

import base64
import binascii
import calendar
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Any, TypedDict
import uuid


PROTOCOLS = frozenset({"anytls", "vmess", "vless", "trojan", "shadowsocks"})
MODULE_PROTOCOLS = {"anytls": frozenset({"anytls"}),
                    "proxy": PROTOCOLS}
_NAME = re.compile(r"[^\W_][\w ._-]{0,63}\Z", re.UNICODE)
_INTERVAL = re.compile(r"every:([1-9][0-9]{0,3}):(days|months|years):(-|[1-9]|[12][0-9]|3[01]|[0-1][0-9]-[0-3][0-9])\Z")


def reset_interval(mode: str) -> tuple[int, str, str] | None:
    """Decode a recurring schedule while keeping version-one inventories readable."""
    if not isinstance(mode, str):
        return None
    match = _INTERVAL.fullmatch(mode)
    if match is None:
        return None
    count, unit, anchor = match.groups()
    if (unit == "days" and anchor != "-") or (unit == "months" and not anchor.isdigit()) or \
            (unit == "years" and (not re.fullmatch(r"\d{2}-\d{2}", anchor) or
                                  not _valid_month_day(anchor))):
        return None
    return int(count), unit, anchor


def _valid_month_day(value: str) -> bool:
    month, day = map(int, value.split("-"))
    return 1 <= month <= 12 and 1 <= day <= calendar.monthrange(2000, month)[1]


def advance_reset_interval(due: datetime, mode: str) -> datetime:
    parsed = reset_interval(mode)
    if parsed is None:
        raise InvalidInventory("invalid reset interval")
    count, unit, anchor = parsed
    try:
        if unit == "days":
            return due + timedelta(days=count)
        if unit == "months":
            index = due.year * 12 + due.month - 1 + count
            year, month_index = divmod(index, 12)
            month = month_index + 1
            return due.replace(year=year, month=month,
                               day=1, hour=0, minute=0, second=0, microsecond=0)
        month, day = map(int, anchor.split("-"))
        year = due.year + count
        return due.replace(year=year, month=month,
                           day=min(day, calendar.monthrange(year, month)[1]))
    except (ValueError, OverflowError) as exc:
        raise InvalidInventory("reset interval exceeds supported dates") from exc


class InvalidInventory(ValueError):
    """An input cannot be safely represented or merged."""


class Node(TypedDict):
    id: str
    number: int
    name: str
    protocol: str
    port: int
    inbound: dict[str, Any]
    enabled: bool
    cap_bytes: int | None
    cap_action: str
    upload_limit_bps: int | None
    download_limit_bps: int | None
    expiry_count: int | None
    expiry_unit: str | None
    expires_at: str | None
    reset_mode: str
    next_reset_at: str | None
    upload_bytes: int
    download_bytes: int
    total_upload_bytes: int
    total_download_bytes: int
    counter_epoch: int


class Inventory(TypedDict):
    version: int
    next_number: int
    migration_namespace: str
    migration_hashes: dict[str, str]
    base_config: dict[str, Any]
    nodes: list[Node]


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidInventory("duplicate JSON key")
        result[key] = value
    return result


def _document(value: bytes | str | dict[str, Any]) -> dict[str, Any]:
    try:
        if isinstance(value, (bytes, str)):
            value = json.loads(value, object_pairs_hook=_pairs,
                               parse_constant=lambda _: (_ for _ in ()).throw(InvalidInventory("nonfinite JSON")))
        # A JSON round trip rejects arbitrary Python objects, NaN, cycles and non-string keys.
        value = json.loads(json.dumps(value, allow_nan=False), object_pairs_hook=_pairs)
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise InvalidInventory("invalid JSON document") from exc
    if not isinstance(value, dict):
        raise InvalidInventory("expected JSON object")
    return value


def _uuid(value: str) -> uuid.UUID:
    try:
        parsed = uuid.UUID(value)
        if str(parsed) != value:
            raise ValueError("noncanonical UUID")
        return parsed
    except (TypeError, AttributeError, ValueError) as exc:
        raise InvalidInventory("expected canonical UUID") from exc


def _inbound(inbound: Any, module: str | None = None) -> tuple[str, int, str]:
    if not isinstance(inbound, dict):
        raise InvalidInventory("inbound must be an object")
    protocol, port, tag = (inbound.get(k) for k in ("type", "listen_port", "tag"))
    if not isinstance(protocol, str) or protocol not in PROTOCOLS or (module is not None and protocol not in MODULE_PROTOCOLS[module]):
        raise InvalidInventory("unknown or misplaced protocol")
    if type(port) is not int or not 1 <= port <= 65535:
        raise InvalidInventory("invalid inbound port")
    if not isinstance(tag, str) or not tag or tag.strip() != tag:
        raise InvalidInventory("invalid inbound tag")
    if protocol == "shadowsocks":
        credential = inbound.get("password")
        if not isinstance(inbound.get("method"), str) or not inbound["method"]:
            raise InvalidInventory("missing shadowsocks method")
    else:
        users = inbound.get("users")
        if not isinstance(users, list) or len(users) != 1 or not isinstance(users[0], dict):
            raise InvalidInventory("expected one inbound user")
        credential = users[0].get("uuid" if protocol in ("vmess", "vless") else "password")
    if not isinstance(credential, str) or not credential:
        raise InvalidInventory("missing inbound credential")
    if protocol in ("vmess", "vless"):
        try:
            parsed = uuid.UUID(credential)
        except ValueError as exc:
            raise InvalidInventory("invalid inbound UUID") from exc
        if parsed.int == 0:
            raise InvalidInventory("zero inbound UUID")
    if protocol == "shadowsocks" and inbound["method"] == "2022-blake3-aes-128-gcm":
        try:
            key = base64.b64decode(credential, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise InvalidInventory("invalid shadowsocks key") from exc
        if len(key) != 16 or base64.b64encode(key).decode("ascii") != credential:
            raise InvalidInventory("shadowsocks key must be canonical 16-byte base64")
    tls = inbound.get("tls")
    if tls is not None and (not isinstance(tls, dict) or
                            any(not isinstance(tls.get(k), str) or not tls[k]
                                for k in ("certificate_path", "key_path"))):
        raise InvalidInventory("invalid TLS certificate references")
    if protocol in ("anytls", "vmess", "vless", "trojan") and tls is None:
        raise InvalidInventory("missing TLS certificate references")
    return protocol, port, tag


def _base(document: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(document.get("inbounds"), list) or not isinstance(document.get("outbounds"), list):
        raise InvalidInventory("missing inbounds/outbounds")
    base = {k: v for k, v in document.items() if k != "inbounds"}
    outbounds = base["outbounds"]
    if not outbounds or any(not isinstance(item, dict) or
                           not isinstance(item.get("tag"), str) or not item["tag"] or
                           not isinstance(item.get("type"), str) for item in outbounds):
        raise InvalidInventory("invalid outbounds")
    tags = [item["tag"] for item in outbounds]
    if len(tags) != len(set(tags)):
        raise InvalidInventory("duplicate outbound tags")
    return base


def _hash(document: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(document, sort_keys=True, ensure_ascii=False,
                                   separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_inventory(inventory: Inventory) -> None:
    """Reject malformed state, duplicate IDs/ports/tags, and invalid metadata."""
    if not isinstance(inventory, dict) or set(inventory) != {"version", "next_number", "migration_namespace", "migration_hashes", "base_config", "nodes"} or type(inventory["version"]) is not int or inventory["version"] not in (1, 2):
        raise InvalidInventory("unsupported inventory schema")
    legacy = inventory["version"] == 1
    if type(inventory["next_number"]) is not int or inventory["next_number"] < 1:
        raise InvalidInventory("invalid next node number")
    namespace = _uuid(inventory["migration_namespace"])
    hashes = inventory["migration_hashes"]
    if not isinstance(hashes, dict) or not set(hashes) <= set(MODULE_PROTOCOLS) or any(not isinstance(h, str) or not re.fullmatch(r"[0-9a-f]{64}", h) for h in hashes.values()):
        raise InvalidInventory("invalid migration hashes")
    base = _document(inventory["base_config"])
    if "inbounds" in base:
        raise InvalidInventory("base must not contain inbounds")
    _base({**base, "inbounds": []})
    nodes = inventory["nodes"]
    if not isinstance(nodes, list):
        raise InvalidInventory("nodes must be a list")
    ids, numbers, tags, ports = set(), set(), set(), set()
    outbound_tags = {item["tag"] for item in base["outbounds"]}
    for node in nodes:
        expected = (set(Node.__annotations__) - {"cap_action", "upload_limit_bps", "download_limit_bps",
                                                "expiry_count", "expiry_unit"}) if legacy else set(Node.__annotations__)
        if not isinstance(node, dict) or set(node) != expected:
            raise InvalidInventory("invalid node fields")
        identifier = _uuid(node["id"])
        number = node["number"]
        if type(number) is not int or number < 1 or number in numbers:
            raise InvalidInventory("invalid or duplicate node number")
        if not isinstance(node["name"], str) or not _NAME.fullmatch(node["name"]) or node["name"] != node["name"].strip():
            raise InvalidInventory("invalid node name")
        protocol, port, tag = _inbound(node["inbound"])
        if node["protocol"] != protocol or type(node["port"]) is not int or node["port"] != port or type(node["enabled"]) is not bool:
            raise InvalidInventory("node/inbound mismatch")
        cap = node["cap_bytes"]
        if cap is not None and (type(cap) is not int or cap <= 0):
            raise InvalidInventory("invalid cap")
        if not legacy and node["cap_action"] not in ("throttle", "block"):
            raise InvalidInventory("invalid traffic cap action")
        if not legacy:
            for key in ("upload_limit_bps", "download_limit_bps"):
                value = node[key]
                if value is not None and (type(value) is not int or not 1_000 <= value <= 10_000_000_000_000):
                    raise InvalidInventory("invalid directional speed limit")
            count, unit, expiry = node["expiry_count"], node["expiry_unit"], node["expires_at"]
            if (count, unit, expiry) != (None, None, None) and \
                    (type(count) is not int or not 1 <= count <= 9999 or
                     unit not in ("days", "months", "years") or expiry is None):
                raise InvalidInventory("invalid validity period")
        for key in ("expires_at", "next_reset_at"):
            value = node[key]
            if value is not None:
                if not isinstance(value, str):
                    raise InvalidInventory("invalid node date")
                try:
                    date = datetime.fromisoformat(value)
                except ValueError as exc:
                    raise InvalidInventory("invalid node date") from exc
                if date.tzinfo is None or date.utcoffset() != timezone.utc.utcoffset(date):
                    raise InvalidInventory("node date must be UTC")
        if ((node["reset_mode"] not in ("none", "monthly", "once") and
             reset_interval(node["reset_mode"]) is None) or
                (node["reset_mode"] == "none") != (node["next_reset_at"] is None)):
            raise InvalidInventory("invalid reset schedule")
        if node["reset_mode"] == "monthly" and node["next_reset_at"] is not None:
            date = datetime.fromisoformat(node["next_reset_at"])
            if date.day != 1 or date.hour or date.minute or date.second or date.microsecond:
                raise InvalidInventory("monthly reset must start at 00:00 UTC on day one")
        if any(type(node[k]) is not int or node[k] < 0 for k in
               ("upload_bytes", "download_bytes", "total_upload_bytes", "total_download_bytes", "counter_epoch")):
            raise InvalidInventory("invalid counters")
        if node["upload_bytes"] > node["total_upload_bytes"] or \
                node["download_bytes"] > node["total_download_bytes"]:
            raise InvalidInventory("period usage exceeds lifetime usage")
        if identifier in ids or tag in tags or tag in outbound_tags or port in ports:
            raise InvalidInventory("duplicate node identity, port or tag")
        ids.add(identifier)
        numbers.add(number)
        tags.add(tag)
        ports.add(port)
    if numbers and inventory["next_number"] <= max(numbers):
        raise InvalidInventory("next node number must exceed existing numbers")


def migrate_inventory(inventory: Inventory) -> Inventory:
    """Remove the retired deadline limit and default old caps to throttling."""
    validate_inventory(inventory)
    result = copy.deepcopy(inventory)
    if result["version"] == 1:
        for node in result["nodes"]:
            node["expires_at"] = None
            node["cap_action"] = "throttle"
            node["upload_limit_bps"] = None
            node["download_limit_bps"] = None
            node["expiry_count"] = None
            node["expiry_unit"] = None
        result["version"] = 2
    validate_inventory(result)
    return result


def import_legacy(anytls: bytes | str | dict[str, Any] | None,
                  proxy: bytes | str | dict[str, Any] | None, *,
                  migration_namespace: str, existing: Inventory | None = None) -> Inventory:
    """Import a snapshot once; repeated identical snapshots return existing state unchanged.

    A namespace must be independently generated and durably persisted by the caller.
    Different service bases are ambiguous and must be reconciled outside this module.
    """
    namespace = _uuid(migration_namespace)
    documents = {module: _document(value) for module, value in
                 (("anytls", anytls), ("proxy", proxy)) if value is not None}
    if not documents:
        raise InvalidInventory("no legacy configuration")
    bases = [_base(doc) for doc in documents.values()]
    if any(base != bases[0] for base in bases[1:]):
        raise InvalidInventory("legacy service base configurations differ")
    for module, document in documents.items():
        for inbound in document["inbounds"]:
            _inbound(inbound, module)
    hashes = {module: _hash(doc) for module, doc in documents.items()}
    if existing is not None:
        existing = migrate_inventory(existing)
        if existing["migration_namespace"] != str(namespace) or existing["migration_hashes"] != hashes:
            raise InvalidInventory("legacy snapshot differs from completed migration")
        return copy.deepcopy(existing)
    nodes = []
    valid_names = {inbound["tag"] for document in documents.values()
                   for inbound in document["inbounds"]
                   if _NAME.fullmatch(inbound["tag"]) and inbound["tag"] == inbound["tag"].strip()}
    used_names = set(valid_names)
    for module, document in documents.items():
        for inbound in document["inbounds"]:
            protocol, port, tag = _inbound(inbound, module)
            identifier = uuid.uuid5(namespace, f"{module}:{tag}")
            name = tag
            if name not in valid_names:
                fallback = f"legacy-{identifier.hex}"
                name = fallback
                suffix = 2
                while name in used_names:
                    name = f"{fallback}-{suffix}"
                    suffix += 1
                used_names.add(name)
            nodes.append(Node(id=str(identifier),
                              number=len(nodes) + 1,
                              name=name, protocol=protocol, port=port,
                              inbound=copy.deepcopy(inbound), enabled=True,
                              cap_bytes=None, cap_action="throttle",
                              upload_limit_bps=None, download_limit_bps=None,
                              expiry_count=None, expiry_unit=None, expires_at=None,
                              reset_mode="none", next_reset_at=None,
                              upload_bytes=0, download_bytes=0,
                              total_upload_bytes=0, total_download_bytes=0,
                              counter_epoch=0))
    inventory = Inventory(version=2, next_number=len(nodes) + 1,
                          migration_namespace=str(namespace),
                          migration_hashes=hashes, base_config=copy.deepcopy(bases[0]),
                          nodes=nodes)
    validate_inventory(inventory)
    return inventory


def render_config(inventory: Inventory) -> dict[str, Any]:
    """Return one config with only enabled inbounds; never mutate the inventory."""
    validate_inventory(inventory)
    result = copy.deepcopy(inventory["base_config"])
    result["inbounds"] = [copy.deepcopy(node["inbound"]) for node in inventory["nodes"]
                          if node["enabled"]]
    return result
