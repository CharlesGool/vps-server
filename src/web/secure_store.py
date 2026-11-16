#!/usr/bin/env python3
"""Encryption at rest for the console's own state files.

A random 256-bit data key lives in ``/etc/vps-server/data.key`` (mode 0600, created by the
installer, outside the state directory). State files that hold secrets or personal data are
written as ``VSE1`` + nonce + ChaCha20-Poly1305 ciphertext, bound to the file's name so one
file cannot be swapped for another. Reading still accepts a plain file written by an older
version, so an upgrade needs no flag day: the next write (or ``migrate``) encrypts it.

Without a key file everything stays plain: a host that has not run the installer yet, or a
test, behaves as before. A file that is encrypted but cannot be decrypted raises
``SecureStoreError`` (a ``ValueError``) and is never replaced by empty state.

What this protects: copies of the state directory or of a disk image taken without ``/etc``,
and a backup that does not carry the key. What it cannot: someone who is root on the running
host (the key is there for the service to use). Files that other programs must read as they
are (sing-box, frps and Caddy configuration, tailscaled state) are not encrypted here; the
configuration backups that include them are sealed to the operator's own key instead.

  python3 secure_store.py init|status|migrate|decrypt-all|export-key
"""

import argparse
import base64
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crypto_box  # noqa: E402

MAGIC = b"VSE1"
LINE_PREFIX = "VSEL1:"
DEFAULT_KEY_FILE = Path("/etc/vps-server/data.key")
AAD_PREFIX = b"vps-server file:"


class SecureStoreError(ValueError):
    pass


def key_path():
    return Path(os.environ.get("VPSSRV_DATA_KEY_FILE") or DEFAULT_KEY_FILE)


_cache = {}


def load_key():
    """The 32-byte data key, or None when this host has none."""
    path = key_path()
    try:
        info = path.stat()
        stamp = (info.st_mtime_ns, info.st_ctime_ns, info.st_ino, info.st_size)
    except FileNotFoundError:
        _cache.pop(path, None)
        return None
    cached = _cache.get(path)
    if cached and cached[0] == stamp:
        return cached[1]
    try:
        key = bytes.fromhex(path.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        raise SecureStoreError(f"unreadable data key {path}") from None
    if len(key) != 32:
        raise SecureStoreError(f"data key {path} is not 32 bytes")
    _cache[path] = (stamp, key)
    return key


def enabled():
    return load_key() is not None


def init_key():
    """Create the key file if there is none. Returns True when it made one."""
    path = key_path()
    if path.exists():
        load_key()
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".data-key-", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="ascii") as handle:
            handle.write(os.urandom(32).hex() + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)          # never replaces a key that appeared in the meantime
    except FileExistsError:
        return False
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return True


def _aad(name):
    return AAD_PREFIX + str(name).encode("utf-8")


def is_encrypted(blob):
    return blob[:4] == MAGIC


def encrypt(data, name):
    key = load_key()
    if key is None:
        raise SecureStoreError("no data key on this host")
    nonce = os.urandom(crypto_box.NONCE_LEN)
    return MAGIC + nonce + crypto_box.aead_encrypt(key, nonce, data, _aad(name))


def decrypt(blob, name):
    key = load_key()
    if key is None:
        raise SecureStoreError("this file is encrypted but the host has no data key")
    if len(blob) < 4 + crypto_box.NONCE_LEN + crypto_box.TAG_LEN:
        raise SecureStoreError("encrypted file is truncated")
    try:
        return crypto_box.aead_decrypt(key, blob[4:16], blob[16:], _aad(name))
    except crypto_box.CryptoError:
        raise SecureStoreError("cannot decrypt (wrong key or damaged file)") from None


def read_bytes(path):
    path = Path(path)
    blob = path.read_bytes()
    return decrypt(blob, path.name) if is_encrypted(blob) else blob


def read_text(path, errors="strict"):
    return read_bytes(path).decode("utf-8", errors)


def _atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".secure-", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def write_bytes(path, data):
    path = Path(path)
    _atomic(path, encrypt(data, path.name) if enabled() else data)


def write_text(path, text):
    write_bytes(path, text.encode("utf-8"))


def load_cert_chain(context, certfile, keyfile):
    """``SSLContext.load_cert_chain`` for a key that may be encrypted: the plain key lives only in memory.

    A plain key file is loaded as it is. An encrypted one is decrypted into an anonymous
    in-memory file (``memfd``) that exists only while the key is read.
    """
    blob = Path(keyfile).read_bytes()
    if not is_encrypted(blob):
        context.load_cert_chain(certfile=str(certfile), keyfile=str(keyfile))
        return
    plain = decrypt(blob, Path(keyfile).name)
    try:
        descriptor = os.memfd_create("vps-server-key", 0)
    except (AttributeError, OSError):
        raise SecureStoreError("this host cannot hold the decrypted key in memory (needs Linux memfd)") from None
    try:
        os.write(descriptor, plain)
        context.load_cert_chain(certfile=str(certfile), keyfile=f"/proc/self/fd/{descriptor}")
    finally:
        os.close(descriptor)


