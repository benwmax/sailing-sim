"""Bakes a steady ocean current (the Gulf Stream's Florida Current) for a coast world: <World>.stream.

  Tools/venv/bin/python -I Tools/coast/gulf_stream.py MiamiBimini [--nc <monthly means .nc>] [--cell 1000]
  python3 -I Tools/coast/gulf_stream.py --self-test

Docs: docs/world-bimini/README.md (stage 1, Miami to Bimini). The tidal current a world already has (<World>.current,
"SSCF", Tides.h) is a direction and gain per cell times one station's prediction: right for a bay entrance, wrong for an
ocean river that runs north at 1.5 to 2 m/s all day. This is the other kind: a surface velocity per cell for each month,
which the game adds to the tidal current (game wiring is a later Source/ PR; nothing reads the file yet).

Two sources, in order:
  1. Monthly mean surface currents from an ocean model, when --nc is given: Copernicus Marine GLOBAL_MULTIYEAR_PHY_001_030
     (uo/vo, free for commercial use with credit) or HYCOM GOFS 3.1 reanalysis (water_u/water_v, US Navy, public release).
     The file needs lat, lon, a 12-step time (or month) axis and the two velocity components at the surface; the bake
     interpolates them onto the world's grid and keeps them only where the world's water is 10 m deep or more.
  2. Otherwise an analytic Florida Current fitted to the published section (the default, so the bake runs anywhere):
     across each east-west row of the world the stream fills the deep channel between its western and eastern 100 m
     isobaths, its core a quarter of the way across from the Florida side (Leaman, Molinari and Vertes 1987: the surface
     maximum 20 to 30 km off Miami), falling off fast toward Florida and slowly toward the Bahama Bank, north along the
     channel's midline. Peak surface speed VMAX (1.8 m/s; published surface cores 1.5 to 2.2 m/s at 25.5-27 N) scaled by
     the month's transport (the NOAA AOML cable at 27 N: mean about 32 Sv, highest in summer, lowest in autumn and
     winter, a few per cent either side). It tapers to nothing in water shallower than 10 m (the bay, the bank, the reef
     flats). Meanders, eddies and day-to-day changes are not in a monthly mean: the game adds those later.

Output (Content/TerrainData), map frame (X north, Y east, metres, the world's projection):
  - <World>.stream: "SSGS", uint32 version 1, uint32 nx (east), uint32 ny (north), uint32 months (12), float32 cell,
    float64 x0 (north of row 0), float64 y0 (east of column 0), then for each month ny rows of nx (north, east) int16 pairs
    in mm/s. 40-byte header.
  - <World>.stream.json: the source, the parameters, each month's peak speed and the Miami-Bimini section (speed by km
    east of the western wall) for the docs and the later game test.
"""
import json
import math
import os
import struct
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TERRAIN = os.path.join(ROOT, "Content", "TerrainData")
MAGIC = b"SSGS"
HEADER = struct.Struct("<4sIIIIfdd")   # 40 bytes
assert HEADER.size == 40

# Analytic Florida Current (defaults; a world's "gulf_stream" block overrides them).
DEFAULTS = {
    "vmax_ms": 1.8,          # peak surface speed, annual mean
    "core_frac": 0.25,       # core position across the channel, from the western (Florida) 100 m isobath
    "west_frac": 0.12,       # e-folding half-width toward Florida, as a share of the channel's width
    "east_frac": 0.45,       # toward the Bahama Bank
    "edge_ms": 0.15,         # the slow drift that still runs north at the channel's edges
    "wall_depth_m": 100.0,   # the isobath that bounds the channel
    "shallow_m": 10.0,       # no stream in water shallower than this
    "season": 0.05,          # monthly scale = 1 + season * cos(2 pi (month - peak_month) / 12)
    "peak_month": 7,         # July (1 = January)
}


def season_scale(month, p):
    return 1.0 + p["season"] * math.cos(2.0 * math.pi * (month - p["peak_month"]) / 12.0)


def channel_rows(depth, p):
    """Per row (north): the western and eastern wall columns of the deepest run of water deeper than the wall isobath,
    or None where the row has none."""
    walls = []
    for row in depth:
        deep = np.nan_to_num(row, nan=0.0) >= p["wall_depth_m"]
        if not deep.any():
            walls.append(None)
            continue
        # The longest run of deep cells is the channel (a hole on the bank is not).
        d = np.diff(np.concatenate([[0], deep.astype(np.int8), [0]]))
        starts, ends = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        k = int(np.argmax(ends - starts))
        walls.append((int(starts[k]), int(ends[k]) - 1))
    return walls


