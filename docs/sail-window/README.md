# The jib's window (Oct 26 2026)

The Ultra re-audit's gap 5 left the jib's window reading as a flat grey panel. A real window is clear film (PVC or
mylar) sewn into the sail. It shows the view behind it, a little hazed, and it reflects the sky by Fresnel: about 4.5%
square on (n about 1.54), up to a mirror at grazing angles. Its corners are cut round, and its edge runs about 2 cm under
the cloth, sewn there with two rows.

## What changed (`M_SailCloth`, `JIB_WINDOW` in `scripts/make_materials.py`)

- **Shape (every tier).** The cut is in metres with 40 mm round corners (square corners split in real sails). `winSdf`
  is the distance outside it. The 20 mm band outside the cut is the film under the cloth (`winEdge`).
- **High and Ultra (`Detail`).**
  - *Coverage.* The window stays a masked, dithered cut-out: the temporal AA blends it, and the sail stays opaque
    everywhere else. But a window pixel is drawn with the film's own chance, its Fresnel reflectance plus 4% haze,
    from the vertex normal and the view. It had been a fixed 12%.
  - *The drawn pixels.* They are the film: a mirror (metallic, roughness 0.04) for the Fresnel share and a milky
    diffuse for the haze. Lumen reflects the sky in them. They take the cloth's creases and the geometric wrinkles
    through the normal, so the sheen creases with the cloth. They don't glow with the cloth's transmitted light.
  - *The band.* It is a double layer: 6% darker, and against the light it passes 88% of the cloth's light (half, before).
    Two straight stitch rows at 6 and 15 mm show where a pixel is fine enough (within a couple of metres).
- **Medium** keeps the flat 12% veil and the dark ring.

## Stills (main left, this change right)

| File | View |
|---|---|
| `close-ultra.jpg`, `close-ultra-zoom.jpg`, `close-high-zoom.jpg` | 7 m from abeam |
| `ahead-ultra-zoom.jpg` | from ahead, through the window |
| `chase-ultra.jpg`, `chase-high.jpg` | 16 m chase |

Square on, the film reflects little, so the view through it is clearer than the old veil. Toward grazing it brightens
with the sky.

## Gate (boats scope, main 91328c11 + this)

Tests 226/226; pass.

- helm-eye 54.3 fps, slip 52.9 and crew 52.4 on High.
- beam8, beat15 and marina ran under 45 on the first pass (GPU 42-49 ms, likely the new material's pipelines compiling
  in the freshly cooked package). Benched again beside main: beam8 56.0 against 57.8, beat15 55.0 against 55.0, marina
  55.9 against 56.0 (passed as flapping).
