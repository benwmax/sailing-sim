"""Composes a streamed world from worlds already baked (World streaming, Wide World Rendering PR 2: docs/world-streaming).

A world definition with "compose" (Tools/coast/worlds/TexasCoast.json) names its members and the one whose map frame it
keeps ("frame"): that member's grid, houses, crowns, piers and tidal-current field carry over unchanged (same projection,
same metres), and the others are reprojected into it (pyproj: their tmerc -> lat/lon -> the frame's tmerc). Outputs
(Content/TerrainData):

  - <World>.tiles : the heights in square tiles ("SSTI", version 1; FTileIndex in Source/SailingPhysics/Public/WorldStream.h):
                    a 48-byte header (tile size, origin, finest spacing, tile count), one 40-byte entry per tile (row, column,
                    cells, spacing, unit, flags, min and max height, offset, stored size), then each tile's (cells + 1)^2 int16
                    heights in cm above the datum, rows north, columns east, zlib-compressed. Tiles that overlap the frame
                    member's grid are 10 m (its own nodes where it has them), the rest take the coarsest member's spacing
                    there (50 m on the Gulf). Within BLEND_M of the frame grid's edge, where another member has data, the two
                    are blended so the seam has no step. Where no member has data the ground is land (NO_DATA_M); a tile
                    with no data at all is left out (the game reads a missing tile as land too).
  - <World>.trees : tree density on the frame member's 20 m grid over the whole box (others resampled)
  - <World>.json  : the frame's metadata with every member's launch spots, checkpoints, docks, bridges, buildings, navaids,
                    landmarks and tide stations (another member's only where the frame's grid does not reach), the world's
                    passage, "tiles" (the index's numbers) and "members" (the frame member's files the game reads in place:
                    houses, crowns, piers, current).
  - <World>.chart.json : the members' vector charts merged the same way.

Run: Tools/venv/bin/python Tools/coast/build_coast.py TexasCoast   (build_coast.py hands a "compose" world to this script)
"""
import json
import math
import os
import struct
import sys
import time
import zlib

import numpy as np
from pyproj import Transformer
from scipy import ndimage

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TERRAIN = os.path.join(ROOT, "Content", "TerrainData")
TILE_M = 6400.0          # FTileIndex::kTileM
BLEND_M = 1000.0         # the frame grid fades into the next member over this, inside its edge
NO_DATA_M = 1.5          # ground where no member has data (inland, beyond the charts)
ZLIB_LEVEL = 9


def load_member(name):
    meta = json.load(open(os.path.join(TERRAIN, f"{name}.json")))
    with open(os.path.join(TERRAIN, f"{name}.height"), "rb") as fh:
        data = fh.read()
    assert data[:4] == b"SSHT", name
    _, nx, ny = struct.unpack_from("<III", data, 4)
    cell, x0, y0, unit = struct.unpack_from("<ffff", data, 16)
    h = np.frombuffer(data, dtype="<i2", count=nx * ny, offset=32).reshape(ny, nx)
    trees = None
    path = os.path.join(TERRAIN, f"{name}.trees")
    if os.path.exists(path):
        with open(path, "rb") as fh:
            t = fh.read()
        tnx, tny = struct.unpack_from("<II", t, 8)
        tcell, tx0, ty0 = struct.unpack_from("<fff", t, 16)
        trees = (np.frombuffer(t, dtype=np.uint8, count=tnx * tny, offset=28).reshape(tny, tnx), float(tcell), float(tx0), float(ty0))
    chart = json.load(open(os.path.join(TERRAIN, f"{name}.chart.json")))
    return Member(name, meta, h, float(cell), float(x0), float(y0), float(unit), trees, chart)


