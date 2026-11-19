"""Track A: the layered ground material, as numpy. ground_hlsl.py is the same maths for M_Ground (written line for line
from this file: change both together; test_ground.py checks they agree on the decode and weights).

Inputs, per pixel, the same ones the terrain material has in the game:
  P       world position, metres in the map frame (+X north, +Y east, Z = 0 at the 435.5 ft pool)
  N       the mesh normal (unit, world)
  C       the terrain's vertex colour, linear RGB (LakeTerrainActor::BuildChunk: bed, bank clay/sand, low flats,
          grass to woods by canopy, bare slopes)
  Near    the vertex colour's alpha: open water within 4/8/14 m (1/0.6/0.25)
  WaterZ  the water level (pool 0; the gauge runs under it in a drought)
  Mown    0..1, mown lawn (from house and club footprints; the terrain supplies it at integration)
  Season  0 summer .. 1 dormant (game date: Dec to Mar dormant, ramps in Nov and Apr)
Outputs: base colour (linear), roughness, a world normal with the scans' relief, and the eight surface weights.

Method: eight weights from the inputs (cheap maths), the two strongest sampled from the texture arrays (each sampled
twice at unrelated scales and rotations, joined by height, so no repeat shows in a 40 m frame), the rest drawn as their
card colour, then a slow colour wash (9 m and 31 m) and the wet band. Every distance draws the same mean colour, so the
far band (no texture past 150 m) has no seam.
"""
import os

import numpy as np

import pack as packs

HERE = os.path.dirname(os.path.abspath(__file__))
IDS = packs.ROLES
S = {k: i for i, k in enumerate(IDS)}


def use_pack(name=None):
    """Load a region pack's colours, sizes and roughness into this module (the maths itself is the same everywhere)."""
    global CARD, ALB_SUMMER, ALB_DORMANT, TILE, ROUGH, DARKEN, ROUGH_WET
    CARD = packs.load(name)
    s = CARD["surfaces"]
    ALB_SUMMER = np.array([x["albedo_linear"]["summer"] for x in s], np.float32)
    ALB_DORMANT = np.array([x["albedo_linear"]["dormant"] for x in s], np.float32)
    TILE = np.array([x["tile_m"] for x in s], np.float32)
    ROUGH = np.array([x["roughness"] for x in s], np.float32)
    DARKEN = np.array([x["wet"]["darken"] for x in s], np.float32)
    ROUGH_WET = np.array([x["wet"]["rough_wet"] for x in s], np.float32)


use_pack()
# Second sample of each surface: rotated and at a scale with no small common ratio to the first (golden ratio), offset.
ROT2 = np.radians(np.array([37.0, 71.0, 113.0, 23.0, 59.0, 97.0, 41.0, 83.0], np.float32))
SCALE2 = 1.618
# Knobs (mirrored in ground_hlsl.py).
BLEND_DEPTH = 0.18        # height blend: how far (in 0..1 height) one surface can push through its neighbour
MACRO_A, MACRO_B = 0.10, 0.07     # slow wash amplitudes at 9 m and 31 m
TEXTURE_FAR_M = 150.0     # past this, card colours only (the near band's edge)
NORMAL_FADE_M = (25.0, 80.0)
# Cost bands (the Mac's world gate at 7307fe54: -9 fps on coast-day, -4 on slip at High with 12 fetches everywhere inside
# 150 m): the second, rotated scale only inside BAND_A (the hero band, where a tile's repeat would show); the height
# maps, normals and roughness (the RHA and normal arrays) only inside BAND_B; past it the two surfaces are colour only,
# mixed by their weights. Fetches per pixel: 12 inside 35 m, 6 to 75 m, 2 to 150 m, none past it.
BAND_A_M = (35.0, 45.0)
BAND_B_M = (75.0, 85.0)


def sat(x):
    return np.clip(x, 0.0, 1.0)


def smoothstep(a, b, x):
    t = sat((x - a) / (b - a))
    return t * t * (3 - 2 * t)


def hash2(ix, iy):
    return np.modf(np.abs(np.sin(ix * 127.1 + iy * 311.7) * 43758.5453))[0]


def vnoise(x, y):
    """Value noise in -1..1, smooth, period-free (the HLSL's VNoise)."""
    ix, iy = np.floor(x), np.floor(y)
    fx, fy = x - ix, y - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = hash2(ix, iy), hash2(ix + 1, iy)
    c, d = hash2(ix, iy + 1), hash2(ix + 1, iy + 1)
    return 2.0 * ((a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) * fy) - 1.0


