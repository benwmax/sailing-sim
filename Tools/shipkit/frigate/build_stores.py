"""Builds and checks the frigate's below-decks stores kit (stores.py, stores_1797.json; docs/shipkit-stores).

    python -I build_stores.py <out dir> [--render [--res 900] [--only Name,Name]]

Writes <out>/stores.blend (each item one object in its own frame in the collection StoresKit, laid out side by side
for a look by their 'Show' empties' offsets; the assemblies in StoresAssemblies: a hammock on its two hooks, the magazine's
rack with its barrels, the cartridge rack filled, a butt on its bilge between its quoins, each copy a linked mesh)
and <out>/stores.json: for each item its box (min and max, metres in its frame), its rests, attach points, slots, its
triangles against the card's figure, its materials and its checks. --render writes <out>/renders/<item>.jpg (each item
alone, Cycles on the CPU) and the assemblies, for docs/shipkit-stores.

Checks (each item, then each assembly; the build fails on any):
* closed: every edge of every piece meets exactly two faces, the two running opposite ways (the piece is closed and
  its faces agree), and every closed piece of it encloses a positive volume (faces out);
* crossing: no piece crosses itself (two of its triangles that share no corner meeting: a fold, or two of its solids
  running into each other);
* room (deck.room): no two pieces meet unless stores_1797.json's meets lists the pair, and those listed meet no deeper
  than it allows and do meet (a designed contact the build no longer finds fails it); an item that stands on the deck
  stands on it (its feet on z 0, nothing hanging just over it)."""
import fnmatch
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import deck  # noqa: E402
import stores  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
OUT = ARGS[0] if ARGS and not ARGS[0].startswith("--") else os.path.join(HERE, "out_stores")
RENDER = "--render" in ARGS
RES = int(ARGS[ARGS.index("--res") + 1]) if "--res" in ARGS else 900
ONLY = ARGS[ARGS.index("--only") + 1].split(",") if "--only" in ARGS else None
os.makedirs(OUT, exist_ok=True)
IN = stores.IN

# the build's paints (build_frigate.py PAINT: the same names and values; Ash, Tin and Fleece are slice 12's)
PAINT = {
    "Interior": ((0.66, 0.60, 0.50), 0.7, 0.0), "Iron": ((0.05, 0.05, 0.05), 0.5, 0.6),
    "Hemp": ((0.35, 0.28, 0.18), 0.85, 0.0), "Tarred": ((0.055, 0.045, 0.035), 0.75, 0.0),
    "Shadow": ((0.008, 0.007, 0.006), 0.9, 0.0), "Oak": ((0.30, 0.20, 0.11), 0.7, 0.0),
    "Canvas": ((0.55, 0.50, 0.40), 0.9, 0.0), "Copper": ((0.62, 0.36, 0.22), 0.35, 1.0),
    "Blacking": ((0.035, 0.035, 0.037), 0.55, 0.0), "Ash": ((0.55, 0.45, 0.32), 0.6, 0.0),
    "Fleece": ((0.70, 0.66, 0.58), 0.95, 0.0), "Tin": ((0.55, 0.55, 0.56), 0.4, 1.0),
}

bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
SC.unit_settings.system = "METRIC"
MATS = {}
for name, (rgb, rough, metal) in PAINT.items():
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    MATS[name] = m


# ---- checks ---------------------------------------------------------------------------------------------------------------
def triangles(part):
    V, F, M, U = part.arrays()
    T = []
    for f in F:
        for k in range(1, len(f) - 1):
            T.append((f[0], f[k], f[k + 1]))
    return V, np.array(T, int).reshape(-1, 3)


def welded(V, T, eps=1e-6):
    key = np.round(V / eps).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    return inv.reshape(-1)[T]


def closed_check(V, T):
    """open or disagreeing edges, and closed pieces enclosing no positive volume"""
    W = welded(V, T)
    E = np.concatenate([W[:, [0, 1]], W[:, [1, 2]], W[:, [2, 0]]])
    E = E[E[:, 0] != E[:, 1]]
    fw = {}
    for a, b in map(tuple, E):
        fw[(a, b)] = fw.get((a, b), 0) + 1
    bad = 0
    for (a, b), n in fw.items():
        if n != 1 or fw.get((b, a), 0) != 1:
            bad += 1
    lab = deck.islands(W, int(W.max()) + 1)
    vol = {}
    for t, (a, b, c) in zip(T, W):
        k = lab[a]
        vol[k] = vol.get(k, 0.0) + float(np.dot(V[t[0]], np.cross(V[t[1]], V[t[2]]))) / 6.0
    inside_out = sum(1 for v in vol.values() if v <= 0)
    return {"open_or_disagreeing_edges": bad, "inside_out_solids": inside_out, "solids": len(vol)}


