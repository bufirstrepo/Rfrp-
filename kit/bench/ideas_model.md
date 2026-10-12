# Speed mechanisms: first-order models (MODELED)

Reuses `speed_model.py`'s KV-cache and compute model (Llama 3.1, one H100-equivalent per receiver, prefill at an assumed 50% of dense BF16 peak). Decode is modeled as memory-bound at batch 1: every weight and the whole KV cache read once per token at an assumed 70% of 3.35 TB/s. No queueing, contention or loss. Each section says when the mechanism saves time and when it loses.

## 1. Fidelity chosen per receiver

Llama 3.1 8B, 32K-token context. R1 on 400 Gb/s needs exact state; R2 on 10 Gb/s accepts bounded (E or T); R3 on 1 Gb/s accepts any class. Seconds until each holds usable state:

| Policy | R1 | R2 | R3 | Sum | Slowest |
|---|---|---|---|---|---|
| one policy for all: exact, receivers on different stacks | 0.09 | 3.44 | 34.36 | 37.88 | 34.36 |
| one policy for all: exact, every receiver on the sender's pinned stack | 0.09 | 2.64 | 2.64 | 5.36 | 2.64 |
| per-receiver fidelity (each receiver's own requirement) | 0.09 | 0.86 | 1.63 | 2.58 | 1.63 |

Choices under per-receiver fidelity: R1: send KV, BF16 (E); R2: send KV, ~4x codec (T); R3: send text, recompute, default kernels (N). The codec option counts bytes only; encoding and decoding time are not modeled.

## 2. Start before the exact state arrives (ideal layered code)

Llama 3.1 8B, 256-token response, coarse layer 1/4 of the exact size. Exact path: wait for the exact cache, then decode. Lossy path: decode on the coarse cache (outputs can differ; that is idea 1). Speculative path: draft on the coarse cache, verify once the exact cache is complete, keep the matching prefix (outputs identical to the exact path). Seconds to the full response, by per-token acceptance:

| Context | Link | Exact path | Lossy path | a = 0.90 | a = 0.95 | a = 0.99 | a = 0.999 |
|---|---|---|---|---|---|---|---|
| 8K | 100 Gb/s | 1.96 | 1.89 | 1.92 (2%) | 1.92 (2%) | 1.91 (3%) | 1.91 (3%) |
| 8K | 25 Gb/s | 2.21 | 1.96 | 2.15 (3%) | 2.10 (5%) | 2.00 (9%) | 1.97 (11%) |
| 8K | 10 Gb/s | 2.73 | 2.08 | 2.66 (2%) | 2.59 (5%) | 2.31 (15%) | 2.12 (22%) |
| 32K | 100 Gb/s | 2.57 | 2.31 | 2.49 (3%) | 2.44 (5%) | 2.35 (8%) | 2.33 (9%) |
| 32K | 25 Gb/s | 3.60 | 2.57 | 3.52 (2%) | 3.43 (5%) | 3.00 (17%) | 2.64 (27%) |
| 32K | 10 Gb/s | 5.66 | 3.08 | 5.59 (1%) | 5.50 (3%) | 4.87 (14%) | 3.71 (34%) |
| 128K | 100 Gb/s | 5.00 | 3.97 | 4.88 (3%) | 4.74 (5%) | 4.29 (14%) | 4.03 (19%) |
| 128K | 25 Gb/s | 9.13 | 5.00 | 9.03 (1%) | 8.89 (3%) | 7.86 (14%) | 5.97 (35%) |
| 128K | 10 Gb/s | 17.37 | 7.07 | 17.27 (1%) | 17.13 (1%) | 16.11 (7%) | 14.21 (18%) |

### Sensitivity: the layered code adds 10% over a direct exact transfer

Llama 3.1 8B, 256-token response, coarse layer 1/4 of the exact size. Exact path: wait for the exact cache, then decode. Lossy path: decode on the coarse cache (outputs can differ; that is idea 1). Speculative path: draft on the coarse cache, verify once the exact cache is complete, keep the matching prefix (outputs identical to the exact path). Seconds to the full response, by per-token acceptance:

| Context | Link | Exact path | Lossy path | a = 0.90 | a = 0.95 | a = 0.99 | a = 0.999 |
|---|---|---|---|---|---|---|---|
| 8K | 100 Gb/s | 1.96 | 1.89 | 1.93 (1%) | 1.92 (2%) | 1.91 (2%) | 1.91 (3%) |
| 8K | 25 Gb/s | 2.21 | 1.96 | 2.18 (1%) | 2.13 (4%) | 2.02 (9%) | 1.98 (11%) |
| 8K | 10 Gb/s | 2.73 | 2.08 | 2.75 (-1%) | 2.68 (2%) | 2.36 (13%) | 2.13 (22%) |
| 32K | 100 Gb/s | 2.57 | 2.31 | 2.52 (2%) | 2.47 (4%) | 2.36 (8%) | 2.33 (9%) |
| 32K | 25 Gb/s | 3.60 | 2.57 | 3.66 (-2%) | 3.57 (1%) | 3.10 (14%) | 2.65 (26%) |
| 32K | 10 Gb/s | 5.66 | 3.08 | 5.93 (-5%) | 5.84 (-3%) | 5.22 (8%) | 4.06 (28%) |
| 128K | 100 Gb/s | 5.00 | 3.97 | 5.01 (-0%) | 4.88 (3%) | 4.36 (13%) | 4.04 (19%) |
| 128K | 25 Gb/s | 9.13 | 5.00 | 9.58 (-5%) | 9.44 (-3%) | 8.41 (8%) | 6.52 (29%) |
| 128K | 10 Gb/s | 17.37 | 7.07 | 18.65 (-7%) | 18.51 (-7%) | 17.48 (-1%) | 15.59 (10%) |

### Sensitivity: coarse layer half the exact size (an 8-bit layer)

Llama 3.1 8B, 256-token response, coarse layer 1/2 of the exact size. Exact path: wait for the exact cache, then decode. Lossy path: decode on the coarse cache (outputs can differ; that is idea 1). Speculative path: draft on the coarse cache, verify once the exact cache is complete, keep the matching prefix (outputs identical to the exact path). Seconds to the full response, by per-token acceptance:

| Context | Link | Exact path | Lossy path | a = 0.90 | a = 0.95 | a = 0.99 | a = 0.999 |
|---|---|---|---|---|---|---|---|
| 8K | 100 Gb/s | 1.96 | 1.91 | 1.93 (1%) | 1.93 (1%) | 1.93 (1%) | 1.93 (1%) |
| 8K | 25 Gb/s | 2.21 | 2.04 | 2.15 (3%) | 2.12 (4%) | 2.07 (6%) | 2.06 (7%) |
| 8K | 10 Gb/s | 2.73 | 2.30 | 2.66 (2%) | 2.60 (5%) | 2.41 (12%) | 2.33 (15%) |
| 32K | 100 Gb/s | 2.57 | 2.39 | 2.50 (3%) | 2.47 (4%) | 2.42 (6%) | 2.41 (6%) |
| 32K | 25 Gb/s | 3.60 | 2.91 | 3.52 (2%) | 3.44 (4%) | 3.13 (13%) | 2.95 (18%) |
| 32K | 10 Gb/s | 5.66 | 3.94 | 5.58 (1%) | 5.50 (3%) | 4.92 (13%) | 4.12 (27%) |
| 128K | 100 Gb/s | 5.00 | 4.32 | 4.88 (3%) | 4.76 (5%) | 4.47 (11%) | 4.35 (13%) |
| 128K | 25 Gb/s | 9.13 | 6.38 | 9.02 (1%) | 8.88 (3%) | 7.95 (13%) | 6.67 (27%) |
| 128K | 10 Gb/s | 17.37 | 10.50 | 17.27 (1%) | 17.13 (1%) | 16.11 (7%) | 14.21 (18%) |

### When it loses

- Coarse layer 1/4, ideal layered code: worst case over acceptances 0–0.999 and every row above is 0.33% slower (+30.0 ms), at acceptance 0, 128K context, 25 Gb/s.
- Coarse layer 1/2, ideal layered code: worst case over acceptances 0–0.999 and every row above is 0.21% slower (+19.0 ms), at acceptance 0, 128K context, 25 Gb/s.
- Coarse layer 1/4, layered code 10% larger than a direct exact transfer: worst case over acceptances 0–0.999 and every row above is 8.08% slower (+1,404.0 ms), at acceptance 0, 128K context, 10 Gb/s.
- Coarse layer 1/2, layered code 10% larger than a direct exact transfer: worst case over acceptances 0–0.999 and every row above is 8.08% slower (+1,404.0 ms), at acceptance 0, 128K context, 10 Gb/s.

With an ideal layered code the only extra cost is the verification pass: at acceptance 0 it keeps one exact token and costs one pass over the whole draft, which at long contexts takes longer than one decode step. With any acceptance worth speculating on, the kept tokens repay it.

Per-token acceptance is treated as independent, which real drafts only approximate. On the small model with a 4-bit cache, the median draft kept 4 of 48 tokens and 16% were kept whole; independent acceptance at the same average (0.942) would give a median of 12 and 6% kept whole. Mismatches cluster by prompt.
Treat these savings as first-order.

### At the acceptance the small model showed

Measured per-token acceptance on the small model (`spec_start_toy.md`), by KV bits: 8-bit 0.9979, 6-bit 0.9916, 4-bit 0.9425, 3-bit 0.8427, 2-bit 0.3642. That is a sub-million-parameter model, not a production measurement. Savings against the exact path at those acceptances (ideal layered code / layered code 10% larger):

| Coarse layer | Acceptance | Context | 100 Gb/s | 25 Gb/s | 10 Gb/s |
|---|---|---|---|---|---|
| 4-bit, 1/4 size | 0.9425 | 8K | 2% / 2% | 5% / 3% | 4% / 1% |
| 4-bit, 1/4 size | 0.9425 | 32K | 4% / 3% | 4% / 0% | 2% / -4% |
| 4-bit, 1/4 size | 0.9425 | 128K | 5% / 2% | 2% / -4% | 1% / -7% |
| 8-bit, 1/2 size | 0.9979 | 8K | 1% / 2% | 7% / 7% | 14% / 14% |
| 8-bit, 1/2 size | 0.9979 | 32K | 6% / 6% | 17% / 17% | 25% / 22% |
| 8-bit, 1/2 size | 0.9979 | 128K | 13% / 12% | 24% / 22% | 16% / 8% |

Differences of a point or so, including the cells where the larger code looks better, come from counting whole decode steps while the exact cache arrives.

## 3. Compute once, fan out

N receivers at a remote site need the same 32K-token Llama 3.1 8B cache (4.29 GB). The site shares one 10 Gb/s WAN link; inside it, links are 400 Gb/s and holders re-forward (doubling). Seconds until the last receiver holds it / GPU-seconds spent:

| N | Each recomputes | Origin sends each copy | One WAN copy + LAN fan-out | One recompute at the site + LAN fan-out |
|---|---|---|---|---|
| 1 | 1.63 s / 1.63 GPU-s | 3.44 s / 0.00 GPU-s | 3.52 s / 0.00 GPU-s | 1.63 s / 1.63 GPU-s |
| 8 | 1.63 s / 13.06 GPU-s | 27.49 s / 0.00 GPU-s | 3.78 s / 0.00 GPU-s | 1.98 s / 1.63 GPU-s |
| 64 | 1.63 s / 104.49 GPU-s | 219.90 s / 0.00 GPU-s | 4.04 s / 0.00 GPU-s | 2.23 s / 1.63 GPU-s |

## 4. Cancel superseded work

A 16.06 GB state (Llama 3.1 8B weights in BF16) gets a new version every 3 s for 60 s. Delivery delay is production to arrival; age of held state is how old the receiver's newest version is just before the next one lands (worst case).

| Link | Policy | Versions sent | Last arrives at | Worst delivery delay | Worst age of held state | Bytes sent |
|---|---|---|---|---|---|---|
| 25 Gb/s, 5.14 s per copy (load 171%) | Every version, in order | 21 | 107.9 s | 47.9 s and growing | 50.9 s and growing | 100% |
| 25 Gb/s, 5.14 s per copy (load 171%) | Skip to the latest | 13 | 66.8 s | 8.1 s | 13.3 s | 62% |
| 100 Gb/s, 1.28 s per copy (load 43%) | Every version, in order | 21 | 61.3 s | 1.3 s | 4.3 s | 100% |
| 100 Gb/s, 1.28 s per copy (load 43%) | Skip to the latest | 21 | 61.3 s | 1.3 s | 4.3 s | 100% |

Skipping helps only when the link cannot keep up (load above 100%); when it can, both policies send every version.

## 5. Trust by proof instead of re-running

An untrusted worker returns R tokens for an 8K-token prompt (Llama 3.1 8B). Re-running repeats the generation; checking a TOPLOC-style proof is one parallel pass over the known tokens:

| Generated tokens | Re-run to check | Proof check | Faster by | Proof size |
|---|---|---|---|---|
| 256 | 2.17 s | 0.312 s | 7.0× | 2,064 B |
| 1,024 | 7.81 s | 0.344 s | 22.7× | 8,256 B |
| 4,096 | 30.70 s | 0.479 s | 64.1× | 33,024 B |

The speedup comes from checking in one parallel pass instead of regenerating token by token; a verifier that recomputes the claimed tokens in one pass is just as fast. What the proof adds is tolerance for numeric differences across hardware, binding to the runtime and input, and a compact record a third party can check later.

## 6. No round trip for steady pipelines

A chain of k handoffs at 10 Gb/s; negotiated ≈ 2 RTT + transfer per handoff, push ≈ ½ RTT + transfer. The baseline is ARFP's own DEMAND/OFFER/ACCEPT negotiation, not HTTP or a pub/sub system:

| Where | State per handoff | Handoffs | Negotiated | Push | Saved |
|---|---|---|---|---|---|
| inside one data center (assumed 0.1 ms RTT) | 100 KB | 1 | 0.0003 s | 0.0001 s | 54% |
| inside one data center (assumed 0.1 ms RTT) | 100 KB | 5 | 0.0014 s | 0.0007 s | 54% |
| inside one data center (assumed 0.1 ms RTT) | 100 KB | 20 | 0.0056 s | 0.0026 s | 54% |
| inside one data center (assumed 0.1 ms RTT) | 4.29 GB | 1 | 3.4322 s | 3.4320 s | 0% |
| inside one data center (assumed 0.1 ms RTT) | 4.29 GB | 5 | 17.1610 s | 17.1602 s | 0% |
| inside one data center (assumed 0.1 ms RTT) | 4.29 GB | 20 | 68.6440 s | 68.6410 s | 0% |
| between regions (56 ms, New York-London fiber minimum) | 100 KB | 1 | 0.1121 s | 0.0281 s | 75% |
| between regions (56 ms, New York-London fiber minimum) | 100 KB | 5 | 0.5604 s | 0.1404 s | 75% |
| between regions (56 ms, New York-London fiber minimum) | 100 KB | 20 | 2.2416 s | 0.5616 s | 75% |
| between regions (56 ms, New York-London fiber minimum) | 4.29 GB | 1 | 3.5440 s | 3.4600 s | 2% |
| between regions (56 ms, New York-London fiber minimum) | 4.29 GB | 5 | 17.7200 s | 17.3000 s | 2% |
| between regions (56 ms, New York-London fiber minimum) | 4.29 GB | 20 | 70.8800 s | 69.2000 s | 2% |
