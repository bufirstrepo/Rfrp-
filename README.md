# ARFP — Adaptive Reconstruction Fabric Protocol

**ARFP is a protocol design for machine-to-machine state handoff in and between data centers:** moving large worktrees, KV caches and model working state between AI systems. For each receiver, a plan chooses whether to send the state, a compressed version, a delta against what the receiver already holds, or the inputs to recompute it. Any reconstructed or approximate result must pass a contract check before it is trusted, and generated parts are labeled.

It is not a consumer "your AI feels faster" pitch, and it does not make the web faster; see [Where it does not win](#where-it-does-not-win). Every speed figure below is modeled or measured offline. Nothing has run over a network yet.

## Why machine-to-machine state handoff

**The best way to move AI state flips inside real link speeds** (modeled, [speed review §6](docs/analysis/ARFP-internet-speed-review.md#6-ai-to-ai-state-where-the-planner-already-pays)). A receiver that needs a model's KV cache can be sent the cache, or the text to recompute it from. Sending wins above a break-even link speed, per H100 of receiver compute:
- about 4–29 Gb/s for an uncompressed (BF16) cache, depending on model and context length (Llama 3.1 8B and 70B, 8K–128K tokens);
- about 1–7 Gb/s with a ~4× lossy codec (CacheGen-class);
- proportionally higher for a receiver with several GPUs behind one link (33–228 Gb/s for 8 GPUs).

Real links sit on both sides of these numbers: 400 Gb/s per GPU in DGX H100-class clusters, 25 Gb/s between machines in DistServe's testbed. So no single strategy is best for every receiver.

**Choosing per receiver halved the total in the model.** With three receivers on 400, 10 and 1 Gb/s links (Llama 3.1 8B, 32K-token context), the summed time until each holds the cache was 2.51 s, against 4.90 s for the best single fixed strategy (always recompute).
- The whole gain comes from sending a lossy, class-T compressed cache to the two fast-link receivers. The slowest receiver gains nothing.
- The model leaves out the codec's encode and decode time, which flatters it.

**The contract sets the price.** If results must be exact, the same three receivers take 2.1× as long (5.36 s) when all run the sender's pinned software stack, and 15× as long (37.88 s) when they don't, because shipping the full cache is then the only exact option modeled. Recomputing is not bit-exact by default, and the known fix holds only on one pinned stack.

**The negotiation round trip that hurts on the web is cheap here.** A round trip pays for itself when it saves more than bandwidth × RTT. At 100 Gb/s and an assumed 0.1 ms RTT that is about 1.25 MB; between sites at 10 Gb/s and an assumed 30 ms RTT it is about 37.5 MB. The 32K-token Llama 3.1 8B KV cache above is 4.3 GB (arithmetic, not measured).

**Receiver state is worth a lot of bytes** (measured, [speed review §4](docs/analysis/ARFP-internet-speed-review.md#4-measured-what-receiver-state-is-worth-in-bytes)). A receiver holding the previous release of a JavaScript file needed 18–190× fewer bytes than brotli for three.js updates and 560–1,117× fewer for TypeScript patch releases. Handing a worktree to an agent that already holds an earlier version of it is the same kind of case.

**What already exists, and what ARFP would add.**
- Transfer engines already do the moving. Mooncake and LMCache move KV caches between machines, and inside a well-provisioned cluster the transfer is already a small share of serving time (Splitwise measured about 0.8% of end-to-end time at 400 Gb/s between H100 machines).
- CacheGen already adapts each chunk of a KV cache between encoding levels and text-plus-recompute as bandwidth changes.
- ARFP is not meant to replace them. Its proposed contribution is the layer above them: one contract, evidence and provenance format that decides when lossy or recomputed state may be trusted and labels what was generated. It matters most for handoffs that cross operators or trust boundaries, such as agent-to-agent handoff or federated inference, where today's systems have no common format. None of this has been demonstrated on a network.

**Next step:** run the KV-cache handoff over real links against LMCache/CacheGen-style transfer ([proposal](docs/proposals/ARFP-ai-state-handoff-network-test.md)).

## Candidate data-center use cases

Reviewed in [Candidate data-center use cases](docs/proposals/ARFP-data-center-use-cases.md). None is demonstrated. Each is checked against three conditions: the state is big, the link is the bottleneck, and the receiver may accept rebuilt state under a contract.

| Candidate | Fit | Note |
|---|---|---|
| Prefill-to-decode KV-cache handoff | Partial | Solved inside clusters (Splitwise, DistServe, Mooncake). ARFP would add per-receiver choice and contract-checked compression where links between pools are slower |
| Cross-request cache reuse | Best fit, and the most crowded | LMCache, CacheGen and CacheBlend already do it. ARFP would add binding to model and software stack, per-consumer acceptance, and scoping of who may reuse whose cache |
| Failover and migration | Check, not speed | Llumnix, DéjàVu, SpotServe and vLLM already move or recompute state. ARFP's value would be verifying rebuilt state before it is trusted |
| Checkpoint and model-delta sync | Weak | Mostly exact bytes that compression and exact deltas already handle |
| Small state or compute-bound work | Does not fit | The negotiation costs more than it saves |

## Current status (2026-10-11)

**What exists:**
- A research architecture and an experimental specification.
- An **executable object-level conformance kit**:
  - a CDDL schema for deterministic CBOR with COSE signatures;
  - 95 passing cases, with every one of the C01–C28 scenarios covered by at least one case;
  - gate zero (a publisher-signed binding checked before any planning);
  - repair, crash recovery from real process kills, and multi-hop provenance;
  - the contract split.
- A byte benchmark on real data, a first-order time model (including KV-cache send versus recompute), and an engineering review of where this approach can and cannot speed up transfers.

**What does not exist:**
- a networked sender or receiver;
- a transport;
- a second independent implementation;
- a network benchmark;
- any measured end-to-end speedup, demonstrated novelty, or Internet-scale deployment.

## Where it does not win

These are documented boundaries, not footnotes. Each is in the [speed review](docs/analysis/ARFP-internet-speed-review.md), with the full pre-registered list in [§10](docs/analysis/ARFP-internet-speed-review.md#10-negative-cases-to-publish-pre-registered).

- **Web pages and consumer downloads.** ARFP v0.1 as specified is slower than HTTP with RFC 9842 compression dictionaries in the common case. Its OFFER/ACCEPT exchange adds a round trip that dictionaries don't need (modeled: 113 vs 56 ms for a three.js update at 100 Mbit/s, 56 ms RTT, warm connection; sending the whole file takes 74 ms). On cold or slow links it still beats the whole file (113 vs 234 ms). Typical page loads are bound by round trips and CPU, not bytes.
- **Pushing deltas.** A push profile would at best tie a pub/sub channel carrying dictionary deltas, and trails it by the cost of hashing the output on large objects until that check is incremental.
- **Inside a uniform, well-provisioned cluster.** Above about 30 Gb/s per H100 of receiver compute, shipping the state wins outright, and existing engines already make that cheap. A planner has little left to decide there; only the contract and evidence layer would remain.
- **The slowest receiver.** In the three-receiver model it gains nothing from per-receiver choice.
- **Recompute treated as exact.** Default inference kernels are not batch-invariant: Thinking Machines got 80 different completions out of 1,000 at temperature 0.
- **Small frequent updates and novel content.** Control bytes dominate tiny updates (94% overhead for a 70-byte pose, even on the v0.1 fast path), and no representation helps when the receiver holds nothing related.

## Start here

| File | What it is | Maturity |
|---|---|---|
| [Working analysis](docs/analysis/ARFP-analysis-2026-10-11.md) | Engineering record: schema map, identity and encoding rules, design choices and what each forces, Stage-1 results, contract split, next work, full CDDL | Checked: the kit-derived numbers (§§6, 8, 10, 15) reproduce from `kit/` |
| [Speed review](docs/analysis/ARFP-internet-speed-review.md) | Where the transfer set can and cannot make transfers faster: AI-state send versus recompute (§6), the push-profile design, ranked domains, pre-registered negative cases, Stage 4/5 hypotheses | Measured, modeled and sourced; checked twice by a separate agent |
| [AI-state network test](docs/proposals/ARFP-ai-state-handoff-network-test.md) | Proposed next step: KV-cache handoff over real links against LMCache/CacheGen-style transfer, with pre-registered pass and kill criteria | Proposal; not run |
| [Data-center use cases](docs/proposals/ARFP-data-center-use-cases.md) and [their sources](docs/research/use-cases/data_center_use_case_sources.md) | Three strong and two weaker candidate uses, each checked against the fit test and against what existing systems already do | Candidates; not demonstrated |
| [Schema kit](kit/README.md) | `arfp-v0.1.cddl`, the reference checker, 95 cases, mutation check, benchmark and model | Runs: `python3 run_checks.py` |
| [Contract split](docs/handoffs/ARFP-contract-split-handoff.md) and [implementation notes](docs/handoffs/ARFP-contract-split-implementation.md) | Session contract template plus per-revision binding; what was built, measured, and changed from the proposal | Built and tested (T1–T14) |
| [Complete concept handoff](docs/architecture/ARFP_Concept_Handoff_v0.1_2026-10-11.md) | Full architecture, mathematical model, authority and evidence rules, repeater fabric, six-stage plan, C01–C28 | Original, preserved byte for byte |
| [Experimental draft v0.1](docs/specification/Adaptive_Reconstruction_Protocol_v0.1.md) | Narrow assembly-component profile (`arf-experiment/0.1`, JSON/JCS) with worked transcripts | Original, preserved byte for byte |
| [Profile compatibility](docs/PROFILE_COMPATIBILITY.md) | How the handoff, the experimental draft and the kit relate, and the decisions still open | Editorial |
| [Roadmap](docs/ROADMAP.md) | Stages, gates and current status | Editorial |
| [Standards reuse](docs/STANDARDS_REUSE.md) | Canonical encoding, signatures and receipts mapped to existing specifications | Editorial |
| [Research notes](docs/research/speed-review/) | Quote-backed source notes behind the speed review | Research notes |
| [External review](docs/reviews/2026-10-11_external_review.md), [concept notes](docs/sources/conversation_concept_notes.md) | Review and originating design notes | Preserved sources |
| [Import verification](docs/IMPORT_VERIFICATION.md), [source manifest](SOURCE_MANIFEST.json) | What was checked when material was added; file provenance and SHA-256 | Verification records |

For the overall design, read the handoff first. To run or extend the object model, read the working analysis and then the kit. To implement the narrow JSON profile, read the compatibility guide and then the experimental draft.

The experimental draft and the kit use different encodings: JSON with RFC 8785 canonicalization in the draft, deterministic CBOR with COSE signatures in the kit. Choosing one for the next profile is an open decision ([profile compatibility](docs/PROFILE_COMPATIBILITY.md)). The documents keep their original titles and versions; they are not interchangeable specifications.

## Run the kit

```
cd kit
pip install -r requirements.txt
python3 run_checks.py        # exit 0: 38/38 fixtures valid, 11/11 malformed objects rejected, 95/95 cases pass
python3 mutation_check.py    # exit 0: all 7 removed guards caught (six turn their cases red, one crashes the run)

python3 bench/speed_model.py # offline, standard library only: regenerates the speed review's modeled numbers

pip install -r bench/requirements.txt
python3 bench/delta_bench.py # optional: re-measures the deltas (needs the npm CLI and registry the first time)
```

The kit checks objects and rules, not performance:
- Its outputs are toy integer geometry, simulated decoders and an exact byte profile.
- It has no transport.
- The second encoder in its encoding check is a library (cbor2), not an independent implementation of the spec.

## How it works

**Purpose:** negotiate how a receiver reconstructs a versioned object from existing state and newly delivered information, then validate the actual result before committing it locally.

ARFP is a proposed application-layer protocol for mixed-representation delivery. Its **Data Worktree** is a dependency DAG that can combine content references, deltas, procedural recipes, learned latents, residual corrections, and literal bytes. A receiver-specific Plan chooses eligible work under an explicit Contract for fidelity, dependencies, resources, evidence, and authority. Authorized repeaters extend the concept with caching, partial materialization, shared computation, and plan rewriting.

1. **Negotiate:** bind the logical Target and acceptance Contract; inspect receiver capabilities and relevant state.
2. **Plan:** choose representations, dependencies, and execution placement for this receiver.
3. **Materialize:** obtain missing assets and run the eligible reconstruction operations.
4. **Validate:** check the concrete output using the required reference, metric, and trusted evidence path.
5. **Repair or commit:** preserve reusable work on failure; install only an accepted output within the receiver's authority.

Plan acceptance authorizes an eligible attempt. It does not guarantee that execution will succeed. A digest identifies bytes; a signature authenticates a statement; neither independently establishes fidelity.

| Identity | Names |
|---|---|
| Target | Logical object and publisher revision |
| Contract | Bound acceptance requirements (whole, or a session template plus a per-revision binding) |
| Plan | Receiver-specific reconstruction DAG and execution choices |
| Realized Output | Concrete bytes or canonical state actually produced |

Different receivers may have different accepted realizations. Approximate results keep distinct content identities. A patch requires a matching exact baseline; the handoff also allows an explicitly defined semantic applicability rule, which the kit does not implement.

## What the experimental draft specifies

The working wire identifier is `arf-experiment/0.1`. The profile is `assembly-component-v1`, with an exact `component-state-v1` record and an `indexed-triangle-mesh-um-v1` display asset checked against an authoritative reference mesh.

It specifies full-state updates, constrained field replacements, mesh references, a restricted RFC 8785 canonical JSON data model, SHA-256 identities, bounded stream framing, reservation leases, resource ceilings, repair negotiation, and an atomic local installation rule. The examples cover an accepted 5-micrometre display deviation, a rejected 11-micrometre deviation under a 10-micrometre bound, and repair using the exact reference mesh.

These examples exercise an acceptance mechanism. They do not implement a general mixed-operation DAG, neural decoding, repeaters, signed fabric receipts, multiwriter collaboration, or large-dataset replication.

## Repeater fabric direction

An authorized repeater may cache validated artifacts, execute eligible operations, share work across clients, and emit receiver-specific Plans under the original Target and Contract. Rewrites must preserve authority and acceptance requirements. Artifact identity, evidence applicability, and permission to use an artifact remain separate checks.

Cancellation follows live demand: if one receiver changes its interest, shared work still needed by another receiver stays live. Required-transition streams are retained. A camera jump is only a demonstration of changed application interest; cameras are absent from the core protocol definition.

The kit checks these rules at object level (delegation narrowing, plan rewriting, shared-demand cancellation, supersession, multi-hop evidence). No repeater runtime exists.

## Evidence required before stronger claims

| Requirement | Status |
|---|---|
| Independently implemented endpoints agree on encoding, acceptance, failures and durable outcomes | Not started. The kit is one implementation; its encoding check uses a library as the second encoder |
| The one-repeater/two-receiver demonstration passes shared-work and replacement cases C15–C18 | The rules pass at object level; no runtime repeater exists |
| Benchmarks compare conventional, delta, content-addressed, fixed-hybrid and ARFP transfer with equivalent fidelity | Compression sizes measured and a first-order model built; no network benchmark. The first proposed network test is the [AI-state handoff](docs/proposals/ARFP-ai-state-handoff-network-test.md) |
| Accounting covers all delivery links, dependencies, planning, validation, compute, memory, retries, failed attempts and discarded work | Partly specified (the speed review's Stage 4/5 metrics); not yet run |
| At least one negative result identifies a workload where ARFP overhead outweighs its benefit | Pre-registered in the speed review (small frequent updates, novel content, verification cost on large objects); the model already shows v0.1 losing to HTTP with dictionaries on warm links |

AI is optional planner machinery. Nothing in this repository supports a claim that AI reconstructs arbitrary missing information, that tiny transfers represent full dataset replication, or that the architecture itself proves novelty.

## Project boundaries

One designated publisher owns revisions in the initial profile. Receivers commit locally; successful reconstruction does not grant source write authority. Multiwriter telepresence remains separate future work, and no telepresence document is imported into this repository.

The owner-controlled material is all rights reserved; see [LICENSE](LICENSE). No open-source or patent license is granted. A permissive or reciprocal license remains an explicit owner decision. The original documents are preserved without silently rewriting their requirements; reconciliation and follow-up decisions are recorded separately.
