"""Shore loop slice 1 (docs/shore-loop/rocks.md): the lake's riprap rocks as quarried limestone, built from code.

A quarry blast breaks the bed into blocks along fracture planes, so a riprap stone is a convex block of a few big flat
faces and a few corner cuts, not a lump. Each face is one of two surfaces (Tools/shoreloop/cards/rock.json):
  - fresh fracture: flat overall, undulating a centimetre or two (conchoidal), rough with small ridged scarps
  - weathered rind: the bed's old surface, rounder, with dissolution pits from a few millimetres to a few centimetres
The edges are rounded a little by handling and the years, and chipped where blocks knocked together on the truck.

The mesh is a cube's grid (6 x N x N quads) pushed out along each grid direction to the block's surface: the ray from the
centre meets the nearest plane, and a soft minimum over the planes rounds the edges. Detail is a displacement along the
surface normal from numpy noise (no per-vertex Python, so a 50k-triangle rock builds in about a second).

Vertex colour (linear, read by M_WorldSurface's rock pattern 4.25 as VC): R = open (1) or in a hollow (0), G = weathered
rind (1) or fresh fracture (0), B = 1 on faces, falling toward 0 on the edges' wear. A mesh without colours reads white:
open, weathered, no edge, which is the old rocks' look.

Pure geometry (numpy only): build_props.py turns it into SM_Rock_<i>; Tools/shoreloop/rocks/render_rocks.py renders it.
"""
import math
import random

import numpy as np

# Rock kinds by index. 0-5 are the general riprap block (the breakwater's crest and faces, the bridges' shore riprap);
# 6-11 the other shapes a quarry's armour stone comes in (near-shore phase 3): a flat slab, a long block, a sharp
# angular piece, twice each. Sizes are the unscaled rock: the game scales each instance (0.35 to 2.2).
KINDS = ["block"] * 6 + ["slab", "long", "angular"] * 2
# Each rock's bounding box (x, y, z metres) as the old kit built it (main before slice 1, measured from its FBX): the
# new stones are cut to the same boxes, so every placement (breakwater, riprap, shores) keeps its footprint and packing.
OLD_SIZE = [(1.21, 1.03, 0.90), (1.09, 1.07, 0.71), (1.45, 0.95, 0.85), (1.20, 1.22, 0.79), (1.55, 1.07, 0.78),
            (1.25, 0.90, 0.95), (1.44, 1.47, 0.38), (2.32, 0.79, 0.79), (1.42, 1.05, 1.01), (1.31, 1.55, 0.42),
            (2.32, 0.94, 0.75), (1.29, 0.98, 1.11)]
CUTS = {"block": (6, 10), "slab": (4, 7), "long": (5, 8), "angular": (9, 13)}


# ---------------------------------------------------------------- vectorised noise
def _hash(ix, iy, iz, seed):
    """A 32-bit integer hash of lattice points (int64 arrays)."""
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761 & 0xFFFFFFFF)
    h &= 0xFFFFFFFF
    h = ((h ^ (h >> 15)) * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 3266489917) & 0xFFFFFFFF
    return h ^ (h >> 16)


def _u01(h):
    return (h & 0xFFFFFF).astype(np.float64) / float(0x1000000)


def perlin(p, seed=0):
    """Gradient noise in about -1..1 at points p (N, 3), one lattice cell per unit."""
    i = np.floor(p).astype(np.int64)
    f = p - i
    u = f * f * f * (f * (f * 6 - 15) + 10)
    out = 0.0
    acc = []
    for dz in (0, 1):
        for dy in (0, 1):
            for dx in (0, 1):
                h = _hash(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz, seed)
                th = _u01(h) * 2 * math.pi
                z = _u01(h >> 8) * 2 - 1
                s = np.sqrt(1 - z * z)
                g = np.stack([s * np.cos(th), s * np.sin(th), z], 1)
                d = f - np.array([dx, dy, dz])
                acc.append(((dx, dy, dz), np.sum(g * d, 1)))
    vals = {k: v for k, v in acc}
    x0 = vals[(0, 0, 0)] + u[:, 0] * (vals[(1, 0, 0)] - vals[(0, 0, 0)])
    x1 = vals[(0, 1, 0)] + u[:, 0] * (vals[(1, 1, 0)] - vals[(0, 1, 0)])
    x2 = vals[(0, 0, 1)] + u[:, 0] * (vals[(1, 0, 1)] - vals[(0, 0, 1)])
    x3 = vals[(0, 1, 1)] + u[:, 0] * (vals[(1, 1, 1)] - vals[(0, 1, 1)])
    y0 = x0 + u[:, 1] * (x1 - x0)
    y1 = x2 + u[:, 1] * (x3 - x2)
    out = y0 + u[:, 2] * (y1 - y0)
    return out * 1.6


def fbm(p, octaves, seed, lac=2.1, gain=0.5, ridged=False):
    amp, tot, norm = 1.0, 0.0, 0.0
    q = p.copy()
    for k in range(octaves):
        n = perlin(q, seed + 17 * k)
        tot = tot + amp * ((1.0 - np.abs(n)) * 2.0 - 1.0 if ridged else n)
        norm += amp
        amp *= gain
        q = q * lac
    return tot / norm


