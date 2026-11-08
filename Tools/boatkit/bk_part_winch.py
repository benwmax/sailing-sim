"""Winch16 and WinchPlain: the kit's two kinds of winch (part detail loop, Nov 2026: docs/part-detail-loop/winch.md).

Winch16 follows Bean's reference photo of a modern self-tailer: a wide base, a bell flaring up into the drum, a black
self-tailing ring with ribbed jaws, a polished stripper arm reaching over the jaws and down the side, a glossy black
sloped cap with the handle socket set down in it. Sizes are the catalogue size 16 self-tailer's: 121 mm base, 65.7 mm
drum, 145.5 mm tall. WinchPlain is the same family without the self-tailer (a black flange stops the line instead):
size 6 is the plain-top retailers list for the J/22 (90 mm base, 60 mm drum, 82 mm tall), size 16 the standard
two-speed (120 mm base, 112 mm tall). Bean (Nov 8): keep both kinds so boats can differ.

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
    body = G.lathe("drum", prof, al, 64)
    G.finish(body, 0.0, sharp=40)
    # --- the self-tailer: the jaws' V groove, the ribbed outer band, the dark top rising to the cap
    T = [(0.0, 0.1030 * s), (0.0395 * s, 0.1030 * s), (0.0480 * s, 0.1036 * s),       # lower jaw's lip
         (0.0470 * s, 0.1044 * s), (0.0385 * s, 0.1092 * s), (0.0375 * s, 0.1100 * s),   # the open V groove the line is gripped in
         (0.0385 * s, 0.1108 * s), (0.0490 * s, 0.1150 * s), (0.0508 * s, 0.1162 * s),   # up to the upper jaw's lip
         (0.0510 * s, 0.1222 * s)]                                                       # the ribbed, lettered outer band
    T += _fillet((0.0480 * s, 0.1222 * s), 0.0030 * s, 0.0030 * s, 0, 90, 3)
    T += [(0.0400 * s, 0.1290 * s), (0.0335 * s, 0.1310 * s), (0.0305 * s, 0.1314 * s)]   # the top sloping up inward
    # the cap (Bean, round 4): a black cone rising steeply from a short rim inside the stripper's crescent to the socket,
    # which sits down in it nearly flush; open in the middle for the socket
    T += [(0.0302 * s, 0.1348 * s), (0.0296 * s, 0.1356 * s), (0.0284 * s, 0.1360 * s), (0.0200 * s, 0.1408 * s),
          (0.0150 * s, 0.1432 * s), (0.0128 * s, 0.1438 * s), (0.0126 * s, 0.1330 * s), (0.0, 0.1330 * s)]
    jaws = G.lathe("tailer", T, bp, 120)
    panel = (-math.pi / 2 + math.radians(40), math.radians(17))          # the smooth panel the lettering sits on
    _ribs(jaws, 0.1164 * s, 0.1220 * s, 60, 0.0008 * s, 0.050 * s, panel)
    _ribs(jaws, 0.1223 * s, 0.1290 * s, 60, 0.0004 * s, 0.040 * s, panel)    # and over the rounded rim onto the top's edge
    G.finish(jaws, 0.0, sharp=40)
    # --- the handle socket: a polished boss with a ten-point star hole
    # the socket set down in the cap: a polished ring standing about 1.5 mm proud of the cap, a deep star hole
    boss = G.lathe("socket", [(0.0, 0.1330 * s), (0.0125 * s, 0.1330 * s), (0.0125 * s, 0.1446 * s), (0.0119 * s, 0.1453 * s),
                              (0.0105 * s, 0.1455 * s), (0.0, 0.1455 * s)], ss, 30)
    G.boolean(boss, _star("star", 0.0082 * s, 0.0066 * s, 0.1345 * s, 0.1470 * s, 10))
    G.finish(boss, 0.0, sharp=40)
    floor = G.lathe("socketfloor", [(0.0, 0.1346 * s), (0.008 * s, 0.1346 * s), (0.008 * s, 0.1347 * s), (0.0, 0.1347 * s)], bp, 20)
    G.finish(floor, 0.0)
    # --- the stripper arm: a polished crescent round the cap, its arm out over the jaws and down the side, the tip
    # curling in under the jaws (it lifts the tail out of the groove)
    arm_a = -math.pi / 2                                   # the arm on -Y
    span = math.radians(300)
    w_in, w_out = 0.0304 * s, 0.0385 * s
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
    rz = [(0.0335 * s, zc + 0.0009 * s), (0.040 * s, 0.1302 * s), (0.0475 * s, 0.1270 * s)]
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


# Plain-top (non-self-tailing) winches by catalogue size: base radius, drum radius, height (metres) and the heights
# where the base's straight side ends, the bell meets the drum and the drum meets its top flare. Size 6 is the plain-top
# retailers list for the J/22 (90 mm base, 60 mm drum, 82 mm tall); size 16 the standard two-speed (120 mm base,
# 112 mm tall, the size 16 self-tailer's 65.7 mm drum).
_PLAIN = {
    "6": dict(R=0.045, rd=0.030, H=0.082, zb=0.019, zbell=0.031, zd=0.060),
    "16": dict(R=0.060, rd=0.03285, H=0.112, zb=0.031, zbell=0.054, zd=0.087),
}


def _plain_top(R, rd, H, zb, zbell, zd):
    """A plain-top winch in the self-tailer's family: the same turned base, bell and drum (the drum with fine grip ribs,
    as plain drums have), flaring at the top into a black flange that stops the line riding off, then the same black
    sloped cap with the handle socket set down in it."""
    al, bp, ss = P.M("Aluminium"), P.M("BlackPlastic"), P.M("Stainless")
    k = R / 0.0605                                       # detail sizes scale with the base
    # --- base and drum: plinth line, soft shoulder, concave bell, a faint waist, the flare up to the flange
    prof = [(0.0, 0.0), (R - 0.0025 * k, 0.0)] + _fillet((R - 0.0025 * k, 0.0025 * k), 0.0025 * k, 0.0025 * k, -90, 0, 3)
    prof += [(R, 0.0085 * k), (R - 0.0008 * k, 0.0095 * k), (R - 0.0008 * k, 0.0115 * k), (R, 0.0125 * k), (R, zb)]
    sh = 0.004 * k
    prof += _fillet((R - sh, zb), sh, sh, 0, 90, 4)
    n_base = len(prof)                                   # the base (black composite, as small plain-tops have) ends here
    bh = zbell - zb - sh
    for i in range(1, 9):
        t = math.radians(90 * i / 8)
        prof.append(((R - sh) - (R - sh - rd) * math.sin(t), zb + sh + bh - bh * math.cos(t)))
    fl = 0.006 * k                                      # the top flare's radius
    prof += [(rd - 0.0004 * k, (zbell + zd) / 2), (rd, zd)]
    prof += _fillet((rd + fl, zd), fl, fl, 180, 115, 4)
    zf = zd + fl * math.sin(math.radians(115)) + 0.0010 * k
    rf = rd + 0.0105 * k                                # the flange's radius (the line's stop)
    prof += [(rf - 0.0010 * k, zf), (0.0, zf)]
    zs = prof[n_base - 1][1]
    base = G.lathe("base", prof[:n_base] + [(0.0, zs)], bp, 64)
    G.finish(base, 0.0, sharp=40)
    body = G.lathe("drum", [(0.0, zs - 0.0005 * k), (prof[n_base - 1][0] - 0.0004 * k, zs - 0.0005 * k)] + prof[n_base:], al, 96)
    _ribs(body, zbell + 0.003 * k, zd - 0.002 * k, 48, 0.0006 * k, rd * 0.9)    # the drum's grip ribs
    G.finish(body, 0.0, sharp=40)
    # --- the black flange and sloped cap, the socket set down in it
    zc = H - 0.0017 * k                                 # the cap's peak, the socket ring standing about 1.5 mm proud
    rc = 0.0300 * k                                     # the cap's foot
    rs = 0.0125 * k                                     # the socket ring
    # a rolled rim: a chamfer underneath, a deep band for the lettering, a rounded top edge
    T = [(0.0, zf), (rf - 0.0020 * k, zf), (rf + 0.0006 * k, zf + 0.0022 * k), (rf + 0.0008 * k, zf + 0.0080 * k)]
    T += _fillet((rf - 0.0027 * k, zf + 0.0080 * k), 0.0035 * k, 0.0035 * k, 0, 90, 4)
    zt = zf + 0.0115 * k                                # the flange's top face
    T += [(rc + 0.0010 * k, zt), (rc, zt + 0.0005 * k), (rc - 0.0012 * k, zt + 0.0012 * k)]
    T += [(0.0200 * k, zc - 0.0030 * k), (0.0150 * k, zc - 0.0006 * k), (rs + 0.0003 * k, zc), (rs + 0.0001 * k, zc - 0.010 * k),
          (0.0, zc - 0.010 * k)]
    top = G.lathe("flange", T, bp, 96)
    G.finish(top, 0.0, sharp=40)
    boss = G.lathe("socket", [(0.0, zc - 0.011 * k), (rs, zc - 0.011 * k), (rs, H - 0.0009 * k), (rs - 0.0006 * k, H - 0.0002 * k),
                              (rs - 0.0020 * k, H), (0.0, H)], ss, 30)
    G.boolean(boss, _star("star", 0.0082 * k, 0.0066 * k, zc - 0.0095 * k, H + 0.002, 10))
    G.finish(boss, 0.0, sharp=40)
    floor = G.lathe("socketfloor", [(0.0, zc - 0.0094 * k), (0.008 * k, zc - 0.0094 * k), (0.008 * k, zc - 0.0093 * k),
                                    (0.0, zc - 0.0093 * k)], bp, 20)
    G.finish(floor, 0.0)
    mark = _band_letters("lettering", _LETTERS, 0.0042 * k, rf + 0.0008 * k, zf + 0.0052 * k, -math.pi / 2, bp)
    socks = [("Drum", (0, rd, (zbell + zd) / 2)), ("Handle", (0, 0, H)), ("Tail", (0, -rd, (zbell + zd) / 2))]
    return [base, body, top, boss, floor, mark], socks


@P.part("Winch16", "winch", "Size 16 self-tailing winch (121 mm base, 145 mm tall): bell base, drum, ribbed self-tailer, "
        "stripper arm, black sloped cap with the handle socket set in it")
def winch16(scale=1.0):
    return P.done("Winch16", *_self_tailer(scale))


@P.part("WinchPlain", "winch", "Plain-top (non-self-tailing) winch, size 6 (90 mm base, 82 mm tall; the J/22's): the self-tailer's "
        "base, bell and drum with grip ribs, a black flange and sloped cap with the handle socket set in it; size 16 option")
def winch_plain(size="6", scale=1.0):
    d = dict(_PLAIN[size])
    if scale != 1.0:
        d = {key: v * scale for key, v in d.items()}
    objs, socks = _plain_top(**d)
    return P.done("WinchPlain", objs, socks)


# Sizes by catalogue base diameter.
P.SIZES["Winch16"] = {"dim": "winch size (self-tailers 8 / 16 / 20 / 30 / 40: 102 / 121 / 130 / 152 / 175 mm base)",
                      "default": "16",
                      "kw": {"8": {"scale": 102 / 121}, "16": {}, "20": {"scale": 130 / 121},
                             "30": {"scale": 152 / 121}, "40": {"scale": 175 / 121}}}
P.SIZES["WinchPlain"] = {"dim": "winch size (plain-tops 6 / 8 / 16: 90 / 102 / 120 mm base)", "default": "6",
                         "kw": {"6": {}, "8": {"size": "16", "scale": 102 / 120}, "16": {"size": "16"}}}
