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
		FAutoTrim Trim;
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
					if (Along > FaceSlope) { FaceSum += Accel; ++Faces; }
					else if (Along < -FaceSlope) { BackSum += Accel; ++Backs; }
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
		R.Hs = HsSum / std::max(1.0, std::floor(Seconds));
		if (R.MinKnots > 1e8) R.MinKnots = 0.0;
		return R;
	}

	double RunGaleTack(const FBoatConfig& Config, int Reefs, uint32_t Seed, bool bSea, double Knots)
	{
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
		Hand.TargetTWADeg = -45.0;
		Hand.MaxTiller = 0.8;
		Hand.bKeepShortOfStall = false;
		const double Called = 60.0 + 7.0 * Seed;
		double T = 0.0, Settled = 0.0;
		for (int I = 0; I < int((Called + 90.0) * PhysicsHz); ++I, T += PhysicsDt)
		{
			const Vec3 O = Boat.OriginPosition();
			Gale.Update(T, O.X, O.Y);
			FStationInput In;
			if (T >= Called && Stations.GetStation() != ECrewStation::Helm) Stations.MoveTo(Boat, ECrewStation::Helm);
			if (T >= Called) In.Wheel = Clamp((Hand.Update(Boat) - Stations.GetControls().Tiller) * 8.0, -1.0, 1.0);
			Boat.Step(PhysicsDt, Stations.Step(Boat, In, PhysicsDt), Gale.GetWind(), Gale.GetWaves());
			if (T < Called) continue;
			const double Twa = Boat.GetTelemetry().TrueWindAngle / kDegToRad;
			Settled = Twa < -30.0 && Twa > -100.0 ? Settled + PhysicsDt : 0.0;
			if (Settled >= 1.0) return T - Called - 1.0;
		}
		return -1.0;
	}
}
