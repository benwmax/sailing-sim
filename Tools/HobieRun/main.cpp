// The Hobie 16 running deep (TWA 170, 14 kn) on the autopilot: when does it capsize, and why.
#include "SeaTrials.h"
#include "AutoTrim.h"
#include "FixedStepper.h"
#include "WindClimate.h"
#include <cstdio>
#include <cstdlib>
using namespace Sailing;
int main(int Argc, char** Argv)
{
	FTurbulenceTile::LoadShared("Content/TerrainData/Wind.mann");
	const double Twa = Argc > 1 ? std::atof(Argv[1]) : 170.0;
	const bool bTrace = Argc > 2;
	for (const bool bHands : { true, false })
	for (const double Fetch : { 1.0, 5000.0 })
	for (const double Gust : { 0.0, GustIntensityForFactor(ClimateGustFactor(7, 14.0, false)) })
	{
		FTrialSeaSpec Spec; Spec.WindKnots = 14.0; Spec.FetchMeters = Fetch; Spec.GustIntensity = Gust;
		FTrialSea Sea(Spec);
		FBoatModel Boat(FBoatConfig::Make(EBoatType::Hobie16));
		Boat.Reset(0.0, 0.0, Sea.HeadingFor(Twa), 6.0 * kKnot);
		FAutoTrim Trim; Trim.Settings.bHands = bHands;
		FAutopilot Helm; Helm.TargetTWADeg = Twa;
		FBoatControls C;
		double T = 0.0, Capsized = -1.0, MaxPitch = 0.0, MaxHeel = 0.0;
		for (int I = 0; I < int(120.0 * PhysicsHz); ++I, T += PhysicsDt)
		{
			const Vec3 O = Boat.OriginPosition(); Sea.Update(T, O.X, O.Y);
			C = Trim.Update(Boat, C, PhysicsDt); C.Tiller = Helm.Update(Boat);
			Boat.Step(PhysicsDt, C, Sea.GetWind(), Sea.GetWaves());
			const FBoatTelemetry& Tm = Boat.GetTelemetry();
			MaxPitch = std::max(MaxPitch, std::fabs(Tm.Pitch) / kDegToRad); MaxHeel = std::max(MaxHeel, std::fabs(Tm.Heel) / kDegToRad);
			if (bTrace && bHands && Fetch > 1.0 && Gust > 0.0 && I % 60 == 0) std::printf("t %5.1f kn %5.2f twa %6.1f heel %6.1f pitch %6.1f main %.2f jib %.2f hike %.2f tiller %5.2f\n", T, Tm.BoatSpeed / kKnot, Tm.TrueWindAngle / kDegToRad, Tm.Heel / kDegToRad, Tm.Pitch / kDegToRad, C.MainSheet, C.JibSheet, C.Hike, C.Tiller);
			if (Tm.bCapsized && Capsized < 0.0) { Capsized = T; break; }
		}
		std::printf("%-5s fetch %5.0f gust %.2f: %s, max pitch %.0f, max heel %.0f\n", bHands ? "hands" : "ideal", Fetch, Gust,
			Capsized >= 0.0 ? (std::string("CAPSIZED at ") + std::to_string(int(Capsized)) + " s").c_str() : "upright 120 s", MaxPitch, MaxHeel);
	}
}
