#include "SeaTrials.h"
#include "AutoTrim.h"
#include "CrewStation.h"
#include "FixedStepper.h"
#include <algorithm>
#include <cmath>
#include <vector>

namespace Sailing
{
	FTrialSeaSpec FTrialSeaSpec::Gale(uint32_t Seed, double Knots, bool bSea)
	{
		FTrialSeaSpec S;
		S.bGale = true;
		S.bGaleSea = bSea;
		S.WindKnots = Knots;
		S.WindFromDeg = 180.0;
		S.Seed = Seed;
		S.FetchMeters = 200.0;
		return S;
	}

	FTrialSea::FTrialSea(const FTrialSeaSpec& InSpec) : Spec(InSpec), Waves(InSpec.bGale ? 3 : 7)
	{
		FromDeg = Spec.WindFromDeg;
		if (Spec.bGale)
		{
			// As the prologue's tests sail it (PrologueTests.cpp FGale): the preset evaluated at the start, scaled to the
			// scene's wind, its sea configured once, the chop on a 200 m fetch.
			Weather.Configure(EWeatherPreset::Mistral, Spec.Seed, Spec.GaleHour);
			Weather.SetClimate(10, true);
			Weather.SetPrevailingFrom(Spec.WindFromDeg);
			Weather.ClearCues();
			FWeatherState State = Weather.Evaluate(0.0);
			Scale = Spec.WindKnots / State.Wind.SpeedKnots;
			State.Wind.SpeedKnots *= Scale;
			FromDeg = State.Wind.FromDegrees;
			Wind = FWindField(State.Wind);
			bWaves = Spec.bGaleSea;
			FOceanParams O;
			O.WindMs = State.Wind.SpeedKnots * kKnot;
			O.WindFromRad = State.Wind.FromDegrees * kDegToRad;
			O.WindSeaHs = State.WindSeaHsM;
			O.WindSeaTp = State.WindSeaTpS;
			O.SwellHs = State.SwellHsM;
			O.SwellTp = State.SwellTpS;
			O.SwellFromRad = State.SwellFromDeg * kDegToRad;
			Ocean = std::make_shared<FOcean>();
			Ocean->Configure(O);
			if (bWaves) Waves.SetOcean(Ocean);
			FWaveParams WP;
			WP.WindSpeedKnots = State.Wind.SpeedKnots;
			WP.WindFromDegrees = State.Wind.FromDegrees;
			WP.FetchMeters = bWaves ? 200.0 : 1.0;
			Waves.SetWind(WP);
			Waves.SnapToTarget();
			return;
		}
		FWindParams WindParams;
		WindParams.SpeedKnots = Spec.WindKnots;
		WindParams.FromDegrees = Spec.WindFromDeg;
		WindParams.GustIntensity = Spec.GustIntensity;
		WindParams.ShiftDegrees = Spec.GustIntensity > 0.0 ? 4.0 : 0.0;
		WindParams.Seed = Spec.Seed;
		Wind = FWindField(WindParams);
		if (Spec.bOcean)
		{
			Ocean = std::make_shared<FOcean>();
			Ocean->Configure(Spec.Ocean);
			Waves.SetOcean(Ocean);
		}
		FWaveParams WaveParams;
		WaveParams.WindSpeedKnots = Spec.WindKnots;
		WaveParams.WindFromDegrees = Spec.WindFromDeg;
		WaveParams.FetchMeters = Spec.FetchMeters;
		WaveParams.bCalibrationSea = Spec.bCalibrationSea;
		Waves.SetWind(WaveParams);
		Waves.SnapToTarget();
	}

	void FTrialSea::Update(double T, double BoatX, double BoatY)
	{
		if (!Spec.bGale || T + 1e-9 < NextWeather) return;
		NextWeather = T + 0.25;
		FWeatherState State = Weather.Evaluate(T);
		State.Wind.SpeedKnots *= Scale;
		FWeatherSystem::ApplyToWind(State, Wind, T, BoatX, BoatY);
		FWaveParams WP;
		WP.WindSpeedKnots = State.Wind.SpeedKnots;
		WP.WindFromDegrees = State.Wind.FromDegrees;
		WP.FetchMeters = bWaves ? 200.0 : 1.0;
		Waves.SetWind(WP);
		Waves.Update(0.25);
	}

