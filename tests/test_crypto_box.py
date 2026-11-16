"""ChaCha20-Poly1305, X25519, HKDF and sealed boxes against the RFC vectors and a reference library."""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import crypto_box as cb  # noqa: E402

H = bytes.fromhex
KEY = bytes(range(0x80, 0xA0))
NONCE = H("070000004041424344454647")
AAD = H("50515253c0c1c2c3c4c5c6c7")
PLAIN = b"Ladies and Gentlemen of the class of '99: If I could offer you only one tip for the future, sunscreen would be it."


class AeadTest(unittest.TestCase):
    def test_rfc8439_vector(self):
        out = cb.aead_encrypt(KEY, NONCE, PLAIN, AAD)
        self.assertEqual(out[:16].hex(), "d31a8d34648e60db7b86afbc53ef7ec2")
        self.assertEqual(out[-16:].hex(), "1ae10b594f09e26a7e902ecbd0600691")
        self.assertEqual(cb.aead_decrypt(KEY, NONCE, out, AAD), PLAIN)

    def test_every_kind_of_tampering_is_detected(self):
        out = cb.aead_encrypt(KEY, NONCE, PLAIN, AAD)
        cases = [(KEY, NONCE, out[:-1] + bytes([out[-1] ^ 1]), AAD), (KEY, NONCE, bytes([out[0] ^ 1]) + out[1:], AAD),
                 (KEY, NONCE, out, AAD + b"x"), (KEY, NONCE, out, b""), (KEY, bytes(12), out, AAD),
                 (bytes(32), NONCE, out, AAD), (KEY, NONCE, out[:-2], AAD)]
        for key, nonce, sealed, aad in cases:
            with self.assertRaises(cb.CryptoError):
                cb.aead_decrypt(key, nonce, sealed, aad)

    def test_bad_lengths(self):
        for key, nonce in ((KEY[:31], NONCE), (KEY, NONCE[:11])):
            with self.assertRaises(cb.CryptoError):
                cb.aead_encrypt(key, nonce, b"x")
        with self.assertRaises(cb.CryptoError):
            cb.aead_decrypt(KEY, NONCE, b"short")

    def test_empty_and_block_boundaries_round_trip(self):
        for size in (0, 1, 15, 16, 17, 63, 64, 65, 127, 128, 1000):
            data = os.urandom(size)
            self.assertEqual(cb.aead_decrypt(KEY, NONCE, cb.aead_encrypt(KEY, NONCE, data, b"a"), b"a"), data, size)

    def test_agrees_with_a_reference_library(self):
        try:
            from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
        except ImportError:
            self.skipTest("cryptography not installed")
        for size in (0, 5, 64, 100, 513):
            key, nonce, data, aad = os.urandom(32), os.urandom(12), os.urandom(size), os.urandom(7)
            self.assertEqual(cb.aead_encrypt(key, nonce, data, aad), ChaCha20Poly1305(key).encrypt(nonce, data, aad))


class X25519Test(unittest.TestCase):
    def test_rfc7748_vector(self):
        a = H("77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a")
        b = H("5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb")
        self.assertEqual(cb.x25519_public(a).hex(), "8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a")
        self.assertEqual(cb.x25519_public(b).hex(), "de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f")
        shared = "4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742"
        self.assertEqual(cb.x25519(a, cb.x25519_public(b)).hex(), shared)
        self.assertEqual(cb.x25519(b, cb.x25519_public(a)).hex(), shared)

    def test_agrees_with_a_reference_library(self):
        try:
            from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
            from cryptography.hazmat.primitives import serialization as s
        except ImportError:
            self.skipTest("cryptography not installed")
        raw = lambda key: key.public_bytes(s.Encoding.Raw, s.PublicFormat.Raw)
        for _ in range(3):
            mine, theirs = os.urandom(32), X25519PrivateKey.generate()
            self.assertEqual(cb.x25519(mine, raw(theirs.public_key())),
                             theirs.exchange(X25519PublicKey.from_public_bytes(cb.x25519_public(mine))))

    def test_bad_inputs(self):
        with self.assertRaises(cb.CryptoError):
            cb.x25519(bytes(31), bytes(32))


class HkdfTest(unittest.TestCase):
    def test_rfc5869_case_1(self):
        okm = cb.hkdf(H("0b" * 22), H("000102030405060708090a0b0c"), H("f0f1f2f3f4f5f6f7f8f9"), 42)
        self.assertEqual(okm.hex(), "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865")


class SealedBoxTest(unittest.TestCase):
    def test_only_the_private_key_opens_it(self):
        private, public = cb.generate_keypair()
        blob = cb.seal(public, b"configuration", b"name")
        self.assertEqual(cb.open_sealed(private, blob, b"name"), b"configuration")
        other_private, _ = cb.generate_keypair()
        for wrong in (lambda: cb.open_sealed(other_private, blob, b"name"), lambda: cb.open_sealed(private, blob, b"other"),
                      lambda: cb.open_sealed(private, blob[:-1] + bytes([blob[-1] ^ 1]), b"name"),
                      lambda: cb.open_sealed(private, bytes([blob[0] ^ 1]) + blob[1:], b"name"),
                      lambda: cb.open_sealed(private, blob[:40], b"name")):
            with self.assertRaises(cb.CryptoError):
                wrong()

    def test_two_seals_of_the_same_data_differ(self):
        _, public = cb.generate_keypair()
        self.assertNotEqual(cb.seal(public, b"x"), cb.seal(public, b"x"))

    def test_the_sealing_side_cannot_read_it_back(self):
        # all it holds is the public key and the ephemeral key it threw away
        private, public = cb.generate_keypair()
        blob = cb.seal(public, b"secret")
        with self.assertRaises(cb.CryptoError):
            cb.open_sealed(public, blob)                    # the public key is not the private key


if __name__ == "__main__":
    unittest.main()
