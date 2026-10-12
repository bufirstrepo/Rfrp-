"""Speed-mechanism cases: fidelity per receiver (F1-F8), speculative start (P1-P8), proof-based evidence
(V1-V8), and push on a standing subscription (U1-U13).

From docs/proposals/ARFP-speed-mechanisms.md. Ideas 3 (compute once, fan out) and 4 (cancel superseded
work) reuse rules the kit already tests (C15-C18, C27); U7 adds the supersession check for pushes.
Called from run_checks.py; rows have the same shape as the rest of the report. Object level only: the
generator and the activations are deterministic stand-ins, not a model.
"""
import hashlib

from arfpkit.canon import art, encode, num, oid
from arfpkit.cose import fixture_key, sign1
from arfpkit.gate import BINDING_KID, TrustStore, check_binding_any
from arfpkit.rules import Reject
from arfpkit.speed import (PROOF_SCHEME, check_demand_accept, check_output_classes, check_plan_bounds,
                           check_proof_evidence, check_provisional_commit, check_push, check_receiver_bound,
                           check_speculation, coarse, make_proof, subscribe, toy_activations, toy_decode,
                           verify_draft)
from arfpkit.template import materialize

rows = []
CTX = {}
WORKER = "key:worker-1"
FAIRING = "fairing.hausdorff.v1"
CLEARANCE = "clearance.min.v1"


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


def all_of(checks):
    """Sub-checks [(label, fn)], each fn returning (observed, ok): the case passes only if every one does."""
    parts, ok = [], True
    for i, (label, fn) in enumerate(checks, 1):
        obs, good = fn()
        parts.append(f"[{i}] {label}: {obs}")
        ok &= good
    return " ".join(parts), ok


