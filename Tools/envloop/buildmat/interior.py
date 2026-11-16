"""Fake interiors for house windows (Track E2, docs/envloop/buildmat): a room behind every pane with no extra geometry,
lit at dusk and night. Builds the room atlas and holds the shader maths (HLSL for the engine, the numpy twin that the
renders in this folder use).

    python3 -I Tools/envloop/buildmat/interior.py [--cell 256] [--out DIR]     # writes T_RoomAtlas.png (RGBA)

The method is interior mapping (van Dongen 2008) with a flat atlas instead of a cubemap. Every room is the same box,
ROOM_W x ROOM_H x ROOM_D metres; the window is a hole in its front face. Each atlas cell is a pinhole picture of one room
taken from the camera at (0, ROOM_H / 2, +F) in front of the front face, framed so the front face fills the cell. So a
point (x, y, z) inside the room (z <= 0, into the room) appears in its cell at

    x' = x * F / (F - z) / (ROOM_W / 2),   y' = (y - ROOM_H / 2) * F / (F - z) / (ROOM_H / 2)        (-1..1)

and the shader, which finds where the view ray through the pane meets the room's walls, floor or ceiling, looks that
point up exactly where the picture has it. The back wall fills the middle F / (F + ROOM_D) of the cell (a half with
F = ROOM_D). Furniture is painted into the pictures, so it sits flat on the walls and floor: from the water, at 15 m and
more, that is invisible.

Atlas: 4 x 4 cells (living rooms, bedrooms, kitchens, dining, office, stairs, empty), RGB = the room as lit by daylight
through the window (sRGB), A = how much the room's own lamps light it (linear 0..1; the night look is RGB x A x warm).
Image row 0 is the top. Cells are picked per window by its seed and mirrored left-right by a second bit.
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(REPO, "Data", "BuildMat", "raw", "out")

ROOM_W, ROOM_H, ROOM_D = 4.0, 2.7, 4.0
F = ROOM_D
GRID = 4
SILL = 0.9          # metres above the room's floor to the bottom of a window pane

# ------------------------------------------------------------------ the shader (engine)

INTERIOR_CODE = """
// Inputs: UVp (pane 0..1, u right, v up, from outside), Size (pane width, height m: UV1), Seed (vertex colour G),
// Obscure (vertex colour B), Door (vertex colour A), Vt (camera to pixel, tangent space: x along u, y up, z out of the
// wall), Atlas (T_RoomAtlas, Texture2D), AtlasSampler, Night (MPC_World), SkyLum (the sky's luminance at the wall).
// Outputs: return emissive interior (linear), Blind (0..1 how much a blind or curtain covers this pixel).
const float RW = 4.0, RH = 2.7, RD = 4.0, FF = 4.0;
float cx = (frac(Seed * 7.13) - 0.5) * max(RW - Size.x - 0.6, 0.0);
float cy = lerp(0.9, 0.0, Door) + 0.5 * Size.y;
float3 P = float3(cx + (UVp.x - 0.5) * Size.x, cy + (UVp.y - 0.5) * Size.y, 0.0);
float3 d = normalize(float3(Vt.x, Vt.y, min(Vt.z, -0.02)));
float tX = ((d.x > 0.0 ? 0.5 * RW : -0.5 * RW) - P.x) / (abs(d.x) > 1e-4 ? d.x : 1e-4);
float tY = ((d.y > 0.0 ? RH : 0.0) - P.y) / (abs(d.y) > 1e-4 ? d.y : 1e-4);
float tZ = -RD / d.z;
float t = min(min(abs(tX), abs(tY)), tZ);
float3 H = P + d * t;
float s = FF / (FF - H.z);
float2 q = float2(H.x * s / (0.5 * RW), (H.y - 0.5 * RH) * s / (0.5 * RH)) * 0.5 + 0.5;
float cell = floor(frac(Seed * 13.37) * 16.0);
q.x = frac(Seed * 3.71) > 0.5 ? 1.0 - q.x : q.x;
float2 auv = (float2(fmod(cell, 4.0), floor(cell / 4.0)) + float2(clamp(q.x, 0.002, 0.998), 1.0 - clamp(q.y, 0.002, 0.998))) / 4.0;
float4 room = Texture2DSampleLevel(Atlas, AtlasSampler, auv, 0.0);
float3 alb = room.rgb;   // the sampler is sRGB: linear here
float on = step(frac(Seed * 29.71), 0.45) * smoothstep(0.4, 0.95, Night);
// blinds (25 mm slats, lowered to a random height) or curtains (two side panels with folds), per window
float kindB = frac(Seed * 5.17);
float lower = 1.0 - frac(Seed * 17.9) * 0.8;
float slat = step(0.35, frac(UVp.y * Size.y / 0.025));
float blind = kindB < 0.35 ? step(lower, UVp.y) * (0.75 + 0.25 * slat) : 0.0;
float side = 0.12 + 0.25 * frac(Seed * 41.3);
float folds = 0.85 + 0.15 * sin(UVp.x * Size.x / 0.06 * 6.2832);
float curtain = (kindB > 0.35 && kindB < 0.75) ? (step(UVp.x, side) + step(1.0 - side, UVp.x)) * folds : 0.0;
Blind = saturate(max(blind, curtain) + Obscure);
float3 day = alb * SkyLum * 0.12;
float3 lamp = alb * room.a * float3(1.0, 0.72, 0.45) * 3.0 * on;
float3 cloth = float3(0.75, 0.72, 0.66) * (0.3 + 0.7 * frac(Seed * 61.1));
float3 front = cloth * (SkyLum * 0.25 + 1.2 * on * float3(1.0, 0.75, 0.5));
return lerp(day + lamp, front, Blind);
"""

# ------------------------------------------------------------------ the numpy twin


def room_uv(uvp, size, seed, door, vt):
    """Atlas UV (0..1, row 0 top) and the room hit point, for arrays: uvp (..., 2), size (..., 2), seed (...),
    door (...), vt (..., 3) camera-to-pixel in tangent space. The same lines as INTERIOR_CODE."""
    cx = (np.modf(seed * 7.13)[0] - 0.5) * np.maximum(ROOM_W - size[..., 0] - 0.6, 0.0)
    cy = (1 - door) * SILL + 0.5 * size[..., 1]
    P = np.stack([cx + (uvp[..., 0] - 0.5) * size[..., 0], cy + (uvp[..., 1] - 0.5) * size[..., 1], np.zeros_like(cx)], -1)
    d = np.stack([vt[..., 0], vt[..., 1], np.minimum(vt[..., 2], -0.02)], -1)
    d = d / np.linalg.norm(d, axis=-1, keepdims=True)
    sx = np.where(np.abs(d[..., 0]) > 1e-4, d[..., 0], 1e-4)
    sy = np.where(np.abs(d[..., 1]) > 1e-4, d[..., 1], 1e-4)
    tX = (np.where(d[..., 0] > 0, 0.5 * ROOM_W, -0.5 * ROOM_W) - P[..., 0]) / sx
    tY = (np.where(d[..., 1] > 0, ROOM_H, 0.0) - P[..., 1]) / sy
    tZ = -ROOM_D / d[..., 2]
    t = np.minimum(np.minimum(np.abs(tX), np.abs(tY)), tZ)
    H = P + d * t[..., None]
    s = F / (F - H[..., 2])
    qx = H[..., 0] * s / (0.5 * ROOM_W) * 0.5 + 0.5
    qy = (H[..., 1] - 0.5 * ROOM_H) * s / (0.5 * ROOM_H) * 0.5 + 0.5
    cell = np.floor(np.modf(seed * 13.37)[0] * 16.0)
    qx = np.where(np.modf(seed * 3.71)[0] > 0.5, 1.0 - qx, qx)
    au = (np.fmod(cell, 4.0) + np.clip(qx, 0.002, 0.998)) / 4.0
    av = (np.floor(cell / 4.0) + 1.0 - np.clip(qy, 0.002, 0.998)) / 4.0
    return np.stack([au, av], -1), H


def shade_np(atlas, uvp, size, seed, door, obscure, vt, night, sky_lum):
    """INTERIOR_CODE on numpy: returns (emissive linear rgb, blind)."""
    auv, _ = room_uv(uvp, size, seed, door, vt)
    h, w = atlas.shape[:2]
    xi = np.clip((auv[..., 0] * w).astype(int), 0, w - 1)
    yi = np.clip((auv[..., 1] * h).astype(int), 0, h - 1)
    room = atlas[yi, xi]
    alb = room[..., :3]; la = room[..., 3]
    fr = lambda a: np.modf(a)[0]
    on = (fr(seed * 29.71) <= 0.45) * np.clip((night - 0.4) / 0.55, 0, 1)
    kindB = fr(seed * 5.17)
    lower = 1.0 - fr(seed * 17.9) * 0.8
    slat = (fr(uvp[..., 1] * size[..., 1] / 0.025) >= 0.35).astype(float)
    blind = np.where(kindB < 0.35, (uvp[..., 1] >= lower) * (0.75 + 0.25 * slat), 0.0)
    side = 0.12 + 0.25 * fr(seed * 41.3)
    folds = 0.85 + 0.15 * np.sin(uvp[..., 0] * size[..., 0] / 0.06 * 2 * np.pi)
    curtain = np.where((kindB > 0.35) & (kindB < 0.75), ((uvp[..., 0] <= side) + (uvp[..., 0] >= 1 - side)) * folds, 0.0)
    bl = np.clip(np.maximum(blind, curtain) + obscure, 0, 1)
    day = alb * (sky_lum * 0.12)[..., None]
    lamp = alb * (la * on * 3.0)[..., None] * np.array([1.0, 0.72, 0.45])
    cloth = np.array([0.75, 0.72, 0.66]) * (0.3 + 0.7 * fr(seed * 61.1))[..., None]
    front = cloth * ((sky_lum * 0.25)[..., None] + (1.2 * on)[..., None] * np.array([1.0, 0.75, 0.5]))
    return day + lamp + (front - day - lamp) * bl[..., None], bl


# ------------------------------------------------------------------ the room atlas

def srgb(h):
    h = h.lstrip("#")
    c = np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


WALLS = ["#D8D2C6", "#E9E6DE", "#CFC6B6", "#C9D2D4", "#D9CDB8", "#BFC5B8", "#E4DCCB", "#A9B4BC"]
FLOORS = {"wood": "#8A6446", "oak": "#A8805A", "carpet": "#B4AA98", "tile": "#C9C1B2", "dark": "#5A4535"}
FURN = ["#5E5A55", "#7B6B5A", "#3E4247", "#A39684", "#6A4E3A", "#2F3E4F", "#8C7D6B", "#C8BFAF"]

# Each room: (name, wall colour index, floor, lamp spots [(x, y, z, strength)], boxes [(x0, x1, y0, y1, z0, z1, colour)])
# x across (-2..2), y up (0..2.7), z into the room (0..-4). Boxes are furniture against the walls and floor.
ROOMS = [
    ("living", 0, "wood", [(-1.2, 1.4, -3.4, 1.0)], [(-1.6, 1.0, 0.0, 0.85, -4.0, -3.1, 2), (-1.9, -1.5, 0.0, 0.6, -2.4, -1.6, 4), (1.3, 1.9, 0.0, 1.5, -2.6, -1.4, 6), (-0.6, 0.6, 1.3, 1.9, -4.0, -3.97, 7)]),
    ("bedroom", 1, "carpet", [(1.5, 1.2, -3.8, 0.9)], [(-1.0, 0.9, 0.0, 0.6, -4.0, -1.9, 7), (-1.0, 0.9, 0.6, 1.2, -4.0, -3.85, 4), (1.3, 1.9, 0.0, 0.7, -4.0, -3.5, 1), (-1.9, -1.5, 0.0, 1.9, -1.8, -0.8, 6)]),
    ("kitchen", 2, "tile", [(0.0, 2.6, -2.0, 1.2)], [(-2.0, 2.0, 0.0, 0.9, -4.0, -3.4, 7), (-2.0, 2.0, 1.4, 2.1, -4.0, -3.7, 3), (-0.6, 0.6, 0.0, 0.9, -2.4, -1.6, 0)]),
    ("dining", 3, "wood", [(0.0, 2.3, -2.2, 1.1)], [(-0.9, 0.9, 0.7, 0.76, -2.8, -1.6, 4), (-0.9, 0.9, 0.0, 0.7, -2.75, -2.65, 4), (-0.5, 0.5, 1.2, 1.9, -4.0, -3.97, 1), (1.4, 1.95, 0.0, 1.9, -3.9, -2.9, 6)]),
    ("office", 4, "oak", [(1.0, 1.1, -3.6, 1.0)], [(0.4, 1.9, 0.0, 0.75, -4.0, -3.3, 6), (-1.9, -1.5, 0.0, 2.1, -4.0, -1.5, 1), (0.8, 1.4, 0.75, 1.15, -3.95, -3.9, 2)]),
    ("stairs", 5, "carpet", [(0.0, 2.5, -2.5, 0.8)], [(-2.0, 2.0, 0.0, 0.2, -4.0, -3.7, 3), (-2.0, 2.0, 0.2, 0.4, -4.0, -3.45, 3), (-2.0, 2.0, 0.4, 0.6, -4.0, -3.2, 3), (-2.0, 2.0, 0.6, 0.8, -4.0, -2.95, 3), (-0.8, 0.2, 1.2, 1.8, -4.0, -3.97, 5)]),
    ("living2", 6, "dark", [(1.4, 1.3, -1.8, 1.0), (-1.4, 2.6, -2.5, 0.5)], [(-1.9, -1.0, 0.0, 0.85, -3.6, -0.9, 0), (-0.7, 0.7, 0.0, 0.45, -2.4, -1.6, 4), (-0.8, 0.8, 0.5, 1.1, -4.0, -3.92, 2), (-1.0, 1.0, 0.0, 0.5, -4.0, -3.6, 4)]),
    ("bedroom2", 7, "wood", [(-1.6, 1.2, -3.6, 0.8)], [(-0.2, 1.9, 0.0, 0.55, -4.0, -2.0, 1), (-0.2, 1.9, 0.55, 1.0, -4.0, -3.85, 4), (-1.95, -1.4, 0.0, 1.3, -3.0, -2.0, 6)]),
    ("empty", 1, "oak", [(0.0, 2.6, -2.0, 0.9)], []),
    ("family", 4, "carpet", [(-1.5, 1.3, -3.7, 1.0)], [(-1.2, 1.2, 0.0, 0.8, -4.0, -3.15, 5), (1.4, 1.95, 0.0, 0.8, -3.0, -1.6, 5), (-0.5, 0.5, 0.0, 0.42, -2.4, -1.8, 4), (-0.7, 0.7, 1.2, 1.7, -4.0, -3.97, 2)]),
    ("kitchen2", 0, "tile", [(0.0, 2.6, -2.4, 1.2)], [(-2.0, -1.4, 0.0, 0.9, -4.0, -0.5, 7), (-2.0, 2.0, 0.0, 0.9, -4.0, -3.4, 7), (0.9, 1.9, 0.0, 2.0, -4.0, -3.3, 7)]),
    ("hall", 2, "wood", [(0.0, 2.5, -2.0, 0.7)], [(-0.45, 0.45, 0.0, 2.05, -4.0, -3.98, 4), (1.5, 1.95, 0.0, 0.8, -2.5, -1.5, 4), (-1.95, -1.9, 1.3, 1.8, -2.5, -1.8, 2)]),
    ("bedroom3", 3, "carpet", [(1.5, 1.2, -3.8, 0.9), (-1.5, 1.2, -3.8, 0.5)], [(-0.9, 0.9, 0.0, 0.6, -4.0, -2.0, 1), (-0.9, 0.9, 0.6, 1.3, -4.0, -3.85, 6), (1.2, 1.9, 0.0, 0.6, -4.0, -3.6, 4), (-1.9, -1.2, 0.0, 0.6, -4.0, -3.6, 4)]),
    ("study", 5, "dark", [(0.6, 1.1, -3.4, 1.0)], [(-2.0, 2.0, 0.0, 2.3, -4.0, -3.7, 4), (-0.5, 1.2, 0.0, 0.75, -2.8, -2.1, 1)]),
    ("dim", 6, "wood", [], [(-1.6, 1.0, 0.0, 0.85, -4.0, -3.1, 3)]),
    ("sunroom", 7, "tile", [(0.0, 2.5, -2.0, 0.9)], [(-1.6, -0.4, 0.0, 0.8, -3.6, -2.8, 7), (0.4, 1.6, 0.0, 0.8, -3.6, -2.8, 7), (-0.3, 0.3, 0.0, 0.45, -2.6, -2.0, 4), (-1.9, -1.5, 0.0, 1.2, -4.0, -3.6, 2)]),
]


def render_room(room, cell):
    """Ray-cast one room from the atlas camera: returns (cell, cell, 4) floats: linear daylight colour, lamp amount."""
    name, wall_i, floor_k, lamps, boxes = room
    yy, xx = np.mgrid[0:cell, 0:cell]
    xp = (xx + 0.5) / cell * 2 - 1
    yp = 1 - (yy + 0.5) / cell * 2
    cam = np.array([0.0, ROOM_H / 2, F])
    P0 = np.stack([xp * ROOM_W / 2, ROOM_H / 2 + yp * ROOM_H / 2, np.zeros_like(xp)], -1)
    d = P0 - cam
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    o = P0
    big = 1e9
    t_best = np.full(xp.shape, big)
    nrm = np.zeros(xp.shape + (3,))
    col = np.zeros(xp.shape + (3,))
    wallc = srgb(WALLS[wall_i]); floorc = srgb(FLOORS[floor_k]); ceilc = srgb("#ECEAE4")

    def hit_plane(axis, val, normal, colour, inside):
        nonlocal t_best
        dd = d[..., axis]
        with np.errstate(divide="ignore", invalid="ignore"):
            t = np.where(np.abs(dd) > 1e-9, (val - o[..., axis]) / dd, big)
        p = o + d * t[..., None]
        ok = (t > 1e-5) & (t < t_best) & inside(p)
        t_best = np.where(ok, t, t_best)
        nrm[ok] = normal
        c = colour(p) if callable(colour) else colour
        col[ok] = (c[ok] if np.ndim(c) == 3 else c)

    inroom = lambda p: (np.abs(p[..., 0]) <= ROOM_W / 2 + 1e-6) & (p[..., 1] >= -1e-6) & (p[..., 1] <= ROOM_H + 1e-6) & (p[..., 2] <= 1e-6) & (p[..., 2] >= -ROOM_D - 1e-6)
    boards = lambda p: floorc * (0.9 + 0.2 * np.modf(np.abs(np.sin(np.floor(p[..., 0] / 0.14) * 12.9) * 4375.5))[0])[..., None] if floor_k in ("wood", "oak", "dark") else floorc * np.ones(p.shape)
    hit_plane(0, -ROOM_W / 2, [1, 0, 0], wallc, inroom)
    hit_plane(0, ROOM_W / 2, [-1, 0, 0], wallc, inroom)
    hit_plane(1, 0.0, [0, 1, 0], boards, inroom)
    hit_plane(1, ROOM_H, [0, -1, 0], ceilc, inroom)
    hit_plane(2, -ROOM_D, [0, 0, 1], wallc * 0.97, inroom)
    for (x0, x1, y0, y1, z0, z1, ci) in boxes:
        fc = srgb(FURN[ci])
        for axis, lo, hi in ((0, x0, x1), (1, y0, y1), (2, z0, z1)):
            for val, sgn in ((lo, -1), (hi, 1)):
                nn = [0, 0, 0]; nn[axis] = sgn
                a1, a2 = [k for k in range(3) if k != axis]
                lims = {0: (x0, x1), 1: (y0, y1), 2: (z0, z1)}
                inside = lambda p, a1=a1, a2=a2: (p[..., a1] >= lims[a1][0]) & (p[..., a1] <= lims[a1][1]) & (p[..., a2] >= lims[a2][0]) & (p[..., a2] <= lims[a2][1])
                hit_plane(axis, val, nn, fc, inside)
    p = o + d * np.minimum(t_best, 50)[..., None]
    # daylight: from the window (the front face), falling off into the room; a soft corner darkening
    depth = -p[..., 2]
    day = 0.25 + 0.75 * np.exp(-depth / 2.2)
    edge = np.minimum.reduce([ROOM_W / 2 - np.abs(p[..., 0]), p[..., 1], ROOM_H - p[..., 1], ROOM_D + p[..., 2]])
    occ = 0.6 + 0.4 * np.clip(edge / 0.35, 0, 1)
    # lamps: point lights with a cosine term; strength scaled so a lit room reads at about 0.5-0.9
    lamp = np.zeros(xp.shape)
    for (lx, ly, lz, ls) in lamps:
        L = np.array([lx, ly, lz]) - p
        dist = np.linalg.norm(L, axis=-1)
        ndl = np.clip((nrm * L).sum(-1) / np.maximum(dist, 1e-6), 0, 1)
        lamp += ls * (0.35 + 0.65 * ndl) * 2.2 / (1.0 + dist * dist)
        glow = np.exp(-((xp - lx * F / (F - lz) / (ROOM_W / 2)) ** 2 + (yp - (ly - ROOM_H / 2) * F / (F - lz) / (ROOM_H / 2)) ** 2) / 0.002)
        lamp += 3.0 * glow * ls
    lamp = np.clip(lamp * occ, 0, 1)
    rgb = np.clip(col * (day * occ)[..., None], 0, 1)
    return np.concatenate([rgb, lamp[..., None]], -1)


def build_atlas(cell=256):
    atlas = np.zeros((GRID * cell, GRID * cell, 4))
    for i, room in enumerate(ROOMS):
        r, c = divmod(i, GRID)
        atlas[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell] = render_room(room, cell)
    return atlas


def to8(atlas):
    rgb = np.where(atlas[..., :3] <= 0.0031308, atlas[..., :3] * 12.92, 1.055 * np.clip(atlas[..., :3], 0, 1) ** (1 / 2.4) - 0.055)
    return (np.concatenate([rgb, atlas[..., 3:]], -1) * 255 + 0.5).astype(np.uint8)


def load_atlas(path=None):
    """The atlas back as linear floats (RGB decoded from sRGB, A linear)."""
    a = np.asarray(Image.open(path or os.path.join(OUT, "T_RoomAtlas.png")), np.float64) / 255.0
    rgb = np.where(a[..., :3] <= 0.04045, a[..., :3] / 12.92, ((a[..., :3] + 0.055) / 1.055) ** 2.4)
    return np.concatenate([rgb, a[..., 3:]], -1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", type=int, default=256)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    atlas = build_atlas(a.cell)
    Image.fromarray(to8(atlas), "RGBA").save(os.path.join(a.out, "T_RoomAtlas.png"))
    meta_p = os.path.join(a.out, "textures.json")
    meta = json.load(open(meta_p)) if os.path.exists(meta_p) else {}
    meta["T_RoomAtlas"] = dict(kind="atlas", px=[GRID * a.cell] * 2, grid=GRID, room_m=[ROOM_W, ROOM_H, ROOM_D], f_m=F,
                               rooms=[r[0] for r in ROOMS])
    json.dump(meta, open(meta_p, "w"), indent=1)
    print("atlas", atlas.shape)


if __name__ == "__main__":
    main()
