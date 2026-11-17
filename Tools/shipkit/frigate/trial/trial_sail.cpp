// The frigate Commonwealth's trial sail in the standalone physics (docs/frigate-physics). Nothing here is game code: it
// builds an FBoatConfig from the sheet physics.py writes (commonwealth_trial.inl, CommonwealthHullData.inl in the build
// dir) and sails her the way the fleet's reference polars are sailed (the polar's lake chop, the autopilot, ideal trim:
// FAutoTrim braces each mast's yards), under each of a frigate's sail plans, keeping the fastest one her officers would
// carry (heel under the cap). Build and run with trial.sh.
//
//   trial_sail <out json> [--quick | --point <tws> <twa> [plan] | --manoeuvre <tack|wear|heaveto> <tws> [plan] [seed]]
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
#include "ShipHandling.h"
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

	// The manoeuvres' settings (TRIAL_SET's mainsail_haul, let_go, rise_tacks, draw_alpha).
	FShipHandlingSettings gHandling;

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
			if (K == "mainsail_haul") gHandling.MainsailHaulDeg = V;
			if (K == "let_go") gHandling.LetGoDeg = V;
			if (K == "rise_tacks") gHandling.RiseTacksDeg = V;
			if (K == "draw_alpha") gHandling.DrawAlphaDeg = V;
			if (K == "let_go_latest") gHandling.LetGoLatestDeg = V;
			if (K == "brail") gHandling.bBrailToPayOff = V > 0.5;
			if (K == "main_haul_brace") gHandling.MainHaulBrace = V;
			if (K == "hove_share") gHandling.HoveToBraceShare = V;
			if (K == "hove_twa") gHandling.HoveToTwaDeg = V;
			if (K == "hove_spanker") gHandling.HoveToSpankerSheet = V;
			if (K == "pilot_max") gHandling.PilotMaxTiller = V;
			if (K == "downwash") C.KeelDownwashFactor = V;
			if (K == "slope") C.WaveSlopeForceScale = V;
			if (K == "foil_lag") C.FoilLiftLagScale = V;
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

	// docs/frigate-physics/: a manoeuvre by orders (ShipHandling.h) from close-hauled on the starboard tack, settled for
	// three minutes; prints her every 5 s and what it cost. Returns the seconds to Done (-1 if she never finished).
	struct FManoeuvreResult { double ToWind = -1, Through = -1, Done = -1, MinSpeed = 1e9, SpeedBefore = 0, SpeedAfter = 0, Leeward = 0; bool bMissed = false; };
	FManoeuvreResult SailManoeuvre(const FBoatConfig& C, EShipManoeuvre What, double Tws, int Plan, int Seed, bool bPrint)
	{
		FWindParams WindParams;
		WindParams.SpeedKnots = Tws;
		WindParams.FromDegrees = 0.0;
		const FWindField Wind(WindParams);
		FWaveField Waves(7 + Seed);
		FWaveParams WaveParams;
		WaveParams.WindSpeedKnots = Tws;
		WaveParams.FetchMeters = kPolarFetchMeters;
		WaveParams.bCalibrationSea = true;
		Waves.SetWind(WaveParams);
		Waves.SnapToTarget();
		const double Twa = 67.5;
		FBoatModel Boat(C);
		Boat.Reset(0.0, 0.0, -Twa * kDegToRad, std::min(0.4 * Tws, 9.0) * kKnot);
		Boat.GetMutableState().WindwardSide = 1;
		FAutopilot Pilot;
		Pilot.TargetTWADeg = Twa;
		FAutoTrim Trim;
		Trim.Settings.bHands = false;
		Trim.Settings.bHike = false;
		FBoatControls Ctl;
		Ctl.MainSheet = Ctl.JibSheet = Twa / 180.0;
		ApplyPlan(C, kPlans[Plan], Ctl, false);
		for (int M = 0; M < kMaxMasts; ++M) Ctl.Brace[M] = 1.0;
		for (int I = 0; I < int(C.Square.Sails.size()); ++I)
		{
			Boat.GetMutableState().YardAngle[I] = YardAngleFor(C.Square, I, 1.0);
			Boat.GetMutableState().SquareOut[I] = Ctl.SquareSet[I] == ESailSet::Set ? 1.0 : 0.0;
		}
		FShipHandling H;
		H.Settings = gHandling;
		FManoeuvreResult Out;
		const double Settle = 180.0, Limit = 900.0;
		double SpeedSum = 0.0, Y0 = 0.0; int SpeedN = 0;
		const Vec3 WindFrom(1.0, 0.0, 0.0); // the wind from the north (+X): to leeward is -X
		bool bStarted = false;
		for (int I = 0; I < int((Settle + Limit) * PhysicsHz); ++I)
		{
			const double Tm = I * PhysicsDt;
			if (!bStarted && Tm >= Settle)
			{
				H.Start(What, Boat);
				bStarted = true;
				Out.SpeedBefore = SpeedSum / std::max(SpeedN, 1);
				Y0 = Boat.GetState().Position.Dot(WindFrom);
			}
			Ctl = Trim.Update(Boat, Ctl, PhysicsDt);
			const bool bHeld = bStarted && H.Update(Boat, Ctl, PhysicsDt);
			if (!bHeld) { if (bStarted) Pilot.TargetTWADeg = H.CourseAfterDeg(); Ctl.Tiller = Pilot.Update(Boat); }
			Boat.Step(PhysicsDt, Ctl, Wind, &Waves);
			const FBoatTelemetry& T = Boat.GetTelemetry();
			const double Kn = T.BoatSpeed / kKnot, A = T.TrueWindAngle * kRadToDeg;
			if (!bStarted) { if (Tm > Settle - 30.0) { SpeedSum += Kn; ++SpeedN; } continue; }
			const double Ts = Tm - Settle;
			Out.MinSpeed = std::min(Out.MinSpeed, Kn);
			if (What == EShipManoeuvre::Tack)
			{
				if (Out.ToWind < 0.0 && A < 0.0 && A > -90.0) Out.ToWind = Ts;
				if (Out.Through < 0.0 && A < -H.Settings.LetGoDeg) Out.Through = Ts;
			}
			else if (What == EShipManoeuvre::Wear && Out.Through < 0.0 && A < -90.0) Out.Through = Ts;
			if (H.Step() == EShipManoeuvreStep::MissedStays) Out.bMissed = true;
			if (bPrint && I % int(5.0 * PhysicsHz) == 0)
			{
				std::printf("t %5.0f  %-30s %+5.2f kn ahead  TWA %6.1f  turn %+5.2f deg/s  heel %5.1f  rudder %+5.1f  braces", Ts, FShipHandling::StepName(H.Step()),
					T.ForwardSpeed / kKnot, A, Boat.GetState().AngularVelocity.Z * kRadToDeg, T.Heel * kRadToDeg, T.RudderAngle * kRadToDeg);
				for (int M = 0; M < C.Square.NumMasts; ++M) std::printf(" %+.2f", Ctl.Brace[M]);
				std::printf("  alpha");
				for (int M = 0; M < C.Square.NumMasts; ++M)
				{
					int L = -1;
					for (int Q = 0; Q < T.NumSquareSails; ++Q) if (C.Square.Sails[Q].Mast == M && Boat.GetState().SquareOut[Q] > 0.5) { L = Q; break; }
					if (L >= 0) std::printf(" %+.0f", T.SquareStrips[L].AlphaN * kRadToDeg);
				}
				std::printf("  AWA %+.0f jib %.2f main %.2f%s\n", T.ApparentWindAngle * kRadToDeg, Ctl.JibSheet, Ctl.MainSheet, Ctl.bMainDown ? " down" : "");
			}
			static const double ProbeAt = std::getenv("PROBE_AT") ? std::atof(std::getenv("PROBE_AT")) : -1.0;
			if (ProbeAt > 0.0 && std::fabs(Ts - ProbeAt) < 0.5 * PhysicsDt)
			{
				// What turns her here: 60 s on with one thing changed at a time, the turn rate at the end.
				FWindParams CalmP;
				CalmP.SpeedKnots = 0.0;
				const FWindField Calm(CalmP);
				for (int V = 0; V < 9; ++V)
				{
					FBoatModel Copy = Boat;
					FBoatControls K = Ctl;
					const char* Name = "as is";
					if (V == 1) { Name = "square sails furled"; for (int Q = 0; Q < kMaxSquareSails; ++Q) K.SquareSet[Q] = ESailSet::Furled; }
					if (V == 2) { Name = "fore-and-aft sails down"; K.bMainDown = K.bJibDown = K.bStaysailDown = true; }
					if (V == 3) { Name = "rudder amidships"; K.Tiller = 0.0; }
					if (V == 4) { Name = "rudder other way"; K.Tiller = -K.Tiller; }
					if (V == 5) { Name = "fore square sails only"; for (int Q = 0; Q < int(C.Square.Sails.size()) && Q < kMaxSquareSails; ++Q) if (C.Square.Sails[Q].Mast != 0) K.SquareSet[Q] = ESailSet::Furled; }
					if (V == 6) { Name = "after square sails only"; for (int Q = 0; Q < int(C.Square.Sails.size()) && Q < kMaxSquareSails; ++Q) if (C.Square.Sails[Q].Mast == 0) K.SquareSet[Q] = ESailSet::Furled; }
					for (int Q = 0; Q < int(C.Square.Sails.size()); ++Q) if (K.SquareSet[Q] != ESailSet::Set) Copy.GetMutableState().SquareOut[Q] = 0.0;
					if (V == 7) Name = "no waves";
					if (V == 8) Name = "no wind, no waves";
					for (int J = 0; J < int(60.0 * PhysicsHz); ++J) Copy.Step(PhysicsDt, K, V == 8 ? Calm : Wind, V >= 7 ? nullptr : &Waves);
					const Vec3 Moved = Copy.GetState().Position - Boat.GetState().Position;
					std::printf("probe %-26s moved %+.0f N %+.0f E m, vel %+.2f %+.2f m/s  turn %+6.3f deg/s  TWA %6.1f  ahead %+5.2f kn\n", Name, Moved.X, Moved.Y,
						Copy.GetState().Velocity.X, Copy.GetState().Velocity.Y, Copy.GetState().AngularVelocity.Z * kRadToDeg,
						Copy.GetTelemetry().TrueWindAngle * kRadToDeg, Copy.GetTelemetry().ForwardSpeed / kKnot);
				}
			}
			if (Out.Done < 0.0 && bStarted && !H.IsActive() && H.Manoeuvre() != EShipManoeuvre::HeaveTo) Out.Done = Ts;
			if (What == EShipManoeuvre::HeaveTo && Ts >= 300.0)
			{
				Out.SpeedAfter = Kn;
				Out.Leeward = (Y0 - Boat.GetState().Position.Dot(WindFrom));
				Out.Done = Ts;
				break;
			}
			if (Out.Done >= 0.0 && Ts >= Out.Done + 60.0)
			{
				Out.SpeedAfter = Kn;
				Out.Leeward = (Y0 - Boat.GetState().Position.Dot(WindFrom));
				break;
			}
		}
		return Out;
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
	if (Argc > 3 && std::strcmp(Argv[2], "--astern") == 0)
	{
		// The rudder going astern: no wind, flat water, a fixed helm (+ = bow to starboard going ahead).
		const double Helm = std::atof(Argv[3]);
		for (double V : { 1.0, -1.0 })
		{
			FWindParams Calm;
			Calm.SpeedKnots = 0.0;
			const FWindField Wind(Calm);
			FBoatModel Boat(C);
			Boat.Reset(0.0, 0.0, 0.0, V);
			FBoatControls Ctl;
			Ctl.bMainDown = Ctl.bJibDown = Ctl.bStaysailDown = true;
			for (int I = 0; I < kMaxSquareSails; ++I) Ctl.SquareSet[I] = ESailSet::Furled;
			Ctl.Tiller = Helm;
			for (int I = 0; I < int(30.0 * PhysicsHz); ++I)
			{
				// Started at V along her axis with every sail in, so only the helm turns her (her way decays as she goes).
				Boat.Step(PhysicsDt, Ctl, Wind);
				if (I % int(5.0 * PhysicsHz) == 0)
					std::printf("speed %+.1f m/s  t %4.1f  ahead %+5.2f m/s  turn %+6.3f deg/s  rudder %+5.1f\n", V, I * PhysicsDt,
						Boat.GetTelemetry().ForwardSpeed, Boat.GetState().AngularVelocity.Z * kRadToDeg, Boat.GetTelemetry().RudderAngle * kRadToDeg);
			}
		}
		return 0;
	}
	if (Argc > 4 && std::strcmp(Argv[2], "--manoeuvre") == 0)
	{
		const std::string W = Argv[3];
		const EShipManoeuvre What = W == "wear" ? EShipManoeuvre::Wear : W == "heaveto" ? EShipManoeuvre::HeaveTo : EShipManoeuvre::Tack;
		const int Plan = Argc > 5 ? std::atoi(Argv[5]) : 0;
		const int Seed = Argc > 6 ? std::atoi(Argv[6]) : 0;
		const FManoeuvreResult R = SailManoeuvre(C, What, std::atof(Argv[4]), Plan, Seed, true);
		std::printf("%s in %s kn under %s: head to wind %.0f s, through %.0f s, done %.0f s%s; %.2f kn before, %.2f at least, %.2f a minute after; "
			"%.0f m to leeward\n", W.c_str(), Argv[4], kPlans[Plan].Name, R.ToWind, R.Through, R.Done, R.bMissed ? " (missed stays: wore)" : "",
			R.SpeedBefore, R.MinSpeed, R.SpeedAfter, R.Leeward);
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
