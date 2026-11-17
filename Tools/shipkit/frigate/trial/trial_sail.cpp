// The frigate Commonwealth's trial sail in the standalone physics (docs/frigate-physics). Nothing here is game code: it
// builds an FBoatConfig from the sheet physics.py writes (commonwealth_trial.inl, CommonwealthHullData.inl in the build
// dir) and sails her the way the fleet's reference polars are sailed (the polar's lake chop, the autopilot, ideal trim:
// FAutoTrim braces each mast's yards), under each of a frigate's sail plans, keeping the fastest one her officers would
// carry (heel under the cap). Build and run with trial.sh.
//
//   trial_sail <out json> [--quick | --point <tws> <twa> [plan]]
//
// Prints and writes: her mass and centre of gravity as the physics builds them, how she floats at rest, her righting
// moments, her speed at the estimated polar's points, her best beat and run VMGs, and how close to the wind her yards
// let her sail (the brace limits' question).
#include "BoatModel.h"
#include "PolarReference.h"
#include "FixedStepper.h"
#include "Wind.h"
#include "AutoTrim.h"
#include "Waves.h"
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

// The fleet's config helpers (Fleet.cpp's, which are file-local there).
namespace
{
	using namespace Sailing;

	FFoilDef Foil(EFoilRole Role, Vec3 Center, double Area, double Chord, double AspectRatio, double StallDeg)
	{
		FFoilDef F;
		F.Role = Role;
		F.Params.Center = Center;
		F.Params.Area = Area;
		F.Params.Chord = Chord;
		F.Params.EffectiveAspectRatio = AspectRatio;
		F.Params.StallAngleDeg = StallDeg;
		F.Params.ProfileDrag = 0.009;
		if (Role == EFoilRole::Rudder) { F.VentStartDeg = 30.0; F.VentEndDeg = 55.0; F.VentDepth = 0.8; }
		return F;
	}

	void SetMain(FBoatConfig& C, double FootZ, double HeadZ, double FootChord, double HeadChord, double Roach, double LuffX, double LuffXHead,
		double Area, double LiftSlope, double AspectRatio, double Camber)
	{
		C.MainFootZ = FootZ; C.MainHeadZ = HeadZ; C.MainFootChord = FootChord; C.MainHeadChord = HeadChord; C.MainRoach = Roach;
		C.MainLuffX = LuffX; C.MainLuffXHead = LuffXHead; C.MainArea = Area;
		C.BoomZ = FootZ;
		C.Main.NumStrips = 4;
		C.BuildMain(0);
		C.Main.LiftSlope = LiftSlope;
		C.Main.InducedAspectRatio = AspectRatio;
		C.Main.BaseCamber = Camber;
	}

	void SetSail(FSailGeometry& S, double FootZ, double HeadZ, double FootChord, double HeadChord, double LuffXFoot, double LuffXHead,
		double Area, double LiftSlope, double AspectRatio, double Camber)
	{
		BuildSail(S, 4, FootZ, HeadZ, FootChord, HeadChord, 0.0, LuffXFoot, LuffXHead, Area);
		S.LiftSlope = LiftSlope;
		S.InducedAspectRatio = AspectRatio;
		S.BaseCamber = Camber;
	}

#include "CommonwealthHullData.inl"
#include "commonwealth_trial.inl"

	FBoatConfig Commonwealth()
	{
		// From the J/22's defaults like every boat of the fleet, as the maxi's type (a big wheel-steered ship: the type
		// only names her here; the boat type comes with her Source step).
		FBoatConfig C;
		C.Type = EBoatType::Maxi;
		ApplyCommonwealth(C);
		return C;
	}

