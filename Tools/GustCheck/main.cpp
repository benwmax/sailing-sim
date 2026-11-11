// Session weather check (Nov 11 2026 review): the gusts a day delivers against its label, measured the way a sailor reads
// "10 gusting 13" (the strongest 3-second wind in each ten minutes), and the chosen wind holding through a session.
// Builds the wind the way ASailingGameMode::UpdateWeather does for a front-end session: the preset scaled to the chosen
// wind, the label's gusts by ApplySailorGust, Easy at half. No shelter map: near the shore, where the gusts are not eased
// by the open water (FShelterMap::OpenWaterGust), the worst case. Usage: scripts/gust-check.sh [--hours h]
#include "Weather.h"
#include "Wind.h"
#include "WindClimate.h"
#include "EasyAssists.h"
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

using namespace Sailing;

namespace
{
	struct FCase { const char* Name; EWeatherPreset Preset; int Month; double Hour; double Kn, GustKn; };

	FWindParams SessionWind(const FCase& C, bool bEasy, uint32_t Seed)
	{
		FWeatherSystem W;
		W.SetHoldWind(true);
		W.Configure(C.Preset, Seed, C.Hour);
		W.SetClimate(C.Month, false);
		FWeatherState S = W.Evaluate(0.0);
		S.Wind.SpeedKnots = C.Kn;   // WindScale
		ApplySailorGust(S.Wind, C.GustKn / C.Kn);
		if (bEasy)
		{
			const double Scale = FEasyAssists().WindVariabilityScale;
			S.Wind.GustIntensity *= Scale;
			if (S.Wind.PuffIntensity > 0.0) S.Wind.PuffIntensity *= Scale;
		}
		return S.Wind;
	}
}

int main(int Argc, char** Argv)
{
	double Hours = 2.0;
	if (Argc > 2 && std::strcmp(Argv[1], "--hours") == 0) Hours = std::atof(Argv[2]);
	if (!FTurbulenceTile::LoadShared("Content/TerrainData/Wind.mann") || FTurbulenceTile::Shared()->Nx < 64)
	{
		std::printf("Content/TerrainData/Wind.mann is missing or an LFS stub (git lfs pull): the gust numbers would be wrong.\n");
		return 2;
	}
	// The slice's session presets (SailSession.cpp), the Fair day at 15 gusting 20, and the "Live from today" breeze in
	// November and July.
	const FCase Cases[] = {
		{ "Lesson day 10 gusting 13", EWeatherPreset::AfternoonBreeze, 4, 10.0, 10.0, 13.0 },
		{ "Fair 15 gusting 20", EWeatherPreset::AfternoonBreeze, 4, 13.0, 15.0, 20.0 },
		{ "Blue norther 20 gusting 28", EWeatherPreset::Overcast, 11, 11.0, 20.0, 28.0 },
		{ "July afternoon 12 gusting 20", EWeatherPreset::Thunderstorm, 7, 14.5, 12.0, 20.0 },
		{ "Today (Nov) 11 gusting 16", EWeatherPreset::AfternoonBreeze, 11, 13.0, 11.0, 16.0 },
		{ "Today (Jul) 9 gusting 14", EWeatherPreset::AfternoonBreeze, 7, 15.0, 9.0, 14.0 },
	};
	int Fails = 0;
	std::printf("%-30s %5s %5s %9s %9s %9s %5s\n", "Day", "label", "", "typical", "9 in 10", "worst", "");
	for (const FCase& C : Cases)
	{
		for (int Easy = 0; Easy < 2; ++Easy)
		{
			// Three seeds (the session's weather seed varies the pattern, not its statistics).
			double Typ = 0.0, P90 = 0.0, Worst = 0.0;
			for (uint32_t Seed = 1; Seed <= 3; ++Seed)
			{
				const FWindField F(SessionWind(C, Easy != 0, Seed * 7919u));
				const FSailorGustStats G = MeasureSailorGusts(F, Hours, 4);
				Typ += G.MeanFactor / 3.0;
				P90 += G.P90Factor / 3.0;
				Worst = std::max(Worst, G.MaxFactor);
			}
			const double TypKn = Typ * C.Kn, P90Kn = P90 * C.Kn, WorstKn = Worst * C.Kn;
			// Realistic: nine ten-minute stretches in ten top out at the label (within 1 kn), the rare strongest at most 15 %
			// past it. Easy: gentler, under the label.
			const bool bOk = Easy ? P90Kn < C.GustKn && WorstKn <= C.GustKn * 1.15
				: std::fabs(P90Kn - C.GustKn) <= 1.0 && TypKn < C.GustKn && WorstKn <= C.GustKn * 1.15;
			Fails += bOk ? 0 : 1;
			std::printf("%-30s %5.0f %5s %6.1f kn %6.1f kn %6.1f kn %5s\n", C.Name, C.GustKn, Easy ? "easy" : "real", TypKn, P90Kn, WorstKn, bOk ? "ok" : "FAIL");
		}
	}
	// The chosen wind holds: a 10 kn lesson started at 10:00, four hours on (it built to 18.5 by noon before).
	{
		FWeatherSystem W;
		W.SetHoldWind(true);
		W.Configure(EWeatherPreset::AfternoonBreeze, 1, 10.0);
		W.SetClimate(4, false);
		const double Scale = 10.0 / W.Evaluate(0.0).Wind.SpeedKnots;
		double Most = 0.0;
		for (double T = 0.0; T <= 4.0 * 3600.0; T += 600.0) Most = std::max(Most, std::fabs(W.Evaluate(T).Wind.SpeedKnots * Scale - 10.0));
		const bool bOk = Most < 0.05;
		Fails += bOk ? 0 : 1;
		std::printf("Lesson wind held 4 h from 10:00: off by at most %.2f kn %s\n", Most, bOk ? "ok" : "FAIL");
	}
	std::printf(Fails ? "%d FAILED\n" : "all ok\n", Fails);
	return Fails ? 1 : 0;
}
