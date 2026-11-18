#include "ShipSailPlans.h"
#include "AutoTrim.h"
#include "FixedStepper.h"
#include "Waves.h"
#include "Wind.h"
#include <algorithm>
#include <cmath>

namespace Sailing
{
	namespace
	{
		const FShipSailPlan kShipSailPlans[] = {
			{ "all plain sail", true, true, 0, true, true, true, true },
			{ "royals in", false, true, 0, true, true, true, true },
			{ "topgallants in", false, false, 0, true, true, true, true },
			{ "single-reefed topsails", false, false, 1, true, true, false, true },
			{ "double-reefed topsails", false, false, 2, true, true, false, true },
			{ "close-reefed topsails, courses in", false, false, 4, false, false, false, true },
		};
		constexpr int kNumShipSailPlans = int(sizeof(kShipSailPlans) / sizeof(kShipSailPlans[0]));
	}

	int NumShipSailPlans() { return kNumShipSailPlans; }

	const FShipSailPlan& ShipSailPlan(int Plan) { return kShipSailPlans[std::clamp(Plan, 0, kNumShipSailPlans - 1)]; }

	void ApplyShipSailPlan(const FBoatConfig& C, int Plan, FBoatControls& Controls, bool bRunning)
	{
		const FShipSailPlan& P = ShipSailPlan(Plan);
		for (int I = 0; I < int(C.Square.Sails.size()) && I < kMaxSquareSails; ++I)
		{
			const ESquareSailKind K = C.Square.Sails[I].Kind;
			const bool bSet = K == ESquareSailKind::Royal ? P.bRoyals : K == ESquareSailKind::Topgallant ? P.bTopgallants
				: K == ESquareSailKind::Course ? P.bCourses : true;
			Controls.SquareSet[I] = bSet ? ESailSet::Set : ESailSet::Clewed;
			Controls.SquareReef[I] = K == ESquareSailKind::Topsail
				? (unsigned char)std::min<int>(P.TopsailReef, int(C.Square.Sails[I].ReefAreaFraction.size())) : 0;
		}
		Controls.bMainDown = !P.bSpanker || bRunning;
		Controls.bJibDown = !P.bJib;
		Controls.bStaysailDown = !P.bStaysails;
	}

