"""Renders the frigate's light copy against the detailed ship (slice 16, docs/shipkit-16) from a light.py build.

    python -I render_light.py <frigate_light.blend> <out dir> [--state underway] [--dists 50,100,300] [--only pairs|wire] [--level L2] [--bearings abeam,bow]

As the J-Class's slice 12 (render_jclass.py, light_compare.py): at a 4K screen's own pixels with the game's narrowest
field of view (60 degrees), in one state of the ship (light_1797.json's; underway: sails set, guns housed), dressed at
wear level L2 by default (--level), on a dark sea, from an eye 3 m over the water on her port side, abeam and 40 degrees off the bow, at 50,
100 and 300 m from a point 15 m up her mainmast. Each pair (light_<dist>_<bearing>_{hero,light}.png) is rendered alike
(the same seed), cropped to the box round both, with an id shot of each (every dressed material in its own flat colour,
the sea and sky black) for light_compare.py to measure over her outline; light_noise.png is the detailed ship again with
another seed, the renderer's own noise, which no copy can beat. Then wireframes close to, detailed and light
(light_wire_<view>_{hero,light}.png): the head, a gun run out at its port, the stern gallery. Below the gun deck is
hidden in both, as the game hides it unless the camera is below. Every image is flipped left to right as render_wear's
are (the build's frame is Unreal's). Then light_compare.py (the J-Class's, imported) writes compare.json and, with
--docs <dir>, the side-by-side JPEGs.
"""
import importlib.util
import json
import math
import os
import sys
import time

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import weathering  # noqa: E402
import render_wear  # noqa: E402  (its ARGS are ours: <blend> <out>)

ARGS, opt = render_wear.ARGS, render_wear.opt
LC = json.load(open(os.path.join(HERE, "light_1797.json")))
_cmp = importlib.util.spec_from_file_location("light_compare", os.path.join(HERE, "..", "jclass", "light_compare.py"))
light_compare = importlib.util.module_from_spec(_cmp)
_cmp.loader.exec_module(light_compare)

AIM = Vector((-3.0, 0.0, 15.0))          # 15 m up the mainmast
EYE_Z = 3.0
WIRE = {"head": ((30.0, -12.0, 7.0), (33.0, 0.0, 5.0), 34.0),
        "gun": ((4.0, -9.0, 3.6), (1.5, -5.5, 3.2), 30.0),
        "gallery": ((-36.0, -11.0, 6.0), (-29.0, -5.0, 4.0), 32.0)}


def below(o):
    names = LC["inside_collections"]
    return any(c.name in names or c.name.startswith(tuple(n + "_" for n in names)) for c in o.users_collection)


def shown_in(o, state):
    """light.py's rule: a part in the scene's own collection shows in every state, one in a pose collection only in
    the states that list it."""
    pose = next((c.name for c in o.users_collection if c.name in {n for v in LC["states"].values() for n in v}
                 or c.name.startswith(("Sails_", "Running_", "Guns", "Carronades_"))), None)
    return pose is None or pose in LC["states"][state]


def sea(sc):
    """A dark sea to the horizon (black in the id shots: it has no emission)."""
    me = bpy.data.meshes.new("Sea")
    me.from_pydata([(-3000, -3000, 0), (3000, -3000, 0), (3000, 3000, 0), (-3000, 3000, 0)], [], [(0, 1, 2, 3)])
    m = bpy.data.materials.new("SeaDark")
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.05, 0.12, 0.16, 1)
    p.inputs["Roughness"].default_value = 0.08
    me.materials.append(m)
    o = bpy.data.objects.new("Sea", me)
    sc.collection.objects.link(o)
    return o


def wire_material():
    m = bpy.data.materials.new("LightWire")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    d = nt.nodes.new("ShaderNodeBsdfDiffuse")
    d.inputs[0].default_value = (0.75, 0.75, 0.72, 1)
    e = nt.nodes.new("ShaderNodeBsdfDiffuse")
    e.inputs[0].default_value = (0.03, 0.05, 0.12, 1)
    w = nt.nodes.new("ShaderNodeWireframe")
    w.use_pixel_size, w.inputs[0].default_value = True, 1.0
    mx = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(w.outputs[0], mx.inputs[0])
    nt.links.new(d.outputs[0], mx.inputs[1])
    nt.links.new(e.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs[0])
    return m


def crop_to_ship(sc, cam):
    """The render border round every shown mesh (detailed or twin), so a pair shares one crop."""
    bpy.context.view_layer.update()
    pts = [world_to_camera_view(sc, cam, o.matrix_world @ Vector(c)) for o in sc.objects
           if o.type == "MESH" and not o.hide_render and o.name != "Sea" for c in o.bound_box]
    pts = [p for p in pts if p.z > 0]
    pad = 0.01
    sc.render.use_border = sc.render.use_crop_to_border = True
    sc.render.border_min_x = max(0.0, min(p.x for p in pts) - pad)
    sc.render.border_max_x = min(1.0, max(p.x for p in pts) + pad)
    sc.render.border_min_y = max(0.0, min(p.y for p in pts) - pad)
    sc.render.border_max_y = min(1.0, max(p.y for p in pts) + pad)


