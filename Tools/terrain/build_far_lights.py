"""Wide World Rendering PR 3 (docs/world-far-lights): what a world shows at night beyond its near lights.

  Tools/venv/bin/python -I Tools/terrain/build_far_lights.py [World ...]   (default RayHubbard GalvestonBay GulfPassage Marseille)

Reads the world's bake (Content/TerrainData/<World>.json, .houses) and writes Content/TerrainData/<World>.farlights.json:
  - "lights": every lit aid the world charts (its navaids), plus the lights of the coast around it out to the far ring's
    radius from the other bakes that cover it (Galveston Bay and the Gulf passage see each other's) and, for a world
    with NGA Pub 113 in its raw data, the List of Lights (Marseille: Cap Couronne, Sainte-Marie, Cassidaigne, Cap
    Sicie...). One entry per light: map position, height above the datum, S-57 character, colours, nominal range, and
    whether it is a navaid of this world (the near pool's NavaidsActor draws those close by, ANavaidsActor index).
  - "shore": lit shore sprites: the houses bake binned to 100 m cells (weight = houses in the cell), the town at night.
  - "cities": the light domes over the nearest cities (up to four: name, map position, light weight), from the world
    json's "city_glow" or, for the Texas worlds, the list that was hard-coded in SailingEnvironment.cpp.
  - "lanes": shipping lanes for the horizon ships (map polylines, knots), from the world json's "ship_lanes".
"""
import glob
import json
import math
import os
import re
import struct
import sys

import numpy as np
from pyproj import Transformer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(ROOT, "Content", "TerrainData")
WORLDS = os.path.join(ROOT, "Tools", "coast", "worlds")
sys.path.insert(0, os.path.join(ROOT, "Tools", "coast"))

# The domes SailingEnvironment.cpp had hard-coded (Visual V6), by world; light 1 = Dallas.
TEXAS_CITIES = [("Dallas", 32.78, -96.80, 1.0), ("Houston", 29.76, -95.37, 1.3), ("Texas City", 29.39, -94.92, 0.35),
                ("Fort Worth", 32.75, -97.33, 0.6), ("Galveston", 29.29, -94.80, 0.3), ("Pasadena", 29.69, -95.21, 0.35)]
TEXAS_LANES = {
    # The Galveston entrance to the Gulf safety fairway (the Galveston-Freeport approach), ships at 12 kn.
    "GalvestonBay": [{"name": "Galveston fairway", "kn": 12.0, "pts": [[29.335, -94.700], [29.20, -94.55], [28.95, -94.35]]}],
    "GulfPassage": [{"name": "Galveston fairway", "kn": 12.0, "pts": [[29.335, -94.700], [29.20, -94.55], [28.95, -94.35]]},
                    {"name": "Freeport fairway", "kn": 11.0, "pts": [[28.93, -95.30], [28.80, -95.15], [28.60, -95.00]]}],
}
FAR_RADIUS_M = {"RayHubbard": 30000.0, "GalvestonBay": 45000.0, "GulfPassage": 45000.0}


