"""Storm water step 2 (docs/storm-water/foam-texture/): bakes T_FoamLace, the whitecaps' foam texture, from our own
procedural noise (no photographs): a tileable 1024^2 RGB, linear, written to Artifacts/foam/T_FoamLace.png and imported
by scripts/import_foam_texture.py.

  R  lace:    fresh foam, a crest's bubbly white. Two octaves of Worley cell walls (F2 - F1: the films between bubbles)
              broken by holes from fractal noise. Sampled at the fine scale (3.2 m a tile).
  G  streaks: ageing foam drawn out by the wind. Ridged noise filtered 9:1 along U (the wind's axis in the shader), in
              patches, so the residue thins into strings along the wind. The coarse scale (12.8 m).
  B  cells:   the foam's marbling (bright bubble mass, thin dark veins of ridged filtered noise). The fine scale.

Each channel is histogram-matched to the sine pattern it replaces in M_WaterV4 (lace, streak x lace, cells), so the
means the shader's tone and cover factors were set against (a crest's whiteness 0.92, the residue's pattern, the cells'
0.6) are unchanged: only where the white sits, and its shape, change. The script prints each channel's mean and standard
deviation; the shader's variance-preserving hex-tile blend uses them (FOAM_STATS in make_materials.py).

Usage: python -I Tools/water/make_foam_texture.py [out_dir]
"""
import math
import os
import sys

import numpy as np
from PIL import Image

N = 1024
SEED = 1288


def periodic_worley(n, cells, rng, stretch=1.0):
    """F1 and F2 distances (in cell units) to jittered points on a cells x cells torus, the domain squeezed by stretch
    along x (cells longer along U)."""
    pts = rng.random((cells, cells, 2))
    y, x = np.mgrid[0:n, 0:n] / n * cells
    cx, cy = np.floor(x).astype(int), np.floor(y).astype(int)
    f1 = np.full((n, n), 1e9)
    f2 = np.full((n, n), 1e9)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ix, iy = (cx + dx) % cells, (cy + dy) % cells
            px = cx + dx + pts[iy, ix, 0]
            py = cy + dy + pts[iy, ix, 1]
            d = np.sqrt(((x - px) / stretch) ** 2 + (y - py) ** 2)
            f2 = np.where(d < f1, f1, np.minimum(f2, d))
            f1 = np.minimum(f1, d)
    return f1, f2


def periodic_value_noise(n, freq, rng, stretch=1.0):
    """Smooth value noise on a freq x freq torus (cosine-interpolated lattice), stretched along x."""
    fx = max(1, int(round(freq / stretch)))
    lat = rng.random((freq, fx))
    y, x = np.mgrid[0:n, 0:n] / n
    u, v = x * fx, y * freq
    x0, y0 = np.floor(u).astype(int), np.floor(v).astype(int)
    tx, ty = u - x0, v - y0
    sx, sy = (1 - np.cos(tx * math.pi)) / 2, (1 - np.cos(ty * math.pi)) / 2
    a = lat[y0 % freq, x0 % fx]
    b = lat[y0 % freq, (x0 + 1) % fx]
    c = lat[(y0 + 1) % freq, x0 % fx]
    d = lat[(y0 + 1) % freq, (x0 + 1) % fx]
    return (a * (1 - sx) + b * sx) * (1 - sy) + (c * (1 - sx) + d * sx) * sy


def filtered_noise(n, wavelength_px, rng, stretch=1.0):
    """White noise low-passed on the torus (FFT) by a Gaussian of the given wavelength across and stretch times it along x:
    smooth, periodic and free of a lattice (value noise's ridges followed its grid). Normalised to 0..1."""
    w = rng.standard_normal((n, n))
    ky = np.fft.fftfreq(n)[:, None]
    kx = np.fft.fftfreq(n)[None, :]
    s = wavelength_px / (2 * math.pi)
    env = np.exp(-0.5 * ((ky * 2 * math.pi * s) ** 2 + (kx * 2 * math.pi * s * stretch) ** 2))
    f = np.real(np.fft.ifft2(np.fft.fft2(w) * env))
    f = (f - f.mean()) / (f.std() + 1e-9)
    return np.clip(0.5 + 0.18 * f, 0, 1)


