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
- [ ] **VC++ prompt:** it appears only on a PC without the Visual C++ 2015-2022 runtime (the 4090 PC has it, so expect
      none). If a spare PC or VM is to hand, run the zip there: choose Yes at the prompt and the game starts. Otherwise
      check the zip has `Engine\Extras\Redist\en-us\vc_redist.x64.exe`.
- [ ] **First job:** play it through; the caption says Instructor, the loading screen "Your first job".
- [ ] **One lesson on the pad:** Day Sailor's Leave the dock with the controller only: cast off, back out, sail clear,
      the quiz, the finish panel's Next lesson. Note anything the pad couldn't do.
- [ ] **Mode screen on the pad:** Free Sail through to the Mode screen, then on the Mode choice press Right (Learning
      to Game) and Down: the focus stays on Mode, then moves on (it used to jump to the mode cards).
- [ ] **Settings:** change the quality tier and Easy / Realistic; quit and relaunch: both kept. Controls: rebind one key,
      check it works, reset it.
- [ ] **Send feedback:** pause > Send feedback, a Bug with a title; it says sent (crash reports on) or kept on this
      computer (off), and the folder is in `Saved\Feedback`.
- [ ] **Session log:** `Saved\Logs\session.txt` exists and starts with the build stamp matching `BUILD.md`; it has a
      `Session:` line for the map you sailed and the first job's `first-job done in ... s` line; no Windows user name in
      it. The kept feedback report includes its tail.
- [ ] **Sunfish in irons:** Free Sail, the Sunfish at Galveston on Easy, head to wind and hands off for five minutes
      beside the pier: she stays put, no freeze (the Nov 2 zip's hang). Note SailingSim's memory in Task Manager at the
      start and after the five minutes: it should barely move (it used to climb about 3 MB a minute on High and Ultra). Then the Catalina 22 at the dock: the new deck
      hardware is there (turnbuckles, mast step, vents).
- [ ] Put the real `Saved` folder back.

## 3. Hand over

Send the zip and `BUILD.md` to the testers with [README.md](README.md). Note in `BUILD.md` anything the hand checks
found, and open an issue for each (label `slice`).
