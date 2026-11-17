"""Track B (docs/envloop/grass/README.md): renders the grass set the way the shore plan's loop asks, outside the game.

    python Tools/envloop/grass/render_grass.py --out DIR [--shots all | name,...] [--res 1280x720] [--samples 48]
    python Tools/envloop/grass/render_grass.py --out DIR --studio          (one still per plant on a grey card floor)

Needs Blender's Python (`bpy` 5.x), numpy and Pillow. A shot is <view>_<dist>m_<light>_<season>[_<tier>]:
  view   shore: a natural lake bank seen from a boat (sedge at the water, bank grasses on a 1 m rise, the unmown edge,
         then mown lawn with weeds), the shore plan's target view
  dist   3, 15 or 60 m from the waterline, eye 1.5 m above the water (the plan's standard renders)
  light  noon (sun 68 deg), low (sun 12 deg, from the side and a little behind the camera: evening light on the bank), overcast (no sun, a grey sky)
  season summer or dormant (the pack's look.json)
  tier   High (lawn blades to 20 m, bank plants to 60 m) or Ultra (bank plants to 100 m); past them the ground is a
         flat stand-in for Track A's texture at its mean colour
Placement follows the plan's bands: hero meshes to 30 m (lawn hero to 8 m, its Light copy to 20 m), Light copies past
that, each band thinning over its last fifth the way the game will fade them. Every plant scales from 85 to 115 percent
and turns at random; species come in patches from a smooth field (no grid). Cycles renders linear light to float, the
script meters a white card under the same light and exposes it to 0.8, then a filmic curve and sRGB: the same exposure
rule for every shot, so seasons and lights compare. Writes <shot>.png and <shot>.json (instances per mesh, triangles in
view, render seconds).
"""
import argparse
import json
import math
import os
import random
import sys
import time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grass_geo as G  # noqa: E402

import bpy  # noqa: E402
from build_grass import to_object  # noqa: E402

LOOK = G.pack()["look"]                # the region pack (--pack, default north-texas-lake)
WATER = (0.045, 0.055, 0.04)         # Ray Hubbard's turbid olive, as the shore loop's renderers use
CLAY = (0.20, 0.13, 0.08)            # blackland clay at the wet toe (Track A will own this)
HFOV = math.radians(55.0)            # a 35 mm-ish lens, about the game's helm view
EYE = 1.5
LIGHTS = {"noon": (68.0, 200.0, 1.0), "low": (12.0, 245.0, 1.0), "overcast": (None, None, 0.0)}
BANK_TOP_Y, BANK_TOP_Z = 6.0, 1.0    # the bank rises 1 m over 6 m from the waterline, then the yard is flat
EDGE_Y = 7.0                         # mowing starts here


def ground_z(y):
    if y < 0:
        return max(-0.6, y * 0.25)
    if y < BANK_TOP_Y:
        t = y / BANK_TOP_Y
        return BANK_TOP_Z * (3 * t * t - 2 * t * t * t)
    return BANK_TOP_Z + 0.004 * (y - BANK_TOP_Y)


def field(x, y, seed):
    """A smooth 0..1 patch field (a few skewed sines): which species grows where."""
    r = random.Random(seed)
    v = 0.0
    for _ in range(4):
        k, a, p = r.uniform(0.15, 0.6), r.uniform(0, math.pi), r.uniform(0, 6.28)
        v += math.sin(k * (x * math.cos(a) + y * math.sin(a)) + p)
    return 0.5 + v / 8.0


# --------------------------------------------------------------------------------------------------------- materials

def _lerp(a, b, t):
    return [a[i] + (b[i] - a[i]) * t for i in range(3)]


def species_colours(card, season):
    look = LOOK[card]
    c = dict(look[season])
    c.setdefault("stalk", _lerp(c["root"], c["tip"], 0.6))
    c.setdefault("seed", c["tip"])
    c.setdefault("cut_tip", c["tip"])
    c.setdefault("midrib", c["tip"])
    return c, look["translucency"], look["roughness"]


