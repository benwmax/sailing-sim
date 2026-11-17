"""Environment loop standard renders (shore plan step 5) for Tracks F and H, until Track 0's shared tools land.

Every mesh in an FBX folder (from build_shore_docks.py or build_yard_props.py) is rendered the same way every round:
from the water (docks) or the lawn (yard props), with the camera at eye height 1.5 m and 3 m, 15 m and 60 m from the
asset's centre, in three lights: midday sun (65 deg), low sun (8 deg, warm) and overcast. A bank with a concrete
bulkhead, lawn and the lake surface stand in for the shore. Sockets in the manifest are dressed with the boats,
PWC ports, kayaks, umbrellas and chairs found in the given folders, so a dock is seen as it will stand.
Preview looks are flat stand-ins for the MI_World_* looks (the game's materials are Track A/E's and the Mac's work).

Writes <out>/<mesh>/<light>_<dist>m.png, a clay still, and stats.json (triangles, size, slots, sockets).

Usage (Python with the bpy module):
  python3 Tools/envloop/docks/render_envloop.py <fbx dir> <out dir> [--dress <dir>,<dir>] [--only SM_A,SM_B]
      [--dists 3,15,60] [--lights midday,low,overcast] [--samples 16] [--size 640x400] [--setting water|lawn]
      [--bearing <deg>] [--boat SM_ShoreBoat_RunaboutCovered] [--no-dress] [--no-clay]
"""
import hashlib
import json
import math
import os
import sys

import bpy
from mathutils import Euler, Vector

