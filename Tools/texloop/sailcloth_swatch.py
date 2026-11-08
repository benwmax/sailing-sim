"""Sailcloth wear swatches: a CPU (numpy) port of the white-cloth part of SAIL_CODE (scripts/make_materials.py), so the
texture loop can compare the five wear levels before and after a change without the engine.

What it ports: the panel tone and weave, the sun yellowing, the foot grime, the mildew specks, the crinkle and flaking
folds as normals, and (after) the Time/Dirt wear. What it leaves out: marks, seams' stitching, the window, the belly and
wrinkle shading (screen derivatives) and the light through the cloth. The lighting is a plain overcast sky (a soft key from
above plus ambient), the same for every level, so only the cloth differs. It is a judging aid, not the engine: the
in-game stills come from the PC with -SailingBoatAge=<years>,<care>.

    python3 sailcloth_swatch.py OUT_DIR             # writes before/after swatches and stats.json for L0..L4

Levels come from Tools/texloop/levels.json when present (the shared loop), else from the plan's table below.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LEVELS = {"L0": (0.0, 1.0), "L1": (0.3, 0.9), "L2": (6.0, 0.5), "L3": (30.0, 0.9), "L4": (20.0, 0.1)}
C = np.array([0.70, 0.68, 0.63])   # SailboatPawn's Dacron colour (linear)
R = 0.55                           # the cloth's roughness parameter (the kit's Dacron)


def levels():
    p = os.path.join(HERE, "levels.json")
    if os.path.exists(p):
        d = json.load(open(p))
        lv = d.get("levels", d)
        out = {}
        for k, v in lv.items():
            if isinstance(v, dict) and "age" in v:
                out[k] = (float(v["age"]), float(v["care"]))
        if out:
            return out
    return LEVELS


def sat(x):
    return np.clip(x, 0.0, 1.0)


def smooth(a, b, x):
    t = sat((x - a) / (b - a))
    return t * t * (3 - 2 * t)


def hash2(ix, iy, k1, k2, m=43758.5):
    return np.modf(np.sin(ix * k1 + iy * k2) * m)[0] % 1.0


def vnoise(x, y, k1=127.1, k2=311.7):
    """The shader's value noise: hashed corners, smoothstep blend; returns value and its x, y slopes."""
    ix, iy = np.floor(x), np.floor(y)
    fx, fy = x - ix, y - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    dsx, dsy = 6 * fx * (1 - fx), 6 * fy * (1 - fy)
    a00, a10 = hash2(ix, iy, k1, k2), hash2(ix + 1, iy, k1, k2)
    a01, a11 = hash2(ix, iy + 1, k1, k2), hash2(ix + 1, iy + 1, k1, k2)
    n = (a00 * (1 - sx) + a10 * sx) * (1 - sy) + (a01 * (1 - sx) + a11 * sx) * sy
    dx = ((a10 - a00) * (1 - sy) + (a11 - a01) * sy) * dsx
    dy = ((a01 - a00) * (1 - sx) + (a11 - a10) * sx) * dsy
    return n, dx, dy


def wear_split(age, care):
    """Time (care can't undo it) and Dirt (care removes it), from Age and Care. Mirrors Tools/texloop/wear.py when it
    exists (the shared loop's formulas); this fallback is the same formulas (wear.py, Nov 8 2026)."""
    try:
        sys.path.insert(0, HERE)
        import wear  # noqa: F401  (shared module from the gelcoat thread)
        return float(wear.time_k(age, care)), float(wear.dirt_k(age, care))
    except Exception:
        t = sat(0.25 * (1 - math.exp(-age / 0.75)) + 0.75 * (1 - math.exp(-age / 18.0)))
        d = sat((1 - math.exp(-age)) * (0.15 + 0.85 * (1 - sat(care))))
        return float(t), float(d)


