# Reference Footage: Monohulls (J/22, Sunfish, ILCA/Laser, Catalina 22, Catalina 30)

Researched 2026-10-12 for the sailing simulator realism pass.

## How to read this file

- Every URL below came from a web search result. None was made up.
- **[V]** means the title and channel were confirmed through the YouTube oEmbed proxy (noembed.com). Titles marked [V] are the live titles.
- **[S]** means the URL comes from search results only.
- **I could not watch any of the videos.** YouTube pages and descriptions blocked fetching from this environment. So "Shows" is inferred from the title, the channel and any linked event reports. Treat it as *expected* content and confirm it while scrubbing the clip.
- Wind figures come from the clip title or from regatta reports for the same day, and the source is cited each time. "Wind: not stated" means I found no figure.
- Buckets used: LIGHT 0-7 kn, MODERATE 8-15 kn, HEAVY 16-25 kn, STORM 25+ kn (knockdown, capsize, broach).

---

## 1. J/22 (highest priority)

### Published data points (J/22)

| Item | Value | Source |
|---|---|---|
| LWL / hull speed | 19.0 ft / 5.8 kn | keelindex.com/boat/j-22/performance |
| Displacement | 1,790 lb; ballast/disp 39.1%; SA/D about 24.2 | keelindex; North Sails speed guide |
| VPP polar (site says ORC VPP; I did not verify where it came from) | TWS 6/10/14/20 kn. Best upwind VMG speed 2.8 / 3.9 / 4.3 / 4.3 kn. Beam reach (90°) 4.9 / 6.1 / 6.6 / 7.5 kn. At 120° TWA: 4.7 / 6.1 / 7.2 / **9.2** kn (planing/surfing at 20 kn). At 14 kn: best upwind TWA 37°, best downwind TWA 172° | https://keelindex.com/boat/j-22/performance |
| Crew weight limit | 605 lb (3-4 people). "Flat is fast": hike hard upwind. Planes "near the top of the wind range" | https://northsails.com/sailing/en/resources/j-22-speed-guide |
| Rig tension by wind | Bands of 0-4, 5-9, 10-13, 14-16, 17-18 and 18-25 kn, with Loos gauge numbers. Crew all on the rail at 10-15 kn. At 12+ kn about ½" backstay. Ease the jib 1-3" in puffs at 12-18 kn | https://www.quantumsails.com/en/sails/one-design/documents/j22/j22_tuningguide |
| Top speed anecdote | The J22 *Geronimo* crew sailed in "30+ knots of breeze". Their earlier personal best was **16 kn** of boat speed. The article references a YouTube video but gives no URL | https://spinsheet.com/node/7283 |

Sim check: in 14-18 kn, upwind speed should top out at about 4.3 kn VMG (6.0-6.4 kn at 52-60° TWA). A 20 kn broad reach under spinnaker should reach about 8-9 kn in bursts. Heel upwind should stay low (crew hiking, traveler and backstay depower) instead of growing linearly with wind.

### J/22: LIGHT (0-7 kn)

1. **2024 J/22 World Championship - Friday** [V]
   - URL: https://www.youtube.com/watch?v=evSED4AFYIU
   - Source: T2PTV: Sailing On Demand
   - Wind/location/date: **southerly 5-7 kn**, Chesapeake Bay, Annapolis (Eastport YC), 25 Oct 2024. Yachtsandyachting Day 3 report: https://yachtsandyachting.com/news/280858/2024-J-22-Worlds-at-Annapolis-Maryland-Day-3
   - Shows (expected): professional chase-boat and on-water coverage of a 48-boat fleet in light air, with a general recall and black-flag starts that day.
   - Check: near-zero heel, crew weight to leeward or centered, fuller sails, eased backstay, slow tacks that hold speed, flat wake. Compare boat speed against the 6 kn polar (about 2.8 kn VMG upwind).

2. **J/22 World Championship 2021, Corpus Christi YC, Texas (report and photos; no video found)** [S]
   - URL: https://www.marinebusinessworld.com/news/239741/J-22-Worlds-at-Corpus-Christi-day-1
   - Wind/location/date: **6-8 kn** on Day 1, "unsettled", only one race. Corpus Christi Bay, TX, 19-23 Jul 2021. A KIII-TV piece says winds built over the last two days: https://www.kiiitv.com/article/sports/j22-champion-leads-wire-to-wire-this-week-kiii-3sports/503-f8d264cd-a4ff-4048-86c7-e2ce287d0c47 (local TV page; it may embed a news video, not confirmed).
   - Check: Texas coastal light-to-moderate sea breeze and the photo look of J/22 fleets in Texas water and light.

3. **Sailing a J22 in Newport Beach, CA (July 2022)** [V]
   - URL: https://www.youtube.com/watch?v=xnap2aMQTxo
   - Source: keeldragger
   - Wind: not stated. Newport Harbor in summer is typically light to moderate.
   - Shows (expected): onboard daysail footage.
   - Check: cockpit-level camera, how the sails look from the helm, and harbor chop.

