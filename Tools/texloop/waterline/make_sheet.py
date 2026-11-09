"""Before/after sheet for Bean: one row per wear level, the reference photo crop beside main's render and this round's.

    python3 Tools/texloop/waterline/make_sheet.py <render_dir> <out.jpg> [--ref photo.jpg x0 y0 x1 y1]

The reference crop (L2 only so far: TX 7295 EC, Bean's photo) is shown, never committed.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 600, 350


def font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def tile(path):
    if path and os.path.exists(path):
        im = Image.open(path).convert("RGB")
        im.thumbnail((W, H))
        t = Image.new("RGB", (W, H), (235, 235, 232))
        t.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
        return t
    t = Image.new("RGB", (W, H), (235, 235, 232))
    ImageDraw.Draw(t).text((20, H // 2 - 10), "no photo yet (club close-ups wanted)", fill=(120, 120, 120), font=font(20))
    return t


def main():
    a = sys.argv[1:]
    rd, out = a[0], a[1]
    ref = None
    if "--ref" in a:
        i = a.index("--ref")
        ref = (a[i + 1], [int(v) for v in a[i + 2:i + 6]])
    levels = ["L0", "L1", "L2", "L3", "L4"]
    names = {"L0": "L0 new", "L1": "L1 a few months", "L2": "L2 club boat", "L3": "L3 old, kept", "L4": "L4 neglected"}
    cols = ["Reference", "Before: close", "After: close", "Before: bottom", "After: bottom"]
    score = {}
    sp = os.path.join(rd, "score.json")
    if os.path.exists(sp):
        score = json.load(open(sp))
    lw, top = 210, 50
    sheet = Image.new("RGB", (lw + W * len(cols), top + H * len(levels)), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    for j, c in enumerate(cols):
        d.text((lw + j * W + 12, 14), c, fill=(20, 20, 20), font=font(24))
    for i, lv in enumerate(levels):
        y = top + i * H
        d.text((10, y + 20), names[lv], fill=(20, 20, 20), font=font(22))
        s = score.get(lv, {})
        if s:
            d.text((10, y + 56), "dirt %.2f  time %.2f" % (s.get("dirt", 0), s.get("time", 0)), fill=(80, 80, 80), font=font(16))
            m = s.get("measured")
            if m:
                d.text((10, y + 80), "line %.0f%% of hull" % (100 * m["line_Y_ratio"]), fill=(80, 80, 80), font=font(16))
                d.text((10, y + 102), "height %.1f cm" % m["line_height_cm"], fill=(80, 80, 80), font=font(16))
            d.text((10, y + 128), "targets: %s" % ("pass" if s.get("pass") else "MISS"), fill=(0, 110, 0) if s.get("pass") else (170, 0, 0), font=font(16))
        if lv == "L2" and ref:
            im = Image.open(ref[0]).convert("RGB").crop(tuple(ref[1]))
            r = tile(None)
            im.thumbnail((W, H))
            r.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
            ImageDraw.Draw(r).text((10, H - 26), "TX 7295 EC on her lift, Rush Creek (Bean)", fill=(60, 60, 60), font=font(16))
        else:
            r = tile(None)
        sheet.paste(r, (lw, y))
        for j, (tag, v) in enumerate((("before", "close"), ("after", "close"), ("before", "heel"), ("after", "heel"))):
            sheet.paste(tile(os.path.join(rd, "%s_%s_%s.png" % (tag, lv, v))), (lw + (j + 1) * W, y))
    sheet.save(out, quality=88)
    print("sheet", out, sheet.size)


if __name__ == "__main__":
    main()
