#!/usr/bin/env python3
"""ARFP v0.1 object-level conformance sketch.

Builds fixtures for one scenario (publisher, repeater, workstation, phone), validates every
object against arfp-v0.1.cddl, runs the semantic rules, and writes report.json + report.md.
Outputs are synthetic (toy integer geometry, simulated decoders). There is no transport and no
real codec: this checks objects and rules, not performance.

Run:  python3 run_checks.py
"""
import copy
import json
import sys

import cbor2
import pycddl

from arfpkit import profile as P
from arfpkit.canon import (Tag, art, check_numbers, decode, encode, is_canonical, is_normalized_num,
                           key_types_uniform, num, num_value, oid, same, short)
from arfpkit.cose import fixture_key, rfc8032_key, sign1, verify1
from arfpkit.gate import BINDING_KID, envelope_hash
from arfpkit.template import materialize, template_of
from arfpkit.rules import (Forwarder, Reject, bound_from_sender, cancel_candidates, check_children,
                           check_transfer_binding,
                           check_eligible, check_fast_path, composed_bound, evidence_applies,
                           lint_contract, may_use, work_keys)

NOW = 1791698400000          # 2026-10-11T06:00:00Z, epoch milliseconds
CDDL = open("arfp-v0.1.cddl").read()
SCHEMA = pycddl.Schema(CDDL)                                   # the arfp-object union
RULES = ("target", "scope", "contract", "contract-template", "binding", "capabilities", "state", "demand", "plan",
         "evidence", "attestation", "approval", "receipt", "head", "delegation", "rewrite", "repair", "speculation",
         "message")
RULE_SCHEMAS = {}


def rule_schema(b):
    """Validate against the object's own rule, not only the union: pycddl 0.6.4 can accept, through the
    union, an object that no member rule accepts (see the split-binding negative case)."""
    try:
        kind = cbor2.loads(b).get("kind")
    except Exception:                                        # noqa: BLE001
        kind = None
    rule = kind if kind in RULES else "arfp-object"
    if rule not in RULE_SCHEMAS:
        RULE_SCHEMAS[rule] = SCHEMA if rule == "arfp-object" else pycddl.Schema(f"top = {rule}\n" + CDDL)
    return rule, RULE_SCHEMAS[rule]

PUB, WS, PH, R1, E1 = "key:publisher", "key:workstation", "key:phone", "key:repeater-1", "key:edge-1"
KEYS = {p: fixture_key(p) for p in (WS, PH, R1)}
KEYS[PUB] = rfc8032_key()                                   # RFC 8032 test key 1: independently checkable
PUBLISHED_BINDING_HEX = ("d2845826a201270458207075626b65792d656432353531392d7374617469632d616c6c6f776c69737431a0588e"
                         "a5646b696e646762696e64696e67666973737565641b000001a128425c0066746172676574822f5820dba9708b"
                         "eae13bb942a7b772cfd0166dd403ca4db9f4b3844eba73269900248668636f6e7472616374822f58203089acac"
                         "691520486fc7b4d38037fbdd5db33f494556df8358590b759bea6a53697075626c69736865726d6b65793a7075"
                         "626c6973686572584097616d5734978c9ebd1c605775d4dbbf4528fb7f7f2a5fa1a27af7ab5a359b3fa3d8a118"
                         "2a55c555b9402e6ed78bceaac7bade30881572dc76831e7d0434270a")
ALL6 = ["reference", "delta", "procedural", "latent", "residual", "literal"]
OBJ = "assembly/interstage"

results, schema_rows, sizes = [], [], {}


def record(cid, title, expected, fn):
    try:
        observed, ok = fn()
    except Reject as r:
        observed, ok = f"unexpected reject {r.code}: {r.detail}", False
    results.append({"id": cid, "case": title, "expected": expected, "observed": observed, "pass": bool(ok)})


def expect_reject(code, fn):
    try:
        fn()
    except Reject as r:
        return f"rejected {r.code}: {r.detail}", r.code == code
    return f"accepted (expected {code})", False


def expect_ok(fn, note=""):
    fn()
    return ("accepted" + (f"; {note}" if note else "")), True


def mm(d):
    return f"{num_value(d)} mm" if not isinstance(d, str) else d


# =====================================================================
# Geometry and the publisher's authoritative revision 28
# =====================================================================
frame = P.box(0, 0, 0, 2_000_000, 2_000_000, 1_000_000)
bracket27 = P.box(500_000, 500_000, 900_000, 520_000, 540_000, 910_000)
bracket28 = P.translate(bracket27, 5_000, 0, 0)
bolts = P.bolt_circle(1_000_000, 1_000_000, 1_000_000, 400_000)
fairing_ref = P.surface(600_000, 600_000, 1_100_300, 100_000, 8)
probe = fairing_ref[4 * 8 + 4]
mount28 = P.box(probe[0], probe[1], probe[2] + 3_000, probe[0] + 10_000, probe[1] + 10_000, probe[2] + 13_000)

latent_bytes = P.latent_encode(fairing_ref, 500)
latent_obj = decode(latent_bytes)
tex_payload = b"texture-seed:interstage-28"

RUNTIME = {}


def runtime(rid, det, bound=None):
    r = {"id": rid, "digest": art(b"runtime:" + rid.encode()), "det": det}
    if det in ("E", "T"):
        r["vectors"] = art(b"vectors:" + rid.encode())
    if det == "T":
        r["bound"] = bound
    RUNTIME[rid] = r
    return r


rt_xform = runtime("xform.delta.v1", "E")
rt_bolt = runtime("gen.bolt-circle.v2", "E")
rt_asm = runtime("assemble.v1", "E")
rt_tile = runtime("tile.geo.v1", "E")
rt_lod = runtime("tile.lod.v1", "E")
rt_view = runtime("view.compose.v1", "E")
rt_pose = runtime("pose.apply.v1", "E")
rt_surf = runtime("dec.surface.v3", "T", {"metric": "hausdorff-linf.v1", "value": num("0.15"), "units": "mm"})
rt_fast = runtime("dec.surface.v3-fast", "T", {"metric": "hausdorff-linf.v1", "value": num("0.25"), "units": "mm"})
rt_chamfer = runtime("dec.surface.v3c", "T", {"metric": "chamfer.v1", "value": num("0.1"), "units": "mm"})
rt_diff = runtime("dec.surface.diffusion.v1", "N")
rt_tex = runtime("dec.texture.v1", "N")


def rt_map(*rts):
    return {bytes(r["digest"][1]): r for r in rts}


# Publisher's authoritative parts and its own decode of the latent (sender-side evidence).
y_auth_parts = {"frame": frame, "bracket-12": bracket28, "sensor-mount": mount28}
y_pub_f = P.latent_decode(latent_obj, "dev:publisher", 75)
eps_pub_um = P.hausdorff(y_pub_f, fairing_ref)

target27 = {"kind": "target", "object": OBJ, "revision": 27, "publisher": PUB, "profile": P.PROFILE}
target = dict(target27, revision=28)
scope_all = {"kind": "scope", "target": oid(target), "select": "all"}
scope_nav = {"kind": "scope", "target": oid(target), "select": "all", "milestone": "navigable"}
scope_bay = {b: {"kind": "scope", "target": oid(target), "select": [f"bay-{b}"]} for b in "ABC"}

pred_parts = {"id": "parts.exact.v1", "kind": "digest-match", "covers": ["frame", "bracket-12", "sensor-mount"],
              "expected": art(P.project(y_auth_parts, ["frame", "bracket-12", "sensor-mount"])),
              "mode": "digest-match", "validator": "canon.digest.v1"}
