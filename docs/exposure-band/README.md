# The histogram's dark side of the exposure band (measuring, no default change)

Re-audit gap 2: in the chase view (15:00, 111 deg from the sun) the PC's water read 0.019 against the Mac's 0.064. The
water isn't the cause. At an exposure locked at the incident meter's EV the PC's water is 0.059 (Ultra) and 0.063
(High), with the sky 0.23 to 0.25 (`pc/water-sky` findings). On auto exposure the histogram drives the exposure a stop
darker. The bright sky and cumulus fill the 10-90% histogram, so it settles on the band's dark end: the incident EV +1.

## The arg (this branch)

`-SailingExposureBand=<dark>,<bright>` scales the band either side of the incident meter. The histogram may take the
exposure `dark x Band` darker or `bright x Band` brighter, where Band is 1 in clear air and 0.3 under a storm deck as
before. The default 1,1 is the band as it was. This is not a lift: the incident meter's EV is unchanged, and only the
histogram's room to darken shrinks.

`-SailingDumpExposure` logs, once and 6 s in, every exposure input (`ExposureDump:` lines). The PC's are in
`dump-pc-ultra-chase.txt` and `dump-pc-high-chase.txt` for the Mac to diff. Ultra and High are identical apart from the
tier.

## Measured (PC, RTX 4090, 1920x1080, uncooked; linear luminance; pre-exposure from `ShowFlag.VisualizeHDR`)

Water is the frame's lower corners and sky its upper centre. "EV vs locked" is log2 of the locked run's pre-exposure
over this run's. The lock is `-SailingEV=-0.85`, the incident meter's EV here.

| View | Tier | Band | Water | Sky | Pre-exposure | EV vs locked | Clipped |
| --- | --- | --- | --- | --- | --- | --- | --- |
| chase 15:00 | Ultra | 1,1 (main) | 0.022 | 0.119 | 0.971 | 0.82 | 0% |
| | Ultra | 0.3,1 | 0.044 | 0.193 | 1.461 | 0.23 | 0% |
| | Ultra | 0.2,1 | 0.046 | 0.207 | 1.547 | 0.15 | 0% |
| | Ultra | locked | 0.059 | 0.226 | 1.720 | 0 | 0% |
| chase 15:00 | High | 1,1 (main) | 0.025 | 0.133 | 0.954 | 0.80 | 0% |
| | High | 0.3,1 | 0.050 | 0.210 | 1.420 | 0.23 | 0% |
| | High | 0.2,1 | 0.053 | 0.222 | 1.500 | 0.15 | 0% |
| | High | locked | 0.063 | 0.246 | 1.661 | 0 | 0% |
| helm eye 12:30 | Ultra | 1,1 | 0.30 | 0.40 | 0.809 | | 0.003% |
| | Ultra | 0.3,1 | 0.39 | 0.48 | 0.823 | | 0.002% |
| chase 18:36 (low sun) | Ultra | 1,1 | 0.131 | 0.294 | 12.44 | | 7.1% |
| | Ultra | 0.3,1 | 0.135 | 0.306 | 12.86 | | 7.2% |

- At noon and with the low sun the histogram isn't against the dark end, so the band changes nothing. The noon helm eye's
  water and sky differ between the two runs by the scene (the waves and the frame), not the exposure: the pre-exposure
  moved 0.02 EV. The low-sun chase clips 7% (the sun and its glow) with either band.
- 0.2 meets the aim (within 0.2 EV of the locked exposure). 0.3 is just outside it, at 0.23.
- The audit set (`docs/ultra-audit-1024`'s nine views) with 0.3,1: chase, helm eye and action cam are brighter (frame
  mean linear 0.098 to 0.158, 0.126 to 0.150 and 0.177 to 0.200). The other six are unchanged. No view clips (0.00%
  of pixels at 250+ in every one, before and after).

| Audit view (main left, 0.3,1 right) | |
| --- | --- |
| Chase | ![chase](chase.jpg) |
| Helm eye | ![helm eye](helmeye.jpg) |
| Action cam | ![action cam](actioncam.jpg) |

## Not changed

The default stays 1,1 until the Mac's VisualizeHDR read of the same view is in. If the Mac's histogram also pins at the
band's end there, the band is the cause on both machines; if not, the auto path differs between them, and the dumps
above are where to look.
