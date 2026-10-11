# Adaptive Reconstruction Protocol — Experimental Draft v0.1

Date: 11 October 2026  
Working identifier: `arf-experiment/0.1`  
Status: proposed design and checked illustrative transcript. Not an IETF Internet-Draft, approved standard, production implementation, or measured performance result. No protocol name or identifier in this document has been registered.

## 1. Objective and scope

Make the required portion of a large shared workspace usable sooner by negotiating how a receiver will reconstruct it from locally available state and newly delivered information. A sender can select among compatible representations, but acceptance depends on the agreed output contract.

The broader design accommodates learned latents, procedural operations, asset references, baseline deltas, residuals, and local tasks. This first profile specifies a versioned assembly component with an exact authoritative record and a display mesh checked against a geometric tolerance. A designated publisher owns revisions; one receiver installs them locally. An agent can select plans, but protocol correctness does not depend on an LLM agreeing with another LLM.

The base profile defines conventional field updates and asset references so that the acceptance mechanism has an executable meaning. Neural representations require an extension that specifies the actual decoder, bitstream, numerical requirements, dependencies, and test vectors. This document does not invent a universal neural decoder or claim an AI performance gain.

### 1.1 What “terabyte-scale” means

Report these quantities separately:

| Quantity | Definition |
|---|---|
| Backing dataset | Unique source assets in the named dataset snapshot, in bytes |
| Required working set | Objects and fidelity required by the current task |
| Newly transferred bytes | Traffic attributable to the task across every dependency, registry, control, update, repair, and offload connection |
| Newly materialized output | New canonical output actually reconstructed; do not count cached bytes again |
| Readiness time | Time from an explicit task/update request until the required output passes its acceptance conditions |
| Complete replication time | Time until every requested byte/object is present and accepted, if full replication is requested |

A large backing dataset can be interactively useful before full replication. That is a working-set result. A claim about reconstructing an entire dataset requires verification of the entire target state.

Illustrative arithmetic using decimal units, without protocol overhead or processing: 1 TB needs 800 seconds on a 10 Gbit/s link, or 13 minutes 20 seconds. If a particular task actually requires 100 MB of additional transfer, its serialization time on that link is 0.08 seconds. The latter does not demonstrate that 1 TB was transferred in 0.08 seconds. Cold setup, prior distribution, receiver work, and every other connection still count.

### 1.2 Existing work and the proposed contribution

HTTP delta encoding already describes transferring changes relative to cached instances [1]. HTTP Compression Dictionary Transport already defines dictionary distribution and availability negotiation [2]. Learned compression and structured scene composition also exist [6,7]. These are foundations and comparison points.

The proposed research question is whether one interoperable agreement can select among heterogeneous reconstruction methods under dependency, device, fidelity, and authority constraints and outperform strong existing delivery methods. Novelty and advantage are not established by this draft.

## 2. Actors and authority

- **Publisher:** the configured, authenticated authority for an object stream. It chooses target revisions and their expected state digests.
- **Receiver:** maintains a verified local head and may accept or reject a proposed plan.
- **Selector:** sender, receiver, or coordinator software that proposes a representation. Its estimates are advisory. It cannot override the receiver's limits or fidelity requirement.
- **Connector:** maps an application's source data into the object schema. It preserves revision, units, identity, and provenance; provenance alone does not prove physical correctness.

The secure session must bind the publisher's authenticated identity to the locally configured object authorization. A payload field named `publisher_id` is not proof of authority. Provision the initial publisher and baseline through a trusted deployment process. Publisher rotation, multi-writer agreement, cross-object transactions, and disconnected conflict merging are out of scope for v0.1.

The publisher's target is authoritative independently of receiver readiness. A successful `RESULT` means this receiver installed the target; it is not global consensus or permission to change the publisher's state.

## 3. Object and fidelity profiles

### 3.1 Exact component state: `component-state-v1`

Required fields, with no extra fields in this profile:

| Field | Type and rule |
|---|---|
| `schema` | Literal `component-state-v1` |
| `object_id` | Nonempty printable-ASCII identifier; scoped to the configured publisher |
| `source_revision` | Nonnegative safe integer; monotonically increasing for the object |
| `length_um` | Positive safe integer, micrometres |
| `material_id` | Nonempty printable-ASCII reference to a deployment-defined material definition |
| `translation_um` | Exactly three safe integers in the assembly coordinate frame |
| `geometry_digest` | Digest of the authoritative mesh asset |

The exactness contract covers this record's canonical bytes. It is not byte-for-byte reconstruction of an original CAD file, validation of a material model, or proof that a simulation is physically valid. The connector must declare any conversion into this limited profile. Rotations and other CAD properties require another schema rather than silent omission from a claimed full CAD replica.

### 3.2 Display mesh: `indexed-triangle-mesh-um-v1`

An asset is an object with exactly `schema`, `vertices_um`, and `triangles`. `vertices_um` is an ordered array of integer triples in component-local micrometres. `triangles` is an ordered array of index triples. Indices must be in range, repeated indices within one triangle are prohibited, and both reference and output triangles must have nonzero area. Resource caps apply before allocation.

The selected contract is `same-topology-vertex-bound`:

