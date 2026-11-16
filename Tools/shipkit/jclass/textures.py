"""Bluebonnet's own close-up detail maps (docs/jclass-11), tileable, built from numpy (no photos, nothing to licence).

    python3 -I Tools/shipkit/jclass/textures.py [out dir] [--res 1024] [--check]

Her other surfaces reuse the boats' shared detail library (Inputs/boat-detail, Tools/boats/make_detail_textures.py:
Gelcoat's orange peel for the enamels, TeakWeathered for the laid deck and the pine soles, WoodVarnish for the
brightwork and the panelling, Metal for bare duralumin and galvanised wire, Canvas for the bags and the cots), so only
what the library has nothing like is made here. Each tiles at its real size (textures_bluebonnet.json "maps"):

  T_JClass_CastBronze_N/_M  100 mm: sand-cast bronze (winches, fittings, portlights, the binnacle): a fine grain of
                            sand pits 0.2-0.6 mm across, a few casting pores to 1.2 mm, and soft filing marks.
                            M: R cavity (0 in a pit: where verdigris and polish sit), G roughness variation, B height
  T_JClass_Cotton_N/_M      40 mm: the sails' cotton duck, a plain weave of 26 warp and 20 weft threads to the
                            centimetre (Egyptian sail cotton of the 1930s) whose yarns thicken and thin along their
                            length (slubs).
                            M: R the weave's gaps (where dirt and mildew sit), G the yarn's tone, B height
  T_JClass_Manila_N/_M      60 x 30 mm, along a strand by across it: manila's long hard fibres, 0.1-0.4 mm wide and
                            a few centimetres long, light and dark, a few hairs standing off.
                            M: R the fibre's tone, G hairs, B height

Every map is made periodic (FFT-filtered noise and patterns with a whole number of repeats in the tile), so it tiles
with no seam; --check measures it (the wrapped edge's gradient against the interior's) and the pixels per millimetre,
the texture loop's tiling and size checks (docs/texture-loop), and prints them as JSON. Normals are OpenGL (+Y up), as
the boat library's (Unreal's import flips green).
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
OUT = ARGS[0] if ARGS and not ARGS[0].startswith("--") else os.path.join(REPO, "Inputs", "jclass-detail")
RES = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else 1024
CARDS = json.load(open(os.path.join(HERE, "textures_bluebonnet.json")))
SURF = {k: v["pattern_mm"] for k, v in CARDS["surfaces"].items()}


def spectral_noise(shape, lo_mm, hi_mm, tile_mm, seed, aniso=(1.0, 1.0)):
    """Periodic noise whose features (a bump, half a wavelength) lie between lo_mm and hi_mm across, unit variance: a
    log-normal band about the wavelength 2 sqrt(lo hi), its amplitude divided by the frequency so that the power per
    octave, not per mode, follows the band (a 2-D spectrum has more modes the finer it goes). aniso lengthens the
    features (x, y): (8, 1) makes streaks along x eight times longer than they are wide."""
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


def feature_mm(a, tile_mm, axis=None):
    """The power-weighted median feature size (half a wavelength) in millimetres: over all directions, or across
    the given axis (0: along y, 1: along x) only."""
    a = a.astype(float) - a.mean()
    h, w = a.shape
    p = np.abs(np.fft.fft2(a)) ** 2
    fy = np.fft.fftfreq(h, d=tile_mm[1] / h)[:, None]
    fx = np.fft.fftfreq(w, d=tile_mm[0] / w)[None, :]
    f = np.abs(fy) + 0 * fx if axis == 0 else (np.abs(fx) + 0 * fy if axis == 1 else np.hypot(fx, fy))
    f, p = f.ravel(), p.ravel()
    keep = f > 0
    f, p = f[keep], p[keep]
    o = np.argsort(f)
    c = np.cumsum(p[o])
    return round(float(0.5 / f[o][np.searchsorted(c, 0.5 * c[-1])]), 3)


def peak_mm(a, tile_mm, axis):
    """The wavelength in millimetres of the strongest repeat along x (axis 1) or y (axis 0): a weave's thread pitch."""
    prof = a.astype(float).mean(axis=0 if axis == 1 else 1)
    p = np.abs(np.fft.rfft(prof - prof.mean())) ** 2
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


