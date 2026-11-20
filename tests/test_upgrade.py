"""The trusted upgrade command: verification order, refusals, safe unpacking (no network, no installer)."""
import argparse
import base64
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import release_trust as rt  # noqa: E402
import upgrade as up  # noqa: E402


class Signer:
    """An Ed25519 key made with OpenSSL, for signing test releases."""

    def __init__(self, directory):
        if not shutil.which("openssl"):
            raise unittest.SkipTest("openssl not available")
        self.key = os.path.join(directory, "k.pem")
        try:
            subprocess.run(["openssl", "genpkey", "-algorithm", "ED25519", "-out", self.key],
                           check=True, capture_output=True)
            der = subprocess.run(["openssl", "pkey", "-in", self.key, "-pubout", "-outform", "DER"],
                                 check=True, capture_output=True).stdout
        except (OSError, subprocess.CalledProcessError):
            raise unittest.SkipTest("openssl cannot do Ed25519") from None
        self.public = der[-32:]
        self.directory = directory

    def sign(self, data):
        source, out = (os.path.join(self.directory, n) for n in ("sign-in", "sign-out"))
        with open(source, "wb") as handle:
            handle.write(data)
        subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey", self.key, "-rawin", "-in", source, "-out", out],
                       check=True, capture_output=True)
        with open(out, "rb") as handle:
            return base64.b64encode(handle.read()) + b"\n"


def make_package(path, tag, key=None, extra=(), version=None):
    """A package tarball; ``extra`` is (TarInfo, bytes or None) pairs added as they are."""
    version = version or tag.lstrip("v")
    with tarfile.open(path, "w:gz") as archive:
        def add(name, data, mode=0o644):
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), mode
            archive.addfile(info, io.BytesIO(data))
        add("vps-server/config/VERSION", version.encode() + b"\n")
        add("vps-server/deploy/install.sh", b"#!/bin/sh\nexit 0\n", 0o755)
        if key is not None:
            add("vps-server/config/release-key.pub", rt.format_key(key).encode())
        for info, data in extra:
            archive.addfile(info, io.BytesIO(data) if data is not None else None)


class UpgradeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.signer = Signer(str(self.tmp))
        self.state = self.tmp / "state"
        self.prefix = self.tmp / "apps" / "vps-server"
        (self.prefix / "config").mkdir(parents=True)
        (self.prefix / "config" / "VERSION").write_text("6.5.0\n")
        self.release = self.tmp / "release"
        self.release.mkdir()
        self.log = []
        self.ran = []

    def publish(self, tag="v6.6.0", key="signer", sign_with=None, tamper=False, **package):
        shipped = self.signer.public if key == "signer" else key
        name = up.package_name(tag, "offline")
        make_package(self.release / name, tag, shipped, **package)
        digest = rt.file_sha256(self.release / name)
        sums = f"{digest}  {name}\n".encode()
        (self.release / "SHA256SUMS").write_bytes(sums)
        signer = sign_with or self.signer
        (self.release / "SHA256SUMS.sig").write_bytes(signer.sign(sums))
        if tamper:
            with open(self.release / name, "ab") as handle:
                handle.write(b"x")
        return name

    def args(self, **over):
        values = dict(version=None, variant="offline", repo=up.DEFAULT_REPO, source=str(self.release),
                      trust_fingerprint="", accept_key_change="", allow_downgrade=False, dry_run=False)
        values.update(over)
        return argparse.Namespace(**values)

    def go(self, **over):
        return up.run(self.args(**over), state_dir=self.state, prefix=self.prefix,
                      installer=["sh", "-c", 'echo "$VPSSRV_MODULES|$VPSSRV_ACCEPT_KEY_CHANGE" > "$0"', str(self.tmp / "ran")],
                      out=self.log.append)

    def installed(self):
        path = self.tmp / "ran"
        return path.read_text().strip() if path.exists() else None

    def pin(self, raw=None):
        rt.write_pinned(self.state, raw or self.signer.public)

    def test_signed_release_installs_when_pinned(self):
        self.publish()
        self.pin()
        self.assertEqual(self.go(), 0)
        self.assertEqual(self.installed(), "web|")
        self.assertTrue(any("Signature OK" in line for line in self.log))
        self.assertEqual([p.name for p in self.prefix.parent.iterdir() if p.name.startswith(".vps-server-upgrade")], [])

    def test_a_package_signed_by_another_key_is_refused(self):
        other = Signer(str(self.tmp / "other")) if (self.tmp / "other").mkdir() is None else None
        self.publish(key=other.public, sign_with=other)
        self.pin()
        with self.assertRaises(rt.TrustError):
            self.go()
        self.assertIsNone(self.installed())

    def test_tampered_package_or_sums_are_refused(self):
        self.publish(tamper=True)
        self.pin()
        with self.assertRaises(up.UpgradeError):
            self.go()
        self.publish()
        (self.release / "SHA256SUMS").write_bytes((self.release / "SHA256SUMS").read_bytes().replace(b"  ", b" *"))
        with self.assertRaises(rt.TrustError):
            self.go()
        self.assertIsNone(self.installed())

    def test_missing_or_garbled_signature_is_refused(self):
        self.publish()
        self.pin()
        (self.release / "SHA256SUMS.sig").write_bytes(b"AAAA")
        with self.assertRaises(rt.TrustError):
            self.go()
        (self.release / "SHA256SUMS.sig").unlink()
        with self.assertRaises(up.UpgradeError):
            self.go()

    def test_unsigned_package_and_changed_key_are_refused_unless_accepted(self):
        new = bytes(range(1, 33))
        self.publish(key=None)
        self.pin()
        with self.assertRaises(up.UpgradeError):
            self.go()
        self.publish(key=new)                      # signed by the pinned signer but ships another key
        with self.assertRaises(up.UpgradeError):
            self.go()
        self.assertEqual(self.go(accept_key_change=rt.fingerprint(new)), 0)
        self.assertEqual(self.installed(), "web|" + rt.fingerprint(new))

    def test_versions(self):
        self.pin()
        self.publish("v6.4.0")
        with self.assertRaises(up.UpgradeError):
            self.go()                                                  # older
        self.assertEqual(self.go(allow_downgrade=True), 0)
        self.publish("v6.5.0")
        self.assertEqual(self.go(version="v6.5.0"), 0)                 # same version: nothing to do
        self.assertIn("Already at v6.5.0.", self.log)

    def test_package_that_lies_about_its_version_is_refused(self):
        self.pin()
        self.publish("v6.6.0", version="6.9.9")
        with self.assertRaises(up.UpgradeError):
            self.go()

    def test_first_use_needs_the_right_fingerprint_then_pins(self):
        self.publish()
        with self.assertRaises(up.UpgradeError):
            self.go()                                                  # no pin, no fingerprint
        with self.assertRaises(up.UpgradeError):
            self.go(trust_fingerprint=rt.fingerprint(bytes(range(32))))
        self.assertIsNone(rt.read_pinned(self.state))
        self.assertEqual(self.go(trust_fingerprint=rt.fingerprint(self.signer.public)), 0)
        self.assertEqual(rt.read_pinned(self.state), self.signer.public)

    def test_first_use_still_checks_the_signature(self):
        self.publish()
        (self.release / "SHA256SUMS.sig").write_bytes(self.signer.sign(b"something else"))
        with self.assertRaises(rt.TrustError):
            self.go(trust_fingerprint=rt.fingerprint(self.signer.public))
        self.assertIsNone(rt.read_pinned(self.state))

    def test_dry_run_installs_nothing(self):
        self.publish()
        self.pin()
        self.assertEqual(self.go(dry_run=True), 0)
        self.assertIsNone(self.installed())
        self.assertTrue(any(line.startswith("Would upgrade 6.5.0 -> v6.6.0") for line in self.log))

    def test_unsafe_archives_are_refused(self):
        self.pin()
        bad = []
        escape = tarfile.TarInfo("vps-server/../evil")
        escape.size = 1
        bad.append(((escape, b"x")))
        absolute = tarfile.TarInfo("/etc/evil")
        absolute.size = 1
        bad.append((absolute, b"x"))
        outside = tarfile.TarInfo("evil-top/file")
        outside.size = 1
        bad.append((outside, b"x"))
        link = tarfile.TarInfo("vps-server/link")
        link.type, link.linkname = tarfile.SYMTYPE, "../../outside"
        bad.append((link, None))
        absolute_link = tarfile.TarInfo("vps-server/link2")
        absolute_link.type, absolute_link.linkname = tarfile.SYMTYPE, "/etc/passwd"
        bad.append((absolute_link, None))
        device = tarfile.TarInfo("vps-server/dev")
        device.type = tarfile.CHRTYPE
        bad.append((device, None))
        for item in bad:
            self.publish(extra=[item])
            with self.assertRaises(up.UpgradeError, msg=item[0].name):
                self.go()
            self.assertIsNone(self.installed())
        self.assertFalse((self.tmp / "evil").exists())

    @unittest.skipUnless(getattr(tarfile, "tar_filter", None), "links are refused without tarfile filters")
    def test_a_relative_link_inside_the_package_is_fine(self):
        self.pin()
        link = tarfile.TarInfo("vps-server/config/latest")
        link.type, link.linkname = tarfile.SYMTYPE, "VERSION"
        self.publish(extra=[(link, None)])
        self.assertEqual(self.go(), 0)

    def test_an_older_version_is_refused_while_state_files_are_encrypted(self):
        import secure_store
        saved = {name: os.environ.get(name) for name in ("VPSSRV_STATE_DIR", "VPSSRV_DATA_KEY_FILE")}
        os.environ["VPSSRV_STATE_DIR"] = str(self.state)
        os.environ["VPSSRV_DATA_KEY_FILE"] = str(self.tmp / "data.key")
        secure_store._cache.clear()
        try:
            self.pin()
            self.publish("v6.9.0")
            (self.state / "data").mkdir(parents=True, exist_ok=True)
            self.assertEqual(self.go(allow_downgrade=True, dry_run=True), 0)       # no key yet: nothing to decrypt
            secure_store.init_key()
            secure_store.write_text(self.state / "admin_password.txt", "a-long-enough-password\n")
            with self.assertRaises(up.UpgradeError) as caught:
                self.go(dry_run=True)
            self.assertIn("decrypt-all", str(caught.exception))
            for leftover in self.release.iterdir():                                   # a version that can read them
                leftover.unlink()
            self.publish("v7.0.0")
            self.assertEqual(self.go(dry_run=True), 0)
        finally:
            # Restore, not remove: without VPSSRV_DATA_KEY_FILE later tests would read the host's real key.
            for name, value in saved.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
            secure_store._cache.clear()

    def test_installer_failure_is_passed_on(self):
        self.publish()
        self.pin()
        code = up.run(self.args(), state_dir=self.state, prefix=self.prefix, installer=["sh", "-c", "exit 7"],
                      out=self.log.append)
        self.assertEqual(code, 7)

    def test_a_failed_download_is_a_clean_refusal_not_a_traceback(self):
        self.pin()
        self.publish()
        (self.release / "SHA256SUMS").unlink()          # forces the network path below
        calls = []

        def failing_opener(request, timeout=0):
            calls.append(request.full_url)
            raise OSError("timed out")

        args = self.args(source=None, version="v6.6.0")
        with self.assertRaises(up.UpgradeError):
            up.run(args, state_dir=self.state, prefix=self.prefix, opener=failing_opener, out=self.log.append)
        self.assertTrue(calls)
        self.assertEqual([p.name for p in self.prefix.parent.iterdir() if p.name.startswith(".vps-server-upgrade")], [])

    def test_a_download_that_fails_its_checksum_is_a_clean_refusal(self):
        self.pin()
        name = self.publish()
        original = up.online_assets._download

        def broken(url, destination, expected, **kwargs):
            raise RuntimeError("download failed: " + url)

        up.online_assets._download = broken
        try:
            args = self.args(source=None, version="v6.6.0")
            small = {"SHA256SUMS": (self.release / "SHA256SUMS").read_bytes(),
                     "SHA256SUMS.sig": (self.release / "SHA256SUMS.sig").read_bytes()}

            class Response:
                def __init__(self, data):
                    self.data = data

                def read(self, limit=-1):
                    return self.data

                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    return False

            def opener(request, timeout=0):
                return Response(small[request.full_url.rsplit("/", 1)[1]])

            with self.assertRaises(up.UpgradeError):
                up.run(args, state_dir=self.state, prefix=self.prefix, opener=opener, out=self.log.append)
        finally:
            up.online_assets._download = original
        self.assertTrue(name)

    def test_name_and_url_helpers(self):
        self.assertEqual(up.package_name("v1.2.3", "online"), "vps-server-v1.2.3-linux-amd64-online.tar.gz")
        self.assertEqual(up.release_url("a/b", "v1.2.3", "SHA256SUMS"),
                         "https://github.com/a/b/releases/download/v1.2.3/SHA256SUMS")
        for bad in ("../x", "v1.2", "latest", "v1.2.3; rm"):
            with self.assertRaises(up.UpgradeError, msg=bad):
                up.run(self.args(version=bad), state_dir=self.state, prefix=self.prefix) if self.pin() is None else None
        with self.assertRaises(up.UpgradeError):
            up.run(self.args(repo="a/b/c"), state_dir=self.state, prefix=self.prefix)


if __name__ == "__main__":
    unittest.main()
