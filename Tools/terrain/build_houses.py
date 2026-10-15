"""Graphics G6: the shore's houses from the G2 footprints (Inputs/g2 on the `inputs` branch; DATA-README.md there).

Each Overture footprint with its lidar roof fit (eave, ridge height, pitch, roof type, ridge direction) and NAIP roof
colour becomes a few roof rectangles in the map frame: one for a plain footprint, up to four for an L, T or U plan
(greedy largest rectangles on a 1 m raster, at least 4 m wide, grown into each other so the wings join; a footprint
filling 78% of its bounding rectangle stays one). The game builds walls, eaves,
roofs, windows and doors from them (WorldKit BuildHouseGeometry) and bakes them into Nanite tiles.

  Tools/venv/bin/python -I Tools/terrain/build_houses.py [RayHubbard|GalvestonBay ...]

Input:  Data/<World>/raw/g2/buildings.geojson.gz  (git show origin/inputs:Inputs/g2/<World>/buildings.geojson.gz)
Output: Content/TerrainData/<World>.houses (little endian):
  "HOUS", uint32 version (1), uint32 count, then per house:
    float32 north, east (footprint centre, m), ground (m in the world's datum), eave, ridge (m above ground), pitch (deg)
    uint8 roof (0 flat, 1 gable, 2 hip, 3 shed), detail (1 within 400 m of the water), rects, storeys,
    uint8 roof colour r, g, b (sRGB), flags (1 lidar roof, 2 commercial)
    rects x { float32 north, east, half length, half width, yaw (deg, X north toward Y east) }  (length along yaw)
"""
import gzip
import json
import math
import os
import struct
import sys
import zlib

import numpy as np
import shapely
import shapely.affinity
from pyproj import Transformer
from shapely.geometry import Polygon

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Sim Z = NAVD88 + offset (DATA-README.md: the pool for the lake, MLLW for the coast).
Z_OFFSET = {"RayHubbard": -132.7407, "GalvestonBay": 0.094}
COMMERCIAL = {"commercial", "retail", "industrial", "warehouse", "office", "hotel", "school", "church", "hospital",
              "civic", "public", "parking", "service", "supermarket", "university", "college", "transportation"}


def largest_rect(mask):
    """Largest all-true axis-aligned rectangle in a 2D bool array: (area, r0, r1, c0, c1), half-open."""
    rows, cols = mask.shape
    h = np.zeros(cols, dtype=np.int32)
    best = (0, 0, 0, 0, 0)
    for r in range(rows):
        h = np.where(mask[r], h + 1, 0)
        stack = []
        for c in range(cols + 1):
            cur = h[c] if c < cols else 0
            start = c
            while stack and stack[-1][1] >= cur:
                s, hh = stack.pop()
                area = hh * (c - s)
                if area > best[0]:
                    best = (area, r - hh + 1, r + 1, s, c)
                start = s
            stack.append((start, cur))
    return best


def decompose(poly, ca, sa, cx, cy):
    """Rectangles (u0, u1, v0, v1) in the footprint's frame (u along the long axis) covering most of it."""
    local = shapely.affinity.affine_transform(poly, [ca, sa, -sa, ca, -(cx * ca + cy * sa), -(-cx * sa + cy * ca)])
    u0, v0, u1, v1 = local.bounds
    if local.area > 0.78 * (u1 - u0) * (v1 - v0):
        return [(u0, u1, v0, v1)]
    nu, nv = max(1, int(math.ceil(u1 - u0))), max(1, int(math.ceil(v1 - v0)))
    if nu * nv > 40000:
        return [(u0, u1, v0, v1)]
    uu, vv = np.meshgrid(u0 + np.arange(nu) + 0.5, v0 + np.arange(nv) + 0.5)
    filled = shapely.contains_xy(local, uu, vv)
    if filled.sum() < 6:
        return [(u0, u1, v0, v1)]
    covered = np.zeros_like(filled)
    rects = []
    while len(rects) < 4:
        area, r0, r1, c0, c1 = largest_rect(filled & ~covered)
        if area < 20 or min(r1 - r0, c1 - c0) < 4:
            break
        # Grow into the cells already covered, so the wings overlap and join.
        grew = True
        while grew:
            grew = False
            if r0 > 0 and filled[r0 - 1, c0:c1].all(): r0 -= 1; grew = True
            if r1 < nv and filled[r1, c0:c1].all(): r1 += 1; grew = True
            if c0 > 0 and filled[r0:r1, c0 - 1].all(): c0 -= 1; grew = True
            if c1 < nu and filled[r0:r1, c1].all(): c1 += 1; grew = True
        covered[r0:r1, c0:c1] = True
        rects.append((u0 + c0, u0 + c1, v0 + r0, v0 + r1))
        if covered.sum() >= 0.92 * filled.sum():
            break
    return rects or [(u0, u1, v0, v1)]


def hash01(s, k):
    return (zlib.crc32(f"{s}:{k}".encode()) & 0xFFFFFF) / float(0xFFFFFF)


