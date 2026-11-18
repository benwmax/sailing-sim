"""Commonwealth's light copy (slice 16, docs/shipkit-16): a lighter twin of every part seen from outside, for her at a
distance, held to one pixel of a 4K screen from 50 m out (light_1797.json).

    python -I Tools/shipkit/frigate/light.py <frigate.blend> [<out.blend>] [--only a,b] [--report light.json]
        [--shard i/n]                               # only the i-th of n shares of the meshes (largest dealt first)
    python -I Tools/shipkit/frigate/light.py <frigate.blend> <out.blend> --merge s0.blend,s1.blend --reports s0.json,s1.json

A whole ship is about 7 million triangles and takes hours in one process: run n shards side by side (one per core),
then merge them into the ship (their twins appended, the report made whole).

The work is the J-Class's (Tools/shipkit/jclass/light.py, loaded by path with this ship's settings in place of
Bluebonnet's): specks under a pixel left out, ropes and rods built again round their centrelines with the fewest sides,
the rest collapsed to the smallest share that keeps it within the tolerance with its paint lines in place, every twin's
normals and UVs carried from its part and each twin measured against it. What differs here:

  shared meshes  a gun's barrel, trucks and quoin are one mesh used by every gun (226 objects share 10 meshes): the
                 twin is made once per mesh and each object gets its own twin object sharing it, so the light copy
                 shares as the ship does (the export writes each shared mesh once);
  outside        every mesh but the hidden lofted hull and the decks below the gun deck (inside_collections): the gun
                 deck shows through the open waist and the ports, so its parts, the guns and the lids get twins;
  states         the ship's states are collections of the build (light_1797.json 'states'): each state's triangles,
                 detailed and light, are reported against the budget (a million, and a quarter of the detailed ship).

Every twin is '<part>_Light' in the collection 'Light', hidden, with 'light_of' naming its part, the part's frame,
parent, material slots and UV maps; the export (slice 17) writes each twin as its part's LOD 1.
"""
import importlib.util
import json
import math
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
JCLASS = os.path.join(HERE, "..", "jclass", "light.py")
LC = json.load(open(os.path.join(HERE, "light_1797.json")))