pred_bolts = {"id": "bolts.features.v1", "kind": "invariant", "covers": ["bolt-pattern"],
              "expected": P.bolt_features(bolts), "mode": "feature-digest", "validator": "feat.bolt-circle.v1"}
pred_fairing = {"id": "fairing.hausdorff.v1", "kind": "metric-bound", "covers": ["fairing-surface"],
                "reference": art(encode(fairing_ref)), "metric": "hausdorff-linf.v1", "threshold": num("0.5"),
                "units": "mm", "composition": "additive", "mode": "reference-metric",
                "validator": "geom.hausdorff.v1"}
pred_clear = {"id": "clearance.min.v1", "kind": "invariant", "covers": "all", "metric": "clearance-linf.v1",
              "threshold": num("2"), "units": "mm", "validator": "geom.clearance.v1"}
pred_tex = {"id": "texture.sane.v1", "kind": "schema", "covers": ["skin-texture"], "validator": "tex.sanity.v1"}

contract = {
    "kind": "contract", "target": oid(target), "profile": P.PROFILE, "classes": ALL6,
    "acceptance": [pred_parts, pred_bolts, pred_fairing], "invariants": [pred_clear, pred_tex],
    "free": ["skin-texture"],
    "determinism": {"baseline-eligible": ["E"], "evidence-transfer": ["E", "T"]},
    "evidence": {"modes": ["digest-match", "feature-digest", "reference-metric", "checker-attestation"],
                 "checkers": [R1], "max-age": 600_000},
    "authority": {"publisher": PUB, "local-commit": True},
    "updates": [{"stream": "view", "mode": "replaceable", "fast-path": "shape-equal"},
                {"stream": "edits", "mode": "required-transition"}],
    "limits": {"bytes": 67_108_864, "cpu": 30_000, "memory": 268_435_456, "wall": 60_000, "repairs": 2},
    "milestones": [
        {"name": "navigable", "roots": ["frame", "fairing-surface"], "acceptance": ["fairing.hausdorff.v1"],
         "uses": ["navigate"]},
        {"name": "review-ready", "roots": ["frame", "bracket-12", "bolt-pattern", "fairing-surface",
                                           "skin-texture", "sensor-mount"],
         "acceptance": ["parts.exact.v1", "bolts.features.v1", "fairing.hausdorff.v1", "clearance.min.v1",
                        "texture.sane.v1"],
         "uses": ["navigate", "measure", "sign-off"]}],
}
FULL_USES = ["navigate", "measure", "sign-off"]
binding_obj = {"kind": "binding", "target": oid(target), "contract": oid(contract), "publisher": PUB,
               "issued": 1791676800000}
binding_env = sign1(KEYS[PUB], BINDING_KID, binding_obj)
BH = envelope_hash(binding_env)

# Contract split: the same rules as a session template plus a per-revision binding (contract_split.py)
template_obj, split_over = template_of(contract)
split_binding_obj = {"kind": "binding", "target": oid(target), "template": oid(template_obj), "publisher": PUB,
                     "issued": 1791676800000, **split_over}
split_binding_env = sign1(KEYS[PUB], BINDING_KID, split_binding_obj)
contract27 = dict(contract, target=oid(target27))

d_r1 = {"kind": "delegation", "issuer": PUB, "grantee": R1, "target": oid(target), "contract": oid(contract),
        "scope": oid(scope_all), "rights": ["cache", "forward", "execute", "check"], "recipients": [WS, PH],
        "expires": NOW + 3_600_000, "subdelegate": True, "budget": {"cpu": 20_000, "bytes": 33_554_432}}

caps_ws = {"kind": "capabilities", "endpoint": WS, "protocols": ["arfp/0"], "profiles": [P.PROFILE],
           "classes": ALL6, "runtimes": [rt_xform, rt_bolt, rt_surf, rt_tex, rt_asm],
           "limits": {"cpu": 30_000, "memory": 8_589_934_592}}
caps_ph = {"kind": "capabilities", "endpoint": PH, "protocols": ["arfp/0"], "profiles": [P.PROFILE],
           "classes": ["reference", "delta", "procedural", "latent", "literal"],
           "runtimes": [rt_xform, rt_bolt, rt_tex, rt_asm], "limits": {"cpu": 5_000, "memory": 1_073_741_824}}
RT_WS = rt_map(*caps_ws["runtimes"])
RT_PH = rt_map(*caps_ph["runtimes"])
RT_WS_PLUS = rt_map(*caps_ws["runtimes"], rt_fast, rt_chamfer, rt_diff)

# Committed rev-27 state: the bracket-12 output was produced on an exact path.
bracket27_out = art(encode(bracket27))
y27 = {"frame": frame, "bracket-12": bracket27, "bolt-pattern": bolts}
head27 = {"kind": "head", "object": OBJ, "target": oid(target27), "contract": oid(contract27),
          "scope": oid(dict(scope_all, target=oid(target27))), "output": art(encode(y27))}
BASE_DET = {bytes(bracket27_out[1]): "E"}


# =====================================================================
# Plans
# =====================================================================
def nd(nid, cls, deps=(), **kw):
    n = {"id": nid, "class": cls, "deps": list(deps)}
    n.update(kw)
    return n


def base_nodes():
    return [
        nd("frame", "reference", artifact=art(encode(frame)), emits=["frame"]),
        nd("bracket", "delta", op="xform.delta.v1", runtime=rt_xform["digest"], base=bracket27_out,
           params=encode({"dx": 5_000, "dy": 0, "dz": 0}), emits=["bracket-12"]),
        nd("bolts", "procedural", op="gen.bolt-circle.v2", runtime=rt_bolt["digest"],
           params=encode({"cx": 1_000_000, "cy": 1_000_000, "z": 1_000_000, "r": 400_000}), emits=["bolt-pattern"]),
        nd("mount", "literal", payload=art(encode(mount28)), emits=["sensor-mount"]),
    ]


def plan_for(snapshot, fairing_node, skin_node=None, extra=()):
    skin = skin_node or nd("skin", "latent", op="dec.texture.v1", runtime=rt_tex["digest"],
                           payload=art(tex_payload), emits=["skin-texture"])
    nodes = base_nodes() + [fairing_node, skin] + list(extra)
    asm = nd("assemble", "procedural", [n["id"] for n in nodes], op="assemble.v1", runtime=rt_asm["digest"])
    return {"kind": "plan", "target": oid(target), "contract": oid(contract), "scope": oid(scope_all),
            "snapshot": snapshot, "nodes": nodes + [asm], "roots": ["assemble"]}


def fairing(rt, at=None):
    n = nd("fairing", "latent", op=rt["id"], runtime=rt["digest"], payload=art(latent_bytes),
           emits=["fairing-surface"], claim={"bytes": len(latent_bytes), "error": num("0.35")})
    if at:
        n["at"] = at
    return n


plan_ws = plan_for(41, fairing(rt_surf))
plan_ph_orig = plan_for(17, fairing(rt_surf))                 # phone decoding the surface itself
plan_ph = plan_for(17, fairing(rt_surf, at=R1))               # rewritten: decode at the repeater


def elig_ws(plan, caps=caps_ws, rts=RT_WS, snap=41, delegs=(d_r1,), c=contract):
    return check_eligible(plan, c, caps, rts, WS, snap, BASE_DET, delegations=delegs)


def elig_ph(plan, delegs=(d_r1,)):
    return check_eligible(plan, contract, caps_ph, RT_PH, PH, 17, BASE_DET, delegations=delegs)


