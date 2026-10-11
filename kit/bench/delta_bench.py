"""Delta on an exact base: what receiver state is worth on real release pairs.

For consecutive releases of three real npm packages, take one shipped file per release and measure
what it costs to deliver release N to a receiver:
  - holding nothing:        gzip -9, brotli q11, zstd -19
  - holding release N-1:    zstd -19 in patch-from mode, release N-1 as a raw prefix
                            (the raw-dictionary mechanism of RFC 9842's dcz encoding)
  - holding an older one:   the same, with the series' first release as the base (stale cache)
  - a fast encoder:          the same delta at zstd level 3 (what a sender could afford at event time)
  - a content-aware delta:  indentation and line text as two streams, each delta-coded against the
                            previous release's streams (lossless; verified by reconstruction)
plus single-threaded decode times, SHA-256 time over the new release (the cost of an end-to-end
output check), and how many of the new release's bytes sit in lines found in the old one.
Writes bench/delta_results.json.

Network: needs registry.npmjs.org (npm pack). Sizes are deterministic; timings are not.
"""
import gzip
import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import brotli
import pyzstd
import zstandard

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
OUT = HERE / "delta_results.json"
REPEATS = 5

SERIES = [
    # (package, file inside the tarball, consecutive releases)
    ("react-dom", "package/cjs/react-dom.production.min.js", ["18.0.0", "18.1.0", "18.2.0", "18.3.0", "18.3.1"]),
    ("three", "package/build/three.module.js",
     ["0.150.0", "0.151.0", "0.152.0", "0.153.0", "0.154.0", "0.155.0", "0.156.0", "0.157.0", "0.158.0",
      "0.159.0", "0.160.0"]),
    ("typescript", "package/lib/typescript.js", ["5.4.2", "5.4.3", "5.4.4", "5.4.5", "5.5.2", "5.6.2"]),
]


def fetch(pkg, version, member):
    CACHE.mkdir(exist_ok=True)
    tgz = CACHE / f"{pkg}-{version}.tgz"
    if not tgz.exists():
        out = subprocess.run(["npm", "pack", f"{pkg}@{version}", "--pack-destination", str(CACHE), "--silent"],
                             capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1]
        produced = CACHE / out
        if produced != tgz:
            produced.rename(tgz)
    with tarfile.open(tgz) as t:
        return t.extractfile(member).read()


def median_time(fn):
    times = []
    for _ in range(REPEATS):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    return statistics.median(times)


def split_lines(data):
    """Lossless split into (indentation, rest) streams joined by newlines."""
    ind, rest = [], []
    for line in data.split(b"\n"):
        body = line.lstrip(b" \t")
        ind.append(line[: len(line) - len(body)])
        rest.append(body)
    return b"\n".join(ind), b"\n".join(rest)


def join_lines(ind, rest):
    return b"\n".join(i + r for i, r in zip(ind.split(b"\n"), rest.split(b"\n")))


def content_aware_delta(base, new):
    """Indentation and text delta-coded separately against the base's streams. Returns total bytes."""
    bi, br = split_lines(base)
    ni, nr = split_lines(new)
    if join_lines(ni, nr) != new:
        raise SystemExit("line split is not lossless")
    di, dr = zstd_delta(bi, ni), zstd_delta(br, nr)
    return {"bytes": di["bytes"] + dr["bytes"], "indent_bytes": di["bytes"], "text_bytes": dr["bytes"],
            "decode_ms": round(di["decode_ms"] + dr["decode_ms"], 2)}


def line_overlap(base, new):
    """Share of the new release's bytes in lines that occur in the old one: verbatim, and ignoring indentation."""
    old_lines = base.split(b"\n")
    exact, stripped = set(old_lines), {l.strip() for l in old_lines}
    lines = new.split(b"\n")
    total = len(new)
    return {"verbatim": round(sum(len(l) + 1 for l in lines if l in exact) / total, 4),
            "ignoring_whitespace": round(sum(len(l) + 1 for l in lines if l.strip() in stripped) / total, 4)}


def sha256_ms(data):
    return round(median_time(lambda: hashlib.sha256(data).digest()) * 1e3, 2)


