# #810 Bluebonnet below decks, lit: PC stills at bec7847b

`bec7847b` ("Light below": the eye adapts under a deckhead; her ten brass lamps are lit). Built in the kept `pr810`
worktree: MSVC Succeeded, 0 errors. The `.walk` is a plain git file (not LFS), so the checkout brought it.

## Tests

| Filter | Tests | Failed |
|---|---|---|
| SailingSim.ShipWalk | 7 | 0 |
| SailingSim.Visual.Bluebonnet | 2 | 0 |
| SailingSim.Smoke | 32 | 0 (1 with warnings, the standing one) |

## Stills

Settings: uncooked, Ultra, 1920x1080, Lake, 8 kn, 15:00. The bench ran 10 s, so each still is about 9 s after the walk
starts. Every below shot logged "-SailingWalkAt: walking on Below at ...", and `SM_Bluebonnet_Below` loaded. No material
errors and no checker. Files: `args.csv`, each shot's `bench.json`, `contact.png`, and
`saloon-lamps-and-stair-crops.png` (full-resolution crops).

| Still | Mean luma (ae64479b) | Pixels under 16 | fps | GPU ms | Game ms | Render ms |
|---|---|---|---|---|---|---|
| `bb-below-saloon` (-2, 0, 0) | **82.5** (2.9) | 21% (95%) | 66.2 | 11.51 | 12.23 | 14.80 |
| `bb-below-galley` (3, 0.8, -90) | **73.3** (7.1, at yaw 0) | 13% (94%) | 68.3 | 9.77 | 11.97 | 14.56 |
| `bb-below-focsle` (5.3, 0, 0) | **110.0** (19.8) | 0% (68%) | 71.8 | 8.92 | 11.89 | 13.69 |
| `bb-below-doghouse-stair` (-6.2, 0, 180) | **84.0** (8.3) | 15% (95%) | 66.6 | 12.42 | 11.78 | 14.98 |
| `bb-deck-aft-look-fwd` (photo cam, as at 046c5c05) | **114.4** (114.5 at 046c5c05) | 1% (1%) | 79.4 | 9.28 | 8.94 | 12.57 |

These are 10 s uncooked benches, so take the frame times as rough. Nothing clips: 0.1% of pixels or less are at 250+.

## Findings

- **Exposure below is fixed.** Every room reads now: mean luma is 73-110, against 3-20 at ae64479b. The outside
  exposure is unchanged: the deck still measures 114.4, against 114.5 at 046c5c05.
- **The lamps:** two lamps show in the saloon and three at the stair foot. Each is a small warm hot spot with a soft
  pool on the panelling. None blows out (no clipped pixels). At this distance I can't see a brass fixture body round
  the bulb; the light looks like it sits on the panel face (crops).
- **Shadow artifacts:** shadow acne shows as wavy stripes on the stair treads' faces and edges (crop, lower left).
  The handrails' long shadows on the stair are clean.
- **The saloon's Lumen blotches are mostly gone.** A faint mottled darkening remains on the starboard panelling to the
  right of the second lamp (crop, top right).
- **Colour:** the mahogany reads very saturated orange in the saloon and at the stair foot, now that the exposure opens
  six stops onto lamp light at 2700 K. The fo'c'sle's white panelling looks natural.
- **The galley at yaw -90:** the mast fills the middle of the frame, a grey cylinder through the galley. The stove
  and counter show to its right, and the white panelling to the left. A spot a little aft (x about 2.4) or a yaw of
  about -60 would clear it.
- **Frame times below against on deck:** GPU time below is 8.9-12.4 ms, against 9.3 ms on deck. The saloon and stair,
  with lamps in view, are the highest. The game thread is about 3 ms slower below than on deck (11.8-12.2 against
  8.9 ms), and the render thread about 2 ms slower (13.7-15.0 against 12.6 ms). That is worth a look in a cooked
  build (shadowed point lights, deck streaming).

Bean's Saved was held aside for the stills and restored; profile 7B5CA7BE.
