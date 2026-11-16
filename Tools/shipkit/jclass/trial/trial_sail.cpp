// Bluebonnet's trial sail in the standalone physics (slice 13, the cloud half; docs/jclass-13). Nothing here is game
// code: it builds an FBoatConfig from the sheet physics.py writes (bluebonnet_trial.inl, BluebonnetHullData.inl in the
// build dir) and sails her the way the fleet's reference polars are sailed (SailSteadyWith: the polar's lake chop, the
// autopilot, ideal trim), so the Mac's half starts from numbers already sailed. Build and run with trial.sh.
//
//   trial_sail <out json> [--quick | --point <tws> <twa> [spin]]
//
// Prints and writes: her mass and centre of gravity as the physics builds them, how she floats at rest, her righting
// moments, and her speed at the estimated polar's points plus her best beat and run VMGs.
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
		if (Camber >= 0.18) { S.MaxLift = 1.3; S.ParasiteDrag = 0.30; } // spinnaker
		S.LiftSlope = LiftSlope;
		S.InducedAspectRatio = AspectRatio;
		S.BaseCamber = Camber;
	}

#include "BluebonnetHullData.inl"
#include "bluebonnet_trial.inl"

	FBoatConfig Bluebonnet()
	{
		// From the J/22's defaults like every boat of the fleet, as the maxi's type (a big wheel-steered keelboat: the
		// type only names her here; the Mac's half gives her her own).
		FBoatConfig C;
		C.Type = EBoatType::Maxi;
		ApplyBluebonnet(C);
		return C;
	}

	// TRIAL_SET="name=value,..." in the environment overrides a knob for a tuning run without rebuilding the sheet:
	// keel_x, keel_ar, rudder_area, rudder_ar, downwash, heel_yaw, munk, yaw_damping, residuary (a factor on the table).
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
				if (!bKeel && K == "rudder_ar") F.Params.EffectiveAspectRatio = V;
			}
			if (K == "downwash") C.KeelDownwashFactor = V;
			if (K == "heel_yaw") C.HeelYawCoef = V;
			if (K == "munk") C.MunkAddedMass = V;
			if (K == "yaw_damping") C.YawDampingLinear = V;
			if (K == "residuary") for (auto& R : C.Residuary) R.second *= V;
			std::printf("override %s = %g\n", K.c_str(), V);
		}
	}

	struct FPoint { double Tws, Twa; bool bSpin; FSteadyResult R; };

	// The polar's way (SailSteady) with a longer settle: she weighs 150 times the J/22.
	FSteadyResult Sail(const FBoatConfig& C, double Tws, double Twa, bool bSpin, bool bQuick)
	{
		FSteadyResult Best;
		FAutoTrimSettings Base;
		Base.bHands = false;
		const std::vector<double> Margins = bQuick ? std::vector<double>{ 2.0 } : std::vector<double>{ 0.0, 2.0, 4.0 };
		const std::vector<double> Heels = bQuick ? std::vector<double>{ 22.0 } : std::vector<double>{ 18.0, 25.0 };
		for (double Margin : Margins)
		for (double Heel : Heels)
		{
			FAutoTrimSettings T = Base;
			T.AlphaMarginDeg = Margin;
			T.HeelLimitDeg = Heel;
			const FSteadyResult R = SailSteadyWith(Tws, Twa, T, C, 70.0, 20.0, bSpin);
			if (R.BoatSpeedKnots > Best.BoatSpeedKnots) Best = R;
		}
		return Best;
	}

	std::string Num(double V) { char B[32]; std::snprintf(B, sizeof(B), "%.4g", V); return B; }

	// --point <tws> <twa> [spin]: one run of the polar's way, printed every 5 s (for tuning).
	void TracePoint(const FBoatConfig& C, double Tws, double Twa, bool bSpin)
	{
		FWindParams WindParams;
		WindParams.SpeedKnots = Tws;
		const FWindField Wind(WindParams);
		FWaveField Waves(7);
		FWaveParams WaveParams;
		WaveParams.WindSpeedKnots = Tws;
		WaveParams.FetchMeters = kPolarFetchMeters;
		WaveParams.bCalibrationSea = true;
		Waves.SetWind(WaveParams);
		Waves.SnapToTarget();
		FBoatModel Boat(C);
		Boat.Reset(0.0, 0.0, -Twa * kDegToRad, 0.6 * Tws * kKnot);
		Boat.GetMutableState().WindwardSide = 1;
		Boat.GetMutableState().CrewOffset = C.CrewSitOut;
		FAutopilot Pilot;
		Pilot.TargetTWADeg = Twa;
		FAutoTrim Trim;
		Trim.Settings.bHands = false;
		FBoatControls Ctl;
		Ctl.MainSheet = Ctl.JibSheet = Clamp(Twa / 180.0, 0.0, 1.0);
		Ctl.bSpinnaker = bSpin;
		Ctl.Hike = Clamp((Tws - 6.0) / 6.0, 0.0, 1.0) * (1.0 - SmoothStep(95.0, 115.0, Twa));
		Ctl.SpinSheet = 0.5;
		for (int I = 0; I <= int(90.0 * PhysicsHz); ++I)
		{
			Ctl = Trim.Update(Boat, Ctl, PhysicsDt);
			Ctl.Tiller = Pilot.Update(Boat);
			Boat.Step(PhysicsDt, Ctl, Wind, &Waves);
			if (I % int(5.0 * PhysicsHz) == 0)
			{
				const FBoatTelemetry& T = Boat.GetTelemetry();
				const FBoatState& S = Boat.GetState();
				std::printf("t %4.0f  %5.2f kn  TWA %6.1f  AWA %5.1f  heel %5.1f  leeway %5.1f  rudder %+5.1f  tiller %+.2f  drive %6.0f  heeling %7.0f  "
					"calm %6.0f  boom %5.1f  jib %5.1f  Fn %.3f\n", S.Time, T.BoatSpeed / kKnot, T.TrueWindAngle * kRadToDeg, T.ApparentWindAngle * kRadToDeg,
					T.Heel * kRadToDeg, T.Leeway * kRadToDeg, T.RudderAngle * kRadToDeg, Ctl.Tiller, T.DriveForce, T.HeelingForce, T.CalmResistance,
					S.BoomAngle * kRadToDeg, S.JibAngle * kRadToDeg, T.Froude);
			}
		}
	}
}