def self_crossing(V, T):
    """pairs of a piece's triangles that meet but share no corner (welded)"""
    W = welded(V, T)
    tr = BVHTree.FromPolygons(V.tolist(), T.tolist(), all_triangles=True)
    n = 0
    worst = None
    for i, j in tr.overlap(tr):
        if i >= j:
            continue
        if set(W[i]) & set(W[j]):
            continue
        n += 1
        worst = worst or np.round(V[T[i]].mean(0), 4).tolist()
    return n, worst


def stands_check(objs, names, tol=0.01 * IN):
    """an item standing on the deck: its lowest point on z 0, and the middle of its vertices (plan) over the outline of
    what touches the deck (within half an inch, for a round thing lying on a line)"""
    V = np.concatenate([objs[n][0] for n in names])
    zmin = float(V[:, 2].min())
    foot = V[V[:, 2] <= zmin + tol][:, :2]
    c = V[:, :2].mean(0)
    off = 0.0
    if len(foot) >= 3:
        from scipy.spatial import ConvexHull, QhullError
        try:
            h = ConvexHull(foot)
            # the distance outside the hull (0 inside)
            eq = h.equations
            off = max(0.0, float((eq[:, :2] @ c + eq[:, 2]).max()))
        except QhullError:                                   # the feet in a line: the distance off that line
            d = foot.max(0) - foot.min(0)
            u = d / max(np.linalg.norm(d), 1e-12)
            r = c - foot.mean(0)
            off = float(abs(r[0] * u[1] - r[1] * u[0]))
    else:
        off = float(np.linalg.norm(c - foot.mean(0)))
    return {"lowest_in": round(zmin / IN, 3), "middle_off_feet_in": round(off / IN, 2),
            "fail": bool(abs(zmin) > tol or off > 0.5 * IN)}


def run_checks(name, pieces, stands, meets):
    """the closed, crossing and room checks for pieces {name: Part}; returns (report, failures)"""
    objs, fails, rep = {}, [], {"pieces": {}}
    for pn, part in pieces.items():
        V, T = triangles(part)
        objs[pn] = (V, T)
        cc = closed_check(V, T)
        nx, where = self_crossing(V, T)
        rep["pieces"][pn] = {"triangles": int(len(T)), **cc, "crossing_itself": nx}
        if cc["open_or_disagreeing_edges"] or cc["inside_out_solids"]:
            fails.append(f"{name}.{pn}: not closed or faces in ({cc})")
        if nx:
            fails.append(f"{name}.{pn}: crosses itself ({nx} pairs, first near {where})")
    # a tiny solid far off, so deck.room has something that is not the item's (it needs one)
    objs["_far"] = (np.array([[100.0, 100, 100], [100.01, 100, 100], [100, 100.01, 100], [100, 100, 100.01]]),
                    np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]]))
    # the meets: a pair names two pieces, or patterns (fnmatch: an assembly's 'PowderBarrel#*.Cask'), expanded to the
    # pairs present
    names = [k for k in objs if k != "_far"]
    mt, want = {}, []
    for a, b, why, depth in meets:
        A = [n for n in names if fnmatch.fnmatchcase(n, a)]
        B = [n for n in names if fnmatch.fnmatchcase(n, b)]
        if not A or not B:
            fails.append(f"{name}: the meet {a} / {b} names no piece")
        for x in A:
            for y in B:
                if x != y:
                    mt[(x, y)] = (why, depth)
        want.append((a, b, why, A, B))
    rm = deck.room(objs, names, None, near=0.3, meets=mt)
    rep["room"] = rm
    for m_ in rm["meet"]:
        fails.append(f"{name}: {m_[0]} meets {m_[1]} " + (m_[3] if len(m_) > 3 else f"({m_[2]} pairs), not by design"))
    found = {(a, b) for a, b, *_ in rm["by_design"]} | {(b, a) for a, b, *_ in rm["by_design"]}
    for a, b, why, A, B in want:
        # each piece on the first side meets one on the other (every barrel its chocks)
        for x in A:
            if not any((x, y) in found for y in B):
                fails.append(f"{name}: {x} should meet {b} ({why}) and does not")
    if stands:
        rep["stands"] = stands_check(objs, names)
        if rep["stands"]["fail"]:
            fails.append(f"{name}: does not stand on the deck ({rep['stands']})")
    return rep, fails


