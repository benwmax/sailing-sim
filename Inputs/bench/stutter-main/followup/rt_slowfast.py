"""Render-thread frames from an Insights ExportTimingEvents csv: per frame, inclusive ms per timer (depth 1-4, a timer's
outermost instance per frame only); compare slow frames (> slow_ms) with fast ones (< fast_ms)."""
import csv, sys
from collections import defaultdict

path, slow_ms, fast_ms = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
frames = []  # (dur_ms, {timer: ms})
cur = None
open_stack = []  # (end, name) of instances counted, to skip nested repeats of the same timer
with open(path, newline='') as f:
    for row in csv.DictReader(f):
        try:
            depth = int(row['Depth']); start = float(row['StartTime']); end = float(row['EndTime']); dur = float(row['Duration'])
        except ValueError:
            continue
        name = row['TimerName']
        if depth == 0:
            if name != 'Frame':
                continue
            cur = (dur * 1000.0, defaultdict(float), end)
            frames.append(cur)
            open_stack = []
            continue
        if cur is None or start > cur[2] or depth > 12:
            continue
        open_stack = [(e, n) for (e, n) in open_stack if e > start]
        if any(n == name for (_, n) in open_stack):
            continue
        cur[1][name] += dur * 1000.0
        open_stack.append((end, name))

slow = [fr for fr in frames if fr[0] > slow_ms]
fast = [fr for fr in frames if fr[0] < fast_ms]
print(f"frames {len(frames)}: slow (> {slow_ms} ms) {len(slow)}, fast (< {fast_ms} ms) {len(fast)}")
if not slow or not fast:
    sys.exit(0)
mean = lambda xs: sum(xs) / len(xs)
print(f"mean frame: slow {mean([f[0] for f in slow]):.2f} ms, fast {mean([f[0] for f in fast]):.2f} ms")
names = set()
for fr in slow + fast:
    names.update(fr[1].keys())
rows = []
for n in names:
    s = mean([fr[1].get(n, 0.0) for fr in slow]); q = mean([fr[1].get(n, 0.0) for fr in fast])
    rows.append((s - q, s, q, n))
rows.sort(reverse=True)
print(f"{'timer':70s} {'slow':>7s} {'fast':>7s} {'diff':>7s}")
for d, s, q, n in rows[:45]:
    print(f"{n[:70]:70s} {s:7.2f} {q:7.2f} {d:+7.2f}")
