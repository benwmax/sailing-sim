"""Commonwealth's Unreal export (slice 17, docs/shipkit-17): FBX files, sockets and the materials table the PC's import
reads (export_1797.json says what goes where).

    python -I Tools/shipkit/frigate/export.py <frigate.blend> <out dir> [--only Outside,Decks,Guns] [--dry] [--build <dir>]

--only writes the sockets file for those groups alone (a partial file: run all three for the game's); --dry counts
without writing FBX files (the two json files are written).

Run it on a built frigate.blend after light.py has added the twins (without twins it exports the parts alone and says
so); the build's json files (guns.json, deck.json, gundeck.json, berthdeck.json, ...) are read beside the blend, or
from --build <dir> when the blend is the light copy's merge saved elsewhere. It writes, into <out dir>:

  Outside/SM_Frigate_<Part>.fbx         one per part above the gun deck, in the ship's frame (origin midships on the
                                        load waterline), and SM_Frigate_<Part>_Light.fbx, its twin (the import makes it
                                        LOD 1). A part that shows only in some states (a sail set, clewed or furled;
                                        the running rigging with it) says which in the sockets file. The parts that
                                        turn on deck (deck.json 'frames': the wheel, the capstan's drumhead) are in
                                        their own frames, placed in the sockets file, as the gun deck's are
  Decks/SM_Frigate_<Deck>.fbx           each deck below merged into one mesh, in the ship's frame (collections GunDeck,
                                        BerthDeck, Orlop, Hold); the gun deck, seen from outside through the waist and
                                        the ports, with its merged twins as SM_Frigate_GunDeck_Light; the parts that
                                        turn (gundeck.json 'frames': the capstan's head, the cabin doors) apart, each
                                        in its own frame, placed in the sockets file
  Guns/SM_Frigate_<Mesh>.fbx            the guns' shared meshes (a barrel, a carriage, a truck) once each, in their own
                                        frames; each gun's gear for each pose and its irons in its port's frame; each
                                        port lid in its hinge's frame (origin on the hinge, +X along it); each with its
                                        _Light twin
  Frigate_sockets.json                  in centimetres, ship frame: every exported mesh's file, group and frame (an
                                        outside part's states too; a gun part's or lid's placing says its pose); every
                                        placed copy of a shared or framed mesh (the gun parts in each pose, the lids)
                                        as location and rotation (a quaternion x, y, z, w); the guns' port frames and
                                        poses from guns.json; the lanterns below (gundeck.json 'lights', in cm)
  Frigate_materials.json                each material slot (MI_Frigate_<Material>), its surface and kind on the cards
                                        (textures_1797.json) and the wear terms at each level L0..L4, for the PC to
                                        build the material instances

Slots are named MI_Frigate_<Material> in the files (renamed in memory, the .blend is not saved). FBX axes as the
maxi's (Tools/boats/maxi/build_maxi.py: X forward, Z up, unit scale applied): the build's frame is Unreal's.
"""
import json
import os
import sys
import time

import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import weathering  # noqa: E402

EC = json.load(open(os.path.join(HERE, "export_1797.json")))
LC = json.load(open(os.path.join(HERE, "light_1797.json")))
TAG = EC["tag"]
STATE_COLLECTIONS = sorted({c for v in LC["states"].values() for c in v})
CM = 100.0


def is_twin(o):
    return o.get("light_of") is not None


def deck_of(o):
    d = o.get("deck")
    names = {c.name for c in o.users_collection}
    for deck, rule in EC["decks"].items():
        if d == rule["property"] or names & set(rule["collections"]):
            return deck
    return None


def group_of(o):
    if o.name in EC["skip"] or is_twin(o) or o.type != "MESH":
        return None
    if o.name.startswith(tuple(EC.get("ship_frame_parts") or ())):
        return "Outside"                       # one ship-frame mesh among the guns' collections (the lid lanyards for
    if any(c.name in EC["skip_collections"] for c in o.users_collection):   # each state, the carronades' chocks)
        return "Pose"                          # a gun part's other pose: placed, not exported
    if any(p in o.name for p in EC["gun_parts"]) and o.name.startswith(("Gun24_", "Carr32_", "Lid_")):
        return "Guns"                          # (before the decks: a gun stays apart whatever collection it is in)
    if deck_of(o):
        return "Decks"
    return "Outside"


def states_of(o):
    cols = [c.name for c in o.users_collection if c.name in STATE_COLLECTIONS]
    if not cols:
        return sorted(LC["states"])
    return sorted(s for s, v in LC["states"].items() if set(cols) & set(v))


