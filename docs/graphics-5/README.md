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
   - Fibres from value noise stretched along the wind (four octaves, the fine ones faded with distance) replace the sine
     streaks.
   - Fainter overall (45% at most, was 55%).
4. **Clean stills.** `-SailingNoHud` no longer draws the canvas hint line ("H: show instruments..."), which gave a marina
   frame away.

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
