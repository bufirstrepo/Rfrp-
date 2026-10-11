# ARFP Contract Split — Handoff Note

**Date:** 2026-10-11  
**Purpose:** Factor the immutable Contract so a new target revision does not force a full contract object onto the wire.  
**Status:** Design proposal; not yet in the schema kit or checked.

---

## Problem

In v0.1 a `contract` names one specific `target` (by digest). The publisher-signed `binding` binds that exact pair. An `OFFER` therefore carries the binding plus the target and contract (or their digests). When the receiver does not already hold the contract, the OFFER inlines both.

Measured result (from the 2026-10-11 analysis): a single-revision OFFER reaches **3,310 bytes**. That is the dominant term in the 3,421-byte end-to-end control cost. Every new revision pays it again.

The architecture handoff already requires that a Contract, once bound, is immutable and that amendment creates a new identity. The split preserves that rule while removing the repeated transmission of the unchanging rules.

---

## Solution

Two objects:

1. **Session contract template** — signed once, long-lived, cached by digest. Holds every rule that does not change with a revision.
2. **Per-revision binding** — small, signed per update. Names the template digest, the new target id, and any revision-specific expected digests or parameters.

Gate zero, eligibility, evidence, receipts, and compare-and-swap commits stay the same. Only the wire representation of the unchanging rules changes.

---

## CDDL

```cddl
; ---------- session contract template (signed once, long-lived) ----------
; Holds every rule that does not change with a target revision.
; Amendment of any field creates a new template identity.

contract-template = {
  kind: "contract-template",
  profile: name,
  classes: node-classes,
  acceptance: [+ predicate],
  ? invariants: [+ predicate],
  ? free: [+ tstr],                     ; regions where generation is allowed and must be labeled
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

; ---------- per-revision binding (small, signed per update) ----------
; Names the cached template and the revision-specific facts.
; Gate zero verifies this before any planning.

binding = {
  kind: "binding",
  template: digest,                     ; id(contract-template)
  target: digest,                       ; id(target) for this revision
  publisher: party,                     ; must equal template.authority.publisher and target.publisher
  issued: uint,                         ; epoch ms
  ? expires: uint,                      ; epoch ms
  ? expected: {* name => digest},       ; revision-specific expected digests (predicate id -> digest)
  ? params: {* name => exact-num},      ; revision-specific predicate parameters that override template defaults
}

; ---------- OFFER change ----------
; Full template is sent only when not already cached.

body = { type: "OFFER",
         binding: cose-sign1,           ; payload = canonical CBOR of `binding`
         ? template: contract-template / digest,  ; inline only on first use or template change
         target: target / digest,
         scope: scope / digest,
         plan: plan / digest } /
       ; ... remaining message types unchanged
```

---

## Normative usage rules

- Receiver caches `contract-template` by digest. Subsequent OFFERs omit the inline template when the binding’s `template` digest is already held.
- Gate zero order is unchanged: allow-list → signature → payload `kind` == `"binding"` → signer is the publisher → binding.target matches the offered target → binding.template matches a held template (or the inline one) → not expired.
- Eligibility and evidence checks run against the template’s rules. Any `expected` or `params` from the binding apply as overrides for that revision only.
- A change to any template field produces a new template digest. Old bindings that name the previous digest remain valid until they expire.
- Receipts and approvals name the template digest as the Contract identity, so the full rule set remains bound into the audit trail.
- A template change is a new signed template; it is not a silent amendment of an existing one.

---

## What does not change

- Determinism classes (E/T/N), evidence transfer rules, free-region labeling, and cone repair.
- Compare-and-swap commits on the head.
- Delegation narrowing and budget partitioning.
- Multi-hop provenance (signed evidence, attestations that add rather than replace).
- The requirement that a Plan is admissible only when it satisfies the bound rules.

---

## Next concrete steps

1. Add the two types to `arfp-v0.1.cddl` and regenerate the binding vector in the kit so G1 still passes byte-for-byte.
2. Update the OFFER fixture and the gate-zero checks to accept a template digest.
3. Measure the new OFFER size against the existing 3,310-byte baseline.
4. Confirm that a second independent encoder still produces identical bytes for the reduced binding.

---

## References

- ARFP working analysis (2026-10-11), section 6 (measured 3,310-byte OFFER) and section 11 (open item: split the contract).
- Architecture handoff: Contract is bound before Plan acceptance; amendment creates a new identity.
- Existing schema kit: `binding` and `OFFER` definitions in `arfp-v0.1.cddl`.