def _load():
    spec = importlib.util.spec_from_file_location("jclass_light", JCLASS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.LC = LC                              # this ship's tolerance, ratios and tube rules
    mod.SUITS = dict(LC["states"])
    return mod


JL = _load()
SUFFIX, COLLECTION = JL.SUFFIX, JL.COLLECTION
_plain_collapse = JL.collapse


def guarded_collapse(me, ratio, passes=4, reach=0.25):
    """The J-Class's collapse, held where it strays: Blender's quadric collapse is global, and on a big part one tight
    spot (the hull's hawse holes, a tackle's blocks hard against each other) can stray five centimetres at every share
    while the rest is within a millimetre, so the search keeps the whole part. Here each pass finds where the collapsed
    mesh strays past half the tolerance (either way: its points from the part, the part's from it) and holds the
    part's vertices within `reach` of those spots out of the next collapse (a vertex group at weight 0), so the rest
    still collapses to the share asked."""
    import numpy as np
    from scipy.spatial import cKDTree
    tol = JL.tolerance()
    V, T, _, _ = JL.arrays(me)
    if not len(T):
        return _plain_collapse(me, ratio)
    tr, kd = JL.tree(V, T), cKDTree(V)
    hp = JL.surface_points(V, T, 4 * tol)
    hb = _rim_points(me, 0.25 * tol)                     # the part's own open edges: the collapse must not open others
    hbk = cKDTree(hb) if len(hb) else None
    key = (len(V), len(T), round(float(V.sum()), 3))
    keep = _KEEP.get(key, np.zeros(len(V), dtype=bool)).copy()    # the spots held at one share, held at the next
    out = None
    for i in range(passes):
        ob = bpy.data.objects.new("_light_tmp", me)
        bpy.context.scene.collection.objects.link(ob)
        vg = ob.vertex_groups.new(name="light_collapse")
        free = np.where(~keep)[0].tolist()
        if free:
            vg.add(free, 1.0, "REPLACE")
        m = ob.modifiers.new("collapse", "DECIMATE")
        m.decimate_type, m.ratio, m.use_collapse_triangulate = "COLLAPSE", ratio, True
        if keep.any():
            m.vertex_group = vg.name
        if out is not None:
            bpy.data.meshes.remove(out)
        out = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        bpy.data.objects.remove(ob)
        if i == passes - 1:
            break
        cv, ct, _, _ = JL.arrays(out)
        if not len(ct):
            break
        lp = JL.surface_points(cv, ct, 4 * tol)            # points inside the faces too, as the measure takes them:
        d1, _ = JL.nearest(tr, lp)                          # a long face can bridge a hollow with its corners on
        d2, _ = JL.nearest(JL.tree(cv, ct), hp)             # the part (the counter, 45 mm off at its middle).
        if max((d1 > 0.5 * tol).mean(), (d2 > 0.5 * tol).mean()) > 0.02:   # (the tree's own nearest: it can only
            break                                           # overstate, so the guard errs safe) Strays all over: the
        bad = [lp[d1 > 0.5 * tol], hp[d2 > 0.5 * tol]]       # share is too small to hold, the search moves on
        lb = _rim_points(out, 0.25 * tol)                   # an open edge the part does not have (a metre off its own,
        if len(lb):                                         # amidships under the wale): held too
            bad.append(lb[hbk.query(lb)[0] > 0.5 * tol] if hbk is not None else lb)
        bad = np.concatenate(bad)
        if not len(bad):
            break
        bad = np.unique(np.round(bad / (0.25 * reach)), axis=0) * (0.25 * reach)   # one spot per cell: a stray
        for idx in kd.query_ball_point(bad, reach):                                  # band of many thousand points
            keep[idx] = True                                                         # took hours point by point
        if keep.mean() > 0.2:                               # held so much it cannot reach the share: let the search
            keep[:] = _KEEP.get(key, np.zeros(len(V), dtype=bool))   # move on to a larger one
            break
        print(f"  guard pass {i + 1} at {ratio}: {len(bad)} spots, {int(keep.sum())} of {len(V)} vertices held",
              flush=True)
    if keep.mean() <= 0.2:
        _KEEP[key] = keep
    return out


def _own_edges(me, step):
    """JL.own_edges with the part's pinched edges (more than two faces: sheets touching) counted as its own open edges:
    split_warped parts them before the collapse, and the twin's open edges along them lie exactly on the part's."""
    import numpy as np
    from scipy.spatial import cKDTree
    pts = _rim_points(me, step, pinched=True)
    return cKDTree(pts) if len(pts) else None


JL.own_edges = _own_edges


def _rim_points(me, step, pinched=True):
    """Points every `step` along the mesh's open edges (and its pinched ones)."""
    import bmesh
    import numpy as np
    bm = bmesh.new()
    bm.from_mesh(me)
    pts = []
    for e in bm.edges:
        if e.is_boundary or (pinched and len(e.link_faces) > 2):
            a, b = np.array(e.verts[0].co), np.array(e.verts[1].co)
            n = max(int(np.linalg.norm(b - a) / step), 1)
            pts.append(a + (b - a) * (np.arange(n + 1) / n)[:, None])
    bm.free()
    return np.vstack(pts) if pts else np.zeros((0, 3))


def fast_nearest(tr, P, V=None, T=None, check=None):
    """JL.nearest with its exact re-measure narrowed: the triangles grouped by size, each group's centres in a k-d
    tree, so a point is tested only against triangles whose centre lies within its radius plus the group's reach,
    instead of a box test against every triangle, which on the hull's skin (a million surface points against 266k
    triangles) took hours for one candidate (box-testing only the large ones still stalled its guarded candidates).
    Same answers (`light.py --check-nearest <part>` measures both; Blender's own range search missed slivers just as
    its nearest does, 0.8 m off on the stays). The re-measure looks no further than four tolerances: a worse candidate
    fails either way, and its reported error is the tree's, which can only overstate it."""
    import numpy as np
    d = np.empty(len(P))
    k = np.empty(len(P), dtype=np.int64)
    for i, p in enumerate(P):
        hit = tr.find_nearest(p)
        d[i], k[i] = (hit[3], hit[2]) if hit[0] is not None else (1e9, -1)
    if V is not None and len(T) and check is not None:
        redo = np.where(d > check)[0]
        if not len(redo):
            return d, k
        from scipy.spatial import cKDTree
        tv = V[T]
        c = tv.mean(1)
        ext = np.linalg.norm(tv - c[:, None], axis=2).max(1)  # how far a triangle reaches from its centre
        cap = 4.0 * JL.tolerance()                          # past four tolerances the exact distance decides nothing:
        r = np.minimum(d[redo], cap)                        # a point no triangle comes within it of fails either way,
        Q = P[redo]                                         # and keeps the tree's (over)statement
        edges = [0.0] + [_SMALL * 2.0 ** n for n in range(-2, 12)] + [np.inf]
        found = [[] for _ in redo]
        for a, b in zip(edges[:-1], edges[1:]):             # triangles by size class, each class's centres in a k-d
            ci = np.where((ext >= a) & (ext < b))[0]        # tree: a triangle within r of a point has its centre
            if not len(ci):                                 # within r + its class's reach
                continue
            hits = cKDTree(c[ci]).query_ball_point(Q, r + ext[ci].max(), workers=-1)
            for n, h in enumerate(hits):
                if h:
                    found[n].append(ci[h])
        for n, i in enumerate(redo):
            if found[n]:
                near = np.concatenate(found[n])
                e = JL.point_triangle(P[i], tv[near])
                j = int(np.argmin(e))
                if e[j] < d[i]:
                    d[i], k[i] = e[j], near[j]
    return d, k


_SMALL = 0.2


_slow_nearest = JL.nearest
JL.nearest = fast_nearest


def split_warped(me, share=0.1):
    """A copy of the mesh with each warped face (corners off its plane by more than `share` of the tolerance) cut
    along the diagonal the part is drawn and measured with (its loop triangles). The collapse triangulates the faces it
    keeps its own way: a quad warped 33 mm (the counter's, where the tuck meets the stern) cut on its other diagonal
    stood 46 mm off the part at every share, so the skin never collapsed."""
    import bmesh
    import numpy as np
    tol = JL.tolerance()
    out = me.copy()
    out.calc_loop_triangles()
    co = np.empty(len(out.vertices) * 3)
    out.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    tris = {}
    for lt in out.loop_triangles:
        tris.setdefault(lt.polygon_index, []).append(tuple(lt.vertices))
    warped = []
    for p in out.polygons:
        if len(p.vertices) < 4:
            continue
        vs = co[list(p.vertices)]
        if np.abs((vs - vs.mean(0)) @ np.array(tuple(p.normal))).max() > share * tol:
            warped.append(p.index)
    bm = bmesh.new()
    bm.from_mesh(out)
    pinched = [e for e in bm.edges if len(e.link_faces) > 2]   # two sheets touching along an edge (the skin's, 4 cm
    if pinched:                                                # under the main channel each side): parted first, so
        bmesh.ops.split_edges(bm, edges=pinched)               # the collapse does not tear them its own way
    if not warped:
        bm.to_mesh(out)
        bm.free()
        return out, 0
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    faces = [bm.faces[i] for i in warped]
    cut = 0
    for i, f in zip(warped, faces):
        edges = {frozenset(e) for t in tris[i] for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0]))}
        rim = {frozenset((f.verts[j].index, f.verts[(j + 1) % len(f.verts)].index)) for j in range(len(f.verts))}
        for a, b in (tuple(e) for e in edges - rim):        # the inner edges of its triangles, cut one by one
            for g in list(bm.verts[a].link_faces):
                if bm.verts[b] in g.verts and len(g.verts) > 3:
                    bmesh.utils.face_split(g, bm.verts[a], bm.verts[b])
                    cut += 1
                    break
    bm.to_mesh(out)
    bm.free()
    return out, cut


