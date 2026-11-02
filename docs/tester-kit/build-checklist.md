# Friday build checklist (for Bean)

The Friday tester build from main, on the RTX 4090 PC, then the checks only a person can do. About an hour, most of it
the cook. Tester brief: [README.md](README.md).

## 1. Build

1. On the PC, in the repo, with nothing tracked changed: `scripts\windows\friday.ps1`. It:
   - checks out origin/main detached (`-Commit <sha>` for another; `-NoCheckout` for a dry run of what's checked out);
   - builds, and full-cooks a Shipping package into `Packaged\Shipping-<commit>` as a **slice build** (the testers'
     menus; `-FullGame` leaves the switch out), with the build stamp on the title screen;
   - runs its smoke checks by launch arguments only (Title > Gallery with the slice off, two Ultra lake benches);
   - writes `Packaged\ReadyAbout-<commit>-Win64.zip` with `TESTER-GUIDE.md`, and `BUILD.md` beside the package (commit,
     date, fps, the checks, what merged since the last Friday build);
   - adds the Sentry DSN from `Artifacts\sentry\dsn.txt` for the cook only, and uploads symbols when sentry-cli is set up.
2. Read the result line in `Artifacts\friday-<commit>.txt` and `BUILD.md`. Any failed step: stop and send the log.

## 2. Hand checks (on the unzipped build, not the package folder)

Unzip the zip somewhere new, as a tester would, and run `SailingSim.exe` from there.

- [ ] **Fresh save:** rename `%LOCALAPPDATA%\SailingSim\Saved` aside first (put it back after), so the game starts as
      a new player's.
- [ ] **First launch:** the first-launch screen opens (school name, two questions); quality is pre-picked for the card.
      Skip to the menu once: the Career screen shows the First job card. Then start the first job from it.
- [ ] **Title:** the logo reads READY ABOUT / SAILING; the window title is "Ready About: Sailing"; the **build stamp** in
      the corner matches `BUILD.md`'s commit and date. No Race, no Gallery (slice build). Replays is greyed.
- [ ] **World and Boat screens:** only Ray Hubbard and Galveston Bay; only the J/22, Sunfish and Catalina 22, with
      their lock reasons.
- [ ] **First job:** play it through; the caption says Instructor, the loading screen "Your first job".
- [ ] **One lesson on the pad:** Day Sailor's Leave the dock with the controller only: cast off, back out, sail clear,
      the quiz, the finish panel's Next lesson. Note anything the pad couldn't do.
- [ ] **Settings:** change the quality tier and Easy / Realistic; quit and relaunch: both kept. Controls: rebind one key,
      check it works, reset it.
- [ ] **Send feedback:** pause > Send feedback, a Bug with a title; it says sent (crash reports on) or kept on this
      computer (off), and the folder is in `Saved\Feedback`.
- [ ] Put the real `Saved` folder back.

## 3. Hand over

Send the zip and `BUILD.md` to the testers with [README.md](README.md). Note in `BUILD.md` anything the hand checks
found, and open an issue for each (label `slice`).
