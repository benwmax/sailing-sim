#pragma once

#include "SailingPhysicsApi.h"
#include "SailingMath.h"

namespace Sailing
{
	/** A keel or rudder as a finite wing, standing vertically in the boat's frame. */
	struct FFoilParams
	{
		Vec3 Center;                // body-frame center of pressure (m)
		double Area = 0.5;          // planform area (m^2)
		double Chord = 0.5;         // mean chord (m)
		double EffectiveAspectRatio = 2.0; // geometric AR doubled where the hull acts as an end plate
		double StallAngleDeg = 14.0;
		double ProfileDrag = 0.009; // section drag at zero lift
		double OswaldEfficiency = 0.9;

		/** Lift slope per radian for a finite wing (Helmbold, good for low aspect ratios). */
		double LiftSlope() const
		{
			const double A = EffectiveAspectRatio;
			return 2.0 * kPi * A / (2.0 + std::sqrt(A * A + 4.0));
		}
	};

	struct FFoilResult
	{
		Vec3 Force;              // body frame, N
		double AngleOfAttack = 0.0; // rad, signed
		double LiftCoefficient = 0.0;
		double DragCoefficient = 0.0;
		bool bStalled = false;
	};

	/**
	 * Forces on a foil from the fluid velocity relative to it (body frame; only the X and Y components
	 * are used). ChordDir points from leading edge to trailing edge in the body XY plane.
	 * LiftFactor < 1 models ventilation when the foil nears the surface.
	 */
	SAILINGPHYSICS_API FFoilResult ComputeFoil(const FFoilParams& Foil, const Vec3& FlowBody, const Vec3& ChordDir, double Density, double LiftFactor = 1.0);

	/** Lift and drag coefficients against angle of attack for a symmetric foil, with stall. */
	SAILINGPHYSICS_API void FoilCoefficients(const FFoilParams& Foil, double Alpha, double& OutCL, double& OutCD, bool& bOutStalled);
}
