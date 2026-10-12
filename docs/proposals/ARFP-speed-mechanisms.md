# Speed mechanisms: six ways ARFP could make AI state handoff faster

**Date:** 2026-10-12 · **Status:** four mechanisms specified and tested at object level in the kit (37 cases); all six modeled; the verification step of mechanism 2 run on a small model trained for the purpose on a CPU, with no transfer or timing. Nothing here was measured on a production model or over a network. · **Model:** [`kit/bench/ideas_model.md`](../../kit/bench/ideas_model.md) · **Small-model run:** [`kit/bench/spec_start_toy.md`](../../kit/bench/spec_start_toy.md)

## Summary

| # | Mechanism | Protocol change | Kit cases | Modeled effect | Loses when |
|---|---|---|---|---|---|
| 1 | Fidelity chosen per receiver | A DEMAND carries the receiver's own acceptance; it may tighten the contract's metric bounds, never loosen them | F1–F8 | Three receivers: 2.58 s summed, against 5.36 s if all must be exact on one pinned stack and 37.88 s if exact across stacks | Every receiver needs exact output |
| 2 | Start before the exact state arrives | Layered transfer; output drafted on the coarse layer commits as exact only with a speculation record | P1–P8, plus a small-model run | At most 0.3% slower with an ideal layered code. At the small model's acceptance: 1–25% faster with an 8-bit first layer, 1–5% with a 4-bit one; identical output | The layered code costs extra bytes and acceptance is low: up to 8.1% slower at 10% extra |
| 3 | Compute once, fan out | None: repeaters, shared work keys and signed evidence already exist | C15, C27 (existing) | 64 receivers behind one 10 Gb/s link: one shared copy reaches all in 4.0 s instead of 220 s; one shared recompute costs 1.6 GPU-s instead of 104.5 | One receiver per site |
| 4 | Cancel superseded work | None beyond existing supersession; pushes added to it | C16–C18 (existing), U7, U10 | On an overloaded link: the receiver's state is never more than 13.3 s old, against 50.9 s and growing; 38% fewer bytes | The link keeps up (nothing to skip), or every version must arrive |
| 5 | Trust by proof instead of re-running | Evidence mode `proof`, bound to runtime, input and output | V1–V8 | Checking is 7–64× faster than re-running the generation | The verifier lacks the model, or the proof scheme can be fooled |
| 6 | No round trip for steady pipelines | DEMAND `subscribe`; a PUSH message; a miss falls back to REPAIR | U1–U13 | Between regions, 100 KB per handoff, over 20 handoffs: 2.24 s to 0.56 s | Inside one data center (3 ms saved over 20 handoffs) or large state (2%) |

**Ranking by modeled effect:** fan-out (3) and per-receiver fidelity (1) are the largest, and 3 needs no protocol change. Proof-based trust (5) is large wherever work crosses a trust boundary. Cancelling superseded work (4) matters only when updates outrun the link, as large, frequent weight updates can. Push (6) pays only between regions with small state. Speculative start (2) is the smallest and the most conditional, and it is not new: Lynx (July 2026) does the same for KV-cache transfer.

None of the six patterns is new on its own; the analogs are named in each section. What ARFP adds is that each one is checked against the publisher's signed contract: what a receiver may accept, when drafted output may commit, which evidence counts, and which streams may skip.

## 1. Fidelity chosen per receiver

**Mechanism.** A DEMAND may carry `accept`:
- `bounds`: tighter thresholds for the contract's metric bounds, by predicate id. They set fidelity: how far the output may be from the publisher's reference.
- `classes`: the determinism classes the receiver accepts for its own copy outside free regions. They set reproducibility: E means the copy is the same bytes every time; T and N copies can differ between runs. Work done upstream arrives as hash-checked bytes, so it is E for the receiver whatever its fidelity.
- `free`: whether it accepts generated content in the contract's free regions (default yes).

