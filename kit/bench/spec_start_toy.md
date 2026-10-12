# Speculative start on a toy model (MEASURED, toy scale)

Byte-level transformer, 841,984 parameters, trained 1500 steps on the first 80% of 163,022 bytes of the repository's preserved original documents (corpus SHA-256 b0ba86a9d7eacb46…), 14.8 min on this machine. 200 non-overlapping held-out prompts of 96 bytes; 48 tokens drafted greedily on the quantized cache, then verified in one parallel pass against the exact (32-bit) cache. No transfer and no timing are measured.

| KV bits | Size vs 16-bit (with scales) | Mean tokens kept (of 48) | Median | 10th pct | Drafts fully kept | Per-token acceptance | Final output = exact | Bits/byte exact → quantized |
|---|---|---|---|---|---|---|---|---|
| 8 | 1.92× smaller | 44.98 | 48 | 48 | 90% | 0.998 | 200/200 | 2.598 → 2.598 |
| 6 | 2.53× smaller | 36.98 | 48 | 4 | 68% | 0.992 | 200/200 | 2.598 → 2.597 |
| 4 | 3.69× smaller | 13.77 | 4 | 0 | 16% | 0.942 | 200/200 | 2.598 → 2.620 |
| 3 | 4.8× smaller | 5.2 | 1 | 0 | 3% | 0.843 | 200/200 | 2.598 → 2.700 |
| 2 | 6.86× smaller | 0.57 | 0 | 0 | 0% | 0.364 | 200/200 | 2.598 → 2.929 |

Identical output is not guaranteed by construction. On the exact path, the one-pass check and step-by-step decoding gave logits that differed in 9,400 of 9,400 positions (by up to 7.2e-05): matrix products of different shapes add in a different order. No greedy choice changed: the smallest gap between the top two logits was 3.3e-04. A near tie could flip a token, so exact output needs batch-invariant kernels, on a CPU as on a GPU.

Toy scale only: acceptance on production models has to be measured there (QuantSpec reports >90% with a 4-bit cache and 4-bit weights).
