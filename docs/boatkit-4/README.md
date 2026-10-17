# Boat kit phase 4: round 12's J/22 fixes

Bean marked blind round 12 on Oct 16 and caught all 20 stills. Five of the tells were about the J/22: no wear, blocky
fittings at the winch, untextured gelcoat and non-skid, a tiller texture that looked repeated, chrome too shiny, and a
"random rectangle at the back of the boat". Every one of those stills showed the game's default J/22
(`Tools/blender/build_j22.py`), not the hero model (`Inputs/j22-hero`), which only drew with `-SailingJ22Hero`. The
default model also carried a bow pulpit, stanchions and lifelines, which the lesson boats at Rush Creek (TX 7295 EC,
7297 EC) don't have.

## Part 1: the hero is the player's boat

`ASailboatPawn::ModelMeshesFor` now gives the player's J/22 the hero: the open deck, kit winches and fittings, the cabin,
the outboard on its bracket, the baked gelcoat and wood. AI J/22s and the ghost keep the light model with their
liveries. The pawn's grey box on the transom (a stand-in for engines without a model) is skipped when the model carries
its own outboard (`FBoatModelMeshes::bOwnOutboard`).

- `-SailingClassicJ22` draws the older model on the player's boat, for comparing.
- `-SailingJ22Hero` still works and now also puts the hero on AI J/22s.

The gate: `scripts/gate.sh --scope boats` on the Mac, Medium 60 and High 45. If High falls under 45 with the hero, the
fallback is a per-tier choice in `ModelMeshesFor` (hero only where it holds), not dropping it.

## Part 2: the light model and the boat materials (next PR)

The light J/22 loses its pulpits, stanchions and lifelines, gets an outboard on a bracket and cast, rounded fittings, and
a tiller drawn as one taper (its eight capped segments shaded in bands). The boat materials get grime and a mottle
anchored to the boat, wood grain, and less mirror-like stainless, with the wear on E1's seeded slot layout.
