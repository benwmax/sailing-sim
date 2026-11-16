"""Bluebonnet's light copy (slice 12, docs/jclass-12): a lighter twin of every part seen from outside, for distant and
AI boats, held to one pixel of a 4K screen from 50 m out (light_bluebonnet.json).

    import light
    report = light.build()        # in the build (build_jclass.py), after the wear: adds the twins
    python light.py <build dir>   # or on a built jclass.blend: makes the twins again, saves it, writes light.json

Every part seen from outside (not slice 1's reference hull, nothing below decks) gets a twin '<name>_Light' with the
detailed part's frame, parent, material slots, UV maps and custom properties (so it shows in the same suits and
states), plus 'light_of' naming the part, in the collection 'Light', hidden: the game imports each twin as its part's
light level (slice 14), and render_jclass.py's light shots show the twins in their parts' places. A twin is made in
five steps:

  specks   a separate piece (a split pin, a rivet head) whose bounding box's diagonal is under the tolerance is left
           out: it is under a pixel from 50 m;
  tubes    a rope, a wire or a round rod (the detailed part's tube: rings of one count capped by a fan to each end's
           centre) is built again round its own centreline (the rings' centres) with the fewest sides, its corners
           at the mean radius, that keep it within half the tolerance and a share of its radius of the round tube, so
           its width seen from any side is within that share of the tube's; its rings are thinned to those its
           centreline and radius need; its paint is carried as a solid's is (below). One that would stray further
           than the tolerance, or whose paint would slide further, is simplified with the solids;
  solids   the rest is collapsed (Blender's quadric decimation) to the smallest share of its triangles that keeps it
           within the tolerance of the detailed part's surface, its drawn paint too (below). Where two materials meet
           (a paint line, a sail's patches) or a UV map's numbers jump (a seam in the drawn paint: the plating's, a
           sail's cloths) the faces are cut apart first and collapsed apart, so each line keeps its place exactly; then
           the two sides are sewn together again, every vertex on one side put into the other side's edge, so no crack
           opens (only the seams cut are sewn, never an edge the part itself leaves open). A jump of a whole turn (a
           spar's wrap round seam, 1 back to 0) is no seam and stays whole;
  paint    every corner takes the detailed part's UVs at the nearest point of its own piece (between the seams) facing
           its face's way, looked for a little inside the face, so the plating's seams and rivets, a sail's cloths and
           a spar's bands stay where the part draws them; across a wrap round seam each face keeps its own side;
  normals  every corner takes the detailed part's normal at the nearest point of its faces facing the corner's face
           (within 72 degrees): the twin shades as the part does, a four-sided rope as round, a hard edge as hard, and
           a thin piece's two sides (a window's glass) keep their own.

Each twin is then measured against its part (light.json): the furthest any point of the part (less its specks) lies
from the twin and any point of the twin from the part, the furthest a face of one material lies from that material on
the part (a paint line out of place), how far its drawn paint slides (each UV number's lines, uv_slide: the 99th
percentile by area is held to the tolerance, the largest reported), any face turned over (narrower than the
tolerance), the open edges (cracks: no longer than the part's, and lying along the part's own), the triangles, and the
screen size at which its error (the largest of its surface's, its paint's and a turned face's) is one pixel (Unreal's
LOD screen size).
Units are metres in each part's own frame.
"""
import json
import math
import os
import sys

import bpy  # noqa: I100  (bpy first: it makes bmesh and mathutils importable)
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
LC = json.load(open(os.path.join(HERE, "light_bluebonnet.json")))
SUITS = {k: v for k, v in json.load(open(os.path.join(HERE, "sails_bluebonnet.json")))["suits"].items() if k != "note"}
COLLECTION = "Light"
SUFFIX = "_Light"
PIECE = "light_piece"      # a face attribute while the twin is made: the piece (between seams) of the part it came from
SEAM = "light_seam"        # a point attribute while the twin is made: 1 on the vertices of the seams cut (Hero.seam)
FLAT = 0.2                 # a UV number changing under this share of its usual rate draws no line there; over its
#                            inverse it jumps (a flag's edge, a pole, a seam smeared over one face): uv_slide, Hero


def tolerance():
    """One pixel ('pixels') at 'from_m' on light_bluebonnet.json's screen, in metres."""
    s = LC["screen"]
    return LC["pixels"] * 2.0 * LC["from_m"] * math.tan(math.radians(s["fov_deg"]) / 2) / s["width_px"]


def screen_size(radius, err):
    """Unreal's LOD screen size (twice the bounding sphere's projected radius over the screen's height, as
    ComputeBoundsScreenSize has it with the horizontal field of view held: aspect R / (D tan(fov / 2)) from the
    sphere's centre D away) below which the twin may stand in for the part: where an error of `err` metres is within
    'pixels' at the sphere's nearest point, D - R away, on light_bluebonnet.json's screen in its widest field of view
    (fov_max_deg; the switch then comes later in any narrower one). For a small part, R much under err W / 2, it is
    the error's own pixel, 2 aspect R / (err W)."""
    s = LC["screen"]
    t = math.tan(math.radians(s["fov_max_deg"]) / 2)
    return s["aspect"] * radius / (radius * t + max(err, 1e-4) * s["width_px"] / (2 * LC["pixels"]))


# ------------------------------------------------------------------------------------------------ meshes as arrays
def arrays(me):
    """Vertices (n, 3), triangles (m, 3), each triangle's polygon and each polygon's material slot."""
    V = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", V)
    me.calc_loop_triangles()
    T = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", T)
    P = np.empty(len(me.loop_triangles), dtype=np.int64)
    me.loop_triangles.foreach_get("polygon_index", P)
    M = np.zeros(len(me.polygons), dtype=np.int64)
    if len(me.polygons):
        me.polygons.foreach_get("material_index", M)
    return V.reshape(-1, 3), T.reshape(-1, 3), P, M


def islands(n, T):
    """Each vertex's separate piece (vertices joined by triangles)."""
    if not len(T):
        return np.arange(n)
    a = np.concatenate([T[:, 0], T[:, 1], T[:, 2]])
    b = np.concatenate([T[:, 1], T[:, 2], T[:, 0]])
    g = coo_matrix((np.ones(len(a)), (a, b)), shape=(n, n))
    return connected_components(g, directed=False)[1]


def tree(V, T):
    return BVHTree.FromPolygons([tuple(map(float, v)) for v in V], [tuple(map(int, t)) for t in T])


def nearest(tr, P, V=None, T=None, check=None):
    """Each point's distance to the tree's surface and the triangle it lands on. Blender's tree can miss the nearest
    triangle when it is a long sliver (a collapsed spar's side, 30 m by 3 cm): with the mesh (V, T) given, every
    distance over `check` is measured again exactly against each triangle whose box comes within it."""
    d = np.empty(len(P))
    k = np.empty(len(P), dtype=np.int64)
    for i, p in enumerate(P):
        hit = tr.find_nearest(p)
        d[i], k[i] = (hit[3], hit[2]) if hit[0] is not None else (1e9, -1)
    if V is not None and len(T) and check is not None:
        lo, hi = V[T].min(1), V[T].max(1)
        for i in np.where(d > check)[0]:
            p = P[i]
            near = np.where(np.all(lo - d[i] <= p, axis=1) & np.all(hi + d[i] >= p, axis=1))[0]
            if len(near):
                e = point_triangle(p, V[T[near]])
                j = int(np.argmin(e))
                if e[j] < d[i]:
                    d[i], k[i] = e[j], near[j]
    return d, k


def point_triangle(p, tri):
    """Exact distances from the point p (or each of n points) to each triangle (n, 3, 3)."""
    return np.linalg.norm(closest_points(p, tri) - p, axis=1)


def closest_points(p, tri):
    """The point of each triangle (n, 3, 3) nearest the point p (or each of n points): found by the region of the
    triangle's plane the point projects into (Ericson, Real-Time Collision Detection 5.1.5), vectorised."""
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    ab, ac = b - a, c - a
    d1, d2 = (ab * (p - a)).sum(1), (ac * (p - a)).sum(1)
    d3, d4 = (ab * (p - b)).sum(1), (ac * (p - b)).sum(1)
    d5, d6 = (ab * (p - c)).sum(1), (ac * (p - c)).sum(1)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2

    def frac(x, y):
        return np.clip(x / np.where(np.abs(y) < 1e-30, 1e-30, y), 0.0, 1.0)[:, None]
    den = va + vb + vc
    den = np.where(np.abs(den) < 1e-30, 1e-30, den)
    q = a + ab * (vb / den)[:, None] + ac * (vc / den)[:, None]                 # inside the face, unless...
    cases = [((va <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0), b + (c - b) * frac(d4 - d3, (d4 - d3) + (d5 - d6))),
             ((vb <= 0) & (d2 >= 0) & (d6 <= 0), a + ac * frac(d2, d2 - d6)),
             ((d6 >= 0) & (d5 <= d6), c),
             ((vc <= 0) & (d1 >= 0) & (d3 <= 0), a + ab * frac(d1, d1 - d3)),
             ((d3 >= 0) & (d4 <= d3), b),
             ((d1 <= 0) & (d2 <= 0), a)]                                       # ...nearer a region tested later
    for mask, pt in cases:
        q = np.where(mask[:, None], pt, q)
    return q


