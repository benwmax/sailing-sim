"""Standard renders for the building materials (Track E2, docs/envloop/buildmat): a test house at 3, 15 and 60 m in
midday sun, low sun and overcast, plus each finish's wear ladder (L0..L4), all from the shader text itself.

    python3 -I Tools/envloop/buildmat/render.py [houses...] [--px 720] [--out DIR] [--ladder] [--levels L2]

No engine and no Blender: a numpy ray caster over a single-storey test house (12 x 8 m, 2.9 m walls, 6:12 gable roof,
three windows and a door on the front, one window on the gable end), sampling the texture sets with mip maps by each
pixel's footprint (so 60 m shows what the GPU's filtering will), the wear and anti-tiling through BUILDMAT_CODE
(buildmat_hlsl.py, run on numpy), the windows through interior.py, and image-based light from three CC0 Poly Haven skies
(the texture loop's prefiltered split-sum shading, Tools/texloop/render_swatch.py). The camera stands 1.6 m up, the
height of an eye in a dinghy on a bank-side lake, 25 degrees off square. Exposure meters an 18% grey card facing the
camera, as the texture loop does. Writes PNGs and render.json to Artifacts/envloop/buildmat/ (git-ignored).

Not in the picture: shadows (the sun term has no shadow from the eaves), the trim and gutters (the parts kit's), any
ground but a flat lawn.
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "Tools", "texloop"))
sys.path.insert(0, os.path.join(REPO, "Tools", "texloop", "dock"))
import buildmat_hlsl as BH          # noqa: E402
import pack as P                    # noqa: E402
import interior as INT              # noqa: E402
import render_swatch as RS          # noqa: E402

TEX = P.tex_dir()
OUT = os.path.join(REPO, "Artifacts", "envloop", "buildmat")
SKIES = {"midday": "kloofendal_48d_partly_cloudy_puresky", "lowsun": "spruit_sunrise", "overcast": "kloofendal_overcast"}
SUN_AZ = {"midday": -125.0, "lowsun": -150.0, "overcast": -125.0}   # where each sky's sun is turned to (deg, world frame)
LEVELS = {lv["id"]: lv for lv in json.load(open(os.path.join(REPO, "Tools", "texloop", "levels.json")))["levels"]}

# The test houses: a wall finish, a roof finish, paint (sRGB) for painted walls and roofs, bare metal or not.
HOUSES = P.load()["test_houses"]
TRIM = np.array([0.80, 0.80, 0.77])
DOOR = np.array([0.18, 0.05, 0.04])
LAWN = np.array([0.16, 0.20, 0.07])

# geometry (metres; x right, y away from the camera, z up)
HW, DEPTH, WALL_H, PITCH, OVER = 6.0, 8.0, 2.9, 0.5, 0.45
EAVE_Z = WALL_H - OVER * PITCH
RIDGE_Y, RIDGE_Z = DEPTH / 2, WALL_H + DEPTH / 2 * PITCH
FRONT_WINDOWS = [(-4.2, 0.9, 0.9, 1.5), (-1.6, 0.9, 0.9, 1.5), (3.6, 0.9, 1.8, 1.5)]   # x centre, sill, w, h
DOOR_RECT = (1.0, 0.0, 0.91, 2.03)
SIDE_WINDOWS = [(4.0, 0.9, 0.9, 1.5)]   # y centre on the gable end


def srgb_lin(h):
    h = h.lstrip("#")
    return RS.np.array([((int(h[i:i + 2], 16) / 255.0 + 0.055) / 1.055) ** 2.4 for i in (0, 2, 4)])


class Tex:
    """A texture with box-filtered mips; trilinear sampling with wrap."""

    def __init__(self, arr):
        self.levels = [arr.astype(np.float32)]
        while min(self.levels[-1].shape[:2]) > 4:
            a = self.levels[-1]
            h, w = a.shape[0] // 2 * 2, a.shape[1] // 2 * 2
            self.levels.append(a[:h, :w].reshape(h // 2, 2, w // 2, 2, -1).mean((1, 3)))

    def _bilinear(self, lv, u, v):
        a = self.levels[lv]
        h, w = a.shape[:2]
        x = u * w - 0.5; y = v * h - 0.5
        x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
        fx = (x - x0)[..., None]; fy = (y - y0)[..., None]
        x0w, x1w, y0w, y1w = x0 % w, (x0 + 1) % w, y0 % h, (y0 + 1) % h
        return (a[y0w, x0w] * (1 - fx) + a[y0w, x1w] * fx) * (1 - fy) + (a[y1w, x0w] * (1 - fx) + a[y1w, x1w] * fx) * fy

    def sample(self, u, v, lod):
        lod = np.clip(lod, 0, len(self.levels) - 1)
        out = np.zeros(u.shape + (self.levels[0].shape[2],), np.float32)
        lo = np.floor(lod).astype(int); t = (lod - lo)[..., None]
        for lv in np.unique(lo):
            m = lo == lv
            a = self._bilinear(lv, u[m], v[m])
            b = self._bilinear(min(lv + 1, len(self.levels) - 1), u[m], v[m])
            out[m] = a * (1 - t[m]) + b * t[m]
        return out


_TEX = {}


def texset(name):
    if name in _TEX:
        return _TEX[name]
    meta = json.load(open(os.path.join(TEX, "textures.json")))[name]
    load = lambda s: np.asarray(Image.open(os.path.join(TEX, "%s_%s.png" % (name, s))), np.float64) / 255.0
    c = load("C"); c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    n = load("N") * 2 - 1
    m = load("M")
    _TEX[name] = dict(C=Tex(c), N=Tex(n), M=Tex(m), tile=meta["tile_m"], px=meta["px"][0])
    return _TEX[name]


def noise_tex():
    if "noise" not in _TEX:
        _TEX["noise"] = Tex(np.asarray(Image.open(os.path.join(TEX, "BuildNoise.png")), np.float64) / 255.0)
    return _TEX["noise"]


def lod_of(u, v, size_px):
    """Mip level from the screen-space derivatives of (u, v) in texture units."""
    du = np.maximum(np.abs(np.gradient(u, axis=0)), np.abs(np.gradient(u, axis=1)))
    dv = np.maximum(np.abs(np.gradient(v, axis=0)), np.abs(np.gradient(v, axis=1)))
    return np.log2(np.maximum(np.maximum(du, dv) * size_px, 1e-6))


_SKY = {}


def turned_sky(name, az_deg):
    """The sky turned so its sun stands at az_deg (cached: prefiltering is the slow part of a render)."""
    if (name, az_deg) in _SKY:
        return _SKY[(name, az_deg)]
    _SKY[(name, az_deg)] = _turned_sky(name, az_deg)
    return _SKY[(name, az_deg)]


def _turned_sky(name, az_deg):
    env = RS.load_env(name)
    lum = env.sum(-1)
    y, x = np.unravel_index(np.argmax(RS_blur(lum)), lum.shape)
    w = env.shape[1]
    phi_sun = (x + 0.5) / w * 2 * math.pi - math.pi
    shift = int(round((math.radians(az_deg) - phi_sun) / (2 * math.pi) * w))
    return RS.Sky(np.roll(env, shift, axis=1)), np.roll(env, shift, axis=1)


def RS_blur(a):
    k = 9
    out = a.copy()
    for d in range(1, k):
        out += np.roll(a, d, 0) + np.roll(a, -d, 0) + np.roll(a, d, 1) + np.roll(a, -d, 1)
    return out


def camera(dist, w, h, yaw_deg=25.0):
    aspect = w / h
    yaw = math.radians(yaw_deg)
    if dist <= 4:
        target = np.array([-4.2, 0.0, 1.55])
    else:
        target = np.array([-0.8, 0.0, 2.2])
    cam = target + np.array([-math.sin(yaw) * dist, -math.cos(yaw) * dist, 0.0])
    cam[2] = 1.6
    fwd = target - cam; fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0, 0, 1.0]); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    fov = math.radians(50.0)
    xs = (np.arange(w) + 0.5) / w * 2 - 1
    ys = 1 - (np.arange(h) + 0.5) / h * 2
    X, Y = np.meshgrid(xs * math.tan(fov / 2), ys * math.tan(fov / 2) / aspect)
    d = fwd + X[..., None] * right + Y[..., None] * up
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    return cam, d


def trace(cam, d):
    """Nearest surface per ray: id (0 sky, 1 ground, 2 front wall, 3 side wall, 4 roof, 5 soffit), hit point."""
    H, W = d.shape[:2]
    t = np.full((H, W), np.inf)
    sid = np.zeros((H, W), int)

    def plane(n, k, inside, i, two_sided_id=None):
        nonlocal t
        nd = d @ n
        with np.errstate(divide="ignore", invalid="ignore"):
            tt = (k - cam @ n) / nd
        p = cam + d * tt[..., None]
        ok = (tt > 0.01) & (tt < t) & inside(p)
        t = np.where(ok, tt, t)
        sid[ok] = i
        if two_sided_id is not None:
            sid[ok & (nd > 0)] = two_sided_id

    plane(np.array([0, 0, 1.0]), 0.0, lambda p: np.hypot(p[..., 0], p[..., 1]) < 400, 1)
    plane(np.array([0, 1.0, 0]), 0.0, lambda p: (np.abs(p[..., 0]) <= HW) & (p[..., 2] >= 0) & (p[..., 2] <= WALL_H), 2)
    gable = lambda p: (p[..., 1] >= 0) & (p[..., 1] <= DEPTH) & (p[..., 2] >= 0) & (p[..., 2] <= WALL_H + np.minimum(p[..., 1], DEPTH - p[..., 1]) * PITCH)
    plane(np.array([1.0, 0, 0]), -HW, gable, 3)
    rn = np.array([0, -PITCH, 1.0]) / math.hypot(PITCH, 1.0)
    roof_k = np.array([0, -OVER, EAVE_Z]) @ rn
    plane(rn, roof_k, lambda p: (np.abs(p[..., 0]) <= HW + 0.4) & (p[..., 1] >= -OVER) & (p[..., 1] <= RIDGE_Y), 4, 5)
    # the back slope (seen over the ridge from far away) as plain roof
    rn2 = np.array([0, PITCH, 1.0]) / math.hypot(PITCH, 1.0)
    plane(rn2, np.array([0, DEPTH + OVER, EAVE_Z]) @ rn2, lambda p: (np.abs(p[..., 0]) <= HW + 0.4) & (p[..., 1] >= RIDGE_Y) & (p[..., 1] <= DEPTH + OVER), 6)
    p = cam + d * np.where(np.isfinite(t), t, 0)[..., None]
    return sid, p


def surface_inputs(name, u, v, tile, lod_px, mask):
    ts = texset(name)
    tu, tv = u / ts["tile"][0], -v / ts["tile"][1]
    lod = lod_of(tu, tv, ts["px"])
    C = ts["C"].sample(tu[mask], tv[mask], lod[mask])
    N = ts["N"].sample(tu[mask], tv[mask], lod[mask])
    M = ts["M"].sample(tu[mask], tv[mask], lod[mask])
    nz = noise_tex()
    k1, k2 = 1.0 / BH.NOISE1_M, 1.0 / BH.NOISE2_M
    l1 = lod_of(u * k1, v * k1, 512)[mask]; l2 = lod_of(u * k2, v * k2, 512)[mask]
    N1 = nz.sample(u[mask] * k1, -v[mask] * k1, l1); N2 = nz.sample(u[mask] * k2 + 0.37, -v[mask] * k2 + 0.61, l2)
    return C, N, M, N1, N2, ts


def run_material(name, u, v, mask, kind_extra):
    """BUILDMAT_CODE over the masked pixels: returns colour, rough, metal, ao, tangent normal (each over mask)."""
    C, N, M, N1, N2, ts = surface_inputs(name, u, v, None, None, mask)
    n = C.shape[0]
    shp = lambda a: np.asarray(a, float).reshape(1, n, -1)
    env = dict(C=shp(C), M=shp(M[:, :3]), HT=shp(M[:, 3]), UV=shp(np.stack([u[mask], v[mask]], -1)), uv=shp(np.stack([u[mask], v[mask]], -1)),
               TS=np.array(ts["tile"], float), N1=shp(N1[:, :3]), N1W=shp(N1[:, 3]), N2=shp(N2[:, :3]), N2W=shp(N2[:, 3]))
    for k, val in kind_extra.items():
        env[k] = shp(val[mask]) if isinstance(val, np.ndarray) and val.shape == mask.shape else (np.asarray(val, float) if np.ndim(val) else float(val))
    if "Paint" in kind_extra and np.ndim(kind_extra["Paint"]) == 1:
        env["Paint"] = np.asarray(kind_extra["Paint"], float)
    c, r, mt, ao = BH.run_np(env)
    tn = N / np.maximum(np.linalg.norm(N, axis=-1, keepdims=True), 1e-6)
    return c[0], r[0], mt[0], ao[0], tn


ATLAS = None


def render(house, dist, light, level, px=720, ss=2, before=False):
    hs = HOUSES[house]
    lv = LEVELS[level]
    sky, env = turned_sky(SKIES[light], SUN_AZ[light])
    cam, d = camera(dist, px * ss, int(px / 1.5) * ss)
    sid, p = trace(cam, d)
    Hh, Ww = sid.shape
    col = np.zeros((Hh, Ww, 3)); rough = np.ones((Hh, Ww)); metal = np.zeros((Hh, Ww)); ao = np.ones((Hh, Ww))
    nrm = np.zeros((Hh, Ww, 3)); nrm[..., 2] = 1.0
    emis = np.zeros((Hh, Ww, 3))
    glass = np.zeros((Hh, Ww), bool)
    wall_paint = srgb_lin(hs.get("paint", "#EDEAE0"))
    roof_paint = srgb_lin(hs.get("roof_paint", "#A9ADAF"))
    age, care = lv["age"], lv["care"]
    # walls
    walls = [(2, p[..., 0] + HW, p[..., 2], np.array([1.0, 0, 0]), np.array([0, 0, 1.0]), np.array([0, -1.0, 0]), 0.2, FRONT_WINDOWS, True),
             (3, DEPTH - p[..., 1], p[..., 2], np.array([0, -1.0, 0]), np.array([0, 0, 1.0]), np.array([-1.0, 0, 0]), 0.5, SIDE_WINDOWS, False)]
    for wid, u, v, T, B, Nw, north, wins, front in walls:
        m = sid == wid
        if not m.any():
            continue
        kind = BH.kind_of(hs["wall"])
        if before:
            card = CARDS[hs["wall"]]
            vc = lin_to_srgb(wall_paint if "paint" in hs else srgb_lin(card["palette"][0]))
            c, r, e = run_old("HOUSE_KIT_WALL_CODE", OLD_WALL_CODE[CARDS[hs["wall"]]["class"]], vc, u, v, m, p * 100.0)
            col[m] = c; rough[m] = r; nrm[m] = Nw; emis[m] = e
        else:
            c, r, mt, a, tn = run_material(hs["wall"], u, v, m, dict(Kind=kind, Paint=wall_paint, Bare=0.0, Age=age, Care=care, North=north, Sun=1 - north, Eave=WALL_H))
            col[m] = c; rough[m] = r; metal[m] = mt; ao[m] = a
            nrm[m] = tn[:, :1] * T + tn[:, 1:2] * B + tn[:, 2:3] * Nw
        # windows, trim and the door, cut into the wall
        uu = u if front else u
        for k, (cx, sill, ww, wh) in enumerate(wins):
            cxu = cx + HW if front else DEPTH - cx
            inwin = m & (np.abs(uu - cxu) <= ww / 2 + 0.09) & (v >= sill - 0.09) & (v <= sill + wh + 0.09)
            pane = m & (np.abs(uu - cxu) <= ww / 2) & (v >= sill) & (v <= sill + wh)
            col[inwin & ~pane] = TRIM; rough[inwin & ~pane] = 0.5; nrm[inwin & ~pane] = Nw; ao[inwin & ~pane] = 1.0
            if pane.any() and before:
                pm = np.zeros_like(m); pm[pane] = True
                c, r, e = run_old("HOUSE_KIT_WALL_CODE", 3, [0.5, 0.5, 0.5], uu - (cxu - ww / 2), v - sill, pm, p * 100.0)
                col[pane] = c; rough[pane] = r; nrm[pane] = Nw; ao[pane] = 1.0; emis[pane] = e
                gidx = np.argwhere(pane); glass[gidx[:, 0], gidx[:, 1]] = r < 0.2
            elif pane.any():
                # a double-hung sash: two panes, a 5 cm meeting rail, 4 cm sash frames; the room behind
                pu = (uu[pane] - (cxu - ww / 2)) / ww; pv = (v[pane] - sill) / wh
                frame = (np.minimum(pu, 1 - pu) * ww < 0.04) | (np.minimum(pv, 1 - pv) * wh < 0.04) | (np.abs(pv - 0.5) * wh < 0.025)
                if ww > 1.2:
                    frame |= np.abs(pu - 0.5) * ww < 0.025
                vt_world = d[pane]
                vt = np.stack([vt_world @ T, vt_world @ B, vt_world @ Nw], -1)
                seed = np.full(pu.shape, [0.137, 0.618, 0.401, 0.883][(k + wid) % 4])
                sky_lum = np.full(pu.shape, float(RS.Sky._lookup(sky._filtered(1.0), Nw[None, None, :])[0, 0].mean()) * math.pi)
                e, bl = INT.shade_np(ATLAS, np.stack([pu, pv], -1), np.broadcast_to([ww, wh], pu.shape + (2,)), seed,
                                     np.zeros_like(pu), np.zeros_like(pu), vt, 0.0, sky_lum)
                cpane = np.zeros(pu.shape + (3,)); cpane[frame] = TRIM
                col[pane] = cpane; rough[pane] = np.where(frame, 0.5, 0.05); nrm[pane] = Nw; ao[pane] = 1.0
                em = np.zeros(pu.shape + (3,)); em[~frame] = e[~frame]
                emis[pane] = em
                gl = np.zeros(pu.shape, bool); gl[~frame] = True
                gidx = np.argwhere(pane)
                glass[gidx[gl, 0], gidx[gl, 1]] = True
        if front:
            cx, sill, ww, wh = DOOR_RECT
            cxu = cx + HW
            door = m & (np.abs(u - cxu) <= ww / 2) & (v <= wh)
            dtrim = m & (np.abs(u - cxu) <= ww / 2 + 0.09) & (v <= wh + 0.09) & ~door
            col[door] = DOOR; rough[door] = 0.45; nrm[door] = Nw; ao[door] = 1.0
            col[dtrim] = TRIM; rough[dtrim] = 0.5; nrm[dtrim] = Nw; ao[dtrim] = 1.0
    # roof (front slope; the back slope only shows past the ridge from far off)
    rn = np.array([0, -PITCH, 1.0]) / math.hypot(PITCH, 1.0)
    rb = np.array([0, 1.0, PITCH]) / math.hypot(PITCH, 1.0)
    for rid, nr, sgn in ((4, rn, 1.0), (6, np.array([0, PITCH, 1.0]) / math.hypot(PITCH, 1.0), -1.0)):
        m = sid == rid
        if not m.any():
            continue
        u = p[..., 0] + HW + 0.4
        v = (p[..., 1] + OVER) * math.hypot(1, PITCH) if sgn > 0 else (DEPTH + OVER - p[..., 1]) * math.hypot(1, PITCH)
        kind = BH.kind_of(hs["roof"])
        slope_len = (RIDGE_Y + OVER) * math.hypot(1, PITCH)
        if before:
            card = CARDS[hs["roof"]]
            vc = lin_to_srgb(roof_paint if ("roof_paint" in hs or hs.get("bare")) else srgb_lin(card["palette"][0]))
            c, r, e = run_old("HOUSE_KIT_ROOF_CODE", OLD_ROOF_CODE[CARDS[hs["roof"]]["class"]], vc, u, v, m, p * 100.0, eave=0.37)
            col[m] = c; rough[m] = r; nrm[m] = nr
            continue
        c, r, mt, a, tn = run_material(hs["roof"], u, v, m, dict(Kind=kind, Paint=roof_paint, Bare=hs.get("bare", 0.0), Age=age, Care=care,
                                                                 North=0.2 if sgn > 0 else 0.8, Sun=0.9 if sgn > 0 else 0.4, Eave=slope_len))
        Bv = rb if sgn > 0 else np.array([0, -1.0, PITCH]) / math.hypot(PITCH, 1.0)
        col[m] = c; rough[m] = r; metal[m] = mt; ao[m] = a
        nrm[m] = tn[:, :1] * np.array([1.0, 0, 0]) + tn[:, 1:2] * Bv + tn[:, 2:3] * nr
    m = sid == 5
    col[m] = TRIM * 0.9; rough[m] = 0.6; nrm[m] = -rn
    # ground: a summer lawn with a little noise
    m = sid == 1
    g = 0.9 + 0.1 * RS.hash2(np.floor(p[..., 0][m] / 0.05), np.floor(p[..., 1][m] / 0.05)) + 0.1 * RS.hash2(np.floor(p[..., 0][m] / 2.0), np.floor(p[..., 1][m] / 2.0))
    col[m] = LAWN * g[:, None]; rough[m] = 0.95; nrm[m] = np.array([0, 0, 1.0])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=-1, keepdims=True), 1e-6)
    # shade: split-sum IBL (diffuse + one specular lobe, metals tint it)
    v_ = -d
    nv = np.clip((nrm * v_).sum(-1), 1e-3, 1)
    r_ = 2 * nv[..., None] * nrm - v_
    diffuse = col * (1 - metal[..., None]) * sky.irradiance(nrm) * ao[..., None]
    A, Bb = RS.env_brdf(np.clip(rough, 0.03, 1), nv)
    f0 = 0.04 * (1 - metal[..., None]) + col * metal[..., None]
    spec = sky.specular(r_, np.clip(rough, 0.03, 1)) * (f0 * A[..., None] + Bb[..., None]) * ao[..., None]
    lit = diffuse + spec + emis
    skym = sid == 0
    lit[skym] = RS.Sky._lookup(env, d[skym][None])[0]
    ncard = -np.array([d[d.shape[0] // 2, d.shape[1] // 2][0], d[d.shape[0] // 2, d.shape[1] // 2][1], 0.0])
    ncard /= np.linalg.norm(ncard)
    e_card = float((sky.irradiance(ncard[None, None, :])[0, 0] * 0.18).mean())
    img = RS.to_srgb(RS.aces(lit * 0.18 / max(e_card, 1e-6) * 0.8))
    img = img.reshape(img.shape[0] // ss, ss, img.shape[1] // ss, ss, 3).mean((1, 3))
    return img


CARDS = P.finishes()
ROOFS = {c["name"] for c in P.load()["roofs"]}
# main's house shader patterns by class (HOUSE_KIT_WALL_CODE 0 masonry, 1 siding, 2 stucco; ROOF 0 shingle, 2 metal)
OLD_WALL_CODE = {"brick": 0, "stone": 0, "lap": 1, "batten": 1, "render": 2}
OLD_ROOF_CODE = {"shingle": 0, "standing_seam": 2, "membrane": 2}


def old_code(var, rev=None):
    """HOUSE_KIT_WALL_CODE or HOUSE_KIT_ROOF_CODE from scripts/make_materials.py (main's house materials: "before")."""
    import subprocess
    if rev:
        src = subprocess.run(["git", "-C", REPO, "show", "%s:scripts/make_materials.py" % rev], capture_output=True, text=True, check=True).stdout
    else:
        src = open(os.path.join(REPO, "scripts", "make_materials.py"), encoding="utf-8").read()
    a = src.index(var + ' = """') + len(var + ' = """')
    return src[a:src.index('"""', a)]


def run_old(var, code_id, vc_srgb, u, v, mask, p_cm, eave=WALL_H, seed=0.37):
    """Main's house material over the masked pixels (flat normal): returns colour, roughness, emissive."""
    import hlsl_np
    n = int(mask.sum())
    shp = lambda a: np.asarray(a, float).reshape(1, n, -1)
    env = dict(VC=np.broadcast_to(np.asarray(vc_srgb, float), (1, n, 3)).copy(), VA=np.full((1, n, 1), code_id / 255.0), UV=shp(np.stack([u[mask], v[mask]], -1)),
               uv=shp(np.stack([u[mask], v[mask]], -1)), Tag=np.array([eave, seed]), WP=shp(p_cm[mask]), Night=0.0)
    ns = hlsl_np.run(old_code(var), env)
    full = lambda a, k: np.broadcast_to(np.asarray(a, float), (1, n, k)).astype(float)[0]
    e = full(ns["Emit"], 3) if "Emit" in ns else np.zeros((n, 3))
    return full(ns["c"], 3), full(ns["Out"], 1)[:, 0], e


def lin_to_srgb(c):
    c = np.clip(np.asarray(c, float), 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def swatch(name, level, light, px=600, ss=2, w_m=1.6, h_m=1.2):
    """A finish straight on, from 2 m, w_m x h_m of it from the ground line (walls) or the eave (roofs) up: the wear
    ladder's view. Walls face the low sun's side; roofs tilt up 26.6 degrees (6:12)."""
    lv = LEVELS[level]
    sky, env = turned_sky(SKIES[light], SUN_AZ[light])
    W, H = px * ss, int(px * ss * h_m / w_m)
    u = (np.arange(W) + 0.5) / W * w_m + 0.3
    v = h_m - (np.arange(H) + 0.5) / H * h_m
    U, V = np.meshgrid(u, v)
    m = np.ones(U.shape, bool)
    roof = name in ROOFS
    T = np.array([1.0, 0, 0])
    Nw = np.array([0, -PITCH, 1.0]) / math.hypot(PITCH, 1.0) if roof else np.array([0, -1.0, 0])
    B = np.cross(Nw, T)
    paint = srgb_lin(CARDS[name].get("paint_examples", ["#EDEAE0"])[0])
    bare = 1.0 if CARDS[name]["class"] == "standing_seam" else 0.0
    c, r, mt, a, tn = run_material(name, U, V, m, dict(Kind=BH.kind_of(name), Paint=paint, Bare=bare, Age=lv["age"], Care=lv["care"],
                                                        North=0.3, Sun=0.7, Eave=5.0 if roof else WALL_H))
    c = c.reshape(H, W, 3); r = r.reshape(H, W); mt = mt.reshape(H, W); a = a.reshape(H, W)
    tn = tn.reshape(H, W, 3)
    nrm = tn[..., :1] * T + tn[..., 1:2] * B + tn[..., 2:3] * Nw
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    v_ = np.broadcast_to(-(-Nw), nrm.shape)
    nv = np.clip((nrm * v_).sum(-1), 1e-3, 1)
    r_ = 2 * nv[..., None] * nrm - v_
    diffuse = c * (1 - mt[..., None]) * sky.irradiance(nrm) * a[..., None]
    A, Bb = RS.env_brdf(np.clip(r, 0.03, 1), nv)
    f0 = 0.04 * (1 - mt[..., None]) + c * mt[..., None]
    spec = sky.specular(r_, np.clip(r, 0.03, 1)) * (f0 * A[..., None] + Bb[..., None]) * a[..., None]
    e_card = float((sky.irradiance(Nw[None, None, :])[0, 0] * 0.18).mean())
    img = RS.to_srgb(RS.aces((diffuse + spec) * 0.18 / max(e_card, 1e-6) * 0.8))
    return img.reshape(H // ss, ss, W // ss, ss, 3).mean((1, 3))


def main():
    global ATLAS
    ap = argparse.ArgumentParser()
    ap.add_argument("houses", nargs="*")
    ap.add_argument("--px", type=int, default=720)
    ap.add_argument("--ss", type=int, default=2)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--levels", default="L2")
    ap.add_argument("--dists", default="3,15,60")
    ap.add_argument("--lights", default="midday,lowsun,overcast")
    ap.add_argument("--before", action="store_true", help="main's house materials (HOUSE_KIT_*_CODE) for comparison")
    ap.add_argument("--ladder", action="store_true", help="wear ladder swatches L0..L4 for every finish instead")
    P.add_arg(ap)
    a = ap.parse_args()
    ATLAS = INT.load_atlas()
    os.makedirs(a.out, exist_ok=True)
    meta_p = os.path.join(a.out, "render.json")
    meta = json.load(open(meta_p)) if os.path.exists(meta_p) else {}
    if a.ladder:
        for name in (a.houses or list(CARDS)):
            for lid in LEVELS:
                img = swatch(name, lid, "overcast")
                fn = "ladder_%s_%s.png" % (name, lid)
                Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(os.path.join(a.out, fn))
                print(fn, flush=True)
        return
    for house in (a.houses or list(HOUSES)):
        for level in a.levels.split(","):
            for light in a.lights.split(","):
                for dist in [float(x) for x in a.dists.split(",")]:
                    img = render(house, dist, light, level, a.px, a.ss, before=a.before)
                    name = "%s%s_%s_%s_%dm.png" % ("before_" if a.before else "", house, level, light, dist)
                    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(os.path.join(a.out, name))
                    meta[name] = dict(house=house, level=level, light=light, dist=dist, before=a.before, **HOUSES[house])
                    print(name, flush=True)
    json.dump(meta, open(meta_p, "w"), indent=1)


if __name__ == "__main__":
    main()
