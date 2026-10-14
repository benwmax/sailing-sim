"""Gulf front pack: the Galveston Island Gulf shore south of the bay grid, from the GalvestonGulf G2 tiles and piers run.
Run after `piers/run.sh GalvestonGulf`. numpy + Pillow only (like the piers scripts).

Writes <G2>/GalvestonBay/gulf-front/ (or GULF_DEST):
  landmarks.geojson        Seawall end to end, both entrance jetties to their charted heads, named Gulf piers
  gulf_piers.geojson       over-water structures standing in the open Gulf (piers, platforms, the Pleasure Pier deck)
  groins.geojson           rock groins and other narrow structures sticking out into the Gulf (lidar)
  charted_structures.geojson  NOAA ENC piers and groins on the Gulf front (cross-check; catches the low ones)
  beach_profiles.geojson   one cross-shore profile every 50 m along the Gulf beach: width, slopes, berm, dune, what backs it
  gulf_water10.png         10 m mask of open Gulf water (white) used to tell the Gulf side from the bay side
Usage: build.py [chart.json] [navaids json]   (defaults: $SIM_REPO/Content/TerrainData/GalvestonBay.chart.json and .json)
"""
import sys, os, json, math, glob, numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), "piers"))
from geo import ll2utm, utm2ll, ll2local, local2ll, convergence_deg
from stage1 import dilate, erode, G2

REG = "GalvestonGulf"; D = f"{G2}/{REG}"
DEST = os.environ.get("GULF_DEST", f"{G2}/GalvestonBay/gulf-front"); os.makedirs(DEST, exist_ok=True)
SIM = os.environ.get("SIM_REPO", "")
CHART = sys.argv[1] if len(sys.argv) > 1 else f"{SIM}/Content/TerrainData/GalvestonBay.chart.json"
SIMJ = sys.argv[2] if len(sys.argv) > 2 else f"{SIM}/Content/TerrainData/GalvestonBay.json"
BAY_SOUTH = -27600.0                       # sim_north of the bay grid's south edge (29.295 N); north of it the bay copy wins
SIMOFF = 0.094
CONV = convergence_deg(-94.85, 29.25)       # true az = grid az + CONV
GULF_AZ = 136.0                             # the island's Gulf beach faces about 136 deg true
TILES = {t["name"]: t for t in json.load(open(f"{D}/tiles.json"))["tiles"]}
r2 = lambda v: None if v is None or not np.isfinite(v) else round(float(v), 2)

def fc(name, feats):
    return {"type": "FeatureCollection", "name": name, "features": feats}

def save(name, feats):
    json.dump(fc(name, feats), open(f"{DEST}/{name}.geojson", "w"), separators=(",", ":"))
    print(name, len(feats))

def sim_xy(lon, lat):
    e, n = ll2local(lon, lat); return round(float(n), 2), round(float(e), 2)

def ring_of(g):
    return np.array(g["coordinates"][0] if g["type"] == "Polygon" else g["coordinates"][0][0])

