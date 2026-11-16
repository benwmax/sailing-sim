"""Track D's standard renders (environment loop step 5): one tree at 3, 15 and 60 m in midday sun, low sun and overcast,
in Cycles, with the game's materials mirrored closely enough to judge shape, leaf size, bark and the crown's inside.

Besides the picture it measures, per view:
  core   - share of the crown's pixels where the first thing hit is the opaque core ball (V6's "hollow" crown fill):
           the dark lumps Bean sees up close. 0 when the tree has no core.
  layers - mean number of leaf-card surfaces a ray crosses before something opaque (or the sky), over the crown's
           pixels: the masked overdraw the game pays in its depth pass. The current crowns' core was added to cut it.

The tree comes from either generator:
  --gen v6   Tools/blender/build_trees.py as it is on main (the "before")
  --gen d    Tools/envloop/trees/build_trees_d.py (Track D)

Run with Blender (blender -b --factory-startup -P render_trees.py -- <args>) or the bpy module (python render_trees.py <args>):
  --species PostOak --variant 0 --gen d --dist 3,15,60 --light midday,low,overcast --out <dir> [--size 960x600]
  [--samples 32] [--atlas <T_LeafAtlas.png>] [--no-metrics]
Writes <out>/<gen>_<species>_<variant>_<dist>m_<light>.jpg and appends rows to <out>/metrics.csv.
"""
import argparse
import csv
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "Tools", "blender"))
sys.path.insert(0, HERE)


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser()
    p.add_argument("--species", default="PostOak")
    p.add_argument("--variant", type=int, default=0)
    p.add_argument("--gen", default="d", choices=("v6", "d"))
    p.add_argument("--dist", default="3,15,60")
    p.add_argument("--light", default="midday,low,overcast")
    p.add_argument("--out", required=True)
    p.add_argument("--size", default="960x600")
    p.add_argument("--samples", type=int, default=32)
    p.add_argument("--atlas", default="")
    p.add_argument("--season", default="summer", choices=("summer", "winter"))
    p.add_argument("--no-metrics", action="store_true")
    p.add_argument("--core", default="", help="d generator: crown fill override (none, shell, v6)")
    return p.parse_args(argv)


# ----------------------------------------------------------------------------------------------------------------- tree

def build_tree(args):
    """Returns (object, height, crown radius, crown centre z) of the tree built at the origin."""
    if args.gen == "v6":
        sys.argv = [sys.argv[0], "--", os.path.join(args.out, "_unused")]
        import build_trees as bt
        spec = bt.SPECIES[args.species]
        seed = sum(ord(ch) for ch in args.species) * 31 + args.variant * 7919
        b = {"cone": bt.cone_tree, "stemmed": bt.stemmed_tree}.get(spec["kind"], bt.broad_tree)(args.species, spec, seed)
        far = bt.far_version(b, "far", seed)
        bt.hollow(b, far.blobs, seed)
        obj, tris = bt.finish(b, f"SM_{args.species}_{args.variant}")
        bark_set = None
        bpy.data.objects.remove(bpy.data.objects["far"]) if "far" in bpy.data.objects else None
        far.bm.free()
    else:
        import build_trees_d as bd
        if args.core:
            bd.CORE_MODE = args.core
        obj, tris, info = bd.build(args.species, args.variant)
        bark_set = info.get("bark")
    xs = [v.co for v in obj.data.vertices]
    h = max(v.z for v in xs)
    r = max(math.hypot(v.x, v.y) for v in xs)
    zs = sorted(v.z for v in xs)
    print(f"Render: {obj.name} {tris} tris, height {h:.1f} m, reach {r:.1f} m")
    return obj, tris, h, r, bark_set


# ------------------------------------------------------------------------------------------------------------ materials

def tex_node(nt, path, colorspace="sRGB"):
    n = nt.nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = colorspace
    n.image = img
    return n


