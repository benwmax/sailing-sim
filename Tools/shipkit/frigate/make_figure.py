"""Our figurehead's mesh (docs/shipkit-9) from a scan of Bertel Thorvaldsen's "Goddess of Hope" (Zenodo record
10242636, https://zenodo.org/records/10242636, scan by Geoffrey Marchal, CC BY 4.0: credited in CREDITS.md). The scan's
pieces are joined and welded and turned so she faces +X (the scan's height and depth are its principal axes; she faces
the side her flower is held out to), then stood level on her plinth (its top is the plane its upward faces fit; her long
axis leans 5.9 deg off it, her weight on one foot), the plinth cut off just over its top (she stands on our console in
the ship) and stray scan islands dropped. Then she is closed: the cut at her feet is levelled onto the cut and capped
flat, and the holes the scan left (the top of her head, which the camera never saw, and a few pinholes) are filled and
faired into the surface round them (holes, patch, fair). Last she is scaled to stand 1 m (her feet at z 0) and
decimated to the triangle count given. Written to figure_hope.npz: 'V' her vertices quantised to 16 bits over 'box'
(lo, hi), 'T' the triangles (uint32).
The scan itself is not kept in the repository: put it in Data/Figurehead/raw/ (git-ignored; its sha256 is SHA below).

    blender python: make_figure.py <hope.glb> [triangles]       (Blender's Python: pip bpy)
"""
import hashlib
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import deck  # noqa: E402
SHA = "e2093ea0e5a4cb4d217a3c1f036ca73fa1a79167e7480ef965a9b7024337ba40"
# lengths before she is scaled are of the scan's height, plinth and all (about 2.45 m for her 2.3 m in the ship)
PLINTH_FIT = 0.003          # the plinth's top: its upward faces within this of the plane they fit
PLINTH_CLEAR = 0.006        # she is cut off her plinth this far over its top (1.5 cm at her size), clear of its faces
ISLAND_MIN = 200            # scan islands with fewer triangles than this are noise
FEET_RIM = 0.02             # the cut at her feet: a hole whose rim lies within this over the cut
PINHOLE = 5                 # a hole of this many edges or fewer is closed by a fan


def plinth(Q, T):
    """The plinth's top: the plane (its upward normal, a point on it) of the faces looking up in the scan's lowest tenth,
    fitted by area (the normal is the least axis of the face centres' spread), then again on those of them within
    PLINTH_FIT of it, until the faces it takes stop changing."""
    C = Q[T].mean(1)
    N = np.cross(Q[T[:, 1]] - Q[T[:, 0]], Q[T[:, 2]] - Q[T[:, 0]])
    A = np.linalg.norm(N, axis=1)
    N /= np.maximum(A, 1e-20)[:, None]
    low = C[:, 2] < Q[:, 2].min() + 0.1 * np.ptp(Q[:, 2])
    sel = low & (N[:, 2] > 0.9)
    for _ in range(30):
        w = A[sel]
        on = (C[sel] * w[:, None]).sum(0) / w.sum()
        n = np.linalg.svd((C[sel] - on) * np.sqrt(w)[:, None], full_matrices=False)[2][2]
        n *= np.sign(n[2])
        was, sel = sel, low & (N @ n > 0.9) & (np.abs((C - on) @ n) < PLINTH_FIT)
        if np.array_equal(was, sel):
            break
    else:
        raise SystemExit("the plinth's top would not settle on a plane")
    print(f"plinth's top: {int(sel.sum())} faces, {np.degrees(np.arccos(n[2])):.2f} deg off her long axis")
    return n, on


def upright(n):
    """The turn that takes the unit vector n to +z (about their common perpendicular)."""
    z = np.array([0.0, 0.0, 1.0])
    k = np.cross(n, z)
    s, c = np.linalg.norm(k), float(n @ z)
    if s < 1e-12:
        return np.eye(3)
    k /= s
    K = np.array([[0.0, -k[2], k[1]], [k[2], 0.0, -k[0]], [-k[1], k[0], 0.0]])
    return np.eye(3) + s * K + (1.0 - c) * K @ K


