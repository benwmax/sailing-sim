# Club porch steps, landing and skirting

The clubhouse's grounds are generated in `BuildClubGrounds` (`Source/SailingSim/Private/MarinaActor.cpp`) and baked into
the marina's Nanite tiles (`/Game/World/Baked/SM_Marina_*`). The porch runs along the dock side of the clubhouse with its
deck flush with the floor (`Floor`, 20 cm over the building's ground); the steps come down from its west end to a level
landing where the walks to the shore walkway and the ramp pier start. Toward the docks the lawn falls away under the
porch, about 0.75 m below the floor at the steps.

## What was wrong

1. **Floating slabs** (main before #628): the steps were two 14 cm concrete slabs at fixed heights, the top one flush with
   the floor and the lower one at the ground under its centre. Where the lawn falls away they floated over it with a dark
   gap underneath (the stills from the `#611` doors pass showed it).
2. **A wall** (first try, a9f8c9d7): seating each slab on the ground under it turned the top one into a 0.75 m block of
   concrete in front of the porch: no step at all.
3. **The deck** stood on nothing: where the lawn drops away, the gap under the porch deck read as a black band.

## The rules now

- **Flight**: from the porch floor down to the landing's top, as many risers as the drop needs at **18 cm or less**, with
  the treads sharing the 1.05 m between the porch's edge and the landing (the landing is the last tread). Each step is a
  block from its tread down to **10 cm under the lowest ground below its four corners**, so none floats and the risers
  read as steps. A flat site (a drop of 18 cm or less: one riser) gets a single tread at the landing's height across the
  1.05 m, seated the same way, rather than bare lawn.
- **Landing**: its top is 5 cm over the highest ground under its four corners (it stays level and 1 cm over the walks'
  first slabs, which run under it); its bottom reaches 10 cm under the lowest of those corners, so it can't float on
  steeper ground.
- **Skirting**: white boards in the rail's `Trim` look, 3 cm in from the deck's edge, from the deck's underside down to
  10 cm under the ground, in runs of about a metre so they follow the lawn. They close the front either side of the
  steps and both ends; the steps' 2.2 m stays open. A run is left out where the ground stands above the deck's underside.

## Checks

`SailingSim.World` and `SailingSim.Lake` (the marina and club berth tests) after a marina rebake
(`scripts\windows\run-python.ps1` with the marina bake, or `scripts/make-world-models.sh` on the Mac).

## Stills (inputs branch)

- `Inputs/club-step/` (13a086e7): before, the first try (the wall) and the flight, from 8 m and 30 m.
- `Inputs/club-step-2/` (b09341bf): before (the flight) and after (landing seated, skirting) from 8 m, 30 m and a low view
  along the porch front.