The receiver can only narrow the publisher's contract. At planning, each node's declared error is compared with the bound that applies to this receiver:
- F1: a receiver that accepts bounded output gets the latent plan, whose declared 0.35 mm error fits the contract's 0.5 mm.
- F2: a receiver that sets the bound to 0 cannot get the latent plan; the literal reference plan is chosen for it instead (1,026 B against 653 B).
- F3: a bound looser than the contract's is rejected.
- F4: a receiver that tightens the bound to 0.4 mm gets an eligible plan (0.35 mm declared), but the composed bound of 0.425 mm fails validation for that receiver only; other receivers still pass at 0.5.
- F5: a receiver that refuses generated content makes a plan with free-region generation ineligible for it.
- F6: a receiver that accepts only E copies cannot decode a latent locally (T), but can take the same decode done at the repeater, which arrives as exact bytes.
- F7: only metric bounds, whose threshold is an upper limit on a distance, can be tightened. A demand that sets 1 mm on the contract's 2 mm minimum clearance would loosen it, and is rejected.
- F8: a node that declares no error is ineligible for a receiver that set its own bound.

**Why it is faster.** With one policy for everyone, the policy has to suit the strictest consumer. The model uses Llama 3.1 8B, 32K context, and links of 400, 10 and 1 Gb/s. Forcing exact state on all three receivers costs 37.88 s summed across different software stacks, or 5.36 s if every receiver runs the sender's pinned stack. Letting each receiver set its own requirement gives 2.58 s: the 400 Gb/s receiver still gets exact state, the 10 Gb/s receiver a compressed cache, and the 1 Gb/s receiver recomputes. The compressed option counts bytes only; encoding and decoding time are not modeled.

**What it costs.** Compressed state is class T: outputs can differ. On the small model in section 2, a 4-bit cache raised the held-out loss by only 0.02 bits per byte (2.598 to 2.620). Greedy text generated on it matched the exact text at only 35% of positions, because one early difference changes everything after it. A 2-bit cache raised the loss by 0.33 bits per byte. CacheGen reports no more than 2% accuracy loss at its compression levels. The contract's predicates still bound what any receiver may accept, so they have to measure something that matters to the application.

**Existing work.** Receivers choosing their own quality is a familiar pattern:
- in receiver-driven layered multicast, each receiver joins as many layers of a stream as its path carries;
- in adaptive streaming such as MPEG-DASH, each client picks the representation it can sustain;
- DDS matches a reader's requested QoS against a writer's offered QoS and reports the pair as incompatible when the request asks for more.

CacheGen chooses its compression level from bandwidth. ARFP applies the pattern to AI state, with the publisher's contract predicates as the outer bounds.

## 2. Start before the exact state arrives

**Mechanism.** The cache is sent in two layers: a coarse layer first, then a refinement that completes the exact cache. The receiver starts generating on the coarse layer while the rest arrives. When the exact cache is complete, one parallel pass checks the drafted tokens. The matching prefix is kept, plus the exact model's token at the first mismatch, and decoding continues on the exact cache. In exact arithmetic the final output is identical to decoding on the exact cache from the start; in floating point that also takes batch-invariant kernels (see the small-model run).

The commit rule depends on what the receiver accepts:
- A receiver that requires exact output may commit drafted output only with a `speculation` record. The record names the plan, both states, the draft, the verified prefix length and the final output. The receiver's checker recomputes the verification (P1).
- Committing without a record is rejected for a receiver that did not opt in, even when the coarse layer's declared error is in range (P2).
- A record is rejected if it names another exact state (P3), overstates the verified prefix (P4), or names another plan, provisional state or draft, or if the committed output is not the verified one (P8).
- A receiver that accepts class T may use the draft without waiting, but only if the contract lets T-class evidence transfer and the coarse layer declares an error within the contract's bound (P5). A coarse layer whose declared error exceeds the bound is rejected even for a receiver that opted in (P6), and so is any unverified use under a contract that accepts no T-class evidence (P7). This is mechanism 1 applied to the coarse layer.

**Run on a small model.** A byte-level transformer with 841,984 parameters was trained on a CPU for about 15 minutes. The repository's preserved original documents (163,022 bytes, pinned by their digests in the manifest) were split into the first 80% (130,417 bytes) for training and the rest for testing. On 200 non-overlapping held-out prompts, it drafted 48 tokens on a quantized cache and verified them against the exact one:

