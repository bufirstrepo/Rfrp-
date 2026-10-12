"""First-order models for the six speed mechanisms in docs/proposals/ARFP-speed-mechanisms.md (MODELED).

Reuses the KV-cache and compute model of speed_model.py. Every constant is either published (source in
the comment) or marked ASSUMED. No network, no queueing, no contention, one H100-equivalent per
receiver unless stated. The question each section answers: when does this mechanism save time, by
how much, and when does it lose?

    python3 bench/ideas_model.py      # offline, standard library only

Writes bench/ideas_model.md and bench/ideas_model.json.
"""
import json
import math
from pathlib import Path

from speed_model import (H100_BF16_DENSE, LLAMA, MFU, RTT_NY_LONDON, kv_bytes_per_token, kv_options,
                         prefill_flops)

HERE = Path(__file__).resolve().parent
TOY = HERE / "spec_start_toy.json"

H100_HBM = 3.35e12          # B/s, H100 SXM memory bandwidth (NVIDIA product page; research notes Q7)
HBM_EFF = 0.70              # ASSUMED fraction of HBM bandwidth achieved by a batch-1 decode step
QUANTSPEC_ACCEPT = 0.90     # QuantSpec (ICML 2025): ">90%" acceptance, draft = same model with 4-bit
                            #   KV cache AND 4-bit weights; used here as a lower bound for a KV-only draft
TOPLOC_BYTES_PER_32 = 258   # TOPLOC (ICML 2025): 258 bytes of proof per 32 new tokens
RTT_DC = 0.0001             # ASSUMED 0.1 ms round trip inside a data center
LAN_GBPS = 400              # per-GPU network inside a DGX H100-class cluster (research notes Q7)
M8 = LLAMA["Llama 3.1 8B"]


def kv(m, n):
    return kv_bytes_per_token(m) * n


def send_s(nbytes, gbps):
    return nbytes * 8 / (gbps * 1e9)


def prefill_s(m, n):
    return prefill_flops(m, n) / (MFU * H100_BF16_DENSE)


def decode_step_s(m, ctx):
    """Memory-bound batch-1 decode: read every weight and the whole KV cache once per token."""
    return (2 * m["params"] + kv(m, ctx)) / (H100_HBM * HBM_EFF)


def verify_s(m, ctx, d):
    """One parallel pass over d drafted tokens attending to a ctx-token cache: the dense matmuls plus
    attention (QK^T and AV, counted as prefill_flops counts them), or one memory-bound step, whichever
    is longer."""
    flops = 2 * m["params"] * d + 4 * m["layers"] * d * (ctx + d / 2) * m["d_model"]
    return max(decode_step_s(m, ctx), flops / (MFU * H100_BF16_DENSE))


# ---------------------------------------------------------------- 1. fidelity chosen per receiver
def per_receiver_fidelity(n=32_768):
    """Three receivers with different needs. One policy for everyone must satisfy the strictest one;
    per-receiver fidelity lets each take the fastest option its own requirements allow."""
    recv = [("R1", 400, "needs exact", {"E"}),
            ("R2", 10, "accepts bounded (E or T)", {"E", "E-pinned", "T"}),
            ("R3", 1, "accepts any class", {"E", "E-pinned", "T", "N"})]
    opts = {g: kv_options(M8, n, g) for _, g, _, _ in recv}

    def pick(g, allowed):
        return min((t, mode) for mode, (cls, t) in opts[g].items() if cls in allowed)

    rows = {}
    for label, allowed_for in (
            ("one policy for all: exact, receivers on different stacks", lambda a: {"E"}),
            ("one policy for all: exact, every receiver on the sender's pinned stack", lambda a: {"E", "E-pinned"}),
            ("per-receiver fidelity (each receiver's own requirement)", lambda a: a)):
        per = {r: pick(g, allowed_for(a)) for r, g, _, a in recv}
        rows[label] = {"per_receiver_s": {r: round(t, 3) for r, (t, _) in per.items()},
                       "choices": {r: mode for r, (_, mode) in per.items()},
                       "sum_s": round(sum(t for t, _ in per.values()), 3),
                       "slowest_s": round(max(t for t, _ in per.values()), 3)}
    return {"model": "Llama 3.1 8B", "context": n,
            "receivers": [{"id": r, "gbps": g, "requirement": req} for r, g, req, _ in recv], "rows": rows}


