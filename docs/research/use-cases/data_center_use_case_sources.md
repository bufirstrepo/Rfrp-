# Sources for the data-center use-case review

*Compiled 2026-10-11 for [ARFP-data-center-use-cases.md](../../proposals/ARFP-data-center-use-cases.md). These add to the [speed-review research notes](../speed-review/), which already cover CacheGen, LMCache, CacheBlend, Mooncake, DistServe, Splitwise, LoRA, BitDelta and DeltaZip. Quotes are as returned by a web-fetch tool that reads the page and extracts passages; they were not re-checked against the PDFs. Evidence labels: **[measured]** the authors' own experiment; **[claim]** a statement without data in the quoted text; **[docs]** product documentation.*

## Llumnix (OSDI 2024): live migration of requests between serving instances

- Abstract: an "efficient and scalable live migration mechanism for requests and their in-memory states", used to reschedule requests "across multiple model instances". — [arXiv 2406.03243](https://arxiv.org/abs/2406.03243), "To appear at OSDI '24"
- What moves: requests move "along with their GPU memory states across instances"; "the KV cache is append-only", so "Llumnix can safely copy the KV cache of previous tokens in parallel with the computation for new tokens." Only the last stage pauses the request, which is drained "out of the current batch" while the remaining block is copied. — [arXiv HTML](https://arxiv.org/html/2406.03243v1)
- **[measured]** "the downtime of migration is nearly constant with increasing sequence lengths (roughly 20-30 ms)". Recomputing an 8K-token sequence on LLaMA-30B instead "takes 3.5s". — [arXiv HTML](https://arxiv.org/html/2406.03243v1)
- **[measured]** Headline: "improves tail latencies by an order of magnitude", "accelerates high-priority requests by up to 1.5x", and "delivers up to 36% cost savings while achieving similar tail latencies". — [arXiv 2406.03243](https://arxiv.org/abs/2406.03243)

## DéjàVu (ICML 2024): KV-cache streaming for fault tolerance

- Abstract: a "KV cache streaming library" used for, among other things, "state replication for fault-tolerance", addressing "long recovery times in case of failures". — [arXiv 2403.01876](https://arxiv.org/abs/2403.01876); [PMLR v235](https://proceedings.mlr.press/v235/strati24a.html)
- Mechanism: "Each worker x streams its KV cache to worker (x+1)%N (assuming an N-stage pipeline)", "incrementally, as each token is generated". After a failure, "token generation just restarts from the latest replicated step"; without it, "the processing of the microbatches that were active at the point of failure starts from scratch". — [arXiv HTML](https://arxiv.org/html/2403.01876v1)
- Baseline practice: "Existing LLM serving systems lack a fault tolerance mechanism, resorting to restarting the entire request." **[claim]**, as of the paper. — [arXiv HTML](https://arxiv.org/html/2403.01876v1)
- **[measured]** "A single failure led to 1.91× increase in the latency of a set of microbatches"; with DéjàVu the increase is 1.24× (fetch-tool summary of §5.2.3). Throughput: "up to 2× compared to FasterTransformer". — [arXiv HTML](https://arxiv.org/html/2403.01876v1)

## SpotServe: serving on preemptible instances

- "to take advantage of the grace period offered by modern clouds, we introduce stateful inference recovery", which "commits inference progress at a much finer granularity"; a migration plan is chosen with "the Kuhn-Munkres algorithm" to minimize communication. — [arXiv 2311.15566](https://arxiv.org/abs/2311.15566)
- **[measured]** "SpotServe can reduce the P99 tail latency by 2.4 - 9.1x compared with the best existing LLM serving systems", "saving 54% monetary cost compared with only using on-demand instances". — [arXiv 2311.15566](https://arxiv.org/abs/2311.15566)

## vLLM: preempted requests are recomputed by default

- **[docs]** When KV cache space runs short, vLLM "can preempt requests to free up KV cache space for other requests"; preempted requests are "recomputed when sufficient KV cache space becomes available again". In V1 "the default preemption mode is `RECOMPUTE` rather than `SWAP`" because "recomputation has lower overhead in the V1 architecture". — [vLLM docs, Optimization and Tuning](https://docs.vllm.ai/en/latest/configuration/optimization/)

## Auditing prompt caching (ICML 2025): shared caches leak through timing

- Cached prompts return faster, and "These timing differences introduce the risk of side-channel timing attacks." **[measured]** "We detect global cache sharing across users in seven API providers". — [arXiv 2502.07776](https://arxiv.org/abs/2502.07776); [PMLR v267](https://proceedings.mlr.press/v267/gu25b.html)

## Check-N-Run (NSDI 2022): lossy checkpoints for training

- "it applies incremental checkpointing, which tracks and checkpoints the modified part of the model", and it "leverages quantization techniques to significantly reduce the checkpoint size, without degrading training accuracy." **[measured]** "reduce the required write bandwidth by 6-17x and the required capacity by 2.5-8x". — [arXiv 2010.08679](https://arxiv.org/abs/2010.08679); [USENIX NSDI '22](https://www.usenix.org/conference/nsdi22/presentation/eisenman)
- Scope: deep learning recommendation models, not LLMs.
