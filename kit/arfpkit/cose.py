"""COSE_Sign1 (RFC 9052 section 4) with EdDSA/Ed25519 (alg -8, RFC 9053).

The key id travels in the protected header, so it is covered by the signature.
Fixture keys derive from fixed labels, except the publisher's, which is RFC 8032 test key 1
so the binding vector can be checked with any Ed25519 library.
"""
import hashlib

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .canon import Tag, decode, encode

ALG_EDDSA = -8
HDR_ALG = 1
HDR_KID = 4

RFC8032_TEST1_SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")


def fixture_key(label):
    seed = hashlib.sha256(b"arfp-fixture-key:" + label.encode()).digest()
    return Ed25519PrivateKey.from_private_bytes(seed)


def rfc8032_key():
    return Ed25519PrivateKey.from_private_bytes(RFC8032_TEST1_SEED)


def sign1(private_key, kid, payload_obj):
    kid_b = kid.encode() if isinstance(kid, str) else kid
    protected = encode({HDR_ALG: ALG_EDDSA, HDR_KID: kid_b})
    payload = encode(payload_obj)
    signature = private_key.sign(encode(["Signature1", protected, b"", payload]))
    return Tag(18, [protected, {}, payload, signature])


def kid_of(msg):
    if not (isinstance(msg, Tag) and msg.tag == 18 and isinstance(msg.value, list) and len(msg.value) == 4):
        raise ValueError("not a COSE_Sign1 structure")
    return decode(msg.value[0]).get(HDR_KID)


def payload_of(msg):
    """Decode the payload without verifying (for routing only; never for decisions)."""
    return decode(msg.value[2])


def verify1(public_key, msg):
    """Return the decoded payload; raises if the signature or structure is wrong."""
    if not (isinstance(msg, Tag) and msg.tag == 18 and isinstance(msg.value, list) and len(msg.value) == 4):
        raise ValueError("not a COSE_Sign1 structure")
    protected, _unprotected, payload, signature = msg.value
    if decode(protected).get(HDR_ALG) != ALG_EDDSA:
        raise ValueError("unexpected algorithm")
    public_key.verify(signature, encode(["Signature1", protected, b"", payload]))
    return decode(payload)
