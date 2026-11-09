"""The kit's tillers and tiller extension (part detail loop, Nov 2026: docs/part-detail-loop/tiller.md).

Two kinds of tiller, so each boat can carry the one it really has:

- `Tiller`: the laminated wooden tiller of a small keelboat (the J/22, Catalina 22): varnished ash and mahogany
  laminations glued in a curved form, so the stripes run along its sides; rectangular with eased edges, deep at the butt
  and tapering to a rounded hand grip, rising from the rudder head. Two stainless side straps through-bolted into the
  butt carry it on the rudder head's big pivot bolt (hex head and washer one side, nylock nut the other; three carriage
  bolts through straps and tiller). Sizes from the catalogue (Rudder Craft J/22 tiller: 47 in long, the butt 2 in high
  by 1.5 in wide, 4.75 in rise); the lamination pattern from Bean's photos of the J/22 he sails.
- `TillerAlu`: the dinghy's metal tiller (the Sunfish's current 44 in tiller, the ILCA's 990 mm): a round anodised
  aluminium tube, 32 mm, a moulded anodised insert in its rudder end that slides into the rudder head's box and takes
  the retaining pin, pop rivets holding it, a textured rubber grip over the hand end and a plastic end cap. `carbon=True`
  builds the same in carbon (a black carbon tube with an alloy insert), as racing dinghies use.
- `TillerExtension`: a tiller extension ("hiking stick") as Ronstan, Harken and the class boats use: a ribbed urethane
  universal joint on a plate screwed to the tiller, a ferrule into a 19 mm anodised tube, a textured grip at its far end
  and a rubber end knob.

Frames (as bk_parts): a tiller's origin is the pivot it turns the rudder about (the wooden tiller's pivot bolt, the metal
tiller's retaining pin), the tiller running aft-to-forward along -X and rising in +Z, Y across. The extension's origin is
the foot of its universal joint, the tube along +X (folded down along the tiller, as it lies when stowed).

Kept in its own file so the loop's other parts can be worked at the same time (bk_parts imports every bk_part_*.py).
"""
import math

import bmesh
import bpy

from mathutils import Matrix, Vector

import bk_geom as G
import bk_parts as P
import bk_trim as BT

IN = 0.0254
# Laminations from the bottom up, as fractions of the depth, and their wood (Bean's photos of the J/22's tiller: broad
# pale ash (the library's Wood) between darker mahogany, as Inputs/j22-hero/j22_steering.py LAMS).
LAMS = (("WoodMahogany", 0.16), ("Wood", 0.30), ("WoodMahogany", 0.07), ("Wood", 0.30), ("WoodMahogany", 0.17))


def _smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def _section(w, h, rc, splits, corner=5):
    """A rounded rectangle (w across Y as u, h up as v) counter-clockwise from the bottom's middle, its straight sides cut
    at the lamination lines (fractions of the height from the bottom), so faces between them take one wood each."""
    rc = min(rc, w / 2 - 1e-5, h / 2 - 1e-5)
    pts = [(0.0, -h / 2)]

    def corner_arc(cx, cy, a0):
        for k in range(corner + 1):
            a = math.radians(a0 + 90 * k / corner)
            pts.append((cx + rc * math.cos(a), cy + rc * math.sin(a)))

    corner_arc(w / 2 - rc, -h / 2 + rc, 270)
    for f in splits:                      # right side, going up
        v = -h / 2 + f * h
        if -h / 2 + rc + 1e-6 < v < h / 2 - rc - 1e-6:
            pts.append((w / 2, v))
    corner_arc(w / 2 - rc, h / 2 - rc, 0)
    pts.append((0.0, h / 2))
    corner_arc(-w / 2 + rc, h / 2 - rc, 90)
    for f in reversed(splits):            # left side, going down
        v = -h / 2 + f * h
        if -h / 2 + rc + 1e-6 < v < h / 2 - rc - 1e-6:
            pts.append((-w / 2, v))
    corner_arc(-w / 2 + rc, -h / 2 + rc, 180)
    return pts


