"""Lay out the hardware kit's review renders (build_kit.py --render) as review sheets (boat fidelity 2).

    python3 Tools/boatkit/make_review_sheet.py <kit out dir> [docs dir]

Writes <kit out dir>/kit_catalogue.png and kit_sizes.png (full size) and, with a docs dir, JPEGs under 300 KB there:
kit-catalogue.jpg (every part's hero with its triangle counts) and kit-sizes.jpg (each sized part's catalogue sizes side by
side at true relative scale). Blender's own Python has no Pillow on the PC, so this runs in a system Python.
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "..", "..", "Content", "UI", "Fonts", "SairaSemiCondensed-Medium.ttf")


def jpeg_under(img, path, limit=290_000):
    for q in range(88, 40, -6):
        img.save(path, quality=q)
        if os.path.getsize(path) < limit:
            return q
    return q


def catalogue(out, kit, cols=8, tile=(420, 320)):
    names = [n for n in kit if os.path.exists(os.path.join(out, "_tiles", f"{n}.png"))]
    rows = math.ceil(len(names) / cols)
    lab = 46
    sheet = Image.new("RGB", (cols * tile[0], rows * (tile[1] + lab)), (24, 26, 28))
    d = ImageDraw.Draw(sheet)
    f1, f2 = ImageFont.truetype(FONT, 22), ImageFont.truetype(FONT, 17)
    for i, n in enumerate(names):
        r, k = divmod(i, cols)
        x, y = k * tile[0], r * (tile[1] + lab)
        sheet.paste(Image.open(os.path.join(out, "_tiles", f"{n}.png")).convert("RGB"), (x, y))
        info = kit[n]
        size = " x ".join(f"{v * 1000:.0f}" for v in info["size_m"])
        d.text((x + 10, y + tile[1] + 2), n, fill=(230, 232, 235), font=f1)
        d.text((x + 10, y + tile[1] + 25), f"{info['tris']} / {info['light']['tris']} tris   {size} mm", fill=(150, 156, 162), font=f2)
    return sheet


def sizes(out, cols=2, tile=(900, 420)):
    names = sorted(f[:-5] for f in os.listdir(os.path.join(out, "_sizes")) if f.endswith(".json"))
    rows = math.ceil(len(names) / cols)
    lab = 34
    sheet = Image.new("RGB", (cols * tile[0], rows * (tile[1] + lab)), (24, 26, 28))
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(FONT, 22)
    for i, n in enumerate(names):
        r, k = divmod(i, cols)
        x, y = k * tile[0], r * (tile[1] + lab)
        meta = json.load(open(os.path.join(out, "_sizes", f"{n}.json")))
        sheet.paste(Image.open(os.path.join(out, "_sizes", f"{n}.png")).convert("RGB"), (x, y))
        d.text((x + 10, y + tile[1] + 4), f"{n}: {meta['dim']}  {' / '.join(meta['sizes'])}", fill=(230, 232, 235), font=f)
    return sheet


def main():
    out = os.path.abspath(sys.argv[1])
    docs = sys.argv[2] if len(sys.argv) > 2 else None
    kit = json.load(open(os.path.join(out, "kit.json")))
    cat, siz = catalogue(out, kit), sizes(out)
    cat.save(os.path.join(out, "kit_catalogue.png"))
    siz.save(os.path.join(out, "kit_sizes.png"))
    if docs:
        os.makedirs(docs, exist_ok=True)
        for img, name, width in ((cat, "kit-catalogue.jpg", 2400), (siz, "kit-sizes.jpg", 1600)):
            small = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
            q = jpeg_under(small, os.path.join(docs, name))
            print(name, os.path.getsize(os.path.join(docs, name)), "bytes, quality", q)


if __name__ == "__main__":
    main()