# =====================================================================
# Execution (synthetic) and evidence
# =====================================================================
def realize(fairing_points, texture):
    return {"frame": frame, "bracket-12": P.translate(bracket27, 5_000, 0, 0),
            "bolt-pattern": P.bolt_circle(1_000_000, 1_000_000, 1_000_000, 400_000),
            "fairing-surface": fairing_points, "skin-texture": texture, "sensor-mount": mount28}


y_ws_f = P.latent_decode(latent_obj, "dev:workstation", 75)
y_r1_f = P.latent_decode(latent_obj, "dev:repeater-1", 75)
y_ws = realize(y_ws_f, P.texture_decode(tex_payload, "dev:workstation"))
y_ph = realize(y_r1_f, P.texture_decode(tex_payload, "dev:phone"))
out_ws, out_ph = art(encode(y_ws)), art(encode(y_ph))


def ev(checker, output, pred, passed, validator, reference=None, measured=None, units=None, c=contract,
       scope=scope_all):
    e = {"kind": "evidence", "contract": oid(c), "scope": oid(scope), "output": output, "predicate": pred["id"],
         "pass": passed, "validator": validator, "checker": checker, "at": NOW}
    if reference is not None:
        e["reference"] = reference
    if measured is not None:
        e["measured"], e["units"] = measured, units
    return e


def accept_output(y, who, fairing_evidence, fairing_ok):
    """Run every predicate the receiver can run itself; fairing evidence arrives from elsewhere,
    and fairing_ok is the result of checking it (composed bound or direct measurement)."""
    evs = []
    parts_ok = same(art(P.project(y, pred_parts["covers"])), pred_parts["expected"])
    evs.append(ev(who, art(encode(y)), pred_parts, parts_ok, "canon.digest.v1"))
    bolts_ok = same(P.bolt_features(y["bolt-pattern"]), pred_bolts["expected"])
    evs.append(ev(who, art(encode(y)), pred_bolts, bolts_ok, "feat.bolt-circle.v1"))
    clr = P.clearance(y["fairing-surface"], y["sensor-mount"])
    evs.append(ev(who, art(encode(y)), pred_clear, clr >= 2_000, "geom.clearance.v1",
                  measured=P.um_to_mm(clr), units="mm"))
    evs.append(ev(who, art(encode(y)), pred_tex, 0 < len(y["skin-texture"]) <= 65_536, "tex.sanity.v1"))
    return evs + fairing_evidence, all(e["pass"] for e in evs + fairing_evidence) and fairing_ok, clr


# Workstation: fairing evidence moves by bound (publisher's measured eps + runtime divergence bound).
WK_WS = work_keys(plan_ws)
ev_pub = ev(PUB, art(encode(y_pub_f)), pred_fairing, eps_pub_um <= 500, "geom.hausdorff.v1",
            reference=pred_fairing["reference"], measured=P.um_to_mm(eps_pub_um), units="mm")
ev_pub["work"] = WK_WS["fairing"]                      # publisher decoded the same work the receiver will
check_transfer_binding(ev_pub, WK_WS["fairing"])
ev_ws_hop = ev(WS, art(encode(y_ws_f)), pred_fairing, True, "bound.transfer.v1",
               reference=art(encode(y_pub_f)))
ev_ws_hop.update({"bound": rt_surf["bound"]["value"], "units": "mm", "work": WK_WS["fairing"]})
ok_bound, total_ws = composed_bound(pred_fairing, [ev_pub, ev_ws_hop], pred_fairing["reference"], art(encode(y_ws_f)))
true_ws_um = P.hausdorff(y_ws_f, fairing_ref)          # the receiver cannot compute this; the harness can
evs_ws, accepted_ws, clr_ws = accept_output(y_ws, WS, [ev_pub, ev_ws_hop], ok_bound)

# Phone: the repeater decoded, measured against the reference itself, and shipped exact bytes.
eps_r1_um = P.hausdorff(y_r1_f, fairing_ref)
ev_r1 = ev(R1, art(encode(y_r1_f)), pred_fairing, eps_r1_um <= 500, "geom.hausdorff.v1",
           reference=pred_fairing["reference"], measured=P.um_to_mm(eps_r1_um), units="mm")
evs_ph, accepted_ph, clr_ph = accept_output(y_ph, PH, [ev_r1], ev_r1["pass"])


# =====================================================================
# Commit machinery
# =====================================================================
class Consumer:
    def __init__(self, party, head, snapshot):
        self.party, self.head, self.snapshot, self.journal = party, head, snapshot, {}

    def head_id(self):
        return oid(self.head) if self.head else None

    def commit(self, signed_approval, approver_key, active_scope=None):
        a = verify1(approver_key.public_key(), signed_approval)
        if a["txn"] in self.journal:
            return self.journal[a["txn"]]                       # idempotent retry
        if active_scope is not None and not same(a["scope"], active_scope):
            raise Reject("canceled", "approval is for a superseded demand")
        prior, exp = self.head_id(), a["expected-head"]
        if (exp is None and prior is None) or (exp is not None and prior is not None and same(exp, prior)):
            self.head = {"kind": "head", "object": OBJ, "target": a["target"], "contract": a["contract"],
                         "scope": a["scope"], "output": a["output"]}
            self.snapshot += 1
            status, new = "committed", oid(self.head)
        else:
            status, new = "conflict", None
        r = {"kind": "receipt", "txn": a["txn"], "approval": oid(a), "prior-head": prior, "head": new,
             "status": status}
        signed = sign1(KEYS[self.party], self.party, r)
        self.journal[a["txn"]] = signed
        return signed


def approval_for(plan, output, evs, txn, expected_head, scope=scope_all, authority=WS):
    return {"kind": "approval", "binding": BH, "target": oid(target), "contract": oid(contract), "scope": oid(scope),
            "plan": oid(plan), "output": output, "evidence": [oid(e) for e in evs], "txn": txn,
            "expected-head": expected_head, "authority": authority}


approval_ws = approval_for(plan_ws, out_ws, evs_ws, "ws-28-1", oid(head27))
signed_approval_ws = sign1(KEYS[WS], WS, approval_ws)


# =====================================================================
# Schema validation of every fixture
# =====================================================================
def msg(body, attempt="a-1", **kw):
    m = {"kind": "message", "v": 0, "session": "s-interstage-28", "attempt": attempt, "body": body}
    m.update(kw)
    return m


ws_consumer = Consumer(WS, head27, 41)
signed_receipt_ws = ws_consumer.commit(signed_approval_ws, KEYS[WS])
receipt_ws = verify1(KEYS[WS].public_key(), signed_receipt_ws)

demand_ph = {"kind": "demand", "consumer": PH, "stream": "view", "seq": 3, "target": oid(target),
             "scope": oid(scope_bay["A"])}
state_ws = {"kind": "state", "endpoint": WS, "snapshot": 41, "heads": [head27],
            "have": [art(encode(frame)), bracket27_out]}
rewrite_ph = {"kind": "rewrite", "from": oid(plan_ph_orig), "to": oid(plan_ph), "repeater": R1,
              "delegation": oid(d_r1), "changed": ["fairing"], "reused": [art(encode(frame))],
              "pending": ["fairing"]}
repair_ws = {"kind": "repair", "attempt": "a-2", "failed": "fairing", "reason": "validation-failure",
             "affected": ["fairing", "assemble"], "alternative": "fairing-literal"}
