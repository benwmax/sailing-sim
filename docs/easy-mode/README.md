# Easy mode

Roadmap phase 3 (the first hour and the feel), first PR. Easy is **one switch** that turns on a fixed set of assists, so a
beginner gets to a first tack quickly and the boat still behaves like a boat. Each assist is a plain number in
`Sailing::FEasyAssists` (`Source/SailingPhysics/Public/EasyAssists.h`, SailingPhysics, no Unreal), with its reason in a
comment beside it. The sim applies them through the boat's config, the trim's settings and `FEasyHelm`, never from an
actor. Realistic changes nothing.

## The switch

- `USailingSettings::IsEasy()`. `-SailingEasy=0|1` decides when given (stills, tests, the gate runs below). Otherwise
  it follows the Difficulty setting (Mode/Conditions in the front end, Settings > Gameplay, the `K` key in game, the old
  menu). It is **off** in measuring runs (`-SailingBench=`), captures (`-SailingCapture=`) and automation, so benches and
  reference captures sail Realistic.
- `ASailboatPawn::ApplyDifficulty` builds `FEasyAssists::For(config, on)` for the player's boat only, never for traffic
  boats or the ghost, and applies it: `ApplyTo(FBoatConfig&)` and `ApplyTo(FAutoTrimSettings&)`. The step job
  (`FBoatStepJob`) runs `FEasyHelm` on a **copy** of the controls, so the player's own tiller and sheets are where they
  left them afterwards.
- Polars, reference checks, scenarios and the traffic simulation never build the assists: `FBoatConfig`'s new heel-cap
  fields default to 0, `FAutoTrimSettings`'s new ones to the old behaviour.
- The save keeps the Difficulty, as before (`settings.difficulty`, `lastSession.easy`).
- Time compression is a separate switch, not part of this.

## The assists

