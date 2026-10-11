# Receiver-state-aware transfer: compact block relay, set reconciliation, and compact state summaries

Research date: 2026-10-11. These notes feed the ARFP engineering review. ARFP receivers advertise state so senders can send references and deltas, and ARFP currently waits one round trip (OFFER, then ACCEPT) before sending payload.

**Evidence tags.** Each finding carries one tag:

| Tag | Meaning |
|---|---|
| [SPEC] | Normative or specification text |
| [MEASURED] | Empirical result the source reports (deployment, testbed or experiment) |
| [SIM] | Simulation result |
| [CLAIM] | Expectation or assertion with no data in the quoted text |
| [ANALYSIS] | Mathematical derivation in the source |
| [COMPUTED] | My own arithmetic from sourced formulas; not stated by the source |

**How exact the quotes are.**
- **Downloaded directly, exact text:** quotes from `raw.githubusercontent.com` URLs (bitcoin/bips, bitcoin/bitcoin, sipa/minisketch, git/git). I removed only wiki/HTML markup such as `''`, `<code>` and `<sup>`; the wording is unchanged.
- **Extracted through a web-fetch tool:** quotes from every other URL. Direct download from arxiv.org, ietf.org, samba.org, git-scm.com, bitcoincore.org, ics.uci.edu and acm.org was blocked in the research environment. The tool returns quoted fragments that appear to be verbatim. They were not individually re-checked against the sources; the speed review's verification re-checked 11 of its load-bearing claims against the original pages. Where a fetch could not return an exact sentence, I say so.

**Comparison at a glance.** Every cell is sourced in the sections below.

| Protocol | How the sender learns receiver state | Summary size | Round trips: best case / on a miss | What happens on a miss | Evidence |
|---|---|---|---|---|---|
| BIP 152, high-bandwidth (HB) mode | Receiver opts in once per connection (`sendcmpct` with first flag = 1). Sender assumes the receiver's mempool contains the block's transactions | 6 bytes per transaction, plus header, an 8-byte nonce, and prefilled transactions (up to 10 KB) | 0.5 RTT / 1.5 RTT | `getblocktxn`/`blocktxn`, or the full block. A short-ID collision falls back to normal inv/header relay | Spec, plus informal 2016 tests |
| BIP 152, low-bandwidth (LB) mode | Same; the block is announced first, then requested | Same | 1.5 RTT / at least 2.5 RTT | Same | Same |
| Graphene | Receiver sends its mempool transaction count *m* with its request | Bloom filter + IBLT. The tech report claims about 12% of deployed systems' bandwidth for larger blocks | About 1.5 RTT (inferred) / +1 RTT (Protocol 2) | Protocol 2: receiver sends a second Bloom filter | Analysis, simulation, and a Bitcoin Cash deployment |
| Erlay / BIP 330 | Periodic reconciliation. Initiator sends its set size and *q*; responder sends a sketch | 4 bytes per unit of capacity (32-bit IDs). Capacity ≈ estimated difference + 1, usually ≤ 20, so ≤ 80 bytes | At least 1 RTT per round, plus a batching timer / +1 extension round | Sketch extension; if that fails, announce everything by flooding | Simulation + 100-node testbed |
| Difference Digest (Eppstein et al.) | Strata Estimator plus an IBF (invertible Bloom filter) | 15.3 KB fixed + about 24 bytes per difference | "one round" as designed | Probabilistic decode failure; overprovision cells | Experiments |
| rsync | Receiver sends a checksum pair for each block of its old file | 20 bytes per block of S bytes | One exchange per file, pipelined across files | Unmatched regions sent as literal data | 1996-era experiments |
| Git fetch | Client sends "have" commit IDs in rounds | One have line per commit; batch size grows each round | Several rounds | Gives up after 256 unacknowledged haves and takes everything; `skipping` trades bytes for fewer rounds | Spec + source code |
| HTTP Cache Digests | Client sends a digest of its cache | Golomb-Rice set (-00) or Cuckoo filter (-05) | No extra RTT | Server may push anyway, or push a 304 | Dead draft (2019) |

## 1. BIP 152 Compact Block Relay: short ID size, high- vs low-bandwidth mode, mempool reconstruction, getblocktxn/blocktxn fallback, measured improvements

### Takeaway
BIP 152 (assigned 2016-04-27, status Deployed, implemented in Bitcoin Core 0.13.0) relays a block as its header plus a 6-byte (48-bit) salted SipHash short ID per transaction. The receiver rebuilds the block from its mempool and fetches only the misses, with one extra `getblocktxn`/`blocktxn` round trip. High-bandwidth mode pushes the compact block unsolicited to up to 3 opted-in peers: 0.5 RTT best case, 1.5 RTT on a miss. Low-bandwidth mode announces first: 1.5 RTT best case, at least 2.5 RTT on a miss. The only performance numbers found are informal 2016 developer test figures, not a rigorous measurement study.

### Cited Findings
**Status, dates, and goal**
- [SPEC] Header: "BIP: 152 … Title: Compact Block Relay … Authors: Matt Corallo … Status: Deployed … Assigned: 2016-04-27" — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)
- [SPEC] Abstract: "Compact blocks on the wire as a way to save bandwidth for nodes on the P2P network." — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)
- [CLAIM] Latency is a side effect, not the goal: "While the goal of this work is explicitly not to reduce block transfer latency, it does, as a side effect reduce block transfer latencies in some rather significant ways." — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)
- [SPEC] Design choice: "Because this work is not focused primarily on reducing block relay time, its design is much simpler (ie does not rely on set reconciliation protocols)." — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)
- Shipped in Bitcoin Core 0.13.0: "Support for block relay using the Compact Blocks protocol has been implemented in PR 8068." and "The primary goal is reducing the bandwidth spikes at relay time". The same changelog lists "#8408 `b7e2011` Prevent fingerprinting, disk-DoS with compact blocks (sdaftuar)". — [Bitcoin Core 0.13.0 release notes](https://raw.githubusercontent.com/bitcoin/bitcoin/master/doc/release-notes/release-notes-0.13.0.md)

**Short IDs: size and collision handling**
- [SPEC] "Short transaction IDs are used to represent a transaction without sending a full 256-bit hash." The final derivation step is "Dropping the 2 most significant bytes from the SipHash output to make it 6 bytes." — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)
- [SPEC] Wire fields: `shortids` is a "List of 6-byte integers" taking "6*shortids_length bytes". `nonce` is "uint64_t … 8 bytes … A nonce for use in short transaction ID calculations". — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)
- [SPEC] Why ID size matters: "cmpctblock messages are never optional in this protocol, and contain a short ID for each non-prefilled transaction in the block. Thus, the size of short IDs is directly proportional to the maximum bandwidth savings possible." — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)
- [ANALYSIS] Salting: "We truncate the output from SipHash-2-4 to 48 bits (see next section) in order to minimize space. The resulting 48-bit hash is certainly not large enough to avoid intentionally created individual collisions, but by using the block hash as a key to SipHash, an attacker cannot predict what keys will be used…" and "We mix in a per-connection 64-bit nonce to obtain independent short IDs on every connection… The mixing is done using SHA256(block_header || nonce)". — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)
- [ANALYSIS] Sizing rule: "we need log2(F * m * t) bits hash functions." and "B = 48 bits short IDs suffice for blocks with up to t = 10000 transactions, mempools up to m = 100000 transactions, with failure to reconstruct at most one in F = 281474 blocks. Since failure to reconstruct just means we fall back to normal inv/header based relay, it isn't necessary to avoid such failure completely." — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)
- [COMPUTED] log2(281474 × 100000 × 10000) = 48.00 bits, which matches the BIP's choice.
- [ANALYSIS] Ambiguous matches cost a request rather than an error: "In cases 2, 3, or 4, we request the full transaction because we know we're uncertain. Only in case 5, we fail to reconstruct." Also: "short transaction IDs are expected to occasionally collide, and that nodes MUST NOT be penalized for such collisions". — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)

