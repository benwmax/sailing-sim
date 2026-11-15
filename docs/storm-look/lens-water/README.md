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
