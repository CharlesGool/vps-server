#!/usr/bin/env python3
"""Client-certificate login for the console (mutual TLS).

The console signs one certificate per device with its own CA and hands it out
once as a PKCS#12 file. The server keeps only the CA and each certificate's
serial number, never a device's private key.

Once the CA exists, TLS asks every browser for a certificate but does not
insist (CERT_OPTIONAL). The "required" switch is enforced per request by the
console instead: a Clash subscription on the same port must keep working for
clients that cannot hold a certificate, and a revoked serial must be refused
without rebuilding the TLS context.

Root on the host recovers from a lost certificate with:
    python3 <prefix>/src/web/client_cert.py disable
"""

import json
import os
import secrets
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

try:
    from .state_paths import cert_dir as default_cert_dir
except ImportError:  # Installed helpers are copied into one flat directory.
    from state_paths import cert_dir as default_cert_dir


NAME_LIMIT = 40
CA_DAYS = 3650
CLIENT_DAYS = 1825


class ClientCertError(RuntimeError):
    """A certificate operation failed; ``code`` names the console message."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _clean_name(name):
    name = " ".join(str(name).split())
    if not name or len(name) > NAME_LIMIT or any(ord(char) < 32 for char in name):
        raise ClientCertError("client_cert_name_invalid")
    return name


def _write_private(path, data, mode=0o600):
    descriptor, temporary = tempfile.mkstemp(prefix=".client-", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class ClientAuth:
    def __init__(self, cert_dir=None):
        self.cert_dir = Path(cert_dir) if cert_dir else default_cert_dir()
        self.ca_cert = self.cert_dir / "client-ca.pem"
        self.ca_key = self.cert_dir / "client-ca.key"
        self.state_file = self.cert_dir / "client-auth.json"
        self._lock = threading.Lock()
        self._cache = (None, {"required": False, "certs": []})

    # -- state -------------------------------------------------------------

    def _stamp(self):
        try:
            return self.state_file.stat().st_mtime_ns
        except OSError:
            return None

    def state(self):
        """The saved state, re-read only when the file changed (cheap per request)."""
        stamp = self._stamp()
        if stamp != self._cache[0]:
            data = {"required": False, "certs": []}
            try:
                loaded = json.loads(self.state_file.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data["required"] = loaded.get("required") is True
                    data["certs"] = [item for item in loaded.get("certs", [])
                                     if isinstance(item, dict) and isinstance(item.get("serial"), str)]
            except (OSError, ValueError):
                pass
            self._cache = (stamp, data)
        return self._cache[1]

    def _save(self, data):
        self.cert_dir.mkdir(parents=True, exist_ok=True)
        _write_private(self.state_file, json.dumps(data, ensure_ascii=False, indent=2).encode())
        self._cache = (None, data)

    def required(self):
        return self.state()["required"] and self.ca_cert.is_file()

    def certificates(self):
        return list(self.state()["certs"])

    # -- TLS ---------------------------------------------------------------

    def configure(self, context):
        """Ask for a client certificate once a CA exists; never insist at TLS level."""
        if self.ca_cert.is_file():
            context.verify_mode = ssl.CERT_OPTIONAL
            context.load_verify_locations(cafile=str(self.ca_cert))
        return context

    def ca_stamp(self):
        try:
            return self.ca_cert.stat().st_mtime_ns
        except OSError:
            return None

    def peer(self, connection):
        """The active certificate entry the connection presented, or None."""
        getpeercert = getattr(connection, "getpeercert", None)
        if getpeercert is None:
            return None
        try:
            presented = getpeercert()
        except (ValueError, OSError):
            return None
        if not presented or "serialNumber" not in presented:
            return None  # Unverified certificates are refused by the handshake itself.
        try:
            serial = int(presented["serialNumber"], 16)
        except ValueError:
            return None
        for item in self.state()["certs"]:
            if not item.get("revoked") and int(item["serial"], 16) == serial:
                return item
        return None

    # -- operations --------------------------------------------------------

    def _openssl(self, *args, env=None):
        binary = shutil.which("openssl")
        if not binary:
            raise ClientCertError("client_cert_openssl_missing")
        try:
            subprocess.run([binary, *args], check=True, timeout=60, env=env,
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ClientCertError("client_cert_error") from exc

    def _ensure_ca(self):
        if self.ca_cert.is_file() and self.ca_key.is_file():
            return
        self.cert_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.cert_dir, 0o700)
        with tempfile.TemporaryDirectory(dir=self.cert_dir) as work:
            key, cert = Path(work) / "ca.key", Path(work) / "ca.pem"
            self._openssl("req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                          "-nodes", "-keyout", str(key), "-out", str(cert), "-days", str(CA_DAYS),
                          "-subj", "/CN=vps-server console client CA",
                          "-addext", "basicConstraints=critical,CA:TRUE",
                          "-addext", "keyUsage=critical,keyCertSign,cRLSign")
            _write_private(self.ca_key, key.read_bytes())
            _write_private(self.ca_cert, cert.read_bytes(), 0o644)

    def issue(self, name):
        """Sign a new device certificate; return (pkcs12_bytes, import_password, entry)."""
        name = _clean_name(name)
        with self._lock:
            self._ensure_ca()
            serial = secrets.token_hex(16)
            password = secrets.token_urlsafe(12)
            with tempfile.TemporaryDirectory(dir=self.cert_dir) as work:
                work = Path(work)
                (work / "ext.cnf").write_text("basicConstraints=CA:FALSE\n"
                                              "keyUsage=critical,digitalSignature\n"
                                              "extendedKeyUsage=clientAuth\n")
                # The CN is fixed ASCII so the device name never reaches openssl's -subj parser.
                self._openssl("req", "-new", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                              "-nodes", "-keyout", str(work / "client.key"), "-out", str(work / "client.csr"),
                              "-subj", f"/CN=vps-server client {serial[:8]}")
                self._openssl("x509", "-req", "-in", str(work / "client.csr"),
                              "-CA", str(self.ca_cert), "-CAkey", str(self.ca_key),
                              "-set_serial", "0x" + serial, "-days", str(CLIENT_DAYS),
                              "-sha256", "-extfile", str(work / "ext.cnf"), "-out", str(work / "client.pem"))
                env = dict(os.environ, VPSSRV_P12_PASSWORD=password)
                self._openssl("pkcs12", "-export", "-inkey", str(work / "client.key"),
                              "-in", str(work / "client.pem"), "-name", f"vps-server {serial[:8]}",
                              "-passout", "env:VPSSRV_P12_PASSWORD", "-out", str(work / "client.p12"),
                              env=env)
                bundle = (work / "client.p12").read_bytes()
            data = self.state()
            entry = {"serial": serial, "name": name, "created": int(time.time()), "revoked": False}
            self._save({"required": data["required"], "certs": [*data["certs"], entry]})
            return bundle, password, entry

    def revoke(self, serial):
        with self._lock:
            data = self.state()
            certs = [dict(item, revoked=True) if item["serial"] == serial else item for item in data["certs"]]
            if certs == data["certs"]:
                raise ClientCertError("client_cert_error")
            self._save({"required": data["required"], "certs": certs})

    def set_required(self, required):
        with self._lock:
            data = self.state()
            if required and not any(not item.get("revoked") for item in data["certs"]):
                raise ClientCertError("client_cert_need_current")
            self._save({"required": bool(required), "certs": data["certs"]})


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv not in (["status"], ["disable"]):
        raise SystemExit("usage: client_cert.py status|disable")
    auth = ClientAuth()
    if argv == ["disable"]:
        auth.set_required(False)
        print("Client certificates are no longer required; password login is enabled again.")
        return 0
    state = auth.state()
    print(f"required: {'yes' if auth.required() else 'no'}")
    for item in state["certs"]:
        created = time.strftime("%Y-%m-%d", time.localtime(item.get("created", 0)))
        print(f"{item['serial'][:8]}  {created}  {'revoked' if item.get('revoked') else 'active '}  {item.get('name', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
