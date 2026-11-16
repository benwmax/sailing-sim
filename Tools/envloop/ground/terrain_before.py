"""Track A: today's M_Terrain (scripts/make_materials.py build_terrain, main 4320a45), line for line in numpy, for the
"before" renders. The lake's branch only (Land = 0). P in metres here (the HLSL's p = P * 0.01)."""
import numpy as np


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def shade(P, C, CA, WaterZ, cam):
    px, py, pz = P[:, 0], P[:, 1], P[:, 2]
    n = np.sin(px * 0.11 + np.sin(py * 0.07) * 2.0) * np.sin(py * 0.13 + np.sin(px * 0.05) * 2.0)
    m = np.sin(px * 1.3 + py * 0.7) * np.sin(py * 1.7 - px * 0.4)
    f = np.sin(px * 4.1 + np.sin(py * 3.3) * 1.7) * np.sin(py * 4.7 + np.sin(px * 2.9) * 1.9) * np.sin(px * 9.3 - py * 7.1)
    col = C * ((0.88 + 0.12 * n + 0.05 * m) * (0.93 + 0.07 * f))[:, None]
    h = pz - WaterZ
    grassK = np.clip((C[:, 1] - C[:, 0]) * 30.0, 0, 1) * smoothstep(0.8, 1.4, h)
    bx, by = np.floor(px / 40.0), np.floor(py / 40.0)
    ang = 6.2831853 * np.modf(np.abs(np.sin(bx * 41.3 + by * 97.1) * 43758.5))[0]
    stripe = (np.modf((px * np.cos(ang) + py * np.sin(ang)) / 5.0)[0] % 1.0 >= 0.5).astype(np.float32)
    dry = smoothstep(0.35, 0.85, 0.5 + 0.5 * np.sin(px * 0.31 + np.sin(py * 0.23) * 2.3) * np.sin(py * 0.37 + np.sin(px * 0.19) * 1.9) + 0.15 * f)
    lawn = col * (0.94 + 0.12 * stripe)[:, None]
    lawn = lawn + (lawn * np.array([1.25, 1.12, 0.7]) - lawn) * (dry * 0.55)[:, None]
    col = col + (lawn - col) * grassK[:, None]
    wet = (1.0 - smoothstep(0.05, 0.6 + 0.2 * n + 0.08 * f, h)) * CA
    under = smoothstep(0.0, -0.35, h)
    col = col + (col * 0.5 - col) * wet[:, None]
    film = (1.0 - smoothstep(0.02, 0.10 + 0.04 * f, h)) * (h >= -0.05) * CA
    col = col + (col * np.array([0.62, 0.74, 0.46]) - col) * (film * 0.8)[:, None]
    col = col + (col * np.array([0.55, 0.6, 0.45]) - col) * under[:, None]
    rough = 0.92 + (0.32 - 0.92) * wet * (1.0 - under)
    dist = np.linalg.norm(P - cam, axis=-1)
    bandTop = 0.95 + 0.3 * n + 0.12 * m
    lumC = C @ np.array([0.3, 0.59, 0.11])
    soil = 1.0 - np.clip((lumC - 0.38) * 6.0, 0, 1)
    rank = CA * soil * (h >= -0.03) * (1.0 - smoothstep(bandTop - 0.3, bandTop, h)) * smoothstep(180.0, 260.0, dist)
    clump = 0.5 + 0.5 * np.sin(px * 0.9 + np.sin(py * 0.6) * 2.0) * np.sin(py * 1.1 + np.sin(px * 0.7) * 2.0)
    weed = np.array([0.045, 0.062, 0.022]) + (np.array([0.12, 0.105, 0.05]) - np.array([0.045, 0.062, 0.022])) * np.clip(0.65 * clump + 0.2 * f + 0.1, 0, 1)[:, None]
    cover = rank * smoothstep(-0.55, -0.1, n + 0.4 * m) * (0.75 + 0.25 * np.clip(n + 0.6, 0, 1))
    col = col + (weed - col) * cover[:, None]
    rough = rough + (0.95 - rough) * cover
    return col.astype(np.float32), rough.astype(np.float32)
