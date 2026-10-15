"""W1: fits the gust factor and the time between puffs by season and hour from the station data (Tools/wind/fetch_wind.sh)
and prints the table for Source/SailingPhysics/Private/WindClimate.cpp.

Gust factor: the highest 5-second wind in a minute over the 2-minute mean (ASOS TD-6405 reports exactly these), as the
ratio of sums over all minutes with a mean of at least 8 kn (lighter winds are dominated by the 1 kn reporting step).
  Lake (Dallas Love, Terrell, Dallas Executive ASOS): over mown grass, so an upper bound; converted to open water by the
  ratio of turbulence intensities for a neutral log profile, ln(10/0.03) / ln(10/0.0002) = 0.54 on (GF - 1).
  Coast (CO-OPS Galveston Bay: North Jetty, Eagle Point, Morgans Point): over water already, but the gust is the highest
  5 s in a 6-minute report against a 2-minute mean, so (GF - 1) is scaled to a 1-minute window by the ratio of Gaussian
  peak factors sqrt(2 ln(60/5)) / sqrt(2 ln(360/5)) = 0.76.
Puffs: in each day's 2-minute mean (ASOS, 1 min steps), peaks of the speed above its 31-minute running mean by at least
half its running standard deviation, at least 2 minutes apart; the median time between successive peaks. Their strength:
the RMS of the 2-minute mean over its 31-minute running mean (minus one), converted to water by sqrt(0.54) (the puffs come
down from the mixed layer, so roughness changes them less than the gusts; half the log-law factor, in variance).
Usage: Tools/venv/bin/python -I Tools/wind/fit_gusts.py [--csv out.csv]
"""
import collections
import csv
import glob
import math
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "Data", "Wind", "raw")
SEASONS = {12: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 1, 6: 2, 7: 2, 8: 2, 9: 3, 10: 3, 11: 3}
SEASON_NAMES = ["DJF", "MAM", "JJA", "SON"]
LAND_TO_WATER = math.log(10 / 0.03) / math.log(10 / 0.0002)
WINDOW_6_TO_1 = math.sqrt(2 * math.log(60 / 5)) / math.sqrt(2 * math.log(360 / 5))
MIN_KT = 8.0


def asos_minutes():
    """(station, datetime tuple local standard time, mean kt, gust kt) per minute."""
    for path in sorted(glob.glob(os.path.join(ROOT, "asos", "*.dat"))):
        st = os.path.basename(path).split("-")[3]
        with open(path, errors="replace") as fh:
            for line in fh:
                tok = line.split()
                if len(tok) < 6 or len(tok[1]) < 19:
                    continue
                stamp = tok[1][3:15]
                last = tok[-4:]
                if not all(t.isdigit() for t in last):
                    continue
                d2, s2, d5, s5 = (int(t) for t in last)
                if s5 < s2 or s2 > 80 or d2 > 360:
                    continue
                yield st, (int(stamp[0:4]), int(stamp[4:6]), int(stamp[6:8]), int(stamp[8:10]), int(stamp[10:12])), float(s2), float(s5)


def coops_reports():
    """(station, month, hour, mean m/s, gust m/s) per 6-minute report (local standard time)."""
    for path in sorted(glob.glob(os.path.join(ROOT, "coops", "*.csv"))):
        st = os.path.basename(path).split("-")[1]
        with open(path) as fh:
            rows = csv.reader(fh)
            next(rows, None)
            for r in rows:
                try:
                    stamp, s, g = r[0], float(r[1]), float(r[4])
                except (ValueError, IndexError):
                    continue
                if s <= 0 or g < s or g > 60:
                    continue
                yield st, int(stamp[5:7]), int(stamp[11:13]), s, g