def grass_material(name, card, season, seed_slot, emit=False):
    """The grass material as the game will build it (its own script after the slice): root-to-tip blend along UV V,
    the root darkened toward the ground by the height fraction, a per-blade value and hue nudge from the colour's G,
    stalks and seed heads by B, mown tips by A, a pale midrib on johnsongrass; diffuse plus a translucent share for the
    backlit glow, two-sided (Blender is always)."""
    cols, trans, rough = species_colours(card, season)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    attr = N.new("ShaderNodeAttribute")
    attr.attribute_name = "Col"
    uv = N.new("ShaderNodeUVMap")
    sep = N.new("ShaderNodeSeparateColor")
    L.new(attr.outputs["Color"], sep.inputs[0])
    sepuv = N.new("ShaderNodeSeparateXYZ")
    L.new(uv.outputs["UV"], sepuv.inputs[0])

    def rgb(c):
        n = N.new("ShaderNodeRGB")
        n.outputs[0].default_value = (*c, 1.0)
        return n.outputs[0]

    def mix(a, b, fac):
        n = N.new("ShaderNodeMix")
        n.data_type = "RGBA"
        L.new(fac, n.inputs["Factor"])
        L.new(a, n.inputs[6])
        L.new(b, n.inputs[7])
        return n.outputs[2]

    def maprange(v, a, b, c=0.0, d=1.0):
        n = N.new("ShaderNodeMapRange")
        n.inputs[1].default_value, n.inputs[2].default_value = a, b
        n.inputs[3].default_value, n.inputs[4].default_value = c, d
        L.new(v, n.inputs[0])
        return n.outputs[0]

    if seed_slot:
        base = rgb(cols["seed"])
    else:
        leaf = mix(rgb(cols["root"]), rgb(cols["tip"]), maprange(sepuv.outputs["Y"], 0.0, 0.55))
        if card == "johnsongrass":
            dist = N.new("ShaderNodeMath")
            dist.operation = "ABSOLUTE"
            sub = N.new("ShaderNodeMath")
            sub.operation = "SUBTRACT"
            L.new(sepuv.outputs["X"], sub.inputs[0])
            sub.inputs[1].default_value = 0.5
            L.new(sub.outputs[0], dist.inputs[0])
            leaf = mix(rgb(cols["midrib"]), leaf, maprange(dist.outputs[0], 0.04, 0.09))
        leaf = mix(leaf, rgb(cols["cut_tip"]), maprange(attr.outputs["Alpha"], 0.5, 1.0, 0.0, 0.6))
        base = mix(leaf, rgb(cols["stalk"]), maprange(sep.outputs["Blue"], 0.25, 0.4))
    # per-blade nudge: value +-15 percent, a little hue
    hsv = N.new("ShaderNodeHueSaturation")
    L.new(base, hsv.inputs["Color"])
    L.new(maprange(sep.outputs["Green"], 0.0, 1.0, 0.485, 0.515), hsv.inputs["Hue"])
    L.new(maprange(sep.outputs["Green"], 0.0, 1.0, 0.85, 1.15), hsv.inputs["Value"])
    # root shade: the bottom of a stand sees little sky (the game does it from R; ray tracing adds more here)
    shade = mix(rgb((0.7, 0.7, 0.7)), rgb((1.0, 1.0, 1.0)), maprange(sep.outputs["Red"], 0.0, 0.4))
    mul = N.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    L.new(hsv.outputs[0], mul.inputs[6])
    L.new(shade, mul.inputs[7])
    col = mul.outputs[2]
    if emit:                                            # the far-card baker reads the base colour only
        em = N.new("ShaderNodeEmission")
        L.new(col, em.inputs["Color"])
        L.new(em.outputs[0], out.inputs["Surface"])
        return m
    pb = N.new("ShaderNodeBsdfPrincipled")
    L.new(col, pb.inputs["Base Color"])
    pb.inputs["Roughness"].default_value = rough
    pb.inputs["Specular IOR Level"].default_value = 0.35
    tr = N.new("ShaderNodeBsdfTranslucent")
    L.new(col, tr.inputs["Color"])
    ms = N.new("ShaderNodeMixShader")
    ms.inputs[0].default_value = trans * 0.5
    L.new(pb.outputs[0], ms.inputs[1])
    L.new(tr.outputs[0], ms.inputs[2])
    L.new(ms.outputs[0], out.inputs["Surface"])
    return m


FAR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "Artifacts", "grass", "far")


