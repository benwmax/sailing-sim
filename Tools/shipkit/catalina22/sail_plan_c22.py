"""The Catalina 22's sails over the physics' sail plan (docs/c22-6): the physics' planforms, read from Fleet.cpp's
Catalina22() (SetMain and SetSail: foot and head heights, chords and luff positions), drawn as outlines over
render_sails_c22.py's orthographic profiles.

    python3 -I sail_plan_c22.py <sail views dir> <out.jpg> [--repo <repo root>]

Each profile is orthographic from port, 10.5 m square, centred on (0.5, 4.6) (render_sails_c22.py's up_profile,
reef_profile and run_profile), so a point's pixel follows from its x and z alone. The physics' strips are flat
trapezoids in the centreline plane; the drawn sails are cut to slice 4's rig, so their difference is the point.
"""
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

ARGS = sys.argv[1:]
if len(ARGS) < 2:
    sys.exit(__doc__)
VIEWS, OUT = ARGS[0], ARGS[1]
REPO = ARGS[ARGS.index("--repo") + 1] if "--repo" in ARGS else os.path.join(os.path.dirname(__file__), "..", "..", "..")
CX, CZ, SPAN = 0.5, 4.6, 10.5                      # the profiles' centre and width (render_sails_c22.py)


def physics():
    """{'main': (foot_z, head_z, foot_chord, head_chord, luff_x_foot, luff_x_head), 'genoa': ..., 'spinnaker': ...}"""
    src = open(os.path.join(REPO, "Source/SailingPhysics/Private/Fleet.cpp")).read()
    i = src.index("Catalina22()")
    block = src[i:i + 6000]
    num = r"(-?[0-9.]+)"
    m = re.search(r"SetMain\(C, " + ", ".join([num] * 8), block)
    j = re.search(r"SetSail\(C\.Jib, " + ", ".join([num] * 6), block)
    s = re.search(r"SetSail\(C\.Spinnaker, " + ", ".join([num] * 6), block)
    mf = [float(v) for v in m.groups()]
    out = {"main": (mf[0], mf[1], mf[2], mf[3], mf[5], mf[6])}
    for key, g in (("genoa", j), ("spinnaker", s)):
        v = [float(x) for x in g.groups()]
        out[key] = (v[0], v[1], v[2], v[3], v[4], v[5])
    return out


def outline(p):
    """The planform's corners: luff foot, luff head, leech head, leech foot (x, z); chords run aft of the luff."""
    fz, hz, fc, hc, lxf, lxh = p
    return [(lxf, fz), (lxh, hz), (lxh - hc, hz), (lxf - fc, fz)]


def to_px(x, z, w):
    return (w * (0.5 + (CX - x) / SPAN), w * (0.5 - (z - CZ) / SPAN))   # from port: forward is to the left


def main():
    P = physics()
    panels = [("up_profile", ("main", "genoa"), "main and genoa"),
              ("reef_profile", ("main",), "reefed main and jib (red: the full main)"),
              ("run_profile", ("main", "spinnaker"), "main and spinnaker")]
    ims = []
    for view, sails, label in panels:
        im = Image.open(os.path.join(VIEWS, view + ".png")).convert("RGB")
        w = im.width
        d = ImageDraw.Draw(im)
        for sname in sails:
            pts = [to_px(x, z, w) for x, z in outline(P[sname])]
            d.line(pts + [pts[0]], fill=(200, 30, 30), width=max(2, w // 400))
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", w // 40)
        except OSError:
            font = ImageFont.load_default()
        text = label if "red:" in label else label + ": drawn (grey), physics (red)"
        d.text((w // 40, w // 40), text, fill=(20, 20, 20), font=font)
        ims.append(im)
    W = sum(i.width for i in ims)
    sheet = Image.new("RGB", (W, ims[0].height), "white")
    x = 0
    for i in ims:
        sheet.paste(i, (x, 0))
        x += i.width
    sheet = sheet.resize((1800, ims[0].height * 1800 // W))
    sheet.save(OUT, quality=82)
    for k, v in P.items():
        print(k, "foot z %.2f head z %.2f foot chord %.2f head chord %.2f luff x %.2f to %.2f" % v)
    print("written", OUT)


if __name__ == "__main__":
    main()