def analytic(depth, cell, p, month):
    """(north, east) surface velocity in m/s on the depth grid (rows north, columns east, depth positive down)."""
    ny, nx = depth.shape
    vn = np.zeros((ny, nx))
    ve = np.zeros((ny, nx))
    walls = channel_rows(depth, p)
    rows = [i for i, w in enumerate(walls) if w is not None]
    if not rows:
        return vn, ve
    # The channel's midline and width, filled across rows without a channel and smoothed over about 10 km, so the
    # direction follows the strait, not a single row's isobath.
    mid = np.full(ny, np.nan)
    width = np.full(ny, np.nan)
    for i in rows:
        w0, w1 = walls[i]
        mid[i] = 0.5 * (w0 + w1)
        width[i] = max(w1 - w0, 1)
    idx = np.arange(ny)
    good = ~np.isnan(mid)
    mid = np.interp(idx, idx[good], mid[good])
    width = np.interp(idx, idx[good], width[good])
    west = mid - 0.5 * width
    k = max(1, int(round(10000.0 / cell)))
    kernel = np.ones(2 * k + 1) / (2 * k + 1)
    pad = lambda a: np.concatenate([np.full(k, a[0]), a, np.full(k, a[-1])])
    mid_s = np.convolve(pad(mid), kernel, mode="valid")
    # Direction: north along the midline (east offset per row of north), the same across the row.
    slope = np.gradient(mid_s)            # columns east per row north
    ang = np.arctan(slope)                # radians east of north
    scale = season_scale(month, p)
    cols = np.arange(nx)
    for i in range(ny):
        xi = (cols - west[i]) / width[i]  # 0 at the western wall, 1 at the eastern
        c = p["core_frac"]
        s = np.where(xi < c, np.exp(-((xi - c) / p["west_frac"]) ** 2), np.exp(-((xi - c) / p["east_frac"]) ** 2))
        speed = p["edge_ms"] + (p["vmax_ms"] - p["edge_ms"]) * s
        speed = np.where((xi < -0.15) | (xi > 1.15), 0.0, speed)   # nothing past the channel's walls
        d = np.nan_to_num(depth[i], nan=0.0)
        taper = np.clip((d - p["shallow_m"]) / (p["wall_depth_m"] - p["shallow_m"]), 0.0, 1.0) ** 0.5
        speed = speed * taper * scale
        vn[i] = speed * math.cos(ang[i])
        ve[i] = speed * math.sin(ang[i])
    return vn, ve


def from_netcdf(path, lat, lon, depth, p):
    """Monthly (north, east) surface velocity from a model's monthly means, bilinear onto the grid's lat/lon."""
    try:
        import xarray as xr
    except ImportError:
        sys.exit("--nc needs xarray and netCDF4 (Tools/venv/bin/pip install xarray netCDF4)")
    from scipy.interpolate import RegularGridInterpolator
    ds = xr.open_dataset(path)
    u = next(ds[v] for v in ("uo", "water_u", "u", "ugos") if v in ds)
    v = next(ds[v] for v in ("vo", "water_v", "v", "vgos") if v in ds)
    for dim in ("depth", "deptht", "lev", "z"):
        if dim in u.dims:
            u, v = u.isel({dim: 0}), v.isel({dim: 0})
    latn = next(n for n in ("latitude", "lat", "y") if n in u.coords)
    lonn = next(n for n in ("longitude", "lon", "x") if n in u.coords)
    tdim = next(d for d in u.dims if d not in (latn, lonn))
    if u.sizes[tdim] != 12:
        # A longer monthly series: average each calendar month.
        u = u.groupby(f"{tdim}.month").mean()
        v = v.groupby(f"{tdim}.month").mean()
        tdim = "month"
    la = np.asarray(u[latn])
    lo = np.asarray(u[lonn])
    lo = np.where(lo > 180.0, lo - 360.0, lo)
    out = []
    for m in range(12):
        comp = []
        for a in (v, u):   # north, east
            grid = np.nan_to_num(np.asarray(a.isel({tdim: m})), nan=0.0)
            f = RegularGridInterpolator((la, lo), grid, bounds_error=False, fill_value=0.0)
            comp.append(f(np.stack([lat.ravel(), lon.ravel()], axis=-1)).reshape(lat.shape))
        mask = np.nan_to_num(depth, nan=0.0) >= p["shallow_m"]
        out.append((np.where(mask, comp[0], 0.0), np.where(mask, comp[1], 0.0)))
    return out


