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

## Packaging: incremental cook, and no rebuild when the code is unchanged

`scripts/package-mac.sh` now keeps the cooked output (`Saved/Cooked/Mac`, a Zen store) between runs and passes
`-cookincremental`. UE 5.8's incremental cook checks each package's dependencies (the package, its classes' schemas,
the config it reads, the packages it references) and re-cooks only those that changed. Until now every package deleted
the store and cooked all 4,142 packages, because `CookIncrementalDefaultIncremental=false` is the engine default.
`FULL=1 scripts/package-mac.sh` restores that: it deletes the store, recooks everything and rebuilds the game.

The cook turned out to be a small part of a package. With the DDC warm, a full cook of this project is 25 s; most of a
package is elsewhere. With this installed engine, the build step recompiled 32 files of the game target on every run,
about 30 s, even when nothing had changed. UnrealBuildTool regenerates the target's makefile every time (this engine
has no `ISPC/bin/Mac/ispc`, which UBT lists as a dependency of every target) and rewrites its shared-PCH response files
with a different set of engine `UHT` include paths each time, so the PCHs and everything after them count as outdated.
I tried a stub ispc in the engine: it stops the "ispc deleted" message but not the response-file churn, so I removed it.
The script now skips the game build (no `-build`) when `Source`, `Config`, `Plugins` and the `.uproject` hash the same
as at the last successful package (`Artifacts/package-code.hash`; `inputs_hash` moved to `env.sh` and is shared with
`gate.sh`). After a code change it builds as before.

Measured on Bean's M5 Pro, Oct 15 2026, same tree:

| Package | Wall time | Build step | Cook step | Packages cooked |
|---|---|---|---|---|
| Full (`FULL=1`, as every package before) | 136-138 s | 31 s, 32 compiles | 25.6 s | 4,142 |
| Incremental, nothing changed (code unchanged: build skipped) | **87 s** | none | 10.5 s | 1 |
| Incremental after a change to a game-module .cpp | 126-128 s | 33 s | 15.6 s | 1 |
| Incremental, nothing changed, before the build skip | 110-132 s | 31-33 s | 15.5-24.8 s | 1 |

So the incremental cook saves 10-15 s, and skipping the unchanged build saves about 30 s more. A package where only
`Content` changed (a material, a bake, a model) now takes about 90 s instead of 137 s. A package after a code change is
about 10 s faster. In both, about 55 s remains in staging, IoStore (19 s to compress the 3.3 GB container) and the
archive copy.

**Same game.** The incremental package's containers are byte-identical to the full package's (SHA-256 of
`SailingSim-Mac.ucas`, `.utoc`, `.pak`, `global.ucas`, `global.utoc`). The packaged game starts and benches the same.
Here are the clouds scope's views, one launch each, 12 s windows, on a full package and on an incremental one after a
code change and its revert:

| View | Tier | Full fps | Incremental fps | Difference |
|---|---|---|---|---|
| beam8 | Medium | 90.2 | 90.0 | -0.2 |
| beam8 | High | 55.0 | 54.8 | -0.2 |
| beat15 | Medium | 86.5 | 86.1 | -0.4 |
| beat15 | High | 50.9 | 51.0 | +0.1 |
| storm | Medium | 72.0 | 72.0 | +0.0 |
| storm | High | 50.2 | 50.7 | +0.5 |
| coast-day | Medium | 82.8 | 81.4 | -1.4 |
| coast-day | High | 47.7 | 47.0 | -0.7 |
| gulf-sea | Medium | 106.0 | 105.2 | -0.8 |
| gulf-sea | High | 61.2 | 57.5 | -3.7 |
| helm-eye | Medium | 81.1 | 80.6 | -0.5 |
| helm-eye | High | 47.1 | 44.8 | -2.3 |
| slip | Medium | 79.1 | 77.1 | -2.0 |
| slip | High | 46.9 | 47.2 | +0.3 |
| bridge | Medium | 98.7 | 98.5 | -0.2 |
| bridge | High | 55.1 | 53.5 | -1.6 |

The files are identical, so the differences are run-to-run noise. The full run went last and was a little faster on
a few High views. An earlier incremental run of the same content (`visual-bench-cook-inc0.csv`) gave helm-eye High 45.1
and gulf-sea High 57.7. Today's PR #53 gate gave helm-eye High 46.2 and 45.7 on the same views a few hours apart. The
CSVs are `Artifacts/visual-bench-cook-{full,inc,inc0}.csv`.

When to use `FULL=1`: after an engine update, if a cook warning mentions stale or invalidated packages, or for a
release build.

## Less of it (Oct 18 2026)

Bean asked for faster gates. A scoped gate was running 14 launches (7 views on Medium and High), about 5 min of bench
on every PR, including ones that changed only docs. Three cuts, measured against the sweeps in this folder and the
gate CSVs since:

- **High only, plus the storm view on Medium.** Across every sweep since bench-fast, the lowest Medium view is the storm
  at 67-69 fps (floor 60); every other Medium view has 13 fps or more in hand, while High has under 1 fps on the storm
  and a few on the sentinels. A change that takes 7 fps off Medium takes far more off High first. Medium's storm run
  is appended to the gate CSV from a second `bench-visual.sh` call (`<label>-medium`).
