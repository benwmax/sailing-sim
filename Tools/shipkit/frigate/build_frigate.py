"""Builds the frigate Commonwealth in Blender (docs/shipkit-1 to docs/shipkit-4).

Slice 1 lofted the moulded hull (the frames' outside, as the 1927 lines give it). Slice 2 planks it (skin.py): copper
to the main wale, the wales, black strakes, the ochre port band, the bulwarks to the rail, the gun deck and spar deck
ports with their linings and lids, the rail cap, the plankshear moulding, the channels, the entry steps, the rudder
and its irons, and placeholder decks and bulkheads for the later slices. Slice 3 (spars.py, spars_1795.json) masts
her: lower masts, tops, caps, topmasts, topgallant masts, every yard, the spanker boom and gaff, the bowsprit and
jibbooms. Each yard, the boom, the gaff and the spritsail yard is its own object with its origin on the axis it turns
about (local Z up that axis): <out>/rig.json lists how far each one braces and hoists. Slice 4 (rigging.py,
standing_1797.json) sets up the standing rigging: shrouds, deadeyes, lanyards, chains, ratlines, futtock shrouds,
backstays, stays and the bowsprit's shrouds, martingales and guys; then each moving spar is swung against it (and the
masts and hull) to find how far it braces, hoisted, lowered and between (brace_limits).

    python build_frigate.py <out dir>        (Blender's Python: pip bpy, or blender -b -P build_frigate.py -- <out>)

Writes <out>/frigate.blend, <out>/frigate.obj (the moulded hull, transom and backbone, for lines_check.py),
<out>/build.json (triangles per object, main dimensions, displacement, the rig's heights) and <out>/rig.json. Units are metres in Unreal's body frame
(X forward, Y starboard, Z up), origin on the centreline at midships on the load waterline. The moulded hull stays in
the .blend as "Hull", hidden from renders: the shape tools measure it. Edit loft.py, skin.py, offsets.json and
specs_1795.json, spars.py and spars_1795.json, rigging.py and standing_1797.json, never the .blend.
"""
import json
import math
import os
import sys

import bpy
import bmesh
from mathutils import Matrix
from mathutils.bvhtree import BVHTree
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import loft  # noqa: E402
import rigging  # noqa: E402
import skin  # noqa: E402
import spars  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
OUT = ARGS[0] if ARGS else os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
SC.unit_settings.system = "METRIC"


def material(name, rgb, rough=0.6):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def make(name, V, F, mat):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V], [], [list(map(int, f)) for f in F])
    me.validate()
    ob = bpy.data.objects.new(name, me)
    SC.collection.objects.link(ob)
    me.materials.append(mat)
    return ob


def weld(ob, dist=0.0005):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=dist)
    bm.to_mesh(ob.data)
    bm.free()


def smooth(ob, angle=30):
    me = ob.data
    me.shade_smooth()
    if hasattr(me, "set_sharp_from_angle"):
        me.set_sharp_from_angle(angle=math.radians(angle))


L = loft.Lines()
H = loft.Hull(L).build()
parts = loft.mesh(L, H)

# paint as built (1797): a black side with an ochre band along the gun ports and black lids (the chequer of the
# period), copper to the main wale, red inside the bulwarks and ports. Plain colours: textures are the texture loop's
PAINT = {
    "Copper": ((0.62, 0.36, 0.22), 0.35, 1.0),
    "HullBlack": ((0.03, 0.028, 0.026), 0.55, 0.0),
    "HullOchre": ((0.60, 0.44, 0.17), 0.6, 0.0),
    "HullRed": ((0.40, 0.07, 0.045), 0.6, 0.0),
    "Interior": ((0.66, 0.60, 0.50), 0.7, 0.0),
    "Deck": ((0.58, 0.52, 0.42), 0.75, 0.0),
    "Iron": ((0.05, 0.05, 0.05), 0.5, 0.6),
    "Bronze": ((0.55, 0.40, 0.22), 0.35, 1.0),
    "Spar": ((0.50, 0.36, 0.20), 0.5, 0.0),
    # the standing rigging (slice 4): tarred hemp, untarred lanyards, elm deadeyes and hearts, their holes in shadow
    "Tarred": ((0.055, 0.045, 0.035), 0.75, 0.0),
    "Hemp": ((0.35, 0.28, 0.18), 0.85, 0.0),
    "Deadeye": ((0.16, 0.10, 0.055), 0.6, 0.0),
    "Shadow": ((0.008, 0.007, 0.006), 0.9, 0.0),
}
MATS = {}
for name, (rgb, rough, metal) in PAINT.items():
    m = material(name, rgb, rough)
    m.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = metal
    MATS[name] = m
