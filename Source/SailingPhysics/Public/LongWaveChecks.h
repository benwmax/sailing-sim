#pragma once

#include "SailingPhysicsApi.h"
#include "LongWaves.h"
#include <string>
#include <vector>

namespace Sailing
{
	/**
	 * docs/long-wave-fft/: the long-wave FFT's checks, shared by the automation tests (SailingSim.Physics.LongWaves.*) and
	 * the standalone tool (scripts/long-wave-check.sh). Each returns whether it holds and what it measured.
	 */
	struct FLongWaveCheck
	{
		std::string Name;
		bool bPass = false;
		std::vector<std::string> Lines; // what it measured, one finding a line
	};

	namespace LongWaveChecks
	{
		/** Configured variance = the sines' bands 0-7 (1%) at 10, 15, 20, 28 kn; Tm01 within 2%, mean direction 2 deg; each
		 *  cascade's modes inside its wavelength range. */
		SAILINGPHYSICS_API FLongWaveCheck Spectrum(ELongWaveLayout Layout = ELongWaveLayout::PerBand);
		/** Every field at random grid nodes and three keys equals the straight sum over the modes (1e-4, scaled by the field). */
		SAILINGPHYSICS_API FLongWaveCheck MatchesDirectSum(ELongWaveLayout Layout = ELongWaveLayout::PerBand);
		/** Blending keys linearly is within 2% (of L1's RMS) of the exact L1 surface half way between keys. */
		SAILINGPHYSICS_API FLongWaveCheck TimeBlend(ELongWaveLayout Layout = ELongWaveLayout::PerBand);
		/** The modes' energy by direction follows the bands' sech^2 spreading (no spikes). */
		SAILINGPHYSICS_API FLongWaveCheck Spreading(ELongWaveLayout Layout = ELongWaveLayout::PerBand);
		/** Each band reaches 1 - 1/e of its height in GrowthSeconds (3%). */
		SAILINGPHYSICS_API FLongWaveCheck Growth(ELongWaveLayout Layout = ELongWaveLayout::PerBand);
		/** 30 and 90 deg wind shifts: the height at a point never steps; after 3 tau the old direction's energy is under 5%. */
		SAILINGPHYSICS_API FLongWaveCheck WindShift(ELongWaveLayout Layout = ELongWaveLayout::PerBand);
		/** 30 s of world time stepped at 30, 60 and 144 fps gives the same grids to the bit. */
		SAILINGPHYSICS_API FLongWaveCheck FrameRateFree(ELongWaveLayout Layout = ELongWaveLayout::PerBand);
		/** The same grids to the bit on 1, 2 and 8 workers, and after a restart at the same world time. */
		SAILINGPHYSICS_API FLongWaveCheck Determinism(ELongWaveLayout Layout = ELongWaveLayout::PerBand);
		/** At t = 1e6 s, heights within 1 mm of the straight sum. */
		SAILINGPHYSICS_API FLongWaveCheck LongClock(ELongWaveLayout Layout = ELongWaveLayout::PerBand);
		/** 64 heights from a fixed seed against the checked-in table (1e-5 m). */
		SAILINGPHYSICS_API FLongWaveCheck Golden(ELongWaveLayout Layout = ELongWaveLayout::PerBand);
		/** The 20 kn sea's height autocorrelation over a 300 m patch has no peak past 0.25 away from zero lag, but at the
		 *  cascades' tile lags (reported); the 24 sines' (reported) for comparison. */
		SAILINGPHYSICS_API FLongWaveCheck NoWeave(ELongWaveLayout Layout = ELongWaveLayout::PerBand);

		/** All of the above, in order. */
		SAILINGPHYSICS_API std::vector<FLongWaveCheck> RunAll(ELongWaveLayout Layout = ELongWaveLayout::PerBand);
	}
}
