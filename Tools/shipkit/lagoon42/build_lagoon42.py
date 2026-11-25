"""The Lagoon 42's rebuild in Blender (docs/lagoon42-2 on): the hulls (slice 1), the bridge deck (slice 2), the decks,
saloon and roof (slice 3).

    blender -b --factory-startup -P build_lagoon42.py -- <out dir>

Builds both hull shells from hull_lagoon42.py (lines_lagoon42.json, the canoe depth solved for the game's 15.5 t),
each one shell from its inboard top round the keel to its outboard top: the sugar scoop's treads and risers close it
aft (L42_Hull, with the swim platforms and steps), the outboard windows are flush dark panes (L42_HullWindows). The
shell is cut along the boot top's line BOTTOM_Z: Topsides above, Antifouling below.

Slice 2 (docs/lagoon42-3) adds the bridge deck, its placeholder lid, the crossbeam with the centre beam, the bowsprit
and the trampolines from bridgedeck_lagoon42.py.

Slice 3 (docs/lagoon42-4) replaces the deck's lid with each hull's deck, toe rail and hatches (L42_Deck, L42_Hatches)
and adds the saloon's walls with their windows (L42_Saloon) and the roof over the saloon and cockpit (L42_Roof) from
saloon_lagoon42.py.

Writes <out>/lagoon42.blend, <out>/lagoon42_report.json (the shape loop's report: the canoe bodies' volume and centre
of buoyancy beside the game's) and <out>/hydrostatics.json.
Frame: Blender's, X forward, Y to PORT, Z up (the game's starboard-positive Y is mirrored, as build_fleet.py does), so
the shape loop's tools read it like the fleet's .blend.
"""
import json
import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hull_lagoon42 as H  # noqa: E402
import bridgedeck_lagoon42 as B  # noqa: E402
import saloon_lagoon42 as S  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
OUT = ARGS[0]
os.makedirs(OUT, exist_ok=True)

N_STATIONS, N_GIRTH = 220, 60          # stations along her length; girth steps per side (bunched: hull_lagoon42.girth)
UV_M = 1.0
BOTTOM_Z = 0.05                        # the antifouling's top over the game's waterline
SLOT_RGB = {"Topsides": (0.92, 0.92, 0.9), "Antifouling": (0.16, 0.17, 0.2), "CabinWindow": (0.06, 0.07, 0.08),
            "Teak": (0.55, 0.38, 0.22), "Trampoline": (0.1, 0.1, 0.11), "Spar": (0.55, 0.56, 0.58)}


def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)


def material(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*SLOT_RGB[name], 1.0)
    return m


def box_uvs(bm):
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        f.normal_update()
        ax = max(range(3), key=lambda i: abs(f.normal[i]))
        a, b = [(1, 2), (0, 2), (0, 1)][ax]
        for lp in f.loops:
            lp[uv].uv = (lp.vert.co[a] / UV_M, lp.vert.co[b] / UV_M)


