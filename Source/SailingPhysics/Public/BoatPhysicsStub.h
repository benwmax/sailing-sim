#pragma once

#include "CoreMinimal.h"

namespace Sailing
{
	constexpr double WaterDensity = 1000.0;  // kg/m^3, fresh water (Lake Ray Roberts)
	constexpr double Gravity = 9.80665;      // m/s^2
	constexpr double MetersPerFoot = 0.3048;
	constexpr double MetersPerSecondPerKnot = 0.514444;

	/** Classic displacement hull-speed rule: knots = 1.34 * sqrt(LWL in feet). */
	SAILINGPHYSICS_API double HullSpeedKnots(double WaterlineLengthMeters);

	/**
	 * Boat particulars. Defaults are the J/22 (class figures, to be checked against
	 * builder data in Phase 2): LOA 22 ft 6 in, 1,790 lb.
	 */
	struct SAILINGPHYSICS_API FBoatParams
	{
		double LengthOverall = 6.86;     // m (22 ft 6 in)
		double WaterlineLength = 5.79;   // m (19 ft)
		double Beam = 2.44;              // m (8 ft)
		double Draft = 1.16;             // m (3 ft 10 in, fixed keel)
		double Mass = 812.0;             // kg (1,790 lb)
		double WaterplaneArea = 8.3;     // m^2, estimate: Cwp 0.68 * LWL * BWL
		double MetacentricHeight = 0.9;  // m, GM estimate for small heel angles
		double LongitudinalGM = 6.0;     // m, GML estimate
		double RollGyradius = 0.85;      // m, about 0.35 * beam
		double PitchGyradius = 1.7;      // m, about 0.25 * LOA
		double AddedMassRatio = 0.5;     // heave / roll / pitch added mass as a fraction of rigid-body inertia
		double HeaveDampingRatio = 0.35;
		double RollDampingRatio = 0.15;
		double PitchDampingRatio = 0.4;

		// Phase 0 placeholder propulsion and steering, replaced by sails, foils and hull resistance in Phase 1.
		double MaxThrust = 600.0;        // N, a small outboard
		double LinearDrag = 40.0;        // N per m/s
		double QuadraticDrag = 80.0;     // N per (m/s)^2
		double MaxRudderAngle = 0.52;    // rad (30 degrees)
		double YawResponseTime = 0.6;    // s
		double TurnHeelCoefficient = 0.35; // m, lever arm for heel from turning (centripetal force * this)

		double Displacement() const { return Mass / WaterDensity; } // m^3
	};

	struct FBoatControls
	{
		double Rudder = 0.0;   // -1 (hard to port) .. +1 (hard to starboard)
		double Throttle = 0.0; // -1 .. +1, placeholder outboard
	};

	/**
	 * Boat state in SI units. World frame matches Unreal's axes (X forward, Y right, Z up) but in meters.
	 * Angles in radians: Heading is yaw (positive turns from +X toward +Y), Heel is roll (positive = starboard side down).
	 */
	struct FBoatState
	{
		double X = 0.0, Y = 0.0, Z = 0.0; // Z = height of the design waterline above the water surface
		double Heading = 0.0, Heel = 0.0, Pitch = 0.0;
		double Surge = 0.0;      // m/s along the boat's heading
		double HeaveRate = 0.0;  // m/s
		double YawRate = 0.0;    // rad/s
		double RollRate = 0.0;   // rad/s
		double PitchRate = 0.0;  // rad/s
	};

	/**
	 * Phase 0 stub: flat-water hydrostatics (heave, heel and pitch as damped springs about equilibrium)
	 * plus a placeholder motor and rudder. Phase 1 replaces this with the force-based 6-DOF model
	 * (sails, foils, hull resistance, buoyancy sampled against the wave surface).
	 */
	class SAILINGPHYSICS_API FBoatPhysicsStub
	{
	public:
		explicit FBoatPhysicsStub(const FBoatParams& InParams = FBoatParams()) : Params(InParams) {}

		/** Advances one fixed step. WaterSurfaceZ is the flat water height in meters. */
		void Step(double Dt, const FBoatControls& Controls, double WaterSurfaceZ = 0.0);

		FBoatState State;
		const FBoatParams& GetParams() const { return Params; }

		/** Undamped natural periods, for tests and tuning. */
		double HeavePeriod() const;
		double RollPeriod() const;

	private:
		FBoatParams Params;
	};
}
