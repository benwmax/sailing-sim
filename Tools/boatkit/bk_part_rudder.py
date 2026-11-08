"""Rudder hardware: the J/22's strap gudgeon and strap pintle (part detail loop, Nov 2026: docs/part-detail-loop/rudder.md).

The J/22 hangs its rudder on the transom the way most small keelboats do: on the blade, a pintle (two stainless straps
bolted through both faces of the blade, welded to a block round a barrel at the leading edge); on the transom, strap
gudgeons (a stainless strap wrapped round a bushed eye, its legs bent flat onto the transom and bolted through). Bean's
J/22 photos (tiller-transom-attachemnt, -2) show each pintle between two gudgeon lugs, one above and one below, and a
long pin through all three with its head on top and a keeper underneath. Sizes are the catalogue's J/24-style strap
fittings (Schaefer 81-47 class: 1/2 in pin, 25 x 5 mm strap, four fasteners, for a 1 1/2 in blade) and the hero J/22's
blade (35 to 38 mm thick at the pintles, Inputs/j22-hero/j22_steering.py).

It lives in its own file so threads working on other parts don't touch the same lines: bk_parts imports every
bk_part_*.py at its end, and the @part below replaces bk_parts' older Gudgeon of the same name.

Frames (the old Gudgeon's, so layouts and build_fleet place the new one unchanged): the gudgeon's origin is on the
transom face, +X aft out of the transom, +Z up, and its pin axis (socket Pin) 26 mm aft. The pintle's origin is on its
pin axis at the barrel's middle, the blade running aft along +X; its Lug sockets are where the gudgeons' Pin sockets go.
"""
import math

import bmesh
from mathutils import Matrix, Vector

import bk_geom as G
import bk_parts as P

# ------------------------------------------------------------------ shared sizes (metres)

PIN_R = 0.00635        # 1/2 in pin
BORE_R = 0.0066        # its clearance in the bushes
BUSH_R = 0.0085        # acetal bush outside radius (the strap wraps it)
STRAP_W = 0.025        # gudgeon strap width (catalogue 1 in)
STRAP_T = 0.0040       # and thickness (5/32 in: r2 read chunky as an angle bracket)
PIN_X = 0.026          # the gudgeon's pin axis aft of the transom (the old part's socket, kept)
LUG_Z = 0.028          # each gudgeon lug's centre above / below the pintle's middle
BARREL_H = 0.029       # the pintle's block height between the lugs (1 mm bush lip each side)


def _hex(name, p, axis, af, h, mat, washer=True):
    """A hex bolt head or nut, `af` across flats and `h` high, on a washer, standing out of p along axis."""
    axis = Vector(axis).normalized()
    p = Vector(p)
    out = []
    if washer:
        w = G.lathe(name + "_wsh", [(0.0, 0.0), (af * 0.85, 0.0), (af * 0.85, 0.0011), (af * 0.80, 0.0015), (0.0, 0.0014)], mat, 24)
        w.matrix_world = G.along(p, axis)
        G.bake_xform(w)
        out.append(G.finish(w, 0))
        p = p + axis * 0.0015
    r = af / math.sqrt(3)
    hx = G.lathe(name, [(0.0, 0.0), (r, 0.0), (r, h - 0.0012), (af * 0.45, h), (0.0, h)], mat, 6)
    hx.matrix_world = G.along(p, axis) @ Matrix.Rotation(math.radians(30), 4, "Z")
    G.bake_xform(hx)
    out.append(G.finish(hx, 0.0003, segs=1))
    return out, p + axis * h


def _nylock(name, p, axis, af, mat):
    """A nylon-insert lock nut on a washer with the bolt's thread end standing proud."""
    axis = Vector(axis).normalized()
    out, top = _hex(name, p, axis, af, af * 0.5, mat)
    ins = G.lathe(name + "_ins", [(af * 0.48, 0.0), (af * 0.44, af * 0.22), (af * 0.30, af * 0.26), (0.0, af * 0.26)], P.M("BlackPlastic"), 20)
    ins.matrix_world = G.along(top, axis)
    G.bake_xform(ins)
    out.append(G.finish(ins, 0))
    thd = G.lathe(name + "_thd", [(0.0, 0.0), (af * 0.30, 0.0), (af * 0.30, af * 0.36), (af * 0.25, af * 0.40), (0.0, af * 0.40)], mat, 16)
    thd.matrix_world = G.along(top, axis)
    G.bake_xform(thd)
    out.append(G.finish(thd, 0))
    return out


def _bush(name, zc, h, mat):
    """A flanged acetal bush on the pin axis: its sleeve h tall about zc, a thin lip at each end."""
    hh = h / 2
    prof = [(BORE_R, zc - hh - 0.001), (BUSH_R + 0.002, zc - hh - 0.001), (BUSH_R + 0.002, zc - hh), (BUSH_R, zc - hh),
            (BUSH_R, zc + hh), (BUSH_R + 0.002, zc + hh), (BUSH_R + 0.002, zc + hh + 0.001), (BORE_R, zc + hh + 0.001),
            (BORE_R, zc - hh - 0.001)]
    return G.finish(G.lathe(name, prof, mat, 32), 0)