def _layer(vfrac):
    """The lamination index at a height fraction from the bottom (0..1)."""
    z = 0.0
    for k, (_, f) in enumerate(LAMS):
        z += f
        if vfrac < z - 1e-6:
            return k
    return len(LAMS) - 1


def _laminated(name, stations, mats):
    """Loft the tiller's body through stations [(centre Vector, tangent Vector, w, h, rc, scale)], every ring the same
    point count, and give each side face the wood of its lamination (by its height in the section)."""
    splits = []
    z = 0.0
    for _, f in LAMS[:-1]:
        z += f
        splits.append(z)
    bm = bmesh.new()
    rings, vf = [], None
    side = Vector((0, 1, 0))
    for c, t, w, h, rc, s in stations:
        up = t.cross(side).normalized()
        if up.z < 0:
            up = -up
        sec = _section(w, h, min(rc, 0.12 * h), splits)    # (the corners stay inside the outer laminations, so every ring matches)
        if vf is None:
            vf = [(v + h / 2) / h for _, v in sec]
        rings.append([bm.verts.new(c + side * (u * s) + up * (v * s)) for u, v in sec])
    n = len(rings[0])
    slot = {m: i for i, m in enumerate(mats)}
    for a, b in zip(rings, rings[1:]):
        for k in range(n):
            f = bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
            f.material_index = slot[LAMS[_layer(0.5 * (vf[k] + vf[(k + 1) % n]))][0]]
    for ring, rev in ((rings[0], True), (rings[-1], False)):
        f = bm.faces.new(list(reversed(ring)) if rev else ring)
        f.material_index = slot["Wood"]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy_mesh(name, bm)
    for m in mats:
        me.materials.append(P.M(m))
    return G.link(bpy.data.objects.new(name, me))


