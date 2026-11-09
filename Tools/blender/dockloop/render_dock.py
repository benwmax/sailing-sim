"""Dock hardware detail pass (Nov 9 2026): render the dock kit from one version of Tools/blender/build_docks.py the same
way every round, for the part detail loop's sheets and blind reviews (docs/dock-hardware).

For each SM_Dock_* mesh the script builds, it writes four stills (three-quarter, square on its +X face, from the
other side and a clay still with every slot grey) and one "in place" still on a plain deck, piling or float of the
real size, plus stats.json (triangles, size in mm, slots). Preview looks are flat stand-ins for the MI_World_* looks.

Run with the bpy module (or blender -b --factory-startup -P ... --):
    python3 Tools/blender/dockloop/render_dock.py <build_docks.py> <out dir> [--parts Cleat,Hoop] [--samples 24]
`git show main:Tools/blender/build_docks.py > before.py` gives the before round.
"""
import json
import math
import os
import runpy
import sys
import tempfile

import bpy
from mathutils import Vector

LOOKS = {   # slot -> (base colour, metallic, roughness, emission)
    "Steel": ((0.62, 0.63, 0.64), 1.0, 0.33, 0.0),
    "White": ((0.80, 0.80, 0.77), 0.0, 0.5, 0.0),
    "Dark": ((0.03, 0.03, 0.03), 0.0, 0.7, 0.0),
    "Trim": ((0.33, 0.34, 0.35), 0.0, 0.5, 0.0),
    "Glass": ((0.04, 0.05, 0.06), 0.0, 0.05, 0.0),
    "LampGlow": ((0.95, 0.93, 0.85), 0.0, 0.3, 0.6),
    "SafetyRed": ((0.55, 0.03, 0.02), 0.0, 0.4, 0.0),
    "Floats": ((0.025, 0.025, 0.025), 0.0, 0.55, 0.0),
    "Gold": ((0.75, 0.55, 0.22), 1.0, 0.35, 0.0),
}
# what the part stands on for the "in place" still: (kind, args)
CONTEXT = {
    "Cleat": "deck", "Pedestal": "deck", "Box": "deck", "Extinguisher": "deck", "Ladder": "dock_end",
    "PilingCap": "piling_top", "Hoop": "piling_hoop", "Float": None, "Bumper": "finger",
}
VIEWS = {"threeq": (1.0, -1.0, 0.7), "front": (1.0, 0.0, 0.08), "back": (-1.0, 0.8, 0.45)}


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parts = a[a.index("--parts") + 1].split(",") if "--parts" in a else None
    samples = int(a[a.index("--samples") + 1]) if "--samples" in a else 24
    return os.path.abspath(a[0]), os.path.abspath(a[1]), parts, samples


def build(src, fbx_dir):
    argv = sys.argv
    sys.argv = [src, "--", fbx_dir]
    try:
        runpy.run_path(src, run_name="__main__")
    finally:
        sys.argv = argv


def material(name, clay=False):
    key = name.split(".")[0]
    col, met, rough, emit = LOOKS.get(key, ((0.5, 0.5, 0.5), 0.0, 0.5, 0.0))
    if clay:
        col, met, rough, emit = (0.6, 0.6, 0.6), 0.0, 0.55, 0.0
    m = bpy.data.materials.new(f"Prev_{key}_{int(clay)}")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Metallic"].default_value = met
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*col, 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


def plain(name, col, rough=0.8):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def add_box(name, c, half, mat):
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=c)
    o = bpy.context.active_object
    o.name = name
    o.scale = half
    o.data.materials.append(mat)
    return o


def add_cyl(name, c, r, depth, mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=r, depth=depth, location=c)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(mat)
    return o


def context(kind):
    deck = plain("Deck", (0.42, 0.36, 0.28))
    fl = plain("FloatCtx", (0.03, 0.03, 0.03), 0.6)
    pile = plain("Pile", (0.30, 0.28, 0.25))
    water = plain("Water", (0.10, 0.16, 0.17), 0.15)
    objs = []
    if kind == "deck":
        objs.append(add_box("CtxDeck", (0, 0, -0.06), (1.2, 0.8, 0.06), deck))
    elif kind == "dock_end":
        objs.append(add_box("CtxDeck", (-0.8, 0, -0.06), (0.8, 1.0, 0.06), deck))
        objs.append(add_box("CtxFloat", (-0.8, 0, -0.4), (0.78, 0.85, 0.28), fl))
        objs.append(add_box("CtxWater", (0, 0, -0.45), (2.0, 2.0, 0.001), water))
    elif kind == "piling_top":
        objs.append(add_cyl("CtxPile", (0, 0, -0.6), 0.17, 1.2, pile))
    elif kind == "piling_hoop":
        objs.append(add_cyl("CtxPile", (0, 0, 0.2), 0.17, 1.6, pile))
        objs.append(add_box("CtxDeck", (-0.7, 0, 0.0), (0.5, 0.8, 0.06), deck))
        objs.append(add_box("CtxWater", (0, 0, -0.45), (2.0, 2.0, 0.001), water))
    elif kind == "finger":
        objs.append(add_box("CtxFinger", (-0.6, 0, -0.04), (0.6, 0.3, 0.04), deck))
        for s in (-1, 1):
            objs.append(add_box("CtxRub", (-0.6, s * 0.33, -0.09), (0.6, 0.03, 0.07), fl))
        objs.append(add_box("CtxFloat", (-0.6, 0, -0.3), (0.6, 0.22, 0.2), fl))
    return objs


