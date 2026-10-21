# Vest armhole (clipping audit 2) and the PC's crew-clothes script

## The armhole

In the clipping audit the trimmer's life jacket showed through the polo at the armpit. In the winch-grip view it was a
sliver of the vest's side panel (its inside face) between the sleeve and the torso: the armhole's lower edge sat inside
the arm.

`Tools/blender/build_vest.py` now opens the armhole wider at the bottom:
- The side runs straight up to `ARMHOLE_FOOT` (9 cm) below the armpit line.
- It then tapers in to the torso's own half width (`W`) at the armpit, before the existing curve to the shoulder strap.

The vest's edge now sits on the torso where the arm comes down. The polo cut away under the vest
(`<Role>_PoloOpen`) follows the same outline, 7 cm inside it.

`armpit-oct14-main-after.jpg`, the trimmer at the jib winch (4 kn, Ultra):
- **Left:** the PC's old vests (Oct 14, from before round 11's armholes), with the jagged triangles from the audit.
- **Middle:** main's vest, with the side panel showing under the arm.
- **Right:** this change, with a clean edge under the sleeve.

`crew-views-after.jpg` shows all three crew in the winch-grip, hiking (15 kn) and seated views on Ultra.

The tailored clothes stay git-ignored with the MetaHumans. This PR carries the script change and these stills, and
each machine rebuilds its clothes with the script.

## scripts\windows\make-crew-clothes.ps1

This is the PC's twin of `scripts/make-crew-clothes.sh`. It runs the same steps in the same order:
1. Export the bodies with `export_crew_bodies.py`.
2. Tailor the clothes in Blender with `build_polo.py`, `build_shoes.py` and `build_vest.py`.
3. Import them with `import_crew_clothes.py`, filtered by `$env:PIECES`.
4. Tune the skin with `tune_crew_skin.py`.

The export runs in the full editor with `-ExecCmds="py <script>, QUIT_EDITOR"`. The script doesn't `os._exit` on
Windows: that leaves a zombie editor holding the asset locks, and without `QUIT_EDITOR` the editor sat idle after the
export. Run the import with `$env:SKIP_EXPORT=1` (or `-SkipExport`) to reuse the exported bodies.

Run once on the unchanged script, it rebuilt main's current vest, not the PC's Oct 14 one: the PC's MetaHuman pack
predated round 11 (Oct 16) and the strap tails (Oct 18). A full run also re-imports the polo and its cut-out, so the two
match.

## Conditions screen rows

This folds in a cosmetic follow-up to #220. The Sky row's six chips wrap at 1440x1080, and the left column then fell
out of step with the right (Air temp against Lake level).

The two columns' rows now line up in pairs: wind and time, gusts and date, sky and tide, air temp and lake level. Each
row is at least as tall as its partner (`SSailFrontEnd::BuildConditions`). `conditions-rows-aligned.jpg` shows
Conditions and ConditionsInGame at 1440x1080 and Conditions at 1920x1080.
