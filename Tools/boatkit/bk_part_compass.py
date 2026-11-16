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
proportions are the usual ones and a part-detail-loop round against photos can tighten them.
"""
import math

import bmesh
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
GLYPH_H = 7.4            # figure height along the slope
STROKE = 1.05
PROUD = 0.25

# Strokes on a 4 x 6 grid.
GLYPHS = {
    "0": [[(1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0)]],
    "1": [[(1, 5), (2, 6), (2, 0)]],
    "2": [[(0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (0, 0), (4, 0)]],
    "3": [[(0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (3, 3), (4, 2), (4, 1), (3, 0), (1, 0), (0, 1)], [(1.6, 3), (3, 3)]],
    "4": [[(0, 6), (0, 3), (4, 3)], [(4, 6), (4, 0)]],
    "5": [[(4, 6), (0, 6), (0, 3.4), (3, 3.4), (4, 2.4), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "6": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1), (4, 2.4), (3, 3.4), (0, 3.4)]],
    "N": [[(0, 0), (0, 6), (4, 0), (4, 6)]],
    "E": [[(4, 6), (0, 6), (0, 0), (4, 0)], [(0, 3), (3, 3)]],
    "S": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 4), (1, 3), (3, 3), (4, 2), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "W": [[(0, 6), (1, 0), (2, 4), (3, 0), (4, 6)]],
}
LABELS = {0: "N", 30: "3", 60: "6", 90: "E", 120: "12", 150: "15", 180: "S", 210: "21", 240: "24", 270: "W", 300: "30", 330: "33"}


def _mm(*v):
    return tuple(x / 1000.0 for x in v)


def _slab(bm, frame, a, b, width, proud):
    """A flat bar from a to b (mm, in the frame's XY) lying on the frame's plane, `proud` high along its Z."""
    a, b = Vector((a[0], a[1], 0.0)), Vector((b[0], b[1], 0.0))
    d = (b - a)
    if d.length < 1e-6:
        return
    d.normalize()
    n = Vector((-d.y, d.x, 0.0)) * (width / 2)
    e = d * (width / 2)        # square ends that overlap at the corners
    base = [a - e - n, b + e - n, b + e + n, a - e + n]
    lo = [bm.verts.new(frame @ (p / 1000.0)) for p in base]
    hi = [bm.verts.new(frame @ ((p + Vector((0, 0, proud))) / 1000.0)) for p in base]
    bm.faces.new(hi)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))


def _cone_frame(bearing_deg, r):
    """A frame on the card's cone at a bearing (card north = +X, east = -Y) and radius: X to the reader's right (the
    reader stands outside the card looking in), Y up the slope toward the top, Z out of the surface. Metres."""
    b = math.radians(bearing_deg)
    radial = Vector((math.cos(b), -math.sin(b), 0.0))
    right = Vector((-radial.y, radial.x, 0.0))
    run = CARD_R - CARD_TOP_R
    up = (Vector((0, 0, CARD_RISE)) - radial * run).normalized()
    out = right.cross(up).normalized()
    z = CARD_RISE * (CARD_R - r) / run
    o = (radial * r + Vector((0, 0, z))) / 1000.0
    m = Matrix((
        (right.x, up.x, out.x, o.x),
        (right.y, up.y, out.y, o.y),
        (right.z, up.z, out.z, o.z),
        (0, 0, 0, 1)))
    return m


def _card():
    """The turning card about its pivot (origin), +Z up, north along +X."""
    blk, wht, red, brs = P.M("BlackPlastic"), P.M("WhitePlastic"), P.M("RedPlastic"), P.M("Brass")
    objs = []
    body = G.lathe("card", [(0, CARD_RISE - 5.0), (CARD_TOP_R - 3, CARD_RISE - 5.0), (CARD_R - 1.0, -2.2), (CARD_R, -2.2),
                            (CARD_R, 0.0), (CARD_TOP_R, CARD_RISE), (0, CARD_RISE)], blk, 72)
    body.data.transform(Matrix.Scale(0.001, 4))
    objs.append(G.finish(body, 0.0003, segs=1))
    # the graduations: a tick every 10 degrees along the rim, longer at the 30s, and a figure every 30 above them.
    # A mark at card bearing b is read when b is at the aft edge, when the boat heads b + 180: it shows b + 180.
    bm = bmesh.new()
    scale = GLYPH_H / 6.0
    for b in range(0, 360, 10):
        shown = (b + 180) % 360
        f = _cone_frame(b, CARD_R - 0.4)
        long_tick = shown % 30 == 0
        _slab(bm, f, (0, 0.3), (0, 4.2 if long_tick else 2.6), 0.95 if long_tick else 0.7, PROUD)
        text = LABELS.get(shown)
        if not text:
            continue
        w = len(text) * 4 * scale + (len(text) - 1) * 1.3
        f = _cone_frame(b, CARD_R - 5.4)
        x0 = -w / 2
        for ch in text:
            for stroke in GLYPHS[ch]:
                for p, q in zip(stroke, stroke[1:]):
                    _slab(bm, f, (x0 + p[0] * scale, p[1] * scale), (x0 + q[0] * scale, q[1] * scale), STROKE, PROUD)
            x0 += 4 * scale + 1.3
    marks = G.mesh_obj("card_marks", bm, wht)
    for p in marks.data.polygons:
        p.use_smooth = False
    objs.append(marks)
    # the top: a red arrow to the card's north on the flat, the pivot's brass jewel cap in the middle
    bm = bmesh.new()
    top = Matrix.Translation(_mm(0, 0, CARD_RISE))
    for a, b in (((4.5, 0), (CARD_TOP_R - 4.5, 0)), ((CARD_TOP_R - 4.5, 0), (CARD_TOP_R - 9.5, 4.0)), ((CARD_TOP_R - 4.5, 0), (CARD_TOP_R - 9.5, -4.0))):
        _slab(bm, top, a, b, 1.5, PROUD)
    arrow = G.mesh_obj("card_north", bm, red)
    for p in arrow.data.polygons:
        p.use_smooth = False
    objs.append(arrow)
    cap = G.lathe("pivot_cap", [(0, CARD_RISE), (3.4, CARD_RISE), (3.2, CARD_RISE + 1.6), (1.6, CARD_RISE + 2.6), (0, CARD_RISE + 2.8)], brs, 20)
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
    bowl = G.lathe("bezel_bowl", prof, blk, 64)
    bowl.data.transform(Matrix.Scale(0.001, 4))
    objs.append(G.finish(bowl, 0.0006, segs=2))
    pts = []
    for k in range(4):
        a = math.radians(45 + 90 * k)
        pts.append(_mm((BEZEL_R - 4.9) * math.cos(a), (BEZEL_R - 4.9) * math.sin(a), 6.0))
    objs += G.screw_heads("bezel_screw", pts, ss, 0.0030, 0.0012)
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
    objs.append(G.tube("lubber_hoop", path, 0.8 / 1000, blk, 8))
    for name, ang in (("lubber", 0.0), ("lubber_port", 45.0), ("lubber_stbd", -45.0)):
        a = math.radians(ang)
        y, z = ring_r * math.sin(a), PIVOT_OUT + ring_r * math.cos(a)
        objs.append(G.cyl(name, _mm(foot_x, y, z), _mm(4.5, y, z), (0.8 if ang == 0.0 else 0.55) / 1000, wht, 8))
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
