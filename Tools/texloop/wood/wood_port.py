"""Texture loop, wood: a numpy mirror of BOAT_CODE's path for the two wood kinds (scripts/make_materials.py: surf 6
varnished wood, surf 7 bare teak), so a round can be measured and rendered in the cloud without Unreal.

It mirrors, for one flat face of a part lying along the boat's X (the grain along X, U along X):
  the value noise vn, the gelcoat chalk (gel is 0 on Grain parts since this loop), the Grain block, the wood block
  (WOOD_CODE below is the HLSL; wood() is its twin) and, with detail=True (High and Ultra), the WoodVarnish or
  TeakWeathered detail maps' colour and roughness terms.
Keep wood() and the HLSL in scripts/make_materials.py in step: tests/test_wood_port.py checks the constants match.

    from wood_port import shade
    out = shade("varnish", age=6, care=0.5, size_m=(1.0, 0.25), px_per_mm=1, detail=True)
    out["albedo"] (linear RGB), out["rough"], out["coat"], out["failed"] (0-1 mask of failed film / grey wood)
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import wear  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DETAIL = os.path.join(ROOT, "Inputs", "boat-detail")

# BOAT_LIBRARY Wood and Teak (colour linear, roughness, clear coat). Read from make_materials.py so they can't drift.
def library():
    import ast
    src = open(os.path.join(ROOT, "scripts", "make_materials.py")).read()
    i = src.index("BOAT_LIBRARY = {")
    j = src.index("\n}\n", i)
    lib = ast.literal_eval(src[i + len("BOAT_LIBRARY = "):j + 2])
    return {k: lib[k] for k in ("Wood", "Teak")}


def frac(x):
    return x - np.floor(x)


def h2(x, y):
    return frac(np.sin(x * 12.99 + y * 78.23) * 43758.5)


def value_noise(LP):
    """BOAT_CODE's vn: three octaves (37, 9, 2.2 cm) of value noise anchored to the boat."""
    vn = np.zeros(LP[0].shape)
    amp, sc = 0.6, 37.0
    for o in range(3):
        qx = (LP[0] + LP[2] * 0.6) / sc + o * 17.3
        qy = (LP[1] - LP[2] * 0.4) / sc + o * 17.3
        ix, iy = np.floor(qx), np.floor(qy)
        fx, fy = qx - ix, qy - iy
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        a00, a10, a01, a11 = h2(ix, iy), h2(ix + 1, iy), h2(ix, iy + 1), h2(ix + 1, iy + 1)
        vn += amp * ((a00 * (1 - fx) + a10 * fx) * (1 - fy) + (a01 * (1 - fx) + a11 * fx) * fy)
        amp *= 0.5
        sc /= 4.1
    return vn / 1.05


