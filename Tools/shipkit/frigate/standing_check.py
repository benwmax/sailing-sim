"""The standing rigging's check against the 1817 sail plan (docs/shipkit-4): the rigging as rigging.py builds it, drawn
back onto 'A Draft of the U.S. Frigate Constitution' (NARA 102278445), and tables of where the deadeyes and hearts are
against where the draught has them.

    python standing_check.py <1817 draught scan.jpg> <out dir>          (plain Python: numpy, scipy, Pillow)

Writes <out>/rigging.md (the numbers), <out>/standing_check.json and <out>/overlay_standing.jpg, with zooms of each
mast's channel (overlay_channels_<mast>.jpg), its heads (overlay_heads_<mast>.jpg) and the bow (overlay_bow.jpg). The
model is drawn in profile, its starboard side only. On the overlays:

  cyan     lower shrouds, topmast shrouds and topgallant shrouds (their free runs)
  yellow   topmast, topgallant and royal backstays
  magenta  stays, the bowsprit's shrouds, martingales and guys
  red      the model's deadeyes and hearts (rings), and its deadeyes' places on the channel (ticks)
  green    the draught's deadeyes on the channel (ticks) and stays' hearts (crosses), as read for standing_1797.json
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
import skin  # noqa: E402
import spars  # noqa: E402

FT = loft.FT
IN = FT / 12
CYAN, YELLOW, RED, MAGENTA, GREEN = (0, 200, 255), (255, 220, 0), (255, 40, 40), (255, 0, 220), (0, 220, 60)
Image.MAX_IMAGE_PIXELS = None


def main(scan, out):
    os.makedirs(out, exist_ok=True)
    L = loft.Lines()
    rig = spars.Rig(L, json.load(open(os.path.join(HERE, "specs_1795.json")))).build()
    SK = skin.Skin(L, stem_bed=rig.stem_bed).build()
    st = rigging.Standing(rig, SK).build()
    reg = rig.sp["registration"]
    sp = st.sp

    def to_d(x_m, z_m):
        """Ship metres (x forward of midships, z above A) to the draught's pixels."""
        xpx = L.mid_px + np.asarray(x_m, float) / FT * L.ppf
        xd = reg["x_scale"] * xpx + reg["x_offset"]
        yd = reg["y0"] + reg["y_tilt"] * xd - reg["px_per_ft"] * np.asarray(z_m, float) / FT
        return xd, yd

    def d_ft(xd):
        return ((xd - reg["x_offset"]) / reg["x_scale"] - L.mid_px) / L.ppf

    im = Image.open(scan).convert("RGB")
    dr = ImageDraw.Draw(im)

    def line(P, col, w=2):
        xd, yd = to_d(np.asarray(P)[:, 0], np.asarray(P)[:, 2])
        dr.line(list(zip(xd.tolist(), yd.tolist())), fill=col, width=w)

    def ring(P, d_m, col, w=2):
        xd, yd = to_d(P[0], P[2])
        rp = max(3.0, d_m / 2 / FT * reg["px_per_ft"])
        dr.ellipse([xd - rp, yd - rp, xd + rp, yd + rp], outline=col, width=w)

    def tick(x_m, z_m, col, up=True):
        xd, yd = to_d(x_m, z_m)
        dr.line([(xd, yd), (xd, yd + (-14 if up else 14))], fill=col, width=3)

    # the free runs, starboard side (y >= 0) and the stays on the centreline
    for name, a, b, r in st.spans:
        if min(a[1], b[1]) < -0.05 and "stay" not in name:
            continue
        if "stay" in name and min(a[1], b[1]) < -0.05 and "preventer" not in name and not name.startswith("main"):
            continue
        if "backstay" in name:
            col = YELLOW
        elif "shroud" in name and "bowsprit" not in name:
            col = CYAN
        else:
            col = MAGENTA
        line(np.array([a, b]), col, 2)
    # deadeyes: the model's upper deadeyes on the lower shrouds; the channel places against the draught's
    rows = []
    for mast in ("fore", "main", "mizzen"):
        places = st.channel_places(mast)
        D = sp["deadeyes"]["lower"][rigging.MI[mast]] * IN
        for ln in st.shroud_lines[(mast, "lower", 1)]:
            ring(ln[3], D, RED)
        n = sp["masts"][mast]["shrouds"]
        nb = sp["masts"][mast]["topmast_backstays"]
        xd_s = sp["masts"][mast]["shroud_x_draught"]
        xd_b = sp["masts"][mast]["backstay_x_draught"]
        for key, xd in [(f"topmast_backstay_{k}", xd_b[k]) for k in range(nb)] + \
                       [(f"shroud_{k}", xd_s[k]) for k in range(n)]:
            xm = places[key]
            z_top = float(st.channel_edge(mast, xm)[0][2])
            tick(xm * FT, z_top, RED, up=True)
            tick(d_ft(xd) * FT, z_top, GREEN, up=False)
            rows.append({"mast": mast, "deadeye": key.replace("_", " "), "draught_ft": round(float(d_ft(xd)), 2),
                         "model_ft": round(float(xm), 2), "moved_in": round(float((xm - d_ft(xd)) * 12), 1)})
        for key in ("topgallant_backstay", "royal_backstay"):
            rows.append({"mast": mast, "deadeye": key.replace("_", " ") + " (thimble)", "draught_ft": None,
                         "model_ft": round(float(places[key]), 2), "moved_in": None})
    # the stays' hearts against the draught's
    hearts = []
    for nm, (cu, cl) in st.report.get("heart_at", {}).items():
        Lh = sp["hearts_in"]["preventer_stay" if nm.endswith("preventer") else "stay"][rigging.MI[nm.split("_")[0]]] * IN
        ring(cu, Lh, RED)
        ring(cl, Lh, RED)
        spec = sp["stays"][nm]
        row = {"stay": nm.replace("_", " "), "upper_model_ft": np.round(np.array([cu[0], cu[2]]) / FT, 1).tolist(),
               "lower_model_ft": np.round(np.array([cl[0], cl[2]]) / FT, 1).tolist()}
        for k, lab in (("heart_up_draught", "upper_draught_ft"), ("heart_low_draught", "lower_draught_ft"),
                       ("heart_draught", "lower_draught_ft")):
            if k in spec:
                xd, yd = spec[k]
                dr.line([(xd - 10, yd - 10), (xd + 10, yd + 10)], fill=GREEN, width=3)
                dr.line([(xd - 10, yd + 10), (xd + 10, yd - 10)], fill=GREEN, width=3)
                z = (reg["y0"] + reg["y_tilt"] * xd - yd) / reg["px_per_ft"]
                row[lab] = [round(float(d_ft(xd)), 1), round(float(z), 1)]
        hearts.append(row)

    xs = {n: float(to_d(m["O"][0], 0.0)[0]) for n, m in rig.masts.items()}
    for n, xc in xs.items():
        chan = [p for k, p in st.channel_places(n).items()]
        x0, x1 = float(to_d(min(chan) * FT - 4 * FT, 0)[0]), float(to_d(max(chan) * FT + 4 * FT, 0)[0])
        y_c = float(to_d(rig.masts[n]["O"][0], 15 * FT)[1])
        im.crop((int(x0), int(y_c - 260), int(x1), int(y_c + 120))).save(
            os.path.join(out, f"overlay_channels_{n}.jpg"), quality=82)
        im.crop((int(xc - 300), 60, int(xc + 300), 1450)).save(os.path.join(out, f"overlay_heads_{n}.jpg"), quality=80)
    im.crop((2550, 1350, 3800, 2200)).save(os.path.join(out, "overlay_bow.jpg"), quality=82)
    im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS).save(
        os.path.join(out, "overlay_standing.jpg"), quality=80)

    summ = st.summary()
    res = {"deadeyes": rows, "hearts": hearts, "notes": summ["notes"], "objects": summ["objects"],
           "triangles": int(sum(summ["objects"].values())), "deadeye_count": summ["deadeyes"],
           "heart_count": summ["hearts"], "main_stays_heart_y_ft": summ.get("main_stays_heart_y_ft")}
    json.dump(res, open(os.path.join(out, "standing_check.json"), "w"), indent=1)
    with open(os.path.join(out, "rigging.md"), "w") as fh:
        fh.write("# Standing rigging against the 1817 draught\n\n")
        fh.write("Deadeyes on the channels, feet forward of midships: the draught's (read on the 3840 px copy and "
                 "carried to the ship through the slice 3 registration) and the model's, placed by rigging.py as near "
                 "the draught's as it can with 2 1/2 in between neighbours, no deadeye in front of a spar deck port "
                 "and as little of a lanyard as may be crossing a port's edge (the model's ports are the 1927 plan's; "
                 "the notes below list the lanyards that still cross one). The topgallant and royal backstays are set "
                 "up with thimbles to eyebolts, abaft the topmast backstays: the draught has no deadeyes for them.\n\n")
        fh.write("| mast | deadeye | draught ft | model ft | moved in |\n| --- | --- | --- | --- | --- |\n")
        for r in rows:
            mv = "" if r["moved_in"] is None else f"{r['moved_in']:+.1f}"
            dd = "" if r["draught_ft"] is None else r["draught_ft"]
            fh.write(f"| {r['mast']} | {r['deadeye']} | {dd} | {r['model_ft']} | {mv} |\n")
        fh.write("\nStays' hearts, (feet forward of midships, feet above A):\n\n| stay | upper, draught | upper, model "
                 "| lower, draught | lower, model |\n| --- | --- | --- | --- | --- |\n")
        for h in hearts:
            fh.write(f"| {h['stay']} | {h.get('upper_draught_ft', '')} | {h['upper_model_ft']} | "
                     f"{h.get('lower_draught_ft', '')} | {h['lower_model_ft']} |\n")
        fh.write("\nWhere the rigging had to give way (rigging.py's report):\n\n")
        for n_ in summ["notes"]:
            fh.write(f"* {n_}\n")
        fh.write(f"\n{summ['deadeyes']} deadeyes, {summ['hearts']} hearts, {res['triangles']:,} triangles.\n")
    print(open(os.path.join(out, "rigging.md")).read())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