def to_object(name, bm, mats):
    box_uvs(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for m in mats:
        me.materials.append(material(m))
    return ob


def bl(x, y, z):
    """Game frame (Y starboard) to Blender's (Y port)."""
    return (x, -y, z)


def hull_rows(cy, out_sign):
    """One hull's grid: for each station, the section from the inboard top round the keel to the outboard top, as
    game-frame points; out_sign is the outboard direction (+1 starboard hull, -1 port hull)."""
    rows = []
    xs = H.stations(N_STATIONS)
    for x in xs:
        row = []
        for j in range(-N_GIRTH, N_GIRTH + 1):
            side = 1 if j > 0 else -1
            y, z = H.section(x, H.girth(abs(j), N_GIRTH), side)
            if x == xs[-1]:
                y = 0.0
            row.append((x, cy + out_sign * side * y if j else cy, z))
        rows.append(row)
    return xs, rows


def section_between(x, z0, z1, side, n=8):
    """Half-breadths of the shell at station x between heights z0 and z1 on one side (side 1 outboard)."""
    out = []
    for k in range(n + 1):
        z = z0 + (z1 - z0) * k / n
        out.append((H.topsides_y(x, z), z))
    return out


def build_hull(bm, cy, out_sign):
    xs, rows = hull_rows(cy, out_sign)
    vrows = [[bm.verts.new(bl(*p)) for p in row] for row in rows]
    for a, b in zip(vrows[:-1], vrows[1:]):
        for j in range(len(a) - 1):
            bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
    # the transom: from the platform's edge round the keel, its own vertices so its edge stays crisp
    bm.faces.new([bm.verts.new(bl(*p)) for p in rows[0]])
    treads = []
    steps = H.scoop_steps()
    # the treads: flat from the inboard top to the outboard wall at each step's height
    for (x0, x1, z) in steps:
        txs = [x for x in xs if x0 - 1e-6 <= x <= x1 + 1e-6]
        trow = []
        for x in txs:
            yi = H.topsides_y(x, z)
            trow.append([bm.verts.new(bl(x, cy - out_sign * yi, z)), bm.verts.new(bl(x, cy + out_sign * yi, z))])
        for a, b in zip(trow[:-1], trow[1:]):
            treads.append(bm.faces.new((a[0], a[1], b[1], b[0])))
    # the risers: up from each tread to the next (the last to the sheer), across the hull at the step's forward edge
    tops = [z for _, _, z in steps[1:]] + [H.sheer_z(steps[-1][1])]
    for (x0, x1, z), zt in zip(steps, tops):
        inb = section_between(x1, z, zt, -1)
        outb = section_between(x1, z, zt, 1)
        poly = [bl(x1, cy - out_sign * y, zz) for y, zz in inb] + [bl(x1, cy + out_sign * y, zz) for y, zz in reversed(outb)]
        bm.faces.new([bm.verts.new(p) for p in poly])
    return treads


def build_windows(bm, cy, out_sign):
    """Flush dark panes on the outboard topsides, 4 mm proud, with rounded corners."""
    for pane in H.LINES["windows"]["panes"]:
        (xa, xb), (za, zb), r = pane["x"], pane["z"], pane["corner"]
        nx, nz = 24, 8
        grid = []
        for i in range(nx + 1):
            x = xa + (xb - xa) * i / nx
            dx = min(x - xa, xb - x)
            inset = r - math.sqrt(max(r * r - (r - dx) ** 2, 0.0)) if dx < r else 0.0
            col = []
            for k in range(nz + 1):
                z = za + inset + (zb - za - 2 * inset) * k / nz
                y = H.topsides_y(x, z) + 0.004
                col.append(bm.verts.new(bl(x, cy + out_sign * y, z)))
            grid.append(col)
        for a, b in zip(grid[:-1], grid[1:]):
            for k in range(nz):
                bm.faces.new((a[k], b[k], b[k + 1], a[k + 1]))


def grid_faces(bm, rows, flip=False):
    """Quads between consecutive rows of game-frame points (every row the same length); returns the faces."""
    vrows = [[bm.verts.new(bl(*p)) for p in row] for row in rows]
    faces = []
    for a, b in zip(vrows[:-1], vrows[1:]):
        for j in range(len(a) - 1):
            q = (a[j], a[j + 1], b[j + 1], b[j])
            faces.append(bm.faces.new(q[::-1] if flip else q))
    return faces


def face_out(bm, faces, probe, want):
    """Turn the faces' winding so the one nearest the game-frame point probe faces along want (a game-frame vector)."""
    p = bl(*probe)
    near = min(faces, key=lambda f: (f.calc_center_median() - Vector(p)).length)
    near.normal_update()
    w = bl(*want)
    if near.normal.dot(Vector(w)) < 0:
        bmesh.ops.reverse_faces(bm, faces=faces)


def sweep(bm, section, path, closed_ends=True):
    """A tube: section [(a, b)] placed at each path point by frame(t) -> (origin, a axis, b axis), game frame."""
    vrows = []
    for o, ea, eb in path:
        vrows.append([bm.verts.new(bl(*(o[i] + ea[i] * a + eb[i] * b for i in range(3)))) for a, b in section])
    faces = []
    n = len(section)
    for r0, r1 in zip(vrows[:-1], vrows[1:]):
        for j in range(n):
            faces.append(bm.faces.new((r0[j], r0[(j + 1) % n], r1[(j + 1) % n], r1[j])))
    if closed_ends:
        faces.append(bm.faces.new(vrows[0][::-1]))
        faces.append(bm.faces.new(vrows[-1]))
    return faces


def build_bridgedeck():
    """The bridge deck (underside, nose, foredeck and its aft face), the placeholder lid aft of the foredeck, the
    crossbeam with the centre beam, the bowsprit and the trampolines: each its own object."""
    bm = bmesh.new()
    faces = grid_faces(bm, B.bridgedeck_rows())
    faces.append(bm.faces.new([bm.verts.new(bl(*p)) for p in B.aft_face()]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    face_out(bm, bm.faces[:], (0.0, 0.0, B.US["z"]), (0, 0, -1))
    for f in bm.faces:
        f.smooth = len(f.verts) == 4
    to_object("L42_Bridgedeck", bm, ["Topsides"])

    bm = bmesh.new()
    grid_faces(bm, B.lid_rows())
    face_out(bm, bm.faces[:], (0.0, 0.0, 1.6), (0, 0, 1))
    to_object("L42_BridgeLidPlaceholder", bm, ["Topsides"])

    bm = bmesh.new()
    sec = B.rounded_rect(B.CB["chord"], B.CB["depth"], B.CB["radius"])
    e = B.crossbeam_ends()
    path = [((B.CB["x"], -e + 2 * e * k / 40, B.CB["z"]), (1, 0, 0), (0, 0, 1)) for k in range(41)]
    sweep(bm, sec, path)
    sec = B.rounded_rect(B.CBM["width"], B.CBM["depth"], B.CBM["radius"])
    x0, x1 = B.centre_beam_ends()
    path = [((x0 + (x1 - x0) * k / 20, 0.0, B.CBM["z"]), (0, 1, 0), (0, 0, 1)) for k in range(21)]
    sweep(bm, sec, path)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        f.smooth = len(f.verts) == 4
    to_object("L42_Crossbeam", bm, ["Topsides"])

    bm = bmesh.new()
    n = 16
    path = []
    for k in range(13):
        x, z, r = B.bowsprit_axis(k / 12)
        path.append(((x, 0.0, z), (0, r, 0), (0, 0, r)))
    circle = [(math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)) for i in range(n)]
    sweep(bm, circle, path)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        f.smooth = len(f.verts) == 4
    to_object("L42_Bowsprit", bm, ["Spar"])

    bm = bmesh.new()
    for side in (1, -1):
        fs = grid_faces(bm, B.trampoline_grid(side))
        face_out(bm, fs, (5.0, side * 1.2, B.TR["z"]), (0, 0, 1))
    to_object("L42_Trampolines", bm, ["Trampoline"])


def loop_faces(bm, rings, mats=None):
    """Quads between consecutive closed rings of game-frame points (every ring the same length); mats(k, i) gives a
    face's material index (k the ring, i the column). Returns the vertex rings and the faces."""
    vr = [[bm.verts.new(bl(*p)) for p in ring] for ring in rings]
    faces = []
    for k, (a, b) in enumerate(zip(vr[:-1], vr[1:])):
        n = len(a)
        for i in range(n):
            f = bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
            if mats:
                f.material_index = mats(k, i)
            faces.append(f)
    return vr, faces


def build_deck():
    """Each hull's deck (crowned between its sheers) with the toe rail on its outboard edge (L42_Deck), and the hatches
    (L42_Hatches: a low white frame, dark acrylic on top)."""
    bm = bmesh.new()
    for cy, out_sign in ((H.HULL_Y, 1), (-H.HULL_Y, -1)):
        fs = grid_faces(bm, S.deck_rows(cy))
        face_out(bm, fs, (0.0, cy, 1.6), (0, 0, 1))
        fs = grid_faces(bm, S.toe_rail_rows(cy, out_sign))
        face_out(bm, fs, (0.0, cy + out_sign * (H.half_beam(0.0) - 0.015), 1.6), (0, 0, 1))
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    to_object("L42_Deck", bm, ["Topsides"])

    bm = bmesh.new()
    for cy in (H.HULL_Y, -H.HULL_Y):
        for x0, x1, y0, y1, z0, z1 in S.hatches(cy):
            v = [bm.verts.new(bl(x, y, z)) for z in (z0, z1) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
            top = bm.faces.new(v[4:])
            top.material_index = 1
            for i in range(4):
                bm.faces.new((v[i], v[(i + 1) % 4], v[4 + (i + 1) % 4], v[4 + i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    to_object("L42_Hatches", bm, ["Topsides", "CabinWindow"])


def build_saloon():
    """The saloon's walls round its plan, from under the decks up into the roof: white below the plinth and above the
    windows, dark glass between along the front, the side windows and the aft door (L42_Saloon)."""
    rows, glazed = S.wall_rows()
    bm = bmesh.new()
    _, faces = loop_faces(bm, rows, lambda k, i: 1 if k == 1 and glazed[i] else 0)
    face_out(bm, faces, (S.SAL["front_x"], 0.0, 2.1), (1, 0, 0))
    for f in bm.faces:
        f.smooth = True
    to_object("L42_Saloon", bm, ["Topsides", "CabinWindow"])


def build_roof():
    """The roof over the saloon and the cockpit: rings from the top's centre over its rounded edge to the underside's
    centre, each closed at the middle (L42_Roof)."""
    rings = S.roof_rings()
    bm = bmesh.new()
    vr, faces = loop_faces(bm, rings)
    faces.append(bm.faces.new(vr[0][::-1]))
    faces.append(bm.faces.new(vr[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    face_out(bm, faces, (0.0, 0.0, S.ROOF["top_z"]), (0, 0, 1))
    for f in bm.faces:
        f.smooth = len(f.verts) == 4
    to_object("L42_Roof", bm, ["Topsides"])


def mesh_volume_below(ob, z=0.0):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, z), plane_no=(0, 0, 1),
                           clear_outer=True)
    bmesh.ops.holes_fill(bm, edges=bm.edges[:], sides=0)
    v = bm.calc_volume(signed=False)
    bm.free()
    return v


def light_sink(ob, light_m3):
    """How far the light boat rises off the game's waterline: the height z whose mesh volume under it, plus the
    appendages', is light_m3 (bisection on the built mesh, so it is the new hulls' own waterplane, not today's)."""
    app = H.BOT["appendage_volume_m3"]
    lo, hi = -0.4, 0.0
    for _ in range(30):
        z = (lo + hi) / 2
        if mesh_volume_below(ob, z) + app > light_m3:
            hi = z
        else:
            lo = z
    return -(lo + hi) / 2


def main():
    clear_scene()
    depth = H.solve_depth()
    bm = bmesh.new()
    treads = []
    for cy, out_sign in ((H.HULL_Y, 1), (-H.HULL_Y, -1)):
        treads += build_hull(bm, cy, out_sign)
    for f in treads:
        f.material_index = 2
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=(0.0, 0.0, BOTTOM_Z),
                           plane_no=(0.0, 0.0, 1.0))
    for f in bm.faces:
        if f.material_index != 2:
            f.material_index = 1 if f.calc_center_median().z < BOTTOM_Z else 0
        f.smooth = len(f.verts) < 6
    hull = to_object("L42_Hull", bm, ["Topsides", "Antifouling", "Teak"])
    wm = bmesh.new()
    for cy, out_sign in ((H.HULL_Y, 1), (-H.HULL_Y, -1)):
        build_windows(wm, cy, out_sign)
    to_object("L42_HullWindows", wm, ["CabinWindow"])
    build_deck()
    build_bridgedeck()
    build_saloon()
    build_roof()

    h = H.hydrostatics()
    mesh_v = mesh_volume_below(hull)
    app = H.BOT["appendage_volume_m3"]
    g = H.CARD["game"]
    sink = light_sink(hull, g["design_volume_m3"] - (g["load_kg"] + g["crew_kg"]) / 1000.0)
    report = {"canoe_volume_m3": round(mesh_v + app, 4), "hull_volume_m3": round(mesh_v, 4),
              "design_hull_volume_m3": round(h["volume_m3"], 4), "appendage_volume_m3": app,
              "physics_volume_m3": g["design_volume_m3"], "cb_x": round(h["cb"][0], 3), "cb_z": round(h["cb"][2], 3),
              "physics_cb": [-0.196, -0.424], "canoe_depth_m": round(depth, 4), "lwl_m": round(h["lwl"], 3),
              "beam_wl_one_hull_m": round(h["beam_wl_one_hull"], 3),
              "waterplane_m2": round(H.waterplane(), 2), "waterplane_15cm_down_m2": round(H.waterplane(-0.15), 2),
              "load_sink_m": round(sink, 4), "canoe_depth_light_m": round(depth - sink, 4),
              "bridgedeck_clearance_m": B.US["z"], "bridgedeck_clearance_light_m": round(B.US["z"] + sink, 4),
              "roof_top_z_m": S.ROOF["top_z"], "roof_top_light_m": round(S.ROOF["top_z"] + sink, 4),
              "mast_foot_measured": S.SD["measured"]["mast_foot"],
              "note": "canoe_volume_m3 is what lagoon42_check.py weighs: both hull meshes' volume under the game's "
                      "waterline (hull_volume_m3) plus the appendages' allowance (two keels and two rudders, a guess "
                      "until slice 5 builds them). design_hull_volume_m3 is the drawing's own integral "
                      "(hull_lagoon42.hydrostatics), which solve_depth sets to the target. load_sink_m: how far the "
                      "game's stores and crew (3.4 t) sink these hulls below the light boat's waterline, from the mesh "
                      "(today's hulls: 0.148, the card's game.load_sink_m); lagoon42_check.py measures the draft and "
                      "air draft from it when it is here."}
    json.dump(report, open(os.path.join(OUT, "lagoon42_report.json"), "w"), indent=1)
    json.dump(h, open(os.path.join(OUT, "hydrostatics.json"), "w"), indent=1)
    tris = sum(len(p.vertices) - 2 for p in hull.data.polygons)
    print(f"Lagoon 42: canoe depth {depth:.4f} m, hulls {h['volume_m3']:.4f} m^3 (mesh {mesh_v:.4f}), CB x {h['cb'][0]:+.3f}, "
          f"LWL {h['lwl']:.3f} m, one hull's BWL {h['beam_wl_one_hull']:.3f} m, load sink {sink:.3f} m, hull triangles {tris}")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "lagoon42.blend"))


main()