def tri_area(V, T):
    return 0.5 * np.linalg.norm(np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]), axis=1)


def open_edges(me):
    """The edges with one face: their count and length."""
    bm = bmesh.new()
    bm.from_mesh(me)
    es = [e for e in bm.edges if e.is_boundary]
    out = (len(es), float(sum(e.calc_length() for e in es)))
    bm.free()
    return out


# ------------------------------------------------------------------------------------------------ tubes
def _walk_tube(c, sides_from):
    """The rings of the tube whose end cap's fan centre is `c` (a BMVert), or None if it is not one: each layer of
    vertices out from c has c's count and closes on itself, and the last is the other end's centre."""
    n = len(c.link_edges)
    if n < sides_from or len(c.link_faces) != n or any(len(f.verts) != 3 for f in c.link_faces):
        return None
    prev, cur = {c}, [e.other_vert(c) for e in c.link_edges]
    rings = []
    while True:
        cs = set(cur)
        if len(cs) != n or sum(1 for v in cur for e in v.link_edges if e.other_vert(v) in cs) != 2 * n:
            return None
        rings.append(cur)
        nxt = {e.other_vert(v) for v in cur for e in v.link_edges} - cs - prev
        if len(nxt) == 1:
            end = next(iter(nxt))
            if len(end.link_edges) != n or {e.other_vert(end) for e in end.link_edges} != cs:
                return None
            return rings, end
        if len(nxt) != n:
            return None
        prev, cur = cs, list(nxt)


