"""The sails' check against the 1817 sail plan (docs/shipkit-5): the sails as sails.py builds them, drawn flat back onto
'A Draft of the U.S. Frigate Constitution' (NARA 102278445), and tables of their sizes.

    python sails_check.py <1817 draught scan.jpg> <out dir>          (plain Python: numpy, scipy, Pillow)

Writes <out>/sails.md (the numbers), <out>/sails_check.json and <out>/overlay_sails.jpg, with zooms of each mast
(overlay_sails_<mast>.jpg) and the headsails (overlay_sails_bow.jpg), at half the scan's scale. A sail plan draws the
square sails face on, so they are drawn here the same way: each square sail's head and clews at their heights, spread
about its mast by their distance from the yard's middle (the model's set sails bow forward, which a flat plan can't
show), and a course with its clews where it is cut (set, they are hauled in to the ship's side). On the overlays:

  red      square sails: head, leeches and the foot with its roach
  orange   their reef bands
  blue     headsails and staysails (tack, head, clew)
  green    the spanker (throat, peak, clew, tack)
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loft  # noqa: E402
import rigging  # noqa: E402
import sails  # noqa: E402
import skin  # noqa: E402
import spars  # noqa: E402

FT = loft.FT
RED, ORANGE, BLUE, GREEN = (255, 30, 30), (255, 150, 0), (0, 90, 255), (0, 200, 0)
SQUARE = ("course", "topsail", "topgallant", "royal")
Image.MAX_IMAGE_PIXELS = None


def name(k):
    return k.replace("_", " ").capitalize()


def main(scan, out):
    os.makedirs(out, exist_ok=True)
    L = loft.Lines()
    rig = spars.Rig(L, json.load(open(os.path.join(HERE, "specs_1795.json")))).build()
    SK = skin.Skin(L, stem_bed=rig.stem_bed).build()
    st = rigging.Standing(rig, SK).build()
    sv = sails.Sails(rig, st).build()
    reg = rig.sp["registration"]
    ppf = reg["px_per_ft"]

    def to_d(x_m, z_m):
        """Ship metres (x forward of midships, z above A) to the draught's pixels."""
        xpx = L.mid_px + np.asarray(x_m, float) / FT * L.ppf
        xd = reg["x_scale"] * xpx + reg["x_offset"]
        yd = reg["y0"] + reg["y_tilt"] * xd - ppf * np.asarray(z_m, float) / FT
        return xd, yd

    im = Image.open(scan).convert("RGB")
    dr = ImageDraw.Draw(im)
    res = {}
    for key, I in sv.info.items():
        if I["kind"] in SQUARE:
            o, R = rig.parts_[I["yard"]]["frame"]
            xd0, _ = to_d(o[0], o[2])

            def P(p):
                w = o + R @ np.asarray(p, float)
                return (float(xd0 + p[1] / FT * ppf), float(to_d(w[0], w[2])[1]))

            he, cl = np.array(I["head_earing_local_m"]), np.array(I["clew_cut_local_m"])     # as cut (a sail plan's)
            mir = np.array([1.0, -1.0, 1.0])
            roach = I["roach_ft"] * FT
            foot = [P(cl * (1 - u) + cl * mir * u + np.array([0, 0, roach * (1 - (2 * u - 1) ** 2)]))
                    for u in np.linspace(0, 1, 21)]
            dr.line([P(he * mir), P(he), P(cl)] + foot + [P(cl * mir), P(he * mir)], fill=RED, width=3)
            for rk in I["reefs"]:
                z = he[2] - rk * I["depth_ft"] * FT
                y = abs(he[1]) + (abs(cl[1]) - abs(he[1])) * (he[2] - z) / (he[2] - cl[2]) + FT
                dr.line([P([he[0], -y, z]), P([he[0], y, z])], fill=ORANGE, width=2)
            wc, wh, ws = o + R @ cl, o + R @ he, o + R @ np.array(I["clew_local_m"])
            res[key] = {"kind": I["kind"], "head_z_ft": round(float(wh[2] / FT), 1),
                        "clew_z_ft": round(float(wc[2] / FT), 1), "half_head_ft": round(float(abs(he[1]) / FT), 1),
                        "half_foot_ft": round(float(abs(cl[1]) / FT), 1),
                        "set_clew_ft": [round(float(v / FT), 1) for v in ws]}
        elif I["kind"] == "spanker":
            o, R = rig.parts_["SpankerGaff"]["frame"]
            c = I["corners_gaff_frame_m"]
            W = {k: o + R @ np.array(c[k]) for k in ("throat", "peak", "clew", "tack")}
            pts = [to_d(W[k][0], W[k][2]) for k in ("throat", "peak", "clew", "tack", "throat")]
            dr.line([(float(a), float(b)) for a, b in pts], fill=GREEN, width=3)
            res[key] = {"kind": "spanker", **{k: [round(float(v[0] / FT), 1), round(float(v[2] / FT), 1)]
                                              for k, v in W.items()}}
        else:
            pts = [to_d(I[k][0], I[k][2]) for k in ("tack_m", "head_m", "clew_m", "tack_m")]
            dr.line([(float(a), float(b)) for a, b in pts], fill=BLUE, width=3)
            res[key] = {"kind": I["kind"], **{k[:-2]: [round(I[k][0] / FT, 1), round(I[k][2] / FT, 1)]
                                              for k in ("tack_m", "head_m", "clew_m")}}

    def half(box, path):
        c = im.crop(tuple(int(v) for v in box))
        c.resize((c.width // 2, c.height // 2), Image.LANCZOS).save(os.path.join(out, path), quality=82)

    for n, m in rig.masts.items():
        xc = float(to_d(m["O"][0], 0.0)[0])
        half((xc - 700, 40, xc + 700, 2100), f"overlay_sails_{n}.jpg")
    half((2500, 300, 3840, 2100), "overlay_sails_bow.jpg")
    im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS).save(
        os.path.join(out, "overlay_sails.jpg"), quality=74)

    # the draught's main course, as read for sails_1797.json (square.course.src)
    mc = res.get("main_course", {})
    draught_main = {"clew_z_ft": 26.8, "half_foot_ft": 51.6, "half_head_ft": 45.6}
    json.dump({"sails": res, "info": sv.info, "draught_main_course": draught_main}, open(
        os.path.join(out, "sails_check.json"), "w"), indent=1)
    with open(os.path.join(out, "sails.md"), "w") as fh:
        fh.write("# Sails against the 1817 draught\n\n")
        fh.write("Square sails, feet: the head and foot across, the depth from the yard to the foot's middle "
                 "(less the roach), the roach (the table's least, then the depth the clearance needed and what it "
                 "clears), the reef bands and the belly's depth when set.\n\n")
        fh.write("| Sail | Head | Foot | Depth | Area sq ft | Reefs | Belly | Roach (table) | Roach clears |\n"
                 "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |\n")
        for k, I in sv.info.items():
            if I["kind"] in SQUARE:
                rt = f"{I['roach_ft']:g} ({I['roach_table_ft']:g})" if I["roach_ft"] > I["roach_table_ft"] + 0.05 \
                    else f"{I['roach_ft']:g}"
                fh.write(f"| {name(k)} | {I['head_ft']:.1f} | {I['foot_ft']:.1f} | {I['depth_ft']:.1f} | "
                         f"{I['area_ft2']:,.0f} | {len(I['reefs'])} | {I['belly_ft']:.1f} | {rt} | "
                         f"{', '.join(I['roach_clears']) or '-'} |\n")
        fh.write("\nThe main course against the draught, as cut (feet: clews above the load line A, half the foot and "
                 "half the head from the centre line):\n\n| | draught | model |\n| --- | ---: | ---: |\n")
        for k, lab in (("clew_z_ft", "clews above A"), ("half_foot_ft", "half the foot"),
                       ("half_head_ft", "half the head")):
            fh.write(f"| {lab} | {draught_main[k]} | {mc.get(k, '')} |\n")
        fh.write("\nSet, a course's clews are hauled in to the ship's side (feet forward of midships, out from the centre "
                 "line, above A):\n\n")
        for k in ("fore_course", "main_course"):
            if k in res:
                fh.write(f"* {name(k)}: {res[k]['set_clew_ft']}\n")
        fh.write("\nHeadsails, staysails and the spanker, feet (luff, foot, leech; corners as feet forward of midships, "
                 "feet above A):\n\n| Sail | Luff | Foot | Leech | Area sq ft | Tack | Head | Clew |\n"
                 "| --- | ---: | ---: | ---: | ---: | --- | --- | --- |\n")
        for k, I in sv.info.items():
            if I["kind"] in SQUARE:
                continue
            r = res[k]
            hd = r.get("head", r.get("throat"))
            fh.write(f"| {name(k)} | {I['luff_ft']:.1f} | {I['foot_ft']:.1f} | {I['leech_ft']:.1f} | "
                     f"{I['area_ft2']:,.0f} | {r['tack']} | {hd} | {r['clew']} |\n")
        tot = {g: sum(I["area_ft2"] for I in sv.info.values() if (I["kind"] in SQUARE) == (g == "square"))
               for g in ("square", "fore and aft")}
        fh.write(f"\nSail area: {tot['square']:,.0f} sq ft square, {tot['fore and aft']:,.0f} fore and aft, "
                 f"{tot['square'] + tot['fore and aft']:,.0f} in all.\n")
    print(open(os.path.join(out, "sails.md")).read())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
