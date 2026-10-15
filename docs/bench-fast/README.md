# Bench-fast: a faster Mac gate

The Mac gate now runs only what a change can affect. `scripts/gate.sh --scope <area>` benches the views of that area on
Medium and High, skips the build, the tests and the package when their inputs are unchanged, and runs the 12 slowest
physics tests only when the physics, the tests or the terrain bake changed. A scoped gate after a game-code change took
**9.4 min** against **19.4 min** for today's hand-scoped gate of #50 and #52 (a similar change), and **26.6 min** for a full gate. The
measurement is unchanged: the same 3 s warm-up, 12 s window and GPU slices, one packaged launch per view.

```bash
scripts/gate.sh --scope clouds --baseline Artifacts/visual-bench-<last>.csv
```

## Timings

Measured on Bean's M5 Pro, Oct 15 2026, same tree and build for each pair.

| Run | Old | New | What changed |
|---|---|---|---|
| Full test suite (135 tests) | 11.5 min | 11.5 min | Unchanged when the physics changed; see the next row otherwise |
| Tests when the physics, tests and terrain are unchanged | 11.5 min | 1.3 min | 123 tests; the 12 heavy ones already passed on these inputs |
| Tests or package when nothing changed | 11.5 + 2.3 min | 0 | Content hash of their inputs |
| Full sweep (12 views x Low/Medium/High) | 12.4 min | 12.4 min | Still the default for `--scope all` |
| Clouds-scoped bench (8 views x Medium/High) | none | 5.5 min | Scope plus three sentinel views |
| A clouds gate after a code change (build, tests, package, bench) | 19.4 min | 9.4 min | Old: today's gate of #50 and #52 (7 views x 2 tiers); new: `--scope clouds` on this branch |
| Full gate (build, tests, package, full sweep) | 26.6 min | 26.6 min | Run it daily and before every blind round |

The scoped gate in the table (`--scope clouds` after a change to the game module): build 19 s, light tests 76 s,
package 135 s, bench 332 s, 562 s in all. Re-gating the same tree is the bench alone: 5.5 min.

## Scopes

| Scope | Views (plus helm-eye, slip and coast-day) | Tiers |
|---|---|---|
| `clouds` (`sky`) | beam8, beat15, storm, gulf-sea, bridge | Medium, High |
| `water` | beam8, beat15, storm, marina, gulf-sea, bridge | Medium, High |
| `boats` | beam8, beat15, marina, crew | Medium, High |
| `crew` | beat15, crew | Medium, High |
| `world` | marina, bridge, coast-night, marina-night | Medium, High |
| `night` | coast-night, marina-night | Medium, High |
| `ui` | beam8 | Medium, High |
| `all` | all 12 | Low, Medium, High |

helm-eye, slip and coast-day run in every scope: they are High's tightest views (about 1 fps over 45 after W2), so any
change can push them under. The gates stay Medium 60 fps and High 45 fps; the gate prints every view against them and
against `--baseline`.

## What else the gate does

- **Skips work by content hash.** Build: `Source`, `Config`, `Plugins`, the `.uproject`. Package and tests: those plus
  `Content`. Each file's git blob id counts, including uncommitted and new files, so committing the same files changes
  nothing. Hashes live in `Artifacts/gate/`; `--force` ignores them.
- **Splits the tests.** The 12 tests listed in `scripts/gate-heavy-tests.txt` take 600 of the suite's 655 s: the fleet
  polars, the reference checks, the long passage and the AI race. They read only the physics, the tests and the terrain
  bake, so they run only when one of those changed since they last passed. Any change under `Source/SailingSimTests`
  re-runs everything, so new tests are never skipped.
- **Gates PRs in a batch.** `--merge <branch> ...` makes `gate-<date>` from origin/main with each branch merged in, then
  builds, tests, packages and benches once for all of them.
- **The PC pre-screens (process, no code).** Cloud and material candidates are screened on the 4090 first
  (`scripts/windows/bench-visual-win.ps1`); the Mac gates only the finalist, with its scope.

## What did not work: many views in one process

The plan was one packaged launch per tier running every view in-process. I built that and kept it as an option
(`FAST=1` in `bench-visual.sh`, `LIST=` in `bench-mac.sh`): `USailingBenchRunner` (`BenchRunner.h`) swaps the command
line, puts back the settings' class defaults, the session and any console variable a view changed, collects garbage
and reloads the map. `SailingSim.Smoke.BenchList.*` tests the reset.

It measures the same as fresh launches while it lasts: the first 4 to 7 views of every list matched the old harness
within about 1 fps on every tier. But on some runs, and not others, the render and RHI threads slowed from one view to
the next. RHI time went from 1.8 ms to 6 to 22 ms with the GPU's own time unchanged, and later Medium views lost up to
70%. It is not memory (flat at about 8 GB), not window focus, not the storm view and not the frame trace. A full garbage
collection between views stopped it carrying over but not starting. The engine's RHI resource tracking is compiled out
of this build, so the cause is still open.

