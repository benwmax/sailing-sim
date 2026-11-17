"""Draw each shore station from above: ground and water from the bakes, houses, crowns, map docks, the generated
boathouses, the subject point and the three cameras with their 80 degree view (docs/env-loop/README.md).

    python3 Tools/envloop/station_maps.py OUT_DIR [station ...]

Writes OUT_DIR/<station>.png (220 m square, 1 px = 0.25 m) and OUT_DIR/stations_map.jpg (all ten on one sheet).
Images stay out of git from the cloud (Git LFS); the Mac or PC commits any that docs need.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lake import Lake  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE_M, PX_M = 220.0, 4


def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def draw(lake, st, slips):
    s = st["subject_map"]
    n = st["out_to_lake"]
    # centre between the subject and the 60 m camera, so the whole fan shows
    c = (s[0] + n[0] * 30.0, s[1] + n[1] * 30.0)
    N = int(SIZE_M * PX_M)
    g = (np.arange(N) + 0.5) / PX_M - SIZE_M / 2
    # image rows run north to south (top = north), columns west to east
    X = c[0] - g[:, None] + np.zeros((1, N))
    Y = c[1] + g[None, :] + np.zeros((N, 1))
    h = lake.height_at(X, Y)
    gy, gx = np.gradient(h)
    shade = np.clip(0.75 + 2.0 * (gx + gy), 0.35, 1.15)
    land = np.stack([0.62 + 0.04 * np.clip(h, 0, 5), 0.66 + 0.01 * np.clip(h, 0, 5), 0.45 + 0.0 * h], -1) * shade[..., None]
    water = np.stack([0.42 + 0.03 * np.clip(h, -4, 0), 0.58 + 0.04 * np.clip(h, -4, 0), 0.66 + 0.03 * np.clip(h, -4, 0)], -1)
    rgb = np.where((h < -0.05)[..., None], water, land)
    img = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(img, "RGBA")

    def px(p):
        return ((p[1] - c[1] + SIZE_M / 2) * PX_M, (c[0] - p[0] + SIZE_M / 2) * PX_M)
    for cr in lake.crowns[np.hypot(lake.crowns[:, 0] - c[0], lake.crowns[:, 1] - c[1]) < SIZE_M]:
        x, y = px(cr[:2])
        r = cr[4] * PX_M
        d.ellipse((x - r, y - r, x + r, y + r), fill=(40, 90, 40, 110), outline=(30, 70, 30, 180))
    for k in lake.houses_near(c[0], c[1], SIZE_M):
        for (wx, wy, hl, hw, yaw) in lake.houses[k]["wings"]:
            a = math.radians(yaw)
            u, v = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
            pts = [px((wx + u[0] * sa * hl + v[0] * sb * hw, wy + u[1] * sa * hl + v[1] * sb * hw)) for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            d.polygon(pts, fill=(150, 80, 60, 230), outline=(60, 30, 20, 255))
    for dk in lake.docks:
        pts = [px(p) for p in dk["points"]]
        if any(0 <= x < N and 0 <= y < N for x, y in pts):
            d.line(pts, fill=(110, 70, 30, 255), width=max(2, int(1.5 * PX_M)))
    for row in lake.marina.get("rows", []) + lake.marina.get("piers", []) + lake.marina.get("breakwaters", []):
        d.line([px(p) for p in row["points"]], fill=(120, 110, 100, 255), width=int(row.get("width", 2.0) * PX_M))
    for sp, w in slips:
        if abs(sp[0] - c[0]) < SIZE_M and abs(sp[1] - c[1]) < SIZE_M:
            a = (-w[1], w[0])
            pts = [px((sp[0] + w[0] * al + a[0] * ac, sp[1] + w[1] * al + a[1] * ac)) for al, ac in ((0.6, -4), (15.4, -4), (15.4, 4), (0.6, 4))]
            d.polygon(pts, outline=(90, 60, 30, 255), fill=(200, 170, 120, 120))
    f = font(15)
    for cam in st["cameras"]:
        p = cam["camera_map"]
        b = math.radians(cam["bearing_deg"])
        x, y = px(p)
        L = (cam["distance_m"] + 25) * PX_M
        for side in (-40, 40):
            a = b + math.radians(side)
            d.line([(x, y), (x + math.sin(a) * L, y - math.cos(a) * L)], fill=(255, 255, 255, 150), width=2)
        d.ellipse((x - 7, y - 7, x + 7, y + 7), fill=(230, 60, 40, 255), outline=(255, 255, 255, 255), width=2)
        d.text((x + 10, y - 8), "%d m" % cam["distance_m"], fill=(255, 255, 255), font=f, stroke_width=2, stroke_fill=(0, 0, 0))
    x, y = px(s)
    d.rectangle((x - 6, y - 6, x + 6, y + 6), fill=(255, 220, 0, 255), outline=(0, 0, 0, 255), width=2)
    d.rectangle((0, 0, N, 30), fill=(0, 0, 0, 150))
    d.text((8, 6), "%s  (subject %.0f N, %.0f E; N up; 220 m)" % (st["name"], s[0], s[1]), fill=(255, 255, 255), font=font(17))
    d.line([(N - 110, N - 20), (N - 10, N - 20)], fill=(0, 0, 0), width=4)
    d.text((N - 100, N - 42), "25 m", fill=(0, 0, 0), font=f)
    return img


def main():
    out = sys.argv[1]
    only = set(sys.argv[2:])
    os.makedirs(out, exist_ok=True)
    data = json.load(open(os.path.join(HERE, "stations.json")))
    lake = Lake()
    slips = []
    for st in data["stations"]:
        s = st["subject_map"]
        for k in lake.houses_near(s[0], s[1], 300.0):
            lt = lake.lot(k)
            if lt and lt["boathouse"]:
                slips.append((lt["slip"], lt["water"]))
    tiles = []
    for st in data["stations"]:
        if only and st["id"] not in only:
            continue
        im = draw(lake, st, slips)
        im.save(os.path.join(out, st["id"] + ".png"))
        tiles.append(im)
        print(st["id"])
    if tiles:
        T = 440
        cols = 2
        sheet = Image.new("RGB", (cols * T, ((len(tiles) + cols - 1) // cols) * T), "white")
        for i, im in enumerate(tiles):
            sheet.paste(im.resize((T, T), Image.LANCZOS), ((i % cols) * T, (i // cols) * T))
        sheet.save(os.path.join(out, "stations_map.jpg"), quality=88)


if __name__ == "__main__":
    main()