CLAY = material("Clay_Hull", (0.55, 0.53, 0.5))


def make_painted(name, V, F, M):
    """One object, a material slot per paint used, each face on its paint's slot."""
    names = sorted(set(M))
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V], [], [list(map(int, f)) for f in F])
    for n in names:
        me.materials.append(MATS[n])
    idx = {n: i for i, n in enumerate(names)}
    me.polygons.foreach_set("material_index", [idx[m] for m in M])
    me.validate()
    ob = bpy.data.objects.new(name, me)
    SC.collection.objects.link(ob)
    return ob


def mirrored(V, F, M):
    """A starboard part and its port twin as one mesh (y flipped, faces turned so they still face out)."""
    V = np.asarray(V, float)
    Vp = V * np.array([1.0, -1.0, 1.0])
    n = len(V)
    return np.concatenate([V, Vp]), list(F) + [tuple(n + i for i in f[::-1]) for f in F], list(M) + list(M)


# the moulded hull: both sides and the wing transom's underside as one welded surface. It is the drawing's line and
# what lines_check and the shape tools measure; the planking covers it, so it is hidden from renders
objs = [make(n, *parts[n], CLAY) for n in ("Hull_Stbd", "Hull_Port")]
bpy.ops.object.select_all(action="DESELECT")
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.join()
hull = bpy.context.view_layer.objects.active
hull.name = hull.data.name = "Hull"
weld(hull)
smooth(hull)
hull.hide_render = True
hull.hide_set(True)

# the transom (moulded, black; the stern windows and carvings go on it in slice 9)
transom = make("Transom", *parts["Transom"], MATS["HullBlack"])
weld(transom)
smooth(transom)

# the planked ship
# the rig first: the stem head is cut down to the bowsprit's bed
RIG = spars.Rig(L, json.load(open(os.path.join(HERE, "specs_1795.json")))).build()
SK = skin.Skin(L, stem_bed=RIG.stem_bed).build()
SKIN = SK.parts()
LIDS = []
for name, (V, F, M, side) in SKIN.items():
    if name.startswith("Lid_"):
        LIDS.append(name)
        continue
    if side == "stbd":
        V, F, M = mirrored(V, F, M)
    ob = make_painted(name, V, F, M)
    smooth(ob, 40 if name in ("Backbone", "Rudder") else 30)

# the gun port lids: an object each side, its origin on the hinge axis (through the knuckles) with X along it and Z out
# of the side, so on either side a positive turn about the lid's own X opens it outward. Port lids are the starboard
# ones mirrored; their X points aft so the frame stays right-handed and opens the same way (Y points down on both)
for name in LIDS:
    V, F, M, _ = SKIN[name]
    o, xa, za = SK.lid_frame(name)
    for suffix, sgn in (("S", 1.0), ("P", -1.0)):
        flip = np.array([1.0, sgn, 1.0])
        oo, xx, zz = o * flip, xa * flip * sgn, za * flip
        yy = np.cross(zz, xx)
        R = np.stack([xx, yy, zz], 1)                 # columns: the lid's axes in the ship
        Vw = np.asarray(V, float) * flip
        Vl = (Vw - oo) @ R
        Fs = list(F) if sgn > 0 else [f[::-1] for f in F]
        ob = make_painted(f"{name}_{suffix}", Vl, Fs, M)
        ob.matrix_world = Matrix(((*R[0], oo[0]), (*R[1], oo[1]), (*R[2], oo[2]), (0, 0, 0, 1)))
        smooth(ob, 30)

