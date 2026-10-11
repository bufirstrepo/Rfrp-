"""Toy application profile "scene.assembly.v1".

Geometry is integer micrometres so exact paths are genuinely exact. The "learned" surface
decoder is simulated: quantization error plus a per-device jitter whose spread is the
runtime's declared divergence bound. Nothing here is a real codec; it exists so the
protocol rules can be exercised on concrete bytes and measured distances.
"""
import hashlib
from decimal import Decimal

from .canon import H, encode, num

PROFILE = "scene.assembly.v1"

UNIT_CIRCLE_12 = [(1000, 0), (866, 500), (500, 866), (0, 1000), (-500, 866), (-866, 500),
                  (-1000, 0), (-866, -500), (-500, -866), (0, -1000), (500, -866), (866, -500)]


def box(x0, y0, z0, x1, y1, z1):
    return [[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]


def translate(points, dx, dy, dz):
    return [[x + dx, y + dy, z + dz] for x, y, z in points]


def bolt_circle(cx, cy, z, r):
    # Integer-only generator. Division rounding is part of the runtime spec: Python's //
    # floors (-1 // 2 == -1) where C truncates toward zero (-1 / 2 == 0).
    return [[cx + r * c // 1000, cy + r * s // 1000, z] for c, s in UNIT_CIRCLE_12]


def surface(x0, y0, z, step, n):
    return [[x0 + i * step, y0 + j * step, z + (i * j) % 7 * 40] for i in range(n) for j in range(n)]


def linf(p, q):
    return max(abs(p[0] - q[0]), abs(p[1] - q[1]), abs(p[2] - q[2]))


def hausdorff(a, b):
    """Hausdorff distance under the L-infinity ground metric: a true metric on finite sets."""
    return max(max(min(linf(p, q) for q in b) for p in a), max(min(linf(p, q) for p in a) for q in b))


def clearance(a, b):
    return min(linf(p, q) for p in a for q in b)


def um_to_mm(um):
    return num(str(Decimal(um) / Decimal(1000)))


# ---------- simulated latent path ----------

def latent_encode(points, grid):
    return encode({"grid": grid, "q": [[(c + grid // 2) // grid for c in p] for p in points]})


def _jitter(device, i, axis, j):
    h = hashlib.sha256(f"{device}|{i}|{axis}".encode()).digest()
    return int.from_bytes(h[:4], "big") % (2 * j + 1) - j


def latent_decode(payload_obj, device, jitter_um):
    """Dequantize, then add device-dependent jitter in [-jitter_um, +jitter_um] per axis.
    Two conforming devices therefore differ by at most 2 * jitter_um: the T-class bound."""
    g = payload_obj["grid"]
    return [[c * g + _jitter(device, i, a, jitter_um) for a, c in enumerate(p)]
            for i, p in enumerate(payload_obj["q"])]


def texture_decode(payload, device):
    """Non-reproducible generator (N-class): output depends on the device."""
    seed = hashlib.sha256(payload + device.encode()).digest()
    out = b""
    while len(out) < 4096:
        seed = hashlib.sha256(seed).digest()
        out += seed
    return out[:4096]


# ---------- profile validators ----------

def project(y, regions):
    return encode({r: y[r] for r in regions})


def bolt_features(points):
    return H(encode(sorted([[c // 10 for c in p] for p in points])))