def main():
    gf_land = collections.defaultdict(lambda: [0.0, 0.0, 0])
    days = collections.defaultdict(list)
    for st, (y, mo, d, h, mi), s2, s5 in asos_minutes():
        days[(st, y, mo, d)].append((h * 60 + mi, s2))
        if s2 >= MIN_KT:
            k = (SEASONS[mo], h // 3)
            gf_land[k][0] += s5
            gf_land[k][1] += s2
            gf_land[k][2] += 1
    intervals = collections.defaultdict(list)
    slow = collections.defaultdict(lambda: [0.0, 0])
    for (st, y, mo, d), series in days.items():
        series.sort()
        if len(series) < 600:
            continue
        t = np.array([m for m, _ in series], float)
        v = np.array([s for _, s in series], float)
        # Regular minutes only (gaps break the running statistics).
        full = np.full(1440, np.nan)
        full[t.astype(int)] = v
        k = np.ones(31) / 31
        valid = ~np.isnan(full)
        f0 = np.where(valid, full, 0.0)
        n = np.convolve(valid.astype(float), k, "same")
        mean = np.convolve(f0, k, "same") / np.maximum(n, 1e-9)
        var = np.convolve(f0 ** 2, k, "same") / np.maximum(n, 1e-9) - mean ** 2
        sd = np.sqrt(np.maximum(var, 0.0))
        ex = full - mean
        last = None
        for m in range(1, 1439):
            if not (valid[m - 1] and valid[m] and valid[m + 1]) or n[m] < 0.9 or mean[m] < MIN_KT:
                continue
            sk = (SEASONS[mo], (m // 60) // 3)
            slow[sk][0] += (ex[m] / mean[m]) ** 2
            slow[sk][1] += 1
            if ex[m] >= 0.5 * max(sd[m], 0.5) and full[m] >= full[m - 1] and full[m] > full[m + 1]:
                if last is not None and m - last >= 2 and m - last <= 40:
                    intervals[(SEASONS[mo], (m // 60) // 3)].append(m - last)
                last = m
    gf_coast = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for st, mo, h, s, g in coops_reports():
        if s >= MIN_KT * 0.514444:
            k = (SEASONS[mo], h // 3)
            gf_coast[k][0] += g
            gf_coast[k][1] += s
            gf_coast[k][2] += 1

    print("Gust factor (5 s peak in a minute / 2-min mean, over water) and median minutes between puffs.")
    print(f"Land to water {LAND_TO_WATER:.3f}; coast 6-min to 1-min window {WINDOW_6_TO_1:.3f}; minutes with a mean >= {MIN_KT:.0f} kn.")
    print("season hours   lake_land  lake_water  n_lake   coast_raw  coast_1min  n_coast  puff_min  n_puffs  slow_land  slow_water")
    rows = []
    for s in range(4):
        for b in range(8):
            gl = gf_land.get((s, b), [0, 0, 0])
            gc = gf_coast.get((s, b), [0, 0, 0])
            land = gl[0] / gl[1] if gl[1] else float("nan")
            water = 1 + (land - 1) * LAND_TO_WATER
            craw = gc[0] / gc[1] if gc[1] else float("nan")
            c1 = 1 + (craw - 1) * WINDOW_6_TO_1
            iv = intervals.get((s, b), [])
            med = float(np.median(iv)) if iv else float("nan")
            sl = slow.get((s, b), [0.0, 0])
            sland = math.sqrt(sl[0] / sl[1]) if sl[1] else float("nan")
            swater = sland * math.sqrt(LAND_TO_WATER)
            rows.append((SEASON_NAMES[s], b * 3, land, water, gl[2], craw, c1, gc[2], med, len(iv), sland, swater))
            print(f"{SEASON_NAMES[s]}   {b * 3:02d}-{b * 3 + 3:02d}   {land:8.3f}  {water:9.3f}  {gl[2]:7d}   {craw:8.3f}  {c1:9.3f}  {gc[2]:7d}  {med:7.1f}  {len(iv):7d}  {sland:8.3f}  {swater:9.3f}")
    print("\nC++ table rows {lake water GF, coast 1-min GF, puff minutes, puff strength} per season (DJF, MAM, JJA, SON), 3-hour bins from 00:")
    for s in range(4):
        cells = []
        for b in range(8):
            r = rows[s * 8 + b]
            cells.append("{ %.3f, %.3f, %.1f, %.3f }" % (r[3], r[6], r[8], r[11]))
        print("\t\t{ " + ", ".join(cells) + " },")
    if "--csv" in sys.argv:
        out = sys.argv[sys.argv.index("--csv") + 1]
        with open(out, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["season", "hour_from", "lake_land_gf", "lake_water_gf", "lake_minutes", "coast_raw_gf", "coast_1min_gf", "coast_reports", "puff_minutes", "puff_count", "slow_rms_land", "slow_rms_water"])
            for r in rows:
                w.writerow([r[0], r[1]] + ["%.4f" % x if isinstance(x, float) else x for x in r[2:]])


if __name__ == "__main__":
    main()
