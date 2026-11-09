# Hero J/22 ageing (Nov 9 2026)

The PC's in-game ageing stills (PR #568, `docs/texture-loop/ingame/age*-{helm,close,waterline,teak,tiller}-*.jpg`)
showed `-SailingBoatAge=0`, `5,0.5` and `15,0` barely changing the player's J/22. Three causes:

1. **The bake carried the club boat's own wear.** `Inputs/j22-hero` bakes the TX 7295 club style: rain streaks, a
   6.5 cm scum line, bottom slime, grimy non-skid with stains, chipped edges, repairs and silvered teak are in
   `T_J22H_{Hull,DeckMould,Rudder,Teak}_D`. The shader can only add wear on top, so Age 0 still looked like a club boat.
2. **The hero's shader had the old, light wear.** `M_J22HeroSurface` (DETAIL_CODE in `scripts/import_j22_hero.py`)
   had only an even chalk film, a 30% darkening of the non-skid and a 25% darkening of the teak. The texture loop's
   lines (blotchy chalk, grime, non-skid blotches, waterline scum and slime, dock rash) were only in `M_BoatSurface`.
3. **Age only reached the hull part.** `BuildModelVisuals` set Age and Care on `SM_J22H_Hull`'s slots; the rudder
   (blade and tiller), the boom and the mast never aged.

## The fix

- **Clean bake.** `build_j22_hero.py --clean-bake` bakes the hull, deck mould, rudder and teak from
  `j22_style.clean_bake(style)`: the same boat with no streaks, chalk, chips, fender marks, repairs, scum, slime,
  grime, stains, and fresh bare teak. Ropes, sails, flat hardware and the cabin keep the style's wear. Renders and
  stills that want the worn look build without the flag.
- **The fleet's lines on the hero.** DETAIL_CODE now carries M_BoatSurface's gelcoat chalk with its 40 cm blotches,
  yellowing, deck grime, non-skid blotches and scuffs, the lake waterline (scum line, slime, bottom film, from
  `Tools/texloop/waterline`), dock rash, and silvering teak, all from the shared timeK and dirtK
  (`Tools/texloop/wear.py`; `test_wear.py` checks them). It takes the part's local position (new `LP` pin) so the
  wear stays on the boat. Two new scalars: `Waterline` (1 on the Hull and Rudder instances: the lake's line) and
  `Exterior` (0 on the Interior instance: the cabin keeps its baked dirt and takes no weather).
- **Unset Age in play is the club boat.** With no `-SailingBoatAge` (the player's boat in play) the hero weathers as
  the texture loop's L2 club boat (6 years, Care 0.5), so the clean bake still looks like the school boat she was.
  The livery's `Wear` no longer drives the hero's textured groups.
- **Every part ages for stills.** `-SailingBoatAge` now also reaches the rudder blades, boom and mast (dev argument
  only; nothing changes in play).

Not ported: rust weeps (the hero has no bolt-line data for them yet) and salt-water stains (lake only).

## Before merge

- The PC rebuilds the hero with `--clean-bake` (with the hero rebuild already queued) and commits the new
  `T_J22H_*` maps, fbx and `materials.json`, then runs `import_j22_hero.py`.
- The Mac merges main, runs `HERO_MATERIALS_ONLY=1 import_j22_hero.py`, commits the rebuilt `/Game/Boats/J22Hero`
  assets (standing rule for material scripts), and passes the boats gate.
- New ageing stills at Age 0, 5,0.5 and 15,0 (helm, close, waterline, teak, tiller) against #568's.

Without the clean maps the new shader would add its L2 wear on top of the club bake in play, so the rebake has to land
on this branch before it merges.
