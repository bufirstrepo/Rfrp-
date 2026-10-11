"""Semantic rules the CDDL cannot express.

Each check raises Reject(code, detail) using the schema's error-code vocabulary.
"""
from .canon import H, encode, num_value, is_normalized_num, oid, same

DET_RANK = {"E": 0, "T": 1, "N": 2}  # higher = weaker reproducibility


class Reject(Exception):
    def __init__(self, code, detail):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


def weakest(*classes):
    return max(classes, key=DET_RANK.get) if classes else "E"


# ---------- graph ----------

def check_dag(plan):
    ids = [n["id"] for n in plan["nodes"]]
    if len(set(ids)) != len(ids):
        raise Reject("ineligible-plan", "duplicate node id")
    known = set(ids)
    for n in plan["nodes"]:
        for d in n["deps"]:
            if d not in known:
                raise Reject("missing-dependency", f"{n['id']} depends on undeclared node {d}")
    for r in plan["roots"]:
        if r not in known:
            raise Reject("ineligible-plan", f"root {r} is not a node")
    indeg = {i: 0 for i in ids}
    children = {i: [] for i in ids}
    for n in plan["nodes"]:
        for d in n["deps"]:
            indeg[n["id"]] += 1
            children[d].append(n["id"])
    ready = [i for i in ids if indeg[i] == 0]
    order = []
    while ready:
        i = ready.pop(0)
        order.append(i)
        for c in children[i]:
            indeg[c] -= 1
            if indeg[c] == 0:
                ready.append(c)
    if len(order) != len(ids):
        raise Reject("ineligible-plan", "dependency cycle")
    return order


def work_keys(plan):
    """wk(v) = H(["arfp/0","work", class, op, runtime, params, payload, artifact, base, [wk(dep)]])."""
    nodes = {n["id"]: n for n in plan["nodes"]}
    keys = {}
    for nid in check_dag(plan):
        n = nodes[nid]
        keys[nid] = H(encode(["arfp/0", "work", n["class"], n.get("op"), n.get("runtime"),
                              n.get("params"), n.get("payload"), n.get("artifact"), n.get("base"),
                              [keys[d] for d in n["deps"]]]))
    return keys


# ---------- contract lint ----------

def predicates(contract):
    return contract["acceptance"] + contract.get("invariants", [])


def reference_bound(p):
    return "reference" in p or "expected" in p


def covering(contract, region):
    return [p for p in predicates(contract)
            if p.get("covers") == "all" or (isinstance(p.get("covers"), list) and region in p["covers"])]


def lint_contract(contract):
    free = set(contract.get("free", []))
    for p in predicates(contract):
        if "threshold" in p and not is_normalized_num(p["threshold"]):
            raise Reject("invalid-contract", f"{p['id']}: threshold is not a normalized exact number")
        if p["kind"] == "metric-bound" and not all(k in p for k in ("metric", "threshold", "units")):
            raise Reject("invalid-contract", f"{p['id']}: a metric bound needs metric, threshold and units")
        if p.get("composition") == "additive" and p["kind"] != "metric-bound":
            raise Reject("invalid-contract", f"{p['id']}: additive composition applies only to metric bounds")
        if reference_bound(p) and isinstance(p.get("covers"), list) and free & set(p["covers"]):
            raise Reject("invalid-contract", f"{p['id']}: a free region cannot also be reference-bound")


# ---------- eligibility ----------

def runtime_of(node, runtimes):
    rt = runtimes.get(bytes(node["runtime"][1])) if "runtime" in node else None
    if rt is None:
        raise Reject("unsupported-op", f"{node['id']}: runtime not available to this executor")
    return rt


def is_local(node, receiver):
    return node.get("at", "receiver") in ("receiver", receiver)


