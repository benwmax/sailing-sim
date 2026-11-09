"""Render the hero J/22's hull at the waterline for the five wear levels, before (main's material) and after.

    python3 Tools/texloop/waterline/render_hero.py <j22_hero.blend> <out_dir> [--before old_j22_materials.py] [--samples N]
        [--views close,heel] [--levels L0,L4] [--before-only]

Run with a Python that has the bpy module (pip bpy 5.x). The blend comes from Inputs/j22-hero/build_j22_hero.py (no sails
needed). For each level the hull's GelcoatHull material is rebuilt from a style with that level's wear (Dirt and Time)
and rendered in two views: `close` (about 1 m off the hull at the waterline, the boat out of the water like TX 7295 EC
on her lift, as in Bean's photo) and `heel` (3 m, low, the bottom and the line together). Light: Poly Haven's CC0
kloofendal_overcast_puresky (1k) in the git-ignored Data/Reference/raw/textures/sky/.
"""
import importlib.util
import json
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
HERO = os.path.join(REPO, "Inputs", "j22-hero")
sys.path.insert(0, HERO)
sys.path.insert(0, HERE)
from j22_style import TX7295, make_style  # noqa: E402
import swatch  # noqa: E402

SKY = os.path.join(REPO, "Data", "Reference", "raw", "textures", "sky", "kloofendal_overcast_puresky_1k.hdr")
# the old style keys for "before": each level's wear and care through main's style generator
PRESET_OF = {"L0": ("new", 0.0, 1.0), "L1": ("race", 0.05, 0.9), "L2": ("club", 0.65, 0.35), "L3": ("race", 0.5, 0.9),
             "L4": ("neglected", 0.92, 0.08)}


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def style(level, dirt, time):
    preset, wear, care = PRESET_OF[level]
    st = make_style(7295, preset, overrides=TX7295)
    st["wear"], st["care"] = wear, care
    # main's keys, as its style generator makes them from wear and care (seed jitter off, for a fair before)
    st["hull"]["scum"] = max(0.0, min(1.0, wear * (1.2 - care)))
    st["hull"]["scum_height_m"] = 0.03 + 0.05 * wear
    st["hull"]["bottom_slime"] = max(0.0, min(1.0, wear * (1 - care)))
    st["dirt"], st["time"] = dirt, time
    return st


def scene(samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.device = "CPU"
    sc.view_settings.view_transform = "AgX"
    w = bpy.data.worlds.new("Sky")
    w.use_nodes = True
    nt = w.node_tree
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(SKY)
    nt.links.new(env.outputs[0], nt.nodes["Background"].inputs[0])
    sc.world = w
    # keep only the hull and the keel: the rest of the boat only shades the view
    for o in list(sc.objects):
        if o.name not in ("Hull", "Keel") and o.type != "CAMERA":
            o.hide_render = True
    cam = bpy.data.objects.get("WLCam") or bpy.data.objects.new("WLCam", bpy.data.cameras.new("WLCam"))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam


def aim(cam, eye, target, lens):
    cam.location = eye
    d = [t - e for t, e in zip(target, eye)]
    yaw = math.atan2(d[1], d[0])
    pitch = math.atan2(d[2], math.hypot(d[0], d[1]))
    cam.rotation_euler = (math.pi / 2 + pitch, 0.0, yaw - math.pi / 2)
    cam.data.lens = lens


VIEWS = {
    # (eye, target, lens, resolution), metres in the hull's frame; the -y side (both sides carry the same line)
    "close": ((-0.5, -2.0, 0.08), (-0.5, -0.8, 0.0), 50, (1200, 700)),
    "heel": ((0.2, -2.6, -0.45), (-0.1, -0.8, 0.0), 35, (1200, 700)),
}


def main():
    a = sys.argv[1:]
    blend, out = a[0], a[1]
    before = a[a.index("--before") + 1] if "--before" in a else None
    samples = int(a[a.index("--samples") + 1]) if "--samples" in a else 48
    views = a[a.index("--views") + 1].split(",") if "--views" in a else list(VIEWS)
    only = a[a.index("--levels") + 1].split(",") if "--levels" in a else None
    skip_after = "--before-only" in a
    os.makedirs(out, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc, cam = scene(samples)
    hull = bpy.data.objects["Hull"]
    new = load(os.path.join(HERO, "j22_materials.py"), "j22_materials")
    sys.modules["j22_materials"] = new
    old = load(before, "j22_materials_old") if before else None
    lv, src = swatch.levels()
    log = {"levels_from": src, "renders": []}
    for level, (dirt, time) in lv.items():
        if only and level not in only:
            continue
        st = style(level, dirt, time)
        for tag, mod in (("after", new), ("before", old)):
            if mod is None or (tag == "after" and skip_after):
                continue
            m = mod.gelcoat_hull(st)
            for i, slot in enumerate(hull.material_slots):
                if slot.material and slot.material.name.startswith("GelcoatHull"):
                    hull.material_slots[i].material = m
            for v in views:
                eye, tgt, lens, res = VIEWS[v]
                aim(cam, eye, tgt, lens)
                sc.render.resolution_x, sc.render.resolution_y = res
                path = os.path.join(out, "%s_%s_%s.png" % (tag, level, v))
                sc.render.filepath = path
                bpy.ops.render.render(write_still=True)
                log["renders"].append(path)
                print("rendered", path, flush=True)
    json.dump(log, open(os.path.join(out, "renders.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
