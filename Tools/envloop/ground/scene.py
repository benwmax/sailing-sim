"""Track A: a synthetic 160 m stretch of Lake Ray Hubbard shore for rendering the ground material outside the engine.

Three kinds of bank side by side, the ones Track 0's stations cover:
  west  (x < -30)   the club: a sandy-clay beach and mown lawn rising gently (club lawn, club beach stations)
  middle            a natural clay cut bank 2.5 m high with rough grass above and a wood (natural bank, wooded bank)
  east  (x > 25)    a low cove: lake bed left dry at the gauge, sedge flats, a mown yard further back (residential)
Heights are a 1 m grid, as LakeTerrainActor meshes the shore band (Step 0); the vertex colour, Near (alpha) and the
normals follow LakeTerrainActor::BuildChunk exactly for the non-garrigue lake (5 m colour cells, the 4/8/14 m water
search against the pool). x runs along the shore (east), y inland (north); the water is at y < 0.
"""
import numpy as np

CELL = 1.0
X0, X1, Y0, Y1 = -110.0, 110.0, -90.0, 90.0
GRID_CELL = 5.0          # the 5 m grid whose cells carry the colour noise
POOL = 0.0
GAUGE = -0.45            # the November 2026 gauge, about 0.45 m under the pool


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def hash01(seed):
    """LakeTerrainActor's Rand01 is a 32-bit integer hash; any uniform hash keyed the same way serves here."""
    s = (np.asarray(seed, np.int64) * 0x9E3779B1) & 0xFFFFFFFF
    s ^= s >> 16
    s = (s * 0x85EBCA6B) & 0xFFFFFFFF
    s ^= s >> 13
    s = (s * 0xC2B2AE35) & 0xFFFFFFFF
    s ^= s >> 16
    return (s & 0xFFFFFF) / float(0xFFFFFF)


def shoreline(x):
    return 3.0 * np.sin(x / 23.0) + 1.6 * np.sin(x / 7.3 + 1.0) + 0.5 * np.sin(x / 2.9)


def height(x, y):
    d = y - shoreline(x)                       # metres inland from the pool line
    west = 1.0 - smoothstep(-40.0, -22.0, x)
    east = smoothstep(18.0, 34.0, x)
    mid = 1.0 - west - east
    # Below the pool: a gentle bed, flatter in the cove (that is what the drought uncovers).
    bed = np.where(d < 0, d / (8.0 * (1 - east) + 22.0 * east), 0.0)
    # Club: 1:7 beach to 1.1 m, then a lawn at 1:45.
    club = np.clip(d, 0, None) / 7.0
    club = np.minimum(club, 1.1) + np.clip(d - 7.7, 0, None) / 45.0
    # Cut bank: a 2.4 m face over 3.5 m (slumped at its foot), then a 1:25 field.
    cut = 2.4 * smoothstep(0.3, 3.8, d) + np.clip(d - 3.8, 0, None) / 25.0 + 0.15 * np.sin(x / 4.0) * smoothstep(0.3, 3.8, d)
    # Cove: sedge flats 0 to 0.6 m over 20 m, then up 1:12 to a yard.
    cove = np.clip(d, 0, None) * 0.03 + np.clip(d - 20.0, 0, None) / 12.0
    cove = np.minimum(cove, 2.5) + np.clip(d - 42.0, 0, None) / 60.0
    land = west * club + mid * cut + east * cove
    bumps = 0.06 * np.sin(x * 0.9 + np.sin(y * 0.7)) * np.sin(y * 1.1) * smoothstep(0.0, 2.0, d)
    return np.where(d < 0, bed, land) + bumps


def canopy(x, y):
    """Lidar canopy height / 12 (BuildChunk's Canopy): a wood on the cut bank's top, a few yard trees."""
    d = y - shoreline(x)
    wood = smoothstep(-8.0, -2.0, x) * (1 - smoothstep(14.0, 22.0, x)) * smoothstep(6.0, 12.0, d) * (1 - smoothstep(55.0, 70.0, d))
    blobs = 0.0
    for cx, cy, r in [(-60.0, 34.0, 6.0), (-78.0, 22.0, 5.0), (52.0, 46.0, 7.0), (70.0, 38.0, 5.0)]:
        blobs = np.maximum(blobs, 1 - smoothstep(r * 0.6, r, np.hypot(x - cx, y - cy)))
    return np.clip(np.maximum(wood, blobs), 0, 1)


