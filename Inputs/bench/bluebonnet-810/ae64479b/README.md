# #810 Bluebonnet below decks: PC stills at ae64479b

`ae64479b` (`-SailingWalkAt`, code and docs only, on top of the Content commit `046c5c05`). Built in the kept
`pr810` worktree: MSVC Succeeded, 0 errors.

Stills: uncooked, Ultra, 1920x1080, Lake, 8 kn, 15:00. Each was taken at the bench's 8 s mark, about 7 s after the
walk starts (args in `args.csv`; all four in `contact.png`). Every shot logged "-SailingWalkAt: walking on Below at ..."
(no "nowhere to stand" warning), and the editor waited for `SM_Bluebonnet_Below` to be ready. No material errors and
no default checker anywhere.

| Still | Spot | Mean luma (0-255) | What it shows |
|---|---|---|---|
| `bb-below-saloon` | Below -2, 0, facing forward | **2.9** (95% of pixels under 16) | Nearly black. Brightened (`saloon-galley-brightened.png`): the forward panelled bulkhead with its glazed door to the pantry, the skylight trunk overhead, and settee backs at the bottom. Smeared light blotches on the panelling either side of the door look like Lumen noise or reflections, not geometry. |
| `bb-below-galley` | Below 3, 0.8, facing forward | **7.1** | The galley's forward bulkhead, white tongue-and-groove, with its door open into the lit fo'c'sle (pipe cots, mess table). The galley itself is dim, and its stove and counter to port are out of frame. |
| `bb-below-focsle` | Below 5.3, 0, facing forward | **19.8** | The best lit: pipe cots in two tiers each side on their chains, white panelling, deck beams overhead, the door forward to the sail locker and its ladder, and the mess table's end. The cots and their chains read well. |
| `bb-below-doghouse-stair` | Below -6.2, 0, facing aft | **8.3** | The doghouse stairs' handrails rising to the doghouse window. The window is blown out (sky, with the binnacle against it) and everything around it is black: the window sets the exposure. |

## What to look at

- **Lighting below is too dark** in the saloon (mean 2.9), galley and doghouse foot, against 19.8 in the fo'c'sle.
  The only light is daylight through the skylights and doors, and the exposure follows the incident meter
  outdoors. Without a cabin lamp, more skylight bounce, or an exposure lift when the walker is below, the
  aft rooms read as black.
- **Saloon blotches:** bright smears on the panelling (see the brightened crop), probably Lumen on a dark glossy finish.
- **Eye height:** looks right in the galley and fo'c'sle, with the deckhead and beams just above the frame top.
  In the saloon the skylight trunk fills the top fifth.
- **No z-fighting** that I could see, though the saloon and stair stills are too dark to judge well.
- **The galley spot** at y 0.8 faces the forward bulkhead. A view of the galley itself needs a yaw of about -90 (to port)
  or a spot further aft.

Bean's Saved was held aside for the stills and restored; profile 7B5CA7BE.
