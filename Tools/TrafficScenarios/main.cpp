// Runs the Navigation Rules scenarios standalone (no Unreal): scripts/traffic.sh
#include "TrafficScenarios.h"
#include "Wind.h"
#include <cstdio>
#include <cstdlib>

int main(int argc, char** argv)
{
	using namespace Sailing;
	// W1: the fine turbulence tile, from the repository root or from where the script runs.
	if (!Sailing::FTurbulenceTile::LoadShared("Content/TerrainData/Wind.mann")) std::printf("(no Content/TerrainData/Wind.mann: fine turbulence stand-in)\n");
	const int Only = argc > 1 ? std::atoi(argv[1]) : -1;
	int Failed = 0;
	for (int I = 0; I < RulesScenarioCount(); ++I)
	{
		if (Only >= 0 && I != Only) continue;
		const FRulesScenarioResult R = RunRulesScenario(I);
		std::printf("%s %2d %-58s %-22s no-rules %6.0f m  rules %6.0f m (safe %3.0f)  give-way turn %5.1f slow %4.2f  stand-on turn %5.1f  collisions %d%s%s\n",
			R.bPassed ? "PASS" : "FAIL", I, R.Name.c_str(), R.Rule.c_str(), R.MinRangeNoRules, R.MinRange, R.Safe, R.GiveWayTurnDeg, R.GiveWaySlowdown,
			R.StandOnTurnDeg, R.Collisions, R.bPassed ? "" : "  -- ", R.Failure.c_str());
		if (Only >= 0) for (const std::string& E : R.Events) std::printf("    %s\n", E.c_str());
		Failed += !R.bPassed;
	}
	if (Only == 98)
	{
		// Robustness: the same race from several starting spreads.
		// W1: and again in an afternoon breeze's puffs and shifts, where they tack on the headers.
		for (const bool bShifty : { false, true })
		{
			for (unsigned Seed = 1; Seed <= 16; ++Seed)
			{
				const FRaceScenarioResult R = RunAiRace(5, 2, 600.0, Seed, bShifty);
				int Finished = 0;
				for (const auto& B : R.Boats) Finished += B.Place > 0;
				std::printf("%s seed %u: %s in %.0f s, %d of 5 finished, %d collisions, %d tacks\n", bShifty ? "shifty" : "steady", Seed, R.bOver ? "over" : "NOT OVER",
					R.RaceSeconds, Finished, R.Collisions, R.Tacks);
			}
		}
	}
	if (Only < 0 || Only == 99)
	{
		const FRaceScenarioResult R = RunAiRace(5, 2, 600.0);
		std::printf("Race: %s after %.0f s, %d collisions\n", R.bOver ? "over" : "NOT OVER", R.RaceSeconds, R.Collisions);
		for (const auto& B : R.Boats)
			std::printf("  %-8s place %d points %d %s finish %.0f s marks %d%s\n", B.Name.c_str(), B.Place, B.Points, B.Status.c_str(), B.FinishSeconds, B.MarksRounded, B.bOcsAtStart ? " (OCS at the gun)" : "");
		for (const std::string& S : R.Signals) std::printf("    %s\n", S.c_str());
	}
	return Failed ? 1 : 0;
}
