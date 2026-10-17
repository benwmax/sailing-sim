#include "Weather.h"
#include "Storm.h"
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
		constexpr double kCellBehindFront = 3000.0; // m, rain core trails the gust front
		// W5b: the cold pool of a strong North Texas summer storm (Charba 1974, Engerer et al. 2008: 3 to 8 C colder, a
		// kilometre or so deep) under a hot afternoon, and the warm 10 kn southerly ahead of it.
		constexpr double kColdPoolDeltaC = 6.0;
		constexpr double kColdPoolDepthM = 1400.0;
		constexpr double kStormAirC = 33.0;
		constexpr double kAheadKnots = 10.0, kAheadFromDeg = 180.0;
		// The microburst in the core: a moderate wet one, its outflow peaking at 10 m/s 50 m up on a ring 1.2 km across (JAWS
		// microbursts: 10 to 25 m/s; at 10 m about 5 m/s on top of the cold pool's own flow, whose gusts already reach the
		// 1.5 times the front's speed Goff 1976 measured), bursting as the front nears the start and lasting ten minutes.

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

		/** The thunderstorm's sky at storm time Ts (the preset's timeline), blended over the day's sky by Weight (1 = all). */
		void StormSky(FCloudSky& S, double Ts, double Weight)
		{
			FCloudLayer& Cu = S[ECloudLayer::Cumulus];
			FCloudLayer& St = S[ECloudLayer::Stratus];
			FCloudLayer& Ci = S[ECloudLayer::Cirrus];
			FCloudLayer& Sm = S[ECloudLayer::Storm];
			const double Build = SmoothStep(0.0, FWeatherSystem::kFrontArrives, Ts);
			const double Clearing = SmoothStep(FWeatherSystem::kClearingStarts, FWeatherSystem::kClear, Ts);
			Cu.Coverage = Lerp(Cu.Coverage, Lerp(0.3, 0.15, Build) * (1.0 - Clearing) + 0.3 * Clearing, Weight);
			Cu.TopKm = Lerp(Cu.TopKm, Cu.BaseKm + 2.5, Weight);
			S.CuCellScale = Lerp(S.CuCellScale, 1.0, Weight);   // C1: a building day's cells are the big ones
			Ci.Coverage = Lerp(Ci.Coverage, 0.5 * Build * (1.0 - Clearing) + 0.2 * Clearing, Weight);
			Sm.Coverage = Lerp(Sm.Coverage, Lerp(0.35, 1.0, Build) * (1.0 - Clearing), Weight);
			Sm.BaseKm = 0.03; // the rain shafts under the core reach the water (the shelf's base is FStormShape::ShelfBaseM)
			Sm.TopKm = FStormShape::CoreTopM / 1000.0;
			St.Coverage = Lerp(St.Coverage, 0.5 * SmoothStep(FWeatherSystem::kRainStarts, FWeatherSystem::kClearingStarts, Ts) * (1.0 - Clearing) + 0.25 * Clearing, Weight);
			if (Weight > 0.5) { St.BaseKm = 0.7; St.TopKm = 2.0; }
			S.Haze = Lerp(S.Haze, Lerp(0.6, 0.25, Clearing), Weight);
		}

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
			Ci.BaseKm = 8.5; Ci.TopKm = 10.0; Ci.Density = 0.25;
			St.BaseKm = 0.9; St.TopKm = 1.6; St.Density = 0.8;
			const double Afternoon = SmoothStep(10.5, 15.0, H) * (1.0 - 0.6 * SmoothStep(18.5, 20.5, H));
			// C1 (round 12): every cumulus base on a day sits at one height, the lifting condensation level, about 125 m per
			// degree of spread between the air and its dew point: near 1 km on a humid summer morning, near 2 km on a hot
			// afternoon over the lake (DFW's July ceilings), lower on the humid coast.
			Cu.BaseKm = Clamp(0.125 * (W.AirC - W.DewC), 0.5, 2.5);
			// C1: fair-weather cumulus about as deep as they are wide (0.4 to 1.1 km); at 1.5 km deep the towers stood as
			// columns filling the low sky. A building day deepens them (StormSky, the real days' instability).
			Cu.TopKm = Cu.BaseKm + 0.4 + 0.7 * Afternoon;
			switch (P)
			{
			case EWeatherPreset::CalmMorning:
				Cu.Coverage = 0.04 + 0.12 * Afternoon;
				Ci.Coverage = 0.25;
				S.Haze = 0.75;
				break;
			case EWeatherPreset::AfternoonBreeze:
				// C1 (round 12): scattered at most, about a fifth of the sky by mid-afternoon (real-05: a row of puffs over the
				// far shore and a lot of blue). At a third, the towers' sides filled the low sky into a deck seen from the water.
				Cu.Coverage = 0.04 + 0.18 * Afternoon;
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
				StormSky(S, T, 1.0);
				break;
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

	double FWeatherSystem::StormFrontSpeed()
	{
		const double Move = (kStormFromDeg + 180.0) * kDegToRad, Ahead = kAheadFromDeg * kDegToRad;
		// The ambient wind's component along the track (it blows toward Ahead + 180 deg).
		const double Along = kAheadKnots * kKnot * (-std::cos(Ahead) * std::cos(Move) - std::sin(Ahead) * std::sin(Move));
		return FColdPool::FrontSpeed(kColdPoolDeltaC, kColdPoolDepthM, kStormAirC, Along);
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

		Day.reset();
		if (Preset == EWeatherPreset::Thunderstorm) MakeStrikes(S, 0.0, (kStormFromDeg + 180.0), StormFrontSpeed());
	}

	void FWeatherSystem::MakeStrikes(uint32_t& S, double Shift, double MoveDegrees, double Speed)
	{
		// Lightning around the storm cell, rarer at first, most frequent as the core passes, then fading.
		const double Move = MoveDegrees * kDegToRad;
		double T = 30.0;
		while (T < kClearingStarts + 40.0)
		{
			const double Intensity = SmoothStep(20.0, kFrontArrives, T) * (1.0 - SmoothStep(kClearingStarts - 60.0, kClearingStarts + 40.0, T));
			T += 6.0 + 30.0 * (1.0 - Intensity) * Rand01(S) + 8.0 * Rand01(S);
			const double CellAlong = Speed * (T - kFrontArrives) - kCellBehindFront;
			FLightningStrike Strike;
			Strike.Time = T + Shift;
			const double Lateral = (Rand01(S) - 0.5) * 5000.0;
			const double Along = CellAlong + (Rand01(S) - 0.5) * 3000.0;
			Strike.X = OriginX + std::cos(Move) * Along - std::sin(Move) * Lateral;
			Strike.Y = OriginY + std::sin(Move) * Along + std::cos(Move) * Lateral;
			Strike.bCloudToGround = Rand01(S) < 0.6;
			Strikes.push_back(Strike);
		}
	}

	void FWeatherSystem::ConfigureDay(std::shared_ptr<const FWeatherDay> InDay, uint32_t InSeed, double InStartHour, double BoatX, double BoatY)
	{
		Configure(EWeatherPreset::AfternoonBreeze, InSeed, InStartHour, BoatX, BoatY);
		Day = std::move(InDay);
		if (!Day || !Day->IsValid())
		{
			Day.reset();
			return;
		}
		Month = Day->Month();
		bCoast = false;
		if (Day->bStorm)
		{
			// The replay is anchored at the start: the front reaches it when it reached the lake that day.
			DaySpec.MoveDegrees = Day->StormMoveDegrees;
			DaySpec.SpeedMs = Day->StormSpeedMs;
			DaySpec.ColdPoolDeltaC = Day->ColdPoolDeltaC;
			DaySpec.ColdPoolDepthM = Day->ColdPoolDepthM;
			DaySpec.BurstPeakMs = Day->BurstPeakMs;
			DaySpec.TimeScale = Day->StormTimeScale;
			DayShift = (Day->StormArrivalHour - StartHour) * 3600.0 - kFrontArrives;
			uint32_t S = Seed ^ 0x5bd1e995u;
			MakeStrikes(S, DayShift, DaySpec.MoveDegrees, DaySpec.SpeedMs);
		}
	}

	FWeatherState FWeatherSystem::EvaluateDay(double T) const
	{
		FWeatherState W;
		W.HourOfDay = StartHour + T / 3600.0;
		W.Wind.Seed = Seed;
		W.Day = Day;
		W.DayStartHour = StartHour;
		W.RadarOffsetX = OriginX;
		W.RadarOffsetY = OriginY;
		const FWeatherHour H = Day->At(W.HourOfDay);
		W.Wind.SpeedKnots = std::max(H.WindKnots, 0.0);
		W.Wind.FromDegrees = H.FromDegrees;
		// The hourly analyses turn the wind through the day themselves; light air wanders more.
		W.Wind.ShiftDegrees = Lerp(18.0, 8.0, SmoothStep(4.0, 10.0, H.WindKnots));
		W.Wind.ShiftPeriodSeconds = 300.0;
		// Gusts: the stations' calibration for the month and hour, scaled by the model's own gustiness that day (HRRR's
		// surface gust is typically 1.7 times its mean wind).
		const double Gustiness = Clamp(H.GustKnots / std::max(H.WindKnots, 2.0) / 1.7, 0.6, 1.6);
		W.Wind.GustIntensity = Gustiness * GustIntensityForFactor(ClimateGustFactor(Month, W.HourOfDay, false));
		W.Wind.PuffIntensity = Gustiness * ClimatePuffStrength(Month, W.HourOfDay, false);
		const double Water = H.WaterC > -50.0 ? H.WaterC : ClimateWaterC(Month, false);
		W.AirC = H.AirC;
		W.DewC = H.DewC;
		W.Wind.AirMinusWaterC = H.AirC - Water;
		W.Wind.MixedLayerMeters = Clamp(H.MixedLayerM, 100.0, 4000.0);
		W.Wind.ClimateAirMinusWaterC = ClimateAirC(Month, W.HourOfDay, false) - ClimateWaterC(Month, false);
		W.Wind.ClimateMixedLayerMeters = ClimateMixedLayerM(Month, W.HourOfDay, false);
		W.Wind.PuffIntervalSeconds = 60.0 * ClimatePuffMinutes(Month, W.HourOfDay, false);
		W.FetchMeters = 5000.0;

		// Clouds by layer (random overlap), rain and visibility from the analysis.
		W.CloudCover = 1.0 - (1.0 - H.CloudLow) * (1.0 - H.CloudMid) * (1.0 - H.CloudHigh);
		W.CloudTopKm = H.CapeJkg > 1000.0 && H.CloudLow > 0.3 ? 8.0 : 3.0;
		W.Rain = FStormRain::Amount(H.RainMmPerHour);
		W.CloudDarkness = Clamp(0.5 * H.CloudLow + 0.3 * H.CloudMid + 0.4 * W.Rain, 0.0, 0.9);
		W.VisibilityKm = Clamp(H.VisibilityKm, 0.5, 25.0);
		FCloudSky& S = W.Sky;
		FCloudLayer& Cu = S[ECloudLayer::Cumulus];
		FCloudLayer& St = S[ECloudLayer::Stratus];
		FCloudLayer& Ci = S[ECloudLayer::Cirrus];
		Ci.BaseKm = 8.5; Ci.TopKm = 10.0; Ci.Density = 0.25;
		Ci.Coverage = H.CloudHigh;
		const double BaseKm = Clamp(H.CloudBaseM / 1000.0, 0.3, 3.0);
		// Low cloud on an unstable day is cumulus (its tops from the instability); otherwise a stratus deck.
		if (H.CapeJkg > 100.0 && H.CloudLow < 0.8)
		{
			Cu.Coverage = H.CloudLow;
			Cu.BaseKm = BaseKm;
			Cu.TopKm = BaseKm + Clamp(0.6 + H.CapeJkg / 2000.0, 0.6, 3.0);
			S.CuCellScale = Clamp(0.6 + H.CapeJkg / 2500.0, 0.6, 1.0);   // C1: bigger cells as the day builds
		}
		else
		{
			St.Coverage = H.CloudLow;
			St.BaseKm = BaseKm;
			St.TopKm = BaseKm + 0.8;
			St.Density = 0.8 + 0.4 * W.Rain;
		}
		// A middle deck (altostratus) where there is no low one over it.
		if (H.CloudMid > St.Coverage)
		{
			St.Coverage = H.CloudMid;
			St.BaseKm = 3.0;
			St.TopKm = 4.5;
		}
		// Haze from the humidity: a muggy Texas morning is milky, a dry norther crisp.
		S.Haze = Clamp((H.DewC - 2.0) / 20.0, 0.1, 0.85);
		const double From = (W.Wind.FromDegrees + 15.0) * kDegToRad;
		const double Aloft = std::max(4.0, 2.0 * W.Wind.SpeedKnots * kKnot);
		S.DriftX = -std::cos(From) * Aloft;
		S.DriftY = -std::sin(From) * Aloft;

		// The storm, in its window: an hour before its front reaches the start until it has passed.
		if (Day->bStorm)
		{
			const double Scale = std::max(DaySpec.TimeScale, 1.0);
			const double Raw = T - DayShift;
			const double Ts = Raw <= kFrontArrives ? Raw : kFrontArrives + (Raw - kFrontArrives) / Scale;
			if (Ts > -3600.0 && Ts < kClear + 900.0)
			{
				StormSky(S, Ts, SmoothStep(-3600.0, -1200.0, Ts) * (1.0 - SmoothStep(kClear, kClear + 900.0, Ts)));
				ApplyStorm(W, T, DayShift, DaySpec, OriginX, OriginY);
				W.Wind.AirMinusWaterC -= W.Front.TemperatureDropAt(OriginX, OriginY, T);
			}
		}
		// Where the radar has frames, it says where it rains (moved with the start like the front).
		if (Day->HasRadar() && W.HourOfDay >= Day->RadarHours.front() && W.HourOfDay <= Day->RadarHours.back())
		{
			W.bStormRain = true;
			if (W.StormRainScale <= 0.0) W.StormRainScale = 1.0;
			W.Rain = W.RainAt(OriginX, OriginY, T);
			W.VisibilityKm = std::min(W.VisibilityKm, Lerp(25.0, 1.5, W.Rain));
			W.CloudDarkness = std::max(W.CloudDarkness, 0.85 * W.Rain);
		}
		return W;
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
		if (Day) return EvaluateDay(T);
		FWeatherState W;
		W.HourOfDay = StartHour + T / 3600.0;
		W.Wind.Seed = Seed;
		const double Daily = Diurnal(W.HourOfDay);

		EWeatherPreset P = Preset == EWeatherPreset::RandomDay ? RandomBase : Preset;
		// W1: the preset scales the calibrated gustiness (WindClimate.h) and nudges the stability and the mixed layer.
		double Gustiness = 1.0, Overcast = 0.0, AirOffset = 0.0, Layer = 1.0;
		const double SpeedScale = Preset == EWeatherPreset::RandomDay ? RandomSpeedScale : 1.0;
		const double DirOffset = Preset == EWeatherPreset::RandomDay ? RandomDirectionOffset : 0.0;

		switch (P)
		{
		case EWeatherPreset::CalmMorning:
			W.Wind.SpeedKnots = 6.0 * Daily;
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
			W.Wind.SpeedKnots = 13.0 * Daily;
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
			W.Wind.SpeedKnots = Lerp(kAheadKnots, 7.0, After);
			W.Wind.FromDegrees = Lerp(kAheadFromDeg, 320.0, After);
			// Hot and deep before; the cold outflow over the warm water after (gusty, shifty, shallow).
			Gustiness = Lerp(0.75, 1.25, After);
			AirOffset = Lerp(2.0, 2.0 - kColdPoolDeltaC - 2.0, SmoothStep(kFrontArrives - 20.0, kRainStarts, T));
			Layer = Lerp(1.3, 0.6, After);
			W.Wind.ShiftDegrees = 8.0;
			W.FetchMeters = 5000.0;

			FStormSpec Spec;
			Spec.MoveDegrees = kStormFromDeg + 180.0;
			Spec.SpeedMs = StormFrontSpeed();
			Spec.ColdPoolDeltaC = kColdPoolDeltaC;
			Spec.ColdPoolDepthM = kColdPoolDepthM;
			Spec.BurstPeakMs = 10.0;
			ApplyStorm(W, T, 0.0, Spec, OriginX, OriginY);
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
		W.AirC = P == EWeatherPreset::Thunderstorm ? kStormAirC : Air;
		W.DewC = ClimateDewC(Month, bCoast);
		W.Wind.MixedLayerMeters = ClimateMixedLayerM(Month, W.HourOfDay, bCoast) * Layer * (1.0 - 0.5 * Overcast);
		W.Wind.ClimateAirMinusWaterC = ClimateAirC(Month, W.HourOfDay, bCoast) - ClimateWaterC(Month, bCoast);
		W.Wind.ClimateMixedLayerMeters = ClimateMixedLayerM(Month, W.HourOfDay, bCoast);
		W.Wind.PuffIntervalSeconds = 60.0 * ClimatePuffMinutes(Month, W.HourOfDay, bCoast);

		FillSky(P, T, W);
		W.Wind.SpeedKnots *= SpeedScale;
		W.Wind.FromDegrees = std::fmod(W.Wind.FromDegrees + DirOffset + 360.0, 360.0);
		return W;
	}

	void FWeatherSystem::ApplyStorm(FWeatherState& W, double T, double Shift, const FStormSpec& Spec, double OX, double OY)
	{
		// Storm time: the preset's timeline (the front reaches the start at kFrontArrives), shifted on a real day and
		// stretched after the front to the real storm's length.
		const double Scale = std::max(Spec.TimeScale, 1.0);
		const double Ts = T - Shift <= kFrontArrives ? T - Shift : kFrontArrives + (T - Shift - kFrontArrives) / Scale;
		const double Move = Spec.MoveDegrees, Speed = Spec.SpeedMs;
		W.Front.bActive = true;
		W.Front.MoveDegrees = Move;
		W.Front.SpeedMs = Speed;
		W.Front.StartTime = Shift;
		W.Front.StartX = OX - std::cos(Move * kDegToRad) * Speed * kFrontArrives;
		W.Front.StartY = OY - std::sin(Move * kDegToRad) * Speed * kFrontArrives;
		// W5b: the cold pool's own flow behind the head, and the microburst in the core.
		W.Front.OutflowKnots = FColdPool::kOutflowRatio * Speed / kKnot;
		W.Front.ColdPoolDeltaC = Spec.ColdPoolDeltaC;
		W.Front.ColdPoolDepthM = Spec.ColdPoolDepthM;
		W.Front.Burst.PeakOutflowMs = Spec.BurstPeakMs;
		W.Front.Burst.PeakRadiusM = 1200.0;
		W.Front.Burst.PeakHeightM = 50.0;
		W.Front.BurstBehindM = 1500.0;
		W.Front.BurstStartTime = Shift + kFrontArrives - 60.0;
		W.Front.BurstHoldSeconds = 240.0 * std::min(Scale, 2.5);
		W.Front.OutflowFromDegrees = std::fmod(Move + 180.0, 360.0);
		W.Front.OutflowGustIntensity = 0.2;
		W.Front.DecayStartTime = Shift + kFrontArrives + (kOutflowDecays - kFrontArrives) * Scale;
		W.Front.DecaySeconds = 120.0 * Scale;

		const double Build = SmoothStep(0.0, kFrontArrives, Ts);
		const double Clearing = SmoothStep(kClearingStarts, kClear, Ts);
		W.CloudTopKm = std::max(W.CloudTopKm, Lerp(Lerp(4.0, 12.0, Build), 6.0, Clearing));
		W.StormBuild = Build;
		W.StormClearing = Clearing;
		W.BaseCloudCover = W.CloudCover;
		W.BaseCloudDarkness = W.CloudDarkness;
		W.BaseVisibilityKm = W.VisibilityKm;
		// W5b: rain from the core's position (FStormRain, or the radar on a real day), easing as the storm dies; W.Rain is
		// what falls at the start.
		W.bStormRain = true;
		W.StormRainScale = 1.0 - SmoothStep(kOutflowDecays - 40.0, kClearingStarts, Ts);
		W.Rain = W.RainAt(OX, OY, T);
		// W8: darkness, cover and visibility at the start from the front's distance (the game redoes them at the camera).
		W.LocalizeStorm(OX, OY, T);

		if (Ts < kFrontArrives - 20.0) W.Storm = EStormPhase::Building;
		else if (Ts < kRainStarts) W.Storm = EStormPhase::GustFront;
		else if (Ts < kClearingStarts) W.Storm = EStormPhase::Rain;
		else if (Ts < kClear) W.Storm = EStormPhase::Clearing;
		else W.Storm = EStormPhase::Clear;
		W.StormDirectionDeg = std::fmod(Move + 180.0, 360.0);
		W.StormDistanceKm = (Speed * (kFrontArrives - Ts) + kCellBehindFront) / 1000.0;
	}

	double FWeatherState::RainRateAt(double X, double Y, double Z, double FrontTime) const
	{
		if (!bStormRain) return Rain >= 1.0 ? 50.0 : 50.0 * Rain * Rain; // the inverse of FStormRain::Amount
		// A real day's storm rains where the radar saw rain, moved with the start like the front.
		if (Day && Day->HasRadar())
		{
			const double R = Day->RadarRate(X - RadarOffsetX, Y - RadarOffsetY, DayStartHour + FrontTime / 3600.0);
			if (R >= 0.0) return R;
		}
		if (!Front.bActive || StormRainScale <= 0.0) return 0.0;
		return FStormRain::RateAt(Front.DistanceAhead(X, Y, FrontTime), Z, Front.AlongFront(X, Y)) * StormRainScale;
	}

	double FWeatherState::RainAt(double X, double Y, double FrontTime) const
	{
		return bStormRain ? FStormRain::Amount(RainRateAt(X, Y, 0.0, FrontTime)) : Rain;
	}

	void FWeatherState::LocalizeStorm(double X, double Y, double FrontTime)
	{
		if (!Front.bActive || !bStormRain) return;
		// W8: the storm's gloom comes with its shelf, not with its timeline: ahead of the front the sun shines (the direct
		// light is FWeatherMap::SunTransmittance's), and the sky darkens as the shelf covers more of it overhead. Before
		// W8 this followed the clock at the start, so a front 7 km off (-SailingStormDelay) already had the boat in gloom.
		const double D = Front.DistanceAhead(X, Y, FrontTime);
		const double Over = StormBuild * FStormShape::Overhead(D);
		CloudCover = std::max(BaseCloudCover, Lerp(Lerp(0.35, 0.95, Over), 0.4, StormClearing));
		CloudDarkness = std::max(BaseCloudDarkness, Lerp(Lerp(0.1, 0.85, Over), 0.15, StormClearing));
		// The air thickens as the front's dust and spray arrive (about 30 s before it to 20 s after, at its speed).
		const double FrontHere = 1.0 - SmoothStep(-20.0 * Front.SpeedMs, 30.0 * Front.SpeedMs, D);
		const double Visibility = Lerp(Lerp(Lerp(25.0, 10.0, FrontHere), 1.5, Rain), 20.0, StormClearing);
		VisibilityKm = std::min(BaseVisibilityKm, Visibility);
		// Under the rain (the core, or a real day's radar) it is dark whatever the shelf is doing.
		CloudDarkness = std::max(CloudDarkness, 0.85 * Rain);
	}

	double FWeatherState::AirTempAt(double X, double Y, double FrontTime) const
	{
		return AirC - Front.TemperatureDropAt(X, Y, FrontTime);
	}

	void FWeatherSystem::ApplyToWind(const FWeatherState& State, FWindField& Wind, double T, double AnchorX, double AnchorY)
	{
		Wind.SetParamsAt(State.Wind, T, AnchorX, AnchorY);
		Wind.SetFront(State.Front);
	}
}
