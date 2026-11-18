# #797 Track A ground textures: Ultra stills at the 30 shore stations (PC)

**Build:**

- PR #797 head `0c1d9669` (claude/project-thread-tpx398: the Mac's asset commit 7307fe54 plus licence rows).
- Merged locally with main `f0158285` (merge `0cd04a3c`, never pushed), in a fresh worktree, then `git lfs pull` (exit 0; the assets are committed, no import).
- MSVC build: Succeeded, 0 errors.
- The worktree was removed afterwards; the main checkout is clean at 40226d1c.

**Stills:**

- Every row of the branch's `Tools/envloop/stations.csv` (Track 0's 10 stations at 5, 15 and 60 m: Drone, the rows' own args).
- Run uncooked through `scripts\windows\run-game.ps1` at 1920x1080 with `-SailingQuality=Ultra -ForceRes -SailingScreenPct=100`, the same way as the Track 0 station stills.
- Each still's exact command line is in `args.csv`.
- Taken 07:51-08:12 local, Nov 18. Bean's Saved was held aside and restored (profile hash checked).

**Contents:** `stills/` (30 PNGs), `contact.png` (all 30 at a third size), `crops/` (1:1), `station-fps.csv`.

## What the stills show (inspected at 1:1)

- **The ground is textured at every station.**
  - At 5 m: sand with grass flecks on the club beach, soil and pebbles on the club lawn and clay bank, gravel bands on the bridge bank.
  - A darker wet band runs along the waterline (`crops/crop-env-club-beach-05m.png`, `crop-env-club-lawn-05m.png`, `crop-env-bridge-05m.png`).
  - At 15 and 60 m it reads as a sand, gravel or grass shoreline without visible tiling.
- **sailing-feedback #29's cream glow is gone** at the I-30 bridge and the wooded bank.
  - In the same regions #29 names (`crops/crop-glow-check.png`: wooded-15m x 480-960 y 560-720, bridge-05m x 480-960 y 640-900) the bank shows soil, gravel and the wet band, with no featureless cream blob.
  - This is #797 merged with main f0158285, so it isn't proven which change removed it.

**Things worth a look:**

1. **Club beach 5 m (`crop-env-club-beach-05m.png`):** the grey gravel patches inside the sand have straight, box-like edges. The one at right, about x 1000-1440, y 620-760 of the full still, looks rectangular rather than natural.
2. **Clay bank 5 m (`crop-env-clay-bank-05m.png`):** a soft, lighter vertical strip about 80 px wide (full still about x 850-930, y 530-690) crosses the bank's soil and the tree shadow. It looks like a translucent column, not ground texture.
3. **The waterline is ruler-straight** in the 5 m stills (club beach, club lawn, bulkhead). The bank meets the water along one horizontal line, with the wet band above it. The 15 m views show the same at the beach.
4. **Bridge 5 m:** the reed tufts cast long, thin, fanned shadow streaks across the bank. The wet gravel at the waterline has bright, glittery specular points.

## Frame rate

Uncooked editor `-game` runs, so not comparable with packaged benches. They're only a sanity check:

- 69.0 to 82.8 fps across the 30 stills.
- GPU frame 8.8 to 9.9 ms everywhere (`station-fps.csv`).
- The lowest are bulkhead-60m (69.0) and wooded-05m (69.9).
- The texel-cost share asked for in the docs page (High 3.0 ms for the whole shore) needs a packaged A/B bench; this run doesn't measure it.
