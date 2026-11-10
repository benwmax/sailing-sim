"""Fenders and dock lines (part detail loop, Nov 2026: docs/part-detail-loop/docklines.md).

  Fender      a twin-eye ribbed vinyl fender, 6.5 x 22 in (165 x 559 mm), the size the catalogues give for 20 to 30 ft
              boats (Polyform G-4 class, Taylor Made Tuff End): a straight body with twelve shallow lengthwise ribs,
              rounded shoulders into blunt cone ends, a moulded eye lug at each end with an 18 mm rope hole, and the
              inflation valve on the top shoulder. Origin at the top eye's hole (it hangs from there), -Z down.
  DockLineEye the end of a 3/8 in (9.5 mm) three-strand nylon dock line with a 12 in (305 mm) soft eye spliced in:
              five tucks against the lay, the splice tapering to its cut ends. Laid flat on the deck, throat at the
              origin, the eye towards +X and the standing part off along -X.
  CleatHitch  the same line made fast on the club's 10 in dock cleat (Tools/blender/build_docks.py SM_Dock_Cleat): a
              turn round the base, a figure eight and a locking hitch, the tail on the deck. Rope only (the cleat is
              the dock's); origin on the deck under the cleat's middle, cleat frame (X along the horns). Options: the
              cleat's length and the lead's direction.
  EyeOnCleat  the eye end dropped round the J/22's 130 mm bow cleat (kit HornCleat 130), under both horns, with the
              throat and the standing part leading off. Rope only, cleat frame.

Ropework maths (paths, three strands, tucks, hitch) is bk_ropework.py, shared with Tools/blender/build_berthed.py.
Lives in its own file (bk_parts imports every bk_part_*.py at its end).
"""
import math

import bmesh
from mathutils import Matrix, Vector

import bk_geom as G
import bk_parts as P
import bk_ropework as RW
from bk_parts import M, done, part

LINE_D = 0.0095                       # 3/8 in
DOCK_CLEAT = dict(L=0.254, h_under=0.047, h_top=0.070, half_w=0.012, foot_x=0.056)   # SM_Dock_Cleat (build_docks.py)
BOW_CLEAT = dict(L=0.130, h_under=0.026, h_top=0.038, half_w=0.008, foot_x=0.024)    # kit HornCleat 130


def rope_objs(name, path, d, slot="Rope", segs=5, step_div=10.0, phase=0.0, plain=False, swell=None):
    """A three-strand rope along a path as three strand tubes (or one plain tube)."""
    if plain:
        return [G.tube(name, RW.resample(path, 0.01), d / 2, M(slot), 8)]
    sts, sr = RW.strands(path, d, phase=phase, step=3.3 * d / step_div, swell=swell)
    return [G.tube(f"{name}{k}", pts, sr, M(slot), segs) for k, pts in enumerate(sts)]


def splice_objs(name, standing, splice, d, slot="Rope"):
    """The tucked strands over the standing part's first `splice` metres, each ending in a heat-sealed nub."""
    out = []
    for k, (pts, radii) in enumerate(RW.tucks(standing, d, 0.0, splice)):
        if len(pts) > 2:
            out.append(G.tube(f"{name}{k}", pts, 1.0, M(slot), 5, radii=radii))
    return out


# ------------------------------------------------------------------ fender