def voronoi(p, seed=0):
    """F1, F2 (distances to the nearest and second feature point, in cells) and the nearest cell's hash in 0..1."""
    i = np.floor(p).astype(np.int64)
    best1 = np.full(len(p), 9.0)
    best2 = np.full(len(p), 9.0)
    cell = np.zeros(len(p))
    for dz in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                c = i + np.array([dx, dy, dz])
                h = _hash(c[:, 0], c[:, 1], c[:, 2], seed)
                fp = c + np.stack([_u01(h), _u01(h >> 3), _u01(h >> 6)], 1) * 0.8 + 0.1
                d = np.linalg.norm(p - fp, axis=1)
                nearer = d < best1
                best2 = np.where(nearer, best1, np.minimum(best2, d))
                cell = np.where(nearer, _u01(h >> 9), cell)
                best1 = np.where(nearer, d, best1)
    return best1, best2, cell


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- the block
def planes_for(index):
    """The block's planes: (normals (P, 3), offsets (P,), weathered (P,) 0/1), its kind and its seed."""
    rng = random.Random(9001 + index * 7919)
    kind = KINDS[index % len(KINDS)]
    half = np.array(OLD_SIZE[index % len(OLD_SIZE)]) * 0.5 * 1.15 * np.array([rng.uniform(0.96, 1.04) for _ in range(3)])
    nrm, off, wea = [], [], []
    for ax in range(3):
        for sgn in (-1.0, 1.0):
            n = np.zeros(3)
            n[ax] = sgn
            tilt = np.array([rng.gauss(0, 1) for _ in range(3)])
            tilt -= n * tilt.dot(n)
            n = n + tilt * math.tan(math.radians(rng.uniform(6, 24))) / max(np.linalg.norm(tilt), 1e-9)
            n /= np.linalg.norm(n)
            nrm.append(n)
            off.append(half[ax] * rng.uniform(0.85, 1.08))
            # The bed's top and bottom are its old weathered surfaces more often than the blast's sides.
            wea.append(1.0 if rng.random() < (0.55 if ax == 2 else 0.3) else 0.0)
    for _ in range(rng.randint(*CUTS[kind])):
        d = np.array([rng.gauss(0, 1) for _ in range(3)])
        d /= np.linalg.norm(d)
        support = float(np.sum(np.abs(d) * half))
        nrm.append(d)
        off.append(support * rng.uniform(0.66, 0.9 if kind != "angular" else 0.84))
        wea.append(1.0 if rng.random() < 0.15 else 0.0)
    return np.array(nrm), np.array(off), np.array(wea), kind, rng


def build(index, cuts=63):
    """The rock's grid: verts (V, 3), quads (F, 4), vertex colours (V, 3), kind. cuts: grid lines per cube edge."""
    nrm, off, wea, kind, rng = planes_for(index)
    seed = 1000 + index * 31
    verts, quads = cube_grid(cuts)
    u = verts / np.linalg.norm(verts, axis=1, keepdims=True)
    cos = u @ nrm.T                                             # (V, P)
    t = np.where(cos > 1e-6, off[None, :] / np.maximum(cos, 1e-6), 1e6)
    tmin = t.min(1, keepdims=True)
    k = rng.uniform(0.012, 0.022) if kind != "angular" else rng.uniform(0.006, 0.012)   # edge rounding (m)
    w = np.exp(-(t - tmin) / k)
    ts = tmin[:, 0] - k * np.log(w.sum(1))
    w /= w.sum(1, keepdims=True)
    p = u * ts[:, None]
    n = w @ nrm
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    weathered = w @ wea
    edge = smoothstep(0.08, 0.5, 1.0 - w.max(1))               # 0 on a face, 1 along an edge's crest

    # Fresh fracture: conchoidal undulation, ridged roughness, small scarps where the break stepped.
    und = fbm(p * 1.6, 2, seed) * 0.03 + fbm(p * 4.5, 2, seed + 1) * 0.012 + perlin(p * 9.0, seed + 3) * 0.004
    rough = fbm(p * 14.0, 3, seed + 5, ridged=True) * 0.006 + fbm(p * 5.0, 2, seed + 7, ridged=True) * 0.007
    s = perlin(p * 3.5, seed + 9) * 5.0
    scarp = (np.round(s) - s) * 0.0045 * smoothstep(0.2, 0.6, np.abs(perlin(p * 1.7, seed + 11)))
    fresh = und + rough + scarp
    # Weathered rind: rounder, softly lumpy, pitted by solution at two scales.
    lump = fbm(p * 1.8, 3, seed + 21) * 0.03 + fbm(p * 7.0, 2, seed + 23) * 0.005
    # Pits gather where the rind is softest (a slow noise), a few millimetres to two centimetres deep and wide.
    soft = smoothstep(-0.1, 0.5, fbm(p * 3.0, 2, seed + 29))
    f1, f2, ch = voronoi(p / 0.055, seed + 25)
    pits = -np.where(ch < 0.55 * soft, 1.0, 0.0) * (0.004 + 0.008 * _u01(_hash(np.floor(ch * 1e6).astype(np.int64), 0, 0, seed))) \
        * np.clip(1 - (f1 / 0.42) ** 2, 0, 1) ** 2
    g1, g2, gh = voronoi(p / 0.018, seed + 27)
    pits += -np.where(gh < 0.4 * soft, 1.0, 0.0) * 0.0022 * np.clip(1 - (g1 / 0.45) ** 2, 0, 1) ** 2
    rind = lump + pits
    disp = fresh * (1.0 - weathered) + rind * weathered
    # Chips along the edges: flat scars a few centimetres across, cut back a centimetre or so, soft at their rims.
    c1, c2, chh = voronoi(p / 0.075, seed + 31)
    chip = np.where(chh < 0.55, 1.0, 0.0) * (0.006 + 0.014 * _u01(_hash(np.floor(chh * 1e6).astype(np.int64), 1, 0, seed)))
    chip *= smoothstep(0.0, 0.12, c2 - c1) * smoothstep(0.15, 0.55, edge)
    disp -= chip
    p = p + n * disp[:, None]

    # Recentre on the bounding box and fit it to the old rock's box (a few per cent per axis after the cuts).
    lo, hi = p.min(0), p.max(0)
    p -= (lo + hi) / 2
    p *= np.array(OLD_SIZE[index % len(OLD_SIZE)]) / (hi - lo)

    open_, convex = cavity(p, quads)
    col = np.stack([open_, weathered, 1.0 - np.maximum(edge * 0.8, convex)], 1)
    return p, quads, np.clip(col, 0.0, 1.0), kind


