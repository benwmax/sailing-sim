"""A before/after sheet for Bean: one row per wear level, the material before the round beside after it, with the
measured numbers under each, and a CC0 reference crop where the level has one (docs/texture-loop).

    python Tools/texloop/make_sheet.py gelcoat [--out docs/texture-loop/gelcoat_before_after.jpg]

Only references with use "ship" (CC0, public domain, our own photos) go on a sheet that is committed; measure-only
photos (CC BY, BY-SA, FAL) are left off it, so the repo never redistributes them.
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))


def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("surface")
    ap.add_argument("--renders", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--tile", type=int, default=420)
    a = ap.parse_args()
    root = a.renders or os.path.join(REPO, "Artifacts", "texloop", a.surface)
    out = a.out or os.path.join(REPO, "docs", "texture-loop", a.surface + "_before_after.jpg")
    levels = json.load(open(os.path.join(HERE, "levels.json")))["levels"]
    refs = json.load(open(os.path.join(HERE, "refs", a.surface + ".json")))["refs"]
    score_path = os.path.join(HERE, "scores", a.surface + ".json")
    score = json.load(open(score_path)) if os.path.exists(score_path) else None
    T = a.tile
    th = int(T * 0.75)
    head, lab = 46, 64
    W = 220 + 3 * (T + 12)
    H = head + len(levels) * (th + lab + 12)
    sheet = Image.new("RGB", (W, H), (250, 250, 248))
    d = ImageDraw.Draw(sheet)
    f1, f2, f3 = font(20), font(15), font(13)
    d.text((12, 12), "%s: before (one wear number) | after (time and dirt) | CC0 reference" % a.surface.capitalize(), fill=(20, 20, 20), font=f1)
    for i, lv in enumerate(levels):
        y = head + i * (th + lab + 12)
        d.text((12, y + 8), "%s %s" % (lv["id"], lv["name"]), fill=(20, 20, 20), font=f2)
        d.text((12, y + 30), "age %g yr, care %g" % (lv["age"], lv["care"]), fill=(90, 90, 90), font=f3)
        for j, tag in enumerate(("before", "after")):
            p = os.path.join(root, tag, "%s_%s.png" % (a.surface, lv["id"]))
            if not os.path.exists(p):
                continue
            im = Image.open(p).convert("RGB")
            im.thumbnail((T, th))
            x = 220 + j * (T + 12)
            sheet.paste(im, (x, y))
            if score:
                nums = (score["numbers"][tag] or {}).get(lv["id"], {}).get("topsides")
                if nums:
                    d.text((x, y + th + 4), "b* %.1f  mottle %.1f  gloss %.1f" % (nums["b"], nums["mottle"], nums["gloss"]),
                           fill=(60, 60, 60), font=f3)
        ship = [r for r in refs if r["level"] == lv["id"] and r.get("use") == "ship" and r.get("box")]
        if ship:
            r = ship[0]
            p = os.path.join(REPO, "Data", "Reference", "raw", "textures", a.surface.capitalize(), r["level"], r["id"] + ".jpg")
            if os.path.exists(p):
                im = Image.open(p).convert("RGB")
                w, h = im.size
                x0, y0, x1, y1 = r["box"]
                cx, cy = (x0 + x1) / 2 * w, (y0 + y1) / 2 * h
                half = max((x1 - x0) * w, (y1 - y0) * h * 4 / 3) * 0.75
                im = im.crop((int(max(cx - half, 0)), int(max(cy - half * 0.75, 0)), int(min(cx + half, w)), int(min(cy + half * 0.75, h))))
                im.thumbnail((T, th))
                x = 220 + 2 * (T + 12)
                sheet.paste(im, (x, y))
                d.text((x, y + th + 4), "%s (CC0)" % r["id"][:44], fill=(60, 60, 60), font=f3)
        if score and score["colour"]["levels"].get(lv["id"], {}).get("target"):
            t = score["colour"]["levels"][lv["id"]]
            d.text((12, y + 52), "photos: b* %.1f" % t["target"][1], fill=(90, 90, 90), font=f3)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out, quality=88)
    print(out)


if __name__ == "__main__":
    main()
