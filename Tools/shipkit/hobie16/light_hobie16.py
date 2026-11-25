"""The Hobie 16's light copy (slice 8, docs/hobie16-9): a lighter twin of every part, for distant and AI boats and
beach neighbours, made by the J-Class's tool (Tools/shipkit/jclass/light.py, docs/jclass-12) with the Hobie's settings
(light_hobie16.json), as the Catalina 22's is (Tools/shipkit/catalina22/light_c22.py).

    python light_hobie16.py -- <build dir>    # on a built hobie16.blend (Blender's Python): adds the twins, saves it,
                                              # writes <build dir>/light.json

Every mesh gets a twin '<name>_Light', hidden, in the collection Light, with 'light_of' naming its part (light.py's
rules: specks dropped, ropes and wires built again with fewer sides, the rest collapsed, its paint and normals carried,
each held to a pixel of a 4K screen from 50 m). She has one state: the main and jib set (no spinnaker, no cabin below),
so every part shows in it.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "jclass"))
import bpy  # noqa: E402
import light as L  # noqa: E402

L.LC = json.load(open(os.path.join(HERE, "light_hobie16.json")))
L.SUITS = {"Up": {"sails": ["H16Sail_Main", "H16Sail_Jib"]}}


def outside(objs=None):
    """Every mesh but the twins."""
    objs = objs if objs is not None else bpy.context.scene.objects
    return [o for o in objs if o.type == "MESH" and o.get("light_of") is None]


def shown_in(o, suit, tack="starboard"):
    """She has one state, the sails up: every part shows in it."""
    return True


_twin = L.twin


def twin(ob, tol):
    """light.twin with the part's own share of the tolerance (light_hobie16.json part_pixels), or every triangle kept
    (its 'whole' parts: the tool's last ratio, 1.0, alone, and their tubes kept as they are)."""
    if ob.name in L.LC.get("whole", []):          # no collapse, and no tube built again with fewer sides
        ratios, sides = L.LC["ratios"], L.LC["tube"]["hero_sides_from"]
        L.LC["ratios"], L.LC["tube"]["hero_sides_from"] = [1.0], 10 ** 6
        try:
            return _twin(ob, tol)
        finally:
            L.LC["ratios"], L.LC["tube"]["hero_sides_from"] = ratios, sides
    return _twin(ob, tol * L.LC.get("part_pixels", {}).get(ob.name, 1.0))


L.outside = outside
L.shown_in = shown_in
L.twin = twin


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    d = os.path.abspath(args[0])
    bpy.ops.wm.open_mainfile(filepath=os.path.join(d, "hobie16.blend"))
    rep = L.build()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(d, "hobie16.blend"))
    with open(os.path.join(d, "light.json"), "w") as f:
        json.dump(rep, f, indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k != "parts"}, indent=1))
