"""Station sheet for Bean (docs/env-loop/README.md, steps 7 and 8): one row per station, before and after at each of
the three distances, so a track's change is seen from the same cameras every time.

    python3 Tools/envloop/make_sheet.py --before DIR --after DIR --out sheet.jpg [--stations a,b] [--distances 5,15,60]

DIR holds capture-scenes.sh output (env-<station>-<dd>m.png). A missing picture leaves its cell grey and labelled.
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))


def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after")
    ap.add_argument("--out", required=True)
    ap.add_argument("--stations")
    ap.add_argument("--distances", default="5,15,60")
    ap.add_argument("--tile", type=int, default=400)
    a = ap.parse_args()
    data = json.load(open(os.path.join(HERE, "stations.json")))
    st = [s for s in data["stations"] if not a.stations or s["id"] in a.stations.split(",")]
    dists = [int(d) for d in a.distances.split(",")]
    cols = [("before", a.before)] + ([("after", a.after)] if a.after else [])
    T, th = a.tile, a.tile * 9 // 16
    W = 180 + len(dists) * len(cols) * (T + 6)
    H = 40 + len(st) * (th + 30)
    sheet = Image.new("RGB", (W, H), (248, 248, 246))
    d = ImageDraw.Draw(sheet)
    d.text((10, 10), "Shore stations: " + " | ".join("%s at %s m" % (c[0], ", ".join(map(str, dists))) for c in cols), fill=(0, 0, 0), font=font(18))
    for i, s in enumerate(st):
        y = 40 + i * (th + 30)
        d.text((10, y + 6), s["name"], fill=(0, 0, 0), font=font(14))
        x = 180
        for j, dist in enumerate(dists):
            for label, folder in cols:
                p = os.path.join(folder, "env-%s-%02dm.png" % (s["id"], dist))
                if os.path.exists(p):
                    sheet.paste(Image.open(p).convert("RGB").resize((T, th), Image.LANCZOS), (x, y))
                else:
                    d.rectangle((x, y, x + T, y + th), fill=(200, 200, 200))
                    d.text((x + 8, y + 8), "missing", fill=(90, 90, 90), font=font(13))
                d.text((x, y + th + 4), "%s, %d m" % (label, dist), fill=(70, 70, 70), font=font(12))
                x += T + 6
    sheet.save(a.out, quality=88)
    print(a.out)


if __name__ == "__main__":
    main()
