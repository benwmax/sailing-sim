"""Cabin-top fittings (part detail loop, Nov 2026: docs/part-detail-loop/cabintop.md): the fore hatch, the halyard deck
organiser and the teak handrail.

- HatchFwd: a low-profile aluminium-framed deck hatch. A screwed-down flange and a sloping extruded wall carry a black
  gasket; the lid is a thin aluminium band round a thick smoked acrylic pane that stands a few mm proud; two hinge
  knuckles with pins on the -X edge, two lever handles and their bosses under the pane on the +X side (seen through the
  smoke). w along X, d along Y, as the older kit part, so the layouts' options still fit.
- DeckOrganizer: a moulded composite organiser, sheaves side by side on upright axles between a base and a top plate
  with a dog-bone outline (round over each sheave, a waist between), a screw tab at each end, stainless axle heads on
  top. Catalogue size of the common 40 mm two-sheave model: 104 mm long, 24 mm high. The lines pass along X.
- HandrailTeak: a teak grab rail cut from one plank. Bean's dock photo of TX 7295 (IMG_9224): three hand holes a
  side on the J/22, tall feet, arched holes open to the deck, long sloped ends; the section is rounded to a grip.
  Catalogue rails: 2-3/8 in (60 mm) high, 1 in (25 mm) across, holes 10-1/16 in apart.

They live in their own file so threads working on other parts don't touch the same lines: bk_parts imports every
bk_part_*.py at its end, and the @part entries here replace bk_parts' older HatchFwd and HandrailTeak.
Conventions follow bk_parts: origin at the centre of the underside, +Z up, +X forward along the part.
"""
import math

from mathutils import Matrix, Vector

import bmesh

import bk_geom as G
import bk_parts as P


# ------------------------------------------------------------------ helpers

def _rrect_loft(name, w, d, r, prof, mat, segs=6, closed=True):
    """Loft rounded rectangles along a profile [(inset, z), ...]: each ring is the w x d outline moved in by `inset`.
    A closed profile makes a solid ring (a frame's section swept round its outline)."""
    bm = bmesh.new()
    rings = []
    for inset, z in prof:
        pts = G.rrect(w - 2 * inset, d - 2 * inset, max(r - inset, 0.002), segs)
        rings.append([bm.verts.new((x, y, z)) for x, y in pts])
    pairs = list(zip(rings, rings[1:] + ([rings[0]] if closed else [])))
    n = len(rings[0])
    for a, b in pairs:
        for k in range(n):
            bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return G.mesh_obj(name, bm, mat)


def _resample(pts, step):
    """Points every `step` along a closed outline."""
    segs = []
    total = 0.0
    for i in range(len(pts)):
        a, b = Vector(pts[i]), Vector(pts[(i + 1) % len(pts)])
        segs.append((a, b, total))
        total += (b - a).length
    n = max(4, round(total / step))
    out = []
    for k in range(n):
        s = total * k / n
        for a, b, s0 in segs:
            L = (b - a).length
            if s0 <= s <= s0 + L + 1e-12:
                out.append(a + (b - a) * ((s - s0) / max(L, 1e-12)))
                break
    return out


def _csk_screw(name, at, mat, r=0.0024, h=0.0008):
    """A flat countersunk head with a cross-slot hint (two shallow notches), sitting flush at `at`."""
    o = G.lathe(name, [(0, 0), (r, 0), (r * 0.96, h * 0.7), (r * 0.5, h), (0, h * 0.9)], mat, 14)
    o.location = at
    G.bake_xform(o)
    return G.finish(o, 0, weighted=False)


def _star_outline(inside, n=96, rmax=0.2):
    """The boundary of a region star-shaped about the origin, `inside(x, y)` -> bool, sampled on n rays."""
    out = []
    for i in range(n):
        a = G.TAU * i / n
        lo, hi = 0.0, rmax
        for _ in range(40):
            m = 0.5 * (lo + hi)
            if inside(m * math.cos(a), m * math.sin(a)):
                lo = m
            else:
                hi = m
        out.append((lo * math.cos(a), lo * math.sin(a)))
    return out