def cast_bronze(card):
    tile = card["tile_mm"]
    shape = (RES, RES)
    rng = np.random.default_rng(37)
    sand = spectral_noise(shape, 0.2, 0.6, tile, 1)
    h = 0.012 * sand                                                   # mm: the sand's grain
    # pores: round pits, a few to the square centimetre, 0.3-1.2 mm across
    x, y = grid(shape)
    pit = np.zeros(shape)
    n = int(card["pores_per_cm2"] * tile[0] * tile[1] / 100.0)
    for _ in range(n):
        cx, cy = rng.random(2)
        r = rng.uniform(0.15, 0.6) / tile[0]                           # radius as a share of the tile
        d = np.hypot((x - cx + 0.5) % 1.0 - 0.5, (y - cy + 0.5) % 1.0 - 0.5) / r
        pit = np.maximum(pit, np.clip(1.0 - d * d, 0, 1) * rng.uniform(0.5, 1.0))
    h -= 0.06 * pit
    # filing marks: long faint scratches, two directions, where the castings were dressed
    files = (spectral_noise(shape, 0.05, 0.4, tile, 2, aniso=(30.0, 1.0))
             + 0.6 * spectral_noise(shape, 0.05, 0.4, tile, 3, aniso=(1.0, 24.0)))
    h += 0.003 * files
    rough = unit(0.6 * sand + 0.4 * files)
    cav = np.clip(1.0 - 1.4 * pit - 0.25 * np.clip(-sand, 0, None), 0, 1)
    sizes = {"sand_grain": (feature_mm(sand, tile), SURF["bronze"]["sand_grain"])}
    return h, np.stack([cav, rough, unit(h)], -1), tile, sizes


def cotton(card):
    tile = card["tile_mm"]
    nw, nf = card["warp_per_cm"] * tile[0] / 10.0, card["weft_per_cm"] * tile[1] / 10.0
    nw, nf = int(round(nw)), int(round(nf))
    shape = (RES, RES)
    x, y = grid(shape)
    wx, wy = x * nw, y * nf                     # warp threads run along y (one per column band), weft along x
    ix, iy = np.floor(wx).astype(int), np.floor(wy).astype(int)
    fx, fy = wx - ix, wy - iy
    # slubs: each yarn thickens and thins along its length (periodic in the tile, a different phase per yarn)
    rng = np.random.default_rng(11)
    sl_w = np.zeros(shape)
    sl_f = np.zeros(shape)
    pw = rng.random((nw, 3)) * 2 * math.pi
    pf = rng.random((nf, 3)) * 2 * math.pi
    for k, m in enumerate((2, 5, 9)):
        sl_w += np.cos(2 * math.pi * m * y + pw[ix % nw, k]) / (k + 1)
        sl_f += np.cos(2 * math.pi * m * x + pf[iy % nf, k]) / (k + 1)
    sl_w, sl_f = 1.0 + 0.18 * sl_w / 1.8, 1.0 + 0.18 * sl_f / 1.8
    # a yarn's round section, its width set by the slub; plain weave: warp over where (ix + iy) is even
    warp = np.clip(1.0 - ((fx - 0.5) / (0.47 * sl_w)) ** 2, 0, 1) ** 0.5
    weft = np.clip(1.0 - ((fy - 0.5) / (0.47 * sl_f)) ** 2, 0, 1) ** 0.5
    over = ((ix + iy) % 2) == 0
    crimp_w = np.sin(math.pi * fy)              # the warp bows up over the weft it crosses, down under the next
    crimp_f = np.sin(math.pi * fx)
    hw = warp * (0.55 + 0.45 * np.where(over, crimp_w, 1 - crimp_w))
    hf = weft * (0.55 + 0.45 * np.where(over, 1 - crimp_f, crimp_f))
    h = np.maximum(hw, hf)
    fuzz = spectral_noise(shape, 0.03, 0.12, tile, 4)
    hmm = 0.09 * h + 0.004 * fuzz
    # the yarn's tone: thicker is lighter (the slubs), with a fine fleck of the fibres' own (a tone in blotches
    # of a centimetre would repeat visibly every 4 cm)
    tone = unit(np.where(hw >= hf, sl_w, sl_f) + 0.15 * spectral_noise(shape, 0.5, 2.0, tile, 5))
    gaps = 1.0 - np.clip(h * 1.6, 0, 1)         # 1 between the yarns, where dirt and mildew sit
    sizes = {"warp_pitch": (peak_mm(hmm, tile, 1), SURF["cotton"]["warp_pitch"]),
             "weft_pitch": (peak_mm(hmm, tile, 0), SURF["cotton"]["weft_pitch"]),
             "slub": (feature_mm(sl_w, tile, 0), SURF["cotton"]["slub"])}
    return hmm, np.stack([gaps, tone, unit(hmm)], -1), tile, sizes


