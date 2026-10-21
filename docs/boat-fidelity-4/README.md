# Boat fidelity, phase 4 (PC half): sails, sheets and rig lines

This is the PC half of phase 4 of the Boat Fidelity Plan. The Mac's half is the cloth simulation: `FSailCloth`, the
mainsail crumpling in a swell, and the leech crease normals.

## Sails (`M_SailCloth`: `build_sail_cloth` and `SAIL_CODE` in `scripts/make_materials.py`)

With `Detail` on, the sail gets what a sailmaker's sail carries. The pawn turns `Detail` on for High and Ultra; Medium
and Low keep the old path line for line.

- **Seams that stay on screen.** Each seam keeps a minimum width of about 0.6 px. Its strength falls off as it widens, so
  the panel lines still read at mid range instead of shimmering out. Up close there is the overlap's edge line and two
  rows of 6 mm zigzag stitching.
- **Tabling.** Luff 25 mm, leech 40 mm and foot 30 mm, each with a stitch line.
- **Corner patches.** Three layers each at the tack, clew and head, scaled with the sail (the J/22 main is 7.6 m). They
  have straight edges at 45-degree steps, like cut panels, a stitch line inside each edge, and a 0.3 mm step in the
  surface normal at each edge.
- **Batten pockets.** A stitch line along each side and the elastic end at the leech.
- **Against the sun.** Every extra layer of cloth halves the light coming through, so patches, tabling and pockets show
  darker in backlight. Stitch holes and patch edges show too.
- **Dirt toward the foot.** The new `Age` and `Care` parameters drive it (E1's convention). `Age` -1, the default, means
  unset and looks exactly as before. Every boat has `Age` unset today, so the foot is unchanged until a lane sets it.
- **Insignia.** The main's insignia was a copy of the J/22 class mark (a red "J" plus "/22"). It is now a made-up emblem:
  a red sail over two navy swells, with no letters (`scripts/make_sail_marks.py`). The digits are unchanged. The licence
  notes are updated (`docs/licences`, item 2).

The stitches and edge lines size themselves from the pixel depth, which is ray-tracing safe (no screen-space
derivatives), and fade out beyond a few metres.

## Rope (`M_RigRope`, `scripts/import_boat_detail.py`)

- **Yarns.** Fine streaks run along the cover's two helices, so each carrier reads as twisted fibre at arm's reach.
- **Weave shadow.** The shadow in the weave is a little deeper.
- **Fuzz.** Polyester fuzz brightens the rope's silhouette, more on a sun-faded rope.

These are a few ALU operations on every tier. `ROPE_MATERIAL_ONLY=1` rebuilds just `M_RigRope`.

## Coiled tails become rope (`BoatModelVisuals.cpp`)

The "painted-flat coils" on the J/22's cockpit sole, seats and cabin top were the baked shadows of the hero's coil
geometry. `bake_j22_hero.py` keeps the coils out of the game mesh as "live" rope, but nothing in the game drew them.

They are now drawn live: the mainsheet tail, three halyard tails and both jib tails, in the rope's own colourways. They
are on the rig-line mesh with `M_RigRope`, built once into their own section, and they lie exactly on their shadows.
There is no rebake and no `AddModelPart`.

| Piece | Path |
| --- | --- |
| Coil dump | `build_j22_hero.py` writes the polylines; `J22H_COILS_ONLY=1` skips its sail maps, which need Pillow inside Blender |
| Coil data | `Inputs/j22-hero/J22H_coils.json` (the anchor rode is already in `SM_J22H_Interior`, so it is left out) |
| Generated table | `Tools/boats/make_coil_data.py` turns the JSON into `Source/SailingSim/Private/J22CoilData.inl`, because `Inputs/` is not staged in the game |
| Tube builder | `AppendPolyTube`: Catmull-Rom smoothed, with parallel-transported rings so the braid doesn't twist |
| Compare | `-SailingNoCoils` turns the coils off |

## A minimum on-screen width for the rig (`UpdateModelRig`)

Every shroud, stay, sheet and control line is drawn at least 0.8 px wide, measured at its middle's distance from the
camera. A 5 mm shroud was under half a pixel at chase range and flickered under TSR.

The radius steps by a quarter at a time, and a change of radius is now part of each section's "moved" check. So a
moving camera re-uploads a section only when a step is crossed. `-SailingNoMinLineWidth` compares.

## Stills (Ultra, uncooked, 1600x900; before = main's materials with `-SailingNoCoils -SailingNoMinLineWidth`)

- `sails-before-after.jpg`: the clew close up, the sails from 5 m to leeward, and from 5 m to windward against the light.
- `coils-ropes-before-after.jpg`: the jib tail on the seat at arm's reach, the cockpit sole, and the cabin top.
- `rig-width-chase.jpg`: the chase view at 14 m, cropped. The shroud behind the main and the backstay hold their line.

## The leech crease

The leech crease does not come from `SAIL_CODE`. It has no term along the leech. Its creases are the fold lines parallel
to the foot, the stress wrinkles fanning from the clew (Layout 0) and the seam pucker. So the crease is the cloth's
normals (`FSailCloth`), which is the Mac's job.

## Cost (Ultra, J/22 alone)

Packaged Development, RTX 4090, 1920x1080, two runs each. "On" is this branch; "off" adds `-SailingNoSailDetail
-SailingNoCoils -SailingNoMinLineWidth`.

| Tier, view | On (fps) | Off (fps) | GPU (ms) | Base pass (ms) | boat_visuals (ms) |
| --- | --- | --- | --- | --- | --- |
| Ultra, chase 9 m | 75.1 / 75.4 | 75.2 / 80.7 | 6.05–6.29 vs 6.05–6.11 | 2.54–2.67 vs 2.59–2.61 | 0.62–0.64 both |
| Ultra, sails from 5 m | 74.8 / 76.0 | 75.0 / 79.9 | 6.53–6.65 vs 6.66–6.73 | 2.85–2.90 vs 2.91–2.92 | 0.69–0.70 both |
| Medium, chase 9 m | 92.5 / 92.4 | 92.0 / 99.2 | 3.30–3.34 vs 3.27–3.30 | 1.47–1.51 vs 1.49–1.52 | 0.71 vs 0.70–0.77 |

In each first pair, on and off match. The second "off" run is higher in all three sets: it is the render thread's
run-to-run drift, since the GPU, base pass and boat_visuals times are the same either way.

What each part costs:
- **Sail work:** per-pixel ALU behind a uniform branch (Medium samples nothing new).
- **Coils:** about 11k static triangles (six tails, about 700 rings of 8 sides), built once.
- **Minimum width:** it only changes radii.

The Mac gate (Medium 60, High 45) still has to be run on the Mac.

## Test

`SailingSim.Visual.SailAndRig` checks:
- the coil JSON and the generated `.inl` agree;
- every coil point is inside the hero hull's bounds, and each tail is a rope (2–8 mm radius);
- `M_SailCloth` has `Detail` (off by default), `Age` (unset) and `Care`.
