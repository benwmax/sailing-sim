"""Boat fidelity (pc/j22-detail, assembly 1): the hero J/22's steering as Bean's photos show it (tiller, tiller-2,
tiller-transom-attachemnt, tiller-transom-attachemnt-2, transom-worn, aft-transom). Replaces build_rudder's guessed
cast cheeks and boxes and build_tiller's round tube:

- the blade's own head rising above the aft deck, its aft top corner on a large radius, thick and parallel-sided where
  the tiller straps hug it (no cast head: the photos show the gelcoat blade itself);
- the tiller pinned to the head by two stainless side straps on one big through-bolt (hex head, washer, nylock nut),
  the straps running into the tiller's end under three carriage bolts;
- a laminated tiller (ash and mahogany laminations, rectangular with eased edges), an open channel along its top near
  the head, sweeping down and up again to a rounded grip with a cam cleat; the extension's universal joint on the grip
  end and the extension folded aft along the top;
- each pintle on a polished strap down both faces of the blade, following its section, four staggered through-bolts,
  the pin through a gudgeon of two lugs: a barrel each, its strap folded flat onto the transom either side, two hex
  bolts a side, the pin's head on top and a keeper under the bottom lug.

The game's sockets for this assembly stay exactly where they were (J22H_sockets.json): the parts are built to meet them
and anchor_<Name> empties carry them to the bake (bake_j22_hero.py). Body frame metres, as build_j22_hero.py; this
module draws in Blender's frame (y mirrored), which the symmetric parts don't notice."""
import math

import bmesh
import bpy
from mathutils import Vector

from j22_geom import apply_mods, cyl, link, mesh_obj

PIVOT_X = -3.46            # RudderPivot: the pintles' common axis, 5 cm aft of the transom
STOCK_Z = 0.7042           # RudderStock: where the tiller leaves the head
TILLER_END = (-2.1597, 0.839)   # TillerEnd: the grip end (the tiller's top is 2 cm above it)
EXT_UJ = (-2.16, 0.87)          # TillerExtUJ
EXT_TIP = (-3.1815, 0.8175)     # TillerExtTip: the extension folded aft
TRANSOM_X = -3.41
PINTLE_Z = (0.47, 0.05)
HEAD_TOP = 0.80
LE_X = PIVOT_X - 0.016     # the blade's leading edge behind the pintle barrels


def naca(t, x):
    x = min(max(x, 0.0), 1.0)
    return 5 * t * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x * x + 0.2843 * x ** 3 - 0.1036 * x ** 4)


def smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ the blade

def blade_edges(z):
    """Leading and trailing edge x at height z (the blade below the deck as before; the head rounded aft)."""
    le = LE_X if z >= 0.40 else LE_X - 0.0174 * (0.40 - z)
    r = 0.035
    if z > HEAD_TOP - r:
        le -= r - math.sqrt(max(r * r - (z - (HEAD_TOP - r)) ** 2, 0.0))
    te = -3.81 - 0.02 * min(max((z + 0.98) / 1.53, 0.0), 1.0)
    R, zc = 0.24, 0.56
    if z > zc:
        te += R - math.sqrt(max(R * R - (z - zc) ** 2, 0.0))
    return le, te


def blade_thick(z, chord):
    """Thickness ratio: a 10% section in the water, the head 44 mm thick where the straps hug it."""
    head = min(0.044 / max(chord, 0.05), 0.30)
    return 0.10 + (head - 0.10) * smooth((z - 0.42) / 0.14)


def blade_half(x, z):
    """The blade's half thickness at (x, z): the surface the pintle straps lie on."""
    le, te = blade_edges(z)
    c = le - te
    return naca(blade_thick(z, c), (le - x) / c) * c


