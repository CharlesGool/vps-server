#!/usr/bin/env python3
"""Offline SHA-256 check of artifacts listed in dependencies.lock.json.

This checks checkout bytes, not upstream identity or distro package versions.
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

LANGUAGE_TAGS = {"en": "en", "zh_cn": "zh-CN", "zh_tw": "zh-TW", "zh_hk": "zh-HK",
                 "hi": "hi", "es": "es", "ar": "ar", "fr": "fr"}
LANGUAGE = LANGUAGE_TAGS.get(os.environ.get("VPSSRV_DEFAULT_LANG", "en"), "en")
MESSAGES = json.loads((ROOT / "lang" / "verify_dependencies" / f"{LANGUAGE}.json").read_text(encoding="utf-8"))


def _t(key, **fields):
    return MESSAGES[key].format(**fields)


def verify(lock_file=ROOT / "config/dependencies.lock.json", root=ROOT):
    lock = json.loads(Path(lock_file).read_text(encoding="utf-8"))
    if lock.get("schema_version") != 1 or not isinstance(lock.get("artifacts"), list):
        raise ValueError(_t("unsupported_list"))
    if not lock["artifacts"]:
        raise ValueError(_t("empty_list"))

    errors = []
    seen = set()
    root = Path(root).resolve()
    for entry in lock["artifacts"]:
        name = entry["path"]
        expected = entry["sha256"]
        if (not isinstance(name, str) or not name or name in seen
                or not isinstance(expected, str)
                or re.fullmatch(r"[0-9a-f]{64}", expected) is None):
            raise ValueError(_t("invalid_path_hash"))
        seen.add(name)
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            errors.append(_t("missing_artifact", name=name))
            continue
        digest = hashlib.sha256()
        with path.open("rb") as artifact:
            for block in iter(lambda: artifact.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != expected:
            errors.append(_t("hash_mismatch", name=name))
        else:
            print(_t("artifact_ok", name=name, hash=expected))
    for error in errors:
        print(error, file=sys.stderr)
    return not errors


if __name__ == "__main__":
    try:
        sys.exit(0 if verify() else 1)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(_t("invalid_lock", error=exc), file=sys.stderr)
        sys.exit(1)
