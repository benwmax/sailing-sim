"""The moth in Blender (docs/moth-2 on): slice 1, the hull.

    blender -b --factory-startup -P build_moth.py -- <out dir>

Builds the hull from hull_moth.py (lines_moth.json; the waterline solved so she floats the game's 115 kg, boat and
sailor, at rest): one closed shell, MOTH_Hull, its deck (above the deck edge's roll: the non-skid in slice 6) and its
sides as two material slots, the transom a flat face. The wings, foils and rig come in slices 2 to 4.

Writes <out>/moth.blend, <out>/moth_report.json (the mesh's volume under the design waterline, which the check weighs,
the centre of buoyancy beside the game's centre of gravity, and how she floats without her sailor) and
<out>/hydrostatics.json (hull_moth.report). Frame: Blender's, X forward, Y to PORT, Z up (the fleet's .blend frame; the
hull is symmetric, so only later parts care), z = 0 the design waterline at rest with her sailor aboard.
"""
import json
import math
import os
import sys

import bpy
import bmesh

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hull_moth as H  # noqa: E402
import wings_moth as WG  # noqa: E402
import foils_moth as FO  # noqa: E402
import rig_moth as RG  # noqa: E402
from mathutils import Vector  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
OUT = ARGS[0]
os.makedirs(OUT, exist_ok=True)

N_STATIONS, N_SIDE = 180, 40          # stations along the hull; points up one side (plus the deck edge and deck)
UV_M = 1.0                            # box-projected UVs, 1 UV unit per metre (the tangent frame Unreal's import needs)
SLOT_RGB = {"Hull": (0.93, 0.93, 0.91), "Deck": (0.9, 0.9, 0.88), "Carbon": (0.06, 0.06, 0.065),
            "Mesh": (0.12, 0.12, 0.13), "Foil": (0.1, 0.1, 0.11), "Alloy": (0.7, 0.7, 0.72),
            "Sail": (0.85, 0.87, 0.9), "Batten": (0.2, 0.2, 0.22), "Wire": (0.6, 0.6, 0.62)}


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


def ring(x):
    """The closed section at x: starboard side keel-up-deck, then the port side mirrored back down (the centreline
    points shared once)."""
    half = H.section(float(x), N_SIDE)
    side = [(-y, z) for y, z in half]                        # Blender: starboard is -y
    back = [(y, z) for y, z in reversed(half[1:-1])]
    return side + back