def write(path, cell, x0, y0, months):
    ny, nx = months[0][0].shape
    with open(path, "wb") as fh:
        fh.write(HEADER.pack(MAGIC, 1, nx, ny, len(months), float(cell), float(x0), float(y0)))
        for vn, ve in months:
            q = np.empty((ny, nx, 2), "<i2")
            q[..., 0] = np.clip(np.round(vn * 1000.0), -32000, 32000)
            q[..., 1] = np.clip(np.round(ve * 1000.0), -32000, 32000)
            fh.write(q.tobytes())


def read(path):
    data = open(path, "rb").read()
    magic, ver, nx, ny, nm, cell, x0, y0 = HEADER.unpack_from(data, 0)
    assert magic == MAGIC and ver == 1, path
    a = np.frombuffer(data, "<i2", count=nm * ny * nx * 2, offset=HEADER.size).reshape(nm, ny, nx, 2).astype(np.float64) / 1000.0
    return {"cell": cell, "x0": x0, "y0": y0, "months": [(a[m, ..., 0], a[m, ..., 1]) for m in range(nm)]}


def section(depth, vn, ve, row, cell, p):
    """Speed across one row, by km east of the western wall: the section the docs and tests compare to the published one."""
    walls = channel_rows(depth, p)[row]
    if walls is None:
        return []
    sp = np.hypot(vn[row], ve[row])
    return [[round((c - walls[0]) * cell / 1000.0, 1), round(float(sp[c]), 3)] for c in range(max(0, walls[0] - 5), min(len(sp), walls[1] + 6))]


