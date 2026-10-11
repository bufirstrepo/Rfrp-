"""Stage-1 cases: gate zero (signed binding), C04, C07, C08, C10, C21 (real crashes), C27.

Each case family uses its own target, so failures in one cannot mask another. Called from
run_checks.py; returns result rows in the same shape as the rest of the report.
"""
import atexit
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from arfpkit.canon import H, Tag, art, decode, encode, oid, same, short
from arfpkit.cose import fixture_key, rfc8032_key, sign1
from arfpkit.engine import Engine, Store, patch
from arfpkit.gate import BINDING_KID, TrustStore, check_binding, envelope_hash, handle_offer
from arfpkit.journal import KILLED, DurableConsumer, Journal
from arfpkit.provenance import check_bundle, reconstruct
from arfpkit.rules import Reject


def died(rc):
    return "killed by SIGKILL" if rc == KILLED and rc < 0 else f"exit {rc}"


NOW = 1791698400000
PUB, WS, R2 = "key:publisher", "key:workstation", "key:repeater-2"
PUBKEY, WSKEY, R2KEY = rfc8032_key(), fixture_key(WS), fixture_key(R2)
KIT = Path(__file__).resolve().parent
ALL6 = ["reference", "delta", "procedural", "latent", "residual", "literal"]

TRUST = TrustStore()
TRUST.add(BINDING_KID, PUB, PUBKEY.public_key())
TRUST.add(WS, WS, WSKEY.public_key())
TRUST.add(R2, R2, R2KEY.public_key())
CONSUMER_TRUST = TrustStore()
CONSUMER_TRUST.add(WS, WS, WSKEY.public_key())

RT = {name: art(b"runtime:" + name.encode()) for name in ("patch.v1", "gen.repeat.v1", "concat.v1")}
RUNTIMES = {bytes(d[1]): name for name, d in RT.items()}

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


# ---------- builders ----------
def mk_target(obj, rev):
    return {"kind": "target", "object": obj, "revision": rev, "publisher": PUB, "profile": "bytes.exact.v1"}


def mk_scope(target):
    return {"kind": "scope", "target": oid(target), "select": "all"}


def mk_contract(target, acceptance, repairs=2, invariants=None):
    c = {"kind": "contract", "target": oid(target), "profile": "bytes.exact.v1", "classes": ALL6,
         "acceptance": acceptance,
         "determinism": {"baseline-eligible": ["E"], "evidence-transfer": ["E"]},
         "evidence": {"modes": ["digest-match"]},
         "authority": {"publisher": PUB, "local-commit": True},
         "updates": [{"stream": "view", "mode": "replaceable"}],
         "limits": {"repairs": repairs}}
    if invariants:
        c["invariants"] = invariants
    return c


def digest_pred(pid, region, data):
    return {"id": pid, "kind": "digest-match", "covers": [region], "expected": art(data), "mode": "digest-match",
            "validator": "canon.digest.v1"}


def mk_binding(target, contract, **extra):
    b = {"kind": "binding", "target": oid(target), "contract": oid(contract), "publisher": PUB, "issued": NOW}
    b.update(extra)
    return sign1(PUBKEY, BINDING_KID, b)


def nd(nid, cls, deps=(), **kw):
    n = {"id": nid, "class": cls, "deps": list(deps)}
    n.update(kw)
    return n


def mk_plan(target, contract, nodes, roots, snapshot=0, fallbacks=None):
    p = {"kind": "plan", "target": oid(target), "contract": oid(contract), "scope": oid(mk_scope(target)),
         "snapshot": snapshot, "nodes": nodes, "roots": roots}
    if fallbacks:
        p["fallbacks"] = fallbacks
    return p


def edits(*pairs):
    return encode([[o, r] for o, r in pairs])


def head_for(target, contract, output):
    return {"kind": "head", "object": target["object"], "target": oid(target), "contract": oid(contract),
            "scope": oid(mk_scope(target)), "output": art(output)}


def new_consumer(obj, genesis):
    root = Path(tempfile.mkdtemp(prefix="arfp-"))
    atexit.register(shutil.rmtree, root, True)
    c = DurableConsumer(root, WS, obj)
    c.seed(genesis)
    c.recover()
    return c


def approval_obj(binding_hash, target, contract, plan, output, evidence_ids, txn, expected_head, relayed=None):
    a = {"kind": "approval", "binding": binding_hash, "target": oid(target), "contract": oid(contract),
         "scope": oid(mk_scope(target)), "plan": oid(plan), "output": art(output), "evidence": evidence_ids,
         "txn": txn, "expected-head": expected_head, "authority": WS}
    if relayed:
        a["relayed-by"] = relayed
    return a


