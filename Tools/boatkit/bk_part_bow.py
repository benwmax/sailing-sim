"""Bow fittings (part detail loop, Nov 2026: docs/part-detail-loop/bow.md).

- Stemhead: the J/22's forestay chainplate as Bean's photo of TX 7295 EC shows it (open bow, no pulpit or roller): a
  stainless bar set edge-on along the stem, through-bolted side to side, its top a tang above the deck for the forestay's
  toggle. Replaces the kit's October Stemhead (a flat deck plate, a sail-shaped tang and two pins).
- TackEye: the jib's tack fitting a few centimetres aft of it, a U-bail on a plate (new).
- BowEye: the stainless U-bolt bow eye on the stem for the trailer winch: 3/8 in rod, 1 7/16 in between the legs, the eye
  about 37 mm proud, on an oval stainless plate (catalogue sizes). Replaces the kit's October BowEye (rod and plate
  about two thirds size, the loop a thin half circle).
- BowHandle: the Sunfish's cast aluminium bow handle on the foredeck's centreline, its grip arched over two oval feet,
  one oval-head screw in each (the class part, Zim 48102; sizes are GUESSES from class photos). New: the Sunfish had a
  six-sided bent tube drawn by build_fleet.py.

They live in their own file so threads working on other parts don't touch the same lines: bk_parts imports every
bk_part_*.py at its end, and the @part below replaces bk_parts' older parts of the same name.
Conventions follow bk_parts: origin on the mounting face, +Z out of it, +X forward along the part, metres.
"""
import math

from mathutils import Matrix, Vector

import bk_geom as G
import bk_parts as P

# ---------------------------------------------------------------------------------------------------------- Stemhead
# Bean's photo of TX 7295 EC's bow on its lift (IMG_9224, Oct 4 2026): the forestay's chainplate is a stainless flat bar
# set edge-on along the stem's leading edge, through-bolted side to side, its top standing up past the deck as the tang
# the forestay's toggle pins through; the jib tacks to a separate U-bail on a plate a few centimetres aft (TackEye). The
# sizes are GUESSES read off that photo against the toggle (no J/22 drawing is public): a 6 mm bar (the turnbuckle's
# toggle cheeks straddle 6.4 mm) 30 mm deep standing 10 mm proud of the stem, a 10.5 mm hole for the 3/8 in pin (Rigrite's
# J/22 stemhead) 34 mm above the deck edge, bolts every 65 mm.
_BT = 0.006                             # bar thickness, across the boat
_BD = 0.030                             # bar depth, fore and aft (into the stem)
_PROUD_S = 0.010                        # how far the bar stands out of the stem's edge
_PIN = (-0.012, 0.034, 0.00525)         # forestay hole: x, z (from the deck edge at the stem), radius
_RAKE = 70.0                            # default stem: a straight edge this many degrees below the deck line, 0.32 m long
_PITCH = 0.065                          # through-bolt spacing down the stem


