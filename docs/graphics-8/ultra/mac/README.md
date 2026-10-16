# Ultra showcase on the Mac (PR #84)

Branch `ultra-showcase` with main c371418e merged in (merge commit 6f8b336b), plus one fix (below). Mac: M5 Pro, packaged
Development build.

## Fix: M_Smoke was not in the packaged game

In the packaged build the log showed `LoadPackage: SkipPackage: /Game/Materials/M_Smoke ... does not exist on disk`, and
no vessel had exhaust. `UpdateExhaust` loads the material only by path, and nothing else references it, so the cook left
it out. The PC's still came from an uncooked run, which finds the asset on disk. `APowerVesselActor`'s constructor now
finds it with `ConstructorHelpers`, as `M_Ghost` and `M_RainCurtain` are found, so the cook includes it. Each actor
copies it from the class default; the per-actor `LoadObject` stays as a fallback. With the fix, the packaged game logs
`Exhaust:` for every vessel and `exhaust-ultra-packaged.jpg` shows the container ship's stack trailing black smoke aft.

**Cast-off reload:** the packaged game was started on the front end at Ultra
(`-SailingUIScript=Log,Enter,...`). Continue cast off into Galveston, the map reloaded, and every vessel logged
`Exhaust:` again after the reload. That line only prints once the material is loaded.

## Gate (`scripts/gate.sh --scope water`, against main c371418e benched in the same session)

| view | tier | main fps | PR fps | delta |
|---|---|---|---|---|
| beam8 | Medium | 88.5 | 88.4 | -0.1 |
| beam8 | High | 58.7 | 58.8 | +0.1 |
| beat15 | Medium | 86.3 | 84.1 | -2.2 |
| beat15 | High | 56.2 | 51.7 | -4.5 |
| storm | Medium | 71.0 | 69.5 | -1.5 |
| storm | High | 51.2 | 50.0 | -1.2 |
| marina | Medium | 95.1 | 93.5 | -1.6 |
| marina | High | 61.9 | 60.0 | -1.9 |
| coast-day | Medium | 83.7 | 81.5 | -2.2 |
| coast-day | High | 53.6 | 52.5 | -1.1 |
| gulf-sea | Medium | 105.8 | 103.2 | -2.6 |
| gulf-sea | High | 70.6 | 68.7 | -1.9 |
| helm-eye | Medium | 87.8 | 85.4 | -2.4 |
| helm-eye | High | 55.2 | 54.0 | -1.2 |
| slip | Medium | 82.1 | 80.4 | -1.7 |
| slip | High | 52.4 | 51.8 | -0.6 |
| bridge | Medium | 100.8 | 98.7 | -2.1 |
| bridge | High | 64.6 | 62.3 | -2.3 |

Every view passes (Medium 60, High 45; 135 of 135 tests). The run came out about 2 fps low across the board, so the moved
views were rerun:

- Right after, beat15 and gulf-sea, PR then main then PR again: High was 55.7 / 55.8 / 52.5 and 70.5 / 70.5 / 68.7.
  The first PR rerun matches main exactly, so the -4.5 was session drift.
- beat15 Medium still read about 2 fps lower (84.4 and 83.9 against 86.4), so the two packaged builds were alternated
  on the same view, main, PR, main, PR: 83.8, 83.7, 83.9, 83.8 fps. That leaves no difference.

- With the M_Smoke fix, the gate ran again (135 of 135 tests, every view passes) and read low again: storm High
  46.4 (-4.8), beat15 High 51.2 (-5.0), the rest -0.2 to -3.0. Alternated once more, main, PR, main, PR: beat15 High
  56.0, 55.3, 55.3, 54.9 and storm High 51.2, 51.3, 49.2, 51.4. No difference again.

So High and Medium are unchanged, which matches the code: every Ultra path returns early on any other tier. Gate runs
late in a long session come out about 2 fps under the baseline on every view, the views this PR can't touch included.
Only interleaved runs separate a change from that drift.

## Ultra runs on the Mac

| view | fps | GPU ms |
|---|---|---|
| beat15 | 16.5 | 54.4 |
| coast-day | 22.2 | 39.2 |
| gulf-sea | 26.6 | 35.9 |
| Galveston near a ship, traffic busy | 24 | 39.7 |

It runs without errors (the one ensure in the log is the existing groom PSO-precache one). There is no Ultra gate on the
Mac.

## Bow spray on the Gulf (19 kn, 1.8 m swell, close-hauled at 45 deg)

`-SailingWorld=Gulf -SailingLaunch=2 -SailingWeather=AfternoonBreeze -SailingWind=19 -SailingSwell=1.8 -SailingTWA=45
-SailingHoldTWA=45 -SailingHour=11 -SailingCamYaw=150 -SailingCamPitch=-6 -SailingCamDist=11`.

**She slams and sprays.** In an 8 s recording at 10 frames a second, about one frame in eight catches a burst: the bow
comes down on a swell and a sheet of droplets runs aft along the lee topsides (`spray-gulf-19kn-ultra-bursts.jpg`, four
of those frames cropped to the bow). The sheet is dense, but it stays low along the hull; none is thrown up over the
deck or carried aft by the wind. A single still mostly falls between bursts (`spray-gulf-19kn-ultra.jpg`, and High's
`spray-gulf-19kn-high.jpg`), so compare the two tiers in motion, not from stills.

## Seen in passing: the sail blows out after `-SailingNearShip`

In two of six runs with `-SailingNearShip` (one packaged, one uncooked), the J/22's sail cloth had stretched into a
huge flat sheet (`nearship-sail-blowout.jpg`). It wasn't seen in any run without it. The option resets the boat
(`ResetBoat`) when the first ship spawns, mid-run, and the cloth isn't reset with her. It is measuring-only, but it spoils
stills: worth a follow-up that resets the sail cloth when the boat is reset.
