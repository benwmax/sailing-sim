"""Black moulded plastic wear in numpy: the PLASTIC_WEAR lines of BOAT_CODE (scripts/make_materials.py), line for line,
for the texture loop's swatches (docs/texloop-plastic). test_plastic.py checks the constants still match the HLSL.

Inputs are per-pixel arrays: n (world normal, camera side), p (cm, the projection across the face: BOAT_CODE's hwP),
curv (1/cm, |fwidth(n)| / |fwidth(WP)|), depth (cm), cav (0..1, the kit trim sheet's cavities; 0 on the boats).
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wear  # noqa: E402

CHALK = (0.190, 0.185, 0.172)
DUST = (0.13, 0.105, 0.075)
SCUFF = (0.085, 0.085, 0.082)
MILDEW = (0.02, 0.024, 0.016)


def sat(x):
    return np.clip(x, 0.0, 1.0)


def smoothstep(a, b, x):
    t = sat((x - a) / (b - a))
    return t * t * (3 - 2 * t)


def hfrac(x):
    return x - np.floor(x)


def h2(ix, iy, k1, k2, m=4375.5):
    return hfrac(np.sin(ix * k1 + iy * k2) * m)


def lerp(a, b, t):
    return a + (b - a) * t


def noise(p):
    """bpN: 1.2 and 0.39 cm value noise on a rotated lattice."""
    q = p / 1.2
    out = np.zeros(p.shape[:-1])
    for o, amp in enumerate((0.65, 0.35)):
        i = np.floor(q); f = q - i
        f = f * f * (3 - 2 * f)
        ix, iy = i[..., 0], i[..., 1]
        a = lerp(h2(ix, iy, 31.7, 57.1), h2(ix + 1, iy, 31.7, 57.1), f[..., 0])
        b = lerp(h2(ix, iy + 1, 31.7, 57.1), h2(ix + 1, iy + 1, 31.7, 57.1), f[..., 0])
        out += amp * lerp(a, b, f[..., 1])
        q = np.stack([q[..., 0] * 0.8 - q[..., 1] * 0.6, q[..., 0] * 0.6 + q[..., 1] * 0.8], -1) * 3.1 + 7.7
    return out


def plastic(base, rough0, age, care, n, p, curv, depth, cav=None, sun=1.0, parts=False):
    """Returns (albedo (..., 3), roughness) for black plastic of colour `base` at (age, care)."""
    shape = n.shape[:-1]
    col = np.broadcast_to(np.asarray(base, float), shape + (3,)).copy()
    rough = np.full(shape, float(rough0))
    if cav is None:
        cav = np.zeros(shape)
    on = 1.0 if age >= 0.0 else 0.0
    tk, dk = wear.time_k(age, care), wear.dirt_k(age, care)
    nz = n[..., 2]
    sky = sat(0.5 + 0.5 * nz)
    bn = noise(p)
    chalk = on * sat(tk * (0.25 + 1.3 * dk) * sky * sun * (1.0 + (bn - 0.5) * (0.4 + 1.2 * dk)))
    col = lerp(col, np.array(CHALK), ((0.85 - 0.45 * sat(care)) * chalk)[..., None])
    rough = lerp(rough, lerp(0.82, 0.55, sat(care)), chalk)
    dust = on * dk * sat(nz * 1.5) * (0.5 + 0.5 * cav) * (0.5 + 0.5 * bn)
    col = lerp(col, np.array(DUST), (0.6 * dust)[..., None]); rough = lerp(rough, 0.9, 0.5 * dust)
    near = 1.0 - smoothstep(150.0, 400.0, depth)
    pol = on * sat(tk * 2.0) * sat((curv - 0.7) * 2.0) * near * (0.6 + 0.4 * bn)
    col = lerp(col, np.asarray(base, float) * 0.85, (0.85 * pol)[..., None]); rough = lerp(rough, 0.2, 0.8 * pol)
    c = p / 1.5; cf = hfrac(c) - 0.5; ci = np.floor(c)
    h = h2(ci[..., 0], ci[..., 1], 17.9, 83.3, 43758.5)
    dx, dy = np.cos(h * 31.4159), np.sin(h * 31.4159)
    along = (cf[..., 0] * dx + cf[..., 1] * dy) * 1.5
    across = (-cf[..., 0] * dy + cf[..., 1] * dx) * 1.5
    ln = 0.25 + 0.35 * hfrac(h * 7.3)
    t = sat(1.0 - np.abs(along) / ln)
    across = across + (hfrac(h * 5.9) - 0.5) * 0.5 * along * along
    scr = on * near * (hfrac(h * 3.1) >= 1.0 - 0.08 * sat(4.0 * tk) - 0.35 * tk - 0.15 * dk) \
        * (1 - smoothstep(0.03, 0.08, np.abs(across) / np.maximum(np.sqrt(t), 0.05))) * (t >= 0.001) * (0.35 + 0.65 * hfrac(h * 11.3))
    col = lerp(col, np.array(SCUFF), (0.6 * scr)[..., None]); rough = lerp(rough, 0.6, scr)
    mc = p / 0.15
    m = h2(np.floor(mc[..., 0]), np.floor(mc[..., 1]), 19.3, 47.9)
    mil = on * sat((dk - 0.6) / 0.4) * (1 - sat(care)) * (m >= 0.93) * sat(bn * 2.0 - 0.6) \
        * (1 - smoothstep(0.25, 0.4, np.linalg.norm(hfrac(mc) - 0.5, axis=-1)))
    col = lerp(col, np.array(MILDEW), (0.7 * mil)[..., None])
    if parts:
        return col, rough, dict(chalk=chalk, dust=dust, polish=pol, scuff=scr, mildew=mil)
    return col, rough