| Assist | Knob (FEasyAssists) | Value | Why |
| --- | --- | --- | --- |
| Forgiving helm | `HelmStiffness` | 1e5 N m/rad (J/22's own 600) | The helm holds the tiller where it is put: no weather helm pulling it to leeward. Kept from the old Easy. |
| | `RollDampingPerTonne` | 2376 N m s per t (2.5 kN m s on the J/22) | A puff heels her over a couple of seconds instead of one. Kept from the old Easy. |
| | `HeelYawScale` | 0.4 of `HeelYawCoef` | She still carries weather helm when she heels (the lesson), but a puff no longer swings her head to wind faster than a beginner can answer. |
| | `YawDampingScale` | 2x `YawDampingLinear` | A round-up starts more slowly; the turns the tiller asks for still come (the rudder's moment is about 50 times this damping's at a tack's turn rate). |
| No capsize | `HeelCapPerTrimLimit`, `HeelCapMaxDeg` | 1.9x `TrimHeelLimitDeg`, at most 25 deg | J/22 24.7 (her rail goes under at about 30), the dinghies 15, Hobie 20, Corsair 19, Lagoon 7.6, the Catalinas 25. |
| | `HeelCapSoftDeg`, `CapLeverM` | from 6 deg short of the cap, 2 m x weight at the cap | `FBoatModel` adds a righting moment that grows with the square of the tilt past the soft start. With 1 m the light Hobie went 9 deg past her cap in a 30% gusty 22 kn. |
| Stronger auto-trim | always on; `TrimIdleSeconds` | back 4 s after the player trims | The trim assist runs whatever its setting says. |
| | `TrimRateScale` | 1.5x | The sheets move at 1.2 of their travel per second instead of 0.8. |
| | `TrimHeelScale` | 0.85 | Depowers earlier: the J/22 at 11 deg instead of 13. |
| | `bEasePuffs` | on | A keelboat crew eases in a puff the way the dinghy sailor already does (`FAutoTrim`'s puff ease, 0.4 s reaction). |
| Wider no-go cue | `NoGoCueDeg`, `NoGoWarnMarginDeg` | 45 deg, warning from 55 | The wind dial draws the no-go band at the sim's angle (Realistic: 35, where `FBoatModel` calls her in irons, thin, no early warning). Easy draws it wide with edge lines. It turns amber when the bow is near and red when inside (`NoGoCueFor`). The tips say "Close to the no-go zone" before she slows. |
| Irons recovery | `IronsHelpSeconds`, `StuckKnots` | 3 s inside the cue under 1 kn | The crew backs the jib (held half out: `RecoveryJibSheet` 0.5; hard in, it pushed the bow off half as fast), lets the main run and puts the helm over (`RecoveryTiller` 1, reversed while she goes astern). She falls off onto the tack she is nearer (the side the jib backed on) until she is `RecoveredTWADeg` 60 off the wind. A tip says what the crew is doing. |
| Bear-away guard | `GuardTiller`, `GuardDeadband` | up to 0.3 tiller (9 deg) with the tiller within 0.15 of centre | Let go of the tiller inside the cue with way on, and the crew bears her off toward 45 deg. A beginner who lets go after a tack, or pinches, sails off instead of luffing into irons. Hold the tiller and nothing happens. |
| Gentler wind | `WindVariabilityScale` | 0.5 | The game mode halves the gusts, puffs and shifts (kept from the old Easy). |

Easy also keeps the Simple control layout (`UseSimpleControls`), as before.

## Honest grading

`career.json` has `"easy_max_medal": "bronze"` at the top. A drill run is Easy if the assists were on at any moment of
it (`ASailboatPawn::bDrillEasy` to `FCareerRun::bEasy`). `FCareerContent::Grade` caps the medal and the lesson keeps a
`medalEasy` mark until the same medal or better is sailed on Realistic. The Career screen shows "Easy: bronze", and the
debrief says when a run on Easy was worth more. The Day Sailor checkride asks for silver, so it needs Realistic; the
screen says so under the checkride. Tests: `SailingSim.Career.EasyMedal`.

## Checks

`scripts/polar.sh [--boat <name>] --easy` sails these standalone, assists off and on. `SailingSim.Physics.EasyMode`
holds the J/22 (and an ILCA 7 dinghy) to them:

| J/22 | Realistic | Easy |
| --- | --- | --- |
| 15 kn beam reach, 20% gusts, 120 s: max heel / course error | 12.9 deg / 3.8 deg | 12.0 deg (cap 24.7) / 1.6 deg |
| 22 kn at 70 deg, 30% gusts: max heel / course error | 31.8 deg / 13.8 deg | 22.2 deg / 7.0 deg |
| Head to wind, no way on, tiller centred, 10 kn | still in irons at 40 s (sternway) | sailing (50 deg off, 1.5 kn) after 20.3 s |
| Beginner's tack (tiller hard over 4 s, let go), 6 / 10 / 15 kn | not tacked: back head to wind | tacked each time, settled at 41-43 deg |

(In the editor the wind carries the Mann turbulence tile, which the standalone build doesn't load, so the test's numbers
differ a little: 12.6 deg and 1.4 deg on the 15 kn reach; 22.9 deg against Realistic's 36.6 at 22 kn.)

The rest of the fleet on Easy (standalone). At 22 kn with 30% gusts every boat stays under its cap except the Hobie 16.
She spins out on the compass course and reaches 23.1 deg against her 20.3 cap, but stays upright; on Realistic she
capsizes. Every boat but the Lagoon 42 gets out of irons in 13-28 s; the Lagoon is still turning at 40 s. The crude 4-s
tack works at 6, 10 and 15 kn on the J/22, the Sunfish, the ILCA 7 and the Hobie. The Catalinas miss it at 6 kn (the
22 at 15 kn too), the Corsair 880 at 6 and 10 kn, and the Lagoon always: 4 s of helm is not enough to carry them through
the wind, and they fall back onto the old tack.

Realistic is unchanged: `scripts/polar.sh` (0 of 39 points outside tolerance), `--scenarios` and
`scripts/reference-checks.sh --quick` print byte for byte what main does.

## What Realistic keeps

The boat's own helm, damping, weather helm and capsize, the trim assist as the setting has it, the 35 deg no-go
band, no irons help, full-strength gusts, and every medal.

## Not yet

- The first-launch flow (pick Easy or Realistic, check the controls) and the guided first sail: the next PR.
- The goal (four of five first-time players tack within 10 minutes) needs players; nothing here measures it.
- Easy's wind softening is applied to the world's weather, so with a second player it would soften theirs too. That's
  fine for one player; online it would have to become per boat.
