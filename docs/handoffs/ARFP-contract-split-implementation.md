# ARFP contract split: implementation notes

**Date:** 2026-10-11
**Implements:** [ARFP-contract-split-handoff.md](ARFP-contract-split-handoff.md)
**Status:** built and tested in the schema kit:
- 14 cases, T1–T14 in `kit/contract_split.py`.
- 38/38 fixtures valid, 11/11 malformed objects rejected, 95/95 cases pass.
- 7/7 guard removals caught by `kit/mutation_check.py`.

Object-level only: no transport.

## What the handoff asked for, and what happened

| Handoff step | Result |
|---|---|
| 1. Add the two types to `arfp-v0.1.cddl`; keep G1 passing byte for byte | `contract-template` added. `binding` became a choice between the whole form (`contract`) and the split form (`template` + per-revision values). The whole form is unchanged, so G1 still matches the published vector byte for byte; nothing needed regenerating. |
| 2. Update the OFFER fixture and gate zero to accept a template digest | OFFER now takes an optional `template` (inline object or digest). Gate zero accepts the template inline, by digest, or from the receiver's cache (`arfpkit/gate.py`: `check_binding_any`, `handle_offer_any`). |
| 3. Measure the new OFFER against the 3,310-byte baseline | First use 3,325 B (template inline). Template cached: 1,838 B, a 44% cut. Plan also by id: 707 B. Template 1,478 B, once per session. |
| 4. Confirm a second independent encoder produces identical bytes | cbor2 matches the kit's encoder on all 38 fixtures, including both split bindings and both split OFFERs (case C28). cbor2 is a library, so this is a cross-check, not an independent implementation of the spec. |

## Changes from the handoff, and why

1. **Per-revision references.** The handoff's binding carried `expected` digests and `params`. Metric predicates also name a designated reference that changes with each revision (the assembly's fairing reference geometry, for one). The binding therefore also has `references: {predicate id => digest}`.

2. **The contract identity is the materialized contract's id, not the template digest.** The handoff said receipts and approvals should name the template digest as the contract identity. That drops the target and the per-revision values from the identity:
   - Two revisions under one template would share it, and evidence measured for one would match the next. Case T8 shows the template ids are equal across revisions while the contract ids differ.
   - Instead, sender and receiver both compute `materialize(template, binding)`, and the contract id is its ordinary id.
   - For the assembly fixture this reproduces the whole contract exactly, same object and same id (T12). Plans, evidence, approvals, heads and receipts are therefore the same objects in either form.
   - Approvals still name the binding hash, so the audit trail pins the template too (T11 rebuilds binding → template → evidence from the receipt).

3. **No separate template signature.** Every publisher-signed binding covers the template's digest, which already authenticates the template. A second signature would add bytes and no authentication. A receiver caches a template only after a binding that names it has verified.

4. **Both forms stay valid.** The whole-contract binding (v0.1 form) still works, so existing vectors and cases are unchanged. The schema makes the forms exclusive: a binding naming both a contract and a template is rejected.

5. **Override rules are explicit.** A binding override is rejected as `invalid-contract` if it:
   - names a predicate the template lacks (T6);
   - sets `params` for a predicate without a template threshold;
   - leaves a digest-match or feature-digest predicate without an expected digest (T7);
   - leaves a reference-metric predicate without a reference.

   The materialized contract then goes through the same lint as any contract.

## Gate zero for a split binding (as implemented)

1. The key id is on the allow-list.
2. The signature verifies.
3. The payload kind is `binding`.
4. The signer is the binding's publisher and the target's publisher.
5. The binding names id(target).
6. The template is the one the binding names: inline (digest must match, T4), by digest (must agree with the binding, T14), or cached. If neither is available, `missing-dependency` (T3). The kit defines no message for requesting a template; in a live session, fetching it would cost a round trip.
7. The signer is the template's `authority.publisher` (T13).
8. The binding has not expired.
9. The overrides are valid (T6, T7). Eligibility runs only after all of this (T10).

## Schema

See `kit/arfp-v0.1.cddl`: `contract-template`, the `binding` group choice, and the OFFER `contract` / `template` fields.

The validator in use (pycddl 0.6.4) accepted a malformed split binding through the top-level `arfp-object` union, even though the `binding` rule rejects it. The kit therefore now validates every object against its own rule as well as the union, and keeps that object as a negative case.

## Still open

- **Session-scoped delegations.** Delegations still name a per-revision contract id, so a repeater needs a fresh delegation per revision. A delegation naming the template would survive revisions; it needs its own scope and expiry rules.
- **Override direction.** Overrides may loosen as well as tighten a threshold. That is the publisher's signed decision and is recorded in the binding hash, but a profile may want to forbid loosening.
- **Template lifetime.** There is no revocation or expiry on the template itself; old bindings remain valid until they expire.
