"""Downloads the free data stage 1 of the Florida-to-Bahamas map bakes from (docs/world-bimini): Miami and Biscayne Bay,
the Florida Straits and Bimini, the three members of MiamiBimini.

  Tools/venv/bin/python -I Tools/coast/fetch_miami_bimini.py [MiamiBiscayne FloridaStraits Bimini] [--force] [--list]

Everything lands in Data/<World>/raw (git-ignored, as for Galveston); files already there are kept unless --force.
--list only prints the ENC cells and tide stations it would fetch. Run it on the Mac: most of these hosts refuse cloud
sessions (docs/world-bimini/data-sources.md lists which were reachable on Nov 27 2026).

All of it is usable in a sold game (docs/licences/assets.csv rows and CREDITS.md lines go in with the first bake):
  - NOAA ENC cells (S-57, public domain): picked from NOAA's product catalog by each world's box, so new or rescheme
    cells are found without a list here. The usage bands a world takes: Miami 3-5 (approach to harbour), the Straits 2-3
    (overview to approach: 200 m cells need no more), Bimini 3-5 (the US charts reach the islands; how detailed the
    Bahamas side is shows in the bake's coverage line).
  - USGS 3DEP 1/3 arc-second DEM (public domain) through the National Map's export service, Miami only (Bimini has no
    US lidar). The 1 m FL_MiamiDade_D23 lidar DEM (prd-tnm S3, reachable from the cloud too) is the shore-detail
    upgrade, fetched by a later build_shore_detail step.
  - NOAA CO-OPS tide stations (public domain): harmonic constituents, datums and metadata for the stations a world names,
    and a list of every harmonic station in its box (tides/stations_in_box.json) to choose more from.
The Gulf Stream's monthly means are not fetched here: they need a (free) Copernicus Marine account or HYCOM's THREDDS
server; the commands are in docs/world-bimini/data-sources.md, and gulf_stream.py bakes an analytic stream without them.
"""
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WORLDS = os.path.join(os.path.dirname(__file__), "worlds")
CATALOG = "https://charts.noaa.gov/ENCs/ENCProdCat.xml"
ENC_ZIP = "https://charts.noaa.gov/ENCs/{}.zip"
CO_OPS = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi"
TNM_EXPORT = ("https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage?bbox={w},{s},{e},{n}"
              "&bboxSR=4326&imageSR=4326&size={cols},{rows}&format=tiff&pixelType=F32&noDataInterpretation=esriNoDataMatchAny"
              "&interpolation=RSP_BilinearInterpolation&f=image")
BANDS = {"MiamiBiscayne": (3, 5), "FloridaStraits": (2, 3), "Bimini": (3, 5)}
DEM_M = 10.0   # the export's cell, about 1/3 arc-second


def curl(url, path, force, timeout=900):
    if not force and os.path.exists(path) and os.path.getsize(path) > 0:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # A generic client name: no personal details go to outside services.
    subprocess.run(["curl", "-sS", "-f", "-L", "--retry", "3", "--retry-all-errors", "--retry-delay", "10", "-m", str(timeout),
                    "-A", "SailingSim-bake/0.1", "-o", path, url], check=True)
    return True


DEM_TILE_DEG = 0.1   # one export per 0.1 degree square (about 1,100 x 1,000 px): the whole Miami box in one request (3110 x 5344) was dropped


