# ARFP v0.1 object-level check report

Schema fixtures valid: 42/42
Malformed objects rejected: 13/13
Semantic cases passing: 132/132

| Fixture | Valid | Bytes |
| --- | --- | --- |
| target | True | 101 |
| scope (full) | True | 66 |
| scope (milestone) | True | 86 |
| contract | True | 1648 |
| capabilities (workstation) | True | 759 |
| capabilities (phone) | True | 577 |
| state | True | 344 |
| demand | True | 134 |
| plan (workstation, 7 nodes) | True | 1167 |
| plan (phone, rewritten) | True | 1184 |
| delegation | True | 321 |
| rewrite | True | 243 |
| evidence | True | 355 |
| approval | True | 587 |
| receipt | True | 176 |
| head | True | 211 |
| repair | True | 121 |
| msg CAPABILITIES | True | 841 |
| msg STATE | True | 420 |
| msg DEMAND | True | 212 |
| msg OFFER | True | 3310 |
| msg OFFER (split, template inline) | True | 3325 |
| msg OFFER (split, template cached) | True | 1838 |
| msg ACCEPT | True | 112 |
| msg REJECT | True | 135 |
| msg WORKTREE_PAYLOAD | True | 848 |
| msg RESULT | True | 356 |
| msg REPAIR | True | 199 |
| msg SUPERSEDE | True | 233 |
| msg CANCEL | True | 88 |
| msg VALIDATION_APPROVAL | True | 771 |
| binding | True | 142 |
| contract-template | True | 1478 |
| binding (split form) | True | 326 |
| binding (split form, threshold override) | True | 359 |
| attestation | True | 173 |
| msg EVIDENCE | True | 1204 |
| msg COMMIT_RECEIPT | True | 354 |
| demand (receiver acceptance, subscription) | True | 206 |
| speculation | True | 282 |
| evidence (proof) | True | 439 |
| msg PUSH | True | 2622 |

| Malformed object | Result |
| --- | --- |
| Unknown node class "hologram" | rejected by the plan rule |
| Contract without a determinism declaration | rejected by the contract rule |
| T-class runtime with no divergence bound | rejected by the capabilities rule |
| Digest algorithm given as text | rejected by the evidence rule |
| OFFER with no plan | rejected by the message rule |
| Receipt status "probably-committed" | rejected by the receipt rule |
| Unknown message type "TELEPORT" | rejected by the message rule |
| Scope selecting an empty list | rejected by the scope rule |
| Threshold as a binary float (0.5) | refused by the encoder; rejected by the contract rule |
| Binding naming both a whole contract and a template | rejected by the binding rule |
| Split binding with expected digests as a list instead of a map | rejected by the binding rule (the arfp-object union accepted it) |
| Demand whose acceptance bounds are a list instead of a map | rejected by the demand rule (the arfp-object union accepted it) |
| PUSH with no base | rejected by the message rule |

