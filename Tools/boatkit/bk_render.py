"""Preview renders for the boat kit (Cycles, CPU-friendly): a studio contact sheet of parts and close-up turntables.

The studio is a grey sweep under a soft key, a rim light and a sky texture for reflections, so bevels and weighted
normals show as the rolling highlights the screenshot bar asks for.
"""
import math
import os

import bpy
from mathutils import Matrix, Vector

SAMPLES = int(os.environ.get("BK_SAMPLES", "48"))


def _engine(w, h):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    world = bpy.data.worlds.new("Studio") if not sc.world else sc.world
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    sky = nt.nodes.new("ShaderNodeTexSky")
    try:
        sky.sky_type = "NISHITA"
    except TypeError:
        pass
    sky.sun_elevation = math.radians(35)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.25
    nt.links.new(sky.outputs[0], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])


def _light(name, kind, loc, target, energy, size):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    if kind == "AREA":
        ld.size = size
    lo = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = loc
    d = Vector(target) - Vector(loc)
    lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return lo


def _camera(loc, target, lens=50):
    cd = bpy.data.cameras.new("Cam")
    cd.lens = lens
    co = bpy.data.objects.new("Cam", cd)
    bpy.context.scene.collection.objects.link(co)
    co.location = loc
    co.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = co
    return co


def _floor(z, size):
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size)
    me = bpy.data.meshes.new("Floor")
    bm.to_mesh(me)
    m = bpy.data.materials.new("FloorMat")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.32, 0.33, 0.34, 1)
    m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.7
    me.materials.append(m)
    ob = bpy.data.objects.new("Floor", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location.z = z
    return ob


def _bounds(ob):
    pts = [ob.matrix_basis @ v.co for v in ob.data.vertices]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


def contact_sheet(parts, path, cols=6, tile=(420, 320)):
    """Render each part alone in the studio (scaled to a 1 m bound so the light is the same for all), from a
    three-quarter view, and tile the renders with their names into one sheet. The tiles stay in _tiles; without PIL in
    Blender's Python (the PC's Blender) the sheet is left to a system Python."""
    tmp = os.path.join(os.path.dirname(path), "_tiles")
    os.makedirs(tmp, exist_ok=True)
    _engine(*tile)
    _floor(0, 40)
    _light("Key", "AREA", (-2.2, -3.0, 3.6), (0, 0, 0.3), 700, 2.5)
    _light("Rim", "AREA", (3.0, 2.6, 1.6), (0, 0, 0.3), 260, 1.5)
    _light("Fill", "AREA", (2.5, -3.5, 0.8), (0, 0, 0.3), 90, 3.0)
    _camera((2.1, -2.6, 1.7), (0, 0, 0.28), 60)
    tiles = []
    for name, ob in parts:
        ob.hide_render = True
        for c in ob.children:
            c.hide_render = True
    for name, ob in parts:
        lo, hi = _bounds(ob)
        size = max(hi - lo)
        c = (lo + hi) / 2
        keep = ob.matrix_world.copy()
        ob.matrix_world = Matrix.Scale(0.9 / max(size, 1e-3), 4) @ Matrix.Translation((-c.x, -c.y, -lo.z)) @ keep
        ob.hide_render = False
        p = os.path.join(tmp, f"{name}.png")
        bpy.context.scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        ob.hide_render = True
        ob.matrix_world = keep
        tiles.append((name, p))
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print(f"Kit: {len(tiles)} tiles -> {tmp} (no PIL here for the sheet)")
        return
    rows = math.ceil(len(tiles) / cols)
    sheet = Image.new("RGB", (cols * tile[0], rows * (tile[1] + 28)), (24, 26, 28))
    d = ImageDraw.Draw(sheet)
    for i, (name, p) in enumerate(tiles):
        r, k = divmod(i, cols)
        sheet.paste(Image.open(p).convert("RGB"), (k * tile[0], r * (tile[1] + 28)))
        d.text((k * tile[0] + 10, r * (tile[1] + 28) + tile[1] + 7), name, fill=(220, 222, 225))
    sheet.save(path)
    print(f"Kit: catalogue -> {path}")


def closeup(objs, path, view=(1, -1, 0.7), lens=85, w=960, h=640, floor=True, fill=1.0):
    lo = Vector((1e9, 1e9, 1e9))
    hi = -lo
    for o in objs:
        if o.type != "MESH":
            continue
        a, b = _bounds(o)
        lo = Vector([min(lo[i], a[i]) for i in range(3)])
        hi = Vector([max(hi[i], b[i]) for i in range(3)])
    c = (lo + hi) / 2
    size = max(hi - lo)
    _engine(w, h)
    if floor:
        _floor(lo.z, size * 20)
    d = Vector(view).normalized()
    dist = size * 2.2 * (lens / 50) / fill
    _light("Key", "AREA", c + Vector((-1, -1.2, 1.6)) * size * 3, c, 60 * size ** 2 * 400, size * 2)
    _light("Rim", "AREA", c + Vector((1.5, 1.2, 0.8)) * size * 3, c, 25 * size ** 2 * 400, size * 1.5)
    _camera(c + d * dist, c, lens)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