# ---------------------------------------------------------------- 2. start before the exact state arrives
def expected_kept(a, d):
    """Greedy verification keeps the drafted prefix up to the first mismatch, plus the exact token at
    the mismatch. Per-token acceptance a, independent: E[prefix] = sum_{i=1..d} a^i; +1 if a mismatch
    occurs within the draft (probability 1 - a^d)."""
    return sum(a ** i for i in range(1, d + 1)) + (1 - a ** d)


def speculative_start(response=256, ratio=4, overhead=0.0, acceptances=None):
    """Layered transfer: a coarse layer (1/ratio of the exact size) arrives first, then a refinement
    layer completing the exact cache. The receiver drafts on the coarse cache until the exact one is
    complete, verifies the draft in one parallel pass, keeps the matching prefix, and decodes the rest
    exactly. 'overhead' is the layered code's extra size over a direct exact transfer (0 = ideal).
    Acceptance is per token and independent (expected_kept), which real drafts only approximate."""
    acceptances = acceptances or [("QuantSpec lower bound (4-bit KV and weights)", QUANTSPEC_ACCEPT),
                                  ("0.95", 0.95), ("0.99", 0.99), ("0.999", 0.999)]
    rows = []
    for n in (8_192, 32_768, 131_072):
        S, t = kv(M8, n), decode_step_s(M8, n)
        for g in (100, 25, 10):
            t_exact_direct = send_s(S, g)
            t_e = t_exact_direct * (1 + overhead)
            t_c = send_s(S / ratio, g)
            d = min(response, int((t_e - t_c) / t))
            t_verify = verify_s(M8, n, d)
            exact_total = t_exact_direct + response * t
            lossy_total = t_c + response * t
            row = {"context": n, "link_gbps": g, "decode_step_ms": round(t * 1e3, 2),
                   "exact_arrives_s": round(t_e, 3), "coarse_arrives_s": round(t_c, 3), "drafted_tokens": d,
                   "exact_path_s": round(exact_total, 3), "lossy_path_s (outputs differ)": round(lossy_total, 3),
                   "speculative": {}}
            for label, a in acceptances:
                kept = min(response, expected_kept(a, d)) if d else 0
                spec_total = t_e + (t_verify if d else 0) + max(0.0, response - kept) * t
                row["speculative"][label] = {"tokens_kept": round(kept, 1), "total_s": round(spec_total, 3),
                                             "saving_vs_exact": round(1 - spec_total / exact_total, 4)}
            rows.append(row)
    return {"model": "Llama 3.1 8B", "response_tokens": response, "coarse_ratio": ratio,
            "layered_overhead": overhead, "rows": rows}


def speculative_start_worst_case(ratio=4, overhead=0.0):
    """Smallest saving over every modeled context and link, for acceptances from 0 to 0.999. With an
    ideal layered code the only cost is the verification pass, which the kept tokens nearly always repay."""
    grid = [(f"{a:g}", a) for a in (0.0, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 0.999)]
    r = speculative_start(ratio=ratio, overhead=overhead, acceptances=grid)
    worst = min(((v["saving_vs_exact"], v["total_s"] - row["exact_path_s"], label, row["context"], row["link_gbps"])
                 for row in r["rows"] for label, v in row["speculative"].items()))
    return {"coarse_ratio": ratio, "layered_overhead": overhead, "worst_saving": worst[0],
            "worst_extra_s": round(worst[1], 4), "at_acceptance": worst[2], "context": worst[3], "link_gbps": worst[4]}


