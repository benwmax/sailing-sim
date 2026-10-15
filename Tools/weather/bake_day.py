"""W5b: bakes one fetched day (Tools/weather/fetch_day.py) into Content/TerrainData/Weather/<date>.wxday.

The hourly timeline is the HRRR analysis over the lake: the mean of the grid points within 5 km of the map origin for
the wind, cloud cover by layer, cloud base, boundary layer depth, CAPE, rain rate and visibility (the water temperature is
left to the game's monthly normal: see hour_row). On a stormy day (fetched with --storm) it also fits the storm the game
draws (FGustFront):
  - its motion: the shift that best maps each radar frame onto the next (log rain rate), the median over the storm;
  - its arrival: when the rain's leading edge reaches the map origin, less the time the front runs ahead of the rain;
  - the cold pool: the largest temperature drop at a station as the storm passed, its depth from the density current's
    speed (FColdPool: c = 0.75 sqrt(g h dT / T) + 0.6 x the ambient wind along the track);
  - the peak gust (stations), and from it the microburst: its outflow tops up the cold pool's flow to the peak gust over
    the gust factor;
  - the storm's peak rain over the lake (95th percentile of the raining cells within 10 km), and how long it rained hard
    there (the preset's storm timeline is stretched after its front to match);
and keeps the radar's rain rate on a 64 x 64 grid of 2 km cells round the origin, frame by frame.

Usage: Tools/venv/bin/python Tools/weather/bake_day.py YYYY-MM-DD ["title"]
"""
import csv
import datetime as dt
import glob
import json
import math
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LAKE_ELEV_M = 132.7          # Ray Hubbard pool, 435.5 ft
KNOT = 0.514444
RADAR_N, RADAR_CELL = 64, 2000.0
CORE_BEHIND_M, FOOT_REACH_M = 700.0, 300.0  # FStormShape::CoreBehindM, FStormRain::FootReachM
FRONT_ARRIVES_S = 150.0                     # FWeatherSystem::kFrontArrives
HRRR_LOV = -97.5                            # HRRR's Lambert conformal grid: central meridian, tangent latitude 38.5
HRRR_SIN_LAT_TAN = math.sin(math.radians(38.5))


def local_xy(lat, lon, lat0, lon0):
    """Map metres: X north, Y east of the origin."""
    return (lat - lat0) * 111_200.0, (lon - lon0) * 111_200.0 * math.cos(math.radians(lat0))


def hour_row(z, lat0, lon0):
    x, y = local_xy(z["lat"], z["lon"], lat0, lon0)
    r = np.hypot(x, y)
    near = r <= 5000.0
    nearest = np.unravel_index(np.argmin(r), r.shape)
    mean = lambda k: float(np.nanmean(z[k][near]))
    # Grid-relative to earth-relative winds (a fraction of a degree here, but right).
    rot = math.radians(HRRR_SIN_LAT_TAN * (lon0 - HRRR_LOV))
    u, v = mean("u10"), mean("v10")
    ue, ve = u * math.cos(rot) + v * math.sin(rot), -u * math.sin(rot) + v * math.cos(rot)
    # Speed: the mean of the points' speeds (a vector mean shrinks a light, variable wind); direction from the vector mean.
    speed = float(np.nanmean(np.hypot(z["u10"][near], z["v10"][near]))) / KNOT
    frm = (math.degrees(math.atan2(-ue, -ve)) + 360.0) % 360.0
    # The water: HRRR's 3 km grid does not resolve the lake's surface (its skin temperature there is the land's), so the
    # game takes W1's monthly normal (ClimateWaterC); -99 says so.
    t2 = mean("t2") - 273.15
    water = -99.0
    base = z["cbase"][nearest]
    base_agl = float(base) - LAKE_ELEV_M if np.isfinite(base) and base > 0 else 1500.0
    return dict(wind=speed, frm=frm, gust=mean("gust") / KNOT, air=t2, dew=mean("d2") - 273.15, water=water,
                pbl=mean("hpbl"), cape=mean("cape"), low=mean("lcdc") / 100.0, mid=mean("mcdc") / 100.0,
                high=mean("hcdc") / 100.0, base=float(np.clip(base_agl, 150.0, 6000.0)),
                rain=max(mean("prate") * 3600.0, 0.0), vis=float(np.clip(mean("vis") / 1000.0, 0.2, 40.0)))