def holes(T):
    """The mesh's open edges chained into a loop per hole, each the way its faces run it (a face's edge a -> b on the
    rim; a patch must run it b -> a)."""
    D = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]).tolist()
    S = set(map(tuple, D))
    nxt = {}
    for a, b in D:
        if (b, a) not in S:
            if a in nxt:
                raise SystemExit(f"vertex {a} lies on two holes")
            nxt[a] = b
    loops, seen = [], set()
    for s in nxt:
        if s in seen:
            continue
        loop, v = [s], nxt[s]
        seen.add(s)
        while v != s:
            loop.append(v)
            seen.add(v)
            v = nxt[v]
        loops.append(np.array(loop))
    return loops


def trim(T, n, limit=2000):
    """The scan's ragged rims trimmed: where an edge inside her joins two points of one hole's rim that are not next to
    each other along it (a chord), the few faces between it and the rim are dropped, so the rim runs along the chord
    and no fill can repeat an edge she has. Returns the faces left."""
    def faces_of(k):
        i = int(np.searchsorted(uk, k))
        return fs[first[i]:first[i] + cnt[i]]

    def side(f, chord):                             # the faces reached from f without crossing the chord or the rim
        seen, todo = {int(f)}, [int(f)]
        while todo:
            g = todo.pop()
            a, b, c = T[g]
            for x, y in ((a, b), (b, c), (c, a)):
                k = min(x, y) * n + max(x, y)
                if k == chord:
                    continue
                for h in faces_of(k):
                    if int(h) not in seen:
                        seen.add(int(h))
                        todo.append(int(h))
                        if len(seen) > limit:
                            return None
        return seen
    for _ in range(20):
        loops = holes(T)
        where, at = np.full(n, -1), np.full(n, -1)
        for i, lp in enumerate(loops):
            where[lp], at[lp] = i, np.arange(len(lp))
        U = np.sort(np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]), axis=1).astype(np.int64)
        key = U[:, 0] * n + U[:, 1]
        srt = np.argsort(key, kind="stable")
        fs = np.tile(np.arange(len(T)), 3)[srt]
        uk, first, cnt = np.unique(key[srt], return_index=True, return_counts=True)
        a, b = uk // n, uk % n
        m = np.array([len(loops[i]) if i >= 0 else 0 for i in where[a]])
        gap = np.abs(at[a] - at[b])
        chords = uk[(cnt == 2) & (where[a] >= 0) & (where[a] == where[b]) & (gap != 1) & (gap != m - 1)]
        if not len(chords):
            return T
        drop = set()
        for k in chords:
            for f in faces_of(k):
                got = side(f, k)
                if got is not None:
                    drop |= got
                    break
            else:
                raise SystemExit("a chord across one of her holes has her on both sides")
        T = np.delete(T, sorted(drop), axis=0)
    raise SystemExit("her holes' rims would not come clean")


def crossings(Q):
    """How many pairs of the closed outline Q's edges (not neighbours) cross."""
    A, B, n = Q, np.roll(Q, -1, axis=0), len(Q)
    i, j = np.triu_indices(n, 2)
    keep = ~((i == 0) & (j == n - 1))
    i, j = i[keep], j[keep]
    r, s, d = B[i] - A[i], B[j] - A[j], A[j] - A[i]
    den = r[:, 0] * s[:, 1] - r[:, 1] * s[:, 0]
    ok = np.abs(den) > 1e-18
    den = np.where(ok, den, 1.0)
    t = (d[:, 0] * s[:, 1] - d[:, 1] * s[:, 0]) / den
    u = (d[:, 0] * r[:, 1] - d[:, 1] * r[:, 0]) / den
    return int(np.count_nonzero(ok & (t >= 0) & (t <= 1) & (u >= 0) & (u <= 1)))


