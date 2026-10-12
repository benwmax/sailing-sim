#pragma once

#include "SailingPhysicsApi.h"
#include "SailingMath.h"
#include <cstdint>
#include <string>
#include <vector>

namespace Sailing
{
	/** One harmonic constituent as NOAA publishes it: amplitude (m, or m/s for currents) and Greenwich phase lag (deg). */
	struct FTideConstituent
	{
		std::string Name;
		double Amplitude = 0.0;
		double PhaseDeg = 0.0;
	};

	/** A tide (or tidal current) station: where it is, its mean (Z0) and its constituents. */
	struct FTideStation
	{
		std::string Name;
		double X = 0.0, Y = 0.0;     // map frame, m
		double Z0 = 0.0;             // mean water level above chart datum (MLLW), or mean current (m/s, + = flood)
		double FloodDirRad = 0.0;    // currents: direction the flood sets toward (map frame, 0 = +X north)
		std::vector<FTideConstituent> Constituents;
	};

	/**
	 * Harmonic prediction the way NOAA's tables are made (Schureman): height = Z0 + sum f A cos(V + u - G), with the
	 * equilibrium argument V computed from the astronomical mean longitudes at the moment and f, u the 18.6-year nodal
	 * corrections. Matches NOAA's published predictions to within a few millimeters for Galveston Bay stations.
	 */
	SAILINGPHYSICS_API double PredictTide(const FTideStation& Station, double UnixSeconds);

	/** A turn of the tide or the current: high or low water, maximum flood or ebb, or slack. */
	struct FTideEvent
	{
		enum EType { Low = -1, Slack = 0, High = 1 }; // for currents: Low = maximum ebb, High = maximum flood
		double Time = 0.0;   // Unix seconds
		double Value = 0.0;  // height above datum (m) or current (m/s, + = flood)
		EType Type = Slack;
	};

	/**
	 * High and low waters between two times, the way NOAA's tables list them: the turning points of the predicted
	 * curve, to the minute.
	 */
	SAILINGPHYSICS_API std::vector<FTideEvent> TideExtremes(const FTideStation& Station, double From, double To);

	/**
	 * A current station's slack waters (where the current changes direction) and maximum flood and ebb (the strongest
	 * point of each run; a weakening between two maxima of the same direction is not listed, as in NOAA's tables).
	 */
	SAILINGPHYSICS_API std::vector<FTideEvent> CurrentEvents(const FTideStation& Station, double From, double To);

	/** Seconds since 1970-01-01 UTC for a calendar date and time (UTC). */
	SAILINGPHYSICS_API double UnixSecondsUtc(int Year, int Month, int Day, int Hour, int Minute, double Second = 0.0);

	/**
	 * Tides and tidal currents over a bay: water level interpolated between height stations (inverse distance, so the
	 * phase lag up the bay comes from the stations themselves), and currents from one reference current station spread
	 * over the water by a baked field of direction, strength and delay (channels carry the flow, the open bay barely
	 * moves, and the flow arrives later the farther it is from the entrance).
	 */
	class SAILINGPHYSICS_API FTideModel
	{
	public:
		std::vector<FTideStation> HeightStations;
		FTideStation CurrentStation;
		bool bHasCurrent = false;

		/** Loads the baked current field (".current": "SSCF" header, per cell int16 dir x, y in 1/10000, uint16 gain in 1/1000, uint16 delay s). */
		bool LoadCurrentField(const uint8_t* Data, size_t Size);
		bool IsValid() const { return !HeightStations.empty(); }

		/** Water level above chart datum (MLLW), m. */
		double HeightAt(double X, double Y, double UnixSeconds) const;
		/** Tidal current (m/s, map frame XY) at a point. */
		Vec3 CurrentAt(double X, double Y, double UnixSeconds) const;
		/** Current at the reference station along its flood direction (m/s, + = flood). */
		double StationCurrent(double UnixSeconds) const;
		/** The next high or low water at a point after a time (searched up to 30 h ahead); false if none. */
		bool NextExtreme(double X, double Y, double UnixSeconds, FTideEvent& Out) const;

	private:
		int Rows = 0, Cols = 0;
		double Cell = 50.0, OriginX = 0.0, OriginY = 0.0;
		std::vector<int16_t> DirX, DirY;
		std::vector<uint16_t> Gain, Delay;
	};
}