# ------------------------------------------------------------------ rasters (1 m dem / cover by UTM point)
_c = {}
def arr(kind, E, N):
    k = (kind, int(E // 1000), int(N // 1000))
    if k not in _c:
        p = f"{D}/{kind}/15_{k[1]:04d}_{k[2]:04d}.tif"
        if not os.path.exists(p): _c[k] = None
        else:
            a = np.array(Image.open(p))
            if kind != "cover": a = a.astype(np.float32); a[a < -9000] = np.nan
            _c[k] = a
    return _c[k]

def zat(E, N, kind="dem"):
    a = arr(kind, E, N)
    if a is None: return np.nan
    return a[999 - int(N % 1000), int(E % 1000)]

def cov(E, N):
    a = arr("cover", E, N)
    if a is None: return 255
    return int(a[1999 - int((N % 1000) * 2), int((E % 1000) * 2)])

def wl_at(E, N):
    t = TILES.get(f"15_{int(E // 1000):04d}_{int(N // 1000):04d}")
    return t["water_level_navd88"] if t else -0.5

# ------------------------------------------------------------------ open-Gulf water mask at 10 m (UTM)
es = [t["e_min"] for t in TILES.values()]; ns = [t["n_min"] for t in TILES.values()]
E0, E1, N0, N1 = min(es), max(es) + 1000, min(ns), max(ns) + 1000
H, W = (N1 - N0) // 10, (E1 - E0) // 10
water = np.ones((H, W), bool); known = np.zeros((H, W), bool)
for t in TILES.values():
    a = arr("dem", t["e_min"] + 1, t["n_min"] + 1)
    if a is None: continue
    a10 = a.reshape(100, 10, 100, 10)
    wet = np.nanmean(np.where(np.isnan(a10), 1.0, a10 <= t["water_level_navd88"] + 0.15), axis=(1, 3)) >= 0.5
    ok = ~np.all(np.isnan(a10), axis=(1, 3))
    r0 = (N1 - t["n_min"] - 1000) // 10; c0 = (t["e_min"] - E0) // 10
    water[r0:r0 + 100, c0:c0 + 100] = np.where(ok, wet, True); known[r0:r0 + 100, c0:c0 + 100] = ok
# a water cell is open Gulf when a 3 km ray toward the beach's facing direction never meets land (off-grid counts as sea)
# nodata outside the 1 km band is open sea only when it connects to the grid edge without crossing land; the island's
# interior (more than 1 km from both shores) is a nodata hole ringed by band land, so it stays land
unk = ~known; sea = np.zeros((H, W), bool); sea[0, :] = unk[0, :]; sea[-1, :] = unk[-1, :]; sea[:, 0] = unk[:, 0]; sea[:, -1] = unk[:, -1]
for _ in range(2000):      # geodesic growth in 100 m steps (land rings are 1 km or more thick, so nothing leaks)
    nxt = dilate(sea, 21) & unk
    if (nxt == sea).all(): break
    sea = nxt
water = np.where(known, water, sea)
ga = math.radians(GULF_AZ - CONV); dE, dN = math.sin(ga), math.cos(ga)
# open Gulf = the water body (lidar water plus open-sea nodata) connected to a seed off East Beach. Inside this grid the
# Gulf touches no bay water: the island crosses the south edge and the entrance channel lies north of the top edge.
sE_, sN_ = ll2utm(*local2ll(26180.0, -32620.0))           # GalvestonGulf seed_xy (north, east) in common.py
gulf = np.zeros((H, W), bool); gulf[int((N1 - sN_) // 10), int((sE_ - E0) // 10)] = True
for _ in range(3000):      # geodesic growth in 50 m steps; land between the Gulf and any canal is wider than that
    nxt = dilate(gulf, 11) & water
    if (nxt == gulf).all(): break
    gulf = nxt
Image.fromarray((gulf * 255).astype(np.uint8)).save(f"{DEST}/gulf_water10.png", optimize=True)
gulf_near = dilate(gulf, 7)                   # within about 30 m of open Gulf
gulf_band = dilate(gulf, 41)                  # within about 200 m

def in_mask(m, E, N):
    r, c = int((N1 - N) // 10), int((E - E0) // 10)
    return 0 <= r < H and 0 <= c < W and bool(m[r, c])

# ------------------------------------------------------------------ Gulf piers and groins (from the piers run)
P = f"{D}/piers"
OW = json.load(open(f"{P}/overwater_structures.geojson"))["features"]
NS = json.load(open(f"{P}/narrow_structures.geojson"))["features"]
NC = {f["properties"]["id"]: f for f in json.load(open(f"{P}/narrow_structures_centrelines.geojson"))["features"]}
NAMED = [("Galveston Island Historic Pleasure Pier", -94.7897, 29.2861, 250),     # 25th St; charted pier (NOAA ENC US5TXTD*)
         ("61st Street Fishing Pier", -94.8251, 29.2649, 250),
         ("Galveston Fishing Pier (90th St)", -94.8525, 29.2497, 300)]

def gulf_side(f, mask):
    r = ring_of(f["geometry"]); E, N = ll2utm(r[:, 0], r[:, 1])
    return np.mean([in_mask(mask, e, n) for e, n in zip(E, N)]) >= 0.5

GULF_DECK_MIN = 1.5
n_surf = 0
piers = []
for f in OW:
    p = f["properties"]
    if p.get("kind") in ("vessel_large", "boats_in_slips") or p.get("area_m2", 0) < 20: continue
    # Gulf piers stand 4 to 10 m above the water on piles; the many 0.4 m "decks" off the beach are breaking waves on the bars
    if p.get("deck_above_water_m", 0) < GULF_DECK_MIN: n_surf += 1; continue
    r = ring_of(f["geometry"]); clon, clat = r[:, 0].mean(), r[:, 1].mean()
    if sim_xy(clon, clat)[0] >= BAY_SOUTH: continue
    if not gulf_side(f, gulf_near): continue
    q = dict(p); q["setting"] = "gulf"
    if p["kind"] == "bridge" and p.get("attached_to_shore") and abs((p["long_axis_dir_deg"] - GULF_AZ + 90) % 180 - 90) <= 30:
        q["kind"] = "pier"; q["kind_note"] = "high deck (classed bridge by the bay rules): a Gulf pier standing on tall piles"
    for nm, lo, la, rad in NAMED:
        E, N = ll2utm(lo, la); cE, cN = ll2utm(clon, clat)
        if math.hypot(cE - E, cN - N) <= rad and p.get("length_m", 0) >= 50 and q.get("kind") in ("pier", "platform_or_wharf", "covered_slip_or_building", "dock_complex"):
            q["name"] = nm
    piers.append({"type": "Feature", "geometry": f["geometry"], "properties": q})
# one named pier per name: keep the longest candidate
for nm, *_ in NAMED:
    c = [f for f in piers if f["properties"].get("name") == nm]
    for f in sorted(c, key=lambda f: -f["properties"]["length_m"])[1:]: f["properties"]["name"] = None
save("gulf_piers", piers)

groins = []
for f in NS:
    p = f["properties"]
    r = ring_of(f["geometry"]); clon, clat = r[:, 0].mean(), r[:, 1].mean()
    if sim_xy(clon, clat)[0] >= BAY_SOUTH or p["kind"] not in ("groin", "jetty", "breakwater"): continue
    if not gulf_side(f, gulf_band): continue
    q = dict(p); q["setting"] = "gulf"
    cl = NC.get(p["id"])
    groins.append({"type": "Feature", "geometry": cl["geometry"] if cl else f["geometry"], "properties": q})
save("groins", groins)

# charted structures on the Gulf front (NOAA ENC shoreline constructions, from the sim's Gulf passage chart): a cross-check
# and a fill-in for the low ones the lidar misses (groins awash, low walkways)
GCH = f"{SIM}/Content/TerrainData/GulfPassage.chart.json"; GPJ = f"{SIM}/Content/TerrainData/GulfPassage.json"
charted = []
if os.path.exists(GCH) and os.path.exists(GPJ):
    pj = json.load(open(GPJ))["projection"]
    lat0 = float(pj.split("+lat_0=")[1].split()[0]); lon0 = float(pj.split("+lon_0=")[1].split()[0])
    # the Gulf passage frame is the same tmerc with another origin: go through lon/lat with the bay frame's formulas
    from geo import _fwd, _inv
    Y0g = float(_fwd(lon0, lat0, lon0)[1])
    for d in json.load(open(GCH))["docks"]:
        q = np.array(d[1:]).reshape(-1, 2)
        lon, lat = _inv(q[:, 1], q[:, 0] + Y0g, lon0)
        E, N = ll2utm(lon, lat)
        if not any(in_mask(gulf_band, e, n) for e, n in zip(E, N)): continue
        if sim_xy(lon.mean(), lat.mean())[0] >= BAY_SOUTH: continue
        L = float(np.hypot(np.diff(E), np.diff(N)).sum()); closed = bool(np.hypot(E[0] - E[-1], N[0] - N[-1]) < 1)
        sn, se = sim_xy(lon.mean(), lat.mean())
        geom = {"type": "Polygon", "coordinates": [[[round(float(a), 7), round(float(b), 7)] for a, b in zip(lon, lat)]]} if closed and len(lon) >= 4 else \
               {"type": "LineString", "coordinates": [[round(float(a), 7), round(float(b), 7)] for a, b in zip(lon, lat)]}
        charted.append({"type": "Feature", "geometry": geom, "properties": dict(kind="groin_or_breakwater" if d[0] == "breakwater" else "pier",
                        chart_kind=d[0], outline_length_m=round(L, 1), sim_north=sn, sim_east=se, source="NOAA ENC via Content/TerrainData/GulfPassage.chart.json")})
save("charted_structures", charted)

# ------------------------------------------------------------------ beach profiles every 50 m along the Gulf shore
# shoreline cells: land next to open Gulf; order them along the beach axis (046 deg true) and take one station per 50 m
land = known & ~water
shore = land & dilate(gulf, 3)
rr, cc = np.nonzero(shore)
SE_ = E0 + (cc + 0.5) * 10; SN_ = N1 - (rr + 0.5) * 10
aa = math.radians(GULF_AZ - 90 - CONV); ux, uy = math.sin(aa), math.cos(aa)        # along-shore unit (toward 046 true)
nx, ny = dE, dN                                                                   # seaward unit
along = SE_ * ux + SN_ * uy; cross = SE_ * nx + SN_ * ny
SW = [f for f in json.load(open(f"{P}/seawall.geojson"))["features"]
      if sim_xy(*np.array(f["geometry"]["coordinates"]).mean(0))[0] < BAY_SOUTH]      # seam runs: the bay copy wins
BAYSW = f"{G2}/GalvestonBay/piers/seawall.geojson"
if os.path.exists(BAYSW): SW += json.load(open(BAYSW))["features"]
swpts = np.vstack([np.column_stack(ll2utm(*np.array(s["geometry"]["coordinates"]).T)) for s in SW]) if SW else np.zeros((0, 2))
if len(swpts):     # densify the seawall lines to 2 m for the crossing test
    dens = []
    for s in SW:
        c = np.column_stack(ll2utm(*np.array(s["geometry"]["coordinates"]).T))
        for a, b in zip(c[:-1], c[1:]):
            k = max(2, int(np.hypot(*(b - a)) / 2)); dens.append(a + (b - a) * np.linspace(0, 1, k)[:, None])
    swpts = np.vstack(dens)
SAND, NOTBEACH = {4}, {1, 2, 5, 6, 7, 8, 9}
SAND_Z_MAX = 2.0     # NAIP-bright dry sand often falls in the concrete class; below +2.0 m NAVD88 it is still beach
NAMES = {0: "water", 1: "grass", 2: "scrub", 3: "bare_clay", 4: "sand", 5: "riprap_rock", 6: "concrete", 7: "asphalt", 8: "tree_canopy", 9: "building", 255: "none"}
prof = []
bins = np.floor(along / 50).astype(int)
for b in np.unique(bins):
    sel = bins == b
    if sel.sum() < 2: continue
    k = np.nonzero(sel)[0]; k = k[np.argmax(cross[k])]           # most seaward shoreline cell in the bin
    sE, sN = SE_[k], SN_[k]
    # local shore direction from the shoreline cells within 150 m along the axis
    near = np.abs(along - along[k]) <= 150
    if near.sum() >= 6:
        X = np.column_stack([SE_[near], SN_[near]]); Xc = X - X.mean(0); _, _, vt = np.linalg.svd(Xc, full_matrices=False)
        t = vt[0] if vt[0] @ [ux, uy] > 0 else -vt[0]
        n_ = np.array([t[1], -t[0]])                                   # seaward = right of the along-shore direction
        if n_ @ [nx, ny] < 0.5: n_ = np.array([nx, ny])
    else:
        n_ = np.array([nx, ny])
    s = np.arange(-120, 601, 1.0)
    PE, PN = sE - n_[0] * s, sN - n_[1] * s                         # s > 0 runs landward
    z = np.array([zat(e, n) for e, n in zip(PE, PN)]); cv = np.array([cov(e, n) for e, n in zip(PE, PN)])
    wl = wl_at(sE, sN)
    dry = np.nonzero(np.nan_to_num(z, nan=-99) > wl + 0.15)[0]
    if not len(dry): continue
    i_wl = dry[0]
    if s[i_wl] > 80: continue
    # back of the beach: 3 m in a row of non-beach cover, a seawall crossing, or a 1.5 m step within 4 m
    i_bk = None; backed = None
    for i in range(i_wl + 1, len(s) - 4):
        if len(swpts) and np.min(np.hypot(swpts[:, 0] - PE[i], swpts[:, 1] - PN[i])) <= 1.5:
            i_bk = i; backed = "seawall"; break
        if all(cv[i + j] in NOTBEACH and not (cv[i + j] == 6 and np.nan_to_num(z[i + j], nan=9) <= SAND_Z_MAX) for j in range(3)):
            i_bk = i; break
        if np.isfinite(z[i + 4]) and np.isfinite(z[i]) and z[i + 4] - z[i] >= 1.5 and z[i + 4] >= 3.0:
            i_bk = i; backed = "wall_or_steep_bank"; break
    if i_bk is None: continue
    if backed in (None, "wall_or_steep_bank") and len(swpts):
        q_ = np.column_stack([PE[i_bk:i_bk + 31], PN[i_bk:i_bk + 31]])
        if min(np.min(np.hypot(swpts[:, 0] - e, swpts[:, 1] - n)) for e, n in q_) <= 3: backed = "seawall"
    if backed == "wall_or_steep_bank": backed = "scarp_or_bank"     # a steep dune face, bulkhead or bank away from the Seawall
    bw = s[i_bk] - s[i_wl]
    fs = slice(i_wl, min(i_wl + 25, i_bk) + 1)
    ok = np.isfinite(z[fs])
    slope = float(np.polyfit(s[fs][ok], z[fs][ok], 1)[0]) if ok.sum() >= 5 else np.nan
    berm = float(np.nanmedian(z[i_wl + (i_bk - i_wl) // 2:i_bk + 1])) if i_bk > i_wl + 2 else float(z[i_wl])
    # what backs the beach: a dune (rises 1 m over the berm before any building or pavement), else the main cover behind
    j1 = i_bk
    while j1 < min(len(s) - 1, i_bk + 150) and cv[j1] not in (7, 9) and not (cv[j1] == 6 and np.nan_to_num(z[j1], nan=0) > 3.5): j1 += 1
    seg = z[i_bk:j1 + 1]
    dune_z = dune_s = None
    w15 = cv[i_bk:i_bk + 15]
    if backed is None and 9 not in w15 and 7 not in w15 and len(seg) > 5 and np.isfinite(seg).any() and np.nanmax(seg) - berm >= 1.0:
        jm = i_bk + int(np.nanargmax(seg)); dune_z = float(z[jm]); dune_s = float(s[jm] - s[i_wl]); backed = "dune"
    if backed is None:
        w = cv[i_bk:i_bk + 30]; w = w[w < 255]
        m = int(np.bincount(w, minlength=10).argmax()) if len(w) else 255
        if 9 in w15: backed = "buildings"
        elif 7 in w15: backed = "road_or_parking"
        else: backed = {1: "vegetation", 2: "vegetation", 8: "trees", 6: "pavement", 7: "road_or_parking", 9: "buildings", 5: "riprap", 3: "bare_ground", 4: "sand"}.get(m, "other")
    behind = int(np.bincount(cv[i_bk:min(len(s), i_bk + 60)][cv[i_bk:min(len(s), i_bk + 60)] < 255], minlength=10).argmax()) if np.any(cv[i_bk:i_bk + 60] < 255) else 255
    sand_frac = float(np.mean([c in SAND for c in cv[i_wl:i_bk + 1]]))
    end = j1 if dune_z is not None else i_bk
    lon, lat = utm2ll(np.array([PE[i_wl], PE[end]]), np.array([PN[i_wl], PN[end]]))
    sn, se = sim_xy(lon[0], lat[0])
    if sn >= BAY_SOUTH: continue
    faces = (math.degrees(math.atan2(n_[0], n_[1])) + CONV) % 360
    prof.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[round(float(lon[0]), 7), round(float(lat[0]), 7)], [round(float(lon[1]), 7), round(float(lat[1]), 7)]]},
                 "properties": dict(id=f"P{len(prof):04d}", beach_width_m=round(float(bw), 1), faces_deg=round(faces, 1), water_z_navd88=wl,
                                    foreshore_slope=r2(slope), berm_z_navd88=r2(berm), back_z_navd88=r2(z[i_bk]), backed_by=backed,
                                    dune_crest_z_navd88=r2(dune_z), dune_dist_m=r2(dune_s), behind=NAMES.get(behind, "other"), sand_frac=round(sand_frac, 2),
                                    sim_north=sn, sim_east=se)})
save("beach_profiles", prof)

# ------------------------------------------------------------------ landmarks: Seawall end to end, jetties to their heads, named piers
lm = []
runs = SW
if runs:
    pts = np.vstack([np.column_stack(ll2utm(*np.array(s["geometry"]["coordinates"]).T)) for s in runs])
    o = np.argsort(pts @ [ux, uy]); pts = pts[o]
    keep = [0]
    for i in range(1, len(pts)):
        if np.hypot(*(pts[i] - pts[keep[-1]])) >= 5: keep.append(i)
    pts = pts[keep]; lon, lat = utm2ll(pts[:, 0], pts[:, 1])
    gaps = np.hypot(*np.diff(pts, axis=0).T)
    # real gaps are between runs (vertices inside one simplified run can be far apart)
    ends = []
    for r_ in runs:
        c_ = np.column_stack(ll2utm(*np.array(r_["geometry"]["coordinates"]).T)); pr = c_ @ [ux, uy]
        ends.append((pr.min(), pr.max(), c_[pr.argmin()], c_[pr.argmax()]))
    ends.sort(key=lambda e: e[0]); rgaps = []
    for a_, b_ in zip(ends[:-1], ends[1:]):
        g_ = b_[0] - a_[1]
        if g_ > 50:
            mlo, mla = utm2ll(*((a_[3] + b_[2]) / 2)); rgaps.append(dict(length_m=round(float(g_), 1), at=[round(float(mlo), 5), round(float(mla), 5)]))
    L = float(gaps.sum()); cz = [s["properties"]["crest_z_navd88"] for s in runs]
    wts = [s["properties"]["length_m"] for s in runs]
    mlon, mlat = utm2ll(*pts.mean(0)); sn, se = sim_xy(mlon, mlat)
    lm.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[round(float(a), 7), round(float(b), 7)] for a, b in zip(lon, lat)]},
               "properties": dict(name="Galveston Seawall", kind="seawall", length_m=round(L, 1), runs=len(runs), lidar_seen_m=round(float(sum(r_["properties"]["length_m"] for r_ in runs)), 1), gaps=rgaps,
                                  crest_z_navd88=round(float(np.average(cz, weights=wts)), 2), sim_crest_z=round(float(np.average(cz, weights=wts)) + SIMOFF, 2),
                                  faces_deg=round(float(np.median([s["properties"]["faces_deg"] for s in runs])), 1),
                                  source="lidar step edge (2018), Gulf tiles plus the bay grid's north-east end; gaps (groins, piers, stairs breaking the step) are bridged with straight lines", sim_north=sn, sim_east=se)})