# the masts and yards (slice 3): masts, tops and the bowsprit where they stand; each yard, the spanker boom and gaff on
# its own frame, origin on the axis it turns about
for name, (V, F, M, frame) in RIG.parts().items():
    ob = make_painted(name, V, F, M)
    if frame is not None:
        o, R = frame
        ob.matrix_world = Matrix(((*R[0], o[0]), (*R[1], o[1]), (*R[2], o[2]), (0, 0, 0, 1)))
    smooth(ob, 35)

# the standing rigging (slice 4): built in place, both sides in each object
ST = rigging.Standing(RIG, SK).build()
for name, (V, F, M, _) in ST.parts().items():
    smooth(make_painted(name, V, F, M), 40)
for name, low in ST.yard_rests().items():          # a royal yard lowered rests on the topgallant rigging's eyes
    RIG.meta[name]["hoist_m"][0] = low


def brace_limits(cfg):
    """How far each yard, the spanker boom and gaff and the spritsail yard braces before it touches the standing
    rigging, a mast, a top or the hull (cfg: standing_1797.json's "brace"). Each part is turned about its axis in
    steps from square, each way, at each hoist (0 lowered, 1 hoisted). A lower yard's truss and a topsail yard's
    parrel let it come forward as it braces (to cfg's ease_max_ft): at each step it is eased forward, an inch at a
    time, until it clears. Its limit at a hoist is the last clear angle less the margin, at most cfg's top. Then the
    ease the part needs at each angle and hoist (the more either side needs, taken a step early) is tried again at
    the angles between the steps, and between the hoists (interpolated, against the smaller of the two limits), and a
    limit is cut back where that ease fails. Returns {part: {"by_hoist": [[hoist, lo, hi], ...], "ease_m": [[deg,
    m], ...] (hoisted), "ease_m_by_hoist": [[hoist, [[deg, m], ...]], ...], "touches": [[hoist, sign, object, deg],
    ...]}}."""
    step, top, margin = cfg["step_deg"], cfg["top_deg"], cfg["margin_deg"]
    e_step = cfg["ease_step_in"] * loft.FT / 12
    still = [o for o in SC.objects if o.type == "MESH" and o.name not in RIG.meta and o.name != "Hull"]
    Vs, Fs, owner = [], [], []
    n0 = 0
    for o in still:
        Mw = np.array(o.matrix_world)
        V = np.array([v.co for v in o.data.vertices]) @ Mw[:3, :3].T + Mw[:3, 3]
        o.data.calc_loop_triangles()
        T = np.array([t.vertices for t in o.data.loop_triangles], int)
        Vs.append(V)
        Fs.append(T + n0)
        owner += [o.name] * len(T)
        n0 += len(V)
    V_all, F_all = np.concatenate(Vs), np.concatenate(Fs)
    still_tree = BVHTree.FromPolygons(V_all.tolist(), F_all.tolist(), all_triangles=True)

    def kind(name):
        for k in ("Topsail", "Topgallant", "Royal", "Spanker", "Spritsail"):
            if k in name:
                return k.lower()
        return "lower"
    out, square = {}, []
    for name, m in RIG.meta.items():
        o = SC.objects[name]
        o.data.calc_loop_triangles()
        T = np.array([t.vertices for t in o.data.loop_triangles], int).tolist()
        Mw = np.array(o.matrix_world)
        Vl = np.array([v.co for v in o.data.vertices]) @ Mw[:3, :3].T          # about the origin, in the ship's axes
        org, ax, fwd = Mw[:3, 3], np.array(m["axis"], float), Mw[:3, 0] / np.linalg.norm(Mw[:3, 0])
        K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
        e_max = cfg["ease_max_ft"][kind(name)] * loft.FT

        def touch(o_h, deg, e):
            th = math.radians(deg)
            Rm = np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * (K @ K)
            ov = BVHTree.FromPolygons((Vl @ Rm.T + o_h + fwd * e).tolist(), T, all_triangles=True).overlap(still_tree)
            return ov[0][1] if ov else None
        hs = cfg["hoists"] if m["hoist_m"][0] != 0.0 else [1.0]
        lims, need, touches = {}, [], []
        for h in hs:
            o_h = org + ax * (1.0 - h) * m["hoist_m"][0]
            for sgn in (1, -1):
                a, e, hit = 0.0, 0.0, None
                while a <= top + margin + 1e-9:
                    t = touch(o_h, sgn * a, e)
                    while t is not None and e + e_step <= e_max + 1e-9:
                        e += e_step
                        t = touch(o_h, sgn * a, e)
                    if t is not None:
                        hit = owner[t]
                        if a == 0.0:
                            where = V_all[list(F_all[t])].mean(0) / loft.FT
                            square.append(f"{name} at hoist {h} touches {hit} at {np.round(where, 2).tolist()} ft")
                        break
                    need.append((h, a, e))
                    a += step
                lims[(h, sgn)] = round(min(top, a - step - margin), 1) if hit else top
                if hit:
                    touches.append([h, sgn, hit, round(a, 1)])
        # each hoist's ease (both sides), a step ahead of where it was needed, kept where it grows
        grid = np.arange(0.0, top + step / 2, step)
        tables = {}
        for h in hs:
            e_of = np.array([max([e for hh, a, e in need if hh == h and abs(a - g - step) < 1e-6] + [0.0]) for g in grid])
            e_of = np.maximum.accumulate(e_of)
            tb = [[0.0, 0.0]] + [[float(g), round(float(e), 4)] for k, (g, e) in enumerate(zip(grid, e_of))
                                 if k > 0 and e > e_of[k - 1]]
            if tb[-1][1] > 0.0:
                tb.append([float(top), round(float(e_of[-1]), 4)])
            tables[h] = tb
        if any(tb[-1][1] > 0.0 for tb in tables.values()):
            def ease(deg, h):
                """the ease at |deg| and hoist h: each table's value, interpolated between the two hoists either side"""
                ev = [float(np.interp(abs(deg), [a for a, _ in tables[k]], [e for _, e in tables[k]])) for k in hs]
                return float(np.interp(h, hs, ev))
            # each hoist's limit again at half steps, then between hoists (taking the smaller limit) at quarter
            # hoists: a limit is cut back where the ease fails
            checks = [(h, h, h) for h in hs] + [(h0 + (h1 - h0) * q, h0, h1) for h0, h1 in zip(hs[:-1], hs[1:])
                                               for q in (0.25, 0.5, 0.75)]
            for hc, h0, h1 in checks:
                o_h = org + ax * (1.0 - hc) * m["hoist_m"][0]
                for sgn in (1, -1):
                    lim = min(lims[(h0, sgn)], lims[(h1, sgn)])
                    for a in np.arange(step / 2, lim + margin + 1e-9, step / 2):
                        t = touch(o_h, sgn * a, ease(a, hc))
                        if t is not None:
                            cut = round(max(0.0, a - step / 2 - margin), 1)
                            for hk in {h0, h1}:
                                lims[(hk, sgn)] = min(lims[(hk, sgn)], cut)
                            touches.append([round(hc, 3), sgn, owner[t] + " (eased)", round(float(a), 2)])
                            break
        else:
            tables = {}
        out[name] = {"by_hoist": [[h, -lims[(h, -1)], lims[(h, 1)]] for h in hs],
                     "ease_m": tables.get(hs[-1], []),
                     "ease_m_by_hoist": [[h, tables[h]] for h in hs] if len(hs) > 1 and tables else [],
                     "touches": touches}
    if square:
        raise RuntimeError("touching when square:\n" + "\n".join(square))
    return out


