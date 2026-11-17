"""Read Lake Ray Hubbard's bakes outside the engine, the way the game reads them (docs/env-loop).

    from lake import Lake
    lake = Lake()                      # Content/TerrainData/RayHubbard.* (git lfs pull those first)
    lake.height_at(north, east)        # FLakeTerrain::HeightAt: the 1 m shore detail where it exists, else the 5 m grid
    lake.houses                        # the .houses bake, in the game's order (index = HouseKit's K)
    lake.lot(k)                        # HouseKit.cpp's lot dressing for house k: bank type, boathouse, the waterline

Map frame: +north, +east metres from Rush Creek Yacht Club; heights in metres above the 435.5 ft pool (water < 0).
Only numpy. Every rule here mirrors a named function in the game's code, so a station picked here lands on the same
bank in the game; when the game's rule changes, change it here too (the function names are in each docstring).
"""
import json
import math
import os
import struct
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(REPO, "Content", "TerrainData")
LAUNCH0 = (5.5, -37.5)   # launch spot 0 (RayHubbard.json): -SailingCamWorld is relative to the boat's start


def _need(path):
    with open(path, "rb") as f:
        head = f.read(64)
    if head.startswith(b"version https://git-lfs"):
        raise SystemExit(f"{os.path.relpath(path, REPO)} is a Git LFS pointer: run "
                         f"git lfs pull --include \"Content/TerrainData/RayHubbard.*\" first")
    with open(path, "rb") as f:
        return f.read()


def house_hash(k, salt):
    """HouseKit.cpp HouseHash (uint32 arithmetic)."""
    m = 0xFFFFFFFF
    h = (k * 0x9E3779B1 + salt * 0x85EBCA77) & m
    h ^= h >> 15
    h = (h * 0x2C1B3C6D) & m
    h ^= h >> 12
    h = (h * 0x297A2D39) & m
    h ^= h >> 15
    return h


def hash01(k, salt):
    """HouseKit.cpp Hash01."""
    return (house_hash(k, salt) & 0xFFFFFF) / float(0xFFFFFF)


