"""Step 4: merge tile records into GeoJSON (EPSG:4326), match the sim's buildings, write tile index and previews."""
import sys, os, json, glob, pickle, math, collections, numpy as np
from scipy.spatial import cKDTree
from common import *
reg = sys.argv[1]; R = REGIONS[reg]; U = f"EPSG:{R['utm_epsg']}"
SIMJSON = {"RayHubbard": f"{SIM_REPO}/Content/TerrainData/RayHubbard.json",
           "GalvestonBay": f"{SIM_REPO}/Content/TerrainData/GalvestonBay.json",
           "GalvestonGulf": f"{SIM_REPO}/Content/TerrainData/GalvestonBay.json"}[reg]
D = f"{OUT}/{reg}"
tiles, B, Tr, Sh = [], [], [], []
for p in sorted(glob.glob(f"{WORK}/{reg}/tiles/*.pkl")):
    d = pickle.load(open(p, "rb"))
    tiles.append(d["info"]); B += d["buildings"]; Tr += d["trees"]; Sh += d["shore"]
print(reg, len(tiles), "tiles", len(B), "buildings", len(Tr), "trees", len(Sh), "shore runs")
u2ll = tf(reg, U, "EPSG:4326"); u2l = tf(reg, U, "local")
# grid convergence: UTM grid north vs true north at the region centre (azimuths are converted to true north)
lon0, lat0 = [float(x) for x in R["local"].split("+lon_0=")[1].split()[0:1]] + [float(R["local"].split("+lat_0=")[1].split()[0])]
from pyproj import Proj
conv = Proj(U).get_factors(lon0, lat0).meridian_convergence  # degrees; true az = grid az + convergence
sim = json.load(open(SIMJSON))["buildings"]
kd = cKDTree(np.array([[s[0], s[1]] for s in sim]))
r6 = lambda x: round(float(x), 7)

def ll(coords):
    xs, ys = u2ll.transform([c[0] for c in coords], [c[1] for c in coords])
    return [[r6(x), r6(y)] for x, y in zip(xs, ys)]

feats = []; used = set()
for rec in B:
    b = rec["b"]; g = b["geom"]
    ring = list(g.exterior.coords)
    srcs = b["src"]
    source = "osm" if b["osm"] else ("microsoft" if "Microsoft ML Buildings" in srcs else ("esri" if any("Esri" in s for s in srcs) else "other"))
    dd, k = kd.query([b["sim_n"], b["sim_e"]])
    sim_index = int(k) if dd <= 6.0 else None
    if sim_index is not None: used.add(sim_index)
    hsrc = "lidar" if rec["lidar"] == "ok" else ("overture" if b["ov_height"] else "none")
    height = rec["height_m"] if hsrc == "lidar" else (round(b["ov_height"], 2) if b["ov_height"] else None)
    ridge = None if rec["ridge_az"] is None else round((rec["ridge_az"] + conv) % 180, 1)
    props = dict(id=b["id"], osm_id=b["osm"], source=source, footprint_sources=srcs, height_m=height, height_source=hsrc,
                 eave_m=rec["eave_m"], roof_type=rec["roof_type"], roof_detail=rec["roof_detail"], roof_fallback=rec.get("roof_fallback"),
                 ridge_dir_deg=ridge, pitch_deg=rec["pitch_deg"], fit_rms_m=rec["fit_rms"], roof_colour=rec["roof_colour"],
                 dist_to_water_m=round(b["dist10"], 0), detail="full" if b["dist10"] <= 400 else "reduced",
                 ground_z_navd88=rec["ground_z"], area_m2=rec["area_m2"], length_m=rec["length_m"], width_m=rec["width_m"],
                 long_axis_dir_deg=round((rec["long_axis_az"] + conv) % 180, 1), lidar_points=rec["lidar_points"],
                 sim_north=round(b["sim_n"], 2), sim_east=round(b["sim_e"], 2), sim_index=sim_index,
                 ov_class=b["ov_class"], ov_floors=b["ov_floors"], ov_roof_shape=b["ov_roof_shape"], roof_grid=rec.get("roof_grid"))
    feats.append(dict(type="Feature", geometry=dict(type="Polygon", coordinates=[ll(ring)]), properties=props))
json.dump(dict(type="FeatureCollection", name=f"{reg}_buildings", crs=dict(type="name", properties=dict(name="urn:ogc:def:crs:OGC:1.3:CRS84")), features=feats),
          open(f"{D}/buildings.geojson", "w"), separators=(",", ":"))
print("matched sim buildings", len(used), "of", len(sim))

tf_ = []
if Tr:
    lons, lats = u2ll.transform([t["e"] for t in Tr], [t["n"] for t in Tr]); le, ln = u2l.transform([t["e"] for t in Tr], [t["n"] for t in Tr])
    for t, lo, la, e_, n_ in zip(Tr, lons, lats, le, ln):
        p = {k: v for k, v in t.items() if k not in ("e", "n")}
        p["ground_z_navd88"] = p.pop("ground_z"); p["sim_north"] = round(n_, 2); p["sim_east"] = round(e_, 2)
        tf_.append(dict(type="Feature", geometry=dict(type="Point", coordinates=[r6(lo), r6(la)]), properties=p))
json.dump(dict(type="FeatureCollection", name=f"{reg}_trees", features=tf_), open(f"{D}/trees.geojson", "w"), separators=(",", ":"))

sf = []
for s in Sh:
    p = {k: v for k, v in s.items() if k != "utm"}
    p["water_z_navd88"] = p.pop("water_z"); p["crest_z_navd88"] = p.pop("crest_z")
    p["mean_rock_size_m"] = None
    sf.append(dict(type="Feature", geometry=dict(type="LineString", coordinates=ll(s["utm"])), properties=p))
json.dump(dict(type="FeatureCollection", name=f"{reg}_shore_armour", features=sf), open(f"{D}/shore_armour.geojson", "w"), separators=(",", ":"))

json.dump(dict(region=reg, crs=U, tile_size_m=1000, naming="<zone>_<E km>_<N km> of the tile's south-west corner",
               dem="dem/<tile>.tif float32 1 m NAVD88 m, nodata -9999", dsm="dsm/<tile>.tif float32 1 m NAVD88 m, nodata -9999 (land tiles only)",
               cover="cover/<tile>.tif uint8 0.5 m, nodata 255 (land tiles only)", ortho="ortho/<tile>.tif RGB uint8 0.6 m native NAIP grid (land tiles only)",
               sim_z_offset_m=(-435.5 * 0.3048006096 if reg == "RayHubbard" else 0.094), grid_convergence_deg=round(conv, 4), tiles=tiles),
          open(f"{D}/tiles.json", "w"), indent=1)
stats = dict(tiles=len(tiles), land_tiles=sum(t["has_land"] for t in tiles), buildings=len(B),
             full_detail=sum(f["properties"]["detail"] == "full" for f in feats),
             roof_type=dict(collections.Counter(str(f["properties"]["roof_type"]) for f in feats)),
             height_source=dict(collections.Counter(f["properties"]["height_source"] for f in feats)),
             sim_buildings_matched=len(used), sim_buildings_total=len(sim), trees=len(Tr),
             species=dict(collections.Counter(t["species_guess"] for t in Tr)),
             shore_km={k: round(sum(s["length_m"] for s in Sh if s["type"] == k) / 1000, 2) for k in ("riprap", "bulkhead", "beach")},
             grid_convergence_deg=round(conv, 4))
json.dump(stats, open(f"{WORK}/{reg}_stats.json", "w"), indent=1)
print(json.dumps(stats, indent=1))