def find_tubes(me, label, cfg):
    """The detailed mesh's tubes: {island: {rings: [vertex indices], centres: (2,) vertex indices, their places, each
    ring's centre, radius and the place of its vertex on the tube's UV seam (where its UVs part: NaN if none)}} for
    every island that is one tube end to end with round enough rings."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    count = np.bincount(label)
    seamy = np.zeros(len(bm.verts), dtype=bool)          # a vertex whose corners' UVs differ: on a UV seam
    vuv = np.zeros((len(bm.verts), 0))                    # each vertex's UVs (its corners' mean), every number
    if len(me.loops) and len(me.uv_layers):
        lv = np.empty(len(me.loops), dtype=np.int64)
        me.loops.foreach_get("vertex_index", lv)
        cols = []
        for ly in me.uv_layers:
            uv = np.empty(len(me.loops) * 2)
            ly.data.foreach_get("uv", uv)
            uv = uv.reshape(-1, 2)
            lo, hi = np.full((len(bm.verts), 2), np.inf), np.full((len(bm.verts), 2), -np.inf)
            np.minimum.at(lo, lv, uv)
            np.maximum.at(hi, lv, uv)
            seamy |= (hi - lo).max(1) > 1e-5
            cols.append(0.5 * (lo + hi))
        vuv = np.where(np.isfinite(np.hstack(cols)), np.hstack(cols), 0.0)
    found = {}
    for v in bm.verts:
        isl = int(label[v.index])
        if isl in found or len(v.link_faces) < cfg["hero_sides_from"]:
            continue
        w = _walk_tube(v, cfg["hero_sides_from"])
        if w is None:
            continue
        rings, end = w
        if len(rings) < 2 or len(rings) * len(rings[0]) + 2 != count[isl]:
            continue
        R = [[u.index for u in r] for r in rings]
        co = np.array([[tuple(u.co) for u in r] for r in rings])
        cen = co.mean(1)
        dist = np.linalg.norm(co - cen[:, None, :], axis=2)
        ratio = dist.max(1) / np.maximum(dist.min(1), 1e-12)
        if dist.min() <= 0 or ratio.max() > cfg["roundness"] or np.median(ratio) > cfg["round_median"]:
            continue
        seam = np.full((len(R), 3), np.nan)
        for i, r in enumerate(R):
            on = [j for j in r if seamy[j]]
            if on:
                seam[i] = tuple(bm.verts[on[0]].co)
            elif vuv.shape[1]:                          # or the edge round the ring over which a number jumps back
                rs = set(r)                             # in one step, smeared over one face (no seam cut)
                es = [(j, e.other_vert(bm.verts[j]).index) for j in r for e in bm.verts[j].link_edges
                      if e.other_vert(bm.verts[j]).index in rs and e.other_vert(bm.verts[j]).index > j]
                step = np.abs(np.array([vuv[a] - vuv[b] for a, b in es]))
                med = np.median(step, axis=0)
                jump = np.where(med > 1e-9, step / np.maximum(med, 1e-30), 0.0).max(1)
                e = int(np.argmax(jump))
                if jump[e] > 1 / FLAT:
                    a, b = es[e]
                    seam[i] = 0.5 * (np.array(tuple(bm.verts[a].co)) + np.array(tuple(bm.verts[b].co)))
        found[isl] = {"rings": R, "centres": (v.index, end.index), "centre_co": cen, "radius": dist.min(1),
                      "ends_co": (np.array(tuple(v.co)), np.array(tuple(end.co))), "seam_co": seam}
    bm.free()
    return found


def _simplify(C, R, tol):
    """The rings to keep: Douglas-Peucker on the centres within tol, then any ring whose radius the kept ones'
    straight run would miss by more than tol. Returns sorted indices (both ends always)."""
    keep = {0, len(C) - 1}
    stack = [(0, len(C) - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        d = C[b] - C[a]
        L = float(np.linalg.norm(d))
        Q = C[a + 1:b] - C[a]
        if L < 1e-9:
            off = np.linalg.norm(Q, axis=1)
        else:
            d = d / L
            off = np.linalg.norm(Q - np.outer(Q @ d, d), axis=1)
        k = int(np.argmax(off))
        if off[k] > tol:
            keep.add(a + 1 + k)
            stack += [(a, a + 1 + k), (a + 1 + k, b)]
    while True:
        K = sorted(keep)
        worst = (0.0, None)
        for a, b in zip(K[:-1], K[1:]):
            if b - a < 2:
                continue
            s = np.cumsum(np.r_[0.0, np.linalg.norm(np.diff(C[a:b + 1], axis=0), axis=1)])
            f = s / s[-1] if s[-1] > 0 else np.linspace(0, 1, len(s))
            err = np.abs(R[a:b + 1] - (R[a] + f * (R[b] - R[a])))
            j = int(np.argmax(err))
            if err[j] > max(worst[0], tol):
                worst = (float(err[j]), a + j)
        if worst[1] is None:
            return K
        keep.add(worst[1])


def _rings_along(P, R, k, up=None):
    """Rings of k sides round the polyline P with radii R, carried along it without twisting and stretched across each
    bend (a mitre), as deck.tube makes the detailed ones. With `up` (a point per ring, NaN where none), each ring's
    first vertex is turned toward its point: the detailed tube's UV seam, so the light one has an edge along it."""
    d = np.diff(P, axis=0)
    d /= np.linalg.norm(d, axis=1)[:, None]
    a = 2 * math.pi * np.arange(k) / k
    ref = np.array([0.0, 0.0, 1.0]) if abs(d[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(d[0], ref)
    u /= np.linalg.norm(u)
    rings = []
    for i in range(len(P)):
        if 0 < i < len(P) - 1:
            t = d[i - 1] + d[i]
            t /= np.linalg.norm(t)
        else:
            t = d[min(i, len(d) - 1)]
        if up is not None and not np.isnan(up[i]).any():
            w = up[i] - P[i]
            w = w - (w @ t) * t
            if np.linalg.norm(w) > 1e-9:
                u = w
        u = u - (u @ t) * t
        u /= np.linalg.norm(u)
        v = np.cross(t, u)
        q = R[i] * (np.cos(a)[:, None] * u + np.sin(a)[:, None] * v)
        if 0 < i < len(P) - 1:
            bn = d[i] - d[i - 1]
            bn -= (bn @ t) * t
            if np.linalg.norm(bn) > 1e-9:
                bn /= np.linalg.norm(bn)
                q = q + (1.0 / max(float(t @ d[i]), 0.4) - 1.0) * (q @ bn)[:, None] * bn
        rings.append(P[i] + q)
    return np.array(rings)


def _off_round(k):
    """How far, as a share of the radius, a k-sided tube with its corners at the mean radius r 2 / (1 + cos(pi / k))
    strays from the round one: its corners as far outside it as its flats inside, r (1 - cos) / (1 + cos)."""
    c = math.cos(math.pi / k)
    return (1 - c) / (1 + c)


def tube_twin(tb, cfg, tol):
    """A tube built again: vertices, faces (quads, and each end capped by a fan to the detailed tube's end centre) and
    its sides. Its corners stand at the mean radius (_off_round), so seen from any side its width is within the share
    of the round tube's its sides allow (for four sides, 17%), where corners on the round tube would leave its flats
    29% inside; its rings are turned to have an edge along the detailed tube's UV seam, where its paint parts."""
    C, R = tb["centre_co"], tb["radius"]
    rmax = float(R.max())
    want = min(cfg["flat_share"] * tol, cfg["radius_share"] * rmax)
    k = cfg["min_sides"]
    while rmax * _off_round(k) > want and k < len(tb["rings"][0]):
        k += 1
    K = _simplify(C, R, cfg["line_share"] * tol)
    P, Rk = C[K], R[K]
    keep = [0] + [i for i in range(1, len(P)) if np.linalg.norm(P[i] - P[i - 1]) > 1e-6]
    if len(keep) < 2:
        return None
    K = [K[i] for i in keep]
    P, Rk = P[keep], Rk[keep]
    rings = _rings_along(P, Rk * 2 / (1 + math.cos(math.pi / k)), k, tb["seam_co"][K])
    n = len(P) * k
    V = np.vstack([rings.reshape(-1, 3), tb["ends_co"][0], tb["ends_co"][1]])   # each end capped by a fan to its
    F = [(i * k + j, i * k + (j + 1) % k, (i + 1) * k + (j + 1) % k, (i + 1) * k + j)  # centre, as the detailed
         for i in range(len(P) - 1) for j in range(k)]                                  # tube's (its UVs pole there)
    F += [(n, (j + 1) % k, j) for j in range(k)]
    F += [(n + 1, (len(P) - 1) * k + j, (len(P) - 1) * k + (j + 1) % k) for j in range(k)]
    return V, F, k


def tube_mesh(me0, tubes, name):
    """The tubes built again (twin's tubes: {island: (vertices, faces, sides, material, ...)}) as one mesh with the
    part's materials and UV maps (the UVs not yet carried) and its faces' normals outward; and each face's island."""
    verts, faces, mats, group = [], [], [], []
    for isl, (TV, TF, k, mat, *_) in tubes.items():
        base = len(verts)
        verts.extend(tuple(map(float, p)) for p in TV)
        faces.extend(tuple(base + i for i in f) for f in TF)
        mats.extend([mat] * len(TF))
        group.extend([isl] * len(TF))
    tm = bpy.data.meshes.new(name + "_tubes")
    tm.from_pydata(verts, [], faces)
    for mt in me0.materials:
        tm.materials.append(mt)
    tm.polygons.foreach_set("material_index", mats)
    for ly in me0.uv_layers:
        tm.uv_layers.new(name=ly.name)
    bm = bmesh.new()
    bm.from_mesh(tm)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(tm)
    bm.free()
    return tm, np.array(group, dtype=np.int64)


# ------------------------------------------------------------------------------------------------ solids
def split_seams(me):
    """Cut the mesh apart along every edge between two materials, and every UV seam (an edge whose two faces' UVs
    differ at either end, in any map), so that the collapse keeps each in its place; but not where a UV number jumps
    by a whole turn (a share round a spar going from 1 back to 0: the paint repeats, so the seam is no line). Returns
    the numbers cut and the (map, number) pairs that wrap so."""
    bm = bmesh.new()
    bm.from_mesh(me)
    names = [ly.name for ly in me.uv_layers]
    lys = [bm.loops.layers.uv[n] for n in names]
    mats, uvs, wraps = [], [], set()
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        f0, f1 = e.link_faces
        if f0.material_index != f1.material_index:
            mats.append(e)
            continue
        if _uv_jump(e, names, lys, wraps):
            uvs.append(e)
    lay = bm.verts.layers.float.new(SEAM)              # the seams' vertices: by them a corner keeps its side
    for e in mats + uvs:
        for v in e.verts:
            v[lay] = 1.0
    if mats or uvs:
        bmesh.ops.split_edges(bm, edges=mats + uvs)
    bm.to_mesh(me)
    bm.free()
    return len(mats), len(uvs), wraps


def _uv_jump(e, names, lys, wraps):
    """Whether the UVs jump across the edge e (two faces): any number of any map differing between its two faces at
    either end, but for a jump of a whole turn (a share round a spar going from 1 back to 0: the paint repeats), which
    is added to `wraps` as (map, number) instead."""
    f0, f1 = e.link_faces
    l0 = {lp.vert: lp for lp in f0.loops}
    l1 = {lp.vert: lp for lp in f1.loops}
    cut = False
    for v in e.verts:
        for n, ly in zip(names, lys):
            for c in (0, 1):
                d = l0[v][ly].uv[c] - l1[v][ly].uv[c]
                if abs(d) < 1e-5:
                    continue
                if abs(d) > 0.5 and abs(d - round(d)) < 1e-4:
                    wraps.add((n, c))
                else:
                    cut = True
    return cut


def find_wraps(me, verts):
    """The (map, number) pairs whose UVs jump by a whole turn across an edge between two of the vertices `verts`
    (a mask): a tube's wrap round seam."""
    bm = bmesh.new()
    bm.from_mesh(me)
    names = [ly.name for ly in me.uv_layers]
    lys = [bm.loops.layers.uv[n] for n in names]
    wraps = set()
    for e in bm.edges:
        if len(e.link_faces) == 2 and verts[e.verts[0].index] and verts[e.verts[1].index]:
            _uv_jump(e, names, lys, wraps)
    bm.free()
    return wraps


def own_edges(me, step):
    """Points every `step` or closer along the part's own open edges (before any cut), in a tree: the edges the
    sewing must leave open."""
    bm = bmesh.new()
    bm.from_mesh(me)
    pts = []
    for e in bm.edges:
        if e.is_boundary:
            a, b = np.array(tuple(e.verts[0].co)), np.array(tuple(e.verts[1].co))
            n = max(1, int(math.ceil(np.linalg.norm(b - a) / step)))
            pts.extend(a + (b - a) * (k / n) for k in range(n + 1))
    bm.free()
    return cKDTree(np.array(pts)) if pts else None


def open_off(me, own, step):
    """The furthest any point of the mesh's open edges (every `step` along them) lies from the part's own open edges
    (`own`, own_edges): 0 with none open, infinite if the part has none. A crack opened by the collapse or left by the
    sewing lies away from them, where the length of the open edges alone might not show it."""
    bm = bmesh.new()
    bm.from_mesh(me)
    pts = []
    for e in bm.edges:
        if e.is_boundary:
            a, b = np.array(tuple(e.verts[0].co)), np.array(tuple(e.verts[1].co))
            n = max(1, int(math.ceil(np.linalg.norm(b - a) / step)))
            pts.extend(a + (b - a) * (k / n) for k in range(n + 1))
    bm.free()
    if not pts:
        return 0.0
    if own is None:
        return math.inf
    return float(own.query(np.array(pts))[0].max())


def stitch(me, join, own=None, near=0.0, passes=3):
    """Sew the cut seams together again (_sew, until a pass sews nothing): every open edge but those along the part's
    own open edges (`own`, own_edges: both ends within `near` of them). Returns the vertices sewn into an edge, the
    vertices joined with another and the furthest any moved."""
    out = {"sewn": 0, "joined": 0, "furthest_mm": 0.0, "passes": 0}
    for _ in range(passes):
        r = _sew(me, join, own, near)
        out["passes"] += 1
        out["sewn"] += r["sewn"]
        out["joined"] += r["joined"]
        out["furthest_mm"] = max(out["furthest_mm"], r["furthest_mm"])
        if not r["sewn"] and not r["moved"]:
            break
    return out


def _sew(me, join, own=None, near=0.0):
    """One pass: each vertex on a cut seam's open edge goes into the nearest such edge on the far side of its seam
    (another piece, or its own piece's edge whose face lies the other way, as a tube's wrap seam's does) within `join`,
    as a new vertex in that edge at this one's place, or is joined with that edge's end if it lies at it; then the
    coincident vertices are welded."""
    V, T, _, _ = arrays(me)
    piece = islands(len(V), T)
    bm = bmesh.new()
    bm.from_mesh(me)
    edge = {}                                      # only the cut seams, not the part's own open edges, are sewn:

    def on_own(v):                                 # by place, since the collapse blurs any mark on the vertices
        if v not in edge:
            edge[v] = own is not None and own.query(tuple(v.co))[0] <= near
        return edge[v]
    es = [e for e in bm.edges if e.is_boundary and not (on_own(e.verts[0]) and on_own(e.verts[1]))]
    if not es:
        bm.free()
        return {"sewn": 0, "joined": 0, "moved": 0, "furthest_mm": 0.0}
    emat = np.array([piece[e.verts[0].index] for e in es])
    ein = []                                       # each open edge's way into its face, across the surface
    for e in es:
        d = e.link_faces[0].calc_center_median() - 0.5 * (e.verts[0].co + e.verts[1].co)
        ein.append(tuple(d.normalized()))
    ein = np.array(ein)
    P0 = np.array([tuple(e.verts[0].co) for e in es])
    P1 = np.array([tuple(e.verts[1].co) for e in es])
    reach = join + 0.5 * float(np.linalg.norm(P1 - P0, axis=1).max())
    kd = cKDTree(0.5 * (P0 + P1))
    of_vert = {}
    for i, e in enumerate(es):
        for v in e.verts:
            of_vert.setdefault(v, []).append(i)
    ends = 0.1 * join
    splits, pairs, furthest = {}, [], 0.0
    for v, mine in of_vert.items():
        vm = {int(piece[v.index])}
        vin = np.zeros(3)                          # this vertex's way into its faces
        for f in v.link_faces:
            vin += np.array(tuple((f.calc_center_median() - v.co).normalized()))
        vin /= max(np.linalg.norm(vin), 1e-12)
        p = np.array(tuple(v.co))
        best = None
        for i in kd.query_ball_point(p, reach):
            if v in es[i].verts or (emat[i] in vm and ein[i] @ vin > 0.5):   # its own side of the seam
                continue
            a, d = P0[i], P1[i] - P0[i]
            L2 = float(d @ d)
            t = 0.0 if L2 < 1e-18 else min(max(float((p - a) @ d) / L2, 0.0), 1.0)
            dist = float(np.linalg.norm(a + t * d - p))
            if dist <= join and (best is None or dist < best[0]):
                best = (dist, i, t, math.sqrt(L2))
        if best is None:
            continue
        dist, i, t, L = best
        furthest = max(furthest, dist)
        if t * L < ends:
            pairs.append((v, es[i].verts[0]))
        elif (1 - t) * L < ends:
            pairs.append((v, es[i].verts[1]))
        else:
            splits.setdefault(i, []).append((t, p))
    parent = {}

    def root(x):
        while parent.get(x, x) is not x:
            x = parent[x]
        return x
    for a, b in pairs:
        ra, rb = root(a), root(b)
        if ra is not rb:
            parent[ra] = rb
    groups = {}
    for v in {x for pr in pairs for x in pr}:
        groups.setdefault(root(v), []).append(v)
    moved = 0
    for g in groups.values():
        c = np.mean([tuple(v.co) for v in g], axis=0)
        for v in g:
            moved += int(np.linalg.norm(np.array(tuple(v.co)) - c) > 1e-7)
            v.co = c
    touched = set()
    sewn = 0
    for i, pts in splits.items():
        e = es[i]
        a, b = e.verts
        cur, start, t0 = e, a, 0.0
        for t, p in sorted(pts, key=lambda x: x[0]):
            fac = (t - t0) / (1.0 - t0)
            if fac <= 1e-9 or fac >= 1 - 1e-9:
                continue
            ne, nv = bmesh.utils.edge_split(cur, start, fac)
            nv.co = p
            cur = ne if b in ne.verts else cur
            start, t0 = nv, t
            sewn += 1
            touched.update(f for f in nv.link_faces)
    tri = [f for f in touched if f.is_valid and len(f.verts) > 3]
    if tri:
        bmesh.ops.triangulate(bm, faces=tri)
    nv = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=[v for v in bm.verts if v.is_boundary], dist=1e-6)
    moved += nv - len(bm.verts)
    bm.to_mesh(me)
    bm.free()
    return {"sewn": sewn, "joined": len(pairs), "moved": moved, "furthest_mm": round(furthest * 1000, 2)}


def collapse(me, ratio):
    """The mesh collapsed to `ratio` of its triangles (a new mesh)."""
    ob = bpy.data.objects.new("_light_tmp", me)
    bpy.context.scene.collection.objects.link(ob)
    m = ob.modifiers.new("collapse", "DECIMATE")
    m.decimate_type, m.ratio, m.use_collapse_triangulate = "COLLAPSE", ratio, True
    out = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(ob)
    return out


def surface_points(V, T, h):
    """Points covering the triangles: every corner, each triangle's centre, and a grid over each triangle no further
    apart along its edges than h (its edges' middles at least, at most 64 to an edge): where a surface's distance
    from another is measured, inside its faces as well as at their corners."""
    if not len(T):
        return np.zeros((0, 3))
    tv = V[T]
    L = np.linalg.norm(tv - tv[:, [1, 2, 0]], axis=2).max(1)
    n = np.clip(np.ceil(L / h), 2, 64).astype(np.int64)
    out = [V[np.unique(T)], tv.mean(1)]
    for k in np.unique(n):
        i, j = (a.ravel() for a in np.mgrid[0:k + 1, 0:k + 1])
        s = (i + j <= k) & ~(((i == 0) & (j == 0)) | (i == k) | (j == k))      # not the corners
        a, b = (i[s] / k)[None, :, None], (j[s] / k)[None, :, None]
        t = tv[n == k]
        out.append((t[:, None, 0] + a * (t[:, None, 1] - t[:, None, 0]) + b * (t[:, None, 2] - t[:, None, 0]))
                   .reshape(-1, 3))
    return np.vstack(out)


def measure(hero, light, tol):
    """The twin against its part: hero = (V, T, tri materials) of the part less its specks, light the same of the twin.
    Distances both ways, from points covering each surface (surface_points: every corner, and inside every face on a
    grid at most four tolerances apart), and for each twin triangle whose material is not the part's under it, how
    far it lies from that material on the part."""
    HV, HT, HM = hero
    LV, LT, LM = light
    if not len(LT):
        return {"hero_to_light_max_mm": None, "ok": not len(HT)}
    ht, lt = tree(HV, HT), tree(LV, LT)
    hp = surface_points(HV, HT, 4 * tol)
    lp = surface_points(LV, LT, 4 * tol)
    d1, _ = nearest(lt, hp, LV, LT, 0.5 * tol)
    d2, _ = nearest(ht, lp, HV, HT, 0.5 * tol)
    _, under = nearest(ht, LV[LT].mean(1))
    wrong = np.where(HM[under] != LM)[0]
    area = tri_area(LV, LT)
    paint = 0.0
    if len(wrong):
        mats = {}
        for k in wrong:
            m = int(LM[k])
            if m not in mats:
                sel = HT[HM == m]
                mats[m] = tree(HV, sel) if len(sel) else None
            if mats[m] is None:
                paint = 1e9
                continue
            pts = np.vstack([LV[LT[k]], LV[LT[k]].mean(0)])
            paint = max(paint, float(nearest(mats[m], pts, HV, HT[HM == m], 0.5 * tol)[0].max()))
    out = {"hero_to_light_max_mm": round(float(d1.max()) * 1000, 2),
           "hero_to_light_p99_mm": round(float(np.percentile(d1, 99)) * 1000, 2),
           "light_to_hero_max_mm": round(float(d2.max()) * 1000, 2),
           "light_to_hero_p99_mm": round(float(np.percentile(d2, 99)) * 1000, 2),
           "paint_line_max_mm": round(paint * 1000, 2),
           "wrong_material_area_share": round(float(area[wrong].sum() / max(area.sum(), 1e-12)), 6)}
    out["error_mm"] = max(out["hero_to_light_max_mm"], out["light_to_hero_max_mm"], out["paint_line_max_mm"])
    out["ok"] = out["error_mm"] <= tol * 1000
    return out


def tri_mats(T_poly, M):
    return M[T_poly] if len(T_poly) else np.zeros(0, dtype=np.int64)


# ------------------------------------------------------------------------------------------------ one twin
def twin(ob, tol):
    """The light twin of one part (made, linked into 'Light', hidden) and its report."""
    me0 = ob.data
    V, T, TP, PM = arrays(me0)
    TM = tri_mats(TP, PM)
    lab = islands(len(V), T)
    nis = int(lab.max()) + 1 if len(lab) else 0
    lo = np.full((nis, 3), np.inf)
    hi = np.full((nis, 3), -np.inf)
    np.minimum.at(lo, lab, V)
    np.maximum.at(hi, lab, V)
    diag = np.linalg.norm(hi - lo, axis=1)
    speck = diag < LC["speck_share"] * tol
    tri_isl = lab[T[:, 0]] if len(T) else np.zeros(0, dtype=np.int64)
    tubes, refused = {}, 0
    for isl, tb in find_tubes(me0, lab, LC["tube"]).items():   # a tube built again must keep within the tolerance
        if speck[isl]:
            continue
        built = tube_twin(tb, LC["tube"], tol)
        sel = tri_isl == isl
        if built is not None:
            TV, TF = built[0], built[1]
            tt = np.array([(f[0], f[j], f[j + 1]) for f in TF for j in range(1, len(f) - 1)])
            m = measure((V, T[sel], TM[sel]), (TV, tt, np.full(len(tt), TM[sel][0])), tol)
            if m["ok"]:
                tubes[isl] = built + (int(np.bincount(TM[sel]).argmax()), int(sel.sum()), m["error_mm"])
                continue
        refused += 1
    is_tube = np.zeros(nis, dtype=bool)
    tm = tslide = ht_ = None
    fell_t = 0
    while True:                                           # the tubes' paint, carried as the solids' is: a tube
        is_tube[:] = False                                # whose paint slides more than the tolerance (a winch
        is_tube[list(tubes)] = True                       # drum's, round which the paint jumps back within one of
        if tm is not None:                                # its faces) is refused and simplified with the solids
            bpy.data.meshes.remove(tm)
            tm = None
        if not tubes:
            break
        tm, group = tube_mesh(me0, tubes, ob.name)
        ht_ = Hero(me0, keep=is_tube[tri_isl], smear=True)
        ht_.wraps = find_wraps(me0, np.isin(lab, list(tubes)))
        fell_t = carry_uvs(ht_, tm, tol)
        tslide = uv_slide(ht_, tm, tol, groups=group)
        bad = [g for g, v in tslide["group_p99_mm"].items() if v > tol * 1000]
        if not bad:
            break
        for g in bad:
            del tubes[g]
        refused += len(bad)
    kept = ~speck[tri_isl]
    solid = kept & ~is_tube[tri_isl]
    rep = {"hero_triangles": int(len(T)), "pieces": nis,
           "specks": {"count": int(speck.sum()), "triangles": int((~kept).sum()),
                      "largest_mm": round(float(diag[speck].max()) * 1000, 1) if speck.any() else 0.0}}
    # the solids: everything but the specks and the tubes, cut at their seams, collapsed, sewn
    sm = me0.copy()
    drop = np.where(speck[lab] | is_tube[lab])[0]
    if len(drop):
        bm = bmesh.new()
        bm.from_mesh(sm)
        bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.verts[i] for i in drop], context="VERTS")
        bm.to_mesh(sm)
        bm.free()
    hero_solid = (V, T[solid], TM[solid])
    light_me, chosen = None, None
    slide = {"max_mm": 0.0, "p99_mm": 0.0, "measured": 1.0, "turned_faces": 0, "turned_widest_mm": 0.0,
             "settings_largest_error": {}}
    if len(sm.polygons):
        open0 = open_edges(sm)[1]
        own = own_edges(sm, 0.25 * tol)                   # its own open edges, left open
        seams = split_seams(sm)
        sv, st, stp, _ = arrays(sm)                       # each face's piece between the seams, kept through the
        piece = islands(len(sv), st)                      # collapse and the sewing: a corner takes its UVs from its
        fp = np.zeros(len(sm.polygons), dtype=np.int64)   # own piece of the part, on its own side of a UV seam
        fp[stp] = piece[st[:, 0]]
        sm.attributes.new(PIECE, "INT", "FACE").data.foreach_set("value", fp)
        hs = Hero(sm)
        hs.wraps = seams[2]

        def made(cand):
            """Sew the candidate, give it the part's UVs, measure it: (sewing, measure, slide, corners fallen back)."""
            sw = stitch(cand, LC["seam_join_share"] * tol, own, 1.25 * tol)
            fell = carry_uvs(hs, cand, tol)
            cv, ct, ctp, cpm = arrays(cand)
            m = measure(hero_solid, (cv, ct, tri_mats(ctp, cpm)), tol)
            m["open_m"] = open_edges(cand)[1]
            return sw, m, uv_slide(hs, cand, tol), fell
        R = LC["ratios"]
        lo_i, hi_i = 0, len(R) - 1
        best, tried = None, []
        while lo_i <= hi_i:
            mid = (lo_i + hi_i) // 2
            cand = collapse(sm, R[mid])
            sw, m, sl, fell = made(cand)
            tried.append({"ratio": R[mid], "error_mm": m["error_mm"], "open_m": round(m["open_m"], 3),
                          "paint_slide_mm": sl["max_mm"], "paint_slide_p99_mm": sl["p99_mm"],
                          "turned_widest_mm": sl["turned_widest_mm"]})
            if (m["ok"] and m["open_m"] <= open0 * 1.001 + 1e-3        # within the tolerance, every seam sewn,
                    and sl["p99_mm"] <= tol * 1000                         # the paint where the part has it,
                    and sl["turned_widest_mm"] <= tol * 1000):             # no face turned over wider than a pixel
                if best is not None:
                    bpy.data.meshes.remove(best[0])
                best = (cand, R[mid], sw, m, sl, fell)
                hi_i = mid - 1
            else:
                bpy.data.meshes.remove(cand)
                lo_i = mid + 1
        if best is None:                                  # nothing collapsed keeps it: the solids as they are
            cand = sm.copy()
            best = (cand, 1.0) + made(cand)
        light_me, chosen, sw, msol, slide, fell = best
        for a in (PIECE, SEAM):
            if a in light_me.attributes:
                light_me.attributes.remove(light_me.attributes[a])
        lt_ = len(arrays(light_me)[1])
        rep["solids"] = {"hero_triangles": int(solid.sum()), "light_triangles": lt_,
                         "ratio": chosen, "share_reached": round(lt_ / max(int(solid.sum()), 1), 4),
                         "seams_cut": seams[0], "uv_seams_cut": seams[1],
                         "uv_wraps": sorted(f"{a}.{'uv'[c]}" for a, c in seams[2]), "seams": sw,
                         "error_mm": msol["error_mm"], "paint_slide": slide, "uv_corners_fallen_back": fell,
                         "tried": tried,
                         "open_m": round(msol.get("open_m", open_edges(light_me)[1]), 3),
                         "hero_open_m": round(open0, 3)}
    bpy.data.meshes.remove(sm)
    if light_me is None:
        light_me = me0.copy()
        bm = bmesh.new()
        bm.from_mesh(light_me)
        bm.clear()
        bm.to_mesh(light_me)
        bm.free()
    # the tubes, built again, their paint carried from the part's tubes as the solids' is, and joined into the twin
    if tubes:
        sides, hero_t, light_t, worst = {}, 0, 0, 0.0
        for isl, (TV, TF, k, mat, ht, err) in tubes.items():
            sides[k] = sides.get(k, 0) + 1
            hero_t += ht
            light_t += sum(len(f) - 2 for f in TF)
            worst = max(worst, err)
        tslide = {k: v for k, v in tslide.items() if k != "group_p99_mm"}
        bm = bmesh.new()
        bm.from_mesh(light_me)
        bm.from_mesh(tm)                                  # (a second mesh read in is added to the first)
        bm.to_mesh(light_me)
        bm.free()
        bpy.data.meshes.remove(tm)
        rep["tubes"] = {"count": len(tubes), "sides": {str(k): v for k, v in sorted(sides.items())},
                        "hero_triangles": hero_t, "light_triangles": light_t, "error_mm": worst,
                        "paint_slide": tslide, "uv_wraps": sorted(f"{a}.{'uv'[c]}" for a, c in ht_.wraps),
                        "uv_corners_fallen_back": fell_t, "refused": refused}
        slide = {"max_mm": max(slide["max_mm"], tslide["max_mm"]),     # the 99th percentile of the two together
                 "p99_mm": max(slide["p99_mm"], tslide["p99_mm"]),     # is no more than the larger of theirs
                 "measured": None, "turned_faces": slide["turned_faces"] + tslide["turned_faces"],
                 "turned_widest_mm": max(slide["turned_widest_mm"], tslide["turned_widest_mm"]),
                 "settings_largest_error": {k: max(slide["settings_largest_error"].get(k, 0.0),
                                                   tslide["settings_largest_error"].get(k, 0.0))
                                            for k in set(slide["settings_largest_error"])
                                            | set(tslide["settings_largest_error"])}}
    elif refused:
        rep["tubes"] = {"count": 0, "refused": refused}
    # the object, its normals from the part's, then measured whole
    for p in light_me.polygons:
        p.use_smooth = True
    lob = ob.copy()
    lob.data = light_me
    lob.name = light_me.name = ob.name + SUFFIX
    lob["light_of"] = ob.name
    col = bpy.data.collections.get(COLLECTION) or bpy.data.collections.new(COLLECTION)
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    col.objects.link(lob)
    shade = {"mean_deg": 0.0, "p95_deg": 0.0, "share_over_10_deg": 0.0}
    if len(light_me.polygons):
        hk = Hero(me0, keep=kept)
        carry_normals(hk, light_me, tol)
        shade = shading(hk, light_me, tol)
    lob.hide_render = True
    lob.hide_set(True)
    LV, LT, LTP, LPM = arrays(lob.data)
    m = measure((V, T[kept], TM[kept]), (LV, LT, tri_mats(LTP, LPM)), tol)
    radius = float(np.linalg.norm(V - 0.5 * (V.min(0) + V.max(0)), axis=1).max()) if len(V) else 0.0
    hoe, loe = open_edges(me0), open_edges(lob.data)
    off_own = open_off(lob.data, own_edges(me0, 0.25 * tol), 0.5 * tol)
    m["paint_slide_mm"] = slide["max_mm"]
    m["paint_slide_p99_mm"] = slide["p99_mm"]
    m["turned_widest_mm"] = slide["turned_widest_mm"]
    m["settings_largest_error"] = slide["settings_largest_error"]
    m["switch_error_mm"] = max(m["error_mm"] or 0.0, slide["p99_mm"], slide["turned_widest_mm"])
    rep.update({"light_triangles": int(len(LT)), "share": round(len(LT) / max(len(T), 1), 4), "measure": m,
                "shading": shade,
                "open_edges": {"hero": hoe[0], "light": loe[0], "hero_m": round(hoe[1], 3),
                               "light_m": round(loe[1], 3), "light_off_own_mm": round(off_own * 1000, 2)},
                "frame_same": lob.matrix_world == ob.matrix_world and lob.parent == ob.parent,
                "uv_maps": [ly.name for ly in lob.data.uv_layers] == [ly.name for ly in me0.uv_layers],
                "slots": [s.material.name if s.material else None for s in lob.material_slots]
                == [s.material.name if s.material else None for s in ob.material_slots],
                "bounding_radius_m": round(radius, 3),
                "centre_m": [round(float(a), 3) for a in ob.matrix_world @ Vector(tuple(0.5 * (V.min(0) + V.max(0))))]
                if len(V) else [0.0, 0.0, 0.0],
                "ue_screen_size": round(screen_size(radius, m["switch_error_mm"] / 1000), 4)})
    rep["ok"] = bool(m["ok"] and max(slide["p99_mm"], slide["turned_widest_mm"]) <= tol * 1000
                     and rep["frame_same"] and rep["uv_maps"] and rep["slots"]
                     and loe[1] <= hoe[1] * 1.02 + 1e-3 and off_own <= LC["seam_join_share"] * tol)
    return lob, rep


