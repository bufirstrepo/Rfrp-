"""Speculative start on a toy model: decode on a compressed KV cache, verify against the exact one.

Idea 2 in docs/proposals/ARFP-speed-mechanisms.md. A receiver gets a coarse (quantized) copy of a
KV cache first and starts generating with it while the exact cache is still arriving. When the exact
cache lands, one parallel forward pass checks the drafted tokens; the longest matching prefix is kept,
plus the exact model's token at the first mismatch. In exact arithmetic the final output is identical
to decoding on the exact cache from the start; in floating point the one-pass check and step-by-step
decoding round differently, so a near tie could flip a token. This script checks the final output on
every sample, measures that rounding gap, and measures how many drafted tokens survive at several
quantization levels.

Toy scale, measured on this machine: a ~0.8M-parameter byte-level transformer trained here for about
15 minutes on the repository's preserved original documents (the manifest's source files, which the
repository never edits). It shows the verification step and its correctness; it says nothing about
acceptance rates on production models (QuantSpec reports >90% with a 4-bit KV cache and 4-bit
weights; Lynx applies the same idea to KV transfer). No transfer and no timing are measured here.

    pip install -r bench/requirements-toy.txt
    python3 bench/spec_start_toy.py          # trains (~10-20 min on 2 CPU cores), then measures
    python3 bench/spec_start_toy.py --render # rebuilds the .md from the .json, no training

Writes bench/spec_start_toy.json and bench/spec_start_toy.md.
"""
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
CFG = {"d": 128, "layers": 4, "heads": 4, "ctx": 160, "mlp": 4, "vocab": 256,
       "steps": 1500, "batch": 32, "lr": 2e-3, "warmup": 100, "seed": 0}
PREFIX, DRAFT, SAMPLES, HELD_OUT = 96, 48, 200, 0.2
BITS = (8, 6, 4, 3, 2)


# ---------------------------------------------------------------- corpus (hash-pinned in the manifest)
def corpus():
    """The preserved originals only (SOURCE_MANIFEST.json "source_files"), so the corpus never changes."""
    manifest = json.loads((REPO / "SOURCE_MANIFEST.json").read_text())
    entries = manifest["source_files"]
    data, mismatched = bytearray(), []
    for e in entries:
        b = (REPO / e["path"]).read_bytes()
        if hashlib.sha256(b).hexdigest() != e["sha256"]:
            mismatched.append(e["path"])
        data += b + b"\n"
    return np.frombuffer(bytes(data), dtype=np.uint8), [e["path"] for e in entries], mismatched


