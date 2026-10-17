#pragma once

#include "SailingPhysicsApi.h"
#include "CloudSky.h"
#include "WeatherDay.h"
#include "Wind.h"
#include <cstdint>
#include <memory>
#include <vector>

namespace Sailing
{
	enum class EWeatherPreset : uint8_t
	{
		CalmMorning,     // glassy to light and patchy, haze
		AfternoonBreeze, // building southerly with fair-weather cumulus: a typical Texas lake afternoon
		Overcast,        // grey, steady northerly
		Rain,            // overcast with steady rain, reduced visibility
		Thunderstorm,    // the full sequence: towering cumulus, gust front, rain, lightning, clearing
		RandomDay,       // seeded mix of the above, chosen and varied by the seed
		Count
	};

	SAILINGPHYSICS_API const char* WeatherPresetName(EWeatherPreset Preset);

	/** Thunderstorm phases, in order. */
	enum class EStormPhase : uint8_t { None, Building, GustFront, Rain, Clearing, Clear };
	SAILINGPHYSICS_API const char* StormPhaseName(EStormPhase Phase);

	struct FLightningStrike
	{
		double Time = 0.0;       // s since the weather started
		double X = 0.0, Y = 0.0; // world position of the strike (m)
		bool bCloudToGround = true;
	};

	/** W5b: a storm to run (the preset's, or a real day's fitted to its radar and stations). */
	struct FStormSpec
	{
		double MoveDegrees = 110.0, SpeedMs = 12.0;
		double ColdPoolDeltaC = 6.0, ColdPoolDepthM = 1000.0;
		double BurstPeakMs = 18.0;
		double TimeScale = 1.0; // the timeline after the front, stretched (a real storm rains for half an hour, the preset's for minutes)
	};

	/** Everything the world needs from the weather at one instant. */
	struct FWeatherState
	{
		FWindParams Wind;            // base (pre-front) wind
		FGustFront Front;            // thunderstorm outflow, if any
		double CloudCover = 0.0;     // 0 clear .. 1 overcast
		double CloudTopKm = 2.0;     // towering cumulus reach 10+ km
		double CloudDarkness = 0.0;  // 0 white .. 1 storm-dark base
		double Rain = 0.0;           // 0 .. 1 (1 = downpour)
		double VisibilityKm = 25.0;
		double FetchMeters = 4000.0;
		double HourOfDay = 15.0;     // local solar time
		EStormPhase Storm = EStormPhase::None;
		double StormDirectionDeg = 0.0; // where the storm cell is (from the boat's start), for towering cloud placement
		double StormDistanceKm = 0.0;
		FCloudSky Sky;               // Visual V5: the cloud layers, haze and the wind aloft
		// W5b: a storm rains where its core is (FStormRain, tied to the front); other weather rains everywhere alike.
		bool bStormRain = false;
		double StormRainScale = 0.0; // the storm's rain through its life (0..1)
		double AirC = 30.0;          // air temperature at the start before any cold pool (C)
		double DewC = 20.0;          // C1: dew point (C); the cumulus base is about 125 m per C of AirC - DewC
		// W8: a storm's darkness, cover and visibility are the place's (how close the front is), not the timeline's: the
		// day's values under it, the storm's build and clearing, kept so LocalizeStorm can redo them at the camera.
		double StormBuild = 0.0, StormClearing = 0.0;
		double BaseCloudCover = 0.0, BaseCloudDarkness = 0.0, BaseVisibilityKm = 25.0;
		// W5b: on a real day, the day itself (its radar), the local hour at weather time 0 and where the replay is anchored.
		std::shared_ptr<const FWeatherDay> Day;
		double DayStartHour = 0.0, RadarOffsetX = 0.0, RadarOffsetY = 0.0;