def build_blade(mat):
    zs = [-0.98 + (0.42 + 0.98) * i / 18 for i in range(19)] + [0.42 + (HEAD_TOP - 0.006 - 0.42) * i / 26 for i in range(1, 27)]
    n = 44
    bm = bmesh.new()
    rings = []
    for z in zs:
        le, te = blade_edges(z)
        c = le - te
        t = blade_thick(z, c)
        ring = []
        for k in range(n):
            a = 2 * math.pi * k / n
            xc = 0.5 * (1 + math.cos(a))
            y = naca(t, xc) * c * (1 if a < math.pi else -1)
            ring.append(bm.verts.new((le - xc * c, y, z)))
        rings.append(ring)
    # a rounded top: the last rings drawn in toward the section's middle
    le, te = blade_edges(HEAD_TOP - 0.006)
    mid = 0.5 * (le + te)
    for f, dz in ((0.82, 0.003), (0.45, 0.0055), (0.12, 0.0065)):
        ring = []
        for v in rings[len(zs) - 1]:
            ring.append(bm.verts.new((mid + (v.co.x - mid) * (0.6 + 0.4 * f), v.co.y * f, HEAD_TOP - 0.006 + dz)))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(n):
            bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj("Rudder", bm, mat)


# ------------------------------------------------------------------ small hardware

