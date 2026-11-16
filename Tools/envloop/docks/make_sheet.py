"""Environment loop: a labelled contact sheet from render_envloop.py's output (for the docs, the blind rounds and
Bean's one-page look).

Usage: python3 Tools/envloop/docks/make_sheet.py <render dir> <out.jpg> [--shots midday_15m,low_15m] [--only SM_A,SM_B]
       [--cols 4] [--width 1600] [--title "..."]
Each tile is one mesh x one shot, labelled with the mesh name (less SM_) and the shot.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont


def main():
    a = sys.argv[1:]

    def opt(k, d):
        return a[a.index(k) + 1] if k in a else d
    src, out = a[0], a[1]
    shots = opt("--shots", "midday_15m").split(",")
    only = opt("--only", None)
    cols = int(opt("--cols", "4"))
    width = int(opt("--width", "1600"))
    title = opt("--title", "")
    names = sorted(d for d in os.listdir(src) if os.path.isdir(os.path.join(src, d)))
    if only:
        names = [n for n in only.split(",") if n in names]
    tiles = []
    for n in names:
        for s in shots:
            p = os.path.join(src, n, s + ".png")
            if os.path.exists(p):
                tiles.append((n, s, p))
    if not tiles:
        sys.exit("no tiles")
    tw = width // cols
    im0 = Image.open(tiles[0][2])
    th = int(tw * im0.height / im0.width)
    head = 40 if title else 0
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (width, head + rows * (th + 22)), (24, 26, 28))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 15)
        big = ImageFont.truetype("DejaVuSans.ttf", 22)
    except OSError:
        font = big = ImageFont.load_default()
    if title:
        d.text((10, 8), title, fill=(235, 235, 235), font=big)
    for i, (n, s, p) in enumerate(tiles):
        r, c = divmod(i, cols)
        x, y = c * tw, head + r * (th + 22)
        sheet.paste(Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS), (x, y + 22))
        label = n.replace("SM_", "") + ("  " + s if len(shots) > 1 else "")
        d.text((x + 6, y + 3), label, fill=(220, 220, 220), font=font)
    sheet.save(out, quality=88)
    print(f"Sheet: {out} {len(tiles)} tiles")


main()
