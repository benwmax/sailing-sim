#pragma once

#include "SailingPhysicsApi.h"
#include "CloudSky.h"
#include "Wind.h"
#include <cstdint>
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
		/** W1: the month and the water (lake, or the bay and the Gulf) for the wind's calibration and the stability. */
		void SetClimate(int InMonth, bool bInCoast) { Month = InMonth; bCoast = bInCoast; }

		/** Weather at T seconds after Configure. */
		FWeatherState Evaluate(double T) const;

		/** Applies the state to a wind field without making gust patterns jump. */
		static void ApplyToWind(const FWeatherState& State, FWindField& Wind, double T, double AnchorX = 0.0, double AnchorY = 0.0);

		const std::vector<FLightningStrike>& GetStrikes() const { return Strikes; }
		EWeatherPreset GetPreset() const { return Preset; }

		/** Thunder reaches a listener this long after a strike (speed of sound, 343 m/s). */
		static double ThunderDelaySeconds(const FLightningStrike& Strike, double ListenerX, double ListenerY);

		// Thunderstorm timeline (seconds after start).
		static constexpr double kFrontArrives = 150.0;   // gust front reaches the start position
		static constexpr double kRainStarts = 210.0;     // rain follows the front by about a minute
		static constexpr double kOutflowDecays = 420.0;
		static constexpr double kClearingStarts = 450.0;
		static constexpr double kClear = 560.0;

	private:
		EWeatherPreset Preset = EWeatherPreset::AfternoonBreeze;
		EWeatherPreset RandomBase = EWeatherPreset::AfternoonBreeze;
		uint32_t Seed = 1;
		double StartHour = 15.0;
		int Month = 6;
		bool bCoast = false;
		double OriginX = 0.0, OriginY = 0.0;
		double RandomSpeedScale = 1.0, RandomDirectionOffset = 0.0;
		std::vector<FLightningStrike> Strikes;
	};
}
