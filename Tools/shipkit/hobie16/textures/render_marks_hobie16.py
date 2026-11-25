"""The Hobie 16's sail marks as the game will draw them (docs/hobie16-8): the rebuilt main's cloth UVs (sails_hobie16
cloth_uvs: UV0 metres, UV1 the planform's shares, UV2 from the leech) read by a Blender copy of M_SailCloth's marks
block (scripts/make_materials.py SAIL_CODE: the insignia's box, the number's box, each side's set reading right from
its own side, the port set a row below), over the main's panels in one of the class's colour schemes.

    blender -b -P render_marks_hobie16.py -- <hobie16.blend> <out dir> [--number 1288] [--res 1200] [--samples 32]
        [--font <ttf>]

The marks atlas is scripts/make_sail_marks.py's own drawing (the made-up emblem, never a maker's logo, and the digit
strip), run here with its output redirected. Its font is the repo's Saira Condensed Bold (SIL OFL); where the checkout
holds only the Git LFS pointer (the cloud), --font or DejaVu Sans Bold stands in for the preview's digits.

Writes marks_<view>.png (the main from starboard and port, abeam and from aft), marks.jpg (the four together) and
marks.json: each mark's box on the sail in metres, against the class rule's number height (the G3 catalogue's
sail_number) and whether the insignia's box stays inside the sail.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
SRC, OUT = ARGS[0], ARGS[1]
NUMBER = ARGS[ARGS.index("--number") + 1] if "--number" in ARGS else "1288"     # the player's (BoatLivery.cpp)
RES = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else 1200
SAMPLES = int(ARGS[ARGS.index("--samples") + 1]) if "--samples" in ARGS else 32
os.makedirs(OUT, exist_ok=True)
CAT = json.load(open(os.path.join(REPO, "Inputs", "g3", "boat-catalogue.json")))
H16 = next(c for c in CAT["classes"] if c["id"] == "hobie16")
TEX = 2048            # the marks' bake, over UV1's square


def atlas():
    """scripts/make_sail_marks.py's atlas, drawn into OUT (its font swapped for a stand-in when the repo's is an LFS
    pointer)."""
    src = open(os.path.join(REPO, "scripts", "make_sail_marks.py")).read()
    repo_font = os.path.join(REPO, "Content", "UI", "Fonts", "SairaCondensed-Bold.ttf")
    font = ARGS[ARGS.index("--font") + 1] if "--font" in ARGS else repo_font
    if os.path.getsize(font) < 1000:
        font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    out = os.path.join(OUT, "T_SailMarks_preview.png")
    src = src.replace('os.path.join(ROOT, "Artifacts", "textures", "T_SailMarks.png")', repr(out))
    src = src.replace('os.path.join(ROOT, "Content", "UI", "Fonts", "SairaCondensed-Bold.ttf")', repr(font))
    exec(compile(src, "make_sail_marks.py", "exec"), {"__file__": os.path.join(REPO, "scripts", "make_sail_marks.py"),
                                                       "__name__": "__main__"})
    return np.asarray(Image.open(out).convert("RGBA"), np.float32) / 255.0, os.path.basename(font)


def sample(img, u, v):
    """Bilinear lookup of img (H, W, 4) at u right, v down (0..1)."""
    h, w = img.shape[:2]
    x, y = np.clip(u * w - 0.5, 0, w - 1.001), np.clip(v * h - 0.5, 0, h - 1.001)
    x0, y0 = x.astype(int), y.astype(int)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    a, b = img[y0, x0], img[y0, x0 + 1]
    c, d = img[y0 + 1, x0], img[y0 + 1, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def marks(img, number, stbd_face):
    """M_SailCloth's marks block on UV1's square: this face's ink (rgb, alpha) as an image over UV1 (row 0 the head)."""
    nd = max(len(number), 1)
    num = float(number)
    bw = min(0.58, 0.145 * nd)
    v1, u1 = np.meshgrid(1.0 - (np.arange(TEX) + 0.5) / TEX, (np.arange(TEX) + 0.5) / TEX, indexing="ij")
    rgb, a = np.zeros((TEX, TEX, 3), np.float32), np.zeros((TEX, TEX), np.float32)
    stbd = stbd_face                   # set 0 (this face's) is the starboard set on the starboard face
    r0x, r0y = (u1 - 0.30) / 0.46, (v1 - 0.79) / 0.09
    r1x, r1y = (u1 - (0.53 - 0.5 * bw)) / bw, (v1 - (0.62 if stbd else 0.48)) / 0.12
    ins = (r0x >= 0) & (r0x <= 1) & (r0y >= 0) & (r0y <= 1)
    t = sample(img, np.where(stbd, 1.0 - r0x, r0x), 0.5 - r0y * 0.5)
    rgb[ins], a[ins] = t[ins, :3], t[ins, 3]
    box = (r1x >= 0) & (r1x <= 0.999) & (r1y >= 0) & (r1y <= 0.999)
    xs = np.where(stbd, 0.999 - r1x, r1x)
    i = np.floor(xs * nd)
    d = np.mod(np.floor(num / np.power(10.0, nd - 1.0 - i) + 0.01), 10.0)
    t = sample(img, (d + np.mod(xs * nd, 1.0)) / 10.0, 1.0 - r1y * 0.5)
    rgb[box], a[box] = t[box, :3], t[box, 3]
    return rgb, a, bw


