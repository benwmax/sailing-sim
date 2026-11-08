"""Winch16: a size 16 self-tailing winch, and the J/22's small plain-top winch (part detail loop, Nov 2026:
docs/part-detail-loop/winch.md).

The default build follows Bean's reference photo (a modern self-tailer: a wide base, a bell flaring up into the drum, a
black self-tailing ring with ribbed jaws round a dark top, a polished stripper arm reaching over the jaws and down the
side, a star socket for the handle in the middle). Sizes are the catalogue size 16 self-tailer's: 121 mm base, 65.7 mm
drum, 145.5 mm tall. The `plain` build is the catalogue size 6 plain-top winch (90 mm base, 60 mm drum, 82 mm tall:
the J/22's cabin-top halyard winch on the class layouts): the same family without the self-tailer.

Proportions not in a catalogue (where the bell starts and ends, the jaws' heights, the arm's width) are measured on
Bean's photo (measuring only, not in the repo). It lives in its own file so threads working on other parts don't touch
the same lines: bk_parts imports every bk_part_*.py at its end, and the @part below replaces bk_parts' older Winch16.
Conventions follow bk_parts: origin at the centre of the underside, +Z up; the stripper arm (where the tail leaves) is
on -Y, the side the old part's Tail socket faced.
"""
import math

import bpy
from mathutils import Matrix, Vector

import bk_geom as G
import bk_parts as P

_LETTERS = "TERNWAY"


