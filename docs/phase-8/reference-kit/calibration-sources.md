# Calibration Data Sources & Methodology References — Realism Pass

Scope: UE5 sailing sim set on Lake Ray Hubbard (Rush Creek Yacht Club, Heath TX), Galveston Bay (Clear Lake/Kemah to Bolivar Roads) and the Gulf off Galveston.
Compiled 2026-10-12. Every URL below was fetched or returned by search during compilation unless marked **[unverified]**. Numbers marked *(derived)* are my own calculations from cited inputs.

Reference point used for distances: USGS site "Lk Ray Hubbard nr Rush Ck Yacht Club" 32.8234 N, -96.4976 W (Ray Hubbard); Kemah approx 29.54 N, -95.02 W (Galveston Bay).

---

## 1. Lake Ray Hubbard — wind, weather, water level, radar

### 1.1 Surface stations (ASOS/AWOS), distance from RCYC *(derived great-circle)*

| ID | Name | Lat, Lon | Dist / bearing from RCYC | IEM archive start | Notes |
|---|---|---|---|---|---|
| F46 | Rockwall (Ralph M. Hall Muni) | 32.9306, -96.4355 | 8.2 mi, 026° | 2012-08-27 | AWOS; closest airport on the lake's NE side. Nearest exposure analogue for N/NE winds. |
| HQZ | Mesquite (Metro) | 32.7470, -96.5304 | 5.6 mi, 200° | 2003-07-09 | Closest station of all; good for S flow (dominant summer direction). |
| TRL | Terrell Muni | 32.71, -96.27 | 15.4 mi, 121° | 1997-05-31 | Rural/open exposure; useful for SE flow. |
| DAL | Dallas Love Field | 32.8471, -96.8518 | 20.6 mi, 275° | 1930-01-01 | NWS ASOS — has 1-minute data. |
| ADS | Dallas/Addison | 32.9686, -96.8364 | 22.1 mi, 297° | 1974-01-31 | |
| GVT | Greenville/Majors | 33.0678, -96.0653 | 30.2 mi, 056° | 1942-09-11 | |
| DFW | Dallas/Fort Worth Intl | 32.8968, -97.038 | 31.8 mi, 279° | 1953-05-01 | NWS ASOS; long climatology, 1-min data. |

- No ASOS was found at Garland. Station pages: `https://mesonet.agron.iastate.edu/sites/site.php?station=HQZ&network=TX_ASOS` (swap the ID).
- Sources: IEM network table https://mesonet.agron.iastate.edu/sites/networks.php?network=TX_ASOS ; F46 on SkyVector https://skyvector.com/airport/F46/Ralph-M-Hall-Rockwall-Municipal-Airport

**How to use:** HQZ and F46 bracket the lake (S and NE). Pull several years of 5-minute and hourly wind (speed, gust, direction). Build per-month wind roses, Weibull fits of wind speed, and gust-factor distributions. These become the sim's weather generator: random draws per season and time of day, plus a gust/lull model with realistic gust factor and duration. Airport anemometers sit at 10 m over grass, so apply an overwater roughness correction. Over-water winds are typically ~10–20 % stronger. Treat that range as a tunable parameter and check it against your own on-lake logging (§5.2).

### 1.2 Download tools for historical surface wind

| Name | URL | What it gives | How to use |
|---|---|---|---|
| IEM ASOS/AWOS download | https://mesonet.agron.iastate.edu/request/download.phtml?network=TX_ASOS | METAR-derived routine, special, and **MADIS HFMETAR 5-minute** obs. CSV/TSV output with selectable variables (sknt, drct, gust, peak wind, tmpf, dwpf, mslp, vsby, skyc/skyl, wxcodes, raw METAR) and timezone. Up to 1,000 station-years per request. | Main bulk source. Request F46, HQZ, TRL, DAL, ADS with the America/Chicago timezone. Also scriptable (see IEM's backend docs). |
| IEM ASOS 1-minute | https://mesonet.agron.iastate.edu/request/asos/1min.phtml | NCEI 1-minute ASOS archive, 2000–present (to ~2 days ago): wind speed/dir, **5-second gust** speed/dir, temp, dewpoint, pressure, precip. NWS ASOS sites only (DAL, DFW, likely ADS/TRL), not AWOS like F46. | Build gust spectra and gust-onset time scales for the gust model (puff duration, ramp rate, direction shifts in puffs). |
| NCEI Local Climatological Data v2 | https://ncei.noaa.gov/products/land-based-station/local-climatological-data · map https://www.ncei.noaa.gov/maps/lcd/ · bulk https://www.ncei.noaa.gov/oa/local-climatological-data/index.html#v2/access/ · docs https://www.ncei.noaa.gov/oa/local-climatological-data/v2/doc/lcdv2_DOCUMENTATION.pdf · station list https://www.ncei.noaa.gov/oa/local-climatological-data/v2/doc/lcdv2-station-list.txt | Official hourly, daily, and monthly summaries in CSV (SI units) or certified PDF. Derived from GHCNh/GHCNd. | Climatology cross-check, e.g. monthly mean wind and peak gust by month for the season system. |
| Synoptic Data Viewer (MesoWest successor) | https://viewer.synopticdata.com/ · API docs https://docs.synopticdata.com/services/time-series | Aggregates all public networks, including CWOP/personal stations, TxDOT, and possibly lakeside stations. Time-series API needs a token (paid/commercial tiers; I did not confirm a free tier). | Look for any **lakeshore or on-lake station** around Rockwall/Heath/Rowlett, which would beat airports for overwater wind. |

### 1.3 Lake level / lake stations

| Name | URL | What it gives | How to use |
|---|---|---|---|
| **USGS 08061550 Lk Ray Hubbard nr Forney, TX** | https://nwis.waterdata.usgs.gov/monitoring-location/08061550 · graphs https://waterdata.usgs.gov/monitoring-location/USGS-08061550/all-graphs | Reservoir water-surface elevation gauge (the TWDB data source). | Drive the sim's lake level from it, which moves shoreline, exposed riprap, and dock heights. |
| TWDB Water Data for Texas — Ray Hubbard | https://waterdatafortexas.org/reservoirs/individual/ray-hubbard · CSV: `.../ray-hubbard.csv` (POR), `ray-hubbard-1year.csv`, `ray-hubbard-30day.csv` | Conservation pool **435.50 ft NGVD29**. Conservation capacity **439,559 ac-ft**. Surface area **~19,489 ac** (at fetch time). 96.4 % full as of 2026-07-30. | Mean depth ≈ 439,559 / 19,489 ≈ **22.6 ft (6.9 m)** *(derived)*. Use it as h in the shallow-water wave formulas (§4.1). Typical level range sets the water-plane height. |
| USGS lake water-quality sites (incl. one **at RCYC**) | Rush Ck YC site 324924096295100: https://nwis.waterdata.usgs.gov/monitoring-location/324924096295100 · RHP site 324857096304801 · Release Gates 324807096294201 · Terry Park 325023096302500 · PS site 324929096305601 | Discrete sampling sites, established 2010. Instrument flags show no continuous met sensors. | Possible source of water-clarity data (Secchi/turbidity, if sampled) for the water shader's absorption and scattering. No wind data here. |
| Outflow USGS 08061551 E Fk Trinity Rv blw Lk Ray Hubbard | https://nwis.waterdata.usgs.gov/monitoring-location/08061551 | Dam release flow. | Optional: currents near the dam (negligible elsewhere). |
| No NDBC/buoy on Ray Hubbard was found. | | | |

