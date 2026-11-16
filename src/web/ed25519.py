"""Ed25519 signature verification in pure Python (RFC 8032, section 5.1.7).

Only verification is here: the installer and the upgrade command check release
signatures on hosts that have only python3, and signing happens elsewhere
(``tools/sign-release``). The arithmetic follows the RFC's reference code. It is
not constant time, which does not matter because every input is public.
"""

import hashlib

P = 2 ** 255 - 19
Q = 2 ** 252 + 27742317777372353535851937790883648493


def _inv(value):
    return pow(value, P - 2, P)


D = -121665 * _inv(121666) % P
_SQRT_M1 = pow(2, (P - 1) // 4, P)


def _recover_x(y, sign):
    if y >= P:
        return None
    x2 = (y * y - 1) * _inv(D * y * y + 1) % P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (P + 3) // 8, P)
    if (x * x - x2) % P:
        x = x * _SQRT_M1 % P
    if (x * x - x2) % P:
        return None
    if (x & 1) != sign:
        x = P - x
    return x


_GY = 4 * _inv(5) % P
_GX = _recover_x(_GY, 0)
BASE = (_GX, _GY, 1, _GX * _GY % P)


def _add(a, b):
    first = (a[1] - a[0]) * (b[1] - b[0]) % P
    second = (a[1] + a[0]) * (b[1] + b[0]) % P
    third = 2 * a[3] * b[3] * D % P
    fourth = 2 * a[2] * b[2] % P
    e, f, g, h = second - first, fourth - third, fourth + third, second + first
    return (e * f % P, g * h % P, f * g % P, e * h % P)


def _multiply(scalar, point):
    result = (0, 1, 1, 0)
    while scalar > 0:
        if scalar & 1:
            result = _add(result, point)
        point = _add(point, point)
        scalar >>= 1
    return result


def _equal(a, b):
    return (a[0] * b[2] - b[0] * a[2]) % P == 0 and (a[1] * b[2] - b[1] * a[2]) % P == 0


def _decompress(encoded):
    if len(encoded) != 32:
        return None
    y = int.from_bytes(encoded, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % P)


def verify(public_key, message, signature):
    """True only for a valid signature of ``message`` by the 32-byte ``public_key``."""
    if not isinstance(public_key, bytes) or not isinstance(signature, bytes) \
            or len(public_key) != 32 or len(signature) != 64:
        return False
    point_a = _decompress(public_key)
    point_r = _decompress(signature[:32])
    if point_a is None or point_r is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= Q:
        return False
    h = int.from_bytes(hashlib.sha512(signature[:32] + public_key + message).digest(), "little") % Q
    return _equal(_multiply(s, BASE), _add(point_r, _multiply(h, point_a)))
