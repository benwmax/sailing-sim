"""Piers step 2: join the step-1 pixels across tiles, split moored boats from docks, classify and write GeoJSON.
Usage: stage2.py <Region>     (reads <WORK>/<Region>/s1/*.npz, writes <G2>/<Region>/piers/*.geojson)"""
import sys, os, glob, json, math, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from geo import utm2ll, ll2local, convergence_deg, ll2utm
from vec import components, group, to_mask, from_mask, rings, area, simplify_ring, obb, centreline, hull, dp
from stage1 import erode, dilate, G2, WORK

reg = sys.argv[1]
OUTD = f"{G2}/{reg}/piers"; os.makedirs(OUTD, exist_ok=True)
SIM_Z = 0.094                       # sim Z (m above MLLW) = NAVD88 + this
WATER_ABOVE_FLAT = 0.5              # lidar water returns sit ~0.5 m above the hydro-flattened DEM (measured at Kemah)
LAT_C, LON_C = 29.42, -94.89
CONV = convergence_deg(LON_C, LAT_C)  # true az = grid az + CONV

# ---------- load ----------
P = {k: [] for k in ("A_e", "A_n", "A_dem", "A_dsm", "A_cov", "A_hard", "A_adj", "B_e", "B_n", "B_dem", "B_dsm", "B_cov", "B_hard", "B_adj")}
for f in sorted(glob.glob(f"{WORK}/{reg}/s1/*.npz")):
    d = np.load(f)
    for k in P: P[k].append(d[k])
P = {k: np.concatenate(v) for k, v in P.items()}
print("pixels A", len(P["A_e"]), "B", len(P["B_e"]), flush=True)

r7 = lambda v: round(float(v), 7)
r2 = lambda v: None if v is None or not np.isfinite(v) else round(float(v), 2)

def ll_ring(r):
    lon, lat = utm2ll(r[:, 0], r[:, 1]); return [[r7(a), r7(b)] for a, b in zip(lon, lat)]

def polygon(x, y, tol=0.75, min_hole=12.0):
    M, e0, n0 = to_mask(x, y)
    R = rings(M, e0, n0)
    outer = [r for r in R if area(r) > 0]; holes = [r for r in R if area(r) < -min_hole]
    outer.sort(key=area, reverse=True)
    polys = []
    for o in outer:
        if area(o) < 2: continue
        polys.append([simplify_ring(o, tol)])
    for h in holes:  # holes go to the largest outer ring containing their first vertex
        px, py = h[0] + np.array([0.5, -0.5])
        for pg in polys:
            o = pg[0]; xs, ys = o[:, 0], o[:, 1]
            inside = np.sum(((ys[:-1] > py) != (ys[1:] > py)) & (px < (xs[1:] - xs[:-1]) * (py - ys[:-1]) / (ys[1:] - ys[:-1] + 1e-12) + xs[:-1])) % 2
            if inside: pg.append(simplify_ring(h, tol)); break
    if not polys: return None
    if len(polys) == 1: return {"type": "Polygon", "coordinates": [ll_ring(r) for r in polys[0]]}
    return {"type": "MultiPolygon", "coordinates": [[ll_ring(r) for r in pg] for pg in polys]}

def place(cx, cy):
    lon, lat = utm2ll(cx, cy); se, sn = ll2local(lon, lat)
    return float(lon), float(lat), round(float(sn), 2), round(float(se), 2)

def true_az(gaz): return round((gaz + CONV) % 180, 1)

