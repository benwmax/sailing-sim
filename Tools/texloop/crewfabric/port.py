"""Crew fabric wear in numpy: the FABRIC_WEAR lines of FABRIC_CODE (scripts/make_materials.py), line for line, for the
texture loop's swatches (docs/texloop-crewfabric). test_crewfabric.py checks the constants still match the HLSL.

Inputs are per-pixel arrays: albedo (..., 3) and roughness as FABRIC_CODE has them before the block, detail (the scan's
luminance over its mean), uv (..., 2, the garment's UV0), nz (the world normal's z), depth (cm). Kind and UVm as on the
material instance.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wear  # noqa: E402

# (sun fade, grime, mildew, pilling), (tide marks, coating loss) per Kind: FABRIC_CODE's fwW and fwW2
W = {1: (0.50, 1.00, 1.00, 0.00), 2: (0.40, 0.75, 0.00, 1.00), 3: (0.75, 0.85, 0.60, 0.25), 4: (0.50, 0.80, 0.30, 0.35)}
W2 = {1: (0.00, 1.00), 2: (0.00, 0.00), 3: (1.00, 0.00), 4: (0.00, 0.00)}
FADE_TINT = (1.0, 0.98, 0.94)
GRIME = (0.045, 0.038, 0.026)
SALT = (0.62, 0.60, 0.55)
MILDEW = (0.030, 0.035, 0.025)


def sat(x):
    return np.clip(x, 0.0, 1.0)


def smoothstep(a, b, x):
    t = sat((x - a) / (b - a))
    return t * t * (3 - 2 * t)


def hfrac(x):
    return x - np.floor(x)


def lerp(a, b, t):
    return a + (b - a) * t


def h(ix, iy, k1, k2, m):
    return hfrac(np.sin(ix * k1 + iy * k2) * m)


def vn(q):
    """FW_VN: one octave of value noise on a unit grid."""
    i = np.floor(q); f = q - i
    f = f * f * (3 - 2 * f)
    ix, iy = i[..., 0], i[..., 1]
    a = lerp(h(ix, iy, 27.1, 61.7, 4375.5), h(ix + 1, iy, 27.1, 61.7, 4375.5), f[..., 0])
    b = lerp(h(ix, iy + 1, 27.1, 61.7, 4375.5), h(ix + 1, iy + 1, 27.1, 61.7, 4375.5), f[..., 0])
    return lerp(a, b, f[..., 1])


def rot(p, c, s):
    return np.stack([p[..., 0] * c - p[..., 1] * s, p[..., 0] * s + p[..., 1] * c], -1)


def lum(c):
    return c[..., 0] * 0.3 + c[..., 1] * 0.59 + c[..., 2] * 0.11


def fabric(albedo, rough, fuzz, detail, uv, nz, depth, age, care, kind, uvm=1.0, parts=False):
    """Returns (albedo, roughness, fuzz) after FABRIC_WEAR at (age, care)."""
    col = np.array(albedo, float, copy=True)
    rough = np.array(rough, float, copy=True)
    fuzz = np.array(fuzz, float, copy=True)
    on = float(age >= 0.0) * float(kind >= 0.5)
    a = max(age, 0.0)
    tk = on * wear.time_k(a, care)
    dk = on * wear.dirt_k(a, care)
    fk = int(kind + 0.5)
    w = W.get(fk, W[4]); w2 = W2.get(fk, W2[4])
    p = uv * uvm * 100.0
    fb = vn(rot(p, 0.8, 0.6) / 3.1 + 5.3)
    blot = 0.65 * vn(p / 9.0) + 0.35 * fb
    grime_n = 0.65 * vn(p / 14.0 + 11.7) + 0.35 * vn(rot(p, 0.6, 0.8) / 4.3 + 2.9)
    sky = sat(0.5 + 0.5 * nz)
    near = 1.0 - smoothstep(60.0, 150.0, depth)
    L = lum(col)[..., None]
    faded = lerp(col, np.repeat(L, 3, -1), 0.55) + 0.07 * (1.0 - L) * np.array(FADE_TINT)
    fade = sat(tk ** 0.7 * w[0] * (0.35 + 0.65 * sky) * (0.8 + 0.4 * blot) * lerp(1.0, sat(detail), 0.3))
    col = lerp(col, faded, fade[..., None])
    rough = lerp(rough, 0.88, 0.6 * tk * w2[1])
    grime = dk * w[1] * sat(0.2 + 0.8 * smoothstep(0.4, 0.7, grime_n) * (0.5 + 0.5 * (1.0 - sky)))
    col = lerp(col, col * 0.6 + np.array(GRIME), grime[..., None])
    rough = lerp(rough, 0.9, 0.4 * grime)
    pc = p / 0.12
    ph = h(np.floor(pc[..., 0]), np.floor(pc[..., 1]), 17.9, 83.3, 43758.5)
    pill = near * w[3] * (ph >= 1.0 - 0.30 * tk - 0.15 * dk) * (1.0 - smoothstep(0.22, 0.38, np.linalg.norm(hfrac(pc) - 0.5, axis=-1)))
    L2 = lum(col)[..., None]
    col = lerp(col, lerp(col, np.repeat(L2, 3, -1), 0.5) * 1.15 + 0.03, (0.7 * pill)[..., None])
    fuzz = sat(fuzz + 0.35 * tk * w[3])
    ring = np.abs(hfrac((p[..., 1] + 1.5 * blot) / 1.6) - 0.5)
    tk_ = sat((dk - 0.2) / 0.5) * w2[0] * (1.0 - smoothstep(0.1, 0.35, uv[..., 1])) * (0.5 + 0.5 * fb)
    tide = tk_ * smoothstep(0.44, 0.48, ring)
    tide_in = tk_ * smoothstep(0.34, 0.42, ring) * (1.0 - smoothstep(0.42, 0.45, ring))
    col = lerp(col, col * 0.8, (0.5 * tide_in)[..., None])
    col = lerp(col, np.array(SALT), (0.3 * tide)[..., None])
    m = vn(p / 5.0 + 3.3)
    mc = p / 0.18
    mh = h(np.floor(mc[..., 0]), np.floor(mc[..., 1]), 19.3, 47.9, 4375.5)
    mo = np.stack([hfrac(mh * 7.1), hfrac(mh * 13.7)], -1) * 0.5 - 0.25
    speck = (mh >= 0.75) * (1.0 - smoothstep(0.12, 0.25, np.linalg.norm(hfrac(mc) - 0.5 - mo, axis=-1)))
    mil = w[2] * sat((dk - 0.5) / 0.4) * (1.0 - sat(care)) * smoothstep(0.6, 0.8, m)
    col = lerp(col, np.array(MILDEW), (mil * lerp(0.25, 0.9 * speck, near))[..., None])
    if parts:
        return col, rough, fuzz, dict(fade=fade, grime=grime, pill=pill, tide=tide, mildew=mil * lerp(0.25, 0.9 * speck, near))
    return col, rough, fuzz