**High-bandwidth vs. low-bandwidth mode, with round trips**
- [SPEC] High-bandwidth: "peers send new block announcements with the short transaction IDs already (via a cmpctblock message), possibly even before fully validating the block… In some cases no further round-trip is needed, and the receiver can reconstruct the block and process it as usual immediately. When some transactions were not available from local sources (ie mempool), a getblocktxn/blocktxn roundtrip is necessary, bringing the best-case latency to the same 1.5*RTT minimum time that nodes take today, though with significantly less bandwidth usage." — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)
- [SPEC] 0.5 RTT and the peer cap: "sending a sendcmpct message with the first integer set to 1 to up to 3 peers is RECOMMENDED… allowing nodes to receive blocks which come from those peers in only 0.5*RTT." and "Nodes MUST NOT send such sendcmpct messages to more than three peers, as it encourages wasting outbound bandwidth across the network." — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)
- [SPEC] Low-bandwidth: "peers send new block announcements with the usual inv/headers announcements (as per BIP130, and after fully validating the block). The receiving peer may then request the block using a MSG_CMPCT_BLOCK getdata request… taking the same 1.5*RTT minimum time that nodes take today… When some transactions were not available from local sources (ie mempool), a getblocktxn/blocktxn roundtrip is necessary, bringing the latency to at least 2.5*RTT in this case". — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)
- [CLAIM] "Because TCP often exhibits worse transfer latency for larger data sizes (as a multiple of RTT), total latency is expected to be reduced even when the full 2.5*RTT transfer mechanism is used." Also: "Nodes with limited inbound bandwidth SHOULD request blocks using MSG_CMPCT_BLOCK/getblocktxn requests… While this increases worst-case message round-trips, it is expected to reduce overall transfer latency". — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)
- [SPEC] Validation trade-off in high-bandwidth mode: it "permits relaying of CMPCTBLOCK messages prior to full validation (requiring only that the block header is valid before relay)", so nodes "SHOULD NOT ban a peer for announcing a new block with a CMPCTBLOCK message that is invalid, but has a valid header." — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)

**Mempool reconstruction and the miss path**
- [SPEC] "nodes SHOULD calculate the short transaction ID for each unconfirmed transaction they have available (ie in their mempool) and compare each to each short transaction ID in the cmpctblock message." Then: "nodes which do not have all transactions available to reconstruct the full block SHOULD request the missing transactions using a getblocktxn message." — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)
- [SPEC] Sender obligation: "A node MUST NOT send a cmpctblock message unless they are able to respond to a getblocktxn message which requests every transaction in the block." The responder "MUST respond with either an appropriate blocktxn message, or a full block message." — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)
- [SPEC] Prefilling the likely misses: prefilled transactions are "Used to provide the coinbase transaction and a select few which we expect a peer may be missing", and "Nodes sending cmpctblock messages SHOULD limit prefilledtxn to 10KB of transactions. When in doubt, nodes SHOULD only include the coinbase transaction in prefilledtxn." — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)

