# Shore loop: close-up shoreline, foliage and rocks (Nov 12 2026)

Bean's ask: use the deep-pass loop on the shore (rocks, the waterline, ground, grass, the water's-edge plants, shore
trees, debris) so it holds up when a player is close: a boat a few metres off the bank, photo mode down to a metre. The
plan with its slices, review points, photo wishes and costs is the Claude Doc "Close-up shore deep pass: shoreline,
foliage and rocks" (https://claude.ai/artifact/DNyAodguK2JnBLmm7Dkx5y). Bean chose to start slice 0 (this page,
stations, cards, tools) and slice 1 (the lake rock kit) before the Nov 21 slice ships; the rest waits until after it.

## The loop

It is the texture loop's (`docs/texture-loop/`) and the part detail loop's, on shore pieces:

1. **Card** (`Tools/shoreloop/cards/<piece>.json`): what the piece is in the game (meshes, material branch, placements),
   what the real thing looks like on Lake Ray Hubbard, the measures it must hit, the references wanted, its stations.
2. **References**: Bean's club photos with a grey card first (the card makes colour measurable); CC0, PD or CC BY
   photos only when there are none, credited. Photos with people never enter the repo.
3. **Measure**: sizes, colour (Lab, against the grey card), cover (what share of the ground a plant takes), height.
4. **Build**: geometry from generators (`Tools/blender/`), looks in `scripts/make_materials.py`. Never edit assets.
5. **Render**: in the cloud with the game's own shader text (`Tools/texloop/dock/hlsl_np.py` runs the HLSL on numpy
   over Cycles data passes: `Tools/shoreloop/rocks/render_rocks.py`), then on the Mac at the stations.
6. **Score**: size within 10%; colour dE under 6 once photos exist; cover within 15%; silhouette; a blind A/B by three
   fresh reviewers who see only the two pictures (a round is kept on 2 of 3; a losing round is reverted); the season
   ladder where it applies; the frame budget.
7. **Fix or log**, at most five rounds; then a sheet for Bean (before, after, reference) and the gate.

## Stations

`Tools/shoreloop/stations.csv` is in `capture-scenes.sh`'s format (`SCENES=Tools/shoreloop/stations.csv
OUT=docs/shore-loop/captures scripts/capture-scenes.sh 8`). Fixed cameras use the `Drone` preset (an 80 degree lens, like a phone held wide) with
`-SailingCamWorld`, never `ShoreTele`: that is a 15 degree telephoto, so a camera 4 m off fills its frame with one
stone. `-SailingCamWorld`'s north and east are relative to launch spot 0 (map 5.5, -37.5), its `up` is above the
water, and `camera.json`'s `camera_m` gives the map metres used. The breakwater's toe stones reach about 5.5 m off its
centreline in `RayHubbard.marina.json`, so the rock stations stand 6.7 to 9.5 m off it (placed by the Mac, Nov 13). Each slice adds its own stations (waterline, grass bank, plant beds, tree line, debris).

## Slices so far

| Slice | Piece | State |
| --- | --- | --- |
| 0 | Stations, cards, tools, method | rock stations and card in; the cover scorer comes with the grass slice (it needs photos) |
| 1 | Lake rock kit | [rocks.md](rocks.md): new stones and shader; waits on the Mac's rebuild and gates |
