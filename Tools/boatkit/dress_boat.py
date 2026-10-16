"""Dress a boat from its layout and character sheet, then export the placements and preview renders.

  python3 Tools/boatkit/dress_boat.py <layout.json> <character.json> <out dir> [--render] [--views a,b]
  (or blender -b --factory-startup -P Tools/boatkit/dress_boat.py -- ...)

Steps: import the boat's hull FBX and strip the fittings baked into it (faces whose slot is not in the layout's
keep_hull_slots), so the kit's parts replace them; import the spars and rudder for context; place every kit part from
the layout (bk_layout); add the character sheet's owner touches (bk_touches); write placements.json and the merged
SM_<Boat>_Kit.fbx; render the review views.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import bpy  # noqa: E402  (before bmesh: the bpy module sets up Blender's own modules)
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import bk_geom as G  # noqa: E402
import bk_layout as L  # noqa: E402
import bk_render as R  # noqa: E402
import bk_touches as T  # noqa: E402


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    opts = {}
    pos = []
    i = 0
    while i < len(a):
        if a[i] in ("--views", "--camera", "--photo"):
            opts[a[i][2:]] = a[i + 1]
            i += 2
        else:
            if not a[i].startswith("--"):
                pos.append(a[i])
            i += 1
    views = opts["views"].split(",") if "views" in opts else None
    return pos[0], pos[1], os.path.abspath(pos[2]), "--render" in a, views, opts.get("camera"), opts.get("photo")


def import_fbx(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()
    for o in new:
        if o.type == "MESH":
            o.data.transform(o.matrix_world)
            o.matrix_world = o.matrix_world.Identity(4)
    return new


def strip_fittings(ob, keep):
    me = ob.data
    keep_idx = {i for i, m in enumerate(me.materials) if m and m.name.split(".")[0] in keep}
    bm = bmesh.new()
    bm.from_mesh(me)
    dead = [f for f in bm.faces if f.material_index not in keep_idx]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(me)
    bm.free()
    return len(dead)


HERO_SLOT_MAP = {"RubRail": "Rubrail", "Gelcoat": "Deck", "HatchAcrylic": "CabinWindow", "BlackPlastic": "BlackPlastic",
                 "Stainless": "Stainless", "Chrome": "Stainless", "Aluminium": "Aluminium", "CastAlu": "Aluminium",
                 "MastAlu": "Aluminium"}


def textured(name, tex_dir, group):
    """A preview material from the hero bake's texture set (T_J22H_<group>_D/_R/_N on the first UV map)."""
    m = bpy.data.materials.new(f"Preview_{group}")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]

    def img(suffix, colour):
        p = os.path.join(tex_dir, f"T_J22H_{group}_{suffix}.png")
        if not os.path.exists(p):
            return None
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(p, check_existing=True)
        n.image.colorspace_settings.name = "sRGB" if colour else "Non-Color"
        return n
    d, r, nrm = img("D", True), img("R", False), img("N", False)
    if d:
        nt.links.new(d.outputs["Color"], b.inputs["Base Color"])
    if r:
        nt.links.new(r.outputs["Color"], b.inputs["Roughness"])
    if nrm:
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(nrm.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Coat Weight"].default_value = 0.3 if group == "Hull" else 0.0
    return m


def preview_materials(objs, tex_dir):
    """Swap the imported FBX's untextured materials for previews: the hero bake's textures where they exist, the game
    library's colours (MI_Boat_*) elsewhere."""
    import bk_materials as BM
    for o in objs:
        if o.type != "MESH":
            continue
        for i, m in enumerate(o.data.materials):
            key = m.name.split(".")[0] if m else ""
            if key.startswith("J22H_") and os.path.exists(os.path.join(tex_dir, f"T_{key}_D.png")):
                o.data.materials[i] = textured(key, tex_dir, key[len("J22H_"):])
            else:
                o.data.materials[i] = BM.get(HERO_SLOT_MAP.get(key, "Aluminium" if "Alu" in key or "Mast" in key else "Deck"))


VIEWS = {
    # name: (camera position, target, lens) in boat metres, chosen to match the hero review renders
    "deck_quarter": ((-5.6, -3.6, 2.9), (-0.6, 0.0, 0.7), 35),
    "cockpit_aft": ((-4.4, -0.9, 1.75), (-1.2, 0.0, 0.55), 28),
    "foredeck": ((3.9, -1.9, 2.1), (1.2, 0.0, 1.0), 35),
    "winch_close": ((-1.05, -1.05, 1.40), (-0.42, -0.47, 1.0), 50),
    "transom": ((-5.2, 1.6, 1.1), (-3.5, 0.3, 0.45), 40),
}


def outdoor(w, h):
    sc = bpy.context.scene
    R._engine(w, h)
    world = sc.world
    nt = world.node_tree
    nt.nodes["Background"].inputs["Strength"].default_value = 0.6
    sky = [n for n in nt.nodes if n.type == "TEX_SKY"][0]
    sky.sun_elevation = math.radians(38)
    sky.sun_rotation = math.radians(150)
    sd = bpy.data.lights.new("Sun", "SUN")
    sd.energy = 6.0
    sd.angle = math.radians(0.6)
    so = bpy.data.objects.new("Sun", sd)
    sc.collection.objects.link(so)
    so.rotation_euler = (math.radians(52), 0, math.radians(150 + 90))
    sc.view_settings.exposure = -3.2


def render_views(out, views):
    for name in views:
        loc, tgt, lens = VIEWS[name]
        for c in [o for o in bpy.data.objects if o.type == "CAMERA"]:
            bpy.data.objects.remove(c, do_unlink=True)
        R._camera(loc, tgt, lens)
        bpy.context.scene.render.filepath = os.path.join(out, f"{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Dress: view {name}")


def main():
    layout_path, char_path, out, render, views, camera, photo = args()
    os.makedirs(out, exist_ok=True)
    layout = json.load(open(layout_path))
    character = json.load(open(char_path))
    G.clear_scene()
    hull = [o for o in import_fbx(os.path.join(REPO, layout["hull_fbx"])) if o.type == "MESH"][0]
    n = strip_fittings(hull, set(layout["keep_hull_slots"]))
    print(f"Dress: hull {hull.name}, stripped {n} fitting faces")
    fbx_dir = os.path.dirname(os.path.join(REPO, layout["hull_fbx"]))
    for extra in layout.get("context_fbx", ["SM_J22H_Mast.fbx", "SM_J22H_Boom.fbx", "SM_J22H_Rudder.fbx"]):
        p = os.path.join(fbx_dir, extra)
        if os.path.exists(p):
            import_fbx(p)
    tex_dir = os.path.join(os.path.dirname(fbx_dir), "textures")
    preview_materials(list(bpy.data.objects), tex_dir)
    origins = json.load(open(os.path.join(REPO, layout["sockets"]))).get("origins", {})
    for o in list(bpy.data.objects):
        key = o.name.split(".")[0]
        if key in origins and key != hull.name.split(".")[0]:
            v = origins[key]
            o.location = (v[0] / 100, -v[1] / 100, v[2] / 100)
    sockets = L.load_sockets(os.path.join(REPO, layout["sockets"]))
    bvh = L.bvh_of([hull])
    placed, records = L.place(layout, sockets, bvh)
    touches = T.apply(character, sockets, bvh, placed)
    records += touches
    L.write_placements(records, os.path.join(out, "placements.json"))
    print(f"Dress: {len(placed)} kit parts, {len(touches)} owner touches for {character['id']}")
    if render:
        outdoor(1280, 800)
        fl = R._floor(0.0, 400)   # a dark, glossy stand-in for Ray Hubbard's olive water (lesson photo IMG_9272)
        b = fl.data.materials[0].node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.020, 0.028, 0.020, 1)
        b.inputs["Roughness"].default_value = 0.12
        if camera:
            render_match(out, camera, photo)
        else:
            render_views(out, views or list(VIEWS))


