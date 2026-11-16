"""The Catalina 22's deck, cockpit, cabin trunk and pop-top as meshes (docs/c22-3), from deck_c22's surfaces.

Imported by build_c22.py (needs Blender's Python). Every part is built in the game's frame (X forward, Y starboard,
Z up) and written with Y mirrored to Blender's port-positive Y, as the hull is. Neighbouring parts take their shared
edges from the same deck_c22 functions, so they meet exactly; the rubrail overlaps the hull-to-deck joint.

Objects (each one material slot per surface, named as build_fleet.py's SLOTS):
  C22_Deck           the cambered deck from the sheer, open over the cockpit, closed across the transom's top
  C22_Rubrail        the vinyl rubrail round the sheer and across the transom, tapering away at the stem
  C22_Well           the cockpit: coamings, bench seats, footwell and sole, its aft end and the footwell's front
  C22_Cabin          the trunk: sides, raked front, crowned top open under the pop-top (with a lip), its corners
                     rounded, the companionway bulkhead with its tapered opening, sill and jambs
  C22_Ports          one long window a side: dark glass in an aluminium frame
  C22_DropBoards     three teak drop boards in the companionway, a backing strip behind each joint
  C22_ForeHatch      the foredeck hatch
  C22_PopTop         the pop-top closed: a closed moulding standing proud of the top, its flange turned down round it,
                     with the sliding companionway hatch
  C22_PopTopRaised   the same raised by pop_top.lift on four stainless legs, a two-sided canvas skirt all round
                     (hidden; with --raised it is built in place of the closed one, under the name C22_PopTop)
"""
import math

import bpy
import bmesh
from mathutils import Vector

import deck_c22 as DK
import hull_c22 as H

CK, CB, PT, CW = DK.CK, DK.CB, DK.PT, DK.CW
LID_GAP = PT["lid_rise"]  # the closed lid's skin over the trunk top
LID_THICK = 0.006         # the lid's moulding: its underside this far under its skin, its flange this thick
LIP = 0.03                # the opening's lip, turned down inside the trunk top
HATCH_HALF = 0.30         # the sliding hatch's half-width (it covers the companionway's opening, 0.26 a side)
HATCH_RISE = 0.035        # its top over the lid's centreline
FLANGE_SINK = 0.005       # the lid's flange sits this far into the trunk top (a join overlaps, not just meets)
FW_SHARE = CK["footwell_half_width"] / CK["half_width"]
WELL_SHARES = ([-1 + (1 - FW_SHARE) * k / 4 for k in range(4)] + [-FW_SHARE + 2 * FW_SHARE * k / 8 for k in range(8)]
               + [FW_SHARE + (1 - FW_SHARE) * k / 4 for k in range(5)])   # the deck's middle columns, as shares
SILL_DEPTH = 0.03         # the companionway bulkhead's thickness at its opening (the sill and jambs)


