#include "Weather.h"

namespace Sailing
{
	const char* WeatherPresetName(EWeatherPreset Preset)
	{
		switch (Preset)
		{
		case EWeatherPreset::CalmMorning: return "Calm morning";
		case EWeatherPreset::AfternoonBreeze: return "Afternoon breeze";
		case EWeatherPreset::Overcast: return "Overcast";
		case EWeatherPreset::Rain: return "Rain";
		case EWeatherPreset::Thunderstorm: return "Thunderstorm";
		case EWeatherPreset::RandomDay: return "Random day";
		default: return "?";
		}
	}

	const char* StormPhaseName(EStormPhase Phase)
	{
		switch (Phase)
		{
		case EStormPhase::Building: return "Storm building";
		case EStormPhase::GustFront: return "Gust front";
		case EStormPhase::Rain: return "Heavy rain";
		case EStormPhase::Clearing: return "Clearing";
		case EStormPhase::Clear: return "Storm passed";
		default: return "";
		}
	}

	namespace
	{
		// Thunderstorm geometry: the cell comes from the west-northwest and moves east-southeast.
		constexpr double kStormFromDeg = 290.0;
		constexpr double kFrontSpeed = 12.0;       // m/s (about 23 kn), typical outflow boundary
		constexpr double kCellBehindFront = 3000.0; // m, rain core trails the gust front

		/** Diurnal cycle of a southern lake: calm mornings, building afternoon breeze, easing at dusk. */
		double Diurnal(double Hour)
		{
			return 0.35 + 0.65 * SmoothStep(9.0, 14.0, Hour) * (1.0 - 0.45 * SmoothStep(18.0, 21.0, Hour));
		}

		uint32_t Hash(uint32_t S)
		{
			S ^= S >> 16; S *= 0x7feb352dU; S ^= S >> 15; S *= 0x846ca68bU; S ^= S >> 16;
			return S;
		}
		double Rand01(uint32_t& S) { S = Hash(S + 0x9e3779b9U); return (S % 1000000u) / 1000000.0; }
	}

	void FWeatherSystem::Configure(EWeatherPreset InPreset, uint32_t InSeed, double InStartHour, double BoatX, double BoatY)
	{
		Preset = InPreset;
		Seed = InSeed ? InSeed : 1;
		StartHour = InStartHour;
		OriginX = BoatX;
		OriginY = BoatY;
		Strikes.clear();

		uint32_t S = Seed;
		if (Preset == EWeatherPreset::RandomDay)
		{
			const EWeatherPreset Choices[] = { EWeatherPreset::CalmMorning, EWeatherPreset::AfternoonBreeze, EWeatherPreset::AfternoonBreeze, EWeatherPreset::Overcast, EWeatherPreset::Rain };
			RandomBase = Choices[int(Rand01(S) * 5.0) % 5];
			RandomSpeedScale = 0.7 + 0.6 * Rand01(S);
			RandomDirectionOffset = (Rand01(S) - 0.5) * 80.0;
		}

		if (Preset == EWeatherPreset::Thunderstorm)
		{
			// Lightning around the storm cell, rarer at first, most frequent as the core passes, then fading.
			const double Move = (kStormFromDeg + 180.0) * kDegToRad;
			double T = 30.0;
			while (T < kClearingStarts + 40.0)
			{
				const double Intensity = SmoothStep(20.0, kFrontArrives, T) * (1.0 - SmoothStep(kClearingStarts - 60.0, kClearingStarts + 40.0, T));
				T += 6.0 + 30.0 * (1.0 - Intensity) * Rand01(S) + 8.0 * Rand01(S);
				const double CellAlong = kFrontSpeed * (T - kFrontArrives) - kCellBehindFront;
				FLightningStrike Strike;
				Strike.Time = T;
				const double Lateral = (Rand01(S) - 0.5) * 5000.0;
				const double Along = CellAlong + (Rand01(S) - 0.5) * 3000.0;
				Strike.X = OriginX + std::cos(Move) * Along - std::sin(Move) * Lateral;
				Strike.Y = OriginY + std::sin(Move) * Along + std::cos(Move) * Lateral;
				Strike.bCloudToGround = Rand01(S) < 0.6;
				Strikes.push_back(Strike);
			}
		}
	}

	double FWeatherSystem::ThunderDelaySeconds(const FLightningStrike& Strike, double ListenerX, double ListenerY)
	{
		const double Dx = Strike.X - ListenerX, Dy = Strike.Y - ListenerY;
		// Strike channel averages about 2 km up; use slant range to the lower part of the channel.
		const double Distance = std::sqrt(Dx * Dx + Dy * Dy + 1000.0 * 1000.0);
		return Distance / 343.0;
	}

