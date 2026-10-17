#!/usr/bin/env python3
"""Soak numbers for the budget ledger from a -SailingBenchTrace frames CSV and an RSS CSV.

Usage: docs/budget/soak_stats.py <frames.csv> <mem.csv> [--downsample <out.csv>]
Prints mean fps and p99 ms for the first and last 10 minutes, the p99 drift (ms per hour, a linear fit of the
per-minute p99 over the run), the RSS growth (MB per hour, a linear fit after the first 5 minutes) and the peak RSS.
--downsample writes the frames at 1 Hz (t_s, frames, mean_ms, p99_ms, max_ms per second).
"""
import csv, sys


def p99(xs):
    s = sorted(xs)
    return s[min(len(s) - 1, int(0.99 * len(s)))]


def fit(xs, ys):
    n = len(xs); mx = sum(xs) / n; my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0.0


def window(frames, t0, t1):
    ms = [m for t, m in frames if t0 <= t < t1]
    return len(ms) / (sum(ms) / 1000.0), p99(ms)


def main():
    frames = [(float(r["t_s"]), float(r["frame_ms"])) for r in csv.DictReader(open(sys.argv[1]))]
    mem = [(float(r["seconds"]), float(r["rss_mb"])) for r in csv.DictReader(open(sys.argv[2]))]
    warm = 3.0  # the bench's warm-up
    start = frames[0][0] + warm; end = frames[-1][0]
    fps_a, p99_a = window(frames, start, start + 600)
    fps_b, p99_b = window(frames, end - 600, end + 1)
    minutes = {}
    for t, m in frames:
        if t >= start: minutes.setdefault(int((t - start) // 60), []).append(m)
    mins = sorted(k for k in minutes if len(minutes[k]) > 100)
    drift = fit([k / 60.0 for k in mins], [p99(minutes[k]) for k in mins])
    late = [(t, v) for t, v in mem if t >= 300]
    growth = fit([t / 3600.0 for t, _ in late], [v for _, v in late]) if len(late) > 2 else float("nan")
    print(f"run {end - frames[0][0]:.0f} s, {len(frames)} frames, {len(mem)} RSS samples")
    print(f"first 10 min: {fps_a:.1f} fps, p99 {p99_a:.2f} ms")
    print(f"last 10 min:  {fps_b:.1f} fps, p99 {p99_b:.2f} ms")
    print(f"p99 drift: {drift:+.3f} ms/h (per-minute p99, {len(mins)} minutes)")
    print(f"RSS growth: {growth:+.1f} MB/h after 5 min; peak {max(v for _, v in mem):.0f} MB, "
          f"first {mem[0][1]:.0f} MB, last {mem[-1][1]:.0f} MB")
    print(f"worst frame {max(m for t, m in frames if t >= start):.1f} ms; "
          f"frames over 33.3 ms after warm-up: {sum(1 for t, m in frames if t >= start and m > 33.3)}")
    if "--downsample" in sys.argv:
        out = sys.argv[sys.argv.index("--downsample") + 1]
        secs = {}
        for t, m in frames: secs.setdefault(int(t), []).append(m)
        with open(out, "w") as f:
            f.write("t_s,frames,mean_ms,p99_ms,max_ms\n")
            for s in sorted(secs):
                v = secs[s]
                f.write(f"{s},{len(v)},{sum(v) / len(v):.3f},{p99(v):.3f},{max(v):.3f}\n")


if __name__ == "__main__":
    main()
