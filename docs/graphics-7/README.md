# Graphics G7: wiring in the input packs

G7 brings in the three packs the cloud threads built on the `inputs` branch (copied with `git checkout origin/inputs --
Inputs/<dir>`, never merged): the ASA 101 learning content (`Inputs/drills`), the sound sample pack (`Inputs/audio`) and
the Galveston piers, jetties and moored boats (`Inputs/g2/piers`). No new graphics round: Bean's round 8 tells (trees on
the shore, the crew close-up's textures) are waiting on his further notes.

## 1. Learning mode: briefings, tips and quizzes (`Inputs/drills`)

The JSON is staged as loose files in `Content/Learning` (`DirectoriesToAlwaysStageAsUFS`, like `Content/TerrainData`)
and loaded by `FLearningContent` (`Learning.h`).

- **Briefing before each drill.** When a drill starts in learning mode the game pauses on a briefing screen
  (`SSailFrontEnd`, `ESailScreen::Briefing`): goal, why it matters, setup, the crew's calls, every step with the coach's
  notes, what good looks like, common mistakes with their fixes, and a note on the lake. Enter starts the drill. While
  sailing, the drill panel uses the briefing's wording (key letters follow rebinding) and shows the coach's line under
  the current step.
- **Tips on their events.** `FLearningEvents` turns each frame into the 63 dotted events of `learning-tips.json` (trim,
  pinching, irons, head up and bear away, tack and jibe start, finish and slow, heel, helm, gusts, depth, crew overboard,
  heaving to, docking, every right-of-way case from the rules coach, storms, heat, fronts, calm, mark rounding, drill
  complete). `FLearningCoach` picks the tip: the running drill's own tip beats an Any tip, then the higher level, with
  each tip's cooldown and once-per-session flag kept. The tip card shows it under its ASA topic. `FRulesCoach::FAdvice`
  now carries the encounter, both vessels' status and tack so the rules tips can key off them.
- **A quiz after each drill.** Three seconds after a drill ends, a quiz of the briefing's `quiz_after` questions opens
  (the drill's own questions first, then Any; options shuffled with the answer kept). The quiz shows the drill's debrief
  line for how it went (`FDrillRunner::GetOutcome`: clean/contact, done, proper/improper, gentle/hard), explains each
  answer, and writes the score in the logbook.
- **Fixes in `Drills.cpp`.** The crew-overboard figure-eight contradicted itself (the step said stop to windward of the
  person, the finish said bring them aboard on the windward side). Bean's answer: approach into the wind so the
  headwind slows the boat, and pick them up on port or starboard. Step 4 is now "Approach on a close reach and turn into
  the wind to stop alongside them", and the finish is "Get them aboard, on either side, and keep them warm." `validate.py`
  also showed that the briefing's leave-the-dock step 2 was missing the code's ": the crew hoists the sails" (the code
  is right, since G6 hoists the sails at cast-off), so the JSON was fixed. `python3 Inputs/drills/validate.py` passes.
- **Tests:** `SailingSim.Drills.LearningContent` loads `Content/Learning` and checks every briefing step against
  `FDrillRunner`'s steps, the debrief keys against the outcomes, every tip's event against the detector, every key
  token, the tip length, the quiz answers and each quiz's size. `SailingSim.Drills.LearningEvents` drives the detector
  through a tack, irons, a fast crew-overboard approach and a port-starboard crossing, and checks the coach prefers the
  drill's own tip.
- Stills: `-SailingDrill=<id> -SailingFrontEnd=Briefing|Quiz` (drill ids such as `CrewOverboardFigureEight` now work
  for `-SailingDrill`).

| Briefing | Tip and coach line | Quiz |
|---|---|---|
| ![briefing](briefing.png) | ![tip](tip.png) | ![quiz](quiz.png) |

## 2. Sound sample pack (`Inputs/audio`)

`scripts/import-audio.sh` now also imports the pack's 48 WAVs to `/Game/Audio/Pack/<Folder>/<name>`, with Looping set on
every `*_loop`. Each file plays the layer named in the manifest's "Game parameter" column (`SailingSound::PackLoops`,
`PackShots`):

| Layer | Files | Driven by |
|---|---|---|
| Wind | light, moderate, strong rigging loops | apparent wind, equal-power crossfade at 3, 7 and 11 m/s |
| Sail flog | luff light and moderate, strong flog | luff 0.25 / 0.55 / 0.85; the strong flog only above 7 m/s |
| Hull wash | 1, 3, 5, 7 kn loops | boat speed (0.5, 1.5, 2.6, 3.6 m/s); 7 kn raised past 0.9 hull speed |
| Lapping | calm, dock, choppy | at rest, tied up, bow slam or chop |
| Winch, sheet | ratchet slow and tailing, sheet running | trim rate |
| Rain on deck | rain on roof | rain |
| One-shots | halyard slaps, sail fill snaps, winch clicks, sheet easing, dock creaks, fender squeaks | at rest in a breeze, a tack filling, small trims, easing, surging in the slip (pitch ±5%) |
| World | marina halyards, gulls (laughing gulls on the coast), outboard idle, low and running | `USailingWorldSamples` follows each source's level and rate; the synth source is muted |

The synth stays as the fallback for every voice with no file imported, and keeps gusts, telltales, rain on the water,
the squall, thunder and the diesel. A single `Audio/Samples/<Cue>.wav` still overrides the pack for its cue. The
attributions (avphillips and ezwa, public domain; Tony Phillips, CC BY 3.0) are in `Audio/Samples/CREDITS.md` and
`CREDITS.md`. Test: `SailingSim.Audio.SamplePack` checks every manifest file is imported, loops as the manifest says,
and has a layer.

