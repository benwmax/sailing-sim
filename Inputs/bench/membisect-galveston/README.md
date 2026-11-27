# Galveston memory bisect, 30 min runs (PC, Nov 27 2026)

**Question:** where does the Galveston-route private-bytes climb of the 95220b32 soak (`../soak-95220b32-galveston/`, about
100 MB steps at minutes 29, 33, 36, 41, 46 and 52) come in?

**Runs:** 30 min each, the soak's arguments (4K Ultra at 100%, Bolivar Roads start, demo, 15:00); private bytes and
working set of the game process every minute (`memory.csv`), her logged position every 60 s (`track.txt`), the exact
command line (`args.txt`). Bean's Saved held aside and restored (7B5CA7BE) each time.

| Run | private MB at minute 10 / 20 / 28 / 30 | the minute-29/30 step |
|---|---|---|
| 95220b32 soak (wildlife on) | 14,852 / 14,787 / 14,823 / 14,946 | +132 at 29 |
| `95220b32-nowildlife/` | 14,782 / 14,782 / 14,784 / 14,888 | +98 at 29 |
| `a3f81854/` (#834 in, #839 and #844 not) | 14,777 / 14,783 / 14,792 / 14,891 | +102 at 30 |

## What it shows

- **Not wildlife:** with `-SailingNoWildlife`, 95220b32 is flat to minute 28 and takes the same 100 MB step at 29.
- **Not #839 or #844:** a3f81854 takes the same step at minute 30.
- **(Withdrawn: see `run-95220b32/`, where the steps come on a different route too.)** It follows the place, not the build. All three runs sailed the same track to about 25 min (south from the start to
  about -23,350 N, 23,710 E: `track.txt`), and the step comes when they get there. The demo then parts ways (the nowildlife
  run turned back north at 1,800 s; the soak and a3f81854 were at -23,627 N).
- **8ae5a0b1 climbs too** (corrected: `../soak-95220b32-galveston/`): about 8 MB/min over 2 h, on a track that went west.

**Caveat:** 30 min ends right where the staircase starts, so these runs can't compare slopes, only the first step. The
580e5270 run was skipped (its job launched and stopped it within 4 s; nothing kept). Next: one 60 min run on a fixed route
(`-SailingRun`), in `run-95220b32/`, to see whether the steps come with distance on a repeatable line.