def studio(w, h, samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("Sky")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.62, 0.7, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.6


def bounds(objs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = -lo
    for o in objs:
        for v in o.data.vertices:
            p = o.matrix_world @ v.co
            lo = Vector([min(lo[i], p[i]) for i in range(3)])
            hi = Vector([max(hi[i], p[i]) for i in range(3)])
    return lo, hi


def shoot(objs, view, path, fill=1.0, floor=True, frame=None):
    for o in list(bpy.data.objects):
        if o.type in ("LIGHT", "CAMERA") or o.name == "Floor":
            bpy.data.objects.remove(o, do_unlink=True)
    lo, hi = bounds(frame or objs)
    c = (lo + hi) / 2
    size = max(hi - lo)
    if floor:
        bpy.ops.mesh.primitive_plane_add(size=size * 40, location=(c.x, c.y, lo.z))
        f = bpy.context.active_object
        f.name = "Floor"
        f.data.materials.append(plain("FloorMat", (0.32, 0.33, 0.34), 0.7))
    for name, off, e, s in (("Key", (-1, -1.2, 1.6), 900, 2.0), ("Rim", (1.5, 1.2, 0.8), 350, 1.5), ("Fill", (1.2, -1.6, 0.3), 150, 3.0)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = e * size ** 2
        ld.size = size * s
        lo_ = bpy.data.objects.new(name, ld)
        bpy.context.scene.collection.objects.link(lo_)
        lo_.location = c + Vector(off) * size * 2.5
        lo_.rotation_euler = (c - lo_.location).to_track_quat("-Z", "Y").to_euler()
    cd = bpy.data.cameras.new("Cam")
    cd.lens = 70
    cd.clip_start = 0.001
    cam = bpy.data.objects.new("Cam", cd)
    bpy.context.scene.collection.objects.link(cam)
    d = Vector(view).normalized()
    cam.location = c + d * size * 2.6 / fill
    cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    src, out, only, samples = args()
    os.makedirs(out, exist_ok=True)
    fbx_dir = tempfile.mkdtemp(prefix="dockfbx_")
    build(src, fbx_dir)
    stats = {}
    for fn in sorted(os.listdir(fbx_dir)):
        name = fn[len("SM_Dock_"):-4]
        if only and name not in only:
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        studio(720, 540, samples)
        bpy.ops.import_scene.fbx(filepath=os.path.join(fbx_dir, fn))
        part = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        slots = []
        for o in part:
            for i, ms in enumerate(o.material_slots):
                slots.append(ms.material.name.split(".")[0] if ms.material else "")
        tris = sum(len(p.vertices) - 2 for o in part for p in o.data.polygons)
        lo, hi = bounds(part)
        stats[name] = {"tris": tris, "size_mm": [round((hi[i] - lo[i]) * 1000) for i in range(3)], "slots": slots,
                       "lo_mm": [round(lo[i] * 1000) for i in range(3)], "hi_mm": [round(hi[i] * 1000) for i in range(3)]}
        looks = {}
        for o in part:
            for ms in o.material_slots:
                looks.setdefault(ms.material.name, ms.material)
                ms.material = material(ms.material.name)
        d = os.path.join(out, name)
        os.makedirs(d, exist_ok=True)
        for view, vec in VIEWS.items():
            shoot(part, vec, os.path.join(d, f"{view}.png"))
        for o in part:
            for ms in o.material_slots:
                ms.material = material("clay", clay=True)
        shoot(part, VIEWS["threeq"], os.path.join(d, "clay.png"))
        for o in part:
            for i, ms in enumerate(o.material_slots):
                ms.material = material(slots[i] if i < len(slots) else "")
        kind = CONTEXT.get(name)
        if kind:
            ctx = context(kind)
            shoot(part + ctx, (1.0, -1.3, 0.8), os.path.join(d, "inplace.png"), fill=0.6, floor=False, frame=part)
        print(f"Dockloop: {name} {stats[name]}")
    with open(os.path.join(out, "stats.json"), "w") as f:
        json.dump(stats, f, indent=1)


main()
