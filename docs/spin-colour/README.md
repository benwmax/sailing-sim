# Spinnaker and coloured sails (realism audit 7)

`docs/realism-audit-1022`, item 7: the J/22's red spinnaker was one flat red, with no seams and no shading from its
shape, and the Hobie's and Sunfish's coloured panels were flat colour too. On top of the sail-look pass (#261:
translucency per cloth, draft shading, faint show-through), this adds the following.

- **Spinnaker panels** (`M_SailCloth` `Layout` 5, `scripts/make_materials.py` `SAIL_CODE`): horizontal cloths across
  the body every `PanelWidth` (1.0 m), and a radial head in the top quarter, its seams fanning down from the head (a
  line of constant `UV1.x` in the normalized planform), taped where they cross. Each nylon panel is its own dye lot, a
  few percent apart. Its seams' overlap reads darker (28%) than a white Dacron seam (12%).
- **The pawn sets the spinnaker's cloth** (`SailboatPawn.cpp`, `RebuildBoatVisuals`): `Layout` 5, the sailmaker's
  `Detail` on High and Ultra, its `Height` from the spinnaker's strips, `PanelWidth`, no marks, no battens. Before, it
  kept the material's defaults: a main's crosscut lines.
- **Nylon translucency** is 0.45 (`MI_Sail_Spinnaker`).
- **Coloured Dacron** (the Sunfish's bands, the Hobie's panels): seams read darker on dyed cloth (up to 22%), and each
  panel is a little apart in tone.
- **The maxi:** her membrane checks (`Layout` 4) now test for 4 exactly, not anything over 3.5, so `Layout` 5 doesn't
  pick up the fibre paths.

Frame cost (uncooked, 1920 x 1080, the spinnaker filling the view, total GPU per frame): High 12.68 ms before, 12.92
after; Ultra 16.89 ms before, 16.77 after. Within the noise.

Before and after: `g5-spinnaker-before-after.jpg` and `g5-hobie-before-after.jpg` (the audit's G5 scenes; "before" is
main after #261). `spinnaker-panels.jpg` shows the panels and radial head from astern.

Seen, not fixed here: the spinnaker's shadow (from the main, and its own far half) has a stair-stepped edge that follows
the cloth's grid. A sharper shadow LOD (`r.Shadow.Virtual.ResolutionLodBiasDirectional -2`) and less translucency (0.3)
both leave it. It looks like the shadow resolving on the coarse `FSailCloth` grid, which is for the Mac.