### 1.4 Storms and radar (NWS Fort Worth, FWD)

| Name | URL | What it gives | How to use |
|---|---|---|---|
| NWS Fort Worth office | https://weather.gov/fwd/office | Event summaries (e.g. https://www.weather.gov/fwd/torradar041307). | Pick reference storm days for squall/outflow-boundary scenarios. |
| NEXRAD **KFWS** level II | Info: https://radar2pub.ncep.noaa.gov/site/kfws.html · AWS Open Data https://registry.opendata.aws/noaa-nexrad/ → bucket `s3://unidata-nexrad-level2` (archive), `s3://unidata-nexrad-level2-chunks` (real-time). Anonymous: `aws s3 ls --no-sign-request s3://unidata-nexrad-level2/` | Reflectivity and radial velocity volume scans. | Replay real squall-line passages: timing of outflow wind shift, then rain, then the clearing sky. Gives a timeline for scripting storm fronts. Velocity data gives gust-front wind magnitudes. (Galveston equivalent: **KHGX** League City **[ID from memory, verify]**.) |
| NCEI Storm Events Database | https://www.ncdc.noaa.gov/stormevents/ **[unverified URL — search didn't return it directly]** | County-level thunderstorm-wind and hail reports with measured or estimated gusts. | Frequency and severity of severe wind events in Rockwall/Dallas counties for the "storm" weather tier. |

---

## 2. Galveston Bay & Gulf — NOAA CO-OPS / PORTS / NDBC / TABS

### 2.1 CO-OPS water-level + met stations (Houston/Galveston PORTS)
Metadata verified via the CO-OPS MDAPI (`https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{id}.json?expand=sensors`). All four list sensors: **Wind, Air Temp, Water Temp, Barometric Pressure, Microwave WL, Tsunami (1-min) WL**. Eagle Point and Morgans Point also have Conductivity.

| ID | Name | Lat, Lon | Dist from Kemah *(derived)* | Tidal datums (ft, STND) |
|---|---|---|---|---|
| **8771013** | Eagle Point, Galveston Bay | 29.4813, -94.9173 | 7.4 mi | MHHW 5.39, MSL 4.88, MLLW 4.27 → **GT 1.12 ft**, MN 1.02 ft |
| **8770613** | Morgans Point, Barbours Cut | 29.6817, -94.985 | 10.0 mi | |
| **8771450** | Galveston Pier 21 | 29.31, -94.7933 | 20.9 mi | MHHW 5.79, MSL 5.21, MLLW 4.38 → **GT 1.41 ft**, MN 1.02 ft |
| **8771341** | Galveston Bay Entrance, North Jetty | 29.3575, -94.7247 | 21.8 mi | PORTS page: https://tidesandcurrents.noaa.gov/ports/ports.html?id=8771341 |

- Data API (CSV/JSON, 6-min water level and 6-min met, up to 31 days per call for 6-min data): `https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?station=8771013&product=wind&begin_date=20250101&end_date=20250131&units=english&time_zone=lst_ldt&format=csv` (products: `water_level`, `predictions`, `wind`, `air_temperature`, `water_temperature`, `air_pressure`, `currents`) **[URL pattern from CO-OPS API docs, not fetched]**.
- Datums: `https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/8771450/datums.json`
- Station home (JS page): https://tidesandcurrents.noaa.gov/stationhome.html?id=8771013 ; physical oceanography https://tidesandcurrents.noaa.gov/physocean.html?id=8771450
- CO-OPS current stations (from MDAPI): **g06010** Galveston Bay Entr Channel LB 11 · **g08010** Fred Hartman Br., HSC · **g09010** Galveston Channel W end · **g11010** Galveston Channel E end · g10010 610 Bridge HSC.

**How to use:** The tide is small: mean range ~1 ft, great diurnal range 1.1–1.4 ft, mixed/diurnal. Wind setup and setdown often exceed the astronomical tide. Drive the sim water level from predictions plus a wind-setup term, and validate against observed minus predicted. Use g06010 for ebb/flood strength at Bolivar Roads, the strongest currents in the play area, and apply them in the entrance channel. Eagle Point wind is the best open-bay overwater anemometer for the Clear Lake to mid-bay area.

### 2.2 TCOON
Texas Coastal Ocean Observation Network (TAMU-CC Conrad Blucher Institute): https://lighthouse.tamucc.edu/ (e.g. station 503 = Morgans Point, now **INACTIVE**; TCOON O&M unfunded since 31 Aug 2014). Overview PDF: https://www.cbi.tamucc.edu/wp-content/uploads/TCOON-Overview-2010-FINAL.pdf. Use for older historical records only. Current data lives in the CO-OPS stations above.

### 2.3 Offshore buoys (waves, spectra)

| ID | Name / location | Depth | Data | URL |
|---|---|---|---|---|
| **NDBC 42035** | Galveston, 22 NM E of Galveston; 29.235 N, 94.410 W (≈42 mi from Kemah) | 15.5 m | Active. Met (wind 10 m/20 m adjusted, gust, pressure, air/water temp) + **WVHT, DPD, APD, MWD**. Historical: stdmet 1993–2025; **spectral density (swden) 1996–2025**; alpha1/alpha2/r1/r2 directional 1998–2025 (no 2022); continuous winds 2005–2017. | https://www.ndbc.noaa.gov/station_page.php?station=42035 · history https://www.ndbc.noaa.gov/station_history.php?station=42035 |
| NDBC 42019 | Freeport, 60 NM S; 27.908 N, 95.343 W | 85 m | Deep-water reference. **Went adrift 2025-02-26, recovered 2026-05-04**, so expect a data gap. | https://www.ndbc.noaa.gov/station_page.php?station=42019 |
| TABS buoys (TAMU GERG / Texas GLO) | B, D, F, J, K, R, W, X | — | Currents, met, some waves. THREDDS archive. | https://tabs.gerg.tamu.edu/ · status https://tabs.gerg.tamu.edu/tglo/?mapidx=4 · THREDDS https://thredds.gerg.tamu.edu/thredds/ · Buoy B https://tabs.gerg.tamu.edu/tglo/stations.php?buoy=B&type=ven · TABS paper https://tabs.gerg.tamu.edu/tglo/TABS_Descriptive_Paper.pdf |

