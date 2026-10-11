# AI-infrastructure state transfer: send state vs. send compressed state vs. recompute at the receiver (closest deployed analogs to an "AI compression interconnect")

Compiled 2026-10-11. Quotes are verbatim as extracted from the cited page or PDF. PDF quotes were obtained through a text-extraction fetch tool that caps quote length, so long sentences appear as fragments joined by " … ". Markdown and HTML markup were stripped from GitHub README quotes. Labels: **[measured]** = authors' own experiment; **[sim]** = simulation; **[claim]** = descriptive or marketing statement with no experiment in the fetched text; **[spec]** = vendor specification; **[derived]** = my arithmetic from cited inputs, always placed under Inferences. NVIDIA's datasheet site (resources.nvidia.com) was not fetched, so the research on that question stopped short. Remaining gaps are listed under each question.

---

## Q1. CacheGen (Liu et al., ACM SIGCOMM 2024): size, delay, and quality claims; bandwidth adaptation; text-and-recompute fallback

### Takeaway
CacheGen compresses KV caches (token-wise delta encoding, layer-wise quantization, then arithmetic coding) by 3.5–4.3x. It cuts the total time to fetch and process a context by 3.2–3.7x compared with KV-reuse baselines, with at most 2% accuracy loss. Yes, it adapts per chunk to the available bandwidth while streaming. Yes, it explicitly falls back to sending a chunk as text and recomputing that chunk's KV cache at the receiver, but only when bandwidth is too low to meet the SLO. It does not run a general "whichever is faster" optimizer. Of all the deployed-research systems found, it is the closest to ARFP's per-item choice between compressed bytes and a recipe.

