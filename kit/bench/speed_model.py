"""Speed model: when do the transfer modes turn saved bytes into saved time?

Inputs
  - bench/delta_results.json   measured here (delta_bench.py): real release pairs, real compressors,
                               decode, encode and SHA-256 times on this machine
  - report.json                measured here (run_checks.py): ARFP v0.1 control-message sizes
  - constants below            published figures, each with its source; assumptions marked ASSUMED
Outputs
  - bench/speed_model.json and bench/speed_model.md

Everything here is arithmetic on those inputs. Nothing is a network measurement. Labels in the output:
MEASURED (sizes and times from this kit), SOURCED (published), MODELED (computed here).
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent

# ---------------------------------------------------------------- published constants and assumptions
IW_BYTES = 14_600            # TCP initial window, RFC 6928: min(10*MSS, max(2*MSS, 14600))
RTT_NY_LONDON = 0.056        # s, fiber minimum, High Performance Browser Networking table 1-1
H100_BF16_DENSE = 989.5e12   # FLOP/s: NVIDIA lists 1,979 TFLOPS "with sparsity"; dense is half (derived)
MFU = 0.50                   # ASSUMED prefill utilization; the one published H100 figure found is 63% (405B, 128K)
LLAMA = {                    # Meta llama-models sku_list.py; parameter counts from Hugging Face metadata
    "Llama 3.1 8B": {"params": 8_030_261_248, "layers": 32, "d_model": 4096, "kv_heads": 8, "head_dim": 128},
    "Llama 3.1 70B": {"params": 70_553_706_496, "layers": 80, "d_model": 8192, "kv_heads": 8, "head_dim": 128},
}
DCZ_HEADER = 40              # RFC 9842 dcz: 8 magic bytes + 32-byte SHA-256 of the dictionary
PUSH_FRAME_BYTES = 128       # ASSUMED design target for a compact push frame (binding ref + plan ref + chunk header)
DETERMINISTIC_COST = 42 / 26  # Thinking Machines (Sep 2025), one decode-heavy benchmark (Qwen3-8B, one GPU);
                              # ASSUMED to carry over to prefill
TEXT_BYTES_PER_TOKEN = 4     # ASSUMED average for sending prompt text instead of its KV cache


# ---------------------------------------------------------------- transport model
def slow_start(size, bw_bps, rtt, cold):
    """(flights, bytes in the last flight). Warm: one flight at line rate. Cold: initial window 14.6 KB,
    doubling each round trip until it reaches the bandwidth-delay product; the rest then streams at line
    rate. No loss, no pacing, no server think time; the connection handshake is NOT included."""
    if not cold:
        return 1, size
    bdp = bw_bps * rtt / 8
    cwnd, sent, n = IW_BYTES, 0, 0
    while True:
        n += 1
        if cwnd >= bdp or sent + cwnd >= size:
            return n, size - sent
        sent += cwnd
        cwnd *= 2


def pull(size, bw, rtt, cold):
    """Request sent -> last byte in: one round trip per flight, plus the sending time of the last flight
    (earlier flights' sending time overlaps their round trips)."""
    n, last = slow_start(size, bw, rtt, cold)
    return n * rtt + last * 8 / bw


def push(size, bw, rtt, cold):
    """Sender's event -> last byte in: one-way delay, one round trip per further flight, last flight's sending time."""
    n, last = slow_start(size, bw, rtt, cold)
    return rtt / 2 + (n - 1) * rtt + last * 8 / bw


def pull_flows(u, bw, rtt, cold, kit):
    """Receiver asks for revision N. Seconds until it holds the result. ARFP rows include the end-to-end
    SHA-256 check of the output that the HTTP rows do not do."""
    return {
        "HTTP, whole file (brotli)": pull(u["brotli"], bw, rtt, cold) + u["brotli_dec"],
        "HTTP + RFC 9842 dictionary (dcz)": pull(u["delta"] + DCZ_HEADER, bw, rtt, cold) + u["delta_dec"],
        "ARFP v0.1 negotiated (DEMAND, OFFER, ACCEPT, payload)":
            rtt + kit["offer"] * 8 / bw + pull(u["delta"] + kit["envelope"], bw, rtt, cold)
            + u["delta_dec"] + u["sha256"],
        "ARFP v0.1 fast path (OFFER with payload)":
            pull(u["delta"] + kit["fast"], bw, rtt, cold) + u["delta_dec"] + u["sha256"],
    }


def push_flows(u, bw, rtt, cold):
    """Publisher has revision N; receiver is subscribed. Seconds from the publisher's event until the
    receiver holds the result. Assumes the publisher knows each receiver's base (no miss; a miss adds one
    round trip) and, unless stated, that the delta was encoded before the event."""
    return {
        "Notify, then HTTP fetch of whole file": rtt / 2 + pull(u["brotli"], bw, rtt, cold) + u["brotli_dec"],
        "Notify, then HTTP fetch with dictionary": rtt / 2 + pull(u["delta"] + DCZ_HEADER, bw, rtt, cold) + u["delta_dec"],
        "Push whole file": push(u["brotli"], bw, rtt, cold) + u["brotli_dec"],
        "Push delta over any pub/sub channel (dcz)": push(u["delta"] + DCZ_HEADER, bw, rtt, cold) + u["delta_dec"],
        "ARFP push profile (128 B frame + delta + SHA-256 check)":
            push(u["delta"] + PUSH_FRAME_BYTES, bw, rtt, cold) + u["delta_dec"] + u["sha256"],
    }


def event_time_flows(u, bw, rtt, cold):
    """Delta encoded only when the publisher's event happens. Notify-then-fetch can encode during its own
    notify-and-request round trip, so it waits max(RTT, encode) before answering."""
    out = {}
    for label, size, enc, dec in (("zstd -3", u["fast"], u["fast_enc"], u["fast_dec"]),
                                  ("zstd -19", u["delta"], u["delta_enc"], u["delta_dec"])):
        out[f"Notify, then fetch with dictionary ({label} at the event)"] = (
            max(rtt, enc) + pull(size + DCZ_HEADER, bw, rtt, cold) - rtt + rtt / 2 + dec)
        out[f"Push delta over any pub/sub channel ({label} at the event)"] = (
            enc + push(size + DCZ_HEADER, bw, rtt, cold) + dec)
        out[f"ARFP push profile ({label} at the event, hash check)"] = (
            enc + push(size + PUSH_FRAME_BYTES, bw, rtt, cold) + dec + u["sha256"])
    return out


# ---------------------------------------------------------------- KV-cache model
def kv_bytes_per_token(m, bytes_per_elem=2):
    return 2 * m["layers"] * m["kv_heads"] * m["head_dim"] * bytes_per_elem


def prefill_flops(m, n):
    """2*P*n for the dense matmuls plus causal attention ~ 2*layers*n^2*d_model (QK^T and AV, half each)."""
    return 2 * m["params"] * n + 2 * m["layers"] * n * n * m["d_model"]


def kv_options(m, n, gbps):
    """Seconds to give a receiver the KV cache for an n-token context, per transfer mode, with its class."""
    kv = kv_bytes_per_token(m) * n
    t_re = prefill_flops(m, n) / (MFU * H100_BF16_DENSE)
    text = n * TEXT_BYTES_PER_TOKEN * 8 / (gbps * 1e9)
    return {
        "send KV, BF16 (E)": ("E", kv * 8 / (gbps * 1e9)),
        "send KV, ~4x codec (T)": ("T", kv / 4 * 8 / (gbps * 1e9)),
        "send text, recompute, default kernels (N)": ("N", text + t_re),
        "send text, recompute, batch-invariant kernels (E only on the sender's exact stack)":
            ("E-pinned", text + t_re * DETERMINISTIC_COST),
    }


def adaptive_vs_fixed(model_name="Llama 3.1 8B", n=32_768, links=(400, 10, 1)):
    m = LLAMA[model_name]
    per_link = {g: kv_options(m, n, g) for g in links}
    rows = {}
    for mode in per_link[links[0]]:
        rows[f"always: {mode}"] = {g: per_link[g][mode][1] for g in links}
    contracts = (("exact, receivers on different stacks", {"E"}),
                 ("exact, every receiver on the sender's pinned stack", {"E", "E-pinned"}),
                 ("bounded (E or T)", {"E", "E-pinned", "T"}),
                 ("any class (E, T or N)", {"E", "E-pinned", "T", "N"}))
    for contract, allowed in contracts:
        best = {g: min((t, mode) for mode, (cls, t) in per_link[g].items() if cls in allowed) for g in links}
        rows[f"adaptive, contract: {contract}"] = {**{g: best[g][0] for g in links},
                                                   "choices": {g: best[g][1] for g in links}}
    return {"model": model_name, "context": n, "links_gbps": list(links), "rows": rows}


def kv_model():
    out = []
    for name, m in LLAMA.items():
        for n in (8_192, 32_768, 131_072):
            t_re = prefill_flops(m, n) / (MFU * H100_BF16_DENSE)
            kv = kv_bytes_per_token(m) * n
            row = {"model": name, "context": n, "kv_bytes_bf16": kv, "recompute_s_per_h100": t_re,
                   "send_s": {}, "breakeven_gbps_per_h100": {}}
            for label, k in (("BF16", 1), ("FP8", 2), ("~4x codec (CacheGen-class)", 4)):
                row["breakeven_gbps_per_h100"][label] = kv / k * 8 / t_re / 1e9
            row["breakeven_gbps_8_gpus_one_link_bf16"] = 8 * row["breakeven_gbps_per_h100"]["BF16"]
            for gbps in (400, 100, 25, 1, 0.1):
                row["send_s"][gbps] = kv * 8 / (gbps * 1e9)
            out.append(row)
    return out


# ---------------------------------------------------------------- STATE summary sizes
def state_sizes():
    rows = []
    bloom_bits = lambda p: -math.log(p) / math.log(2) ** 2                          # noqa: E731
    for n in (1_000, 10_000, 100_000, 1_000_000):
        rows.append({"held_objects": n, "sha256_list": 32 * n, "short_ids_6B": 6 * n,
                     "bloom_1pct": math.ceil(n * bloom_bits(0.01) / 8),
                     "bloom_0.1pct": math.ceil(n * bloom_bits(0.001) / 8),
                     "gcs_1pct": math.ceil(n * 8.11 / 8)})
    sketch = [{"sketch_capacity": d, "minisketch_32bit_ids": 4 * d, "iblt_eppstein": 24 * d}
              for d in (10, 100, 1_000)]
    return rows, sketch


# ---------------------------------------------------------------- report
def ms(s):
    return f"{s * 1e3:,.1f}"


def main():
    delta = json.loads((HERE / "delta_results.json").read_text())
    rep = json.loads((KIT / "report.json").read_text())["sizes"]
    kit = {"offer": rep["full_update_control"]["OFFER (binding + inline 7-node plan)"],
           "envelope": rep["full_update_control"]["WORKTREE_PAYLOAD envelope"],
           "fast": rep["pose_fast_path_overhead"], "negotiated_total": rep["full_update_control_total"]}
    kit["negotiated_critical"] = kit["offer"] + kit["envelope"]
    model = {"inputs": {"kit_control_bytes": kit, "push_frame_bytes_assumed": PUSH_FRAME_BYTES,
                        "dcz_header_bytes": DCZ_HEADER, "mfu_assumed": MFU, "h100_bf16_dense": H100_BF16_DENSE,
                        "deterministic_cost_assumed": DETERMINISTIC_COST, "rtt_s": RTT_NY_LONDON}}
    md = ["# Speed model output", "",
          "Generated by `bench/speed_model.py` from `bench/delta_results.json` (measured), `report.json` "
          "(measured) and published constants. Model output, not network measurement.", ""]

    # 1. delta summary
    md += ["## 1. What receiver state is worth in bytes (MEASURED)", "",
           "Delta = zstd -19 in patch-from mode, the previous release as a raw prefix (the raw-dictionary mechanism of dcz). Fast = the same at "
           "zstd -3. Content-aware = indentation and text coded as two streams. Overlap = share of the new release's "
           "bytes in lines found in the old one, verbatim / ignoring indentation.", "",
           "| Release pair | Raw | Brotli q11 | Delta | × smaller than brotli | Fast delta (encode ms) | "
           "Content-aware | Overlap | SHA-256 ms |", "|---|---|---|---|---|---|---|---|---|"]
    summary = []
    for s in delta["series"]:
        for p in s["pairs"]:
            factor = p["brotli11"] / p["delta"]["bytes"]
            u = {"package": s["package"], "from": p["from"], "to": p["to"], "raw": p["raw"],
                 "brotli": p["brotli11"], "delta": p["delta"]["bytes"], "factor": factor,
                 "fast": p["delta_fast"]["bytes"], "content_aware": p["content_aware"]["bytes"],
                 "overlap": p["line_overlap"],
                 "brotli_dec": p["brotli_decode_ms"] / 1e3, "delta_dec": p["delta"]["decode_ms"] / 1e3,
                 "delta_enc": p["delta"]["encode_ms"] / 1e3, "fast_enc": p["delta_fast"]["encode_ms"] / 1e3,
                 "fast_dec": p["delta_fast"]["decode_ms"] / 1e3, "sha256": p["sha256_ms"] / 1e3}
            summary.append(u)
            md.append(f"| {s['package']} {p['from']} → {p['to']} | {p['raw']:,} | {p['brotli11']:,} | "
                      f"{p['delta']['bytes']:,} | {factor:,.1f}× | {p['delta_fast']['bytes']:,} "
                      f"({p['delta_fast']['encode_ms']:,.0f}) | {p['content_aware']['bytes']:,} | "
                      f"{p['line_overlap']['verbatim']:.1%} / {p['line_overlap']['ignoring_whitespace']:.1%} | "
                      f"{p['sha256_ms']:,.2f} |")
    model["delta_summary"] = summary
    md += ["", "Stale base (receiver still holds the first release of the series):", "",
           "| Package | Base → target | Delta | Share of brotli |", "|---|---|---|---|"]
    for s in delta["series"]:
        for st in s["stale"]:
            md.append(f"| {s['package']} | {st['from']} → {st['to']} | {st['delta_bytes']:,} | "
                      f"{st['delta_over_brotli']:.1%} |")

    # 2. one round trip in bytes
    md += ["", "## 2. One round trip, priced in bytes (MODELED: bandwidth × RTT)", "",
           "An extra round trip pays only if it saves more bytes than this.", "",
           "| Link | 20 ms | 56 ms (NY–London fiber minimum) | 100 ms | 160 ms |", "|---|---|---|---|---|"]
    bdp = {}
    for mbps in (10, 50, 100, 1000):
        cells = [f"{mbps * 1e6 * r / 8 / 1e3:,.0f} KB" for r in (0.02, 0.056, 0.1, 0.16)]
        bdp[mbps] = {r: mbps * 1e6 * r / 8 for r in (0.02, 0.056, 0.1, 0.16)}
        md.append(f"| {mbps} Mbit/s | " + " | ".join(cells) + " |")
    model["bdp_bytes"] = bdp

    # 3. pull and push flows for representative measured updates
    picks = [("three", "0.156.0", "0.157.0"), ("typescript", "5.4.4", "5.4.5"), ("react-dom", "18.2.0", "18.3.0")]
    cases = [(10e6, True), (100e6, True), (100e6, False), (1e9, False)]
    head = "| Flow | 10 Mbit/s cold | 100 Mbit/s cold | 100 Mbit/s warm | 1 Gbit/s warm |"
    flows = []
    md += ["", "## 3. Bytes into time for real updates (MODELED from MEASURED sizes and times)", "",
           f"RTT {RTT_NY_LONDON * 1e3:.0f} ms. Cold = new connection in slow start, handshake excluded (add one RTT "
           "to every cold cell for QUIC, two for TCP + TLS 1.3). Warm = window already open. Decode and SHA-256 "
           "times measured here (medians of 5); ARFP rows include the SHA-256 check of the output.", ""]
    for pkg, a, b in picks:
        u = next(x for x in summary if x["package"] == pkg and x["from"] == a and x["to"] == b)
        pulls = [pull_flows(u, bw, RTT_NY_LONDON, cold, kit) for bw, cold in cases]
        pushes = [push_flows(u, bw, RTT_NY_LONDON, cold) for bw, cold in cases]
        md += [f"**{pkg} {a} → {b}**: brotli {u['brotli']:,} B, delta {u['delta']:,} B "
               f"(zstd -3: {u['fast']:,} B), output {u['raw']:,} B", "",
               "Pull: from the receiver's request (ms).", "", head, "|---|---|---|---|---|"]
        for flow in pulls[0]:
            md.append(f"| {flow} | " + " | ".join(ms(r[flow]) for r in pulls) + " |")
        md += ["", "Push: from the publisher's event (ms). Assumes the publisher knows the receiver's base; "
               "a miss adds one RTT.", "", head, "|---|---|---|---|---|"]
        for flow in pushes[0]:
            md.append(f"| {flow} | " + " | ".join(ms(r[flow]) for r in pushes) + " |")
        events = [event_time_flows(u, bw, RTT_NY_LONDON, cold) for bw, cold in cases]
        md += ["", "Push and notify-then-fetch when the delta is encoded only at the event (ms; encode times "
               "are single runs). Notify-then-fetch encodes during its own round trip.", "", head, "|---|---|---|---|---|"]
        for flow in events[0]:
            md.append(f"| {flow} | " + " | ".join(ms(r[flow]) for r in events) + " |")
        md.append("")
        key = lambda bw, c: f"{int(bw / 1e6)}Mbps_{'cold' if c else 'warm'}"      # noqa: E731
        flows.append({"update": f"{pkg} {a}->{b}",
                      "pull": {key(bw, c): r for (bw, c), r in zip(cases, pulls)},
                      "push": {key(bw, c): r for (bw, c), r in zip(cases, pushes)},
                      "event_time": {key(bw, c): r for (bw, c), r in zip(cases, events)}})
    model["flows"] = flows

    # 4. control overhead vs payload
    md += ["## 4. ARFP v0.1 control bytes against payload size (MEASURED sizes)", "",
           f"Negotiated update: {kit['negotiated_total']:,} B of control messages in all, of which "
           f"{kit['negotiated_critical']:,} B (OFFER + payload envelope) precede the payload. Fast path: "
           f"{kit['fast']:,} B, measured for a one-node plan (the kit's pose fixture).", "",
           "| Payload | Negotiated, all control | Negotiated, before payload | Fast path | Push frame (128 B target) |",
           "|---|---|---|---|---|"]
    for payload in (70, 2_559, 37_000, 195_000, 1_081_000):
        c = [x / (x + payload) for x in (kit["negotiated_total"], kit["negotiated_critical"], kit["fast"],
                                         PUSH_FRAME_BYTES)]
        md.append(f"| {payload:,} B | " + " | ".join(f"{v:.1%}" for v in c) + " |")

    # 5. state summaries
    rows, sketch = state_sizes()
    model["state"] = {"membership": rows, "difference": sketch}
    md += ["", "## 5. Telling the sender what the receiver holds (MODELED from sourced formulas)", "",
           "| Objects held | SHA-256 list | 6-byte short IDs | Bloom 1% | Bloom 0.1% | Golomb-coded set 1% |",
           "|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['held_objects']:,} | {r['sha256_list']:,} B | {r['short_ids_6B']:,} B | {r['bloom_1pct']:,} B | "
                  f"{r['bloom_0.1pct']:,} B | {r['gcs_1pct']:,} B |")
    md += ["", "| Sketch capacity (≥ differences since last sync) | minisketch, 32-bit IDs (4 B per unit) | "
           "IBF (Eppstein et al., ~24 B per difference) |", "|---|---|---|"]
    for s in sketch:
        md.append(f"| {s['sketch_capacity']:,} | {s['minisketch_32bit_ids']:,} B | {s['iblt_eppstein']:,} B |")

    # 6. KV cache
    kv = kv_model()
    model["kv"] = kv
    md += ["", "## 6. AI state: send the KV cache or send the text and recompute? (MODELED)", "",
           f"Per H100 of receiver compute at {MFU:.0%} of {H100_BF16_DENSE / 1e12:,.1f} dense BF16 TFLOP/s (ASSUMED "
           "utilization). Break-even: link speed above which sending the cache beats recomputing it. It scales with "
           "the receiver's compute: multiply by G for G GPUs behind one link; divide for a weaker receiver. 70B rows "
           "are per-GPU equivalents (BF16 70B weights do not fit on one 80 GB GPU).", "",
           "| Model | Context | KV cache (BF16) | Recompute per H100 | Send at 400 Gb/s | Send at 1 Gb/s | "
           "Break-even per H100: BF16 | FP8 | ~4× codec | 8 GPUs behind one link, BF16 |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for r in kv:
        be = r["breakeven_gbps_per_h100"]
        md.append(f"| {r['model']} | {r['context']:,} | {r['kv_bytes_bf16'] / 1e9:,.2f} GB | "
                  f"{r['recompute_s_per_h100']:,.2f} s | {r['send_s'][400]:,.3f} s | {r['send_s'][1]:,.1f} s | "
                  f"{be['BF16']:,.1f} Gb/s | {be['FP8']:,.1f} Gb/s | {be['~4x codec (CacheGen-class)']:,.1f} Gb/s | "
                  f"{r['breakeven_gbps_8_gpus_one_link_bf16']:,.0f} Gb/s |")

    # 6b. adaptive vs fixed
    avf = adaptive_vs_fixed()
    model["kv_adaptive_vs_fixed"] = avf
    links = avf["links_gbps"]
    md += ["", f"### Adaptive vs fixed, {avf['model']}, {avf['context']:,}-token context, three receivers", "",
           "Seconds until each receiver holds the cache; each receiver recomputes on one H100-equivalent. The ~4× "
           "codec is lossy (CacheGen reports no more than 2% accuracy loss), so class T; its encode and decode time "
           "is left out, which flatters it. Default serving kernels are class N. Batch-invariant kernels give "
           "run-to-run determinism on one pinned stack (class E only if every receiver runs the sender's exact "
           "stack), at an ASSUMED 1.6× cost taken from a decode-heavy benchmark.", "",
           "| Strategy | " + " | ".join(f"{g} Gb/s" for g in links) + " | Worst | Sum |",
           "|---|" + "---|" * (len(links) + 2)]
    for label, r in avf["rows"].items():
        vals = [r[g] for g in links]
        md.append(f"| {label} | " + " | ".join(f"{v:,.2f}" for v in vals) + f" | {max(vals):,.2f} | {sum(vals):,.2f} |")
    md.append("")
    for label, r in avf["rows"].items():
        if "choices" in r:
            md.append(f"- {label}: " + "; ".join(f"{g} Gb/s → {r['choices'][g]}" for g in links))

    # 7. Amdahl
    md += ["", "## 7. The ceiling on any byte-saving scheme (Amdahl)", "",
           "If a fraction f of the time is spent moving bytes and the bytes shrink k-fold, speedup = 1 / ((1 - f) + f / k).", "",
           "| f (byte-bound share of the time) | k = 2 | k = 10 | k = 100 | k → ∞ |", "|---|---|---|---|---|"]
    amdahl = {}
    for f in (0.1, 0.3, 0.5, 0.9, 0.99):
        vals = [1 / ((1 - f) + f / k) for k in (2, 10, 100)] + [1 / (1 - f)]
        amdahl[f] = vals
        md.append(f"| {f:.0%} | " + " | ".join(f"{v:,.2f}×" for v in vals) + " |")
    model["amdahl"] = amdahl
    implied = 0.017 / 0.23
    md += ["", f"Back-of-envelope from Google Search (23% fewer HTML bytes, 1.7% better LCP overall, up to 9% on "
               f"high-latency networks): if LCP scaled linearly in its HTML-byte-sensitive part, that part was about "
               f"{implied:.0%} of LCP overall and up to about {0.09 / 0.23:.0%} on high-latency networks (where saved "
               f"slow-start round trips likely account for much of it)."]
    model["google_search_implied_html_byte_share"] = {"overall": implied, "high_latency": 0.09 / 0.23}

    (HERE / "speed_model.json").write_text(json.dumps(model, indent=1, default=str) + "\n")
    (HERE / "speed_model.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
