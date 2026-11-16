"""Track A: render the ground material outside the engine, before (today's M_Terrain) beside after (the layered ground).

    python3 -I Tools/envloop/ground/render.py [--out Artifacts/envloop/ground/r1] [--res 1024] [--size 960x540]
        [--only club-15-midday,...] [--season 0] [--water -0.45]

A height-field ray caster over scene.py's synthetic shore (1 m mesh, BuildChunk's vertex colours), a sun with shadow
rays, a sky dome, a flat lake with Fresnel and a shallow bed seen through it, exposure from an incident meter (as the
game meters Medium and High) and an ACES curve. Views (the loop's standard renders): each of three bank kinds from 3 m,
15 m and 60 m off; 15 m in midday sun, low sun and overcast. Writes <view>_before.png, <view>_after.png and
views.json (cameras, lights, timings), plus top40.png, the 40 m frame from above for the repeat check.
"""
import argparse
import json
import os
import time

import numpy as np
from PIL import Image

import ground_material as gm
import scene as sc
import terrain_before as tb
import pack as packs

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

STATIONS = {"club": -60.0, "cutbank": -4.0, "cove": 58.0}
DISTANCES = {3: (1.5, -16.0), 15: (1.6, -2.5), 60: (2.2, -0.8)}       # off the bank: eye height, pitch
LIGHTS = {
    "midday": dict(sun=(0.25, -0.45, 0.86), sun_rgb=(1.0, 0.97, 0.92), sun_e=1.0, sky_rgb=(0.50, 0.62, 0.85), sky_e=0.22, sky_view=0.75),
    "lowsun": dict(sun=(-0.86, -0.42, 0.16), sun_rgb=(1.0, 0.72, 0.45), sun_e=0.75, sky_rgb=(0.45, 0.52, 0.72), sky_e=0.10, sky_view=0.55),
    "overcast": dict(sun=(0, 0, 1), sun_rgb=(0, 0, 0), sun_e=0.0, sky_rgb=(0.80, 0.82, 0.85), sky_e=0.55, sky_view=0.85),
}
# The repeat check's 40 m frames, from 30 m above: the club lawn, the cove's yard, the rough field, the wood's floor.
TOP40 = {"lawn": (-70.0, 40.0), "yard": (70.0, 60.0), "field": (-18.0, 26.0), "woods": (6.0, 36.0)}
WATER_BODY = np.array([0.030, 0.038, 0.026])      # turbid green-brown reservoir


def views(only=None):
    out = []
    for st, x in STATIONS.items():
        for d, (eye, pitch) in DISTANCES.items():
            for light in (LIGHTS if d == 15 else ["midday"]):
                name = f"{st}-{d}-{light}"
                if only and name not in only:
                    continue
                out.append(dict(name=name, station=st, x=x, dist=d, eye=eye, pitch=pitch, light=light))
    return out


def camera_rays(v, scene, w, h, hfov=60.0):
    x = v["x"]
    y = sc.shoreline(np.array(x)) - v["dist"]
    cam = np.array([x, float(y), scene.water + v["eye"]])
    yaw = 0.0
    pitch = np.radians(v["pitch"])
    fwd = np.array([np.sin(yaw) * np.cos(pitch), np.cos(yaw) * np.cos(pitch), np.sin(pitch)])
    right = np.array([np.cos(yaw), -np.sin(yaw), 0.0])
    up = np.cross(right, fwd)
    tx = np.tan(np.radians(hfov) / 2)
    ty = tx * h / w
    px = (np.arange(w) + 0.5) / w * 2 - 1
    py = 1 - (np.arange(h) + 0.5) / h * 2
    PX, PY = np.meshgrid(px, py)
    d = fwd + PX[..., None] * tx * right + PY[..., None] * ty * up
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    return cam, d.reshape(-1, 3), 2 * tx / w