def evidence_ids(contract, target, result):
    ids = []
    for pid, ev in sorted(result["evidence"].items()):
        e = {"kind": "evidence", "contract": oid(contract), "scope": oid(mk_scope(target)), "output": ev["inputs"],
             "predicate": pid, "pass": ev["pass"], "validator": "canon.digest.v1", "checker": WS, "at": NOW}
        ids.append(oid(e))
    return ids


def attempt_and_commit(c, target, contract, plan, payloads, store, faults, txn, attempt):
    """Gate zero, run, and commit if validated. Returns (result, receipt or None)."""
    binding = mk_binding(target, contract)
    msg = {"kind": "message", "v": 0, "session": "s1", "body": {"type": "OFFER", "binding": binding,
                                                                 "target": target, "contract": contract,
                                                                 "scope": oid(mk_scope(target)), "plan": plan}}
    trace = []
    bh = handle_offer(msg, TRUST, NOW, lambda p, k: c.admit(p["snapshot"]), trace)
    eng = Engine(store, RUNTIMES, faults)
    res = eng.run(plan, contract, payloads, bh, attempt)
    res["engine"] = eng
    if res["status"] != "validated":
        return res, None
    c.stage(res["output"])
    appr = approval_obj(bh, target, contract, plan, res["output"], evidence_ids(contract, target, res), txn,
                        c.head_id())
    return res, decode_receipt(c.commit(sign1(WSKEY, WS, appr), WSKEY.public_key()))


def decode_receipt(env):
    from arfpkit.cose import verify1
    return verify1(WSKEY.public_key(), env)


def journal_counts(c):
    recs, _, _ = c.journal.scan()
    kinds = {}
    for r in recs:
        kinds[r["rec"]] = kinds.get(r["rec"], 0) + 1
    return kinds


# =====================================================================
# Gate zero
# =====================================================================
def gate_cases(target, contract, scope, plan, eligibility, published_envelope_hex):
    good = mk_binding(target, contract, issued=1791676800000)        # the section 9 vector

    def offer(binding, t=target, c=contract, p=plan):
        body = {"type": "OFFER", "target": t, "contract": c, "scope": oid(scope), "plan": p}
        if binding is not None:
            body["binding"] = binding
        return {"kind": "message", "v": 0, "session": "s-gate", "body": body}

    def run(binding, **kw):
        trace = []
        handle_offer(offer(binding, **kw), TRUST, NOW, eligibility, trace)
        return trace

    record("G1", "Valid publisher binding, checked before planning", "accepted; matches the published vector",
           lambda: (lambda t: (f"trace {t}; envelope matches section 9 vector: "
                               f"{encode(good).hex() == published_envelope_hex}",
                               t == ["binding", "eligibility"] and encode(good).hex() == published_envelope_hex))(
               run(good)))
    unknown = sign1(fixture_key("key:stranger"), "pubkey-unknown", payload_obj(good))
    record("G2", "Binding signed by a key not on the allow-list", "reject permission-denied",
           lambda: expect_reject("permission-denied", lambda: run(unknown)))
    flipped = Tag(18, list(good.value))
    sig = bytearray(flipped.value[3]); sig[0] ^= 1; flipped.value[3] = bytes(sig)
    record("G3", "Binding signature with one bit flipped", "reject integrity-failure",
           lambda: expect_reject("integrity-failure", lambda: run(flipped)))
    other_contract = dict(contract, limits=dict(contract["limits"], repairs=9))
    record("G4", "Offer carries a different contract than the one signed", "reject integrity-failure",
           lambda: expect_reject("integrity-failure", lambda: run(good, c=other_contract)))
    other_target = dict(target, revision=target["revision"] + 1)
    record("G5", "Offer carries a different target revision than the one signed", "reject integrity-failure",
           lambda: expect_reject("integrity-failure", lambda: run(good, t=other_target)))
    deleg = sign1(PUBKEY, BINDING_KID, {"kind": "delegation", "issuer": PUB, "grantee": R2, "target": oid(target),
                                         "contract": oid(contract), "scope": oid(scope), "rights": ["cache"],
                                         "recipients": [WS], "expires": NOW + 1, "subdelegate": False,
                                         "budget": {"cpu": 1}})
    record("G6", "Publisher's valid signature on a delegation, presented as the binding", "reject integrity-failure",
           lambda: expect_reject("integrity-failure", lambda: run(deleg)))
    impostor = sign1(R2KEY, R2, payload_obj(good))
    record("G7", "Allow-listed repeater key signs a binding in the publisher's name", "reject permission-denied",
           lambda: expect_reject("permission-denied", lambda: run(impostor)))
    expired = sign1(PUBKEY, BINDING_KID, dict(payload_obj(good), expires=NOW - 1))
    record("G8", "Expired binding", "reject expired-authority",
           lambda: expect_reject("expired-authority", lambda: run(expired)))
    calls = []

    def counting(p, c):
        calls.append(1)
        raise Reject("ineligible-plan", "plan would also fail")
    record("G9", "Forged binding and an ineligible plan together", "binding error first; planning never runs",
           lambda: (lambda r: (f"{r[0]}; eligibility calls: {len(calls)}", r[1] and not calls))(
               expect_reject("integrity-failure",
                             lambda: handle_offer(offer(flipped), TRUST, NOW, counting, []))))
    record("G10", "Offer with no binding", "reject permission-denied",
           lambda: expect_reject("permission-denied", lambda: run(None)))
    return good