def leaf_material(atlas, normal_atlas, flat_id=None):
    """M_TreeLeaves mirrored: atlas colour tinted per card (vertex B), lit through (two-sided foliage), alpha-tested."""
    m = bpy.data.materials.new("Leaves_r")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tex = tex_node(nt, atlas)
    tex.interpolation = "Cubic"
    attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Col"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(attr.outputs["Color"], sep.inputs[0])
    # Per-card tint as TREE_LOOK's first line: lerp((0.82,0.86,0.78), (1.15,1.1,0.9), VC.b).
    mix_t = nt.nodes.new("ShaderNodeMix")
    mix_t.data_type = "RGBA"
    mix_t.inputs["A"].default_value = (0.82, 0.86, 0.78, 1)
    mix_t.inputs["B"].default_value = (1.15, 1.1, 0.9, 1)
    nt.links.new(sep.outputs["Blue"], mix_t.inputs["Factor"])
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(tex.outputs["Color"], mul.inputs["A"])
    nt.links.new(mix_t.outputs["Result"], mul.inputs["B"])
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.62
    nt.links.new(mul.outputs["Result"], bsdf.inputs["Base Color"])
    if normal_atlas and os.path.exists(normal_atlas):
        tn = tex_node(nt, normal_atlas, "Non-Color")
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    trans = nt.nodes.new("ShaderNodeBsdfTranslucent")
    sss = nt.nodes.new("ShaderNodeMix")
    sss.data_type = "RGBA"
    sss.blend_type = "MULTIPLY"
    sss.inputs["Factor"].default_value = 1.0
    sss.inputs["B"].default_value = (0.55, 0.65, 0.3, 1)
    nt.links.new(mul.outputs["Result"], sss.inputs["A"])
    nt.links.new(sss.outputs["Result"], trans.inputs["Color"])
    lit = nt.nodes.new("ShaderNodeMixShader")
    lit.inputs["Fac"].default_value = 0.35
    nt.links.new(bsdf.outputs[0], lit.inputs[1])
    nt.links.new(trans.outputs[0], lit.inputs[2])
    surface = lit.outputs[0]
    if flat_id is not None:
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = flat_id
        surface = em.outputs[0]
    # Masked: opacity > 0.5 (the game's alpha test), otherwise fully transparent.
    gt = nt.nodes.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.5
    nt.links.new(tex.outputs["Alpha"], gt.inputs[0])
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    cut = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(gt.outputs[0], cut.inputs["Fac"])
    nt.links.new(clear.outputs[0], cut.inputs[1])
    nt.links.new(surface, cut.inputs[2])
    nt.links.new(cut.outputs[0], out.inputs["Surface"])
    return m


def core_material(flat_id=None):
    """M_TreeCrown for a near tree's core (vertex alpha 0): dark leafy green, dappled, x0.32 for the deep inside."""
    m = bpy.data.materials.new("Core_r")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if flat_id is not None:
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = flat_id
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        return m
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 2.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.045 * 0.32, 0.085 * 0.32, 0.03 * 0.32, 1)
    ramp.color_ramp.elements[1].color = (0.10 * 0.32, 0.16 * 0.32, 0.06 * 0.32, 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs[0])
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.75
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.8
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return m


BARK_DIM = (0.62, 0.6, 0.58)


