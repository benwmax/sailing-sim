# Hull at the waterline (realism audit 9, the hull's half)

`docs/realism-audit-1022`, item 9: the boats didn't sit in the water. There was no contact shading at the waterline and
no water in the hull's reflection, so the hulls looked pasted on, most of all at a distance. This pass is the hull side
only: `M_BoatSurface`, `M_BoatMast` and `M_BoatPacked` (`scripts/make_materials.py` `BOAT_CODE`, rebuilt with
`MATERIALS_ONLY=build_boat_library`) and the hero J/22's `M_J22HeroSurface` (`scripts/import_j22_hero.py`
`DETAIL_CODE`, `HERO_MATERIALS_ONLY=1`). The water side (the darkened water and the hull's reflection in it) is the Mac's.

- **Contact.** The topsides' last 25 cm over the water (`MPC_Boat.WaterZ`) darken by up to 45% toward the waterline.
  That band sees little sky, because the water and the hull's own flare shade it, and it takes the water's dark bounce.
  It applies only on the sides, not up-facing surfaces or metal.
- **The water in the hull.** Where the gelcoat's reflection points down at the water, the lobe was already roughened so
  Lumen skips its screen traces (`docs/lee-topside-patch`), and the hull showed no reflection of the water. The colour
  now carries the water's dark olive there: 18% plus a Fresnel share of up to 60%, most at a grazing look, within
  1.2 m of the water.

Frame cost (uncooked, 1920 x 1080, the marina view, total GPU per frame): High 14.34 ms before, 14.10 after; Ultra
18.72 ms before, 18.57 after. Within the noise.

Before and after: `g5-chase-before-after.jpg`, `g5-marina-before-after.jpg` (the audit's G5 scenes),
`hull-wl-before-after.jpg` (low along the J/22's side). The change is a soft band. Most of what still reads as "pasted
on" is the water side: no darkening or reflection of the hull in the near water.