LOOKS = {   # slot -> (base colour (linear), metallic, roughness, emission)
    "Decking": ((0.30, 0.22, 0.14), 0.0, 0.75, 0.0),     # weathered treated pine going grey-brown
    "Wood": ((0.25, 0.19, 0.13), 0.0, 0.8, 0.0),
    "Galv": ((0.30, 0.31, 0.31), 0.6, 0.6, 0.0),
    "Steel": ((0.62, 0.63, 0.64), 1.0, 0.33, 0.0),
    "White": ((0.80, 0.80, 0.77), 0.0, 0.5, 0.0),
    "Vinyl": ((0.78, 0.78, 0.76), 0.0, 0.45, 0.0),
    "Dark": ((0.03, 0.03, 0.03), 0.0, 0.7, 0.0),
    "Trim": ((0.33, 0.34, 0.35), 0.0, 0.5, 0.0),
    "Glass": ((0.03, 0.04, 0.05), 0.0, 0.05, 0.0),
    "LampGlow": ((0.95, 0.93, 0.85), 0.0, 0.3, 0.3),
    "SafetyRed": ((0.55, 0.03, 0.02), 0.0, 0.4, 0.0),
    "Floats": ((0.025, 0.025, 0.025), 0.0, 0.55, 0.0),
    "Gold": ((0.75, 0.55, 0.22), 1.0, 0.35, 0.0),
    "Gelcoat": ((0.78, 0.78, 0.75), 0.0, 0.25, 0.0),
    "Deck": ((0.45, 0.43, 0.40), 0.0, 0.7, 0.0),
    "Cushion": ((0.70, 0.66, 0.58), 0.0, 0.7, 0.0),
    "TrimGreen": ((0.05, 0.15, 0.08), 0.0, 0.5, 0.0),
    "Carpet": ((0.05, 0.06, 0.08), 0.0, 0.95, 0.0),
    "Concrete": ((0.42, 0.41, 0.38), 0.0, 0.85, 0.0),
    "Paint": ((0.25, 0.27, 0.30), 0.3, 0.3, 0.0),
    "Tyre": ((0.03, 0.03, 0.03), 0.0, 0.85, 0.0),
    "Trailer": ((0.5, 0.51, 0.52), 0.8, 0.45, 0.0),
    "HeadLight": ((0.8, 0.8, 0.8), 0.0, 0.1, 0.0),
    "TailLight": ((0.4, 0.02, 0.02), 0.0, 0.2, 0.0),
    "Roof": ((0.2, 0.19, 0.18), 0.0, 0.8, 0.0),
    "Net": ((0.02, 0.02, 0.02), 0.0, 0.8, 0.0),
    "Limestone": ((0.50, 0.46, 0.38), 0.0, 0.85, 0.0),
    "Crown": ((0.05, 0.12, 0.03), 0.0, 0.8, 0.0),
    "Leaves": ((0.05, 0.12, 0.03), 0.0, 0.8, 0.0),
}
SEE_THROUGH = {"Net": 0.35}   # preview alpha for mesh nets (the game's material masks the weave)
# Per-instance colours the game will set (MetalRoof, Canvas, Plastic): the render picks one by the mesh's name.
TINTS = {
    "MetalRoof": [(0.42, 0.43, 0.42), (0.20, 0.035, 0.03), (0.04, 0.09, 0.05), (0.09, 0.09, 0.09), (0.36, 0.30, 0.21)],
    "Canvas": [(0.02, 0.035, 0.09), (0.36, 0.30, 0.20), (0.04, 0.10, 0.05), (0.20, 0.21, 0.22)],
    "Plastic": [(0.50, 0.08, 0.03), (0.70, 0.45, 0.04), (0.04, 0.22, 0.40), (0.06, 0.30, 0.10), (0.45, 0.45, 0.43)],
}
METAL = {"MetalRoof": (0.5, 0.45), "Canvas": (0.0, 0.85), "Plastic": (0.0, 0.4)}
LIGHTS = {"midday": (65.0, 210.0, 1.0), "low": (8.0, 150.0, 0.55), "overcast": (None, None, 0.0)}
DRESS = {   # socket prefix -> mesh names that may stand there (picked by hash)
    "boat": ["SM_ShoreBoat_RunaboutCovered", "SM_ShoreBoat_Pontoon", "SM_ShoreBoat_RunaboutOpen"],
    "pwc_port": ["SM_ShorePWCPort"], "pwc": ["SM_ShoreBoat_PWC"],
    "kayak": ["SM_Yard_Kayak"], "umbrella": ["SM_Yard_UmbrellaOpen"], "chairs": ["SM_Yard_AdirondackPair"],
}


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]

    def opt(k, d):
        return a[a.index(k) + 1] if k in a else d
    return {
        "src": os.path.abspath(a[0]), "out": os.path.abspath(a[1]),
        "dress": [os.path.abspath(x) for x in opt("--dress", "").split(",") if x],
        "only": opt("--only", None), "dists": [float(x) for x in opt("--dists", "3,15,60").split(",")],
        "lights": opt("--lights", "midday,low,overcast").split(","), "samples": int(opt("--samples", "16")),
        "size": [int(x) for x in opt("--size", "640x400").split("x")], "setting": opt("--setting", "water"),
        "bearing": float(opt("--bearing", "50")), "clay": "--no-clay" not in a,
        "boat": opt("--boat", None), "undressed": "--no-dress" in a,
    }


def hpick(name, seq):
    return seq[int(hashlib.md5(name.encode()).hexdigest(), 16) % len(seq)]


def pbr(name, col, met=0.0, rough=0.5, emit=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Metallic"].default_value = met
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*col, 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


def look(slot, mesh_name, clay=False):
    key = slot.split(".")[0]
    if clay:
        return pbr("Clay", (0.6, 0.6, 0.6), 0.0, 0.6)
    if key in TINTS:
        col = hpick(mesh_name + key, TINTS[key])
        met, rough = METAL[key]
        return pbr(f"Tint_{key}_{col}", col, met, rough)
    col, met, rough, emit = LOOKS.get(key, ((0.5, 0.0, 0.5), 0.0, 0.5, 0.0))
    m = pbr(f"Look_{key}", col, met, rough, emit)
    if key in SEE_THROUGH:
        m.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = SEE_THROUGH[key]
    return m


def import_mesh(path, name_hint, at=(0, 0, 0), yaw=0.0):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path, axis_forward="X", axis_up="Z")
    objs = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    for o in objs:
        o.location = Vector(at) + o.location
        o.rotation_euler.z += math.radians(yaw)   # keep the FBX axis turn the import set
        for ms in o.material_slots:
            ms.material = look(ms.material.name if ms.material else "", name_hint)
    return objs


