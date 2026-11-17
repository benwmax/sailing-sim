# PR #763 (J-Class ropes, without main), head c75df6d0, on the PC

- **Head:** c75df6d0 does NOT contain main 687f777c; main NOT merged (checked on its own, as asked).
- **Worktree:** a fresh one of its own, `D:\dev\ss-fix-wt\pr763`, at c75df6d0. Never pushed; removed afterwards.
- **Crew:** `Content/Crew/MetaHumans` was linked from the main checkout (541 files) for the Visual tests. Only the link was removed afterwards.

**Changed against main 687f777c:** `.github/workflows/sensitive-files.yml`, `CLAUDE.md`, `CREDITS.md`, `Content/Boats/Bluebonnet/SM_Bluebonnet_Boom.uasset`, `Content/Boats/Bluebonnet/SM_Bluebonnet_Hull.uasset`, `Content/Boats/Bluebonnet/SM_Bluebonnet_Mast.uasset`, `Content/Boats/Bluebonnet/SM_Bluebonnet_Rudder.uasset`, `Content/Boats/Bluebonnet/SM_Bluebonnet_Wheel.uasset`, `Content/Career/career.json`, `Content/Materials/M_WaterV4.uasset`, `Inputs/g3/boat-catalogue.json`, `Source/SailingPhysics/Private/AutoTrim.cpp`, `Source/SailingPhysics/Private/BluebonnetConfig.inl`, `Source/SailingPhysics/Private/BluebonnetHullData.inl`, `Source/SailingPhysics/Private/BoatModel.cpp`, `Source/SailingPhysics/Private/Fleet.cpp`, `Source/SailingPhysics/Private/HullClip.cpp`, `Source/SailingPhysics/Public/BoatModel.h`, `Source/SailingPhysics/Public/HullClip.h`, `Source/SailingSim/Private/BoatLiveryData.inl`, `Source/SailingSim/Private/BoatModelVisuals.cpp`, `Source/SailingSim/Private/ChaseCamera.cpp`, `Source/SailingSim/Private/CrewMotion.cpp`, `Source/SailingSim/Private/CrewPose.cpp`, `Source/SailingSim/Private/LakeData.cpp`, `Source/SailingSim/Private/PhotoSettings.cpp`, `Source/SailingSim/Private/SailCloth.cpp`, `Source/SailingSim/Private/SailSave.cpp`, `Source/SailingSim/Private/SailboatPawn.cpp`, `Source/SailingSim/Private/SailingBindings.cpp`, `Source/SailingSim/Private/SailingGameMode.cpp`, `Source/SailingSim/Private/SailingHUD.cpp`, `Source/SailingSim/Private/SailingSettings.cpp`, `Source/SailingSim/Private/UI/SailCatalog.cpp`, `Source/SailingSim/Private/UI/SailFrontEnd.cpp`, `Source/SailingSim/Private/UI/SailPhotoPanel.cpp`, `Source/SailingSim/Private/UI/SailUIStyle.cpp`, `Source/SailingSim/Private/WaterSurface.cpp`, `Source/SailingSim/Public/LakeData.h`, `Source/SailingSim/Public/PhotoSettings.h`, `Source/SailingSim/Public/SailCloth.h`, `Source/SailingSim/Public/SailboatPawn.h`, `Source/SailingSim/Public/UI/SailCatalog.h`, `Source/SailingSim/Public/UI/SailPhotoPanel.h`, `Source/SailingSimTests/Private/BluebonnetTests.cpp`, `Source/SailingSimTests/Private/CareerTests.cpp`, `Source/SailingSimTests/Private/FleetTests.cpp`, `Source/SailingSimTests/Private/HullClipTests.cpp`, `Source/SailingSimTests/Private/PhotoModeTests.cpp`, `Source/SailingSimTests/Private/SailClothTests.cpp`, `Source/SailingSimTests/Private/UITests.cpp`, `Source/SailingSimTests/Private/VisualTests.cpp`, `Tools/fleet/make_liveries.py`, `Tools/shapeloop/sections_c22_rebuild.json`, `Tools/shipkit/catalina22/build_c22.py`, `Tools/shipkit/catalina22/build_cabin_c22.py`, `Tools/shipkit/catalina22/build_hardware_c22.py`, `Tools/shipkit/catalina22/c22_check.py`, `Tools/shipkit/catalina22/cabin_c22.json`, `Tools/shipkit/catalina22/cabin_c22.py`, `Tools/shipkit/catalina22/export_game_c22.py`, `Tools/shipkit/catalina22/game_c22.json`, `Tools/shipkit/catalina22/render_cabin_c22.py`, `Tools/shipkit/catalina22/specs_c22.json`, `Tools/shipkit/frigate/build_stores.py`, `Tools/shipkit/frigate/stores.py`, `Tools/shipkit/frigate/stores_1797.json`, `Tools/shipkit/jclass/export_game.py`, `Tools/shipkit/jclass/game_bluebonnet.json`, `Tools/shipkit/jclass/loft.py`, `Tools/shipkit/jclass/physics.py`, `Tools/shipkit/jclass/running.py`, `Tools/shipkit/jclass/sails.py`, `Tools/shipkit/jclass/weathering.py`, `docs/boat-water-clip/README.md`, `docs/c22-12/README.md`, `docs/c22-8/README.md`, `docs/c22-8/cabin.jpg`, `docs/c22-8/views.jpg`, `docs/camera-views/README.md`, `docs/career/README.md`, `docs/env-loop/README.md`, `docs/envloop/buildkit/README.md`, `docs/envloop/docks/README.md`, `docs/envloop/yard/README.md`, `docs/first-launch/README.md`, `docs/jclass-12/README.md`, `docs/jclass-13/README.md`, `docs/jclass-14/README.md`, `docs/jclass-upwind/README.md`, `docs/licences/assets.csv`, `docs/shipkit-stores/README.md`, `docs/shipkit-stores/baseline/BreadBag.jpg`, `docs/shipkit-stores/baseline/ButtChocked.jpg`, `docs/shipkit-stores/baseline/Cartridge24.jpg`, `docs/shipkit-stores/baseline/CartridgeRackFilled.jpg`, `docs/shipkit-stores/baseline/FillingBench.jpg`, `docs/shipkit-stores/baseline/HammockLashed.jpg`, `docs/shipkit-stores/baseline/HammockSlung.jpg`, `docs/shipkit-stores/baseline/MagazineRackFilled.jpg`, `docs/shipkit-stores/baseline/MessTable.jpg`, `docs/shipkit-stores/baseline/PassingBox.jpg`, `docs/shipkit-stores/baseline/SeaChest.jpg`, `docs/shipkit-stores/baseline/ShotLocker24.jpg`, `docs/shipkit-stores/baseline/kit.jpg`, `docs/shore-loop/README.md`, `docs/slice/README.md`, `scripts/import_boats.py`, `scripts/make-boat-models.sh`, `scripts/make-c22-hero.sh`, `scripts/make_materials.py`, `scripts/windows/make-boat-models.ps1`, `scripts/windows/make-c22-hero.ps1`.

