# PR #803 (Frigate wiring 12: her moving parts on the model (tiller, tiller ropes, wheel, cabin doors, capstans)), head dfa03cb0, on the PC

- **Head:** dfa03cb0 merged locally with main 5f5a4a7e (not pushed).
- **Worktree:** a fresh one of its own, `D:\dev\ss-fix-wt\pr803`, at 4265504f. Never pushed; removed afterwards.
- **Crew:** `Content/Crew/MetaHumans` was linked from the main checkout (541 files) for the Visual tests. Only the link was removed afterwards.

**Changed against main 5f5a4a7e:** `Source/SailingPhysics/Private/CommonwealthFramesData.inl`, `Source/SailingPhysics/Private/ShipFrames.cpp`, `Source/SailingPhysics/Public/ShipFrames.h`, `Source/SailingSim/Private/SailboatPawn.cpp`, `Source/SailingSim/Private/ShipModelVisuals.cpp`, `Source/SailingSim/Public/SailboatPawn.h`, `Source/SailingSimTests/Private/ShipFramesTests.cpp`, `docs/ship-frames/README.md`.

**Stopped:** build failed

**MSVC build:** Failed (OtherCompilationError). 1 errors, 0 warnings in our Source.

Verbatim:

```
D:\dev\ss-fix-wt\pr803\Source\SailingSimTests\Private\ShipFramesTests.cpp(224,28): error C7595: 'UE::Core::Private::FormatStringSan::TCheckedFormatStringPrivate<FString::FmtCharType,TCHAR *>::TCheckedFormatStringPrivate': call to immediate function is not a constant expression
```

## Why the build stops

MSVC rejects one line of the new test file. UE 5.8's compile-time format check (`FormatStringSan`) finds an argument with no matching specifier:

```
D:\dev\ss-fix-wt\pr803\Source\SailingSimTests\Private\ShipFramesTests.cpp(224,28): error C7595: 'UE::Core::Private::FormatStringSan::TCheckedFormatStringPrivate<FString::FmtCharType,TCHAR *>::TCheckedFormatStringPrivate': call to immediate function is not a constant expression
		TestTrue(FString::Printf(TEXT("the other way would be through the wall, forward"), UTF8_TO_TCHAR(Door->Name)), Wrong.X > Door->Origin.X + 0.6);
C:\Program Files\Epic Games\UE_5.8\Engine\Source\Runtime\Core\Public\String\FormatStringSanErrors.inl(40,1): note: failure was caused by call of undefined function or one not declared 'constexpr'
X(NotEnoughSpecifiers, "missing format specifier (Is there a missing '%' somewhere?)")
```

**The cause:** the format `"the other way would be through the wall, forward"` has no `%s`, but `Door->Name` is passed. The two lines above it use `TEXT("%s ...")`. The fix would be to add a `%s` to the text, or drop the argument; not done here, since I don't fix PR branches.

The tests (`SailingSim.ShipFrames`, `ShipRig`, `ShipWalk`, `Smoke`) did not run.

The standing warnings are normal: the missing `S_*` sound samples, J22HeroMesh's tolerance notes, `GalvestonBay.detail` and Feedback.Jpeg's deliberate missing.png.

No package, bench or game launch.