def card_material(season):
    """The far cards' material: the baked atlas's colour and its alpha as a cutout, lit like the blades."""
    m = bpy.data.materials.new(f"GrassFar_{season}")
    m.use_nodes = True
    nt = m.node_tree
    img = bpy.data.images.load(os.path.join(FAR_DIR, f"T_GrassFar_{season}.png"))
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    uv = nt.nodes.new("ShaderNodeUVMap")
    nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
    pb = nt.nodes["Principled BSDF"]
    nt.links.new(tex.outputs["Color"], pb.inputs["Base Color"])
    clip = nt.nodes.new("ShaderNodeMath")
    clip.operation = "GREATER_THAN"
    clip.inputs[1].default_value = 0.4
    nt.links.new(tex.outputs["Alpha"], clip.inputs[0])
    nt.links.new(clip.outputs[0], pb.inputs["Alpha"])
    pb.inputs["Roughness"].default_value = 0.6
    pb.inputs["Specular IOR Level"].default_value = 0.3
    return m


def bake_far(out, slot=256):
    """Bake the far cards' atlas, one per season: each FAR_ATLAS plant's hero mesh seen side-on in an orthographic
    square (the card's own frame, grass_geo.far_frame), its material's base colour (an emission copy, no light) and
    coverage as alpha. Transparent texels take the mean colour so mips and filtering don't darken the edges. Writes
    T_GrassFar_<season>.png (sRGB, straight alpha), 3 x 2 slots in FAR_ATLAS order."""
    os.makedirs(out, exist_ok=True)
    for season in ("summer", "dormant"):
        atlas = np.zeros((2 * slot, 3 * slot, 4), dtype=np.float32)
        for i, cid in enumerate(G.pack()["far"]["atlas"]):
            sc = reset()
            sc.render.film_transparent = True
            sc.world = bpy.data.worlds.new("Black")
            sc.world.use_nodes = True
            sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.0
            pl = G.catalogue(False)[G.pack()["far"]["source"][cid]][1]()
            o = to_object(pl, "src")
            o.data.materials.clear()
            o.data.materials.append(grass_material("leaf", cid, season, False, emit=True))
            o.data.materials.append(grass_material("seed", cid, season, True, emit=True))
            side = G.far_frame(cid)
            cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
            cam.data.type = "ORTHO"
            cam.data.ortho_scale = side
            cam.location = (0.0, -10.0, side / 2)
            cam.rotation_euler = (math.pi / 2, 0.0, 0.0)
            sc.collection.objects.link(cam)
            sc.camera = cam
            sc.render.resolution_x = sc.render.resolution_y = slot
            sc.cycles.samples = 16
            sc.cycles.use_denoising = False
            path = os.path.join(out, f"slot_{i}.exr")
            sc.render.filepath = path
            bpy.ops.render.render(write_still=True)
            px = read_exr(path)
            os.remove(path)
            a = px[..., 3:4]
            rgb = np.where(a > 1e-4, px[..., :3] / np.maximum(a, 1e-4), 0.0)
            # Seen from 60 m a 5 mm blade is a twentieth of a pixel, but a stand of them reads as solid: thicken the
            # coverage by two texels (max filter) so the card keeps its mass through the mips, colour pushed out too.
            for _ in range(2):
                pad = np.pad(a[..., 0], 1, mode="edge")
                grown = np.max([pad[1 + dy:1 + dy + slot, 1 + dx:1 + dx + slot] for dy in (-1, 0, 1) for dx in (-1, 0, 1)], axis=0)
                padc = np.pad(rgb, ((1, 1), (1, 1), (0, 0)), mode="edge")
                padw = np.pad(a[..., 0], 1)
                acc = sum(padc[1 + dy:1 + dy + slot, 1 + dx:1 + dx + slot] * padw[1 + dy:1 + dy + slot, 1 + dx:1 + dx + slot, None]
                          for dy in (-1, 0, 1) for dx in (-1, 0, 1))
                wsum = sum(padw[1 + dy:1 + dy + slot, 1 + dx:1 + dx + slot] for dy in (-1, 0, 1) for dx in (-1, 0, 1))[..., None]
                rgb = np.where(a > 0.5, rgb, acc / np.maximum(wsum, 1e-6))
                a = grown[..., None]
            r, c = i // 3, i % 3
            atlas[r * slot:(r + 1) * slot, c * slot:(c + 1) * slot, :3] = rgb
            atlas[r * slot:(r + 1) * slot, c * slot:(c + 1) * slot, 3:] = a
            print(f"Far card {cid} {season}: side {side:.2f} m, cover {float((a > 0.4).mean()):.2f}")
        cov = atlas[..., 3] > 0.4
        mean = atlas[..., :3][cov].mean(axis=0) if cov.any() else np.zeros(3)
        atlas[..., :3] = np.where(atlas[..., 3:] > 0.05, atlas[..., :3], mean)
        lin = np.clip(atlas[..., :3], 0, 1)
        srgb = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
        rgba = np.concatenate([srgb, np.clip(atlas[..., 3:], 0, 1)], axis=2)
        Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), "RGBA").save(os.path.join(out, f"T_GrassFar_{season}.png"))


