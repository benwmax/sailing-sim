"""Render rubber and webbing at the five wear levels (docs/texloop-rubber), the same view every round.

    python Tools/texloop/rubber/render_levels.py [--out Artifacts/texloop/rubber] [--before] [--px 560]

The scene, on a white deck under the loop's overcast CC0 sky (render_swatch.Sky), seen from 34 cm, 40 degrees down, with an
18% grey card: in front a black rubber rub strake (a 2.4 cm half-round along the boat, the library's Rubrail), in the
middle a black webbing hiking strap (5 cm by 3 mm, the new Webbing slot), at the back the hero J/22's grey PVC rub
rail (RubRail). Sphere-traced in numpy; the curvature the webbing's fray reads is worked out from neighbouring pixels the
way the shader's fwidth does. --before renders today's main (rubber: the one ageK line; the strap was the Rubber slot).
Writes rubber_<L>.png, swatch.json (parts cover and albedo per item).
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
RUBRAIL = ((0.03, 0.03, 0.03), 0.5)            # make_materials.py BOAT_LIBRARY Rubrail
WEBBING = ((0.022, 0.022, 0.024), 0.85)        # BOAT_LIBRARY Webbing (new)
RUBBER = ((0.025, 0.025, 0.026), 0.70)         # BOAT_LIBRARY Rubber (what the strap was before)
HERO_RAIL = ((0.1022, 0.0976, 0.0865), 0.5)    # Inputs/j22-hero/materials.json RubRail
DECK = (0.70, 0.70, 0.67)


def sd_rail(p, y0, z0, r):
    """A round rail along X through (y0, z0), its ends rounded off at |x| = 11."""
    d = p - np.array([0.0, y0, z0])
    q = np.stack([np.maximum(np.abs(d[..., 0]) - 9.5, 0.0), d[..., 1], d[..., 2]], -1)
    return np.linalg.norm(q, axis=-1) - r


def sd_box(p, c, half, r):
    q = np.abs(p - c) - (np.asarray(half) - r)
    return np.linalg.norm(np.maximum(q, 0), axis=-1) + np.minimum(q.max(-1), 0) - r


def scene(p):
    """The hull: deck z < 0 for y > -6, topsides the plane y = -6 below it. Item 1 the rub strake along the sheer,
    item 2 the strap on deck, item 3 the grey PVC rail further inboard."""
    hull = np.maximum(p[..., 2], -6.0 - p[..., 1])
    a = sd_rail(p, -6.0, -0.9, 1.2)
    b = sd_box(p, np.array([0.0, 0.5, 0.15]), (9.5, 2.5, 0.15), 0.06)
    c = sd_rail(p, 6.5, 0.0, 1.0)
    d = np.minimum(np.minimum(np.minimum(a, b), c), hull)
    part = np.where(d == a, 1, np.where(d == b, 2, np.where(d == c, 3, 0)))
    return d, part


def trace(px):
    w, h = px, int(px * 0.62)
    el = math.radians(28)
    cam = np.array([0.0, -40.0 * math.cos(el), 40.0 * math.sin(el)])
    tgt = np.array([0.0, -0.5, -1.0])
    fwd = (tgt - cam) / np.linalg.norm(tgt - cam)
    right = np.cross(fwd, [0, 0, 1.0]); right /= np.linalg.norm(right)
    upv = np.cross(right, fwd)
    fov = math.radians(40)
    u = ((np.arange(w) + 0.5) / w - 0.5) * 2 * math.tan(fov / 2)
    v = (0.5 - (np.arange(h) + 0.5) / h) * 2 * math.tan(fov / 2) * h / w
    U, V = np.meshgrid(u, v)
    d = fwd + U[..., None] * right + V[..., None] * upv
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    t = np.zeros((h, w))
    for _ in range(200):
        dist, _ = scene(cam + d * t[..., None])
        t += dist * 0.9
    pos = cam + d * t[..., None]
    _, part = scene(pos)
    e = 0.01
    n = np.stack([scene(pos + np.array(o))[0] - scene(pos - np.array(o))[0] for o in ([e, 0, 0], [0, e, 0], [0, 0, e])], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return dict(pos=pos, n=n, v=-d, part=part, depth=t, w=w, h=h)


def fwidth(a):
    gy, gx = np.gradient(a, axis=(0, 1))
    return np.abs(gx) + np.abs(gy)


def proj(n, pos):
    an = np.abs(n)
    return np.where((an[..., 2] >= np.maximum(an[..., 0], an[..., 1]))[..., None], pos[..., [0, 1]],
                    np.where((an[..., 1] >= an[..., 0])[..., None], pos[..., [0, 2]], pos[..., [1, 2]]))


def render(g, sky, age, care, before):
    n, pos, v, part = g["n"], g["pos"], g["v"], g["part"]
    curv = np.linalg.norm(fwidth(n), axis=-1) / np.maximum(np.linalg.norm(fwidth(pos), axis=-1), 0.01)
    p = proj(n, pos)
    col = np.broadcast_to(np.array(DECK), n.shape).copy()
    rough = np.full(n.shape[:2], 0.35)
    parts = {}
    n_out = n.copy()
    old_age = age if not before else age   # before: the old lines run on an age too (ageK)
    for k, (base, r0, kind) in {1: (*RUBRAIL, "rubber"), 2: (*(RUBBER if before else WEBBING), "webbing"), 3: (*HERO_RAIL, "rubber")}.items():
        m = part == k
        if before:
            ak = wear.age_k(old_age, care)
            c = np.broadcast_to(np.array(base), n.shape).copy() + 0.05 * ak
            r = np.full(n.shape[:2], r0 + (0.85 - r0) * ak)
            pr = {}
        elif kind == "rubber":
            c, r, pr = port.rubber(base, r0, age, care, n, v, p, g["depth"], parts=True)
        else:
            c, r, pr = port.webbing(base, r0, age, care, n, v, p, curv, g["depth"], parts=True)
        if not before:     # High: the tiling detail normal (BOAT_CODE's detail block: canvas weave at 2 cm on webbing, the rubber stipple at 8 cm)
            nn = detail_normal(n, p, pos, g["depth"], *(("Rubber", 8.0, 1.0) if kind == "rubber" else ("Canvas", 2.0, 0.8)))
            n_out[m] = nn[m]
        col = np.where(m[..., None], c, col)
        rough = np.where(m, r, rough)
        for name, val in pr.items():
            parts["%d_%s" % (k, name)] = round(float((val[m] > 0.25).mean() * 100), 1)
    h, w = g["h"], g["w"]
    card = np.zeros((h, w), bool)
    card[int(h * 0.82):int(h * 0.97), int(w * 0.87):int(w * 0.98)] = True
    ncard = np.asarray(g["v"][h // 2, w // 2])
    gg = dict(n=np.where(card[..., None], ncard, n_out), v=g["v"])
    col = np.where(card[..., None], 0.18, col)
    rough = np.where(card, 0.9, rough)
    e_card = float((sky.irradiance(ncard[None, None, :])[0, 0] * 0.18).mean())
    lit = rs.shade(gg, sky, col, rough, np.zeros_like(rough), 0.18 / max(e_card, 1e-6) * 0.8)
    return rs.to_srgb(rs.aces(lit)), parts, albedo_lab(col, n, part)


_MAPS = {}


def detail_normal(n, p, pos, depth, name, tile_cm, strength):
    """BOAT_CODE's tiled detail normal on the projection p (one face's axis pair), faded out from 1.5 to 6 m."""
    if name not in _MAPS:
        im = np.asarray(Image.open(os.path.join(rs.DETAIL, "T_Detail_%s_N.png" % name)).convert("RGB"), np.float32) / 255.0
        _MAPS[name] = im
    im = _MAPS[name]
    hh, ww = im.shape[:2]
    uv = p / tile_cm
    ix = (np.floor(uv[..., 0] * ww).astype(int)) % ww
    iy = (np.floor(uv[..., 1] * hh).astype(int)) % hh
    d = (im[iy, ix, :2] * 2.0 - 1.0) * strength * (1.0 - np.clip((depth - 150.0) / 450.0, 0, 1))[..., None]
    an = np.abs(n)
    ex, ey, ez = np.eye(3)
    top = (an[..., 2] >= np.maximum(an[..., 0], an[..., 1]))[..., None]
    sidey = (an[..., 1] >= an[..., 0])[..., None]
    a = np.where(top, ex, np.where(sidey, ex, ey))
    b = np.where(top, ey, ez)
    out = n + d[..., :1] * a + d[..., 1:2] * b
    return out / np.linalg.norm(out, axis=-1, keepdims=True)


def albedo_lab(col, n, part):
    """Mean albedo as Lab per item, on its sky-facing top (n.z > 0.8) and its upright side (|n.z| < 0.4)."""
    import measure
    srgb = rs.to_srgb(np.clip(col, 0, 1))
    out = {}
    for k, name in ((1, "rubrail"), (2, "strap"), (3, "pvc_rail")):
        for face, m in (("top", (part == k) & (n[..., 2] > 0.8)), ("side", (part == k) & (np.abs(n[..., 2]) < 0.4))):
            if m.sum() < 20:
                continue
            lab = measure.srgb_to_lab(srgb[m]).mean(0)
            out["%s_%s" % (name, face)] = dict(L=round(float(lab[0]), 1), a=round(float(lab[1]), 1), b=round(float(lab[2]), 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "Artifacts", "texloop", "rubber"))
    ap.add_argument("--before", action="store_true")
    ap.add_argument("--px", type=int, default=560)
    a = ap.parse_args()
    sky = rs.Sky(rs.load_env())
    g = trace(a.px)
    tag = "before" if a.before else "after"
    out = os.path.join(a.out, tag)
    os.makedirs(out, exist_ok=True)
    meta = {}
    for lv in wear.levels():
        img, parts, lab = render(g, sky, lv["age"], lv["care"], a.before)
        path = os.path.join(out, "rubber_%s.png" % lv["id"])
        Image.fromarray((img * 255 + 0.5).astype(np.uint8)).save(path)
        meta[lv["id"]] = dict(path=os.path.relpath(path, REPO), age=lv["age"], care=lv["care"], cover_pct=parts, albedo_lab=lab)
        print(lv["id"], parts, lab)
    json.dump(meta, open(os.path.join(out, "swatch.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