def fetch_dem(box, out, force):
    """The 3DEP 1/3 arc-second DEM over a box, as one GeoTIFF the bake reads (dem_3dep.tif): fetched in DEM_TILE_DEG tiles
    with a small overlap, then each tile is resampled by its own GeoTIFF tags onto one grid of DEM_M cells (the export
    widens a requested box, so tiles are never pasted by their requested corners)."""
    import math
    import numpy as np
    import tifffile
    from scipy import ndimage
    if not force and os.path.exists(out) and os.path.getsize(out) > 0:
        return
    w, s, e, n = box
    dlat = DEM_M / 111320.0
    dlon = DEM_M / (111320.0 * math.cos(math.radians(0.5 * (s + n))))
    rows, cols = int(math.ceil((n - s) / dlat)) + 1, int(math.ceil((e - w) / dlon)) + 1
    mosaic = np.full((rows, cols), np.nan, np.float32)
    tiles = os.path.join(os.path.dirname(out), "dem_tiles")
    pad = 0.005
    lat0 = s
    while lat0 < n - 1e-9:
        lon0 = w
        while lon0 < e - 1e-9:
            tw, ts, te, tn = lon0 - pad, lat0 - pad, min(lon0 + DEM_TILE_DEG, e) + pad, min(lat0 + DEM_TILE_DEG, n) + pad
            tr, tc = int(math.ceil((tn - ts) / dlat)), int(math.ceil((te - tw) / dlon))
            path = os.path.join(tiles, f"dem_{lat0:.2f}_{lon0:.2f}.tif")
            curl(TNM_EXPORT.format(w=tw, s=ts, e=te, n=tn, cols=tc, rows=tr), path, force)
            with tifffile.TiffFile(path) as tif:
                d = tif.pages[0].asarray().astype(np.float32)
                tie = tif.pages[0].tags["ModelTiepointTag"].value
                scale = tif.pages[0].tags["ModelPixelScaleTag"].value
            d[(d < -1000.0) | (d > 10000.0)] = np.nan
            # The mosaic cells this tile covers, sampled bilinearly from the tile by its own georeferencing.
            r0, r1 = max(0, int((n - (tie[4])) / dlat)), min(rows, int(math.ceil((n - (tie[4] - d.shape[0] * scale[1])) / dlat)) + 1)
            c0, c1 = max(0, int((tie[3] - w) / dlon)), min(cols, int(math.ceil((tie[3] + d.shape[1] * scale[0] - w) / dlon)) + 1)
            R, C = np.meshgrid(np.arange(r0, r1), np.arange(c0, c1), indexing="ij")
            lat, lon = n - R * dlat, w + C * dlon
            fr, fc = (tie[4] - lat) / scale[1] - 0.5, (lon - tie[3]) / scale[0] - 0.5
            ok = (fr >= 0) & (fc >= 0) & (fr <= d.shape[0] - 1) & (fc <= d.shape[1] - 1)
            v = ndimage.map_coordinates(np.nan_to_num(d, nan=-9999.0), [fr, fc], order=1, mode="nearest")
            v = np.where(ok & (v > -1000.0), v, np.nan)
            block = mosaic[r0:r1, c0:c1]
            fill = np.isnan(block) & ~np.isnan(v)
            block[fill] = v[fill]
            lon0 += DEM_TILE_DEG
        lat0 += DEM_TILE_DEG
    print(f"  3DEP mosaic {cols} x {rows}, {np.isnan(mosaic).mean() * 100:.1f}% without data")
    # GeoTIFF with the two tags the bake reads: the tiepoint at the upper-left cell's corner and the pixel scale.
    tifffile.imwrite(out, mosaic, extratags=[(33550, 12, 3, (dlon, dlat, 0.0), False),
                                             (33922, 12, 6, (0.0, 0.0, 0.0, w - 0.5 * dlon, n + 0.5 * dlat, 0.0), False)])


def local(tag):
    return tag.rsplit("}", 1)[-1].lower()