class Hero:
    """A part's detailed mesh as arrays (less its specks and, with `keep`, only those triangles), for carrying its
    normals and UVs onto the twin and measuring how far its paint slides. Its seams (where a corner picks its face by
    UV, feet) are the cut ones and, with `smear` (the tubes), the faces over which a number jumps back in one step."""

    def __init__(self, me, keep=None, smear=False):
        self.V, T, TP, PM = arrays(me)
        L = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
        me.loop_triangles.foreach_get("loops", L)
        L = L.reshape(-1, 3)
        TM = tri_mats(TP, face_keys(me))
        TK = tri_mats(TP, PM)
        if keep is not None:
            T, L, TM, TK = T[keep], L[keep], TM[keep], TK[keep]
        self.T, self.L, self.TM = T, L, TM
        active = next((ly.name for ly in me.uv_layers if ly.active_render), None)
        reads = [uv_reads(mt, active) for mt in me.materials] or [set()]
        self.reads = {ly.name: np.array([ly.name in r or ly.name in LC["uv_read_in_game"] for r in reads])
                      [np.clip(TK, 0, len(reads) - 1)] for ly in me.uv_layers}   # each triangle: is the map read
        CN = np.empty(len(me.loops) * 3)
        me.corner_normals.foreach_get("vector", CN)
        self.CN = CN.reshape(-1, 3)
        self.UV = {}
        lv = np.empty(len(me.loops), dtype=np.int64)
        me.loops.foreach_get("vertex_index", lv)
        edge = np.zeros(len(self.V), dtype=bool)                # a vertex on a seam: cut, or a wrap left whole
        for ly in me.uv_layers:
            uv = np.empty(len(me.loops) * 2)
            ly.data.foreach_get("uv", uv)
            self.UV[ly.name] = uv = uv.reshape(-1, 2)
            lo, hi = np.full((len(self.V), 2), np.inf), np.full((len(self.V), 2), -np.inf)
            np.minimum.at(lo, lv, uv)
            np.maximum.at(hi, lv, uv)
            edge |= (hi - lo).max(1) > 1e-5
        if SEAM in me.attributes:
            sv = np.zeros(len(self.V))
            me.attributes[SEAM].data.foreach_get("value", sv)
            edge |= sv > 0.25
        self.seam = edge[T].any(1) if len(T) else np.zeros(0, dtype=bool)   # each triangle: does it touch one,
        V = self.V
        FN = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
        self.FN = FN / np.maximum(np.linalg.norm(FN, axis=1), 1e-30)[:, None]
        self.tr = tree(V, T) if len(T) else None
        self._rate = {}
        for ly in me.uv_layers if len(T) and smear else ():               # or is a number's jump smeared over it
            for c in (0, 1):
                g = self.rate(ly.name, c)
                if (g > 0).any():
                    self.seam |= g > np.median(g[g > 0]) / FLAT
        self.wraps = set()                                      # (map, number) pairs that repeat by whole turns

    def wrap_mask(self):
        """Which of the UV columns side by side (every map's two numbers) wrap by whole turns."""
        return np.array([(n, c) in self.wraps for n in self.UV for c in (0, 1)], dtype=bool)

    def rate(self, layer, c):
        """How fast UV map `layer`'s number `c` changes along each triangle (its gradient's length, per metre)."""
        key = (layer, c)
        if key not in self._rate:
            V, T = self.V, self.T
            u = self.UV[layer][self.L][:, :, c]
            e1, e2 = V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]
            d1, d2 = u[:, 1] - u[:, 0], u[:, 2] - u[:, 0]
            a, b, cc = (e1 * e1).sum(1), (e1 * e2).sum(1), (e2 * e2).sum(1)
            det = a * cc - b * b
            det = np.where(np.abs(det) < 1e-30, np.inf, det)
            x, y = (cc * d1 - b * d2) / det, (a * d2 - b * d1) / det       # gradient = x e1 + y e2
            self._rate[key] = np.linalg.norm(x[:, None] * e1 + y[:, None] * e2, axis=1)
        return self._rate[key]

    def feet(self, P, NL, ML, tol, Q=None, ref=None, facing=0.3):
        """For each point P, the triangle and barycentric weights of its foot on the nearest face, within twice the
        tolerance of Q (P unless given), that faces within 72 degrees of NL (`facing`, the cosine) and has the key ML
        (its piece, or its material); failing that the nearest of any key so facing, and failing that the nearest
        face. With `ref` (each point's UVs, every map side by side), of the faces found within half the tolerance of
        the nearest, the one whose UVs at the foot lie nearest `ref`: on a seam that does not part the mesh (a tube's
        wrap seam, where a UV jumps from 1 back to 0) the side the point's own face lies on: only where one of those
        faces touches a seam, since elsewhere the nearest is right and a face's UVs may change fast across it (a
        chamfer's). Returns the triangles, the weights (n, 3) and which points found a face of their key so facing."""
        Q = P if Q is None else Q
        T, FN, TM = self.T, self.FN, self.TM
        UVL = np.hstack([self.UV[n] for n in self.UV]) if ref is not None and self.UV else None
        wm = self.wrap_mask()
        tri = np.full(len(P), -1, dtype=np.int64)
        matched = np.zeros(len(P), dtype=bool)
        for c0 in range(0, len(P), 100_000):         # in chunks: every (point, face) pair in range at once
            c1 = min(c0 + 100_000, len(P))
            I, K, D = [], [], []
            for i in range(c0, c1):
                hits = self.tr.find_nearest_range(Q[i], 2 * tol)
                I.extend([i] * len(hits))
                K.extend(h[2] for h in hits)
                D.extend(h[3] for h in hits)
            if not I:
                continue
            I, K, D = np.array(I, dtype=np.int64), np.array(K, dtype=np.int64), np.array(D)
            face = (FN[K] * NL[I]).sum(1) > facing
            same = face & (TM[K] == ML[I])
            alt = face & ~same                           # no face of its key: the nearest of any key so facing
            o = np.lexsort((D[alt], I[alt]))
            ia, ka = I[alt][o], K[alt][o]
            first = np.r_[True, ia[1:] != ia[:-1]] if len(ia) else np.zeros(0, dtype=bool)
            tri[ia[first]] = ka[first]
            if not same.any():
                continue
            I, K, D = I[same], K[same], D[same]
            dmin = np.full(len(P), np.inf)
            np.minimum.at(dmin, I, D)
            matched[I] = True
            score = D.copy()                             # the nearest face of its key...
            if UVL is not None:                          # ...or, of those within half the tolerance of it, the one
                near = D <= dmin[I] + 0.5 * tol          # whose UVs at the foot lie nearest the point's own, where
                I, K, D = I[near], K[near], D[near]      # one of them touches a seam
                by_uv = np.zeros(len(P), dtype=bool)
                np.logical_or.at(by_uv, I, self.seam[K])
                tv = self.V[T[K]]
                w = bary(closest_points(P[I], tv), tv)
                d = (w[:, :, None] * UVL[self.L[K]]).sum(1) - ref[I]
                d = np.where(wm, d - np.round(d), d)
                score = np.where(by_uv[I], np.abs(d).sum(1) + 1e-9 * D, D)     # (a tie to the nearer)
            o = np.lexsort((score, I))
            I, K = I[o], K[o]
            first = np.r_[True, I[1:] != I[:-1]]
            tri[I[first]] = K[first]
        far = np.where(tri < 0)[0]
        if len(far):
            tri[far] = nearest(self.tr, P[far], self.V, T, 0.5 * tol)[1]
        tv = self.V[T[tri]]
        return tri, bary(closest_points(P, tv), tv), matched