# ------------------------------------------------------------------ fore hatch

@P.part("HatchFwd", "hatch", "Low-profile aluminium deck hatch: flanged frame, gasket, smoked acrylic lid in an aluminium band, "
        "hinges with pins, two handles under the pane; w along X, d along Y")
def hatch_fwd(w=0.50, d=0.50):
    alu, acr, blk, ss = P.M("Aluminium"), P.M("CabinWindow"), P.M("BlackPlastic"), P.M("Stainless")
    r = min(0.045, 0.2 * min(w, d))
    objs = []
    # frame: flange (rolled edge), sloping wall, gasket seat, inner wall down into the deck opening
    frame = _rrect_loft("frame", w, d, r, [(0.0, 0.0), (0.0, 0.0022), (0.0012, 0.0036), (0.0040, 0.0042), (0.0080, 0.0050),
                                           (0.0095, 0.0070), (0.0115, 0.0195), (0.0130, 0.0212), (0.0225, 0.0212),
                                           (0.0240, 0.0190), (0.0265, 0.0040), (0.0300, 0.0000)], alu)
    objs.append(G.finish(frame, 0.0006, segs=2))
    objs.append(G.finish(_rrect_loft("gasket", w, d, r, [(0.0135, 0.0210), (0.0220, 0.0210), (0.0220, 0.0236),
                                                         (0.0135, 0.0236)], blk), 0.0005, segs=2))
    # lid: an aluminium band whose outer face lines up with the frame's wall top, a rebate for the pane inside it
    # (r2: the band's top is 14 mm wide, as on the low-profile hatches photographed, so the frame reads round the pane)
    lid = _rrect_loft("lid", w, d, r, [(0.0105, 0.0234), (0.0105, 0.0302), (0.0118, 0.0326), (0.0140, 0.0334),
                                       (0.0250, 0.0334), (0.0262, 0.0322), (0.0300, 0.0300), (0.0300, 0.0234)], alu)
    objs.append(G.finish(lid, 0.0004, segs=2))
    pane = G.prism("pane", G.rrect(w - 0.054, d - 0.054, max(r - 0.027, 0.004), 8), 0.0262, 0.0362, acr, taper=0.993)
    objs.append(G.finish(pane, 0.0016, segs=3))
    # hinges on the -X edge: a knuckle on the frame, a leaf on the lid, a pin along Y with domed ends
    xh = -w / 2 + 0.0105
    for s in (-1, 1):
        y = s * d * 0.28
        # (r2: the knuckles stand out past the frame's wall, as the hinge ears do on the real thing, and the leaf runs
        # well onto the lid's band)
        objs.append(G.finish(G.box(f"hinge_base{s}", (xh - 0.0090, y, 0.0140), (0.016, 0.044, 0.020), alu), 0.0018))
        objs.append(G.finish(G.box(f"hinge_leaf{s}", (xh + 0.006, y, 0.0340), (0.026, 0.034, 0.0046), alu), 0.0014))
        objs.append(G.finish(G.cyl(f"hinge_pin{s}", (xh - 0.011, y - 0.024, 0.0262), (xh - 0.011, y + 0.024, 0.0262), 0.0068, alu, 24), 0.0010))
        for k in (-1, 1):            # the knuckle splits: a gap either side of the lid's middle knuckle
            objs.append(G.finish(G.cyl(f"hinge_gap{s}{k}", (xh - 0.011, y + k * 0.0075, 0.0262), (xh - 0.011, y + k * 0.0085, 0.0262), 0.0070, blk, 24), 0))
        for e in (-1, 1):
            objs.append(G.finish(G.lathe(f"pin_end{s}{e}", [(0, 0), (0.0026, 0), (0.0022, 0.0013), (0, 0.0017)], ss, 12,
                                         axis_mat=Matrix.Translation((xh - 0.011, y + e * 0.024, 0.0262)) @ Matrix.Rotation(-e * math.pi / 2, 4, "X")), 0))
    # handles under the pane on the +X side: a boss on the lid's underside, a lever lying along the edge, a cam tongue
    xl = w / 2 - 0.040
    for s in (-1, 1):
        y = s * d * 0.25
        objs.append(G.finish(G.cyl(f"handle_boss{s}", (xl, y, 0.0262), (xl, y, 0.0150), 0.010, blk, 24), 0.0012))
        lever = G.sweep(f"handle{s}", [(xl, y, 0.016), (xl - 0.006, y - s * 0.030, 0.0145), (xl - 0.010, y - s * 0.060, 0.012)],
                        G.rrect(0.010, 0.006, 0.0028, 3), blk)
        objs.append(G.finish(lever, 0.0008))
        objs.append(G.finish(G.box(f"handle_cam{s}", (xl + 0.013, y, 0.0170), (0.014, 0.012, 0.004), blk), 0.0008))
    # flange screws, evenly round the outline
    ring = G.rrect(w - 0.0088, d - 0.0088, r - 0.0044, 6)
    for i, p in enumerate(_resample(ring, 0.085)):
        objs.append(_csk_screw(f"screw{i}", (p.x, p.y, 0.0040), ss))
    # a made-up maker's plate on the lid band's +X side
    objs.append(P.badge("plate", "Plate", 0.028, 0.0045, Matrix.Translation((w / 2 - 0.0195, 0, 0.0334)) @ Matrix.Rotation(math.pi / 2, 4, "Z"), alu))
    return P.done("HatchFwd", objs, [("HandleS", (xl, d * 0.25, 0.02)), ("HandleP", (xl, -d * 0.25, 0.02)),
                                     ("Hinge", (xh - 0.011, 0, 0.0262)), ("Pane", (0, 0, 0.036))])