chunk = {"node": "fairing", "digest": art(latent_bytes), "data": latent_bytes}
ev_r1_signed = dict(ev_r1, checker=PUB)
attestation_obj = {"kind": "attestation", "evidence": envelope_hash(sign1(KEYS[PUB], BINDING_KID, ev_r1_signed)),
                   "attester": R1, "delegation": oid(d_r1), "meaning": "signature-verified", "at": NOW}

FIXTURES = {
    "target": target, "scope (full)": scope_all, "scope (milestone)": scope_nav, "contract": contract,
    "capabilities (workstation)": caps_ws, "capabilities (phone)": caps_ph, "state": state_ws,
    "demand": demand_ph, "plan (workstation, 7 nodes)": plan_ws, "plan (phone, rewritten)": plan_ph,
    "delegation": d_r1, "rewrite": rewrite_ph, "evidence": ev_pub, "approval": approval_ws,
    "receipt": receipt_ws, "head": ws_consumer.head, "repair": repair_ws,
    "msg CAPABILITIES": msg({"type": "CAPABILITIES", "caps": caps_ws}),
    "msg STATE": msg({"type": "STATE", "state": state_ws}),
    "msg DEMAND": msg({"type": "DEMAND", "demand": demand_ph}),
    "msg OFFER": msg({"type": "OFFER", "binding": binding_env, "target": target, "contract": contract,
                      "scope": oid(scope_all), "plan": plan_ws}),
    "msg OFFER (split, template inline)": msg({"type": "OFFER", "binding": split_binding_env, "target": target,
                                               "template": template_obj, "scope": oid(scope_all), "plan": plan_ws}),
    "msg OFFER (split, template cached)": msg({"type": "OFFER", "binding": split_binding_env, "target": target,
                                               "scope": oid(scope_all), "plan": plan_ws}),
    "msg ACCEPT": msg({"type": "ACCEPT", "plan": oid(plan_ws)}),
    "msg REJECT": msg({"type": "REJECT", "plan": oid(plan_ws), "reason": "ineligible-plan"}),
    "msg WORKTREE_PAYLOAD": msg({"type": "WORKTREE_PAYLOAD", "plan": oid(plan_ws), "chunks": [chunk]}),
    "msg RESULT": msg({"type": "RESULT", "stage": "validated", "output": out_ws,
                       "evidence": [oid(e) for e in evs_ws]}),
    "msg REPAIR": msg({"type": "REPAIR", "repair": repair_ws}),
    "msg SUPERSEDE": msg({"type": "SUPERSEDE", "stream": "view", "old-seq": 3,
                          "new": dict(demand_ph, seq=4, scope=oid(scope_bay["C"]))}),
    "msg CANCEL": msg({"type": "CANCEL", "stream": "view", "seq": 4}),
    "msg VALIDATION_APPROVAL": msg({"type": "VALIDATION_APPROVAL", "signed": signed_approval_ws}),
    "binding": binding_obj,
    "contract-template": template_obj,
    "binding (split form)": split_binding_obj,
    "binding (split form, threshold override)": dict(split_binding_obj, params={"fairing.hausdorff.v1": num("0.4")}),
    "attestation": attestation_obj,
    "msg EVIDENCE": msg({"type": "EVIDENCE", "signed": [sign1(KEYS[PUB], BINDING_KID, ev_r1_signed),
                                                        sign1(KEYS[R1], R1, attestation_obj),
                                                        sign1(KEYS[PUB], BINDING_KID, d_r1)]}),
    "msg COMMIT_RECEIPT": msg({"type": "COMMIT_RECEIPT", "signed": signed_receipt_ws}),
}

# Speed mechanisms (speed_mechanisms.py): per-receiver fidelity, speculative start, proof evidence, push
import speed_mechanisms                                         # noqa: E402

FIXTURES.update(speed_mechanisms.setup(dict(
    contract=contract, target=target, plan_ws=plan_ws, plan_for=plan_for, nd=nd, fairing=fairing, rt_surf=rt_surf,
    R1=R1, fairing_ref=fairing_ref, latent_bytes=latent_bytes, RT_WS=RT_WS, WS=WS, PH=PH, PUB=PUB, KEYS=KEYS,
    NOW=NOW, scope_all=scope_all, elig_ws=elig_ws, total_ws=total_ws, out_ws=out_ws, msg=msg,
    template_obj=template_obj, split_binding_obj=split_binding_obj)))

import os
import re

os.makedirs("vectors", exist_ok=True)
for name, obj in FIXTURES.items():
    b = encode(obj)
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    open(os.path.join("vectors", slug + ".cbor"), "wb").write(b)
    valid, err = True, ""
    for label, sch in (("union", SCHEMA), rule_schema(b)):
        try:
            sch.validate_cbor(b)
        except Exception as e:                               # noqa: BLE001
            valid, err = False, f"{label}: " + str(e).splitlines()[0]
    schema_rows.append({"fixture": name, "valid": valid, "bytes": len(b), "error": err})


def bad(obj_fn):
    o = obj_fn()
    try:
        b = encode(o)
        how = ""
    except TypeError:
        b = cbor2.dumps(to_cbor2(o), canonical=True)          # a lenient encoder would still emit it
        how = "refused by the encoder; "
    rule, sch = rule_schema(b)
    try:
        SCHEMA.validate_cbor(b)
        union = "accepted"
    except Exception:                                        # noqa: BLE001
        union = "rejected"
    try:
        sch.validate_cbor(b)
        return how + f"accepted by the {rule} rule", False
    except Exception:                                        # noqa: BLE001
        note = "" if union == "rejected" else f" (the arfp-object union {union} it)"
        return how + f"rejected by the {rule} rule{note}", True


def to_cbor2(o):
    if isinstance(o, Tag):
        return cbor2.CBORTag(o.tag, to_cbor2(o.value))
    if isinstance(o, dict):
        return {k: to_cbor2(v) for k, v in o.items()}
    if isinstance(o, list):
        return [to_cbor2(v) for v in o]
    return o


def mutate(obj, path, value=None, delete=False):
    o = copy.deepcopy(obj)
    cur = o
    for k in path[:-1]:
        cur = cur[k]
    if delete:
        del cur[path[-1]]
    else:
        cur[path[-1]] = value
    return o


NEGATIVE_SCHEMA = [
    ("C05", "Unknown node class \"hologram\"", lambda: mutate(plan_ws, ["nodes", 0, "class"], "hologram")),
    ("", "Contract without a determinism declaration", lambda: mutate(contract, ["determinism"], delete=True)),
    ("", "T-class runtime with no divergence bound",
     lambda: mutate(caps_ws, ["runtimes", 2], {k: v for k, v in rt_surf.items() if k != "bound"})),
    ("", "Digest algorithm given as text", lambda: mutate(ev_pub, ["output"], ["sha256", bytes(32)])),
    ("", "OFFER with no plan", lambda: mutate(FIXTURES["msg OFFER"], ["body", "plan"], delete=True)),
    ("", "Receipt status \"probably-committed\"", lambda: mutate(receipt_ws, ["status"], "probably-committed")),
    ("", "Unknown message type \"TELEPORT\"", lambda: mutate(FIXTURES["msg CANCEL"], ["body", "type"], "TELEPORT")),
    ("", "Scope selecting an empty list", lambda: mutate(scope_all, ["select"], [])),
    ("C28", "Threshold as a binary float (0.5)", lambda: mutate(contract, ["acceptance", 2, "threshold"], 0.5)),
    ("", "Binding naming both a whole contract and a template", lambda: dict(binding_obj, template=oid(template_obj))),
    ("", "Split binding with expected digests as a list instead of a map",
     lambda: dict(split_binding_obj, expected=list(split_binding_obj["expected"].values()))),
    ("", "Demand whose acceptance bounds are a list instead of a map",
     lambda: mutate(FIXTURES["demand (receiver acceptance, subscription)"], ["accept", "bounds"], [num("0.4")])),
    ("", "PUSH with no base", lambda: mutate(FIXTURES["msg PUSH"], ["body", "base"], delete=True)),
]
negative_rows = []
for cid, title, fn in NEGATIVE_SCHEMA:
    observed, ok = bad(fn)
    negative_rows.append({"id": cid, "case": title, "observed": observed, "pass": ok})


