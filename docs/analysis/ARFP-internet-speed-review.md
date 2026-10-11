# ARFP internet speed review

**Question:** can ARFP's transfer set (literal bytes, references, deltas, procedural recipes, latents, residuals, recompute, upstream decode) deliver a usable, validated result faster than today's internet stack? If so, where, and what would the design have to look like?
**Date:** 2026-10-11 · **Concept author:** Dino Silvestri · **Companion to:** [ARFP-analysis-2026-10-11.md](ARFP-analysis-2026-10-11.md) (the working record) · **Kit paths** (`bench/…`, `run_checks.py`) are relative to [`kit/`](../../kit/) · **Research notes:** [`docs/research/speed-review/`](../research/speed-review/)

**Evidence labels.**
- **Measured:** run in the kit. `bench/delta_bench.py` ran on real npm releases (sizes, plus timings on this machine); ARFP message sizes come from `run_checks.py`.
- **Sourced:** published figures, linked; lab or production is noted.
- **Modeled:** computed by `bench/speed_model.py` from the measured sizes and sourced constants.
- **Judgment:** my assessment.

Nothing here is a network measurement. The model is first-order: no packet loss, no server think time, no queueing.

**Verification.** A separate agent that had not seen the work checked an earlier draft:
- every number against the kit's outputs, recomputing the model independently;
- every sourced claim against the verbatim quotes in the research notes;
- 11 of the load-bearing claims against the original pages.

It found two errors and twenty smaller issues, and this version addresses them. The errors:
- A "novel content" example that was really a re-indentation.
- A transfer figure that was measured over NVLink, not a network.

The smaller issues included two modeling biases, both now corrected:
- slow-start transfer time was double-counted;
- ARFP's own hash check was left uncounted.

A second pass confirmed the fixes. It caught one more design error, a hashing fix that could not work for deltas, now corrected (§5 item 3, §7 row 5).

---

## 0. Bottom line

**Yes for specific transfers, no for "the internet" in general.** The transfer set can make a transfer much faster when two things hold:
- the receiver already holds most of what it needs (an earlier version, a cache, a model);
- the transfer is big enough, or the link slow enough, that bytes rather than round trips decide the time.

It cannot beat the speed of light or remove round trips the application needs. Typical web page loads are limited by round trips and CPU, not bytes.

**The lever is real, and it's the one information theory points at.** Measured here on real releases, a receiver holding the previous version needs:

| Workload | Fewer bytes than brotli |
|---|---|
| three.js updates | 18–190× (median 75×) |
| TypeScript patch releases | 560–1,117× |

The more the receiver already knows (Y), the less has to cross the wire: H(X|Y). One release that re-indented most of its file defeated the generic delta (1.7×). Coding indentation and text separately improved that to 8.1×, which is the lesson Google's Courgette taught in 2009: a transform that understands the content beats a generic diff.

**The web already has that lever, and ARFP v0.1 mostly loses to it.**
- RFC 9842 compression dictionaries (Sept 2025) deliver the same delta. The client names the dictionary it holds in a header on the ordinary request, so using it adds no round trip.
- ARFP v0.1 waits for OFFER then ACCEPT, which adds one. At 100 Mbit/s, a warm connection and a 56 ms RTT, a three.js update takes:

| Path | Time (modeled) |
|---|---|
| RFC 9842 dictionary | 56 ms |
| ARFP v0.1 negotiated | 113 ms |
| Plain HTTP, whole file | 74 ms |

- On a cold or slow connection the negotiated path still beats the whole file (113 vs 234 ms).
- The v0.1 fast path ties RFC 9842 on a 1.2 MB file. On a 9 MB file it trails by 12% (64 vs 57 ms), because the ARFP rows check the output's hash and the HTTP rows don't. A page using Subresource Integrity would pay the same cost.

**The rule that decides faster or slower.** Spend a round trip only when it saves more bytes than bandwidth × RTT: 700 KB at 100 Mbit/s and 56 ms, 70 KB at 10 Mbit/s. So the common path must add no round trips:
- push on a standing subscription;
- send references and deltas in one flight;
- pay an extra round trip only on a miss.

Bitcoin's compact blocks deployed exactly this in 2016: 0.5 RTT best case, 1.5 RTT on a miss.

**Where ARFP could beat the best existing stack: not on deltas (at best a tie), but on what nothing else combines.**
- Choosing per receiver among sending bytes, deltas, recipes, latents or the inputs to recompute.
- Decoding upstream for weak receivers.
- Cancelling superseded work.
- Accepting approximate or generated reconstruction under a checkable contract, with labels.

**The clearest live case is AI state.** Whether to send a KV cache, a compressed cache, or the text to recompute flips inside real link ranges. Modeled break-even, per H100 of receiver compute:
- 4–29 Gb/s for an uncompressed cache;
- 1–7 Gb/s with a ~4× codec;
- higher for a receiver with more GPUs behind one link.

In a three-receiver model:
- Choosing per receiver halved the summed completion time against the best single fixed strategy (2.51 vs 4.90 s). All of it came from sending a lossy, class-T compressed cache to the two fast-link receivers; the slowest receiver gained nothing.
- If the contract demands exact results and the receivers run different software stacks, shipping the full cache is the only exact option modeled, and the total is 15× the adaptive one.

The contract, not just the network, sets the speed.

**The biggest aggregate lever is video.** It was about 65% of internet traffic (2022 data) and about 75% of mobile traffic at the end of 2025. The deployed analog, AV1 film grain synthesis, sends parameters and lets the decoder generate the grain; it cut average bitrate 31.6% in Netflix's production A/B test. Netflix's ~300-title analysis found 36% at 1080p and above and about 10% below. Expect up to tens of percent on grainy high-resolution content, not orders of magnitude.

**On "this will change the way the internet works":** nothing measured supports it yet. A narrower claim is defensible and testable: *ARFP makes approximate and generated reconstruction checkable, and its planner beats any fixed transfer strategy when receivers differ.* Stage 4/5 should test that claim, against HTTP/3 with RFC 9842 as the baseline.

---

## 1. What "faster" is made of

```
time to a validated result =
    round trips × RTT                      (handshakes, requests, negotiation, slow start on cold connections)
  + bytes ÷ bandwidth                      (serialization)
  + receiver compute                       (decode, reconstruct, recompute)
  + validation                             (hash, metric checks, invariants)
  + P(miss or failure) × repair cost
```

**Floors no protocol beats.**
- **Bits:** the conditional entropy H(X|Y), or the conditional rate–distortion function for approximate results (working record §1).
- **Latency:** light in fiber travels at about 200,000 km/s, so New York to London is at least 56 ms round trip ([HPBN][hpbn-latency]).
- **Compute:** the receiver's decode throughput.

**The modern stack has already pulled two of the three big levers.**
- **Round trips.** Before the first request byte, TCP + TLS 1.2 needs 3 round trips, TCP + TLS 1.3 needs 2, QUIC needs 1, and QUIC 0-RTT resumption needs none ([HPBN][hpbn-tls], [RFC 9000][rfc9000], [RFC 9001][rfc9001], [RFC 8446][rfc8446]). 0-RTT data can be replayed, so it is limited to safe requests; HTTP has a "425 Too Early" status for this ([RFC 8470][rfc8470]).
- **Bytes per object:** brotli and zstd, AV1, and now dictionaries ([RFC 9842][rfc9842]).
- **Distance:** CDNs.

**The under-used lever is receiver-side state.** Receivers hold caches and earlier versions. Increasingly they hold large shared models too:
- Apple ships a ~3B-parameter on-device model with a developer framework ([Apple 2025][apple-fm]).
- Gemini Nano can be called by third-party apps through ML Kit on Android ([ML Kit GenAI][mlkit-genai]) and by web pages through Chrome's built-in AI APIs ([Chrome][chrome-ai]).