def _piece_meshes(me):
    """The mesh's loose pieces, each a mesh of its own (its attributes, UV maps and slots kept)."""
    import bmesh
    import numpy as np
    V, T, _, _ = JL.arrays(me)
    lab = JL.islands(len(V), T)
    out = []
    for k in range(int(lab.max()) + 1 if len(lab) else 0):
        sub = me.copy()
        bm = bmesh.new()
        bm.from_mesh(sub)
        bm.verts.ensure_lookup_table()
        drop = np.where(lab != k)[0]
        if len(drop):
            bmesh.ops.delete(bm, geom=[bm.verts[i] for i in drop], context="VERTS")
        bm.to_mesh(sub)
        bm.free()
        if len(sub.polygons):
            out.append(sub)
        else:
            bpy.data.meshes.remove(sub)
    return out


def _own_ratio(sub, tol):
    """The smallest of the ratios at which this piece alone stays within the tolerance (surface both ways and its paint
    lines: JL.measure), found by halving as the part's own search is."""
    V, T, TP, PM = JL.arrays(sub)
    hero = (V, T, JL.tri_mats(TP, PM))
    R = [r for r in LC["ratios"]]
    lo, hi, best = 0, len(R) - 1, 1.0
    while lo <= hi:
        mid = (lo + hi) // 2
        cand = _plain_collapse(sub, R[mid])
        cv, ct, ctp, cpm = JL.arrays(cand)
        ok = len(ct) > 0 and JL.measure(hero, (cv, ct, JL.tri_mats(ctp, cpm)), LC.get("piece_share", 0.8) * tol)["ok"]
        bpy.data.meshes.remove(cand)
        if ok:
            best, hi = R[mid], mid - 1
        else:
            lo = mid + 1
    return best


