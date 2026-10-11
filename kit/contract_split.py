"""Contract split cases (T1-T14): a session contract template plus a small per-revision binding.

Built from the contract-split handoff (2026-10-11) with three changes found while implementing it:
- the binding also carries per-revision designated references (metric predicates need them);
- the contract identity is id(materialize(template, binding)), not the template digest, so evidence
  for one revision can't be reused for the next (T8) and every downstream object is unchanged (T12);
- the template is not signed separately; each binding signs its digest.
Called from run_checks.py; rows have the same shape as the rest of the report.
"""
from arfpkit.canon import Tag, art, decode, encode, oid, same, short
from arfpkit.cose import sign1
from arfpkit.engine import Engine, Store, patch
from arfpkit.gate import BINDING_KID, envelope_hash, handle_offer_any
from arfpkit.provenance import reconstruct
from arfpkit.rules import Reject, evidence_applies
from arfpkit.template import materialize, template_of
from stage1 import (CONSUMER_TRUST, NOW, PUB, PUBKEY, RT, RUNTIMES, TRUST, WS, WSKEY, approval_obj,
                    decode_receipt, digest_pred, edits, head_for, mk_contract, mk_plan, mk_scope, mk_target,
                    nd, new_consumer)

rows = []


def record(cid, title, expected, fn):
    try:
        observed, ok = fn()
    except Reject as r:
        observed, ok = f"unexpected reject {r.code}: {r.detail}", False
    rows.append({"id": cid, "case": title, "expected": expected, "observed": observed, "pass": bool(ok)})


def expect_reject(code, fn):
    try:
        fn()
    except Reject as r:
        return f"rejected {r.code}: {r.detail}", r.code == code
    return f"accepted (expected {code})", False


def split_binding(target, template, key=PUBKEY, kid=BINDING_KID, publisher=PUB, **fields):
    b = {"kind": "binding", "target": oid(target), "template": oid(template), "publisher": publisher,
         "issued": NOW}
    b.update(fields)
    return sign1(key, kid, b)


def offer(binding, target, plan, template=None):
    body = {"type": "OFFER", "binding": binding, "target": target, "scope": oid(mk_scope(target)), "plan": plan}
    if template is not None:
        body["template"] = template
    return {"kind": "message", "v": 0, "session": "s-split", "body": body}


def bound_to(plan, contract):
    if not same(plan["contract"], oid(contract)):
        raise Reject("ineligible-plan", "plan is bound to a different contract")


