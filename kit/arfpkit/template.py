"""Contract split: a session-scoped contract template plus a small per-revision binding.

The template holds every rule that does not change with a target revision. A split binding names the
template by digest and carries only what does change: the target, and per-predicate expected digests,
designated references and threshold overrides. Sender and receiver both materialize the effective
contract from the two. Its id is the ordinary contract id, so plans, evidence, approvals and heads are
the same objects whether the contract crossed the wire whole or split.

The template needs no signature of its own: every binding is publisher-signed and names the
template's digest, so a template is authenticated by the first binding that names it.
"""
from .canon import oid
from .rules import Reject, lint_contract

# binding field -> predicate field it sets
OVERRIDES = {"expected": "expected", "references": "reference", "params": "threshold"}
PREDICATE_LISTS = ("acceptance", "invariants")


def predicates_of(obj):
    return [p for key in PREDICATE_LISTS for p in obj.get(key, [])]


def template_of(contract, move=("expected", "reference")):
    """Split a v0.1 contract into (template, overrides): the named per-revision fields move to the binding."""
    tmpl = {k: v for k, v in contract.items() if k not in ("kind", "target")}
    tmpl["kind"] = "contract-template"
    over = {"expected": {}, "references": {}}
    for key in PREDICATE_LISTS:
        if key in tmpl:
            moved = []
            for p in tmpl[key]:
                p = dict(p)
                if "expected" in move and "expected" in p:
                    over["expected"][p["id"]] = p.pop("expected")
                if "reference" in move and "reference" in p:
                    over["references"][p["id"]] = p.pop("reference")
                moved.append(p)
            tmpl[key] = moved
    return tmpl, {k: v for k, v in over.items() if v}


def materialize(template, binding):
    """The effective contract for the binding's revision, or Reject. Pure function of its inputs."""
    if not isinstance(template, dict) or template.get("kind") != "contract-template":
        raise Reject("integrity-failure", "not a contract template")
    by_id = {p["id"]: p for p in predicates_of(template)}
    for field in OVERRIDES:
        for pid in binding.get(field, {}):
            if pid not in by_id:
                raise Reject("invalid-contract", f"binding sets {field} for {pid}, which the template lacks")
    for pid in binding.get("params", {}):
        if "threshold" not in by_id[pid]:
            raise Reject("invalid-contract", f"{pid}: the template declares no threshold to override")
    contract = {k: v for k, v in template.items() if k != "kind"}
    contract["kind"] = "contract"
    contract["target"] = binding["target"]
    for key in PREDICATE_LISTS:
        if key in contract:
            out = []
            for p in contract[key]:
                p = dict(p)
                for field, slot in OVERRIDES.items():
                    if p["id"] in binding.get(field, {}):
                        p[slot] = binding[field][p["id"]]
                out.append(p)
            contract[key] = out
    for p in predicates_of(contract):
        if (p["kind"] == "digest-match" or p.get("mode") == "feature-digest") and "expected" not in p:
            raise Reject("invalid-contract", f"{p['id']}: no expected digest in the template or the binding")
        if p.get("mode") == "reference-metric" and "reference" not in p:
            raise Reject("invalid-contract", f"{p['id']}: no designated reference in the template or the binding")
    lint_contract(contract)
    return contract


def contract_id(template, binding):
    return oid(materialize(template, binding))
