# Proposal: AI-state handoff over a real network link

**Date:** 2026-10-11 · **Status:** proposal. Nothing in this note has been run, and it reports no results. · **Builds on:** [speed review §6](../analysis/ARFP-internet-speed-review.md#6-ai-to-ai-state-where-the-planner-already-pays) (the KV-cache model), [§11](../analysis/ARFP-internet-speed-review.md#11-stage-45-sharpened) (baselines and metrics), and the [schema kit](../../kit/README.md).

## Why this test is next

The repository now leads with machine-to-machine state handoff. Its strongest claim there is that choosing per receiver among sending the KV cache, sending a compressed cache, or sending the text to recompute halves the summed handoff time against the best fixed strategy (2.51 vs 4.90 s for three receivers). That claim is modeled only, on assumptions a real run would test:
- prefill runs at an assumed 50% of H100 peak;
- the codec's encode and decode time is left out, which flatters it;
- each receiver is counted per H100 of compute;
- network stacks, contention and retries are ignored.

It is also the test most likely to show that ARFP adds nothing. CacheGen already adapts each chunk between encoding levels and text-plus-recompute as bandwidth changes, and Mooncake already chooses between fetching and recomputing. The bar is those adaptive systems, not only fixed strategies.

## Questions

1. Does the model's break-even link speed (send the cache versus recompute) hold on real hardware?
2. Does per-receiver choice beat the best fixed strategy once codec time and real transfer stacks are counted?
3. Is ARFP's plan choice at least as fast as the existing adaptive transfer?
4. Do ARFP's contract checks catch bad state at an acceptable cost?

## Hypotheses and proposed kill criteria

The thresholds are proposals. Adjust them, but fix them before running.

| # | Hypothesis | Pass | Kill |
|---|---|---|---|
| A1 | Measured break-even (BF16 cache versus recompute) is within 2× of the model's, for Llama 3.1 8B at 8K and 32K tokens (model: 28.5 and 21.0 Gb/s per H100) | Within 2× | Off by more than 2×: recalibrate the model before using it for any decision |
| A2 | Per-receiver choice beats the best fixed strategy on summed time until three receivers (400, 10 and 1 Gb/s) hold usable state, codec time included | At most 0.7× (model: 0.51×) | Above 0.9× |
| A3 | ARFP's plan choice is no slower than CacheGen's own per-chunk adaptation in LMCache, at equal quality | p50 within 5% | Worse by more than 10%: the planner adds cost without value |
| A4 | Contract checks reject bad state | Zero false accepts across all injected faults; checking under 5% of handoff time | Any false accept |
| A5 | Negative case, reported whatever happens: one uniform 400 Gb/s cluster, short contexts, where shipping the state should win outright | Reported | Not reported |

## Setup

**Machines.**
- One sender node holding a prefilled KV cache.
- Three single-GPU receivers on different links: 400 Gb/s RDMA (or 100 Gb/s if that is what is available; record which), 10 Gb/s and 1 Gb/s Ethernet.
- One 8-GPU receiver behind a single link, to test whether break-even scales with the receiver's GPU count as the model assumes.
- The same GPU model everywhere for the main grid. One receiver runs a different software stack (driver or library version) for the exactness rows.

**Models and contexts.** Llama 3.1 8B at 8K, 32K and 128K tokens. Llama 3.1 70B at 8K and 32K on the 8-GPU receiver.

**Data path.** vLLM or SGLang with LMCache (which carries the CacheGen codec), or the Mooncake Transfer Engine. ARFP sits above them as a controller: binding, contract, plan choice, evidence and receipt, using the kit's objects. It does not move the bytes itself.

**Cheaper first pass.** Two single-GPU machines on one link, with `tc` shaping over TCP to emulate the 10 and 1 Gb/s receivers in turn, and Llama 3.1 8B only. RDMA bypasses kernel shaping, so the shaped runs use TCP. This checks A1 and A3 before committing to the full grid.

## Strategies compared

| Kind | Strategies |
|---|---|
| Fixed | Send the KV cache in BF16; in FP8; CacheGen-compressed. Send the text and recompute with default kernels; with batch-invariant kernels |
| Existing adaptive | CacheGen's per-chunk adaptation in LMCache; Mooncake's fetch-versus-recompute rule where it applies |
| ARFP | A per-receiver plan under three contracts, matching the model's rows: exact; bounded (class E or T); any class (E, T or N) |

## Measurements

- Time until each receiver holds usable state, and time to first token after it.
- Bytes on every link, including retries.
- Sender encode time; receiver decode and prefill time; GPU-seconds on both sides.
- Quality against the exact cache: task accuracy and perplexity as CacheGen reports them, plus the first token where greedy generations diverge.
- ARFP's control bytes and control latency (binding, plan, evidence, receipt).
- Check cost, and false accepts under injected faults:
  - a stale cache for the wrong prefix;
  - a recompute on a different stack presented as exact;
  - a corrupted chunk;
  - a cache for a different model revision.
- p50 and p95 over repeated runs, with every failure reported.

## What the kit provides, and what must be built

**The kit provides:**
- contract and binding objects, whole or split;
- determinism classes (E, T, N) and the eligibility rules built on them;
- evidence, attestation and receipt objects, and the gate-zero checks;
- the model in `kit/bench/speed_model.py` whose numbers A1 and A2 test.

**Still to build:**
- A controller that turns a receiver's link, compute and contract into a plan. It should be a table lookup from measured break-evens, so planning stays off the critical path ([speed review §7](../analysis/ARFP-internet-speed-review.md#7-arfp-v01-reviewed-for-speed-what-costs-time-and-the-fix-for-each), row 7).
- Adapters that drive LMCache or Mooncake transfers and the receiver's prefill.
- Runtime digests for kernel stacks, so a recompute counts as class E only on a pinned stack.
- An acceptance check for compressed caches. The codec's bound is a task metric, not a distance on the result, so the kit's ε + δ transfer rule does not apply. It needs an end-to-end check, for example divergence on a held-out probe set. This is open design work.
- A fault injector.

## What each outcome would change

- **A1 fails:** fix the model before relying on any modeled number.
- **A3 fails** (ARFP slower than the existing adaptive transfer): drop the planner claim, and keep ARFP only as a contract and provenance format above the existing engines.
- **A4 fails:** the central claim, that reconstructed state is checked before it is trusted, fails. Stop and redesign.
- **A2 passes only through the lossy codec**, as the model predicts: report it as a result of the contract (it depends on accepting class-T state), not of the transport.

## Out of scope

- Web and consumer delivery; see the [README's boundaries](../../README.md#where-it-does-not-win).
- Worktree (file-tree) handoff between agents. That should be a separate follow-up with `git fetch` and `rsync` as baselines, building on the measured delta results in [speed review §4](../analysis/ARFP-internet-speed-review.md#4-measured-what-receiver-state-is-worth-in-bytes).

## Sources

The figures and system descriptions here come from the speed review and its [research notes](../research/speed-review/ai_infrastructure_state_transfer.md):
- [CacheGen](https://arxiv.org/abs/2310.07240) (SIGCOMM 2024), now maintained in [LMCache](https://github.com/LMCache/LMCache)
- [Mooncake](https://arxiv.org/abs/2407.00079) and its [transfer engine](https://github.com/kvcache-ai/Mooncake)
- [Splitwise](https://arxiv.org/abs/2311.18677) and [DistServe](https://arxiv.org/abs/2401.09670)
- [Thinking Machines, "Defeating Nondeterminism in LLM Inference"](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)
