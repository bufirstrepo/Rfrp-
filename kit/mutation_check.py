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
