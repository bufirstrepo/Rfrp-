"""Exact-profile execution engine for the Stage-1 failure cases (C04, C07, C08, C10).

Profile "bytes.exact.v1": artifacts are byte strings; every operation is integer/byte exact (E-class).
- reference   fetch content by digest from the store (it can be evicted: C04)
- literal     bytes delivered in WORKTREE_PAYLOAD, checked against their digest
- delta,      apply patch.v1 edits to an exact base (base digest must match: baseline-mismatch otherwise)
  residual
- procedural  gen.repeat.v1 (pattern * n) or patch.v1 applied to its single dependency
- root        concat.v1: canonical CBOR map {region: bytes} of the regions its dependencies emit

Checks run when a node emits a region, before anything consumes it, so a divergent output is never
used downstream as if valid (C07). Cross-branch predicates run once all their regions exist. Evidence
is reused only when every input region digest is unchanged (C10). Repair substitutes a prebound
fallback for the nearest failed-or-ancestor node that has one, invalidates that node's cone, and
re-runs; the attempt aborts when no fallback or repair budget remains. Nothing reaches the
committed store until a commit; staged outputs live only in the engine.
"""
from .canon import H, art, decode, encode, same, short
from .rules import Reject, check_dag

EXCLUDE_FROM_STAGING = ()


class Store:
    """Content-addressed committed store."""

    def __init__(self):
        self.blobs = {}

    def put(self, data):
        d = art(data)
        self.blobs[bytes(d[1])] = data
        return d

    def get(self, d):
        b = self.blobs.get(bytes(d[1]))
        if b is None:
            raise Reject("missing-dependency", f"artifact {short(d)} is not available")
        return b

    def has(self, d):
        return bytes(d[1]) in self.blobs

    def evict(self, d):
        self.blobs.pop(bytes(d[1]), None)


def patch(base, params):
    out = bytearray(base)
    for off, rep in decode(params):
        out[off:off + len(rep)] = rep
    return bytes(out)


def repeat(params):
    p = decode(params)
    return p["pattern"] * p["n"]


