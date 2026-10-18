#pragma once

#include "SailingPhysicsApi.h"

namespace Sailing
{
	/**
	 * W5b: a microburst, Vicroy's analytic axisymmetric model (NASA TM-104053, 1991): the refinement of Oseguera and
	 * Bowles (NASA TM-100632, 1988) that flight simulators use for wind shear. Steady, it satisfies mass continuity in
	 * cylindrical coordinates; the outflow peaks at PeakOutflowMs on the ring r = PeakRadiusM at PeakHeightM above the
	 * surface, the downdraft is strongest at the centre and an updraft ring sits outside r = PeakRadiusM 2^(1/(2 alpha)).
	 *   u_r = lambda r / 2 [e^(c1 z/zm) - e^(c2 z/zm)] e^((2 - (r/rp)^(2 alpha)) / (2 alpha))
	 *   w   = -lambda {zm/c1 [e^(c1 z/zm) - 1] - zm/c2 [e^(c2 z/zm) - 1]} [1 - (r/rp)^(2 alpha) / 2] e^(...same...)
	 *   lambda = 2 um / (rp (e^c1 - e^c2) e^(1/(2 alpha))), c1 = -0.22, c2 = -2.75 (z* over epsilon = 12.5), alpha = 2.
	 */
	struct SAILINGPHYSICS_API FMicroburst
	{
		// One per line: MSVC rejects a second declarator in a static constexpr member of a dllexport class (C2487).
		static constexpr double C1 = -0.22;
		static constexpr double C2 = -2.75;
		double PeakRadiusM = 1200.0; // rp: radius of the strongest outflow (Fujita: a microburst is under 4 km across)
		double PeakHeightM = 50.0;   // zm: height of the strongest outflow (JAWS: 30 to 100 m)
		double PeakOutflowMs = 20.0; // um
		double Alpha = 2.0;          // radial shaping (2 recommended by Vicroy)

		double Lambda() const;
		/** Air velocity (m/s) at a point relative to the burst's centre on the surface: radial outflow and vertical (up +). */
		void At(double Dx, double Dy, double Z, double& OutU, double& OutV, double& OutW) const;
		/** Radius (m) beyond which the air rises: the ring the outflow rolls up into. */
		double UpdraftRadius() const;
	};

	/**
	 * W5b: the storm's cold pool as a density current (Benjamin 1968; Charba 1974, Wakimoto 1982 for thunderstorm
	 * outflows). The front moves at k sqrt(g h dT / T) relative to the air ahead (k about 0.75), plus part of the ambient
	 * wind along its track; the wind behind the head is about 1.2 times the front's speed over the ground.
	 */
	struct SAILINGPHYSICS_API FColdPool
	{
		static constexpr double kFroude = 0.75;       // observed range 0.7 to 0.8
		static constexpr double kAmbientShare = 0.6;  // of the ambient wind along the track that carries the front
		static constexpr double kOutflowRatio = 1.2;  // 10 m wind behind the head over the front's speed

		/** Front speed over the ground (m/s): cold pool dT (C), depth (m), air ahead (C), ambient wind along the track (m/s). */
		static double FrontSpeed(double DeltaC, double DepthM, double AirC, double AmbientAlongMs);
	};

	/**
	 * W5b: where the storm rains. Distances along the front's track, as FGustFront::DistanceAhead (m, positive = ahead of
	 * the outflow), the cloud material's frame. The rain core starts FStormShape::CoreBehindM behind the front aloft; near
	 * the water the outflow carries the falling rain forward into a rain foot, so the curtain's leading edge slants
	 * forward toward the surface. Heaviest just inside the leading edge, tapering back through the core into lighter
	 * trailing rain, and along the front to the storm's lateral extent (the weather map's storm channel).
	 */
	struct SAILINGPHYSICS_API FStormRain
	{
		static constexpr double FootReachM = 300.0;   // how far ahead of the core the rain reaches at the water
		static constexpr double FootHeightM = 180.0;  // e-folding height of the foot
		static constexpr double EdgeWidthM = 250.0;   // the curtain's edge, soft over this width
		static constexpr double CoreLengthM = 6000.0; // heavy rain this far back from the edge
		static constexpr double TrailLengthM = 14000.0; // light trailing rain to here
		static constexpr double PeakMmPerHour = 80.0; // the core's heaviest (a strong Texas storm: 50 to 100 mm/h)
		static constexpr double TrailMmPerHour = 6.0;

		/** Leading edge of the rain (m ahead of the front; negative = behind it) at an altitude. */
		static double LeadingEdge(double AltitudeM);
		/** Rain rate (mm/h) at a distance ahead of the front, altitude and position along the front (m from its centre). */
		static double RateAt(double DistanceAheadM, double AltitudeM, double AlongFrontM);
		/** The rain's share of the storm's lateral extent at a point along the front (1 inside, 0 beyond 20 km). */
		static double LateralMask(double AlongFrontM);
		/** The game's rain amount, 0..1 (1 = a downpour, 50 mm/h and over). */
		static double Amount(double MmPerHour);
	};

	/**
	 * Prologue step 4: a squall line in a gale (the mistral's), not a thunderstorm: a band of heavier rain riding just
	 * behind its own small gust front, over the day's light rain. Distances as FStormRain's (FGustFront::DistanceAhead, m,
	 * positive = ahead of the front). No anvil, no core, no microburst: the shower clouds of a cold northerly are a few
	 * kilometres deep, and their rain falls straight from the deck (the outflow is the gale itself, a little harder).
	 * Rates: the moderate showers of a mistral day on the Provence coast (Meteo-France: 5 to 15 mm/h in the line, 1 to 2
	 * between, in the 1 h records of its winter and spring days).
	 */
	struct SAILINGPHYSICS_API FSquallLine
	{
		double PeakMmPerHour = 12.0;   // just inside the edge
		double BandLengthM = 1500.0;   // the heavy band, behind the edge; it eases to the day's rain over as much again
		double EdgeWidthM = 200.0;
		double LeadM = 80.0;           // the rain's edge sits this far ahead of the wind's (it falls through the outflow's head)

		/** The line's own rain (mm/h, on top of the day's) at a distance ahead of the front. */
		double RateAt(double DistanceAheadM) const;
		/** How far into the line a point is (0 ahead of it, 1 in its heavy band, easing behind): its gloom and its haze. */
		double Inside(double DistanceAheadM) const;
	};
}
