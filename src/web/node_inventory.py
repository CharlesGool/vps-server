"""Pure, offline versioned sing-box inventory import and rendering.

The caller owns durable, root-only storage and must persist the migration namespace
before import; this module neither reads nor writes installed configuration.
"""

import base64
import binascii
import copy
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, TypedDict
import uuid


PROTOCOLS = frozenset({"anytls", "vmess", "vless", "trojan", "shadowsocks"})
MODULE_PROTOCOLS = {"anytls": frozenset({"anytls"}),
                    "proxy": PROTOCOLS - {"anytls"}}
_NAME = re.compile(r"[^\W_][\w ._-]{0,63}\Z", re.UNICODE)


class InvalidInventory(ValueError):
    """An input cannot be safely represented or merged."""


class Node(TypedDict):
    id: str
    name: str
    protocol: str
    port: int
    inbound: dict[str, Any]
    enabled: bool
    cap_bytes: int | None
    expires_at: str | None
    upload_bytes: int
    download_bytes: int
    counter_epoch: int


class Inventory(TypedDict):
    version: int
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
    if not isinstance(inventory, dict) or set(inventory) != {"version", "migration_namespace", "migration_hashes", "base_config", "nodes"} or type(inventory["version"]) is not int or inventory["version"] != 1:
        raise InvalidInventory("unsupported inventory schema")
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
    ids, tags, ports, names = set(), set(), set(), set()
    outbound_tags = {item["tag"] for item in base["outbounds"]}
    for node in nodes:
        if not isinstance(node, dict) or set(node) != set(Node.__annotations__):
            raise InvalidInventory("invalid node fields")
        identifier = _uuid(node["id"])
        if not isinstance(node["name"], str) or not _NAME.fullmatch(node["name"]) or node["name"] != node["name"].strip():
            raise InvalidInventory("invalid node name")
        protocol, port, tag = _inbound(node["inbound"])
        if node["protocol"] != protocol or type(node["port"]) is not int or node["port"] != port or type(node["enabled"]) is not bool:
            raise InvalidInventory("node/inbound mismatch")
        cap = node["cap_bytes"]
        if cap is not None and (type(cap) is not int or cap <= 0):
            raise InvalidInventory("invalid cap")
        expiry = node["expires_at"]
        if expiry is not None:
            if not isinstance(expiry, str):
                raise InvalidInventory("invalid expiry")
            try:
                date = datetime.fromisoformat(expiry)
            except ValueError as exc:
                raise InvalidInventory("invalid expiry") from exc
            if date.tzinfo is None or date.utcoffset() != timezone.utc.utcoffset(date):
                raise InvalidInventory("expiry must be UTC")
        if any(type(node[k]) is not int or node[k] < 0 for k in ("upload_bytes", "download_bytes", "counter_epoch")):
            raise InvalidInventory("invalid counters")
        if identifier in ids or tag in tags or tag in outbound_tags or port in ports or node["name"] in names:
            raise InvalidInventory("duplicate node identity, name, port or tag")
        ids.add(identifier)
        tags.add(tag)
        ports.add(port)
        names.add(node["name"])


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
        validate_inventory(existing)
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
                              name=name, protocol=protocol, port=port,
                              inbound=copy.deepcopy(inbound), enabled=True,
                              cap_bytes=None, expires_at=None, upload_bytes=0,
                              download_bytes=0, counter_epoch=0))
    inventory = Inventory(version=1, migration_namespace=str(namespace),
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
