# Repository import verification

This file records what was checked each time material was added to the repository. Neither import executes an ARFP network protocol.

- [Import 1: handoff pack](#import-1-handoff-pack): concept handoff, experimental draft, external review, concept notes.
- [Import 2: schema kit, analysis and speed review](#import-2-schema-kit-analysis-and-speed-review): the executable kit, the working analysis, the speed review and its research notes, and the contract split.

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
