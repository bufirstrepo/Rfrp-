"""Rules for the speed mechanisms in docs/proposals/ARFP-speed-mechanisms.md.

1. Fidelity chosen per receiver: a DEMAND may carry the receiver's own acceptance. Bounds set fidelity
   (how close to the publisher's reference the output must be); classes set reproducibility of the
   receiver's copy (E, T, N, as everywhere in ARFP); `free` says whether generated content in the
   contract's free regions is acceptable. A receiver may tighten the contract's metric bounds, never
   loosen them; other predicates (an invariant such as a minimum clearance) have no direction to tighten.
2. Speculative start: output drafted on provisional (coarse) state commits as exact only with a
   speculation record that checking against the exact state reproduces. Using provisional output
   without that check is an explicit opt-in, allowed only within a bound the contract accepts.
5. Proof-based evidence: a compact proof bound to the runtime, input and output lets a verifier check
   with one recomputation pass instead of re-running the work; the usual evidence rules still apply.
6. Push on a standing subscription: a new revision arrives without OFFER/ACCEPT, but its binding
   passes gate zero, its plan is a same-shape child of the subscribed plan that is eligible under the
   revision's contract and the subscriber's own acceptance, the receiver must hold the base, and the
   pushed bytes must match the plan. A miss falls back to repair.

Ideas 3 (compute once, fan out) and 4 (cancel superseded work) use mechanisms the kit already checks:
shared work keys (C15), supersession and cancellation (C16-C18), and signed multi-hop evidence (C27).
"""
import hashlib

from .canon import art, decode, encode, num_value, oid, same
from .gate import open_signed
from .rules import Reject, check_fast_path, covering, evidence_applies, path_det, predicates

# ---------------------------------------------------------------- 1. fidelity chosen per receiver

def metric_bound(contract, pid):
    """Only a metric-bound predicate has a direction: its threshold is an upper limit on a distance from
    the reference, so a smaller number is stricter. Nothing else can be tightened by a receiver."""
    p = next((p for p in predicates(contract) if p["id"] == pid), None)
    if p is None or p["kind"] != "metric-bound" or "threshold" not in p:
        raise Reject("permission-denied", f"{pid} is not a metric bound in this contract; a receiver can "
                                          "tighten only metric bounds")
    return p


def check_demand_accept(demand, contract):
    """A receiver's acceptance may only narrow the contract."""
    acc = demand.get("accept")
    if acc is None:
        return None
    for pid, bound in acc.get("bounds", {}).items():
        if num_value(bound) > num_value(metric_bound(contract, pid)["threshold"]):
            raise Reject("permission-denied",
                         f"{pid}: a demand may tighten the contract's bound, not loosen it")
    return acc


def effective_threshold(contract, demand, pid):
    """The bound that applies to this receiver: the contract's, or the receiver's own if tighter."""
    t = num_value(metric_bound(contract, pid)["threshold"])
    bounds = ((demand or {}).get("accept") or {}).get("bounds", {})
    return min(t, num_value(bounds[pid])) if pid in bounds else t


def declared_error(node, p):
    """Planning estimate of a node's distance from p's designated reference: zero when the node carries
    the reference itself, otherwise the node's own claim. None when the node claims nothing."""
    key = {"literal": "payload", "reference": "artifact"}.get(node["class"])
    content = node.get(key) if key else None
    if content is not None and "reference" in p and same(content, p["reference"]):
        return 0
    err = node.get("claim", {}).get("error")
    return None if err is None else num_value(err)


def check_plan_bounds(plan, contract, demand):
    """Planning: for every metric bound covering a region a node emits, the node's declared error must
    fit the bound that applies to this receiver. A node that declares nothing is ineligible where this
    receiver set its own bound, and is left to validation otherwise (as without per-receiver acceptance)."""
    bounds = ((demand or {}).get("accept") or {}).get("bounds", {})
    for n in plan["nodes"]:
        for region in n.get("emits", []):
            for p in covering(contract, region):
                if p["kind"] != "metric-bound" or "threshold" not in p:
                    continue
                err, limit = declared_error(n, p), effective_threshold(contract, demand, p["id"])
                if err is None and p["id"] not in bounds:
                    continue
                if err is None:
                    raise Reject("ineligible-plan", f"{n['id']}: declares no error for {p['id']}; this receiver "
                                                    f"requires {limit} {p.get('units', '')}")
                if err > limit:
                    raise Reject("ineligible-plan", f"{n['id']}: declared error {err} {p.get('units', '')} "
                                                    f"exceeds the bound for this receiver, {limit}")
    return True


def check_receiver_bound(contract, demand, pid, value):
    """Validation: the measured or composed bound must also fit this receiver's tighter bound."""
    limit = effective_threshold(contract, demand, pid)
    if value > limit:
        raise Reject("validation-failure", f"{pid}: {value} exceeds this receiver's bound {limit}")
    return True