def payload_obj(env):
    return decode(env.value[2])


# =====================================================================
# C04, C07, C08, C10
# =====================================================================
def c04_cases():
    t = mk_target("c04/doc", 2)
    base = b"ARFP-C04-baseline-" * 4
    want = patch(base, edits((0, b"arfp")))
    c = mk_contract(t, [digest_pred("p-doc", "doc", want)], repairs=1)
    genesis = head_for(mk_target("c04/doc", 1), c, base)
    nodes = [nd("base", "reference", artifact=art(base)),
             nd("upd", "delta", ["base"], op="patch.v1", runtime=RT["patch.v1"], base=art(base),
                params=edits((0, b"arfp")), emits=["doc"]),
             nd("root", "procedural", ["upd"], op="concat.v1", runtime=RT["concat.v1"])]
    alt = nd("base-lit", "literal", payload=art(base))

    def store_with_base():
        s = Store()
        s.put(base)
        return s

    control_c = new_consumer("c04/doc", genesis)
    control, _ = attempt_and_commit(control_c, t, c, mk_plan(t, c, nodes, ["root"]), {}, store_with_base(), {},
                                    "tx-c04-control", "a0")

    # C04a: no fallback
    ca = new_consumer("c04/doc", genesis)
    store_a = store_with_base()
    res_a, rec_a = attempt_and_commit(ca, t, c, mk_plan(t, c, nodes, ["root"]), {}, store_a,
                                      {"evict": [art(base)]}, "tx-c04a", "a1")
    counts_a = journal_counts(ca)
    record("C04a", "Dependency evicted after ACCEPT, no fallback", "abort; no approval, receipt or head change",
           lambda: (f"status {res_a['status']} ({res_a['reason']}); RESULT missing "
                    f"{[short(d) for d in res_a['results'][-1]['missing']]}; journal {counts_a}; head unchanged: "
                    f"{same(ca.head_id(), oid(genesis))}; staged files: {len(list(ca.staging.iterdir()))}",
                    res_a["status"] == "aborted" and rec_a is None and counts_a == {"genesis": 1}
                    and same(ca.head_id(), oid(genesis)) and not list(ca.staging.iterdir())
                    and same(res_a["results"][-1]["missing"][0], art(base))))
    # C04b: prebound literal fallback
    cb = new_consumer("c04/doc", genesis)
    res_b, rec_b = attempt_and_commit(cb, t, c, mk_plan(t, c, nodes + [alt], ["root"], fallbacks={"base": ["base-lit"]}),
                                      {bytes(art(base)[1]): base}, store_with_base(), {"evict": [art(base)]},
                                      "tx-c04b", "a2")
    rep = res_b["repairs"][0]["repair"] if res_b["repairs"] else {}
    record("C04b", "Dependency evicted, prebound literal fallback", "REPAIR names the cone; commit equals control",
           lambda: (f"REPAIR failed={rep.get('failed')} affected={rep.get('affected')} alt={rep.get('alternative')}; "
                    f"receipt {rec_b['status'] if rec_b else None}; output equals no-fault control: "
                    f"{same(art(res_b['output']), art(control['output']))}",
                    rep.get("failed") == "base" and rep.get("affected") == ["base", "root", "upd"]
                    and rec_b is not None and rec_b["status"] == "committed"
                    and same(art(res_b["output"]), art(control["output"]))))
    # C04c: the failed attempt does not poison the target
    lit_nodes = [nd("base", "literal", payload=art(base))] + nodes[1:]
    res_c, rec_c = attempt_and_commit(ca, t, c, mk_plan(t, c, lit_nodes, ["root"]), {bytes(art(base)[1]): base},
                                      store_a, {}, "tx-c04c", "a3")
    record("C04c", "New offer after the aborted attempt, re-supplying the artifact", "processed and committed",
           lambda: (f"receipt {rec_c['status'] if rec_c else res_c['status']}",
                    rec_c is not None and rec_c["status"] == "committed"))
    bound = all(e.get("binding") is None or e["event"] == "accept" for e in res_a["audit"]) and \
        res_a["audit"][0]["event"] == "accept" and res_a["audit"][0]["binding"] is not None
    record("C04d", "Audit trail of the aborted attempt", "accept bound to the binding, then the abort",
           lambda: (f"events: {[e['event'] for e in res_a['audit']]}",
                    bound and [e["event"] for e in res_a["audit"]] == ["accept", "abort"]))


