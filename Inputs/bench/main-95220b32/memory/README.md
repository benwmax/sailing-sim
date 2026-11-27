# Main 95220b32 memory over 30 min (PC, Nov 27 2026)

**Why:** the Mac sees resident memory climb about 12 MB/min on 95220b32 and is bisecting it.

**Runs:**
- Package: Development `Packaged\Windows-95220b32`, warm.
- Two 30 min lake runs, one after the other, each a fresh launch.
- Settings: High, 1920x1080, launch 1, demo, 15:00, crew off.
- The first run is as is; the second adds `-SailingNoWildlife`.
- The game process's working set and private bytes are logged every minute (`*-memory.csv`).

**Working set (MB) at minutes 1, 5, 10, 15, 20, 25 and 29:**

| Run | 1 | 5 | 10 | 15 | 20 | 25 | 29 |
|---|---|---|---|---|---|---|---|
| wildlife-on | 3810 | 3676 | 3466 | 3500 | 3503 | 3474 | 3497 |
| no-wildlife | 3915 | 3780 | 3588 | 3576 | 3539 | 3543 | 3621 |

**Trend from minute 5 to 30:**

| Run | Working set | Private |
|---|---|---|
| Wildlife on | -5.1 MB/min | -5.6 MB/min |
| `-SailingNoWildlife` | -6.4 MB/min | -6.5 MB/min |

**Result: no climb on Windows.** Memory falls slightly after the start-up peak, with or without the birds. Both runs exited
0.

**So the Mac's +12 MB/min doesn't reproduce here** with this package at High on the lake. It may be Mac- or Metal-side,
or need a longer run or a different view.

Bean's Saved was held aside and restored (7B5CA7BE).
