"""Multi-hop provenance (C27): what a receiver may accept from a repeater.

A repeater can forward signed evidence unchanged, or add a signed attestation that names the
evidence by hash. It can never substitute for the origin: the attestation is accepted only when
the evidence it names is delivered too and verifies under an accepted checker's key, and only
when the repeater holds a publisher-signed delegation with the "attest" right. Unsigned evidence
cannot be checked "byte for byte" across a hop, so evidence that crosses a hop must be signed.
"""
from .canon import H, art, encode, oid, same
from .cose import payload_of
from .gate import check_binding, check_binding_any, envelope_hash, open_signed
from .rules import Reject


def _delegation_ok(dg, issuer, attester, contract, right, now):
    if issuer != contract["authority"]["publisher"]:
        raise Reject("permission-denied", "delegation is not signed by the publisher")
    if dg["grantee"] != attester:
        raise Reject("permission-denied", "delegation was granted to someone else")
    if not same(dg["contract"], oid(contract)):
        raise Reject("permission-denied", "delegation covers a different contract")
    if now > dg["expires"]:
        raise Reject("expired-authority", "delegation has expired")
    if right not in dg["rights"]:
        raise Reject("permission-denied", f"{attester} holds no {right} right")


def check_bundle(target, contract, binding_env, trust, output, bundle, now, rewrite=None, relay=None):
    """Return the provenance chain used for acceptance, or raise. `bundle` is a list of COSE_Sign1."""
    binding_hash = check_binding(binding_env, target, contract, trust, now)      # step 1, always
    delivered = art(output)
    evidence, attestations, delegations = {}, [], {}
    for env in bundle:
        kind = payload_of(env).get("kind")
        if kind not in ("evidence", "attestation", "delegation"):
            raise Reject("integrity-failure", f"unexpected {kind} in an evidence bundle")
        party, obj = open_signed(env, trust, kind)                                 # every item verifies
        if kind == "evidence":
            if obj["checker"] != party:
                raise Reject("integrity-failure", "evidence names a checker other than its signer")
            evidence[bytes(envelope_hash(env)[1])] = (party, obj, env)
        elif kind == "attestation":
            attestations.append((party, obj, env))
        else:
            delegations[bytes(oid(obj)[1])] = (party, obj, env)

    chain_delegations, chain_attestations = [], []
    for party, a, env in attestations:
        if a["attester"] != party:
            raise Reject("integrity-failure", "attestation names an attester other than its signer")
        d = delegations.get(bytes(a["delegation"][1]))
        if d is None:
            raise Reject("permission-denied", "attestation cites a delegation that was not delivered")
        issuer, dg, denv = d
        _delegation_ok(dg, issuer, party, contract, "attest", now)
        if bytes(a["evidence"][1]) not in evidence:
            raise Reject("validation-failure", "attestation names evidence that was not delivered")
        chain_delegations.append(oid(dg))
        chain_attestations.append(envelope_hash(env))

    if relay is not None:                                                          # who carried it here
        mine = [(i, dg) for i, dg, _ in delegations.values() if dg["grantee"] == relay]
        if not mine:
            raise Reject("permission-denied", f"relay {relay} presented no delegation")
        issuer, dg = mine[0]
        _delegation_ok(dg, issuer, relay, contract, "forward", now)
        if oid(dg) not in chain_delegations:
            chain_delegations.insert(0, oid(dg))

    if rewrite is not None:                                                        # plan or payload change
        rparty, rw, renv = rewrite
        d = delegations.get(bytes(rw["delegation"][1]))
        if d is None:
            raise Reject("permission-denied", "rewrite cites a delegation that was not delivered")
        issuer, dg, _ = d
        _delegation_ok(dg, issuer, rparty, contract, "rewrite", now)

    checkers = set(contract["evidence"].get("checkers", [])) | {contract["authority"]["publisher"]}
    used = []
    for p in contract["acceptance"] + contract.get("invariants", []):
        found = [(h, party, e) for h, (party, e, _) in evidence.items() if e["predicate"] == p["id"]]
        if not found:
            raise Reject("validation-failure", f"no evidence for required predicate {p['id']}")
        for h, party, e in found:
            if party not in checkers:
                raise Reject("validation-failure", f"evidence for {p['id']} is signed by {party}, "
                                                   f"who is not an accepted checker")
            if not (same(e["contract"], oid(contract)) and same(e["output"], delivered)):
                raise Reject("validation-failure", "evidence was measured on different bytes or another contract")
            if not e["pass"]:
                raise Reject("validation-failure", f"{p['id']} did not pass")
            used.append([-16, h])
    return {"binding": binding_hash, "delegations": chain_delegations, "attestations": chain_attestations,
            "evidence": used}


def reconstruct(receipt_env, consumer_trust, approval_env, store, trust, target, contract, now):
    """Third-party audit: from a receipt alone (plus the delivered objects), show that acceptance
    rested on the origin contract. Returns the chain [binding, (template), delegation(s), evidence] or
    raises. For a split binding, `contract` may be None: it is materialized from the stored template."""
    _, receipt = open_signed(receipt_env, consumer_trust, "receipt")
    _, approval = open_signed(approval_env, consumer_trust, "approval")
    if not same(receipt["approval"], oid(approval)):
        raise Reject("integrity-failure", "receipt names a different approval")
    binding_env = store.get(bytes(approval["binding"][1]))
    if binding_env is None:
        raise Reject("missing-dependency", "binding named by the approval is not available")
    chain = [approval["binding"]]
    b = payload_of(binding_env)
    if "template" in b:                                            # split form: the template joins the chain
        template = store.get(bytes(b["template"][1]))
        if template is None:
            raise Reject("missing-dependency", "template named by the binding is not available")
        contract = check_binding_any(binding_env, target, template, trust, now)["contract"]
        chain.append(b["template"])
    else:
        check_binding(binding_env, target, contract, trust, now)
    if not same(approval["contract"], oid(contract)):
        raise Reject("integrity-failure", "approval names a different contract than the binding")
    for ref in approval.get("relayed-by", []):                       # repeaters the inputs passed through
        env = store.get(bytes(ref[1]))
        if env is None:
            raise Reject("missing-dependency", "delegation named by the approval is not available")
        issuer, dg = open_signed(env, trust, "delegation")
        if not same(oid(dg), ref) or issuer != contract["authority"]["publisher"]:
            raise Reject("integrity-failure", "relay delegation does not match or is not publisher-signed")
        chain.append(ref)
    for ref in approval["evidence"]:
        env = store.get(bytes(ref[1]))
        if env is None:
            raise Reject("missing-dependency", "evidence named by the approval is not available")
        kind = payload_of(env).get("kind")
        party, obj = open_signed(env, trust, kind)
        if kind == "attestation" and not any(same(obj["delegation"], d) for d in chain):
            chain.append(obj["delegation"])
        if kind == "evidence" and not same(obj["output"], approval["output"]):
            raise Reject("integrity-failure", "evidence does not cover the committed output")
        chain.append(ref)
    return chain