def sat(x):
    return np.clip(x, 0.0, 1.0)


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(e0, e1, x):
    t = sat((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def fine_noise(x, y):
    """One octave of value noise on a unit grid (rounded blobs, not square cells)."""
    ix, iy = np.floor(x), np.floor(y)
    fx, fy = x - ix, y - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a00, a10, a01, a11 = h2(ix + 3.1, iy), h2(ix + 4.1, iy), h2(ix + 3.1, iy + 1), h2(ix + 4.1, iy + 1)
    return (a00 * (1 - fx) + a10 * fx) * (1 - fy) + (a01 * (1 - fx) + a11 * fx) * fy


def specks(x, y, density):
    """Round dots on a unit grid: a cell holds one (random size and place inside it) with probability density."""
    ix, iy = np.floor(x), np.floor(y)
    hc = h2(ix + 9.7, iy + 1.3)
    ox, oy = h2(ix + 2.2, iy + 5.5) - 0.5, h2(ix + 7.4, iy + 0.6) - 0.5
    r = 0.12 + 0.18 * h2(ix + 0.3, iy + 8.8)
    d = np.hypot(x - ix - 0.5 - 0.5 * ox, (y - iy - 0.5 - 0.5 * oy) * 1.4) * (0.8 + 0.4 * fine_noise(x * 4.0, y * 4.0))
    return (1.0 - smoothstep(r * 0.7, r, d)) * (hc > 1.0 - density)


def time_dirt(age, care):
    """The shared wear split (Tools/texloop/wear.py, BOAT_CODE's timeK and dirtK)."""
    if age < 0:
        return None
    return float(wear.time_k(age, care)), float(wear.dirt_k(age, care))


_tex = {}


def tex(name):
    if name not in _tex:
        _tex[name] = np.asarray(Image.open(os.path.join(DETAIL, name)).convert("RGB")).astype(np.float64) / 255.0
    return _tex[name]


def sample(t, u, v):
    """Bilinear, wrapped (the sampler is View.MaterialTextureBilinearWrapedSampler); u, v in tiles."""
    h, w = t.shape[:2]
    x, y = frac(u) * w - 0.5, frac(v) * h - 0.5
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    x0 %= w
    y0 %= h
    x1, y1 = (x0 + 1) % w, (y0 + 1) % h
    return (t[y0, x0] * (1 - fx) + t[y0, x1] * fx) * (1 - fy) + (t[y1, x0] * (1 - fx) + t[y1, x1] * fx) * fy


# ------------------------------------------------------------------ the wood block (keep in step with WOOD_CODE)
# Constants shared with the HLSL (tests/test_wood_port.py greps make_materials.py for each of these numbers).
K = dict(
    v_time_dark=(0.68, 0.56, 0.48),   # varnished wood under the film darkens and reddens with Time (L3)
    v_amber=(1.03, 0.97, 0.84),       # the film itself yellows with Time
    v_bare=(0.125, 0.105, 0.08),       # failed film: the wood goes grey (linear)
    v_stain=(0.035, 0.03, 0.025),     # black water stains wick along the grain from failed edges
    t_silver=(0.215, 0.205, 0.19),    # bare teak's silver-grey (linear, club teak sRGB ~ 140)
    t_dark=(0.055, 0.052, 0.046),     # mildewed, neglected teak (linear)
    t_oil=0.70,                       # oiled teak: darker
)


def wood(kind, col, rough, coat, vn, LP, ring, td, wearx=0.3):
    """The surf 6 / surf 7 weathering. col (H,W,3) linear after the Grain block; returns col, rough, coat, failed."""
    if td is None:
        T = D = wearx
        careK = 0.5
        ageY = 6.0
    else:
        T, D = td
        careK, ageY = td_care[0], td_care[1]
    failed = np.zeros(vn.shape)
    # a slow field along the part (stains and failures run along the grain, in patches): vn stretched along X
    pn = value_noise((LP[0] * 1.0, LP[1] * 2.5, LP[2]))
    if kind == "varnish":
        # the wood under the film darkens and reddens over the years, whatever the care
        col = col * lerp(np.ones(3), np.array(K["v_time_dark"]), T * T)   # slow at first: decades, not years
        # kept older boats are sanded back and recoated: their film is fresh; otherwise it satins within months
        recoat = smoothstep(0.5, 0.9, careK) * sat(ageY / 3.0)
        satin = sat(T * 6.0) * (1.0 - recoat)
        # the film ambers
        col = col * lerp(np.ones(3), np.array(K["v_amber"]), 0.6 * T)
        # failed film: grows from (1 - care); patches along the grain plus the ring's soft early wood
        cover = 1.4 * sat(D - 0.24) ** 2.0                       # fraction of the surface failed
        # jagged, flaking edges: a 4 mm cell hash breaks the patch outline up
        fl = fine_noise(LP[0] / 0.5, LP[1] / 0.35)
        f = pn * 0.75 + 0.25 * (1 - ring) + 0.06 * (fl - 0.5)
        thr = 0.725 - 0.62 * cover + 0.14 * cover * cover  # f's quantile at 1 - cover (measured over a 1 m face)
        fw = 0.03 + 0.08 * (1.0 - sat((D - 0.24) * 2.0))           # a soft worn-through edge early, a torn one late
        failed = smoothstep(thr - fw, thr + fw, f) * (cover > 0.001)
        bare = lerp(col * 0.55 + np.array(K["v_bare"]) * 0.45, np.array(K["v_bare"]), sat(D * 1.2))[...]
        # water stains: black along the grain at the failed patches' edges
        edge = sat(1.0 - np.abs(f - thr) * 9.0) * sat((D - 0.5) * 2.5)
        bare = lerp(bare, np.array(K["v_stain"]), (0.55 * edge * sat(0.6 + 0.4 * ring))[..., None])
        # the film's torn edge lifts and goes white (frosted) just inside the intact side
        lift = smoothstep(thr - 0.07, thr - 0.03, f) * (1.0 - failed) * sat((D - 0.3) * 2.5)
        col = lerp(col, col * 0.75 + 0.06, (0.35 * lift)[..., None])
        # what film is left on a neglected boat has gone dark amber
        col = col * lerp(np.ones(3), np.array([0.80, 0.68, 0.50]), sat((D - 0.6) * 2.5))
        col = lerp(col, bare, failed[..., None])
        # the intact film hazes with Dirt (fine scratches, dried spray, UV-bleached wood under it): greyer, flatter
        lumv = (col * np.array([0.3, 0.59, 0.11])).sum(-1, keepdims=True)
        col = lerp(col, lumv * 1.05, 0.35 * sat((D - 0.2) * 2.0))
        # the intact film dulls with Dirt (fine scratches, dried spray)
        rough = lerp(lerp(lerp(rough, 0.45, 0.8 * satin), 0.36, sat((D - 0.2) * 2.0)), 0.78, failed)
        coat = coat * (1.0 - 0.25 * satin) * (1.0 - 0.2 * sat((D - 0.2) * 2.0)) * (1.0 - failed)
    else:
        # bare teak: silvers in the sun within the first year unless it is oiled (care, on an older boat)
        silver = sat(T * 3.0) * (1.0 - smoothstep(0.5, 0.9, careK) * sat(ageY / 3.0))
        lum = (col * np.array([0.3, 0.59, 0.11])).sum(-1, keepdims=True)
        # not evenly: hands and spray keep some patches browner (Bean's lesson J/22)
        sv = 0.95 * silver * (0.72 + 0.28 * sat(pn * 2.0 - 0.3))
        col = lerp(col, np.array(K["t_silver"]) * (lum / 0.2) ** 0.5, sv[..., None])
        # oiled: darker and a little glossier
        oil = smoothstep(0.5, 0.9, careK) * sat(ageY / 3.0) * (1.0 - silver)
        col = col * lerp(1.0, K["t_oil"], oil)
        # neglect: mildew darkens it in patches along the grain, black in the checks
        mil = sat((D - 0.45) * 2.0) * (0.68 + 0.2 * pn + 0.12 * (1.0 - ring))   # streaky along the grain
        col = lerp(col, np.array(K["t_dark"]), (0.95 * mil)[..., None])
        # mildew specks: black dots, 5 mm cells, more of them the dirtier it is
        dots = specks(LP[0] / 1.5, LP[1] / 0.6, 0.30 * sat((D - 0.6) * 3.0)) * (0.5 + 0.5 * fine_noise(LP[0] / 0.3, LP[1] / 0.3))
        col = lerp(col, np.array(K["t_dark"]) * 0.4, (0.5 * dots)[..., None])
        failed = mil
        rough = lerp(rough, 0.86, sat(silver + 0.5 * D)) - 0.12 * oil
        coat = coat * 0.0
    return col, rough, coat, failed


td_care = (0.5, 6.0)
# BOAT_LIBRARY's two rows before this loop (main at 8219696), for the 'before' column
OLD_LIBRARY = {"Wood": ("M_BoatSurface", (0.30, 0.17, 0.07), 0.30, 0.0, 1.0, 0.0, 0.15),
               "Teak": ("M_BoatSurface", (0.22, 0.19, 0.15), 0.85, 0.0, 0.0, 0.0, 0.5)}


def shade(kind, age, care, size_m=(1.0, 0.25), px_per_mm=1.0, detail=True, origin_cm=(0.0, 0.0, 0.0), wearx=0.3,
          new=True):
    """Albedo (linear), roughness, clear coat and the failed mask of a flat top face of a wood part.
    new=False runs the shader as it was before this loop (main at 8219696) for the 'before' column."""
    global td_care
    lib = library() if new else OLD_LIBRARY
    slot = "Wood" if kind == "varnish" else "Teak"
    base, r0, coat0 = np.array(lib[slot][1]), lib[slot][2], lib[slot][4]
    nx, ny = int(size_m[0] * 1000 * px_per_mm), int(size_m[1] * 1000 * px_per_mm)
    xs = origin_cm[0] + (np.arange(nx) + 0.5) / nx * size_m[0] * 100
    ys = origin_cm[1] + (np.arange(ny) + 0.5) / ny * size_m[1] * 100
    X, Y = np.meshgrid(xs, ys)
    Z = np.full_like(X, origin_cm[2])
    LP = (X, Y, Z)
    vn = value_noise(LP)
    col = np.broadcast_to(base, X.shape + (3,)).copy()
    rough = np.full(X.shape, r0)
    coat = np.full(X.shape, coat0)
    ageK = sat(age / 20.0) * (1 - 0.6 * sat(care)) if age >= 0 else wearx
    up = 1.0
    if not new:
        # the old gelcoat chalk ran on varnished wood too (gel = Coat for a non-metal, non-non-skid slot)
        gel = sat(coat0)
        ox = sat(max(wearx, ageK)) * gel * (0.55 + 0.45 * up)
        lum = (col * np.array([0.3, 0.59, 0.11])).sum(-1, keepdims=True)
        chalk = lerp(lerp(lum, np.array([0.82, 0.80, 0.74]), 0.5) * 1.02, col * 1.25 + lum * 0.35 + 0.01, sat(1.0 - lum * 2.5))
        col = lerp(col, chalk, 0.4 * ox)
        rough = lerp(rough, 0.72, ox)
        coat = coat * (1 - 0.85 * ox)
    # Grain block
    gw = LP[1] * 0.9 + LP[2] * 1.3 + 2.5 * np.sin(LP[0] * 0.021) + 1.2 * np.sin(LP[0] * 0.083 + LP[1])
    ring = 0.5 + 0.5 * np.sin(gw * 6.0 + 4.0 * vn)
    fleck = sat(vn * 3.0 - 1.9)
    # the broad figure; close up on High the detail map carries the fine grain, so the figure steps back there
    fig = 0.5 if (new and detail and kind == "varnish") else 1.0
    col = col * (lerp(1.0 - 0.28 * fig, 1.0 + 0.12 * fig, ring) * (1 - 0.25 * fleck))[..., None]
    rough = rough * lerp(0.85, 1.25, ring)
    failed = np.zeros(X.shape)
    if new:
        td = time_dirt(age, care)
        td_care = (care, age) if age >= 0 else (0.5, 6.0)
        col, rough, coat, failed = wood(kind, col, rough, coat, vn, LP, ring, td, wearx)
    else:
        if kind == "varnish":
            fail = ageK * sat(vn * 2.2 - 0.6 + ageK * 0.6)
            col = lerp(col * lerp(np.ones(3), np.array([1.06, 0.98, 0.82]), ageK), np.array([0.30, 0.28, 0.25]), (0.7 * fail)[..., None])
            rough = lerp(rough, 0.75, fail)
            coat = coat * (1 - fail)
            failed = fail
        else:
            col = lerp(col, np.array([0.30, 0.29, 0.27]), 0.6 * ageK)
            rough = lerp(rough, 0.9, 0.5 * ageK)
    if detail:
        tile = (0.25, 0.125)
        u, v = (X / 100.0) / tile[0], (Y / 100.0) / tile[1]
        name = "WoodVarnish" if kind == "varnish" else "TeakWeathered"
        m = sample(tex(f"T_Detail_{name}_M.png"), u, v)
        if kind == "varnish":
            col = col * (lerp(0.82, 1.12, m[..., 0]) if not new else lerp(0.70, 1.16, m[..., 0]))[..., None]
            if new:   # bare, failed wood: its open pores and checks go dark
                col = lerp(col, col * 0.45, (m[..., 1] * failed)[..., None])
        else:
            sk = (sat(time_dirt(td_care[1], td_care[0])[0] * 3.0) if (new and td_care[1] >= 0) else 0.0)
            col = col * lerp(0.72 - 0.20 * sk, 1.15 + 0.05 * sk, m[..., 0])[..., None]
            rough = sat(rough + 0.1 * m[..., 1])
        if new:
            col, rough = detail_new(kind, col, rough, m, failed, td_care)
    return dict(albedo=np.clip(col, 0, 1), rough=sat(rough), coat=sat(coat), failed=sat(failed), vn=vn)


def detail_new(kind, col, rough, m, failed, tdc):
    """High and Ultra only (the detail map's masks): varnish fails first where its film is thin (B); teak's checks (G)
    go black as it is neglected."""
    if kind == "teak":
        care, age = tdc
        d = time_dirt(age, care)[1] if age >= 0 else 0.3
        col = lerp(col, np.array(K["t_dark"]) * 0.5, (m[..., 1] * sat(0.3 + d))[..., None])
    return col, rough