def bark_material(bark_set, flat_id=None):
    """M_TreeBark: the scan laid twice round the trunk and once a metre (UV x (2, 0.5)), dimmed as in the game; Track D's
    sets carry their own tiling (bark plates' real size) and tint."""
    m = bpy.data.materials.new("Bark_r")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if flat_id is not None:
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = flat_id
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        return m
    if bark_set is None:
        base = os.path.join(REPO, "Inputs", "trees", "ambientcg", "Bark001", "Bark001_1K-JPG_")
        bark_set = dict(color=base + "Color.jpg", normal=base + "NormalDX.jpg", rough=base + "Roughness.jpg", uv=(2.0, 0.5), tint=BARK_DIM, normal_dx=True)
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    sc = nt.nodes.new("ShaderNodeVectorMath")
    sc.operation = "MULTIPLY"
    sc.inputs[1].default_value = (bark_set["uv"][0], bark_set["uv"][1], 1.0)
    nt.links.new(uv.outputs["UV"], sc.inputs[0])
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tc = tex_node(nt, bark_set["color"])
    nt.links.new(sc.outputs[0], tc.inputs["Vector"])
    tint = nt.nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.inputs["Factor"].default_value = 1.0
    tint.inputs["B"].default_value = (*bark_set.get("tint", BARK_DIM), 1)
    nt.links.new(tc.outputs["Color"], tint.inputs["A"])
    nt.links.new(tint.outputs["Result"], bsdf.inputs["Base Color"])
    if bark_set.get("normal") and os.path.exists(bark_set["normal"]):
        tn = tex_node(nt, bark_set["normal"], "Non-Color")
        nt.links.new(sc.outputs[0], tn.inputs["Vector"])
        src = tn.outputs["Color"]
        if bark_set.get("normal_dx"):
            # DirectX normals: green down. Blender wants OpenGL's.
            sep = nt.nodes.new("ShaderNodeSeparateColor")
            comb = nt.nodes.new("ShaderNodeCombineColor")
            inv = nt.nodes.new("ShaderNodeMath")
            inv.operation = "SUBTRACT"
            inv.inputs[0].default_value = 1.0
            nt.links.new(src, sep.inputs[0])
            nt.links.new(sep.outputs["Green"], inv.inputs[1])
            nt.links.new(sep.outputs["Red"], comb.inputs["Red"])
            nt.links.new(inv.outputs[0], comb.inputs["Green"])
            nt.links.new(sep.outputs["Blue"], comb.inputs["Blue"])
            src = comb.outputs[0]
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(src, nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if bark_set.get("rough") and os.path.exists(bark_set["rough"]):
        tr = tex_node(nt, bark_set["rough"], "Non-Color")
        nt.links.new(sc.outputs[0], tr.inputs["Vector"])
        nt.links.new(tr.outputs["Color"], bsdf.inputs["Roughness"])
    else:
        bsdf.inputs["Roughness"].default_value = 0.85
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return m


def layers_material(kind):
    """Metrics pass: leaves fully see-through, every opaque surface emits the number of leaf layers crossed so far
    (Light Path's transparent depth) in red and its kind in green (0.25 bark, 0.5 core, 1 ground); sky is black."""
    m = bpy.data.materials.new(f"Layers_{kind}")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if kind == "leaf":
        # A crossing counts only where the card's alpha passes (so does the game's depth pass: cut texels cost too,
        # but a crown pixel behind an opaque leaf texel is hidden). Visible leaf texels emit blue = 1 and stop.
        atlas = LAYER_ATLAS
        tex = tex_node(nt, atlas)
        gt = nt.nodes.new("ShaderNodeMath")
        gt.operation = "GREATER_THAN"
        gt.inputs[1].default_value = 0.5
        nt.links.new(tex.outputs["Alpha"], gt.inputs[0])
        lp = nt.nodes.new("ShaderNodeLightPath")
        comb = nt.nodes.new("ShaderNodeCombineColor")
        div = nt.nodes.new("ShaderNodeMath")
        div.operation = "DIVIDE"
        div.inputs[1].default_value = 64.0
        nt.links.new(lp.outputs["Transparent Depth"], div.inputs[0])
        nt.links.new(div.outputs[0], comb.inputs["Red"])
        # Green: 0.75 on a card, 0.6 on the shell (vertex alpha 0: the crown's inside).
        vc = nt.nodes.new("ShaderNodeVertexColor")
        vc.layer_name = "Col"
        g = nt.nodes.new("ShaderNodeMapRange")
        g.inputs["To Min"].default_value = 0.6
        g.inputs["To Max"].default_value = 0.75
        nt.links.new(vc.outputs["Alpha"], g.inputs["Value"])
        nt.links.new(g.outputs["Result"], comb.inputs["Green"])
        comb.inputs["Blue"].default_value = 1.0
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(comb.outputs[0], em.inputs["Color"])
        clear = nt.nodes.new("ShaderNodeBsdfTransparent")
        cut = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(gt.outputs[0], cut.inputs["Fac"])
        nt.links.new(clear.outputs[0], cut.inputs[1])
        nt.links.new(em.outputs[0], cut.inputs[2])
        nt.links.new(cut.outputs[0], out.inputs["Surface"])
        return m
    lp = nt.nodes.new("ShaderNodeLightPath")
    div = nt.nodes.new("ShaderNodeMath")
    div.operation = "DIVIDE"
    div.inputs[1].default_value = 64.0
    nt.links.new(lp.outputs["Transparent Depth"], div.inputs[0])
    comb = nt.nodes.new("ShaderNodeCombineColor")
    nt.links.new(div.outputs[0], comb.inputs["Red"])
    comb.inputs["Green"].default_value = {"bark": 0.25, "core": 0.5, "ground": 0.0}[kind]
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(comb.outputs[0], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


LAYER_ATLAS = ""


# ---------------------------------------------------------------------------------------------------------------- scene

def setup_scene(args):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    w, h = (int(x) for x in args.size.split("x"))
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.cycles.samples = args.samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.cycles.transparent_max_bounces = 64
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "None"
    # Ground: a mown-lawn grey-green, big enough for the 60 m view.
    bpy.ops.mesh.primitive_plane_add(size=600, location=(0, 0, 0))
    ground = bpy.context.active_object
    gm = bpy.data.materials.new("Ground_r")
    gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.09, 0.11, 0.05, 1)
    gm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.95
    ground.data.materials.append(gm)
    return ground


def set_light(kind):
    sc = bpy.context.scene
    world = sc.world or bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    for o in [o for o in bpy.data.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o)
    if kind == "overcast":
        bg.inputs["Color"].default_value = (0.75, 0.78, 0.82, 1)
        bg.inputs["Strength"].default_value = 1.6
        sc.view_settings.exposure = 0.0
    else:
        elev = 62.0 if kind == "midday" else 9.0
        azim = 200.0 if kind == "midday" else 250.0   # from the camera's side-front: the crown half lit
        sky = nt.nodes.new("ShaderNodeTexSky")
        sky.sky_type = "MULTIPLE_SCATTERING" if "MULTIPLE_SCATTERING" in [e.identifier for e in sky.bl_rna.properties["sky_type"].enum_items] else "NISHITA"
        sky.sun_disc = False
        sky.sun_elevation = math.radians(elev)
        sky.sun_rotation = math.radians(azim)
        nt.links.new(sky.outputs[0], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 0.35
        sun = bpy.data.lights.new("Sun", "SUN")
        sun.energy = 4.0 if kind == "midday" else 2.2
        sun.color = (1.0, 0.97, 0.92) if kind == "midday" else (1.0, 0.72, 0.48)
        sun.angle = math.radians(0.53)
        so = bpy.data.objects.new("Sun", sun)
        so.rotation_euler = (math.radians(90 - elev), 0, math.radians(azim + 90))
        bpy.context.scene.collection.objects.link(so)
        sc.view_settings.exposure = 0.0 if kind == "midday" else 0.6
    nt.links.new(bg.outputs[0], out.inputs["Surface"])


def place_camera(dist, h, reach, trunk_r=0.3):
    """`dist` m from the crown's near edge (3 m: under the outer limbs, looking up into the crown), eye 1.6 m up (a
    sailor in a small boat or on the bank), aimed at the crown's middle; the lens frames the whole tree from 15 m on."""
    sc = bpy.context.scene
    cam = bpy.data.cameras.new("Cam")
    cam.lens_unit = "FOV"
    cam.clip_start = 0.05
    co = bpy.data.objects.new("Cam", cam)
    sc.collection.objects.link(co)
    x = -(reach + dist)
    eye = Vector((x, -0.15 * (reach + dist), 1.6))
    if dist == 0:
        # Bark at arm's length: 0.8 m from the trunk's surface, chest height, a 45 deg lens (the reference photos' view).
        eye = Vector((-(trunk_r + 0.8), -0.1, 1.35))
        target = Vector((0, 0, 1.3))
        cam.angle = math.radians(45)
    elif dist <= 5:
        target = Vector((0, 0, h * 0.55))
        cam.angle = math.radians(75)
    else:
        target = Vector((0, 0, h * 0.45))
        span = max(h, 2 * reach) * 1.25
        cam.angle = min(math.radians(60), 2 * math.atan(span / 2 / (eye - target).length))
    d = target - eye
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    co.location = eye
    sc.camera = co
    return co


def trunk_radius(obj):
    """The trunk's radius at chest height (vertices of slot 0 within 1 m of the axis, 1.2 to 1.5 m up)."""
    me = obj.data
    rs = [math.hypot(me.vertices[i].co.x, me.vertices[i].co.y) for p in me.polygons if p.material_index == 0 for i in p.vertices
          if 1.2 < me.vertices[i].co.z < 1.5 and math.hypot(me.vertices[i].co.x, me.vertices[i].co.y) < 1.0]
    return max(rs) if rs else 0.3


def metrics(obj, ground, path):
    """Layers pass: swap every material for its layer emitter, render 1 sample at a quarter of the size, read it back."""
    sc = bpy.context.scene
    saved = [s.material for s in obj.material_slots]
    gsaved = ground.material_slots[0].material
    kinds = {}
    for i, s in enumerate(obj.material_slots):
        n = s.material.name
        kinds[i] = "leaf" if n.startswith("Leaves") else ("core" if n.startswith("Core") or n.startswith("Crown") else "bark")
        s.material = layers_material(kinds[i])
    ground.material_slots[0].material = layers_material("ground")
    rs = (sc.render.resolution_percentage, sc.cycles.samples, sc.cycles.use_denoising, sc.render.filter_size, sc.view_settings.view_transform, sc.world)
    sc.render.resolution_percentage = 50
    sc.cycles.samples = 1
    sc.cycles.use_denoising = False
    sc.render.filter_size = 0.01
    sc.view_settings.view_transform = "Standard"
    blank = bpy.data.worlds.new("Black")
    blank.use_nodes = True
    blank.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
    sc.world = blank
    sc.render.image_settings.file_format = "OPEN_EXR"
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    sc.render.image_settings.file_format = "JPEG"
    img = bpy.data.images.load(path)
    px = list(img.pixels)
    bpy.data.images.remove(img)
    os.remove(path)
    n = len(px) // 4
    crown = core = bark = shell = 0
    layers = 0.0
    for i in range(n):
        r, g, b = px[4 * i], px[4 * i + 1], px[4 * i + 2]
        if b > 0.5:            # a visible leaf texel (the shell's: green 0.6)
            crown += 1
            shell += g < 0.68
            layers += r * 64
        elif abs(g - 0.5) < 0.1:   # the core
            crown += 1
            core += 1
            layers += r * 64
        elif abs(g - 0.25) < 0.1:  # bark
            bark += 1
        elif r > 0:            # sky or ground seen through cut card texels: still crossed cards
            layers += r * 64
    for i, s in enumerate(obj.material_slots):
        s.material = saved[i]
    ground.material_slots[0].material = gsaved
    sc.render.resolution_percentage, sc.cycles.samples, sc.cycles.use_denoising, sc.render.filter_size, sc.view_settings.view_transform, sc.world = rs
    return dict(crown_px=crown, core_share=core / max(1, crown), shell_share=shell / max(1, crown), layers=layers / max(1, crown), bark_px=bark)


def main():
    global LAYER_ATLAS
    args = parse()
    os.makedirs(args.out, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ground = setup_scene(args)
    obj, tris, h, reach, bark_set = build_tree(args)
    atlas = args.atlas or os.path.join(REPO, "Artifacts", "models", "world", "T_LeafAtlas.png")
    if args.gen == "d" and not args.atlas:
        atlas = os.path.join(REPO, "Artifacts", "envloop", "trees", "T_LeafAtlasD.png")
    LAYER_ATLAS = atlas
    normal = atlas.replace(".png", "N.png")
    if args.season == "winter":
        # Bare: the game's winter fades the leaves away on deciduous trees (Dec); the cards go.
        pass
    mats = {"Leaves": leaf_material(atlas, normal), "Crown": core_material(), "Bark": bark_material(bark_set)}
    for s in obj.material_slots:
        base = s.material.name.split(".")[0]
        key = "Bark" if base.startswith("Bark") else ("Crown" if base.startswith("Crown") else "Leaves")
        if key == "Leaves" and args.season == "winter" and not args.species in ("LiveOak", "RedCedar"):
            m = bpy.data.materials.new("Leaves_bare")
            m.use_nodes = True
            nt = m.node_tree
            nt.nodes.clear()
            o = nt.nodes.new("ShaderNodeOutputMaterial")
            nt.links.new(nt.nodes.new("ShaderNodeBsdfTransparent").outputs[0], o.inputs["Surface"])
            s.material = m
        else:
            s.material = mats[key]
    rows = []
    for dist in (float(d) for d in args.dist.split(",")):
        for o in [o for o in bpy.data.objects if o.type == "CAMERA"]:
            bpy.data.objects.remove(o)
        place_camera(dist, h, reach, trunk_radius(obj))
        stats = {}
        if not args.no_metrics and dist > 0:
            stats = metrics(obj, ground, os.path.join(args.out, "_layers.exr"))
        for light in args.light.split(","):
            set_light(light)
            name = f"{args.gen}_{args.species}_{args.variant}_{int(dist)}m_{light}" + ("" if args.season == "summer" else "_winter") + (f"_{args.core}" if args.core else "")
            sc = bpy.context.scene
            sc.render.image_settings.file_format = "JPEG"
            sc.render.image_settings.quality = 88
            sc.render.filepath = os.path.join(args.out, name + ".jpg")
            bpy.ops.render.render(write_still=True)
            rows.append(dict(name=name, gen=args.gen, species=args.species, variant=args.variant, dist=dist, light=light, tris=tris,
                             height=round(h, 2), reach=round(reach, 2), **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in stats.items()}))
            print(f"Render: {name} {stats}")
    path = os.path.join(args.out, "metrics.csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "gen", "species", "variant", "dist", "light", "tris", "height", "reach", "crown_px", "core_share",
                                          "shell_share", "layers", "bark_px"], restval="")
        if new:
            w.writeheader()
        w.writerows(rows)


main()