**Measured results vs. expectations**
- [MEASURED, informal; no method given] "Still, in testing at the time of writing, nodes are able to relay blocks without the extra getblocktxn/blocktxn RTT around 90% of the time." — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)
- [CLAIM] "With a smart compact-block-announcement policy, it is thus expected that this work might allow blocks to be relayed between nodes in 0.5*RTT instead of 1.5*RTT at least 75% of the time." — [BIP 152](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0152.mediawiki)
- [MEASURED, informal] Bitcoin Core Compact Blocks FAQ (published June 7, 2016; no author named): "An average full 1MB block announcement can be reconstructed by the receiving node with a block sketch of 9KB" "plus overhead for each transaction in the block that is not in the receiving node’s mempool." and "The largest block sketches seen top out at a few bytes north of 20KB." — [Compact Blocks FAQ](https://bitcoincore.org/en/2016/06/07/compact-blocks-faq/)
- [MEASURED, informal] Same FAQ: "When running live experiments in ‘high bandwidth’ mode and having nodes prefill up to 6 transactions," "we can expect to see well over 90% of blocks propagate immediately without needing to request any missing transactions." Also: "Even without prefilling any transactions except for the coinbase," "experiments show we can see well north of 60% of blocks propagate immediately," "the rest requiring a full additional network round trip." — [Compact Blocks FAQ](https://bitcoincore.org/en/2016/06/07/compact-blocks-faq/)
- [CLAIM] Same FAQ: "Since the difference between mempools and blocks for warmed up nodes is rarely more than 6 transactions," "this means that compact block relay achieves a dramatic reduction in required peak bandwidth." — [Compact Blocks FAQ](https://bitcoincore.org/en/2016/06/07/compact-blocks-faq/)
- [Anecdotal] Same FAQ, on an earlier Bloom-filter approach (BIP 37 filtered blocks): "It was also implemented by Pieter Wuille (sipa) in 2013 but he found the overhead made it slow down the transfer." — [Compact Blocks FAQ](https://bitcoincore.org/en/2016/06/07/compact-blocks-faq/)

### Inferences
- **Precedent for skipping OFFER/ACCEPT.** High-bandwidth mode is the deployed answer to ARFP's question. The per-transfer offer/accept exchange is replaced by a one-time, per-connection opt-in (`sendcmpct`). After that, the sender pushes references optimistically, betting that the receiver already holds most items. The cost is 0.5 RTT in the best case and exactly one extra RTT on a miss.
- **Guardrails BIP 152 pairs with that bet.** ARFP would plausibly need equivalents of each:
  - Cap unsolicited pushes to a few chosen peers (≤3), to limit duplicate outbound bytes.
  - The sender must be able to serve every referenced item ("MUST NOT send cmpctblock unless…").
  - Prefill the items the receiver is likely missing (≤10 KB).
  - Use per-connection salted truncated hashes, so an attacker cannot engineer reference collisions.
  - Treat a failed reconstruction as a fallback to full transfer, not as an error.
- **Size estimate [COMPUTED].** At 6 bytes per transaction, the FAQ's "9KB" average sketch corresponds to about 1,500 short IDs. The FAQ does not state the transaction count, so this is consistency only.
- **Fingerprinting.** The 0.13.0 changelog item "Prevent fingerprinting… with compact blocks" suggests state-dependent relay created a fingerprinting surface in practice. The PR details were not retrieved.

### Gaps
- No peer-reviewed or systematic measurement of BIP 152 latency or bandwidth was found. The 90% and 60% figures are informal 2016 developer tests with no methodology. Present-day (2026) reconstruction rates were not found.
- Bitcoin Core 0.13.0's release date was not verified from fetched text.
- The BIP's protocol-flow diagram (image) was not inspected.
- The details of PR #8408 (the fingerprinting fix) were not retrieved.

## 2. Graphene (Ozisik et al., ACM SIGCOMM 2019): bytes vs. compact blocks; the Bloom filter + IBLT method

### Takeaway
Graphene replaces per-transaction short IDs with a Bloom filter S, which lets the receiver pick candidate transactions out of its mempool, plus an IBLT I that repairs the Bloom filter's false positives. Both are sized from the receiver's reported mempool count. The extended tech report claims "for larger blocks, Graphene uses 12% of the bandwidth of existing deployed systems". It also reports a Bitcoin Cash deployment in which all 3,151 Graphene blocks decoded. Exact published numbers relative to compact blocks could not be extracted from the SIGCOMM camera-ready version.

### Cited Findings
- **Bibliographic (OpenAlex record).** Title "Graphene"; publication_date 2019-08-14; venue "Proceedings of the ACM Special Interest Group on Data Communication"; authors in order A. Pinar Ozisik, Gavin Andresen, Brian N. Levine, Darren Tapp, George Bissias, Sunny Katkuri; DOI 10.1145/3341302.3342082. — [OpenAlex](https://api.openalex.org/works/doi:10.1145%2F3341302.3342082)
- [CLAIM] Published abstract (rebuilt from OpenAlex's inverted index, so near-verbatim): "Through the novel combination of a Bloom filter and an Invertible Bloom Lookup Table (IBLT), Graphene uses a fraction of the network bandwidth used by deployed work for one- and two-way synchronization." — [OpenAlex](https://api.openalex.org/works/doi:10.1145%2F3341302.3342082)
- [ANALYSIS claim] Same abstract: "We show that, for this specific problem, Graphene is more efficient at reconciling n items than using a Bloom filter at the information theoretic bound." It also says the authors contribute an algorithm to parameterize "an IBLT so that it is optimally small in size and meets a desired decode rate with arbitrarily high probability." — [OpenAlex](https://api.openalex.org/works/doi:10.1145%2F3341302.3342082)
- **Source version.** The detailed numbers below come from UMass tech report UM-CS-2019-001. Its first page shows "UM-CS, 2019-001" and states: "This submission extends and improves upon the authors' previous workshop paper [2]." It does not name SIGCOMM. — [Graphene TR](https://web.cs.umass.edu/publication/docs/2019/UM-CS-2019-001.pdf)
- [CLAIM/ANALYSIS] "For example, for larger blocks, Graphene uses 12% of the bandwidth of existing deployed systems." Also: "Graphene is significantly lower in cost than Compact Blocks, as we show in Section 5.3." — [Graphene TR](https://web.cs.umass.edu/publication/docs/2019/UM-CS-2019-001.pdf)
- [SPEC/method] Protocol 1 steps: "2: Receiver: The receiver requests the unknown block, including a count of transactions in her mempool, m." Then: "3: Sender: The sender creates Bloom filter S and IBLT I". Then: "4: Receiver: The receiver creates a candidate set Z of transaction IDs that pass through S". — [Graphene TR](https://web.cs.umass.edu/publication/docs/2019/UM-CS-2019-001.pdf)
- [SPEC/method] Miss path: "Protocol 2 begins when Protocol 1 fails: the receiver requests missing transactions using a second Bloom filter;" and "However, Graphene may use an additional roundtrip time to repair missing transactions." — [Graphene TR](https://web.cs.umass.edu/publication/docs/2019/UM-CS-2019-001.pdf)
- [SPEC/parameter] Decode-failure target: "For all trials, we used a bound of β = 239/240 (see Eqs. 18 and 30)." and "with decode failure rate of 1 − p = 1/240." — [Graphene TR](https://web.cs.umass.edu/publication/docs/2019/UM-CS-2019-001.pdf)
- [MEASURED, deployment] "Fig. 9 shows results from our own peer running the protocol on the real network from January 9–31, 2019." "Out of 3,151 Graphene blocks, all decoded successfully." "the costs of Graphene are almost flat as block size increases." Fig. 9's average sizes are not stated numerically in the text. — [Graphene TR](https://web.cs.umass.edu/publication/docs/2019/UM-CS-2019-001.pdf)

### Inferences
- **Round trips.** Protocol 1 is announce, then a request carrying *m*, then S + I. That is the same 1.5-RTT shape as BIP 152 low-bandwidth mode; I found no unsolicited 0.5-RTT variant. Graphene saves bytes, not round trips, and a miss costs another round (Protocol 2).
- **Minimal receiver advertisement.** The receiver advertises only one scalar, its mempool size *m*. The sender uses it to size the Bloom filter and IBLT. This is a very cheap "receiver advertises a summary statistic" pattern ARFP could copy for sizing summaries.
- **Why savings grow with block size.** Cost depends on a Bloom filter at a few bits per element plus an IBLT proportional to expected false positives. Compact blocks pay a fixed 6 bytes per transaction. That is consistent with the "for larger blocks" qualifier on the 12% claim.
- **Failure budget.** Graphene accepts a nonzero designed decode-failure rate (1/240) in exchange for bytes. ARFP would need an explicit failure budget and a repair round if it adopted IBLT-style summaries.

### Gaps
- The SIGCOMM 2019 camera-ready PDF was not retrieved (ACM DL blocked). The numbers come from the UMass tech report, which may differ from the published version.
- The text does not state per-block byte sizes for Graphene vs. compact blocks in the deployment; they appear only in Fig. 9.
- Neither the tech report nor the abstract states an explicit round-trip count; the 1.5 RTT above is my inference.
- Graphene's deployment status in 2026 (Bitcoin Cash / Bitcoin Unlimited) was not checked.

## 3. Erlay (Naumenko et al., ACM CCS 2019), BIP 330, and minisketch: bandwidth savings; sketch size vs. capacity and bits per element

### Takeaway
Erlay replaces most per-peer transaction announcement flooding with periodic set reconciliation using PinSketch/minisketch.
- **Bandwidth:** the paper reports 40% overall node bandwidth savings at current connectivity, and 84% less announcement bandwidth in simulation.
- **Latency cost:** +2.6 s propagation latency in simulation (3.15 s to 5.75 s), and +0.2 s on a 100-node testbed.
- **Sketch size:** for capacity *c* (maximum decodable differences) and *b*-bit elements, a sketch is exactly *b·c* bits regardless of set size. BIP 330 uses 32-bit IDs, so 4*c* bytes.
- **Decode cost:** quadratic.
- **Status:** BIP 330 is still "Draft". As of September 2026, the full Erlay implementation PR in Bitcoin Core (#35591) is open and marked "[DO NOT MERGE]".

### Cited Findings
**Bibliographic and status**
- **arXiv:** "Bandwidth-Efficient Transaction Relay for Bitcoin" by Gleb Naumenko, Gregory Maxwell, Pieter Wuille, Alexandra Fedorova, Ivan Beschastnikh. Submitted 2019-05-25; v2 2019-06-03. — [arXiv 1905.10518](https://arxiv.org/abs/1905.10518)
- **CCS version:** OpenAlex lists title "Erlay", publication_date 2019-11-06, venue "Proceedings of the 2019 ACM SIGSAC Conference on Computer and Communications Security", DOI 10.1145/3319535.3354237, same authors. — [OpenAlex](https://api.openalex.org/works/doi:10.1145%2F3319535.3354237)
- [SPEC] BIP 330 header: "Title: Transaction announcements reconciliation … Authors: Gleb Naumenko … Pieter Wuille … Status: Draft … Assigned: 2019-09-25". — [BIP 330](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0330.mediawiki)
- [SPEC] BIP 330 differs from the paper: "Note that what we are going to describe here is a modified version from the protocol (it is different from what is presented in the paper)." — [BIP 330](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0330.mediawiki)
- **2026 status** (GitHub mirror): PR "[DO NOT MERGE] Erlay: bandwidth-efficient transaction relay protocol (Full implementation) #35591" by sr-gi. It is open, labelled "Needs rebase", with last activity on September 25, 2026. Its description says: "This is not to be merged. Functionality will be spread across multiple smaller PRs to ease the review process." — [PR #35591 mirror](https://mirror.b10c.me/bitcoin-bitcoin/35591/)

**Problem and headline results**
- [SPEC] "Currently in the Bitcoin network, every 32-byte transaction ID is announced in at least one direction between every pair of connected peers, via INV messages. This results in high cost of announcing transactions: O(nodes * connections_per_node)." — [BIP 330](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0330.mediawiki)
- [CLAIM/MEASURED] "Half of the total bandwidth needed to operate a Bitcoin node is currently used to just announce transactions." and "transaction announcements account for 30–50% of the overall Bitcoin traffic." — [Erlay PDF](https://arxiv.org/pdf/1905.10518)
- [SIM] "reduces the bandwidth consumption by 40% assuming current connectivity," — [Erlay PDF](https://arxiv.org/pdf/1905.10518)
- [SIM] "Erlay reduces the bandwidth used to announce transactions by 84% immediately," — [Erlay PDF](https://arxiv.org/pdf/1905.10518). The fetch tool reported that this 84% figure comes from the simulator.
- [SIM] "while increasing the latency for transaction dissemination by 2.6s (from 3.15s to 5.75s)." — [Erlay PDF](https://arxiv.org/pdf/1905.10518)
- [MEASURED, testbed] "We used a network of 100 Azure nodes located in 6 data centers," and "Erlay introduced a latency increase of 0.2 seconds, while saving 40% of the overall node bandwidth." — [Erlay PDF](https://arxiv.org/pdf/1905.10518)
- [SIM/MEASURED] "The end-to-end probability of reaching fallback is below 1%." and "Fig. 12 illustrates that Erlay's estimate is correct 96% of the time." — [Erlay PDF](https://arxiv.org/pdf/1905.10518)

**Protocol timing**
- Paper parameters: "We use a value of 1 second for T in Erlay." "Every node initiates reconciliation with one outbound peer every T seconds." "we limit the flooding done by public nodes to eight outbound connections". — [Erlay PDF](https://arxiv.org/pdf/1905.10518)
- [SPEC] BIP 330 round structure:
  - "1) every node keeps a reconciliation set for each peer, in which transactions are placed which would have been announced using INV messages absent this protocol 2) once in a while every node chooses a peer from its reconciliation queue to reconcile with… 3) after every reconciliation round, the corresponding reconciliation set is cleared"
  - Messages: "Several new protocol messages are added: sendtxrcncl, reqrecon, sketch, reqsketchext, reconcildiff."
  - "No new "reqrecon" message can be sent until a "reconcildiff" message is sent."
  - Source: [BIP 330](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0330.mediawiki)

**Sketch size as a function of capacity and bits per element**
- [SPEC] "A sketch of nonzero b-bit elements with capacity c can be stored in bc bits." — [BIP 330](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0330.mediawiki); minisketch says the same: "A sketch of b-bit elements with capacity c can be stored in bc bits." — [minisketch README](https://raw.githubusercontent.com/sipa/minisketch/master/README.md)
- [SPEC] Serialization: the elements "are then encoded as 32-bit integers in little endian byte order, resulting in a 4c-byte serialization." — [BIP 330](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0330.mediawiki)
- [SPEC] 32-bit short IDs: "The short ID is equal to 1 + (s mod 0xFFFFFFFF)." Rationale: "According to our estimates, 32 bits provides low collision rate in a non-adversarial model (which is enabled by using independent salts per-link)." — [BIP 330](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0330.mediawiki)
- Paper, per extraction (verify): "we have to use shorter, 64 bit, identifiers." This conflicts with BIP 330's 32-bit IDs; BIP 330 explicitly says it modifies the paper's protocol. — [Erlay PDF](https://arxiv.org/pdf/1905.10518)
- [ANALYSIS] Size depends only on the difference: "This will always succeed when the size of the difference… does not exceed the capacity of the sketch that Alice sent. The interesting part is that this works regardless of the actual set sizes—only the difference matters." — [minisketch README](https://raw.githubusercontent.com/sipa/minisketch/master/README.md)
- [ANALYSIS] Near-optimality vs. IBLT:
  - PinSketch and CPISync "have a near-optimal communication overhead, which in practice means the sketch size is very close (or equal to) bc bits. That is the same size as would be needed to transfer the elements of the difference naively… For IBLT there is an overhead factor α, which depends on various design parameters, but is often between 2 and 10."
  - The comparison table gives sketch sizes CPISync *(b+1)c*, PinSketch *bc*, IBLT *αbc*, and decode complexity O(n³), O(n²), O(n).
  - Source: [minisketch README](https://raw.githubusercontent.com/sipa/minisketch/master/README.md)
- [MEASURED, benchmark] "IBLT takes tens of times the bandwidth of libminisketch sketches when the set difference size is small and the required failure rate is low." — [minisketch README](https://raw.githubusercontent.com/sipa/minisketch/master/README.md)
- [MEASURED, benchmark; i7-7820HQ at 2.4 GHz] "The creation of a sketch on the same machine takes around 5 ns per capacity and per set element." Also: "a set of capacity 4096 with 1024 differences, libminisketch is forty-nine times faster than pinsketch and over eight thousand times faster than cpisync." — [minisketch README](https://raw.githubusercontent.com/sipa/minisketch/master/README.md)
- [MEASURED, benchmark] Break-even against sending the raw set: "a set of 2500 30-bit entries with a difference of 20 elements can be communicated in less time with a minisketch than sending the raw set so long as the communications bandwidth is 1 gigabit per second or less; an eight-element difference can be communicated in better than one-fifth the time on a gigabit link." — [minisketch README](https://raw.githubusercontent.com/sipa/minisketch/master/README.md)
- [MEASURED, benchmark; hardware not captured] Decode timings in the 2026 PR: a typical round at capacity 54 takes "0.13 ms", and "A round between two Core nodes (limiting their set size to `MAX_RECONSET_SIZE`) takes ~120ms" (capacity 3001). Larger capacities: 8192 takes "2.3 s", and the 16384 extension takes "8.8 s". — [PR #35591 mirror](https://mirror.b10c.me/bitcoin-bitcoin/35591/)

**Capacity estimation and the miss path**
- [SPEC] "We suggest the following function: capacity=|set_size - local_set_size| + q * min(set_size, local_set_size) + c." Also: "q should be derived as an optimal q value for the previous reconciliation with a given peer". And: "it is suggested to use c=1 to avoid sending empty sketches and reduce the overhead caused by under-estimations." — [BIP 330](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0330.mediawiki)
- [SPEC] Typical size: "the protocol is currently designed to operate in the conditions where sketches usually have at most the capacity of 20". — [BIP 330](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0330.mediawiki)
- [COMPUTED] 20 × 4 bytes = 80 bytes for a typical sketch.
- [SPEC] Extension on failure: "If a node is unable to reconstruct the set difference from the received sketch, the node then makes a request for sketch extension. The peer would then send an extension, which is a sketch of a higher capacity… over the same transactions minus the sketch part which was already sent initially (to save bandwidth)." Also: "extending a sketch is just concatenating new elements to an array." — [BIP 330](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0330.mediawiki)
- [SPEC] Final fallback: "a "reconcildiff" with success=false should also be accompanied with announcing all transactions from the reconciliation set (or set snapshot if failed after extension) as a fallback to flooding." — [BIP 330](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0330.mediawiki)
- [SPEC] Why PinSketch: "PinSketch is more bandwidth efficient than IBLT, especially for the small differences in sets we expect to operate over." — [BIP 330](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0330.mediawiki)

### Inferences
- **Erlay saves bytes by adding latency, not by removing round trips.** Each reconciliation costs at least one request/response (reqrecon → sketch). The resulting reconcildiff/inv exchange then triggers the normal getdata/tx fetch, on top of a batching interval (T = 1 s in the paper). Set reconciliation fits ARFP flows that tolerate batching delay, not latency-critical first-byte paths.
- **No separate estimation round trip.** BIP 330 sizes sketches from the previous round's observed difference (*q*) plus the size gap. That avoids the extra estimation round a Strata Estimator would need. ARFP could reuse per-peer history the same way.
- **Pay-as-you-go capacity.** Sketch extension sends only the extra elements on a decode failure, so bytes already sent are not wasted. If ARFP uses sketches, this is the model for its miss handling.
- **Per-difference cost [COMPUTED].** At 32 bits per element, PinSketch costs 4 bytes per difference, versus about 24 bytes per difference for Eppstein's 12-byte-cell IBF (Section 4). PinSketch is the better choice when differences are small (tens to hundreds). IBLT's linear decode wins when differences are large; minisketch decode time grows to seconds at capacities in the thousands (PR #35591 timings).

### Gaps
- Present-day status is unclear. I saw no evidence that the full Erlay protocol has been merged and enabled in a Bitcoin Core release as of October 2026. Whether smaller pieces (for example the `sendtxrcncl` negotiation) were merged earlier was not verified; the GitHub search API was not reachable from the research environment.
- The Erlay numbers come from arXiv v2 (2019-06-03); the CCS camera-ready may differ. Fetch-extracted quotes should be spot-checked, especially the "64 bit" identifier sentence.
- Mainnet measurements of Erlay bandwidth or latency were not found; results are simulation plus a 100-node Azure testbed.

## 4. Eppstein, Goodrich, Uyeda & Varghese (ACM SIGCOMM 2011), "What's the Difference? Efficient Set Reconciliation without Prior Context"

### Takeaway
The Difference Digest is an IBF (invertible Bloom filter, the same idea as an IBLT) plus a Strata Estimator. It computes a set difference "in a single round with communication overhead proportional to the size of the difference times the logarithm of the keyspace".
- **Cells needed:** about 1.5d cells (each 12 bytes) decode in practice, and d below 200 needs at least 50% overhead.
- **Average traffic:** about 24d bytes, after a fixed 15.3 KB estimation phase.
- **Theory:** (k+1)d cells give failure probability O(d^-k).

### Cited Findings
- **Venue:** "SIGCOMM '11, August 15–19, 2011, Toronto, Ontario, Canada" (printed on the paper). — [Eppstein et al. PDF](https://www.ics.uci.edu/~eppstein/pubs/EppGooUye-SIGCOMM-11.pdf). Journal form: "ACM SIGCOMM Computer Communication Review, vol. 41, no. 4, pp. 218-229. ACM, 2011." — [minisketch README, ref 6](https://raw.githubusercontent.com/sipa/minisketch/master/README.md)
- [CLAIM/ANALYSIS] Abstract (extracted in fragments): "We describe a synopsis structure, the Difference Digest, that allows" "two nodes to compute the elements belonging to the set difference" "in a single round with communication overhead proportional to the size of the difference" "times the logarithm of the keyspace." Also: "By contrast, our abstraction assumes no prior context". — [Eppstein et al. PDF](https://www.ics.uci.edu/~eppstein/pubs/EppGooUye-SIGCOMM-11.pdf)
- [ANALYSIS] Theorem 1: "let B be an invertible Bloom filter with C = (k + 1)d cells, where k = hash_count is the number of random hash functions in B". With this sizing, "the IBFDecode operation will fail to correctly recover S and T" with probability at most O(d^-k). The exponent was split across lines in extraction. — [Eppstein et al. PDF](https://www.ics.uci.edu/~eppstein/pubs/EppGooUye-SIGCOMM-11.pdf)
- [MEASURED] Practical sizing:
  - "approximately 1.5d cells are required to successfully decode the IBF"
  - "We allocate an IBF, which consists of a table B with n = αd cells, where α ≥ 1."
  - "Our experiments later, however, show that an overhead that is somewhat less than 2 suffices."
  - "Deltas below 200 all require at least 50% overhead to completely decode."
  - Source: [Eppstein et al. PDF](https://www.ics.uci.edu/~eppstein/pubs/EppGooUye-SIGCOMM-11.pdf)
- [MEASURED] "For deltas less than 30, hash_count = 4 decodes 100% of the time". I did not capture the full experimental context. — [Eppstein et al. PDF](https://www.ics.uci.edu/~eppstein/pubs/EppGooUye-SIGCOMM-11.pdf)
- [SPEC/parameter] Cell size: "we allocate 12 bytes for each IBF cell, with 4 bytes given to each idSum, hashSum and count field." — [Eppstein et al. PDF](https://www.ics.uci.edu/~eppstein/pubs/EppGooUye-SIGCOMM-11.pdf)
- [ANALYSIS/MEASURED] Constants:
  - "The constant factors are roughly 12 for computation (4 hash functions, resulting in 3 updates each)" "and 24 for communication (12 bytes/cell scaled by two for accurate estimation and decoding)."
  - "Difference Digest has a constant estimation phase of 15.3KB followed by an average of 24d bytes in transmission."
  - Source: [Eppstein et al. PDF](https://www.ics.uci.edu/~eppstein/pubs/EppGooUye-SIGCOMM-11.pdf)
- [SPEC/parameter] Strata Estimator size:
  - "Thus Peer A computes a logarithmic number of IBF’s (strata), each of some small fixed size, say 80 cells."
  - "Since our largest delta is 100K, we configure our estimator with 16 strata, each containing 80 cells per IBF."
  - "At 12 bytes per IBF cell, this configuration requires approximately 15.3 KB of space."
  - "Using 32 strata of 80 cells is around 32 Kbytes".
  - Source: [Eppstein et al. PDF](https://www.ics.uci.edu/~eppstein/pubs/EppGooUye-SIGCOMM-11.pdf)
- [COMPUTED] 16 × 80 × 12 = 15,360 bytes, which matches "15.3 KB".
- [ANALYSIS] Rounds: "The obvious way to combine the Strata Estimator and IBF is to have node A request an estimator from node B" and "This would take two rounds or at least two round trip delays." The paper's design ends "resulting in one round to compute the set difference." Also: "the diff operation completes with only a single round of communication". — [Eppstein et al. PDF](https://www.ics.uci.edu/~eppstein/pubs/EppGooUye-SIGCOMM-11.pdf)
- [MEASURED] Comparisons: "Difference Digests and CPISync require an order of magnitude less bandwidth that ART" and "the cubic decoding complexity for CPISync dramatically increases its latency at differences larger than 100." Table 1 server compute times: "CPISync (d=100) 0.216 34,051.480 msec" and "ART 1.995 6,937.831 msec". I did not capture the column semantics. — [Eppstein et al. PDF](https://www.ics.uci.edu/~eppstein/pubs/EppGooUye-SIGCOMM-11.pdf)

### Inferences
- **Two size estimates [COMPUTED].** 1.5d cells × 12 bytes is about 18 bytes per difference; the paper's 2× allowance gives 24 bytes per difference. Both are with 32-bit keys, so the IBF costs roughly 4.5–6× the raw key bytes of the difference. That is consistent with minisketch's "α … often between 2 and 10".
- **Fixed cost dominates small differences.** The 15.3 KB estimator is only worth paying when no better difference estimate exists, for example a first contact with no history. Erlay's *q* coefficient avoids it by using per-peer history.
- **One-round claim depends on bundling.** The single round comes from sending the estimator together with the request instead of fetching it separately. An ARFP OFFER that carries the receiver's summary on the first message follows the same principle: piggyback state on the first message.

### Gaps
- The exact message sequence that achieves "one round" was not quoted in full.
- The range of d over which "approximately 1.5d" applies was not stated in the captured sentence. The paper separately says d < 200 needs at least 50% overhead.
- Fetch-extracted quotes should be checked against the PDF, especially Table 1.

## 5. Bloom filter sizing (bits per element for a target false-positive rate) and Golomb-coded sets (GCS)

### Takeaway
- **Bloom filter:** an optimally configured filter uses k = (m/n)·ln 2 hash functions and has false-positive rate f ≈ (1/2)^k ≈ 0.6185^(m/n). So m/n = −ln p/(ln 2)², which is 9.585 bits per element at 1% [COMPUTED]; Wikipedia says "about 9.6". That is within a factor log₂e ≈ 1.44 of the lower bound.
- **Golomb-coded set:** a GCS (Golomb-Rice coded sorted hash gaps, as in BIP 158) costs about B + 1/(1 − e^(−2^B/M)) bits per element, within 0.125% of its entropy bound at the optimum M = 1.497137·2^B. Examples [COMPUTED]: about 8.1 bits per element at 1% (vs. 9.585 for a Bloom filter), and about 21.05 bits at BIP 158's 1/784931 (vs. 28.25). The cost is that a GCS is static and must be decoded sequentially to query.

### Cited Findings
**Bloom filters**
- **Standard reference:** Broder & Mitzenmacher, "Network Applications of Bloom Filters: A Survey," *Internet Mathematics* Vol. 1, No. 4: 485–509 (2004). — [Broder & Mitzenmacher PDF](https://www.eecs.harvard.edu/~michaelm/postscripts/im2005b.pdf)
- [ANALYSIS] Optimal k: "since the optimal value for k is m ln 2/n." — [Broder & Mitzenmacher](https://www.eecs.harvard.edu/~michaelm/postscripts/im2005b.pdf)
- [ANALYSIS] Minimum false-positive rate: "the false positive rate f is (1/2)k ≈ (0.6185)m/n". Superscripts were lost in PDF text extraction; the expression is (1/2)^k ≈ (0.6185)^(m/n). — [Broder & Mitzenmacher](https://www.eecs.harvard.edu/~michaelm/postscripts/im2005b.pdf)
- [ANALYSIS] Worked example: "when m =8n, the false positive probability is just over 0.02." Also: "Bloom filters yield a constant false positive probability even for a constant number of bits per set element." — [Broder & Mitzenmacher](https://www.eecs.harvard.edu/~michaelm/postscripts/im2005b.pdf)
- [ANALYSIS] Lower bound: "Thus, space-wise Bloom filters are within a factor of log2 e ≈ 1.44 of the (asymptotic) lower bound." — [Broder & Mitzenmacher](https://www.eecs.harvard.edu/~michaelm/postscripts/im2005b.pdf)
- [Secondary source] Wikipedia: "fewer than 10 bits per element are required for a 1% false positive probability" (cited there to Bonomi et al., 2006); "requires only about 9.6 bits per element"; "Hence Bloom filters use 44% more space than an equivalent optimal data structure." (cited there to Carter et al., 1978). Wikipedia's formulas did not survive extraction. — [Wikipedia: Bloom filter](https://en.wikipedia.org/wiki/Bloom_filter)
- [COMPUTED] From f = 0.6185^(m/n), i.e. m/n = −ln p/(ln 2)²:

  | Target false-positive rate | Bits per element | Hash functions |
  |---|---|---|
  | 1% | 9.585 | k = 6.64 (round to 7) |
  | 0.1% | 14.38 | not computed |
  | 1/784931 (BIP 158's rate) | 28.25 | not computed |

**Golomb-coded sets**
- [SPEC] BIP 158 (Compact Block Filters for Light Clients; "Status: Deployed", "Assigned: 2017-05-24"):
  - Purpose: it is "an alternative to Bloom filters, as used in BIP 37, that minimizes filter size by using Golomb-Rice coding for compression."
  - Definition: a GCS "matches all items in the set with probability 1, and matches other items with probability 1/M".
  - Construction: "hashing all items to 64-bit integers in the range [0, N * M)", "sorting", "computing the differences", and "writing the differences sequentially, compressed with Golomb-Rice coding".
  - Source: [BIP 158](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0158.mediawiki)
- [SPEC] Minimum size: "The result is a byte vector with a minimum size of N * (P + 1) bits." — [BIP 158](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0158.mediawiki)
- [SPEC/ANALYSIS] Parameters: "The parameter P MUST be set to 19, and the parameter M MUST be set to 784931. Analysis has shown that if one is able to select P and M independently, then setting M=1.497137 * 2^P is close to optimal". Also: "Empirical analysis also shows that these parameters minimize the bandwidth utilized, considering both the expected number of blocks downloaded due to false positives and the size of the filters themselves." — [BIP 158](https://raw.githubusercontent.com/bitcoin/bips/master/bip-0158.mediawiki)
- [ANALYSIS] Pieter Wuille, "Minimizing the redundancy in Golomb Coded Sets" (May 2018). Expected size per element is "B + 1 / (1 - (1 - 1/M)^{2^{B}})", approximately "B + 1 / (1 - e^{-2^{B}/M})". Optimum: "the set size is minimized when B = log2(M) - 0.5822061, or M = 1.497137 2^{B}". — [Wuille](https://wuille.net/posts/minimizing-golomb-filters/)
- [ANALYSIS] Redundancy: at the optimum the GCS is "less than 0.125% larger than theoretically possible", and "if M = 2^{B}, the redundancy is around 0.65%". For M = 2^20 and B = 20 the size "is 21.58197" bits per element (simulation at N=10000: "21.58187"), against an entropy of "21.44270". — [Wuille](https://wuille.net/posts/minimizing-golomb-filters/)
- [COMPUTED] Wuille's formula reproduces 21.58198 for M = 2^20, B = 20, which validates the extracted formula. Applied to other settings:

  | Setting | GCS bits/element | Entropy bound log₂(e·M) | Bloom filter at same rate |
  |---|---|---|---|
  | BIP 158 (P = 19, M = 784931) | 21.05 (about 0.13% redundancy) | 21.02 | 28.25 |
  | 1% false positives (M = 100, best integer B = 6) | 8.11 | 8.09 | 9.585 |

  The GCS entropy bound is about log₂(1/p) + 1.44 bits.
- [Historical use in HTTP] Cache Digests draft -00 (July 9, 2016) used "a Golumb-Rice Coded Set" (sic), with false-positive probability "expressed as "1/P"". — [draft-ietf-httpbis-cache-digest-00](https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-cache-digest-00)

### Inferences
- **Size.** For a static receiver-state advertisement (a snapshot sent once), a GCS is about 15% smaller than an optimal Bloom filter at 1%, and about 25% smaller at false-positive rates near 1e-6 [COMPUTED].
- **Update cost.** A GCS cannot be updated incrementally and needs a sequential decode to test membership. A Bloom filter supports O(k) inserts and lookups. The Cache Digest draft's move from GCS (-00) to a Cuckoo filter (-05) is consistent with wanting an updatable structure, but the stated reason was not found (Section 6).
- **Mismatched problems.** Bloom filters and GCSs answer "is X in the receiver's set?", and their cost grows with the receiver's whole set (n). Sketches and IBLTs (Sections 3–4) scale with the difference (d). When the receiver holds a lot and the sender needs to know only a little, difference-proportional structures win. When the sender must test arbitrary candidate references, membership filters are the natural fit.

### Gaps
- The Bloom formulas were confirmed from the standard survey in extracted form only (superscripts lost); recheck against the PDF.
- The "9.6 bits at 1%" figure was found stated only on Wikipedia; the primary-source value is derived [COMPUTED].
- The original GCS paper (Putze, Sanders & Singler, 2007) was not retrieved.
- Wuille's post also contains a phrase "…times more compact than Bloom filters, but harder to update or query." Its leading quantity was lost in extraction, so it is not used here.

## 6. HTTP Cache Digests (draft-ietf-httpbis-cache-digest): what it proposed and why it was abandoned

### Takeaway
Cache Digests (Kazuho Oku, Yoav Weiss) defined an HTTP/2 `CACHE_DIGEST` frame, plus a `Cache-Digest` header variant, so a client could tell the server what it already had cached. Servers would then skip pushing redundant responses.
- **Structure:** draft -00 (July 2016) used a Golomb-Rice coded set; draft -05 (July 2, 2018) used a Cuckoo filter.
- **Officially stated reason for abandonment:** in January 2019 the HTTP WG chairs moved it to "dead" because it was unlikely to be "implemented widely enough to justify standardisation - even as Experimental", especially by browsers.
- **Privacy:** the draft itself acknowledged that the digest enables passive cache fingerprinting, with mitigations left as a TODO.
- **Server Push:** its only use case was later disabled by Chrome (version 106, 2022).
- **"Complexity":** I found no primary source citing complexity as a reason.

### Cited Findings
- [Status] "draft-ietf-httpbis-cache-digest-05 - Cache Digests for HTTP/2". "Last updated 2019-01-23 (Latest revision 2018-07-02)". IESG state "Expired"; WG state "Dead WG Document". Authors "Kazuho Oku" and "Yoav Weiss". — [IETF Datatracker](https://datatracker.ietf.org/doc/draft-ietf-httpbis-cache-digest/)
- [SPEC] Abstract: "This specification defines a HTTP/2 frame type to allow clients to inform the server of their cache's contents." "Servers can then use this to inform their choices of what to push to clients." — [IETF Datatracker](https://datatracker.ietf.org/doc/draft-ietf-httpbis-cache-digest/)
- [SPEC] Server behavior (-05): "If a given URL has a match in a current CACHE_DIGEST, a complete" "response need not be pushed; The server MAY push a 304 response". — [draft -05](https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-cache-digest-05)
- [SPEC] Data structure (-05, Cuckoo filter):
  - *P* is "of a false positive that is acceptable, expressed as "1/2**P"".
  - Each fingerprint takes "P + 3" bits.
  - "Let "b" be the bucket size, defined as 4."
  - Hashing uses a "SHA-256 message digest" truncated to 32 bits.
  - Source: [draft -05](https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-cache-digest-05)
- [SPEC] Data structure (-00, dated July 9, 2016): it uses "a Golumb-Rice Coded Set". Each entry is a gap written as "Q" '0' bits, then 1 '1' bit, then "R" "as binary, using log2("P") bits". Hash values are truncated to "log2( "N" * "P" ) bits". — [draft -00](https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-cache-digest-00)
- [SPEC] Header alternative (-05 appendix): it "defines how a CACHE_DIGEST frame can be encoded as an HTTP Header" named "Cache-Digest", for browsers "that support Service Workers" "but not Cache Digests (yet)". — [draft -05](https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-cache-digest-05)
- [SPEC, privacy] The -05 Security Considerations:
  - "The contents of a User Agent's cache can be used to re-identify or" ""fingerprint" the user over time, even when other identifiers (e.g.," "are cleared."
  - "CACHE_DIGEST allows such cache-based fingerprinting to become" "passive, since it allows the server to discover the state of the" "client's cache without any visible change in server behaviour."
  - "clients MUST mitigate for this threat when the user" "attempts to remove identifiers (e.g., "clearing cookies")". Suggested mitigations: "by clearing the" "cache, by changing one or both of N and P, or by adding new," "synthetic entries to the digest".
  - "TODO: discuss how effective the suggested mitigations actually would" "be."
  - "User Agents SHOULD NOT send CACHE_DIGEST when in" ""privacy mode.""
  - Source: [draft -05](https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-cache-digest-05)
- [SPEC, scoping] -05 also says: "a client MUST NOT include stale-cached" "responses whose URLs do not share origins" with "the indicated origin", and "Clients MUST NOT send CACHE_DIGEST frames on" "connections that are not authoritative". — [draft -05](https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-cache-digest-05)
- [Decision] Mark Nottingham, "Cache Digests status", Mon, 14 Jan 2019:
  - "After discussion with the editors, the chairs believe that it isn't likely that this draft will be" "implemented widely enough to justify standardisation - even as Experimental - in the foreseeable future."
  - "Therefore, we intend to move it to the "dead" state".
  - "If we've misread the signals and there are" "people intending to implement (especially on the browser side, as that's the primary use case it's designed for), please bring that to our attention."
  - Source: [ietf-http-wg 2019JanMar/0033](https://lists.w3.org/Archives/Public/ietf-http-wg/2019JanMar/0033.html)
- **Replies.** Loïc Hoguin (23 Jan 2019): "This draft seemed like a good solution to optimize PUSH and I was" "looking forward to it (mostly for server/API/mobile clients). Are there" "any plans for an alternative?" — [0052](https://lists.w3.org/Archives/Public/ietf-http-wg/2019JanMar/0052.html). Jxck (24 Jan 2019): "currently mozilla seems not mention about this," "so I'm asking Mozilla Standard Position." — [0053](https://lists.w3.org/Archives/Public/ietf-http-wg/2019JanMar/0053.html)
- **Server Push removal** (Barry Pollard, Chrome developer blog; page "Last updated 2022-08-18 UTC"):
  - "support of HTTP/2 Server Push will be disabled by default in Chrome 106".
  - Reasons: "only 1.25% of HTTP/2 sites making use of this feature"; "without a clear net performance gain and in many cases performance regressions"; "the performance benefits were often difficult to realize"; "Push was not implemented in many HTTP/3 servers and clients".
  - Replacement: 103 Early Hints "is a much less error-prone alternative with many of the same upsides as Push". Early Hints "leaves the browser in control of deciding whether it needs these or not".
  - Source: [Chrome blog](https://developer.chrome.com/blog/removing-push)

### Inferences
- **Closest web precedent, and it failed.** Cache Digests is the nearest web-scale precedent for ARFP's design (receiver advertises state so the sender sends only what is missing). The documented failure modes, roughly in order of evidence strength:
  1. **Deployment:** no browser commitment, which was the official reason.
  2. **Coupling:** it was tied to a sender-initiated mechanism (Server Push) whose benefits proved hard to realize and which browsers later disabled.
  3. **Privacy:** a state advertisement is a passive fingerprinting and tracking vector, and the draft's mitigations were never settled.
- **Implications for ARFP.**
  - Scope state advertisements per origin or principal.
  - Make them resettable or randomizable, for example a re-salt like BIP 152's per-connection nonce.
  - Keep the receiver in control of what it reveals.
- **Direction of travel on the web.** The web's replacement (103 Early Hints plus preload) returns the decision to the receiver, so the web moved toward receiver-driven fetching rather than sender-side state inference.

### Gaps
- No primary source found that cites "complexity" as a reason for abandonment.
- No source found explaining the switch from GCS (-00) to a Cuckoo filter (-05).
- Mozilla's standards position (requested in the thread) was not retrieved.
- Whether any browser or server shipped Cache Digests experimentally was not verified.
- The Chrome blog's original publication date was not visible; only "Last updated 2022-08-18".

## 7. rsync (Tridgell & Mackerras technical report): what is exchanged and how many round trips

### Takeaway
The receiver β (holding old file B) splits B into fixed S-byte blocks. It sends a 32-bit rolling checksum and a 128-bit MD4 checksum per block, 20 bytes per block, to the sender α. α scans its new file A at every byte offset and streams back block references and literal data. That is one request/response exchange per file, pipelined across files with two independent processes.
- **Measured (24 MB Linux kernel tar files, 1.99.10 → 2.0.0):** block sizes above 300 bytes transferred only about 5% of the file.
- **Summary traffic:** the receiver-side summary was about 0.98 MB at 500-byte blocks. It scales with file size, not with the size of the change.

### Cited Findings
- **Title, authors, date.** "The rsync algorithm" by Andrew Tridgell and Paul Mackerras, Department of Computer Science, Australian National University. The HTML byline date is 1998-11-09. — [rsync tech report index](https://rsync.samba.org/tech_report/)
- [SPEC] The algorithm steps:
  1. "β splits the file B into a series of non-overlapping" "fixed-sized blocks of size S bytes".
  2. "For each of these blocks β calculates two checksums:" "a weak ``rolling'' 32-bit checksum (described below) and a strong" "128-bit MD4 checksum."
  3. "β sends these checksums to α."
  4. "α searches through A to find all blocks of length S bytes (at any offset, not just multiples of S)" "that have the same" "weak and strong checksum as one of the blocks of B."
  5. "α sends β a sequence of instructions for" "constructing a copy of A. Each instruction is either a reference" "to a block of B, or literal data."

  Source: [rsync TR, "The rsync algorithm"](https://rsync.samba.org/tech_report/node2.html)
- [SPEC] Pipelining across files:
  - "If we have a several files to copy, we can gain a considerable latency advantage by pipelining the process."
  - "This involves" β "initiating two independent processes." "One of the processes generates and sends the checksums to" α "while the other receives the difference information from" α "and reconstructs the files."
  - "If the communications link is buffered then these two processes can proceed independently" "and the link should be kept fully utilised in both directions for most of the time."
  - Source: [rsync TR, "Pipelining"](https://rsync.samba.org/tech_report/node5.html)
- [MEASURED] Test setup: "The two kernel versions were 1.99.10 and 2.0.0." "These tar files are approximately 24MB in size and are separated by 5 released patch levels." A GNU diff "produced over 32 thousand lines" "of output totalling 2.1 MB." — [rsync TR, "Results"](https://rsync.samba.org/tech_report/node6.html)
- [MEASURED] Kernel tar results ("written" is bytes sent by α, mostly file data; "read" is bytes read by α, "almost all checksum information"):

  | Block size (bytes) | Matches | Tag hits | False alarms | Data (bytes) | Written (bytes) | Read (bytes) |
  |---|---|---|---|---|---|---|
  | 300 | 64247 | 3817434 | 948 | 5312200 | 5629158 | 1632284 |
  | 500 | 46989 | 620013 | 64 | 1091900 | 1283906 | 979384 |
  | 700 | 33255 | 571970 | 22 | 1307800 | 1444346 | 699564 |
  | 900 | 25686 | 525058 | 24 | 1469500 | 1575438 | 544124 |
  | 1100 | 20848 | 496844 | 21 | 1654500 | 1740838 | 445204 |

  Source: [rsync TR, "Results"](https://rsync.samba.org/tech_report/node6.html)
- [MEASURED] Samba source tree (1.7 MB; a 120 kB diff), not tarred, at block size 500: data 171574, written 189330, read 50908. — [rsync TR, "Results"](https://rsync.samba.org/tech_report/node6.html)
- [MEASURED/CLAIM] Conclusions:
  - "The results demonstrate that for block sizes above 300 bytes, only a small fraction (around 5%) of the file was transferred."
  - "The number of false alarms was less than 1/1000 of the number of true matches".
  - "Each pair of checksums consumes 20 bytes: 4 bytes for the rolling checksum plus 16 bytes for the 128-bit MD4 checksum."
  - Source: [rsync TR, "Results"](https://rsync.samba.org/tech_report/node6.html)
- The report does not count round trips; the fetch confirmed that "The page doesn't mention round trips". — [rsync TR, "Pipelining"](https://rsync.samba.org/tech_report/node5.html)

### Inferences
- **Round trips [inferred].** Per file, rsync costs one exchange: receiver checksums go to the sender, and the delta stream comes back. That is about 1 RTT plus transfer time, and pipelining overlaps the per-file round trips across many files. There is no negotiation phase. The receiver's checksum list is the state advertisement, and it doubles as the request.
- **Advertisement size [COMPUTED].** The advertisement grows with file size: 24 MB / 500 B ≈ 48,000 blocks × 20 B ≈ 0.96 MB, consistent with the measured 979,384 bytes "read" at block size 500. That is a cost of about 4% of the file just to describe the receiver's state, and it pays off only when the file changed little.
- **Contrast with set reconciliation.** Sketch and IBLT costs scale with the difference. rsync cost scales with the data the receiver holds, divided by S.
- **Direction.** In rsync the receiver initiates by sending its state summary. That is the inverse of ARFP's OFFER → ACCEPT, and it removes the separate accept step.

### Gaps
- The technical report number (commonly cited as TR-CS-96-05, June 1996) and the original publication date could not be verified from the fetched pages; the only date shown was the HTML byline, 1998-11-09.
- Modern rsync protocol changes (checksum algorithms, incremental file lists) were out of scope and not checked.

## 8. Git fetch negotiation (have/want, protocol v2, the "skipping" algorithm): round-trip cost and how Git limits it

### Takeaway
Git negotiation is receiver-driven and multi-round. The client sends "want" lines, then batches of "have" commit IDs. The server ACKs the common ones until it can say "ready", or the client says "done". The number of round trips grows with how far back the common ancestor is.

Git bounds the cost in five ways:
- **Growing batches:** have batches grow each round. Stateful connections start at 16, then 32, then add 32 per round. Stateless HTTP and protocol v2 double up to 16384, then grow ×1.1.
- **Give-up limit:** the client gives up after 256 unacknowledged haves, but only once at least one "continue" ACK has arrived.
- **Skipping negotiator:** the opt-in `skipping` negotiator skips commits with growing strides and may send a larger packfile.
- **`--negotiation-tip`:** limits which commits are offered as haves.
- **`noop`:** skips negotiation entirely.

Protocol v2 is stateless per round, so the client re-sends the common commits it has learned in every request.

### Cited Findings
**Pack protocol (v0/v1) negotiation**
- [SPEC] "Now the client will send a list of the obj-ids it has using 'have' lines, so the server can make a packfile that only contains the objects that the client needs. In multi_ack mode, the canonical implementation will send up to 32 of these at a time, then will send a flush-pkt. The canonical implementation will skip ahead and send the next 32 immediately, so that there is always a block of 32 "in-flight on the wire" at a time." — [gitprotocol-pack](https://raw.githubusercontent.com/git/git/master/Documentation/gitprotocol-pack.adoc)
- [SPEC] Give-up rule: "…in the canonical implementation, this is determined when the client sends 256 'have' lines without getting any of them ACKed by the server - meaning there is nothing in common and the server should just send all of its objects), then the client will send a 'done' command." Also: "However, the 256 limit *only* turns on in the canonical client implementation if we have received at least one "ACK %s continue" during a prior round. This helps to ensure that at least one common ancestor is found before we give up entirely." — [gitprotocol-pack](https://raw.githubusercontent.com/git/git/master/Documentation/gitprotocol-pack.adoc)
- [SPEC] multi_ack_detailed: "the server will differentiate the ACKs where it is signaling that it is ready to send data with 'ACK obj-id ready' lines, and signals the identified common commits with 'ACK obj-id common' lines." — [gitprotocol-pack](https://raw.githubusercontent.com/git/git/master/Documentation/gitprotocol-pack.adoc)

**Protocol v2**
- [SPEC] Statelessness: "Protocol version 2 is stateless by default. This means that all commands must only last a single round and be stateless from the perspective of the server side, unless the client has requested a capability indicating that state should be maintained by the server… This permits simple round-robin load-balancing on the server side". — [gitprotocol-v2](https://raw.githubusercontent.com/git/git/master/Documentation/gitprotocol-v2.adoc)
- [SPEC] Fetch arguments:
  - `have <oid>`: "Indicates to the server an object which the client has locally. This allows the server to make a packfile which only contains the objects that the client needs. Multiple 'have' lines can be supplied."
  - `done`: "Indicates to the server that negotiation should terminate (or not even begin if performing a clone) and that the server should use the information supplied in the request to construct the packfile."
  - Source: [gitprotocol-v2](https://raw.githubusercontent.com/git/git/master/Documentation/gitprotocol-v2.adoc)
- [SPEC] Ending negotiation early:
  - "The server will respond with a "ready" line indicating that the server has found an acceptable common base and is ready to make and send a packfile (which will be found in the packfile section of the same response)".
  - Once "ready" is sent, the server "can decide to (as an optimization) omit any "ACK" lines… because the server will have already determined the objects it plans to send to the client and no further negotiation is needed."
  - `wait-for-done`: "Indicates to the server that it should never send "ready", but should wait for the client to say "done" before sending the packfile."
  - Source: [gitprotocol-v2](https://raw.githubusercontent.com/git/git/master/Documentation/gitprotocol-v2.adoc)

**Client implementation: batch growth and give-up**
- [SPEC/code] Constants in fetch-pack.c: `#define MAX_IN_VAIN 256`, `#define INITIAL_FLUSH 16`, `#define PIPESAFE_FLUSH 32`, `#define LARGE_FLUSH 16384`. In `next_flush()`, the stateless branch is "if (count < LARGE_FLUSH) count <<= 1; else count = count * 11 / 10;" and the stateful branch is "if (count < PIPESAFE_FLUSH) count <<= 1; else count += PIPESAFE_FLUSH;". — [fetch-pack.c](https://raw.githubusercontent.com/git/git/master/fetch-pack.c)
- [SPEC/code] The v2 path uses the stateless schedule: "*haves_to_send = next_flush(1, *haves_to_send);". It re-adds common commits each request with "add_common(&req_buf, common);". It ends with "done" when "(!haves_added || (seen_ack && *in_vain >= MAX_IN_VAIN))". — [fetch-pack.c](https://raw.githubusercontent.com/git/git/master/fetch-pack.c)
- [SPEC/code] Stateless-RPC replay comment: "We need to replay the have for this object on the next RPC request so the peer knows it is in common with us." — [fetch-pack.c](https://raw.githubusercontent.com/git/git/master/fetch-pack.c)

**Negotiation algorithms (`skipping`, `noop`)**
- [SPEC] Config documentation: `fetch.negotiationAlgorithm` "Set to `consecutive` to use an algorithm that walks over consecutive commits checking each one. Set to `skipping` to use an algorithm that skips commits in an effort to converge faster, but may result in a larger-than-necessary packfile; or set to `noop` to not send any information at all, which will almost certainly result in a larger-than-necessary packfile, but will skip the negotiation step… The default is normally `consecutive`, but if `feature.experimental` is `true`, then the default is `skipping`." — [config/fetch](https://raw.githubusercontent.com/git/git/master/Documentation/config/fetch.adoc)
- [SPEC/code] Skip-stride growth in the skipping negotiator: "uint16_t new_original_ttl = entry->ttl ? entry->original_ttl : entry->original_ttl * 3 / 2 + 1;" — [negotiator/skipping.c](https://raw.githubusercontent.com/git/git/master/negotiator/skipping.c)
- **Git 2.19 release notes:** "Add a server-side knob to skip commits in exponential/fibbonacci stride in an attempt to cover wider swath of history with a smaller number of iterations, potentially accepting a larger packfile transfer, instead of going back one commit a time during common ancestor discovery during the "git fetch" transaction." Also: ""git fetch" learned a new option "--negotiation-tip" to limit the set of commits it tells the other end as "have", to reduce wasted bandwidth and cycles". And: "The wire-protocol v2 relies on the client to send "ref prefixes" to limit the bandwidth spent on the initial ref advertisement." — [Git 2.19.0 RelNotes](https://raw.githubusercontent.com/git/git/master/Documentation/RelNotes/2.19.0.adoc)

**Protocol v2 default history**
- **Git 2.26:** "The transport protocol version 2 becomes the default one." — [2.26.0 RelNotes](https://raw.githubusercontent.com/git/git/master/Documentation/RelNotes/2.26.0.adoc)
- **Git 2.27:**
  - "The transport protocol version 2, which was promoted to the default in Git 2.26 release, turned out to have some remaining rough edges, so it has been demoted from the default."
  - "Those fetching over protocol v2 from linux-next and other kernel repositories are reporting that v2 often fetches way too much than needed."
  - "The upload-pack protocol v2 gave up too early before finding a common ancestor, resulting in a wasteful fetch from a fork of a project. This has been corrected to match the behaviour of v0 protocol."
  - Source: [2.27.0 RelNotes](https://raw.githubusercontent.com/git/git/master/Documentation/RelNotes/2.27.0.adoc)
- **Git 2.29:** "The transport protocol v2 has become the default again." — [2.29.0 RelNotes](https://raw.githubusercontent.com/git/git/master/Documentation/RelNotes/2.29.0.adoc)

### Inferences
- **Round trips [inferred from code].** Each negotiation round is one request/response; in v2 or smart HTTP, each round is a separate stateless request. With batches doubling from 16, finding a common ancestor N commits back takes roughly log₂(N/16) + 1 rounds in the stateless path, before the packfile response. With `skipping`, fewer haves are needed for deep histories, at the risk of over-sending. `noop` takes zero negotiation rounds but may send everything.
- **What Git shows about "ask what the receiver has".** It costs an unbounded number of round trips when histories diverge. Git's main levers trade bytes for rounds (`skipping`, `noop`, the 256-in-vain give-up). It does not use a compact summary such as a Bloom filter or sketch of the client's commits. That leaves a gap ARFP could exploit: a one-shot compact receiver summary could replace iterative have/ACK rounds.
- **Statelessness has a price.** v2's stateless design, chosen for load-balancing, forces the client to replay its accumulated common set every round, so request size grows across rounds. ARFP will face the same trade-off if senders are load-balanced.
- **Edge cases are hard.** The 2.27 demotion over "fetches way too much" and "gave up too early" shows that negotiation heuristics are where regressions concentrate.

### Gaps
- git-scm.com pages could not be fetched (blocked). I used the git/git master sources those pages are generated from. Line-level identity with git-scm.com's rendered version was not checked.
- Release dates for Git 2.19, 2.26, 2.27 and 2.29 were not verified from fetched text, so only version numbers are given.
- No published measurement of typical negotiation round counts or latency for real repositories was found.
- The "server-side knob" wording in the 2.19 notes conflicts with the client-side `fetch.negotiationAlgorithm` documentation; the release-note wording is reported as written.