def flat_material(name, colour, rough=0.9, noise=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    pb = nt.nodes["Principled BSDF"]
    if noise:
        tex = nt.nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = 0.6
        tex.inputs["Detail"].default_value = 6.0
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs[3].default_value, mr.inputs[4].default_value = 1.0 - noise, 1.0 + noise
        nt.links.new(tex.outputs["Fac"], mr.inputs[0])
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        mx.blend_type = "MULTIPLY"
        mx.inputs["Factor"].default_value = 1.0
        mx.inputs[6].default_value = (*colour, 1.0)
        nt.links.new(mr.outputs[0], mx.inputs[7])
        nt.links.new(mx.outputs[2], pb.inputs["Base Color"])
    else:
        pb.inputs["Base Color"].default_value = (*colour, 1.0)
    pb.inputs["Roughness"].default_value = rough
    return m


# ------------------------------------------------------------------------------------------------------------ scene

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 4
    sc.cycles.diffuse_bounces = 2
    sc.cycles.transmission_bounces = 2
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.transparent_max_bounces = 64   # far cards stack many deep along a grazing view
    sc.view_settings.view_transform = "Standard" if "Standard" in [e.identifier for e in sc.view_settings.bl_rna.properties["view_transform"].enum_items] else sc.view_settings.view_transform
    sc.render.image_settings.file_format = "OPEN_EXR"
    sc.render.image_settings.color_depth = "32"
    return sc


def lights(sc, light):
    elev, azim, sun_on = LIGHTS[light]
    w = bpy.data.worlds.new("Sky")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    if sun_on:
        sky = nt.nodes.new("ShaderNodeTexSky")
        sky.sky_type = "MULTIPLE_SCATTERING" if hasattr(sky, "sky_type") else sky.sky_type
        sky.sun_disc = False
        sky.sun_elevation = math.radians(elev)
        sky.sun_rotation = math.radians(azim)
        sky.aerosol_density = 2.0
        nt.links.new(sky.outputs[0], bg.inputs[0])
        bg.inputs[1].default_value = 1.0
        sun = bpy.data.lights.new("Sun", "SUN")
        sun.energy = 9.0 * min(1.0, 0.35 + math.sin(math.radians(elev)))   # W/m2, about 3 to 4 times the sky on a level card
        sun.angle = math.radians(0.53)
        sun.color = (1.0, 0.93, 0.82) if elev < 20 else (1.0, 0.98, 0.95)
        o = bpy.data.objects.new("Sun", sun)
        # Blender's sky rotation is measured from -Y toward +X; point the lamp the same way
        o.rotation_euler = (math.radians(90 - elev), 0.0, math.radians(azim) + math.pi / 2)
        sc.collection.objects.link(o)
        return o, bg, math.sin(math.radians(elev)) * sun.energy, (3.5 if elev > 40 else 1.6)
    else:
        bg.inputs[0].default_value = (0.75, 0.78, 0.82, 1.0)
        bg.inputs[1].default_value = 1.6
    return None, bg, 0.0, 0.0


def balance(sc, sun, bg, sun_card, ratio):
    """Scale the sky so a level white card gets `ratio` times more from the sun than from the sky (a clear Texas day:
    about 3.5 at high sun, 1.6 with the sun at 12 deg); Blender's physical sky is otherwise far brighter than its lamp."""
    if sun is None:
        return
    sun.hide_render = True
    sky_card = meter(sc)
    sun.hide_render = False
    bg.inputs[1].default_value = (sun_card / math.pi / ratio) / max(sky_card, 1e-6)   # a white card's radiance is E / pi


def meter(sc, res=32):
    """White Lambertian card's linear value under this scene's light, seen from above (for the exposure)."""
    me = bpy.data.meshes.new("Card")
    me.from_pydata([(-1, -1, 50), (1, -1, 50), (1, 1, 50), (-1, 1, 50)], [], [(0, 1, 2, 3)])
    card = bpy.data.objects.new("Card", me)
    card.data.materials.append(flat_material("White", (1.0, 1.0, 1.0), 1.0))
    sc.collection.objects.link(card)
    cam = bpy.data.objects.new("MeterCam", bpy.data.cameras.new("MeterCam"))
    cam.location = (0, 0, 51)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 1.0
    sc.collection.objects.link(cam)
    old_cam, old = sc.camera, (sc.render.resolution_x, sc.render.resolution_y, sc.cycles.samples)
    hidden = [o for o in sc.objects if o.type == "MESH" and o is not card]
    for o in hidden:
        o.hide_render = True
    sc.camera = cam
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.cycles.samples = 64
    path = os.path.join(bpy.app.tempdir or "/tmp", "meter.exr")
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    v = read_exr(path)[..., :3].mean()
    for o in hidden:
        o.hide_render = False
    sc.camera = old_cam
    sc.render.resolution_x, sc.render.resolution_y, sc.cycles.samples = old
    bpy.data.objects.remove(card)
    bpy.data.objects.remove(cam)
    return float(v)


def read_exr(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]
    bpy.data.images.remove(img)
    return a


def tonemap(lin, white):
    """Expose the white card to 0.8, then an ACES-like filmic curve (Narkowicz) and sRGB."""
    x = lin[..., :3] * (0.8 / max(white, 1e-6))
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    y = np.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0)
    s = np.where(y <= 0.0031308, 12.92 * y, 1.055 * np.power(y, 1 / 2.4) - 0.055)
    return (np.clip(s, 0, 1) * 255 + 0.5).astype(np.uint8)