def weights(P, N, C, Near, WaterZ, Mown):
    """The eight surface weights (sum 1), in IDS order. Pure maths on the inputs: the shader's first half."""
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    h = z - WaterZ                      # height over the water now
    slope = 1.0 - N[..., 2]
    # The patch noises' lattices are turned off the map's axes (value noise keeps its grid in its features: at 5 m the
    # PC's Ultra stills showed shingle patches with box-straight sides).
    x1, y1 = 0.8253 * x - 0.5646 * y, 0.5646 * x + 0.8253 * y      # 34.4 deg
    x3, y3 = 0.6216 * x + 0.7833 * y, -0.7833 * x + 0.6216 * y     # -51.6 deg
    n1 = vnoise(x1 / 3.1, y1 / 3.1)
    n2 = vnoise(x / 0.9 + 17.0, y / 0.9 - 5.0)
    n3 = vnoise(x3 / 11.0 - 4.0, y3 / 11.0 + 9.0)
    n4 = vnoise(x / 31.0 - 7.7, y / 31.0 + 3.1)    # round 2: a 31 m wander in every band's top, so no zone edge runs straight
    # Decode the vertex colour. Canopy: the upland tone runs (0.36,0.36,0.16) open to (0.16,0.22,0.08) under trees, so
    # red over green falls from 1 to 0.73. Sandy bank (0.50,0.42,0.30) against clay bank (0.42,0.30,0.20): green over red.
    rg = C[..., 0] / np.maximum(C[..., 1], 1e-3)
    canopy = sat((1.0 - rg) / 0.27) * smoothstep(0.4, 0.9, z)     # low flats (z < 0.6) are sedge, not woods
    sandy = sat((C[..., 1] / np.maximum(C[..., 0], 1e-3) - 0.74) / 0.10)
    w = np.zeros(P.shape[:-1] + (8,), np.float32)
    # Under water and the swash: mud. The swash top is ragged, 0.15 to 0.45 m.
    swash = (1.0 - smoothstep(0.08, 0.30 + 0.12 * n1 + 0.08 * n3, h)) * np.maximum(Near, (h < 0.05))
    # Lake bed left dry under the pool (a drought gauge): cracked crust on the flats, from 0.15 m over the water.
    dry_bed = (smoothstep(-0.02, -0.12, z + 0.06 * n3) * smoothstep(0.08, 0.22 + 0.10 * n1, h)
               * (1.0 - smoothstep(0.10, 0.25, slope)))
    # The bank: within reach of open water and under 1.5 m; sand or clay by the vertex colour, with limestone shingle
    # in patches on the wave-washed band 0.1 to 0.7 m over the water.
    top = 1.3 + 0.35 * n3 + 0.15 * n2 + 0.3 * n4   # where grass takes over: ragged, in tufts, wandering along the shore
    bank = Near * (1.0 - smoothstep(top - 0.35, top, h)) * (1.0 - dry_bed)
    shingle = (bank * smoothstep(0.05, 0.15, h) * (1.0 - smoothstep(0.5 + 0.15 * n1, 0.75, h))
               * smoothstep(0.05, 0.6, 0.6 * n1 + 0.45 * n2 + 0.4 * n3))   # round 2: a wide feather, so stones thin out at a patch's edge instead of ending on a contour (they read as grey decals)
    # Bare slopes: the same 0.08 start as BuildChunk's slope tone, eroded faces are clay.
    bare = smoothstep(0.08, 0.24, slope + 0.04 * n2) * (1.0 - swash)
    w[..., S["mud"]] = swash
    rest = 1.0 - swash
    w[..., S["cracked"]] = rest * dry_bed
    rest = rest * (1.0 - dry_bed)
    w[..., S["gravel"]] = rest * shingle
    rest = rest * (1.0 - shingle)
    soil = np.maximum(bank, bare)                   # bare ground: the bank, or an eroded face
    sand = bank * sandy * (1.0 - bare)              # faces are clay even on a sandy bank
    w[..., S["sand"]] = rest * sand
    w[..., S["clay"]] = rest * (soil - sand)
    rest = rest * (1.0 - soil)
    # Grass and woods: litter under canopy, lawn where mown, rough grass elsewhere. A mown lawn keeps a few bare and
    # weedy patches (n1), a field a few short-grazed ones.
    # Under woods the floor is litter; under a yard tree the mown grass mostly carries on, thinning.
    litter = smoothstep(0.45, 0.95, canopy + 0.2 * n2) * (1.0 - 0.6 * sat(Mown))
    lawn = (1.0 - litter) * sat(Mown) * (1.0 - 0.35 * smoothstep(0.45, 0.85, n1))
    w[..., S["litter"]] = rest * litter
    w[..., S["lawn"]] = rest * lawn
    w[..., S["rough"]] = rest * (1.0 - litter - lawn)
    w = np.maximum(w, 0.0)
    return w / np.maximum(w.sum(-1, keepdims=True), 1e-6)


