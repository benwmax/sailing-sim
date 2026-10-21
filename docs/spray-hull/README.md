# Spray hull: the topsides' wet band and the bow wave's curl (Oct 21 2026)

These are the two items `docs/spray/README.md` (#197) left for the PC: the topsides weren't marked by the water that
runs up them, and the bow wave was spray only, with no water standing off the bow.

## The wet band

**What drives it.** `UpdateBoatWetness` (`BoatModelVisuals.cpp`) now runs the same two tests `AWaterSurface::UpdateSpray`
uses to throw spray, on the player's bow: the bow wave past 2 m/s, and a slam when the water closes on the bow faster than
0.45 m/s. They build a `SprayWetness` value, from 0 to 1, that dries off over about 40 s. It goes to `MPC_Boat.SprayWet`
and raises the splash band by up to 25 cm. `WaterSurface.cpp` is untouched.

**What it looks like.** `M_BoatSurface` (`BOAT_CODE`) and the hero J/22's `M_J22HeroSurface` draw the topsides below the
ragged wet line as wet:
- **Film:** a water film a fifth darker. Gelcoat takes up no water, but the film absorbs light and reflects the dark
  water. It is glossy, through the existing wet gloss and the water film's clear-coat lobe.
- **Beads:** water beads, about 9 mm apart, in the band's top 8 cm. On `M_BoatSurface` each bead is a small dome with its
  own glint; on the hero each is a sharp spot of gloss.
- **Drips:** they run 3 to 17 cm down from the line.
- **Spatter:** after spray and slams, beads spatter up the side above the line, up to 30 to 70 cm.

## The bow wave's curl

`ASailboatPawn::UpdateBowWave` builds a sheet of water standing off each side of the bow, every frame, in world space on
the waves' own surface. The boat heels and pitches through it.

**Shape.**
- **Start:** past 1.5 m/s, fading in over the next 1.5 m/s. It starts where the bow meets the water: 0.8 of `BowX`, since
  a raked stem overhangs the waterline.
- **Height:** up to a quarter of the speed head (V²/2g, 15 cm at 6 kn), scaled with the hull, highest a little aft of the
  stem. It falls away aft and out along the Kelvin wedge.
- **Lip:** a shoulder that thickens and curls outward at speed.
- **Mesh:** 10 stations along the bow by 6 across, per side, with normals from the grid.

**Material.** `M_BowWave` is lit translucent water in the lake's dark green. It thins to nothing where it meets the sea,
and a foam crest along the shoulder is broken by bubbly noise that runs aft.

**Where it's drawn.** Not on Low. On the player's boat, and on AI boats within 120 m of the camera.

**Compare.** `-SailingNoBowWave` turns it off.

### The fix after the Mac gate

The Mac's High stills of the J/22 beating at 17 kn showed the curl as a hard-edged, opaque, olive half-dome lying on the
lee topsides well aft of the stem. The cause was the root. Each station was rooted at the deck's half-beam with the boat
upright, but heeled, the lee waterline lies well outboard of that, so the sheet was drawn over her side.

**Root.** Each station now solves for the point where her side meets the sea as she heels and pitches. Along the side,
world height is linear in body z, so one step finds the sea surface. The sheet starts 4 cm outboard of that point and runs
out horizontally.

**Length.** It is shorter, 0.8 to 0.45 of `BowX`, so it stays at the stem.

**Fades.** It fades in from the stem and out aft, at its root, and where it meets the sea.

**Material.** `M_BowWave` is now a thin film of moving water: mostly the sky's reflection by Fresnel, clear from above and
mirror-like at grazing angles, with only a faint dark-water tint and the foam crest.

`bow-wave-fix-high.jpg` shows the PC High run-game repro (J/22, 17 kn, 42 degrees TWA): be174a8b on the left, the fix on
the right. There are three views: from the lee at 8 m, a lee bow close-up, and a windward bow close-up. The dark patch on
the lee topsides is gone, and the curl sits at the stem, blending into the spray and the sea.

## Stills (Ultra, uncooked; main's materials and `-SailingNoBowWave` on the left, this branch on the right)

`bow-wave-wet-band.jpg` holds three pairs:
- the J/22 at 16 kn wind, beam reach, from forward;
- the same from abeam;
- the Gulf in a 1.5 m swell, after slams, the topsides cropped.

The wet band shows as a darker, ragged band along the waterline. The bow wave is a low mound of water off the bow, where
before there was only spray.

## Cost (packaged Development, RTX 4090, 1920x1080, the J/22 at speed from abeam, two runs each)

| Tier | On (fps) | Off (fps) | GPU (ms) | boat_visuals (ms) |
| --- | --- | --- | --- | --- |
| Ultra | 72.1 / 74.3 | 71.7 / 72.6 | 7.21–7.36 vs 7.23 | 0.84–0.88 vs 0.76–0.79 |
| Medium | 88.0 / 81.2 | 82.3 / 82.2 | 3.63–3.79 vs 3.66 | 1.01–1.09 vs 0.97–0.98 |

Building the sheet costs about 0.1 ms of game thread per boat drawing it. The GPU difference is inside noise. The wet band
is a few ALU operations in materials that already run.

## Test

`SailingSim.Visual.SprayHull` checks that `MPC_Boat` has `SprayWet` and that `M_BowWave` exists and is translucent.
