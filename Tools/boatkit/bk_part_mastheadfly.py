"""MastheadFly: the wind indicator on top of the mast (part detail loop, Nov 8 2026: docs/part-detail-loop/mastheadfly.md).

The common keelboat masthead fly (the "Windex" type, a trademark we don't use): a black plastic socket screwed to the
masthead, a thin stainless stalk, a vane that turns on a bearing at the top of the stalk (a pointer arm with an arrow
and a counterweight forward, a tall swept fin aft with red and white reflective panels on both sides), and under it two
fixed reference tabs on wire arms, set aft at the boat's close-hauled angle, so the helm can see when the vane lines up
with one of them. Sized from the catalogues' 15 in (381 mm) vane for boats of about 20 to 40 ft (the J/22's size),
12.75 in (324 mm) tall; size "10" is the 10 in (254 mm, about 240 mm tall) dinghy model.

Frame: the origin is the centre of the socket's foot on the masthead's top plate, +Z up. The vane is drawn pointing
forward (+X, into a wind from dead ahead) and the tabs reach aft (-X) either side, so the render loop's square-on side
view (looking along Y) shows the vane's whole profile. The vane turns about the stalk (the Pivot socket); the game turns
its own vane to the apparent wind, so the kit also has the vane alone (MastheadFlyVane, origin at the pivot) and the
fixed part alone (MastheadFlyMount) for that.

Sockets: Mount (the foot), Pivot (the bearing, top of the stalk, on the arm's line), VaneTip (the arrow's point),
TabL / TabR (the reference tabs' centres; L is port, +Y, when the vane points forward).

It lives in its own file so threads working on other parts don't touch the same lines: bk_parts imports every
bk_part_*.py at its end.
"""
import math

from mathutils import Matrix, Vector

import bk_geom as G
import bk_parts as P

# mm, the 15 in model. Catalogue: vane 381 long, 324 tall overall. The rest is read off photos (proportions only).
VANE_FWD = 118.0         # arrow tip ahead of the pivot
VANE_AFT = 263.0         # fin's trailing edge behind the pivot (VANE_FWD + VANE_AFT = 381)
ARM_Z = 230.0            # the arm's centreline above the foot
STALK_R = 2.4            # 3/16 in stainless rod
TAB_Z = 180.0            # the tab collar on the stalk, under the vane with room for the tabs to read clear of its arm
TAB_ANG = 34.0           # each arm's angle off the centreline aft (set for close hauled; bent to suit the boat)
TAB_LEN = 140.0          # collar to tab centre
FIN = [(-138.0, -5.0), (-228.0, 92.0), (-263.0, 94.0), (-263.0, -5.0)]   # (x, z above the arm), long swept leading edge
FIN_T = 2.2


def _mm(*v):
    return tuple(x / 1000.0 for x in v)


def _xz_prism(name, outline_xz, half_t, mat):
    """Extrude an XZ outline (mm) from y = -half_t to +half_t (mm)."""
    o = G.prism(name, [(x / 1000, z / 1000) for x, z in outline_xz], -half_t / 1000, half_t / 1000, mat)
    o.data.transform(Matrix.Rotation(math.radians(90), 4, "X"))   # (x, y, z) -> (x, -z, y): the outline's y becomes Z
    return o


def _inset(poly, d):
    """Shrink a convex polygon (mm) by moving each edge in by d."""
    n = len(poly)
    cx = sum(p[0] for p in poly) / n
    cz = sum(p[1] for p in poly) / n
    out = []
    for i in range(n):
        p = Vector(poly[i])
        to_c = (Vector((cx, cz)) - p)
        out.append(tuple(p + to_c.normalized() * d * 1.4))
    return out


