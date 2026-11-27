#pragma once

#include "CoreMinimal.h"
#include "Templates/Function.h"

/**
 * docs/long-sail-soak: the long-sail memory test's sums. With -SailingBenchTrace the bench writes a row a minute
 * (Saved/Bench/<shot>.mem.csv): time, where the boat is, how far she has come, the process's memory and what the world
 * streamer holds. At the end it fits a straight line through the rows after the warm-up and reports the growth an hour and
 * per 100 km sailed in bench.json, with a verdict against -SailingMemBudget=<MB/h> (50 by default).
 *
 * A game that streams its world properly holds about the same memory at hour 6 as at hour 1, wherever the boat is: the
 * slope is near zero. Growth that follows the distance (MB per 100 km) and not the time is something loaded and never
 * dropped; growth that follows the time with the boat parked is a per-frame leak.
 */
namespace SailingSoak
{
	struct FMemRow
	{
		double T = 0.0;            // s since the bench started
		double TravelledM = 0.0;   // map metres sailed (or slid by -SailingRun) since the start
		double UsedMB = 0.0;       // the process's used physical memory
	};

	struct FMemFit
	{
		int32 Rows = 0;              // rows after the warm-up
		double MBPerHour = 0.0;      // the least-squares slope against time
		double MBPer100Km = 0.0;     // ... against distance (0 when she hasn't moved 1 km)
		double FirstMB = 0.0, LastMB = 0.0, PeakMB = 0.0;
	};

	/** The rows from WarmupS on (the first 10 minutes fill caches and pools: their growth isn't a leak). */
	inline FMemFit Fit(const TArray<FMemRow>& All, double WarmupS = 600.0)
	{
		FMemFit Out;
		TArray<const FMemRow*> R;
		for (const FMemRow& Row : All) if (Row.T >= WarmupS) R.Add(&Row);
		Out.Rows = R.Num();
		if (R.Num() == 0) return Out;
		Out.FirstMB = R[0]->UsedMB;
		Out.LastMB = R.Last()->UsedMB;
		for (const FMemRow* Row : R) Out.PeakMB = FMath::Max(Out.PeakMB, Row->UsedMB);
		if (R.Num() < 3) return Out;
		auto Slope = [&R](TFunctionRef<double(const FMemRow&)> X) -> double
		{
			double Mx = 0.0, My = 0.0;
			for (const FMemRow* Row : R) { Mx += X(*Row); My += Row->UsedMB; }
			Mx /= R.Num(); My /= R.Num();
			double Sxy = 0.0, Sxx = 0.0;
			for (const FMemRow* Row : R) { const double Dx = X(*Row) - Mx; Sxy += Dx * (Row->UsedMB - My); Sxx += Dx * Dx; }
			return Sxx > 0.0 ? Sxy / Sxx : 0.0;
		};
		Out.MBPerHour = Slope([](const FMemRow& Row) { return Row.T; }) * 3600.0;
		if (R.Last()->TravelledM - R[0]->TravelledM >= 1000.0) Out.MBPer100Km = Slope([](const FMemRow& Row) { return Row.TravelledM; }) * 100000.0;
		return Out;
	}
}
