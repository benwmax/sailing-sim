"""Lines check (docs/shipkit-1): draws a built hull's own lines over the drawing it was taken from and measures how far
they land from the drawing's ink.

    python lines_check.py <hull.obj> <drawing.json> <scan.jpg> <out dir>

The hull is the OBJ's object "Hull" (both sides; the starboard half is cut), the outline uses every object.

Reads the built mesh (an OBJ exported by the build, not the loft's tables), cuts it with the drawing's own planes and
projects the cuts into each view of the scan through the registration in <drawing.json> (scanreg.py):

  half-breadth plan   the waterlines (horizontal cuts)
  body plan           the stations (transverse cuts), aft ones on the left, forward ones on the right
  sheer plan          the outline in profile (keel, stem, sternpost, sheer, stern face) and the buttocks (cuts at a
                      fixed half-breadth)

For each line it samples the projected cut every 2 px and looks up the distance to the nearest ink (the scan's bright
pixels: the drawing is light lines on a dark ground, and any line counts). It reports the median and 90th percentile
distance and the share of samples within 2 px ("on the line"); 11.1 px is a foot across the sheet and 11.69 down it
(drawing.json px_per_ft, px_per_ft_down). The outline's edge pixels are thinned to one per 2 px square, so it weighs
like the other lines. The buttocks are scored below A only (above it the cut runs up the topsides, where the drawing
has no buttock ink) and outside drawing.json's buttocks_undrawn_x_px, where the drawing leaves them out. The overall
figures are over every sample. Ink from a neighbouring line can make a miss read as a hit where lines bunch (midship,
the waterlines near the top), so the overlay images are part of the check: <out>/overlay_<view>.png.

Needs numpy, scipy and Pillow.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt, label

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scanreg import ScanRegistration  # noqa: E402

FT = 0.3048


def load_obj(path):
    """Objects of an OBJ as name -> (V (n,3) in X forward, Y starboard, Z up, triangles (m,3))."""
    objs, cur, V, base = {}, None, [], 0
    allv = []
    for line in open(path):
        if line.startswith("o "):
            cur = line[2:].strip()
            objs[cur] = []
        elif line.startswith("v "):
            x, y, z = map(float, line.split()[1:4])
            allv.append((x, -z, y))                 # OBJ Y up -> body frame
        elif line.startswith("f "):
            idx = [int(t.split("/")[0]) - 1 for t in line.split()[1:]]
            for k in range(1, len(idx) - 1):
                objs[cur].append((idx[0], idx[k], idx[k + 1]))
    allv = np.array(allv)
    out = {}
    for name, tris in objs.items():
        out[name] = (allv, np.array(tris, int))
    return out


def plane_cut(V, T, axis, value):
    """Segments where the triangles cross the plane coordinate[axis] = value: (k, 2, 3)."""
    P = V[T]                                         # (m, 3, 3)
    d = P[:, :, axis] - value
    s = np.sign(d)
    s[s == 0] = 1e-9
    cross = ~((s > 0).all(1) | (s < 0).all(1))
    P, d = P[cross], d[cross]
    segs = []
    for tri, dd in zip(P, d):
        pts = []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            if (dd[a] > 0) != (dd[b] > 0):
                t = dd[a] / (dd[a] - dd[b])
                pts.append(tri[a] + t * (tri[b] - tri[a]))
        if len(pts) == 2:
            segs.append(pts)
    return np.array(segs).reshape(-1, 2, 3)


def chain(segs, tol=1e-5):
    """Orders cut segments into polylines (longest first)."""
    if len(segs) == 0:
        return []
    key = lambda p: (round(p[0] / tol), round(p[1] / tol), round(p[2] / tol))
    adj = {}
    for a, b in segs:
        ka, kb = key(a), key(b)
        adj.setdefault(ka, []).append((kb, b))
        adj.setdefault(kb, []).append((ka, a))
    pos = {}
    for a, b in segs:
        pos[key(a)] = a
        pos[key(b)] = b
    seen, lines = set(), []
    for start in sorted(adj, key=lambda k: len(adj[k])):
        if start in seen:
            continue
        line, cur, prev = [pos[start]], start, None
        seen.add(start)
        while True:
            nxt = [k for k, _ in adj[cur] if k not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            line.append(pos[cur])
        lines.append(np.array(line))
    return sorted(lines, key=lambda l: -len(l))


class Drawing:
    def __init__(self, path, scan):
        self.d = json.load(open(path))
        self.reg = ScanRegistration(path)
        self.ppf = self.d["px_per_ft"]                       # across the sheet: lengths
        self.ppf_y = self.d.get("px_per_ft_down", self.ppf)   # down it: half-breadths (half-breadth plan) and heights
        self.all_d = {}
        self.mid = self.d["midship_x_px"]
        im = Image.open(scan).convert("L")
        if "scan_width_px" in self.d and im.size[0] != self.d["scan_width_px"]:
            sys.exit(f"{scan} is {im.size[0]} px wide; the readings are on the {self.d['scan_width_px']} px rendering "
                     "(fetch_refs.py without --full)")
        self.img = im
        a = np.asarray(im).astype(float)
        self.ink = {}
        for name, v in self.d["views"].items():
            x0, y0, x1, y1 = v["crop"]
            sub = a[y0:y1, x0:x1]
            thr = np.percentile(sub, v.get("ink_percentile", 88))
            mask = sub > max(thr, v.get("ink_min", 120))
            self.ink[name] = (distance_transform_edt(~mask), (x0, y0))

    def px(self, m):
        """A half-breadth or height in metres to the ship frame's pixels (down the sheet)."""
        return np.asarray(m) / FT * self.ppf_y

    def x_px(self, xm):
        return np.asarray(xm) / FT * self.ppf + self.mid

    # each view maps body-frame metres to scan pixels
    def hb_plan(self, P):
        x = self.x_px(P[:, 0])
        return np.stack([x, self.reg.centreline_y(x) - self.px(np.abs(P[:, 1]))], 1)

    def body(self, P, left):
        return np.stack(self.reg.ship_to_body(self.px(np.abs(P[:, 1])), self.px(P[:, 2]), left), 1)

    def sheer(self, P):
        return np.stack(self.reg.ship_to_sheer(self.x_px(P[:, 0]), self.px(P[:, 2])), 1)

    def _result(self, name, d, length_ft):
        self.all_d[name] = d
        return {"samples": int(len(d)), "median_px": round(float(np.median(d)), 2), "p90_px": round(float(np.percentile(d, 90)), 2),
                "on_line": round(float((d <= 2.0).mean()), 3), "length_ft": round(float(length_ft), 1)}

    def steps_ft(self, q):
        """Each step of a polyline in scan pixels, in feet: every view has lengths or half-breadths across the sheet
        and heights or half-breadths down it, so a step is (dx / px_per_ft, dy / px_per_ft_down)."""
        d = np.diff(q, axis=0)
        return np.hypot(d[:, 0] / self.ppf, d[:, 1] / self.ppf_y)

    def score_points(self, name, view, q):
        """Distance to ink of scattered points (the outline), thinned to one per 2 px square so it counts like a line
        sampled every 2 px."""
        dist, (x0, y0) = self.ink[view]
        q = q[np.unique(np.floor(q / 2.0).astype(int), axis=0, return_index=True)[1]]
        ix, iy = np.round(q[:, 0] - x0).astype(int), np.round(q[:, 1] - y0).astype(int)
        ok = (ix >= 0) & (iy >= 0) & (ix < dist.shape[1]) & (iy < dist.shape[0])
        return self._result(name, dist[iy[ok], ix[ok]], 2.0 * ok.sum() / np.sqrt(self.ppf * self.ppf_y))   # about

    def score(self, name, view, pts, keep=None):
        """Distance to ink of points sampled every 2 px along the projected line; keep (one flag per point) limits the
        samples to part of it."""
        dist, (x0, y0) = self.ink[view]
        if len(pts) < 2:
            return None
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        s = np.concatenate([[0], np.cumsum(seg)])
        if s[-1] < 4:
            return None
        t = np.arange(0, s[-1], 2.0)
        q = np.stack([np.interp(t, s, pts[:, 0]), np.interp(t, s, pts[:, 1])], 1)
        kept = np.ones(len(q), bool) if keep is None else np.interp(t, s, np.asarray(keep, float)) > 0.5
        length_ft = float(self.steps_ft(q)[kept[1:] & kept[:-1]].sum())
        q = q[kept]
        ix, iy = np.round(q[:, 0] - x0).astype(int), np.round(q[:, 1] - y0).astype(int)
        ok = (ix >= 0) & (iy >= 0) & (ix < dist.shape[1]) & (iy < dist.shape[0])
        d = dist[iy[ok], ix[ok]]
        if len(d) == 0:
            return None
        return self._result(name, d, length_ft)