# ---------------------------------------------------------------- model, training (JAX)
def train(tokens):
    import jax
    import jax.numpy as jnp

    d, L, H, T, V = CFG["d"], CFG["layers"], CFG["heads"], CFG["ctx"], CFG["vocab"]
    hd = d // H
    key = jax.random.PRNGKey(CFG["seed"])

    def dense(k, i, o):
        return jax.random.normal(k, (i, o)) * (0.02 if o != d or i != d * CFG["mlp"] else 0.02 / math.sqrt(2 * L))

    keys = iter(jax.random.split(key, 8 + 8 * L))
    params = {"wte": jax.random.normal(next(keys), (V, d)) * 0.02,
              "wpe": jax.random.normal(next(keys), (T, d)) * 0.01,
              "lnf": {"g": jnp.ones(d), "b": jnp.zeros(d)}, "blocks": []}
    for _ in range(L):
        params["blocks"].append({
            "ln1": {"g": jnp.ones(d), "b": jnp.zeros(d)}, "ln2": {"g": jnp.ones(d), "b": jnp.zeros(d)},
            "wq": dense(next(keys), d, d), "wk": dense(next(keys), d, d), "wv": dense(next(keys), d, d),
            "wo": dense(next(keys), d, d) / math.sqrt(2 * L),
            "w1": dense(next(keys), d, d * CFG["mlp"]), "w2": dense(next(keys), d * CFG["mlp"], d) / math.sqrt(2 * L)})

    def ln(x, p):
        m = x.mean(-1, keepdims=True)
        v = ((x - m) ** 2).mean(-1, keepdims=True)
        return (x - m) / jnp.sqrt(v + 1e-5) * p["g"] + p["b"]

    def fwd(p, x):
        B, t = x.shape
        h = p["wte"][x] + p["wpe"][:t]
        mask = jnp.tril(jnp.ones((t, t), bool))
        for blk in p["blocks"]:
            a = ln(h, blk["ln1"])
            q = (a @ blk["wq"]).reshape(B, t, H, hd).transpose(0, 2, 1, 3)
            k = (a @ blk["wk"]).reshape(B, t, H, hd).transpose(0, 2, 1, 3)
            v = (a @ blk["wv"]).reshape(B, t, H, hd).transpose(0, 2, 1, 3)
            s = jnp.where(mask, q @ k.transpose(0, 1, 3, 2) / math.sqrt(hd), -1e9)
            o = (jax.nn.softmax(s, -1) @ v).transpose(0, 2, 1, 3).reshape(B, t, d)
            h = h + o @ blk["wo"]
            h = h + jax.nn.gelu(ln(h, blk["ln2"]) @ blk["w1"]) @ blk["w2"]
        return ln(h, p["lnf"]) @ p["wte"].T

    def loss(p, x, y):
        logits = fwd(p, x)
        return -jnp.mean(jnp.take_along_axis(jax.nn.log_softmax(logits), y[..., None], -1))

    @jax.jit
    def step(p, m, v, t, x, y):
        l, g = jax.value_and_grad(loss)(p, x, y)
        lr = CFG["lr"] * jnp.minimum(1.0, (t + 1) / CFG["warmup"]) * 0.5 * (1 + jnp.cos(math.pi * t / CFG["steps"]))
        m = jax.tree_util.tree_map(lambda m_, g_: 0.9 * m_ + 0.1 * g_, m, g)
        v = jax.tree_util.tree_map(lambda v_, g_: 0.99 * v_ + 0.01 * g_ * g_, v, g)
        p = jax.tree_util.tree_map(lambda p_, m_, v_: p_ - lr * (m_ / (1 - 0.9 ** (t + 1)))
                                   / (jnp.sqrt(v_ / (1 - 0.99 ** (t + 1))) + 1e-8), p, m, v)
        return p, m, v, l

    zeros = jax.tree_util.tree_map(jnp.zeros_like, params)
    m, v = zeros, zeros
    rng = np.random.default_rng(CFG["seed"])
    t0, log = time.time(), []
    for t in range(CFG["steps"]):
        idx = rng.integers(0, len(tokens) - T - 1, CFG["batch"])
        x = np.stack([tokens[i:i + T] for i in idx]).astype(np.int32)
        y = np.stack([tokens[i + 1:i + T + 1] for i in idx]).astype(np.int32)
        params, m, v, l = step(params, m, v, t, x, y)
        if t % 100 == 0 or t == CFG["steps"] - 1:
            log.append({"step": t, "loss_nats": float(l), "seconds": round(time.time() - t0, 1)})
            print(f"step {t:5d}  loss {float(l):.3f} nats/byte  {time.time() - t0:7.1f} s", flush=True)
    return jax.tree_util.tree_map(np.asarray, params), log


