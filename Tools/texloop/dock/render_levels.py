"""Render the club docks' surfaces at the five wear levels (docs/texloop-dock): deck boards, a float with its rub strip
at the waterline, a piling through the water, and the launch ramp. The surface colours come from M_WorldSurface's own
HLSL (hlsl_np.py runs it on numpy), lit by the texture loop's image-based renderer (Tools/texloop/render_swatch.py: the
engine's split-sum shading under Poly Haven's CC0 overcast sky).

    python Tools/texloop/dock/render_levels.py [--rev main] [--out DIR] [--tag new]

--rev renders the shader at a git revision (the "before"); without it the working tree. Writes <out>/<tag>_<L>.png,
one 2x2 panel per level, and <out>/<tag>_<L>_<scene>.png.
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import hlsl_np as H  # noqa: E402
import render_swatch as RS  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
LV = {"L0": (0.0, 1.0), "L1": (0.3, 0.9), "L2": (6.0, 0.5), "L3": (30.0, 0.9), "L4": (20.0, 0.1)}
# MI_World_* (scripts/make_materials.py WORLD_LIBRARY): colour, roughness, pattern
LOOK_NEW = {"Decking": ((0.42, 0.40, 0.36), 0.85, 1.0), "Floats": ((0.025, 0.025, 0.024), 0.55, 11.0),
            "Pilings": ((0.32, 0.27, 0.21), 0.9, 9.0), "Concrete": ((0.62, 0.60, 0.56), 0.85, 4.0)}
LOOK_OLD = dict(LOOK_NEW, Floats=((0.05, 0.05, 0.05), 0.6, 0.0))
OPEN = {1.0: "if (Pattern > 0.5 && Pattern < 1.5)", 9.0: "else if (Pattern > 8.5 && Pattern < 9.5)",
        11.0: "else if (Pattern > 10.5 && Pattern < 11.5)", 4.0: "else if (Pattern > 3.5 && Pattern < 4.15)"}
WATER = np.array([0.045, 0.055, 0.04])   # Lake Ray Hubbard: turbid green-brown


def surface(code, look, uv, wp, level, flag=0.0, sun=0.6, wetM=0.6):
    """Run one MI_World_* look's pattern on uv (H, W, 2 metres) and wp (H, W, 3 cm): colour, roughness, tangent bump."""
    col, rough, pat = look
    age, care = LV[level]
    hgt, wid = uv.shape[:2]
    one = np.ones((hgt, wid, 1))
    p = uv * 0.7
    i0 = np.floor(p); f0 = H.smoothstep(0.0, 1.0, p - i0)
    hh = lambda o: H.frac(np.sin((i0 + o) @ np.array([12.99, 78.23]))[..., None] * 43758.5)
    blot = H.lerp(H.lerp(hh((0, 0)), hh((1, 0)), f0[..., :1]), H.lerp(hh((0, 1)), hh((1, 1)), f0[..., :1]), f0[..., 1:])
    n = H.frac(np.sin(np.floor(uv * 7.0) @ np.array([12.9898, 78.233]))[..., None] * 43758.5453)
    env = dict(uv=uv, WP=wp, UV1=np.array([0.0, -1000.0 - flag]), Color=np.array(col), c=np.array(col) * one, r=rough * one,
               Pattern=pat, n=n, blot=blot, bump=np.zeros((hgt, wid, 3)), age=age, care=care, sun=sun, wetM=wetM, site=0.0,
               salt=0.0, aged=min(age / 25.0, 1.0), zw=wp[..., 2:3] * 0.01, variant=0.0, Metal=0.0, Met=0.0, Windows=0.0,
               dkT=float(np.clip(0.25 * (1 - math.exp(-age / 0.75)) + 0.75 * (1 - math.exp(-age / 18.0)), 0, 1)),
               dkD=float(np.clip((1 - math.exp(-age)) * (0.15 + 0.85 * (1 - care)), 0, 1)))
    env["UV1"] = np.broadcast_to(env["UV1"], (hgt, wid, 2))
    if pat in OPEN and OPEN[pat] in code:
        ns = H.run(H.branch(code, OPEN[pat]), env)
        return ns["c"], ns["r"][..., 0], ns["bump"]
    return env["c"], env["r"][..., 0], env["bump"]


def perturb(nrm, t, b, bump):
    tn = H.normalize(np.concatenate([-bump[..., :1], -bump[..., 1:2], np.ones_like(bump[..., :1])], -1))
    out = t * tn[..., :1] + b * tn[..., 1:2] + nrm * tn[..., 2:3]
    return out / np.linalg.norm(out, axis=-1, keepdims=True)


