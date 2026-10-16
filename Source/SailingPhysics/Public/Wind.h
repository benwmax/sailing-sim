#pragma once

#include "SailingPhysicsApi.h"
#include "SailingMath.h"
#include "Storm.h"
#include <cstdint>
#include <limits>
#include <string>
#include <vector>

namespace Sailing
{
	struct FWindParams
	{
		double SpeedKnots = 10.0;        // true wind speed at the 10 m reference height (how polars quote it)
		double FromDegrees = 0.0;        // direction the wind blows FROM, in the world XY plane (0 = from +X)
		double RoughnessLength = 0.0002; // m, open water, for the log height profile
		/**
		 * Gustiness at 10 m as a fraction of the mean speed. With PuffIntensity unset (< 0) it is the whole field's standard
		 * deviation, split between the convective puffs and the fine (Mann) turbulence by the stability. With PuffIntensity
		 * set (the weather, from the station calibration in WindClimate.h) it is the fine turbulence's alone: the 5-second
		 * gusts and the gust factor.
		 */
		double GustIntensity = 0.0;
		double PuffIntensity = -1.0;     // the puffs: spread of the 2-minute mean around the half-hour mean (stations' measure)
		double ShiftDegrees = 0.0;       // typical size of the slow oscillating shifts
		double ShiftPeriodSeconds = 300.0; // their period as they pass a fixed point
		double PersistentShiftDegrees = 0.0; // a slow persistent swing (veer + / back -) over about half an hour
		// W1: the day's air (convective puffs, stability).
		double AirMinusWaterC = 0.0;     // air minus water temperature: < 0 cold over warm (gusty, shifty), > 0 steady
		double MixedLayerMeters = 1000.0; // depth of the convective boundary layer: puffs are about 0.6 of it across
		double PuffIntervalSeconds = 240.0; // typical time between puffs at a point (station calibration)
		/**
		 * The air the station calibration (PuffIntensity) was measured in: the month and hour's normal air minus water and
		 * mixed layer. The stations' spread already carries the season's stability, so the puffs scale only by how far the
		 * day's air departs from it (a front's cold air, a real day). Unset (NaN): by the stability alone, as before.
		 */
		double ClimateAirMinusWaterC = std::numeric_limits<double>::quiet_NaN();
		double ClimateMixedLayerMeters = 1000.0;
		double PuffVeerDegrees = 7.0;    // a puff veers by about this; lulls back
		double PuffFanDegrees = 20.0;    // across a puff the wind turns this much outward on each side
		/**
		 * Share of the puffs' variance carried by the kilometre-scale cells (lulls and puffs 2 to 5 km across, the size of
		 * the convective cells: the W6 LES pilot puts about two thirds of the gust energy there); the smaller puffs carry the
		 * rest and are stronger inside the big puffs than in the lulls. 0 = the W1 field (one scale).
		 */
		double CellShare = 0.65;
		uint32_t Seed = 1;               // the same seed always gives the same gusts and shifts
	};

	/**
	 * A thunderstorm outflow (gust front): a line moving across the water. Behind it the wind blows from the
	 * storm, much harder and gustier. It is the same field the sails feel, so it shows on the water (cat's paws,
	 * a dark line) before it reaches the boat.
	 * W5b: behind the line lies the storm's cold pool, a density current (FColdPool: its depth and temperature drop set the
	 * front's speed and the outflow), and in the rain core a microburst (FMicroburst, Vicroy) drifting with the front.
	 */
	struct SAILINGPHYSICS_API FGustFront
	{
		bool bActive = false;
		double StartX = 0.0, StartY = 0.0; // a point on the front line at StartTime (world, m); the storm's axis passes it
		double MoveDegrees = 0.0;          // direction the front travels toward (same angle convention as headings)
		double SpeedMs = 12.0;             // how fast the front moves
		double StartTime = 0.0;            // s
		double OutflowKnots = 28.0;        // mean wind behind the front (10 m)
		double OutflowFromDegrees = 290.0;
		double OutflowGustIntensity = 0.25;
		double LeadingEdgeMeters = 120.0;  // width of the transition; the strongest gusts sit just behind the edge
		double DecayStartTime = 1e9;       // s, outflow begins to weaken
		double DecaySeconds = 120.0;
		// W5b: the cold pool and the microburst.
		double ColdPoolDeltaC = 0.0;       // air temperature drop behind the front (C; observed 3 to 8, up to 12)
		double ColdPoolDepthM = 1000.0;
		FMicroburst Burst;                 // PeakOutflowMs 0 = none
		double BurstBehindM = 1500.0;      // its centre, this far behind the front on the storm's axis (in the rain core)
		double BurstStartTime = 0.0, BurstGrowSeconds = 120.0, BurstHoldSeconds = 300.0, BurstDecaySeconds = 300.0;