# =====================================================================
# Conformance cases (object level)
# =====================================================================
# C01: different plans, same exact output
plan_lit = plan_for(41, fairing(rt_surf))
plan_lit["nodes"][1] = nd("bracket", "literal", payload=art(encode(bracket28)), emits=["bracket-12"])
def exact_digest(y):
    return art(P.project(y, pred_parts["covers"]))


y_lit = dict(y_ws, **{"bracket-12": decode(encode(bracket28))})   # bracket shipped as literal bytes
record("C01", "Different eligible plans target the same exact output", "same authenticated digest",
       lambda: (f"delta plan, literal plan and phone plan all give {short(exact_digest(y_ws))} for the exact parts",
                elig_ws(plan_lit) and same(exact_digest(y_ws), exact_digest(y_lit))
                and same(exact_digest(y_ws), exact_digest(y_ph)) and same(exact_digest(y_ws), pred_parts["expected"])))

record("C02", "Two approximate outputs satisfy the same contract",
       "both accepted, distinct output digests",
       lambda: (f"workstation {short(out_ws)} and phone {short(out_ph)} both accepted",
                accepted_ws and accepted_ph and not same(out_ws, out_ph)))

plan_c03 = plan_for(41, fairing(rt_surf), extra=[nd("fairing-patch", "delta", ["fairing"], op="xform.delta.v1",
                                                    runtime=rt_xform["digest"], base=art(encode(y_ws_f)),
                                                    params=encode({"dx": 0, "dy": 0, "dz": 200}))])
BASE_DET_C03 = {**BASE_DET, bytes(art(encode(y_ws_f))[1]): "T"}
record("C03", "Patch targets a receiver's approximate (T-class) baseline", "reject baseline-mismatch",
       lambda: expect_reject("baseline-mismatch", lambda: check_eligible(
           plan_c03, contract, caps_ws, RT_WS, WS, 41, BASE_DET_C03, delegations=[d_r1])))

record("C05", "Unknown required profile", "reject unsupported-profile",
       lambda: expect_reject("unsupported-profile", lambda: elig_ws(plan_ws, caps=dict(caps_ws, profiles=["scene.other.v1"]))))

bad_rt = dict(fairing(rt_surf), runtime=art(b"runtime:dec.surface.v2"))
record("C06", "Wrong decoder binding (runtime digest not held)", "reject unsupported-op",
       lambda: expect_reject("unsupported-op", lambda: elig_ws(plan_for(41, bad_rt))))

# C09: a revision where the mount sits 2.1 mm above the surface point the decode pushes up most
k_up = max(range(len(fairing_ref)), key=lambda i: y_ws_f[i][2] - fairing_ref[i][2])
pk = fairing_ref[k_up]
mount29 = P.box(pk[0], pk[1], pk[2] + 2_100, pk[0] + 10_000, pk[1] + 10_000, pk[2] + 12_100)
y_ws29 = dict(y_ws, **{"sensor-mount": mount29})
clr_ref29 = P.clearance(fairing_ref, mount29)
clr_ws29 = P.clearance(y_ws_f, mount29)
record("C09", "Region checks pass but a global invariant fails", "reject the full output",
       lambda: (f"fairing bound {total_ws} mm passes; clearance {num_value(P.um_to_mm(clr_ws29))} mm on the decoded "
                f"surface vs {num_value(P.um_to_mm(clr_ref29))} mm on the reference: output rejected",
                ok_bound and clr_ref29 >= 2_000 and clr_ws29 < 2_000))

contract_exact = dict(contract, classes=["reference", "delta", "procedural", "residual", "literal"])
plan_exact = dict(plan_ws, contract=oid(contract_exact))
record("C11", "Exact-only contract, fallback uses an approximate class", "reject ineligible-plan",
       lambda: expect_reject("ineligible-plan", lambda: elig_ws(plan_exact, c=contract_exact)))

record("C12", "Accepted plan is rewritten by a repeater", "identified replacement that is itself eligible",
       lambda: (lambda before: (f"original phone plan: {before}; rewrite {short(oid(rewrite_ph))} moves the decode "
                                f"to the repeater; rewritten plan eligible", elig_ph(plan_ph)))(
           expect_reject("unsupported-op", lambda: elig_ph(plan_ph_orig))[0]))

record("C13", "Scoped result is accepted", "cannot authorize full-target use",
       lambda: (f"bay-A scope may 'sign-off': {may_use(contract, scope_bay['A'], 'sign-off', FULL_USES)}",
                not may_use(contract, scope_bay["A"], "sign-off", FULL_USES)))

record("C14", "Milestone passes while full result is incomplete", "only declared milestone uses",
       lambda: (f"navigable milestone: navigate={may_use(contract, scope_nav, 'navigate', FULL_USES)}, "
                f"measure={may_use(contract, scope_nav, 'measure', FULL_USES)}",
                may_use(contract, scope_nav, "navigate", FULL_USES)
                and not may_use(contract, scope_nav, "measure", FULL_USES)))


# C15 / C16: camera jump with shared work
def tile_plan(consumer, bays, lod):
    nodes = [nd("frame", "reference", artifact=art(encode(frame))),
             nd("bolts", "procedural", op="gen.bolt-circle.v2", runtime=rt_bolt["digest"],
                params=encode({"cx": 1_000_000, "cy": 1_000_000, "z": 1_000_000, "r": 400_000}))]
    view_deps = []
    for b in bays:
        nodes.append(nd(f"geo-{b}", "procedural", ["frame"], op="tile.geo.v1", runtime=rt_tile["digest"],
                        params=encode({"bay": b})))
        view_deps.append(f"geo-{b}")
        if lod:
            nodes.append(nd(f"lod-{b}", "procedural", [f"geo-{b}"], op="tile.lod.v1", runtime=rt_lod["digest"],
                            params=encode({"bay": b, "device": "phone"})))
            view_deps[-1] = f"lod-{b}"
    nodes.append(nd("view", "procedural", view_deps + ["bolts"], op="view.compose.v1",
                    runtime=rt_view["digest"], params=encode({"consumer": consumer, "bays": bays})))
    return {"kind": "plan", "target": oid(target), "contract": oid(contract), "scope": oid(scope_all),
            "snapshot": 1, "nodes": nodes, "roots": ["view"]}


tp = {"ws": tile_plan(WS, ["A", "B"], False), "ph_old": tile_plan(PH, ["A"], True), "ph_new": tile_plan(PH, ["C"], True)}
wks, deps, names = {}, {}, {}
for pname, pl in tp.items():
    keys = work_keys(pl)
    wks[pname] = keys
    for n in pl["nodes"]:
        k = bytes(keys[n["id"]][1])
        deps[k] = [bytes(keys[d][1]) for d in n["deps"]]
        names.setdefault(k, f"{n['id']}" if n["id"] not in ("view",) else f"view({pname})")
