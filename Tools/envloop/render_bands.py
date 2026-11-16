"""Standard renders for the environment loop (docs/env-loop/README.md, step 5): any asset at 3, 15 and 60 m from eye
height, in midday sun, low sun and overcast, with a 1.75 m scale pole beside it and, if given, the reference photo.

    python3 Tools/envloop/render_bands.py --asset model.glb|.fbx|.obj|.blend --out DIR [--name window-a]
                                          [--builder script.py] [--ref photo.jpg] [--ground grass.png --ground-tile 2.0]
                                          [--res 960x540] [--samples 32] [--eye 1.6] [--distances 3,15,60]

Needs Python with the bpy module (pip install bpy==5.1.2, as Tools/shoreloop/rocks/render_rocks.py). The asset is
imported as is (metres, Z up; FBX from our Blender builders imports at their scale), or --builder runs a script that
builds it into the empty scene (it may read ENV_RENDER_ARGS). The camera looks at the asset's bounding-box centre
from the asset's front (-Y side, the builders' convention), distances counted from that face, unless --yaw turns it. Same lens as the game's Drone capture
(80 degrees across). Writes DIR/<name>_<light>_<d>m.png, DIR/<name>_bands.jpg (the sheet) and DIR/<name>_bands.json.
"""
import argparse
import json
import math
import os
import runpy
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import bpy  # noqa: E402

LIGHTS = {
    # elevation deg, azimuth deg (from the camera's right, round behind), sun W/m2, sky RGB strength
    "midday": (68.0, 40.0, 4.0, (0.45, 0.6, 1.0), 1.0),
    "low": (11.0, 70.0, 3.0, (0.55, 0.55, 0.75), 0.6),
    "overcast": (None, None, 0.0, (0.85, 0.87, 0.9), 1.6),
}


def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"


def import_asset(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".glb" or ext == ".gltf":
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path, forward_axis="NEGATIVE_Y", up_axis="Z")
    elif ext == ".blend":
        with bpy.data.libraries.load(path) as (src, dst):
            dst.objects = src.objects
        for o in dst.objects:
            if o is not None:
                bpy.context.scene.collection.objects.link(o)
    else:
        raise SystemExit("unknown asset type " + ext)


def bounds(objs):
    lo, hi = np.full(3, 1e9), np.full(3, -1e9)
    for o in objs:
        if o.type != "MESH":
            continue
        for c in o.bound_box:
            w = o.matrix_world @ __import__("mathutils").Vector(c)
            lo, hi = np.minimum(lo, w), np.maximum(hi, w)
    return lo, hi


def material(name, colour, rough=0.8, image=None, tile=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*colour, 1.0)
    b.inputs["Roughness"].default_value = rough
    if image:
        nt = m.node_tree
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(image)
        coord = nt.nodes.new("ShaderNodeTexCoord")
        mapping = nt.nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (1.0 / tile, 1.0 / tile, 1.0)
        nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
        nt.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    return m


def stage(lo, hi, ground, ground_tile):
    bpy.ops.mesh.primitive_plane_add(size=400.0, location=(0, 0, min(lo[2], 0.0)))
    g = bpy.context.object
    g.name = "ground"
    g.data.materials.append(material("ground", (0.18, 0.18, 0.18), 0.9, ground, ground_tile))
    # scale pole: 1.75 m, banded every 0.25 m, beside the asset
    x = hi[0] + 1.0
    for i in range(7):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=0.25, location=(x, lo[1], min(lo[2], 0.0) + 0.125 + 0.25 * i))
        bpy.context.object.data.materials.append(material("pole%d" % (i % 2), (0.8, 0.1, 0.05) if i % 2 else (0.9, 0.9, 0.9), 0.5))


def light(kind):
    el, az, sun, sky, sky_s = LIGHTS[kind]
    w = bpy.data.worlds.new("w")
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*sky, 1.0)
    bg.inputs["Strength"].default_value = sky_s
    for o in [o for o in bpy.data.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o)
    if sun:
        ld = bpy.data.lights.new("sun", "SUN")
        ld.energy = sun
        ld.angle = math.radians(0.53)
        ob = bpy.data.objects.new("sun", ld)
        bpy.context.scene.collection.objects.link(ob)
        ob.rotation_euler = (math.radians(90 - el), 0.0, math.radians(az))


