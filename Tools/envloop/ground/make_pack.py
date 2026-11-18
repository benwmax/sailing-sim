"""Track A: the blind-review pack and the before/after sheet for a render round.

    python3 -I Tools/envloop/ground/make_pack.py --renders Artifacts/envloop/ground/r1 [--seed 1]

Writes <renders>/blind/<view>.jpg (the two renders side by side as A and B, sides shuffled by seed), the key
Tools/envloop/ground/reviews/<round>_key.json, and <renders>/sheet_<station>.jpg (before over after, every view of
that station, labelled) for Bean's look. Reviewers get only the blind folder and the question; the key never goes to
them. Track 0's shared sheet maker replaces the sheet half once it merges.
"""
import argparse
import json
import os
import random

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--renders", required=True)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    rnd = os.path.basename(os.path.normpath(args.renders))
    views = json.load(open(os.path.join(args.renders, "views.json")))["views"]
    rng = random.Random(args.seed)
    os.makedirs(os.path.join(args.renders, "blind"), exist_ok=True)
    key = {}
    for v in views:
        b = Image.open(os.path.join(args.renders, f"{v['name']}_before.png"))
        a = Image.open(os.path.join(args.renders, f"{v['name']}_after.png"))
        left_after = rng.random() < 0.5
        L, R = (a, b) if left_after else (b, a)
        im = Image.new("RGB", (b.width * 2 + 12, b.height + 28), (24, 24, 24))
        im.paste(L, (0, 28))
        im.paste(R, (b.width + 12, 28))
        d = ImageDraw.Draw(im)
        d.text((8, 8), "A", fill=(255, 255, 255))
        d.text((b.width + 20, 8), "B", fill=(255, 255, 255))
        im.save(os.path.join(args.renders, "blind", f"{v['name']}.jpg"), quality=90)
        key[v["name"]] = {"A": "after" if left_after else "before", "B": "before" if left_after else "after"}
    os.makedirs(os.path.join(HERE, "reviews"), exist_ok=True)
    json.dump(key, open(os.path.join(HERE, "reviews", f"{rnd}_key.json"), "w"), indent=1)
    for st in sorted({v["station"] for v in views}):
        vs = [v for v in views if v["station"] == st]
        w, h = 480, 270
        sheet = Image.new("RGB", (w * 2 + 8, (h + 22) * len(vs)), (24, 24, 24))
        d = ImageDraw.Draw(sheet)
        for i, v in enumerate(vs):
            y = i * (h + 22)
            d.text((6, y + 5), f"{v['name']}: before (today)", fill=(230, 230, 230))
            d.text((w + 14, y + 5), "after (layered ground)", fill=(230, 230, 230))
            sheet.paste(Image.open(os.path.join(args.renders, f"{v['name']}_before.png")).resize((w, h)), (0, y + 22))
            sheet.paste(Image.open(os.path.join(args.renders, f"{v['name']}_after.png")).resize((w, h)), (w + 8, y + 22))
        sheet.save(os.path.join(args.renders, f"sheet_{st}.jpg"), quality=88)


if __name__ == "__main__":
    main()
