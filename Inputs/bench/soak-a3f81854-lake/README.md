# 2 h lake soak on Windows-a3f81854: **PARTIAL**, stopped at 85 min for Bean's pause (PC, Nov 26 2026)

**Package and run:**
- Package: Development `Packaged\Windows-a3f81854` (main with #834's birds).
- Run: 3840x2160 Ultra, `-SailingWorld=Lake -SailingLaunch=1 -SailingDemo -SailingHour=15 -SailingBench=7200`, from
  23:31 UTC.

**Why it's partial:**
- Bean asked to pause PC work at 00:56 UTC. I stopped the soak by its STOP file at minute 85, by my own PID.
- The bench writes its frame times and bench.json only when it finishes, so **there's no fps or p99 for this run.**
- The two soaks queued after it (Galveston, then the Gulf) were cancelled.

**What there is:**
- **Memory** every minute (`memory.csv`), for 83 rows:

| Minute | Working set (MB) | Private (MB) |
|---|---|---|
| 1 | 4131 | 14912 |
| 10 | 3506 | 14243 |
| 30 | 3552 | 14290 |
| 50 | 3553 | 14296 |
| 70 | 3557 | 14331 |
| 82 | 3539 | 14310 |

- **No crash** in 85 minutes.
- The only crash folders are the frame-0 ensures every run on this PC logs: !IsComponentPSOPrecachingEnabled() || bPSOPrecacheCalled  [F; OriginX <= OriginMax && OriginY <= OriginMax && OriginZ <= O.

Bean's Saved was held aside during the run and restored when it stopped (7B5CA7BE).
