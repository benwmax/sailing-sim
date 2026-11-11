"""Non-skid wear ladder, rendered from the same maths as M_BoatSurface (texture loop steps 5-6, numpy stand-in).

    python3 Tools/texloop/nonskid/render_levels.py <out dir> [--maps Inputs/boat-detail] [--before <dir of old maps>]

For each wear level L0-L4 (Tools/texloop/refs/nonskid.json) it shades a 20 cm close-up (4 px/mm) and a 1 m swatch under
an overcast sky and a low sun, with the shader's own three-octave grime noise, then measures them the way
measure_photos.py measures the photos: Lab relative to a flat white gelcoat of sRGB 215 under the same light, the spread
of L*, and how much is more than 6 L* darker than the median. --before renders today's main (2.5 mm pyramids, the 8 mm
diamond, one dirt number) for the before/after sheet. The per-level numbers in AFTER mirror the HLSL in BOAT_CODE's
non-skid lines; change both together.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
ARGS = sys.argv[1:]
OUT = ARGS[0] if ARGS and not ARGS[0].startswith("--") else os.path.join(ROOT, "Artifacts", "texloop", "nonskid")
MAPS = ARGS[ARGS.index("--maps") + 1] if "--maps" in ARGS else os.path.join(ROOT, "Inputs", "boat-detail")
BEFORE = ARGS[ARGS.index("--before") + 1] if "--before" in ARGS else None
REFS = json.load(open(os.path.join(ROOT, "Tools", "texloop", "refs", "nonskid.json")))
LEVELS = ["L0", "L1", "L2", "L3", "L4"]
TILE_MM = 100.0
C_NONSKID = np.array([0.56, 0.52, 0.43])          # MI_Boat_NonSkid's colour before the texture loop (BOAT_LIBRARY)


# ------------------------------------------------------------------ wear numbers
sys.path.insert(0, os.path.join(ROOT, "Tools", "texloop"))
import wear  # noqa: E402  (Tools/texloop/wear.py: the same formulas as BOAT_CODE)


def time_k(age, care=1.0):
    return wear.time_k(age, care)


def dirt_k(age, care):
    return wear.dirt_k(age, care)


def age_k(age, care):                              # before the split
    return wear.age_k(age, care)


def dirt_today(age, care):                         # the grime weight before the split
    return wear.grime(age, care, split=False)


# ------------------------------------------------------------------ helpers
def srgb2lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin2srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def lin2lab(rgb):
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = rgb @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(np.maximum(xyz, 0)), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def load(path):
    a = np.asarray(Image.open(path).convert("RGB"), float) / 255.0
    return a


def hash2(ix, iy, k=(12.99, 78.23)):
    return np.modf(np.abs(np.sin(ix * k[0] + iy * k[1]) * 43758.5))[0]


def value_noise(xcm, ycm, wear_scale=1.0, turned=True):
    """The shader's grime noise: three octaves at 37, 9 and 2.2 cm (BOAT_CODE, vn). #405: each octave's lattice is turned
    (37, 74, 111 deg) and smoothed quintically, and WearScale sizes it to the boat (0.7 on the dinghies); turned=False is
    the axis-aligned, cubic noise of main before #405 (the --before render)."""
    vn, amp, sc = 0.0, 0.6, 37.0 * wear_scale
    for o in range(3):
        ang = 0.6458 * (o + 1) if turned else 0.0
        rx, ry = xcm * math.cos(ang) - ycm * math.sin(ang), xcm * math.sin(ang) + ycm * math.cos(ang)
        qx, qy = rx / sc + o * 17.3, ry / sc + o * 17.3
        ix, iy = np.floor(qx), np.floor(qy)
        fx, fy = qx - ix, qy - iy
        if turned:
            fx, fy = fx * fx * fx * (fx * (fx * 6 - 15) + 10), fy * fy * fy * (fy * (fy * 6 - 15) + 10)
        else:
            fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        a00, a10, a01, a11 = hash2(ix, iy), hash2(ix + 1, iy), hash2(ix, iy + 1), hash2(ix + 1, iy + 1)
        vn = vn + amp * ((a00 * (1 - fx) + a10 * fx) * (1 - fy) + (a01 * (1 - fx) + a11 * fx) * fy)
        amp *= 0.5
        sc /= 4.1
    return vn / 1.05


