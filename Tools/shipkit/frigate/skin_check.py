"""The skin's check against the 1927 lines plan (docs/shipkit-2): the side's lines and fittings as skin.py lays them,
drawn back onto the sheer plan, and the planked rail against the half-breadth plan's RAIL line.

    python skin_check.py <lines scan.jpg> <out dir>          (plain Python: numpy, scipy, Pillow)

Writes <out>/skin.md (the numbers), <out>/skin.json, and <out>/overlay_side.jpg with zooms of the stern and the bow
(overlay_side_stern.jpg, overlay_side_bow.jpg). On the overlays:

  red      the gun ports and spar ports as built (their sills and heads are fitted lines, not each port's own reading)
  orange   the main wale's top and bottom (the copper's top), from the midship section's heights
  cyan     the sheer, the plankshear and the rail (the bulwark's top)
  yellow   the channels' top and bottom, the entry steps
  magenta  the rudder's aft edge and foot, its straps
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loft  # noqa: E402
import skin  # noqa: E402

RED, ORANGE, CYAN, YELLOW, MAGENTA = (255, 60, 60), (255, 150, 0), (0, 220, 255), (255, 235, 0), (255, 0, 220)


def main(scan, out):
    os.makedirs(out, exist_ok=True)
    L = loft.Lines()
    specs = json.load(open(os.path.join(HERE, "specs_1795.json")))
    pr = skin.Profile(L, specs)
    reg = L.reg
    view = json.load(open(os.path.join(HERE, "drawing_1927.json")))["views"]["sheer"]
    x0, y0, x1, y1 = view["crop"]
    zoom = 2
    im = Image.open(scan).convert("RGB").crop((x0, y0, x1, y1))
    im = im.resize((im.width * zoom, im.height * zoom), Image.LANCZOS)
    dr = ImageDraw.Draw(im)

    def to_img(xs, zs):
        sx, sy = reg.ship_to_sheer(np.asarray(xs, float), np.asarray(zs, float))
        return [((a - x0) * zoom, (b - y0) * zoom) for a, b in zip(np.ravel(sx), np.ravel(sy))]

    def line(xs, zs, col, w=1):
        dr.line(to_img(xs, zs), fill=col, width=w)

    xa_ship = float(L._x_sf(200.0))
    xf_ship = float(L.x_fwd(240.0))
    X = np.linspace(xa_ship, xf_ship, 600)

    # gun ports and spar ports as built
    for a, b, _, _ in pr.gun:
        xs = np.array([a, b, b, a, a])
        zs = np.array([pr.S(a), pr.S(b), pr.Shd(b), pr.Shd(a), pr.S(a)], float).ravel()
        line(xs, zs, RED, 2)
    for a, b in pr.spar:
        xs = np.array([a, b, b, a, a])
        zs = np.array([pr.Ssp(a), pr.Ssp(b), pr.H(b), pr.H(a), pr.Ssp(a)], float).ravel()
        line(xs, zs, RED, 2)
    # wales, sheer, plankshear, rail
    line(X, pr.Wt(X), ORANGE)
    line(X, pr.Wb(X), ORANGE)
    line(X, pr.H(X), CYAN)
    line(X, pr.P(X), CYAN)
    for lo, hi in ((X[0], pr.x_e0), (pr.x_fc, X[-1])):
        Xr = np.linspace(lo, hi, 200)
        line(Xr, pr.R1(Xr), CYAN, 2)
    # channels (top at the traced heights, never above the spar port sills; 6 in deep) and the entry steps
    th = specs["channels"]["thick_in"] * pr.pxin
    for name, (a, b, _, _) in pr.channels.items():
        Xc = np.linspace(a, b, 40)
        line(Xc, pr.channel_top(name, Xc), YELLOW, 2)
        line(Xc, pr.channel_top(name, Xc) - th, YELLOW, 1)
    sa, sf, z0, z1, n = pr.steps
    for z in np.linspace(z0, z1, n):
        line([sa, sf], [z, z], YELLOW, 1)
    # the rudder: aft edge, foot, straps
    zs = np.linspace(pr.rudder_bottom, 104.0, 40)
    line([pr.rudder_aft(z) for z in zs], zs, MAGENTA, 2)
    post = sorted(L.P["sternpost_aft_face_px"], key=lambda p: p[1])
    xpost = float(np.interp(pr.rudder_bottom, [p[1] for p in post], [p[0] for p in post]))
    line([pr.rudder_aft(pr.rudder_bottom), xpost], [pr.rudder_bottom] * 2, MAGENTA, 2)
    for z, xe, ze in pr.rudder_straps:
        line([pr.rudder_aft(z), xe], [z, ze], MAGENTA, 1)

    im.save(os.path.join(out, "overlay_side.jpg"), quality=88)
    # zooms: the stern (ship x up to 1000) and the bow (from 1900)
    for name, (xa, xb) in (("stern", (300.0, 1000.0)), ("bow", (1850.0, 2420.0))):
        pa = to_img([xa, xb], [-260.0, 300.0])
        box = (int(min(p[0] for p in pa)) - 10, 0, int(max(p[0] for p in pa)) + 10, im.height)
        im.crop(box).save(os.path.join(out, f"overlay_side_{name}.jpg"), quality=88)

    # numbers
    res = {"ports": {"sill_resid_px": np.round(pr.sill_resid, 2).tolist(), "height_resid_px": np.round(pr.high_resid, 2).tolist(),
                     "sill_rms_px": round(float(np.sqrt(np.mean(pr.sill_resid ** 2))), 2),
                     "height_rms_px": round(float(np.sqrt(np.mean(pr.high_resid ** 2))), 2)},
           "rail_trace_resid_px": {"quarterdeck": np.round(pr.rail_resid_qu, 2).tolist(),
                                   "forecastle": np.round(pr.rail_resid_fo, 2).tolist()}}
    mould = skin.Mould(L)
    t0 = specs["strakes"]["bulwark"]["thick_in"] * pr.pxin
    rows = []
    for x, hb in L.d["topsides"]["rail_hb_px"]["pts"]:
        z = float(np.ravel(pr.R1(np.array([x], float)))[0])
        ym = float(mould.hb(np.array([x], float), np.array([z]), np.array([True]))[0])
        rows.append({"x_px": x, "rail_z_px": round(z, 1), "drawing_rail_hb_px": hb, "moulded_hb_px": round(ym, 1),
                     "planked_minus_drawing_px": round(ym + t0 - hb, 1)})
    res["rail_half_breadth"] = rows
    # the channels' tops at their ends: as traced (offsets.json, the fore channel cut at the forecastle) and as built
    ch = []
    for name, (a, b, za, zf) in pr.channels.items():
        built = np.ravel(pr.channel_top(name, np.array([a, b])))
        sill = np.ravel(pr.Ssp(np.array([a, b])))
        ch.append({"channel": name, "x_px": [round(a, 1), round(b, 1)], "traced_z_px": [round(za, 1), round(zf, 1)],
                   "built_z_px": np.round(built, 1).tolist(), "spar_sill_z_px": np.round(sill, 1).tolist()})
    res["channels"] = ch
    json.dump(res, open(os.path.join(out, "skin.json"), "w"), indent=1)
    with open(os.path.join(out, "skin.md"), "w") as f:
        f.write("# Skin check against the 1927 lines plan\n\n")
        f.write(f"Gun ports: the sill line is faired through the ports' sills, {res['ports']['sill_rms_px']} px RMS from "
                f"each port's own reading; their height is a straight line along the ship, {res['ports']['height_rms_px']} px "
                f"RMS (1 px is about an inch).\n\n")
        f.write("Rail line (the bulwark's top) on the quarterdeck and forecastle: a gentle curve through the traced points, "
                f"within {max(np.abs(pr.rail_resid_qu).max(), np.abs(pr.rail_resid_fo).max()):.1f} px of every one.\n\n")
        f.write("The planked side at the rail against the half-breadth plan's RAIL line (px, + is outboard of the line; "
                "the bulwark's planking is 4 in, 3.9 px):\n\n")
        f.write("| x (px) | rail z (px) | drawing RAIL | moulded side | planked minus drawing |\n| --- | --- | --- | --- | --- |\n")
        for r in rows:
            f.write(f"| {r['x_px']:.0f} | {r['rail_z_px']} | {r['drawing_rail_hb_px']} | {r['moulded_hb_px']} | "
                    f"{r['planked_minus_drawing_px']:+.1f} |\n")
        f.write("\nThe channels' tops at their aft and fore ends (z px above A): as traced on the sheer plan, as built, and "
                "the spar port sill line there. A channel follows the sill line moved to the traced heights, but never "
                "above the sills. The fore channel starts at the forecastle's break (the open waist has no side there).\n\n")
        f.write("| channel | x aft, fore (px) | traced | built | spar port sills |\n| --- | --- | --- | --- | --- |\n")
        for c in ch:
            f.write(f"| {c['channel']} | {c['x_px'][0]}, {c['x_px'][1]} | {c['traced_z_px'][0]}, {c['traced_z_px'][1]} | "
                    f"{c['built_z_px'][0]}, {c['built_z_px'][1]} | {c['spar_sill_z_px'][0]}, {c['spar_sill_z_px'][1]} |\n")
    print(open(os.path.join(out, "skin.md")).read())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
