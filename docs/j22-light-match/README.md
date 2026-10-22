# Light J/22 matched to the hero (boat fidelity)

AI boats, the ghost and the marina's J/22s draw the light model (`SM_J22_*`, `Tools/blender/build_j22.py`). The hero's
rebuild (`docs/j22-rebuild/`) changed fittings that show from a boat length or two away, so the light model now carries
the same ones, built from simple shapes to stay light.

| Change (as on the hero) | Light model |
| --- | --- |
| Two horn cleats abreast on the bow, 0.42 m aft of the stem, instead of one on the centreline | Two 0.13 m `horn_cleat`s |
| Rudder fittings: two gudgeons bolted to the transom, two lugs each | Stainless straps and lugs (was one box) |
| Cockpit drain outlets low on the transom's corners | A white flange (`Rubrail` slot) round a dark bore |
| Laminated tiller sweeping up from the rudder head, then nearly level | The tiller's curve |
| Teak caps on the cockpit coamings | One teak tube along each coaming |
| Teak handrail on the cabin top | A bar on three legs a side |

The drain flanges sit in `Rubrail`, not `Topsides`: `SailingSim.Visual.J22Mesh` measures the canoe slots, and a flange
there added 4 mm to the measured length. Left out because they show only close up: the spinnaker sheet leads and the
halyard cam spacing. The light model already had six turning blocks at the mast step.

## Budget

| Mesh | Triangles before | After | Material slots |
| --- | ---: | ---: | ---: |
| `SM_J22_Hull` | 43,635 | 45,495 | 15 (unchanged) |
| `SM_J22_Rudder` | 536 | 536 | 3 (unchanged) |
| `SM_J22_Mast`, `SM_J22_Boom` | 639, 276 | unchanged (not reimported) | 2, 3 |

The hull is Nanite, so its 4% more triangles cost almost nothing. Its measured length (6.860 m), volume (1.046 m³) and
centre of buoyancy are unchanged.

New test `SailingSim.Visual.BoatBudget` covers every boat mesh. It checks phase 0's budgets: at most 40,000 triangles for
a part that isn't Nanite, and a target of 8 material slots. No boat meets the slot target yet (that is the slot-merge
pass). Until then each mesh is held at today's slot count, so no boat can grow; lower its entry when it drops.

## Sockets

`J22_sockets.json` is unchanged. `BowCleat` stays on the centreline between the two cleats, where the bow lines lead.
The berthed dresses (`build_berthed.py`) read those sockets and draw their own covers over `SM_J22_Hull`, so they
weren't rebuilt. The marina still shows them correctly.

## Stills (Ultra, uncooked, before at left)

| Still | View |
| --- | --- |
| `ai-20m-before-after.jpg` | Light J/22 at 20 m, sailing (`-SailingClassicJ22`) |
| `ai-60m-before-after.jpg` | At 60 m |
| `ai-8m-before-after.jpg` | At 8 m from the quarter: the coamings, handrail, tiller and bow cleats |
| `marina-row-before-after.jpg` | The home marina row: berthed light J/22s |
| `hero-beside-ai-before-after.jpg` | The hero in its slip beside the berthed light boats |

From 20 m and 60 m the two models now read the same, which was the aim: nothing changes the outline.
