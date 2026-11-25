# Wildlife Phase 1: the distant birds (Nov 25 2026)

Phase 1 of the wildlife plan (Bean's plan doc "Wildlife plan: accurate animals for each sailing area",
https://claude.ai/artifact/CZNpXuF7h14SXZxj6j6MCY). Bean put it in the Dec 11 release (Nov 25, "we can do it!"); the
near birds, fish, dolphins, sharks and the fin whale stay after it.

## What a sailor sees

Birds within 2 km of the camera, from each world's table (`Content/TerrainData/<World>.wildlife.json`, Phase 0): the
right birds for the month, more at dawn and dusk for the ones that feed then, fewer in rain or over 20 kn, none at
night. Each flies its style: pelicans in lines just over the waves, gulls hanging in the wind and resting on the water,
terns and gannets circling and plunging, cormorants fast and low, shearwaters banking over the wave tops, vultures and
raptors circling high, herons standing in the shallows, swallows and swifts zigzagging low, ducks and coots in rafts.
Resting birds take off when a boat comes inside their flush distance and land again 200 to 400 m on. About a quarter of
the flocks fly past within 50 to 150 m of your boat (the games players praise for wildlife put it near the player).

## How it works

- `Sailing::FBirdFlocks` (`Wildlife.h`, plain C++ on the sim clock): spawns and retires flocks so each bird's count in
  view follows the table (the expected number from its habitat's area inside 2 km, the month, the hour and the
  weather, steered by how long its flocks stay), steps leaders and members (each bird follows the path of the one ahead
  in lines and vees), flushes resting flocks, and returns what to draw, nearest first, within the tier's budget.
- `Sailing::FWildlifeHabitatMap`: 50 m cells over 8 km round the camera, classed from the terrain into open water,
  channel, offshore, far offshore, shallows, shore, harbour and cliffs, with each cell's highest ground or tree top
  (a 5 x 5 grid over the cell plus half its steepest step: Marseille's cliffs climb 30 m between corners).
- `AWildlifeActor` (game): builds the map on a worker when the camera is 1.5 km from its centre (or the tide moves
  0.3 m), feeds the flocks the month, local hour, sun, rain and wind at the camera and every boat (sailboats and power
  vessels flush birds), and draws them:
  - far birds (400 m to 2 km): the engine's 1 m plane turned to the camera, x along the span as the camera sees it,
    `M_BirdFar` drawing the silhouette (body, wings bent at the wrist, the style's dihedral and crank, the wingbeat).
    A bird under two pixels keeps a two-pixel quad and thins its dithered cover by the same share.
  - mid and near birds (under 400 m): `SM_Bird_<Style>`, 136 to 152 triangles (`Tools/blender/build_birds.py`),
    `M_BirdMid` beating the wings about the shoulder in the vertex shader, folding them along the back when resting,
    swinging a heron's legs down to stand. Until the bodies are imported every bird is a quad.
  - plumage per species: `Sailing::BirdLookFor` (back, underside, wingtips; field-guide tones).

Budgets (far / mid / near): Low 100 / 20 / 4 (all quads), Medium 200 / 40 / 6, High 300 / 60 / 12, Ultra 500 / 100 / 20.
Instanced, unshadowed, out of the distance-field, Lumen and ray-tracing scenes. Plan budget 0.5 ms GPU and 0.3 ms game
thread on High; the logic's update is 0.05 to 0.25 ms at the 99th percentile in `scripts/wildlife-check.sh`.

## Running it

- `scripts/wildlife-check.sh [World|all] [--months 1,4,7,10] [--hour 10] [--sail] [--tier 2] [--spot N] [--species]`
  builds the physics standalone and runs every launch spot on the real terrain: counts against the tables, birds drawn
  per band against the budget, flushes, birds under the ground (fails), update time. All five worlds pass.
  `WILDLIFE_DEBUG=1` prints each bird found under the ground.
- `scripts/make-birds.sh` (Mac, after `build.sh` and `make-content.sh`): Blender builds the bodies, the editor builds
  `M_BirdFar` and `M_BirdMid` and imports the bodies to `/Game/Wildlife/Birds` (`scripts/import_birds.py`).
  `BLENDER=<a python with the bpy module>` works in place of Blender. On the PC the same two steps run by hand:
  `blender -b --factory-startup -noaudio -P Tools/blender/build_birds.py -- <out>` (or `python build_birds.py <out>`
  with bpy), then `UnrealEditor-Cmd.exe <SailingSim.uproject> -run=pythonscript -script="scripts/import_birds.py <out>"
  -unattended -nosplash -nosound -stdout`, which ends with `Birds: done`.
- Tests: `SailingSim.Wildlife.Tables`, `.Habitats`, `.Day`, `.Counts`, `.Flush`, `.Repeatable`, `.Sprites`.
- Args: `-SailingNoWildlife` leaves the birds out; `-SailingWildlifeScale=<f>` scales every bird's density.

## Open

- Tune by eye against video (the plan's method): wingbeat rates, flock spacing, the far quads' lighting (`SkyFill` on
  `M_BirdFar`), how many birds a sunny July afternoon shows.
- Splashes for plunges and landings are returned (`FBirdFlocks::Splashes`) but not drawn until Phase 2.
- A crew remark when dolphins or a whale show is Bean's call (scenery only for now).