def march(scene, o, d, tmax=420.0):
    """First hit of each ray on the height field (bisection refined) or the water plane. Returns t_ground, t_water."""
    n = len(d)
    t = np.full(n, 0.2)
    hit = np.full(n, np.inf)
    alive = np.ones(n, bool)
    prev = t.copy()
    while alive.any():
        idx = np.where(alive)[0]
        p = o + d[idx] * t[idx, None]
        below = p[:, 2] < scene.height_at(p[:, 0], p[:, 1])
        if below.any():
            j = idx[below]
            lo, hi = prev[j], t[j]
            for _ in range(10):
                mid = 0.5 * (lo + hi)
                q = o + d[j] * mid[:, None]
                b = q[:, 2] < scene.height_at(q[:, 0], q[:, 1])
                hi = np.where(b, mid, hi)
                lo = np.where(b, lo, mid)
            hit[j] = hi
            alive[j] = False
        go = idx[~below]
        prev[go] = t[go]
        t[go] += np.maximum(0.04, 0.006 * t[go])
        out = (t > tmax) | (o[2] + d[:, 2] * t > 40.0)
        alive &= ~out
    tw = np.where(d[:, 2] < 0, (scene.water - o[2]) / np.minimum(d[:, 2], -1e-6), np.inf)
    return hit, tw


def shadow(scene, p, sun):
    lit = np.ones(len(p))
    if sun[2] > 0.95:
        return lit
    for s in np.arange(0.3, 60.0, 0.35):
        q = p + np.asarray(sun) * s
        lit = np.minimum(lit, np.clip((q[:, 2] - scene.height_at(q[:, 0], q[:, 1])) / 0.08 + 0.5, 0, 1))
    return lit


def ggx_spec(n, v, l, rough):
    hv = v + l
    hv /= np.linalg.norm(hv, axis=-1, keepdims=True)
    a = np.maximum(rough, 0.05) ** 2
    nh = np.clip((n * hv).sum(-1), 0, 1)
    nl = np.clip((n * l).sum(-1), 0, 1)
    nv = np.clip((n * v).sum(-1), 1e-3, 1)
    dd = a * a / (np.pi * (nh * nh * (a * a - 1) + 1) ** 2)
    k = a / 2
    g = nl / (nl * (1 - k) + k) * nv / (nv * (1 - k) + k)
    f = 0.04 + 0.96 * (1 - np.clip((v * hv).sum(-1), 0, 1)) ** 5
    return dd * g * f / (4 * nv * np.maximum(nl, 1e-3)) * nl


def aces(x):
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    return np.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0, 1)


def to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def render(v, scene, bank, season, size, which):
    w, h = size
    cam, d, pix = camera_rays(v, scene, w, h)
    L = LIGHTS[v["light"]]
    sun = np.array(L["sun"], float)
    sun /= np.linalg.norm(sun)
    sun_c = np.array(L["sun_rgb"]) * L["sun_e"]
    sky_c = np.array(L["sky_rgb"]) * L["sky_e"]
    meter = L["sun_e"] * max(sun[2], 0) * np.array(L["sun_rgb"]) @ [0.2126, 0.7152, 0.0722] + sky_c @ [0.2126, 0.7152, 0.0722]
    tg, tw = march(scene, cam, d)
    rgb = np.zeros((len(d), 3))
    sky_px = (~np.isfinite(tg)) & (~np.isfinite(tw))
    up = np.clip(d[:, 2], 0, 1)[:, None]
    sky_rad = np.array(L["sky_rgb"]) / (np.array(L["sky_rgb"]) @ [0.2126, 0.7152, 0.0722]) * L["sky_view"] * meter
    rgb[sky_px] = (sky_rad * (1.15 - 0.6 * up))[sky_px]

    def ground(idx, t):
        p = cam + d[idx] * t[:, None]
        at = scene.attributes(p[:, 0], p[:, 1])
        p[:, 2] = at["Z"]
        cosi = np.clip(-(d[idx] * at["N"]).sum(-1), 0.05, 1)
        foot = t * pix / cosi ** 0.25     # 8x anisotropic filtering keeps most of the grazing detail
        if which == "before":
            base, rough = tb.shade(p, at["C"], at["Near"], scene.water, cam)
            nw, ao = at["N"], np.ones(len(idx))
        else:
            base, rough, nw, _, ao = gm.shade(p, at["N"], at["C"], at["Near"], scene.water, at["Mown"], season, bank, foot, cam)
        vdir = -d[idx]
        nl = np.clip((nw * sun).sum(-1), 0, 1)
        sh = shadow(scene, p + at["N"] * 0.05, sun) if L["sun_e"] > 0 else np.zeros(len(idx))
        # Sky light: the hemisphere the normal sees, cut by the slope and the scans' occlusion.
        skyv = (0.55 + 0.45 * nw[:, 2]) * ao
        diff = base * (sun_c * (nl * sh)[:, None] + sky_c * skyv[:, None])
        spec = ggx_spec(nw, vdir, np.broadcast_to(sun, nw.shape), rough)[:, None] * sun_c * sh[:, None]
        spec += (0.04 * (1 - rough) ** 2)[:, None] * sky_c * 0.5
        return diff + spec

    gi = np.where(np.isfinite(tg) & (tg <= tw))[0]
    if len(gi):
        rgb[gi] = ground(gi, tg[gi])
    wi = np.where(np.isfinite(tw) & (tw < tg))[0]
    if len(wi):
        cosv = np.clip(-d[wi, 2], 0, 1)
        fres = 0.02 + 0.98 * (1 - cosv) ** 5
        refl_dir_up = np.clip(-d[wi, 2], 0, 1)
        sky_r = sky_rad * (1.15 - 0.6 * refl_dir_up[:, None])
        body = WATER_BODY * (sun_c * max(sun[2], 0) + sky_c)
        col = body
        # The shallow bed through the water (no refraction): seen while the path under the surface is short.
        bed = np.isfinite(tg[wi])
        if bed.any():
            bi = wi[bed]
            depth_path = tg[bi] - tw[bi]
            through = np.exp(-depth_path * 2.2)[:, None]
            bc = ground(bi, tg[bi])
            col = np.broadcast_to(body, (len(wi), 3)).copy()
            col[bed] = bc * through * np.array([0.85, 0.95, 0.80]) + body * (1 - through)
        rgb[wi] = col * (1 - fres[:, None]) + sky_r * fres[:, None]
    img = to_srgb(aces(rgb / max(meter, 1e-3) * 0.85)).reshape(h, w, 3)
    return (img * 255 + 0.5).astype(np.uint8)


