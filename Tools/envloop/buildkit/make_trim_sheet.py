"""The building kit's shared trim sheet (Track E, shore plan Nov 16 2026): one 2048 x 2048 set at 4 px/cm that every
house part maps onto (casings, fascia, sashes, doors, gutters, vents, rails, steps), so one good texture improves every
house and the whole kit is one material and one draw per house.

    python3 Tools/envloop/buildkit/make_trim_sheet.py [out dir]      (numpy + Pillow; no Blender, no photos)

Fifteen horizontal bands, 128 px (32 cm) tall, each tiling along U (5.12 m) and inside its own height, one per surface
kind, then a bottom row of 128 px cells for parts mapped whole (fan grille, meter face, lamp glass, round vent, kick
plate). 4 px/cm is 2.5 mm per pixel, four times the plan's 1 cm hero rule: trim is narrow and seen edge-on.

  T_HouseTrim_C   base colour (sRGB). Painted bands are a near-white the house's paint colour multiplies.
  T_HouseTrim_N   tangent-space normal (OpenGL, green up), like the boat kit's detail maps
  T_HouseTrim_M   R cavity (0 in grooves), G roughness, B paint mask (1 = takes the paint role's colour), A opacity
                  (insect screen and lattice holes)
  trim.json       bands (name, pixel rows, UV rows, paint mask) and cells; hk_trim.py reads it

Everything is drawn from seeded noise and simple shapes, so it is ours (no third-party texture inside). The wall and
roof textures are the materials thread's (slots.json).
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "Artifacts", "buildkit", "trim")
W = H = 2048
PX_PER_M = 400.0                      # 4 px/cm
BAND_H = 128
# name, paint mask (1 = takes the paint role's colour), base colour (linear-ish sRGB 0..1), roughness, what it is
BANDS = [
    ("paint_smooth", 1, (0.92, 0.92, 0.90), 0.55, "milled trim, fascia, casings, columns: roller-painted smooth"),
    ("paint_grain",  1, (0.91, 0.91, 0.89), 0.62, "fibre-cement trim boards with an embossed cedar grain"),
    ("vinyl",        1, (0.95, 0.95, 0.93), 0.38, "vinyl window frames and sashes, faint extrusion lines"),
    ("aluminium",    1, (0.93, 0.93, 0.92), 0.42, "painted seamless aluminium gutters and downspouts"),
    ("galvanised",   0, (0.62, 0.64, 0.65), 0.50, "galvanised steel: spangle, vents, flashing, meter bases, turbine vents"),
    ("black_iron",   0, (0.035, 0.035, 0.038), 0.62, "powder-coated iron and cast aluminium: rails, lamps, hinges, pulls"),
    ("bronze",       0, (0.105, 0.085, 0.065), 0.40, "dark bronze anodised aluminium: modern frames, slider frames"),
    ("cedar",        0, (0.36, 0.20, 0.11), 0.70, "stained cedar: posts, plank doors, porch ceilings"),
    ("concrete",     0, (0.58, 0.57, 0.54), 0.85, "broom-finished concrete: steps, pads, slab edge"),
    ("cast_stone",   0, (0.78, 0.74, 0.66), 0.80, "cast stone sills and keystones on brick houses"),
    ("rubber",       0, (0.03, 0.03, 0.03), 0.90, "weatherstrip, garage door seal, line set insulation"),
    ("screen",       0, (0.20, 0.21, 0.22), 0.70, "insect screen, alpha 0.45 (A)"),
    ("coil_guard",   0, (0.30, 0.31, 0.31), 0.55, "condenser coil behind its wire guard"),
    ("louvre",       1, (0.92, 0.92, 0.90), 0.55, "louvre slats along U, 64 mm pitch: shutters and gable vents (U runs up the part)"),
    ("lattice",      1, (0.93, 0.93, 0.91), 0.50, "45 degree lattice, 38 mm strips, holes in A: pier-and-beam skirts"),
]
CELLS = ["fan_grille", "meter_face", "lamp_glass", "round_vent", "kick_plate", "dial_gauge"]
CELL_Y0 = BAND_H * len(BANDS)           # 1920


def periodic_noise(w, h, cx, cy, octaves, seed, persistence=0.5):
    """Value noise tiling over w x h with cx x cy cells at the first octave, smoothstep-interpolated, 0..1."""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w))
    amp, total = 1.0, 0.0
    for o in range(octaves):
        nx, ny = cx * 2 ** o, cy * 2 ** o
        if nx > w or ny > h:
            break
        lat = rng.random((ny, nx))
        xi = np.arange(w) * nx / w
        yi = np.arange(h) * ny / h
        x0, y0 = np.floor(xi).astype(int), np.floor(yi).astype(int)
        fx, fy = xi - x0, yi - y0
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        x1, y1 = (x0 + 1) % nx, (y0 + 1) % ny
        a = lat[np.ix_(y0, x0)]
        b = lat[np.ix_(y0, x1)]
        c = lat[np.ix_(y1, x0)]
        d = lat[np.ix_(y1, x1)]
        top = a + (b - a) * fx[None, :]
        bot = c + (d - c) * fx[None, :]
        out += amp * (top + (bot - top) * fy[:, None])
        total += amp
        amp *= persistence
    return out / total


def voronoi_cells(w, h, n, seed):
    """Periodic Voronoi: cell id and distance-to-edge proxy (F2 - F1) in px, tiling over w x h."""
    rng = np.random.default_rng(seed)
    pts = rng.random((n, 2)) * (w, h)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    f1 = np.full((h, w), 1e9, np.float32)
    f2 = np.full((h, w), 1e9, np.float32)
    idx = np.zeros((h, w), np.int32)
    for i, (px, py) in enumerate(pts):
        dx = np.abs(xx - px)
        dx = np.minimum(dx, w - dx)
        dy = np.abs(yy - py)
        dy = np.minimum(dy, h - dy)
        d = np.sqrt(dx * dx + dy * dy)
        closer = d < f1
        f2 = np.where(closer, f1, np.minimum(f2, d))
        idx = np.where(closer, i, idx)
        f1 = np.where(closer, d, f1)
    return idx, f2 - f1


def band_maps(name, seed):
    """Height (metres of relief, small), colour multiplier, roughness offset, cavity and alpha for one band (BAND_H x W)."""
    h, w = BAND_H, W
    v = np.arange(h)[:, None] / PX_PER_M + np.zeros((1, w))
    u = np.arange(w)[None, :] / PX_PER_M + np.zeros((h, 1))
    height = np.zeros((h, w))
    tint = np.ones((h, w))
    rough = np.zeros((h, w))
    cav = np.ones((h, w))
    alpha = np.ones((h, w))
    fine = periodic_noise(w, h, 256, 8, 4, seed)            # 2 cm cells: paint and powder texture
    broad = periodic_noise(w, h, 16, 1, 3, seed + 1)         # 32 cm cells: colour drift
    if name in ("paint_smooth", "vinyl", "aluminium"):
        height += (fine - 0.5) * (0.00010 if name == "paint_smooth" else 0.00004)
        tint *= 0.985 + 0.03 * broad
        rough += (fine - 0.5) * 0.08
        if name == "vinyl":
            lines = (np.sin(v * 2 * math.pi / 0.004) > 0.995).astype(float)
            height += lines * 0.00002
        if name == "aluminium":
            streak = periodic_noise(w, h, 512, 2, 2, seed + 3)
            rough += (streak - 0.5) * 0.12
    elif name == "paint_grain":
        grain = periodic_noise(w, h, 24, 40, 5, seed + 5, 0.6)          # long along U, tight across
        rings = np.sin((v + 0.02 * np.sin(u * 2 * math.pi / 0.64)) * 2 * math.pi / 0.006 + grain * 9.0)
        height += (rings * 0.5 + 0.5) * 0.00025 + (fine - 0.5) * 0.00008
        cav *= 0.93 + 0.07 * (rings * 0.5 + 0.5)
        rough += (rings * 0.5 + 0.5 - 0.5) * 0.06
    elif name == "galvanised":
        cid, edge = voronoi_cells(w, h, 900, seed + 7)
        rng = np.random.default_rng(seed + 8)
        shade = rng.random(cid.max() + 1)[cid]
        tint *= 0.88 + 0.22 * shade
        rough += (shade - 0.5) * 0.35
        height += np.clip(1.0 - edge / 2.0, 0, 1) * 0.00003
        tint *= 0.97 + 0.06 * broad
    elif name == "black_iron":
        height += (periodic_noise(w, h, 1024, 32, 2, seed + 9) - 0.5) * 0.00012
        rough += (fine - 0.5) * 0.1
    elif name == "bronze":
        brush = periodic_noise(w, h, 4, 128, 3, seed + 11)
        tint *= 0.94 + 0.12 * brush
        rough += (brush - 0.5) * 0.12
    elif name == "cedar":
        grain = periodic_noise(w, h, 10, 24, 5, seed + 13, 0.6)
        rings = np.sin((v + 0.03 * grain) * 2 * math.pi / 0.009 + grain * 14.0)
        tint *= 0.78 + 0.22 * (rings * 0.5 + 0.5) + 0.12 * (broad - 0.5)
        # a few knots, tiling
        rng = np.random.default_rng(seed + 14)
        for _ in range(6):
            kx, ky, kr = rng.random() * w, rng.random() * h, 6 + rng.random() * 10
            dx = np.abs(np.arange(w)[None, :] - kx)
            dx = np.minimum(dx, w - dx)
            dy = np.arange(h)[:, None] - ky
            d = np.sqrt(dx * dx + dy * dy)
            tint *= 1.0 - 0.45 * np.clip(1.0 - d / kr, 0, 1)
        height += (rings * 0.5 + 0.5) * 0.0004 + (grain - 0.5) * 0.0006
        cav *= 0.9 + 0.1 * (rings * 0.5 + 0.5)
    elif name == "concrete":
        broom = periodic_noise(w, h, 2048, 6, 2, seed + 15)                 # strokes across U (along V)
        pores = periodic_noise(w, h, 512, 32, 2, seed + 16)
        pit = (pores < 0.18).astype(float)
        height += (broom - 0.5) * 0.0006 - pit * 0.0006
        cav *= 1.0 - 0.5 * pit
        tint *= 0.9 + 0.2 * broad + 0.06 * (fine - 0.5)
        rough += (broom - 0.5) * 0.08
    elif name == "cast_stone":
        sand = periodic_noise(w, h, 1024, 64, 2, seed + 17)
        height += (sand - 0.5) * 0.0003
        tint *= 0.94 + 0.12 * broad + 0.05 * (sand - 0.5)
    elif name == "rubber":
        height += (fine - 0.5) * 0.00005
    elif name == "screen":
        alpha *= 0.45
        tint *= 0.95 + 0.1 * fine
    elif name == "coil_guard":
        pitch = 0.025 * PX_PER_M                                            # 25 mm wire grid
        gx = np.abs(((np.arange(w)[None, :] + 0.5) % pitch) - pitch / 2) < 0.8
        gy = np.abs(((np.arange(h)[:, None] + 0.5) % pitch) - pitch / 2) < 0.8
        wire = (gx | gy).astype(float)
        fins = 0.5 + 0.5 * np.sin(np.arange(w)[None, :] * 2 * math.pi / 0.8)  # fins blur to a sheen at this size
        tint = np.where(wire > 0, 0.25, 0.55 + 0.2 * fins)
        cav = np.where(wire > 0, 1.0, 0.45)
        height += wire * 0.002
    elif name == "louvre":
        pitch = 0.064
        s = (u % pitch) / pitch                                             # 0..1 across one slat, along U
        height += (0.004 * s) * (s < 0.92) + 0.004 * (1 - (s - 0.92) / 0.08) * (s >= 0.92)
        cav *= np.where(s > 0.9, 0.35, 1.0)
        tint *= 0.985 + 0.03 * broad
    elif name == "lattice":
        strip, gap = 0.038, 0.070
        p = (strip + gap) * math.sqrt(2)
        a = ((u + v) % p) / p
        b = ((u - v) % p) / p
        on_a = a < strip * math.sqrt(2) / p
        on_b = b < strip * math.sqrt(2) / p
        alpha = (on_a | on_b).astype(float)
        height += on_a * 0.004 + on_b * 0.008                               # one layer over the other
        cav *= np.where(on_a & ~on_b, 0.85, 1.0)
    return height, tint, rough, cav, alpha


def cell_maps(name, seed):
    n = BAND_H
    yy, xx = (np.mgrid[0:n, 0:n] + 0.5) / n * 2 - 1                          # -1..1
    r = np.sqrt(xx * xx + yy * yy)
    th = np.arctan2(yy, xx)
    height = np.zeros((n, n))
    col = np.ones((n, n, 3)) * 0.5
    rough = np.full((n, n), 0.5)
    cav = np.ones((n, n))
    alpha = np.ones((n, n))
    if name == "fan_grille":                                                 # condenser top: spiral wire over a dark fan
        spiral = np.abs(np.sin(r * 22 * math.pi + th * 0.5)) < 0.18
        spokes = np.abs(np.sin(th * 4)) < 0.05
        wire = (spiral | spokes) & (r < 0.96)
        blades = 0.5 + 0.5 * np.sin(th * 3 + r * 3)
        col[...] = np.where(wire[..., None], 0.05, (0.03 + 0.05 * blades)[..., None])
        col[r >= 0.96] = 0.30
        height += wire * 0.003
        cav = np.where(wire | (r >= 0.96), 1.0, 0.3)
    elif name == "meter_face":                                               # electric meter under its dome: dial plate
        col[...] = 0.75
        col[r < 0.55] = 0.92
        for k in range(5):
            cx = -0.6 + 0.3 * k
            d = np.sqrt((xx - cx) ** 2 + (yy + 0.2) ** 2)
            col[(d < 0.11) & (d > 0.09)] = 0.1
        rough[...] = 0.25
    elif name == "lamp_glass":                                               # seeded glass panes of a lantern
        seedy = periodic_noise(n, n, 16, 16, 3, seed)
        col[...] = (0.85 + 0.1 * seedy)[..., None] * np.array([1.0, 0.97, 0.9])
        height += (seedy - 0.5) * 0.0005
        rough[...] = 0.08
    elif name == "round_vent":
        slots = (np.abs(np.sin(yy * 9 * math.pi)) > 0.6) & (r < 0.85)
        col[...] = 0.6
        col[slots] = 0.08
        cav = np.where(slots, 0.2, 1.0)
        height += (~slots) * 0.002
    elif name == "kick_plate":
        brush = periodic_noise(n, n, 2, 64, 2, seed)
        col[...] = (0.55 + 0.2 * brush)[..., None] * np.array([1.0, 0.82, 0.48])
        rough[...] = 0.3 + 0.1 * brush
    elif name == "dial_gauge":                                               # gas meter's index
        col[...] = 0.85
        for k in range(4):
            cx = -0.6 + 0.4 * k
            d = np.sqrt((xx - cx) ** 2 + yy ** 2)
            col[(d < 0.16) & (d > 0.13)] = 0.08
        rough[...] = 0.3
    return height, col, rough, cav, alpha


def normal_from_height(hgt, metres_per_px):
    dx = (np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)) / (2 * metres_per_px)
    dy = (np.roll(hgt, 1, 0) - np.roll(hgt, -1, 0)) / (2 * metres_per_px)     # rows run down, v runs up
    n = np.stack([-dx, -dy, np.ones_like(hgt)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n


def main():
    os.makedirs(OUT, exist_ok=True)
    col = np.zeros((H, W, 3))
    hgt = np.zeros((H, W))
    m = np.zeros((H, W, 4))
    meta = {"size_px": [W, H], "px_per_m": PX_PER_M, "band_h_px": BAND_H, "u_tile_m": W / PX_PER_M,
            "band_h_m": BAND_H / PX_PER_M, "bands": {}, "cells": {}}
    for i, (name, paint, base, rough0, what) in enumerate(BANDS):
        y0 = i * BAND_H
        h_, tint, rough, cav, alpha = band_maps(name, 100 + i * 17)
        col[y0:y0 + BAND_H] = np.clip(np.array(base)[None, None, :] * tint[..., None], 0, 1)
        hgt[y0:y0 + BAND_H] = h_
        m[y0:y0 + BAND_H, :, 0] = cav
        m[y0:y0 + BAND_H, :, 1] = np.clip(rough0 + rough, 0.02, 1)
        m[y0:y0 + BAND_H, :, 2] = paint
        m[y0:y0 + BAND_H, :, 3] = alpha
        meta["bands"][name] = {"index": i, "v0_px": y0, "v1_px": y0 + BAND_H, "v0": 1 - (y0 + BAND_H) / H,
                               "v1": 1 - y0 / H, "paint": paint, "roughness": rough0, "what": what}
    for k, name in enumerate(CELLS):
        x0, y0 = k * BAND_H, CELL_Y0
        h_, c, rough, cav, alpha = cell_maps(name, 500 + k)
        col[y0:y0 + BAND_H, x0:x0 + BAND_H] = c
        hgt[y0:y0 + BAND_H, x0:x0 + BAND_H] = h_
        m[y0:y0 + BAND_H, x0:x0 + BAND_H] = np.stack([cav, rough, np.zeros_like(cav), alpha], -1)
        meta["cells"][name] = {"rect_px": [x0, y0, BAND_H, BAND_H],
                               "rect_uv": [x0 / W, 1 - (y0 + BAND_H) / H, BAND_H / W, BAND_H / H]}
    nrm = normal_from_height(hgt, 1.0 / PX_PER_M)
    # Seams between bands must not leak relief: the gradient across a band edge is zeroed.
    for i in range(1, len(BANDS) + 1):
        y = i * BAND_H
        nrm[max(y - 1, 0):y + 1] = (0, 0, 1)
    srgb = np.where(col <= 0.0031308, col * 12.92, 1.055 * np.power(np.clip(col, 0, 1), 1 / 2.4) - 0.055)
    Image.fromarray((srgb * 255 + 0.5).astype(np.uint8), "RGB").save(os.path.join(OUT, "T_HouseTrim_C.png"))
    Image.fromarray(((nrm * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8), "RGB").save(os.path.join(OUT, "T_HouseTrim_N.png"))
    Image.fromarray((np.clip(m, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(os.path.join(OUT, "T_HouseTrim_M.png"))
    json.dump(meta, open(os.path.join(OUT, "trim.json"), "w"), indent=1)
    # trim.json is also kept beside the scripts: hk_trim.py and the materials thread read the layout from the repo.
    json.dump(meta, open(os.path.join(HERE, "trim.json"), "w"), indent=1)
    print(f"TrimSheet: {len(BANDS)} bands, {len(CELLS)} cells, {W}x{H} at {PX_PER_M / 100:.0f} px/cm -> {OUT}")


if __name__ == "__main__":
    main()
