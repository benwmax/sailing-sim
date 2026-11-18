"""The Catalina 22's light copy (slice 9, docs/c22-10): a lighter twin of every part seen from outside, for distant and
AI boats and marina neighbours, made by the J-Class's tool (Tools/shipkit/jclass/light.py, docs/jclass-12) with the
Catalina's settings (light_c22.json), her states and her parts.

    python light_c22.py -- <build dir>     # on a built c22.blend (Blender's Python): adds the twins, saves it, writes
                                           # <build dir>/light.json

Every mesh but the cabin below (C22_Interior*, drawn only from inside, close to) gets a twin '<name>_Light', hidden, in
the collection Light, with 'light_of' naming its part (light.py's rules: specks dropped, ropes and wires built again
with fewer sides, the rest collapsed, its paint and normals carried, each held to a pixel of a 4K screen from 50 m).
The states are slice 6's (render_hardware_c22.STATE_SAILS): Rest at her mooring, Up (main and genoa), Jib, Reef and
Run (main and spinnaker); a part hidden in every state (the keel and rudder raised, the pop-top raised) still gets its
twin, for the game's other states.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "jclass"))
import bpy  # noqa: E402
import light as L  # noqa: E402

L.LC = json.load(open(os.path.join(HERE, "light_c22.json")))
STATE_SAILS = {"Rest": ("Main_Covered",), "Up": ("Main_Set", "Genoa_Set"), "Jib": ("Main_Set", "Jib_Set"),
               "Reef": ("Main_Reefed", "Jib_Set"), "Run": ("Main_Run", "Spinnaker_Set")}
ALT = ("C22_KeelUp", "C22_RudderUp", "C22_PopTopRaised", "C22_LidRailsRaised")   # other states, in no sail state
BELOW = "C22_Interior"
L.SUITS = {k: {"sails": list(v)} for k, v in STATE_SAILS.items()}


def outside(objs=None):
    """Every mesh but the cabin below and the twins."""
    objs = objs if objs is not None else bpy.context.scene.objects
    return [o for o in objs if o.type == "MESH" and not o.name.startswith(BELOW) and o.get("light_of") is None]


def shown_in(o, suit, tack="starboard"):
    """Whether a part shows in a state: sails by STATE_SAILS, each state's lines, the raised alternatives in none."""
    if o.name.startswith("C22_Sail_"):
        return o.name[len("C22_Sail_"):] in STATE_SAILS[suit]
    if o.name.startswith("C22_Lines_"):
        return o.name == "C22_Lines_" + suit
    return o.name not in ALT


L.outside = outside
L.shown_in = shown_in


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    d = os.path.abspath(args[0])
    bpy.ops.wm.open_mainfile(filepath=os.path.join(d, "c22.blend"))
    rep = L.build()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(d, "c22.blend"))
    with open(os.path.join(d, "light.json"), "w") as f:
        json.dump(rep, f, indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k != "parts"}, indent=1))
