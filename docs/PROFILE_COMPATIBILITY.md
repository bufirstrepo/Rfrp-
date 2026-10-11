# How the ARFP handoff, the experimental draft and the schema kit fit together

**Status:** editorial integration guide, prepared 2026-10-11 and updated the same day to add the schema kit as a third artifact. This guide labels the supplied material; it does not amend either original specification.

The [complete handoff](architecture/ARFP_Concept_Handoff_v0.1_2026-10-11.md) defines the broad Adaptive Reconstruction **Fabric** Protocol concept. The [experimental draft](specification/Adaptive_Reconstruction_Protocol_v0.1.md) specifies a narrower Adaptive Reconstruction Protocol profile using `arf-experiment/0.1`. Both use “v0.1,” but at different scopes.

A third artifact, the [schema kit](../kit/README.md) with its [working analysis](analysis/ARFP-analysis-2026-10-11.md), turns the handoff's object model into a CDDL schema for deterministic CBOR with COSE signatures and executes 95 object-level cases against it. It follows the handoff, not the experimental draft: it shares neither the draft's wire literal nor its JSON encoding. See [Where the schema kit fits](#where-the-schema-kit-fits).

Use the experimental draft's message tables and rules for that particular profile. Use the handoff for architectural intent and the future fabric. A requirement missing from the narrow profile must not be treated as implemented through implication. Resolve a genuine conflict in a versioned specification change and new test vectors.

## Compatibility map

| Concern | Broad handoff | Experimental draft | Integration consequence |
|---|---|---|---|
| Scope | Domain-independent mixed reconstruction and authorized fabric | Single-publisher assembly-component updates to one receiver | A useful first profile, not the complete fabric |
| Target | Logical object, revision, publisher | `object_id`, `publisher_id`, target revision and exact state digest in Plan | Preserve publisher binding; do not rely on an unauthenticated ID field |
| Contract identity | Separately identified and bound acceptance object | Inline `contracts` inside the hashed Plan, checked against receiver task requirements | No standalone Contract object/hash on this wire; do not claim four separately serialized identities |
| Plan | DAG, dependencies, representations, placement, scheduling | One exact-state slot, one display slot, complete dependency descriptors, limits, payload digest | Narrow Plan is not a general DAG executor |
| Realized output | Concrete identity for every accepted realization | Exact state digest plus display asset association and validation metadata | Display asset identity matters even when exact state digests match |
| Representation classes | Reference, Delta, Procedural, Latent, Residual, Literal | `state-full-v1`, `state-set-v1`, `mesh-ref-v1` | Full state, structured change, and references are concrete; other classes need extensions |
| Fidelity | Profile predicates, references, evidence, semantic invariants | Exact canonical state plus same-topology vertex bound against a receiver-held reference mesh | The receiver must acquire the reference and count its cost |
| Encoding | General wire and signature choices remain open | Restricted printable-ASCII/safe-integer JCS, SHA-256, four-byte length prefix | This choice is resolved for the experiment only |
| Authority | Single designated publisher; explicit downstream grants | Authenticated confidential session plus configured publisher/object permission | Initial identity and baseline provisioning remain deployment responsibilities |
| Evidence and receipts | Separate evidence, approval, and durable commit receipt semantics | Local mesh check and recoverable `RESULT` record; no signed receipt envelope | A RESULT is not automatically a fabric receipt or SCITT receipt |
| Acceptance | Eligible attempt; commit requires realized validation | `ACCEPT` reserves, pins present dependencies, authorizes missing fetches, starts lease | Runtime failure remains possible after acceptance |
| Repair | Replace failed node/cone and recheck affected global predicates | New OFFER/update ID, full state, exact reference display; same or tighter tolerance | Explicit transaction repair is narrower than arbitrary DAG-cone repair |
| Baseline | Exact output identity or declared semantic applicability | Exact installed record revision and digest checked before work and at commit | No fuzzy baseline matching and no arbitrary patching of approximate meshes |
| Commit | Atomic local publication, recoverable outcome, duplicate safety | Exact record, display association, metadata, and durable result installed together | No independent early display milestone in this profile |
| Repeater | Cache, compute, rewrite, scoped interest, checkpoints, delegation | Out of scope | Requires a later fabric profile and its own conformance evidence |
| Cancellation | Replaceable demand, required transitions, shared-work liveness | No fabric cancellation protocol or shared demand registry | C15–C18 remain future implementation gates |
| Learned decoding | Optional, with decoder/runtime/reference/evidence bindings | Extension requirements discussed; no decoder implemented | No AI compression performance claim |
| Multiple writers | Deliberately excluded from initial design | Excluded | Keep telepresence collaboration/consensus separate |

## Where the schema kit fits

The kit implements none of the experimental draft's messages. It is a separate encoding of the broad handoff's objects, executed against toy profiles (`scene.assembly.v1`, simulated decoders) and one exact profile (`bytes.exact.v1`). Results carry over to the draft only where a rule is stated the same way in both.

| Concern | Experimental draft | Schema kit | Consequence |
|---|---|---|---|
| Encoding | Restricted JCS JSON, SHA-256, four-byte length prefix | Deterministic CBOR (RFC 8949 §4.2.1), SHA-256, exact decimals as CBOR tag 4 | Two incompatible encodings exist; choosing one for the next profile is open |
| Identity | Digests of specific records and payloads | Domain-separated object ids: `id(o) = H(canon(["arfp/0", kind, o]))` | Ids from one cannot be compared with the other |
| Contract | Inline `contracts` inside the hashed Plan | Standalone `contract` object with its own id, bound to one target by a publisher-signed `binding` (COSE_Sign1, Ed25519) checked before planning; or a session `contract-template` plus a per-revision split binding that materializes into the same contract and id | The kit answers the "general Contract object" question for its own encoding; mapping the draft's inline contracts onto it is not done |
| Authority | Authenticated session plus configured permission | Static key allow-list; signed bindings and delegations with narrowing rights and partitioned budgets | No key rotation or revocation in either |
| Evidence and receipts | Local mesh check and a recoverable `RESULT` record | Signed evidence per predicate, repeater attestations, approval naming the binding hash, contract, plan, output and evidence; receipt with committed, conflict or aborted status | The kit's approval and receipt are not SCITT receipts and do not model the draft's display-asset association |
| Commit and recovery | Exact record, display association, metadata and result installed together | Write-ahead journal with compare-and-swap on the head; recovery tested against SIGKILL and a torn write | Neither is tested against power loss |
| Repeater and cancellation | Out of scope | Object-level rules for shared-demand cancellation, supersession, delegation, rewrite and multi-hop evidence (C15–C18, C22–C27) | No runtime in either |

## Clarifications that govern interpretation

### Eligibility and validation

The earliest notes say an accepted Plan satisfies the Contract. The consolidated correction is more precise: acceptance permits an eligible reconstruction attempt; successful execution is not guaranteed. Commit requires appropriate evidence about the actual realization, current authority, resource compliance, and a valid commit precondition.

### Exact record and approximate display are different slots

The narrow profile's exactness promise covers a canonical component record. It does not certify an original CAD file, simulation, material model, or every geometric property. Its display predicate compares identical indexed topology and vertex correspondence. The bound is not a certificate of global clearance, watertightness, or structural safety.

Different valid display meshes may accompany the same exact component record. Their asset digests and validation metadata must remain distinguishable. Do not collapse the compound installation into only the exact-state digest when designing later evidence or receipts.

### Contract-preserving repair and plan identity

In the experiment, the new repair Plan has a new hash. Since inline contract fields are part of that Plan, a future global Contract hash cannot simply be inferred from `plan_digest`. A fabric extension must define a canonical independent Contract and its relationship to these inline predicates.

Repair uses the reference mesh as the display mesh, supplying zero geometric deviation. It retains or tightens the original tolerance and reuses only verified immutable dependencies. A new Plan still declares its entire dependency set, even if some payloads no longer need transmission.

### Resource limits and cost measurements are different quantities

The experiment's `max_dependency_bytes` counts all declared unique dependencies, including locally cached assets. Newly transferred bytes count actual traffic. Both are meaningful; they must not be conflated. Receiver reference-mesh download, replay, and validation costs remain part of an honest benchmark.

### Scope changes and source revisions are different events

The original camera example used “revision” loosely. A camera movement commonly changes the requested scope or interest without modifying the publisher's Target revision. Future cancellation must identify which demand is superseded, preserve required transitions, retain completed reusable dependencies, and keep work needed by other live demands.

### Signatures, validation, and transparency

A valid signature authenticates the signer's statement. A transparency receipt can establish a statement's registration under the relevant transparency system. Neither replaces the domain predicate proving that the receiver's actual output meets its Contract. The narrow experiment currently defines neither a fabric signature envelope nor transparency integration.

## Decisions to resolve before implementation claims

| Open point | Concrete next action | Progress in the schema kit |
|---|---|---|
| Naming and scope | Decide whether `arf-experiment/0.1` remains a named ARFP profile or becomes a separately versioned protocol family; keep current wire literal unchanged until decided | Not addressed; the kit uses `arfp/0` as both its id domain and its advertised protocol name (CAPABILITIES `protocols`), with `v: 0` on every message. None of this relates to `arf-experiment/0.1` |
| General Contract object | Define stable independent canonical fields, digest scope, target/reference binding, and mapping from inline contracts | Defined for CBOR: fields, digest scope, target binding by signed binding, per-revision expected digests and references (contract split). Mapping from inline contracts not done |
| Compound realized-output identity | Define how exact state, display asset, scope, and acceptance evidence are referenced together in a future receipt | Partly: an approval names the output digest with the contract, plan and evidence, and each receipt names its approval; no display-asset association |
| Reservation contention | Specify the error/result for a second candidate while an object already has an active reservation; the draft limits concurrency but lacks a dedicated conflict code | Not addressed |
| Durable replay | Specify journal retention, session reconnection behavior, and the exact response to a duplicate after later revisions have been installed | Partly: duplicate retries return a byte-identical receipt (C20, C21-C); journal retention and reconnection not specified |
| Capability and limits schema | Produce machine-readable schemas and invalid-input fixtures; the draft's field tables currently carry the normative profile rules | Done for CBOR: CDDL rules for capabilities and resource limits, plus 11 malformed objects checked by `run_checks.py` (built in code, not shipped as negative vectors) |
| Profile conformance | Map each C01–C28 architectural scenario to implemented, partially covered, out-of-profile, or not-yet-tested behavior | Every C01–C28 scenario has an executable case on the kit's own profiles; the mapping to `arf-experiment/0.1` is not done |
| Repeater extension | Define rewrite lineage, authorization attenuation, budget allocation, evidence applicability, end-to-end error accounting, and shared-demand cancellation on the wire | Object-level rules for rewrite lineage, delegation narrowing, budget partitioning, evidence applicability, additive error bounds and multi-hop evidence; shared-demand cancellation on the wire not defined |
| Encoding for the next profile | Choose JCS (the draft) or deterministic CBOR with COSE (the kit); regenerate vectors for the choice | The kit ships 38 CBOR vectors; a library (cbor2) reproduces them, which is not an independent implementation |
| Contract split | Decide whether the next profile carries contracts whole, split, or both | Built and tested (T1–T14); where it departs from the proposal, and why, is in the [implementation notes](handoffs/ARFP-contract-split-implementation.md) |
| Round trip before payload | Decide whether the next profile negotiates (OFFER/ACCEPT) or pushes on a standing subscription | The [speed review](analysis/ARFP-internet-speed-review.md) models the negotiated path one round trip behind HTTP with RFC 9842; a push profile is proposed, not built |

These are work items, not claims that the source documents already resolve them. The originals remain unchanged so a future implementer can distinguish supplied material from editorial synthesis.
