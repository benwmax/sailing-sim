"""Padeye: a round stainless pad eye (part detail loop, Nov 2026: docs/part-detail-loop/padeye.md).

A forged or cast round base with four countersunk screw holes and a round-bar loop rising from between them, as in
Bean's hardware reference sheet. The base is 40 mm across (the catalogues' 6 mm round pad eye: 40 mm base, 26 mm tall);
the proportions not in a catalogue (bar thickness, hole spacing, countersink size, plate thickness) are measured on
Bean's photo. Built as one piece: the base turned on a lathe, the loop swept as a round bar with flared feet, fused by a
voxel remesh so the feet get a forging's soft fillets, then cut flat underneath and countersunk.

It lives in its own file so threads working on other parts don't touch the same lines: bk_parts imports every
bk_part_*.py at its end, and the @part below replaces bk_parts' older U-bolt padeye of the same name.
Conventions follow bk_parts: origin at the centre of the underside, +Z up, the loop's plane along X (the line leads
along X), screw holes on the diagonals.
"""
import math

import bpy
from mathutils import Matrix

import bk_geom as G
import bk_parts as P

# fractions of the base diameter D (measured on Bean's photo unless noted)
_ROD = 0.12          # loop bar diameter
_LEG = 0.30          # loop leg centre from the middle (legs land between the screw holes)
_H = 0.65            # overall height (catalogue: 26 mm on a 40 mm base)
_HOLE_R = 0.31       # screw-hole circle radius
_CSK = 0.30          # countersink diameter at the top face
_THRU = 0.12         # through-hole diameter (a No. 8 screw's clearance on the 40 mm size)
_T = 0.12            # plate thickness at the flat
_T_RIM = 0.05        # height of the plate's vertical rim before the rounded edge
_DOME = 0.012        # the top's gentle rise to the middle


def _lettering(name, text, height, radius, z, mat, relief=0.00015):
    """Raised letters centred on -Y at `radius`, each letter turned to follow the circle (reading left to right from
    outside the rim), standing `relief` proud of z."""
    objs = []
    cu = bpy.data.curves.new(f"{name}_font", "FONT")
    cu.size, cu.extrude, cu.align_x, cu.align_y = height, relief, "CENTER", "CENTER"
    widths = []
    for ch in text:                                  # each glyph's advance, measured from a one-letter curve
        cu.body = ch
        tmp = bpy.data.objects.new("glyph", cu)
        bpy.context.scene.collection.objects.link(tmp)
        me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        xs = [v.co.x for v in me.vertices] or [0.0]
        widths.append((max(xs) - min(xs)) if ch != " " else height * 0.4)
        bpy.data.meshes.remove(me)
        bpy.data.objects.remove(tmp, do_unlink=True)
    gap = height * 0.12
    total = sum(widths) + gap * (len(widths) - 1)
    s = -total / 2
    for i, (ch, w) in enumerate(zip(text, widths)):
        x = s + w / 2
        s += w + gap
        if ch == " ":
            continue
        cu.body = ch
        tmp = bpy.data.objects.new("glyph", cu)
        bpy.context.scene.collection.objects.link(tmp)
        me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        bpy.data.objects.remove(tmp, do_unlink=True)
        o = bpy.data.objects.new(f"{name}{i}", me)
        bpy.context.scene.collection.objects.link(o)
        me.materials.append(mat)
        ang = x / radius                              # arc length -> angle round the centre
        o.matrix_world = (Matrix.Rotation(ang, 4, "Z") @ Matrix.Translation((0, -radius, z + relief))
                          @ Matrix.Translation((-(min(v.co.x for v in me.vertices) + max(v.co.x for v in me.vertices)) / 2, 0, 0)))
        G.bake_xform(o)
        objs.append(o)
    bpy.data.curves.remove(cu)
    return G.join(name, objs)


