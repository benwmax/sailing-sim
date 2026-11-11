# #632 marina bake on the Mac: three tiles hashed differently from the PC

pc/bake-hash-skip 999c7ae5, built on the Mac (WorldKit.cpp and MarinaActor.cpp touched first), then
`unreal.WorldKitLibrary.bake_marina("RayHubbard")` alone in a commandlet, each mesh saved with `save_loaded_asset`.
Log: `Baked the RayHubbard marina: 7329 quads in 24 tiles (21 unchanged, kept as saved)`.

These are the Mac's re-saved tiles and its `Marina.tilehash` (the committed one is the PC's):

| Tile | PC hash (committed) | Mac hash | PC size | Mac size |
|---|---|---|---|---|
| SM_Marina_2_1 | f91d1aad86ae0f93d3ff562f962bb42e5894aca6 | cb6310716f0ff40cc389e8990dd514eeac6a13ef | 21,791 | 21,790 |
| SM_Marina_m1_3 | 70d8314a8c8a8ed4be4e84163f85957b1fa13ce4 | ecf831fbdca047d79fb8d0b5804b2f977bca4349 | 29,612 | 29,594 |
| SM_Marina_m1_4 | 089939009dc0f671d09b9706b0f9064ffa334987 | 7a5ca734dc2d3e3c1e207bacb76a91eeaae442be | 30,677 | 30,660 |