def patch(P, loop, flat=False):
    """New points and faces over one hole (loop as holes() gives it), its faces running each rim edge the other way.
    A pinhole is closed by a fan. Any other hole is triangulated (deck.cdt) seen square to its rim (from below for the
    cut at her feet: flat), with new points inside at the rim's own spacing (three times it on the flat cap); the new
    points are numbered on from len(P). The flat cap's rim is eased in P itself where it folds over."""
    if len(loop) <= PINHOLE:
        F = np.array([(loop[0], loop[i + 1], loop[i]) for i in range(1, len(loop) - 1)])
        return np.zeros((0, 3)), F
    R = P[loop[::-1]]
    h = float(np.mean(np.linalg.norm(np.roll(R, -1, axis=0) - R, axis=1)))
    c = R.mean(0)
    if flat:
        e1, e2 = np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])
    else:                                           # seen square to the rim's vector area: the way the hole faces
        nv = 0.5 * np.cross(R - c, np.roll(R, -1, axis=0) - c).sum(0)
        nv /= np.linalg.norm(nv)
        e1 = np.linalg.svd(R - c, full_matrices=False)[2][0]
        e1 = (e1 - (e1 @ nv) * nv) / np.linalg.norm(e1 - (e1 @ nv) * nv)
        e2 = np.cross(nv, e1)
    Q = np.stack([(R - c) @ e1, (R - c) @ e2], 1)
    # a ragged rim that folds over itself seen so is eased for the triangulation only (its points stay where they
    # are), and on the flat cap for good: the cut's edge, inside the console
    for _ in range(60):
        if not crossings(Q):
            break
        Q = 0.5 * Q + 0.25 * (np.roll(Q, 1, axis=0) + np.roll(Q, -1, axis=0))
    else:
        raise SystemExit("a hole's rim folds over itself however it is eased")
    if flat:
        P[loop[::-1], :2] = c[:2] + Q
    P2, T2 = deck.cdt(Q, [], (3.0 if flat else 1.0) * h)
    k = len(R)
    new = c + P2[k:, :1] * e1 + P2[k:, 1:2] * e2
    F = np.concatenate([loop[::-1], len(P) + np.arange(len(new))])[T2]
    E = {(int(f[i]), int(f[(i + 1) % 3])) for f in F for i in range(3)}
    a, b = int(loop[0]), int(loop[1])
    if (a, b) in E:
        F = F[:, ::-1]
    elif (b, a) not in E:
        raise SystemExit("a hole's patch does not take its rim")
    return new, F


def fair(P, T, free, rows):
    """The free points moved so that the surface's (uniform) Laplacian is as small as it can be, in least squares, at
    rows: a patch's own points and its rim, whose Laplacians reach the ring outside it, which stays. So the patch takes
    up the slope and the curve of the surface round it (the bi-Laplacian fairing of Liepa's hole filling, 2003)."""
    from scipy.sparse import coo_matrix, diags, identity
    from scipy.sparse.linalg import spsolve
    n = len(P)
    E = np.unique(np.sort(np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]), axis=1), axis=0)
    A = coo_matrix((np.ones(2 * len(E)), (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])), shape=(n, n)).tocsr()
    deg = np.maximum(np.asarray(A.sum(1)).ravel(), 1.0)
    L = (identity(n, format="csr") - diags(1.0 / deg) @ A).tocsr()[rows]
    fixed = np.setdiff1d(np.arange(n), free)
    Af, Bf = L[:, free], L[:, fixed] @ P[fixed]
    M = (Af.T @ Af).tocsc()
    P = P.copy()
    P[free] = np.column_stack([spsolve(M, -(Af.T @ Bf[:, k])) for k in range(3)])
    return P


def closed(T, n):
    """Every edge has two faces, running it once each way: closed, and every face turned the same way."""
    D = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]).astype(np.int64)
    key, back = D[:, 0] * n + D[:, 1], D[:, 1] * n + D[:, 0]
    return len(np.unique(key)) == len(key) and bool(np.isin(back, key).all())


