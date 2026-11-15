# Main 6f44708f on the PC (Nov 15)

main 6f44708f is 17 commits past 7cfcaae2; in Source only `CrewMotion.cpp` and `CrewPose.cpp` changed (#697). I
checked it out detached and clean and ran `git lfs pull`.

- **MSVC build:** Succeeded, 0 errors, 0 warnings in our Source.
- **Licence check** (`scripts/licence-check.sh`): passes. Every file under Content/, Audio/ and Inputs/ has a row
  (87 rows).
- **Tests:** dropped from this step by the queue change; the full suite runs after #703 and is added below.
- **Package:** `Packaged\Windows-6f44708f` is new (2 min) and was warmed once. Bean's Saved was held aside and
  restored (F6458EAB).

## Sunfish still (lake, 12 kn, day; same args as main-check-7cfcaae2's)

`stills/sunfish-lake-day.png`, beside `../main-check-7cfcaae2/stills/sunfish-lake-day.png`.

The Sunfish draws whole: hull, rig, sail, wake and spray. From this camera (9 m, off the bow quarter), the moved
cockpit well and the rubrail barely differ from 7cfcaae2's frame. A close camera over the cockpit would show them
better.

The log has:
- no default-material or missing-mesh warnings (WorldGridMaterial appears only in the engine's own startup line);
- the known optional `S_*` samples;
- the two ensures every launch has (PSO precache, DoubleFloat origin on the first frame);
- the older cook gap, unchanged: `M_BowWave`, 45 `/Game/Audio/Pack` sounds and the Catalina tiller extensions are not
  in the package (see main-check-7cfcaae2).

## Full suite (job 4, after #703; Nov 15)

Before the suite I rebuilt on clean 6f44708f: Succeeded, 0 errors, 0 warnings in our Source.

`test.ps1`, default filter SailingSim: **344 passed, 0 failed, 30 with warnings, 0 not run, 149 min.**

These are the same tests with warnings as on 7cfcaae2's suite (main-check-7cfcaae2, all reasons there), with one
difference. The engine's blocked HTTP probe (`generate_204`) landed on Fleet.Polar.J22 this time, instead of
Fleet.Polar.ILCA7 and Physics.LeewayAndWeatherHelm, so there are 30 warned tests rather than 31. There are no new
failures and no new kinds of warning.
