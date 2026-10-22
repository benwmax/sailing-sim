"""#235 follow-up: composite the DeckMould maps. The committed T_J22H_DeckMould_{D,N,R,X} were baked by a newer Blender
(their non-skid keeps a fine speckle where Blender 4.2 bakes a washed-out moire), but they carry a stale bake of the
cabin trunk's walls: the aft wall to starboard of the companionway came out dark and mirror-glossy (base colour 0.16,
roughness 0.08 where the port side is 0.89 and 0.20). A fresh bake has the walls right. With the same UV layout (each
group's uv_m identical), this keeps the committed maps and takes the cabin trunk's walls (not its top: the non-skid)
from the fresh bake, face by face in UV space, with a few pixels of dilation into the gutter.

    blender -b --factory-startup -P Inputs/j22-hero/patch_deckmould.py -- <SM_J22H_Hull.fbx> <committed maps dir> <fresh maps dir> <out dir>
"""
import os
import sys

import bpy
import numpy as np

ARGS = sys.argv[sys.argv.index("--") + 1:]
FBX, OLD, NEW, OUT = ARGS[:4]
CABIN_AFT, CABIN_FWD = -0.55, 1.65   # build_j22_hero.py
DILATE = 3                           # px into the gutter (the bake's margin is 12)


def wall(c, n):
    """A cabin trunk wall, inside or out (the trunk top's non-skid stays the committed bake)."""
    return CABIN_AFT - 0.08 <= c.x <= CABIN_FWD + 0.1 and c.z > 0.42 and abs(c.y) < 1.0 and abs(n.z) < 0.84


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=FBX)
ob = next(o for o in bpy.context.scene.objects if o.type == "MESH")
me, mw = ob.data, ob.matrix_world
me.calc_loop_triangles()
uv = me.uv_layers[0].data
mi = [m.name for m in me.materials].index("J22H_DeckMould")
size = bpy.data.images.load(os.path.join(OLD, "T_J22H_DeckMould_D.png")).size
W, H = size
take = np.zeros((H, W), bool)       # pixels of the walls' islands
keep = np.zeros((H, W), bool)       # pixels of every other DeckMould face


def raster(mask, tri):
    p = np.array([(u * W - 0.5, v * H - 0.5) for u, v in tri])
    x0, y0 = np.floor(p.min(0)).astype(int)
    x1, y1 = np.ceil(p.max(0)).astype(int)
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W - 1), min(y1, H - 1)
    if x1 < x0 or y1 < y0:
        return
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
    (ax, ay), (bx, by), (cx, cy) = p
    d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(d) < 1e-12:
        return
    l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / d
    l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / d
    inside = (l1 >= -0.02) & (l2 >= -0.02) & (1 - l1 - l2 >= -0.02)
    mask[y0:y1 + 1, x0:x1 + 1] |= inside


rot = mw.to_3x3()
for t in me.loop_triangles:
    if t.material_index != mi:
        continue
    poly = me.polygons[t.polygon_index]
    tri = [tuple(uv[li].uv) for li in t.loops]
    raster(take if wall(mw @ poly.center, (rot @ poly.normal).normalized()) else keep, tri)
grown = take.copy()
for _ in range(DILATE):
    g = grown.copy()
    g[1:, :] |= grown[:-1, :]
    g[:-1, :] |= grown[1:, :]
    g[:, 1:] |= grown[:, :-1]
    g[:, :-1] |= grown[:, 1:]
    grown = g
sel = grown & ~(keep & ~take)        # never over another face's island
print(f"patch_deckmould: {int(take.sum())} wall px, {int(sel.sum())} with the gutter, of {W * H}")
os.makedirs(OUT, exist_ok=True)
for k in ("D", "N", "R", "X"):
    name = f"T_J22H_DeckMould_{k}.png"
    a = bpy.data.images.load(os.path.join(OLD, name))
    b = bpy.data.images.load(os.path.join(NEW, name))
    if tuple(b.size) != tuple(a.size):
        raise RuntimeError(f"{name}: sizes differ {tuple(a.size)} {tuple(b.size)}")
    w, h = a.size
    pa = np.empty(w * h * 4, np.float32)
    pb = np.empty(w * h * 4, np.float32)
    a.pixels.foreach_get(pa)
    b.pixels.foreach_get(pb)
    pa, pb = pa.reshape(h, w, 4), pb.reshape(h, w, 4)
    m = sel if (w, h) == (W, H) else np.kron(sel, np.ones((h // H, w // W), bool)) if w >= W else sel[::H // h, ::W // w]
    pa[m] = pb[m]
    out = bpy.data.images.new(name, w, h, alpha=False, float_buffer=False)
    out.colorspace_settings.name = a.colorspace_settings.name
    out.pixels.foreach_set(pa.ravel())
    out.filepath_raw = os.path.join(OUT, name)
    out.file_format = "PNG"
    out.save()
    print("patch_deckmould: wrote", name)
