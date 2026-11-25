"""One hull of a twin-hulled .blend, centred, for the shape loop's fairness check (docs/hobie16-2).

    blender -b -P one_hull.py -- <in.blend> <object> <out.blend> [--inboard]

Tools/shapeloop/fairness.py cuts a single hull on the centreline and reads its port face. This keeps the port hull of
<object> (the geometry at Blender y > 0), moves it so its centreline is y = 0 (the card's game.hull_center_y_m) and saves
it alone as object "OneHull": its outboard face is then the port face fairness.py reads. --inboard mirrors it, so the
inboard face is read instead. Works on today's model (Hobie16_Hull) and the rebuild's (H16_Hull) alike.
"""
import json
import os
import sys

import bpy
import bmesh

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
SRC, NAME, OUT = ARGS[0], ARGS[1], ARGS[2]
INBOARD = "--inboard" in ARGS
CY = json.load(open(os.path.join(HERE, "specs_hobie16.json")))["game"]["hull_center_y_m"]

bpy.ops.wm.open_mainfile(filepath=SRC)
src = bpy.data.objects[NAME]
bm = bmesh.new()
bm.from_mesh(src.data)
bm.transform(src.matrix_world)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y < 0.05], context="VERTS")
for v in bm.verts:
    v.co.y = (v.co.y - CY) * (-1 if INBOARD else 1)
if INBOARD:
    bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
me = bpy.data.meshes.new("OneHull")
bm.to_mesh(me)
bm.free()
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
ob = bpy.data.objects.new("OneHull", me)
bpy.context.scene.collection.objects.link(ob)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"one_hull: {NAME} -> OneHull ({len(me.polygons)} faces{', inboard face to port' if INBOARD else ''}) in {OUT}")
