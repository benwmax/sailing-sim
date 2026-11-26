# PR #842 frigate polish at 617a930a: PC import, tests and stills (Nov 26 2026)

**Worktree:** `D:\dev\ss-fix-wt\pr842` at 617a930a ("Frigate polish: uneven growth rings, paint wear, cast iron, career
unlock"), one commit on main a3f81854.

**Steps:**
1. **MSVC build:** succeeded, 0 project warnings.
2. **Material:** `run-python.ps1 make_materials.py -Only build_boat_library`, exit 0. `M_BoatSurface` was rebuilt.
3. **Import:** `run-python.ps1 import_frigate.py -ScriptArgs D:\dev\frigate\out-pr840`, exit 0, 34 min. This is the
   existing 32ceee90 export; #842 has no export or mesh change.
   - It touched 1,084 Content files. These are **in the worktree only: not committed, not pushed.** They wait for Bean's
     OK.
4. **Tests:**
   - `SailingSim.Visual`: **109 tests, 0 failed** (3 with warnings: ChaseCamera.Pawn, J22HeroMesh, TreeSpecies).
   - `SailingSim.Career`: **15 of 15**.
   - `SailingSim.ShipWalk`: **8 of 8**.
5. **Package:** Development `Packaged\Windows-pr842-617a930a`, which carries the local reimport. It's complete; all 244
   ship parts load in every run, and none failed.

**Stills:** Ultra 4K, `-SailingBoat=Comm` on the Gulf (launch 2), at the 32ceee90 set's spots.
- `compare-*.webp` puts **32ceee90 on the left and #842 on the right** (1280 px each); `p842-*.webp` are #842 alone at
  1920.

| View | Pillars | Beam faces | Deck |
|---|---|---|---|
| Gun deck (Gun,-19,0,0) | **No longer fluted.** The deep regular vertical stripes are now uneven, softer growth rings. | The rippled grain on the beam above is now **straight and clean**. | — |
| Berth deck (Berth,2,0,90) | — | **The strong wavy ripples are gone.** The faces read as straight-grained timber. The end-grain block now shows rings instead of waves. | — |
| Orlop (Orlop,-12,0,180) | Smooth turned grain, as before. | — | **The ripple moire on the planking is gone.** It's fine, even plank figure now. |

**Paint and iron:**
- **At these distances** the gun carriages' red paint and the barrels read much as before. Paint wear and the cast skin
  are close-range effects.
- **The close-ups missed:**
  - `Gun,-19,±3.5` facing outboard put the camera at the hull wall, above the guns, with only a breech at the edge of
    one frame.
  - `-SailingWalkAt` has no pitch.
  - A retake from 2.2 m off the centreline, looking along the gun row at 45 and 135 degrees, is queued after the low-sun
    clips. Those stills will be added here.

Bean's Saved was held aside and restored for every run (7B5CA7BE).

## Gun close-ups (retake)

**The shots:** `Gun,-19,2.2,45`, `Gun,-19,2.2,135` and `Gun,-19,-2.2,-45`, 2.2 m off the centreline and looking along the
gun row.
- **Files:** `p842-gun-close-c/d/e.webp` are full frames at 1920; `*-crop.webp` are the 4K frame's middle at 1:1.
- **The nearest barrel is about 1.5 m off** in c and e.

**Cast iron:** yes.
- The barrels are dark iron with an uneven skin: rust-brown blotches and mottling along the barrel, stronger on the near
  one.
- At 1:1 the blotches are fairly soft-edged and fairly large, closer to staining than to fine casting pits. That's worth a
  look against the reference by eye.

**Paint wear:**
- The carriages' red reads darker and uneven, with worn, darker patches toward the edges and wheels.
- The gunport linings stay a clean red.
