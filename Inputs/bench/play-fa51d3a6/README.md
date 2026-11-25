# Bean's play build: main fa51d3a6, Nov 25 2026 (NOT shared, NOT cleared)

**Sha:** main **fa51d3a6** ("Merge pull request #833"). Built in a fresh worktree, which I removed afterwards. I only
unlinked the crew link; all 541 crew files are still there.

**Build:** `D:\dev\ss-fix\Packaged\Shipping-fa51d3a6\Windows\SailingSim.exe`

**Zip:** `D:\dev\ss-fix\Packaged\ReadyAbout-fa51d3a6-Win64.zip`, 5,000,524,584 bytes (4.66 GB). Not shared and not
cleared: Bean shares zips himself. The builds Shipping-40226d1c and Shipping-76a41ea4 are kept.

## Checks

- **MSVC build:** Succeeded, 0 errors.
- **Tests:**

  | Suite | Result | Warnings |
  |---|---|---|
  | Skin | 10/10 | |
  | Visual | 108/108 | 4 |
  | Lake | 19/19 | 1 |
  | World | 8/8 | 7: missing git-ignored bakes, as usual |
  | Smoke | 36/36 | 1 |

- **Licence check:** passed. Every file under Content/, Audio/ and Inputs/ has a row (105 rows).
- **friday.ps1 -NoCheckout -Since 76a41ea4:** exit 0 in 9 min.
  - The Sentry DSN was staged quoted: yes. The cook had 0 errors and 0 warnings.
  - The gallery smoke rendered 398 thumbnails.
  - Ultra Lake bench at 1920x1080: 105.3 then **106.8 fps** (p99 13.4 ms, GPU 8.05 ms).
  - Symbols weren't uploaded (there's no Sentry auth token on the PC).
  - Config/ and Content/ were left clean.
- **Smoke from the Shipping exe:** title, then the Lake, sailing 60 s with the demo helm, Ultra 1080p.
  - **87 fps**, p99 17.3 ms, max 47.4 ms, GPU 8.0 ms.
  - The log has 0 errors and 0 warnings, and there were no crash folders.
  - Bean's Saved was held aside for it and restored (7B5CA7BE).

## Merged since 76a41ea4

12 merges, listed in `merged-since-76a41ea4.txt`:
- #833, #824, #829, #822, #825, #821, #819, #820, #818, #817 and #810;
- plus a merge of main into #825's branch.
