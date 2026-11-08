"""Before/after sheet for Bean: one row per wear level, the reference beside today's and the new non-skid.

    python3 Tools/texloop/nonskid/make_sheet.py <render dir> <photo crop dir> <out.jpg>
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

RD, PD, OUT = sys.argv[1:4]
REFS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "refs", "nonskid.json")))
M = json.load(open(os.path.join(RD, "measure.json")))
CELL = 300
LAB = {"L0": "L0 brand new", "L1": "L1 a few months", "L2": "L2 club boat (6 yr)", "L3": "L3 30 yr, kept", "L4": "L4 neglected"}
try:
    F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17)
    FB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 19)
except OSError:
    F = FB = ImageFont.load_default()


def tile(path, box=None):
    im = Image.open(path).convert("RGB")
    if box:
        im = im.crop(box)
    w, h = im.size
    s = min(w, h)
    return im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).resize((CELL, CELL), Image.LANCZOS)


cols = ["Reference photo", "Before: 20 cm, low sun", "After: 20 cm, low sun", "Before: 1 m, overcast", "After: 1 m, overcast"]
W, H = 190 + CELL * 5 + 6 * 10, 90 + (CELL + 64) * 6
sheet = Image.new("RGB", (W, H), (245, 244, 240))
d = ImageDraw.Draw(sheet)
d.text((16, 14), "Non-skid deck, five wear levels: today's main (before) and texture-loop round 4 (after, numpy stand-in for the shader)", font=FB, fill=(20, 20, 20))
d.text((16, 42), "Pattern measured on Bean's J/22 photo: 2.3 mm diagonal ribs (before: 1.8 mm pyramids + 8 mm diamond). Colours vs a white gelcoat of sRGB 215.", font=F, fill=(60, 60, 60))
for i, c in enumerate(cols):
    d.text((190 + 10 + i * (CELL + 10), 66), c, font=F, fill=(30, 30, 30))
rows = [("pattern", None)] + [(lv, lv) for lv in ["L0", "L1", "L2", "L3", "L4"]]
for r, (name, lv) in enumerate(rows):
    y = 90 + r * (CELL + 64)
    x0 = 190 + 10
    if lv is None:
        d.text((16, y + 10), "Pattern at 1:1", font=FB, fill=(20, 20, 20))
        d.text((16, y + 40), "seat, IMG_9272", font=F, fill=(60, 60, 60))
        sheet.paste(tile(os.path.join(PD, "IMG_9272_seat_ribs_1to1.jpg")), (x0, y))
        sheet.paste(tile(os.path.join(RD, "before_L0_close_sun.png"), (0, 0, 380, 380)), (x0 + 1 * (CELL + 10), y))
        sheet.paste(tile(os.path.join(RD, "after_L0_close_sun.png"), (0, 0, 380, 380)), (x0 + 2 * (CELL + 10), y))
        d.text((x0 + 3 * (CELL + 10), y + 10), "Ribs run about 45 degrees to the\nboat's axis, one direction strong,\na faint cross texture.\n\nPitch: photo 2.0-2.7 mm (mean 2.3)\nbefore 1.77 mm, after 2.28 mm", font=F, fill=(40, 40, 40))
        continue
    t = REFS["targets"][lv]
    b, a = M[f"before_{lv}"]["swatch"], M[f"after_{lv}"]["swatch"]
    d.text((16, y + 10), LAB[lv], font=FB, fill=(20, 20, 20))
    d.text((16, y + 40), f"Age {t['age_care'][0]}, Care {t['age_care'][1]}", font=F, fill=(60, 60, 60))
    d.text((16, y + 64), "target L*a*b*\n%s" % ", ".join(str(v) for v in t["lab"]), font=F, fill=(60, 60, 60))
    if lv == "L2":
        sheet.paste(tile(os.path.join(PD, "1000032822_foredeck_footpath_overcast.jpg"), (520, 30, 900, 270)), (x0, y))
        cap = "J/22 foredeck, foot path"
    else:
        d.rectangle((x0, y, x0 + CELL, y + CELL), fill=(225, 223, 218))
        d.text((x0 + 20, y + CELL // 2 - 30), "no photo yet:\ntarget derived from L2\n(club close-ups wanted)", font=F, fill=(90, 90, 90))
        cap = ""
    sheet.paste(tile(os.path.join(RD, f"before_{lv}_close_sun.png")), (x0 + 1 * (CELL + 10), y))
    sheet.paste(tile(os.path.join(RD, f"after_{lv}_close_sun.png")), (x0 + 2 * (CELL + 10), y))
    sheet.paste(tile(os.path.join(RD, f"before_{lv}_swatch_overcast.png")), (x0 + 3 * (CELL + 10), y))
    sheet.paste(tile(os.path.join(RD, f"after_{lv}_swatch_overcast.png")), (x0 + 4 * (CELL + 10), y))
    d.text((x0, y + CELL + 6), cap, font=F, fill=(60, 60, 60))
    d.text((x0 + 3 * (CELL + 10), y + CELL + 6), f"colour off by {M[f'before_{lv}']['dE_swatch']}", font=F, fill=(150, 40, 30) if M[f'before_{lv}']['dE_swatch'] > 6 else (30, 110, 40))
    d.text((x0 + 4 * (CELL + 10), y + CELL + 6), f"colour off by {M[f'after_{lv}']['dE_swatch']}", font=F, fill=(150, 40, 30) if M[f'after_{lv}']['dE_swatch'] > 6 else (30, 110, 40))
sheet.save(OUT, quality=90)
print("wrote", OUT)
