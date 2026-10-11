"""Gate zero: authenticate the publisher's Target/Contract binding before any planning.

Also the generic rule for every signed ARFP object: the key id must be on the receiver's
allow-list, the signature must verify, and the payload's "kind" must be the kind expected,
so a valid signature over one object type can never be replayed as another.
"""
from .canon import H, encode, oid, same, short
from .cose import kid_of, verify1
from .rules import Reject
from .template import materialize

BINDING_KID = "pubkey-ed25519-static-allowlist1"


class TrustStore:
    """Static allow-list: key id -> (party, public key). Stage 1 trust anchor."""

    def __init__(self):
        self.keys = {}

    def add(self, kid, party, public_key):
        self.keys[kid.encode() if isinstance(kid, str) else kid] = (party, public_key)


def envelope_hash(env):
    return H(encode(env))


def open_signed(env, trust, expect_kind):
    try:
        kid = kid_of(env)
    except (ValueError, TypeError) as e:
        raise Reject("integrity-failure", f"malformed signed object: {e}")
    if kid not in trust.keys:
        raise Reject("permission-denied", "signing key is not on the allow-list")
    party, public_key = trust.keys[kid]
    try:
        payload = verify1(public_key, env)
    except Exception:                                           # noqa: BLE001
        raise Reject("integrity-failure", "signature does not verify")
    if not isinstance(payload, dict) or payload.get("kind") != expect_kind:
        raise Reject("integrity-failure", f"signed payload is a {payload.get('kind') if isinstance(payload, dict) else '?'}, "
                                          f"not a {expect_kind}")
    return party, payload


def check_binding(env, target, contract, trust, now):
    """Return the binding hash, or raise. Run before eligibility; nothing is planned until it passes."""
    party, b = open_signed(env, trust, "binding")
    if b["publisher"] != party:
        raise Reject("permission-denied", "binding names a publisher other than its signer")
    if party != target["publisher"] or party != contract["authority"]["publisher"]:
        raise Reject("permission-denied", "signer is not the publisher of this target and contract")
    if not same(b["target"], oid(target)):
        raise Reject("integrity-failure", "binding names a different target")
    if not same(b["contract"], oid(contract)):
        raise Reject("integrity-failure", "binding names a different contract")
    if "expires" in b and now > b["expires"]:
        raise Reject("expired-authority", "binding has expired")
    return envelope_hash(env)


def handle_offer(msg, trust, now, eligibility, trace):
    """Gate zero, then eligibility. `trace` records which checks ran, in order."""
    body = msg["body"]
    if "binding" not in body:
        raise Reject("permission-denied", "offer carries no signed binding")
    if not (isinstance(body["target"], dict) and isinstance(body["contract"], dict)):
        raise Reject("missing-dependency", "gate zero needs the target and contract objects, not just their ids")
    trace.append("binding")
    binding_hash = check_binding(body["binding"], body["target"], body["contract"], trust, now)
    trace.append("eligibility")
    eligibility(body["plan"], body["contract"])
    return binding_hash


# ---------- contract split: either binding form ----------
def check_binding_any(env, target, rules, trust, now, templates=None):
    """Gate zero for both binding forms.

    v0.1 form: the binding names a contract; `rules` must be that contract.
    Split form: the binding names a contract template plus per-revision overrides; `rules` is the
    offered template, its digest, or None, and `templates` is the receiver's cache (digest bytes ->
    template). Order: allow-list, signature, kind, signer is the publisher, target, template, expiry,
    overrides. Returns {"binding": hash, "contract": effective contract, "template": id or None,
    "template_obj": the template or None}."""
    party, b = open_signed(env, trust, "binding")
    if "template" not in b:
        if not isinstance(rules, dict):
            raise Reject("missing-dependency", "gate zero needs the contract object, not just its id")
        return {"binding": check_binding(env, target, rules, trust, now), "contract": rules,
                "template": None, "template_obj": None}
    if b["publisher"] != party:
        raise Reject("permission-denied", "binding names a publisher other than its signer")
    if party != target["publisher"]:
        raise Reject("permission-denied", "signer is not the publisher of this target")
    if not same(b["target"], oid(target)):
        raise Reject("integrity-failure", "binding names a different target")
    tid = b["template"]
    if isinstance(rules, dict):
        if rules.get("kind") != "contract-template" or not same(oid(rules), tid):
            raise Reject("integrity-failure", "offered template is not the one the binding names")
        template = rules
    else:
        if rules is not None and not same(rules, tid):
            raise Reject("integrity-failure", "offer names a different template than the binding")
        template = (templates or {}).get(bytes(tid[1]))
        if template is None:
            raise Reject("missing-dependency", f"template {short(tid)} is neither cached nor offered")
    if template["authority"]["publisher"] != party:
        raise Reject("permission-denied", "signer is not the template's publisher")
    if "expires" in b and now > b["expires"]:
        raise Reject("expired-authority", "binding has expired")
    contract = materialize(template, b)
    return {"binding": envelope_hash(env), "contract": contract, "template": tid, "template_obj": template}


def handle_offer_any(msg, trust, now, eligibility, trace, templates=None):
    """Gate zero for either binding form, then eligibility against the effective contract. A template
    is cached only after a binding that names it has verified."""
    body = msg["body"]
    if "binding" not in body:
        raise Reject("permission-denied", "offer carries no signed binding")
    if not isinstance(body["target"], dict):
        raise Reject("missing-dependency", "gate zero needs the target object, not just its id")
    trace.append("binding")
    res = check_binding_any(body["binding"], body["target"], body.get("contract", body.get("template")),
                            trust, now, templates)
    if res["template"] is not None and templates is not None:
        templates[bytes(res["template"][1])] = res["template_obj"]
    trace.append("eligibility")
    eligibility(body["plan"], res["contract"])
    return res
