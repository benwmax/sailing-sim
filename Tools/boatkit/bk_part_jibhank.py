"""JibHank: a moulded nylon piston hank with a brass piston, screwed through the jib's luff (part detail loop, Nov 8 2026).

Bean's reference sheet (middle row, fourth): the white plastic hank with a brass plunger that clips a hank-on jib to the
forestay. Sized from the catalogue's 1/4 in (6.4 mm) wire piston hank: 50 mm overall, UV-stabilised nylon body, brass
piston, two screws through the sail. The card, references and rounds are in partloop/parts/jibhank.json and
docs/part-detail-loop/jibhank.md.

Frame (this part differs from the deck fittings: it hangs on a wire, not on a surface): the origin is the centre of the
forestay inside the hook's eye and the stay runs along Y, so the hook's J-shape lies in the XZ plane and the render
loop's square-on "side" view shows it. The sail lies in a plane parallel to XY (z = SAIL_Z, a little below the eye's centre) aft of the stay, along -X: its luff edge
sits in the slot between the two cheeks at the tail and the two screws go through it along Z. The piston runs along X
above the eye and closes the hook's mouth; the brass knob at its aft end pulls it back to open.

Sockets: Stay (the wire's centre, along Y), Luff (the sail's edge in the slot), Piston (where the piston meets the hook's
tip), Knob (the thumb knob a hand pulls).
"""
import math

from mathutils import Matrix

import bk_geom as G
import bk_parts as P

# mm, from the catalogue (overall, wire) and Bean's sheet photo (proportions, read off a three-quarter view)
WIRE = 6.4
EYE_R = 4.7              # the eye's inside radius: a 6.4 mm wire passes with room to slide
HOOK_W = 6.2             # the hook's section across (radial), and along the stay
HOOK_T = 9.0
TIP_DEG = 108.0          # where the hook ends, measured round from straight down (-Z) through forward (+X): 180 + 102
BODY_X = (-27.0, -12.4)   # the body block aft of the eye, holding the piston
TAIL_X = (-40.2, -22.0)  # the tail: two cheeks on the luff
TAIL_Z = (-9.8, 2.6)
SAIL_Z = -3.4            # the sail's plane: the slot sits below the piston's line so the knob clears the cheeks
TAIL_T = 14.0            # cheek length along the luff (the stay's direction)
SLOT = 2.2               # the sail's thickness in the slot
PISTON_R = 2.1
KNOB_R = 4.4
SCREW_X = -36.4


def _mm(*v):
    return tuple(x / 1000.0 for x in v)


def _xz_prism(name, outline_xz, half_t, mat):
    """Extrude an XZ outline (mm) from y = -half_t to +half_t (mm)."""
    o = G.prism(name, [(x / 1000, z / 1000) for x, z in outline_xz], -half_t / 1000, half_t / 1000, mat)
    o.data.transform(Matrix.Rotation(math.radians(90), 4, "X"))   # (x, y, z) -> (x, -z, y): the outline's y becomes Z
    return o


def _rrect_xz(x0, x1, z0, z1, r, segs=6):
    w, h = x1 - x0, z1 - z0
    return [(x + (x0 + x1) / 2, z + (z0 + z1) / 2) for x, z in G.rrect(w, h, r, segs)]


