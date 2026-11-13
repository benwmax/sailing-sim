"""The masts and yards' check against the 1817 sail plan (docs/shipkit-3): the rig as spars.py builds it, drawn back
onto 'A Draft of the U.S. Frigate Constitution' (NARA 102278445), and a table of heights against the draught's.

    python rig_check.py <1817 draught scan.jpg> <out dir>          (plain Python: numpy, scipy, Pillow)

Writes <out>/rig.md (the numbers), <out>/rig.json and <out>/overlay_rig.jpg with zooms of each mast's heads
(overlay_rig_<mast>.jpg) and of the bowsprit. The draught draws its yards squared across the sheet at full length, so
the overlay does too (centred on their masts). On the overlays:

  cyan     the masts' outlines (lower masts, topmasts, topgallant masts and royal poles), the bowsprit and jibbooms
  yellow   the tops (their fore-and-aft length), the caps and the crosstrees
  red      the yards, hoisted, at full length
  magenta  the spanker boom and gaff
  green    the draught's own heights read for the table (crosses)
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loft  # noqa: E402
import spars  # noqa: E402

FT = loft.FT
CYAN, YELLOW, RED, MAGENTA, GREEN = (0, 200, 255), (255, 220, 0), (255, 40, 40), (255, 0, 220), (0, 220, 60)
Image.MAX_IMAGE_PIXELS = None


def main(scan, out):
    os.makedirs(out, exist_ok=True)
    L = loft.Lines()
    rig = spars.Rig(L, json.load(open(os.path.join(HERE, "specs_1795.json")))).build()
    sp = rig.sp
    reg = sp["registration"]

    def to_d(x_m, z_m):
        """Ship metres (x forward of midships, z above A) to the draught's pixels."""
        xpx = L.mid_px + np.asarray(x_m, float) / FT * L.ppf
        xd = reg["x_scale"] * xpx + reg["x_offset"]
        yd = reg["y0"] + reg["y_tilt"] * xd - reg["px_per_ft"] * np.asarray(z_m, float) / FT
        return xd, yd

    def z_of(xd, yd):
        return (reg["y0"] + reg["y_tilt"] * xd - yd) / reg["px_per_ft"]

    im = Image.open(scan).convert("RGB")
    dr = ImageDraw.Draw(im)

    def line(P, col, w=2):
        xd, yd = to_d(P[:, 0], P[:, 2])
        dr.line(list(zip(xd.tolist(), yd.tolist())), fill=col, width=w)

    def spar_outline(o, u, f, s0, s1, R, col, n=30):
        ss = np.linspace(s0, s1, n)
        for sgn in (1, -1):
            P = np.array([o + s * u + sgn * R(s) * f for s in ss])
            line(P, col, 2)

    for name, m in rig.masts.items():
        u, f = m["u"], m["f"]
        spar_outline(m["O"], u, f, m["s_gun"], m["s_h"], m["R_lower"], CYAN)
        spar_outline(m["Otm"], u, f, m["s_cap1"], m["s_tmh"], m["R_tm"], CYAN)
        spar_outline(m["Otg"], u, f, m["s_tmcap1"], m["s_pole"], m["R_tg"], CYAN)
        # the top's fore-and-aft length, the caps
        line(np.array([m["O"] + m["s_plat"] * u + m["fa"] * f, m["O"] + m["s_plat"] * u + m["ff"] * f]), YELLOW, 3)
        for o, s in ((m["O"], m["s_cap1"]), (m["Otm"], m["s_tmcap1"])):
            line(np.array([o + s * u - 0.6 * f, o + s * u + 0.9 * f]), YELLOW, 3)
        line(np.array([m["Otm"] + m["s_tmh"] * u - 1.0 * f, m["Otm"] + m["s_tmh"] * u + 1.6 * f]), YELLOW, 2)
    # yards squared across the sheet at full length, centred on their mast
    for pname, meta in rig.meta.items():
        if not pname.startswith("Yard_") or pname == "Yard_Spritsail":
            continue
        o = np.array(meta["origin_m"])
        half = meta["length_ft"] * FT / 2
        line(np.array([o + [-half, 0, 0], o + [half, 0, 0]]), RED, 3)
    # spanker boom and gaff in profile
    for pname in ("SpankerBoom", "SpankerGaff"):
        o, Rm = rig.parts_[pname]["frame"]
        V = rig.parts_[pname]["mesh"].arrays()[0]
        W = V @ Rm.T + o
        xs = W[:, 0]
        a, b = W[np.argmax(xs)], W[np.argmin(xs)]
        line(np.array([a, b]), MAGENTA, 3)
    # bowsprit, jibboom, flying jibboom
    b = rig.bs
    for s0, s1 in ((0.0, b["Lb"]),):
        spar_outline(b["H"], b["ub"], b["up"], s0, s1, b["R"], CYAN)
    line(np.array([b["cap"], b["jib_end"]]), CYAN, 3)
    line(np.array([b["jib_end"], b["fjb_end"]]), CYAN, 2)

    # the draught's heights
    rows = []
    summ = rig.summary()
    names = {"top": "top", "lower_cap": "lower_cap", "topmast_crosstrees": "topmast_crosstrees",
             "topmast_cap": "topmast_cap", "truck": "truck"}
    yard_of = {"lower_yard": "", "topsail_yard": "Topsail", "topgallant_yard": "Topgallant", "royal_yard": "Royal"}
    for mast, pts in sp["draught_heights"].items():
        if mast == "note":
            continue
        for key, (xd, yd) in pts.items():
            zd = z_of(xd, yd)
            dr.line([(xd - 12, yd - 12), (xd + 12, yd + 12)], fill=GREEN, width=3)
            dr.line([(xd - 12, yd + 12), (xd + 12, yd - 12)], fill=GREEN, width=3)
            if key in names:
                zm = summ[mast][names[key]]
            else:
                yname = ("Yard_" + mast.capitalize() + yard_of[key]) if not (mast == "mizzen" and key == "lower_yard") \
                    else "Yard_Crossjack"
                zm = rig.meta[yname]["z_ft"]
            what = key.replace("_", " ") + (" (the draught's: a skysail pole's)" if key == "truck" else "")
            rows.append({"mast": mast, "what": what, "draught_ft": round(float(zd), 1),
                         "model_ft": round(float(zm), 1), "model_minus_draught_ft": round(float(zm - zd), 1)})
    cap_d = sp["bowsprit"]["cap_draught_px"]
    cap_m = b["cap"] / FT
    xd_m, yd_m = to_d(b["cap"][0], b["cap"][2])
    bow = {"cap_draught": [round(cap_d[0], 1), round(cap_d[1], 1)], "cap_model": [round(float(xd_m), 1), round(float(yd_m), 1)],
           "cap_model_ft": np.round(cap_m, 1).tolist(),
           "cap_draught_ft": [round(float(((cap_d[0] - reg["x_offset"]) / reg["x_scale"] - L.mid_px) / L.ppf), 1),
                              round(float(z_of(*cap_d)), 1)]}
    im.save(os.path.join(out, "overlay_rig_full.jpg"), quality=85)
    # zooms: each mast's heads, the bowsprit; and the whole sheet small
    xs = {n: float(to_d(m["O"][0], 0.0)[0]) for n, m in rig.masts.items()}
    for n, xc in xs.items():
        im.crop((int(xc - 260), 60, int(xc + 260), 1750)).save(os.path.join(out, f"overlay_rig_{n}.jpg"), quality=82)
    im.crop((2550, 1450, 3800, 2150)).save(os.path.join(out, "overlay_rig_bowsprit.jpg"), quality=82)
    sm = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
    sm.save(os.path.join(out, "overlay_rig.jpg"), quality=80)
    os.remove(os.path.join(out, "overlay_rig_full.jpg"))

    res = {"heights": rows, "bowsprit": bow, "summary": {k: v for k, v in summ.items() if k != "yards"},
           "yards": {k: {kk: v[kk] for kk in ("length_ft", "diam_in", "z_ft", "hoist_m", "brace_deg")} for k, v in
                     summ["yards"].items()}}
    json.dump(res, open(os.path.join(out, "rig.json"), "w"), indent=1)
    with open(os.path.join(out, "rig.md"), "w") as fh:
        fh.write("# Masts and yards against the 1817 draught\n\n")
        fh.write("Heights in feet above the load line (waterline A). The draught's are read at 10.31 px/ft both ways "
                 "(its deadeyes are round) from its load line; its hull is drawn about 16% deeper than the 1927 lines, "
                 "so its rig's feet carry that much doubt near the hull. The draught is 1817, twenty years on: her rig "
                 "had been changed.\n\n")
        fh.write("| mast | what | draught | model | model - draught |\n| --- | --- | --- | --- | --- |\n")
        for r in rows:
            fh.write(f"| {r['mast']} | {r['what']} | {r['draught_ft']} | {r['model_ft']} | {r['model_minus_draught_ft']:+.1f} |\n")
        fh.write(f"\nBowsprit cap: draught ({bow['cap_draught_ft'][0]}, {bow['cap_draught_ft'][1]}) ft (forward of "
                 f"midships, up), model ({bow['cap_model_ft'][0]}, {bow['cap_model_ft'][2]}) ft.\n\n")
        fh.write("Each mast's points (ft above A):\n\n| mast | step | spar deck | hounds | top | lower cap | topmast "
                 "crosstrees | topmast cap | topgallant stop | truck |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
        for n in ("fore", "main", "mizzen"):
            s = summ[n]
            fh.write(f"| {n} | " + " | ".join(str(s[k]) for k in ("step", "spar_deck", "hounds", "top", "lower_cap",
                                                                  "topmast_crosstrees", "topmast_cap", "topgallant_stop",
                                                                  "truck")) + " |\n")
        fh.write("\nYards (hoisted; hoist is how far each one lowers, m; brace limits in degrees):\n\n| part | length ft | "
                 "diameter in | height ft | lowers m | braces |\n| --- | --- | --- | --- | --- | --- |\n")
        for k, v in summ["yards"].items():
            fh.write(f"| {k} | {v['length_ft']} | {v['diam_in']} | {v['z_ft']} | {abs(v['hoist_m'][0]):.2f} | "
                     f"{v['brace_deg'][0]:+.0f} to {v['brace_deg'][1]:+.0f} |\n")
    print(open(os.path.join(out, "rig.md")).read())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
