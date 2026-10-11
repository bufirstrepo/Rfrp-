"""Deterministic CBOR (RFC 8949 section 4.2.1) for ARFP objects, plus identity helpers.

Written from the RFC rather than wrapped around a library, so it can be cross-checked
against an independent encoder (cbor2's canonical mode) as a two-implementation test.
"""
import hashlib
import struct
from decimal import Decimal


class Tag:
    __slots__ = ("tag", "value")

    def __init__(self, tag, value):
        self.tag, self.value = tag, value

    def __eq__(self, other):
        return isinstance(other, Tag) and other.tag == self.tag and other.value == self.value

    def __hash__(self):
        return hash((self.tag, repr(self.value)))

    def __repr__(self):
        return f"Tag({self.tag}, {self.value!r})"


# ---------- exact numbers ----------

def num(text):
    """Exact number from text: '0.5' -> Tag(4, [-1, 5]); '2' or '2.0' -> 2.

    Normalized so equal values always encode identically: integral values are ints,
    otherwise the mantissa is not divisible by 10.
    """
    d = Decimal(text)
    if d == d.to_integral_value():
        return int(d)
    sign, digits, exp = d.normalize().as_tuple()
    mant = int("".join(map(str, digits))) * (-1 if sign else 1)
    return Tag(4, [exp, mant])


def num_value(x):
    """Python Decimal for an exact-num (int or tag-4 decimal)."""
    if isinstance(x, bool):
        raise TypeError("bool is not a number")
    if isinstance(x, int):
        return Decimal(x)
    if isinstance(x, Tag) and x.tag == 4:
        exp, mant = x.value
        return Decimal(mant).scaleb(exp)
    raise TypeError(f"not an exact number: {x!r}")


def check_numbers(obj, path="$"):
    """Every tag-4 decimal must be normalized: negative exponent, mantissa not divisible by 10.
    Returns a list of offending paths (empty when the object is clean)."""
    bad = []
    if isinstance(obj, Tag):
        if obj.tag == 4 and not is_normalized_num(obj):
            bad.append(path)
        else:
            bad += check_numbers(obj.value, path + f"#{obj.tag}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            bad += check_numbers(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad += check_numbers(v, f"{path}[{i}]")
    return bad


def key_types_uniform(obj):
    """True when no map anywhere mixes key major types (so RFC 7049 and RFC 8949 orders agree)."""
    if isinstance(obj, Tag):
        return key_types_uniform(obj.value)
    if isinstance(obj, dict):
        majors = {encode(k)[0] >> 5 for k in obj}
        return len(majors) <= 1 and all(key_types_uniform(v) for v in obj.values())
    if isinstance(obj, list):
        return all(key_types_uniform(v) for v in obj)
    return True


def is_normalized_num(x):
    if isinstance(x, int) and not isinstance(x, bool):
        return True
    if isinstance(x, Tag) and x.tag == 4:
        v = x.value
        if not (isinstance(v, list) and len(v) == 2
                and all(isinstance(n, int) and not isinstance(n, bool) for n in v)):
            return False
        exp, mant = v
        return exp < 0 and mant % 10 != 0
    return False


# ---------- encoder ----------

def _head(major, n):
    if n < 24:
        return bytes([major << 5 | n])
    if n < 0x100:
        return bytes([major << 5 | 24, n])
    if n < 0x10000:
        return bytes([major << 5 | 25]) + n.to_bytes(2, "big")
    if n < 0x100000000:
        return bytes([major << 5 | 26]) + n.to_bytes(4, "big")
    if n < 0x10000000000000000:
        return bytes([major << 5 | 27]) + n.to_bytes(8, "big")
    raise ValueError("integer too large: ARFP objects do not use bignums")


def encode(o):
    if o is False:
        return b"\xf4"
    if o is True:
        return b"\xf5"
    if o is None:
        return b"\xf6"
    if isinstance(o, int):
        return _head(0, o) if o >= 0 else _head(1, -1 - o)
    if isinstance(o, (bytes, bytearray)):
        return _head(2, len(o)) + bytes(o)
    if isinstance(o, str):
        b = o.encode("utf-8")
        return _head(3, len(b)) + b
    if isinstance(o, (list, tuple)):
        return _head(4, len(o)) + b"".join(encode(x) for x in o)
    if isinstance(o, dict):
        items = sorted((encode(k), encode(v)) for k, v in o.items())
        keys = [k for k, _ in items]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate map key after encoding")
        return _head(5, len(items)) + b"".join(k + v for k, v in items)
    if isinstance(o, Tag):
        return _head(6, o.tag) + encode(o.value)
    if isinstance(o, float):
        raise TypeError("binary floats are not allowed in ARFP objects; use num()")
    raise TypeError(f"cannot encode {type(o).__name__}")


# ---------- strict decoder ----------

def decode(b):
    o, i = _dec(b, 0)
    if i != len(b):
        raise ValueError("trailing bytes")
    return o


def _key(k):
    return tuple(_key(x) for x in k) if isinstance(k, list) else k


def _dec(b, i):
    ib = b[i]
    major, ai = ib >> 5, ib & 31
    i += 1
    if major == 7:
        if ai == 20:
            return False, i
        if ai == 21:
            return True, i
        if ai == 22:
            return None, i
        if ai == 25:
            return struct.unpack(">e", b[i:i + 2])[0], i + 2
        if ai == 26:
            return struct.unpack(">f", b[i:i + 4])[0], i + 4
        if ai == 27:
            return struct.unpack(">d", b[i:i + 8])[0], i + 8
        raise ValueError("unsupported simple value or break")
    if ai < 24:
        n = ai
    elif ai == 24:
        n, i = b[i], i + 1
    elif ai == 25:
        n, i = int.from_bytes(b[i:i + 2], "big"), i + 2
    elif ai == 26:
        n, i = int.from_bytes(b[i:i + 4], "big"), i + 4
    elif ai == 27:
        n, i = int.from_bytes(b[i:i + 8], "big"), i + 8
    else:
        raise ValueError("indefinite length or reserved additional info")
    if major == 0:
        return n, i
    if major == 1:
        return -1 - n, i
    if major == 2:
        return bytes(b[i:i + n]), i + n
    if major == 3:
        return bytes(b[i:i + n]).decode("utf-8"), i + n
    if major == 4:
        out = []
        for _ in range(n):
            x, i = _dec(b, i)
            out.append(x)
        return out, i
    if major == 5:
        out = {}
        for _ in range(n):
            k, i = _dec(b, i)
            v, i = _dec(b, i)
            k = _key(k)
            if k in out:
                raise ValueError("duplicate map key")
            out[k] = v
        return out, i
    v, i = _dec(b, i)
    return Tag(n, v), i


def is_canonical(b):
    """True when b decodes and re-encodes to the identical bytes (and has no floats)."""
    try:
        return encode(decode(b)) == b
    except (ValueError, TypeError):
        return False


# ---------- identities ----------

SHA256 = -16  # COSE hash algorithm id (RFC 9054)


def H(data):
    return [SHA256, hashlib.sha256(data).digest()]


def oid(obj):
    """Domain-separated id of a protocol object."""
    return H(encode(["arfp/0", obj["kind"], obj]))


def art(data):
    """Identity of raw artifact bytes."""
    return H(data)


def same(d1, d2):
    return d1 is not None and d2 is not None and d1[0] == d2[0] and bytes(d1[1]) == bytes(d2[1])


def short(d):
    return "sha256:" + bytes(d[1]).hex()[:12] if d else "null"