def _vane(sx=1.0, sz=1.0, z0=ARM_Z):
    """The turning part, drawn about the pivot at (0, 0, z0) mm with the arrow along +X."""
    blk, red, wht, ss = P.M("BlackPlastic"), P.M("RedPlastic"), P.M("WhitePlastic"), P.M("Stainless")
    objs = []
    # the bearing housing: a black cap over the stalk's top, the arm passing through its head
    hub = G.lathe("hub", [(0, -16 * sz), (5.2, -16 * sz), (5.6, -12 * sz), (5.6, 3.0), (4.8, 6.0), (2.5, 7.2), (0, 7.4)],
                  blk, 28)
    hub.data.transform(Matrix.Scale(0.001, 4))
    hub.location = _mm(0, 0, z0)
    G.bake_xform(hub)
    objs.append(G.finish(hub, 0.0006, segs=2))
    # the arm: a moulded spar, oval (taller than wide), thick at the hub and slimmer toward both ends
    xs = [VANE_FWD * sx - 24, 40, 0, -60, -150 * sx, (-VANE_AFT + 6) * sx]
    path = [_mm(x, 0, z0) for x in xs]
    sec = [(u / 1000, v / 1000) for u, v in G.ellipse(2.1, 3.0, 12)]
    arm = G.sweep("arm", path, sec, blk, radii=[0.8, 1.0, 1.15, 1.0, 0.9, 0.85], twist_up=(0, 0, 1))
    objs.append(G.finish(arm, 0))
    # counterweight: a teardrop moulded on the arm behind the arrow
    cw = G.lathe("counterweight", [(0, 0), (4.0, 3), (6.6, 12), (6.8, 20), (5.0, 30), (2.6, 36), (0, 38)], blk, 24)
    cw.data.transform(Matrix.Scale(0.001, 4))
    cw.matrix_world = G.along(_mm(VANE_FWD * sx - 62, 0, z0), (1, 0, 0))
    G.bake_xform(cw)
    objs.append(G.finish(cw, 0))
    # the arrow: a flat, barbed head on the arm's tip, red reflector inlays both sides
    tip = VANE_FWD * sx
    head = [(tip, 0), (tip - 26, 11.5), (tip - 21, 3.0), (tip - 30, 3.0), (tip - 30, -3.0), (tip - 21, -3.0), (tip - 26, -11.5)]
    ar = _xz_prism("arrow", [(x, z0 + z) for x, z in head], 1.1, blk)
    objs.append(G.finish(ar, 0.0004, segs=1))
    for s in (-1, 1):
        inl = _xz_prism(f"arrow_reflector{s}", [(x, z0 + z) for x, z in ((tip - 5, 0), (tip - 22, 8.0), (tip - 19, 0), (tip - 22, -8.0))],
                        0.15, red)
        inl.location.y = s * 1.2 / 1000
        objs.append(G.bake_xform(inl))
    # the fin: a swept plate with a raised rim, its root moulded round the arm; reflective panels both sides, red
    # forward and below the diagonal, white aft and above it
    fin = [(x * sx, z * sz) for x, z in FIN]
    f = _xz_prism("fin", [(x, z0 + z) for x, z in fin], FIN_T / 2, blk)
    objs.append(G.finish(f, 0.0007, segs=2))
    root = _xz_prism("fin_root", [(x, z0 + z) for x, z in ((-140 * sx, -5.5), (-150 * sx, 6), (-263 * sx, 6), (-263 * sx, -5.5))], 2.6, blk)
    objs.append(G.finish(root, 0.0012, segs=3))
    # reflective film inside the rim: a red triangle low and forward, a white strip along the top aft; the rest of the
    # fin stays black (Bean's dock photo: the vane reads dark against the sky)
    a, b, c, d = _inset(fin, 9.0)
    a = (a[0], max(a[1], 9.0))
    d = (d[0], max(d[1], 9.0))
    up = (a[0] + (b[0] - a[0]) * 0.62, a[1] + (b[1] - a[1]) * 0.62)      # 62% up the leading edge
    red_tri = [a, up, (a[0] - 52 * sx, a[1])]
    top_z = b[1]
    wstrip = [(b[0] - 4 * sx, top_z), (c[0], top_z), (c[0], top_z - 16 * sz), (b[0] - 14 * sx, top_z - 16 * sz)]
    for s in (-1, 1):
        for nm, poly, mat in (("fin_reflector_red", red_tri, red), ("fin_reflector_white", wstrip, wht)):
            p = _xz_prism(f"{nm}{s}", [(x, z0 + z) for x, z in poly], 0.12, mat)
            p.location.y = s * (FIN_T / 2 + 0.1) / 1000
            objs.append(G.bake_xform(p))
    # the pivot pin's stainless tip showing through the cap
    objs.append(G.cyl("pin", _mm(0, 0, z0 + 7.0), _mm(0, 0, z0 + 8.6), 1.1 / 1000, ss, 12))
    socks = [("Pivot", _mm(0, 0, z0)), ("VaneTip", _mm(tip, 0, z0))]
    return objs, socks