# ---------------------------------------------------------------- the world's depth on a coarse grid
def world_depth(world, cell):
    """Depth (m, positive down) on a cell-metre grid in the world's map frame, from its baked heights: a composed world
    reads its members (compose_world.load_member, the finest member wins where they overlap), a plain one its own .height.
    Returns depth, x0, y0, the frame's projection."""
    sys.path.insert(0, os.path.dirname(__file__))
    import compose_world as cw   # noqa: E402
    names = world.get("compose", [world["name"]])
    members = sorted((cw.load_member(n) for n in names), key=lambda m: m.cell)
    frame = next(m for m in members if m.name == world.get("frame", world["name"]))
    frames = cw.Frames(frame.proj, members)
    box = [frame.x0, frame.y0, frame.x1, frame.y1]
    for m in members:
        for xx in (m.x0, m.x1):
            for yy in (m.y0, m.y1):
                X, Y = frames.from_member(m, xx, yy)
                box = [min(box[0], X), min(box[1], Y), max(box[2], X), max(box[3], Y)]
    x0, y0 = math.floor(box[0] / cell) * cell, math.floor(box[1] / cell) * cell
    ny, nx = int((box[2] - x0) // cell) + 1, int((box[3] - y0) // cell) + 1
    X, Y = np.meshgrid(x0 + np.arange(ny) * cell, y0 + np.arange(nx) * cell, indexing="ij")
    z = np.full(X.shape, np.nan)
    for m in members:   # finest first
        x, y = frames.to_member(m, X, Y)
        ins = m.inside(x, y) & np.isnan(z)
        if ins.any():
            z[ins] = m.sample(x[ins], y[ins])
    return -z, x0, y0, frame.proj


def bake(name, nc=None, cell=1000.0):
    world = json.load(open(os.path.join(os.path.dirname(__file__), "worlds", f"{name}.json")))
    p = dict(DEFAULTS, **world.get("gulf_stream", {}))
    depth, x0, y0, proj = world_depth(world, cell)
    print(f"{name}: current grid {depth.shape[1]} x {depth.shape[0]} at {cell:.0f} m, deepest {np.nanmax(depth):.0f} m")
    if nc:
        from pyproj import Transformer
        to_ll = Transformer.from_crs(proj, "EPSG:4326", always_xy=True)
        X, Y = np.meshgrid(x0 + np.arange(depth.shape[0]) * cell, y0 + np.arange(depth.shape[1]) * cell, indexing="ij")
        lon, lat = to_ll.transform(Y, X)
        months = from_netcdf(nc, np.asarray(lat), np.asarray(lon), depth, p)
        source = f"monthly means from {os.path.basename(nc)}"
    else:
        months = [analytic(depth, cell, p, m) for m in range(1, 13)]
        source = "analytic Florida Current (gulf_stream.py DEFAULTS and the world's gulf_stream block)"
    out = os.path.join(TERRAIN, f"{name}.stream")
    write(out, cell, x0, y0, months)
    # The Miami-Bimini section: the row nearest the world's section latitude (default its centre).
    sec_x = world.get("gulf_stream", {}).get("section_north_m", 0.0)
    row = int(np.clip(round((sec_x - x0) / cell), 0, depth.shape[0] - 1))
    summary = {"source": source, "cell_m": cell, "params": p,
               "peak_ms_by_month": [round(float(np.hypot(vn, ve).max()), 3) for vn, ve in months],
               "section_row_north_m": x0 + row * cell,
               "section_km_ms": section(depth, *months[0], row, cell, p)}
    json.dump(summary, open(out + ".json", "w"), indent=1)
    print(f"wrote {out} ({os.path.getsize(out) / 1e6:.2f} MB); peak {max(summary['peak_ms_by_month']):.2f} m/s")


# ---------------------------------------------------------------- self-test on a made-up strait
def synthetic_strait(cell=1000.0):
    """Rows north, columns east: Biscayne Bay (2 m), the Florida shelf and reef (to 30 m), the slope to 800 m, the
    strait, the Bimini wall and the Great Bahama Bank (4 m) from 88 km east."""
    nx, ny = 110, 60
    e = np.arange(nx) * cell / 1000.0
    prof = np.where(e < 10, 2.0, np.where(e < 16, 2.0 + (e - 10) * 5.0, np.where(e < 28, 32.0 + (e - 16) * 64.0,
                    np.where(e < 80, 800.0, np.where(e < 88, 800.0 - (e - 80) * 99.5, 4.0)))))
    return np.tile(prof, (ny, 1))


def self_test():
    p = dict(DEFAULTS)
    depth = synthetic_strait()
    cell = 1000.0
    july = analytic(depth, cell, p, 7)
    jan = analytic(depth, cell, p, 1)
    sp = np.hypot(*july)
    row = sp[30]
    walls = channel_rows(depth, p)[30]
    core = int(np.argmax(row))
    core_km = (core - walls[0]) * cell / 1000.0
    width_km = (walls[1] - walls[0]) * cell / 1000.0
    checks = [
        ("peak in July is vmax x (1 + season)", abs(row.max() - p["vmax_ms"] * (1 + p["season"])) < 0.05),
        ("January is slower than July", np.hypot(*jan).max() < row.max()),
        ("core 15-30 km east of the 100 m wall", 15.0 <= core_km <= 30.0),
        ("channel about 60-70 km wall to wall", 55.0 <= width_km <= 75.0),
        ("nothing in the bay (2 m)", sp[:, :10].max() == 0.0),
        ("nothing on the bank (4 m)", sp[:, 90:].max() == 0.0),
        ("runs north", (july[0][sp > 0] > 0).all()),
        ("under 40% of the peak at the Florida wall", row[walls[0]] < 0.4 * row.max()),
        ("still a knot or more 20 km off the bank", row[walls[1] - 20] > 0.5),
    ]
    path = os.path.join(os.environ.get("TMPDIR", "/tmp"), "gulf_stream_selftest.stream")
    write(path, cell, -30000.0, -20000.0, [july, jan])
    back = read(path)
    checks.append(("file round trip to 1 mm/s", np.abs(back["months"][0][0] - july[0]).max() <= 0.0006 and back["x0"] == -30000.0))
    os.remove(path)
    ok = True
    for nm, good in checks:
        print(("PASS " if good else "FAIL ") + nm)
        ok &= bool(good)
    print("section (km east of the wall, m/s):", " ".join(f"{k}:{v:.2f}" for k, v in section(depth, *july, 30, cell, p)[::5]))
    return ok


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(0 if self_test() else 1)
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    args = sys.argv[1:]
    nc = args[args.index("--nc") + 1] if "--nc" in args else None
    cell = float(args[args.index("--cell") + 1]) if "--cell" in args else 1000.0
    bake(args[0], nc, cell)
