// Standalone polar sweep for calibrating the J/22 physics outside Unreal. Build and run with scripts/polar.sh.
#include "PolarReference.h"
#include "Scenarios.h"
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
	const bool bQuick = Argc > 1 && std::strcmp(Argv[1], "--quick") == 0;
	const FBoatConfig Config = FBoatConfig::Make(Type);
	const std::vector<FPolarPoint>& Polar = FleetReferencePolar(Type);
	std::printf("%s\n", Config.Name);
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
