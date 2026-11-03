# Ready About: Sailing, tester kit (the Nov 7 build)

For the testers of the first Friday build, and for Bean handing it to them. The install and controls card that goes in
the zip is [`docs/windows/TESTER-GUIDE.md`](../windows/TESTER-GUIDE.md); this page is the wider brief. Written from main
aafcb21d (Nov 3 2026); the build's own `BUILD.md` says exactly which commit it is.

## What's in it

The vertical slice (#399): one lake, three boats and the first career tiers, in a slice build that hides the rest.

- **Lake Ray Hubbard**, sailing from Rush Creek Yacht Club. **Galveston Bay** opens with the Day Sailor certificate (the
  stretch, #407).
- **Boats:** the J/22 from the start, the Sunfish with Club Racer, the Catalina 22 with the Day Sailor certificate. The
  Catalina 22 now has her deck hardware up close: chainplates and turnbuckles on the shrouds, the mast step, the
  stemhead, cabin-top vents and cockpit scuppers.
- **Career:** the first job (a guided first sail with an instructor), then **Day Sailor** (six lessons, a checkride and a
  certificate) and **Club Racer** (four Sunfish lessons), which opens after Day Sailor's first three lessons. Coastal
  Cruiser shows as "Coming".
- **Free Sail** (the title's Mode switch): every place and boat the build has, no medals.
- **Easy sailing or Realistic** (asked on the first launch, changed in Settings > Gameplay). Easy helps with the helm and
  trim and earns up to silver; gold needs Realistic.
- **Send feedback** from the pause menu (below), and crash reports if you turn them on.

Not in it: Race and Passage, Marseille, the Texas coast, the other boats and the developers' Gallery.

## Install and start

Windows 10 or 11, 64-bit, a DirectX 12 graphics card, about 10 GB free.

1. Unzip `ReadyAbout-<build>-Win64.zip` into a folder of its own.
2. Run `SailingSim.exe` (the program keeps its working name). Test builds aren't signed: if SmartScreen stops it, choose
   More info, then Run anyway.
3. If it says the Microsoft Visual C++ Redistributable is needed and asks to install it, choose Yes: the installer is in
   the zip, and most PCs that play games already have it. A current graphics driver helps (NVIDIA, AMD or Intel's own).
4. The first launch compiles shaders for your card: the title can take a few minutes, and the first minute on the water
   can stutter. Once per build.

A pad (Xbox layout) works everywhere. On the water `/` (or a tap of View) shows the controls card; Settings > Controls
changes any key.

## The first hour

1. **First launch:** two questions (picture quality, pre-picked for your card, and Easy or Realistic), then Start your
   first job. Skip to the menu if you like: the job waits on the Career screen as a First job card.
2. **The first job:** the J/22 already sailing off Rush Creek; the instructor asks for one thing at a time (steer, ease
   and trim the main, sail upwind, tack, stop). It never fails: if you don't answer, the instructor shows you. About seven
   minutes.
3. **Day Sailor:** Career, then the lessons in order, each started from its row. Every lesson opens with a briefing, sails
   its drill on the lesson day (8 to 10 kn, no traffic) and ends with a short quiz; the finish panel offers the next
   lesson. A medal plus a passed quiz closes a lesson; silver in all six and the written checkride earn the certificate.
4. **Club Racer** opens after Leave the dock, Sail a triangle and Heave to: the Sunfish, singlehanded, with her own
   lesson text and questions.

`SailingSim.Slice.FirstHour` plays this hour on the game's physics every build: the first job, all six Day Sailor
lessons (silver or gold), the checkride and the certificate.

## Sending a bug or an idea

In the game: **pause (Tab, or Menu on the pad) > Send feedback**, choose Bug or Idea, give it a title and a few lines (for
a bug, what you expected instead) and send. It takes a picture of the view at that moment and, if you agree, the last
minute of the boat's numbers (speed, wind, controls). No name, account or other screenshots.

- With Settings > Gameplay > **Send crash reports** on, the report goes straight to the developer.
- Off, it's kept on your computer in `%LOCALAPPDATA%\SailingSim\Saved\Feedback`: zip that folder and send it.
- After a crash, send `%LOCALAPPDATA%\SailingSim\Saved\Crashes` too (a folder per crash).
- The game keeps its own log in `%LOCALAPPDATA%\SailingSim\Saved\Logs\session.txt`. It records the build, your PC's
  graphics card and settings, where and what you sailed (world, boat, weather, Easy or Realistic), each lesson's start
  and result, and any warnings. A bug report and a crash report attach its last lines for you; it has no name, e-mail
  or home folder in it. The last five launches are kept (`session-1.txt` is the one before). If a report didn't send,
  or the game froze, zip `...\Saved\Logs` with it.

Anything is worth sending: a crash, a boat that does what a real one wouldn't, a lesson or menu that confused you, a slow
frame rate (say the Settings > Graphics tier), and what you enjoyed. Say the build number from the title screen.

## Known issues

Fixed since the first zip (Nov 2): a Sunfish left in irons, or pressed against a pier, could fly off at hundreds of knots
and then crash the game (Rush Creek) or freeze it (Galveston). If you see a boat go suddenly wild, report it with the
session log: it notes the moment a boat's numbers go wrong ("Boat state diverged").

- **Leave the dock:** backing out of the J/22's slip, the hull can brush the finger pier she was tied to. The slip is
  barely wider than the boat. A brush under 1 knot still counts as a clean departure; back out slowly.
- **Replays** on the title is greyed until you've sailed a run this session: runs aren't kept between launches.
- The first launch's shader compile (above) happens again with each new build.
- Every lesson has been sailed by script and by a scripted helmsman, not yet by hand on a pad from start to finish: tell
  us if a lesson asks for something the pad can't do easily.
- The first-hour audit (#400, `docs/slice-audit/`) found 21 problems; all are fixed in this build. Anything that looks
  like one of them is worth a report.
