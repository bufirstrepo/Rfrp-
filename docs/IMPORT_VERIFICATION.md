# Repository import verification

This file records what was checked each time material was added to the repository. No import executes an ARFP network protocol.

- [Import 1: handoff pack](#import-1-handoff-pack): concept handoff, experimental draft, external review, concept notes.
- [Import 2: schema kit, analysis and speed review](#import-2-schema-kit-analysis-and-speed-review): the executable kit, the working analysis, the speed review and its research notes, and the contract split.
- [Import 3: speed mechanisms](#import-3-speed-mechanisms): the design note, the kit's rules and cases for four mechanisms, the model of all six, and the small-model run.

## Import 1: handoff pack

**Checked:** 2026-10-11.  
**Scope:** source preservation, document navigation, and the supplied numerical transcript.

### Source preservation

- The complete concept handoff was copied byte-for-byte from the document produced in the project owner's design session.
- The experimental draft was copied byte-for-byte from the project owner's attached Markdown file.
- Their byte lengths and SHA-256 digests are recorded in [SOURCE_MANIFEST.json](../SOURCE_MANIFEST.json).
- The external review was transcribed from the supplied message, with a provenance wrapper. It is labeled review material.
- Earlier repeated concept messages were normalized into one source compilation. The compilation identifies its editorial treatment and points to the handoff's corrections.
- README, compatibility, roadmap, and standards notes are new editorial material. They do not silently amend the imported originals.

### Transcript checks performed during import

A local Python check parsed all **18 JSON blocks** in the experimental draft and verified their values fall within the draft's printable-ASCII/safe-integer data model. Compact, sorted serialization was used only for this restricted fixture domain; it is not offered as a general RFC 8785 implementation.

The check recomputed the three Plan digests and three UPDATE payload digests; reconstructed the exact target record from the permitted field replacements; matched the baseline and target digests; checked the declared mesh asset digests and sizes; and verified each ACCEPT dependency partition covers its Plan exactly.

| Transcript | Maximum squared vertex error | Bound squared | Expected result checked |
|---|---|---|---|
| `update-1042` | 25 square micrometres | 100 square micrometres | Installed; exact target revision 28 |
| `update-1042-bad` | 121 square micrometres | 100 square micrometres | Needs repair; revision 27 retained |
| `update-1043` | 0 square micrometres | 100 square micrometres | Installed; exact target revision 28 |

The fixture meshes' identical topology, matching vertex counts, and nonzero triangle areas were checked. The repair binds the failed attempt, uses the exact target state, and does not loosen the original tolerance. All checks above passed during preparation.

### Limits of this verification

No transport exchange, sender/receiver implementation, crash recovery execution, independent endpoint interoperability, neural decoder, general DAG evaluator, repeater runtime, or performance benchmark was run. C01–C28 remained proposed conformance scenarios at this import (Import 2 adds executable object-level cases). The computed transcript values substantiate those examples only.

Relative document links and fenced JSON blocks are checked as package QA. Remote GitHub transfer is verified separately when the repository commit is created; this file does not claim a transfer occurred merely because a package exists locally.

## Import 2: schema kit, analysis and speed review

**Checked:** 2026-10-11, on a clean copy of the repository tree, in a fresh Python virtual environment installed only from `kit/requirements.txt` and `kit/bench/requirements.txt`.  
**Scope:** source preservation, reproduction of every kit output, and document links. Still no network protocol.

### What was added

| Path | Contents | Treatment |
|---|---|---|
| `docs/handoffs/ARFP-contract-split-handoff.md` | Contract-split proposal supplied by the project owner | Byte-for-byte copy |
| `docs/handoffs/ARFP-contract-split-implementation.md` | What was built from that proposal, what was measured, and where it departs | New |
| `docs/analysis/ARFP-analysis-2026-10-11.md` | Working analysis and engineering record | Produced in the working session; edited to point at repository paths and to correct the claims the pre-publication check found |
| `docs/analysis/ARFP-internet-speed-review.md` | Speed review | Produced in the working session; renamed without spaces, edited to point at repository paths, one conversational phrase removed, one hand estimate labeled as such |
| `docs/research/speed-review/` | Four research notes behind the speed review, plus an index | Notes produced in the working session; access notes reworded as neutral provenance and two pre-publication to-dos turned into stated caveats; index new |
| `kit/` | Schema kit: CDDL, reference checker, cases, vectors, reports, benchmark and model | Copied without caches; [`kit/SHA256SUMS`](../kit/SHA256SUMS) lists every file |
| `README.md`, `docs/ROADMAP.md`, `docs/PROFILE_COMPATIBILITY.md`, `docs/STANDARDS_REUSE.md`, this file, `SOURCE_MANIFEST.json` | Editorial | Updated to the current state |

Not imported: a spatial telepresence handoff supplied earlier in the working session, probably the telepresence document the external review refers to (kept out by the repository boundary on telepresence), and earlier ARFP drafts and vector sets from other tools, which the consolidated handoff and the kit supersede.

### Source preservation

- The four originals from Import 1 are unchanged; their SHA-256 digests still match [SOURCE_MANIFEST.json](../SOURCE_MANIFEST.json). `LICENSE` is byte-identical to the handoff pack's.
- The contract-split handoff matches the uploaded file byte for byte; its digest is in the manifest.

### Reproduction from a clean copy

| Check | Command, in `kit/` | Result |
|---|---|---|
| Schema and cases | `python3 run_checks.py` | Exit 0. 38/38 fixtures valid, each against its own rule and the top-level union; 11/11 malformed objects rejected; 95/95 cases pass. `report.md`, `report.json` and all 38 vectors byte-identical to the committed files |
| Published binding vector | case G1 | The 253-byte binding envelope regenerated byte for byte from RFC 8032 test key 1 |
| Mutation check | `python3 mutation_check.py` | Exit 0. All 7 guard removals caught: six turn the expected cases red, and removing torn-tail detection crashes the run, which is the expected signal for that guard |
| Speed model | `python3 bench/speed_model.py` | Exit 0. `speed_model.md` and `speed_model.json` byte-identical to the committed files |
| Delta benchmark | `python3 bench/delta_bench.py` | Exit 0, run on locally cached copies of the npm release tarballs. All 450 non-timing values across 19 release pairs (sizes, ratios, file hashes, encoder settings and labels) match the committed `delta_results.json`; only the timings differ, as expected |
| Links | A link checker using GitHub heading-anchor rules | All 84 relative links and heading anchors in the repository's Markdown files resolve. External links were not fetched for this import |

### Pre-publication check

A separate agent that had not seen the work checked the assembled tree against the kit's outputs, the code and the originals, reran the kit, and searched for anything that should not be public. It found no problems with the originals, hashes, reproduction, links or secrets. It found overstated or inconsistent claims, all corrected before publication:
- C21 crash coverage described as "every record boundary"; C16 marked as fully passing although only its retirement half is checked.
- The working analysis described as reproducing every number from the kit; the speed model described as producing one estimate it does not compute.
- The kit's protocol name described as absent; receipts described as naming the output directly; a library cross-check described as independent.
- Session-specific wording and two unresolved to-dos in the research notes; the telepresence document listed both as not supplied and as supplied.

It also noted that each kit run left temporary folders behind; `stage1.py` now removes them.

### Limits of this verification

- The kit is one implementation. Its encoding cross-check (C28) uses a library, cbor2, as the second encoder; that is not the independent implementation the roadmap requires.
- One CDDL tool (pycddl 0.6.4), with the deviations listed in the kit README.
- The C21 crash cases kill worker processes with SIGKILL after the approval, head and receipt records and partway through the head write. No crash point sits between a conflict or abort record and its receipt, so that recovery branch is not exercised. None of this models power loss.
- The benchmark measures compression sizes and local timings; every time in the speed review is modeled. No network measurement was made.
- Remote GitHub transfer is verified separately when the repository commit is created.

## Import 3: speed mechanisms

**Checked:** 2026-10-12, on a clean copy of the repository tree.  
**Scope:** reproduction of every deterministic kit output, the mutation check, document links, and two checks by a separate agent. Still no network protocol.

### What was added

| Path | Contents | Treatment |
|---|---|---|
| `docs/proposals/ARFP-speed-mechanisms.md` | Six ways to make AI state handoff faster: protocol changes, kit cases, modeled gains, where each loses, prior work | New |
| `kit/arfpkit/speed.py`, `kit/speed_mechanisms.py` | Rules and 37 cases for fidelity per receiver (F1–F8), speculative start (P1–P8), proof evidence (V1–V8) and push (U1–U13) | New |
| `kit/arfp-v0.1.cddl`, `kit/run_checks.py`, `kit/mutation_check.py` | Schema additions for the four mechanisms; four fixtures, two malformed objects, 22 more guards for the mutation check | Extended |
| `kit/bench/ideas_model.py` and its outputs | First-order model of all six mechanisms | New |
| `kit/bench/spec_start_toy.py`, its outputs and `requirements-toy.txt` | The verification step of speculative start on a small transformer trained for the purpose | New |
| `README.md`, `kit/README.md`, `docs/ROADMAP.md`, the working analysis's note on later additions, this file, `SOURCE_MANIFEST.json` | Editorial | Updated to the current state |

The originals are unchanged; their SHA-256 digests still match the manifest. The small model trains on those originals only, so its corpus is pinned by the same digests.

### Reproduction from a clean copy

In a fresh Python virtual environment installed only from `kit/requirements.txt`, except the small-model run, which needs `kit/bench/requirements-toy.txt`:

| Check | Command, in `kit/` | Result |
|---|---|---|
| Checksums | `sha256sum -c SHA256SUMS` | All 75 kit files match |
| Schema and cases | `python3 run_checks.py` | Exit 0. 42/42 fixtures valid; 13/13 malformed objects rejected; 132/132 cases pass. `report.md`, `report.json` and all 42 vectors byte-identical to the committed files. The 95 cases that predate the speed mechanisms give the same results as before, except that C28, C28b and C28c now count 42 fixtures |
| Mutation check | `python3 mutation_check.py` | Exit 0. All 29 guard removals caught: 28 turn the expected cases red, and removing torn-tail detection crashes the run, the expected signal for that guard |
| Models | `python3 bench/speed_model.py`, then `python3 bench/ideas_model.py` | Exit 0. All four outputs byte-identical to the committed files |
| Small-model run | `python3 bench/spec_start_toy.py` | Run twice on a 2-core CPU machine (about 17 minutes each), with identical training losses at every logged step and identical acceptance figures; not rerun from the clean copy. `--render` rebuilds `spec_start_toy.md` from the JSON byte for byte |
| Links | A link checker using GitHub heading-anchor rules | All 125 relative links and heading anchors resolve. Of the external sources, the arXiv abstracts (Lynx, QuantSpec, TOPLOC, speculative decoding), the Kafka and RTI documentation and the EPFL record were fetched and checked against the quotes used |

### Checks by a separate agent

A separate agent that had not seen the work checked it twice, against the code, the outputs and the sources. Everything it found was fixed before publication.

The first check found:
- A PUSH could not carry a real new revision, and its bytes were not bound to the plan. Each push now carries that revision's signed binding, which passes gate zero, and its bytes must match the plan (U1, U4, U8, U9, U11).
- Two cases did not test what they claimed: the forged-binding push never reached gate zero (U4), and the tightened bound raised no real validation failure (F4).
- Fidelity and reproducibility were conflated. Bounds now set fidelity and classes set reproducibility (F2, F6).
- Unverified use of provisional output needed no contract permission (P5, P6).
- Proof evidence skipped the usual evidence checks and recomputed before the cheap ones (V3, V6, V7).
- The small model's corpus changed whenever the repository's documents did, its held-out prompts overlapped, and its sizes left out quantization scales.
- The note claimed novelty for speculative start that Lynx (July 2026) already covers. It also credited the proof for a speedup that comes from the parallel pass, and misdescribed staleness and push sizes.

The second check found:
- A receiver could loosen a minimum (the clearance invariant) by setting a smaller number. Only metric bounds can now be tightened (F7).
- A push ignored the subscriber's own acceptance (U12).
- The small-model note said the one-pass check and step-by-step decoding run the same arithmetic. They round differently; the run now measures by how much.
- Several rules had no case that failed without them. Each now has one (F8, P2, P7, P8, V8, U13), and the mutation check removes each rule in turn.
- The model's verification pass left out attention, so "never slower" became "at most 0.3% slower".
- Checksums and counts were stale.

### Limits of this verification

- The kit's speed-mechanism cases use deterministic stand-ins (a hash-based generator, hash-derived activations); they test protocol rules, not model behavior.
- The small-model run measures the verification step and acceptance on a sub-million-parameter model. It measures no transfer and no timing, and it ran on one machine; its figures may differ on another.
- Every speed figure in the design note is modeled. No production model, GPU or network was used.
