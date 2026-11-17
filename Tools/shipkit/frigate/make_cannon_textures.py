#!/usr/bin/env python3
"""Cannon fire's textures (docs/cannon-fire/): the smoke puffs' atlas and the flame's, made from seeded noise, for
scripts/import_cannon_fx.py to import into /Game/Materials/CannonFx. numpy and Pillow (Tools/venv); deterministic.

    Tools/venv/bin/python -I Tools/shipkit/frigate/make_cannon_textures.py [out dir, default Artifacts/cannon-fx] [--preview]

T_CannonSmoke.png (1024 x 1024, 4 x 4 puffs of 256, linear RGBA). The quad spans +-2.5 sigma of the puff's Gaussian
(ACannonBattery::UpdateSmokeVisuals), so each tile's density falls off as exp(-r^2 / 2 0.4^2) of the tile's half-width,
broken by billows (cauliflower: the absolute of a fractal noise, domain-warped so the edge is lumpy, not round).
  R  density 0..1 (the billowed Gaussian)
  G  how lit from above: the light's transmittance down through the puff's own density (Beer, the top bright, the
     underside dark), for M_CannonSmoke's self-shadowing
  B  the soft Gaussian alone (old smoke fades toward it: M_CannonSmoke's Fresh)
  A  fine detail (wisps at the edge as it thins)
T_CannonFlame.png (512 x 512, 2 x 2 flames of 256, linear RGBA): each a tongue of flame out of the muzzle along +U (U = 0 at
the muzzle), V across.
  R  the flame's brightness   G  its heat (white core near the muzzle, red at the tip and edges)
  B  burning grains (sparkles in the flame)   A  the round bloom at the mouth
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TILE = 256


def fractal(rng, n, beta, lo=1.0):
    """A field of n x n with a power spectrum ~ k^-beta (fractal clouds), zero mean, unit deviation."""
    white = rng.standard_normal((n, n))
    f = np.fft.rfft2(white)
    ky = np.fft.fftfreq(n)[:, None] * n
    kx = np.fft.rfftfreq(n)[None, :] * n
    k = np.sqrt(kx * kx + ky * ky)
    k[0, 0] = 1.0
    f *= np.where(k < lo, 0.0, k ** (-beta / 2.0))
    out = np.fft.irfft2(f, s=(n, n))
    return (out - out.mean()) / (out.std() + 1e-9)


def bilinear(img, x, y):
    """Sample img (n x n) at pixel coordinates x, y (arrays), wrapping."""
    n = img.shape[0]
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    x0 %= n
    y0 %= n
    x1, y1 = (x0 + 1) % n, (y0 + 1) % n
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x1] * fx * (1 - fy) + img[y1, x0] * (1 - fx) * fy + img[y1, x1] * fx * fy)


def smoke_tile(seed):
    rng = np.random.default_rng(seed)
    n = TILE
    v = (np.arange(n) + 0.5) / n * 2.0 - 1.0           # -1..1 across the quad (+-2.5 sigma)
    X, Y = np.meshgrid(v, -v)                           # Y up (image rows run down)
    # Domain warp: the edge lumpy, a few big lobes.
    wx = fractal(rng, n, 3.6) * 0.16
    wy = fractal(rng, n, 3.6) * 0.16
    Xw, Yw = X + wx, Y + wy
    r2 = Xw * Xw + Yw * Yw
    soft = np.exp(-(X * X + Y * Y) / (2 * 0.4 ** 2))
    gauss = np.exp(-r2 / (2 * 0.4 ** 2))
    # Billows: cauliflower heads, the absolute of a fractal turned over (bright rounded tops, dark creases).
    # (Two scales: a few big heads, and smaller ones on them; no grain finer than a twentieth of the puff.)
    b = 0.75 * fractal(rng, n, 4.2, lo=2.0) + 0.35 * fractal(rng, n, 3.4, lo=5.0)
    billow = 1.0 - np.abs(b) / 2.2
    billow = np.clip(billow, 0.0, 1.0) ** 1.3
    dens = gauss * (0.5 + 0.7 * billow)
    dens = np.clip(dens / dens.max(), 0.0, 1.0)
    # Self-shadow: light from above, the transmittance down to each pixel through the density over it (rows above).
    tau = np.cumsum(dens, axis=0) / n * 2.0 * 3.0       # optical depth from the top edge
    lit = np.exp(-tau)
    lit = (lit - lit.min()) / (lit.max() - lit.min() + 1e-9)
    # Wisps: fine fractal, strongest at the edge.
    fine = fractal(rng, n, 1.8, lo=6.0)
    wisp = np.clip(0.5 + 0.25 * fine, 0.0, 1.0)
    return dens, lit, soft / soft.max(), wisp


def flame_tile(seed):
    rng = np.random.default_rng(seed)
    n = TILE
    u = (np.arange(n) + 0.5) / n                        # 0 at the muzzle .. 1 at the tip
    v = (np.arange(n) + 0.5) / n * 2.0 - 1.0
    U, V = np.meshgrid(u, v)
    turb = fractal(rng, n, 3.6, lo=2.0)
    # The tongue: the bore's width at the mouth, swelling to its widest a third of the way out (the gas expanding), its
    # edge ragged; it narrows to a ragged, forked tip.
    width = 0.08 + 0.3 * np.sin(np.pi * np.clip(U, 0, 1) ** 0.65) * (1.0 - 0.45 * U)
    Vw = V + 0.1 * turb * U
    across = np.exp(-(Vw / np.maximum(width, 1e-3)) ** 2 * 2.5)
    along = np.clip(1.0 - U * (1.0 + 0.25 * turb), 0.0, 1.0) ** 0.9 * np.clip(U / 0.03, 0.0, 1.0)
    bright = across * along * np.clip(0.9 + 0.15 * turb, 0.55, 1.3)   # licks, not holes
    bright = np.clip(bright / bright.max(), 0.0, 1.0)
    heat = np.clip(across ** 3 * np.clip(1.0 - U / 0.45, 0.0, 1.0) ** 1.2 * 1.5, 0.0, 1.0)
    # Burning grains: a scatter of bright points in the flame's body.
    grains = np.zeros((n, n))
    for _ in range(140):
        cx, cy = rng.uniform(0.1, 0.95) * n, rng.normal(0.0, 0.35) * n / 2 + n / 2
        rr = rng.uniform(0.6, 1.6)
        yy, xx = np.ogrid[:n, :n]
        grains += np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * rr * rr))
    grains = np.clip(grains, 0.0, 1.0) * across
    R = np.sqrt((U * 2.2) ** 2 + V ** 2)
    bloom = np.exp(-R ** 2 * 3.0)
    return bright, heat, grains, bloom / bloom.max()


def to8(a):
    return (np.clip(a, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def main(argv):
    out = next((a for a in argv if not a.startswith("--")), os.path.join(REPO, "Artifacts", "cannon-fx"))
    os.makedirs(out, exist_ok=True)
    smoke = np.zeros((4 * TILE, 4 * TILE, 4), np.uint8)
    for k in range(16):
        d, l, s, w = smoke_tile(1000 + k)
        r, c = divmod(k, 4)
        smoke[r * TILE:(r + 1) * TILE, c * TILE:(c + 1) * TILE] = np.stack([to8(d), to8(l), to8(s), to8(w)], axis=-1)
    Image.fromarray(smoke, "RGBA").save(os.path.join(out, "T_CannonSmoke.png"))
    flame = np.zeros((2 * TILE, 2 * TILE, 4), np.uint8)
    for k in range(4):
        b, h, g, bl = flame_tile(2000 + k)
        r, c = divmod(k, 2)
        flame[r * TILE:(r + 1) * TILE, c * TILE:(c + 1) * TILE] = np.stack([to8(b), to8(h), to8(g), to8(bl)], axis=-1)
    Image.fromarray(flame, "RGBA").save(os.path.join(out, "T_CannonFlame.png"))
    if "--preview" in argv:
        # A look at both: smoke lit from above over a sky grey, the flame in its colours over black.
        a = smoke[..., 0] / 255.0
        lit = smoke[..., 1] / 255.0
        col = (0.45 + 0.5 * lit)[..., None] * np.array([0.92, 0.9, 0.86])
        sky = np.array([0.55, 0.65, 0.78])
        Image.fromarray(to8(sky * (1 - a[..., None]) + col * a[..., None]), "RGB").save(os.path.join(out, "preview_smoke.png"))
        br = flame[..., 0] / 255.0
        ht = flame[..., 1] / 255.0
        c = br[..., None] * (np.array([1.0, 0.35, 0.08]) * (1 - ht[..., None]) + np.array([1.0, 0.92, 0.7]) * ht[..., None])
        Image.fromarray(to8(c), "RGB").save(os.path.join(out, "preview_flame.png"))
    print(f"cannon textures -> {os.path.relpath(out, REPO)}")


if __name__ == "__main__":
    main(sys.argv[1:])
