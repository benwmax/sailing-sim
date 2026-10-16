"""Water W3: a SWAN bake of the game's two inland waters (Lake Ray Hubbard and Galveston Bay) on a 50 m grid, 16 wind
directions x 7 speeds, for comparison with the game's fetch-law chop (FWaveField::TargetSignificantHeight along
FLakeTerrain::FetchToward). Resumable: each case runs in its own folder and is skipped once its output exists, so a
restart loses at most the case in flight. Runs under Linux (WSL) with numpy and scipy; SWAN built from source.

Usage (WSL):  python3 Tools/water/swan_bake.py prepare|run|collect [--world RayHubbard|GalvestonBay] [--swan /opt/swan/src/build/bin/swan.exe]
              [--work /root/swan-runs] [--only 270:14,292.5:14] [--jobs 5] [--reverse]
  prepare  resamples each world's height grid to 50 m bottom files and picks the 10 spectrum points
  run      runs every case not yet done (or --only <dir deg>:<speed kn>,...); --jobs N runs N cases at once (this SWAN
           build uses one core per case whatever --threads says; about 4 GB each), --reverse from the end of the list
  collect  reads every finished case into <work>/<world>/summary.npz (Hs, Tp, Dir, Dspr grids; point spectra)"""
import argparse
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TERRAIN = os.path.join(ROOT, "Content", "TerrainData")
DIRS = [22.5 * k for k in range(16)]                 # wind from, degrees true (nautical)
SPEEDS_KN = [5, 8, 11, 14, 18, 22, 28]
KN = 0.514444
CELL = 50.0
# Water level used for the depths: Ray Hubbard at its 435.5 ft pool (the game's Z = 0); Galveston Bay at mean tide level
# (the grid is metres above MLLW; half the bay's MHW above MLLW).
WORLDS = ("RayHubbard", "GalvestonBay")


def read_height(world):
    with open(os.path.join(TERRAIN, f"{world}.height"), "rb") as f:
        data = f.read()
    assert data[:4] == b"SSHT"
    version, nx, ny = struct.unpack_from("<3I", data, 4)
    cell, ox, oy, unit = struct.unpack_from("<4f", data, 16)
    h = np.frombuffer(data, dtype="<i2", count=nx * ny, offset=32).reshape(ny, nx).astype(np.float32) * unit
    return h, cell, ox, oy   # h[row north, col east] metres; origin north ox, east oy


def water_level(world):
    if world == "GalvestonBay":
        meta = json.load(open(os.path.join(TERRAIN, f"{world}.json"), encoding="utf-8"))
        return 0.5 * float(meta.get("mhw_m", 0.4))
    return 0.0


def fetch_law_hs(u, fetch):
    """FWaveField::TargetSignificantHeight (deep-water fetch-limited growth, capped at full development)."""
    g = 9.80665
    u2 = np.maximum(u * u, 1e-6)
    return np.minimum(0.0016 * np.sqrt(g * fetch / u2), 0.243) * u2 / g


def fetch_law_tp(u, fetch):
    g = 9.80665
    return np.maximum(np.minimum(0.286 * np.cbrt(g * fetch / (u * u)), 8.13) * u / g, 0.6)


def game_fetch(h, cell, ox, oy, xs, ys, from_deg, max_m=15000.0):
    """FLakeTerrain::FetchToward on the game's own grid: march upwind one cell at a time until land (height > level)."""
    a = math.radians(from_deg)
    dx, dy = math.cos(a), math.sin(a)          # +X north, +Y east
    fetch = np.full(xs.shape, max_m)
    alive = np.ones(xs.shape, bool)
    ny, nx = h.shape
    s = cell
    while s < max_m and alive.any():
        r = np.round((xs + dx * s - ox) / cell).astype(int)
        c = np.round((ys + dy * s - oy) / cell).astype(int)
        inside = (r >= 0) & (r < ny) & (c >= 0) & (c < nx)
        land = np.zeros(xs.shape, bool)
        land[inside] = h[r[inside], c[inside]] > 0.0
        hit = alive & land
        fetch[hit] = s
        alive &= ~hit
        s += cell
    return fetch


