# Standards reuse and receipt semantics

**Status:** integration research note, checked against the primary sources below on 2026-10-11, and updated the same day for what the [schema kit](../kit/README.md) adopted. This note does not silently change either imported specification.

The supplied review recommends reusing existing serialization, signing, and receipt mechanisms. The experiment already chooses JCS for a restricted JSON profile. The schema kit chose deterministic CBOR and COSE for the broad object model. A future fabric should make its remaining choices explicitly instead of treating every cryptographic structure as a new protocol invention.

| Need | Existing specification | Current ARFP treatment |
|---|---|---|
| Deterministic JSON bytes | [RFC 8785 — JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) | Already selected by `arf-experiment/0.1` with printable-ASCII strings and safe integers. Independent vectors must still verify parser restrictions, ordering, serialization, and digest scope. RFC 8785 is an Informational RFC. |
| Deterministic binary encoding | [RFC 8949 — CBOR, Section 4.2](https://www.rfc-editor.org/rfc/rfc8949.html#section-4.2) | **Adopted by the schema kit**: core deterministic encoding (§4.2.1), no binary floats, exact decimals as tag 4 in normalized form, text keys in every ARFP map so the RFC 8949 and RFC 7049 orders agree. A library (cbor2) reproduces all 42 vectors; that is a cross-check, not an independent implementation. Not accepted by the `arf-experiment/0.1` wire; choosing one encoding for the next profile is open. |
| Signature envelopes | [RFC 9052 — COSE: Structures and Process](https://www.rfc-editor.org/rfc/rfc9052.html) | **Adopted by the schema kit**: COSE_Sign1 (tag 18) with the object as embedded payload, EdDSA/Ed25519 (alg −8, [RFC 9053](https://www.rfc-editor.org/rfc/rfc9053.html)), key id in the protected header. Bindings, delegations, evidence, attestations, approvals and receipts are signed; the payload's `kind` types the signature. Key policy is a static allow-list with no rotation or revocation yet. |
| Signed statements and transparency | [RFC 9943 — SCITT Architecture](https://www.rfc-editor.org/rfc/rfc9943.html) | Candidate integration for auditable statements. Published June 2026; this updates the review's general reference to SCITT work. Not adopted by the kit: its signed approvals and receipts are local records, not transparency receipts. No SCITT implementation or conformance is claimed here. |
| Schema language | [RFC 8610 — CDDL](https://www.rfc-editor.org/rfc/rfc8610.html) | Used by the schema kit (`kit/arfp-v0.1.cddl`). Checked with one tool (pycddl 0.6.4), whose deviations are listed in the kit README; a second CDDL tool is still needed. |
| Hash algorithm identifiers | [RFC 9054 — COSE hash algorithms](https://www.rfc-editor.org/rfc/rfc9054.html) | Used by the schema kit: a digest is `[alg, value]` with COSE algorithm ids (−16 = SHA-256), allowing algorithm agility without string parsing. |
| Delta against what the receiver holds | [RFC 9842 — Compression Dictionary Transport](https://www.rfc-editor.org/rfc/rfc9842.html) | Not part of ARFP, but the baseline it must match: the client names its dictionary on the ordinary request, so a delta costs no extra round trip. The [speed review](analysis/ARFP-internet-speed-review.md) uses it as the comparison for every delta workload. |

The SCITT architecture defines signed and transparent statements using COSE and transparency services. Its receipt semantics concern registration in a verifiable data structure. Those semantics do not make the underlying reconstruction or fidelity claim true. See RFC 9943 Sections 3 and 9.2. ARFP would still need its domain evidence and a local transaction record with explicit meanings.

## Keep three records distinct

In the schema kit, content identity is an object id or artifact digest, the validation statement is a signed `evidence` object, and the commit outcome is a signed `receipt`. The `approval` a consumer records before committing names the binding, contract, plan, output and evidence it relied on.

| Record | The question it answers | What it does not establish by itself |
|---|---|---|
| Content identity | Which exact artifact or canonical output is this? | Whether it meets the Contract |
| Validation statement | Which checker evaluated which concrete output against which predicates/reference, and with what result? | That the current receiver committed it durably |
| Commit outcome | Which local transaction installed which accepted output under which authority? | That the authoritative publisher changed, or that another receiver installed it |

A transparency receipt may accompany a validation or commit statement. The terms must not be collapsed: registration evidence is not geometric evidence, and it is not a local storage transaction.

## Before adopting a fabric signing or receipt profile

1. Specify each canonical payload and the identities it binds: Target, Contract, Plan, realized output, scope, reference, checker, and authority as applicable.
2. Specify signature boundaries and exclude self-referential hashes. Decide how an existing encoded payload is carried without accidental reserialization.
3. Specify issuer authorization, key identification, algorithm choices, expiration/replay policy, and evidence applicability.
4. Define whether transparency is required, optional, or absent for the application profile; count its latency and bytes where used.
5. Produce cross-implementation positive and negative vectors before claiming interoperability.

These are proposed integration steps derived from the architecture and the listed specifications, not requirements copied wholesale from those standards. Existing HTTP, dictionary, delta, content-addressed graph, build-cache, and named-computation comparisons remain documented in the originals. None of these references establishes ARFP novelty or measured advantage.