def check_output_classes(plan, demand, runtimes, receiver, contract):
    """Reproducibility of the receiver's copy: every node that emits a non-free region must produce a
    class this receiver accepts. Work done upstream arrives as hash-checked bytes, so it is E for the
    receiver whatever its fidelity; fidelity is governed by bounds. Generated content in the contract's
    free regions is accepted unless the receiver sets free = false. With no `accept`, the contract
    alone decides."""
    acc = (demand or {}).get("accept")
    if not acc:
        return True
    allowed, free_ok = set(acc["classes"]), acc.get("free", True)
    free = set(contract.get("free", []))
    nodes = {n["id"]: n for n in plan["nodes"]}
    for n in plan["nodes"]:
        regions = set(n.get("emits", []))
        if not regions:
            continue
        det = path_det(n, nodes, runtimes, receiver)
        if regions <= free:
            if det != "E" and not free_ok:
                raise Reject("ineligible-plan",
                             f"{n['id']}: generated content in {sorted(regions)}; this receiver accepts none")
            continue
        if det not in allowed:
            raise Reject("ineligible-plan",
                         f"{n['id']}: {det}-class copy; this receiver accepts {sorted(allowed)}")
    return True


# ---------------------------------------------------------------- 2. speculative start

def _h(*parts):
    return hashlib.sha256(b"".join(parts)).digest()


def coarse(state):
    """What arrives first: the state with its low-order detail dropped (a stand-in for a quantized cache)."""
    return bytes(b & 0xF0 for b in state)


def toy_next(state, prompt, hist):
    """Toy generator. Most positions depend only on the coarse view of the state; about one in ten
    depends on its fine detail. Drafting on the coarse state therefore matches the exact output up
    to the first detail-dependent position."""
    i, h = len(hist), bytes(hist)
    detail = _h(b"detail", prompt, h, i.to_bytes(4, "big"))[0] % 10 == 0
    view = state if detail else coarse(state)
    return _h(b"next", view, prompt, h)[0] % 32


def toy_decode(state, prompt, n, hist=()):
    out = list(hist)
    while len(out) < n:
        out.append(toy_next(state, prompt, out))
    return out


def verify_draft(draft, exact_state, prompt):
    """Keep the drafted prefix that the exact state reproduces, take the exact token at the first
    mismatch, then continue exactly. Returns (tokens kept from the draft, final output)."""
    kept = 0
    while kept < len(draft) and toy_next(exact_state, prompt, draft[:kept]) == draft[kept]:
        kept += 1
    return kept, toy_decode(exact_state, prompt, len(draft), draft[:kept])


def check_speculation(spec, plan, provisional_state, exact_state, prompt, draft, output):
    """A speculation record is acceptable only if it names this plan and these states, and its
    claimed prefix and output are what checking the draft against the exact state produces."""
    if not same(spec["plan"], oid(plan)):
        raise Reject("integrity-failure", "speculation record is for a different plan")
    if not same(spec["provisional"], art(provisional_state)):
        raise Reject("integrity-failure", "speculation record names a different provisional state")
    if not same(spec["exact"], art(exact_state)):
        raise Reject("integrity-failure", "draft was checked against a different exact state")
    if not same(spec["drafted"], art(bytes(draft))):
        raise Reject("integrity-failure", "speculation record names a different draft")
    kept, final = verify_draft(draft, exact_state, prompt)
    if spec["accepted"] != kept:
        raise Reject("validation-failure",
                     f"record claims {spec['accepted']} verified tokens; checking against the exact state keeps {kept}")
    if not (same(spec["output"], art(bytes(final))) and same(spec["output"], art(bytes(output)))):
        raise Reject("validation-failure", "committed output is not the verified output")
    return kept


def check_provisional_commit(demand, contract, from_provisional, spec_check=None, coarse_bound=None, pid=None):
    """Commit rule for output drafted on provisional state.
    - With a passing speculation check it commits as E.
    - Without one, only a receiver that explicitly accepts T may use it, and only if the contract lets
      T-class evidence transfer and the coarse layer declares a bound within the (receiver's) bound
      for the predicate covering it. Unverified provisional use is never the default."""
    if not from_provisional:
        return "E"
    if spec_check is not None:
        spec_check()
        return "E"
    accepts = set(((demand or {}).get("accept") or {}).get("classes", []))
    if "T" not in accepts:
        raise Reject("validation-failure",
                     "output drafted on provisional state needs a check against the exact state before commit")
    if "T" not in contract["determinism"]["evidence-transfer"]:
        raise Reject("validation-failure", "the contract does not accept bounded (T-class) output by bound")
    if coarse_bound is None or pid is None or num_value(coarse_bound) > effective_threshold(contract, demand, pid):
        raise Reject("validation-failure",
                     "the provisional layer declares no bound within the contract; it cannot be used unchecked")
    return "T"


# ---------------------------------------------------------------- 5. proof-based evidence

PROOF_SCHEME = "topk-fingerprint.v0"   # toy, TOPLOC-like: top-k positions and values of hidden activations
TOPK, TOL = 8, 2