def xform(m):
    loc, rot, sc = m.decompose()
    return {"location_cm": [round(v * CM, 3) for v in loc], "rotation_xyzw": [round(rot.x, 6), round(rot.y, 6),
            round(rot.z, 6), round(rot.w, 6)], "scale": [round(v, 5) for v in sc]}


def slot_name(m):
    return f"MI_{TAG}_{m}"


# ------------------------------------------------------------------------------------------------ writing a file
def _temp(name, meshes_and_matrices):
    """A temporary object whose mesh is the given meshes, each moved by its matrix, joined (slots merged by material)."""
    objs = []
    for me, mx in meshes_and_matrices:
        c = me.copy()
        c.transform(mx)
        if mx.determinant() < 0:
            c.flip_normals()
        ob = bpy.data.objects.new("_x_" + name, c)
        bpy.context.scene.collection.objects.link(ob)
        objs.append(ob)
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = ob.data.name = name
    return ob


def write(path, meshes_and_matrices, dry=False):
    name = os.path.splitext(os.path.basename(path))[0]
    ob = _temp(name, meshes_and_matrices)
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    slots = [s.material.name if s.material else None for s in ob.material_slots]
    renamed = []
    for s in ob.material_slots:              # the game's slot names, for the export only
        if s.material and not s.material.name.startswith(f"MI_{TAG}_"):
            renamed.append((s.material, s.material.name))
            s.material.name = slot_name(s.material.name)
    try:
        if not dry:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            bpy.ops.object.select_all(action="DESELECT")
            ob.select_set(True)
            bpy.context.view_layer.objects.active = ob
            bpy.ops.export_scene.fbx(filepath=path, use_selection=True, axis_forward="X", axis_up="Z",
                                     apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                                     mesh_smooth_type="FACE", use_mesh_modifiers=True, add_leaf_bones=False,
                                     bake_space_transform=True)
    finally:
        for m, n in renamed:
            m.name = n
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
    return {"triangles": tris, "slots": [slot_name(s) for s in slots if s]}


# ------------------------------------------------------------------------------------------------ the ship
def pose_of(o, deck):
    """The deck's pose collection a part is in (BerthDeck_Hammocks by night, BerthDeck_Messes by day), or None."""
    poses = EC["decks"][deck].get("poses", [])
    return next((c.name for c in o.users_collection if c.name in poses), None)


def frame_matrix(f):
    """A build file's frame as a matrix: gundeck.json's (origin_m, x, y, z) or deck.json's (origin_m, axes: the three
    axes as rows)."""
    m = Matrix.Identity(4)
    axes = f["axes"] if "axes" in f else [f["x"], f["y"], f["z"]]
    for i, ax in enumerate(axes):
        for r in range(3):
            m[r][i] = ax[r]
    m.translation = f["origin_m"]
    return m


def helm_table(d, frames):
    """gundeck.json's tiller and tiller_ropes in the sockets file's terms (cm, quaternions): the tiller turns about its
    frame's +Z by the helm's degree; the six rope parts (TillerEye_S/P, TillerRun_S/P, TillerWrap_S/P) take the frame
    listed for that degree (poses: o, R with the part's axes as columns; a run's X scaled by scale_x). The Tiller mesh's
    'turns' note comes from here too."""
    t, r = d["tiller"], d["tiller_ropes"]
    if "Tiller" in frames:
        frames["Tiller"]["turns"] = t["turns"]
    poses = []
    for q in r["poses"]:
        row = {"helm_deg": q["helm_deg"]}
        for name, v in q.items():
            if name == "helm_deg":
                continue
            m = Matrix.Identity(4)
            for i in range(3):
                for k in range(3):
                    m[k][i] = v["R"][k][i]
            m.translation = v["o"]
            row[name] = dict(xform(m), scale=[round(v.get("scale_x", 1.0), 5), 1.0, 1.0])
        poses.append(row)
    return {"note": ("the tiller (Decks/SM_Frigate_Tiller) turns about its own frame's +Z by the helm's degree (hard over "
                     "hard_over_deg; a positive turn takes the tiller to starboard and the ship's head to port); at each "
                     "whole degree the six rope parts take the frame in 'poses' (location_cm, rotation_xyzw in the ship's "
                     "frame, a run's X scale); between degrees take the nearer pose or blend two; TillerRopeLeads and "
                     "TillerSheaves stay. From docs/frigate-tiller's gundeck.json (tiller, tiller_ropes)"),
            "tiller": "SM_Frigate_Tiller", "hard_over_deg": t["hard_over_deg"],
            "wheel_turns_lock_to_lock": r.get("wheel_turns_lock_to_lock"), "moves": r.get("moves"), "poses": poses}