		/** Rain amount (0..1) at a point; FrontTime is the front's clock (the game keeps it on the sim clock). */
		SAILINGPHYSICS_API double RainAt(double X, double Y, double FrontTime) const;
		/** Rain rate (mm/h) at a point and altitude. */
		SAILINGPHYSICS_API double RainRateAt(double X, double Y, double Z, double FrontTime) const;
		/** Air temperature (C) at a point: the day's, less the storm's cold pool there. */
		SAILINGPHYSICS_API double AirTempAt(double X, double Y, double FrontTime) const;
		/** W8: sets CloudCover, CloudDarkness and VisibilityKm for a storm as seen from a point (from how far ahead of
		 *  the gust front it is: sunshine until the shelf is close, FStormShape::Overhead). No-op without a storm. */
		SAILINGPHYSICS_API void LocalizeStorm(double X, double Y, double FrontTime);
	};

	/**
	 * Weather for a southern inland lake, deterministic for a preset, seed and start time. Drives the wind field
	 * (speed, direction, gusts, shifts, gust front), waves (via wind and fetch), clouds, rain, visibility and
	 * lightning. The thunderstorm sequence is compressed so it plays in about nine minutes.
	 */
	class SAILINGPHYSICS_API FWeatherSystem
	{
	public:
		void Configure(EWeatherPreset Preset, uint32_t Seed, double StartHour, double BoatX = 0.0, double BoatY = 0.0);
		/**
		 * W5b: a real day (FWeatherDay, Tools/weather) instead of a preset: its hourly timeline drives the wind, the stability,
		 * the clouds and the rain; a storm on it runs the preset's storm with its own fitted front, cold pool and burst,
		 * reaching the start (BoatX, BoatY) when it reached the lake, and rains where the radar saw rain.
		 */
		void ConfigureDay(std::shared_ptr<const FWeatherDay> InDay, uint32_t Seed, double StartHour, double BoatX = 0.0, double BoatY = 0.0);
		const FWeatherDay* GetDay() const { return Day.get(); }

		/** W1: the month and the water (lake, or the bay and the Gulf) for the wind's calibration and the stability. */
		void SetClimate(int InMonth, bool bInCoast) { Month = InMonth; bCoast = bInCoast; }

		/** Weather at T seconds after Configure. */
		FWeatherState Evaluate(double T) const;

		/** Applies the state to a wind field without making gust patterns jump. */
		static void ApplyToWind(const FWeatherState& State, FWindField& Wind, double T, double AnchorX = 0.0, double AnchorY = 0.0);

		const std::vector<FLightningStrike>& GetStrikes() const { return Strikes; }
		EWeatherPreset GetPreset() const { return Preset; }

		/** W5b: the preset storm's gust front speed (m/s), from its cold pool (FColdPool) and the wind ahead of it. */
		static double StormFrontSpeed();

		/** Thunder reaches a listener this long after a strike (speed of sound, 343 m/s). */
		static double ThunderDelaySeconds(const FLightningStrike& Strike, double ListenerX, double ListenerY);

		// Thunderstorm timeline (seconds after start).
		static constexpr double kFrontArrives = 150.0;   // gust front reaches the start position
		static constexpr double kRainStarts = 210.0;     // rain follows the front by about a minute
		static constexpr double kOutflowDecays = 420.0;
		static constexpr double kClearingStarts = 450.0;
		static constexpr double kClear = 560.0;

	private:
		/** Runs the storm's timeline at weather time T; the front reaches (OX, OY) at Shift + kFrontArrives. */
		static void ApplyStorm(FWeatherState& W, double T, double Shift, const FStormSpec& Spec, double OX, double OY);
		void MakeStrikes(uint32_t& S, double Shift, double MoveDegrees, double Speed);
		FWeatherState EvaluateDay(double T) const;

		EWeatherPreset Preset = EWeatherPreset::AfternoonBreeze;
		EWeatherPreset RandomBase = EWeatherPreset::AfternoonBreeze;
		uint32_t Seed = 1;
		double StartHour = 15.0;
		int Month = 6;
		bool bCoast = false;
		double OriginX = 0.0, OriginY = 0.0;
		double RandomSpeedScale = 1.0, RandomDirectionOffset = 0.0;
		std::vector<FLightningStrike> Strikes;
		std::shared_ptr<const FWeatherDay> Day;
		FStormSpec DaySpec;
		double DayShift = 0.0;
	};
}
