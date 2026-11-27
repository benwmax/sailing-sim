# Bow wave 2: one bow wave instead of four (Nov 2026)

Bean asked for a bow wave that splits more realistically and in more detail. The research and the full plan are in the
Claude Doc "Bow wave and wake: research and plan". Phases 1 to 3 go into the Dec 11 release (Bean's choice, Nov 25);
phases 4 to 6 come after it. This page covers phases 1 and 2.

## What was wrong (phase 1 findings)

The water at the bow came from four separate layers, and none of them knew about the others:

1. **The wake grid** (`FWakeGrid`): an exact linear wave solver around the boat, with every hull as a pressure patch.
   It gets the far wake right, including the Kelvin wedge, the transverse waves and the quarter wave. Near the stem,
   though, its crest is small.
2. **The curl** (`ASailboatPawn::UpdateBowWave`, `M_BowWave`): a sheet standing off each side of the bow. Its height
   came from a formula and sat on the bare lake waves, so the grid's own crest and trough under it were ignored.
3. **The waterline foam** (`M_WaterV4`, from `FHullClipMap`): player's boat only.
4. **The bow spray** (`AWaterSurface::UpdateSpray`): sheets peeled from a fixed spot on the deck edge, whatever the
   curl was doing.

An offline copy of the grid (numpy, the same spectral step, the J/22 hull sampled from `FHullShape::BottomZ`) measured
the grid's crest along her side, in flat water, on the High grid (256 cells at 0.25 m):

| Speed | Speed head V²/2g | Grid crest at her side | Where (aft of the stem) |
|---|---|---|---|
| 3 kn (1.54 m/s) | 0.12 m | 0.8 cm | |
| 5 kn (2.57 m/s) | 0.34 m | 3.2 cm | 2.2 m |
| 6 kn (3.09 m/s) | 0.49 m | 4.1 cm | 2.4 m |

So at 6 kn the grid's side crest is about 8% of the speed head, and it peaks 2 to 2.7 m aft of the stem, which is
about right for where a J/22's bow wave crest stands. A finer grid helps (0.125 m cells give 40 to 50% more crest), but
not enough to make a crest you can see on its own, and forcing the bow harder made the grid ring without raising the
crest. A linear solver can't build the steep, breaking crest at the stem. So the near field stays the curl's job,
with the grid underneath it.

The transverse wavelength at 6 kn is 2πV²/g = 6.1 m, about her waterline length (5.8 m): she is at hull speed there, so
the bow and stern waves are at their biggest. That is where the bow wave should first spill white.

## What changed (phase 2)

No new GPU work and no material changes. Everything is in `Source/`.

- **The curl sits on the water as it is drawn.** `AWaterSurface::DrawnWakeHeightAt` reads the wake grid's last
  uploaded frame (the one `M_WaterV4` is drawing), sampled the same way as the material samples it. Each curl vertex
  adds it to the lake waves, so the sheet's outer edge meets the water instead of sinking under the grid's crest or
  standing off its trough.
- **One crest, not two.** At each station the curl's crest is the higher of the formula's and the grid's (read 15 and
  30 cm out from her side). The sheet adds only what the grid doesn't already draw. Near the stem the formula leads.
  Further aft, where the grid's crest stands, the grid carries it. The lip's foam (vertex colour G) follows that crest.
