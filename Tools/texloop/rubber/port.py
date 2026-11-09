"""Rubber and webbing wear in numpy: the RUBBER_WEAR and WEBBING_WEAR lines of BOAT_CODE (scripts/make_materials.py),
line for line, for the texture loop's swatches (docs/texloop-rubber). test_rubber.py checks the constants still match
the HLSL.

Inputs are per-pixel arrays: n (world normal, camera side), p (cm, the projection across the face: BOAT_CODE's hwP;
x runs along a rub rail or a strap), curv (1/cm, |fwidth(n)| / |fwidth(WP)|, webbing only), depth (cm).
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wear  # noqa: E402

BLOOM = (0.13, 0.12, 0.105)
PVC_YELLOW = (1.02, 0.97, 0.85)
CRACK = (0.012, 0.011, 0.01)
ABRADE = (0.13, 0.126, 0.12)
MARK = (0.035, 0.033, 0.03)
DUST = (0.13, 0.105, 0.075)
MILDEW = (0.02, 0.024, 0.016)
WB_FADE = (0.1, 0.078, 0.055)
WB_FUZZ = (0.06, 0.06, 0.057)
WB_GRIT = (0.04, 0.032, 0.02)
WB_FRAY = (0.07, 0.066, 0.06)
WB_MILDEW = (0.018, 0.022, 0.014)
LUMA = np.array([0.3, 0.59, 0.11])


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


def vnoise(q, k1, k2):
    i = np.floor(q); f = q - i
    f = f * f * (3 - 2 * f)
    ix, iy = i[..., 0], i[..., 1]
    a = lerp(h2(ix, iy, k1, k2), h2(ix + 1, iy, k1, k2), f[..., 0])
    b = lerp(h2(ix, iy + 1, k1, k2), h2(ix + 1, iy + 1, k1, k2), f[..., 0])
    return lerp(a, b, f[..., 1])


def noise2(p, scale, k1, k2, mul, add):
    q = p / scale
    out = np.zeros(p.shape[:-1])
    for amp in (0.65, 0.35):
        out += amp * vnoise(q, k1, k2)
        q = np.stack([q[..., 0] * 0.8 - q[..., 1] * 0.6, q[..., 0] * 0.6 + q[..., 1] * 0.8], -1) * mul + add
    return out


def facing_z(n, v):
    return np.where((n * v).sum(-1) < 0.0, -n[..., 2], n[..., 2])


def rubber(base, rough0, age, care, n, v, p, depth, sun=1.0, parts=False):
    """(albedo, roughness) for rubber or soft PVC of colour `base`. Age unset: the old ageK lines."""
    shape = n.shape[:-1]
    col = np.broadcast_to(np.asarray(base, float), shape + (3,)).copy()
    rough = np.full(shape, float(rough0))
    if age < 0.0:
        ak = wear.age_k(age, care)
        col = lerp(col, col + 0.05, ak); rough = lerp(rough, 0.85, ak)
        return (col, rough, {}) if parts else (col, rough)
    tk, dk = wear.time_k(age, care), wear.dirt_k(age, care)
    care = float(np.clip(care, 0, 1))
    nz = facing_z(n, v)
    sky = sat(0.5 + 0.5 * nz)
    rn = noise2(p, 2.0, 23.3, 71.9, 3.1, 4.9)
    pale = sat(((col * LUMA).sum(-1) - 0.04) * 10.0)
    bloom = sat(tk * (0.3 + 1.2 * dk) * sky * sun * (1.0 + (rn - 0.5) * (0.5 + 1.0 * dk)))
    tgt = lerp(np.array(BLOOM), col * np.array(PVC_YELLOW) + 0.015, pale[..., None])
    col = lerp(col, tgt, ((0.85 - 0.6 * care) * bloom)[..., None])
    rough = lerp(rough, lerp(0.92, 0.45, care), bloom)
    near = 1.0 - smoothstep(150.0, 400.0, depth)
    ck = smoothstep(0.45, 0.85, tk) * (1.0 - 0.85 * care) * (1.0 - 0.7 * pale) * near * (0.4 + 0.6 * sky)
    cq = p / np.array([0.35, 0.9]); cf = hfrac(cq) - 0.5; ci = np.floor(cq)
    ch = h2(ci[..., 0], ci[..., 1], 41.9, 13.7, 43758.5)
    cl = 0.25 + 0.25 * hfrac(ch * 3.3)
    cx = cf[..., 0] - (hfrac(ch * 7.1) - 0.5) * 0.5 + 0.9 * cf[..., 1] * (hfrac(ch * 5.3) - 0.5) + 0.1 * np.sin(cf[..., 1] * 9.0 + ch * 20.0)
    crack = ck * (0.5 + 0.5 * hfrac(ch * 2.3)) * (hfrac(ch * 11.7) >= 1.0 - 0.5 * ck) * (1.0 - smoothstep(0.04, 0.05 + 0.08 * ck, np.abs(cx))) \
        * (1.0 - smoothstep(cl - 0.1, cl, np.abs(cf[..., 1]))) * sat(rn * 3.0 - 0.9 + ck)
    col = lerp(col, np.array(CRACK), (0.85 * crack)[..., None]); rough = lerp(rough, 0.95, crack)
    s = p / np.array([6.0, 0.35]); sf = hfrac(s) - 0.5; si = np.floor(s)
    h = h2(si[..., 0], si[..., 1], 15.7, 77.3, 43758.5)
    t = sat(1.0 - np.abs(sf[..., 0] + (hfrac(h * 3.7) - 0.5) * 0.4) / (0.2 + 0.25 * hfrac(h * 5.3)))
    w = (0.06 + 0.16 * hfrac(h * 9.1)) * np.sqrt(t)
    rash = (1.0 - smoothstep(w, w + 0.08, np.abs(sf[..., 1] + 0.15 * (hfrac(h * 2.9) - 0.5)))) * (t >= 0.001) \
        * (hfrac(h * 7.7) >= 1.0 - 0.25 * sat(3.0 * tk) - 0.5 * dk) * (1.0 - sat(np.abs(nz) * 1.5)) * (1.0 - smoothstep(400.0, 1200.0, depth))
    rc = lerp(np.array(ABRADE), np.array(MARK), pale[..., None])
    col = lerp(col, rc, (0.7 * (0.5 + 0.5 * hfrac(h * 13.1)) * rash)[..., None]); rough = lerp(rough, 0.85, rash)
    dust = dk * sat(nz * 1.5) * (0.5 + 0.5 * rn)
    col = lerp(col, np.array(DUST), (0.7 * dust)[..., None]); rough = lerp(rough, 0.9, 0.5 * dust)
    mc = p / 0.15
    m = h2(np.floor(mc[..., 0]), np.floor(mc[..., 1]), 19.3, 47.9)
    mil = sat((dk - 0.6) / 0.4) * (1.0 - care) * (m >= 0.92) * sat(rn * 2.0 - 0.6) \
        * (1.0 - smoothstep(0.25, 0.4, np.linalg.norm(hfrac(mc) - 0.5, axis=-1)))
    col = lerp(col, np.array(MILDEW), (0.7 * mil)[..., None])
    if parts:
        return col, rough, dict(bloom=bloom, crack=crack, rash=rash, dust=dust, mildew=mil)
    return col, rough


def webbing(base, rough0, age, care, n, v, p, curv, depth, sun=1.0, parts=False):
    """(albedo, roughness) for woven webbing of colour `base`. Age unset: the old rope/canvas lines (ageK)."""
    shape = n.shape[:-1]
    col = np.broadcast_to(np.asarray(base, float), shape + (3,)).copy()
    rough = np.full(shape, float(rough0))
    rib = np.abs(np.sin(3.14159 * p[..., 1] / 0.12))
    weft = np.abs(np.sin(3.14159 * (p[..., 0] + 0.06 * (hfrac(p[..., 1] / 0.24) >= 0.5)) / 0.12))
    col = col * lerp(1.0, (0.7 + 0.45 * np.sqrt(rib)) * (0.85 + 0.2 * weft), 1.0 - smoothstep(100.0, 300.0, depth))[..., None]
    if age < 0.0:
        ak = wear.age_k(age, care)
        col = lerp(col, col * 0.8 + np.array([0.035, 0.033, 0.026]), ak)
        return (col, rough, {}) if parts else (col, rough)
    tk, dk = wear.time_k(age, care), wear.dirt_k(age, care)
    care = float(np.clip(care, 0, 1))
    nz = facing_z(n, v)
    sky = sat(0.5 + 0.5 * nz)
    wn = noise2(p, 3.0, 29.3, 53.9, 3.0, 6.1)
    wt = tk * (1.0 - 0.5 * float(smoothstep(0.6, 0.95, care)) * min(max(age / 8.0, 0.0), 1.0))
    lum = (col * LUMA).sum(-1)
    fade = sat(wt * (0.55 + 0.45 * sky) * sun * (0.8 + 0.4 * wn))
    col = lerp(col, lerp(np.repeat(lum[..., None], 3, -1), col, 0.4) * 0.9 + np.array(WB_FADE), (0.8 * fade)[..., None])
    fuzz = sat(wt * (0.6 + 0.9 * dk)) * sat(wn * 2.2 - 0.4)
    col = lerp(col, col + np.array(WB_FUZZ), (0.6 * fuzz)[..., None]); rough = lerp(rough, 0.97, fuzz)
    dirt = dk * (0.5 + 0.5 * wn)
    col = lerp(col, col * 0.75 + np.array(WB_GRIT), (0.7 * dirt)[..., None])
    near = 1.0 - smoothstep(150.0, 400.0, depth)
    fray = sat((wt - 0.3) * 2.5) * sat((curv - 0.7) * 2.0) * near * (0.4 + 0.6 * dk) * (0.5 + 0.5 * wn)
    col = lerp(col, col + np.array(WB_FRAY), (0.8 * fray)[..., None]); rough = lerp(rough, 1.0, fray)
    mc = p / 0.2
    m = h2(np.floor(mc[..., 0]), np.floor(mc[..., 1]), 19.3, 47.9)
    mil = sat((dk - 0.45) / 0.35) * (1.0 - care) * (m >= 0.88) * sat(wn * 2.5 - 1.0) \
        * (1.0 - smoothstep(0.25, 0.42, np.linalg.norm(hfrac(mc) - 0.5, axis=-1)))
    col = lerp(col, np.array(WB_MILDEW), (0.85 * mil)[..., None])
    if parts:
        return col, rough, dict(fade=fade, fuzz=fuzz, dirt=dirt, fray=fray, mildew=mil)
    return col, rough
