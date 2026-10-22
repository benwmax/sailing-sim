"""J/22 hero model, proof of concept: hull, deck mould, hardware, rig and sails, built from code in Blender.

    blender -b --factory-startup -P Tools/blender/build_j22_hero.py -- <out dir> [--sails] [--heel DEG]

Frame: Blender's, X forward, Y to port, Z up, metres, origin on the design waterline amidships (the game's body frame
with Y flipped, as in build_j22.py). Principal dimensions follow the class and the game's physics export: LOA 6.86 m,
beam 2.44 m, draft 1.16 m, I = 7.56 m, mast at x = 0.65 (the class's J of 8.8 ft back from the forestay tack;
the dock photo match pointed the same way, docs/boatkit-2). Deck layout and hardware follow Bean's lesson photos of
TX 7295 EC (Rush Creek, Oct 2026): open bow with no pulpits or lifelines, teak toe rails and coaming caps, cam
cleats with fairleads on the coaming faces, jib tracks and winches on the cabin top (inboard leads; the boat kit's
JibTrack and Winch16, Tools/boatkit), one chainplate a side carrying both shrouds, traveler on the cockpit
floor, transom-hung rudder, varnished tiller with extension, outboard bracket on the port quarter, split backstay.
Dimensions that the photos and published numbers do not fix are marked GUESS and are what the club measurements
will replace.

Writes <out>/j22_hero.blend, <out>/fbx/SM_J22H_<Part>.fbx and <out>/j22_hero_report.json (volumes, counts).
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else "/tmp/j22/hero/out"
SAILS = "--sails" in ARGS
os.makedirs(OUT, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import j22_materials as M  # noqa: E402
import j22_details as D
from j22_fabric import Drape, Wrinkles  # noqa: E402
from j22_style import TX7295, make_style  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "..", "Tools", "boatkit"))
import bk_parts as KIT  # noqa: E402

# style: --style file.json, or --seed N --preset club|race|new|neglected [--tx7295]
if "--style" in ARGS:
    STYLE = json.load(open(ARGS[ARGS.index("--style") + 1]))
else:
    STYLE = make_style(int(ARGS[ARGS.index("--seed") + 1]) if "--seed" in ARGS else 7295,
                       ARGS[ARGS.index("--preset") + 1] if "--preset" in ARGS else "club",
                       overrides=TX7295 if ("--tx7295" in ARGS or "--seed" not in ARGS) else None)
json.dump(STYLE, open(os.path.join(OUT, "style.json"), "w"), indent=1)

bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
SC.unit_settings.system = "METRIC"

# ------------------------------------------------------------------ principal numbers

BOW, STERN = 3.45, -3.41
MAX_HB, MAX_HB_X = 1.22, -0.40
TRANSOM_LOSS = 0.27
WL_MID, WL_HALF, CANOE_D = -0.06, 2.90, 0.20
MAST_X = 0.65                               # J 8.8 ft (2.68 m) aft of the forestay tack to the mast's front face (class)
CHAINPLATE_X = MAST_X - 0.15                # one plate a side carries both shrouds; GUESS: a little aft of the mast (photos)
CABIN_AFT, CABIN_FWD = -0.55, 1.65          # trunk ends: aft GUESS from the bow photo; the raked face's foot from the
                                            # broadside photo (1.51-1.63 m, docs/boatkit-3)
CABIN_H0 = 0.30                             # GUESS: trunk height over the deck at its aft end, on the centreline
COCKPIT_AFT = -2.92                         # GUESS: aft deck starts here
FWD_HATCH = (0.80, 1.12)                    # fore hatch fore and aft edges
SIDE_DECK = 0.25                            # side deck width inboard of the sheer (photo IMG_9272)
SEAT_Z, FLOOR_Z = 0.40, 0.13                # GUESS: seat and self-bailing floor heights above the waterline
SEAT_IN = 0.40                              # seat inboard edge, half-width


def smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def keel_z(x):
    """Centreline of the canoe body: the rocker below the water, the raked stem and stern overhangs above it."""
    u = (x - WL_MID) / WL_HALF
    if abs(u) <= 1.0:
        return -CANOE_D * (1 - u * u) ** 0.62
    over = (abs(u) - 1) * WL_HALF
    return over * (1.12 if u > 0 else 0.50)


def sheer_z(x):
    """Freeboard 0.79 m at the stem, 0.568 m at the transom (ORC certificate: FF 774, FA 568 mm). Aft of the cabin the
    sheer runs down nearly straight to the transom, as the broadside photo shows (docs/boatkit-3)."""
    fwd = smooth((x - 0.3) / (BOW - 0.3)) ** 1.3 * 0.17
    aft = (max(0.0, -0.3 - x) / (-0.3 - STERN)) ** 1.2 * 0.052
    return 0.62 + fwd - aft


def half_beam(x):
    if x > MAX_HB_X:
        u = (x - MAX_HB_X) / (BOW - MAX_HB_X)
        return MAX_HB * max(0.0, 1 - u ** 2.15) ** 0.90 + 0.004
    u = (MAX_HB_X - x) / (MAX_HB_X - STERN)
    return MAX_HB - TRANSOM_LOSS * u * u


def section(x, f):
    """Half-breadth and height of the hull at station x, girth fraction f (0 keel, 1 sheer)."""
    zk, zs = keel_z(x), sheer_z(x)
    z = zk + (zs - zk) * f
    # rounded bilge, flat-ish run aft, straight flared topsides: a superellipse in height fraction
    q = 2.6 if x < 0.5 else 2.6 - 0.7 * smooth((x - 0.5) / 2.5)
    y = half_beam(x) * (1 - (1 - f) ** 3.0) ** (1 / q)
    return y, z


def stations(n):
    """Stations from the transom to the stem, closer together at both ends."""
    out = []
    for i in range(n):
        t = i / (n - 1)
        t = 0.5 - 0.5 * math.cos(math.pi * t)
        t = 0.5 * t + 0.5 * (i / (n - 1))
        out.append(STERN + (BOW - STERN) * t)
    return out


# ------------------------------------------------------------------ helpers

from j22_geom import (apply_mods, bevel, boolean, box, cyl, join, link, mesh_obj, to_mesh, tube)  # noqa: E402

# ------------------------------------------------------------------ materials

MAT = M.build_all(STYLE)

# ------------------------------------------------------------------ hull shell

def build_hull():
    xs = stations(150)
    ng = 44
    bm = bmesh.new()
    rows = []
    for x in xs:
        row = []
        for j in range(-ng, ng + 1):
            f = abs(j) / ng
            y, z = section(x, f)
            row.append(bm.verts.new((x, math.copysign(y, j) if j else 0.0, z)))
        rows.append(row)
    uv_rows = rows
    for a, b in zip(rows[:-1], rows[1:]):
        for j in range(len(a) - 1):
            bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
    # transom
    bm.faces.new(list(reversed(rows[0])))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_obj("Hull", bm, MAT["GelcoatHull"])
    # thickness so the shell reads at the sheer and the transom edge
    s = ob.modifiers.new("solid", "SOLIDIFY")
    s.thickness, s.offset = 0.012, -1
    apply_mods(ob)
    return ob


def hull_volume_below(z_cut=0.0, n=400, m=200):
    """Displaced volume and its centre for the canoe body below z_cut (both sides)."""
    vol, mx, mz = 0.0, 0.0, 0.0
    dx = (BOW - STERN) / n
    for i in range(n):
        x = STERN + (i + 0.5) * dx
        zk = keel_z(x)
        if zk >= z_cut:
            continue
        area, az = 0.0, 0.0
        for k in range(m):
            f0, f1 = k / m, (k + 1) / m
            y0, z0 = section(x, f0)
            y1, z1 = section(x, f1)
            if z0 >= z_cut:
                break
            z1c = min(z1, z_cut)
            frac = (z1c - z0) / max(z1 - z0, 1e-9)
            ym = y0 + (y1 - y0) * frac * 0.5
            da = 2 * ym * (z1c - z0)
            area += da
            az += da * (z0 + z1c) / 2
        vol += area * dx
        mx += area * dx * x
        mz += az * dx
    return vol, (mx / vol if vol else 0), (mz / vol if vol else 0)


# ------------------------------------------------------------------ deck mould

def deck_z(x, y):
    hb = max(half_beam(x), 1e-3)
    v = min(abs(y) / hb, 1.0)
    return sheer_z(x) + 0.055 * (1 - v * v) * min(1.0, hb / 0.6)


def build_deck():
    """Deck surface with the cockpit opening built into the grid: side-deck columns follow the coaming line."""
    xs = sorted(set([round(x, 5) for x in stations(120)] + [CABIN_AFT, COCKPIT_AFT]))
    n_in, n_out = 24, 8
    bm = bmesh.new()
    top, bot = [], []
    for x in xs:
        hb = half_beam(x) - 0.004
        yb = max(hb - min(SIDE_DECK, 0.3 * hb), 0.0)
        ys = [yb * j / n_in for j in range(-n_in, n_in + 1)]
        ys = [-(yb + (hb - yb) * k / n_out) for k in range(n_out, 0, -1)] + ys + [yb + (hb - yb) * k / n_out for k in range(1, n_out + 1)]
        rt = [bm.verts.new((x, y, deck_z(x, y))) for y in ys]
        rb = [bm.verts.new((x, y, deck_z(x, y) - 0.035)) for y in ys]
        top.append(rt)
        bot.append(rb)
    k = len(top[0])

    def hole(i, j):
        xm = (xs[i] + xs[i + 1]) / 2
        return COCKPIT_AFT < xm < CABIN_AFT and n_out <= j < k - 1 - n_out

    for i in range(len(xs) - 1):
        for j in range(k - 1):
            if hole(i, j):
                continue
            bm.faces.new((top[i][j], top[i][j + 1], top[i + 1][j + 1], top[i + 1][j]))
            bm.faces.new((bot[i + 1][j], bot[i + 1][j + 1], bot[i][j + 1], bot[i][j]))
        for j in (0, k - 1):
            q = (top[i][j], top[i + 1][j], bot[i + 1][j], bot[i][j])
            bm.faces.new(q if j == 0 else q[::-1])
    for g, rev in ((0, False), (-1, True)):
        ring = top[g] + list(reversed(bot[g]))
        bm.faces.new(ring[::-1] if rev else ring)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj("Deck", bm, MAT["Gelcoat"])


def cockpit_prism(name, xf, xa, hb_fn, z0, z1, r=0.08, n=40, inset=0.0):
    """A vertical prism over the cockpit plan (rounded aft corners), outline following hb_fn(x) - inset."""
    pts = []
    for i in range(n + 1):
        x = xf + (xa - xf) * i / n
        pts.append((x, hb_fn(x) - inset))
    outline = pts + [(x, -y) for x, y in reversed(pts)]
    bm = bmesh.new()
    lo = [bm.verts.new((x, y, z0)) for x, y in outline]
    hi = [bm.verts.new((x, y, z1)) for x, y in outline]
    k = len(outline)
    for i in range(k):
        bm.faces.new((lo[i], lo[(i + 1) % k], hi[(i + 1) % k], hi[i]))
    bm.faces.new(lo[::-1])
    bm.faces.new(hi)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_obj(name, bm, None, smooth_shade=False)
    if r:
        b = ob.modifiers.new("bev", "BEVEL")
        b.affect = "EDGES"
        b.width, b.segments, b.limit_method = r, 6, "ANGLE"
        b.angle_limit = math.radians(60)
        apply_mods(ob)
    return ob


def _fillet(poly, r, n=4):
    """Round every corner of an open polyline by r (2D points)."""
    out = [poly[0]]
    for a, b, c in zip(poly[:-2], poly[1:-1], poly[2:]):
        a, b, c = Vector(a), Vector(b), Vector(c)
        u, w = (a - b).normalized(), (c - b).normalized()
        rr = min(r, (a - b).length * 0.45, (c - b).length * 0.45)
        p0, p1 = b + u * rr, b + w * rr
        for k in range(n + 1):
            t = k / n
            q = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t * t * p1
            out.append((q.x, q.y))
    out.append(poly[-1])
    return out


def build_cockpit():
    """Cockpit liner lofted along the boat: coaming faces, seats, seat fronts and floor, plus the two end bulkheads."""
    xf, xa = CABIN_AFT + 0.01, COCKPIT_AFT
    n = 50
    t = 0.02
    bm = bmesh.new()
    rings = []
    for i in range(n + 1):
        x = xf + (xa - xf) * i / n
        w = half_beam(x) - SIDE_DECK
        top = deck_z(x, w) + 0.012
        half = [(w + 0.03, top), (w, top), (w, SEAT_Z), (SEAT_IN, SEAT_Z), (SEAT_IN, FLOOR_Z), (0.0, FLOOR_Z + 0.006)]
        inner = _fillet(half, 0.035)
        prof = [(-y, z) for y, z in inner] + list(reversed(inner))[1:]
        rings.append([bm.verts.new((x, y, z)) for y, z in prof])
    k = len(rings[0])
    for a, b in zip(rings[:-1], rings[1:]):
        for j in range(k - 1):
            bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
    bm.normal_update()
    floor = min(bm.faces, key=lambda f: f.calc_center_median().z)
    if floor.normal.z < 0:
        for f in bm.faces:
            f.normal_flip()
    liner = mesh_obj("Cockpit", bm, MAT["Gelcoat"])
    sol = liner.modifiers.new("solid", "SOLIDIFY")
    sol.thickness, sol.offset = t, -1
    apply_mods(liner)
    parts = [liner]
    # aft bulkhead under the aft deck and forward bulkhead under the companionway
    for x0, x1 in ((xa - t, xa + 0.001), (xf - 0.001, xf + t)):
        wv = half_beam((x0 + x1) / 2) - SIDE_DECK
        parts.append(box("Bulkhead", x0, x1, -wv, wv, FLOOR_Z - t, deck_z((x0 + x1) / 2, wv) + 0.01, MAT["Gelcoat"]))
    ob = join("Cockpit", parts)
    return ob


def cabin_ring(t, inset=0.0, z_floor=None, top_extra=0.0):
    """One section of the cabin trunk at fraction t from its aft end. inset > 0 gives the inside of a trunk wall that
    thick (the cabin's headliner), dropped to z_floor below the deck so it can cut the deck open too."""
    x = CABIN_AFT + (CABIN_FWD - CABIN_AFT) * t
    # plan half-width at the deck: inboard edge of the side deck, rounding in to the nose over the last fifth
    side_line = half_beam(x) - SIDE_DECK - 0.015
    nose = smooth((t - 0.80) / 0.20)
    w = max(side_line * math.sqrt(max(1 - nose ** 2.4, 0.0)), 0.0) + 0.02
    hgt = CABIN_H0 - 0.06 * t                          # trunk height above the deck at the centreline
    front = smooth((t - 0.74) / 0.26)                   # long raked forward face
    hgt *= (1 - 0.90 * front)
    zb = deck_z(x, 0) - 0.06
    zt = deck_z(x, 0) + hgt
    zs = deck_z(x, min(w, half_beam(x) - 0.05)) + 0.005
    lean = 0.035 * (1 - front) + 0.02                   # sides lean inboard a few degrees
    wt = max(w - lean, 0.01)
    r = 0.035 * (1 - 0.5 * front)                       # corner radius between side and top
    if inset:
        w, wt, zt = max(w - inset, 0.005), max(wt - inset, 0.005), zt - inset - top_extra
        r = max(r - inset * 0.5, 0.008)
        zb = zs = z_floor if z_floor is not None else zb
    return [(x, -w - 0.02 * (not inset), zb), (x, -w, zs), (x, -wt + 0.002, zt - r * 1.6), (x, -wt + r * 0.35, zt - r * 0.35),
            (x, -wt + r * 1.6, zt - 0.002), (x, -wt * 0.5, zt + 0.010), (x, 0, zt + 0.014),
            (x, wt * 0.5, zt + 0.010), (x, wt - r * 1.6, zt - 0.002), (x, wt - r * 0.35, zt - r * 0.35),
            (x, wt - 0.002, zt - r * 1.6), (x, w, zs), (x, w + 0.02 * (not inset), zb)]


def cabin_top_z(x, y=0.0):
    """Height of the cabin top's outer surface at (x, y), from the same sections build_cabin lofts."""
    t = min(max((x - CABIN_AFT) / (CABIN_FWD - CABIN_AFT), 0.0), 1.0)
    pts = sorted(cabin_ring(t)[2:11], key=lambda p: p[1])
    y = min(max(y, pts[0][1]), pts[-1][1])
    for a, b in zip(pts, pts[1:]):
        if a[1] <= y <= b[1]:
            f = (y - a[1]) / max(b[1] - a[1], 1e-9)
            return a[2] + (b[2] - a[2]) * f
    return pts[len(pts) // 2][2]


def build_cabin():
    """Cabin trunk as on TX 7295 EC (dock photo IMG_9224): low and wide, its sides almost upright and standing just
    inboard of the side decks, a flat lightly cambered top with tight corner radii, and a long raked front that runs
    down to the foredeck ahead of the mast."""
    n = 72
    bm = bmesh.new()
    rings = [[bm.verts.new(pt) for pt in cabin_ring(i / n)] for i in range(n + 1)]
    for a_, b_ in zip(rings[:-1], rings[1:]):
        # the last face is the trunk's bottom, hidden under the deck: it closes the solid so the interior's booleans are clean
        for j in range(len(a_)):
            k = (j + 1) % len(a_)
            bm.faces.new((a_[j], a_[k], b_[k], b_[j]))
    bm.faces.new(rings[0])
    bm.faces.new(list(reversed(rings[-1])))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_obj("Cabin", bm, MAT["CabinGelcoat"])
    sub = ob.modifiers.new("sub", "SUBSURF")
    sub.levels = 1
    apply_mods(ob)
    # companionway opening and its sliding hatch garage
    comp = box("comp", CABIN_AFT - 0.2, CABIN_AFT + 0.55, -0.26, 0.26, SEAT_Z - 0.05, 2.0)
    boolean(ob, comp)
    return ob


# ------------------------------------------------------------------ appendages

def naca(t, x):
    return 5 * t * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x * x + 0.2843 * x ** 3 - 0.1036 * x ** 4)


def foil(name, root_le, root_te, tip_le, tip_te, z_root, z_tip, thick=0.12, n=36, m=24, mat=None, round_tip=True):
    bm = bmesh.new()
    rings = []
    for i in range(m + 1):
        s = i / m
        le = root_le + (tip_le - root_le) * s
        te = root_te + (tip_te - root_te) * s
        z = z_root + (z_tip - z_root) * s
        c = le - te
        tt = thick * (1 - 0.35 * s ** 6) if round_tip else thick
        ring = []
        for k in range(n):
            a = 2 * math.pi * k / n
            xc = 0.5 * (1 + math.cos(a))
            y = naca(tt, xc) * c * (1 if a < math.pi else -1)
            ring.append(bm.verts.new((le - xc * c, y, z)))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(n):
            bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_obj(name, bm, mat)
    return ob


def keel_edges(z):
    """Keel leading and trailing edge x at height z: the class template (docs/boatkit-3) at MPA, 216 mm under the hull,
    and MPC, 483 mm lower: chords 0.965 and 0.603 m, trailing edge 2.90 m forward of the transom at MPA. The rule's
    trailing edge rakes 12 cm forward between them; the broadside photo shows it near plumb, so it rakes 2 cm here."""
    d = KEEL_MPA_Z - z                              # depth below MPA
    return 0.465 - 0.708 * d, -0.500 + 0.041 * d


KEEL_MPA_Z = keel_z(0.0) - 0.216


def build_keel():
    z_root, z_tip = keel_z(0.0) + 0.05, -1.16
    (rl, rt), (tl, tt) = keel_edges(z_root), keel_edges(z_tip)
    k = foil("Keel", rl, rt, tl, tt, z_root, z_tip, thick=0.12, mat=MAT["KeelLead"])
    return k


# ------------------------------------------------------------------ deck hardware

def toe_rail(side):
    pts = []
    for x in stations(80):
        if x < STERN + 0.03 or x > BOW - 0.18:
            continue
        hb = half_beam(x)
        pts.append((x, side * (hb - 0.022), deck_z(x, hb - 0.022) + 0.012))
    ob = tube(f"ToeRail_{side}", pts, 0.019, MAT["TeakWeathered"], smooth_path=True)
    ob.data.bevel_resolution = 1
    return ob


def hull_joint(side):
    pts = []
    for x in stations(80):
        if x < STERN + 0.01 or x > BOW - 0.05:
            continue
        pts.append((x, side * (half_beam(x) + 0.004), sheer_z(x) - 0.012))
    ob = tube(f"Joint_{side}", pts, 0.010, MAT["RubRail"], smooth_path=True)
    ob.data.bevel_resolution = 1
    return ob


def coaming_cap(side):
    pts = []
    for i in range(40):
        x = CABIN_AFT - 0.02 + (COCKPIT_AFT + 0.08 - CABIN_AFT) * i / 39
        y = half_beam(x) - SIDE_DECK + 0.04
        pts.append((x, side * y, deck_z(x, y) + 0.012))
    ob = tube(f"CoamingCap_{side}", pts, 0.022, MAT["TeakWeathered"], smooth_path=True)
    ob.data.bevel_resolution = 1
    return ob


def handrail(side):
    """Teak grab rail on the cabin top: a bar on loops."""
    x0, x1 = CABIN_AFT + 0.26, CABIN_AFT + 1.35          # starts forward of the jib winch on the cabin top's aft corner
    y = side * 0.46
    zt = lambda x: deck_z(x, 0) + (CABIN_H0 - 0.06 * (x - CABIN_AFT) / (CABIN_FWD - CABIN_AFT)) - 0.02  # noqa: E731
    parts = [box(f"HR_bar_{side}", x0, x1, y - 0.016, y + 0.016, zt(x0) + 0.045, zt(x0) + 0.07, MAT["TeakWeathered"], bev=0.006)]
    for i in range(5):
        x = x0 + 0.06 + (x1 - x0 - 0.12) * i / 4
        parts.append(box(f"HR_leg_{side}_{i}", x - 0.03, x + 0.03, y - 0.016, y + 0.016, zt(x) - 0.01, zt(x) + 0.05, MAT["TeakWeathered"], bev=0.006))
    return join(f"Handrail_{side}", parts)


KIT_MATS = {"Teak": "TeakWeathered", "Wood": "TeakVarnish", "Deck": "Gelcoat", "CabinWindow": "HatchAcrylic"}


def kit_part(name, part, at, yaw=0.0, surface=None, **kw):
    """A fitting from the shared boat kit (Tools/boatkit/bk_parts.py) placed at `at` (its mounting face, +Z up, +X forward,
    turned by yaw), its material slots taken over by the hero's materials of the same name. surface(x, y) -> z, when
    given, sets the height and tilts the part to sit flat on it. The part's sockets are kept as custom properties
    (sock_<Name>, local metres) for bake_j22_hero.py, and the empties dropped."""
    ob = KIT.build(part, **kw)
    ob.name = ob.data.name = name
    for c in list(ob.children):
        ob[f"sock_{c.name[len('SOCKET_'):].split('.')[0]}"] = list(c.location)
        bpy.data.objects.remove(c, do_unlink=True)
    for slot in ob.material_slots:
        if slot.material:
            base = slot.material.name.split(".")[0]
            slot.material = MAT[KIT_MATS.get(base, base)]
    rot = Matrix.Rotation(yaw, 4, "Z")
    if surface:
        x, y = at[0], at[1]
        at = (x, y, surface(x, y))
        h = 0.02
        n = Vector(((surface(x - h, y) - surface(x + h, y)) / (2 * h), (surface(x, y - h) - surface(x, y + h)) / (2 * h), 1.0)).normalized()
        fx = (rot.to_3x3() @ Vector((1, 0, 0)))
        fx = (fx - n * fx.dot(n)).normalized()
        rot = Matrix((fx, n.cross(fx), n)).transposed().to_4x4()
    ob.matrix_world = Matrix.Translation(at) @ rot
    return [ob]


def cleat(name, at, along_x=True, size=0.15):
    """Horn cleat: tapered horns on two feet, two through-bolts."""
    x, y, z = at
    L, w = size, size * 0.17
    ax = Vector((1, 0, 0)) if along_x else Vector((0, 1, 0))
    M4 = D.frame((x, y, z), ax)
    parts = [D.lbox(name + "_horn", (0, 0, 0.037), (L, w, 0.014), MAT["CastAlu"], bev=0.006)]
    for dx in (-L / 4, L / 4):
        parts.append(D.lbox(name + "_foot", (dx, 0, 0.017), (0.026, w * 1.1, 0.034), MAT["CastAlu"], bev=0.006))
    D._place(parts, M4)
    parts += D.screws(name, [M4 @ Vector((dx, 0, 0.034)) + Vector((0, 0, 0.0)) for dx in (-L / 4, L / 4)], (0, 0, 1), MAT)
    return parts


def build_hardware():
    parts = []
    for side in (1, -1):
        parts.append(toe_rail(side))
        parts.append(coaming_cap(side))
        parts.append(hull_joint(side))
        parts.append(handrail(side))
        # coaming face: jib-sheet cam cleats with fairlead blocks below (photo IMG_9272)
        for k, x in enumerate((-1.05, -1.55)):
            yw = half_beam(x) - SIDE_DECK - 0.025
            zc = (SEAT_Z + deck_z(x, yw)) / 2 + 0.05
            parts += D.cam_cleat(f"Cam_{side}_{k}", (x, side * yw, zc), (0, -side, 0), (1, 0, 0), MAT)
            parts += D.block(f"Fair_{side}_{k}", (x + 0.03, side * (yw - 0.03), zc - 0.075), (0, side, 0), (0, side, 1), MAT, 0.029)
            parts += D.padeye(f"FairEye_{side}_{k}", (x + 0.03, side * yw, zc - 0.04), (0, -side, 0), MAT)
        # jib winch on the cabin top's aft outboard corner (photos IMG_9224 and IMG_9272, docs/boatkit-2): the kit's size 16
        parts += kit_part(f"Winch_{side}", "Winch16", (CABIN_AFT + 0.12, side * 0.74), surface=lambda x, y: cabin_top_z(x, y) - 0.002)
        # jib track and car on the cabin top outboard of the handrail: inboard leads (photo IMG_9224), the kit's T-track
        parts += kit_part(f"JibTrack_{side}", "JibTrack", (0.15, side * 0.62), surface=lambda x, y: cabin_top_z(x, y) - 0.002, length=0.70)
        # one chainplate a side on the side deck, upper shroud on its aft hole and lower on its forward one (photos)
        xc = CHAINPLATE_X
        yc = half_beam(xc) - 0.09
        parts += D.chainplate(f"Chainplate_{side}", (xc, side * yc, deck_z(xc, yc)), MAT, span=0.072)
        # stern cleats and backstay chainplates at the transom corners
        xs = STERN + 0.20
        ys = half_beam(xs) - 0.14
        parts += cleat(f"SternCleat_{side}", (xs, side * ys, deck_z(xs, ys)))
        parts.append(box(f"BS_plate_{side}", STERN + 0.03, STERN + 0.09, side * (half_beam(STERN) - 0.10) - 0.004, side * (half_beam(STERN) - 0.10) + 0.004,
                         sheer_z(STERN) - 0.005, sheer_z(STERN) + 0.06, MAT["Stainless"], bev=0.003))
    # bow: stem fitting for the forestay, mooring cleat
    sx = BOW - 0.07
    parts.append(box("StemFitting", sx - 0.06, sx + 0.06, -0.005, 0.005, sheer_z(sx) - 0.01, sheer_z(sx) + 0.08, MAT["Stainless"], bev=0.004))
    parts += D.clevis("StemPin", (sx, 0, sheer_z(sx) + 0.06), (0, 1, 0), MAT, 0.02, 0.003)
    parts += D.screws("StemS", [(sx + dx, 0, deck_z(sx + dx, 0) + 0.001) for dx in (-0.05, 0.05)], (0, 0, 1), MAT)
    # Boat fidelity 3 (Bean's J/22 photos, bow-hardware): two horn cleats abreast near the bow, not one on the centreline.
    # The starboard one keeps the name (its horn is the BowCleat socket).
    for side, nm in ((-1, "BowCleat"), (1, "BowCleat_P")):
        bx, by = BOW - 0.42, side * 0.13
        parts += cleat(nm, (bx, by, deck_z(bx, by)), along_x=True, size=0.13)
    # the cockpit drains' outlets on the transom, just above the water: white flanges round a dark bore (photo
    # aft-drainholes-on-transom)
    for side in (1, -1):
        dz, dy = 0.17, side * 0.30
        parts.append(cyl(f"DrainFlange_{side}", (STERN + 0.004, dy, dz), (STERN - 0.008, dy, dz), 0.030, MAT["WhitePlastic"], 28))
        parts.append(cyl(f"DrainBore_{side}", (STERN - 0.0075, dy, dz), (STERN - 0.0095, dy, dz), 0.016, MAT["BlackPlastic"], 20))
    # spinnaker sheet leads on the side decks abreast of the cockpit's forward end: a block on a spring stand and a cam
    # cleat behind it (photos deck-hardware, port-jib-sheet)
    for side in (1, -1):
        xl = CABIN_AFT - 0.20
        yl = half_beam(xl) - SIDE_DECK * 0.45
        zl = deck_z(xl, yl)
        parts.append(cyl(f"SpinStand_{side}", (xl, side * yl, zl), (xl, side * yl, zl + 0.035), 0.004, MAT["Stainless"], 10))
        for k in range(5):
            t = D.torus(f"SpinSpring_{side}_{k}", 0.008, 0.0012, MAT["Stainless"], 14, 6)
            t.matrix_world = Matrix.Translation((xl, side * yl, zl + 0.005 + 0.006 * k))
            parts.append(t)
        parts += D.block(f"SpinLead_{side}", (xl, side * yl, zl + 0.055), (0, 1, 0), (0, 0, -1), MAT, 0.029)
        xc2 = xl - 0.14
        yc2 = half_beam(xc2) - SIDE_DECK * 0.45
        parts += D.cam_cleat(f"SpinCam_{side}", (xc2, side * yc2, deck_z(xc2, yc2)), (0, 0, 1), (-1, 0, 0), MAT)
    # fore hatch (GUESS on its size): on the flat of the cabin top between the mast step and the raked face
    hx0, hx1 = FWD_HATCH
    hxc = 0.5 * (hx0 + hx1)
    zt = deck_z(hxc, 0) + CABIN_H0 - 0.06 * (hxc - CABIN_AFT) / (CABIN_FWD - CABIN_AFT)
    parts.append(box("FwdHatch", hx0, hx1, -0.26, 0.26, zt - 0.02, zt + 0.035, MAT["HatchAcrylic"], bev=0.015))
    parts.append(box("FwdHatchFrame", hx0 - 0.02, hx1 + 0.02, -0.28, 0.28, zt - 0.03, zt + 0.02, MAT["Aluminium"], bev=0.008))
    # sliding companionway hatch and its rails
    za = deck_z(CABIN_AFT, 0) + CABIN_H0
    # #235 gaps (photos companionway-1, companionway-lookinto, companionway-rail-port): the hatch is varnished marine
    # plywood; teak trims run along both sides of the opening beside the closed hatch and frame its aft face either side
    # of the drop board (clear of the halyard cams at 0.335 m out).
    parts.append(box("SlideHatch", CABIN_AFT - 0.02, CABIN_AFT + 0.62, -0.30, 0.30, za + 0.005, za + 0.035, MAT["PlywoodVarnish"], bev=0.012))
    parts.append(box("DropBoard", CABIN_AFT - 0.012, CABIN_AFT + 0.012, -0.24, 0.24, SEAT_Z + 0.02, za - 0.02, MAT["TeakWeathered"], bev=0.004))
    for side in (1, -1):
        parts.append(box(f"CompTrim_{side}", CABIN_AFT - 0.02, CABIN_AFT + 0.55, side * 0.301, side * 0.316, za - 0.002, za + 0.028,
                         MAT["TeakWeathered"], bev=0.004))
        parts.append(box(f"CompPost_{side}", CABIN_AFT - 0.022, CABIN_AFT - 0.002, side * 0.240, side * 0.280, SEAT_Z + 0.02, za + 0.004,
                         MAT["TeakWeathered"], bev=0.004))
    # mast step, halyard turning blocks, organisers and cam cleats on the cabin top
    zm = deck_z(MAST_X, 0) + CABIN_H0 - 0.06 * (MAST_X - CABIN_AFT) / (CABIN_FWD - CABIN_AFT)
    parts.append(box("MastStep", MAST_X - 0.10, MAST_X + 0.10, -0.06, 0.06, zm - 0.005, zm + 0.03, MAT["Aluminium"], bev=0.006))
    # Boat fidelity 3: six turning blocks fanning round the step (photos mast-bottom-closeup, mast-sheetsandhardware)
    for k, dy in enumerate((-0.15, -0.10, -0.05, 0.05, 0.10, 0.15)):
        parts += D.block(f"Turn_{k}", (MAST_X - 0.12, dy, zm + 0.035), (1, 0, 0), (0, 0, -1), MAT, 0.029)
    for side in (1, -1):
        xo = CABIN_AFT + 0.75
        zo = cabin_top_z(xo, side * 0.12)
        parts.append(box(f"Organiser_{side}", xo - 0.04, xo + 0.04, side * 0.12 - 0.06, side * 0.12 + 0.06, zo - 0.005, zo + 0.03, MAT["BlackPlastic"], bev=0.006))
        for k in range(3):
            # cam cleats either side of the sliding hatch, just forward of its aft end
            # (4.5 cm apart from 3.35 cm out: at 5.5 cm the outer cam ran into the handrail at 0.46)
            yc = side * (0.335 + 0.045 * k)
            parts += D.cam_cleat(f"HalCam_{side}_{k}", (CABIN_AFT + 0.30, yc, cabin_top_z(CABIN_AFT + 0.30, yc)), (0, 0, 1), (-1, 0, 0), MAT)
    # traveler across the cockpit floor (photos IMG_9266/9271) with its car and mainsheet blocks
    xt = -1.95
    parts.append(box("TravelerBar", xt - 0.02, xt + 0.02, -SEAT_IN + 0.02, SEAT_IN - 0.02, FLOOR_Z, FLOOR_Z + 0.03, MAT["Aluminium"], bev=0.005))
    parts.append(box("TravelerCar", xt - 0.04, xt + 0.04, 0.05, 0.13, FLOOR_Z + 0.03, FLOOR_Z + 0.06, MAT["BlackPlastic"], bev=0.008))
    for sgn in (-1, 1):
        parts.append(box(f"TravEnd_{sgn}", xt - 0.03, xt + 0.03, sgn * (SEAT_IN - 0.06) - 0.02, sgn * (SEAT_IN - 0.06) + 0.02, FLOOR_Z, FLOOR_Z + 0.045, MAT["CastAlu"], bev=0.008))
        parts += D.screws(f"TravS_{sgn}", [(xt, sgn * (SEAT_IN - 0.06), FLOOR_Z + 0.045)], (0, 0, 1), MAT)
    parts += D.block("MainsheetLow", (xt, 0.09, FLOOR_Z + 0.12), (1, 0, 0), (0, 0, -1), MAT, 0.057, becket=True)
    parts += D.cam_cleat("MainCam", (xt - 0.02, 0.09, FLOOR_Z + 0.075), (0, 0, 1), (1, 0, 0), MAT, 0.055)
    # aft deck: inspection port
    xp = (STERN + COCKPIT_AFT) / 2 - 0.02
    parts.append(cyl("DeckPlate", (xp, 0.30, deck_z(xp, 0.3) - 0.002), (xp, 0.30, deck_z(xp, 0.3) + 0.012), 0.075, MAT["WhitePlastic"], 32))
    # #235 gaps (photo transom-worn): a teak strip along the top of the transom just under the deck edge, short of the
    # rounded corners
    yt = half_beam(STERN) - 0.07
    zt0 = min(deck_z(STERN, 0.0), deck_z(STERN, yt))
    parts.append(box("TransomTeak", STERN - 0.014, STERN + 0.001, -yt, yt, zt0 - 0.045, zt0 - 0.012, MAT["TeakWeathered"], bev=0.004))
    # outboard bracket and motor on the port quarter (photos transom-worn, aft-transom): pc/j22-detail assembly 2, j22_outboard.py
    import j22_outboard as OUTBOARD  # noqa: E402
    parts += OUTBOARD.build(MAT)
    return parts


# ------------------------------------------------------------------ rig

MAST_TOP = 9.25
HOUNDS = 7.86            # GUESS: forestay hounds, I = 7.56 above the sheer at the mast
SPREADER_Z = 4.60        # GUESS
BOOM_Z = 1.45
BOOM_LEN = 2.70          # GUESS: E


def spar(name, p0, p1, w_fa, w_at, mat, taper_top=0.0, n=28):
    """Oval extrusion with an aft sail-track groove, optionally tapered at the top."""
    p0, p1 = Vector(p0), Vector(p1)
    L = (p1 - p0).length
    bm = bmesh.new()
    rings = []
    steps = 16
    for i in range(steps + 1):
        s = i / steps
        k = 1 - taper_top * smooth((s - 0.82) / 0.18)
        ring = []
        for j in range(n):
            a = 2 * math.pi * j / n
            r = 1.0 - (0.12 if abs(math.cos(a) + 1) < 0.08 else 0.0)
            ring.append(bm.verts.new((math.cos(a) * w_fa * 0.5 * k * r, math.sin(a) * w_at * 0.5 * k, s * L)))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for j in range(n):
            bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    ob = mesh_obj(name, bm, mat)
    ob.matrix_world = Matrix.Translation(p0) @ (p1 - p0).to_track_quat("Z", "X").to_matrix().to_4x4()
    return ob


def build_rig():
    zm = deck_z(MAST_X, 0) + CABIN_H0 - 0.06 * (MAST_X - CABIN_AFT) / (CABIN_FWD - CABIN_AFT)
    mast = spar("Mast", (MAST_X, 0, zm), (MAST_X - 0.02, 0, MAST_TOP), 0.098, 0.068, MAT["Aluminium"], taper_top=0.35)
    parts = [mast]
    rake = lambda z: MAST_X - 0.02 * (z - zm) / (MAST_TOP - zm)  # noqa: E731
    aft_face = lambda z: rake(z) - 0.049  # noqa: E731
    parts += D.masthead("Masthead", (rake(MAST_TOP), 0, MAST_TOP), MAT, windex=STYLE["details"]["windex"])
    parts += D.hounds_tang("Hounds", (rake(HOUNDS), 0, HOUNDS), MAT)
    # mast base: collar, halyard exit plates, sheaves at the step
    parts.append(cyl("MastCollar", (MAST_X, 0, zm), (MAST_X, 0, zm + 0.06), 0.058, MAT["CastAlu"], 32))
    for k, (side, zz) in enumerate(((1, 0.55), (-1, 0.55), (1, 0.75))):
        parts.append(box(f"ExitPlate_{k}", MAST_X - 0.03, MAST_X + 0.01, side * 0.033, side * 0.037, zm + zz - 0.06, zm + zz + 0.06, MAT["CastAlu"], bev=0.002))
    tips = []
    for side in (1, -1):
        root = Vector((rake(SPREADER_Z), side * 0.035, SPREADER_Z))
        tip = root + Vector((-0.26, side * 0.70, 0.04))
        tips.append(tip)
        parts.append(spar(f"Spreader_{side}", root, tip, 0.018, 0.045, MAT["Aluminium"]))
        parts += D.spreader_root(f"SprRoot_{side}", (rake(SPREADER_Z), 0, SPREADER_Z), side, MAT)
        parts += D.spreader_tip(f"SprTip_{side}", tip, (tip - root), MAT)
    wires = []
    for side, tip in zip((1, -1), tips):
        xc = CHAINPLATE_X - 0.02
        yc = side * (half_beam(xc) - 0.09)
        zc = deck_z(xc, abs(yc)) + 0.055
        up_target = Vector(tip)
        tb, top = D.turnbuckle(f"TB_up_{side}", (xc, yc, zc), up_target - Vector((xc, yc, zc)), MAT)
        parts += tb
        wires.append(tube(f"Upper_{side}", [tuple(top), tuple(tip), (rake(HOUNDS), side * 0.03, HOUNDS - 0.02)], 0.002, MAT["Wire"]))
        xa = CHAINPLATE_X + 0.02
        ya = side * (half_beam(xa) - 0.09)
        lo_top = Vector((rake(SPREADER_Z), side * 0.035, SPREADER_Z - 0.05))
        tb, top = D.turnbuckle(f"TB_lo_{side}", (xa, ya, deck_z(xa, abs(ya)) + 0.055), lo_top - Vector((xa, ya, deck_z(xa, abs(ya)) + 0.055)), MAT)
        parts += tb
        wires.append(tube(f"Lower_{side}", [tuple(top), tuple(lo_top)], 0.002, MAT["Wire"]))
    sx = BOW - 0.07
    fs_base = Vector((sx, 0, sheer_z(sx) + 0.06))
    fs_top = Vector((rake(HOUNDS) + 0.045, 0, HOUNDS - 0.03))
    tb, top = D.turnbuckle("TB_fore", fs_base, fs_top - fs_base, MAT)
    parts += tb
    wires.append(tube("Forestay", [tuple(top), tuple(fs_top)], 0.0025, MAT["Wire"]))
    # split backstay: wire from the masthead to a cascade block; bridle rope to both transom corners
    yb = half_beam(STERN) - 0.10
    apex = Vector((STERN + 0.45, 0, 2.20))
    for side in (1, -1):
        base = Vector((STERN + 0.06, side * yb, sheer_z(STERN) + 0.01))
        parts += D.padeye(f"BS_eye_{side}", base, (0, 0, 1), MAT)
        wires.append(tube(f"Bridle_{side}", DRAPE.line([tuple(base + Vector((0, 0, 0.012))), tuple(apex - Vector((0, 0, 0.05)))], 0.002, 0.003),
                          0.003, MAT["RopeBackstay"], smooth_path=True))
    parts += D.block("BS_cascade", apex - Vector((0, 0, 0.03)), (1, 0, 0), (0, 0, 1), MAT, 0.040)
    wires.append(tube("Backstay", [tuple(apex + Vector((0, 0, 0.04))), (rake(MAST_TOP) - 0.195, 0, MAST_TOP - 0.06)], 0.002, MAT["Wire"]))
    # boom: gooseneck at the mast's aft face, outhaul end, vang, mainsheet bails
    parts += D.gooseneck("Gooseneck", (aft_face(BOOM_Z), 0, BOOM_Z), BOOM_Z, MAT)
    b0 = Vector((aft_face(BOOM_Z) - 0.12, 0, BOOM_Z))
    b1 = Vector((b0.x - BOOM_LEN + 0.08, 0, BOOM_Z + 0.03))
    parts.append(spar("Boom", b0, b1, 0.075, 0.055, MAT["Aluminium"]))
    parts += D.boom_end("BoomEnd", b1, MAT)
    parts += D.vang("Vang", (MAST_X - 0.06, 0, zm + 0.10), (MAST_X - 0.80, 0, BOOM_Z - 0.03), MAT, MAT["RopeVang"])
    top = Vector((b1.x + 0.20, 0, BOOM_Z - 0.03))
    parts.append(D.tube("MainBail", [(top.x - 0.03, -0.03, top.z + 0.03), (top.x - 0.03, -0.03, top.z - 0.005), (top.x, 0, top.z - 0.02),
                                       (top.x + 0.03, 0.03, top.z - 0.005), (top.x + 0.03, 0.03, top.z + 0.03)], 0.003, MAT["Stainless"], smooth_path=True))
    blk_hi = top - Vector((0, 0, 0.07))
    parts += D.block("MainsheetHigh", blk_hi, (1, 0, 0), (0, 0, 1), MAT, 0.057)
    low = Vector((-1.95, 0.09, FLOOR_Z + 0.12))
    for k, dx in enumerate((-0.010, -0.0035, 0.0035, 0.010)):
        part = DRAPE.line([tuple(blk_hi + Vector((dx, 0, -0.02))), tuple(low + Vector((dx, 0, 0.03)))], 0.0015, 0.004)
        wires.append(tube(f"Mainsheet_{k}", part, 0.004, MAT["RopeMain"], smooth_path=True))
    # mainsheet tail from the ratchet block's cam, coiled on the cockpit floor
    parts += D.coil("MainTail", (-2.30, 0.05, FLOOR_Z), 0.13, 3.2, MAT["RopeMain"], seed=STYLE["seed"], flat_z=FLOOR_Z,
                    tail=[(-2.1, 0.07, FLOOR_Z + 0.03), (-2.0, 0.085, FLOOR_Z + 0.07)])
    # halyards: out of the exit plates, through the turning blocks, aft along the cabin top to the cam cleats
    for k, (side, dy) in enumerate(((1, 0.05), (-1, -0.05), (1, 0.10))):
        z0 = zm + 0.55
        yc = side * (0.34 + 0.055 * (k // 2))
        xo, xc = CABIN_AFT + 0.75, CABIN_AFT + 0.30
        path = [(MAST_X - 0.01, side * 0.036, z0), (MAST_X - 0.06, dy, zm + 0.05), (MAST_X - 0.20, dy * 1.4, cabin_top_z(MAST_X - 0.20, dy * 1.4) + 0.02),
                (xo, side * 0.12, cabin_top_z(xo, side * 0.12) + 0.018), (xo - 0.20, yc * 0.85, cabin_top_z(xo - 0.20, yc * 0.85) + 0.012),
                (xc + 0.03, yc, cabin_top_z(xc, yc) + 0.022)]
        wires.append(tube(f"Halyard_{k}", DRAPE.line(path, [0.0, 0.0, 0.004, 0.003, 0.002], 0.0042), 0.0042, MAT["RopeHalyard"], smooth_path=True))
        # tails coiled and dropped on the cabin top outboard of the hatch, between the cleats and the aft edge
        cx, cy = CABIN_AFT + 0.13 + 0.17 * (k // 2), side * 0.44
        parts += D.coil(f"HalTail_{k}", (cx, cy, 0), 0.05, 2.2, MAT["RopeHalyard"], r=0.0042,
                        seed=STYLE["seed"] + k, flat_z=cabin_top_z(cx, cy))
    return parts, wires


# ------------------------------------------------------------------ sails (flying shape, starboard tack close reach)

class Sail:
    """A flying sail: luff line, chord per height, camber, twist. point(h, u) gives the surface so fittings sit on it."""

    def __init__(self, luff_fn, chord_fn, depth, twist_deg, trim_deg, side, wrinkles=None):
        self.luff, self.chord, self.depth, self.twist, self.trim, self.side = luff_fn, chord_fn, depth, twist_deg, trim_deg, side
        self.wr = wrinkles
        self.shelf = 0.0      # > 0: the foot is held straight along the boom over this fraction of the luff

    def frame(self, h):
        ang = math.radians(self.trim + self.twist * h)
        d = Vector((-math.cos(ang), self.side * math.sin(ang), 0))
        nrm = Vector((-d.y, d.x, 0)) * self.side
        return d, nrm

    def point(self, h, u, off=0.0):
        d, nrm = self.frame(h)
        c = self.chord(h)
        dep = self.depth * (1 - 0.35 * h)
        if self.shelf:
            t = min(h / self.shelf, 1.0)
            dep *= t * t * (3 - 2 * t)
        camber = dep * c * 4 * u * (1 - u) * (1 - 0.25 * u)
        if self.wr:
            off += self.wr(h, u, c) * (min(h / 0.03, 1.0) if self.shelf else 1.0)
        return self.luff(h) + d * (c * u) - nrm * (camber + off)

    def mesh(self, name, mat, nu=48, nv=28):
        bm = bmesh.new()
        uv_layer = bm.loops.layers.uv.new("UVMap")
        grid = [[bm.verts.new(self.point(i / nu, j / nv)) for j in range(nv + 1)] for i in range(nu + 1)]
        for i in range(nu):
            for j in range(nv):
                f = bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
                for loop, (ii, jj) in zip(f.loops, ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j))):
                    loop[uv_layer].uv = (jj / nv, ii / nu)
        ob = mesh_obj(name, bm, mat)
        s = ob.modifiers.new("solid", "SOLIDIFY")
        s.thickness = 0.0015
        return ob


def build_sails():
    tack_z, head_z = BOOM_Z + 0.05, MAST_TOP - 0.18
    side = 1   # sails to port (starboard tack)
    mx = MAST_X - 0.07

    def main_luff(h):
        z = tack_z + (head_z - tack_z) * h
        return Vector((mx - 0.02 * (z - 1.0) / (MAST_TOP - 1.0), 0, z))

    def main_chord(h):
        roach = 0.20 * math.sin(math.pi * min(h / 0.95, 1.0)) * (1 - h * 0.3)
        return max((BOOM_LEN - 0.22) * (1 - h) + 0.14 * h + roach, 0.12)

    DRAPE.post(MAST_X, 0.0, 0.0, MAST_TOP, 0.055)
    age = STYLE["sails"]["age"]
    main = Sail(main_luff, main_chord, 0.10, 16, 1.5, side,   # foot on the centred boom
                Wrinkles(head_z - tack_z, BOOM_LEN - 0.22, age, STYLE["seed"], battens=(0.8, 0.6, 0.4, 0.2), loose=age))
    sx = BOW - 0.12
    tack = Vector((sx, 0, sheer_z(sx) + 0.14))
    head = Vector((MAST_X + 0.08, 0, HOUNDS - 0.14))

    def jib_luff(h):
        return tack + (head - tack) * h

    def jib_chord(h):
        return max(2.78 * (1 - h) ** 1.02, 0.05)          # GUESS: LP ~2.7 m, jib 10.1 m^2

    main.shelf = 0.07
    jib = Sail(jib_luff, jib_chord, 0.11, 12, 16, side,
               Wrinkles((head - tack).length, 2.78, age, STYLE["seed"] + 1, hanks=8, battens=(0.75, 0.5, 0.25), loose=age))
    objs = [main.mesh("Mainsail", MAT["SailMain"], nu=120, nv=64), jib.mesh("Jib", MAT["SailJib"], nu=96, nv=52)]
    lines = []
    _, n0 = main.frame(0)
    # main: tack and clew rings with webbing, cunningham and reef cringles, headboard, luff slugs, battens
    objs += D.ring("MainTackRing", main.point(0.005, 0.01), n0, MAT, 0.012)
    clew = main.point(0.005, 0.995)
    objs += D.ring("MainClewRing", clew, n0, MAT, 0.014)
    objs.append(tube("ClewWebbing", [tuple(clew), tuple(clew + Vector((-0.04, 0, -0.02)))], 0.006, MAT["BlackPlastic"]))
    objs += D.shackle("OuthaulSh", clew + Vector((-0.04, 0, -0.03)), (-1, 0, -0.3), MAT)
    objs += D.ring("Cunningham", main.point(0.035, 0.02), n0, MAT, 0.010)
    objs += D.ring("ReefLuff", main.point(0.13, 0.02), n0, MAT, 0.010)
    objs += D.ring("ReefLeech", main.point(0.13, 0.985), main.frame(0.13)[1], MAT, 0.012)
    hd_n = main.frame(1.0)[1]
    objs += D.headboard("Headboard", (main.point(1.0, 0.0), main.point(1.0, 0.95), main.point(0.965, 0.0)), hd_n, MAT)
    for k in range(1, 26):
        h = k / 26
        p = main.luff(h)
        objs.append(box(f"Slug_{k}", p.x - 0.006, p.x + 0.012, -0.004, 0.004, p.z - 0.015, p.z + 0.015, MAT["WhitePlastic"], bev=0.002))
    for k in range(1, 5):
        h = 1 - k / 5
        L = 0.32 if k in (2, 3) else 0.22
        pts = [tuple(main.point(h, 1 - L + L * t / 8, off=-0.0025)) for t in range(9)]
        objs.append(tube(f"Batten_{k}", pts, 0.0035, MAT["SailMain"]))
    # jib: piston hanks on the forestay, rings at the corners, leech battens, clew bowline and both sheets
    for k in range(1, 9):
        p = jib.luff(k / 9)
        objs.append(cyl(f"Hank_{k}", p - Vector((0.014, 0, 0.01)), p + Vector((0.014, 0, 0.01)), 0.0065, MAT["Bronze"], 12))
        objs.append(cyl(f"HankPiston_{k}", p + Vector((0.004, 0, 0.012)), p + Vector((0.004, 0, 0.028)), 0.0025, MAT["Bronze"], 8))
    objs += D.ring("JibTackRing", jib.point(0.005, 0.01), jib.frame(0)[1], MAT, 0.012)
    jclew = jib.point(0.003, 0.997)
    objs += D.ring("JibClewRing", jclew, jib.frame(0)[1], MAT, 0.014)
    objs += D.ring("JibHeadRing", jib.point(0.995, 0.3), jib.frame(1)[1], MAT, 0.010)
    objs += D.shackle("JibTackSh", tack - Vector((0, 0, 0.03)), (0, 0, 1), MAT)
    objs += D.stopper_knot("JibBowline", jclew + Vector((-0.02, 0, -0.01)), (-1, 0.3, 0), MAT["RopeJibPort"], 0.005)
    for k in range(1, 4):
        h = 1 - k / 4
        pts = [tuple(jib.point(h, 0.86 + 0.14 * t / 6, off=-0.0025)) for t in range(7)]
        objs.append(tube(f"JibBatten_{k}", pts, 0.003, MAT["SailJib"]))
    # the cabin-top lead (kit JibTrack's sheave) and the winch drum on the cabin top's aft corner (build_hardware)
    car = Vector((0.16, side * 0.62, cabin_top_z(0.15, 0.62) + 0.045))
    drum = Vector((CABIN_AFT + 0.12, side * (0.74 + 0.04), cabin_top_z(CABIN_AFT + 0.12, 0.74) + 0.05))
    xf = -1.05 + 0.03
    yf = half_beam(xf) - SIDE_DECK - 0.025 - 0.03
    zf = (SEAT_Z + deck_z(xf, yf)) / 2 + 0.05 - 0.075
    xc = -1.05
    zc = (SEAT_Z + deck_z(xc, yf + 0.03)) / 2 + 0.05
    lee = DRAPE.line([tuple(jclew), tuple(car + Vector((0, 0, 0.01))), tuple(car + Vector((-0.05, 0, -0.01))), tuple(drum),
                      (xf + 0.05, side * (yf + 0.01), deck_z(xf, yf) + 0.02), (xf, side * yf, zf + 0.01),
                      (xc, side * (yf + 0.012), zc), (xc - 0.06, side * (yf + 0.01), zc - 0.02)],
                     [0.002, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0], 0.0045)
    lines.append(tube("JibSheetLee", lee, 0.0045, MAT["RopeJibPort"], smooth_path=True))
    objs += D.coil("JibTailLee", (-1.45, side * (SEAT_IN + 0.18), SEAT_Z), 0.12, 2.6, MAT["RopeJibPort"], seed=STYLE["seed"] + 3, flat_z=SEAT_Z,
                   tail=[(-1.2, side * (yf - 0.02), SEAT_Z + 0.03), (xc - 0.07, side * (yf + 0.005), zc - 0.03)])
    # lazy (windward) sheet: slack over the foredeck, round the mast, back to its own car and cleat
    wcar = Vector((car.x, -car.y, car.z))
    wdrum = Vector((drum.x, -drum.y, drum.z))
    lazy = DRAPE.line([tuple(jclew), tuple(wcar + Vector((0.05, 0, 0.01))), tuple(wcar), tuple(wdrum),
                       (xf + 0.05, -side * (yf + 0.01), deck_z(xf, yf) + 0.02), (xf, -side * yf, zf + 0.01), (xc, -side * (yf + 0.012), zc)],
                      [0.22, 0.0, 0.03, 0.03, 0.0, 0.0], 0.0045)
    lines.append(tube("JibSheetLazy", lazy, 0.0045, MAT["RopeJibStbd"], smooth_path=True))
    objs += D.coil("JibTailLazy", (-1.50, -side * (SEAT_IN + 0.18), SEAT_Z), 0.11, 2.2, MAT["RopeJibStbd"], seed=STYLE["seed"] + 4, flat_z=SEAT_Z,
                   tail=[(-1.2, -side * (yf - 0.02), SEAT_Z + 0.03), (xc - 0.07, -side * (yf + 0.005), zc - 0.03)])
    # telltales: main leech at each batten, jib luff at three heights on both sides
    if STYLE["details"]["telltales"]:
        for k in range(1, 5):
            h = 1 - k / 5 + 0.03
            d, _ = main.frame(h)
            objs += D.telltale(f"TT_main_{k}", main.point(h, 1.0), d, MAT, "TelltaleRed" if k % 2 else "TelltaleGreen", seed=k)
        for k, h in enumerate((0.25, 0.5, 0.75)):
            d, nrm = jib.frame(h)
            for sgn, mat in ((1, "TelltaleRed"), (-1, "TelltaleGreen")):
                objs += D.telltale(f"TT_jib_{k}_{sgn}", jib.point(h, 0.12, off=sgn * 0.003), d, MAT, mat, 0.13, seed=10 + k)
    return objs, lines


# ------------------------------------------------------------------ registration and decals

def _project(ob, side, plane):
    mw = ob.matrix_world.copy()
    ob.matrix_world = Matrix.Identity(4)
    for v in ob.data.vertices:
        w = mw @ v.co
        f = (w.z - keel_z(w.x)) / (sheer_z(w.x) - keel_z(w.x))
        ys, _ = section(w.x, min(max(f, 0.0), 1.0))
        v.co = Vector((w.x, side * (ys + 0.0015) + (w.y - plane), w.z))


def build_registration():
    """State registration on both bows (style: a made-up TX number for the hero, never the lesson boat's) with the validation sticker,
    projected onto the hull. Texas wants 3 in block letters, the sticker within 6 in of the number."""
    out = []
    font = bpy.data.fonts.load(M.FONT)
    for side in (1, -1):
        cu = bpy.data.curves.new(f"Reg_{side}", "FONT")
        cu.body = STYLE["hull"]["registration"]
        cu.size = 0.11
        cu.extrude = 0.0006
        cu.align_x = "CENTER"
        cu.font = font
        ob = link(bpy.data.objects.new(f"Reg_{side}", cu))
        ob.data.materials.append(MAT["DecalBlack"])
        x = 1.85
        y, _ = section(x, 0.88)
        ob.location = (x, side * (y + 0.03), 0.45)
        ob.rotation_euler = (math.radians(90), 0, math.radians(180) if side > 0 else 0)
        ob.scale = (1.3, 1, 1)   # Saira Condensed widened to block-letter proportions (bakes legibly at 2048)
        ob = to_mesh(ob)
        _project(ob, side, side * (y + 0.03))
        out.append(ob)
        # validation sticker, aft of the number on both sides
        xs = 1.85 - side * 0 - 0.47
        stk = box(f"Sticker_{side}", xs - 0.037, xs + 0.037, side * (y + 0.03) - 0.0003, side * (y + 0.03) + 0.0003, 0.455, 0.53, MAT["Sticker"])
        apply_mods(stk)
        _project(stk, side, side * (y + 0.03))
        out.append(stk)
    return out


# ------------------------------------------------------------------ build

hull = build_hull()
deck = build_deck()
cockpit = build_cockpit()
cabin = build_cabin()
import types  # noqa: E402
import j22_interior as INTERIOR  # noqa: E402
interior = INTERIOR.build(types.SimpleNamespace(**globals()), cabin, deck, cockpit, hull)
DRAPE = Drape([o for o in (hull, deck, cockpit, cabin) if isinstance(o, bpy.types.Object)])
keel = build_keel()
# pc/j22-detail: the steering from Bean's photos (j22_steering.py): the blade and its head, the tiller and its straps, the
# extension, the pintles; the gudgeons stay with the hull
import j22_steering as STEER  # noqa: E402
rudder, gudgeons = STEER.build(MAT, D)
hw = build_hardware() + gudgeons
if STYLE.get("interior", {}).get("drop_board_stowed", True):
    # under way the drop board lives below, flat on the port bench, so the companionway shows the cabin
    db = bpy.data.objects["DropBoard"]
    hw.remove(db)
    bpy.data.objects.remove(db, do_unlink=True)
    interior.append(box("DropBoard", 0.12, 0.60, INTERIOR.BENCH_IN + 0.22, INTERIOR.BENCH_IN + 0.50, INTERIOR.BENCH_Z,
                        INTERIOR.BENCH_Z + 0.024, MAT["TeakWeathered"], bev=0.004))
rig, wires = build_rig()
regs = build_registration()
sails, sail_lines = build_sails() if SAILS else ([], [])

# collections for export
groups = {
    "Hull": [hull, keel] + regs,
    "Deck": [deck, cockpit, cabin],
    "Hardware": hw,
    "Rudder": rudder,
    "Rig": rig,
    "Rigging": wires + sail_lines,
    "Sails": sails,
    "Interior": interior,
}
for gname, obs in groups.items():
    coll = bpy.data.collections.new(gname)
    SC.collection.children.link(coll)
    for o in obs:
        o = bpy.data.objects.get(o.name)
        if o is None:
            continue
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)

# every braided line gets arc-length UVs so the braid keeps its true size along it (j22_rope)
import j22_rope as RP  # noqa: E402
for o in list(SC.objects):
    if o.type == "CURVE" and o.data.materials and o.data.materials[0] and o.data.materials[0].get("rope_kind"):
        wire = o.data.materials[0]["rope_kind"] == "Wire1x19"
        RP.rope_uv(o, 2 * o.data.bevel_depth, 11.0 if wire else 5.0)

vol, cbx, cbz = hull_volume_below()
tris = 0
dg = bpy.context.evaluated_depsgraph_get()
for o in SC.objects:
    if o.type in ("MESH", "CURVE", "FONT"):
        me = o.evaluated_get(dg).to_mesh()
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
        o.evaluated_get(dg).to_mesh_clear()
report = {"canoe_volume_m3": round(vol, 4), "physics_volume_m3": 1.052, "cb_x": round(cbx, 3), "cb_z": round(cbz, 3),
          "physics_cb": [-0.195, -0.080], "triangles": tris, "objects": len(SC.objects)}
print("J22H:", json.dumps(report))
json.dump(report, open(os.path.join(OUT, "j22_hero_report.json"), "w"), indent=1)
# Boat fidelity 4: the coiled tails the game draws as live rope (Blender frame, metres; the game flips Y).
json.dump({"frame": "Blender: X forward, Y to port, Z up, metres, the hull's origin", "coils": D.COILS},
          open(os.path.join(OUT, "J22H_coils.json"), "w"), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "j22_hero.blend"))
