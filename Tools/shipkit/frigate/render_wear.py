"""Renders the frigate's wear views (slice 15, docs/shipkit-15) from a built frigate.blend, dressed by weathering.py.

    python -I Tools/shipkit/frigate/render_wear.py <frigate.blend> <out dir> [--views a,b] [--levels L0,L4]
        [--res 960] [--samples 32] [--lit-only] [--save <dressed.blend>]

For each view (VIEWS: a camera in the ship's frame, metres, X forward, Y starboard, Z up from the load waterline) it
writes wear_<view>_id.png (each dressed material in its own flat colour, wear_ids.json names them), and for each level
wear_<view>_<level>.png lit and wear_<view>_<level>_albedo.png (each material's colour alone, no light), the inputs of
wear_check.py. Every image is flipped left to right, so it shows her as the game will (the build's frame is Unreal's,
Y to starboard, which Blender draws mirrored: docs/shipkit-9). The light is a clear afternoon: a sun 50 degrees up on the
starboard quarter and the sky, through AgX as the game's renders are. --save keeps the dressed .blend (for a look in
Blender, or for the export).
"""
import json
import math
import os
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import weathering  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
BLEND, OUT = ARGS[0], ARGS[1]


def opt(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


# camera eye, the point looked at, horizontal field of view (deg); what each view is for
VIEWS = {
    "waterline": ((-5.0, 11.5, 1.0), (-1.0, 6.6, 0.4), 55.0,
                  "the side at the waterline amidships from a boat alongside: copper, the main wale, the black side"),
    "chains": ((-8.5, 13.5, 4.6), (-8.5, 6.8, 4.4), 55.0,
               "the main chains: the channel, deadeyes and lanyards, chain plates, the ochre band and the ports"),
    "waist": ((-8.0, -3.6, 6.4), (10.0, 2.6, 4.6), 70.0,
              "the spar deck forward from the quarterdeck: deck, carronades, red bulwarks, rails, the boats, the belfry"),
    "carronade": ((-12.2, 2.0, 5.9), (-10.7, 4.8, 4.9), 50.0,
                  "a carronade on its slide at a crewman's eye: blacking, red ochre, iron, tackle, the rail and bulwark"),
    "quarterdeck": ((-16.5, 2.8, 6.3), (-22.0, -0.4, 4.9), 60.0,
                    "the wheel, binnacle, skylights, capstan and the companion: oak, bronze, iron, tarpaulin"),
    "gallery": ((-34.5, 10.5, 4.6), (-27.5, 5.0, 3.8), 50.0,
                "the starboard quarter gallery and stern: gilt carving, ochre frames, stone-white sashes, black"),
    "bow": ((37.5, 7.0, 6.0), (31.0, 0.5, 6.5), 55.0,
            "the head from the starboard bow: the figure, trailboards, cathead, the bower anchor and its cable"),
    "boats": ((-4.0, -6.0, 9.2), (5.0, 2.0, 5.2), 60.0,
              "the boats on the skid beams over the waist from the main shrouds: their covers, the hammock cloths"),
    "rig": ((6.0, -3.5, 5.8), (-3.0, 5.5, 18.0), 70.0,
            "aloft from the deck: the main course set, the main yard, shrouds and ratlines, the spars and blocks"),
    "sail": ((-1.0, 5.0, 8.0), (-2.6, 3.0, 13.0), 55.0,
             "the main course's foot over the deck: canvas, its cloths, grime and patches, the tarred clew gear"),
}


def look(o, eye, at):
    o.location = Vector(eye)
    o.rotation_euler = (Vector(at) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()


def setup(res, samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = res, res * 9 // 16
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Base Contrast"
    sc.view_settings.exposure = 0.0
    w = bpy.data.worlds.new("WearSky")
    sc.world = w
    w.use_nodes = True
    sky = w.node_tree.nodes.new("ShaderNodeTexSky")
    sky.sun_disc = False
    sky.sun_elevation = math.radians(50)
    sky.sun_rotation = math.radians(225)
    w.node_tree.links.new(sky.outputs[0], w.node_tree.nodes["Background"].inputs[0])
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.12
    sun = bpy.data.lights.new("WearSun", "SUN")
    sun.energy = 2.2
    sun.angle = math.radians(0.6)
    so = bpy.data.objects.new("WearSun", sun)
    sc.collection.objects.link(so)
    # from the starboard quarter (aft and to starboard: the ship's -X, +Y), 50 degrees up
    so.rotation_euler = (Vector((-0.45, 0.45, 0.77)) * -1.0).to_track_quat("-Z", "Y").to_euler()
    cam = bpy.data.cameras.new("WearCam")
    cam.lens_unit = "FOV"
    cam.clip_start = 0.05
    co = bpy.data.objects.new("WearCam", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    return sc, co, so, w


def mode(sc, so, w, m):
    """lit, or albedo/id: no light at all, nothing but the materials' emissions (wear_check measures them)."""
    weathering.albedo_mode(m if m != "lit" else False)
    so.hide_render = m != "lit"
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.12 if m == "lit" else 0.0
    sc.view_settings.view_transform = "AgX" if m == "lit" else "Standard"
    sc.view_settings.look = "AgX - Base Contrast" if m == "lit" else "None"
    sc.cycles.samples = int(opt("--samples", 32)) if m == "lit" else 8
    sc.cycles.use_denoising = m == "lit"
    sc.render.filter_size = 1.5 if m == "lit" else 0.01


def render(sc, path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    from PIL import Image
    Image.open(path).transpose(Image.FLIP_LEFT_RIGHT).save(path)


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    names = weathering.dress("L0")
    os.makedirs(OUT, exist_ok=True)
    sc, co, so, w = setup(int(opt("--res", 960)), int(opt("--samples", 32)))
    if opt("--save"):
        bpy.ops.wm.save_as_mainfile(filepath=opt("--save"))
    views = opt("--views", ",".join(VIEWS)).split(",")
    levels = opt("--levels", ",".join(weathering.LEVEL_IDS)).split(",")
    # wear_ids.json: each dressed material's id code (weathering.material_id: k mod 64, k from 1 in name order)
    json.dump({str(k % 64): m.name for k, m in enumerate(weathering.dressed(), 1)},
              open(os.path.join(OUT, "wear_ids.json"), "w"), indent=1)
    vpath = os.path.join(OUT, "wear_views.json")      # (a run of some views keeps the others' entries)
    shown = json.load(open(vpath))["views"] if os.path.exists(vpath) else {}
    shown.update({v: VIEWS[v][3] for v in views})
    json.dump({"dressed": names, "views": {v: shown[v] for v in VIEWS if v in shown}}, open(vpath, "w"), indent=1)
    lit_only = "--lit-only" in ARGS
    t0 = time.time()
    for v in views:
        eye, at, fov, _ = VIEWS[v]
        co.data.angle = math.radians(fov)
        look(co, eye, at)
        if not lit_only:
            mode(sc, so, w, "id")
            render(sc, os.path.join(OUT, f"wear_{v}_id.png"))
        for lv in levels:
            weathering.apply_level(lv)
            mode(sc, so, w, "lit")
            render(sc, os.path.join(OUT, f"wear_{v}_{lv}.png"))
            if not lit_only:
                mode(sc, so, w, "albedo")
                render(sc, os.path.join(OUT, f"wear_{v}_{lv}_albedo.png"))
        print(f"view {v} done {time.time() - t0:.0f} s", flush=True)
    mode(sc, so, w, "lit")


if __name__ == "__main__":
    main()