1. Obtain and hash-check the authoritative reference mesh named by the contract.
2. Confirm it equals the reconstructed exact record's `geometry_digest`.
3. Require identical vertex counts and identical ordered triangle index arrays.
4. For every vertex index i, compute the squared Euclidean difference between output and reference coordinates using sufficiently wide integer arithmetic.
5. Accept only if every squared difference is at most `max_vertex_error_um` squared.

The tolerance applies in component-local coordinates. The component's translation is exact and shared. For corresponding triangles with unchanged connectivity, the vertex bound also bounds separation between corresponding barycentric surface points. It does not certify volume, watertightness, clearances between different components, structural behavior, or arbitrarily remeshed surfaces.

The worked example sets the tolerance to 10 micrometres. This is a fixture value, not a recommended aerospace acceptance threshold.

The receiver must possess the reference mesh to perform this check. If it has to download the reference, count those bytes and the delay. A compact hash cannot establish geometric tolerance. Source-side attestations could be a future profile with an explicit trust model; they are not accepted as equivalent validation in this profile.

Both exact state and display contract are required for this component transaction. Neither slot is committed early. A later profile could support independently accepted display levels, with explicit UI status and snapshot rules.

## 4. Canonical bytes, identifiers, and framing

Control messages use JSON. For this profile, all strings and object member names contain only printable ASCII characters; numbers are integers in [-9007199254740991, 9007199254740991]. Null and booleans are allowed. Reject duplicate object keys, non-JSON values, fractional numbers, and unsupported fields. Arrays preserve order.

`CJ(x)` is RFC 8785 JSON canonicalization [3] over this restricted data model. `H(x)` is `sha256:` followed by 64 lowercase hexadecimal characters, computed over the UTF-8 bytes of CJ(x), without a BOM or final newline. Asset digests hash the exact transferred asset bytes. The JSON mesh assets in the example are transferred as CJ(mesh), making their asset digests equal to H(mesh).

Hash canonical component state, plan, payload, and asset bytes separately. Never substitute a compressed-payload checksum for a reconstructed-state digest. HTTP digest fields can protect HTTP content or representations according to their own definitions [4]; the explicit state digest here has an application-defined scope.

Prototype stream binding: each message is a 4-byte unsigned big-endian byte length followed by one UTF-8 JSON object, carried over an authenticated, confidential, reliable bidirectional stream. Length excludes the prefix. Default maximum message size is 8,388,608 bytes. Peers can agree a smaller limit through deployment configuration; larger messages are rejected before allocation. This is an experimental framing choice, not a registered WebSocket subprotocol, ALPN value, or media type.

Large assets are transferred separately from authorized sources and checked against the declared digest and size. Their bytes are part of the same workload accounting. A Layer 3 VPN can carry the stream, but application authorization remains required. Content-aware encoding occurs before application encryption.

## 5. Common envelope and message schemas

Every message has exactly these fields:

| Field | Rule |
|---|---|
| `protocol` | Literal `arf-experiment/0.1` |
| `type` | One of the message types below |
| `session_id` | Agreed identifier of the authenticated session |
| `message_id` | Unique within a session; retries retain the same logical content |
| `reply_to` | Message identifier being answered, or null |
| `body` | Type-specific object |

The message field tables and rules are the normative specification within this experimental draft. They are not a separately published JSON Schema.

### 5.1 Bootstrap: CAPABILITIES and STATE

`CAPABILITIES.body` requires `endpoint_id` (string), `profiles` (unique string array), `representations` (unique string array), and `limits` (object with the four positive integers defined below). In v0.1 the supported profile is `assembly-component-v1`. A receiver implementing this profile supports `state-full-v1`, `state-set-v1`, and `mesh-ref-v1`.

`STATE.body` requires `object_id`, `head` (revision and state_digest), and `available_dependencies` (unique digest array for dependencies relevant to the current request). A STATE message can be solicited by session setup or an OFFER. It is an inventory hint, not a reservation or a complete disclosure of everything stored on the device. A new receiver must provision a verified baseline through the trusted deployment process before this profile begins.

### 5.2 OFFER

`OFFER.body` requires `update_id`, `repair_of` (prior update ID or null), `plan`, and `plan_digest = H(plan)`. An OFFER contains one candidate. Multiple candidates use distinct update IDs; only one candidate for an object's current base may be active at a receiver in this profile.

Required plan fields:

| Field | Meaning |
|---|---|
| `object_id`, `publisher_id` | Object stream and authorized publisher |
| `base` | Exact `revision` and `state_digest` expected at the receiver |
| `target` | Greater `revision` and expected exact `state_digest` |
| `profile` | Literal `assembly-component-v1` |
| `representations` | `authoritative` is state-full-v1 or state-set-v1; `display` is mesh-ref-v1 |
| `contracts` | Exact authoritative mode and display mode/reference/tolerance |
| `dependencies` | Unique descriptors sorted lexicographically by digest |
| `payload_digest` | H of the complete UPDATE payload |
| `limits` | Agreed maximum frame bytes, dependency bytes, staging bytes, and work milliseconds |

Each dependency descriptor has exactly `digest`, `size_bytes` (positive integer), `role` (reference_mesh or display_mesh), and `locator` (authorized absolute HTTPS URL). The same digest may satisfy multiple uses; list it once, using reference_mesh if it is also the reference. All assets used by the selected plan must be listed. Locator permission is checked against deployment policy; a digest does not authorize a network request.

