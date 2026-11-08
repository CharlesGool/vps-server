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

Certificates are signed with the bundled static openssl (vendor/openssl) and
a minimal config of this module's own, so neither the host's OpenSSL version
nor its openssl.cnf shapes them. Each CA must pass an in-memory mTLS handshake
on the host's TLS library before it is used.

Root on the host recovers from a lost certificate with:
    python3 <prefix>/src/web/client_cert.py disable
and checks the openssl and CA in use with:
    python3 <prefix>/src/web/client_cert.py check
"""

import hashlib
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


# Only what `req -subj` needs: no default extensions may leak into a certificate.
OPENSSL_CONFIG = """[ req ]
distinguished_name = req_dn
prompt = no

[ req_dn ]
"""
ROOT = Path(__file__).resolve().parents[2]
OPENSSL_MIN = (1, 1, 1)


def _system_openssl_version(binary):
    try:
        output = subprocess.run([binary, "version"], capture_output=True, text=True,
                                timeout=10, check=False).stdout.split()
        return tuple(int(part) for part in output[1].rstrip("abcdefghijklmnopqrstuvwxyz").split(".")[:3])
    except (OSError, subprocess.SubprocessError, IndexError, ValueError):
        return None


def openssl_binary():
    """The bundled openssl; a host openssl only as a fallback, and only if new enough."""
    override = os.environ.get("VPSSRV_OPENSSL")
    candidates = [override] if override else []
    candidates += [ROOT / "vendor" / "openssl" / "openssl", ROOT / "third_party" / "openssl" / "openssl"]
    for candidate in candidates:
        if candidate and os.access(candidate, os.X_OK):
            return str(candidate)
    system = shutil.which("openssl")
    if system and (_system_openssl_version(system) or (0,)) >= OPENSSL_MIN:
        return system
    return None


def _fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
                    if isinstance(loaded.get("ca_checked"), str):
                        data["ca_checked"] = loaded["ca_checked"]
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

    def _openssl(self, work, *args, env=None):
        """Run openssl with this module's own config, never the host's openssl.cnf.

        OpenSSL 1.1.1k merged the system config's v3_ca section into ``req -x509``
        next to our ``-addext`` lines, writing Basic Constraints twice; the
        resulting CA was rejected even by its own ``openssl verify``.
        """
        binary = openssl_binary()
        if not binary:
            raise ClientCertError("client_cert_openssl_missing")
        config = Path(work) / "openssl.cnf"
        if not config.is_file():
            config.write_text(OPENSSL_CONFIG)
        env = dict(env or os.environ, OPENSSL_CONF=str(config))
        if args[0] == "req":
            args = (args[0], "-config", str(config), *args[1:])
        try:
            subprocess.run([binary, *args], check=True, timeout=60, env=env, cwd=work,
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ClientCertError("client_cert_error") from exc

    def _create_ca(self):
        self.cert_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.cert_dir, 0o700)
        with tempfile.TemporaryDirectory(dir=self.cert_dir) as work:
            key, cert = Path(work) / "ca.key", Path(work) / "ca.pem"
            self._openssl(work, "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                          "-nodes", "-keyout", str(key), "-out", str(cert), "-days", str(CA_DAYS),
                          "-subj", "/CN=vps-server console client CA",
                          "-addext", "basicConstraints=critical,CA:TRUE",
                          "-addext", "keyUsage=critical,keyCertSign,cRLSign")
            _write_private(self.ca_key, key.read_bytes())
            _write_private(self.ca_cert, cert.read_bytes(), 0o644)

    def _sign_client(self, work, serial, days):
        """Write client.key and client.pem for ``serial`` into ``work``."""
        work = Path(work)
        (work / "ext.cnf").write_text("basicConstraints=CA:FALSE\n"
                                      "keyUsage=critical,digitalSignature\n"
                                      "extendedKeyUsage=clientAuth\n")
        # The CN is fixed ASCII so the device name never reaches openssl's -subj parser.
        self._openssl(work, "req", "-new", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                      "-nodes", "-keyout", str(work / "client.key"), "-out", str(work / "client.csr"),
                      "-subj", f"/CN=vps-server client {serial[:8]}")
        self._openssl(work, "x509", "-req", "-in", str(work / "client.csr"),
                      "-CA", str(self.ca_cert), "-CAkey", str(self.ca_key),
                      "-set_serial", "0x" + serial, "-days", str(days),
                      "-sha256", "-extfile", str(work / "ext.cnf"), "-out", str(work / "client.pem"))

    def self_test(self):
        """True when the host's TLS library accepts a certificate from this CA.

        The console's handshakes run on the host libssl through Python, not on
        the bundled openssl, so a CA is only kept once a throwaway client
        certificate passes a full in-memory mTLS handshake.
        """
        if ssl.OPENSSL_VERSION_INFO < (1, 1, 1):
            return False
        serial = secrets.token_hex(16)
        with tempfile.TemporaryDirectory(dir=self.cert_dir) as work:
            work = Path(work)
            self._sign_client(work, serial, 1)
            self._openssl(work, "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                          "-nodes", "-keyout", str(work / "server.key"), "-out", str(work / "server.pem"),
                          "-days", "1", "-subj", "/CN=vps-server self test")
            try:
                server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                server.load_cert_chain(str(work / "server.pem"), str(work / "server.key"))
                server.verify_mode = ssl.CERT_REQUIRED
                server.load_verify_locations(cafile=str(self.ca_cert))
                client = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                client.check_hostname = False
                client.verify_mode = ssl.CERT_NONE
                client.load_cert_chain(str(work / "client.pem"), str(work / "client.key"))
                to_server, to_client = ssl.MemoryBIO(), ssl.MemoryBIO()
                ends = [client.wrap_bio(to_client, to_server), server.wrap_bio(to_server, to_client, server_side=True)]
                done = [False, False]
                for _ in range(20):
                    for index, end in enumerate(ends):
                        if not done[index]:
                            try:
                                end.do_handshake()
                                done[index] = True
                            except ssl.SSLWantReadError:
                                pass
                    if all(done):
                        break
                presented = ends[1].getpeercert() if done[1] else None
            except (ssl.SSLError, OSError, ValueError):
                return False
        return bool(presented) and int(presented.get("serialNumber", "0"), 16) == int(serial, 16)

    def _ensure_ca(self):
        """Create the CA if needed and make sure the host accepts its certificates.

        A CA that fails the self test (for example one written by an old host
        openssl) is replaced; certificates it signed never worked, so they are
        marked revoked and the "required" switch is turned off.
        """
        if not (self.ca_cert.is_file() and self.ca_key.is_file()):
            self._create_ca()
        fingerprint = _fingerprint(self.ca_cert)
        data = self.state()
        if data.get("ca_checked") == fingerprint:
            return
        if not self.self_test():
            self._create_ca()
            fingerprint = _fingerprint(self.ca_cert)
            data = {"required": False,
                    "certs": [dict(item, revoked=True) for item in data["certs"]]}
            if not self.self_test():
                self.ca_cert.unlink(missing_ok=True)
                self.ca_key.unlink(missing_ok=True)
                self._save(data)
                raise ClientCertError("client_cert_tls_unsupported")
        self._save({**data, "ca_checked": fingerprint})

    def issue(self, name):
        """Sign a new device certificate; return (pkcs12_bytes, import_password, entry)."""
        name = _clean_name(name)
        with self._lock:
            self._ensure_ca()
            serial = secrets.token_hex(16)
            password = secrets.token_urlsafe(12)
            with tempfile.TemporaryDirectory(dir=self.cert_dir) as work:
                work = Path(work)
                self._sign_client(work, serial, CLIENT_DAYS)
                env = dict(os.environ, VPSSRV_P12_PASSWORD=password)
                self._openssl(work, "pkcs12", "-export", "-inkey", str(work / "client.key"),
                              "-in", str(work / "client.pem"), "-name", f"vps-server {serial[:8]}",
                              "-passout", "env:VPSSRV_P12_PASSWORD", "-out", str(work / "client.p12"),
                              env=env)
                bundle = (work / "client.p12").read_bytes()
            data = self.state()
            entry = {"serial": serial, "name": name, "created": int(time.time()), "revoked": False}
            self._save({**data, "certs": [*data["certs"], entry]})
            return bundle, password, entry

    def revoke(self, serial):
        with self._lock:
            data = self.state()
            certs = [dict(item, revoked=True) if item["serial"] == serial else item for item in data["certs"]]
            if certs == data["certs"]:
                raise ClientCertError("client_cert_error")
            self._save({**data, "certs": certs})

    def set_required(self, required):
        with self._lock:
            data = self.state()
            if required and not any(not item.get("revoked") for item in data["certs"]):
                raise ClientCertError("client_cert_need_current")
            self._save({**data, "required": bool(required)})


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv not in (["status"], ["disable"], ["check"]):
        raise SystemExit("usage: client_cert.py status|disable|check")
    auth = ClientAuth()
    if argv == ["check"]:
        print(f"openssl: {openssl_binary() or 'missing'}")
        print(f"host TLS library: {ssl.OPENSSL_VERSION}")
        if not auth.ca_cert.is_file():
            print("CA: none yet (created with the first certificate)")
            return 0
        ok = auth.self_test()
        print(f"CA self test: {'ok' if ok else 'FAILED (issuing a certificate replaces the CA)'}")
        return 0 if ok else 1
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
