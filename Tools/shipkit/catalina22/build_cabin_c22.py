"""The Catalina 22's cabin below as meshes (docs/c22-8), from cabin_c22.py's layout. Run by build_c22.py after the hull,
deck, keel and rig, since the liner is drawn from those meshes.

Objects (Blender frame, X forward, Y to port, Z up):
  C22_Interior_Liner         the hull's and cockpit well's skins drawn again inside their laminate, facing in
  C22_Interior_Headliner     the deck's and trunk's (the deck's skin under the trunk is cut away first: it was never
                             seen before, and it roofed the cabin), and the windows' reveals through the trunk's side
                             (the trunk, C22_Cabin, is cut open behind each window: the cabin shows through its glass)
  C22_Interior_PortaPotti    the porta-potti under the V-berth, on its floor board
  C22_Interior               sole, bulkheads (the main one with its doorway and compression post, and one closing each
                             end of the liner), berth and seat fronts, the step and the keel winch's socket in it,
                             the teak cap on the keel trunk, the curtain on its rod
  C22_Interior_Cushions      every cushion, its edges rounded
  C22_Interior_Table         the dinette's table up, on its leg (C22_Interior_TableDown: lowered to make the berth, with
                             its filler cushion; hidden)
  C22_Interior_Galley        the galley pushed home under the port cockpit seat (C22_Interior_GalleyOut: pulled out;
                             hidden)
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cabin_c22 as CC  # noqa: E402
import deck_c22 as DK  # noqa: E402
import keel_c22 as KC  # noqa: E402
from build_deck_c22 import Mesh, box  # noqa: E402
import build_keel_c22 as BK  # noqa: E402
import build_rig_c22 as BR  # noqa: E402
import build_sails_c22 as BS  # noqa: E402

CUSHION_R = 0.018        # the cushions' rounded edges
EDGE_DEG = 30.0          # an edge sharper than this between two faces is a corner (rounded on cushions)
SHARP_DEG = 35.0         # an edge sharper than this on the liner and the keel trunk is drawn sharp


# ------------------------------------------------------------------ the liner

def in_trunk_foot(x, y, pad=0.0):
    """True inside the trunk's footprint on the deck (pad metres inside its edge)."""
    if not (DK.CB["x"][0] + pad <= x):
        return False
    b = DK.trunk_base(x) - pad
    if abs(y) > b or b <= 0:
        return False
    return x <= DK.front_foot_x(min(1.0, abs(y) / DK.trunk_base(x))) - pad


def cut_trunk_floor(ob):
    """Cut the deck's skin away under the cabin trunk, where it was never seen but now roofs the cabin: delete the faces
    inside the trunk's footprint, then move the cut's ragged vertices out onto the footprint's edge."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    gy = lambda v: -v.co.y
    dead = [f for f in bm.faces if all(in_trunk_foot(v.co.x, gy(v)) for v in f.verts)]
    bmesh.ops.delete(bm, geom=dead, context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    for v in bm.verts:
        x, y = v.co.x, gy(v)
        if in_trunk_foot(x, y):
            b = DK.trunk_base(x)
            xf = DK.front_foot_x(min(1.0, abs(y) / b))
            if xf - x < b - abs(y):                          # nearer the front: out to it
                v.co.x = xf
            else:
                v.co.y = -math.copysign(b, y)
            v.co.z = DK.deck_z(v.co.x, gy(v))
    bm.to_mesh(ob.data)
    bm.free()
    return len(dead)


def in_outline(p, poly):
    """Point p inside the closed polygon poly (2D, even-odd rule)."""
    x, y = p
    inside = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (x1 - x0) * (y - y0) / (y1 - y0):
            inside = not inside
    return inside


def side_xt(co, side):
    """A Blender-frame point on the trunk's side as (x, t) for deck_c22.trunk_point (t 0 at the deck, 1 at the top's
    edge), or None if it isn't on that side."""
    x, y, z = co.x, -co.y, co.z
    if y * side <= 0 or not (DK.CB["x"][0] - 1e-4 <= x <= DK.front_foot_x(1.0) + 1e-4):
        return None
    b, e = DK.trunk_base(x), DK.trunk_edge(x)
    z0, z1 = DK.deck_z(x, side * b), DK.top_z(x, side * e)
    t = (z - z0) / (z1 - z0)
    if abs(abs(y) - (b + (e - b) * t)) > 2e-3:
        return None
    return x, t


