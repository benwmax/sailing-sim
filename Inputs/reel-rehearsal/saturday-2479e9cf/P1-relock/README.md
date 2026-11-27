# P1 relock check: the three P1 passes already share one boat path (PC, Nov 27 2026)

**Asked:** P1-final and P1-wireframe looked misaligned (the boat smaller and further out in the wireframe pass), so the
layer peel would need all three passes re-shot from one path.

**Found: the path is already the same in all three passes; nothing needs re-shooting for alignment.**
- All three takes ran with the same launch line apart from the view mode: `-benchmark -fps=60` (a fixed step),
  `-SailingSeed=7`, P1's start and conditions, `-SailingBenchWarmup` at rec.ps1's default 10 s.
- In film mode the warm-up and the recording are counted in frames, not wall time (`FFilmFrameClock`, `SailingGameMode.cpp`
  1310-1316). Each log says "SailingRecord: fixed step 0.01667 s, 720 frames from frame 600, one every 1". So the
  wireframe pass's shorter wall time (236 s against 906) doesn't change game time.
- **The telemetry is byte-identical:** the three `P1-*.telemetry.csv` files (her speed, heading, heel and so on every
  frame) have the same checksum.
- **The camera is the same:** each `camera.json` gives `[-43.21, 10.44, 2.20]`, pitch 2.7, yaw 19.2, fov 34 at frame 0.
- **The overlays here** (`overlay-final-vs-wireframe-f0000|0360|0719.webp`, and the same against lighting-only) average
  P1-final with each pass at its first, middle and last frames. The hull, mast and boom sit on the same pixels in each.

**Why the wireframe pass looks smaller:** in the engine's wireframe view the sail cloth isn't drawn as a surface (see
`docs/film-mode`). So her silhouette loses the two big white sails, and only the hull and rig lines stand out. The far
shore and grid also read as lines. The boat isn't further out; less of her is drawn.

The lighting-only re-take (the sail marks and the far-cap squares) is still queued after #846: one pass at 4K on the same
path, into a new folder.