def path_det(node, nodes, runtimes, receiver):
    """Reproducibility of a node's output as the receiver will hold it.

    Upstream execution delivers hash-verified bytes, so the receiver's copy is exact ("E")
    regardless of the runtime used upstream: placement converts determinism.
    """
    if not is_local(node, receiver):
        return "E"
    own = "E" if node["class"] in ("reference", "literal") else runtime_of(node, runtimes)["det"]
    return weakest(own, *(path_det(nodes[d], nodes, runtimes, receiver) for d in node["deps"]))


def receiver_checkable(p, receiver_refs):
    if not reference_bound(p):
        return True                                # self-check on the actual output
    if p.get("mode") in ("digest-match", "feature-digest") and "expected" in p:
        return True                                # compare actual output to an authenticated expectation
    return "reference" in p and bytes(p["reference"][1]) in receiver_refs


def bound_transfers(node, p, nodes, runtimes, receiver):
    """T-class evidence transfers only for an additive true-metric bound, one T step deep."""
    if p["kind"] != "metric-bound" or p.get("composition") != "additive":
        return False
    rt = runtime_of(node, runtimes)
    if rt["det"] != "T" or rt["bound"]["metric"] != p["metric"] or rt["bound"]["units"] != p["units"]:
        return False
    return all(path_det(nodes[d], nodes, runtimes, receiver) == "E" for d in node["deps"])


def has_right(delegations, party, right):
    return any(g["grantee"] == party and right in g["rights"] for g in delegations)


def check_eligible(plan, contract, caps, runtimes, receiver, snapshot, base_det,
                   receiver_refs=frozenset(), delegations=()):
    """Plan admission. Eligibility authorizes an attempt, never a commit."""
    if not same(plan["contract"], oid(contract)):
        raise Reject("ineligible-plan", "plan is bound to a different contract")
    if not same(plan["target"], contract["target"]):
        raise Reject("ineligible-plan", "plan and contract name different targets")
    if plan["snapshot"] != snapshot:
        raise Reject("stale-state", f"plan assumes snapshot {plan['snapshot']}; receiver is at {snapshot}")
    if contract["profile"] not in caps["profiles"]:
        raise Reject("unsupported-profile", contract["profile"])
    lint_contract(contract)
    check_dag(plan)
    nodes = {n["id"]: n for n in plan["nodes"]}
    free = set(contract.get("free", []))
    transfer = set(contract["determinism"]["evidence-transfer"])
    base_ok = set(contract["determinism"]["baseline-eligible"])
    checkers = set(contract["evidence"].get("checkers", [])) | {contract["authority"]["publisher"]}
    publisher = contract["authority"]["publisher"]

    for n in plan["nodes"]:
        nid, cls, at = n["id"], n["class"], n.get("at", "receiver")
        if cls not in contract["classes"]:
            raise Reject("ineligible-plan", f"{nid}: the contract does not permit {cls} nodes")
        local = is_local(n, receiver)
        if local and cls not in caps["classes"]:
            raise Reject("unsupported-op", f"{nid}: the receiver cannot execute {cls} nodes")
        if not local and cls not in ("reference", "literal") and at != publisher \
                and not has_right(delegations, at, "execute"):
            raise Reject("permission-denied", f"{nid}: {at} holds no execute right")
        if cls in ("delta", "residual"):
            if "base" not in n:
                raise Reject("baseline-mismatch", f"{nid}: no exact base identity")
            bdet = base_det.get(bytes(n["base"][1]))
            if bdet not in base_ok:
                raise Reject("baseline-mismatch",
                             f"{nid}: base is {bdet or 'unknown'}-class; contract allows {sorted(base_ok)}")
        det = path_det(n, nodes, runtimes, receiver)
        own = "E" if cls in ("reference", "literal") or not local else runtime_of(n, runtimes)["det"]
        if own != "E" and not n.get("emits"):
            dependents = [m for m in plan["nodes"] if nid in m["deps"]]
            if not dependents or any(not m.get("emits") for m in dependents):
                raise Reject("ineligible-plan",
                             f"{nid}: {own}-class output reaches the result without a declared region")
        for region in n.get("emits", []):
            if region in free:
                continue
            preds = covering(contract, region)
            if det != "E" and not any(reference_bound(p) for p in preds):
                raise Reject("ineligible-plan",
                             f"{nid}: {det}-class output in '{region}' is neither labeled free nor reference-bound")
            for p in preds:
                if receiver_checkable(p, receiver_refs):
                    continue
                if not local:
                    if at not in checkers and not has_right(delegations, at, "check"):
                        raise Reject("ineligible-plan", f"{nid}: {p['id']} needs a checker; {at} is not one")
                    continue                                  # evidence on the exact bytes delivered
                if det == "E" and "E" in transfer:
                    continue                                  # transfer by identity
                if det == "T" and "T" in transfer and bound_transfers(n, p, nodes, runtimes, receiver):
                    continue                                  # transfer by bound
                raise Reject("ineligible-plan",
                             f"{nid}: {p['id']} cannot be checked at the receiver and {det}-class evidence does not transfer")
    return True


