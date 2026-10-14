"""Small raster/vector helpers (numpy only): sparse connected components, pixel-edge outlines, Douglas-Peucker,
oriented rectangles, centrelines, convex hulls."""
import numpy as np


def components(e, n):
    """8-connected components of a sparse pixel set (integer metre coords). Returns a label per pixel (0..k-1)."""
    order = np.lexsort((e, n)); es, ns = e[order], n[order]
    m = len(es)
    if m == 0:
        return np.zeros(0, np.int64)
    brk = np.ones(m, bool); brk[1:] = (ns[1:] != ns[:-1]) | (es[1:] != es[:-1] + 1)
    starts = np.nonzero(brk)[0]; ends = np.append(starts[1:], m)
    rn = ns[starts]; re0 = es[starts]; re1 = es[ends - 1]
    R = len(starts)
    parent = np.arange(R)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    # runs are sorted by row then column: sweep pairs of consecutive rows
    rows, rstart = np.unique(rn, return_index=True)
    rend = np.append(rstart[1:], R)
    rowpos = {int(r): (int(a), int(b)) for r, a, b in zip(rows, rstart, rend)}
    for r, (a, b) in rowpos.items():
        if r - 1 not in rowpos:
            continue
        pa, pb = rowpos[r - 1]
        i, j = a, pa
        while i < b and j < pb:
            if re0[i] <= re1[j] + 1 and re0[j] <= re1[i] + 1:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)
            if re1[i] < re1[j]:
                i += 1
            else:
                j += 1
    roots = np.array([find(i) for i in range(R)])
    _, runlab = np.unique(roots, return_inverse=True)
    lab_sorted = np.repeat(runlab, ends - starts)
    lab = np.empty(m, np.int64); lab[order] = lab_sorted
    return lab


def group(lab):
    """indices per label, as a list."""
    o = np.argsort(lab, kind="stable"); s = lab[o]
    cuts = np.nonzero(np.diff(s))[0] + 1
    return np.split(o, cuts)


def to_mask(e, n, pad=1):
    e0, n0 = e.min() - pad, n.min() - pad
    W, H = e.max() - e0 + 1 + pad, n.max() - n0 + 1 + pad
    M = np.zeros((H, W), bool); M[n - n0, e - e0] = True   # row = northing offset (row 0 = south)
    return M, e0, n0


def from_mask(M, e0, n0):
    r, c = np.nonzero(M); return c + e0, r + n0


def rings(M, e0, n0):
    """Pixel-edge outline of a boolean mask (row 0 = south). Outer rings counter-clockwise, holes clockwise,
    vertices in integer metres. Diagonal touches are joined (8-connectivity)."""
    P = np.pad(M, 1)
    H, W = P.shape
    edges = {}
    def add(a, b):
        edges.setdefault(a, []).append(b)
    rr, cc = np.nonzero(P)
    for r, c in zip(rr.tolist(), cc.tolist()):
        x, y = c - 1 + e0, r - 1 + n0
        if not P[r - 1, c]: add((x, y), (x + 1, y))
        if not P[r, c + 1]: add((x + 1, y), (x + 1, y + 1))
        if not P[r + 1, c]: add((x + 1, y + 1), (x, y + 1))
        if not P[r, c - 1]: add((x, y + 1), (x, y))
    out = []
    while edges:
        start = next(iter(edges))
        ring = [start]; cur = start; prev_dir = None
        while True:
            outs = edges.get(cur)
            if not outs:
                break
            if len(outs) == 1:
                nxt = outs.pop()
            else:  # saddle: turn right (joins diagonal pixels into one ring, 8-connectivity)
                def turn(b):
                    d = (b[0] - cur[0], b[1] - cur[1])
                    if prev_dir is None: return 0
                    return prev_dir[0] * d[1] - prev_dir[1] * d[0]
                outs.sort(key=turn, reverse=True); nxt = outs.pop()
            if not outs:
                del edges[cur]
            prev_dir = (nxt[0] - cur[0], nxt[1] - cur[1])
            cur = nxt
            if cur == start:
                break
            ring.append(cur)
        if len(ring) >= 4:
            out.append(np.array(ring + [ring[0]], float))
    return out


def area(ring):
    x, y = ring[:, 0], ring[:, 1]
    return 0.5 * float(np.sum(x[:-1] * y[1:] - x[1:] * y[:-1]))


def dp(pts, tol):
    """Douglas-Peucker on an open polyline (N x 2)."""
    if len(pts) < 3:
        return pts
    keep = np.zeros(len(pts), bool); keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1: continue
        p, q = pts[a], pts[b]; seg = q - p; L = np.hypot(*seg)
        sub = pts[a + 1:b]
        d = np.abs(seg[0] * (sub[:, 1] - p[1]) - seg[1] * (sub[:, 0] - p[0])) / L if L > 0 else np.hypot(*(sub - p).T)
        k = int(np.argmax(d))
        if d[k] > tol:
            m = a + 1 + k; keep[m] = True; stack += [(a, m), (m, b)]
    return pts[keep]


def simplify_ring(ring, tol):
    # split at the vertex farthest from the start so both halves are proper polylines
    k = int(np.argmax(np.hypot(*(ring - ring[0]).T)))
    a = dp(ring[:k + 1], tol); b = dp(ring[k:], tol)
    r = np.vstack([a, b[1:]])
    return r if len(r) >= 4 else ring


def obb(x, y):
    """oriented box of pixel centres: (cx, cy, grid azimuth deg 0..180 of the long axis, length, width, ux, uy)."""
    cx, cy = x.mean(), y.mean()
    if len(x) < 3:
        return cx, cy, 0.0, 1.0, 1.0, 0.0, 1.0
    C = np.cov(np.vstack([x - cx, y - cy]))
    w, v = np.linalg.eigh(C); ux, uy = v[:, 1]
    u = (x - cx) * ux + (y - cy) * uy; t = -(x - cx) * uy + (y - cy) * ux
    L = u.max() - u.min() + 1; Wd = t.max() - t.min() + 1
    az = (np.degrees(np.arctan2(ux, uy)) + 180) % 180
    return float(x.mean()), float(y.mean()), float(az), float(L), float(Wd), float(ux), float(uy)


def centreline(x, y, step=10.0):
    """polyline along the principal axis: mean cross-offset per `step` m bin, plus the width of each bin."""
    cx, cy, az, L, Wd, ux, uy = obb(x, y)
    u = (x - cx) * ux + (y - cy) * uy; t = -(x - cx) * uy + (y - cy) * ux
    b = np.floor((u - u.min()) / step).astype(int)
    pts, wid = [], []
    for k in range(b.max() + 1):
        s = b == k
        if s.sum() == 0: continue
        uu = u[s].mean() if k not in (0, b.max()) else (u.min() if k == 0 else u.max())
        tt = t[s].mean()
        pts.append((cx + uu * ux - tt * uy, cy + uu * uy + tt * ux)); wid.append(s.sum() / min(step, max(1.0, u[s].max() - u[s].min() + 1)))
    return np.array(pts), np.array(wid)


def hull(px, py):
    P = sorted(set(zip(px.tolist(), py.tolist())))
    if len(P) < 3: return np.array(P + P[:1], float)
    def cr(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in P:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    h = lo[:-1] + up[:-1]
    return np.array(h + h[:1], float)