# ---- Blender ------------------------------------------------------------------------------------------------------------------
def make_mesh(name, part):
    V, F, M, U = part.arrays()
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V], [], [list(map(int, f)) for f in F])
    names = sorted(set(M))
    for n in names:
        me.materials.append(MATS[n])
    idx = {n: i for i, n in enumerate(names)}
    me.polygons.foreach_set("material_index", [idx[m] for m in M])
    # UVs: the parts' own (u, v metres: round and along a turned piece, along and across the cloth) where they gave
    # them, else box-projected metres by each face's normal (what the texture lane's trim sheets take)
    uv = me.uv_layers.new(name="UVMap")
    loops = []
    for f in F:
        P = V[list(f)]
        nrm = np.cross(P[1] - P[0], P[-1] - P[0])
        ax = int(np.argmax(np.abs(nrm)))
        for i in f:
            if np.any(U[i, :2] != 0):
                loops.append((U[i, 0], U[i, 1]))
            else:
                p = V[i]
                loops.append((p[1], p[2]) if ax == 0 else (p[0], p[2]) if ax == 1 else (p[0], p[1]))
    uv.data.foreach_set("uv", np.array(loops, float).ravel())
    me.validate()
    # turned and rope surfaces shade smooth, edges sharper than 40 deg stay sharp (a box's corners, a hoop's step)
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(40.0))
    return me


def turn_matrix(turn_deg, at):
    rx, ry, rz = (math.radians(a) for a in turn_deg)
    R = Matrix.Rotation(rz, 4, "Z") @ Matrix.Rotation(ry, 4, "Y") @ Matrix.Rotation(rx, 4, "X")
    return Matrix.Translation(Vector(at)) @ R


def placed(part, Mx):
    """a copy of part moved by the 4x4 Mx (for the assemblies' checks)"""
    P = deck.Part()
    V, F, M, U = part.arrays()
    A = np.array(Mx)
    V2 = V @ A[:3, :3].T + A[:3, 3]
    P.V, P.F, P.M, P.U, P.n = [V2], list(F), list(M), [U], len(V2)
    return P


# ---- build ------------------------------------------------------------------------------------------------------------------
kit = stores.Kit()
C = kit.c
items = kit.build()
meets_all = C["meets"]["items"]
budget = C["budget_tris"]
coll = bpy.data.collections.new("StoresKit")
SC.collection.children.link(coll)
meshes, report, failures = {}, {"items": {}, "assemblies": {}}, []
x_show = 0.0
for name, it in items.items():
    rep, fails = run_checks(name, it.pieces, it.stands, meets_all.get(name, []))
    failures += fails
    P = it.merged()
    me = make_mesh(name, P)
    meshes[name] = me
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    lo, hi = it.box()
    ob.location = (x_show - lo[0], 0.0, 0.0)
    x_show += (hi[0] - lo[0]) + 0.4
    key = "hammock_slung" if name == "HammockSlung" else "cask" if name.startswith("Cask_") or name == "PowderBarrel" \
        else "each"
    tris = P.tris()
    report["items"][name] = {
        "note": it.note, "box_m": [np.round(lo, 4).tolist(), np.round(hi, 4).tolist()],
        "size_m": np.round(hi - lo, 4).tolist(), "size_in": np.round((hi - lo) / IN, 2).tolist(),
        "stands_on_deck": it.stands, "rests": it.rests, "attach_m": it.attach, "slots": it.slots,
        "triangles": tris, "budget_triangles": budget[key], "materials": sorted(set(P.M)), "info": it.info,
        "pieces": rep["pieces"], "by_design": rep["room"]["by_design"],
    }

# ---- assemblies ----------------------------------------------------------------------------------------------------------
acoll = bpy.data.collections.new("StoresAssemblies")
SC.collection.children.link(acoll)
y_show = -3.0