def build(world):
    src = os.path.join(ROOT, "Data", world, "raw", "g2", "buildings.geojson.gz")
    # Galveston 2: the Gulf front south of the bay pack's seam (Inputs/g2/gulf-front/shore, the same layer and fields).
    extra = os.path.join(ROOT, "Inputs", "g2", "gulf-front", "shore", "buildings.geojson.gz") if world == "GalvestonBay" else None
    meta = json.load(open(os.path.join(ROOT, "Content", "TerrainData", f"{world}.json")))
    to_local = Transformer.from_crs("EPSG:4326", meta["projection"], always_xy=True)
    fc = json.load(gzip.open(src))
    if extra and os.path.exists(extra):
        fc["features"] += json.load(gzip.open(extra))["features"]
    out = []
    stats = {"rects": 0, "multi": 0, "full": 0, "lidar": 0}
    for f in fc["features"]:
        p = f["properties"]
        geom = f["geometry"]
        rings = geom["coordinates"] if geom["type"] == "Polygon" else max(geom["coordinates"], key=lambda g: len(g[0]))
        ring = np.array(rings[0])
        e, n = to_local.transform(ring[:, 0], ring[:, 1])
        poly = Polygon(np.stack([n, e], axis=1)).buffer(0)
        if poly.is_empty or poly.area < 12.0:
            continue
        if poly.geom_type != "Polygon":
            poly = max(poly.geoms, key=lambda g: g.area)
        poly = poly.simplify(0.4)
        # The long axis from the minimum rotated rectangle, in the map frame.
        mrr = np.array(poly.minimum_rotated_rectangle.exterior.coords)[:4]
        d0, d1 = mrr[1] - mrr[0], mrr[2] - mrr[1]
        axis = d0 if np.hypot(*d0) >= np.hypot(*d1) else d1
        ang = math.atan2(axis[1], axis[0])
        ca, sa = math.cos(ang), math.sin(ang)
        c = np.array(poly.centroid.coords[0])
        rects = decompose(poly, ca, sa, c[0], c[1])
        cls = (p.get("ov_class") or "").lower()
        commercial = cls in COMMERCIAL or (p.get("roof_type") == "flat" and poly.area > 400.0) or poly.area > 2500.0
        rt = p.get("roof_type")
        if rt == "complex":
            rt = p.get("roof_fallback") or "hip"
        if rt not in ("flat", "gable", "hip", "shed"):
            # No lidar roof (built since 2018): Texas suburban houses are mostly hipped; big or commercial ones flat.
            rt = "flat" if commercial else ("gable" if hash01(p["id"], 1) < 0.3 else "hip")
        if p.get("roof_detail") == "shed":
            rt = "shed"
        roof = {"flat": 0, "gable": 1, "hip": 2, "shed": 3}[rt]
        # Heights above ground. The lidar fit gives the eave and the roof top; otherwise one or two storeys.
        h = p.get("height_m")
        eave = p.get("eave_m")
        floors = p.get("ov_floors")
        if eave is None or not (2.0 <= eave <= 40.0):
            if h and roof == 0:
                eave = h
            elif h:
                eave = max(2.5, h * 0.62)
            else:
                storeys = int(floors) if floors else (2 if (poly.area > 180.0 and hash01(p["id"], 2) < 0.3) else 1)
                eave = 2.9 * storeys + 0.2
        eave = float(np.clip(eave, 2.4, 60.0))
        pitch = p.get("pitch_deg")
        pitch = float(np.clip(pitch, 12.0, 40.0)) if pitch else 24.0
        ridge = float(h) if h and h > eave else 0.0
        storeys = int(np.clip(round((eave - 0.3) / 2.9), 1, 20))
        rc = p.get("roof_colour") or "#606060"
        rgb = tuple(int(rc[i:i + 2], 16) for i in (1, 3, 5))
        z = p.get("ground_z_navd88")
        ground = float(z) + Z_OFFSET[world] if z is not None else -1000.0  # -1000: take the terrain's
        flags = (1 if p.get("height_source") == "lidar" else 0) | (2 if commercial else 0)
        detail = 1 if p.get("detail") == "full" else 0
        rec = [struct.pack("<6f", c[0], c[1], ground, eave, ridge, pitch),
               struct.pack("<8B", roof, detail, len(rects), storeys, rgb[0], rgb[1], rgb[2], flags)]
        for (a0, a1, b0, b1) in rects:
            um, vm = (a0 + a1) / 2, (b0 + b1) / 2
            hl, hw = (a1 - a0) / 2, (b1 - b0) / 2
            yaw = math.degrees(ang)
            if hw > hl:  # length along the rectangle's own long side
                hl, hw, yaw = hw, hl, yaw + 90.0
            rec.append(struct.pack("<5f", c[0] + um * ca - vm * sa, c[1] + um * sa + vm * ca, hl, hw, yaw))
        out.append(b"".join(rec))
        stats["rects"] += len(rects)
        stats["multi"] += len(rects) > 1
        stats["full"] += detail
        stats["lidar"] += flags & 1
    path = os.path.join(ROOT, "Content", "TerrainData", f"{world}.houses")
    with open(path, "wb") as fh:
        fh.write(b"HOUS" + struct.pack("<II", 1, len(out)))
        fh.writelines(out)
    print(f"Houses: {world} {len(out)} ({stats['full']} full detail, {stats['multi']} multi-wing, {stats['rects']} rectangles,"
          f" {stats['lidar']} lidar roofs) -> {os.path.getsize(path) / 1e6:.1f} MB")


if __name__ == "__main__":
    for w in sys.argv[1:] or ["RayHubbard"]:
        build(w)