def radar_frames(raw, meta):
    lat0, lon0 = meta["lat0"], meta["lon0"]
    files = sorted(glob.glob(os.path.join(raw, "mrms_*.npz")))
    off = dt.timedelta(hours=meta["utc_offset"])
    hours, frames = [], []
    # Output cell centres, rows north (X) and columns east (Y), centred on the origin.
    c = (np.arange(RADAR_N) - (RADAR_N - 1) / 2.0) * RADAR_CELL
    X, Y = np.meshgrid(c, c, indexing="ij")
    for f in files:
        z = np.load(f)
        rate, lat, lon = z["rate"], z["lat"], z["lon"]
        utc = dt.datetime.strptime(os.path.basename(f)[5:17], "%Y%m%d%H%M")
        local = utc + off
        hours.append(local.hour + local.minute / 60.0 + (24.0 if local.date() > dt.date.fromisoformat(meta["date"]) else 0.0))
        # Regular 0.01 deg grid: block mean of the source cells in each 2 km cell (four samples per cell).
        acc = np.zeros_like(X)
        for sx in (-0.25, 0.25):
            for sy in (-0.25, 0.25):
                la = lat0 + (X + sx * RADAR_CELL) / 111_200.0
                lo = lon0 + (Y + sy * RADAR_CELL) / (111_200.0 * math.cos(math.radians(lat0)))
                i = np.clip(np.round((la - lat[0, 0]) / (lat[1, 0] - lat[0, 0])).astype(int), 0, rate.shape[0] - 1)
                j = np.clip(np.round((lo - lon[0, 0]) / (lon[0, 1] - lon[0, 0])).astype(int), 0, rate.shape[1] - 1)
                acc += rate[i, j]
        frames.append(acc / 4.0)
    return hours, frames, files


def storm_motion(files):
    """Median motion (toward degrees, m/s) of the rain pattern between frames 12 minutes apart."""
    def shift(a, b, m=12):
        A, B = np.log1p(a), np.log1p(b)
        best = (-1.0, 0, 0)
        for dr in range(-m, m + 1):
            for dc in range(-m, m + 1):
                s = (np.roll(np.roll(A, dr, 0), dc, 1)[m:-m, m:-m] * B[m:-m, m:-m]).sum()
                if s > best[0]:
                    best = (s, dr, dc)
        return best[1], best[2]
    vn, ve = [], []
    for i in range(0, len(files) - 3, 3):
        a, b = np.load(files[i]), np.load(files[i + 3])
        if b["rate"].max() < 20.0:
            continue
        dr, dc = shift(a["rate"], b["rate"])
        lat = a["lat"]
        dn = (lat[1, 0] - lat[0, 0]) * 111_200.0
        de = (a["lon"][0, 1] - a["lon"][0, 0]) * 111_200.0 * math.cos(math.radians(float(lat.mean())))
        tsec = 12 * 60.0
        vn.append(dr * dn / tsec)
        ve.append(dc * de / tsec)
    n, e = float(np.median(vn)), float(np.median(ve))
    return (math.degrees(math.atan2(e, n)) + 360.0) % 360.0, math.hypot(n, e)


def stations(raw, t0, t1):
    """Per station: the largest temperature drop within 45 minutes and the peak gust inside the local window."""
    rows = list(csv.DictReader(open(os.path.join(raw, "asos.csv"))))
    out = {}
    for r in rows:
        t = dt.datetime.strptime(r["valid"], "%Y-%m-%d %H:%M")
        if not (t0 <= t <= t1):
            continue
        s = out.setdefault(r["station"], {"temps": [], "gust": 0.0})
        if r["tmpf"] not in ("M", ""):
            s["temps"].append((t, (float(r["tmpf"]) - 32.0) / 1.8))
        if r["gust"] not in ("M", ""):
            s["gust"] = max(s["gust"], float(r["gust"]))
    drops, gust = [], 0.0
    for name, s in out.items():
        temps = sorted(s["temps"])
        best = 0.0
        for i, (ta, a) in enumerate(temps):
            for tb, b in temps[i + 1:]:
                if (tb - ta).total_seconds() <= 45 * 60:
                    best = max(best, a - b)
        if best >= 2.0:
            drops.append(best)
        gust = max(gust, s["gust"])
        print(f"  {name}: drop {best:.1f} C, peak gust {s['gust']:.0f} kn")
    # The cold pool's own drop is the largest seen (the others caught its edge or report too seldom).
    return (max(drops) if drops else 5.0), gust