def terrain(sc, x0, x1, y1, season):
    """Water plane, the bank and the yard as one height-mapped grid; ground colour bands: clay toe, rough on the bank,
    lawn past the mowing edge (Track A's means: the stand-in for their texture)."""
    ta = LOOK["_track_a"]
    nx, ny = 120, 160
    ys = [(-2.0 + (y1 + 2.0) * (j / ny) ** 1.6) for j in range(ny + 1)]
    verts, faces, cols = [], [], []
    for j, y in enumerate(ys):
        for i in range(nx + 1):
            x = x0 + (x1 - x0) * i / nx
            verts.append((x, y, ground_z(y) + (0.03 * math.sin(x * 1.3) * math.sin(y * 0.9) if y > 0.5 else 0.0)))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    me = bpy.data.meshes.new("Ground")
    me.from_pydata(verts, [], faces)
    col = me.color_attributes.new("Band", "FLOAT_COLOR", "POINT")
    for k, (x, y, z) in enumerate(verts):
        if y < 0.6:
            c = CLAY
        elif y < EDGE_Y:
            t = min(1.0, (y - 0.6) / 1.0)
            c = _lerp(CLAY, ta["rough"][season], t)
        else:
            c = _lerp(ta["rough"][season], ta["lawn"][season], min(1.0, (y - EDGE_Y) / 0.8))
        col.data[k].color = (*c, 1.0)
    m = bpy.data.materials.new("Ground")
    m.use_nodes = True
    nt = m.node_tree
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = "Band"
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 0.4
    tex.inputs["Detail"].default_value = 8.0
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs[3].default_value, mr.inputs[4].default_value = 0.85, 1.15
    nt.links.new(tex.outputs["Fac"], mr.inputs[0])
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    mx.blend_type = "MULTIPLY"
    mx.inputs["Factor"].default_value = 1.0
    nt.links.new(at.outputs["Color"], mx.inputs[6])
    nt.links.new(mr.outputs[0], mx.inputs[7])
    pb = nt.nodes["Principled BSDF"]
    nt.links.new(mx.outputs[2], pb.inputs["Base Color"])
    pb.inputs["Roughness"].default_value = 0.95
    me.materials.append(m)
    o = bpy.data.objects.new("Ground", me)
    sc.collection.objects.link(o)
    wm = bpy.data.meshes.new("Water")
    wm.from_pydata([(x0, -400, 0), (x1, -400, 0), (x1, 0.4, 0), (x0, 0.4, 0)], [], [(0, 1, 2, 3)])
    wat = bpy.data.materials.new("Water")
    wat.use_nodes = True
    pb = wat.node_tree.nodes["Principled BSDF"]
    pb.inputs["Base Color"].default_value = (*WATER, 1.0)
    pb.inputs["Roughness"].default_value = 0.12
    pb.inputs["IOR"].default_value = 1.33
    wm.materials.append(wat)
    wo = bpy.data.objects.new("Water", wm)
    sc.collection.objects.link(wo)