def glyph_rows(img):
    """The share of an atlas cell's height the digits' ink fills (the number's height on the sail is this times the
    cell's)."""
    al = img[512:, :, 3]
    rows = np.nonzero(al.max(axis=1) > 0.5)[0]
    return (rows.max() - rows.min() + 1) / 512.0


def scheme():
    """The main's most likely colour scheme in the G3 catalogue: its stripes' colours."""
    sails = next(s for s in H16["sails"] if s["sail"] == "main")
    best = max(sails["colours"], key=lambda c: c["weight"])
    hexes = best["hex"].split(":", 1)[1].split(",") if best["hex"].startswith("stripes:") else [best["hex"]]
    return best["name"], [tuple(int(h[k:k + 2], 16) / 255.0 for k in (1, 3, 5)) for h in hexes]


def lin(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


img, font_used = atlas()
bpy.ops.wm.open_mainfile(filepath=SRC)
sc = bpy.context.scene
main = bpy.data.objects["H16Sail_Main"]
for o in sc.objects:
    if o.type in ("MESH", "CURVE"):
        o.hide_render = False

# each face's marks as images over UV1
ims = {}
for side, stbd in (("stbd", True), ("port", False)):
    rgb, a, bw = marks(img, NUMBER, stbd)
    px = np.dstack([rgb, a])[::-1].reshape(-1)           # Blender images run bottom-up
    im = bpy.data.images.new(f"H16Marks_{side}", TEX, TEX, alpha=True)
    im.colorspace_settings.name = "sRGB"
    im.pixels.foreach_set(px.astype(np.float32))
    im.pack()
    ims[side] = im

name, cols = scheme()
order = [cols[k % len(cols)] for k in range(4)]
for k, slot in enumerate(("SailA", "SailB", "SailC", "SailD")):
    m = bpy.data.materials.get(slot)
    if m is None:
        continue
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bs.inputs["Base Color"].default_value = (*lin(order[k]), 1.0)
    bs.inputs["Roughness"].default_value = 0.55
    bs.inputs["Transmission Weight"].default_value = 0.0
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UV1"
    tex = {}
    for side in ("stbd", "port"):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image, t.interpolation, t.extension = ims[side], "Linear", "CLIP"
        nt.links.new(uv.outputs["UV"], t.inputs["Vector"])
        tex[side] = t
    # the face: Blender's Y is to port, so the starboard face's normal points to -Y in the sail's own space
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    vt = nt.nodes.new("ShaderNodeVectorTransform")
    vt.vector_type, vt.convert_from, vt.convert_to = "NORMAL", "WORLD", "OBJECT"
    nt.links.new(geo.outputs["True Normal"], vt.inputs["Vector"])
    nt.links.new(vt.outputs["Vector"], sep.inputs["Vector"])
    face = nt.nodes.new("ShaderNodeMath")
    face.operation = "LESS_THAN"
    face.inputs[1].default_value = 0.0
    nt.links.new(sep.outputs["Y"], face.inputs[0])
    pick_c, pick_a = nt.nodes.new("ShaderNodeMix"), nt.nodes.new("ShaderNodeMix")
    pick_c.data_type = "RGBA"
    nt.links.new(face.outputs[0], pick_c.inputs["Factor"])
    nt.links.new(tex["port"].outputs["Color"], pick_c.inputs[6])
    nt.links.new(tex["stbd"].outputs["Color"], pick_c.inputs[7])
    nt.links.new(face.outputs[0], pick_a.inputs["Factor"])
    nt.links.new(tex["port"].outputs["Alpha"], pick_a.inputs[2])
    nt.links.new(tex["stbd"].outputs["Alpha"], pick_a.inputs[3])
    ink = nt.nodes.new("ShaderNodeMix")
    ink.data_type = "RGBA"
    ink.inputs[6].default_value = bs.inputs["Base Color"].default_value
    nt.links.new(pick_a.outputs[0], ink.inputs["Factor"])
    nt.links.new(pick_c.outputs[2], ink.inputs[7])
    nt.links.new(ink.outputs[2], bs.inputs["Base Color"])
    nt.links.new(bs.outputs[0], out.inputs[0])

# render: the main abeam from each side and from aft quarters, the boat in clay
sc.render.engine = "CYCLES"
sc.cycles.device, sc.cycles.samples, sc.cycles.use_denoising = "CPU", SAMPLES, True
sc.view_settings.view_transform = "AgX"
world = bpy.data.worlds.new("MarksWorld")
sc.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.62, 0.66, 0.72, 1)
sd = bpy.data.lights.new("MarksSun", "SUN")
sd.energy, sd.angle = 3.0, math.radians(3)
sun = bpy.data.objects.new("MarksSun", sd)
sc.collection.objects.link(sun)
cd = bpy.data.cameras.new("MarksCam")
cam = bpy.data.objects.new("MarksCam", cd)
sc.collection.objects.link(cam)
sc.camera = cam
bb = [main.matrix_world @ Vector(c) for c in main.bound_box]
mid = sum(bb, Vector()) / 8
VIEWS = {"stbd": (Vector((-0.6, -11.0, 4.2)), 40, (0.3, -0.8, 0.6)),
         "port": (Vector((-0.6, 11.0, 4.2)), 40, (0.3, 0.8, 0.6)),
         "stbd_aft": (Vector((-8.5, -7.0, 3.6)), 40, (0.3, -0.8, 0.6)),
         "port_aft": (Vector((-8.5, 7.0, 3.6)), 40, (0.3, 0.8, 0.6))}
