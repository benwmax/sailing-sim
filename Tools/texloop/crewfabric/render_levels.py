"""Render the crew's cloth at the five wear levels (docs/texloop-crewfabric), the same views every round.

    python Tools/texloop/crewfabric/render_levels.py [--out Artifacts/texloop/crewfabric] [--before] [--px 400]

Four tiles a level, each its own little scene under the loop's overcast CC0 sky (render_swatch.Sky) with an 18% grey
card: a royal blue life jacket's front panel and shoulder (the school vests in Bean's lesson photos, Fabric048), a red
one (the game's own colours), a navy six-panel cap's crown (Fabric036), and a pale blue polo over a shoulder
(Fabric070). Each is sphere-traced in numpy, the scan sampled in the garment's UVs as M_CrewFabric does (Tiling, the
scan's luminance over its mean, its normal and roughness), then FABRIC_WEAR (port.py). --before renders today's main
(no wear: every level the same). Writes crewfabric_<L>.png (2 x 2 tiles), a parts summary and swatch.json.

The CC0 scans come from ambientCG (Tools/fabrics/fetch_fabrics.sh, into the git-ignored Data/Fabrics/raw).
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
RAW = os.path.join(REPO, "Data", "Fabrics", "raw")
AVG = {"Fabric070": 0.4114, "Fabric048": 0.9051, "Fabric036": 0.4931}   # make_materials.py FABRIC_SETS

# name: (scan, colour (linear), tiling per UV unit, normal strength, base roughness, kind, metres per UV unit)
# The instances' numbers from make_materials.py (MI_Crew_PFDShell, MI_Crew_CapCloth, MI_Crew_Polo); the colours are the
# pawn's (CrewOutfit.cpp: red vest, pale blue polo; SailboatPawn: the navy cap) and the school's royal blue.
TILES = {
    "vest_blue": ("Fabric048", (0.02, 0.07, 0.42), 30.0, 0.35, 0.66, 1, 1.0),
    "vest_red": ("Fabric048", (0.66, 0.02, 0.02), 30.0, 0.35, 0.66, 1, 1.0),
    "cap": ("Fabric036", (0.02, 0.04, 0.12), 20.0, 0.5, 0.85, 3, 0.106),
    "polo": ("Fabric070", (0.40, 0.53, 0.72), 9.0, 0.55, 0.85, 2, 1.0),
}


def load_scan(k):
    base = os.path.join(RAW, k, k + "_2K-JPG")
    if not os.path.exists(base + "_Color.jpg"):
        raise SystemExit("no scans: run Tools/fabrics/fetch_fabrics.sh")
    rd = lambda s: np.asarray(Image.open(base + s).convert("RGB"), np.float32) / 255.0  # noqa: E731
    col = rs.to_linear(rd("_Color.jpg")) if hasattr(rs, "to_linear") else np.where(rd("_Color.jpg") <= 0.04045, rd("_Color.jpg") / 12.92, ((rd("_Color.jpg") + 0.055) / 1.055) ** 2.4)
    nrm = rd("_NormalDX.jpg") * 2 - 1
    rough = rd("_Roughness.jpg")[..., 0]
    return col, nrm, rough


def sample(img, uv):
    """Bilinear, wrapped; uv in texture repeats."""
    h, w = img.shape[:2]
    x = (uv[..., 0] % 1.0) * w - 0.5
    y = (uv[..., 1] % 1.0) * h - 0.5
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
    fx = x - x0; fy = y - y0
    x0 %= w; y0 %= h; x1 = (x0 + 1) % w; y1 = (y0 + 1) % h
    if img.ndim == 3:
        fx = fx[..., None]; fy = fy[..., None]
    return (img[y0, x0] * (1 - fx) + img[y0, x1] * fx) * (1 - fy) + (img[y1, x0] * (1 - fx) + img[y1, x1] * fx) * fy


def sd_round_box(p, c, half, r):
    q = np.abs(p - c) - (np.asarray(half) - r)
    return np.linalg.norm(np.maximum(q, 0), axis=-1) + np.minimum(q.max(-1), 0) - r


def sd_ellipsoid(p, c, r):
    q = (p - c) / np.asarray(r)
    k0 = np.linalg.norm(q, axis=-1)
    k1 = np.linalg.norm(q / np.asarray(r), axis=-1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)


def sd_capsule_x(p, c, half_len, r):
    d = p - c
    d = np.stack([np.maximum(np.abs(d[..., 0]) - half_len, 0), d[..., 1], d[..., 2]], -1)
    return np.linalg.norm(d, axis=-1) - r


SCENES = {
    # a vest's front panel (34 x 12 x 38 cm, 5 cm round), its top a shoulder that sees the sky; camera 45 cm off, 30 deg down
    "vest": (lambda p: sd_round_box(p, np.array([0.0, 0.0, 19.0]), (17.0, 6.0, 19.0), 5.0), (0.0, -50.0, 52.0), (0.0, 0.0, 20.0)),
    # a cap's crown (half an ellipsoid, 10.5 x 9.5 x 9 cm), seen from 34 cm, 35 deg down
    "cap": (lambda p: np.maximum(sd_ellipsoid(p, np.array([0.0, 0.0, 0.0]), (10.5, 9.5, 9.0)), -p[..., 2]), (6.0, -28.0, 22.0), (0.0, 0.0, 4.0)),
    # a polo over a shoulder: a 16 cm round capsule lying across, seen from 40 cm, 30 deg down
    "polo": (lambda p: sd_capsule_x(p, np.array([0.0, 0.0, 16.0]), 12.0, 16.0), (0.0, -36.0, 38.0), (0.0, 0.0, 18.0)),
}


def trace(name, px):
    sdf, cam, tgt = SCENES[name]
    cam = np.asarray(cam, float); tgt = np.asarray(tgt, float)
    w = h = px
    fwd = (tgt - cam) / np.linalg.norm(tgt - cam)
    right = np.cross(fwd, [0, 0, 1.0]); right /= np.linalg.norm(right)
    upv = np.cross(right, fwd)
    fov = math.radians(46)
    u = ((np.arange(w) + 0.5) / w - 0.5) * 2 * math.tan(fov / 2)
    v = (0.5 - (np.arange(h) + 0.5) / h) * 2 * math.tan(fov / 2)
    U, V = np.meshgrid(u, v)
    d = fwd + U[..., None] * right + V[..., None] * upv
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    t = np.zeros((h, w)); hit = np.zeros((h, w), bool)
    for _ in range(140):
        dist = sdf(cam + d * t[..., None])
        hit |= dist < 0.01
        t = np.where(hit, t, t + dist * 0.9)
        t = np.minimum(t, 400.0)
    pos = cam + d * t[..., None]
    e = 0.01
    n = np.stack([sdf(pos + np.array(o)) - sdf(pos - np.array(o)) for o in ([e, 0, 0], [0, e, 0], [0, 0, e])], -1)
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9)
    return dict(pos=pos, n=n, v=-d, hit=hit & (t < 399.0), depth=t, w=w, h=h)


def garment_uv(name, pos, n):
    """The garment's UV0 in metres (cap: in its unit mesh, 0.106 m a unit): a cylinder round it, as build_vest.py,
    build_polo.py and build_crew_gear.py lay theirs out; the vest's top takes the plan view."""
    m = pos / 100.0
    if name == "vest":
        top = n[..., 2] > 0.7
        return np.where(top[..., None], m[..., [0, 1]], np.stack([m[..., 0] + 0.3 * np.sign(m[..., 0]) * (np.abs(n[..., 0]) > 0.7) * m[..., 1], m[..., 2]], -1))
    if name == "cap":
        r = np.hypot(m[..., 0], m[..., 1]) / 0.106
        return np.stack([np.arctan2(m[..., 1], m[..., 0]) * r, m[..., 2] / 0.106], -1)
    return np.stack([m[..., 0], np.arctan2(m[..., 2] - 0.16, m[..., 1]) * 0.16], -1)


