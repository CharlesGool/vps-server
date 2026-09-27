"""Persistent identity and accounting state for the installed legacy node units.

The legacy sing-box configurations remain the serving source. This module
imports them once, then refuses to silently reinterpret an externally changed
inbound as the same node. Mutating callers hold the shared node lock.
"""

import copy
import json
import os
from pathlib import Path
import stat
import tempfile
import uuid

from node_inventory import InvalidInventory, import_legacy, validate_inventory


STATE_PATH = Path("/etc/vps-server-nodes/state.json")
CONFIG_PATHS = {"anytls": Path("/etc/vps-server-anytls/config.json"),
                "proxy": Path("/etc/vps-server-proxy/config.json")}


def _read_json(path):
    path = Path(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise InvalidInventory("unsafe node state or configuration file")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise InvalidInventory("invalid node state or configuration JSON") from exc


def _installed(config_paths):
    return {module: _read_json(path) for module, path in config_paths.items()}


def _assert_matches(inventory, installed):
    for module, document in installed.items():
        expected = [node["inbound"] for node in inventory["nodes"]
                    if (node["protocol"] == "anytls") == (module == "anytls")]
        actual = [] if document is None else document.get("inbounds") if isinstance(document, dict) else None
        if actual != expected:
            raise InvalidInventory("installed node configuration differs from inventory")
    # A module may remain installed with zero listeners after its last node
    # is deleted. Its empty inbounds list still has to match the inventory.


def read_inventory(*, state_path=STATE_PATH, config_paths=CONFIG_PATHS,
                   check_installed=True):
    inventory = _read_json(state_path)
    if inventory is None:
        return None
    validate_inventory(inventory)
    if check_installed:
        _assert_matches(inventory, _installed(config_paths))
    return inventory


def write_json(value, path):
    """Atomically replace a root-owned JSON file; caller serializes writes."""
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".node-state-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(value, output, ensure_ascii=False, separators=(",", ":"))
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def write_inventory(inventory, *, state_path=STATE_PATH):
    validate_inventory(inventory)
    write_json(inventory, state_path)


def initialize_inventory(*, state_path=STATE_PATH, config_paths=CONFIG_PATHS):
    """Idempotent import, allowing a newly installed second module to join."""
    current = read_inventory(state_path=state_path, config_paths=config_paths,
                             check_installed=False)
    if current is not None:
        installed = _installed(config_paths)
        additions = []
        for module in ("anytls", "proxy"):
            existing = [node for node in current["nodes"]
                        if (node["protocol"] == "anytls") == (module == "anytls")]
            document = installed[module]
            if existing:
                if not isinstance(document, dict) or document.get("inbounds") != \
                        [node["inbound"] for node in existing]:
                    raise InvalidInventory("installed node configuration differs from inventory")
            elif document is not None:
                imported = import_legacy(document if module == "anytls" else None,
                                         document if module == "proxy" else None,
                                         migration_namespace=current["migration_namespace"])
                if imported["base_config"] != current["base_config"]:
                    raise InvalidInventory("new module base configuration differs")
                additions.extend(imported["nodes"])
                current["migration_hashes"].update(imported["migration_hashes"])
        if additions:
            for node in additions:
                node["number"] = current["next_number"]
                current["next_number"] += 1
                current["nodes"].append(node)
            validate_inventory(current)
            write_inventory(current, state_path=state_path)
        _assert_matches(current, installed)
        return current
    documents = _installed(config_paths)
    inventory = import_legacy(documents["anytls"], documents["proxy"],
                              migration_namespace=str(uuid.uuid4()))
    write_inventory(inventory, state_path=state_path)
    return copy.deepcopy(inventory)
