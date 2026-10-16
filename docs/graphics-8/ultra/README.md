# Ultra showcase (graphics-8/ultra)

Ultra only (`ESailingQuality::Ultra`), so the Mac's Medium and High gates don't move. High's numbers are checked
unchanged with `gate.ps1`. The target is 60 fps at 1440p on the RTX 4090; 4K is reported too.

## Pieces

- **Higher-resolution drawn ocean:** `FOcean` cascades at 128 or 256, or a third cascade, and `FWaveDetail` at a
  higher resolution. Drawing only: the physics keeps evaluating at 64, so the boat's motion, PolarGate and the Hs
  tests don't change.
- **Smoke and exhaust (Niagara):** a black diesel plume from the ship-channel traffic and a lighter haze from
  outboards, both blown by `FWindField` at the stack.
- **Bow spray and spindrift on GPU particles (Niagara):** for the player's boat and the AI boats. This replaces High's
  CPU droplets with a higher particle count.
- **Wake foam that lingers.**

## Status

Not started; it follows the cinematic look.