	FSeaRunResult RunInSea(const FBoatConfig& Config, const FTrialSeaSpec& SeaSpec, double TwaDeg, int Reefs, bool bSpinnaker, double Settle,
		double Seconds, double FaceSlope)
	{
		FTrialSea Sea(SeaSpec);
		FBoatModel Boat(Config);
		Boat.Reset(0.0, 0.0, Sea.HeadingFor(TwaDeg), 0.6 * SeaSpec.WindKnots * kKnot);
		const int Windward = TwaDeg >= 0.0 ? 1 : -1;
		Boat.GetMutableState().WindwardSide = Windward;
		Boat.GetMutableState().CrewOffset = Windward * Config.CrewSitOut;
		FAutopilot Pilot;
		Pilot.TargetTWADeg = TwaDeg;
		// A sea trial measures the boat in the sea, trimmed as the polars are (ideal hands: docs/trimmer-hands/).
		FAutoTrim Trim;
		Trim.Settings.bHands = false;
		FBoatControls C;
		C.MainSheet = C.JibSheet = Clamp(std::fabs(TwaDeg) / 180.0, 0.0, 1.0);
		C.bSpinnaker = bSpinnaker && Config.HasSpinnaker();
		C.Hike = Clamp((SeaSpec.WindKnots - 6.0) / 6.0, 0.0, 1.0) * (1.0 - SmoothStep(95.0, 115.0, std::fabs(TwaDeg)));
		C.SpinSheet = 0.5;
		C.Reef = Reefs;

		FSeaRunResult R;
		const int SettleSteps = int(Settle * PhysicsHz), Steps = int(Seconds * PhysicsHz);
		const int Window = int(PhysicsHz);
		std::vector<double> Last(Window, 0.0);
		double WindowSum = 0.0, PrevSpeed = 0.0, FaceSum = 0.0, BackSum = 0.0, HsSum = 0.0;
		int Faces = 0, Backs = 0;
		int PhaseCount[5] = {}, SurfSeconds = 0, Seconds1 = 0;
		double FaceErr = 0.0, BackErr = 0.0;
		R.HullSpeedKnots = 1.34 * std::sqrt(Config.WaterlineLength / 0.3048);
		R.MinKnots = 1e9;
		double T = 0.0;
		Vec3 Start;
		for (int I = 0; I < SettleSteps + Steps; ++I, T += PhysicsDt)
		{
			if (I == SettleSteps) Start = Boat.GetState().Position;
			const Vec3 O = Boat.OriginPosition();
			Sea.Update(T, O.X, O.Y);
			C = Trim.Update(Boat, C, PhysicsDt);
			C.Tiller = Pilot.Update(Boat);
			C.Reef = Reefs;
			Boat.Step(PhysicsDt, C, Sea.GetWind(), Sea.GetWaves());
			const FBoatTelemetry& Tm = Boat.GetTelemetry();
			const double Speed = Tm.ForwardSpeed;
			if (I >= SettleSteps)
			{
				const int K = (I - SettleSteps) % Window;
				WindowSum += Tm.BoatSpeed / kKnot - Last[K];
				Last[K] = Tm.BoatSpeed / kKnot;
				if (I - SettleSteps >= Window - 1)
				{
					R.MaxKnots = std::max(R.MaxKnots, WindowSum / Window);
					R.MinKnots = std::min(R.MinKnots, WindowSum / Window);
				}
				if (K == Window - 1)
				{
					++Seconds1;
					SurfSeconds += WindowSum / Window > 1.5 * R.HullSpeedKnots ? 1 : 0;
				}
				R.MeanKnots += Tm.BoatSpeed / kKnot;
				R.MeanCalmN += Tm.CalmResistance;
				R.MeanWaveN += Tm.WaveResistance;
				R.MeanSurgeN += Tm.WaveSlopeSurge;
				R.MeanHeelDeg += std::fabs(Tm.Heel) * kRadToDeg;
				R.MeanTwaDeg += Tm.TrueWindAngle * kRadToDeg;
				R.MaxTiltDeg = std::max(R.MaxTiltDeg, Boat.GetState().Orientation.Tilt() * kRadToDeg);
				R.bCapsized |= Tm.bCapsized;
				const FWaveField* W = Sea.GetWaves();
				if (W)
				{
					// The slope she feels along her course: the waves' push over her weight (the hull's own average of the
					// surface, so chop much shorter than her does not count). Positive = downhill ahead (a face).
					const double Along = Tm.WaveSlopeSurge / (Boat.TotalMass() * kGravity);
					const double Accel = (Speed - PrevSpeed) / PhysicsDt;
					const double Err = std::fabs(Tm.TrueWindAngle * kRadToDeg - TwaDeg);
					if (Along > FaceSlope) { FaceSum += Accel; ++Faces; FaceErr += Err; }
					else if (Along < -FaceSlope) { BackSum += Accel; ++Backs; BackErr += Err; }
					const int Bin = Along < -2.0 * FaceSlope ? 0 : Along < -FaceSlope ? 1 : Along <= FaceSlope ? 2 : Along <= 2.0 * FaceSlope ? 3 : 4;
					R.PhaseKnots[Bin] += Tm.BoatSpeed / kKnot;
					++PhaseCount[Bin];
					if (I % int(PhysicsHz) == 0) HsSum += W->SignificantHeightAt(Boat.GetState().Position.X, Boat.GetState().Position.Y);
				}
			}
			PrevSpeed = Speed;
		}
		const double N = std::max(Steps, 1);
		const Vec3 Made = Boat.GetState().Position - Start;
		R.NetKnots = Made.LengthXY() / std::max(Seconds, 1e-3) / kKnot;
		R.MeanKnots /= N;
		R.MeanCalmN /= N;
		R.MeanWaveN /= N;
		R.MeanSurgeN /= N;
		R.MeanHeelDeg /= N;
		R.MeanTwaDeg /= N;
		R.FaceAccel = Faces ? FaceSum / Faces : 0.0;
		R.BackAccel = Backs ? BackSum / Backs : 0.0;
		R.FaceShare = Faces / N;
		for (int B = 0; B < 5; ++B)
		{
			R.PhaseShare[B] = PhaseCount[B] / N;
			R.PhaseKnots[B] = PhaseCount[B] ? R.PhaseKnots[B] / PhaseCount[B] : 0.0;
		}
		R.SurfShare = Seconds1 ? double(SurfSeconds) / Seconds1 : 0.0;
		R.FaceCourseErrDeg = Faces ? FaceErr / Faces : 0.0;
		R.BackCourseErrDeg = Backs ? BackErr / Backs : 0.0;
		R.Hs = HsSum / std::max(1.0, std::floor(Seconds));
		if (R.MinKnots > 1e8) R.MinKnots = 0.0;
		return R;
	}