class Member:
    def __init__(self, name, meta, h, cell, x0, y0, unit, trees, chart):
        self.name, self.meta, self.h, self.cell, self.x0, self.y0, self.unit = name, meta, h, cell, x0, y0, unit
        self.trees, self.chart = trees, chart
        self.ny, self.nx = h.shape
        self.x1 = x0 + (self.ny - 1) * cell
        self.y1 = y0 + (self.nx - 1) * cell
        self.proj = meta["projection"]

    def inside(self, X, Y):
        return (X >= self.x0) & (X <= self.x1) & (Y >= self.y0) & (Y <= self.y1)

    def edge_distance(self, X, Y):
        """How far inside the grid's box a point is (m; negative outside)."""
        return np.minimum(np.minimum(X - self.x0, self.x1 - X), np.minimum(Y - self.y0, self.y1 - Y))

    def sample(self, X, Y):
        """Heights (m) at points of this member's own frame, bilinear (FLakeTerrain::HeightAt), clamped at the edge."""
        R = np.clip((X - self.x0) / self.cell, 0, self.ny - 1)
        C = np.clip((Y - self.y0) / self.cell, 0, self.nx - 1)
        return ndimage.map_coordinates(self.hf, [R, C], order=1, mode="nearest").astype(np.float64)

    @property
    def hf(self):
        if not hasattr(self, "_hf"):
            self._hf = self.h.astype(np.float32) * np.float32(self.unit)
        return self._hf


class Frames:
    """Points of the composed world's frame (the frame member's tmerc) into each member's frame."""

    def __init__(self, frame_proj, members):
        self.to_ll = Transformer.from_crs(frame_proj, "EPSG:4326", always_xy=True)
        self.from_ll = Transformer.from_crs("EPSG:4326", frame_proj, always_xy=True)
        self.into = {}
        for m in members:
            if m.proj == frame_proj:
                self.into[m.name] = None
            else:
                self.into[m.name] = Transformer.from_crs(frame_proj, m.proj, always_xy=True)
        self.out_of = {m.name: (None if m.proj == frame_proj else Transformer.from_crs(m.proj, frame_proj, always_xy=True)) for m in members}

    def to_member(self, m, X, Y):
        t = self.into[m.name]
        if t is None:
            return X, Y
        e, n = t.transform(Y, X)
        return np.asarray(n), np.asarray(e)

    def from_member(self, m, x, y):
        t = self.out_of[m.name]
        if t is None:
            return x, y
        e, n = t.transform(y, x)
        return float(n), float(e)

    def heading_from_member(self, m, x, y, heading):
        """A grid heading in a member's frame as one in the composed frame (the two grids' norths differ by the meridians'
        convergence between their central meridians: a few tenths of a degree)."""
        if self.out_of[m.name] is None:
            return heading
        a = math.radians(heading)
        x2, y2 = x + 100.0 * math.cos(a), y + 100.0 * math.sin(a)
        X1, Y1 = self.from_member(m, x, y)
        X2, Y2 = self.from_member(m, x2, y2)
        return (math.degrees(math.atan2(Y2 - Y1, X2 - X1)) + 360.0) % 360.0


def composite_heights(frames, frame, others, X, Y):
    """The composed ground at frame points: the frame grid where it reaches (blended into the next member over BLEND_M
    inside its edge), else the first other member with data there, else NO_DATA_M. Returns heights and a has-data mask."""
    z = np.full(X.shape, np.nan)
    have = np.zeros(X.shape, bool)
    other = np.full(X.shape, np.nan)
    for m in others:
        x, y = frames.to_member(m, X, Y)
        inside = m.inside(x, y) & ~have
        if inside.any():
            other[inside] = m.sample(x[inside], y[inside])
            have |= inside
    in_frame = frame.inside(X, Y)
    if in_frame.any():
        f = frame.sample(X[in_frame], Y[in_frame])
        w = np.clip(frame.edge_distance(X[in_frame], Y[in_frame]) / BLEND_M, 0.0, 1.0)
        o = other[in_frame]
        z[in_frame] = np.where(np.isnan(o), f, w * f + (1.0 - w) * np.nan_to_num(o))
    out = ~in_frame & have
    z[out] = other[out]
    data = in_frame | have
    z[~data] = NO_DATA_M
    return z, data


