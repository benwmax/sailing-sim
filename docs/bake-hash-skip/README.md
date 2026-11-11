# Marina bake: skip unchanged tiles

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
- `TileHashVersion` is part of every hash and the sidecar's first line: bump it when `BakeMesh` builds a mesh differently
  from the same geometry (build settings, attributes, materials), and every tile is baked once more.

## Checked on the PC (Nov 11 2026)

A bake that changes nothing leaves `git status` clean; a change to `BuildClubGrounds` (the skirting 3 cm to 3.5 cm thick)
re-saved only the clubhouse's tiles (`SM_Marina_1_2`, `SM_Marina_2_2`; 22 kept); `SailingSim.World` and `SailingSim.Lake` pass.
When proving it, touch a restored source file before building: a copy that keeps its old timestamp is not recompiled, and the
bake then hashes the stale build's geometry. The log line says how many tiles were
kept: `Baked the RayHubbard marina: ... quads in 24 tiles (24 unchanged, kept as saved)`.

Bridges, shore and houses tiles still re-save on every bake; the same two helpers would cover them.
