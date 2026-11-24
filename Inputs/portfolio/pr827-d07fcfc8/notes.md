# PR #827 (far land at altitude) at d07fcfc8 on the PC, Nov 24 2026

**Verdict: PASS for the lake grid.** In both P4 stills, every bit of land inside the lake's 5 m grid is drawn. The square
holes are gone, and no house or tree floats on water inside the grid. Two smaller things outside the grid are below.

## Build and tests

**Head:** `claude/project-thread-0drn5d` at **d07fcfc8** ("Terrain: keep the near land drawn from altitude"), on main
6630fe1e. I built it in a fresh worktree and removed the worktree afterwards. I only unlinked the crew link; all 541 crew
files are still there. Nothing was pushed to the PR.

- **MSVC build:** Succeeded, 0 errors.
- **`SailingSim.World.TerrainAltitude`:** pass.
- **`SailingSim.World.FarRing`:** pass, 1 warning.
- **All of `SailingSim.World`:** 9 of 9 passed, 7 with warnings.
  - The warnings are missing git-ignored bakes on the PC (`TexasCoast.height`, `Marseille.detail`, `GalvestonBay.detail`)
    and `S_Wind`. They're the usual ones, not new.
- **`SailingSim.Smoke`:** 36 of 36 passed (1 warning, `AsyncPhysicsMatchesSync`, as in earlier runs).
- **Package:** Development `Packaged\Windows-pr827-d07fcfc8`; the cook had 0 errors and 1 warning.

## The P4 stills, against main 6630fe1e

Same shot files and args as the rehearsal (`Inputs/portfolio/rehearsal-6630fe1e/notes.md`, B tries 6 and 2), with the
film args at Ultra 4K, ClearMistral, 10 kn, 12:00. The command lines are in `args-16km.txt` and `args-24km.txt`.

| Shot | Main 6630fe1e (left) vs #827 (right) | #827 still |
|---|---|---|
| Try 6: 16 km, mid-lake start, `look [-90,90,0]` | `P4-16km-main6630fe1e-vs-pr827.jpg` | `P4-16km-4k.png`, `P4-16km-1080p.jpg` |
| Try 2: 24 km, default start, `look [-90,0,0]` | `P4-24km-main6630fe1e-vs-pr827.jpg` | `P4-24km-4k.png`, `P4-24km-1080p.jpg` |

- **16 km:**
  - The whole lake and its shores are solid land out to the grid's edges, with no square holes.
  - The east and west arms, the I-30 and SH-66 bridges and the north fork all read clearly.
- **24 km:**
  - The whole grid is drawn as a rectangle of land.
  - Outside the grid's edge there's only the bare water plane, so at this height the grid's border shows as a hard
    straight edge against blue.

**Outside the grid (not part of the fix):**
- At 16 km the far right strip (east of the grid) shows houses and trees standing on a dark, flat surface, probably the
  far ring's land, with a straight diagonal edge against the water plane. It's only the outer 10% of the frame.
- At 24 km the grid's rectangle is plain to see.
- Either way, P4 is best framed inside the grid: the 16 km shot is.

## Log lines

`B-try6-16000-mid.chunks.txt` and `B-try2-24000.chunks.txt` hold the log's lake line and the bench's `world` block.
- Lake line: 3277x5434 terrain, 11,719 buildings, 35,165 houses.
- Chunks: 4,420 made, 0 dropped, `far_dropped` 0. That's the same count as on main.
- The fix adds no log line of its own.

Bean's Saved was held aside for both runs and restored (7B5CA7BE). No crew is visible (the boat is too small to see at
these heights anyway).