| Cache precision | Size vs 16-bit, with scales | Per-token acceptance | Mean tokens kept (of 48) | Final output identical to exact |
|---|---|---|---|---|
| 8-bit | 1.92× smaller | 0.998 | 45.0 | 200/200 |
| 6-bit | 2.53× smaller | 0.992 | 37.0 | 200/200 |
| 4-bit | 3.69× smaller | 0.942 | 13.8 | 200/200 |
| 3-bit | 4.8× smaller | 0.843 | 5.2 | 200/200 |
| 2-bit | 6.86× smaller | 0.364 | 0.6 | 200/200 |

This tests the verification step only: no transfer and no timing. The final output matched exact decoding in all 200 cases at every precision, but not by construction. On the exact path, the one-pass check and step-by-step decoding gave logits that differed at all 9,400 positions compared, by up to 7.2e-5, because matrix products of different shapes add in a different order. No greedy choice flipped, but the closest call had a gap of only 3.3e-4 between the top two logits. Exact output therefore needs batch-invariant kernels, on a CPU as on a GPU; with default GPU kernels, Thinking Machines got 80 different completions out of 1,000 at temperature 0. Acceptance on production models has to be measured there. QuantSpec reports above 90% for a draft that uses a 4-bit cache and 4-bit weights.

**Modeled gain** (Llama 3.1 8B, 256-token response). The gain is the decode work done while the exact cache is still arriving, so it depends on how long drafts survive:
- **At the small model's acceptance:**
  - An 8-bit first layer (half size, 0.998 per token) saves 1–25% across 8K–128K contexts and 10–100 Gb/s links.
  - A 4-bit first layer (quarter size, 0.942) saves only 1–5%: it arrives sooner, but its drafts die sooner.
  - Example, 32K context at 10 Gb/s: the exact path takes 5.66 s; speculating on the 8-bit layer takes 4.27 s and on the 4-bit layer 5.52 s.
- **At other acceptances** (quarter-size layer, same 32K, 10 Gb/s case): saves 1% at 0.90, 3% at 0.95, 14% at 0.99 and 34% at 0.999.
- **When it loses.** With an ideal layered code (coarse layer plus refinement no larger than the exact cache), the only extra cost is the verification pass. At acceptance 0 it keeps a single exact token, and at 128K context the pass takes longer than one decode step: at most 0.3% (30 ms) slower. If the layered code costs 10% more bytes than a direct exact transfer, low acceptance makes it slower: up to 8.1% at acceptance 0, and 7% for the 4-bit layer at 128K over 10 Gb/s at the small model's acceptance.
- **Independence.** The model treats per-token acceptance as independent; real mismatches cluster by prompt. On the small model with a 4-bit cache, the median draft kept 4 tokens and 16% were kept whole. Independent acceptance at the same average would give a median of 12 and 6% kept whole. These savings are first-order.

Accepting the coarse cache outright (mechanism 1) is faster still: 3.08 s instead of 5.66 s in the example, but the output can differ.

**Existing work.** Lynx (July 2026) does this for KV-cache transfer:
- It splits the cache into a high-priority stream carrying its most significant bits and a lower-priority residual stream with the rest.
- It decodes speculatively once the first stream arrives, while the residual stream is still in transit, then verifies. The authors say verification "ensures equivalence to higher-precision decoding".
- They report time to first token up to 1.43× better than standard 8-bit KV quantization.

QuantSpec uses a quantized cache as the draft to speed up decoding itself. ARFP adds only the protocol side: the speculation record that lets a receiver requiring exact output commit drafted tokens, and the contract permission that governs unverified use.

## 3. Compute once, fan out

**Mechanism.** No protocol change. A repeater at the receivers' site fetches or computes shared state once, and holders re-forward it inside the site. Shared work keys let several receivers depend on one computation (C15). The repeater's signed evidence travels with the state, so receivers need not re-verify against the origin (C27).

**Modeled gain.** 64 receivers at a remote site need the same 32K-token cache (4.29 GB) behind one shared 10 Gb/s link:

| Strategy | Last receiver has it | GPU-seconds |
|---|---|---|
| Origin sends each copy | 220 s | 0 |
| Each receiver recomputes | 1.6 s | 104.5 |
| One copy over the link, then forwarded inside the site at 400 Gb/s | 4.0 s | 0 |
| One recompute at the site, then forwarded | 2.2 s | 1.6 |