# jetties: the bay pack's traced lines, extended to the charted jetty-head lights on the NOAA ENC (the lidar band and
# the NAIP imagery both stop short of the heads)
BAYLM = f"{G2}/GalvestonBay/piers/landmarks.geojson"
if os.path.exists(BAYLM) and os.path.exists(SIMJ):
    nav = {n["name"]: n for n in json.load(open(SIMJ))["navaids"] if "Jetty Light" in (n.get("name") or "")}
    chart = json.load(open(CHART)) if os.path.exists(CHART) else {"docks": []}
    for f in json.load(open(BAYLM))["features"]:
        p = f["properties"]
        if p.get("kind") != "jetty": continue
        light = nav.get("Galveston North Jetty Light 6A" if "North" in p["name"] else "Galveston South Jetty Light 5A")
        c = np.array(f["geometry"]["coordinates"]); E, N = ll2utm(c[:, 0], c[:, 1]); X = np.column_stack([E, N])
        ax = X[-1] - X[max(0, len(X) - 8)]; ax /= np.linalg.norm(ax)
        ext = []
        if light:
            llon, llat = local2ll(light["y"], light["x"]); LE, LN = ll2utm(llon, llat)
            gap = (np.array([LE, LN]) - X[-1]) @ ax
            if gap > 20:
                # charted jetty line vertices between the traced end and the light, within 60 m of that chord
                cand = []
                for d in chart["docks"]:
                    q = np.array(d[1:]).reshape(-1, 2); dl = local2ll(q[:, 1], q[:, 0]); qE, qN = ll2utm(*dl)
                    for e, n in zip(qE, qN):
                        v = np.array([e, n]) - X[-1]; t = v @ ax; off = abs(v @ [-ax[1], ax[0]])
                        if 10 < t < gap - 10 and off < 60: cand.append((t, e, n))
                cand.sort()
                ext = [[e, n] for _, e, n in cand[::max(1, len(cand) // 20)]] + [[LE, LN]]
        full = np.vstack([X] + ([np.array(ext)] if ext else []))
        L = float(np.hypot(*np.diff(full, axis=0).T).sum()); lon, lat = utm2ll(full[:, 0], full[:, 1])
        q = dict(p); q.update(length_m=round(L, 1), traced_length_m=p["length_m"], charted_extension_m=round(L - p["length_m"], 1),
                              head_light=light["name"] if light else None,
                              head_light_height_m=(light.get("light") or {}).get("height") if light else None,
                              source=p["source"] + "; seaward end extended to the charted head light (NOAA ENC US5TXTED), no lidar there, crest assumed as traced")
        lm.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[round(float(a), 7), round(float(b), 7)] for a, b in zip(lon, lat)]}, "properties": q})
        if light:
            sn, se = round(light["x"], 2), round(light["y"], 2)
            lm.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(float(llon), 7), round(float(llat), 7)]},
                       "properties": dict(name=light["name"], kind="jetty_head_light", colour=light.get("colour"), light=light.get("light"),
                                          daymark=light.get("daymark"), sim_north=sn, sim_east=se, source="NOAA ENC " + light.get("cell", ""))})