# ---------- A: over-water structures and moored boats ----------
lab = components(P["A_e"], P["A_n"])
groups = group(lab)
print("A components", len(groups), flush=True)
boats, structs = [], []
struct_pix = []   # (indices) of structure pixels after boats are taken out
for idx in groups:
    if len(idx) < 4: continue
    x, y = P["A_e"][idx], P["A_n"][idx]
    if len(idx) <= 400:                         # small: a single boat, piling cluster or short pier
        struct_pix.append(idx) if len(idx) >= 4 else None
        continue
    # big complex: split thick parts (>= 3 m across) from thin parts (docks, finger piers, walkways)
    M, e0, n0 = to_mask(x, y)
    thick = dilate(erode(M, 3), 3) & M
    tx, ty = from_mask(thick, e0, n0)
    if len(tx):
        tl = components(tx, ty)
        key = {(a, b): i for i, (a, b) in enumerate(zip(x.tolist(), y.tolist()))}
        used = np.zeros(len(idx), bool)
        for g in group(tl):
            gx, gy = tx[g], ty[g]
            if len(g) <= 400:                    # boat-sized thick blob: hand it to the classifier below as its own piece
                ii = np.array([key[(a, b)] for a, b in zip(gx.tolist(), gy.tolist())])
                struct_pix.append(idx[ii]); used[ii] = True
        rest = idx[~used]
        if len(rest):
            rl = components(P["A_e"][rest], P["A_n"][rest])
            for g in group(rl):
                if len(g) >= 4: struct_pix.append(rest[g])
    else:
        struct_pix.append(idx)

print("A pieces", len(struct_pix), flush=True)
import collections; DROP = collections.Counter()

def roughness(idx, z):
    """median |dz| between 4-neighbours inside the piece: ~0.05 m on a deck, 0.3 m or more in a tree crown."""
    M, e0, n0 = to_mask(P["A_e"][idx], P["A_n"][idx])
    Z = np.full(M.shape, np.nan, np.float32); Z[P["A_n"][idx] - n0, P["A_e"][idx] - e0] = z
    d = np.concatenate([np.abs(np.diff(Z, axis=0)).ravel(), np.abs(np.diff(Z, axis=1)).ravel()])
    d = d[np.isfinite(d)]
    return float(np.median(d)) if len(d) else 0.0
for idx in struct_pix:
    x, y = P["A_e"][idx].astype(float) + 0.5, P["A_n"][idx].astype(float) + 0.5
    dem, dsm = P["A_dem"][idx], P["A_dsm"][idx]
    water_z = float(np.median(dem)) + WATER_ABOVE_FLAT
    fb = dsm - water_z
    cx, cy, gaz, L, Wd, ux, uy = obb(x, y)
    n = len(idx); fill = n / (L * Wd)
    attached = bool(P["A_adj"][idx].any()); adj_frac = float(P["A_adj"][idx].mean())
    rough = roughness(idx, dsm)
    p50, p90, p99 = np.percentile(fb, [50, 90, 99])
    rec = dict(n=n, x=x, y=y, idx=idx, cx=cx, cy=cy, gaz=gaz, L=L, W=Wd, fill=fill, att=attached, fb50=p50, fb90=p90, fb99=p99,
               deck=float(np.median(dsm)), adj=adj_frac, rough=rough, top=float(np.percentile(dsm, 99)), water_z=water_z)
    # moored or anchored boat: compact blob of boat size, not a long thin pier
    if 10 <= n <= 400 and 3.5 <= L <= 40 and Wd >= 1.8 and 1.6 <= L / Wd <= 6.5 and fill >= 0.35 and p50 >= 0.9 and rough <= 0.6:
        boats.append(rec); DROP["boat"] += 1
    elif adj_frac > 0.5 and n < 2000:
        DROP["bank_sliver"] += 1      # bank cells inside the flattened water, or overhanging trees
    elif rough > 0.35 and p50 > 1.5:
        DROP["canopy"] += 1           # tree canopy over the water
    elif n >= 8 and (L >= 6 or n >= 25):
        structs.append(rec)
    else:
        DROP["tiny"] += 1

def a_kind(s):
    if s["fb50"] >= 5.0 and s["L"] >= 40: return "bridge"
    if s["L"] >= 30 and s["W"] >= 8 and s["fill"] >= 0.75 and not s["att"] and s["fb50"] >= 1.5: return "vessel_large"
    if s["fb50"] >= 2.8 and s["W"] >= 4 and s["fill"] >= 0.5: return "covered_slip_or_building"
    if s["n"] >= 300 and s["fill"] < 0.45: return "dock_complex"
    if s["W"] >= 10 and s["fill"] >= 0.45:
        # rafted boats in a row of slips are lumpy; wharves and decks are smooth
        return "boats_in_slips" if s["rough"] >= 0.25 and s["fb50"] <= 4 else "platform_or_wharf"
    if s["L"] >= 12 and s["L"] / s["W"] >= 3: return "pier"
    return "deck_small"