`contracts.authoritative` is exactly `{mode: exact-canonical-state}`. `contracts.display` contains exactly `mode`, `reference_digest`, and `max_vertex_error_um` (nonnegative integer). The reference digest must appear among dependencies. The receiver checks that the offered tolerance is no looser than its task requirement. The sender cannot weaken the requirement unilaterally.

Limits are hard ceilings for this transaction: `max_frame_bytes`, `max_dependency_bytes` (sum of declared unique dependency sizes, including locally held ones), `max_staging_bytes` (working memory and temporary artifact allocation budget), and `max_work_ms` (monotonic elapsed budget from beginning UPDATE processing, including dependency acquisition). Exceeding a ceiling prevents installation. Peer configuration can impose stricter ceilings; renegotiation uses a new OFFER, not changed semantics under an old digest.

### 5.3 ACCEPT

`ACCEPT.body` requires `update_id`, `plan_digest`, `accept_id` (unique unguessable reservation identifier in a real implementation), `lease_ms` (positive integer), `present_dependencies`, and `fetch_dependencies` (unique digest arrays).

The two arrays must be disjoint and their union must equal the plan's dependency digests. The receiver hash-checks and pins present dependencies for the reservation, and authorizes retrieval of the others within the plan limits. ACCEPT does not mean missing dependencies have already been downloaded, nor does it guarantee runtime availability or successful reconstruction.

Lease time begins when the receiver emits ACCEPT and is measured by its monotonic clock; no clock synchronization is required. UPDATE must arrive before expiry. Once UPDATE starts within the lease, the work budget governs completion. On expiry before UPDATE, release reservations and send a rejected RESULT with `LEASE_EXPIRED` if the session is available. Late UPDATE is rejected.

### 5.4 UPDATE

`UPDATE.body` requires `update_id`, `plan_digest`, `accept_id`, and `payload`. Their bindings must match the live reservation. Verify `H(payload) == plan.payload_digest` before executing any operations.

Payload has exactly `authoritative` and `display`:

- `authoritative` for state-full-v1: `{kind, state}`. `state` is the complete component record.
- `authoritative` for state-set-v1: `{kind, fields}`. Apply simultaneous replacements to a copy of the exact base record. Allowed field names are source_revision, length_um, material_id, translation_um, and geometry_digest. At least source_revision must be supplied. No arbitrary paths, scripts, network access, imports, loops, or side effects are permitted by this representation.
- `display` for mesh-ref-v1: `{kind, asset_digest}`. The asset must be listed among dependencies and decode as the defined mesh schema.

The kinds must equal the negotiated representations. The final record's object_id and source_revision must equal the plan target; all schema constraints remain in force.

### 5.5 RESULT

`RESULT.body` requires `update_id`, `plan_digest`, `status`, `head`, `checks`, and `error`.

- `status` is installed, needs_repair, or rejected.
- `head` always reports the currently installed revision and exact state digest, never a temporary reconstruction.
- `checks` has exactly `exact_state` and `display_contract` (boolean or null if not evaluated) and `max_vertex_error_squared_um2` (nonnegative safe integer or null). Use arbitrary-width internal arithmetic; if the measured error exceeds the representable report range, report null and TOLERANCE_EXCEEDED rather than overflowing.
- `error` is null on installed; otherwise `{code, slot}`. `slot` is authoritative, display, or transaction.

Error codes: BASE_MISMATCH, UNAUTHORIZED, UNSUPPORTED_PROFILE, UNSUPPORTED_REPRESENTATION, INVALID_MESSAGE, INVALID_PLAN, DEPENDENCY_UNAVAILABLE, DIGEST_MISMATCH, TOPOLOGY_MISMATCH, TOLERANCE_EXCEEDED, LEASE_EXPIRED, RESOURCE_LIMIT, and STALE_AT_COMMIT. Invalid envelopes that cannot safely identify a transaction may instead close the session.

`needs_repair` is reserved for dependency unavailability or a reconstructable output/digest/topology/tolerance failure after a valid reservation. Authorization failures, stale state, invalid plans, and resource/lease violations are rejected. Repair is not a license to bypass policy.

### 5.6 REPAIR

Following needs_repair, the receiver may send a REPAIR with `update_id`, `plan_digest`, `requested_authoritative` (state-full-v1), `requested_display` (mesh-ref-v1), and `require_exact_display_reference` (true).

The old attempt is closed; the installed head remains unchanged. A publisher agreeing to repair sends a new OFFER with a new update_id and `repair_of` set to the failed one. The new plan supplies full exact state and uses the reference mesh itself as display output, giving zero geometric deviation. Retain the original display tolerance or a stricter one; never silently loosen it. The new plan has its own payload/plan digests, ACCEPT, budgets, and UPDATE.

Already hash-verified immutable assets can be reused, but the new plan must declare its complete dependency set. If the head changed meanwhile, the publisher rebases against fresh STATE. The receiver need not abandon the entire session because one representation failed.

## 6. Validation and state transitions

For a valid UPDATE:

