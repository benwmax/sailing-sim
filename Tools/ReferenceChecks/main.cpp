// Phase 8 physics checks against real numbers, outside Unreal. Build and run with scripts/reference-checks.sh.
#include "ReferenceChecks.h"
#include "Wind.h"
#include <cstdio>
#include <cstring>

using namespace Sailing;

int main(int Argc, char** Argv)
{
	// W1: the fine turbulence tile, from the repository root or from where the script runs.
	if (!Sailing::FTurbulenceTile::LoadShared("Content/TerrainData/Wind.mann")) std::printf("(no Content/TerrainData/Wind.mann: fine turbulence stand-in)\n");
	const bool bQuick = Argc > 1 && std::strcmp(Argv[1], "--quick") == 0;
	const bool bCsv = Argc > 1 && std::strcmp(Argv[Argc - 1], "--csv") == 0;
	const std::vector<FReferenceCheck> Checks = RunReferenceChecks(bQuick);
	int Fails = 0;
	if (bCsv) std::printf("group,check,value,low,high,unit,pass,source\n");
	for (const FReferenceCheck& C : Checks)
	{
		Fails += !C.Pass();
		if (bCsv)
		{
			std::printf("%s,\"%s\",%.2f,%.2f,%.2f,%s,%s,\"%s\"\n", C.Group.c_str(), C.Name.c_str(), C.Value, C.Low, C.High, C.Unit.c_str(), C.Pass() ? "yes" : "NO", C.Source.c_str());
		}
		else
		{
			std::printf("%-10s %-52s %7.2f %-5s [%6.2f .. %6.2f] %s\n", C.Group.c_str(), C.Name.c_str(), C.Value, C.Unit.c_str(), C.Low, C.High, C.Pass() ? "ok" : "<-- OUT");
		}
	}
	if (!bCsv) std::printf("\n%d of %zu checks outside their reference range\n", Fails, Checks.size());
	return Fails ? 1 : 0;
}