_READS = {}


def uv_reads(mat, active):
    """The UV maps a material reads (its UV Map nodes, and the mesh's active map for an image or a tangent-space
    normal map left on the default): the maps whose paint the twin must keep in place."""
    if mat is None or mat.node_tree is None:
        return set()
    if (mat.name, active) not in _READS:
        out, seen = set(), set()

        def walk(tree):
            for nd in tree.nodes:
                if nd.type == "GROUP" and nd.node_tree and nd.node_tree.name not in seen:
                    seen.add(nd.node_tree.name)
                    walk(nd.node_tree)
                elif nd.type == "UVMAP":
                    out.add(nd.uv_map or active)
                elif nd.type == "ATTRIBUTE":
                    out.add(nd.attribute_name)
                elif nd.type == "TEX_COORD" and nd.outputs["UV"].is_linked:
                    out.add(active)
                elif nd.type == "TEX_IMAGE" and not nd.inputs["Vector"].is_linked:
                    out.add(active)
                elif nd.type in ("NORMAL_MAP", "TANGENT") and getattr(nd, "uv_map", None) is not None:
                    if nd.type == "TANGENT" and nd.direction_type != "UV_MAP":
                        continue
                    if nd.type == "NORMAL_MAP" and nd.space != "TANGENT":
                        continue
                    out.add(nd.uv_map or active)
        walk(mat.node_tree)
        _READS[(mat.name, active)] = out
    return _READS[(mat.name, active)]


