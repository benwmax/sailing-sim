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
C_NONSKID = np.array([0.56, 0.52, 0.43])          # MI_Boat_NonSkid's colour (make_materials.py BOAT_MATERIALS)


# ------------------------------------------------------------------ wear numbers
def time_k(age):
    """Provisional Time (care can't undo it); replaced by Tools/texloop/wear.py when the shared PR lands."""
    return min(1.0, 0.25 * (1 - math.exp(-age / 0.5)) + 0.75 * min(age / 30.0, 1.0))


def dirt_k(age, care):
    """Provisional Dirt (care removes it): mostly (1 - care), quick start in the first months."""
    return (1 - 0.85 * care) * (1 - math.exp(-age / 0.4)) * min(1.0, 0.35 + age / 15.0)


def age_k(age, care):                              # today's single number
    return min(age / 20.0, 1.0) * (1 - 0.6 * care)


def dirt_today(age, care):                         # today's grime weight
    return min(1.0, 0.15 + age / 18.0) * (1 - 0.65 * care)


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


def value_noise(xcm, ycm):
    """The shader's grime noise: three octaves at 37, 9 and 2.2 cm (BOAT_CODE, vn)."""
    vn, amp, sc = 0.0, 0.6, 37.0
    for o in range(3):
        qx, qy = xcm / sc + o * 17.3, ycm / sc + o * 17.3
        ix, iy = np.floor(qx), np.floor(qy)
        fx, fy = qx - ix, qy - iy
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


def shade_after(M, vn, scuff, spk, spk2, age, care):
    """Albedo and roughness of the new non-skid lines (mirrors BOAT_CODE surf == 2 and the grime line)."""
    tk, dk = time_k(age), dirt_k(age, care)
    cav, polish = M[..., 0:1], M[..., 1:2]
    col = AFTER["pigment"] * (1 + (np.array(AFTER["yellow"]) - 1) * 0.5 * tk)
    # blotches where feet and water go: the shader's grime noise, wider and darker as Dirt grows
    # plus a fine scuff mottle (1.5 cm) that only shows where the blotches are
    blot = np.clip((vn[..., None] - 0.60 + 0.22 * dk) * 3.0, 0, 1) * smoothstep(0.2, 0.6, dk)
    blot = blot * (0.35 + 1.3 * scuff[..., None])
    col = col + (np.array(AFTER["dirt_col"]) - col) * np.clip((0.3 + 0.45 * dk) * blot, 0, 1)
    # dust and grime packed in the grooves (cavity R: 0 deep in a groove)
    groove = (1 - cav) * min(1.0, math.sqrt(dk))
    col = col + (np.array(AFTER["dirt_col"]) - col) * 0.55 * groove
    # Time polishes the rib tops: the grime wears off them and they go a touch lighter and smoother
    top = polish * min(1.0, tk * 1.5)
    col = col * (1 + 0.05 * top) - (col - AFTER["pigment"]) * 0.5 * top
    # grit: dark specks of packed dirt (0.5-2 mm) caught in the grooves, more as Dirt grows
    grit = (spk2[..., None] > 1 - 0.30 * dk) * (1 - cav * 0.6)
    col = col + (np.array(AFTER["grit_col"]) - col) * 0.6 * grit
    # neglect: black mildew specks in the grooves
    mil = (spk[..., None] > 1 - 0.12 * max(0.0, dk * 2.2 - 1.2)) * (1 - cav)
    col = col + (np.array(AFTER["mildew_col"]) - col) * 0.85 * mil
    rough = np.clip(0.6 + 0.2 * dk * (1 - cav[..., 0]) + 0.1 * blot[..., 0] - 0.18 * top[..., 0], 0, 1)
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
    ao = 0.78 + 0.22 * cav
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
    vn = value_noise(X, Y)
    nrm = Ns * 2 - 1
    if before:
        dx, dy = diamond8_normal(size_px, ppm)
        nrm = nrm + np.stack([-dx, dy, np.zeros_like(dx)], -1)
        col, rough = shade_before(Ms, vn, age, care, ppm)
    else:
        spk = hash2(np.floor(X * 10 / 1.2), np.floor(Y * 10 / 1.2), (19.3, 47.9))   # 1.2 mm speckle cells
        scuff = value_noise1(X / 1.5 + 11.0, Y / 1.5)            # one octave, 1.5 cm: scuff trails
        scuff = np.clip((scuff - 0.5) * 1.6 + 0.5, 0, 1)
        spk2 = hash2(np.floor(X * 10 / 0.9) + 3.0, np.floor(Y * 10 / 0.9), (27.1, 61.7))  # 0.9 mm grit cells
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
