# Far whitecaps as flecks (option A of docs/far-caps/)

Past the first texels of the short-wave grid, `M_WaterV4` reads each pixel's whitecap cover from the fold table
(`DetailC`). That is the share of the sea under foam: 0.2–0.4% on the lake at 16–20 kn. Spread evenly over the pixel,
nobody can see it, so the caps stopped at about 250 m. Real distant caps are bright flecks on dark water.

## How

The table's cover is redistributed into flecks. It is never added to: `crest` and `caps`, the mask the cap thresholds,
`SailingSim.Visual.Whitecaps` and `-SailingDebugFoam` work on, are untouched. Only the drawn foam changes.

- **Cells:** world-fixed cells in the map frame, so a fleck holds still as the camera moves and turns. Each is five
  pixel footprints across, by the footprint's geometric mean. A fleck is then about three pixels, and at a grazing view
  a cell is wider than it is tall, so far flecks read as short horizontal dashes.
- **Levels:** the cell size steps by twos with the footprint, two levels cross-faded, so flecks don't pop as the
  distance changes.
- **The fleck:** each cell holds one round fleck, radius 0.3 of the cell, centred within its middle tenth. Its edge is
  feathered over at most one radius, which adds aa²/12 to its area.
- **Its life:** 4 s, a flat-topped rise and fall (1.6 sin, clamped at 1, mean 0.7937), with each cell's phase hashed.
- **Its probability:** cover ÷ (area × mean life), so the mean is the cover. Past about 25% cover a fleck is brightened
  instead; the lake never gets there.
- **Smaller flecks** (1.5 and 3 footprints) were tried first. Dimmed by their feather and the temporal AA, they didn't
  read.

**The test:** `SailingSim.Visual.FarCapFlecks` mirrors the fleck on the CPU (`FarCapFleck`, `WaterTests.cpp`; keep it in
step with `FLK` in `make_materials.py`). It averages over 14,400 cells and 24 times: at covers of 0.2%, 1% and 5% and
cells of 2 m and 16 m, the mean is the cover within 2% (bound 15%).

## Motion

`motion-strip.jpg` is four consecutive frames, 0.1 s apart, of a recorded run on the packaged build (the wide view, 20
kn), cropped to the far band. A fleck holds its place from frame to frame, moving only with the camera, and fades at the
end of its life. Nothing crawls or shimmers.

## Stills

`wide12/16/20-before`/`-after` (from 120 m, 18° down) and `helm12/16/20-*` (helm eye), High. "Before" is main before
#233, whose change was invisible.

- **Wide:** caps now continue as flecks from about 150 m out toward the horizon, thinning with distance, where before
  the water went blank past about 250 m.
- **Helm eye:** unchanged. From 2 m the far sea is foreshortened to a few pixels a kilometre, and a flat fleck there is
  sub-pixel. That is option B (cap sprites with height), which comes back as a decision first.

## Cost

The gate's GPU times are within noise of the last gate on main: helm-eye 15.71 ms against 15.69, beam8 14.95 against
15.04, storm on High 47.4 fps against 47.7. The flecks run only in the far branch, about 60 ALU a pixel.
