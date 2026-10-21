# The Hobie 16 downwind

Fix-list item 14. On a run the Hobie's crew sat aft on the leeward hull, under the eased boom:

- **The trapeze wire:** it was drawn to any sailor whose hips were outside the rail, so it ran a metre aft and down
  across the main to a crew member who was only sitting out.
- **The mainsheet:** it runs from the boom's end, out beyond the leeward hull, back to the traveler on the rear beam.
  It crossed the hull where they sat: 2.8 cm into the forward sailor's back once the wire no longer held the boom in.

## Changes

- **The seat** (`FAutoTrim`): with the boom eased past 55°, a multihull's crew never move to leeward. They stay at
  their sit-out on the windward hull, where Hobie crews sit downwind.
  - The physics crew weight and the drawn crew stay together: the drawn crew follow the physics' crew offset, and its
    size is still the boat's `CrewSitOut`. Only the side changes.
  - On two hulls the light-air lean to leeward bought nothing.
- **The trapeze wire** runs to the harness only for a sailor in the trapeze stance. Otherwise it is the stub at the
  hounds, and the mast model's shock cord.

## Checks

- **Polars:** Hobie 16 0 of 10 outside, as before (10 kn at 120° goes from 8.82 to 8.74). Corsair 880 and Lagoon 42
  unchanged.
- **RigClearance:** passes. The Hobie's running entries are gone: the trapeze wire through the main and the mainsheet
  through the crew. Only her close-hauled shroud against the jib (1 sample) is still listed.
- **Crew tests:** `SailingSim.Visual.Crew*`, 11 of 11.

## Stills

High, 10 kn, 155° TWA, before (main) and after:

- `run-windward-*`: from the windward side. The crew have moved from the leeward hull to the windward one.
- `run-leeward-*`: from the leeward side. Before, they sat under the sail; after, the leeward hull is clear.
