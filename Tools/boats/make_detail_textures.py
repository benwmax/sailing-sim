"""Close-up detail textures for boat surfaces, tileable, built from numpy (no photos).

    python3 Tools/boats/make_detail_textures.py [out dir] [--res 1024]

The baked hero maps carry the boat's own colour, wear and dirt at a few millimetres per texel, which is too coarse for
a helm's-eye camera that sits half a metre over the cockpit. These tile at true scale on top of them, masked by the
baked detail map (T_<Boat>_<Group>_X: R non-skid, G teak, B smooth gelcoat), and fade out with distance:

  T_Detail_NonSkid_N/_M     moulded non-skid, 100 mm tile: a 45-degree grid of rounded pyramids at 2.5 mm pitch with
                            sanding scatter; M: R cavity (where grime sits), G top polish (tops worn smooth), B height
  T_Detail_Gelcoat_N/_M     250 mm tile: orange peel (1-3 mm) and fine buffing scratches; M: R scratches, G roughness
  T_Detail_TeakWeathered_N/_M  300 mm along the grain x 150 mm across: weathered teak, the soft early wood eroded
                            between ridges of latewood, open checks; M: R grain luminance, G checks, B height
  T_Detail_Canvas_N         50 mm tile: plain-weave cushion and bag cloth

Each texture's real size is in detail_textures.json, so a material tiles it as UV x (metres per UV unit) / tile size.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image

ARGS = sys.argv[1:]
OUT = ARGS[0] if ARGS and not ARGS[0].startswith("--") else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Inputs", "boat-detail")
RES = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else 1024
os.makedirs(OUT, exist_ok=True)
RNG = np.random.default_rng(22)


def periodic_noise(res, cells, octaves=4, persistence=0.5, seed=0):
    """Tileable value noise: random lattice values wrapped, bicubic-smoothed through FFT low-pass per octave."""
    rng = np.random.default_rng(seed)
    out = np.zeros((res, res))
    amp, total = 1.0, 0.0
    for o in range(octaves):
        c = cells * 2 ** o
        if c > res:
            break
        lat = rng.random((c, c))
        # upsample with periodic cosine interpolation
        idx = np.arange(res) * c / res
        i0 = np.floor(idx).astype(int)
        f = idx - i0
        f = f * f * (3 - 2 * f)
        i1 = (i0 + 1) % c
        a = lat[i0][:, i0] * (1 - f)[None, :] + lat[i0][:, i1] * f[None, :]
        b = lat[i1][:, i0] * (1 - f)[None, :] + lat[i1][:, i1] * f[None, :]
        out += amp * (a * (1 - f)[:, None] + b * f[:, None])
        total += amp
        amp *= persistence
    return out / total


def normal_map(h, amp_mm, tile_mm_x, tile_mm_y=None):
    tile_mm_y = tile_mm_y or tile_mm_x
    res_y, res_x = h.shape
    hh = h * amp_mm
    dx = (np.roll(hh, -1, 1) - np.roll(hh, 1, 1)) / (2 * tile_mm_x / res_x)
    dy = (np.roll(hh, -1, 0) - np.roll(hh, 1, 0)) / (2 * tile_mm_y / res_y)
    n = np.stack([-dx, dy, np.ones_like(hh)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return ((n * 0.5 + 0.5) * 255 + 0.5).clip(0, 255).astype(np.uint8)


def blur(a, k):
    for ax in (0, 1):
        acc = np.zeros_like(a)
        for d in range(-k, k + 1):
            acc += np.roll(a, d, ax)
        a = acc / (2 * k + 1)
    return a


def save_rgb(a, path):
    Image.fromarray(a if a.dtype == np.uint8 else (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB" if a.ndim == 3 else "L").save(path)


def nonskid():
    tile = 100.0
    pitch = 2.5
    n = int(round(tile / pitch))              # 40 bumps across the tile, so it wraps
    y, x = np.meshgrid((np.arange(RES) + 0.5) / RES, (np.arange(RES) + 0.5) / RES, indexing="ij")
    u = (x + y) * n
    v = (x - y) * n
    fu, fv = u - np.floor(u), v - np.floor(v)
    pyr = np.minimum(1 - np.abs(2 * fu - 1), 1 - np.abs(2 * fv - 1))     # 0 at the grooves, 1 at a bump's top
    h = np.clip(pyr, 0, 1) ** 0.7
    h = np.minimum(h, 0.82) / 0.82                                        # flattened tops (moulded, then worn)
    scatter = periodic_noise(RES, 64, 3, 0.5, 1)
    h = h * (0.9 + 0.1 * scatter) + 0.05 * periodic_noise(RES, 256, 2, 0.5, 2)
    h = np.clip(h, 0, 1)
    cav = np.clip(1 - (1 - h) ** 1.5 * 1.2, 0, 1)
    polish = np.clip((h - 0.8) / 0.2, 0, 1)
    save_rgb(normal_map(h, 0.35, tile), os.path.join(OUT, "T_Detail_NonSkid_N.png"))
    save_rgb(np.stack([cav, polish, h], -1), os.path.join(OUT, "T_Detail_NonSkid_M.png"))
    return tile


def gelcoat():
    tile = 250.0
    peel = periodic_noise(RES, 96, 3, 0.45, 3)
    peel = blur(peel, 1)
    scratches = np.zeros((RES, RES))
    for _ in range(260):
        # short straight scratches and buffing arcs, wrapped
        x0, y0 = RNG.random(2) * RES
        ang = RNG.random() * math.pi
        length = RNG.uniform(10, 120)
        curv = RNG.uniform(-0.01, 0.01)
        steps = int(length * 2)
        for s in range(steps):
            t = s / 2
            a = ang + curv * t
            xi = int(x0 + math.cos(a) * t) % RES
            yi = int(y0 + math.sin(a) * t) % RES
            scratches[yi, xi] = max(scratches[yi, xi], RNG.uniform(0.3, 1.0))
    scratches = np.clip(blur(scratches, 0) * 1.0, 0, 1)
    h = peel - 0.25 * scratches
    rough = np.clip(0.5 + 0.5 * (periodic_noise(RES, 8, 3, 0.5, 4) - 0.5) + 0.4 * scratches, 0, 1)
    save_rgb(normal_map(h, 0.04, tile), os.path.join(OUT, "T_Detail_Gelcoat_N.png"))
    save_rgb(np.stack([scratches, rough, np.zeros_like(h)], -1), os.path.join(OUT, "T_Detail_Gelcoat_M.png"))
    return tile


def teak():
    tl, ta = 300.0, 150.0                       # along the grain (x), across it (y)
    resx, resy = RES, RES // 2
    y, x = np.meshgrid((np.arange(resy) + 0.5) / resy, (np.arange(resx) + 0.5) / resx, indexing="ij")
    # growth rings cut on the flat: lines across the board that wander, with a little figure
    wander = 0.012 * np.sin(2 * np.pi * (2 * x + 0.3)) + 0.008 * np.sin(2 * np.pi * (5 * x + 2 * y)) \
        + 0.05 * (periodic_noise(max(resx, resy), 6, 3, 0.5, 5)[::2, :] - 0.5)
    rings = (y + wander) * 26                  # ~5.8 mm between rings
    f = rings - np.floor(rings)
    late = np.clip(1 - np.abs(f - 0.15) / 0.12, 0, 1) ** 0.6             # hard latewood band
    early = 1 - late
    erosion = early * 0.75                                                 # weathering wears the early wood down
    fibre = periodic_noise(max(resx, resy), 128, 2, 0.5, 6)[::2, :]
    h = 1 - erosion + 0.08 * fibre
    # checks: thin cracks along the grain
    checks = np.zeros((resy, resx))
    for _ in range(18):
        cy = RNG.random() * resy
        cx = RNG.random() * resx
        ln = RNG.uniform(0.1, 0.45) * resx
        for s in range(int(ln)):
            xi = int(cx + s) % resx
            yi = int(cy + 2.5 * math.sin(s / 40.0)) % resy
            w = 1 - abs(2 * s / ln - 1)
            checks[yi, xi] = max(checks[yi, xi], w)
    checks = np.clip(blur(checks, 1) * 3, 0, 1)
    h = h - 0.9 * checks
    lum = np.clip(0.55 + 0.35 * late - 0.25 * checks + 0.1 * (fibre - 0.5), 0, 1)
    save_rgb(normal_map(h, 0.6, tl, ta), os.path.join(OUT, "T_Detail_TeakWeathered_N.png"))
    save_rgb(np.stack([lum, checks, np.clip(h, 0, 1)], -1), os.path.join(OUT, "T_Detail_TeakWeathered_M.png"))
    return tl, ta


def canvas():
    tile = 50.0
    n = 60
    y, x = np.meshgrid((np.arange(RES) + 0.5) / RES, (np.arange(RES) + 0.5) / RES, indexing="ij")
    wx, wy = x * n, y * n
    ix, iy = np.floor(wx).astype(int), np.floor(wy).astype(int)
    fx, fy = wx - ix, wy - iy
    warp_top = ((ix + iy) % 2) == 0
    hx = np.sin(np.pi * fy) ** 0.5 * (0.6 + 0.4 * np.sin(np.pi * fx))
    hy = np.sin(np.pi * fx) ** 0.5 * (0.6 + 0.4 * np.sin(np.pi * fy))
    h = np.where(warp_top, np.maximum(hx, 0.6 * hy), np.maximum(hy, 0.6 * hx))
    save_rgb(normal_map(h, 0.15, tile), os.path.join(OUT, "T_Detail_Canvas_N.png"))
    return tile


meta = {
    "NonSkid": {"tile_m": [nonskid() / 1000] * 2, "normal_strength": 1.0, "fade_m": [2.0, 6.0]},
    "Gelcoat": {"tile_m": [gelcoat() / 1000] * 2, "normal_strength": 1.0, "fade_m": [1.5, 4.0]},
}
tl, ta = teak()
meta["TeakWeathered"] = {"tile_m": [tl / 1000, ta / 1000], "normal_strength": 1.0, "fade_m": [2.0, 6.0]}
meta["Canvas"] = {"tile_m": [canvas() / 1000] * 2, "normal_strength": 0.8, "fade_m": [1.0, 3.0]}
meta["note"] = ("Tile by UV0 x (metres per UV unit, materials.json detail_uv_scale) / tile_m; mask by the baked detail map "
                "T_<Boat>_<Group>_X (R non-skid, G teak, B smooth gelcoat); fade the normal between fade_m[0] and fade_m[1].")
json.dump(meta, open(os.path.join(OUT, "detail_textures.json"), "w"), indent=1)
print("wrote", sorted(os.listdir(OUT)))