def bary(q, tv):
    """Barycentric weights (n, 3) of the points q in their triangles tv (n, 3, 3)."""
    a, b, c = tv[:, 0], tv[:, 1], tv[:, 2]
    v0, v1, v2 = b - a, c - a, q - a
    d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
    d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
    den = d00 * d11 - d01 * d01
    den = np.where(np.abs(den) < 1e-30, 1e-30, den)
    w1, w2 = (d11 * d20 - d01 * d21) / den, (d00 * d21 - d01 * d20) / den
    W = np.clip(np.stack([1 - w1 - w2, w1, w2], 1), 0.0, None)
    return W / np.maximum(W.sum(1), 1e-30)[:, None]


def face_keys(me):
    """Each face's piece of the part (PIECE) where the mesh has them, else its material."""
    k = np.empty(len(me.polygons), dtype=np.int64)
    if PIECE in me.attributes:
        me.attributes[PIECE].data.foreach_get("value", k)
    elif len(me.polygons):
        me.polygons.foreach_get("material_index", k)
    return k


def corners(me):
    """Each corner's (loop's) position, its face's normal, key (face_keys) and centre."""
    V = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3)
    lv = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", lv)
    n = len(me.polygons)
    PN, PC = np.empty(n * 3), np.empty(n * 3)
    me.polygons.foreach_get("normal", PN)
    me.polygons.foreach_get("center", PC)
    lt = np.empty(n, dtype=np.int64)
    me.polygons.foreach_get("loop_total", lt)
    lp = np.repeat(np.arange(n), lt)
    return V[lv], PN.reshape(-1, 3)[lp], face_keys(me)[lp], PC.reshape(-1, 3)[lp]