def mown(x, y):
    """The Mown mask (integration: from house and club footprints): the club lawn and an east yard."""
    d = y - shoreline(x)
    club = (1 - smoothstep(-34.0, -26.0, x)) * smoothstep(5.0, 8.0, d)
    yard = smoothstep(40.0, 46.0, x) * smoothstep(26.0, 30.0, d)
    return np.clip(club + yard, 0, 1)


class Scene:
    def __init__(self, water=GAUGE, bank_noise="cell"):
        xs = np.arange(X0, X1 + CELL / 2, CELL)
        ys = np.arange(Y0, Y1 + CELL / 2, CELL)
        self.xs, self.ys = xs, ys
        X, Y = np.meshgrid(xs, ys, indexing="ij")
        self.H = height(X, Y)
        self.water = water
        dzx, dzy = np.gradient(self.H, CELL)
        nrm = np.stack([-dzx, -dzy, np.ones_like(self.H)], -1)
        self.N = nrm / np.linalg.norm(nrm, axis=-1, keepdims=True)
        self.C, self.A = self._vertex_colours(X, Y, bank_noise)
        self.Mown = mown(X, Y)

    def _vertex_colours(self, X, Y, bank_noise):
        """LakeTerrainActor::BuildChunk, the lake's branch (not the garrigue)."""
        Z = self.H
        slope = 1.0 - self.N[..., 2]
        can = canopy(X, Y)
        gr = np.floor((X - X0) / GRID_CELL).astype(np.int64)
        gc = np.floor((Y - Y0) / GRID_CELL).astype(np.int64)
        noise = 0.9 + 0.2 * hash01(gr * 7919 + gc * 104729)
        near = np.where(Z < -0.3, 1.0, 0.0)
        for radius, weight in [(4.0, 1.0), (8.0, 0.6), (14.0, 0.25)]:
            hit = np.zeros_like(Z, bool)
            for a in range(8):
                ang = a * np.pi / 4
                hit |= self.height_at(X + radius * np.cos(ang), Y + radius * np.sin(ang)) < -0.05
            band = (Z >= -0.3) & (Z < 1.5) & (near == 0) & hit
            near = np.where(band, weight, near)
        if bank_noise == "cell":
            r = hash01(gr * 31 + gc * 17)
        else:   # the proposed integration change: sand and clay in 20-40 m stretches, not 5 m squares
            r = np.clip(0.5 + 0.5 * np.sin(X / 13.0 + 0.6 * np.sin(Y / 9.0)) * np.sin(X / 31.0 + 1.3), 0, 1)
        bank = (np.array([0.42, 0.30, 0.20]) + (np.array([0.50, 0.42, 0.30]) - np.array([0.42, 0.30, 0.20])) * r[..., None])
        low = np.array([0.24, 0.28, 0.12]) + (bank - np.array([0.24, 0.28, 0.12])) * near[..., None]
        up = np.array([0.36, 0.36, 0.16]) + (np.array([0.16, 0.22, 0.08]) - np.array([0.36, 0.36, 0.16])) * can[..., None]
        col = np.where((Z < -0.3)[..., None], np.array([0.20, 0.17, 0.12]), np.where((Z < 0.6)[..., None], low, up))
        sk = np.clip((slope - 0.08) * 6.0, 0, 1)[..., None]
        col = np.where((slope > 0.08)[..., None], col + (np.array([0.40, 0.33, 0.27]) - col) * sk, col)
        return col * noise[..., None], near

    def height_at(self, x, y):
        return self._bilinear(self.H, x, y)

    def _bilinear(self, F, x, y):
        fx = np.clip((x - X0) / CELL, 0, len(self.xs) - 1.001)
        fy = np.clip((y - Y0) / CELL, 0, len(self.ys) - 1.001)
        i, j = np.floor(fx).astype(int), np.floor(fy).astype(int)
        tx, ty = fx - i, fy - j
        if F.ndim == 3:
            tx, ty = tx[..., None], ty[..., None]
        a = F[i, j] + (F[i + 1, j] - F[i, j]) * tx
        b = F[i, j + 1] + (F[i + 1, j + 1] - F[i, j + 1]) * tx
        return a + (b - a) * ty

    def attributes(self, x, y):
        """Interpolated vertex attributes at points on the mesh (as the GPU interpolates them)."""
        n = self._bilinear(self.N, x, y)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        return dict(N=n, C=self._bilinear(self.C, x, y), Near=self._bilinear(self.A, x, y),
                    Mown=self._bilinear(self.Mown, x, y), Z=self.height_at(x, y))
