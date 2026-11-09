# Crew life vest (part detail loop, Nov 9 2026)

The club's royal blue foam Type III vest that every sailor wears. It is not a kit part: `Tools/blender/build_vest.py`
tailors it over each MetaHuman sailor's polo, and `scripts/import_crew_clothes.py` skins it like the polo
(`SKM_<Role>_Vest`). The polos come from the private crew pack, so this pass ran on a faceless stand-in
(`Tools/boatkit/partloop/vest_standin.py`: a 1.78 m mannequin in a polo, 100 cm chest) and rendered with
`Tools/boatkit/partloop/render_vest.py`. Card: `Tools/boatkit/partloop/parts/crewvest.json`.

Reference: Bean's lesson photo of the vest worn in the J/22's cockpit (Oct 4 2026). It shows people, so it stays in the
project files and is never committed. The maker's logo and the school's letters on it are left off the model.

## What changed (round 2)

| | Before (G8 / round 11) | After |
|---|---|---|
| Straps | three bands at 20/38/55% of the polo's height, two vertical straps on each panel (read as a harness) | bands at 18/40/66% of the vest's height (top one at the armpits), one vertical strap on the wearer's right panel only |
| Buckles | 46 x 32 mm blocks, female beside the opening | 1.5 in side-release: female 50 x 46 x 11 mm on the wearer's left panel, male tongue across the opening; bevel faces now black (they took the shell's blue) |
| Tails | 15-20 cm, from the female's far end | out of the male side's adjuster at the opening: a short tab from the top strap, two long tails that run 4 cm past the hem |
| Foam | 22 mm everywhere, a 2 mm lip and a flat wall at every edge | 32 mm front, 22 mm back (blended round the sides), every edge a rolled quarter round (7 mm) |
| Edge colour | lighter blue piping on every edge | lighter blue lining turned over the armholes and shoulders, 2 cm onto the face; hem and front opening in the shell's blue |
| Neck and shoulders | shoulder straps about 4 cm wide, flat neck | armhole meets the neck at 0.92 W (was 0.80 W), straps about 7 cm; a shallow V at the front |
| Opening | 22 mm gap | 10 mm (closed, as zipped) |
| Triangles | 15,028 | 19,077 (budget 20k), 4 slots unchanged |

The armhole below the shoulder, where round 11 fixed the seated tear, is unchanged.

## Scorecard

| Round | Webbing | Buckle | Front foam | Strap heights | Features | Triangles | Blind review |
|---|---|---|---|---|---|---|---|
| Before | 38 mm | 46 x 32 mm | 26 mm | 20/38/55% | 3/9 | 15,028 | lost 3 of 3 to r2; all three said it reads as a harness or cargo vest |
| r2 | 38 mm | 74 x 46 mm (catalogue 76 x 44) | 33 mm (estimate 30) | 18/40/66% (photo 19/38/64) | 9/9 | 19,077 | won 3 of 3 against before (confidence 3, 3, 3 of 3) |
| r3 | | | | | | 19,299 | **lost**: won 1 of 3 against r2 (deeper V, taller vertical strap read as a hash mark); dropped |

Remaining differences the reviewers named: the photo's tails hang to the thigh (ours stop 4 cm past the hem, so a
seated sailor's lap doesn't take them through the legs); the foam in the photo is lumpier; the buckles' moulded detail.

## In the game (waits for the PC)

The PC rebuilds each role's vest from its polo and imports it:

    blender -b --factory-startup -P Tools/blender/build_vest.py -- <Role>_Polo.fbx <Role>_Vest.fbx <Role>_PoloOpen.fbx
    PIECES=Polo,Vest  (scripts/import_crew_clothes.py)

Then check Cockpit, RailHike and Helm at hike 0 and 1 from the side and the front: the armholes (unchanged, but the
shoulder straps are wider), the tails over a seated lap, and the polo under the V (its cut-away follows the V).