feats_A = []
for i, s in enumerate(structs):
    kind = a_kind(s)
    g = polygon(P["A_e"][s["idx"]], P["A_n"][s["idx"]])
    if g is None: continue
    lon, lat, sn, se = place(s["cx"], s["cy"])
    s["kind"] = kind; s["lon"], s["lat"] = lon, lat
    feats_A.append({"type": "Feature", "geometry": g, "properties": dict(
        id=f"A{i:05d}", kind=kind, attached_to_shore=s["att"],
        length_m=round(s["L"], 1), width_m=round(s["W"], 1), long_axis_dir_deg=true_az(s["gaz"]), area_m2=s["n"], fill=round(s["fill"], 2),
        deck_z_navd88=r2(s["deck"]), top_z_navd88=r2(s["top"]), water_z_navd88=r2(s["water_z"]),
        deck_above_water_m=r2(s["fb50"]), surface_roughness_m=r2(s["rough"]), shore_contact_frac=r2(s["adj"]), sim_deck_z=r2(s["deck"] + SIM_Z), name=None,
        sim_north=sn, sim_east=se)})

feats_V = []
for i, b in enumerate(boats):
    lon, lat, sn, se = place(b["cx"], b["cy"])
    mast = b["fb99"] >= 6.0
    feats_V.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [r7(lon), r7(lat)]}, "properties": dict(
        id=f"V{i:05d}", length_m=round(b["L"], 1), beam_m=round(b["W"], 1), heading_deg=true_az(b["gaz"]),
        hull_top_above_water_m=r2(b["fb50"]), max_above_water_m=r2(b["fb99"]), mast_seen=bool(mast),
        alongside_shore=b["att"], sim_north=sn, sim_east=se)})
print("A structures", len(feats_A), "boats", len(feats_V), dict(DROP), flush=True)

# ---------- B: narrow raised land (jetties, dikes, groins, breakwaters, spoil ridges) ----------
lab = components(P["B_e"], P["B_n"])
cand = []
for idx in group(lab):
    if len(idx) < 40: continue
    x, y = P["B_e"][idx].astype(float) + 0.5, P["B_n"][idx].astype(float) + 0.5
    cx, cy, gaz, Lg, Wd, ux, uy = obb(x, y)
    if Lg < 25 or len(idx) / Lg > 45 or Lg / max(len(idx) / Lg, 1) < 3: continue
    cand.append(dict(idx=idx, cx=cx, cy=cy, gaz=gaz, L=Lg, ux=ux, uy=uy, hard=float(P["B_hard"][idx].mean())))
print("B elongated pieces", len(cand), flush=True)
# join collinear pieces of one structure (rock jetties dip under water in places): same direction within 6 deg,
# centre of one within 20 m of the other's axis, and an end gap of at most 250 m
par = list(range(len(cand)))
def fnd(i):
    while par[i] != i: par[i] = par[par[i]]; i = par[i]
    return i
cxy = np.array([[c["cx"], c["cy"]] for c in cand]) if cand else np.zeros((0, 2))
for i, a in enumerate(cand):
    if a["hard"] < 0.15: continue
    d = np.hypot(*(cxy - cxy[i]).T)
    for j in np.nonzero(d < a["L"] / 2 + 250 + 1500)[0]:
        if j <= i: continue
        b = cand[j]
        if b["hard"] < 0.15: continue
        dd = abs((a["gaz"] - b["gaz"] + 90) % 180 - 90)
        if dd > 6: continue
        vx, vy = b["cx"] - a["cx"], b["cy"] - a["cy"]
        off = abs(-vx * a["uy"] + vy * a["ux"]); along = abs(vx * a["ux"] + vy * a["uy"])
        if off <= max(20, 0.015 * along) and along - a["L"] / 2 - b["L"] / 2 <= 250:
            par[fnd(j)] = fnd(i)
