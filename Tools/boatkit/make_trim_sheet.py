"""The hardware kit's shared trim sheet (boat fidelity 2, docs/boat-fidelity-2): one 2048 x 1024 texture pair at 10 px/cm
that every kit part maps onto, so a block's cheek, a winch drum and a stanchion share one material and one draw.

    python3 Tools/boatkit/make_trim_sheet.py [out dir]      (numpy + Pillow; no Blender, no photos)

Eight horizontal bands, 112 px (11.2 cm) tall and tileable along U (204.8 cm) and inside their own height, one per surface
kind (phase 1's library: docs/boat-fidelity-1): brushed stainless, anodised aluminium, cast aluminium, knurl, rubber grip,
textured plastic, smooth moulding, carbon twill. The bottom 128 px row holds the brand plates: made-up maker's plates
(TERNWAY, a name we made up: no real maker's name or logo) with size marks, mapped whole onto a part's badge.

  T_KitTrim_N   tangent-space normal (OpenGL, green up: flipped on import like the other detail maps)
  T_KitTrim_M   R cavity (0 in grooves and engraving), G roughness offset (0.5 neutral), B paint fill (1 where an
                engraving is filled white), A unused
  trim.json     bands (name, v0 and v1 in px and UV) and plate cells (name, rect in px and UV); bk_trim.py reads it
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "Inputs", "boat-kit")
W, H = 2048, 1024
PX_PER_M = 1000.0                      # 10 px/cm
BAND_H = 112
BANDS = ["brushed", "anodised", "cast", "knurl", "grip", "textured", "smooth", "carbon"]
PLATE_Y0 = BAND_H * len(BANDS)          # 896
FONT = os.path.join(REPO, "Content", "UI", "Fonts", "SairaCondensed-Bold.ttf")
os.makedirs(OUT, exist_ok=True)


def periodic_noise(w, h, cells_x, cells_y, octaves, seed, persistence=0.5):
    """Value noise that tiles over w x h (cells per tile along each axis), smoothstep-interpolated."""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w))
    amp, total = 1.0, 0.0
    for o in range(octaves):
        cx, cy = cells_x * 2 ** o, cells_y * 2 ** o
        if cx > w or cy > h:
            break
        lat = rng.random((cy, cx))
        xi = np.arange(w) * cx / w
        yi = np.arange(h) * cy / h
        x0, y0 = np.floor(xi).astype(int), np.floor(yi).astype(int)
        fx, fy = xi - x0, yi - y0
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        x1, y1 = (x0 + 1) % cx, (y0 + 1) % cy
        a = lat[y0][:, x0] * (1 - fx) + lat[y0][:, x1] * fx
        b = lat[y1][:, x0] * (1 - fx) + lat[y1][:, x1] * fx
        out += amp * (a * (1 - fy)[:, None] + b * fy[:, None])
        total += amp
        amp *= persistence
    return out / total


def band(name, seed):
    """One band's height (mm), roughness offset and cavity, W x BAND_H, tileable along U and within the band."""
    h = BAND_H
    y, x = np.meshgrid(np.arange(h) + 0.5, np.arange(W) + 0.5, indexing="ij")
    rng = np.random.default_rng(seed)
    if name == "brushed":                       # 316: straight brushing along U, a few deeper tool lines
        rows = rng.random((h, 1))
        streak = 0.6 * rows + 0.4 * periodic_noise(W, h, 4, h // 2, 2, seed)
        height = (streak - 0.5) * 0.02
        rough = 0.5 + 0.35 * (streak - 0.5)
    elif name == "anodised":                    # extrusion die lines along U under a soft mottle
        lines = 0.5 + 0.5 * np.sin(2 * np.pi * y / 7.0) * periodic_noise(W, h, 16, 1, 2, seed)
        mottle = periodic_noise(W, h, 32, 2, 3, seed + 1)
        height = (lines - 0.5) * 0.015
        rough = 0.5 + 0.2 * (mottle - 0.5)
    elif name == "cast":                        # sand-cast grain: isotropic pits and bumps
        g = periodic_noise(W, h, 512, 28, 2, seed, 0.6)
        height = (g - 0.5) * 0.08
        rough = 0.5 + 0.3 * (g - 0.5)
    elif name == "knurl":                       # straight knurl at 1 mm pitch, 45 degrees both ways
        p = 10.0
        a = np.abs(((x + y) / p) % 1 - 0.5)
        b = np.abs(((x - y) / p) % 1 - 0.5)
        height = (np.minimum(a, b) - 0.25) * 0.15
        rough = 0.5 + 0.2 * (0.25 - np.minimum(a, b))
    elif name == "grip":                        # moulded rubber diamonds, 4 mm
        p = 40.0
        a = np.abs(((x + y) / p) % 1 - 0.5) * 2
        b = np.abs(((x - y) / p) % 1 - 0.5) * 2
        d = np.clip((np.minimum(a, b) - 0.15) * 6, 0, 1)
        height = d * 0.4
        rough = 0.5 + 0.15 * (1 - d)
    elif name == "textured":                    # EDM stipple on moulded plastic
        g = periodic_noise(W, h, 1024, 56, 2, seed, 0.7)
        height = (g - 0.5) * 0.05
        rough = 0.5 + 0.25 * (g - 0.5)
    elif name == "smooth":                      # faint orange peel
        g = periodic_noise(W, h, 256, 14, 3, seed)
        height = (g - 0.5) * 0.012
        rough = 0.5 + 0.1 * (g - 0.5)
    else:                                       # carbon 2x2 twill, 2.8 mm tows (4 across the band; along U the nearest pitch that tiles)
        p = 28.0
        px = W / round(W / p)
        u, v = x / px, y / p
        iu, iv = np.floor(u), np.floor(v)
        over = ((iu + iv // 2 * 2 + (iv % 2)) % 4) < 2
        fu, fv = u - iu, v - iv
        height = np.where(over, np.sin(np.pi * fv), np.sin(np.pi * fu)) * 0.05
        rough = 0.5 + 0.1 * np.where(over, 1.0, -1.0)
    cav = np.clip(1.0 - (height.max() - height) / max(1e-6, np.ptp(height)) * 0.6, 0, 1)
    return height, rough, cav


def plates():
    """The brand plate row: cells of engraved text and discs (height mm, paint fill), and their rects."""
    hgt = np.zeros((H - PLATE_Y0, W))
    fill = np.zeros_like(hgt)
    img = Image.new("L", (W, H - PLATE_Y0), 0)
    d = ImageDraw.Draw(img)
    cells = {}
    x = 0
    specs = [("Plate", "TERNWAY", 256, 64), ("Plate8", "TERNWAY 8", 256, 64), ("Plate16", "TERNWAY 16", 256, 64), ("Plate30", "TERNWAY 30", 256, 64),
             ("Plate29", "29", 128, 64), ("Plate40", "40", 128, 64), ("Plate57", "57", 128, 64), ("Plate75", "75", 128, 64),
             ("Disc", "T", 128, 128), ("DiscLarge", "TERNWAY", 256, 128)]
    row_y = 0
    for name, text, cw, ch in specs:
        if x + cw > W:
            x, row_y = 0, row_y + 64
        cells[name] = (x, PLATE_Y0 + row_y, cw, ch)
        if name.startswith("Disc"):
            r = min(cw, ch) // 2 - 4
            cx, cy = x + cw // 2, row_y + ch // 2
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=255, width=3)
            size = int(r * (1.1 if len(text) == 1 else 0.38))
            f = ImageFont.truetype(FONT, size)
            tw = d.textlength(text, font=f)
            d.text((cx - tw / 2, cy - size * 0.62), text, fill=255, font=f)
        else:
            size = int(ch * 0.62)
            f = ImageFont.truetype(FONT, size)
            tw = d.textlength(text, font=f)
            d.rounded_rectangle((x + 4, row_y + 4, x + cw - 4, row_y + ch - 4), radius=8, outline=255, width=2)
            d.text((x + (cw - tw) / 2, row_y + ch * 0.12), text, fill=255, font=f)
        x += cw
    eng = np.asarray(img, float) / 255.0
    hgt -= eng * 0.15                            # engraved 0.15 mm
    fill = eng
    return hgt, fill, cells


def normal_map(h_mm):
    dx = (np.roll(h_mm, -1, 1) - np.roll(h_mm, 1, 1)) / (2 * 1000.0 / PX_PER_M)
    dy = (np.roll(h_mm, -1, 0) - np.roll(h_mm, 1, 0)) / (2 * 1000.0 / PX_PER_M)
    n = np.stack([-dx, dy, np.ones_like(h_mm)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return ((n * 0.5 + 0.5) * 255 + 0.5).clip(0, 255).astype(np.uint8)


def main():
    height = np.zeros((H, W))
    rough = np.full((H, W), 0.5)
    cav = np.ones((H, W))
    fill = np.zeros((H, W))
    meta = {"size_px": [W, H], "px_per_m": PX_PER_M, "band_h_px": BAND_H, "bands": {}, "cells": {}}
    for i, name in enumerate(BANDS):
        hb, rb, cb = band(name, 100 + i)
        y0 = i * BAND_H
        # Each band normal-mapped on its own (rolls wrap inside the band, so it tiles in V too).
        height[y0:y0 + BAND_H] = hb
        rough[y0:y0 + BAND_H] = rb
        cav[y0:y0 + BAND_H] = cb
        meta["bands"][name] = {"v0_px": y0, "v1_px": y0 + BAND_H, "v0": y0 / H, "v1": (y0 + BAND_H) / H}
    hp, fp, cells = plates()
    height[PLATE_Y0:] = hp
    fill[PLATE_Y0:] = fp
    cav[PLATE_Y0:] = 1.0 - 0.7 * fp
    for name, (x, y, cw, ch) in cells.items():
        meta["cells"][name] = {"rect_px": [x, y, cw, ch], "uv": [x / W, y / H, (x + cw) / W, (y + ch) / H]}
    nrm = np.zeros((H, W, 3), np.uint8)
    for i in range(len(BANDS)):
        y0 = i * BAND_H
        nrm[y0:y0 + BAND_H] = normal_map(height[y0:y0 + BAND_H])
    nrm[PLATE_Y0:] = normal_map(height[PLATE_Y0:])
    Image.fromarray(nrm, "RGB").save(os.path.join(OUT, "T_KitTrim_N.png"))
    m = np.stack([cav, np.clip(rough, 0, 1), fill, np.ones_like(fill)], -1)
    Image.fromarray((m * 255 + 0.5).clip(0, 255).astype(np.uint8), "RGBA").save(os.path.join(OUT, "T_KitTrim_M.png"))
    json.dump(meta, open(os.path.join(OUT, "trim.json"), "w"), indent=1)
    print("trim sheet ->", OUT, sorted(meta["bands"]), sorted(meta["cells"]))


if __name__ == "__main__":
    main()