def setup(ctx):
    """Build the objects the cases and the fixture table need. `ctx` comes from run_checks.py."""
    CTX.clear()
    CTX.update(ctx)
    c, target, plan_ws, WS, PUB = ctx["contract"], ctx["target"], ctx["plan_ws"], ctx["WS"], ctx["PUB"]

    # 1. fidelity chosen per receiver; the same demand opens the subscription used in 6
    CTX["demand_sub"] = {"kind": "demand", "consumer": WS, "stream": "view", "seq": 3, "target": oid(target),
                         "scope": oid(ctx["scope_all"]),
                         "accept": {"classes": ["E", "T"], "bounds": {FAIRING: num("0.45")}},
                         "subscribe": True}

    # 2. speculative start: a 256-byte state; what arrives first is its coarse view
    exact = b"".join(hashlib.sha256(b"kv-state" + bytes([i])).digest() for i in range(8))
    prov = coarse(exact)
    prompt, n = b"handoff-prompt", 48
    draft = toy_decode(prov, prompt, n)
    kept, final = verify_draft(draft, exact, prompt)
    CTX.update(exact=exact, prov=prov, prompt=prompt, n=n, draft=draft, kept=kept, final=final)
    CTX["spec"] = {"kind": "speculation", "plan": oid(plan_ws), "provisional": art(prov), "exact": art(exact),
                   "drafted": art(bytes(draft)), "accepted": kept, "output": art(bytes(final)), "checker": WS,
                   "at": ctx["NOW"]}

    # 5. proof-based evidence from an untrusted worker
    rt_llm, inp = art(b"runtime:llm.toy.v1"), art(b"prompt: summarize the interstage revision")
    out = art(b"output tokens from the worker")
    c_proof = dict(c, evidence=dict(c["evidence"], modes=c["evidence"]["modes"] + ["proof"]))
    wkey = fixture_key(WORKER)
    trust = TrustStore()
    trust.add(WORKER, WORKER, wkey.public_key())

    def proof_ev(contract=c_proof, runtime_claim=rt_llm, runtime_run=rt_llm, inp_claim=inp, at=ctx["NOW"],
                 checker=WORKER, passed=True, scheme=PROOF_SCHEME):
        e = {"kind": "evidence", "contract": oid(contract), "scope": oid(ctx["scope_all"]), "output": out,
             "predicate": "inference.claimed-run.v1", "pass": passed, "validator": "proof." + PROOF_SCHEME,
             "checker": checker, "at": at,
             "proof": {"scheme": scheme, "runtime": runtime_claim, "input": inp_claim,
                       "data": make_proof(toy_activations(runtime_run, inp_claim, out))}}
        return e, sign1(wkey, WORKER, e)

    CTX.update(rt_llm=rt_llm, inp=inp, out=out, c_proof=c_proof, trust_w=trust, proof_ev=proof_ev)

    # 6. push on a standing subscription: revision 29 under the session template (contract split)
    tmpl, split = ctx["template_obj"], ctx["split_binding_obj"]
    target29 = dict(target, revision=29)
    b29 = {k: v for k, v in split.items()}
    b29["target"] = oid(target29)
    env29 = sign1(ctx["KEYS"][PUB], BINDING_KID, b29)
    contract29 = materialize(tmpl, b29)
    latent29 = b"latent fairing, revision 29:" + ctx["latent_bytes"][28:]
    plan29 = dict(plan_ws, target=oid(target29), contract=oid(contract29), parent=oid(plan_ws),
                  scope=oid(dict(ctx["scope_all"], target=oid(target29))),
                  nodes=[dict(nd, payload=art(latent29)) if nd["id"] == "fairing" else nd for nd in plan_ws["nodes"]])
    pub_trust = TrustStore()
    pub_trust.add(BINDING_KID, PUB, ctx["KEYS"][PUB].public_key())
    CTX.update(target29=target29, env29=env29, contract29=contract29, latent29=latent29, plan29=plan29,
               pub_trust=pub_trust, tmpl_id=oid(tmpl), templates={bytes(oid(tmpl)[1]): tmpl})
    CTX["push_body"] = {"type": "PUSH", "stream": "view", "seq": 4, "target": target29, "binding": env29,
                        "plan": plan29, "base": ctx["out_ws"],
                        "chunks": [{"node": "fairing", "digest": art(latent29), "data": latent29}]}
    ev_proof, _ = proof_ev()
    return {"demand (receiver acceptance, subscription)": CTX["demand_sub"],
            "speculation": CTX["spec"],
            "evidence (proof)": ev_proof,
            "msg PUSH": ctx["msg"](CTX["push_body"])}