# ---------------------------------------------------------------- inference with an explicit KV cache (numpy)
class Model:
    def __init__(self, p):
        self.p = p
        self.H = CFG["heads"]
        self.hd = CFG["d"] // self.H

    @staticmethod
    def ln(x, p):
        m = x.mean(-1, keepdims=True)
        v = ((x - m) ** 2).mean(-1, keepdims=True)
        return (x - m) / np.sqrt(v + 1e-5) * p["g"] + p["b"]

    def run(self, toks, pos0, cache):
        """Forward toks (positions pos0..) attending to cache + themselves. Returns logits and new K/V."""
        p, H, hd = self.p, self.H, self.hd
        t = len(toks)
        h = p["wte"][toks] + p["wpe"][pos0:pos0 + t]
        new = []
        for i, blk in enumerate(p["blocks"]):
            a = self.ln(h, blk["ln1"])
            q = (a @ blk["wq"]).reshape(t, H, hd).transpose(1, 0, 2)
            k = (a @ blk["wk"]).reshape(t, H, hd).transpose(1, 0, 2)
            v = (a @ blk["wv"]).reshape(t, H, hd).transpose(1, 0, 2)
            K = np.concatenate([cache[i][0], k], 1) if cache else k
            Vv = np.concatenate([cache[i][1], v], 1) if cache else v
            n_prev = K.shape[1] - t
            s = q @ K.transpose(0, 2, 1) / math.sqrt(hd)
            causal = np.arange(K.shape[1])[None, :] <= (n_prev + np.arange(t))[:, None]
            s = np.where(causal[None], s, -1e9)
            s = s - s.max(-1, keepdims=True)
            w = np.exp(s)
            w /= w.sum(-1, keepdims=True)
            o = (w @ Vv).transpose(1, 0, 2).reshape(t, -1)
            h = h + o @ blk["wo"]
            g = self.ln(h, blk["ln2"]) @ blk["w1"]
            g = 0.5 * g * (1 + np.tanh(0.7978845608 * (g + 0.044715 * g ** 3)))  # gelu (tanh form, as jax.nn.gelu)
            h = h + g @ blk["w2"]
            new.append((k, v))
        logits = self.ln(h, p["lnf"]) @ p["wte"].T
        return logits, new

    @staticmethod
    def extend(cache, new):
        return [(np.concatenate([c[0], n[0]], 1), np.concatenate([c[1], n[1]], 1)) for c, n in zip(cache, new)]

    def prefill(self, toks):
        logits, kv = self.run(toks, 0, None)
        return logits, kv

    def greedy(self, cache, last_logits, pos, n, return_logits=False):
        out, seen = [], []
        logits = last_logits
        for j in range(n):
            tok = int(np.argmax(logits))
            out.append(tok)
            seen.append(logits)
            if j == n - 1:
                break
            lg, new = self.run(np.array([tok]), pos + j, cache)
            cache = self.extend(cache, new)
            logits = lg[-1]
        return (out, seen) if return_logits else out


def quantize(cache, bits):
    """Symmetric uniform quantization: keys per (head, channel), values per (head, token)."""
    qmax = 2 ** (bits - 1) - 1
    out = []
    for K, V in cache:
        sk = np.abs(K).max(axis=1, keepdims=True) / qmax
        sv = np.abs(V).max(axis=2, keepdims=True) / qmax
        sk[sk == 0] = 1
        sv[sv == 0] = 1
        out.append((np.clip(np.round(K / sk), -qmax, qmax) * sk, np.clip(np.round(V / sv), -qmax, qmax) * sv))
    return out