def toy_activations(runtime, inp, out, noise=0):
    """Deterministic stand-in for hidden activations of `runtime` on input and output. `noise` perturbs
    small values, as different hardware or kernel order would."""
    stream = b""
    seed = encode([runtime, inp, out])
    while len(stream) < 256:
        stream += _h(b"act", seed, len(stream).to_bytes(4, "big"))
    acts = [int.from_bytes(stream[i:i + 4], "big") % 100_000 for i in range(0, 256, 4)]
    if noise:
        acts = [a + ((_h(b"noise", seed, noise.to_bytes(4, "big"), i.to_bytes(4, "big"))[0] % 3) - 1)
                for i, a in enumerate(acts)]
    return acts


def make_proof(acts):
    top = sorted(range(len(acts)), key=lambda i: -acts[i])[:TOPK]
    return encode([sorted(top), [acts[i] for i in sorted(top)]])


def proof_matches(data, acts):
    idx, vals = decode(data)
    top = set(sorted(range(len(acts)), key=lambda i: -acts[i])[:TOPK])
    return set(idx) == top and all(abs(acts[i] - v) <= TOL for i, v in zip(idx, vals))


def check_proof_evidence(env, trust, contract, scope, runtime, inp, output, now, recompute):
    """Accept signed proof evidence with one recomputation pass instead of re-running the work.
    `recompute(runtime, inp, out)` is the verifier's parallel pass over the known input and output.
    Everything that can be rejected without computing is rejected first."""
    party, ev = open_signed(env, trust, "evidence")
    if ev.get("checker") != party:
        raise Reject("integrity-failure", "evidence names a checker other than its signer")
    if "proof" not in contract["evidence"]["modes"]:
        raise Reject("validation-failure", "the contract does not accept proof evidence")
    if not evidence_applies(ev, contract, scope, output, now):
        raise Reject("validation-failure", "evidence is for another contract, scope or output, or is too old")
    if not ev["pass"]:
        raise Reject("validation-failure", "evidence reports a failed check")
    pr = ev.get("proof")
    if pr is None or pr["scheme"] != PROOF_SCHEME:
        raise Reject("validation-failure", "no proof in a supported scheme")
    if not same(pr["runtime"], runtime):
        raise Reject("validation-failure", "proof was made with a different runtime than the plan names")
    if not same(pr["input"], inp):
        raise Reject("validation-failure", "proof is for a different input")
    if not proof_matches(pr["data"], recompute(runtime, inp, output)):
        raise Reject("validation-failure", "proof does not match one recomputation of the claimed run")
    return ev


# ---------------------------------------------------------------- 6. push on a standing subscription

def subscribe(subs, demand, plan, template_id):
    if not demand.get("subscribe"):
        raise Reject("permission-denied", "demand did not ask for a subscription")
    subs[(demand["consumer"], demand["stream"])] = {"plan": plan, "template": template_id, "seq": demand["seq"],
                                                    "accept": demand.get("accept")}


def check_push(body, consumer, subs, head_output, snapshot, gate, eligible, runtimes):
    """Apply a PUSH without OFFER/ACCEPT.
    `gate(binding_env, target)` runs gate zero and returns {"contract", "template", ...};
    `eligible(plan, contract)` runs the receiver's own eligibility check (no round trip);
    `runtimes` are the receiver's, for the reproducibility of its copy."""
    sub = subs.get((consumer, body["stream"]))
    if sub is None:
        raise Reject("permission-denied", "no standing subscription for this stream; negotiate with OFFER/ACCEPT")
    res = gate(body["binding"], body["target"])
    if not same(res["template"], sub["template"]):
        raise Reject("integrity-failure", "push binding names a template outside this subscription")
    contract = res["contract"]
    rule = next((r for r in contract["updates"] if r["stream"] == body["stream"]), None)
    if rule is None:
        raise Reject("ineligible-plan", f"this revision's contract defines no stream {body['stream']}")
    seq, last = body["seq"], sub["seq"]
    if rule["mode"] == "replaceable" and seq <= last:
        raise Reject("canceled", f"push seq {seq} is superseded; latest applied is {last}")
    if rule["mode"] == "required-transition" and seq != last + 1:
        raise Reject("missing-dependency" if seq > last + 1 else "stale-state",
                     f"push seq {seq} on a required-transition stream; expected {last + 1}")
    plan = body["plan"]
    check_fast_path(sub["plan"], plan, contract, body["stream"], snapshot)
    eligible(plan, contract)
    own = {"accept": sub["accept"]} if sub.get("accept") else None   # the subscriber's own acceptance
    check_plan_bounds(plan, contract, own)
    check_output_classes(plan, own, runtimes, consumer, contract)
    if not same(body["base"], head_output):
        raise Reject("baseline-mismatch", "push assumes a base this receiver does not hold; send REPAIR")
    payloads = {n["id"]: n.get("payload") for n in plan["nodes"]}
    for ch in body["chunks"]:
        if payloads.get(ch["node"]) is None or not same(payloads[ch["node"]], ch["digest"]) \
                or not same(art(ch["data"]), ch["digest"]):
            raise Reject("integrity-failure", f"pushed bytes for {ch['node']} do not match the plan")
    sub.update(plan=plan, seq=seq)
    return True