1. Verify identity, authorization, envelope, reservation, lease, plan binding, and payload digest.
2. Recheck the current base revision and digest. Acquire missing authorized dependencies within budgets; verify their exact sizes and digests before decoding.
3. Reconstruct the record in temporary state and validate its schema, target revision, and exact state digest.
4. Decode reference and display meshes under resource limits and perform the defined topology and vertex-bound checks.
5. In one atomic local operation, compare the installed base revision/digest again and publish the new exact record together with its display association and validation metadata. Keep a recoverable result record with this operation.
6. Emit installed only after the atomic operation is durable. Release unneeded staging and reservations.

| Current state | Event | Next state | Installed head |
|---|---|---|---|
| Ready | Valid OFFER accepted | Reserved | Prior revision |
| Reserved | Matching UPDATE within lease | Reconstructing | Prior revision |
| Reserved | Lease expires | Ready | Prior revision |
| Reconstructing | All checks pass | Validated | Prior revision |
| Validated | Atomic base comparison succeeds | Ready | Target revision |
| Validated | Base changed | Ready; rejected | Current independently installed head |
| Reconstructing | Repairable failure | Ready; needs_repair | Prior revision |
| Any active attempt | Policy/resource/schema rejection | Ready; rejected | Unchanged by this attempt |

Only one active attempt per object is permitted. An overlapping proposal receives a rejection rather than silently replacing the reservation. Other objects may progress independently subject to a shared resource budget.

Idempotency is keyed by publisher_id, object_id, and update_id; reuse with a different plan digest is INVALID_PLAN. Retransmitted accepted UPDATE must not apply a field operation twice. Store successful result metadata atomically with the head. After reconnection, use fresh session authentication and STATE to recover; a peer lacking a reservation renegotiates rather than executing an old UPDATE. A lost RESULT is not evidence of failed installation. A request for a target already installed with the same state digest and validated display binding can return its recorded result; conflicting same-revision state is rejected. A crash before commit leaves the prior head; a crash after commit recovers the new head and its result metadata.

## 7. Extension requirements for neural and procedural representations

A future representation specification must provide:

- Unambiguous payload encoding and output schema.
- Compatible decoder identity, artifact digests, dependencies, and numerical/conformance requirements. Encoder and decoder need not have identical weights.
- Runtime bounds, supported device behavior, and declared output fidelity.
- Test vectors, error handling, and fallback behavior.
- A defined residual baseline if correction data is used. Residuals are not assumed small.
- Isolation and allowed effects for executable operations. A sender-provided task is never implicitly authorized to run unrestricted code.

Model hashes establish artifact identity, not cross-platform bitwise execution. Determinism requirements must be part of the representation specification [8]. For tolerance profiles, the output must pass the relevant measured contract. Unknown representations are declined. The selector can choose a conventional method at any point through a newly negotiated plan.

## 8. Scaling to large datasets

Do not create one atomic transaction or one complete inventory message for a terabyte workspace. Partition it into independently addressable objects and immutable manifests. Paginate inventories and request only manifests relevant to the working set. A future dataset profile should define a root manifest binding the selected snapshot and child object revisions, with per-object acceptance and explicit completeness reporting.

Prioritize the dependency graph needed for the current view or computation. Apply shared bandwidth, decoder, memory, and staging limits across all objects; use backpressure before queues grow without bound. Bound speculative prefetch and count discarded speculative work. Stream or incrementally validate large assets under a future chunked profile; do not pretend the small JSON fixture specifies terabyte transport framing.

If a task requires a consistent assembly snapshot, display completion only when all required object revisions and dependencies match that snapshot. Object-level acceptance alone does not provide cross-object atomicity. A future multi-object profile must specify snapshot publication or coordinated commitment explicitly.

The caller may request an early visual working set or complete exact replication. The system must report which promise has been satisfied. Prediction may improve responsiveness, but predicted state must not be labeled authoritative.

## 9. Selection and measurement plan

Choose only representations that can meet the required contract. Estimate critical-path completion time from preparation, dependency misses, delivery, reconstruction, validation, and likely repair. Account for overlapping stages rather than blindly adding parallel costs. Track link capacity and receiver capacity independently; more agents do not increase a shared bottleneck's bandwidth.

Benchmark three comparable variants:

1. Conventional caching, incremental updates, and strong appropriate compression.
2. The same foundation with hybrid representations and fixed selection rules.
3. The same available representations with adaptive selection.

The second-to-third comparison isolates the selector. A learned representation must be actually implemented and included to measure its incremental benefit. Remote video streaming can be a separate experience baseline, with its different local capabilities and fidelity contract stated explicitly.

Use cold and warm sessions; identical source updates, task requirements, and network constraints; declared hardware; controlled cache inventory; and several update types, including novel objects. Count all auxiliary traffic, model/asset bootstrap, validation references, controller calls, repair, and offloading. Report bootstrap separately and amortize it over a disclosed session horizon rather than excluding it.

Required results: first accepted useful working-set latency; p50/p95/p99 update completion latency with sample count; full-replication completion where requested; transmitted bytes; reconstruction/validation time; peak receiver memory; dependency misses; fallback rate; and all fidelity failures. Report how failures are counted instead of omitting them from latency results.

Failure scenarios: stale baseline; corrupted payload; changed dependency bytes; unsupported decoder; missing validation reference; display error just above tolerance; cache eviction after inventory; resource exhaustion; lost result; duplicate update; and crash before/after commit. The prior head must survive unsuccessful attempts.