def season_tint(season):
    """Per-surface colour multiplier for the season (dormant over summer), with the summer textures."""
    s = np.asarray(season, np.float32)[..., None, None]
    return 1.0 + s * (ALB_DORMANT / ALB_SUMMER - 1.0)


class TexBank:
    """The texture arrays: per surface a mip pyramid of albedo, normal XY and RHA (roughness, height, AO)."""

    def __init__(self, prep_dir, res):
        self.levels = []          # levels[surface] = list of (albedo, normal, rha) per mip
        for sid in IDS:
            d = np.load(os.path.join(prep_dir, f"{sid}_{res}.npz"))
            maps = np.concatenate([d["albedo"].astype(np.float32), d["normal"].astype(np.float32),
                                   d["rha"].astype(np.float32)], -1)     # 8 channels
            pyr = [maps]
            while pyr[-1].shape[0] > 4:
                m = pyr[-1]
                pyr.append(0.25 * (m[0::2, 0::2] + m[1::2, 0::2] + m[0::2, 1::2] + m[1::2, 1::2]))
            self.levels.append(pyr)
        self.res = res

    def sample(self, si, u, v, lod):
        """Trilinear, wrap-around. si, u, v, lod: flat arrays of the same length. Returns (n, 8)."""
        out = np.zeros((len(u), 8), np.float32)
        for s in np.unique(si):
            m = si == s
            pyr = self.levels[s]
            l = np.clip(lod[m], 0, len(pyr) - 1.001)
            l0 = np.floor(l).astype(int)
            fl = (l - l0)[:, None]
            acc = np.zeros((m.sum(), 8), np.float32)
            for k in np.unique(l0):
                mk = l0 == k
                a = self._bilinear(pyr[k], u[m][mk], v[m][mk])
                b = self._bilinear(pyr[min(k + 1, len(pyr) - 1)], u[m][mk], v[m][mk])
                acc[mk] = a + (b - a) * fl[mk]
            out[m] = acc
        return out

    @staticmethod
    def _bilinear(img, u, v):
        n = img.shape[0]
        x, y = u * n - 0.5, v * n - 0.5
        x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
        fx, fy = (x - x0)[:, None], (y - y0)[:, None]
        x0, y0 = x0 % n, y0 % n
        x1, y1 = (x0 + 1) % n, (y0 + 1) % n
        a = img[y0, x0] + (img[y0, x1] - img[y0, x0]) * fx
        b = img[y1, x0] + (img[y1, x1] - img[y1, x0]) * fx
        return a + (b - a) * fy