@part("Fender", "loose", "Twin-eye ribbed vinyl fender, 6.5 x 22 in (165 x 559 mm), eye lugs at both ends")
def fender(colour="WhitePlastic", dia=0.165, length=0.559, ribs=12):
    eye_len = 0.045
    prof = RW.fender_profile(dia, length, eye_len)
    R = dia / 2
    # the body: a lathe whose radius carries the lengthwise ribs (shallow, rounded), fading out on the shoulders
    segs = ribs * 6
    bm = bmesh.new()
    rings = []
    for z, r in prof:
        full = r / R
        ring = []
        for k in range(segs):
            a = G.TAU * k / segs
            rib = 0.5 + 0.5 * math.cos(ribs * a)
            rr = r * (1 + 0.03 * rib ** 6 * min(1.0, full ** 4))
            ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z)))
        rings.append(ring)
    for a_, b_ in zip(rings, rings[1:]):
        for k in range(segs):
            bm.faces.new((a_[k], a_[(k + 1) % segs], b_[(k + 1) % segs], b_[k]))
    for ring, zc in ((rings[0], prof[0][0]), (rings[-1], prof[-1][0])):
        c = bm.verts.new((0, 0, zc))
        for k in range(segs):
            bm.faces.new((ring[k], ring[(k + 1) % segs], c))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    body = G.mesh_obj("body", bm, M(colour))
    G.finish(body, 0)
    # the eye lugs: a flat moulded tab with a rounded end and a hole through it (hole axis along Y)
    lugs = []
    for zend, sgn in ((length, 1), (0.0, -1)):
        tab = G.prism(f"lug{sgn}", G.rrect(0.040, 0.020, 0.008), 0, eye_len + 0.012, M(colour), taper=0.85)
        if sgn < 0:
            tab.data.transform(Matrix.Rotation(math.pi, 4, "X"))
        tab.location = (0, 0, zend - sgn * (eye_len + 0.012))
        G.bake_xform(tab)
        zh = zend - sgn * 0.017
        G.boolean(tab, G.cyl("hole", (0, -0.03, zh), (0, 0.03, zh), 0.009, None, 24))
        G.finish(tab, 0.003, segs=2)
        lugs.append(tab)
    # the inflation valve: a small cap on the top shoulder
    zv = length - eye_len - 0.06
    rv = dict(prof)[min(dict(prof), key=lambda z: abs(z - zv))]
    valve = G.cyl("valve", (rv - 0.002, 0, zv), (rv + 0.006, 0, zv), 0.0055, M(colour), 16)
    G.finish(valve, 0.001, segs=1)
    objs = [body] + lugs + [valve]
    ob = done("Fender", objs, [("Top", (0, 0, length - 0.017)), ("Bottom", (0, 0, 0.017))])
    # hangs from the top eye: origin at its hole
    ob.data.transform(Matrix.Translation((0, 0, -(length - 0.017))))
    for c in ob.children:
        c.location.z -= length - 0.017
    return ob


# ------------------------------------------------------------------ dock line ends

@part("DockLineEye", "loose", "3/8 in three-strand dock line end with a 12 in soft eye splice (five tucks)")
def dock_line_eye(d=LINE_D, eye=0.305, standing=0.6, slot="Rope"):
    sp = RW.eye_splice(d, eye, 0.13, standing)
    objs = rope_objs("eye", sp["eye"], d, slot)
    objs += rope_objs("strand", sp["standing"], d, slot, swell=(0.0, sp["splice"]))
    objs += splice_objs("tuck", sp["standing"], sp["splice"], d, slot)
    return done("DockLineEye", objs, [("Throat", (0, 0, d / 2)), ("Crown", (eye, 0, d / 2)), ("Standing", (-standing, 0, d / 2))])


@part("CleatHitch", "loose", "3/8 in dock line made fast on a 10 in dock cleat: turn, figure eight, locking hitch")
def cleat_hitch(d=LINE_D, cleat="dock", lead=(0.35, -1.0), slot="Rope"):
    c = DOCK_CLEAT if cleat == "dock" else BOW_CLEAT
    path = RW.cleat_hitch(c["L"], d, lead, c["h_under"], c["h_top"], c["half_w"], c["foot_x"])
    objs = rope_objs("strand", path, d, slot)
    return done("CleatHitch", objs, [("Lead", tuple(path[0]))])


@part("EyeOnCleat", "loose", "Dock line eye dropped round a 130 mm horn cleat, under both horns")
def eye_on_cleat(d=LINE_D, cleat="bow", lead=(0.3, -1.0), slot="Rope", standing=0.5):
    c = BOW_CLEAT if cleat == "bow" else DOCK_CLEAT
    loop, throat = RW.eye_on_cleat(c["L"], d, lead, under=d / 2 + 0.001)
    ld = Vector((lead[0], lead[1], 0)).normalized()
    stand = RW.smooth([throat, throat + ld * 0.06, throat + ld * standing + Vector((0, 0, 0.05))], d * 0.4)
    splice = 5 * 3.3 * d
    objs = rope_objs("eye", loop, d, slot) + rope_objs("standing", stand, d, slot, swell=(0.0, splice))
    objs += splice_objs("tuck", stand, splice, d, slot)
    return done("EyeOnCleat", objs, [("Throat", tuple(throat)), ("Standing", tuple(stand[-1]))])