shared_geo_a = same(wks["ws"]["geo-A"], wks["ph_old"]["geo-A"])
roots = {p: {bytes(wks[p]["view"][1])} for p in tp}
completed = {bytes(wks["ws"]["frame"][1]), bytes(wks["ws"]["bolts"][1])}
unfinished = set(deps) - completed
cancel = cancel_candidates({"ws": roots["ws"], "ph": roots["ph_old"]}, {"ws": roots["ws"], "ph": roots["ph_new"]},
                           deps, unfinished)
cancel_names = sorted(names[k] for k in cancel)
record("C15", "Receiver cancels a demand whose work another receiver needs", "shared work stays live",
       lambda: (f"geo-A has one work key in both plans: {shared_geo_a}; geo-A canceled: "
                f"{bytes(wks['ph_old']['geo-A'][1]) in cancel}",
                shared_geo_a and bytes(wks["ph_old"]["geo-A"][1]) not in cancel))
record("C16", "Replaceable view demand superseded (camera jump)", "retire only the phone-only unfinished work",
       lambda: (f"cancel set = {cancel_names}", cancel_names == ["lod-A", "view(ph_old)"]))


def supersede(stream):
    rule = next(r for r in contract["updates"] if r["stream"] == stream)
    if rule["mode"] != "replaceable":
        raise Reject("permission-denied", f"stream '{stream}' is required-transition; supersession cannot erase it")
    return True


record("C17", "Planner marks a required-transition stream obsolete", "reject; profile wins",
       lambda: expect_reject("permission-denied", lambda: supersede("edits")))

ph_consumer = Consumer(PH, None, 17)
late = sign1(KEYS[PH], PH, approval_for(plan_ph, out_ph, evs_ph, "ph-view-3", None, scope=scope_bay["A"], authority=PH))
record("C18", "Old canceled result arrives late", "not committed as the new demand's result",
       lambda: expect_reject("canceled", lambda: ph_consumer.commit(late, KEYS[PH], active_scope=oid(scope_bay["C"]))))

stale = sign1(KEYS[WS], WS, approval_for(plan_ws, out_ws, evs_ws, "ws-28-2", oid(head27)))
record("C19", "Local head changed before commit", "conflict; newer head untouched",
       lambda: (lambda r: (f"status {r['status']}; head still {short(ws_consumer.head_id())}",
                           r["status"] == "conflict" and same(ws_consumer.head_id(), receipt_ws["head"])))(
           verify1(KEYS[WS].public_key(), ws_consumer.commit(stale, KEYS[WS]))))

record("C20", "Commit acknowledgment lost, request retried", "same durable outcome",
       lambda: (lambda again: (f"retry returned byte-identical receipt: {encode(again) == encode(signed_receipt_ws)}",
                               encode(again) == encode(signed_receipt_ws)))(ws_consumer.commit(signed_approval_ws, KEYS[WS])))

contract29 = dict(contract, target=oid(dict(target, revision=29)))
record("C22", "Cached artifact carries evidence for a different contract", "evidence not reused",
       lambda: (f"applies under rev-28 contract: {evidence_applies(evs_ws[0], contract, scope_all, out_ws, NOW)}; "
                f"under rev-29 contract: {evidence_applies(evs_ws[0], contract29, scope_all, out_ws, NOW)}",
                evidence_applies(evs_ws[0], contract, scope_all, out_ws, NOW)
                and not evidence_applies(evs_ws[0], contract29, scope_all, out_ws, NOW)))

record("C23", "Repeater without execute right asked to transform", "reject permission-denied",
       lambda: expect_reject("permission-denied", lambda: elig_ph(plan_for(17, fairing(rt_surf, at=E1)))))

SCOPES = {bytes(oid(s)[1]): s for s in [scope_all, scope_nav, *scope_bay.values()]}


def child(**kw):
    c = {"kind": "delegation", "issuer": R1, "grantee": E1, "target": oid(target), "contract": oid(contract),
         "scope": oid(scope_bay["A"]), "rights": ["cache", "forward", "execute"], "recipients": [PH],
         "expires": NOW + 1_800_000, "subdelegate": False, "budget": {"cpu": 8_000, "bytes": 8_388_608},
         "parent": oid(d_r1)}
    c.update(kw)
    return c


record("C24", "Two child grants each copy the parent's full budget", "reject resource-limit",
       lambda: expect_reject("resource-limit", lambda: check_children(
           d_r1, [child(budget=dict(d_r1["budget"])),
                  child(grantee="key:edge-2", budget=dict(d_r1["budget"]))], SCOPES)))
record("C24b", "Child grant adds a right the parent lacks", "reject permission-denied",
       lambda: expect_reject("permission-denied", lambda: check_children(
           d_r1, [child(rights=["cache", "rewrite"])], SCOPES)))
record("C24c", "Children that partition the budget and narrow the scope", "accepted",
       lambda: expect_ok(lambda: check_children(
           d_r1, [child(), child(grantee="key:edge-2", budget={"cpu": 12_000, "bytes": 25_165_824})], SCOPES),
           "8 000 + 12 000 ms of a 20 000 ms parent"))

# C25: multi-hop approximation
hop1 = P.translate(fairing_ref, 0, 0, 300)
hop2 = P.translate(hop1, 0, 0, 300)
x_ref = pred_fairing["reference"]
e_h1 = ev(R1, art(encode(hop1)), pred_fairing, True, "geom.hausdorff.v1", reference=x_ref,
          measured=P.um_to_mm(P.hausdorff(hop1, fairing_ref)), units="mm")
e_h2 = ev(E1, art(encode(hop2)), pred_fairing, True, "geom.hausdorff.v1", reference=art(encode(hop1)),
          measured=P.um_to_mm(P.hausdorff(hop2, hop1)), units="mm")
naive = all(num_value(e["measured"]) <= num_value(pred_fairing["threshold"]) for e in (e_h1, e_h2))
add_ok, add_total = composed_bound(pred_fairing, [e_h1, e_h2], x_ref, art(encode(hop2)))
true_h = P.hausdorff(hop2, fairing_ref)
record("C25", "Two repeaters each pass 0.5 mm locally", "end-to-end bound enforced",
       lambda: (f"per-hop 0.3 + 0.3 mm each pass locally (naive accept: {naive}); additive bound {add_total} mm "
                f"rejects; true end-to-end {num_value(P.um_to_mm(true_h))} mm", naive and not add_ok and true_h > 500))

ring = [Forwarder(p) for p in ("key:relay-1", "key:relay-2", "key:relay-3")]
m0 = msg({"type": "DEMAND", "demand": demand_ph}, ttl=8, via=[])
forwards, hop, m, outcome = 0, 0, m0, "forward"
while m is not None and forwards < 100:
    m, outcome = ring[hop % 3].handle(m)
    if m is not None:
        forwards += 1
    hop += 1
record("C26", "Repeaters forward a request around a loop", "bounded; no unbounded work",
       lambda: (f"{forwards} forwards, then {outcome}", forwards == 3 and outcome == "drop-duplicate"))


# C28: canonical encoding across two independent encoders
agree = sum(encode(o) == cbor2.dumps(to_cbor2(o), canonical=True) for o in FIXTURES.values())
unsorted = b"\xa2" + encode("b") + encode(1) + encode("a") + encode(2)
long_head = b"\x18\x05"
record("C28", "Canonical encoding across independent implementations", "identical bytes; deviations detected",
       lambda: (f"{agree}/{len(FIXTURES)} fixtures byte-identical in both encoders; unsorted map canonical: "
                f"{is_canonical(unsorted)}; non-shortest int canonical: {is_canonical(long_head)}; "
                f"num('0.50') == num('0.5'): {encode(num('0.50')) == encode(num('0.5'))}",
                agree == len(FIXTURES) and not is_canonical(unsorted) and not is_canonical(long_head)
                and encode(num("0.50")) == encode(num("0.5")) and not is_normalized_num(Tag(4, [-2, 50]))))