def zstd_delta(base, new, level=19):
    """Delta in zstd's patch-from mode: the base is a raw prefix the decoder also holds (the raw-dictionary
    mechanism RFC 9842's dcz encoding uses). Long-distance matching on and off; the smaller one is kept.
    Every delta is verified by decoding it."""
    wlog = max(23, math.ceil(math.log2(len(base) + len(new))))
    zd = pyzstd.ZstdDict(base, is_raw=True)
    best = None
    for ldm in (False, True):
        opts = {pyzstd.CParameter.compressionLevel: level, pyzstd.CParameter.windowLog: wlog,
                pyzstd.CParameter.enableLongDistanceMatching: int(ldm)}
        t0 = time.perf_counter()
        blob = pyzstd.compress(new, level_or_option=opts, zstd_dict=zd.as_prefix)
        enc = time.perf_counter() - t0
        dopt = {pyzstd.DParameter.windowLogMax: wlog}
        if pyzstd.decompress(blob, zstd_dict=zd.as_prefix, option=dopt) != new:
            raise SystemExit("delta did not round-trip")
        if best is None or len(blob) < len(best[0]):
            best = (blob, ldm, enc)
    blob, ldm, enc = best
    dec = median_time(lambda: pyzstd.decompress(blob, zstd_dict=zd.as_prefix,
                                                option={pyzstd.DParameter.windowLogMax: wlog}))
    return {"bytes": len(blob), "ldm": ldm, "window_log": wlog, "encode_ms": round(enc * 1e3, 1),
            "decode_ms": round(dec * 1e3, 2)}


def full(new):
    br = brotli.compress(new, quality=11)                       # default 4 MiB window, as web servers use
    zs = zstandard.ZstdCompressor(level=19).compress(new)
    zd = zstandard.ZstdDecompressor()
    return {
        "raw": len(new),
        "gzip9": len(gzip.compress(new, 9, mtime=0)),
        "brotli11": len(br),
        "zstd19": len(zs),
        "brotli_decode_ms": round(median_time(lambda: brotli.decompress(br)) * 1e3, 2),
        "zstd_decode_ms": round(median_time(lambda: zd.decompress(zs)) * 1e3, 2),
    }


def main():
    results = {"tool": {"python": platform.python_version(), "zstd": pyzstd.zstd_version,
                        "brotli": brotli.__version__, "machine": platform.machine(), "repeats": REPEATS},
               "series": []}
    try:
        cpu = next(l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name"))
        results["tool"]["cpu"] = cpu
    except (OSError, StopIteration):
        pass
    for pkg, member, versions in SERIES:
        files = {}
        for v in versions:
            try:
                files[v] = fetch(pkg, v, member)
            except Exception as e:                                # noqa: BLE001
                print(f"skip {pkg}@{v}: {e}", file=sys.stderr)
        vs = [v for v in versions if v in files]
        s = {"package": pkg, "file": member.removeprefix("package/"),
             "sha256": {v: hashlib.sha256(files[v]).hexdigest() for v in vs}, "pairs": [], "stale": []}
        for prev, nxt in zip(vs, vs[1:]):
            row = {"from": prev, "to": nxt, **full(files[nxt]), "delta": zstd_delta(files[prev], files[nxt]),
                   "delta_fast": zstd_delta(files[prev], files[nxt], level=3),
                   "content_aware": content_aware_delta(files[prev], files[nxt]),
                   "line_overlap": line_overlap(files[prev], files[nxt]),
                   "sha256_ms": sha256_ms(files[nxt])}
            row["delta_over_brotli"] = round(row["delta"]["bytes"] / row["brotli11"], 4)
            s["pairs"].append(row)
            print(f"{pkg} {prev}->{nxt}: raw {row['raw']} br {row['brotli11']} delta {row['delta']['bytes']} "
                  f"({row['delta_over_brotli']:.1%} of brotli); fast {row['delta_fast']['bytes']} "
                  f"in {row['delta_fast']['encode_ms']} ms; content-aware {row['content_aware']['bytes']}; "
                  f"overlap {row['line_overlap']}; sha256 {row['sha256_ms']} ms", flush=True)
        first = vs[0]
        for nxt in vs[2:]:                                        # receiver still holds the first release
            d = zstd_delta(files[first], files[nxt])
            br = len(brotli.compress(files[nxt], quality=11))
            s["stale"].append({"from": first, "to": nxt, "delta_bytes": d["bytes"], "brotli11": br,
                               "delta_over_brotli": round(d["bytes"] / br, 4)})
        results["series"].append(s)
    OUT.write_text(json.dumps(results, indent=1) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
