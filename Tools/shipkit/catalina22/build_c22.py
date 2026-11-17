"""The Catalina 22's rebuild in Blender (docs/c22-2 on): slice 1, the hull shell; slice 2, the deck and cabin; slice 3,
the swing keel, kick-up rudder and outboard; slice 4, the mast, boom and standing rigging; slice 5, the sails; slice 6, the deck hardware and running rigging.

    blender -b --factory-startup -P build_c22.py -- <out dir> [--fleet <dir>] [--raised] [--keel-up]

Builds the hull shell from hull_c22.py (lines_c22.json, the canoe depth solved for the card's weight), the deck,
rubrail, cockpit, cabin trunk, ports, drop boards, fore hatch and pop-top from deck_c22.py (build_deck_c22.py meshes
them; --raised builds the pop-top up, under the closed one's name), and the keel, its stub and trunk, the rudder with
its tiller, the gudgeons and the outboard from keel_c22.py (build_keel_c22.py; --keel-up builds the keel raised and the
rudder kicked up, under the down ones' names), and the mast, boom, wires and their kit fittings from rig_c22.py
(build_rig_c22.py), the sails in each of their states from sails_c22.py (build_sails_c22.py: all hidden but the
mainsail under its cover), and the deck hardware and each state's running rigging from hardware_c22.py
(build_hardware_c22.py: all states hidden but her rest at the mooring). --fleet <dir> is accepted and ignored since slice 4, which replaced the last of today's parts it
linked (the mast and boom).

Writes <out>/c22.blend (objects C22_Hull and the deck's, the keel's and the rig's: build_deck_c22.py,
build_keel_c22.py and build_rig_c22.py list them), <out>/c22_report.json (the canoe body's volume and centre of
buoyancy beside the game's: the shape loop's report format), <out>/hydrostatics.json and <out>/c22_sockets.json (the
rig's and the hardware's sockets, for c22_check.py's I, J, P and E and slice 9's live ropes).
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
import build_deck_c22 as BD  # noqa: E402
import build_keel_c22 as BK  # noqa: E402
import build_rig_c22 as BR  # noqa: E402
import build_sails_c22 as BS  # noqa: E402
import build_hardware_c22 as BH  # noqa: E402
import keel_c22 as KC  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
OUT = ARGS[0]
FLEET = ARGS[ARGS.index("--fleet") + 1] if "--fleet" in ARGS else None
RAISED = "--raised" in ARGS
KEEL_UP = "--keel-up" in ARGS
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


SLOT_RGB = {"Deck": (0.9, 0.89, 0.85), "NonSkid": (0.84, 0.81, 0.74), "Rubrail": (0.85, 0.85, 0.83),
            "CabinWindow": (0.08, 0.09, 0.1), "Aluminium": (0.75, 0.76, 0.78), "Teak": (0.45, 0.28, 0.14),
            "SailCover": (0.75, 0.7, 0.58), "Stainless": (0.8, 0.8, 0.82), "Keel": (0.24, 0.23, 0.22),
            "Antifouling": (0.16, 0.2, 0.3), "Topsides": (0.92, 0.92, 0.9), "Wood": (0.55, 0.36, 0.2),
            "BlackPlastic": (0.05, 0.05, 0.05), "Rubber": (0.08, 0.08, 0.08), "PaintedAluminium": (0.9, 0.9, 0.9), "Wire": (0.7, 0.71, 0.73),
            "ClothMain": (0.93, 0.92, 0.88), "ClothJib": (0.93, 0.92, 0.88), "ClothGenoa": (0.93, 0.92, 0.88),
            "ClothSpinnaker": (0.13, 0.33, 0.62), "SailHeap": (0.9, 0.89, 0.85), "SailPatch": (0.9, 0.89, 0.85),
            "SailLine": (0.25, 0.33, 0.55), "SailBag": (0.18, 0.22, 0.32)}


def deck_materials():
    return {k: material(k, v) for k, v in SLOT_RGB.items()}


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


def closed_volume(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = bm.calc_volume(signed=False)
    bm.free()
    return v


def main():
    clear_scene()
    depth = H.solve_depth()
    hull = build_hull()
    BD.build_all(deck_materials(), raised=RAISED)
    keel_obs = BK.build_all(deck_materials(), keel_up=KEEL_UP)
    keel = next(o for o in keel_obs if o.name == ("C22_KeelDown" if KEEL_UP else "C22_Keel"))
    _, socks = BR.build_all(deck_materials())
    BS.build_all(deck_materials())
    _, hw = BH.build_all(deck_materials())
    socks["sockets"].update(hw["sockets"])
    socks["owner"].update(hw["owner"])
    socks["hardware_note"] = hw["note"]
    json.dump(socks, open(os.path.join(OUT, "c22_sockets.json"), "w"), indent=1)
    h = H.hydrostatics()
    g = H.CARD["game"]
    mesh_v = mesh_volume_below(hull)
    keel_v = closed_volume(keel) - BK.pin_volume()
    stub_solid, trunk_water = KC.stub_volume()
    report = {"canoe_volume_m3": round(mesh_v + keel_v + stub_solid - trunk_water, 4),
              "hull_volume_m3": round(mesh_v, 4), "design_hull_volume_m3": round(h["volume_m3"], 4),
              "keel_volume_m3": round(keel_v, 4), "keel_kg": round(keel_v * KC.KL["iron_kg_m3"], 1),
              "stub_volume_m3": round(stub_solid, 4), "trunk_water_m3": round(trunk_water, 4),
              "keel_thickness_m": round(KC.thickness(), 4), "keel_raise_deg": round(math.degrees(KC.raise_angle()), 2),
              "physics_volume_m3": g["design_volume_m3"], "cb_x": round(h["cb"][0], 3), "cb_z": round(h["cb"][2], 3),
              "physics_cb": [-0.112, -0.102],
              "note": "canoe_volume_m3 is what c22_check.py weighs: the hull mesh's volume under the design waterline "
                      "(hull_volume_m3), the keel plate's mesh volume less its pin's (keel_volume_m3, all "
                      "of it under the water: keel_kg of cast iron), the stub's moulding under the hull (stub_volume_m3, keel_c22.stub_volume) "
                      "less the water in the trunk inside the hull's skin (trunk_water_m3). design_hull_volume_m3 is "
                      "the drawing's own integral (hull_c22.hydrostatics), which solve_depth sets to the target."}
    json.dump(report, open(os.path.join(OUT, "c22_report.json"), "w"), indent=1)
    h["canoe_depth"] = depth
    json.dump(h, open(os.path.join(OUT, "hydrostatics.json"), "w"), indent=1)
    tris = sum(len(p.vertices) - 2 for p in hull.data.polygons)
    print(f"C22: canoe depth {depth:.4f} m, hull volume {h['volume_m3']:.4f} m^3 (mesh {mesh_v:.4f}), CB x {h['cb'][0]:+.3f}, "
          f"LWL {h['lwl']:.3f} m, BWL {h['beam_wl']:.3f} m, hull triangles {tris}")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "c22.blend"))


main()
