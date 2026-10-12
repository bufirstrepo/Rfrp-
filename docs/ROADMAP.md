# Implementation and evidence roadmap

**Status:** consolidated from the handoff and the supplied review, then updated on 2026-10-11 when the schema kit, the contract split and the speed review were added, and on 2026-10-12 when the speed mechanisms were added. "Present status" below uses the vocabulary in [Claims discipline](#claims-discipline). The kit executes object-level cases; nothing here is a running network endpoint.

## Immediate decisions

1. Use the assembly-component experiment as the first executable profile, with its present wire literal and acceptance rules explicitly pinned.
2. Resolve the integration questions in [Profile compatibility](PROFILE_COMPATIBILITY.md) before claiming full ARFP conformance.
3. Keep the initial implementation single-publisher. Treat multiwriter telepresence as a separate design stream.
4. Select existing encoding and signature building blocks explicitly. The narrow experiment selects JCS (RFC 8785). The schema kit uses deterministic CBOR (RFC 8949 §4.2.1) with COSE_Sign1 and Ed25519 for bindings, delegations, evidence, attestations, approvals and receipts. One of the two must be chosen for the next profile; transparency (SCITT) integration remains a proposal.
5. Recruit an independent implementer or partner for the second endpoint. No contact or outreach has been performed.
6. **Lead with machine-to-machine state handoff.** The project is positioned around moving worktrees, KV caches and model working state between AI systems, which is where the model shows a per-receiver gain (see the [README](../README.md)). Web and consumer delivery are documented boundaries, not the target. The first network test is the [AI-state handoff](proposals/ARFP-ai-state-handoff-network-test.md).
7. **Remove the extra round trip before payload where it matters.** The speed review models v0.1 as slower than HTTP with RFC 9842 compression dictionaries in the common web case, because OFFER/ACCEPT waits a round trip that dictionaries don't need. The push profile ([speed review §8](analysis/ARFP-internet-speed-review.md#8-how-the-transfer-set-would-work-end-to-end-the-push-profile)) is the proposed fix, with parity with pub/sub plus dictionary deltas (H1) as its test. For multi-gigabyte AI state on fast links the round trip is a small cost, so this is no longer first in line.

## Stages and gates

| Stage | Deliverable | Exit evidence | Present status |
|---|---|---|---|
| 1 — Direct core | Schemas, exact-state sender/receiver, bounded parsing, negotiation, references, field changes, staging, validation, durable atomic installation, replay behavior | A local/networked run installs valid targets, rejects invalid ones, and recovers duplicate or interrupted outcomes | **Tested at object level** in [`kit/`](../kit/): CDDL schema, gate zero (G1–G10), staging and validation, write-ahead commit journal, recovery from SIGKILL after the approval, head and receipt records and partway through the head write (C21), stale-head conflict (C19), duplicate-safe retry (C20). **No networked sender/receiver or transport** |
| 2 — Conformance and interoperability | Executable fixtures and a separately implemented encoder/receiver | Cross-implementation agreement on canonical bytes, digests, decisions, and transaction outcomes | **Partly met.** Every C01–C28 scenario has at least one executable case (132 cases, 37 of them for the speed mechanisms; 42 fixtures published as canonical CBOR vectors). The second encoder is a library (cbor2), not a separately implemented endpoint, so the gate is not passed |
| 3 — Mixed reconstruction and repair | Eligible procedural/residual paths, explicit approximation checks, affected-validator repair, fixed hybrid and simple adaptive selectors | Different Plans meet the same bound acceptance requirements; repair preserves those requirements | **Partly tested.** An exact profile executes procedural, residual and delta nodes with cone repair and evidence reuse (C04, C07, C08, C10). Approximate-path eligibility and evidence transfer by determinism class are checked on a toy profile with simulated decoders (C09, C11, R1–R9). No real decoder; no fixed-hybrid or adaptive selector |
| 4 — One repeater, two receivers | Authorized caching/compute/rewrite, scope and shared-demand registry, demand replacement, separate artifact/evidence/permission handling | C15–C18 pass with shared work preserved for the remaining receiver and stale results prevented from committing | **Rules tested at object level:** C15–C18, evidence applicability (C22), delegation and budgets (C23, C24), multi-hop bounds and forwarding (C25, C26), signed multi-hop evidence (C27). No repeater runtime |
| 5 — Measured benefits and losses | Reproducible workload harness; conventional, fixed-hybrid, direct, cache-only, and compute-repeater comparisons | Honest cold/warm results, tail latency and failures, complete accounting, at least one negative result | **Compression measured, time modeled:** delta sizes on real npm releases and a first-order time and KV-cache model ([speed review](analysis/ARFP-internet-speed-review.md)). The model already shows a negative case (v0.1 behind HTTP + RFC 9842 on warm links). No network benchmark |
| 6 — Wider fabric | Multiple repeaters, bounded forwarding, delegated budgets, checkpoints, multi-hop fidelity, topology and fairness study | Evidence specific to the larger deployment; no extrapolation from a single repeater alone | Optional future extension |

### Timebox the direct core

The review asks for a time limit on Stage 1 so the project reaches the distinctive shared-work demonstration. **Proposed planning budget: ten focused engineering days**, subject to owner/implementer scheduling. This is a planning suggestion, not an agreed delivery promise. The object-level part of Stage 1 is done; the timebox now applies to the networked direct core.

At the end of that timebox, publish one of two outcomes:

- A reproducible direct-core demo with a precise supported subset and known limitations.
- A blocker report, failing fixtures, and the smallest revision needed to make the spec implementable.

Do not use a Stage 1 success as evidence of superiority to HTTP, shared dictionary transport, or conventional content caching. Its purpose is to establish a correct and measurable baseline. Stop expanding Stage 1 with neural codecs, general DAG execution, or multiwriter coordination before the direct-core evidence exists.

### Next work, in order

From the [working analysis §11](analysis/ARFP-analysis-2026-10-11.md#11-next-work-in-order), reordered after the speed review and again when the project was positioned around machine-to-machine state handoff:

1. **AI-state handoff over real links:** KV-cache handoff against LMCache/CacheGen-style transfer, with pre-registered pass and kill criteria ([proposal](proposals/ARFP-ai-state-handoff-network-test.md)). Tests the per-receiver gain that is currently only modeled, and should include per-receiver acceptance and speculative start from the [speed mechanisms](proposals/ARFP-speed-mechanisms.md), with Lynx as the baseline for speculative start.
2. **Push profile:** the object-level rules are in the kit (speed mechanism 6, cases U1–U13): a standing DEMAND as the subscription; a PUSH carrying the signed binding, plan, base and payload, checked without a round trip; REPAIR on a miss. Still to do: send the plan by reference and shorten digest references, so the frame (2,622 B for a 653 B payload today) approaches the 128-byte target; a chunked tree hash so verification scales with the change; then H1.
3. **Stage 4 demo** with one strong and one weak receiver over a predictability × churn grid, counting every link's bytes. Tests H2–H5.
4. **Second CDDL tool, then a second implementation** given only the schema and the vectors.
5. **Stage 5 measurement** against HTTP/3 + RFC 9842, glTF/Draco and 3D Tiles, and LMCache-style transfer for AI state, with cold and warm caches.
6. **A real proof-of-inference scheme** for proof evidence (speed mechanism 5), measured for validation time against re-running and for false accepts.
7. **Harden the journal:** power-loss testing, directory fsync on file creation, disk write caches, group commit.

The contract split, previously next on this list, is built (T1–T14; see the [implementation notes](handoffs/ARFP-contract-split-implementation.md)).

## Make the conformance cases executable without changing their meaning

The complete scenario definitions remain in [handoff Section 21](architecture/ARFP_Concept_Handoff_v0.1_2026-10-11.md#21-conformance-cases). A fixture suite must name the profile, input artifacts, expected decision, expected committed head, and applicable limits.

| Cases | Next implementation task | Kit status (object level) |
|---|---|---|
| C01–C05 | Cover equivalent exact-state plans, distinct accepted display realizations, wrong-baseline rejection, missing dependencies after ACCEPT, and unsupported profile/representation rejection. The experiment never patches approximate display meshes; document that boundary when mapping C03. | C01–C03 and C05 pass on the toy profile; C04 (four sub-cases) runs on the exact profile with eviction, prebound fallback and an audit trail |
| C06–C14 | Add only when the respective decoder, procedural, residual, global invariant, generic cone repair, scope, or milestone feature exists; an unsupported-feature rejection is not a pass for successful feature behavior. | C07, C08 and C10 execute real procedural, residual and cone-repair paths on the exact profile. C06, C09 and C11–C14 are rule checks on the toy profile with simulated decoders |
| C15 | Cancel one receiver's demand while another still requires the shared dependency; the dependency remains live. | Passes (rules) |
| C16 | Supersede explicitly replaceable demand and establish a valid path for the new demand under the bound acceptance requirements. | Partly: the retirement half passes (only the replaced demand's unshared, unfinished work is canceled); the new demand's plan is not checked for eligibility |
| C17 | Attempt to suppress a required-transition update; the application profile's required semantics win over planner preference. | Passes (rules) |
| C18 | Deliver a canceled result late; it cannot commit as the replacement request's result. | Passes (rules) |
| C19–C21 | Inject stale-head races, acknowledgment loss, and crashes around durable installation and result delivery. | C19 and C20 pass; C21 runs nine sub-cases against worker processes killed with SIGKILL after the approval, head and receipt records and partway through the head write. Not power loss, and no crash point sits between a conflict or abort record and its receipt |
| C22–C27 | Test evidence applicability, delegated authority/budget, multi-hop approximation, bounded forwarding, and re-attestation once the fabric extension is defined. | All pass at object level; C27 has ten sub-cases with signed evidence and attestations |
| C28 | Build canonical encoding and decoding independently from a frozen spec, exchange positive/negative vectors, and resolve every divergence before interoperability claims. | Library check only: cbor2 reproduces all 42 fixtures byte for byte. The spec-only independent implementation this gate requires does not exist |

For C28, two implementations should not share the same parser/canonicalizer implementation and simply call that independence. Track which code, libraries, and fixtures they share. Separate AI-assisted implementations are one possible way to produce independent attempts, not proof that ambiguities are absent.

## Falsifiable performance hypotheses

These are predictions to test, not results:

- **Likely favorable case:** large structured objects, repeated updates, shared dependencies, warm caches, and sufficient reuse to amortize negotiation and validation.
- **Likely unfavorable case:** small frequent updates with little reuse, where control messages, evidence, validation, and scheduling exceed saved payload cost.
- **Possible cold-start loss:** a reference mesh, decoder, generator, dictionary, or checkpoint is expensive to acquire relative to the requested output.
- **Possible placement loss:** repeater work reduces origin egress while increasing total link traffic or end-to-end latency.

Keep workload scope, fidelity, initial cache state, dependency placement, and resource ceilings comparable. Report all attempts, including failures and deadline misses. Record origin egress separately from the sum across every measured link. Report time to permitted use separately from final validation and durable local commit.

Predict the break-even conditions before running the benchmark. Include a workload where adaptation is expected to lose, and publish that outcome even if it contradicts the favorable hypothesis. A negative case is a required result, not an error to remove from the sample.

The speed review makes these concrete: eight pre-registered negative cases ([§10](analysis/ARFP-internet-speed-review.md#10-negative-cases-to-publish-pre-registered)), and hypotheses H1–H5 with proposed pass and kill thresholds, strong baselines and a predictability × churn workload grid ([§11](analysis/ARFP-internet-speed-review.md#11-stage-45-sharpened)).

A datagram channel may be appropriate for a separately defined stream of expendable real-time updates. This remains an application/transport design option; the imported component experiment specifies a reliable stream, and no telepresence document is adopted by reference.

## Review response register

| Review recommendation | Handling in this repository | Still required |
|---|---|---|
| Align pitch with actual system | README leads with coordination, validation, maturity and the speed review's findings, including where v0.1 loses | Review any external pitch when its actual text is provided |
| Reuse existing standards | [Standards reuse map](STANDARDS_REUSE.md); JCS in the experimental draft; deterministic CBOR and COSE_Sign1/Ed25519 adopted in the kit | Choose one encoding for the next profile; decide on transparency receipts |
| Investigate approximate-output differentiation | Distinct realization identities kept; evidence transfer by determinism class (E/T/N) checked at object level | Compare exact mechanisms with NFN, CFN, and provenance work; demonstrate a meaningful difference |
| Timebox Stage 1 | Proposed ten-day engineering budget and explicit stop/report gate | Owner/implementer schedules and executes it for the networked core |
| Reach the shared-work demo | Stage 4 and C15–C18 keep priority; the rules pass at object level | Implement and record it with every link counted |
| Predict and publish a loss | Adverse workload hypotheses, plus eight pre-registered negative cases in the speed review | Run and report the negative benchmark |
| Make C28 real | Spec-only independent implementation gate defined; library cross-check in the kit | Produce and compare the implementations |
| Keep telepresence separate | Explicit repository boundary | Separate document and consistency model if that work proceeds |
| Find another endpoint builder | Independent participant goal | Identify and engage a willing second party |

## Claims discipline

Use “specified” for documented rules, “checked” for a named artifact check, “implemented” for code that exists, “tested” for executed cases, and “measured” for recorded experiments. A checked JSON transcript is not a network implementation. An object-level test is not a protocol run. A signature is not validation. An architectural synthesis is not proof of novelty. An improvement on one workload is not an Internet-scale performance claim.
