"""W5b: fetches one real day's weather over Lake Ray Hubbard from free, anonymous sources into Data/Weather/raw/<date>/.

- HRRR analyses (NOAA High-Resolution Rapid Refresh, AWS bucket noaa-hrrr-bdp-pds): every hour of the local day, only the
  fields the game uses, byte ranges read from each file's .idx, decoded with eccodes and cropped to a box around the lake.
- MRMS precipitation rate (NOAA Multi-Radar Multi-Sensor, AWS bucket noaa-mrms-pds), every 4 minutes over a storm window,
  cropped to the same kind of box (128 km).
- ASOS reports from Iowa Environmental Mesonet (Mesquite, Dallas Love Field, Terrell): the gust front's arrival, its
  temperature drop and peak gust, which hourly model fields smear out.

Usage: Tools/venv/bin/python Tools/weather/fetch_day.py YYYY-MM-DD [--storm HH:MM-HH:MM local]
Then Tools/weather/bake_day.py YYYY-MM-DD writes Content/TerrainData/Weather/<date>.wxday.
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import gzip
import io
import json
import os
import sys
import tempfile
import urllib.request

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LAT0, LON0 = 32.8233, -96.5000  # the map origin: Rush Creek Yacht Club
HRRR = "https://noaa-hrrr-bdp-pds.s3.amazonaws.com"
MRMS = "https://noaa-mrms-pds.s3.amazonaws.com"
# (idx match, short name): every field the bake reads.
HRRR_FIELDS = [
    ("UGRD:10 m above ground:anl", "u10"), ("VGRD:10 m above ground:anl", "v10"),
    ("UGRD:80 m above ground:anl", "u80"), ("VGRD:80 m above ground:anl", "v80"),
    ("GUST:surface:anl", "gust"), ("TMP:2 m above ground:anl", "t2"), ("DPT:2 m above ground:anl", "d2"),
    ("TMP:surface:anl", "tsfc"), ("HPBL:surface:anl", "hpbl"), ("CAPE:surface:anl", "cape"),
    ("LCDC:low cloud layer:anl", "lcdc"), ("MCDC:middle cloud layer:anl", "mcdc"), ("HCDC:high cloud layer:anl", "hcdc"),
    ("TCDC:entire atmosphere:anl", "tcdc"), ("HGT:cloud base:anl", "cbase"), ("PRATE:surface:anl", "prate"),
    ("VIS:surface:anl", "vis"), ("REFC:entire atmosphere:anl", "refc"),
]
HRRR_HALF_KM = 30.0   # HRRR crop: 60 km square (3 km grid)
MRMS_HALF_KM = 64.0   # radar crop: 128 km square (1 km grid)
STATIONS = ["HQZ", "DAL", "TRL"]


def get(url, rng=None, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={rng[0]}-{rng[1]}"} if rng else {})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:  # network hiccups: back off and retry
            if k == tries - 1:
                raise
            import time
            time.sleep(2 ** (k + 1))
            print(f"  retry {url}: {e}", file=sys.stderr)


def decode_grib(data):
    """All messages in a GRIB2 byte string: (values 2-D, lats, lons)."""
    import eccodes
    out = []
    with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as f:
        f.write(data)
        path = f.name
    try:
        with open(path, "rb") as fh:
            while True:
                h = eccodes.codes_grib_new_from_file(fh)
                if h is None:
                    break
                try:
                    ny, nx = eccodes.codes_get(h, "Ny"), eccodes.codes_get(h, "Nx")
                    vals = eccodes.codes_get_values(h).reshape(ny, nx)
                    lats = eccodes.codes_get_array(h, "latitudes").reshape(ny, nx)
                    lons = eccodes.codes_get_array(h, "longitudes").reshape(ny, nx)
                    miss = eccodes.codes_get(h, "missingValue")
                    vals = np.where(vals == miss, np.nan, vals)
                    out.append((vals, lats, np.where(lons > 180, lons - 360, lons)))
                finally:
                    eccodes.codes_release(h)
    finally:
        os.unlink(path)
    return out


def local_offset(date):
    """UTC offset of US Central time on that date (DST: second Sunday of March to first Sunday of November)."""
    y = date.year
    mar = dt.date(y, 3, 8) + dt.timedelta(days=(6 - dt.date(y, 3, 8).weekday()) % 7)
    nov = dt.date(y, 11, 1) + dt.timedelta(days=(6 - dt.date(y, 11, 1).weekday()) % 7)
    return -5 if mar <= date < nov else -6


def crop_box(lats, lons, half_km):
    dy = (lats - LAT0) * 111.2
    dx = (lons - LON0) * 111.2 * np.cos(np.radians(LAT0))
    m = (np.abs(dx) <= half_km) & (np.abs(dy) <= half_km)
    rows, cols = np.where(m)
    return slice(rows.min(), rows.max() + 1), slice(cols.min(), cols.max() + 1)


def fetch_hrrr_hour(utc, outdir):
    path = os.path.join(outdir, f"hrrr_{utc:%Y%m%d%H}.npz")
    if os.path.exists(path):
        return path
    base = f"{HRRR}/hrrr.{utc:%Y%m%d}/conus/hrrr.t{utc:%H}z.wrfsfcf00.grib2"
    idx = get(base + ".idx").decode().splitlines()
    starts = [(int(l.split(":")[1]), l) for l in idx]
    fields = {}
    box = None
    for key, name in HRRR_FIELDS:
        for i, (off, line) in enumerate(starts):
            if key in line:
                end = starts[i + 1][0] - 1 if i + 1 < len(starts) else None
                vals, lats, lons = decode_grib(get(base, (off, end if end else off + 20_000_000)))[0]
                if box is None:
                    box = crop_box(lats, lons, HRRR_HALF_KM)
                    fields["lat"], fields["lon"] = lats[box], lons[box]
                fields[name] = vals[box].astype(np.float32)
                break
        else:
            print(f"  {utc:%Y-%m-%d %H}Z: no {key}", file=sys.stderr)
    np.savez_compressed(path, **fields)
    return path


def fetch_mrms(utc, outdir, product="PrecipRate_00.00"):
    """The MRMS file nearest a UTC time (they come every 2 minutes)."""
    day = f"{utc:%Y%m%d}"
    path = os.path.join(outdir, f"mrms_{utc:%Y%m%d%H%M}.npz")
    if os.path.exists(path):
        return path
    listing = get(f"{MRMS}/?list-type=2&prefix=CONUS/{product}/{day}/MRMS_{product}_{day}-{utc:%H}").decode()
    keys = [k.split("</Key>")[0] for k in listing.split("<Key>")[1:]]
    if not keys:
        return None
    def when(k):
        s = k.rsplit("_", 1)[1].split(".")[0]
        return abs((dt.datetime.strptime(s, "%Y%m%d-%H%M%S") - utc).total_seconds())
    key = min(keys, key=when)
    vals, lats, lons = decode_grib(gzip.decompress(get(f"{MRMS}/{key}")))[0]
    box = crop_box(lats, lons, MRMS_HALF_KM)
    np.savez_compressed(path, rate=np.clip(np.nan_to_num(vals[box], nan=0.0), 0, None).astype(np.float32),
                        lat=lats[box].astype(np.float32), lon=lons[box].astype(np.float32), key=key)
    return path


def fetch_asos(date, outdir):
    path = os.path.join(outdir, "asos.csv")
    if os.path.exists(path):
        return path
    d1 = date + dt.timedelta(days=1)
    q = "&".join(f"station={s}" for s in STATIONS)
    url = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?" + q +
           "&data=sknt&data=gust&data=drct&data=tmpf&data=dwpf&data=p01i&data=wxcodes"
           f"&year1={date.year}&month1={date.month}&day1={date.day}&year2={d1.year}&month2={d1.month}&day2={d1.day}"
           "&tz=America%2FChicago&format=onlycomma&latlon=no&missing=M&trace=T&direct=no&report_type=1&report_type=3&report_type=4")
    open(path, "wb").write(get(url))
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--storm", help="local window for radar frames, HH:MM-HH:MM")
    a = ap.parse_args()
    date = dt.date.fromisoformat(a.date)
    off = local_offset(date)
    outdir = os.path.join(REPO, "Data", "Weather", "raw", a.date)
    os.makedirs(outdir, exist_ok=True)
    print(f"{a.date}: UTC{off:+d}, raw data in {outdir}")
    hours = [dt.datetime(date.year, date.month, date.day, h) - dt.timedelta(hours=off) for h in range(24)]
    with cf.ThreadPoolExecutor(6) as ex:
        for p in ex.map(lambda u: fetch_hrrr_hour(u, outdir), hours):
            print("  " + os.path.basename(p))
    fetch_asos(date, outdir)
    print("  asos.csv")
    meta = {"date": a.date, "utc_offset": off, "lat0": LAT0, "lon0": LON0}
    if a.storm:
        t0, t1 = a.storm.split("-")
        start = dt.datetime.combine(date, dt.time.fromisoformat(t0)) - dt.timedelta(hours=off)
        end = dt.datetime.combine(date, dt.time.fromisoformat(t1)) - dt.timedelta(hours=off)
        if end <= start:
            end += dt.timedelta(days=1)
        times = []
        t = start
        while t <= end:
            times.append(t)
            t += dt.timedelta(minutes=4)
        with cf.ThreadPoolExecutor(6) as ex:
            for t, p in zip(times, ex.map(lambda u: fetch_mrms(u, outdir), times)):
                print(f"  radar {t:%H:%M}Z {os.path.basename(p) if p else 'missing'}")
        meta["storm_utc"] = [start.isoformat(), end.isoformat()]
    json.dump(meta, open(os.path.join(outdir, "meta.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
