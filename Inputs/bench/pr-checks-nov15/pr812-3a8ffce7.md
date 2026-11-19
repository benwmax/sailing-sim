# PR #812 (Name on the hull for every boat), head 3a8ffce7, on the PC

- **Head:** 3a8ffce7 contains main 91c8c80d: used as is.
- **Worktree:** a fresh one of its own, `D:\dev\ss-fix-wt\pr812`, at 3a8ffce7. Never pushed; removed afterwards.
- **Crew:** `Content/Crew/MetaHumans` was linked from the main checkout (541 files) for the Visual tests. Only the link was removed afterwards.

**Changed against main 91c8c80d:** `Content/Boats/Materials/M_BoatMast.uasset`, `Content/Boats/Materials/M_BoatPacked.uasset`, `Content/Boats/Materials/M_BoatSurface.uasset`, `Source/SailingSim/Private/BoatModelVisuals.cpp`, `Source/SailingSim/Private/BoatSkin.cpp`, `Source/SailingSim/Private/HullName.cpp`, `Source/SailingSim/Private/UI/SailCustomize.cpp`, `Source/SailingSim/Public/BoatSkin.h`, `Source/SailingSim/Public/HullName.h`, `Source/SailingSimTests/Private/SkinTests.cpp`, `docs/skins/README.md`, `scripts/make_materials.py`.

**MSVC build:** Succeeded. 0 errors, 0 warnings in our Source.

## `SailingSim.Skin`: 10 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Skin.Apply | Success |  |
| SailingSim.Skin.BadFiles | Success |  |
| SailingSim.Skin.BuiltIn | Success |  |
| SailingSim.Skin.Editor | Success |  |
| SailingSim.Skin.Ids | Success |  |
| SailingSim.Skin.Lettering | Success |  |
| SailingSim.Skin.RopeColourways | Success |  |
| SailingSim.Skin.RoundTrip | Success |  |
| SailingSim.Skin.SaveField | Success |  |
| SailingSim.Skin.Screen | Success |  |

The standing warnings are normal: the missing `S_*` sound samples, J22HeroMesh's tolerance notes, `GalvestonBay.detail` and Feedback.Jpeg's deliberate missing.png.

No package, bench or game launch.

`SailingSim.Skin.Lettering` now passes; it failed at 23312223. The 23312223 stills (`../pr812/pc-23312223/`) stay valid: this head changes only the test file.
