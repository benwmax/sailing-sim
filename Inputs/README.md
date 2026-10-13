# Inputs prepared off the Mac

Reference data and specs produced by cloud sessions for the graphics plan 2 phases (G2 to G4). They are inputs
to the generators, not game content; nothing here is loaded by the game at run time.

- `g3/boat-catalogue.json` (+ `.md`): published dimensions, weighted colour schemes, sail-number and cloth specs,
  wear zones per class. Read by the boat model generator in G3.
- `g3/clothing-shortlist.md`, `g3/realistic-clothing-method.md`: crew clothing: no purchase (Bean's decision),
  script the garments in Blender as MetaHuman outfit assets; prove the polo first.
- `g4/ui-spec.md`, `g4/sailing-sim-front-end.html`: the front end and HUD spec and its clickable mockup. Class and
  binding names in the spec are suggestions; use the repo's real types.
- `g2/` (when present): GeoJSON for buildings, trees and shore armour plus `tiles.json`; the 1 m rasters are too big
  for git and arrive as a release asset (see `g2/README.md`).
