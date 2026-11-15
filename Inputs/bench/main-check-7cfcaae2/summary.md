# Main 7cfcaae2 on the PC (Nov 14-15)

main 7cfcaae2 is 27 commits past 0d2c4802; in Source only WaterSurface.cpp/.h changed (#690). I checked it out
detached and clean and ran `git lfs pull`. The full suite ran after the #697 PR check
(`Inputs/bench/pr-checks-nov14/`).

- **MSVC build:** Succeeded, 0 errors, 0 warnings in our Source.
- **Licence check** (`scripts/licence-check.sh`): passes. Every file under Content/, Audio/ and Inputs/ has a row
  (87 rows).
- **Full suite** (`test.ps1`, default filter SailingSim): 343 passed, 0 failed, 31 with warnings, 0 not run, 150 min.
- **Package:** `Packaged\Windows-7cfcaae2` is new (4 min) and was warmed once. A reuses `Packaged\Windows-0d2c4802`,
  already warm.

## The 31 tests with warnings (all pass)

| reason | tests |
|---|---|
| `LogStreaming: Failed to read file Content/TerrainData/<World>.detail` (or `TexasCoast.height`). These worlds have no shore-detail bake on this PC, which the code allows; the bakes are git-ignored or built on the Mac. | Coast.ChartSymbolsMatchNoaaChart, Coast.GalvestonSwell, Coast.LongPassageStable, Coast.MarseilleCassis, Geo.LakeData, Lake.InIronsAtLaunch, Physics.OceanSpectrum, Traffic.BusyBayNoCollisions, Visual.TreeSpecies, World.Streaming.Sail, World.Streaming.Windows, World.FarLights, World.FarRing, World.Haze, World.Skyline (15) |
| `LogHttp: HTTP request timed out ... generate_204`. This is the engine's connectivity probe: the PC blocks it, and it lands on whichever test is running at the time. | Fleet.Polar.Catalina30, Corsair880, Hobie16, ILCA7, Lagoon42, Sunfish; Physics.GaleTackTiming, LaserPuffHandling, LeewayAndWeatherHelm, SurfingFlow, TackLookAhead, TackTime (12) |
| The optional `S_*` samples are missing on this PC (known). | Smoke.AsyncPhysicsMatchesSync |
| Warnings the test asks for: `unknown launch spot "gone"` and a missing png. | Geo.SaveFallback, UI.Feedback.Jpeg |
| The hero mesh is outside J22Mesh's tolerance: canoe body volume 1.085 m^3 (physics 1.052), centre of buoyancy z -0.096 (physics -0.077). This is the test's own warning band, the same as on earlier mains. | Visual.J22HeroMesh |

## Benches: 4K Ultra fullscreen, 30 s, A/B/A back to back

Setup: `-SailingBenchTrace` plus Insights. Game-thread figures come from the trace after 8.7 s.

| view | run | fps | p99 ms | max ms | GPU ms | game ms | GT frames > 40 ms | Sailing_WaterUploads > 20 ms | water GPU ms | post GPU ms |
|---|---|---|---|---|---|---|---|---|---|---|
| storm | a 0d2c4802 | 36.7 | 34.5 | 52.0 | 27.06 | 17.10 | 20 | 10 (2 at the start, then ~1 every 5 s) | 1.58 | 2.50 |
| storm | b 7cfcaae2 | 35.7 | 34.8 | 43.5 | 27.69 | 17.66 | 11 | 2 (0 and 0.26 s after the first upload: the start's) | 1.53 | 2.51 |
| storm | c 0d2c4802 | 36.3 | 35.1 | 46.0 | 27.61 | 15.64 | 17 | 8 (2 at the start, then ~1 every 5 s) | 1.48 | 2.62 |
| marina | a 0d2c4802 | 46.3 | 26.8 | 32.1 | 21.43 | 13.63 | 10 | 3 (start) | 1.26 | 2.60 |
| marina | b 7cfcaae2 | 45.3 | 27.7 | 31.0 | 21.63 | 14.69 | 11 | 3 (start) | 1.35 | 2.63 |
| marina | c 0d2c4802 | 46.0 | 27.1 | 31.8 | 21.48 | 14.23 | 9 | 2 (start) | 1.29 | 2.60 |

**Storm.** On 7cfcaae2 the only `Sailing_WaterUploads` over 20 ms are the start's two. On main 0d2c4802 the periodic
reconfigure still costs 26-31 ms about every 5 s. On 7cfcaae2, `Sailing_WaterDetailConfigure` runs 6 times on
Background Workers #1, #2, #3, #6 and #9 (twice on #9). Game-thread frames over 40 ms fall from 17-20 to 11. fps is
1 lower (35.7 against 36.3-36.7), which is within the PC's run-to-run spread for the storm. The GPU slices are the same.

**Marina.** 7cfcaae2 is 0.7-1.0 fps under A (45.3 against 46.0-46.3), just past A's own 0.3 fps spread. GPU is
0.15-0.2 ms higher, p99 is 0.6-0.9 ms higher, and frames over 40 ms are 11 against 9-10. That is small, and #690 does
nothing on the marina's calm water beyond the start.

The end screenshots are the same scene: houses, trees, docks, the marina's boats, the clouds and the boat's wake are
all there. Nothing is missing from the marina.

## Sunfish still (lake, 12 kn, day; `stills/sunfish-lake-day.png`)

The Sunfish draws with its hull, rig, rainbow sail, wake and spray. The log has no default-material, WorldGridMaterial
or missing-mesh warnings for the Sunfish. It does have:
- the known optional `S_*` samples (11);
- two engine ensures that every launch has: PSO precache not called, and DoubleFloat origin precision on the first frame.

The frigate and the J-Class are not in `EBoatType` yet (J22, Sunfish, ILCA7, Catalina22, Catalina30, Hobie16,
Corsair880, Lagoon42, Maxi), so `-SailingBoat` can't pick them and there are no stills of them.

## Found while reading the log (older than this main)

Every Windows package logs `LoadPackage: SkipPackage ... does not exist on disk or in the loader` for these:
- `/Game/Materials/M_BowWave`;
- 45 `/Game/Audio/Pack/...` sounds;
- `/Game/Boats/Catalina22/SM_Catalina22_TillerExt` and `/Game/Boats/Catalina30/SM_Catalina30_TillerExt`.

That includes 7cfcaae2, 0d2c4802, 62a84cc7 and da3e74b0. M_BowWave and the audio pack are in git (Content/Materials,
Content/Audio/Pack), but the cook leaves them out, because they are loaded by path at runtime and their folders aren't
in `DirectoriesToAlwaysCook`. So the Windows packages draw no bow-wave curl and play the synth voices instead of the
recorded pack.

The Catalina tiller extensions don't exist at all, and the code asks for them with `LOAD_NoWarn`, which is harmless.
