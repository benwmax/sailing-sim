"""Shape loop, step 7: the before/after sheet for Bean (docs/shape-loop).

    python3 make_sheet.py <before dir> <after dir> <out.jpg> [view ...] [--ref <dir>] [--title "J/22 hull shell, round 2"]

One row per view (default: shade_profile, shade_34, zebra_34, shade_cockpit), columns before | after, and a reference
column first when --ref holds <view>.jpg or .png (a drawing or photo crop, git-ignored; never committed). Labels sit
under each picture. Needs Pillow.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ARGS = sys.argv[1:]
REF = ARGS[ARGS.index("--ref") + 1] if "--ref" in ARGS else None
TITLE = ARGS[ARGS.index("--title") + 1] if "--title" in ARGS else ""
pos = [a for i, a in enumerate(ARGS) if not a.startswith("--") and (i == 0 or ARGS[i - 1] not in ("--ref", "--title"))]
BEFORE, AFTER, OUT = pos[0], pos[1], pos[2]
VIEWS = pos[3:] or ["shade_profile", "shade_34", "zebra_34", "shade_cockpit"]
W = 900


def font(px):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(f):
            return ImageFont.truetype(f, px)
    return ImageFont.load_default()


def find(d, view):
    for ext in (".png", ".jpg"):
        p = os.path.join(d, view + ext)
        if os.path.exists(p):
            return p
    return None


def tile(path, label):
    im = Image.open(path).convert("RGB") if path else Image.new("RGB", (W, W // 2), (235, 235, 235))
    im = im.resize((W, int(im.height * W / im.width)))
    out = Image.new("RGB", (W, im.height + 40), "white")
    out.paste(im, (0, 0))
    ImageDraw.Draw(out).text((10, im.height + 8), label, fill=(20, 20, 20), font=font(22))
    return out


rows = []
for v in VIEWS:
    cols = []
    if REF:
        cols.append(tile(find(REF, v), f"reference: {v}"))
    cols.append(tile(find(BEFORE, v), f"before: {v}"))
    cols.append(tile(find(AFTER, v), f"after: {v}"))
    h = max(c.height for c in cols)
    row = Image.new("RGB", (W * len(cols) + 10 * (len(cols) - 1), h), "white")
    for i, c in enumerate(cols):
        row.paste(c, (i * (W + 10), 0))
    rows.append(row)
head = 60 if TITLE else 0
sheet = Image.new("RGB", (max(r.width for r in rows), sum(r.height for r in rows) + 10 * len(rows) + head), "white")
if TITLE:
    ImageDraw.Draw(sheet).text((10, 14), TITLE, fill=(0, 0, 0), font=font(32))
y = head
for r in rows:
    sheet.paste(r, (0, y))
    y += r.height + 10
sheet.save(OUT, quality=88)
print("shapeloop sheet:", OUT, sheet.size)