def assembly(aname, members, meets):
    """members [(item name, 4x4)]: each copy a linked object; the copies' pieces checked against each other"""
    global y_show
    pieces = {}
    for k, (iname, Mx) in enumerate(members):
        it = items[iname]
        for pn, part in it.pieces.items():
            pieces[f"{iname}#{k}.{pn}"] = placed(part, Mx)
    rep, fails = run_checks(aname, pieces, stands=False, meets=meets)
    report["assemblies"][aname] = {"members": [m[0] for m in members], "room": rep["room"],
                                   "triangles_drawn": int(sum(items[m[0]].merged().tris() for m in members))}
    failures.extend(fails)
    sub = bpy.data.collections.new(aname)
    acoll.children.link(sub)
    for k, (iname, Mx) in enumerate(members):
        ob = bpy.data.objects.new(f"{aname}_{iname}_{k}", meshes[iname])
        ob.matrix_world = Matrix.Translation(Vector((0.0, y_show, 0.0))) @ Mx
        sub.objects.link(ob)
    y_show -= 3.0


# a hammock on its two hooks: each hook turned so its bight lies on the hammock's attach point, the hook's open side
# toward the hammock
hm = items["HammockSlung"]
hk = items["HammockHook"]
bx, _, bz = hk.attach["bight"]
mem = [("HammockSlung", Matrix.Identity(4))]
for tag, s in (("hook_aft", -1.0), ("hook_fore", 1.0)):
    p = Vector(hm.attach[tag])
    # the hook's bight is at +x of its plate; turn the aft hook 180 deg so its bight points forward (to the hammock)
    R = Matrix.Rotation(0.0 if s < 0 else math.pi, 4, "Z")
    off = R @ Vector((bx, 0.0, bz))
    mem.append(("HammockHook", Matrix.Translation(p - off) @ R))
assembly("HammockOnHooks", mem, C["meets"]["assemblies"].get("HammockOnHooks", []))

# the magazine's rack with its barrels
mr = items["MagazineRack"]
mem = [("MagazineRack", Matrix.Identity(4))]
for s in mr.slots:
    mem.append((s["item"], turn_matrix(s["turn_deg"], s["at_m"])))
assembly("MagazineRackFilled", mem, C["meets"]["assemblies"].get("MagazineRackFilled", []))

# the cartridge rack filled
cr = items["CartridgeRack"]
mem = [("CartridgeRack", Matrix.Identity(4))]
for s in cr.slots:
    mem.append((s["item"], turn_matrix(s["turn_deg"], s["at_m"])))
assembly("CartridgeRackFilled", mem, C["meets"]["assemblies"].get("CartridgeRackFilled", []))

# a butt on its bilge, chocked with a quoin each side under each bilge hoop, the quoin's slope bearing on the hoop
bt = items["Cask_Butt"]
ob_ = bt.rests["on_bilge"]
D, d, L, _ = kit.cask_size("Butt")
Mc = turn_matrix(ob_["turn_deg"], [-L / 2, 0.0, ob_["lift_m"]])     # turned about Y: its foot at -L/2, along +X
mem = [("Cask_Butt", Mc)]
qL, qW, qH = (v * IN for v in C["casks"]["quoin"]["size_in"])
toe = 0.6 * IN
ro = ob_["lift_m"]
bite = 0.05 * IN                                                     # how far the slope is pressed into the hoop


def slope_gap(yc, rh):
    """the distance from the hoop's round (radius rh, centre y 0, z ro) to the quoin's slope, its middle at yc > 0, toe
    to -y, less the hoop's radius"""
    A = np.array([yc + qL / 2, qH])                                  # the heel's top
    B = np.array([yc - qL / 2, toe])                                 # the toe's top
    P = np.array([0.0, ro])
    t = np.clip((P - A) @ (B - A) / ((B - A) @ (B - A)), 0.0, 1.0)
    return float(np.linalg.norm(P - (A + t * (B - A)))) - rh


for zc, w, rh in bt.info["hoops_m"]:
    if 0.2 * L < zc < 0.8 * L:
        lo_, hi_ = 0.0, ro + qL
        for _ in range(60):
            m_ = 0.5 * (lo_ + hi_)
            if slope_gap(m_, rh) > -bite:
                hi_ = m_
            else:
                lo_ = m_
        x = -L / 2 + zc
        for s in (-1.0, 1.0):
            # +X of the quoin (its toe) toward the cask's middle
            R = Matrix.Rotation(math.radians(-90.0 if s > 0 else 90.0), 4, "Z")
            mem.append(("Quoin", Matrix.Translation(Vector((x, s * hi_, 0.0))) @ R))
