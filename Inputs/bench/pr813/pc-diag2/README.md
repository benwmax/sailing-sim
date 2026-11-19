# The faint diamond (about map N 245 E 13): shore detail, lighting-only and wireframe (main 91c8c80d, PC)

**Setup:**

- Uncooked Ultra 1080p in the kept main 91c8c80d worktree.
- View: the backyards top-down (`"-SailingCamWorld=128,40,60,0,-89"`, landing at map N 240.3 E 1.4, 60 m, `-SailingCaptureAbsolute`). Three new runs (`args.csv`).
- Bean's Saved was held aside and restored.

**Compare sheet:** `crops/compare-diamond-2x.png` crops x 1060-1300, y 350-530 and shows each at 2x nearest-neighbour. Panels: #813 79ee1a70, main lit, main `-SailingNoShoreDetail`, main `viewmode lightingonly`, main `viewmode wireframe`. The 1:1 crops are `crops/diamond-0..4.png`.

| Still | Diamond |
|---|---|
| #813 79ee1a70 (lit, its M_Ground) | **clearly there:** a lighter patch with diagonal edges meeting in a point |
| main 91c8c80d lit (main's M_Ground) | **faint at most:** a hint of the same lighter area, hard to call |
| main `-SailingNoShoreDetail` | **faint at most**, about as on main lit. Not obviously changed. |
| main `viewmode lightingonly` | **not there:** flat lighting over the spot, no edge |
| main `viewmode wireframe` | **mesh is regular:** a uniform grid of about 1 m cells, each split by one diagonal, all the same way. No lone vertex, no odd or larger triangle at the spot, and no edge set that follows the diamond's two diagonal directions. |

**Reading:**

- **Not lighting or shading:** the lighting-only pass shows nothing there.
- **Not a lone vertex:** the wireframe shows no lone-vertex hat or irregular triangulation under it.
- **Hard to judge on main:** the diamond is clear with #813's M_Ground but only faint with main's, so the main-worktree switches above can't judge it well.
- **Next:** the decisive test would be `-SailingNoShoreDetail` on #813's M_Ground (79ee1a70). Not run, since #813 is settled.
