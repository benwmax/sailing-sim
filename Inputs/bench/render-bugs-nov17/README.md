# Shore render bugs on main ecd4ed1c (PC, Ultra 1080p)

**Both bugs reproduce on ecd4ed1c.** (a) The white glow at the waterline is in all four bridge and wooded stills. (b) The moiré is on the near water at the bulkhead, and at the bridge bank too.

## How the stills were taken

- **Build:** the Development package `Packaged/Windows-ecd4ed1c`. The Shipping candidate drops camera args.
- **Runs:** warmed once, then each still once through ecd4ed1c's own `bench-win.ps1 -Seconds 8 -ResX 1920 -ResY 1080 -Quality Ultra -Shot <scene>`, with only the stop changed to the game's own PID.
- **Saved:** Bean's Saved was held aside and restored (profile B57AA3AF).
- **Format:** the stills and crops are lossless PNG. Crops are 1:1, cut from the stills with no scaling.
- **Placements:** the bridge, wooded and bulkhead rows at 5 m and 15 m from ecd4ed1c's `Tools/envloop/stations.csv`, the same as the Nov 16 and Nov 17 station sets. There are also two bulkhead views from the 5 m drone spot, pitched down to the near water.

**Common args:** `-SailingWorld=Lake -SailingLakeLevel=pool -SailingDate=2026-06-15 -SailingHour=15 -SailingWeather=AfternoonBreeze -SailingWind=8 -SailingKeepStart -SailingCaptureAbsolute -SailingNoHud -SailingNoGpuSlices -SailingCapture=Drone -SailingScreenPct=100`

| Still | Placement |
| --- | --- |
| `env-bulkhead-05m.png` | `-SailingStartAt=8691.8,2051.2,147.2 -SailingCamWorld=-29.4,19.0,2.0,147.2,-6.0` |
| `env-bulkhead-15m.png` | `-SailingStartAt=8700.2,2045.8,147.2 -SailingCamWorld=-29.4,19.0,2.0,147.2,-2.0` |
| `env-wooded-05m.png` | `-SailingStartAt=2473.9,-3680.0,291.3 -SailingCamWorld=12.7,-32.6,2.0,291.3,-6.0` |
| `env-wooded-15m.png` | `-SailingStartAt=2470.3,-3670.7,291.3 -SailingCamWorld=12.7,-32.6,2.0,291.3,-2.0` |
| `env-bridge-05m.png` | `-SailingStartAt=7200.8,786.9,327.2 -SailingCamWorld=29.4,-18.9,2.0,327.2,-6.0` |
| `env-bridge-15m.png` | `-SailingStartAt=7192.4,792.3,327.2 -SailingCamWorld=29.4,-18.9,2.0,327.2,-2.0` |
| `env-bulkhead-near-20.png` | `-SailingStartAt=8691.8,2051.2,147.2 -SailingCamWorld=-29.4,19.0,2.0,147.2,-20.0` |
| `env-bulkhead-near-35.png` | `-SailingStartAt=8691.8,2051.2,147.2 -SailingCamWorld=-29.4,19.0,2.0,147.2,-35.0` |

Full command lines are in `args.csv`.

## (a) White glow at the waterline: reproduces

**What it looks like:**

- A soft, featureless white-to-cream blob, about 150 to 300 px wide and 40 to 120 px tall, painted on the bank just above the waterline.
- Its lower edge stops sharply at the water.
- It doesn't follow the bank's shading or the sun. It is brightest on banks in shadow, under the trees or the bridge.
- It looks like light added on the terrain at the water's edge, not a reflection on the water.

**Where it shows:**

- `env-bridge-05m`: one large blob left of centre, at x 560-820, y 700-830 (crop `crops/crop-glow-bridge-05m.png`).
- `env-bridge-15m`: two blobs, at x 170-240 and x 760-880, both at about y 610-645, under the tree and the bush (`crops/crop-glow-bridge-15m.png`).
- `env-wooded-15m`: a bright strip at x 560-760, y 615-650, in the trees' shadow (`crops/crop-glow-wooded-15m.png`).
- `env-wooded-05m`: fainter, at x 600-760, y 780-835 (`crops/crop-glow-wooded-05m.png`).
- **Not on the bulkhead stills:** the concrete wall meets the water there, not a bank.

## (b) Moiré on the near water: reproduces

**What it looks like** (two patterns on the same near water):

1. **Zig-zag band:** a regular herringbone of light and dark chevrons, about 6 to 10 px a period. It runs parallel to the bulkhead in a band a few metres wide along the wall, and fades away from it.
   - `env-bulkhead-05m`: y 880-1080 (`crops/crop-moire-bulkhead-05m.png`).
   - `env-bulkhead-near-20`: y 600-760, strongest (`crops/crop-moire-bulkhead-near-20.png`).
   - `env-bulkhead-near-35`: y 140-420 (`crops/crop-moire-bulkhead-near-35.png`).
   - Bridge bank: the same chevrons along the waterline in `env-bridge-05m`, x 930-1500, y 820-870 (`crops/crop-moire-bridge-05m.png`).
2. **Blocky glints:** further from the wall, the sun glints on the ripples are drawn as hard stair-stepped blocks, 10 to 30 px, instead of smooth highlights. They show most looking down (`env-bulkhead-near-35`, lower left and right), as if a low-resolution normal or detail texture is magnified without filtering near the shore.

**How it varies:** both patterns are worst nearest the wall and the bank, and the open water further out looks normal. So they look tied to the shore band, which is shallow water and the shore depth or wave-damping maps, rather than to the water everywhere.
