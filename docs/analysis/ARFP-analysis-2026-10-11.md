# ARFP — Working Analysis and Engineering Record

**Adaptive Reconstruction Fabric Protocol, v0.1**
**Compiled:** 2026-10-11 · **Author of the concept:** Dino Silvestri · **Status:** design plus executable Stage-1 checks (gate zero, failure cases, real-crash recovery, multi-hop provenance, contract split); a byte benchmark on real data and a first-order time model (section 15); no transport, no network measurement

This file pulls together everything worked out so far: the concept, the "meta" it belongs to, the schema, the design choices and how they force each other, what running code has and hasn't shown, an audit of the latest outside contribution (COSE binding vectors, C04/C21 fixtures), and the next work in order. It is written to be handed to another engineer or model as-is.

In the repository, the schema kit is [`kit/`](../../kit/), and file paths such as `run_checks.py` or `bench/speed_model.py` are relative to it.

**Later additions (2026-10-12).** The [speed mechanisms](../proposals/ARFP-speed-mechanisms.md) added four fixtures, two malformed objects, 37 cases and 22 mutation targets to the kit, which now reports 42/42, 13/13, 132/132 and 29/29. This record is otherwise unchanged and describes the kit as of 2026-10-11 (commit `8144f93`). All 95 original cases still pass with the same results, and every size is unchanged; only C28, C28b and C28c now count 42 fixtures instead of 38.

---

## 0. Claims discipline (read first)

| Label | Meaning here |
|---|---|
| **Checked** | Exercised by `run_checks.py` in the schema kit, reproducible bit for bit |
| **Designed** | Specified in the schema or rules, not exercised |
| **Open** | Not decided |
| **Unmeasured** | Any claim about speed, bandwidth, scale or novelty. Nothing in this file is a network measurement; section 15 adds measured compression sizes and local timings, plus a model built on them |

The outputs used in the checks are toy integer geometry and simulated decoders. There is no transport, no real codec, and no second implementation yet.

---

## 1. The meta: what "new high-speed data transfer" actually means here

ARFP does not make a link faster. It shrinks what has to cross the link, then proves the rebuilt result acceptable. Hash checks have verified *exact* rebuilds for decades (Git, rsync). The new part is accepting *approximate or generated* rebuilds under a contract, and saying which parts of a result are which.

| Generation | What crosses the wire | What both ends share | What limits it | Examples |
|---|---|---|---|---|
| 1. Bytes | The content | A format | Link rate | File copy, raw video |
| 2. Compressed bytes | Content minus redundancy | A codec, maybe a dictionary | The content's entropy | zstd, H.264 |
| 3. References and deltas | Names of what the receiver holds, plus changes | Content-addressed state | Knowing what the receiver holds | Git, rsync, CDNs |
| 4. Recipes | Programs, seeds or latents that regenerate content | Runtimes, models | Receiver compute and determinism | Lockstep netcode, neural codecs |
| 5. Recipes under contract | The cheapest of the above, chosen per node, plus evidence | All of the above, plus a contract | Proving what was rebuilt | ARFP's target |

### The floor no protocol beats

- **Exact results:** the minimum is the conditional entropy H(X | Y) of the target X given the receiver's state Y. Slepian and Wolf (1973) showed that rate is achievable asymptotically, with vanishing error, even when the sender never sees Y.
- **Approximate results:** the minimum is the conditional rate–distortion function R_{X|Y}(D) when the sender knows Y. If only the receiver knows Y, the floor is Wyner and Ziv's R_WZ(D) (1976), which is never lower. ARFP's STATE message exists so the sender knows Y.
- **Realism costs accuracy:** Blau and Michaeli (2019) showed that bitrate, distortion and perceptual quality trade off. At a given bitrate, demanding more realism costs accuracy.
- **Novelty:** when Y says nothing about X (a street the system has never seen), H(X | Y) ≈ H(X) and no representation helps. "Photoreal city walks with near-zero bandwidth" is only possible if the generated parts are labeled as generated, not as the real street.

### The honest speed metric

```
effective throughput = |validated result| / T_usable
T_usable = T_prep + T_deps + T_delivery + T_reconstruct + T_validate + T_repair
```

That ratio can exceed the link rate, as compression can. Measuring it is the Stage 4–5 job.

### Three rules this generation implies

1. Choose bytes, a reference, a delta or a recipe node by node, pricing the whole plan against what the receiver holds. (A planner's job.)
2. Accept an output on evidence about what was produced. How it was produced counts only through declared, testable runtime properties: determinism class and divergence bound. (Enforced by the checker.)
3. Label generated content as generated, all the way into the receipt. (Enforced by the checker.)

For AI-to-AI links, a model is one more runtime with a digest. A latent passed between two models is a Latent node, and fetching the model is a dependency with its own cost.

---

## 2. Object map (four planes)

Each object on the receipt chain embeds the ids of the objects it names, so changing anything it names changes its id, and a receipt can't be replayed against a different agreement.

| Plane | Object | What it is |
|---|---|---|
| Identity | Target | Object id + revision, set by the publisher |
| | Scope | A part of a target, or a milestone; `"all"` is the only scope that can authorize full-target use |
| | Artifact id | SHA-256 of raw bytes |
| | Work key | Names one computation (op, runtime, params, inputs) before it runs |
| Agreement | Binding | The publisher's signature over (target id, contract id), or over (target id, template id, this revision's expected digests, references and threshold overrides); checked before any planning (gate zero) |
| | Contract template | Every rule that doesn't change with a revision, cached by digest for the session; authenticated through each binding that names it (section 10) |
| | Contract | What counts as done: node classes, predicates, invariants, free regions, determinism policy, evidence policy, authority, stream rules, limits, milestones |
| | Predicate | One check: digest match, metric bound, invariant or schema |
| | Delegation | A repeater's rights and budget; children narrow, budgets partition |
| Plan | Capabilities | What an endpoint can run, with each runtime's determinism class |
| | State | Heads held, snapshot number, scoped have-answers |
| | Demand | Current interest: stream + seq, separate from target revisions |
| | Plan | Node DAG bound to one receiver snapshot |
| | Rewrite | A repeater's change to a plan, with reused and pending work |
| Outcome | Evidence | One check result on one output, with the work key that produced it |
| | Approval | Permission to commit one output if the head still matches |
| | Receipt | What the commit actually did |
| | Head | What a consumer now holds (object, target, contract, scope, output) |
| | Repair | The failed node and its affected cone |
| | Attestation | A repeater's signed statement naming forwarded evidence by hash; adds to that evidence, never replaces it |

Messages (14): CAPABILITIES, STATE, DEMAND, OFFER (now carries the signed binding), ACCEPT, REJECT, WORKTREE_PAYLOAD, RESULT, REPAIR, EVIDENCE (signed evidence, attestations and delegations crossing a hop), SUPERSEDE, CANCEL, VALIDATION_APPROVAL, COMMIT_RECEIPT.

---

## 3. Identity and encoding rules

| Rule | Spelling | Why |
|---|---|---|
| Deterministic CBOR | RFC 8949 §4.2.1: shortest integers and lengths, no indefinite lengths, keys sorted by encoded bytes | One object, one byte string |
| Object id | SHA-256 of canon(["arfp/0", kind, object]) | Kinds can never collide; versioned hashing |
| Artifact id | SHA-256 of raw bytes | Matches plain content hashes elsewhere |
| Digest form | [alg, value], COSE alg ids (−16 = SHA-256, RFC 9054) | Algorithm agility without string parsing |
| Exact numbers | Int, or tag-4 decimal with negative exponent and mantissa not divisible by 10; no floats | 0.5 hashes the same everywhere |
| Map keys | Text keys in every ARFP map | RFC 8949 and older RFC 7049 orders agree (C28b) |
| Work key | H(["arfp/0","work", class, op, runtime, params, payload, artifact, base, input work keys]) | Shared work found across plans |
| Head id | id of {object, target, contract, scope, output} | Commit compare-and-swaps on this |
| Signatures | COSE_Sign1 (RFC 9052), Ed25519 (alg −8), key id in the protected header | Signs exactly what was hashed; deterministic, so vectors reproduce byte for byte |
| Signed-object typing | Every signed payload carries `kind`; a verifier demands the kind it expects | One key's delegation signature can't pass as a binding (G6) |
| Binding hash | SHA-256 of the binding's COSE_Sign1 bytes | Approvals and audit logs name the exact signed binding |
| Contract id under a split binding | id(materialize(template, binding)) | Identical to the whole contract's id, so plans, evidence, approvals and heads don't change; evidence can't cross revisions (T8) |
| Hop fields | `ttl`, `via` excluded from dedup keys and signatures | Relays can change them |

Runtimes need pinned arithmetic too: Python floors −1 // 2 to −1, C truncates to 0. 3GPP's AMR ships ANSI-C code "necessary for a bit exact implementation"; RFC 6716 makes Opus's decoder source normative. Ballé, Johnston and Minnen (ICLR 2019) showed float differences make entropy-coded latents fail catastrophically across platforms, fixed with integer networks.

---

## 4. The central idea: how evidence reaches a receiver's output