def prepare(work, world):
    h, cell, ox, oy = read_height(world)
    level = water_level(world)
    k = int(round(CELL / cell))
    ny, nx = (h.shape[0] // k) * k, (h.shape[1] // k) * k
    blocks = (h[:ny, :nx] - level).reshape(ny // k, k, nx // k, k)
    # A 50 m cell is water if most of it is; its depth is the mean over its water.
    wet = (blocks < 0).mean(axis=(1, 3))
    depth = np.where(blocks < 0, -blocks, np.nan)
    with np.errstate(invalid="ignore"):
        d = np.nanmean(depth, axis=(1, 3))
    d = np.where(wet >= 0.5, np.maximum(d, 0.3), -9.0)   # SWAN: depth positive down; land as the exception value
    out = os.path.join(work, world)
    os.makedirs(out, exist_ok=True)
    # SWAN reads rows from the first line as the lowest y (IDLA 3 with the grid's origin at the south-west corner).
    np.savetxt(os.path.join(out, "bottom.dat"), d, fmt="%.2f")
    meta = json.load(open(os.path.join(TERRAIN, f"{world}.json"), encoding="utf-8"))
    pts = pick_points(meta, d, ox, oy, k * cell)
    grid = dict(rows=d.shape[0], cols=d.shape[1], cell=k * cell, origin_north=ox + 0.5 * (k - 1) * cell,
                origin_east=oy + 0.5 * (k - 1) * cell, level=level, points=pts)
    json.dump(grid, open(os.path.join(out, "grid.json"), "w"), indent=1)
    print(f"{world}: {d.shape[0]} x {d.shape[1]} cells of {k * cell:.0f} m, {int((d > 0).sum())} wet; points: {[p['name'] for p in pts]}")


def pick_points(meta, d, ox, oy, cell):
    """Ten spectrum points: the world's launch spots and checkpoints first (names from the bake), then open water."""
    cands = []
    for key in ("launch_spots", "checkpoints"):
        for s in meta.get(key, []):
            p = s.get("xy") or s.get("shore")   # [north m, east m] in the map frame
            if not p:
                continue
            cands.append((str(s.get("name", key)), float(p[0]), float(p[1])))
    pts = []
    for name, x, y in cands:
        r, c = int(round((x - ox) / cell)), int(round((y - oy) / cell))
        # Step out to the nearest cell at least 2 m deep (a launch spot sits at a dock).
        best = None
        for rr in range(max(0, r - 12), min(d.shape[0], r + 13)):
            for cc in range(max(0, c - 12), min(d.shape[1], c + 13)):
                if d[rr, cc] >= 2.0:
                    dist = (rr - r) ** 2 + (cc - c) ** 2
                    if best is None or dist < best[0]:
                        best = (dist, rr, cc)
        if best and all(abs(p["row"] - best[1]) + abs(p["col"] - best[2]) > 8 for p in pts):
            pts.append(dict(name=name, row=best[1], col=best[2], north=ox + best[1] * cell, east=oy + best[2] * cell))
        if len(pts) == 10:
            break
    # Fill with the deepest open-water cells spread across the grid.
    order = np.argsort(-np.where(d > 0, d, -1).ravel())
    for idx in order:
        if len(pts) >= 10:
            break
        rr, cc = divmod(int(idx), d.shape[1])
        if all(abs(p["row"] - rr) + abs(p["col"] - cc) > d.shape[0] // 6 for p in pts):
            pts.append(dict(name=f"open-{len(pts)}", row=rr, col=cc, north=ox + rr * cell, east=oy + cc * cell))
    return pts


SWN = """PROJECT '{world}' 'W3'
SET LEVEL=0.0 NAUTICAL
MODE STATIONARY TWODIMENSIONAL
COORDINATES CARTESIAN
CGRID REGULAR {x0} {y0} 0.0 {xlen} {ylen} {mx} {my} CIRCLE 36 0.08 3.0 40
INPGRID BOTTOM REGULAR {x0} {y0} 0.0 {mx} {my} {cell} {cell} EXCEPTION -9.0
READINP BOTTOM 1.0 '../bottom.dat' 3 0 FREE
WIND {u:.3f} {dirn:.1f}
GEN3 WESTHUYSEN
BREAKING
FRICTION JONSWAP CONSTANT 0.038
TRIAD
NUM STOPC 0.005 0.01 0.005 99.5 STAT 40 0.01
BLOCK 'COMPGRID' NOHEADER 'grid.mat' LAY-OUT 3 HSIGN RTP DIR DSPR DEPTH
POINTS 'P' FILE '../points.loc'
SPECOUT 'P' SPEC2D ABS 'spec.txt'
TABLE 'P' HEADER 'points.tab' HSIGN RTP DIR DSPR
COMPUTE
STOP
"""


def case_dir(work, world, d, kn):
    return os.path.join(work, world, f"d{int(round(d * 10)):04d}_u{kn:02d}")


def claim(path):
    """Takes the claim file (holding this process's id); one whose process has gone (a killed runner) is taken over."""
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            try:
                os.kill(int(open(path).read().strip() or 0), 0)
                return False   # its runner is alive
            except (ProcessLookupError, ValueError):
                os.remove(path)
            except PermissionError:
                return False
    return False


def run_case(work, world, swan, d, kn, threads, grid):
    """One case, solved in a private folder (<case>.tmp) and moved into place when it's done. Claimed with an exclusive
    <case>.claim file so parallel runners (--jobs, or several run commands) never solve the same case; a case folder that
    exists without "done" is a runner without claims at work there (one from before --jobs), and is left to it."""
    cd = case_dir(work, world, d, kn)
    if os.path.exists(os.path.join(cd, "done")) or os.path.isdir(cd):
        return
    if not claim(cd + ".claim"):
        return
    tmp = cd + ".tmp"
    try:
        if os.path.isdir(tmp):
            shutil.rmtree(tmp)   # a case cut short by a restart
        os.makedirs(tmp)
        cell, rows, cols = grid
        with open(os.path.join(tmp, "INPUT"), "w") as f:
            f.write(SWN.format(world=world[:16], tag=os.path.basename(cd), x0=0.0, y0=0.0, xlen=(cols - 1) * cell, ylen=(rows - 1) * cell,
                               mx=cols - 1, my=rows - 1, cell=cell, u=kn * KN, dirn=d))
        env = dict(os.environ, OMP_NUM_THREADS=str(threads))
        t0 = time.time()
        r = subprocess.run([swan], cwd=tmp, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        ok = r.returncode == 0 and os.path.exists(os.path.join(tmp, "grid.mat"))
        err = open(os.path.join(tmp, "Errfile")).read() if os.path.exists(os.path.join(tmp, "Errfile")) else ""
        if not ok or "Error" in err:
            print(f"{world} {d:5.1f} deg {kn:2d} kn: FAILED (exit {r.returncode}) {err[:300]}", flush=True)
            return
        if os.path.isdir(cd):
            print(f"{world} {d:5.1f} deg {kn:2d} kn: solved, but another runner started it meanwhile; kept theirs", flush=True)
            return
        open(os.path.join(tmp, "done"), "w").write(f"{time.time() - t0:.0f} s\n")
        os.rename(tmp, cd)
        print(f"{world} {d:5.1f} deg {kn:2d} kn: {time.time() - t0:.0f} s", flush=True)
    finally:
        if os.path.isdir(tmp):
            shutil.rmtree(tmp, ignore_errors=True)
        os.remove(cd + ".claim")


def run(work, world, swan, only, threads, jobs=1, reverse=False):
    """Every case not yet done. SWAN as built here runs on one core whatever OMP_NUM_THREADS says, so --jobs N runs N
    cases at once (about 4 GB each)."""
    base = os.path.join(work, world)
    g = json.load(open(os.path.join(base, "grid.json")))
    cell, rows, cols = g["cell"], g["rows"], g["cols"]
    with open(os.path.join(base, "points.loc"), "w") as f:
        for p in g["points"]:
            f.write(f"{p['col'] * cell:.1f} {p['row'] * cell:.1f}\n")
    cases = [(d, kn) for kn in SPEEDS_KN for d in DIRS]
    if only:
        cases = [(float(dd), int(kk)) for dd, kk in (o.split(":") for o in only.split(","))]
    if reverse:
        cases.reverse()   # from the far end of the list, to share a bake with a runner going forward
    # Each case folder (and its .tmp sibling) reads the bottom and the spectrum points from one level up (../bottom.dat).
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        for fut in [pool.submit(run_case, work, world, swan, d, kn, threads, (cell, rows, cols)) for d, kn in cases]:
            fut.result()


def collect(work, world):
    from scipy.io import loadmat
    base = os.path.join(work, world)
    g = json.load(open(os.path.join(base, "grid.json")))
    shape = (len(DIRS), len(SPEEDS_KN), g["rows"], g["cols"])
    hs, tp, dr, ds = (np.full(shape, np.nan, np.float32) for _ in range(4))
    spec = {}
    for i, d in enumerate(DIRS):
        for j, kn in enumerate(SPEEDS_KN):
            cd = case_dir(work, world, d, kn)
            if not os.path.exists(os.path.join(cd, "done")):
                continue
            m = loadmat(os.path.join(cd, "grid.mat"))
            for arr, key in ((hs, "Hsig"), (tp, "RTpeak"), (dr, "Dir"), (ds, "Dspr")):
                v = m[key].astype(np.float32)
                v[v <= -9] = np.nan
                arr[i, j] = v
            spec[f"{d}:{kn}"] = open(os.path.join(cd, "spec.txt")).read()
    np.savez_compressed(os.path.join(base, "summary.npz"), hs=hs, tp=tp, dir=dr, dspr=ds, dirs=np.array(DIRS), speeds_kn=np.array(SPEEDS_KN))
    json.dump(spec, open(os.path.join(base, "spectra.json"), "w"))
    print(f"{world}: {int(np.isfinite(hs[:, :, 0, 0]).sum() + np.any(np.isfinite(hs), axis=(2, 3)).sum())} cases collected")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("prepare", "run", "collect"))
    ap.add_argument("--world", choices=WORLDS, action="append")
    ap.add_argument("--work", default="/root/swan-runs")
    ap.add_argument("--swan", default="/opt/swan/src/build/bin/swan.exe")
    ap.add_argument("--only", default="")
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--reverse", action="store_true")
    a = ap.parse_args()
    for w in a.world or WORLDS:
        if a.step == "prepare":
            prepare(a.work, w)
        elif a.step == "run":
            run(a.work, w, a.swan, a.only, a.threads, a.jobs, a.reverse)
        else:
            collect(a.work, w)