def decrypted_copy(path, directory):
    """A 0600 plain copy of a possibly encrypted file inside ``directory`` (for a program that needs a path)."""
    plain = read_bytes(path)
    descriptor, name = tempfile.mkstemp(prefix=".plain-", dir=directory)
    with os.fdopen(descriptor, "wb") as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(plain)
    return Path(name)


def seal_line(text, name):
    """One record of an append-only log: encrypted on its own so appending stays cheap."""
    if not enabled():
        return text
    blob = encrypt(text.encode("utf-8"), name)
    return LINE_PREFIX + base64.b64encode(blob).decode("ascii")


def open_line(line, name):
    if not line.startswith(LINE_PREFIX):
        return line
    try:
        blob = base64.b64decode(line[len(LINE_PREFIX):].strip(), validate=True)
    except ValueError:
        raise SecureStoreError("damaged log record") from None
    return decrypt(blob, name).decode("utf-8", "replace")


# -- which files, and moving between plain and encrypted -----------------------------

LINE_FILES = ("security-audit.jsonl",)


def managed_files():
    """The state files this store protects (whole-file ones, then record-per-line ones)."""
    import state_paths
    data = state_paths.data_dir()
    names = ("session_secret.txt", "sessions.json", "alerts.json", "console-access.json",
             "known-logins.json", "scheduled-tasks.json", "scheduled-runs.json", "backup-settings.json")
    paths = [state_paths.password_file()] + [data / name for name in names] + [data / "files" / "index.json"]
    certs = state_paths.cert_dir()
    paths += [certs / "key.pem", certs / "client-ca.key"]
    allowlist = os.environ.get("VPSSRV_IP_ALLOWLIST_FILE")
    if allowlist:
        paths.append(Path(allowlist))
    return paths + [data / name for name in LINE_FILES]


def migrate(paths=None, *, decrypt_instead=False):
    """Encrypt (or, with ``decrypt_instead``, decrypt) every existing managed file. Returns the paths changed."""
    changed = []
    for path in (paths or managed_files()):
        path = Path(path)
        if not path.is_file():
            continue
        raw = path.read_bytes()
        if path.name in LINE_FILES:
            lines = raw.decode("utf-8", "replace").splitlines()
            plain = [open_line(line, path.name) for line in lines]
            if decrypt_instead:
                out = [line for line in plain]
                dirty = any(line.startswith(LINE_PREFIX) for line in lines)
            else:
                out = [seal_line(line, path.name) for line in plain]
                dirty = any(not line.startswith(LINE_PREFIX) for line in lines if line)
            if dirty:
                _atomic(path, ("\n".join(out) + "\n").encode("utf-8") if out else b"")
                changed.append(path)
            continue
        if decrypt_instead:
            if is_encrypted(raw):
                _atomic(path, decrypt(raw, path.name))
                changed.append(path)
        elif not is_encrypted(raw) and enabled():
            _atomic(path, encrypt(raw, path.name))
            changed.append(path)
    return changed


def status():
    rows = []
    for path in managed_files():
        if not path.is_file():
            continue
        raw = path.read_bytes()
        if path.name in LINE_FILES:
            lines = [l for l in raw.decode("utf-8", "replace").splitlines() if l]
            state = ("encrypted" if all(l.startswith(LINE_PREFIX) for l in lines) else "plain") if lines else "empty"
        else:
            state = "encrypted" if is_encrypted(raw) else "plain"
        rows.append((str(path), state))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("init", "status", "migrate", "decrypt-all", "export-key"))
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            print("created" if init_key() else "exists")
        elif args.command == "status":
            print(f"data key: {'present' if enabled() else 'absent'} ({key_path()})")
            for path, state in status():
                print(f"{state:10} {path}")
        elif args.command == "migrate":
            if not enabled():
                raise SecureStoreError("no data key; run init first")
            for path in migrate():
                print("encrypted", path)
        elif args.command == "decrypt-all":
            for path in migrate(decrypt_instead=True):
                print("decrypted", path)
        else:
            key = load_key()
            if key is None:
                raise SecureStoreError("no data key")
            print(key.hex())
    except SecureStoreError as error:
        print(f"secure_store: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
