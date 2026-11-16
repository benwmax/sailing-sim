"""The Catalina 22's mast, boom and standing rigging as meshes (docs/c22-5), from rig_c22. Imported by build_c22.py
(needs Blender's Python). Built in the game's frame (X forward, Y starboard, Z up) and written with Y mirrored to
Blender's port-positive Y, as the hull and deck are (build_deck_c22.Mesh).

Objects:
  C22_Mast         the extrusion with its groove, the masthead's flat-topped cap with its sheaves' slots, the forestay's
                   lug, the backstay's crane and the uppers' strap tangs, the spreaders on their brackets with tip caps, the lowers' tangs, the gooseneck's
                   slide, the vang's tang and the two black bands
  C22_Boom         the boom with its groove, the gooseneck's jaw and pin, the cast end, the black band at E and the
                   mainsheet's and vang's bails. The game swings it about the gooseneck's pin (z up).
  C22_Wires        the forestay, backstay, uppers (bent over the spreaders' tips) and lowers, each from its terminal at
                   the mast to its turnbuckle. Kept apart from the fittings: the game draws live wires between the
                   sockets today, and slice 9 decides which of the two it shows.
  C22_RigFittings  the kit's MastStep on the cabin top with the hinge's cheeks and pivot bolt, its Stemhead on the bow, its Chainplates on the side deck and the
                   transom and its Turnbuckles, and the wires' swaged terminals at the mast

build_all also returns the rig's sockets in the game's sockets file shape (Unreal frame: X forward, Y starboard, Z up,
centimetres), for c22_check.py's I, J, P and E and for slice 9.
"""
import math
import os
import sys

import bmesh
import bpy  # noqa: F401
from mathutils import Matrix, Vector

import build_deck_c22 as BD
import build_keel_c22 as BK
import rig_c22 as RC

KIT_DIR = BK.KIT_DIR
MAST_X, A, B = RC.MAST_X, RC.A, RC.B
WIRE_N = 8                         # sides of a wire
FORE_LUG, CRANE_LUG = 0.004, 0.005  # the masthead's lugs' half thicknesses
TERM_SKIP = 0.03                   # the wires start inside their top terminals' sleeves
MAST_P = 1.0                       # the mast's section: an ellipse (a superellipse's power; under 1 is boxier)
LIGHT_SHARE = 0.25                 # the kit's light copies keep a quarter of the triangles (build_kit.LIGHT_SHARE)


def se(c, p):
    return math.copysign(abs(c) ** p, c)


def orient(prof):
    """+1 if the closed 2D profile runs counter-clockwise, -1 if clockwise."""
    s = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(prof, prof[1:] + prof[:1]))
    return 1 if s > 0 else -1


def loft(m, prof, stations, place, slot, caps=(True, True), flat=False):
    """A solid swept along an axis: prof is a closed 2D outline (u, v); stations are (s, scale) along the axis;
    place(u, v, s) puts a point in the game's frame. Each face turns outward by its outline edge's normal."""
    o = orient(prof)
    rows = [[place(u * k, v * k, s) for u, v in prof] for s, k in stations]
    vs = [[m.v(p) for p in r] for r in rows]
    n = len(prof)
    for i in range(len(rows) - 1):
        s = stations[i][0]
        for j in range(n):
            j1 = (j + 1) % n
            (u0, v0), (u1, v1) = prof[j], prof[j1]
            nu, nv = o * (v1 - v0), -o * (u1 - u0)
            c, d = place(0, 0, s), place(nu, nv, s)
            out = tuple(b - a for a, b in zip(c, d))
            m.face([vs[i][j], vs[i][j1], vs[i + 1][j1], vs[i + 1][j]], slot, out, flat)
    ax = tuple(b - a for a, b in zip(place(0, 0, stations[0][0]), place(0, 0, stations[-1][0])))
    if caps[0]:
        m.polygon(rows[0], slot, tuple(-c for c in ax))
    if caps[1]:
        m.polygon(rows[-1], slot, ax)