	// TRIAL_SET="name=value,..." overrides a knob for a tuning run without rebuilding the sheet: keel_x, keel_ar,
	// rudder_area, downwash, heel_yaw, munk, yaw_damping, residuary (a factor on the table), brace (lower yards' limit,
	// deg, all masts), upper_brace (topsails' and topgallants' limit), camber, ar, running_cd.
	void ApplyOverrides(FBoatConfig& C)
	{
		const char* Env = std::getenv("TRIAL_SET");
		if (!Env) return;
		std::string S(Env);
		size_t At = 0;
		while (At < S.size())
		{
			const size_t End = std::min(S.find(',', At), S.size());
			const std::string Item = S.substr(At, End - At);
			At = End + 1;
			const size_t Eq = Item.find('=');
			if (Eq == std::string::npos) continue;
			const std::string K = Item.substr(0, Eq);
			const double V = std::atof(Item.c_str() + Eq + 1);
			for (FFoilDef& F : C.Foils)
			{
				const bool bKeel = F.Role == EFoilRole::Keel;
				if (bKeel && K == "keel_x") F.Params.Center.X = V;
				if (bKeel && K == "keel_ar") F.Params.EffectiveAspectRatio = V;
				if (!bKeel && K == "rudder_area") F.Params.Area = V;
			}
			for (FSquareSailDef& Q : C.Square.Sails)
			{
				const bool bLow = C.Square.LowestOn(Q.Mast) >= 0 && &C.Square.Sails[C.Square.LowestOn(Q.Mast)] == &Q;
				if (K == "brace" && bLow) Q.BraceLimitDeg = V;
				if (K == "upper_brace" && !bLow) Q.BraceLimitDeg = std::max(Q.BraceLimitDeg, V);
			}
			if (K == "downwash") C.KeelDownwashFactor = V;
			if (K == "heel_yaw") C.HeelYawCoef = V;
			if (K == "munk") C.MunkAddedMass = V;
			if (K == "yaw_damping") C.YawDampingLinear = V;
			if (K == "residuary") for (auto& R : C.Residuary) R.second *= V;
			if (K == "camber") C.Square.Camber = V;
			if (K == "ar") C.Square.AspectRatio = V;
			if (K == "running_cd") C.Square.RunningCD = V;
			if (K == "luff") C.Square.LuffDeg = V;
			std::printf("override %s = %g\n", K.c_str(), V);
		}
	}

	// A frigate's sail plans, from all plain sail down: what her officers took in as the wind rose.
	struct FPlan { const char* Name; bool bRoyals, bTopgallants; int TopsailReef; bool bCourses, bJib, bStaysails, bSpanker; };
	const FPlan kPlans[] = {
		{ "all plain sail", true, true, 0, true, true, true, true },
		{ "royals in", false, true, 0, true, true, true, true },
		{ "topgallants in", false, false, 0, true, true, true, true },
		{ "single-reefed topsails", false, false, 1, true, true, false, true },
		{ "double-reefed topsails", false, false, 2, true, true, false, true },
		{ "close-reefed topsails, courses in", false, false, 4, false, false, false, true },
	};
	constexpr int kNumPlans = int(sizeof(kPlans) / sizeof(kPlans[0]));

	void ApplyPlan(const FBoatConfig& C, const FPlan& P, FBoatControls& Ctl, bool bRunning)
	{
		for (int I = 0; I < int(C.Square.Sails.size()) && I < kMaxSquareSails; ++I)
		{
			const ESquareSailKind K = C.Square.Sails[I].Kind;
			const bool bSet = K == ESquareSailKind::Royal ? P.bRoyals : K == ESquareSailKind::Topgallant ? P.bTopgallants
				: K == ESquareSailKind::Course ? P.bCourses : true;
			Ctl.SquareSet[I] = bSet ? ESailSet::Set : ESailSet::Clewed;
			Ctl.SquareReef[I] = K == ESquareSailKind::Topsail ? (unsigned char)std::min<int>(P.TopsailReef, int(C.Square.Sails[I].ReefAreaFraction.size())) : 0;
		}
		// Before the wind the spanker is brailed up (it only blankets the main and makes her gripe).
		Ctl.bMainDown = !P.bSpanker || bRunning;
		Ctl.bJibDown = !P.bJib;
		Ctl.bStaysailDown = !P.bStaysails;
	}