	double RunGaleTack(const FBoatConfig& Config, int Reefs, uint32_t Seed, bool bSea, double Knots)
	{
		return RunGaleTackDetail(Config, Reefs, Seed, bSea, Knots).Seconds;
	}

	FGaleTackResult RunGaleTackDetail(const FBoatConfig& Config, int Reefs, uint32_t Seed, bool bSea, double Knots)
	{
		FGaleTackResult R;
		// PrologueTests.cpp TackInGale, plain: the same crew, wheel and clock.
		FTrialSea Gale(FTrialSeaSpec::Gale(Seed, Knots, bSea));
		FBoatModel Boat(Config);
		Boat.Reset(0.0, 0.0, Gale.HeadingFor(55.0), 9.0 * kKnot);
		FStationControls Stations;
		Stations.Config = FStationConfig::For(Boat.GetConfig());
		FBoatControls Sails;
		Sails.Reef = Reefs;
		Stations.Reset(Boat, Sails, ECrewStation::JibTrimmer);
		FAutopilot Hand;
		Hand.TargetTWADeg = 45.0; // the tack she is on until the call
		// Hard, but not past the stall (docs/gale-tack/: at 0.8 of the wheel, 25 deg, the stalled rudder braked her and
		// half the tacks fell under 40% of her speed; at 0.6, 19 deg, 11 of 12 keep it).
		Hand.MaxTiller = 0.6;
		Hand.bKeepShortOfStall = false;
		const double Called = 60.0 + 7.0 * Seed;
		double T = 0.0, Settled = 0.0, Before = 0.0;
		int BeforeN = 0;
		R.MinSpeedKnots = 1e9;
		for (int I = 0; I < int((Called + 90.0) * PhysicsHz); ++I, T += PhysicsDt)
		{
			const Vec3 O = Boat.OriginPosition();
			Gale.Update(T, O.X, O.Y);
			FStationInput In;
			if (T >= Called && Stations.GetStation() != ECrewStation::Helm) { Stations.MoveTo(Boat, ECrewStation::Helm); Stations.CallTack(); Hand.TargetTWADeg = -45.0; }
			// The helm watches her before the call (her upwind speed, for timing the tack) and steers from it.
			const double Wheel = Hand.Update(Boat);
			if (T >= Called) In.Wheel = Clamp((Wheel - Stations.GetControls().Tiller) * 8.0, -1.0, 1.0);
			Boat.Step(PhysicsDt, Stations.Step(Boat, In, PhysicsDt), Gale.GetWind(), Gale.GetWaves());
			const double Knots10 = Boat.GetTelemetry().BoatSpeed / kKnot;
			if (T < Called)
			{
				if (T >= Called - 20.0) { Before += Knots10; ++BeforeN; }
				continue;
			}
			R.MinSpeedKnots = std::min(R.MinSpeedKnots, Knots10);
			const double Twa = Boat.GetTelemetry().TrueWindAngle / kDegToRad;
			Settled = Twa < -30.0 && Twa > -100.0 ? Settled + PhysicsDt : 0.0;
			if (Settled >= 1.0) { R.Seconds = T - Called - 1.0; break; }
		}
		R.SpeedBeforeKnots = BeforeN > 0 ? Before / BeforeN : 0.0;
		return R;
	}