def inward(P, C, tol):
    """Each corner P moved a little toward its face's centre C (a quarter of the way, at most half the tolerance):
    searching from there finds the part's face on the twin face's own side of a seam."""
    d = C - P
    n = np.linalg.norm(d, axis=1)
    return P + d * (np.minimum(0.25, 0.5 * tol / np.maximum(n, 1e-12)))[:, None]


def carry_normals(hero, me, tol):
    """Every corner of `me` takes the part's normal (its corner normals, interpolated across the triangle) at its foot
    on the part's nearest face facing within 72 degrees of the corner's own face (Hero.feet), searched from a little
    inside its face: a thin piece's two sides (a window's glass, a cover's lid) never take each other's normals, which
    nearest-corner transfer gives them where a side has moved by more than the piece's thickness, the two sides of a
    hard edge keep their own, a large face whose corner lies on a rounded edge (a deckhouse's foot) shades as the flat
    it stands for, not as the edge, and a four-sided rope's corner takes the round rope's normal on both faces."""
    P, NL, ML, C = corners(me)
    tri, W, _ = hero.feet(P, NL, ML, tol, Q=inward(P, C, tol))
    N = (W[:, :, None] * hero.CN[hero.L[tri]]).sum(1)
    N /= np.maximum(np.linalg.norm(N, axis=1), 1e-30)[:, None]
    me.normals_split_custom_set([tuple(n) for n in N])


def shading(hero, me, tol):
    """How the twin shades against its part: at four points inside each of its triangles (its centre and three about
    it), the angle between its normal (its corners', interpolated) and the part's at the point's foot, by area: the
    mean, the 95th percentile and the share over 10 degrees (degrees). Reported, not held."""
    if not len(me.polygons):
        return {"mean_deg": 0.0, "p95_deg": 0.0, "share_over_10_deg": 0.0}
    V, LT, TP, _ = arrays(me)
    LL = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("loops", LL)
    LL = LL.reshape(-1, 3)
    CN = np.empty(len(me.loops) * 3)
    me.corner_normals.foreach_get("vector", CN)
    CN = CN.reshape(-1, 3)
    w = np.array([(1 / 3, 1 / 3, 1 / 3), (2 / 3, 1 / 6, 1 / 6), (1 / 6, 2 / 3, 1 / 6), (1 / 6, 1 / 6, 2 / 3)])
    tv = V[LT]
    W = np.repeat(w, len(LT), axis=0)
    idx = np.tile(np.arange(len(LT)), len(w))
    P = (W[:, :, None] * tv[idx]).sum(1)
    N = (W[:, :, None] * CN[LL[idx]]).sum(1)
    N /= np.maximum(np.linalg.norm(N, axis=1), 1e-30)[:, None]
    FN = np.cross(tv[:, 1] - tv[:, 0], tv[:, 2] - tv[:, 0])
    FN /= np.maximum(np.linalg.norm(FN, axis=1), 1e-30)[:, None]
    tri, Wh, _ = hero.feet(P, FN[idx], tri_mats(TP, face_keys(me))[idx], tol)
    NH = (Wh[:, :, None] * hero.CN[hero.L[tri]]).sum(1)
    NH /= np.maximum(np.linalg.norm(NH, axis=1), 1e-30)[:, None]
    ang = np.degrees(np.arccos(np.clip((N * NH).sum(1), -1.0, 1.0)))
    a = np.tile(tri_area(V, LT), len(w))
    o = np.argsort(ang)
    cw = np.cumsum(a[o])
    return {"mean_deg": round(float((ang * a).sum() / max(a.sum(), 1e-30)), 2),
            "p95_deg": round(float(ang[o][min(int(np.searchsorted(cw, 0.95 * cw[-1])), len(ang) - 1)]), 1),
            "share_over_10_deg": round(float(a[ang > 10].sum() / max(a.sum(), 1e-30)), 4)}


def carry_uvs(hero, me, tol):
    """Every corner of `me` takes the part's UVs at its foot on the part's nearest face of its material facing its
    own, searched from a little inside its face so that it lands on the face's side of a UV seam: the collapse
    interpolates the UVs where it moves a vertex, and the paint drawn from them (the plating, a sail's seams and
    insignia) slides. Returns how many corners found no face of their material."""
    if not len(me.loops) or not hero.UV:
        return 0
    P, NL, ML, C = corners(me)
    n = len(me.polygons)
    PN, PC, lt = np.empty(n * 3), np.empty(n * 3), np.empty(n, dtype=np.int64)
    me.polygons.foreach_get("normal", PN)
    me.polygons.foreach_get("center", PC)
    me.polygons.foreach_get("loop_total", lt)
    PC = PC.reshape(-1, 3)
    ft, fw, _ = hero.feet(PC, PN.reshape(-1, 3), face_keys(me), tol)     # each face's UVs at its centre: which
    UVL = np.hstack([hero.UV[k] for k in hero.UV])                         # side of a wrap seam its corners are on
    ref = (fw[:, :, None] * UVL[hero.L[ft]]).sum(1)[np.repeat(np.arange(n), lt)]
    tri, W, matched = hero.feet(P, NL, ML, tol, Q=inward(P, C, tol), ref=ref)
    names = list(hero.UV)
    for ly in me.uv_layers:
        uv = (W[:, :, None] * hero.UV[ly.name][hero.L[tri]]).sum(1)
        for c in (0, 1):
            if (ly.name, c) in hero.wraps:                   # the whole turn nearest its face's own: no face spans
                r = ref[:, 2 * names.index(ly.name) + c]       # the seam the long way round
                uv[:, c] += np.round(r - uv[:, c])
        ly.data.foreach_set("uv", uv.ravel())
    return int((~matched).sum())


def _p99(x, w):
    """The 99th percentile of x weighted by w, and the largest (0 for none)."""
    if not len(x):
        return 0.0, 0.0
    o = np.argsort(x)
    cw = np.cumsum(w[o])
    return float(x[o][min(int(np.searchsorted(cw, 0.99 * cw[-1])), len(x) - 1)]), float(x[o][-1])