	FShipSteadyResult SailShipPlan(const FBoatConfig& C, double Tws, double Twa, int Plan, double Settle, double Average,
		const std::function<void(const FBoatModel&)>& OnStep)
	{
		FWindParams WindParams;
		WindParams.SpeedKnots = Tws;
		WindParams.FromDegrees = 0.0;
		const FWindField Wind(WindParams);
		FWaveField Waves(7);
		FWaveParams WaveParams;
		WaveParams.WindSpeedKnots = Tws;
		WaveParams.FetchMeters = kPolarFetchMeters;
		WaveParams.bCalibrationSea = true;
		Waves.SetWind(WaveParams);
		Waves.SnapToTarget();
		FBoatModel Boat(C);
		// Her speed at the start: about what the period's logs give, so the long settle is spent settling, not accelerating.
		Boat.Reset(0.0, 0.0, -Twa * kDegToRad, std::min(0.45 * Tws, 11.0) * kKnot);
		Boat.GetMutableState().WindwardSide = 1;
		FAutopilot Pilot;
		Pilot.TargetTWADeg = Twa;
		FAutoTrim Trim;
		Trim.Settings.bHands = false;
		Trim.Settings.bHike = false;
		FBoatControls Ctl;
		Ctl.MainSheet = Ctl.JibSheet = Clamp(Twa / 180.0, 0.0, 1.0);
		ApplyShipSailPlan(C, Plan, Ctl, Twa > 155.0);
		// The yards already braced for the course (the crew had them round before she bore away).
		for (int M = 0; M < kMaxMasts; ++M) Ctl.Brace[M] = BraceForAlpha(C.Square, M, std::max(Twa - 15.0, 20.0) * kDegToRad, 20.0);
		for (int I = 0; I < int(C.Square.Sails.size()) && I < kMaxSquareSails; ++I)
		{
			Boat.GetMutableState().YardAngle[I] = YardAngleFor(C.Square, I, Ctl.Brace[C.Square.Sails[I].Mast]);
			Boat.GetMutableState().SquareOut[I] = Ctl.SquareSet[I] == ESailSet::Set ? 1.0 : 0.0;
		}
		FShipSteadyResult Out;
		Out.Plan = Plan;
		const int SettleSteps = int(Settle * PhysicsHz), AverageSteps = std::max(int(Average * PhysicsHz), 1);
		double SumSq = 0.0;
		for (int I = 0; I < SettleSteps + AverageSteps; ++I)
		{
			Ctl = Trim.Update(Boat, Ctl, PhysicsDt);
			Ctl.Tiller = Pilot.Update(Boat);
			Boat.Step(PhysicsDt, Ctl, Wind, &Waves);
			if (OnStep) OnStep(Boat);
			if (I < SettleSteps) continue;
			const FBoatTelemetry& T = Boat.GetTelemetry();
			const FBoatState& S = Boat.GetState();
			const double Speed = T.BoatSpeed / kKnot;
			Out.R.BoatSpeedKnots += Speed;
			SumSq += Speed * Speed;
			Out.R.HeelDeg += std::fabs(T.Heel) * kRadToDeg;
			Out.R.LeewayDeg += std::fabs(T.Leeway) * kRadToDeg;
			Out.R.RudderDeg += -T.RudderAngle * kRadToDeg * (T.TrueWindAngle > 0.0 ? 1.0 : -1.0);
			Out.R.HelmForceN += T.HelmForce;
			Out.R.TrueWindAngleDeg += T.TrueWindAngle * kRadToDeg;
			for (int M = 0; M < kMaxMasts; ++M)
			{
				const int L = C.Square.LowestOn(M);
				if (L < 0 || L >= T.NumSquareSails) continue;
				Out.YardDeg[M] += S.YardAngle[L] * kRadToDeg;
				Out.AlphaDeg[M] += T.SquareStrips[L].AlphaN * kRadToDeg;
			}
		}
		const double N = AverageSteps;
		Out.R.BoatSpeedKnots /= N;
		Out.R.SpeedStdDev = std::sqrt(std::max(0.0, SumSq / N - Out.R.BoatSpeedKnots * Out.R.BoatSpeedKnots));
		Out.R.HeelDeg /= N;
		Out.R.LeewayDeg /= N;
		Out.R.RudderDeg /= N;
		Out.R.HelmForceN /= N;
		Out.R.TrueWindAngleDeg /= N;
		for (int M = 0; M < kMaxMasts; ++M) { Out.YardDeg[M] /= N; Out.AlphaDeg[M] /= N; }
		return Out;
	}

	FShipSteadyResult SailShipSteady(const FBoatConfig& C, double Tws, double Twa, double Settle, double Average)
	{
		FShipSteadyResult Best;
		bool bHave = false;
		for (int P = 0; P < kNumShipSailPlans; ++P)
		{
			const FShipSteadyResult R = SailShipPlan(C, Tws, Twa, P, Settle, Average);
			const bool bOk = R.R.HeelDeg <= ShipHeelCapDeg(C);
			if (bOk && (!bHave || R.R.BoatSpeedKnots > Best.R.BoatSpeedKnots)) { Best = R; bHave = true; }
			if (!bHave && (P == 0 || R.R.HeelDeg < Best.R.HeelDeg)) Best = R;
			// Each plan carries less canvas: once one is under the cap and slower than the best, the rest are slower still.
			if (bHave && bOk && R.R.BoatSpeedKnots < Best.R.BoatSpeedKnots - 0.05) break;
		}
		return Best;
	}
}