It also saves little. A launch costs only about 3 s against 17.4 s of warm-up, window and GPU profile:

| Full sweep, 36 runs | Wall time |
|---|---|
| One launch per view (the default) | 741 s |
| One process per tier | 664 s, but wrong on 15 of 36 views |
| Four views per process, slowed views re-run alone | 855 s |

The guarded list (`FAST=1`, `CHUNK=4`) re-runs alone any view whose RHI time rises past 1.5x (+0.5 ms) of its launch's
first view. Its numbers matched the old harness on every view. The table below and the CSVs beside this README show the
three runs on one build: `sweep-old-harness.csv`, `sweep-list-one-process.csv`, `sweep-list-chunked.csv` and
`sweep-list-gc-low.csv`.

## The warm-up stays at 3 s

With `-SailingBenchTrace` every frame from the start is saved (`<shot>.frames.csv`). Frames settle after about 1 s.
But moving the 12 s window to start at 1.5 s instead of 3 s moved its mean by about 1% on most views and by up to 4% on
some, most often faster. That is about 0.5 fps on High, where the margin is about 1 fps, and it would break
comparability with earlier CSVs. `-SailingBenchWarmup=<s>` exists for experiments; the benches don't use it.

## Stills

Every run already writes its screenshot one second before its window closes (`<view>-<tier>.png`), so no extra
capture runs are needed.

## The same numbers, old and new

| View | Tier | Old harness fps | One process fps (RHI ms) | Chunked + guard fps |
|---|---|---|---|---|
| beam8 | Low | 102.6 | 103.1 (1.77) | 102.7 |
| beam8 | Medium | 87.6 | 87.7 (2.34) | 87.8 |
| beam8 | High | 54.1 | 54.3 (3.17) | 54.2 |
| beat15 | Low | 107.9 | 107.2 (1.87) | 107.6 |
| beat15 | Medium | 87.4 | 87.0 (2.58) | 87.5 |
| beat15 | High | 52.2 | 52.0 (3.33) | 53.2 |
| storm | Low | 110.9 | 110.7 (2.78) | 110.8 |
| storm | Medium | 67.3 | 66.6 (3.09) | 67.5 |
| storm | High | 49.5 | 49.1 (3.46) | 49.1 |
| marina | Low | 103.1 | 103.5 (3.74) | 103.3 |
| marina | Medium | 89.1 | 88.7 (3.12) | 88.9 |
| marina | High | 49.3 | 49.7 (4.12) | 48.5 |
| coast-day | Low | 106.3 | 84.7 (7.68) | 106.1 |
| coast-day | Medium | 80.5 | 80.0 (2.71) | 80.9 |
| coast-day | High | 47.0 | 46.3 (6.98) | 46.9 |
| coast-night | Low | 73.9 | 77.2 (9.3) | 97.0 |
| coast-night | Medium | 100.8 | 99.6 (3.71) | 100.7 |
| coast-night | High | 50.7 | 50.8 (5.88) | 51.2 |
| gulf-sea | Low | 119.0 | 68.5 (8.24) | 119.0 |
| gulf-sea | Medium | 104.1 | 103.7 (2.91) | 105.7 |
| gulf-sea | High | 59.9 | 59.4 (3.64) | 59.9 |
| helm-eye | Low | 102.0 | 69.3 (9.0) | 102.2 |
| helm-eye | Medium | 79.8 | 74.9 (6.74) | 81.6 |
| helm-eye | High | 46.3 | 46.0 (4.45) | 46.2 |
| slip | Low | 98.6 | 57.7 (9.94) | 98.0 |
| slip | Medium | 77.6 | 40.9 (13.93) | 77.6 |
| slip | High | 50.2 | 49.8 (5.53) | 49.8 |
| bridge | Low | 117.9 | 46.3 (12.68) | 118.0 |
| bridge | Medium | 96.5 | 28.6 (20.61) | 96.7 |
| bridge | High | 41.5 | 54.0 (5.81) | 53.8 |
| crew | Low | 113.0 | 41.9 (14.03) | 112.4 |
| crew | Medium | 70.8 | 25.7 (22.52) | 70.9 |
| crew | High | 48.9 | 48.5 (8.83) | 48.4 |
| marina-night | Low | 90.0 | 50.0 (11.48) | 88.9 |
| marina-night | Medium | 82.6 | 35.1 (16.36) | 82.6 |
| marina-night | High | 53.2 | 52.3 (5.94) | 52.6 |

Two of the old harness's own runs were outliers: coast-night Low at 73.9 and bridge High at 41.5, with a 70 ms p99.
Both read normally (97 and 54) in every other run.

## bench.json additions

- `foreground`: the share of the window's frames with the game in front.
- `mem_used_mb`, `mem_peak_mb`, `tex_mem_mb`: the process's memory at the end of the window.
- `view_wall_s`: in a list, the view's time from load to result.

Each view also brings the game's window to the front when its window starts.
