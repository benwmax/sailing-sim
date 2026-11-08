"""Before/after sheet for the sailcloth loop: one row per wear level; the whole J/22 main (2 cm a pixel) and a 60 cm
close-up at the clew (1 mm a pixel), before and after, with the level's Lab against its target.

    python3 -I sailcloth_sheet.py SWATCH_DIR OUT.jpg [--ref L2=photo.jpg:x0,y0,x1,y1 ...]
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sailcloth_lab import de  # noqa: E402

NAMES = {"L0": "L0 brand new (0 yr, care 1.0)", "L1": "L1 a few months (0.3 yr, 0.9)", "L2": "L2 club boat (6 yr, 0.5)",
         "L3": "L3 decades, kept (30 yr, 0.9)", "L4": "L4 neglected (20 yr, 0.1)"}


def main():
    sw, out = sys.argv[1], sys.argv[2]
    refs = {}
    for a in sys.argv[3:]:
        if a.startswith("--ref"):
            continue
        lv, rest = a.split("=", 1)
        path, bx = rest.rsplit(":", 1)
        refs[lv] = (path, [int(v) for v in bx.split(",")])
    stats = json.load(open(os.path.join(sw, "stats.json")))
    targets = json.load(open(os.path.join(HERE, "refs", "sailcloth.json")))["targets"]
    f = ImageFont.load_default(size=22)
    fs = ImageFont.load_default(size=17)
    cw, rh, head = 330, 420, 70
    cols = (["photo"] if refs else []) + ["sail before", "sail after", "close-up before", "close-up after"]
    W = Image.new("RGB", (220 + cw * len(cols), head + rh * 5), (32, 34, 38))
    d = ImageDraw.Draw(W)
    for i, c in enumerate(cols):
        d.text((220 + i * cw + 10, 20), c, fill="white", font=f)
    for r, lv in enumerate(["L0", "L1", "L2", "L3", "L4"]):
        y = head + r * rh
        d.text((10, y + 10), NAMES[lv].split(" (")[0], fill="white", font=f)
        d.text((10, y + 40), "(" + NAMES[lv].split(" (")[1], fill=(200, 200, 200), font=fs)
        t = targets[lv]["lab"]
        for k, m in enumerate(("before", "after")):
            s = stats[m][lv]
            e = de(s["clew_lab_mean"], t)
            d.text((10, y + 90 + k * 70), f"{m}: Lab {s['clew_lab_mean'][0]:.0f} {s['clew_lab_mean'][1]:+.1f} {s['clew_lab_mean'][2]:+.1f}", fill="white", font=fs)
            d.text((10, y + 112 + k * 70), f"dE {e:.1f} vs target {'ok' if e <= 6 else 'FAIL'}", fill=(150, 230, 150) if e <= 6 else (240, 140, 120), font=fs)
        d.text((10, y + 240), f"target {t[0]:.0f} {t[1]:+.1f} {t[2]:+.1f}", fill=(200, 200, 200), font=fs)
        d.text((10, y + 262), "(measured)" if "measured" in targets[lv]["source"] else "(estimate)", fill=(200, 200, 200), font=fs)
        x = 220
        if refs:
            if lv in refs:
                p, bx = refs[lv]
                im = Image.open(p).convert("RGB").crop(bx)
                im.thumbnail((cw - 10, rh - 10))
                W.paste(im, (x, y))
            else:
                d.text((x + 10, y + 180), "no photo yet", fill=(150, 150, 150), font=f)
            x += cw
        for m in ("before", "after"):
            s = Image.open(os.path.join(sw, f"sail_{m}_{lv}.png"))
            bg = Image.new("RGB", s.size, (122, 140, 158))
            bg.paste(s, mask=s.split()[3])
            W.paste(bg, (x + (cw - bg.width) // 2, y))
            x += cw
        for m in ("before", "after"):
            c = Image.open(os.path.join(sw, f"close_{m}_{lv}.png")).resize((rh - 10, rh - 10))
            c = c.crop((0, 0, cw - 10, rh - 10))
            W.paste(c, (x, y))
            x += cw
    W.save(out, quality=88)


if __name__ == "__main__":
    main()
