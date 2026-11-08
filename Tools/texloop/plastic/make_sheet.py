"""The before/after sheet for black plastic (docs/texloop-plastic/plastic_before_after.jpg).

    python Tools/texloop/plastic/make_sheet.py [--renders Artifacts/texloop/plastic] [--out docs/texloop-plastic/plastic_before_after.jpg]

Top row: main before this PR (black plastic had no weathering, so every level is the same); bottom row: this PR.
Run render_levels.py with and without --before first.
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.dirname(HERE))
import wear  # noqa: E402

FONT = os.path.join(REPO, "Content", "UI", "Fonts", "SairaCondensed-Bold.ttf")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--renders", default=os.path.join(REPO, "Artifacts", "texloop", "plastic"))
    ap.add_argument("--out", default=os.path.join(REPO, "docs", "texloop-plastic", "plastic_before_after.jpg"))
    ap.add_argument("--scale", type=float, default=0.6)
    a = ap.parse_args()
    lv = wear.levels()
    tiles = {t: [Image.open(os.path.join(a.renders, t, "plastic_%s.png" % l["id"])) for l in lv] for t in ("before", "after")}
    w0, h0 = tiles["after"][0].size
    w, h = int(w0 * a.scale), int(h0 * a.scale)
    head, side = 46, 90
    sheet = Image.new("RGB", (side + w * 5, head + h * 2), (24, 26, 30))
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype(FONT, 22)
    except OSError:                          # the font is in Git LFS: a clone without it gets Pillow's own
        f = ImageFont.load_default(22)
    for i, l in enumerate(lv):
        d.text((side + i * w + 8, 10), "%s  %s" % (l["id"], l["name"]), fill=(235, 235, 235), font=f)
    for r, t in enumerate(("before", "after")):
        d.text((8, head + r * h + h // 2 - 12), t, fill=(235, 235, 235), font=f)
        for i, im in enumerate(tiles[t]):
            sheet.paste(im.resize((w, h), Image.LANCZOS), (side + i * w, head + r * h))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    sheet.save(a.out, quality=88)
    print(a.out)


if __name__ == "__main__":
    main()