def c07_cases():
    t = mk_target("c07/doc", 1)
    tile = b"tile" * 64
    post = patch(tile, edits((0, b"TILE")))
    c = mk_contract(t, [digest_pred("p-pattern", "pattern", tile), digest_pred("p-post", "post", post)], repairs=1)
    genesis = head_for(mk_target("c07/doc", 0), c, b"")
    nodes = [nd("gen", "procedural", op="gen.repeat.v1", runtime=RT["gen.repeat.v1"],
                params=encode({"pattern": b"tile", "n": 64}), emits=["pattern"]),
             nd("post", "procedural", ["gen"], op="patch.v1", runtime=RT["patch.v1"], params=edits((0, b"TILE")),
                emits=["post"]),
             nd("root", "procedural", ["gen", "post"], op="concat.v1", runtime=RT["concat.v1"])]
    ca = new_consumer("c07/doc", genesis)
    res_a, rec_a = attempt_and_commit(ca, t, c, mk_plan(t, c, nodes, ["root"]), {}, Store(), {"diverge": ["gen"]},
                                      "tx-c07a", "a1")
    rej = next((e for e in res_a["audit"] if e["event"] == "rejected-output"), {})
    record("C07a", "Procedural generator diverges, no fallback", "rejected at emission; dependent never runs",
           lambda: (f"status {res_a['status']}; executed {res_a['engine'].trace}; audit names node "
                    f"{rej.get('node')}, runtime {short(rej.get('runtime'))}, observed {short(rej.get('observed', [None])[0])}",
                    res_a["status"] == "aborted" and "post" not in res_a["engine"].trace and rec_a is None
                    and rej.get("node") == "gen" and same(rej.get("runtime"), RT["gen.repeat.v1"])
                    and not same(rej["observed"][0], art(tile)) and same(ca.head_id(), oid(genesis))))
    cb = new_consumer("c07/doc", genesis)
    alt = nd("gen-lit", "literal", payload=art(tile))
    res_b, rec_b = attempt_and_commit(cb, t, c, mk_plan(t, c, nodes + [alt], ["root"], fallbacks={"gen": ["gen-lit"]}),
                                      {bytes(art(tile)[1]): tile}, Store(), {"diverge": ["gen"]}, "tx-c07b", "a2")
    record("C07b", "Generator diverges, prebound literal fallback", "repaired and committed",
           lambda: (f"repairs {[r['repair']['failed'] for r in res_b['repairs']]}; receipt "
                    f"{rec_b['status'] if rec_b else res_b['status']}",
                    rec_b is not None and rec_b["status"] == "committed"))


def c08_cases():
    t = mk_target("c08/doc", 2)
    r1 = b"R1-" + bytes(range(48, 112))
    want = patch(r1, edits((3, b"R2")))
    c = mk_contract(t, [digest_pred("p-doc", "doc", want)], repairs=1)
    genesis = head_for(mk_target("c08/doc", 1), c, r1)
    wrong = nd("fix", "residual", op="patch.v1", runtime=RT["patch.v1"], base=art(r1), params=edits((4, b"R2")),
               emits=["doc"])
    right = nd("fix2", "residual", op="patch.v1", runtime=RT["patch.v1"], base=art(r1), params=edits((3, b"R2")),
               emits=["doc"])
    root = nd("root", "procedural", ["fix"], op="concat.v1", runtime=RT["concat.v1"])

    def store():
        s = Store()
        s.put(r1)
        return s
    ca = new_consumer("c08/doc", genesis)
    res_a, rec_a = attempt_and_commit(ca, t, c, mk_plan(t, c, [wrong, root], ["root"]), {}, store(), {}, "tx-c08a", "a1")
    record("C08a", "Residual on the exact R1 base misses its bound", "no approval; R1 stays the head",
           lambda: (f"status {res_a['status']} ({res_a['reason']}); head still R1: {same(ca.head_id(), oid(genesis))}; "
                    f"journal {journal_counts(ca)}",
                    res_a["status"] == "aborted" and rec_a is None and same(ca.head_id(), oid(genesis))
                    and journal_counts(ca) == {"genesis": 1}))
    res_b, rec_b = attempt_and_commit(ca, t, c, mk_plan(t, c, [wrong, right, root], ["root"],
                                                         fallbacks={"fix": ["fix2"]}), {}, store(), {}, "tx-c08b", "a2")
    record("C08b", "Well-formed residual against the same baseline", "accepted; the baseline isn't blacklisted",
           lambda: (f"receipt {rec_b['status'] if rec_b else res_b['status']}",
                    rec_b is not None and rec_b["status"] == "committed"))


