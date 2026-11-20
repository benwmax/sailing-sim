# #810 Bluebonnet walkable: PC Content commit and checks (046c5c05)

Branch `claude/project-thread-vgcj4i`. Its tip was still `10cea067` when I committed. I added one Content-only commit,
`046c5c05`, and pushed it normally (no force).

## The rebuild (Nov 20, Bean's RTX 4090 PC)

- Fresh worktree at `10cea067` (no main merge), MSVC build OK.
- `make-boat-models.ps1 -Parts bluebonnet -RebuildJClass` ran the `JCLASS_REBUILD` build, `export_game.py` and
  `import_boats.py bluebonnet`: 52 min, exit 0. The Blender log has only "collapse modifier" warnings on `_light_tmp`.
- Export: LOA 39.929 m, beam 6.556 m, draft 4.521 m (physics match), 24 sockets. Triangles: Hull 507,238, Mast 94,828,
  Boom 15,380, Rudder 7,246, Wheel 3,520, Below 631,252.
- Import: hull (16 sockets), mast (4), boom (1), rudder (2) and wheel (1), Nanite on. New
  `Decks/SM_Bluebonnet_Below`. 0 errors, 7 warnings.
- The commit holds only `Content/Boats/Bluebonnet`: `SM_Bluebonnet_{Hull,Mast,Boom,Rudder,Wheel}.uasset` (modified)
  and `Decks/SM_Bluebonnet_Below.uasset` (new, 16.7 MB). Six LFS objects, 36 MB. No other asset was re-saved.

## Checks at 046c5c05

- MSVC build: Succeeded, 0 errors.
- `SailingSim.ShipWalk`: 7/7 pass (Beams, Bluebonnet, Commonwealth, File, Heel, Ladders, Wander).
- `SailingSim.Visual.Bluebonnet`: 2/2 pass (BluebonnetHelmReach, BluebonnetMesh).
- `SailingSim.Smoke`: 32/32 pass (1 with warnings).
- The game log reads "Walk map Bluebonnet: 3 decks, 3 ladders, 1 spots".

## Stills (uncooked, Ultra, 1920x1080, Lake, 8 kn, 15:00; args in `args.csv`, all six in `contact.png`)

| Still | What it shows |
|---|---|
| `bb-cockpit-helm` | The seated helm view (`-SailingCockpit`): the deck forward past the doghouse, with its door hooked open (dark inside), and the binnacle. |
| `bb-deck-fwd-look-aft` | Standing forward of the mast, looking aft: laid deck, winches, mast collar, the doghouse and wheel aft. |
| `bb-deck-aft-look-fwd` | Standing at the quarter looking forward: wheel, doghouse with its open door, skylights, the mast. |
| `bb-cockpit-from-aft` | Looking down into the cockpit well: its slatted sole, the wheel and the binnacle. |
| `bb-saloon-skylight` | Looking down through the saloon skylight: the glass shows the sky's reflection over a dark cabin. |
| `bb-chase-quarter` | Chase camera at 40 m, yaw -135: it frames the sails, not the hull (that framing is too close for her). |

## Below decks: not shot

The saloon, galley and fo'c'sle can't be shot from the command line at this commit:

- No argument puts the walker below. The walker starts at `Helm` (`PlaceWalkerAtHelm`), and
  `-SailingWalkMap` only picks the map.
- `Decks/SM_Bluebonnet_Below` loads only while a walker wants it (`ShipWalkVisuals.cpp:282`, `DecksWanted`), and
  Bluebonnet's top deck loads nothing below (`AlsoLoad` is empty). So the photo camera finds an empty hull, and the
  skylight still shows only a dark cabin.
- Walking there needs held keys, and I don't send synthetic input on this PC.

A small hook on the branch would let the PC shoot those rooms. For example, `-SailingWalkAt=<deck>,<x>,<y>,<yaw>` would
call `Walker.Reset` and set `bWalking`. With it, the saloon would be about x -1.8, the galley x 3.2 and the fo'c'sle
x 6.7, on soles -0.6, -0.5 and -0.4 (`interior_bluebonnet.json`). I have not changed the branch.

Bean's Saved was held aside for the stills and restored. Its profile hash is 7B5CA7BE: Bean played 11:35-11:49 local
today, so that is his own new profile.
