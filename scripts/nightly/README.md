# The nightly Mac bench (#401)

PRs merge on fast checks (both compilers build, unit tests and physics checks pass); the full Mac bench runs once a
night on main instead. `nightly.sh` runs `scripts/gate.sh --scope all --force` on `origin/main` in its own worktree
(`Artifacts/wt-nightly`), holding the Mac lock (`scripts/mac-lock.sh`, owner `nightly <date>`), and writes:

- `Artifacts/nightly/<date>.csv`: the sweep (every view, Low, Medium, High);
- `Artifacts/nightly/<date>.gate.txt` and `<date>.log`: the gate's output and the script's log;
- `Artifacts/nightly/latest.txt`: one line, `PASS`, `FLOOR BREAK` (with the views under Medium 60 / High 45),
  `SKIPPED` (with why) or `ERROR`.

It skips the night (a `SKIPPED` line) when the screen is locked (the game can't open its window, and on Nov 1 2026 even
the headless test editor stalled for six hours until the screen was unlocked) or the Metal toolchain is missing (after
an Xcode update: `xcodebuild -downloadComponent MetalToolchain`).

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

It runs daily at 03:00 local time (launchd's `StartCalendarInterval`). Off again:
`launchctl bootout gui/$(id -u)/com.benwmax.sailing-nightly`. Keep the Mac unlocked overnight (System Settings > Lock
Screen: require a password after the display turns off: Never); a sleeping display is fine.