def speculative_start_at_toy(toy):
    """The same model at the per-token acceptance the small model showed (spec_start_toy.md) for a
    4-bit coarse layer (1/4 size) and an 8-bit one (1/2 size). Scale overhead is ignored here; it is a
    few percent at production head sizes. A toy model's acceptance is not a production measurement."""
    if not toy:
        return None
    out = {}
    for bits, ratio in (("4", 4), ("8", 2)):
        a = toy[bits]
        for overhead in (0.0, 0.10):
            r = speculative_start(ratio=ratio, overhead=overhead, acceptances=[(f"{a:.4f}", a)])
            out[f"{bits}-bit coarse layer, overhead {overhead:.0%}"] = {
                "acceptance": round(a, 4), "coarse_ratio": ratio, "layered_overhead": overhead,
                "rows": [{"context": row["context"], "link_gbps": row["link_gbps"], "exact_path_s": row["exact_path_s"],
                          "speculative_s": list(row["speculative"].values())[0]["total_s"],
                          "saving_vs_exact": list(row["speculative"].values())[0]["saving_vs_exact"]}
                         for row in r["rows"]]}
    return out


# ---------------------------------------------------------------- 3. compute once, fan out
def fan_out(n=32_768, wan_gbps=10):
    """N receivers at a remote site need the same context's KV cache; the site is behind one shared
    WAN link. Time until the LAST receiver holds it, GPU-seconds spent, WAN bytes."""
    S, t_re = kv(M8, n), prefill_s(M8, n)
    rows = []
    for N in (1, 8, 64):
        tree = math.ceil(math.log2(N + 1)) if N > 1 else 1      # doubling fan-out: holders re-forward
        rows.append({"receivers": N, "strategies": {
            "each receiver recomputes": {"last_s": round(t_re, 2), "gpu_s": round(N * t_re, 2), "wan_bytes": 4 * n * N},
            "origin sends each copy over the shared WAN": {"last_s": round(N * send_s(S, wan_gbps), 2), "gpu_s": 0,
                                                           "wan_bytes": N * S},
            "one WAN copy to a site repeater, then LAN fan-out": {
                "last_s": round(send_s(S, wan_gbps) + tree * send_s(S, LAN_GBPS), 2), "gpu_s": 0, "wan_bytes": S},
            "one recompute at the site, then LAN fan-out": {
                "last_s": round(t_re + (tree * send_s(S, LAN_GBPS) if N > 1 else 0), 2), "gpu_s": round(t_re, 2),
                "wan_bytes": 4 * n}}})
    return {"model": "Llama 3.1 8B", "context": n, "kv_bytes": S, "wan_gbps": wan_gbps, "lan_gbps": LAN_GBPS,
            "rows": rows}


# ---------------------------------------------------------------- 4. cancel superseded work
def supersession(size_gb=16.06, gbps=25, interval_s=3.0, horizon_s=60.0):
    """Updates of `size_gb` (default: Llama 3.1 8B weights in BF16) produced every `interval_s` for
    `horizon_s` and sent over `gbps`. FIFO delivers every version in order; skip-to-latest finishes the
    transfer in flight, then sends only the newest pending version (superseded ones are never sent).
    Delivery delay: production to arrival of a version. Age of held state: how old the newest version
    the receiver holds is, worst case (just before each arrival)."""
    T = send_s(size_gb * 1e9, gbps)
    produced = [k * interval_s for k in range(int(horizon_s / interval_s) + 1)]

    def summary(deliveries):                     # [(arrival time, production time)] in arrival order
        delay = [t - p for t, p in deliveries]
        age = [t - p_prev for (t, _), (_, p_prev) in zip(deliveries[1:], deliveries)]
        return {"versions_sent": len(deliveries), "last_arrives_at_s": round(deliveries[-1][0], 1),
                "max_delivery_delay_s": round(max(delay), 1), "max_held_state_age_s": round(max(age), 1),
                "bytes_sent_fraction": round(len(deliveries) / len(produced), 3)}

    # FIFO
    t, fifo = 0.0, []
    for p in produced:
        t = max(t, p) + T
        fifo.append((t, p))
    # skip to latest: when the link frees up, send the newest version not yet sent
    t, last, latest = 0.0, -1.0, []
    while last < produced[-1]:
        avail = [p for p in produced if last < p <= t]
        if not avail:
            t = min(p for p in produced if p > last)
            continue
        p = avail[-1]
        t += T
        latest.append((t, p))
        last = p
    return {"update_gb": size_gb, "link_gbps": gbps, "transfer_s": round(T, 2), "interval_s": interval_s,
            "horizon_s": horizon_s, "link_load": round(T / interval_s, 2),
            "fifo": summary(fifo), "skip_to_latest": summary(latest)}