def top40(scene, bank, season, res):
    """The 40 m frame from 30 m straight above the club lawn and the cove's yard (the repeat check's input)."""
    out = {}
    for name, (cx, cy) in TOP40.items():
        n = 640
        g = (np.arange(n) + 0.5) / n * 40.0 - 20.0
        X, Y = np.meshgrid(cx + g, cy + g)
        x, y = X.ravel(), Y.ravel()
        at = scene.attributes(x, y)
        p = np.stack([x, y, at["Z"]], -1)
        cam = np.array([cx, cy, 30.0])
        base, _, nw, _, ao = gm.shade(p, at["N"], at["C"], at["Near"], scene.water, at["Mown"], season, bank,
                                      np.full(len(x), 40.0 / n), cam)
        shade = (0.3 + 0.7 * np.clip(nw @ np.array([0.3, -0.4, 0.87]), 0, 1)) * ao
        img = to_srgb(aces(base * shade[:, None] * 2.2)).reshape(n, n, 3)
        out[name] = (img * 255 + 0.5).astype(np.uint8)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "Artifacts", "envloop", "ground", "r1"))
    ap.add_argument("--pack", default=None)
    ap.add_argument("--res", type=int, default=1024)
    ap.add_argument("--size", default="960x540")
    ap.add_argument("--only", default="")
    ap.add_argument("--season", type=float, default=0.0)
    ap.add_argument("--water", type=float, default=sc.GAUGE)
    ap.add_argument("--which", default="before,after")
    ap.add_argument("--top-only", action="store_true", help="only the repeat check's 40 m frames")
    ap.add_argument("--bank-noise", default="smooth", help="after's bank tone: smooth (proposed) or cell (today)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    size = tuple(int(s) for s in args.size.split("x"))
    gm.use_pack(args.pack)
    bank = gm.TexBank(packs.prep_dir(args.pack), args.res)
    scenes = {"before": sc.Scene(args.water, "cell"), "after": sc.Scene(args.water, args.bank_noise)}
    log = []
    for v in ([] if args.top_only else views(set(filter(None, args.only.split(","))) or None)):
        row = dict(v)
        for which in args.which.split(","):
            t0 = time.time()
            img = render(v, scenes[which], bank, args.season, size, which)
            Image.fromarray(img).save(os.path.join(args.out, f"{v['name']}_{which}.png"))
            row[f"{which}_s"] = round(time.time() - t0, 1)
        log.append(row)
        print(row, flush=True)
    if "after" in args.which:
        for name, img in top40(scenes["after"], bank, args.season, args.res).items():
            Image.fromarray(img).save(os.path.join(args.out, f"top40_{name}.png"))
    if args.top_only:
        return
    json.dump(dict(views=log, season=args.season, water=args.water, res=args.res, lights=LIGHTS), open(os.path.join(args.out, "views.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