def uv_slide(hero, me, tol, flat=FLAT, groups=None):
    """How far the paint slides on the twin. The materials draw from each UV map's two numbers separately (a seam is a
    line where one of them is constant: the plating's, a sail's cloths and tablings), so each number of each map the
    face's material reads (uv_reads) is held on its own: at seven points inside each of the twin's triangles (its centre
    and six about it, each standing for a seventh of its area: not its corners, which take the part's UVs exactly),
    the twin's value against the part's at the point's foot, over the rate the part's value changes along its surface
    there, is how far that number's lines have moved. Where a number hardly changes on the part (its rate
    under `flat` of its usual) it draws no line to move; where it changes far faster than usual (over 1/`flat`) it is
    a flag or a pole, not a line on the surface (the plating's mark for 'not plated', the spars' fittings, the centre
    of a spar's end cap, where the share round it is undefined): neither is measured. A number that is a length
    the material reads (light_bluebonnet.json's uv_numbers: 'metres') moves a line by its own error (but for where it
    jumps, as a spar's girth does to 0 at a fitting); one that sets something else ('setting') has its largest error
    reported, not held. Returns the largest slide and the 99th percentile by area (mm), the share of the area measured,
    and the twin's faces turned over (no face of the part's of their material facing their way near them) with the
    widest's width; with `groups` (each face's group: a tube) each group's 99th percentile too."""
    if not len(me.polygons):
        return {"max_mm": 0.0, "p99_mm": 0.0, "measured": 1.0, "turned_faces": 0, "turned_widest_mm": 0.0,
                "settings_largest_error": {}}
    V, LT, TP, PM = arrays(me)
    LL = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("loops", LL)
    LL = LL.reshape(-1, 3)
    tv = V[LT]
    C = tv.mean(1)
    w = [(1 / 3, 1 / 3, 1 / 3), (2 / 3, 1 / 6, 1 / 6), (1 / 6, 2 / 3, 1 / 6), (1 / 6, 1 / 6, 2 / 3),
         (1 / 6, 5 / 12, 5 / 12), (5 / 12, 1 / 6, 5 / 12), (5 / 12, 5 / 12, 1 / 6)]
    Wl = np.repeat(np.array(w), len(LT), axis=0)
    idx = np.tile(np.arange(len(LT)), len(w))
    P = (Wl[:, :, None] * tv[idx]).sum(1)
    FN = np.cross(tv[:, 1] - tv[:, 0], tv[:, 2] - tv[:, 0])
    FN /= np.maximum(np.linalg.norm(FN, axis=1), 1e-30)[:, None]
    ML = tri_mats(TP, face_keys(me))
    ULS = {}
    for ly in me.uv_layers:
        luv = np.empty(len(me.loops) * 2)
        ly.data.foreach_get("uv", luv)
        ULS[ly.name] = (Wl[:, :, None] * luv.reshape(-1, 2)[LL[idx]]).sum(1)
    ref = np.hstack([ULS[k] for k in hero.UV]) if hero.UV else None
    tri, W, matched = hero.feet(P, FN[idx], ML[idx], tol, Q=inward(P, C[idx], tol), ref=ref)
    slide = np.zeros(len(P))
    seen = np.zeros(len(P), dtype=bool)
    settings = {}
    for ly in me.uv_layers:
        ul = ULS[ly.name]
        huv = hero.UV[ly.name][hero.L[tri]]
        uh = (W[:, :, None] * huv).sum(1)
        read = hero.reads[ly.name][tri]
        for c in (0, 1):
            kind = LC["uv_numbers"].get(f"{ly.name}.{'uv'[c]}", "lines")
            du = ul[:, c] - uh[:, c]
            if (ly.name, c) in hero.wraps:
                du = du - np.round(du)
            if kind == "setting":                       # sets something else: its error reported, not held
                if (matched & read).any():
                    settings[f"{ly.name}.{'uv'[c]}"] = round(float(np.abs(du[matched & read]).max()), 5)
                continue
            g = hero.rate(ly.name, c)
            gt = g[tri]
            med = np.median(g[(g > 0) & hero.reads[ly.name]]) if ((g > 0) & hero.reads[ly.name]).any() else 0.0
            ok = matched & read & (gt < med / flat)     # (not where it jumps: a flag's edge, a pole)
            if kind == "metres":                        # a length the material reads: its error is the slide
                d = np.where(ok, np.abs(du), 0.0)
            else:                                       # lines where it takes a value: error over its rate
                ok &= gt > flat * med
                d = np.where(ok, np.abs(du) / np.maximum(gt, 1e-30), 0.0)
            slide = np.maximum(slide, d)
            seen |= ok
    # a twin face with no face of the part's of its material facing its way within twice the tolerance is turned over
    # or folded: it must be narrower than the tolerance (its area over its longest edge), under a pixel
    k = len(LT)
    lone = ~matched[:k]                                            # at the triangles' centres
    area = tri_area(V, LT)
    L = np.linalg.norm(tv - np.roll(tv, 1, axis=1), axis=2).max(1)
    width = 2 * area / np.maximum(L, 1e-12)
    wt = np.tile(area, len(w)) / len(w)                            # each point stands for its share of the area
    p99, big = _p99(slide[seen], wt[seen])
    out = {}
    if groups is not None:
        gp = np.tile(groups[TP], len(w))
        out["group_p99_mm"] = {int(g): round(_p99(slide[seen & (gp == g)], wt[seen & (gp == g)])[0] * 1000, 2)
                               for g in np.unique(groups)}
    return {**out, "max_mm": round(big * 1000, 2), "p99_mm": round(p99 * 1000, 2),
            "measured": round(float(wt[seen].sum() / max(wt.sum(), 1e-30)), 4), "turned_faces": int(lone.sum()),
            "turned_widest_mm": round(float(width[lone].max()) * 1000, 2) if lone.any() else 0.0,
            "settings_largest_error": settings}


# ------------------------------------------------------------------------------------------------ the whole boat
def outside(objs=None):
    """The parts seen from outside: every mesh but slice 1's reference hull, the twins and below decks."""
    objs = objs if objs is not None else bpy.context.scene.objects
    return [o for o in objs if o.type == "MESH" and o.name not in LC["skip"] and o.get("light_of") is None
            and o.get("slice", 1) not in LC["below_slices"]]


def shown_in(o, suit, tack="starboard"):
    """Whether a part shows in a suit (render_jclass.py's rule): sails by their suits, the running rigging and flags by
    their suit, a runner set on the tack's side and let off on the other, everything else always."""
    if o.get("sail") is not None:
        return suit in o["suits"].split(",")
    if o.get("suit") is not None:
        return o["suit"] == suit
    if o.get("state") is not None:
        return (o["state"] == "Set") == (o["side"] == tack)
    return True


def clear():
    for o in [o for o in bpy.data.objects if o.get("light_of") is not None]:
        me = o.data
        bpy.data.objects.remove(o)
        if me.users == 0:
            bpy.data.meshes.remove(me)


def build(log=print):
    """Every outside part's twin (any made before are removed first) and the report."""
    clear()
    tol = tolerance()
    parts = sorted(outside(), key=lambda o: o.name)
    per = {}
    for ob in parts:
        _, rep = twin(ob, tol)
        rep["suits"] = [s for s in SUITS if shown_in(ob, s)]     # where it shows (starboard tack), for gate_views.py
        per[ob.name] = rep
        m = rep["measure"]
        log(f"Light: {ob.name:26s} {rep['hero_triangles']:7d} -> {rep['light_triangles']:6d} ({rep['share']:.3f}) "
            f"error {m['error_mm']} mm  paint {m['paint_slide_mm']} mm  specks {rep['specks']['count']}  "
            f"tubes {rep.get('tubes', {}).get('count', 0)}"
            f"  {'ok' if rep['ok'] else 'FAILS'}")
    suits = {}
    for s in SUITS:
        hero = sum(per[o.name]["hero_triangles"] for o in parts if shown_in(o, s))
        light = sum(per[o.name]["light_triangles"] for o in parts if shown_in(o, s))
        suits[s] = {"hero_triangles": hero, "light_triangles": light, "share": round(light / hero, 4)}
    worst = max(per.values(), key=lambda r: r["measure"]["error_mm"] or 0.0)
    err = max(r["measure"]["error_mm"] or 0.0 for r in per.values()) / 1000
    swe = max(r["measure"]["switch_error_mm"] for r in per.values()) / 1000     # surface, paint or a turned face
    s = LC["screen"]
    half = math.tan(math.radians(s["fov_deg"]) / 2)
    out = {"tolerance_mm": round(tol * 1000, 2),
           "screen": {k: v for k, v in s.items() if k != "note"}, "from_m": LC["from_m"], "pixels": LC["pixels"],
           "parts": per, "suits": suits,
           "largest_share": max(v["share"] for v in suits.values()), "budget_share": LC["budget_share"],
           "worst_error_mm": round(err * 1000, 2),
           "worst_part": next(k for k, v in per.items() if v is worst),
           "worst_paint_slide_mm": max(r["measure"]["paint_slide_mm"] for r in per.values()),
           "worst_paint_slide_p99_mm": max(r["measure"]["paint_slide_p99_mm"] for r in per.values()),
           "twins": sum(1 for o in bpy.context.scene.objects if o.get("light_of") is not None),
           "parts_outside": len(outside()),
           "worst_switch_error_mm": round(swe * 1000, 2),
           "one_pixel_from_m": {"4K at 60 deg": round(swe * s["width_px"] / (2 * half), 1),
                                "4K at 90 deg": round(swe * s["width_px"] / 2, 1),
                                "1080p at 90 deg": round(swe * 1920 / 2, 1)},
           "failing": sorted(k for k, v in per.items() if not v["ok"])}
    out["ok"] = not out["failing"] and out["largest_share"] <= LC["budget_share"]
    return out


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    d = os.path.abspath(args[0])
    bpy.ops.wm.open_mainfile(filepath=os.path.join(d, "jclass.blend"))
    rep = build()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(d, "jclass.blend"))
    with open(os.path.join(d, "light.json"), "w") as f:
        json.dump(rep, f, indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k != "parts"}, indent=1))
