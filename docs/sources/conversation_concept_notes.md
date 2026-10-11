# ARFP conversation concept notes

**Source:** project owner's visible conversation preceding the complete handoff.  
**Purpose:** retain the original design direction and repeater extension alongside the consolidated document.  
**Editorial treatment:** repeated copies of the same proposal are included once; broken paste text and table formatting are repaired. This is a normalized source compilation, not a verbatim chat export. No substantive feature is intentionally removed.  
**Status:** historical concept notes. The [complete handoff's corrections table](../architecture/ARFP_Concept_Handoff_v0.1_2026-10-11.md#13-corrections-that-supersede-earlier-shorthand) refines early shorthand, especially accepted-plan guarantees, residual bounds, validation cones, and camera/revision terminology.

## 1. Originating concept

Adaptive Reconstruction Fabric Protocol (ARFP) v0.1 is a hybrid representation selector and reconstruction protocol that transmits a compressed Data Worktree instead of raw data or pure neural latents. The receiving side walks the worktree and reconstructs under an explicit agreement that binds representation choice, dependencies, fidelity, validation, and authority.

The deeper concept is a protocol for negotiating, materializing, validating, and committing versioned objects via a dependency DAG of mixed representations. The receiver's actual capabilities and state determine the Plan. The original statement that any accepted Plan satisfies the same Contract is refined by the handoff: acceptance authorizes an eligible attempt; successful commitment requires validation of the actual result.

## 2. Separated identifiers

| Identifier | What it names | Mutability or binding |
|---|---|---|
| Target | Logical object and revision, such as `scene://v3/update-42` | Immutable once requested |
| Contract | Acceptance criteria: fidelity thresholds, semantic invariants, resource bounds, permitted approximation classes | Bound before planning |
| Plan | Chosen DAG of operations, representations, and dependencies for this receiver | Receiver-specific; multiple Plans may exist for one Target |
| Realized Output | Concrete bytes or canonical form actually produced | Own content identity, linked to Target and Contract by a receipt |

A hash on the Realized Output proves content identity relative to the expected digest. It does not prove the Contract was met. The receipt needs both identity and the applicable validation evidence.

## 3. Data Worktree node types

Each node declares its type, content or reference, dependency edges, claimed fidelity contribution, required execution environment, and fallback policy.

| Type | Intended meaning |
|---|---|
| Reference | Content-addressed asset the receiver already holds or is entitled to fetch; verify its identity |
| Delta | Structured change against an identified baseline node |
| Procedural | Approved generator and parameters executed in a sandbox |
| Latent | Neural representation and compatible decoder identifier; approximation only by Contract |
| Residual | Explicit correction applied after other nodes; the resulting error bound still needs validation |
| Literal | Conventionally compressed bytes when no cheaper eligible path exists |

Shared dependencies are ordinary DAG edges. The transmitted payload is the worktree plus only the missing node payloads and dependencies. A recipe or model does not eliminate information or dependency costs.

## 4. Whole-plan selection

The selector, at the sender or a joint coordinator, searches for a Plan minimizing time to validated availability under hard constraints:

- Every representation is permitted by the Contract.
- Missing dependencies are costed once and amortized across dependents.
- Execution cost, peak memory, and decoder availability match the receiver's declared capabilities.
- Expected repair probability and cost are included.
- Fidelity and authority are constraints, never soft objectives.

Different receivers can receive different Plans for the same Target. Their realized outputs must each pass the bound acceptance criteria. AI is an optional way to implement the selector; the protocol does not require AI.

## 5. Reconstruction and localized repair

1. Walk the DAG in topological order, resolving references, applying deltas, executing procedural nodes, decoding latents, and applying residuals.
2. On a missing dependency, decoder mismatch, procedural divergence, or failed residual bound, identify the failed node.
3. Preserve independent validated work and invalidate affected descendants.
4. Request an agreed alternative representation for that node or sub-DAG under the existing Contract.
5. Reevaluate affected reconstruction and validation, including cross-branch or global predicates where applicable.
6. Commit only after the full required output passes acceptance and the local transaction/receipt conditions hold.

Repair stays within the original Contract. A lower-fidelity substitute requires an explicit Contract amendment; changing a Plan does not silently change acceptance.

## 6. Validation evidence and authority

Evidence must be produced where the comparison is possible:

- Exact output: match the authenticated expected content identity.
- Approximate output: evaluate the residual norm, distributional statistic, or model-specific fidelity metric against a held reference, or use a trusted checker explicitly named by the Contract.
- Receiver self-attestation is insufficient for a comparison that needs ground truth it does not hold.

Successful reconstruction does not grant write authority. The initial design has one designated publisher. Receivers stage, validate, and commit locally; pushing a change back to the authoritative source is a separate explicit operation.

## 7. Initial demonstration and minimal objects

Use repeated updates to a structured 3D scene with cached buildings (Reference), moved objects (Delta), repeated geometry (Procedural), approximate textures (Latent), novel assets (Literal), and sparse geometric corrections (Residual).

Compare full compressed transfer, pure delta, and pure content-addressed reuse, with strong fixed-hybrid comparisons added by the handoff. Measure total bytes including dependencies, time to validated availability, receiver compute/peak memory, and single-node recovery cost under cold and warm caches.

| Object | Original proposed contents |
|---|---|
| Target | ID, revision, publisher |
| Contract | Fidelity predicates, permitted node classes, execution bounds, evidence requirements |
| Plan | Node/edge DAG and the receiver capability profile used in planning |
| WorktreePayload | Serialized DAG and missing node contents |
| Receipt | Target ID, Contract hash, Plan hash, output hash, validation evidence summary, commit status |

The proposed contribution is the negotiated binding of these objects so independently implemented endpoints can coordinate mixed representations, receiver-specific Plans, local repair, and explicit fidelity evidence. The decisive test is whether adaptation beats a strong fixed method after all dependency, compute, validation, and repair costs are counted.

## 8. Internet repeater fabric

ARFP with Internet repeaters is a fabric of authorized intermediate nodes that cache, partially materialize, re-plan, and re-emit reconstruction worktrees so downstream receivers can obtain accepted results faster and cheaper. Faster and cheaper are intended benefits to measure, not established results.

A repeater is neither the original publisher nor the final consumer. It may store validated artifacts, execute eligible operations, and emit Plans for clients while remaining bound by the same Target, Contract, and authority constraints.

### 8.1 Advertised role

A repeater advertises:

- Cache capacity and eviction policy.
- Execution capabilities, including supported generators and decoders.
- Trust domain: evidence it is allowed to produce or re-attest.
- Downstream affinity: receivers or regions it serves.

Authorization is contractual: the Contract or a derived session policy names the repeater or an eligible class and its permitted operations. A pure cache may store and forward. A compute repeater may materialize eligible nodes. Neither may alter the Contract.

### 8.2 Operations

**Dependency caching and reuse.** Retain content-addressed assets, procedural outputs, decoded latent outputs, and residual artifacts. Future Plans can satisfy shared dependencies locally. Evidence that validated an artifact under one Contract must not be mistaken for universal acceptability or permission to disclose it.

**Partial materialization.** For a scoped request such as one room's navigation geometry, compute the required dependency closure and materialize only that cone. Emit a reduced worktree with the original Target identity and explicit scope so it cannot be mistaken for the complete object.

**Plan rewriting.** Given downstream capabilities, replace an incoming Plan with a cheaper eligible representation, factor shared work once, and choose execution placement between repeater and receiver. A generated mesh may serve several constrained phones, while a capable workstation receives the generator parameters. Preserve the Contract and record original and rewritten Plan identities and applicable evidence.

**Milestone acceleration.** Prioritize and push intermediate milestones to clients that declared interest, for example navigation-ready structure before presentation-ready textures. Each milestone grants only its declared permitted uses.

**Obsolete-update suppression.** For replaceable state, abandon unfinished intermediate revisions or superseded requests while preserving reusable dependencies. Required-transition streams are forwarded intact. The handoff further requires retaining unfinished shared work still needed by other active demands.

**Shared checkpoint emission.** Periodically materialize a common content-addressed baseline that a group can adopt so subsequent deltas remain compact. Adoption requires the declared exact baseline and applicable authority; it does not erase differences among approximate realizations by assertion.

### 8.3 Proposed fabric objects

| Object or rule | Purpose |
|---|---|
| RepeaterCapability | Advertised cache, compute, and trust profile |
| ScopedInterest | Requested subset and intended use |
| PlanRewrite | Signed lineage record binding a substituted DAG to Target/Contract and the evidence for substituted nodes |
| MilestoneReceipt | Acceptance record authorizing only the stated intermediate uses, distinct from the final receipt |
| Checkpoint | Content-addressed, identically reconstructed baseline offered to a receiver group |
| Evidence forwarding rules | Re-attestation only within the repeater's trust authority; otherwise preserve original validation evidence and provenance |

The consolidated handoff elaborates artifact/evidence/authority separation, attenuated delegation, budgets that cannot be duplicated, multi-hop fidelity, loop prevention, and atomic local commitment. Those elaborations are preserved in that document, including its mathematical model.

### 8.4 Session behavior

A session can span publisher, one or more repeaters, and receivers. The first update populates caches and may establish a shared checkpoint. Later updates increasingly resolve from those caches. Receiver-specific Plans reuse the same repeater preparation where possible. A changed application interest can switch active work without restarting the session, provided all remaining demands and obligations are respected.

### 8.5 Constraints

- Fidelity and authority remain hard constraints across all hops.
- A lower-fidelity substitute is eligible only when the Contract explicitly permits it for the scope or milestone.
- Scoped or milestone acceptance does not commit the full Target or grant write authority.
- Rewrites and milestone receipts remain linked to the original Target and Contract hashes.
- Validation evidence stays verifiable; a repeater cannot invent fidelity claims outside its authority.
- Multi-hop approximation must satisfy the end-to-end reference requirement or a justified error-composition rule.

### 8.6 Two-receiver demonstration

One phone and one workstation open the same scene through one repeater. The phone reaches a permitted navigation-ready milestone from lightweight proxies; the workstation performs richer eligible reconstruction locally. Subsequent updates reuse shared dependencies.

When one receiver changes its interest, the repeater discards only work that has become unnecessary. It preserves work still needed by the other receiver and supplies a valid path for the new demand.

Display origin bytes, repeater-delivered bytes/cache attribution, total measured link traffic, time to first permitted use, time to final validation, and discarded/reused work. Origin egress savings alone do not prove total network savings.

## 9. The camera is an application example

The camera is not a protocol concept. A camera jump illustrates a rule for application state explicitly marked replaceable by the Contract or a bound application profile:

- An unfinished older replaceable request may be abandoned when a valid newer request supersedes it.
- Completed reusable dependencies are preserved.
- Shared unfinished work still needed by another demand remains live.
- A valid reconstruction path for the replacement remains required under the bound acceptance conditions.
- Required transitions, such as transactions or audit events, cannot be dropped merely because the planner prefers a newer state.

A changed view commonly changes interest or scope rather than the source object's revision. The core protocol should express request identity, supersession, obligation, and scope independently of any 3D application.

## 10. Candidate Internet protocol, optional AI

ARFP is being shaped as a candidate Internet protocol because it defines negotiation and reconstruction across independent endpoints; separates Target, Contract, Plan, and actual output; gives intermediaries explicit cache/compute/rewrite roles; and binds verifiable result records to the agreement and execution path.

Whether this combination warrants standardization depends on a concrete interoperability problem and demonstrated benefit beyond existing delta, content-addressed graph, caching, and named-computation mechanisms. VCDIFF, IPLD/GraphSync, NFN, CFN, and related systems are comparisons to investigate, not evidence that ARFP is unique.

AI may choose among eligible Plans. Acceptance, validation, authority, and commit behavior cannot depend on calling the selector intelligent. Cameras, scene graphs, and learned decoding are not mandatory core concepts. The mathematical formulation and its assumptions are retained in [handoff Section 17](../architecture/ARFP_Concept_Handoff_v0.1_2026-10-11.md#17-mathematical-model).