def camera(target, d, eye, yaw_deg):
    cd = bpy.data.cameras.new("cam")
    cd.sensor_fit = "HORIZONTAL"
    cd.angle = math.radians(80.0)
    cd.clip_end = 2000.0
    ob = bpy.data.objects.new("cam", cd)
    bpy.context.scene.collection.objects.link(ob)
    a = math.radians(yaw_deg)
    pos = np.array([target[0] - math.sin(a) * d, target[1] - math.cos(a) * d, eye])
    ob.location = pos
    v = np.array(target) - pos
    pitch = math.atan2(v[2], math.hypot(v[0], v[1]))
    head = math.atan2(v[0], v[1])
    ob.rotation_euler = (math.pi / 2 + pitch, 0.0, -head)
    bpy.context.scene.camera = ob
    return ob


def main():
    argv = sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset")
    ap.add_argument("--builder")
    ap.add_argument("--out", required=True)
    ap.add_argument("--name")
    ap.add_argument("--ref")
    ap.add_argument("--ground")
    ap.add_argument("--ground-tile", type=float, default=2.0)
    ap.add_argument("--res", default="960x540")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--eye", type=float, default=1.6)
    ap.add_argument("--yaw", type=float, default=0.0)
    ap.add_argument("--distances", default="3,15,60")
    a = ap.parse_args(argv)
    name = a.name or os.path.splitext(os.path.basename(a.asset or a.builder))[0]
    dists = [float(v) for v in a.distances.split(",")]
    W, H = (int(v) for v in a.res.split("x"))
    os.makedirs(a.out, exist_ok=True)
    reset()
    if a.builder:
        os.environ["ENV_RENDER_ARGS"] = json.dumps(vars(a))
        runpy.run_path(a.builder, run_name="__main__")
    else:
        import_asset(a.asset)
    objs = [o for o in bpy.data.objects if o.type == "MESH"]
    lo, hi = bounds(objs)
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)
    stage(lo, hi, a.ground, a.ground_tile)
    # distances count from the asset's front face (its -Y side), at the middle of its height, as a bank or a wall is
    # measured from the boat
    target = [(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2]
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = a.samples
    sc.cycles.use_denoising = False
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.view_settings.view_transform = "AgX"
    shots = {}
    for kind in LIGHTS:
        light(kind)
        for d in dists:
            camera(target, d, a.eye, a.yaw)
            p = os.path.join(a.out, "%s_%s_%gm.png" % (name, kind, d))
            sc.render.filepath = p
            bpy.ops.render.render(write_still=True)
            shots["%s_%gm" % (kind, d)] = p
    # the sheet: rows = light, columns = distance, plus the reference
    T = 420
    th = int(T * H / W)
    cols = len(dists) + (1 if a.ref else 0)
    sheet = Image.new("RGB", (110 + cols * (T + 8), 36 + len(LIGHTS) * (th + 26)), (248, 248, 246))
    dr = ImageDraw.Draw(sheet)
    dr.text((8, 8), "%s: %d triangles, size %.2f x %.2f x %.2f m" % (name, tris, *(hi - lo)), fill=(0, 0, 0), font=font(16))
    for i, kind in enumerate(LIGHTS):
        y = 36 + i * (th + 26)
        dr.text((8, y + th // 2), kind, fill=(40, 40, 40), font=font(14))
        for j, d in enumerate(dists):
            im = Image.open(shots["%s_%gm" % (kind, d)]).convert("RGB").resize((T, th), Image.LANCZOS)
            sheet.paste(im, (110 + j * (T + 8), y))
            dr.text((110 + j * (T + 8), y + th + 4), "%g m" % d, fill=(60, 60, 60), font=font(13))
        if a.ref and i == 0:
            im = Image.open(a.ref).convert("RGB")
            im.thumbnail((T, th))
            sheet.paste(im, (110 + len(dists) * (T + 8), y))
            dr.text((110 + len(dists) * (T + 8), y + th + 4), "reference", fill=(60, 60, 60), font=font(13))
    sp = os.path.join(a.out, name + "_bands.jpg")
    sheet.save(sp, quality=88)
    json.dump(dict(name=name, triangles=tris, size_m=(hi - lo).round(3).tolist(), shots=shots, sheet=sp, eye_m=a.eye,
                   lens_deg=80, distances_m=dists), open(os.path.join(a.out, name + "_bands.json"), "w"), indent=1)
    print(sp)


if __name__ == "__main__":
    main()