def cam_rays(w, h, fov, pitch_deg, yaw_deg=0.0):
    """Camera looking along +Y rotated: pitch down by pitch_deg. Returns per-pixel world directions."""
    f = 0.5 * w / math.tan(math.radians(fov) / 2)
    x = (np.arange(w) + 0.5 - w / 2)
    y = (np.arange(h) + 0.5 - h / 2)
    X, Y = np.meshgrid(x, y)
    d = np.stack([X, np.full_like(X, f), -Y], -1)
    p = math.radians(pitch_deg)
    R = np.array([[1, 0, 0], [0, math.cos(p), -math.sin(p)], [0, math.sin(p), math.cos(p)]])
    d = d @ R.T
    return d / np.linalg.norm(d, axis=-1, keepdims=True)


def light(sky, col, rough, nrm, view, exposure):
    g = {"n": nrm, "v": view}
    return RS.shade(g, sky, col, rough, np.zeros_like(rough), exposure)


def water_over(img, sky, depth, view, exposure):
    """The lake over anything below the water: turbid (a quarter metre to fade), with the sky's reflection."""
    a = (1.0 - np.exp(-np.maximum(depth, 0.0) / 0.22))[..., None] * (depth > 0)[..., None]
    a = np.where(depth[..., None] > 0, np.maximum(a, 0.35), 0.0)
    nup = np.zeros_like(view); nup[..., 2] = 1.0
    wcol = light(sky, WATER * np.ones_like(img), np.full(img.shape[:2], 0.08), nup, view, exposure)
    return img * (1 - a) + wcol * a


def scene_deck(code, look, level, sky, exposure, w=640, h=480):
    d = cam_rays(w, h, 50, -42)
    eye = np.array([0.6, -1.1, 1.6])          # standing on the dock, looking along it
    t = eye[2] / np.maximum(-d[..., 2], 1e-4)
    p = eye + d * t[..., None]
    uv = np.stack([p[..., 0] + 1.0, p[..., 1] + 3.0], -1)
    wp = np.concatenate([p[..., :2] * 100, np.full(p.shape[:2] + (1,), 45.0)], -1)
    c, r, bump = surface(code, look, uv, wp, level)
    nrm = perturb(np.array([0, 0, 1.0]) * np.ones_like(p), np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), bump)
    return light(sky, c, r, nrm, -d, exposure)


def scene_float(code, looks, level, sky, exposure, w=640, h=480):
    """A floating dock's edge, side on from a boat: the float (to 0.33 m), its rub strip (0.29-0.43) and the deck edge."""
    d = cam_rays(w, h, 40, -6)
    eye = np.array([0.8, -2.2, 0.55])
    t = (0.0 - eye[1]) / np.maximum(d[..., 1], 1e-4)
    p = eye + d * t[..., None]
    x, z = p[..., 0] + 5.0, p[..., 2]
    out = np.zeros(p.shape)
    nrm = np.array([0, -1.0, 0]) * np.ones_like(p)
    view = -d
    for name, z0, z1 in (("Floats", -0.35, 0.29), ("FloatsStrip", 0.29, 0.43), ("Decking", 0.43, 0.45)):
        lk = looks["Floats" if name.startswith("Floats") else name]
        uv = np.stack([x, z - z0], -1)
        wp = np.stack([x * 100, np.zeros_like(x), z * 100], -1)
        c, r, bump = surface(code, lk, uv, wp, level)
        n2 = perturb(nrm, np.array([1.0, 0, 0]), np.array([0, 0, 1.0]), bump)
        lit = light(sky, c, r, n2, view, exposure)
        m = ((z >= z0) & (z < z1))[..., None]
        out = np.where(m, lit, out)
    top = (z >= 0.45)[..., None]
    sky_bg = sky.specular(d, np.full(z.shape, 0.05)) * exposure
    out = np.where(top, sky_bg * 0.9, out)
    return water_over(out, sky, -z, view, exposure)


def scene_piling(code, look, level, sky, exposure, w=480, h=640):
    d = cam_rays(w, h, 45, -8)
    eye = np.array([0.0, -2.0, 0.9])
    # ray vs vertical cylinder radius 0.17 at the origin
    R = 0.17
    a = d[..., 0] ** 2 + d[..., 1] ** 2
    bq = 2 * (eye[0] * d[..., 0] + eye[1] * d[..., 1])
    cq = eye[0] ** 2 + eye[1] ** 2 - R * R
    disc = bq * bq - 4 * a * cq
    hit = disc > 0
    t = (-bq - np.sqrt(np.maximum(disc, 0))) / (2 * a)
    p = eye + d * t[..., None]
    ang = np.arctan2(p[..., 1], p[..., 0])
    uv = np.stack([ang * R + 3.0, p[..., 2] + 3.0], -1)
    wp = p * 100.0
    c, r, bump = surface(code, look, uv, wp, level)
    nrm = np.stack([p[..., 0], p[..., 1], np.zeros_like(ang)], -1) / R
    tng = np.stack([-np.sin(ang), np.cos(ang), np.zeros_like(ang)], -1)
    n2 = perturb(nrm, tng, np.array([0, 0, 1.0]), bump)
    lit = light(sky, c, r, n2, -d, exposure)
    # behind: the lake to the horizon
    bg_w = water_over(np.zeros_like(lit), sky, np.full(hit.shape, 9.0), -d, exposure)
    bg = np.where((d[..., 2] < 0)[..., None], bg_w, sky.specular(d, np.full(hit.shape, 0.05)) * exposure)
    out = np.where(hit[..., None], water_over(lit, sky, -p[..., 2], -d, exposure), bg)
    return out