Against the origin sending each copy, fan-out is more than 50 times faster. Against every receiver recomputing, it is slightly slower to the last receiver (2.2 s against 1.6 s) but spends one sixty-fourth of the GPU time. With one receiver per site, the repeater only adds a hop.

**Existing work.** Shared KV-cache stores exist inside clusters (Mooncake, LMCache). Across sites and operators, with evidence a receiver can check, is the open part.

## 4. Cancel superseded work

**Mechanism.** Replaceable streams may skip superseded versions; required-transition streams may not (C17). Existing cases cover cancellation that keeps shared work alive (C15, C16) and late results for a superseded demand (C18). For pushes:
- U7: an older push arriving after a newer one on a replaceable stream is dropped.
- U10: a gap on a required-transition stream is rejected even when the contract grants that stream a fast path.

**Modeled gain.** A 16 GB state (Llama 3.1 8B weights, the shape of an RL weight update) gets a new version every 3 s for a minute. The model compares two links:
- **25 Gb/s, where the link cannot keep up.** A copy takes 5.1 s, so the link is loaded to 171% by design: this is the case the mechanism is for.
  - Delivering every version in order falls further behind with each one. The version made at 60 s arrives at 108 s, 47.9 s late. Just before each arrival, the receiver's newest state is up to 50.9 s old, and both figures keep growing.
  - Skipping to the newest version sends 13 of 21 versions (38% fewer bytes). Each arrives at most 8.1 s after it was made, and the receiver's state is never more than 13.3 s old.
- **100 Gb/s, where the link keeps up** (1.3 s per copy). Both policies send every version, and skipping saves nothing.

**Existing work.** Keeping only the latest value is standard in publish/subscribe systems: DDS with a KEEP_LAST history of depth 1, and Kafka's compacted topics, which guarantee "that the latest value for each message key is always retained". ARFP's addition is that the publisher's contract says which streams may skip and which must arrive in order, and the receiver enforces it.

## 5. Trust by proof instead of re-running

**Mechanism.** Evidence may carry a `proof`: a scheme name, the runtime (model) digest, the input digest and the proof data. The verifier first runs the usual evidence checks, then one recomputation pass. Everything that can be rejected without computing is rejected first:
- V1: a valid proof from an untrusted worker is accepted after one recomputation pass with simulated hardware noise; the generation is not repeated.
- V2: a worker that ran a different model but claims the contracted one is caught by the recomputation pass.
- V3: a proof made for a different input is rejected before any recomputation.
- V4: a contract that does not list the `proof` mode rejects proof evidence.
- V5: proof bytes edited after signing fail the worker's signature.
- V6: a proof that names a runtime other than the plan's is rejected before any recomputation.
- V7: proof evidence older than the contract's maximum age is rejected before any recomputation.
- V8: evidence that names a checker other than its signer, reports a failed check, or uses an unsupported proof scheme is rejected before any recomputation.

The kit uses a toy scheme in the spirit of TOPLOC, which fingerprints the top values of hidden activations and tolerates small numeric differences.

**Why it is faster.** Re-running repeats the generation one token at a time. Checking needs one parallel pass over the prompt and the generated tokens, which are already known. For an 8K-token prompt on Llama 3.1 8B, re-running takes 2.2–30.7 s for 256–4,096 generated tokens; the check takes 0.31–0.48 s, 7–64× faster. The proof is 2–33 KB at TOPLOC's 258 bytes per 32 tokens.

The speedup comes from the parallel pass, not from the proof: a verifier that recomputes the claimed tokens in one pass is just as fast. The proof adds three things:
- tolerance for numeric differences across hardware;
- binding to the runtime and the input;
- a compact record that a third party can check later.

TOPLOC reports that validation is "significantly faster than the original inference"; the 7–64× figure is our model, not theirs.

**Limits.** A proof shows the claimed model produced the output. It says nothing about whether the output is good; the contract still decides that. The verifier needs the model and a GPU.

## 6. No round trip for steady pipelines

**Mechanism.** A DEMAND with `subscribe` opens a standing subscription. Later revisions arrive as a PUSH, with no OFFER or ACCEPT. A PUSH carries:
- the stream and sequence number;
- the target;
- the publisher's signed binding for that revision;
- the plan;
- the base it assumes;
- the payload chunks.

