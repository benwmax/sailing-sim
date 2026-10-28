// The Hobie 16 running deep (TWA 170, 14 kn) on the autopilot: when does it capsize, and why (docs/hobie-run/).
//   HobieRun [twa] [trace]      the run, guard off and on, steady and gusty
//   HobieRun gybe [gust]        a gybe she is told to make: -160 for 30 s, then +160
//   HobieRun seeds              TWA +-170, gusty chop, seeds 1-12, guard off and on: how many capsize or cross
#include "SeaTrials.h"
#include "AutoTrim.h"
#include "FixedStepper.h"
#include "WindClimate.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
using namespace Sailing;

namespace
{
	struct FRunResult { double Capsized = -1.0, MaxHeel = 0.0, MaxPitch = 0.0, DeepestTwa = 0.0; int Crossings = 0, Gybes = 0; };

	FRunResult Run(double Twa, double GustIntensity, double Fetch, bool bGuard, bool bHands, double Seconds, double GybeAt, bool bTrace, uint32_t Seed = 1)
	{
		FTrialSeaSpec Spec; Spec.WindKnots = 14.0; Spec.FetchMeters = Fetch; Spec.GustIntensity = GustIntensity; Spec.Seed = Seed;
		FTrialSea Sea(Spec);
		FBoatModel Boat(FBoatConfig::Make(EBoatType::Hobie16));
		Boat.Reset(0.0, 0.0, Sea.HeadingFor(Twa), 6.0 * kKnot);
		FAutoTrim Trim; Trim.Settings.bHands = bHands;
		FAutopilot Helm; Helm.TargetTWADeg = Twa;
		if (bGuard) Helm.Wind = &Sea.GetWind();
		FBoatControls C;
		FRunResult R;
		double T = 0.0, PrevTwa = Twa, BoomSide = 0.0;
		for (int I = 0; I < int(Seconds * PhysicsHz); ++I, T += PhysicsDt)
		{
			if (GybeAt >= 0.0 && T >= GybeAt) Helm.TargetTWADeg = -Twa;
			const Vec3 O = Boat.OriginPosition(); Sea.Update(T, O.X, O.Y);
			C = Trim.Update(Boat, C, PhysicsDt); C.Tiller = Helm.Update(Boat);
			Boat.Step(PhysicsDt, C, Sea.GetWind(), Sea.GetWaves());
			const FBoatTelemetry& Tm = Boat.GetTelemetry();
			const double TwaNow = Tm.TrueWindAngle / kDegToRad;
			if (T > 2.0)
			{
				R.MaxPitch = std::max(R.MaxPitch, std::fabs(Tm.Pitch) / kDegToRad);
				R.MaxHeel = std::max(R.MaxHeel, std::fabs(Tm.Heel) / kDegToRad);
				R.DeepestTwa = std::max(R.DeepestTwa, std::fabs(TwaNow));
				if (std::fabs(TwaNow) > 150.0 && std::fabs(PrevTwa) > 150.0 && TwaNow * PrevTwa < 0.0) ++R.Crossings;
				// A gybe: the boom across (past 20 deg on the other side).
				const double Boom = Boat.GetState().BoomAngle / kDegToRad;
				if (std::fabs(Boom) > 20.0) { const double Side = Boom > 0.0 ? 1.0 : -1.0; if (BoomSide != 0.0 && Side != BoomSide) ++R.Gybes; BoomSide = Side; }
			}
			PrevTwa = TwaNow;
			if (bTrace && I % 30 == 0) std::printf("t %5.1f kn %5.2f twa %7.1f awa %7.1f boom %6.1f heel %6.1f main %.2f tiller %5.2f\n", T, Tm.BoatSpeed / kKnot, TwaNow, Tm.ApparentWindAngle / kDegToRad, Boat.GetState().BoomAngle / kDegToRad, Tm.Heel / kDegToRad, C.MainSheet, C.Tiller);
			if (Tm.bCapsized) { R.Capsized = T; break; }
		}
		return R;
	}

	void Print(const char* Label, const FRunResult& R)
	{
		std::printf("%-44s %s, max heel %4.0f, max pitch %3.0f, deepest TWA %5.1f, TWA crossed 180 %d times, gybed %d times\n", Label,
			R.Capsized >= 0.0 ? (std::string("CAPSIZED at ") + std::to_string(int(R.Capsized)) + " s").c_str() : "upright", R.MaxHeel, R.MaxPitch, R.DeepestTwa, R.Crossings, R.Gybes);
	}
}

int main(int Argc, char** Argv)
{
	FTurbulenceTile::LoadShared("Content/TerrainData/Wind.mann");
	// 14 kn gusting to about 18: a gust factor of 1.3.
	const double Gusty = GustIntensityForFactor(1.3);
	if (Argc > 1 && std::strcmp(Argv[1], "gybe") == 0)
	{
		const double G = Argc > 2 ? std::atof(Argv[2]) : Gusty;
		const bool bTrace = Argc > 3;
		std::printf("A gybe she is told to make (-160 for 30 s, then +160), 14 kn, gust intensity %.3f:\n", G);
		for (const bool bGuard : { false, true })
		for (const double Fetch : { 1.0, 5000.0 })
		{
			char Label[96];
			std::snprintf(Label, sizeof(Label), "guard %s, fetch %5.0f", bGuard ? "on " : "off", Fetch);
			Print(Label, Run(-160.0, G, Fetch, bGuard, true, 90.0, 30.0, bTrace && bGuard && Fetch > 1.0));
		}
		return 0;
	}
	if (Argc > 1 && std::strcmp(Argv[1], "seeds") == 0)
	{
		for (const bool bGuard : { false, true })
		{
			int Capsized = 0, Crossed = 0, N = 0;
			double Deepest = 0.0, Heel = 0.0;
			for (uint32_t Seed = 1; Seed <= uint32_t(Argc > 2 ? std::atoi(Argv[2]) : 12); ++Seed)
			for (const double Side : { -1.0, 1.0 })
			{
				const FRunResult R = Run(170.0 * Side, Gusty, 5000.0, bGuard, true, 120.0, -1.0, false, Seed);
				++N;
				Capsized += R.Capsized >= 0.0;
				Crossed += R.Gybes > 0;
				Deepest = std::max(Deepest, R.DeepestTwa);
				Heel = std::max(Heel, R.Capsized >= 0.0 ? 0.0 : R.MaxHeel);
			}
			std::printf("guard %s: of %d runs (TWA +-170, 14 kn, gust %.2f, 5 km chop, 120 s) %d capsized, %d gybed (the boom across); deepest TWA %.1f, max heel upright %.0f\n",
				bGuard ? "on " : "off", N, Gusty, Capsized, Crossed, Deepest, Heel);
		}
		return 0;
	}
	const double Twa = Argc > 1 ? std::atof(Argv[1]) : -170.0;
	const bool bTrace = Argc > 2;
	std::printf("Holding TWA %.0f, 14 kn, 120 s (gust intensity %.3f when gusty):\n", Twa, Gusty);
	for (const bool bGuard : { false, true })
	for (const double Fetch : { 1.0, 5000.0 })
	for (const double Gust : { 0.0, Gusty })
	{
		char Label[96];
		std::snprintf(Label, sizeof(Label), "guard %s, fetch %5.0f, %s", bGuard ? "on " : "off", Fetch, Gust > 0.0 ? "gusty " : "steady");
		Print(Label, Run(Twa, Gust, Fetch, bGuard, true, 120.0, -1.0, bTrace && Gust > 0.0 && Fetch > 1.0));
	}
	return 0;
}