mixed = {1000: 0, "a": 0}
record("C28b", "Map mixing integer and text keys", "orders differ; no ARFP map mixes key types",
       lambda: (f"RFC 8949 and RFC 7049 orders agree on the mixed map: "
                f"{encode(mixed) == cbor2.dumps(mixed, canonical=True)}; fixtures with uniform key types: "
                f"{sum(key_types_uniform(o) for o in FIXTURES.values())}/{len(FIXTURES)}",
                encode(mixed) != cbor2.dumps(mixed, canonical=True)
                and all(key_types_uniform(o) for o in FIXTURES.values())))
denorm = dict(ev_pub, measured=Tag(4, [-2, 50]))
posexp = dict(ev_pub, measured=Tag(4, [1, 1]))
record("C28c", "Decimals 4([-2, 50]) (0.5) and 4([1, 1]) (10)", "both rejected; all fixtures normalized",
       lambda: (f"flagged: {check_numbers(denorm) + check_numbers(posexp)}; fixtures clean: "
                f"{sum(not check_numbers(o) for o in FIXTURES.values())}/{len(FIXTURES)}",
                check_numbers(denorm) == ["$.measured"] and check_numbers(posexp) == ["$.measured"]
                and all(not check_numbers(o) for o in FIXTURES.values())))

# ---------- rules beyond the C-list ----------
record("R1", "Evidence moves by bound: sender eps + runtime divergence fits the threshold", "accepted",
       lambda: (f"{num_value(P.um_to_mm(eps_pub_um))} + 0.15 = {total_ws} mm <= 0.5; true distance "
                f"{num_value(P.um_to_mm(true_ws_um))} mm (inside the bound)", ok_bound and true_ws_um <= total_ws * 1000))

other_wk = work_keys(plan_for(41, fairing(rt_fast)))["fairing"]
record("R1b", "Sender evidence measured on a different decode (other runtime)", "reject validation-failure",
       lambda: expect_reject("validation-failure", lambda: check_transfer_binding(ev_pub, other_wk)))
record("R2", "Non-reproducible (N) decoder on a reference-bound region at the receiver", "reject ineligible-plan",
       lambda: expect_reject("ineligible-plan", lambda: elig_ws(plan_for(41, fairing(rt_diff)), rts=RT_WS_PLUS)))
record("R3", "Same N decoder placed at a checker repeater (placement converts determinism)", "accepted",
       lambda: expect_ok(lambda: elig_ws(plan_for(41, fairing(rt_diff, at=R1)), rts=RT_WS_PLUS),
                         "receiver gets checked, hash-verified bytes"))
record("R4", "T decoder whose bound uses a different metric (Chamfer vs Hausdorff)", "reject ineligible-plan",
       lambda: expect_reject("ineligible-plan", lambda: elig_ws(plan_for(41, fairing(rt_chamfer)), rts=RT_WS_PLUS)))

y_pub_fast = P.latent_decode(latent_obj, "dev:publisher", 125)
eps_fast = P.hausdorff(y_pub_fast, fairing_ref)
ok_fast, tot_fast = bound_from_sender(pred_fairing, {"measured": P.um_to_mm(eps_fast)}, rt_fast)
record("R5", "Faster T decoder: eligible, but its bound does not fit", "acceptance fails; repair",
       lambda: (f"{num_value(P.um_to_mm(eps_fast))} + 0.25 = {tot_fast} mm > 0.5: repair", elig_ws(
           plan_for(41, fairing(rt_fast)), rts=RT_WS_PLUS) and not ok_fast))

y_ws_fast = P.latent_decode(latent_obj, "dev:workstation", 125)
resid = plan_for(41, fairing(rt_fast), extra=[nd("fairing-fix", "residual", ["fairing"], op="xform.delta.v1",
                                                 runtime=rt_xform["digest"], base=art(encode(y_ws_fast)))])
record("R6", "Repair by residual on the T-class decode", "reject baseline-mismatch",
       lambda: expect_reject("baseline-mismatch", lambda: check_eligible(
           resid, contract, caps_ws, RT_WS_PLUS, WS, 41, {**BASE_DET, bytes(art(encode(y_ws_fast))[1]): "T"},
           delegations=[d_r1])))
lit_fix = plan_for(41, nd("fairing", "literal", payload=art(encode(fairing_ref)), emits=["fairing-surface"]))
record("R7", "Repair by literal reference geometry", "accepted",
       lambda: expect_ok(lambda: elig_ws(lit_fix), f"costs {len(encode(fairing_ref))} bytes vs {len(latent_bytes)} latent"))

record("R8", "Generated content in a region that is neither free nor reference-bound", "reject ineligible-plan",
       lambda: expect_reject("ineligible-plan", lambda: elig_ws(plan_for(41, fairing(rt_surf), extra=[
           nd("cables", "latent", op="dec.texture.v1", runtime=rt_tex["digest"], payload=art(b"cables"),
              emits=["cable-run"])]))))

record("R8b", "Generated content with no declared region, feeding the result", "reject ineligible-plan",
       lambda: expect_reject("ineligible-plan", lambda: elig_ws(plan_for(41, fairing(rt_surf), extra=[
           nd("cables", "latent", op="dec.texture.v1", runtime=rt_tex["digest"], payload=art(b"cables"))]))))

bad_free = copy.deepcopy(contract)
bad_free["free"] = ["skin-texture", "fairing-surface"]
record("R9", "Contract marks a reference-bound region as free", "reject invalid-contract",
       lambda: expect_reject("invalid-contract", lambda: lint_contract(bad_free)))

pose_prev = {"kind": "plan", "target": oid(target), "contract": oid(contract), "scope": oid(scope_all),
             "snapshot": 42, "nodes": [nd("pose", "delta", op="pose.apply.v1", runtime=rt_pose["digest"],
                                          base=art(b"pose-0"), params=bytes(70))], "roots": ["pose"]}
pose_next = dict(copy.deepcopy(pose_prev), parent=oid(pose_prev))
pose_next["nodes"][0]["params"] = bytes([1]) * 70
pose_next["nodes"][0]["base"] = art(b"pose-1")
record("R10", "Fast path: same plan shape, current snapshot", "executes without waiting for ACCEPT",
       lambda: expect_ok(lambda: check_fast_path(pose_prev, pose_next, contract, "view", 42)))
record("R11", "Fast path replayed after the receiver moved on", "reject stale-state before execution",
       lambda: expect_reject("stale-state", lambda: check_fast_path(pose_prev, pose_next, contract, "view", 43)))
reshaped = copy.deepcopy(pose_next)
reshaped["nodes"][0]["op"] = "pose.apply.v2"
record("R12", "Fast path with a changed plan shape", "reject; full negotiation required",
       lambda: expect_reject("ineligible-plan", lambda: check_fast_path(pose_prev, reshaped, contract, "view", 42)))
record("R13", "Fast path on a required-transition stream", "reject",
       lambda: expect_reject("ineligible-plan", lambda: check_fast_path(pose_prev, pose_next, contract, "edits", 42)))


# =====================================================================
# Sizes
# =====================================================================
def size(o):
    return len(encode(o))


pose_offer = msg({"type": "OFFER", "binding": binding_env, "target": oid(target), "contract": oid(contract),
                  "scope": oid(scope_all), "plan": pose_next})