# ------------------------------------------------------------------ deck organiser

@P.part("DeckOrganizer", "block", "Composite deck organiser, 40 mm sheaves side by side on upright axles (2 by default), "
        "dog-bone plates, screw tab each end: 104 x 46 x 24 mm for two")
def deck_organizer(sheaves=2):
    blk, ss = P.M("BlackPlastic"), P.M("Stainless")
    R, pitch, tab = 0.020, 0.044, 0.030          # sheave radius, sheave spacing, axle to the end of the tab
    rp, waist = 0.0235, 0.0175                   # plate radius round a sheave, half width at the waist
    n = sheaves
    ys = [(i - (n - 1) / 2) * pitch for i in range(n)]
    half = ys[-1] + tab
    z0, z1 = 0.0042, 0.0182                       # base plate top, top plate underside
    zt = 0.0224                                   # top plate; with the axle heads, the catalogue's 24 mm overall

    def in_plate(x, y, tabs):
        if any((x * x + (y - c) ** 2) <= rp * rp for c in ys):
            return True
        if abs(x) <= waist and ys[0] <= y <= ys[-1]:
            return True
        if tabs:                                  # a capsule along Y, 28 mm wide, to the tab ends
            yy = min(max(y, -(half - 0.014)), half - 0.014)
            return x * x + (y - yy) ** 2 <= 0.014 ** 2
        return False

    objs = []
    base = G.prism("base", _star_outline(lambda x, y: in_plate(x, y, True), 120), 0.0, z0, blk, taper=0.97)
    objs.append(G.finish(base, 0.0012, segs=2))
    # r2 tried one flat top plate without the crown and the waist plate (r1 reviewers: "puffy"); it lost 0 of 3 to r1,
    # whose raised rim and waist plate read as a moulded production part, so r1's top stands
    top = G.prism("top", _star_outline(lambda x, y: in_plate(x, y, False), 120), z1, zt - 0.0012, blk, taper=0.985)
    objs.append(G.finish(top, 0.0012, segs=2))
    crown = G.prism("crown", _star_outline(lambda x, y: in_plate(x * 1.12, y * 1.04, False), 120), zt - 0.0013, zt, blk, taper=0.95)
    objs.append(G.finish(crown, 0.0006, segs=2))
    # the web joining the plates at each waist (the side the lines never touch) and its fillet
    for i in range(n - 1):
        yw = 0.5 * (ys[i] + ys[i + 1])
        web = G.prism(f"web{i}", G.rrect(0.022, 0.0065, 0.003, 4), z0 - 0.0005, z1 + 0.0005, blk)
        web.location = (0, yw, 0)
        G.bake_xform(web)
        objs.append(G.finish(web, 0.0008))
    # sheaves with a round groove for 8-10 mm line, a stainless bushing, an axle head on top and a nut under the base's skirt
    zm = 0.5 * (z0 + z1)
    for i, c in enumerate(ys):
        prof = [(0.0055, z0 + 0.0008), (R - 0.0006, z0 + 0.0008), (R, z0 + 0.0016)]
        for k in range(9):
            a = math.pi * k / 8
            prof.append((R - 0.0042 * math.sin(a), zm - 0.0050 * math.cos(a)))
        prof += [(R, z1 - 0.0016), (R - 0.0006, z1 - 0.0008), (0.0055, z1 - 0.0008)]
        sh = G.lathe(f"sheave{i}", prof, blk, 48)
        sh.location = (0, c, 0)
        G.bake_xform(sh)
        objs.append(G.finish(sh, 0, sharp=50))
        objs.append(G.finish(G.cyl(f"bush{i}", (0, c, z0), (0, c, z1), 0.0058, ss, 20), 0))
        cap = G.lathe(f"axle{i}", [(0, zt - 0.0003), (0.0050, zt - 0.0003), (0.0050, zt + 0.0006), (0.0042, zt + 0.0014), (0, zt + 0.0016)], ss, 24)
        cap.location = (0, c, 0)
        G.bake_xform(cap)
        objs.append(G.finish(cap, 0, weighted=False))
        hexs = G.prism(f"socket{i}", [(0.0016 * math.cos(G.TAU * k / 6), 0.0016 * math.sin(G.TAU * k / 6)) for k in range(6)],
                       zt + 0.0012, zt + 0.0017, blk)
        hexs.location = (0, c, 0)
        G.bake_xform(hexs)
        objs.append(hexs)
    objs.append(P.badge("plate", "Plate", 0.014, 0.0045, Matrix.Translation((0.0135, 0, zt - 0.0006)) @ Matrix.Rotation(math.pi / 2, 4, "Z"), blk))
    # a countersunk screw in each tab
    for s in (-1, 1):
        objs.append(_csk_screw(f"screw{s}", (0, s * (half - 0.0110), z0), ss, r=0.0030, h=0.0007))
    socks = [("Base", (0, 0, 0))] + [(f"Line{i}", (0, c, zm)) for i, c in enumerate(ys)]
    return P.done("DeckOrganizer", objs, socks)