def catalog_cells(path):
    """NOAA's ENC product catalog as (name, usage band, coverage box w s e n), from each <cell>'s <name> and the
    <lat>/<long> vertices of its coverage panels. Read by local tag name, so a namespace change doesn't matter."""
    cells = []
    for el in ET.parse(path).getroot().iter():
        if local(el.tag) != "cell":
            continue
        name, lats, lons, status = None, [], [], "active"
        for ch in el.iter():
            t = local(ch.tag)
            if t == "name" and name is None and ch.text:
                name = ch.text.strip()
            elif t == "status" and ch.text:
                status = ch.text.strip().lower()
            elif t == "lat" and ch.text:
                lats.append(float(ch.text))
            elif t in ("long", "lon") and ch.text:
                lons.append(float(ch.text))
        if name and lats and lons and status.startswith("active") and len(name) >= 3 and name[2].isdigit():
            cells.append((name, int(name[2]), (min(lons), min(lats), max(lons), max(lats))))
    return cells


def overlaps(a, b):
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def fetch_world(name, cells, force, list_only):
    world = json.load(open(os.path.join(WORLDS, f"{name}.json")))
    raw = os.path.join(ROOT, "Data", name, "raw")
    box = tuple(world["bbox"])
    lo, hi = BANDS.get(name, (2, 5))
    mine = sorted(c for c in cells if lo <= c[1] <= hi and overlaps(c[2], box))
    print(f"{name}: {len(mine)} ENC cells in bands {lo}-{hi}: {' '.join(c[0] for c in mine)}")

    # Tide stations: every harmonic station in the box, for choosing; the world's own fetched in full.
    st_list = os.path.join(raw, "tides", "stations_all.json")
    if not list_only:
        curl(f"{CO_OPS}/stations.json?type=harcon&units=metric", st_list, force, 120)
        allst = json.load(open(st_list)).get("stations", [])
        inbox = [{"id": s["id"], "name": s["name"], "lat": s["lat"], "lng": s["lng"]} for s in allst
                 if box[1] <= float(s["lat"]) <= box[3] and box[0] <= float(s["lng"]) <= box[2]]
        json.dump(inbox, open(os.path.join(raw, "tides", "stations_in_box.json"), "w"), indent=1)
        print(f"  {len(inbox)} harmonic tide stations in the box: " + ", ".join(f"{s['id']} {s['name']}" for s in inbox))
    tides = world.get("tides", {})
    ids = list(dict.fromkeys(tides.get("stations", []) + ([tides["datum_station"]] if tides.get("datum_station") else [])))
    print(f"  tide stations to fetch: {' '.join(ids) or 'none'}")
    if list_only:
        return
    for c, _, _ in mine:
        z = os.path.join(raw, "enc", f"{c}.zip")
        if curl(ENC_ZIP.format(c), z, force, 300) or not os.path.isdir(os.path.join(raw, "enc", "ENC_ROOT", c)):
            with zipfile.ZipFile(z) as zf:
                zf.extractall(os.path.join(raw, "enc"))
    for st in ids:
        curl(f"{CO_OPS}/stations/{st}/harcon.json?units=metric", os.path.join(raw, "tides", f"harcon_{st}.json"), force, 60)
        curl(f"{CO_OPS}/stations/{st}/datums.json?units=metric", os.path.join(raw, "tides", f"datums_{st}.json"), force, 60)
        curl(f"{CO_OPS}/stations/{st}.json", os.path.join(raw, "tides", f"station_{st}.json"), force, 60)
    # Land: only where the world names the 3DEP export (Miami). The bake reads the real extent from the GeoTIFF tags.
    if any(src.get("path") == "dem_3dep.tif" for src in world.get("elevation", [])):
        fetch_dem(box, os.path.join(raw, "dem_3dep.tif"), force)
    print(f"  fetched into {raw}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force, list_only = "--force" in sys.argv, "--list" in sys.argv
    names = args or ["MiamiBiscayne", "FloridaStraits", "Bimini"]
    cat = os.path.join(ROOT, "Data", "ENC", "raw", "ENCProdCat.xml")
    curl(CATALOG, cat, force, 300)
    cells = catalog_cells(cat)
    print(f"ENC catalog: {len(cells)} active cells")
    for name in names:
        fetch_world(name, cells, force, list_only)


if __name__ == "__main__":
    main()