def shade(P, N, C, Near, WaterZ, Mown, Season, bank, footprint, cam, detail=1.0):
    """P, N, C: (n,3); Near, Mown, footprint: (n,). footprint = metres per pixel at P (the GPU's derivatives).
    Returns base colour (n,3), roughness (n,), world normal (n,3), weights (n,8)."""
    w = weights(P, N, C, Near, WaterZ, Mown)
    n = len(P)
    tint = season_tint(float(Season)).reshape(8, 3)   # (8,3)
    card = ALB_SUMMER * tint                          # card colour per surface this season
    base = w @ card
    rough = w @ ROUGH
    dist = np.linalg.norm(P - cam, axis=-1)
    textured = dist < TEXTURE_FAR_M
    nrm_t = np.zeros((n, 2), np.float32)
    ao = np.ones(n, np.float32)
    if textured.any():
        idx = np.where(textured)[0]
        order = np.argsort(-w[idx], axis=1)
        top = order[:, :2]
        x, y = P[idx, 0], P[idx, 1]
        kA = detail * (1.0 - smoothstep(BAND_A_M[0], BAND_A_M[1], dist[idx]))   # detail 0 = the High tier: no second scale
        kB = 1.0 - smoothstep(BAND_B_M[0], BAND_B_M[1], dist[idx])
        layers, heights = [], []
        for k in range(2):
            si = top[:, k]
            t = TILE[si]
            u1, v1 = x / t, y / t
            c, s_ = np.cos(ROT2[si]), np.sin(ROT2[si])
            u2 = (c * x - s_ * y) / (t * SCALE2) + 0.37 * si
            v2 = (s_ * x + c * y) / (t * SCALE2) + 0.71 * si
            lod1 = np.log2(np.maximum(footprint[idx] * bank.res / t, 1e-6))
            lod2 = lod1 - np.log2(SCALE2)
            a = bank.sample(si, u1 % 1.0, v1 % 1.0, lod1)
            b = bank.sample(si, u2 % 1.0, v2 % 1.0, lod2)
            # Join the two samples by height, steered by a slow noise so neither scale shows its own repeat.
            m = vnoise(x / 4.3 + 3.0 * si, y / 4.3 - 2.0 * si)
            j = smoothstep(-0.12, 0.12, (a[:, 6] - b[:, 6]) + 0.6 * m)[:, None]
            two = b + (a - b) * j
            layer = a + (two - a) * kA[:, None]     # the rotated scale fades out over BAND_A (the GPU stops fetching it)
            layers.append(layer)
            heights.append(layer[:, 6])
        w1 = w[idx, top[:, 0]]
        w2 = w[idx, top[:, 1]]
        # Height blend of the two: the higher surface wins near the boundary (grass through sand, stones through mud).
        h1 = heights[0] + w1
        h2 = heights[1] + w2
        hm = np.maximum(h1, h2) - BLEND_DEPTH
        b1 = np.maximum(h1 - hm, 0.0)
        b2 = np.maximum(h2 - hm, 0.0)
        tot = np.maximum(b1 + b2, 1e-6)
        b1, b2 = b1 / tot, b2 / tot
        share = w1 + w2                                 # the rest keep their card colour
        # Past BAND_B the height maps are not read: the two surfaces mix by their weights.
        wtot = np.maximum(share, 1e-6)
        b1 = w1 / wtot + (b1 - w1 / wtot) * kB
        b2 = w2 / wtot + (b2 - w2 / wtot) * kB
        t1, t2 = tint[top[:, 0]], tint[top[:, 1]]
        tex_col = layers[0][:, 0:3] * t1 * b1[:, None] + layers[1][:, 0:3] * t2 * b2[:, None]
        rough_card = ROUGH[top[:, 0]] * b1 + ROUGH[top[:, 1]] * b2
        tex_rough = rough_card + (layers[0][:, 5] * b1 + layers[1][:, 5] * b2 - rough_card) * kB
        others = base[idx] - w1[:, None] * card[top[:, 0]] - w2[:, None] * card[top[:, 1]]
        far_k = smoothstep(TEXTURE_FAR_M * 0.8, TEXTURE_FAR_M, dist[idx])[:, None]
        mix_col = tex_col * share[:, None] + others
        base[idx] = mix_col + (base[idx] - mix_col) * far_k
        others_r = rough[idx] - w1 * ROUGH[top[:, 0]] - w2 * ROUGH[top[:, 1]]
        rough[idx] = (tex_rough * share + others_r) * (1 - far_k[:, 0]) + rough[idx] * far_k[:, 0]
        nfade = (1.0 - smoothstep(NORMAL_FADE_M[0], NORMAL_FADE_M[1], dist[idx]))[:, None]
        nrm_t[idx] = (layers[0][:, 3:5] * b1[:, None] + layers[1][:, 3:5] * b2[:, None]) * share[:, None] * nfade
        ao[idx] = 1.0 + ((layers[0][:, 7] * b1 + layers[1][:, 7] * b2) - 1.0) * share * nfade[:, 0]
    # Slow wash: brightness and, on grass, a drift toward straw, so a lawn is never one colour across 40 m.
    x, y = P[:, 0], P[:, 1]
    m1 = vnoise(x / 9.0 + 5.2, y / 9.0 + 1.3)
    m2 = vnoise(x / 31.0 - 7.7, y / 31.0 + 3.1)
    base *= (1.0 + MACRO_A * m1 + MACRO_B * m2)[:, None]
    # Round 2: a cut bank's clay face carries strata, bands about 18 cm apart bent by the small noise (the scan is one even
    # texture; reviewers saw a face with no layers). Only on clay and only on the steep part.
    slope = 1.0 - N[:, 2]
    face = w[:, S["clay"]] * smoothstep(0.25, 0.5, slope)
    strata = np.sin(P[:, 2] / 0.18 * 6.2831853 + 1.5 * vnoise(x / 0.9 + 17.0, y / 0.9 - 5.0) + 0.4 * vnoise((0.8253 * x - 0.5646 * y) / 3.1, (0.5646 * x + 0.8253 * y) / 3.1))
    base *= (1.0 + 0.14 * strata * face)[:, None]
    grassy = w[:, S["lawn"]] + w[:, S["rough"]]
    straw = ALB_DORMANT[S["rough"]] / ALB_SUMMER[S["rough"]]
    dry = smoothstep(0.2, 0.9, 0.5 * m1 + 0.5 * m2 + 0.3) * 0.35 * (1.0 - np.asarray(Season))
    base *= 1.0 + (grassy * dry)[:, None] * (straw - 1.0)
    # Mowing stripes on the lawn (as today's M_Terrain: 2.5 m wide, each 40 m block mown its own way), only +-4%: the
    # light on bent blades, not paint.
    bx, by = np.floor(x / 40.0), np.floor(y / 40.0)
    ang = 6.2831853 * hash2(bx + 0.13, by + 0.71)
    stripe = np.where(((x * np.cos(ang) + y * np.sin(ang)) / 5.0) % 1.0 < 0.5, -1.0, 1.0)
    # Only where the lawn owns the ground: a half-weight lawn over a bank showed the stripes as pale columns up the soil.
    base *= (1.0 + 0.04 * stripe * smoothstep(0.55, 0.9, w[:, S["lawn"]]))[:, None]
    # The wet band (as today's M_Terrain: up the swash about half a metre, ragged) and the algae film just over the line.
    h = P[:, 2] - WaterZ
    n_ = vnoise((0.8253 * x - 0.5646 * y) / 3.1, (0.5646 * x + 0.8253 * y) / 3.1)   # = weights()' n1
    wet = (1.0 - smoothstep(0.05, 0.6 + 0.2 * n_, h)) * np.maximum(Near, h < 0.05)
    dark = w @ DARKEN
    base *= (1.0 - dark * wet)[:, None]
    # #804's rule from M_Terrain: a wet bank seen at a grazing angle glowed white; only near-flat ground keeps the wet gloss.
    rwet = w @ ROUGH_WET
    rwet = np.maximum(rwet, 0.62 + (rwet - 0.62) * smoothstep(0.88, 0.97, N[:, 2]))
    # The bed under the water is matte and flat, as M_Terrain's (wet gloss and relief there put every visible bed pixel
    # under Lumen's reflection roughness: round 4 gate).
    under = smoothstep(0.0, -0.35, h)
    rough = rough + (rwet - rough) * (wet * (1.0 - under))
    rough = rough + (0.92 - rough) * under
    nrm_t = nrm_t * (1.0 - under)[:, None]
    film = (1.0 - smoothstep(0.02, 0.10, h)) * (h > -0.05) * np.maximum(Near, h < 0.05)
    base = base + (base * np.array([0.62, 0.74, 0.46]) - base) * (film * 0.8)[:, None]
    base = base + (base * np.array([0.55, 0.6, 0.45]) - base) * under[:, None]
    # Relief: the scans' tangent normals on the mesh normal (the terrain's tangent frame is world X/Y on the slope).
    Nw = perturb(N, nrm_t)
    return base.astype(np.float32), np.clip(rough, 0.05, 1.0).astype(np.float32), Nw, w, ao


def perturb(N, nt):
    t = np.stack([np.ones(len(N)), np.zeros(len(N)), np.zeros(len(N))], -1)
    t = t - N * (N * t).sum(-1, keepdims=True)
    t /= np.linalg.norm(t, axis=-1, keepdims=True)
    b = np.cross(N, t)
    nz = np.sqrt(np.clip(1.0 - (nt ** 2).sum(-1), 0.0, 1.0))[:, None]
    out = t * nt[:, 0:1] + b * nt[:, 1:2] + N * nz
    return out / np.linalg.norm(out, axis=-1, keepdims=True)