int main(int Argc, char** Argv)
{
	if (Argc < 2) { std::printf("usage: trial_sail <out json> [--quick]\n"); return 2; }
	const bool bQuick = Argc > 2 && std::strcmp(Argv[2], "--quick") == 0;
	FBoatConfig C = Bluebonnet();
	ApplyOverrides(C);
	if (Argc > 4 && std::strcmp(Argv[2], "--point") == 0)
	{
		TracePoint(C, std::atof(Argv[3]), std::atof(Argv[4]), Argc > 5);
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

		// At rest: a minute in no wind on flat water.
		FWindParams Calm;
		Calm.SpeedKnots = 0.0;
		const FWindField Wind(Calm);
		Boat.Reset(0.0, 0.0, 0.0, 0.0);
		FBoatControls Controls;
		for (int I = 0; I < int(60.0 * PhysicsHz); ++I) Boat.Step(PhysicsDt, Controls, Wind);
		const FBoatTelemetry& T = Boat.GetTelemetry();
		const double Sink = -Boat.OriginPosition().Z;
		std::printf("at rest: heel %.2f deg, pitch %.2f deg (+ bow down?), origin %.3f m below the water\n", T.Heel * kRadToDeg, T.Pitch * kRadToDeg, Sink);
		J += "\"rest\": {\"heel_deg\": " + Num(T.Heel * kRadToDeg) + ", \"pitch_deg\": " + Num(T.Pitch * kRadToDeg) + ", \"sink_m\": " + Num(Sink) + "},\n";

		// Righting moments: the physics' own hydrostatics (crew on the centreline).
		J += "\"righting\": [";
		const double W = Boat.TotalMass() * kGravity;
		bool bFirst = true;
		for (double Deg : { 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0 })
		{
			const double M = Boat.RightingMomentAt(Deg * kDegToRad);
			std::printf("  heel %3.0f: righting %8.0f kN m, GZ %.3f m\n", Deg, M / 1000.0, M / W);
			J += std::string(bFirst ? "" : ", ") + "[" + Num(Deg) + ", " + Num(M) + ", " + Num(M / W) + "]";
			bFirst = false;
		}
		J += "],\n";
	}

	// Stiffness against her sail, hers and the estimate's two references' (the J/22 and the Catalina 30 as the fleet
	// builds them): righting at 20 deg over the main and jib's area times the height of their centre above the water,
	// so the comparison (polar_compare.py) can say how much more she heels than they did at the wind she is read at.
	// Crew on the centreline for all three (RightingMomentAt), which flatters her: the small boats' crews hike.
	{
		auto Stiffness = [](const FBoatConfig& K, const char* Name, std::string& Out)
		{
			const FBoatModel B(K);
			double A = 0.0, Az = 0.0;
			for (const FSailGeometry* S : { &K.Main, &K.Jib })
			for (int I = 0; I < S->NumStrips; ++I)
			{
				A += S->Strips[I].Area;
				Az += S->Strips[I].Area * 0.5 * (S->Strips[I].ZBottom + S->Strips[I].ZTop);
			}
			const double M = B.RightingMomentAt(20.0 * kDegToRad);
			std::printf("stiffness %-10s righting at 20 deg %9.0f N m, main and jib %6.1f m^2 at %5.2f m: %7.1f N/m^2\n", Name, M, A, Az / A,
				M / Az);
			Out += std::string("\"") + Name + "\": {\"righting_20_nm\": " + Num(M) + ", \"sail_area_m2\": " + Num(A) + ", \"sail_centre_m\": "
				+ Num(Az / A) + ", \"stiffness_pa\": " + Num(M / Az) + "}";
		};
		J += "\"stiffness\": {";
		Stiffness(C, "bluebonnet", J);
		J += ", ";
		Stiffness(FBoatConfig(), "j22", J);
		J += ", ";
		Stiffness(FBoatConfig::Make(EBoatType::Catalina30), "c30", J);
		J += "},\n";
	}

	// The estimated polar's points (polar_bluebonnet.py: 52 to 150 deg, the spinnaker from 120).
	// Every run is its own boat, wind and sea: they go on all the cores.
	std::vector<FPoint> Jobs;
	for (double Tws : { 6.0, 10.0, 16.0 })
	for (double Twa : { 52.0, 60.0, 90.0, 120.0, 150.0 })
		Jobs.push_back({ Tws, Twa, Twa >= 120.0, {} });
	const size_t NumGrid = Jobs.size();
	const std::vector<double> VmgWinds = { 6.0, 10.0, 12.0, 16.0 };
	for (double Tws : VmgWinds)
	{
		for (double Twa = bQuick ? 38.0 : 36.0; Twa <= 52.0; Twa += bQuick ? 4.0 : 2.0) Jobs.push_back({ Tws, Twa, false, {} });
		for (double Twa = 150.0; Twa <= 180.0; Twa += bQuick ? 10.0 : 5.0) Jobs.push_back({ Tws, Twa, true, {} });
	}
	std::atomic<size_t> Next(0);
	std::vector<std::thread> Workers;
	const unsigned NumThreads = std::max(1u, std::thread::hardware_concurrency());
	for (unsigned W = 0; W < NumThreads; ++W)
	{
		Workers.emplace_back([&]()
		{
			for (size_t I = Next++; I < Jobs.size(); I = Next++) Jobs[I].R = Sail(C, Jobs[I].Tws, Jobs[I].Twa, Jobs[I].bSpin, bQuick);
		});
	}
	for (std::thread& T : Workers) T.join();

	const std::vector<FPoint> Points(Jobs.begin(), Jobs.begin() + NumGrid);
	for (const FPoint& P : Points)
	{
		std::printf("TWS %4.1f TWA %5.1f%s: %5.2f kn (sailed at %5.1f), heel %4.1f, leeway %4.1f, rudder %+5.1f deg (+ weather), helm %+6.0f N\n", P.Tws,
			P.Twa, P.bSpin ? " spin" : "     ", P.R.BoatSpeedKnots, P.R.TrueWindAngleDeg, P.R.HeelDeg, P.R.LeewayDeg, P.R.RudderDeg, P.R.HelmForceN);
	}
	// Best beat and run VMGs (the race checks are VMGs), by the angle she actually sailed.
	std::vector<FPoint> Beat, Run;
	for (double Tws : VmgWinds)
	{
		FPoint BestB{ Tws, 0.0, false, {} }, BestR{ Tws, 0.0, true, {} };
		double VB = -1.0, VR = -1.0;
		for (size_t I = NumGrid; I < Jobs.size(); ++I)
		{
			const FPoint& P = Jobs[I];
			if (P.Tws != Tws) continue;
			const double V = P.R.BoatSpeedKnots * std::cos(P.R.TrueWindAngleDeg * kDegToRad);
			if (!P.bSpin && V > VB) { VB = V; BestB = P; }
			if (P.bSpin && -V > VR) { VR = -V; BestR = P; }
		}
		std::printf("TWS %4.1f: beat VMG %.2f kn at TWA %.0f (%.2f kn, heel %.1f, leeway %.1f, rudder %+.1f); run VMG %.2f kn at TWA %.0f (%.2f kn)\n",
			Tws, VB, BestB.R.TrueWindAngleDeg, BestB.R.BoatSpeedKnots, BestB.R.HeelDeg, BestB.R.LeewayDeg, BestB.R.RudderDeg, VR, BestR.R.TrueWindAngleDeg,
			BestR.R.BoatSpeedKnots);
		Beat.push_back(BestB);
		Run.push_back(BestR);
	}
	auto Row = [](const FPoint& P)
	{
		return "{\"tws\": " + Num(P.Tws) + ", \"twa\": " + Num(P.Twa) + ", \"spinnaker\": " + (P.bSpin ? "true" : "false") + ", \"speed\": "
			+ Num(P.R.BoatSpeedKnots) + ", \"heel\": " + Num(P.R.HeelDeg) + ", \"leeway\": " + Num(P.R.LeewayDeg) + ", \"rudder\": "
			+ Num(P.R.RudderDeg) + ", \"helm_n\": " + Num(P.R.HelmForceN) + ", \"twa_sailed\": " + Num(P.R.TrueWindAngleDeg) + ", \"vmg\": "
			+ Num(std::fabs(P.R.BoatSpeedKnots * std::cos(P.R.TrueWindAngleDeg * kDegToRad)))
			+ "}";
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
