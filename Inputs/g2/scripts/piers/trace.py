"""Piers step 4: trace the two Galveston entrance jetties end to end, past the edge of the G2 lidar band, in the NAIP
2022 imagery. Rock reads grey (red about equal to green); Gulf water reads green-blue (red 20 to 35 below green). From
the lidar-detected landward part, the tracer steps 5 m seaward, finds the grey ridge on a profile across the line and
follows it until 6 steps in a row find no rock. Heights come from the lidar where the line is inside the band.
Also writes landmarks.geojson: the named structures (jetties, Texas City Dike, Seawall) in one small file.
Usage: trace.py <Region>     (after stage2.py and seawall.py)"""
import sys, os, json, math, numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from geo import ll2utm, utm2ll, ll2local, convergence_deg
from stage1 import G2

reg = sys.argv[1]
D = f"{G2}/{reg}"; OUTD = f"{D}/piers"
CONV = convergence_deg(-94.75, 29.34)
_cache = {}

def tile_arr(kind, E, N):
    k = (kind, int(E // 1000), int(N // 1000))
    if k not in _cache:
        p = f"{D}/{kind}/15_{k[1]:04d}_{k[2]:04d}.tif"
        if not os.path.exists(p): _cache[k] = None
        else:
            im = Image.open(p)
            if kind == "ortho":
                ext = im.tag_v2.get(33922); sc = im.tag_v2.get(33550)
                _cache[k] = (np.array(im.convert("RGB")).astype(np.int16), ext[3], ext[4], sc[0])
            else:
                a = np.array(im).astype(np.float32); a[a < -9000] = np.nan; _cache[k] = a
    return _cache[k]

def rockness(E, N, mode="grey"):
    t = tile_arr("ortho", E, N)
    if t is None: return np.nan
    a, x0, y0, s = t
    r, c = int((y0 - N) / s), int((E - x0) / s)
    if not (0 <= r < a.shape[0] and 0 <= c < a.shape[1]): return np.nan
    w = a[max(r - 1, 0):r + 2, max(c - 1, 0):c + 2].reshape(-1, 3)
    return float(np.mean(w[:, 0] - w[:, 1])) if mode == "grey" else float(np.mean(w)) / 3

def zval(kind, E, N):
    a = tile_arr(kind, E, N)
    if a is None: return np.nan
    return a[999 - int(N % 1000), int(E % 1000)]

def trace(start, direction, max_len=12000, step=5.0, half=30, bridge_nan=0, mode="grey", thr=9):
    """start (E, N) on the jetty, direction unit (dx, dy) seaward. Returns the list of (E, N) points on the crest."""
    pts = [np.array(start, float)]; d = np.array(direction, float); miss = 0; nan_run = 0; good = 1
    nrm = np.array([-d[1], d[0]])
    off = np.arange(-half, half + 1, 1.0)
    while len(pts) * step < max_len:
        p = pts[-1] + d * step
        prof = np.array([rockness(*(p + o * nrm), mode) for o in off])
        if np.all(np.isnan(prof)):
            nan_run += 1                                        # no imagery: keep going straight for a while
            if nan_run * step > bridge_nan: break
            pts.append(p); continue
        nan_run = 0
        base = np.nanmedian(prof)
        sm = np.convolve(np.nan_to_num(prof, nan=base), np.ones(5) / 5, "same")
        k = int(np.argmax(sm - np.abs(off) * 0.15))            # prefer the ridge near the predicted line
        if sm[k] - base >= thr and (mode != "grey" or sm[k] >= -12):
            p = p + off[k] * nrm * 0.6; miss = 0                # move most of the way onto the ridge
            pts.append(p); good = len(pts)
            if len(pts) >= 12:                                  # re-estimate the heading from the last 50 m
                v = pts[-1] - pts[-11]; d = v / np.linalg.norm(v); nrm = np.array([-d[1], d[0]])
        else:
            miss += 1; pts.append(p)
            if miss >= 6: break
    return pts[:good]

def simplify(pts, tol=1.5):
    from vec import dp
    return dp(np.array(pts), tol)

S = json.load(open(f"{OUTD}/narrow_structures.geojson"))["features"]
A = json.load(open(f"{OUTD}/overwater_structures.geojson"))["features"]
ANCH = {a["name"]: a for a in json.load(open(f"{HERE}/anchors.json"))}
land = []
for name in ("Galveston North Jetty", "Galveston South Jetty"):
    an = ANCH[name]; aE, aN = ll2utm(an["lon"], an["lat"])
    # collect lidar pieces (narrow land, or decks over hydro-flattened water) that lie on this jetty's line
    cand = []
    for f in S + A:
        p = f["properties"]
        if p.get("length_m", 0) < 40: continue
        g = f["geometry"]; ring = np.array(g["coordinates"][0] if g["type"] == "Polygon" else g["coordinates"][0][0])
        E, N = ll2utm(ring[:, 0], ring[:, 1])
        dmin = float(np.min(np.hypot(E - aE, N - aN)))
        az = p["long_axis_dir_deg"]
        if dmin <= an["radius_m"] and 95 <= az <= 135:
            cand.append((p["length_m"], E, N, p["id"]))
    if not cand:
        print(name, "no lidar piece near the anchor"); continue
    cand.sort(key=lambda c: -c[0])
    _, E, N, pid = cand[0]
    # endpoints along the piece's axis; seaward = farther from the anchor
    X = np.stack([E, N], 1); c = X.mean(0); u, s, vt = np.linalg.svd(X - c); ax = vt[0]
    t = (X - c) @ ax; e1, e2 = c + ax * t.min(), c + ax * t.max()
    if np.hypot(*(e1 - [aE, aN])) > np.hypot(*(e2 - [aE, aN])): e1, e2 = e2, e1; ax = -ax
    # trace both ways: seaward to the head, landward to the beach
    sea = trace(e2 - ax * 20, ax)
    landw = trace(e1 + ax * 20, -ax, max_len=3000)
    # drop a hook at the seaward head: trailing points more than 15 m off the line through the rest
    sea = np.array(sea)
    if len(sea) > 20:
        k0 = len(sea) - 20; q = sea[:k0]; qc = q.mean(0); _, _, vt2 = np.linalg.svd(q - qc); n2 = np.array([-vt2[0][1], vt2[0][0]])
        offs = np.abs((sea - qc) @ n2); bad = np.nonzero(offs > 15)[0]
        if len(bad): sea = sea[:bad[0]]
    line = [*reversed(landw), *sea]
    line = simplify(line)
    L = float(np.sum(np.hypot(*np.diff(line, axis=0).T)))
    zs = []
    for P0, P1 in zip(line[:-1], line[1:]):
        for f in np.linspace(0, 1, max(2, int(np.hypot(*(P1 - P0)) / 5))):
            q = P0 + (P1 - P0) * f
            v = max([zval("dsm", q[0] + dx, q[1] + dy) for dx in (-3, 0, 3) for dy in (-3, 0, 3)] + [-99])
            zs.append(v if v > -99 and np.isfinite(v) else np.nan)
    zs = np.array(zs); ok = np.isfinite(zs)
    lon, lat = utm2ll(line[:, 0], line[:, 1])
    mE, mN = line.mean(0); mlon, mlat = utm2ll(mE, mN); se, sn = ll2local(mlon, mlat)
    v = line[-1] - line[0]; gaz = (math.degrees(math.atan2(v[0], v[1])) + 180) % 180
    land.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[round(float(a), 7), round(float(b), 7)] for a, b in zip(lon, lat)]},
                 "properties": dict(name=name, kind="jetty", length_m=round(L, 1), long_axis_dir_deg=round((gaz + CONV) % 180, 1),
                                    seed_piece=pid, lidar_coverage_frac=round(float(ok.mean()), 2),
                                    crest_z_navd88=round(float(np.nanpercentile(zs, 75)), 2) if ok.any() else None,
                                    crest_z_navd88_min=round(float(np.nanpercentile(zs, 10)), 2) if ok.any() else None,
                                    sim_crest_z=round(float(np.nanpercentile(zs, 75)) + 0.094, 2) if ok.any() else None,
                                    width_m_guess=12.0, source="lidar piece + NAIP 2022 trace (imagery past the lidar band)",
                                    sim_north=round(float(sn), 2), sim_east=round(float(se), 2))})
    print(name, "traced", round(L), "m from", pid, "lidar coverage", round(float(ok.mean()), 2))