# ---------- acceptance ----------

def check_transfer_binding(sender_evidence, receiver_work_key):
    """Sender evidence covers the receiver's output only if it measured the same work:
    same runtime, payload, params and inputs, i.e. an identical work key."""
    if not same(sender_evidence.get("work"), receiver_work_key):
        raise Reject("validation-failure", "sender evidence was measured on different work; it cannot transfer")
    return True


def bound_from_sender(p, sender_evidence, runtime):
    """d(y_r, x) <= d(y_r, y_s) + d(y_s, x) <= delta + eps_s, valid for a true metric."""
    total = num_value(runtime["bound"]["value"]) + num_value(sender_evidence["measured"])
    return total <= num_value(p["threshold"]), total


def composed_bound(p, chain, reference, final_output):
    """Multi-hop check. Additive: hops must link reference -> ... -> final and their sum must fit.
    End-to-end: one record measured directly against the designated reference."""
    thr = num_value(p["threshold"])
    if p.get("composition") == "additive":
        expected_input = reference
        total = 0
        for ev in chain:
            if not same(ev["reference"], expected_input):
                raise Reject("validation-failure", "hop evidence does not chain from the previous output")
            if not ev["pass"]:
                raise Reject("validation-failure", "a hop failed its own check")
            total += num_value(ev["measured"] if "measured" in ev else ev["bound"])
            expected_input = ev["output"]
        if not same(expected_input, final_output):
            raise Reject("validation-failure", "chain does not end at the output being accepted")
        return total <= thr, total
    direct = [ev for ev in chain if same(ev["reference"], reference) and same(ev["output"], final_output)]
    if not direct:
        raise Reject("validation-failure", "end-to-end composition needs evidence against the designated reference")
    return all(num_value(ev["measured"]) <= thr for ev in direct), max(num_value(ev["measured"]) for ev in direct)


def evidence_applies(ev, contract, scope, output, now):
    """Content reuse is not evidence reuse: evidence binds a contract, a scope and an output."""
    max_age = contract["evidence"].get("max-age")
    return (same(ev["contract"], oid(contract)) and same(ev["scope"], oid(scope))
            and same(ev["output"], output) and (max_age is None or now - ev["at"] <= max_age))


# ---------- scope and milestone use ----------

def may_use(contract, scope, use, full_uses):
    if "milestone" in scope:
        m = next(m for m in contract.get("milestones", []) if m["name"] == scope["milestone"])
        return use in m["uses"]
    if scope["select"] == "all":
        return use in full_uses
    return False   # a scoped result never authorizes a full-target use


# ---------- delegation ----------

def scope_within(child_scope, parent_scope):
    if parent_scope["select"] == "all":
        return True
    return child_scope["select"] != "all" and set(child_scope["select"]) <= set(parent_scope["select"])