def span_room(end_m=0.3, every_m=0.02):
    """Each free straight run of standing rigging (Standing.spans: a shroud's or stay's leg between its head and its
    deadeye, heart or collar) against everything that isn't rigging: the hull, masts, tops, yards squared and hoisted,
    the bowsprit. Points every_m along it, less end_m at each end (where it is made fast), and the room between the
    rope's surface and the nearest surface; a run whose room goes under zero passes through something."""
    rig_objs = set(ST.meshes)
    Vs, Fs, n0 = [], [], 0
    for o in SC.objects:
        if o.type != "MESH" or o.name in rig_objs or o.name == "Hull":
            continue
        Mw = np.array(o.matrix_world)
        V = np.array([v.co for v in o.data.vertices]) @ Mw[:3, :3].T + Mw[:3, 3]
        o.data.calc_loop_triangles()
        Vs.append(V)
        Fs.append(np.array([t.vertices for t in o.data.loop_triangles], int) + n0)
        n0 += len(V)
    tree = BVHTree.FromPolygons(np.concatenate(Vs).tolist(), np.concatenate(Fs).tolist(), all_triangles=True)
    least, through = [], []
    for name, a, b, r in ST.spans:
        L = float(np.linalg.norm(b - a))
        if L < 2 * end_m + every_m:
            continue
        room = min(tree.find_nearest(a + (b - a) * t)[3] for t in np.arange(end_m, L - end_m, every_m) / L) - r
        least.append((room, name))
        if room < 0:
            through.append([name, round(room / 0.0254, 1)])
    least.sort()
    return {"spans": len(ST.spans), "through": through,
            "closest_in": [[n, round(c / 0.0254, 1)] for c, n in least[:8]]}


