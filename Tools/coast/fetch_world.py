"""Downloads the free data a coast world without NOAA charts bakes from (a box and a name: Tools/coast/worlds/<World>.json).

  python3 Tools/coast/fetch_world.py Marseille [--force]

Everything lands in Data/<World>/raw (git-ignored); files already there are kept unless --force. Sources, all usable
in a sold game with credit (docs/licences/assets.csv, CREDITS.md):
  - Copernicus DEM GLO-30 and GLO-90 (AWS Open Data; (c) DLR/Airbus, provided under COPERNICUS by the EU and ESA, free
    licence with attribution), the land: 30 m inside the box, 90 m for the far coast ring
  - EMODnet Bathymetry DTM (CC BY 4.0), the sea bed, through its WCS
  - OpenStreetMap (ODbL 1.0) through Overpass: coastline, harbours, quays, pontoons, breakwaters, seamarks (buoys,
    beacons, lights with their characters), landmarks, land use, buildings
  - NGA Pub 113 List of Lights (US public domain), the light characters checked against OSM's
  - IGN RGE ALTI 5 m (Licence Ouverte 2.0), bare earth, through the Geoplateforme's WMS-R (the world's "ign" box,
    Lambert-93); the bake prefers it to Copernicus wherever it has a value
SHOM products (charts, Litto3D, tide tables) are not free for this use: never fetch them.
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OVERPASS = os.path.join(ROOT, "Tools", "terrain", "overpass.sh")


def main():
    world = json.load(open(os.path.join(os.path.dirname(__file__), "worlds", f"{sys.argv[1]}.json")))
    force = "--force" in sys.argv
    raw = os.path.join(ROOT, "Data", world["name"], "raw")
    os.makedirs(raw, exist_ok=True)
    w, s, e, n = world["bbox"]

    def need(name):
        p = os.path.join(raw, name)
        return force or not os.path.exists(p) or os.path.getsize(p) == 0

    def curl(url, name, timeout=900):
        if not need(name):
            return
        print("fetch", name)
        subprocess.run(["curl", "-sS", "-f", "-m", str(timeout), "-A", "SailingSim/0.1 (ben@benjaminwmaxwell.com)", "-o",
                        os.path.join(raw, name), url], check=True)

    def overpass(query, name):
        if not need(name):
            return
        print("overpass", name)
        subprocess.run([OVERPASS, query, os.path.join(raw, name)], check=True)
        time.sleep(10)   # the public server rate-limits

    # Land: Copernicus GLO-30 for every 1-degree tile the box touches, GLO-90 for the far ring.
    import math
    for lat in range(math.floor(s), math.floor(n) + 1):
        for lon in range(math.floor(w), math.floor(e) + 1):
            t = f"N{lat:02d}_00_E{lon:03d}_00" if lon >= 0 else f"N{lat:02d}_00_W{-lon:03d}_00"
            stem = f"Copernicus_DSM_COG_10_{t}_DEM"
            curl(f"https://copernicus-dem-30m.s3.amazonaws.com/{stem}/{stem}.tif", f"copdem_{t[:3]}_{t[7:11]}.tif")
    os.makedirs(os.path.join(raw, "far"), exist_ok=True)
    for t in world.get("far_ring", {}).get("tiles", []):
        stem = f"Copernicus_DSM_COG_30_{t}_DEM"
        try:
            curl(f"https://copernicus-dem-90m.s3.amazonaws.com/{stem}/{stem}.tif", f"far/glo90_{t}.tif")
        except subprocess.CalledProcessError:
            print("  no GLO-90 tile (all sea):", t)
    os.makedirs(os.path.join(raw, "far"), exist_ok=True)

    # Land, bare earth: IGN RGE ALTI 5 m through the Geoplateforme's WMS-R (32-bit BIL, Lambert-93), in 10 km tiles with a
    # 100 m overlap, each with its ESRI .hdr. Some resolvers fail on data.geopf.fr: then its address comes from Google's
    # public DNS over HTTPS and curl is pinned to it (the TLS name stays data.geopf.fr).
    ign = world.get("ign")
    if ign:
        resolve = []
        if subprocess.run(["curl", "-sS", "-m", "20", "-o", "/dev/null", "https://data.geopf.fr/"], capture_output=True).returncode != 0:
            ans = json.loads(subprocess.run(["curl", "-sS", "-m", "20", "-H", "accept: application/dns-json",
                                             "https://dns.google/resolve?name=data.geopf.fr&type=A"], capture_output=True, text=True, check=True).stdout)
            ip = [a["data"] for a in ans.get("Answer", []) if a["type"] == 1][0]
            resolve = ["--resolve", f"data.geopf.fr:443:{ip}"]
            print("data.geopf.fr does not resolve here: pinned to", ip)
        os.makedirs(os.path.join(raw, "rgealti"), exist_ok=True)
        x0, y0, x1, y1 = ign["l93_box"]
        res, tile, pad = float(ign.get("cell_m", 5.0)), 10000.0, 100.0
        x = x0
        while x < x1:
            y = y0
            while y < y1:
                name = f"rgealti/RGEALTI_{int(x)}_{int(y)}"
                if need(name + ".bil"):
                    bx = (x - pad, y - pad, x + tile + pad, y + tile + pad)
                    n_ = int(round((tile + 2 * pad) / res))
                    url = ("https://data.geopf.fr/wms-r/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES"
                           f"&CRS=EPSG:2154&BBOX={bx[0]},{bx[1]},{bx[2]},{bx[3]}&WIDTH={n_}&HEIGHT={n_}&FORMAT=image/x-bil;bits=32&STYLES=")
                    print("fetch", name)
                    subprocess.run(["curl", "-sS", "-f", "-m", "600", *resolve, "-o", os.path.join(raw, name + ".bil"), url], check=True)
                    # ESRI BIL header: the map coordinates of the upper-left cell's centre, little-endian float32.
                    with open(os.path.join(raw, name + ".hdr"), "w") as fh:
                        fh.write(f"BYTEORDER I\nLAYOUT BIL\nNROWS {n_}\nNCOLS {n_}\nNBANDS 1\nNBITS 32\nPIXELTYPE FLOAT\n"
                                 f"ULXMAP {bx[0] + res / 2}\nULYMAP {bx[3] - res / 2}\nXDIM {res}\nYDIM {res}\nNODATA -99999\n")
                    time.sleep(1)
                y += tile
            x += tile

    # Sea bed: EMODnet mean depth, the box plus a margin.
    m = 0.06
    curl("https://ows.emodnet-bathymetry.eu/wcs?SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCoverage&COVERAGEID=emodnet__mean"
         f"&SUBSET=Lat({s - m:.3f},{n + m:.3f})&SUBSET=Long({w - m:.3f},{e + m:.3f})&FORMAT=image/tiff", "emodnet_mean.tif")

    # Lights: NGA Pub 113 (the whole volume; the bake picks the box).
    curl("https://msi.nga.mil/api/publications/ngalol/lights-buoys?volume=113&output=json&includeRemovals=false", "nga_pub113.json")

    # OpenStreetMap. The coastline query reaches past the box so the bake can close the land polygons along its edge.
    b = f"{s},{w},{n},{e}"
    bx = f"{s - 0.05},{w - 0.05},{n + 0.05},{e + 0.05}"
    overpass(f'[out:json][timeout:250];way["natural"="coastline"]({bx});out geom;', "coastline_osm.json")
    overpass(f'[out:json][timeout:250];(nwr["seamark:type"]({b});nwr["man_made"="lighthouse"]({b}););out geom tags;', "seamarks_osm.json")
    overpass(f'[out:json][timeout:250];(way["man_made"~"pier|breakwater|groyne|quay"]({b});nwr["leisure"~"marina|slipway"]({b});'
             f'nwr["harbour"]({b});nwr["landuse"="harbour"]({b});way["mooring"]({b});way["bridge"]["highway"]({b}););out geom tags;',
             "harbours_osm.json")
    overpass(f'[out:json][timeout:250];(nwr["man_made"~"tower|water_tower|chimney|crane|mast|obelisk"]({b});'
             f'nwr["historic"~"castle|fort|monument"]({b});nwr["building"~"cathedral|church|basilica"]["name"]({b});'
             f'nwr["amenity"="place_of_worship"]["name"]({b}););out center tags;', "landmarks_osm.json")
    overpass(f'[out:json][timeout:250];(way["landuse"~"forest|residential|commercial|industrial|grass|meadow|farmland|vineyard|orchard|port"]({b});'
             f'relation["landuse"="forest"]({b});way["natural"~"wood|scrub|heath|grassland|bare_rock|beach|cliff|wetland"]({b});'
             f'relation["natural"~"wood|scrub|heath|bare_rock"]({b});way["leisure"~"park|nature_reserve|garden"]({b}););out geom tags;',
             "landuse_osm.json")
    k = int(world.get("osm", {}).get("buildings_tiles", 3))
    for i in range(k):
        for j in range(k):
            ts, tn = s + (n - s) * i / k, s + (n - s) * (i + 1) / k
            tw, te = w + (e - w) * j / k, w + (e - w) * (j + 1) / k
            overpass(f'[out:json][timeout:280];way["building"]({ts:.4f},{tw:.4f},{tn:.4f},{te:.4f});out geom tags;',
                     f"buildings_osm_{i * k + j}.json")
    print("Fetched into", raw)


if __name__ == "__main__":
    main()
