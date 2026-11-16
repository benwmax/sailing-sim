"""The Catalina 22's rebuild in Blender (docs/c22-2 on): slice 1, the hull shell.

    blender -b --factory-startup -P build_c22.py -- <out dir> [--fleet <dir>]

Builds the hull shell from hull_c22.py (lines_c22.json, the canoe depth solved for the card's weight) and a flat,
cambered placeholder deck so renders read as a boat; the deck, cockpit and cabin are slice 2. With --fleet <dir> (a
build_fleet.py FLEET_SHAPE_BLEND=1 output: Catalina22_shape.blend) it also links today's keel, rudder, mast and boom as
they are, so the shape loop's views show the hull with today's appendages until slice 3 and 4 replace them.

Writes <out>/c22.blend (objects C22_Hull, C22_DeckPlaceholder, and with --fleet today's Catalina22_Board,
SM_Catalina22_Rudder, SM_Catalina22_Mast, SM_Catalina22_Boom), <out>/c22_report.json (the canoe body's volume and
centre of buoyancy beside the game's: the shape loop's report format) and <out>/hydrostatics.json.
Frame: Blender's, X forward, Y to PORT, Z up (the game's starboard-positive Y is mirrored, as build_fleet.py does), so
the shape loop's tools read it like the fleet's .blend.
"""
import json
import math
import os
import sys

import bpy
import bmesh

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hull_c22 as H  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
OUT = ARGS[0]
FLEET = ARGS[ARGS.index("--fleet") + 1] if "--fleet" in ARGS else None
os.makedirs(OUT, exist_ok=True)

N_STATIONS, N_GIRTH = 180, 64         # stations along her length, girth steps per side (bunched: hull_c22.girth)
UV_M = 1.0                            # box-projected UVs, 1 UV unit per metre (the tangent frame Unreal's import needs)


def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)


def material(name, rgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    return m


def box_uvs(bm):
    """UVMap: each face projected along the axis its normal is closest to, in metres (as build_fleet.py's parts)."""
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        f.normal_update()
        ax = max(range(3), key=lambda i: abs(f.normal[i]))
        a, b = [(1, 2), (0, 2), (0, 1)][ax]
        for lp in f.loops:
            lp[uv].uv = (lp.vert.co[a] / UV_M, lp.vert.co[b] / UV_M)


def mesh_object(name, bm, mat):
    box_uvs(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def build_hull():
    """The shell: one grid of stations x girth (port, centreline, starboard), the transom closing its aft end."""
    bm = bmesh.new()
    rows = []
    xs = H.stations(N_STATIONS)
    for x in xs:
        row = []
        for j in range(-N_GIRTH, N_GIRTH + 1):
            y, z = H.section(x, H.girth(abs(j), N_GIRTH))
            if x == xs[-1]:
                y = 0.0                                        # the stem's head: the row closes to a point
            row.append(bm.verts.new((x, -math.copysign(y, j) if j else 0.0, z)))   # Blender Y = port
        rows.append(row)
    for a, b in zip(rows[:-1], rows[1:]):
        for j in range(len(a) - 1):
            bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)     # the stem head's row collapses to one vertex
    # the transom: its own vertices, so it shades flat and its edge with the topsides stays crisp
    transom = bm.faces.new([bm.verts.new(v.co) for v in rows[0]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    transom.normal_update()
    if transom.normal.x > 0:                                   # a lone flat face: recalc can't orient it; face aft
        transom.normal_flip()
    transom.smooth = False
    ob = mesh_object("C22_Hull", bm, material("GelcoatHull", (0.92, 0.92, 0.9)))
    for p in ob.data.polygons:
        p.use_smooth = len(p.vertices) == 4                    # the quads; the transom stays flat
    return ob


def build_deck_placeholder():
    """A flat deck with 4 cm of camber over the sheer: only so the renders read as a boat (slice 2 builds the deck)."""
    bm = bmesh.new()
    rows = []
    n = 24
    for x in H.stations(N_STATIONS):
        hb, zs = H.half_beam(x) - 0.002, H.sheer_z(x)
        row = []
        for j in range(-n, n + 1):
            t = j / n
            row.append(bm.verts.new((x, -hb * t, zs + 0.04 * (1 - t * t) * min(1.0, hb / 0.6))))
        rows.append(row)
    for a, b in zip(rows[:-1], rows[1:]):
        for j in range(len(a) - 1):
            bm.faces.new((a[j], b[j], b[j + 1], a[j + 1]))
    bm.faces.new(rows[0])                                      # its camber over the transom's top, closed
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_object("C22_DeckPlaceholder", bm, material("DeckPlaceholder", (0.8, 0.78, 0.72)))
    for p in ob.data.polygons:
        p.use_smooth = len(p.vertices) == 4
    return ob


def link_fleet(path):
    """Today's keel, rudder, mast and boom from the fleet's shape .blend, as they are."""
    blend = os.path.join(path, "Catalina22_shape.blend")
    want = ["Catalina22_Board", "SM_Catalina22_Rudder", "SM_Catalina22_Mast", "SM_Catalina22_Boom"]
    with bpy.data.libraries.load(blend, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in want]
    for o in dst.objects:
        if o is not None:
            bpy.context.scene.collection.objects.link(o)


def mesh_volume_below(ob, z=0.0):
    """The mesh's own volume under the design waterline: cut at z, cap the waterplane, measure. What c22_check.py
    weighs, so a coarse mesh can't hide behind the drawing's integral."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, z), plane_no=(0, 0, 1),
                           clear_outer=True)
    bmesh.ops.holes_fill(bm, edges=bm.edges[:], sides=0)
    v = bm.calc_volume(signed=False)
    bm.free()
    return v


def main():
    clear_scene()
    depth = H.solve_depth()
    hull = build_hull()
    build_deck_placeholder()
    if FLEET:
        link_fleet(FLEET)
    h = H.hydrostatics()
    g = H.CARD["game"]
    mesh_v = mesh_volume_below(hull)
    report = {"canoe_volume_m3": round(mesh_v + H.CARD["targets"]["keel_kg"] / H.IRON_KG_M3, 4),
              "hull_volume_m3": round(mesh_v, 4), "design_hull_volume_m3": round(h["volume_m3"], 4),
              "keel_volume_m3": round(H.CARD["targets"]["keel_kg"] / H.IRON_KG_M3, 4),
              "physics_volume_m3": g["design_volume_m3"], "cb_x": round(h["cb"][0], 3), "cb_z": round(h["cb"][2], 3),
              "physics_cb": [-0.112, -0.102],
              "note": "canoe_volume_m3 is the hull mesh's volume under the design waterline (hull_volume_m3, measured on "
                      "the mesh) plus the swing keel's (249 kg of cast iron), which slice 3 hangs below it: what "
                      "c22_check.py weighs. design_hull_volume_m3 is the drawing's own integral (hull_c22.hydrostatics), "
                      "which solve_depth sets to the target."}
    json.dump(report, open(os.path.join(OUT, "c22_report.json"), "w"), indent=1)
    h["canoe_depth"] = depth
    json.dump(h, open(os.path.join(OUT, "hydrostatics.json"), "w"), indent=1)
    tris = sum(len(p.vertices) - 2 for p in hull.data.polygons)
    print(f"C22: canoe depth {depth:.4f} m, hull volume {h['volume_m3']:.4f} m^3 (mesh {mesh_v:.4f}), CB x {h['cb'][0]:+.3f}, "
          f"LWL {h['lwl']:.3f} m, BWL {h['beam_wl']:.3f} m, hull triangles {tris}")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "c22.blend"))


main()
