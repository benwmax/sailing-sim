#pragma once

#include "SailingPhysicsApi.h"
#include "SailingMath.h"
#include <cstdint>

namespace Sailing
{
	struct FWindParams
	{
		double SpeedKnots = 10.0;        // true wind speed at the 10 m reference height (how polars quote it)
		double FromDegrees = 0.0;        // direction the wind blows FROM, in the world XY plane (0 = from +X)
		double RoughnessLength = 0.0002; // m, open water, for the log height profile
		double GustIntensity = 0.0;      // gust/lull amplitude as a fraction of mean speed (0.15 to 0.3 is a typical lake day)
		double ShiftDegrees = 0.0;       // typical size of oscillating shifts
		double GustLengthMeters = 250.0; // spacing of gust patches, which drift downwind at the mean speed
		double ShiftPeriodSeconds = 90.0;
		uint32_t Seed = 1;               // the same seed always gives the same gusts and shifts
	};

	/**
	 * True wind field: mean speed and direction, logarithmic height gradient, and seeded gusts, lulls and
	 * shifts. Gust patches are frozen in the flow and advected downwind, so they reach a boat from upwind
	 * the way they do on the water.
	 */
	class SAILINGPHYSICS_API FWindField
	{
	public:
		explicit FWindField(const FWindParams& InParams = FWindParams());

		/** Air velocity (where the air is going, m/s) at a world position and time. */
		Vec3 VelocityAt(const Vec3& WorldPos, double TimeSeconds) const;

		/** Mean speed at a height, before gusts. */
		double MeanSpeedAtHeight(double HeightMeters) const;

		/** Gust factor (1 = mean) at a world position and time. */
		double GustFactorAt(const Vec3& WorldPos, double TimeSeconds) const;

		/** Direction shift (radians, positive = veer toward +Y) at a time. */
		double ShiftAt(const Vec3& WorldPos, double TimeSeconds) const;

		const FWindParams& GetParams() const { return Params; }
		void SetParams(const FWindParams& InParams);

	private:
		double Noise(double S, int Octave) const;

		FWindParams Params;
		double Phases[8];
		double MeanSpeed10 = 0.0; // m/s
		Vec3 DownwindDir;         // unit vector the air travels along
	};
}
