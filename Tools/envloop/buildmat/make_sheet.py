"""Contact sheets from render.py's output (Track E2): one per test house (lights down, 3 / 15 / 60 m across), before
beside after, the wear ladders, and the room atlas. Labels are drawn in, so a sheet stands on its own.

    python3 -I Tools/envloop/buildmat/make_sheet.py [--src Artifacts/envloop/buildmat] [--out <src>/sheets]
"""
import argparse
import glob
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pack as P    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, "Artifacts", "envloop", "buildmat")
LIGHTS = ["midday", "lowsun", "overcast"]
DISTS = [3, 15, 60]
LEVEL_NAMES = {"L0": "L0 new", "L1": "L1 months", "L2": "L2 club, 6 y", "L3": "L3 kept, 30 y", "L4": "L4 left, 20 y"}


def font(size):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def grid(cells, cols, labels_top, labels_left, title, cell_w=420):
    ims = [Image.open(c).convert("RGB") if c and os.path.exists(c) else None for c in cells]
    ref = next(i for i in ims if i is not None)
    ch = int(ref.height * cell_w / ref.width)
    rows = (len(cells) + cols - 1) // cols
    lw, th, pad = 110 if labels_left else 0, 60, 6
    W = lw + cols * (cell_w + pad)
    H = th + rows * (ch + pad)
    sheet = Image.new("RGB", (W, H), (245, 245, 240))
    d = ImageDraw.Draw(sheet)
    d.text((8, 6), title, fill=(20, 20, 20), font=font(20))
    for k, lab in enumerate(labels_top):
        d.text((lw + k * (cell_w + pad) + 4, 34), lab, fill=(60, 60, 60), font=font(15))
    for r, lab in enumerate(labels_left or []):
        d.text((6, th + r * (ch + pad) + ch // 2 - 8), lab, fill=(60, 60, 60), font=font(15))
    for i, im in enumerate(ims):
        if im is None:
            continue
        r, c = divmod(i, cols)
        sheet.paste(im.resize((cell_w, ch), Image.LANCZOS), (lw + c * (cell_w + pad), th + r * (ch + pad)))
    return sheet


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default=None)
    P.add_arg(ap)
    a = ap.parse_args()
    out = a.out or os.path.join(a.src, "sheets")
    os.makedirs(out, exist_ok=True)
    meta = json.load(open(os.path.join(a.src, "render.json")))
    houses = sorted({m["house"] for m in meta.values()})
    for h in houses:
        info = next(m for m in meta.values() if m["house"] == h)
        cells = [os.path.join(a.src, "%s_L2_%s_%dm.png" % (h, l, d)) for l in LIGHTS for d in DISTS]
        title = "%s: %s walls, %s roof, wear L2 (club, 6 years)" % (h, info["wall"], info["roof"])
        grid(cells, 3, ["%d m" % d for d in DISTS], LIGHTS, title).save(os.path.join(out, "house_%s.jpg" % h), quality=88)
        ba = [os.path.join(a.src, "before_%s_L2_%s_%dm.png" % (h, l, d)) for l in ("midday", "overcast") for d in (15, 60)]
        af = [os.path.join(a.src, "%s_L2_%s_%dm.png" % (h, l, d)) for l in ("midday", "overcast") for d in (15, 60)]
        cells = [ba[0], af[0], ba[1], af[1], ba[2], af[2], ba[3], af[3]]
        if all(os.path.exists(c) for c in cells):
            grid(cells, 2, ["before (main today)", "after (this branch)"], ["15 m sun", "60 m sun", "15 m overcast", "60 m overcast"],
                 "%s: before and after" % h).save(os.path.join(out, "before_after_%s.jpg" % h), quality=88)
        lv = [os.path.join(a.src, "%s_%s_overcast_15m.png" % (h, l)) for l in ("L0", "L2", "L4")]
        if all(os.path.exists(c) for c in lv):
            grid(lv, 3, ["L0 new", "L2 club, 6 y", "L4 left, 20 y"], None, "%s: age and care at 15 m, overcast" % h).save(
                os.path.join(out, "levels_%s.jpg" % h), quality=88)
    lad = sorted(glob.glob(os.path.join(a.src, "ladder_*_L0.png")))
    names = [os.path.basename(p)[7:-7] for p in lad]
    roofs = {c["name"] for c in P.load()["roofs"]}
    for group, sel in (("walls", [n for n in names if n not in roofs]), ("roofs", [n for n in names if n in roofs])):
        cells = [os.path.join(a.src, "ladder_%s_%s.png" % (n, l)) for n in sel for l in LEVEL_NAMES]
        if cells:
            grid(cells, 5, list(LEVEL_NAMES.values()), [n.replace("_", " ") for n in sel], "Wear ladder, %s: 1.6 m of each finish from 2 m, overcast" % group,
                 cell_w=300).save(os.path.join(out, "ladder_%s.jpg" % group), quality=88)
    atlas = os.path.join(REPO, "Data", "BuildMat", "raw", "out", "T_RoomAtlas.png")
    if os.path.exists(atlas):
        Image.open(atlas).convert("RGB").save(os.path.join(out, "room_atlas.jpg"), quality=88)
    print(out)


if __name__ == "__main__":
    main()
