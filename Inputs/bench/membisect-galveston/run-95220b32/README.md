# Fixed-route memory run on Windows-95220b32, 60 min (PC, Nov 27 2026)

**Route (`args.txt`, repeatable on any build by swapping the package):** the Galveston soak's start (-20,900 N, 23,500 E),
4K Ultra at 100%, 15:00, no demo. A fixed 10 kn AfternoonBreeze from 305 (`-SailingWindFrom=305`), the boat held head to
wind (`-SailingTWA=0 -SailingHoldTWA=0`), and `-SailingRun=3,305` slides her north-west up the bay at 3 m/s. The
GalvestonBay height bake has at least 2 m of water 75 m either side of that line for 11.1 km. She ended at -14,249 N,
13,478 E, 10.7 km from the start on bearing 304 (`track.txt`, every 60 s). Exit 0; Bean's Saved restored (7B5CA7BE).

## Result: the staircase comes on the fixed route too, from minute 34

| Minute | private MB | step |
|---|---|---|
| 10 | 14,766 | |
| 20 | 14,651 | |
| 33 | 14,620 | flat or falling from minute 1 to 33 |
| 35 | 14,927 | +262 at 35 (falls back to 14,798 by 37) |
| 46 | 14,917 | +89 |
| 53 | 15,020 | +99 |
| 59 | 15,121 | +103 |

- **Private:** +367 MB from minute 20 to 58 (9.7 MB/min), all of it from minute 34 on: about 100 MB steps every 6 to 7
  minutes, flat between, as in the soak (steps at 29, 33, 36, 41, 46, 52).
- **Working set:** +172 MB from 20 to 58, the same steps, smaller.

## What it changes

This route goes north-west up the bay, nowhere near the south track the 30 min runs shared (`../README.md`), and the
steps still start about half an hour in. So I'm withdrawing "it follows the place". At a constant speed it could be
time or distance travelled: here they move together. Against that, the 83aa7652 soak stayed flat for 100 min.

**A next run that would separate them:** the same arguments with `-SailingRun=0,305` (she stays put) for 60 min. Steps
there would mean time, not distance.