def bpy_mesh(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def _xz_plate(name, outline, y0, y1, mat):
    """A plate whose outline is drawn in (x, z), from y0 to y1."""
    ob = G.prism(name, outline, -y1, -y0, mat)
    ob.matrix_world = Matrix.Rotation(math.pi / 2, 4, "X")
    G.bake_xform(ob)
    return ob


def _hex(name, c, axis, across_flats, h, mat):
    """A hex head or nut: across_flats, h thick, from c along axis."""
    r = across_flats / 2 / math.cos(math.pi / 6)
    a = Vector(axis).normalized()
    ob = G.lathe(name, [(0, 0), (r, 0), (r, h * 0.85), (r * 0.9, h), (0, h)], mat, 6)
    ob.matrix_world = G.along(c, a) @ Matrix.Rotation(math.pi / 6, 4, "Z")
    G.bake_xform(ob)
    return G.finish(ob, 0.0004, segs=1)


def _dome(name, c, axis, r, h, mat, segs=16):
    prof = [(0, 0), (r, 0)] + [(r * math.cos(a), h * math.sin(a)) for a in (0.35, 0.75, 1.15)] + [(0, h)]
    ob = G.lathe(name, prof, mat, segs)
    ob.matrix_world = G.along(c, Vector(axis))
    G.bake_xform(ob)
    return G.finish(ob, 0)


def _nylock(name, c, axis, across_flats, mat):
    """A nylock nut: hex, its nylon collar domed over the bolt's end."""
    a = Vector(axis).normalized()
    h = across_flats * 0.55
    out = [_hex(name, c, a, across_flats, h, mat)]
    out.append(_dome(f"{name}_collar", c + a * h, a, across_flats * 0.42, across_flats * 0.22, mat, 16))
    return out


# ------------------------------------------------------------------ the wooden tiller

def _wood_path(length, rise, strap_in, n=48):
    """Stations from the butt to where the grip's round-off starts: flat through the straps, then the catalogue's 4.75 in
    rise over the first 40% and nearly straight to the grip (r2's S read as too wavy; r4's longer, smoother rise lost its
    blind round to this one)."""
    x0 = -strap_in
    pts = []
    for i in range(n + 1):
        u = i / n
        x = x0 - (length - 0.035) * u
        z = rise * _smooth((u - 0.08) / 0.42) - 0.005 * math.sin(math.pi * min(max((u - 0.40) / 0.6, 0.0), 1.0)) ** 2
        pts.append(Vector((x, 0.0, z)))
    return pts


@P.part("Tiller", "steering", "Laminated ash and mahogany tiller, 47 in (J/22), rising from stainless side straps on the rudder head's pivot bolt to a rounded grip")
def tiller(length=1.194, rise=0.121, butt_h=2.0 * IN, butt_w=1.5 * IN, grip_h=0.031, grip_w=0.029, strap_in=0.085):
    pts = _wood_path(length, rise, strap_in)
    n = len(pts) - 1

    def dims(u):
        w = butt_w + (grip_w - butt_w) * _smooth(u * 1.15)
        h = butt_h + (grip_h - butt_h) * (0.6 * u + 0.4 * _smooth(u * 1.4))     # deep at the butt, tapering all the way
        return w, h

    stations = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n)] - pts[max(i - 1, 0)]).normalized()
        w, h = dims(i / n)
        stations.append((p, t, w, h, 0.0065 if i == 0 else 0.0075, 1.0))     # t points forward, along -X
    # the butt's end eased off (a few rings stepping in) and the grip rounded over its last 35 mm
    t0 = stations[0][1]
    w0, h0 = dims(0)
    stations.insert(0, (pts[0] - t0 * 0.002, t0, w0 * 0.92, h0 * 0.94, 0.006, 1.0))
    tn = stations[-1][1]
    wn, hn = dims(1)
    for f in (0.99, 0.95, 0.87, 0.74, 0.55, 0.28):
        d = 0.035 * math.sqrt(max(1 - f * f, 0.0))
        stations.append((pts[-1] + tn * d, tn, wn * f, hn * f, min(0.0075, wn * f / 2 - 0.0005), 1.0))
    body = _laminated("tiller_body", stations, ["Wood", "WoodMahogany"])
    BT.mark(G.finish(body, 0), band="grip")

    objs = [body]
    # the stainless straps: from the pivot (round-ended round it) into the butt's sides, under three carriage bolts
    st = P.M("Stainless")
    s_half, s_t, s_len = 0.017, 0.004, strap_in + 0.17
    r_end = 0.021
    outline = [(r_end * math.cos(a), r_end * math.sin(a)) for a in [math.pi / 2 - math.pi * k / 12 for k in range(13)]]
    outline = [(x, z) for x, z in outline]          # forward half-round, from the top round the front to the bottom
    outline += [(-0.03, -s_half), (-s_len + 0.006, -s_half * 0.92), (-s_len, -s_half * 0.92 + 0.006),
                (-s_len, s_half * 0.92 - 0.006), (-s_len + 0.006, s_half * 0.92), (-0.03, s_half)]
    outline = list(reversed(outline))               # counter-clockwise for prism's caps
    y_in = butt_w / 2
    for sgn in (1, -1):
        y0, y1 = (y_in, y_in + s_t) if sgn > 0 else (-y_in - s_t, -y_in)
        objs.append(G.finish(_xz_plate(f"strap{'_p' if sgn > 0 else '_s'}", outline, y0, y1, st), 0.0008, segs=2))
    yo = y_in + s_t
    # the pivot bolt (3/8 in) with a hex head and washer to port, a nylock to starboard
    objs.append(G.finish(G.cyl("pivot_bolt", (0, -yo - 0.016, 0), (0, yo + 0.012, 0), 0.0048, st, 16), 0))
    objs.append(G.finish(G.cyl("pivot_washer", (0, yo, 0), (0, yo + 0.0016, 0), 0.0105, st, 24), 0.0003, segs=1))
    objs.append(_hex("pivot_head", Vector((0, yo + 0.0016, 0)), (0, 1, 0), 0.0143, 0.006, st))
    objs.append(G.finish(G.cyl("pivot_washer_s", (0, -yo, 0), (0, -yo - 0.0016, 0), 0.0105, st, 24), 0.0003, segs=1))
    objs += _nylock("pivot_nut", Vector((0, -yo - 0.0016, 0)), (0, -1, 0), 0.0143, st)
    # three carriage bolts (1/4 in) through straps and butt: domed heads to port, nylocks to starboard
    for k, d in enumerate((strap_in + 0.040, strap_in + 0.085, strap_in + 0.130)):
        x = -d
        objs.append(_dome(f"carriage_head{k}", Vector((x, yo, 0)), (0, 1, 0), 0.0075, 0.0035, st))
        objs += _nylock(f"carriage_nut{k}", Vector((x, -yo, 0)), (0, -1, 0), 0.011, st)
    end = pts[-1]
    _, hn = dims(1)
    tip_x = end.x - 0.035
    return P.done("Tiller", objs, [("Stock", (0, 0, 0)), ("ExtPivot", (tip_x + 0.07, 0, end.z + hn / 2)),
                                   ("Hand", (tip_x + 0.15, 0, end.z)), ("Butt", (-strap_in, 0, 0))])