def measure(model, tokens):
    rng = np.random.default_rng(1)
    held = tokens[int(len(tokens) * (1 - HELD_OUT)):]
    windows = list(range(0, len(held) - PREFIX - DRAFT - 1, PREFIX + DRAFT + 1))   # non-overlapping
    pick = np.linspace(0, len(windows) - 1, min(SAMPLES, len(windows))).round().astype(int)
    starts = [windows[i] for i in pick]
    rows = {b: {"accepted": [], "full": 0, "exact_ok": 0, "free_match": [], "nll_exact": [], "nll_q": []} for b in BITS}
    # rounding: a parallel pass and step-by-step decoding need not produce bit-identical logits
    rounding = {"max_abs_logit_diff": 0.0, "positions_differing": 0, "positions": 0, "argmax_disagreements": 0,
                "min_top2_gap": math.inf}
    for s in starts:
        prefix = held[s:s + PREFIX].astype(np.int64)
        truth = held[s + PREFIX:s + PREFIX + DRAFT].astype(np.int64)
        logits, exact_kv = model.prefill(prefix)
        exact_out, seq_lg = model.greedy(exact_kv, logits[-1], PREFIX, DRAFT, return_logits=True)
        par_lg, _ = model.run(np.array(exact_out[:-1]), PREFIX, exact_kv)      # the same positions, in one pass
        for j in range(1, DRAFT):
            seq, par = seq_lg[j], par_lg[j - 1]
            rounding["max_abs_logit_diff"] = max(rounding["max_abs_logit_diff"], float(np.abs(seq - par).max()))
            rounding["positions_differing"] += int(not np.array_equal(seq, par))
            rounding["positions"] += 1
            rounding["argmax_disagreements"] += int(np.argmax(seq) != np.argmax(par))
        for lg in seq_lg:
            top2 = np.sort(lg)[-2:]
            rounding["min_top2_gap"] = min(rounding["min_top2_gap"], float(top2[1] - top2[0]))
        # teacher-forced log-likelihood of the true continuation on the exact cache
        lg_tf, _ = model.run(truth[:-1], PREFIX, exact_kv)
        all_lg = np.concatenate([logits[-1:], lg_tf], 0)
        lp = all_lg - all_lg.max(-1, keepdims=True)
        lp = lp - np.log(np.exp(lp).sum(-1, keepdims=True))
        nll_exact = -lp[np.arange(DRAFT), truth].mean()
        for b in BITS:
            q_kv = quantize(exact_kv, b)
            # the receiver's last prefill logits also come from the coarse cache: recompute the last
            # prefix position against the quantized cache of the positions before it
            last_lg, _ = model.run(prefix[-1:], PREFIX - 1, [(k[:, :-1], v[:, :-1]) for k, v in q_kv])
            draft = model.greedy(q_kv, last_lg[-1], PREFIX, DRAFT)
            # verification: one parallel pass over the drafted tokens with the EXACT cache
            vlg, _ = model.run(np.array(draft[:-1]), PREFIX, exact_kv)
            preds = [int(np.argmax(logits[-1]))] + [int(t) for t in np.argmax(vlg, -1)]
            n_ok = 0
            while n_ok < DRAFT and draft[n_ok] == preds[n_ok]:
                n_ok += 1
            final = draft[:n_ok]
            if n_ok < DRAFT:  # the verify pass also yields the exact token at the first mismatch
                final.append(preds[n_ok])
                if len(final) < DRAFT:  # then normal decoding on the exact cache continues from there
                    lg_c, new = model.run(np.array(final), PREFIX, exact_kv)
                    cache = model.extend(exact_kv, new)
                    final += model.greedy(cache, lg_c[-1], PREFIX + len(final), DRAFT - len(final))
            r = rows[b]
            r["accepted"].append(n_ok)
            r["full"] += n_ok == DRAFT
            r["exact_ok"] += final == exact_out
            r["free_match"].append(float(np.mean(np.array(draft) == np.array(exact_out))))
            lg_q, _ = model.run(truth[:-1], PREFIX, q_kv)
            allq = np.concatenate([last_lg[-1:], lg_q], 0)
            lq = allq - allq.max(-1, keepdims=True)
            lq = lq - np.log(np.exp(lq).sum(-1, keepdims=True))
            r["nll_exact"].append(float(nll_exact))
            r["nll_q"].append(float(-lq[np.arange(DRAFT), truth].mean()))
    out = {}
    L, H, hd = CFG["layers"], CFG["heads"], CFG["d"] // CFG["heads"]
    for b in BITS:
        r = rows[b]
        acc = np.array(r["accepted"])
        n_el = 2 * L * H * PREFIX * hd                         # K and V elements of the prefix cache
        n_scales = L * (H * hd + H * PREFIX)                   # K per (head, channel), V per (head, token)
        out[str(b)] = {
            "compression_vs_fp16": round(16 / b, 2),
            "compression_vs_fp16_incl_scales": round(16 * n_el / (b * n_el + 16 * n_scales), 2),
            "mean_accepted_of_draft": round(float(acc.mean()), 2),
            "median_accepted": float(np.median(acc)),
            "p10_accepted": float(np.percentile(acc, 10)),
            "drafts_fully_accepted": round(r["full"] / len(acc), 3),
            "per_token_acceptance_estimate": float(acc.sum() / (acc.sum() + (acc < DRAFT).sum())),
            "samples": len(acc),
            "final_output_identical_to_exact": f"{r['exact_ok']}/{len(acc)}",
            "free_running_token_match": round(float(np.mean(r["free_match"])), 4),
            "bits_per_byte_exact": round(float(np.mean(r["nll_exact"])) / math.log(2), 4),
            "bits_per_byte_quantized": round(float(np.mean(r["nll_q"])) / math.log(2), 4),
        }
    return out, rounding