**MSVC build:** Succeeded. 0 errors, 0 warnings in our Source.

## `SailingSim.Visual.SpinnakerHead`: 1 passed, 0 failed, 0 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.SpinnakerHead | Success |  |

## `SailingSim.Visual.RigClearance`: 0 passed, 0 failed, 1 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.RigClearance | Success | LogUObjectGlobals: Failed to find object 'SoundBase /Game/Audio/Samples/S_Wind.S_Wind' |

## `SailingSim.Visual.SailShrouds`: 0 passed, 0 failed, 1 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.SailShrouds | Success | LogUObjectGlobals: Failed to find object 'SoundBase /Game/Audio/Samples/S_Wind.S_Wind' |

## `SailingSim.Visual.SheetClearance`: 0 passed, 0 failed, 1 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.SheetClearance | Success | LogUObjectGlobals: Failed to find object 'SoundBase /Game/Audio/Samples/S_Wind.S_Wind' |

## `SailingSim.Visual.TrimmerTailsJib`: 0 passed, 0 failed, 1 with warnings, 0 not run

| Test | State | Note |
| --- | --- | --- |
| SailingSim.Visual.TrimmerTailsJib | Success | LogUObjectGlobals: Failed to find object 'SoundBase /Game/Audio/Samples/S_Wind.S_Wind' |

**Main was NOT merged.** This is c75df6d0 on its own, as the J-Class thread asked. A local merge with main 687f777c conflicts in `docs/licences/assets.csv` and `scripts/import_boats.py` (see `pr763-c75df6d.md`), which is expected to clear once #758 lands. The "changed against main" list above is therefore the branch's whole difference from 687f777c, #758's files included. RigClearance passes now: the e40c514 failure (her jib sheet's tail 3.0 cm through the hull) is fixed by lifting the tail's rest 4 cm.

The standing warnings are normal: the missing `S_*` sound samples, J22HeroMesh's tolerance notes, `GalvestonBay.detail` and Feedback.Jpeg's deliberate missing.png.

No package, bench or game launch.