def _fillet(c, rr, rz, a0, a1, n):
    """Points (r, z) round an ellipse centred c (radii rr, rz) from angle a0 to a1 (degrees), excluding a0."""
    out = []
    for i in range(1, n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        out.append((c[0] + rr * math.cos(a), c[1] + rz * math.sin(a)))
    return out


def _band_letters(name, text, height, radius, z, ang0, mat, relief=0.0003):
    """Raised letters standing on a vertical band of `radius`, centred at angle ang0 (radians, measured from +X),
    reading left to right from outside."""
    cu = bpy.data.curves.new(f"{name}_font", "FONT")
    cu.size, cu.extrude, cu.align_x, cu.align_y = height, relief, "CENTER", "CENTER"

    def glyph(ch):
        cu.body = ch
        tmp = bpy.data.objects.new("glyph", cu)
        bpy.context.scene.collection.objects.link(tmp)
        me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        bpy.data.objects.remove(tmp, do_unlink=True)
        return me

    widths = []
    for ch in text:
        me = glyph(ch)
        xs = [v.co.x for v in me.vertices] or [0.0]
        widths.append((max(xs) - min(xs)) if ch != " " else height * 0.4)
        bpy.data.meshes.remove(me)
    gap = height * 0.35                                  # spaced out, like moulded lettering
    total = sum(widths) + gap * (len(widths) - 1)
    s = -total / 2
    objs = []
    for i, (ch, w) in enumerate(zip(text, widths)):
        x = s + w / 2
        s += w + gap
        if ch == " ":
            continue
        me = glyph(ch)
        cx = (min(v.co.x for v in me.vertices) + max(v.co.x for v in me.vertices)) / 2
        o = bpy.data.objects.new(f"{name}{i}", me)
        bpy.context.scene.collection.objects.link(o)
        me.materials.append(mat)
        # text plane XY, +Z out of the face -> stand it up facing -Y, then wrap it round the band
        a = ang0 + math.pi / 2 + x / radius
        o.matrix_world = (Matrix.Rotation(a, 4, "Z") @ Matrix.Translation((0, -radius + 0.0001, z))
                          @ Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Translation((-cx, 0, 0)))
        G.bake_xform(o)
        objs.append(o)
    bpy.data.curves.remove(cu)
    return G.join(name, objs)


def _ribs(ob, z0, z1, n, depth, r_min, skip=None):
    """Push alternate vertex columns of a lathe out by `depth` between z0 and z1 (radial ribs on a ring's side), leaving
    a smooth panel where `skip` = (centre angle, half width) in radians."""
    for v in ob.data.vertices:
        if z0 < v.co.z < z1:
            r = math.hypot(v.co.x, v.co.y)
            if r < r_min:
                continue
            a = math.atan2(v.co.y, v.co.x)
            if skip and abs((a - skip[0] + math.pi) % (2 * math.pi) - math.pi) < skip[1]:
                continue
            k = 1 + depth / r * max(0.0, math.cos(a * n)) ** 4
            v.co.x *= k
            v.co.y *= k


def _star(name, r_out, r_in, z0, z1, points, mat=None):
    pts = []
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.pi * i / points + math.pi / 2
        pts.append((r * math.cos(a), r * math.sin(a)))
    return G.prism(name, pts, z0, z1, mat)


def _self_tailer(s=1.0):
    al, bp, ss = P.M("Aluminium"), P.M("BlackPlastic"), P.M("Stainless")
    # --- base and drum: one turned profile (radius, z); the base's plinth line, a soft shoulder, a bell into the drum
    R = 0.0605 * s
    prof = [(0.0, 0.0), (R - 0.0025 * s, 0.0)] + _fillet((R - 0.0025 * s, 0.0025 * s), 0.0025 * s, 0.0025 * s, -90, 0, 3)
    prof += [(R, 0.0095 * s), (R - 0.0008 * s, 0.0105 * s), (R - 0.0008 * s, 0.0125 * s), (R, 0.0135 * s), (R, 0.0355 * s)]
    prof += _fillet((R - 0.004 * s, 0.0355 * s), 0.004 * s, 0.004 * s, 0, 90, 4)
    # the bell: a concave quarter from the shoulder's top to the drum's foot
    rd = 0.03285 * s
    bell_c = (R - 0.004 * s, 0.0395 * s + 0.026 * s)
    for i in range(1, 11):
        t = math.radians(90 * i / 10)
        prof.append((bell_c[0] - (bell_c[0] - rd) * math.sin(t), bell_c[1] - 0.026 * s * math.cos(t)))
    # the drum: a faint waist, then the flare up to the lower jaw's lip
    prof += [(rd - 0.0004 * s, 0.079 * s), (rd, 0.091 * s)]
    prof += _fillet((rd + 0.010 * s, 0.091 * s), 0.010 * s, 0.009 * s, 180, 112, 5)
    prof += [(0.0475 * s, 0.1018 * s), (0.0475 * s, 0.1028 * s), (0.0, 0.1028 * s)]
    body = G.lathe("drum", prof, al, 72)
    G.finish(body, 0.0, sharp=40)
    # --- the self-tailer: the jaws' V groove, the ribbed outer band, the dark top rising to the cap
    T = [(0.0, 0.1030 * s), (0.0395 * s, 0.1030 * s), (0.0480 * s, 0.1036 * s),       # lower jaw's lip
         (0.0470 * s, 0.1044 * s), (0.0385 * s, 0.1092 * s), (0.0375 * s, 0.1100 * s),   # the open V groove the line is gripped in
         (0.0385 * s, 0.1108 * s), (0.0490 * s, 0.1150 * s), (0.0508 * s, 0.1162 * s),   # up to the upper jaw's lip
         (0.0510 * s, 0.1222 * s)]                                                       # the ribbed, lettered outer band
    T += _fillet((0.0480 * s, 0.1222 * s), 0.0030 * s, 0.0030 * s, 0, 90, 3)
    T += [(0.0400 * s, 0.1290 * s), (0.0330 * s, 0.1310 * s), (0.0275 * s, 0.1318 * s),   # the top sloping up inward
          (0.0270 * s, 0.1335 * s), (0.0250 * s, 0.1352 * s), (0.0190 * s, 0.1362 * s), (0.0, 0.1364 * s)]   # the cap
    jaws = G.lathe("tailer", T, bp, 120)
    panel = (-math.pi / 2 + math.radians(40), math.radians(17))          # the smooth panel the lettering sits on
    _ribs(jaws, 0.1164 * s, 0.1220 * s, 60, 0.0008 * s, 0.050 * s, panel)
    _ribs(jaws, 0.1223 * s, 0.1290 * s, 60, 0.0004 * s, 0.040 * s, panel)    # and over the rounded rim onto the top's edge
    G.finish(jaws, 0.0, sharp=40)
    # --- the handle socket: a polished boss with a ten-point star hole
    boss = G.lathe("socket", [(0.0, 0.1350 * s), (0.0125 * s, 0.1350 * s), (0.0125 * s, 0.1440 * s), (0.0118 * s, 0.1452 * s),
                              (0.0102 * s, 0.1455 * s), (0.0, 0.1455 * s)], ss, 40)
    G.boolean(boss, _star("star", 0.0078 * s, 0.0062 * s, 0.1300 * s, 0.1470 * s, 10))
    G.finish(boss, 0.0, sharp=40)
    floor = G.lathe("socketfloor", [(0.0, 0.1395 * s), (0.008 * s, 0.1395 * s), (0.008 * s, 0.1396 * s), (0.0, 0.1396 * s)], bp, 20)
    G.finish(floor, 0.0)
    # --- the stripper arm: a polished crescent round the cap, its arm out over the jaws and down the side, the tip
    # curling in under the jaws (it lifts the tail out of the groove)
    arm_a = -math.pi / 2                                   # the arm on -Y
    span = math.radians(300)
    w_in, w_out = 0.0262 * s, 0.0360 * s
    zc = 0.1322 * s
    n = 36
    outline = []
    for i in range(n + 1):
        a = arm_a - math.radians(20) + span * i / n
        outline.append((w_out * math.cos(a), w_out * math.sin(a)))
    for i in range(n, -1, -1):
        a = arm_a - math.radians(20) + span * i / n
        outline.append((w_in * math.cos(a), w_in * math.sin(a)))
    crescent = G.prism("stripper_ring", outline, zc - 0.0004 * s, zc + 0.0030 * s, ss)
    G.finish(crescent, 0.0006 * s, segs=2)
    # the arm in the radial plane at arm_a: (r, z) path, the section 2.4 mm thick and 15 mm wide (tapering to 11)
    rz = [(0.030 * s, zc + 0.0009 * s), (0.040 * s, 0.1302 * s), (0.0475 * s, 0.1270 * s)]
    rz += [(0.0475 * s + 0.0065 * s * math.sin(math.radians(a)), 0.1222 * s + 0.0060 * s * math.cos(math.radians(a))) for a in (25, 50, 75, 90)]
    rz += [(0.0540 * s, 0.1120 * s), (0.0540 * s, 0.1040 * s), (0.0530 * s, 0.0980 * s), (0.0505 * s, 0.0945 * s),
           (0.0470 * s, 0.0932 * s), (0.0440 * s, 0.0945 * s), (0.0425 * s, 0.0975 * s)]
    ca, sa = math.cos(arm_a), math.sin(arm_a)
    path = [(r * ca, r * sa, z) for r, z in rz]
    sec = [(-0.0018 * s, -0.0085 * s), (0.0018 * s, -0.0085 * s), (0.0018 * s, 0.0085 * s), (-0.0018 * s, 0.0085 * s)]
    arm = G.sweep("stripper_arm", path, sec, ss, radii=[1.0] * len(path), twist_up=(-sa, ca, 0))
    # taper the width toward the tip
    for v in arm.data.vertices:
        p = Vector(v.co)
        if p.z < 0.1200 * s:
            k = 0.72 + 0.28 * max(0.0, min(1.0, (p.z - 0.0932 * s) / (0.0250 * s)))
            tang = Vector((-sa, ca, 0))
            off = p.dot(tang)
            p -= tang * off * (1 - k)
            v.co = p
    G.finish(arm, 0.0007 * s, segs=2)
    # --- moulded lettering on the band, beside the arm, and a small size disc on the arm's bend
    mark = _band_letters("lettering", _LETTERS, 0.0042 * s, 0.0511 * s, 0.1192 * s, arm_a + math.radians(40), bp)
    objs = [body, jaws, boss, floor, crescent, arm, mark]
    socks = [("Drum", (0, 0.033 * s, 0.075 * s)), ("Handle", (0, 0, 0.1455 * s)), ("Tail", (0, -0.0540 * s, 0.110 * s)),
             ("Jaws", (0, 0.038 * s, 0.110 * s))]
    return objs, socks


def _plain_top():
    """Catalogue size 6 plain-top: 90 mm composite base, 60 mm drum, 82 mm tall, no self-tailer."""
    al, bp, ss = P.M("Aluminium"), P.M("BlackPlastic"), P.M("Stainless")
    R = 0.045
    base = [(0.0, 0.0), (R - 0.002, 0.0)] + _fillet((R - 0.002, 0.002), 0.002, 0.002, -90, 0, 3)
    base += [(R, 0.012)] + _fillet((R - 0.004, 0.012), 0.004, 0.004, 0, 90, 4)
    rd = 0.030
    bell_c = (R - 0.004, 0.016 + 0.012)
    for i in range(1, 9):
        t = math.radians(90 * i / 8)
        base.append((bell_c[0] - (bell_c[0] - rd - 0.0015) * math.sin(t), bell_c[1] - 0.012 * math.cos(t)))
    base += [(rd + 0.0015, 0.030), (0.0, 0.030)]
    b = G.lathe("base", base, bp, 64)
    G.finish(b, 0.0, sharp=40)
    drum = [(0.0, 0.030), (rd, 0.030), (rd - 0.0004, 0.050), (rd, 0.068)]
    drum += _fillet((rd + 0.006, 0.068), 0.006, 0.006, 180, 110, 4)
    drum += [(0.0365, 0.0745), (0.0365, 0.0755), (0.0, 0.0755)]
    d = G.lathe("drum", drum, al, 64)
    G.finish(d, 0.0, sharp=40)
    top = [(0.0, 0.0755), (0.0360, 0.0755), (0.0362, 0.0775)] + _fillet((0.0342, 0.0775), 0.002, 0.002, 0, 90, 3)
    top += [(0.020, 0.0800), (0.0, 0.0802)]
    t = G.lathe("top", top, bp, 64)
    G.finish(t, 0.0, sharp=40)
    boss = G.lathe("socket", [(0.0, 0.0795), (0.011, 0.0795), (0.011, 0.0815), (0.0095, 0.0820), (0.0, 0.0820)], ss, 40)
    G.boolean(boss, _star("star", 0.0072, 0.0057, 0.0760, 0.0840, 10))
    G.finish(boss, 0.0, sharp=40)
    socks = [("Drum", (0, rd, 0.050)), ("Handle", (0, 0, 0.082)), ("Tail", (0, -rd, 0.060))]
    return [b, d, t, boss], socks


@P.part("Winch16", "winch", "Size 16 self-tailing winch (121 mm base, 145 mm tall): bell base, drum, ribbed self-tailer, "
        "stripper arm, star handle socket; size 6 is the J/22's plain-top")
def winch16(scale=1.0, plain=False):
    objs, socks = _plain_top() if plain else _self_tailer(scale)
    return P.done("Winch16", objs, socks)


# Size by catalogue: base diameter 90 (6, plain-top), 102 (8), 121 (16), 130 (20), 152 (30), 175 (40) mm.
P.SIZES["Winch16"] = {"dim": "winch size (6 plain-top: 90 mm base; self-tailers 8 / 16 / 20 / 30 / 40: 102 / 121 / 130 / 152 / 175 mm)",
                      "default": "16",
                      "kw": {"6": {"plain": True}, "8": {"scale": 102 / 121}, "16": {}, "20": {"scale": 130 / 121},
                             "30": {"scale": 152 / 121}, "40": {"scale": 175 / 121}}}
