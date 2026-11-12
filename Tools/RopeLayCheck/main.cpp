// docs/rope-lay/: the rope lay's checks standalone (scripts/rope-check.sh), the same SailingSim.Visual.RopeLay.* runs.
#include "RopeLayChecks.h"

#include <cstdio>

int main()
{
	int Failed = 0;
	for (const Sailing::FRopeLayCheck& C : Sailing::RopeLayChecks::All())
	{
		std::printf("%s %s\n", C.bPass ? "PASS" : "FAIL", C.Name.c_str());
		for (const std::string& L : C.Lines) std::printf("    %s\n", L.c_str());
		Failed += C.bPass ? 0 : 1;
	}
	return Failed == 0 ? 0 : 1;
}