class Kit:
    """Builds each mesh once (a hidden prototype with its species' materials) and places linked copies."""

    def __init__(self, sc, season):
        self.sc, self.season, self.proto, self.count, self.tris = sc, season, {}, {}, 0
        self.coll = bpy.data.collections.new("Plants")
        sc.collection.children.link(self.coll)
        self.cat = G.catalogue()
        self.mats = {}

    def mesh(self, name):
        if name not in self.proto:
            card, fn, kind = self.cat[name]
            pl = fn()
            o = to_object(pl, "proto_" + name)
            bpy.context.scene.collection.objects.unlink(o)
            me = o.data
            me.materials.clear()
            if kind == "far":
                if "far" not in self.mats:
                    self.mats["far"] = card_material(self.season)
                me.materials.append(self.mats["far"])
                self.proto[name] = (me, pl.tri_count)
                return self.proto[name]
            if card not in self.mats:
                self.mats[card] = (grass_material(f"{card}_leaf", card, self.season, False),
                                   grass_material(f"{card}_seed", card, self.season, True))
            me.materials.append(self.mats[card][0])
            me.materials.append(self.mats[card][1])
            self.proto[name] = (me, pl.tri_count)
        return self.proto[name]

    def put(self, name, x, y, yaw, scale):
        me, tris = self.mesh(name)
        o = bpy.data.objects.new(name, me)
        o.location = (x, y, ground_z(y))
        o.rotation_euler = (0.0, 0.0, yaw)
        o.scale = (scale, scale, scale)
        self.coll.objects.link(o)
        self.count[name] = self.count.get(name, 0) + 1
        self.tris += tris


def in_view(x, y, cy, margin=2.0):
    """Inside the camera's horizontal field (camera at (0, cy) looking +Y)."""
    d = y - cy
    return d > 0.3 and abs(x) < d * math.tan(HFOV / 2) + margin


# The stand rules the game's placement code will follow (round 2, from blind round 1's notes: "evenly spaced, the same
# height, a hard top line"): a smooth vigour field sets each patch's height and density, the stand thins and shortens
# toward the dry bank top, and bare gaps open where vigour is lowest.
STAND = G.pack()["stand"]
BANDS = G.pack()["bands"]


def vigour(x, y):
    return min(1.0, max(0.0, (field(x, y, STAND["vigour_seed"]) - 0.25) / 0.5))


def stand(x, y, rng):
    """(placed?, scale) for a bunch at (x, y) on the bank, by the stand rules."""
    v = vigour(x, y)
    top = min(1.0, max(0.0, (y - 0.8) / (EDGE_Y - 1.2)))
    if v < STAND["gap_below"] and rng.random() < 0.7:
        return False, 1.0
    dens = STAND["density_low"] + (STAND["density_high"] - STAND["density_low"]) * v
    scale = (STAND["scale_low"] + (STAND["scale_high"] - STAND["scale_low"]) * v) * (1.0 - STAND["top_shrink"] * top)
    return rng.random() < dens, scale * rng.uniform(0.8, 1.2)