def close(P, T):
    """Her holes closed: the rims trimmed (trim); the cut at her feet (each hole whose rim lies within FEET_RIM over the
    cut) levelled onto the cut and capped flat; every other hole filled (patch) and the fills faired together (fair).
    Fails if she is not then closed, or a fill crosses her. Returns the points, the faces and each hole's count of
    edges."""
    T = trim(T, len(P))
    loops = holes(T)
    feet = [len(lp) > PINHOLE and P[lp, 2].max() < PLINTH_CLEAR + FEET_RIM for lp in loops]
    if not any(feet):
        raise SystemExit("no hole at her feet: the plinth's cut is not where it was looked for")
    P = P.copy()
    for lp, ft in zip(loops, feet):
        if ft:
            P[lp, 2] = PLINTH_CLEAR
    n_scan, faces, free, rows = len(T), [T], [], []
    for lp, ft in zip(loops, feet):
        new, F = patch(P, lp, flat=ft)
        if len(new) and not ft:
            free.append(len(P) + np.arange(len(new)))
            rows += [free[-1], lp]
        P = np.concatenate([P, new])
        faces.append(F)
    T = np.concatenate(faces).astype(np.int64)
    if free:
        P = fair(P, T, np.concatenate(free), np.concatenate(rows))
    if not closed(T, len(P)):
        raise SystemExit("her holes' fills leave her open, or turn faces over")
    from mathutils.bvhtree import BVHTree
    pt = np.arange(n_scan, len(T))
    tp = BVHTree.FromPolygons(P.tolist(), T[pt].tolist(), all_triangles=True)
    ts = BVHTree.FromPolygons(P.tolist(), T[:n_scan].tolist(), all_triangles=True)
    cross = [(i, j) for i, j in tp.overlap(ts) if not set(T[pt[i]].tolist()) & set(T[j].tolist())]
    if cross:
        raise SystemExit(f"{len(cross)} of her holes' fill faces cross her")
    return P, T, [len(lp) for lp in loops]


