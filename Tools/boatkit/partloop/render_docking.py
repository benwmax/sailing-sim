"""Part detail loop: fenders and dock lines, as parts and in place in the J/22's slip (docs/part-detail-loop/docklines.md).

    python3 Tools/boatkit/partloop/render_docking.py parts <out dir> [--before] [--samples N]
    python3 Tools/boatkit/partloop/render_docking.py slip <out dir> <SM_J22_Berthed.fbx> [--samples N] [--views a,b]
    (or blender -b --factory-startup -P Tools/boatkit/partloop/render_docking.py -- ...)

parts: the kit's Fender hanging on its line, CleatHitch on the club's 10 in dock cleat (Tools/blender/build_docks.py's
SM_Dock_Cleat, rebuilt here render-only), EyeOnCleat round the J/22's 130 mm horn cleat (kit HornCleat 130) and
DockLineEye laid on a deck. --before draws what the boat wears today (Tools/blender/build_berthed.py on main): a
plain 140 mm, 10-sided white tube for a fender with a 4-sided line, and 5-sided 12 mm dock lines that stop short of
the cleats (they ended at fixed points 0.5 m up, not at a cleat).

slip: the hero J/22 (Inputs/j22-hero/fbx/SM_J22H_Hull.fbx) in her berth at the club, wearing a berthed dress FBX
(build_berthed.py's output, before or after), with the row, both fingers and their cleats where FMarina::Load and
AMarinaActor::DockKitPlacements put them, from a sailor's eye on the finger, at the bow and from above.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import bk_geom as G  # noqa: E402
import bk_materials as BM  # noqa: E402
import bk_parts as P  # noqa: E402
import bk_render as R  # noqa: E402
import bk_ropework as RW  # noqa: E402


EXPOSURE = -1.6


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    o = {"mode": a[0], "out": os.path.abspath(a[1]), "before": "--before" in a,
         "samples": int(a[a.index("--samples") + 1]) if "--samples" in a else 40}
    o["fbx"] = a[2] if o["mode"] == "slip" else None
    o["views"] = a[a.index("--views") + 1].split(",") if "--views" in a else None
    return o


def mat(name, col, rough=0.6, metal=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def dock_cleat(at=(0, 0, 0), yaw=0.0):
    """SM_Dock_Cleat (build_docks.py cleat()): 10 in cast aluminium, X along the horns, origin on the deck."""
    al = BM.get("Aluminium")
    objs = [G.box("base", (0, 0, 0.004), (0.13, 0.064, 0.008), al)]
    for s in (-1, 1):
        objs.append(G.cyl(f"foot{s}", (s * 0.04, 0, 0.006), (s * 0.03, 0, 0.05), 0.018, al, 16, r1=0.013))
        objs.append(G.tube(f"horn{s}", RW.smooth([(s * 0.03, 0, 0.055), (s * 0.075, 0, 0.062), (s * 0.115, 0, 0.066), (s * 0.127, 0, 0.064)], 0.004), 0.011, al, 16))
    objs.append(G.cyl("waist", (-0.03, 0, 0.055), (0.03, 0, 0.055), 0.014, al, 16))
    for o in objs:
        G.finish(o, 0)
    ob = G.join("DockCleat", objs)
    ob.matrix_world = Matrix.Translation(at) @ Matrix.Rotation(yaw, 4, "Z")
    return ob


def floor_plane(name, size, z, col, rough=0.8):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2)
    ob = G.mesh_obj(name, bm, mat(name + "Mat", col, rough))
    ob.location.z = z
    return ob


def studio(samples, w=1100, h=800):
    G.clear_scene()
    R.SAMPLES = samples
    R._engine(w, h)
    bpy.context.scene.view_settings.exposure = EXPOSURE


def lights(c, size):
    for nm, off, k, spread in (("Key", (-1, -1.2, 1.6), 5, 2.0), ("Rim", (1.5, 1.2, 0.8), 2.5, 1.5), ("Fill", (1.2, -2.0, -0.3), 1, 3.0)):
        pos = Vector(c) + Vector(off) * size * 3
        R._light(nm, "AREA", pos, c, k * (pos - Vector(c)).length_squared, size * spread)


def shoot(path, cam, target, lens=50):
    R._camera(cam, target, lens)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def tris(ob):
    ob.data.calc_loop_triangles()
    return len(ob.data.loop_triangles)


def old_fender():
    """main's kit Fender and the berthed dress's: what the boat wore before this pass."""
    prof = [(0, 0)]
    for i in range(41):
        z = 0.5 * i / 40
        r = 0.075 * math.sin(math.pi * min(1.0, 0.18 + 0.64 * i / 40)) ** 0.25
        r *= 1 + 0.015 * math.cos(G.TAU * i / 5)
        prof.append((r, z))
    prof.append((0, 0.5))
    body = G.lathe("body", prof, BM.get("BlackPlastic"), 40)
    G.finish(body, 0)
    return body


def parts(o):
    out = o["out"]
    os.makedirs(out, exist_ok=True)
    stats = {}
    deck = (0.30, 0.29, 0.27)
    # 1. fender hanging on its line from a rail
    studio(o["samples"])
    if o["before"]:
        f = G.cyl("fender", (0, 0, -0.62), (0, 0, -0.12), 0.07, BM.get("Deck"), 10)       # berthed: tube r 0.07, 10 sides
        G.tube("line", [(0, 0, -0.12), (0, 0, 0.0)], 0.004, BM.get("Rope"), 4)
    else:
        f = P.build("Fender")
        stats["Fender"] = {"tris": tris(f), "slots": [m.name for m in f.data.materials]}
        G.tube("line", RW.smooth([(0, 0, 0.0), (0, 0.006, 0.05), (0, 0.0, 0.12)], 0.004), 0.0045, BM.get("Rope"), 10)
    floor_plane("Floor", 30, -1.4, (0.32, 0.33, 0.34))
    lights((0, 0, -0.3), 0.6)
    shoot(os.path.join(out, "fender_threeq.png"), (1.25, -1.0, 0.1), (0, 0, -0.3), 50)
    shoot(os.path.join(out, "fender_close.png"), (0.38, -0.36, 0.05), (0, 0, -0.08), 50)
    # 2. dock line made fast on the dock cleat
    studio(o["samples"])
    floor_plane("Deck", 6, 0.0, deck)
    dock_cleat()
    if o["before"]:
        G.tube("line", RW.sag((0.3, -1.4, 0.35), (0.25, -0.12, 0.07), 0.05), 0.006, BM.get("Rope"), 5)
    else:
        h = P.build("CleatHitch")
        stats["CleatHitch"] = {"tris": tris(h), "slots": [m.name for m in h.data.materials]}
        lead = Vector(h.children[0].location) if h.children else Vector((0.18, -0.5, 0.04))
        G.tube("span", RW.resample([lead, lead + (lead - Vector((0, 0, lead.z))).normalized() * 0.9 + Vector((0, 0, 0.35))], 0.02), 0.00475, BM.get("Rope"), 10)
    lights((0, 0, 0.04), 0.3)
    shoot(os.path.join(out, "hitch_threeq.png"), (0.30, -0.34, 0.30), (0, 0, 0.035), 50)
    shoot(os.path.join(out, "hitch_top.png"), (0.01, -0.03, 0.42), (0, 0, 0.04), 50)
    # 3. the eye round the J/22's bow cleat
    studio(o["samples"])
    floor_plane("Deck", 6, 0.0, (0.55, 0.55, 0.52))
    P.build("HornCleat", length=0.13)
    if o["before"]:
        G.tube("line", RW.sag((0.05, -0.22, 0.06), (0.4, -1.3, 0.2), 0.03), 0.006, BM.get("Rope"), 5)
    else:
        e = P.build("EyeOnCleat")
        stats["EyeOnCleat"] = {"tris": tris(e), "slots": [m.name for m in e.data.materials]}
    lights((0, 0, 0.03), 0.3)
    shoot(os.path.join(out, "eye_threeq.png"), (0.26, -0.40, 0.26), (0, -0.08, 0.02), 50)
    # 4. the spliced eye on its own
    if not o["before"]:
        studio(o["samples"])
        floor_plane("Deck", 6, 0.0, deck)
        e = P.build("DockLineEye")
        stats["DockLineEye"] = {"tris": tris(e), "slots": [m.name for m in e.data.materials]}
        lights((0.05, 0, 0.0), 0.4)
        shoot(os.path.join(out, "splice_threeq.png"), (-0.05, -0.42, 0.30), (-0.02, 0, 0.0), 50)
        shoot(os.path.join(out, "splice_close.png"), (-0.08, -0.14, 0.10), (-0.07, 0, 0.0), 50)
        stats["clay"] = True
    json.dump(stats, open(os.path.join(out, "stats.json"), "w"), indent=1)
    print("Docking parts:", stats)


# ------------------------------------------------------------------ the slip

PACKS = json.load(open(os.path.join(REPO, "Tools", "blender", "boat_packs.json")))


def preview_by_pack(ob):
    """Give an imported packed mesh (pack slot + entry in UV 'Pack') the kit's preview materials per entry."""
    me = ob.data
    uv = me.uv_layers.get("Pack")
    names = [m.name.split(".")[0] if m else "" for m in me.materials]
    slots = []
    idx = []
    for p in me.polygons:
        pack = names[p.material_index]
        e = int(round(uv.data[p.loop_indices[0]].uv[0])) if uv else 0
        slot = PACKS[pack][e] if pack in PACKS and e < len(PACKS[pack]) else pack
        if slot not in slots:
            slots.append(slot)
        idx.append(slots.index(slot))
    me.materials.clear()
    for s in slots:
        try:
            me.materials.append(BM.get(s))
        except KeyError:
            me.materials.append(mat(s, (0.7, 0.7, 0.7)))
    me.polygons.foreach_set("material_index", idx)


