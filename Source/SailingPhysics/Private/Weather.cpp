#include "Weather.h"
#include "WindClimate.h"

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

		/**
		 * Visual V5: the cloud layers for a preset (reference: North Texas summer climatology). Fair-weather cumulus grows
		 * as the land heats, from scattered puffs late in the morning to a third of the sky by mid-afternoon, its base
		 * rising from about 1.2 to 1.5 km with the deepening boundary layer, fading at dusk; the overcast is a low stratus
		 * deck behind a dry northerly (crisp air); rain falls from a thick nimbostratus; the thunderstorm towers, blows
		 * cirrus off its anvil ahead of itself and leaves broken debris cloud behind.
		 */
		void FillSky(EWeatherPreset P, double T, FWeatherState& W)
		{
			FCloudSky& S = W.Sky;
			const double H = W.HourOfDay;
			FCloudLayer& Cu = S[ECloudLayer::Cumulus];
			FCloudLayer& St = S[ECloudLayer::Stratus];
			FCloudLayer& Ci = S[ECloudLayer::Cirrus];
			FCloudLayer& Sm = S[ECloudLayer::Storm];
			Ci.BaseKm = 8.5; Ci.TopKm = 10.0; Ci.Density = 0.25;
			St.BaseKm = 0.9; St.TopKm = 1.6; St.Density = 0.8;
			const double Afternoon = SmoothStep(10.5, 15.0, H) * (1.0 - 0.6 * SmoothStep(18.5, 20.5, H));
			Cu.BaseKm = 1.2 + 0.3 * SmoothStep(11.0, 16.0, H);
			Cu.TopKm = Cu.BaseKm + 0.6 + 0.9 * Afternoon;
			switch (P)
			{
			case EWeatherPreset::CalmMorning:
				Cu.Coverage = 0.04 + 0.12 * Afternoon;
				Ci.Coverage = 0.25;
				S.Haze = 0.75;
				break;
			case EWeatherPreset::AfternoonBreeze:
				Cu.Coverage = 0.06 + 0.29 * Afternoon;
				Ci.Coverage = 0.1;
				S.Haze = 0.55;
				break;
			case EWeatherPreset::Overcast:
				// Graphics G6: an overcast is eight oktas: at 0.95 the deck showed blue holes (the round 7 race start).
				St.Coverage = 1.0;
				St.BaseKm = 0.9; St.TopKm = 1.7;
				S.Haze = 0.15;
				break;
			case EWeatherPreset::Rain:
				St.Coverage = 1.0;
				St.BaseKm = 0.6; St.TopKm = 3.5; St.Density = 1.2;
				S.Haze = 0.85;
				break;
			case EWeatherPreset::Thunderstorm:
			{
				const double Build = SmoothStep(0.0, FWeatherSystem::kFrontArrives, T);
				const double Clearing = SmoothStep(FWeatherSystem::kClearingStarts, FWeatherSystem::kClear, T);
				Cu.Coverage = Lerp(0.3, 0.15, Build) * (1.0 - Clearing) + 0.3 * Clearing;
				Cu.TopKm = Cu.BaseKm + 2.5;
				Ci.Coverage = 0.5 * Build * (1.0 - Clearing) + 0.2 * Clearing;
				Sm.Coverage = Lerp(0.35, 1.0, Build) * (1.0 - Clearing);
				Sm.BaseKm = 0.03; // the rain shafts under the core reach the water (the shelf's base is FStormShape::ShelfBaseM)
				Sm.TopKm = FStormShape::CoreTopM / 1000.0;
				St.Coverage = 0.5 * SmoothStep(FWeatherSystem::kRainStarts, FWeatherSystem::kClearingStarts, T) * (1.0 - Clearing) + 0.25 * Clearing;
				St.BaseKm = 0.7; St.TopKm = 2.0;
				S.Haze = Lerp(0.6, 0.25, Clearing);
				break;
			}
			default:
				break;
			}
			// The clouds drift with the wind at their height: about twice the surface wind, from a little to the right.
			const double From = (W.Wind.FromDegrees + 15.0) * kDegToRad;
			const double Aloft = std::max(4.0, 2.0 * W.Wind.SpeedKnots * kKnot);
			S.DriftX = -std::cos(From) * Aloft;
			S.DriftY = -std::sin(From) * Aloft;
		}
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
		// W1: the preset scales the calibrated gustiness (WindClimate.h) and nudges the stability and the mixed layer.
		double Gustiness = 1.0, Overcast = 0.0, AirOffset = 0.0, Layer = 1.0;
		const double SpeedScale = Preset == EWeatherPreset::RandomDay ? RandomSpeedScale : 1.0;
		const double DirOffset = Preset == EWeatherPreset::RandomDay ? RandomDirectionOffset : 0.0;

		switch (P)
		{
		case EWeatherPreset::CalmMorning:
			W.Wind.SpeedKnots = 6.0 * Day;
			W.Wind.FromDegrees = 150.0;
			// W1: light air is the gustiest and shiftiest relative to its speed (1.75 x the calibrated breeze).
			Gustiness = 1.75;
			W.Wind.ShiftDegrees = 20.0;
			W.Wind.ShiftPeriodSeconds = 240.0;
			W.Wind.PersistentShiftDegrees = 15.0;
			W.CloudCover = 0.1;
			W.CloudTopKm = 2.0;
			W.VisibilityKm = 12.0;
			W.FetchMeters = 3000.0;
			break;
		case EWeatherPreset::AfternoonBreeze:
			W.Wind.SpeedKnots = 13.0 * Day;
			W.Wind.FromDegrees = 180.0;
			W.Wind.ShiftDegrees = 8.0;
			W.Wind.ShiftPeriodSeconds = 420.0;
			W.Wind.PersistentShiftDegrees = 8.0; // the afternoon breeze veering as it fills
			W.CloudCover = 0.3;
			W.CloudTopKm = 3.0;
			W.VisibilityKm = 25.0;
			W.FetchMeters = 6000.0;
			break;
		case EWeatherPreset::Overcast:
			W.Wind.SpeedKnots = 10.0;
			W.Wind.FromDegrees = 0.0;
			Gustiness = 0.6;
			Overcast = 0.8;
			W.Wind.ShiftDegrees = 5.0;
			W.Wind.ShiftPeriodSeconds = 600.0;
			W.Wind.PersistentShiftDegrees = 5.0;
			W.CloudCover = 0.95;
			W.CloudTopKm = 2.5;
			W.CloudDarkness = 0.35;
			W.VisibilityKm = 12.0;
			W.FetchMeters = 5000.0;
			break;
		case EWeatherPreset::Rain:
			W.Wind.SpeedKnots = 14.0;
			W.Wind.FromDegrees = 45.0;
			Gustiness = 1.25;
			Overcast = 0.9;
			AirOffset = -3.0; // rain-cooled air
			W.Wind.ShiftDegrees = 10.0;
			W.Wind.ShiftPeriodSeconds = 300.0;
			W.Wind.PersistentShiftDegrees = 6.0;
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
			// Hot and deep before; the cold outflow over the warm water after (gusty, shifty, shallow).
			Gustiness = Lerp(0.75, 1.25, After);
			AirOffset = Lerp(2.0, -6.0, SmoothStep(kFrontArrives - 20.0, kRainStarts, T));
			Layer = Lerp(1.3, 0.6, After);
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

		// W1: gust factor and puff timing from the station calibration for the month, hour and water; stability from the
		// air over the water (cloud keeps the air near its daily mean); the convective layer the puffs come down from.
		const double Air = Lerp(ClimateAirC(Month, W.HourOfDay, bCoast), 0.5 * (ClimateAirC(Month, 6.5, bCoast) + ClimateAirC(Month, 15.5, bCoast)), Overcast);
		W.Wind.GustIntensity = Gustiness * GustIntensityForFactor(ClimateGustFactor(Month, W.HourOfDay, bCoast));
		W.Wind.PuffIntensity = Gustiness * ClimatePuffStrength(Month, W.HourOfDay, bCoast);
		W.Wind.AirMinusWaterC = Air + AirOffset - ClimateWaterC(Month, bCoast);
		W.Wind.MixedLayerMeters = ClimateMixedLayerM(Month, W.HourOfDay, bCoast) * Layer * (1.0 - 0.5 * Overcast);
		W.Wind.PuffIntervalSeconds = 60.0 * ClimatePuffMinutes(Month, W.HourOfDay, bCoast);

		FillSky(P, T, W);
		W.Wind.SpeedKnots *= SpeedScale;
		W.Wind.FromDegrees = std::fmod(W.Wind.FromDegrees + DirOffset + 360.0, 360.0);
		return W;
	}

	void FWeatherSystem::ApplyToWind(const FWeatherState& State, FWindField& Wind, double T, double AnchorX, double AnchorY)
	{
		Wind.SetParamsAt(State.Wind, T, AnchorX, AnchorY);
		Wind.SetFront(State.Front);
	}
}