The subscription keeps the subscriber's own acceptance, and the receiver checks each push without a round trip:
- **Accepted.** U1: the binding passes gate zero against the cached contract template, the plan is a same-shape child of the subscribed plan, and the pushed bytes match it.
- **Gate zero.** A forged signature (U4) and a binding for a different target (U9) are rejected.
- **Contract.** A binding under a template outside the subscription, a plan bound to another revision's contract, and a stream the revision's contract does not define are rejected (U13).
- **Plan.** A stream the contract gives no fast path (U5) and a plan that changes shape (U6) need full OFFER/ACCEPT. A plan the subscriber's own acceptance rules out is rejected, as it would be when negotiated (U12).
- **Bytes.** Pushed bytes must match their digest (U8), and the digest must be the plan's (U11).
- **Order.** An older push after a newer one is dropped (U7); a gap on a required-transition stream is rejected (U10).
- **Fallback.** A push to a receiver with no subscription is refused (U3). A push that assumes a base the receiver does not hold gets a REPAIR, which costs a round trip (U2).

**Size.** In the kit a PUSH is 2,622 bytes for 653 bytes of payload. Of the 1,969 bytes of overhead, the inline plan is 1,210 B and the signed binding 438 B. The speed review's push profile aims for a frame of about 128 bytes. That needs the plan sent by reference and shorter references for digests; neither is specified yet.

**Modeled gain.** The baseline is ARFP's own negotiation (DEMAND, OFFER, ACCEPT, then payload), which costs about two round trips per handoff. A push costs half of one. Over 20 handoffs:
- Small state (100 KB) between regions (56 ms round trip): 2.24 s falls to 0.56 s.
- Inside one data center (assumed 0.1 ms): 5.6 ms falls to 2.6 ms, which rarely matters.
- For multi-gigabyte state, the transfer dominates and push saves about 2%.

## What would test these on real systems

- **Mechanisms 1 and 2:** the [AI-state network test](ARFP-ai-state-handoff-network-test.md), with per-receiver acceptance and speculative start added as strategies. Its A2 and A3 hypotheses cover the per-receiver gain. Add acceptance for 8-bit and 4-bit first layers on the production model, with Lynx as the baseline for speculative start.
- **Mechanism 5:** replace the toy scheme with a real proof-of-inference scheme. Measure validation time against re-running, and false accepts under the V2–V8 attacks.
- **Mechanism 3:** a two-site test with a repeater, counting bytes on every link and GPU-seconds, against per-receiver fetch and per-receiver recompute.

## Sources

- Speed review [§6](../analysis/ARFP-internet-speed-review.md#6-ai-to-ai-state-where-the-planner-already-pays) and its [research notes](../research/speed-review/ai_infrastructure_state_transfer.md): KV-cache sizes, the three-receiver model, CacheGen, Mooncake, LMCache, Thinking Machines.
- [Lynx: Progressive Speculative Quantization for accelerating KV Transfer in Long-Context Inference](https://arxiv.org/abs/2607.01831) (arXiv, 2 July 2026): anchor and residual streams; verification that "ensures equivalence to higher-precision decoding"; time to first token up to 1.43× better than standard 8-bit KV quantization.
- [QuantSpec: Self-Speculative Decoding with Hierarchical Quantized KV Cache](https://arxiv.org/abs/2502.10424) (ICML 2025): "high acceptance rates (>90%)".
- [Fast Inference from Transformers via Speculative Decoding](https://arxiv.org/abs/2211.17192): identical outputs, 2–3× on T5-XXL.
- [TOPLOC](https://arxiv.org/abs/2501.16007) (ICML 2025): 258 bytes per 32 tokens; validation "significantly faster than the original inference".
- [Receiver-driven Layered Multicast](https://infoscience.epfl.ch/record/34141) (McCanne, Jacobson and Vetterli, SIGCOMM 1996).
- DDS requested-versus-offered QoS: [RTI Connext, `RequestedIncompatibleQosStatus`](https://community.rti.com/docs/html/api_cpp/structDDS__RequestedIncompatibleQosStatus.html).
- [Kafka log compaction](https://docs.confluent.io/kafka/design/log_compaction.html): "the latest value for each message key is always retained".
- H100 SXM memory bandwidth (3.35 TB/s), from the speed-review research notes.