- **One sentinel, not three.** helm-eye runs in every scope; slip (the marina with the player's boat) runs in boats,
  crew and world; coast-day (the bay shore) in water and world.
- **No bench when the packaged game did not change.** The bench reads only `Packaged/Mac`, whose inputs are the package
  hash (Source, Config, Plugins, Content). A scope that passed on that hash keeps its result
  (`Artifacts/gate/bench-<scope>.hash` and `.csv`, written only on a pass; `--force` or `--baseline` rerun it).

A boats gate goes from 14 launches to 6 (about 2 min of bench), a ui gate to 2, and a docs-only PR to a few seconds.
`--scope all` is unchanged: every view on Low, Medium and High, daily and before a blind round.

Two test-side skips (Oct 18 2026, gate-test-skips, on top of the above): the credits-screen gate spent 683 of its
952 s on tests because editing one UI test changed the heavy tests' hash (it covered all of `Source/SailingSimTests`).
The heavy tests now key on their own five files (`OceanTests`, `FleetTests`, `ReferenceTests`, `PhysicsTests`,
`TrafficTests`) plus the physics, so another test edit runs the other ~150 tests in about 70 s. Package and bench key
on the game without the editor-only tests module (`GAME_HASH`), so a change to the tests alone is build plus tests,
about 1.5 min.


## Daily sweep, Oct 18 2026

`scripts/gate.sh --scope all` on main c9e6fa9c: **pass**, every view on Low, Medium and High over its floor
([sweep-2026-10-18.csv](sweep-2026-10-18.csv)). Steps: build 21 s; tests 72 s (145 passed: the heavy set had already
passed on these physics inputs, so the gate ran the other 145); package skipped (the packaged game was already this
tree); bench 659 s (36 launches); 12.5 min in all. Tightest views: High storm 50.2 fps (floor 45), High crew 53.2 and
slip 53.4; Medium storm 68.0 (floor 60).

## Against main for a view under its floor (Oct 18 2026)

Storm High made the scoped gate flap: 44.3 to 44.6 fps in the clouds' slow phase, on main and on any branch run back to
back, and 50.2 in a fast launch ([storm-high-2026-10-18.md](../budget/storm-high-2026-10-18.md)). A scoped gate now
treats a view under its floor as a regression question. That view alone (and only views under their floor) is benched
again on this tree and on a package of origin/main, back to back, one launch each, with the same seconds. It passes
as **flapping** when this tree is within 1.0 fps of main (or reaches the floor on the rerun), and fails when it is more
than 1 fps under main.

- **The main package** is `Artifacts/apps/main.app`, keyed by main's `GAME_HASH` in `Artifacts/gate/main.hash`. It is
  packaged in a git worktree, `Artifacts/main-tree` (detached at origin/main, so the working tree is untouched), by this
  branch's `build.sh` and `package-mac.sh` pointed at it with `SAILING_ROOT` (env.sh). The git-ignored MetaHumans are
  APFS-cloned in. It is built only when a view is under its floor and main moved, never when nothing failed.
- **The verdict is kept.** The pair goes into `bench-<scope>.csv` as `rerun_fps` and `main_fps`, so a rerun that skips
  the bench prints the same verdict. Every main run is also appended to `Artifacts/gate/main-bench.csv`.
- **`--scope all` stays absolute.** It never runs main. A view under its floor fails, and the line names it as flapping
  when the last main run of that view on the current main package was within 1 fps.
- `--no-main-check` turns it off. The bench-skip and heavy-test keys are unchanged.

First run, `scripts/gate.sh --scope clouds` on this branch (main a58eb1ec plus the gate change):

```
[gate 0 s] build
[gate 19 s] tests: the heavy set passed on these physics inputs; 145 others
[gate 95 s] package
[gate 201 s] bench beam8,beat15,storm,gulf-sea,bridge,helm-eye on High, storm on Medium
[gate 331 s] bench done
storm          High      44.6   25.27    21.0  UNDER 45
gate: 1 view(s) under the gate or lost
[gate 338 s] main package: building main a58eb1ec in Artifacts/main-tree
[gate 488 s] back to back with main a58eb1ec: storm High
[gate 543 s] storm High: this tree 45.0, main 44.6
storm          High      44.6   25.27    21.0  under 45, but 45.0 on the rerun beside main 44.6: pass (flapping)
gate: pass, 1 flapping: storm High under 45, but 45.0 on the rerun beside main 44.6
[gate 543 s] gate passed
```

The other views: beam8 58.5, beat15 62.0, gulf-sea 69.5, helm-eye 59.5, bridge 64.5 (High), storm Medium 65.8. The
first main package, from a fresh worktree, took 150 s: the editor build was 34 s (UBA), and the cook was full but fast
on the shared DDC. When main has not moved, the main step is just the two launches, about 55 s. Running the same
command again skipped everything and printed the same table and verdict in about 1 s.