def manila(card):
    tile = card["tile_mm"]                      # x along the strand, y across it
    shape = (RES // 2, RES)
    rng = np.random.default_rng(23)
    x, y = grid(shape)
    # fibres: long streaks along x, 0.1-0.4 mm wide, each a run of a few cm with its own tone
    fib = spectral_noise(shape, 0.1, 0.4, tile, 6, aniso=(60.0, 1.0))
    tone = spectral_noise(shape, 0.15, 0.6, tile, 7, aniso=(40.0, 1.0))
    h = 0.08 * fib + 0.02 * spectral_noise(shape, 1.0, 4.0, tile, 8)
    # hairs: a few broken fibre ends standing off, short bright curved strokes at a slant
    hair = np.zeros(shape)
    n = int(card["hairs_per_cm2"] * tile[0] * tile[1] / 100.0)
    H, W = shape
    for _ in range(n):
        cx, cy = rng.random() * W, rng.random() * H
        ln = rng.uniform(2.0, 6.0) / tile[0] * W
        ang = rng.uniform(-0.6, 0.6)
        bend = rng.uniform(-0.004, 0.004)
        for s in np.linspace(0, 1, int(ln * 1.5) + 2):
            px = int(cx + s * ln * math.cos(ang)) % W
            py = int(cy + s * ln * math.sin(ang) + bend * (s * ln) ** 2) % H
            hair[py, px] = max(hair[py, px], 1.0 - 0.6 * s)
    k = np.array([0.25, 0.5, 0.25])
    for ax in (0, 1):
        hair = sum(w * np.roll(hair, d, ax) for d, w in zip((-1, 0, 1), k))
    hair = np.clip(hair * 2.5, 0, 1)
    h += 0.05 * hair
    sizes = {"fibre_width": (feature_mm(fib, tile, 0), SURF["manila"]["fibre_width"])}
    return h, np.stack([unit(tone + 0.5 * fib), hair, unit(h)], -1), tile, sizes


MAKERS = {"CastBronze": cast_bronze, "Cotton": cotton, "Manila": manila}


def tiling(a):
    """The wrapped edges' step against the tile's own steps: the mean absolute difference across the wrap (last column
    to first, last row to first) over the largest of the same mean taken between every other pair of neighbouring
    columns (rows). A periodic tile steps across its wrap like anywhere else, so 1 or under passes; a seam stands out
    above it (a regular weave's steps vary with its phase, so a typical step is no yardstick)."""
    a = a.astype(float)
    if a.ndim == 3:
        a = a.mean(-1)
    worst = 0.0
    for b in (a, a.T):
        steps = np.abs(np.diff(b, axis=1)).mean(0)
        wrap = np.abs(b[:, 0] - b[:, -1]).mean()
        worst = max(worst, wrap / (steps.max() + 1e-12))
    return round(float(worst), 3)


def repeat_share(a):
    """How much a 3x3 tiling would show the tile itself repeating: the share of the map's variance at wavelengths
    longer than a quarter of the tile (big blotches recur visibly; the weave's own fine regularity does not count).
    The loop's 'no strong repeat' passes under 0.2."""
    a = a.astype(float)
    if a.ndim == 3:
        a = a.mean(-1)
    p = np.abs(np.fft.fft2(a - a.mean())) ** 2
    h, w = a.shape
    fy = np.abs(np.fft.fftfreq(h) * h)[:, None]
    fx = np.abs(np.fft.fftfreq(w) * w)[None, :]
    low = (np.maximum(fx, fy) <= 4) & ((fx + fy) > 0)
    return round(float(p[low].sum() / (p.sum() + 1e-12)), 3)


def size_report(sizes):
    """The loop's size check: each measured pattern inside the card's range (lo, hi) mm, or within 10% of a single
    asked size (a weave's pitch)."""
    out = {}
    for k, (got, asked) in sizes.items():
        ok = (asked[0] <= got <= asked[1]) if isinstance(asked, list) else abs(got / asked - 1.0) <= 0.1
        out[k] = {"mm": got, "asked_mm": asked, "pass": bool(ok)}
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    meta = {"_about": "Bluebonnet's own detail maps (docs/jclass-11, Tools/shipkit/jclass/textures.py); each tiles at "
                      "tile_m (x, y) metres; normals OpenGL. Medium draws none of them (textures_bluebonnet.json "
                      "budget)."}
    for name, card in CARDS["maps"]["own"].items():
        hmm, m, tile, sizes = MAKERS[name](card)
        n = normal_map(hmm, tile)
        save(n, os.path.join(OUT, f"T_JClass_{name}_N.png"))
        save(m, os.path.join(OUT, f"T_JClass_{name}_M.png"))
        h, w = hmm.shape
        meta[name] = {"tile_m": [tile[0] / 1000.0, tile[1] / 1000.0], "px": [w, h],
                      "px_per_mm": round(min(w / tile[0], h / tile[1]), 2),
                      "normal_strength": card["normal_strength"], "fade_m": card["fade_m"],
                      "tiling_N": tiling(n), "tiling_M": tiling(m), "repeat_N": repeat_share(n),
                      "repeat_M": repeat_share(m), "size": size_report(sizes)}
        print(name, meta[name])
    json.dump(meta, open(os.path.join(OUT, "jclass_detail.json"), "w"), indent=1)
    if "--check" in ARGS:
        print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
