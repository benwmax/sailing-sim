# Crew cost: MetaHumans aft on a big crew (Nov 17 2026)

*Bluebonnet*'s own helm-eye view ran at 42.9 fps on the Mac's High tier, under its 45 floor (65 on Medium). The PC traced it
on Ultra at 1080p. Her model costs little. Her twelve MetaHuman crew are the cost:

| Her helm-eye, PC Ultra 1080p | fps | game / render / RHI thread (ms) |
|---|---|---|
| Twelve MetaHumans (crew shown) | 40.8 | 23.5 / 24.1 / 11.6 |
| Crew hidden | 60.5 | 12.4 / 16.2 / 7.5 |
| Twelve SK_Sailor (`-SailingBlenderCrew`) | 60.6 | |
| The J/22 with her three MetaHumans | 58.8 | |
| The maxi with her twelve MetaHumans | 35.7 | |

The GPU added only 1.3 ms. Each MetaHuman is about ten components: body, face, outfit, polo, shoes, vest, cap and grooms.
Every frame they are ticked, moved with the boat and sent to the renderer, which costs about 0.7 ms of frame each on the
CPU. SK_Sailor is one component and costs next to nothing.

## The change

A crew has at most `kMaxMetaHumanCrew` (5) MetaHumans (`CrewPose.h`: `CrewFigureIsMetaHuman`):

- **Who is a MetaHuman.** The aftmost five: the helm, the trimmer and the three hands nearest them. `CrewPlacement` puts each
  figure aft of the one before, with the helm last. These are the figures the helm's eye and the chase camera see closest.
- **The others** are SK_Sailor in the same polo and life-jacket colours (`SampleCrewOutfit`).
- **Their faces.** The five MetaHumans still cycle through all three faces (`CrewMetaHumanRole` is unchanged).
- **Smaller crews are unchanged.** Every crew of five or fewer is still all MetaHumans: the J/22's three, the Lagoon's four
  and the Catalina 30's five. Only the maxi and *Bluebonnet* change, with seven stand-ins forward each.
- **A failed build.** A MetaHuman that fails to build is now an SK_Sailor stand-in; before, that figure was dropped.
- **Crew falls** (Ultra) apply to the MetaHumans only, since SK_Sailor has no physics asset. In a knockdown the forward
  hands on a big boat stay braced on deck. `HasMetaHumanCrew` now asks whether any figure is a MetaHuman, not only the first.

## Measured

The helm-eye view, the cap of five (this change) against `-SailingMetaCrew=12` (all twelve, as before), same build back to
back:

| | Mac High, full resolution: fps (p99 ms, GPU ms) | PC Ultra, 1080p: fps |
|---|---|---|
| *Bluebonnet*, five | **47.0** (23.9, 20.5) | **53.4** |
| *Bluebonnet*, twelve | 43.0 (25.8, 23.2) | 43.9 |
| Maxi, five | **47.0** (25.3, 19.6) | **57.0** |
| Maxi, twelve | 43.5 (27.1, 21.9) | 42.4 |

Both boats are back over the Mac's 45 floor on High. On the PC the cap saves 6 to 8 ms of game thread, and the GPU is
unchanged (`Inputs/bench/pr781-50ee9917/` on `inputs`).

## Measuring

`-SailingMetaCrew=<n>` sets the count, from 0 (all SK_Sailor) to 12 (all MetaHumans, as before). To compare her helm-eye
view, run the bench with `BENCH_EXTRA="-SailingBoat=Bluebonnet -SailingMetaCrew=12"` against the default. Do the same
with `-SailingBoat=Maxi`.

## Tests

- `SailingSim.Visual.MetaHumanCrewCap` (logic, no assets) checks every boat:
  - the count;
  - the helm and the trimmer are always MetaHumans;
  - the MetaHumans include all three faces;
  - every crew of five or fewer is whole;
  - on the capped boats, the MetaHumans sit aft of every stand-in, on both tacks, sitting up and hiked, upwind and running.
- `SailingSim.Smoke.MetaHumanCrewMix` (the pawn, High) checks:
  - *Bluebonnet* and the maxi each draw all twelve, five MetaHumans aft and seven SK_Sailor forward;
  - the J/22 keeps her three;
  - `-SailingMetaCrew=12` brings back the whole crew;
  - Low is all SK_Sailor.

  Without the MetaHumans built, it checks the counts only.
