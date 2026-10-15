# Round 11: game stills for the blind test

Ten new stills in the capture mode on High, 1440x1080, uncooked (`scripts/capture-scenes.sh`). They were captured on
origin/main 4c2584ca with #63 (storm-sky-fix) merged in. `game/scenes.csv` reproduces them:

```bash
SCENES=docs/round-11/game/scenes.csv OUT=docs/round-11/game scripts/capture-scenes.sh 14
```

`candidates.csv` lists, for each still, the file, world, conditions and camera, and the tell it tests. Each still also
has `.camera.json` (camera, sun, wind) and `.telemetry.csv` (the boat over the capture). No HUD. None of them reuses a
round 10 framing. The cockpit view was moved off round 10's helm-eye spot, to Chandlers Landing on a broad reach.

## Fixed in this round

- **Rudder blade:** now white gelcoat, not antifouling (`Tools/blender/build_j22.py`, `SM_J22_Rudder` reimported).
  J/22s are dry-sailed, and the dark blade read as a grey slab hanging off the transom.
- **Action-cam lens:** `M_LensDistortion` is now normalised at the frame's corners instead of its side edges, so no
  pixel samples outside the rendered frame. Before, the clamp smeared the side edges into streaks. The preset renders
  at 125 deg so that the middle of each side edge still sees 118 deg (`ReferenceCapture.cpp`, test updated).

## Tells I can see (before the blind round)

- **Storm from the sunshine:** I couldn't frame a shelf cloud seen from sunlit water on the lake. From the start of the
  storm's timeline to the front's arrival, the boat is already under the deck's shade. `-SailingStormDelay` past
  about 600 s changes nothing in the view. The best version is on the bay (`r11-bay-storm`): sun on the boat, rain wall
  and dark base behind. The base still shows grain (speckle) at full size, and there is no crisp arcus edge.
- **Lake whitecaps at 20 kn:** `r11-lake-beat20` in open water shows chop but almost no caps. The lake's coverage is
  0.4 of Monahan (W0, a literature value). Photos of 20 kn on Texas reservoirs usually show scattered caps. This
  still is the test of that choice.
- **Shaded face, reversed number:** in `r11-gulf-seawall` the far side's number shows through the near face quite
  strongly. The near face is in shade, so it's physically right. The question is whether it reads as right.
- **Grey storm towers:** with #63, cumulus inside the storm's painted extent are uniformly grey, with no sunlit tops
  (seen in game-10, not in these stills). This is the README's weather-map item: fade cumulus near the front.