SPAN_ROOM = span_room()
BRACE = brace_limits(ST.sp["brace"])
for name, b in BRACE.items():
    hoisted = b["by_hoist"][-1]
    RIG.meta[name]["brace_deg"] = [hoisted[1], hoisted[2]]
    if len(b["by_hoist"]) > 1:
        RIG.meta[name]["brace_deg_by_hoist"] = b["by_hoist"]
    if b["ease_m"]:
        RIG.meta[name]["ease_m"] = b["ease_m"]
    if any(t[-1][1] > 0.0 for _, t in b["ease_m_by_hoist"]):
        RIG.meta[name]["ease_m_by_hoist"] = b["ease_m_by_hoist"]

# a sun and sky so a quick look in Blender isn't black (render_set.py brings its own)
SC.world = bpy.data.worlds.new("World")
SC.world.color = (0.6, 0.65, 0.7)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "frigate.blend"))
# the lines check reads the moulded surfaces only: the drawing's lines are the frames' outside, not the planking
loft.write_obj(os.path.join(OUT, "frigate.obj"), {n: parts[n] for n in ("Hull_Stbd", "Hull_Port", "Transom", "Backbone")})


def tris(ob):
    ob.data.calc_loop_triangles()
    return len(ob.data.loop_triangles)


def bounds(ob):
    P = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])
    return P.min(0).round(3).tolist(), P.max(0).round(3).tolist()


