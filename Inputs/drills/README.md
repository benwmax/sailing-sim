# ASA 101 drill learning content

Written off the Mac (Oct 14 2026) for the six learning-mode drills in `Source/SailingSim/Private/Drills.cpp`, to be
wired in after the G6 fix round. Like the rest of `Inputs/`, this is source material: copy the JSON into
`Content/Learning/` (or wherever suits) when wiring it in, and stage it as loose files the way `Content/TerrainData` is.

Wording follows ASA 101 and *Sailing Made Easy*: jibe (not gybe), crew overboard, "Ready about / Ready / Helm's a-lee",
"Prepare to jibe / Ready / Jibe-ho". The examples are set on Lake Ray Hubbard from Rush Creek in a J/22, with inland
North Texas weather (afternoon thunderstorms, summer heat, fall fronts, lake level instead of tides).

| File | What it holds |
|---|---|
| `drill-briefings.json` | One briefing per drill: goal, why it matters, setup, crew calls, coaching for each `FDrillRunner` step, what good looks like, common mistakes with fixes, a lake note, debrief lines per outcome, how many quiz questions to ask afterwards, and an optional `sim_fix` note for code changes |
| `learning-tips.json` | 63 sim events (with a suggested detection for each) and 68 tips keyed to them: trim and luffing, heading up and bearing away, tacking, jibing, heel, depth, crew overboard, heaving to, docking, right-of-way encounters, weather |
| `quiz-bank.json` | 86 multiple-choice questions with a one-line explanation, tagged by drill and ASA topic. None repeats a question from the ASA 101 Study Kit |
| `validate.py` | Checks all three files, and that each briefing's steps still match `Drills.cpp` |

Run `python3 Inputs/drills/validate.py` from the repo root (plain Python 3, no packages). If someone edits a step in
`Drills.cpp`, the validator fails until the matching `sim_text` here is updated, so the briefing and the HUD never
disagree.

## Layout

All three files follow `Inputs/g3/boat-catalogue.json`: `schema_version`, `generated`, a `conventions` block that
explains the fields, then the data.

**Drill ids** are the `ESailingDrill` enumerator names: `LeaveTheDock`, `SailATriangle`, `HeaveTo`,
`CrewOverboardFigureEight`, `CrewOverboardQuickStop`, `ReturnAndDock`. `Any` marks a tip or question that fits any sail.

### drill-briefings.json

```
drills[]: id, name (= DrillName()), asa_skill, goal, why_it_matters, setup,
          commands[]: {call, reply, meaning},
          steps[]: {sim_text, text?, coach}     same count and order as FDrillRunner::Steps
          good[], mistakes[]: {mistake, fix}, lake_notes,
          debrief: {outcome: line}, quiz_after, sim_fix?
```

- `sim_text` is copied verbatim from `Drills.cpp`. `text` (on three steps) is the same line with the hard-coded key
  letter, such as `(T)`, swapped for a key token, so it follows rebinding. Use `text` when present.
- `coach` is the longer explanation for the briefing screen or the drill panel when the step is current.
- `debrief` keys match the drill's completion branches in `FDrillRunner::Update`:
  LeaveTheDock `clean` or `contact` (`MaxContactSpeed > 1.0`), SailATriangle `done`, HeaveTo `done`, crew overboard
  `proper` or `improper` (the `bProper` test), ReturnAndDock `gentle` or `hard` (`MaxContactSpeed > 1.5`).
  Placeholders: `{time}` as m:ss, `{contact_kn}` to one decimal.
- `quiz_after` is how many questions to ask when the drill finishes: draw from questions tagged with that drill
  first, then `Any`.

### learning-tips.json

```
events: {event id: plain-language detection}
tips[]: {id, event, drills[], level, cooldown_s, once_per_session, asa_topic, text}
```

- Event ids are dotted (`jib.luffing`, `tack.slow`, `cob.fast_approach`, `rules.port_starboard.give_way`,
  `weather.gust_front`). The detection strings use `FBoatTelemetry`, `FBoatControls`, `FDrillRunner`, `FRulesCoach`
  and `FWeatherState` names; thresholds are starting points to tune on the Mac. Several overlap with what
  `SailingCollectTips` already checks (luffing, stalled, irons, heel, weather helm, by the lee, storm), so those
  can switch to this text directly.
- `level` maps to the existing tip severity: `info` 0 (white), `good` 1 (green), `warn` 2 (amber), `danger` 3 (red).
- When an event fires, prefer a tip whose `drills` names the running drill over an `Any` tip. Several tips can share
  an event; show the highest level first.
- Tips are 240 characters or less so they fit the tip panel at the default text size.
- All tips respect the existing learning-tips toggle (`bLearningTips`, L).

### quiz-bank.json

```
questions[]: {id, drills[], topic, q, options[4], answer, why}
```

- `topic` uses the Study Kit's tags: parts, sail, trim, rules, lights, aton, nav, knots, safety, weather, dock.
- `answer` is a zero-based index into `options`. The options are already in a mixed order, but shuffle them at run
  time anyway and carry the answer with its text.
- Six questions are tagged with both crew-overboard drills.

## Key tokens

Tip and step text never names a key directly. Replace each token with the player's current binding from
`USailingSettings`, so the text stays right after rebinding and on a controller.

| Token | Action and direction in `SailingSettings.cpp` | Default key |
|---|---|---|
| `{key:JibSheet.trim}` | JibSheet, scale -1 | E |
| `{key:JibSheet.ease}` | JibSheet, scale +1 | Q |
| `{key:MainSheet.trim}` | MainSheet, scale -1 | W |
| `{key:MainSheet.ease}` | MainSheet, scale +1 | S |
| `{key:Hike.out}` | Hike, scale +1 | F |
| `{key:BackJib}` | BackJib | B |
| `{key:DockLines}` | DockLines | T |
| `{key:ToggleLearning}` | ToggleLearning | L |

## Fix for Drills.cpp (crew-overboard pick-up side)

Figure-eight step 4 says to stop "to windward of them", but the finish message says "Get them aboard on the windward
side". Bean settled it on Oct 14 2026: turn into the wind for the final approach so the headwind slows the boat, and
pick the person up on port or starboard, either works. The briefings, tips and quiz now say that. Suggested code
change when wiring this in (then update the matching `sim_text` and rerun `validate.py`):

- Step 4: `Approach on a close reach and turn into the wind to stop alongside them`
- Finish message: `Recovered in m:ss. Get them aboard and keep them warm.`

The sim says about five boat lengths for the figure-eight; the briefing and quiz say "about four or five", which
covers the usual book and school wording.