def check_children(parent, children, scopes):
    """Children narrow the parent; their budgets partition it."""
    if children and not parent["subdelegate"]:
        raise Reject("permission-denied", "the parent grant forbids subdelegation")
    pid = oid(parent)
    for c in children:
        if not same(c.get("parent"), pid):
            raise Reject("permission-denied", "child does not name this parent")
        if c["issuer"] != parent["grantee"]:
            raise Reject("permission-denied", "only the parent's grantee may issue a child grant")
        if not (same(c["target"], parent["target"]) and same(c["contract"], parent["contract"])):
            raise Reject("permission-denied", "child changes the target or contract")
        extra = set(c["rights"]) - set(parent["rights"])
        if extra:
            raise Reject("permission-denied", f"child adds rights {sorted(extra)}")
        extra = set(c["recipients"]) - set(parent["recipients"])
        if extra:
            raise Reject("permission-denied", f"child adds recipients {sorted(extra)}")
        if c["expires"] > parent["expires"]:
            raise Reject("permission-denied", "child outlives its parent")
        if not scope_within(scopes[bytes(c["scope"][1])], scopes[bytes(parent["scope"][1])]):
            raise Reject("permission-denied", "child widens the scope")
        missing = set(parent["budget"]) - set(c["budget"])
        if missing:
            raise Reject("resource-limit", f"child leaves {sorted(missing)} unbounded")
    for k, cap in parent["budget"].items():
        total = sum(c["budget"].get(k, 0) for c in children)
        if total > cap:
            raise Reject("resource-limit", f"children allocate {total} {k} of a parent budget of {cap}")
    return True


# ---------- supersession ----------

def closure(roots, deps):
    seen, stack = set(), list(roots)
    while stack:
        w = stack.pop()
        if w not in seen:
            seen.add(w)
            stack.extend(deps.get(w, ()))
    return seen


def cancel_candidates(demands_before, demands_after, deps, unfinished, retained=()):
    """W_cancel = [L(D) - L(D')] & unfinished; retention obligations count as roots."""
    before = closure(set().union(*demands_before.values()) | set(retained), deps)
    after = closure(set().union(*demands_after.values()) | set(retained), deps)
    return (before - after) & set(unfinished)


# ---------- fast path ----------

def plan_shape(plan):
    return (tuple((n["id"], n["class"], n.get("op"), bytes(n["runtime"][1]) if "runtime" in n else None,
                   tuple(n["deps"]), tuple(n.get("emits", ())), n.get("at", "receiver"))
                  for n in plan["nodes"]), tuple(plan["roots"]))


def check_fast_path(prev_plan, new_plan, contract, stream, snapshot):
    rule = next((r for r in contract["updates"] if r["stream"] == stream), None)
    if rule is None or rule.get("fast-path") != "shape-equal":
        raise Reject("ineligible-plan", f"stream {stream} has no fast path; full OFFER/ACCEPT required")
    if not same(new_plan.get("parent"), oid(prev_plan)):
        raise Reject("ineligible-plan", "fast-path plan does not name the accepted plan as parent")
    if plan_shape(prev_plan) != plan_shape(new_plan):
        raise Reject("ineligible-plan", "plan shape changed; full OFFER/ACCEPT required")
    if new_plan["snapshot"] != snapshot:
        raise Reject("stale-state", f"fast-path plan assumes snapshot {new_plan['snapshot']}; receiver is at {snapshot}")
    return True


# ---------- forwarding ----------

def dedup_key(msg):
    return bytes(H(encode({k: v for k, v in msg.items() if k not in ("ttl", "via")}))[1])


class Forwarder:
    def __init__(self, party):
        self.party, self.seen = party, set()

    def handle(self, msg):
        key = dedup_key(msg)
        if key in self.seen:
            return None, "drop-duplicate"
        self.seen.add(key)
        if self.party in msg.get("via", []):
            return None, "drop-loop"
        if msg.get("ttl", 0) == 0:
            return None, "drop-ttl"
        return dict(msg, ttl=msg["ttl"] - 1, via=msg.get("via", []) + [self.party]), "forward"
