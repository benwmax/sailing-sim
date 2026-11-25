"""The moth's own close-up detail maps (docs/moth-10), tileable, built from numpy (no photos, nothing to licence).

    python3 -I Tools/shipkit/moth/textures.py [out dir] [--res N] [--check]

Her other surfaces reuse the boats' shared detail library (Inputs/boat-detail: Gelcoat for the hull's paint, NonSkid
for the deck's patches, Metal for the anodised fittings, Braid for her Dyneema lines and shrouds, Rubber for the grip),
so only what the library has nothing like is made here (textures_moth.json "maps"):

  T_Moth_CarbonTwill_N/_M   16.24 mm, 1024 px: 3K carbon in a 2x2 twill under clear coat, the look of every tube, spar and the
                            wand. Eight tows each way, 2.03 mm apart (12.5 to the inch); a tow floats over two and under
                            two, each step offset by one, so the diagonal runs at 45 degrees. A tow's filaments run along
                            it: under a clear coat that is what you see, the tows lit or dark by which way they run.
                            M: R the tow's direction (0 along x, 1 along y: the material turns its highlight by it),
                            G roughness variation (resin-rich valleys smoother), B height
  T_Moth_WingMesh_N/_M      15 mm, 512 px: the wings' open mesh, PVC-coated polyester strands 1.0 mm wide on a 2.5 mm pitch in
                            a plain weave (a third open): light through the gaps.
                            M: R coverage (1 on a strand, 0 in a gap: the material's opacity mask), G roughness,
                            B height
  T_Moth_Scrim_N/_M         50 mm, 512 px: the sail's laminate: clear film over a scrim of polyester threads, diagonals both
                            ways crossing the length every 25 mm (17.7 mm apart across: whole repeats in the tile) and
                            a thread along the length 12.5 mm apart, with the film's faint ripple.
                            M: R the threads (where the sail is less clear), G the film's haze, B height

Every map is periodic (whole numbers of repeats in the tile), so it tiles with no seam; --check measures the wrapped
edge's gradient against the interior's, the pattern's pitch on the map against the card, the pixels a millimetre against
the loop's 4 and the block-compressed size against the budget (the texture loop's tiling, size and budget checks,
docs/texture-loop), and prints them as JSON; check.json keeps them. Normals are OpenGL (+Y up), as the boat library's.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image

ARGS = sys.argv[1:]
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = ARGS[0] if ARGS and not ARGS[0].startswith("--") else os.path.join(REPO, "Inputs", "moth-detail")
RES_ARG = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else None      # overrides every card's px
CARDS = json.load(open(os.path.join(HERE, "textures_moth.json")))
MAPS = CARDS["maps"]["own"]


def spectral_noise(shape, lo_mm, hi_mm, tile_mm, seed, aniso=(1.0, 1.0)):
    """Periodic noise whose features lie between lo_mm and hi_mm across, unit variance (as jclass/textures.py)."""
    rng = np.random.default_rng(seed)
    h, w = shape
    fy = np.fft.fftfreq(h, d=tile_mm[1] / h)[:, None] * aniso[1]
    fx = np.fft.fftfreq(w, d=tile_mm[0] / w)[None, :] * aniso[0]
    f = np.maximum(np.hypot(fx, fy), 1e-9)
    f0 = 1.0 / (2.0 * math.sqrt(lo_mm * hi_mm))
    band = np.exp(-0.5 * (np.log(f / f0) / (math.log(hi_mm / lo_mm) / 3.0)) ** 2) / f
    band[0, 0] = 0.0
    z = np.fft.ifft2(np.fft.fft2(rng.standard_normal(shape)) * band).real
    return (z - z.mean()) / (z.std() + 1e-12)


def peak_mm(a, tile_mm, axis):
    """The wavelength in millimetres of the strongest repeat along x (axis 1) or y (axis 0): the power spectrum of each
    row (or column) on its own, averaged (a mean profile would cancel a pattern that shifts from row to row, like the
    twill's diagonal)."""
    a = a.astype(float)
    if axis == 0:
        a = a.T
    p = (np.abs(np.fft.rfft(a - a.mean(axis=1, keepdims=True), axis=1)) ** 2).mean(0)
    p[0] = 0.0
    return round((tile_mm[0] if axis == 1 else tile_mm[1]) / int(np.argmax(p)), 4)


def normal_map(hmm, tile_mm):
    """Height in millimetres over a tile of tile_mm (x, y) to an OpenGL normal map (uint8 RGB)."""
    h, w = hmm.shape
    dx = (np.roll(hmm, -1, 1) - np.roll(hmm, 1, 1)) / (2 * tile_mm[0] / w)
    dy = (np.roll(hmm, -1, 0) - np.roll(hmm, 1, 0)) / (2 * tile_mm[1] / h)
    n = np.stack([-dx, dy, np.ones_like(hmm)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return ((n * 0.5 + 0.5) * 255 + 0.5).clip(0, 255).astype(np.uint8)


def unit(a):
    lo, hi = np.percentile(a, 0.5), np.percentile(a, 99.5)
    return np.clip((a - lo) / (hi - lo + 1e-12), 0, 1)


def save(a, path):
    a = a if a.dtype == np.uint8 else (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(a, "RGB" if a.ndim == 3 else "L").save(path, optimize=True)


def grid(shape):
    h, w = shape
    return np.meshgrid((np.arange(w) + 0.5) / w, (np.arange(h) + 0.5) / h)


def weave(shape, n, over, width):
    """A woven cloth of n threads each way across the tile: (height of the top thread in units of its half-thickness,
    which way it runs: 0 along x, 1 along y, coverage). over(i, j) says whether thread i along x lies over thread j
    along y at their crossing; width is a thread's width as a share of its pitch."""
    x, y = grid(shape)
    u, v = x * n, y * n                          # in pitches
    i, j = np.floor(v).astype(int) % n, np.floor(u).astype(int) % n      # i: the x-running thread (a row), j: the column
    fu, fv = u - np.floor(u), v - np.floor(v)    # where in the cell
    ax = np.clip(1 - ((fv - 0.5) / (width / 2)) ** 2, 0, None)          # across an x-running thread (it lies along x)
    ay = np.clip(1 - ((fu - 0.5) / (width / 2)) ** 2, 0, None)
    top_x = over(i, j)
    # a thread rises over its crossing and dips at the next: the next cell along its length decides
    hx = np.sqrt(ax) * np.where(top_x, 1.0, 0.0)
    hy = np.sqrt(ay) * np.where(top_x, 0.0, 1.0)
    # where the top thread doesn't cover (its edges), the other shows
    hx_under = np.sqrt(ax) * np.where(top_x, 0.0, 0.55)
    hy_under = np.sqrt(ay) * np.where(top_x, 0.55, 0.0)
    hxx, hyy = np.maximum(hx, hx_under), np.maximum(hy, hy_under)
    h = np.maximum(hxx, hyy)
    direction = np.where(hyy > hxx, 1.0, 0.0)
    cover = np.clip(np.maximum(ax, ay) * 4, 0, 1)
    return h, direction, cover


def res_of(card):
    return RES_ARG or card["px"]


def carbon_twill(card):
    tile, n = card["tile_mm"], card["tows"]
    shape = (res_of(card), res_of(card))
    h, d, _ = weave(shape, n, lambda i, j: ((i + j) % 4) < 2, 0.98)
    fil_x = spectral_noise(shape, 0.02, 0.08, tile, 11, aniso=(40.0, 1.0))      # filaments along x-running tows
    fil_y = spectral_noise(shape, 0.02, 0.08, tile, 12, aniso=(1.0, 40.0))
    fil = np.where(d > 0.5, fil_y, fil_x)
    hmm = 0.05 * h + 0.004 * fil                                               # mm under the coat
    rough = unit(0.7 * h + 0.3 * fil)                                          # resin-rich valleys smoother
    # the direction map repeats with the twill (four tows) along each axis
    sizes = {"twill_repeat_x": (peak_mm(d, tile, 1), card["twill_repeat_mm"]),
             "twill_repeat_y": (peak_mm(d, tile, 0), card["twill_repeat_mm"]),
             "tow_pitch": (round(tile[0] / n, 4), card["tow_pitch_mm"])}
    return hmm, np.stack([d, rough, unit(hmm)], -1), tile, sizes


def wing_mesh(card):
    tile, n = card["tile_mm"], card["strands"]
    shape = (res_of(card), res_of(card))
    h, _, cover = weave(shape, n, lambda i, j: ((i + j) % 2) == 0, card["strand_mm"] / card["pitch_mm"])
    grain = spectral_noise(shape, 0.05, 0.2, tile, 21)
    hmm = 0.35 * h + 0.01 * grain
    sizes = {"pitch_mm": (peak_mm(cover, tile, 1), card["pitch_mm"])}
    return hmm, np.stack([cover, unit(0.5 + 0.2 * grain), unit(hmm)], -1), tile, sizes


def scrim(card):
    tile = card["tile_mm"]
    shape = (res_of(card), res_of(card))
    x, y = grid(shape)
    X, Y = x * tile[0], y * tile[1]
    t = card["thread_mm"] / 2

    def lines(coord, pitch):
        dd = (coord + pitch / 2) % pitch - pitch / 2
        return np.clip(1 - (dd / t) ** 2, 0, 1)
    dg = card["diagonal_mm"]                  # 45 degree lines crossing the length every 25 mm: x + y = k dg, periodic
    th = np.maximum.reduce([lines(X + Y, dg), lines(X - Y, dg), lines(Y, card["along_mm"])])
    ripple = spectral_noise(shape, 2.0, 8.0, tile, 31, aniso=(1.0, 3.0))
    hmm = 0.03 * th + 0.01 * ripple
    haze = unit(0.5 + 0.5 * spectral_noise(shape, 3.0, 12.0, tile, 32))
    sizes = {"along_mm": (peak_mm(lines(Y, card["along_mm"]), tile, 0), card["along_mm"]),
             "diagonal_mm": (peak_mm(lines(X + Y, dg), tile, 1), card["diagonal_mm"])}
    return hmm, np.stack([th, haze, unit(hmm)], -1), tile, sizes


BUILD = {"CarbonTwill": carbon_twill, "WingMesh": wing_mesh, "Scrim": scrim}


def seam(a):
    """The wrapped edge's mean gradient across it over the roughest interior line's (columns and rows alike): at most
    about 1 when the tile wraps cleanly. (Against the interior's mean, a map whose weave or thread edge lands on the tile's
    edge would fail though it wraps exactly.)"""
    a = a.astype(float)
    if a.ndim == 3:
        a = a.mean(-1)
    worst = 0.0
    for ax in (0, 1):
        g = np.abs(a - np.roll(a, 1, axis=ax)).mean(axis=1 - ax)        # g[k]: across the line between k-1 and k
        worst = max(worst, g[0] / (g[1:].max() + 1e-12))
    return round(float(worst), 3)


def mb(px):
    """BC5 normal (1 byte a pixel) and BC1 mask (half a byte), with mips (4/3)."""
    return px * px * 1.5 * 4 / 3 / 2 ** 20


def main():
    os.makedirs(OUT, exist_ok=True)
    report = {}
    total = 0.0
    for name, fn in BUILD.items():
        card = MAPS[name]
        hmm, m, tile, sizes = fn(card)
        n = normal_map(hmm * card.get("normal_strength", 1.0), tile)
        save(n, os.path.join(OUT, f"T_Moth_{name}_N.png"))
        save(m, os.path.join(OUT, f"T_Moth_{name}_M.png"))
        px = res_of(card)
        total += mb(px)
        sz = {k: {"model": a, "card": b, "off": round(a / b - 1, 3)} for k, (a, b) in sizes.items()}
        ppm = round(px / tile[0], 2)
        report[name] = {"tile_mm": tile, "px": px, "px_per_mm": ppm, "mb": round(mb(px), 2), "seam_N": seam(n),
                        "seam_M": seam(m), "sizes": sz,
                        "pass": bool(ppm >= CARDS["closest_px_per_mm"] and seam(n) <= 1.0 and seam(m) <= 1.0
                                     and all(abs(v["off"]) <= 0.1 for v in sz.values()))}
    cap = CARDS["budget"]["high_mb"]
    report["budget"] = {"high_mb": round(total, 2), "cap_high_mb": cap, "medium_mb": 0.0, "pass": total <= cap}
    if "--check" in ARGS:
        print(json.dumps(report, indent=1))
    json.dump(report, open(os.path.join(OUT, "check.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
