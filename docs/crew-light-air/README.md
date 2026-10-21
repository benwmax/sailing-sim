# Light-air dinghy sailors and the Hobie's crew

These are items 4, 5 and 7 of the PC's Ultra audit (`docs/clipping-audit-2/` on `audit-fixes`).

## The ILCA and the Sunfish running at 4 kn

The sailor sat back as if in a full hike: back arched, face to the sky, hands at the hips (`ilca-light-air-hike.jpg`).

The crew model had them sitting in from the deck edge, as it should in light air. But the dinghy stance (`CrewPose`
`DinghyHike`) leaned back at least 20°, whatever its hike. The idle clips weren't the cause: the pose was the same with
`-SailingNoCrewClips` and `-SailingCrewStill`.

- **The fix:** `FCrewPoseParams::Inboard` measures how far in from the edge the sailor sits, 0 at the edge and 1 at
  the inner seat (`CrewPlacement`).
  - Sitting in, they sit up, a little forward, the head level with the trunk.
  - At the edge the hike is as it was (`ilca-beat15-after`: hiked hard at 15 kn).
- **The test:** `SailingSim.Visual.CrewPose` now checks that a dinghy sailor sitting inboard doesn't lean back.

## The Hobie 16's crew with their arms overhead

The Hobie's crew take the dinghy stance. Two problems:

- **No grips:** her twin tillers have no socket to hold, so both hands stayed at the stance's free angles. Leaning
  back, those point overhead at the sail.
- **The legs:** they dropped into a cockpit well she doesn't have. On the trampoline that read as kneeling.

The fix:

- **The hands:** on a multihull, a free hand rests on the knee, as the keelboats' do.
- **The legs:** on the trampoline, the dinghy stance takes the flat-deck legs: knees up, feet on the trampoline in front
  (`bFlatDeck`, which the rail stance already used).

At 15 kn the trapeze hand still reaches up to the wire as the crew steps out (`hobie-15-after`). That is what a crew
does.

## The J/22's third crew

Checked at 15 kn on a beat (`j22-15-after`): the three sit on the side deck. Nobody is perched on the cabin top.

## Stills

High, before (main) and after: `ilca-run-*` and `sunfish-run-*` (4 kn, 165° TWA); `hobie-4-*` (4 kn, 90°);
`hobie-15-*` (15 kn, 60°).
