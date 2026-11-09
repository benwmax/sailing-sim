"""Boat fidelity (pc/j22-detail, assembly 3; rebuilt by the part detail loop Nov 8 2026, docs/part-detail-loop/boomgear.md):
the boom's fittings as Bean's photos show them (mast-boom-gooseneck-connector, boom-end, boom-vang-closeup,
outhaul-sheet-cleet). Replaces j22_details' gooseneck and boom_end:

- the gooseneck: a stainless plate curved to the mast's aft face (rounded corners, eight countersunk screws) with two
  tangs welded on and a gusset behind each, a hex bolt down through both (the boom's swing) with its nylock under, a
  black toggle between them (a barrel round the bolt on nylon washers, a short neck aft to an eye across the boat), the
  boom's end casting (grey cast aluminium, a lip proud of the boom, riveted in) tapering forward into a fork whose
  cheeks have bosses round the quick-release pin through the toggle's eye (the boom's lift); ram's horns for the reef
  (port) and cunningham (starboard) on plates riveted to the casting;
- the boom's aft end: a cast cap with a lip, its top swept down aft, the outhaul sheave in a slot cut through the top,
  its axle's heads each side, rivets through the boom, a lug and D-shackle on top for the topping lift;
- the outhaul's clam cleat under the boom: a base curved to the boom, two ridged jaws, a fairlead hoop aft, screws
  down the channel;
- the vang's bail: a stainless strap round the boom's underside on a through-bolt, its loop the top block's shackle
  hangs from (the blocks are the boat kit's Fiddle40 and FiddleCam, placed by build_j22_hero.py).

The parts the bake reads keep their names and centres (Gooseneck_vpin: the boom's pivot; BoomEnd_outhaul: Boom_Clew),
so no socket moves (Boom_Vang is pinned by an anchor where the old bail's centre was). Blender frame, as
build_j22_hero.py: +X forward, +Y port, +Z up."""
import math

import bmesh
from mathutils import Vector

from j22_geom import apply_mods, boolean, box, cyl, mesh_obj, tube
from j22_steering import hex_head, lathe, nylock, plate

MAST_A, MAST_B = 0.049, 0.034       # the mast section's half fore-and-aft and half width (build_j22_hero: spar 98 x 68)
BOOM_RY, BOOM_RZ = 0.0275, 0.0375   # the boom's half width and half height (spar 75 high x 55 wide)


