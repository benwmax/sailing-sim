"""Forged stainless shackles for the boat kit (part detail loop, Nov 2026: docs/part-detail-loop/shackles.md).

Two parts that share one design, sized from a 5 mm forged stainless catalogue range:
  ShackleBow  a bow (lyre) shackle: legs that swell out into a round crown, for loads that pull at an angle
              (jib tack, a halyard on its head, a block on a padeye). 36 mm overall, 10 mm opening, 25 mm across the bow.
  ShackleD    a long D (dee) shackle, as on Bean's reference sheet: straight legs and a half-round crown, for a straight
              pull (sheets, vang, a block on a bail). 41 mm overall, 10 mm opening, a forged flat section. Replaces the October kit's ShackleD (a bent tube with a loose pin).

Both: a 5 mm round body forged into flat round ears, a 5 mm pin through the ears with a flat key head (a tab with a
hole for seizing wire) on one side and a domed end on the other. The body and ears are fused by a voxel remesh, so the
ears grow out of the legs like a forging instead of sitting on them.

Frame (kit convention, as the blocks' own shackles): origin at the pin's centre, pin along X with its head on +X, the
shackle standing up along +Z in the XZ plane, so the part loop's square-on "side" view (along Y) sees its face.
Sockets: Pin (origin), Bow (inside of the crown, where a line or ring sits), Head (the key head's tab).

Parts kept in their own files (bk_part_<name>.py) register themselves when bk_parts imports them at its end.
"""
import math

from mathutils import Matrix, Vector

import bk_geom as G
import bk_parts as P

WIRE = 0.005            # body and pin diameter, 5 mm
OPENING = 0.010         # inside width at the pin


def _ear_x(opening=OPENING):
    return opening / 2 + WIRE / 2          # each ear's centre on the pin


def _forged_body(name, path_right, xe, k_ear=0.94, voxel=0.00016, tris=9000, flat=1.0):
    """Body tube along a centreline (the right half from the ear up to the crown's top, mirrored), two flat round
    ears at the pin, fused by a voxel remesh and reduced to `tris`."""
    steel = P.M("Stainless")
    r = WIRE / 2
    half = [Vector(p) for p in path_right]
    # left ear up to the crown's top (the right half mirrored), then down the right half to the right ear
    full = [Vector((-p.x, p.y, p.z)) for p in half] + list(reversed(half))[1:]
    # flatten the wire a little where it meets the ears (forged lugs are wider than the round body)
    radii = []
    for p in full:
        t = max(0.0, 1.0 - p.z / (WIRE * 1.4))
        radii.append(1.0 + 0.10 * t)
    # section: round, or with flat=0.84 a forged flat section (flat faces toward the viewer square-on: thinner across
    # the shackle's plane than in it), a superellipse so the faces read flat with rounded edges
    sec = []
    for i in range(24):
        a = G.TAU * i / 24
        c, s_ = math.cos(a), math.sin(a)
        e = 2.0 if flat >= 1.0 else 3.2
        sec.append((r * flat * math.copysign(abs(c) ** (2 / e), c), r * math.copysign(abs(s_) ** (2 / e), s_)))
    body = G.sweep("body", [tuple(p) for p in full], sec, steel, radii=radii)
    ears = []
    for s in (-1, 1):
        # a flat disc in the YZ plane (the pin passes through it along X), a little thinner than the wire
        e = G.lathe(f"ear{s}", [(0, -0.5), (0.72, -0.5), (0.9, -0.42), (0.98, -0.26), (1.0, 0.0), (0.98, 0.26), (0.9, 0.42),
                                   (0.72, 0.5), (0, 0.5)], steel, 40)
        # a lug round the pin: a pin bore's wall below, stretched up into the leg above (taller than wide)
        e.data.transform(Matrix.Diagonal((k_ear * WIRE * 1.45, k_ear * WIRE * 1.08, 0.96 * WIRE, 1.0)))
        e.matrix_world = (Matrix.Translation((s * xe, 0, 0.0018)) @ Matrix.Rotation(math.radians(90), 4, "Y"))
        G.bake_xform(e)
        ears.append(e)
    fused = G.join("forging", [body] + ears)
    m = fused.modifiers.new("fuse", "REMESH")
    m.mode, m.voxel_size, m.adaptivity = "VOXEL", voxel, 0.0
    sm = fused.modifiers.new("soften", "SMOOTH")
    sm.factor, sm.iterations = 0.5, 3
    G.apply(fused)
    # the pin bore through both ears (seen at the domed end and behind the key head)
    bore = G.cyl("bore", (-xe - WIRE, 0, 0), (xe + WIRE, 0, 0), r * 1.02, steel, 32)
    G.boolean(fused, bore)
    me = fused.data
    me.calc_loop_triangles()
    d = fused.modifiers.new("budget", "DECIMATE")
    d.ratio = min(1.0, tris / max(1, len(me.loop_triangles)))
    G.apply(fused)
    G.finish(fused, 0.0, sharp=70)
    fused.name = "forging"
    return fused