def populate(kit, cy, tier, rng):
    """The shore bands by distance from the camera: hero to 30 m (lawn hero to 8 m, lawn Light to 20 m), Light copies
    to the tier's limit (High 60, Ultra 100), then far cards (High to 150, Ultra to 200), each band's last fifth
    thinning out."""
    light_lim, far_lim = BANDS[tier]["light"], BANDS[tier]["far"]

    def dist(x, y):
        return math.hypot(x, y - cy)

    def keep(d, lim):
        return d < lim * 0.8 or rng.random() < max(0.0, (lim - d) / (lim * 0.2))

    def pick(base, d):
        """Hero mesh to 30 m, the plant's Light copy to the tier's limit, then its far card (None if it has none)."""
        stem = base.rsplit("_", 1)[0]
        if d < BANDS["hero_m"]:
            return base
        if d < light_lim:
            return stem + "_Light"
        return stem + "_Far" if stem + "_Far" in kit.cat else None

    def put(base, d, x, y, scale):
        name = pick(base, d)
        if name:
            kit.put(name, x, y, rng.uniform(0, 6.28), scale)

    # sedge at the water's edge
    y = -0.1
    xs = np.arange(-160, 160, 0.45)
    for x in xs:
        for row in range(3):
            yy = y + row * 0.45 + rng.uniform(-0.15, 0.15)
            xx = x + rng.uniform(-0.2, 0.2)
            d = dist(xx, yy)
            if not in_view(xx, yy, cy) or not keep(d, far_lim):
                continue
            if field(xx, yy, 5) < 0.35 + 0.15 * row:      # gaps of bare clay
                continue
            if d > light_lim and rng.random() < 0.5:      # far cards: half as many, each a whole tussock's outline
                continue
            put(f"SM_Grass_Sedge_{rng.randrange(3)}", d, xx, yy, rng.uniform(0.85, 1.15) * (0.7 + 0.5 * vigour(xx, yy)))
    # the bank: rough tiles everywhere as the base, bunch grasses and weeds in patches over them
    for yy in np.arange(1.2, EDGE_Y + 0.6, 0.5):
        for xx in np.arange(-160, 160, 0.5):
            x, y = xx + rng.uniform(-0.25, 0.25), yy + rng.uniform(-0.25, 0.25)   # a whole cell: no grid
            d = dist(x, y)
            if not in_view(x, y, cy) or not keep(d, far_lim):
                continue
            if d < light_lim or rng.random() < 0.25:      # past the Light band, one rough card per square metre
                put(f"SM_Grass_Rough_{rng.randrange(3)}", d, x, y, rng.uniform(0.7, 1.3))
            f, g = field(x, y, 11), field(x, y, 29)
            if not (0.8 < y < EDGE_Y - 0.4):
                continue
            placed, scale = stand(x, y, rng)
            if not placed:
                continue
            r = rng.random()
            if g > 0.66:
                kind = f"SM_Grass_Switch_{rng.randrange(3)}"
            elif f < 0.32 and g < 0.5:
                kind = f"SM_Grass_Johnson_{rng.randrange(2)}"
            elif r < 0.03:
                kind = f"SM_Weed_Horseweed_{rng.randrange(2)}"
            elif y < 2.0 and f < 0.5:
                kind = f"SM_Grass_Sedge_{rng.randrange(3)}"
            else:
                kind = f"SM_Grass_Bluestem_{rng.randrange(3)}"
            put(kind, d, x + rng.uniform(-0.2, 0.2), y + rng.uniform(-0.2, 0.2), scale)
    # the mown lawn: hero tiles to 8 m, the Light tile to 20 m, weeds in it
    lawn_lim = 20.0
    for yy in np.arange(EDGE_Y + 0.25, cy + lawn_lim + 1, 0.5):
        for xx in np.arange(-lawn_lim, lawn_lim, 0.5):
            x, y = xx + rng.uniform(-0.12, 0.12), yy + rng.uniform(-0.12, 0.12)
            d = dist(x, y)
            if not in_view(x, y, cy, 1.0) or not keep(d, lawn_lim):
                continue
            name = f"SM_Grass_Lawn_{rng.randrange(4)}" if d < 8.0 else "SM_Grass_Lawn_Light"
            kit.put(name, x, y, rng.uniform(0, 6.28), rng.uniform(0.9, 1.1))
            if rng.random() < 0.025 and d < 15.0:
                w = ("SM_Weed_Dandelion", "SM_Weed_Clover", "SM_Weed_Plantain")[rng.randrange(3)]
                kit.put(w if d < 8 else w + "_Light", x + 0.2, y, rng.uniform(0, 6.28), rng.uniform(0.8, 1.2))


def camera(sc, dist, res):
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.angle = HFOV
    cam.data.clip_start = 0.05
    cam.data.clip_end = 3000
    cam.location = (0.0, -dist, EYE)
    pitch = math.atan2(EYE - 0.5, dist + 3.0)   # look at a point half a metre up, 3 m into the bank
    cam.rotation_euler = (math.pi / 2 - pitch, 0.0, 0.0)
    sc.collection.objects.link(cam)
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = res


