# Storm look 5: refractive lens water (`LENS_CODE`, M_LensWater)

Bean's report (sailing-feedback #24) was that the lens drops read as grey discs. The V5 drop shifted the scene a little
and dimmed it by a constant. A real drop on a lens is a cap of water with a short focal length, so it behaves like a
small lens of its own:

- **Upside down and wide.** It shows the scene behind it inverted and wide: the upside-down horizon in every wet
  action-camera frame. The shader mirrors the sample point through the drop's centre and spreads the view over
  `LENS_FIELD` (4) times the drop's own size.
- **A dark rim.** Its steep edge turns the light inside away (total internal reflection). The light through it is
  multiplied by 1 at the centre, falling to 0.4 at the rim.
- **A glint.** One sharp highlight sits high on the drop, toward the sky (up to x2.2).
- **A sharp edge.** The drop's edge on the glass is sharp: a 10% feather, where V5 used 40%.
- **Slams.** A slam's spray (`Spray`, from `AWaterSurface::LensSpray`) throws big splashes (a fourth layer, scale 4.5,
  as many as 0.35 x Spray squared). For a moment it also films the whole glass: up to 55% mask, the view through it
  wobbling.

The custom node now returns a float4: the UV shift, the water's mask and the gain on the refracted light. The gain
replaces the constant 1.06.

It is on High and up, outside the capture mode, as before. Settings > Graphics > Water on the lens (on by default, saved
as `display.lensWater`) sets the blendable's weight to 1 or 0 each frame in `ASailingEnvironment::UpdateRain`.

## Fix: drops cut off square, and streaks at the frame's edge (Nov 15)

The Mac's bow-down slam stills of #703 showed two faults in the big drops. Both are in `LENS_CODE`, so they showed with
and without `-SailingClassicFoam`.

- **Cut off square.** Each layer looked for a drop only in the pixel's own cell. A drop's tail runs downwind up to three
  times its radius, and a slam's splash is up to 0.3 of a cell across. So a big drop ran past its cell, and the part
  outside was never drawn: a hard straight edge through the drop. Now each layer looks in the four cells nearest the
  pixel. A drop is held within 0.66 of a cell of its centre (the stretch is capped at `0.66 / radius`), and drop centres
  sit 0.2 to 0.8 into their cell, so those four cells always hold every drop over the pixel. Only a slam's biggest
  splashes in a strong apparent wind have shorter tails; rain drops are unchanged.
- **Streaks at the edge.** A drop mirrors the view through its centre, five times its own size, so near the frame's edge
  it looked past the frame. The scene texture is clamped there, so the frame's last row or column of pixels was smeared
  across the drop. Now the source point is mirrored back into the frame.
- **One drop per pixel.** Where drops overlap, the pixel looks through the strongest one. The shifts used to add up.

Each layer now hashes four cells instead of one, 16 per pixel. That is a few hundred ALU operations, about
0.1 ms at 4K on the 4090 by estimate.

![An offline run of LENS_CODE on a test pattern: before and after](drops-whole.jpg)
