# Rain on deck (boat polish, phase 6)

When it rains, puddles collect in the low spots of the deck, the rain rings them and beads on the gelcoat, and water
drips off the boom and the sheer. This is for the player's boat on High and Ultra, in `M_BoatSurface`/`M_BoatMast`
(`BOAT_CODE` in `scripts/make_materials.py`) and in the hero J/22's `M_J22HeroSurface` (`DETAIL_CODE` in
`scripts/import_j22_hero.py`).

## State (C++, `ASailboatPawn::UpdateBoatWetness`)

| MPC_Boat | What sets it |
| --- | --- |
| `Rain` | The boat's local rain (`FWeatherState::Rain`, 0..1) |
| `Puddle` | `PuddleLevel`: fills in about ten minutes of steady rain, drains and dries in about fifteen once it stops; heel spills it |

`-SailingPuddle=<0..1>` starts the puddles that full, for stills; `-SailingDeckWet=1` starts the deck soaked.

## Shading

- **Puddles.** Low spots are the lows of a value noise (37 cm on the hero; `M_BoatSurface`'s grime noise) on level surfaces (normal within about 23° of up, not
  metal), filling as `Puddle` rises. A puddle is a still mirror: 30% darker, roughness 0.012 on High and Ultra (0.03
  below), a stronger clear-coat lobe, and the deck's texture drowned (flat normal).
- **Rain rings.** One drop per 14 cm cell, each with its own phase. Its ring grows out to 5 cm and fades, 6 mm wide,
  on puddles and, at half strength, on the wet deck. The ring bends the normal outward and brightens a little. At first
  the rings were 22 cm cells out to 7 cm and 3.5 mm wide, which came out under a pixel from the cockpit camera.
- **Beads.** On level gelcoat outside the puddles, and on the metal fittings (`M_BoatSurface`): a bead on half the
  8 mm cells. Rain on metal tightens its gloss between the beads.
- **Distance (rain-fade).** The rings and beads fade out from 2 to 3 m from the camera, and past 3 m a branch skips
  their maths. They cost 0.2 ms on the Mac's storm view on High and weren't visible from its 3 m camera. The puddles'
  darkening, gloss and flat normal stay at every distance: they're cheap.
- These come before #203's below-horizon roughness (`docs/lee-topside-patch/`), which still runs last, and alongside
  the spray-hull film (`SprayWet`). Every new conditional uses typed literals (`SailingSim.Visual.BoatShaderLiterals`).

## Drips (`ASailboatPawn::UpdateDrips`)

48 drips at most, as `M_Spray` quads (smooth, grain 0) on an instanced engine plane. Each faces the camera and is
stretched along its fall. Half fall from the boom's underside to the cockpit sole (95 cm), and half fall off the sheer
on either side into the sea. Up to 10 a second start while the deck is wet, easing off under way (none past 3.5 m/s,
when the water runs aft instead). `-SailingNoDrips` turns them off.

At first no drip drew at all. The pool's hidden instances sat at z = -1e6, so the component's bounds were centred half
a kilometre under the lake. The hidden instances now wait at the boat with zero scale, and the component is movable at
an identity transform, like the bow wave's.

## Bow-wave lip (folded in from #206's Mac gate)

The white lip of the bow wave's curl (`BOW_WAVE_CODE`) read as one even line. A coarser noise (34 cm, running aft with
the water) now tears it into clumps and gaps: a clump widens the crest and moves it a little off the hull, and a gap
leaves only the clear sheet.

## Stills (J/22, Rain preset, 4 kn, Ultra, uncooked)

| Still | Shows |
| --- | --- |
| `rain-hatch.jpg` | Puddles on the cabin top and hatch: dark mirrors reflecting the hatch, rings and beads |
| `rain-cabin-top.jpg` | The same from the side deck |
| `rain-sole.jpg` | Rings on the wet cockpit sole |
| `rain-drips.jpg` | Drips falling off the sheer |
| `bow-lip.jpg` | The torn bow-wave lip (17 kn, High) |
