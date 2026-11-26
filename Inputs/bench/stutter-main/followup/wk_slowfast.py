"""Worker-thread busy time (depth-0 events, by timer) overlapping each render-thread frame; slow vs fast frames."""
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
        if r['Depth'] != '0': continue
        try: ev.append((float(r['StartTime']), float(r['EndTime']), r['TimerName']))
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
print(f"render frames {len(frames)}: slow {len(slow)}, fast {len(fast)}; worker events {len(ev)}")
names = set().union(*[d.keys() for d in slow + fast])
m = lambda L, n: sum(d.get(n, 0) for d in L) / max(1, len(L))
rows = sorted(((m(slow, n) - m(fast, n), m(slow, n), m(fast, n), n) for n in names), reverse=True)
print(f"{'worker job (ms of worker time inside the frame)':70s} {'slow':>7s} {'fast':>7s} {'diff':>7s}")
for d, s, q, n in rows[:25]: print(f"{n[:70]:70s} {s:7.2f} {q:7.2f} {d:+7.2f}")
tot = lambda L: sum(sum(d.values()) for d in L) / max(1, len(L))
print(f"total worker busy per frame: slow {tot(slow):.1f} ms, fast {tot(fast):.1f} ms")
