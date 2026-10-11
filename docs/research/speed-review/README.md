# Research notes behind the speed review

Compiled 2026-10-11 for the [ARFP internet speed review](../../analysis/ARFP-internet-speed-review.md). Each note answers a set of research questions with short verbatim quotes, each linked to its source and labeled by evidence type (specification, lab, production, vendor, simulation or claim). The speed review's sourced claims were checked against these quotes, and 11 load-bearing claims against the original pages.

| Note | Covers |
|---|---|
| [internet_time_and_web_protocols.md](internet_time_and_web_protocols.md) | Where time and bytes go: round trips versus bandwidth (Belshe), video's share of traffic, page weight, RFC 9842 compression dictionaries, Courgette, handshake round trips and 0-RTT, the speed of light in fiber, HTTP/2 Server Push's removal and 103 Early Hints, page-load time breakdowns |
| [receiver_state_protocols.md](receiver_state_protocols.md) | Receiver-state-aware transfer: compact block relay (BIP 152), Graphene, Erlay and minisketch, set reconciliation, Bloom filters and Golomb-coded sets, HTTP Cache Digests, rsync, Git fetch negotiation |
| [ai_infrastructure_state_transfer.md](ai_infrastructure_state_transfer.md) | AI state transfer: CacheGen, LMCache and CacheBlend, Mooncake, DistServe and Splitwise, inference nondeterminism (Thinking Machines), Llama 3.1 KV-cache sizes, H100 compute and network bandwidth, prefill MFU, LoRA and fine-tune delta compression, on-device foundation models |
| [generative_reconstruction_precedents.md](generative_reconstruction_precedents.md) | Generative and model-based reconstruction: face-vid2vid, NAS, Gemino, AV1 film grain synthesis, Codec Avatars, Draco and 3D Tiles, lockstep and client prediction in games, 6G semantic communication, RTX Video Super Resolution |

The tools used to collect the quotes capped quote length, so many long sentences appear as fragments joined by "…". These are working notes: findings are as reported by each source, not reproduced here.
