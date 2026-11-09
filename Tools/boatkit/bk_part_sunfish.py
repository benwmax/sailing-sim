"""Sunfish deck and spar gear (part detail loop, Nov 2026: docs/part-detail-loop/sunfish.md).

From the Sunfish rigging manuals (LaserPerformance and SERO): the upper spar (yard) and the lower boom are joined at
their forward ends by two interlocking eye bolts, the sail's tack is hooked to the boom's eye bolt with an S-hook, and
the mainsheet's blocks hang from eye straps under the lower boom. Spars are 1 1/2 in (38 mm) aluminium tube.

- EyeBolt: a 1/4 in stainless eye bolt through a spar: the forged eye (10 mm hole) on a short neck, a washer on the
  spar's skin and the shank down through the tube to a nylon-insert nut. Origin on the spar's axis, +Z out through the
  eye, the eye's plane along X (its hole along Y). `tube_d` is the spar's diameter (the washer seats on its skin).
- SHook: a 2 in stainless S-hook, wire 4 mm, its two bights in the XZ plane, origin at the upper bight's inside.
- SparStrap: a bent stainless eye strap across a round spar (two screws), the loop standing off the skin with its
  hole along X (a block's shackle pin goes through it). Origin on the spar's axis, +Z out through the loop.

They live in their own file (bk_parts imports every bk_part_*.py) so other threads don't touch the same lines.
"""
import math

from mathutils import Matrix

import bk_geom as G
import bk_parts as P

M = P.M


@P.part("EyeBolt", "fastener", "1/4 in stainless eye bolt through a 38 mm spar: forged eye, washer, acorn nut")
def eye_bolt(tube_d=0.038, eye_r=0.0068, wire=0.0032, neck=0.004):
    steel = M("Stainless")
    rt = tube_d / 2
    objs = []
    ez = rt + neck + eye_r + wire                    # the eye's centre above the spar's axis
    # forged eye: a ring a touch thicker at the neck, as forged eyes are
    ring = G.tube("eye", [(eye_r * math.sin(G.TAU * i / 28), 0, ez - eye_r * math.cos(G.TAU * i / 28)) for i in range(28)], wire, steel, 12,
                  closed=True, radii=[1.0 + 0.18 * max(0.0, math.cos(G.TAU * i / 28)) ** 4 for i in range(28)])
    objs.append(G.finish(ring))
    neckc = G.cyl("neck", (0, 0, rt - 0.0006), (0, 0, ez - eye_r - wire * 0.6), 0.0036, steel, 16, r1=0.0042)
    objs.append(G.finish(neckc, 0.0003))
    # washer bent to the spar's skin (a flat ring sitting on the curve reads right at arm's length)
    washer = G.lathe("washer", [(0.0034, 0), (0.0080, 0), (0.0080, 0.0011), (0.0034, 0.0011)], steel, 24)
    washer.location = (0, 0, rt - 0.0004)
    G.bake_xform(washer)
    objs.append(G.finish(washer, 0.0002, segs=1))
    # shank through the tube and the nut under it
    shank = G.cyl("shank", (0, 0, -rt - 0.007), (0, 0, rt), 0.0031, steel, 12)
    objs.append(G.finish(shank, 0.0003, segs=1))
    nut = G.prism("nut", G.ellipse(0.0063, 0.0063, 6), -rt - 0.0065, -rt - 0.0005, steel)
    objs.append(G.finish(nut, 0.0005, segs=1))
    cap = G.lathe("acorn", [(0, 0), (0.0055, 0), (0.0052, 0.0022), (0.0034, 0.0042), (0, 0.0049)], steel, 20)
    cap.matrix_world = Matrix.Translation((0, 0, -rt - 0.0065)) @ Matrix.Rotation(math.pi, 4, "X")
    G.bake_xform(cap)
    objs.append(G.finish(cap, 0, weighted=False))
    return P.done("EyeBolt", objs, [("Eye", (0, 0, ez)), ("Skin", (0, 0, rt)), ("Nut", (0, 0, -rt - 0.0065))])


@P.part("SHook", "fastener", "2 in stainless S-hook, 4 mm wire, for a sail's tack")
def s_hook(length=0.050, wire=0.002):
    steel = M("Stainless")
    r = length / 4
    pts = G.arc_pts((0, 0, -r), r, math.radians(-60), math.radians(180), 18, "xz")
    pts += G.arc_pts((0, 0, -3 * r), r, math.radians(0), math.radians(-240), 18, "xz")[1:]
    hook = G.tube("hook", pts, wire, steel, 10)
    objs = [G.finish(hook)]
    return P.done("SHook", objs, [("Top", (0, 0, 0)), ("Bottom", (0, 0, -4 * r))])


@P.part("SparStrap", "fastener", "Stainless eye strap across a 38 mm spar, two screws, the loop's hole along X")
def spar_strap(tube_d=0.038, width=0.012):
    """Bent across the spar: its two screwed feet lie on the skin either side (+-Y), the strap follows the curve and
    rises in the middle into a loop whose hole runs along the spar, so a block's shackle pin goes through it lengthwise
    and the block hangs in the line's plane."""
    steel = M("Stainless")
    rt = tube_d / 2
    t = 0.0016
    rs = rt + t / 2
    lr = 0.0055                                       # the loop's inner radius
    a0 = math.radians(58)                             # the feet's ends, from the top of the spar
    a1 = math.asin((lr + 0.002) / rs)                 # where the strap leaves the skin for the loop
    path = [(0, rs * math.sin(-a0 + (a0 - a1) * k / 8), rs * math.cos(-a0 + (a0 - a1) * k / 8)) for k in range(9)]
    zc = rs * math.cos(a1) + lr * 0.55
    path += [(0, (lr + 0.0009) * math.cos(math.pi + math.pi * k / 12 + 0.0), zc - (lr + 0.0009) * math.sin(math.pi + math.pi * k / 12)) for k in range(1, 12)]
    path += [(0, rs * math.sin(a1 + (a0 - a1) * k / 8), rs * math.cos(a1 + (a0 - a1) * k / 8)) for k in range(9)]
    bar = G.sweep("loop", path, [(-t / 2, -width / 2), (t / 2, -width / 2), (t / 2, width / 2), (-t / 2, width / 2)], steel, twist_up=(1, 0, 0))
    objs = [G.finish(bar, 0.0003, segs=1)]
    for sy in (-1, 1):
        a = sy * (a0 - math.radians(14))
        head = G.lathe(f"screw{sy}", [(0, 0), (0.0026, 0), (0.0022, 0.0009), (0.0012, 0.0013), (0, 0.0014)], steel, 16)
        head.matrix_world = Matrix.Rotation(-a, 4, "X") @ Matrix.Translation((0, 0, rt + t))
        G.bake_xform(head)
        objs.append(G.finish(head, 0, weighted=False))
    return P.done("SparStrap", objs, [("Eye", (0, 0, zc)), ("Skin", (0, 0, rt))])