def fbm(n, base, octaves, rng, stretch=1.0):
    out = np.zeros((n, n))
    amp, total = 1.0, 0.0
    for o in range(octaves):
        out += amp * periodic_value_noise(n, base * 2 ** o, rng, stretch)
        total += amp
        amp *= 0.5
    return out / total


def match(values, target):
    """Rank-maps values onto target's distribution (histogram matching)."""
    order = np.argsort(values, axis=None)
    q = np.sort(target)
    idx = np.linspace(0, len(q) - 1, values.size).astype(int)
    out = np.empty(values.size)
    out[order] = q[idx]
    return out.reshape(values.shape)


def old_patterns(rng, count=400000):
    """The shader's sine patterns at random places (and random wind frames): the distributions to match."""
    p = rng.random((count, 2)) * 400.0
    T = rng.random(count) * 100.0
    x, y = p[:, 0], p[:, 1]
    lace = (0.5 + 0.5 * np.sin(x * 9.1 + np.sin(y * 7.3) * 1.7)) * (0.5 + 0.5 * np.sin(y * 8.3 + np.sin(x * 6.1 + T * 0.2) * 1.9))
    ang = rng.random(count) * 2 * math.pi
    wd = np.stack([np.cos(ang), np.sin(ang)], 1)
    wn = np.stack([-wd[:, 1], wd[:, 0]], 1)
    across = (p * wn).sum(1)
    along = (p * wd).sum(1)
    streak = 0.5 + 0.5 * np.sin(across * 7.0 + np.sin(along * 0.6) * 2.5)
    cells = (0.5 + 0.5 * np.sin(x * 23.7 + np.sin(y * 19.1) * 2.3)) * (0.5 + 0.5 * np.sin(y * 21.3 + np.sin(x * 17.9 + T * 0.6) * 2.7))
    return lace, streak * lace, cells


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Artifacts", "foam")
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.default_rng(SEED)
    lace_t, streak_t, cells_t = old_patterns(rng)

    # R, lace: bubble films at two sizes (about 16 and 6 cm on a 3.2 m tile), open where the fractal noise is low.
    f1a, f2a = periodic_worley(N, 20, rng)
    f1b, f2b = periodic_worley(N, 52, rng)
    films = np.exp(-(f2a - f1a) * 9.0) * 0.6 + np.exp(-(f2b - f1b) * 7.0) * 0.4
    holes = fbm(N, 6, 5, rng)
    lace = films * 0.55 + np.clip((holes - 0.38) * 2.2, 0, 1) * 0.45 + 0.15 * (1 - f1b)
    # G, streaks: ridges drawn out 9:1 along U, thinned in patches.
    ridged = 1.0 - np.abs(2.0 * (0.6 * filtered_noise(N, 36, rng, 9.0) + 0.4 * filtered_noise(N, 12, rng, 9.0)) - 1.0)
    streaks = ridged ** 6 * np.clip(filtered_noise(N, 160, rng, 3.0) * 2.6 - 0.8, 0, 1)
    # B, cells: the foam's marbling: bright bubble mass parted by thin, irregular dark veins (ridges of filtered noise, about
    # 25 and 9 cm apart on the fine 3.2 m tile), in brighter and duller patches. No cells of one size: those read as cobbles.
    veins = (1.0 - np.abs(2.0 * filtered_noise(N, 80, rng) - 1.0)) ** 10 * 0.7 + (1.0 - np.abs(2.0 * filtered_noise(N, 28, rng) - 1.0)) ** 6 * 0.2
    cells = (1.0 - veins) * (0.55 + 0.45 * filtered_noise(N, 240, rng))

    R = match(lace, lace_t)
    G = match(streaks, streak_t)
    B = match(cells, cells_t)
    img = np.stack([R, G, B], -1)
    Image.fromarray(np.clip(np.round(img * 255.0), 0, 255).astype(np.uint8), "RGB").save(os.path.join(out_dir, "T_FoamLace.png"))
    q = np.round(img * 255.0) / 255.0
    for name, ch, t in (("lace", q[..., 0], lace_t), ("streaks", q[..., 1], streak_t), ("cells", q[..., 2], cells_t)):
        print(f"{name}: mean {ch.mean():.4f} sd {ch.std():.4f} (the sine pattern's {t.mean():.4f} / {t.std():.4f})")
    print(f"Wrote {os.path.join(out_dir, 'T_FoamLace.png')}")


if __name__ == "__main__":
    main()
