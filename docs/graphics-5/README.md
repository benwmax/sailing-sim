# Graphics G5: the whole-game blind test

G5 checks the four graphics phases together. Fifteen photos from Wikimedia Commons are paired with fifteen game frames
set up to match them. The mix is lakes, the marina, keelboats sailing and racing, a Hobie, a ship, open sea, storm and
fair-weather sky, and sunsets. Five photos are of Lake Tawakoni, a Texas reservoir 30 miles east of Ray Hubbard. Then I
fixed what gave the game away most cheaply.

- **The test:** [Real or Game: The Whole Game](https://claude.ai/artifact/3vCD1d83vfZx21tXNuGZzY). Thirty stills; answers
  save as you go. The key is in `blind/answer-key.csv` (don't open it before marking). Credits are in `blind/credits.md`.
- **How it's made:**
  - `Tools/blindtest/fetch_commons.py` searches Commons (free text or a category) and keeps only CC0, public domain,
    CC BY and CC BY-SA files, recording each credit.
  - `blind/scenes.csv` holds the game frames: `SCENES=docs/graphics-5/blind/scenes.csv OUT=docs/graphics-5/blind/game
    scripts/capture-scenes.sh 14`.
  - `Tools/blindtest/make_blind_pack.py` crops both sides to 4:3, strips metadata and shuffles them.

## My own read, pair by pair

What gives each game frame away, before the fixes, most visible first.

| Scene | What gives it away |
|---|---|
| Lake sunset, sailboats at dusk | The worst pair. A white band of haze on the horizon, the whole frame washed out, no sun disc, the water near white. |
| Almost every sky | Cirrus drawn as regular parallel brush strokes. |
| Towering cumulus, the lake views | Cumulus edges frosted with fine grain; overhead decks look marbled (the curl warp smears them); shapes melt rather than billow. |
| Shelf cloud | A bright cauliflower wall with grainy edges where a real shelf is a dark, smooth, layered arch. |
| Ship | Flat-shaded container stacks and hull. The real tanker has decks, rails, cranes and rust streaks. |
| Wooded cove | The shore buildings read as plain boxes. No weed or reeds at the waterline. |
| Gulf swell | The open sea is too teal and too smooth for 12 kn; the overcast still shows blue holes. |
| Keelboats (chase, crew, spinnaker) | Close. The tells are the crew's stiffness, the sails' cleanliness (no creases or numbers' sheen) and the spinnaker run's empty course (no fleet around). |
| Marina, slip, Hobie | The best pairs. Ours are tidier than life (no fenders, lines or covers lying about), and the masts are a little thick. |

## Fixed

1. **The haze follows the light.**
   - Before: the fog's inscattering was a fixed colour, so when the exposure opened four or five stops for a low sun,
     the horizon blew out white.
   - Now: it's lit by the same metered light as the exposure, relative to a clear midday, and warms toward the sun's
     colour below 12°.
   - `-SailingClassicHaze` shows the old look.
2. **Sunsets go deep.**
   - Facing a sun below 20°, the exposure closes up to 2.5 stops, as a camera metering the bright sky does.
   - The fog stops at 90% opacity, so the low sun's disc shows through the haze as it does in life.
3. **Cirrus.**
   - Fibres from value noise stretched along the wind (three octaves, the fine one faded with distance) replace the sine
     streaks.
   - Fainter overall (45% at most, was 55%).
4. **Clean stills.** `-SailingNoHud` no longer draws the canvas hint line ("H: show instruments..."), which gave a marina
   frame away.

**Before and after:** [compare/index.html](compare/index.html) shows each scene's photo, the frame the test used and the
same frame after the fixes (`blind/after/`). The two sunsets change completely. Every other scene is unchanged at a
glance, apart from fainter cirrus.

**Cost:** the first cirrus version ran its noise on every sky pixel and cost High about 0.3 ms (the round 7 bench below:
helm-eye 43.1). It now runs only where the weather map has cirrus, with three octaves. These are packaged High runs
against G4:

| View | G4 | G5 |
|---|---|---|
| helm-eye | 44.9 | 45.0, 45.1 |
| crew | 46.5 | 47.2 |
| beam8 | 53.0 | 52.9 |

Tried and not kept: doubling the cloud view samples and tripling the shadow samples (`-SailingCloudScale=2,3`) on High.
The frosting softens a little but stays, at a cost the High gate can't afford. Half-resolution tracing (mode 1) is
sharper but just as frosted. The frosting is in the density, not the upsampling.

## Open

- The cumulus frosting and the marbled overhead decks (G1's noise and curl warp), and the shelf cloud's form.
- The ship and shore building models.
- The Gulf's colour and roughness under overcast, and blue holes in the Overcast preset.
- A handled engine ensure in Galveston runs: a distance-field object with an out-of-range transform on frame 2
  (`FDFMatrix::MakeToRelativeWorldMatrix`). Harmless but noisy.
- A second blind round (round 7) was built on this branch at the same time by another session, in `game/`.

## Round 7: ten game stills for the "real or game" pack

The cloud side holds ten real photos. `game/game-01.png` to `game-10.png` are the matching game frames: capture mode
(no HUD, blur or depth of field, auto exposure frozen at 2.5 s), High tier, 1440x1080. I didn't try Ultra on the Mac.
`game/captures.csv` lists each still's world, boat, weather, hour, camera and full arguments. `game/candidates*.csv` are
the roughly 60 candidates I chose from, and `game/final.csv` the picks, recaptured together on one build:
`SCENES=docs/graphics-5/game/final.csv OUT=<dir> scripts/capture-scenes.sh 12`.

| Still | Scene | Notes |
|---|---|---|
| 01 | Galveston Bay race start, 14 mixed keelboats, overcast | New `-SailingRaceBoats=<n>` (up to 16, the line closes up) and `-SailingRaceMixed` (Catalina 30, J/22, Catalina 22) |
| 02 | Rush Creek's masts from the shore, flat overcast | |
| 03 | Drone over the club at golden hour (18:12) | |
| 04 | Catalina 30 sunlit against the shelf cloud | `-SailingStormDelay` keeps the front off the boat |
| 05 | Sunfish with a sailor, another behind, cumulus | |
| 06 | J/22 crew in PFDs from the stern action cam, overcast | |
| 07 | J/22 in her slip, blue sky | Weak match: the photo has the boom down and the sails stowed. In the drill the sails are up. |
| 08 | Dark storm base and a bright band over the open bay | |
| 09 | Hobie 16 passing lakeside houses, clear sky | Weak match: the houses are plain boxes |
| 10 | Storm over a lake cove with houses and docks | |

`capture-scenes.sh` now reads its scene list from a private temp file first. Two runs at once used to rewrite the shared
list and cut each other short.

### Bench after round 7

`scripts/bench-visual.sh 12 g5 Medium High` on the packaged build, at HEAD after the round-7 stills (this includes the
haze, exposure and cirrus fixes above). The full table is in `game/bench-visual.csv`.

| View | Medium fps (G4 -> now) | High fps (G4 -> now) | High GPU ms (G4 -> now) |
|---|---|---|---|
| beam8 | 95.5 -> 90.6 | 53.0 -> 50.4 | 16.4 -> 17.8 |
| beat15 | 92.5 -> 88.5 | 51.8 -> 50.2 | 16.5 -> 17.5 |
| storm | 86.6 -> 81.5 | 50.4 -> 48.4 | 17.9 -> 19.6 |
| marina | 89.2 -> 84.5 | 47.0 -> 46.9 | 17.7 -> 20.0 |
| coast-day | 86.2 -> 81.5 | 46.8 -> 47.3 | 16.8 -> 16.7 |
| coast-night | 115.2 -> 107.8 | 56.2 -> 54.0 | 13.9 -> 15.0 |
| gulf-sea | 114.0 -> 108.5 | 61.6 -> 59.3 | 13.8 -> 13.8 |
| helm-eye | 84.7 -> 80.4 | 44.9 -> 43.1 | 20.3 -> 20.8 |
| slip | 77.9 -> 74.0 | 47.3 -> 45.3 | 18.9 -> 20.5 |
| bridge | 95.4 -> 91.2 | 52.1 -> 50.3 | 16.9 -> 17.7 |
| crew | 72.9 -> 68.5 | 46.5 -> 44.9 | 19.5 -> 20.0 |
| marina-night | 91.5 -> 88.7 | 57.4 -> 54.8 | 15.4 -> 16.2 |

Every view is 2-5% lower in fps, including those whose GPU time didn't move (most Medium views). Reruns of beam8 Medium
gave 89.9 and 93.2, and crew High gave 45.0 and 44.8, so about half of the drop is run-to-run noise. On High the clouds
and fog slice is up 0.1-0.5 ms on most views, from the new haze and cirrus. Medium stays far above its 60 fps gate.
High holds 45 except helm-eye (43.1, already 44.9 in G4) and crew, which sits on the line (44.9).

Update: the extra High cloud time came from the first version of the cirrus, which ran noise on every sky pixel. Since
8150565 it runs only where the weather map has cirrus, with three octaves. Packaged High is back at G4 (helm-eye 45.0
and 45.1, crew 47.2, beam8 52.9; see the cost table above). The round-7 stills were captured before that change, which
affects cost, not the look.