def run():
    rows.clear()
    x = CTX
    c, plan_ws, WS = x["contract"], x["plan_ws"], x["WS"]

    # ------------------------------------------------------------ 1. fidelity chosen per receiver
    def demand(**accept):
        return dict(x["demand_sub"], accept=accept)

    def plan_ok(d, plan=plan_ws):
        x["elig_ws"](plan)
        check_demand_accept(d, c)
        check_plan_bounds(plan, c, d)
        return check_output_classes(plan, d, x["RT_WS"], WS, c)

    record("F1", "Receiver accepts bounded output within the contract's bound", "the latent fairing plan is eligible",
           lambda: ("accepted; declared error 0.35 mm fits the contract's 0.5 mm", plan_ok(demand(classes=["E", "T"]))))

    lit = x["plan_for"](41, x["nd"]("fairing", "literal", payload=art(encode(x["fairing_ref"])),
                                    emits=["fairing-surface"]))

    def f2():
        d = demand(classes=["E", "T"], bounds={FAIRING: 0})
        obs, ok = expect_reject("ineligible-plan", lambda: plan_ok(d))
        plan_ok(d, lit)
        b_lat, b_lit = len(x["latent_bytes"]), len(encode(x["fairing_ref"]))
        return (f"{obs}; the literal reference plan is eligible instead ({b_lit:,} B vs {b_lat:,} B latent)", ok)

    record("F2", "Receiver requires the exact reference geometry (bound 0)", "latent plan rejected for it; exact plan chosen", f2)
    record("F3", "Demand tries to loosen the contract's bound (0.6 mm vs 0.5 mm)", "reject permission-denied",
           lambda: expect_reject("permission-denied",
                                 lambda: check_demand_accept(demand(classes=["E", "T"], bounds={FAIRING: num("0.6")}), c)))

    def f4():
        d = demand(classes=["E", "T"], bounds={FAIRING: num("0.4")})
        plan_ok(d)                                                   # declared 0.35 mm fits 0.4 at planning
        check_receiver_bound(c, None, FAIRING, x["total_ws"])        # another receiver: 0.425 <= 0.5
        obs, ok = expect_reject("validation-failure", lambda: check_receiver_bound(c, d, FAIRING, x["total_ws"]))
        return f"plan eligible; composed bound {x['total_ws']} mm passes the contract's 0.5 for others; {obs}", ok

    record("F4", "Receiver tightens the bound to 0.4 mm", "eligible, then fails validation for it only", f4)
    record("F5", "Receiver refuses generated content even where the contract allows it", "reject ineligible-plan",
           lambda: expect_reject("ineligible-plan", lambda: plan_ok(demand(classes=["E", "T"], free=False))))

    def f6():
        d = demand(classes=["E"])
        obs, ok = expect_reject("ineligible-plan", lambda: plan_ok(d))
        upstream = x["plan_for"](41, x["fairing"](x["rt_surf"], at=x["R1"]))
        plan_ok(d, upstream)
        return (f"local decode {obs}; the same decode run at the repeater arrives as exact bytes and is eligible "
                "(classes set reproducibility; bounds set fidelity, F2 and F4)", ok)

    record("F6", "Receiver accepts only reproducible (E) copies", "local T decode rejected; upstream decode accepted", f6)
    record("F7", "Demand sets 1 mm on the 2 mm clearance minimum (smaller would loosen a minimum)",
           "reject permission-denied (only metric bounds can be tightened)",
           lambda: expect_reject("permission-denied",
                                 lambda: check_demand_accept(demand(classes=["E", "T"], bounds={CLEARANCE: 1}), c)))

    def f8():
        unclaimed = dict(plan_ws, nodes=[{k: v for k, v in n.items() if k != "claim"} if n["id"] == "fairing" else n
                                         for n in plan_ws["nodes"]])
        return expect_reject("ineligible-plan",
                             lambda: plan_ok(demand(classes=["E", "T"], bounds={FAIRING: num("0.45")}), unclaimed))

    record("F8", "Latent plan that declares no error, for a receiver with its own bound", "reject ineligible-plan", f8)

    # ------------------------------------------------------------ 2. speculative start
    exact, prov, prompt, n, draft = x["exact"], x["prov"], x["prompt"], x["n"], x["draft"]
    needs_exact = dict(x["demand_sub"], accept={"classes": ["E"]})
    accepts_t = dict(x["demand_sub"], accept={"classes": ["E", "T"]})

    def p1():
        def chk():
            return check_speculation(x["spec"], plan_ws, prov, exact, prompt, draft, x["final"])
        cls = check_provisional_commit(needs_exact, c, True, chk)
        same_as_exact = x["final"] == toy_decode(exact, prompt, n)
        return (f"kept {x['kept']} of {n} drafted tokens, exact token at the first mismatch, rest decoded exactly; "
                f"committed as {cls}; output identical to decoding on the exact state: {same_as_exact}",
                cls == "E" and same_as_exact)

    record("P1", "Draft on the coarse state, checked once the exact state arrives", "commits; identical output", p1)
    record("P2", "Provisional output committed with no check by a receiver that did not opt in (coarse bound in range)",
           "reject validation-failure",
           lambda: expect_reject("validation-failure", lambda: check_provisional_commit(
               needs_exact, c, True, coarse_bound=num("0.3"), pid=FAIRING)))
    other_exact = bytes(b ^ 0x01 for b in exact)
    record("P3", "Speculation record checked against a different exact state", "reject integrity-failure",
           lambda: expect_reject("integrity-failure", lambda: check_speculation(
               dict(x["spec"], exact=art(other_exact)), plan_ws, prov, exact, prompt, draft, x["final"])))
    record("P4", "Speculation record claims more verified tokens than the check keeps", "reject validation-failure",
           lambda: expect_reject("validation-failure", lambda: check_speculation(
               dict(x["spec"], accepted=x["kept"] + 5), plan_ws, prov, exact, prompt, draft, x["final"])))

    def p5():
        cls = check_provisional_commit(accepts_t, c, True, coarse_bound=num("0.3"), pid=FAIRING)
        return f"accepted; coarse layer declares 0.3 mm within 0.5 mm; committed as class {cls} without waiting", cls == "T"

    record("P5", "Receiver that opts in uses the provisional draft, within a declared bound", "commits, labeled T", p5)
    record("P6", "Receiver opts in, but the coarse layer declares no bound within the contract",
           "reject validation-failure (a receiver cannot loosen the contract)",
           lambda: expect_reject("validation-failure", lambda: check_provisional_commit(
               accepts_t, c, True, coarse_bound=num("0.6"), pid=FAIRING)))
    c_exact_only = dict(c, determinism=dict(c["determinism"], **{"evidence-transfer": ["E"]}))
    record("P7", "Receiver opts in, bound in range, but the contract accepts no T-class evidence", "reject validation-failure",
           lambda: expect_reject("validation-failure", lambda: check_provisional_commit(
               accepts_t, c_exact_only, True, coarse_bound=num("0.3"), pid=FAIRING)))

    def p8():
        spec, fin = x["spec"], x["final"]

        def chk(rec=spec, output=fin):
            return lambda: check_speculation(rec, plan_ws, prov, exact, prompt, draft, output)
        other_out = fin[:-1] + [(fin[-1] + 1) % 32]
        other_draft = draft[:-1] + [(draft[-1] + 1) % 32]
        return all_of([
            ("another plan", lambda: expect_reject("integrity-failure", chk(dict(spec, plan=oid(x["plan29"]))))),
            ("another provisional state",
             lambda: expect_reject("integrity-failure", chk(dict(spec, provisional=art(b"another coarse layer"))))),
            ("another draft", lambda: expect_reject("integrity-failure", chk(dict(spec, drafted=art(bytes(other_draft)))))),
            ("committed output differs from the verified one",
             lambda: expect_reject("validation-failure", chk(output=other_out))),
        ])

    record("P8", "Speculation record that misnames the plan, provisional state or draft, or a committed output it does not verify",
           "each rejected", p8)

    # ------------------------------------------------------------ 5. proof-based evidence
    calls = []

    def recompute(r, i, o):                         # the verifier's one parallel pass, on different hardware
        calls.append(1)
        return toy_activations(r, i, o, noise=7)

    def proof_check(env, contract=None):
        calls.clear()
        check_proof_evidence(env, x["trust_w"], contract or x["c_proof"], x["scope_all"], x["rt_llm"], x["inp"],
                             x["out"], x["NOW"], recompute)

    def v1():
        e, env = x["proof_ev"]()
        proof_check(env)
        return (f"accepted after {len(calls)} recomputation pass with hardware noise; proof {len(e['proof']['data'])} B; "
                "the worker's generation was not repeated", len(calls) == 1)

    record("V1", "Untrusted worker's output with a valid proof", "accepted with one recomputation pass", v1)
    record("V2", "Worker ran a different model but claims the contracted one", "reject validation-failure",
           lambda: expect_reject("validation-failure", lambda: proof_check(
               x["proof_ev"](runtime_run=art(b"runtime:llm.cheaper.v1"))[1])))

    def no_compute(code, env):
        obs, ok = expect_reject(code, lambda: proof_check(env))
        return f"{obs}; recomputation passes spent: {len(calls)}", ok and not calls

    record("V3", "Proof made for a different input", "reject validation-failure before any recomputation",
           lambda: no_compute("validation-failure", x["proof_ev"](inp_claim=art(b"another prompt"))[1]))
    record("V4", "Contract does not accept proof evidence", "reject validation-failure",
           lambda: expect_reject("validation-failure", lambda: proof_check(x["proof_ev"](contract=c)[1], contract=c)))

    def v5():
        e, env = x["proof_ev"]()
        payload = bytearray(env.value[2])
        data = e["proof"]["data"]
        at = bytes(payload).find(data)
        payload[at + len(data) - 1] ^= 0x01         # one byte inside the proof data itself
        env.value[2] = bytes(payload)
        return expect_reject("integrity-failure", lambda: proof_check(env))

    record("V5", "Proof bytes edited after signing", "reject integrity-failure", v5)
    record("V6", "Proof states a runtime other than the one the plan names", "reject validation-failure before any recomputation",
           lambda: no_compute("validation-failure", x["proof_ev"](runtime_claim=art(b"runtime:llm.other.v2"),
                                                                    runtime_run=art(b"runtime:llm.other.v2"))[1]))
    record("V7", "Proof evidence older than the contract's max-age", "reject validation-failure before any recomputation",
           lambda: no_compute("validation-failure", x["proof_ev"](at=x["NOW"] - 10 * 86_400_000)[1]))
    record("V8", "Proof evidence that names another checker, reports a failed check, or uses an unsupported scheme",
           "each rejected before any recomputation",
           lambda: all_of([
               ("checker is not the signer",
                lambda: no_compute("integrity-failure", x["proof_ev"](checker="key:worker-2")[1])),
               ("reports a failed check", lambda: no_compute("validation-failure", x["proof_ev"](passed=False)[1])),
               ("unsupported scheme", lambda: no_compute("validation-failure", x["proof_ev"](scheme="other-proof.v1")[1])),
           ]))

    # ------------------------------------------------------------ 6. push on a standing subscription
    def gate(env, target):
        return check_binding_any(env, target, None, x["pub_trust"], x["NOW"], templates=x["templates"])

    def elig(plan, contract):
        return x["elig_ws"](plan, c=contract)

    def fresh_subs():
        subs = {}
        subscribe(subs, x["demand_sub"], plan_ws, x["tmpl_id"])
        subscribe(subs, dict(x["demand_sub"], stream="edits", seq=7), plan_ws, x["tmpl_id"])
        return subs

    def push(body, consumer=WS, subs=None, gate_fn=gate):
        return check_push(body, consumer, subs if subs is not None else fresh_subs(), x["out_ws"], 41, gate_fn, elig,
                          x["RT_WS"])

    def subs_with(demand_changes=None, template=None):
        subs = {}
        subscribe(subs, dict(x["demand_sub"], **(demand_changes or {})), plan_ws, template or x["tmpl_id"])
        return subs

    pb = x["push_body"]
    record("U1", "Revision 29 pushed on a standing subscription", "applied without OFFER/ACCEPT",
           lambda: ("applied: the revision's binding passed gate zero against the cached template, the plan is a "
                    "same-shape child of the subscribed plan, and the pushed bytes match it", push(pb)))
    record("U2", "Push assumes a base the receiver does not hold", "reject baseline-mismatch (receiver sends REPAIR)",
           lambda: expect_reject("baseline-mismatch", lambda: push(dict(pb, base=art(b"some other head")))))
    record("U3", "Push to a receiver with no subscription", "reject permission-denied",
           lambda: expect_reject("permission-denied", lambda: push(pb, consumer=x["PH"])))

    def u4():
        env = x["env29"]
        forged = type(env)(env.tag, [env.value[0], env.value[1], env.value[2],
                                     bytes([env.value[3][0] ^ 0x01]) + env.value[3][1:]])
        return expect_reject("integrity-failure", lambda: push(dict(pb, binding=forged)))

    record("U4", "Push carries a binding with a forged signature", "reject integrity-failure (gate zero)", u4)
    record("U5", "Push on the required-transition stream, which the contract gives no fast path", "reject ineligible-plan",
           lambda: expect_reject("ineligible-plan", lambda: push(dict(pb, stream="edits", seq=8))))

    def u6():
        extra = x["nd"]("note", "literal", payload=art(b"annotation"), emits=["skin-texture"])
        reshaped = dict(x["plan29"], nodes=x["plan29"]["nodes"][:-1] + [extra, x["plan29"]["nodes"][-1]])
        return expect_reject("ineligible-plan", lambda: push(dict(pb, plan=reshaped)))

    record("U6", "Push whose plan changes shape", "reject ineligible-plan (full OFFER/ACCEPT required)", u6)

    def u7():
        subs = fresh_subs()
        push(dict(pb, seq=5), subs=subs)
        return expect_reject("canceled", lambda: push(dict(pb, seq=4), subs=subs))

    record("U7", "Older push arrives after a newer one on a replaceable stream", "reject canceled (superseded)", u7)
    record("U8", "Pushed bytes do not match the digest they carry", "reject integrity-failure",
           lambda: expect_reject("integrity-failure", lambda: push(dict(pb, chunks=[
               {"node": "fairing", "digest": art(x["latent29"]), "data": x["latent29"][:-1] + b"?"}]))))
    record("U9", "Push binding names a different target than the one pushed", "reject integrity-failure (gate zero)",
           lambda: expect_reject("integrity-failure", lambda: push(dict(pb, target=dict(x["target29"], revision=30)))))

    def u10():
        granted = dict(x["contract29"], updates=[r if r["stream"] != "edits" else dict(r, **{"fast-path": "shape-equal"})
                                                 for r in x["contract29"]["updates"]])
        return expect_reject("missing-dependency", lambda: push(
            dict(pb, stream="edits", seq=9), gate_fn=lambda env, t: dict(gate(env, t), contract=granted)))

    record("U10", "Gap on a required-transition stream whose contract grants a fast path", "reject missing-dependency", u10)
    swapped = b"latent fairing from some other revision"
    record("U11", "Pushed bytes match the digest they carry, but not the plan's payload", "reject integrity-failure",
           lambda: expect_reject("integrity-failure", lambda: push(dict(pb, chunks=[
               {"node": "fairing", "digest": art(swapped), "data": swapped}]))))
    record("U12", "Push that the subscriber's own acceptance rules out", "each rejected ineligible-plan, as F6 and F2 are",
           lambda: all_of([
               ("subscriber accepts only E copies; the plan decodes a latent locally (T)",
                lambda: expect_reject("ineligible-plan", lambda: push(pb, subs=subs_with({"accept": {"classes": ["E"]}})))),
               ("subscriber's own bound is 0.3 mm; the plan declares 0.35 mm",
                lambda: expect_reject("ineligible-plan", lambda: push(pb, subs=subs_with(
                    {"accept": {"classes": ["E", "T"], "bounds": {FAIRING: num("0.3")}}})))),
           ]))
    record("U13", "Push that does not match the subscription's contract", "each rejected",
           lambda: all_of([
               ("binding under a template outside the subscription",
                lambda: expect_reject("integrity-failure", lambda: push(pb, subs=subs_with(
                    template=art(b"an earlier session's template"))))),
               ("plan bound to the previous revision's contract",
                lambda: expect_reject("ineligible-plan", lambda: push(dict(pb, plan=dict(x["plan29"], contract=oid(c)))))),
               ("stream the revision's contract does not define",
                lambda: expect_reject("ineligible-plan", lambda: push(dict(pb, stream="pose"),
                                                                       subs=subs_with({"stream": "pose"})))),
           ]))
    return list(rows)
