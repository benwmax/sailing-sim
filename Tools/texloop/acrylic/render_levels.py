"""Render smoked acrylic glazing at the five wear levels (docs/texloop-acrylic), the same view every round.

    python Tools/texloop/acrylic/render_levels.py [--out Artifacts/texloop/acrylic] [--before] [--px 640]

The scene: the corner of a cabin trunk in white gelcoat, a fore hatch's acrylic lid (18 x 12 cm of it in frame) on the
top and a portlight (22 x 7 cm, round-cornered) in the side, seen from about 45 cm, 35 degrees down, under the loop's
overcast CC0 sky (render_swatch.Sky), with an 18% grey card. Ray-plane in numpy; the pixel footprint the filtered
cracks and scratches read is worked out from neighbouring pixels the way the shader's fwidth does. --before renders
today's main (the window chalks as gelcoat with Age; render_swatch.gelcoat-style chalk only, no acrylic lines).
Writes acrylic_<L>.png, a parts cover per level and swatch.json.
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import port  # noqa: E402
import render_swatch as rs  # noqa: E402
import wear  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
BASE = (0.006, 0.008, 0.010)    # make_materials.py BOAT_LIBRARY CabinWindow
ROUGH, COAT = 0.04, 1.0
GEL = (0.70, 0.70, 0.67)


def rrect(u, v, cu, cv, hu, hv, r):
    q = np.stack([np.abs(u - cu) - (hu - r), np.abs(v - cv) - (hv - r)], -1)
    return (np.linalg.norm(np.maximum(q, 0), axis=-1) + np.minimum(q.max(-1), 0) - r) < 0


def trace(px):
    w, h = px, int(px * 0.62)
    cam = np.array([4.0, -36.0, 26.0])
    tgt = np.array([0.0, 2.0, -2.0])
    fwd = (tgt - cam) / np.linalg.norm(tgt - cam)
    right = np.cross(fwd, [0, 0, 1.0]); right /= np.linalg.norm(right)
    upv = np.cross(right, fwd)
    fov = math.radians(36)
    u = ((np.arange(w) + 0.5) / w - 0.5) * 2 * math.tan(fov / 2)
    v = (0.5 - (np.arange(h) + 0.5) / h) * 2 * math.tan(fov / 2) * h / w
    U, V = np.meshgrid(u, v)
    d = fwd + U[..., None] * right + V[..., None] * upv
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    t_top = np.where(d[..., 2] < 0, -cam[2] / np.minimum(d[..., 2], -1e-6), np.inf)
    y_top = cam[1] + d[..., 1] * t_top
    t_top = np.where(y_top >= 0, t_top, np.inf)
    t_side = np.where(d[..., 1] > 0, -cam[1] / np.maximum(d[..., 1], 1e-6), np.inf)
    z_side = cam[2] + d[..., 2] * t_side
    t_side = np.where(z_side <= 0, t_side, np.inf)
    top = t_top <= t_side
    t = np.where(top, t_top, t_side)
    pos = cam + d * t[..., None]
    n = np.where(top[..., None], np.array([0, 0, 1.0]), np.array([0, -1.0, 0]))
    p = np.where(top[..., None], pos[..., [0, 1]], pos[..., [0, 2]])     # BOAT_CODE hwP: xy on the top, xz on the side
    pane_top = top & rrect(pos[..., 0], pos[..., 1], 0.0, 9.0, 9.0, 6.0, 1.5)
    pane_side = ~top & rrect(pos[..., 0], pos[..., 2], 0.0, -6.5, 11.0, 3.5, 2.5)
    return dict(pos=pos, n=n, p=p, v=-d, top=top, pane=pane_top | pane_side, pane_top=pane_top, pane_side=pane_side,
                depth=t, w=w, h=h)


def footprint(p):
    gy, gx = np.gradient(p, axis=(0, 1))
    return np.linalg.norm(np.abs(gx) + np.abs(gy), axis=-1)


def before_maps(g, age, care):
    """Main before this PR: the window has Coat 1, so with an Age it chalks, yellows and loses its coat as gelcoat
    does (BOAT_CODE ox: max(dirtK, 0.3 timeK) x (0.55 + 0.45 up) x blotch, toward the chalk colour by 0.4)."""
    shape = g["n"].shape[:-1]
    col = np.broadcast_to(np.array(BASE), shape + (3,)).copy()
    rough = np.full(shape, ROUGH); coat = np.full(shape, COAT)
    if age < 0:
        return col, rough, coat
    tk, dk = wear.time_k(age, care), wear.dirt_k(age, care)
    up = g["n"][..., 2]
    bl = port.vnoise(np.stack([g["pos"][..., 0] / 40.0 + g["pos"][..., 1] / 55.0, g["pos"][..., 2] / 40.0 + g["pos"][..., 1] / 55.0], -1), 12.99, 78.23)
    ox = np.clip(max(dk, 0.3 * tk) * (0.55 + 0.45 * up) * (0.55 + 0.9 * bl), 0, 1)
    lum = float(np.dot(BASE, (0.3, 0.59, 0.11)))
    chalk = np.array(BASE) * 1.25 + lum * 0.35 + 0.01     # dark paint branch of the chalk mix (lum < 0.4)
    col = port.lerp(col, chalk, (0.4 * ox)[..., None])
    rough = port.lerp(rough, 0.72, ox)
    coat = coat * (1 - 0.85 * ox)
    return col, rough, coat


def render(g, sky, age, care, before):
    n = g["n"]
    if before:
        col, rough, coat = before_maps(g, age, care); parts = None
    else:
        col, rough, coat, _, parts = port.acrylic(BASE, ROUGH, COAT, age, care, n, g["p"], footprint(g["p"]), g["depth"], parts=True)
    pane = g["pane"]
    col = np.where(pane[..., None], col, np.array(GEL))
    rough = np.where(pane, rough, 0.25)
    coat = np.where(pane, coat, 1.0)
    h, w = g["h"], g["w"]
    card = np.zeros((h, w), bool)
    card[int(h * 0.78):int(h * 0.96), int(w * 0.84):int(w * 0.97)] = True
    ncard = np.asarray(g["v"][h // 2, w // 2])
    gg = dict(n=np.where(card[..., None], ncard, n), v=g["v"])
    col = np.where(card[..., None], 0.18, col)
    rough = np.where(card, 0.9, rough); coat = np.where(card, 0.0, coat)
    e_card = float((sky.irradiance(ncard[None, None, :])[0, 0] * 0.18).mean())
    lit = rs.shade(gg, sky, col, rough, coat, 0.18 / max(e_card, 1e-6) * 0.8)
    return rs.to_srgb(rs.aces(lit)), parts, albedo_lab(col, g)


def albedo_lab(col, g):
    import measure
    srgb = rs.to_srgb(np.clip(col, 0, 1))
    out = {}
    for name in ("pane_top", "pane_side"):
        lab = measure.srgb_to_lab(srgb[g[name]]).mean(0)
        out[name] = dict(L=round(float(lab[0]), 1), a=round(float(lab[1]), 1), b=round(float(lab[2]), 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "Artifacts", "texloop", "acrylic"))
    ap.add_argument("--before", action="store_true")
    ap.add_argument("--px", type=int, default=640)
    a = ap.parse_args()
    sky = rs.Sky(rs.load_env())
    g = trace(a.px)
    tag = "before" if a.before else "after"
    out = os.path.join(a.out, tag)
    os.makedirs(out, exist_ok=True)
    meta = {}
    for lv in wear.levels():
        img, parts, lab = render(g, sky, lv["age"], lv["care"], a.before)
        path = os.path.join(out, "acrylic_%s.png" % lv["id"])
        Image.fromarray((img * 255 + 0.5).astype(np.uint8)).save(path)
        cover = {}
        if parts:
            for k, v in parts.items():
                cover[k] = round(float((v[g["pane"]] > 0.25).mean() * 100), 1)
        meta[lv["id"]] = dict(path=os.path.relpath(path, REPO), age=lv["age"], care=lv["care"], cover_pct=cover, albedo_lab=lab)
        print(lv["id"], cover, lab)
    json.dump(meta, open(os.path.join(out, "swatch.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
