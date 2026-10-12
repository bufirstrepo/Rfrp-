# ARFP v0.1 schema kit

Object-level schema and conformance checks for the Adaptive Reconstruction Fabric Protocol (ARFP),
plus executable Stage-1 cases: gate zero (the publisher-signed binding), failure handling and repair,
crash recovery, multi-hop provenance, the contract split (session template plus per-revision binding), and four
speed mechanisms (fidelity per receiver, speculative start, proof-based evidence, push on a subscription).
It checks objects and rules, not performance: outputs are toy
integer geometry, simulated decoders and an exact byte profile, and there is no transport.

## Contents

- `arfp-v0.1.cddl`: the schema (CDDL, RFC 8610, 420 lines) for deterministic CBOR (RFC 8949 section 4.2.1)
- `arfpkit/canon.py`: deterministic CBOR encoder and strict decoder, ids, exact decimals
- `arfpkit/cose.py`: COSE_Sign1 (RFC 9052) with Ed25519; the publisher uses RFC 8032 test key 1,
  other fixture keys derive from fixed labels, so every signature reproduces byte for byte
- `arfpkit/gate.py`: gate zero; allow-listed key, signature, payload kind, publisher, ids, expiry,
  checked in that order before any planning
- `arfpkit/rules.py`: the semantic rules the CDDL cannot express (eligibility, evidence transfer,
  composition, delegation, supersession, fast path, forwarding)
- `arfpkit/profile.py`: the toy profile `scene.assembly.v1`
- `arfpkit/engine.py`: executor for the exact profile `bytes.exact.v1`; validates at emission, repairs
  with prebound fallbacks over the failed node's cone, reuses evidence only when its inputs are unchanged
- `arfpkit/journal.py`: write-ahead commit journal and crash recovery; runs as a worker process that is
  killed with SIGKILL at injected crash points
- `arfpkit/provenance.py`: signed evidence bundles across hops, attestations, and rebuilding the
  provenance chain from a receipt
- `arfpkit/template.py`: the contract split; a session contract template plus a per-revision binding
  materialize into the ordinary contract, so its id and every downstream object stay the same
- `arfpkit/speed.py`: rules for the speed mechanisms: a receiver's own acceptance (tighten, never loosen),
  the commit rule for output drafted on provisional state, proof-based evidence, and pushes on a standing
  subscription
- `run_checks.py`: builds the scenario, validates every fixture, runs every case, writes reports
- `stage1.py`: the 40 Stage-1 cases (G1-G10, C04, C07, C08, C10, C21, C27), called by `run_checks.py`
- `contract_split.py`: the 14 contract-split cases (T1-T14), called by `run_checks.py`
- `speed_mechanisms.py`: the 37 speed-mechanism cases (F1-F8, P1-P8, V1-V8, U1-U13), called by `run_checks.py`
- `mutation_check.py`: removes 29 critical guards one at a time and confirms the cases that should
  catch each removal fail
- `vectors/*.cbor`: the 42 fixtures as canonical CBOR test vectors
- `report.json`, `report.md`: results of the last run
- `bench/delta_bench.py`: what receiver state is worth on real data. Downloads consecutive releases of
  react-dom, three.js and TypeScript from the npm registry and measures brotli, zstd, patch-from deltas
  (zstd -19 and -3), a content-aware delta, line overlap, decode and SHA-256 times. Writes
  `bench/delta_results.json`. Needs the npm CLI and network on first run (tarballs are cached in `bench/.cache/`, not
  shipped); sizes are deterministic, timings are not
- `bench/speed_model.py`: offline model that turns the measured sizes into time (round trips, slow start,
  hashing), prices ARFP control bytes, sizes receiver-state summaries, and models KV-cache send versus
  recompute. Writes `bench/speed_model.md` and `bench/speed_model.json`
- `bench/ideas_model.py`: offline first-order model of the six speed mechanisms, reusing the KV-cache
  model. Writes `bench/ideas_model.md` and `bench/ideas_model.json`
- `bench/spec_start_toy.py`: trains a small byte-level transformer on the repository's hash-pinned
  documents (about 15 minutes on 2 CPU cores, JAX), then drafts tokens on a quantized KV cache and verifies
  them against the exact cache, and measures how far the one-pass check's logits drift from step-by-step
  decoding. Writes `bench/spec_start_toy.json` and `bench/spec_start_toy.md` (`--render` rebuilds the .md from
  the .json without training); toy scale, timings and exact figures vary by machine

## Run

    pip install -r requirements.txt
    python3 run_checks.py        # exit 0: every fixture valid, every malformed object rejected, every case passing
    python3 mutation_check.py    # exit 0: every guard removal caught (its cases turn red, or the run crashes where that is the expected signal)

    python3 bench/speed_model.py # offline, standard library only
    python3 bench/ideas_model.py # offline, standard library only

    pip install -r bench/requirements-toy.txt
    python3 bench/spec_start_toy.py # optional; about 15 minutes on 2 CPU cores

    pip install -r bench/requirements.txt
    python3 bench/delta_bench.py # optional; needs the npm CLI and network the first time

Last run: 42/42 fixtures valid, 13/13 malformed objects rejected, 132/132 cases passing, 29/29 guard
removals caught. Every one of the handoff's 28 conformance cases (C01-C28) has at least one executable
case; the rest are sub-cases and rules added along the way (R1-R13, G1-G10, T1-T14, and the
speed-mechanism cases F, P, V and U). The C21 cases spawn
worker processes and need a writable temp directory.

Contract split, measured on the assembly fixture: the whole contract is 1,648 B per revision; the
template is 1,478 B once per session. An OFFER for a new revision drops from 3,310 B (whole contract
inline) to 1,838 B once the template is cached, and to 707 B when the plan is also sent by id. The
split binding grows from 253 B to 438 B because it carries this revision's expected digests and
reference.

Speed mechanisms, on the same fixture: a PUSH is 2,622 B for a 653 B payload, mostly the inline plan
(1,210 B) and the signed split binding (438 B); a demand with acceptance and subscription is 206 B, a
speculation record 282 B, and evidence with a proof 439 B.

Case G1 regenerates the published binding envelope (253 bytes) byte for byte from RFC 8032 test key 1.

## Limits

- Toy profiles and simulated decoders; no transport. The only speed-related numbers are compression sizes
  and local timings (`bench/`), plus a first-order model built on them; none is a network measurement.
- C21 crashes are process kills after the approval, head and receipt records, plus one torn head write.
  No crash point sits between a conflict or abort record and its receipt, so that recovery branch is not
  exercised. None of this is power loss: the journal does not fsync its directory on file creation, and
  disk write caches are not modeled.
- Trust anchor is a static allow-list: no key rotation, no revocation.
- The speed-mechanism cases use deterministic stand-ins: a hash-based generator for speculative start and
  hash-derived activations for proof evidence (a toy scheme in the spirit of TOPLOC, not TOPLOC). They check
  protocol rules, not model behavior. `bench/spec_start_toy.py` runs the verification step of speculative
  start on a real, small transformer; it measures no transfer and no timing.
- One CDDL tool (below), one implementation.

## Validator notes

pycddl 0.6.4 (the Rust cddl crate) needed three spellings that RFC 8610 treats as equivalent:
`null / x` instead of `x / null`, a quoted `"bytes"` key, and choices written inline inside array
types. It does not enforce `nint`, and it skips tag contents inside a type choice, so `check_numbers`
re-validates every decimal. Through the top-level `arfp-object` union it accepted a split binding that
the `binding` rule itself rejects, so every fixture and malformed object is now validated against its
own rule as well as the union. Validate with a second CDDL tool before claiming interoperability.