def c10_cases():
    t = mk_target("c10/doc", 1)
    a, cbytes = b"A" * 40, b"c" * 30
    b = patch(cbytes, edits((0, b"B")))
    x = {"id": "x-len", "kind": "invariant", "covers": ["a", "b"], "threshold": 70, "validator": "xbranch.len-sum.v1"}
    c = mk_contract(t, [digest_pred("p-a", "a", a), x, digest_pred("p-b", "b", b)], repairs=1)
    genesis = head_for(mk_target("c10/doc", 0), c, b"")
    nodes = [nd("a", "procedural", op="gen.repeat.v1", runtime=RT["gen.repeat.v1"],
                params=encode({"pattern": b"A", "n": 40}), emits=["a"]),
             nd("c", "procedural", op="gen.repeat.v1", runtime=RT["gen.repeat.v1"],
                params=encode({"pattern": b"c", "n": 30})),
             nd("b", "procedural", ["c"], op="patch.v1", runtime=RT["patch.v1"], params=edits((0, b"B")), emits=["b"]),
             nd("root", "procedural", ["a", "b"], op="concat.v1", runtime=RT["concat.v1"])]
    good_alt = nd("c-lit", "literal", payload=art(cbytes))
    ca = new_consumer("c10/doc", genesis)
    res, rec = attempt_and_commit(ca, t, c, mk_plan(t, c, nodes + [good_alt], ["root"], fallbacks={"c": ["c-lit"]}),
                                  {bytes(art(cbytes)[1]): cbytes}, Store(), {"diverge": ["c"]}, "tx-c10a", "a1")
    rep = res["repairs"][0]["repair"] if res["repairs"] else {}
    ev = res["engine"].evals
    final_x = res["evidence"]["x-len"]["inputs"]
    record("C10a", "Branch c fails late; a is independent; cross-branch x reads a and b",
           "cone excludes a; a's evidence reused; x re-run on the new b",
           lambda: (f"REPAIR failed={rep.get('failed')} affected={rep.get('affected')}; evaluations "
                    f"p-a={ev.get('p-a')} x-len={ev.get('x-len')} p-b={ev.get('p-b')}; final x covers new b: "
                    f"{same(final_x, H(encode([art(a), art(b)])))}; receipt "
                    f"{rec['status'] if rec else res['status']}",
                    rep.get("failed") == "c" and rep.get("affected") == ["b", "c", "root"] and ev.get("p-a") == 1
                    and ev.get("x-len") == 2 and ev.get("p-b") == 2 and rec is not None
                    and rec["status"] == "committed"))
    # x passed on the divergent b in the first pass; that evidence must not be what was cited
    stale_inputs = H(encode([art(a), art(patch(cbytes[:-1] + b"!", edits((0, b"B"))))]))
    first_x = next(e for e in res["audit"] if e["event"] == "evidence" and e["predicate"] == "x-len")
    record("C10b", "Cross-branch x passed on the divergent b before repair", "stale x evidence not reused",
           lambda: (f"first x pass={first_x['pass']} on the divergent b: {same(first_x['inputs'], stale_inputs)}; "
                    f"final x on the repaired b: {same(final_x, H(encode([art(a), art(b)])))}",
                    first_x["pass"] and same(first_x["inputs"], stale_inputs)
                    and same(final_x, H(encode([art(a), art(b)])))))
    bad_alt = nd("c-lit", "literal", payload=art(cbytes[:-1] + b"x"))
    cb = new_consumer("c10/doc", genesis)
    res2, rec2 = attempt_and_commit(cb, t, c, mk_plan(t, c, nodes + [bad_alt], ["root"], fallbacks={"c": ["c-lit"]}),
                                    {bytes(art(cbytes[:-1] + b"x")[1]): cbytes[:-1] + b"x"}, Store(),
                                    {"diverge": ["c"]}, "tx-c10c", "a2")
    record("C10c", "Repair cannot restore the cone", "abort; a's staged output never committed",
           lambda: (f"status {res2['status']}; journal {journal_counts(cb)}; head unchanged "
                    f"{same(cb.head_id(), oid(genesis))}",
                    res2["status"] == "aborted" and rec2 is None and journal_counts(cb) == {"genesis": 1}
                    and same(cb.head_id(), oid(genesis))))