## 3. Galveston piers, jetties and moored boats (`Inputs/g2/piers`)

`Tools/coast/build_piers.py` bakes the pack into `Content/TerrainData/GalvestonBay.piers`. `FLakeData::LoadPiers` reads
it, `scripts/bake-shore.sh` rebakes the shore's Nanite tiles, and `-SailingNoPiers` compares with the old coast.

- **Lidar decks on piles:** 1,787 piers, dock complexes, wharves, covered slips and the better small decks, each at its
  measured deck height. The shore kit draws them: deck, fascia, and pilings every 3 m down into the bed. The 515 OSM
  piers a lidar deck covers are dropped. Free-standing "decks" under 0.9 m with a ragged outline are left out: they are
  oyster reef and shoal tops. So are decks in canals the 10 m grid shows as land. Every deck outline is an obstacle.
- **Riprap:** both Galveston jetties (12 m mounds at their lidar crest), the Texas City Dike (rock along both edges of
  its 41 m crest), the end of the Seawall inside the grid (a concrete wall to +4.6 m), and 720 more jetties, groins and
  breakwaters the OSM breakwaters didn't already have. All are obstacles. The named jetties and the dike get the G2
  boulders; the other pieces keep only the baked rock core (see Gate).
- **Moored boats as marina neighbours:** sailboats under 7.8 m become J/22s or Catalina 22s, longer ones Catalina 30s, in
  the six berthed dresses with per-instance liveries. Power boats under 9.5 m are the runabout and longer ones the
  trawler yacht. Each boat is scaled to her measured length (0.75 to 1.6) and is an obstacle. Bows point at the row's
  walkway, or at the nearest deck. `ACoastMarinasActor` draws them at the water's level, so they float while the
  terrain follows the tide.
- **Floating docks:** the lidar can't see them. The bake finds rows of boats lying side by side and checks both ends of
  each row against the docks already there (OSM and lidar). Two facing rows share a walkway between their bows. A
  single row gets its walkway on the landward side, taken from the terrain, and fingers go between neighbours. Most
  marina rows already have an OSM dock, so 33 walkways were inferred.
- **What's left out, and why:** of the pack's 8,241 boats, 6,184 sit where the 10 m bay grid has land: narrow canals,
  boat yards, and a few boats off the grid's south edge. A boat there would sit on the lawn. Another 610 overlap an OSM
  pier or a lidar deck, which happens where the 2018 boat and the dock data disagree; the dock is kept. 1,447 boats are
  drawn. The Gulf front (the rest of the Seawall, the Pleasure Pier, the fishing piers) needs a G2 rebuild against USGS
  and TxGIO hosts and a sim grid that grows south. That isn't cheap, so it's skipped.
- Test: `SailingSim.Coast.Piers` checks the named structures, deck heights, that no boat sits on land, that a boat
  stops the player, and that a deck's triangles survive the tile split. The splitter walks four vertices at a time, so
  a first bake drew stray lines across the bay; triangles are now stored as degenerate quads.

| Lidar piers and covered slips (Clear Lake) | Moored boats | The Texas City Dike |
|---|---|---|
| ![piers](galveston-piers.png) | ![boats](marina-boats.png) | ![dike](dike.png) |

## Gate

`scripts/build.sh`, `scripts/test.sh`: 98 passed, 0 failed (four new tests: `SailingSim.Drills.LearningContent`,
`SailingSim.Drills.LearningEvents`, `SailingSim.Audio.SamplePack`, `SailingSim.Coast.Piers`). `scripts/package-mac.sh`
succeeded.

**bench-visual** (packaged, 12 s per view; `bench-visual.csv`, screenshots in `bench/`). Every view holds Medium 60 and High 45.
The first High run had Galveston coast-day at 44.5 fps. The GPU time hadn't changed (16.6 ms against 16.4), so the
cost was on the CPU, and switching layers off showed the boulders on the 720 extra jetty and breakwater pieces. Those
pieces now keep only their baked rock core, as the groins do, and the boulders stay on the named jetties and the dike
(268k boulders, was 399k). High was rerun after that change; the Medium rows are from the first run, before it, so they
are if anything conservative.

| View | Medium fps (G6) | High fps (G6) |
|---|---|---|
| beam8 | 92.9 (91.6) | 54.3 (52.3) |
| beat15 | 90.6 (90.8) | 51.5 (52.0) |
| storm | 77.8 (77.3) | 48.5 (47.5) |
| marina | 88.6 (88.1) | 51.8 (49.2) |
| coast-day | 82.6 (84.5) | 48.4 (50.0) |
| coast-night | 105.1 (104.7) | 52.5 (52.7) |
| gulf-sea | 111.5 (111.3) | 61.1 (59.8) |
| helm-eye | 83.0 (84.0) | 45.6 (44.9) |
| slip | 75.0 (75.1) | 49.3 (47.3) |
| bridge | 98.5 (98.9) | 54.2 (54.0) |
| crew | 74.2 (73.8) | 46.2 (46.6) |
| marina-night | 81.4 (81.4) | 53.7 (51.8) |

**bench-phase5** (Galveston on Medium, packaged; `bench-phase5.csv`; run before the boulder change, so `docs/phase-5`
screenshots are not overwritten):

| View | fps | p99 ms |
|---|---|---|
| coast-day | 83.0 | 12.63 |
| coast-bay | 79.0 | 13.63 |
| coast-night | 103.6 | 10.47 |
| coast-dusk | 108.4 | 9.91 |
| chart | 119.7 | 9.86 |
| chart-bay | 119.6 | 9.09 |

