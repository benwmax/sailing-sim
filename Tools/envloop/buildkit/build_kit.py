"""Builds the building parts kit (Track E): every part in hk_parts.PARTS, checked against its size-card row and triangle
budget, exported as SM_HouseKit_<Part>.fbx with its sockets, and listed in kit.json. With --render it also renders a
catalogue tile per part and lays them out as one sheet (catalogue.jpg).

    python3 Tools/envloop/buildkit/build_kit.py <out dir> [--render] [--only A,B]      (bpy module)
    blender -b --factory-startup -P Tools/envloop/buildkit/build_kit.py -- <out dir> [--render]

No light copies: the plan's near band (30 to 150 m) uses the full parts, and past 150 m houses are the re-baked tiles
(HouseKit's bake), so a part never needs its own decimated twin. Exits non-zero when a check fails.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hk_core as K  # noqa: E402
import hk_parts as P  # noqa: E402
from hk_core import G  # noqa: E402

# Size checks: (part axis, size-card key). Openings are checked on the opening (w, h), so frames and sills that stand
# past it are allowed for; the tolerance is the loop's 5 percent plus the frame allowance.
FRAME_ALLOW = {"opening": 0.13, "wallmount": 0.02, "roof": 0.10, "floor": 0.02, "linear": 0.02}
SKIP_SIZE = {"Gutter", "Downspout", "RidgeCap", "FoundationSlab", "SkirtLattice", "CasingBrickMould", "CasingFlat",
             "CornerBoard", "Fascia", "RailBaluster", "StepsConcrete", "DormerGable", "DormerShed", "ChimneyBrick",
             "ChimneyChase", "ChimneyFlue", "PostCedar", "ColumnTapered", "ACCondenser", "MeterGas", "MeterElectric",
             "LightGooseneck", "TurbineVent", "StackPipe", "SillCastStone"}


def bounds(ob):
    vs = [v.co for v in ob.data.vertices]
    lo = Vector([min(v[i] for v in vs) for i in range(3)])
    hi = Vector([max(v[i] for v in vs) for i in range(3)])
    return lo, hi


def check(name, ob, info):
    lo, hi = bounds(ob)
    size = hi - lo
    row = K.SIZES.get(info["row"]) or K.SIZES.get(name)
    tris = K.tris(ob)
    notes = []
    ok = True
    if tris > info["budget"]:
        ok = False
        notes.append(f"over budget {tris} > {info['budget']}")
    if row and name not in SKIP_SIZE:
        allow = FRAME_ALLOW[info["kind"]]
        for axis, key in ((0, "w"), (2, "h")):
            want = row[key]
            got = size[axis]
            if name == "WinArchTop3060" and key == "h":
                want = row["h"]
            err = (got - want) / want
            if err < -0.05 or err > 0.05 + allow / want:
                ok = False
                notes.append(f"{key} {got:.3f} vs card {want:.3f}")
    slots = [m.name for m in ob.data.materials]
    bad = [s for s in slots if s not in K.SLOTS]
    if bad:
        ok = False
        notes.append(f"unknown slots {bad}")
    return ok, dict(tris=tris, size_m=[round(x, 3) for x in size], slots=slots, sockets=[c.name[7:] for c in ob.children],
                    budget=info["budget"], kind=info["kind"], card=info["row"], notes=notes)


def export_fbx(ob, path):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    ob.select_set(True)
    for c in ob.children:
        c.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH", "EMPTY"}, apply_unit_scale=True,
                             mesh_smooth_type="OFF", use_custom_props=False, add_leaf_bones=False, bake_anim=False,
                             axis_forward="X", axis_up="Z", colors_type="LINEAR")


def render_tiles(built, out, palette):
    import hk_preview as PV
    import test_house as T
    PV.setup_materials(palette, os.path.join(K.REPO, "Artifacts", "buildkit", "trim"))
    PV.render_setup(res=(400, 400), samples=int(os.environ.get("HK_SAMPLES", "24")))
    PV.light("low", yaw_deg=150.0)
    # a backdrop: a wall behind and a floor
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, -0.002, 0), rotation=(math.pi / 2, 0, 0))
    wall = bpy.context.active_object
    m = bpy.data.materials.new("Backdrop")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1)
    for o in bpy.context.scene.objects:
        if o.type == "MESH" and o.name.startswith("Plane"):
            o.data.materials.append(m)
    # every part on its own spot 60 m apart, the backdrop moved behind each in turn
    for k, (name, ob) in enumerate(built):
        ob.location = (k * 60.0, 0.0, 0.0)
    floor = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.name.startswith("Plane") and o is not wall][0]
    tiles = []
    for k, (name, ob) in enumerate(built):
        lo, hi = bounds(ob)
        lo.x += k * 60.0
        hi.x += k * 60.0
        c = (lo + hi) / 2
        wall.location.x = floor.location.x = k * 60.0
        wall.location.y = lo.y - 0.002 if P.PARTS[name]["kind"] in ("opening", "wallmount", "linear") else -0.002
        r = max((hi - lo).length * 0.5, 0.15)
        kind = P.PARTS[name]["kind"]
        wall.hide_render = kind not in ("opening", "wallmount", "linear")
        d = r / math.tan(math.radians(17)) * 1.15
        dirv = Vector((0.45, 1.0, 0.35 if kind in ("roof", "floor") else 0.18)).normalized()
        for o in [o for o in bpy.context.scene.objects if o.type == "CAMERA"]:
            bpy.data.objects.remove(o, do_unlink=True)
        T.camera(c + dirv * d, c, 50.0)
        p = os.path.join(out, "tiles", f"{name}.jpg")
        bpy.context.scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        tiles.append((name, p))
    return tiles


def contact_sheet(tiles, manifest, path, cols=8):
    from PIL import Image, ImageDraw, ImageFont
    tw = 300
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (tw + 34)), (24, 24, 24))
    font_path = os.path.join(K.REPO, "Content", "UI", "Fonts", "SairaCondensed-Bold.ttf")
    try:
        font = ImageFont.truetype(font_path, 17)
    except OSError:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(sheet)
    for i, (name, p) in enumerate(tiles):
        x, y = (i % cols) * tw, (i // cols) * (tw + 34)
        sheet.paste(Image.open(p).resize((tw, tw)), (x, y))
        m = manifest[name]
        d.text((x + 6, y + tw + 2), f"{name}", fill=(235, 235, 235), font=font)
        d.text((x + 6, y + tw + 17), f"{m['tris']} tris  {m['size_m'][0]:.2f} x {m['size_m'][2]:.2f} m", fill=(170, 170, 170), font=font)
    sheet.save(path, quality=90)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    out = argv[0] if argv else os.path.join(K.REPO, "Artifacts", "buildkit", "kit")
    flags = argv[1:]
    only = None
    if "--only" in flags:
        only = set(flags[flags.index("--only") + 1].split(","))
    os.makedirs(os.path.join(out, "fbx"), exist_ok=True)
    os.makedirs(os.path.join(out, "tiles"), exist_ok=True)
    trim_dir = os.path.join(K.REPO, "Artifacts", "buildkit", "trim")
    if not os.path.exists(os.path.join(trim_dir, "T_HouseTrim_C.png")):
        import subprocess
        subprocess.run([sys.executable, os.path.join(HERE, "make_trim_sheet.py"), trim_dir], check=True)
    G.clear_scene()
    manifest, built, failed = {}, [], []
    for i, (name, info) in enumerate(P.PARTS.items()):
        if only and name not in only:
            continue
        ob = info["build"]()
        ob.name = f"SM_HouseKit_{name}"
        ok, st = check(name, ob, info)
        manifest[name] = st
        export_fbx(ob, os.path.join(out, "fbx", f"SM_HouseKit_{name}.fbx"))
        built.append((name, ob))
        if not ok:
            failed.append(name)
        print(f"Kit: {name:18s} {st['tris']:6d} tris / {info['budget']:5d}  {st['size_m']}  {'OK' if ok else 'FAIL ' + '; '.join(st['notes'])}")
    json.dump(manifest, open(os.path.join(out, "kit.json"), "w"), indent=1)
    print(f"Kit: {len(built)} parts, {sum(m['tris'] for m in manifest.values())} tris, {len(failed)} failed -> {out}")
    if "--render" in flags:
        pal = json.load(open(os.path.join(HERE, "styles", "ranch1970.json")))["palettes"][0]
        tiles = render_tiles(built, out, pal)
        contact_sheet(tiles, manifest, os.path.join(out, "catalogue.jpg"))
        print(f"Kit: catalogue -> {os.path.join(out, 'catalogue.jpg')}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