		/** Signed distance from a point to the front line (m): positive = still ahead of the front (old wind). */
		double DistanceAhead(double X, double Y, double T) const;
		/** Distance along the front line from the storm's axis (m; positive to the right of its track). */
		double AlongFront(double X, double Y) const;
		/** How far a point is into the cold pool: 0 ahead of the front, 1 well behind it (times the outflow's decay). */
		double Behind(double X, double Y, double T) const;
		/** Air temperature drop at a point (C, positive = colder). */
		double TemperatureDropAt(double X, double Y, double T) const;
		/** The microburst's air velocity at a point (world, m/s; Z up), its strength through its life included. */
		Vec3 BurstAt(double X, double Y, double Z, double T) const;
	};

	/**
	 * W1: the fine turbulence texture, a horizontal slice of a Mann (1994) box (Tools/wind/make_mann_slice.py,
	 * Content/TerrainData/Wind.mann): along-wind u and cross-wind v, u at unit standard deviation, periodic.
	 * Shared by every wind field once loaded; without it the fine layer is a cheap stand-in (and says so).
	 */
	struct SAILINGPHYSICS_API FTurbulenceTile
	{
		int Nx = 0, Ny = 0;
		double Dx = 2.0, LengthScale = 30.0, Gamma = 3.9, VRatio = 0.75;
		std::vector<float> U, V;

		bool IsValid() const { return Nx > 0 && Ny > 0; }
		/** Bilinear, wrapping; X along the wind, Y across (m). */
		void Sample(double X, double Y, double& OutU, double& OutV) const;

		/** Loads the shared tile from a .mann file; false (and the stand-in stays) if it is missing or malformed. */
		static bool LoadShared(const std::string& Path);
		/** Same from bytes already read (Unreal reads the staged file). */
		static bool LoadSharedFromMemory(const uint8_t* Data, size_t Size);
		static const FTurbulenceTile* Shared();
	};

	/** A pattern frame drifting with the air: origin, axis (the direction it drifts along) and drift velocity. */
	struct FDriftFrame
	{
		double OX = 0.0, OY = 0.0;   // origin at T0 (world, m)
		double T0 = 0.0;
		double Angle = 0.0;          // axis heading (rad, from +X toward +Y)
		double VX = 0.0, VY = 0.0;   // drift (m/s)
		double C = 1.0, S = 0.0;     // cos and sin of Angle

		void Local(double X, double Y, double T, double& Along, double& Across) const
		{
			const double DX = X - (OX + VX * (T - T0)), DY = Y - (OY + VY * (T - T0));
			Along = DX * C + DY * S;
			Across = -DX * S + DY * C;
		}
		/** New axis and drift from time T, the pattern kept still at the anchor (it turns about the boat, not the map origin). */
		void Reanchor(double T, double AnchorX, double AnchorY, double NewAngle, double NewVX, double NewVY);
	};

	/**
	 * True wind field: mean speed and direction with a stability-corrected log profile, and three seeded layers that are
	 * functions of place and time only (the same at any frame rate), each in its own frame drifting with the air:
	 *  - convective puffs (W1): cells 0.3 to 3 km across from the mixed-layer depth, drifting at the wind aloft (faster,
	 *    a few degrees veered); streets along the wind in a breeze, open cells in light air. Each lands, grows for 20 to
	 *    40 s, drifts, fades. Inside one the wind veers (PuffVeerDegrees) and fans out to both sides (PuffFanDegrees);
	 *    between them it is lighter and backed.
	 *  - kilometre cells: lulls and puffs from a band of waves 2 to 5 km long (1 to 2.5 mixed-layer depths) in the same
	 *    drifting frame, re-forming over half an hour; they carry CellShare of the puffs' variance and scale the smaller
	 *    puffs inside them.
	 *  - fine turbulence under 200 m: the Mann tile as frozen flow at the mean wind.
	 *  - slow oscillating and persistent shifts.
	 * Stability (air minus water temperature) sets the share and size of the puffs and the height profile. Shore lee and
	 * the building of the wind over open water come from the shelter map; a gust front blends over everything.
	 */
	class SAILINGPHYSICS_API FWindField
	{
	public:
		explicit FWindField(const FWindParams& InParams = FWindParams());

