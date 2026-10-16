"""W7 numbers: how long a puff lasts and how far it veers, from the same ASOS one-minute data as fit_gusts.py.

On each day's 2-minute means (1-minute steps, minutes with a mean of 8 kn or more around them):
  - a puff is a run of minutes above the 31-minute running mean by at least half its running standard deviation
    (fit_gusts.py's peak rule, held while it lasts); its duration is the run's length in minutes;
  - its veer is the 2-minute mean direction at the run's peak minus the 31-minute circular mean direction (positive =
    clockwise, a veer); its strength is the peak speed over the running mean, minus one.
Prints the medians and the veer per +10 % of strength (a least-squares slope through zero), lake stations only.
The game's side is Tools/wind/PuffShape.cpp (scripts/w7-numbers.sh), measured the same way.
Usage: Tools/venv/bin/python -I Tools/wind/puff_shape.py [--series <PuffShape output> ...]
"""
import collections
import glob
import math
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "Data", "Wind", "raw", "asos")
MIN_KT = 8.0


def days():
    out = collections.defaultdict(dict)
    for path in sorted(glob.glob(os.path.join(ROOT, "*.dat"))):
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
                if s5 < s2 or s2 > 80 or d2 > 360 or s2 <= 0:
                    continue
                key = (st, stamp[0:8])
                out[key][int(stamp[8:10]) * 60 + int(stamp[10:12])] = (float(s2), float(d2))
    return out


def analyse(series):
    """series: list of (minute, speed kt, from-direction deg). Returns [(duration min, veer deg, strength)]."""
    puffs = []
    t = np.array([m for m, _, _ in series])
    s = np.array([v for _, v, _ in series])
    d = np.radians([x for _, _, x in series])
    n = len(s)
    above = np.zeros(n, bool)
    rm = np.zeros(n)
    rdir = np.zeros(n)
    ok = np.zeros(n, bool)
    for m in range(15, n - 15):
        if t[m + 15] - t[m - 15] != 30:
            continue  # a gap in the record
        w = s[m - 15:m + 16]
        mean, sd = w.mean(), w.std()
        if mean < MIN_KT:
            continue
        ok[m] = True
        rm[m] = mean
        rdir[m] = math.atan2(np.mean(np.sin(d[m - 15:m + 16])), np.mean(np.cos(d[m - 15:m + 16])))
        above[m] = s[m] - mean >= 0.5 * max(sd, 0.5)
    m = 0
    while m < n:
        if not (ok[m] and above[m]):
            m += 1
            continue
        start = m
        while m < n and ok[m] and above[m]:
            m += 1
        if start == 0 or m >= n or not ok[start - 1] or not ok[m]:
            continue  # only runs with a measured start and end
        peak = start + int(np.argmax(s[start:m]))
        veer = math.degrees(math.atan2(math.sin(d[peak] - rdir[peak]), math.cos(d[peak] - rdir[peak])))
        puffs.append((m - start, veer, s[peak] / rm[peak] - 1.0))
    return puffs


def game_series(path):
    """PuffShape's lines (point, minute, speed kn, from deg) as one series per point."""
    out = collections.defaultdict(list)
    with open(path) as fh:
        for line in fh:
            p, m, v, d = line.split()
            out[p].append((int(m), float(v), float(d)))
    return out.values()


def main():
    allp = []
    if "--series" in sys.argv:
        label = "game"
        for path in sys.argv[sys.argv.index("--series") + 1:]:
            for series in game_series(path):
                allp += analyse(series)
    else:
        label = "stations"
        for key, mins in days().items():
            series = [(m, *mins[m]) for m in sorted(mins)]
            if len(series) > 60:
                allp += analyse(series)
    dur = np.array([p[0] for p in allp])
    veer = np.array([p[1] for p in allp])
    strength = np.array([p[2] for p in allp])
    slope = float(np.sum(veer * strength) / np.sum(strength * strength)) * 0.1
    print(f"{label}: {len(allp)} puffs; duration median {np.median(dur):.0f} min (p25 {np.percentile(dur, 25):.0f}, "
          f"p75 {np.percentile(dur, 75):.0f}); veer at the peak mean {veer.mean():+.1f} deg, median {np.median(veer):+.1f}; "
          f"strength median {np.median(strength):+.3f}; veer per +10 % {slope:+.2f} deg")


if __name__ == "__main__":
    main()
