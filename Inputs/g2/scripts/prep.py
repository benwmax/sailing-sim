"""Step 2: UTM 1 km tile list, DEM tile index, NAIP index, and buildings (UTM geometry + sim-frame centroid), per region."""
import sys, re, json, pickle, numpy as np, rasterio, pyarrow.parquet as pq, shapely
from shapely import wkb
from common import *
reg = sys.argv[1]; R = REGIONS[reg]; U = f"EPSG:{R['utm_epsg']}"
m = np.load(f"{WORK}/{reg}_mask10.npz")
band, dist, lake = m["band"], m["dist"], m["lake"]; C = 10.0; ntop = float(m["n_top"]); el = float(m["e_left"])
rr, cc = np.nonzero(band)
north = ntop - (rr + 0.5) * C; east = el + (cc + 0.5) * C
E, N = tf(reg, "local", U).transform(east, north)
tiles = sorted(set(zip(np.floor(E / 1000).astype(int).tolist(), np.floor(N / 1000).astype(int).tolist())))
print(reg, "tiles", len(tiles))
zone = R["utm_epsg"] - 26900
keys = [l.strip() for l in open(f"{SRC}/dem_{R['dem1m_project']}.txt") if l.strip().endswith(".tif")]
ek = {t[0] for t in tiles}; nk = {t[1] for t in tiles}
dem = []
for k in keys:
    mm = re.search(r"_1M_(\d\d)_x(\d+)y(\d+)_", k)
    z, x, y = int(mm[1]), int(mm[2]), int(mm[3])
    if z != zone:
        continue
    b = [x * 1e4, (y - 1) * 1e4, (x + 1) * 1e4, y * 1e4]
    if any(b[0] - 1e3 <= e * 1e3 <= b[2] and b[1] - 1e3 <= n * 1e3 <= b[3] for e, n in tiles):
        dem.append(dict(url=f"/vsicurl/{TNM}/{k}", bbox=b))
print("dem tiles", len(dem))
naip = []
for f in open(f"{WORK}/{reg}_naip.txt").read().split():
    with rasterio.open(f"{SRC}/naip/{f}") as s:
        t = tf(reg, s.crs.to_wkt(), U); b = s.bounds
        xs, ys = t.transform([b.left, b.right, b.left, b.right], [b.bottom, b.bottom, b.top, b.top])
        naip.append(dict(path=f"{SRC}/naip/{f}", bbox=[min(xs), min(ys), max(xs), max(ys)], native=s.crs.to_epsg() == R["utm_epsg"]))
print("naip", len(naip), "native-zone", sum(n["native"] for n in naip))
t = pq.read_table(f"{SRC}/bldg/overture_{reg}.parquet").to_pylist()
to_u = tf(reg, "EPSG:4326", U); u2l = tf(reg, U, "local")
B = []
for r in t:
    g = wkb.loads(r["geometry"])
    g = shapely.transform(g, lambda xy: np.column_stack(to_u.transform(xy[:, 0], xy[:, 1])))
    if g.geom_type == "MultiPolygon":
        g = max(g.geoms, key=lambda p: p.area)
    if g.area < 6:
        continue
    c = g.centroid; le, ln = u2l.transform(c.x, c.y)
    ri, ci = int((ntop - ln) / C), int((le - el) / C)
    if not (0 <= ri < band.shape[0] and 0 <= ci < band.shape[1]) or lake[ri, ci] or dist[ri, ci] > 1010:
        continue
    osm = None; srcs = []
    for s in r["sources"] or []:
        srcs.append(s["dataset"])
        if s["dataset"] == "OpenStreetMap" and s["record_id"]:
            osm = s["record_id"].split("@")[0]
    B.append(dict(id=r["id"], osm=osm, src=sorted(set(srcs)), geom=g, sim_n=ln, sim_e=le, ov_height=r["height"], ov_floors=r["num_floors"],
                  ov_class=r["class"] or r["subtype"], ov_roof_shape=r["roof_shape"], dist10=float(dist[ri, ci])))
print("buildings in band", len(B))
pickle.dump(dict(tiles=tiles, dem=dem, naip=naip, buildings=B), open(f"{WORK}/{reg}_prep.pkl", "wb"))
