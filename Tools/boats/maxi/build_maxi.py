"""The 100 ft maxi (Tools/boats/maxi/ref.json), built by script in Blender, stage 1: hull, deck shells, appendages and spars.

    blender -b --factory-startup -P Tools/boats/maxi/build_maxi.py -- <out dir> [--render]

- Hull: the quad loft from maxi_hull.py (the reference stations, interpolated), smoothed by a subdivision surface with
  the chine creased aft and fading out forward; a flat transom; the sheer edge rolled.
- Deck: a separate shell with real thickness, cambered, the cockpit well cut into it (floor, sides, a step down
  forward) and the low coachroof forward of the pit; a deck/hull flange under the sheer.
- Keel fin (NACA 0012, swept) with its bulb, twin canted rudders (NACA 0011), all lofted, bevelled where they meet.
- Spars: the mast (tapering elliptic section), three swept spreaders, boom and bowsprit.
- Sockets (empties named SOCKET_<Name>) for the rig, the crew stations and the moving parts, and sections.json for the
  Mac's physics class. Saves <out>/maxi.blend, writes <out>/Maxi100_sockets.json; --render adds three preview renders.
Frames: the body frame (X forward, Y starboard, Z up, metres, DWL amidships); Blender gets (x, -y, z).
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import maxi_hull as H  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else os.path.join(HERE, "out")
RENDER = "--render" in ARGS
os.makedirs(OUT, exist_ok=True)
REF = H.REF


def B(p):
    """Body frame to Blender."""
    return Vector((p[0], -p[1], p[2]))


def material(name, rgb, rough=0.4, metal=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    m.diffuse_color = (*rgb, 1.0)
    return m


MATS = {}


def make_materials():
    MATS.update({
    "Topsides": material("MI_Boat_Topsides", (0.02, 0.025, 0.03), 0.25),
    "Antifouling": material("MI_Boat_Antifouling", (0.05, 0.05, 0.055), 0.6),
    "Deck": material("MI_Boat_Deck", (0.55, 0.56, 0.57), 0.55),
    "NonSkid": material("MI_Boat_NonSkid", (0.42, 0.43, 0.44), 0.8),
    "Carbon": material("MI_Boat_Carbon", (0.025, 0.025, 0.028), 0.3),
    "Keel": material("MI_Boat_Keel", (0.06, 0.06, 0.065), 0.45),
    })


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
                e[crease] = 0.8
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
    zc = -k["draft"] + D / 2
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


def build_rudders():
    r = REF["rudders"]
    obs = []
    for s in (1, -1):
        cant = math.radians(r["cant_deg"]) * s
        sections = []
        for i in range(6):
            t = i / 5
            span = r["span"] * t
            # Top at the hull bottom near the transom, canted outboard below.
            st = H.station_at(r["x_stock"])
            ztop = min(-0.05, st["z_keel"] * 0.4) - 0.02
            y = s * r["y"] + math.sin(cant) * span
            z = ztop - math.cos(cant) * span
            chord = r["root_chord"] + (r["tip_chord"] - r["root_chord"]) * t
            sections.append(((r["x_stock"] + 0.25 * chord, y, z), chord, r["thickness"]))
        obs.append(loft_foil("Maxi_Rudder_" + ("S" if s > 0 else "P"), sections, "Keel"))
    return obs


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
    mast = tube_along("Maxi_Mast", pts, hw, hd, "Carbon")
    spreaders = []
    for k, sp in enumerate(rg["spreaders"]):
        z = z0 + sp["z"]
        sw = math.radians(sp["sweep_deg"])
        for s in (1, -1):
            tip = (mx - math.sin(sw) * sp["span"], s * math.cos(sw) * sp["span"], z + 0.15)
            spreaders.append(tube_along(f"Maxi_Spreader{k}_{'S' if s > 0 else 'P'}", [(mx, s * 0.12, z), tip], [0.035, 0.02], [0.09, 0.05], "Carbon", 10))
    b = rg["boom"]
    bz = z0 + b["gooseneck_z"]
    boom = beam_along_x("Maxi_Boom", mx - 0.2, mx - 0.2 - b["length"], bz, b["width"] / 2, b["depth"] / 2, "Carbon")
    bs = rg["bowsprit"]
    sprit = tube_along("Maxi_Bowsprit", [(REF["bow_x"] - 0.6, 0.0, bs["z"]), (REF["bow_x"] + bs["length"], 0.0, bs["z"] + 0.05)], [0.09, 0.06], [0.09, 0.06], "Carbon", 12)
    return mast, spreaders, boom, sprit


# --------------------------------------------------------------------------------------------------------------- sockets

def socket(name, p):
    e = bpy.data.objects.new("SOCKET_" + name, None)
    e.location = B(p)
    e.empty_display_size = 0.15
    bpy.context.scene.collection.objects.link(e)
    return name, p


def sockets():
    rg, d = REF["rig"], REF["deck"]
    mx = rg["mast_x"]
    z0 = deck_z(mx, 0.0)
    out = []
    out.append(socket("MastStep", (mx, 0.0, z0)))
    out.append(socket("Masthead", (mx, 0.0, z0 + rg["mast_above_deck"])))
    out.append(socket("Hounds", (mx, 0.0, z0 + rg["hounds_z"])))
    out.append(socket("Forestay", (rg["forestay_x"], 0.0, rg["forestay_z"])))
    out.append(socket("Tack_J1", (rg["forestay_x"], 0.0, rg["forestay_z"] + 0.3)))
    out.append(socket("Tack_ASail", (REF["bow_x"] + rg["bowsprit"]["length"], 0.0, rg["bowsprit"]["z"] + 0.1)))
    out.append(socket("Gooseneck", (mx - 0.2, 0.0, z0 + rg["boom"]["gooseneck_z"])))
    out.append(socket("BoomEnd", (mx - 0.2 - rg["boom"]["length"], 0.0, z0 + rg["boom"]["gooseneck_z"])))
    for s, nm in ((1, "S"), (-1, "P")):
        out.append(socket(f"Runner_{nm}", (rg["runners_x"], s * rg["runner_y"], deck_z(rg["runners_x"], rg["runner_y"]))))
        out.append(socket(f"Chainplate_{nm}", (mx - 0.4, s * (H.station_at(mx)["half_deck"] - 0.25), deck_z(mx, 3.0))))
        w = d["wheels"]
        out.append(socket(f"Wheel_{nm}", (w["x"], s * w["y"], deck_z(w["x"], w["y"]) - d["cockpit"]["depth"] + 1.05)))
        out.append(socket(f"Helm_{nm}", (w["x"] - 0.7, s * (w["y"] + 0.6), deck_z(w["x"], 3.0))))
        out.append(socket(f"Trimmer_Jib_{nm}", (-7.6, s * 2.9, deck_z(-7.6, 2.9))))
        out.append(socket(f"JibSheetLead_{nm}", (-3.2, s * d["genoa_tracks"]["y"], deck_z(-3.2, 2.95))))
    out.append(socket("Trimmer_Main", (d["traveller"]["x"] + 0.6, 0.0, deck_z(-10.8, 0.0) - d["cockpit"]["depth"])))
    out.append(socket("MainsheetTraveller", (d["traveller"]["x"], 0.0, deck_z(d["traveller"]["x"], 0.0) - d["cockpit"]["depth"] + 0.3)))
    for k, p in enumerate(d["pedestals"]):
        out.append(socket(f"Grinder_{k + 1}", (p["x"], p["y"], deck_z(p["x"], 0.0) - d["cockpit"]["depth"])))
    out.append(socket("Pit", (-4.9, 0.0, deck_z(-4.9, 0.0) - d["cockpit"]["depth"])))
    out.append(socket("Mast", (mx - 0.8, 0.0, z0)))
    out.append(socket("Bow", (11.5, 0.0, deck_z(11.5, 0.0))))
    out.append(socket("Navigator", (-1.0, 0.0, deck_z(-1.0, 0.0) - 1.8)))
    out.append(socket("RudderStock_S", (REF["rudders"]["x_stock"], REF["rudders"]["y"], 0.0)))
    out.append(socket("RudderStock_P", (REF["rudders"]["x_stock"], -REF["rudders"]["y"], 0.0)))
    with open(os.path.join(OUT, f"{REF['tag']}_sockets.json"), "w") as f:
        json.dump({n: [round(v * 100.0, 2) for v in p] for n, p in out}, f, indent=1)   # Unreal frame, cm
    return out


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


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    make_materials()
    hull = build_hull()
    deck = build_deck()
    pit = build_cockpit()
    roof = build_coachroof()
    fin, bulb = build_keel()
    rudders = build_rudders()
    spars = build_spars()
    socks = sockets()
    H.export_sections(os.path.join(OUT, "sections.json"))
    vol, cbx, cbz = H.canoe_volume()
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in bpy.context.scene.objects if o.type == "MESH")
    print(f"Maxi: canoe {vol:.2f} m^3 ({vol * 1025:.0f} kg), CB x {cbx:.2f} z {cbz:.3f}; {tris} tris; {len(socks)} sockets")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "maxi.blend"))
    if RENDER:
        sc = bpy.context.scene
        sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
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
        render(os.path.join(OUT, "maxi_quarter.png"), (-32, 24, 9), (-1, 0, 2), 40)
        render(os.path.join(OUT, "maxi_profile.png"), (0, 70, 2), (0, 0, 0), 50)
        render(os.path.join(OUT, "maxi_deck.png"), (-24, 6, 16), (-5, 0, 2), 35)


main()
