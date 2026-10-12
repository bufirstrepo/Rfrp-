"""Mutation check: do the tests have teeth?

Removes one critical guard at a time from a scratch copy of the kit, reruns run_checks.py, and
confirms the cases that should catch it turn red. Exit code 0 means every removal was caught.

    python3 mutation_check.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent

# (guard, file, original text, mutated text, cases that must fail; None = the run must crash)
MUTATIONS = [
    ("Binding's contract-id check", "arfpkit/gate.py",
     '    if not same(b["contract"], oid(contract)):\n'
     '        raise Reject("integrity-failure", "binding names a different contract")\n', "",
     {"G4"}),
    ("Accepted-checker rule for evidence", "arfpkit/provenance.py",
     "            if party not in checkers:", "            if False:",
     {"C27c"}),
    ("Torn-tail detection in the journal", "arfpkit/journal.py",
     "            if len(body) < n or zlib.crc32(body) != crc:", "            if False:",
     None),
    ("Evidence reuse keyed by input digests", "arfpkit/engine.py",
     'if cached is not None and same(cached["inputs"], inputs):', "if cached is not None:",
     {"C07b", "C08b", "C10a", "C10b"}),
    ("Staged-bytes check before commit", "arfpkit/journal.py",
     '        if not self.staged_ok(rec["output"]):', "        if False:",
     {"C21-D"}),
    ("Split binding's template-digest check", "arfpkit/gate.py",
     '        if rules.get("kind") != "contract-template" or not same(oid(rules), tid):',
     '        if rules.get("kind") != "contract-template":',
     {"T4"}),
    ("Unknown-predicate check on binding overrides", "arfpkit/template.py",
     '            if pid not in by_id:\n                raise Reject("invalid-contract", '
     'f"binding sets {field} for {pid}, which the template lacks")\n',
     '            if False:\n                pass\n',
     {"T6"}),
    ("Tighten-only rule for a receiver's own bounds", "arfpkit/speed.py",
     '        if num_value(bound) > num_value(metric_bound(contract, pid)["threshold"]):', "        if False:",
     {"F3"}),
    ("Verified-prefix check on a speculation record", "arfpkit/speed.py",
     '    if spec["accepted"] != kept:', "    if False:",
     {"P4"}),
    ("Recomputation check on proof evidence", "arfpkit/speed.py",
     '    if not proof_matches(pr["data"], recompute(runtime, inp, output)):', "    if False:",
     {"V2"}),
    ("Exact-base check on a push", "arfpkit/speed.py",
     '    if not same(body["base"], head_output):', "    if False:",
     {"U2"}),
    ("Pushed bytes checked against the digest they carry", "arfpkit/speed.py",
     '                or not same(art(ch["data"]), ch["digest"]):', "                or False:",
     {"U8"}),
    ("Pushed digest checked against the plan's payload", "arfpkit/speed.py",
     'or not same(payloads[ch["node"]], ch["digest"])', "or False",
     {"U11"}),
    ("Proof's input binding, checked before recomputation", "arfpkit/speed.py",
     '    if not same(pr["input"], inp):\n        raise Reject("validation-failure", "proof is for a different input")\n',
     "",
     {"V3"}),
    ("Only metric bounds can be tightened by a receiver", "arfpkit/speed.py",
     '    if p is None or p["kind"] != "metric-bound" or "threshold" not in p:',
     '    if p is None or "threshold" not in p:',
     {"F7"}),
    ("A node that declares no error is unbounded", "arfpkit/speed.py",
     '                err, limit = declared_error(n, p), effective_threshold(contract, demand, p["id"])',
     '                err, limit = declared_error(n, p) or 0, effective_threshold(contract, demand, p["id"])',
     {"F8"}),
    ("Opt-in rule for unverified provisional output", "arfpkit/speed.py",
     '    if "T" not in accepts:', "    if False:",
     {"P2"}),
    ("Contract permission for unverified provisional output", "arfpkit/speed.py",
     '    if "T" not in contract["determinism"]["evidence-transfer"]:', "    if False:",
     {"P7"}),
    ("Speculation record bound to the plan", "arfpkit/speed.py",
     '    if not same(spec["plan"], oid(plan)):', "    if False:",
     {"P8"}),
    ("Speculation record bound to the provisional state", "arfpkit/speed.py",
     '    if not same(spec["provisional"], art(provisional_state)):', "    if False:",
     {"P8"}),
    ("Speculation record bound to the draft", "arfpkit/speed.py",
     '    if not same(spec["drafted"], art(bytes(draft))):', "    if False:",
     {"P8"}),
    ("Committed output is the verified output", "arfpkit/speed.py",
     '    if not (same(spec["output"], art(bytes(final))) and same(spec["output"], art(bytes(output)))):',
     "    if False:",
     {"P8"}),
    ("Proof evidence's checker is its signer", "arfpkit/speed.py",
     '    if ev.get("checker") != party:', "    if False:",
     {"V8"}),
    ("Proof evidence must report a pass", "arfpkit/speed.py",
     '    if not ev["pass"]:', "    if False:",
     {"V8"}),
    ("Supported proof scheme", "arfpkit/speed.py",
     '    if pr is None or pr["scheme"] != PROOF_SCHEME:', "    if pr is None:",
     {"V8"}),
    ("Subscriber's own classes applied to a push", "arfpkit/speed.py",
     "    check_output_classes(plan, own, runtimes, consumer, contract)\n", "",
     {"U12"}),
    ("Subscriber's own bounds applied to a push", "arfpkit/speed.py",
     "    check_plan_bounds(plan, contract, own)\n", "",
     {"U12"}),
    ("Push binding's template matches the subscription", "arfpkit/speed.py",
     '    if not same(res["template"], sub["template"]):', "    if False:",
     {"U13"}),
    ("Pushed plan eligible under the revision's contract", "arfpkit/speed.py",
     "    eligible(plan, contract)\n", "",
     {"U13"}),
]


def main():
    work = Path(tempfile.mkdtemp(prefix="arfp-mut-"))
    caught_all = True
    print("| Guard removed | Expected | Observed | Caught |")
    print("| --- | --- | --- | --- |")
    try:
        for guard, rel, old, new, expect in MUTATIONS:
            copy = work / "kit"
            shutil.rmtree(copy, ignore_errors=True)
            shutil.copytree(KIT, copy, ignore=shutil.ignore_patterns("__pycache__", "report.*", "vectors",
                                                                     "mutation_check.py"))
            f = copy / rel
            src = f.read_text()
            if src.count(old) != 1:
                raise SystemExit(f"mutation target for '{guard}' not found exactly once in {rel}")
            f.write_text(src.replace(old, new))
            p = subprocess.run([sys.executable, "run_checks.py"], cwd=copy, capture_output=True, text=True)
            report = copy / "report.json"
            if report.exists():
                red = sorted(c["id"] for c in json.loads(report.read_text())["cases"] if not c["pass"])
                observed = f"exit {p.returncode}; failing {red}"
                caught = p.returncode != 0 and expect is not None and expect <= set(red)
            else:
                last = (p.stderr.strip().splitlines() or ["?"])[-1]
                observed = f"exit {p.returncode}; run crashed: {last[:80]}"
                caught = p.returncode != 0 and expect is None
            wanted = "run crashes" if expect is None else ", ".join(sorted(expect)) + " fail"
            caught_all &= caught
            print(f"| {guard} | {wanted} | {observed} | {caught} |")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0 if caught_all else 1


if __name__ == "__main__":
    sys.exit(main())
