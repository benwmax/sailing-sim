"""The 100 ft maxi (Tools/boats/maxi/ref.json), built by script in Blender as the game's four parts.

    blender -b --factory-startup -P Tools/boats/maxi/build_maxi.py -- <out dir> [--render]

- Hull: the quad loft from maxi_hull.py (the reference stations, interpolated), smoothed by a subdivision surface with
  the chine creased aft and fading out forward; a flat transom; the sheer edge sharp.
- Deck: a separate shell with real thickness, cambered, the cockpit well cut into it (floor, sides, a step down
  forward) and the low coachroof forward of the pit.
- Keel fin (NACA 0012, swept) with its bulb, the bowsprit and the deck gear from the shared kit (layout.json): all in
  SM_Maxi_Hull.
- SM_Maxi_Mast (mast and three swept spreaders, about the mast step), SM_Maxi_Boom (about the gooseneck: x 2.8, the deck
  plus 2.15), SM_Maxi_Rudder (the port blade, canted 8 deg out, and its stock, about RudderPivot: the game mirrors it on
  RudderPivot_1).
- Sockets (empties named SOCKET_<Name> in the .blend) with the J/22 hero's names the pawn reads (docs/prologue/README.md),
  the crew's attach points and a socket per crew station, written to <out>/Maxi_sockets.json in import_boats.py's form
  (sockets in cm, owner, origins); sections.json for the Mac's physics class.
Writes <out>/SM_Maxi_{Hull,Mast,Boom,Rudder}.fbx and maxi.blend; --render adds three views and an eight-view turntable.
Slots are the game's MI_Boat_* names (Tools/boatkit/bk_materials.py). Frames: the body frame (X forward, Y starboard,
Z up, metres, DWL amidships); Blender gets (x, -y, z).
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import maxi_hull as H  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "..", "boatkit"))
import bk_materials as BM  # noqa: E402 (the game's MI_Boat_* table: slot names import straight onto the library)

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else os.path.join(HERE, "out")
RENDER = "--render" in ARGS
os.makedirs(OUT, exist_ok=True)
REF = H.REF


def B(p):
    """Body frame to Blender."""
    return Vector((p[0], -p[1], p[2]))


MATS = {}


def make_materials():
    """The slots, named as the game's MI_Boat_* library (scripts/make_materials.py BOAT_LIBRARY): the livery colours
    Topsides, Deck, NonSkid and Antifouling and wears them (M_BoatSurface's Wear); the mast's CarbonMast is on M_BoatMast
    so it bends with the rig."""
    for slot in ("Topsides", "Antifouling", "Deck", "NonSkid", "Carbon", "CarbonMatte", "CarbonMast", "Keel"):
        MATS[slot] = BM.get(slot)

def mesh_object(name, bm, mats):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for m in mats:
        me.materials.append(MATS[m])
    for p in me.polygons:
        p.use_smooth = True
    return ob


def apply_mods(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    for m in list(ob.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


# ---------------------------------------------------------------------------------------------------------------- hull

def build_hull():
    rows = H.hull_grid(48)
    bm = bmesh.new()
    crease = bm.edges.layers.float.get("crease_edge") or bm.edges.layers.float.new("crease_edge")
    grid = []   # [station][k] with k running port sheer .. keel .. starboard sheer
    for x, sec, cr in rows:
        half = [(y, z) for y, z in sec]
        ring = [(-y, z) for y, z in reversed(half)] + [(y, z) for y, z in half[1:]]
        grid.append([bm.verts.new(B((x, y, z))) for y, z in ring])
    n = len(grid[0])
    keel_k = H.ROWS - 1
    for i in range(len(grid) - 1):
        for k in range(n - 1):
            f = bm.faces.new((grid[i][k], grid[i][k + 1], grid[i + 1][k + 1], grid[i + 1][k]))
            zc = (grid[i][k].co.z + grid[i][k + 1].co.z) / 2
            f.material_index = 1 if zc < 0.05 else 0
    # The chine rows (both sides): creased aft, fading forward.
    chine_rows = (keel_k - (H.BOTTOM_PTS - 1), keel_k + (H.BOTTOM_PTS - 1))
    bm.edges.ensure_lookup_table()
    for i in range(len(grid) - 1):
        cr = rows[i][2]
        for k in chine_rows:
            e = bm.edges.get((grid[i][k], grid[i + 1][k]))
            if e:
                e[crease] = cr
    # The sheer and the transom's edges stay sharp-ish (the subdivision would round them away).
    for i in range(len(grid) - 1):
        for k in (0, n - 1):
            e = bm.edges.get((grid[i][k], grid[i + 1][k]))
            if e:
                e[crease] = 1.0
    # Transom: flat, closed by quad strips across (port k to starboard n-1-k), so the subdivision keeps it flat; its rim
    # creased.
    t0 = grid[0]
    for k in range(keel_k):
        q = (t0[k], t0[n - 1 - k], t0[n - 2 - k], t0[k + 1]) if k + 1 != n - 2 - k else None
        if q and len(set(q)) == 4:
            f = bm.faces.new(q)
            f.material_index = 0
    bm.faces.new((t0[keel_k - 1], t0[keel_k + 1], t0[keel_k]))   # the last strip, closed at the keel
    for a, b in zip(grid[0], grid[0][1:]):
        e = bm.edges.get((a, b))
        if e:
            e[crease] = 1.0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = mesh_object("Maxi_Hull", bm, ["Topsides", "Antifouling"])
    sub = ob.modifiers.new("sub", "SUBSURF")
    sub.levels = sub.render_levels = 2
    apply_mods(ob)
    return ob


# ---------------------------------------------------------------------------------------------------------------- deck

def deck_z(x, y):
    """The deck surface: the sheer at the edge, crowned toward the centreline (the camber)."""
    st = H.station_at(x)
    hd = max(st["half_deck"], 0.05)
    t = min(abs(y) / hd, 1.0)
    return st["sheer"] + REF["deck_camber"] * (1 - t * t)


def in_cockpit(x, y):
    c = REF["deck"]["cockpit"]
    return c["x_aft"] <= x <= c["x_fwd"] and abs(y) <= c["width"] / 2


def build_deck():
    """The deck shell (3 cm laminate, Solidify), with the cockpit well's opening left out; the well and the coachroof are
    their own shells."""
    xs, xb = REF["stern_x"] + 0.02, REF["bow_x"] - 0.05
    nx, ny = 96, 24
    bm = bmesh.new()
    verts = []
    for i in range(nx + 1):
        x = xs + (xb - xs) * i / nx
        hd = H.station_at(x)["half_deck"] - 0.015
        row = []
        for j in range(ny + 1):
            y = -hd + 2 * hd * j / ny
            row.append(bm.verts.new(B((x, y, deck_z(x, y)))))
        verts.append(row)
    for i in range(nx):
        for j in range(ny):
            cx = xs + (xb - xs) * (i + 0.5) / nx
            hd = H.station_at(cx)["half_deck"]
            cy = -hd + 2 * hd * (j + 0.5) / ny
            if in_cockpit(cx, cy):
                continue
            f = bm.faces.new((verts[i][j], verts[i + 1][j], verts[i + 1][j + 1], verts[i][j + 1]))
            f.material_index = 1 if abs(cy) < hd - 0.35 else 0
    ob = mesh_object("Maxi_Deck", bm, ["Deck", "NonSkid"])
    sol = ob.modifiers.new("solid", "SOLIDIFY")
    sol.thickness = 0.03
    sol.offset = -1.0
    apply_mods(ob)
    return ob


def build_cockpit():
    """The racing pit: a well 55 cm deep under the deck, its sides and floor (non-skid), a step at the forward end."""
    c = REF["deck"]["cockpit"]
    x0, x1, w, d = c["x_aft"], c["x_fwd"], c["width"] / 2, c["depth"]
    bm = bmesh.new()
    nx = 24
    floor = []
    tops = []
    for i in range(nx + 1):
        x = x0 + (x1 - x0) * i / nx
        zt = deck_z(x, w)
        zf = zt - d
        floor.append((bm.verts.new(B((x, -w + 0.06, zf))), bm.verts.new(B((x, w - 0.06, zf)))))
        tops.append((bm.verts.new(B((x, -w, deck_z(x, -w)))), bm.verts.new(B((x, w, zt)))))
    for i in range(nx):
        bm.faces.new((floor[i][0], floor[i + 1][0], floor[i + 1][1], floor[i][1])).material_index = 1
        for s in (0, 1):
            q = (tops[i][s], tops[i + 1][s], floor[i + 1][s], floor[i][s])
            bm.faces.new(q if s == 0 else tuple(reversed(q))).material_index = 0
    # The forward end wall and the open transom end (the pit drains aft through the transom).
    bm.faces.new((tops[-1][0], floor[-1][0], floor[-1][1], tops[-1][1])).material_index = 0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = mesh_object("Maxi_Cockpit", bm, ["Deck", "NonSkid"])
    sol = ob.modifiers.new("solid", "SOLIDIFY")
    sol.thickness = 0.025
    bev = ob.modifiers.new("bevel", "BEVEL")
    bev.width = 0.012
    bev.segments = 2
    bev.limit_method = "ANGLE"
    apply_mods(ob)
    return ob


def build_coachroof():
    """A low coachroof forward of the pit: sloped sides and front, rounded edges, a raised flat top."""
    c = REF["deck"]["coachroof"]
    x0, x1, w, h = c["x_aft"], c["x_fwd"], c["width"] / 2, c["height"]
    bm = bmesh.new()
    nx = 16
    base, top = [], []
    for i in range(nx + 1):
        x = x0 + (x1 - x0) * i / nx
        t = (x - x0) / (x1 - x0)
        ww = w * (1 - 0.35 * t ** 2.2)          # narrowing forward
        hh = h * (1 - 0.55 * t ** 3)            # sweeping down to the deck at the front
        zb = deck_z(x, ww)
        base.append((bm.verts.new(B((x, -ww, deck_z(x, -ww) - 0.02))), bm.verts.new(B((x, ww, zb - 0.02)))))
        top.append((bm.verts.new(B((x, -ww + 0.28, zb + hh))), bm.verts.new(B((x, ww - 0.28, zb + hh)))))
    for i in range(nx):
        for s in (0, 1):
            q = (base[i][s], base[i + 1][s], top[i + 1][s], top[i][s])
            bm.faces.new(q if s == 1 else tuple(reversed(q))).material_index = 0
        bm.faces.new((top[i][0], top[i + 1][0], top[i + 1][1], top[i][1])).material_index = 1
    bm.faces.new((base[-1][0], base[-1][1], top[-1][1], top[-1][0])).material_index = 0
    bm.faces.new((base[0][1], base[0][0], top[0][0], top[0][1])).material_index = 0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = mesh_object("Maxi_Coachroof", bm, ["Deck", "NonSkid"])
    bev = ob.modifiers.new("bevel", "BEVEL")
    bev.width = 0.06
    bev.segments = 4
    bev.limit_method = "ANGLE"
    apply_mods(ob)
    return ob


# ---------------------------------------------------------------------------------------------------------- appendages

def loft_foil(name, sections, mat):
    """sections: [(origin body xyz, chord, thickness, span direction body xyz)] root to tip; the chord runs aft (-X)."""
    bm = bmesh.new()
    rings = []
    for (o, chord, th) in sections:
        half = H.foil_section(chord, th)
        ring = [(o[0] - x, o[1] + y, o[2]) for x, y in half] + [(o[0] - x, o[1] - y, o[2]) for x, y in reversed(half[1:-1])]
        rings.append([bm.verts.new(B(p)) for p in ring])
    n = len(rings[0])
    for a, b in zip(rings, rings[1:]):
        for k in range(n):
            bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return mesh_object(name, bm, [mat])


def build_keel():
    k = REF["keel"]
    root_z = -0.88
    sections = []
    for i in range(9):
        t = i / 8
        z = root_z + (-(k["draft"] - k["bulb_diameter"] * 0.5) - root_z) * t
        chord = k["root_chord"] + (k["tip_chord"] - k["root_chord"]) * t
        le = k["x_root_le"] - math.tan(math.radians(k["sweep_deg"])) * (root_z - z) * -1
        sections.append(((le, 0.0, z), chord, k["thickness"]))
    fin = loft_foil("Maxi_KeelFin", sections, "Keel")
    # The bulb: a body of revolution (an ogive nose, a long taper aft) at the fin's tip.
    bm = bmesh.new()
    L, D = k["bulb_length"], k["bulb_diameter"]
    xn = k["bulb_x_nose"]
    zc = -k["draft"] + 0.85 * D / 2          # its bottom (the flattened section's 0.85) on the draft
    rings = []
    nl, nr = 28, 16
    for i in range(1, nl):
        t = i / nl
        r = D / 2 * (math.sin(math.pi * min(t / 0.35, 1.0) / 2) ** 0.6 if t < 0.35 else (1 - ((t - 0.35) / 0.65) ** 1.8) ** 0.8)
        x = xn - L * t
        rings.append([bm.verts.new(B((x, r * math.cos(2 * math.pi * j / nr), zc + 0.85 * r * math.sin(2 * math.pi * j / nr)))) for j in range(nr)])
    nose, tail = bm.verts.new(B((xn, 0, zc))), bm.verts.new(B((xn - L, 0, zc)))
    for j in range(nr):
        j2 = (j + 1) % nr
        bm.faces.new((nose, rings[0][j], rings[0][j2]))
        bm.faces.new((tail, rings[-1][j2], rings[-1][j]))
        for a, b in zip(rings, rings[1:]):
            bm.faces.new((a[j], b[j], b[j2], a[j2]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bulb = mesh_object("Maxi_KeelBulb", bm, ["Keel"])
    return fin, bulb


def build_rudder():
    """The port blade (RudderPivot), canted 8 deg outboard; the pawn draws it mirrored on the starboard stock
    (RudderPivot_1)."""
    r = REF["rudders"]
    cant = -math.radians(r["cant_deg"])
    st = H.station_at(r["x_stock"])
    ztop = min(-0.05, st["z_keel"] * 0.4) - 0.02          # the top at the hull bottom near the transom
    sections = []
    for i in range(6):
        t = i / 5
        span = r["span"] * t
        chord = r["root_chord"] + (r["tip_chord"] - r["root_chord"]) * t
        sections.append(((r["x_stock"] + 0.25 * chord, -r["y"] + math.sin(cant) * span, ztop - math.cos(cant) * span), chord, r["thickness"]))
    blade = loft_foil("Maxi_Rudder", sections, "Keel")
    # The stock: from the blade's root up through the hull to the cockpit floor.
    zf = deck_z(r["x_stock"], 0.0) - REF["deck"]["cockpit"]["depth"]
    stock = tube_along("Maxi_RudderStock", [(r["x_stock"], -r["y"], ztop + 0.05), (r["x_stock"], -r["y"], zf)], [0.075, 0.075], [0.075, 0.075], "Carbon", 16)
    return [blade, stock]

# ---------------------------------------------------------------------------------------------------------------- spars

def tube_along(name, pts, half_w, half_d, mat, sides=16):
    """An elliptic tube through body points (half width across Y, half depth along X), each point its own size."""
    bm = bmesh.new()
    rings = []
    for (p, w, d) in zip(pts, half_w, half_d):
        rings.append([bm.verts.new(B((p[0] + d * math.cos(2 * math.pi * j / sides), p[1] + w * math.sin(2 * math.pi * j / sides), p[2]))) for j in range(sides)])
    for a, b in zip(rings, rings[1:]):
        for j in range(sides):
            bm.faces.new((a[j], a[(j + 1) % sides], b[(j + 1) % sides], b[j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return mesh_object(name, bm, [mat])


def beam_along_x(name, x0, x1, z, half_w, half_d, mat, n=12, sides=16):
    """A deep, rounded-box spar along X (the boom): a superellipse section, depth on Z, tapering a little aft."""
    bm = bmesh.new()
    rings = []
    for i in range(n + 1):
        t = i / n
        x = x0 + (x1 - x0) * t
        k = 1.0 - 0.35 * max(0.0, (t - 0.6) / 0.4)
        ring = []
        for j in range(sides):
            a = 2 * math.pi * j / sides
            c, s = math.cos(a), math.sin(a)
            # Superellipse (exponent 4): nearly flat sides, rounded corners.
            y = half_w * k * math.copysign(abs(c) ** 0.5, c)
            zz = half_d * k * math.copysign(abs(s) ** 0.5, s)
            ring.append(bm.verts.new(B((x, y, z - half_d + zz))))
        rings.append(ring)
    for a, b2 in zip(rings, rings[1:]):
        for j in range(sides):
            bm.faces.new((a[j], a[(j + 1) % sides], b2[(j + 1) % sides], b2[j]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return mesh_object(name, bm, [mat])


def build_spars():
    rg = REF["rig"]
    mx = rg["mast_x"]
    z0 = deck_z(mx, 0.0)
    n = 24
    pts, hw, hd = [], [], []
    for i in range(n + 1):
        t = i / n
        z = z0 + rg["mast_above_deck"] * t
        taper = 1.0 if t < 0.55 else 1 - (1 - rg["mast_tip_chord"] / rg["mast_chord"]) * ((t - 0.55) / 0.45) ** 1.3
        pts.append((mx, 0.0, z))
        hd.append(rg["mast_chord"] / 2 * taper)
        hw.append(rg["mast_width"] / 2 * (0.55 + 0.45 * taper))
    mast = tube_along("Maxi_Mast", pts, hw, hd, "CarbonMast")
    spreaders = []
    for k, sp in enumerate(rg["spreaders"]):
        z = z0 + sp["z"]
        sw = math.radians(sp["sweep_deg"])
        for s in (1, -1):
            tip = (mx - math.sin(sw) * sp["span"], s * math.cos(sw) * sp["span"], z + 0.15)
            spreaders.append(tube_along(f"Maxi_Spreader{k}_{'S' if s > 0 else 'P'}", [(mx, s * 0.12, z), tip], [0.035, 0.02], [0.09, 0.05], "CarbonMast", 10))
    b = rg["boom"]
    bz = z0 + b["gooseneck_z"]
    boom = beam_along_x("Maxi_Boom", mx - 0.3, mx - 0.3 - b["length"], bz, b["width"] / 2, b["depth"] / 2, "Carbon")
    bs = rg["bowsprit"]
    sprit = tube_along("Maxi_Bowsprit", [(REF["bow_x"] - 0.6, 0.0, bs["z"]), (REF["bow_x"] + bs["length"], 0.0, bs["z"] + 0.05)], [0.09, 0.06], [0.09, 0.06], "Carbon", 12)
    return mast, spreaders, boom, sprit


# ------------------------------------------------------------------------------------------------------------ deck gear

def place_kit():
    """The shared kit's deck gear (Tools/boatkit) where layout.json puts it: on the deck surface or the cockpit floor.
    Returns the placed objects and each one's top (by part, x, y: the sockets read the winches' tops)."""
    import bk_parts as P   # noqa: E402 (needs bpy, so imported here)
    lay = json.load(open(os.path.join(HERE, "layout.json")))
    pit_d = REF["deck"]["cockpit"]["depth"]
    placed, tops = [], {}
    for e in lay["parts"]:
        for s in ((1, -1) if e.get("mirror") else (1,)):
            ob = P.build(e["part"], **e.get("kw", {}))
            x, y = e["x"], e["y"] * s
            z = deck_z(x, y) - (pit_d if e["on"] == "pit" else 0.0)
            yaw = math.radians(e.get("yaw", 0.0)) * (s if e.get("mirror") else 1)
            ob.matrix_world = Matrix.Translation(B((x, y, z))) @ Matrix.Rotation(-yaw, 4, "Z")
            ob.name = f"Maxi_{e['part']}_{len(placed)}"
            bpy.context.view_layer.update()
            tops[(e["part"], x, y)] = max((ob.matrix_world @ Vector(c)).z for c in ob.bound_box)
            placed.append(ob)
    return placed, tops

# --------------------------------------------------------------------------------------------------------------- sockets

def socket(out, owner, name, p):
    """A rig or crew point (body frame, metres) on one part: an empty SOCKET_<Name> in the .blend, a row in the JSON."""
    e = bpy.data.objects.new("SOCKET_" + name, None)
    e.location = B(p)
    e.empty_display_size = 0.15
    bpy.context.scene.collection.objects.link(e)
    out[name] = (owner, p)


def roof_top(x):
    """The coachroof's top surface height at x (centreline), from build_coachroof's sweep."""
    c = REF["deck"]["coachroof"]
    t = min(max((x - c["x_aft"]) / (c["x_fwd"] - c["x_aft"]), 0.0), 1.0)
    return deck_z(x, 0.0) + c["height"] * (1 - 0.55 * t ** 3)


def sockets(kit_tops):
    """The points the pawn reads (BoatModelVisuals.cpp: the J/22 hero's names, docs/prologue/README.md), the crew's
    attach points and the stations. kit_tops: the top of each placed kit part, by (part, x, y)."""
    rg, d, ru = REF["rig"], REF["deck"], REF["rudders"]
    mx = rg["mast_x"]
    z0 = deck_z(mx, 0.0)
    pit = d["cockpit"]["depth"]
    bz = z0 + rg["boom"]["gooseneck_z"]
    S = {}
    hull, mast, boom, rud = "SM_Maxi_Hull", "SM_Maxi_Mast", "SM_Maxi_Boom", "SM_Maxi_Rudder"
    floor = lambda x: deck_z(x, 0.0) - pit                                   # noqa: E731 (the cockpit floor)
    socket(S, hull, "MastStep", (mx, 0.0, z0))
    socket(S, hull, "ForestayTack", (rg["forestay_x"], 0.0, rg["forestay_z"]))
    socket(S, hull, "BackstayPlate", (REF["stern_x"] + 0.18, 0.0, H.sheer_z(REF["stern_x"]) + 0.05))
    socket(S, hull, "LazySheetVia", (mx - 0.8, 0.0, roof_top(mx - 0.8) + 0.04))
    socket(S, hull, "CockpitSole", (-9.0, 0.0, floor(-9.0)))
    trav = d["traveller"]
    tz = floor(trav["x"]) + 0.12
    socket(S, hull, "Traveler_C", (trav["x"], 0.0, tz))
    # The two stocks: RudderPivot to port, RudderPivot_1 to starboard (the blade mesh is the port one, mirrored there).
    socket(S, hull, "RudderPivot", (ru["x_stock"], -ru["y"], 0.0))
    socket(S, hull, "RudderPivot_1", (ru["x_stock"], ru["y"], 0.0))
    winch = kit_tops[("Winch70", -7.0, 2.55)]
    for s, nm in ((1, "S"), (-1, "P")):
        y_edge = H.station_at(mx)["half_deck"] - 0.12
        socket(S, hull, f"ChainplateUpper_{nm}", (mx - 0.9, s * (H.station_at(mx - 0.9)["half_deck"] - 0.12), H.sheer_z(mx - 0.9) + 0.03))
        socket(S, hull, f"ChainplateLower_{nm}", (mx - 0.5, s * y_edge, H.sheer_z(mx - 0.5) + 0.03))
        gt = d["genoa_tracks"]
        socket(S, hull, f"JibLead_{nm}", (-3.2, s * gt["y"], deck_z(-3.2, gt["y"]) + 0.07))
        socket(S, hull, f"JibWinch_{nm}", (-7.0, s * 2.55, winch - 0.05))
        socket(S, hull, f"JibTailer_{nm}", (-7.0, s * 2.55, winch + 0.01))
        socket(S, hull, f"JibTailRest_{nm}", (-6.3, s * 2.15, deck_z(-6.3, 2.15) + 0.01))
        socket(S, hull, f"Traveler_{nm}", (trav["x"], s * (trav["width"] / 2 - 0.15), tz))
        # The crew's attach points (CrewMotion: the J/22 hero's names): the rail, the pit edge, the coachroof.
        cw = d["cockpit"]["width"] / 2
        socket(S, hull, f"Seat_{nm}", (-7.6, s * (cw + 0.25), deck_z(-7.6, cw + 0.25)))
        socket(S, hull, f"FootBrace_{nm}", (-7.6, s * (cw - 0.15), floor(-7.6) + 0.12))
        socket(S, hull, f"SideDeck_{nm}", (-7.6, s * (H.station_at(-7.6)["half_deck"] - 0.1), H.sheer_z(-7.6)))
        socket(S, hull, f"HandholdCoaming_{nm}", (-7.6, s * cw, deck_z(-7.6, cw) + 0.04))
        socket(S, hull, f"HandholdCabin_{nm}", (-2.5, s * 1.55, roof_top(-2.5) - 0.06))
        # The stations (crew sockets per station): where each stands or sits, and where the hands go.
        w = d["wheels"]
        hub = floor(w["x"]) + 1.05
        socket(S, hull, f"Wheel_{nm}", (w["x"], s * w["y"], hub))
        socket(S, hull, f"Helm_{nm}", (w["x"] - 0.75, s * (w["y"] + 0.55), floor(w["x"]) + 0.15))
        socket(S, hull, f"Trimmer_Jib_{nm}", (-7.6, s * 2.95, deck_z(-7.6, 2.95)))
        socket(S, hull, f"Trimmer_Jib_Hands_{nm}", (-7.0, s * 2.55, winch + 0.1))
    for k, p in enumerate(d["pedestals"]):
        x = p["x"]
        socket(S, hull, f"Grinder_{k + 1}", (x - 0.55, 0.0, floor(x)))
        socket(S, hull, f"Grinder_Hands_{k + 1}", (x, 0.0, floor(x) + 0.85))
    socket(S, hull, "Trimmer_Main", (trav["x"] + 0.7, 0.0, floor(trav["x"])))
    socket(S, hull, "Trimmer_Main_Hands", (-10.6, 0.0, floor(-10.6) + 0.3))
    socket(S, hull, "Pit", (-4.9, 0.0, floor(-4.9)))
    socket(S, hull, "Mast", (mx - 0.8, 0.0, roof_top(mx - 0.8)))
    socket(S, hull, "Bow", (11.5, 0.0, deck_z(11.5, 0.0)))
    socket(S, hull, "Navigator", (-1.0, 0.0, deck_z(-1.0, 0.0) - 1.8))
    # The mast: its base (the vang's foot), the lowest spreader's tang and tips, the hounds and the head.
    sp = rg["spreaders"][0]
    sw = math.radians(sp["sweep_deg"])
    socket(S, mast, "MastBase", (mx - 0.32, 0.0, roof_top(mx - 0.32) + 0.25))
    socket(S, mast, "LowerTang", (mx, 0.0, z0 + sp["z"]))
    for s, nm in ((1, "S"), (-1, "P")):
        socket(S, mast, f"SpreaderTip_{nm}", (mx - math.sin(sw) * sp["span"], s * math.cos(sw) * sp["span"], z0 + sp["z"] + 0.15))
    socket(S, mast, "Hounds", (mx + 0.05, 0.0, z0 + rg["hounds_z"]))
    socket(S, mast, "MastheadAft", (mx - 0.15, 0.0, z0 + rg["mast_above_deck"] - 0.1))
    # The boom (built about the physics gooseneck: x MainLuffX 2.8, z the deck plus gooseneck_z).
    b = rg["boom"]
    x0 = mx - 0.3
    socket(S, boom, "Boom_Vang", (x0 - 2.0, 0.0, bz - b["depth"]))
    socket(S, boom, "Boom_Mainsheet", (x0 - b["length"] + 0.35, 0.0, bz - b["depth"] * 0.8))
    socket(S, boom, "Boom_Clew", (x0 - b["length"] + 0.1, 0.0, bz + 0.05))
    # The port rudder: its stock's top at the cockpit floor, and TillerEnd, a point on the port wheel's rim the helm's hand
    # holds (on the stock's own axis, so it stays put as the blade turns; the wheel's plane is 10 cm aft of it).
    w = d["wheels"]
    hub = floor(w["x"]) + 1.05
    dy = abs(w["y"] - ru["y"])
    rim = hub + math.sqrt(max((w["diameter"] / 2) ** 2 - dy * dy, 0.0))
    socket(S, rud, "RudderStock", (ru["x_stock"], -ru["y"], floor(ru["x_stock"])))
    socket(S, rud, "TillerEnd", (ru["x_stock"], -ru["y"], rim - 0.05))
    return S


# -------------------------------------------------------------------------------------------------------------- measure

def measure_canoe(ob):
    """The canoe body as FleetMesh measures it: the Topsides and Antifouling faces' extent, the volume below the DWL and its
    centroid (body frame)."""
    me = ob.data
    lo, hi = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
    vol, mom = 0.0, Vector((0, 0, 0))
    canoe = {i for i, m in enumerate(me.materials) if m and m.name in ("Topsides", "Antifouling")}
    for p in me.polygons:
        if p.material_index not in canoe:
            continue
        pts = [ob.matrix_world @ me.vertices[v].co for v in p.vertices]
        pts = [Vector((q.x, -q.y, q.z)) for q in pts]
        for q in pts:
            lo = Vector(map(min, lo, q))
            hi = Vector(map(max, hi, q))
        for k in range(1, len(pts) - 1):
            tri = (pts[0], pts[k], pts[k + 1])
            poly = []
            for j in range(3):
                a, c = tri[j], tri[(j + 1) % 3]
                if a.z <= 0:
                    poly.append(a)
                if (a.z <= 0) != (c.z <= 0):
                    poly.append(a + (c - a) * (-a.z / (c.z - a.z)))
            for j in range(1, len(poly) - 1):
                v = poly[0].dot(poly[j].cross(poly[j + 1])) / 6.0
                vol += v
                mom += v * (poly[0] + poly[j] + poly[j + 1]) / 4.0
    cb = mom / vol if abs(vol) > 1e-9 else Vector((0, 0, 0))
    return hi - lo, abs(vol), cb


def inflate(ob, target):
    """The subdivision surface rounds the loft inward a few millimetres (2% of the canoe body's volume): push the hull out
    along its normals until the volume below the waterline is the sections' again (FleetMesh holds it to 2%)."""
    for _ in range(3):
        size, vol, cb = measure_canoe(ob)
        me = ob.data
        wet = sum(p.area for p in me.polygons if p.center.z < 0.0)
        d = (target - vol) / max(wet, 1.0)
        if abs(d) < 1e-4:
            break
        for v in me.vertices:
            v.co += v.normal * d
    return ob


# --------------------------------------------------------------------------------------------------------------- export

def as_mesh(ob):
    """A plain mesh object with its modifiers applied (kit parts arrive finished; this is for safety)."""
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    if ob.modifiers:
        bpy.ops.object.convert(target="MESH")
    return ob


def join_part(name, obs, pivot):
    """One game part: the objects joined (custom normals kept by the operator), the origin moved to the pivot (body frame)."""
    obs = [as_mesh(o) for o in obs if o and o.type == "MESH"]
    for o in obs:
        o.parent = None
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    if len(obs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = ob.data.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    pv = B(pivot)
    ob.data.transform(Matrix.Translation(-pv))
    ob.location = pv
    return ob


def export_part(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    loc = ob.location.copy()
    ob.location = (0, 0, 0)
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, ob.name + ".fbx"), use_selection=True, axis_forward="X",
                             axis_up="Z", apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             mesh_smooth_type="FACE", use_mesh_modifiers=True, add_leaf_bones=False, bake_space_transform=True)
    ob.location = loc


# ---------------------------------------------------------------------------------------------------------------- render

def render(path, loc, look, lens=35):
    sc = bpy.context.scene
    cam = bpy.data.objects.get("PreviewCam") or bpy.data.objects.new("PreviewCam", bpy.data.cameras.new("PreviewCam"))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    cam.location = B(loc)
    cam.rotation_euler = (B(look) - B(loc)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    cam.data.clip_end = 500
    sc.camera = cam
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def render_setup():
    sc = bpy.context.scene
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.65, 0.8, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 1.2
    sc.world = world
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 4.0
    sun.rotation_euler = (math.radians(50), 0, math.radians(35))
    sc.collection.objects.link(sun)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    make_materials()
    hull = build_hull()
    cvol, cbx, cbz = H.canoe_volume()
    inflate(hull, cvol)
    size, vol, cb = measure_canoe(hull)
    deck = build_deck()
    pit = build_cockpit()
    roof = build_coachroof()
    fin, bulb = build_keel()
    rudder = build_rudder()
    mast, spreaders, boom, sprit = build_spars()
    kit, kit_tops = place_kit()
    socks = sockets(kit_tops)
    H.export_sections(os.path.join(OUT, "sections.json"))
    rg = REF["rig"]
    mx = rg["mast_x"]
    z0 = deck_z(mx, 0.0)
    pivots = {"SM_Maxi_Hull": (0.0, 0.0, 0.0), "SM_Maxi_Mast": (mx, 0.0, z0),
              "SM_Maxi_Boom": (mx - 0.3, 0.0, z0 + rg["boom"]["gooseneck_z"]),
              "SM_Maxi_Rudder": (REF["rudders"]["x_stock"], -REF["rudders"]["y"], 0.0)}
    parts = {"SM_Maxi_Hull": [hull, deck, pit, roof, fin, bulb, sprit] + kit, "SM_Maxi_Mast": [mast] + spreaders,
             "SM_Maxi_Boom": [boom], "SM_Maxi_Rudder": rudder}
    obs = {name: join_part(name, o, pivots[name]) for name, o in parts.items()}
    tris = {name: sum(len(p.vertices) - 2 for p in ob.data.polygons) for name, ob in obs.items()}
    draft = -min((obs["SM_Maxi_Hull"].matrix_world @ v.co).z for v in obs["SM_Maxi_Hull"].data.vertices)
    meta = {"sockets": {n: [round(v * 100.0, 2) for v in p] for n, (o, p) in socks.items()},
            "owner": {n: o for n, (o, p) in socks.items()},
            "origins": {n: [round(v * 100.0, 2) for v in p] for n, p in pivots.items()},
            "measures": {"loa": size.x, "beam": size.y, "draft": draft, "canoe_volume": vol, "cb": [cb.x, cb.y, cb.z], "tris": tris},
            "live": {"ropes": "FRigLine (BoatModelVisuals.cpp) from these sockets", "sails": "FSailCloth from the physics strips (M_SailCloth Layout 4)"}}
    with open(os.path.join(OUT, "Maxi_sockets.json"), "w") as f:
        json.dump(meta, f, indent=1)
    for ob in obs.values():
        export_part(ob)
    print(f"Maxi: canoe mesh LOA {size.x:.3f} beam {size.y:.3f}, volume {vol:.3f} m^3 (sections {cvol:.3f}), "
          f"CB ({cb.x:.3f}, {cb.y:.3f}, {cb.z:.3f}) (sections x {cbx:.3f} z {cbz:.3f}); draft {draft:.3f}; tris {tris}; {len(socks)} sockets")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "maxi.blend"))
    if RENDER:
        render_setup()
        render(os.path.join(OUT, "maxi_quarter.png"), (-32, 24, 9), (-1, 0, 2), 40)
        render(os.path.join(OUT, "maxi_profile.png"), (0, 70, 2), (0, 0, 0), 50)
        render(os.path.join(OUT, "maxi_deck.png"), (-24, 6, 16), (-5, 0, 2), 35)
        # The turntable: eight bearings round her at the same height and distance.
        for k in range(8):
            a = math.radians(22.5 + 45 * k)
            render(os.path.join(OUT, f"maxi_turn_{k}.png"), (math.cos(a) * 46, math.sin(a) * 46, 12), (0, 0, 1.5), 40)


main()
