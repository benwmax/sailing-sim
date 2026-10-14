"""Piers step 3: the Galveston Seawall from the 1 m bare-earth DEM. The wall shows as a long, straight-ish step where the
ground drops 2 m or more within a few metres from the boulevard (crest about +5 m NAVD88) to the beach, with the Gulf
close by. Usage: seawall.py <Region>   (writes <G2>/<Region>/piers/seawall.geojson; no output if the wall is outside)"""
import sys, os, json, numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from geo import ll2utm, utm2ll, ll2local, convergence_deg
from vec import components, group, centreline, dp, obb
from stage1 import erode, dilate, G2

reg = sys.argv[1]
BOX = (-94.90, 29.20, -94.74, 29.33)        # lon/lat box holding the seawall (west end near 103rd St to the east end)
CREST_MIN, TOE_MAX, REACH = 3.6, 2.2, 7     # m NAVD88, m NAVD88, m
T = {t["name"]: t for t in json.load(open(f"{G2}/{reg}/tiles.json"))["tiles"]}
E0, N0 = ll2utm(BOX[0], BOX[1]); E1, N1 = ll2utm(BOX[2], BOX[3])
names = [n for n, t in T.items() if E0 - 1000 <= t["e_min"] <= E1 and N0 - 1000 <= t["n_min"] <= N1]
print(len(names), "tiles in the seawall box")
xs, ys, crest = [], [], []
DEMS, COVS = {}, {}
def cov_at(E, N):
    k = f"15_{int(E // 1000):04d}_{int(N // 1000):04d}"
    if k not in COVS:
        pc = f"{G2}/{reg}/cover/{k}.tif"
        COVS[k] = np.array(Image.open(pc)) if os.path.exists(pc) else None
    a = COVS[k]
    if a is None: return 255
    return a[1999 - int((N % 1000) * 2), int((E % 1000) * 2)]
def zat(E, N):
    k = f"15_{int(E // 1000):04d}_{int(N // 1000):04d}"
    a = DEMS.get(k)
    if a is None: return np.nan
    return a[999 - int(N % 1000), int(E % 1000)]
for nm in names:
    t = T[nm]
    p = f"{G2}/{reg}/dem/{nm}.tif"
    if not os.path.exists(p): continue
    dem = np.array(Image.open(p)).astype(np.float32); dem[dem < -9000] = np.nan
    wl = t["water_level_navd88"]; DEMS[nm] = dem
    hi = np.nan_to_num(dem, nan=-99) >= CREST_MIN
    low = np.nan_to_num(dem, nan=99) <= TOE_MAX
    water = np.nan_to_num(dem, nan=99) < wl + 0.45
    edge = hi & dilate(low, 2 * REACH + 1) & dilate(water, 401)
    r, c = np.nonzero(edge)
    xs.append(t["e_min"] + c); ys.append(t["n_min"] + 999 - r)
    crest.append(dem[r, c])
if not xs or sum(len(a) for a in xs) == 0:
    print("no seawall cells in this region"); sys.exit(0)
x = np.concatenate(xs); y = np.concatenate(ys); z = np.concatenate(crest)
lab = components(x, y)
feats = []
CONV = convergence_deg(-94.82, 29.27)
for g in group(lab):
    if len(g) < 120: continue
    gx, gy = x[g] + 0.5, y[g] + 0.5
    cx, cy, gaz, L, W, ux, uy = obb(gx, gy)
    if L < 150 or L / max(W, 1) < 6: continue
    # which side is low? sample 15 to 40 m out on both sides of the centre, perpendicular to the run
    nx, ny = uy, -ux
    side = [np.nanmedian([zat(cx + sg * d * nx, cy + sg * d * ny) for d in range(15, 41, 5)]) for sg in (1, -1)]
    sg = 1 if side[0] < side[1] else -1
    faces = (np.degrees(np.arctan2(sg * nx, sg * ny)) + CONV) % 360
    high_side = max(side)
    sand = np.mean([cov_at(cx + sg * d * nx, cy + sg * d * ny) == 4 for d in range(15, 81, 5)])
    if not (95 <= faces <= 215) or not high_side >= 3.0 or sand < 0.3:   # and a sand beach in front     # the Gulf seawall faces south-east; harbour wharves and road fills face elsewhere
        print("skip run facing", round(faces), "sand", round(float(sand), 2), "land side z", round(float(high_side), 2), "at", [round(float(v), 4) for v in utm2ll(cx, cy)]); continue
    cl, wid = centreline(gx, gy, 20.0)
    cl = dp(cl, 1.0)
    lon, lat = utm2ll(cl[:, 0], cl[:, 1])
    clon, clat = utm2ll(cx, cy); se, sn = ll2local(clon, clat)
    feats.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[round(float(a), 7), round(float(b), 7)] for a, b in zip(lon, lat)]},
                  "properties": dict(id=f"S{len(feats):03d}", kind="seawall", name="Galveston Seawall", length_m=round(L, 1),
                                     crest_z_navd88=round(float(np.percentile(z[g], 90)), 2), sim_crest_z=round(float(np.percentile(z[g], 90)) + 0.094, 2),
                                     long_axis_dir_deg=round((gaz + CONV) % 180, 1), faces_deg=round(float(faces), 1), land_side_z_navd88=round(float(high_side), 2), beach_side_z_navd88=round(float(min(side)), 2), sim_north=round(float(sn), 2), sim_east=round(float(se), 2),
                                     note="line follows the top edge of the Gulf-facing step; the curved face drops to the beach on the Gulf side")})
os.makedirs(f"{G2}/{reg}/piers", exist_ok=True)
json.dump({"type": "FeatureCollection", "name": f"{reg}_seawall", "features": feats}, open(f"{G2}/{reg}/piers/seawall.geojson", "w"), separators=(",", ":"))
print(len(feats), "seawall runs", [f["properties"]["length_m"] for f in feats])