def cut_ports(ob):
    """Open the trunk's side behind each window (deck_c22.port_outline), so the cabin shows through the glass and the
    cabin's light through it: the side's faces near the window are deleted and the gap between the hole's edge and the
    window's outline is filled again (zipped round the window's middle). Returns each outline's vertex indices in ob,
    for the reveals."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    loops = []
    for side in (-1, 1):
        for k in range(len(DK.D["windows"]["ports"])):
            out = DK.port_outline(k)
            xs, ts = [p[0] for p in out], [p[1] for p in out]
            bx, bt = (min(xs) - 0.012, max(xs) + 0.012), (min(ts) - 0.03, max(ts) + 0.03)
            xm, tm = 0.5 * (bx[0] + bx[1]), 0.5 * (bt[0] + bt[1])
            sx, st = 0.5 * (bx[1] - bx[0]), 0.5 * (bt[1] - bt[0])
            xt = {v: side_xt(v.co, side) for v in bm.verts}

            def ang(p):                                  # round the window's middle, its box squared up
                return math.atan2((p[1] - tm) / st, (p[0] - xm) / sx)

            def near(f):
                q = [xt[v] for v in f.verts]
                if any(a is None for a in q):
                    return False
                return (min(a[0] for a in q) < bx[1] and max(a[0] for a in q) > bx[0] and
                        min(a[1] for a in q) < bt[1] and max(a[1] for a in q) > bt[0])
            dead = [f for f in bm.faces if near(f)]
            mat = dead[0].material_index
            touched = {v for f in dead for v in f.verts}
            bmesh.ops.delete(bm, geom=dead, context="FACES_ONLY")
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
            A = sorted((v for v in touched if v.is_valid), key=lambda v: ang(xt[v]))
            B = [bm.verts.new(DK.trunk_point(x, side, t)) for x, t in out]
            for v in B:
                v.co.y = -v.co.y
            bxt = {v: p for v, p in zip(B, out)}
            B = sorted(B, key=lambda v: ang(bxt[v]))
            aa = [ang(xt[v]) for v in A]
            ba = [ang(bxt[v]) for v in B]
            i = j = 0
            tris = []
            while i < len(A) or j < len(B):
                na = aa[(i + 1) % len(A)] + (2 * math.pi if i + 1 >= len(A) else 0)
                nb = ba[(j + 1) % len(B)] + (2 * math.pi if j + 1 >= len(B) else 0)
                if j >= len(B) or (i < len(A) and na <= nb):
                    tris.append((A[i % len(A)], B[j % len(B)], A[(i + 1) % len(A)]))
                    i += 1
                else:
                    tris.append((A[i % len(A)], B[j % len(B)], B[(j + 1) % len(B)]))
                    j += 1
            for tri in tris:
                f = bm.faces.new(tri)
                f.material_index = mat
                f.normal_update()
                if -f.normal.y * side < 0:
                    f.normal_flip()
            loops.append(B)
    bm.verts.index_update()
    order = [[v.index for v in L] for L in loops]
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return order


def reveals(m, ob, loops, t, slot):
    """The window openings' sides through the laminate, from each outline on the trunk's skin to t inside it, facing
    into the opening."""
    me = ob.data
    for L in loops:
        ps = [me.vertices[i].co.copy() for i in L]
        ns = [me.vertices[i].normal.copy() for i in L]
        c = sum(ps, Vector()) / len(ps)
        n = len(ps)
        for a in range(n):
            b = (a + 1) % n
            q = [ps[a], ps[b], ps[b] - ns[b] * t, ps[a] - ns[a] * t]
            f = m.bm.faces.new([m.bm.verts.new(p) for p in q])
            f.material_index = m.slot(slot)
            f.normal_update()
            mid = sum(q, Vector()) / 4
            if f.normal.dot(c - mid) < 0:
                f.normal_flip()


def inner_copy(m, ob, t, slot, keep=None, foot=None):
    """ob's faces again, t inside along its vertex normals, facing the other way, into the Mesh m (game frame). foot:
    a test for vertices to move straight down by foot's depth instead (the trunk's foot, to meet the deck's liner)."""
    me = ob.data
    vs = [v.co - v.normal * t for v in me.vertices]
    if foot is not None:
        test, depth = foot
        vs = [v.co - Vector((0, 0, depth)) if test(v.co) else q for v, q in zip(me.vertices, vs)]
    for p in me.polygons:
        if keep and not keep(p):
            continue
        pts = [vs[i] for i in reversed(p.vertices)]
        f = m.bm.faces.new([m.bm.verts.new(q) for q in pts])
        f.material_index = m.slot(slot)
    return m