def stage(setting, extent):
    """The shore stand-in: lake surface, a bulkhead along X = 0 with a lawn behind it (docks), or a lawn (yard)."""
    water = pbr("Water", (0.03, 0.045, 0.04), 0.0, 0.18)
    lawn = pbr("Lawn", (0.08, 0.12, 0.035), 0.0, 0.9)
    conc = look("Concrete", "")
    big = max(400.0, extent * 20)
    if setting == "water":
        bpy.ops.mesh.primitive_plane_add(size=big, location=(big / 2 - 0.2, 0, 0))
        bpy.context.active_object.data.materials.append(water)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(-big / 4, 0, 0.0))
        o = bpy.context.active_object
        o.scale = (big / 2, big, 1.2)
        o.data.materials.append(lawn)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.15, 0, -0.1))
        o = bpy.context.active_object
        o.scale = (0.3, big, 1.4)
        o.data.materials.append(conc)
    else:
        bpy.ops.mesh.primitive_plane_add(size=big, location=(0, 0, 0))
        bpy.context.active_object.data.materials.append(lawn)


def sky(light):
    sc = bpy.context.scene
    elev, az, strength = LIGHTS[light]
    w = bpy.data.worlds.new("Sky")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    for o in [o for o in bpy.data.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o, do_unlink=True)
    if elev is None:
        bg.inputs[0].default_value = (0.55, 0.57, 0.6, 1)
        bg.inputs[1].default_value = 1.2
        return
    tex = nt.nodes.new("ShaderNodeTexSky")
    try:
        tex.sky_type = "NISHITA"
        tex.sun_elevation = math.radians(elev)
        tex.sun_rotation = math.radians(az)
        tex.sun_disc = False
    except Exception:
        pass
    nt.links.new(tex.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = 0.12 if elev > 20 else 0.2
    ld = bpy.data.lights.new("Sun", "SUN")
    ld.energy = 5.0 * strength
    ld.angle = math.radians(0.6)
    if elev < 20:
        ld.color = (1.0, 0.72, 0.5)
    lo = bpy.data.objects.new("Sun", ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.rotation_euler = Euler((math.radians(90 - elev), 0, math.radians(az + 90)))


def bounds(objs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = -lo
    for o in objs:
        mw = o.matrix_world
        for v in o.data.vertices:
            p = mw @ v.co
            lo = Vector([min(lo[i], p[i]) for i in range(3)])
            hi = Vector([max(hi[i], p[i]) for i in range(3)])
    return lo, hi


def camera(target, dist, bearing, setting, size_xy):
    """Eye height 1.5 m over the water or lawn, `dist` metres horizontally from the target, at `bearing` degrees from
    straight out along +X (docks: looking back at the bank from the lake)."""
    for o in [o for o in bpy.data.objects if o.type == "CAMERA"]:
        bpy.data.objects.remove(o, do_unlink=True)
    cd = bpy.data.cameras.new("Cam")
    cd.lens = 35 if dist >= 10 else 24
    cd.clip_start = 0.05
    cd.clip_end = 5000
    cam = bpy.data.objects.new("Cam", cd)
    bpy.context.scene.collection.objects.link(cam)
    b = math.radians(bearing)
    d = Vector((math.cos(b), math.sin(b), 0.0))
    cam.location = Vector((target.x, target.y, 0.0)) + d * dist + Vector((0, 0, 1.5))
    aim = Vector((target.x, target.y, max(0.8, min(target.z, 2.5))))
    cam.rotation_euler = (aim - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam


def render(path, samples, size):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def find_fbx(dirs, name):
    for d in dirs:
        p = os.path.join(d, name + ".fbx")
        if os.path.exists(p):
            return p
    return None


def manifests(dirs):
    m = {}
    for d in dirs:
        for fn in os.listdir(d):
            if fn.endswith("_manifest.json"):
                with open(os.path.join(d, fn)) as f:
                    m.update(json.load(f))
    return m


def main():
    a = args()
    os.makedirs(a["out"], exist_ok=True)
    dirs = [a["src"]] + a["dress"]
    man = manifests(dirs)
    names = sorted(fn[:-4] for fn in os.listdir(a["src"]) if fn.endswith(".fbx"))
    if a["only"]:
        names = [n for n in names if n in a["only"].split(",")]
    stats = {}
    for name in names:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        objs = import_mesh(os.path.join(a["src"], name + ".fbx"), name)
        lo, hi = bounds(objs)
        slots = man.get(name, {}).get("slots", [])
        tris = sum(len(p.vertices) - 2 for o in objs for p in o.data.polygons)
        st = {"tris": tris, "size": [round(hi[i] - lo[i], 3) for i in range(3)], "lo": [round(x, 3) for x in lo],
              "hi": [round(x, 3) for x in hi], "sockets": man.get(name, {}).get("sockets", {})}
        dressed = []
        for sock, s in st["sockets"].items():
            prefix = sock.rsplit("_", 1)[0]
            cands = [c for c in DRESS.get(prefix, []) if find_fbx(dirs, c)]
            if prefix == "boat" and a["boat"]:
                cands = [a["boat"]]
            if not cands or a["undressed"]:
                continue
            pick = hpick(name + sock, cands)
            dressed += import_mesh(find_fbx(dirs, pick), pick + sock, s["at"], s["yaw"])
            st.setdefault("dressed", {})[sock] = pick
        stats[name] = st
        stage(a["setting"], max(hi - lo))
        target = (lo + hi) / 2
        d = os.path.join(a["out"], name)
        os.makedirs(d, exist_ok=True)
        for light in a["lights"]:
            sky(light)
            for dist in a["dists"]:
                # distances are from the structure's lake end (docks: the boat is that far off it) or the prop's centre
                tgt = Vector((hi.x, 0.5 * (lo.y + hi.y), target.z)) if a["setting"] == "water" else target
                # the 3 m still is the build's own detail: the dressing (boats, ports) is hidden so it can't block it
                for o in dressed:
                    o.hide_render = dist < 5 and a["setting"] == "water"
                # on a lawn the distance is from the prop's nearest side, so a trailer and a mailbox frame alike
                reach = dist if a["setting"] == "water" else dist + 0.5 * max(hi.x - lo.x, hi.y - lo.y)
                camera(tgt, reach, a["bearing"], a["setting"], None)
                render(os.path.join(d, f"{light}_{int(dist)}m.png"), a["samples"], a["size"])
        if a["clay"]:
            for o in objs + dressed:
                for ms in o.material_slots:
                    ms.material = look("", "", clay=True)
            sky("overcast")
            tgt = Vector((hi.x, 0.5 * (lo.y + hi.y), target.z)) if a["setting"] == "water" else target
            camera(tgt, 15.0 if a["setting"] == "water" else 3.0, a["bearing"] + 20, a["setting"], None)
            render(os.path.join(d, "clay.png"), a["samples"], a["size"])
        print(f"Envloop: {name} {st['tris']} tris, {st['size']} m, slots {slots}")
        st["slots"] = slots
    with open(os.path.join(a["out"], "stats.json"), "w") as f:
        json.dump(stats, f, indent=1, sort_keys=True)


main()
