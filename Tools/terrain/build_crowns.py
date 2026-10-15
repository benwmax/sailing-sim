"""Graphics G6: the shore's trees from the G2 lidar crowns (Inputs/g2 on the `inputs` branch; DATA-README.md there).

One point per crown found on the lidar canopy height model, with its height and equal-area crown radius, becomes a tree
the game places as it is (TreePlacement.cpp PlaceTreeInstances): full density within 400 m of the water (Bean's rule),
beyond it one crown in three, the kept ones standing for their neighbours (the far shore reads by mass, not by tree).
The game keeps its canopy-map placement for land the lidar band does not cover (over 1 km from the water).

  Tools/venv/bin/python -I Tools/terrain/build_crowns.py [RayHubbard|GalvestonBay ...]

Input:  Data/<World>/raw/g2/trees.geojson.gz  (git show origin/inputs:Inputs/g2/<World>/trees.geojson.gz)
Output: Content/TerrainData/<World>.crowns (little endian):
  "CROW", uint32 version (1), uint32 count, then per crown:
    float32 north, east (m, map frame), ground (m in the world's datum), height (m), crown radius (m)
    uint8 species guess (0 unknown, 1 eastern red cedar), detail (1 within 400 m of the water), weight (crowns it stands
    for), pad
"""
import gzip
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
Z_OFFSET = {"RayHubbard": -132.7407, "GalvestonBay": 0.094}
FULL_DETAIL_M = 400.0
FAR_KEEP = 3   # one crown in three beyond the full-detail band


def keep_far(north, east):
    """Deterministic thinning by position (stable across rebakes of the same data)."""
    h = (int(round(north * 10.0)) * 73856093) ^ (int(round(east * 10.0)) * 19349663)
    return (h & 0x7FFFFFFF) % FAR_KEEP == 0


def build(world):
    src = os.path.join(ROOT, "Data", world, "raw", "g2", "trees.geojson.gz")
    # Galveston 2: the Gulf front south of the bay pack's seam (Inputs/g2/gulf-front/shore, the same layer and fields).
    extra = os.path.join(ROOT, "Inputs", "g2", "gulf-front", "shore", "trees.geojson.gz") if world == "GalvestonBay" else None
    data = json.load(gzip.open(src))
    if extra and os.path.exists(extra):
        data["features"] += json.load(gzip.open(extra))["features"]
    out = []
    near = far = 0
    for f in data["features"]:
        p = f["properties"]
        h = float(p["height_m"])
        r = float(p["crown_radius_m"])
        # Crowns over 30 m are towers, poles or lidar noise in this country (the tallest pecans and cottonwoods
        # reach about 30 m); under 3 m they are scrub (the source already leaves those out).
        if h > 30.0 or h < 3.0 or r <= 0.3:
            continue
        north, east = float(p["sim_north"]), float(p["sim_east"])
        full = float(p["dist_to_water_m"]) <= FULL_DETAIL_M
        if not full and not keep_far(north, east):
            continue
        weight = 1 if full else FAR_KEEP
        z = p.get("ground_z_navd88")
        ground = float(z) + Z_OFFSET[world] if z is not None else -1000.0
        cedar = 1 if p.get("species_guess") == "eastern_red_cedar" else 0
        out.append(struct.pack("<5f4B", north, east, ground, h, r, cedar, 1 if full else 0, weight, 0))
        near += full
        far += not full
    dst = os.path.join(ROOT, "Content", "TerrainData", f"{world}.crowns")
    with open(dst, "wb") as fh:
        fh.write(b"CROW" + struct.pack("<II", 1, len(out)))
        fh.writelines(out)
    print(f"{world}: {len(out)} crowns ({near} within {FULL_DETAIL_M:.0f} m of the water, {far} beyond, kept 1 in {FAR_KEEP}) -> {dst}")


if __name__ == "__main__":
    for w in sys.argv[1:] or ["RayHubbard", "GalvestonBay"]:
        build(w)