class Lake:
    def __init__(self, world="RayHubbard"):
        self.world = world
        self.meta = json.load(open(os.path.join(DATA, world + ".json")))
        raw = _need(os.path.join(DATA, world + ".height"))
        _, _, nx, ny, cell, x0, y0, unit = struct.unpack("<4sIIIffff", raw[:32])
        g = self.meta["grid"]
        rows, cols = g["rows_north"], g["cols_east"]
        self.grid = np.frombuffer(raw[32:32 + rows * cols * 2], "<i2").reshape(rows, cols).astype(np.float32) * unit
        self.cell, self.x0, self.y0 = float(cell), float(x0), float(y0)
        # the canopy density (20 m cells), after the heights
        off = 32 + rows * cols * 2
        if raw[off:off + 4] == b"SSTR":
            _, _, tnx, tny, tcell, tx0, ty0 = struct.unpack("<4sIIIfff", raw[off:off + 28])
            t = self.meta["trees"]
            self.trees = np.frombuffer(raw[off + 28:off + 28 + t["rows_north"] * t["cols_east"]], np.uint8).reshape(t["rows_north"], t["cols_east"])
            self.tree_cell, self.tree_x0, self.tree_y0 = float(tcell), float(tx0), float(ty0)
        else:
            self.trees = None
        self._load_detail()
        self._load_houses()
        self._load_crowns()
        self.docks = self.meta.get("docks", [])
        self.bridges = self.meta.get("bridges", [])
        self.marina = json.load(open(os.path.join(DATA, world + ".marina.json"))) \
            if os.path.exists(os.path.join(DATA, world + ".marina.json")) else {}

    # --- heights -------------------------------------------------------------------------------------------------------
    def _load_detail(self):
        path = os.path.join(DATA, self.world + ".detail")
        self.detail = None
        if not os.path.exists(path):
            return
        z = _need(path)
        assert z[:4] == b"SSDZ"
        raw = zlib.decompress(z[8:])
        _, _, tile, count, cell, x0, y0, unit = struct.unpack("<4sIIIffff", raw[:32])
        idx = np.frombuffer(raw[32:32 + 8 * count], "<i4").reshape(count, 2)
        n = tile + 1
        h = np.frombuffer(raw[32 + 8 * count:32 + 8 * count + count * n * n * 2], "<i2").reshape(count, n, n)
        span = tile * cell
        rows_g, cols_g = self.grid.shape
        drows = int(math.ceil((self.x0 + (rows_g - 1) * self.cell - x0) / span)) + 1
        dcols = int(math.ceil((self.y0 + (cols_g - 1) * self.cell - y0) / span)) + 1
        index = -np.ones((drows, dcols), np.int32)
        ok = (idx[:, 0] >= 0) & (idx[:, 1] >= 0) & (idx[:, 0] < drows) & (idx[:, 1] < dcols)
        index[idx[ok, 0], idx[ok, 1]] = np.nonzero(ok)[0]
        self.detail = dict(tile=tile, cell=float(cell), x0=float(x0), y0=float(y0), unit=float(unit), index=index, h=h, span=span)

    def grid_at(self, x, y):
        """FLakeTerrain::GroundAt on the whole grid (bilinear, clamped)."""
        x, y = np.asarray(x, float), np.asarray(y, float)
        r, c = (x - self.x0) / self.cell, (y - self.y0) / self.cell
        r0, c0 = np.floor(r).astype(int), np.floor(c).astype(int)
        fr, fc = r - r0, c - c0
        R, C = self.grid.shape

        def node(a, b):
            return self.grid[np.clip(a, 0, R - 1), np.clip(b, 0, C - 1)]
        return (node(r0, c0) * (1 - fc) + node(r0, c0 + 1) * fc) * (1 - fr) + (node(r0 + 1, c0) * (1 - fc) + node(r0 + 1, c0 + 1) * fc) * fr

    def height_at(self, x, y):
        """FLakeTerrain::HeightAt: DetailHeightAt where a 1 m shore tile exists, else the 5 m grid (pool level)."""
        x, y = np.broadcast_arrays(np.asarray(x, float), np.asarray(y, float))
        out = self.grid_at(x, y).astype(float)
        d = self.detail
        if d is None:
            return out
        tx, ty = (x - d["x0"]) / d["span"], (y - d["y0"]) / d["span"]
        inside = (tx >= 0) & (ty >= 0) & (tx < d["index"].shape[0]) & (ty < d["index"].shape[1])
        R = np.where(inside, tx, 0).astype(int)
        C = np.where(inside, ty, 0).astype(int)
        k = np.where(inside, d["index"][R, C], -1)
        has = k >= 0
        if not has.any():
            return out
        u = (tx - R) * d["tile"]
        v = (ty - C) * d["tile"]
        r0 = np.minimum(u.astype(int), d["tile"] - 1)
        c0 = np.minimum(v.astype(int), d["tile"] - 1)
        fr, fc = u - r0, v - c0
        kk = np.where(has, k, 0)
        H = d["h"]
        h00, h01 = H[kk, r0, c0], H[kk, r0, c0 + 1]
        h10, h11 = H[kk, r0 + 1, c0], H[kk, r0 + 1, c0 + 1]
        fine = ((h00 * (1 - fc) + h01 * fc) * (1 - fr) + (h10 * (1 - fc) + h11 * fc) * fr) * d["unit"]
        return np.where(has, fine, out)

    def tree_density(self, x, y):
        """The 20 m canopy map (0..255), nearest cell."""
        if self.trees is None:
            return 0
        r = int((x - self.tree_x0) / self.tree_cell)
        c = int((y - self.tree_y0) / self.tree_cell)
        if 0 <= r < self.trees.shape[0] and 0 <= c < self.trees.shape[1]:
            return int(self.trees[r, c])
        return 0

    # --- houses (LakeData.cpp LoadHouses, HouseKit.cpp BuildHouseGeometry) --------------------------------------------------
    def _load_houses(self):
        raw = _need(os.path.join(DATA, self.world + ".houses"))
        assert raw[:4] == b"HOUS"
        _, count = struct.unpack("<II", raw[4:12])
        at, out = 12, []
        for _ in range(count):
            if at + 32 > len(raw):
                break
            x, y, ground, eave, ridge, pitch = struct.unpack("<6f", raw[at:at + 24])
            b = raw[at + 24:at + 32]
            at += 32
            wings = []
            for _w in range(b[2]):
                wings.append(struct.unpack("<5f", raw[at:at + 20]))
                at += 20
            if wings:   # LoadHouses keeps only houses with wings, so K counts those
                out.append(dict(x=x, y=y, ground=ground, eave=eave, ridge=ridge, pitch=pitch, roof=min(b[0], 3), full=b[1] != 0,
                                storeys=max(1, b[3]), roof_rgb=(b[4], b[5], b[6]), lidar=bool(b[7] & 1), commercial=bool(b[7] & 2),
                                wings=wings))
        self.houses = out
        self.house_xy = np.array([(h["x"], h["y"]) for h in out]) if out else np.zeros((0, 2))

    def _load_crowns(self):
        path = os.path.join(DATA, self.world + ".crowns")
        self.crowns = np.zeros((0, 5))
        if not os.path.exists(path):
            return
        raw = _need(path)
        assert raw[:4] == b"CROW"
        _, count = struct.unpack("<II", raw[4:12])
        rec = np.dtype([("n", "<f4"), ("e", "<f4"), ("g", "<f4"), ("h", "<f4"), ("r", "<f4"), ("sp", "u1"), ("full", "u1"), ("w", "u1"), ("pad", "u1")])
        a = np.frombuffer(raw[12:12 + count * rec.itemsize], rec)
        self.crowns = np.stack([a["n"], a["e"], a["g"], a["h"], a["r"]], 1).astype(float)

    def houses_near(self, x, y, r):
        if not len(self.house_xy):
            return []
        d = np.hypot(self.house_xy[:, 0] - x, self.house_xy[:, 1] - y)
        return [int(i) for i in np.nonzero(d < r)[0]]

    def crowns_near(self, x, y, r):
        if not len(self.crowns):
            return 0
        return int((np.hypot(self.crowns[:, 0] - x, self.crowns[:, 1] - y) < r).sum())

    def _in_marina_building(self, h):
        """HouseTiles: the marina actor draws the club's own buildings."""
        for b in self.marina.get("buildings", []):
            if math.hypot(b["center"][0] - h["x"], b["center"][1] - h["y"]) < 0.5 * math.hypot(*b["size"]) + 5.0:
                return True
        return False

    def lot(self, k):
        """HouseKit.cpp BuildHouseGeometry's lot round full-detail house k: None if it has no lot, else a dict with
        bank ('bulkhead' | 'riprap' | 'natural'), water (unit vector toward the lake), shore (m from the house centre to
        the first wet ground straight out), line (the waterline points along the lot), boathouse (bool) and its
        slip point. Mirrors: Street search, Front, Shore march, the waterline Line, Edge = Hash01(K, 51), the boathouse
        rule Hash01(K, 54) <= 0.35, no map dock within 30 m, 0.7 m of water 10 m out."""
        h = self.houses[k]
        if not h["full"] or self._in_marina_building(h):
            return None
        storeys = h["storeys"]
        if h["commercial"] or storeys >= 4:
            return None
        cx, cy = h["x"], h["y"]
        wings = []
        for (wx, wy, hl, hw, yaw) in h["wings"]:
            a = math.radians(yaw)
            wings.append(((wx, wy), (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a)), hl, hw))
        street = (-wings[0][2][0], -wings[0][2][1])
        found = False
        R = 25.0
        while R <= 400.0 and not found:
            for A in range(16):
                d = (math.cos(A * math.pi / 8), math.sin(A * math.pi / 8))
                if self.height_at(cx + R * d[0], cy + R * d[1]) < -0.3:
                    street = (-d[0], -d[1])
                    found = True
                    break
            R += 25.0
        water = (-street[0], -street[1])
        across = (-street[1], street[0])
        front = side_w = 0.0
        for (c, u, v, hl, hw) in wings:
            for cn in range(4):
                a = hl if cn & 1 else -hl
                b = hw if cn & 2 else -hw
                p = (c[0] + u[0] * a + v[0] * b - cx, c[1] + u[1] * a + v[1] * b - cy)
                front = max(front, p[0] * water[0] + p[1] * water[1])
                side_w = max(side_w, abs(p[0] * across[0] + p[1] * across[1]))
        shore = -1.0
        D = front + 2.0
        while D < front + 70.0:
            if self.height_at(cx + water[0] * D, cy + water[1] * D) < -0.05:
                shore = D
                break
            D += 1.0
        if shore < 0:
            return dict(k=k, bank=None, water=water, shore=None, line=[], boathouse=False)
        half = min(max(side_w + 5.0, 8.0), 18.0)
        line = []
        S = -half
        while S <= half + 0.01:
            D = shore - 10.0
            while D < shore + 10.0:
                px, py = cx + across[0] * S + water[0] * D, cy + across[1] * S + water[1] * D
                if self.height_at(px, py) < -0.02:
                    line.append((px, py))
                    break
                D += 0.5
            S += 2.0
        edge = hash01(k, 51)
        if len(line) < 3 or edge > 0.85:
            bank = "natural"
        else:
            bank = "bulkhead" if edge < 0.55 else "riprap"
        boathouse, slip = False, None
        if bank != "natural" and hash01(k, 54) <= 0.35:
            sp = line[len(line) // 2]
            docked = any((p[0] - sp[0]) ** 2 + (p[1] - sp[1]) ** 2 < 900.0 for dk in self.docks for p in dk["points"])
            deep = (sp[0] + water[0] * 10.0, sp[1] + water[1] * 10.0)
            if not docked and self.height_at(*deep) <= -0.7:
                boathouse, slip = True, sp
        return dict(k=k, bank=bank, water=water, shore=shore, line=line, boathouse=boathouse, slip=slip,
                    house=(cx, cy), wall=("brick", "siding", "stucco")[0 if hash01(k, 1) < 0.5 else (1 if hash01(k, 1) < 0.78 else 2)])