That lever is ARFP's lane. A protocol that lets senders exploit receiver state *safely* is the contribution. Exploiting it carelessly is easy, and it is how generated content gets passed off as the real thing.

**"Faster internet" has two meanings.**
- **Per-transfer latency:** what a user feels. Fewer bytes per session can also mean fewer stalls: Netflix's grain-synthesis A/B test reported 10% fewer rebuffers in the treated sessions ([Netflix][netflix-fgs]).
- **Aggregate load:** fewer bytes on shared links means less congestion for everyone. No source found here measures that effect for these techniques.

---

## 2. Where the time goes today

| Regime | Size | What limits it | Evidence |
|---|---|---|---|
| Web page loads | Median home page 2,559 KB mobile / 2,862 KB desktop; 75 / 80 requests ([Web Almanac 2025][almanac]) | Round trips and client CPU, above about 5 Mbit/s | See below |
| Video | ~65% of all internet traffic, 2022 data ([Sandvine, Jan 2023][sandvine2023]); ~75% of mobile data traffic, end of 2025 ([Ericsson, June 2026][ericsson]) | Sustained throughput; codec efficiency | The Sandvine figure is dated; no newer primary percentage was found |
| AI datacenter state | KV cache 128 KiB per token (Llama 3.1 8B) to 320 KiB (70B), derived from [Meta's configs][llama-models]; 42.9 GB (40 GiB) for 128K tokens on 70B, which [Mooncake][mooncake-repo] cites as "40 GB" | Link bandwidth vs. recompute | Mooncake's transfer engine reports up to 87 GB/s on 4×200 Gb/s and up to 190 GB/s on 8×400 Gb/s |

Evidence for the web row:
- **Lab:** [Belshe 2010][belshe] simulated 25 popular pages. Going from 5 to 10 Mbit/s cut page load time by 5%. With bandwidth fixed at 5 Mbit/s, every 20 ms cut from RTT cut it by 7–15%. Pages used only about 16% of a 10 Mbit/s link.
- **Lab:** [WProf, NSDI 2013][wprof] found computation was up to 35% of the critical path, on 150 sites at 10 Mbit/s.
- **Lab counterpoint:** a [2025 Montana State / Akamai study][msu2025] found 18% of 45 popular pages primarily bandwidth-limited, on emulated links.
- **Production:** at [Google Search][search-dict], a dictionary cut HTML bytes 23% versus brotli, but LCP improved only 1.7% overall (up to 9% on high-latency networks).

**The ceiling on any byte-saving scheme (Amdahl).** If a fraction f of the time is spent moving bytes and the bytes shrink k-fold, speedup = 1 / ((1 − f) + f/k).

| Byte-bound share f | k = 10 | k = 100 | Limit |
|---|---|---|---|
| 10% | 1.10× | 1.11× | 1.11× |
| 30% | 1.37× | 1.42× | 1.43× |
| 90% | 5.26× | 9.17× | 10× |
| 99% | 9.17× | 50.25× | 100× |

Google Search's numbers imply the HTML-byte-sensitive part of LCP was about 7% overall and up to about 39% on high-latency networks, where saved slow-start round trips probably account for much of it. This is a back-of-envelope estimate (§7 of the model output), and a lower bound for all bytes, since only the HTML shrank.

**Conclusion.** Byte savings move the needle in a few places:
- big transfers and slow links;
- cold connections, where saved bytes also save slow-start round trips;
- video and AI state.

They barely move typical web pages.

---

## 3. The transfer set, mode by mode

| Mode | What crosses the wire | Receiver must hold | Wins when | Deployed or published precedent (best figure found) | Class | What ARFP adds |
|---|---|---|---|---|---|---|
| Literal | The bytes | Nothing | Content is novel or tiny | Everything today | E | — |
| Reference | An ID | The object | Hit rate is high and asking costs nothing | HTTP caching. [BIP 152][bip152] compact blocks: 6-byte IDs; about 90% of blocks needed no extra round trip in informal 2016 tests. Mooncake hash-based KV prefix reuse ([repo][mooncake-repo]) | E | Binding of every reference to a signed contract |
| Delta | Edits against an exact base | The exact base | Small change to a big object | [RFC 9842][rfc9842]: in Cloudflare's lab a 272 KB JS file was 92.2 KB with gzip and 2.6 KB as a delta ([Cloudflare][cf-dict]). [Courgette][courgette]: 10.4 MB update → 79 KB. [LoRA][lora] fine-tunes of GPT-3 175B ship a 35 MB checkpoint instead of 350 GB (a different fine-tuning method, applied on an exact base) | E (lossy weight deltas such as [BitDelta][bitdelta] are T) | The base must be exact, enforced (C03, R6) |
| Procedural recipe | A program, seed or command list | A deterministic generator | Output ≫ recipe and the generator is pinned | [Age of Empires][aoe]: only player commands per 200 ms turn, over 28.8k modems; passing state "would have limited us to 250 moving units". [AV1 film grain][av1-conformance] | E only when pinned; otherwise T or N | Determinism class, vectors, output hashes |
| Latent | A code for a model | The model | The model predicts the content well and the receiver has compute | [face-vid2vid][facevid2vid]: H.264 quality at one-tenth the bandwidth (lab). [Gemino][gemino]: 2.2–5× below VP8/VP9 at ~100 Kbps (lab). [PiCA][pica]: 256 latent values per frame | T or N | Contract, plus labels on generated regions |
| Residual | A correction over an approximate result | The approximate result, held exactly | The approximation is shared byte for byte | Gemino sends an exact VP8/VP9 base layer and generates the detail on top | Base must be E | Refuses residuals on T-class bases (R6) |
| Recompute | The inputs (e.g. prompt text) | Model plus compute | The link is slow relative to compute | [CacheGen][cachegen] sends text when bandwidth is too low. [Mooncake][mooncake] chooses recompute vs fetch by prefix-match length | N by default ([TML][tml]). E only with batch-invariant kernels on the sender's exact pinned stack, at ~1.6–2.1× the time in one decode-heavy benchmark | Class-aware planning (§6) |
| Upstream decode | Decoded bytes from a nearer node | Nothing | Weak receiver, strong edge | [DistServe][distserve] and [Splitwise][splitwise] split prefill and decode across GPUs or machines. ARFP R3 | E downstream | Evidence that survives the hop (C27) |
| Provisional | Nothing yet | A predictor | Interaction latency matters | [Valve][valve-pred]: the client predicts the local player's actions and re-simulates when the server disagrees | N, labeled provisional | Milestones and free regions |

**What the precedents share.** Most hard-wire one mode. CacheGen and Mooncake choose between two (cached state or recompute), under one implicit trust assumption. None spans all modes or declares determinism classes.

**Labeling.** None of the sources found labels generated output for the person using it:
- AV1 signals synthetic grain in-band but leaves the fidelity bound outside the spec. "Perceptually significant differences" "may be specified, for example, by a service provider as part of their accreditation program" ([AV1 spec source][av1-conformance]).
- RTX Video Super Resolution generates detail at the receiver with no signal at all ([NVIDIA][rtx-vsr]).

**Determinism.** Lockstep games showed what happens without it. Age of Empires stopped the game on any out-of-sync checksum. Its developers wrote that "very subtle differences would multiply over time", and they debugged them with 50 MB message traces ([Game Developer][aoe]).

That gap, a contract plus classes plus labels across all modes, is what ARFP fills.

---

## 4. Measured: what receiver state is worth in bytes

**Method.** Files and SHA-256 hashes for every release are in `bench/delta_results.json`.
- Real npm releases.
- **Delta:** zstd 1.5.6 level 19 in patch-from mode. Release N−1 is a raw prefix the decoder also holds, which is the raw-dictionary mechanism behind RFC 9842's `dcz` encoding. Long-distance matching was tried on and off. Every delta was verified by decoding.
- **Fast delta:** the same at level 3.
- **Content-aware delta:** indentation and line text coded as two streams, each delta-coded against the old release's streams (lossless, verified).
- **No-state baseline:** brotli quality 11 with the default window.
- **Timings:** on a 2.1 GHz Xeon. Decode and SHA-256 times are single-threaded medians of 5 runs; encode times are single runs of the better long-distance-matching setting.

| Workload | File size | Brotli | Delta from previous release | Fewer bytes than brotli |
|---|---|---|---|---|
| react-dom 18.0 → 18.3.1 (4 updates) | 132 KB | 36.8–36.9 KB | 63 B – 8.8 KB | 4.2× – 584× (median 9×) |
| three.js r150 → r160 (10 updates) | 1.2–1.3 MB | 190–201 KB | 1.0 – 10.7 KB | 17.8× – 189.6× (median 75×) |
| TypeScript 5.4.2 → 5.4.5 (3 patches) | 9.1 MB | 1.08 MB | 968 B – 1.9 KB | 560× – 1,117× |
| TypeScript 5.5.2 → 5.6.2 (minor) | 8.9 MB | 1.13 MB | 35 KB | 32× |
| **TypeScript 5.4.5 → 5.5.2 (minor, re-indented)** | 8.9 MB | 1.12 MB | **653 KB generic; 138 KB content-aware** | **1.7× generic; 8.1× content-aware** |

**Three things this shows.**

1. **The gain depends on knowing the exact base.** If the receiver still holds r150 when r160 ships, the delta is 15.8% of brotli instead of a median 1.3% for adjacent releases. That is still 6× smaller than brotli, but about 12× the typical adjacent-release delta. Accurate, current STATE is worth a lot.

2. **A mechanical rewrite defeats a generic delta, and a content-aware transform recovers much of it.**
   - In TypeScript 5.5, only 11.6% of the new file's bytes sat in lines found verbatim in 5.4.5, but 90.6% did once indentation is ignored. The release mostly re-indented the code.
   - The generic delta saved just 42% against brotli (653 KB).
   - Coding indentation and text separately brought it to 138 KB: 8.1× smaller than brotli and 4.7× smaller than the generic delta.

   That is a large improvement, though still far from the next minor release's 32×. Courgette made the same point: a transform that understands the content beat bsdiff by about 9× ([Chromium blog][courgette]). This is an argument for per-profile transforms in ARFP. Genuinely novel content, where H(X|Y) ≈ H(X), wasn't in this sample, and the benchmark still needs it.

3. **The receiver's cost is small. The sender's is large but reusable, or small if it accepts a bigger delta.**
   - **Decoding:** a delta takes 0.11–0.19 ms for three.js and 0.8–5.4 ms for TypeScript, against 2.3–3.1 ms and 13.6–16.2 ms to decode the brotli files.
   - **Encoding at level 19:** 0.2–0.3 s per three.js pair and 2.7–9.1 s per TypeScript pair, once per (base, target) pair, and cacheable.
   - **Encoding at level 3:** about two orders of magnitude faster (2.5–3.5 ms for three.js; 14–20 ms for TypeScript patch and minor releases, 62 ms on the re-indented one), for deltas 1.3–2× larger. On the re-indented release it fails outright: 1.38 MB, bigger than brotli. A sender encoding at event time therefore needs a fallback, which ARFP's prebound fallbacks provide.
   - **Hashing:** SHA-256 of the output, ARFP's end-to-end check, takes 0.8–1.0 ms for three.js (1.2 MB) and 7.0–8.3 ms for TypeScript (9 MB), about 1.1–1.6 GB/s on this CPU.

These are compression measurements only. Section 5 turns them into time.

---

## 5. From bytes to time

**Model** (`bench/speed_model.py`).
- **Pull.** A request costs one round trip per flight, plus the sending time of the last flight; earlier flights' sending time overlaps their round trips.
  - On a cold connection, slow start sends 14.6 KB in the first flight ([RFC 6928][rfc6928] initial window) and doubles each round trip until the pipe is full.
  - The connection handshake is *not* included. Add 1 RTT to every cold cell for QUIC, or 2 for TCP + TLS 1.3.
  - A warm connection sends in one flight.
- **Push.** The one-way delay, then a round trip per further flight.
- **RTT:** 56 ms throughout, the New York–London fiber floor.
- **Dictionary rows** carry `dcz`'s 40-byte header.
- **ARFP rows** include the SHA-256 check of the output, measured on this CPU. The HTTP rows do no end-to-end check (a page using Subresource Integrity would pay the same cost).
- **ARFP control bytes** come from the kit:

| Path | Control bytes |
|---|---|
| Negotiated | OFFER 1,633 B, then a 195 B payload envelope |
| Fast path | 1,079 B, measured for a one-node plan |
| Proposed push frame | 128 B (a design target, not measured) |

**Pull: the receiver asks for a three.js update** (r156 → r157; brotli 194,172 B, delta 2,559 B, output 1.2 MB). Times in ms:

| Flow | 10 Mbit/s cold | 100 Mbit/s cold | 100 Mbit/s warm | 1 Gbit/s warm |
|---|---|---|---|---|
| HTTP, whole file | 299.9 | 233.7 | 73.9 | 59.9 |
| HTTP + RFC 9842 dictionary | 58.2 | 56.3 | 56.3 | 56.2 |
| ARFP v0.1 negotiated | 116.4 | 113.3 | 113.3 | 113.0 |
| ARFP v0.1 fast path | 59.8 | 57.2 | 57.2 | 56.9 |

**Pull: a TypeScript patch** (5.4.4 → 5.4.5; brotli 1,081,641 B, delta 968 B, output 9.1 MB). Times in ms:

| Flow | 10 Mbit/s cold | 100 Mbit/s cold | 100 Mbit/s warm | 1 Gbit/s warm |
|---|---|---|---|---|
| HTTP, whole file | 1,022.1 | 419.5 | 157.1 | 79.2 |
| HTTP + RFC 9842 dictionary | 57.7 | 57.0 | 57.0 | 56.9 |
| ARFP v0.1 negotiated | 122.1 | 120.1 | 120.1 | 119.9 |
| ARFP v0.1 fast path | 65.5 | 64.0 | 64.0 | 63.9 |

**Push: the publisher has the three.js update and the receiver is subscribed.** Time from the publisher's event to a validated result, in ms. The model assumes the publisher knows the receiver's base; a miss adds one round trip.

| Flow | 10 Mbit/s cold | 100 Mbit/s cold | 100 Mbit/s warm | 1 Gbit/s warm |
|---|---|---|---|---|
| Notify, then HTTP fetch of whole file | 327.9 | 261.7 | 101.9 | 87.9 |
| Notify, then HTTP fetch with dictionary | 86.2 | 84.3 | 84.3 | 84.2 |
| Push whole file | 271.9 | 205.7 | 45.9 | 31.9 |
| Push delta over any pub/sub channel | 30.2 | 28.3 | 28.3 | 28.2 |
| ARFP push profile (pre-encoded delta, hash check) | 31.1 | 29.1 | 29.1 | 28.9 |
| ARFP push, delta encoded at the event, zstd -3 | 35.4 | 32.1 | 32.1 | 31.8 |
| ARFP push, delta encoded at the event, zstd -19 | 260.9 | 258.9 | 258.9 | 258.7 |

**If the delta is encoded only at the event** (three.js and TypeScript, 100 Mbit/s warm, ms). Notify-then-fetch can encode during its own round trip:

| Flow | three.js, zstd -3 | three.js, zstd -19 | TypeScript, zstd -3 | TypeScript, zstd -19 |
|---|---|---|---|---|
| Notify, then fetch with dictionary | 84.5 | 258.1 | 84.9 | 2,844.7 |
| Push delta over any pub/sub channel | 31.3 | 258.1 | 43.0 | 2,844.7 |
| ARFP push profile (hash check) | 32.1 | 258.9 | 50.0 | 2,851.7 |

**What the tables say.**

1. **Deltas pay most on cold connections and slow links.**
   - three.js at 100 Mbit/s cold: 234 → 56 ms (four flights become one).
   - TypeScript at 10 Mbit/s cold: 1.02 s → 58 ms.
   - Counting a QUIC handshake on both sides, the three.js case is 290 vs 112 ms: 2.6× rather than 4.2×.
2. **On warm, fast links the gain is one serialization time** (74 → 56 ms), and one added round trip erases it. ARFP v0.1 negotiated takes 113 ms, slower than sending the whole file. On cold or slow links it still wins (113 vs 234 ms).
3. **The fast path ties RFC 9842 on a 1.2 MB file** (57.2 vs 56.3 ms) **and trails by 12% on a 9 MB one** (64.0 vs 57.0 ms), because the ARFP rows hash the output. That is the price of end-to-end verification, and overlapping the hash with arrival can't hide it for a delta: the 9 MB output only exists after local decoding.
   - **What works:** a chunked tree hash in which chunks copied unchanged from the already-verified base keep their digests, so only changed chunks are hashed.
   - **Cost:** about 0.15 ms for three 64 KB chunks at the measured rate (hand arithmetic, not computed by `bench/speed_model.py`).
   - **Requirements:** content-defined chunk boundaries, so an insertion doesn't shift every chunk, and a delta format that records which chunks were copied.
4. **Push beats notify-then-fetch by about a round trip on subscribed streams** (28 vs 84 ms; both clocks start at the publisher's event), but only when the delta is ready within about one round trip of the event. With level-19 encoding at the event, every delta path takes about 258 ms (three.js) or 2.85 s (TypeScript). Any pub/sub channel carrying dictionary deltas gets the same 28 ms.
   - ARFP's push profile matches it within 1 ms for three.js, and trails by 7 ms (24%) for TypeScript, the hash again.
   - For pure versioned deltas, ARFP's best case equals the state of the art. Any advantage has to come from §6–§9.
5. **Precomputation matters.** Encoding the delta at event time at level 19 adds 0.23 s for three.js and 2.8 s for TypeScript. At level 3 it adds 3–14 ms, for a delta 1.3–2× larger, and push keeps its round-trip advantage.
6. **Control bytes matter only for small payloads.**

| Payload | Negotiated: all control (3,421 B) | Negotiated: before the payload (1,828 B) | Fast path (1,079 B) | 128 B push frame |
|---|---|---|---|---|
| 70 B (avatar pose) | 98.0% | 96.3% | 93.9% | 64.6% |
| 2,559 B (three.js delta) | 57.2% | 41.7% | 29.7% | 4.8% |
| 195,000 B | 1.7% | 0.9% | 0.6% | 0.1% |

Even a 128-byte frame nearly triples a 70-byte pose. Per-frame streams need a datagram profile with a header of a few bytes and evidence only at checkpoints.

**The round-trip rule, priced** (bandwidth × RTT: an extra round trip pays only if it saves more than this):

| Link | 20 ms | 56 ms | 100 ms | 160 ms |
|---|---|---|---|---|
| 10 Mbit/s | 25 KB | 70 KB | 125 KB | 200 KB |
| 100 Mbit/s | 250 KB | 700 KB | 1,250 KB | 2,000 KB |
| 1 Gbit/s | 2.5 MB | 7 MB | 12.5 MB | 20 MB |

---

## 6. AI-to-AI state: where the planner already pays

This is the strongest near-term fit for the "AI compression interconnect" idea. Research and production systems already make ARFP's per-item choice between two of its modes.

**What exists (sourced).**
- **[CacheGen][cachegen]** (SIGCOMM 2024).
  - Each chunk of KV cache is sent at one of several encoding levels, or as text for the receiver to recompute "when the bandwidth is too low".
  - Compared with recent systems that reuse the KV cache, the cache is 3.5–4.3× smaller and total fetch-and-process delay is 3.2–3.7× lower.
  - The accuracy loss is "no more than 2%".
  - It is now maintained as part of [LMCache][lmcache].
- **[Mooncake][mooncake]** (Kimi's serving platform, FAST 2025).
  - Serving is built around a disaggregated KV-cache store.
  - Its transfer engine reports up to 87 GB/s on 4×200 Gb/s and up to 190 GB/s on 8×400 Gb/s for a 40 GB payload ([repo][mooncake-repo]).
  - It recomputes rather than fetches when the best remote prefix match is no longer than the local one.
  - Kimi handled 75% more requests under real workloads.
- **Moving the cache inside a cluster is cheap.**
  - [Splitwise][splitwise] measured about 5 ms of non-overlapped transfer, 0.8% of end-to-end time, between H100 machines at 400 Gb/s.
  - [DistServe][distserve] measured under 0.1% of latency, but its placement keeps that transfer on NVLink inside one machine. Its links between machines were 25 Gb/s.
- **Model weights.**
  - [LoRA][lora] fine-tunes ship a 35 MB checkpoint instead of 350 GB for GPT-3 175B: a delta on an exact base.
  - [BitDelta][bitdelta] stores fine-tune deltas at 1 bit (lossy, so class T).
  - [DeltaZip][deltazip] compresses deltas up to 10×.

**Modeled: send the cache, or send the text and recompute?**

Assumptions:
- Each receiver is counted per H100 of compute, at 50% of 989.5 dense BF16 TFLOP/s. NVIDIA lists 1,979 TFLOP/s "with sparsity" ([H100][h100]); dense is half (derived).
- The 50% utilization is assumed. The one published H100 prefill figure found is 63%, for 405B at long context ([arXiv 2411.01783][cp-prefill]).
- Attention cost is included.

Break-even is the link speed above which sending beats recomputing. It scales with the receiver's compute: multiply by G for G GPUs behind one link, and divide for a weaker receiver.

| Model | Context | KV cache | Recompute per H100 | Send at 400 Gb/s | Send at 1 Gb/s | Break-even per H100: BF16 | FP8 | ~4× codec | 8 GPUs behind one link (BF16) |
|---|---|---|---|---|---|---|---|---|---|
| Llama 3.1 8B | 8K | 1.07 GB | 0.30 s | 0.021 s | 8.6 s | 28.5 Gb/s | 14.2 | 7.1 | 228 Gb/s |
| Llama 3.1 8B | 128K | 17.2 GB | 13.4 s | 0.34 s | 137 s | 10.3 Gb/s | 5.1 | 2.6 | 82 Gb/s |
| Llama 3.1 70B* | 8K | 2.68 GB | 2.5 s | 0.054 s | 21.5 s | 8.5 Gb/s | 4.3 | 2.1 | 68 Gb/s |
| Llama 3.1 70B* | 128K | 42.9 GB | 82.9 s | 0.86 s | 344 s | 4.1 Gb/s | 2.1 | 1.0 | 33 Gb/s |

\*Per-GPU equivalent. 70B BF16 weights don't fit on one 80 GB GPU, so a real 70B receiver has several GPUs; use the last column for 8 GPUs sharing one link.

**The decision flips inside real link ranges.** Per H100 of receiver compute:
- Above about 30 Gb/s, ship state.
- From about 10 to 25 Gb/s, short contexts on small models favor recompute or a compressed cache.
- On WAN and consumer links (1 Gb/s and below), send the recipe (the text) or compress heavily. This assumes the receiver has GPU-class compute; a weaker receiver lowers the break-even in proportion.
- Longer contexts favor shipping state, because attention cost grows with the square of the context.
- Per GPU, larger models also favor shipping state. But a large-model receiver has many GPUs behind one link, which multiplies its break-even (8 GPUs: 33–68 Gb/s for 70B).

**Modeled: adaptive vs fixed.** Llama 3.1 8B, 32K context, three receivers on 400, 10 and 1 Gb/s links, each recomputing on one H100-equivalent. Seconds until each receiver holds the cache:

| Strategy | 400 Gb/s | 10 Gb/s | 1 Gb/s | Slowest | Sum |
|---|---|---|---|---|---|
| Always send KV, BF16 (E) | 0.09 | 3.44 | 34.36 | 34.36 | 37.88 |
| Always send KV, ~4× codec (T) | 0.02 | 0.86 | 8.59 | 8.59 | 9.47 |
| Always recompute, default kernels (N) | 1.63 | 1.63 | 1.63 | 1.63 | 4.90 |
| Always recompute, batch-invariant kernels (E on one pinned stack) | 2.64 | 2.64 | 2.64 | 2.64 | 7.91 |
| Adaptive, contract: exact, receivers on different stacks | 0.09 | 3.44 | 34.36 | 34.36 | 37.88 |
| Adaptive, contract: exact, all on the sender's pinned stack | 0.09 | 2.64 | 2.64 | 2.64 | 5.36 |
| Adaptive, contract: bounded (E or T) | 0.02 | 0.86 | 2.64 | 2.64 | 3.52 |
| Adaptive, contract: any class (E, T or N) | 0.02 | 0.86 | 1.63 | 1.63 | 2.51 |

**How to read it.**
- **The summed time halves** against the best fixed strategy (2.51 vs 4.90 s). The slowest receiver doesn't improve (1.63 s either way). The whole gain is the class-T codec at the two fast-link receivers.
- **Against always shipping the uncompressed cache,** the 1 Gb/s receiver is 21× faster.
- **The contract sets the price.** Exact results cost 2.1× (5.36 vs 2.51 s) if every receiver runs the sender's pinned stack. They cost 15× (37.88 vs 2.51 s) if not, because shipping the full cache is then the only exact option modeled. A lossless codec on the cache would also be exact and would narrow that gap.
- **The model flatters the codec:** its encode and decode time is left out.
- **The model predicts no gain for the slowest receiver,** so it offers no support for H2 in §11.

**Why the classes matter here.**
- **Shipped KV bytes are class E.**
- **A compressed cache is class T.** Its bound is a task metric (CacheGen's accuracy figure), not a distance on the result, so ARFP's ε + δ transfer rule cannot apply. It needs end-to-end checks instead.
- **Recompute is class N by default.** Thinking Machines got 80 different completions out of 1,000 at temperature 0 on Qwen3-235B, because kernels are not batch-invariant and batch size varies with server load ([TML, Sept 2025][tml]).
  - Their batch-invariant kernels gave run-to-run determinism on one setup, at about 1.6–2.1× the time in one decode-heavy benchmark. Applying that ratio to prefill is an assumption.
  - They do not claim determinism across hardware or library versions, so recompute is class E only when every receiver runs the sender's exact pinned stack.

**On-device models are the consumer version of this.** Apple's ~3B model and Gemini Nano are shared receiver-side knowledge, so a sender can ship a short recipe instead of bytes. But they are versioned:
- Nano v2, v3 and v4 coexist across devices ([ML Kit GenAI][mlkit-genai]).
- Apple tells developers to version prompts across model updates.

Recipes against them are class N unless the runtime is pinned and checked. ARFP's runtime-digest binding and class rules are what make such recipes trustworthy.

**Judgment.** ARFP should not try to replace the transfer engines; Mooncake and LMCache do that well. Its contribution here would be the common layer above them: one contract, evidence and provenance format for KV caches and context that cross organizational or trust boundaries, such as agent-to-agent handoff or federated inference. That is also where today's systems have nothing.

---

## 7. ARFP v0.1 reviewed for speed: what costs time, and the fix for each

| # | Cost in v0.1 | Size or effect | Fix | Precedent |
|---|---|---|---|---|
| 1 | OFFER → ACCEPT wait | +1 round trip before payload: 113 vs 56 ms (three.js, warm 100 Mbit/s) | **Push profile** (§8): a standing subscription; binding reference, plan reference and payload in one flight; REPAIR only on a miss | [BIP 152][bip152] high-bandwidth mode: 0.5 RTT, 1.5 on a miss. [RFC 9842][rfc9842]: state rides on the request |
| 2 | Control bytes | 3,421 B per negotiated update (1,828 B before the payload); 1,079 B on the fast path | Contract template signed once; small per-revision binding; plan by digest; ~128 B frame target; a few-byte datagram header for per-frame streams; signatures only on durable objects, with the transport authenticating everything else | — |
| 3 | STATE | Scoped have-queries cost round trips. Full inventories leak and grow: 10,000 objects is 320 KB as digests | Name the one base you hold, on the request (Available-Dictionary style). Or a membership filter: ~12 KB as a Bloom filter or ~10 KB as a Golomb-coded set, for 10,000 objects at 1%. Or a sketch of changes since the last sync: 4 B per unit of capacity, which must cover the differences, with per-peer history | [RFC 9842][rfc9842]; [BIP 158][bip158] GCS; [Erlay / BIP 330][bip330], [minisketch][minisketch] |
| 4 | Validation on the critical path | T-class checks (e.g. Hausdorff) are heavy | E: hash on arrival. T: the publisher measures ε once at publish time and the receiver does ε + δ arithmetic. Global invariants run after provisional use and promote the result to "validated" | [3D Tiles][3dtiles]: producer-declared `geometricError` in meters |
| 5 | End-to-end output check | SHA-256 of 9 MB is ~7 ms on this CPU. Against the dictionary paths it adds 12% (pull) to 24% (push) to a warm 9 MB update | A chunked tree hash over content-defined chunks: chunks copied from the verified base keep their digests and only changed chunks are hashed, so the check scales with the change, not the file. Overlapping the hash with arrival helps only whole-object transfers | — |
| 6 | Commit durability | One fsync per journal record (C21) | Group commit (batch fsync). Journal only durable streams. One signature over a batch of receipts (Merkle root) | Standard database practice |
| 7 | Planner latency | An AI model planning each update would put hundreds of milliseconds or more on the critical path (judgment) | Plans come from precomputed templates by table lookup. AI generates templates and policies offline. This also keeps the property that a bad planner makes things slower, not wrong | Mooncake's one-line fetch-vs-recompute rule; CacheGen's per-chunk configuration choice |
| 8 | One contract per revision | 1.6 KB per revision; an OFFER with inline target and contract is 3,310 B | **Built** after this review: a session template plus a per-revision binding. A new revision's OFFER is 1,838 B once the template is cached, 707 B with the plan by id (working record §10, cases T1–T14) | — |
| 9 | Misses and encode time | A STATE error costs a round trip; encoding at event time costs 3 ms – 2.8 s (§5) | Prefill likely misses. The sender must be able to serve every item it references. Use per-session salted short IDs. Precompute deltas for the likely bases, encode fast for the rest, and fall back to literal bytes when a delta is no smaller (prebound fallbacks). Never treat a fallback as an error | [BIP 152][bip152]: prefill ≤10 KB; the sender "MUST" be able to answer any getblocktxn |
| 10 | STATE privacy | A state summary is a fingerprint | Scope per origin or principal; re-salt per session; let the receiver decide what it reveals; send nothing in private mode | [Cache Digests][cache-digest] was declared dead in 2019 for lack of implementers ([chairs' note][cache-digest-dead]). The draft required clients to mitigate fingerprinting but left "how effective the suggested mitigations actually would be" as a TODO |

---

## 8. How the transfer set would work end to end: the push profile

This is an evolution of v0.1's fast path, not a new protocol. It runs over QUIC. Because every object is content-addressed, objects are immutable and CDN-cacheable without revalidation.

**Session (once, off the critical path).**
1. QUIC connection: 1 RTT, or 0 RTT on resumption.
2. CAPABILITIES: runtimes with digests and determinism classes, plus a compute score per runtime class.
3. STATE as a summary: held bases by digest, or a filter or sketch, scoped and salted.
4. The publisher's signed **contract template**, cached by digest.
5. A **standing DEMAND** per stream. This is the subscription, the equivalent of BIP 152's per-connection opt-in.

**Per update (the critical path).**
1. **Publisher event → one flight:**
   - `[binding(rev) | plan-template ref + parameters | evidence refs | payload chunks, milestone first]`
   - The planner picks, per node and per receiver, the eligible mode with the lowest expected time:
     `bytes/bandwidth + compute/receiver speed + P(miss) × RTT + validation`
   - Eligible modes are limited by the contract's classes. Deltas against likely bases are precomputed.
2. **Receiver reconstructs while streaming:**
   - E nodes are checked against the expected digest through the chunked tree hash, re-hashing only chunks that changed.
   - T nodes are accepted by ε + δ arithmetic against precomputed evidence.
   - Milestones and free regions are usable at once, labeled **provisional**.
3. **Miss:** a REPAIR names only the missing nodes, costing one round trip; or a prebound fallback runs with none.
4. **Promotion:** provisional → validated once global invariants pass → committed locally, with receipts batched.

**Cost per update:**
- Push profile: 0.5 RTT + conditional bytes/bandwidth + decode + hashing of changed chunks, plus P(miss) × RTT.
- Pull with dictionary: 1 RTT + delta bytes/bandwidth.
- Notify-then-fetch: 1.5 RTT + delta bytes/bandwidth.

**Where it is faster than HTTP/3 + dictionaries:**
1. **Push saves a round trip on subscribed streams.** Any pub/sub channel gets this too, so it is not unique.
2. **Per-node choice across all modes.** Dictionaries only do deltas; ARFP adds recipes, latents, recompute and references, per receiver.
3. **Receiver-specific plans:**
   - upstream decode for weak devices;
   - exact deltas for strong ones;
   - recompute where the link is slow.
4. **Cancellation.** Superseded work is dropped by work key, so camera jumps waste fewer bytes.
5. **Trusted approximation across modes.** Latent and procedural reconstruction is accepted under one contract with labels. AV1 film grain does this for one layer of one codec; nothing spans modes.

**Where it is not faster:**
- one-shot fetches of novel content;
- small objects on warm, fast links;
- anything bound by chains of dependent round trips (most web pages).

---

## 9. Where it would and wouldn't speed things up

| Rank | Domain | What limits it | What the transfer set does | Expected gain vs a *strong* baseline | Confidence (judgment) |
|---|---|---|---|---|---|
| 1 | AI datacenter and AI-to-AI state | Bandwidth vs. compute; GB-scale caches | Chooses send, compress or recompute per receiver and link, respecting E/T/N | Modeled: summed time halved against the best fixed strategy, all from compressed (T-class) caches to fast-link receivers; exact contracts cost 2.1× (pinned stacks) to 15× (mixed stacks). CacheGen: 3.2–3.7× lower delay than KV-reuse baselines | High that it matters. The mechanics exist; ARFP's value is the contract and provenance layer |
| 2 | Large versioned content to mixed receivers (CAD/BIM, digital twins, game patches, 3D tiles) | Bytes on slow or cold links; device differences | Exact deltas, content-aware transforms, per-receiver detail level or upstream decode, cancellation, milestones | Deltas: 1.7–1,117× fewer bytes across 19 release pairs (median 75× for three.js), but RFC 9842 gets the generic part too. Content-aware transforms helped where the generic delta failed (8.1× vs 1.7×). The gain from heterogeneity is unmeasured | Medium. Stage 4 decides |
| 3 | Telepresence and avatars | Bitrate at low bandwidth; latency | Latents against person models; exact keyframes as the correction channel; labeled generation | 2.2–10× in the lab (face-vid2vid, Gemino); no production figure found | Medium. Gemino's model is ~1 GB unoptimized, and its authors found personalization gives limited benefits; privacy weighs heavily |
| 4 | Video streaming | Throughput | Parametric synthesis of high-entropy detail | −31.6% average bitrate in Netflix's production A/B test; its ~300-title analysis found 36% at 1080p and above and about 10% below ([Netflix][netflix-fgs]); NAS 17% at equal QoE (lab) | High that tens of percent are real on grainy high-resolution content. ARFP adds contracts and labels, not compression |
| 5 | Constrained links (mobile edge, satellite, disaster response) | Bytes and round trips | Push, references, recipes | Large where bytes dominate (Amdahl f → 1) | Medium |
| 6 | General web pages | Round trips, client CPU | — | Little: Google Search's 23% byte cut gave 1.7% LCP | High that this is the wrong target |

---

## 10. Negative cases to publish (pre-registered)

1. **Tiny frequent updates on warm, fast links.** Control bytes and any added round trip dominate. For a 70-byte pose, 94% of the bytes are overhead even on the v0.1 fast path.
2. **Mechanical rewrites against a generic delta.** For TypeScript 5.4.5 → 5.5.2 the generic delta was 58% of brotli. A content-aware transform improved it to 8.1× smaller than brotli, still far short of the next minor release's 32×.
3. **Genuinely novel content.** No release in this sample was novel. When Y says nothing about X, no representation helps, and the benchmark must include such updates.
4. **Weak receivers for latent decoding.** Gemino adds about 40 ms of frame latency (87 vs 47 ms). It uses a person-specific model, about 1 GB unoptimized, though its authors found personalization adds little ([Gemino][gemino]).
5. **Stale or wrong STATE.** A base ten releases stale cost about 12× the bytes of a typical up-to-date delta (three.js). A miss costs a round trip, and a state summary can fingerprint the user (Cache Digests).
6. **Verification cost on big objects.** Hashing a 9 MB output put ARFP's push profile 24% behind a plain pub/sub delta in the model, until the check is made incremental.
7. **Nondeterministic recompute treated as exact.** Age of Empires' out-of-sync failures; Thinking Machines' 80 different completions out of 1,000 at temperature 0.
8. **Byte savings that don't become time.** Google Search: 23% fewer HTML bytes, LCP only 1.7% better.

---

## 11. Stage 4/5, sharpened

**Baselines.** Each must be strong, or the result means nothing:

| Workload | Baselines |
|---|---|
| Delta workloads | HTTP/3 + RFC 9842 `dcz` + CDN cache (dcz-equivalent delta sizes measured here; no HTTP timing yet); pub/sub push with dictionary deltas |
| 3D | glTF + Draco; 3D Tiles |
| AI state | LMCache / CacheGen-style adaptive KV transfer |

**Workload: steady editing or camera-jump churn?** Don't choose a single point. Sweep two knobs and add a receiver mix:
- **Predictability:** how much of each update the receiver can rebuild from what it holds (0%, 50%, 90%, 99%).
- **Churn:** superseded demands per minute (0, 1, 10, 60).
- **Receiver mix:** one strong and one weak receiver. This is where ARFP's distinct gain should appear, if it exists.

Headline point: **steady editing with occasional jumps** (high predictability, low-to-moderate churn, mixed receivers). That is what real review sessions look like. Push plus delta should tie the baseline there, and the adaptive planner has to pull ahead. Publish the whole grid, including the corner where ARFP loses: low predictability, high churn, tiny updates.

**Hypotheses, with proposed kill criteria:**

| # | Hypothesis | Pass | Kill |
|---|---|---|---|
| H1 | Parity: the push profile matches pub/sub + dictionary on single-receiver delta workloads, including the end-to-end hash | p50 time-to-validated within 5% | Worse by more than 5%: the protocol overhead is wrong; fix it before anything else. As modeled, a 9 MB object fails this unless the check scales with the change (chunked tree hash) |
| H2 | Heterogeneity: per-receiver plans (upstream decode, detail level) beat the best single fixed strategy for the weak receiver | ≥1.5× on p95 time-to-usable for the weak receiver, at equal total bytes | Below 1.2×: the planner isn't earning its complexity. No model here supports H2 yet |
| H3 | Churn: cancellation by work key cuts wasted bytes vs. HTTP/3 stream cancellation | ≥30% fewer wasted bytes | Below 10% |
| H4 | Approximation under contract: T-class plans with precomputed evidence deliver contract-valid results faster on a slow link (10 Mbit/s) | ≥2× faster, zero false accepts under fault injection | Any false accept |
| H5 | Negative: tiny frequent updates and novel content | Reported, whatever the result | Not reported |

The thresholds are proposals. Adjust them, but fix them before running.

**Metrics:**
- time to validated result (p50/p95);
- time to first usable result;
- bytes on every link, including model and dictionary bootstrap;
- sender encode time;
- receiver CPU and energy;
- repair rate;
- false-accept rate under fault injection.

---

## 12. Scorecard for the whole project

**Strong.**
- **The core idea is coherent and maps onto real distinctions** that deployed systems already struggle with. The precedents only partly cover the classes:
  - Bounded error is declared, not verified: Draco quantization, 3D Tiles `geometricError`.
  - AV1 lets a conformant decoder choose between bit-exact grain and grain with "no perceptually significant differences".
  - Lockstep needs bit-exact determinism.
  - LLM endpoints are nondeterministic by default.

  The core is a contract, determinism classes, evidence that transfers by identity or bound, and labeled generation. Across all modes at once, it covers what those precedents handle piecemeal.
- **The rigor is unusual for a concept:**
  - a CDDL schema;
  - 95 executable cases;
  - mutation testing;
  - real-crash recovery;
  - vectors that reproduce byte for byte;
  - now a measured byte benchmark and an explicit time model.
- **It sits in a gap the precedents leave open.** No source found verifies or labels generated reconstruction end to end. The 6G semantic-communication literature is mostly vision ([survey][semcom-survey], [ITU-R M.2160][m2160]), and recent work names "wireless hallucination" in generative-AI communication as an underexplored problem ([2025][hallucination]).

**Weak or unproven.**
- **Speed is unmeasured.** In the model, the negotiated v0.1 path trails HTTP with RFC 9842 by a round trip everywhere, and trails plain HTTP on warm, fast links. The fast path ties RFC 9842 on small objects and trails it by the hash cost on large ones. That is fixable (§7, §8), but it is the current state.
- **ARFP's "true metric" requirement for transferring T-class evidence rules out most perceptual scores.** Media systems judge quality with learned or perceptual scores: Gemino uses LPIPS, and the AV1 grain authors note that objective metrics "would not work well" on synthesized grain ([Norkin and Birkbeck][norkin]). Nothing in those papers establishes the triangle inequality the ε + δ rule needs. Perceptual tiers need their own evidence rule: receiver-side or sampled checks, or an accreditation-style bound like AV1's.
- **Receiver-state protocols have a poor deployment record on the web.**
  - Cache Digests died.
  - Server Push was removed from Chrome; only 1.25% of HTTP/2 sites had used it, later 0.7% ([Chrome][push-removal]).
  - RFC 9842 is still "Limited availability": Chrome and Edge, with Firefox in progress as of April 2026 ([MDN][mdn-dict], [Cloudflare][cf-dict]).
- **Shared models are expensive and versioned.** Recipes and latents need them delivered and pinned; that cost belongs in every plan.
- **Generic deltas lose much of their gain on predictable rewrites** (re-indentation, renaming, reordering). Content-aware transforms per profile recover part of it (8.1× vs 1.7× here). That is engineering per content type, not protocol.
- **Novelty sits in the combination, not in any one mode.** Every mode exists somewhere. The combination of contract-governed per-node choice, determinism-aware evidence and labeled generation was not found assembled in any source checked. That is a statement about the search, not proof of novelty.

**Overall (judgment).** Strong as a correctness and trust framework. Unproven as a transport, and currently slower than HTTP with RFC 9842 in the model. The path to "faster" is clear and testable:
1. zero-round-trip push;
2. compact frames;
3. state summaries;
4. precomputed deltas and evidence;
5. incremental (tree) hashing;
6. a planner that wins on mixed receivers.

The honest pitch is not "faster internet". It is "the layer that lets the internet use what receivers already know, without lying about what was reconstructed."

---

## 13. What changed in the kit

- **`bench/delta_bench.py` and `bench/delta_results.json`:** measured patch-from deltas at levels 19 and 3, the content-aware delta, line overlap, and decode, encode and SHA-256 times. Rerunning needs network access to the npm registry the first time.
- **`bench/speed_model.py`, `bench/speed_model.md` and `bench/speed_model.json`:** every modeled number in this review, except the hand estimate of chunk-hashing cost in §5. Runs offline in under a second.
- **Protocol changes since this review:** the contract split (§7 row 8) is built and tested. The push profile (§8) is a design, not code yet.

---

## 14. Sources

**Web and transport**
- Belshe, "More Bandwidth Doesn't Matter (much)" (2010): [belshe.com][belshe]; reproduced in [HPBN ch. 10][hpbn-web]
- HPBN, latency and fiber table: [hpbn.co][hpbn-latency]; TLS round trips: [hpbn.co][hpbn-tls]
- Mostafa, Wittie, Goel (2025), bandwidth-limited pages: [arXiv 2503.03641][msu2025]
- WProf (NSDI 2013): [PDF][wprof]
- Google Search compression dictionaries (Chrome blog, May 2025): [developer.chrome.com][search-dict]
- RFC 9842 Compression Dictionary Transport (Sept 2025): [rfc-editor.org][rfc9842]; Cloudflare shared dictionaries (Apr 2026): [blog][cf-dict]; MDN status: [MDN][mdn-dict]
- Courgette (2009): [Chromium blog][courgette]
- RFC 9000 / 9001 (QUIC), RFC 8446 (TLS 1.3), RFC 8470 (Early Data), RFC 6928 (initial window): [9000][rfc9000], [9001][rfc9001], [8446][rfc8446], [8470][rfc8470], [6928][rfc6928]
- Chrome removing HTTP/2 Server Push (2022): [developer.chrome.com][push-removal]; Early Hints, Cloudflare and Shopify: [Cloudflare][cf-early], [Shopify][shopify-early]
- Web Almanac 2025, Page Weight: [almanac.httparchive.org][almanac]
- Sandvine 2023 GIPR (2022 data): [press release][sandvine2023]; Ericsson Mobility Report, June 2026: [ericsson.com][ericsson]

**Receiver-state protocols**
- BIP 152 Compact Block Relay: [bitcoin/bips][bip152]; Compact Blocks FAQ (2016): [bitcoincore.org][cb-faq]
- Graphene tech report (2019): [UMass][graphene]
- Erlay (CCS 2019): [arXiv 1905.10518][erlay]; BIP 330: [bitcoin/bips][bip330]; minisketch: [GitHub][minisketch]
- Eppstein et al., "What's the Difference?" (SIGCOMM 2011): [PDF][eppstein]
- Broder & Mitzenmacher, Bloom filter survey: [PDF][bloom]; BIP 158: [bitcoin/bips][bip158]; Wuille on Golomb-coded sets: [wuille.net][wuille-gcs]
- Cache Digests draft: [datatracker][cache-digest]; status note (Jan 2019): [ietf-http-wg][cache-digest-dead]
- rsync technical report: [samba.org][rsync]; Git pack protocol: [git/git][git-pack]

**AI infrastructure**
- CacheGen: [arXiv 2310.07240][cachegen]; LMCache: [GitHub][lmcache]
- Mooncake: [arXiv 2407.00079][mooncake], [GitHub][mooncake-repo]
- DistServe: [arXiv 2401.09670][distserve]; Splitwise: [arXiv 2311.18677][splitwise]
- Thinking Machines Lab, "Defeating Nondeterminism in LLM Inference" (Sept 2025): [blog][tml]
- Llama 3.1 architecture: [meta-llama/llama-models][llama-models]; NVIDIA H100: [product page][h100]; Context parallelism, 63% utilization: [arXiv 2411.01783][cp-prefill]
- LoRA: [arXiv 2106.09685][lora]; BitDelta: [arXiv 2402.10193][bitdelta]; DeltaZip: [arXiv 2312.05215][deltazip]
- Apple Foundation Models tech report (2025): [Apple ML Research][apple-fm]; Gemini Nano: [Android][nano], [ML Kit GenAI][mlkit-genai]; Chrome built-in AI APIs: [Chrome][chrome-ai]

**Generative and model-based reconstruction**
- face-vid2vid (Wang, Mallya, Liu): [arXiv 2011.15126][facevid2vid]
- NAS (OSDI 2018): [KAIST record][nas]
- Gemino: [arXiv 2209.10507][gemino]
- AV1 film grain conformance text: [AV1 spec source][av1-conformance]; Norkin and Birkbeck, AV1 film grain synthesis: [PDF][norkin]; Netflix, "AV1 @ Scale: Film Grain Synthesis" (July 2025): [Netflix TechBlog][netflix-fgs]
- Pixel Codec Avatars: [arXiv 2104.04638][pica]
- Draco on 3D Tiles (Cesium, 2018): [cesium.com][cesium-draco]; 3D Tiles: [CesiumGS/3d-tiles][3dtiles]
- "1500 Archers on a 28.8" (2001): [Game Developer][aoe]; Valve prediction: [Valve Developer Community][valve-pred]
- ITU-R M.2160 (2023): [PDF][m2160]; Chaccour et al., semantic communication survey: [arXiv 2211.14343][semcom-survey]; "Wireless Hallucination" (2025): [arXiv 2503.06149][hallucination]
- NVIDIA RTX Video Super Resolution (2023): [NVIDIA blog][rtx-vsr]

[belshe]: https://www.belshe.com/2010/05/24/
[hpbn-web]: https://hpbn.co/primer-on-web-performance/
[hpbn-latency]: https://hpbn.co/primer-on-latency-and-bandwidth/
[hpbn-tls]: https://hpbn.co/transport-layer-security-tls/
[msu2025]: https://arxiv.org/html/2503.03641v1
[wprof]: https://homes.cs.washington.edu/~arvind/papers/wprof.pdf
[search-dict]: https://developer.chrome.com/blog/search-compression-dictionaries
[rfc9842]: https://www.rfc-editor.org/rfc/rfc9842.html
[cf-dict]: https://blog.cloudflare.com/shared-dictionaries
[mdn-dict]: https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Compression_dictionary_transport
[courgette]: https://blog.chromium.org/2009/07/smaller-is-faster-and-safer-too.html
[rfc9000]: https://www.rfc-editor.org/rfc/rfc9000.html
[rfc9001]: https://www.rfc-editor.org/rfc/rfc9001.html
[rfc8446]: https://www.rfc-editor.org/rfc/rfc8446.html
[rfc8470]: https://www.rfc-editor.org/rfc/rfc8470.html
[rfc6928]: https://www.rfc-editor.org/rfc/rfc6928.html
[push-removal]: https://developer.chrome.com/blog/removing-push
[cf-early]: https://blog.cloudflare.com/early-hints-performance/
[shopify-early]: https://performance.shopify.com/blogs/blog/early-hints-at-shopify
[sandvine2023]: https://www.applogicnetworks.com/press-releases/sandvines-2023-global-internet-phenomena-report-shows-24-jump-in-video-traffic-with-netflix-volume-overtaking-youtube
[ericsson]: https://www.ericsson.com/en/reports-and-papers/mobility-report/dataforecasts/mobile-traffic-update
[almanac]: https://almanac.httparchive.org/en/2025/page-weight
[bip152]: https://github.com/bitcoin/bips/blob/master/bip-0152.mediawiki
[cb-faq]: https://bitcoincore.org/en/2016/06/07/compact-blocks-faq/
[graphene]: https://web.cs.umass.edu/publication/docs/2019/UM-CS-2019-001.pdf
[erlay]: https://arxiv.org/abs/1905.10518
[bip330]: https://github.com/bitcoin/bips/blob/master/bip-0330.mediawiki
[minisketch]: https://github.com/sipa/minisketch
[eppstein]: https://www.ics.uci.edu/~eppstein/pubs/EppGooUye-SIGCOMM-11.pdf
[bloom]: https://www.eecs.harvard.edu/~michaelm/postscripts/im2005b.pdf
[bip158]: https://github.com/bitcoin/bips/blob/master/bip-0158.mediawiki
[wuille-gcs]: https://wuille.net/posts/minimizing-golomb-filters/
[cache-digest]: https://datatracker.ietf.org/doc/draft-ietf-httpbis-cache-digest/
[cache-digest-dead]: https://lists.w3.org/Archives/Public/ietf-http-wg/2019JanMar/0033.html
[rsync]: https://rsync.samba.org/tech_report/
[git-pack]: https://github.com/git/git/blob/master/Documentation/gitprotocol-pack.adoc
[cachegen]: https://arxiv.org/abs/2310.07240
[lmcache]: https://github.com/LMCache/LMCache
[mooncake]: https://arxiv.org/abs/2407.00079
[mooncake-repo]: https://github.com/kvcache-ai/Mooncake
[distserve]: https://arxiv.org/abs/2401.09670
[splitwise]: https://arxiv.org/abs/2311.18677
[tml]: https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
[llama-models]: https://github.com/meta-llama/llama-models/blob/main/models/sku_list.py
[h100]: https://www.nvidia.com/en-us/data-center/h100/
[cp-prefill]: https://arxiv.org/abs/2411.01783
[lora]: https://arxiv.org/abs/2106.09685
[bitdelta]: https://arxiv.org/abs/2402.10193
[deltazip]: https://arxiv.org/abs/2312.05215
[apple-fm]: https://machinelearning.apple.com/research/apple-foundation-models-tech-report-2025
[nano]: https://developer.android.com/ai/gemini-nano
[mlkit-genai]: https://developers.google.com/ml-kit/genai
[chrome-ai]: https://developer.chrome.com/docs/ai/built-in-apis
[facevid2vid]: https://arxiv.org/abs/2011.15126
[nas]: https://koasas.kaist.ac.kr/handle/10203/246781?mode=full
[gemino]: https://arxiv.org/abs/2209.10507
[av1-conformance]: https://raw.githubusercontent.com/AOMediaCodec/av1-spec/master/08.decoding.process.md
[netflix-fgs]: https://netflixtechblog.com/av1-scale-film-grain-synthesis-the-awakening-ee09cfdff40b
[norkin]: https://norkin.org/pdf/DCC_2018_AV1_film_grain.pdf
[pica]: https://arxiv.org/abs/2104.04638
[cesium-draco]: https://cesium.com/blog/2018/04/09/draco-compression/
[3dtiles]: https://github.com/CesiumGS/3d-tiles
[aoe]: https://www.gamedeveloper.com/programming/1500-archers-on-a-28-8-network-programming-in-age-of-empires-and-beyond
[valve-pred]: https://developer.valvesoftware.com/wiki/Prediction
[m2160]: https://www.itu.int/dms_pubrec/itu-r/rec/m/R-REC-M.2160-0-202311-I!!PDF-E.pdf
[semcom-survey]: https://arxiv.org/abs/2211.14343
[hallucination]: https://arxiv.org/abs/2503.06149
[rtx-vsr]: https://blogs.nvidia.com/blog/rtx-video-super-resolution/