def import_fbx(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    return [o for o in bpy.data.objects if o not in before and o.type == "MESH"]


def slip(o):
    out = o["out"]
    os.makedirs(out, exist_ok=True)
    studio(o["samples"], 1280, 800)
    sc = bpy.context.scene
    nt = sc.world.node_tree
    sky = next(n for n in nt.nodes if n.type == "TEX_SKY")
    sky.sun_elevation = math.radians(40)
    sky.sun_rotation = math.radians(200)
    next(n for n in nt.nodes if n.type == "BACKGROUND").inputs["Strength"].default_value = 0.3
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = 3.0
    so = bpy.data.objects.new("Sun", sun)
    sc.collection.objects.link(so)
    so.rotation_euler = (math.radians(50), 0, math.radians(110))
    # the hero hull: gelcoat white for every slot (a preview: the bake's maps aren't loaded)
    hull = import_fbx(os.path.join(REPO, "Inputs", "j22-hero", "fbx", "SM_J22H_Hull.fbx"))
    gel = mat("Gelcoat", (0.82, 0.82, 0.79), 0.35)
    for h in hull:
        for i in range(len(h.data.materials)):
            h.data.materials[i] = gel
    dress = import_fbx(o["fbx"])
    for d in dress:
        preview_by_pack(d)
    # water, the row (1.8 m), two fingers (0.6 m) and their cleats; Blender axes (Y port): Unreal Y -> -Y
    floor_plane("Water", 400, 0.0, (0.02, 0.028, 0.018), 0.08)
    dk = mat("DockDeck", (0.50, 0.49, 0.46), 0.85)
    fl = mat("Floats", (0.05, 0.05, 0.05), 0.6)
    edge = 0.5 * 7.3 + 0.4
    G.box("Row", (edge + 0.9, 0, 0.40), (1.8, 14.0, 0.10), dk)
    G.box("RowFloat", (edge + 0.9, 0, 0.18), (1.5, 13.6, 0.34), fl)
    for s in (1, -1):
        G.box(f"Finger{s}", (edge - 3.65, -s * 1.8, 0.40), (7.3, 0.6, 0.10), dk)
        G.box(f"FingerFloat{s}", (edge - 3.65, -s * 1.8, 0.22), (7.1, 0.45, 0.3), fl)
        for t in (0.45, 0.95):
            dock_cleat((edge - 7.3 * t, -s * 1.8, 0.43), 0.0)
        dock_cleat((edge + 0.15, -s * 0.9, 0.43), math.pi / 2)
    views = {
        "finger_stern": ((-4.6, -2.4, 2.05), (-2.6, -1.3, 0.55), 40),      # standing on the starboard finger, aft of her
        "quarter": ((-3.5, -1.95, 1.30), (-2.95, -1.45, 0.55), 35),         # her starboard quarter: eye, span, hitch
        "port_spring": ((-1.6, 2.8, 1.75), (-1.0, 1.5, 0.45), 35),          # the port fender and the spring
        "bow": ((5.2, -1.2, 1.75), (3.6, -0.45, 0.55), 40),                 # from the row: the bow lines and their cleats
        "wide": ((-6.5, -6.0, 5.0), (0.2, 0.0, 0.5), 32),
    }
    for name, (cam, tgt, lens) in views.items():
        if o["views"] and name not in o["views"]:
            continue
        shoot(os.path.join(out, f"slip_{name}.png"), cam, tgt, lens)
    t = sum(tris(d) for d in dress)
    json.dump({"dress_tris": t}, open(os.path.join(out, "stats.json"), "w"))
    print("Slip:", t, "dress tris")


O = args()
(parts if O["mode"] == "parts" else slip)(O)