	struct FRun { FSteadyResult R; int Plan = 0; double Yard[kMaxMasts] = { 0, 0, 0 }; double Alpha[kMaxMasts] = { 0, 0, 0 }; };

	FRun SailPlan(const FBoatConfig& C, double Tws, double Twa, int Plan, double Settle, double Average, bool bTrace = false)
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
		ApplyPlan(C, kPlans[Plan], Ctl, Twa > 155.0);
		// The yards already braced for the course (the crew had them round before she bore away).
		for (int M = 0; M < kMaxMasts; ++M) Ctl.Brace[M] = BraceForAlpha(C.Square, M, std::max(Twa - 15.0, 20.0) * kDegToRad, 20.0);
		for (int I = 0; I < int(C.Square.Sails.size()); ++I)
		{
			Boat.GetMutableState().YardAngle[I] = YardAngleFor(C.Square, I, Ctl.Brace[C.Square.Sails[I].Mast]);
			Boat.GetMutableState().SquareOut[I] = Ctl.SquareSet[I] == ESailSet::Set ? 1.0 : 0.0;
		}
		FRun Out;
		Out.Plan = Plan;
		const int SettleSteps = int(Settle * PhysicsHz), AverageSteps = int(Average * PhysicsHz);
		double SumSq = 0.0;
		for (int I = 0; I < SettleSteps + AverageSteps; ++I)
		{
			Ctl = Trim.Update(Boat, Ctl, PhysicsDt);
			Ctl.Tiller = Pilot.Update(Boat);
			Boat.Step(PhysicsDt, Ctl, Wind, &Waves);
			const FBoatTelemetry& T = Boat.GetTelemetry();
			const FBoatState& S = Boat.GetState();
			if (bTrace && I % int(10.0 * PhysicsHz) == 0)
			{
				std::printf("t %4.0f  %5.2f kn  TWA %6.1f  AWA %5.1f  heel %5.1f  leeway %4.1f  rudder %+5.1f  drive %7.0f  heeling %8.0f  calm %7.0f  Fn %.3f  yards",
					S.Time, T.BoatSpeed / kKnot, T.TrueWindAngle * kRadToDeg, T.ApparentWindAngle * kRadToDeg, T.Heel * kRadToDeg, T.Leeway * kRadToDeg,
					T.RudderAngle * kRadToDeg, T.DriveForce, T.HeelingForce, T.CalmResistance, T.Froude);
				for (int Q = 0; Q < T.NumSquareSails; ++Q)
				{
					const FSailStripState& St = T.SquareStrips[Q];
					std::printf(" %s%.0f/%.0f", Q > 0 && C.Square.Sails[Q].Mast != C.Square.Sails[Q - 1].Mast ? "| " : "", S.YardAngle[Q] * kRadToDeg, St.AlphaN * kRadToDeg);
				}
				std::printf("\n");
			}
			if (I < SettleSteps) continue;
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
				if (L < 0) continue;
				Out.Yard[M] += S.YardAngle[L] * kRadToDeg;
				Out.Alpha[M] += T.SquareStrips[L].AlphaN * kRadToDeg;
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
		for (int M = 0; M < kMaxMasts; ++M) { Out.Yard[M] /= N; Out.Alpha[M] /= N; }
		return Out;
	}

	// The heel her officers sailed her to: past it the light sails came in (physics_frigate.json's trim heel limit).
	double HeelCap(const FBoatConfig& C) { return C.TrimHeelLimitDeg + 2.0; }