def sharpen(ob, deg=SHARP_DEG):
    """Mark ob's edges sharper than deg as sharp, so smooth shading doesn't round a corner into a bolster."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    for e in bm.edges:
        if len(e.link_faces) == 2 and math.degrees(e.link_faces[0].normal.angle(e.link_faces[1].normal, 0.0)) > deg:
            e.smooth = False
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def build_liner(mats):
    """The hull's and the well's insides (C22_Interior_Liner) and the deck's and trunk's (C22_Interior_Headliner)."""
    m = Mesh("C22_Interior_Liner")
    x0, x1 = CC.LN["x"]
    inner_copy(m, bpy.data.objects["C22_Hull"], CC.LN["hull"], "Liner",
               keep=lambda p: x0 <= p.center.x <= x1 and len(p.vertices) == 4)
    inner_copy(m, bpy.data.objects["C22_Well"], CC.LN["deck"], "Liner")
    deck = bpy.data.objects["C22_Deck"]
    n = cut_trunk_floor(deck)
    cabin = bpy.data.objects["C22_Cabin"]
    loops = cut_ports(cabin)
    h = Mesh("C22_Interior_Headliner")
    inner_copy(h, deck, CC.LN["deck"], "Headliner")

    def at_foot(co):                              # the trunk's foot on the deck: down to the deck liner's cut edge
        return co.x > DK.CB["x"][0] + 1e-3 and abs(co.z - DK.deck_z(co.x, -co.y)) < 2e-3
    inner_copy(h, cabin, CC.LN["cabin"], "Headliner", foot=(at_foot, CC.LN["deck"]))
    reveals(h, cabin, loops, CC.LN["cabin"], "Headliner")
    print(f"C22 cabin: cut {n} deck faces from under the trunk, opened {len(loops)} windows")
    sharpen(bpy.data.objects["C22_KeelStub"])            # the keel trunk in the cabin: a box, not a bolster
    return [sharpen(m.finish(mats, weld=1e-5)), sharpen(h.finish(mats, weld=1e-5))]


# ------------------------------------------------------------------ the pieces

def solid(m, s, slot=None):
    """A cabin_c22.Solid as a closed block: four sides swept along its stations, both ends capped."""
    slot = slot or s.slot
    rows = []
    for x in s.stations():
        (l0, h0), (l1, h1) = s.across(x, s.z0), s.across(x, s.z1)
        rows.append([(x, l0, s.z0), (x, h0, s.z0), (x, h1, s.z1), (x, l1, s.z1)])
    ring = [[r[k] for r in rows] for k in range(4)]
    ring.append(ring[0])
    for k in range(4):
        a, b = ring[k], ring[k + 1]
        m.grid([a, b], slot, lambda mid, k=k: ((0, 0, -1), (0, 1, 0), (0, 0, 1), (0, -1, 0))[k])
    m.polygon(rows[0], slot, (-1, 0, 0))
    m.polygon(rows[-1], slot, (1, 0, 0))


def round_edges(ob, r):
    """Round the corners (edges sharper than EDGE_DEG) of every block in ob."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    sharp = [e for e in bm.edges if len(e.link_faces) == 2 and
             math.degrees(e.link_faces[0].normal.angle(e.link_faces[1].normal)) > EDGE_DEG]
    bmesh.ops.bevel(bm, geom=sharp, offset=r, segments=3, affect="EDGES", profile=0.5, clamp_overlap=True)
    bm.to_mesh(ob.data)
    bm.free()
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def slab_x(m, pts, x, thick, slot, side):
    """A flat panel across the boat at x, `thick` fore and aft: the outline pts ((y, z), starboard half), mirrored to
    port if side is -1."""
    s = 1 if side > 0 else -1
    a = [(x - thick / 2, s * y, z) for y, z in pts]
    b = [(x + thick / 2, s * y, z) for y, z in pts]
    m.polygon(a, slot, (-1, 0, 0))
    m.polygon(b, slot, (1, 0, 0))
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    o = 1 if area > 0 else -1                                  # counter-clockwise in (y, z): out is (dz, -dy)
    for i in range(n):
        j = (i + 1) % n
        dy, dz = pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]
        m.face([m.v(a[i]), m.v(a[j]), m.v(b[j]), m.v(b[i])], slot, (0, s * o * dz, -o * dy), flat=True)