pose_payload = msg({"type": "WORKTREE_PAYLOAD", "plan": oid(pose_next),
                    "chunks": [{"node": "pose", "digest": art(bytes(70)), "data": bytes(70)}]})
wt_overhead = size(FIXTURES["msg WORKTREE_PAYLOAD"]) - len(latent_bytes)
offer_ref = msg({"type": "OFFER", "binding": binding_env, "target": oid(target), "contract": oid(contract),
                 "scope": oid(scope_all), "plan": plan_ws})
sizes = {
    "objects": {k: size(v) for k, v in FIXTURES.items() if not k.startswith("msg ")},
    "messages": {k[4:]: size(v) for k, v in FIXTURES.items() if k.startswith("msg ")},
    "worktree_envelope_overhead": wt_overhead,
    "signed_approval": size(signed_approval_ws),
    "signed_receipt": size(signed_receipt_ws),
    "evidence_record": size(ev_pub),
    "full_update_control": {
        "OFFER (binding + inline 7-node plan)": size(offer_ref),
        "ACCEPT": size(FIXTURES["msg ACCEPT"]),
        "WORKTREE_PAYLOAD envelope": wt_overhead,
        "RESULT (validated)": size(FIXTURES["msg RESULT"]),
        "VALIDATION_APPROVAL": size(FIXTURES["msg VALIDATION_APPROVAL"]),
        "COMMIT_RECEIPT": size(FIXTURES["msg COMMIT_RECEIPT"]),
    },
    "pose_fast_path": {"OFFER (1-node plan)": size(pose_offer),
                       "WORKTREE_PAYLOAD envelope": size(pose_payload) - 70, "payload": 70},
    "payloads": {"latent fairing": len(latent_bytes), "literal fairing": len(encode(fairing_ref))},
    "binding_envelope": size(binding_env),
    "evidence_signing_overhead": size(sign1(KEYS[PUB], BINDING_KID, ev_r1_signed)) - size(ev_r1_signed),
    "offer_with_inline_target_and_contract": size(FIXTURES["msg OFFER"]),
    "contract_split": {
        "contract (whole, one revision)": size(contract),
        "contract-template (once per session)": size(template_obj),
        "binding envelope, whole form": size(binding_env),
        "binding envelope, split form": size(split_binding_env),
        "OFFER, whole contract inline": size(FIXTURES["msg OFFER"]),
        "OFFER, split, template inline (first use)": size(FIXTURES["msg OFFER (split, template inline)"]),
        "OFFER, split, template cached": size(FIXTURES["msg OFFER (split, template cached)"]),
        "OFFER, split, template cached, plan by id": size(msg({"type": "OFFER", "binding": split_binding_env,
                                                                 "target": target, "scope": oid(scope_all),
                                                                 "plan": oid(plan_ws)})),
    },
}
sizes["full_update_control_total"] = sum(sizes["full_update_control"].values())
sizes["pose_fast_path_overhead"] = sizes["pose_fast_path"]["OFFER (1-node plan)"] + sizes["pose_fast_path"]["WORKTREE_PAYLOAD envelope"]

measures = {
    "eps_publisher_mm": str(num_value(P.um_to_mm(eps_pub_um))),
    "bound_workstation_mm": str(total_ws),
    "true_workstation_mm": str(num_value(P.um_to_mm(true_ws_um))),
    "eps_repeater_mm": str(num_value(P.um_to_mm(eps_r1_um))),
    "clearance_workstation_mm": str(num_value(P.um_to_mm(clr_ws))),
    "eps_fast_mm": str(num_value(P.um_to_mm(eps_fast))),
    "bound_fast_mm": str(tot_fast),
    "c09_clearance_decoded_mm": str(num_value(P.um_to_mm(clr_ws29))),
    "c09_clearance_reference_mm": str(num_value(P.um_to_mm(clr_ref29))),
    "c25_additive_mm": str(add_total),
    "c25_true_mm": str(num_value(P.um_to_mm(true_h))),
    "work_key_geo_A_shared": shared_geo_a,
    "receipt_ws_status": receipt_ws["status"],
}

import stage1                                                   # noqa: E402

s1_rows, s1_binding = stage1.run(
    target, contract, scope_all, plan_ws,
    lambda p, c: check_eligible(p, c, caps_ws, RT_WS, WS, 41, BASE_DET, delegations=[d_r1]),
    PUBLISHED_BINDING_HEX)
results.extend(s1_rows)
measures["binding_matches_published_vector"] = encode(binding_env).hex() == PUBLISHED_BINDING_HEX

import contract_split                                           # noqa: E402

results.extend(contract_split.run(target, contract))
measures["split_materializes_to_whole_contract"] = materialize(template_obj, split_binding_obj) == contract

results.extend(speed_mechanisms.run())
sizes["speed_mechanisms"] = {
    "demand with receiver acceptance and subscription": size(FIXTURES["demand (receiver acceptance, subscription)"]),
    "speculation record": size(FIXTURES["speculation"]),
    "evidence with proof": size(FIXTURES["evidence (proof)"]),
    "PUSH message (target, split binding, inline plan, one chunk)": size(FIXTURES["msg PUSH"]),
    "PUSH overhead beyond the pushed bytes": size(FIXTURES["msg PUSH"]) - len(FIXTURES["msg PUSH"]["body"]["chunks"][0]["data"]),
}
measures["speculation_tokens_kept_of_48"] = speed_mechanisms.CTX["kept"]

report = {"schema_fixtures": schema_rows, "schema_negative": negative_rows, "cases": results,
          "sizes": sizes, "measures": measures,
          "digests": {"contract": short(oid(contract)), "plan_ws": short(oid(plan_ws)), "output_ws": short(out_ws),
                      "output_ph": short(out_ph), "head_ws": short(ws_consumer.head_id())}}
json.dump(report, open("report.json", "w"), indent=2, default=str)

lines = ["# ARFP v0.1 object-level check report", "",
         f"Schema fixtures valid: {sum(r['valid'] for r in schema_rows)}/{len(schema_rows)}",
         f"Malformed objects rejected: {sum(r['pass'] for r in negative_rows)}/{len(negative_rows)}",
         f"Semantic cases passing: {sum(r['pass'] for r in results)}/{len(results)}", "",
         "| Fixture | Valid | Bytes |", "| --- | --- | --- |"]
lines += [f"| {r['fixture']} | {r['valid']} | {r['bytes']} |" for r in schema_rows]
lines += ["", "| Malformed object | Result |", "| --- | --- |"]
lines += [f"| {r['case']} | {r['observed']} |" for r in negative_rows]
lines += ["", "| ID | Case | Expected | Observed | Pass |", "| --- | --- | --- | --- | --- |"]
lines += [f"| {r['id']} | {r['case']} | {r['expected']} | {r['observed']} | {r['pass']} |" for r in results]
open("report.md", "w").write("\n".join(lines) + "\n")

print("\n".join(lines[:5]))
for r in schema_rows:
    if not r["valid"]:
        print("SCHEMA FAIL", r)
for r in negative_rows:
    if not r["pass"]:
        print("NEGATIVE FAIL", r)
for r in results:
    flag = "ok " if r["pass"] else "FAIL"
    print(f"{flag} {r['id']:5} {r['observed']}")
print(json.dumps(sizes, indent=1))
print(json.dumps(measures, indent=1))
sys.exit(0 if all(r["valid"] for r in schema_rows) and all(r["pass"] for r in negative_rows)
         and all(r["pass"] for r in results) else 1)