def main(obj, drawing, scan, out):
    os.makedirs(out, exist_ok=True)
    D = Drawing(drawing, scan)
    objs = load_obj(obj)
    shell = [k for k in objs if k == "Hull" or k.startswith("Hull_Stbd")]
    V, T = objs[shell[0]]
    T = T[(V[T][:, :, 1] >= -1e-6).all(1)]              # the starboard side: cuts are drawn as half-breadths
    lines = {}
    draw = {v: [] for v in D.d["views"]}
    # half-breadth plan: waterlines
    for name, zpx in D.d["waterlines_z_px"].items():
        cuts = chain(plane_cut(V, T, 2, zpx / D.ppf_y * FT))
        if not cuts:
            lines[f"wl_{name}"] = None
            continue
        c = cuts[0]                                  # chain order: one line from the stern round to the stem
        p = D.hb_plan(c)
        lines[f"wl_{name}"] = D.score(f"wl_{name}", "half_breadth", p)
        draw["half_breadth"].append((f"wl {name}", p))
    # body plan: stations
    for st, xpx in D.d["stations_px"].items():
        xm = (xpx - D.mid) / D.ppf * FT
        cuts = chain(plane_cut(V, T, 0, xm))
        if not cuts:
            continue
        c = cuts[0]
        left = int(st) >= 5
        p = D.body(c, left)
        lines[f"st_{st}"] = D.score(f"st_{st}", "body", p)
        draw["body"].append((f"st {st}", p))
    # sheer plan: buttocks
    for b in D.d["buttocks_px"]:
        cuts = chain(plane_cut(V, T, 1, b / D.ppf_y * FT))
        for k, c in enumerate(cuts[:3]):                 # below water, and the topsides' crossings at the ends
            if len(c) < 10:
                continue
            p = D.sheer(c)
            # scored below A only (the drawing's buttocks stop at the load waterline aft) and where the drawing has them
            keep = c[:, 2] < 0
            if "buttocks_undrawn_x_px" in D.d:
                lo, hi = D.d["buttocks_undrawn_x_px"]
                x = D.x_px(c[:, 0])
                keep &= (x < lo) | (x > hi)
            lines[f"buttock_{b}_{k}"] = D.score(f"buttock_{b}_{k}", "sheer", p, keep=keep)
            draw["sheer"].append((f"bt {b}", p))
    # sheer plan: the profile outline (the hull's and backbone's silhouette edges in side view)
    prof = profile_outline(objs, D)["outline"]
    lines["profile_outline"] = D.score_points("profile_outline", "sheer", prof)
    outline_pts = prof
    # overlays
    for view, items in draw.items():
        x0, y0, x1, y1 = D.d["views"][view]["crop"]
        im = D.img.crop((x0, y0, x1, y1)).convert("RGB")
        im = Image.eval(im, lambda v: int(v * 0.6))
        z = D.d["views"][view].get("zoom", 2)
        im = im.resize((im.size[0] * z, im.size[1] * z), Image.LANCZOS)
        dr = ImageDraw.Draw(im)
        cols = [(255, 60, 60), (255, 170, 0), (255, 255, 0), (0, 255, 0), (0, 220, 255), (90, 120, 255), (255, 0, 255), (255, 140, 140), (160, 255, 160)]
        for k, (label, p) in enumerate(items):
            q = [((a - x0) * z, (b - y0) * z) for a, b in p]
            dr.line(q, fill=cols[k % len(cols)], width=1)
        if view == "sheer":
            for a, b in outline_pts:
                dr.point(((a - x0) * z, (b - y0) * z), fill=(0, 255, 255))
        im.save(os.path.join(out, f"overlay_{view}.png"))
    every = np.concatenate([D.all_d[k] for k, v in lines.items() if v])
    res = {"lines": lines,
           "all": {"median_px": round(float(np.median(every)), 2), "on_line": round(float((every <= 2.0).mean()), 3),
                   "samples": int(len(every))}}
    json.dump(res, open(os.path.join(out, "lines.json"), "w"), indent=1)
    with open(os.path.join(out, "lines.md"), "w") as f:
        f.write("| Line | Median (px) | 90% (px) | On the line (within 2 px) | Length (ft) |\n| --- | --- | --- | --- | --- |\n")
        for k, v in lines.items():
            f.write(f"| {k} | " + (" | ".join(str(v[c]) for c in ("median_px", "p90_px", "on_line", "length_ft")) if v else "missing | | |") + " |\n")
        f.write(f"\nAll lines: median {res['all']['median_px']} px, {res['all']['on_line']:.1%} of the {res['all']['samples']} samples within 2 px "
                f"({D.ppf} px = 1 ft across the sheet, {D.ppf_y} down it).\n")
    print(f"lines check: median {res['all']['median_px']} px, on the line {res['all']['on_line']:.1%}")
    for k, v in lines.items():
        print(f"  {k:18s}", v and f"median {v['median_px']:5.2f}  p90 {v['p90_px']:5.2f}  on {v['on_line']:.2f}")
    return res