def run(main_target, main_contract):
    rows.clear()
    base = b"ARFP-split-baseline-" * 4                                  # 80 bytes
    outs = {r: patch(base, edits((0, f"rev{r}".encode()))) for r in (1, 2, 3)}
    targets = {r: mk_target("split/doc", r) for r in (1, 2, 3)}
    x_len = {"id": "x-len", "kind": "invariant", "covers": ["doc"], "threshold": len(outs[1]),
             "validator": "xbranch.len-sum.v1"}

    def whole(r, **extra_pred):
        """The v0.1 contract for revision r (expected digest of that revision's output)."""
        return mk_contract(targets[r], [digest_pred("p-doc", "doc", outs[r]), dict(x_len, **extra_pred)],
                           repairs=1)

    template, over1 = template_of(whole(1))
    over = {r: {"expected": {"p-doc": art(outs[r])}} for r in (1, 2, 3)}

    def plan_for(r, contract):
        nodes = [nd("base", "reference", artifact=art(base)),
                 nd("upd", "delta", ["base"], op="patch.v1", runtime=RT["patch.v1"], base=art(base),
                    params=edits((0, f"rev{r}".encode())), emits=["doc"]),
                 nd("root", "procedural", ["upd"], op="concat.v1", runtime=RT["concat.v1"])]
        return mk_plan(targets[r], contract, nodes, ["root"])

    plans = {r: plan_for(r, whole(r)) for r in (1, 2, 3)}
    bindings = {r: split_binding(targets[r], template, **over[r]) for r in (1, 2, 3)}

    # T1-T2: first use carries the template; later revisions name it
    cache, trace1 = {}, []
    res1 = handle_offer_any(offer(bindings[1], targets[1], plans[1], template), TRUST, NOW, bound_to, trace1, cache)
    record("T1", "First offer of a session carries the template inline",
           "accepted; template cached; plan bound to the materialized contract",
           lambda: (f"trace {trace1}; cached {[short([-16, k]) for k in cache]}; materialized id equals the "
                    f"whole contract's: {same(oid(res1['contract']), oid(whole(1)))}",
                    trace1 == ["binding", "eligibility"] and bytes(oid(template)[1]) in cache
                    and same(oid(res1["contract"]), oid(whole(1)))))
    trace2 = []
    msg2 = offer(bindings[2], targets[2], plans[2])
    res2 = handle_offer_any(msg2, TRUST, NOW, bound_to, trace2, cache)
    whole2 = {"kind": "message", "v": 0, "session": "s-split",
              "body": {"type": "OFFER", "binding": sign1(PUBKEY, BINDING_KID, {
                  "kind": "binding", "target": oid(targets[2]), "contract": oid(whole(2)), "publisher": PUB,
                  "issued": NOW}), "target": targets[2], "contract": whole(2), "scope": oid(mk_scope(targets[2])),
                  "plan": plans[2]}}
    record("T2", "Next revision names the cached template; the offer omits it",
           "accepted; smaller than the same offer with the whole contract",
           lambda: (f"trace {trace2}; offer {len(encode(msg2))} B vs {len(encode(whole2))} B with the whole "
                    f"contract inline", trace2 == ["binding", "eligibility"]
                    and same(oid(res2["contract"]), oid(whole(2))) and len(encode(msg2)) < len(encode(whole2))))

    # T3-T5, T14: the template must be exactly the one the binding names
    calls = []

    def counting(plan, contract):
        calls.append(1)

    trace3 = []
    record("T3", "Template neither cached nor offered", "reject missing-dependency; planning never runs",
           lambda: (lambda r: (f"{r[0]}; trace {trace3}; eligibility calls {len(calls)}",
                               r[1] and trace3 == ["binding"] and not calls))(
               expect_reject("missing-dependency", lambda: handle_offer_any(
                   offer(bindings[3], targets[3], plans[3]), TRUST, NOW, counting, trace3, {}))))
    amended = dict(template, limits={"repairs": 9})
    record("T4", "Inline template differs from the one the binding names", "reject integrity-failure",
           lambda: expect_reject("integrity-failure", lambda: handle_offer_any(
               offer(bindings[3], targets[3], plans[3], amended), TRUST, NOW, bound_to, [], {})))

    def t5():
        only_amended = {bytes(oid(amended)[1]): amended}
        r_missing = expect_reject("missing-dependency", lambda: handle_offer_any(
            offer(bindings[3], targets[3], plans[3]), TRUST, NOW, bound_to, [], only_amended))
        both = {**only_amended, bytes(oid(template)[1]): template}
        res = handle_offer_any(offer(bindings[3], targets[3], plans[3]), TRUST, NOW, bound_to, [], both)
        return (f"amended id differs: {not same(oid(amended), oid(template))}; with only the amended one cached: "
                f"{r_missing[0]}; with both cached the binding resolves to the original rules "
                f"(repairs={res['contract']['limits']['repairs']})",
                r_missing[1] and res["contract"]["limits"]["repairs"] == 1)
    record("T5", "An amended template in the cache never applies to bindings that name the original",
           "missing-dependency, or the original rules", t5)

    def wrong_digest_offer():
        m = offer(bindings[3], targets[3], plans[3])
        m["body"]["template"] = oid(amended)
        return handle_offer_any(m, TRUST, NOW, bound_to, [], cache)
    record("T14", "Offer names a template digest that disagrees with the binding", "reject integrity-failure",
           lambda: expect_reject("integrity-failure", wrong_digest_offer))

    # T6-T7, T13: overrides and authority
    record("T6", "Binding sets a value for a predicate the template lacks", "reject invalid-contract",
           lambda: expect_reject("invalid-contract", lambda: handle_offer_any(
               offer(split_binding(targets[3], template, expected={"p-doc": art(outs[3]), "p-ghost": art(b"x")}),
                     targets[3], plans[3], template), TRUST, NOW, bound_to, [], {})))
    record("T7", "Digest-match predicate left without an expected digest", "reject invalid-contract",
           lambda: expect_reject("invalid-contract", lambda: handle_offer_any(
               offer(split_binding(targets[3], template), targets[3], plans[3], template),
               TRUST, NOW, bound_to, [], {})))
    foreign = dict(template, authority={"publisher": "key:someone-else", "local-commit": True})
    record("T13", "Publisher signs a binding for a template whose authority names someone else",
           "reject permission-denied",
           lambda: expect_reject("permission-denied", lambda: handle_offer_any(
               offer(split_binding(targets[3], foreign, **over[3]), targets[3], plans[3], foreign),
               TRUST, NOW, bound_to, [], {})))

    # T8: evidence binds the revision's contract, not the template
    c1, c2 = materialize(template, payload(bindings[1])), materialize(template, payload(bindings[2]))
    shared_out = art(base)                                           # a region unchanged between revisions
    ev = {"kind": "evidence", "contract": oid(c1), "scope": oid(mk_scope(targets[2])), "output": shared_out,
          "predicate": "x-len", "pass": True, "validator": "xbranch.len-sum.v1", "checker": WS, "at": NOW}
    record("T8", "Evidence from revision 1 offered for revision 2 under the same template",
           "not reused; the template digest alone could not tell the revisions apart",
           lambda: (f"applies under rev 2: {evidence_applies(ev, c2, mk_scope(targets[2]), shared_out, NOW)}; "
                    f"contract ids differ: {not same(oid(c1), oid(c2))}; template ids equal: "
                    f"{same(payload(bindings[1])['template'], payload(bindings[2])['template'])}",
                    not evidence_applies(ev, c2, mk_scope(targets[2]), shared_out, NOW)
                    and not same(oid(c1), oid(c2))))

    # T9: a threshold override applies to its own revision only
    def attempt(r, binding):
        res = handle_offer_any(offer(binding, targets[r], plan_for(r, materialize(template, payload(binding)))),
                               TRUST, NOW, bound_to, [], {bytes(oid(template)[1]): template})
        store = Store()
        store.put(base)
        return Engine(store, RUNTIMES).run(plan_for(r, res["contract"]), res["contract"], {}, res["binding"], "a1")
    tight = split_binding(targets[3], template, params={"x-len": len(outs[3]) + 1}, **over[3])
    record("T9", "Threshold override in one revision's binding", "that revision fails; the others keep the default",
           lambda: (lambda a, b: (f"rev 2 (default): {a['status']}; rev 3 (override {len(outs[3]) + 1}): "
                                  f"{b['status']} ({b.get('reason')})",
                                  a["status"] == "validated" and b["status"] == "aborted"
                                  and b.get("reason") == "validation-failure"))(
               attempt(2, bindings[2]), attempt(3, tight)))

    # T10: gate order holds for split bindings
    flipped = Tag(18, list(bindings[3].value))
    sig = bytearray(flipped.value[3])
    sig[0] ^= 1
    flipped.value[3] = bytes(sig)
    calls.clear()

    def refuse(plan, contract):
        calls.append(1)
        raise Reject("ineligible-plan", "plan would also fail")
    record("T10", "Forged split binding and an ineligible plan together", "binding error first; planning never runs",
           lambda: (lambda r: (f"{r[0]}; eligibility calls {len(calls)}", r[1] and not calls))(
               expect_reject("integrity-failure", lambda: handle_offer_any(
                   offer(flipped, targets[3], plans[3], template), TRUST, NOW, refuse, [], {}))))

    # T11: a split-form update commits, and the receipt alone rebuilds the chain through the template
    def t11():
        genesis = head_for(targets[1], whole(1), outs[1])
        consumer = new_consumer("split/doc", genesis)
        res = handle_offer_any(offer(bindings[2], targets[2], plans[2], template), TRUST, NOW,
                               lambda p, c: consumer.admit(p["snapshot"]), [], {})
        store = Store()
        store.put(base)
        result = Engine(store, RUNTIMES).run(plans[2], res["contract"], {}, res["binding"], "a1")
        consumer.stage(result["output"])
        ev_env = sign1(WSKEY, WS, {"kind": "evidence", "contract": oid(res["contract"]),
                                   "scope": oid(mk_scope(targets[2])), "output": art(result["output"]),
                                   "predicate": "p-doc", "pass": True, "validator": "canon.digest.v1",
                                   "checker": WS, "at": NOW})
        appr = approval_obj(res["binding"], targets[2], res["contract"], plans[2], result["output"],
                            [envelope_hash(ev_env)], "tx-split-2", consumer.head_id())
        appr_env = sign1(WSKEY, WS, appr)
        receipt_env = consumer.commit(appr_env, WSKEY.public_key())
        audit = {bytes(res["binding"][1]): bindings[2], bytes(oid(template)[1]): template,
                 bytes(envelope_hash(ev_env)[1]): ev_env}
        chain = reconstruct(receipt_env, CONSUMER_TRUST, appr_env, audit, TRUST, targets[2], None, NOW)
        status = decode_receipt(receipt_env)["status"]
        return (f"receipt {status}; chain {[short(d) for d in chain]}; template in chain: "
                f"{any(same(d, oid(template)) for d in chain)}",
                status == "committed" and any(same(d, oid(template)) for d in chain)
                and same(appr["contract"], oid(whole(2))))
    record("T11", "Split-form update commits; the receipt alone rebuilds binding, template and evidence",
           "committed; the chain names the template", t11)

    # T12: the split loses nothing
    tmpl_main, over_main = template_of(main_contract)
    b_main = {"kind": "binding", "target": main_contract["target"], "template": oid(tmpl_main),
              "publisher": PUB, "issued": NOW, **over_main}
    record("T12", "Template plus binding reproduce the whole assembly contract", "identical object and id",
           lambda: (lambda m: (f"identical: {m == main_contract}; same id: {same(oid(m), oid(main_contract))}; "
                               f"moved to the binding: {len(over_main.get('expected', {}))} expected digests, "
                               f"{len(over_main.get('references', {}))} reference",
                               m == main_contract and same(oid(m), oid(main_contract))))(
               materialize(tmpl_main, b_main)))
    return list(rows)


def payload(env):
    return decode(env.value[2])
