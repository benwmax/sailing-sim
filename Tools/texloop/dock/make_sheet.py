"""Before/after sheet for the club docks (docs/texloop-dock/dock_before_after.jpg): main's shader on top, this branch
below, L0 to L4 left to right. Run render_levels.py --rev <base> --tag old and render_levels.py first.

    python Tools/texloop/dock/make_sheet.py [--out docs/texloop-dock/dock_before_after.jpg]
"""
import argparse
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, "Artifacts", "texloop", "dock")
NAMES = {"L0": "L0 new", "L1": "L1 months", "L2": "L2 club, 6 y", "L3": "L3 kept, 30 y", "L4": "L4 left, 20 y"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "docs", "texloop-dock", "dock_before_after.jpg"))
    a = ap.parse_args()
    w, h, top, left = 512, 384, 28, 70
    sheet = Image.new("RGB", (left + 5 * w, top + 2 * h), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for i, lv in enumerate(NAMES):
        d.text((left + i * w + 8, 8), NAMES[lv], fill=(230, 230, 230))
        for j, tag in enumerate(("old", "new")):
            sheet.paste(Image.open(os.path.join(SRC, f"{tag}_{lv}.png")).convert("RGB").resize((w, h)), (left + i * w, top + j * h))
    d.text((8, top + h // 2), "before", fill=(230, 230, 230))
    d.text((8, top + h + h // 2), "after", fill=(230, 230, 230))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    sheet.save(a.out, quality=88)
    print(a.out)


if __name__ == "__main__":
    main()