def main():
    date = sys.argv[1]
    raw = os.path.join(REPO, "Data", "Weather", "raw", date)
    meta = json.load(open(os.path.join(raw, "meta.json")))
    off = dt.timedelta(hours=meta["utc_offset"])
    d0 = dt.date.fromisoformat(date)
    hours = []
    for h in range(24):
        utc = dt.datetime(d0.year, d0.month, d0.day, h) - off
        hours.append(hour_row(np.load(os.path.join(raw, f"hrrr_{utc:%Y%m%d%H}.npz")), meta["lat0"], meta["lon0"]))
    title = sys.argv[2] if len(sys.argv) > 2 else date
    lines = ["WXDAY 1", f"date {date}", "place RayHubbard", f"title {title}", f"utc_offset {meta['utc_offset']}"]
    storm = None
    radar = b""
    if "storm_utc" in meta:
        rh, frames, files = radar_frames(raw, meta)
        move, speed = storm_motion(files)
        # Arrival: the rain's edge at the origin (heavier than 20 mm/h within 3 km), less the front's lead over it.
        c = (np.arange(RADAR_N) - (RADAR_N - 1) / 2.0) * RADAR_CELL
        X, Y = np.meshgrid(c, c, indexing="ij")
        near = np.hypot(X, Y) <= 3000.0
        reach = [h for h, f in zip(rh, frames) if f[near].max() > 20.0]
        lead_s = (CORE_BEHIND_M - FOOT_REACH_M) / max(speed, 3.0)
        arrival = (reach[0] if reach else rh[len(rh) // 2]) - lead_s / 3600.0
        t0 = dt.datetime.combine(d0, dt.time()) + dt.timedelta(hours=arrival - 1.0)
        drop, gust = stations(raw, t0, t0 + dt.timedelta(hours=2.5))
        drop = float(np.clip(drop, 3.0, 10.0))
        # Cold pool depth from the density current's speed, with the hour's wind ahead of it along the track.
        ahead = hours[min(int(arrival), 23)]
        along = ahead["wind"] * KNOT * -math.cos(math.radians(ahead["frm"] - move))
        reduced = 9.80665 * drop / (ahead["air"] + 273.15)
        depth = float(np.clip(((speed - 0.6 * along) / 0.75) ** 2 / reduced, 300.0, 2500.0))
        # The microburst: what the cold pool's own flow (1.2 x the front) leaves of the peak gust over a gust factor of
        # 1.25, at 10 m (0.515 of its peak at 50 m).
        burst = float(np.clip((gust * KNOT / 1.25 - 1.2 * speed) / 0.515, 0.0, 30.0))
        lake = np.hypot(X, Y) <= 10000.0
        wet = np.concatenate([f[lake] for f in frames])
        peak_rain = float(np.percentile(wet[wet > 5.0], 95)) if (wet > 5.0).any() else 30.0
        # How long it rained hard at the lake, against the preset storm's five minutes of rain and clearing.
        hard = [h for h, f in zip(rh, frames) if f[lake].max() > 10.0]
        scale = float(np.clip((hard[-1] - hard[0]) * 3600.0 / 300.0, 1.0, 12.0)) if len(hard) > 1 else 1.0
        storm = dict(arrival=arrival, move=move, speed=speed, cold_pool=drop, depth=depth, peak_gust=gust, burst=burst,
                     peak_rain=peak_rain, time_scale=scale)
        lines.append(f"start_hour {arrival - FRONT_ARRIVES_S / 3600.0:.4f}")
        lines.append("storm " + " ".join(f"{k} {v:.3f}" for k, v in storm.items()))
        lines.append(f"radar {RADAR_N} {RADAR_N} {RADAR_CELL:.0f} {len(frames)}")
        lines.append("radar_hours " + " ".join(f"{h:.4f}" for h in rh))
        radar = b"".join(np.clip(np.round(f * 2.0), 0, 255).astype(np.uint8).tobytes() for f in frames)
        print(f"  storm: arrival {arrival:.2f} h, moving toward {move:.0f} at {speed:.1f} m/s, cold pool {drop:.1f} C "
              f"{depth:.0f} m deep, peak gust {gust:.0f} kn, burst {burst:.1f} m/s, peak rain {peak_rain:.0f} mm/h")
    else:
        # Start when the day is at its most sailable: the windiest daylight hour under 20 kn (or mid-afternoon).
        day = [(h, r["wind"]) for h, r in enumerate(hours) if 9 <= h <= 17 and r["wind"] < 20.0]
        lines.append(f"start_hour {max(day, key=lambda t: t[1])[0] if day else 15}")
    lines.append("# hour wind_kn from_deg gust_kn air_c dew_c water_c pbl_m cape low mid high base_m rain_mmh vis_km")
    for h, r in enumerate(hours):
        lines.append(f"hour {h} {r['wind']:.2f} {r['frm']:.1f} {r['gust']:.2f} {r['air']:.2f} {r['dew']:.2f} {r['water']:.0f} "
                     f"{r['pbl']:.0f} {r['cape']:.0f} {r['low']:.3f} {r['mid']:.3f} {r['high']:.3f} {r['base']:.0f} {r['rain']:.2f} {r['vis']:.1f}")
    out_dir = os.path.join(REPO, "Content", "TerrainData", "Weather")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{date}.wxday")
    with open(path, "wb") as f:
        f.write(("\n".join(lines) + "\n").encode())
        if radar:
            f.write(b"RADARBIN\n" + radar)
    print(f"wrote {path} ({os.path.getsize(path) // 1024} KB)")
    for h in (0, 6, 9, 12, 15, 18, 21):
        r = hours[h]
        print(f"  {h:02d}h wind {r['wind']:4.1f} kn from {r['frm']:3.0f} gust {r['gust']:4.1f} air {r['air']:4.1f} water {r['water']:4.1f} "
              f"pbl {r['pbl']:5.0f} cape {r['cape']:5.0f} cloud {r['low']:.2f}/{r['mid']:.2f}/{r['high']:.2f} base {r['base']:5.0f} rain {r['rain']:5.1f}")


if __name__ == "__main__":
    main()