No performance measurement is supplied here. The numerical examples below check protocol semantics only and cannot establish compression ratios, headset suitability, or terabyte-scale throughput.

## 10. Worked transcript

This is a tiny triangular test fixture representing one component's display surface, not a flight-qualified rocket model. The authorized publisher changes the component length and source geometry from revision 27 to 28. The reference mesh is already present; the display mesh is fetched after acceptance. Example hostnames use the reserved invalid suffix and do not identify live services. Example IDs and reservations are readable placeholders; production session/reservation IDs need appropriate uniqueness and unpredictability.

### 10.1 Canonical object fixtures

**Baseline authoritative record**

```json
{
  "schema": "component-state-v1",
  "object_id": "assembly/component-481",
  "source_revision": 27,
  "length_um": 1000000,
  "material_id": "material/example-v1",
  "translation_um": [
    0,
    0,
    0
  ],
  "geometry_digest": "sha256:48d1b79a66fceb3dbe80bdf37f331722df6e06531f9ec50a08980d9c7df8229c"
}
```

Canonical digest: `sha256:56a050c5a1ae950aea62b3c1e9fd082332d3975c4b1a5380cf3317ac90904e04`.

**Target authoritative record**

```json
{
  "schema": "component-state-v1",
  "object_id": "assembly/component-481",
  "source_revision": 28,
  "length_um": 1001000,
  "material_id": "material/example-v1",
  "translation_um": [
    0,
    0,
    0
  ],
  "geometry_digest": "sha256:0f4c900e0e441025ab486189209d4f9795451d340b983c6279c721314f93dc56"
}
```

Canonical digest: `sha256:f1b1f335e0e3f5883f7f404a045ff42f73163c118f986cfa2d8022719eae1813`.

**Authoritative target mesh**

```json
{
  "schema": "indexed-triangle-mesh-um-v1",
  "vertices_um": [
    [
      0,
      0,
      0
    ],
    [
      1001000,
      0,
      0
    ],
    [
      0,
      1000000,
      0
    ]
  ],
  "triangles": [
    [
      0,
      1,
      2
    ]
  ]
}
```

Canonical digest: `sha256:0f4c900e0e441025ab486189209d4f9795451d340b983c6279c721314f93dc56`.

**Accepted display mesh**

```json
{
  "schema": "indexed-triangle-mesh-um-v1",
  "vertices_um": [
    [
      0,
      0,
      0
    ],
    [
      1001000,
      0,
      5
    ],
    [
      0,
      1000000,
      0
    ]
  ],
  "triangles": [
    [
      0,
      1,
      2
    ]
  ]
}
```

Canonical digest: `sha256:7a53ca7608bda01dbc48922ce78d95086ef0f15162bc1b70ef84433bda885065`.

### OFFER

```json
{
  "protocol": "arf-experiment/0.1",
  "type": "OFFER",
  "session_id": "session-example-1",
  "message_id": "m1",
  "reply_to": null,
  "body": {
    "update_id": "update-1042",
    "repair_of": null,
    "plan": {
      "object_id": "assembly/component-481",
      "publisher_id": "publisher-example",
      "base": {
        "revision": 27,
        "state_digest": "sha256:56a050c5a1ae950aea62b3c1e9fd082332d3975c4b1a5380cf3317ac90904e04"
      },
      "target": {
        "revision": 28,
        "state_digest": "sha256:f1b1f335e0e3f5883f7f404a045ff42f73163c118f986cfa2d8022719eae1813"
      },
      "profile": "assembly-component-v1",
      "representations": {
        "authoritative": "state-set-v1",
        "display": "mesh-ref-v1"
      },
      "contracts": {
        "authoritative": {
          "mode": "exact-canonical-state"
        },
        "display": {
          "mode": "same-topology-vertex-bound",
          "reference_digest": "sha256:0f4c900e0e441025ab486189209d4f9795451d340b983c6279c721314f93dc56",
          "max_vertex_error_um": 10
        }
      },
      "dependencies": [
        {
          "digest": "sha256:0f4c900e0e441025ab486189209d4f9795451d340b983c6279c721314f93dc56",
          "size_bytes": 114,
          "role": "reference_mesh",
          "locator": "https://assets.example.invalid/reference-28.json"
        },
        {
          "digest": "sha256:7a53ca7608bda01dbc48922ce78d95086ef0f15162bc1b70ef84433bda885065",
          "size_bytes": 114,
          "role": "display_mesh",
          "locator": "https://assets.example.invalid/display-28.json"
        }
      ],
      "payload_digest": "sha256:551403b37a2fbf6e5a97575e90e056f1df23cbfd94a7a9bd0bf629452516e86b",
      "limits": {
        "max_frame_bytes": 8388608,
        "max_dependency_bytes": 1048576,
        "max_staging_bytes": 16777216,
        "max_work_ms": 5000
      }
    },
    "plan_digest": "sha256:e3894e47980c6e806ab465f400672144a08790eeb41dd1a51f0bc9ebece55c64"
  }
}
```

### ACCEPT