def value_noise1(qx, qy):
    ix, iy = np.floor(qx), np.floor(qy)
    fx, fy = qx - ix, qy - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a00, a10, a01, a11 = hash2(ix, iy), hash2(ix + 1, iy), hash2(ix, iy + 1), hash2(ix + 1, iy + 1)
    return (a00 * (1 - fx) + a10 * fx) * (1 - fy) + (a01 * (1 - fx) + a11 * fx) * fy


def smoothstep(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def sample(tex, px_per_mm, size_px, ox_mm=0.0, oy_mm=0.0):
    """Tile tex (TILE_MM square) at px_per_mm, box-filtered down from the texture's own density."""
    res = tex.shape[0]
    tex_ppm = res / TILE_MM
    step = tex_ppm / px_per_mm
    if step > 1.01:                                 # minify: box filter to the output density first (a mip)
        k = int(round(step))
        r2 = res // k * k
        t = tex[:r2, :r2].reshape(r2 // k, k, r2 // k, k, -1).mean((1, 3))
        res, tex_ppm, step = t.shape[0], t.shape[0] / TILE_MM, t.shape[0] / TILE_MM / px_per_mm
        tex = t
    ys = (np.arange(size_px) + 0.5) * step + oy_mm * tex_ppm
    xs = (np.arange(size_px) + 0.5) * step + ox_mm * tex_ppm
    iy, ix = np.floor(ys).astype(int) % res, np.floor(xs).astype(int) % res
    fy, fx = (ys - np.floor(ys))[:, None, None], (xs - np.floor(xs))[None, :, None]
    iy1, ix1 = (iy + 1) % res, (ix + 1) % res
    return (tex[iy][:, ix] * (1 - fx) + tex[iy][:, ix1] * fx) * (1 - fy) + (tex[iy1][:, ix] * (1 - fx) + tex[iy1][:, ix1] * fx) * fy


# ------------------------------------------------------------------ the surface
AFTER = {
    # pigment (linear): the clean moulded beige, L0's target next to a white gelcoat of 215
    "pigment": None,
    "yellow": (1.0, 0.975, 0.90),       # Time: gelcoat yellowing, up to half of it at timeK 1
    "dirt_col": (0.205, 0.198, 0.178),   # grey-tan lake dust and clay (foot path hue, photo 1000032822)
    "mildew_col": (0.025, 0.026, 0.022),
    "grit_col": (0.11, 0.105, 0.09),
}


def pigment_from_target():
    L, a, b = REFS["targets"]["L0"]["lab"]
    # invert Lab -> linear sRGB (D65), then scale to sit next to white 215 the way the photos were measured
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200
    inv = lambda f: f ** 3 if f ** 3 > 0.008856 else (f - 16 / 116) / 7.787
    xyz = np.array([inv(fx) * 0.95047, inv(fy), inv(fz) * 1.08883])
    m = np.linalg.inv(np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]))
    return np.clip(m @ xyz, 0, 1)