def render(result):
    """spec_start_toy.md from the JSON alone, so `--render` can rebuild it without retraining."""
    res, rd, n_s = result["results_by_bits"], result["rounding"], result["samples"]
    train_s = result["train_seconds"]
    lines = ["# Speculative start on a toy model (MEASURED, toy scale)", "",
             f"Byte-level transformer, {result['params']:,} parameters, trained {result['config']['steps']} steps on the "
             f"first {1 - result['held_out_fraction']:.0%} of {result['corpus_bytes']:,} bytes of the repository's preserved "
             f"original documents (corpus SHA-256 {result['corpus_sha256'][:16]}…), {train_s / 60:.1f} min on this machine. "
             f"{n_s} non-overlapping held-out prompts of {result['prefix']} bytes; {result['draft']} tokens drafted greedily "
             "on the quantized cache, then verified in one parallel pass against the exact (32-bit) cache. "
             "No transfer and no timing are measured.", "",
             "| KV bits | Size vs 16-bit (with scales) | Mean tokens kept (of %d) | Median | 10th pct | Drafts fully kept | "
             "Per-token acceptance | Final output = exact | Bits/byte exact → quantized |" % result["draft"],
             "|---|---|---|---|---|---|---|---|---|"]
    for b, r in res.items():
        lines.append(f"| {b} | {r['compression_vs_fp16_incl_scales']}× smaller | {r['mean_accepted_of_draft']} | {r['median_accepted']:.0f} | "
                     f"{r['p10_accepted']:.0f} | {r['drafts_fully_accepted']:.0%} | {r['per_token_acceptance_estimate']:.3f} | "
                     f"{r['final_output_identical_to_exact']} | {r['bits_per_byte_exact']:.3f} → {r['bits_per_byte_quantized']:.3f} |")
    lines += ["", "Identical output is not guaranteed by construction. On the exact path, the one-pass check and "
              f"step-by-step decoding gave logits that differed in {rd['positions_differing']:,} of {rd['positions']:,} "
              f"positions (by up to {rd['max_abs_logit_diff']:.1e}): matrix products of different shapes add in a "
              "different order. " + (
                  f"No greedy choice changed: the smallest gap between the top two logits was {rd['min_top2_gap']:.1e}. "
                  if rd["argmax_disagreements"] == 0 else
                  f"{rd['argmax_disagreements']} greedy choices changed (smallest top-two gap {rd['min_top2_gap']:.1e}). ")
              + "A near tie could flip a token, so exact output needs batch-invariant kernels, on a CPU as on a GPU.", "",
              "Toy scale only: acceptance on production models has to be measured there "
              "(QuantSpec reports >90% with a 4-bit cache and 4-bit weights)."]
    (HERE / "spec_start_toy.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    if "--render" in sys.argv[1:]:
        render(json.loads((HERE / "spec_start_toy.json").read_text()))
        return
    tokens, files, mismatched = corpus()
    print(f"corpus: {len(tokens):,} bytes from {len(files)} hash-pinned files"
          + (f"; {len(mismatched)} differ from the manifest" if mismatched else ""))
    split = int(len(tokens) * (1 - HELD_OUT))
    t0 = time.time()
    params, log = train(tokens[:split])
    train_s = time.time() - t0
    model = Model(params)
    n_params = sum(int(np.prod(np.shape(x))) for x in __import__("jax").tree_util.tree_leaves(params))
    t1 = time.time()
    res, rounding = measure(model, tokens)
    result = {"config": CFG, "prefix": PREFIX, "draft": DRAFT, "samples": res[str(BITS[0])]["samples"],
              "held_out_fraction": HELD_OUT, "params": n_params, "train_bytes": int(split),
              "corpus_bytes": int(len(tokens)), "corpus_sha256": hashlib.sha256(tokens.tobytes()).hexdigest(),
              "corpus_files": files, "corpus_files_changed_since_manifest": mismatched,
              "train_seconds": round(train_s, 1), "measure_seconds": round(time.time() - t1, 1),
              "training_log": log, "rounding": rounding, "results_by_bits": res}
    (HERE / "spec_start_toy.json").write_text(json.dumps(result, indent=2) + "\n")
    render(result)


if __name__ == "__main__":
    main()
