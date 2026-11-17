# Bluebonnet deck at #764's f491dab6 (PC)

**Verdict at 1:1:**

- **Plank moiré bands, mid-deck to bow: gone.** Each laid plank has straight lengthwise grain, with thin dark seams and staggered butts. There are no wavy chevron bands, matching the Mac's f491dab6 crop.
- **Far-deck woven aliasing: gone.** Out toward the bow and the counter, the deck fades smoothly to plain teak. There is no woven or knit pattern.
- **No grey checker.** The game logs have no default-material lines or failed asset loads.

## Run

- **Worktree:** the kept `pr764` worktree at **f491dab6**: the plank-grain fix 834b7547, plus M_BoatSurface, M_BoatMast and M_BoatPacked rebuilt by the Mac.
- **LFS:** real files (T_MaskGrey 10,381 B; MI_Boat_LaidTeak 9,687 B).
- **No re-export or reimport:** the 48028ddc meshes stand. From 48028ddc to f491dab6, `Content/Boats/Bluebonnet` and `Tools` are unchanged. `scripts/make_materials.py` changed by 14 lines; that is the Mac's material builder, whose rebuilt assets are in the commit.
- **Editor build:** MSVC clean.
- **Tests:**
  - `SailingSim.Visual.JClassMaterials`: 1/1
  - `SailingSim.Visual.FleetMesh`: 1/1
  - `SailingSim.Visual.RigClearance`: pass, with only the standing missing `S_*` sound-sample warnings
- **Stills:** uncooked through `run-game.ps1 -Seconds 10 -ResX 1920 -ResY 1080 -NoDemo`, Ultra 1920x1080.
- **Saved:** Bean's Saved was held aside and restored both times (B57AA3AF).

**Stills on Bolivar Roads:** common args `-SailingBoat=Bluebonnet -SailingWorld=1 -SailingNoHud -SailingQuality=Ultra -SailingNoGpuSlices -ForceRes`.

| Still | Extra args | 1:1 crop |
| --- | --- | --- |
| `bluebonnet-helm.png` | `-SailingCamTarget=-10.85,1.1,2.6 -SailingCamDist=7 -SailingCamYaw=60 -SailingCamPitch=-15` | `bluebonnet-helm-deck-1to1.png` (x 1000-1720, y 760-1080) |
| `bluebonnet-deck.png` | `-SailingCamTarget=-8,0,2.4 -SailingCamDist=6 -SailingCamYaw=150 -SailingCamPitch=-35` | `bluebonnet-deck-1to1.png` (x 1080-1480, y 180-620) |
| `bluebonnet-afterdeck-top.png` | `-SailingCamTarget=-14,0,1.6 -SailingCamDist=4 -SailingCamYaw=0 -SailingCamPitch=-89`: 4 m up, looking straight down | `bluebonnet-afterdeck-top-1to1.png` (x 660-1260, y 240-840) |
| `bluebonnet-helmeye.png` | `-SailingCapture=HelmEye -SailingScreenPct=100` | `bluebonnet-helmeye-deck-1to1.png` (x 640-1600, y 440-1000) |

**The first helm-eye still doesn't match the Mac's view.** On Bolivar Roads the helm-eye camera sits over the varnished doghouse roof, so the roof fills the frame and the forward deck is a sliver.

**Helm-eye retake on the lake (default world), both tacks:** common args `-SailingBoat=Bluebonnet -SailingNoHud -SailingQuality=Ultra -SailingNoGpuSlices -ForceRes -SailingCapture=HelmEye -SailingScreenPct=100`.

| Still | Extra args | 1:1 crop |
| --- | --- | --- |
| `bluebonnet-helmeye-lake-stbd.png` | `-SailingTWA=45` | `bluebonnet-helmeye-lake-stbd-deck-1to1.png` (x 760-1720, y 560-1080) |
| `bluebonnet-helmeye-lake-port.png` | `-SailingTWA=-45` | `bluebonnet-helmeye-lake-port-deck-1to1.png` (same rectangle; it lands on the binnacle box, so only its left edge shows planks) |

The starboard-tack one matches the Mac's `jclass-764/mac-f491dab6/jclass-helm.png` (inputs ac8563da): the binnacle in front, looking forward along the starboard deck past the doghouse. It is the one to compare.

## What I saw at 1:1

- **Overhead after deck:**
  - Clean laid planking: a king plank down the middle, planks a few cm wide with dark seams, and staggered butts.
  - Plank ends nibbed into the covering boards along the sheer, and the skylight hatch planked too.
  - No moiré and no woven pattern.
- **Helm-eye, starboard tack, mid-deck forward:**
  - Each plank shows straight lengthwise grain; the earlier chevron and wavy bands are gone.
  - Toward the bow the seams converge and fade evenly, with no banding.
- **Helm and deck stills:** planks draw across the whole deck, by the wheel box and aft toward the counter. In the 1d28db92 stills these areas were the woven texture.