def piecewise_collapse(me, ratio):
    """Each loose piece collapsed apart, to the larger of `ratio` and its own smallest share (found once per mesh and
    kept): Blender's collapse takes one share for the whole part, so on a part of many pieces (a gun's tackles: blocks,
    hooks, falls, the breeching) the one piece that needs most sets the share for all. The part's own search then runs
    as before over `ratio`; at its smallest every piece is at its own share."""
    import bmesh
    import numpy as np
    V = JL.arrays(me)[0]
    key = (len(me.vertices), len(me.polygons), round(float(np.abs(V).sum()), 3))
    if key not in _PIECES:
        tol = JL.tolerance()
        subs, seen = _piece_meshes(me), {}
        for sub in subs:                                    # the same piece again (a rail's pins, a stay's deadeyes)
            sv, st, _, _ = JL.arrays(sub)                   # takes the first one's share: same counts, the same
            ext = np.sort(np.linalg.norm(sv - sv.mean(0), axis=1))   # spread of its corners from its centre
            sig = (len(sv), len(st), tuple(np.round(ext[[0, len(ext) // 2, -1]], 4)),
                   round(float(JL.tri_area(sv, st).sum()), 6))
            if sig not in seen:
                seen[sig] = _own_ratio(sub, tol)
            _PIECES.setdefault(key, []).append((sub, seen[sig]))
    out = bpy.data.meshes.new(me.name + "_pieces")
    bm = bmesh.new()
    for sub, own in _PIECES[key]:
        r = max(ratio, own)
        cand = _plain_collapse(sub, r) if r < 1.0 else sub.copy()
        bm.from_mesh(cand)                                  # (each mesh read in is added to the last)
        bpy.data.meshes.remove(cand)
    bm.to_mesh(out)
    bm.free()
    for m in me.materials:
        out.materials.append(m)
    return out


def _collapse(me, ratio):
    flat, cut = split_warped(me)
    try:
        if _PIECEWISE[0]:
            return piecewise_collapse(flat, ratio)
        return guarded_collapse(flat, ratio) if _GUARD[0] else _plain_collapse(flat, ratio)
    finally:
        bpy.data.meshes.remove(flat)


JL.collapse = _collapse
_GUARD = [False]
_PIECEWISE = [False]
_KEEP = {}
_PIECES = {}


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def below(o):
    return any(c.name in LC["inside_collections"] or c.name.startswith(tuple(n + "_" for n in LC["inside_collections"]))
               for c in o.users_collection)       # a deck's own sub-collections too (BerthDeck_Hammocks, _Messes)


def outside(objs=None):
    objs = objs if objs is not None else bpy.context.scene.objects
    return [o for o in objs if o.type == "MESH" and o.name not in LC["skip"] and o.get("light_of") is None
            and not below(o)]


def collection_of(o):
    return next((c.name for c in o.users_collection if c.name in {n for v in LC["states"].values() for n in v}
                 or c.name.startswith(("Sails_", "Running_", "Guns", "Carronades_"))), None)


def shown_in(o, state):
    c = collection_of(o)
    return c is None or c in LC["states"][state]


def _twin_object(ob, light_me):
    lob = ob.copy()
    lob.data = light_me
    lob.name = ob.name + SUFFIX
    lob["light_of"] = ob.name
    col = bpy.data.collections.get(COLLECTION) or bpy.data.collections.new(COLLECTION)
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    col.objects.link(lob)
    lob.hide_render = True
    lob.hide_set(True)
    return lob


def groups(parts):
    """The parts by mesh (a shared mesh's users together), in name order."""
    by_mesh = {}
    for ob in parts:
        by_mesh.setdefault(ob.data.name, []).append(ob)
    return dict(sorted(by_mesh.items(), key=lambda kv: kv[1][0].name))


def shard_of(by_mesh, n):
    """Each mesh's shard (0..n-1): the meshes dealt out largest first to the lightest shard, by triangles."""
    load, out = [0] * n, {}
    for name, obs in sorted(by_mesh.items(), key=lambda kv: -tris(kv[1][0])):
        i = load.index(min(load))
        out[name] = i
        load[i] += tris(obs[0]) + 2000          # (a part's fixed cost)
    return out


def _made(first, tol):
    """JL.twin, and again at the next larger share while it fails a check the collapse's search does not hold (an
    open edge moved off the part's own), until it passes or keeps everything."""
    lob, rep = JL.twin(first, tol)
    rep["guarded"] = _GUARD[0]
    tried = 0
    while not rep["ok"] and rep.get("solids", {}).get("ratio", 1.0) < 1.0 and tried < 4:
        r0 = rep["solids"]["ratio"]
        me = lob.data
        bpy.data.objects.remove(lob)
        bpy.data.meshes.remove(me)
        JL.LC = dict(LC, ratios=[r for r in LC["ratios"] if r > r0])
        try:
            lob, rep = JL.twin(first, tol)
        finally:
            JL.LC = LC
        rep["guarded"] = _GUARD[0]
        rep["retried_from_ratio"] = r0
        tried += 1
    return lob, rep


def build(log=lambda m: print(m, flush=True), only=None, shard=None):
    """Every outside part's twin (any made before are removed first) and the report. shard (i, n) makes only the
    i-th of n shares of the meshes (merge() gathers them)."""
    JL.clear()
    tol = JL.tolerance()
    parts = sorted(outside(), key=lambda o: o.name)
    if only:
        parts = [o for o in parts if o.name in only or o.data.name in only]
    by_mesh = groups(parts)
    if shard:
        sh = shard_of(by_mesh, shard[1])
        by_mesh = {k: v for k, v in by_mesh.items() if sh[k] == shard[0]}
        parts = [o for obs in by_mesh.values() for o in obs]
    per, t0 = {}, time.time()
    for name, obs in by_mesh.items():
        first = obs[0]
        t1 = time.time()
        _GUARD[0] = any(name.startswith(g) or first.name.startswith(g) or g in name for g in LC.get("guarded", []))
        piecewise = any(g in name or g in first.name for g in LC.get("piecewise", []))
        _PIECEWISE[0] = False
        lob, rep = _made(first, tol)
        if piecewise:                         # piece by piece as well, and the lighter of the two that pass: on some
            _PIECEWISE[0] = True              # parts one piece sets the share for all, on others the whole part's
            lob2, rep2 = _made(first, tol)    # collapse spends its triangles better than the pieces' own
            _PIECEWISE[0] = False
            better = rep2["ok"] and (not rep["ok"] or rep2["light_triangles"] < rep["light_triangles"])
            rep2["plain_light_triangles"] = rep["light_triangles"]
            rep["piecewise_light_triangles"] = rep2["light_triangles"]
            lose, (lob, rep) = (lob, (lob2, rep2)) if better else (lob2, (lob, rep))
            me = lose.data
            bpy.data.objects.remove(lose)
            bpy.data.meshes.remove(me)
            lob.name = first.name + SUFFIX
        rep["piecewise"] = bool(rep.get("plain_light_triangles"))
        for subs in _PIECES.values():
            for sub, _ in subs:
                bpy.data.meshes.remove(sub)
        _PIECES.clear()
        lob.data.name = name + SUFFIX
        for ob in obs[1:]:                    # the mesh's other users: their own twin objects, sharing the twin mesh
            _twin_object(ob, lob.data)
        rep["seconds"] = round(time.time() - t1, 1)
        rep["objects"] = [o.name for o in obs]
        for ob in obs:
            per[ob.name] = rep
        m = rep["measure"]
        log(f"Light: {first.name:26s} x{len(obs):<3d} {rep['hero_triangles']:7d} -> {rep['light_triangles']:6d} "
            f"({rep['share']:.3f}) error {m['error_mm']} mm  paint {m['paint_slide_mm']} mm  "
            f"specks {rep['specks']['count']}  tubes {rep.get('tubes', {}).get('count', 0)}  {rep['seconds']} s  "
            f"{'ok' if rep['ok'] else 'FAILS'}  ({time.time() - t0:.0f} s)")
    return report(parts, per, tol, time.time() - t0)


def report(parts, per, tol, seconds):
    """The light copy's report from each part's (per: part name -> its mesh's twin report)."""
    by_mesh = groups(parts)
    states = {}
    for s in LC["states"]:
        shown = [o for o in parts if shown_in(o, s)]
        hero = sum(per[o.name]["hero_triangles"] for o in shown)
        light = sum(per[o.name]["light_triangles"] for o in shown)
        states[s] = {"hero_triangles": hero, "light_triangles": light, "share": round(light / max(hero, 1), 4)}
    meshes = {n: per[obs[0].name] for n, obs in by_mesh.items()}
    swe = max((r["measure"]["switch_error_mm"] for r in meshes.values()), default=0.0) / 1000
    s = LC["screen"]
    half = math.tan(math.radians(s["fov_deg"]) / 2)
    out = {"tolerance_mm": round(tol * 1000, 2),
           "screen": {k: v for k, v in s.items() if not k.startswith("note")}, "from_m": LC["from_m"],
           "pixels": LC["pixels"], "states": states,
           "largest_share": max(v["share"] for v in states.values()), "budget_share": LC["budget_share"],
           "largest_light_triangles": max(v["light_triangles"] for v in states.values()),
           "budget_triangles": LC["budget_triangles"],
           "unique_meshes": len(meshes), "twins": len(per), "parts_outside": len(parts),
           "light_triangles_unique": sum(r["light_triangles"] for r in meshes.values()),
           "hero_triangles_unique": sum(r["hero_triangles"] for r in meshes.values()),
           "worst_error_mm": max((r["measure"]["error_mm"] or 0.0 for r in meshes.values()), default=0.0),
           "worst_paint_slide_p99_mm": max((r["measure"]["paint_slide_p99_mm"] for r in meshes.values()), default=0.0),
           "worst_switch_error_mm": round(swe * 1000, 2),
           "one_pixel_from_m": {"4K at 60 deg": round(swe * s["width_px"] / (2 * half), 1),
                                "1080p at 90 deg": round(swe * 1920 / 2, 1)},
           "failing": sorted(n for n, r in meshes.items() if not r["ok"]),
           "seconds": round(seconds)}
    out["ok"] = (not out["failing"] and out["largest_share"] <= LC["budget_share"]
                 and out["largest_light_triangles"] <= LC["budget_triangles"])
    out["meshes"] = meshes
    return out


def merge(shard_blends, shard_reports):
    """Into the open ship: every shard's twins (appended from its .blend, each into 'Light', sharing as there) and
    the whole report from the shards' per-mesh reports."""
    JL.clear()
    col = bpy.data.collections.get(COLLECTION) or bpy.data.collections.new(COLLECTION)
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    for path in shard_blends:
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            dst.objects = [n for n in src.objects if n.endswith(SUFFIX)]
        for o in dst.objects:
            if o is None or o.get("light_of") is None:
                continue
            if any(t.get("light_of") == o["light_of"] for t in col.objects):    # the first shard given wins
                bpy.data.objects.remove(o)
                continue
            part = bpy.data.objects.get(o["light_of"])
            o.parent = part.parent if part else None
            if part:
                o.matrix_world = part.matrix_world.copy()
            col.objects.link(o)
            o.hide_render = True
            o.hide_set(True)
    # what the twins brought along that the ship already has (their materials, a parent): the ship's own instead
    for coll in (bpy.data.materials, bpy.data.objects, bpy.data.meshes, bpy.data.images, bpy.data.node_groups):
        for d in list(coll):
            base, dot, num = d.name.rpartition(".")
            if dot and num.isdigit() and len(num) == 3 and base in coll and not d.name.endswith(SUFFIX) \
                    and not (coll is bpy.data.objects and d.get("light_of") is not None):
                d.user_remap(coll[base])
                coll.remove(d)
    parts = sorted(outside(), key=lambda o: o.name)
    per, secs = {}, 0.0
    for r in shard_reports:
        rep = json.load(open(r))
        secs = max(secs, rep["seconds"])
        for m in rep["meshes"].values():
            for n in m["objects"]:
                per.setdefault(n, m)                  # (the first shard given wins: a part made again goes first)
    missing = [o.name for o in parts if o.name not in per]
    if missing:
        raise SystemExit(f"light: no twin report for {len(missing)} parts, e.g. {missing[:5]}")
    return report(parts, per, JL.tolerance(), secs)


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    src = os.path.abspath(args[0])
    dst = args[1] if len(args) > 1 and not args[1].startswith("--") else src
    only = set(args[args.index("--only") + 1].split(",")) if "--only" in args else None
    shard = tuple(int(v) for v in args[args.index("--shard") + 1].split("/")) if "--shard" in args else None
    rpt = args[args.index("--report") + 1] if "--report" in args else os.path.join(os.path.dirname(dst), "light.json")
    bpy.ops.wm.open_mainfile(filepath=src)
    if "--check-nearest" in args:      # --check-nearest <part>: both measures on that part collapsed to a fifth
        import numpy as np
        me = bpy.data.objects[args[args.index("--check-nearest") + 1]].data
        tol = JL.tolerance()
        cand = _plain_collapse(me, 0.2)
        V, T, _, _ = JL.arrays(me)
        cv, ct, _, _ = JL.arrays(cand)
        pts = JL.surface_points(V, T, 4 * tol)
        a = _slow_nearest(JL.tree(cv, ct), pts, cv, ct, 0.5 * tol)[0]
        b = fast_nearest(JL.tree(cv, ct), pts, cv, ct, 0.5 * tol)[0]
        print(f"check-nearest: {len(pts)} points, {int((a > 0.5 * tol).sum())} re-measured, "
              f"largest difference {float(np.abs(a - b).max()) * 1000:.4f} mm")
        return
    if "--merge" in args:              # --merge a.blend,b.blend --reports a.json,b.json
        rep = merge([os.path.abspath(p) for p in args[args.index("--merge") + 1].split(",")],
                    args[args.index("--reports") + 1].split(","))
    else:
        rep = build(only=only, shard=shard)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(dst))
    with open(rpt, "w") as f:
        json.dump(rep, f, indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k != "meshes"}, indent=1))


if __name__ == "__main__":
    main()
