# World bakes: skip unchanged tiles

`UWorldKitLibrary::BakeMarina` (`Source/SailingSim/Private/WorldKit.cpp`) builds the marina's geometry, splits it into
40 m tiles and bakes each into a Nanite mesh, `/Game/World/Baked/SM_Marina_<x>_<y>`; the caller saves them
(`scripts/import_world.py` from `make-world-models.sh` on the Mac, or a one-off `bake_marina.py` through
`scripts\windows\run-python.ps1` on the PC). Re-saving a mesh writes a new `.uasset` even from the same geometry, so
every bake used to change the LFS object of all 24 tiles (22 of them for nothing in the club-step rounds).

## How it skips

- Each tile's generated geometry is hashed (`TileGeometryHash`: SHA-1 over each look's material name and its vertices,
  normals, tangents, both UV channels, colours and triangles). Values are quantised (positions to 0.1 mm, directions and
  UVs to 1e-4) so the Mac's and the PC's floating point give the same hash.
- The hashes live in a sidecar beside the tiles, `Content/World/Baked/Marina.tilehash` (text: `version <n>`, then one
  `<tile> <sha1>` line per tile, sorted, LF endings by `.gitattributes`). It is in git (covered by the `Content/World/*`
  row of `docs/licences/assets.csv`), so both machines agree on what is already baked.
- A tile whose hash matches the sidecar and whose asset exists is loaded as it is and returned untouched. The callers save
  with `save_loaded_asset`, which only saves dirty packages, so it is not written; returning it also keeps
  `import_world.py` from deleting it as a stale tile. Any other tile is baked and saved as before, and the sidecar is
  rewritten (only when its text changes).
- The hash alone can't decide across machines (#632): MSVC and clang differ in the last bit of a float, and the Mac's
  bake of three tiles moved vertices by up to 0.01 mm (X and Y only; the same vertex, triangle and group counts), which
  crossed the 0.1 mm rounding step in a few positions and, in two tiles, in normals or tangents. No rounding grid is safe
  from noise that lands on its edges. So a tile whose recorded hash differs is compared with its saved mesh before it is
  baked again (`TileMatchesSaved`: the same looks in order, vertex and triangle counts and triangles; positions within
  0.1 mm, compared in double; normals, tangents, UVs and colours within 1e-3). If it matches, it is kept unsaved and the
  sidecar keeps the hash it already records, so another machine's float noise changes neither the tile nor the sidecar.
  A genuine change under that tolerance (under 0.1 mm, a normal turned under 0.06 deg) is kept too: no generator moves
  anything by so little.
- The tolerance compare runs only against a recorded hash. A tile with no line in the sidecar (a new tile, a missing
  sidecar or line) is baked, and so is every tile after a `TileHashVersion` bump (2 since #632; it is part of every hash
  and the sidecar's first line): bump it when `BakeMesh` builds a mesh differently from the same geometry (build
  settings, attributes, Nanite settings, materials), and everything re-bakes once.

## Checked on the PC (Nov 11 2026)

A bake that changes nothing leaves `git status` clean; a change to `BuildClubGrounds` (the skirting 3 cm to 3.5 cm thick)
re-saved only the clubhouse's tiles (`SM_Marina_1_2`, `SM_Marina_2_2`; 22 kept); `SailingSim.World` and `SailingSim.Lake` pass.
When proving it, touch a restored source file before building: a copy that keeps its old timestamp is not recompiled, and the
bake then hashes the stale build's geometry. The log line says how many tiles were
kept: `Baked the RayHubbard marina: ... quads in 24 tiles (24 unchanged, kept as saved)`.

Cross-machine check (#632, PC, Nov 11): with the Mac's three re-saved tiles and the Mac's hashes for them put in place,
a PC bake kept all three by the tolerance check (`24 unchanged, kept as saved; 3 of them matched within tolerance`), left
the Mac's files as they were and did not touch the sidecar.

## Bridges, shore and houses (follow-up to #632)

The same check now runs for every tile bake (`BakeOrKeepTiles`, shared by `BakeMarina`, `BakeBridges`, `BakeShore` and
`BakeHouses`): each kind keeps its own sidecar beside its tiles, `Marina.tilehash`, `Bridges_<Lake>.tilehash`,
`Shore_<Lake>.tilehash` and `Houses_<Lake>.tilehash`, since those asset names carry the lake. The first bake after this
change writes the three new sidecars (every tile has no recorded hash, so it bakes once as before) and they are committed
with the tiles; from then on an unchanged tile is kept as saved. `scripts/make-houses.sh` and `scripts/bake-shore.sh`
need no change: they save dirty packages only, as `import_world.py` does. The log line of each bake says how many tiles
were kept and how many matched within tolerance.

## Mac and PC disagree on bridge and house tiles (Nov 12 2026)

The PC's first bake with the three new sidecars re-saved 617 of the 665 committed bridge, shore and house tiles (last
baked 27 Oct): stale geometry (the clubhouse doors, club docks and terrain attach changes since then), not noise. A Mac
bake on those Windows tiles then kept the shore (19 of 19) and the marina (24, 14 by tolerance) but re-saved 32 of 93
bridge tiles and 136 of 553 house tiles, none rescued by the tolerance; a second Mac pass kept everything, so each machine
is self-consistent. The two machines differ by more than float noise on those tiles, which means a count or a triangle
differs, not a position. The likely cause: those generators turn continuous values into counts and choices
(`int32((L - 1.6) / 3.2)`, `RoundToInt((EaveH - 0.3) / 2.9)`, `CeilToInt32(L / 2.4)`, thresholds on `HeightAt`), and the
footprints' lengths sit on round numbers, so the quotient lands exactly on an integer and the last bit (clang on arm64
fuses a multiply and add, MSVC does not) decides which side it falls. The shore and the marina make fewer such decisions
from such inputs. Until the discrete decisions snap their inputs first (follow-up issue), the Mac's bake is the
reference: tiles and sidecars committed to the repo come from the Mac, and a PC bake's re-saved bridge and house tiles
are discarded, not committed.
