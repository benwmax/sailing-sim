"""Graphics G1: the cloud noise volumes, baked here instead of the engine's single Perlin-Worley volume (whose 1.25 km
repeat showed as the same puff over and over).

Layout after Guerrilla's Nubis (Schneider, "The Real-Time Volumetric Cloudscapes of Horizon Zero Dawn", SIGGRAPH 2015):
  T_CloudShape   128^3, RGBA: R Perlin-Worley (the base shape), G/B/A Worley fBm at 4, 8 and 16 cells per tile
  T_CloudDetail   64^3, RGB: Worley fBm at 8, 16 and 32 cells per tile (erosion of the edges)
  T_CloudCurl    128^2, RG: 2D curl of a tileable Perlin field, for domain warp and wisps (0.5 = zero)
Every volume tiles in all three axes. A volume is written as a 2D atlas of its Z slices (tiles in rows of COLS), the
layout Unreal's volume texture factory takes (Source2DTileSizeX/Y).

    Tools/venv/bin/python Tools/clouds/make_cloud_noise.py <out dir>
Writes T_CloudShape.png (2048x1024), T_CloudDetail.png (512x512), T_CloudCurl.png (128x128) and prints their stats.
"""
import os
import sys

import numpy as np
from PIL import Image

RNG = np.random.default_rng(20261013)


def worley(n, cells, seed):
    """Tileable 3D Worley (1 - F1, normalised) on an n^3 grid with cells^3 feature points."""
    rng = np.random.default_rng(seed)
    pts = rng.random((cells, cells, cells, 3))
    ax = (np.arange(n) + 0.5) / n * cells
    x, y, z = np.meshgrid(ax, ax, ax, indexing="ij")
    ix, iy, iz = np.floor(x).astype(int), np.floor(y).astype(int), np.floor(z).astype(int)
    best = np.full(x.shape, 9.0, dtype=np.float32)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                cx, cy, cz = ix + dx, iy + dy, iz + dz
                p = pts[cx % cells, cy % cells, cz % cells]
                d = (x - (cx + p[..., 0])) ** 2 + (y - (cy + p[..., 1])) ** 2 + (z - (cz + p[..., 2])) ** 2
                best = np.minimum(best, d.astype(np.float32))
    f1 = np.sqrt(best)
    return 1.0 - np.clip(f1 / np.sqrt(3) * 1.6, 0.0, 1.0)


def perlin3(n, cells, seed, octaves=4):
    """Tileable 3D gradient-noise fBm in 0..1."""
    total = np.zeros((n, n, n), np.float32)
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        c = cells * 2 ** o
        rng = np.random.default_rng(seed + o)
        g = rng.normal(size=(c, c, c, 3))
        g /= np.linalg.norm(g, axis=-1, keepdims=True)
        ax = (np.arange(n) + 0.5) / n * c
        x, y, z = np.meshgrid(ax, ax, ax, indexing="ij")
        i0 = [np.floor(v).astype(int) for v in (x, y, z)]
        f = [v - np.floor(v) for v in (x, y, z)]
        s = [t * t * t * (t * (t * 6 - 15) + 10) for t in f]
        acc = np.zeros_like(x)
        for dx in (0, 1):
            wx = s[0] if dx else 1 - s[0]
            for dy in (0, 1):
                wy = s[1] if dy else 1 - s[1]
                for dz in (0, 1):
                    wz = s[2] if dz else 1 - s[2]
                    gg = g[(i0[0] + dx) % c, (i0[1] + dy) % c, (i0[2] + dz) % c]
                    dot = gg[..., 0] * (f[0] - dx) + gg[..., 1] * (f[1] - dy) + gg[..., 2] * (f[2] - dz)
                    acc += wx * wy * wz * dot
        total += amp * acc
        norm += amp
        amp *= 0.5
    return np.clip(total / norm * 1.4 + 0.5, 0.0, 1.0)


def fbm_worley(n, base, seed):
    v = 0.625 * worley(n, base, seed) + 0.25 * worley(n, base * 2, seed + 1) + 0.125 * worley(n, base * 4, seed + 2)
    return (v - v.min()) / (v.max() - v.min())  # full 0..1 range: the shader's remaps assume it


def remap(v, lo, hi, nlo, nhi):
    return nlo + (v - lo) / (hi - lo) * (nhi - nlo)


def atlas(vol, cols):
    """Z slices of an (n,n,n,c) volume into rows of `cols` tiles: X along a tile's columns, Y down its rows."""
    n = vol.shape[0]
    rows = n // cols
    out = np.zeros((rows * n, cols * n, vol.shape[3]), np.uint8)
    for z in range(n):
        r, c = divmod(z, cols)
        out[r * n:(r + 1) * n, c * n:(c + 1) * n] = np.clip(vol[:, :, z].transpose(1, 0, 2) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return out


def stats(name, v):
    print(f"{name}: shape {v.shape} mean {v.mean():.3f} std {v.std():.3f} min {v.min():.3f} max {v.max():.3f}")


def main(out):
    os.makedirs(out, exist_ok=True)
    n = 128
    perlin = perlin3(n, 4, 11)
    w_lo = fbm_worley(n, 4, 21)
    # Perlin-Worley: Perlin's billows pushed into Worley's cells (Nubis' remap of Perlin by the inverted Worley).
    pw = np.clip(remap(perlin, -(1.0 - w_lo), 1.0, 0.0, 1.0), 0.0, 1.0)
    shape = np.stack([pw, w_lo, fbm_worley(n, 8, 31), fbm_worley(n, 16, 41)], axis=-1)
    for i, c in enumerate("RGBA"):
        stats(f"T_CloudShape.{c}", shape[..., i])
    Image.fromarray(atlas(shape, 16), "RGBA").save(os.path.join(out, "T_CloudShape.png"))

    m = 64
    detail = np.stack([fbm_worley(m, 8, 51), fbm_worley(m, 16, 61), fbm_worley(m, 32, 71)], axis=-1)
    for i, c in enumerate("RGB"):
        stats(f"T_CloudDetail.{c}", detail[..., i])
    Image.fromarray(atlas(detail, 8), "RGB").save(os.path.join(out, "T_CloudDetail.png"))

    # Curl of a tileable 2D potential (a slice of 3D Perlin): divergence-free swirl for domain warp.
    k = 128
    pot = perlin3(k, 4, 81, octaves=3)[:, :, 0]
    dy = (np.roll(pot, -1, 1) - np.roll(pot, 1, 1)) * 0.5 * k
    dx = (np.roll(pot, -1, 0) - np.roll(pot, 1, 0)) * 0.5 * k
    curl = np.stack([dy, -dx], axis=-1)
    curl /= np.abs(curl).max()
    stats("T_CloudCurl", curl)
    img = np.clip((curl * 0.5 + 0.5) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    img = np.concatenate([img, np.zeros((k, k, 1), np.uint8)], axis=-1)
    Image.fromarray(img.transpose(1, 0, 2), "RGB").save(os.path.join(out, "T_CloudCurl.png"))


if __name__ == "__main__":
    main(sys.argv[1])