```json
{
  "protocol": "arf-experiment/0.1",
  "type": "ACCEPT",
  "session_id": "session-example-1",
  "message_id": "m2",
  "reply_to": "m1",
  "body": {
    "update_id": "update-1042",
    "plan_digest": "sha256:e3894e47980c6e806ab465f400672144a08790eeb41dd1a51f0bc9ebece55c64",
    "accept_id": "accept-example-1",
    "lease_ms": 10000,
    "present_dependencies": [
      "sha256:0f4c900e0e441025ab486189209d4f9795451d340b983c6279c721314f93dc56"
    ],
    "fetch_dependencies": [
      "sha256:7a53ca7608bda01dbc48922ce78d95086ef0f15162bc1b70ef84433bda885065"
    ]
  }
}
```

### UPDATE

```json
{
  "protocol": "arf-experiment/0.1",
  "type": "UPDATE",
  "session_id": "session-example-1",
  "message_id": "m3",
  "reply_to": "m2",
  "body": {
    "update_id": "update-1042",
    "plan_digest": "sha256:e3894e47980c6e806ab465f400672144a08790eeb41dd1a51f0bc9ebece55c64",
    "accept_id": "accept-example-1",
    "payload": {
      "authoritative": {
        "kind": "state-set-v1",
        "fields": {
          "source_revision": 28,
          "length_um": 1001000,
          "geometry_digest": "sha256:0f4c900e0e441025ab486189209d4f9795451d340b983c6279c721314f93dc56"
        }
      },
      "display": {
        "kind": "mesh-ref-v1",
        "asset_digest": "sha256:7a53ca7608bda01dbc48922ce78d95086ef0f15162bc1b70ef84433bda885065"
      }
    }
  }
}
```

### Successful RESULT

```json
{
  "protocol": "arf-experiment/0.1",
  "type": "RESULT",
  "session_id": "session-example-1",
  "message_id": "m4",
  "reply_to": "m3",
  "body": {
    "update_id": "update-1042",
    "plan_digest": "sha256:e3894e47980c6e806ab465f400672144a08790eeb41dd1a51f0bc9ebece55c64",
    "status": "installed",
    "head": {
      "revision": 28,
      "state_digest": "sha256:f1b1f335e0e3f5883f7f404a045ff42f73163c118f986cfa2d8022719eae1813"
    },
    "checks": {
      "exact_state": true,
      "display_contract": true,
      "max_vertex_error_squared_um2": 25
    },
    "error": null
  }
}
```

### 10.2 Repair branch

This is a separate session scenario starting from revision 27; do not execute it after installing the success scenario. Its display vertex is displaced by 11 micrometres, so squared error 121 exceeds the 100-square-micrometre limit. Its distinct asset, plan, and payload digests are computed for this scenario. The failed update preserves revision 27, and the repair offer reuses the same exact target and fidelity requirement with a conventional representation.

**Display asset that fails tolerance**

```json
{
  "schema": "indexed-triangle-mesh-um-v1",
  "vertices_um": [
    [
      0,
      0,
      0
    ],
    [
      1001000,
      0,
      11
    ],
    [
      0,
      1000000,
      0
    ]
  ],
  "triangles": [
    [
      0,
      1,
      2
    ]
  ]
}
```

**Alternative OFFER**

```json
{
  "protocol": "arf-experiment/0.1",
  "type": "OFFER",
  "session_id": "session-example-1",
  "message_id": "b1",
  "reply_to": null,
  "body": {
    "update_id": "update-1042-bad",
    "repair_of": null,
    "plan": {
      "object_id": "assembly/component-481",
      "publisher_id": "publisher-example",
      "base": {
        "revision": 27,
        "state_digest": "sha256:56a050c5a1ae950aea62b3c1e9fd082332d3975c4b1a5380cf3317ac90904e04"
      },
      "target": {
        "revision": 28,
        "state_digest": "sha256:f1b1f335e0e3f5883f7f404a045ff42f73163c118f986cfa2d8022719eae1813"
      },
      "profile": "assembly-component-v1",
      "representations": {
        "authoritative": "state-set-v1",
        "display": "mesh-ref-v1"
      },
      "contracts": {
        "authoritative": {
          "mode": "exact-canonical-state"
        },
        "display": {
          "mode": "same-topology-vertex-bound",
          "reference_digest": "sha256:0f4c900e0e441025ab486189209d4f9795451d340b983c6279c721314f93dc56",
          "max_vertex_error_um": 10
        }
      },
      "dependencies": [
        {
          "digest": "sha256:0f4c900e0e441025ab486189209d4f9795451d340b983c6279c721314f93dc56",
          "size_bytes": 114,
          "role": "reference_mesh",
          "locator": "https://assets.example.invalid/reference-28.json"
        },
        {
          "digest": "sha256:e485ed7ffe991fab2bbb20f82779ad75be55bda11b7c78de5c311adcdc6860fc",
          "size_bytes": 115,
          "role": "display_mesh",
          "locator": "https://assets.example.invalid/display-28-bad.json"
        }
      ],
      "payload_digest": "sha256:1b626271a459284870e95f1bc36fdf50b91f22528ac3b627faad2c1bc4a15f2d",
      "limits": {
        "max_frame_bytes": 8388608,
        "max_dependency_bytes": 1048576,
        "max_staging_bytes": 16777216,
        "max_work_ms": 5000
      }
    },
    "plan_digest": "sha256:33b2c5c7e205fe7c50218f78e62fcdedc8ab62c2db414153093c8638a8e3338e"
  }
}
```