def shade_after(M, vn, scuff, spk, spk2, age, care, detail=True):
    """Albedo and roughness of M_BoatSurface's non-skid after the texture loop: the same steps, in the same order, as
    BOAT_CODE (shared grime line, the non-skid block after it, then the surf == 2 detail branch)."""
    tk, dk = time_k(age), dirt_k(age, care)
    pig = AFTER["pigment"]
    dcol = np.array(AFTER["dirt_col"])
    col = np.broadcast_to(pig, M.shape[:2] + (3,)).copy()
    # shared grime (deckish 1, NonSkid 1), then the faint mottle
    grime = np.clip(vn * 1.4 - 0.4, 0, 1)[..., None] * dk      # #405: softer edge (was x1.8 - 0.6)
    col = col + (col * 0.76 + np.array([0.014, 0.011, 0.007]) - col) * grime
    rough = 0.66 + (min(0.66 + 0.18, 0.9) - 0.66) * grime[..., 0]
    col = col * (1 + 0.05 * (vn[..., None] - 0.5))
    # non-skid block: yellowing, blotches with the scuff mottle, Medium's even dust
    col = col * (1 + (np.array(AFTER["yellow"]) - 1) * 0.5 * tk)
    blot = (np.clip((vn - 0.60 + 0.22 * dk) * 1.8, 0, 1) * smoothstep(0.2, 0.6, dk) * (0.35 + 1.3 * scuff))[..., None]
    col = col + (dcol - col) * np.clip((0.3 + 0.45 * dk) * blot, 0, 1)
    if not detail:
        col = col + (dcol - col) * 0.55 * math.sqrt(dk) * 0.35
    rough = rough + (np.minimum(rough + 0.1, 0.9) - rough) * blot[..., 0]
    if detail:                                     # surf == 2 detail branch (fadeD 1 at these distances)
        mr, mg = M[..., 0:1], M[..., 1:2]
        cav = 1 - mr
        col = col * (0.80 + 0.24 * mr)
        col = col + (dcol - col) * 0.55 * math.sqrt(dk) * cav
        grit = (spk2[..., None] > 1 - 0.30 * dk) * (1 - 0.6 * mr)
        col = col + (np.array(AFTER["grit_col"]) - col) * 0.6 * grit
        mil = (spk[..., None] > 1 - 0.12 * max(0.0, min(1.0, dk * 2.2 - 1.2))) * cav
        col = col + (np.array(AFTER["mildew_col"]) - col) * 0.85 * mil
        top = mg * min(1.0, tk * 1.5)
        col = col + ((col + pig) * 0.5 * 1.05 - col) * top
        rough = np.clip(rough + 0.12 * cav[..., 0] - 0.15 * mg[..., 0] + 0.2 * dk * cav[..., 0] - 0.18 * top[..., 0], 0, 1)
    return col, rough


def shade_before(M, vn, age, care, ppm):
    """Today's main: one ageK and one dirt number (BOAT_CODE before the texture loop)."""
    ak, dt = age_k(age, care), dirt_today(age, care)
    col = np.broadcast_to(C_NONSKID, M.shape[:2] + (3,)).copy()
    col = col + (col * 0.78 + 0.02 - col) * ak * 0.7          # 'worn, grimy non-skid' (wear.x stands in for ageK)
    grime = np.clip(vn * 1.8 - 0.6, 0, 1)[..., None] * dt
    col = col + (col * 0.76 + np.array([0.014, 0.011, 0.007]) - col) * grime
    col = col * (1 + 0.05 * (vn[..., None] - 0.5))
    col = col * (0.70 + 0.2 * (1 - dt) + (1.06 - 0.70 - 0.2 * (1 - dt)) * M[..., 0:1])
    rough = np.clip(0.66 + 0.18 * grime[..., 0] + 0.12 * (1 - M[..., 0]) - 0.15 * M[..., 1], 0, 1)
    return col, rough


def diamond8_normal(size_px, ppm):
    """The 8 mm analytic diamond every tier draws today (BOAT_CODE grad, 0.35 * NonSkid)."""
    k = 2 * math.pi / 8.0
    x = (np.arange(size_px) + 0.5) / ppm
    X, Y = np.meshgrid(x, x)
    gx, gy = np.cos(X * k) * np.sin(Y * k), np.sin(X * k) * np.cos(Y * k)
    return 0.35 * gx, 0.35 * gy


def light(nrm, cav, rough, sun):
    """Overcast: sky over the hemisphere with the grooves occluded. Sun: 20 degrees up, plus sky fill."""
    nz = np.clip(nrm[..., 2], 0, 1)
    ao = 1.0                    # the game has no AO at this scale; the albedo carries the grooves' shade
    if not sun:
        return (0.55 + 0.45 * nz) * ao
    s = np.array([math.cos(math.radians(20)) * math.cos(math.radians(225)), math.cos(math.radians(20)) * math.sin(math.radians(225)), math.sin(math.radians(20))])
    lam = np.clip(nrm @ s, 0, None) / s[2]
    return 0.35 * (0.55 + 0.45 * nz) * ao + 0.65 * lam * (0.9 + 0.1 * (1 - rough))