		/**
		 * Changes speed, direction, gusts or shifts at time T without making the patterns jump: they keep drifting from
		 * where they were, and a change of direction turns them about the anchor (the boat), not the map origin.
		 */
		void SetParamsAt(const FWindParams& InParams, double T, double AnchorX = 0.0, double AnchorY = 0.0);

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

		/** Mean speed at a height, before gusts (the stability-corrected profile through the 10 m speed). */
		double MeanSpeedAtHeight(double HeightMeters) const;

		/** Gust factor (1 = mean) at a world position and time: puffs and fine turbulence, before any lee. */
		double GustFactorAt(const Vec3& WorldPos, double TimeSeconds) const;

		/** Direction shift (radians, positive = veer toward +Y) at a place and time: puffs, turbulence and shifts. */
		double ShiftAt(const Vec3& WorldPos, double TimeSeconds) const;

		/**
		 * What a sailor reads on the water at a place: where the wind comes from (rad, with the puffs' veer and fan and the
		 * slow shifts, not the seconds-long turbulence) and its strength relative to the mean (the puffs, the lee).
		 */
		void ReadableAt(double X, double Y, double TimeSeconds, double& OutFromRadians, double& OutFactor) const;

		/** The puff layer alone at a point: its speed factor (1 = none) and shift (rad). For the tests and the README. */
		void PuffAt(double X, double Y, double TimeSeconds, double& OutFactor, double& OutShift) const;
		/**
		 * W3: how strong the gusts are here relative to the field's (the stations', at the shore): they ease with fetch
		 * from the upwind shore (FShelterMap::GustAt, W6's LES over the lake). 1 without a shelter map.
		 */
		double GustScaleAt(double X, double Y) const;
		/** Where the puffs drift (m/s, world) and the frames' current state. */
		Vec3 PuffDrift() const { return Vec3(Puffs.VX, Puffs.VY, 0.0); }
		/** Derived sizes (m) and shares, for the README and tests. */
		struct FDerived
		{
			double PuffAcross = 0.0, PuffAlong = 0.0, SpacingAcross = 0.0, SpacingAlong = 0.0, Streets = 0.0;
			double PuffSigma = 0.0, FineSigma = 0.0, PuffAmplitude = 0.0, ZetaAt10 = 0.0, AloftRatio = 1.25, Lifetime = 600.0;
			double CellWaveMin = 0.0, CellWaveMax = 0.0, CellSeconds = 1800.0, CellSigma = 0.0;
			bool bGusty = false;
		};
		const FDerived& GetDerived() const { return D; }

		const FWindParams& GetParams() const { return Params; }
		void SetParams(const FWindParams& InParams);

	private:
		void Derive();
		double Profile(double HeightMeters) const;
		double PuffField(double Along, double Across, double T, double& Fan) const;
		/** The kilometre cells at a point of the puffs' frame: unit standard deviation, zero mean. */
		double CellField(double Along, double Across, double T) const;
		void Fine(double X, double Y, double T, double& DU, double& DV) const;
		double Slow(double Along, double Across, double T) const;

		FWindParams Params;
		FDerived D;
		double Phases[12];
		double MeanSpeed10 = 0.0; // m/s
		Vec3 DownwindDir;         // unit vector the air travels along
		double PuffMean = 0.0;    // spatial mean of the raw puff field (subtracted so the gusts average to 1)
		double ProfileNorm = 1.0; // the profile's value at 10 m (divided out)
		double ObukhovL = 1e9;    // m (stable > 0, unstable < 0)
		static constexpr int kCellWaves = 12;
		double CellKA[kCellWaves] = {}, CellKC[kCellWaves] = {}, CellOmega[kCellWaves] = {}, CellPhase[kCellWaves] = {};
		FDriftFrame Puffs, Air;   // puffs drift at the wind aloft; fine turbulence and shifts at the mean wind
		FGustFront Front;
		const class FShelterMap* Shelter = nullptr;
	};
}
