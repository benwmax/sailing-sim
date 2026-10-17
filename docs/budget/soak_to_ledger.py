#!/usr/bin/env python3
"""A Mac soak's RSS CSV and 1 Hz frames CSV -> the ledger's soak CSV (t_s, ram_mb, vram_mb, fps, p99_ms).

Usage: docs/budget/soak_to_ledger.py <mem.csv> <frames-1hz.csv> <out.csv>
One row per RSS sample (every 60 s); fps and p99 cover the 60 s before it, p99 as the median of the per-second p99s
(the 1 Hz trace keeps no single frames). vram_mb stays blank: the Mac has no whole-GPU figure like nvidia-smi's.
"""
import csv, sys

mem = [(float(r["seconds"]), float(r["rss_mb"])) for r in csv.DictReader(open(sys.argv[1]))]
secs = [(int(r["t_s"]), int(r["frames"]), float(r["mean_ms"]), float(r["p99_ms"])) for r in csv.DictReader(open(sys.argv[2]))]
with open(sys.argv[3], "w") as f:
    f.write("t_s,ram_mb,vram_mb,fps,p99_ms\n")
    for t, ram in mem:
        w = [s for s in secs if t - 60 <= s[0] < t]
        if not w or ram < 100:
            continue
        frames = sum(s[1] for s in w); ms = sum(s[1] * s[2] for s in w)
        p = sorted(s[3] for s in w)[len(w) // 2]
        f.write(f"{t:.0f},{ram:.1f},,{frames / (ms / 1000.0):.2f},{p:.3f}\n")