merged = {}
for i in range(len(cand)): merged.setdefault(fnd(i), []).append(i)
feats_B = []; Brec = []
for members in merged.values():
    idx = np.concatenate([cand[i]["idx"] for i in members])
    x, y = P["B_e"][idx].astype(float) + 0.5, P["B_n"][idx].astype(float) + 0.5
    cx, cy, gaz, Lg, Wd, ux, uy = obb(x, y)
    n = len(idx); u = (x - cx) * ux + (y - cy) * uy
    covered = len(np.unique(np.floor(u).astype(int)))           # metres of the axis with land on them
    wmean = n / max(covered, 1)
    if Lg < 60 or wmean > 45 or Lg / max(wmean, 1) < 3.5: continue
    cov = P["B_cov"][idx]
    f_road = float(np.isin(cov, (6, 7)).mean()); f_bld = float((cov == 9).mean()); f_tree = float((cov == 8).mean())
    f_hard = float(P["B_hard"][idx].mean()); f_sand = float((cov == 4).mean())
    if f_bld > 0.08: continue
    dem, dsm = P["B_dem"][idx], P["B_dsm"][idx]
    crest = float(np.percentile(dem, 90)); top = float(np.percentile(dsm, 95))
    att = bool(P["B_adj"][idx].any())
    cl, wid = centreline(x, y, 10.0)
    path = float(np.sum(np.hypot(*np.diff(cl, axis=0).T))) if len(cl) > 1 else Lg
    straight = Lg / max(path, 1)
    if f_road >= 0.3 and wmean >= 18 and Lg >= 300: kind = "dike_or_causeway"
    elif f_hard >= 0.25: kind = ("jetty" if Lg >= 400 else "groin") if att else "breakwater"
    elif crest >= 0.8 and straight >= 0.85: kind = "spoil_or_ridge"
    else: continue                                   # low, soft, wiggly: marsh edge, not a structure
    cl = dp(cl, 1.0) if len(cl) > 2 else cl
    lon, lat, sn, se = place(cx, cy)
    clon, clat = utm2ll(cl[:, 0], cl[:, 1])
    g = polygon(P["B_e"][idx], P["B_n"][idx], tol=1.0, min_hole=50)
    if g is None: continue
    props = dict(kind=kind, attached_to_shore=att, length_m=round(Lg, 1), above_water_length_m=covered, pieces=len(members),
                 mean_width_m=round(wmean, 1), max_width_m=round(float(np.percentile(wid, 90)), 1),
                 long_axis_dir_deg=true_az(gaz), area_m2=n, crest_z_navd88=r2(crest), mean_z_navd88=r2(float(np.mean(dem))), top_z_navd88=r2(top),
                 sim_crest_z=r2(crest + SIM_Z), frac_rock_or_hard=round(f_hard, 2), frac_paved=round(f_road, 2), frac_sand=round(f_sand, 2), frac_tree=round(f_tree, 2),
                 straightness=round(straight, 2), name=None, sim_north=sn, sim_east=se)
    feats_B.append({"type": "Feature", "geometry": g, "properties": props,
                    "_centre": {"type": "LineString", "coordinates": [[r7(a), r7(b)] for a, b in zip(clon, clat)]}})
print("B features", len(feats_B), flush=True)

# ---------- names for well-known structures (nearest matching feature to an approximate anchor) ----------
ANCHORS = json.load(open(f"{HERE}/anchors.json"))
def dist_m(lon1, lat1, lon2, lat2):
    return math.hypot((lon1 - lon2) * 111320 * math.cos(math.radians(lat1)), (lat1 - lat2) * 110950)
for a in ANCHORS:
    if a["layer"] == "M": continue
    pool = feats_B if a["layer"] == "B" else feats_A
    best = None
    for f in pool:
        p = f["properties"]
        if a.get("kinds") and p["kind"] not in a["kinds"]: continue
        geom = f["geometry"]
        ring = geom["coordinates"][0] if geom["type"] == "Polygon" else geom["coordinates"][0][0]
        d = min(dist_m(a["lon"], a["lat"], c[0], c[1]) for c in ring)
        if d <= a["radius_m"]:
            score = (p.get("length_m", 0), -d)
            if best is None or score > best[0]: best = (score, f)
    if best:
        best[1]["properties"]["name"] = a["name"]; a["matched"] = best[1]["properties"].get("id") or True
        if "Jetty" in a["name"]: best[1]["properties"]["kind"] = "jetty"
    print("anchor", a["name"], "->", "matched" if best else "NOT FOUND", best[1]["properties"]["length_m"] if best else "")