def scene_ramp(code, look, level, sky, exposure, w=640, h=480):
    """Standing on the launch ramp 6 m above its foot, looking down it to the water (5.7 deg slope)."""
    d = cam_rays(w, h, 55, -48)
    slope = 1.8 / 18.0
    top = 0.4
    U0 = 1.0
    eye = np.array([2.5, U0, top - slope * U0 + 1.7])   # x across (V), y down the ramp (U)
    # plane z = top - slope * y  ->  eye.z + t dz = top - slope (eye.y + t dy)
    t = (top - slope * eye[1] - eye[2]) / np.minimum(d[..., 2] + slope * d[..., 1], -1e-4)
    p = eye + d * t[..., None]
    uv = np.stack([p[..., 1], p[..., 0]], -1)
    wp = np.stack([p[..., 0] * 100, p[..., 1] * 100, p[..., 2] * 100], -1)
    c, r, bump = surface(code, look, uv, wp, level, flag=4.0)
    nrm = np.array([0, slope, 1.0]) / math.hypot(1, slope) * np.ones_like(p)
    n2 = perturb(nrm, np.array([0, 1.0, -slope]) / math.hypot(1, slope), np.array([1.0, 0, 0]), bump)
    lit = light(sky, c, r, n2, -d, exposure)
    side = (p[..., 0] < 0) | (p[..., 0] > 5.0)
    lit = np.where(side[..., None], light(sky, np.array([0.16, 0.14, 0.10]) * np.ones_like(p), np.full(p.shape[:2], 0.95), nrm, -d, exposure), lit)
    far = t > 60
    lit = np.where(far[..., None], 0, lit)
    return water_over(lit, sky, -p[..., 2], -d, exposure)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rev")
    ap.add_argument("--out", default=os.path.join(REPO, "Artifacts", "texloop", "dock"))
    ap.add_argument("--tag", default="new")
    ap.add_argument("--levels", default="L0,L1,L2,L3,L4")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    code = H.world_code(a.rev)
    looks = LOOK_OLD if a.rev else LOOK_NEW
    sky = RS.Sky(RS.load_env())
    ncard = np.array([0.0, -1.0, 0.25]); ncard /= np.linalg.norm(ncard)
    e_card = float((sky.irradiance(ncard[None, None, :])[0, 0] * 0.18).mean())
    exposure = 0.18 / max(e_card, 1e-6) * 0.8
    for lv in a.levels.split(","):
        imgs = {
            "deck": scene_deck(code, looks["Decking"], lv, sky, exposure),
            "float": scene_float(code, looks, lv, sky, exposure),
            "piling": scene_piling(code, looks["Pilings"], lv, sky, exposure),
            "ramp": scene_ramp(code, looks["Concrete"], lv, sky, exposure),
        }
        tiles = {}
        for k, im in imgs.items():
            px = (RS.to_srgb(RS.aces(np.nan_to_num(im))) * 255).astype(np.uint8)
            tiles[k] = Image.fromarray(px)
            tiles[k].save(os.path.join(a.out, f"{a.tag}_{lv}_{k}.png"))
        sheet = Image.new("RGB", (640 * 2 + 360, 480 * 2), (30, 30, 30))
        sheet.paste(tiles["deck"], (0, 0)); sheet.paste(tiles["float"], (640, 0))
        sheet.paste(tiles["ramp"], (0, 480)); sheet.paste(tiles["piling"].resize((360, 480)), (1280, 240))
        sheet.paste(Image.new("RGB", (640, 480), (30, 30, 30)), (640, 480))
        sheet.paste(tiles["piling"].resize((360, 480)), (640 + 140, 480))
        sheet = Image.new("RGB", (640 * 2, 480 * 2), (30, 30, 30))
        sheet.paste(tiles["deck"], (0, 0)); sheet.paste(tiles["float"], (640, 0)); sheet.paste(tiles["ramp"], (0, 480))
        sheet.paste(tiles["piling"].resize((360, 480)), (640 + 140, 480))
        sheet.save(os.path.join(a.out, f"{a.tag}_{lv}.png"))
        print(a.tag, lv, "done")


if __name__ == "__main__":
    main()
