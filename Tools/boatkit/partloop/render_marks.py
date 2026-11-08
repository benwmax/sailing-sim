"""Part detail loop: the course marks and the crew-overboard buoy on the water, as a sailor sees them
(docs/part-detail-loop/marks.md).

    python3 Tools/boatkit/partloop/render_marks.py <out dir> [--before] [--samples N] [--only RaceMark,...]
    (or blender -b --factory-startup -P Tools/boatkit/partloop/render_marks.py -- <out dir> ...)

The studio views (render_views.py) show the part; these show what the game shows: the part floating on a lake (dark
olive water with a light chop, a clear afternoon sky), seen from a J/22 helm's eye height (1.3 m over the water) at the
distances the drills and races use: "near" (6 m, rounding a mark or picking up the buoy), "far" (25 m, the approach),
and a "quarter" close look. --before draws the game's placeholders as UpdateDrillVisuals and TrafficManager place them
today (Engine BasicShapes: a 1 m cylinder and a 1 m sphere, scaled, BasicShapeMaterial in the placeholder's colour),
so the before and after sheets differ only in the object.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import bk_geom as G  # noqa: E402
import bk_parts as P  # noqa: E402
import bk_render as R  # noqa: E402

EYE = 1.3
# part -> (camera distances near/far, the placeholder as the game draws it: shape, scale (m), centre height over the
# water (m), colour). SailboatPawn::UpdateDrillVisuals: marks Cylinder (1.2, 1.2, 2.0) at +0.6 m, dummy Sphere 0.6 at
# +0.1 m; TrafficManager::StartRace: marks Cylinder (1.6, 1.6, 2.2) at +0.8 m, pin Sphere 1.1 at +0.3 m.
PARTS = {
    "LessonMark":    ((6.0, 25.0), ("cyl", (1.2, 1.2, 2.0), 0.6, (1.0, 0.35, 0.02))),
    "RaceMark":      ((7.0, 30.0), ("cyl", (1.6, 1.6, 2.2), 0.8, (1.0, 0.33, 0.02))),
    "PinBuoy":       ((7.0, 30.0), ("sph", (1.1, 1.1, 1.1), 0.3, (1.0, 0.33, 0.02))),
    "HorseshoeBuoy": ((4.0, 15.0), ("sph", (0.6, 0.6, 0.6), 0.1, (1.0, 0.85, 0.05))),
    "MOBBuoy":       ((6.0, 50.0), ("sph", (0.6, 0.6, 0.6), 0.1, (1.0, 0.85, 0.05))),   # the set the drill throws
}


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    out = os.path.abspath(a[0])
    samples = int(a[a.index("--samples") + 1]) if "--samples" in a else 48
    only = a[a.index("--only") + 1].split(",") if "--only" in a else list(PARTS)
    return out, "--before" in a, samples, only


def lake():
    """A 400 m water plane: olive-brown inland lake water, glossy, with a fine noise chop on the normal."""
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=200)
    me = bpy.data.meshes.new("Lake")
    bm.to_mesh(me)
    m = bpy.data.materials.new("LakeWater")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.020, 0.028, 0.018, 1)     # Ray Hubbard's green-brown, seen from above
    b.inputs["Roughness"].default_value = 0.06
    b.inputs["IOR"].default_value = 1.33
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.6, 3.0, 1.0)
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 2.2
    nz.inputs["Detail"].default_value = 6.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.05
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    me.materials.append(m)
    ob = bpy.data.objects.new("Lake", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def placeholder(spec):
    shape, scale, zc, col = spec
    if shape == "cyl":     # Engine BasicShapes Cylinder: 1 m across, 1 m tall, centred
        ob = G.cyl("before", (0, 0, -0.5), (0, 0, 0.5), 0.5, None, 64)
    else:
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=0.5)
        ob = G.mesh_obj("before", bm)
        for p in ob.data.polygons:
            p.use_smooth = True
    m = bpy.data.materials.new("BasicShape")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = 0.5          # BasicShapeMaterial: plain, mid roughness, no sheen or wear
    ob.data.materials.append(m)
    ob.scale = scale
    ob.location = (0, 0, zc)
    return ob


def scene(samples):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    R.SAMPLES = samples
    R._engine(1280, 720)
    sc = bpy.context.scene
    nt = sc.world.node_tree
    sky = next(n for n in nt.nodes if n.type == "TEX_SKY")
    sky.sun_elevation = math.radians(38)              # mid-afternoon
    sky.sun_rotation = math.radians(215)               # from behind the camera's left shoulder
    next(n for n in nt.nodes if n.type == "BACKGROUND").inputs["Strength"].default_value = 0.30
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = 3.2
    sun.angle = math.radians(0.6)
    so = bpy.data.objects.new("Sun", sun)
    sc.collection.objects.link(so)
    so.rotation_euler = (math.radians(52), 0, math.radians(215 - 90))
    lake()


def shoot(path, cam, target, lens):
    R._camera(cam, target, lens)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    out, before, samples, only = args()
    os.makedirs(out, exist_ok=True)
    stats = {}
    for name in only:
        (near, far), spec = PARTS[name]
        scene(samples)
        ob = placeholder(spec) if before else P.build(name)
        ob.rotation_euler.z = math.radians(25) if not before else 0.0
        h = {"HorseshoeBuoy": 0.10, "MOBBuoy": 0.6}.get(name, 0.5)
        shoot(os.path.join(out, f"{name}_near.png"), (-near * 0.85, -near * 0.5, EYE), (0, 0, h), 50)
        shoot(os.path.join(out, f"{name}_far.png"), (-far * 0.9, -far * 0.42, EYE), (0, 0, h), 85)
        q = {"HorseshoeBuoy": 2.6, "MOBBuoy": 5.0}.get(name, 4.0)
        shoot(os.path.join(out, f"{name}_quarter.png"), (-q * 0.7, q * 0.7, EYE + 0.9 if name == "HorseshoeBuoy" else EYE + 0.4),
              (0, 0, h * 0.8), 50)
        if not before:
            ob.data.calc_loop_triangles()
            stats[name] = {"tris": len(ob.data.loop_triangles), "slots": [m.name for m in ob.data.materials]}
    json.dump(stats, open(os.path.join(out, "stats.json"), "w"), indent=1)
    print(f"Marks: {len(only)} parts -> {out}")


main()