4. **J22 Sailing Lake Washington February** [V]
   - URL: https://www.youtube.com/watch?v=E1tYvoxQ4CA
   - Source: danamite358
   - Wind: not stated. Winter lake.
   - Check: inland-lake water texture (short wind chop with no swell), which is relevant to Texas lakes.

### J/22: MODERATE (8-15 kn)

5. **2024 J/22 World Championship - Wednesday** [V]
   - URL: https://www.youtube.com/watch?v=gg61tm1bwjI
   - Source: T2PTV: Sailing On Demand
   - Wind/location/date: Day 1 report says **8-10 kn, light chop**, blue skies, Annapolis, 23 Oct 2024 (https://yachtsandyachting.com/news/280794/2024-J-22-Worlds-at-Annapolis-Maryland-Day-1).
   - Check: the low end of the moderate band. Crew start to hike, heel is about 5-12° with the traveler working, and jibs trimmed tight. Fleet starts and mark roundings work as overall scene composition reference.

6. **2024 J/22 World Championship - Saturday** [V]
   - URL: https://www.youtube.com/watch?v=BFntxjaYtDI
   - Source: T2PTV
   - Wind: not stated in reports. The final day; *Baby Doll* (Glenn Darden, a Fort Worth sailor) won two races. Annapolis, 26 Oct 2024.
   - Check: the closing races. Watch for a Texas team's boat handling.

7. **2024 J/22 World Championship - Wrap Up** [S]
   - URL: https://www.youtube.com/watch?v=Z68kGceoCOs
   - Source: T2PTV (by series naming)
   - Shows: a highlight compilation that likely covers all conditions from 5-7 kn to 16-18 kn. It is a good single clip for A/B comparison against the sim.

8. **J/22 Tacking** [V]
   - URL: https://www.youtube.com/watch?v=t2qLleZ0HAs
   - Source: Al Sargent
   - Shows (expected): an instructional clip of a tack sequence, likely filmed onboard.
   - Check: tack timing (helm to new close-hauled), jib cross and re-trim, crew cross, speed loss through the tack, and how far the boat turns (about 75-90° between close-hauled tacks on a J/22).

9. **J/22 Spinnaker Sets** [V]
   - URL: https://www.youtube.com/watch?v=5T4qPmYgV-I
   - Source: Al Sargent
   - Check: bear-away and hoist sequence, the pole going up, and when the chute fills relative to the turn.

10. **J/22 Spinnaker Jibes** [V]
    - URL: https://www.youtube.com/watch?v=h42r8WXgxY4
    - Source: Al Sargent
    - Check: end-for-end pole gybe on a symmetric spinnaker, the timing of the boom crossing, and whether the chute stays full or collapses during the gybe.

11. **J/22 Spinnaker Douses** [V]
    - URL: https://www.youtube.com/watch?v=2G3LSq2SFSc
    - Source: Al Sargent
    - Check: the takedown sequence before a leeward mark, and how the sail collapses and is pulled in.

12. **Sailing a J22 under a Bright Blue Spinnaker** [V]
    - URL: https://www.youtube.com/watch?v=nzMY-8iQ0c0
    - Source: Clyde Outside
    - Check: spinnaker shape and luff curl, the boat's attitude downwind, and the stern wake.

13. **J22 Sailing Practice - Cleveland, Ohio** [V]
    - URL: https://www.youtube.com/watch?v=RBvnch38sP0
    - Source: Ryan Lashaway
    - Shows: practice on Lake Erie. Likely an onboard camera.
    - Check: freshwater lake chop and practice maneuvers.

14. **Inside the Class: J/22** [V]
    - URL: https://www.youtube.com/watch?v=XlEAD1SVrSU
    - Source: Sailing World
    - Shows: a class profile with on-water footage and interviews.
    - Check: general proportions of the boat and rig, crew positions, and the cockpit layout for the onboard camera.

15. **J/22 Singlehanded sailing** [V]
    - URL: https://www.youtube.com/watch?v=bppni8MVqs8
    - Source: ian hunter
    - Check: a single-crew helm view, which is useful if the sim allows solo play. Expect more heel because there is no crew weight on the rail.

16. **Sailboat Racing, Sailing Crashes - J22 Regatta** [V]
    - URL: https://www.youtube.com/watch?v=zjp62xjwkyw
    - Source: Clyde Outside
    - Shows (expected): close-quarters fleet racing and contact or near-misses.
    - Check: collision and near-collision behavior, plus bow-wave size at close range.

17. **Blue J ducking a J22 under spinnaker** [S]
    - URL: https://www.youtube.com/watch?v=wy_6cJ0Y-ck
    - Check: a J/22 under spinnaker seen from another boat, a good external camera reference.

18. **J22s of Annapolis** [S]
    - URL: https://www.youtube.com/watch?v=wGKwclDvFVA
    - Check: fleet racing on the Chesapeake.

### J/22: HEAVY (16-25 kn)

19. **2024 J/22 World Championship - Thursday** [V], the best J/22 heavy-air clip with a stated wind speed.
    - URL: https://www.youtube.com/watch?v=N_tNWa-hfw0
    - Source: T2PTV
    - Wind/location/date: **16-18 kn, dropping only slightly**, sunny, **choppy seas**, Chesapeake Bay, 24 Oct 2024. Sources: https://j22.org/?p=1249 and https://yachtsandyachting.com/news/280823/2024-J-22-Worlds-at-Annapolis-Maryland-Day-2
    - Check: full hike, max backstay, eased traveler, vang sheeting, and how much the main is feathered or luffing in puffs. Spray over the bow in chop, pitching motion, spinnaker reaching or planing bursts downwind, and broach risk at mark roundings. Target speeds: about 4.3 kn VMG upwind, 7-9 kn bursts downwind.

20. **Legendary J22 Sailboat Takes On HEAVY Air Action #sailing #sailboatracing #racingboat** [V]
    - URL: https://www.youtube.com/watch?v=iRTATat7KbU
    - Source: Sailing Team Tally Ho!
    - Wind: not stated ("HEAVY air").
    - Check: heel angle under gusts, crew hiking, and spray.

21. **Awesome heavy air mark rounding..j22! Sailing Team Tally Ho! captures expert crew work.** [S] (YouTube Short)
    - URL: https://www.youtube.com/shorts/emLwO97YfT0
    - Source: Sailing Team Tally Ho! (by title)
    - Check: windward or leeward mark rounding in breeze, the spinnaker hoist or douse under load, and rudder loading and heel during the turn.

22. **Crazy J/22 sailing in Jamaica** [V]
    - URL: https://www.youtube.com/watch?v=Thc4S-pR5XI
    - Source: J22-Geronimo
    - Wind: not stated. This is the same crew as the Spinsheet speed-trial article, where they sailed in 30+ kn with a previous best of 16 kn boat speed (https://spinsheet.com/node/7283). It is likely heavy trade-wind conditions, possibly STORM bucket.
    - Check: planing under spinnaker, rooster tail and stern wake at high speed, and wipeouts.

23. **33rd Annual Jamin J/22 Regatta at Montego Bay Yacht Club - Highlights** [V]
    - URL: https://www.youtube.com/watch?v=0YjUvAofpVM
    - Source: DRIFT UAV Services (drone)
    - Wind: not stated. Montego Bay trades are typically moderate to heavy.
    - Check: **aerial/drone** view of wake patterns, fleet spacing and whitecap density. Good for a sim chase or overhead camera.

24. **Round The Island Race in a J22...** [V]
    - URL: https://www.youtube.com/watch?v=uw2EumJQzj4
    - Source: jaaaaapor
    - Wind: not stated. Likely the Isle of Wight Round the Island Race (Solent), which often has strong tide and chop. Bucket is not certain.
    - Check: open-water waves and an onboard view.

### J/22: STORM / broach

- No J/22-specific broach or knockdown clip with a confirmed title was found. Candidates:
  - The *Geronimo* clip above (#22).
  - A generic keelboat broach recovery clip, "Recovering from a broach / wipeout" [S]: https://www.youtube.com/watch?v=M3q5sxacAoQ
  - "Amazing broach on an Etchells 22" [S], a similar-size keelboat: https://www.youtube.com/watch?v=emJaVjjK4UE
- Sim check: a J/22 keelboat should round up and lie on its side with the spinnaker flogging, then **self-right** once the sheets are eased (39% ballast ratio). It should not turtle.

### J/22: Texas lakes (specific search results)

- No YouTube clip of a J/22 on Lake Ray Hubbard, Rush Creek YC, Corinthian SC or Austin YC turned up in search. The Texas material I found:
  - **Rush Creek Yacht Club YouTube channel** [S]: https://www.youtube.com/@rushcreekyachtclub7644. Check it for club-made J/22 clips. RCYC (Heath, TX, on Lake Ray Hubbard) hosted the **2025 J/22 Midwinters, 14-16 Mar 2025**. Friday had "gusty winds" with only one race, and the weekend was calmer (https://yachtsandyachting.com/news/284464/J-22-Midwinters-at-New-Orleans-overall; the URL slug says New Orleans but the content is RCYC).
  - **Texas Yacht Club Challenge Cup, Fort Worth Boat Club** (Eagle Mountain Lake, Dec 2023), sailed in the club's fleet of 10 J/22s; expected conditions were "calm-to-moderate breeze". Article: https://yachtsandyachting.com/news/269078/Dave-Valentine-on-the-TX-Yacht-Club-Challenge-Cup
  - **Sailing Lake Ray Hubbard** [V], from channel dallasboricua21c (boat type unknown). Use it for the look of the lake's water, shoreline and haze: https://www.youtube.com/watch?v=n6omVtBbU1A
  - **Catalina 310 Sailboat Racing** [S], which came up in a Lake Ray Hubbard search: https://www.youtube.com/watch?v=ozwlWtKaTYw
  - **J24 March Madness Austin Yacht Club** [V], from WeekendSailing. It shows the J/24, a larger sister boat with similar handling, on Lake Travis with the Hill Country backdrop: https://www.youtube.com/watch?v=AJBbpRBcSuU
  - **J/22 photo archive:** "J/22 Sailboat Regatta", Oklahoma Historical Society, 21 Jul 2003, lake not identified. It is a regional (southern plains) lake regatta photo: https://gateway.okhistory.org/ark:/67531/metadc1650759/

---

## 2. Sunfish

### Published data points / behavior notes (Sunfish)

- **Capsize behavior:** a Sunfish does **not self-right**. After a capsize it floats on its side with the lateen sail flat on the water. If the sail is left there, it can turtle with the mast pointing down, and in shallow lakes the mast can stick in mud. To recover, the sailor swims to the daggerboard, which must stay fully down, pulls or stands on it, and the boat comes up, usually pointing head to wind. The Lee Montes clip below covers how to avoid turtling.
- **Turtling:** a capsized dinghy that is not righted promptly can roll from about 90° to fully inverted. A float on the masthead prevents this. Climbing onto the high side of a knocked-down boat raises weight and windage and makes turtling more likely. Righting from turtle means standing on the centreboard. Source: https://en.wikipedia.org/wiki/Turtling_(sailing)
- **2023 Sunfish Worlds, Miami (5-9 Dec 2023):** Day 1 had a strong NW wind gusting into the 20s. Days 2-5 had gusts to about 12 kn. **Steep chop** made upwind work hard, and offwind conditions gave "near-ideal surfing". Source: https://www.sailingscuttlebutt.com/?p=123413

Sim check: in a capsize the Sunfish should settle at about 90° and stay there until the sailor applies a righting moment on the daggerboard. Any sim auto-righting is unrealistic. When it comes up it often swings head to wind and can capsize again to windward if the sheet is cleated. The low freeboard means water sweeps over the deck in chop.

### Sunfish: LIGHT

25. **Sailing a Sunfish, Small Sailboat & Light Wind** [V]
    - URL: https://www.youtube.com/watch?v=snKLjcqKJfg
    - Source: AngelsTravels
    - Check: lateen sail shape in light air (wrinkles off the gooseneck), a flat boat with the sailor to leeward, and a glassy lake surface.

26. **'60's Sunfish 'Happily Used' 5 mph sailing** [S]
    - URL: https://www.youtube.com/watch?v=6TaylfF6mIg
    - Wind: title says **5 mph** (about 4.3 kn).
    - Check: speed and flow at the low end of the range.

27. **Go-Pro Sunfish Sailing** [S]
    - URL: https://www.youtube.com/watch?v=tCNEUMd7I1Y
    - Also **Sunfish Sailing GoPro** [S]: https://www.youtube.com/watch?v=Ipx6_TBAHYM
    - Check: a mast- or deck-mounted POV, the closest match to a sim first-person camera.

### Sunfish: MODERATE

28. **Start of Race 2 at the 2023 Sunfish Worlds Miami** [V]
    - URL: https://www.youtube.com/watch?v=1dtKUHEeTsY
    - Source: Kathleen Tocke Media
    - Wind: an event day on 6-9 Dec, gusts about 12 kn, steep chop (scuttlebutt).
    - Check: hiking posture, the bow slamming into chop, and the line-up of a starting fleet.

29. **2023 Sunfish Worlds Final day** [V]
    - URL: https://www.youtube.com/watch?v=EoIm7XGVq3c
    - Source: Sunfishworlds
    - Wind: 9 Dec 2023, gusts about 12 kn.
    - Check: top-level hiking and surfing downwind.
    - Also **2023 Sunfish Worlds last race** [S]: https://www.youtube.com/watch?v=zONWOIUJlMQ

30. **Sunfish World Championships, Sarasota** [S]
    - URL: https://www.youtube.com/watch?v=ukerpvUFJNc
    - Check: a fleet on Gulf of Mexico water.

### Sunfish: HEAVY

31. **Sailing a Sunfish in 20 knot wind** [V], with a stated wind speed.
    - URL: https://www.youtube.com/watch?v=GGqbbAT5Xvc
    - Source: David Martineau
    - Wind: **20 kn** (title).
    - Check: a full-hike, overpowered boat with the sail luffed in puffs, the leeward rail and deck awash, and spray. Planing reaches.

32. **Sunfish Sailing in Heavy Winds** [V]
    - URL: https://www.youtube.com/watch?v=_DIZVO3DbDI
    - Source: PrestonHarris
    - Also **Sunfish Sailing in Heavy Winds with Collision** [S]: https://www.youtube.com/watch?v=rCXKWCLU6e8

33. **Heavy Wind Sunfish Sailing** [V]
    - URL: https://www.youtube.com/watch?v=hqVYrYxfTPc
    - Source: Boating with Billy

34. **Megan sails a Sunfish for the first time--high wind.** [S]
    - URL: https://www.youtube.com/watch?v=e6QYTWr56kY
    - Check: novice handling, with uncontrolled heel and rounding up. This is a good model for how a sim's beginner mode should look.

35. **Sunfish Sailing High Wind with SPARS ONLY.** [S]
    - URL: https://www.youtube.com/watch?v=c_H7z0xcix0
    - Check: windage-only drift and the speed under bare spars.

### Sunfish: STORM / capsize and recovery

36. **Sunfish high wind capsize** [V]
    - URL: https://www.youtube.com/watch?v=28prJEmB1tY
    - Source: planesnthings
    - Check: the capsize dynamics, either to leeward in a gust or to windward on a death roll, and the boat settling at about 90° and staying there. It does not come back up by itself.

37. **Demonstrating how to right a capsized Sunfish Sailboat** [V]
    - URL: https://www.youtube.com/watch?v=Lwokzjlcjvk
    - Source: JTColePhoto
    - Check: the full recovery sequence (swim to the daggerboard, lever it, the boat rises, the sailor climbs in). Time each step for the sim's recovery animation.

38. **Flip your Sunfish Sailboat without getting wet!** [V]
    - URL: https://www.youtube.com/watch?v=Wja6cbzthNU
    - Source: Adventures In Reach
    - Shows: a "dry capsize", where the sailor steps over the rail onto the daggerboard as the boat goes over.

39. **Capsize recovery of a Sunfish by a 7-year-old (first attempt)** [V]
    - URL: https://www.youtube.com/watch?v=5CbmkAeWZ0Y
    - Source: Bruce Liese
    - Check: how little righting force is needed. A light child can right it, so the righting moment the sim requires should be modest.

40. **Sunfish Sailing How to Avoid Capsizing Turning Turtle | Sail Safer** [V]
    - URL: https://www.youtube.com/watch?v=FkqmF-MJ47g
    - Source: Lee Montes
    - Check: the turtle mechanism and how the sail filling with water makes it worse.
    - Also **5 Cautions and Solutions when Flipping a Sunfish Sailboat** [S]: https://www.youtube.com/watch?v=vv-XaMFtOmM

---

## 3. ILCA 7 / Laser

### Published data points (ILCA/Laser)

- **Polars and heel (Day et al. 2017, "Performance prediction for sailing dinghies", Ocean Engineering, Strathclyde):** https://strathprints.strath.ac.uk/59980/1/Day_OE_2017_Performance_prediction_for_sailing_dinghies.pdf
  - Measured Laser polars exist at 9 and 12 kn TWS (Binns et al. 2002) and from an instrumented GPS boat at about 12.5 kn (Clark 2014).
  - Best upwind VMG falls at **TWA about 40-46°** in flat water. Apparent wind angle runs **about 27° at 5 kn to about 33° at 15 kn**.
  - Upwind, the boat is sailed **flat up to about 9 kn TWS**, then with a small heel.
  - Downwind in light air, the typical **windward heel is about 20°** (by the lee, "kiting"). The VPP finds the optimum heel switching abruptly at about 9.1 kn TWS.
  - The text gives no numeric speeds (they are in figures only).
- **Chalmers study:** best heel and trim of a Laser upwind at 2-5 kn of boat speed. It finds a small heel is beneficial in higher winds. https://research.chalmers.se/en/publication/234579
- **Anecdotal top speed:** 15 kn GPS on a broad reach in a "very big gust", including about 2 kn of tide (forum post): https://www.yachtsandyachting.com/FORUM/printer_friendly_posts.asp?TID=13885
- **2024 ILCA 7 Men's Worlds, Adelaide (Jan 2024):**
  - Day 1 was a gradient breeze of about **10-20 kn**: https://paris2024.sailing.org/2024/01/26/tomasgaard-draws-first-blood-on-opening-day-of-ilca-7-worlds-in-adelaide/
  - Day 3 started at **5-7 kn and built to 12-15 kn**: https://ilcasailing.org/2024-ilca-7-mens-world-championships-day-3/
  - Finals Day 1 (30 Jan) was a strong sea breeze, "proper windy", with **steep swells**: https://paris2024.sailing.org/2024/01/30/podium-begins-to-take-shape-as-the-top-sailors-battle-adelaides-windy-conditions/

### ILCA: LIGHT

41. **Laser Sailing - Roll Tack with Slow Motion [HD]** [V]
    - URL: https://www.youtube.com/watch?v=kQbf-1fyDH8
    - Source: LaserXD
    - Check: the roll-tack sequence (heel to windward, then the flattening flick) and the speed retained. Slow motion helps for timing the animation.

42. **ILCA (LASER) SAILING IN LIGHT/MEDIUM WIND with British Sailing Team's Sam Whaley & Hannah Snellgrove** [V]
    - URL: https://www.youtube.com/watch?v=n9uQFyg2F4A
    - Source: Dinghy Racing Channel
    - Check: sailor positioned forward and to leeward, induced leeward heel upwind, and kiting downwind at about 20° windward heel (matches Day et al.).
    - Also **3 roll tacks in 25 seconds- 3knts wind** [S] (Short, **3 kn** stated): https://www.youtube.com/shorts/aM71roUPHqo

### ILCA: MODERATE

43. **Day 3 Highlights - 2024 ILCA 7 Men's World Championship AUSTRALIA, Adelaide** [V]
    - URL: https://www.youtube.com/watch?v=2vTuqRYPuSc
    - Source: jonemmettsailing
    - Wind: **5-7 kn building to 12-15 kn** (ILCA report), 28 Jan 2024.
    - Check: the transition from flat sailing to full hiking, all in one clip.

44. **Day 1 Highlights - 2024 ILCA 7 Men's World Championship AUSTRALIA, Adelaide** [V]
    - URL: https://www.youtube.com/watch?v=oKw2KXuMy-g
    - Source: jonemmettsailing
    - Wind: **10-20 kn gradient** breeze, about 26 Jan 2024.
    - Check: straddles the MODERATE and HEAVY buckets. Look at hiking angle, vang and cunningham depower (flattened sail with a twisted leech), and the hull slapping in waves.

45. **Boom Cam of Brett Beyer working the ILCA/Laser downwind** [V]
    - URL: https://www.youtube.com/watch?v=j8YkrQfRuHA
    - Source: Andy Rice
    - Check: a **boom-mounted camera** view of the steering-by-heel downwind technique, the timing of sheet pumps, and catching waves.

### ILCA: HEAVY

46. **Laser Sailing like Olympians || Upwind in Windy Conditions** [V]
    - URL: https://www.youtube.com/watch?v=Xpm-o09FLGk
    - Source: Dan Self Sailing
    - Check: the full-hike body angle, the mainsheet eased and pulled in through waves, the bow lifting over chop, and a flat boat at heel under 10°.

47. **Laser Sailing Like the Pros - Surfing Downwind** [V]
    - URL: https://www.youtube.com/watch?v=LYSJXsbOVv8
    - Source: Dan Self Sailing
    - Check: **planing and surfing downwind**. Look for the bow lifting, the wake and spray signature at planing speed, and S-turns down the waves.
    - Also **DOWNWIND TECHNIQUE: ILCA (LASER) TECHNIQUE TIPS - British Sailing Team** [S]: https://www.youtube.com/watch?v=i28JBeWFtRM

48. **Laser sailing 25+knots** [V]
    - URL: https://www.youtube.com/watch?v=6o5kPepxvsI
    - Source: Haul Parteck
    - Wind: **25+ kn** (title). This is the HEAVY/STORM edge.

### ILCA: STORM / capsize

49. **Extreme Laser downwind sailing +30 knots - SYLT** [V]
    - URL: https://www.youtube.com/watch?v=OA-mOpjef2E
    - Source: Swedish Youth Laser Team
    - Wind: **30+ kn** (title).
    - Check: top-end planing, nosedives, and the edge of control. Likely includes wipeouts.

50. **Fast Laser Sailing with a downwind double death roll! (GOPRO HD)** [V]
    - URL: https://www.youtube.com/watch?v=M5H9aI7N2hM
    - Source: pipercub37
    - Check: the **death roll** dynamics (rhythmic rolling builds up and the boat capsizes to windward on a run). This is a key failure mode for the sim.

51. **22 Apr 12 - 20+mph downwind deathroll** [V]
    - URL: https://www.youtube.com/watch?v=L-rkD4NMs8c
    - Source: staRgraZer
    - Wind: **20+ mph** (about 17+ kn), with a stated condition.
    - Also **ILCA Death Roll** [S] (Short): https://www.youtube.com/shorts/7LoxjKAxF7A

52. **Laser sailing - dry capsize recovery** [V]
    - URL: https://www.youtube.com/watch?v=yX57m4RP8bo
    - Source: Don Silva
    - Check: a Laser also does **not self-right**. It lies on its side, and the sailor steps over onto the centreboard. Capture the timing.
    - Also **Capsized? Dont waste time and energy righting the boat the wrong way.** [S]: https://www.youtube.com/watch?v=T7lUaEafLv8

---

## 4. Catalina 22

### Published data points (Catalina 22)

- Hull speed 5.9 kn (LWL 19.3 ft). Displacement 2,250 lb. Ballast 550 lb, so the ballast ratio is **24.4%**, much more tender than the J/22. SA/D 19.2, PHRF 270.
- Wind guide from the same site: ghosting at 0-6 kn, sweet spot 6-16 kn, **reef at 16-24 kn**, heavy weather above 24 kn.
- Source: https://keelindex.com/boat/catalina-22/performance
- Sim check: compared with a J/22 in the same breeze, the Catalina 22 should heel more and earlier, round up sooner, and be slower (about 90 s/nm slower by PHRF).

### Catalina 22: LIGHT / MODERATE

53. **Playing the Puffs - Sailing Upwind in Gusty Air -- Catalina 22 - Jim's Little Boat** [V]
    - URL: https://www.youtube.com/watch?v=MiDIk3l19Po
    - Source: Jim's Little Boat
    - Check: the heel response to puffs, easing the main, and the boat feathering up. Gives a puff-to-heel transient time constant.
    - The same channel has an instructional series: **Single-hand Your Small Sailboat -- Catalina 22** [S]: https://www.youtube.com/watch?v=0BP_M5rsmGY

54. **Catalina 22 Racing | Sisters with Sails** [V]
    - URL: https://www.youtube.com/watch?v=XVcPAIoaaAI
    - Source: Kostas Lazanas
    - Check: racing trim on a cruiser-racer, with crew on the rail.

55. **How to sail a small sailboat (on our Catalina 22)** [S]
    - URL: https://www.youtube.com/watch?v=uNW54RFtmew
    - Also **Sailing my Catalina 22 with Laura on Lake Michigan** [S]: https://www.youtube.com/watch?v=MBd20cUAl3o

### Catalina 22: HEAVY

56. **Sailing in strong wind on our Catalina 22** [V]
    - URL: https://www.youtube.com/watch?v=3cqosurPe3Y
    - Source: Sailing Okaliptüs
    - Check: heel likely 20-30°, a flogging jib, weather helm, and spray.

57. **Catalina 22 heeling in gusty winds #2** [V]
    - URL: https://www.youtube.com/watch?v=nswepMFtfj4
    - Source: Robert Forrester
    - Same series: #1 [S] https://www.youtube.com/watch?v=HhrIOcKLHjQ and #5 [S] https://www.youtube.com/watch?v=OmrfFR6EpvU
    - Check: heel angle per gust. These are short clips useful for measuring the angle (look for the horizon in frame).

58. **reefed the main and jib.** [S]
    - URL: https://www.youtube.com/watch?v=59t3FjDuEZo
    - Appeared in a Catalina 22 search, but the boat type is not confirmed.
    - Related, a different boat: **Sailing a Catalina Capri 22 with two reefs and a storm jib** [S]. The Capri 22 is a fin-keel sport cruiser, not a Catalina 22. Its oEmbed returned 401, so the video may be private or have embedding disabled: https://www.youtube.com/watch?v=2CM8ZPfDzdk

### Catalina 22: STORM

59. **Catalina 22; gusts over 50, Main Destroyed.** [V]
    - URL: https://www.youtube.com/watch?v=l7d1WP6pQ7A
    - Source: "Catalina 22"
    - Wind: **gusts over 50** (units not given in the title, probably mph or kn).
    - Check: sail failure (a torn, flogging main), extreme heel, and wind-blown spray and spindrift on the water surface. This is the storm reference for small keelboats.

---

## 5. Catalina 30

### Published data points (Catalina 30)

- Hull speed 6.7 kn (LWL 25 ft). Displacement 10,200 lb. Ballast ratio 41.2%. SA/D about 15. D/L 291. PHRF 180.
- VPP polar (site-listed; I did not verify where it came from), at TWS 6/10/14/20 kn:
  - Best upwind VMG speed: 3.1 / 4.1 / 4.3 / 4.3 kn
  - 90° TWA: 5.1 / 6.4 / 6.8 / 7.2 kn
  - 120° TWA: 4.9 / 6.4 / 7.0 / 7.9 kn
  - At 14 kn: best upwind TWA 41°, best downwind TWA 160°, top speed 7.1 kn at 110°
  - Source: https://keelindex.com/boat/catalina-30/performance
- **Owner-reported heel vs wind (C30, fully crewed, close-hauled):**

  | True wind | Apparent wind | Sails | Heel |
  |---|---|---|---|
  | 6 kn | 9 kn | full | **4°** |
  | 10 kn | 13-14 kn | full | **about 15°** |
  | 12 kn | 16 kn | full | **17°** |
  | 16 kn | 19-20 kn | full | **21°** |
  | 20 kn | 23 kn | 1st reef | **22°** |
  | 30+ kn | not stated | 2 reefs, 100% jib | **20-25°** |

  The owner advises reefing above 20 kn true wind to keep heel under 25°. Short-handed crews should reef sooner. Too much heel makes the rudder "a brake". Source: https://forums.sailboatowners.com/threads/max-optimum-angle-of-heel-for-catalina-30.80892/latest. **This is the best heel-calibration table found.**

### Catalina 30: LIGHT / MODERATE (cruising)

60. **Catalina 30 Sailing past Silver Lake on Lake Michigan** [V]
    - URL: https://www.youtube.com/watch?v=fcCoBgivdHI
    - Source: Saltless Shakedowns
    - Check: cruising pace on a big lake.

61. **SOLO SAILING HOME from LITTLE FISHERMANS COVE on a CATALINA 30** [V]
    - URL: https://www.youtube.com/watch?v=1YiC0MdPtKI
    - Source: Sailing Solé (Catalina Island, CA)
    - Check: a single-hander's cockpit view.

62. **Coastal Cruising on a Catalina 30 | Sailing Fujin S1E9** [V]
    - URL: https://www.youtube.com/watch?v=F-9B8ltKqTM
    - Source: Sailing Fujin
    - Also **Sailing Catalina 30 with Autohelm 4000** [S]: https://www.youtube.com/watch?v=_d_NHuJEWn8
    - Also **BOAT LIFE: Day Sail and fishing on our Catalina 30 // Pacific Northwest // Ep. 48** [S]: https://www.youtube.com/watch?v=rzwLW_30IzU

63. **Full Moon Regatta THE BEST Sailing Race you've Never Heard of! Racing a Catalina 30 | A&J Sailing** [V]
    - URL: https://www.youtube.com/watch?v=Qvx32qiDrWc
    - Source: Allison & James
    - Also a season racing compilation, listed in search as "GAMBIT - A Season Racing a Catalina 30" [V]. Its live title is "2020 Season: Set to Tchaikovsky's 1812 Overture (June 3 - Oct. 14)", channel Marshall Lystra: https://www.youtube.com/watch?v=Vr8zQK-IBBs
    - Also **Sailing Tom's Catalina 30 Tall Rig** [S]: https://www.youtube.com/watch?v=S_lsVZoqudQ

### Catalina 30: HEAVY / STORM

64. **Offshore on a Catalina 30 Sailboat** [V]
    - URL: https://www.youtube.com/watch?v=3wYxyxO3kFM
    - Source: Wicked Salty
    - Check: ocean swell, pitching and rolling motion, and probably a reefed main.
    - No Catalina 30 clip with stated 20+ kn wind and a confirmed title was found. Closest substitutes from similar 30-38 ft production cruisers:
      - **45 Seconds of SAILING in 30 Knots of Wind in a Catalina 387** [S]: https://www.youtube.com/watch?v=BEBb2L6t0SE
      - **SQUALL sailing thru Line Squall storm on Lake Michigan on Tartan 30** [S], a lake squall that matches a Texas-lake storm scenario: https://www.youtube.com/watch?v=Hl5NYDbSygc
      - **Sailing Into a 30 Knot Squall: 4K 360 - Eastbound and Up** [S], a 360° camera: https://www.youtube.com/watch?v=Z-gFBIFtr90
      - **Heavy Weather Sailing in Force 6 - 8. Reefing, Heaving-To & Storm Tactics** [S]: https://www.youtube.com/watch?v=BDMxhuxaaHI
    - Sim check: with a first reef at about 20 kn, heel should stay at 20-25° (owner table). The 41% ballast ratio means it should stiffen and resist knockdown. A squall gust front should show a dark ruffled band on the water and then a whitecap field.

---

## Gaps and recommendations

- **Texas J/22 footage is the main gap.** Search found no YouTube J/22 clips from Lake Ray Hubbard, RCYC, CSC, AYC or FWBC. Ways to fill it:
  1. Browse the RCYC channel (https://www.youtube.com/@rushcreekyachtclub7644).
  2. Check the International J/22 Class Facebook page, which j22.org says carries the 2024 Worlds videos and photos.
  3. Ask the Texas fleets (FWBC runs a 10-boat J/22 fleet; RCYC hosted the 2025 Midwinters).
  4. Use the J/24 Austin YC clip as a proxy for the look of Lake Travis.
- No J/22 broach or knockdown clip with a confirmed title. The *Geronimo* Jamaica clip (#22) is the best candidate. The Spinsheet article links a 30+ kn run whose URL I could not extract.
- Wind speeds came from regatta reports for about 10 clips: the 2024 J/22 Worlds days, the 2023 Sunfish Worlds and the 2024 ILCA 7 Worlds. Others carry the speed in the title (Sunfish 20 kn, Laser 25+ and 30+, deathroll 20+ mph, Sunfish 5 mph, roll tacks 3 kn). The rest are unquantified.
- Strongest quantitative references for calibration:
  1. The owner-reported Catalina 30 heel table.
  2. The keelindex J/22 and C30 polar tables.
  3. Day et al. 2017 for Laser heel and AWA behavior.
  4. The Quantum J/22 tuning wind bands.
