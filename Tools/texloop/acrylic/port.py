"""Smoked acrylic glazing wear in numpy: the ACRYLIC_WEAR lines of BOAT_CODE (scripts/make_materials.py), line for line,
for the texture loop's swatches (docs/texloop-acrylic). test_acrylic.py checks the constants still match the HLSL.

Inputs are per-pixel arrays: n (world normal, camera side), p (cm, the projection across the pane: BOAT_CODE's hwP),
px (cm a pixel spans across the pane: |fwidth(p)|), depth (cm).
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wear  # noqa: E402

BLEACH = (1.5, 1.35, 1.15)
HAZE = (0.20, 0.205, 0.21)
DUST = (0.13, 0.105, 0.075)
CRACK = (0.42, 0.42, 0.41)
SCRATCH = (0.36, 0.36, 0.35)
MINERAL = (0.42, 0.41, 0.38)
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


def vnoise(q, k1, k2):
    i = np.floor(q); f = q - i
    f = f * f * (3 - 2 * f)
    ix, iy = i[..., 0], i[..., 1]
    a = lerp(h2(ix, iy, k1, k2), h2(ix + 1, iy, k1, k2), f[..., 0])
    b = lerp(h2(ix, iy + 1, k1, k2), h2(ix + 1, iy + 1, k1, k2), f[..., 0])
    return lerp(a, b, f[..., 1])


def noise(p):
    """acN: 2.5 and 0.8 cm value noise on a rotated lattice."""
    q = p / 2.5
    out = np.zeros(p.shape[:-1])
    for amp in (0.65, 0.35):
        out += amp * vnoise(q, 23.3, 71.9)
        q = np.stack([q[..., 0] * 0.8 - q[..., 1] * 0.6, q[..., 0] * 0.6 + q[..., 1] * 0.8], -1) * 3.1 + 4.1
    return out


def acrylic(base, rough0, coat0, age, care, n, p, px, depth, sun=1.0, parts=False):
    """Returns (albedo (..., 3), roughness, clear coat, haze) for smoked acrylic of colour `base` at (age, care)."""
    shape = n.shape[:-1]
    col = np.broadcast_to(np.asarray(base, float), shape + (3,)).copy()
    rough = np.full(shape, float(rough0))
    coat = np.full(shape, float(coat0))
    on = 1.0 if age >= 0.0 else 0.0
    tk, dk = wear.time_k(age, care), wear.dirt_k(age, care)
    cr_ = float(np.clip(care, 0, 1))
    nz = n[..., 2]
    sky = sat(0.5 + 0.5 * nz)
    near = 1.0 - smoothstep(150.0, 400.0, depth)
    px = np.maximum(px, 0.002)
    an = noise(p)
    col = col * lerp(np.ones(3), np.array(BLEACH), (on * 0.6 * tk * sky * sun)[..., None])
    haze = on * sat(tk * (0.12 + 0.55 * dk) * (1.0 - 0.5 * cr_) * (0.6 + 0.4 * sky) * sun * (0.75 + 0.5 * an))
    col = lerp(col, np.array(HAZE), (0.55 * haze)[..., None])
    rough = lerp(rough, 0.32, haze)
    coat = coat * (1.0 - 0.8 * haze)
    dust = on * dk * sat(nz * 1.5) * (0.35 + 0.65 * an)
    col = lerp(col, np.array(DUST), (0.45 * dust)[..., None])
    rough = lerp(rough, 0.7, 0.6 * dust)
    coat = coat * (1.0 - 0.7 * dust)
    zn = vnoise(p / 6.0, 53.1, 17.3)
    cr = on * sat((tk - 0.3) / 0.5) * (0.45 + 0.55 * (1.0 - cr_))
    cra = cr * smoothstep(1.0 - cr, 1.45 - cr, zn)
    crack = np.zeros(shape)
    if cr > 0:
        v = p / 0.25; vi = np.floor(v); vf = v - vi
        f1 = np.full(shape, 8.0); f2 = np.full(shape, 8.0)
        for y in (-1, 0, 1):
            for x in (-1, 0, 1):
                cx, cy = vi[..., 0] + x, vi[..., 1] + y
                jx = hfrac(np.sin(cx * 12.7 + cy * 31.1) * 43758.5)
                jy = hfrac(np.sin(cx * 26.9 + cy * 18.3) * 43758.5)
                d = np.hypot(x + jx - vf[..., 0], y + jy - vf[..., 1])
                f2 = np.where(d < f1, f1, np.minimum(f2, d))
                f1 = np.minimum(f1, d)
        w, pw = 0.006 / 0.25, px / 0.25
        crack = cra * near * (1.0 - smoothstep(0.0, np.maximum(w, pw), f2 - f1)) * np.minimum(1.0, w / pw * 2.5) * smoothstep(0.3, 0.7, an)
    col = lerp(col, np.array(HAZE), (0.35 * cra)[..., None])
    col = lerp(col, np.array(CRACK), (0.5 * crack)[..., None])
    rough = lerp(rough, 0.45, 0.4 * cra + 0.5 * crack)
    coat = coat * (1.0 - 0.5 * cra)
    sk = on * near * (0.08 * sat(4.0 * tk) + 0.45 * tk + 0.15 * dk)
    scr = np.zeros(shape)
    for layer in (0, 1):
        q = p if layer == 0 else np.stack([p[..., 0] * 0.6 - p[..., 1] * 0.8, p[..., 0] * 0.8 + p[..., 1] * 0.6], -1) + 0.6
        s = q / 1.2; sf = hfrac(s) - 0.5; si = np.floor(s)
        h = h2(si[..., 0], si[..., 1], 17.9 + 3.0 * layer, 83.3, 43758.5)
        dx, dy = np.cos(h * 31.4159), np.sin(h * 31.4159)
        al = (sf[..., 0] * dx + sf[..., 1] * dy) * 1.2
        ac = (-sf[..., 0] * dy + sf[..., 1] * dx) * 1.2
        ln = 0.3 + 0.4 * hfrac(h * 7.3)
        t = sat(1.0 - np.abs(al) / ln)
        ac = ac + (hfrac(h * 5.9) - 0.5) * 0.8 * al * al
        sw = 0.006 * np.sqrt(t)
        one = (hfrac(h * 3.1) >= 1.0 - sk) * (t >= 0.001) * (1.0 - smoothstep(0.0, np.maximum(sw, px), np.abs(ac))) \
            * np.minimum(1.0, sw / px * 2.5) * (0.4 + 0.6 * hfrac(h * 11.3))
        scr = np.maximum(scr, one)
    col = lerp(col, np.array(SCRATCH), (0.45 * scr)[..., None])
    rough = lerp(rough, 0.4, scr)
    wq = p / 0.5; wf = hfrac(wq) - 0.5; wi = np.floor(wq)
    wh = h2(wi[..., 0], wi[..., 1], 41.3, 29.9, 43758.5)
    wr = 0.05 + 0.07 * hfrac(wh * 7.7)
    off = np.stack([hfrac(wh * 3.3), hfrac(wh * 5.1)], -1) - 0.5
    wd = np.linalg.norm(wf - off * 0.2, axis=-1) * 0.5
    ww = np.maximum(0.012, px)
    spot = on * (wh >= 1.0 - 0.18 * dk * (0.2 + 0.8 * sat(nz * 2.0))) \
        * np.maximum(np.exp(-((wd - wr) / ww) ** 2) * np.minimum(1.0, 0.012 / px * 2.0), 0.12 * smoothstep(wr, wr - ww, wd))
    col = lerp(col, np.array(MINERAL), (0.5 * spot)[..., None])
    rough = lerp(rough, 0.6, spot)
    mc = p / 0.15
    m = h2(np.floor(mc[..., 0]), np.floor(mc[..., 1]), 19.3, 47.9)
    mil = on * sat((dk - 0.6) / 0.4) * (1 - cr_) * (m >= 0.95) * sat(an * 2.0 - 0.6) \
        * (1 - smoothstep(0.25, 0.4, np.linalg.norm(hfrac(mc) - 0.5, axis=-1)))
    col = lerp(col, np.array(MILDEW), (0.7 * mil)[..., None])
    haze_out = sat(haze + 0.5 * cra + 0.6 * dust + 0.3 * spot)
    if parts:
        return col, rough, coat, haze_out, dict(haze=haze, dust=dust, craze=cra, crack=crack, scratch=scr, spot=spot, mildew=mil)
    return col, rough, coat, haze_out