def rounded(x0, x1, z0, z1, r, n=6):
    """A rounded rectangle's outline in (x, z)."""
    pts = []
    for cx, cz, a0 in ((x1 - r, z1 - r, 0), (x0 + r, z1 - r, 90), (x0 + r, z0 + r, 180), (x1 - r, z0 + r, 270)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts


def _bevel(ob, w, segs=2, angle=40):
    m = ob.modifiers.new("bev", "BEVEL")
    m.width, m.segments, m.limit_method, m.angle_limit = w, segs, "ANGLE", math.radians(angle)
    apply_mods(ob)
    return ob


def loft(name, rings, mat, cap0=True, cap1=True, smooth=True):
    """A skin through rings of points (each the same count, in order round)."""
    bm = bmesh.new()
    vs = [[bm.verts.new(tuple(p)) for p in r] for r in rings]
    n = len(rings[0])
    for a, b in zip(vs[:-1], vs[1:]):
        for k in range(n):
            bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    if cap0:
        bm.faces.new(vs[0][::-1])
    if cap1:
        bm.faces.new(vs[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, mat, smooth_shade=smooth)


def ell_ring(x, cz, ry, rz, n=40, p=2.0):
    """A ring round the X axis at x: a superellipse (p 2: an ellipse; higher: squarer) of half sizes ry, rz."""
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n
        c, s = math.cos(a), math.sin(a)
        out.append(Vector((x, ry * math.copysign(abs(c) ** (2 / p), c), cz + rz * math.copysign(abs(s) ** (2 / p), s))))
    return out


def slab(name, us, extent, surf, thick, mat, bev=0.0006):
    """A plate lying on a surface curved in one direction: columns at us, each spanning extent(u) -> (v0, v1);
    surf(u, v) -> (point, outward normal). The plate's back is on the surface, its face thick out along the normal."""
    bm = bmesh.new()
    B0, B1, F0, F1 = [], [], [], []
    for u in us:
        v0, v1 = extent(u)
        for v, Bl, Fl in ((v0, B0, F0), (v1, B1, F1)):
            p, n = surf(u, v)
            Bl.append(bm.verts.new(tuple(p)))
            Fl.append(bm.verts.new(tuple(p + n * thick)))
    for i in range(len(us) - 1):
        j = i + 1
        bm.faces.new((B0[i], B0[j], B1[j], B1[i]))
        bm.faces.new((F0[i], F1[i], F1[j], F0[j]))
        bm.faces.new((B0[i], F0[i], F0[j], B0[j]))
        bm.faces.new((B1[i], B1[j], F1[j], F1[i]))
    bm.faces.new((B0[0], B1[0], F1[0], F0[0]))
    k = len(us) - 1
    bm.faces.new((B0[k], F0[k], F1[k], B1[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_obj(name, bm, mat, smooth_shade=False)
    return _bevel(ob, bev) if bev else ob


def round_extent(half_u, v0, v1, r):
    """A rounded rectangle as columns: (v0, v1) at u, its corners of radius r."""
    def f(u):
        d = max(0.0, abs(u) - (half_u - r))
        e = r - math.sqrt(max(0.0, r * r - d * d))
        return v0 + e, v1 - e
    return f


def columns(half_u, r, n_mid=6, n_corner=6):
    """Column positions for round_extent: dense in the corners."""
    us = []
    for k in range(n_corner):
        us.append(-half_u + r * (1 - math.cos(math.pi / 2 * k / n_corner)))
    for k in range(n_mid + 1):
        us.append(-(half_u - r) + 2 * (half_u - r) * k / n_mid)
    for k in range(n_corner - 1, -1, -1):
        us.append(half_u - r * (1 - math.cos(math.pi / 2 * k / n_corner)))
    return us


def sweep_strap(name, pts, across, width, thick, mat):
    """A flat strap (width along `across`, thick in the path's plane) along a path of points."""
    X = Vector(across).normalized()
    pts = [Vector(p) for p in pts]
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        n = t.cross(X).normalized()
        rings.append([p + X * width / 2 + n * thick / 2, p - X * width / 2 + n * thick / 2,
                      p - X * width / 2 - n * thick / 2, p + X * width / 2 - n * thick / 2])
    return _bevel(loft(name, rings, mat, smooth=False), min(width, thick) * 0.25, 2, 30)


def countersunk_dimpled(name, p, normal, d, mat):
    """A countersunk machine screw's head, flush, a dimple in the middle for the driver."""
    n = Vector(normal).normalized()
    return [lathe(name, [(0.0, -0.0002), (d * 0.12, -0.0002), (d * 0.17, 0.0005), (d / 2, 0.0003), (d / 2, -0.0003)],
                  Vector(p), n, mat, 16)]


def plate_yz(name, outline_yz, x0, x1, mat, bev=0.001):
    """A plate lying in a y-z plane (on the mast's aft face): outline (y, z) extruded x0..x1."""
    bm = bmesh.new()
    a = [bm.verts.new((x0, y, z)) for y, z in outline_yz]
    b = [bm.verts.new((x1, y, z)) for y, z in outline_yz]
    k = len(outline_yz)
    for i in range(k):
        bm.faces.new((a[i], a[(i + 1) % k], b[(i + 1) % k], b[i]))
    bm.faces.new(a[::-1])
    bm.faces.new(b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_obj(name, bm, mat, smooth_shade=False)
    if bev:
        from j22_geom import apply_mods
        m = ob.modifiers.new("bev", "BEVEL")
        m.width, m.segments, m.limit_method, m.angle_limit = bev, 2, "ANGLE", math.radians(40)
        apply_mods(ob)
    return ob


def plate_xy(name, outline_xy, z0, z1, mat, bev=0.001):
    """A flat plate in plan: outline (x, y) extruded z0..z1."""
    bm = bmesh.new()
    a = [bm.verts.new((x, y, z0)) for x, y in outline_xy]
    b = [bm.verts.new((x, y, z1)) for x, y in outline_xy]
    k = len(outline_xy)
    for i in range(k):
        bm.faces.new((a[i], a[(i + 1) % k], b[(i + 1) % k], b[i]))
    bm.faces.new(a[::-1])
    bm.faces.new(b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_obj(name, bm, mat, smooth_shade=False)
    if bev:
        from j22_geom import apply_mods
        m = ob.modifiers.new("bev", "BEVEL")
        m.width, m.segments, m.limit_method, m.angle_limit = bev, 2, "ANGLE", math.radians(40)
        apply_mods(ob)
    return ob


def countersunk(name, p, axis, d, mat):
    """(Shared with j22_mastgear and j22_mainsheet.) A countersunk machine screw's head, flush with a dimple and a cross slot."""
    axis = Vector(axis).normalized()
    out = [lathe(name, [(0.0, 0.0), (d / 2, 0.0), (d * 0.44, 0.0008), (0.0, 0.0008)], p, axis, mat, 16)]
    return out


def rivet(name, p, normal, d, mat):
    """A pop rivet's domed head with its hollow mandrel."""
    n = Vector(normal).normalized()
    return [lathe(name, [(d * 0.14, 0.0006), (d * 0.18, 0.0011), (d * 0.36, 0.0010), (d * 0.5, 0.0003), (d * 0.5, -0.0003),
                         (d * 0.14, -0.0003)], Vector(p), n, mat, 14)]


def boom_wall(zc, dz, side):
    """The point on the boom's side wall dz above its centre line (side +1 port), and the wall's normal there."""
    y = side * BOOM_RY * math.sqrt(max(0.0, 1 - (dz / BOOM_RZ) ** 2))
    n = Vector((0, y / BOOM_RY ** 2, dz / BOOM_RZ ** 2)).normalized()
    return Vector((0, y, zc + dz)), n


def gooseneck(name, mast_aft, boom_z, M):
    p = Vector(mast_aft)
    cx = p.x + MAST_A                     # the mast's centre line
    out = []

    # the mast plate: stainless, rounded corners, its back on the mast's curved aft face
    def mast_surf(y, z):
        x = cx - MAST_A * math.sqrt(max(0.0, 1 - (y / MAST_B) ** 2))
        n = Vector(((x - cx) / MAST_A ** 2, y / MAST_B ** 2, 0)).normalized()
        return Vector((x, y, z)) + n * 0.0002, n
    hw, r = 0.024, 0.009
    out.append(slab(f"{name}_plate", columns(hw, r), round_extent(hw, boom_z - 0.082, boom_z + 0.082, r), mast_surf, 0.0035,
                    M["Stainless"], bev=0.0008))
    for zz in (-0.068, -0.050, 0.050, 0.068):
        for sgn in (1, -1):
            q, n = mast_surf(sgn * 0.0155, boom_z + zz)
            out += countersunk_dimpled(f"{name}_scr{zz:+.3f}{sgn}", q + n * 0.0035, n, 0.0075, M["Stainless"])
    # two tangs welded on, top and bottom, round-ended aft, a weld bead and a gusset where they meet the plate
    px = p.x - 0.034
    for dz in (0.0275, -0.0275):
        up = 1 if dz > 0 else -1
        outline = [(p.x - 0.002, -0.0135), (px, -0.0135)] + \
                  [(px - 0.0135 * math.sin(math.pi * k / 12), -0.0135 * math.cos(math.pi * k / 12)) for k in range(1, 12)] + \
                  [(px, 0.0135), (p.x - 0.002, 0.0135)]
        out.append(_tang_xy(f"{name}_tang{dz:+.3f}", outline, boom_z + dz - 0.0025, boom_z + dz + 0.0025, M["Stainless"]))
        zf = boom_z + dz + 0.0025 * up
        out.append(tube(f"{name}_weld{dz:+.3f}", [(p.x - 0.0032, -0.0135, zf), (p.x - 0.0032, 0.0135, zf)], 0.0016, M["Stainless"]))
        g = [(p.x - 0.0032, zf), (p.x - 0.0032, zf + up * 0.020), (p.x - 0.0075, zf + up * 0.020), (p.x - 0.020, zf + up * 0.002),
             (p.x - 0.020, zf)]
        out.append(plate(f"{name}_gusset{dz:+.3f}", g, -0.002, 0.002, M["Stainless"], bev=0.0006))
    # the bolt through both tangs (the boom's swing): the game reads Gooseneck_vpin's centre as the boom's pivot
    out.append(cyl(f"{name}_vpin", (px, 0, boom_z - 0.045), (px, 0, boom_z + 0.045), 0.004, M["Stainless"], 12))
    out += hex_head(f"{name}_vpinhead", Vector((px, 0, boom_z + 0.030)), (0, 0, 1), 0.013, 0.0065, M["Stainless"])
    out += nylock(f"{name}_vpinnut", Vector((px, 0, boom_z - 0.030)), (0, 0, -1), 0.013, M["Stainless"])
    # the toggle (it swings with the boom: bake BOOM_PARTS): a barrel round the bolt on nylon washers, a neck aft, an
    # eye across the boat for the lift pin
    out.append(lathe(f"{name}_knuckle", [(0.0042, -0.0236), (0.0115, -0.0236), (0.0128, -0.0222), (0.0128, 0.0222), (0.0115, 0.0236),
                                         (0.0042, 0.0236)], Vector((px, 0, boom_z)), (0, 0, 1), M["BlackPlastic"], 32))
    for up in (1, -1):
        out.append(lathe(f"{name}_knucklewsh{up}", [(0.0042, 0.0), (0.0125, 0.0), (0.0125, 0.0013), (0.0042, 0.0013)],
                         Vector((px, 0, boom_z + up * 0.0237)), (0, 0, up), M["WhitePlastic"], 24))
    hx = p.x - 0.068                       # the lift pin
    rings = [ell_ring(x, boom_z, hwd, hh, 24, 3.2) for x, hwd, hh in ((px - 0.006, 0.0082, 0.0150), (px - 0.0135, 0.0082, 0.0118),
                                                                       (hx + 0.006, 0.0082, 0.0098))]
    out.append(_bevel(loft(f"{name}_knuckleneck", rings, M["BlackPlastic"]), 0.0008))
    out.append(lathe(f"{name}_knuckleeye", [(0.0042, -0.0086), (0.0098, -0.0086), (0.0108, -0.0078), (0.0108, 0.0078), (0.0098, 0.0086),
                                            (0.0042, 0.0086)], Vector((hx, 0, boom_z)), (0, 1, 0), M["BlackPlastic"], 28))
    # the boom's end casting: a plug in the boom, a lip proud of it, a nose tapering forward to the fork
    b0 = p.x - 0.12                        # where the boom's tube starts (build_j22_hero: aft_face - 0.12)
    prof = ((b0 - 0.045, 0.0, 0.97, 0.97), (b0 - 0.001, 0.0, 0.97, 0.97), (b0 - 0.0005, 0.0, 1.055, 1.045), (b0 + 0.0045, 0.0, 1.055, 1.045),
            (b0 + 0.0065, 0.0, 1.0, 1.0), (b0 + 0.0125, 0.0, 0.93, 0.91), (b0 + 0.0195, 0.0, 0.81, 0.77),
            (b0 + 0.0265, 0.0, 0.68, 0.62), (b0 + 0.0295, 0.0, 0.60, 0.55), (b0 + 0.0310, 0.0, 0.50, 0.46))
    rings = [ell_ring(x, boom_z + dzc, BOOM_RY * sy, BOOM_RZ * sz, 40, 2.4) for x, dzc, sy, sz in prof]
    out.append(loft(f"{name}_boomcap", rings, M["CastAlu"]))
    # a dark slot along the top: the boom's bolt-rope groove running out through the casting
    out.append(box(f"{name}_boomcapslot", b0 - 0.002, b0 + 0.0062, -0.0022, 0.0022, boom_z + BOOM_RZ * 0.95, boom_z + BOOM_RZ * 1.045 + 0.0003,
                   M["BlackPlastic"]))
    # the fork: two cheeks from the nose forward round the toggle's eye, a boss round the pin each side
    nose = b0 + 0.026
    for sgn in (1, -1):
        top = [(nose - 0.002 + (hx - 0.002 - nose) * t, boom_z + 0.019 - 0.0085 * (3 * t * t - 2 * t ** 3)) for t in (i / 6 for i in range(7))]
        arc = [(hx + 0.0105 * math.cos(math.pi / 2 - math.pi * k / 10), boom_z + 0.0105 * math.sin(math.pi / 2 - math.pi * k / 10))
               for k in range(1, 10)]
        bot = [(x, 2 * boom_z - z) for x, z in top[::-1]]
        out.append(plate(f"{name}_fork{sgn}", [(nose - 0.004, boom_z + 0.019)] + top + arc + bot + [(nose - 0.004, boom_z - 0.019)],
                         min(sgn * 0.0090, sgn * 0.0128), max(sgn * 0.0090, sgn * 0.0128), M["CastAlu"], bev=0.0012))
        out.append(lathe(f"{name}_forkboss{sgn}", [(0.0042, 0.0), (0.0085, 0.0), (0.0085, 0.0012), (0.0072, 0.0020), (0.0042, 0.0020)],
                         Vector((hx, sgn * 0.0127, boom_z)), (0, sgn, 0), M["CastAlu"], 20))
    # the quick-release pin across the fork (the boom's lift), its ring hanging to port
    out.append(cyl(f"{name}_hpin", (hx, -0.0185, boom_z), (hx, 0.0165, boom_z), 0.0039, M["Stainless"], 14))
    out.append(lathe(f"{name}_hpinhead", [(0.0, 0.0), (0.0068, 0.0), (0.0068, 0.0025), (0.0055, 0.0045), (0.0030, 0.0055), (0.0, 0.0057)],
                     Vector((hx, 0.0147, boom_z)), (0, 1, 0), M["Stainless"], 18))
    out.append(lathe(f"{name}_hpinball", [(0.0, -0.0008), (0.0012, -0.0008), (0.0012, 0.0008), (0.0, 0.0008)],
                     Vector((hx + 0.0026, -0.0170, boom_z)), (0, 1, 0), M["Stainless"], 8))
    ring = [Vector((hx, -0.0195, boom_z)) + Vector((0.0075 * math.sin(a), -0.0025 * math.sin(a), -0.0075 * (1 - math.cos(a))))
            for a in (2 * math.pi * k / 20 for k in range(21))]
    out.append(tube(f"{name}_hpinring", [tuple(q) for q in ring], 0.0010, M["Stainless"], smooth_path=True))
    # pop rivets through the boom into the casting's plug, three a side
    for sgn in (1, -1):
        for dx, dz in ((-0.010, 0.016), (-0.010, -0.016), (-0.026, 0.0)):
            q, n = boom_wall(boom_z, dz, sgn)
            out += rivet(f"{name}_boomcaprivet{sgn}{dx}{dz}", Vector((b0 + dx, q.y, q.z)) + n * 0.0001, n, 0.0095, M["Stainless"])
    # the ram's horns: reef (port) and cunningham (starboard), cast stainless on a plate riveted to the casting's side
    for sgn, nm in ((1, "reef"), (-1, "cunn")):
        x0 = b0 - 0.012
        q, n = boom_wall(boom_z, 0.006, sgn)
        y0, y1 = sorted((q.y - sgn * 0.0005, q.y + sgn * 0.003))
        out.append(plate(f"{name}_{nm}hookbase", rounded(x0 - 0.011, x0 + 0.011, boom_z - 0.004, boom_z + 0.016, 0.004), y0, y1,
                         M["Stainless"], bev=0.0008))
        yb = q.y + sgn * 0.003
        # a stubby cast horn: a tapering stem up out of the plate, curling forward to a rounded tip
        path = [Vector((x0 - 0.002, yb - sgn * 0.0015, boom_z + 0.004)), Vector((x0 - 0.002, yb + sgn * 0.0025, boom_z + 0.018)),
                Vector((x0 + 0.002, yb + sgn * 0.0035, boom_z + 0.031)), Vector((x0 + 0.010, yb + sgn * 0.003, boom_z + 0.038)),
                Vector((x0 + 0.018, yb + sgn * 0.002, boom_z + 0.037))]
        fine = []
        for i in range(len(path) - 1):
            for k in range(4):
                t = k / 4
                p0, p1 = path[max(i - 1, 0)], path[i]
                p2, p3 = path[i + 1], path[min(i + 2, len(path) - 1)]
                fine.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
        fine.append(path[-1])
        hrings = []
        for i, c in enumerate(fine):
            tg = (fine[min(i + 1, len(fine) - 1)] - fine[max(i - 1, 0)]).normalized()
            u = tg.cross(Vector((0, 1, 0))).normalized()
            w = tg.cross(u)
            r = 0.0062 - 0.0030 * i / (len(fine) - 1)
            hrings.append([c + (u * math.cos(2 * math.pi * k / 14) * 1.15 + w * math.sin(2 * math.pi * k / 14)) * r for k in range(14)])
        out.append(loft(f"{name}_{nm}hook", hrings, M["Stainless"]))
        out.append(lathe(f"{name}_{nm}hooktip", [(0.0, -0.0032), (0.0024, -0.0026), (0.0033, 0.0), (0.0024, 0.0026), (0.0, 0.0032)],
                         path[-1], (1, 0, 0), M["Stainless"], 14))
        for dx in (-0.006, 0.006):
            out += rivet(f"{name}_{nm}hookrivet{dx}", Vector((x0 + dx, yb, boom_z + 0.000)), (0, sgn, 0), 0.006, M["Stainless"])
    return out


def _tang_xy(name, outline_xy, z0, z1, mat):
    bm = bmesh.new()
    a = [bm.verts.new((x, y, z0)) for x, y in outline_xy]
    b = [bm.verts.new((x, y, z1)) for x, y in outline_xy]
    k = len(outline_xy)
    for i in range(k):
        bm.faces.new((a[i], a[(i + 1) % k], b[(i + 1) % k], b[i]))
    bm.faces.new(a[::-1])
    bm.faces.new(b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _bevel(mesh_obj(name, bm, mat, smooth_shade=False), 0.0009)


def boom_end(name, end, M):
    """The boom's aft cap: a casting plugged into the boom, a lip, its top swept down aft; the outhaul sheave in a slot
    through the top (Boom_Clew reads the sheave's centre), a lug and shackle on top for the topping lift."""
    e = Vector(end)
    out = []
    prof = ((0.040, 0.0, 0.97, 0.97), (0.0015, 0.0, 0.97, 0.97), (0.001, 0.0, 1.05, 1.04), (-0.004, 0.0, 1.05, 1.04),
            (-0.006, 0.0, 1.0, 0.99), (-0.020, 0.0010, 0.97, 0.94), (-0.032, 0.0035, 0.90, 0.80), (-0.041, 0.0065, 0.76, 0.60),
            (-0.0465, 0.0085, 0.66, 0.46), (-0.0490, 0.0090, 0.52, 0.34), (-0.0500, 0.0090, 0.30, 0.18))
    rings = [ell_ring(e.x + dx, e.z + dzc, BOOM_RY * sy, BOOM_RZ * sz, 40, 3.0) for dx, dzc, sy, sz in prof]
    cap = loft(f"{name}_cap", rings, M["CastAlu"])
    sx = e.x - 0.010                     # the outhaul sheave: its centre is Boom_Clew
    cutter = box(f"{name}_slotcut", sx - 0.020, sx + 0.017, -0.0072, 0.0072, e.z + 0.004, e.z + 0.06)
    boolean(cap, cutter)
    out.append(cap)
    out.append(lathe(f"{name}_outhaul", [(0.0, -0.0062), (0.0118, -0.0062), (0.012, -0.0048), (0.0098, -0.0018), (0.0094, 0.0),
                                         (0.0098, 0.0018), (0.012, 0.0048), (0.0118, 0.0062), (0.0, 0.0062)],
                     Vector((sx, 0, e.z + 0.012)), (0, 1, 0), M["SheaveGrey"], 28))
    out.append(cyl(f"{name}_axle", (sx, -0.029, e.z + 0.012), (sx, 0.029, e.z + 0.012), 0.0028, M["Stainless"], 10))
    for sgn in (1, -1):
        q, n = boom_wall(e.z, 0.012, sgn)
        out.append(lathe(f"{name}_axlehead{sgn}", [(0.0, 0.0), (0.0055, 0.0), (0.0052, 0.0016), (0.0035, 0.0024), (0.0, 0.0026)],
                         Vector((sx, q.y * 0.99, q.z)), n, M["Stainless"], 16))
        for dx, dz in ((0.012, 0.016), (0.012, -0.016), (0.026, 0.0)):
            q, n = boom_wall(e.z, dz, sgn)
            out += rivet(f"{name}_rivet{sgn}{dx}{dz}", Vector((e.x + dx, q.y, q.z)) + n * 0.0001, n, 0.0095, M["Stainless"])
    # the lug on top, aft of the slot, and a D-shackle for the topping lift
    lx, lz = e.x - 0.036, e.z + 0.0035 + BOOM_RZ * 0.80
    out.append(plate(f"{name}_lug", [(lx - 0.011, lz - 0.006), (lx + 0.008, lz - 0.006), (lx + 0.006, lz + 0.004)] +
                     [(lx + 0.0055 * math.cos(math.pi * k / 8), lz + 0.006 + 0.0055 * math.sin(math.pi * k / 8)) for k in range(9)] +
                     [(lx - 0.008, lz + 0.002)], -0.0025, 0.0025, M["CastAlu"], bev=0.0008))
    ring = [(lx + 0.0085 * math.cos(a), 0.0, lz + 0.006 + 0.012 * math.sin(a)) for a in (math.pi * k / 12 for k in range(13))]
    out.append(tube(f"{name}_shackle", [(lx + 0.0085, 0.0, lz + 0.006)] + ring[1:], 0.0021, M["Stainless"], smooth_path=True))
    out.append(cyl(f"{name}_shacklepin", (lx, -0.0065, lz + 0.006), (lx, 0.0075, lz + 0.006), 0.0022, M["Stainless"], 10))
    out.append(lathe(f"{name}_shacklepinhead", [(0.0, 0.0), (0.0042, 0.0), (0.0042, 0.0022), (0.0, 0.0026)], Vector((lx, 0.0055, lz + 0.006)),
                     (0, 1, 0), M["Stainless"], 12))
    return out


def outhaul_cleat(name, at, M):
    """The outhaul's clam cleat under the boom (photo outhaul-sheet-cleet): a base curved to the boom, two jaws with
    angled ridges inside (the line pulls forward into them), a fairlead hoop at the aft end, screws down the channel."""
    a = Vector(at)
    zc = a.z + BOOM_RZ
    out = []

    def under(y, x):
        z = zc - BOOM_RZ * math.sqrt(max(0.0, 1 - (y / BOOM_RY) ** 2))
        n = Vector((0, y / BOOM_RY ** 2, (z - zc) / BOOM_RZ ** 2)).normalized()
        return Vector((x, y, z)) + n * 0.0002, n
    out.append(slab(f"{name}_base", columns(0.0125, 0.006, 4, 5), round_extent(0.0125, a.x - 0.044, a.x + 0.044, 0.006), under, 0.0035,
                    M["SheaveGrey"], bev=0.0008))
    z0 = a.z - 0.0030
    prof = [(a.x + 0.040, z0), (a.x - 0.034, z0), (a.x - 0.041, z0 - 0.009), (a.x - 0.035, z0 - 0.021), (a.x - 0.005, z0 - 0.0235),
            (a.x + 0.028, z0 - 0.0185), (a.x + 0.040, z0 - 0.0085)]
    for sgn in (1, -1):
        out.append(plate(f"{name}_jaw{sgn}", prof, min(sgn * 0.0036, sgn * 0.0120), max(sgn * 0.0036, sgn * 0.0120), M["SheaveGrey"], bev=0.0018))
        for k in range(7):
            x = a.x - 0.024 + 0.008 * k
            rid = [(x, z0 - 0.0005), (x + 0.0022, z0 - 0.0005), (x + 0.0022 + 0.010, z0 - 0.0185), (x + 0.010, z0 - 0.0185)]
            out.append(plate(f"{name}_ridge{sgn}{k}", rid, min(sgn * 0.0036, sgn * 0.0022), max(sgn * 0.0036, sgn * 0.0022), M["SheaveGrey"], bev=0.0004))
    # the fairlead hoop aft, across the channel's mouth
    out.append(lathe(f"{name}_throat", [(0.0042, -0.002), (0.0072, -0.002), (0.0072, 0.002), (0.0042, 0.002), (0.0042, -0.002)],
                     Vector((a.x - 0.041, 0, z0 - 0.0110)), (1, 0, 0), M["SheaveGrey"], 20))
    for dx in (0.022, -0.016):
        out.append(lathe(f"{name}_scr{dx}", [(0.0, 0.0), (0.0034, 0.0), (0.0030, 0.0011), (0.0012, 0.0016), (0.0, 0.0016)],
                         Vector((a.x + dx, 0.0, z0)), (0, 0, -1), M["Stainless"], 14))
    return out


def boom_bail(name, x, zc, M):
    """The vang's bail (Kenyon K-10456 kind): a 16 x 3 mm stainless strap from a through-bolt each side of the boom down
    round its underside to a loop, where the top block's shackle hangs. Returns (objects, the loop's pin point)."""
    out = []
    zb = zc + 0.004                        # the bolt, a little above the boom's centre line
    ys = BOOM_RY + 0.0017
    loop_c, loop_r = zc - 0.0565, 0.0055
    right = [(ys, zb), (ys + 0.0002, zc - 0.010), (BOOM_RY * 0.86 + 0.002, zc - 0.024), (0.0165, zc - 0.036), (0.0085, zc - 0.047),
             (loop_r + 0.0004, loop_c - 0.0005)]
    arc = [(loop_r * math.cos(t), loop_c - loop_r * math.sin(t)) for t in (math.pi * k / 10 for k in range(1, 10))]
    path = right + arc + [(-y, z) for y, z in right[::-1]]
    out.append(sweep_strap(f"{name}", [(x, y, z) for y, z in path], (1, 0, 0), 0.016, 0.003, M["Stainless"]))
    out.append(cyl(f"{name}_bolt", (x, -ys - 0.010, zb), (x, ys + 0.012, zb), 0.0032, M["Stainless"], 12))
    out += hex_head(f"{name}_bolthead", Vector((x, ys + 0.0015, zb)), (0, 1, 0), 0.011, 0.0045, M["Stainless"])
    out += nylock(f"{name}_boltnut", Vector((x, -ys - 0.0015, zb)), (0, -1, 0), 0.011, M["Stainless"])
    return out, Vector((x, 0, loop_c))


def vang_line(name, mt, mb, t, s, rope_mat, deck_z, r=0.003):
    """The vang's 4:1 line reeved through the kit's fiddles (the same reeving as partloop/render_assembly.py): the
    becket to the top's small sheave, round the bottom's small sheave, round the top's big sheave, round the bottom's big
    sheave and out through the cam, its tail falling to the cabin top. mt, mb: the blocks' world matrices; t, s: their
    sockets in local metres. Stills only: the game draws the vang as live rope."""
    def T(x, z):
        return mt @ Vector((x, 0, z))

    def B(x, z):
        return mb @ Vector((x, 0, z))
    rb, rs = 0.0201, 0.0131
    cz, cz2 = t["Axle"].z, t["Axle2"].z

    def wrap(F, rho, z, n=14, a_end=0.0):
        return [F(rho * math.cos(a), z + rho * math.sin(a)) for a in (math.pi - (math.pi - a_end) * i / n for i in range(n + 1))]
    pts = [B(0, s["Becket"].z - 0.001)]
    pts += wrap(T, rs, cz2)[::-1]
    pts += wrap(B, rs, cz2)
    pts += wrap(T, rb, cz)[::-1]
    cam = s["Cam"]
    lead = (s.get("CamLead", cam - Vector((0, 0, 0.01))) - cam).normalized()
    ex, ez = cam.x - lead.x * 0.012, cam.z - lead.z * 0.012
    a_end = math.atan2(ez - cz, ex) + math.acos(min(1.0, rb / math.hypot(ex, ez - cz)))
    pts += wrap(B, rb, cz, a_end=a_end)
    pts += [B(ex, ez), B(cam.x + lead.x * 0.010, cam.z + lead.z * 0.010), B(cam.x + lead.x * 0.030, cam.z + lead.z * 0.030)]
    p, q = pts[-1], pts[-1] - pts[-2]
    q.normalize()
    a = p + q * 0.06
    b = Vector((p.x - 0.16, 0.035, deck_z(p.x - 0.16, 0.035) + 0.004))
    c = Vector((p.x - 0.40, 0.06, deck_z(p.x - 0.40, 0.06) + 0.004))
    pts += [p * (1 - k) ** 2 + a * 2 * k * (1 - k) + b * k * k for k in (i / 12 for i in range(1, 13))]
    pts += [b.lerp(c, k) + Vector((0, 0.012 * math.sin(math.pi * k), 0)) for k in (0.25, 0.5, 0.75, 1.0)]
    return tube(name, [tuple(v) for v in pts], r, rope_mat, 12)


def big_block(name, p, along, M, sheave_r=0.040):
    """The October vang's upper block, kept for partloop/render_assembly.py's "before" (the hero now hangs the kit's
    Fiddle40 from boom_bail). Was: the vang's upper block (photo boom-vang-closeup): long cheeks with lightening holes (dark rings set in), several
    sheaves inside, a swivel and a stainless strap up to the boom's bail."""
    p = Vector(p)
    d = Vector(along).normalized()
    side = Vector((0, 1, 0))
    u = d.cross(side).normalized()
    out = []
    L, H = 0.12, 0.044
    outline = []
    for k in range(13):
        a = math.pi / 2 + math.pi * k / 12
        outline.append(p + d * (L / 2 - H / 2) + (d * math.cos(a) * -1 + u * math.sin(a)) * H / 2 * 1.0)
    for k in range(13):
        a = -math.pi / 2 + math.pi * k / 12
        outline.append(p - d * (L / 2 - H / 2) + (d * math.cos(a) * -1 + u * math.sin(a)) * H / 2)
    for sgn in (1, -1):
        bm = bmesh.new()
        a = [bm.verts.new(q + side * sgn * 0.010) for q in outline]
        b = [bm.verts.new(q + side * sgn * 0.0135) for q in outline]
        n = len(outline)
        for i in range(n):
            bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
        bm.faces.new(a[::-1])
        bm.faces.new(b)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        out.append(mesh_obj(f"{name}_cheek{sgn}", bm, M["BlackPlastic"], smooth_shade=False))
        for i in range(6):
            for j in (-1, 1):
                c = p + d * (-0.045 + 0.018 * i) + u * (j * 0.0105) + side * sgn * 0.0137
                out.append(lathe(f"{name}_hole{sgn}{i}{j}", [(0.0035, 0.0), (0.0052, 0.0), (0.0052, 0.0006), (0.0035, 0.0006)], c, side * sgn, M["Stainless"], 14))
    for i in range(3):
        c = p + d * (-0.035 + 0.035 * i)
        out.append(cyl(f"{name}_sheave{i}", c - side * 0.008, c + side * 0.008, 0.017, M["SheaveGrey"], 20))
    # the swivel and the strap up to the bail
    top = p + d * (L / 2 + 0.008)
    out.append(lathe(f"{name}_swivel", [(0.0, 0.0), (0.008, 0.0), (0.0075, 0.016), (0.0, 0.018)], top, d, M["Stainless"], 16))
    return out
