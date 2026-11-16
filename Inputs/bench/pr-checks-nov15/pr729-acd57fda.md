# PR #729 (paper grain), head acd57fda, on the PC

Head acd57fda merged locally with main f148592b (not pushed), built in a fresh worktree of its own (`D:\dev\ss-fix-wt\pr729`, at 7d0f9853;
never pushed; removed afterwards). Changed against main f148592b: `Source/SailingSim/Private/UI/SailFrontEnd.cpp`, `Source/SailingSim/Private/UI/SailUIStyle.cpp`, `Source/SailingSim/Private/UI/SailWidgets.cpp`, `Source/SailingSim/Public/UI/SailUIStyle.h`, `Source/SailingSim/Public/UI/SailWidgets.h`, `Source/SailingSimTests/Private/UITests.cpp`, `docs/ui-overhaul/README.md`.

**Stopped:** build failed

**MSVC build:** Failed (OtherCompilationError), **1 errors, 0 warnings in our Source**.

Verbatim:

```
D:\dev\ss-fix-wt\pr729\Source\SailingSim\Private\UI\SailUIStyle.cpp(313,17): error C4459: declaration of 'Ink' hides global declaration
```

No package, bench or game launch.