# Texas City Dike: a straight road dike; the band and imagery have gaps along it, so fit one line through every lidar
# piece on its axis (narrow land or deck, within 12 deg of the matched piece, 40 m of its axis) and span them end to end.
seed = [f for f in S if f["properties"].get("name") == "Texas City Dike"]
if seed:
    sp = seed[0]["properties"]; saz = sp["long_axis_dir_deg"]
    g = seed[0]["geometry"]; r0 = np.array([v for r in (g["coordinates"] if g["type"] == "Polygon" else [r for q in g["coordinates"] for r in q]) for v in r])
    sE, sN = ll2utm(r0[:, 0], r0[:, 1]); c0 = np.array([sE.mean(), sN.mean()])
    a = math.radians(saz - CONV); ax = np.array([math.sin(a), math.cos(a)])
    pts, ids, crest = [], [], []
    for f in S + A:
        p = f["properties"]
        if abs((p["long_axis_dir_deg"] - saz + 90) % 180 - 90) > 12 or p.get("length_m", 0) < 15: continue
        g = f["geometry"]; ring = np.array([v for r in (g["coordinates"] if g["type"] == "Polygon" else [r for q in g["coordinates"] for r in q]) for v in r])
        E, N = ll2utm(ring[:, 0], ring[:, 1]); X = np.stack([E, N], 1) - c0
        along = X @ ax; off = X @ np.array([-ax[1], ax[0]])
        mc = X.mean(0) @ np.array([-ax[1], ax[0]])
        if abs(mc) <= 40 and np.abs(off).max() <= 150 and np.abs(along).max() <= 9000:
            pts.append(X); ids.append(p["id"]); crest.append(p.get("crest_z_navd88") or p.get("deck_z_navd88"))
    X = np.vstack(pts); c = X.mean(0); u, sv, vt = np.linalg.svd(X - c); d = vt[0]
    t = (X - c) @ d; e1, e2 = c0 + c + d * t.min(), c0 + c + d * t.max()
    covered = len(np.unique(np.floor(t / 10))) * 10
    # extend along the imagery: every 25 m along the axis (up to 9 km each way) look across +-40 m for the grey ridge
    # (road and rock: red about equal to green; turbid bay water is greener). Keep the run of hits with gaps under 600 m.
    m0 = c0 + c; nrm = np.array([-d[1], d[0]]); hits = []
    for tt in np.arange(-9000, 9001, 25.0):
        prof = np.array([rockness(*(m0 + d * tt + nrm * o)) for o in range(-40, 41, 2)])
        if np.all(np.isnan(prof)): continue
        k = int(np.nanargmax(prof)); base = np.nanmedian(prof)
        q = m0 + d * tt + nrm * (k * 2 - 40)
        side = [zval("dem", *(q + nrm * o)) for o in (-60, 60)]
        wet = any(np.isnan(z) or z < -0.1 for z in side)       # water (or outside the band) beside it: not a city street
        if prof[k] - base >= 6 and prof[k] >= -6 and wet:
            hits.append((tt, (k * 2 - 40)))
    hits = np.array(hits)
    t_lo, t_hi = t.min(), t.max()
    for sgn in (1, -1):
        cur = t_hi if sgn > 0 else t_lo
        for tt, _ in sorted(hits.tolist(), key=lambda h: sgn * h[0]):
            if sgn * (tt - cur) < 0: continue
            if sgn * (tt - cur) > 600: break
            cur = tt
        if sgn > 0: t_hi = cur
        else: t_lo = cur
    sel = hits[(hits[:, 0] >= t_lo) & (hits[:, 0] <= t_hi)] if len(hits) else hits
    if len(sel) > 10:      # refit the line through the lidar centre and the imagery hits
        Q = np.vstack([m0 + d * sel[:, :1] + nrm * sel[:, 1:2]])
        qc = Q.mean(0); _, _, vt3 = np.linalg.svd(Q - qc); d2 = vt3[0] * np.sign(vt3[0] @ d)
        tq = (Q - qc) @ d2; e1, e2 = qc + d2 * tq.min(), qc + d2 * tq.max(); d = d2
    else:
        e1, e2 = m0 + d * t_lo, m0 + d * t_hi
    line = np.array([e1, e2]); lon, lat = utm2ll(line[:, 0], line[:, 1])
    L = float(np.hypot(*(e2 - e1))); mlon, mlat = utm2ll(*(c0 + c)); se, sn = ll2local(mlon, mlat)
    gaz = (math.degrees(math.atan2(d[0], d[1])) + 180) % 180
    land.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[round(float(a), 7), round(float(b), 7)] for a, b in zip(lon, lat)]},
                 "properties": dict(name="Texas City Dike", kind="dike_or_causeway", length_m=round(L, 1), lidar_seen_length_m=covered,
                                    long_axis_dir_deg=round((gaz + CONV) % 180, 1), pieces=ids,
                                    crest_z_navd88=round(float(np.nanmedian([v for v in crest if v is not None])), 2),
                                    mean_width_m=sp["mean_width_m"], source="straight line fitted through the lidar pieces, ends extended along the NAIP 2022 imagery; gaps bridged",
                                    sim_north=round(float(sn), 2), sim_east=round(float(se), 2))})
    print("Texas City Dike", round(L), "m from", len(ids), "pieces; lidar saw", covered, "m")
p = f"{OUTD}/seawall.geojson"
if os.path.exists(p):
    land += json.load(open(p))["features"]
json.dump({"type": "FeatureCollection", "name": f"{reg}_landmarks", "features": land}, open(f"{OUTD}/landmarks.geojson", "w"), separators=(",", ":"))
print("landmarks", [(f["properties"]["name"], f["properties"].get("length_m")) for f in land])
