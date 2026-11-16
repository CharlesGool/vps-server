#!/usr/bin/env python3
"""Who may release for this host: a pinned Ed25519 key and the rules around it.

A release is trusted when ``SHA256SUMS`` carries a valid signature by the key
this host has pinned (``<state dir>/release-key.pub``). The installer pins the
key a package ships in ``config/release-key.pub`` the first time it sees one;
after that a package must be signed by that key. A package without a key, or
with a different one, is refused until the operator accepts the change by its
fingerprint. Forks can sign with their own key; a host pinned to one key never
installs the other's builds.

Standard library only (see ``ed25519.py``), so it runs on a bare host. Used by
``deploy/install.sh`` (``check``/``pin``) and by ``upgrade.py``.
"""

import argparse
import base64
import hashlib
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ed25519  # noqa: E402

PINNED_NAME = "release-key.pub"
SHIPPED = Path("config") / "release-key.pub"
KEY_LABEL = "ed25519"
SUMS_LINE = re.compile(r"([0-9a-f]{64}) [ *]([A-Za-z0-9._-]+)")


class TrustError(Exception):
    pass


def format_key(raw):
    return f"{KEY_LABEL} {base64.b64encode(raw).decode('ascii')}\n"


def parse_key(text):
    """The 32 raw bytes of a public key written as ``ed25519 <base64> [comment]``."""
    fields = text.split()
    if len(fields) < 2 or fields[0] != KEY_LABEL:
        raise TrustError("not an ed25519 public key")
    try:
        raw = base64.b64decode(fields[1], validate=True)
    except ValueError:
        raise TrustError("not an ed25519 public key") from None
    if len(raw) != 32:
        raise TrustError("not an ed25519 public key")
    return raw


def fingerprint(raw):
    """Short form to compare by eye: the first 16 bytes of the SHA-256, in groups of four hex digits."""
    digest = hashlib.sha256(raw).hexdigest()[:32]
    return ":".join(digest[i:i + 4] for i in range(0, 32, 4))


def same_fingerprint(typed, raw):
    """True when ``typed`` (any case, with or without colons) names ``raw``."""
    cleaned = re.sub(r"[^0-9a-f]", "", typed.lower())
    return len(cleaned) >= 16 and cleaned == fingerprint(raw).replace(":", "")


def pinned_path(state_dir):
    return Path(state_dir) / PINNED_NAME


def read_pinned(state_dir):
    try:
        return parse_key(pinned_path(state_dir).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def read_shipped(package):
    try:
        return parse_key((Path(package) / SHIPPED).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def write_pinned(state_dir, raw):
    path = pinned_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".release-key-", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(format_key(raw))
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def decide(pinned, shipped):
    """What an installer should do: ``pin``, ``ok``, ``unsigned``, ``changed`` or ``unsigned-refused``."""
    if pinned is None:
        return "pin" if shipped is not None else "unsigned"
    if shipped is None:
        return "unsigned-refused"
    return "ok" if shipped == pinned else "changed"


def decode_signature(data):
    """64 raw bytes from a ``.sig`` file holding them raw or as base64 text."""
    if len(data) == 64:
        return data
    try:
        raw = base64.b64decode(data.strip(), validate=True)
    except ValueError:
        raise TrustError("unreadable signature") from None
    if len(raw) != 64:
        raise TrustError("unreadable signature")
    return raw


def verify_sums(sums, signature, key):
    """Parse ``SHA256SUMS`` (``{name: sha256 hex}``) after checking its signature; TrustError otherwise."""
    if not ed25519.verify(key, sums, decode_signature(signature)):
        raise TrustError("signature does not match the pinned release key")
    entries = {}
    for line in sums.decode("utf-8").splitlines():
        if not line.strip():
            continue
        match = SUMS_LINE.fullmatch(line.strip())
        if not match:
            raise TrustError("malformed SHA256SUMS")
        entries[match.group(2)] = match.group(1)
    if not entries:
        raise TrustError("empty SHA256SUMS")
    return entries


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version_tuple(text):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", text.strip())
    if not match:
        raise TrustError("unrecognised version: " + text)
    return tuple(int(part) for part in match.groups())


def installer_check(state_dir, package, accept=""):
    """Run by deploy/install.sh before it changes anything. Returns (exit code, message words).

    Exit 0 = go on (``pin`` still to be done by ``pin``), 3 = refuse.
    """
    pinned, shipped = read_pinned(state_dir), read_shipped(package)
    verdict = decide(pinned, shipped)
    if verdict == "changed" and accept and same_fingerprint(accept, shipped):
        verdict = "accepted"
    codes = {"pin": 0, "ok": 0, "unsigned": 0, "accepted": 0, "changed": 3, "unsigned-refused": 3}
    return codes[verdict], verdict, shipped, pinned


def install_pin(state_dir, package):
    """After the layout exists: record the shipped key (first use, or an accepted change)."""
    shipped = read_shipped(package)
    if shipped is not None and read_pinned(state_dir) != shipped:
        write_pinned(state_dir, shipped)
    return shipped


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "pin"):
        item = sub.add_parser(name)
        item.add_argument("--state-dir", required=True)
        item.add_argument("--package", required=True)
        if name == "check":
            item.add_argument("--accept", default="")
    show = sub.add_parser("show")
    show.add_argument("--state-dir", required=True)
    args = parser.parse_args(argv)
    if args.command == "check":
        code, verdict, shipped, pinned = installer_check(args.state_dir, args.package, args.accept)
        words = [verdict]
        if shipped is not None:
            words.append(fingerprint(shipped))
        if pinned is not None:
            words.append(fingerprint(pinned))
        print(" ".join(words))
        return code
    if args.command == "pin":
        shipped = install_pin(args.state_dir, args.package)
        print(fingerprint(shipped) if shipped is not None else "")
        return 0
    pinned = read_pinned(args.state_dir)
    print(fingerprint(pinned) if pinned is not None else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
