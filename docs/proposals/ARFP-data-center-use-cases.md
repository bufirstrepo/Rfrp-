# Candidate data-center use cases

**Date:** 2026-10-11 · **Status:** candidate use cases and hypotheses, reviewed against published systems. Nothing here is measured, network-tested or demonstrated. Figures are either the sources' own results or the [speed review's model](../analysis/ARFP-internet-speed-review.md#6-ai-to-ai-state-where-the-planner-already-pays), and each is labeled. Sources: the [speed-review research notes](../research/speed-review/ai_infrastructure_state_transfer.md) and the [use-case source notes](../research/use-cases/data_center_use_case_sources.md).

## The fit test

A use case fits ARFP only when all three hold:
1. **Big state.** What has to move is large: gigabytes of KV cache or model state, not kilobytes.
2. **The link is the bottleneck.** Moving the state takes longer than the alternatives, at the link speeds actually deployed.
3. **Rebuilding is tolerable.** The receiver may accept state that was compressed lossily, recomputed, or rebuilt from parts, under a contract that says when that is good enough.

If any one fails, ARFP's planner has little to gain, and its negotiation can cost more than it saves, which is the web-page failure. As a rule of thumb from the speed review, a round trip pays only when it saves more than bandwidth × RTT: about 1.25 MB at 100 Gb/s with an assumed 0.1 ms RTT (arithmetic).

One finding runs through all three strong candidates: published systems already move this state, often well. Where ARFP could add something is mostly the contract and evidence layer, which decides when rebuilt or lossy state may be trusted, rather than speed.

| Candidate | Big state | Link is the bottleneck | Rebuilding tolerable | Already done by | What ARFP would add |
|---|---|---|---|---|---|
| Prefill-to-decode handoff | Yes | Only on slower interconnects | Partly: lossy compression under a contract; recompute defeats the purpose | Splitwise, DistServe, Mooncake, LMCache | Per-receiver choice where decode workers differ; contract-checked lossy compression |
| Cross-request cache reuse | Yes | Yes, when the cache lives in a remote tier | Yes: CacheGen and CacheBlend already accept small, measured quality loss | LMCache, CacheGen, CacheBlend, Mooncake | Binding of each cache to model, tokenizer and kernel stack; per-consumer acceptance; scoping who may reuse whose cache |
| Failover and migration | Yes | Mostly no: moving state is far cheaper than recomputing it | Only under a stated contract | Llumnix, DéjàVu, SpotServe, vLLM preemption | A check that rebuilt state is correct before it is trusted, plus journaled, exactly-once commit |
| *Weaker:* checkpoint and model-delta sync | Yes | Sometimes | Rarely: mostly exact bytes | Exact deltas, compression, Check-N-Run, Mooncake weight transfer | Labels for the lossy minority only |
| *Weaker:* small state or compute-bound work | No | No | — | Anything | Nothing: overhead exceeds savings |

## 1. Prefill-to-decode KV-cache handoff

**What crosses the wire:** the KV cache of each request's prompt, from the GPU pool that read the prompt (prefill) to the pool that generates the reply (decode).

**What the receiver already holds:** the model weights, and sometimes cached prefix blocks it can reuse.

**Fit.**
- **Big state, yes.** DistServe sizes one 512-token OPT-66B request at about 1.13 GB of KV cache. The speed review's model puts a 32K-token Llama 3.1 8B cache at 4.3 GB.
- **Link is the bottleneck, only on slower interconnects.** Inside a well-provisioned cluster the transfer is already a small share: Splitwise measured about 5 ms of non-overlapped transfer, 0.8% of end-to-end time, at 400 Gb/s between H100 machines. DistServe measured under 0.1% of latency, by placing prefill and decode so the transfer stays on NVLink inside one machine. It also computes that hiding the transfer needs about 90 Gb/s at 10 requests per second for its example, so slower links between pools would expose it.
- **Rebuilding tolerable, partly.** Recomputing the cache at the decode side throws away the point of separating the pools. A lossy compressed cache (class T in ARFP's terms) may be acceptable under a contract.

**Already done:** this is a solved engineering problem inside clusters. Splitwise streams the cache layer by layer while prefill continues, and picks the transfer technique by prompt size. Mooncake streams it over GPUDirect RDMA. LMCache carries it over NVLink, RDMA or TCP.

**What ARFP would add:** not the handoff itself. Two narrow pieces:
- a per-receiver choice when decode workers sit behind different links or hardware;
- a contract that decides whether a compressed cache is acceptable for this request, with the result labeled and checked.

This is essentially the headline case in the [README](../../README.md), and the [network-test proposal](ARFP-ai-state-handoff-network-test.md) tests it.

**What would test it:** the transfer's share of end-to-end time across interconnect speeds. If it stays below a few percent at deployed speeds, there is little for ARFP to win here.

## 2. Cross-request cache reuse

**What crosses the wire:** a KV cache computed once for a shared document or context, sent to whichever session needs it, instead of each session reading the document again.

**What the receiver already holds:** the model, and sometimes part of the cache (a matching prefix).

**Fit.**
- **Big state, yes.** A 128K-token context for Llama 3.1 8B is 17.2 GB uncompressed in the speed review's model.
- **Link is the bottleneck, yes, when the cache lives in a remote tier** (another node's memory, SSD, object storage). That is the case CacheGen was built for: at 3 Gb/s it cut time to first token 3.1–4.7× against sending the text and recomputing.
- **Rebuilding tolerable, yes, and already accepted.** CacheGen's compressed caches lose "no more than 2%" accuracy. CacheBlend reuses caches for chunks that are not at the start of the prompt and recomputes a small subset of tokens to repair them; it reports no loss in generation quality on its benchmarks.

**Already done:** this is the most developed of the three.
- LMCache stores and reuses caches across queries and serving engines, and reports up to 15× throughput with vLLM.
- CacheGen adapts each chunk between encoding levels and sending text for recompute as bandwidth changes.
- Mooncake decides between fetching a remote prefix and recomputing it, by comparing match lengths. It estimates that up to 50% of its cache could be reused in current workloads, and up to 90% for some services.

**What ARFP would add:**
- **Binding.** A cache is valid only for one model revision, tokenizer and context, and recomputed parts depend on the kernel stack. ARFP's identities and runtime digests can bind all of that, so a cache built for another model revision is rejected rather than silently reused.
- **Per-consumer acceptance.** One consumer may accept a lossy cache and another may not. The contract makes that a stated, checkable decision instead of a system-wide setting.
- **Who may reuse whose cache.** Shared caches leak: an audit of language-model APIs found "global cache sharing across users in seven API providers", with the timing differences creating "the risk of side-channel timing attacks". ARFP's per-principal scoping could express who may reuse a cache. It would not remove timing side channels by itself.

**What would test it:** per-request choice (load compressed, load raw, recompute, blend) against LMCache with CacheGen's own adaptation, plus provenance checks: caches from a different model revision, tokenizer or tenant must be rejected every time.

## 3. Failover and migration

**What crosses the wire:** the in-flight state of running requests (their KV caches and progress), moved off a failing, preempted or overloaded node, or onto new nodes when scaling.

**What the receiver already holds:** the model weights, and possibly a replica of the state made before the failure.

**Fit.**
- **Big state, yes.** A long-running request's cache grows with every token.
- **Link is the bottleneck, mostly no.** Moving the state is usually far cheaper than rebuilding it, so there is little for a planner to decide; the value here is the check, not speed. Llumnix measured migration downtime of roughly 20–30 ms, nearly constant with sequence length; recomputing an 8K-token sequence on LLaMA-30B instead took 3.5 s.
- **Rebuilding tolerable, only under a stated contract.** A request resumed from recomputed state continues validly but not necessarily identically, since default kernels are not batch-invariant (Thinking Machines got 80 different completions out of 1,000 at temperature 0). Whether that is acceptable is a contract question.

**Already done:**
- vLLM preempts requests when memory runs short and, by default, recomputes them later rather than swapping their cache out, because "recomputation has lower overhead in the V1 architecture".
- Llumnix live-migrates requests with their KV cache between instances while decoding continues, and reports tail latency improved by an order of magnitude.
- DéjàVu streams each worker's KV cache to the next worker as tokens are generated, so after a failure generation "restarts from the latest replicated step" instead of from scratch. In its test a single failure raised latency 1.91× without it and 1.24× with it.
- SpotServe migrates inference progress during a cloud preemption's grace period, and reports 2.4–9.1× lower P99 latency than the best existing systems.

**What ARFP would add:** the check, which matters most here. Migration and failover are where state is most likely to arrive stale, partial or corrupted, and where a silent error turns into wrong output that nobody notices. ARFP would:
- verify migrated state by digest when it must be exact;
- state in the contract whether a recomputed or replica-based continuation is acceptable, and label it when it is;
- commit the takeover exactly once. The kit's write-ahead journal and crash cases (C21) test the local version of this: recovery to one outcome after a crash, a stale head detected, and staged bytes checked before commit.

**What would test it:** inject node failures and preemptions; compare migrating state, restoring a replica, and recomputing, on time to resume and on correctness. Pass only with zero accepted corrupted or mismatched states.

## Weaker candidates

**Training checkpoints and model-delta sync.** The state is big, and moving it can matter: SGLang with Mooncake's transfer engine cut weight updates for the 1T-parameter Kimi K2 from 53 s to 7.2 s. But most of this is exact-bytes work that compression, deduplication and exact deltas already handle. A LoRA fine-tune of GPT-3 175B is a 35 MB delta on an exact base instead of 350 GB. Lossy cases exist and would fit ARFP's labels: BitDelta and DeltaZip compress fine-tune deltas with small quality loss, and Check-N-Run quantizes training checkpoints "without degrading training accuracy", cutting write bandwidth 6–17× (for recommendation models). That is a minority, so ARFP's approximate-rebuild angle adds little here.

**Small state or compute-bound work.** Per-token streams, small tool-call payloads, embeddings and control messages fail the first two tests. Below about 1.25 MB on a 100 Gb/s, 0.1 ms link, a negotiation round trip costs more than any saving (arithmetic). This is the same failure as the web-page case in the [README's boundaries](../../README.md#where-it-does-not-win).

## Sources

From the [speed-review research notes](../research/speed-review/ai_infrastructure_state_transfer.md): [DistServe](https://arxiv.org/abs/2401.09670), [Splitwise](https://arxiv.org/abs/2311.18677), [Mooncake](https://arxiv.org/abs/2407.00079) and its [repository](https://github.com/kvcache-ai/Mooncake), [LMCache](https://github.com/LMCache/LMCache), [CacheGen](https://arxiv.org/abs/2310.07240), [CacheBlend](https://arxiv.org/abs/2405.16444), [LoRA](https://arxiv.org/abs/2106.09685), [BitDelta](https://arxiv.org/abs/2402.10193), [DeltaZip](https://arxiv.org/abs/2312.05215), [Thinking Machines](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/).

From the [use-case source notes](../research/use-cases/data_center_use_case_sources.md): [Llumnix](https://arxiv.org/abs/2406.03243), [DéjàVu](https://arxiv.org/abs/2403.01876), [SpotServe](https://arxiv.org/abs/2311.15566), [vLLM preemption](https://docs.vllm.ai/en/latest/configuration/optimization/), [Auditing Prompt Caching in Language Model APIs](https://arxiv.org/abs/2502.07776), [Check-N-Run](https://arxiv.org/abs/2010.08679).