assembly("ButtChocked", mem, C["meets"]["assemblies"].get("ButtChocked", []))

# ---- write -------------------------------------------------------------------------------------------------------------------
report["failures"] = failures
report["frame_note"] = C["frame_note"]
json.dump(report, open(os.path.join(OUT, "stores.json"), "w"), indent=1, default=lambda o: o.tolist()
          if hasattr(o, "tolist") else str(o))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "stores.blend"))
for name, r in report["items"].items():
    s = r["size_in"]
    print(f"{name:22s} {s[0]:7.2f} x {s[1]:6.2f} x {s[2]:6.2f} in  {r['triangles']:6d} tris (card {r['budget_triangles']})")
for a, r in report["assemblies"].items():
    print(f"{a:22s} {r['triangles_drawn']} tris drawn")
if failures:
    print("\n".join(["FAILED:"] + failures[:80]))
    if len(failures) > 80:
        print(f"... and {len(failures) - 80} more")

# ---- renders -----------------------------------------------------------------------------------------------------------------
if RENDER:
    rd = os.path.join(OUT, "renders")
    os.makedirs(rd, exist_ok=True)
    SC.render.engine = "CYCLES"
    SC.cycles.device = "CPU"
    SC.cycles.samples = 64
    SC.cycles.use_denoising = True
    SC.render.resolution_x = RES
    SC.render.resolution_y = int(RES * 0.66)
    SC.render.image_settings.file_format = "JPEG"
    SC.render.image_settings.quality = 90
    SC.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in SC.view_settings.bl_rna.properties[
        "view_transform"].enum_items] else "Filmic"
    world = bpy.data.worlds.new("Studio")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.42, 0.42, 0.44, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    SC.world = world
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3.0
    sun.data.angle = math.radians(8)
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))
    SC.collection.objects.link(sun)
    floor_me = bpy.data.meshes.new("Floor")
    floor_me.from_pydata([(-50, -50, 0), (50, -50, 0), (50, 50, 0), (-50, 50, 0)], [], [(0, 1, 2, 3)])
    fm = bpy.data.materials.new("FloorMat")
    fm.use_nodes = True
    fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.36, 0.33, 0.29, 1)
    floor_me.materials.append(fm)
    floor = bpy.data.objects.new("Floor", floor_me)
    SC.collection.objects.link(floor)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.lens = 50
    SC.collection.objects.link(cam)
    SC.camera = cam
    all_obs = [o for o in SC.objects if o.type == "MESH" and o.name != "Floor"]

    def show_only(obs, floor_z=0.0):
        for o in all_obs:
            o.hide_render = o not in obs
        floor.location = (0, 0, floor_z)

    def frame(obs, az=35.0, el=24.0, pad=1.25):
        pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
        lo = Vector([min(p[i] for p in pts) for i in range(3)])
        hi = Vector([max(p[i] for p in pts) for i in range(3)])
        mid = (lo + hi) / 2
        r = (hi - lo).length / 2 * pad
        dist = r / math.tan(cam.data.angle / 2) * 1.05
        a, e = math.radians(az), math.radians(el)
        d = Vector((math.cos(e) * math.cos(a), -math.cos(e) * math.sin(a), math.sin(e)))
        cam.location = mid + d * dist
        cam.rotation_euler = (mid - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.clip_start = max(0.01, dist / 200)
        return lo

    for name in items:
        if ONLY and name not in ONLY:
            continue
        ob = bpy.data.objects[name]
        show_only([ob], floor_z=min((ob.matrix_world @ Vector(c)).z for c in ob.bound_box))
        frame([ob], pad=0.62 if name == "HammockSlung" else 1.25, el=30.0 if name == "HammockSlung" else 24.0)
        SC.render.filepath = os.path.join(rd, name + ".jpg")
        bpy.ops.render.render(write_still=True)
    for sub in acoll.children:
        if ONLY and sub.name not in ONLY:
            continue
        obs = list(sub.objects)
        show_only(obs, floor_z=min((o.matrix_world @ Vector(c)).z for o in obs for c in o.bound_box) - 0.002)
        frame(obs, az=30.0, el=20.0)
        SC.render.filepath = os.path.join(rd, sub.name + ".jpg")
        bpy.ops.render.render(write_still=True)

sys.exit(1 if failures else 0)
