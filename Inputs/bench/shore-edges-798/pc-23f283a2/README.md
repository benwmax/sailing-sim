# #798 Track C shore edges at 23f283a2 (rebuilt M_ShoreEdge): Ultra stills (PC)

**Build:**

- PR #798 head `23f283a2` (the Mac's rebuilt M_ShoreEdge: compile fix plus the Galveston house tiles).
- Merged locally with main `c7f1b59c` (merge `6e51b936`, never pushed), in a fresh worktree; `git lfs pull` after the merge.
- MSVC build: Succeeded, 0 errors.
- The worktree was removed afterwards.

**Stills:** the 9 `env-bulkhead-*`, `env-clay-bank-*` and `env-club-beach-*` rows of the branch's `stations.csv`, uncooked, Ultra 1920x1080, `-SailingScreenPct=100` (`args.csv`). Bean's Saved was held aside and restored.

**Contents:** `stills/`, `contact.png`, `crops/`.

- `crop-bulkhead-05m.png` and `crop-bulkhead-15m.png` are at the same boxes as `pc-0ea7a5fa`, plus `crop-clay-bank-05m.png` and `crop-club-beach-05m.png`.
- `compare-05m/15m/60m.png` set the 0ea7a5fa stills (default material) beside these.
- `material-log.txt` has the game log's shore-edge lines.

## Verdict: M_ShoreEdge compiles clean on D3D, and the edges draw textured

- **Log:** the game log has "Shore edges: 23673 pieces (9063 lot wall segments on 674 lots, 14715 natural shore nodes), 21 of 21 meshes". It has **no** "Failed to compile Material" and **no** "missing usage flag" line for M_ShoreEdge. At 0ea7a5fa both were there.
- **Bulkhead lot:** the walls along the water now draw with the edge material instead of the engine checker (`crop-bulkhead-05m.png`). It is a tan, wood-grain-like surface with darker stain and a green algae band where the water reaches.

**Worth a look:**

- **The lot wall pieces are open shells:** each segment reads as a box with no face toward the lake, so from the water you see its inner side and floor in shadow (the black wedges in `crop-bulkhead-05m.png`). Same geometry as at 0ea7a5fa; only the material changed.
- **Clay bank and club beach look the same as at 0ea7a5fa:** smooth tan banks with no visible kit pieces at these distances. This branch doesn't carry #797's ground textures.