- NDBC historical file pattern: `https://www.ndbc.noaa.gov/download_data.php?filename=42035w2024.txt.gz&dir=data/historical/swden/`. Type letters: `h` stdmet, `w` spectral density, `d` alpha1, `i` alpha2, `j` r1, `k` r2, `c` continuous wind, `s` supplemental. Real-time 45-day files: `https://www.ndbc.noaa.gov/data/realtime2/42035.data_spec` and `.swdir/.swdir2/.swr1/.swr2/.spec/.txt` **[realtime2 pattern from memory; the measdes page confirms the 45-day realtime files exist]**.
- Definitions: https://www.ndbc.noaa.gov/faq/measdes.shtml. WVHT = mean of highest 1/3 over a 20-min record. Spectral density in m²/Hz, bins ~0.03–0.40 Hz. Buoy WSPD = **8-min average**, GST = 5- or 8-s peak. r1/r2 in historical files are ×100.
- Web data guide: https://www.ndbc.noaa.gov/docs/ndbc_web_data_guide.pdf · THREDDS https://dods.ndbc.noaa.gov/

**How to use:** Fit JONSWAP parameters (Hs, Tp, γ, spreading from r1/r2) to 42035 spectra binned by wind speed and direction. Do it separately for wind-sea (onshore SE flow) and swell. Drive the Gulf ocean FFT/spectrum with these fits, which beats a generic Pierson–Moskowitz. Then check that sim Hs and Tp at given winds fall within the 42035 distribution. For inside the bay, use the shallow-water formulas (§4.1). Bay mean depth is ~6 ft (1.8–2 m), max undredged ~10 ft. The bay is ~30 mi × 17 mi, ~600 sq mi (https://en.wikipedia.org/wiki/Galveston_Bay). Expect short, steep chop with Tp ≈ 2–3.5 s.

### 2.4 Galveston-area airports (IEM)
GLS Galveston/Scholes 29.2653, -94.8604 (21 mi from Kemah, since 1939). **T41 La Porte** 29.6692, -95.0641 (9.3 mi, since 2019). EFD Houston/Ellington 29.6073, -95.1588 (9.5 mi, since 1941). HOU Hobby 29.6375, -95.2825 (17 mi). LBX Angleton 29.1086, -95.4621.

---

## 3. Boat polars, ratings and specs

### 3.1 Summary table

| Boat | Key specs (source) | US Portsmouth D-PN (US Sailing 2017 precalc: DPN / DPN1 / DPN2 / DPN3 / DPN4 by wind band) | PHRF (typical) |
|---|---|---|---|
| **J/22** | LOA 22.5 ft (6.86 m), LWL 19.0 ft, beam 8.0 ft, **displ 1,790 lb (812 kg)**, ballast 700 lb, draft 3.8 ft, SA 226.6 sq ft (Wikipedia). ORC OD cert: displ **857 kg** (sailing trim), main 13.76 m² measured/14.11 rated, jib 9.49 m², spinnaker 30.94 m², **RM 15.9 kg·m (ORC RM, per degree)**, stability index 96.2, GPH 736.1. Crew limit 275 kg (605 lb). | Not listed in 2017 precalc. | **180–183** (Wikipedia) |
| **Sunfish** | LOA 13'9" (4.19 m), beam 4'1", hull 120 lb (54 kg), sail 75 sq ft (7.0 m²) lateen (Wikipedia) | **99.6** / 103.0 / 100.4 / 97.8 / 95.8 | — |
| **ILCA 7 (Laser)** | LOA 4.23 m, LWL 3.96 m, hull 59 kg, sail 7.06 m² (Wikipedia ILCA) | **91.1** / 93.7 / 92.3 / 91.0 / 88.2 (RYA PN 1101 for ILCA 7) | — |
| **Catalina 22** | LOA 21.5 ft, LWL 19.33 ft, beam 7.67 ft, displ 2,490 lb, swing keel draft 5.0 / 1.67 ft, SA 204.75 sq ft (main 101.4, jib 103.3) (Wikipedia) | SK/WK no spi **96.3**/98.4/96.3/95.3/95.1. SK w/spi 94.7. Fixed keel no spi 97.1. | **270** avg (243–280) |
| **Catalina 30** | LOA 29.9 ft, LWL 25.0 ft, displ 10,200 lb, ballast ~4,200 lb, SA ~446 sq ft (keelindex) | Std rig **85.8**/88.6/87.1/85.5/82.7. Tall rig 84.0. | **180** (keelindex) |
| **Hobie 16** | LOA 5.05 m, beam 2.41 m, hull 145 kg (320 lb), main 13.77 m², jib 5.12 m², total ≈ 20 m² (Wikipedia) | **76.0** / 81.5 / 78.7 / 74.1 / 71.3 | ~126 (Arizona YC conversion) |
| **Corsair 880** | LOA 28'8" (8.8 m), beam 8'2" folded / 22'3" open, **displ 3,659–3,660 lb (1,660 kg)**, SA 554 / 677 sq ft (51.5 / 62.9 m²), mast 39'4" (12 m), Sport +70 cm (Multihulls World test MW185) | Not listed. Nearest: **Corsair F-28 67.1** (F-28R 65.0). | F-28 ≈ 30 (Arizona YC) |
| **Lagoon 42 (2016)** | LOA 42 ft (12.80 m), LWL 41 ft, beam 25'3" (7.70 m), light displ **12.1 t (26,681 lb)** (Lagoon), main 55–59 m² (std/square-top), self-tacking jib 35 m², Code 0 68–78 m², air draft 20.6 m (67'7"), draft 4'1" (Lagoon site, Sailing Mag) | Not listed. | No PHRF found. |

Sources:
- US Sailing D-PN page: https://www.ussailing.org/competition/offshore/dpn/ · **Precalculated table PDF** https://www.ussailing.org/wp-content/uploads/2018/01/2017-Portsmouth-Precalculated-Classes.pdf · Handbook https://www.ussailing.org/wp-content/uploads/2018/01/2017-North-American-Portsmouth-Yardstick-Handbook.pdf
- D-PN wind bands (per the Handbook): DPN1 = 0–3 kt, DPN2 = 4–7, DPN3 = 8–11, DPN4 = 12+ **[band edges from memory; confirm in Handbook]**. Corrected time = elapsed × 100 / D-PN (https://en.wikipedia.org/wiki/Portsmouth_Yardstick).
- Arizona YC club tables (PHRF/DPN cross-reference): https://arizonayachtclub.org/racing/club-rating-tables/
- J/22: https://en.wikipedia.org/wiki/J/22 · https://sail1design.com/j22/ · class site http://www.j22.org/ **[not fetched]**
- Sunfish https://en.wikipedia.org/wiki/Sunfish_(sailboat) · ILCA https://en.wikipedia.org/wiki/ILCA_(dinghy) · Hobie 16 https://en.wikipedia.org/wiki/Hobie_16 · Catalina 22 https://en.wikipedia.org/wiki/Catalina_22 · Catalina 30 https://keelindex.com/boat/catalina-30/performance
- Corsair 880: https://blog.corsairmarine.com/wp-content/uploads/2022/08/MW185-Corsair-880-Trimaran-Test-Sail-Extract.pdf · https://corsairmarine.com/corsair-880-sport
- Lagoon 42: https://www.catamarans-lagoon.com/boats/lagoon-42 · https://wikipedia.com/wiki/Lagoon_42-2 · https://sailingmagazine.net/article-1852-lagoon-42.html (SA/D 18.99, D/L 171). Note https://en.wikipedia.org/wiki/Lagoon_42 is the **1990** model, a different boat.

**How to use D-PN as a calibration check:** D-PN is a speed ratio around a course (time ∝ D-PN). Over a W/L or triangle course in a given wind band, sim lap times should satisfy t_boat / t_ref ≈ DPN_boat / DPN_ref. Example at 8–11 kt (DPN3): ILCA 91.0, Sunfish 97.8, Hobie 16 74.1, Catalina 30 85.5, C22 95.3, F-28 67.2. So a Sunfish should take ~7.5 % longer than an ILCA, and a Hobie 16 ~19 % less time than an ILCA. Use the per-band columns, because ranking changes with wind: the Sunfish is relatively better in heavy air, and the Hobie much better in breeze. For PHRF (sec/mile), the corrected-time difference per mile between two boats ≈ ΔPHRF seconds. A J/22 (~180) and Catalina 30 (180) should be roughly equal around a course. The C22 (270) is ~90 s/mile slower.

### 3.2 Polars / speed data

| Name | URL | What it gives | How to use |
|---|---|---|---|
| **ORC One-Design certificate — J/22 (2021)** | https://data.orc.org/public/od/2021/j22.od.html?nav=1 (PDF 2019: https://data.orc.org/public/od/2019/j22.od.pdf) | Full VPP polar (table below), RM, sail areas. | **Primary J/22 target polar.** |
| keelindex Catalina 30 | https://keelindex.com/boat/catalina-30/performance | ORC-VPP-based speeds averaged from 3 ORC certificates (table below). | Catalina 30 target polar. Also look for individual ORC Club certs (e.g. https://data.orc.org/public/WPub.dll/CC/04560004V6J redirects to sas.orc.org and needs a browser). |
| keelindex J/22 | https://keelindex.com/boat/j-22/performance | Same method for J/22. | Cross-check. |
| ORC Sailor Services | https://orc.org/sailors/sailor-services | Self-service ORC VPP runs. | Generate Catalina 22/30 polars from measured hull/rig if needed (paid). |
| Hobie 16 polar (Hobie Hotline ~1978, Al Bowers) | https://thebeachcats.com/OnTheWire/westnet/_lpm/hobie/archives/v1-i3/feature3.htm | Polar **image** at 10 kt TWS only, comparing H16 with other boats. Notes: H16 "all tack downwind" (fastest VMG not at 180°). Accuracy caveats. | Shape check only. No published VPP for Hobie 16 was found, so build one from GPS logs (§5.2) or the H16 measured-speed folklore. |
| Laser VPP validated vs measured data — Day (2017) | https://strathprints.strath.ac.uk/59980/ (PDF https://strathprints.strath.ac.uk/59980/1/Day_OE_2017_Performance_prediction_for_sailing_dinghies.pdf) | Ocean Engineering 136:67–79, doi:10.1016/j.oceaneng.2017.02.025. Custom Laser VPP with "excellent agreement" upwind against measured data. Covers depowering, heel decoupled from hiking moment, and crew weight (±10 kg gives >60 s/hr). | **ILCA 7 polar source**. Its formulation (hiking moment, depower) is a good template for the dinghy physics model. |
| Laser best heel/trim — Pennanen et al. (2016) | https://research.chalmers.se/en/publication/234579 | Procedia Eng. 147:336–341. Inverse VPP from towing tank + CFD (2–5 kt). Small heel is beneficial in higher winds. | Tune ILCA AI/auto-hike target heel. |
| Laser sailor motion/hiking — Taylor, Banks, Turnock (2016) | https://eprints.soton.ac.uk/400462 | CSYS 2016: IMU suit + video to measure hiking moment on a Laser. | Hiking moment magnitudes and dynamics for crew-weight animation and physics. |
| Corsair 880 measured speeds (MW185 test) | link above | 10–15 kt TWS: **>8 kt upwind at ~40° TWA in 15 kt**. **10.4 kt** max on a run (≥9 kt sustained). ~7 kt under 9.9 hp outboard. | Spot-check points for the trimaran polar. |
| Lagoon 42 | — | No manufacturer polar found online (brochure request only: catamarans-lagoon.com/brochure). Listing sheets show cruise ~7 kt, max ~8 kt (motor). keelindex hull speed 8.6 kt is a monohull formula and not meaningful for a cat. | Build the polar from SA/D 18–19 and D/L ~171 with cruising-cat rules of thumb. Ask the Lagoon dealer for the polar. |
| US Sailing Speed Guide explanation/sample | https://www.ussailing.org/wp-content/uploads/2018/01/Speed-Guide-Explanation.pdf · https://www.ussailing.org/wp-content/uploads/2018/01/Speed-Guide-Sample.pdf | How VPP speed guides are presented. | Format reference. |

**J/22 ORC OD rated boat speeds (kt):**

| TWA \ TWS | 6 | 8 | 10 | 12 | 14 | 16 | 20 |
|---|---|---|---|---|---|---|---|
| Beat angle | 43.5° | 42.4° | 40.9° | 39.0° | 38.6° | 39.0° | 40.5° |
| Beat VMG | 2.85 | 3.44 | 3.87 | 4.14 | 4.20 | 4.20 | 4.15 |
| 52° | 4.38 | 5.21 | 5.62 | 5.83 | 5.94 | 5.97 | 5.98 |
| 60° | 4.65 | 5.43 | 5.77 | 6.00 | 6.18 | 6.25 | 6.26 |
| 75° | 4.84 | 5.56 | 5.91 | 6.21 | 6.52 | 6.74 | 6.89 |
| 90° | 4.99 | 5.75 | 6.16 | 6.45 | 6.67 | 7.02 | 7.59 |
| 110° | 5.03 | 5.81 | 6.30 | 6.84 | 7.33 | 7.70 | 8.39 |
| 120° | 4.87 | 5.71 | 6.20 | 6.75 | 7.37 | 8.04 | 9.19 |
| 135° | 4.38 | 5.29 | 5.91 | 6.37 | 6.91 | 7.55 | 9.40 |
| 150° | 3.65 | 4.61 | 5.42 | 5.95 | 6.38 | 6.87 | 8.14 |
| Run VMG | 3.16 | 4.00 | 4.73 | 5.40 | 5.87 | 6.26 | 7.19 |
| Gybe angle | 148° | 151° | 154° | 174° | 180° | 180° | 180° |

**Catalina 30 (keelindex, ORC-VPP median):**

| | 6 kt | 10 kt | 14 kt | 20 kt |
|---|---|---|---|---|
| Beat VMG | 3.1 | 4.1 | 4.3 | 4.3 |
| 90° | 5.1 | 6.4 | 6.8 | 7.2 |
| 110° | 5.1 | 6.5 | 7.1 | 7.7 |
| 120° | 4.9 | 6.4 | 7.0 | 7.9 |
| Run VMG | 3.3 | 4.8 | 5.7 | 6.7 |

At 14 kt: best upwind VMG at 41°, best downwind at 160°, top speed 7.1 kt at 110°.

Hull speeds (1.34√LWL ft) *(derived)*: J/22 5.8 kt · C22 5.9 · C30 6.7 · ILCA 4.8 · Lagoon 42 8.6 (not meaningful for a cat). J/22 VPP exceeds hull speed only off the wind at 16–20 kt with spinnaker, which is consistent.

**J/22 stability** *(derived)*: ORC RM 15.9 kg·m per degree with Δ 857 kg gives GM ≈ 15.9 × 57.3 / 857 ≈ **1.06 m** (small-angle). In the sim, linear RM ≈ 15.9 kg·m/° × φ is valid only to ~10–15°. Use a GZ curve beyond that. Crew hiking adds more: the 275 kg crew limit at ~1 m lever ≈ 275 kg·m.

### 3.3 J/22 tuning guides (rig and expected behaviour)

| Name | URL | Key numbers |
|---|---|---|
| **North Sails J/22 Tuning Guide** | https://northsails.com/sailing/en/resources/j22-tuning-guide | Rake: gooseneck band → template/bow-plate junction **4'11"** (hulls <1460) / **5' 1/8"** (≥1460). Pre-bend ~1" halyard off mast at spreaders. Base: uppers **250 lb ≈ 26 on PT-1** (~10 kt). Lowers ~5 on the black PT-1. Forestay ~6–7. Leeward upper should not wiggle >½". Spreader sag ½"–1½", straight at 20+. **Heel ~3–4° in 6–8 kt** with max-weight crew. Trim matrix 0–8 / 8–15 / 15–20 / 20+ kt: backstay slack → gradual → hard (blocks ~1' apart); vang slack until ~12 kt, then hard with boom bend; outhaul seam 1¾" → 1" → tight; traveler within 2" of weather seat in light air → centerline 15+; jib lead aft up to 2 holes (max 3) above 15 kt. |
| **Quantum J/22 Tuning Guide** | https://www.quantumsails.com/en/sails/one-design/documents/j22/j22_tuningguide | Headstay length **4'11½"–5'1"**. Loos **PT-1** uppers/lowers/headstay by TWS: 0–4: 15/11/3 · 5–9: 20/15/5 · 10–13: 25/19/8 · 14–16: 28/21/10 · 17–18: 31/25/13 · 18–25: 33/30/17. Loos Model A: 23/20/4 → 44/42/23. Main: top telltale flying 60 % (0–5 kt) → 30 % (6–8) → 15 % (8–12). Boom ~8" below centerline at 12+. "Keep the boat almost flat" at ~5 kt. Play backstay in puffs to limit heel and helm. Jib ease 1–3" in puffs. |
| Catalina 22 tuning (North) | https://northsails.com/sailing/en/resources/catalina-22-tuning-guide | Same structure for the C22. |

**How to use:** Make sail-control states (backstay, vang, outhaul, traveler, lead) map to the guide's wind bands. The sim's "auto-trim" should reproduce these settings. Calibrate the heel model so a J/22 with full crew hiking is ~3–4° at 6–8 kt and stays moderate (well under ~20°) when depowered per the guide up to ~15–18 kt. Excess heel then indicates missing depower physics.

### 3.4 Capsize behaviour (Sunfish, ILCA, Hobie 16)
- Sunfish: the hull is a sealed hollow pontoon, so it floats when capsized ("self-rescuing", not self-righting) (https://en.wikipedia.org/wiki/Sunfish_(sailboat)). No official Sunfish manual text on righting was retrievable. The Vanguard rigging manual (https://www.manualslib.com/manual/1739245/Vanguard-Sunfish.html) and the MYC rigging manual (https://myc.org/wp-content/uploads/2020/11/Sunfish-Riggin-Manual.pdf) don't cover it.
- General dinghy procedure (https://en.wikipedia.org/wiki/Capsizing): stand on or pull the centreboard/daggerboard to lift the mast, and "the hull's righting moment usually takes over once the mast is about 30 degrees from horizontal". Point the bow into the wind so the wind helps lift the sail, and avoid a re-capsize to the other side. Dinghies are treated as **non-self-righting**, and they can turtle (https://en.wikipedia.org/wiki/Turtling_(sailing)). Recovery from turtle: release sheets, stand on the hull or board, lever.
- Hobie 16: stand on the lower hull and pull a righting line over the upper hull. Act immediately, or it may turtle and be very hard to right.
- Discover Boating capsize recovery (scoop and single-handed): https://www.discoverboating.com/resources/sailing-capsize-recovery-scoop-and-single-handed-methods
- US Sailing Dinghy Entrapment report: https://www.ussailing.org/wp-content/uploads/2018/01/Dinghy-Entrapment-Report_Final.pdf
- **Sim rule:** Sunfish, ILCA, and Hobie 16 must stay capsized (stable at ~90°, able to turtle) until the player applies a righting action (board/line). Keelboats (J/22, C22, C30) self-right. Corsair 880 and Lagoon 42 are not self-righting once inverted, but they have very high initial stability.

---

## 4. Physics & visual references

### 4.1 Fetch-limited wave growth

| Name | URL | What it gives |
|---|---|---|
| USACE Coastal Engineering Manual EM 1110-2-1100 Part II Ch. 2 (Meteorology & Wave Climate) | PDF copy: https://pdhonline.com/courses/c772/Part-II-Chap_2entire.pdf | Fetch definition: direction within ±15° and speed within ±2.5 m/s, and the upwind coast limits fetch. Fully developed limit. Narrow-fetch and shallow-water sections II-2-2.b(1)(c),(d), b(3). |
| PlanetCalc CEM calculator | https://planetcalc.com/4442 | Restates the CEM equations (below). |
| USGS UMESC wind-fetch/wave tools | https://www.umesc.usgs.gov/management/dss/wind_fetch_wave_models.html (OFR https://pubs.usgs.gov/of/2008/1200/) | ArcGIS fetch + wave model (SPM 1984, CEM 2002, Smith 1991 restricted fetch). **Use it to compute directional fetch for Ray Hubbard from a shoreline polygon.** |
| ScientiMate (Python) `parametricwaveshallow` | https://scientimate.readthedocs.io/en/latest/python_functions/ocean_wave_parametric_model/parametricwaveshallow.html | Implements SPM-shallow, Young & Verhagen (1996, for shallow lakes), and Karimpour (2017). Input U10, fetch, mean depth. Also `mindurationdeep` etc. |

Equations (CEM, deep-water fetch-limited; U10 = 10-m wind, m/s):
- C_D = 0.001 (1.1 + 0.035 U10), u* = U10 √C_D
- g·Hm0 / u*² = 4.13×10⁻² (g·X / u*²)^½
- g·Tp / u* = **0.651** (g·X / u*²)^⅓. PlanetCalc prints 0.751; my recollection of CEM Eq. II-2-36 is 0.651, so verify in the PDF. The table below gives both.
- Duration to reach fetch-limited: t = 77.23 X^0.67 / (U^0.34 g^0.33)
- Fully developed: g·Hm0/u*² = 211.5, g·Tp/u* = 239.8
- Shallow-water caps (PlanetCalc): Tp ≤ 9.78 √(d/g), H ≤ 0.6 d
- SPM 1984 shallow-water (Eqs. 3-39/3-40, from memory), with adjusted wind U_A = 0.71 U10^1.23:
  H = 0.283 tanh[0.530 (gd/U_A²)^¾] · tanh{0.00565 (gF/U_A²)^½ / tanh[0.530 (gd/U_A²)^¾]} · U_A²/g
  T = 7.54 tanh[0.833 (gd/U_A²)^⅜] · tanh{0.0379 (gF/U_A²)^⅓ / tanh[0.833 (gd/U_A²)^⅜]} · U_A/g

**Computed for Lake Ray Hubbard** *(derived; mean depth 6.9 m; fetch in statute miles)*:

| Wind | Fetch | CEM Hm0 m (ft) | CEM Tp s [Tp with 0.751] | Min. duration h | SPM-shallow H m (ft) / T s |
|---|---|---|---|---|---|
| 10 kt | 3 mi | 0.17 (0.6) | 1.4 [1.6] | 1.7 | 0.18 (0.6) / 1.7 |
| 10 kt | 8 mi | 0.28 (0.9) | 1.9 [2.2] | 3.3 | 0.29 (0.9) / 2.2 |
| 10 kt | 22 mi | 0.46 (1.5) | 2.7 [3.1] | 6.5 | 0.42 (1.4) / 2.6 |
| 15 kt | 3 mi | 0.26 (0.9) | 1.6 [1.8] | 1.5 | 0.30 (1.0) / 2.0 |
| 15 kt | 8 mi | 0.43 (1.4) | 2.2 [2.5] | 2.9 | 0.47 (1.5) / 2.6 |
| 15 kt | 22 mi | 0.71 (2.3) | 3.1 [3.5] | 5.6 | 0.69 (2.2) / 3.3 |
| 20 kt | 3 mi | 0.36 (1.2) | 1.8 [2.0] | 1.3 | 0.43 (1.4) / 2.3 |
| 20 kt | 8 mi | 0.59 (1.9) | 2.4 [2.8] | 2.6 | 0.65 (2.1) / 3.0 |
| 20 kt | 22 mi | 0.98 (3.2) | 3.4 [3.9] | 5.1 | 0.93 (3.0) / 3.8 |
| 25 kt | 8 mi | 0.76 (2.5) | 2.7 [3.1] | 2.4 | 0.83 (2.7) / 3.3 |
| 30 kt | 8 mi | 0.94 (3.1) | 2.8 [3.3] | 2.3 | 1.02 (3.3) / 3.5 |

Caveat: Ray Hubbard's actual longest straight-line over-water fetch is probably well under 22 mi. The lake is ~19,500 acres and elongated roughly N–S, with I-30 causeways splitting it. **Measure directional fetch from the shoreline (UMESC tool or a GIS raycast)** and use the 3–8 mi rows as the likely realistic range. RCYC sits near the south end, so S winds have a short fetch there and N winds a long one. Use Hm0 as the spectrum's Hs, Tp as peak, and a JONSWAP shape with γ ≈ 3.3 for young fetch-limited seas.

### 4.2 Beaufort / sea state / whitecaps
- NOAA *Guide to Sea State, Wind and Clouds*: https://www.weather.gov/media/marine/SeaState.pdf. Also https://www.wpc.ncep.noaa.gov/html/beaufort.shtml and https://www.weather.gov/pqr/Beaufort
- Key rows: F2 4–6 kt small wavelets, glassy crests, not breaking. **F3 7–10 kt crests begin to break, scattered whitecaps** (whitecap onset ~7–10 kt). F4 11–16 kt numerous whitecaps. F5 17–21 kt many whitecaps, some spray. F6 22–27 kt whitecaps everywhere. F7 28–33 kt foam blown in streaks. Probable wave heights in the table (F3 0.6–1 m, F4 1–1.5 m) are **open-ocean** values. A fetch-limited lake is far lower (see §4.1). Use the visual descriptors (whitecap coverage, streaks) and the §4.1 heights.
- **How to use:** Drive the foam/whitecap coverage parameter from wind speed. It should be zero below ~7 kt and ramp through F3–F6. Check against reference photos taken at known logged wind speed (§5).

### 4.3 Kelvin wake
- https://en.wikipedia.org/wiki/Kelvin_wake_pattern: half-angle **19.47° = arcsin(1/3)** (total ~39°), deep water, independent of speed at moderate Froude number. At high hull Froude number Fr = U/√(gL) (Rabaud & Moisy 2013), the apparent wake angle narrows. In shallow water (depth Froude U/√(gh) → 1) the wake widens toward 90°.
- **How to use:** Check that the sim wake arms sit at ~19.5° for a displacement keelboat. Transverse wavelength λ = 2πU²/g (e.g. 6 kt → ~9.5 m, physics-standard). Narrower apparent wakes are expected for planing dinghies and cats.

### 4.4 Heel, righting moment, roll period
- Static heel: RM(φ) = Δ·g·GZ(φ) with GZ ≈ GM·sin φ at small angles. Equilibrium where heeling moment from sails (F_side × CE height above CLR) = RM(φ) + crew hiking moment. Standard references: Larsson & Eliasson, *Principles of Yacht Design* **[book, no URL]**, and the ORC VPP documentation at https://orc.org **[not fetched]**.
- Roll period (IMO Res. A.562(14) weather criterion): T = 2·C·B / √GM, with C = 0.373 + 0.023 (B/d) − 0.043 (L/100) (L, B, d, GM in metres): https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/AssemblyDocuments/A.562(14).pdf. Ships formula, so use it only as a sanity check. J/22 example *(derived)*: B 2.446, d 1.179, L 6.86, GM 1.06 gives C 0.418 and **T ≈ 2.0 s**. Compare with the phone-measured roll decay (§5.2), since the free roll period of a small keelboat should come out ~2–3 s. Physics form: T = 2π k / √(g·GM), k = roll radius of gyration ≈ 0.35–0.45 B.

### 4.5 Sky, atmosphere, exposure
| Name | URL | Use |
|---|---|---|
| Hillaire 2020, "A Scalable and Production Ready Sky and Atmosphere Rendering Technique" (EGSR, CGF 39(4)) | https://diglib.eg.org/handle/10.1111/cgf14050 · PDF https://diglib7.eg.org/bitstream/handle/10.1111/cgf14050/v39i4pp013-022.pdf · slides https://blog.selfshadow.com/publications/s2020-shading-course/hillaire/s2020_pbs_hillaire_slides.pdf | The model behind UE's SkyAtmosphere component. Its parameter definitions (Rayleigh/Mie scattering, ozone absorption) let you set physically measured values. |
| UE Sky Atmosphere docs | https://dev.epicgames.com/documentation/unreal-engine/sky-atmosphere-component-in-unreal-engine | Component parameters. |
| UE Physical Lighting Units | https://dev.epicgames.com/documentation/en-us/unreal-engine/using-physical-lighting-units-in-unreal-engine | cd, lm, lux, EV100. Sky light luminance = pixel × intensity (cd/m²). Raise Auto Exposure Max EV100 if the image goes white. Clear-sky sun is commonly ~100–120 klux at the ground **[general physics figure, not from this page]**. |
| Kider et al. 2014, "A Framework for the Experimental Comparison of Solar and Skydome Illumination" (ACM TOG / SIGGRAPH Asia, doi 10.1145/2661229.2661259) | PDF https://w1.graphics.cornell.edu/Kider-ClearSkyCapture(2014).pdf · dataset http://www.graphics.cornell.edu/resources/clearsky/ | **Measured** spectral sky radiance (81 points/hemisphere, 350–2500 nm), HDR fisheye, and pyranometer data. Analytic models err most near the sun and horizon. Hosek beats Preetham, which shows red horizon saturation. Use the dataset to check the UE sky gradient and horizon colour. |
| Magnopus: lighting in Unreal with photography principles (PBL) | https://www.magnopus.com/blog/lighting-in-unreal-with-photography-principles | Practical EV100 / camera-matched workflow. |
| "Towards Physically-Based Sky-Modeling" (arXiv 2412.11883) | https://arxiv.org/pdf/2412.11883 | Recent sky-model evaluation. |

### 4.6 Moon / sun ephemeris
| Name | URL | Use |
|---|---|---|
| USNO Astronomical Applications API | https://aa.usno.navy.mil/data/api · phases: `https://aa.usno.navy.mil/api/moon/phases/date?date=2026-10-1&nump=12`, `.../phases/year?year=2026` · rise/set/transit + **fracillum, curphase**: `https://aa.usno.navy.mil/api/rstt/oneday?date=2026-10-12&coords=32.82,-96.50&tz=-6&dst=true` | Ground truth for moon phase, illumination fraction, and rise/set at RCYC and Kemah. Unit-test the in-engine ephemeris against it. |
| Meeus, *Astronomical Algorithms* (2nd ed., Willmann-Bell 1998) **[book]** | — | Standard algorithms (ch. 47 Moon position, ch. 48 illuminated fraction, ch. 49 phases) **[chapter numbers from memory]**. |
| SunCalc (JS, based on Astronomy Answers formulas) | https://github.com/mourner/suncalc | Compact sun/moon position, illumination, and parallactic angle. Easy to port to C++ for UE. Moon disc orientation (bright-limb angle) comes from the parallactic angle. |

---

## 5. Methodology & tools

### 5.1 Photogrammetry / scanning
| Tool | URL | Use |
|---|---|---|
| RealityScan 2.0 (ex-RealityCapture, Epic) | https://www.realityscan.com/news/realityscan-20-new-release-brings-powerful-new-features-to-a-rebranded-realitycapture · https://en.wikipedia.org/wiki/RealityCapture | Desktop photogrammetry released 17 Jun 2025 via the Epic Launcher. Free below US$1M revenue (subscription above). AI masking, quality heatmaps, LiDAR fusion. Use it for club docks, the clubhouse, shoreline riprap, and boat hulls. RealityScan Mobile is the phone app. |
| Apple Object Capture (RealityKit `PhotogrammetrySession`, macOS) | https://developer.apple.com/documentation/realitykit/realitykit-object-capture.md · CLI tutorial https://developer.apple.com/tutorials/data/documentation/realitykit/creating-a-photogrammetry-command-line-app.md · WWDC21 https://developer.apple.com/wwdc21/10076/ | Mac-side reconstruction of fittings, blocks, tillers, and small objects. iPhone LiDAR depth can be supplied with samples. |
| Polycam | https://poly.cam **[unverified URL]** | iPhone LiDAR room/dock scans and quick scale reference. |
| Workflow note | — | Shoot with a ColorChecker in frame and a known-length scale bar. Use overcast light for albedo capture. Hulls are glossy gelcoat, so use cross-polarisation or dulling spray on small parts. |

### 5.2 On-water sensor logging (heel, roll, speed, GPS)
| Tool | URL | What it gives / use |
|---|---|---|
| Sensor Logger (Tsz Hei Choi) | https://apps.apple.com/us/app/-/id1531582925 | iOS/watchOS: accelerometer, gyro, **orientation (roll/pitch/yaw)**, magnetometer/compass, barometer, GPS speed/heading, video, timestamped annotations. Export CSV/JSON/KML/SQLite (some formats paid). Mount the phone on the centreline bulkhead to log heel and roll time series plus GPS SOG/COG. |
| SensorLogger – CSV Export (different app) | https://apps.apple.com/app/id1505203547 | Alternative iOS logger. |
| phyphox (RWTH Aachen) | https://phyphox.org/ · F-Droid https://f-droid.org/packages/de.rwth_aachen.phyphox/ · iOS https://apps.apple.com/app/1127319693 | Free on iOS and Android. Includes an inclination experiment. **Remote control and download from a laptop browser.** Export CSV/Excel. Good for **roll-decay tests** at the dock (push the boat and log roll to get the natural roll period and damping) and for heel-vs-wind logs. |
| GPS tracks (Strava GPX, Navionics track export, SailGPS etc.) | **[no URLs verified]** | SOG/COG per second. Combine with the simultaneous Eagle Point / HQZ / F46 wind (or a handheld anemometer) to build measured polar points. |
| Building a polar from logs | https://firstshiftsailing.substack.com/p/how-to-build-a-polar-for-the-boat | Method: 1 Hz logging. Drop data within minutes of manoeuvres. Bin by TWS (1–2 kt) × TWA (5°). Take the **90th percentile** per bin, not the mean. Check sample counts, smooth, and flag sparse bins. Apply it to your J/22 and Sunfish logs, then compare with the ORC and D-PN predictions. |
| SailGRIB polar creation | https://sailgrib.com/en/apps/sailgrib-wr/aide/routing/create-your-boat-polar/ | Polar file format (TWA × TWS grid). Handy as the sim's polar data format. |

### 5.3 Video analysis
| Tool | URL | Use |
|---|---|---|
| Tracker (Open Source Physics, D. Brown) | https://physlets.org/tracker/ **[canonical URL from memory; mirrors: https://www.linuxlinks.com/tracker-2/]** | Frame-by-frame point tracking with scale calibration. Measure mast-tip roll amplitude and period, wave crest speed and period (Tp check vs §4.1), wake angle, and tack/gybe timing. |
| ffmpeg | https://ffmpeg.org **[not fetched]** | Extract frames at fixed fps (`ffmpeg -i in.mp4 -vf fps=10 f_%05d.png`) for side-by-side comparison with sim captures. Make matched-framerate stacks with `hstack`. |

### 5.4 Image comparison
| Tool | URL | Use |
|---|---|---|
| NVIDIA ꟻLIP | https://github.com/NVlabs/flip · paper https://research.nvidia.com/publication/flip | LDR-FLIP and HDR-FLIP perceptual error maps. `pip install flip-evaluator`, then `flip -r ref.png -t test.png` (BSD-3). Use HDR-FLIP on EXR captures against calibrated reference HDR photos at the same camera pose and time. |
| SSIM (scikit-image `structural_similarity`) | https://scikit-image.org/docs/stable/api/skimage.metrics.html **[not fetched]** | Structural similarity for regression tests of sky, water, and foam looks. |
| ColorChecker workflow | — | Photograph the chart in each reference shot. White-balance and expose to the 18 % grey patch, then compare chart patch values rendered in UE (chart model in scene under the same sky) with photo values. |

### 5.5 Look-dev with reference photography
| Name | URL | Use |
|---|---|---|
| CAVE Academy — neutral look-dev environment | https://caveacademy.com/wiki/post-production-assets/surfacing/surfacing-training/creating-a-neutral-look-development-environment/ | Calibrate the real and CG sets with a grey ball (exposure) and colour chart (white balance), which "gets you 90% of the way". HDRI pixel values are relative and must be converted to absolute units. |
| HDRI shooting & editing (Xuan Prada & Greg Zaal) | https://pixelsham.com/?p=13000 | Bracketed HDRI capture on the water or dock for UE HDRI backdrop and sky-light comparison. Measure the sun with a lux meter to set absolute scale. |
| Chrome-ball lighting reference | https://forum.highend3d.com/t/how-to-use-chrome-balls-for-lighting-reference/62023 | Shoot chrome and grey balls on the boat deck next to a ColorChecker at known times. Render identical balls in UE at the same sun position (USNO/SunCalc) and compare with FLIP. |
| VFX Voice article | https://vfxvoice.com/?p=726 **[content not checked]** | Industry practice. |

### 5.6 How other sailing sims validated physics
| Name | URL | Takeaway |
|---|---|---|
| Clark, N.A. (2023) *Validation of a sailing simulator using full scale experimental data*, Univ. Tasmania PhD/MPhil thesis | https://figshare.utas.edu.au/articles/thesis/Validation_of_a_sailing_simulator_using_full_scale_experimental_data/23235968 · https://eprints.utas.edu.au/18684/ | Virtual Sailing Pty Ltd ride-on simulator (Laser, Megabyte, V-Sail Access). Full-scale trials at Albert Park Lake logged VOG, apparent wind speed and angle, rudder angle, and GPS, then the simulator replayed the same course. **Manoeuvring matched, but speed vs TWA differed by up to an order of magnitude.** Recommends separately validating hull drag, sailor righting moment, and sail forces. That is a direct template for this project. |
| UTas "Verification and validation of an active sailing simulator" (conf.) | https://figshare.utas.edu.au/articles/conference_contribution/Verification_and_validation_of_an_active_sailing_simulator/23090681 | Embargoed. Same group. |
| Sailaway (Richard Knol) | https://www.gamepressure.com/newsroom/meet-sailaway-the-most-accurate-sailing-simulator-ever/za44b | Solo developer. Real-time NOAA weather. No published validation method found. |
| eSail | https://www.pressreader.com/uk/practical-boat-owner/20181201/282875141770019 (PBO review) | No validation paper found. |
| Virtual Regatta | — | No public statement found on how polars are derived. Community polars are typically VPP/ORC-like. **[not found]** |
| "Multiple Applications of Sailing Simulation" | https://www.academia.edu/12254307/Multiple_Applications_of_Sailing_Simulation | Background. |

---

## 6. Suggested calibration checklist (how the above fits together)
1. **Wind climate:** fetch HQZ + F46 (5-min), DAL (1-min gusts), Eagle Point (6-min overwater). Fit seasonal speed, direction, and gust-factor distributions.
2. **Waves:** Ray Hubbard uses directional fetch × §4.1 (Hs 0.2–1 m, Tp 1.5–3.5 s for 10–25 kt). Galveston Bay uses SPM-shallow with d ≈ 2 m. The Gulf uses JONSWAP fits to 42035 spectra.
3. **Boat speed:** J/22 against the ORC table. C30 against keelindex/ORC. ILCA against Day (2017). Cross-boat ratios against D-PN per wind band. Corsair 880 against the MW185 spot points. Fill Hobie and Lagoon from your own GPS logs.
4. **Heel and roll:** J/22 3–4° heel at 6–8 kt per North. GM ≈ 1.06 m from ORC RM. Roll period ~2 s (IMO estimate), validated by phone roll-decay tests.
5. **Capsize:** dinghies and the beach cat stay down until righted. Keelboats self-right.
6. **Visuals:** whitecap onset at F3 (7–10 kt). Kelvin half-angle 19.47°. Sky checked against Kider measured radiance. Exposure in physical units. Moon from USNO. Reference photos with ColorChecker, grey and chrome balls, and HDRI, compared via ꟻLIP.