| ID | Case | Expected | Observed | Pass |
| --- | --- | --- | --- | --- |
| C01 | Different eligible plans target the same exact output | same authenticated digest | delta plan, literal plan and phone plan all give sha256:7357a6a44563 for the exact parts | True |
| C02 | Two approximate outputs satisfy the same contract | both accepted, distinct output digests | workstation sha256:24a7cec15050 and phone sha256:09c4a2aea47a both accepted | True |
| C03 | Patch targets a receiver's approximate (T-class) baseline | reject baseline-mismatch | rejected baseline-mismatch: fairing-patch: base is T-class; contract allows ['E'] | True |
| C05 | Unknown required profile | reject unsupported-profile | rejected unsupported-profile: scene.assembly.v1 | True |
| C06 | Wrong decoder binding (runtime digest not held) | reject unsupported-op | rejected unsupported-op: fairing: runtime not available to this executor | True |
| C09 | Region checks pass but a global invariant fails | reject the full output | fairing bound 0.425 mm passes; clearance 1.829 mm on the decoded surface vs 2.1 mm on the reference: output rejected | True |
| C11 | Exact-only contract, fallback uses an approximate class | reject ineligible-plan | rejected ineligible-plan: fairing: the contract does not permit latent nodes | True |
| C12 | Accepted plan is rewritten by a repeater | identified replacement that is itself eligible | original phone plan: rejected unsupported-op: fairing: runtime not available to this executor; rewrite sha256:5fd3bad24de1 moves the decode to the repeater; rewritten plan eligible | True |
| C13 | Scoped result is accepted | cannot authorize full-target use | bay-A scope may 'sign-off': False | True |
| C14 | Milestone passes while full result is incomplete | only declared milestone uses | navigable milestone: navigate=True, measure=False | True |
| C15 | Receiver cancels a demand whose work another receiver needs | shared work stays live | geo-A has one work key in both plans: True; geo-A canceled: False | True |
| C16 | Replaceable view demand superseded (camera jump) | retire only the phone-only unfinished work | cancel set = ['lod-A', 'view(ph_old)'] | True |
| C17 | Planner marks a required-transition stream obsolete | reject; profile wins | rejected permission-denied: stream 'edits' is required-transition; supersession cannot erase it | True |
| C18 | Old canceled result arrives late | not committed as the new demand's result | rejected canceled: approval is for a superseded demand | True |
| C19 | Local head changed before commit | conflict; newer head untouched | status conflict; head still sha256:7148c1fb73cb | True |
| C20 | Commit acknowledgment lost, request retried | same durable outcome | retry returned byte-identical receipt: True | True |
| C22 | Cached artifact carries evidence for a different contract | evidence not reused | applies under rev-28 contract: True; under rev-29 contract: False | True |
| C23 | Repeater without execute right asked to transform | reject permission-denied | rejected permission-denied: fairing: key:edge-1 holds no execute right | True |
| C24 | Two child grants each copy the parent's full budget | reject resource-limit | rejected resource-limit: children allocate 40000 cpu of a parent budget of 20000 | True |
| C24b | Child grant adds a right the parent lacks | reject permission-denied | rejected permission-denied: child adds rights ['rewrite'] | True |
| C24c | Children that partition the budget and narrow the scope | accepted | accepted; 8 000 + 12 000 ms of a 20 000 ms parent | True |
| C25 | Two repeaters each pass 0.5 mm locally | end-to-end bound enforced | per-hop 0.3 + 0.3 mm each pass locally (naive accept: True); additive bound 0.6 mm rejects; true end-to-end 0.6 mm | True |
| C26 | Repeaters forward a request around a loop | bounded; no unbounded work | 3 forwards, then drop-duplicate | True |
| C28 | Canonical encoding across independent implementations | identical bytes; deviations detected | 42/42 fixtures byte-identical in both encoders; unsorted map canonical: False; non-shortest int canonical: False; num('0.50') == num('0.5'): True | True |
| C28b | Map mixing integer and text keys | orders differ; no ARFP map mixes key types | RFC 8949 and RFC 7049 orders agree on the mixed map: False; fixtures with uniform key types: 42/42 | True |
| C28c | Decimals 4([-2, 50]) (0.5) and 4([1, 1]) (10) | both rejected; all fixtures normalized | flagged: ['$.measured', '$.measured']; fixtures clean: 42/42 | True |
| R1 | Evidence moves by bound: sender eps + runtime divergence fits the threshold | accepted | 0.275 + 0.15 = 0.425 mm <= 0.5; true distance 0.271 mm (inside the bound) | True |
| R1b | Sender evidence measured on a different decode (other runtime) | reject validation-failure | rejected validation-failure: sender evidence was measured on different work; it cannot transfer | True |
| R2 | Non-reproducible (N) decoder on a reference-bound region at the receiver | reject ineligible-plan | rejected ineligible-plan: fairing: fairing.hausdorff.v1 cannot be checked at the receiver and N-class evidence does not transfer | True |
| R3 | Same N decoder placed at a checker repeater (placement converts determinism) | accepted | accepted; receiver gets checked, hash-verified bytes | True |
| R4 | T decoder whose bound uses a different metric (Chamfer vs Hausdorff) | reject ineligible-plan | rejected ineligible-plan: fairing: fairing.hausdorff.v1 cannot be checked at the receiver and T-class evidence does not transfer | True |
| R5 | Faster T decoder: eligible, but its bound does not fit | acceptance fails; repair | 0.318 + 0.25 = 0.568 mm > 0.5: repair | True |
| R6 | Repair by residual on the T-class decode | reject baseline-mismatch | rejected baseline-mismatch: fairing-fix: base is T-class; contract allows ['E'] | True |
| R7 | Repair by literal reference geometry | accepted | accepted; costs 1026 bytes vs 653 latent | True |
| R8 | Generated content in a region that is neither free nor reference-bound | reject ineligible-plan | rejected ineligible-plan: cables: N-class output in 'cable-run' is neither labeled free nor reference-bound | True |
| R8b | Generated content with no declared region, feeding the result | reject ineligible-plan | rejected ineligible-plan: cables: N-class output reaches the result without a declared region | True |
| R9 | Contract marks a reference-bound region as free | reject invalid-contract | rejected invalid-contract: fairing.hausdorff.v1: a free region cannot also be reference-bound | True |
| R10 | Fast path: same plan shape, current snapshot | executes without waiting for ACCEPT | accepted | True |
| R11 | Fast path replayed after the receiver moved on | reject stale-state before execution | rejected stale-state: fast-path plan assumes snapshot 42; receiver is at 43 | True |
| R12 | Fast path with a changed plan shape | reject; full negotiation required | rejected ineligible-plan: plan shape changed; full OFFER/ACCEPT required | True |
| R13 | Fast path on a required-transition stream | reject | rejected ineligible-plan: stream edits has no fast path; full OFFER/ACCEPT required | True |
| G1 | Valid publisher binding, checked before planning | accepted; matches the published vector | trace ['binding', 'eligibility']; envelope matches section 9 vector: True | True |
| G2 | Binding signed by a key not on the allow-list | reject permission-denied | rejected permission-denied: signing key is not on the allow-list | True |
| G3 | Binding signature with one bit flipped | reject integrity-failure | rejected integrity-failure: signature does not verify | True |
| G4 | Offer carries a different contract than the one signed | reject integrity-failure | rejected integrity-failure: binding names a different contract | True |
| G5 | Offer carries a different target revision than the one signed | reject integrity-failure | rejected integrity-failure: binding names a different target | True |
| G6 | Publisher's valid signature on a delegation, presented as the binding | reject integrity-failure | rejected integrity-failure: signed payload is a delegation, not a binding | True |
| G7 | Allow-listed repeater key signs a binding in the publisher's name | reject permission-denied | rejected permission-denied: binding names a publisher other than its signer | True |
| G8 | Expired binding | reject expired-authority | rejected expired-authority: binding has expired | True |
| G9 | Forged binding and an ineligible plan together | binding error first; planning never runs | rejected integrity-failure: signature does not verify; eligibility calls: 0 | True |
| G10 | Offer with no binding | reject permission-denied | rejected permission-denied: offer carries no signed binding | True |
| C04a | Dependency evicted after ACCEPT, no fallback | abort; no approval, receipt or head change | status aborted (missing-dependency); RESULT missing ['sha256:34b5b2732b11']; journal {'genesis': 1}; head unchanged: True; staged files: 0 | True |
| C04b | Dependency evicted, prebound literal fallback | REPAIR names the cone; commit equals control | REPAIR failed=base affected=['base', 'root', 'upd'] alt=base-lit; receipt committed; output equals no-fault control: True | True |
| C04c | New offer after the aborted attempt, re-supplying the artifact | processed and committed | receipt committed | True |
| C04d | Audit trail of the aborted attempt | accept bound to the binding, then the abort | events: ['accept', 'abort'] | True |
| C07a | Procedural generator diverges, no fallback | rejected at emission; dependent never runs | status aborted; executed ['gen']; audit names node gen, runtime sha256:52167141903c, observed sha256:0566964aa92b | True |
| C07b | Generator diverges, prebound literal fallback | repaired and committed | repairs ['gen']; receipt committed | True |
| C08a | Residual on the exact R1 base misses its bound | no approval; R1 stays the head | status aborted (validation-failure); head still R1: True; journal {'genesis': 1} | True |
| C08b | Well-formed residual against the same baseline | accepted; the baseline isn't blacklisted | receipt committed | True |
| C10a | Branch c fails late; a is independent; cross-branch x reads a and b | cone excludes a; a's evidence reused; x re-run on the new b | REPAIR failed=c affected=['b', 'c', 'root']; evaluations p-a=1 x-len=2 p-b=2; final x covers new b: True; receipt committed | True |
| C10b | Cross-branch x passed on the divergent b before repair | stale x evidence not reused | first x pass=True on the divergent b: True; final x on the repaired b: True | True |
| C10c | Repair cannot restore the cone | abort; a's staged output never committed | status aborted; journal {'genesis': 1}; head unchanged True | True |
| C21-A | Killed after the approval is journaled, before the head swap | recovery applies the swap; receipt identical to an uncrashed run | killed by SIGKILL; recovery [('resolved-pending-approval', 'tx-c21-990')]; head is rev 3: True; receipt committed, byte-identical to control: True; journal {'genesis': 1, 'approval': 1, 'head': 1, 'receipt': 1} | True |
| C21-C | Retry with the same transaction after recovery | same receipt; no new journal entries | byte-identical: True; journal before {'genesis': 1, 'approval': 1, 'head': 1, 'receipt': 1} after {'genesis': 1, 'approval': 1, 'head': 1, 'receipt': 1} | True |
| C21-E | Offer arriving while the receiver is recovering | refused until recovery ends; then stale | state recovering: stale-state; after recovery, a plan built on snapshot 0: rejected stale-state: plan assumes snapshot 0; receiver is at 1 | True |
| C21-T | Killed halfway through writing the head record | torn tail dropped; same outcome as C21-A | killed by SIGKILL; recovery ['truncated-torn-tail', ('resolved-pending-approval', 'tx-c21-990')]; receipt byte-identical: True | True |
| C21-H | Killed after the head swap, before the receipt is durable | receipt rebuilt from the journal | killed by SIGKILL; recovery [('receipt-from-commit', 'tx-c21-990')]; byte-identical: True | True |
| C21-R | Killed after the receipt is durable | nothing to redo; retry returns the stored receipt | killed by SIGKILL; recovery actions []; retry byte-identical: True | True |
| C21-B | Another commit moved the head before recovery | conflict; moved head untouched; output kept | receipt conflict, head None, prior-head is the moved head: True; head still concurrent: True; staged output kept: True | True |
| C21-D | Staged output corrupted while the receiver was down | aborted; never commit other bytes | receipt aborted; head unchanged: True | True |
| C21-I | Invariants across all seven journals | every head swap follows a durable approval; one receipt per txn | 7/7 journals clean | True |
| C27a | Repeater forwards the origin's signed evidence unchanged | commit; receipt chain rebuilds from the receipt alone | receipt committed; audit triple ['sha256:dc7c2d06f848', 'sha256:b29449620ad1', 'sha256:2928b6ea8cc0']; chain rebuilt from the receipt: 3 links, relay delegation verified; approval cites exactly the audited evidence | True |
| C27b | Repeater adds a signed attestation naming the origin evidence | commit; receipt chain rebuilds from the receipt alone | receipt committed; audit triple ['sha256:dc7c2d06f848', 'sha256:b29449620ad1', 'sha256:32fd123d34a0']; chain rebuilt from the receipt: 4 links, relay delegation verified; approval cites exactly the audited evidence | True |
| C27c | Repeater re-signs the evidence as its own, origin copy dropped | reject validation-failure; no receipt | rejected validation-failure: evidence for p1 is signed by key:repeater-2, who is not an accepted checker | True |
| C27d | Repeater edits the evidence and keeps the origin signature | reject integrity-failure; no receipt | rejected integrity-failure: signature does not verify | True |
| C27e | Attestation names origin evidence that was not delivered | reject validation-failure; no receipt | rejected validation-failure: attestation names evidence that was not delivered | True |
| C27f | Required predicate's evidence dropped entirely | reject validation-failure; no receipt | rejected validation-failure: no evidence for required predicate p1 | True |
| C27g | Repeater attests without the attest right | reject permission-denied; no receipt | rejected permission-denied: key:repeater-2 holds no attest right | True |
| C27h | Repeater substitutes the payload bytes | reject validation-failure; no receipt | rejected validation-failure: evidence was measured on different bytes or another contract | True |
| C27i | Repeater rewrites the plan without the rewrite right | reject permission-denied; no receipt | rejected permission-denied: key:repeater-2 holds no rewrite right | True |
| C27j | Forged origin binding, valid repeater signatures | reject integrity-failure; no receipt | rejected integrity-failure: signature does not verify | True |
| T1 | First offer of a session carries the template inline | accepted; template cached; plan bound to the materialized contract | trace ['binding', 'eligibility']; cached ['sha256:0d75d2d04ed3']; materialized id equals the whole contract's: True | True |
| T2 | Next revision names the cached template; the offer omits it | accepted; smaller than the same offer with the whole contract | trace ['binding', 'eligibility']; offer 998 B vs 1505 B with the whole contract inline | True |
| T3 | Template neither cached nor offered | reject missing-dependency; planning never runs | rejected missing-dependency: template sha256:0d75d2d04ed3 is neither cached nor offered; trace ['binding']; eligibility calls 0 | True |
| T4 | Inline template differs from the one the binding names | reject integrity-failure | rejected integrity-failure: offered template is not the one the binding names | True |
| T5 | An amended template in the cache never applies to bindings that name the original | missing-dependency, or the original rules | amended id differs: True; with only the amended one cached: rejected missing-dependency: template sha256:0d75d2d04ed3 is neither cached nor offered; with both cached the binding resolves to the original rules (repairs=1) | True |
| T14 | Offer names a template digest that disagrees with the binding | reject integrity-failure | rejected integrity-failure: offer names a different template than the binding | True |
| T6 | Binding sets a value for a predicate the template lacks | reject invalid-contract | rejected invalid-contract: binding sets expected for p-ghost, which the template lacks | True |
| T7 | Digest-match predicate left without an expected digest | reject invalid-contract | rejected invalid-contract: p-doc: no expected digest in the template or the binding | True |
| T13 | Publisher signs a binding for a template whose authority names someone else | reject permission-denied | rejected permission-denied: signer is not the template's publisher | True |
| T8 | Evidence from revision 1 offered for revision 2 under the same template | not reused; the template digest alone could not tell the revisions apart | applies under rev 2: False; contract ids differ: True; template ids equal: True | True |
| T9 | Threshold override in one revision's binding | that revision fails; the others keep the default | rev 2 (default): validated; rev 3 (override 81): aborted (validation-failure) | True |
| T10 | Forged split binding and an ineligible plan together | binding error first; planning never runs | rejected integrity-failure: signature does not verify; eligibility calls 0 | True |
| T11 | Split-form update commits; the receipt alone rebuilds binding, template and evidence | committed; the chain names the template | receipt committed; chain ['sha256:28d720e6ffa5', 'sha256:0d75d2d04ed3', 'sha256:058119b581ec']; template in chain: True | True |
| T12 | Template plus binding reproduce the whole assembly contract | identical object and id | identical: True; same id: True; moved to the binding: 2 expected digests, 1 reference | True |
| F1 | Receiver accepts bounded output within the contract's bound | the latent fairing plan is eligible | accepted; declared error 0.35 mm fits the contract's 0.5 mm | True |
| F2 | Receiver requires the exact reference geometry (bound 0) | latent plan rejected for it; exact plan chosen | rejected ineligible-plan: fairing: declared error 0.35 mm exceeds the bound for this receiver, 0; the literal reference plan is eligible instead (1,026 B vs 653 B latent) | True |
| F3 | Demand tries to loosen the contract's bound (0.6 mm vs 0.5 mm) | reject permission-denied | rejected permission-denied: fairing.hausdorff.v1: a demand may tighten the contract's bound, not loosen it | True |
| F4 | Receiver tightens the bound to 0.4 mm | eligible, then fails validation for it only | plan eligible; composed bound 0.425 mm passes the contract's 0.5 for others; rejected validation-failure: fairing.hausdorff.v1: 0.425 exceeds this receiver's bound 0.4 | True |
| F5 | Receiver refuses generated content even where the contract allows it | reject ineligible-plan | rejected ineligible-plan: skin: generated content in ['skin-texture']; this receiver accepts none | True |
| F6 | Receiver accepts only reproducible (E) copies | local T decode rejected; upstream decode accepted | local decode rejected ineligible-plan: fairing: T-class copy; this receiver accepts ['E']; the same decode run at the repeater arrives as exact bytes and is eligible (classes set reproducibility; bounds set fidelity, F2 and F4) | True |
| F7 | Demand sets 1 mm on the 2 mm clearance minimum (smaller would loosen a minimum) | reject permission-denied (only metric bounds can be tightened) | rejected permission-denied: clearance.min.v1 is not a metric bound in this contract; a receiver can tighten only metric bounds | True |
| F8 | Latent plan that declares no error, for a receiver with its own bound | reject ineligible-plan | rejected ineligible-plan: fairing: declares no error for fairing.hausdorff.v1; this receiver requires 0.45 mm | True |
| P1 | Draft on the coarse state, checked once the exact state arrives | commits; identical output | kept 9 of 48 drafted tokens, exact token at the first mismatch, rest decoded exactly; committed as E; output identical to decoding on the exact state: True | True |
| P2 | Provisional output committed with no check by a receiver that did not opt in (coarse bound in range) | reject validation-failure | rejected validation-failure: output drafted on provisional state needs a check against the exact state before commit | True |
| P3 | Speculation record checked against a different exact state | reject integrity-failure | rejected integrity-failure: draft was checked against a different exact state | True |
| P4 | Speculation record claims more verified tokens than the check keeps | reject validation-failure | rejected validation-failure: record claims 14 verified tokens; checking against the exact state keeps 9 | True |
| P5 | Receiver that opts in uses the provisional draft, within a declared bound | commits, labeled T | accepted; coarse layer declares 0.3 mm within 0.5 mm; committed as class T without waiting | True |
| P6 | Receiver opts in, but the coarse layer declares no bound within the contract | reject validation-failure (a receiver cannot loosen the contract) | rejected validation-failure: the provisional layer declares no bound within the contract; it cannot be used unchecked | True |
| P7 | Receiver opts in, bound in range, but the contract accepts no T-class evidence | reject validation-failure | rejected validation-failure: the contract does not accept bounded (T-class) output by bound | True |
| P8 | Speculation record that misnames the plan, provisional state or draft, or a committed output it does not verify | each rejected | [1] another plan: rejected integrity-failure: speculation record is for a different plan [2] another provisional state: rejected integrity-failure: speculation record names a different provisional state [3] another draft: rejected integrity-failure: speculation record names a different draft [4] committed output differs from the verified one: rejected validation-failure: committed output is not the verified output | True |
| V1 | Untrusted worker's output with a valid proof | accepted with one recomputation pass | accepted after 1 recomputation pass with hardware noise; proof 55 B; the worker's generation was not repeated | True |
| V2 | Worker ran a different model but claims the contracted one | reject validation-failure | rejected validation-failure: proof does not match one recomputation of the claimed run | True |
| V3 | Proof made for a different input | reject validation-failure before any recomputation | rejected validation-failure: proof is for a different input; recomputation passes spent: 0 | True |
| V4 | Contract does not accept proof evidence | reject validation-failure | rejected validation-failure: the contract does not accept proof evidence | True |
| V5 | Proof bytes edited after signing | reject integrity-failure | rejected integrity-failure: signature does not verify | True |
| V6 | Proof states a runtime other than the one the plan names | reject validation-failure before any recomputation | rejected validation-failure: proof was made with a different runtime than the plan names; recomputation passes spent: 0 | True |
| V7 | Proof evidence older than the contract's max-age | reject validation-failure before any recomputation | rejected validation-failure: evidence is for another contract, scope or output, or is too old; recomputation passes spent: 0 | True |
| V8 | Proof evidence that names another checker, reports a failed check, or uses an unsupported scheme | each rejected before any recomputation | [1] checker is not the signer: rejected integrity-failure: evidence names a checker other than its signer; recomputation passes spent: 0 [2] reports a failed check: rejected validation-failure: evidence reports a failed check; recomputation passes spent: 0 [3] unsupported scheme: rejected validation-failure: no proof in a supported scheme; recomputation passes spent: 0 | True |
| U1 | Revision 29 pushed on a standing subscription | applied without OFFER/ACCEPT | applied: the revision's binding passed gate zero against the cached template, the plan is a same-shape child of the subscribed plan, and the pushed bytes match it | True |
| U2 | Push assumes a base the receiver does not hold | reject baseline-mismatch (receiver sends REPAIR) | rejected baseline-mismatch: push assumes a base this receiver does not hold; send REPAIR | True |
| U3 | Push to a receiver with no subscription | reject permission-denied | rejected permission-denied: no standing subscription for this stream; negotiate with OFFER/ACCEPT | True |
| U4 | Push carries a binding with a forged signature | reject integrity-failure (gate zero) | rejected integrity-failure: signature does not verify | True |
| U5 | Push on the required-transition stream, which the contract gives no fast path | reject ineligible-plan | rejected ineligible-plan: stream edits has no fast path; full OFFER/ACCEPT required | True |
| U6 | Push whose plan changes shape | reject ineligible-plan (full OFFER/ACCEPT required) | rejected ineligible-plan: plan shape changed; full OFFER/ACCEPT required | True |
| U7 | Older push arrives after a newer one on a replaceable stream | reject canceled (superseded) | rejected canceled: push seq 4 is superseded; latest applied is 5 | True |
| U8 | Pushed bytes do not match the digest they carry | reject integrity-failure | rejected integrity-failure: pushed bytes for fairing do not match the plan | True |
| U9 | Push binding names a different target than the one pushed | reject integrity-failure (gate zero) | rejected integrity-failure: binding names a different target | True |
| U10 | Gap on a required-transition stream whose contract grants a fast path | reject missing-dependency | rejected missing-dependency: push seq 9 on a required-transition stream; expected 8 | True |
| U11 | Pushed bytes match the digest they carry, but not the plan's payload | reject integrity-failure | rejected integrity-failure: pushed bytes for fairing do not match the plan | True |
| U12 | Push that the subscriber's own acceptance rules out | each rejected ineligible-plan, as F6 and F2 are | [1] subscriber accepts only E copies; the plan decodes a latent locally (T): rejected ineligible-plan: fairing: T-class copy; this receiver accepts ['E'] [2] subscriber's own bound is 0.3 mm; the plan declares 0.35 mm: rejected ineligible-plan: fairing: declared error 0.35 mm exceeds the bound for this receiver, 0.3 | True |
| U13 | Push that does not match the subscription's contract | each rejected | [1] binding under a template outside the subscription: rejected integrity-failure: push binding names a template outside this subscription [2] plan bound to the previous revision's contract: rejected ineligible-plan: plan is bound to a different contract [3] stream the revision's contract does not define: rejected ineligible-plan: this revision's contract defines no stream pose | True |
