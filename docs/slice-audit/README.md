# Slice audit: the first hour (#400)

A new player's first hour in the vertical slice (#399): **Lake Ray Hubbard, the J/22 and the Sunfish, Day Sailor and Club
Racer**, Career mode, from a fresh save, on keyboard and controller. Galveston Bay and the Catalina 22 are the stretch
(#407) and stay reachable; they are listed under "Outside the slice" only.

**Status: Part A and Part B done.** Part A comes from the data (`Content/Career/career.json`, `Content/Learning/*.json`) and the menu code
(`SSailFrontEnd`, `ASailingHUD`, `FSailSessionConfig`) at main 964ccdcd. Part B, the scripted play-through with stills, is
pending: each launch brings the game window to the front, and Bean is choosing when the Mac is free. Each finding below
says whether it is **seen** (in a run), or **read** (in code or data, to confirm in the run).

## Fixed since (main 127081ee, #422: docs/first-launch/)

The first-launch build answers findings 1 to 8 and 6's naming; Part B's stills (tonight) check them on the game itself.

| # | Finding | Now |
|---|---|---|
| 1 | Two ways to learn on the title | A new save opens on the first-launch screen and the first job; the title's "ASA 101 drills" item is gone |
| 2 | Five screens from a lesson row | Start lesson casts off from the row (`MakeLesson`) |
| 3 | Easy caps at bronze, no certificate | Easy earns up to silver, enough for the checkride |
| 4 | Light traffic can take the medal | Lessons sail with their own `traffic` (off) |
| 5 | Any weather, same medals | Lessons sail in their own `conditions` (the lesson day) |
| 6 | "ASA 101" in the menus | Gone from the title, Mode card, briefing, quiz footer, preset name and HUD |
| 7 | No quiz retake | Retake the quiz after a lesson; Take the quiz on its Career row |
| 8 | No next lesson | Next lesson and Sail it again on the finish panel |

Still open: 9 (Replays with no run), 10 (Gallery on the title), 11 (Club Racer behind the checkride, a design
question), 12 to 14 (the Sunfish's J/22 text and quizzes, drills a Sunfish can't sail).

## How it was run

- Packaged Development build of main (`Packaged/Mac/SailingSim.app`), 1920x1080 windowed, Medium.
- **Fresh profile.** The container's `Saved/Config` and `Saved/SaveGames` are moved aside for the run and restored byte
  for byte after it (`diff -r` clean), so the game starts as on a new Mac: no `profile.json`, no `GameUserSettings.ini`.
- **Keys.** `-SailingUIScript` sends keys through Slate (menus only; `Gamepad_*` names give the controller's menu path). It
  can't sail: the boat's input is Enhanced Input. The drills themselves need Bean's hand on the keyboard and a pad (list
  at the end). Whether each lesson can be completed is taken from the scripted helmsmen's tests
  (`SailingSim.Drills.SailATriangle`, `SailingSim.Drills.SunfishLessons`, the drill tests).
- **Stills.** Only the game's own screenshot (one launch per screen): never the desktop.

## Ranked blockers (by how early in the first hour they bite)

| # | Minute | Category | Finding | Source |
|---|---|---|---|---|
| 1 | 0 | Unclear objective | The title offers **two ways to learn**: Career (lessons, medals, certificates) and **"ASA 101 drills"** (six drills, "N passed", from the older `DrillsPassed` list). Sail, the free-sail flow, is the first item, and a new player's Enter goes there, not to lessons. Nothing says which one is the course. | read |
| 2 | 1 | Unclear objective | From a Career lesson row to sailing is **five screens and a load**: Launch, Boat, Conditions, Mode, then cast off. Each lets the player wander off the lesson: another boat, a thunderstorm, Free sail or another drill on the Mode screen. The lesson's name isn't carried onto those screens. | read |
| 3 | 1 | Unfair medal | **Difficulty defaults to Easy** (`FSailSessionConfig::bEasy = true`), and Easy earns at most bronze (`easy_max_medal`). The Day Sailor checkride needs silver in every lesson, so a player who never finds the Difficulty switch on the Mode screen can never certify, and never reaches Club Racer. The Career screen explains it only on the checkride line. | read |
| 4 | 2 | Unfair medal | **Traffic defaults to Light** in lessons. Silver and gold ask for zero rules infractions, so an AI boat in the fairway can take the medal on Leave the dock. | read |
| 5 | 2 | Unfair medal | A lesson doesn't set its conditions: the Conditions screen's default is the Lesson day, but any preset (Thunderstorm) earns the same medals against the same times. | read |
| 6 | 3 | Naming | **"ASA 101"** shows in the menus: the title item and the Mode card ("ASA 101 drills"), and the quiz footer ("Questions in ASA 101 wording"). `docs/career/README.md` keeps ASA to the descriptive `learning` text. | read |
| 7 | 10 | No retry | The lesson quiz opens only after a completed drill in Learning mode. Esc ("Skip the quiz"), a failed quiz, or Game mode means **sailing the whole drill again** to retake it; the Career screen has no quiz button for a lesson. | read |
| 8 | 10 | Dead end | After a lesson there is no "next lesson". The way on is pause, Quit to title, Career, the next row, and the five screens again. | read |
| 9 | 0 | Dead end | Title **Replays** with no run in this session: the menus close and nothing plays (`WatchLastRun` does nothing when `LastRun` is empty), leaving the player in the world with no menu. The last run isn't kept across launches. | read |
| 10 | 0 | Developer leftovers | **Gallery** ("Developer · every asset") is on the title by default (`bShowDeveloperTools = true`; an ini line turns it off). | read |
| 11 | 60+ | Slice design | **Club Racer is locked** behind the Day Sailor certificate: six lessons at silver plus a 12-question written test at 80%. A first hour won't reach the Sunfish. | read |
| 12 | 60+ | Missing explanation | **Club Racer's text is the J/22's.** The Sunfish lessons run the keelboat drills with their briefings and coaching: "the crew hoists the sails", jib telltales, "five J/22 lengths", "the J/22 weighs over 800 kg", and on the quick-stop "leave the jib backed" (a Sunfish has no jib). | read |
| 13 | 60+ | Unfair medal | **Club Racer's quizzes ask J/22 questions**, for example qs-02 "During the quick-stop, the jib is:", tri-02 (jib telltales), tri-14 ("a boat like the J/22"), ld-11 ("brief the crew"), dk-03 ("in a keelboat"). 28 questions in the four drills' pools mention a jib, a crew, the J/22 or a keelboat (some still fit a dinghy), and a Sunfish sailor can fail a lesson quiz on them. | read |
| 14 | 60+ | Stuck state | The Mode screen's drill grid offers all six drills on any boat, so **Heave to and the figure-eight on the Sunfish**, which both need a jib to back. | read |

## Outside the slice, reachable from the menus

From the menu code (to confirm with stills):

- **World screen:** Lake Ray Hubbard, Galveston Bay & Gulf, Marseille & Cassis and the Texas coast. In Career on a fresh
  save the last three are greyed with their lock reason: Galveston and the Texas coast open with the Day Sailor certificate
  (Galveston through the Coastal Cruiser tier it opens), and Marseille is "Not in the career yet".
- **Boat screen:** the whole fleet except the maxi (J/22, Sunfish, ILCA 7, Catalina 22 and 30, Hobie 16, Corsair 880,
  Lagoon 42), locked by certificate in Career.
- **Mode screen:** Race, and Passage (greyed on the lake, with the note "Galveston and Marseille only").
- **Title:** Race and Gallery (developer tools).
- **Free Sail** (the title's Mode switch, one key away) opens all of the above at once, with no warning that it leaves
  the course.
- **Not reachable:** the maxi prologue (`-SailingPrologue` only) and the maxi (the Boat screen skips it).

Galveston and the Catalina 22 stay reachable (stretch, #407).

## Needs Bean's hand

- Sailing each lesson on the keyboard and on a pad: Leave the dock, the triangle, heave to, both crew-overboard methods,
  docking; then the Sunfish's four.
- On the pad: casting off (`DockLines`), backing the jib (`BackJib`), the sheets, and whether the drill steps' key names
  follow the pad (`FLearningContent::ResolveKeys` uses the pad's labels when the pad is in use).

## Part B: the play-through (Nov 1 2026, main 8ab0048c)

34 stills of the packaged Development build at 1920x1080 on Medium, each the game's own screenshot of its window (never
the desktop), on a fresh profile (Config and SaveGames moved aside, restored byte for byte after: `diff -r` clean), an
existing save part way through Day Sailor (`docs/career/still-save.json`) and one with the Day Sailor certificate
(`docs/free-sail/still-save.json`); keys and pad buttons through `-SailingUIScript`. Script and runner:
`Artifacts/claude-6e6e/audit/` on the Mac (`night.sh`, `shot.sh`).

### Seen

| Still | What it shows |
|---|---|
| ![](stills/f-first-launch.jpg) | **A new save opens on the first-launch screen** (#402): the school, quality pre-picked (Medium), Easy pre-picked, Start your first job focused. Finding 1 fixed. |
| ![](stills/f-title.jpg) | **The title** after Skip: no "ASA 101 drills" (finding 6 fixed), Career shows "Day Sailor · 0 of 6 lessons". Still there: **Gallery** (finding 10, developer tools on) and a faint **"GRAPHICS G4 BUILD"** label top right (17). Sail is still the first item and focused for a player who skipped. |
| ![](stills/f-lesson1-r-launch.jpg) | **Start lesson**: Right then Enter on Day Sailor's first row goes straight to its loading screen, "J/22 · Leave the dock", the lesson day, Learning mode (finding 2 fixed). |
| ![](stills/f-career.jpg) | **The Career screen** on a fresh save. Focus starts on the tiers; Down walks the tiers, not the lessons (19). |
| ![](stills/f-lesson1-d-launch.jpg) | Down five times from the Career screen ends on **Passage Maker**, whose panel says **"The passage boat waits on Bean."** (17: developer notes shown to players). |
| ![](stills/k-career.jpg) | **Day Sailor certified**: Club Racer open with its Sunfish lessons; **Take the quiz** under a lesson with a medal and an unpassed quiz (finding 7 fixed). Coastal Cruiser is open but "Lessons to come" (21). |
| ![](stills/f-hud-sunfish-quickstop.jpg) | **The Sunfish's quick-stop** tells the player to "tack, leave the jib backed" (finding 12 seen): a Sunfish has no jib. |
| ![](stills/f-hud-sunfish-heaveto.jpg) | **Heave to on the Sunfish**: "Back the jib ... (B)" (finding 14 seen: a drill the boat cannot sail, reachable from the Mode screen). |
| ![](stills/f-quiz-sunfish-quickstop.jpg) | **The quiz** after the Sunfish quick-stop; footer "Questions on what you just sailed" (finding 6 fixed). |
| ![](stills/g-career-pad.jpg) | **On the pad**: the prompts become A Choose, B Back (`SailingSim.Slice.PadCoverage` holds every first-hour action on the pad). |
| ![](stills/f-replays.jpg) | **Settings > Graphics** (five Downs from the title now reach Settings, not Replays): the help panel quotes "Measured on the packaged build, slowest view (docs/graphics-3/bench.csv) ... on the M5 Pro" (17). |
| ![](stills/f-enter.jpg) | **Sail > World**: Galveston locked (Day Sailor certificate), Marseille "Not in the career yet", the Texas coast; the cards' facts run into each other ("AIDS TO NAVIGALAUNCH SPOTS", "LESSONS IN DAYNORMAL POOL") (18). |

### New findings from Part B and the PC's Windows check

| # | Category | Finding |
|---|---|---|
| 15 | Missing explanation | The first job's caption header read "Captain"; the design says Instructor (PC, Windows Shipping 127081ee). Fixed on `first-launch-fixes`. |
| 16 | Unclear objective | The first job's loading screen read "J/22 · Free sail" (PC). Fixed on `first-launch-fixes` ("Your first job"). |
| 17 | Developer leftovers | Player-facing developer text: the Settings help quotes bench numbers and a docs path; Passage Maker says "The passage boat waits on Bean."; a "GRAPHICS G4 BUILD" label on the title. |
| 18 | Layout | The World screen's card facts overflow into each other. |
| 19 | Unclear objective | On the Career screen Down walks the tiers; the lessons are reached with Right, which nothing says. |
| 20 | Dead end | A player who chose "Skip to the menu" has no way back to the first job (the design's "First job" entry on the Career screen isn't there). |
| 21 | Dead end | Coastal Cruiser opens with the Day Sailor certificate but has no lessons ("Lessons to come"). |

Not reached by the script: Replays with no run (9: still read only), the Sunfish's J/22 quiz questions (13: read; the
still's first question happened to fit a dinghy), and every drill sailed by hand (Bean's, on keyboard and pad).
