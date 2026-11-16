#!/usr/bin/env python3
"""Sign a release's SHA256SUMS with the maintainer's key, which never leaves its own machine.

The private key (an OpenSSL Ed25519 key, encrypted, with its passphrase file next to it) lives on
a separate host, normally a NAS. This script sends SHA256SUMS to that host over SSH, asks OpenSSL
there to sign it, and receives only the signature. It then checks the signature against
``config/release-key.pub`` with the same verifier the servers use, so a wrong key or a broken
signature is caught before anything is published.

  python3 tools/sign-release/sign_release.py SHA256SUMS --ssh nas --key-dir /path/to/signing-dir

Needs: ssh access to that host, and OpenSSL 3 there. Writes ``SHA256SUMS.sig`` next to the input.
"""

import argparse
import base64
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "web"))
import release_trust  # noqa: E402


def remote_script(key_dir, key_name, pass_name):
    key = shlex.quote(f"{key_dir.rstrip('/')}/{key_name}")
    passphrase = shlex.quote(f"{key_dir.rstrip('/')}/{pass_name}")
    return ("set -e; umask 077; t=$(mktemp); trap 'rm -f \"$t\"' EXIT; cat > \"$t\"; "
            f"openssl pkeyutl -sign -inkey {key} -passin file:{passphrase} -rawin -in \"$t\" | base64 -w0")


def sign(sums, ssh_host, key_dir, key_name="signing-key.pem", pass_name="passphrase.txt", runner=subprocess.run):
    result = runner(["ssh", ssh_host, remote_script(key_dir, key_name, pass_name)],
                    input=sums, capture_output=True, check=False)
    if result.returncode:
        raise SystemExit("signing failed on the remote host: " + result.stderr.decode("utf-8", "replace").strip())
    return base64.b64decode(result.stdout.strip(), validate=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sums", help="the SHA256SUMS file to sign")
    parser.add_argument("--ssh", required=True, help="ssh host that holds the private key")
    parser.add_argument("--key-dir", required=True, help="directory on that host with the key and passphrase files")
    parser.add_argument("--key-name", default="signing-key.pem")
    parser.add_argument("--passphrase-name", default="passphrase.txt")
    parser.add_argument("--public-key", default=str(ROOT / "config" / "release-key.pub"))
    parser.add_argument("--output", help="default: <sums>.sig")
    args = parser.parse_args(argv)
    sums_path = Path(args.sums)
    sums = sums_path.read_bytes()
    public = release_trust.parse_key(Path(args.public_key).read_text(encoding="utf-8"))
    signature = sign(sums, args.ssh, args.key_dir, args.key_name, args.passphrase_name)
    try:
        release_trust.verify_sums(sums, signature, public)
    except release_trust.TrustError as error:
        raise SystemExit(f"the signature does not verify against {args.public_key}: {error}") from None
    output = Path(args.output) if args.output else sums_path.with_name(sums_path.name + ".sig")
    output.write_text(base64.b64encode(signature).decode("ascii") + "\n", encoding="ascii")
    print(f"signed {sums_path.name} -> {output} (key {release_trust.fingerprint(public)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