| Class | Example | How the sender's evidence covers the receiver's own output | Delta base? |
|---|---|---|---|
| **E** bit-exact | Integer generator; hash-verified bytes | By identity: once output digests match, every sender check holds | Yes |
| **T** bounded divergence | Fixed-point decoder with declared bound δ under a named metric | By bound, true-metric predicates only: ε (sender, measured) + δ ≤ threshold | No |
| **N** non-reproducible | Sampling diffusion decoder | Doesn't transfer. Use a free region, a receiver-runnable check, or decode upstream at a checker | No |

The T rule is the triangle inequality: d(y_r, x) ≤ d(y_r, y_s) + d(y_s, x) ≤ δ + ε. It rests on three assumptions: the metric is a true metric (the profile defines it; code can't check it), both decodes ran the same work (evidence carries a work key; R1b), and δ really bounds both runs (declared and vector-tested, not proven, so the contract states it as an assumption).

Checked instance: publisher measured ε = 0.275 mm, decoder declares δ = 0.15 mm, so 0.425 ≤ 0.5 mm passes without the receiver holding the reference. True distance (computable only by the harness): 0.271 mm.

**Placement restores determinism.** Running a T- or N-class decode upstream at a checker turns it into exact bytes for everyone downstream (R3), at the price of last-hop bandwidth.

---

## 5. Design choices and what each forces

| # | Choice | Schema surface | Buys | Forces |
|---|---|---|---|---|
| 1 | Keep target, contract, plan, output apart | Separate digests | Different plans per receiver | Receipts bind all four |
| 2 | One canonical encoding | `id(o)`, deterministic CBOR | Identity without coordination | Canonical encoder everywhere |
| 3 | Exact decimals, never floats | `exact-num` | Thresholds mean the same everywhere | Units on every predicate |
| 4 | Name computations | Work keys | Shared work across plans | Canonical params |
| 5 | Judge the output, not the path | `predicate`, `evidence.output` | Planner freedom | Every region needs a checkable predicate |
| 6 | Never average invariants away | `invariants` | Global failures caught (C09) | Evidence per predicate |
| 7 | Declare determinism per runtime | `det`, `vectors`, `bound` | Evidence transfer by identity or bound | Conformance vectors per runtime |
| 8 | Compose multi-hop error or check end-to-end | `composition` | Repeaters approximate safely (C25) | Hop evidence must chain |
| 9 | Label generated regions | `contract.free` | Generation where no fidelity is claimed | Free can't be reference-bound (R9); unlabeled refused (R8, R8b) |
| 10 | One publisher; commit is compare-and-swap | `head`, `expected-head` | No stale overwrite; idempotent retry | No multi-writer in v0.1 |
| 11 | Approval is permission, receipt is fact | `approval`, `receipt` | Permission and fact recorded apart | A durable journal that recovery replays (C21) |
| 12 | Delegations narrow, budgets partition | `parent`, `budget` | No escalation (C24, C24b) | A coordinator tracks spend |
| 13 | Receivers demand, publishers offer | DEMAND/OFFER roles | Offers never collide | Receivers can't propose plans |
| 14 | Interest revisions apart from target revisions | `demand.stream`, `seq` | Camera jumps don't fake revisions | Per-stream supersession rules |
| 15 | Plans immutable | `plan.parent`, `fallbacks` | Auditable repairs | New digest per repair |
| 16 | Planners propose, rules decide | Eligibility check; `claim` ≠ evidence | Planner can't get an ineligible plan admitted | Rules must be complete |
| 17 | Fast path for unchanged plan shapes | `fast-path`, `plan.snapshot` | No wait for ACCEPT (R10) | Late replays refused (R11) |
| 18 | Hop-limited, deduplicated forwarding | `ttl`, `via` | Loops end (C26) | Hop fields outside signatures |
| 19 | Placement as a determinism tool | `node.at` | N decoders usable upstream (R3) | Exact bytes on the last hop |
| 20 | Gate zero: publisher-signed binding before planning | `binding`, OFFER.binding, approval.binding | Forged target/contract pairs refused before any work (G1–G10) | 253 bytes per binding; an allow-list to manage |
| 21 | Evidence that crosses a hop is signed; attestations add, never substitute | EVIDENCE message, `attestation`, `attest` right | Provenance checkable across repeaters (C27) | 112 bytes per signed evidence record |
| 22 | Write-ahead journal: approval durable before the head swap | Local journal (not on the wire) | A crash after the approval, head or receipt record, or partway through the head write, recovers to one outcome (C21) | An fsync per record |
| 23 | Split the contract: session template plus per-revision binding | `contract-template`, split `binding`, OFFER `template` | 3,310 → 1,838 B per new-revision OFFER once cached (fixtures; T2 shows the same on its own target, 1,505 → 998 B; section 10) | A cache miss costs a round trip; the binding grows by the per-revision values |

### Coupling chains

**Trust for approximate content:** approximation allowed only where declared → receiver lacks the reference → evidence must come from the reference holder and reach the receiver's actual output → needs E (identity) or T (bound) → runtimes declare a class and ship vectors → N work goes to free regions or upstream.

**Baselines:** deltas need an exact base → approximate outputs differ per receiver (C02) → only E outputs are bases (C03) → a T decode can't take a residual (R6) → repair falls back to literal or upstream decode (R7, R3) → shared exact checkpoints keep deltas cheap.

**Authority:** one publisher in v0.1 → commit is compare-and-swap on the head → stale results can't overwrite (C19), retries return the same receipt (C20), late results for retired demands are refused (C18) → a replayed fast-path update is refused by snapshot once the receiver moves on (R11), and one racing the original fails at commit (C19, C20).

**Placement:** repeaters execute and check → they need delegations that only narrow (C24b) → budgets partition (C24) → multi-hop error composes or is checked end-to-end (C25) → upstream decode buys determinism.

**Liveness:** interest changes faster than objects → demand stream + seq → supersession only on replaceable streams (C17) → cancel = unfinished work outside the new live closure, by work key (C15, C16) → forwarding needs hop limits and dedup (C26).

**Trust root:** every acceptance traces to the publisher's binding → the binding is checked before planning (G9) → delegations, evidence and attestations are signed and typed → a repeater can carry or co-sign but never become the root (C27c, C27e) → a receipt alone rebuilds the chain (C27a, C27b).

**Planner safety:** AI planning optional → every plan passes a mechanical eligibility check → given complete rules, authenticated contracts and honest runtime bounds, a hallucinating or prompt-injected planner makes things slower, not wrong → estimates live in `claim`, never evidence.

---

## 6. Speed levers and the correctness tax
Measured control cost (fixture, deterministic CBOR, Ed25519): **3,421 bytes from OFFER through COMMIT_RECEIPT** for one negotiated update, with the target and contract referenced by id. DEMAND and session setup add more.

| Message | Bytes |
|---|---|
| OFFER: signed binding + ids + 7-node plan inline | 1,633 (48%) |
| VALIDATION_APPROVAL, signed | 771 |
| RESULT, validated | 356 |
| COMMIT_RECEIPT, signed | 354 |
| WORKTREE_PAYLOAD envelope | 195 |
| ACCEPT | 112 |

- The signed binding is 253 bytes. Signing an evidence record for a hop adds 112 bytes.
- **A cost the binding exposed, now fixed in the kit:** a contract names one target revision, so every revision needed a new contract, and an OFFER carrying target and contract inline was **3,310 bytes**. With the contract split (section 10), the template (1,478 B) is cached once per session and each revision's OFFER is **1,838 bytes**, or **707 bytes** with the plan sent by id. The split binding grows from 253 to 438 bytes because it carries the revision's expected digests and reference.
- That's about **49× a 70-byte avatar pose update** (50 kbps at 90 Hz ≈ 70 B). The fast path's OFFER + envelope alone wrap a 70-byte pose in 1,079 bytes, about 15× its size, before validation or commit messages. Per-frame streams belong on a plain datagram channel under a standing contract, with evidence at checkpoints.
- First optimizations: send a plan once and refer to it by digest; split the contract as above.
- Round trips usually cost more than bytes: at 50 Mbit/s and 40 ms RTT, one extra round trip ≈ 250 KB of payload time. A negotiation pays only when it avoids more than about the bandwidth-delay product.
- Toy data note: the latent fairing was 653 bytes vs 1,026 literal. That says nothing about real geometry.

| Lever | Mechanism | Saves | Costs | Loses when |
|---|---|---|---|---|
| Don't resend what they hold | Reference nodes; scoped `have` | Bytes | A round trip; leaks cache contents | Content is new |
| Send the change | Delta on exact `base` | Bytes | E baselines; mismatch repairs | Baselines diverge |
| Send the recipe | Procedural/latent + `det` | Bytes when output ≫ recipe | Compute, bootstrap, evidence | Novelty, weak devices, cold caches |
| Expand at the right hop | `node.at` + delegation | Repeated compute, downstream bytes | Trust in repeater checks; more link bytes | One receiver |
| Compute shared work once | Work keys | Compute | Coordination | Receivers rarely overlap |
| Usable before final | Milestones | Time to first use | Extra validation | Milestone ≈ full result |
| Stop unneeded work | Demand seq + live closure | Compute, bytes | Consumer tracking | Interest stable |
| Fix only what broke | Cone repair, `fallbacks` | Re-transfer | Per-node evidence | Global failures |
| Skip the ACCEPT wait | Fast path + `snapshot` | One round trip per update | Snapshot tracking | Plan shapes change often |

Precedents: Chrome disabled HTTP/2 Server Push by default in 2022 after gains proved hard to realize; the Cache Digests draft (clients telling servers what they hold) expired. TLS 1.3 gives 0-RTT data no replay guarantee between connections.

---

## 7. Lifecycle

States: Negotiating (gate zero runs first: the binding is verified before eligibility) → Accepted → Materializing → Validating → Ready → Committed, with Rejected, Aborted, Repairing and Conflict as side states. The fast path goes Negotiating → Materializing when the plan shape and snapshot are unchanged.

| Message | Sent by | Moves the attempt | Carries |
|---|---|---|---|
| CAPABILITIES | Any endpoint | Before any attempt | Profiles, classes, runtimes + det class |
| STATE | Receiver | Before planning | Snapshot, heads, scoped have-answers |
| DEMAND | Receiver | Opens negotiation | Stream, seq, target, scope |
| OFFER | Publisher or delegate | → Negotiating | Signed binding, target, contract, scope, plan |
| ACCEPT / REJECT | Receiver | → Accepted / Rejected | Plan digest; reason |
| WORKTREE_PAYLOAD | Publisher or repeater | → Materializing | Chunks with digests |
| RESULT | Receiver or repeater | Reports stage | Output, evidence, missing deps |
| REPAIR | Receiver | → Repairing | Failed node, reason, cone, alternative |
| EVIDENCE | Checker or repeater | Supplies evidence across a hop | Signed evidence, attestations, delegations |
| SUPERSEDE / CANCEL | Receiver | → Aborted (old demand) | Stream, seq, new demand |
| VALIDATION_APPROVAL | Validator or authority | → Ready | Signed approval with expected head |
| COMMIT_RECEIPT | Consumer | → Committed / Conflict | Signed receipt: prior head, head, status |

---

## 8. What the checks showed
`run_checks.py`: **38/38 fixtures valid · 11/11 malformed objects rejected · 95/95 semantic cases pass.** Every one of the handoff's 28 conformance cases now has at least one executable case; the rest test rules added along the way. Two encoders, the kit's own and the cbor2 library, produced byte-identical output for all 38 fixtures, including the split binding; that is a library cross-check, not an independent implementation. Every fixture validates against its own CDDL rule as well as the `arfp-object` union. C21 uses real process crashes: a worker process is killed with SIGKILL at the injected point (no cleanup runs), and a fresh process recovers from the journal on disk.

**Mutation check.** Seven critical guards were removed one at a time in a scratch copy (`python3 mutation_check.py` in the kit reproduces this). Each removal was caught: six turned the expected cases red, and removing torn-tail detection crashed the run. The tests have teeth:

| Guard removed | Result |
|---|---|
| Binding's contract-id check | G4 failed |
| Accepted-checker rule for evidence | C27c failed |
| Torn-tail detection in the journal | Whole run crashed in recovery |
| Evidence reuse keyed by input digests | C07b, C08b, C10a, C10b failed |
| Staged-bytes check before commit | C21-D failed |
| Split binding's template-digest check | T4 failed |
| Unknown-predicate check on binding overrides | T6 failed |

Scenario for the original 41 cases: one publisher, one repeater, a workstation and a phone on revision 28 of an assembly; six regions use five node classes (residual appears in R6, correctly refused). The Stage-1 cases each use an isolated target.

Limits: toy profiles, simulated decoders, no transport, a single-writer journal, crash points at record boundaries plus one torn write (not power loss with a lying disk cache).

| ID | Case | What happened |
|---|---|---|
| C01 | Different eligible plans target the same exact output | delta plan, literal plan and phone plan all give sha256:7357a6a44563 for the exact parts |
| C02 | Two approximate outputs satisfy the same contract | workstation sha256:24a7cec15050 and phone sha256:09c4a2aea47a both accepted |
| C03 | Patch targets a receiver's approximate (T-class) baseline | rejected baseline-mismatch: fairing-patch: base is T-class; contract allows ['E'] |
| C05 | Unknown required profile | rejected unsupported-profile: scene.assembly.v1 |
| C06 | Wrong decoder binding (runtime digest not held) | rejected unsupported-op: fairing: runtime not available to this executor |
| C09 | Region checks pass but a global invariant fails | fairing bound 0.425 mm passes; clearance 1.829 mm on the decoded surface vs 2.1 mm on the reference: output rejected |
| C11 | Exact-only contract, fallback uses an approximate class | rejected ineligible-plan: fairing: the contract does not permit latent nodes |
| C12 | Accepted plan is rewritten by a repeater | original phone plan: rejected unsupported-op: fairing: runtime not available to this executor; rewrite sha256:5fd3bad24de1 moves the decode to the repeater; rewritten plan eligible |
| C13 | Scoped result is accepted | bay-A scope may 'sign-off': False |
| C14 | Milestone passes while full result is incomplete | navigable milestone: navigate=True, measure=False |
| C15 | Receiver cancels a demand whose work another receiver needs | geo-A has one work key in both plans: True; geo-A canceled: False |
| C16 | Replaceable view demand superseded (camera jump) | cancel set = ['lod-A', 'view(ph_old)'] |
| C17 | Planner marks a required-transition stream obsolete | rejected permission-denied: stream 'edits' is required-transition; supersession cannot erase it |
| C18 | Old canceled result arrives late | rejected canceled: approval is for a superseded demand |
| C19 | Local head changed before commit | status conflict; head still sha256:7148c1fb73cb |
| C20 | Commit acknowledgment lost, request retried | retry returned byte-identical receipt: True |
| C22 | Cached artifact carries evidence for a different contract | applies under rev-28 contract: True; under rev-29 contract: False |
| C23 | Repeater without execute right asked to transform | rejected permission-denied: fairing: key:edge-1 holds no execute right |
| C24 | Two child grants each copy the parent's full budget | rejected resource-limit: children allocate 40000 cpu of a parent budget of 20000 |
| C24b | Child grant adds a right the parent lacks | rejected permission-denied: child adds rights ['rewrite'] |
| C24c | Children that partition the budget and narrow the scope | accepted; 8 000 + 12 000 ms of a 20 000 ms parent |
| C25 | Two repeaters each pass 0.5 mm locally | per-hop 0.3 + 0.3 mm each pass locally (naive accept: True); additive bound 0.6 mm rejects; true end-to-end 0.6 mm |
| C26 | Repeaters forward a request around a loop | 3 forwards, then drop-duplicate |
| C28 | Canonical encoding across independent implementations | 38/38 fixtures byte-identical in both encoders; unsorted map canonical: False; non-shortest int canonical: False; num('0.50') == num('0.5'): True |
| C28b | Map mixing integer and text keys | RFC 8949 and RFC 7049 orders agree on the mixed map: False; fixtures with uniform key types: 38/38 |
| C28c | Decimals 4([-2, 50]) (0.5) and 4([1, 1]) (10) | flagged: ['$.measured', '$.measured']; fixtures clean: 38/38 |
| R1 | Evidence moves by bound: sender eps + runtime divergence fits the threshold | 0.275 + 0.15 = 0.425 mm <= 0.5; true distance 0.271 mm (inside the bound) |
| R1b | Sender evidence measured on a different decode (other runtime) | rejected validation-failure: sender evidence was measured on different work; it cannot transfer |
| R2 | Non-reproducible (N) decoder on a reference-bound region at the receiver | rejected ineligible-plan: fairing: fairing.hausdorff.v1 cannot be checked at the receiver and N-class evidence does not transfer |
| R3 | Same N decoder placed at a checker repeater (placement converts determinism) | accepted; receiver gets checked, hash-verified bytes |
| R4 | T decoder whose bound uses a different metric (Chamfer vs Hausdorff) | rejected ineligible-plan: fairing: fairing.hausdorff.v1 cannot be checked at the receiver and T-class evidence does not transfer |
| R5 | Faster T decoder: eligible, but its bound does not fit | 0.318 + 0.25 = 0.568 mm > 0.5: repair |
| R6 | Repair by residual on the T-class decode | rejected baseline-mismatch: fairing-fix: base is T-class; contract allows ['E'] |
| R7 | Repair by literal reference geometry | accepted; costs 1026 bytes vs 653 latent |
| R8 | Generated content in a region that is neither free nor reference-bound | rejected ineligible-plan: cables: N-class output in 'cable-run' is neither labeled free nor reference-bound |
| R8b | Generated content with no declared region, feeding the result | rejected ineligible-plan: cables: N-class output reaches the result without a declared region |
| R9 | Contract marks a reference-bound region as free | rejected invalid-contract: fairing.hausdorff.v1: a free region cannot also be reference-bound |
| R10 | Fast path: same plan shape, current snapshot | accepted |
| R11 | Fast path replayed after the receiver moved on | rejected stale-state: fast-path plan assumes snapshot 42; receiver is at 43 |
| R12 | Fast path with a changed plan shape | rejected ineligible-plan: plan shape changed; full OFFER/ACCEPT required |
| R13 | Fast path on a required-transition stream | rejected ineligible-plan: stream edits has no fast path; full OFFER/ACCEPT required |
| G1 | Valid publisher binding, checked before planning | trace ['binding', 'eligibility']; envelope matches section 9 vector: True |
| G2 | Binding signed by a key not on the allow-list | rejected permission-denied: signing key is not on the allow-list |
| G3 | Binding signature with one bit flipped | rejected integrity-failure: signature does not verify |
| G4 | Offer carries a different contract than the one signed | rejected integrity-failure: binding names a different contract |
| G5 | Offer carries a different target revision than the one signed | rejected integrity-failure: binding names a different target |
| G6 | Publisher's valid signature on a delegation, presented as the binding | rejected integrity-failure: signed payload is a delegation, not a binding |
| G7 | Allow-listed repeater key signs a binding in the publisher's name | rejected permission-denied: binding names a publisher other than its signer |
| G8 | Expired binding | rejected expired-authority: binding has expired |
| G9 | Forged binding and an ineligible plan together | rejected integrity-failure: signature does not verify; eligibility calls: 0 |
| G10 | Offer with no binding | rejected permission-denied: offer carries no signed binding |
| C04a | Dependency evicted after ACCEPT, no fallback | status aborted (missing-dependency); RESULT missing ['sha256:34b5b2732b11']; journal {'genesis': 1}; head unchanged: True; staged files: 0 |
| C04b | Dependency evicted, prebound literal fallback | REPAIR failed=base affected=['base', 'root', 'upd'] alt=base-lit; receipt committed; output equals no-fault control: True |
| C04c | New offer after the aborted attempt, re-supplying the artifact | receipt committed |
| C04d | Audit trail of the aborted attempt | events: ['accept', 'abort'] |
| C07a | Procedural generator diverges, no fallback | status aborted; executed ['gen']; audit names node gen, runtime sha256:52167141903c, observed sha256:0566964aa92b |
| C07b | Generator diverges, prebound literal fallback | repairs ['gen']; receipt committed |
| C08a | Residual on the exact R1 base misses its bound | status aborted (validation-failure); head still R1: True; journal {'genesis': 1} |
| C08b | Well-formed residual against the same baseline | receipt committed |
| C10a | Branch c fails late; a is independent; cross-branch x reads a and b | REPAIR failed=c affected=['b', 'c', 'root']; evaluations p-a=1 x-len=2 p-b=2; final x covers new b: True; receipt committed |
| C10b | Cross-branch x passed on the divergent b before repair | first x pass=True on the divergent b: True; final x on the repaired b: True |
| C10c | Repair cannot restore the cone | status aborted; journal {'genesis': 1}; head unchanged True |
| C21-A | Killed after the approval is journaled, before the head swap | killed by SIGKILL; recovery [('resolved-pending-approval', 'tx-c21-990')]; head is rev 3: True; receipt committed, byte-identical to control: True; journal {'genesis': 1, 'approval': 1, 'head': 1, 'receipt': 1} |
| C21-C | Retry with the same transaction after recovery | byte-identical: True; journal before {'genesis': 1, 'approval': 1, 'head': 1, 'receipt': 1} after {'genesis': 1, 'approval': 1, 'head': 1, 'receipt': 1} |
| C21-E | Offer arriving while the receiver is recovering | state recovering: stale-state; after recovery, a plan built on snapshot 0: rejected stale-state: plan assumes snapshot 0; receiver is at 1 |
| C21-T | Killed halfway through writing the head record | killed by SIGKILL; recovery ['truncated-torn-tail', ('resolved-pending-approval', 'tx-c21-990')]; receipt byte-identical: True |
| C21-H | Killed after the head swap, before the receipt is durable | killed by SIGKILL; recovery [('receipt-from-commit', 'tx-c21-990')]; byte-identical: True |
| C21-R | Killed after the receipt is durable | killed by SIGKILL; recovery actions []; retry byte-identical: True |
| C21-B | Another commit moved the head before recovery | receipt conflict, head None, prior-head is the moved head: True; head still concurrent: True; staged output kept: True |
| C21-D | Staged output corrupted while the receiver was down | receipt aborted; head unchanged: True |
| C21-I | Invariants across all seven journals | 7/7 journals clean |
| C27a | Repeater forwards the origin's signed evidence unchanged | receipt committed; audit triple ['sha256:dc7c2d06f848', 'sha256:b29449620ad1', 'sha256:2928b6ea8cc0']; chain rebuilt from the receipt: 3 links, relay delegation verified; approval cites exactly the audited evidence |
| C27b | Repeater adds a signed attestation naming the origin evidence | receipt committed; audit triple ['sha256:dc7c2d06f848', 'sha256:b29449620ad1', 'sha256:32fd123d34a0']; chain rebuilt from the receipt: 4 links, relay delegation verified; approval cites exactly the audited evidence |
| C27c | Repeater re-signs the evidence as its own, origin copy dropped | rejected validation-failure: evidence for p1 is signed by key:repeater-2, who is not an accepted checker |
| C27d | Repeater edits the evidence and keeps the origin signature | rejected integrity-failure: signature does not verify |
| C27e | Attestation names origin evidence that was not delivered | rejected validation-failure: attestation names evidence that was not delivered |
| C27f | Required predicate's evidence dropped entirely | rejected validation-failure: no evidence for required predicate p1 |
| C27g | Repeater attests without the attest right | rejected permission-denied: key:repeater-2 holds no attest right |
| C27h | Repeater substitutes the payload bytes | rejected validation-failure: evidence was measured on different bytes or another contract |
| C27i | Repeater rewrites the plan without the rewrite right | rejected permission-denied: key:repeater-2 holds no rewrite right |
| C27j | Forged origin binding, valid repeater signatures | rejected integrity-failure: signature does not verify |
| T1 | First offer of a session carries the template inline | trace ['binding', 'eligibility']; cached ['sha256:0d75d2d04ed3']; materialized id equals the whole contract's: True |
| T2 | Next revision names the cached template; the offer omits it | trace ['binding', 'eligibility']; offer 998 B vs 1505 B with the whole contract inline |
| T3 | Template neither cached nor offered | rejected missing-dependency: template sha256:0d75d2d04ed3 is neither cached nor offered; trace ['binding']; eligibility calls 0 |
| T4 | Inline template differs from the one the binding names | rejected integrity-failure: offered template is not the one the binding names |
| T5 | An amended template in the cache never applies to bindings that name the original | amended id differs: True; with only the amended one cached: rejected missing-dependency: template sha256:0d75d2d04ed3 is neither cached nor offered; with both cached the binding resolves to the original rules (repairs=1) |
| T14 | Offer names a template digest that disagrees with the binding | rejected integrity-failure: offer names a different template than the binding |
| T6 | Binding sets a value for a predicate the template lacks | rejected invalid-contract: binding sets expected for p-ghost, which the template lacks |
| T7 | Digest-match predicate left without an expected digest | rejected invalid-contract: p-doc: no expected digest in the template or the binding |
| T13 | Publisher signs a binding for a template whose authority names someone else | rejected permission-denied: signer is not the template's publisher |
| T8 | Evidence from revision 1 offered for revision 2 under the same template | applies under rev 2: False; contract ids differ: True; template ids equal: True |
| T9 | Threshold override in one revision's binding | rev 2 (default): validated; rev 3 (override 81): aborted (validation-failure) |
| T10 | Forged split binding and an ineligible plan together | rejected integrity-failure: signature does not verify; eligibility calls 0 |
| T11 | Split-form update commits; the receipt alone rebuilds binding, template and evidence | receipt committed; chain ['sha256:28d720e6ffa5', 'sha256:0d75d2d04ed3', 'sha256:058119b581ec']; template in chain: True |
| T12 | Template plus binding reproduce the whole assembly contract | identical: True; same id: True; moved to the binding: 2 expected digests, 1 reference |

### Validator findings (a C28 problem one level up)

pycddl 0.6.4 (the Rust `cddl` crate) needed three rewrites that RFC 8610 treats as equivalent: `null / x` instead of `x / null`; a quoted `"bytes"` key; choices written inline inside array types. It also doesn't enforce `nint`, and it skips tag contents inside a type choice, so the checker re-validates every decimal itself (C28c). Through the top-level `arfp-object` union it accepted a split binding whose `expected` field was a list, which the `binding` rule itself rejects, so the kit now validates every object against its own rule too (and keeps that object as a negative case). No second CDDL tool ran: the reference Ruby `cddl` gem couldn't install under the environment's network policy, and zcbor 0.9.1 couldn't parse plain bareword keys. **The schema hasn't been through two independent CDDL tools yet.**

### What an independent review caught (all fixed)

- A non-reproducible node that declared no region could put generated content into a result unlabeled. Now refused (R8b).
- The workstation's acceptance didn't actually apply ε + δ; the transfer record was hard-coded to pass and stored δ as if measured. Now the bound gates acceptance and δ sits in a separate `bound` field.
- Non-normalized decimals (4([−2, 50]), 4([1, 1])) passed. Now flagged (C28c).
- `head` was missing from the object union. Added, and moved to the outcome plane.
- C24 tested over-allocation, not copying. Now two children each copy the full parent budget.
- Overclaims removed: "crash-safe" commit (claimed before C21 was tested), "replay-safe" fast path (the snapshot only catches late replays), "skips OFFER" (it skips the wait for ACCEPT), "the second half is new" (only approximate rebuilds are new), the Wyner–Ziv floor stated for the wrong case, and Slepian–Wolf without its asymptotic qualifier.

---

## 9. Audit of the latest outside contribution (COSE binding + C04/C21 fixtures)

The proposal itself is right and matches the top open item: authenticate the publisher's binding of target revision to contract before any planning ("authentication as gate zero"), and close the Stage-1 recovery surface with C04 and C21. The test vectors, though, don't verify. Every check below was run against the bytes as given.

| Claim in the contribution | Result |
|---|---|
| Public key d75a9801… for seed 9d61b19d… | **Correct** (RFC 8032 Ed25519 test key 1) |
| `contract_digest` = 3097c554… for the canonical contract JSON | **Wrong.** SHA-256 of that exact string is 1bd40b7378d2e9a041ae50783adec7d45b28f823d985424013859a58ac047d22 |
| Timestamp 1775875200 = 2026-10-11 00:00 UTC | **Wrong.** 1775875200 is 2026-04-11 02:40 UTC; Oct 11 2026 00:00 UTC is 1791676800 |
| Payload hex encodes that timestamp | **Wrong.** The payload's last item is 0x69db6400 = 1775985664, a third value |
| Protected header is 41 bytes (`5829`) | **Wrong.** The header given is 38 bytes (`5826`) |
| Payload is 90 bytes (`585a`) | **Wrong.** The payload given is 92 bytes; the envelope doesn't parse |
| Signature 793c1f1a… is valid | **Invalid.** It doesn't verify over the stated Sig_structure |
| `alg` −7 for Ed25519 (second note) | **Wrong.** −7 is ES256; EdDSA is −8 (the first note has it right) |
| C21 approval signature `3045022100…` | A DER ECDSA prefix, inconsistent with an Ed25519 profile |
| C21 `approval_hash` `sha256:app_c21_…` | Not hex; not a digest |

Design conflicts with the validated schema:

- **Two encodings.** The contract digest is taken over JSON ("RFC 8785 / RFC 8949" is cited together), while every other ARFP id is SHA-256 over deterministic CBOR. Pick one: the kit uses CBOR.
- **Different identity forms.** String digests (`"sha256:…"`), string revisions (`"rev-2"`) and `head:scene-root:rev-1` refs don't match the schema's `[alg, bstr]` digests, uint revisions and head ids. They need mapping, not a second vocabulary.
- **Different error vocabulary.** `ERR_DEPENDENCY_LOST`, `ERR_UNTRUSTED_OFFER` etc. vs the schema's `missing-dependency`, `permission-denied`/`integrity-failure`.
- **Conflict receipt.** Path B sets `committed_head` to the moved head; in the schema a conflict receipt carries `head: null` and leaves the head untouched.

### 9b. Re-audit of the two "corrected" vector sets (same session)

Both revisions claim to be verified, and neither verifies. Checked against the bytes as printed, with the RFC 8032 key:

| Check | Set 1 ("byte-exact") | Set 2 (with generator script) |
|---|---|---|
| Protected header length | Declared 38 (`5826`): correct | Declares 37 (`5825`), but the map is 38 bytes: wrong |
| Payload length | Payload is 92 bytes; envelope declares 88 (`5858`): wrong, envelope doesn't parse | 92 (`585c`): correct |
| Signature over the stated Sig_structure | **Invalid** | **Invalid** |
| Contract digest | b527453d… matches neither the JSON nor the CBOR of the stated contract (CBOR gives a5eeedd4…) | Running its own generator gives c441cc0f…, not 97beeaeb… |
| Expected output digest | n/a | SHA-256 of its own output string is fb0406fa…, not 72054ff4… |
| Timestamp 1775875200 labeled "2026-10-11" | Still wrong: it is 2026-04-11 02:40 UTC (Oct 11 is 1791676800) | Same |
| C21 approval hash / receipt signatures | `sha256:app_c21_…` (not hex), `c0ffee00…` placeholders | Fixed to hex, but reuses the binding signature as the approval signature |

Set 2's printed values were not produced by the script printed next to them: running the script yields different digests and a different signature. The script itself is sound and is the right method; only its outputs were invented.

Where set 2 is right: a conflict receipt should keep the transaction's *expected* prior head in its audit trail, not the concurrent head. The kit's receipt already records `prior-head` (the head found at commit time) while the approval carries `expected-head`, so both appear in the record.

Rule going forward: no hex enters the spec unless it was produced by running code in the kit. The verified binding vector in section 9 stands.

### Correct binding vector, in the kit's own profile

Same RFC 8032 key, so anyone can reproduce it. The kit now regenerates this envelope byte for byte (case G1). Binding payload = canonical CBOR map; envelope = tagged COSE_Sign1 (tag 18). Verified, canonical, and a one-bit tamper of the payload is rejected.

```
kid (protected label 4) = "pubkey-ed25519-static-allowlist1" (32 bytes)
target id   = dba9708beae13bb942a7b772cfd0166dd403ca4db9f4b3844eba732699002486
contract id = 3089acac691520486fc7b4d38037fbdd5db33f494556df8358590b759bea6a53
payload     = {"kind":"binding","target":[-16,h'dba9…'],"contract":[-16,h'3089…'],
               "publisher":"key:publisher","issued":1791676800000}

payload_hex   a5646b696e646762696e64696e67666973737565641b000001a128425c0066746172676574822f5820dba9708beae13bb942a7b772cfd0166dd403ca4db9f4b3844eba73269900248668636f6e7472616374822f58203089acac691520486fc7b4d38037fbdd5db33f494556df8358590b759bea6a53697075626c69736865726d6b65793a7075626c6973686572
protected_hex a201270458207075626b65792d656432353531392d7374617469632d616c6c6f776c69737431
signature     97616d5734978c9ebd1c605775d4dbbf4528fb7f7f2a5fa1a27af7ab5a359b3fa3d8a1182a55c555b9402e6ed78bceaac7bade30881572dc76831e7d0434270a
envelope      d2845826a201270458207075626b65792d656432353531392d7374617469632d616c6c6f776c69737431a0588ea5646b696e646762696e64696e67666973737565641b000001a128425c0066746172676574822f5820dba9708beae13bb942a7b772cfd0166dd403ca4db9f4b3844eba73269900248668636f6e7472616374822f58203089acac691520486fc7b4d38037fbdd5db33f494556df8358590b759bea6a53697075626c69736865726d6b65793a7075626c6973686572584097616d5734978c9ebd1c605775d4dbbf4528fb7f7f2a5fa1a27af7ab5a359b3fa3d8a1182a55c555b9402e6ed78bceaac7bade30881572dc76831e7d0434270a  (253 bytes)
```

Schema addition (now in the kit; see section 10 and Appendix A):

```cddl
binding = {                             ; signed by the publisher; checked before any planning
  kind: "binding",
  target: digest,                       ; id(target)
  contract: digest,                     ; id(contract)
  publisher: party,                     ; must equal target.publisher and contract.authority.publisher
  issued: uint,                         ; epoch ms
  ? expires: uint,                      ; epoch ms
}
; OFFER gains:  binding: cose-sign1     ; payload = canonical CBOR of `binding`
```

Gate-zero rule: verify the COSE_Sign1 with an allow-listed `kid`, then require `binding.target == id(offer target)` and `binding.contract == id(offer contract)` before eligibility runs; else REJECT `permission-denied` (unknown key, or a signer who isn't the publisher), `integrity-failure` (bad signature, wrong payload kind or mismatched ids) or `expired-authority`. Section 10 gives the full order.

---

## 10. Stage 1, built and executed
The six cases left open, plus the gate, are now running code in the kit (`arfpkit/gate.py`, `engine.py`, `journal.py`, `provenance.py`, `stage1.py`). All 40 Stage-1 cases and the 14 contract-split cases pass, and the mutation check above shows they fail when the guards are removed.

### Gate zero (G1–G10)

Order is enforced: a forged binding is reported before any planning, and eligibility is never called (G9). The receiver checks, in order:
1. The key id is on the allow-list (G2).
2. The signature verifies (G3).
3. The payload's `kind` is `binding` (G6: a valid publisher signature on a delegation is refused).
4. The signer is the binding's publisher, the target's publisher and the contract's authority (G7).
5. The binding names `id(target)` and `id(contract)` of the offered objects (G4, G5).
6. It hasn't expired (G8).

G1 uses the section 9 vector: the kit regenerates it byte for byte from the RFC 8032 key.

### C04, C07, C08, C10 (exact profile `bytes.exact.v1`)

- Checks run when a node emits a region, so a divergent output is never consumed downstream (C07a: the dependent never ran).
- Repair picks the nearest failed-or-ancestor node with a prebound fallback, invalidates that node's cone, and re-runs. It aborts when no fallback or repair budget remains (C04a, C08a, C10c).
- Evidence is reused only if every input digest is unchanged. In C10, the cross-branch check passed on the divergent output in the first pass; after repair it was re-run on the new bytes (evaluated twice), while the independent branch's evidence was reused (evaluated once).
- Nothing is staged until validated; aborted attempts leave the journal holding only its genesis record.

### C21 (real crashes)

The journal is append-only, with [length][CRC32][canonical CBOR] records, each fsynced. The write-ahead order is approval → head swap (or conflict/abort outcome) → receipt. Each crash is a SIGKILL of a separate worker process; a fresh process then recovers from what is on disk.

| Crash point | Recovery |
|---|---|
| After approval, before head swap | Applies the swap; receipt byte-identical to an uncrashed run |
| Torn head record | Drops the torn tail, then as above |
| After head swap, before receipt | Rebuilds the receipt from the journal, byte-identical |
| After receipt | Nothing to redo; retry returns the stored receipt |
| Head moved by another commit | Conflict receipt; moved head untouched; staged output kept |
| Staged output corrupted while down | Aborted; never commits other bytes |

Offers are refused while recovering, and stale snapshots are refused afterwards (C21-E). An invariant sweep over all seven journals finds every head swap preceded by a durable approval and one receipt per transaction.

### C27 (multi-hop provenance)

- Evidence crossing a hop must be signed by its checker; a repeater's attestation names that evidence by hash and is accepted only if the evidence itself is delivered and verifies.
- Delegations are publisher-signed; `attest`, `forward` and `rewrite` are separate rights.
- Approvals record `relayed-by` delegations, so a third party rebuilds binding → delegation → (attestation) → evidence from the receipt alone (C27a, C27b).
- Refused: re-signed evidence (C27c), edited evidence with the old signature (C27d), attestation without its evidence (C27e), missing evidence (C27f), attestation without the right (C27g), substituted payload (C27h), rewrite without the right (C27i), forged binding (C27j).

### Contract split (T1–T14)

Built from the contract-split handoff note (2026-10-11), with three changes that came from implementing it:
1. **The binding also carries per-revision designated references** (`references`, keyed by predicate id). Metric predicates such as the fairing bound need this revision's reference geometry, and the handoff's `expected` map only covered expected digests.
2. **The contract identity is id(materialize(template, binding)), not the template digest.** Naming the template alone would drop the target and the per-revision values from the identity, and evidence for one revision would then match the next (T8 shows the template ids are equal across revisions while the contract ids differ). Materializing gives exactly the whole contract (T12: identical object and id for the assembly contract), so plans, evidence, approvals, heads and receipts are unchanged.
3. **The template has no signature of its own.** Each publisher-signed binding covers the template's digest, which authenticates it; a template signature would add bytes and no authentication.

The whole-contract binding (v0.1 form) stays valid, so the published section 9 vector and G1 are unchanged. The schema makes the two forms exclusive: a binding naming both a contract and a template is rejected.

Gate zero for a split binding checks, in order: allow-list, signature, payload kind, signer is the binding's publisher and the target's publisher, binding names id(target), template is the one named (inline or cached; T3, T4, T14), signer is the template's authority (T13), expiry, then the overrides (T6, T7). A template enters the cache only after a binding that names it verifies.

| Measured (assembly fixture) | Bytes |
|---|---|
| Whole contract, per revision | 1,648 |
| Contract template, once per session | 1,478 |
| Binding envelope: whole form → split form | 253 → 438 |
| OFFER for a new revision, whole contract inline | 3,310 |
| OFFER, split, template inline (first use) | 3,325 |
| OFFER, split, template cached | 1,838 |
| OFFER, split, template cached, plan by id | 707 |

The cases also show a threshold override applying to its own revision only (T9), the forged-binding order holding (T10), and a split-form update committing with the receipt chain rebuilt through the template (T11).

### What changed from the drafts (Grok and other AI) and why

The drafts' structure was right. These changes came from building them:

1. **RFC 8152 → RFC 9052.** 8152 is obsoleted.
2. **Ed25519 (−8), not ES256 (−7), for fixtures.** ECDSA signatures are randomized, so test vectors can't reproduce byte for byte; Ed25519 is deterministic.
3. **Bind `id(target)`, not just id + revision strings,** so the publisher and profile fields are covered too.
4. **Type the signed payload (`kind`).** The publisher key also signs delegations and evidence; untyped, one could pass as another (G6).
5. **A map, not a positional array with an optional trailing timestamp.** Optional trailing positions are fragile across implementations.
6. **No `H(Target || Contract)`.** Raw concatenation is ambiguous; hash canonical encodings (ids) instead.
7. **Forwarded evidence must be signed.** Without the origin checker's signature, "byte-for-byte identical to what the origin produced" can't be checked (C27d).
8. **An embedded hash proves nothing unless the hashed evidence is delivered** (C27e). Repeater signatures add to the origin's, never replace them (C27c).
9. **C27's oracle covered only the positive paths.** Negatives need "receipt count 0, head unchanged".
10. **"No capability exchange occurs" was out of order.** CAPABILITIES and STATE come before OFFER; the gate blocks planning and acceptance.
11. **Idempotence is keyed by transaction id, not attempt id.** Attempts retry planning; transactions are commits.
12. **Error names mapped to the schema's codes:** missing-dependency, validation-failure, integrity-failure, permission-denied, expired-authority, stale-state.
13. **C21 Path B: both heads are kept.** The receipt records the head found at commit time and the approval carries the expected head, so both are in the audit trail.

---

## 11. Next work, in order
Reordered after the speed review (section 15). The protocol has to stop being slower than HTTP with compression dictionaries before anything else is worth measuring. The contract split, item 2 of the previous order, is built (section 10).

1. **Push profile in the kit:** a standing DEMAND as the subscription; binding reference, plan-template reference and payload in one flight; REPAIR only on a miss; a ~128-byte frame; a chunked tree hash so verification scales with the change. First test: H1, parity with pub/sub plus RFC 9842 deltas.
2. **Stage 4 demo** with mixed receivers (one strong, one weak) over a predictability × churn grid: one publisher, one repeater, two receivers, camera jumps; count every link's bytes. Tests H2–H5.
3. **Second CDDL tool, then a second implementation** (another language, or another model given only the schema and the 38 vectors). Every divergence is a spec ambiguity.
4. **Stage 5 measurement** against strong baselines: HTTP/3 + RFC 9842, glTF/Draco and 3D Tiles, and LMCache-style transfer for AI state. Cold and warm caches; publish the negative cases (small frequent updates, novel content).
5. **Harden the journal:** power-loss testing, fsync of the directory on file creation, disk write-cache behavior, group commit.

## 12. Open items
- Key distribution and rotation beyond the static allow-list; revocation of bindings and delegations.
- Divergence bounds for real decoders: fixed-point error analysis or an explicitly statistical claim.
- STATE privacy: scoped have-queries by default; approximate inventories need confirmation.
- Payload-size leakage: whether contracts set a padding policy.
- Receiver trust policy for repeater checkers.
- Profile registry: definitions and vectors for names like `hausdorff-linf.v1` and `bytes.exact.v1`.
- Multi-writer scenes (telepresence) stay out of v0.1.

## 13. Positioning and ownership notes (not legal advice)

- Ingredients have strong prior art: content-addressed DAGs (IPLD), remote execution caches (Bazel), Named Function Networking and Compute First Networking, RFC 9842 dictionaries, Media over QUIC, SCITT receipts, neural codecs. The defensible contribution is narrow: one negotiated contract binding approximate acceptance, evidence transfer by determinism class, labeled generation, receipts, and per-node generate-vs-fetch.
- The core idea has been publicly described (X thread and replies). In the US that starts a one-year grace period for your own disclosure; many other countries have no general grace period. The US is first-inventor-to-file, so a dated header doesn't establish priority. Apache 2.0 includes a patent grant. IETF participation requires patent disclosure (BCP 79), and working groups favor royalty-free terms. Talk to a patent attorney before publishing more.

## 14. Sources

- RFC 8949 (CBOR): https://www.rfc-editor.org/rfc/rfc8949.html
- RFC 8610 (CDDL): https://www.rfc-editor.org/rfc/rfc8610.html
- RFC 9052 (COSE structures): https://www.rfc-editor.org/rfc/rfc9052.html
- RFC 9054 (COSE hash algorithms): https://www.rfc-editor.org/rfc/rfc9054.html
- RFC 6716 (Opus): https://www.rfc-editor.org/rfc/rfc6716.html
- RFC 8446 (TLS 1.3): https://www.rfc-editor.org/rfc/rfc8446.html
- RFC 9842 (Compression Dictionary Transport): https://www.rfc-editor.org/rfc/rfc9842.html
- 3GPP TS 26.073 (AMR ANSI-C code): https://www.freecalypso.org/pub/GSM/3GPP/archive/26_series/26.073/26073-b00.pdf
- Slepian & Wolf (1973): https://itsoc.org/node/36672
- Wyner & Ziv (1976): https://itsoc.org/node/36673
- Blau & Michaeli (2019): https://arxiv.org/abs/1901.07821
- Ballé, Johnston & Minnen (ICLR 2019): https://research.google/pubs/integer-networks-for-data-compression-with-latent-variable-models/
- Bettner, "1500 Archers on a 28.8" (2001): https://www.gamedeveloper.com/programming/1500-archers-on-a-28-8-network-programming-in-age-of-empires-and-beyond
- Chrome, removing HTTP/2 Server Push (2022): https://developer.chrome.com/blog/removing-push
- Cache Digests for HTTP/2 (expired draft): https://datatracker.ietf.org/doc/draft-ietf-httpbis-cache-digest/
- RFC 8032 (EdDSA, test key 1): https://www.rfc-editor.org/rfc/rfc8032.html
- pycddl: https://pypi.org/project/pycddl/

---

## 15. Speed review (summary; full text in [ARFP-internet-speed-review.md](ARFP-internet-speed-review.md))

**Verdict:** faster for specific transfers, not for the internet in general.
- The lever is receiver state: the bits that must cross are H(X|Y), not H(X).
- It pays where transfers are byte-bound (big objects, slow or cold links, video, AI state), not on web pages bound by round trips and CPU.
- A separate agent checked the review twice against the kit's outputs, the research notes and the original sources.

**Measured** (`bench/delta_bench.py`, real npm releases). A receiver holding the previous release needs:

| Workload | Fewer bytes than brotli |
|---|---|
| three.js updates | 18–190× (median 75×) |
| TypeScript patch releases | 560–1,117× |
| A TypeScript release that re-indented most of the file, generic delta | 1.7× |
| The same release, coding indentation and text separately | 8.1× |
| three.js, base ten releases stale | 6× (about 12× the typical up-to-date delta) |

**Modeled** (`bench/speed_model.py`; RTT 56 ms, warm 100 Mbit/s). A three.js update takes:

| Path | Time |
|---|---|
| HTTP with an RFC 9842 dictionary | 56 ms |
| Plain HTTP, whole file | 74 ms |
| ARFP v0.1 negotiated | 113 ms |

- **The negotiation round trip is the problem.** It loses wherever one round trip is worth more than the bytes saved: 700 KB at 100 Mbit/s and 56 ms.
- **The v0.1 fast path ties RFC 9842 on 1.2 MB.** On 9 MB it trails by 12%: the output hash costs 7 ms on this CPU.
- **A push profile ties any pub/sub channel carrying dictionary deltas** (28 ms from the publisher's event, against 84 ms for notify-then-fetch). Pure deltas therefore can't be ARFP's edge.

**Where ARFP can win.**
- Per-receiver choice among modes.
- Upstream decode for weak receivers.
- Cancellation of superseded work.
- Approximate or generated reconstruction under a contract.

AI state is the clearest case.
- **Send-vs-recompute break-even** is 4–29 Gb/s per H100 of receiver compute for an uncompressed KV cache (Llama 3.1 8B and 70B, modeled), and scales with the receiver's GPU count.
- **Choosing per receiver halved the summed time** against the best fixed strategy in a three-receiver model, all of it from lossy (class T) compressed caches.
- **Demanding exact results cost 2.1× on pinned stacks and 15× on mixed stacks.**

**Design changes (the push profile).**
- A standing DEMAND as the subscription.
- One-flight updates.
- REPAIR only on a miss (the BIP 152 compact-blocks pattern).
- STATE as a named base, filter or sketch, scoped and salted.
- Publisher-precomputed deltas and ε.
- A chunked tree hash.
- Provisional → validated promotion.
- Group commit and batched receipts.
- A planner that works by table lookup over templates.

**Honest claim to test.** ARFP makes approximate and generated reconstruction checkable, and its planner beats any fixed transfer strategy when receivers differ. Stage 4/5 test this with hypotheses H1–H5 and pre-registered kill criteria; see the full review §11.

---

## Appendix A — Full schema (`arfp-v0.1.cddl`, 384 lines, as validated on 2026-10-11; the kit's current schema adds the speed-mechanism fields and objects)

```cddl
; ARFP v0.1 core schema -- design draft, not a registered wire format.
; Encoding: deterministic CBOR (RFC 8949 section 4.2.1). Schema language: CDDL (RFC 8610).
;
; Identity rules
;   object id    id(o)  = H(canon(["arfp/0", o.kind, o]))         domain-separated per kind
;   artifact id  H(bytes)                                          raw bytes, no wrapper
;   work key     wk(v)  = H(canon(["arfp/0", "work", class, op, runtime, params,
;                                  payload, artifact, base, [* wk(dep)]]))
;   head id      id(head record)                                   compare-and-swap key for commits
;   binding hash H(COSE_Sign1 bytes of the binding)                approvals and audit logs name it
;   contract id  under a split binding: id(materialize(template, binding)), the same id the
;                equivalent whole contract has, so plans, evidence, approvals and heads don't change
; Signed objects: binding (publisher), delegation (issuer), evidence (checker), attestation
;   (attester), approval and receipt (consumer) travel as COSE_Sign1 with the object as payload.
;   A contract template is not signed: every binding that names it is, over its digest.
;   The payload's "kind" field types the signature, so one key's binding can't pass as a receipt.
; Numbers: protocol objects carry no binary floats. Integral values are ints; others are decimal
;   fractions (tag 4) with a negative exponent and a mantissa not divisible by 10.
; Map keys: every ARFP map uses text keys, so RFC 8949 and RFC 7049 canonical orders agree.
; Hop-varying envelope fields (ttl, via) are excluded from dedup keys and signatures.
; Tool note: three spellings here are equivalent rewrites for the Rust cddl crate (pycddl 0.6.4):
;   "null / x" instead of "x / null"; a quoted "bytes" key; and choices written inline inside
;   array types (node-classes, det-classes, evidence-modes, rights), because that crate only tries
;   the first alternative of a named choice used as an array element. That crate also skips tag
;   contents inside a type choice (exact-num), so decimals are re-checked by the number rule.

arfp-object = target / scope / contract / contract-template / binding / capabilities / state /
              demand / plan / evidence / attestation / approval / receipt / head / delegation /
              rewrite / repair / message

; ---------- primitives ----------
digest = [alg: int, value: bstr]        ; alg = COSE hash algorithm id (RFC 9054); -16 = SHA-256
name = tstr                             ; versioned identifier, e.g. "geom.clearance.v1"
party = tstr                            ; participant key id
ms = uint                               ; milliseconds
exact-num = int / decimal
decimal = #6.4([exponent: int .lt 0, mantissa: int])   ; mantissa not divisible by 10 (checked on decode)
det-class = "E" / "T" / "N"             ; bit-exact / bounded divergence / non-reproducible
node-class = "reference" / "delta" / "procedural" / "latent" / "residual" / "literal"
node-classes = [+ ("reference" / "delta" / "procedural" / "latent" / "residual" / "literal")]
det-classes = [+ ("E" / "T" / "N")]
cose-sign1 = #6.18([protected: bstr, unprotected: {* any => any}, payload: null / bstr, signature: bstr])

resources = {
  ? "bytes": uint,
  ? cpu: ms,
  ? memory: uint,
  ? wall: ms,
  ? repairs: uint,
}

; ---------- identity plane ----------
target = {
  kind: "target",
  object: tstr,
  revision: uint,
  publisher: party,
  profile: name,
}

scope = {
  kind: "scope",
  target: digest,
  select: "all" / [+ tstr],             ; "all" is the only scope that can authorize full-target use
  ? milestone: tstr,
}

; ---------- agreement plane ----------
contract = {
  kind: "contract",
  target: digest,
  profile: name,
  classes: node-classes,
  acceptance: [+ predicate],
  ? invariants: [+ predicate],
  ? free: [+ tstr],                     ; regions where plausible generation is allowed and labeled
  determinism: {
    baseline-eligible: det-classes,     ; whose outputs may serve as delta/residual bases
    evidence-transfer: det-classes,     ; whose sender-side evidence may cover a receiver's output
  },
  evidence: {
    modes: evidence-modes,
    ? checkers: [+ party],
    ? max-age: ms,
  },
  authority: {
    publisher: party,
    local-commit: bool,
    ? delegation-root: digest,
  },
  updates: [+ stream-rule],
  limits: resources,
  ? milestones: [+ milestone],
}

; Session contract template: every rule that does not change with a target revision. Cached by
; digest; amending any field makes a new template. Predicates may leave out per-revision values
; (expected digests, designated references), which each binding then supplies.
contract-template = {
  kind: "contract-template",
  profile: name,
  classes: node-classes,
  acceptance: [+ predicate],
  ? invariants: [+ predicate],
  ? free: [+ tstr],
  determinism: {
    baseline-eligible: det-classes,
    evidence-transfer: det-classes,
  },
  evidence: {
    modes: evidence-modes,
    ? checkers: [+ party],
    ? max-age: ms,
  },
  authority: {
    publisher: party,
    local-commit: bool,
    ? delegation-root: digest,
  },
  updates: [+ stream-rule],
  limits: resources,
  ? milestones: [+ milestone],
}

binding = {                             ; signed by the publisher; checked before any planning
  kind: "binding",
  target: digest,                       ; id(target)
  ( contract: digest //                 ; whole form: id(contract) for this one revision
    template: digest,                   ; split form: id(contract-template), plus this revision's
    ? expected: {* name => digest},     ;   expected digests,
    ? references: {* name => digest},   ;   designated references,
    ? params: {* name => exact-num} ),  ;   and threshold overrides, each keyed by predicate id
  publisher: party,                     ; must equal target.publisher and the contract's or template's
  issued: uint,                         ;   authority.publisher; epoch ms
  ? expires: uint,                      ; epoch ms
}

predicate = {
  id: name,
  kind: "digest-match" / "metric-bound" / "invariant" / "schema",
  ? covers: "all" / [+ tstr],
  ? reference: digest,                  ; designated reference (reference-bound predicate)
  ? expected: digest,                   ; authenticated expected digest or feature digest
  ? metric: name,
  ? threshold: exact-num,
  ? units: tstr,
  ? composition: "end-to-end" / "additive",   ; additive only for true metrics
  ? mode: evidence-mode,
  validator: name,
}

evidence-mode = "digest-match" / "feature-digest" / "reference-metric" /
                "checker-attestation" / "spot-reexecution"
evidence-modes = [+ ("digest-match" / "feature-digest" / "reference-metric" /
                     "checker-attestation" / "spot-reexecution")]

stream-rule = {
  stream: tstr,
  mode: "replaceable" / "required-transition",
  ? fast-path: "shape-equal",           ; same plan shape: execute without waiting for ACCEPT
}

milestone = {
  name: tstr,
  roots: [+ tstr],                      ; region names, not plan node ids
  acceptance: [+ name],
  uses: [+ tstr],
}

delegation = {
  kind: "delegation",
  issuer: party,
  grantee: party,
  target: digest,
  contract: digest,
  scope: digest,
  rights: rights,
  recipients: [+ party],
  expires: uint,
  subdelegate: bool,
  budget: resources,                    ; children partition the parent's budget, never copy it
  ? parent: digest,
}

rights = [+ ("cache" / "forward" / "execute" / "rewrite" / "check" / "checkpoint" / "attest")]

; ---------- plan plane ----------
capabilities = {
  kind: "capabilities",
  endpoint: party,
  protocols: [+ tstr],
  profiles: [+ name],
  classes: node-classes,
  runtimes: [* runtime],
  limits: resources,
}

runtime = {
  id: name,
  digest: digest,
  ( det: "E", vectors: digest //                              ; bit-exact: conformance vectors
    det: "T", vectors: digest, bound: divergence-bound //     ; bounded: vectors plus a declared bound
    det: "N" ),                                               ; non-reproducible
}
divergence-bound = { metric: name, value: exact-num, units: tstr }

state = {
  kind: "state",
  endpoint: party,
  snapshot: uint,
  heads: [* head],
  ? have: [* digest],                   ; answers to a scoped have-query, not a full inventory
}

demand = {
  kind: "demand",
  consumer: party,
  stream: tstr,
  seq: uint,                            ; interest revision, separate from target revision
  target: digest,
  scope: digest,
  ? milestone: tstr,
}

plan = {
  kind: "plan",
  target: digest,
  contract: digest,
  scope: digest,
  snapshot: uint,                       ; receiver state this plan assumes
  nodes: [+ node],
  roots: [+ tstr],
  ? parent: digest,                     ; plan this one repairs, rewrites or fast-paths from
  ? fallbacks: {* tstr => [+ tstr]},    ; node id -> pre-authorized alternatives
}

node = {
  id: tstr,
  class: node-class,
  deps: [* tstr],
  ? op: name,
  ? runtime: digest,
  ? payload: digest,
  ? artifact: digest,                   ; referenced content
  ? base: digest,                       ; exact baseline output (delta, residual)
  ? params: bstr,                       ; canonical CBOR, opaque to the envelope
  ? emits: [+ tstr],                    ; regions of the output this node writes
  ? at: placement,
  ? checks: [* name],
  ? bounds: resources,
  ? claim: claim,                       ; planning estimate, never evidence
}

placement = "publisher" / "receiver" / party

claim = {
  ? "bytes": uint,
  ? cpu: ms,
  ? error: exact-num,
}

rewrite = {
  kind: "rewrite",
  from: digest,
  to: digest,
  repeater: party,
  delegation: digest,
  changed: [+ tstr],
  reused: [* digest],                   ; validated artifacts carried over with their evidence
  pending: [* tstr],                    ; nodes still awaiting execution or validation
}

; ---------- outcome plane ----------
evidence = {
  kind: "evidence",
  contract: digest,
  scope: digest,
  output: digest,
  ? work: digest,                       ; work key that produced the output; required for transfer
  predicate: name,
  pass: bool,
  ? reference: digest,                  ; designated reference, or the hop input under additive composition
  ? measured: exact-num,
  ? bound: exact-num,                   ; a declared bound (a runtime's delta), not a measurement
  ? units: tstr,
  validator: name,
  checker: party,
  at: uint,
}

attestation = {                         ; a repeater's statement about evidence it forwards
  kind: "attestation",
  evidence: digest,                     ; H(COSE_Sign1 bytes of the evidence); that evidence must be delivered too
  attester: party,
  delegation: digest,                   ; id(delegation) granting "attest"
  meaning: "signature-verified" / "recomputed",
  at: uint,
}

approval = {
  kind: "approval",
  binding: digest,                      ; H(binding COSE_Sign1 bytes) the consumer verified
  target: digest,
  contract: digest,
  scope: digest,
  plan: digest,
  output: digest,
  evidence: [+ digest],
  txn: tstr,
  expected-head: null / digest,
  authority: party / digest,
  ? relayed-by: [* digest],             ; delegations of the repeaters the inputs passed through
}

head = {                                ; a consumer's committed state for one object
  kind: "head",
  object: tstr,
  target: digest,
  contract: digest,
  scope: digest,
  output: digest,
}

receipt = {
  kind: "receipt",
  txn: tstr,
  approval: digest,
  prior-head: null / digest,
  head: null / digest,
  status: "committed" / "conflict" / "aborted",
}

repair = {
  kind: "repair",
  attempt: tstr,
  failed: tstr,
  reason: error-code,
  affected: [+ tstr],
  ? alternative: tstr / digest,
}

error-code = "unsupported-profile" / "unsupported-op" / "missing-dependency" /
             "baseline-mismatch" / "integrity-failure" / "permission-denied" /
             "resource-limit" / "validation-failure" / "stale-state" /
             "expired-authority" / "commit-conflict" / "canceled" / "repair-exhausted" /
             "ineligible-plan" / "invalid-contract"

; ---------- messages ----------
message = {
  kind: "message",
  v: 0,
  session: tstr,
  ? attempt: tstr,
  ? ttl: uint,                          ; hop-varying: remaining forwards
  ? via: [* party],                     ; hop-varying: path so far, for loop detection
  body: body,
}

; receivers send DEMAND; only the publisher or its delegate sends OFFER, so offers never collide
body = { type: "CAPABILITIES", caps: capabilities } /
       { type: "STATE", state: state } /
       { type: "DEMAND", demand: demand } /
       { type: "OFFER", binding: cose-sign1, target: target / digest,
         ? contract: contract / digest,             ; whole form
         ? template: contract-template / digest,    ; split form: inline only when not yet cached
         scope: scope / digest, plan: plan / digest } /
       { type: "ACCEPT", plan: digest } /
       { type: "REJECT", plan: digest, reason: error-code } /
       { type: "WORKTREE_PAYLOAD", plan: digest, chunks: [+ chunk] } /
       { type: "RESULT", stage: "materialized" / "validated" / "failed",
         ? output: digest, ? evidence: [* digest], ? missing: [* digest] } /
       { type: "REPAIR", repair: repair } /
       { type: "EVIDENCE", signed: [+ cose-sign1] } /        ; signed evidence, attestations, delegations
       { type: "SUPERSEDE", stream: tstr, old-seq: uint, new: demand } /
       { type: "CANCEL", stream: tstr, seq: uint } /
       { type: "VALIDATION_APPROVAL", signed: cose-sign1 } /
       { type: "COMMIT_RECEIPT", signed: cose-sign1 }

chunk = {
  node: tstr,
  digest: digest,
  data: bstr,
  ? offset: uint,
}
```

## Appendix B — Reproducing

In `kit/`, run `pip install -r requirements.txt && python3 run_checks.py`. Exit code 0 reproduces every number in sections 6, 8 and 10, including the contract-split sizes. Fixture keys derive from fixed labels (the publisher uses RFC 8032 test key 1), so digests and signatures match exactly. The C21 cases spawn worker processes and kill them with SIGKILL; they need a writable temp directory. `python3 mutation_check.py` reproduces the mutation table in section 8. `pip install -r bench/requirements.txt`, then `python3 bench/speed_model.py`, regenerates every modeled number in section 15 offline; `python3 bench/delta_bench.py` re-measures the deltas (it needs network access to the npm registry the first time).