def bulkhead_outline(x):
    """The starboard wing of the main bulkhead at x with half the doorway's header: from the doorway's foot out along
    the sole, up the hull's liner, in under the deck, up the trunk's side, in under its top to the centreline, then
    down to the doorway's top and back to its side. (y, z) pairs."""
    BH, zs = CC.BH, CC.SO["z"]
    dw = BH["door_half_width"]
    edge_z = DK.deck_z(x, DK.H.half_beam(x)) - CC.LN["deck"]
    pts = [(dw, zs)]
    n = 24
    for i in range(n + 1):
        z = zs + (edge_z - 0.004 - zs) * i / n
        pts.append((CC.fit(x, z), z))
    tb = DK.trunk_base(x) - CC.LN["cabin"]
    for i in range(1, 9):
        y = pts[-1][0] + (tb - pts[-1][0]) * i / 8
        pts.append((y, CC.deck_under(x, y) - CC.CLEAR))
    te = DK.trunk_edge(x) - CC.LN["cabin"]
    z_top_edge = CC.top_under(x, te) - CC.CLEAR
    pts.append((te - CC.CLEAR, z_top_edge))
    for i in range(1, 9):
        y = te * (1 - i / 8)
        pts.append((max(y, 0.0), CC.top_under(x, y) - CC.CLEAR))
    pts += [(0.0, BH["door_top"]), (dw, BH["door_top"])]
    return pts


def end_outline(x):
    """A bulkhead right across the liner at x, starboard half: from the bottom on the centreline out along the hull's
    liner, then in under whatever is over it (deck, cockpit seat, footwell) to the centreline. (y, z) pairs."""
    zb = -1.5
    while CC.fit(x, zb) <= 0.002:
        zb += 0.002
    edge_z = DK.deck_z(x, DK.H.half_beam(x)) - CC.LN["deck"] - 0.004
    pts = [(0.0, zb)]
    n = 30
    for i in range(n + 1):
        z = zb + (edge_z - zb) * i / n
        pts.append((CC.fit(x, z), z))
    y = pts[-1][0]
    while y > 0.004:
        y = max(0.0, y - 0.005)
        pts.append((y, min(CC.ceiling(x, y) - CC.CLEAR, edge_z)))
    return pts


def build_interior(mats, S):
    m = Mesh("C22_Interior")
    for s in S:
        if s.kind in ("cushion",) or s.name in ("Table", "TableCushion", "Galley"):
            continue
        if s.name == "PortaPotti":
            continue
        solid(m, s)
    # a teak tread on the step
    STP = CC.STP
    box(m, (STP["x"][0] + 0.005, -STP["half_width"] + 0.01, STP["top"]), (STP["x"][1] - 0.005, STP["half_width"] - 0.01,
                                                                          STP["top"] + 0.012), "Teak")
    # the bulkhead and its doorway
    BH = CC.BH
    pts = bulkhead_outline(BH["x"])
    for sd in (1, -1):
        slab_x(m, pts, BH["x"] - BH["thick"] / 2 - 0.0, BH["thick"], "Laminate", sd)
    # the liner's ends: a bulkhead aft of the quarter berth's foot and the forepeak's forward of the V-berth, inside the
    # liner's last faces
    for x in (CC.LN["x"][0] + 0.06, CC.LN["x"][1] - 0.06):
        pts = end_outline(x)
        for sd in (1, -1):
            slab_x(m, pts, x, 0.015, "Laminate", sd)
    # the compression post under the mast step, on the trunk
    px = DK.MAST_X
    BR.rod(m, (px, 0.0, CC.trunk_out_top(px) - 0.002), (px, 0.0, CC.top_under(px, 0.0) + 0.002), BH["post_d"] / 2,
           "Aluminium", 16)
    # the curtain: a rod across the doorway, the cloth drawn to port in folds, clear of the dinette's cushion
    rz = BH["door_top"] - 0.04
    rx = BH["x"] - BH["thick"] - 0.012
    dw = BH["door_half_width"]
    BR.rod(m, (rx, -dw - 0.03, rz), (rx, dw + 0.03, rz), 0.006, "Stainless", 8)
    low = max(rz - CC.VB["curtain_drop"], CC.DN["seat_top"] + CC.DN["cushion"] + 0.03)
    nu, nv = 36, 6
    rows = []
    for j in range(nv + 1):
        z = rz - 0.012 - (rz - 0.012 - low) * j / nv
        row = []
        for i in range(nu + 1):
            u = i / nu
            y = -dw - 0.02 + 0.2 * u
            row.append((rx - 0.008 * math.sin(math.pi * u) + 0.016 * math.sin(2 * math.pi * 6 * u) * (1 + 0.15 * j / nv),
                        y, z))
        rows.append(row)
    m.grid(rows, "Curtain", lambda mid: (-1, 0, 0))
    m.grid([[(p[0] + 0.0015, p[1], p[2]) for p in r] for r in rows], "Curtain", lambda mid: (1, 0, 0))   # its other face
    for i in range(0, nu + 1, 3):                              # the rings on the rod
        p = rows[0][i]
        BS.torus(m, (rx, p[1], rz), (0, 1, 0), 0.012, 0.002, "Stainless", 10, 4)
    # the keel's winch is inside the step (under the bridgedeck): only its crank socket shows, in a boss on the step's
    # forward face; its cable runs straight forward into the trunk's aft end, unseen
    KW = CC.KW
    fx = STP["x"][1]
    BR.rod(m, (fx, KW["socket_y"], KW["socket_z"]), (fx + 0.012, KW["socket_y"], KW["socket_z"]), KW["boss_r"],
           "Aluminium", 20)
    BR.rod(m, (fx + 0.011, KW["socket_y"], KW["socket_z"]), (fx + 0.016, KW["socket_y"], KW["socket_z"]), 0.011,
           "BlackPlastic", 10)
    # a teak cap on the keel trunk's top: a flat-topped box over its smooth moulding
    TC = CC.C["trunk_cap"]
    w = CC.TRUNK_W + 0.004
    xs = [x for x in CC.trunk_stations() if CC.trunk_out_top(x) is not None]
    rows = []
    for x in xs:
        t = CC.trunk_out_top(x)
        lo = max(t - TC["skirt"], CC.SO["z"] + 0.001)
        rows.append([(x, -w, lo), (x, -w, t + TC["thick"]), (x, w, t + TC["thick"]), (x, w, lo)])
    ring = [[r[k] for r in rows] for k in range(4)]
    for k, out in enumerate(((0, -1, 0), (0, 0, 1), (0, 1, 0))):
        m.grid([ring[k], ring[k + 1]], "Teak", lambda mid, out=out: out)
    m.polygon(rows[0], "Teak", (-1, 0, 0))
    m.polygon(rows[-1], "Teak", (1, 0, 0))
    return m.finish(mats)


