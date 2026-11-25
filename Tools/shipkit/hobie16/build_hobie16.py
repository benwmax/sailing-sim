"""The Hobie 16's rebuild in Blender (docs/hobie16-2 on): slice 1, the twin hulls.

    blender -b --factory-startup -P build_hobie16.py -- <out dir>

Builds both hulls from hull_hobie16.py (lines_hobie16.json, the keel's depth solved for the game's 295 kg of boat and
crew): one closed shell a hull, its deck (above the greatest breadth: the non-skid in slice 7) and its sides as two
material slots, the transom a flat face. They're one object, H16_Hull, so the shape loop measures her overall beam.
The platform, rudders and rig come in slices 2 to 5; until then the renders show the hulls alone.

Writes <out>/hobie16.blend, <out>/hobie16_report.json (the mesh's volume under the design waterline, which
hobie16_check.py weighs, with the centre of buoyancy beside the game's centre of gravity, and how far she rises without
her crew) and <out>/hydrostatics.json (the drawing's own numbers, hull_hobie16.hydrostatics).
Frame: Blender's, X forward, Y to PORT, Z up (the game's starboard-positive Y mirrored, as build_fleet.py does), so the
shape loop's tools read it like the fleet's .blend. Each hull's outboard face is its fuller one.
"""
import json
import math
import os
import sys

import bpy
import bmesh

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hull_hobie16 as H  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
OUT = ARGS[0]
os.makedirs(OUT, exist_ok=True)

N_STATIONS, N_QUARTER = 200, 28       # stations along each hull; points a quarter of the section (4 quarters a ring)
UV_M = 1.0                            # box-projected UVs, 1 UV unit per metre (the tangent frame Unreal's import needs)
SLOT_RGB = {"Hull": (0.93, 0.93, 0.91), "Deck": (0.9, 0.9, 0.88)}


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


def add_hull(bm, centre_y):
    """One hull at Blender y = centre_y: stations x rings, the stem's ring collapsed to a point, the transom a face.
    Returns the transom face."""
    out = 1.0 if centre_y > 0 else -1.0                  # Blender's outboard direction for this hull
    rows = []
    xs = H.stations(N_STATIONS)
    for i, x in enumerate(xs):
        ring = H.section(float(x), N_QUARTER)
        row = []
        for y, z in ring:
            if i == len(xs) - 1:
                y = 0.0                                  # the stem's head: the ring closes to a point
            row.append(bm.verts.new((float(x), centre_y + out * float(y), float(z))))
        rows.append(row)
    m = len(rows[0])
    for a, b in zip(rows[:-1], rows[1:]):
        for j in range(m):
            k = (j + 1) % m
            bm.faces.new((a[j], a[k], b[k], b[j]))
    return bm.faces.new([bm.verts.new(v.co) for v in rows[0]])


def build_hulls():
    bm = bmesh.new()
    cy = H.CARD["game"]["hull_center_y_m"]
    transoms = [add_hull(bm, cy), add_hull(bm, -cy)]
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)     # the stems' rings collapse to one vertex each
    bmesh.ops.recalc_face_normals(bm, faces=[f for f in bm.faces if f not in transoms])
    for t in transoms:
        t.normal_update()
        if t.normal.x > 0:                               # a lone flat face: recalc can't orient it; face aft
            t.normal_flip()
        t.smooth = False
    box_uvs(bm)
    me = bpy.data.meshes.new("H16_Hull")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("H16_Hull", me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(material("Hull"))
    me.materials.append(material("Deck"))
    for p in me.polygons:
        p.use_smooth = len(p.vertices) < 20
        # the deck: above the greatest breadth at that station
        p.material_index = 1 if len(p.vertices) < 20 and p.center.z > H.max_beam_z(p.center.x) + 1e-4 else 0
    return ob


def mesh_volume_below(ob, z=0.0):
    """The mesh's own volume under the design waterline: cut at z, cap the waterplanes, measure (what the check weighs,
    so a coarse mesh can't hide behind the drawing's integral)."""
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
    hull = build_hulls()
    h = H.hydrostatics()
    g = H.CARD["game"]
    mesh_v = mesh_volume_below(hull)
    cg_x = (g["hull_rig_kg"] * 0.0 + g["crew_kg"] * -0.7) / (g["hull_rig_kg"] + g["crew_kg"])
    report = {"canoe_volume_m3": round(mesh_v, 4), "design_hull_volume_m3": round(h["volume_m3"], 4),
              "physics_volume_m3": g["design_volume_m3"], "keel_depth_m": round(depth, 4),
              "cb_x": round(h["cb"][0], 3), "cb_z": round(h["cb"][1], 3), "game_cg_x": round(cg_x, 3),
              "crew_sink_m": round(h["crew_sink"], 4), "draft_empty_m": round(h["draft_empty"], 4),
              "lwl_empty_m": round(h["lwl_empty"], 4), "lwl_m": round(h["lwl"], 4),
              "waterplane_m2": round(h["waterplane_m2"], 3), "beam_wl_hull_m": round(h["beam_wl_hull"], 3),
              "freeboard_mid_m": round(h["freeboard_mid"], 3), "transom_height_m": round(h["transom_height"], 3),
              "note": "canoe_volume_m3 is what hobie16_check.py weighs: both hull meshes' volume under the design "
                      "waterline (the game's, with two crew aboard). design_hull_volume_m3 is the drawing's own "
                      "integral (hull_hobie16.hydrostatics), which solve_depth sets to the boat's and crew's 0.295 m^3. "
                      "game_cg_x is the game's centre of gravity of boat and crew (Fleet.cpp: the boat's at x 0, the "
                      "crew's at -0.7): she floats level when cb_x is under it. crew_sink_m is how much higher she "
                      "floats without her crew, draft_empty_m and lwl_empty_m her draft and waterline length then (what "
                      "the card's 10 in and 15 ft 2 in are), lwl_m her waterline length with her crew aboard. "
                      "freeboard_mid_m is the deck's top over the water at the keel's lowest point, crew aboard."}
    json.dump(report, open(os.path.join(OUT, "hobie16_report.json"), "w"), indent=1)
    json.dump(h, open(os.path.join(OUT, "hydrostatics.json"), "w"), indent=1)
    tris = sum(len(p.vertices) - 2 for p in hull.data.polygons)
    print(f"H16: keel depth {depth:.4f} m, volume {h['volume_m3']:.4f} m^3 (mesh {mesh_v:.4f}), CB x {h['cb'][0]:+.3f} "
          f"(CG {cg_x:+.3f}), LWL {h['lwl']:.3f} m, hull triangles {tris}")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "hobie16.blend"))


main()