# ------------------------------------------------------------------ gudgeon

def _gudgeon_parts(flange=0.072, offset=PIN_X):
    ss = P.M("Stainless")
    t, w = STRAP_T, STRAP_W
    rm = BUSH_R + t / 2                   # the strap's mid line round the eye
    xf = t / 2                            # the flanges' mid line, lying on the transom
    rb = 0.005                            # the bends at the transom
    objs = []
    # one strap: flange end, bend, leg aft, round the eye, leg forward, bend, flange end (its mid line, swept)
    path = [(xf, -flange + w / 2, 0.0), (xf, -(rm + rb), 0.0)]
    path += [(xf + rb - rb * math.cos(a), -(rm + rb) + rb * math.sin(a), 0.0) for a in [math.pi / 2 * k / 6 for k in range(1, 7)]]
    path += [(offset, -rm, 0.0)]
    path += [(offset + rm * math.sin(a), -rm * math.cos(a), 0.0) for a in [math.pi * k / 20 for k in range(1, 20)]]
    path += [(offset, rm, 0.0), (xf + rb, rm, 0.0)]
    path += [(xf + rb - rb * math.sin(a), rm + rb - rb * math.cos(a), 0.0) for a in [math.pi / 2 * k / 6 for k in range(1, 7)]]
    path += [(xf, flange - w / 2, 0.0)]
    sec = [(u, v) for u, v in G.rrect(t, w, 0.0016, 3)]
    strap = G.sweep("strap", path, sec, ss)
    objs.append(G.finish(strap, 0))
    # the flanges' round ends (the strap's full width as a half disc)
    for s in (-1, 1):
        end = G.lathe(f"strap_end{s}", [(0.0, -t / 2), (w / 2 - 0.0012, -t / 2), (w / 2, -t / 2 + 0.0012), (w / 2, t / 2 - 0.0012),
                                         (w / 2 - 0.0012, t / 2), (0.0, t / 2)], ss, 32, arc=math.pi)
        # half disc in the transom's plane (local XY of the lathe -> world YZ), facing outboard
        # lathe X -> up, lathe Y (the half disc) -> outboard, lathe Z (thickness) -> along the transom normal
        end.matrix_world = Matrix(((0, 0, -s, xf), (0, s, 0, s * (flange - w / 2)), (1, 0, 0, 0), (0, 0, 0, 1)))
        G.bake_xform(end)
        objs.append(G.finish(end, 0))
    # the bush in the eye
    b = _bush("bush", 0.0, w, P.M("BlackPlastic"))
    b.location = (offset, 0, 0)
    G.bake_xform(b)
    objs.append(b)
    # two hex bolts through each flange (M6), heads aft
    bolts = []
    for s in (-1, 1):
        for k, y in enumerate((0.034, flange - w / 2)):
            o, _ = _hex(f"bolt{s}{k}", (t, s * y, 0.0), (1, 0, 0), 0.011, 0.0058, ss)
            objs += o
            bolts.append((f"Bolt{len(bolts) + 1}", (t, s * y, 0.0)))
    return objs, [("Pin", (offset, 0, 0))] + bolts


@P.part("Gudgeon", "steering", "Stainless strap gudgeon for a transom-hung rudder: 25 x 5 mm strap round a bushed eye for a 1/2 in pin, flanges bolted to the transom")
def gudgeon(flange=0.072, offset=PIN_X):
    """`offset`: the pin's axis aft of the transom (26 mm by default, the old part's; the J/22's is 50 mm)."""
    return P.done("Gudgeon", *_gudgeon_parts(flange, offset))


# ------------------------------------------------------------------ pintle

def _naca_half(x, chord, t):
    """Half thickness of a NACA 00xx section at x aft of the leading edge."""
    u = min(max(x / chord, 0.0), 1.0)
    return 5 * t * chord * (0.2969 * math.sqrt(u) - 0.1260 * u - 0.3516 * u * u + 0.2843 * u ** 3 - 0.1036 * u ** 4)