# ---------------------------------------------------------------- 5. trust by proof instead of re-running
def proof_vs_rerun(n=8_192):
    """An untrusted worker returns R generated tokens for an n-token prompt. Checking by re-running
    repeats the generation (prefill + R sequential decode steps). Checking a TOPLOC-style proof needs
    one parallel pass over the prompt and the generated tokens (they are known), which is compute-bound."""
    rows = []
    for R in (256, 1_024, 4_096):
        rerun = prefill_s(M8, n) + R * decode_step_s(M8, n + R // 2)
        check = prefill_s(M8, n + R)
        rows.append({"prompt_tokens": n, "generated_tokens": R, "rerun_s": round(rerun, 2),
                     "proof_check_s": round(check, 3), "speedup": round(rerun / check, 1),
                     "proof_bytes": TOPLOC_BYTES_PER_32 * math.ceil(R / 32)})
    return {"model": "Llama 3.1 8B", "rows": rows}


# ---------------------------------------------------------------- 6. no round trip for steady pipelines
def pipeline_push(state_bytes=(100_000, 4.29e9), gbps=10):
    """A chain of k agent handoffs. Negotiated (DEMAND, OFFER, ACCEPT, payload) costs about two round
    trips plus the transfer; a push on a standing subscription costs half a round trip plus the
    transfer (as in the speed review's push profile)."""
    rows = []
    for where, rtt in (("inside one data center (assumed 0.1 ms RTT)", RTT_DC),
                       ("between regions (56 ms, New York-London fiber minimum)", RTT_NY_LONDON)):
        for sb in state_bytes:
            for k in (1, 5, 20):
                x = send_s(sb, gbps)
                neg, push = k * (2 * rtt + x), k * (0.5 * rtt + x)
                rows.append({"where": where, "state_bytes": sb, "handoffs": k, "negotiated_s": round(neg, 4),
                             "push_s": round(push, 4), "saved_s": round(neg - push, 4),
                             "saving": round(1 - push / neg, 3)})
    return {"link_gbps": gbps, "rows": rows}


def toy_acceptance():
    if not TOY.exists():
        return None
    res = json.loads(TOY.read_text())["results_by_bits"]
    return {b: r["per_token_acceptance_estimate"] for b, r in res.items()}


def s(x):
    return f"{x:,.2f}"


def main():
    out = {"constants": {"H100_HBM_Bps": H100_HBM, "HBM_EFF (ASSUMED)": HBM_EFF, "MFU (ASSUMED)": MFU,
                         "QuantSpec_acceptance_lower_bound": QUANTSPEC_ACCEPT,
                         "TOPLOC_bytes_per_32_tokens": TOPLOC_BYTES_PER_32, "RTT_DC (ASSUMED)": RTT_DC},
           "1_per_receiver_fidelity": per_receiver_fidelity(),
           "2_speculative_start": speculative_start(),
           "2_speculative_start_layered_overhead_10pct": speculative_start(overhead=0.10),
           "2_speculative_start_coarse_half_size": speculative_start(ratio=2),
           "2_worst_case_ideal_code": [speculative_start_worst_case(4), speculative_start_worst_case(2)],
           "2_worst_case_overhead_10pct": [speculative_start_worst_case(4, 0.10), speculative_start_worst_case(2, 0.10)],
           "2_toy_measured_acceptance": toy_acceptance(),
           "2_speculative_start_at_toy_acceptance": speculative_start_at_toy(toy_acceptance()),
           "3_fan_out": fan_out(),
           "4_supersession": supersession(),
           "4_supersession_link_keeps_up": supersession(gbps=100),
           "5_proof_vs_rerun": proof_vs_rerun(),
           "6_pipeline_push": pipeline_push()}
    (HERE / "ideas_model.json").write_text(json.dumps(out, indent=2) + "\n")

    L = ["# Speed mechanisms: first-order models (MODELED)", "",
         "Reuses `speed_model.py`'s KV-cache and compute model (Llama 3.1, one H100-equivalent per receiver, "
         f"prefill at an assumed {MFU:.0%} of dense BF16 peak). Decode is modeled as memory-bound at batch 1: "
         f"every weight and the whole KV cache read once per token at an assumed {HBM_EFF:.0%} of 3.35 TB/s. "
         "No queueing, contention or loss. Each section says when the mechanism saves time and when it loses.", ""]

    r1 = out["1_per_receiver_fidelity"]
    L += ["## 1. Fidelity chosen per receiver", "",
          "Llama 3.1 8B, 32K-token context. R1 on 400 Gb/s needs exact state; R2 on 10 Gb/s accepts bounded "
          "(E or T); R3 on 1 Gb/s accepts any class. Seconds until each holds usable state:", "",
          "| Policy | R1 | R2 | R3 | Sum | Slowest |", "|---|---|---|---|---|---|"]
    for label, row in r1["rows"].items():
        p = row["per_receiver_s"]
        L.append(f"| {label} | {s(p['R1'])} | {s(p['R2'])} | {s(p['R3'])} | {s(row['sum_s'])} | {s(row['slowest_s'])} |")
    L += ["", "Choices under per-receiver fidelity: " + "; ".join(
        f"{k}: {v}" for k, v in r1["rows"]["per-receiver fidelity (each receiver's own requirement)"]["choices"].items())
        + ". The codec option counts bytes only; encoding and decoding time are not modeled.", ""]

    for key, title in (("2_speculative_start", "## 2. Start before the exact state arrives (ideal layered code)"),
                       ("2_speculative_start_layered_overhead_10pct",
                        "### Sensitivity: the layered code adds 10% over a direct exact transfer"),
                       ("2_speculative_start_coarse_half_size",
                        "### Sensitivity: coarse layer half the exact size (an 8-bit layer)")):
        r2 = out[key]
        L += [title, "",
              f"Llama 3.1 8B, {r2['response_tokens']}-token response, coarse layer 1/{r2['coarse_ratio']} of the exact "
              "size. Exact path: wait for the exact cache, then decode. Lossy path: decode on the coarse cache "
              "(outputs can differ; that is idea 1). Speculative path: draft on the coarse cache, verify once the exact "
              "cache is complete, keep the matching prefix (outputs identical to the exact path). Seconds to the full "
              "response, by per-token acceptance:", "",
              "| Context | Link | Exact path | Lossy path | a = 0.90 | a = 0.95 | a = 0.99 | a = 0.999 |",
              "|---|---|---|---|---|---|---|---|"]
        for row in r2["rows"]:
            sp = row["speculative"]
            cells = [f"{s(v['total_s'])} ({v['saving_vs_exact']:.0%})" for v in sp.values()]
            L.append(f"| {row['context'] // 1024}K | {row['link_gbps']} Gb/s | {s(row['exact_path_s'])} | "
                     f"{s(row['lossy_path_s (outputs differ)'])} | " + " | ".join(cells) + " |")
        L.append("")
    L += ["### When it loses", ""]
    for key, label in (("2_worst_case_ideal_code", "ideal layered code"),
                       ("2_worst_case_overhead_10pct", "layered code 10% larger than a direct exact transfer")):
        for w in out[key]:
            if w["worst_extra_s"] <= 0:
                L.append(f"- Coarse layer 1/{w['coarse_ratio']}, {label}: never slower than the exact path for any "
                         "acceptance from 0 to 0.999 in any row above.")
            else:
                L.append(f"- Coarse layer 1/{w['coarse_ratio']}, {label}: worst case over acceptances 0–0.999 and "
                         f"every row above is {-w['worst_saving']:.2%} slower ({w['worst_extra_s'] * 1e3:+,.1f} ms), at "
                         f"acceptance {w['at_acceptance']}, {w['context'] // 1024}K context, {w['link_gbps']} Gb/s.")
    L += ["", "With an ideal layered code the only extra cost is the verification pass: at acceptance 0 it keeps one "
          "exact token and costs one pass over the whole draft, which at long contexts takes longer than one decode "
          "step. With any acceptance worth speculating on, the kept tokens repay it."]
    L += ["", "Per-token acceptance is treated as independent, which real drafts only approximate."]
    if TOY.exists():
        t = json.loads(TOY.read_text())
        r4, d = t["results_by_bits"]["4"], t["draft"]
        a4 = r4["per_token_acceptance_estimate"]
        L[-1] += (f" On the small model with a 4-bit cache, the median draft kept {r4['median_accepted']:.0f} of {d} tokens "
                  f"and {r4['drafts_fully_accepted']:.0%} were kept whole; independent acceptance at the same average "
                  f"({a4:.3f}) would give a median of {math.log(0.5) / math.log(a4):.0f} and {a4 ** d:.0%} kept whole. "
                  "Mismatches cluster by prompt.")
    L += ["Treat these savings as first-order.", ""]
    toy = out["2_toy_measured_acceptance"]
    if toy:
        L += ["### At the acceptance the small model showed", "",
              "Measured per-token acceptance on the small model (`spec_start_toy.md`), by KV bits: "
              + ", ".join(f"{b}-bit {a:.4f}" for b, a in toy.items())
              + ". That is a sub-million-parameter model, not a production measurement. Savings against the exact "
              "path at those acceptances (ideal layered code / layered code 10% larger):", "",
              "| Coarse layer | Acceptance | Context | 100 Gb/s | 25 Gb/s | 10 Gb/s |", "|---|---|---|---|---|---|"]
        at = out["2_speculative_start_at_toy_acceptance"]
        for bits, ratio in (("4", 4), ("8", 2)):
            ideal, over = at[f"{bits}-bit coarse layer, overhead 0%"], at[f"{bits}-bit coarse layer, overhead 10%"]
            for n in (8_192, 32_768, 131_072):
                cells = []
                for g in (100, 25, 10):
                    a = next(r for r in ideal["rows"] if r["context"] == n and r["link_gbps"] == g)
                    b = next(r for r in over["rows"] if r["context"] == n and r["link_gbps"] == g)
                    cells.append(f"{a['saving_vs_exact']:.0%} / {b['saving_vs_exact']:.0%}")
                L.append(f"| {bits}-bit, 1/{ratio} size | {ideal['acceptance']:.4f} | {n // 1024}K | " + " | ".join(cells) + " |")
        L += ["", "Differences of a point or so, including the cells where the larger code looks better, come from "
              "counting whole decode steps while the exact cache arrives.", ""]

    r3 = out["3_fan_out"]
    L += ["## 3. Compute once, fan out", "",
          f"N receivers at a remote site need the same 32K-token Llama 3.1 8B cache ({r3['kv_bytes'] / 1e9:.2f} GB). "
          f"The site shares one {r3['wan_gbps']} Gb/s WAN link; inside it, links are {r3['lan_gbps']} Gb/s and holders "
          "re-forward (doubling). Seconds until the last receiver holds it / GPU-seconds spent:", "",
          "| N | Each recomputes | Origin sends each copy | One WAN copy + LAN fan-out | One recompute at the site + LAN fan-out |",
          "|---|---|---|---|---|"]
    for row in r3["rows"]:
        st = row["strategies"]
        L.append(f"| {row['receivers']} | " + " | ".join(
            f"{s(v['last_s'])} s / {s(v['gpu_s'])} GPU-s" for v in st.values()) + " |")
    L.append("")

    r4 = out["4_supersession"]
    L += ["## 4. Cancel superseded work", "",
          f"A {r4['update_gb']} GB state (Llama 3.1 8B weights in BF16) gets a new version every {r4['interval_s']:g} s "
          f"for {r4['horizon_s']:.0f} s. Delivery delay is production to arrival; age of held state is how old the "
          "receiver's newest version is just before the next one lands (worst case).", "",
          "| Link | Policy | Versions sent | Last arrives at | Worst delivery delay | Worst age of held state | Bytes sent |",
          "|---|---|---|---|---|---|---|"]
    for r in (out["4_supersession"], out["4_supersession_link_keeps_up"]):
        link = f"{r['link_gbps']} Gb/s, {r['transfer_s']} s per copy (load {r['link_load']:.0%})"
        grow = " and growing" if r["link_load"] > 1 else ""
        for name, key, g in (("Every version, in order", "fifo", grow), ("Skip to the latest", "skip_to_latest", "")):
            v = r[key]
            L.append(f"| {link} | {name} | {v['versions_sent']} | {v['last_arrives_at_s']} s | {v['max_delivery_delay_s']} s{g} | "
                     f"{v['max_held_state_age_s']} s{g} | {v['bytes_sent_fraction']:.0%} |")
    L += ["", "Skipping helps only when the link cannot keep up (load above 100%); when it can, both policies send "
          "every version.", ""]

    r5 = out["5_proof_vs_rerun"]
    L += ["## 5. Trust by proof instead of re-running", "",
          "An untrusted worker returns R tokens for an 8K-token prompt (Llama 3.1 8B). Re-running repeats the "
          "generation; checking a TOPLOC-style proof is one parallel pass over the known tokens:", "",
          "| Generated tokens | Re-run to check | Proof check | Faster by | Proof size |", "|---|---|---|---|---|"]
    for row in r5["rows"]:
        L.append(f"| {row['generated_tokens']:,} | {s(row['rerun_s'])} s | {row['proof_check_s']:.3f} s | "
                 f"{row['speedup']}× | {row['proof_bytes']:,} B |")
    L += ["", "The speedup comes from checking in one parallel pass instead of regenerating token by token; a verifier "
          "that recomputes the claimed tokens in one pass is just as fast. What the proof adds is tolerance for "
          "numeric differences across hardware, binding to the runtime and input, and a compact record a third "
          "party can check later.", ""]

    r6 = out["6_pipeline_push"]
    L += ["## 6. No round trip for steady pipelines", "",
          f"A chain of k handoffs at {r6['link_gbps']} Gb/s; negotiated ≈ 2 RTT + transfer per handoff, push ≈ ½ RTT + "
          "transfer. The baseline is ARFP's own DEMAND/OFFER/ACCEPT negotiation, not HTTP or a pub/sub system:",
          "", "| Where | State per handoff | Handoffs | Negotiated | Push | Saved |", "|---|---|---|---|---|---|"]
    for row in r6["rows"]:
        size = f"{row['state_bytes'] / 1e9:.2f} GB" if row["state_bytes"] >= 1e9 else f"{row['state_bytes'] / 1e3:.0f} KB"
        L.append(f"| {row['where']} | {size} | {row['handoffs']} | {row['negotiated_s']:.4f} s | {row['push_s']:.4f} s | "
                 f"{row['saving']:.0%} |")
    (HERE / "ideas_model.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