def plate(name, outline, y0, y1, mat, bev=0.0008):
    """A flat plate: outline (x, z) pairs extruded across y0..y1, its edges eased."""
    bm = bmesh.new()
    a = [bm.verts.new((x, y0, z)) for x, z in outline]
    b = [bm.verts.new((x, y1, z)) for x, z in outline]
    k = len(outline)
    for i in range(k):
        bm.faces.new((a[i], a[(i + 1) % k], b[(i + 1) % k], b[i]))
    bm.faces.new(a[::-1])
    bm.faces.new(b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_obj(name, bm, mat, smooth_shade=False)
    if bev:
        m = ob.modifiers.new("bev", "BEVEL")
        m.width, m.segments, m.limit_method, m.angle_limit = bev, 2, "ANGLE", math.radians(40)
        apply_mods(ob)
    return ob


def lathe(name, prof, origin, axis, mat, segs=24):
    """A turned part: prof (radius, height) pairs swept round axis from origin."""
    axis = Vector(axis).normalized()
    u = axis.orthogonal().normalized()
    w = axis.cross(u)
    o = Vector(origin)
    bm = bmesh.new()
    rings = [[bm.verts.new(o + axis * h + (u * math.cos(2 * math.pi * k / segs) + w * math.sin(2 * math.pi * k / segs)) * max(r, 1e-5))
              for k in range(segs)] for r, h in prof]
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(segs):
            bm.faces.new((a[k], a[(k + 1) % segs], b[(k + 1) % segs], b[k]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm, mat)


def hex_head(name, p, axis, af, h, mat, washer=True):
    """A hex bolt head (or nut) of af across flats, h high, on a washer, standing out of p along axis."""
    axis = Vector(axis).normalized()
    p = Vector(p)
    out = []
    if washer:
        out.append(lathe(name + "_wsh", [(0.0, 0.0), (af * 0.95, 0.0), (af * 0.95, 0.0012), (af * 0.9, 0.0016), (0.0, 0.0016)], p, axis, mat, 24))
        p = p + axis * 0.0016
    r = af / math.sqrt(3)
    out.append(cyl(name + "_hex", p, p + axis * h, r, mat, 6))
    out.append(lathe(name + "_chm", [(r * 0.98, 0.0), (af * 0.48, 0.0006), (0.0, 0.0008)], p + axis * h, axis, mat, 24))
    return out


def nylock(name, p, axis, af, mat):
    """A nylon-insert lock nut on a washer, the bolt's thread standing a few millimetres proud."""
    axis = Vector(axis).normalized()
    out = hex_head(name, p, axis, af, af * 0.5, mat)
    top = Vector(p) + axis * (0.0016 + af * 0.5)
    out.append(lathe(name + "_ins", [(af * 0.5, 0.0), (af * 0.46, af * 0.25), (0.0, af * 0.28)], top, axis, mat, 20))
    out.append(cyl(name + "_thd", top, top + axis * af * 0.35, af * 0.3, mat, 12))
    return out


def carriage_head(name, p, axis, d, mat):
    """A carriage bolt's dome (d across), domed out of p along axis."""
    prof = [(d / 2 * math.cos(a), d * 0.28 * math.sin(a)) for a in [math.pi / 2 * i / 6 for i in range(7)]]
    return lathe(name, prof, p, axis, mat, 24)


# ------------------------------------------------------------------ tiller

LAMS = (("TeakVarnish", 0.16), ("AshVarnish", 0.30), ("TeakVarnish", 0.07), ("AshVarnish", 0.30), ("TeakVarnish", 0.17))
CHANNEL = 0.21            # the open channel's length along the top from the root
STRAP_IN = 0.085          # the straps' run from the pivot to the tiller's root


def tiller_path(n=40):
    """Stations from the root to the grip's start, a gentle S: down off the head, then up to the grip."""
    x0, z0 = -3.45, STOCK_Z + 0.008
    x1, z1 = TILLER_END[0] - 0.035, TILLER_END[1] - 0.004
    pts = []
    for i in range(n + 1):
        u = i / n
        # (photo tiller: a pronounced S, high off the head, down 8 cm through the middle, up again to the grip)
        z = z0 + (z1 - z0) * smooth(u) - 0.085 * math.sin(math.pi * min(u / 0.75, 1.0)) ** 1.5 * (1 - 0.6 * u)
        pts.append(Vector((x0 + (x1 - x0) * u, 0.0, z)))
    return pts


def frame(pts, i):
    t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
    side = Vector((0, 1, 0))
    up = side.cross(t).normalized()
    if up.z < 0:
        up = -up
    return t, side, up


def section(u):
    """Width and height of the tiller at fraction u of its length: 46 x 66 mm at the root (photo tiller-2: deeper than
    wide) to 36 x 44 at the grip."""
    return 0.046 + (0.036 - 0.046) * u, 0.074 + (0.044 - 0.074) * smooth(u * 1.3)


def lam_strip(name, pts, s_range, z_frac, y_span, mat):
    """One lamination (z_frac: its bottom and top as fractions of the height) between arc lengths s_range, across y_span
    (fractions of the half width, -1..1)."""
    L = [0.0]
    for a, b in zip(pts, pts[1:]):
        L.append(L[-1] + (b - a).length)
    total = L[-1]
    idx = [i for i in range(len(pts)) if s_range[0] - 1e-6 <= L[i] <= s_range[1] + 1e-6]
    bm = bmesh.new()
    rings = []
    for i in idx:
        t, side, up = frame(pts, i)
        w, h = section(L[i] / total)
        c = pts[i]
        y0, y1 = y_span[0] * w / 2, y_span[1] * w / 2
        z0, z1 = (z_frac[0] - 0.5) * h, (z_frac[1] - 0.5) * h
        rings.append([bm.verts.new(c + side * y + up * z) for y, z in ((y0, z0), (y1, z0), (y1, z1), (y0, z1))])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(4):
            bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_obj(name, bm, mat, smooth_shade=False)
    m = ob.modifiers.new("bev", "BEVEL")
    m.width, m.segments, m.limit_method, m.angle_limit = 0.0012, 2, "ANGLE", math.radians(50)
    apply_mods(ob)
    return ob


def build_tiller(MAT, D):
    pts = tiller_path()
    L = sum((b - a).length for a, b in zip(pts, pts[1:]))
    out = []
    zb = 0.0
    lams = []
    for k, (mname, f) in enumerate(LAMS):
        lams.append((k, mname, zb, zb + f))
        zb += f
    for k, mname, z0, z1 in lams:
        if z1 <= 0.5 + 1e-6:          # under the channel: whole width all along
            out.append(lam_strip(f"Tiller_lam{k}", pts, (0.0, L), (z0, z1), (-1, 1), MAT[mname]))
        else:                          # the channel's floor is at mid-height: two cheeks near the root, whole width beyond
            out.append(lam_strip(f"Tiller_lam{k}_p", pts, (0.0, CHANNEL), (max(z0, 0.5), z1), (0.48, 1), MAT[mname]))
            out.append(lam_strip(f"Tiller_lam{k}_s", pts, (0.0, CHANNEL), (max(z0, 0.5), z1), (-1, -0.48), MAT[mname]))
            out.append(lam_strip(f"Tiller_lam{k}", pts, (CHANNEL, L), (z0, z1), (-1, 1), MAT[mname]))
    # the grip: the laminations' stack rounded off over its last 3.5 cm (a turned, varnished end)
    t, side, up = frame(pts, len(pts) - 1)
    w, h = section(1.0)
    base = pts[-1]
    bm = bmesh.new()
    rings = []
    seg = 24
    for j, f in enumerate((1.0, 0.99, 0.95, 0.86, 0.70, 0.45, 0.12)):
        c = base + t * 0.035 * (1 - f * f) ** 0.5 * 1.0 + t * 0.0 if j == 0 else base + t * 0.035 * math.sqrt(max(1 - f * f, 0.0))
        ring = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            ca, sa = math.cos(a), math.sin(a)
            r = 1.0 / (abs(ca) ** 4 + abs(sa) ** 4) ** 0.25       # a superellipse: the square section with eased corners
            ring.append(bm.verts.new(c + side * (w / 2 * f * ca * r) + up * (h / 2 * f * sa * r)))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(seg):
            bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    out.append(mesh_obj("TillerGrip", bm, MAT["TeakVarnish"]))
    # the mainsheet... no: the tiller's own cam cleat (for the extension's lanyard) on top, two thirds along
    i = int(len(pts) * 0.70)
    tc, sc, uc = frame(pts, i)
    out += D.cam_cleat("TCam", pts[i] + uc * (section(i / (len(pts) - 1))[1] / 2), tuple(uc), tuple(tc), MAT, 0.055)
    # the straps from the pivot into the tiller's root, under three carriage bolts
    t0, s0, u0 = frame(pts, 0)
    piv = pts[0] - t0 * STRAP_IN
    out += straps(MAT, piv, t0, u0, pts)
    # the extension: a universal joint on a plate screwed to the grip end's top, the tube folded aft along the tiller
    out += extension(MAT, pts)
    return out, piv


def straps(MAT, piv, t0, u0, pts):
    out = []
    r_end, half_h, length = 0.021, 0.016, STRAP_IN + 0.17
    for sgn in (1, -1):
        outline = []
        for k in range(13):                       # the round end round the pivot, behind it
            a = math.pi / 2 + math.pi * k / 12
            p = piv + t0 * (r_end * math.cos(a)) + u0 * (r_end * math.sin(a))
            outline.append((p.x, p.z))
        for d, hh in ((0.03, half_h), (length, half_h * 0.9)):
            pass
        q0 = piv + u0 * (-half_h) + t0 * 0.03
        q1 = piv + u0 * (-half_h * 0.9) + t0 * length
        q2 = piv + u0 * (half_h * 0.9) + t0 * length
        q3 = piv + u0 * half_h + t0 * 0.03
        outline += [(q0.x, q0.z), (q1.x, q1.z), (q2.x, q2.z), (q3.x, q3.z)]
        y0, y1 = sgn * 0.0218, sgn * 0.0248
        out.append(plate("RudderHead" if sgn > 0 else "RudderHead_strap", outline, min(y0, y1), max(y0, y1), MAT["Stainless"]))
    # the pivot bolt: hex head and washer to one side, nylock the other
    p = piv
    out.append(cyl("TillerPin", Vector((p.x, -0.031, p.z)), Vector((p.x, 0.031, p.z)), 0.0055, MAT["Stainless"], 16))
    out += hex_head("TillerPinHead", Vector((p.x, 0.0248, p.z)), (0, 1, 0), 0.017, 0.0075, MAT["Stainless"])
    out += nylock("TillerPinNut", Vector((p.x, -0.0248, p.z)), (0, -1, 0), 0.017, MAT["Stainless"])
    # three carriage bolts through the tiller and the straps: domes one side, nylocks the other
    for k, d in enumerate((STRAP_IN + 0.045, STRAP_IN + 0.085, STRAP_IN + 0.125)):
        c = piv + t0 * d
        w = 0.046 / 2
        out.append(carriage_head(f"TillerBolt_{k}", Vector((c.x, w, c.z)), (0, 1, 0), 0.016, MAT["Stainless"]))
        out += nylock(f"TillerBoltNut_{k}", Vector((c.x, -w, c.z)), (0, -1, 0), 0.011, MAT["Stainless"])
    return out


def extension(MAT, pts):
    out = []
    ux, uz = EXT_UJ
    tz = pts[-1].z + section(1.0)[1] / 2
    base = Vector((ux, 0.0, tz))
    out.append(plate("ExtPlate", [(ux - 0.028, tz), (ux + 0.022, tz), (ux + 0.022, tz + 0.004), (ux - 0.028, tz + 0.004)], -0.016, 0.016, MAT["CastAlu"]))
    for dx in (-0.018, 0.012):
        out.append(lathe(f"ExtPlateScrew_{dx:+.3f}", [(0.0, 0.0), (0.0035, 0.0), (0.003, 0.0012), (0.0, 0.0016)], Vector((ux + dx, 0.0, tz + 0.004)), (0, 0, 1), MAT["Stainless"], 16))
    # the rubber universal joint: a ribbed black column from the plate to the tube's ferrule
    prof = [(0.0, 0.0), (0.011, 0.0)]
    h = uz + 0.012 - (tz + 0.004)
    for k in range(5):
        prof += [(0.011, h * (k + 0.2) / 5), (0.0125, h * (k + 0.5) / 5), (0.011, h * (k + 0.8) / 5)]
    prof += [(0.011, h), (0.0, h)]
    out.append(lathe("ExtUJ", prof, Vector((ux, 0.0, tz + 0.004)), (0, 0, 1), MAT["BlackPlastic"], 24))
    # the tube: from the joint's top, bent over aft and lying along the tiller to the tip, a foam grip and a cap at the tip
    top = Vector((ux, 0.0, uz + 0.012))
    tip = Vector((EXT_TIP[0], 0.0, EXT_TIP[1]))
    bend = top + Vector((-0.05, 0, 0.012))
    path = [top, top + Vector((-0.012, 0, 0.008)), bend]
    for i in range(1, 11):
        path.append(bend + (tip - bend) * (i / 10))
    bm = bmesh.new()
    rings = []
    seg = 18
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        u = t.orthogonal().normalized()
        w = t.cross(u)
        rings.append([bm.verts.new(p + 0.0125 * (u * math.cos(2 * math.pi * k / seg) + w * math.sin(2 * math.pi * k / seg))) for k in range(seg)])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(seg):
            bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    out.append(mesh_obj("TillerExt", bm, MAT["ExtensionBlack"]))
    d = (tip - bend).normalized()
    gp = [(0.0, 0.0)] + [(0.0165 if k % 2 == 0 else 0.0152, 0.015 * k) for k in range(15)] + [(0.0, 0.21)]
    out.append(lathe("TillerExtGrip", gp, tip - d * 0.22, d, MAT["BlackPlastic"], 20))
    out.append(lathe("TillerExtCap", [(0.0, 0.0), (0.016, 0.0), (0.016, 0.012), (0.012, 0.018), (0.0, 0.019)], tip - d * 0.01, d, MAT["BlackPlastic"], 20))
    return out


# ------------------------------------------------------------------ pintles and gudgeons

def build_pintles(MAT):
    out = []
    for k, z in enumerate(PINTLE_Z):
        # the strap down both faces of the blade, lying on its section, round-ended aft, round the leading edge to the
        # barrel
        xs = [PIVOT_X - 0.285 * i / 28 for i in range(29)] + [PIVOT_X - 0.285 - 0.015 * math.sin(math.pi / 2 * i / 8) for i in range(1, 9)]
        hz, th = 0.015, 0.003
        for sgn in (1, -1):
            bm = bmesh.new()
            rings = []
            for x in xs:
                yin = max(blade_half(x, z) if x < LE_X else 0.0, 0.0115 * (1 - (PIVOT_X - x) / 0.02) if x > PIVOT_X - 0.02 else 0.0)
                yin = max(yin, blade_half(x, z) if x < LE_X else yin) + 0.0002
                taper = 1.0 if x > PIVOT_X - 0.285 else math.sqrt(max(1 - ((PIVOT_X - 0.285 - x) / 0.015) ** 2, 0.0))   # a round end
                y0, y1 = sgn * yin, sgn * (yin + th)
                rings.append([bm.verts.new((x, y, z + zz * taper)) for y, zz in ((y0, -hz), (y1, -hz), (y1, hz), (y0, hz))])
            for a, b in zip(rings[:-1], rings[1:]):
                for q in range(4):
                    bm.faces.new((a[q], a[(q + 1) % 4], b[(q + 1) % 4], b[q]))
            bm.faces.new(rings[0][::-1])
            bm.faces.new(rings[-1])
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            out.append(mesh_obj(f"PintleStrap_{k}_{sgn}", bm, MAT["Stainless"], smooth_shade=False))   # a flat bar, not a rod
        # the strap's square block round the barrel at the leading edge (photo tiller-transom-attachemnt-2)
        out.append(plate(f"PintleBlock_{k}", [(PIVOT_X + 0.013, z - 0.0145), (LE_X - 0.012, z - 0.0145), (LE_X - 0.012, z + 0.0145), (PIVOT_X + 0.013, z + 0.0145)],
                         -0.0175, 0.0175, MAT["Stainless"], bev=0.0025))
        # the barrel on the axis between the gudgeon's lugs, the pin through all three
        out.append(lathe(f"PintleBarrel_{k}", [(0.0062, -0.014), (0.0115, -0.014), (0.0118, -0.012), (0.0118, 0.012), (0.0115, 0.014), (0.0062, 0.014)],
                         Vector((PIVOT_X, 0, z)), (0, 0, 1), MAT["Stainless"], 28))
        # four through-bolts, staggered, nylocks and washers each side
        for b, (dx, dz) in enumerate(((0.07, 0.006), (0.12, -0.006), (0.18, 0.006), (0.24, -0.006))):
            x = PIVOT_X - dx
            yh = blade_half(x, z) + 0.0032
            out += hex_head(f"PintleBolt_{k}_{b}", Vector((x, yh, z + dz)), (0, 1, 0), 0.011, 0.005, MAT["Stainless"])
            out += nylock(f"PintleNut_{k}_{b}", Vector((x, -yh, z + dz)), (0, -1, 0), 0.011, MAT["Stainless"])
    return out


def build_gudgeons(MAT):
    """On the transom (game part: the hull, they stay put while the rudder turns)."""
    out = []
    for k, z in enumerate(PINTLE_Z):
        out.append(cyl(f"GudgeonPin_{k}", Vector((PIVOT_X, 0, z - 0.046)), Vector((PIVOT_X, 0, z + 0.046)), 0.0058, MAT["Stainless"], 16))
        out.append(lathe(f"GudgeonPinHead_{k}", [(0.0, 0.0), (0.0095, 0.0), (0.0095, 0.003), (0.008, 0.0045), (0.0, 0.0048)],
                         Vector((PIVOT_X, 0, z + 0.046)), (0, 0, 1), MAT["Stainless"], 24))
        # the keeper under the bottom lug: a ring through the pin's cross-hole
        out.append(lathe(f"GudgeonKeeper_{k}", [(0.0045, -0.0012), (0.0075, -0.0012), (0.0075, 0.0012), (0.0045, 0.0012), (0.0045, -0.0012)],
                         Vector((PIVOT_X, 0, z - 0.040)), (0, 0, 1), MAT["Stainless"], 20))
        for lug, dz in ((0, 0.025), (1, -0.025)):
            zc = z + dz
            out.append(lathe(f"Gudgeon_{k}_{lug}_barrel", [(0.0062, -0.009), (0.0125, -0.009), (0.013, -0.007), (0.013, 0.007), (0.0125, 0.009), (0.0062, 0.009)],
                             Vector((PIVOT_X, 0, zc)), (0, 0, 1), MAT["Stainless"], 28))
            for sgn in (1, -1):
                # the strap's legs from the barrel forward to the transom, then folded flat on it, round-ended
                leg = [(PIVOT_X + 0.004, zc - 0.009), (TRANSOM_X - 0.003, zc - 0.009), (TRANSOM_X - 0.003, zc + 0.009), (PIVOT_X + 0.004, zc + 0.009)]
                y0, y1 = sgn * 0.0098, sgn * 0.0128
                out.append(plate(f"Gudgeon_{k}_{lug}_leg{sgn}", leg, min(y0, y1), max(y0, y1), MAT["Stainless"]))
                bm = bmesh.new()
                fl = [(0.0098, -0.009), (0.060, -0.009)] + [(0.060 + 0.009 * math.sin(math.pi * i / 8), -0.009 * math.cos(math.pi * i / 8)) for i in range(1, 8)] + [(0.060, 0.009), (0.0098, 0.009)]
                a = [bm.verts.new((TRANSOM_X - 0.003, sgn * y, zc + zz)) for y, zz in fl]
                b = [bm.verts.new((TRANSOM_X, sgn * y, zc + zz)) for y, zz in fl]
                n = len(fl)
                for i in range(n):
                    bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
                bm.faces.new(a[::-1])
                bm.faces.new(b)
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
                out.append(mesh_obj(f"Gudgeon_{k}_{lug}_flange{sgn}", bm, MAT["Stainless"], smooth_shade=False))
                for j, yb in enumerate((0.030, 0.054)):
                    out += hex_head(f"Gudgeon_{k}_{lug}_bolt{sgn}{j}", Vector((TRANSOM_X - 0.003, sgn * yb, zc)), (-1, 0, 0), 0.011, 0.005, MAT["Stainless"])
    return out


# ------------------------------------------------------------------ sockets

def anchors():
    """The assembly's sockets, unchanged (J22H_sockets.json), as empties the bake reads (anchor_<Name>)."""
    rx = PIVOT_X
    for name, (x, z) in (("TillerEnd", TILLER_END), ("RudderStock", (rx, STOCK_Z)), ("RudderPivot", (rx, 0.0)),
                         ("TillerExtTip", EXT_TIP), ("TillerExtUJ", EXT_UJ)):
        e = bpy.data.objects.new("anchor_" + name, None)
        e.location = (x, 0.0, z)
        link(e)


def build(MAT, D):
    """The rudder group (blade, tiller, straps, extension, pintles) and the gudgeons."""
    blade = build_blade(MAT["CabinGelcoat"])     # clean moulded gelcoat (photo tiller-2): the hull's repairs and chips read huge at this size
    tiller, _ = build_tiller(MAT, D)
    anchors()
    return [blade] + tiller + build_pintles(MAT), build_gudgeons(MAT)