def main():
    blend, out = ARGS[0], ARGS[1]
    bpy.ops.wm.open_mainfile(filepath=blend)
    # what the build itself hides (the lofted hull, the hidden hammocks) stays hidden; light.py hides every twin, so a
    # twin shows when its part would
    base = {o.name: (o.hide_render or o.hide_get()) for o in bpy.context.scene.objects if o.get("light_of") is None}

    def show_(state, light):
        """Hide everything but the state's parts (light: their twins instead, where a part has one)."""
        for o in bpy.context.scene.objects:
            if o.type != "MESH":
                continue
            if o.name == "Sea":
                o.hide_render = False
                continue
            if o.get("light_of") is not None:
                part = bpy.data.objects.get(o["light_of"])
                on = light and part is not None and shown_in(part, state) and not below(part) \
                    and not base.get(part.name, False)
            else:
                twin = bpy.data.objects.get(o.name + "_Light")
                on = shown_in(o, state) and not below(o) and not base.get(o.name, False) \
                    and not (light and twin is not None) and o.name not in LC["skip"]
            o.hide_render = not on
    weathering.dress(opt("--level", "L2"))
    os.makedirs(out, exist_ok=True)
    sc, co, so, w = render_wear.setup(3840, int(opt("--samples", 48)))
    sc.render.resolution_x, sc.render.resolution_y = 3840, 2160
    sea(sc)
    state = opt("--state", "underway")
    only = opt("--only")
    # the sun on her lee (port) side, where the eye is, 40 degrees up: the light copy is judged where it is lit
    so.rotation_euler = (Vector((-0.3, -0.6, 0.74)) * -1.0).to_track_quat("-Z", "Y").to_euler()
    t0 = time.time()
    if only in (None, "pairs"):
        co.data.angle = math.radians(LC["screen"]["fov_deg"])
        for dist in (int(d) for d in opt("--dists", "50,100,300").split(",")):
            for bname, deg in (("abeam", 90.0), ("bow", 40.0)):
                if bname not in opt("--bearings", "abeam,bow").split(","):
                    continue
                if os.path.exists(os.path.join(out, f"light_{dist}_{bname}_light_id.png")):
                    continue                    # done before (the cloud container restarts: runs resume)
                a = math.radians(deg)
                eye = (AIM.x + dist * math.cos(a), -dist * math.sin(a), EYE_Z)   # port side (-Y)
                render_wear.look(co, eye, AIM)
                for which in ("hero", "light"):
                    show_(state, which == "light")
                    if which == "hero":
                        crop_to_ship(sc, co)
                    render_wear.mode(sc, so, w, "lit")
                    sc.cycles.seed = 1
                    render_wear.render(sc, os.path.join(out, f"light_{dist}_{bname}_{which}.png"))
                    render_wear.mode(sc, so, w, "id")
                    sc.cycles.samples = 1
                    render_wear.render(sc, os.path.join(out, f"light_{dist}_{bname}_{which}_id.png"))
                    if dist == 100 and bname == "abeam" and which == "hero":
                        render_wear.mode(sc, so, w, "lit")
                        sc.cycles.seed = 7
                        render_wear.render(sc, os.path.join(out, "light_noise.png"))
                print(f"pair {dist} {bname} done {time.time() - t0:.0f} s", flush=True)
    if only in (None, "wire"):
        sc.render.use_border = sc.render.use_crop_to_border = False
        sc.render.resolution_x, sc.render.resolution_y = 1280, 720
        render_wear.mode(sc, so, w, "lit")
        sc.cycles.samples = 16
        bpy.context.view_layer.material_override = wire_material()
        bpy.data.objects["Sea"].hide_render = True
        for vname, (eye, at, fov) in WIRE.items():
            co.data.angle = math.radians(fov)
            render_wear.look(co, eye, at)
            for which in ("hero", "light"):
                show_(state, which == "light")
                bpy.data.objects["Sea"].hide_render = True
                render_wear.render(sc, os.path.join(out, f"light_wire_{vname}_{which}.png"))
            print(f"wire {vname} done {time.time() - t0:.0f} s", flush=True)
        bpy.context.view_layer.material_override = None
    if only in (None, "pairs"):
        rep = light_compare.main(out, opt("--docs"))
        for k, v in rep["views"].items():
            print(k, v)
        if "noise_100_abeam" in rep:
            print("noise", rep["noise_100_abeam"])


if __name__ == "__main__":
    main()
