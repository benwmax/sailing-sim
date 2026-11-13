"""Before/after sheet for the rock kit: rows of scenes, columns before (main) and after.

    python Tools/shoreloop/rocks/make_sheet.py <render dir> <out.jpg> [scene ...]

Reads <dir>/old_<scene>.png and <dir>/new_<scene>.png (render_rocks.py --tag old --rev main, and --tag new).
"""
import os
import sys

from PIL import Image, ImageDraw

d, out = sys.argv[1], sys.argv[2]
scenes = sys.argv[3:] or ["bank", "close", "studio"]
W = 900
rows = []
for sc in scenes:
    a, b = (Image.open(os.path.join(d, f"{t}_{sc}.png")).convert("RGB") for t in ("old", "new"))
    h = round(a.height * W / a.width)
    rows.append((sc, a.resize((W, h), Image.LANCZOS), b.resize((W, h), Image.LANCZOS)))
H = sum(r[1].height + 30 for r in rows) + 30
sheet = Image.new("RGB", (W * 2 + 30, H), (250, 250, 248))
dr = ImageDraw.Draw(sheet)
dr.text((10, 8), "before (main)", fill=(0, 0, 0))
dr.text((W + 20, 8), "after (rock kit, slice 1)", fill=(0, 0, 0))
y = 30
for sc, a, b in rows:
    dr.text((10, y + 4), sc, fill=(60, 60, 60))
    sheet.paste(a, (10, y + 24))
    sheet.paste(b, (W + 20, y + 24))
    y += a.height + 30
sheet.save(out, quality=88)
print("wrote", out)