def _pintle_parts(blade=0.036, chord=0.35, length=0.27, le=0.016):
    ss = P.M("Stainless")
    t_ratio = blade / chord
    th, hw = 0.003, 0.015                 # strap thickness and half width (Bean's photos: 30 mm flat bar)
    x0 = le + 0.020                       # the straps leave the block here
    x1 = length                           # to the start of their round ends
    hb = lambda x: _naca_half(x - le, chord, t_ratio) + 0.0002
    objs = []
    # the block round the barrel: a rounded nose ahead of the pin, its sides closing in on the blade aft
    # r3: a round barrel on the pin (r2's square block read as a door hinge to a reviewer), a tapered neck aft
    # joining it to the straps
    xa = x0 + 0.004
    side = hb(xa) + th
    br = 0.0125
    barrel = G.lathe("block", [(BORE_R, -BARREL_H / 2), (br - 0.0012, -BARREL_H / 2), (br, -BARREL_H / 2 + 0.0012), (br, BARREL_H / 2 - 0.0012),
                               (br - 0.0012, BARREL_H / 2), (BORE_R, BARREL_H / 2), (BORE_R, -BARREL_H / 2)], ss, 40)
    objs.append(G.finish(barrel, 0))
    neck_out = [(br * 0.55, -br * 0.92), (xa, -side), (xa, side), (br * 0.55, br * 0.92)]
    neck = G.prism("neck", neck_out, -hw * 0.95, hw * 0.95, ss)
    objs.append(G.finish(neck, 0.0016, segs=3, angle=30))
    # its bushes' lips top and bottom
    for s in (-1, 1):
        lip = G.lathe(f"bushlip{s}", [(BORE_R, 0.0), (BUSH_R + 0.002, 0.0), (BUSH_R + 0.002, 0.001), (BORE_R, 0.001), (BORE_R, 0.0)], P.M("BlackPlastic"), 32)
        lip.location = (0, 0, BARREL_H / 2 if s > 0 else -BARREL_H / 2 - 0.001)
        G.bake_xform(lip)
        objs.append(G.finish(lip, 0))
    # the two straps, lying on the blade's faces, round-ended aft
    xs = [x0 + (x1 - x0) * k / 24 for k in range(25)] + [x1 + hw * math.sin(math.pi / 2 * k / 8) for k in range(1, 9)]
    for s in (-1, 1):
        bm = bmesh.new()
        rings = []
        e = 0.0008                        # eased edges
        for x in xs:
            taper = 1.0 if x <= x1 else math.sqrt(max(1 - ((x - x1) / hw) ** 2, 0.0))
            z = hw * max(taper, 0.06)
            y0 = s * hb(x)
            y1 = s * (hb(x) + th)
            ring = [(y0, -z), (y1 - s * e, -z), (y1, -z + e), (y1, z - e), (y1 - s * e, z), (y0, z)]
            rings.append([bm.verts.new((x, y, zz)) for y, zz in ring])
        n = len(rings[0])
        for a, b in zip(rings[:-1], rings[1:]):
            for q in range(n):
                bm.faces.new((a[q], a[(q + 1) % n], b[(q + 1) % n], b[q]))
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        st = G.mesh_obj(f"strap{s}", bm, ss)
        objs.append(G.finish(st, 0, sharp=50))
    # four staggered through-bolts: hex heads to starboard (+Y), nylocks to port
    for k, f in enumerate((0.28, 0.46, 0.67, 0.88)):
        x = x0 + (x1 - x0) * f
        z = 0.006 if k % 2 == 0 else -0.006
        y = hb(x) + th
        o, _ = _hex(f"bolt{k}", (x, y, z), (0, 1, 0), 0.011, 0.0058, ss)
        objs += o
        objs += _nylock(f"nut{k}", (x, -y, z), (0, -1, 0), 0.011, ss)
    # the pin through both lugs and the barrel: a domed head resting on the upper lug, a keeper ring under the lower
    top = LUG_Z + STRAP_W / 2 + 0.001
    bot = -LUG_Z - STRAP_W / 2 - 0.001
    pin = G.cyl("pin", (0, 0, bot - 0.014), (0, 0, top), PIN_R, ss, 24)
    objs.append(G.finish(pin, 0.0006, segs=2))
    head = G.lathe("pinhead", [(0.0, 0.0), (0.0110, 0.0), (0.0110, 0.0035), (0.0102, 0.0048), (0.0085, 0.0062), (0.0050, 0.0072), (0.0, 0.0075)], ss, 32)
    head.location = (0, 0, top)
    G.bake_xform(head)
    objs.append(G.finish(head, 0))
    # the keeper: a split ring through the pin's cross-hole
    zc, rr = bot - 0.008, 0.0080
    ring = G.tube("keeper", [(0.0, rr - 0.001 + rr * math.cos(a), zc + rr * math.sin(a)) for a in [math.tau * k / 20 for k in range(20)]],
                  0.0012, ss, 8, closed=True)
    objs.append(G.finish(ring, 0))
    socks = [("Pin", (0, 0, 0)), ("LugUpper", (0, 0, LUG_Z)), ("LugLower", (0, 0, -LUG_Z)), ("PinTop", (0, 0, top + 0.006))]
    return objs, socks


@P.part("Pintle", "steering", "Stainless strap pintle for a transom-hung rudder: two 30 mm straps through-bolted on the blade, a bushed block at the leading edge, 1/2 in pin with head and keeper")
def pintle(blade=0.036, chord=0.35, length=0.27):
    return P.done("Pintle", *_pintle_parts(blade, chord, length))