def world_cfg(name):
    p = os.path.join(WORLDS, f"{name}.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def light_entry(x, y, z, light, name, navaid):
    return {"xy": [round(x, 1), round(y, 1)], "z": round(z, 1), "litchr": light.get("litchr") or 2, "siggrp": light.get("siggrp") or "(1)",
            "sigper": light.get("sigper"), "colour": [int(c) for c in (light.get("colour") or ["1"]) if str(c).isdigit()] or [1],
            "range": light.get("range"), "name": name, "navaid": navaid}


def build(world):
    meta = json.load(open(os.path.join(DATA, f"{world}.json")))
    cfg = world_cfg(world)
    to_map = Transformer.from_crs("EPSG:4326", meta["projection"], always_xy=True)

    def ll(lat, lon):
        e, n = to_map.transform(lon, lat)
        return n, e

    radius = float(cfg.get("far_ring", {}).get("radius_km", 0.0)) * 1000.0 or FAR_RADIUS_M.get(world, 40000.0)
    lights = []
    # This world's lit navaids: their index in the navaid list is how the game ties them to ANavaidsActor's near lights.
    for i, a in enumerate(meta.get("navaids", [])):
        if "light" in a:
            top = a["light"].get("height") or (3.4 if a["kind"] == "buoy" else 6.0)
            lights.append(light_entry(a["x"], a["y"], top, a["light"], a.get("name") or "", i))
    own = np.array([l["xy"] for l in lights]) if lights else np.zeros((0, 2))

    def add_far(x, y, z, light, name):
        if math.hypot(x, y) > radius:
            return False
        if len(own) and np.min(np.hypot(own[:, 0] - x, own[:, 1] - y)) < 60.0:
            return False   # charted here already
        if any(math.hypot(l["xy"][0] - x, l["xy"][1] - y) < 60.0 for l in lights if l["navaid"] < 0):
            return False
        lights.append(light_entry(x, y, z, light, name, -1))
        return True

    far = 0
    # Neighbouring bakes' charted lights (the Texas coast: the bay and the Gulf passage overlap).
    for other in ("GalvestonBay", "GulfPassage"):
        if other == world or not os.path.exists(os.path.join(DATA, f"{other}.json")) or world == "RayHubbard":
            continue
        om = json.load(open(os.path.join(DATA, f"{other}.json")))
        back = Transformer.from_crs(om["projection"], "EPSG:4326", always_xy=True)
        for a in om.get("navaids", []):
            if "light" in a:
                lon, lat = back.transform(a["y"], a["x"])
                x, y = ll(lat, lon)
                far += add_far(x, y, a["light"].get("height") or 6.0, a["light"], a.get("name") or "")
    # NGA Pub 113 where the world fetched it (Tools/coast/fetch_world.py).
    raw = os.path.join(ROOT, "Data", world, "raw")
    if os.path.exists(os.path.join(raw, "nga_pub113.json")):
        import osm_chart
        lat0, lon0 = meta["latitude"], meta["longitude"]
        dlat, dlon = radius / 111200.0, radius / (111200.0 * math.cos(math.radians(lat0)))
        for n in osm_chart.nga_lights(raw, [lon0 - dlon, lat0 - dlat, lon0 + dlon, lat0 + dlat]):
            x, y = ll(n["lat"], n["lon"])
            far += add_far(x, y, n["height"] or 8.0, {"litchr": n["litchr"], "siggrp": n["siggrp"], "sigper": n["sigper"],
                                                     "colour": n["colour"], "range": n["range"]}, n["name"])

    # Lit shore: the houses binned to 100 m.
    shore = {}
    hp = os.path.join(DATA, f"{world}.houses")
    if os.path.exists(hp):
        data = open(hp, "rb").read()
        count = struct.unpack("<I", data[8:12])[0]
        at = 12
        for _ in range(count):
            n_, e_, ground = struct.unpack("<3f", data[at:at + 12])
            rects = data[at + 24 + 2]
            at += 24 + 8 + rects * 20
            key = (int(math.floor(n_ / 100.0)), int(math.floor(e_ / 100.0)))
            c = shore.setdefault(key, [0.0, 0.0, 0.0, 0])
            c[0] += n_; c[1] += e_; c[2] += max(ground, 0.0); c[3] += 1
    shore_out = [[round(c[0] / c[3], 1), round(c[1] / c[3], 1), round(c[2] / c[3] + 6.0, 1), c[3]] for c in shore.values() if c[3] >= 2]

    # City domes.
    if cfg.get("city_glow"):
        cities = [{"name": c["name"], "xy": [round(v, 1) for v in ll(c["lat"], c["lon"])],
                   "light": round((float(c.get("population", 100000)) / 2.3e6) ** 0.8, 3)} for c in cfg["city_glow"]]   # Houston's 2.3 M = 1.3 in the old list
    else:
        cities = [{"name": n, "xy": [round(v, 1) for v in ll(la, lo)], "light": w} for n, la, lo, w in TEXAS_CITIES]

    lanes = []
    for lane in cfg.get("ship_lanes") or TEXAS_LANES.get(world, []):
        lanes.append({"name": lane["name"], "kn": lane["kn"], "ships": lane.get("ships", 3),
                      "pts": [[round(v, 1) for v in ll(la, lo)] for la, lo in lane["pts"]]})

    out = {"schema": 1, "world": world, "radius_m": radius, "lights": lights, "shore": shore_out, "cities": cities, "lanes": lanes,
           "sources": "the world's charted navaids; neighbouring bakes; NGA Pub 113 List of Lights (public domain); the houses bake"}
    path = os.path.join(DATA, f"{world}.farlights.json")
    with open(path, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print(f"{world}: {len(lights)} lights ({len(lights) - far} charted here, {far} from beyond), {len(shore_out)} shore sprites, "
          f"{len(cities)} city domes, {len(lanes)} lanes; {os.path.getsize(path) / 1e3:.0f} kB -> {path}")


if __name__ == "__main__":
    for w in sys.argv[1:] or ["RayHubbard", "GalvestonBay", "GulfPassage", "Marseille"]:
        build(w)