for f in piers:
    if f["properties"].get("name"):
        q = f["properties"]
        lm.append({"type": "Feature", "geometry": f["geometry"], "properties": dict(name=q["name"], kind="pier", length_m=q["length_m"], width_m=q["width_m"],
                   deck_z_navd88=q["deck_z_navd88"], top_z_navd88=q["top_z_navd88"], sim_deck_z=q["sim_deck_z"], long_axis_dir_deg=q["long_axis_dir_deg"],
                   source="2018 lidar over hydro-flattened water", sim_north=q.get("sim_north"), sim_east=q.get("sim_east"))})
save("landmarks", lm)

summary = dict(gulf_piers=len(piers), dropped_as_surf=n_surf, named=[f["properties"]["name"] for f in piers if f["properties"].get("name")],
               groins=len(groins), charted_structures=len(charted), beach_profiles=len(prof),
               beach_width_m_median=r2(np.median([f["properties"]["beach_width_m"] for f in prof])) if prof else None,
               backed_by={k: sum(f["properties"]["backed_by"] == k for f in prof) for k in sorted({f["properties"]["backed_by"] for f in prof})},
               landmarks=[(f["properties"]["name"], f["properties"].get("length_m")) for f in lm])
json.dump(summary, open(f"{DEST}/gulf_summary.json", "w"), indent=1); print(json.dumps(summary, indent=1))