def tangent_frame(name, n):
    if name == "polo":
        T = np.broadcast_to(np.array([1.0, 0, 0]), n.shape)
    else:
        T = np.cross(np.array([0, 0, 1.0]), n)
        bad = np.linalg.norm(T, axis=-1) < 0.2
        T = np.where(bad[..., None], np.array([1.0, 0, 0]), T)
    T = T / np.maximum(np.linalg.norm(T, axis=-1, keepdims=True), 1e-9)
    B = np.cross(n, T)
    return T, B


def render_tile(tile, g, scans, sky, age, care, before):
    scene = "vest" if tile.startswith("vest") else tile
    k, colour, tiling, strength, rough0, kind, uvm = TILES[tile]
    a_map, n_map, r_map = scans[k]
    n = g["n"]
    uv = garment_uv(scene, g["pos"], n)
    tuv = uv * tiling / (1.0 if scene != "cap" else 1.0 / 1.0)
    if scene == "cap":
        tuv = uv * tiling   # the cap's UVs are in its unit mesh already
    A = sample(a_map, tuv); Nt = sample(n_map, tuv); R = sample(r_map, tuv)
    lumA = A[..., 0] * 0.3 + A[..., 1] * 0.59 + A[..., 2] * 0.11
    detail = 1.0 + (lumA / AVG[k] - 1.0) * 0.8
    depth = g["depth"]
    fade = np.clip(1.0 - (depth - 150.0) / 600.0, 0, 1)
    albedo = np.clip(np.asarray(colour) * detail[..., None], 0, 1)
    rough = np.clip(rough0 + (R - rough0) * (0.6 * fade + 0.2), 0, 1)
    fuzz = np.full(rough.shape, 0.5)
    T, B = tangent_frame(scene, n)
    s = strength * fade
    nn = n + s[..., None] * (Nt[..., 0:1] * T - Nt[..., 1:2] * B)
    nn /= np.linalg.norm(nn, axis=-1, keepdims=True)
    parts = None
    if not before:
        # the cap's own UVs: UVm brings them to metres inside the port, as on the material
        albedo, rough, fuzz, parts = port.fabric(albedo, rough, fuzz, detail, uv, n[..., 2], depth, age, care, kind, uvm, parts=True)
    hit = g["hit"]
    ground = np.array([0.30, 0.30, 0.29])
    col = np.where(hit[..., None], albedo, ground)
    rgh = np.where(hit, rough, 0.9)
    nrm = np.where(hit[..., None], nn, np.array([0, 0, 1.0]))
    h, w = g["h"], g["w"]
    card = np.zeros((h, w), bool)
    card[int(h * 0.86):int(h * 0.97), int(w * 0.84):int(w * 0.97)] = True
    ncard = g["v"][h // 2, w // 2]
    col = np.where(card[..., None], 0.18, col)
    rgh = np.where(card, 0.9, rgh)
    nrm = np.where(card[..., None], ncard, nrm)
    e_card = float((sky.irradiance(ncard[None, None, :])[0, 0] * 0.18).mean())
    lit = rs.shade(dict(n=nrm, v=g["v"]), sky, col, rgh, np.zeros_like(rgh), 0.18 / max(e_card, 1e-6) * 0.8)
    # fuzz: a soft rim of the cloth's own colour at grazing angles (Substrate's fuzz, roughly)
    nv = np.clip((nrm * g["v"]).sum(-1), 0, 1)
    lit = lit + (np.where(hit, fuzz, 0) * 0.25 * (1 - nv) ** 3)[..., None] * col * sky.irradiance(nrm) * 0.18 / max(e_card, 1e-6) * 0.8
    img = rs.to_srgb(rs.aces(lit))
    return img, parts, hit, albedo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "Artifacts", "texloop", "crewfabric"))
    ap.add_argument("--before", action="store_true")
    ap.add_argument("--px", type=int, default=400)
    a = ap.parse_args()
    sky = rs.Sky(rs.load_env())
    scans = {k: load_scan(k) for k in {t[0] for t in TILES.values()}}
    geo = {s: trace(s, a.px) for s in SCENES}
    tag = "before" if a.before else "after"
    out = os.path.join(a.out, tag)
    os.makedirs(out, exist_ok=True)
    meta = {}
    import measure
    for lv in wear.levels():
        tiles, cover, lab = [], {}, {}
        for tile in ("vest_blue", "vest_red", "cap", "polo"):
            g = geo["vest" if tile.startswith("vest") else tile]
            img, parts, hit, alb = render_tile(tile, g, scans, sky, lv["age"], lv["care"], a.before)
            tiles.append(img)
            if parts:
                cover[tile] = {k: round(float((v[hit] > 0.25).mean() * 100), 1) for k, v in parts.items()}
            m = hit & (g["n"][..., 1] < -0.6)     # the faces toward the camera
            L = measure.srgb_to_lab(rs.to_srgb(np.clip(alb[m], 0, 1))).mean(0)
            lab[tile] = dict(L=round(float(L[0]), 1), a=round(float(L[1]), 1), b=round(float(L[2]), 1), C=round(float(math.hypot(L[1], L[2])), 1))
        grid = np.concatenate([np.concatenate(tiles[:2], 1), np.concatenate(tiles[2:], 1)], 0)
        path = os.path.join(out, "crewfabric_%s.png" % lv["id"])
        Image.fromarray((np.clip(grid, 0, 1) * 255 + 0.5).astype(np.uint8)).save(path)
        meta[lv["id"]] = dict(path=path, age=lv["age"], care=lv["care"], cover_pct=cover, albedo_lab=lab)
        print(lv["id"], json.dumps(lab), json.dumps(cover))
    json.dump(meta, open(os.path.join(out, "swatch.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