class Mesh:
    """A bmesh in the game's frame with named material slots; faces are turned to face 'out'."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.slots = []
        self.flat = set()

    def v(self, p):
        return self.bm.verts.new((p[0], -p[1], p[2]))

    def slot(self, name):
        if name not in self.slots:
            self.slots.append(name)
        return self.slots.index(name)

    def face(self, verts, slot, out=None, flat=False):
        f = self.bm.faces.new(verts)
        f.material_index = self.slot(slot)
        if out is not None:
            f.normal_update()
            o = Vector((out[0], -out[1], out[2]))
            if f.normal.dot(o) < 0:
                f.normal_flip()
        if flat:
            self.flat.add(f)
        return f

    def grid(self, rows, slot, out, skip=None, flat=False):
        """Quads between rows of points (game frame). out(point) is the side they face; skip(i, j) leaves a hole;
        slot is a slot's name or a function of the quad's middle and facing that names one."""
        vs = [[self.v(p) for p in r] for r in rows]
        for i in range(len(rows) - 1):
            for j in range(len(rows[i]) - 1):
                if skip and skip(i, j):
                    continue
                q = [vs[i][j], vs[i][j + 1], vs[i + 1][j + 1], vs[i + 1][j]]
                mid = [sum(c) / 4 for c in zip(rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j])]
                o = out(mid)
                self.face(q, slot(mid, o) if callable(slot) else slot, o, flat)
        return vs

    def polygon(self, pts, slot, out):
        """A flat polygon (may be concave), cut into triangles. Points in a straight line with their neighbours are
        dropped first, so the cut leaves no zero-area triangles."""
        keep = []
        for i, p in enumerate(pts):
            a, b = Vector(pts[i - 1]), Vector(pts[(i + 1) % len(pts)])
            u, w = Vector(p) - a, b - Vector(p)
            if u.length < 1e-9 or w.length < 1e-9 or u.normalized().cross(w.normalized()).length > 1e-5:
                keep.append(p)
        f = self.face([self.v(p) for p in keep], slot, out, flat=True)
        res = bmesh.ops.triangulate(self.bm, faces=[f], quad_method="BEAUTY", ngon_method="EAR_CLIP")
        for t in res["faces"]:
            t.normal_update()
            o = Vector((out[0], -out[1], out[2]))
            if t.normal.dot(o) < 0:
                t.normal_flip()
            self.flat.add(t)

    def strip(self, left, right, slot, out):
        """A flat band between two chains of points that start apart and may end together: right is resampled to
        left's count by arc length, each quad cut on its shorter diagonal, zero-area triangles left out. Every point of
        left is kept, so a neighbour sharing those points welds to it with no T-junction."""
        def arclen(c):
            d = [0.0]
            for a, b in zip(c[:-1], c[1:]):
                d.append(d[-1] + (Vector(b) - Vector(a)).length)
            return [x / d[-1] for x in d]

        fl, fr = arclen(left), arclen(right)
        rs = []
        for f in fl:
            k = max(i for i in range(len(fr)) if fr[i] <= f + 1e-12) if f < 1 else len(fr) - 2
            k = min(k, len(fr) - 2)
            t = (f - fr[k]) / (fr[k + 1] - fr[k])
            rs.append(tuple(Vector(right[k]).lerp(Vector(right[k + 1]), t)))
        for i in range(len(left) - 1):
            a, b, c, d = Vector(left[i]), Vector(left[i + 1]), Vector(rs[i + 1]), Vector(rs[i])
            tris = [(a, b, c), (a, c, d)] if (a - c).length < (b - d).length else [(a, b, d), (b, c, d)]
            for t in tris:
                if (t[1] - t[0]).cross(t[2] - t[0]).length > 1e-9:
                    self.face([self.v(tuple(q)) for q in t], slot, out, flat=True)

    def finish(self, materials, weld=1e-6):
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=weld)
        bmesh.ops.delete(self.bm, geom=[v for v in self.bm.verts if not v.link_faces], context="VERTS")
        self.bm.normal_update()
        uv = self.bm.loops.layers.uv.new("UVMap")
        for f in self.bm.faces:
            ax = max(range(3), key=lambda i: abs(f.normal[i]))
            a, b = [(1, 2), (0, 2), (0, 1)][ax]
            for lp in f.loops:
                lp[uv].uv = (lp.vert.co[a], lp.vert.co[b])
            f.smooth = f not in self.flat
        me = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(me)
        self.bm.free()
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        for s in self.slots:
            me.materials.append(materials[s])
        return ob


def lerp(a, b, t):
    return a + (b - a) * t


def deck_rows():
    """The deck's stations: the hull's, with the cockpit's two ends put in exactly (the opening's edges)."""
    xs = H.stations(180)
    keep = [x for x in xs if all(abs(x - c) > 0.006 for c in CK["x"])]
    return sorted(keep + list(CK["x"]))


def deck_inner(x):
    """Where the deck's grid changes from its middle to its outer columns: the cockpit's side, narrower forward."""
    return min(CK["half_width"], 0.7 * H.half_beam(x))


def build_deck(mats):
    m = Mesh("C22_Deck")
    xs = deck_rows()
    no = 12
    rows = []
    for i, x in enumerate(xs):
        hb, yi = H.half_beam(x), deck_inner(x)
        if i == len(xs) - 1:
            hb = yi = 0.0                                       # the stem's head: the row closes to a point
        ys = [-hb + (hb - yi) * k / no for k in range(no)]
        ys += [yi * f for f in WELL_SHARES]
        ys += [yi + (hb - yi) * k / no for k in range(1, no + 1)]
        rows.append([(x, y, DK.deck_z(x, y) if hb > 0 else H.sheer_z(x)) for y in ys])
    i0, i1 = xs.index(CK["x"][0]), xs.index(CK["x"][1])
    nw = len(WELL_SHARES) - 1
    jc = [j for j in range(no, no + nw) if abs(WELL_SHARES[j - no]) < FW_SHARE + 1e-9
          and abs(WELL_SHARES[j - no + 1]) < FW_SHARE + 1e-9]

    def skip(i, j):
        """The cockpit's opening, and the strip under the companionway between the bulkhead and the next station
        (it would show as a ledge behind the drop boards)."""
        return (i0 <= i < i1 and no <= j < no + nw) or (i == i1 and j in jc)

    m.grid(rows, "NonSkid", lambda p: (0, 0, 1), skip=skip)
    # the transom's top: the deck's camber over the straight top of the transom, closed
    m.polygon(rows[0], "Deck", (-1, 0, 0))
    return m.finish(mats, weld=1e-5)


def build_rubrail(mats, sides=12):
    """A rounded vinyl strip over the joint, its top 'cap' over the deck's edge, 'proud' out of the topsides; its inner
    half sits inside the hull, so the joint is covered from both sides. It runs up the port side, across the transom
    (turning its corners on corner_radius) and up the starboard side, tapering away toward the stem."""
    R = DK.D["rubrail"]
    rz, ry = 0.5 * R["height"], R["proud"]
    xs = [x for x in deck_rows() if x < H.STEM_X - 0.04]
    xs = xs[::2] + ([xs[-1]] if len(xs) % 2 == 0 else [])
    half = [(x, DK.hull_half_breadth(x, H.sheer_z(x) - rz)) for x in xs]
    yt = half[0][1]
    # the plan path: corners at the transom rounded on arcs (no fold where the rail's reach passes the corner)
    port = [(x, -y) for x, y in reversed(half)]
    stbd = list(half)
    rc = R["corner_radius"]
    c_port = DK.fillet(port[-2], port[-1], (H.TRANSOM_X, 0.0), rc, 8)
    c_stbd = DK.fillet((H.TRANSOM_X, 0.0), stbd[0], stbd[1], rc, 8)
    lo, hi = c_port[-1][1], c_stbd[0][1]
    port = [p for p in port[:-1] if p[0] > c_port[0][0] + 1e-6]
    stbd = [p for p in stbd[1:] if p[0] > c_stbd[-1][0] + 1e-6]
    across = [(H.TRANSOM_X, lo + (hi - lo) * k / 16) for k in range(1, 16)]
    path = port + c_port + across + c_stbd + stbd
    taper_x = H.STEM_X - 0.04 - R["stem_taper"]

    def size(x):
        """The rail's section toward the stem: full aft of the taper, a third of it at its end."""
        t = DK.H.smooth(max(0.0, (x - taper_x) / R["stem_taper"])) if x > taper_x else 0.0
        return 1 - 0.67 * t

    rings = []
    for k, (x, y) in enumerate(path):
        a, b = path[max(k - 1, 0)], path[min(k + 1, len(path) - 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        n = math.hypot(tx, ty)
        ox, oy = -ty / n, tx / n          # outward in plan: the path runs aft up the port side, across, forward
        f = size(x)
        zc = H.sheer_z(max(x, H.TRANSOM_X)) - rz * f + R["cap"]
        ring = []
        for j in range(sides + 1):
            ang = 2 * math.pi * j / sides
            ring.append((x + ox * ry * f * math.cos(ang), y + oy * ry * f * math.cos(ang), zc + rz * f * math.sin(ang)))
        rings.append((ring, (x, y, zc)))
    mm = Mesh("C22_Rubrail")
    vs = [[mm.v(p) for p in r] for r, _ in rings]
    for i in range(len(rings) - 1):
        ring, c = rings[i]
        for j in range(sides):
            q = [vs[i][j], vs[i][j + 1], vs[i + 1][j + 1], vs[i + 1][j]]
            p = ring[j]
            mm.face(q, "Rubrail", (p[0] - c[0], p[1] - c[1], p[2] - c[2]))
    for r, _ in (rings[0], rings[-1]):
        mm.face([mm.v(p) for p in r[:-1]], "Rubrail", (1, 0, 0), flat=True)
    return mm.finish(mats, weld=1e-6)


def build_well(mats):
    """The cockpit: one cross-section swept from its aft end to the bulkhead, its aft end closed."""
    m = Mesh("C22_Well")
    hw, fw, sole = CK["half_width"], CK["footwell_half_width"], CK["sole_z"]
    xs = [x for x in deck_rows() if CK["x"][0] <= x <= CK["x"][1]]

    ys = [hw * f for f in WELL_SHARES]                   # the seats' and sole's columns: the deck's, vertex for vertex
    seat_l = [y for y in ys if y <= -fw + 1e-9]
    sole_c = [y for y in ys if -fw - 1e-9 <= y <= fw + 1e-9]
    seat_r = [y for y in ys if y >= fw - 1e-9]

    def section(x):
        dz, sz = DK.deck_z(x, hw), DK.seat_z(x)
        pts = [(-hw, lerp(dz, sz, k / 4)) for k in range(4)]
        pts += [(y, sz) for y in seat_l[:-1]]
        pts += [(-fw, lerp(sz, sole, k / 4)) for k in range(4)]
        pts += [(y, sole) for y in sole_c[:-1]]
        pts += [(fw, lerp(sole, sz, k / 4)) for k in range(4)]
        pts += [(y, sz) for y in seat_r[:-1]]
        pts += [(hw, lerp(sz, dz, k / 4)) for k in range(5)]
        return [(x, y, z) for y, z in pts]

    def inward(p):
        """The well's skin faces into the cockpit: away from the nearest wall's outside."""
        x, y, z = p
        sz = DK.seat_z(x)
        if abs(abs(y) - hw) < 1e-4:
            return (0, -math.copysign(1, y), 0)
        if abs(abs(y) - fw) < 1e-4 and z < sz - 1e-4:
            return (0, -math.copysign(1, y), 0)
        return (0, 0, 1)

    rows = [section(x) for x in xs]
    m.grid(rows, lambda mid, o: "NonSkid" if o[2] > 0.5 else "Deck", inward, flat=True)
    # the aft end: columns from the seats and sole up to the deck's camber, on the walls', seats' and deck's points
    x = CK["x"][0]
    sz, k4 = DK.seat_z(x), [k / 4 for k in range(5)]

    def column(y, low):
        """From the seat (or, low, from the sole through the seat's height) up to the deck at y."""
        dz = DK.deck_z(x, y)
        zs = ([lerp(sole, sz, k) for k in k4[:-1]] if low else []) + [lerp(sz, dz, k) for k in k4]
        return [(x, y, z) for z in zs]

    for part, low in ((seat_l, False), (sole_c, True), (seat_r, False)):
        m.grid([column(y, low) for y in part], "Deck", lambda p: (1, 0, 0), flat=True)
    # the footwell's front, under the companionway's sill
    x = CK["x"][1]
    bz = DK.bridge_z()
    m.grid([[(x, y, lerp(sole, bz, k)) for k in k4] for y in sole_c], "Deck", lambda p: (-1, 0, 0), flat=True)
    return m.finish(mats)


def trunk_lattices():
    """The top's and sides' shared grid: s along (0 at the companionway), v across, t up the side."""
    vi = DK.hole_v()
    ss = [DK.S1 * k / 24 for k in range(24)] + [DK.S1 + (1 - DK.S1) * k / 16 for k in range(17)]
    vin = [vi * k / 10 for k in range(10)] + [vi]
    vout = [vi + (1 - vi) * 0.3, 1.0]       # the column nearest the edge stays clear of the corner's rounding
    vs = [-v for v in reversed(vout)] + [-v for v in reversed(vin[1:])] + vin + vout
    ts = [k / 10 for k in range(11)]
    return ss, vs, ts, vi


def build_cabin(mats):
    m = Mesh("C22_Cabin")
    ss, vs, ts, vi = trunk_lattices()
    x0 = CB["x"][0]
    up = lambda p: (0, 0, 1)                                                  # noqa: E731
    # the top, open over the pop-top (s up to S1, |v| under vi)
    rows = [[DK.trunk_point(DK.top_x(s, v), v, 1.0) for v in vs] for s in ss]
    k1 = ss.index(DK.S1)
    jv = [j for j in range(len(vs) - 1) if abs(vs[j]) < vi + 1e-9 and abs(vs[j + 1]) < vi + 1e-9]
    m.grid(rows, "NonSkid", up, skip=lambda i, j: i < k1 and j in jv)
    # the opening's lip, turned down inside
    edge = [rows[i][vs.index(-vi)] for i in range(k1 + 1)]
    edge += [rows[k1][j] for j in range(vs.index(-vi) + 1, vs.index(vi))]
    edge += [rows[i][vs.index(vi)] for i in range(k1, -1, -1)]
    lip = [[p, (p[0], p[1], p[2] - LIP)] for p in edge]
    p1 = DK.top_x(DK.S1, 0.0)
    m.grid(lip, "Deck", lambda p: (-1, 0, 0) if abs(p[0] - p1) < 1e-4 else (0, -math.copysign(1, p[1]), 0), flat=True)
    # the sides
    for side in (-1, 1):
        rows = [[DK.trunk_point(DK.side_x(u, t), side, t) for t in ts] for u in ss]
        m.grid(rows, "Deck", lambda p, s=side: (0, s, 0.2))
    # the front
    rows = [[DK.trunk_point(DK.front_foot_x(v) - CB["front_rake"] * t, v, t) for t in ts] for v in vs]
    m.grid(rows, "Deck", lambda p: (1, 0, 0.3))
    # the companionway bulkhead: each side of the opening (narrower at the sill), from the seats' height to the top
    bz = DK.bridge_z()
    hb_, ht_ = CW["half_width_bottom"], CW["half_width_top"]
    tz = DK.top_z(x0, ht_)
    for side in (-1, 1):
        outer = [(x0, side * CK["half_width"], bz)]
        outer += [DK.trunk_point(x0, side, t) for t in ts]
        outer += [DK.trunk_point(x0, side * abs(v), 1.0) for v in reversed(vs) if ht_ / DK.trunk_edge(x0) < v < 1]
        outer.append((x0, side * ht_, tz))
        m.strip(outer, [(x0, side * hb_, bz), (x0, side * ht_, tz)], "Deck", (-1, 0, 0))
    # the opening's sill and jambs: the bulkhead's thickness, so the drop boards stand in a frame, not on an edge
    d = SILL_DEPTH
    m.polygon([(x0, -hb_, bz), (x0 + d, -hb_, bz), (x0 + d, hb_, bz), (x0, hb_, bz)], "Deck", (0, 0, 1))
    for side in (-1, 1):
        m.polygon([(x0, side * hb_, bz), (x0 + d, side * hb_, bz), (x0 + d, side * ht_, tz), (x0, side * ht_, tz)],
                  "Deck", (0, -side, 0))
    return round_corners(m.finish(mats), CB["corner_radius"])


def round_corners(ob, r):
    """Round the trunk's top, front and side corners on radius r: bevel the skin's creases, leaving the opening's lip,
    the bulkhead's outline and the foot on the deck sharp. The grid keeps its lines next to each crease more than r
    away (trunk_lattices), so the bevel needs no clamping and keeps its full radius."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    x0 = CB["x"][0]
    pick = []
    for e in bm.edges:
        if len(e.link_faces) != 2 or e.calc_face_angle(0) < math.radians(35):
            continue
        pts = [(v.co.x, -v.co.y) for v in e.verts]
        if all(x < x0 + 1e-4 for x, _ in pts):
            continue                                            # the bulkhead's own edges
        if all(abs(y) > DK.trunk_edge(max(x, x0)) - 0.002 or x > PT["x"][1] + 0.2 for x, y in pts):
            pick.append(e)
    bmesh.ops.bevel(bm, geom=pick, offset=r, offset_type="OFFSET", segments=4, profile=0.5, affect="EDGES",
                    clamp_overlap=False)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])     # where the rounding meets the bulkhead
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def build_ports(mats):
    W = DK.D["windows"]
    m = Mesh("C22_Ports")
    off, fr = 0.003, 0.5 * W["frame"]
    for side in (-1, 1):
        for k in range(len(W["ports"])):
            outline = DK.port_outline(k)
            pts, nrm = [], []
            for x, t in outline:
                p = Vector(DK.trunk_point(x, side, t))
                dx = Vector(DK.trunk_point(x + 1e-3, side, t)) - p
                dt = Vector(DK.trunk_point(x, side, t + 1e-3)) - p
                n = dx.cross(dt).normalized()
                if n.y * side < 0:
                    n = -n
                pts.append(p)
                nrm.append(n)
            glass = [tuple(p + n * off) for p, n in zip(pts, nrm)]
            c = sum((Vector(g) for g in glass), Vector()) / len(glass)
            nc = sum(nrm, Vector()).normalized()
            for a, b in zip(glass, glass[1:] + glass[:1]):
                m.face([m.v(c), m.v(a), m.v(b)], "CabinWindow", tuple(nc), flat=True)
            # the frame: a small tube round the outline
            ring = []
            npt = len(pts)
            for i in range(npt + 1):
                p, n = pts[i % npt], nrm[i % npt]
                tang = (pts[(i + 1) % npt] - pts[(i - 1) % npt]).normalized()
                b = n.cross(tang).normalized()
                ring.append([tuple(p + n * (off + fr * math.sin(2 * math.pi * s / 8)) + b * fr *
                                   math.cos(2 * math.pi * s / 8)) for s in range(9)])
            vs = [[m.v(q) for q in r] for r in ring]
            for i in range(npt):
                for s in range(8):
                    q = [vs[i][s], vs[i][s + 1], vs[i + 1][s + 1], vs[i + 1][s]]
                    mid = Vector(ring[i][s])
                    m.face(q, "Aluminium", tuple(mid - pts[i % npt] - nrm[i % npt] * off))
    return m.finish(mats, weld=1e-7)


def cw_half(z):
    """The companionway's half-width at height z: half_width_bottom at the sill to half_width_top at the top."""
    x0 = CB["x"][0]
    bz, tz = DK.bridge_z(), DK.top_z(x0, CW["half_width_top"])
    return lerp(CW["half_width_bottom"], CW["half_width_top"], (z - bz) / (tz - bz))


def build_drop_boards(mats):
    """Teak boards in channels behind the jambs (each 6 mm wider a side than the opening at its height), a backing
    strip behind their joints so they show a groove, not a slit."""
    m = Mesh("C22_DropBoards")
    x0 = CB["x"][0]
    bz, tz = DK.bridge_z(), DK.top_z(x0, CW["half_width_top"]) - 0.004
    n, gap, th, lap = CW["boards"], 0.003, 0.02, 0.006
    xa, xb = x0 + SILL_DEPTH * 0.3, x0 + SILL_DEPTH * 0.3 + th
    for i in range(n):
        z0 = lerp(bz, tz, i / n) + (gap if i else 0)
        z1 = lerp(bz, tz, (i + 1) / n) if i < n - 1 else DK.top_z(x0, 0.0) - 0.002   # the top one up to the crown
        hexa(m, trapezoid(xa, xb, z0, z1, lambda z: cw_half(min(z, tz)) + lap), "Teak")
        if i:                                                  # the backing strip behind the joint below this board
            zj = lerp(bz, tz, i / n)
            hexa(m, trapezoid(xb, xb + 0.004, zj - 0.012, zj + 0.012, lambda z: cw_half(z) + lap), "Teak")
    return m.finish(mats)


def trapezoid(xa, xb, z0, z1, half):
    """The 8 corners of a block from xa to xb, z0 to z1, half(z) a side (box()'s corner order)."""
    return [(xa if i & 1 == 0 else xb, (-1 if i & 2 == 0 else 1) * half(z0 if i & 4 == 0 else z1),
             z0 if i & 4 == 0 else z1) for i in range(8)]


def hexa(m, c, slot):
    """A six-sided block from its 8 corners (bit 0 x, bit 1 y, bit 2 z), each face turned outward."""
    mid = [sum(p[a] for p in c) / 8 for a in range(3)]
    vs = [m.v(p) for p in c]
    for f in ((0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)):
        ctr = [sum(c[i][a] for i in f) / 4 for a in range(3)]
        m.face([vs[i] for i in f], slot, tuple(p - q for p, q in zip(ctr, mid)), flat=True)


def box(m, lo, hi, slot):
    hexa(m, [(lo[0] if i & 1 == 0 else hi[0], lo[1] if i & 2 == 0 else hi[1], lo[2] if i & 4 == 0 else hi[2])
             for i in range(8)], slot)


def build_fore_hatch(mats):
    m = Mesh("C22_ForeHatch")
    F = DK.D["fore_hatch"]
    x, (lx, ly) = F["x"], F["size"]
    base = min(DK.deck_z(x + sx * lx / 2, ly / 2) for sx in (-1, 1)) - 0.01     # under the deck at every corner
    box(m, (x - lx / 2, -ly / 2, base), (x + lx / 2, ly / 2, DK.deck_z(x, 0) + 0.06), "Deck")
    ob = m.finish(mats)
    return bevel(ob, 0.008)


def bevel(ob, w):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=w, segments=2, affect="EDGES")
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def lid(m, lift):
    """The pop-top's lid, a closed moulding: its skin LID_GAP over the trunk top's crown, covering the opening and its
    flange; the flange turned down to the top round the sides and front (FLANGE_SINK into it) and over the bulkhead at
    the aft end; its underside LID_THICK under the skin, the flange LID_THICK thick."""
    x0, x1, fl = CB["x"][0] - 0.004, PT["x"][1] + PT["flange"], PT["flange"]
    vi = DK.hole_v()
    nx, ny = 24, 20

    def rows_at(inset, dz):
        rows = []
        for i in range(nx + 1):
            x = lerp(x0 + inset, x1 - inset, i / nx)
            yw = vi * DK.trunk_edge(x) + fl - inset
            rows.append([(x, y, DK.top_z(x, y) + LID_GAP + lift + dz) for y in [lerp(-yw, yw, j / ny)
                                                                                for j in range(ny + 1)]])
        return rows

    def ring_of(rows):
        ring = [rows[0][j] for j in range(ny, -1, -1)] + [rows[i][0] for i in range(1, nx + 1)]
        ring += [rows[nx][j] for j in range(1, ny + 1)] + [rows[i][ny] for i in range(nx - 1, 0, -1)]
        return ring + [ring[0]]

    def drop(p):
        aft = p[0] < x0 + LID_THICK + 1e-6
        return DK.top_z(p[0], p[1]) + lift - (PT["flange"] if aft else FLANGE_SINK)

    def facing(sign, xa, xb):
        return lambda p: (tuple(sign * c for c in ((-1, 0, 0) if p[0] < xa + 1e-6 else (1, 0, 0) if p[0] > xb - 1e-6
                                                    else (0, math.copysign(1, p[1]), 0))))

    top = rows_at(0.0, 0.0)
    under = rows_at(LID_THICK, -LID_THICK)
    m.grid(top, "NonSkid", lambda p: (0, 0, 1))
    m.grid(under, "Deck", lambda p: (0, 0, -1))
    outer, inner = ring_of(top), ring_of(under)
    ob_ = [(p, (p[0], p[1], drop(p))) for p in outer]
    ib_ = [(p, (p[0], p[1], drop((p[0] - LID_THICK, p[1]) if p[0] < x0 + LID_THICK + 1e-6 else p))) for p in inner]
    m.grid([list(r) for r in ob_], "Deck", facing(1, x0, x1), flat=True)
    m.grid([list(r) for r in ib_], "Deck", facing(-1, x0 + LID_THICK, x1 - LID_THICK), flat=True)
    m.grid([[o[1], i[1]] for o, i in zip(ob_, ib_)], "Deck", lambda p: (0, 0, -1), flat=True)
    # the sliding hatch on the lid's aft end
    zc = DK.top_z(x0, 0) + LID_GAP + lift
    box(m, (x0 - 0.01, -HATCH_HALF, DK.top_z(x0, HATCH_HALF) + LID_GAP + lift - 0.01),
        (x0 + CW["hatch_length"], HATCH_HALF, zc + HATCH_RISE), "Deck")


def build_pop_top(mats):
    m = Mesh("C22_PopTop")
    lid(m, 0.0)
    return m.finish(mats)


def build_pop_top_raised(mats):
    m = Mesh("C22_PopTopRaised")
    lift = PT["lift"]
    lid(m, lift)
    vi = DK.hole_v()
    x0, p1 = CB["x"][0], PT["x"][1]
    # the canvas skirt, all round the opening: up its sides and front from the trunk top, and across its aft end from
    # the bulkhead's top, to the raised lid's underside; two-sided (cloth is seen from the cabin too)
    e = lambda x: vi * DK.trunk_edge(x)                                       # noqa: E731
    xa = x0 + 0.002
    edge = [(xa, y) for y in [lerp(e(xa), -e(xa), k / 12) for k in range(12)]]
    edge += [(x, -e(x)) for x in [lerp(x0 + 0.002, p1, k / 16) for k in range(17)]]
    edge += [(p1, y) for y in [lerp(-e(p1), e(p1), k / 12) for k in range(1, 12)]]
    edge += [(x, e(x)) for x in [lerp(p1, x0 + 0.002, k / 16) for k in range(17)]]
    top = lambda x, y: DK.top_z(x, y) + LID_GAP + lift - LID_THICK + 0.002   # noqa: E731

    def out(p):
        return (-1, 0, 0) if p[0] < x0 + 0.01 else (1, 0, 0) if p[0] > p1 - 0.005 else (0, math.copysign(1, p[1]), 0)

    for sgn, off in ((1, 0.0), (-1, 0.002)):
        cloth = []
        for x, y in edge:
            o = out((x, y, 0))
            xx, yy = x - o[0] * off, y - o[1] * off
            cloth.append([(xx, yy, DK.top_z(xx, yy) - 0.002), (xx, yy, top(xx, yy))])
        m.grid(cloth, "SailCover", lambda p, s=sgn: tuple(s * c for c in out(p)), flat=True)
    # four stainless legs on the trunk top just outside the opening, under the lid's flange
    for x in (x0 + 0.06, p1 - 0.06):
        for sd in (-1, 1):
            y = sd * (e(x) + 0.012)
            z0, z1 = DK.top_z(x, y) - 0.002, top(x, y)
            r = 0.008
            ring0 = [(x + r * math.cos(a), y + r * math.sin(a), z0) for a in [2 * math.pi * k / 8 for k in range(9)]]
            ring1 = [(p[0], p[1], z1) for p in ring0]
            m.grid([ring0, ring1], "Stainless", lambda p, x=x, y=y: (p[0] - x, p[1] - y, 0))
    return m.finish(mats)


def build_all(mats, raised=False):
    """Every part. raised: the pop-top up instead (named C22_PopTop, so the shape loop draws it; no closed lid).
    Otherwise both are built and the raised one is hidden."""
    obs = [build_deck(mats), build_rubrail(mats), build_well(mats), build_cabin(mats), build_ports(mats),
           build_drop_boards(mats), build_fore_hatch(mats)]
    if raised:
        ob = build_pop_top_raised(mats)
        ob.name = ob.data.name = "C22_PopTop"
        return obs + [ob]
    up = build_pop_top_raised(mats)
    up.hide_render = up.hide_viewport = True
    return obs + [build_pop_top(mats), up]