# ---------- marinas: clusters of docks and boats ----------
DOCKY = ("dock_complex", "pier", "covered_slip_or_building", "deck_small", "boats_in_slips")
pts = [(s["cx"], s["cy"], "d", s["n"]) for s in structs if s.get("kind") in DOCKY] + \
      [(b["cx"], b["cy"], "b", 1) for b in boats]
pts = np.array([(p[0], p[1]) for p in pts])
isboat = np.array([0] * (len(pts) - len(boats)) + [1] * len(boats), bool)
cell = 30          # m: docks and boats closer than ~30 to 60 m join one marina
ce, cn = np.floor(pts[:, 0] / cell).astype(np.int64), np.floor(pts[:, 1] / cell).astype(np.int64)
uc, inv = np.unique(np.stack([ce, cn], 1), axis=0, return_inverse=True)
cl = components(uc[:, 0], uc[:, 1])[inv.ravel()]
feats_M = []
for g in group(cl):
    nb = int(isboat[g].sum()); nd = int((~isboat[g]).sum())
    if nb < 10: continue
    h = hull(np.round(pts[g, 0]).astype(int), np.round(pts[g, 1]).astype(int))
    if len(h) < 4: continue
    cx, cy = pts[g, 0].mean(), pts[g, 1].mean()
    lon, lat, sn, se = place(cx, cy)
    feats_M.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ll_ring(h)]}, "properties": dict(
        id=f"M{len(feats_M):04d}", boats_2018=nb, dock_pieces=nd, area_m2=round(abs(area(h))), name=None, sim_north=sn, sim_east=se)})
for a in ANCHORS:
    if a["layer"] != "M": continue
    best = None
    for f in feats_M:
        d = min(dist_m(a["lon"], a["lat"], c[0], c[1]) for c in f["geometry"]["coordinates"][0])
        if d <= a["radius_m"] and (best is None or f["properties"]["boats_2018"] > best[1]["properties"]["boats_2018"]):
            best = (d, f)
    if best:
        best[1]["properties"]["name"] = a["name"]
    print("anchor", a["name"], "->", best[1]["properties"]["id"] if best else "NOT FOUND")
print("marinas", len(feats_M), flush=True)

def write(name, feats, extra=None):
    fc = {"type": "FeatureCollection", "name": f"{reg}_{name}", "crs_note": "EPSG:4326 lon/lat; heights NAVD88 m (GEOID12B); sim Z = NAVD88 + 0.094 (m above MLLW)",
          "features": feats}
    with open(f"{OUTD}/{name}.geojson", "w") as f: json.dump(fc, f, separators=(",", ":"))

for i, f in enumerate(feats_B): f["properties"] = dict(id=f"B{i:05d}", **f["properties"])
centres = [{"type": "Feature", "geometry": f.pop("_centre"), "properties": {"id": f["properties"]["id"], "kind": f["properties"]["kind"], "name": f["properties"]["name"]}} for f in feats_B]
write("overwater_structures", feats_A); write("moored_boats_2018", feats_V); write("narrow_structures", feats_B)
write("narrow_structures_centrelines", centres); write("marinas", feats_M)
import collections
summary = dict(region=reg, overwater=dict(collections.Counter(f["properties"]["kind"] for f in feats_A)), boats=len(feats_V),
               narrow=dict(collections.Counter(f["properties"]["kind"] for f in feats_B)), marinas=len(feats_M),
               named=[(f["properties"]["name"], f["properties"]["id"]) for f in feats_A + feats_B if f["properties"]["name"]])
json.dump(summary, open(f"{OUTD}/summary.json", "w"), indent=1)
print(json.dumps(summary, indent=1))