# ------------------------------------------------------------------ the metal tiller

@P.part("TillerAlu", "steering", "Dinghy tiller: 32 mm anodised aluminium tube (Sunfish 44 in, ILCA 990 mm), moulded nose insert with retaining pin, rubber grip, end cap; carbon=True for a carbon tube")
def tiller_alu(length=1.118, d=0.032, carbon=False, rise=0.0):
    r = d / 2
    tube_mat = P.M("CarbonMatte" if carbon else "Aluminium")
    alu, st, rub, blk = P.M("Aluminium"), P.M("Stainless"), P.M("Rubber"), P.M("BlackPlastic")
    nose_back = -0.075                  # where the tube starts: the insert's shoulder
    end_x = -length + 0.0515            # the tube's hand end, under the cap (the tongue's nose is 33 mm ahead of the pin and the cap 18.5 mm long, so nose to cap is `length`)
    objs = []
    # the tube (a 1.6 mm wall shows at nothing: it's capped both ends)
    tube = G.cyl("tube", (nose_back, 0, 0), (end_x, 0, rise), r, tube_mat, 32)
    objs.append(G.finish(tube, 0))
    # the moulded insert: a shoulder ring the tube's size, then a tongue that slides into the rudder head's box, tapering
    # and rounded at its nose, with the retaining pin's hole through it at the origin
    objs.append(G.finish(G.cyl("insert_collar", (nose_back + 0.012, 0, 0), (nose_back, 0, 0), r + 0.0012, alu, 32), 0.0008, segs=2))
    # (r3: lofted from the collar's round down a short taper and a step to the tongue, rounded off at its nose; r2's
    # straight box read as machined)
    x0 = nose_back + 0.012
    secs = [(x0, 0.0338, 0.0338, 0.0169), (x0 + 0.010, 0.030, 0.031, 0.013), (x0 + 0.022, 0.026, 0.029, 0.009),
            (x0 + 0.024, 0.023, 0.026, 0.0075), (0.020, 0.023, 0.026, 0.0075), (0.027, 0.021, 0.024, 0.0075),
            (0.031, 0.016, 0.019, 0.0075), (0.033, 0.009, 0.012, 0.0045)]
    bm = bmesh.new()
    rings = []
    for x, w, h, rc in secs:
        rings.append([bm.verts.new((x, u, v)) for u, v in _section(w, h, min(rc, w / 2 - 1e-4, h / 2 - 1e-4), [], corner=6)])
    n = len(rings[0])
    for a_, b_ in zip(rings, rings[1:]):
        for k in range(n):
            bm.faces.new((a_[k], a_[(k + 1) % n], b_[(k + 1) % n], b_[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    tongue = G.mesh_obj("insert_tongue", bm, alu)
    G.finish(tongue, 0)
    hole = G.cyl("pin_hole", (0, 0, -0.03), (0, 0, 0.03), 0.0045, alu, 20)
    objs.append(G.boolean(tongue, hole))
    # the retaining pin through the head and tongue: a stainless pin with a ring through its head
    objs.append(G.finish(G.cyl("retaining_pin", (0, 0, -0.026), (0, 0, 0.024), 0.0038, st, 16), 0))
    objs.append(_dome("retaining_pin_head", Vector((0, 0, 0.024)), (0, 0, 1), 0.0062, 0.0035, st))
    ring = G.tube("retaining_ring", G.arc_pts((0.0, 0, 0.0355), 0.008, 0, 2 * math.pi, 24, "xz")[:-1], 0.0010, st, 8, closed=True)
    ring.matrix_world = Matrix.Translation((-0.008, 0, -0.004)) @ Matrix.Identity(4)
    G.bake_xform(ring)
    objs.append(G.finish(ring, 0))
    # two pop rivets holding the insert in the tube, top and bottom
    for zs in (1, -1):
        objs.append(_dome(f"rivet{'_t' if zs > 0 else '_b'}", Vector((nose_back - 0.022, 0, zs * (r - 0.0006))), (0, 0, zs), 0.0042, 0.0018, alu, 12))
    # the textured grip over the hand end's last 240 mm: a rubber sleeve with fine moulded rings
    gx0 = end_x + 0.24
    span = gx0 - end_x
    prof = [(0, 0), (r + 0.0018, 0)]
    nring = 40
    for k in range(nring):
        z0 = 0.004 + (span - 0.008) * k / nring
        dz = (span - 0.008) / nring
        prof += [(r + 0.0023, z0 + dz * 0.25), (r + 0.0023, z0 + dz * 0.65), (r + 0.0016, z0 + dz * 0.9)]
    prof += [(r + 0.0018, span), (0, span)]
    grip = G.lathe("grip", prof, rub, 32)
    grip.matrix_world = G.along((gx0, 0, rise * (gx0 - nose_back) / (end_x - nose_back)), (-1, 0, 0))
    G.bake_xform(grip)
    BT.mark(G.finish(grip, 0), band="grip")
    objs.append(grip)
    # the plastic end cap: a flat plug with a rounded rim
    cap = G.lathe("end_cap", [(0, 0), (r + 0.0026, 0), (r + 0.0026, 0.012), (r + 0.0012, 0.0165), (r * 0.8, 0.018), (0, 0.0185)], blk, 32)
    cap.matrix_world = G.along((end_x, 0, rise), (-1, 0, 0))
    G.bake_xform(cap)
    objs.append(G.finish(cap, 0))
    return P.done("TillerAlu", objs, [("Stock", (0, 0, 0)), ("ExtPivot", (end_x + 0.06, 0, rise + r + 0.0026)),
                                      ("Hand", (end_x + 0.15, 0, rise))])


# ------------------------------------------------------------------ the extension

@P.part("TillerExtension", "steering", "Tiller extension: ribbed urethane universal joint on a screwed plate, 19 mm anodised tube, textured grip, rubber end knob")
def tiller_extension(length=1.0, d=0.019, black=False):
    r = d / 2
    alu, st, rub, blk = P.M("Aluminium"), P.M("Stainless"), P.M("Rubber"), P.M("BlackPlastic")
    tube_mat = P.M("BlackPlastic") if black else alu
    objs = []
    # the joint's plate on the tiller, two pan-head screws
    plate = G.prism("uj_plate", G.rrect(0.052, 0.026, 0.008, 4), 0.0, 0.004, blk)
    objs.append(G.finish(plate, 0.0008, segs=2))
    for x in (-0.017, 0.017):
        objs += G.screw_heads(f"uj_screw{'a' if x < 0 else 'b'}", [(x, 0, 0.004)], st, r=0.0035, h=0.0018)
    # the urethane joint: a ribbed column up from the plate that bends over (it is the joint: flexible) to lie along +X,
    # stowed, then a ferrule onto the tube
    R_, z0 = 0.018, 0.012          # (r3 tried a tighter 13 mm bend: it lost 0-3, read as a plumbing elbow)
    path = [Vector((0, 0, 0.004)), Vector((0, 0, z0))]
    path += [Vector((R_ - R_ * math.cos(a), 0, z0 + R_ * math.sin(a))) for a in [math.pi / 2 * k / 14 for k in range(1, 15)]]
    path += [Vector((R_ + 0.004, 0, z0 + R_)), Vector((R_ + 0.010, 0, z0 + R_))]
    s_ = [0.0]
    for p0, p1 in zip(path, path[1:]):
        s_.append(s_[-1] + (p1 - p0).length)
    rib = 0.0062                          # rib pitch along the joint
    # (densify so the ribs read: resample the path every 1 mm)
    dense, dr = [], []
    for i in range(len(path) - 1):
        n = max(1, int((path[i + 1] - path[i]).length / 0.001))
        for j in range(n):
            t = j / n
            x = s_[i] + (s_[i + 1] - s_[i]) * t
            dense.append(path[i].lerp(path[i + 1], t))
            dr.append(1.0 + 0.16 * max(0.0, math.cos(2 * math.pi * x / rib)) ** 4 if 0.005 < x < s_[-1] - 0.005 else 1.0)
    dense.append(path[-1])
    dr.append(1.0)
    uj = G.sweep("uj", dense, G.ellipse(0.0105, 0.0105, 20), blk, radii=dr)
    objs.append(G.finish(uj, 0))
    zc = z0 + R_                         # the tube's centre height, lying along +X
    objs.append(G.finish(G.cyl("ferrule", (R_ + 0.006, 0, zc), (R_ + 0.040, 0, zc), r + 0.0016, alu, 24), 0.0008, segs=2))
    t_end = length - 0.063               # the tube's end under the knob: overall, plate's front to knob's end, is `length`
    tube = G.cyl("tube", (R_ + 0.035, 0, zc), (t_end, 0, zc), r, tube_mat, 24)
    objs.append(G.finish(tube, 0))
    # the grip over the far 280 mm: textured with rings
    g0 = t_end - 0.28
    prof = [(0, 0), (r + 0.0015, 0)]
    for k in range(28):
        z = 0.003 + 0.274 * k / 28
        dz = 0.274 / 28
        prof += [(r + 0.0024, z + dz * 0.3), (r + 0.0024, z + dz * 0.6), (r + 0.0015, z + dz * 0.9)]
    prof += [(r + 0.0015, 0.28), (0, 0.28)]
    grip = G.lathe("grip", prof, rub, 24)
    grip.matrix_world = G.along((g0, 0, zc), (1, 0, 0))
    G.bake_xform(grip)
    BT.mark(G.finish(grip, 0), band="grip")
    objs.append(grip)
    # the rubber end knob: a ball on a neck
    knob = G.lathe("knob", [(0, 0), (r + 0.002, 0), (r + 0.004, 0.006), (0.019, 0.016), (0.0195, 0.024), (0.016, 0.032), (0.009, 0.036), (0, 0.037)], blk, 24)
    knob.matrix_world = G.along((t_end, 0, zc), (1, 0, 0))
    G.bake_xform(knob)
    objs.append(G.finish(knob, 0))
    return P.done("TillerExtension", objs, [("UJ", (0, 0, 0)), ("Grip", (length * 0.8, 0, zc)), ("Tip", (length, 0, zc))])


P.SIZES["Tiller"] = {"dim": "length mm", "default": "1194", "kw": {"1050": {"length": 1.05}, "1194": {"length": 1.194}, "1300": {"length": 1.30}}}
P.SIZES["TillerAlu"] = {"dim": "length mm", "default": "1118", "kw": {"990": {"length": 0.99}, "1118": {"length": 1.118}}}
P.SIZES["TillerExtension"] = {"dim": "length mm", "default": "1000", "kw": {"610": {"length": 0.61}, "914": {"length": 0.914}, "1000": {"length": 1.0}, "1220": {"length": 1.22}}}