def circle(r, n):
    return [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def frame(d):
    """Two unit vectors square to d and to each other."""
    d = Vector(d).normalized()
    ref = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    u = d.cross(ref).normalized()
    return u, d.cross(u).normalized()


def rod(m, a, b, r, slot, n=12, flat=False):
    """A capped cylinder from a to b."""
    a, b = Vector(a), Vector(b)
    u, w = frame(b - a)
    place = lambda pu, pv, s: tuple(a + (b - a) * s + u * pu + w * pv)
    loft(m, circle(r, n), [(0, 1), (1, 1)], place, slot, flat=flat)


def plank(m, c, X, Y, Z, hx, hy, hz, slot):
    """A box centred on c, its half sizes along the unit vectors X, Y, Z."""
    c, X, Y, Z = Vector(c), Vector(X), Vector(Y), Vector(Z)
    pts = [tuple(c + X * (hx if i & 1 else -hx) + Y * (hy if i & 2 else -hy) + Z * (hz if i & 4 else -hz)) for i in range(8)]
    BD.hexa(m, pts, slot)


def kit_frame(m, name, origin, X, Y, Z, light=False, **kw):
    """One of the kit's parts merged into m with its axes on the game-frame unit vectors X, Y, Z (right-handed) at
    origin. light: collapsed to a quarter of its triangles, as the kit's own light copy is (build_kit.light_version).
    Returns its sockets in the game frame."""
    if KIT_DIR not in sys.path:
        sys.path.insert(0, KIT_DIR)
    import bk_parts as KP  # noqa: E402
    import bk_geom as KG  # noqa: E402
    S = lambda v: Vector((v[0], -v[1], v[2]))
    cols = [S(X), -S(Y), S(Z)]
    rot = Matrix([[cols[c][r] for c in range(3)] for r in range(3)]).to_4x4()
    xf = Matrix.Translation(S(origin)) @ rot
    ob = KP.build(name, **kw)
    if light:
        d = ob.modifiers.new("light", "DECIMATE")
        d.decimate_type = "COLLAPSE"
        d.ratio = LIGHT_SHARE
        d.use_collapse_triangulate = True
        KG.apply(ob)
    socks = {}
    for ch in list(ob.children):
        if ch.name.startswith("SOCKET_"):
            p = xf @ (ob.matrix_world @ ch.location)
            socks[ch.name[7:].split(".")[0]] = (p.x, -p.y, p.z)
        bpy.data.objects.remove(ch)
    me = ob.data
    me.transform(ob.matrix_world)
    me.transform(xf)
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    tmp = bmesh.new()                                    # drop the slivers a part's boolean unions leave (the Stemhead's)
    tmp.from_mesh(me)
    bmesh.ops.dissolve_degenerate(tmp, dist=1e-6, edges=tmp.edges[:])
    tmp.to_mesh(me)
    tmp.free()
    first = len(m.bm.faces)
    m.bm.from_mesh(me)
    m.bm.faces.ensure_lookup_table()
    names = [mt.name.split(".")[0] for mt in me.materials]
    for f in m.bm.faces[first:]:
        f.material_index = m.slot(names[f.material_index] if names else "Stainless")
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    return socks


def right_handed(Y, Z):
    """X, Y, Z from a wanted Z and a Y to be squared to it: X = Y x Z."""
    Z = Vector(Z).normalized()
    Y = Vector(Y)
    Y = (Y - Z * Y.dot(Z)).normalized()
    return tuple(Y.cross(Z)), tuple(Y), tuple(Z)


# ------------------------------------------------------------------ the mast

def mast_profile(grow=0.0, n=40):
    """The mast's section (u fore and aft, v across): an oval with the groove's slot up its after face."""
    gw, gd = RC.MS["groove"]
    a, b = A / 2 + grow, B / 2 + grow
    t0 = math.asin(min(1.0, (gw / 2 / b) ** (1 / MAST_P)))
    pts = []
    for k in range(n + 1):
        t = t0 + (2 * math.pi - 2 * t0) * k / n
        pts.append((-a * se(math.cos(t), MAST_P), b * se(math.sin(t), MAST_P)))
    xe = pts[-1][0]
    pts += [(xe + gd, -gw / 2), (xe + gd, gw / 2)]
    return pts


def oval(grow=0.0, n=32):
    a, b = A / 2 + grow, B / 2 + grow
    return [(a * se(math.cos(2 * math.pi * k / n), MAST_P), b * se(math.sin(2 * math.pi * k / n), MAST_P)) for k in range(n)]


def build_mast(mats):
    m = BK.Mesh("C22_Mast")
    on_mast = lambda u, v, z: (MAST_X + u, v, z)
    z0, z1 = RC.heel_z(), RC.top_z()
    cap = RC.MH["height"]
    loft(m, mast_profile(), [(z0, 1), (z1 - cap + 0.01, 1)], on_mast, "Aluminium")
    # the masthead's cap: a flat-topped casting following the section, a little proud of it, its top's edge eased
    grow = 0.004
    stations = [(z1 - cap, 1.0), (z1 - 0.006, 1.0), (z1 - 0.0015, 0.93), (z1, 0.82)]
    loft(m, oval(grow), stations, on_mast, "Aluminium")
    # its two sheaves' slots let into the top (the jib's forward, the main's aft): dark only where the top is cut
    for x in (0.018, -0.018):
        plank(m, (MAST_X + x, 0, z1 - 0.0075), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.016, 0.0045, 0.0078, "BlackPlastic")
    # the forestay's lug cast on the forward face, the backstay's short crane aft, each tapering out to its pin
    h, c = RC.hounds(), RC.crane_pin()
    lug(m, MAST_X + A / 2 - 0.004, h[0] + 0.008, h[2], 0.04, 0.02, FORE_LUG)
    lug(m, MAST_X - A / 2 + 0.004, c[0] - 0.008, c[2], 0.05, 0.02, CRANE_LUG)
    for p in (h, c):
        rod(m, (p[0], -0.0085, p[2]), (p[0], 0.0085, p[2]), 0.003, "Stainless", 10)
    for side in (1, -1):
        # the uppers' strap tangs flat on the mast's sides, through-bolted above their pins
        t = RC.cap_tang(side)
        strap_tang(m, side, MAST_X, t[2], 0.07)
        # the lowers' tang: one strap with two pins under the spreaders
        f, a = RC.lower_tang(side, 1), RC.lower_tang(side, -1)
        strap_tang(m, side, MAST_X, f[2], 0.055, width=RC.SH["lower_tang_spread"] + 0.024, pins=(f[0], a[0]))
    build_spreaders(m)
    # the gooseneck's slide on the after face, its jaw's lugs reaching aft to the pin
    g = RC.gooseneck()
    plank(m, (MAST_X - A / 2 - 0.004, 0, g[2]), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.006, 0.018, 0.06, "Aluminium")
    x_in, x_out = MAST_X - A / 2 + 0.002, g[0] - 0.008          # from inside the slide to 8 mm past the pin
    for dz in (-0.03, 0.03):
        plank(m, ((x_in + x_out) / 2, 0, g[2] + dz), (1, 0, 0), (0, 1, 0), (0, 0, 1), (x_in - x_out) / 2, 0.012, 0.005,
              "Aluminium")
    rod(m, (g[0], 0, g[2] - 0.047), (g[0], 0, g[2] + 0.047), 0.005, "Stainless", 12)
    # the vang's tang: a strap on the after face just above the step's cheeks, its pin across
    v = RC.vang_foot()
    plank(m, (MAST_X - A / 2 - 0.002, 0, v[2] + 0.015), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.003, 0.012, 0.025, "Stainless")
    lug(m, MAST_X - A / 2 - 0.003, v[0] - 0.008, v[2], 0.024, 0.016, 0.003)
    rod(m, (v[0], -0.008, v[2]), (v[0], 0.008, v[2]), 0.0028, "Stainless", 10)
    # the black bands, a hair proud
    for (b0, b1) in RC.mast_bands():
        loft(m, oval(0.0012), [(b0, 1), (b1, 1)], on_mast, "BlackPlastic")
    return m.finish(mats)


def lug(m, x0, x1, z, h0, h1, half_t):
    """A cast lug on the centreline from x0 (in the casting) to x1, tapering from h0 tall to h1, half_t thick."""
    c = []
    for i in range(8):
        x = x1 if i & 1 else x0
        hh = (h1 if i & 1 else h0) / 2
        c.append((x, half_t if i & 2 else -half_t, z + (hh if i & 4 else -hh)))
    BD.hexa(m, c, "Aluminium")


def strap_tang(m, side, x, z_pin, length, width=0.024, pins=None):
    """A stainless strap flat on the mast's side from z_pin - 12 mm up `length`, a bolt head near its top and a pin
    across it (along Y) at each of pins' x (default x)."""
    yt = side * (B / 2 + RC.TANG_T / 2)
    plank(m, (x, yt, z_pin - 0.012 + length / 2), (1, 0, 0), (0, 1, 0), (0, 0, 1), width / 2, RC.TANG_T / 2, length / 2,
          "Stainless")
    yo = side * (B / 2 + RC.TANG_T)
    rod(m, (x, yo - side * 0.001, z_pin + length - 0.03), (x, yo + side * 0.003, z_pin + length - 0.03), 0.006, "Stainless", 10)
    for px in (pins or (x,)):
        rod(m, (px, yt - side * 0.007, z_pin), (px, yt + side * 0.009, z_pin), 0.003, "Stainless", 10)


def build_spreaders(m):
    sp = RC.SP
    t = RC.spreader_tilt()
    for side in (1, -1):
        root = Vector((MAST_X, side * (B / 2 - 0.002), sp["z"]))
        tip = Vector(RC.spreader_tip(side))
        d = (tip - root).normalized()
        up = Vector((0, -side * math.sin(t), math.cos(t)))
        place = lambda u, v, s, root=root, d=d, up=up: tuple(root + d * s + Vector((1, 0, 0)) * u + up * v)
        L = (tip - root).length
        prof = [(sp["chord"] / 2 * math.cos(2 * math.pi * k / 20), sp["thickness"] / 2 * math.sin(2 * math.pi * k / 20))
                for k in range(20)]
        taper = [(0.0, 1.0), (L * 0.5, 1.0), (L - 0.004, 0.8)]
        loft(m, prof, taper, place, "Aluminium")
        # the root's socket hugging the mast: the spreader's section grown a little, tapering off
        loft(m, prof, [(0.0, 1.35), (sp["root"] * 0.6, 1.3), (sp["root"], 1.08)], place, "Aluminium")
        # the tip: a small end fitting with the wire through it, wrapped in tape
        loft(m, circle(0.0105, 14), [(L - 0.035, 1.0), (L + 0.004, 1.0), (L + 0.009, 0.7)], place, "Rubber")


# ------------------------------------------------------------------ the boom

def boom_profile(n=28):
    """The boom's section (u across, v up): a rounded rectangle with the foot's groove along its top."""
    h, w = RC.BM["section"]
    gw, gd = 0.008, 0.008
    pts = []
    t0 = math.asin(min(1.0, (gw / w) ** (1 / 0.6)))
    for k in range(n + 1):
        t = t0 + (2 * math.pi - 2 * t0) * k / n          # t from the top, round through the bottom
        pts.append((w / 2 * se(math.sin(t), 0.6), h / 2 * se(math.cos(t), 0.6)))
    ye = pts[-1][1]
    pts += [(-gw / 2, ye - gd), (gw / 2, ye - gd)]
    return pts


def build_boom(mats):
    m = BK.Mesh("C22_Boom")
    g = RC.gooseneck()
    zc = RC.BM["gooseneck_z"]
    along = lambda u, v, x: (x, u, zc + v)
    x_aft, x_fwd = RC.boom_x()
    end = RC.BM["end"]
    loft(m, boom_profile(), [(g[0] - 0.045, 1), (x_aft + end - 0.01, 1)], along, "Aluminium")
    # the cast end: a little proud of the boom, rounded off aft, the outhaul's sheave box in it
    h, w = RC.BM["section"]
    rr = [(w / 2 * se(math.cos(2 * math.pi * k / 24), 0.6) + 0.003 * math.cos(2 * math.pi * k / 24),
           h / 2 * se(math.sin(2 * math.pi * k / 24), 0.6) + 0.003 * math.sin(2 * math.pi * k / 24)) for k in range(24)]
    st = [(x_aft + end, 1.0), (x_aft + 0.008, 1.0), (x_aft + 0.002, 0.94), (x_aft, 0.85)]
    loft(m, rr, st, lambda u, v, s: (s, u, zc + v), "Aluminium")
    # the outhaul's sheave in its slot through the end, open aft
    plank(m, (x_aft + 0.03, 0, zc + 0.012), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.0315, 0.004, 0.022, "BlackPlastic")
    # the gooseneck's jaw: a cast block in the boom's end, held back clear of the mast's lugs at every angle (their
    # far corners swing 16 mm from the pin, the block's face is 26 mm), and two cheeks above and below the lugs
    # reaching forward round the pin
    plank(m, (g[0] - 0.04, 0, zc), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.014, w / 2 + 0.002, h / 2 + 0.002, "Aluminium")
    for dz in (-0.039, 0.039):
        plank(m, (g[0] - 0.011, 0, zc + dz), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.023, 0.016, 0.004, "Aluminium")
    # the band at E, a hair proud
    b0, b1 = RC.boom_band()
    band = [(u * 1.0 + math.copysign(0.0012, u), v + math.copysign(0.0012, v)) for u, v in boom_profile()[:-2]]
    loft(m, band, [(b0, 1), (b1, 1)], lambda u, v, s: (s, u, zc + v), "BlackPlastic")
    # the bails under the boom: a stainless strap with a loop for the mainsheet's and the vang's blocks
    for x in (RC.BM["mainsheet_x"], RC.BM["vang_x"]):
        plank(m, (x, 0, zc - h / 2 - 0.002), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.03, w / 2 + 0.003, 0.0025, "Stainless")
        pts = [(x, 0.012 * math.cos(math.pi * k / 10), zc - h / 2 - 0.004 - 0.016 * math.sin(math.pi * k / 10)) for k in range(11)]
        for a_, b_ in zip(pts, pts[1:]):
            rod(m, a_, b_, 0.0028, "Stainless", 8)
    return m.finish(mats)


# ------------------------------------------------------------------ the wires and fittings

def build_wires(mats):
    m = BK.Mesh("C22_Wires")
    r = RC.SH["wire_d"] / 2
    for name, (pts, _) in sorted(RC.wires().items()):
        pts = list(pts)
        a, b = Vector(pts[0]), Vector(pts[1])
        pts[0] = tuple(a + (b - a).normalized() * TERM_SKIP)      # the terminal holds the wire's end
        for a, b in zip(pts, pts[1:]):
            rod(m, a, b, r, "Wire", WIRE_N)
    return m.finish(mats)


def build_fittings(mats):
    m = BK.Mesh("C22_RigFittings")
    socks = {}
    # the swaged terminals at the mast: a fork straddling each masthead lug, an eye on the outer face of each strap
    # tang, and the sleeve crimped on the wire below
    for name, (pts, _) in RC.wires().items():
        a, b = Vector(pts[0]), Vector(pts[1])
        d = (b - a).normalized()
        if name in ("Forestay", "Backstay"):
            half = FORE_LUG if name == "Forestay" else CRANE_LUG
            dx = Vector((d.x, 0, d.z)).normalized()
            for sg in (-1, 1):
                plank(m, tuple(a + dx * 0.011 + Vector((0, sg * (half + 0.0025), 0))), tuple(dx), (0, 1, 0),
                      tuple(dx.cross(Vector((0, 1, 0)))), 0.014, 0.0015, 0.0065, "Stainless")
            rod(m, tuple(a + d * 0.022), tuple(a + d * 0.06), 0.0034, "Stainless", 10)
        else:
            side = 1 if a.y > 0 else -1
            loft(m, circle(0.0075, 14), [(a.y - RC.EYE_T / 2, 1), (a.y + RC.EYE_T / 2, 1)],
                 lambda u, v, s_, a=a: (a.x + u, s_, a.z + v), "Stainless")
            rod(m, tuple(a + d * 0.008), tuple(a + d * 0.054), 0.0032, "Stainless", 10)
    m.seal()
    X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
    so, sn = RC.step_frame()
    kit_frame(m, "MastStep", so, *right_handed((0, 1, 0), sn))
    socks["MastStep"] = (MAST_X, 0.0, RC.step_z())
    # her step is a hinge (the mast is lowered aft for the trailer): two cheeks on the shoe either side of the heel and
    # a pivot bolt through them and the mast, aft of its middle, with a head and a nut
    hz = RC.heel_z()
    for side in (1, -1):
        plank(m, (MAST_X - 0.004, side * (B / 2 + 0.0035), hz + 0.034), X, Y, Z, 0.036, 0.003, 0.035, "Aluminium")
        loft(m, circle(0.0085, 6), sorted([(side * (B / 2 + 0.0065), 1), (side * (B / 2 + 0.0115), 0.85)]),
             lambda u, v, s_: (MAST_X - 0.018 + u, s_, hz + 0.045 + v), "Stainless")
    rod(m, (MAST_X - 0.018, -(B / 2 + 0.012), hz + 0.045), (MAST_X - 0.018, B / 2 + 0.012, hz + 0.045), 0.005,
        "Stainless", 12)
    kit_frame(m, "Stemhead", RC.stemhead_base(), X, Y, Z, stem=RC.stem_line())
    for name, (pts, pin) in RC.wires().items():
        athwart = name.startswith(("Upper", "Lower"))
        if name != "Forestay":                                   # the forestay's pin is the stemhead's own
            n = RC.surface_normal(RC.D.deck_z, pin[0], pin[1])
            base = RC.add(pin, n, -RC.CHAIN_PIN)
            kit_frame(m, "Chainplate", base, *right_handed((1, 0, 0) if athwart else (0, 1, 0), n), size="4")
        foot = pts[-1]
        tx, ty, tz = right_handed((1, 0, 0) if athwart else (0, 1, 0), tuple(b - a for a, b in zip(pin, foot)))
        kit_frame(m, "Turnbuckle", pin, tx, ty, tz, light=True, size="4")
    return m.finish(mats), socks


def sockets():
    """The rig's sockets in the game's sockets file shape (centimetres, Y starboard)."""
    cm = lambda p: [round(c * 100, 2) for c in p]
    s, own = {}, {}
    hull, mast, boom = "SM_Catalina22_Hull", "SM_Catalina22_Mast", "SM_Catalina22_Boom"
    w = RC.wires()

    def put(name, p, owner):
        s[name], own[name] = cm(p), owner
    put("MastStep", (MAST_X, 0, RC.step_z()), hull)
    put("MastHeel", (MAST_X, 0, RC.heel_z()), mast)
    put("MastBase", RC.vang_foot(), mast)                              # the vang's foot: its tang on the after face
    put("Hounds", RC.hounds(), mast)
    put("MastheadAft", RC.crane_pin(), mast)
    put("ForestayTack", RC.tack_pin(), hull)
    put("BackstayPlate", w["Backstay"][1], hull)
    put("ForestayFoot", w["Forestay"][0][-1], hull)                     # the stays' wires leave their turnbuckles here
    put("BackstayFoot", w["Backstay"][0][-1], hull)
    for side, tag in ((1, "S"), (-1, "P")):
        put("SpreaderTip_" + tag, RC.spreader_tip(side), mast)
        put("CapTang_" + tag, RC.cap_tang(side), mast)
        put("LowerTangFwd_" + tag, RC.lower_tang(side, 1), mast)
        put("LowerTangAft_" + tag, RC.lower_tang(side, -1), mast)
        # the wires' feet (the turnbuckles' tops), as today's file has them, and the chainplates' pins under new names
        for sock, wire in (("ChainplateUpper_", "Upper_"), ("ChainplateLower_", "LowerAft_"),
                           ("ChainplateLowerFwd_", "LowerFwd_")):
            put(sock + tag, w[wire + tag][0][-1], hull)
            put(sock.replace("Chainplate", "ChainplatePin") + tag, w[wire + tag][1], hull)
    put("LowerTang", (MAST_X, 0, RC.lower_tang(1, -1)[2]), mast)
    zc = RC.BM["gooseneck_z"]
    put("Boom_Clew", (RC.boom_band()[1], 0, RC.boom_top()), boom)
    put("Boom_Vang", (RC.BM["vang_x"], 0, zc - RC.BM["section"][0] / 2), boom)
    put("Boom_Mainsheet", (RC.BM["mainsheet_x"], 0, zc - RC.BM["section"][0] / 2), boom)
    put("BandBoom", (MAST_X, 0, RC.mast_bands()[0][1]), mast)
    put("BandTop", (MAST_X, 0, RC.mast_bands()[1][0]), mast)
    return {"sockets": s, "owner": own,
            "origins": {mast: cm((MAST_X, 0, RC.step_z())), boom: cm(RC.gooseneck())},
            "note": "The rebuild's rig sockets (slice 4), in the game's sockets file shape: Unreal frame (X forward, Y "
                    "starboard, Z up), centimetres, in the boat's frame. Not the game's file: slice 9 writes that. "
                    "BandBoom and BandTop are the mast's black bands' inner edges (P), for c22_check.py. As in today's file, "
                    "Chainplate{Upper,Lower}_* are the wires' feet (the turnbuckles' tops), ForestayTack and BackstayPlate "
                    "the deck pins, LowerTang on the mast's centreline and MastBase the vang's foot on the after face. New: "
                    "ChainplateLowerFwd_* (the game draws one lower a side, the aft one), ChainplatePin*_* (the "
                    "chainplates' pins), CapTang_*, LowerTangFwd_*/LowerTangAft_* (where the model's wires end at the "
                    "mast: the game draws the uppers from SpreaderTip to Hounds), MastHeel, and ForestayFoot/BackstayFoot "
                    "(where the stays leave their turnbuckles: a live wire drawn to the deck pin would run through one)."}


def build_all(mats):
    obs = [build_mast(mats), build_boom(mats), build_wires(mats)]
    fit, _ = build_fittings(mats)
    return obs + [fit], sockets()
