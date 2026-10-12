#pragma once

#include "SailingPhysicsApi.h"
#include "AutoTrim.h"
#include <vector>

namespace Sailing
{
	/**
	 * J/22 reference polar for the Phase 1 validation gate.
	 *
	 * Source: ORC VPP polar for the J/22 one-design, median of 13 ORC certificates, as tabulated by keelindex.com
	 * (https://keelindex.com/boat/j-22/performance), cross-checked against the ORC 2021 J/22 One Design certificate
	 * (https://data.orc.org/public/od/2021/j22.od.html): beat angles 43.5 / 40.9 / 38.6 deg and beat VMG
	 * 2.85 / 3.87 / 4.20 kn at 6 / 10 / 14 kn. Speeds are at 10 m true wind.
	 *
	 * Three adjustments, each labeled in the table:
	 *  - 15 kn is interpolated between the published 14 and 20 kn columns (one sixth of the way).
	 *  - Beat speed = beat VMG / cos(beat angle); run speed = run VMG / cos(8 deg) at the 172 deg run angle.
	 *  - Downwind (110 deg and deeper) ORC assumes a spinnaker; Phase 1 has main and jib only. Those points are an
	 *    APPROXIMATE non-spinnaker polar: ORC speed x 0.84 / 0.89 / 0.91 at 6 / 10 / 15 kn. The 10 kn factor comes
	 *    from ORC's J/22 non-spinnaker rating (GPH 781.0 s/nm against 736.1 with spinnaker: about 6 percent slower
	 *    over a mixed course, all of it on the downwind half, so about 11 percent slower downwind). The light- and
	 *    heavy-air factors are judgment: a spinnaker adds the most in light air. Replace these points with a real
	 *    non-spinnaker certificate or on-the-water data when available.
	 */
	struct FPolarPoint
	{
		double TrueWindKnots;
		double TrueWindAngleDeg;
		double BoatSpeedKnots;
		const char* Note;
		bool bSpinnaker = false; // sailed with the spinnaker (or gennaker / screacher) up
		// Allowed error, set by how good the source is: 10% for ORC certificates and polars anchored on measured
		// speeds, 15% for handicap-scaled estimates, 20% for hand-built estimates (the research's own uncertainty).
		double Tolerance = 0.10;
	};

	SAILINGPHYSICS_API const std::vector<FPolarPoint>& J22ReferencePolar();

	/** Reference polar for any boat in the fleet (the J/22's adds its spinnaker points). Sources in docs/phase-4/fleet-data.json. */
	SAILINGPHYSICS_API const std::vector<FPolarPoint>& FleetReferencePolar(EBoatType Type);

	/** Result of sailing the boat steadily at one point. */
	struct FSteadyResult
	{
		double BoatSpeedKnots = 0.0;
		double HeelDeg = 0.0;
		double LeewayDeg = 0.0;
		double RudderDeg = 0.0;   // positive = weather helm (rudder holding the bow off the wind)
		double HelmForceN = 0.0;
		double TrueWindAngleDeg = 0.0;
		double SpeedStdDev = 0.0;
		FAutoTrimSettings Trim;
	};

	/**
	 * Sails the J/22 at a fixed true wind speed and angle with the autopilot and auto-trim, lets it settle,
	 * and averages the last part. Tries a few trim settings and keeps the fastest (the polar is optimal trim).
	 */
	SAILINGPHYSICS_API FSteadyResult SailSteady(double TrueWindKnots, double TrueWindAngleDeg, const FBoatConfig& Config = FBoatConfig::J22(), bool bSearchTrim = true, bool bSpinnaker = false);

	/**
	 * Lake chop used for the polar: ORC's polars assume a moderate sea state, so the boat is sailed in the
	 * fetch-limited waves for this fetch (about 0.11 / 0.19 / 0.28 m significant height at 6 / 10 / 15 kn).
	 */
	constexpr double kPolarFetchMeters = 5000.0;

	/** One run with fixed trim settings. */
	SAILINGPHYSICS_API FSteadyResult SailSteadyWith(double TrueWindKnots, double TrueWindAngleDeg, const FAutoTrimSettings& Trim, const FBoatConfig& Config, double SettleSeconds = 40.0, double AverageSeconds = 15.0, bool bSpinnaker = false);
}
