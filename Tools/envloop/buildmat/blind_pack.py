"""Blind review pack for the building materials (Track E2): before/after pairs with A and B shuffled, and the wear
ladders with their levels shuffled under letters. The key stays in key.json next to the pack (reviewers never see it).

    python3 -I Tools/envloop/buildmat/blind_pack.py [--seed 1] [--out Artifacts/envloop/buildmat/blind]
"""
import argparse
import glob
import json
import os
import random
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_sheet as MS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = MS.SRC


def pair(a, b, out):
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    w, h = ia.size
    sheet = Image.new("RGB", (2 * w + 12, h + 40), (245, 245, 240))
    d = ImageDraw.Draw(sheet)
    for k, im in enumerate((ia, ib)):
        sheet.paste(im, (k * (w + 12), 40))
        d.text((k * (w + 12) + 8, 8), "AB"[k], fill=(0, 0, 0), font=MS.font(24))
    sheet.save(out, quality=90)


def ladder(cells, out):
    ims = [Image.open(c).convert("RGB").resize((300, 225)) for c in cells]
    sheet = Image.new("RGB", (len(ims) * 306, 265), (245, 245, 240))
    d = ImageDraw.Draw(sheet)
    for k, im in enumerate(ims):
        sheet.paste(im, (k * 306, 40))
        d.text((k * 306 + 8, 8), "VWXYZ"[k], fill=(0, 0, 0), font=MS.font(22))
    sheet.save(out, quality=90)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=os.path.join(SRC, "blind"))
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    os.makedirs(a.out, exist_ok=True)
    key = {"pairs": {}, "ladders": {}}
    meta = json.load(open(os.path.join(SRC, "render.json")))
    houses = sorted({m["house"] for m in meta.values()})
    for i, h in enumerate(houses):
        for light in ("midday", "overcast"):
            before = os.path.join(SRC, "before_%s_L2_%s_15m.png" % (h, light))
            after = os.path.join(SRC, "%s_L2_%s_15m.png" % (h, light))
            if not (os.path.exists(before) and os.path.exists(after)):
                continue
            flip = rnd.random() < 0.5
            name = "pair_%02d_%s.jpg" % (i, light)
            pair(*(after, before) if flip else (before, after), out=os.path.join(a.out, name))
            key["pairs"][name] = dict(house=h, light=light, after="A" if flip else "B")
    for p in sorted(glob.glob(os.path.join(SRC, "ladder_*_L0.png"))):
        fin = os.path.basename(p)[7:-7]
        levels = ["L0", "L1", "L2", "L3", "L4"]
        order = levels[:]
        rnd.shuffle(order)
        name = "ladder_%s.jpg" % fin
        ladder([os.path.join(SRC, "ladder_%s_%s.png" % (fin, l)) for l in order], os.path.join(a.out, name))
        key["ladders"][name] = dict(finish=fin, letters={"VWXYZ"[k]: l for k, l in enumerate(order)})
    json.dump(key, open(os.path.join(a.out, "key.json"), "w"), indent=1)
    print(a.out, len(key["pairs"]), "pairs", len(key["ladders"]), "ladders")


if __name__ == "__main__":
    main()
