// Standalone polar sweep for calibrating the J/22 physics outside Unreal. Build and run with scripts/polar.sh.
#include "PolarReference.h"
#include "Scenarios.h"
#include "EasyAssists.h"
#include "SeaTrials.h"
#include "WindClimate.h"
#include "Wind.h"
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cctype>
#include "FixedStepper.h"

using namespace Sailing;

// Case-insensitive prefix match (strncasecmp is POSIX only; the PC builds this with MSVC).
static bool StartsWithNoCase(const char* Name, const char* Prefix)
{
	for (; *Prefix; ++Name, ++Prefix)
	{
		if (*Name == '\0' || std::tolower(static_cast<unsigned char>(*Name)) != std::tolower(static_cast<unsigned char>(*Prefix))) return false;
	}
	return true;
}

int main(int Argc, char** Argv)
{
	// --boat <name> (first word, any case) picks a boat from the fleet; it can come first, before the other options.
	EBoatType Type = EBoatType::J22;
	if (Argc > 2 && std::strcmp(Argv[1], "--boat") == 0)
	{
		for (int I = 0; I < int(EBoatType::Count); ++I)
		{
			if (StartsWithNoCase(BoatTypeName(EBoatType(I)), Argv[2])) Type = EBoatType(I);
		}
		Argv += 2;
		Argc -= 2;
	}
	// --ar <coef>, --surf <scale> and --flow <scale> override the boat's added resistance, wave slope push and orbital flow
	// (calibration runs).
	FBoatConfig Config = FBoatConfig::Make(Type);
	while (Argc > 2 && (std::strcmp(Argv[1], "--ar") == 0 || std::strcmp(Argv[1], "--surf") == 0 || std::strcmp(Argv[1], "--flow") == 0))
	{
		(std::strcmp(Argv[1], "--ar") == 0 ? Config.AddedResistanceCoef
			: std::strcmp(Argv[1], "--surf") == 0 ? Config.WaveSlopeForceScale : Config.WaveOrbitalFlowScale) = std::atof(Argv[2]);
		Argv += 2;
		Argc -= 2;
	}
	const bool bQuick = Argc > 1 && std::strcmp(Argv[1], "--quick") == 0;
	const std::vector<FPolarPoint>& Polar = FleetReferencePolar(Type);
	std::printf("%s\n", Config.Name);
	if (Argc > 1 && std::strcmp(Argv[1], "--sea") == 0)
	{
		// The game's fine turbulence (the gale is gusty), as the module loads it.
		if (!FTurbulenceTile::LoadShared("Content/TerrainData/Wind.mann")) std::printf("(no Content/TerrainData/Wind.mann: fine turbulence stand-in)\n");
		// Wave physics (docs/wave-physics/): calm and added resistance and the surf. --sea alone: the polar's sea at 8-20 kn,
		// beating, reaching and running. --sea gale: the prologue's gale (six tacks on the wheel; beat, reach and run, in its
		// sea and on flat water). --sea checks: what the wave tests assert. --sea orc <hs> <tws>: ORC's 5 s sea. --sea at
		// <tws> <twa> [settle s] [seconds]: one point of the polar's sea.
		const bool bGale = Argc > 2 && std::strcmp(Argv[2], "gale") == 0;
		auto Print = [](const char* What, const FSeaRunResult& R)
		{
			std::printf("%-34s Hs %.2f m  %5.2f kn (net %5.2f, 1 s %5.2f..%5.2f)  calm %6.0f N  waves %6.0f N (%3.0f%%)  surge %+6.0f N  face %+.3f back %+.3f m/s2 (%2.0f%% on faces)  heel %4.1f%s\n",
				What, R.Hs, R.MeanKnots, R.NetKnots, R.MinKnots, R.MaxKnots, R.MeanCalmN, R.MeanWaveN, 100.0 * R.MeanWaveN / std::max(R.MeanCalmN, 1.0), R.MeanSurgeN, R.FaceAccel,
				R.BackAccel, 100.0 * R.FaceShare, R.MeanHeelDeg, R.bCapsized ? "  CAPSIZED" : "");
		};
		if (Argc > 2 && std::strcmp(Argv[2], "checks") == 0)
		{
			// What SailingSim.Physics.WaveAddedResistanceScaling and SailingSim.Physics.Surfing assert, printed.
			FTrialSeaSpec Orc;
			Orc.WindKnots = 16.0;
			Orc.FetchMeters = 1.0;
			Orc.bOcean = true;
			Orc.Ocean.WindMs = 16.0 * kKnot;
			Orc.Ocean.WindFromRad = 0.0;
			Orc.Ocean.WindSeaHs = 1.0;
			Orc.Ocean.WindSeaTp = 5.0;
			Orc.Ocean.SwellHs = 0.0;
			double J22 = 0.0;
			for (const EBoatType B : { EBoatType::J22, EBoatType::Catalina22, EBoatType::Catalina30, EBoatType::Maxi })
			{
				const FSeaRunResult R = RunInSea(FBoatConfig::Make(B), Orc, 45.0, 0, false, 30.0, 120.0);
				if (B == EBoatType::J22) J22 = R.MeanWaveN;
				std::printf("ORC sea, %-12s added resistance %6.0f N = %5.2f x the J/22's (%.2f kn)\n", BoatTypeName(B), R.MeanWaveN, R.MeanWaveN / std::max(J22, 1.0), R.MeanKnots);
			}
			FTrialSeaSpec Gulf;
			Gulf.WindKnots = 12.0;
			Gulf.WindFromDeg = 180.0;
			Gulf.FetchMeters = 1.0;
			Gulf.bOcean = true;
			Gulf.Ocean.WindMs = 12.0 * kKnot;
			Gulf.Ocean.WindFromRad = kPi;
			Gulf.Ocean.SwellHs = 1.2;
			Gulf.Ocean.SwellTp = 9.0;
			Gulf.Ocean.SwellFromRad = 135.0 * kDegToRad;
			for (const double Surf : { 0.0, 1.0 })
			{
				FBoatConfig C = FBoatConfig::Make(EBoatType::J22);
				C.WaveSlopeForceScale = Surf;
				Print(Surf > 0.0 ? "J/22 Gulf swell TWA 150, push" : "J/22 Gulf swell TWA 150, no push", RunInSea(C, Gulf, 150.0, 0, false, 30.0, 240.0));
				FBoatConfig L = FBoatConfig::Make(EBoatType::ILCA7);
				L.WaveSlopeForceScale = Surf;
				FTrialSeaSpec Chop;
				Chop.WindKnots = 20.0;
				Chop.bCalibrationSea = true;
				Print(Surf > 0.0 ? "ILCA 20 kn chop TWA 150, push" : "ILCA 20 kn chop TWA 150, no push", RunInSea(L, Chop, 150.0, 0, false, 30.0, 240.0));
				FTrialSeaSpec Swell = Gulf;
				Swell.WindKnots = 0.0;
				Swell.Ocean.WindMs = 0.5;
				Print(Surf > 0.0 ? "J/22 adrift on the swell, push" : "J/22 adrift on the swell, no push", RunInSea(C, Swell, 90.0, 0, false, 30.0, 300.0));
			}
			return 0;
		}
		if (Argc > 2 && std::strcmp(Argv[2], "trim") == 0)
		{
			// docs/trimmer-hands/: how the crew work the sheets (the boat's, default the J/22) at 15 kn, with human hands and with
			// the polar's ideal trim: each control's travel per minute (whole travels; the traveller's is 2), adjustments.
			const double Gust = GustIntensityForFactor(ClimateGustFactor(7, 15.0, false));
			for (const double Twa : { 45.0, 90.0 })
			for (const double Fetch : { 1.0, 5000.0 })
			for (const double G : { 0.0, Gust })
			for (const bool bHands : { false, true })
			{
				const FTrimHandsResult R = MeasureTrimHands(Config, 15.0, Twa, Fetch, G, 600.0, bHands);
				std::printf("TWA %2.0f %-9s %-6s %-5s: main %5.2f, traveller %5.2f, jib %5.2f travels/min, %5.1f adjustments/min, %5.2f kn\n", Twa,
					Fetch > 1.0 ? "lake chop" : "flat", G > 0.0 ? "gusty" : "steady", bHands ? "hands" : "ideal", R.MainTravelPerMin, R.TravelerTravelPerMin,
					R.JibTravelPerMin, R.AdjustmentsPerMin, R.MeanKnots);
			}
			return 0;
		}
		if (Argc > 2 && std::strcmp(Argv[2], "surf") == 0)
		{
			// docs/surfing/: speed by wave phase. A J/22 running on a following 2 m wind sea in 20 kn (kite up), the maxi on the
			// gale's quartering sea, and the J/22 upwind on flat water (which must not change).
			auto Phase = [](const char* What, const FSeaRunResult& R)
			{
				std::printf("%-30s %5.2f kn (1 s %5.2f..%5.2f, hull speed %.1f, over 1.5x %3.0f%%)  by phase steep back/back/level/face/steep face:", What, R.MeanKnots,
					R.MinKnots, R.MaxKnots, R.HullSpeedKnots, 100.0 * R.SurfShare);
				for (int B = 0; B < 5; ++B) std::printf(" %5.2f (%2.0f%%)", R.PhaseKnots[B], 100.0 * R.PhaseShare[B]);
				std::printf("  face %+.2f back %+.2f m/s2, course error face %.1f back %.1f deg, max tilt %.0f%s\n", R.FaceAccel, R.BackAccel, R.FaceCourseErrDeg,
					R.BackCourseErrDeg, R.MaxTiltDeg, R.bCapsized ? " CAPSIZED" : "");
			};
			FTrialSeaSpec Run;
			Run.WindKnots = 20.0;
			Run.WindFromDeg = 0.0;
			Run.FetchMeters = 1.0;
			Run.bOcean = true;
			Run.Ocean.WindMs = 20.0 * kKnot;
			Run.Ocean.WindFromRad = 0.0;
			Run.Ocean.WindSeaHs = 2.0;
			Run.Ocean.WindSeaTp = 6.5;
			Run.Ocean.SwellHs = 0.0;
			// Each run without the orbital flow (still water past the hull and foils, as before docs/surfing/) and with it.
			for (const double Flow : { 0.0, 1.0 })
			{
				const char* Tag = Flow > 0.0 ? "flow" : "still";
				FBoatConfig J22 = FBoatConfig::Make(EBoatType::J22);
				J22.WaveOrbitalFlowScale = Flow;
				for (const double Twa : { 150.0, 165.0 }) { char N[48]; std::snprintf(N, sizeof(N), "%s J/22 2 m 20 kn TWA %3.0f", Tag, Twa); Phase(N, RunInSea(J22, Run, Twa, 0, true, 30.0, 300.0, 0.02)); }
				FBoatConfig Maxi = FBoatConfig::Make(EBoatType::Maxi);
				Maxi.WaveOrbitalFlowScale = Flow;
				FSceneLimits::For(true).ApplyTo(Maxi);
				for (const double Twa : { 120.0, 150.0 }) { char N[48]; std::snprintf(N, sizeof(N), "%s maxi gale TWA %3.0f", Tag, Twa); Phase(N, RunInSea(Maxi, FTrialSeaSpec::Gale(1), Twa, 2, false, 30.0, 180.0, 0.03)); }
				FTrialSeaSpec Flat;
				Flat.WindKnots = 12.0;
				Flat.FetchMeters = 1.0;
				char N[48];
				std::snprintf(N, sizeof(N), "%s J/22 flat 12 kn TWA 45", Tag);
				Phase(N, RunInSea(J22, Flat, 45.0, 0, false, 25.0, 60.0));
			}
			return 0;
		}
		if (Argc > 4 && std::strcmp(Argv[2], "orc") == 0)
		{
			// ORC's VPP sea (docs/wave-physics/): an open-sea wind sea at a fixed 5 s modal period, here at Hs <hs>, TWS
			// <tws>; upwind at TWA 45, no chop (the ratio of two boats' added resistance is what is compared with ORC).
			FTrialSeaSpec Sea;
			Sea.WindKnots = std::atof(Argv[4]);
			Sea.FetchMeters = 1.0;
			Sea.bOcean = true;
			Sea.Ocean.WindMs = Sea.WindKnots * kKnot;
			Sea.Ocean.WindFromRad = 0.0;
			Sea.Ocean.WindSeaHs = std::atof(Argv[3]);
			Sea.Ocean.WindSeaTp = 5.0;
			Sea.Ocean.SwellHs = 0.0;
			for (const double Twa : { 45.0, 90.0, 150.0 })
			{
				char Name[64];
				std::snprintf(Name, sizeof(Name), "ORC sea Hs %.1f TWA %3.0f", Sea.Ocean.WindSeaHs, Twa);
				Print(Name, RunInSea(Config, Sea, Twa, 0, Twa > 100.0 && Config.HasSpinnaker(), 30.0, 120.0));
			}
			return 0;
		}
		if (bGale)
		{
			FBoatConfig Scene = Config;
			FSceneLimits::For(true).ApplyTo(Scene);
			int Ok = 0, FlatOk = 0;
			for (uint32_t Seed = 1; Seed <= 6; ++Seed)
			{
				const FGaleTackResult W = RunGaleTackDetail(Scene, 2, Seed, true), F = RunGaleTackDetail(Scene, 2, Seed, false);
				Ok += W.Seconds > 0.0;
				FlatOk += F.Seconds > 0.0;
				std::printf("gale tack seed %u: in the sea %5.1f s (%5.2f kn, slowest %5.2f = %3.0f%%), flat %5.1f s (%5.2f kn, slowest %5.2f = %3.0f%%)\n", Seed,
					W.Seconds, W.SpeedBeforeKnots, W.MinSpeedKnots, 100.0 * W.MinSpeedKnots / std::max(W.SpeedBeforeKnots, 1e-3),
					F.Seconds, F.SpeedBeforeKnots, F.MinSpeedKnots, 100.0 * F.MinSpeedKnots / std::max(F.SpeedBeforeKnots, 1e-3));
			}
			std::printf("gale tacks: %d of 6 in the sea, %d of 6 on flat water\n", Ok, FlatOk);
			for (const double Twa : { 50.0, 100.0, 150.0 })
			{
				char Name[64];
				std::snprintf(Name, sizeof(Name), "gale TWA %3.0f, sea", Twa);
				Print(Name, RunInSea(Scene, FTrialSeaSpec::Gale(1), Twa, 2, false, 30.0, 120.0, 0.05));
				std::snprintf(Name, sizeof(Name), "gale TWA %3.0f, flat", Twa);
				Print(Name, RunInSea(Scene, FTrialSeaSpec::Gale(1, 32.0, false), Twa, 2, false, 30.0, 120.0, 0.05));
			}
			return 0;
		}
		if (Argc > 3 && std::strcmp(Argv[2], "at") == 0)
		{
			// --sea at <tws> <twa>: the polar's sea at one point.
			FTrialSeaSpec Sea;
			Sea.WindKnots = std::atof(Argv[3]);
			Sea.bCalibrationSea = true;
			const double Twa = std::atof(Argv[4]);
			const double Settle = Argc > 5 ? std::atof(Argv[5]) : 25.0, Seconds = Argc > 6 ? std::atof(Argv[6]) : 120.0;
			Print("polar sea", RunInSea(Config, Sea, Twa, 0, Twa > 100.0 && Config.HasSpinnaker(), Settle, Seconds));
			return 0;
		}
		for (const double Tws : { 8.0, 12.0, 16.0, 20.0 })
		{
			for (const double Twa : { 45.0, 90.0, 150.0 })
			{
				FTrialSeaSpec Sea;
				Sea.WindKnots = Tws;
				Sea.FetchMeters = kPolarFetchMeters;
				Sea.bCalibrationSea = true;
				char Name[64];
				std::snprintf(Name, sizeof(Name), "polar sea %2.0f kn TWA %3.0f", Tws, Twa);
				Print(Name, RunInSea(Config, Sea, Twa, 0, Twa > 100.0 && Config.HasSpinnaker(), 25.0, 60.0));
			}
		}
		return 0;
	}
	if (Argc > 1 && std::strcmp(Argv[1], "--scenarios") == 0 && Type == EBoatType::Maxi)
	{
		// The prologue maxi (docs/prologue/README.md step 3): heavy-air tacks and the gust on a reach.
		for (const int Reefs : { 0, 2 })
		{
			for (const double Tws : { 16.0, 30.0 })
			{
				const FTackResult T = RunTack(Config, Tws, Reefs);
				std::printf("tack %2.0f kn, %d reefs: %s in %.1f s, speed %.2f -> min %.2f -> %.2f after 10 s\n", Tws, Reefs, T.bCompleted ? "done" : "NOT DONE",
					T.TackSeconds, T.SpeedBeforeKnots, T.MinSpeedKnots, T.SpeedAfter10sKnots);
			}
		}
		for (const bool bLimits : { false, true })
		{
			for (const double Twa : { 70.0, 80.0, 90.0, 100.0, 130.0 })
			{
				const FGustReachResult G = RunGustReach(Config, 30.0, 40.0, Twa, 2, bLimits);
				std::printf("gust 30 -> 40 kn at TWA %3.0f, 2 reefs, limits %s: max heel %.1f, speed %.1f -> max %.1f kn, min TWA %.0f, course error %.0f, capsized %d\n",
					Twa, bLimits ? "on " : "off", G.MaxHeelDeg, G.SpeedBeforeKnots, G.MaxSpeedKnots, G.MinTwaDeg, G.MaxCourseErrorDeg, G.bCapsized);
			}
		}
		return 0;
	}
	if (Argc > 1 && std::strcmp(Argv[1], "--scenarios") == 0)
	{
		for (double Tws : { 6.0, 10.0, 15.0 })
		{
			const FTackResult T = RunTack(Tws);
			std::printf("tack %2.0f kn: %s in %.1f s, speed %.2f -> min %.2f -> %.2f after 10 s\n", Tws, T.bCompleted ? "done" : "NOT DONE",
				T.TackSeconds, T.SpeedBeforeKnots, T.MinSpeedKnots, T.SpeedAfter10sKnots);
		}
		for (double Tiller : { 0.0, 1.0 })
		{
			const FIronsResult I = RunIrons(10.0, 20.0, Tiller);
			std::printf("irons 10 kn tiller %.0f: TWA %.1f fwd speed %.2f (max %.2f) in irons %d\n", Tiller, I.FinalTWADeg, I.FinalForwardSpeedKnots,
				I.MaxForwardSpeedKnots, I.bInIronsAtEnd);
		}
		return 0;
	}
	if (Argc > 1 && std::strcmp(Argv[1], "--easy") == 0)
	{
		// Easy mode's checks (docs/easy-mode/README.md), each with the assists off and on.
		for (const bool bEasy : { false, true })
		{
			const char* Mode = bEasy ? "easy" : "realistic";
			const FEasyReachResult R = RunEasyReach(Type, bEasy, 15.0, 90.0, 120.0);
			std::printf("%-9s reach 15 kn gusty: max heel %.1f (cap %.1f) course error max %.1f deg, %.2f kn, capsized %d\n", Mode, R.MaxHeelDeg, R.HeelCapDeg,
				R.MaxCourseErrorDeg, R.MeanSpeedKnots, R.bCapsized);
			const FEasyReachResult G = RunEasyReach(Type, bEasy, 22.0, 70.0, 120.0, 0.3);
			std::printf("%-9s reach 22 kn very gusty: max heel %.1f (cap %.1f) course error max %.1f deg, %.2f kn, capsized %d\n", Mode, G.MaxHeelDeg, G.HeelCapDeg,
				G.MaxCourseErrorDeg, G.MeanSpeedKnots, G.bCapsized);
			const FEasyIronsResult I = RunEasyIrons(Type, bEasy, 10.0, 40.0);
			std::printf("%-9s irons 10 kn: filled after %.1f s, TWA %.1f, %.2f kn\n", Mode, I.FilledSeconds, I.FinalTwaDeg, I.FinalSpeedKnots);
			for (const double Tws : { 6.0, 10.0, 15.0 })
			{
				const FEasyTackResult T = RunEasyTack(Type, bEasy, Tws);
				std::printf("%-9s crude tack %2.0f kn: %s, TWA %.1f, %.2f kn, max heel %.1f\n", Mode, Tws, T.bTacked ? "tacked" : "NOT TACKED", T.FinalTwaDeg,
					T.FinalSpeedKnots, T.MaxHeelDeg);
			}
		}
		return 0;
	}
	if (Argc > 3 && std::strcmp(Argv[1], "--point") == 0)
	{
		// Detailed look at one point: --point <tws> <twa>
		const double Tws = std::atof(Argv[2]), Twa = std::atof(Argv[3]);
		const bool bSpin = Argc > 4 && std::strcmp(Argv[4], "spin") == 0;
		const FSteadyResult Best = SailSteady(Tws, Twa, Config, true, bSpin);
		std::printf("best: %.2f kn heel %.1f leeway %.1f rudder %.1f margin %.0f heelLimit %.0f\n", Best.BoatSpeedKnots, Best.HeelDeg,
			Best.LeewayDeg, Best.RudderDeg, Best.Trim.AlphaMarginDeg, Best.Trim.HeelLimitDeg);
		// Re-run that trim and dump the final state.
		FWindParams WP; WP.SpeedKnots = Tws; const FWindField Wind(WP);
		FBoatModel Boat(Config);
		Boat.Reset(0, 0, -Twa * kDegToRad, 0.6 * Tws * kKnot);
		FAutopilot Pilot; Pilot.TargetTWADeg = Twa;
		FAutoTrim Trim; Trim.Settings = Best.Trim;
		FBoatControls C; C.MainSheet = C.JibSheet = Twa / 180.0; C.bSpinnaker = bSpin;
		for (int I = 0; I < int(55 * PhysicsHz); ++I) { C = Trim.Update(Boat, C, PhysicsDt); C.Tiller = Pilot.Update(Boat); Boat.Step(PhysicsDt, C, Wind); }
		const FBoatTelemetry& T = Boat.GetTelemetry();
		std::printf("speed %.2f AWA %.1f AWS %.2f kn drive %.0f N heelF %.0f N boom %.1f jib %.1f\n", T.BoatSpeed / kKnot, T.ApparentWindAngle * kRadToDeg,
			T.ApparentWindSpeed / kKnot, T.DriveForce, T.HeelingForce, Boat.GetState().BoomAngle * kRadToDeg, Boat.GetState().JibAngle * kRadToDeg);
		std::printf("controls: main %.2f jib %.2f trav %.2f vang %.2f cunn %.2f outhaul %.2f backstay %.2f hike %.2f\n", C.MainSheet, C.JibSheet,
			C.Traveler, C.Vang, C.Cunningham, C.Outhaul, C.Backstay, C.Hike);
		const char* Flow[] = { "attached", "luffing", "stalled", "backed" };
		for (int I = 0; I < T.NumJibStrips; ++I) { const FSailStripState& S = T.JibStrips[I];
			std::printf(" jib  %d ang %5.1f awa %6.1f aoa %5.1f stall %5.1f luff %5.1f CL %5.2f CD %5.2f camber %.3f %s\n", I, S.AngleFromCenterline * kRadToDeg, S.ApparentAngle * kRadToDeg,
				S.AlphaN * kRadToDeg, S.StallAlpha * kRadToDeg, S.LuffAlpha * kRadToDeg, S.LiftCoefficient, S.DragCoefficient, S.Camber, Flow[int(S.Flow)]); }
		for (int I = 0; I < T.NumMainStrips; ++I) { const FSailStripState& S = T.MainStrips[I];
			std::printf(" main %d ang %5.1f awa %6.1f aoa %5.1f stall %5.1f luff %5.1f CL %5.2f CD %5.2f camber %.3f %s\n", I, S.AngleFromCenterline * kRadToDeg, S.ApparentAngle * kRadToDeg,
				S.AlphaN * kRadToDeg, S.StallAlpha * kRadToDeg, S.LuffAlpha * kRadToDeg, S.LiftCoefficient, S.DragCoefficient, S.Camber, Flow[int(S.Flow)]); }
		return 0;
	}
	{
		FBoatModel Boat(Config);
		std::printf("Mass %.0f kg, CG (%.2f, %.2f, %.2f), canoe depth %.3f m\n", Boat.TotalMass(),
			Boat.GetCenterOfGravity().X, Boat.GetCenterOfGravity().Y, Boat.GetCenterOfGravity().Z, Boat.HullDepth());
		for (double H : { 5.0, 10.0, 20.0, 30.0, 45.0, 60.0, 90.0 })
		{
			std::printf("  RM at %4.0f deg heel: %7.0f N m\n", H, Boat.RightingMomentAt(H * kDegToRad));
		}
	}
	std::printf("\n TWS  TWA   polar   model   err%%   heel  leeway rudder  helmN  note\n");
	int Fails = 0;
	double WorstErr = 0.0;
	for (const FPolarPoint& P : Polar)
	{
		const FSteadyResult R = SailSteady(P.TrueWindKnots, P.TrueWindAngleDeg, Config, !bQuick, P.bSpinnaker);
		const double Err = (R.BoatSpeedKnots - P.BoatSpeedKnots) / P.BoatSpeedKnots * 100.0;
		WorstErr = std::max(WorstErr, std::fabs(Err));
		Fails += std::fabs(Err) > P.Tolerance * 100.0;
		std::printf("%4.0f %5.1f  %5.2f   %5.2f  %+5.1f  %5.1f  %5.1f  %5.1f  %5.0f  %s%s\n", P.TrueWindKnots, P.TrueWindAngleDeg,
			P.BoatSpeedKnots, R.BoatSpeedKnots, Err, R.HeelDeg, R.LeewayDeg, R.RudderDeg, R.HelmForceN, P.Note, std::fabs(Err) > P.Tolerance * 100.0 ? "  <-- FAIL" : "");
	}
	std::printf("\n%d of %zu points outside tolerance, worst %.1f%%\n", Fails, Polar.size(), WorstErr);
	return Fails ? 1 : 0;
}