class Engine:
    def __init__(self, store, runtimes, faults=None):
        self.store, self.runtimes = store, runtimes          # runtime digest bytes -> op name
        self.faults = dict(faults or {})
        self.trace, self.evals = [], {}

    # ---------- one node ----------
    def _op(self, node):
        return self.runtimes.get(bytes(node["runtime"][1])) if "runtime" in node else None

    def _exec(self, node, inputs, payloads):
        cls = node["class"]
        if cls == "reference":
            return self.store.get(node["artifact"])
        if cls == "literal":
            data = payloads.get(bytes(node["payload"][1]))
            if data is None:
                raise Reject("missing-dependency", f"literal payload {short(node['payload'])} not delivered")
            if not same(art(data), node["payload"]):
                raise Reject("integrity-failure", "literal payload does not match its digest")
            return data
        op = self._op(node)
        if op is None:
            raise Reject("unsupported-op", f"{node['id']}: runtime not held")
        if cls in ("delta", "residual"):
            base = next((v for v in inputs.values() if same(art(v), node["base"])), None)
            if base is None:
                base = self.store.get(node["base"]) if self.store.has(node["base"]) else None
            if base is None:
                raise Reject("baseline-mismatch", f"{node['id']}: exact base {short(node['base'])} not present")
            out = patch(base, node["params"])
        elif op == "gen.repeat.v1":
            out = repeat(node["params"])
        elif op == "patch.v1":
            (src,) = inputs.values()
            out = patch(src, node["params"])
        elif op == "concat.v1":
            out = encode(inputs["__regions__"])
        else:
            raise Reject("unsupported-op", f"{node['id']}: unknown op {op}")
        if node["id"] in self.faults.get("diverge", ()) and out:
            out = out[:-1] + b"!"                                    # receiver-side generator bug, same length
        return out

    # ---------- predicates ----------
    def _evaluate(self, p, regions, cache, audit, attempt):
        covers = p["covers"]
        if any(r not in regions for r in covers):
            return None
        inputs = H(encode([art(regions[r]) for r in covers]))
        cached = cache.get(p["id"])
        if cached is not None and same(cached["inputs"], inputs):
            return cached                                            # reuse: inputs unchanged
        self.evals[p["id"]] = self.evals.get(p["id"], 0) + 1
        if p["kind"] == "digest-match":
            (r,) = covers
            ok = same(art(regions[r]), p["expected"])
        elif p["validator"] == "xbranch.len-sum.v1":
            ok = sum(len(regions[r]) for r in covers) == p["threshold"]
        else:
            raise Reject("unsupported-profile", f"no validator {p['validator']}")
        ev = {"predicate": p["id"], "inputs": inputs, "pass": ok,
              "observed": [art(regions[r]) for r in covers], "seq": len(audit)}
        cache[p["id"]] = ev
        audit.append({"event": "evidence", "attempt": attempt, "predicate": p["id"], "pass": ok,
                      "inputs": inputs})
        return ev

    # ---------- an attempt ----------
    def run(self, plan, contract, payloads, binding_hash, attempt, max_repairs=None):
        audit = [{"event": "accept", "attempt": attempt, "binding": binding_hash}]
        nodes = {n["id"]: n for n in plan["nodes"]}
        fallbacks = {k: list(v) for k, v in plan.get("fallbacks", {}).items()}
        preds = contract["acceptance"] + contract.get("invariants", [])
        budget = contract["limits"].get("repairs", 0) if max_repairs is None else max_repairs
        for d in self.faults.get("evict", ()):
            self.store.evict(d)
        subst, outputs, regions, cache, repairs, results = {}, {}, {}, {}, [], []
        alts = {a for v in fallbacks.values() for a in v}
        main = [n for n in plan["nodes"] if n["id"] not in alts]
        order = check_dag({"nodes": main, "roots": plan["roots"]})
        children = {i: [m["id"] for m in main if i in m["deps"]] for i in order}

        def cone(start):
            seen, stack = set(), [start]
            while stack:
                x = stack.pop()
                if x not in seen:
                    seen.add(x)
                    stack.extend(children[x])
            return seen

        def ancestors_first(start):
            out, frontier = [start], [start]
            while frontier:
                nxt = []
                for x in frontier:
                    for d in nodes[x]["deps"]:
                        if d not in out:
                            out.append(d)
                            nxt.append(d)
                frontier = nxt
            return out

        while True:
            failure = None
            for nid in order:
                if nid in outputs:
                    continue
                node = nodes[subst.get(nid, nid)]
                inputs = {d: outputs[d] for d in nodes[nid]["deps"]}
                if node["class"] == "procedural" and self._op(node) == "concat.v1":
                    inputs = {"__regions__": dict(regions)}
                try:
                    out = self._exec(node, inputs, payloads)
                except Reject as r:
                    failure = (nid, nid, r.code, r.detail)
                    break
                self.trace.append(subst.get(nid, nid))
                outputs[nid] = out
                for region in nodes[nid].get("emits", []):
                    regions[region] = out
                for p in preds:                                       # validate at emission
                    ev = self._evaluate(p, regions, cache, audit, attempt) if set(p["covers"]) & set(
                        nodes[nid].get("emits", [])) or p["covers"] == [] else None
                    if ev is not None and not ev["pass"]:
                        failure = (nid, nid, "validation-failure",
                                   f"{p['id']} failed on {nid}: observed {short(ev['observed'][-1])}")
                        audit.append({"event": "rejected-output", "attempt": attempt, "node": nid,
                                      "runtime": node.get("runtime"), "predicate": p["id"],
                                      "observed": ev["observed"]})
                        break
                if failure:
                    break
            if failure is None:
                for p in preds:                                       # anything not yet evaluated
                    ev = self._evaluate(p, regions, cache, audit, attempt)
                    if ev is None:                                    # plan never produced its regions
                        results.append({"type": "RESULT", "stage": "failed", "missing": []})
                        audit.append({"event": "abort", "attempt": attempt, "node": None,
                                      "reason": "validation-failure", "detail": f"{p['id']} regions not produced"})
                        return {"status": "aborted", "reason": "validation-failure", "failed": None,
                                "audit": audit, "repairs": repairs, "results": results, "evidence": cache,
                                "output": None}
                    if not ev["pass"]:
                        failure = (order[-1], order[-1], "validation-failure", f"{p['id']} not satisfied")
                        break
            if failure is None:
                root = plan["roots"][0]
                results.append({"type": "RESULT", "stage": "validated", "output": art(outputs[root])})
                audit.append({"event": "validated", "attempt": attempt, "output": art(outputs[root])})
                return {"status": "validated", "output": outputs[root], "audit": audit, "repairs": repairs,
                        "results": results, "evidence": cache}
            failed_node, _, code, detail = failure
            target = next((x for x in ancestors_first(failed_node) if fallbacks.get(x)), None)
            if target is None or len(repairs) >= budget:
                missing = [nodes[failed_node]["artifact"]] if code == "missing-dependency" and \
                    "artifact" in nodes[failed_node] else []
                results.append({"type": "RESULT", "stage": "failed", "missing": missing})
                audit.append({"event": "abort", "attempt": attempt, "node": failed_node,
                              "reason": "repair-exhausted" if target is not None else code, "detail": detail})
                return {"status": "aborted", "reason": code, "failed": failed_node, "audit": audit,
                        "repairs": repairs, "results": results, "evidence": cache, "output": None}
            alt = fallbacks[target].pop(0)
            affected = sorted(cone(target))
            repairs.append({"type": "REPAIR", "repair": {"kind": "repair", "attempt": attempt, "failed": target,
                                                         "reason": code, "affected": affected,
                                                         "alternative": alt}})
            audit.append({"event": "repair", "attempt": attempt, "failed": target, "reason": code,
                          "affected": affected, "alternative": alt, "detail": detail})
            subst[target] = alt
            for x in affected:
                outputs.pop(x, None)
                for region in nodes[x].get("emits", []):
                    regions.pop(region, None)