def _key_pin(xe, tab=0.0060):
    """The pin: a 5 mm shank through both ears, a domed end proud of the -X ear and on +X a collar and a flat key head
    (a rounded tab in the XZ plane with a seizing-wire hole along Y)."""
    steel = P.M("Stainless")
    r = WIRE / 2
    ear_t = 0.96 * WIRE / 2
    x0, x1 = -xe - ear_t - 0.0006, xe + ear_t
    objs = []
    shank = G.cyl("pin", (x0, 0, 0), (x1, 0, 0), r * 0.99, steel, 28)
    objs.append(G.finish(shank, 0.0002, segs=2))
    dome = G.lathe("pinend", [(math.cos(a) * r * 0.99, math.sin(a) * r * 0.45) for a in [i * math.pi / 2 / 6 for i in range(7)]], steel, 28)
    dome.matrix_world = Matrix.Translation((x0, 0, 0)) @ Matrix.Rotation(math.radians(-90), 4, "Y")
    G.bake_xform(dome)
    objs.append(G.finish(dome, 0, weighted=False))
    collar = G.cyl("pincollar", (x1, 0, 0), (x1 + 0.0011, 0, 0), r * 1.42, steel, 32)
    objs.append(G.finish(collar, 0.0003, segs=2))
    # key head: a rounded tab standing in the XZ plane, its round end out along +X, hole along Y
    L, H, T = tab, 0.0076, 0.0022
    tab = G.prism("pinhead", G.rrect(L, H, H * 0.30, 8), -T / 2, T / 2, steel)
    tab.matrix_world = Matrix.Translation((x1 + 0.0011 + L / 2 - 0.0012, 0, 0)) @ Matrix.Rotation(math.radians(90), 4, "X")
    G.bake_xform(tab)
    hx = x1 + 0.0011 + L - 0.0012 - H * 0.46
    G.boolean(tab, G.cyl("tabhole", (hx, -0.01, 0), (hx, 0.01, 0), 0.0019, steel, 28))
    objs.append(G.finish(tab, 0.0004, segs=2))
    return objs, (hx, 0, 0)


# Bow centreline, right half, from the ear up to the crown's top: (x, z) in mm from the pin's centre for a 5 mm
# shackle, measured row by row on the square-on reference photo scaled to the catalogue's 36 mm. The legs pinch in
# just above the ears (the lyre's waist), swell out to the widest point two thirds up and close over a crown a little
# taller than a half circle.
_BOW_LINE = [(8.0, 0.0), (7.3, 2.2), (6.75, 4.4), (7.0, 7.0), (8.0, 10.2), (9.2, 13.4), (10.0, 16.5), (9.8, 19.0),
             (8.9, 21.6), (7.6, 24.2), (5.6, 26.6), (3.0, 28.2), (0.0, 28.8)]


def _catmull(pts, n=6):
    """A smooth line through the points (Catmull-Rom, ends held)."""
    out = []
    P_ = [Vector(p) for p in pts]
    for i in range(len(P_) - 1):
        p0, p1, p2, p3 = P_[max(i - 1, 0)], P_[i], P_[i + 1], P_[min(i + 2, len(P_) - 1)]
        for j in range(n):
            t = j / n
            out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P_[-1])
    return out


def _bow_path(scale=1.0):
    pts = _catmull([(x * 0.001 * scale, 0.0, z * 0.001 * scale) for x, z in _BOW_LINE], 6)
    pts[-1].x = 0.0
    return [tuple(p) for p in pts]


def _d_path(inside_len=0.0310):
    r = WIRE / 2
    xe = _ear_x()
    zt = inside_len + r
    zc = zt - xe
    pts = [(xe, 0, z) for z in [0.0, zc * 0.33, zc * 0.66, zc]]
    pts += G.arc_pts((0, 0, zc), xe, 0, math.pi / 2, 14, "xz")[1:]
    return pts


def _shackle(name, path, inside_len, tris, flat=1.0, tab=0.0066):
    xe = path[0][0]                          # the ears sit where the centreline starts
    body = _forged_body(name, path, xe, tris=tris, flat=flat)
    pin, hole = _key_pin(xe, tab)
    socks = [("Pin", (0, 0, 0)), ("Bow", (0, 0, inside_len)), ("Head", hole)]
    return P.done(name, [body] + pin, socks)


@P.part("ShackleBow", "fastener", "5 mm forged stainless bow shackle, key-head pin along X, bow up (36 mm overall)")
def shackle_bow():
    return _shackle("ShackleBow", _bow_path(), _BOW_LINE[-1][1] * 0.001 - WIRE / 2, 11000)


@P.part("ShackleD", "fastener", "5 mm forged stainless D shackle, key-head pin along X, bow up (41 mm overall, a long D)")
def shackle_d(inside_len=0.0310):
    return _shackle("ShackleD", _d_path(inside_len), inside_len, 11000, flat=0.84, tab=0.0080)


P.SIZES["ShackleBow"] = {"dim": "pin diameter mm", "default": "5", "scale": {"4": 0.8, "5": 1.0, "6": 1.2, "8": 1.6, "10": 2.0}}
P.SIZES["ShackleD"] = {"dim": "pin diameter mm", "default": "5", "scale": {"4": 0.8, "5": 1.0, "6": 1.2, "8": 1.6, "10": 2.0}}
