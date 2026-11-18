# Shipping canary at main ad60911e, Nov 18 2026 (PC)

**Result:** a Friday-style Shipping build of main's tip builds, packages, starts and runs a 60 s bench cleanly on
Bean's PC (RTX 4090).

**What was built:**

- Same steps as `friday.ps1`: editor build, version stamp `ad60911e, Nov 18 2026 canary`, Sentry DSN staged into
  WindowsEngine.ini by variable, slice switch, full cook.
- Release `sailing-sim@ad60911e-canary`, environment `canary`.
- No zip. Output: `Packaged\Shipping-ad60911e-canary`, so it can't be taken for the Nov 20 candidate.
- The ini was restored byte for byte afterwards. The worktree's Config and Content were clean, and the main checkout was untouched (40226d1c, clean).

## Build and package

| Step | Result |
|---|---|
| Editor build | Succeeded, 0 errors (3 min) |
| DSN staged | yes, a quoted https URL (value not recorded) |
| Package (`package-win.ps1 -Config Shipping -Full`) | exit 0, 226 s full cook (4 min) |
| Package size | 4.58 GB |

## Runs

Both runs used `-SailingShippingSmoke -SailingWorld=Lake -SailingLaunch=1 -SailingBench=60 -windowed -ResX=1920 -ResY=1080 -NoCrashReporter`.
Each had a fresh Saved; Bean's Saved was held aside and restored (profile hash checked).

| | warm (first launch) | smoke (measured) |
|---|---|---|
| Launcher exit | 0 | 0 |
| Wall time | 120 s | 73 s |
| Launch to session log | about 4 s | about 3 s |
| Session log to bench start (world ready) | 5.3 s | 3.7 s |
| fps (60 s) | 88.3 | **111.2** |
| mean / p99 / max ms | 11.32 / 16.99 / 33.05 | **8.99 / 13.58 / 22.83** |
| GPU frame ms | 8.06 | 8.00 |
| game / render / RHI ms | 10.12 / 10.12 / 6.19 | 7.27 / 8.08 / 5.48 |
| Memory used / peak MB | 3,537 / 3,539 | 3,128 / 3,522 |
| Crashes | 0 | 0 |
| Speed at the end | 3.96 kn | 4.04 kn |

**Start-up:** about 7 s from launch to the first measured frame on the second launch, and 9 s on the first.

**Start-up problems:** none.

- The session log has no errors, warnings or ensures (the Shipping log carries none of the engine's lines).
- No crash folders in either run's Saved. Each run made the usual empty `CrashReportClient.ini`.
- The first launch spent about 37 s after its bench before exiting. It finished at 00:11:24 and its pipeline cache was written at 00:12:01, so this was likely the first PSO cache save. The second launch exited 4 s after its bench.
- The first run's lower fps is the warm-up (shader and PSO compiles), as on earlier canaries.

**Ensures and asserts:** none in either session log. The Shipping build has no engine log to check further.

**Sentry:** the session log has no Sentry lines, so the event count can't be read from the log. Nothing in the logs
points to an event: no crash or ensure. The runs' `.sentry-native` folder was not read.

## Files

- `status.txt`: the canary script's steps
- `warm/` and `smoke/`: each run's `bench.json` and `session.txt`
- `smoke/canary-smoke.png`: the smoke run's end screenshot
