"""Persistent, operator-supplied label for distinguishing installed servers."""

import os
from pathlib import Path
import unicodedata


def read_server_label(data_dir):
    try:
        value = (Path(data_dir) / "server-label.txt").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""
    return value if valid_server_label(value) else ""


def valid_server_label(value):
    return (len(value) <= 40 and
            all(unicodedata.category(character)[0] in "LNM" or character in " -_."
                for character in value) and
            (not value or value == value.strip()))


def save_server_label(data_dir, value):
    value = unicodedata.normalize("NFC", value).strip()
    if not valid_server_label(value):
        raise ValueError("invalid server label")
    target = Path(data_dir) / "server-label.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".tmp")
    temp.write_text(value + "\n", encoding="utf-8")
    os.chmod(temp, 0o600)
    os.replace(temp, target)