def _hook_path(rc, tip_deg, n=40):
    """The hook's centreline (mm, XZ): straight in from the body along the bottom, round the front, up and over to the tip."""
    pts = [(-14.0, -rc), (-7.0, -rc), (-2.5, -rc)]
    a0, a1 = -90.0, tip_deg
    for i in range(1, n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((rc * math.cos(a), rc * math.sin(a)))
    return pts


def _jib_hank_parts(tris=14000, voxel=0.00024):
    nylon, brass, ss = P.M("WhitePlastic"), P.M("Brass"), P.M("Stainless")
    rc = EYE_R + HOOK_W / 2
    tip = math.radians(TIP_DEG)
    zp = rc * math.sin(tip)                                    # the piston's line: level with the hook's tip
    tip_x = rc * math.cos(tip)

    # --- the moulding: hook sweep + body block + tail, fused into one piece by a voxel remesh (soft moulded fillets)
    sec = [(u / 1000, v / 1000) for u, v in G.rrect(HOOK_W, HOOK_T, 2.2, 5)]
    path = [(x / 1000, 0.0, z / 1000) for x, z in _hook_path(rc, TIP_DEG)]
    # the hook is chunky where it leaves the body and tapers toward the tip (r2's reviewers: a thin uniform C)
    n = len(path)
    radii = [1.22 - 0.30 * min(1.0, i / (n * 0.55)) for i in range(n)]
    hook = G.sweep("hook", path, sec, nylon, radii=radii, twist_up=(0, 1, 0))
    # a rounded end on the tip: the piston seats in it
    tipk = G.lathe("tipk", [(math.sin(math.pi * i / 12) * 1.0, -math.cos(math.pi * i / 12)) for i in range(13)], nylon, 24)
    tipk.data.transform(Matrix.Diagonal((HOOK_W / 2000 * 1.12, HOOK_T / 2000 * 0.98, HOOK_W / 2000 * 1.12, 1.0)))
    tipk.location = _mm(tip_x, 0, zp)
    G.bake_xform(tipk)
    top = zp + PISTON_R + 3.0
    # the body's top rises from the mouth toward the knob (Bean's photo); its corners round off in the bevel and remesh
    bot = -rc - HOOK_W / 2
    body = _xz_prism("block", [(BODY_X[1], bot), (BODY_X[1], top - 1.0), (BODY_X[1] - 3.0, top - 0.6), (BODY_X[0], top + 1.0),
                               (BODY_X[0], bot)], HOOK_T / 2, nylon)
    tail = _xz_prism("tail", _rrect_xz(TAIL_X[0], TAIL_X[1], TAIL_Z[0], TAIL_Z[1], 4.2), TAIL_T / 2, nylon)
    # a raised boss round the knob's slot at the top aft of the body
    # a web where the hook leaves the body's underside, so the two flow into one curve instead of stepping
    web = G.lathe("web", [(math.sin(math.pi * i / 12), -math.cos(math.pi * i / 12)) for i in range(13)], nylon, 24)
    web.data.transform(Matrix.Diagonal((6.0 / 1000, HOOK_T / 2000 * 1.02, 4.4 / 1000, 1.0)))
    web.location = _mm(BODY_X[1] - 0.5, 0, -rc - 0.6)
    G.bake_xform(web)
    boss = G.cyl("boss", _mm(BODY_X[0] - 1.0, 0, zp), _mm(BODY_X[0] + 6.0, 0, zp), (PISTON_R + 2.6) / 1000, nylon, 32)
    for o in (body, tail):
        G.finish(o, 0.0017, segs=4, angle=30, weighted=False)     # moulded edges: about a 1.7 mm radius
    mould = G.join("mould", [hook, tipk, web, body, tail, boss])
    m = mould.modifiers.new("fuse", "REMESH")
    m.mode, m.voxel_size, m.adaptivity = "VOXEL", voxel, 0.0
    sm = mould.modifiers.new("soften", "SMOOTH")
    sm.factor, sm.iterations = 0.5, 10
    G.apply(mould)
    # the luff slot between the cheeks, open aft
    G.boolean(mould, G.box("slot", _mm((TAIL_X[0] - 4 + TAIL_X[1] + 2) / 2, 0, SAIL_Z), _mm(TAIL_X[1] + 2 - TAIL_X[0] + 4, TAIL_T + 6, SLOT)))
    # the piston's bore, opening on the body's front face into the mouth
    G.boolean(mould, G.cyl("bore", _mm(BODY_X[1] + 3, 0, zp), _mm(BODY_X[0] + 3.0, 0, zp), (PISTON_R + 0.25) / 1000, None, 24))
    # the rounded side window where the brass piston shows (Bean's photo: a slot in the body's flank)
    G.boolean(mould, _xz_prism("window", _rrect_xz(-23.0, -15.6, zp - 2.5, zp + 2.5, 2.45), HOOK_T, None))
    # screw holes through both cheeks
    for y in (-3.6, 3.6):
        G.boolean(mould, G.cyl(f"hole{y}", _mm(SCREW_X, y, TAIL_Z[0] - 2), _mm(SCREW_X, y, TAIL_Z[1] + 2), 0.0013, None, 16))
    d = mould.modifiers.new("budget", "DECIMATE")
    mould.data.calc_loop_triangles()
    d.ratio = min(1.0, tris / max(1, len(mould.data.loop_triangles)))
    G.apply(mould)
    G.finish(mould, 0.0, sharp=70)
    mould.name = "body"

    # --- the brass piston: a rod across the mouth into the tip (it shows in the side window), a smooth flat-topped thumb knob aft
    objs = [mould]
    rod = G.cyl("piston", _mm(BODY_X[0] + 2.0, 0, zp), _mm(tip_x - 0.6, 0, zp), PISTON_R / 1000, brass, 24)
    objs.append(G.finish(rod, 0.0003, segs=2))
    neck = G.cyl("knob_neck", _mm(BODY_X[0] - 1.2, 0, zp), _mm(BODY_X[0] - 2.6, 0, zp), 1.2 / 1000, brass, 16)
    objs.append(G.finish(neck, 0.0002, segs=1))
    kx0, kx1 = BODY_X[0] - 2.6, BODY_X[0] - 6.8
    prof = [(0, 0), (KNOB_R - 0.6, 0), (KNOB_R, 0.6), (KNOB_R, 3.4), (KNOB_R - 0.9, 4.2), (0, 4.2)]
    knob = G.lathe("knob", [(r / 1000, z / 1000) for r, z in prof], brass, 36)
    knob.matrix_world = G.along(_mm(kx0, 0, zp), (-1, 0, 0))
    G.bake_xform(knob)
    objs.append(G.finish(knob, 0.0002, segs=2, sharp=40))

    # --- two stainless pan-head screws down through the cheeks and the sail, nuts underneath
    screws = []
    for y in (-3.6, 3.6):
        for s, z in ((1, TAIL_Z[1] - 0.5), (-1, TAIL_Z[0] + 0.5)):
            h = G.lathe(f"screw{y}{s}", [(0, 0), (3.0 / 1000, 0), (2.9 / 1000, 1.0 / 1000), (2.1 / 1000, 1.9 / 1000), (0, 2.0 / 1000)], ss, 24)
            h.matrix_world = G.along(_mm(SCREW_X, y, z), (0, 0, s))
            G.bake_xform(h)
            G.finish(h, 0, weighted=False)
            if s > 0:                                   # a cross recess in the top heads
                for ang in (0, 90):
                    c = G.box("x", (0, 0, 0), (0.0032, 0.0006, 0.0022))
                    c.matrix_world = Matrix.Translation(_mm(SCREW_X, y, z + 2.0)) @ Matrix.Rotation(math.radians(ang), 4, "Z")
                    G.bake_xform(c)
                    G.boolean(h, c)
            screws.append(h)
    objs.append(G.join("screw", screws))

    socks = [("Stay", (0.0, 0.0, 0.0)), ("Luff", _mm((TAIL_X[0] + TAIL_X[1]) / 2 - 3, 0, SAIL_Z)), ("Piston", _mm(tip_x, 0, zp)),
             ("Knob", _mm(kx1, 0, zp))]
    return objs, socks


@P.part("JibHank", "rigging", "Nylon piston hank, 50 mm, for 6.4 mm (1/4 in) forestay wire: brass piston and knob, screwed through the luff")
def jib_hank():
    objs, socks = _jib_hank_parts()
    return P.done("JibHank", objs, socks)
