# First launch and the skipper's first job (#402, design)

**Status: design, approved by Bean on Oct 31 2026 (the four decisions below, as written).** Part of the vertical slice (#399, Nov 21). The maxi prologue
stays parked. The same design is in the Claude Doc "First launch and a guided first sail (design)"; this page is the
repo's copy.

A new player's first ten minutes: two questions, a short guided sail in the J/22 on Lake Ray Hubbard with an
instructor aboard, then Day Sailor lesson 1, with no menus in between.

## First launch

On a save with no `firstLaunch` record, the title is skipped once. The player gets one screen with two questions, then
the loading screen straight into the first sail.

1. **Picture quality:** Low, Medium or High (Ultra on Windows), pre-picked from the GPU the way `USailingSettings` picks
   it now, with one line on what each costs. Changeable later in Settings.
2. **How the boat sails:** *Easy* (the helm and trim help you; she won't round up or lay over) or *Realistic* (the boat's
   own). Pre-picked: Easy. Under it: "You can switch any time in Settings. Gold medals need Realistic."

Controls are not asked. The prompts follow whichever the player touched last, keyboard or pad
(`FLearningContent::ResolveKeys` already does).

Under the Start button, a small "Skip to the menu" for players who have sailed before. It records the first sail as
skipped; the sail stays on the Career screen as "First job" for later.

## The skipper's first job

About seven minutes, six steps, never a fail. The framing is a job, not a test:

> **Blue Heron Sailing School.** "You're our newest skipper. Your first job: take the J/22 across to the lesson dock
> while I watch. I'll tell you what to do; you do it."

The J/22 is already sailing on a beam reach 300 m off Rush Creek (lesson 1 teaches leaving the dock, so this doesn't).
Conditions are the Lesson day: 8 to 10 kn with steady puffs, 10 am, no traffic. The player has the helm and the
mainsheet; the crew trims the jib. The instructor speaks in captions ("Instructor"), naming the live keys. A step not done
after three tries is done by the instructor ("I'll take it this time. Watch what I do.") and the job goes on.

| # | Step | The instructor says | Done when |
|---|---|---|---|
| 1 | Steer straight | "She's yours. Pick a tree on the far shore and keep the bow on it." | TWA 70 to 110 deg for 20 s |
| 2 | Ease the main | "Let the mainsheet out until the front of the sail starts to flap." | Main eased by 0.15 or more |
| 3 | Trim it back | "Now pull it in just until the flapping stops. That's trimmed." | Main trimmed by 0.05 or more within 10 s |
| 4 | Sail upwind | "Turn toward the wind, slowly, until the sails start to flap, then bear off a touch." | TWA 38 to 55 deg for 15 s |
| 5 | Tack | "Ready about? Push the tiller away from you and hold it. Bow through the wind." | A settled tack: TWA 30 to 100 on the new side |
| 6 | Stop | "To stop, point her straight into the wind and let the sails flap." | TWA under 30 deg and under 1 kn for 5 s |

After step 6: "Job done: steer, trim, tack, stop. Next time you'll take her off the dock yourself." The screen fades
and loads lesson 1. Checkpoints at steps 1, 4 and 6; R restarts at the last one. The job costs the player nothing and
records no medal; it marks `firstLaunch` done.

## Into lesson 1

The first job hands over to Day Sailor's Leave the dock: J/22, Learning mode, the Lesson day, traffic off, at the home
slip, opening on its briefing. The same direct path, **Start lesson**, replaces the five screens from every Career lesson
row. A finished lesson ends on **Next lesson**, **Sail it again** and **Retake the quiz**.

## What it fixes from the audit (#400)

| Finding | How this design answers it |
|---|---|
| 1. Two ways to learn on the title | A new player never sees the title first; the "ASA 101 drills" item goes (Career covers the same six drills) |
| 2. Five screens and a load from a lesson | Start lesson goes straight to the briefing with the lesson's own boat and conditions |
| 3. Easy caps medals at bronze, so no certificate | Easy earns up to silver, enough for the checkride; gold needs Realistic |
| 4. Light traffic can take the medal | Lessons sail with traffic off unless the lesson asks for it |
| 5. Any weather earns the same medals | A lesson fixes its conditions; free choice stays in Free Sail |
| 7. No quiz retake | Retake the quiz after a lesson and on its Career row |
| 8. No next lesson | Next lesson on the finish panel |

Findings 6 and 9 to 14 (the ASA naming, Replays, Gallery, the Sunfish's J/22 text and quizzes, drills a Sunfish can't
sail) are small fixes of their own, filed as separate slice issues.

## What it touches

Mostly data on machinery that exists; about three to four days on the Mac.

| Part | Where |
|---|---|
| The job's script | `Content/FirstSail/first-sail.json`: a second `FScriptedScene` file in the prologue's format, checked by `Tools/prologue/validate.py`. One addition: `max_speed_kn` on a Hold, for the stop. |
| The first-launch screen | `ESailScreen::FirstLaunch` in `SSailFrontEnd`, shown when the save has no `firstLaunch` record; its answers go to `USailingSettings` (quality, Easy), the record to `profile.json` (a new field read as absent on older saves: no version change, `docs/save/README.md`) |
| Hand-off | The scene's `then` names the lesson; the game mode travels to it through `USailSessionSubsystem`, as Start lesson does |
| Career | `easy_max_medal` to silver in `Content/Career/career.json`; each lesson gets fixed `conditions` and `traffic`; the finish panel's three buttons; `Tools/career/validate.py` checks the new fields |
| Tests | `SailingSim.Scene.FirstSail` sails the script with the autopilot answering each call, and once answering nothing so the instructor finishes it; `SailingSim.UI.FirstLaunch` walks the screen and the hand-off; `SailingSim.Career.EasySilver`. Then a UI gate on the Mac |

## For Bean to decide

- [x] The two questions and their defaults (quality from the GPU, Easy pre-picked)
- [x] The six steps and their wording, and the "first job" framing
- [x] Easy earns up to silver; gold needs Realistic
- [x] Drop the title's "ASA 101 drills" item for good