	// The fastest plan she carries under the heel cap (the most canvas first; the light sails come in as she heels).
	FRun Sail(const FBoatConfig& C, double Tws, double Twa, bool bQuick)
	{
		const double Settle = bQuick ? 120.0 : 180.0, Average = bQuick ? 20.0 : 40.0;
		FRun Best;
		bool bHave = false;
		for (int P = 0; P < kNumPlans; ++P)
		{
			const FRun R = SailPlan(C, Tws, Twa, P, Settle, Average);
			const bool bOk = R.R.HeelDeg <= HeelCap(C);
			if (bOk && (!bHave || R.R.BoatSpeedKnots > Best.R.BoatSpeedKnots)) { Best = R; bHave = true; }
			if (!bHave && (P == 0 || R.R.HeelDeg < Best.R.HeelDeg)) Best = R;
			// Each plan carries less canvas: once one is under the cap and slower than the best, the rest are slower still.
			if (bHave && bOk && R.R.BoatSpeedKnots < Best.R.BoatSpeedKnots - 0.05) break;
		}
		return Best;
	}

	std::string Num(double V) { char B[32]; std::snprintf(B, sizeof(B), "%.4g", V); return B; }

	struct FPoint { double Tws, Twa; FRun R; bool bAtEnd; };
}

int main(int Argc, char** Argv)
{
	if (Argc < 2) { std::printf("usage: trial_sail <out json> [--quick | --point <tws> <twa> [plan]]\n"); return 2; }
	const bool bQuick = Argc > 2 && std::strcmp(Argv[2], "--quick") == 0;
	FBoatConfig C = Commonwealth();
	ApplyOverrides(C);
	if (Argc > 4 && std::strcmp(Argv[2], "--point") == 0)
	{
		const int Plan = Argc > 5 ? std::atoi(Argv[5]) : 0;
		const FRun R = SailPlan(C, std::atof(Argv[3]), std::atof(Argv[4]), Plan, 240.0, 40.0, true);
		std::printf("%s: %.2f kn at TWA %.1f, heel %.1f, leeway %.1f, rudder %+.1f; lower yards %.1f %.1f %.1f deg, alpha %.1f %.1f %.1f\n",
			kPlans[Plan].Name, R.R.BoatSpeedKnots, R.R.TrueWindAngleDeg, R.R.HeelDeg, R.R.LeewayDeg, R.R.RudderDeg, R.Yard[0], R.Yard[1], R.Yard[2],
			R.Alpha[0], R.Alpha[1], R.Alpha[2]);
		return 0;
	}
	std::string J = "{\n";

	// Statics: what the physics makes of the sheet.
	{
		FBoatModel Boat(C);
		const Vec3 Cg = Boat.GetCenterOfGravity();
		const Vec3 Cb = Boat.DesignBuoyancyCentre();
		std::printf("mass %.0f kg, CG (%.3f, %.3f, %.3f); canoe depth %.4f m against the sections' %.4f; design canoe volume %.2f m^3, "
			"centre (%.3f, %.3f); capsize tilt %.0f deg\n", Boat.TotalMass(), Cg.X, Cg.Y, Cg.Z, Boat.HullDepth(), C.Hulls[0].StationDepth,
			Boat.DesignDisplacedVolume(), Cb.X, Cb.Z, Boat.CapsizeTilt() * kRadToDeg);
		J += "\"mass_kg\": " + Num(Boat.TotalMass()) + ", \"cg\": [" + Num(Cg.X) + ", " + Num(Cg.Y) + ", " + Num(Cg.Z) + "],\n";
		J += "\"canoe_depth_m\": " + Num(Boat.HullDepth()) + ", \"station_depth_m\": " + Num(C.Hulls[0].StationDepth) + ",\n";
		J += "\"design_canoe_volume_m3\": " + Num(Boat.DesignDisplacedVolume()) + ", \"design_canoe_centre\": [" + Num(Cb.X) + ", "
			+ Num(Cb.Z) + "], \"capsize_tilt_deg\": " + Num(Boat.CapsizeTilt() * kRadToDeg) + ",\n";

		// At rest: two minutes in no wind on flat water, sails furled.
		FWindParams Calm;
		Calm.SpeedKnots = 0.0;
		const FWindField Wind(Calm);
		Boat.Reset(0.0, 0.0, 0.0, 0.0);
		FBoatControls Controls;
		for (int I = 0; I < int(120.0 * PhysicsHz); ++I) Boat.Step(PhysicsDt, Controls, Wind);
		const FBoatTelemetry& T = Boat.GetTelemetry();
		const double Sink = -Boat.OriginPosition().Z;
		std::printf("at rest: heel %.2f deg, pitch %.2f deg, origin %.3f m below the water\n", T.Heel * kRadToDeg, T.Pitch * kRadToDeg, Sink);
		J += "\"rest\": {\"heel_deg\": " + Num(T.Heel * kRadToDeg) + ", \"pitch_deg\": " + Num(T.Pitch * kRadToDeg) + ", \"sink_m\": " + Num(Sink) + "},\n";

		J += "\"righting\": [";
		const double W = Boat.TotalMass() * kGravity;
		bool bFirst = true;
		for (double Deg : { 2.0, 5.0, 10.0, 15.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0 })
		{
			const double M = Boat.RightingMomentAt(Deg * kDegToRad);
			std::printf("  heel %3.0f: righting %9.0f kN m, GZ %.3f m\n", Deg, M / 1000.0, M / W);
			J += std::string(bFirst ? "" : ", ") + "[" + Num(Deg) + ", " + Num(M) + ", " + Num(M / W) + "]";
			bFirst = false;
		}
		J += "],\n";
	}

	// The estimated polar's points, and searches for the best beat and run.
	std::vector<FPoint> Jobs;
	const std::vector<double> Winds = bQuick ? std::vector<double>{ 8.0, 16.0 } : std::vector<double>{ 8.0, 12.0, 16.0, 20.0, 24.0 };
	const std::vector<double> Angles = bQuick ? std::vector<double>{ 80.0, 110.0, 150.0 } : std::vector<double>{ 70.0, 80.0, 90.0, 110.0, 135.0, 160.0, 180.0 };
	for (double Tws : Winds)
	for (double Twa : Angles)
		Jobs.push_back({ Tws, Twa, {}, false });
	const size_t NumGrid = Jobs.size();
	const double kBeatFrom = 56.0, kBeatTo = 100.0, kRunFrom = 140.0, kRunTo = 180.0;
	for (double Tws : Winds)
	{
		for (double Twa = kBeatFrom; Twa <= kBeatTo; Twa += bQuick ? 8.0 : 4.0) Jobs.push_back({ Tws, Twa, {}, false });
		for (double Twa = kRunFrom; Twa <= kRunTo; Twa += 10.0) Jobs.push_back({ Tws, Twa, {}, false });
	}
	std::atomic<size_t> Next(0);
	std::vector<std::thread> Workers;
	const unsigned NumThreads = std::max(1u, std::thread::hardware_concurrency());
	for (unsigned W = 0; W < NumThreads; ++W)
	{
		Workers.emplace_back([&]()
		{
			for (size_t I = Next++; I < Jobs.size(); I = Next++) Jobs[I].R = Sail(C, Jobs[I].Tws, Jobs[I].Twa, bQuick);
		});
	}
	for (std::thread& T : Workers) T.join();

	auto Line = [&](const FPoint& P)
	{
		std::printf("TWS %4.1f TWA %5.1f: %5.2f kn (sailed at %5.1f, sd %.2f), heel %4.1f, leeway %4.1f, rudder %+5.1f (+ weather), lower yards %4.1f %4.1f %4.1f deg, "
			"alpha %4.1f %4.1f %4.1f; %s\n", P.Tws, P.Twa, P.R.R.BoatSpeedKnots, P.R.R.TrueWindAngleDeg, P.R.R.SpeedStdDev, P.R.R.HeelDeg, P.R.R.LeewayDeg,
			P.R.R.RudderDeg, P.R.Yard[0], P.R.Yard[1], P.R.Yard[2], P.R.Alpha[0], P.R.Alpha[1], P.R.Alpha[2], kPlans[P.R.Plan].Name);
	};
	const std::vector<FPoint> Points(Jobs.begin(), Jobs.begin() + NumGrid);
	for (const FPoint& P : Points) Line(P);
	std::vector<FPoint> Beat, Run;
	for (double Tws : Winds)
	{
		FPoint BestB{ Tws, 0.0, {}, false }, BestR{ Tws, 0.0, {}, false };
		double VB = -1e9, VR = -1e9;
		for (size_t I = NumGrid; I < Jobs.size(); ++I)
		{
			const FPoint& P = Jobs[I];
			if (P.Tws != Tws) continue;
			const double V = P.R.R.BoatSpeedKnots * std::cos(P.R.R.TrueWindAngleDeg * kDegToRad);
			if (P.Twa <= kBeatTo && V > VB) { VB = V; BestB = P; }
			if (P.Twa >= kRunFrom && -V > VR) { VR = -V; BestR = P; }
		}
		BestB.bAtEnd = BestB.Twa == kBeatFrom || BestB.Twa == kBeatTo;
		BestR.bAtEnd = BestR.Twa == kRunFrom;
		std::printf("TWS %4.1f: beat VMG %.2f kn at TWA %.0f (%.2f kn, heel %.1f, leeway %.1f, %s)%s; run VMG %.2f kn at TWA %.0f (%.2f kn)%s\n",
			Tws, VB, BestB.R.R.TrueWindAngleDeg, BestB.R.R.BoatSpeedKnots, BestB.R.R.HeelDeg, BestB.R.R.LeewayDeg, kPlans[BestB.R.Plan].Name,
			BestB.bAtEnd ? " AT THE SEARCH'S END" : "", VR, BestR.R.R.TrueWindAngleDeg, BestR.R.R.BoatSpeedKnots, BestR.bAtEnd ? " AT THE SEARCH'S END" : "");
		Beat.push_back(BestB);
		Run.push_back(BestR);
	}
	auto Row = [](const FPoint& P)
	{
		return "{\"tws\": " + Num(P.Tws) + ", \"twa\": " + Num(P.Twa) + ", \"speed\": " + Num(P.R.R.BoatSpeedKnots) + ", \"heel\": " + Num(P.R.R.HeelDeg)
			+ ", \"leeway\": " + Num(P.R.R.LeewayDeg) + ", \"rudder\": " + Num(P.R.R.RudderDeg) + ", \"helm_n\": " + Num(P.R.R.HelmForceN)
			+ ", \"twa_sailed\": " + Num(P.R.R.TrueWindAngleDeg) + ", \"vmg\": " + Num(std::fabs(P.R.R.BoatSpeedKnots * std::cos(P.R.R.TrueWindAngleDeg * kDegToRad)))
			+ ", \"plan\": \"" + kPlans[P.R.Plan].Name + "\", \"lower_yards_deg\": [" + Num(P.R.Yard[0]) + ", " + Num(P.R.Yard[1]) + ", " + Num(P.R.Yard[2])
			+ "], \"lower_alpha_deg\": [" + Num(P.R.Alpha[0]) + ", " + Num(P.R.Alpha[1]) + ", " + Num(P.R.Alpha[2]) + "]"
			+ (P.bAtEnd ? ", \"at_search_end\": true" : "") + "}";
	};
	auto List = [&](const char* Name, const std::vector<FPoint>& V, bool bLast)
	{
		std::string S = std::string("\"") + Name + "\": [\n";
		for (size_t I = 0; I < V.size(); ++I) S += " " + Row(V[I]) + (I + 1 < V.size() ? ",\n" : "\n");
		return S + "]" + (bLast ? "\n" : ",\n");
	};
	J += List("points", Points, false) + List("beat", Beat, false) + List("run", Run, true) + "}\n";
	if (FILE* F = std::fopen(Argv[1], "w")) { std::fputs(J.c_str(), F); std::fclose(F); }
	return 0;
}
