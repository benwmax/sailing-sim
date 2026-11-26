"""Named game scopes (Sailing_*) on worker threads inside each render-thread frame, slow vs fast frames. Counts each named
event's time overlapping the frame (any depth)."""
import csv, sys
from collections import defaultdict
rt, wk, slow_ms, fast_ms = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
frames = []
with open(rt, newline='') as f:
    for r in csv.DictReader(f):
        if r['Depth'] == '0' and r['TimerName'] == 'Frame':
            try: frames.append((float(r['StartTime']), float(r['EndTime']), float(r['Duration']) * 1000))
            except ValueError: pass
ev = []
with open(wk, newline='') as f:
    for r in csv.DictReader(f):
        n = r['TimerName']
        if not (n.startswith('Sailing_') or (r['Depth'] == '1' and n == 'ParallelFor Task')): continue
        try: ev.append((float(r['StartTime']), float(r['EndTime']), n))
        except ValueError: pass
ev.sort()
def busy(a, b):
    d = defaultdict(float)
    for s, e, n in ev:
        if s >= b: break
        if e <= a: continue
        d[n] += (min(e, b) - max(s, a)) * 1000
    return d
slow = [busy(a, b) for a, b, ms in frames if ms > slow_ms]
fast = [busy(a, b) for a, b, ms in frames if ms < fast_ms]
print(f"render frames {len(frames)}: slow (> {slow_ms} ms) {len(slow)}, fast (< {fast_ms} ms) {len(fast)}")
names = set().union(*[d.keys() for d in slow + fast])
m = lambda L, n: sum(d.get(n, 0) for d in L) / max(1, len(L))
rows = sorted(((m(slow, n) - m(fast, n), m(slow, n), m(fast, n), n) for n in names), reverse=True)
print(f"{'scope (ms of worker time inside the frame)':50s} {'slow':>7s} {'fast':>7s} {'diff':>7s}")
for d, s, q, n in rows[:20]: print(f"{n[:50]:50s} {s:7.2f} {q:7.2f} {d:+7.2f}")