def build_hull():
    bm = bmesh.new()
    xs = H.stations(N_STATIONS)
    rows = []
    for i, x in enumerate(xs):
        pts = ring(x)
        if i == len(xs) - 1:                                  # the stem's head: the ring closes onto its centreline
            pts = [(0.0, z) for _, z in pts]
        rows.append([bm.verts.new((float(x), y, z)) for y, z in pts])
    m = len(rows[0])
    for a, b in zip(rows[:-1], rows[1:]):
        for j in range(m):
            k = (j + 1) % m
            bm.faces.new((a[j], a[k], b[k], b[j]))
    transom = bm.faces.new([bm.verts.new(v.co) for v in rows[0]])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    degenerate = [f for f in bm.faces if f.calc_area() < 1e-10]
    bmesh.ops.delete(bm, geom=degenerate, context="FACES")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])     # closed shell: the transom oriented with the rest
    box_uvs(bm)
    me = bpy.data.meshes.new("MOTH_Hull")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("MOTH_Hull", me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(material("Hull"))
    me.materials.append(material("Deck"))
    r = H.SEC["edge_round_m"]
    for p in me.polygons:
        big = len(p.vertices) > 8
        p.use_smooth = not big
        p.material_index = 1 if (not big and p.center.z > H.sheer_z(p.center.x) - r * 0.3) else 0
    return ob


def resample(pts, step=0.02):
    """A polyline resampled at about `step` metres, its corners kept."""
    out = [Vector(pts[0])]
    for a, b in zip(pts[:-1], pts[1:]):
        a, b = Vector(a), Vector(b)
        n = max(1, int((b - a).length / step))
        out += [a.lerp(b, k / n) for k in range(1, n + 1)]
    return out


def add_tube(bm, pts, d, sides, d_end=None):
    """A round tube of diameter d (tapering to d_end) along the polyline pts (parallel-transported rings, both ends
    capped)."""
    pts = resample(pts)
    d_end = d if d_end is None else d_end
    tang = [(pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(len(pts))]
    up = Vector((0, 0, 1)) if abs(tang[0].z) < 0.9 else Vector((1, 0, 0))
    n = (up - tang[0] * up.dot(tang[0])).normalized()
    rings = []
    for i, p in enumerate(pts):
        r = (d + (d_end - d) * i / max(len(pts) - 1, 1)) / 2
        n = (n - tang[i] * n.dot(tang[i])).normalized()
        bnorm = tang[i].cross(n)
        rings.append([bm.verts.new(p + r * (math.cos(2 * math.pi * k / sides) * n + math.sin(2 * math.pi * k / sides) * bnorm))
                      for k in range(sides)])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(sides):
            bm.faces.new((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])


def finish(bm, name, slot):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    box_uvs(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(material(slot))
    for p in me.polygons:
        p.use_smooth = len(p.vertices) == 4
    return ob


def build_wings():
    """Both wings: MOTH_WingFrame (every tube, carbon) and MOTH_WingDeck (the mesh, one thin sheet a side)."""
    t = WG.W["tube"]
    bm = bmesh.new()
    for side in (1, -1):
        for name, pts in WG.frame(side).items():
            d = t["rail_d_m"] if name == "Rail" else t["inner_d_m"] if name == "Inner" else t["bar_d_m"] * 0.7
            add_tube(bm, pts, d, t["sides"])
    frame = finish(bm, "MOTH_WingFrame", "Carbon")
    bm = bmesh.new()
    for side in (1, -1):
        rows, _ = WG.deck(side)
        vs = [[bm.verts.new(p) for p in row] for row in rows]
        for a, b in zip(vs[:-1], vs[1:]):
            for j in range(len(a) - 1):
                bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
    deck = finish(bm, "MOTH_WingDeck", "Mesh")
    mod = deck.modifiers.new("Thickness", "SOLIDIFY")       # a 4 mm sheet, so it renders from both sides
    mod.thickness = 0.004
    mod.offset = 0.0
    return frame, deck


def add_loft(bm, rings):
    """A closed body through rings of equal length (each ring a closed loop), both ends capped."""
    vs = [[bm.verts.new(p) for p in ring] for ring in rings]
    m = len(vs[0])
    for a, b in zip(vs[:-1], vs[1:]):
        for j in range(m):
            k = (j + 1) % m
            bm.faces.new((a[j], a[k], b[k], b[j]))
    bm.faces.new(vs[0])
    bm.faces.new(list(reversed(vs[-1])))


def add_pod(bm, start, length, d, n=20, sides=16):
    """A slim body of revolution along x from start (its tail) forward: a torpedo (blunt nose, fine tail)."""
    rings = []
    for i in range(n + 1):
        u = i / n
        r = d / 2 * math.sqrt(max(0.0, math.sin(math.pi * u ** 0.8))) if 0 < i < n else 0.0004
        x = start[0] + length * u
        rings.append([(x, start[1] + r * math.cos(2 * math.pi * k / sides), start[2] + r * math.sin(2 * math.pi * k / sides))
                      for k in range(sides)])
    add_loft(bm, rings)


def build_foils():
    """The main strut and T-foil with its flap and pod, the gantry, rudder and elevator, the wand and its fitting:
    one object each (the game moves the flap, elevator and wand on their own)."""
    parts, info = FO.geometry()
    slot = {"MOTH_GantryL": "Carbon", "MOTH_GantryR": "Carbon", "MOTH_Wand": "Carbon", "MOTH_BowFitting": "Carbon",
            "MOTH_RudderHead": "Alloy", "MOTH_WandPaddle": "Foil"}
    obs = []
    for name, spec in parts.items():
        bm = bmesh.new()
        kind = spec[0]
        if kind == "loft":
            add_loft(bm, spec[1])
        elif kind == "tube":
            add_tube(bm, spec[1], spec[2], 10, spec[3])
        elif kind == "pod":
            add_pod(bm, spec[1], spec[2], spec[3])
        elif kind == "plate":
            bm.faces.new([bm.verts.new(p) for p in spec[1]])
        ob = finish(bm, name, slot.get(name, "Foil"))
        if kind == "plate":
            mod = ob.modifiers.new("Thickness", "SOLIDIFY")
            mod.thickness = 0.003
        if kind == "loft":
            for p in ob.data.polygons:
                p.use_smooth = len(p.vertices) == 4
        obs.append(ob)
    return obs, info


def build_rig():
    """The mast, boom, shrouds and forestay, the sail (roach solved for the card's area) and its battens."""
    roach = RG.solve_roach()
    obs = []
    bm = bmesh.new()
    add_loft(bm, RG.mast_rings())
    obs.append(finish(bm, "MOTH_Mast", "Carbon"))
    bm = bmesh.new()
    goose, end = RG.boom_line()
    b = RG.R["boom"]
    add_tube(bm, [tuple(goose), tuple(end)], b["d_m"], 12, b["d_end_m"])
    obs.append(finish(bm, "MOTH_Boom", "Carbon"))
    bm = bmesh.new()
    for name, (a, c) in RG.wires().items():
        add_tube(bm, [tuple(a), tuple(c)], RG.R["rigging"]["wire_d_m"], 6)
    obs.append(finish(bm, "MOTH_Rigging", "Wire"))
    bm = bmesh.new()
    rows = RG.sail_grid(roach)
    vs = [[bm.verts.new(p) for p in row] for row in rows]
    for r0, r1 in zip(vs[:-1], vs[1:]):
        for j in range(len(r0) - 1):
            bm.faces.new((r0[j], r1[j], r1[j + 1], r0[j + 1]))
    sail = finish(bm, "MOTH_Sail", "Sail")
    mod = sail.modifiers.new("Thickness", "SOLIDIFY")
    mod.thickness = 0.002
    obs.append(sail)
    bm = bmesh.new()
    for line in RG.battens(roach):
        add_tube(bm, line, 0.008, 6)
    obs.append(finish(bm, "MOTH_Battens", "Batten"))
    pts, tack, head, clew = RG.sail_outline(roach)
    info = {"roach": roach, "sail_area_m2": RG.area(pts), "luff_length_m": float(((head - tack) ** 2).sum() ** 0.5),
            "sockets": RG.sockets(roach)}
    return obs, info


def mesh_volume_below(ob, z=0.0):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, z), plane_no=(0, 0, 1),
                           clear_outer=True)
    cap = bmesh.ops.holes_fill(bm, edges=bm.edges[:], sides=0)["faces"]
    bmesh.ops.triangulate(bm, faces=cap)     # the waterplane is one long concave n-gon: polyfill it before measuring
    v = bm.calc_volume(signed=False)
    bm.free()
    return v


def main():
    clear_scene()
    rep = H.report()                     # solves the waterline first: the mesh is built in the design frame
    hull = build_hull()
    mesh_v = mesh_volume_below(hull)
    frame, deck = build_wings()
    foils, finfo = build_foils()
    rig, rinfo = build_rig()
    g = H.CARD["game"]
    report = dict(rep)
    report.update({
        "canoe_volume_m3": round(mesh_v, 5), "physics_volume_m3": g["design_volume_m3"],
        "crew_kg": g["crew_kg"], "boat_kg_assumed": H.CARD["targets"]["rigged_weight_kg"],
        "sailor_x": H.SAILOR_X, "boat_cg_x": H.BOAT_CG_X,
        "note": "canoe_volume_m3 is the mesh's own volume under the design waterline (at rest, sailor aboard), which "
                "moth_check.py weighs against the card's 115 kg; volume_m3 is the drawing's integral. She floats level "
                "when cb_x is under cg_x (the boat's 35 kg at boat_cg_x and the sailor's 80 kg at sailor_x, sitting by "
                "the wing bars at rest). empty_rise_m is how far she rises without him: her static waterplane for "
                "class rule 6.3 (the main foil must leave the hull below it). Flying, none of this matters: the hull is "
                "0.4-0.5 m clear."})
    json.dump(rep, open(os.path.join(OUT, "hydrostatics.json"), "w"), indent=1)
    report["wing_plan_area_m2"] = round(WG.plan_area(), 4)
    report.update({k: round(v, 4) for k, v in FO.areas().items()})
    report["foils"] = {k: (round(v, 4) if isinstance(v, float) else [round(c, 4) for c in v]) for k, v in finfo.items()}
    report.update({"sail_area_m2": round(rinfo["sail_area_m2"], 4), "luff_length_m": round(rinfo["luff_length_m"], 4),
                   "roach": round(rinfo["roach"], 4)})
    json.dump({"boat": "Moth (Lacewing 11)", "frame": "Unreal: x forward, y starboard, z up, cm; z 0 the design "
               "waterline at rest", "sockets": {**FO.sockets(finfo), **rinfo["sockets"]}},
              open(os.path.join(OUT, "Moth_sockets.json"), "w"), indent=1)
    json.dump(report, open(os.path.join(OUT, "moth_report.json"), "w"), indent=1)
    tris = sum(len(p.vertices) - 2 for p in hull.data.polygons)
    wt = sum(len(p.vertices) - 2 for o in (frame, deck) for p in o.data.polygons)
    print(f"MOTH wings: beam {2 * max(abs(v.co.y) for v in frame.data.vertices):.4f} m, plan area a side "
          f"{WG.plan_area():.3f} m^2, triangles {wt} (deck before its thickness)")
    rt = sum(len(p.vertices) - 2 for o in rig for p in o.data.polygons)
    print(f"MOTH rig: sail {rinfo['sail_area_m2']:.3f} m^2 (roach {rinfo['roach']:.3f}), luff {rinfo['luff_length_m']:.3f} m, "
          f"triangles {rt}")
    ft = sum(len(p.vertices) - 2 for o in foils for p in o.data.polygons)
    a = FO.areas()
    print(f"MOTH foils: main {a['main_foil_area_m2']:.4f} m^2 (flap {a['flap_area_m2']:.4f}), elevator "
          f"{a['elevator_area_m2']:.4f} m^2, wand at {finfo['wand_angle_deg']:.1f} deg from vertical, triangles {ft}")
    print(f"MOTH: waterline {rep['waterline_over_keel_m']:.4f} m over the keel, volume {rep['volume_m3']:.4f} "
          f"(mesh {mesh_v:.4f}), CB x {rep['cb_x']:+.3f} (CG {rep['cg_x']:+.3f}), trim {rep['trim_deg']:+.2f} deg, "
          f"LWL {rep['lwl_m']:.3f}, hull triangles {tris}")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "moth.blend"))


main()