**Alternative ACCEPT**

```json
{
  "protocol": "arf-experiment/0.1",
  "type": "ACCEPT",
  "session_id": "session-example-1",
  "message_id": "b2",
  "reply_to": "b1",
  "body": {
    "update_id": "update-1042-bad",
    "plan_digest": "sha256:33b2c5c7e205fe7c50218f78e62fcdedc8ab62c2db414153093c8638a8e3338e",
    "accept_id": "accept-example-bad",
    "lease_ms": 10000,
    "present_dependencies": [
      "sha256:0f4c900e0e441025ab486189209d4f9795451d340b983c6279c721314f93dc56"
    ],
    "fetch_dependencies": [
      "sha256:e485ed7ffe991fab2bbb20f82779ad75be55bda11b7c78de5c311adcdc6860fc"
    ]
  }
}
```

**Alternative UPDATE**

```json
{
  "protocol": "arf-experiment/0.1",
  "type": "UPDATE",
  "session_id": "session-example-1",
  "message_id": "b3",
  "reply_to": "b2",
  "body": {
    "update_id": "update-1042-bad",
    "plan_digest": "sha256:33b2c5c7e205fe7c50218f78e62fcdedc8ab62c2db414153093c8638a8e3338e",
    "accept_id": "accept-example-bad",
    "payload": {
      "authoritative": {
        "kind": "state-set-v1",
        "fields": {
          "source_revision": 28,
          "length_um": 1001000,
          "geometry_digest": "sha256:0f4c900e0e441025ab486189209d4f9795451d340b983c6279c721314f93dc56"
        }
      },
      "display": {
        "kind": "mesh-ref-v1",
        "asset_digest": "sha256:e485ed7ffe991fab2bbb20f82779ad75be55bda11b7c78de5c311adcdc6860fc"
      }
    }
  }
}
```

**Failed RESULT**

```json
{
  "protocol": "arf-experiment/0.1",
  "type": "RESULT",
  "session_id": "session-example-1",
  "message_id": "b4",
  "reply_to": "b3",
  "body": {
    "update_id": "update-1042-bad",
    "plan_digest": "sha256:33b2c5c7e205fe7c50218f78e62fcdedc8ab62c2db414153093c8638a8e3338e",
    "status": "needs_repair",
    "head": {
      "revision": 27,
      "state_digest": "sha256:56a050c5a1ae950aea62b3c1e9fd082332d3975c4b1a5380cf3317ac90904e04"
    },
    "checks": {
      "exact_state": true,
      "display_contract": false,
      "max_vertex_error_squared_um2": 121
    },
    "error": {
      "code": "TOLERANCE_EXCEEDED",
      "slot": "display"
    }
  }
}
```

**REPAIR request**

```json
{
  "protocol": "arf-experiment/0.1",
  "type": "REPAIR",
  "session_id": "session-example-1",
  "message_id": "b5",
  "reply_to": "b4",
  "body": {
    "update_id": "update-1042-bad",
    "plan_digest": "sha256:33b2c5c7e205fe7c50218f78e62fcdedc8ab62c2db414153093c8638a8e3338e",
    "requested_authoritative": "state-full-v1",
    "requested_display": "mesh-ref-v1",
    "require_exact_display_reference": true
  }
}
```

**Conventional repair OFFER**

```json
{
  "protocol": "arf-experiment/0.1",
  "type": "OFFER",
  "session_id": "session-example-1",
  "message_id": "r1",
  "reply_to": "b5",
  "body": {
    "update_id": "update-1043",
    "repair_of": "update-1042-bad",
    "plan": {
      "object_id": "assembly/component-481",
      "publisher_id": "publisher-example",
      "base": {
        "revision": 27,
        "state_digest": "sha256:56a050c5a1ae950aea62b3c1e9fd082332d3975c4b1a5380cf3317ac90904e04"
      },
      "target": {
        "revision": 28,
        "state_digest": "sha256:f1b1f335e0e3f5883f7f404a045ff42f73163c118f986cfa2d8022719eae1813"
      },
      "profile": "assembly-component-v1",
      "representations": {
        "authoritative": "state-full-v1",
        "display": "mesh-ref-v1"
      },
      "contracts": {
        "authoritative": {
          "mode": "exact-canonical-state"
        },
        "display": {
          "mode": "same-topology-vertex-bound",
          "reference_digest": "sha256:0f4c900e0e441025ab486189209d4f9795451d340b983c6279c721314f93dc56",
          "max_vertex_error_um": 10
        }
      },
      "dependencies": [
        {
          "digest": "sha256:0f4c900e0e441025ab486189209d4f9795451d340b983c6279c721314f93dc56",
          "size_bytes": 114,
          "role": "reference_mesh",
          "locator": "https://assets.example.invalid/reference-28.json"
        }
      ],
      "payload_digest": "sha256:551efc5e579690979e054d918473552d6dcc459f74f21115a510693531f40fdd",
      "limits": {
        "max_frame_bytes": 8388608,
        "max_dependency_bytes": 1048576,
        "max_staging_bytes": 16777216,
        "max_work_ms": 5000
      }
    },
    "plan_digest": "sha256:e44d99ae3f048985f7f1c88c3a067eae36e4eff5d9f9bc818e17851e3db8180f"
  }
}
```

