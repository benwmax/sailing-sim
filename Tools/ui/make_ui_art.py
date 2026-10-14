"""Graphics G4: the front end's baked art (ui-spec.md 5.3, 5.2, 5.7), from the game's own data and screenshots.

  Artifacts/ui/T_Map_<World>.png   chart-style launch maps: land in chart buff, water shaded by depth, the shoreline,
                                   bridges and causeways in brown, place names in tracked capitals (Saira), a magenta
                                   compass rose. The map covers the world's whole height grid, north up, so the game
                                   places pins by the grid's extent (Content/TerrainData/<World>.json "grid").
  Artifacts/ui/T_MiniMap_<World>.png  the same chart for the HUD's minimap, 4096 px, no names (and the Gulf passage's).
  Artifacts/ui/T_Card_<World>.jpg  world card art and T_Load_<World>_<n>.jpg loading images, cropped from the bench
                                   screenshots in docs/ (the game itself, never photos).

    Tools/venv/bin/python -I Tools/ui/make_ui_art.py
Then scripts/import_ui_art.py (run by scripts/make-content.sh) imports them to /Game/UI.
"""
import json
import math
import os
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pyproj import Transformer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(ROOT, "Content", "TerrainData")
OUT = os.path.join(ROOT, "Artifacts", "ui")
FONTS = os.path.join(ROOT, "Content", "UI", "Fonts")
os.makedirs(OUT, exist_ok=True)

LAND = (0xCD, 0xBF, 0x98)
WATER_SHALLOW = (0x5A, 0x95, 0xB8)
WATER_DEEP = (0x2F, 0x6F, 0x97)
SHORE = (0x8A, 0x7A, 0x55)
ROAD = (0x8B, 0x6A, 0x3E)
CHART = (0xD1, 0x4F, 0x9B)
INK = (0x2A, 0x26, 0x1C)

PLACES = {
    "RayHubbard": [("ROWLETT", 32.9029, -96.5639), ("ROCKWALL", 32.9312, -96.4597), ("HEATH", 32.8365, -96.4747),
                   ("GARLAND", 32.8800, -96.6000), ("SUNNYVALE", 32.7966, -96.5608)],
    "GalvestonBay": [("KEMAH", 29.5427, -95.0205), ("SEABROOK", 29.5641, -95.0255), ("LA PORTE", 29.6658, -95.0194),
                     ("TEXAS CITY", 29.3838, -94.9027), ("GALVESTON", 29.2900, -94.8200), ("BOLIVAR", 29.4100, -94.7000),
                     ("SMITH POINT", 29.5450, -94.7800)],
}


def load(world):
    meta = json.load(open(os.path.join(DATA, world + ".json")))
    with open(os.path.join(DATA, world + ".height"), "rb") as f:
        data = f.read()
    _, _, nx, ny, cell, x0, y0, unit = struct.unpack("<4sIIIffff", data[:32])
    h = np.frombuffer(data[32:32 + nx * ny * 2], "<i2").reshape(ny, nx).astype(np.float32) * unit
    return meta, h, (nx, ny, cell, x0, y0)


