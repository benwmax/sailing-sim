# The nightly Mac bench (#401)

PRs merge on fast checks (both compilers build, unit tests and physics checks pass); the full Mac bench runs once a
night on main instead. `nightly.sh` runs `scripts/gate.sh --scope all --force` on `origin/main` in its own worktree
(`Artifacts/wt-nightly`), holding the Mac lock (`scripts/mac-lock.sh`, owner `nightly <date>`), and writes:

- `Artifacts/nightly/<date>.csv`: the sweep (every view, Low, Medium, High);
- `Artifacts/nightly/<date>.gate.txt` and `<date>.log`: the gate's output and the script's log;
- `Artifacts/nightly/latest.txt`: one line, `PASS`, `TESTS FAILED` (naming the failed tests, #404: the first hour's
  scripted runs are among them), `FLOOR BREAK` (with the views under Medium 60 / High 45), `SKIPPED` (with why),
  `STALLED` (with why, when and the last log lines) or `ERROR`.

A watchdog ends the gate and writes `STALLED` when its logs show no progress for 20 minutes (`NIGHTLY_STALL_S`) or it runs
past 4 hours (`NIGHTLY_LIMIT_S`; a whole night takes under one). Progress is the number of log lines other than the
editor's idle noise (its iPhone probe every 10 s, the hourly cache maintenance), summed over the gate's logs, the build,
test and package logs and the game's: on Nov 1 and Nov 6 2026 the test editor sat six hours on frame 0 behind a macOS
dialog (Documents folder access for the editor's Home screen, turned off in `scripts/test.sh` since) while that noise kept
its log growing. It then ends the packaged game too and drops the lock. `bash scripts/nightly/nightly.sh --self-test`
runs the watchdog on stand-in jobs in about 20 s (no gate, no lock).

A view under its floor is benched once more, alone, in the same run (`<date>.rerun-<view>-<tier>.txt`). If every view the
gate counted passes on its rerun the night is `PASS main <sha> (flapping: storm High: first 44.8, rerun 45.6)`; a view
under on both readings, or one the gate lost, makes it `FLOOR BREAK`, with the reruns listed. A view sitting on its floor
reads either side of it from run to run (storm High: 44.7 to 45.6 in one session on Nov 2 2026, the same before and after
the merges first suspected), so one reading under it doesn't flag the night.

It skips the night (a `SKIPPED` line) when the screen is locked (the game can't open its window) or the Metal toolchain
is missing (after an Xcode update: `xcodebuild -downloadComponent MetalToolchain`).

A floor break means revert only the PR that broke it; a swing within 2 fps is noise, so the view is benched again once
first (`ONLY=<view> scripts/bench-visual.sh 12 <label> High` on the night's package in `Artifacts/wt-nightly`).

## Installing it (once, by hand: a scheduled job is Bean's to add)

The live copy runs from `Artifacts/nightly/` (git-ignored), so a branch checkout never changes the running job:

```bash
mkdir -p ~/myProjects/sailing-sim/Artifacts/nightly
cp scripts/nightly/nightly.sh scripts/nightly/com.benwmax.sailing-nightly.plist ~/myProjects/sailing-sim/Artifacts/nightly/
cp ~/myProjects/sailing-sim/Artifacts/nightly/com.benwmax.sailing-nightly.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.benwmax.sailing-nightly.plist
```

After a change to `nightly.sh` is merged, copy it over the live one again (the first line above; the plist is unchanged).
It runs daily at 03:00 local time (launchd's `StartCalendarInterval`). Off again:
`launchctl bootout gui/$(id -u)/com.benwmax.sailing-nightly`. Keep the Mac unlocked overnight (System Settings > Lock
Screen: require a password after the display turns off: Never); a sleeping display is fine.
