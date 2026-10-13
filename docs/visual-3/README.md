# Visual V3: sails and crew

The sails are now cloth shaped by the physics, with real sail details. The yellow cylinders are gone: every boat
carries proportioned, rigged sailors posed from the physics crew model. The J/22's spinnaker is its real size.

![Spinnaker](spinnaker.png)

## Sails (`SailCloth.h`, `SailVisuals.cpp`, `M_SailCloth`)

- **Shape from the physics.** Each sail is a 25 × 16 grid. Its target shape each frame comes from the physics strips: chord angle (twist), camber, and flow per strip, interpolated up the luff, over the sail's planform (luff line, chords, headboard, roach). Draft sits at about 42% of the chord. `SailingSim.Visual.SailShape` checks depth/chord against the strip camber, the chord angle against the twist, the draft position and the planform area.
- **Cloth.** On Medium and High a position-based cloth layer at 60 Hz follows the target:
  - stiff where the sail is drawing;
  - loose where it luffs, so an eased sail flogs and the spinnaker collapses and refills;
  - the leech shivers above about 10 kn apparent;
  - fine luff wrinkles appear when the Cunningham is off in a breeze;
  - held at the luff, at the boom foot on the main, and at the sheeted clew on the jib.

  Low draws the target shape directly. Cost: **0.03–0.10 ms of CPU a frame for all boats** (`cloth_cpu_ms` in
  bench.json). It has no GPU slice of its own (the plan's 1.2 ms Niagara and cloth budget is untouched).
- **Material.** Two-sided Dacron, lit through from behind (two-sided foliage, converted by Substrate). The marks come from the mesh UVs:
  - crosscut seams every 0.9 m;
  - batten pockets on the main's leech;
  - the J/22 class insignia and a sail number from a generated atlas (`scripts/make_sail_marks.py`), on the J/22's main only.

  Seams, batten pockets and ink transmit less light, so they show darker against the sun. The spinnaker is red nylon.
- **Telltales.** Ribbons replace the cubes:
  - three pairs on the jib luff, red to port and green to starboard;
  - three on the main leech at the battens.

  The jib's windward ribbon lifts when you pinch and the leeward one droops and twirls when oversheeted. The leech
  ribbons stream aft, or curl behind the leech when the main stalls. `SailingSim.Visual.Telltales` sails the physics J/22
  to check the rules: both stream trimmed close-hauled, the windward one lifts when pinched to 30°, and the leeward one
  stalls at 62° with the sheet still in.
- **Jib sheets.** They lead from the cloth's clew.

## The spinnaker (physics)

The J/22 spinnaker is now the **30.94 m²** of the ORC one-design certificate (it was 16.3 m², about half).
- **Lift.** Its maximum lift is 1.18, within the wind-tunnel range for spinnakers.
- **Auto-trimmer.** It now blows the spinnaker sheet the moment she heels past the limit and trims back on as she comes upright. Before, it trimmed *in* and she broached. The steady 20 kn run stays at about 10 kn with 4–9° of heel.
- **Polar gate.** Unchanged: 0 of 39 points out, and every spinnaker point is now within 3% of ORC (they were 4–8% slow).

Reference checks: **43 of 46**.
- **Now in range:** "J/22 spinnaker 135°, 20 kn steady" at 9.79 kn (target 8.65–10.15).
- **Newly out:** the gusting-25 peak at 12.10 kn against a 12.0 ceiling. The bigger sail surfs harder; 12.1 kn is still under the boat's 16 kn record and within the method's "bursts of 9–12, rare peaks near 16". It is listed as a known gap rather than tuned away.
- **Still open:** Catalina 22 light-air and Hobie 12+ kn Portsmouth ratios.

## Crew (`Tools/blender/build_crew.py`, `CrewPose.h`)

**MetaHuman was tried first.** MetaHuman Creator ships with this engine and can be scripted (character factory, editor
subsystem, build). But building a character on this Mac stops at "Character is not rigged":
- rigging is Epic's cloud auto-rigging service, which needs a signed-in Epic account;
- the Creator's optional content (texture synthesis) is not installed — it is an engine add-on downloaded through the Epic launcher.

Neither can be done headless here, so the crew is the plan's fallback: a stylised but proportioned sailor built in
Blender from code. No Fab pack was needed.

`SK_Sailor`:
- **Body:** 1.78 m; 2,544 triangles and 19 bones.
- **Gear:** foul-weather jacket (coloured per sailor), PFD harness with its collar, sailing trousers, deck boots, cap, wraparound sunglasses.
- **Materials:** from the boat library (`MI_Boat_Crew*`, which get wet too), assigned by slot in the game.

Poses come from the physics crew model, blended over a fraction of a second, and work on every boat:

| Stance | When |
| --- | --- |
| Rail hike | Keelboat crew to windward: on the rail facing out, legs over the side, leaning out over the lifeline with the hike |
| Helm | The aftmost crew on a keelboat: aft on the windward deck facing forward, leaning out as she heels, hands on the extension and mainsheet |
| Cockpit | Light air or downwind: sitting on the cockpit seat facing in |
| Crossing | On a tack (crew moving across fast): crouched |
| Dinghy hike | Sunfish, ILCA, Hobie helm: on the deck edge facing in, feet under the strap, leaning back with the hike |
| Trapeze | Hobie crew on the wire: standing on the rail, body out over the water |
| Righting | Capsized dinghy: standing on the board, leaning back, hands on the gunwale |

`SailingSim.Visual.CrewPose` checks these on the reference skeleton:
- the chest leans out over the legs on the rail;
- the lower legs hang down the topsides;
- dinghy hiking leans back;
- seated thighs are level with the knees forward;
- crossing is crouched;
- the facing (outboard on a keelboat rail, inboard in a dinghy).

## Frame rate and GPU (packaged build, `bench.csv`)

| View | Low | Medium | High | Medium GPU ms (base / Lumen / clouds+fog / post) | Cloth CPU ms (Medium) |
| --- | --- | --- | --- | --- | --- |
| beam8 | 118.5 | 82.6 | 45.6 | 11.9 (4.9 / 2.0 / 3.9 / 0.7) | 0.064 |
| beat15 | 118.6 | 85.5 | 46.7 | 9.8 (4.1 / 2.2 / 2.4 / 0.7) | 0.061 |
| storm | 118.6 | 118.8 | 65.3 | 7.8 (3.9 / 2.1 / 0.6 / 0.7) | 0.046 |
| marina | 118.4 | 89.2 | 55.2 | 11.8 (5.2 / 2.0 / 3.6 / 0.6) | 0.065 |
| coast-day | 118.3 | 80.2 | 46.6 | 11.3 (4.4 / 2.1 / 3.7 / 0.7) | 0.070 |
| coast-night | 119.5 | 98.8 | 60.4 | 9.3 (2.8 / 1.9 / 3.6 / 0.7) | 0.061 |
| gulf-sea | 118.6 | 100.1 | 56.8 | 9.2 (3.4 / 1.9 / 2.8 / 0.7) | 0.061 |
| helm-eye | 118.5 | 88.2 | 47.1 | 11.3 (4.3 / 2.3 / 3.7 / 0.5) | 0.065 |

Every view is at or above 60 on Medium and 45 on High. High is tight in the lake chase views (45.6–47.1).

## Comparison (`compare/index.html`) and blind test (`blind/`)

The 12 reference scenes were recaptured next to V2. Scores, before → after:

| Category | Scenes | Score |
| --- | --- | --- |
| Boat | J/22 chase and helm scenes | 3 → 2 |
| Boat | Action-cam scenes with the crew close to the lens (J/22, Hobie, Sunfish) | 3 |
| Sails | J/22 scenes | 3 → 2 |

The action-cam scenes stay at 3 because the stylised sailors read as mannequins at arm's length.

Round 1 (the Phase 8 pack) was marked: all 10 game frames spotted, all 10 photos called real
(`docs/phase-8/blind-test/results.md`). The one reason given was the water's pattern and the round trees (V4 and V6).

Round 2 is in `blind/`: the same ten Commons photos and ten new game frames, reshuffled. Its marking page is
https://claude.ai/artifact/SobrKzreqUPoVPXayNUVjU and the answer key is `blind/answer-key.csv` (don't open it before
marking).
