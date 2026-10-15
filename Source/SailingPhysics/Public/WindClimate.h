#pragma once

#include "SailingPhysicsApi.h"
#include "Wind.h"

namespace Sailing
{
	/**
	 * W1: the wind's climate, from free station data (Tools/wind/fetch_wind.sh, fit_gusts.py; docs/w1/README.md).
	 * Gust factor = the highest 5-second wind in a minute over the 2-minute mean, over water, by month and hour (local
	 * standard time): the lake's from the Dallas ASOS one-minute data converted from grass to water, the coast's from the
	 * CO-OPS Galveston Bay stations. With air and water temperature normals (stability) and the convective mixed layer.
	 */
	SAILINGPHYSICS_API double ClimateGustFactor(int Month, double Hour, bool bCoast);
	/** Median minutes between puffs at a point (ASOS 2-minute means). */
	SAILINGPHYSICS_API double ClimatePuffMinutes(int Month, double Hour, bool bCoast);
	/** Puff strength: RMS of the 2-minute mean around its half-hour mean, over water (FWindParams::PuffIntensity). */
	SAILINGPHYSICS_API double ClimatePuffStrength(int Month, double Hour, bool bCoast);
	/** Surface water temperature, monthly mean (C). */
	SAILINGPHYSICS_API double ClimateWaterC(int Month, bool bCoast);
	/** Air temperature from the monthly normal highs and lows with the usual daily cycle (C). */
	SAILINGPHYSICS_API double ClimateAirC(int Month, double Hour, bool bCoast);
	/** Depth of the convective boundary layer (m): deep on a summer afternoon over Texas, shallow at night and at sea. */
	SAILINGPHYSICS_API double ClimateMixedLayerM(int Month, double Hour, bool bCoast);

	/** The turbulence intensity (FWindParams::GustIntensity) that gives a gust factor in FWindField. */
	SAILINGPHYSICS_API double GustIntensityForFactor(double GustFactor);

	/** A field's gust statistics measured the way the stations measure them (10 m, fixed points). */
	struct FGustStats
	{
		double GustFactor = 1.0;    // sum of 5 s peaks per minute / sum of 2-minute means
		double PuffMinutes = 0.0;   // median minutes between puffs (fit_gusts.py's peak rule)
		double Sigma = 0.0;         // standard deviation of the 1 Hz speed over the mean
		double MeanFactor = 1.0;    // mean speed over the field's mean (should be 1)
		double SlowRms = 0.0;       // RMS of the 2-minute mean around its 31-minute running mean (the puffs)
	};
	SAILINGPHYSICS_API FGustStats MeasureGustStats(const FWindField& Wind, double Hours, int Points = 4);
}
