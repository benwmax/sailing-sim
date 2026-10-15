#pragma once

#include "SailingPhysicsApi.h"
#include <cstdint>
#include <string>
#include <vector>

namespace Sailing
{
	/** W5b: one hour of a real day over the lake (HRRR analysis at the lake, Tools/weather/bake_day.py). */
	struct FWeatherHour
	{
		double WindKnots = 8.0, FromDegrees = 180.0, GustKnots = 12.0; // 10 m
		double AirC = 25.0, DewC = 15.0, WaterC = 22.0;
		double MixedLayerM = 1000.0;  // HRRR planetary boundary layer height
		double CapeJkg = 0.0;         // surface-based CAPE (instability)
		double CloudLow = 0.0, CloudMid = 0.0, CloudHigh = 0.0; // fractions
		double CloudBaseM = 1500.0;   // above the lake
		double RainMmPerHour = 0.0;
		double VisibilityKm = 25.0;
	};

	/**
	 * W5b: a real day baked from free data (Tools/weather): the hourly timeline from HRRR model analyses, and on a stormy day
	 * the storm's replay: its gust front fitted to the radar's motion and the stations' arrival, temperature drop and peak
	 * gust, and MRMS radar frames of the rain rate around the lake. File: Content/TerrainData/Weather/<date>.wxday (a text
	 * header, then the radar bytes). Radar grid: rows north (X), columns east (Y), centred on the map origin.
	 */
	struct SAILINGPHYSICS_API FWeatherDay
	{
		std::string Date, Place, Title;
		int UtcOffset = -5;
		double StartHour = 15.0;      // suggested local start (on a stormy day: the front arrives at kFrontArrives)
		std::vector<FWeatherHour> Hours; // local hours 0..23

		bool bStorm = false;
		double StormArrivalHour = 0.0; // local: the gust front reaches the map origin
		double StormMoveDegrees = 110.0, StormSpeedMs = 12.0;
		double ColdPoolDeltaC = 6.0, ColdPoolDepthM = 1000.0;
		double PeakGustKnots = 40.0, BurstPeakMs = 0.0, PeakRainMmPerHour = 60.0;
		double StormTimeScale = 1.0;   // how much longer than the preset's the storm's passage was (FStormSpec::TimeScale)

		int RadarNx = 0, RadarNy = 0;
		double RadarCellM = 2000.0;
		std::vector<double> RadarHours;  // local hour of each frame
		std::vector<uint8_t> Radar;      // rain rate x 2 (mm/h), frame after frame

		bool LoadFromMemory(const uint8_t* Data, size_t Size, std::string* OutError = nullptr);
		bool LoadFile(const std::string& Path, std::string* OutError = nullptr);
		bool IsValid() const { return Hours.size() == 24; }
		int Year() const;
		int Month() const;
		int DayOfMonth() const;

		/** The timeline at a local hour (linear between hours; directions the short way round). */
		FWeatherHour At(double LocalHour) const;
		bool HasRadar() const { return RadarNx > 0 && RadarNy > 0 && !RadarHours.empty(); }
		/** Radar rain rate (mm/h) at a map point (m from the origin) and local hour; -1 outside the frames' time or area. */
		double RadarRate(double X, double Y, double LocalHour) const;
	};
}