def main(src, target):
    h = hashlib.sha256(open(src, "rb").read()).hexdigest()
    if h != SHA:
        print(f"warning: {src} is not the scan this was made from (sha256 {h})")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=src)
    Vs, Ts, n0 = [], [], 0
    for o in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
        M = np.array(o.matrix_world)
        V = np.empty(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", V)
        o.data.calc_loop_triangles()
        T = np.empty(len(o.data.loop_triangles) * 3, int)
        o.data.loop_triangles.foreach_get("vertices", T)
        Vs.append(V.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])
        Ts.append(T.reshape(-1, 3) + n0)
        n0 += len(Vs[-1])
    V, T = np.concatenate(Vs), np.concatenate(Ts)
    # her own frame: x her depth (she faces -x here), y her breadth, z her height from the plinth's foot. The ship's
    # frame is Unreal's (Y to starboard: left-handed), so a mesh drawn in it reads mirrored in Blender and the right way
    # round in the game: the basis is made a reflection whatever signs the SVD gives (they differ between maths
    # libraries), so that in the game she stands as the statue does, and every triangle is turned over with it so her
    # faces still look out (every flip after this one is a pair: a turn)
    c = V.mean(0)
    _, _, W = np.linalg.svd(V - c, full_matrices=False)
    B = np.stack([W[2], W[1], W[0]], 1)
    if np.linalg.det(B) > 0:
        B[:, 1] *= -1
    Q = (V - c) @ B
    T = T[:, ::-1].copy()
    z = Q[:, 2]
    lo, hi = z.min(), z.max()
    foot = lambda s: np.ptp(Q[s, 0]) * np.ptp(Q[s, 1])          # noqa: E731
    if foot(z > hi - 0.04 * (hi - lo)) > foot(z < lo + 0.04 * (hi - lo)):  # the plinth is the broad end
        Q[:, 2] *= -1
        Q[:, 1] *= -1
    # she holds her flower out in front: the side of her depth axis her upper body reaches furthest to
    zz = (Q[:, 2] - Q[:, 2].min()) / np.ptp(Q[:, 2])
    up = (zz > 0.55) & (zz < 0.8)
    if Q[up, 0].max() > -Q[up, 0].min():                      # she faces +x: turn her to face -x like the scan
        Q[:, 0] *= -1
        Q[:, 1] *= -1
    Q[:, 2] -= Q[:, 2].min()
    Q /= np.ptp(Q[:, 2])
    # to the ship's way of standing: facing +x
    Q[:, 0] *= -1
    Q[:, 1] *= -1
    # stood level on her plinth, its top at z 0
    n_up, on = plinth(Q, T)
    Q = (Q - on) @ upright(n_up).T
    me = bpy.data.meshes.new("Hope")
    me.from_pydata(Q.tolist(), [], T.tolist())
    me.validate()
    for o in list(bpy.context.scene.objects):
        bpy.data.objects.remove(o)
    ob = bpy.data.objects.new("Hope", me)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=1e-5)
    bpy.ops.object.mode_set(mode="OBJECT")
    # cut the plinth off: drop every triangle with a corner under PLINTH_CLEAR over its top
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < PLINTH_CLEAR], context="VERTS")
    # stray islands
    seen, small = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, isl = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            isl.append(g)
            for e in g.edges:
                for h2 in e.link_faces:
                    if h2.index not in seen:
                        seen.add(h2.index)
                        stack.append(h2)
        if len(isl) < ISLAND_MIN:
            small += isl
    bmesh.ops.delete(bm, geom=small, context="FACES")
    bm.to_mesh(me)
    bm.free()
    me.update()
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    P = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", P)
    T = np.empty(n * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", T)
    # close her before decimating, while each hole's rim is a clean loop: the cut at her feet levelled and capped flat,
    # the top of her head and the pinholes filled and faired
    P, T, filled = close(P.reshape(-1, 3), T.reshape(-1, 3))
    me.clear_geometry()
    me.from_pydata(P.tolist(), [], T.tolist())
    me.update()
    mod = ob.modifiers.new("decimate", "DECIMATE")
    mod.ratio = min(1.0, target / len(T))
    mod.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    md = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    md.calc_loop_triangles()
    P = np.empty(len(md.vertices) * 3)
    md.vertices.foreach_get("co", P)
    P = P.reshape(-1, 3)
    P[:, 2] -= P[:, 2].min()
    P /= P[:, 2].max()                                        # 1 m tall, her feet (the cut) at z 0
    T = np.empty(len(md.loop_triangles) * 3, np.int64)
    md.loop_triangles.foreach_get("vertices", T)
    T = T.reshape(-1, 3)
    used = np.unique(T)
    remap = np.full(len(P), -1)
    remap[used] = np.arange(len(used))
    P, T = P[used], remap[T]
    if not closed(T, len(P)):
        raise SystemExit("decimating her left her open, or turned faces over")
    # her faces must look out: the volume she bounds is positive
    o = P.mean(0)
    vol = float(np.einsum("ij,ij->i", P[T[:, 0]] - o, np.cross(P[T[:, 1]] - o, P[T[:, 2]] - o)).sum() / 6.0)
    if vol <= 0.0:
        raise SystemExit(f"her faces look inward (signed volume {vol:.5f})")
    box = np.array([P.min(0), P.max(0)])
    q = np.round((P - box[0]) / (box[1] - box[0]) * 65535).astype(np.uint16)
    out = os.path.join(HERE, "figure_hope.npz")
    np.savez_compressed(out, V=q, box=box.astype(np.float64), T=T.astype(np.uint32))
    print(f"{n} triangles cut and cleaned; holes closed {sorted(filled, reverse=True)} (edges round each); decimated to "
          f"{len(T)} triangles, {len(P)} vertices; size {np.ptp(P, 0).round(3)}; volume {vol:.5f}; "
          f"{os.path.getsize(out) / 1e6:.2f} MB -> {out}")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    main(args[0], int(args[1]) if len(args) > 1 else 150000)
