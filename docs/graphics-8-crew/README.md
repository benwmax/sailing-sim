# Graphics G8 (Mac): the crew

Round 8 of the blind test scored 20 of 20 again. Bean named the people twice: the dinghy sailor looks fake (game-05), and
the crew close-up lacks texture and detail (game-06). This round splits the work by machine. The PC (graphics-8-pc) takes
the boats, piers, clouds, trees and shoreline. The Mac takes the people and owns the crew assets.

`game/game-05.png` and `game/game-06.png` are those two scenes recaptured with the same arguments as before
(`docs/graphics-5/game/final.csv`): High, capture mode, 1440x1080. `compare/` puts each G6 frame (round 8,
`docs/graphics-6/game/`) beside its G8 frame. `<scene>.jpg` is the whole frame and `<scene>-crew.jpg` the crew enlarged.
`Tools/blindtest/make_g8_crew_compare.py` rebuilds them.

## What looked fake, and the fix

| What showed | Cause | Fix | Before / after |
|---|---|---|---|
| Hands open in the air: the trimmer and bow held flat, splayed hands over nothing, and the dinghy sailor reached for nothing | The stances set the arms by forward kinematics only, and the fingers stayed in the MetaHuman's flat rest | **Hands.** `FCrewHands` (`CrewPose.h`) adds two-bone IK from the shoulder that keeps the stance's elbow plane, and curls the fingers about axes found from each rig's palm. The helm holds the tiller extension in the aft hand, about 90 cm from the tiller's end and low beside the hip, and the mainsheet's tail in the other hand at lap height. The tail is drawn from the car to that hand. The trimmer holds the working jib sheet's tail a forearm's length off the self-tailer. Everyone else rests their hands on their knees. Hands on a line close into a fist; the rest are relaxed. | [game-06](compare/game-06-crew.jpg), [game-05](compare/game-05-crew.jpg) |
| The dinghy sailor bald at 10 m (game-05) | His hair's LODs 2 and 4 have no card mesh (the build makes cards for LODs 1 and 3 only), and LOD 5 and up is a helmet mesh that draws nothing here | **Hair at distance.** Past 6 m each groom is held on its coarsest LOD that has a card mesh (`UpdateCrewGroomLOD`). | [game-05](compare/game-05-crew.jpg) |
| The dinghy sailor kneeling and stiff, staring across the boat | The dinghy stance's lower legs went straight down through the deck | **Dinghy pose.** He sits on the side deck with his thighs level and his lower legs in the cockpit well. He faces inboard, turned 15° toward the bow, with his head turned another 30° toward the luff. The tiller extension is in his aft hand and the mainsheet in the other. The fleet's tillered boats (Sunfish, ILCA, Catalina 22, Corsair) get the extension from the config; the J/22 gets it from its socket. | [game-05](compare/game-05-crew.jpg) |
| Vest straps and piping with ragged, stepped edges (G6's open item) | The straps, armholes and opening were picked face by face from the polo's triangles | **Vest** (`Tools/blender/build_vest.py`). Every outline is now a straight cut through the shirt: the armhole is three segments, plus the neck, the hem, the opening and both edges of each strap. The webbing is raised 3 mm with side walls, in its own woven material (`MI_Crew_Webbing`). The piping rolls over the edge. The buckles are two bevelled halves on the strap's line. The foam's vertical channels are a 4 mm pillow every 6.5 cm, with darker seams (`M_CrewFabric` `ChanPeriod`). It is 25k triangles, down from 38k. | [game-06](compare/game-06-crew.jpg) |
| The trimmer's white polo showing through her vest when seated | Two things. The outfit's default T-shirt was never hidden: the check read the material's name after it had become a `MaterialInstanceDynamic`. And the polo, skinned slightly differently from the vest, pushed through at her shoulders. | The T-shirt sections are now found by the asset's own slot materials. The polo is imported with its torso under the vest cut away (`<Role>_PoloOpen.fbx`), keeping 2 cm under the neck, hem and opening and 6 cm in from the armholes. | [game-06](compare/game-06-crew.jpg) |
| Faces smooth, like plastic, at capture distance | The optimized MetaHuman build bakes the face with its micro skin detail (tiling pore normal and cavity) and region pores (Scalable Normals) switched off | **Skin.** `scripts/tune_crew_skin.py`, now run by `make-crew-clothes.sh`, turns both on for every role's face, covering the whole face, and strengthens the body's micro normal a little. | close-up below |

Close-up with the micro detail on: the helm at 1.3 m in the afternoon sun (`run-game.sh` with
`-SailingCamTarget=-2.1,0.9,1.3 -SailingCamDist=1.3 -SailingCamYaw=160`): [face.png](face.png).

What didn't work: inpainting the vest's skin weights (Geometry Script `InpaintWeights` with a normal threshold) made the
solver fail on the buckles and webbing walls, and the trimmer's vest went to spikes. The vest keeps closest-point weights
from the T-shirt. The cut-away polo is what stopped the show-through. Lowering the cap 1.5 cm let the crown of the skull
through it, so the cap stays where it was.

## The MetaHuman crew for the PC

`scripts/pack-metahumans.sh [--sources]` zips `Content/Crew/MetaHumans` (git-ignored) with a manifest to
`Artifacts/MetaHumanCrew-<date>-<commit>.zip`. Unzip it over the PC checkout's root. The fabric and gear come from git.
The G8 crew (new vests, cut-away polos, skin switches) is in the zip named in the PR.

## Cost

Results of `scripts/bench-visual.sh 12 g8crew Medium High` on the packaged build (full table in `bench-visual.csv`;
screenshots in `bench/`):

| View | Medium fps (G7 -> G8) | High fps (G7 -> G8) |
|---|---|---|
| beam8 | 92.9 -> 90.3 | 54.3 -> 53.4 |
| beat15 | 90.6 -> 88.2 | 51.5 -> 50.6 |
| storm | 77.8 -> 76.1 | 48.5 -> 47.6 |
| marina | 88.6 -> 85.2 | 51.8 -> 49.1 |
| coast-day | 82.6 -> 81.3 | 48.4 -> 46.7 |
| coast-night | 105.1 -> 102.8 | 52.5 -> 51.2 |
| gulf-sea | 111.5 -> 108.5 | 61.1 -> 59.1 |
| helm-eye | 83.0 -> 84.2 | 45.6 -> 45.1 (reruns 45.8, 45.4) |
| slip | 75.0 -> 73.4 | 49.3 -> 48.6 |
| bridge | 98.5 -> 96.4 | 54.2 -> 53.2 |
| crew | 74.2 -> 74.0 | 46.2 -> 47.1 |
| marina-night | 81.4 -> 80.0 | 53.7 -> 52.6 |

Every view holds Medium 60 and High 45. Helm-eye is on the line, as in G6 and G7. The crew view (G7 -> G8) is the one the
new skin, vests and hands touch most. The 1 to 3 fps drop elsewhere is run-to-run spread on views with no crew close by
(gulf-sea and bridge moved as much as marina).

Tests: 98 passed, 0 failed (`SailingSim.Visual.CrewPose` and `SailingSim.Visual.MetaHumanCrew` now check the reach, the knee
rest and the finger grip).

## Open

- From the side, the trimmer's light blue armhole piping still reads wide at 4 m, where her sleeve meets the vest.
- The caps sit a little high and read as domes. The scalp hair is left off under them, so the nape shows bare. A cap
  that fits needs the head's shape, not a sphere.
- The helm's foot can go through the J/22's topsides when he sits on the near side in the cockpit stance (seen in a
  crew close-up at 15:00). The stance's legs don't know the hull.
- The fleet's rudder models bake a tiller extension lying along the tiller. The live one is drawn as well. The fleet
  models are the PC's this round: a `TillerEnd` socket there, without the baked extension, would remove the double.
- The fine speckle in the grey storm skies and the diamond-plate pattern in very shallow coast water are the PC's, for a
  later round.