def cube_grid(cuts):
    """A cube from -1 to 1 as a grid of quads, shared vertices along its edges: (verts (V, 3), quads (F, 4))."""
    m = cuts + 1
    lin = np.linspace(-1.0, 1.0, m + 1)
    index = {}
    verts = []

    def vid(c):
        key = tuple(np.round(c, 6))
        j = index.get(key)
        if j is None:
            j = len(verts)
            index[key] = j
            verts.append(c)
        return j
    quads = []
    for ax in range(3):
        for sgn in (-1.0, 1.0):
            a1, a2 = [a for a in range(3) if a != ax]
            ids = np.zeros((m + 1, m + 1), np.int64)
            for i, s in enumerate(lin):
                for j, tt in enumerate(lin):
                    c = np.zeros(3)
                    c[ax] = sgn
                    c[a1] = s
                    c[a2] = tt
                    ids[i, j] = vid(c)
            for i in range(m):
                for j in range(m):
                    quads.append([ids[i, j], ids[i + 1, j], ids[i + 1, j + 1], ids[i, j + 1]])
    verts, quads = np.array(verts), np.array(quads, np.int64)
    # Wind every quad outward (its normal along its centre's direction from the cube's centre).
    a, b, c, d = (verts[quads[:, k]] for k in range(4))
    inward = np.sum(np.cross(c - a, d - b) * (a + b + c + d), 1) < 0
    quads[inward] = quads[inward][:, ::-1]
    return verts, quads


def cavity(p, quads):
    """Per vertex: open (1) to deep in a hollow (0), and convexity (0 flat to 1 a sharp crest), from the mesh's mean
    curvature at a few centimetres and at a decimetre."""
    e = np.concatenate([quads[:, [0, 1]], quads[:, [1, 2]], quads[:, [2, 3]], quads[:, [3, 0]]])
    e = np.unique(np.sort(e, 1), axis=0)
    nv = len(p)
    deg = np.bincount(e.ravel(), minlength=nv).astype(np.float64)
    # Vertex normals from the quads (area weighted).
    a, b, c, d = (p[quads[:, k]] for k in range(4))
    fn = np.cross(c - a, d - b)
    vn = np.zeros_like(p)
    for k in range(4):
        np.add.at(vn, quads[:, k], fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)

    def lap(x):
        s = np.zeros_like(x)
        np.add.at(s, e[:, 0], x[e[:, 1]])
        np.add.at(s, e[:, 1], x[e[:, 0]])
        return s / deg[:, None] if x.ndim == 2 else s / deg

    el = np.mean(np.linalg.norm(p[e[:, 0]] - p[e[:, 1]], axis=1))
    # Positive where the surface bulges out (crest), negative in a hollow.
    curv = -np.sum((lap(p) - p) * vn, 1) / (el * el)
    fine = curv.copy()
    for _ in range(3):
        fine = lap(fine[:, None])[:, 0] * 0.5 + fine * 0.5
    broad = curv.copy()
    for _ in range(30):
        broad = lap(broad[:, None])[:, 0] * 0.5 + broad * 0.5
    hollow = smoothstep(2.0, 12.0, -(0.4 * fine + 0.6 * broad * 2.5))
    convex = smoothstep(4.0, 20.0, fine)
    return 1.0 - hollow, convex