def _mount(sx=1.0, sz=1.0, spike=False):
    """The fixed part: socket, stalk, reference tabs."""
    blk, red, ss = P.M("BlackPlastic"), P.M("RedPlastic"), P.M("Stainless")
    objs = []
    # the socket: a flanged black foot with two screw holes, a tapered boss gripping the stalk, a knurled lock collar
    flange = G.prism("socket_flange", [(x / 1000, y / 1000) for x, y in G.rrect(38, 18, 8.5, 8)], 0, 0.0030, blk)
    G.finish(flange, 0.0008, segs=2)
    for x in (-13.0, 13.0):
        G.boolean(flange, G.cyl("hole", _mm(x, 0, -1), _mm(x, 0, 5), 2.3 / 1000, None, 16))
    objs.append(flange)
    for x in (-13.0, 13.0):
        h = G.lathe("socket_screw", [(0, 0), (3.2, 0), (3.0, 0.8), (2.0, 1.5), (0, 1.6)], ss, 20)
        h.data.transform(Matrix.Scale(0.001, 4))
        h.location = _mm(x, 0, 3.2)
        G.bake_xform(h)
        objs.append(G.finish(h, 0, weighted=False))
    boss = G.lathe("socket", [(0, 3.0), (8.0, 3.0), (7.8, 8.0), (6.4, 36.0), (5.6, 40.0), (0, 40.0)], blk, 28)
    boss.data.transform(Matrix.Scale(0.001, 4))
    objs.append(G.finish(boss, 0.0006, segs=2))
    col = G.lathe("lock_collar", [(0, 22.0), (7.6, 22.0), (7.6, 30.0), (0, 30.0)], blk, 18)   # 18 flats read as knurling
    col.data.transform(Matrix.Scale(0.001, 4))
    objs.append(G.finish(col, 0.0004, segs=1, sharp=15))
    # the stalk: stainless rod from the socket to inside the hub
    top = ARM_Z * sz - 14
    objs.append(G.cyl("stalk", _mm(0, 0, 38), _mm(0, 0, top), STALK_R / 1000, ss, 16))
    # the tab collar and two wire arms aft, each ending in a reflective tab standing on edge
    tz = TAB_Z * sz
    tc = G.lathe("tab_collar", [(0, -7), (5.0, -7), (5.6, -5), (5.6, 5), (5.0, 7), (0, 7)], blk, 20)
    tc.data.transform(Matrix.Scale(0.001, 4))
    tc.location = _mm(0, 0, tz)
    G.bake_xform(tc)
    objs.append(G.finish(tc, 0))
    socks = []
    for s, nm in ((1, "L"), (-1, "R")):
        a = math.radians(180 - TAB_ANG) * s
        d = Vector((math.cos(a), math.sin(a), 0))
        L = TAB_LEN * sx
        p0 = Vector(_mm(0, 0, tz)) + d * 0.004
        p1 = Vector(_mm(0, 0, tz)) + d * (L - 14) / 1000 + Vector(_mm(0, 0, -6))
        mid = p0.lerp(p1, 0.5) + Vector(_mm(0, 0, -1.5))
        objs.append(G.tube(f"tab_arm{nm}", [tuple(p0), tuple(mid), tuple(p1)], 1.3 / 1000, ss, 8))
        cen = Vector(_mm(0, 0, tz)) + d * L / 1000 + Vector(_mm(0, 0, -6))
        plate = [(-14, -9), (14, -9), (14, 6), (8, 9), (-14, 9)]
        t = _xz_prism(f"tab{nm}", plate, 0.7, blk)
        G.finish(t, 0.0003, segs=1)
        ins = _xz_prism(f"tab_reflector{nm}", [(x * 0.8, z * 0.75) for x, z in plate], 0.85, red)
        tt = G.join(f"tab{nm}", [t, ins])
        tt.matrix_world = G.frame(cen, d, (0, 0, 1))
        objs.append(G.bake_xform(tt))
        socks.append((f"Tab{nm}", tuple(cen)))
    if spike:   # an optional bird spike above the cap
        objs.append(G.cyl("spike", _mm(0, 0, ARM_Z * sz + 8), _mm(0, 0, ARM_Z * sz + 240), 0.8 / 1000, ss, 8, r1=0.4 / 1000))
    socks.insert(0, ("Mount", (0.0, 0.0, 0.0)))
    return objs, socks


def _parts(length=0.381, height=0.324, vane=True, mount=True, spike=False):
    sx = length / 0.381
    sz = height / 0.324
    objs, socks = [], []
    if mount:
        o, s = _mount(sx, sz, spike)
        objs += o
        socks += s
    if vane:
        o, s = _vane(sx, sz, ARM_Z * sz)
        objs += o
        socks += s
    return objs, socks


@P.part("MastheadFly", "rigging", "Masthead wind indicator, 15 in (381 mm) vane on a 324 mm stalk: arrow and counterweight, swept fin with reflectors, two reference tabs")
def masthead_fly(length=0.381, height=0.324, spike=False):
    objs, socks = _parts(length, height, spike=spike)
    return P.done("MastheadFly", objs, socks)


masthead_fly.photo_view = (0.55, -1.0, 0.25)     # a dock photo's angle: from abeam, a little forward and below the vane


@P.part("MastheadFlyVane", "rigging", "The masthead fly's turning vane alone, origin at the pivot (the game turns it to the apparent wind)")
def masthead_fly_vane(length=0.381, height=0.324):
    objs, socks = _parts(length, height, mount=False)
    ob = P.done("MastheadFlyVane", objs, [])
    z = ARM_Z * height / 0.324 / 1000
    ob.data.transform(Matrix.Translation((0, 0, -z)))
    for nm, loc in socks:
        G.socket(ob, nm, (loc[0], loc[1], loc[2] - z))
    return ob


@P.part("MastheadFlyMount", "rigging", "The masthead fly's fixed part: socket, stalk and reference tabs (the vane goes on its Pivot socket)")
def masthead_fly_mount(length=0.381, height=0.324, spike=False):
    objs, socks = _parts(length, height, vane=False, spike=spike)
    socks.append(("Pivot", _mm(0, 0, ARM_Z * height / 0.324)))
    return P.done("MastheadFlyMount", objs, socks)


for _n in ("MastheadFly", "MastheadFlyVane", "MastheadFlyMount"):
    P.SIZES[_n] = {"dim": "vane in", "default": "15", "kw": {"10": {"length": 0.254, "height": 0.240}, "15": {}}}
