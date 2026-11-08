"""Part detail loop, step 8 for long parts: the before/after sheet from render_long.py's views (docs/part-detail-loop/tiller.md).
make_sheet.py lays out render_views.py's square stills, in which a tiller is a thin line; this lays out the whole-length
three-quarter view and each end close up, before above after, one section per part, with each round's scorecard.

    python3 Tools/boatkit/partloop/make_long_sheet.py <out.jpg> --title T \
        --section "Wooden tiller (J/22)" <before dir or -> <after dir> [--section ...]

Needs Pillow. Each round dir holds render_long.py's views and (optionally) score.json from score.py.
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

W = 1800
BG, INK, QUIET = (250, 250, 248), (20, 22, 24), (110, 112, 116)


def font(size, bold=False):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/System/Library/Fonts/Supplemental/Arial.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def tile(d, name, w, h):
    p = os.path.join(d, f"{name}.png")
    if d == "-" or not os.path.exists(p):
        im = Image.new("RGB", (w, h), (236, 236, 234))
        ImageDraw.Draw(im).text((20, h // 2 - 14), "(none in the kit before)" if d == "-" else "(not rendered)", fill=QUIET, font=font(24))
        return im
    return Image.open(p).convert("RGB").resize((w, h))


def score_line(d):
    p = os.path.join(d, "score.json")
    if d == "-" or not os.path.exists(p):
        return ""
    s = json.load(open(p))
    bits = []
    for z in s.get("sizes", []):
        if z.get("target"):
            bits.append(f"{z['id']} {z['got']:.0f} mm (target {z['target']:.0f})")
    f = s.get("features", [])
    if f:
        bits.append(f"features {sum(1 for x in f if x.get('pass'))}/{len(f)}")
    b = s.get("budget") or {}
    if b:
        bits.append(f"{b['tris']:,} tris, {b['slots']} slots")
    bl = s.get("review")
    if bl:
        bits.append(f"blind: won {bl.get('wins')} of {bl.get('runs')} vs {bl.get('vs')}")
    return "   ".join(bits)


def section(title, before, after):
    rows = []
    hdr = Image.new("RGB", (W, 64), BG)
    ImageDraw.Draw(hdr).text((20, 14), title, fill=INK, font=font(34, True))
    rows.append(hdr)
    for label, d in (("Before", before), ("After", after)):
        lab = Image.new("RGB", (W, 44), BG)
        dr = ImageDraw.Draw(lab)
        dr.text((20, 8), label, fill=INK, font=font(26, True))
        dr.text((150, 12), score_line(d), fill=QUIET, font=font(21))
        if d == "-":     # a new part: one line, no empty tiles
            dr.text((150, 12), "(none in the kit before)", fill=QUIET, font=font(21))
            rows.append(lab)
            continue
        rows.append(lab)
        rows.append(tile(d, "long_threeq", W, 600))
        strip = Image.new("RGB", (W, 450), BG)
        for i, n in enumerate(("aft_threeq", "aft_side", "fwd_threeq", "with_ext_close" if d != "-" and os.path.exists(os.path.join(d, "with_ext_close.png")) else "fwd_side")):
            strip.paste(tile(d, n, 450, 450), (i * 450, 0))
        rows.append(strip)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--title", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--section", nargs=3, action="append", metavar=("TITLE", "BEFORE", "AFTER"), default=[])
    a = ap.parse_args()
    rows = []
    top = Image.new("RGB", (W, 110 if a.note else 80), BG)
    d = ImageDraw.Draw(top)
    d.text((20, 18), a.title, fill=INK, font=font(42, True))
    if a.note:
        d.text((20, 72), a.note, fill=QUIET, font=font(22))
    rows.append(top)
    for t, b, af in a.section:
        rows += section(t, b, af)
    H = sum(r.height for r in rows)
    sheet = Image.new("RGB", (W, H), BG)
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height
    sheet.save(a.out, quality=88)
    print(f"Sheet: {a.out} ({W} x {H})")


if __name__ == "__main__":
    main()
