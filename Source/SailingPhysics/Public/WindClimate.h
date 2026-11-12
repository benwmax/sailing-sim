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
	/** Dew point, monthly mean (C): with the air temperature it sets the cumulus base (about 125 m per C of spread). */
	SAILINGPHYSICS_API double ClimateDewC(int Month, bool bCoast);
	/** Depth of the convective boundary layer (m): deep on a summer afternoon over Texas, shallow at night and at sea. */
	SAILINGPHYSICS_API double ClimateMixedLayerM(int Month, double Hour, bool bCoast);

	/** The turbulence intensity (FWindParams::GustIntensity) that gives a gust factor in FWindField. */
	SAILINGPHYSICS_API double GustIntensityForFactor(double GustFactor);

	/**
	 * A day's label read the way a sailor reads it: "10 gusting 13" means the strongest gusts you meet are about 13.
	 * Measured as the highest 3-second wind in each ten minutes over that ten minutes' mean (MeasureSailorGusts). The stations'
	 * gust factor (GustIntensityForFactor) is a smaller thing, a minute's 5-second peak over the 2-minute mean: a field built
	 * to that label met gusts half as strong again as the label (the Nov 11 2026 review: "10 gusting 13" peaked near 20).
	 *
	 * SailorGustScale returns the one factor that scales the calibrated gustiness (GustIntensity and, when set,
	 * PuffIntensity: the fine turbulence and the puffs together, so the day keeps its own mix) so that nine ten-minute
	 * stretches in ten top out at or under SailorFactor times the mean (the label is the top of the usual gusts, as a
	 * forecast's gust is). ApplySailorGust applies it. The average stretch tops out about a quarter of the way below the
	 * label's gust over the mean (12.2 on "10 gusting 13"), the rare strongest about 10 % past the label.
	 */
	SAILINGPHYSICS_API double SailorGustScale(const FWindParams& Calibrated, double SailorFactor);
	SAILINGPHYSICS_API void ApplySailorGust(FWindParams& Params, double SailorFactor);

	/** The sailor's measure (10 m, fixed points): per ten minutes, the highest 3 s mean over the ten-minute mean. */
	struct FSailorGustStats
	{
		double MeanFactor = 1.0;    // the typical strongest gust over the mean (average over the ten-minute blocks)
		double P90Factor = 1.0;     // nine ten-minute stretches in ten top out at or under this
		double MaxFactor = 1.0;     // the strongest of them all
		int Blocks = 0;
	};
	SAILINGPHYSICS_API FSailorGustStats MeasureSailorGusts(const FWindField& Wind, double Hours, int Points = 4);

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