P.SIZES["DeckOrganizer"] = {"dim": "sheave mm", "default": "40", "scale": {"40": 1.0, "50": 1.25}}


# ------------------------------------------------------------------ teak handrail

def _handrail_outline(length, loops, h, hole_h, end, foot, rc=0.011, flare=0.006):
    """The rail's side outline in XZ (counter-clockwise): flat on the deck under each foot, arched hand holes open to
    the deck between the feet, long sloped ends rising to the grip."""
    L2 = length / 2
    pitch = (length - 2 * end) / loops
    feet = [-L2 + end + k * pitch for k in range(loops + 1)]
    pts = [(-L2, 0.0)]
    for k in range(loops):
        xa, xb = feet[k] + foot / 2, feet[k + 1] - foot / 2
        # up the foot's face: a small flare at the deck, straight, then the arch's corner
        pts += [(xa - flare, 0.0), (xa - flare * 0.25, flare * 0.6), (xa, flare * 1.6)]
        for i in range(7):
            a = math.pi - (math.pi / 2) * i / 6
            pts.append((xa + rc + rc * math.cos(a), hole_h - rc + rc * math.sin(a)))
        # the grip's underside sags a touch at the middle (a hand's room is where it is used)
        for i in range(1, 6):
            t = i / 6
            pts.append((xa + rc + (xb - xa - 2 * rc) * t, hole_h + 0.0015 * math.sin(math.pi * t)))
        for i in range(7):
            a = math.pi / 2 - (math.pi / 2) * i / 6
            pts.append((xb - rc + rc * math.cos(a), hole_h - rc + rc * math.sin(a)))
        pts += [(xb, flare * 1.6), (xb + flare * 0.25, flare * 0.6), (xb + flare, 0.0)]
    pts.append((L2, 0.0))
    # the ends: a short upright at the deck, then an S-curve up to the grip's top, the top flat between
    for i in range(13):
        t = i / 12
        e = t * t * (3 - 2 * t)
        pts.append((L2 - end * (0.10 + 0.90 * t), 0.008 + (h - 0.008) * e))
    for i in range(13):
        t = i / 12
        e = t * t * (3 - 2 * t)
        pts.append((-L2 + end * (0.10 + 0.90 * (1 - t)), 0.008 + (h - 0.008) * (1 - e)))
    pts.append((-L2, 0.004))
    # drop points that land on each other
    out = []
    for p in pts:
        if not out or (Vector(p) - Vector(out[-1])).length > 1e-5:
            out.append(p)
    return out, feet