def displacement(L):
    """Moulded volume below the load waterline: each section's area (both sides, from the rabbet up to A) plus the
    keel and deadwood below the rabbet (the keel's siding), summed along x at 1 px."""
    k = L.k
    xa, xf = L.wl_ends["A"]
    vol_px = 0.0
    for x in np.arange(xa + 0.5, xf, 1.0):
        zb = L.rabbet_z(x)
        if zb >= 0:
            continue
        sec = L.section(x, "lower")
        zs = np.linspace(zb, 0, 200)
        vol_px += 2 * np.trapezoid(np.maximum(sec(zs), k), zs)
    keel = L.P["keel_bottom_z_px"]
    kx, kz = [p[0] for p in keel], [p[1] for p in keel]
    for x in np.arange(max(kx[0], xa), kx[-1], 1.0):
        zr = min(L.rabbet_z(x), 0.0)
        vol_px += 2 * k * max(0.0, zr - float(np.interp(x, kx, kz)))
    return vol_px / (L.ppf * L.ppf_y ** 2) * loft.FT ** 3     # x across the sheet, half-breadths and heights down it


REFERENCE = {"Hull"}           # measured, never drawn
stats = {"objects": {o.name: {"triangles": tris(o), "bounds_m": bounds(o)} for o in SC.objects if o.type == "MESH"}}
stats["triangles_model"] = sum(v["triangles"] for k, v in stats["objects"].items() if k not in REFERENCE)
stats["triangles_reference"] = sum(v["triangles"] for k, v in stats["objects"].items() if k in REFERENCE)
stats["dimensions"] = loft.summary(L, H)
sk_ob = SC.objects["Skin"]
P = np.array([v.co for v in sk_ob.data.vertices])
stats["dimensions"]["extreme_breadth_planked_ft"] = round(float(2 * P[:, 1].max()) / loft.FT, 2)
stats["dimensions"]["extreme_breadth_note"] = "outside the main wales: the moulded 43 ft 5 in plus two 7 in wales (specs_1795.json)"
vol = displacement(L)
stats["displacement"] = {"moulded_volume_m3": round(vol, 1), "seawater_tonnes": round(vol * 1.025, 0),
                         "long_tons": round(vol * 1.025 / 1.016, 0),
                         "note": "moulded (inside the planking); the planking and copper add about 3-4%. Constitution: about 2,200 long tons at 21 ft (designed)"}
stats["rig"] = RIG.summary()
stats["triangles_rig"] = sum(v["triangles"] for k, v in stats["objects"].items() if k in RIG.parts_)
stats["standing"] = ST.summary()
stats["triangles_rigging"] = sum(v["triangles"] for k, v in stats["objects"].items() if k in ST.meshes)
stats["brace"] = BRACE
stats["span_room"] = SPAN_ROOM
json.dump(stats, open(os.path.join(OUT, "build.json"), "w"), indent=1)
json.dump({"note": "each moving spar (docs/shipkit-3): origin_m on the axis it turns about (metres, ship frame) and that "
                   "axis (the object's local +Z); parent, the object it rides on; hoist_m, its offset along the axis "
                   "[lowered, hoisted] (negative is down; the model hangs it hoisted); brace_deg, the limits of a turn "
                   "about local +Z (right-handed: positive swings a square yard's starboard arm aft and the spanker "
                   "boom and gaff to port); port_tack_sign, the sign of the turn that trims it for the wind on the "
                   "port side (each yard's lee arm aft, the boom and gaff to leeward). Since slice 4 the limits are the standing "
                   "rigging's: brace_deg is the hoisted part's, brace_deg_by_hoist [hoist, lo, hi] the limits from "
                   "lowered (0) to hoisted (1) (between two, take the smaller); each is the last clear angle less 1 deg. ease_m "
                   "[[deg, m]] (lower and topsail yards, hoisted): as it braces, a yard's truss or parrel lets it come "
                   "forward: move its origin along its own +X by the table's value at |brace| (interpolated), then turn "
                   "it. ease_m_by_hoist [[hoist, [[deg, m]]]] (topsail yards): the same table at each hoist; between two "
                   "hoists, interpolate between their tables' values",
           "parts": RIG.meta}, open(os.path.join(OUT, "rig.json"), "w"), indent=1)
print(json.dumps(stats, indent=1))