def make_map(world, long_side=1800, mini=False):
    meta, h, (nx, ny, cell, x0, y0) = load(world)
    # North up: grid rows run north, so flip; columns run east.
    img_h = h[::-1, :]
    scale = long_side / max(nx, ny)
    w, hh = int(nx * scale), int(ny * scale)
    if mini:
        w, hh = w // 4 * 4, hh // 4 * 4   # block compression
    small = np.asarray(Image.fromarray(img_h).resize((w, hh), Image.BILINEAR))
    water = small < 0.0
    depth = np.clip(-small / 8.0, 0, 1)[..., None]
    rgb = np.where(water[..., None], np.array(WATER_SHALLOW) * (1 - depth) + np.array(WATER_DEEP) * depth, np.array(LAND, float))
    # Hillshade on land, faint.
    gy, gx = np.gradient(np.where(water, 0, small))
    shade = np.clip(1.0 + 0.04 * (gx - gy), 0.9, 1.08)[..., None]
    rgb = np.where(water[..., None], rgb, rgb * shade)
    im = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")
    # The shoreline: the water mask's edge.
    edge = Image.fromarray((water * 255).astype(np.uint8)).filter(ImageFilter.FIND_EDGES)
    im.paste(Image.new("RGB", im.size, SHORE), mask=edge)
    d = ImageDraw.Draw(im)

    def px(n, e):
        return ((e - y0) / cell * scale, (ny - 1 - (n - x0) / cell) * scale)

    for b in meta.get("bridges", []):
        pts = [px(p[0], p[1]) for p in b.get("points", [])]
        if len(pts) > 1:
            d.line(pts, fill=ROAD, width=max(3, int(6 * scale * 10 / cell)))
    if mini:
        # The HUD's minimap: the same chart without names or rose (it shows a few km around the boat).
        im.save(os.path.join(OUT, f"T_MiniMap_{world}.png"))
        print(f"T_MiniMap_{world}: {w}x{hh}")
        return
    to_local = Transformer.from_crs("EPSG:4326", meta["projection"], always_xy=True)
    font = ImageFont.truetype(os.path.join(FONTS, "SairaSemiCondensed-SemiBold.ttf"), 30)
    for name, lat, lon in PLACES.get(world, []):
        e, n = to_local.transform(lon, lat)
        x, y = px(n, e)
        if 0 < x < w and 0 < y < hh:
            spaced = " ".join(name)   # tracked capitals
            tw = d.textlength(spaced, font=font)
            d.text((x - tw / 2, y - 15), spaced, fill=INK, font=font)
    # Compass rose, top right.
    cx, cy, r = w - 90, 90, 48
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=CHART, width=3)
    d.ellipse((cx - r + 10, cy - r + 10, cx + r - 10, cy + r - 10), outline=CHART, width=1)
    d.polygon([(cx, cy - r + 4), (cx - 9, cy + 6), (cx, cy), (cx + 9, cy + 6)], fill=CHART)
    d.text((cx - 9, cy - r - 36), "N", fill=CHART, font=font)
    im.save(os.path.join(OUT, f"T_Map_{world}.png"))
    print(f"T_Map_{world}: {w}x{hh}, {len(meta.get('launch_spots', []))} launch spots")


def crop(src, out, aspect=16 / 9, size=(1600, 900), focus=0.5):
    im = Image.open(os.path.join(ROOT, src)).convert("RGB")
    w, h = im.size
    if w / h > aspect:
        nw = int(h * aspect)
        x = int((w - nw) * focus)
        im = im.crop((x, 0, x + nw, h))
    else:
        nh = int(w / aspect)
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    im.resize(size, Image.LANCZOS).save(os.path.join(OUT, out), quality=90)


for world in ("RayHubbard", "GalvestonBay"):
    make_map(world)
for world in ("RayHubbard", "GalvestonBay", "GulfPassage"):
    make_map(world, long_side=4096, mini=True)
# The capture-mode stills and the blind test's frames: the game without its HUD.
CAP = "docs/graphics-3/captures/"
CAP4 = "docs/graphics-4/captures/"   # Galveston stills in the capture mode (scripts/run-game.sh -SailingWorld=1 -SailingCapture=Chase)
crop(CAP + "j22-light-chase.png", "T_Card_RayHubbard.jpg", aspect=2.2, size=(1320, 600))
crop(CAP4 + "bay-hobie-chase.png", "T_Card_GalvestonBay.jpg", aspect=2.2, size=(1320, 600))
for i, src in enumerate((CAP + "rh-c30-evening.png", CAP + "j22-moderate-chase.png", CAP + "storm-lake.png")):
    crop(src, f"T_Load_RayHubbard_{i}.jpg")
for i, src in enumerate((CAP4 + "bay-j22-chase.png", CAP4 + "bay-hobie-chase.png", CAP + "sunfish-reach.png")):
    crop(src, f"T_Load_GalvestonBay_{i}.jpg")
crop(CAP + "j22-heavy-chase.png", "T_Title_RayHubbard.jpg")
crop(CAP4 + "bay-j22-chase.png", "T_Title_GalvestonBay.jpg")
print("ui art in", OUT)
