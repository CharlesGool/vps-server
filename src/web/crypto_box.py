"""Authenticated encryption in pure Python: ChaCha20-Poly1305 (RFC 8439), X25519 (RFC 7748), HKDF (RFC 5869).

Hosts that run vps-server have only python3, so encryption at rest cannot lean on a
third-party package. Everything here is the textbook construction from the RFCs and is
checked against their test vectors. It is not constant time, which is acceptable for
local files that never leave the host, and fast enough for the small files it protects.

``seal``/``open_sealed`` encrypt to a public key (an ephemeral X25519 key per message), so
a host can write backups it cannot read back: only the holder of the private key can.
"""

import hashlib
import hmac
import os
import struct

TAG_LEN = 16
NONCE_LEN = 12
KEY_LEN = 32


class CryptoError(Exception):
    pass


# -- ChaCha20 ------------------------------------------------------------------

def _rotl(value, count):
    return ((value << count) & 0xFFFFFFFF) | (value >> (32 - count))


def _block(key_words, counter, nonce_words):
    state = [0x61707865, 0x3320646E, 0x79622D32, 0x6B206574, *key_words, counter, *nonce_words]
    work = list(state)
    for _ in range(10):
        for a, b, c, d in ((0, 4, 8, 12), (1, 5, 9, 13), (2, 6, 10, 14), (3, 7, 11, 15),
                           (0, 5, 10, 15), (1, 6, 11, 12), (2, 7, 8, 13), (3, 4, 9, 14)):
            work[a] = (work[a] + work[b]) & 0xFFFFFFFF
            work[d] = _rotl(work[d] ^ work[a], 16)
            work[c] = (work[c] + work[d]) & 0xFFFFFFFF
            work[b] = _rotl(work[b] ^ work[c], 12)
            work[a] = (work[a] + work[b]) & 0xFFFFFFFF
            work[d] = _rotl(work[d] ^ work[a], 8)
            work[c] = (work[c] + work[d]) & 0xFFFFFFFF
            work[b] = _rotl(work[b] ^ work[c], 7)
    return struct.pack("<16I", *((work[i] + state[i]) & 0xFFFFFFFF for i in range(16)))


def chacha20_xor(key, counter, nonce, data):
    key_words = struct.unpack("<8I", key)
    nonce_words = struct.unpack("<3I", nonce)
    out = bytearray(len(data))
    for offset in range(0, len(data), 64):
        stream = _block(key_words, counter + offset // 64, nonce_words)
        chunk = data[offset:offset + 64]
        out[offset:offset + len(chunk)] = bytes(a ^ b for a, b in zip(chunk, stream))
    return bytes(out)


# -- Poly1305 ------------------------------------------------------------------

def poly1305(key, message):
    r = int.from_bytes(key[:16], "little") & 0x0FFFFFFC0FFFFFFC0FFFFFFC0FFFFFFF
    s = int.from_bytes(key[16:], "little")
    p = (1 << 130) - 5
    acc = 0
    for offset in range(0, len(message), 16):
        block = message[offset:offset + 16]
        acc = (acc + int.from_bytes(block + b"\x01", "little")) * r % p
    return ((acc + s) & ((1 << 128) - 1)).to_bytes(16, "little")


def _pad16(data):
    return b"\0" * (-len(data) % 16)


def _mac_data(aad, ciphertext):
    return aad + _pad16(aad) + ciphertext + _pad16(ciphertext) + struct.pack("<QQ", len(aad), len(ciphertext))


def aead_encrypt(key, nonce, plaintext, aad=b""):
    if len(key) != KEY_LEN or len(nonce) != NONCE_LEN:
        raise CryptoError("bad key or nonce length")
    one_time = chacha20_xor(key, 0, nonce, bytes(32))
    ciphertext = chacha20_xor(key, 1, nonce, plaintext)
    return ciphertext + poly1305(one_time, _mac_data(aad, ciphertext))


def aead_decrypt(key, nonce, sealed, aad=b""):
    if len(key) != KEY_LEN or len(nonce) != NONCE_LEN or len(sealed) < TAG_LEN:
        raise CryptoError("bad key, nonce or message length")
    ciphertext, tag = sealed[:-TAG_LEN], sealed[-TAG_LEN:]
    one_time = chacha20_xor(key, 0, nonce, bytes(32))
    if not hmac.compare_digest(poly1305(one_time, _mac_data(aad, ciphertext)), tag):
        raise CryptoError("authentication failed")
    return chacha20_xor(key, 1, nonce, ciphertext)


# -- X25519 --------------------------------------------------------------------

_P = 2 ** 255 - 19
_A24 = 121665


def x25519(scalar, u_coordinate):
    if len(scalar) != 32 or len(u_coordinate) != 32:
        raise CryptoError("X25519 inputs are 32 bytes")
    k = bytearray(scalar)
    k[0] &= 248
    k[31] &= 127
    k[31] |= 64
    k_int = int.from_bytes(k, "little")
    x1 = int.from_bytes(u_coordinate, "little") & ((1 << 255) - 1)
    x2, z2, x3, z3, swap = 1, 0, x1, 1, 0
    for t in range(254, -1, -1):
        bit = (k_int >> t) & 1
        swap ^= bit
        if swap:
            x2, x3, z2, z3 = x3, x2, z3, z2
        swap = bit
        a, b = (x2 + z2) % _P, (x2 - z2) % _P
        aa, bb = a * a % _P, b * b % _P
        e = (aa - bb) % _P
        c, d = (x3 + z3) % _P, (x3 - z3) % _P
        da, cb = d * a % _P, c * b % _P
        x3 = pow(da + cb, 2, _P)
        z3 = x1 * pow(da - cb, 2, _P) % _P
        x2 = aa * bb % _P
        z2 = e * (aa + _A24 * e) % _P
    if swap:
        x2, x3, z2, z3 = x3, x2, z3, z2
    result = x2 * pow(z2, _P - 2, _P) % _P
    return result.to_bytes(32, "little")


BASEPOINT = (9).to_bytes(32, "little")


def x25519_public(private):
    return x25519(private, BASEPOINT)


def generate_keypair():
    private = os.urandom(32)
    return private, x25519_public(private)


# -- HKDF-SHA256 ---------------------------------------------------------------

def hkdf(secret, salt, info, length=32):
    prk = hmac.new(salt or bytes(32), secret, hashlib.sha256).digest()
    out, block = b"", b""
    counter = 1
    while len(out) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        out += block
        counter += 1
    return out[:length]


# -- sealed boxes (encrypt to a public key) --------------------------------------

def seal(recipient_public, plaintext, aad=b""):
    """ephemeral public key (32) + nonce (12) + ciphertext + tag; only the private key opens it."""
    ephemeral_private, ephemeral_public = generate_keypair()
    shared = x25519(ephemeral_private, recipient_public)
    if shared == bytes(32):
        raise CryptoError("invalid recipient key")
    key = hkdf(shared, ephemeral_public + recipient_public, b"vps-server sealed box v1")
    nonce = os.urandom(NONCE_LEN)
    return ephemeral_public + nonce + aead_encrypt(key, nonce, plaintext, aad)


def open_sealed(recipient_private, blob, aad=b""):
    if len(blob) < 32 + NONCE_LEN + TAG_LEN:
        raise CryptoError("sealed message too short")
    ephemeral_public, nonce, sealed = blob[:32], blob[32:44], blob[44:]
    shared = x25519(recipient_private, ephemeral_public)
    key = hkdf(shared, ephemeral_public + x25519_public(recipient_private), b"vps-server sealed box v1")
    return aead_decrypt(key, nonce, sealed, aad)