for v, (off, lens, sun_from) in VIEWS.items():
    sc.render.resolution_x, sc.render.resolution_y = RES * 2 // 3, RES
    cam.location = mid + off
    cam.rotation_euler = (mid - cam.location).to_track_quat("-Z", "Y").to_euler()
    cd.lens, cd.clip_start, cd.clip_end = lens, 0.05, 500
    sun.rotation_euler = Vector(sun_from).to_track_quat("Z", "Y").to_euler()
    sc.render.filepath = os.path.join(OUT, f"marks_{v}.png")
    bpy.ops.render.render(write_still=True)

# the marks' boxes on the main in metres: UV1 back to the sail through its UV0 (metres) at the box's corners
me = main.data
uv0, uv1 = me.uv_layers["UV0"].data, me.uv_layers["UV1"].data
pts = np.array([(uv1[i].uv[0], uv1[i].uv[1], uv0[i].uv[0], uv0[i].uv[1]) for i in range(len(uv0))])
pts = pts[(pts[:, 1] > 0) | (pts[:, 3] > 0)]
top = float(pts[:, 3].max()) / max(float(pts[:, 1].max()), 1e-6)       # metres of height per unit of UV1.y


def chord_at(v):
    near = pts[np.abs(pts[:, 1] - v) < 0.02]
    return float((near[:, 2] / np.maximum(near[:, 0], 1e-6))[near[:, 0] > 0.5].mean())


glyph = glyph_rows(img)
nd = len(NUMBER)
bw = min(0.58, 0.145 * nd)
rule = H16.get("sail_number", {})
rep = {"number": NUMBER, "font": font_used, "scheme": name,
       "head_height_m": round(top, 3),
       "number_cell_height_m": round(0.12 * top, 3),
       "digit_height_m": round(0.12 * top * glyph, 3),
       "rule_digit_height_m": rule.get("height_mm", 0) / 1000.0,
       "number_width_m_at_its_rows": round(bw * chord_at(0.68), 3),
       "number_rows_stbd_port": [[0.62, 0.74], [0.48, 0.60]],
       "insignia_box_uv1": [[0.30, 0.79], [0.76, 0.88]],
       "insignia_width_m": round(0.46 * chord_at(0.835), 3),
       "insignia_height_m": round(0.09 * top, 3),
       "insignia_inside_sail": True,
       "note": "UV1.x is each row's share from luff to leech (FSailCloth's UVNormal), so every box stays on the cloth; "
               "the boxes are M_SailCloth's, the same for every class"}
json.dump(rep, open(os.path.join(OUT, "marks.json"), "w"), indent=1)
ims_out = [Image.open(os.path.join(OUT, f"marks_{v}.png")).convert("RGB") for v in VIEWS]
w, h = ims_out[0].size
sheet = Image.new("RGB", (w * 4, h), (24, 24, 24))
for k, im in enumerate(ims_out):
    sheet.paste(im, (k * w, 0))
sheet.thumbnail((2400, 1200))
sheet.save(os.path.join(OUT, "marks.jpg"), quality=86)
print(json.dumps(rep, indent=1))
