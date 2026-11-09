"""Part detail loop, the Sunfish's deck gear in place (docs/part-detail-loop/sunfish.md).

Builds the Sunfish with Tools/blender/build_fleet.py in this same Blender, then renders close-ups of the gear where it
sits on the boat, in the kit's preview materials (bk_materials, the game's MI_Boat_* values): the tack's spar joint,
the boom's end block over the bridle, the ratchet block and halyard cleat forward of the cockpit, the boom's middle
block and a three-quarter view of the whole boat. The same views for any checkout, so a "before" from main and an
"after" from the branch line up.

    python3 Tools/boatkit/partloop/render_sunfish.py <boat.json from Tools/BoatExport> <out dir> [--samples N]

(boat.json: `Artifacts/boat-export sunfish sunfish.json`, the physics export make-boat-models.sh writes.)
"""
import json
import math
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
CFG, OUT = os.path.abspath(a[0]), os.path.abspath(a[1])
SAMPLES = int(a[a.index("--samples") + 1]) if "--samples" in a else 48
os.environ["BK_SAMPLES"] = str(SAMPLES)
os.makedirs(OUT, exist_ok=True)
MODELS = os.path.join(OUT, "model")

sys.argv = [os.path.join(ROOT, "Tools", "blender", "build_fleet.py"), "--", CFG, "Sunfish", MODELS]
runpy.run_path(sys.argv[0], run_name="__main__")

import bk_materials as BM  # noqa: E402
import bk_render as R  # noqa: E402

boat = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("SM_Sunfish_")]
for o in list(bpy.data.objects):
    if o not in boat:
        bpy.data.objects.remove(o)
for o in boat:
    for i, m in enumerate(o.data.materials):
        name = m.name.split(".")[0] if m else "Deck"
        try:
            o.data.materials[i] = BM.get(name)
        except Exception:
            o.data.materials[i] = BM.get("Deck" if name in ("Topsides", "NonSkid", "Bootstripe", "CoveStripe") else "BlackPlastic")
sock = json.load(open(os.path.join(MODELS, "Sunfish_sockets.json")))
S = {k: Vector((v[0], -v[1], v[2])) / 100.0 for k, v in sock["sockets"].items()} if "sockets" in sock else \
    {k: Vector((v[0], -v[1], v[2])) / 100.0 for k, v in sock.items() if isinstance(v, list)}


def shot(name, target, view, dist, lens=50, w=1200, h=800):
    for o in list(bpy.data.objects):
        if o.type in ("LIGHT", "CAMERA"):
            bpy.data.objects.remove(o)
    R._engine(w, h)
    t = Vector(target)
    d = Vector(view).normalized()
    R._light("Key", "AREA", t + Vector((-1.0, -1.2, 1.6)) * 3.0, t, 900.0, 2.0)
    R._light("Rim", "AREA", t + Vector((1.5, 1.2, 0.8)) * 3.0, t, 350.0, 1.5)
    R._camera(t + d * dist, t, lens)
    bpy.context.scene.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)


# the tack: where the yard's foot meets the boom (forward of the mast)
yard_foot = Vector((1.70, 0.0, 0.57))
shot("tack", yard_foot, (0.35, -1.0, 0.35), 0.75)
shot("tack_high", yard_foot, (-0.6, -0.7, 0.9), 0.75)
# the boom's end block over the bridle, and the bridle
eb = S.get("Boom_Mainsheet", Vector((-1.73, 0, 0.48)))
shot("end_block", (eb + Vector(S.get("Traveler_C", eb))) / 2, (0.2, -1.0, 0.25), 1.1)
# forward of the cockpit: the ratchet block and the halyard's horn cleat
shot("ratchet", Vector((-0.43, 0.08, 0.33)), (-0.9, -0.6, 0.7), 0.85)
shot("mid_block", S.get("Boom_MidBlock", Vector((-0.52, 0, 0.48))), (0.3, -1.0, -0.15), 0.6)
shot("boat", Vector((0.0, 0.0, 0.9)), (1.0, -1.2, 0.55), 9.0, lens=35)
print("render_sunfish:", OUT)