def build_porta_potti(mats, S):
    m = Mesh("C22_Interior_PortaPotti")
    s = next(p for p in S if p.name == "PortaPotti")
    x0, x1, z0, z1 = s.x0, s.x1, s.z0, s.z1
    w = s.y_out
    box(m, (x0, -w, z0), (x1, w, z1 - 0.06), "WhitePlastic")
    box(m, (x0 + 0.01, -w + 0.01, z1 - 0.058), (x1 - 0.01, w - 0.01, z1 - 0.002), "WhitePlastic")
    box(m, (x0 - 0.008, -0.05, z1 - 0.1), (x0 + 0.001, 0.05, z1 - 0.08), "BlackPlastic")     # the flush valve's handle
    return round_edges(m.finish(mats), 0.012)


def build_cushions(mats, S):
    m = Mesh("C22_Interior_Cushions")
    for s in S:
        if s.kind == "cushion" and s.name != "TableCushion":
            solid(m, s)
    # the settee's back cushion, leaning on the hull: its foot at the seat's back, its top against the hull higher up
    ST = CC.ST
    zt = ST["top"] + ST["cushion"]
    for x0, x1 in ((ST["x"][0] + 0.01, 0.12), (0.14, ST["x"][1] - 0.01)):
        rows = []
        for x in [x0 + (x1 - x0) * i / 8 for i in range(9)]:
            zh = zt + ST["back_height"]
            for _ in range(3):                                   # its top kept clear of the deck's liner
                zh = min(zh, CC.ceiling(x, CC.fit(x, zh) - 0.01) - CC.CLEAR - CUSHION_R)
            y0, y1 = CC.fit(x, zt) - ST["back_thick"], CC.fit(x, zh) - 0.01
            rows.append([(x, y0, zt), (x, y0 + ST["back_thick"], zt), (x, y1, zh), (x, y1 - ST["back_thick"], zh)])
        ring = [[r[k] for r in rows] for k in range(4)]
        ring.append(ring[0])
        for k in range(4):
            m.grid([ring[k], ring[k + 1]], "Cushion", lambda mid, k=k: ((0, 0, -1), (0, 1, 0), (0, 0, 1), (0, -1, 0))[k])
        m.polygon(rows[0], "Cushion", (-1, 0, 0))
        m.polygon(rows[-1], "Cushion", (1, 0, 0))
    # the dinette's aft back cushion, on its panel
    DN = CC.DN
    xa = DN["aft_seat"][0]
    zt = DN["seat_top"] + DN["cushion"]
    from cabin_c22 import Solid
    solid(m, Solid("DinetteBackCushion", "Cushion", (xa + 0.002, xa + 0.07), (zt + 0.01, zt + DN["back_height"] - 0.02),
                   DN["inboard_y"] + 0.02, side=-1))
    return round_edges(m.finish(mats), CUSHION_R)