def _padeye_parts(D=0.040, tris=14000, voxel=0.0002):
    ss = P.M("Stainless")
    R, t = D / 2, _T * D
    # base: turned profile (radius, z); vertical rim, a rounded top edge, a near-flat top rising gently to the middle
    rr = t - _T_RIM * D
    prof = [(0.0, -0.002), (R, -0.002), (R, _T_RIM * D)]
    for i in range(1, 9):
        a = math.pi / 2 * i / 8
        prof.append((R - rr + rr * math.cos(a), _T_RIM * D + rr * math.sin(a)))
    prof += [(0.62 * R, t + 0.6 * _DOME * D), (0.30 * R, t + 0.9 * _DOME * D), (0.0, t + _DOME * D)]
    base = G.lathe("base", prof, ss, 96)
    # loop: legs straight up from inside the plate, a half circle over the top; flared feet for the fillets
    a, r = _LEG * D, _ROD * D / 2
    zc = _H * D - a - r
    path = [(-a, 0, t * 0.4), (-a, 0, zc)] + G.arc_pts((0, 0, zc), a, math.pi, 0, 32, "xz")[1:-1] + [(a, 0, zc), (a, 0, t * 0.4)]
    loop = G.tube("loop", path, r, ss, 28)
    feet = [G.cyl(f"foot{s}", (s * a, 0, t - 0.0005), (s * a, 0, t + 0.08 * D), r * 1.5, ss, 32, r1=r) for s in (-1, 1)]
    body = G.join("body", [base, loop] + feet)
    m = body.modifiers.new("fuse", "REMESH")
    m.mode, m.voxel_size, m.adaptivity = "VOXEL", voxel, 0.0
    sm = body.modifiers.new("soften", "SMOOTH")
    sm.factor, sm.iterations = 0.5, 3
    G.apply(body)
    G.boolean(body, G.box("floor", (0, 0, -0.05), (D * 3, D * 3, 0.1)))
    d = body.modifiers.new("budget", "DECIMATE")
    me = body.data
    me.calc_loop_triangles()
    d.ratio = min(1.0, (tris - 4000) / max(1, len(me.loop_triangles)))
    G.apply(body)
    # four countersunk screw holes (cut after the reduction so their cones stay clean) on the diagonals: a steep cone into a through hole
    top = t + 0.004
    cs, th, depth = _CSK * D / 2, _THRU * D / 2, 0.80 * t
    for k in range(4):
        ang = math.radians(45 + 90 * k)
        c = G.lathe(f"csk{k}", [(0.0, -0.002), (th, -0.002), (th, t - depth), (cs, t + 0.0002), (cs, top), (0.0, top)], None, 48)
        c.location = (_HOLE_R * D * math.cos(ang), _HOLE_R * D * math.sin(ang), 0)
        G.bake_xform(c)
        G.boolean(body, c)
    G.finish(body, 0.00025, segs=2, angle=35, sharp=35)    # only the countersinks' rims and the underside edge are sharp
    body.name = "forging"
    # a made-up maker's mark on the top face, toward the front between two holes: small raised letters following the
    # rim (r3's flush plate couldn't be seen; r2's proud plate read as a stuck-on label)
    mark = _lettering("stamp", "TERNWAY", 0.05 * D, 0.37 * D, t + 0.30 * _DOME * D, ss)
    socks = [("Eye", (0, 0, zc + a - r)), ("Base", (0, 0, 0))]
    socks += [(f"Screw{k + 1}", (_HOLE_R * D * math.cos(math.radians(45 + 90 * k)), _HOLE_R * D * math.sin(math.radians(45 + 90 * k)), t - depth))
              for k in range(4)]
    return [body, mark], socks


@P.part("Padeye", "fastener", "Round stainless pad eye, 40 mm base, four countersunk screw holes, round-bar loop (6 mm size)")
def padeye(diameter=0.040):
    return P.done("Padeye", *_padeye_parts(diameter))


P.SIZES["Padeye"] = {"dim": "base diameter mm", "default": "40", "scale": {"33": 0.825, "40": 1.0, "50": 1.25}}