- **Finer curl:** 20 stations by 8 across a side, up from 10 by 6. Close up, the old lip showed visible facets.
- **The spray peels from the lip.** `UpdateBowWave` keeps the lip (`ASailboatPawn::GetBowLip`: position, height and the
  crest's share at each station). `UpdateSpray` picks each sheet's starting point along it, weighted by the crest, so
  the spray leaves where the wave is highest. With no curl (Low, far AI boats) it uses the old deck-edge spot.
- **White along her side at speed.** In the wake grid, open water right beside her hull that is pushed up past 1.5 cm
  makes foam once she is fast for her length. That starts at a length Froude number of 0.30 (about 4.5 kn for a J/22)
  and is full by 0.42 (her hull speed, about 6 kn). The offline copy gives no side foam at 3 kn, 0.11 at 5 kn and 0.85
  at 6 kn at the most, with none ahead of her. It leaves a narrow white band along her track. `M_WaterV4` draws wake
  foam only past about 0.4, so the first rate (0.28 at 6 kn, matched exactly in the engine on the PC) drew nothing in
  the PC's bow stills of Nov 26; the rate is now three times that.

Cost: the curl does about 360 bilinear lookups a frame per boat on the game thread (a few microseconds). The grid's new
foam test runs only on cells beside a hull. And a saving: the PC's stutter trace (Nov 26) put the wake FFT's column pass
at 27-32 ms of worker time a frame against 2 ms for its rows, because each column was walked in place at a stride of the
grid's width. `Fft2` now copies the columns out in blocks of 16, transforms them as contiguous lines and copies them
back: the same arithmetic, bit-identical results (on a Linux box, single-threaded, 512 grid: 12 ms down to 6.4).

**Switch and compare:** the console's `sailing.BowWave2` (default 1) turns all of phase 2 on or off: the curl, the bow
spray and the grid's side foam. Its default is one line in `WaterSurface.cpp` (`GBowWave2`), so the release can ship
without it if the Dec 9-10 sweep finds a water regression. `-SailingClassicBowWave` turns it off for one run, for
before and after stills.

**Test:** `SailingSim.Visual.BowCrest` sails the J/22 on the High grid at 3, 5 and 6 kn. It checks that the side crest
grows with speed, is a few centimetres at 6 kn and turns white there (not at 3 kn), with no foam ahead. The bounds are
loose around the offline numbers above. `SailingSim.Visual.WakeGrid` is unchanged.

## Bench views

`bow-scenes.csv` lists 16 capture-mode stills: about 3, 5, 6 and 7 kn on the lake, from the bow quarter on both sides,
from abeam, from the stern quarter, from above and from the helm. Bean asked that every view look good, since the camera
rotates. Two of them are "before" stills with `-SailingClassicBowWave`. Wind and angle come from the J/22 polar
(`scripts/polar.sh --quick`: 6 kn of wind at 150 degrees sails 2.9 kn, at 90 degrees 4.7 kn; 10 kn at 90 degrees 6.0 kn;
15 kn at 90 degrees 6.8 kn).

```
SCENES=docs/bow-wave/bow-scenes.csv OUT=docs/bow-wave/captures scripts/capture-scenes.sh 25
```

Give each run about 25 s so she is up to speed and the grid has filled in. Every row carries `-SailingDemo`: `-SailingHoldTWA` only steers with the demo autopilot, and unsteered she rounded up from 90 to 49 degrees and sailed past the camera, so the bow views showed her stern (the PC's first pass, Nov 26). The captures' `.telemetry.csv` files give
the speed she actually sailed.

## Reference footage

Bean will film the J/22's bow if he gets the chance. Until then the references are online clips, used for study only
and never copied into the game or the repo. Phase 8 already lists three J/22 chase clips with the speed and wind known
(`docs/phase-8/reference-scenes.csv`: J22-L-001 light air, J22-M-001 10 to 14 kn, J22-H-001 16 to 18 kn), and they
show the lee bow from a chase boat. They have not been screened for the bow yet. What to look for in them:

- where along her side the crest stands, and how high it is against the topsides
- where it first turns white, and at what speed
- how wide the white band is, and how long it lasts astern
- where the spray leaves the bow, and how high it goes

## Next: phase 3

Sharper crests: horizontal displacement from the wake grid (one more complex FFT a step), foam where the surface folds,
and a 16-bit wake texture. This needs `make_materials.py`, so the pull request needs Bean's `bean-approved` label, and
it waits for the lake wind streaks PR (#837), which changes the same material.
