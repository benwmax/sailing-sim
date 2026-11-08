"""Render black plastic hardware at the five wear levels (docs/texloop-plastic), the same view every round.

    python Tools/texloop/plastic/render_levels.py [--out Artifacts/texloop/plastic] [--before] [--px 520]

The scene: a cam cleat's base (a 7 x 3.2 x 3.4 cm rounded block, 5 mm edges) and a block's cheek (a 5.6 cm disc, 1.2 cm
thick, facing the camera) on a white deck, seen from 32 cm, 45 degrees down, under the loop's overcast CC0 sky (render_swatch.Sky), with an
18% grey card. Sphere-traced in numpy; the curvature the polish reads is worked out from neighbouring pixels the way
the shader's fwidth does. --before renders today's main (black plastic has no weathering: every level the same).
Writes plastic_<L>.png, a parts mask per level (what each wear layer covers) and swatch.json.
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
BASE = (0.018, 0.018, 0.02)     # make_materials.py BOAT_LIBRARY BlackPlastic
ROUGH = 0.45
DECK = (0.70, 0.70, 0.67)


def sd_round_box(p, c, half, r):
    q = np.abs(p - c) - (np.asarray(half) - r)
    return np.linalg.norm(np.maximum(q, 0), axis=-1) + np.minimum(q.max(-1), 0) - r


def sd_disc(p, c, rad, half_t, r):
    """A rounded disc with its axis along Y (facing the camera)."""
    d = p - c
    rr = np.hypot(d[..., 0], d[..., 2])
    q = np.stack([rr - (rad - r), np.abs(d[..., 1]) - (half_t - r)], -1)
    return np.linalg.norm(np.maximum(q, 0), axis=-1) + np.minimum(q.max(-1), 0) - r


def scene(p):
    a = sd_round_box(p, np.array([-2.5, 0.0, 1.7]), (3.5, 1.6, 1.7), 0.5)
    b = sd_disc(p, np.array([4.6, 0.6, 2.8]), 2.8, 0.6, 0.35)
    deck = p[..., 2]
    return np.minimum(np.minimum(a, b), deck), np.where(np.minimum(a, b) < deck, 1, 0)


def trace(px):
    w, h = px, int(px * 0.62)
    cam = np.array([0.0, -32.0 * math.cos(math.radians(45)), 32.0 * math.sin(math.radians(45)) + 1.5])
    tgt = np.array([0.8, 0.0, 1.5])
    fwd = (tgt - cam) / np.linalg.norm(tgt - cam)
    right = np.cross(fwd, [0, 0, 1.0]); right /= np.linalg.norm(right)
    upv = np.cross(right, fwd)
    fov = math.radians(32)
    u = ((np.arange(w) + 0.5) / w - 0.5) * 2 * math.tan(fov / 2)
    v = (0.5 - (np.arange(h) + 0.5) / h) * 2 * math.tan(fov / 2) * h / w
    U, V = np.meshgrid(u, v)
    d = fwd + U[..., None] * right + V[..., None] * upv
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    t = np.zeros((h, w))
    for _ in range(160):
        dist, _ = scene(cam + d * t[..., None])
        t += dist * 0.9
    pos = cam + d * t[..., None]
    _, part = scene(pos)
    e = 0.01
    n = np.stack([scene(pos + np.array(o))[0] - scene(pos - np.array(o))[0] for o in ([e, 0, 0], [0, e, 0], [0, 0, e])], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    view = -d
    return dict(pos=pos, n=n, v=view, part=part.astype(bool), depth=t, w=w, h=h)


def fwidth(a):
    gy, gx = np.gradient(a, axis=(0, 1))
    return np.abs(gx) + np.abs(gy)


def render(g, sky, age, care, before):
    n, pos = g["n"], g["pos"]
    curv = np.linalg.norm(fwidth(n), axis=-1) / np.maximum(np.linalg.norm(fwidth(pos), axis=-1), 0.01)
    an = np.abs(n)
    p = np.where((an[..., 2] >= np.maximum(an[..., 0], an[..., 1]))[..., None], pos[..., [0, 1]],
                 np.where((an[..., 1] >= an[..., 0])[..., None], pos[..., [0, 2]], pos[..., [1, 2]]))
    if before:
        col = np.broadcast_to(np.array(BASE), n.shape).copy(); rough = np.full(n.shape[:2], ROUGH)
        parts = None
    else:
        col, rough, parts = port.plastic(BASE, ROUGH, age, care, n, p, curv, g["depth"], parts=True)
    col = np.where(g["part"][..., None], col, np.array(DECK))
    rough = np.where(g["part"], rough, 0.35)
    h, w = g["h"], g["w"]
    card = np.zeros((h, w), bool)
    card[int(h * 0.78):int(h * 0.96), int(w * 0.84):int(w * 0.97)] = True
    ncard = -np.asarray(g["v"][h // 2, w // 2]); ncard = -ncard
    gg = dict(n=np.where(card[..., None], ncard, n), v=g["v"])
    col = np.where(card[..., None], 0.18, col)
    rough = np.where(card, 0.9, rough)
    e_card = float((sky.irradiance(ncard[None, None, :])[0, 0] * 0.18).mean())
    lit = rs.shade(gg, sky, col, rough, np.zeros_like(rough), 0.18 / max(e_card, 1e-6) * 0.8)
    return rs.to_srgb(rs.aces(lit)), parts, albedo_lab(col, n, g["part"])


def albedo_lab(col, n, part):
    """Mean albedo as Lab, on the parts' sky-facing tops and on their upright sides (what the targets are in)."""
    import measure
    srgb = rs.to_srgb(np.clip(col, 0, 1))
    out = {}
    for name, m in (("top", part & (n[..., 2] > 0.9)), ("side", part & (np.abs(n[..., 2]) < 0.3))):
        lab = measure.srgb_to_lab(srgb[m]).mean(0)
        out[name] = dict(L=round(float(lab[0]), 1), a=round(float(lab[1]), 1), b=round(float(lab[2]), 1))
    return out


def boxes(g):
    """Normalised boxes: the block's sky-facing top, its side face, and the grey card."""
    return dict(top=[0.22, 0.34, 0.40, 0.44], side=[0.20, 0.60, 0.42, 0.74], neutral=[0.85, 0.80, 0.96, 0.94])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "Artifacts", "texloop", "plastic"))
    ap.add_argument("--before", action="store_true")
    ap.add_argument("--px", type=int, default=520)
    a = ap.parse_args()
    sky = rs.Sky(rs.load_env())
    g = trace(a.px)
    tag = "before" if a.before else "after"
    out = os.path.join(a.out, tag)
    os.makedirs(out, exist_ok=True)
    meta = {}
    for lv in wear.levels():
        img, parts, lab = render(g, sky, lv["age"], lv["care"], a.before)
        path = os.path.join(out, "plastic_%s.png" % lv["id"])
        Image.fromarray((img * 255 + 0.5).astype(np.uint8)).save(path)
        cover = {}
        if parts:
            for k, v in parts.items():
                cover[k] = round(float((v[g["part"]] > 0.25).mean() * 100), 1)
        meta[lv["id"]] = dict(path=path, boxes=boxes(g), age=lv["age"], care=lv["care"], cover_pct=cover, albedo_lab=lab)
        print(path, cover, lab)
    json.dump(meta, open(os.path.join(out, "swatch.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