def _hull2d(pts):
    """Convex hull (x, y), counter-clockwise."""
    pts = sorted(set((round(x, 7), round(y, 7)) for x, y in pts))
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and (lo[-1][0] - lo[-2][0]) * (p[1] - lo[-2][1]) - (lo[-1][1] - lo[-2][1]) * (p[0] - lo[-2][0]) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and (hi[-1][0] - hi[-2][0]) * (p[1] - hi[-2][1]) - (hi[-1][1] - hi[-2][1]) * (p[0] - hi[-2][0]) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def _circle(c, r, n=24):
    return [(c[0] + r * math.cos(2 * math.pi * i / n), c[1] + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def _resample(stem, step=0.006):
    """The stem's leading edge (x, z) from the deck edge down, every `step` metres, and each point's outward normal."""
    pts = [Vector((x, z)) for x, z in stem]
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int((b - a).length / step))
        out += [a.lerp(b, k / n) for k in range(1, n + 1)]
    norms = []
    for i in range(len(out)):
        t = (out[min(i + 1, len(out) - 1)] - out[max(i - 1, 0)]).normalized()     # down the stem
        norms.append(Vector((-t.y, t.x)) if (-t.y) > 0 else Vector((t.y, -t.x)))   # the side facing forward
    return out, norms


def _stemhead_parts(stem):
    ss = P.M("Stainless")
    pts, norms = _resample(stem)
    front = [p + n * _PROUD_S for p, n in zip(pts, norms)]
    back = [p - n * (_BD - _PROUD_S) for p, n in zip(pts, norms)]
    bar = G.prism("bar", [tuple(p) for p in front + list(reversed(back))], -_BT / 2, _BT / 2, ss)
    # the tang: a lobe round the pin hole standing up out of the bar's top, its front edge leaning with the forestay
    px, pz, pr = _PIN
    lobe = _hull2d(_circle((px, pz), pr * 2.45, 32) + [tuple(front[0]), tuple(back[0]), tuple(front[2]), tuple(back[2])])
    tang = G.prism("tang", lobe, -_BT / 2, _BT / 2, ss)
    G.boolean(bar, tang, "UNION")
    bar.matrix_world = Matrix.Rotation(math.radians(90), 4, "X")      # outline (x, y) -> (x, z); thickness along Y
    G.bake_xform(bar)
    G.boolean(bar, G.cyl("hole", (px, -0.02, pz), (px, 0.02, pz), pr, None, 32))
    G.finish(bar, 0.0012, segs=2)
    bar.name = "chainplate"
    # through-bolts side to side: a dome head on one side, an acorn nut on the other, along the bar's middle
    bolts = []
    s, k = 0.0, 0
    length = sum((b - a).length for a, b in zip(pts, pts[1:]))
    d = 0.022
    while d < length - 0.02:
        acc = 0.0
        for a, b, na in zip(pts, pts[1:], norms):
            seg = (b - a).length
            if acc + seg >= d:
                c = a.lerp(b, (d - acc) / seg) - na * 0.004
                break
            acc += seg
        for sgn in (-1, 1):
            prof = [(0, 0), (0.0046, 0), (0.0044, 0.0010), (0.0030, 0.0022), (0, 0.0026)] if sgn < 0 else \
                   [(0, 0), (0.0040, 0), (0.0040, 0.0030), (0.0032, 0.0042), (0.0018, 0.0050), (0, 0.0052)]
            h = G.lathe(f"bolt{k}_{'head' if sgn < 0 else 'nut'}", prof, ss, 16)
            h.matrix_world = G.along((c.x, sgn * _BT / 2, c.y), (0, sgn, 0))
            G.bake_xform(h)
            G.finish(h, 0.0, weighted=False)
            bolts.append(h)
        k += 1
        d += _PITCH
    lo = pts[-1]
    socks = [("Forestay", (px, 0, pz)), ("Base", (0, 0, 0)), ("StemFoot", (lo.x, 0, lo.y))]
    return [bar] + bolts, socks


def _stem_line(rake, length=0.32):
    a = math.radians(rake)
    return [(0.0, 0.0), (-length * math.cos(a), -length * math.sin(a))]


@P.part("Stemhead", "rig", "Forestay chainplate: a stainless bar edge-on down the stem, through-bolted, its top a tang above the deck for the forestay toggle")
def stemhead(stem=None, rake=_RAKE):
    """stem: the stem's leading edge as (x, z) points from the deck edge (0, 0) downward, in the part's frame (the hero
    passes its own); otherwise a straight edge `rake` degrees below the deck line."""
    return P.done("Stemhead", *_stemhead_parts(stem or _stem_line(rake)))


# ----------------------------------------------------------------------------------------------------------- TackEye
# The jib's tack fitting on the J/22's foredeck just aft of the stem (Bean's photo IMG_9224): a stainless U-bail standing
# fore and aft on a rounded rectangular plate, four screws. GUESSES off the photo: plate 66 x 28 x 4 mm, 8 mm rod, legs
# 30 mm apart on centres, 30 mm high.
def _tack_eye_parts():
    ss = P.M("Stainless")
    plate = G.prism("plate", G.rrect(0.066, 0.028, 0.007, 8), 0.0, 0.004, ss, taper=0.95)
    G.finish(plate, 0.0010, segs=2)
    r, a = 0.004, 0.015
    zc = 0.030 - a - r
    path = [(-a, 0, 0.002), (-a, 0, zc * 0.5), (-a, 0, zc)] + G.arc_pts((0, 0, zc), a, math.pi, 0, 24, "xz")[1:-1] + [(a, 0, zc), (a, 0, zc * 0.5), (a, 0, 0.002)]
    bail = G.tube("bail", path, r, ss, 20)
    G.finish(bail, 0.0)
    collars = []
    for sgn in (-1, 1):
        c = G.lathe(f"collar{sgn}", [(0, 0.003), (r * 1.7, 0.003), (r * 1.4, 0.0055), (r, 0.0068), (0, 0.0068)], ss, 20)
        c.location = (sgn * a, 0, 0)
        G.bake_xform(c)
        collars.append(G.finish(c, 0.0))
    screws = G.screw_heads("screw", [(sx * 0.0255, sy * 0.0085, 0.0038) for sx in (-1, 1) for sy in (-1, 1)], ss, 0.0030, 0.0012)
    return [plate, bail] + collars + screws, [("Eye", (0, 0, 0.030 - r)), ("Base", (0, 0, 0))]


@P.part("TackEye", "fastener", "Jib tack fitting: a stainless U-bail standing fore and aft on a 66 x 28 mm plate, four screws")
def tack_eye():
    return P.done("TackEye", *_tack_eye_parts())


# ------------------------------------------------------------------------------------------------------------ BowEye
# Catalogue (Hardin Marine 3/8 x 2 1/2 in U-bolt bow eye): rod 3/8 in (9.5 mm), legs 1 7/16 in (36.5 mm) apart on centres,
# 1 1/16 in (27 mm) inside between them; overall 3 15/16 in with 2 1/2 in of thread, so the eye stands about 1 7/16 in
# (37 mm) proud. The plate: an oval stainless washer plate (GUESS 64 x 24 x 3 mm, rounded edges).
_ROD = 0.0095
_LEGS = 0.0365
_PROUD = 0.037


def _bow_eye_parts():
    ss = P.M("Stainless")
    r = _ROD / 2
    a = _LEGS / 2
    plate = G.prism("plate", G.rrect(0.024, 0.064, 0.0119, 10), 0.0, 0.003, ss, taper=0.93)
    G.finish(plate, 0.0009, segs=2)
    # the U: legs out of the plate along Y (in the hull's plane), a half round on top (outer height = _PROUD)
    zc = _PROUD - a - r
    path = [(0, -a, 0.0015), (0, -a, zc * 0.5), (0, -a, zc)] + G.arc_pts((0, 0, zc), a, math.pi, 0, 28, "yz")[1:-1] + [(0, a, zc), (0, a, zc * 0.5), (0, a, 0.0015)]
    loop = G.tube("loop", path, r, ss, 24)
    G.finish(loop, 0.0)
    # rounded collars where the legs meet the plate (the bolt's shoulder)
    collars = [G.finish(G.lathe(f"collar{s}", [(0, 0.0025), (r * 1.55, 0.0025), (r * 1.35, 0.0055), (r, 0.0070), (0, 0.0070)], ss, 24), 0.0) for s in (-1, 1)]
    for s, c in zip((-1, 1), collars):
        c.location = (0, s * a, 0)
        G.bake_xform(c)
    return [plate, loop] + collars, [("Eye", (0, 0, _PROUD - r)), ("Base", (0, 0, 0))]


@P.part("BowEye", "hull", "Stainless U-bolt bow eye, 3/8 in rod, legs 36.5 mm apart, 37 mm proud of an oval plate; for the trailer winch")
def bow_eye():
    return P.done("BowEye", *_bow_eye_parts())


# --------------------------------------------------------------------------------------------------------- BowHandle
# The Sunfish's bow handle (class part, ISCA approved; Zim 48102): a cast aluminium grip arched over two oval feet on the
# foredeck's centreline, one #8 oval-head screw in each foot. GUESSES from class photos (no drawing is public): 150 mm
# long overall, feet 112 mm apart on centres, 32 mm high (low, as the class photos show it), a flattened oval bar 18 wide x 12 mm deep
# flaring into the feet.
_BH_L = 0.150
_BH_C = 0.112
_BH_H = 0.032


def _bow_handle_parts(voxel=0.00045, tris=12000):
    al = P.M("Aluminium")
    ss = P.M("Stainless")
    c = _BH_C / 2
    feet = []
    for s in (-1, 1):
        f = G.prism(f"foot{s}", G.rrect(0.040, 0.026, 0.009, 10), 0.0, 0.0050, al, taper=0.94)
        f.location = (s * c, 0, 0)
        G.bake_xform(f)
        feet.append(f)
    # grip: an oval bar swept up out of each foot and across, its section flattening toward the middle
    zc = _BH_H - 0.0062
    path = G.bezier((-c - 0.004, 0, 0.004), (-c + 0.006, 0, zc + 0.006), (-c * 0.45, 0, zc + 0.001), (0, 0, zc), 14)
    path = path + [Vector((-p.x, p.y, p.z)) for p in reversed(path[:-1])]
    radii = []
    for p in path:
        t = min(1.0, abs(p.x) / c)                       # flares into the feet like a casting
        radii.append(1.0 + 0.30 * t ** 4)
    grip = G.sweep("grip", path, G.ellipse(0.0092, 0.0062, 20), al, radii=radii, twist_up=(0, 0, 1))
    body = G.join("casting", feet + [grip])
    m = body.modifiers.new("fuse", "REMESH")
    m.mode, m.voxel_size, m.adaptivity = "VOXEL", voxel, 0.0
    sm = body.modifiers.new("soften", "SMOOTH")
    sm.factor, sm.iterations = 0.5, 4
    G.apply(body)
    G.boolean(body, G.box("floor", (0, 0, -0.05), (0.4, 0.4, 0.1)))
    me = body.data
    me.calc_loop_triangles()
    dec = body.modifiers.new("budget", "DECIMATE")
    dec.ratio = min(1.0, (tris - 1500) / max(1, len(me.loop_triangles)))
    G.apply(body)
    # a countersink and an oval-head screw in each foot
    out = [body]
    for s in (-1, 1):
        x = s * (c + 0.004)
        csk = G.lathe(f"csk{s}", [(0, -0.01), (0.0022, -0.01), (0.0022, 0.0045), (0.0052, 0.0072), (0, 0.0072)], None, 32)
        G.boolean(body, _at(csk, (x, 0, 0)))
        h = G.lathe(f"screw{s}", [(0, 0), (0.0048, 0), (0.0045, 0.0009), (0.0030, 0.0018), (0, 0.0021)], ss, 20)
        _at(h, (x, 0, 0.0047))
        G.finish(h, 0.0, weighted=False)
        slot = G.box(f"slot{s}", (x, 0, 0.0066), (0.0075, 0.0011, 0.0016), None)
        G.boolean(h, slot)
        out.append(h)
    G.finish(body, 0.0, angle=40, sharp=50)
    body.name = "casting"
    return out, [("Grip", (0, 0, _BH_H - 0.006)), ("Base", (0, 0, 0))]


def _at(ob, loc):
    ob.location = loc
    G.bake_xform(ob)
    return ob


@P.part("BowHandle", "hull", "Sunfish bow handle: cast aluminium grip arched over two oval feet, one oval-head screw each, 150 mm")
def bow_handle():
    return P.done("BowHandle", *_bow_handle_parts())


P.SIZES["BowHandle"] = {"dim": "length mm", "default": "150", "scale": {"130": 130 / 150, "150": 1.0}}