# =====================================================================
# C21: real crashes
# =====================================================================
def c21_cases():
    t2, t3 = mk_target("c21/doc", 2), mk_target("c21/doc", 3)
    rev2, rev3 = b"scene rev 2", b"scene rev 3"
    c = mk_contract(t3, [digest_pred("p-doc", "doc", rev3)])
    genesis = head_for(t2, c, rev2)
    plan = mk_plan(t3, c, [nd("doc", "literal", payload=art(rev3), emits=["doc"])], ["doc"])
    bh = envelope_hash(mk_binding(t3, c))
    ev = {"kind": "evidence", "contract": oid(c), "scope": oid(mk_scope(t3)), "output": art(rev3),
          "predicate": "p-doc", "pass": True, "validator": "canon.digest.v1", "checker": WS, "at": NOW}
    appr = sign1(WSKEY, WS, approval_obj(bh, t3, c, plan, rev3, [oid(ev)], "tx-c21-990", oid(genesis)))
    new_head = {"kind": "head", "object": "c21/doc", "target": oid(t3), "contract": oid(c),
                "scope": oid(mk_scope(t3)), "output": art(rev3)}
    spec = {"party": WS, "object": "c21/doc", "artifact": rev3, "approval": appr}

    def run(crash_at, before_recover=None):
        root = Path(tempfile.mkdtemp(prefix="arfp-c21-"))
        atexit.register(shutil.rmtree, root, True)
        DurableConsumer(root, WS, "c21/doc").seed(genesis)
        (root / "input.cbor").write_bytes(encode(spec))
        p = subprocess.run([sys.executable, "-m", "arfpkit.journal", str(root), crash_at, str(root / "input.cbor")],
                           cwd=KIT, capture_output=True)
        if before_recover:
            before_recover(root)
        c2 = DurableConsumer(root, WS, "c21/doc")
        pre = c2.state
        try:
            c2.admit(0)
            during = "admitted"
        except Reject as r:
            during = r.code
        actions = c2.recover()
        return p.returncode, c2, actions, pre, during

    rc0, ctrl, _, _, _ = run("none")
    r_ctrl = encode(ctrl.receipts["tx-c21-990"])

    def same_receipt(c2):
        return encode(c2.receipts["tx-c21-990"]) == r_ctrl

    rc, ca, acts, pre, during = run("after-approval")
    rec = decode_receipt(ca.receipts["tx-c21-990"])
    record("C21-A", "Killed after the approval is journaled, before the head swap",
           "recovery applies the swap; receipt identical to an uncrashed run",
           lambda: (f"{died(rc)}; recovery {acts}; head is rev 3: {same(ca.head_id(), oid(new_head))}; receipt "
                    f"{rec['status']}, byte-identical to control: {same_receipt(ca)}; journal {journal_counts(ca)}",
                    rc == KILLED and same(ca.head_id(), oid(new_head)) and rec["status"] == "committed"
                    and same_receipt(ca) and journal_counts(ca) == {"genesis": 1, "approval": 1, "head": 1,
                                                                      "receipt": 1}))
    before = journal_counts(ca)
    again = ca.commit(appr, WSKEY.public_key())
    record("C21-C", "Retry with the same transaction after recovery", "same receipt; no new journal entries",
           lambda: (f"byte-identical: {encode(again) == r_ctrl}; journal before {before} after {journal_counts(ca)}",
                    encode(again) == r_ctrl and journal_counts(ca) == before))
    record("C21-E", "Offer arriving while the receiver is recovering", "refused until recovery ends; then stale",
           lambda: (lambda late: (f"state {pre}: {during}; after recovery, a plan built on snapshot 0: {late[0]}",
                                  pre == "recovering" and during == "stale-state" and late[1]))(
               expect_reject("stale-state", lambda: ca.admit(0))))
    rc, ct, acts_t, _, _ = run("torn-head")
    record("C21-T", "Killed halfway through writing the head record", "torn tail dropped; same outcome as C21-A",
           lambda: (f"{died(rc)}; recovery {acts_t}; receipt byte-identical: {same_receipt(ct)}",
                    rc == KILLED and acts_t[0] == "truncated-torn-tail" and same_receipt(ct)
                    and same(ct.head_id(), oid(new_head))))
    rc, ch, acts_h, _, _ = run("after-head")
    record("C21-H", "Killed after the head swap, before the receipt is durable", "receipt rebuilt from the journal",
           lambda: (f"{died(rc)}; recovery {acts_h}; byte-identical: {same_receipt(ch)}",
                    rc == KILLED and acts_h == [("receipt-from-commit", "tx-c21-990")] and same_receipt(ch)))
    rc, cr, acts_r, _, _ = run("after-receipt")
    record("C21-R", "Killed after the receipt is durable", "nothing to redo; retry returns the stored receipt",
           lambda: (f"{died(rc)}; recovery actions {acts_r}; retry byte-identical: "
                    f"{encode(cr.commit(appr, WSKEY.public_key())) == r_ctrl}",
                    rc == KILLED and acts_r == [] and encode(cr.commit(appr, WSKEY.public_key())) == r_ctrl))
    concurrent = {"kind": "head", "object": "c21/doc", "target": oid(t3), "contract": oid(c),
                  "scope": oid(mk_scope(t3)), "output": art(b"concurrent rev")}

    def inject(root):
        Journal(root / "journal.bin").append({"rec": "head", "txn": "tx-concurrent-9", "head": concurrent,
                                              "prior": oid(genesis)})
    rc, cbx, acts_b, _, _ = run("after-approval", inject)
    rb = decode_receipt(cbx.receipts["tx-c21-990"])
    staged = (cbx.staging / bytes(art(rev3)[1]).hex()).exists()
    record("C21-B", "Another commit moved the head before recovery", "conflict; moved head untouched; output kept",
           lambda: (f"receipt {rb['status']}, head {rb['head']}, prior-head is the moved head: "
                    f"{same(rb['prior-head'], oid(concurrent))}; head still concurrent: "
                    f"{same(cbx.head_id(), oid(concurrent))}; staged output kept: {staged}",
                    rb["status"] == "conflict" and rb["head"] is None and same(cbx.head_id(), oid(concurrent))
                    and staged))

    def corrupt(root):
        (root / "staging" / bytes(art(rev3)[1]).hex()).write_bytes(b"scene rev 3?")
    rc, cdx, _, _, _ = run("after-approval", corrupt)
    rd = decode_receipt(cdx.receipts["tx-c21-990"])
    record("C21-D", "Staged output corrupted while the receiver was down", "aborted; never commit other bytes",
           lambda: (f"receipt {rd['status']}; head unchanged: {same(cdx.head_id(), oid(genesis))}",
                    rd["status"] == "aborted" and same(cdx.head_id(), oid(genesis))))

    def sweep(c2):
        recs, _, _ = c2.journal.scan()
        approvals = set()
        per_txn = {}
        ok = True
        for r in recs:
            if r["rec"] == "approval":
                approvals.add(r["txn"])
            if r["rec"] == "head" and r["txn"] != "tx-concurrent-9" and r["txn"] not in approvals:
                ok = False
            if r["rec"] == "receipt":
                per_txn[r["txn"]] = per_txn.get(r["txn"], 0) + 1
        return ok and all(v == 1 for v in per_txn.values())
    journals = [ctrl, ca, ct, ch, cr, cbx, cdx]
    record("C21-I", "Invariants across all seven journals", "every head swap follows a durable approval; one receipt per txn",
           lambda: (f"{sum(sweep(j) for j in journals)}/{len(journals)} journals clean",
                    all(sweep(j) for j in journals)))
    for j in journals:
        shutil.rmtree(j.root, ignore_errors=True)