def shot(out, view, dist, light, season, tier, res, samples):
    name = f"{view}_{dist}m_{light}_{season}" + ("" if tier == "High" else f"_{tier}")
    sc = reset()
    balance(sc, *lights(sc, light))
    white = meter(sc)
    terrain(sc, -200, 200, 400, season)
    kit = Kit(sc, season)
    populate(kit, -dist, tier, random.Random(1000 + dist))
    camera(sc, dist, res)
    sc.cycles.samples = samples
    path = os.path.join(out, name + ".exr")
    sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    secs = time.time() - t0
    lin = read_exr(path)
    Image.fromarray(tonemap(lin, white)).save(os.path.join(out, name + ".png"))
    np.save(os.path.join(out, name + ".npy"), (lin[..., :3] * (0.8 / white)).astype(np.float16))
    os.remove(path)
    rep = {"shot": name, "dist_m": dist, "light": light, "season": season, "tier": tier, "white": white,
           "instances": kit.count, "tris_placed": kit.tris, "render_s": round(secs, 1), "res": list(res), "samples": samples}
    json.dump(rep, open(os.path.join(out, name + ".json"), "w"), indent=1)
    print(f"Shot {name}: {sum(kit.count.values())} plants, {kit.tris / 1e6:.1f} M tris, {secs:.0f} s")


def studio(out, res, samples):
    """Each plant alone on a mid-grey floor in noon light, 1.6 m tall frame: the size and shape check by eye."""
    names = [n for n, (_c, _f, k) in G.catalogue().items() if k == "hero"]
    for season in ("summer", "dormant"):
        for n in names:
            sc = reset()
            balance(sc, *lights(sc, "noon"))
            white = meter(sc)
            fm = bpy.data.meshes.new("Floor")
            fm.from_pydata([(-5, -5, 0), (5, -5, 0), (5, 5, 0), (-5, 5, 0)], [], [(0, 1, 2, 3)])
            fm.materials.append(flat_material("Grey", (0.18, 0.18, 0.18), 0.9))
            sc.collection.objects.link(bpy.data.objects.new("Floor", fm))
            kit = Kit(sc, season)
            kit.put(n, 0.0, 0.0, 0.4, 1.0)
            o = kit.coll.objects[0]
            o.location = (0, 0, 0)
            h = max(0.15, max(v.co.z for v in o.data.vertices))
            cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
            cam.data.type = "ORTHO"
            cam.data.ortho_scale = max(0.6, h * 1.25)
            cam.location = (0, -6, h * 0.5)
            cam.rotation_euler = (math.radians(88), 0, 0)
            sc.collection.objects.link(cam)
            sc.camera = cam
            sc.render.resolution_x, sc.render.resolution_y = res
            sc.cycles.samples = samples
            path = os.path.join(out, f"studio_{n}_{season}.exr")
            sc.render.filepath = path
            bpy.ops.render.render(write_still=True)
            Image.fromarray(tonemap(read_exr(path), white)).save(path[:-4] + ".png")
            os.remove(path)
            print(f"Studio {n} {season}")


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--pack", help="region pack under Tools/envloop/grass/packs (default north-texas-lake)")
    ap.add_argument("--shots", default="standard")
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--studio", action="store_true")
    ap.add_argument("--bake-far", action="store_true", help="bake the far cards' atlas to Artifacts/grass/far first")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    res = tuple(int(v) for v in a.res.split("x"))
    if a.bake_far or not os.path.exists(os.path.join(FAR_DIR, "T_GrassFar_summer.png")):
        bake_far(FAR_DIR)
    if a.studio:
        studio(a.out, res, a.samples)
        return
    if a.shots == "standard":
        todo = [("shore", d, l, s, "High") for s in ("summer", "dormant") for d in (3, 15, 60) for l in ("noon", "low", "overcast")]
        todo += [("shore", 60, "noon", s, "Ultra") for s in ("summer", "dormant")]
    else:
        todo = []
        for n in a.shots.split(","):
            p = n.split("_")
            todo.append((p[0], int(p[1].rstrip("m")), p[2], p[3], p[4] if len(p) > 4 else "High"))
    for t in todo:
        shot(a.out, *t, res, a.samples)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
