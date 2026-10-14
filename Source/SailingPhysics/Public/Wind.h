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
	 * A thunderstorm outflow (gust front): a line moving across the water. Behind it the wind blows from the
	 * storm, much harder and gustier. It is the same field the sails feel, so it shows on the water (cat's paws,
	 * a dark line) before it reaches the boat.
	 */
	struct SAILINGPHYSICS_API FGustFront
	{
		bool bActive = false;
		double StartX = 0.0, StartY = 0.0; // a point on the front line at StartTime (world, m)
		double MoveDegrees = 0.0;          // direction the front travels toward (same angle convention as headings)
		double SpeedMs = 12.0;             // how fast the front moves
		double StartTime = 0.0;            // s
		double OutflowKnots = 28.0;        // mean wind behind the front (10 m)
		double OutflowFromDegrees = 290.0;
		double OutflowGustIntensity = 0.25;
		double LeadingEdgeMeters = 120.0;  // width of the transition; the strongest gusts sit just behind the edge
		double DecayStartTime = 1e9;       // s, outflow begins to weaken
		double DecaySeconds = 120.0;

		/** Signed distance from a point to the front line (m): positive = still ahead of the front (old wind). */
		double DistanceAhead(double X, double Y, double T) const;
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

		/**
		 * Changes speed, direction, gusts or shifts at time T without making the gust pattern jump: the pattern's
		 * travelled distance is carried over. Use this when the weather changes the wind during play.
		 */
		void SetParamsAt(const FWindParams& InParams, double T);

		void SetFront(const FGustFront& InFront) { Front = InFront; }
		/** Lee of land and trees (optional): slows and roughens the wind near the shore. */
		void SetShelter(const class FShelterMap* InShelter) { Shelter = InShelter; }
		const FGustFront& GetFront() const { return Front; }

		/**
		 * How ruffled the water looks at a point: local 10 m wind speed relative to 8 m/s (about 15 kn). Cat's paws
		 * and the gust front are this value on the water. Same source as the sails' wind.
		 */
		double SurfaceRoughnessAt(double X, double Y, double TimeSeconds) const;
		/**
		 * The same scale for the mean wind alone (no gusts, lulls or lee; a gust front's outflow where it has passed):
		 * what the water looks like on average there, the value the cat's-paw map fades to at its edge.
		 */
		double MeanSurfaceRoughnessAt(double X, double Y, double TimeSeconds) const;

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
		double AdvectionOffset = 0.0; // m the gust pattern had travelled at AdvectionTime
		double AdvectionTime = 0.0;
		FGustFront Front;
		const class FShelterMap* Shelter = nullptr;

		double Advected(double TimeSeconds) const { return AdvectionOffset + MeanSpeed10 * (TimeSeconds - AdvectionTime); }
	};
}