def render_match(out, camera_json, photo):
    """The photo match loop's render: the solved camera, the photo's resolution, a transparent background so the
    compare page can outline the boat over the photo."""
    cam = json.load(open(camera_json))
    for c in [o for o in bpy.data.objects if o.type == "CAMERA"]:
        bpy.data.objects.remove(c, do_unlink=True)
    for o in [o for o in bpy.data.objects if o.name == "Floor"]:
        o.hide_render = True
    co = R._camera((0, 0, 0), (1, 0, 0), cam["lens_mm"])
    co.location = cam["location"]
    co.rotation_mode = "QUATERNION"
    co.rotation_quaternion = cam["rotation_quaternion"]
    co.data.sensor_fit = "HORIZONTAL"
    co.data.sensor_width = cam["sensor_width_mm"]
    w, h = cam["resolution"]
    s = min(1.0, 1600 / w)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = int(w * s), int(h * s)
    sc.render.film_transparent = True
    stem = os.path.splitext(os.path.basename(cam["photo"]))[0]
    path = os.path.join(out, f"match_{stem}.png")
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"Dress: match render {path}")
    if photo:
        sys.path.insert(0, os.path.join(HERE, "photomatch"))
        import compare
        compare.compose(photo, path, os.path.join(out, f"compare_{stem}.jpg"))


if __name__ == "__main__":
    main()
