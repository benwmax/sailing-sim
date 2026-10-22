"""pc/boat-slots: folds a built boat mesh's material slots into the packs of boat_packs.json (one slot, and one draw, per
pack). Each face keeps its library slot as an entry index in a second UV set ("Pack", u = the entry), which M_BoatPacked
reads; MI_Boat_<Pack> holds the entries' values (scripts/make_materials.py). Shared by build_j22.py, build_fleet.py and
build_berthed.py."""
import json
import os

import bpy

PACKS = {k: v for k, v in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "boat_packs.json"))).items()
         if not k.startswith("_")}
ENTRY = {slot: (pack, k) for pack, entries in PACKS.items() for k, slot in enumerate(entries)}


def pack_slots(me, keep=()):
    """Folds `me`'s faces into packs: a face whose slot is a pack entry (and not in `keep`) moves to the pack's slot with
    its entry in the "Pack" UV set; the rest keep their slot. Unused slots are dropped. Returns the new slot names."""
    names = [m.name.split(".")[0] if m else "" for m in me.materials]
    uv = me.uv_layers.new(name="Pack")
    order, new_index, faces = [], {}, []
    for p in me.polygons:
        slot = names[p.material_index]
        pack, k = ENTRY.get(slot, (slot, 0)) if slot not in keep else (slot, 0)
        if pack not in new_index:
            new_index[pack] = len(order)
            order.append(pack)
        faces.append(new_index[pack])
        for li in p.loop_indices:
            uv.data[li].uv = (float(k), 0.0)
    me.materials.clear()   # (resets every face's index: set them after)
    for name in order:
        me.materials.append(bpy.data.materials.get(name) or bpy.data.materials.new(name))
    me.polygons.foreach_set("material_index", faces)
    return order