def export(out, only=None, dry=False, log=lambda m: print(m, flush=True), frames=None, shut_lids=()):
    """frames: the parts that turn below (gundeck.json 'frames': the capstan's head, the cabin doors), each exported
    on its own in its frame instead of merged into its deck."""
    frames = frames or {}
    only = set(only or EC["groups"])
    scene = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    twins = {o["light_of"]: o for o in scene if is_twin(o)}
    groups = {}
    for o in scene:
        g = group_of(o)
        if g:
            groups.setdefault(g, []).append(o)
    meshes, placed, t0 = {}, {}, time.time()
    ident = Matrix.Identity(4)

    def file(group, name, items, twin_items=None, **info):
        path = os.path.join(out, group, f"SM_{TAG}_{name}.fbx")
        rep = write(path, items, dry)
        rep.update({"file": os.path.relpath(path, out), "group": group, "asset": f"{EC['root']}/{group}/SM_{TAG}_{name}"})
        if twin_items:
            lp = os.path.join(out, group, f"SM_{TAG}_{name}_Light.fbx")
            lr = write(lp, twin_items, dry)
            rep["light"] = {"file": os.path.relpath(lp, out), "triangles": lr["triangles"]}
        rep.update(info)
        meshes[f"SM_{TAG}_{name}"] = rep
        log(f"Export: {rep['file']:52s} {rep['triangles']:8d} tris"
            + (f"  light {rep['light']['triangles']}" if "light" in rep else "") + f"  ({time.time() - t0:.0f} s)")

    if "Outside" in only:
        for o in sorted(groups.get("Outside", []), key=lambda o: o.name):
            tw = twins.get(o.name)
            if o.name in frames:                  # a part that turns (deck.json frames: the wheel, the capstan's
                fm = frame_matrix(frames[o.name])  # drumhead): on its own, in its frame, placed in the sockets file
                inv = fm.inverted()
                file("Outside", o.name, [(o.data, inv @ o.matrix_world)], tw and [(tw.data, inv @ tw.matrix_world)],
                     part=o.name, states=states_of(o), frame="its own (deck.json frames)",
                     turns=frames[o.name].get("turns"))
                placed[o.name] = {"mesh": f"SM_{TAG}_{o.name}", **xform(fm), "collection": None, "owner": "ship"}
                continue
            file("Outside", o.name, [(o.data, o.matrix_world)], tw and [(tw.data, tw.matrix_world)],
                 part=o.name, states=states_of(o), frame="ship")
    if "Decks" in only:
        by_deck = {}
        for o in groups.get("Decks", []):
            if o.name in frames:                  # a part that turns: on its own, in its frame
                fm = frame_matrix(frames[o.name])
                inv = fm.inverted()
                tw = twins.get(o.name)
                file("Decks", o.name, [(o.data, inv @ o.matrix_world)], tw and [(tw.data, inv @ tw.matrix_world)],
                     part=o.name, deck=deck_of(o), frame="its own (gundeck.json frames)",
                     turns=frames[o.name].get("turns"))
                placed[o.name] = {"mesh": f"SM_{TAG}_{o.name}", **xform(fm), "collection": deck_of(o), "owner": "ship"}
                continue
            deck = deck_of(o)
            if o.data.users > 1:                  # a linked copy (hammocks, hooks, mess tables): one mesh in its own
                mname = o.data.name               # frame, each copy placed, instanced by the game
                placed[o.name] = {"mesh": f"SM_{TAG}_{mname}", **xform(o.matrix_world),
                                  "collection": next((c.name for c in o.users_collection), None), "deck": deck,
                                  "owner": "ship"}
                if f"SM_{TAG}_{mname}" not in meshes:
                    tw = twins.get(o.name)
                    file("Decks", mname, [(o.data, ident)], tw and [(tw.data, ident)], deck=deck,
                         frame="own (instanced: each copy in the sockets file's placed)", shared_by=o.data.users)
                continue
            by_deck.setdefault((deck, pose_of(o, deck)), []).append(o)
        for (deck, pose), obs in sorted(by_deck.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
            tw = [twins[o.name] for o in obs if o.name in twins]     # the gun deck's (seen from outside)
            file("Decks", deck + (f"_{pose.split('_', 1)[-1]}" if pose else ""), [(o.data, o.matrix_world) for o in obs],
                 tw and [(t.data, t.matrix_world) for t in tw], parts=sorted(o.name for o in obs), frame="ship",
                 light_parts=len(tw), deck=deck, pose=pose)
    if "Guns" in only:
        done = set()
        shut = set(shut_lids)
        for o in sorted(groups.get("Guns", []) + groups.get("Pose", []), key=lambda o: o.name):
            mname = o.data.name
            # who places it in the game: the battery (the cannon-fire code) spawns and moves every gun's parts, gear,
            # irons, tompion and apron and opens the lids with a gun behind them; the ship's static placement keeps
            # only the bridle ports' lids (guns.json shut_lids: no gun, always shut)
            owner = "ship" if o.name in shut else "battery"
            placed[o.name] = {"mesh": f"SM_{TAG}_{mname}", **xform(o.matrix_world),
                              "collection": next((c.name for c in o.users_collection), None), "owner": owner}
            if mname in done or group_of(o) == "Pose":
                continue
            done.add(mname)
            tw = twins.get(o.name)
            frame = ("hinge" if o.name.startswith("Lid_") else "own (guns.json meshes)" if o.data.users > 1
                     else "port")
            file("Guns", mname, [(o.data, ident)], tw and [(tw.data, ident)], frame=frame,
                 shared_by=o.data.users)
        # a shared mesh only some poses place (a run-in quoin) is written from its first user above; check all are
        missing = {o.data.name for o in groups.get("Pose", [])} - done
        for mname in sorted(missing):
            o = next(o for o in groups["Pose"] if o.data.name == mname)
            tw = twins.get(o.name)
            done.add(mname)
            frame = ("hinge" if o.name.startswith("Lid_") else "own (guns.json meshes)" if o.data.users > 1
                     else "port")
            file("Guns", mname, [(o.data, ident)], tw and [(tw.data, ident)], frame=frame, shared_by=o.data.users)
    return meshes, placed, groups, twins


def materials_table():
    idx = weathering.material_index()
    used = sorted({s.material.name for o in bpy.context.scene.objects if o.type == "MESH" and not is_twin(o)
                   and o.name not in EC["skip"] for s in o.material_slots if s.material})
    levels = {lv: weathering.LEVELS[lv] for lv in weathering.LEVEL_IDS}
    out = {}
    for n in used:
        m = bpy.data.materials[n]
        bsdf = next((nd for nd in (m.node_tree.nodes if m.node_tree else []) if nd.type == "BSDF_PRINCIPLED"), None)
        base = list(bsdf.inputs["Base Color"].default_value)[:3] if bsdf else None
        rough = bsdf.inputs["Roughness"].default_value if bsdf else None
        e = {"slot": slot_name(n), "base_colour_linear": base and [round(v, 4) for v in base],
             "roughness": rough and round(rough, 3)}
        if n in idx:
            s, k = idx[n]
            e.update({"surface": s, "kind": k,
                      "wear": {lv: {t: round(v, 3) for t, v in weathering.amounts(s, k, L["age"], L["care"]).items()}
                               for lv, L in levels.items()}})
        else:
            e["surface"] = "unweathered" if n in weathering.CARDS["unweathered"] else "below_decks"
        out[n] = e
    return {"note": "each material slot of the export: its surface and kind on the cards (textures_1797.json) and the "
                    "wear terms at each level (weathering.amounts: the same numbers the Blender dressing uses). "
                    "base_colour_linear and roughness are the undressed material's",
            "levels": {lv: {"age": L["age"], "care": L["care"]} for lv, L in levels.items()},
            "materials": out}


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    src, out = os.path.abspath(args[0]), os.path.abspath(args[1])
    only = args[args.index("--only") + 1].split(",") if "--only" in args else None
    dry = "--dry" in args
    # the build's json files (guns.json, deck.json, gundeck.json, ...): beside the blend, or --build <dir> when the
    # blend exported is the light copy's merge saved elsewhere
    bdir = os.path.abspath(args[args.index("--build") + 1]) if "--build" in args else os.path.dirname(src)
    for need in ("guns.json", "deck.json"):
        if not os.path.exists(os.path.join(bdir, need)):
            raise SystemExit(f"no {need} in {bdir}: give the build's folder with --build <dir>")
    bpy.ops.wm.open_mainfile(filepath=src)
    guns_json = os.path.join(bdir, "guns.json")
    frames, lights, budgets = {}, [], {}
    spar = os.path.join(bdir, EC["outside_json"])
    if os.path.exists(spar):                  # the spar deck's turning parts (deck.json 'frames': the wheel, capstan)
        frames.update(json.load(open(spar)).get("frames") or {})
    read, helm = set(), None
    for deck, rule in EC["decks"].items():    # each deck's file from the build (gundeck.json, berthdeck.json, ...)
        path = os.path.join(bdir, rule.get("json", ""))
        built = any(c in bpy.data.collections for c in rule["collections"])
        if built and rule.get("json") and not os.path.exists(path):
            raise SystemExit(f"{deck} is built but {path} is missing: its turning parts' frames and lanterns come "
                             f"from it (give the build's folder with --build <dir>)")
        if rule.get("json") and os.path.exists(path) and path not in read:   # (orlop.json serves the orlop and
            read.add(path)                                                   # the hold: read once)
            d = json.load(open(path))
            frames.update(d.get("frames") or {})
            for L in d.get("lights") or []:
                L = dict(L, deck=deck)
                if "pos_m" not in L and "at_m" in L:       # slice 14's lanterns give at_m and no zone, kelvin,
                    L["pos_m"] = L.pop("at_m")              # lumens or radius (the gun and berth decks' do)
                L.setdefault("zone", rule["property"])
                lights.append(L)
            if d.get("light_budget"):
                budgets[deck] = d["light_budget"]
            if d.get("tiller") and d.get("tiller_ropes"):   # the tiller build (docs/frigate-tiller): the tiller's
                helm = helm_table(d, frames)                 # turn and the rope parts' frames at each degree of helm
    g = json.load(open(guns_json))
    meshes, placed, groups, twins = export(out, only, dry, frames=frames,
                                           shut_lids=sorted((g.get("long24") or {}).get("shut_lids") or {}))
    os.makedirs(out, exist_ok=True)
    socks = {"note": "Commonwealth's export (Tools/shipkit/frigate/export.py): centimetres, the ship's frame (X forward, "
                     "Y starboard, Z up, origin midships on the load waterline)",
             "root": EC["root"], "states": LC["states"], "meshes": meshes, "placed": placed,
             "placed_note": "owner 'battery': spawned, placed and moved by the cannon-fire code (every gun's parts in "
                            "each pose, its gear, irons, tompion and apron, and the lids with a gun behind them); "
                            "'ship': the static placement (the bridle ports' lids, the framed parts, the decks' copies)",
             "twins": len(twins), "parts_without_twin": sorted(o.name for g in ("Outside", "Guns")
                                                               for o in groups.get(g, []) if o.name not in twins)}
    socks["guns"] = {k: g[k] for k in ("frames_note", "meshes", "long24", "carronade32") if k in g}
    socks["guns_note"] = ("guns.json: the port frame's definition (frames_note), the shared meshes' own frames (meshes), "
                          "the long guns' and carronades' port frames, poses and lid frames (metres there; this "
                          "file's own entries are cm)")
    if lights:                                # the lanterns below: the game places its own lights from these
        socks["lights"] = [dict({k: v for k, v in L.items() if k not in ("pos_m", "radius_m")},
                                location_cm=[round(v * CM, 2) for v in L["pos_m"]],
                                radius_cm=round(L.get("radius_m", 0) * CM, 1)) for L in lights]
        socks["light_budget"] = budgets
    if helm:
        socks["helm"] = helm
        short = [L["name"] for L in lights if "lumens" not in L or "radius_m" not in L]
        if short:
            socks["lights_note"] = ("without kelvin, lumens and radius_cm (slice 14's orlop.json gives only the place "
                                    "and colour; take the gun deck's 2200 K, 180 lm and a 3 m radius until the model "
                                    "thread adds them): " + ", ".join(short))
    json.dump(socks, open(os.path.join(out, f"{TAG}_sockets.json"), "w"), indent=1)
    json.dump(materials_table(), open(os.path.join(out, f"{TAG}_materials.json"), "w"), indent=1)
    tot = {g: sum(r["triangles"] for r in meshes.values() if r["group"] == g) for g in EC["groups"]}
    print(json.dumps({"files": len(meshes), "triangles_by_group": tot, "twins": len(twins),
                      "parts_without_twin": len(socks["parts_without_twin"]), "dry": dry}, indent=1))


if __name__ == "__main__":
    main()