### Cited Findings
- Metadata: arXiv title "CacheGen: KV Cache Compression and Streaming for Fast Large Language Model Serving". Submitted 2023-10-11; current version v6 is dated 2024-07-19. — [arXiv abs 2310.07240](https://arxiv.org/abs/2310.07240)
- Venue: the authors' repo labels the paper "(SIGCOMM'24)", using an earlier title, "CacheGen: Fast Context Loading for Language Model Applications via KV Cache Streaming". The repo also says "For the latest update and integration, please check out the LMCache project!" — [GitHub UChi-JCL/CacheGen](https://github.com/UChi-JCL/CacheGen)
- Positioning: "CacheGen is a fast context-loading module for LLM systems." — [arXiv abs](https://arxiv.org/abs/2310.07240)
- **[measured] Headline:** "CacheGen reduces the KV cache size by 3.5-4.3x and the total delay in fetching and processing contexts by 3.2-3.7x" … "with negligible impact on the LLM response quality." (abstract). Per the fetch tool's summary of the abstract, the baseline is recent systems that reuse the KV cache. — [arXiv PDF](https://arxiv.org/pdf/2310.07240)
- **[measured] Quality bound (§7.2):** "the degradation is no more than 2% in accuracy, less than 0.1% in F1 score, and less than 0.1 in perplexity." — [arXiv PDF](https://arxiv.org/pdf/2310.07240)
- **[measured] TTFT (§7.2):**
  - "Under bandwidth of 3 Gbps, compared to text context, CacheGen is able to reduce TTFT by 3.1-4.7×."
  - "Compared to default quantization, CacheGen is able to reduce TTFT by 3.2-3.7×."
  - Against 8-bit quantization: "CacheGen can still reduce the TTFT by 1.67-1.81×."
  - [arXiv PDF](https://arxiv.org/pdf/2310.07240)
- Setup:
  - Models (§7.1): "specifically the fine-tuned versions of Mistral-7B, Llama-34B, and Llama-70B."
  - Bandwidth sweep (§7.3): "under a wide range of bandwidth from 0.4–15 Gbps and 15–400 Gbps". The fetch tool reports a fixed 16K-token context for this sweep.
  - [arXiv PDF](https://arxiv.org/pdf/2310.07240)
- Codec mechanism:
  - §5.1.1: "The token-wise locality of K and V tensors inspires CacheGen to encode deltas rather than original values."
  - §5.2: "we apply more conservative quantization (i.e., using more bits) on the delta tensors of earlier layers."
  - Arithmetic coding is used "to losslessly compress the delta tensors and anchor tensors of a context into bitstreams."
  - [arXiv PDF](https://arxiv.org/pdf/2310.07240)
- **Bandwidth adaptation: yes (§5.3).**
  - "CacheGen adapts the configuration of each chunk while streaming the KV cache"
  - Each chunk "can be sent at one of the encoding levels or can be sent in the text format"
  - "It then picks the configuration that has the least compression loss". According to the fetch tool, this is chosen among configurations whose expected delay stays within the SLO.
  - [arXiv PDF](https://arxiv.org/pdf/2310.07240)
- **Fallback to text plus receiver-side recompute: yes (§5.3).** "When the bandwidth is too low, CacheGen can also fall back to sending a chunk in text format" … "and leave it to the LLM to recompute the KV cache of the chunk."
  - The fetch tool describes Figure 7 as showing a switch to text-and-recompute at t=2s after a bandwidth drop. This is a description, not a quote.
  - The trigger is the SLO and low bandwidth. The paper does not say text is chosen "whenever it is faster" in general.
  - [arXiv PDF](https://arxiv.org/pdf/2310.07240)

### Inferences
- CacheGen's per-chunk decision space is {KV at encoding level k} ∪ {text, then recompute at the receiver}. In ARFP terms, that covers two of the five transfer modes: compressed bytes/latent, and recipe. It does not do content-addressed references; that comes from LMCache and Mooncake prefix hashing (Q2, Q3). Its "deltas" are within-tensor (token-to-token), not version-to-version.
- CacheGen output is lossy, so it falls in ARFP class **T**. Divergence is bounded by task metrics (≤2% accuracy, <0.1 perplexity), not by token-level equivalence. The text fallback adds the receiver's own prefill numerics, so whether the result is E or N depends on the receiver's kernels (Q5).
- Even after 3.5–4.3x compression, KV state stays orders of magnitude larger than the text it came from (Q6 arithmetic). This is why the text fallback exists and why a bandwidth threshold governs the choice.

### Gaps
- The ACM Digital Library camera-ready (DOI, page numbers, publication month) was not fetched. I assumed arXiv v6 matches the SIGCOMM version but did not verify it.
- The GPU model used for the TTFT measurements was not captured.
- The exact comparison-baseline wording in the abstract was captured only as a paraphrase.

---

## Q2. LMCache and CacheBlend: what each does, with headline numbers

### Takeaway
LMCache is an open-source, engine-agnostic KV-cache layer for vLLM and SGLang. It offloads KV caches to tiered storage, reuses them across queries and engines, and moves them between prefill and decode workers. Its tech report claims up to 15x throughput when combined with vLLM. CacheBlend reuses precomputed KV caches for chunks that are not at the start of the prompt, as in RAG. It recomputes a small subset of tokens to repair cross-chunk attention and reports 2.2–3.3x lower TTFT and 2.8–5x higher throughput than full recompute. Both CacheGen and CacheBlend are now folded into LMCache.

### Cited Findings
- **LMCache, what it is [claim]:** "LMCache is a KV cache management layer for LLM inference. It turns KV cache from a temporary state into reusable AI-native knowledge that can be stored persistently, reused across multiple serving engines, monitored with an observability stack, and transformed for better generation quality." — [GitHub LMCache README](https://github.com/LMCache/LMCache)
- **LMCache [claim]:** "As a result, LMCache reduces TTFT (time-to-first-token) and improves throughput, especially for long-context agentic, multi-turn conversation, and knowledge-augmented workloads (e.g., RAG)." — [GitHub LMCache README](https://github.com/LMCache/LMCache)
- **LMCache transports and storage [claim]:**
  - "Support KV cache transfer from prefill workers to decode workers over NVLink, RDMA, or TCP through transport layers such as NIXL."
  - "LMCache supports storage backends including CPU RAM, local disk (SSD), Redis/Valkey, Mooncake, InfiniStore, S3-compatible object storage, NIXL, and GDS."
  - [GitHub LMCache README](https://github.com/LMCache/LMCache)
- **LMCache non-prefix reuse via CacheBlend [claim]:** "Extend KV reuse beyond prefix caching by reusing cached KV blocks at any position in the prompt. This leverages CacheBlend to selectively recompute tokens for quality recovery." — [GitHub LMCache README](https://github.com/LMCache/LMCache)
- **LMCache tech report metadata:** "LMCache: An Efficient KV Cache Layer for Enterprise-Scale LLM Inference". Submitted 2025-10-08; v2 dated 2025-12-05. — [arXiv 2510.09665](https://arxiv.org/abs/2510.09665)
- **LMCache tech report:**
  - "We present LMCACHE, the first and so far the most efficient open-source KV caching solution"
  - It "extracts and stores KV caches generated by modern LLM engines (vLLM and SGLang)"
  - It supports "both cache offloading (prefix reuse across queries)" and "prefill-decode (PD) disaggregation (cross-engine/GPU cache transfer)"
  - [arXiv 2510.09665](https://arxiv.org/abs/2510.09665)
- **[measured] LMCache headline:** "Our evaluation shows that combining LMCACHE with vLLM achieves up to 15x improvement in throughput". The gains span "multi-round question answering and document analysis" workloads. — [arXiv 2510.09665](https://arxiv.org/abs/2510.09665)
- **CacheBlend metadata:** "CacheBlend: Fast Large Language Model Serving for RAG with Cached Knowledge Fusion". Submitted 2024-05-26; v3 dated 2025-04-03. — [arXiv abs 2405.16444](https://arxiv.org/abs/2405.16444)
- **[measured] CacheBlend headline (paraphrase; the fetch tool would not return the abstract verbatim):**
  - CacheBlend reuses cached KV "regardless of whether a chunk is at the prefix".
  - It "selectively recomputes a small subset of tokens to update each reused cache".
  - It pipelines that recomputation with cache retrieval so caches can live on slower storage.
  - On three open-source LLMs and four benchmarks, it reports "2.2–3.3x reduction in time-to-first-token and 2.8–5x higher throughput versus full recomputation, with no loss in generation quality".
  - [arXiv abs 2405.16444](https://arxiv.org/abs/2405.16444)
- CacheBlend repo: "The newest updates will always be at LMCache." — [GitHub YaoJiayi/CacheBlend](https://github.com/YaoJiayi/CacheBlend)

### Inferences
- **CacheBlend is a partial-recipe hybrid.** It sends cached state, recomputes a selected subset at the receiver, and blends the two. ARFP's planner currently picks one mode per item. CacheBlend suggests a per-item mixed mode: mostly cached latent plus a small recompute "repair" set.
- **CacheBlend output is class T.** Its quality claim is "no loss in generation quality" on benchmarks, not bit-identity with full prefill.
- **LMCache is the ecosystem evidence that this layer exists in production stacks.** It covers vendor-neutral KV storage, transfer (NVLink, RDMA, TCP, NIXL), and reuse.

### Gaps
- The verbatim CacheBlend abstract and its venue were not captured (I did not verify EuroSys 2025).
- The setup behind LMCache's "up to 15x" (models, hardware, baseline) was not captured.
- I found no independent, third-party replication of either system's numbers.

---

## Q3. Mooncake (Moonshot AI / Kimi; USENIX FAST 2025): architecture, transfer engine and bandwidth, reported gains

### Takeaway
Mooncake is Kimi's serving platform. It separates prefill and decode clusters and pools spare CPU, DRAM, SSD, and RDMA resources into a disaggregated KV-cache store. KV caches move layer by layer over GPUDirect RDMA. The open-source Transfer Engine reports 87 GB/s on 4×200 Gbps and 190 GB/s on 8×400 Gbps RoCE for a 40 GB payload, about the size of 128K tokens of Llama 3 70B KV cache. Reported gains are up to 525% throughput in simulated scenarios and 75% more requests under real Kimi workloads. The arXiv text gives a recompute-vs-fetch rule based on prefix-match length, not a bandwidth threshold.

### Cited Findings
- **FAST'25 metadata:** title "Mooncake: Trading More Storage for Less Computation — A KVCache-centric Architecture for Serving LLM Chatbot". Published in "23rd USENIX Conference on File and Storage Technologies (FAST 25)", pages "155--170", month "feb", 2025. — [GitHub kvcache-ai/Mooncake README, citation block](https://github.com/kvcache-ai/Mooncake)
- **arXiv metadata:** "Mooncake: A KVCache-centric Disaggregated Architecture for LLM Serving". Submitted 2024-06-24; v4 dated 2025-09-03. — [arXiv abs 2407.00079](https://arxiv.org/abs/2407.00079)
- **Architecture:**
  - "It features a KVCache-centric disaggregated architecture that separates the prefill and decoding clusters."
  - "It also leverages the underutilized CPU, DRAM, and SSD resources of the GPU cluster" … "to implement a disaggregated cache of KVCache."
  - [arXiv PDF 2407.00079](https://arxiv.org/pdf/2407.00079)
- **Transfer path (§3):**
  - KV transfer "is handled by a separate (GPUDirect) RDMA-based component called Messenger."
  - Messenger works by "streaming the KVCache generated by each model layer to the destination decoding node's CPU memory"
  - [arXiv PDF](https://arxiv.org/pdf/2407.00079)
- **Testbed (§8.1):**
  - Nodes are "equipped with RDMA network cards that support up to 800 Gbps of interconnect bandwidth between nodes."
  - Each node has "8 NVIDIA-A800-SXM4-80GB GPUs".
  - [arXiv PDF](https://arxiv.org/pdf/2407.00079)
- **[measured, vendor benchmark] Transfer Engine bandwidth:** "With 40 GB of data (equivalent to the size of the KVCache generated by 128k tokens in the LLaMA3-70B model), Mooncake Transfer Engine delivers up to 87 GB/s and 190 GB/s of bandwidth in 4×200 Gbps and 8×400 Gbps RoCE networks respectively, which are about 2.4x and 4.6x faster than the TCP protocol." — [GitHub Mooncake README](https://github.com/kvcache-ai/Mooncake)
- **Transfer Engine features [claim]:**
  - "Transfer Engine supports the use of multiple RDMA NIC devices to achieve the aggregation of transfer bandwidth."
  - "Once transmission fails, Transfer Engine will try to use alternative paths for data delivery automatically."
  - Transports: "TCP, RDMA, AWS EFA, NVMe-oF, NVLink, HIP, Barex, CXL, and Ascend-family transports."
  - [GitHub Mooncake README](https://github.com/kvcache-ai/Mooncake)
- **[sim] and [measured] Gains:**
  - Abstract: "Compared to the baseline method, Mooncake can achieve up to a 525% increase in throughput" … "in certain simulated scenarios while adhering to SLOs."
  - §8.1.2: "Mooncake demonstrates significantly higher throughput, with enhancements ranging from 50% to 525%,"
  - §8.1.1: "achieves throughput improvements of 20% and 40%, respectively, over vLLM-[4M]"
  - Real workloads: "Under real workloads, Mooncake's innovative architecture enables Kimi to handle 75% more requests." §8.1.3: "Mooncake can process approximately 75% more requests while adhering to the SLOs."
  - [arXiv PDF](https://arxiv.org/pdf/2407.00079)
- **Reuse rates:**
  - §4.2: "Increasing the cache capacity from 1,000 to 50,000 blocks boosts the cache hit ratio from 30% to 50%."
  - §9: "Theoretically, up to only 50% of the KVCache can be reused in our current workloads," and reuse "can be as large as 90% for certain scenarios, such as our chat-to-paper service"
  - [arXiv PDF](https://arxiv.org/pdf/2407.00079)
- **Recompute-vs-fetch rule (§6.2):** "we prefer to compute the input tokens if the best remote prefix match length" … "is no larger than the current local reusable prefix". The fetch tool found no explicit bandwidth threshold for when reuse beats recompute in the arXiv text. — [arXiv PDF](https://arxiv.org/pdf/2407.00079)
- **Content-addressed KV reuse in vLLM [claim]:** "Through MooncakeStoreConnector, multiple vLLM instances can store, retrieve, and reuse KV cache blocks based on hash-based prefix caching, reducing redundant prefill computation" — [GitHub Mooncake README](https://github.com/kvcache-ai/Mooncake)
- **Adoption, dated README entries [claim]:**
  - "Dec 19, 2025: Mooncake Transfer Engine has been directly integrated into vLLM v1 as a KV Connector in PD-disaggregated setups."
  - Same date: "integrated into TensorRT LLM for KVCache transfer in PD-disaggregated inference."
  - "Apr 10, 2025: SGLang officially supports Mooncake Transfer Engine for disaggregated prefilling and KV cache transfer."
  - "Jul 20, 2025: Mooncake powers the deployment of Kimi K2 on 128 H200 GPUs with PD disaggregation and large-scale expert parallelism, achieving 224k tokens/sec prefill throughput and 288k tokens/sec decode throughput."
  - [GitHub Mooncake README](https://github.com/kvcache-ai/Mooncake)
- **Weight transfer over the same engine [claim]:** "Apr 29, 2026: SGLang introduces RDMA-based P2P weight transfer for large-scale distributed RL using Mooncake TransferEngine, achieving 7x faster weight updates for the 1T-parameter Kimi-K2 model (53s → 7.2s)" — [GitHub Mooncake README](https://github.com/kvcache-ai/Mooncake)

### Inferences
- **[derived] Link efficiency:**
  - 8×400 Gbps is 3.2 Tb/s, or 400 GB/s at line rate, so 190 GB/s is about 47.5% of aggregate line rate.
  - 4×200 Gbps is 100 GB/s at line rate, so 87 GB/s is about 87%.
  - Moving 40 GB at 190 GB/s takes about 0.21 s.
  - Recomputing the same 128K-token prefill for a 70B model takes roughly 10 s on 8 H100s at 50% MFU (Q6/Q7 arithmetic). At datacenter speeds, fetching state beats recompute by more than an order of magnitude.
- **Mooncake's §6.2 rule is a deployed planner heuristic.** It chooses between a remote reference (fetch the matching prefix's KV) and a recipe (recompute locally) using match length versus local reuse. ARFP's planner is a generalization of that rule.
- **Hash-based block reuse is ARFP's "reference" mode for KV state.** It is content-addressed and valid only within one model, version, and tokenizer.

### Gaps
- The FAST'25 camera-ready's headline figures were not retrieved; the USENIX page was not fetched. They may differ from arXiv v4.
- The arXiv text gives no measured per-request KV transfer latency, per the fetch tool. Figure 7 values were not extracted.
- The GPU and NIC setup behind the README's 87/190 GB/s benchmark was not captured.

---

## Q4. DistServe (OSDI 2024) and Splitwise (ISCA 2024): prefill-to-decode KV transfer size, and the network bandwidth that makes it negligible

### Takeaway
DistServe sizes a single 512-token OPT-66B request's KV cache at about 1.13 GB. At 10 requests/s that needs about 90 Gbps to hide the transfer. The authors note that 800 Gbps InfiniBand and 600 GB/s intra-node A100 links make this a non-issue, and they measured KV transfer at under 0.1% of total latency even on a 25 Gbps testbed. Splitwise gives no absolute size; it says transfer time scales with prompt tokens. It overlaps transfer with compute layer by layer and measured about 5 ms of non-overlapped transfer on H100 (400 Gbps per GPU), 0.8% of end-to-end time. It calls the impact "hardly perceivable", but warns that large prompts can make transfer a significant fraction of time between tokens.

### Cited Findings
- **DistServe [authors' computation] Size (§3.3):** "For example, the KV cache size of a single 512-token request on OPT-66B is approximately 1.13GB." — [arXiv PDF 2401.09670](https://arxiv.org/pdf/2401.09670)
- **DistServe bandwidth needed (§3.3):** "Assuming an average arrival rate of 10 rps, we need to transfer 11.3GB data" … "per second—or equivalently 90Gbps bandwidth to render the overhead invisible." — [arXiv PDF](https://arxiv.org/pdf/2401.09670)
- **DistServe, what makes it negligible (§3.3):**
  - "While many modern GPU clusters for LLMs are equipped with InfiniBand (e.g., 800 Gbps)"
  - Intra-node: "the peak bandwidth between A100 GPUs is 600 GB/s, again rendering" the overhead negligible. The sentence continues past the captured fragment.
  - [arXiv PDF](https://arxiv.org/pdf/2401.09670)
- **[measured] DistServe:**
  - Testbed (§6.1): "The cross-node bandwidth is 25Gbps."
  - §6.3: "even for OPT-175B, the KV Cache transmission only accounts for less than 0.1% of the total" … "latency."
  - "…of requests experience a delay of less than 30ms, despite our testbed having only limited cross-node bandwidth." The leading percentage was not captured.
  - [arXiv PDF](https://arxiv.org/pdf/2401.09670)
- **[measured, best case across settings] DistServe headline:** "DistServe can serve 7.4× more requests or 12.6× tighter SLO, compared to state-of-the-art" … "systems, while staying within latency constraints for > 90% of requests." — [arXiv PDF](https://arxiv.org/pdf/2401.09670)
- **Splitwise size scaling (Sec. IV-C):** "The time required for the transfer depends on the size of the KV cache" … "which is directly proportional to the number of prompt tokens". The fetch tool found no absolute KV size in GB. — [arXiv PDF 2311.18677](https://arxiv.org/pdf/2311.18677)
- **Splitwise mechanism (Sec. IV-C):**
  - "At the end of each layer, we trigger an asynchronous transfer of the KVcache for that layer"
  - "Layer-wise KV-cache transfer happens in parallel with the prompt computation for the next layer."
  - "Splitwise picks the best technique for KV-cache transfer." Per the fetch tool, it uses serialized transfer for small prompts and layer-wise transfer for large ones.
  - [arXiv PDF](https://arxiv.org/pdf/2311.18677)
- **Splitwise bandwidth:**
  - Sec. II-F: "The InfiniBand bandwidth offered in the cloud today ranges from 25 to 50GBps per GPU pair"
  - Sec. V-A: "the DGX-H100s have double the bandwidth (i.e., 400 Gbps)."
  - [arXiv PDF](https://arxiv.org/pdf/2311.18677)
- **[measured] Splitwise overhead (Sec. VI-A):**
  - "Compared to the prompt computation time, the overhead is minimal (< 7%)."
  - "we see a constant non-overlapped transfer time of around 8ms" … "for the A100 and around 5ms for the H100 setup."
  - "Splitwise only incurs 0.8% of E2E."
  - "Splitwise adds a 16.5% latency to the second token," … "as compared to the 64% overhead from a serialized transfer."
  - "Overall, the transfer impact in Splitwise is hardly perceivable even in a user-facing inference."
  - [arXiv PDF](https://arxiv.org/pdf/2311.18677)
- **Splitwise caveats:**
  - Sec. IV-C: "Even when using fast InfiniBand links, the transfer overhead for large prompt sizes" … "could become a significant fraction of the TBT."
  - Sec. VII: "an interconnect with 10× lower bandwidth would likely still be beneficial."
  - [arXiv PDF](https://arxiv.org/pdf/2311.18677)
- **Splitwise headline:** "Splitwise clusters achieve up to" … "1.4× higher throughput at 20% lower cost." "Alternatively, they can deliver 2.35× more throughput under the same power and cost budgets." — [arXiv PDF](https://arxiv.org/pdf/2311.18677)
- **Source inconsistency:** Splitwise's Table I lists InfiniBand as "200GBps" (A100) and "400GBps" (H100), while Sec. V-A says "400 Gbps" for DGX-H100. The fetch tool flagged this as a units conflict. — [arXiv PDF](https://arxiv.org/pdf/2311.18677)

### Inferences
- **[derived] GQA shrinks per-token KV state about 6.7x.** DistServe's figure is 1.13 GB ÷ 512 ≈ 2.2 MB per token for OPT-66B, which uses full multi-head attention. Llama 3.1 70B, which uses grouped-query attention (GQA), needs 320 KiB per token (Q6). DistServe's 90 Gbps figure would fall proportionally for a GQA model.
- **The design pattern in both papers:**
  - Transfer layer by layer and overlap it with compute.
  - Co-locate prefill and decode on NVLink where possible.
  - Accept 25–400 Gbps cross-node links.
  - At datacenter bandwidths, sending raw state is cheap enough that neither paper compresses KV. Compression (CacheGen) matters at roughly 0.4–15 Gbps, the WAN and edge range ARFP targets.
- **Splitwise's "1.4× / 20% lower cost" vs. its conclusion.** Per the fetch tool, the conclusion's "1.76× better throughput with 15% lower power" is a different comparison. Cite the abstract numbers.

### Gaps
- The OSDI 2024 and ISCA 2024 venues were taken from the assignment and not re-verified in the fetched text.
- DistServe's arXiv submission date was not captured; the ID 2401 implies January 2024.
- Whether Splitwise's cluster-level headline numbers come from simulation or hardware was not confirmed.
- The percentage in DistServe's "<30ms" sentence was not captured.

---

## Q5. Thinking Machines Lab, "Defeating Nondeterminism in LLM Inference" (September 2025): root cause, what was built, cost

### Takeaway
Floating-point non-associativity is the underlying mechanism, but the root cause is not concurrency or atomics. The LLM forward pass uses no atomic adds, and each kernel is run-to-run deterministic. The problem is that kernels lack *batch invariance*: a request's numerics depend on batch size, and batch size varies with server load. TML built batch-invariant RMSNorm, matmul, and attention kernels, released as the batch-invariant-ops library and demonstrated in vLLM. In their benchmark, determinism cost about 2.1x wall time unoptimized (55 s vs 26 s) and about 1.6x with an improved attention kernel (42 s).

### Cited Findings
- Author and date: "Horace He", "Sep 10, 2025"; citation line "Thinking Machines Lab: Connectionism, Sep 2025." — [thinkingmachines.ai blog](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)
- **The "concurrency + floating point" hypothesis:**
  - "While this hypothesis is not entirely wrong, it doesn't reveal the full picture."
  - "concurrency (and atomic adds) end up being completely uninvolved in LLM inference nondeterminism!"
  - "the forward pass of an LLM involves no operations that require atomic adds."
  - [blog](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)
- **Root cause:**
  - "the primary reason nearly all LLM inference endpoints are nondeterministic is that the load" … "(and thus batch-size) nondeterministically varies!"
  - "our forward pass lacks "batch invariance""
  - [blog](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)
- **[measured] Demonstration:**
  - "We use Qwen/Qwen3-235B-A22B-Instruct-2507 and sample 1000 completions at temperature 0"
  - "Surprisingly, we generate 80 unique completions"
  - "The first instance of diverging completions occurs at the 103rd token."
  - [blog](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)
- **What they built:**
  - "We provide a demonstration of deterministic inference on top of vLLM" … "by leveraging its FlexAttention backend as well as torch.Library."
  - Library: "thinking-machines-lab/batch-invariant-ops"
  - Matmul: "compile one kernel configuration and use that for all shapes"
  - Attention: "we must adopt a "fixed split-size" strategy."
  - The post also has a batch-invariant RMSNorm section; that is a fetch-tool description, not a quote.
  - [blog](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)
- **Library README:**
  - "This library primarily leverages torch.Library to sub out existing PyTorch kernels with "batch-invariant" ones."
  - Supported ops listed: torch.mm(), torch.addmm(), torch.log_softmax(), torch.mean().
  - [GitHub batch_invariant_ops](https://github.com/thinking-machines-lab/batch_invariant_ops)
- **[measured] vLLM proof of concept:** "Without the upstream PR, we see that out of 1000 random length 100 completions we see 18 unique samples. After the upstream PR, there is only one unique sample." — [GitHub batch_invariant_ops](https://github.com/thinking-machines-lab/batch_invariant_ops)
- **[measured] Cost of determinism:**
  - Setup: "We will set up an API server with one GPU running Qwen-3-8B" and "request 1000 sequences with an output length of between 90 and 110."
  - Results: "vLLM default" 26 s; "Unoptimized Deterministic vLLM" 55 s; "+ Improved Attention Kernel" 42 s.
  - The post does not name the GPU model.
  - [blog](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)
- **[measured] RL payoff:**
  - With bitwise-identical sampling "we are fully on policy (i.e. 0 KL divergence) and can also train smoothly"
  - "our KL-divergence stays flat at 0"
  - Without importance weighting, "our reward collapses partway through training."
  - [blog](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)

### Inferences
- **[derived] Cost ratios:** 55/26 ≈ 2.12x (+112%) unoptimized; 42/26 ≈ 1.62x (+62%) with the improved attention kernel. This is one single-GPU decode-heavy benchmark. Prefill-heavy or multi-GPU (tensor-parallel) costs were not reported in the captured text.
- **For ARFP's runtime classes:**
  - A default production endpoint is class **N** for any given request, even though every kernel is deterministic. Output depends on co-batched traffic the sender cannot see.
  - Class **E** requires batch-invariant kernels on a pinned software and hardware stack, and costs about 1.6–2.1x in TML's benchmark.
  - A recipe (text + model + seed) is reproducible only if the receiver runs in E mode. Otherwise ARFP should treat recipe outputs as N, or T with an empirically measured divergence.
- The 80-of-1000 result is measured on a 235B MoE; the README's 18-of-1000 is on a different vLLM setup. Both show divergence at temperature 0.

### Gaps
- The GPU model for the 26/55/42 s benchmark is not given.
- Whether batch invariance gives bit-exactness *across different GPU types or library versions* is not claimed in the captured text. Their result is run-to-run and trainer/sampler equality on their stack.
- Whether vLLM or SGLang have since shipped batch-invariant modes as stable features (2025–2026) was not checked.

---

## Q6. Llama 3.1 8B and 70B: exact architecture numbers for KV-cache size and prefill compute

### Takeaway
From Meta's official llama-models repo:
- **Llama 3.1 8B:** 32 layers, hidden size 4096, 32 attention heads, 8 KV heads.
- **Llama 3.1 70B:** 80 layers, hidden size 8192, 64 attention heads, 8 KV heads.
- **Head dimension:** 128 for both (hidden ÷ heads).
- **Exact parameter counts** (Hugging Face safetensors metadata): 8,030,261,248 and 70,553,706,496.
- **BF16 KV cache:** 128 KiB per token (8B) and 320 KiB per token (70B). For 70B at 128K tokens that is 40 GiB, which matches Mooncake's independent "40 GB" figure.

### Cited Findings
- **Llama 3.1 8B official arch args:**
  - `core_model_id=CoreModelId.llama3_1_8b`, `huggingface_repo="meta-llama/Llama-3.1-8B"`
  - `"dim": 4096, "n_layers": 32, "n_heads": 32, "n_kv_heads": 8`
  - `"ffn_dim_multiplier": 1.3, "multiple_of": 1024, "norm_eps": 1e-05, "rope_theta": 500000.0, "use_scaled_rope": True`
  - [GitHub meta-llama/llama-models, models/sku_list.py](https://github.com/meta-llama/llama-models/blob/main/models/sku_list.py)
- **Llama 3.1 70B official arch args:**
  - `core_model_id=CoreModelId.llama3_1_70b`, `huggingface_repo="meta-llama/Llama-3.1-70B"`
  - `"dim": 8192, "n_layers": 80, "n_heads": 64, "n_kv_heads": 8`
  - `"ffn_dim_multiplier": 1.3, "multiple_of": 4096, "rope_theta": 500000.0`
  - `pth_file_count=8`
  - [GitHub llama-models sku_list.py](https://github.com/meta-llama/llama-models/blob/main/models/sku_list.py)
- **Exact parameter counts:**
  - Llama-3.1-8B: "safetensors.total: 8030261248" (BF16), repo createdAt "2024-07-14T22:20:15.000Z". — [HF API meta-llama/Llama-3.1-8B](https://huggingface.co/api/models/meta-llama/Llama-3.1-8B)
  - Llama-3.1-70B: "safetensors.total: 70553706496" (BF16). — [HF API meta-llama/Llama-3.1-70B](https://huggingface.co/api/models/meta-llama/Llama-3.1-70B)
- **Model card:**
  - "All model versions use Grouped-Query Attention (GQA) for improved inference scalability."
  - "Model Release Date: July 23, 2024."
  - Sizes: "in 8B, 70B and 405B sizes (text in/text out)".
  - [GitHub llama-models, llama3_1/MODEL_CARD.md](https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/MODEL_CARD.md)
- **Cross-check:** "40 GB of data (equivalent to the size of the KVCache generated by 128k tokens in the LLaMA3-70B model)" — [GitHub Mooncake README](https://github.com/kvcache-ai/Mooncake)

### Inferences
- **Name mapping to HF config.json:** dim → hidden_size; n_layers → num_hidden_layers; n_heads → num_attention_heads; n_kv_heads → num_key_value_heads. head_dim = dim/n_heads = **128** for both models [derived].
- **[derived] KV bytes per token** = 2 (K and V) × layers × KV heads × head_dim × bytes per element.

  | | Llama 3.1 8B | Llama 3.1 70B |
  |---|---|---|
  | Per token (BF16/FP16) | 2×32×8×128×2 = **131,072 B (128 KiB)** | 2×80×8×128×2 = **327,680 B (320 KiB)** |
  | 8K tokens | 1.07 GB (1 GiB) | 2.68 GB |
  | 32K tokens | 4.29 GB | 10.7 GB |
  | 128K tokens (131,072) | 17.2 GB (16 GiB) | 42.9 GB (40 GiB) |

  - FP8 KV halves these figures.
  - The 70B 128K value matches Mooncake's "40 GB", which confirms the arithmetic.
- **[derived] Prefill FLOPs per token.** Uses the standard approximation 2 × params for the dense matmuls, plus causal attention ≈ 2 × layers × L × d_model per token averaged over prompt length L. GQA does not reduce attention FLOPs.

  | | Llama 3.1 8B | Llama 3.1 70B |
  |---|---|---|
  | Linear term | 1.606e10 | 1.411e11 |
  | Attention term | 2.62e5 × L | 1.31e6 × L |
  | L = 8K, attention added | +2.1e9 (+13%) | +1.07e10 (+7.6%) |
  | L = 128K, attention added | +3.4e10 (+214%) | +1.72e11 (+122%) |

- **[derived] Recompute vs. transfer.** Assumes H100 dense BF16 ≈ 989 TFLOPS (Q7) at 50% MFU, i.e. about 4.95e14 FLOP/s, and an 8K prompt.

  | | 8B | 70B (one-GPU-equivalent; BF16 70B weights do not fit on one 80 GB GPU) |
  |---|---|---|
  | Recompute | ≈ 36.8 µs/token (0.30 s per 8K prompt) | ≈ 307 µs/token (2.5 s; ≈ 0.31 s on 8 GPUs) |
  | Send raw KV at 400 Gb/s (50 GB/s) | 2.6 µs/token (21 ms) | 6.6 µs/token (54 ms) |

- **[derived] Break-even link bandwidth per recomputing H100** (raw-KV send time equals recompute time):
  - 8B: ~28 Gb/s at 8K context, ~10 Gb/s at 128K.
  - 70B: ~8.5 Gb/s at 8K, ~4 Gb/s at 128K.
  - CacheGen-style 3.5–4.3x compression lowers each by about 4x, ignoring codec time.
  - Datacenter NICs (400 Gb/s) sit 10–100x above break-even, so ship state. WAN and consumer links (0.01–1 Gb/s) sit below it, so ship text/recipe or compress heavily. This is directionally consistent with CacheGen's 0.4–400 Gbps sweep and text fallback.
  - If the receiver is a phone or laptop with far less compute than an H100, break-even falls in proportion and shipping state becomes attractive again.
- **[derived] The size gap behind ARFP's latent/recipe tension.** A token ID is a few bytes; KV is 128–320 KiB per token. Raw KV is about 10^4–10^5x larger than the token stream that regenerates it, and still about 10^4x after CacheGen compression.

### Gaps
- The HF config.json files themselves were not read. The repos are gated, and the HF API "config" object omits the dimension fields. Values come from Meta's llama-models sku_list.py, an official Meta source.
- The model card's context-length column values and the vocab size (LLAMA3_VOCAB_SIZE) were not extracted.
- The FLOPs formulas are standard approximations, not taken from a fetched source.

---

## Q7. NVIDIA H100 SXM peak dense BF16 Tensor Core TFLOPS, and typical per-GPU network bandwidth

### Takeaway
NVIDIA's current H100 product page lists H100 SXM BF16 Tensor Core at 1,979 TFLOPS, marked "With sparsity". NVIDIA's own spec convention (dense/sparse pairs, where sparse is 2x dense) makes the dense figure ≈ 989 TFLOPS. That number is derived; the datasheet itself was not retrieved. A DGX H100 has 8 single-port ConnectX-7 InfiniBand cards at up to 400 Gb/s for 8 GPUs, so one 400 Gb/s (≈50 GB/s) NIC per GPU. Intra-node NVLink provides 900 GB/s per GPU.

### Cited Findings
- **[spec] H100 product page, SXM / NVL:**
  - "BFLOAT16 Tensor Core*": 1,979 teraFLOPS / 1,671 teraFLOPS
  - "FP16 Tensor Core*": 1,979 / 1,671
  - "FP8 Tensor Core*": 3,958 / 3,341
  - "TF32 Tensor Core*": 989 / 835
  - Memory: 80GB / 94GB; bandwidth 3.35TB/s / 3.9TB/s
  - Interconnect: "NVIDIA NVLink™: 900GB/s, PCIe Gen5: 128GB/s" (SXM)
  - TDP: "Up to 700W (configurable)" (SXM)
  - Asterisk footnote: "With sparsity."
  - [NVIDIA H100 product page](https://www.nvidia.com/en-us/data-center/h100/)
- **[spec, 2022 launch figures] Hopper architecture blog:**
  - Table 3 lists H100 SXM5 "Peak BF16 Tensor TFLOPS with FP32 Accumulate" as 1000/2000.
  - Footnote: "Effective TOPS / TFLOPS using the Sparsity feature". The first number is dense, the second sparse.
  - H100 SXM5 SM count: 132. Published Mar 22, 2022.
  - [NVIDIA Technical Blog, "NVIDIA Hopper Architecture In-Depth"](https://developer.nvidia.com/blog/nvidia-hopper-architecture-in-depth/)
- **[spec] DGX H100 networking:**
  - "4 x OSFP ports for 8 x NVIDIA® ConnectX®-7 Single Port InfiniBand Cards"
  - "InfiniBand (default): Up to 400Gbps"
  - "For H100: 8 x NVIDIA H100 GPUs that provide 640 GB total GPU memory"
  - "4 x 4th generation NVLinks that provide 900 GB/s GPU-to-GPU bandwidth"
  - Per the fetch tool, the guide's network-module table maps each of the 8 OSFP ports to a different GPU (0–7), i.e. one 400 Gb/s port per GPU.
  - [NVIDIA DGX H100 User Guide](https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html)
- **Corroborating per-GPU and per-node bandwidth from the papers:**
  - Splitwise: "the DGX-H100s have double the bandwidth (i.e., 400 Gbps)" and cloud InfiniBand "ranges from 25 to 50GBps per GPU pair". — [Splitwise PDF](https://arxiv.org/pdf/2311.18677)
  - DistServe: "InfiniBand (e.g., 800 Gbps)". — [DistServe PDF](https://arxiv.org/pdf/2401.09670)
  - Mooncake testbed: "up to 800 Gbps of interconnect bandwidth between nodes". — [Mooncake PDF](https://arxiv.org/pdf/2407.00079)
  - Mooncake TE benchmark networks: "4×200 Gbps and 8×400 Gbps RoCE". — [Mooncake README](https://github.com/kvcache-ai/Mooncake)

### Inferences
- **[derived] Dense BF16 ≈ 1,979 ÷ 2 ≈ 989.5 TFLOPS for H100 SXM.**
  - The halving follows NVIDIA's dense/sparse pairing in the Hopper blog.
  - The 2022 blog's rounder 1000/2000 figures predate final specs; treat the current product page as authoritative.
  - Do not confuse this 989 with the product page's TF32 row, which is also 989 but *with* sparsity.
- **[derived] Per-GPU bandwidth:** 400 Gb/s ≈ 50 GB/s scale-out. NVLink at 900 GB/s is about 18x higher, which is why DistServe co-locates prefill and decode over NVLink where possible.
- **[derived] Compute-to-network ratio:** about 989e12 FLOP/s against 50e9 B/s, roughly 2×10^4 FLOP per byte. A KV byte "costs" about 2×10^4 FLOPs to move-equivalently. This feeds the Q6 break-even analysis.

### Gaps
- **NVIDIA's H100 datasheet PDF (resources.nvidia.com) was not retrieved.** I therefore have no verbatim NVIDIA statement of the dense BF16 value (e.g., a "one-half lower without sparsity" footnote). The 989 figure is derived.
- I did not verify the "NDR" naming for 400 Gb/s InfiniBand in fetched text.
- No inference-cluster survey of per-GPU NIC bandwidth was consulted; the claim rests on DGX H100 reference architecture and paper testbeds.

---

## Q8. Published measurements of prefill MFU on H100 for 8B–70B models

### Takeaway
I found no published, primary-source prefill MFU measurement on H100 specifically for 8B–70B models. The closest verified figure is 63% "FLOPS utilization" for Llama 3 405B long-context prefill on up to 128 H100s, from the context-parallelism paper (arXiv 2411.01783). The search was cut short.

### Cited Findings
- **Context-parallelism paper, metadata:** "Context Parallelism for Scalable Million-Token Inference". Submitted 2024-11-04; v3 dated 2025-04-21. — [arXiv abs 2411.01783](https://arxiv.org/abs/2411.01783)
- **[measured] Context-parallelism paper, results:**
  - The method "achieves near-linear scaling for long-context prefill latency with up to 128 H100 GPUs across 16 nodes"
  - "our method achieves 1M context prefill with Llama3 405B model in 77s" … "and 128K context prefill in 3.8s"
  - "(93% parallelization efficiency, 63% FLOPS utilization)"
  - [arXiv abs 2411.01783](https://arxiv.org/abs/2411.01783)
- The paper appears in search results at mlsys.org/virtual/2025/3255, suggesting MLSys 2025. The page was not opened. — [mlsys.org listing](https://mlsys.org/virtual/2025/3255)

### Inferences
- Q6 uses 50% MFU as a round planning assumption for 8B–70B prefill on H100, bracketed by the 63% measured for 405B long-context prefill. Smaller models and shorter prompts likely achieve lower MFU (less arithmetic per launch, more overhead). That is an expectation, not a sourced measurement.
- ARFP's recompute-cost model should take MFU as a measured input per receiver class rather than a constant. Break-even bandwidth scales linearly with it.

### Gaps
- No verified H100 prefill MFU for Llama 3.x 8B or 70B. Candidate sources not checked: Sarathi-Serve, NanoFlow, FlashInfer, vendor MLPerf submissions, and the vLLM, SGLang, and TensorRT-LLM blogs.
- The numeric precision (BF16 vs FP8) behind the 63% figure was not captured.
- The context-parallelism paper's author affiliation was not captured.

---

## Q9. LoRA checkpoint reduction for GPT-3 175B, and compression of fine-tune deltas (BitDelta, DeltaZip)

### Takeaway
LoRA (2021) shrinks a GPT-3 175B fine-tune checkpoint from 350 GB to 35 MB, about 10,000x, with rank 4 on the query and value projections. It can be merged into the base weights so inference latency does not increase. Full fine-tune deltas also compress well:
- **BitDelta (2024):** quantizes the delta to 1 bit without compromising performance, cutting GPU memory by more than 10x, tested up to 70B.
- **DeltaZip:** compresses deltas up to 10x and improves serving throughput 2–12x.

Delta distribution of weights is well established, but it requires the exact base model to already be at the receiver.

### Cited Findings
- **[measured/computed] LoRA checkpoint (Sec. 4.2):** "With r = 4 and only the query and value projection matrices being adapted," … "the checkpoint size is reduced by roughly 10,000× (from 350GB to 35MB)" — [arXiv PDF 2106.09685](https://arxiv.org/pdf/2106.09685)
- **LoRA training memory (Sec. 4.2):** "On GPT-3 175B, we reduce the VRAM consumption during training from 1.2TB to 350GB." — [arXiv PDF](https://arxiv.org/pdf/2106.09685)
- **LoRA abstract:** "LoRA can reduce the number of trainable parameters by 10,000 times and the" … "GPU memory requirement by 3 times." — [arXiv PDF](https://arxiv.org/pdf/2106.09685)
- **LoRA merge (Sec. 4.1):** "When deployed in production, we can explicitly compute and store W = W0 + BA" … "and perform inference as usual." — [arXiv PDF](https://arxiv.org/pdf/2106.09685)
- **BitDelta metadata:** "BitDelta: Your Fine-Tune May Only Be Worth One Bit". Submitted 2024-02-15; v3 dated 2024-10-13. — [arXiv abs 2402.10193](https://arxiv.org/abs/2402.10193)
- **[measured] BitDelta:**
  - "BitDelta, which successfully quantizes this delta down to 1 bit without compromising performance."
  - "dramatically reduces GPU memory requirements by more than 10x"
  - Tested "across Llama-2 and Mistral model families, and on models up to 70B parameters"
  - "showcasing minimal performance degradation over all tested settings"
  - [arXiv abs 2402.10193](https://arxiv.org/abs/2402.10193)
- **DeltaZip metadata:** "DeltaZip: Efficient Serving of Multiple Full-Model-Tuned LLMs". Submitted 2023-12-08; v3 dated 2025-03-25. — [arXiv abs 2312.05215](https://arxiv.org/abs/2312.05215)
- **[measured] DeltaZip:**
  - It works "by aggressively compressing model deltas by up to 10x" "while maintaining high model quality"
  - "DeltaZip achieves 2x to 12x improvement in throughput compared to the state-of-the-art systems."
  - [arXiv abs 2312.05215](https://arxiv.org/abs/2312.05215)
- **Contrast, full-weight transfer at cluster scale [claim]:** SGLang plus Mooncake TransferEngine achieved "7x faster weight updates for the 1T-parameter Kimi-K2 model (53s → 7.2s)". — [GitHub Mooncake README](https://github.com/kvcache-ai/Mooncake)

### Inferences
- **[derived] 350 GB is consistent with 175B parameters × 2 bytes (FP16).**
- **[derived] One bit per weight is a 16x reduction against BF16, before per-matrix scale overhead.** For Llama 3.1 70B, a fully 1-bit delta is about 70.55e9 bits ≈ 8.8 GB versus about 141 GB in BF16. This is an upper-bound illustration; whether BitDelta applies to embeddings and LM head was not verified.
- **For ARFP's "delta" mode:**
  - Base and receiver must share a byte-identical base (content hash).
  - LoRA deltas are exact if merged in the same precision, so class E for the weights. Compute numerics are still governed by Q5.
  - BitDelta and DeltaZip deltas are lossy approximations of the fine-tune, so class T.

### Gaps
- Venues were not verified: LoRA (ICLR 2022?), BitDelta (NeurIPS 2024?), DeltaZip.
- DeltaZip's compression method was not named in the abstract text captured.
- LoRA's exact arXiv submission date was not captured; the ID 2106 implies June 2021.

---

## Q10. Foundation models already on consumer devices (shared receiver-side knowledge): Apple and Gemini Nano

### Takeaway
Both major mobile platforms now ship an OS-managed LLM that third-party developers can call.

**Apple.** The on-device model is about 3B parameters (2025 tech report), with KV-cache sharing and 2-bit quantization-aware training. Developers reach it through the Swift Foundation Models framework, which offers guided generation, tool calling, and LoRA adapter fine-tuning. As of the 2026 docs, the framework also routes to Private Cloud Compute and to custom Core AI models, and it tells developers to version prompts across model updates.

**Gemini Nano.**
- Android: runs in AICore and is callable by third parties through ML Kit GenAI APIs (mostly Beta; Speech recognition Alpha). Limits: a per-app quota, foreground-only use, and specific devices. Multiple Nano versions (v2/v3/v4) are in the field.
- Chrome: exposes built-in AI APIs to web pages. Translator, Language Detector, and Summarizer are stable since Chrome 138. The Prompt API is on the web from Chrome 148 and in extensions from 138. Writer, Rewriter, and Proofreader are in developer trial.

### Cited Findings
- **[claim, vendor tech report, July 2025] Apple on-device model:**
  - "a ∼3B-parameter on-device model optimized for Apple silicon"
  - Uses "architectural innovations such as KV-cache sharing and 2-bit quantization-aware training"
  - Server model: "a scalable server model built on a novel Parallel-Track Mixture-of-Experts (PT-MoE) transformer"
  - [Apple ML Research, "Apple Intelligence Foundation Language Models Tech Report 2025"](https://machinelearning.apple.com/research/apple-foundation-models-tech-report-2025)
- **Apple framework (2025 report):** "A new Swift-centric Foundation Models framework exposes guided generation" … "constrained tool calling, and LoRA adapter fine-tuning." — [Apple ML Research](https://machinelearning.apple.com/research/apple-foundation-models-tech-report-2025)
- **Apple developer docs (2026; page cites WWDC 2026 sessions, © 2026), access:**
  - "The Foundation Models framework provides access to any large language model, like the on-device and Private Cloud Compute models designed for Apple Intelligence."
  - "When you need more reasoning capabilities and context size, use Private Cloud Compute or any server model provider."
  - "To use Apple Foundation Models, people need a device that supports Apple Intelligence."
  - SystemLanguageModel: "An on-device Apple Foundation Model capable of text generation tasks."
  - [Apple Developer, FoundationModels](https://developer.apple.com/documentation/foundationmodels)
- **Apple developer docs, versioning and KV state:**
  - "Manage the prompts your app uses by versioning them to make the most out of model improvements." (article "Updating prompts for new model versions")
  - "Prevent repeated token processing by preserving the cached state across turns." (article "Optimizing key-value caching in language model sessions")
  - "Send requests on device to an open source model you export with Core AI to get a consistent API experience."
  - [Apple Developer, FoundationModels](https://developer.apple.com/documentation/foundationmodels)
- **Android Gemini Nano (page last updated 2026-10-08):**
  - "Gemini Nano runs in Android's AICore system service"
  - "ML Kit's GenAI APIs harness the power of Gemini Nano to help your apps perform"
  - Constraints: "on-device constraints such as token limits, device hardware limitations, and" … "inference speed depends on device hardware."
  - Hybrid inference via Firebase AI Logic can "Automatically route requests to Gemini Flash or" Pro in the cloud.
  - [Android Developers, Gemini Nano](https://developer.android.com/ai/gemini-nano)
- **ML Kit GenAI status and devices (page last updated 2026-10-08):**
  - Status: "Summarization (Beta)", "Proofreading (Beta)", "Rewriting (Beta)", "Image description (Beta)", "Speech recognition (Alpha)", "Prompt (Beta)".
  - Devices include "Google: Pixel 11, Pixel 11 Pro, Pixel 11 Pro XL, Pixel 11 Pro Fold, Pixel 10," and "Samsung: Galaxy S25, Galaxy S25+, Galaxy S25 Ultra, Galaxy S26, Galaxy S26+, Galaxy S26 Ultra, Galaxy Z Flip8,".
  - The Prompt API device table is split by nano-v2, nano-v3, and nano-v4 model versions (fetch-tool description).
  - [Google ML Kit GenAI](https://developers.google.com/ml-kit/genai)
- **ML Kit GenAI limits:**
  - "AICore enforces an inference quota per app."
  - "GenAI API inference is permitted only when the app is the top foreground application."
  - "No additional server cost incurred for each API call"
  - [Google ML Kit GenAI](https://developers.google.com/ml-kit/genai)
- **Chrome built-in AI overview:**
  - "With built-in AI, your browser provides and manages foundation and expert models."
  - "Review the APIs and their availability status to use with Gemini Nano in Chrome."
  - [Chrome for Developers, Built-in AI](https://developer.chrome.com/docs/ai/built-in)
- **Chrome per-API status (Web / Extensions):**

  | API | Web | Extensions |
  |---|---|---|
  | Translator | "Chrome 138" | "Chrome 138" |
  | Language Detector | "Chrome 138" | "Chrome 138" |
  | Summarizer | "Chrome 138" | "Chrome 138" |
  | Writer | "Developer trial" | "Developer trial" |
  | Rewriter | "Developer trial" | "Developer trial" |
  | Prompt API | "Chrome 148" | "Chrome 138" |
  | Prompt API sampling parameters | "Origin trial for sampling parameters" | "Chrome 148" |
  | Proofreader | "Developer trial" | "Developer trial" |

  - The page also says "The built-in foundation model is a generative AI model."
  - The page's last-updated date as reported by the fetch tool is internally inconsistent and predates Chrome 148. Treat the table as current but the date as unreliable.
  - [Chrome for Developers, Built-in AI APIs](https://developer.chrome.com/docs/ai/built-in-apis)
- **Chrome hardware requirements and model lifecycle:**
  - OS: "Windows 10 or 11; macOS 13+ (Ventura and onwards);" "Linux; or ChromeOS (from Platform 16389.0.0 and onwards) on"
  - Storage: "At least 22 GB of free space on the volume that contains your Chrome profile."
  - GPU: "Strictly more than 4 GB of VRAM." CPU alternative: "16 GB of RAM or more and 4 CPU cores or more."
  - Download: "The first time a user interacts with these APIs, the model must be downloaded to the browser."
  - Removal: "If the available storage space falls to less than 10 GB after the download, the model is removed from your device." "The model redownloads once the requirements are met."
  - Header dates: published Dec 12, 2024; last updated May 20, 2025.
  - [Chrome for Developers, Get started](https://developer.chrome.com/docs/ai/get-started)

### Inferences
- **These OS-managed models are ARFP's "shared receiver-side knowledge".** A sender can ship a short recipe (prompt + schema) instead of bytes, and the receiver expands it locally at no per-call server cost (Android: "No additional server cost").
- **The shared knowledge is versioned and heterogeneous:**
  - Nano v2/v3/v4 coexist across devices.
  - Apple tells developers to version prompts for "new model versions".
  - Chrome can evict the model when storage is low.
  - Recipes against these runtimes should therefore be class **N** across devices unless the planner pins (model-version, runtime) and verifies them. At best they are class **T** with application-level validation such as Apple's guided generation into typed structures.
- **None of these runtimes exposes reusable KV state across devices.** Apple's KV-caching article concerns caching within a session. So the "latent" mode (shipping KV state) cannot target consumer runtimes through public APIs; only "recipe" mode can. This is my reading of the fetched docs.
- **[derived, rough] Apple's ~3B model at 2-bit QAT is roughly 0.75 GB if uniformly 2-bit.** This is likely an under-estimate if some layers stay in higher precision. It shows why OS-level sharing of one copy, rather than per-app bundling, matters for distribution.
- **Third-party access to Gemini Nano: yes.** On Android it goes through ML Kit GenAI (Beta/Alpha) with quota and foreground limits. In Chrome it goes through the built-in AI web and extension APIs, with Prompt API web stable from Chrome 148 per the status table.

### Gaps
- **2026 Apple on-device model generation and parameter count:** I found no primary source. Secondary sites mention an "AFM 3" at WWDC 2026 (e.g., letsdatascience.com) but were not verified. The 2025 report's ~3B figure may be superseded.
- **Gemini Nano parameter counts (any version):** not retrieved from a primary source.
- **Chrome Prompt API:** the release date for Chrome 148 and whether all web origins can use it without an origin-trial token were not confirmed beyond the status table.
- **Apple Foundation Models context-window size and OS-version availability:** not captured; the docs' sub-pages were not opened.