def profile_outline(objs, D):
    """The side view's outline: every object's triangles filled into a mask in the sheer plan's pixels, then the mask's
    edge (keel bottom, stem and sternpost faces, sheer, stern face) as points in scan pixels."""
    x0, y0, x1, y1 = D.d["views"]["sheer"]["crop"]
    sub = 2                                            # fill at half-pixel resolution
    mask = Image.new("L", ((x1 - x0) * sub, (y1 - y0) * sub), 0)
    dr = ImageDraw.Draw(mask)
    for name, (V, T) in objs.items():
        P = D.sheer(V) if len(V) else None
        for t in T:
            q = [((P[i, 0] - x0) * sub, (P[i, 1] - y0) * sub) for i in t]
            dr.polygon(q, fill=255)
    m = np.asarray(mask) > 0
    # pinholes where two objects' edges meet a fraction of a pixel apart are the fill's rounding, not gaps in the hull:
    # close enclosed holes under 2 scan px, keep bigger ones (they would be real gaps)
    holes, n = label(~m)
    border = set(np.unique(np.concatenate([holes[0], holes[-1], holes[:, 0], holes[:, -1]]))) | {0}
    sizes = np.bincount(holes.ravel(), minlength=n + 1)
    small = np.array([k not in border and sizes[k] <= 2 * sub * sub for k in range(n + 1)])
    m = m | small[holes]
    edge = m & ~(np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1))
    iy, ix = np.nonzero(edge)
    pts = np.stack([ix / sub + x0, iy / sub + y0], 1)
    return {"outline": pts}


if __name__ == "__main__":
    main(*sys.argv[1:5])