def compose(cfg):
    t0 = time.time()
    name = cfg["name"]
    members = [load_member(n) for n in cfg["compose"]]
    frame = next(m for m in members if m.name == cfg["frame"])
    others = [m for m in members if m is not frame]
    frames = Frames(frame.proj, members)

    # The tile lattice: the frame grid's origin, extended by whole tiles until every member's box is covered.
    box = [frame.x0, frame.y0, frame.x1, frame.y1]
    for m in others:
        for xx, yy in ((m.x0, m.y0), (m.x0, m.y1), (m.x1, m.y0), (m.x1, m.y1), (0.5 * (m.x0 + m.x1), m.y0), (0.5 * (m.x0 + m.x1), m.y1),
                       (m.x0, 0.5 * (m.y0 + m.y1)), (m.x1, 0.5 * (m.y0 + m.y1))):
            X, Y = frames.from_member(m, xx, yy)
            box = [min(box[0], X), min(box[1], Y), max(box[2], X), max(box[3], Y)]
    ox = frame.x0 - math.ceil((frame.x0 - box[0]) / TILE_M) * TILE_M
    oy = frame.y0 - math.ceil((frame.y0 - box[1]) / TILE_M) * TILE_M
    nr = math.ceil((box[2] - ox) / TILE_M)
    nc = math.ceil((box[3] - oy) / TILE_M)
    fine = frame.cell
    coarse = max(m.cell for m in members)
    print(f"{name}: tile lattice {nr} x {nc} of {TILE_M / 1000:.1f} km from ({ox:.0f}, {oy:.0f}); frame {frame.name} at {fine:.0f} m, others to {coarse:.0f} m")

    entries, blobs = [], []
    raw_bytes = 0
    for i in range(nr):
        for j in range(nc):
            tx0, ty0 = ox + i * TILE_M, oy + j * TILE_M
            overlaps_frame = not (tx0 > frame.x1 or tx0 + TILE_M < frame.x0 or ty0 > frame.y1 or ty0 + TILE_M < frame.y0)
            cell = fine if overlaps_frame else coarse
            n = int(round(TILE_M / cell))
            k = np.arange(n + 1) * cell
            X, Y = np.meshgrid(tx0 + k, ty0 + k, indexing="ij")
            if overlaps_frame and tx0 >= frame.x0 and ty0 >= frame.y0 and tx0 + TILE_M <= frame.x1 and ty0 + TILE_M <= frame.y1:
                # Wholly inside the frame grid: its own nodes, exactly (the bay's 10 m bake unchanged); the blend band is
                # only at the grid's edge, which this tile does not reach.
                r0, c0 = int(round((tx0 - frame.x0) / frame.cell)), int(round((ty0 - frame.y0) / frame.cell))
                q = frame.h[r0:r0 + n + 1, c0:c0 + n + 1].astype(np.int16)
                data = np.ones(q.shape, bool)
                inside_blend = frame.edge_distance(X, Y) < BLEND_M
                if inside_blend.any():
                    z, data = composite_heights(frames, frame, others, X, Y)
                    q = np.clip(np.round(z / 0.01), -32768, 32767).astype("<i2")
            else:
                z, data = composite_heights(frames, frame, others, X, Y)
                if not data.any():
                    continue
                q = np.clip(np.round(z / 0.01), -32768, 32767).astype("<i2")
            q = np.ascontiguousarray(q, dtype="<i2")
            flags = 1 | (2 if (q < 0).any() else 0) | (4 if (q > 0).any() else 0)
            blob = zlib.compress(q.tobytes(), ZLIB_LEVEL)
            raw_bytes += q.nbytes
            entries.append((i, j, n, cell, 0.01, flags, int(q.min()), int(q.max()), len(blob)))
            blobs.append(blob)
    header_size = 48 + 40 * len(entries)
    off = header_size
    head = struct.pack("<4sIIfddfIII", b"SSTI", 1, len(entries), TILE_M, ox, oy, fine, 0, 0, 0)
    assert len(head) == 48
    index = b""
    for (i, j, n, cell, unit, flags, lo, hi, size) in entries:
        index += struct.pack("<iiIffIhhQI", i, j, n, cell, unit, flags, lo, hi, off, size)
        off += size
    assert len(index) == 40 * len(entries)
    path = os.path.join(TERRAIN, f"{name}.tiles")
    with open(path, "wb") as fh:
        fh.write(head + index + b"".join(blobs))
    n_fine = sum(1 for e in entries if e[3] == fine)
    print(f"{name}.tiles: {len(entries)} tiles ({n_fine} at {fine:.0f} m, {len(entries) - n_fine} at {coarse:.0f} m), "
          f"{raw_bytes / 1e6:.1f} MB of heights in {os.path.getsize(path) / 1e6:.1f} MB")

    # Trees: the frame member's 20 m grid extended over the lattice (the others resampled, nearest).
    ftrees, tcell, tx0, ty0 = frame.trees
    TX0 = tx0 - math.ceil((tx0 - ox) / tcell) * tcell
    TY0 = ty0 - math.ceil((ty0 - oy) / tcell) * tcell
    tny = int(math.ceil((ox + nr * TILE_M - TX0) / tcell))
    tnx = int(math.ceil((oy + nc * TILE_M - TY0) / tcell))
    trees = np.zeros((tny, tnx), np.uint8)
    for m in others:
        if m.trees is None:
            continue
        mt, mcell, mx0, my0 = m.trees
        for r0 in range(0, tny, 512):
            rows = np.arange(r0, min(tny, r0 + 512))
            X, Y = np.meshgrid(TX0 + (rows + 0.5) * tcell, TY0 + (np.arange(tnx) + 0.5) * tcell, indexing="ij")
            x, y = frames.to_member(m, X, Y)
            R = np.floor((x - mx0) / mcell).astype(np.int64)
            C = np.floor((y - my0) / mcell).astype(np.int64)
            ok = (R >= 0) & (C >= 0) & (R < mt.shape[0]) & (C < mt.shape[1])
            block = trees[rows[0]:rows[-1] + 1]
            block[ok] = np.maximum(block[ok], mt[R[ok], C[ok]])
    fr0, fc0 = int(round((tx0 - TX0) / tcell)), int(round((ty0 - TY0) / tcell))
    trees[fr0:fr0 + ftrees.shape[0], fc0:fc0 + ftrees.shape[1]] = ftrees
    with open(os.path.join(TERRAIN, f"{name}.trees"), "wb") as fh:
        fh.write(b"SSTR" + struct.pack("<III", 1, tnx, tny) + struct.pack("<fff", tcell, TX0, TY0))
        fh.write(trees.tobytes())

    # Metadata: the frame's, with the others' things reprojected where the frame's grid does not reach.
    meta = dict(frame.meta)
    meta["name"] = cfg["display"]
    meta["ocean"] = cfg.get("ocean", True)
    meta["grid"] = {"rows_north": int(round(nr * TILE_M / fine)) + 1, "cols_east": int(round(nc * TILE_M / fine)) + 1, "cell_m": fine,
                    "origin_north_m": ox, "origin_east_m": oy, "height_unit_m": 0.01}
    meta["trees"] = {"rows_north": tny, "cols_east": tnx, "cell_m": tcell}
    meta["tiles"] = {"tile_m": TILE_M, "count": len(entries), "origin_north_m": ox, "origin_east_m": oy, "finest_cell_m": fine,
                     "coarse_cell_m": coarse}
    meta["members"] = {kind: frame.name for kind in ("houses", "crowns", "piers", "current")
                       if os.path.exists(os.path.join(TERRAIN, f"{frame.name}.{kind}"))}
    meta["composed_from"] = [m.name for m in members]
    meta["sources"] = {k: "; ".join(dict.fromkeys(m.meta["sources"].get(k, "") for m in members if m.meta["sources"].get(k))) for k in frame.meta["sources"]}

    def outside_frame(x, y):
        return not (frame.x0 <= x <= frame.x1 and frame.y0 <= y <= frame.y1)

    def xy_list(m, pts):
        return [[round(v, 2) for v in frames.from_member(m, p[0], p[1])] for p in pts]

    for m in others:
        mm = m.meta
        for s in mm["launch_spots"]:
            X, Y = frames.from_member(m, *s["xy"])
            meta["launch_spots"].append({**s, "xy": [round(X, 1), round(Y, 1)],
                                         "heading": round(frames.heading_from_member(m, s["xy"][0], s["xy"][1], s["heading"]), 1)})
        for c in mm["checkpoints"]:
            X, Y = frames.from_member(m, *c["shore"])
            meta["checkpoints"].append({**c, "shore": [round(X, 2), round(Y, 2)]})
        for d in mm["docks"]:
            pts = xy_list(m, d["points"])
            cx, cy = np.mean([p[0] for p in pts]), np.mean([p[1] for p in pts])
            if outside_frame(cx, cy):
                meta["docks"].append({**d, "points": pts})
        for b in mm["bridges"]:
            pts = xy_list(m, b["points"])
            cx, cy = np.mean([p[0] for p in pts]), np.mean([p[1] for p in pts])
            if outside_frame(cx, cy):
                meta["bridges"].append({**b, "points": pts})
        for b in mm["buildings"]:
            X, Y = frames.from_member(m, b[0], b[1])
            if outside_frame(X, Y):
                turn = frames.heading_from_member(m, b[0], b[1], 0.0)   # the grids' norths differ by a few tenths of a degree
                turn = turn - 360.0 if turn > 180.0 else turn
                meta["buildings"].append([round(X, 1), round(Y, 1)] + list(b[2:6]) + [round(b[6] + turn, 1)] + list(b[7:]))
        for kind in ("navaids", "landmarks"):
            for a in mm[kind]:
                X, Y = frames.from_member(m, a["x"], a["y"])
                if outside_frame(X, Y):
                    meta[kind].append({**a, "x": round(X, 2), "y": round(Y, 2)})
        have = {s["id"] for s in meta["tide_stations"]}
        for s in mm["tide_stations"]:
            if s["id"] not in have:
                X, Y = frames.from_member(m, s["x"], s["y"])
                meta["tide_stations"].append({**s, "x": round(X, 1), "y": round(Y, 1)})
    meta["passage"] = [{"name": nm, "xy": [round(v, 1) for v in ll_to_frame(frames, la, lo)]} for nm, la, lo in cfg.get("passage", [])]
    if cfg.get("launch"):
        for nm, la, lo, hd in cfg["launch"]:
            X, Y = ll_to_frame(frames, la, lo)
            meta["launch_spots"].append({"name": nm, "xy": [round(X, 1), round(Y, 1)], "heading": hd})
    with open(os.path.join(TERRAIN, f"{name}.json"), "w") as fh:
        json.dump(meta, fh, separators=(",", ":"), default=lambda o: o.item() if hasattr(o, "item") else str(o))

    # The chart: the frame's, then the others' features whose middle lies beyond the frame's grid.
    chart = {k: list(v) for k, v in frame.chart.items()}
    for m in others:
        for key, lead in (("areas", 1), ("contours", 1), ("coast", 0), ("soundings", 0), ("channels", 0), ("bridges", 1), ("docks", 1)):
            for row in m.chart.get(key, []):
                head, coords = row[:lead], row[lead:]
                if key == "soundings":
                    X, Y = frames.from_member(m, coords[0], coords[1])
                    if outside_frame(X, Y):
                        chart[key].append([round(X, 1), round(Y, 1), coords[2]])
                    continue
                pts = [frames.from_member(m, coords[k], coords[k + 1]) for k in range(0, len(coords) - 1, 2)]
                cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
                if outside_frame(cx, cy):
                    chart[key].append(head + [round(c, 1) for p in pts for c in p])
    with open(os.path.join(TERRAIN, f"{name}.chart.json"), "w") as fh:
        json.dump(chart, fh, separators=(",", ":"))
    print(f"{name}: {len(meta['launch_spots'])} launch spots, {len(meta['navaids'])} navaids, {len(meta['landmarks'])} landmarks, "
          f"{len(meta['docks'])} docks, {len(meta['tide_stations'])} tide stations; chart {len(chart['areas'])} triangles; "
          f"{time.time() - t0:.0f} s")


def ll_to_frame(frames, lat, lon):
    e, n = frames.from_ll.transform(lon, lat)
    return float(n), float(e)


if __name__ == "__main__":
    world = sys.argv[1] if len(sys.argv) > 1 else "TexasCoast"
    compose(json.load(open(os.path.join(os.path.dirname(__file__), "worlds", f"{world}.json"))))