def render(level, ppm, size_px, maps, before=False, sun=False, seed=7):
    age, care = REFS["targets"][level]["age_care"]
    N, M = maps
    Ns, Ms = sample(N, ppm, size_px), sample(M, ppm, size_px)
    xcm = (np.arange(size_px) + 0.5) / ppm / 10.0 + 120.0
    X, Y = np.meshgrid(xcm, xcm + 40.0)
    vn = value_noise(X, Y, turned=not before)
    nrm = Ns * 2 - 1
    if before:
        dx, dy = diamond8_normal(size_px, ppm)
        nrm = nrm + np.stack([-dx, dy, np.zeros_like(dx)], -1)
        col, rough = shade_before(Ms, vn, age, care, ppm)
    else:
        spk = hash2(np.floor(X * 10 / 1.2), np.floor(Y * 10 / 1.2), (19.3, 47.9))   # 1.2 mm speckle cells
        scuff = value_noise1(X / 1.5 + 11.0, Y / 1.5)            # one octave, 1.5 cm: scuff trails
        scuff = np.clip((scuff - 0.5) * 1.6 + 0.5, 0, 1)
        spk2 = hash2(np.floor(X * 10 / 0.9), np.floor(Y * 10 / 0.9), (27.1, 61.7))  # 0.9 mm grit cells
        col, rough = shade_after(Ms, vn, scuff, spk, spk2, age, care)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    lit = col * light(nrm, Ms[..., 0], rough, sun)[..., None]
    white = srgb2lin(np.array(215 / 255.0)) * light(np.array([[[0, 0, 1.0]]]), np.ones((1, 1)), np.full((1, 1), 0.3), sun)[0, 0]
    return lit, white


def measure(lit, white):
    lab = lin2lab(np.clip(lit / white * srgb2lin(np.array(215 / 255.0)), 0, 1))
    L = lab[..., 0]
    return {"lab": [round(float(v), 1) for v in lab.reshape(-1, 3).mean(0)], "L_std": round(float(L.std()), 1),
            "dark_cover": round(float((L < np.median(L) - 6).mean()), 3)}


def to_img(lit, white, gain=1.0):
    return Image.fromarray((lin2srgb(lit / white * srgb2lin(np.array(215 / 255.0)) * gain) * 255 + 0.5).astype(np.uint8))


def main():
    os.makedirs(OUT, exist_ok=True)
    AFTER["pigment"] = pigment_from_target()
    sets = [("after", (load(os.path.join(MAPS, "T_Detail_NonSkid_N.png")), load(os.path.join(MAPS, "T_Detail_NonSkid_M.png"))), False)]
    if BEFORE:
        sets.insert(0, ("before", (load(os.path.join(BEFORE, "T_Detail_NonSkid_N.png")), load(os.path.join(BEFORE, "T_Detail_NonSkid_M.png"))), True))
    report = {}
    maps_after = sets[-1][1]
    for _ in range(3):                  # calibrate the pigment so the clean L0 swatch sits on its L*
        lit, white = render("L0", 1.0, 400, maps_after)
        L = measure(lit, white)["lab"][0]
        AFTER["pigment"] = AFTER["pigment"] * ((REFS["targets"]["L0"]["lab"][0] + 16) / (L + 16)) ** 3
    report["pigment_linear"] = [round(float(v), 4) for v in AFTER["pigment"]]
    for name, maps, before in sets:
        for lv in LEVELS:
            r = {}
            for view, ppm, size in (("close", 4.0, 800), ("swatch", 1.0, 1000)):
                for sun in (False, True):
                    lit, white = render(lv, ppm, size, maps, before, sun)
                    tag = f"{name}_{lv}_{view}_{'sun' if sun else 'overcast'}"
                    to_img(lit, white).save(os.path.join(OUT, tag + ".png"))
                    if not sun:
                        r[view] = measure(lit, white)
            t = REFS["targets"][lv]
            r["dE_swatch"] = round(float(np.linalg.norm(np.array(r["swatch"]["lab"]) - np.array(t["lab"]))), 1)
            r["time_k"], r["dirt_k"], r["age_k_today"] = round(time_k(*t["age_care"][:1]), 3), round(dirt_k(*t["age_care"]), 3), round(age_k(*t["age_care"]), 3)
            report[f"{name}_{lv}"] = r
            print(name, lv, r["swatch"], "dE", r["dE_swatch"], "target", t["lab"], t.get("L_std", t.get("L_std_max")), t.get("dark_cover", t.get("dark_cover_max")))
    json.dump(report, open(os.path.join(OUT, "measure.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
