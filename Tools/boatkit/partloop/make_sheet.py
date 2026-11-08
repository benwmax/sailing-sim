"""Part detail loop, step 8: the before/after sheet for review (docs/part-detail-loop).

    python3 Tools/boatkit/partloop/make_sheet.py <ref photo> <before dir> <after dir> <out.jpg>
        [--title T] [--credit "photo credit"] [--in-use <photo crop>] [--in-use-label L] [--line "12 mm line"] [--zoom 0.6]
        [--ref-label L] [--assembly <before dir> <after dir>]

Row 1: the square-on reference photo, then the side view before and after at the same scale. Row 2: three-quarter
before and after, and the after from below. Row 3: edge-on before and after, and the after in clay. Optional row: a crop
of the part in use on a real boat beside both rounds' in_use renders. Last row: the scorecards from each round's
score.json and the after's outline overlap (grey both, blue model only, red photo only). The photos are only laid out
in the sheet: keep sheets that show a third party's photo out of the repo, and credit a CC BY/BY-SA photo with
--credit (printed under the sheet).
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont, ImageOps

T = 460
BG, INK, QUIET = (250, 250, 248), (20, 22, 24), (110, 112, 116)


def font(size, bold=False):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/System/Library/Fonts/Supplemental/Arial.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def tile(path, box=T, crop=1.0):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    if crop < 1.0:
        w, h = im.size
        cw, ch = int(w * crop), int(h * crop)
        im = im.crop(((w - cw) // 2, (h - ch) // 2, (w + cw) // 2, (h + ch) // 2))
    k = box / max(im.size)                          # fit the tile, enlarging a small crop too
    im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    out = Image.new("RGB", (box, box), BG)
    out.paste(im, ((box - im.width) // 2, (box - im.height) // 2))
    return out


def card(score, label):
    im = Image.new("RGB", (T, T), BG)
    d = ImageDraw.Draw(im)
    d.text((16, 14), label, fill=INK, font=font(22, True))
    y = 54
    for s in score["sizes"]:
        if s["target"] is None:
            continue
        ok = s["pass"]
        g = f"{s['got']:.2f}" if s["got"] < 5 else f"{s['got']:.0f} mm"
        d.text((16, y), f"{'✓' if ok else '✗'} {s['name'][:34]}: {g} ({round(s['err'] * 100) + 0:+d}%)", fill=INK if ok else (190, 40, 30), font=font(15))
        y += 24
    o = score.get("outline")
    if o:
        d.text((16, y), f"{'✓' if o['pass'] else '✗'} Outline overlap with the photo: {o['iou'] * 100:.0f}%", fill=INK if o["pass"] else (190, 40, 30), font=font(15))
        y += 24
    n = sum(f["pass"] for f in score["features"])
    miss = [f["id"] for f in score["features"] if not f["pass"]]
    d.text((16, y), f"{'✓' if not miss else '✗'} Features {n}/{len(score['features'])}", fill=INK if not miss else (190, 40, 30), font=font(15))
    y += 22
    for m in miss[:8]:
        d.text((34, y), f"missing: {m}", fill=QUIET, font=font(13))
        y += 19
    b = score["budget"]
    d.text((16, y + 4), f"{'✓' if b['pass'] else '✗'} Budget: {b['tris']:,} triangles, {b['slots']} materials", fill=INK if b["pass"] else (190, 40, 30), font=font(15))
    y += 30
    bl = score.get("review")
    if bl:
        d.text((16, y), f"{'✓' if bl.get('pass') else '✗'} Blind reviews: {bl.get('wins', '?')} of {bl.get('runs', '?')} picked this", fill=INK if bl.get("pass") else (190, 40, 30), font=font(15))
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ref")
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("out")
    ap.add_argument("--title", default="Before and after")
    ap.add_argument("--credit", default="")
    ap.add_argument("--in-use", dest="in_use", default="")
    ap.add_argument("--in-use-label", dest="in_use_label", default="In use on a real boat (photo crop)")
    ap.add_argument("--line", default="10 mm line", help="the in-use renders' line, for their captions")
    ap.add_argument("--zoom", type=float, default=1.0, help="crop the renders to this share of the frame (0.6 for a long, low part)")
    ap.add_argument("--ref-label", dest="ref_label", default="Reference photo (square-on)")
    ap.add_argument("--assembly", nargs=2, metavar=("BEFORE", "AFTER"), default=None,
                    help="render_assembly.py output dirs: adds a row of the part in place, before and after")
    a = ap.parse_args()
    z = a.zoom
    ref, before, after, out, title = a.ref, a.before, a.after, a.out, a.title
    sb = json.load(open(os.path.join(before, "score.json")))
    sa = json.load(open(os.path.join(after, "score.json")))
    rows = [
        [(tile(ref), a.ref_label), (tile(os.path.join(before, "side.png"), crop=z), "Before: side"), (tile(os.path.join(after, "side.png"), crop=z), "After: side")],
        [(tile(os.path.join(before, "threeq.png"), crop=z), "Before: three-quarter"), (tile(os.path.join(after, "threeq.png"), crop=z), "After: three-quarter"),
         (tile(os.path.join(after, "threeq_low.png"), crop=z), "After: from below, far side")],
        [(tile(os.path.join(before, "edge.png"), crop=z), "Before: edge-on"), (tile(os.path.join(after, "edge.png"), crop=z), "After: edge-on"),
         (tile(os.path.join(after, "clay.png"), crop=z), "After: clay (shape only)")],
    ]
    if a.in_use:
        rows.append([(tile(a.in_use), a.in_use_label), (tile(os.path.join(before, "in_use.png")), f"Before: in use, {a.line}"),
                     (tile(os.path.join(after, "in_use.png")), f"After: in use, {a.line}")])
    if a.assembly:
        ab, aa = a.assembly
        rows.append([(tile(os.path.join(ab, "threeq.png")), "Before: in place on the J/22"), (tile(os.path.join(aa, "threeq.png")), "After: in place on the J/22"),
                     (tile(os.path.join(aa, "close.png")), "After: in place, close")])
    oc = os.path.join(after, "outline_compare.png")
    # a card without a square-on reference has no outline compare: show the after's clay outline instead
    last = (tile(oc, crop=1.0), "After outline vs photo (blue ours, red photo)") if os.path.exists(oc) else \
        (tile(os.path.join(after, "outline_side.png")), "After outline (no square-on photo to compare)")
    rows += [[(card(sb, "Before"), ""), (card(sa, "After"), ""), last]]
    pad, cap, head = 14, 30, 64
    W = 3 * T + 4 * pad
    foot = 34 if a.credit else 0
    H = head + len(rows) * (T + cap + pad) + pad + foot
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    d.text((pad, 18), title, fill=INK, font=font(26, True))
    for r, row in enumerate(rows):
        y = head + r * (T + cap + pad)
        for c, (im, lab) in enumerate(row):
            x = pad + c * (T + pad)
            sheet.paste(im, (x, y))
            d.text((x + 4, y + T + 6), lab, fill=QUIET, font=font(15))
    if a.credit:
        d.text((pad, H - foot), a.credit, fill=QUIET, font=font(14))
    sheet.save(out, quality=90)
    print(f"Sheet: {out}")


if __name__ == "__main__":
    main()