def cloth(u, v, u2, v1, age, care, mode, px):
    """Albedo (linear RGB), roughness and the height slopes for white crosscut Dacron at UV0 (u, v) metres, UV2.x u2,
    UV1.y v1. mode 'before' is today's SAIL_CODE; 'after' the Time/Dirt version."""
    pw = 0.9
    base = np.broadcast_to(C, u.shape + (3,)).copy()
    weave = 0.5 + 0.5 * np.sin(u * 1400) * np.sin(v * 1400)
    panel = np.modf(np.sin(np.floor(v / pw) * 12.9898) * 43758.5453)[0] % 1.0
    col = base * (0.97 + 0.03 * weave)[..., None] * (0.985 + 0.03 * panel)[..., None]
    mott, _, _ = vnoise(u / 0.6, v / 0.6)
    whiteish = 1.0
    shape = sat(0.3 + 0.45 * np.exp(-u2 / 0.6) + 0.25 * v1 + 0.35 * (panel - 0.5) + 0.15 * (mott - 0.5))
    foot = (1 - smooth(0.05, 0.55 + 0.3 * mott, v)) * (0.6 + 0.4 * mott)
    sp_i, sp_j = np.floor(u / 0.045), np.floor(v / 0.045)
    sr = hash2(sp_i, sp_j, 41.3, 289.1, 15731.7)
    inner = np.hypot(u / 0.045 - sp_i - 0.5, v / 0.045 - sp_j - 0.5) <= 0.3
    rough = np.full(u.shape, R)
    if mode == "before":
        col *= 1 + (np.array([1.0, 0.95, 0.83]) - 1) * (shape * 0.6 * whiteish)[..., None]
        dk = sat(0.15 + age / 15.0) * (1 - 0.6 * sat(care)) * 2.0
        col *= 1 + (np.array([0.80, 0.78, 0.72]) - 1) * sat(foot * 0.5 * dk)[..., None]
        speck = (sr >= 0.993) * (1 - smooth(0.0, 2.5, v)) * inner
        col *= (1 - 0.35 * speck)[..., None]
        ageC = sat(0.3 + age / 12.0) * (1 - 0.5 * sat(care))
        crinkle_on = 1.0
    else:
        tk, dk = wear_split(age, care)
        # New Dacron is a bright, slightly cool white (optical brightener); the brightener and the white go with time.
        col *= (1 + 0.10 * (1 - tk))
        col *= 1 + (np.array([-0.012, -0.004, 0.02])) * (1 - tk)
        # Sun yellowing: Time, most at the leech and head (the shape the old fixed term had), never zero on an old sail.
        yel = tk * (0.45 + 0.55 * shape)
        col *= 1 + (np.array([1.0, 0.92, 0.76]) - 1) * (0.85 * yel)[..., None]
        # Dinge: Dirt greys and browns the whole cloth a little.
        dinge = 0.22 * dk
        col = col * (1 - dinge * 0.22) + np.array([0.034, 0.027, 0.015]) * dinge
        # Tan clay smudges where hands and the boom rub: slow blotches over a threshold that falls with Dirt.
        # Two octaves turned off the cloth's axes (a lone value noise reads as square blocks from the dock).
        ru, rv = 0.866 * u - 0.5 * v, 0.5 * u + 0.866 * v
        b1, _, _ = vnoise(ru / 0.22 + 5.3, rv / 0.22 + 1.7, 269.5, 183.3)
        b2, _, _ = vnoise((0.5 * u + 0.866 * v) / 0.08 + 2.9, (-0.866 * u + 0.5 * v) / 0.08 + 7.7, 269.5, 183.3)
        bl = 0.72 * b1 + 0.28 * b2 + 0.06
        sm = smooth(0.66 - 0.3 * dk, 0.88 - 0.15 * dk, bl) * dk
        sm *= 0.5 + 0.5 * (1 - smooth(0.3, 2.0, v))
        col *= 1 + (np.array([0.84, 0.81, 0.72]) - 1) * (0.9 * sm)[..., None]
        # Foot grime from the deck and flaking: Dirt.
        col *= 1 + (np.array([0.80, 0.76, 0.66]) - 1) * sat(foot * 0.45 * dk)[..., None]
        # Mildew specks: only on a boat left dirty; more of them, and higher up, the dirtier.
        # Real mildew is clusters of 1-4 mm black dots, not single centimetre spots: a fine speck grid (1.2 cm cells,
        # dots a third of a cell) thinned by a slow cluster noise, under the folds and low on the sail.
        mil = smooth(0.5, 0.95, dk)
        fi, fj = np.floor(u / 0.012), np.floor(v / 0.012)
        fr = hash2(fi, fj, 41.3, 289.1, 15731.7)
        jx, jy = hash2(fi, fj, 12.7, 77.3) - 0.5, hash2(fi, fj, 63.1, 21.9) - 0.5
        fin = np.hypot(u / 0.012 - fi - 0.5 - 0.6 * jx, v / 0.012 - fj - 0.5 - 0.6 * jy) <= 0.08 + 0.2 * (fr - 0.8) / 0.2
        cl, _, _ = vnoise(u / 0.18 + 9.1, v / 0.18 + 4.4, 269.5, 183.3)
        speck = (fr >= 1 - 0.2 * mil * smooth(0.6, 0.9, cl)) * (1 - smooth(0.0, 0.8 + 2.2 * dk, v)) * fin
        col *= (1 - 0.55 * speck)[..., None]
        col = col * (1 - 0.3 * speck[..., None]) + np.array([0.02, 0.022, 0.015]) * 0.3 * speck[..., None]
        # Sail tape repairs: a few rectangles on a used sail (white, glossier, a hair proud).
        ti, tj = np.floor(u / 1.1), np.floor(v / 0.9)
        th = hash2(ti, tj, 17.3, 91.1)
        tu, tv = u / 1.1 - ti, v / 0.9 - tj
        tape = (th < 0.22 * tk * (0.4 + dk)) * (np.abs(tu - 0.5) < 0.06) * (np.abs(tv - 0.45) < 0.04)
        col = np.where(tape[..., None], C * 1.12, col)
        rough = np.where(tape, 0.3, rough)
        # Resin loss: the finish wears off, the cloth goes soft and matt.
        rough = rough + 0.17 * tk + 0.06 * dk - 0.12 * (1 - tk)
        ageC = tk
        crinkle_on = sat(tk * 5.0)
    # Crinkle (SAIL_CODE's two octaves of folds in patches) and the flaking folds every 0.75 m.
    du = np.zeros(u.shape)
    dv = np.zeros(u.shape)
    patch, _, _ = vnoise(u / 0.4 + 3.7, v / 0.4 + 1.9, 269.5, 183.3)
    thC = 0.78 - 0.40 * ageC
    cover = smooth(thC - 0.12, thC + 0.12, patch) * crinkle_on
    sAmp = 0.08 * (0.5 + ageC)
    wd = 0.045
    crink = np.zeros(u.shape)
    for o, sC in enumerate((0.03, 0.012)):
        fadeC = 1 - smooth(0.08 * sC, 0.2 * sC, px)
        ca0, sa0 = (0.8290, 0.5592) if o == 0 else (0.2588, 0.9659)
        qx = (ca0 * u - sa0 * v) / sC + o * 7.31
        qy = (sa0 * u + ca0 * v) / sC + o * 7.31
        qx2 = qx + 0.4 * np.sin(qy * 0.61 + 1.3)
        qy2 = qy + 0.4 * np.sin(qx * 0.53 + 2.1)
        n, dqx, dqy = vnoise(qx2, qy2)
        dnx, dny = ca0 * dqx + sa0 * dqy, -sa0 * dqx + ca0 * dqy
        x = n - 0.5
        h = np.exp(-x * x / (wd * wd))
        ln = np.maximum(np.hypot(dnx, dny), 1e-4)
        fs = cover * fadeC * (1.0 if o == 0 else 0.6) * sAmp * (-2 * x / wd) * h
        du += fs * dnx / ln
        dv += fs * dny / ln
        crink = np.maximum(crink, cover * fadeC * h)
    yk = v / 0.75
    k = np.floor(yk + 0.5)
    jit = np.modf(np.sin(k * 91.7) * 4375.5)[0] % 1.0 - 0.5
    dy = (yk - k - 0.2 * jit) * 0.75
    st = 0.0018 * (0.35 + 0.65 * (0.5 + 0.5 * np.sin(u * 1.7 + k * 2.3))) * np.where(np.modf(k * 0.5)[0] % 1.0 > 0.25, 1.0, -0.7)
    w = 0.014
    dv += st * (-2 * dy / (w * w)) * np.exp(-dy * dy / (w * w))
    fold = np.exp(-dy * dy / (w * w)) * np.abs(st) / 0.0018
    col *= (1 - 0.05 * fold)[..., None]
    rough = np.minimum(rough + 0.08 * crink, 0.9)
    return np.clip(col, 0, 1), np.clip(rough, 0.05, 0.95), du, dv