**Repair ACCEPT**

```json
{
  "protocol": "arf-experiment/0.1",
  "type": "ACCEPT",
  "session_id": "session-example-1",
  "message_id": "r2",
  "reply_to": "r1",
  "body": {
    "update_id": "update-1043",
    "plan_digest": "sha256:e44d99ae3f048985f7f1c88c3a067eae36e4eff5d9f9bc818e17851e3db8180f",
    "accept_id": "accept-example-repair",
    "lease_ms": 10000,
    "present_dependencies": [
      "sha256:0f4c900e0e441025ab486189209d4f9795451d340b983c6279c721314f93dc56"
    ],
    "fetch_dependencies": []
  }
}
```

**Repair UPDATE**

```json
{
  "protocol": "arf-experiment/0.1",
  "type": "UPDATE",
  "session_id": "session-example-1",
  "message_id": "r3",
  "reply_to": "r2",
  "body": {
    "update_id": "update-1043",
    "plan_digest": "sha256:e44d99ae3f048985f7f1c88c3a067eae36e4eff5d9f9bc818e17851e3db8180f",
    "accept_id": "accept-example-repair",
    "payload": {
      "authoritative": {
        "kind": "state-full-v1",
        "state": {
          "schema": "component-state-v1",
          "object_id": "assembly/component-481",
          "source_revision": 28,
          "length_um": 1001000,
          "material_id": "material/example-v1",
          "translation_um": [
            0,
            0,
            0
          ],
          "geometry_digest": "sha256:0f4c900e0e441025ab486189209d4f9795451d340b983c6279c721314f93dc56"
        }
      },
      "display": {
        "kind": "mesh-ref-v1",
        "asset_digest": "sha256:0f4c900e0e441025ab486189209d4f9795451d340b983c6279c721314f93dc56"
      }
    }
  }
}
```

**Repair RESULT**

```json
{
  "protocol": "arf-experiment/0.1",
  "type": "RESULT",
  "session_id": "session-example-1",
  "message_id": "r4",
  "reply_to": "r3",
  "body": {
    "update_id": "update-1043",
    "plan_digest": "sha256:e44d99ae3f048985f7f1c88c3a067eae36e4eff5d9f9bc818e17851e3db8180f",
    "status": "installed",
    "head": {
      "revision": 28,
      "state_digest": "sha256:f1b1f335e0e3f5883f7f404a045ff42f73163c118f986cfa2d8022719eae1813"
    },
    "checks": {
      "exact_state": true,
      "display_contract": true,
      "max_vertex_error_squared_um2": 0
    },
    "error": null
  }
}
```

The repair response uses a new OFFER and update ID, full exact component state, and the authoritative reference mesh as display output. This yields zero display error when the assets are correctly decoded. Revision 27 stays installed until that new transaction completes, unless another valid transaction has already advanced the head.

## 11. Verification performed for this artifact

- Generated the canonical fixture bytes and the success, failure, and repair transcript SHA-256 digests.
- Reconstructed the target record by applying the permitted field replacements to the baseline and checked its exact digest.
- Checked that each transcript binds its immutable plan, that each payload digest matches, and that dependency partitions cover the corresponding plan exactly.
- Computed the accepted display's maximum squared vertex error as 25 square micrometres (5 micrometres), within the 100-square-micrometre limit.
- Computed the alternative display mesh's 11-micrometre failure and checked the repair's unchanged fidelity contract and exact target record.
- Parsed the emitted JSON examples. These checks do not constitute a general RFC 8785 conformance suite, a network protocol implementation, neural decoding, fault-injection execution, or a performance benchmark.

## 12. Standards discussion boundary

The candidate standardization subject is the interoperable reconstruction agreement, its representation extension mechanism, and explicit acceptance semantics. The controller's internal algorithm can remain implementation-specific. An application protocol over existing transport can be prototyped before seeking registered identifiers. No IANA assignment or IETF endorsement is implied.

The next evidence milestone is independent implementations interoperating on the exact same acceptance and failure cases, followed by workload measurements showing an advantage over the conventional baseline. The IETF has a process for bringing new work for discussion [9]; this local experimental draft has not been submitted.

## References

1. RFC 3229, Delta encoding in HTTP. https://www.rfc-editor.org/rfc/rfc3229.html
2. RFC 9842, Compression Dictionary Transport. https://www.rfc-editor.org/rfc/rfc9842.html
3. RFC 8785, JSON Canonicalization Scheme (JCS). https://www.rfc-editor.org/rfc/rfc8785.html
4. RFC 9530, Digest Fields. https://www.rfc-editor.org/rfc/rfc9530.html
5. RFC 9221, An Unreliable Datagram Extension to QUIC. https://www.rfc-editor.org/rfc/rfc9221.html
6. Microsoft, Deep Contextual Video Compression. https://github.com/microsoft/DCVC
7. OpenUSD, Introduction to USD. https://openusd.org/release/intro.html
8. PyTorch, Reproducibility. https://github.com/pytorch/pytorch/blob/main/docs/source/notes/randomness.md
9. IETF, Bringing new work to the IETF. https://www.ietf.org/process/new-work/