	FWeatherState FWeatherSystem::Evaluate(double T) const
	{
		FWeatherState W;
		W.HourOfDay = StartHour + T / 3600.0;
		W.Wind.Seed = Seed;
		const double Day = Diurnal(W.HourOfDay);

		EWeatherPreset P = Preset == EWeatherPreset::RandomDay ? RandomBase : Preset;
		const double SpeedScale = Preset == EWeatherPreset::RandomDay ? RandomSpeedScale : 1.0;
		const double DirOffset = Preset == EWeatherPreset::RandomDay ? RandomDirectionOffset : 0.0;

		switch (P)
		{
		case EWeatherPreset::CalmMorning:
			W.Wind.SpeedKnots = 6.0 * Day;
			W.Wind.FromDegrees = 150.0;
			W.Wind.GustIntensity = 0.35;
			W.Wind.ShiftDegrees = 20.0;
			W.Wind.GustLengthMeters = 180.0;
			W.CloudCover = 0.1;
			W.CloudTopKm = 2.0;
			W.VisibilityKm = 12.0;
			W.FetchMeters = 3000.0;
			break;
		case EWeatherPreset::AfternoonBreeze:
			W.Wind.SpeedKnots = 13.0 * Day;
			W.Wind.FromDegrees = 180.0;
			W.Wind.GustIntensity = 0.2;
			W.Wind.ShiftDegrees = 8.0;
			W.CloudCover = 0.3;
			W.CloudTopKm = 3.0;
			W.VisibilityKm = 25.0;
			W.FetchMeters = 6000.0;
			break;
		case EWeatherPreset::Overcast:
			W.Wind.SpeedKnots = 10.0;
			W.Wind.FromDegrees = 0.0;
			W.Wind.GustIntensity = 0.12;
			W.Wind.ShiftDegrees = 5.0;
			W.CloudCover = 0.95;
			W.CloudTopKm = 2.5;
			W.CloudDarkness = 0.35;
			W.VisibilityKm = 12.0;
			W.FetchMeters = 5000.0;
			break;
		case EWeatherPreset::Rain:
			W.Wind.SpeedKnots = 14.0;
			W.Wind.FromDegrees = 45.0;
			W.Wind.GustIntensity = 0.25;
			W.Wind.ShiftDegrees = 10.0;
			W.CloudCover = 1.0;
			W.CloudTopKm = 4.0;
			W.CloudDarkness = 0.5;
			W.Rain = 0.6;
			W.VisibilityKm = 4.0;
			W.FetchMeters = 4000.0;
			break;
		case EWeatherPreset::Thunderstorm:
		{
			// Before: a warm, light southerly. After: a light northwesterly as the cool outflow settles.
			const double After = SmoothStep(kOutflowDecays, kClear, T);
			W.Wind.SpeedKnots = Lerp(10.0, 7.0, After);
			W.Wind.FromDegrees = Lerp(180.0, 320.0, After);
			W.Wind.GustIntensity = Lerp(0.15, 0.25, After);
			W.Wind.ShiftDegrees = 8.0;
			W.FetchMeters = 5000.0;

			const double Move = kStormFromDeg + 180.0;
			W.Front.bActive = true;
			W.Front.MoveDegrees = Move;
			W.Front.SpeedMs = kFrontSpeed;
			W.Front.StartTime = 0.0;
			W.Front.StartX = OriginX - std::cos(Move * kDegToRad) * kFrontSpeed * kFrontArrives;
			W.Front.StartY = OriginY - std::sin(Move * kDegToRad) * kFrontSpeed * kFrontArrives;
			W.Front.OutflowKnots = 24.0;
			W.Front.OutflowFromDegrees = kStormFromDeg;
			W.Front.OutflowGustIntensity = 0.2;
			W.Front.DecayStartTime = kOutflowDecays;
			W.Front.DecaySeconds = 120.0;

			const double Build = SmoothStep(0.0, kFrontArrives, T);
			const double Clearing = SmoothStep(kClearingStarts, kClear, T);
			W.CloudCover = Lerp(Lerp(0.35, 0.95, Build), 0.4, Clearing);
			W.CloudTopKm = Lerp(Lerp(4.0, 12.0, Build), 6.0, Clearing);
			W.CloudDarkness = Lerp(Lerp(0.1, 0.85, Build), 0.15, Clearing);
			W.Rain = SmoothStep(kRainStarts, kRainStarts + 40.0, T) * (1.0 - SmoothStep(kOutflowDecays - 40.0, kClearingStarts, T));
			const double FrontHere = SmoothStep(kFrontArrives - 30.0, kFrontArrives + 20.0, T);
			W.VisibilityKm = Lerp(Lerp(25.0, 10.0, FrontHere), 1.5, W.Rain);
			W.VisibilityKm = Lerp(W.VisibilityKm, 20.0, Clearing);

			if (T < kFrontArrives - 20.0) W.Storm = EStormPhase::Building;
			else if (T < kRainStarts) W.Storm = EStormPhase::GustFront;
			else if (T < kClearingStarts) W.Storm = EStormPhase::Rain;
			else if (T < kClear) W.Storm = EStormPhase::Clearing;
			else W.Storm = EStormPhase::Clear;
			W.StormDirectionDeg = kStormFromDeg;
			W.StormDistanceKm = (kFrontSpeed * (kFrontArrives - T) + kCellBehindFront) / 1000.0;
			break;
		}
		default:
			break;
		}

		W.Wind.SpeedKnots *= SpeedScale;
		W.Wind.FromDegrees = std::fmod(W.Wind.FromDegrees + DirOffset + 360.0, 360.0);
		return W;
	}

	void FWeatherSystem::ApplyToWind(const FWeatherState& State, FWindField& Wind, double T)
	{
		Wind.SetParamsAt(State.Wind, T);
		Wind.SetFront(State.Front);
	}
}
