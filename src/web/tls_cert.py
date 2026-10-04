"""Generate a self-signed PEM pair with the bundled sing-box binary."""

import os
import re
import ssl
import subprocess
import tempfile
import sys
from pathlib import Path


BINARY = Path("/usr/local/bin/sing-box-vps-server")
PEM = re.compile(r"-----BEGIN ([A-Z ]+)-----\s+.*?-----END \1-----", re.S)


def create_self_signed(cert, key, server_name, *, binary=BINARY):
    cert, key = Path(cert), Path(key)
    if not server_name or len(server_name) > 253 or any(char in server_name for char in "\r\n\0"):
        raise ValueError("invalid certificate name")
    output = subprocess.run([str(binary), "generate", "tls-keypair", server_name,
                             "--months", "120"], capture_output=True, text=True,
                            check=True, timeout=30).stdout
    blocks = {match.group(1): match.group(0) + "\n" for match in PEM.finditer(output)}
    private = next((value for name, value in blocks.items() if "PRIVATE KEY" in name), None)
    certificate = blocks.get("CERTIFICATE")
    if private is None or certificate is None:
        raise ValueError("invalid generated certificate")
    cert.parent.mkdir(parents=True, exist_ok=True)
    key.parent.mkdir(parents=True, exist_ok=True)
    temporary = []
    try:
        for target, data, mode in ((cert, certificate, 0o644), (key, private, 0o600)):
            descriptor, name = tempfile.mkstemp(prefix=".tls-", dir=target.parent)
            temporary.append((Path(name), target))
            os.fchmod(descriptor, mode)
            with os.fdopen(descriptor, "w") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        check = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        check.load_cert_chain(str(temporary[0][0]), str(temporary[1][0]))
        for source, target in temporary:
            os.replace(source, target)
    finally:
        for source, _ in temporary:
            source.unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit("usage: tls_cert.py CERT KEY SERVER_NAME BINARY")
    create_self_signed(sys.argv[1], sys.argv[2], sys.argv[3], binary=Path(sys.argv[4]))