	FTrimHandsResult MeasureTrimHands(const FBoatConfig& Config, double TrueWindKnots, double TwaDeg, double FetchMeters, double GustIntensity,
		double Seconds, bool bHands)
	{
		FTrialSeaSpec Spec;
		Spec.WindKnots = TrueWindKnots;
		Spec.GustIntensity = GustIntensity;
		Spec.FetchMeters = FetchMeters;
		FTrialSea Sea(Spec);
		FBoatModel Boat(Config);
		Boat.Reset(0.0, 0.0, Sea.HeadingFor(TwaDeg), 0.5 * TrueWindKnots * kKnot);
		FAutoTrim Trim;
		Trim.Settings.bHands = bHands;
		FAutopilot Helm;
		Helm.TargetTWADeg = TwaDeg;
		FBoatControls C;
		const double Warm = 60.0;
		FTrimHandsResult R;
		FBoatControls Last;
		int AdjustmentsAtStart = 0, N = 0;
		double T = 0.0;
		for (int I = 0; I < int((Warm + Seconds) * PhysicsHz); ++I, T += PhysicsDt)
		{
			const Vec3 O = Boat.OriginPosition();
			Sea.Update(T, O.X, O.Y);
			C = Trim.Update(Boat, C, PhysicsDt);
			C.Tiller = Helm.Update(Boat);
			Boat.Step(PhysicsDt, C, Sea.GetWind(), Sea.GetWaves());
			if (T < Warm) { Last = C; AdjustmentsAtStart = Trim.GetAdjustments(); continue; }
			R.MainTravelPerMin += std::fabs(C.MainSheet - Last.MainSheet);
			R.TravelerTravelPerMin += std::fabs(C.Traveler - Last.Traveler);
			R.JibTravelPerMin += std::fabs(C.JibSheet - Last.JibSheet);
			R.MeanKnots += Boat.GetTelemetry().BoatSpeed / kKnot;
			++N;
			Last = C;
		}
		const double Minutes = Seconds / 60.0;
		R.MainTravelPerMin /= Minutes;
		R.TravelerTravelPerMin /= Minutes;
		R.JibTravelPerMin /= Minutes;
		R.AdjustmentsPerMin = (Trim.GetAdjustments() - AdjustmentsAtStart) / Minutes;
		R.MeanKnots /= std::max(N, 1);
		return R;
	}
}
