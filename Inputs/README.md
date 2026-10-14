# Inputs prepared off the Mac

Reference data and specs produced by cloud sessions for the graphics plan 2 phases (G2 to G4). They are inputs
to the generators, not game content; nothing here is loaded by the game at run time.

- `g3/boat-catalogue.json` (+ `.md`): published dimensions, weighted colour schemes, sail-number and cloth specs,
  wear zones per class. Read by the boat model generator in G3.
- `g3/clothing-shortlist.md`, `g3/realistic-clothing-method.md`: crew clothing: no purchase (Bean's decision),
  script the garments in Blender as MetaHuman outfit assets; prove the polo first.
- `g4/ui-spec.md`, `g4/sailing-sim-front-end.html`: the front end and HUD spec and its clickable mockup. Class and
  binding names in the spec are suggestions; use the repo's real types.
- `g2/`: GeoJSON (gzipped) for buildings, trees and shore armour, cover-class tiles, `tiles.json` and the generator
  scripts; the 1 m DEM/DSM and ortho tiles are rebuilt on the Mac (see `g2/README.md`).
- `drills/`: learning content for the six ASA 101 drills: briefings per drill, learning tips keyed to sim events,
  and an 86-question quiz bank, as JSON, plus `validate.py` (checks the steps still match `Drills.cpp`). Wire in after
  G6; see `drills/README.md`.
- `audio/`: sound sample pack (48 kHz 16-bit WAV, Git LFS) for the layers in `USailingSynthWave`: script-built rigging,
  sail, winch, hull wash, dock and outboard sounds plus Wikimedia Commons recordings (birds, rain, thunder, shore surf,
  ships). `audio/README.md` lists each file, its use, suggested driving parameter and loop points; `audio/CREDITS.md`
  has the attribution the CC BY / CC BY-SA clips need once they ship. Optional: the synth keeps working without them.
