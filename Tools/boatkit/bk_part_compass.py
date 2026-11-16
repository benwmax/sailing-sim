"""BulkheadCompass: the steering compass let into a keelboat's cabin bulkhead (UI overhaul, docs/ui-overhaul Phase 13).

With the interface off the boat herself has to tell the helm the heading: a dinghy sailor glances at the wrist compass,
a keelboat carries this. It is the common small-keelboat bulkhead compass, generic (no maker's shape or name): a black
flanged pod screwed to the bulkhead's face, a spherical bowl inside it, and in the bowl a conical card on
a pivot, read at its near (aft) edge against a lubber line. A card read from aft is printed half a turn round: the
figure at the aft edge is the heading, so the mark for 0 (N) sits at the card's south.

Frame of the mount: the origin is the centre of its foot on the bulkhead's aft face, +Z out of the bulkhead (aft, at
the helm), +X up the bulkhead. The card is its own part (BulkheadCompassCard): origin at the pivot, +Z up, +X toward
the card's north, east at -Y (Blender's +Y is port). The game holds the card level and north, so the boat turns round
it; the kit also has the fixed part alone (BulkheadCompassMount) and the dome alone (BulkheadCompassDome, which the game
draws with a clear material: the kit's library has only smoked acrylic).

Sockets: Mount (the foot's centre), Pivot (the card's pivot), Lubber (the top of the aft lubber line).

Sizes: a 100 mm class bowl (92 mm sphere, 76 mm card) in a 124 mm pod standing 38 mm off the bulkhead. No catalogue was fetched for it; the
proportions are the usual ones and a part-detail-loop round against photos can tighten them. The figures are set in
B612 Bold and wrapped onto the card's cone; ticks every 5 degrees.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

import bk_geom as G
import bk_parts as P

# mm
BEZEL_R = 62.0
BOWL_R = 46.0            # the sphere's inside radius
PIVOT_OUT = 44.0         # the pivot (the sphere's centre) aft of the bulkhead's face: the whole bowl stands proud of it
CARD_R = 38.0
CARD_TOP_R = 21.0
CARD_RISE = 9.5          # the cone: the rim sits this far below the top
GLYPH_H = 7.6            # figure (cap) height along the slope
PROUD = 0.25

# The figures are B612 Bold (the cockpit-instrument face the HUD's numerals use; OFL, Content/UI/Fonts), turned to
# geometry and wrapped onto the card's cone.
FONT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Content", "UI", "Fonts", "B612-Bold.ttf"))
LABELS = {0: "N", 30: "3", 60: "6", 90: "E", 120: "12", 150: "15", 180: "S", 210: "21", 240: "24", 270: "W", 300: "30", 330: "33"}


def _mm(*v):
    return tuple(x / 1000.0 for x in v)


def _cone_point(bearing_deg, r, proud=0.0):
    """A point on the card's cone (metres) at a bearing (card north = +X, east = -Y) and radius (mm), `proud` mm off
    the surface."""
    b = math.radians(bearing_deg)
    radial = Vector((math.cos(b), -math.sin(b), 0.0))
    run = CARD_R - CARD_TOP_R
    slope = math.hypot(run, CARD_RISE)
    out = (radial * CARD_RISE + Vector((0, 0, run))) / slope
    return (radial * r + Vector((0, 0, CARD_RISE * (CARD_R - r) / run)) + out * proud) / 1000.0


def _wrap(bearing_deg, r0, x, y, proud):
    """A point of a flat drawing laid on the cone, as its reader sees it from outside the card: x mm to the reader's
    right along the cone at the drawing's foot radius r0, y mm up the slope toward the card's top."""
    run = CARD_R - CARD_TOP_R
    r = r0 - y * run / math.hypot(run, CARD_RISE)
    # the reader's right is anticlockwise seen from above (bearings run clockwise); x keeps its length at every height
    return _cone_point(bearing_deg - math.degrees(x / max(r, 1e-6)), r, proud)


def _extruded(name, outline_faces, place, mat):
    """Flat faces (lists of (x, y) mm) laid on the card by `place(x, y, proud)`, with walls down into the surface."""
    bm = bmesh.new()
    foot = {}

    def key(co):
        return (round(co[0], 7), round(co[1], 7), round(co[2], 7))

    for face in outline_faces:
        if len(face) < 3:
            continue
        top = []
        for x, y in face:
            v = bm.verts.new(place(x, y, PROUD))
            foot[key(v.co)] = place(x, y, -0.15)
            top.append(v)
        try:
            bm.faces.new(top)
        except ValueError:
            continue
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-7)
    rim = [e for e in bm.edges if len(e.link_faces) == 1]
    if rim:
        ext = bmesh.ops.extrude_edge_only(bm, edges=rim)
        for v in ext["geom"]:
            if isinstance(v, bmesh.types.BMVert):
                v.co = foot.get(key(v.co), v.co)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = G.mesh_obj(name, bm, mat)
    return G.finish(ob, 0, sharp=40.0)


def _text_faces(text, height):
    """The filled outlines of `text` in B612 Bold, as flat faces in mm: cap height `height`, centred on x = 0, the
    baseline at y = 0."""
    font = bpy.data.fonts.load(FONT, check_existing=True)
    cu = bpy.data.curves.new("compass_text", "FONT")
    cu.body, cu.font, cu.align_x = text, font, "CENTER"
    cu.size = 1.0
    cu.resolution_u = 8                                 # smooth bowls on the 3, 6, S and 0
    ob = bpy.data.objects.new("compass_text", cu)
    G.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    cap = max((v.co.y for v in me.vertices), default=1.0)
    k = height / max(cap, 1e-6)
    # finer than the font's own triangles across long edges, so a figure bends with the cone
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    long = [e for e in bm.edges if e.calc_length() * k > 1.6]
    for _ in range(3):
        if not long:
            break
        bmesh.ops.subdivide_edges(bm, edges=long, cuts=1)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        long = [e for e in bm.edges if e.calc_length() * k > 1.6]
    faces = [[(v.co.x * k, v.co.y * k) for v in f.verts] for f in bm.faces]
    bm.free()
    bpy.data.meshes.remove(me)
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.curves.remove(cu)
    return faces


def _card():
    """The turning card about its pivot (origin), +Z up, north along +X."""
    blk, wht, red, brs = P.M("BlackPlastic"), P.M("WhitePlastic"), P.M("RedPlastic"), P.M("Brass")
    objs = []
    body = G.lathe("card", [(0, CARD_RISE - 5.0), (CARD_TOP_R - 3, CARD_RISE - 5.0), (CARD_R - 1.0, -2.2), (CARD_R, -2.2),
                            (CARD_R, 0.0), (CARD_TOP_R, CARD_RISE), (0, CARD_RISE)], blk, 144)
    body.data.transform(Matrix.Scale(0.001, 4))
    objs.append(G.finish(body, 0.0003, segs=2))
    # the graduations: a tick every 5 degrees along the rim (longer at the 10s, longest at the 30s) and a figure every
    # 30 above them. A mark at card bearing b is read when b is at the aft edge, when the boat heads b + 180: it shows
    # b + 180.
    ticks, figures = [], []
    for b in range(0, 360, 5):
        shown = (b + 180) % 360
        length, half = (4.4, 0.5) if shown % 30 == 0 else (3.0, 0.36) if shown % 10 == 0 else (1.7, 0.26)
        n = 4
        for i in range(n):                              # in short lengths, so a tick lies on the cone
            y0, y1 = 0.25 + length * i / n, 0.25 + length * (i + 1) / n
            ticks.append((b, [(-half, y0), (half, y0), (half, y1), (-half, y1)]))
        text = LABELS.get(shown)
        if text:
            figures += [(b, f) for f in _text_faces(text, GLYPH_H if len(text) == 1 else GLYPH_H * 0.9)]
    r_tick, r_fig = CARD_R - 0.3, CARD_R - 6.4
    bm_faces = {}
    for name, items, r0 in (("card_ticks", ticks, r_tick), ("card_figures", figures, r_fig)):
        by_bearing = {}
        for b, face in items:
            by_bearing.setdefault(b, []).append(face)
        parts = [_extruded(f"{name}_{b}", faces, lambda x, y, h, b=b, r0=r0: _wrap(b, r0, x, y, h), wht) for b, faces in by_bearing.items()]
        objs.append(G.join(name, parts))
    # the top: a pointer to the card's north on the flat (a long red lozenge, a short white tail), the pivot's brass
    # jewel cap in the middle
    def on_top(x, y, h):
        return Vector((x, y, CARD_RISE + h)) / 1000.0

    tip, root, half = CARD_TOP_R - 2.0, 4.2, 2.3
    objs.append(_extruded("card_north", [[(root, -0.9), (root + 4.0, -half), (tip, 0.0), (root + 4.0, half), (root, 0.9)]], on_top, red))
    objs.append(_extruded("card_south", [[(-root, 0.8), (-root - 3.0, 1.6), (-tip + 6.0, 0.0), (-root - 3.0, -1.6), (-root, -0.8)]], on_top, wht))
    cap = G.lathe("pivot_cap", [(0, CARD_RISE), (3.6, CARD_RISE), (3.5, CARD_RISE + 1.4), (2.6, CARD_RISE + 2.4), (1.2, CARD_RISE + 2.9), (0, CARD_RISE + 3.0)], brs, 40)
    cap.data.transform(Matrix.Scale(0.001, 4))
    objs.append(G.finish(cap, 0))
    return objs


def _to_mount(objs, heading=0.0):
    """Card parts into the mount's frame: the card's +Z is the mount's +X (up), and with the boat heading `heading`
    degrees the card's north lies that far round from forward (the mount's -Z)."""
    c, s = math.cos(math.radians(heading)), math.sin(math.radians(heading))
    # boat frame (forward, port, up) of card vectors: north = (c, s, 0) (the card turns to port as she turns to starboard)
    north = Vector((c, s, 0.0))
    west = Vector((-s, c, 0.0))                # the card's +Y (port of north)
    up = Vector((0, 0, 1))

    def mount_of(v):                           # boat (forward, port, up) -> mount (+X up, +Y port, +Z aft)
        return Vector((v.z, v.y, -v.x))

    cols = [mount_of(north), mount_of(west), mount_of(up)]
    m = Matrix((
        (cols[0].x, cols[1].x, cols[2].x, 0.0),
        (cols[0].y, cols[1].y, cols[2].y, 0.0),
        (cols[0].z, cols[1].z, cols[2].z, PIVOT_OUT / 1000.0),
        (0, 0, 0, 1)))
    for o in objs:
        o.data.transform(m)
        o.data.update()
    return objs


def _mount():
    """The fixed part: pod, bowl, pivot post, lubber lines."""
    blk, wht, ss = P.M("BlackPlastic"), P.M("WhitePlastic"), P.M("Stainless")
    objs = []
    # A pod standing on the bulkhead (no cutout in the boat: let in flush, the hull's own face hid the bowl and the
    # card's forward half): the flange, a tapered wall out to the lip, then the bowl's inside, a sphere about the pivot
    # down to a flat floor just clear of the bulkhead.
    lip = PIVOT_OUT - 6.0
    prof = [(0, 0.0), (BEZEL_R, 0.0), (BEZEL_R, 3.6), (BEZEL_R - 1.8, 6.0), (BEZEL_R - 8.0, 6.0), (BOWL_R + 4.5, lip - 2.0), (BOWL_R + 3.2, lip)]
    n = 14
    z_top = lip - 0.8
    z_bot = max(PIVOT_OUT - BOWL_R, 1.0)
    for i in range(n + 1):
        z = z_top + (z_bot - z_top) * (i / n) ** 0.8
        r = math.sqrt(max(BOWL_R ** 2 - (z - PIVOT_OUT) ** 2, 0.0))
        if r > 1e-3:
            prof.append((r, z))
    prof.append((0, z_bot))
    bowl = G.lathe("bezel_bowl", prof, blk, 128)
    bowl.data.transform(Matrix.Scale(0.001, 4))
    objs.append(G.finish(bowl, 0.0006, segs=2))
    pts = []
    for k in range(4):
        a = math.radians(45 + 90 * k)
        pts.append(_mm((BEZEL_R - 4.9) * math.cos(a), (BEZEL_R - 4.9) * math.sin(a), 6.0))
    for i, pt in enumerate(pts):                # pan heads, round enough to hold up close
        h = G.lathe(f"bezel_screw{i}", [(0, 0), (3.1, 0), (3.0, 0.7), (2.3, 1.25), (1.2, 1.5), (0, 1.55)], ss, 28)
        h.data.transform(Matrix.Scale(0.001, 4))
        h.location = pt
        G.bake_xform(h)
        objs.append(G.finish(h, 0))
    # the pivot post, up from the bowl's floor (the mount's -X is down) to just under the card
    objs.append(G.cyl("pivot_post", _mm(-(BOWL_R - 1.0), 0, PIVOT_OUT), _mm(CARD_RISE - 5.5, 0, PIVOT_OUT), 1.5 / 1000, ss, 12,
                      r1=0.7 / 1000))
    # lubber lines: short pins on a wire hoop round the card's aft half, just outside and under its rim, its ends let
    # into the bowl's wall; the aft pin is the one the helm reads against, and one each side at 45 degrees serves
    # sitting out to windward
    ring_r, foot_x = CARD_R + 2.6, -5.0
    end_z = PIVOT_OUT - 7.0                                                # the hoop ends just inside the lip
    wall_r = math.sqrt(BOWL_R ** 2 - foot_x ** 2 - (PIVOT_OUT - end_z) ** 2) + 0.5
    end = math.acos((end_z - PIVOT_OUT) / ring_r)
    path = [_mm(foot_x, -wall_r, end_z)]
    path += [_mm(foot_x, -ring_r * math.sin(end - 2 * end * i / 40), PIVOT_OUT + ring_r * math.cos(end - 2 * end * i / 40)) for i in range(41)]
    path.append(_mm(foot_x, wall_r, end_z))
    objs.append(G.tube("lubber_hoop", path, 0.8 / 1000, blk, 12))
    for name, ang in (("lubber", 0.0), ("lubber_port", 45.0), ("lubber_stbd", -45.0)):
        a = math.radians(ang)
        y, z = ring_r * math.sin(a), PIVOT_OUT + ring_r * math.cos(a)
        r = 0.85 if ang == 0.0 else 0.6
        top = 4.5
        pin = G.lathe(name, [(0, foot_x), (r, foot_x), (r, top - r), (r * 0.7, top - r * 0.3), (0, top)], wht, 20)
        pin.data.transform(Matrix.Scale(0.001, 4))
        pin.data.transform(Matrix(((0, 0, 1, 0), (0, 1, 0, y / 1000), (-1, 0, 0, z / 1000), (0, 0, 0, 1))))   # its axis up the bulkhead
        objs.append(G.finish(pin, 0))
    socks = [("Mount", (0.0, 0.0, 0.0)), ("Pivot", _mm(0, 0, PIVOT_OUT)), ("Lubber", _mm(4.5, 0, PIVOT_OUT + ring_r))]
    return objs, socks


def _dome():
    """The clear dome: the sphere's aft half from the bezel's lip out."""
    z0 = PIVOT_OUT - 6.8
    n = 16
    prof = []
    a0 = math.asin((z0 - PIVOT_OUT) / (BOWL_R + 0.8))
    for i in range(n + 1):
        a = a0 + (math.pi / 2 - a0) * i / n
        prof.append(((BOWL_R + 0.8) * math.cos(a), PIVOT_OUT + (BOWL_R + 0.8) * math.sin(a)))
    prof[-1] = (0, PIVOT_OUT + BOWL_R + 0.8)
    dome = G.lathe("dome", prof, P.M("CabinWindow"), 64)
    dome.data.transform(Matrix.Scale(0.001, 4))
    return [G.finish(dome, 0)]


@P.part("BulkheadCompass", "instrument", "Bulkhead steering compass, 100 mm class: flanged pod, spherical bowl, conical card read at its aft edge, three lubber lines (shown without its dome)")
def bulkhead_compass(heading=320.0):
    objs, socks = _mount()
    objs += _to_mount(_card(), heading)
    return P.done("BulkheadCompass", objs, socks)


bulkhead_compass.photo_view = (0.55, 0.25, 1.0)     # the helm's eye: from aft, above and a little to one side


@P.part("BulkheadCompassCard", "instrument", "The bulkhead compass's card alone, origin at the pivot, +X to its north (the game holds it level and north)")
def bulkhead_compass_card():
    return P.done("BulkheadCompassCard", _card(), [("Pivot", (0.0, 0.0, 0.0))])


@P.part("BulkheadCompassMount", "instrument", "The bulkhead compass's fixed part: pod, bowl, pivot post and lubber lines (the card goes on its Pivot socket)")
def bulkhead_compass_mount():
    objs, socks = _mount()
    return P.done("BulkheadCompassMount", objs, socks)


@P.part("BulkheadCompassDome", "instrument", "The bulkhead compass's dome alone, in the mount's frame (the game draws it clear)")
def bulkhead_compass_dome():
    return P.done("BulkheadCompassDome", _dome(), [])
