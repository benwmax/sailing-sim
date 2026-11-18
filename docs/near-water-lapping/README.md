# Near water: the lapping line only at the waterline (Nov 18 2026)

sailing-feedback #30: on the near water at the bulkhead lot and along the bank at the I-30 bridge, M_WaterV4 drew a
herringbone of chevrons along the wall, and hard-edged grey blocks 10 to 30 px across nearer the camera.
`-SailingClassicWater` removed both; no other flag did. Stills and the flag isolation:
`Inputs/bench/render-bugs-nov17/` on the `inputs` branch.

## Finding it

- **First guess (wrong):** a cubic B-spline read for the chop, long-chop and ripple slope maps, on the theory that their
  texels were magnified near the camera. It compiled clean on D3D SM6, but the pattern was unchanged
  (`render-bugs-nov17/pr805-18f58e2b/`). The blocks' flat, hard-edged fill pointed away from slopes.
- **Bisect:** a temporary switch turned off one layer of M_WaterV4 at a time, and the PC shot bulkhead-near-35 and
  bulkhead-near-20 for each (`render-bugs-nov17/pr805-7c8d3f57-bisect/`).
  - **Pattern gone:** with no foam at all, with no shore depth, and with only the shore's lapping foam off.
  - **No change:** with a flat normal, or with no wake-grid slopes, capillaries, ripples, chop or foam bump, or with
    roughness raised to at least 0.35.
  - **No whitecaps:** `-SailingDebugFoam` drew none on that water.

## Cause

The lapping foam (`swash`, then `lap`) was drawn wherever the shore map's depth was under 35 cm. That was the whole test.
The water in front of the bulkhead and along that bank is a flat shallow shelf, so the "lapping line" became a band
metres wide. Its lace texture, banded by the lapping's wave, read as the herringbone along the wall and as grey blocks
nearer the camera. M_Water draws no lapping, which is why `-SailingClassicWater` hid it.

## Fix

`swash` now also needs the waterline to be close. The distance to the waterline is the depth divided by its slope,
taken from the shore map's own cells: central differences one 1 m cell either way, and land is stored as 0 deep.

- **Where it draws:** the line is full within 0.4 m of the waterline and gone by 1.2 m.
- **Docks:** a dock's stamp (0.05 m deep plus 0.6 m per metre out) keeps its lapping within about half a metre.
- **Shelves:** a flat shallow shelf, whose depth hardly changes, draws no lapping at all.
- **Cost:** four extra shore-map reads, only on pixels shallower than 35 cm.

**Second half: the lapping's pattern.** The PC's reshoot of the waterline-only change (`render-bugs-nov17/pr805-c25fc326/`)
cut the pattern back to the first metre off the wall, but it stayed in that strip. It also showed at the bridge bank's
waterline, and as a checker band under a private dock. The lapping was broken up by the foam texture's lace (its R
channel: thin bubble films), both multiplied in and added to the phase of its wave, which multiplied the films'
frequency. A metre or so from the camera at a grazing angle, that aliased. It now uses the wash's bubble noise instead:
`WB_NOISE`, soft value noise at 0.4 m, 0.14 m and 5 cm, the same the boats' wakes use. Its mean is about 0.25, the
lace's mean, so the lapping keeps its brightness. Lapping alone no longer reads the foam texture, which saves its six
taps on shore pixels.

The B-spline reads and the bisect switch are not in the final change.

## Checks

- **PC:** the four #30 stills plus `private-dock-05m` and `club-beach-05m` (`env-bulkhead-05m`, `-near-20`, `-near-35`, `env-bridge-05m`, with the args in the
  issue) at Ultra 1080p, 1:1 against `crops/`. Also a look at a beach and the marina docks, to confirm the lapping line
  is still there.
- **Mac:** `scripts/gate.sh --scope water`, and commit the rebuilt M_WaterV4.
