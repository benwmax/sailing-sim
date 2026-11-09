"""The rope texture loop's review sheet: one row per wear level, the reference photo (where we have one) beside the rope
before the loop (fixed Fade 0.4 / Dirt 0.5 on every boat) and after (Age and Care through time_k / dirt_k).

    python3 Tools/rope/make_rope_sheet.py <out.jpg> [L2 reference photo crop]

The reference crop is Bean's own lesson photo of the club J/22's lines (git-ignored, Data/Reference/raw/textures/Rope/L2/),
so the sheet goes to the project files, not the repo.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rope_wear as R  # noqa: E402

NAMES = {"L0": "L0 brand new (0 yr, care 1.0)", "L1": "L1 a few months (0.3 yr, 0.9)", "L2": "L2 club boat (6 yr, 0.5)",
         "L3": "L3 30 years, kept (care 0.9)", "L4": "L4 neglected (20 yr, 0.1)"}


def font(px):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, px)
    return ImageFont.load_default()


def ropes(legacy, age, care, maps, looks=(0, 1, 2, 7)):
    ims = [R.render_rope(lk, age, care, maps, length_mm=70, px_per_mm=8, legacy=legacy)[0] for lk in looks]
    gap = np.full((8, ims[0].shape[1], 3), 236, np.uint8)
    return Image.fromarray(np.concatenate(sum(([im, gap] for im in ims), [])[:-1], axis=0))


def main(out, ref=None):
    maps = R.load_maps()
    rows = []
    W_REF, F = 420, font(22)
    for lv, (age, care) in R.LEVELS.items():
        b, a = ropes(True, age, care, maps), ropes(False, age, care, maps)
        h = b.height
        cell = Image.new("RGB", (W_REF, h), (236, 236, 236))
        if ref and lv == "L2":
            im = Image.open(ref).convert("RGB")
            im.thumbnail((W_REF, h))
            cell.paste(im, ((W_REF - im.width) // 2, (h - im.height) // 2))
        else:
            ImageDraw.Draw(cell).text((14, h // 2 - 12), "no photo yet", fill=(120, 120, 120), font=F)
        row = Image.new("RGB", (W_REF + b.width + a.width + 40, h + 40), (236, 236, 236))
        row.paste(cell, (0, 40))
        row.paste(b, (W_REF + 20, 40))
        row.paste(a, (W_REF + 40 + b.width, 40))
        ImageDraw.Draw(row).text((6, 8), NAMES[lv], fill=(20, 20, 20), font=F)
        rows.append(row)
    head = Image.new("RGB", (rows[0].width, 50), (236, 236, 236))
    d = ImageDraw.Draw(head)
    for x, t in ((10, "Reference"), (W_REF + 20, "Before (every boat the same)"), (W_REF + 40 + rows[0].width // 2 - W_REF // 2, "After (Age and Care)")):
        d.text((x, 12), t, fill=(0, 0, 0), font=font(26))
    sheet = Image.new("RGB", (rows[0].width, 50 + sum(r.height for r in rows)), (236, 236, 236))
    sheet.paste(head, (0, 0))
    y = 50
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height
    sheet.save(out, quality=90)
    print("wrote", out, sheet.size)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
