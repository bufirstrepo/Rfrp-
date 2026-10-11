# ARFP — Complete Concept Handoff

**Adaptive Reconstruction Fabric Protocol**  
**Concept version:** v0.1  
**Handoff revision:** 2026-10-11  
**Status:** Consolidated architectural proposal and implementation brief  
**Basis:** The concept, refinements, repeater extension, and mathematical formulation developed in the conversation through this date.

> ARFP negotiates, materializes, validates, and commits versioned objects using a dependency DAG of mixed representations. Plans adapt to receiver capabilities and available state. Authorized intermediate nodes may cache, execute, and rewrite eligible reconstruction work while preserving the bound Target, Contract, scope, and authority requirements.

This document is intended to let another engineer or model continue the project without reconstructing the conversation. It preserves the broad vision while distinguishing established design direction, proposed engineering rules, optional extensions, and unresolved choices.

No implementation, interoperability result, benchmark, or Internet-scale deployment was produced or inspected in the discussion. The equations below are a proposed model, not an experimental result or a completed proof.

## Contents

1. [Read first: intent and status](#1-read-first-intent-and-status)
2. [Problem and operating principle](#2-problem-and-operating-principle)
3. [Goals and boundaries](#3-goals-and-boundaries)
4. [Architecture and roles](#4-architecture-and-roles)
5. [Identity model and protocol objects](#5-identity-model-and-protocol-objects)
6. [Data Worktree and node semantics](#6-data-worktree-and-node-semantics)
7. [Contracts, profiles, scopes, and milestones](#7-contracts-profiles-scopes-and-milestones)
8. [Capabilities, state, and cache behavior](#8-capabilities-state-and-cache-behavior)
9. [Whole-plan selection and scheduling](#9-whole-plan-selection-and-scheduling)
10. [Negotiation and execution lifecycle](#10-negotiation-and-execution-lifecycle)
11. [Validation and evidence](#11-validation-and-evidence)
12. [Localized repair](#12-localized-repair)
13. [Replaceable updates and shared-work cancellation](#13-replaceable-updates-and-shared-work-cancellation)
14. [Commitment, receipts, and authority](#14-commitment-receipts-and-authority)
15. [Authorized repeater fabric](#15-authorized-repeater-fabric)
16. [Optional session extensions](#16-optional-session-extensions)
17. [Mathematical model](#17-mathematical-model)
18. [Illustrative object shapes](#18-illustrative-object-shapes)
19. [Reference processing algorithm](#19-reference-processing-algorithm)
20. [Demonstration and benchmark design](#20-demonstration-and-benchmark-design)
21. [Conformance cases](#21-conformance-cases)
22. [Trust and execution constraints](#22-trust-and-execution-constraints)
23. [Prior work and source register](#23-prior-work-and-source-register)
24. [Implementation sequence](#24-implementation-sequence)
25. [Open decision register](#25-open-decision-register)
26. [Instructions for the next engineer or model](#26-instructions-for-the-next-engineer-or-model)
27. [Glossary](#27-glossary)

## 1. Read first: intent and status

### 1.1 What the project is trying to accomplish

The originating ambition is to make large data pipelines and repeated transfers substantially more efficient by exploiting shared state, structure, existing assets, executable recipes, and suitable learned representations. The receiver should obtain a usable, accepted result with less unnecessary transfer and work.

The central delivery artifact is a **Data Worktree**: a dependency graph describing what must be obtained or reconstructed and how it can be produced. The wire carries that description plus the payloads and dependencies that are actually missing.

ARFP is being shaped as a candidate application-layer Internet protocol. The first implementation can run as an overlay on ordinary Internet infrastructure. AI is optional planner machinery. Cameras, viewpoints, and 3D scenes are application examples, not core protocol concepts.

### 1.2 Maturity labels

| Label | Meaning in this handoff |
|---|---|
| Core direction | Repeatedly established architecture to preserve while developing the prototype |
| Proposed hardening | Engineering rule introduced to make that architecture coherent and testable |
| Optional extension | Potential capability to retain in the roadmap without making the minimal prototype depend on it |
| Open | A choice that has not been resolved or standardized |
| Demonstrated | Reserved for behavior supported by executed tests; no such project results are claimed here |

Requirements expressed as “must” in this document are proposed requirements for a conforming ARFP implementation. They are not statements that a deployed implementation already provides those guarantees. Message names and example schemas are working design names, not registered wire identifiers.

### 1.3 Corrections that supersede earlier shorthand

| Earlier shorthand | Consolidated interpretation |
|---|---|
| Every accepted Plan satisfies the Contract | Plan acceptance authorizes an eligible attempt. Commitment requires acceptable evidence and authority; execution may fail. |
| Send the worktree instead of the data | Send the worktree plus all missing payloads and dependencies. Literal data remains a valid representation. |
| The worktree is a tree | Shared dependencies make its execution structure a DAG. |
| A hash proves correctness | A digest establishes content identity relative to an authenticated expectation. Fidelity and semantic correctness require additional predicates where applicable. |
| A residual bounds the error | A residual supplies a correction. Its resulting error bound must be established by validation or a sound profile rule. |
| Revalidate only the repaired execution cone | Reevaluate all affected computations and validation predicates, including cross-branch or global checks. |
| Same Target means the same delta baseline | Approximate outputs can differ. Deltas and residuals need exact baseline identities or explicit semantic applicability conditions. |
| A signed receipt makes the result correct | A signature authenticates a statement. Correctness depends on evidence, validators, and their trust assumptions. |
| A camera jump is a new object revision | It commonly changes an interest or request scope. The source Target may remain unchanged. |
| Cancel the old request, therefore cancel all its work | Cancel only unfinished work no longer required by any active demand or retention obligation. |
| Each repeater passes its local tolerance | End-to-end fidelity must still hold relative to the Contract's reference or a justified composition rule. |
| Origin traffic fell, so network traffic fell | Origin traffic, total link traffic, compute, validation, and latency must be measured separately. |
| This is Internet-scale | It is an architecture intended for Internet deployment; scalability is an untested claim. |

## 2. Problem and operating principle

A receiver may already possess assets, baselines, schemas, dictionaries, decoders, generators, or intermediate results that make retransmission wasteful. Different receivers have different caches, processors, memory, runtime support, and local policies.

A fixed transfer format cannot always exploit those differences. Conversely, allowing arbitrary reconstruction without an explicit agreement makes it unclear what the result should be, how to check it, or when it may replace the current state.

ARFP combines four activities:

1. Negotiate a concrete reconstruction agreement and eligible Plan.
2. Obtain or execute the chosen representations and dependencies.
3. Validate the realized result using evidence required by the Contract.
4. Commit the accepted result only within the authority granted to that participant.

A single update may reuse a content reference, apply a structured delta, run a generator, decode a learned representation, apply a residual, and decompress a literal artifact.

The proposed contribution is the coordinated binding of these choices to identity, fidelity, evidence, repair, and authority across independently implemented endpoints. The individual ingredients have substantial prior work; see Section 23.

### 2.1 Where benefits could arise

Potential savings come from avoiding duplicate transfers, exploiting structure, computing outputs near consumers, sharing intermediate work, materializing only requested scopes, and stopping obsolete reconstruction attempts.

A recipe cannot reconstruct arbitrary unseen information for free. A missing model is a dependency with a transfer and execution cost. An approximate output is acceptable only when the bound Contract permits it. A derived summary or query result is a distinct requested output, not evidence that the entire original dataset was transferred or reconstructed.

The relevant performance target is **time and cost to an accepted result**, not the size of the smallest payload in isolation.

## 3. Goals and boundaries

### 3.1 Core goals

- Support mixed representations within one reconstruction graph.
- Adapt Plans to a receiver's actual declared capabilities, available state, and policy.
- Keep logical targets and acceptance requirements independent of physical Plans.
- Preserve exactness where required and permit approximation only where declared.
- Make dependencies explicit and verifiable.
- Repair local failures without discarding valid independent work.
- Separate result acceptance from source write authority.
- Support authorized intermediate caches and compute nodes.
- Preserve required updates while allowing explicit supersession of replaceable updates.
- Produce auditable records linking outputs, evidence, Plans, Contracts, and authority.
- Permit different selector implementations to interoperate.

### 3.2 Boundaries for the initial design

- No mandatory AI model, agent council, or neural representation.
- No requirement to replace IP routing or deploy special router hardware.
- No claim that cryptographic signatures alone prove arbitrary computation correct.
- No universal semantic-fidelity metric.
- No implied multiwriter consensus algorithm.
- No automatic right for receivers or repeaters to update the authoritative source.
- No unconditional guarantee of finishing an accepted Plan.
- No assumption that learned decoding is bitwise reproducible across all devices.
- No camera, viewpoint, or scene-specific concept in the protocol core.
- No demonstrated compression ratio, throughput gain, cost reduction, or novelty result.

Single-publisher authority is the proposed starting point. More complex ownership and consensus models require a separate design.

## 4. Architecture and roles

### 4.1 Logical layers

| Layer | Responsibility |
|---|---|
| Application profile and adapter | Defines output schemas, units, coordinates, fidelity meaning, operation semantics, and update replacement rules |
| Agreement layer | Binds Target, Contract, scope, permitted participants, and acceptance requirements |
| Planner | Selects representations, dependency resolution, placement, and scheduling |
| Execution layer | Resolves references and performs authorized reconstruction operations |
| Validation layer | Produces or checks evidence against the applicable predicates |
| Transport and storage | Carries envelopes and payloads; stores identified artifacts |
| Commit and receipt layer | Applies authorized state transitions and records outcomes |

An adapter must preserve provenance, object identities, schemas, units, coordinate systems, and declared dependencies. It must not silently convert an exact requirement into an approximate one.

### 4.2 Participant roles

| Role | Authority and responsibility |
|---|---|
| Publisher | Names or authorizes a Target revision and its binding to a Contract |
| Receiver | Declares capabilities, stages reconstruction, checks acceptance, and commits locally if authorized |
| Planner or selector | Proposes eligible Plans; may run at sender, receiver, repeater, or through coordination |
| Validator or checker | Evaluates named predicates within a declared trust policy |
| Repeater | Caches, computes, forwards, or rewrites only within its delegation |
| Session coordinator | Optional initial mechanism for allocating work, budgets, and repeater placement |
| Application adapter | Maps domain objects and events to protocol-level targets, scopes, dependencies, and predicates |

Roles may coexist on one machine. Co-location does not merge their permissions. A planner can propose a Plan without being authorized to validate its output or commit it.

## 5. Identity model and protocol objects

### 5.1 The four primary identifiers

| Identity | Names | Rule |
|---|---|---|
| Target | A logical object and publisher revision | The named revision's meaning is immutable |
| Contract | Acceptance predicates, permitted representations, resource rules, evidence policy, and authority binding | Bound before a particular Plan is accepted; amendment creates a new identity |
| Plan | The chosen reconstruction DAG and relevant execution choices | Receiver-specific and immutable once accepted; repairs create a new Plan or select a preauthorized alternative |
| Realized Output | The concrete bytes or agreed canonical content actually produced | Has its own content identity, even if another accepted output names the same logical Target |

An initial offer may negotiate which Contract to bind. Once bound, a repeater or planner cannot silently change it.

Two accepted approximate outputs may satisfy the same Target and Contract yet have different output digests. A later patch cannot assume those outputs are identical.

### 5.2 Supporting identities

- **Scope:** A canonical description of the requested subset or projection.
- **Milestone:** A declared stage of accepted availability and its permitted uses.
- **Interest/request:** A receiver's current demand, with its own stream and sequence.
- **Capability/state snapshot:** The receiver state against which a Plan was proposed.
- **Node:** An operation or artifact descriptor within a Plan; distinct from its output digest.
- **Reference:** The authenticated source or baseline against which a predicate is checked.
- **Attempt/transaction:** Distinguishes retries, repair attempts, and idempotent commitment.
- **Delegation:** A bounded authorization for another participant.
- **Checkpoint:** An identified baseline that multiple receivers can adopt.

A content digest is not a retrieval location. A locator is a hint for obtaining content; retrieved bytes must still match the required identity and policy.

### 5.3 Minimal conceptual objects

| Object | Minimum information to define |
|---|---|
| Target | Object ID, revision, publisher, schema or profile reference, authenticated agreement binding |
| Contract | Fidelity predicates, permitted node classes, invariants, scopes/milestones if applicable, resource limits, evidence and authority policies |
| Plan | Node DAG, output roots, representation and runtime bindings, dependency identities, capability/state reference, fallback rules |
| WorktreePayload | Plan or graph description plus the missing node payloads and associated metadata |
| Evidence | Output, reference, predicate, validator, measured result, and authentication bindings |
| ValidationApproval | Accepted evidence and authority to commit one specified result |
| Receipt | Target, Contract, scope/milestone, Plan, output, evidence, participant, and actual commit outcome |

The earliest concept listed five objects: Target, Contract, Plan, WorktreePayload, and Receipt. Evidence and ValidationApproval are proposed explicit separations that resolve ambiguity; their final wire packaging is open.

## 6. Data Worktree and node semantics

### 6.1 Graph model

The Data Worktree is the dependency DAG used to obtain the requested result. Dependencies may be shared by multiple nodes or requests. Eligible execution can proceed concurrently when dependencies and resource limits allow; a topological ordering does not require serial execution.

Validation dependencies must also be explicit, whether represented inside the same graph or through a linked validation graph. A structural cycle is invalid for the simple DAG execution model. Iteration, if later supported, needs an explicitly bounded operation with defined semantics.

### 6.2 The six established representation classes

| Class | Reconstruction behavior | Required binding or check |
|---|---|---|
| Reference | Reuse an existing artifact or fetch identified content | Expected content identity, access permission, availability, and applicable evidence |
| Delta | Apply a change to a specified baseline | Exact baseline output digest or explicit semantic applicability predicates |
| Procedural | Execute an approved generator with declared parameters | Generator and runtime identities, input identities, execution bounds, output validation |
| Latent | Decode a learned representation | Decoder/model identity, preprocessing and runtime requirements, permitted approximation profile |
| Residual | Apply an explicit correction to a preceding result | Actual correction baseline, operation semantics, and validation of the corrected output |
| Literal | Transfer bytes directly or through a conventional lossless codec | Codec and dictionary identities where used, decompression limits, output digest |

“Literal” is the fallback representation when no better eligible path exists. The baseline codec and uncompressed encoding are open decisions.

The current latent use case is approximate-by-contract. Learned coding is not inherently always lossy; a future profile could define exact learned reconstruction. Such a profile would still need exact-output validation.

A Reference to an approximate artifact does not make that artifact exact. A cached Procedural output can be referenced without rerunning its generator if its identity, evidence, and policy are suitable.

### 6.3 Node descriptor requirements

Each node should declare:

- Local node ID, node type, output schema, and relevant profile.
- Operation or codec identity and payload reference.
- All execution dependencies and their required versions or digests.
- Generator, decoder, model, dictionary, and runtime requirements as applicable.
- Baseline identity or semantic preconditions for Delta and Residual operations.
- Claimed cost and fidelity information for planning.
- Validation predicates and evidence requirements.
- Permitted execution locations and authority requirements.
- Resource bounds and fallback alternatives.
- Side-effect policy.

Claimed fidelity is planning metadata, not acceptance evidence. Unknown required node types must lead to rejection or renegotiation, not guessed execution.

### 6.4 Historical “task” representation

Earlier discussion included tasks among possible representations. The consolidated minimal node set contains the six classes above.

For the initial implementation, a task should map to an approved Procedural operation with explicit inputs, outputs, and evidence. Arbitrary agent activity or an unconstrained natural-language instruction is not an interoperable execution definition. General remote task execution remains an optional future profile.

## 7. Contracts, profiles, scopes, and milestones

### 7.1 Contract contents

A Contract should bind:

- Target and output schema expectations.
- Exact and approximate fields or subobjects.
- Fidelity predicates, thresholds, units, and reference identities.
- Semantic invariants and cross-object constraints.
- Permitted approximation classes and representations.
- Execution and resource limits.
- Evidence requirements and accepted checker identities or classes.
- Authority and delegation policy.
- Scope and milestone semantics, when offered.
- Update supersession and required-transition rules.
- Failure, repair, and amendment behavior.

A receiver may additionally impose stricter local admission or trust requirements. Publisher authorization does not compel a receiver to execute code or trust a checker.

### 7.2 Profiles

Application profiles define the meaning that the common envelope cannot supply universally: geometry distance, numerical tolerance, schema validity, unit preservation, distributional metrics, permitted state replacement, and appropriate validators.

Profiles need stable identities and versions. Capability negotiation identifies supported profiles. A profile revision that changes acceptance semantics creates a new relevant binding.

### 7.3 Scoped requests

A scope can identify a subset, projection, region, time interval, or set of attributes. Its dependency closure may include material outside the requested visible subset.

A scoped result links to the original Target but explicitly identifies what it covers. Its receipt must bind the scope. Materializing a subset must not be reported as acceptance of the full Target.

A computed summary, filtered table, or query answer may instead require a separately defined derived Target. The profile must make that relationship explicit.

### 7.4 Milestones

A Contract may declare independently accepted stages with permitted uses. For an application demonstration, examples include navigation readiness, interaction readiness, and presentation readiness. These names belong to that application's profile.

A milestone needs:

- Its output roots and required dependencies.
- Acceptance predicates and consistency requirements.
- Permitted uses.
- Its relationship to the full requested result.
- A receipt that cannot be mistaken for a full-result receipt.

An incomplete state must not become authoritative merely because it is useful to display. Cross-object consistency can require several outputs to be accepted atomically as one milestone.

## 8. Capabilities, state, and cache behavior

### 8.1 Receiver declarations

A capability/state exchange can report:

- Supported protocol versions, schemas, profiles, node classes, and codecs.
- Approved generators, decoder/model versions, and runtimes.
- Available assets, baselines, dictionaries, and intermediate outputs.
- Compute and memory limits, concurrency, and local execution policy.
- Applicable trust and evidence policies.
- Current accepted revisions and concrete output identities.
- Relevant network observations and deadline requirements.

Declarations are planning inputs, not eternal guarantees. A cache entry can be evicted and a device can become busy after negotiation.

### 8.2 State snapshots and optional leases

Bind a Plan to the state snapshot used to produce it. Before execution, verify required dependencies still exist or are retrievable.

An optional lease can reserve a dependency for an agreed interval. The protocol must define expiry and failure handling if leases are implemented. Approximate cache inventories can reduce metadata size but require confirmation before an apparent hit is relied upon.

### 8.3 Separate three forms of reuse

| Stored association | Meaning |
|---|---|
| Artifact store | These bytes exist under this content identity |
| Evidence store | These checks were performed against these references under these policies |
| Authorization state | These participants currently have permission to receive, execute, or transform the artifact |

Validation under one Contract is not universal validation. Authorization can change while the content bytes remain the same. Content-addressed reuse and evidence reuse therefore have different eligibility checks.

## 9. Whole-plan selection and scheduling

### 9.1 Selection problem

Choose an eligible Plan that minimizes the selected cost to an accepted result. The initial objective is time to validated availability; bandwidth, energy, monetary cost, or a declared composite objective may be implemented by a planner.

Account for:

- Plan construction and negotiation.
- Missing payloads and transitive dependencies.
- Shared dependency reuse.
- Transfer latency and bandwidth.
- Execution, queueing, memory, and storage.
- Validation and evidence production.
- Expected repair, retransmission, and fallback.
- Aborted or failed attempts.
- First permitted use and final acceptance, if milestones exist.

Fidelity and authority are eligibility and acceptance constraints. The optimizer cannot trade them away for speed.

### 9.2 Avoid local minima

The smallest per-node payload may require an expensive missing model. A procedural recipe may save bytes while taking too long to execute. Several dependents may collectively justify a dependency that is uneconomical for one node.

Account for a shared dependency once at a location when the same transfer and retained artifact serve multiple dependents. Do not treat it as free at another location that must independently receive it.

### 9.3 Placement

Eligible operations can be placed at publisher, receiver, or authorized repeater. Placement must account for transferred inputs and outputs, queueing, checker availability, policy, and downstream consequences.

Expanding a compact recipe into a large artifact earlier in the route can save repeated computation but increase network traffic. Compare complete delivery paths.

### 9.4 Session-wide planning

Optional lookahead can evaluate whether obtaining a reusable dictionary, decoder, generator, or checkpoint will reduce future update costs. The model must include eviction risk and uncertain session duration.

Observed performance can improve a selector over time. AI-based selection, deterministic heuristics, and simple fixed policies can all implement the same protocol. Any agent council is implementation machinery with bounded proposal authority.

## 10. Negotiation and execution lifecycle

### 10.1 Candidate messages

These names preserve the conversation's protocol outline. Their exact framing and whether some are combined remain open.

| Message | Purpose |
|---|---|
| CAPABILITIES | Advertise supported execution, decoding, profile, and evidence features |
| STATE | Report relevant caches, baselines, accepted outputs, and state snapshot |
| OFFER | Propose Target, Contract, scope, Plan, and required dependencies |
| ACCEPT / REJECT | Authorize an eligible attempt or explain why it cannot proceed |
| UPDATE / WORKTREE_PAYLOAD | Deliver graph information and missing payloads |
| RESULT | Report materialization or validation outcome and evidence references |
| REPAIR | Identify failure, required replacement, and new or preauthorized Plan choice |
| CANCEL / SUPERSEDE | Retire an authorized replaceable demand |
| VALIDATION_APPROVAL | Bind accepted evidence to a proposed local commit |
| COMMIT_RECEIPT | Record an actual durable local state transition |

Each operation needs stable context: protocol version, session or request identity, attempt ID, Target and Contract bindings, scope, Plan, applicable baseline, and authentication.

### 10.2 State progression

~~~mermaid
stateDiagram-v2
    [*] --> Negotiating
    Negotiating --> Accepted: Eligible plan accepted
    Negotiating --> Rejected
    Accepted --> Materializing
    Materializing --> Validating
    Materializing --> Repairing: Dependency or execution failure
    Validating --> Repairing: Acceptance failure
    Repairing --> Materializing: Authorized revised plan
    Validating --> Ready: Evidence accepted
    Ready --> Committed: Atomic local transition
    Ready --> Conflict: Commit precondition fails
    Accepted --> Aborted
    Materializing --> Aborted
    Repairing --> Aborted
    Committed --> [*]
    Rejected --> [*]
    Conflict --> [*]
    Aborted --> [*]
~~~

“Ready” does not mean the result has been committed. A RESULT message must distinguish materialization complete, validation passed, and commitment complete.

### 10.3 Liveness and fallback

The receiver can abort when dependencies, policy, budgets, or deadlines prevent completion. Fallback should produce an eligible alternative under the same bound Contract, or fail explicitly. A Contract amendment is a separate negotiation with a new Contract identity.

A literal fallback is useful only when the required representation, authority, resources, and delivery path are actually available. No fallback is assumed to guarantee eventual completion.

## 11. Validation and evidence

### 11.1 Three distinct questions

1. **Identity:** Are these the expected bytes or canonical content?
2. **Acceptance:** Does this output meet the Contract's predicates for the requested scope or milestone?
3. **Authority:** Is this participant allowed to make the proposed state transition?

Do not collapse them into one “verified” flag.

Exact-output validation requires an authenticated expected digest. Comparing an artifact to a digest supplied solely by the same untrusted source establishes internal consistency, not the publisher's intended output.

Approximate-output validation requires a declared reference, metric, invariant set, and checker policy. A decoder name or confidence score is not sufficient evidence of fidelity.

### 11.2 Evidence binding

An evidence record should identify:

- Target and Contract.
- Scope or milestone.
- Actual realized output digest.
- Reference identity and applicable baseline.
- Predicate identity, version, threshold, and units.
- Validator identity and version.
- Measured result or verifiable supporting data.
- Checker identity and authentication.
- Relevant environment, policy, freshness, and sampling information.

A distributional or statistical predicate needs a specified population, sampling procedure, uncertainty interpretation, and permitted error risk. Do not claim a probabilistic guarantee merely by attaching a confidence number.

### 11.3 Where checking can occur

The receiver can check a predicate when it has the needed inputs. Otherwise the Contract must name an accepted checker, proof procedure, or evidence path.

Sender-side validation of the sender's reconstruction does not automatically certify a different receiver-side reconstruction. Evidence must cover the actual output accepted, or a formally specified procedure must establish the relationship.

A pinned decoder identifier alone may not eliminate floating-point or runtime differences. Exactness requires a profile capable of enforcing the relevant determinism or an output check that rejects divergence.

### 11.4 Global predicates and validation reuse

Independent per-node checks do not necessarily imply whole-object correctness. Examples include cross-object clearance, unit consistency, aggregate numerical bounds, referential integrity, and mutually constrained field values.

Reuse validation results only if all relevant inputs, reference identities, validator versions, policy conditions, and required freshness remain suitable. A changed branch can invalidate a global predicate even when other branch bytes are unchanged.

### 11.5 Meaning of a receipt

A signed receipt proves who signed the bound statement, subject to the signature and trust model. It does not prove arbitrary semantic claims by itself.

The proposed safety property is conditional: conforming endpoints apply the acceptance procedure correctly, and the procedure's validators and trust assumptions are adequate for the claimed fidelity.

## 12. Localized repair

### 12.1 Repair procedure

1. Identify the failed node, predicate, or unavailable dependency.
2. Retain the previous committed state.
3. Preserve independently usable staged artifacts and evidence.
4. Determine the affected execution and validation dependencies.
5. Select an agreed alternative, or negotiate a revised Plan under the same Contract.
6. Reconstruct affected outputs.
7. Reevaluate all predicates whose relevant inputs changed.
8. Commit only after the requested output or milestone is accepted.

Possible failures include missing baselines, unsupported decoders, procedural divergence, resource exhaustion, integrity failures, unacceptable residual error, and expired evidence or authorization.

### 12.2 What repair may preserve

Materialization work can be retained when its concrete inputs and output identity remain applicable. Evidence can be retained only under its own validity conditions.

A changed Plan may alter descriptor hashes and graph references without forcing all unchanged artifacts to be regenerated. Distinguish graph-description updates from changes to artifact bytes.

### 12.3 Immutability and fallback

An accepted Plan is immutable. A repair either selects an alternative already bound into it or creates a new Plan with an explicit parent/derivation relationship.

A lower-fidelity replacement is eligible only if the existing Contract already permits it for the relevant scope or milestone. Otherwise it requires a Contract amendment. A failed node never authorizes silent weakening of a predicate.

## 13. Replaceable updates and shared-work cancellation

### 13.1 Separate three revision domains

| Revision domain | What changes |
|---|---|
| Target revision | The publisher's logical object |
| Interest/request revision | What a receiver currently needs from an object |
| Plan revision or replacement | How the requested result will be reconstructed |

The application example of a camera jump normally changes interest. It is not a protocol-level camera event and need not change the Target.

### 13.2 Supersession rule

A Contract or bound application profile defines when one update supersedes another for a specific consumer or demand.

If an unfinished older demand is explicitly replaceable:

- Its delivery obligation may be retired.
- Completed reusable dependencies remain reusable.
- Work still needed by any remaining demand must be preserved.
- A valid reconstruction path to the new demand must exist or be supplied.
- Acceptance still uses the bound Contract.

Sequence order alone does not make replacement valid.

### 13.3 Required transitions

Required updates cannot be semantically discarded. They may be compressed, batched, or delivered through an equivalent declared representation only when the profile preserves all required effects and evidence.

Required updates may include transactions, audit events, or application operations whose intermediate transitions matter. The exact classification belongs to the application profile.

### 13.4 Shared work

Cancel a demand, then recompute the live dependency closure across all remaining demands. Do not cancel a shared generator merely because one receiver no longer needs its result.

Active checkpoint work, pinned dependencies, and other accepted retention obligations also count as roots. Cache eviction is a separate policy from cancellation of unfinished work.

### 13.5 State changes during execution

The scheduler must reevaluate liveness when demands arrive or are superseded. A race between cancellation and a newly attached consumer needs synchronization at the work registry. A late result can still be retained as cache content if allowed, but must not be misreported as fulfilling a canceled request.

## 14. Commitment, receipts, and authority

### 14.1 Initial authority model

Use one designated publisher for v0.1. Receivers and repeaters may propose changes, reconstruct results, and commit authorized local state. Writing back to the publisher is a separate explicitly authorized operation.

Successful reconstruction does not grant write authority. A checkpoint publisher role likewise requires authorization; its creation does not make an intermediate node the owner of the original Target.

### 14.2 Three-stage commitment model

1. **Validation approval:** Records accepted evidence for one specified output and proposed transition.
2. **Atomic local commit:** Updates the visible state only if its expected current-state precondition holds.
3. **Commit receipt:** Records the durable outcome of that transition.

The logical stages need not each require a network round trip. A crash-safe implementation must durably link the output identity, approval, and transaction outcome so a post-crash receipt can be recovered or completed.

Do not claim “committed” before the transition occurs. Do not require a record asserting completed commitment to exist before that same commitment has happened.

### 14.3 Idempotence and conflicts

Retries use a stable transaction identity. Repeating a successful request returns the same outcome rather than applying it again.

A compare-and-swap-style precondition can ensure the current accepted state still matches the one against which the update was authorized. Define the meaning of the local head precisely: it may need Target revision, Contract, scope, and concrete output identity, not merely one revision number.

If the head changed, retain the reconstructed artifact if permitted but report a conflict. Replanning or a new authorized transition can follow.

### 14.4 Receipt contents

A full receipt should bind:

- Protocol/profile version.
- Target and Contract identities.
- Scope or milestone.
- Final applicable Plan and relevant rewrite/repair ancestry.
- Realized Output identity.
- Validation approval and evidence references.
- Signer and authority/delegation context.
- Transaction ID and expected prior state.
- Actual commit state and outcome.

A milestone receipt explicitly limits the accepted uses. A scoped receipt cannot imply that an entire Target is accepted.

## 15. Authorized repeater fabric

### 15.1 Definition

An ARFP repeater is an explicitly authorized intermediate participant that may cache identified artifacts, partially materialize requested results, rewrite eligible Plans, and deliver results to downstream receivers.

It is neither the original publisher nor necessarily the final consumer. It remains bound to the original agreement and the scope of its delegation.

Repeaters can be application services deployed on ordinary servers, edge machines, or organizational gateways. No special router hardware or change to IP forwarding is required for an initial overlay implementation.

### 15.2 Advertised capabilities

A RepeaterCapability can describe:

- Cache capacity, relevant content availability, and eviction behavior.
- Supported codecs, generators, decoders, models, and execution environments.
- Resource availability and concurrency.
- Checker capabilities and trust domain.
- Permitted recipients or downstream affinity.
- Applicable authorization/delegation references.

Self-advertised capability or trust labels do not grant authority. The applicable grants and receiver policy determine what may be accepted.

### 15.3 Repeater operations

| Operation | Behavior | Constraint |
|---|---|---|
| Dependency caching | Store identified artifacts and associated evidence | Recheck applicability and access for each request |
| Partial materialization | Compute a scoped dependency closure | Preserve explicit scope and required hidden dependencies |
| Plan rewriting | Replace eligible representations or execution placement | Preserve Contract meaning; record new Plan identity and provenance |
| Shared preparation | Generate a reusable artifact for several receivers | Preserve each receiver's acceptance and authorization requirements |
| Milestone delivery | Prioritize accepted intermediate stages | Grant only the milestone's declared uses |
| Supersession handling | Retire obsolete replaceable demand | Keep work needed by other demands |
| Checkpoint emission | Offer a common baseline | Bind actual bytes, relevant evidence, and authority |

Pure caches need not execute content. Compute repeaters may execute only eligible operations. Neither role may silently amend the Contract.

### 15.4 PlanRewrite record

A rewrite record should bind:

- Original and replacement Plan identities.
- Repeater identity and delegation.
- Target, Contract, scope, and affected logical outputs.
- Changed representations, dependencies, and placements.
- Previously validated artifacts and their applicable evidence.
- Operations still awaiting execution or validation.

A signature authenticates the rewrite assertion. It does not certify future unexecuted outputs. If plans combine previously independent work, provenance may form a DAG rather than one linear receipt chain.

### 15.5 Bounded delegation

A proposed DelegationGrant contains:

| Field | Meaning |
|---|---|
| Target/Contract binding | Which reconstruction agreement applies |
| Scope and operations | What may be obtained, transformed, executed, or checked |
| Participant or eligible class | Who may act under the grant |
| Eligible recipients | Who may receive outputs |
| Expiry or authorization epoch | When authority must be reevaluated |
| Further-delegation rule | Whether and how another repeater may participate |
| Resource allocation | What work and transfer budget is allocated |
| Issuer and authentication | Who granted the authority |

A child grant can narrow a parent's permissions, not enlarge them. Copying the same remaining budget to several workers must not multiply the total permitted expenditure.

A session coordinator is a proposed practical first mechanism for allocating budgets and assigning work. More distributed budget enforcement is an open extension.

### 15.6 Evidence forwarding

A repeater may forward original evidence unchanged. It may add its own authenticated assertions within its authority, but must not erase original checker identity or silently strengthen the claim.

Re-attestation needs defined semantics: it can mean “I verified this evidence under policy X,” not automatically “I independently recomputed every underlying result.”

### 15.7 Multi-hop fidelity

Per-hop success does not imply end-to-end acceptance. Successive approximations must be checked against the Contract's designated reference or a sound composition rule.

For compatible metric spaces, error bounds may sometimes compose through a triangle inequality. Perceptual scores, learned quality judgments, and many statistical checks do not automatically support that rule.

Deltas and residuals at each hop need exact baseline identity or explicit semantic applicability conditions. A new transformation creates a new output identity and may require fresh evidence.

### 15.8 Forwarding, discovery, and loops

An acyclic execution DAG does not prevent a repeater routing loop. Requests need bounded forwarding, stable request identities, duplicate suppression, and clear responsibility for retries.

Initial discovery can use explicitly configured repeaters. Automatic discovery, topology selection, and broad federation remain open.

### 15.9 Encryption and access

A cache can store and forward encrypted artifacts without interpreting them. A compute repeater needs an explicitly authorized way to access the content required for its operations. The design does not imply transparent computation on arbitrary end-to-end encrypted content.

Digest-based deduplication is not itself an access-control mechanism. Authorization applies to disclosure, execution, evidence access, and reuse.

## 16. Optional session extensions

These ideas extend the concept but need not all be implemented in v0.1.

| Extension | Mechanism | Intended benefit |
|---|---|---|
| Independently accepted milestones | Bind staged output roots, predicates, and permitted uses | Earlier useful availability |
| Scoped interest | Request only needed portions or projections | Avoid unnecessary materialization |
| Lookahead dependency investment | Weigh a dependency's initial cost against expected future reuse | Cheaper repeated updates |
| Execution placement | Choose publisher, receiver, or authorized intermediate worker | Match compute and transfer to actual conditions |
| Shared receiver planning | Factor common work across several eligible Plans | Avoid repeated preparation |
| Replaceable-update coalescing | Retire obsolete unfinished demand under profile rules | Avoid processing stale state |
| Shared checkpoints | Bring selected outputs to a common exact baseline | Reduce divergence and future delta specialization |
| Validation-aware planning | Include evidence availability and checking cost in selection | Reduce cost to accepted output |
| Dependency leases | Reserve required cached content for a bounded interval | Reduce mid-execution cache misses |
| Measured selector adaptation | Learn from actual execution and repair outcomes | Improve decisions without changing protocol semantics |

### 16.1 Checkpoint tradeoff

Receivers with different accepted approximations can accumulate separate histories. A common exact checkpoint for a frequently updated subgraph may make future patches cheaper.

Compare the checkpoint transfer and computation cost against the cost of maintaining separate histories. Adoption is an explicit local transition, not an automatic global write. Checkpoint scope, baseline identity, and evidence must be unambiguous.

### 16.2 Keep the protocol and optimizer separate

The protocol defines permissible objects, messages, evidence, and state transitions. It does not require one particular search algorithm, learned policy, cache replacement strategy, or scheduling heuristic.

Extensions should add declared profile semantics or optional capabilities rather than silently changing how existing fields are interpreted.

## 17. Mathematical model

This is a proposed formal vocabulary for the architecture. It specifies useful invariants and accounting rules. It does not prove that any implementation has correct validators, reliable scheduling, or improved performance.

### 17.1 Symbols

| Symbol | Meaning |
|---|---|
| $T$ | Logical Target and publisher revision |
| $C$ | Immutable bound Contract |
| $\sigma$ | Canonical requested scope, including applicable milestone |
| $S_r$ | Receiver $r$'s relevant capabilities and state |
| $P$ | A chosen reconstruction Plan |
| $y$ | Actual realized output |
| $e$ | Validation evidence |
| $H$ | Agreed content-digest function |
| $\operatorname{canon}$ | Profile-defined canonicalization or serialization |
| $x_{T,\sigma}$ | Contract-designated reference for the requested output |
| $\tau$ | Observed execution trace, including resource use |
| $\mathcal D$ | Active demands and explicit work-retention obligations |

Digest algorithms, canonicalization rules, and exact reference formats are open protocol-profile decisions. Equations involving hashes assume suitable authenticated bindings and the selected digest's security properties.

### 17.2 Output acceptance

Define the Contract's semantic acceptance predicate:

$$
F_C(T,\sigma,y)\in\{0,1\}.
$$

For exact reconstruction:

$$
F_C(T,\sigma,y)=
\left[
H(\operatorname{canon}(y))=h_{T,\sigma}
\right]
\land
\bigwedge_j I_{C,j}(y).
$$

The expected digest $h_{T,\sigma}$ must be authenticated. Canonical equality and raw byte equality are different requirements; the Contract identifies which applies. Additional invariants are included only where the profile requires them.

For approximate reconstruction:

$$
F_C(T,\sigma,y)=
\left[
d_C(y,x_{T,\sigma})\leq\varepsilon_C
\right]
\land
\bigwedge_j I_{C,j}(y).
$$

Here $d_C$ is a specified error measure, $\varepsilon_C$ is its acceptance threshold, and the $I_{C,j}$ terms are mandatory invariants. More complex profiles can define multiple metrics rather than one scalar.

Different accepted realizations can satisfy:

$$
y_1\neq y_2,\qquad
F_C(T,\sigma,y_1)=F_C(T,\sigma,y_2)=1.
$$

That establishes compatibility with the same acceptance criteria, not equality of the outputs or interchangeable patch baselines.

### 17.3 Plan eligibility and execution

Represent a Plan as:

$$
P=(G,\rho,\ell,\pi),
$$

where $G=(V,E)$ is the dependency DAG, $\rho$ selects node representations, $\ell$ selects authorized execution locations, and $\pi$ specifies a schedule or scheduling policy.

The planner selects:

$$
P\in\mathcal P_{\mathrm{eligible}}(T,C,\sigma,S_r).
$$

Eligibility requires permitted operations, declared resolvable dependencies, authority, supported profiles, and enforceable resource limits. Some feasibility information is estimated from current state. Eligibility does not establish successful future execution.

Actual execution has the form:

$$
\operatorname{Execute}(P,S_r)\rightarrow(y,\tau)
\quad\text{or}\quad
\operatorname{Execute}(P,S_r)\rightarrow(\bot,\tau).
$$

The failure outcome $\bot$ includes explicit abort or exhaustion of permitted repair.

For a dependency edge $u\rightarrow v$, scheduling must respect:

$$
s_v\geq f_u+t_{u,v},
$$

where $s_v$ is the start of $v$, $f_u$ is the completion of $u$, and $t_{u,v}$ is the time required to make its output available at $v$'s execution location. Network contention and queueing affect these times.

A critical-path calculation alone is insufficient when operations compete for compute, memory, bandwidth, or validators. Retained inputs and outputs consume memory or storage even when their producer operations are no longer running.

### 17.4 Evidence and commitment

Define:

$$
V_C(T,\sigma,y,e)=1
$$

when the specified verifier accepts the evidence for the concrete output.

Let $A_C(a,\mathrm{commit},T,\sigma)$ express the committer's authority, $R_C(\tau)$ express required execution/resource compliance, and $B_C$ express the actual commit precondition.

The proposed invariant is:

$$
\operatorname{Commit}(a,T,C,\sigma,P,y,e,\tau)
\Rightarrow
V_C(T,\sigma,y,e)
\land A_C(a,\mathrm{commit},T,\sigma)
\land R_C(\tau)
\land B_C.
$$

To infer semantic fidelity from accepted evidence, a sound verifier must provide the relevant implication under its declared assumptions:

$$
V_C(T,\sigma,y,e)=1
\Rightarrow F_C(T,\sigma,y)=1.
$$

The protocol cannot manufacture that implication by signing a receipt. Where a profile offers statistical rather than deterministic assurance, it must specify the experiment, adversarial assumptions if relevant, and the precise guarantee being claimed. There is no generic confidence percentage valid for all validators.

### 17.5 Baseline applicability

For a Delta or Residual node $v$, define:

$$
\operatorname{ValidBase}_v(y_b)=
\left[H(\operatorname{canon}(y_b))=h_{b,v}\right]
$$

for an exact baseline, or a profile-defined semantic predicate:

$$
\operatorname{ValidBase}_v(y_b)=Q_v(y_b)
$$

when the operation is expressly valid across several representations.

The second form needs a justified operation semantics and acceptance check. It is not a general permission to patch any output bearing the same Target identity.

### 17.6 Replaceability

Describe an update or request as:

$$
u_k=(s,k,T_k,\sigma_k),
$$

where $s$ identifies a stream and $k$ orders requests within that stream. $T_k$ may remain unchanged when only interest changes.

The Contract/profile defines:

$$
u_j\prec_C u_k
$$

to mean that the newer request supersedes the older outstanding delivery obligation for the relevant consumer.

The condition $k>j$ alone is insufficient. Supersession cannot erase required-transition semantics. Removing a delivery obligation does not remove dependencies still needed by the new request.

### 17.7 Live work and cancellation

Use a graph of concrete work identities that includes execution and validation dependencies. Different Plans may refer to the same reusable work only when its operation and input bindings actually match.

Define:

$$
L(\mathcal D)=
\operatorname{DependencyClosure}
\left(\operatorname{Roots}(\mathcal D)\right).
$$

If demand $d_j$ is superseded by $d_k$:

$$
\mathcal D'=
(\mathcal D\setminus\{d_j\})\cup\{d_k\}.
$$

Newly eligible cancellation candidates are:

$$
W_{\mathrm{cancel}}=
\left[L(\mathcal D)\setminus L(\mathcal D')\right]
\cap W_{\mathrm{unfinished}}.
$$

This is a permission to cancel work no longer needed, not a guarantee that cancellation is instantaneous. Apply the update atomically relative to attaching new consumers. Contractually pinned work and active checkpoint obligations must appear among the roots.

Example:

| Demand | Required work |
|---|---|
| Receiver A, old | $a,b,c$ |
| Receiver B, continuing | $b,d$ |
| Receiver A, new | $a,e$ |

After replacing A's old demand, $a,b,d,e$ remain live. Only unfinished $c$ becomes newly cancelable. Completed artifacts can remain cached according to retention policy.

### 17.8 Repair closure

Let $G^+$ include all relevant execution and validation dependencies. For a changed or failed node $v$:

$$
\operatorname{Affected}(v)=
\{v\}\cup\operatorname{Descendants}_{G^+}(v).
$$

A whole-output acceptance predicate depends on all inputs it examines and is therefore affected when any such input changes. A sound incremental validator can reduce its recomputation cost; the dependency cannot simply be ignored.

Structural Plan changes require new graph bindings even where some actual artifacts and evidence remain reusable.

### 17.9 Planner objective with failure accounting

For a deadline $D$, one candidate objective is:

$$
P^*=
\arg\min_{P\in\mathcal P_{\mathrm{eligible}}}
\left\{
\mathbb E[\min(T_{\mathrm{valid}}(P),D)]
+
w_F\,\Pr(T_{\mathrm{valid}}(P)>D)
\right\}.
$$

Set $T_{\mathrm{valid}}=\infty$ when the complete permitted attempt never produces an accepted result. $w_F$ is a failure penalty expressed in time-equivalent units. Repair and retry must be included in the attempt being measured.

This objective is optional implementation policy. It avoids treating failed attempts as free or excluding them from statistics. The penalty never permits an unacceptable output to be committed.

Measured or predicted probabilities are planning estimates, not protocol guarantees. A hard deadline can require aborting an unsuccessful attempt; it does not guarantee that an eligible result will exist before that deadline.

### 17.10 Multi-hop approximation

For successive realizations $x_0,\ldots,x_n$ in a common space with a distance satisfying the triangle inequality:

$$
d(x_0,x_n)\leq
\sum_{i=1}^{n}d(x_{i-1},x_i).
$$

If each term has a justified upper bound $\varepsilon_i$, an eligible composed budget may require:

$$
\sum_{i=1}^{n}\varepsilon_i\leq\varepsilon_C.
$$

This applies only when the metric, domains, and transformations support the reasoning. A general alternative is final checking against $x_{T,\sigma}$. Independent local quality scores cannot be assumed to compose.

### 17.11 Delegation and budgets

Represent permitted actions as sets. A proposed child-grant rule is:

$$
\mathcal A_{\mathrm{child}}
\subseteq
\mathcal A_{\mathrm{parent}}\cap\mathcal A_C.
$$

The participant's local policy can narrow the effective permissions further.

For allocations $b_i$ from one finite parent budget $B$:

$$
\sum_i b_i\leq B.
$$

Allocated and spent amounts need consistent bookkeeping. Reissuing a grant or retrying an operation must not accidentally reset spent resources. This is an accounting invariant; a decentralized enforcement mechanism has not been selected.

### 17.12 Traffic accounting

For measured delivery links $\mathcal L$:

$$
B_{\mathrm{fabric}}=
\sum_{\ell\in\mathcal L}B_\ell.
$$

Count all actual payload, dependency, envelope, evidence, repair, and retry traffic on those links. Report origin egress separately.

Illustration, with ordinary separate transfers and no extra compression or multicast:

- Origin sends one 20 MB artifact to a repeater.
- Repeater sends it to each of two receivers.
- Origin egress is 20 MB.
- Total measured traffic is $20+20+20=60$ MB.
- Two direct copies would be 40 MB total and 40 MB origin egress.

The example demonstrates an accounting distinction, not a performance result. Latency and origin load can improve while total link traffic rises.

### 17.13 Receipt binding

A conceptual receipt signature can cover:

$$
R=\operatorname{Sign}_a
\left(
H(T),H(C),H(\sigma),H(P),H(y),H(e),
\operatorname{CommitRecord}
\right).
$$

The signed encoding must be unambiguous and versioned. Define exactly which fields are inside each digest and signature. Do not introduce recursive self-hashing by including an object's own digest inside the bytes that define that same digest.

A receipt binds the statement to the identified signer. Its acceptance still depends on the authorization and evidence policies.

## 18. Illustrative object shapes

These examples are descriptive JSON, not a finalized wire schema or valid conformance fixtures. Names, numerical values, digest strings, and runtime labels are illustrative. SHA-256 syntax here is an example, not a negotiated algorithm decision. No supplied placeholder is a real signature, digest, or measurement.

Production encoding must define canonicalization, type rules, required fields, unknown-field behavior, units, and the exact signed payload.

### 18.1 Contract content

~~~json
{
  "profile": "example-profile-v1",
  "target_ref": "target:example-object:revision-42",
  "scope": {
    "scope_id": "scope:requested-components",
    "selection": ["component-a", "component-b"]
  },
  "permitted_node_classes": [
    "reference", "delta", "procedural",
    "latent", "residual", "literal"
  ],
  "acceptance": {
    "reference_ref": "reference:publisher-approved",
    "predicates": [
      {
        "id": "example-numeric-bound-v1",
        "units": "profile-defined",
        "maximum_error": 0.001,
        "validator_ref": "validator:approved-v1"
      },
      {
        "id": "required-identifiers-preserved-v1",
        "validator_ref": "validator:schema-v1"
      }
    ]
  },
  "execution_limits": {
    "memory_bytes": 268435456,
    "maximum_repair_attempts": 2
  },
  "evidence_policy_ref": "policy:evidence-v1",
  "authority_policy_ref": "policy:authority-v1",
  "update_policy_ref": "policy:replaceable-state-v1"
}
~~~

The resource limits are example values only. A Contract can use multiple predicates and separately classify exact and approximate components.

### 18.2 Plan content

~~~json
{
  "target_ref": "target:example-object:revision-42",
  "contract_ref": "sha256:CONTRACT_DIGEST_PLACEHOLDER",
  "scope_ref": "sha256:SCOPE_DIGEST_PLACEHOLDER",
  "receiver_state_ref": "state:receiver-a:snapshot-17",
  "profile": "example-profile-v1",
  "environment_requirements": [
    {
      "operation": "example-delta-v1",
      "runtime_ref": "sha256:RUNTIME_DIGEST_PLACEHOLDER"
    }
  ],
  "nodes": [
    {
      "node_id": "base",
      "type": "reference",
      "artifact_ref": "sha256:BASE_OUTPUT_DIGEST_PLACEHOLDER",
      "dependencies": []
    },
    {
      "node_id": "updated",
      "type": "delta",
      "operation": "example-delta-v1",
      "dependencies": ["base"],
      "base_output_ref": "sha256:BASE_OUTPUT_DIGEST_PLACEHOLDER",
      "payload_ref": "sha256:DELTA_PAYLOAD_DIGEST_PLACEHOLDER",
      "execution_location": "receiver-a",
      "validation_predicates": ["example-result-check-v1"]
    }
  ],
  "output_roots": ["updated"],
  "fallback_policy_ref": "policy:repair-v1"
}
~~~

Environment and payload references are explicit dependencies even if encoded separately from node-to-node edges. Their acquisition must be included in the effective dependency closure and cost model. The profile must define how root outputs form the realized object.

### 18.3 Validation approval

~~~json
{
  "kind": "validation-approval",
  "target_ref": "target:example-object:revision-42",
  "contract_ref": "sha256:CONTRACT_DIGEST_PLACEHOLDER",
  "scope_ref": "sha256:SCOPE_DIGEST_PLACEHOLDER",
  "plan_ref": "sha256:FINAL_PLAN_DIGEST_PLACEHOLDER",
  "output_ref": "sha256:ACTUAL_OUTPUT_DIGEST_PLACEHOLDER",
  "evidence_refs": ["sha256:EVIDENCE_DIGEST_PLACEHOLDER"],
  "transaction_id": "example-transaction-27",
  "expected_local_head_ref": "head:receiver-a:previous",
  "authority_ref": "grant:receiver-a-local-commit",
  "decision": "approved-for-local-commit",
  "issuer": "checker:accepted",
  "signature": "SIGNATURE_PLACEHOLDER"
}
~~~

### 18.4 Commit receipt

~~~json
{
  "kind": "commit-receipt",
  "transaction_id": "example-transaction-27",
  "target_ref": "target:example-object:revision-42",
  "contract_ref": "sha256:CONTRACT_DIGEST_PLACEHOLDER",
  "scope_ref": "sha256:SCOPE_DIGEST_PLACEHOLDER",
  "plan_ref": "sha256:FINAL_PLAN_DIGEST_PLACEHOLDER",
  "output_ref": "sha256:ACTUAL_OUTPUT_DIGEST_PLACEHOLDER",
  "approval_ref": "sha256:APPROVAL_DIGEST_PLACEHOLDER",
  "prior_head_ref": "head:receiver-a:previous",
  "committed_head_ref": "head:receiver-a:current",
  "commit_record_ref": "record:durable-transition-27",
  "status": "committed",
  "signer": "receiver-a",
  "signature": "SIGNATURE_PLACEHOLDER"
}
~~~

A full-result receipt and a milestone receipt must have distinguishable scope and status semantics. Implementations must not infer that the illustrative signature strings are cryptographic examples.

### 18.5 Canonicalization questions still open

- JSON with a specified canonical form versus a binary encoding such as a defined CBOR profile.
- Identity treatment for integer versus floating-point representations.
- NaN, infinities, negative zero, Unicode, absent fields, and default values.
- Domain-separated digests or signatures for different object kinds.
- Large payload chunking and graph-descriptor limits.
- Whether node IDs are local labels, descriptor digests, or both.
- Exact handling of optional extensions and unsupported required features.

These choices affect interoperability and must be resolved before independent encoders can reliably exchange signed or content-addressed objects.

## 19. Reference processing algorithm

The following is pseudocode for responsibilities and ordering. It is not shipped implementation code.

~~~text
handle_offer(offer, local_policy):
    authenticate target, contract, offer, and applicable delegation
    verify supported versions, profiles, scope, and node operations
    validate graph structure and all explicit dependency declarations
    check authority and resource admission against local policy
    record the state snapshot used for this attempt
    register this demand in the shared-work registry
    accept an eligible attempt, or return a specific rejection

materialize(attempt):
    while the demand remains active and its budget permits:
        resolve ready artifacts and environment dependencies
        verify retrieved content identities and access policy
        execute only approved operations in staging
        attach actual output identities and provenance
        evaluate ready predicates when their inputs are available

        if a node or predicate fails:
            compute affected execution and validation closure
            keep independent reusable artifacts
            choose an already permitted fallback or negotiate a new plan
            if no eligible repair remains:
                abort the attempt without changing the committed head

        if the requested output or milestone passes all required checks:
            produce a validation approval for the actual realized output
            return ready_to_commit

on_supersede(old_demand, new_demand):
    verify that the contract/profile permits this supersession
    atomically update the active-demand registry
    recompute live work across all receivers and retention obligations
    cancel only unfinished work no longer required
    preserve completed artifacts according to retention and access policy
    begin or attach to the valid reconstruction path for the new demand

commit(approval, transaction_id):
    verify approval, scope, authority, actual output identity, and evidence
    if transaction_id already has a durable outcome:
        return that outcome

    perform one crash-safe local transition:
        require the expected local head still matches
        persist the approval reference, output binding, and commit record
        update the visible local head atomically

    sign or recover a receipt from the actual durable commit record
    return the committed outcome
~~~

### 19.1 Proposed internal components

- Object/Contract registry and canonical encoding.
- Content-addressed artifact store.
- Evidence and provenance store.
- Capability and state manager.
- Candidate-plan generator and cost estimator.
- Dependency scheduler and shared-work registry.
- Bounded operation executor.
- Validator registry.
- Repair coordinator.
- Local transaction/receipt journal.
- Transport adapter.
- Optional repeater delegation and placement coordinator.

These are conceptual responsibilities, not a requirement for separate services. A small prototype can implement many in one process.

### 19.2 Proposed error vocabulary

Define machine-readable failures for unsupported profile, unsupported operation, missing dependency, baseline mismatch, integrity failure, permission denial, resource limit, validation failure, stale state, expired authority, commit conflict, canceled demand, and exhausted repair.

Exact codes and retry semantics are open. Error messages must identify the relevant attempt, node or predicate, and applicable Plan without granting new authority by implication.

## 20. Demonstration and benchmark design

### 20.1 Initial workload

Use repeated updates to a structured 3D scene. This is a demonstration profile, not the protocol's domain definition.

| Content | Representation to exercise |
|---|---|
| Cached static buildings or assets | Reference |
| Changed positions or structured properties | Delta |
| Repeated geometry | Procedural |
| Textures with explicitly permitted approximation | Latent |
| Sparse geometric corrections | Residual |
| Previously unseen assets | Literal |

Begin with deterministic and exact operations. Add learned decoding after identity, evidence, repair, and commit behavior can be tested. The six representation classes remain part of the design even if the first executable slice supports fewer.

### 20.2 Topology and participant behavior

Use one publisher, one authorized repeater, and two receivers with intentionally different capabilities or caches.

- A constrained receiver can receive a pre-materialized artifact.
- A capable receiver can receive an approved generator and parameters.
- Both must satisfy their bound common acceptance requirements for comparable outputs.
- Milestones may authorize different stages, but comparisons must identify those stages.
- Shared dependencies remain available across subsequent updates.
- A changed interest supersedes only the appropriate request.
- The repeater preserves work still required by the other receiver.

The key shared-work demonstration is one receiver changing its requested scope while the other still needs work associated with the previous demand.

### 20.3 Baselines

| Comparison | Purpose |
|---|---|
| Full conventional compressed transfer | Establish a simple complete delivery baseline |
| Delta transfer against known baselines | Isolate change-based reuse |
| Content-addressed reference reuse | Isolate cache reuse |
| Fixed hybrid with the same available representations | Measure the added value of adaptive selection |
| Direct ARFP without repeater | Separate protocol behavior from intermediate placement |
| ARFP through a cache-only repeater | Isolate caching benefits |
| ARFP through a compute/rewrite repeater | Evaluate shared preparation and placement |
| Optional simple greedy selector | Compare a basic policy with a more elaborate planner |

Do not compare one system's complete validated output with another system's partial preview and call the difference a transfer speedup. Keep fidelity, scope, initial state, dependencies, and resource accounting comparable.

### 20.4 Required measurements

- Origin egress.
- Total bytes across measured delivery links.
- Payload, dependency, envelope, and evidence bytes.
- Time to first accepted permitted use.
- Time to final validated availability.
- Time to durable local commit.
- Receiver and repeater computation.
- Peak memory and retained storage.
- Planning and negotiation overhead.
- Validation and checker cost.
- Repair and retry cost.
- Canceled, discarded, and reused work.
- Success, abort, conflict, and deadline-miss counts.
- Latency distributions, including tail behavior.
- Cache state and hit/miss attribution.

Count failed attempts. Do not omit model downloads, prewarming, checkpoint traffic, or external checker work.

### 20.5 Conditions and fault cases

Run cold-cache and warm-cache conditions. Explicitly define what is preinstalled and why. Exercise:

1. A repeated stable workload.
2. A missing shared dependency.
3. An evicted or stale baseline.
4. A decoder/runtime mismatch.
5. Procedural output divergence.
6. A failed acceptance predicate.
7. A changed interest during shared computation.
8. A slower or resource-constrained receiver.
9. A lost acknowledgment or crash around commit.
10. A later multi-hop case testing end-to-end fidelity.

Repeated trials and reproducible fixtures should establish whether gains survive workload and cache variation. No numeric success threshold or performance claim has been agreed yet.

### 20.6 Candidate domains beyond the demonstration

Earlier discussion also considered VR/3D streaming, engineering/CAD collaboration, simulation or telemetry review, and program-to-program assistance. Large structured datasets with repeated updates are another plausible evaluation class.

Each domain needs appropriate adapters, profiles, references, and validators. Success on scene delivery does not establish suitability for every dataset or safety-critical use.

## 21. Conformance cases

The next technical deliverable proposed in the conversation is a small executable conformance suite. This table defines intended behavior to test; it is not a report of passing tests.

| ID | Case | Required outcome |
|---|---|---|
| C01 | Two different eligible Plans target the same exact output | Both produce the authenticated expected content identity |
| C02 | Two approximate outputs satisfy the same Contract | Both can be accepted, with distinct concrete output identities |
| C03 | Patch targets one receiver's different approximate baseline | Reject unless exact baseline identity or declared semantic applicability passes |
| C04 | Dependency missing after Plan acceptance | Repair or abort; no premature commit |
| C05 | Unknown required node type or profile | Reject or renegotiate explicitly |
| C06 | Wrong decoder/model/runtime binding | Reject execution or fail validation and repair |
| C07 | Procedural result diverges | Preserve prior committed state; obtain eligible fallback or abort |
| C08 | Residual exists but corrected error exceeds bound | Reject the corrected output |
| C09 | Local node checks pass but a global invariant fails | Reject the full output or affected milestone |
| C10 | One branch is repaired | Retain independent work; rerun all affected validation |
| C11 | Contract permits only exact output and fallback is approximate | Reject fallback or negotiate a new Contract |
| C12 | Accepted Plan is rewritten | Produce an identified replacement or use a prebound alternative |
| C13 | Scoped result is accepted | Receipt cannot authorize full-Target use |
| C14 | Milestone passes while full result remains incomplete | Permit only declared milestone uses |
| C15 | Receiver cancels demand needed by another receiver | Shared work remains live |
| C16 | Replaceable update is superseded | Retire only the allowed obligation and establish a valid new path |
| C17 | Required-transition stream is marked obsolete by a planner | Preserve required semantics; planner preference cannot override the profile |
| C18 | Old canceled result arrives late | Do not commit it as the new request's result |
| C19 | Local head changes before commit | Report conflict; do not overwrite the newer head |
| C20 | Successful commit acknowledgment is lost | Idempotent retry returns the same durable outcome |
| C21 | Crash occurs between validation and receipt delivery | Recover actual committed/aborted state without falsely asserting commitment |
| C22 | Cached artifact has evidence for a different Contract | Reassess evidence applicability rather than treating it as universally valid |
| C23 | Repeater lacks transform permission | Forward/cache only if allowed; do not execute the transformation |
| C24 | Child delegation broadens permissions or duplicates budget | Reject the unauthorized allocation |
| C25 | Repeater changes approximation at multiple hops | Enforce final reference check or justified composed bound |
| C26 | Repeater forwards request back into a loop | Bound or reject forwarding; no unbounded work expansion |
| C27 | Original evidence is forwarded or re-attested | Preserve provenance and the precise meaning of each assertion |
| C28 | Canonical encoding differs across independent implementations | Detect the incompatibility; resolve it before claiming interoperability |

At least two independently implemented encoders/decoders are a useful proposed interoperability milestone. This is a project validation goal, not a claim that a particular standards process mandates that exact number.

## 22. Trust and execution constraints

These are implementation requirements arising from the protocol's execution and delegation model.

- Authenticate the publisher's binding between Target revision, Contract, and expected references.
- Authenticate grants, evidence, and receipts under an explicitly configured trust policy.
- Verify actual retrieved bytes against required identities.
- Apply authorization at disclosure and execution time; cache membership does not authorize access.
- Pin operation, decoder, model, schema, and validator versions.
- Bound graph size, depth, fan-out, payload size, decompression, execution time, memory, and repair.
- Restrict procedural operations to approved behavior and declared dependencies.
- Keep arbitrary network, filesystem, and external side effects outside the default reconstruction executor.
- Treat any permitted side-effecting application operation as a separate explicitly defined profile with idempotence and authority rules.
- Enforce budgets across delegated work and retries.
- Detect stale baselines and state changes before commitment.
- Preserve scoped and milestone restrictions at application boundaries.
- Avoid disclosing an entire private cache inventory when a narrowly scoped query is sufficient.
- Preserve checker identity and evidence provenance through repeaters.
- Support request deduplication, bounded forwarding, and duplicate-safe processing.
- Define failure behavior when authority, evidence, or leases expire.

Transport encryption and artifact authentication address different parts of the system. The selected transport and identity infrastructure remain open. No blockchain, zero-knowledge proof system, trusted hardware, or specialized credential format is required by the current concept.

## 23. Prior work and source register

### 23.1 Positioning

ARFP combines techniques with substantial predecessors. The potential contribution is a common negotiated agreement across representation selection, reconstruction, fidelity evidence, repair, and authorized intermediate participation.

This is an architectural hypothesis. The discussion did not establish that the combination is unique, that a standard is needed, or that it outperforms existing systems.

The repeater extension makes Named Function Networking, Compute First Networking, and result-provenance work especially close comparisons. A novelty argument cannot rest only on content-addressed graphs, cached computation, intermediate execution, or signed provenance.

### 23.2 Comparison map

| Area | Existing contribution relevant to ARFP | ARFP question to investigate |
|---|---|---|
| VCDIFF and dictionary transport | Reconstruct targets using baselines or negotiated dictionaries | Does a common mixed-representation agreement improve coordination beyond a fixed reconstruction mechanism? |
| IPLD/GraphSync | Identify and synchronize selected content-addressed graph portions | How are execution alternatives, fidelity, and commit authority bound to the transferred graph? |
| Nix/Bazel | Explicit build inputs, recipes, execution, and cached outputs | What additional semantics are needed for mixed exact/approximate object reconstruction and continuing updates? |
| MPEG scene descriptions | Stream scene descriptions, media, and updates | Does ARFP provide useful cross-domain interoperability beyond domain-specific delivery? |
| Semantic communication research | Shared knowledge and learned reconstruction under fidelity objectives | Can multiple representation families interoperate under explicit acceptance and repair rules? |
| NDN/NFN/Compute First Networking | Named content, caching, computation placement, graphs, and reuse | What does ARFP add to negotiated fidelity and receiver-specific accepted realizations? |
| NFN result provenance | Make computation origins and providers visible | How does ARFP bind provenance to concrete output acceptance, approximation, and local commitment? |
| RATS and conditional HTTP updates | Separate evidence appraisal from policy; prevent stale conditional updates | Which established mechanisms can be reused rather than redesigned? |

These questions are research and implementation tasks, not assertions that all comparison systems lack those capabilities.

### 23.3 Sources consulted in the conversation

The sources below support the comparison facts. They are not evidence of ARFP's own performance. URLs are included directly so this Markdown remains portable.

| ID | Primary source | Relevance |
|---|---|---|
| S01 | [RFC 3284 — The VCDIFF Generic Differencing and Compression Data Format](https://www.rfc-editor.org/rfc/rfc3284.html) | Baseline-dependent delta reconstruction |
| S02 | [RFC 9842 — Compression Dictionary Transport](https://www.rfc-editor.org/rfc/rfc9842.html) | HTTP negotiation and use of shared compression dictionaries |
| S03 | [Filecoin specification — IPLD and GraphSync](https://spec.filecoin.io/libraries/ipld/) | Content-addressed graphs and selective graph synchronization |
| S04 | [Nix Reference Manual — Store Derivation and Deriving Path](https://nix.dev/manual/nix/2.35/store/derivation/index.html) | Declared inputs, build steps, and references to outputs |
| S05 | [Bazel — Remote Caching](https://bazel.build/remote/caching) | Action cache and content-addressed output storage |
| S06 | [MPEG — Scene Description and Application Engine](https://mpeg.chiariglione.org/standards/mpeg-4/scene-description-and-application-engine.html) | BIFS scene description, media delivery, and rendering |
| S07 | [MPEG — Can the scene description be changed?](https://mpeg.chiariglione.org/faq/can-scene-description-be-changed.html) | Scene updates and animation parameters |
| S08 | [End-to-End Generative Semantic Communication Powered by Shared Semantic Knowledge Base](https://arxiv.org/abs/2405.05738) | Learned reconstruction using shared knowledge |
| S09 | [RFC 9334 — Remote ATtestation procedureS Architecture](https://www.rfc-editor.org/rfc/rfc9334.html) | Evidence, verifier appraisal, trust, and relying-party policy |
| S10 | [RFC 9110 — HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html) | Conditional updates and transforming intermediaries |
| S11 | [RFC 9218 — Extensible Prioritization Scheme for HTTP](https://www.rfc-editor.org/rfc/rfc9218.html) | Urgency and incremental-processing signals |
| S12 | [OpenUSD — UsdStage reference](https://openusd.org/release/api/class_usd_stage.html) | Working-set and payload-loading control |
| S13 | [Bazel — Build without the Bytes](https://blog.bazel.build/2023/10/06/bwob-in-bazel-7.html) | Avoiding unnecessary intermediate-output downloads |
| S14 | [Named Data Networking — Motivation and Details](https://named-data.net/project/archoverview/) | Named content and network caching |
| S15 | [Sifalakis et al., 2014 — An information centric network for computing the distribution of computations](https://irf.fhnw.ch/entities/publication/80703636-f798-435d-a42f-d3f068c0c98e) | NFN computation distribution and cached result reuse |
| S16 | [Compute First Networking: Distributed Computing meets ICN](https://named-data.net/publications/compute/) | Distributed computation graphs and execution |
| S17 | [ACM ICN 2020 — Result Provenance in Named Function Networking](https://conferences.sigcomm.org/acm-icn/2020/accepted-papers.html) | Abstract describing result genesis and trust in computing providers |

Research referenced here was retrieved during the conversation. Some links are versioned or archival. Revisit primary sources before making a formal standards comparison or a broader novelty claim.

### 23.4 Standards direction

ARFP is a candidate protocol concept, not an adopted IETF work item or published standard.

A useful future standards-oriented package would contain a problem statement, explicit comparison with existing mechanisms, interoperable object/message definitions, security and authority semantics, implementation experience, and measured benefits.

No transport binding, IANA registration, URI scheme, mandatory codec suite, or final protocol namespace has been selected. Example identifiers in this document are illustrative.

## 24. Implementation sequence

This is a proposed progression that keeps the full concept intact while making each step reviewable.

### Stage 1 — Formalize the direct core

Deliver:

- One exact-output application profile.
- Canonical encodings and digest/signature boundaries.
- Target, Contract, Plan, output, evidence, and transaction identities.
- Capability/state exchange and an eligible-plan negotiation.
- Literal, Reference, and a deterministic Delta operation.
- Staging, validation approval, atomic local commit, and recoverable receipt.
- Basic missing-dependency and baseline-mismatch cases.

Exit condition: a sender and receiver can exchange a versioned object, reject invalid updates, and recover duplicate or interrupted commits correctly.

### Stage 2 — Conformance before broad optimization

Deliver:

- Deterministic fixtures with expected outcomes.
- Failure cases for stale baselines, global predicates, and canceled demand.
- A second independently implemented encoder or receiver for the selected profile.
- Clear distinction between tested behavior and unimplemented features.

Exit condition: implementations agree on object identities, acceptance, and transaction outcomes.

### Stage 3 — Mixed reconstruction and repair

Deliver:

- Approved Procedural operations.
- Residuals bound to concrete baselines.
- Bounded approximation with explicit validators.
- Localized repair including affected validation.
- A fixed hybrid baseline and a simple adaptive selector.

Add a learned Latent path only with an identified decoder, runtime assumptions, appropriate reference, and evidence method. Preserve literal or other eligible fallback where possible.

Exit condition: different Plans can produce accepted results under one declared Contract, and failures do not silently weaken it.

### Stage 4 — One repeater and two receivers

Deliver:

- Explicit repeater configuration and delegation.
- Shared artifact/evidence storage with separate authorization checks.
- Plan rewriting, placement, and shared-work registration.
- Scoped interest and replacement semantics.
- Single-publisher local commitment across both receivers.

Exit condition: one receiver can supersede its demand without canceling work still needed by the other, and each accepted output has the correct provenance and scope.

### Stage 5 — Measured session benefits

Deliver:

- Cold/warm cache experiments.
- Full compressed, delta, reference-reuse, and fixed-hybrid comparisons.
- Direct, cache-only-repeater, and compute-repeater comparisons.
- Complete traffic, compute, validation, failure, and latency accounting.
- At least one negative case where ARFP overhead outweighs the benefit.

Exit condition: the report identifies the workloads and conditions where adaptation or intermediate execution helps, and where it does not.

### Stage 6 — Optional wider fabric

Consider multiple repeaters, bounded forwarding, more decentralized placement, scoped delegation, shared checkpoints, dependency leases, and longer-horizon planning.

Do not promote a single-repeater result into an Internet-scale claim. Broad deployment introduces topology, discovery, fairness, economic, trust, and failure-management questions that require their own evidence.

## 25. Open decision register

| Decision | Current direction | Still unresolved |
|---|---|---|
| Normative wire encoding | Canonical, independently reproducible objects | JSON profile, CBOR profile, framing, and extensions |
| Digest and signature suites | Authenticated identity and verifiable bindings | Required algorithms and key distribution |
| Target naming | Logical object plus publisher revision | Namespace and binding format |
| Scope identity | Canonical explicit selection/projection | Cross-domain syntax and schema |
| Baseline semantics | Exact output digest or explicit applicability predicate | Initial operation/profile definitions |
| Mandatory baseline representation | Literal and references support a basic path | Codec, dictionary behavior, and uncompressed form |
| Runtime execution | Approved bounded operations | Runtime packaging, determinism rules, sandbox mechanism |
| Latent support | Optional profile with pinned decoder and validation | Model choice, reference comparison, cross-device behavior |
| Validators | Versioned predicates and explicit trust | Standard evidence schemas and accepted checker policy |
| Resource limits | Admission plus runtime enforcement | Accounting units, reservations, and distributed enforcement |
| Contract resource policy | Bound limits and no silent relaxation | Which limits belong to common Contract versus participant-specific allocations |
| Plan replacements | Immutable accepted Plans with identified repair/rewrite | Parent references and fallback representation |
| Receipt format | Separate approval and actual commit outcome | Exact encoding and durability/signing implementation |
| Local head identity | Include sufficient context to avoid stale updates | Full key: revision, scope, Contract, and output relationships |
| Repeater discovery | Explicit configuration initially | Automatic discovery and topology negotiation |
| Delegation | Narrow grants with bounded resources | Credential encoding, expiry, revocation, and subdelegation rules |
| Milestones | Declared predicates and permitted uses | Generic object shape versus application-specific profiles |
| Replaceability | Profile-defined supersession relation | Ordering, sequencing, and stream failure semantics |
| Checkpoints | Optional common concrete baseline | Frequency, scope, admission, and authority |
| Cache inventories | Relevant scoped state exchange | Exact versus approximate inventories and privacy |
| Leases | Optional reserved dependency availability | Reservation and expiry semantics |
| Transport | Application overlay using existing infrastructure | Binding, multiplexing, congestion behavior, resumption |
| Optimization objective | Time/cost to accepted result | Deadline policy, failure penalty, energy/cost weighting |
| Success criteria | Compare against strong fixed hybrid and topology baselines | Workload corpus and quantitative acceptance thresholds |
| Authority beyond v0.1 | Single designated publisher | Multiwriter merge, consensus, or conflict policy |
| Standards path | Candidate protocol concept | Whether independent demand and results justify formal standardization |

An implementation can choose temporary experimental answers, but must record them as profile or prototype decisions. Do not present an experiment-specific choice as an already established universal requirement.

## 26. Instructions for the next engineer or model

### 26.1 Preserve these decisions

- Keep Target, Contract, Plan, and Realized Output distinct.
- Treat Data Worktree as a DAG with explicit execution and validation dependencies.
- Retain all six representation classes in the architecture.
- Keep the receiver's actual capabilities and available state central to planning.
- Keep fidelity, dependency validity, authority, and commitment rules enforceable.
- Separate Plan admission from output acceptance and actual commitment.
- Require exact baseline identity or declared semantic applicability for patches.
- Preserve explicit scopes and milestone restrictions.
- Treat cameras and 3D scenes as application examples only.
- Keep AI optional and outside mandatory protocol semantics.
- Preserve authorized repeater participation and shared-work cancellation.
- Keep one designated publisher as the initial authority model.
- Make learned/approximate output identity distinct from logical Target identity.
- Account for validation, missing dependencies, failures, repair, and all network links.
- Keep prior-work comparisons visible, particularly NFN and result provenance.

### 26.2 What to do next

Start with the direct-core profile, schemas, state machine, and executable conformance fixtures. Use the implementation sequence in Section 24. Then add the smallest repeater demonstration that exercises shared work and receiver-specific Plans.

Before selecting new features, identify which core invariant or measured bottleneck they address. Avoid repeatedly rewriting the concept without producing a concrete schema, fixture, implementation slice, or result.

When a design change is required, record:

1. The concrete inconsistency or evidence motivating it.
2. The objects and invariants affected.
3. Compatibility implications.
4. How the changed behavior will be checked.

### 26.3 Claims discipline

Use “proposed,” “implemented,” “tested,” and “demonstrated” accurately. Do not claim measured speed, universal compression, standardized status, Internet-scale operation, or established novelty from the architecture alone.

A valid handoff continuation should distinguish documentation checks from executed protocol tests. This document itself is a design artifact, not a reference implementation or benchmark report.

## 27. Glossary

| Term | Meaning |
|---|---|
| Accepted Plan | An authorized eligible reconstruction attempt |
| Accepted output | A concrete result whose required evidence passes the applicable acceptance procedure |
| Application profile | Versioned domain semantics for schemas, operations, fidelity, updates, and validation |
| Artifact | Concrete stored bytes or content with an identity |
| Authority | Permission to perform a defined operation or state transition |
| Baseline | The specific prior content or semantic state an operation depends on |
| Checkpoint | An identified shared baseline offered for subsequent reconstruction |
| Contract | The bound requirements governing acceptance and permitted execution |
| Data Worktree | The reconstruction dependency DAG and associated descriptors |
| Delegation | A bounded grant allowing another participant to act |
| Evidence | Data supporting an acceptance or execution claim |
| Fidelity | The specified relation between realized output and its designated reference |
| Interest | A receiver's current demand for a Target, scope, or milestone |
| Literal | Direct or conventionally compressed bytes used as a reconstruction representation |
| Materialization | Producing a concrete result from references, payloads, and operations |
| Milestone | An independently checked stage with explicitly permitted uses |
| Plan | One selected dependency graph, representation assignment, and execution strategy |
| Realized Output | The concrete content actually produced |
| Receipt | An authenticated record binding identities, evidence, authority, and outcome |
| Repeater | An authorized intermediate cache, executor, or Plan rewriter |
| Required transition | An update whose required semantics cannot be erased by supersession |
| Scope | The explicitly requested portion or projection of a Target |
| Supersession | Contract-permitted retirement of an older delivery obligation |
| Target | A logical object and immutable publisher revision |
| Validation approval | Permission to commit a particular output based on accepted evidence |
| Validator | A specified procedure or trusted checker evaluating a predicate |

---

**End of handoff.** The stable architectural direction is negotiated mixed-representation reconstruction with explicit acceptance and authority. The next concrete work is to turn that direction into interoperable objects, executable conformance cases, and measured behavior.









