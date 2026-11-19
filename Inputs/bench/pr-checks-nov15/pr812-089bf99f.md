# PR #812 at 089bf99f on the PC (name colour follows the hull)

**Build:**

- Head `089bf99f`, confirmed with `gh pr view 812`. It contains main `91c8c80d`, so it was used as is.
- Fresh worktree, `git lfs pull`, crew linked. MSVC build: **Succeeded, 0 errors**.
- The worktree was removed afterwards.

**Test:** `SailingSim.Skin` passed 10 of 10, 0 failed.

## Bluebonnet, low stern quarter

**Shots:** the same camera as the ef2821bd set: `-SailingHullName=Bluebonnet -SailingNoHud`, yaw -35 and -55, `-SailingCamPitch=-2 -SailingCamDist=22 "-SailingCamTarget=-15,-2,1"`, Ultra 1080p uncooked (`args.csv`). Bean's Saved was held aside and restored.

**Verdict: the name is now drawn, in pale letters, but only partly legible.**

- **At ef2821bd** the navy topside aft showed nothing.
- **Now** pale lettering shows on her port quarter aft (`crop-y-35.png` at 1:1; `zoom4x-y-35.png` at 4x nearest-neighbour).
- **The catch:** it sits very low on the topside, right at the waterline. In this view the water surface cuts across its lower part and its forward end, so only the last letters ("...nnet") read.
- **In `crop-y-55.png`** it's harder still to make out.
- **Suggestion:** the letters likely need to sit higher on her topside (or her freeboard aft taken into account) to read clearly.