def build_table(mats, S, name, down=False):
    m = Mesh(name)
    t = next(p for p in S if p.name == "Table")
    solid(m, t)
    lx, ly = 0.5 * (t.x0 + t.x1), -(CC.DN["inboard_y"] + 0.06)
    BR.rod(m, (lx, ly, CC.SO["z"]), (lx, ly, t.z0), 0.022, "Aluminium", 14)
    BR.rod(m, (lx, ly, CC.SO["z"]), (lx, ly, CC.SO["z"] + 0.008), 0.06, "Aluminium", 16)      # its foot on the sole
    ob = m.finish(mats)
    obs = [ob]
    if down:
        c = next(p for p in S if p.name == "TableCushion")
        mc = Mesh(name + "_cushion")
        solid(mc, c)
        cob = round_edges(mc.finish(mats), CUSHION_R)
        obs.append(cob)
        ob = join(obs, name)
    return ob


def build_galley(mats, S, name):
    m = Mesh(name)
    g = next(p for p in S if p.name == "Galley")
    solid(m, g)
    lo, hi = g.across(g.x1, g.z1)
    zt = g.z1
    # the stove at its forward end: a stainless tray, two burners; the sink aft of it
    box(m, (g.x1 - 0.31, lo + 0.04, zt), (g.x1 - 0.03, hi - 0.04, zt + 0.006), "Stainless")
    for k in range(2):
        cx = g.x1 - 0.17
        cy = lo + 0.04 + (hi - lo - 0.08) * (0.27 + 0.46 * k)
        BS.torus(m, (cx, cy, zt + 0.01), (0, 0, 1), 0.045, 0.005, "BlackPlastic", 16, 5)
        BS.torus(m, (cx, cy, zt + 0.012), (0, 0, 1), 0.02, 0.004, "BlackPlastic", 12, 5)
    box(m, (g.x0 + 0.08, lo + 0.08, zt), (g.x0 + 0.34, hi - 0.08, zt + 0.004), "Stainless")
    BR.rod(m, (g.x0 + 0.21, 0.5 * (lo + hi), zt + 0.004), (g.x0 + 0.21, 0.5 * (lo + hi), zt + 0.006), 0.018,
           "BlackPlastic", 12)
    # its handle on the front
    mz = 0.5 * (g.z0 + g.z1)
    for sy in (lo + 0.12, hi - 0.12):
        BR.rod(m, (g.x1, sy, mz), (g.x1 + 0.03, sy, mz), 0.006, "Stainless", 8)
    BR.rod(m, (g.x1 + 0.03, lo + 0.11, mz), (g.x1 + 0.03, hi - 0.11, mz), 0.007, "Stainless", 8)
    return m.finish(mats)


def join(obs, name):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join()
    obs[0].name = name
    obs[0].data.name = name
    return obs[0]


def build_all(mats):
    """Every part; the alternative states hidden. Returns the objects and the report's numbers."""
    S = CC.layout()
    obs = build_liner(mats) + [build_interior(mats, S), build_porta_potti(mats, S), build_cushions(mats, S),
           build_table(mats, S, "C22_Interior_Table"), build_galley(mats, S, "C22_Interior_Galley")]
    Sd = CC.layout(table_down=True)
    down = build_table(mats, Sd, "C22_Interior_TableDown", down=True)
    out = build_galley(mats, CC.layout(galley_out=True), "C22_Interior_GalleyOut")
    for o in (down, out):
        o.hide_render = o.hide_viewport = True
    obs += [down, out]
    tris = {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in obs}
    print("C22 cabin triangles: " + ", ".join(f"{k} {v}" for k, v in tris.items()) + f"; {sum(tris.values())} in all")
    report = {"headroom_popup_closed_m": round(CC.headroom(False), 4),
              "headroom_popup_raised_m": round(CC.headroom(True), 4)}
    return obs, report