@P.part("HandrailTeak", "trim", "Teak cabin-top handrail cut from one plank: arched hand holes open to the deck, tall feet, "
        "sloped ends, rounded grip, bungs over the bolts; length and loops options (60 x 25 mm section)")
def handrail(length=0.90, loops=4):
    teak = P.M("Teak")
    # r2 (all three r1 reviewers: too slender and low, stubby feet, shallow holes, thin ends): the J/22's rails are
    # chunkier than the catalogue's 60 x 25 mm, as Bean's photo shows: 66 mm high, 28 mm across, tall arched holes,
    # broad feet flaring into the deck, long heavy ends
    # r3 (r2 won 3 of 3 against r1, but all three still read it as too low with shallow holes next to the photo, where
    # the holes are about as tall as the bar is deep): 72 mm high, 30 mm across, 46 mm holes
    h, t = 0.072, 0.030
    end = min(0.115, length * 0.14)
    foot = 0.068
    hole_h = 0.046
    outline, feet = _handrail_outline(length, loops, h, hole_h, end, foot, rc=0.017, flare=0.011)
    rail = P._xz_prism("rail", outline, -t / 2, t / 2, teak)
    # round the grip: a generous roll on every long edge (8 of the 12.5 mm half width), the deck edges barely broken
    objs = [G.finish(rail, 0.0085, segs=4, angle=30)]
    # bungs over the through-bolts, one a foot (the end feet sit under the ramps' tops)
    for k, x in enumerate(feet):
        b = G.lathe(f"bung{k}", [(0, h - 0.0024), (0.0048, h - 0.0024), (0.0048, h + 0.0002), (0.0040, h + 0.0005), (0, h + 0.0006)], teak, 16)
        b.location = (x, 0, 0)
        G.bake_xform(b)
        objs.append(G.finish(b, 0, weighted=False))
    pitch = (length - 2 * end) / loops
    socks = [(f"Grip{i}", (-length / 2 + end + (i + 0.5) * pitch, 0, 0.5 * (hole_h + h))) for i in range(loops)]
    return P.done("HandrailTeak", objs, socks)
