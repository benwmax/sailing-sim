# Stationary memory run on Windows-95220b32, 60 min (PC, Nov 27 2026)

**Arguments (`args.txt`):** the fixed-route run's (`../run-95220b32/`) with `-SailingRun=0,305`: the Galveston start, 4K
Ultra at 100%, 15:00, a fixed 10 kn AfternoonBreeze from 305, the boat held head to wind, no slide. She drifted astern
1.5 km in the hour (to -20,509 N, 22,011 E: `track.txt`), against 10.7 km on the fixed route. Exit 0; Bean's Saved
restored (7B5CA7BE).

## Result: the steps come anyway, so they follow time, not distance

| Minute | private MB | step |
|---|---|---|
| 10 | 14,758 | |
| 18 | 14,751 | flat from minute 3 |
| 19 | 14,835 | +84 |
| 30 | 14,959 | +102 |
| 41 | 15,063 | +91 |
| 46 | 15,118 | +54 |
| 53 | 15,214 | +95 |
| 59 | 15,220 | |

- **Private:** +382 MB from minute 20 to 58 (10.0 MB/min). The fixed route did 9.7 and the soak 15.
- **The steps:** about 90 MB each, flat between, starting at minute 19 here (34 on the fixed route, 29 in the soak and
  the 30 min runs). They are about 11 min apart at first, then 5 to 7.
- **Working set:** +120 MB from 20 to 58, the same steps, smaller.

With the boat nearly still the staircase is the same size, so it comes with time in the game, not distance sailed or
where she is. Since the 30 min runs show it in a3f81854 too, and 8ae5a0b1 climbs at about 8 MB/min, it predates #839 and
#844. The one flat Galveston soak so far is 83aa7652's (100 min). The steps are too regular and too big for one source
alone to explain from here.
