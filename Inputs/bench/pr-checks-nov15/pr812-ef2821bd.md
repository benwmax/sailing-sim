# PR #812 "Name on the hull for every boat" on the PC: head ef2821bd

**Build:**

- Head f2821bd (the PR moved on from 891d4af5). It contains main 91c8c80d, so it was used as is.
- Fresh worktree, git lfs pull, crew linked. MSVC build: **Succeeded, 0 errors**.
- The worktree was removed afterwards.

**Tests:**

- `SailingSim.Skin`: 10 of 10 passed.
- `SailingSim.Visual`: 106 of 106 passed (3 with the standing warnings).
- **0 failed.**

## Stills

Uncooked Ultra 1920x1080, -SailingHullName=Bluebonnet -SailingNoHud, lake, 8 kn, no demo (rgs.csv). Bean's Saved was held aside and restored.

**Catalina 22: legible.**

- **Framing:** port quarter, -SailingCamYaw=-45 -SailingCamPitch=-5 -SailingCamDist=9.
- **What shows:** "Bluebonnet" in dark serif letters on the port topside aft, just forward of the outboard (crop-catalina22-name.png, 1:1). Clear and readable; straight, not distorted.

**Bluebonnet: not seen in these stills.**

- **yaw -45, 45 m:** the camera sits high off her quarter. The view is mostly deck, with only a thin strip of dark blue topside showing, and no lettering visible (crop-bluebonnet-name.png).
- **yaw -160:** the sails fill the frame.
- **Not shown either way:** whether the name is drawn on her. A lower, closer stern view is needed, for example pitch around 0 to +5 at 25-30 m, or a capture-mode camera at the waterline.

**First try** (irst-try/): yaw -135 framed the C22's bow quarter, and at 24 m the camera sat inside the Bluebonnet's sails.