def shade(col, rough, du, dv):
    """Overcast: a soft key from above and to the left, a broad sky fill, and a faint sheen that rough cloth loses."""
    n = np.stack([-du, -dv, np.ones_like(du)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    key = np.array([-0.35, 0.55, 0.76])
    key /= np.linalg.norm(key)
    ndl = np.clip(n @ key, 0, 1)
    light = 0.62 + 0.42 * ndl
    hv = key + np.array([0, 0, 1.0])
    hv /= np.linalg.norm(hv)
    spec = np.clip(n @ hv, 0, 1) ** (2.0 / np.maximum(rough, 0.05) ** 4) * 0.06 * (1 - rough)
    return col * light[..., None] + spec[..., None]


def sail_planform(age, care, mode, cm_per_px=2.0, luff=7.9, foot=2.9):
    s = cm_per_px / 100.0
    H, W = int(luff / s), int(foot / s)
    v = (H - 0.5 - np.arange(H))[:, None] * s * np.ones((1, W))
    u = (np.arange(W) + 0.5)[None, :] * s * np.ones((H, 1))
    chord = foot * (1 - v / luff)
    inside = u <= chord
    u2 = np.maximum(chord - u, 0)
    col, rough, du, dv = cloth(u, v, u2, v / luff, age, care, mode, s)
    img = shade(col, rough, du, dv)
    return img, inside, col, rough


def closeup(age, care, mode, size_m=0.6, mm_per_px=1.0, origin=(1.9, 0.15)):
    """A square of cloth near the clew (1.9 m along the foot, 15 cm up): where the grime, specks and crinkle show."""
    s = mm_per_px / 1000.0
    N = int(size_m / s)
    v = origin[1] + (N - 0.5 - np.arange(N))[:, None] * s * np.ones((1, N))
    u = origin[0] + (np.arange(N) + 0.5)[None, :] * s * np.ones((N, 1))
    u2 = np.maximum(2.9 * (1 - v / 7.9) - u, 0)
    col, rough, du, dv = cloth(u, v, u2, v / 7.9, age, care, mode, s)
    return shade(col, rough, du, dv), col, rough


def to_srgb8(lin):
    lin = np.clip(lin, 0, 1)
    s = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)
    return (s * 255 + 0.5).astype(np.uint8)


def main(out):
    from PIL import Image
    sys.path.insert(0, HERE)
    os.makedirs(out, exist_ok=True)
    stats = {}
    for mode in ("before", "after"):
        for name, (age, care) in levels().items():
            img, inside, col, rough = sail_planform(age, care, mode)
            rgba = np.dstack([to_srgb8(img), (inside * 255).astype(np.uint8)])
            Image.fromarray(rgba, "RGBA").save(os.path.join(out, f"sail_{mode}_{name}.png"))
            cu, ccol, crough = closeup(age, care, mode)
            Image.fromarray(to_srgb8(cu)).save(os.path.join(out, f"close_{mode}_{name}.png"))
            from sailcloth_lab import lin_to_lab
            lab = lin_to_lab(col[inside])
            labc = lin_to_lab(ccol.reshape(-1, 3))
            stats.setdefault(mode, {})[name] = {
                "age": age, "care": care,
                "lab_mean": [round(float(x), 2) for x in lab.mean(0)], "lab_sd": [round(float(x), 2) for x in lab.std(0)],
                "clew_lab_mean": [round(float(x), 2) for x in labc.mean(0)], "clew_lab_sd": [round(float(x), 2) for x in labc.std(0)],
                "rough_mean": round(float(rough[inside].mean()), 3),
                "wear": dict(zip(("time", "dirt"), wear_split(age, care))) if mode == "after" else None,
            }
    json.dump(stats, open(os.path.join(out, "stats.json"), "w"), indent=1)
    return stats


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1] if len(sys.argv) > 1 else "out"), indent=1))