# =====================================================================
# C27: multi-hop provenance
# =====================================================================
def c27_cases():
    t = mk_target("c27/doc", 1)
    out = b"c27 delivered output"
    c = mk_contract(t, [digest_pred("p1", "doc", out)])
    scope = mk_scope(t)
    genesis = head_for(mk_target("c27/doc", 0), c, b"")
    binding = mk_binding(t, c)
    e1 = {"kind": "evidence", "contract": oid(c), "scope": oid(scope), "output": art(out), "predicate": "p1",
          "pass": True, "reference": art(out), "validator": "canon.digest.v1", "checker": PUB, "at": NOW}
    e1_env = sign1(PUBKEY, BINDING_KID, e1)

    def deleg(rights):
        return sign1(PUBKEY, BINDING_KID, {"kind": "delegation", "issuer": PUB, "grantee": R2, "target": oid(t),
                                            "contract": oid(c), "scope": oid(scope), "rights": rights,
                                            "recipients": [WS], "expires": NOW + 600000, "subdelegate": False,
                                            "budget": {"cpu": 1000}})
    d_ok = deleg(["cache", "forward", "attest"])
    d_noattest = deleg(["cache", "forward"])

    def attest(ev_env, d_env):
        return sign1(R2KEY, R2, {"kind": "attestation", "evidence": envelope_hash(ev_env), "attester": R2,
                                 "delegation": oid(payload_obj(d_env)), "meaning": "signature-verified", "at": NOW})

    def deliver(bundle, output=out, binding_env=binding, rewrite=None):
        """Receiver side: check provenance, then commit. Returns (chain, receipt, consumer, store)."""
        cons = new_consumer("c27/doc", genesis)
        chain = check_bundle(t, c, binding_env, TRUST, output, bundle, NOW, rewrite=rewrite, relay=R2)
        store = {bytes(envelope_hash(e)[1]): e for e in bundle}
        store.update({bytes(oid(payload_obj(e))[1]): e for e in bundle
                      if payload_obj(e).get("kind") == "delegation"})
        store[bytes(envelope_hash(binding_env)[1])] = binding_env
        cited = chain["attestations"] + chain["evidence"]
        appr = approval_obj(chain["binding"], t, c, mk_plan(t, c, [nd("doc", "literal", payload=art(output),
                                                                         emits=["doc"])], ["doc"]),
                            output, cited, "tx-c27", cons.head_id(), relayed=chain["delegations"])
        cons.stage(output)
        appr_env = sign1(WSKEY, WS, appr)
        rec_env = cons.commit(appr_env, WSKEY.public_key())
        return chain, rec_env, appr_env, cons, store

    def oracle_ok(result):
        chain, rec_env, appr_env, cons, store = result
        rebuilt = reconstruct(rec_env, CONSUMER_TRUST, appr_env, store, TRUST, t, c, NOW)
        triple = [chain["binding"]] + chain["delegations"][:1] + (chain["attestations"] or chain["evidence"])[:1]
        cited = payload_obj(appr_env)["evidence"]
        audit_used = chain["attestations"] + chain["evidence"]
        consistent = len(cited) == len(audit_used) and all(same(x, y) for x, y in zip(cited, audit_used))
        return (decode_receipt(rec_env)["status"] == "committed" and len(cons.receipts) == 1
                and len(triple) == 3 and len(rebuilt) >= 3 and same(rebuilt[1], chain["delegations"][0])
                and consistent), rebuilt, triple

    def positive(cid, title, bundle):
        res = deliver(bundle)
        ok, rebuilt, triple = oracle_ok(res)
        record(cid, title, "commit; receipt chain rebuilds from the receipt alone",
               lambda: (f"receipt committed; audit triple {[short(x) for x in triple]}; chain rebuilt from the "
                        f"receipt: {len(rebuilt)} links, relay delegation verified; approval cites exactly the audited "
                        f"evidence", ok))

    positive("C27a", "Repeater forwards the origin's signed evidence unchanged", [e1_env, d_ok])
    positive("C27b", "Repeater adds a signed attestation naming the origin evidence", [e1_env, attest(e1_env, d_ok), d_ok])

    def negative(cid, title, code, **kw):
        bundle = kw.pop("bundle")
        record(cid, title, f"reject {code}; no receipt",
               lambda: expect_reject(code, lambda: deliver(bundle, **kw)))

    forged = sign1(R2KEY, R2, dict(e1, checker=R2))
    negative("C27c", "Repeater re-signs the evidence as its own, origin copy dropped", "validation-failure",
             bundle=[forged, attest(forged, d_ok), d_ok])
    tampered = Tag(18, [e1_env.value[0], {}, encode(dict(e1, output=art(b"other"))), e1_env.value[3]])
    negative("C27d", "Repeater edits the evidence and keeps the origin signature", "integrity-failure",
             bundle=[tampered, d_ok])
    negative("C27e", "Attestation names origin evidence that was not delivered", "validation-failure",
             bundle=[attest(e1_env, d_ok), d_ok])
    negative("C27f", "Required predicate's evidence dropped entirely", "validation-failure", bundle=[d_ok])
    negative("C27g", "Repeater attests without the attest right", "permission-denied",
             bundle=[e1_env, attest(e1_env, d_noattest), d_noattest])
    negative("C27h", "Repeater substitutes the payload bytes", "validation-failure",
             bundle=[e1_env, d_ok], output=b"c27 substituted output")
    rw = {"kind": "rewrite", "from": art(b"plan-a"), "to": art(b"plan-b"), "repeater": R2,
          "delegation": oid(payload_obj(d_ok)), "changed": ["doc"], "reused": [], "pending": ["doc"]}
    negative("C27i", "Repeater rewrites the plan without the rewrite right", "permission-denied",
             bundle=[e1_env, d_ok], rewrite=(R2, rw, sign1(R2KEY, R2, rw)))
    bad_binding = Tag(18, list(binding.value))
    s = bytearray(bad_binding.value[3]); s[5] ^= 0x40; bad_binding.value[3] = bytes(s)
    negative("C27j", "Forged origin binding, valid repeater signatures", "integrity-failure",
             bundle=[e1_env, attest(e1_env, d_ok), d_ok], binding_env=bad_binding)


def run(main_target, main_contract, main_scope, main_plan, main_eligibility, published_envelope_hex):
    rows.clear()
    good = gate_cases(main_target, main_contract, main_scope, main_plan, main_eligibility, published_envelope_hex)
    c04_cases()
    c07_cases()
    c08_cases()
    c10_cases()
    c21_cases()
    c27_cases()
    return list(rows), good
