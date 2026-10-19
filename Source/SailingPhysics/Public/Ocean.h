#pragma once

#include "SailingPhysicsApi.h"
#include "Waves.h"
#include <array>
#include <atomic>
#include <mutex>
#include <complex>
#include <cstdint>
#include <vector>

namespace Sailing
{
	class FLakeTerrain;

	/** The open sea: the local wind sea and a swell from far away. */
	struct SAILINGPHYSICS_API FOceanParams
	{
		double WindMs = 6.0;            // at 10 m
		double WindFromRad = 0.0;       // where the wind comes from (map frame, 0 = north)
		double WindSeaFraction = 1.0;   // how developed the wind sea is (1 = fully developed for this wind)
		/** Prologue step 4: a fetch-limited wind sea given outright (the mistral's short steep sea: higher and shorter than
		 *  WindSeaFraction's partly developed sea, which keeps Pierson-Moskowitz's height-to-period). 0 = from the wind. */
		double WindSeaHs = 0.0;         // m
		double WindSeaTp = 0.0;         // s
		double SwellHs = 1.0;           // m, significant height of the swell
		double SwellTp = 9.0;           // s, its peak period
		double SwellFromRad = 2.4;      // where it comes from (the Gulf swell runs in from the southeast)
		uint32_t Seed = 7;
	};

	/**
	 * An FFT ocean (Tessendorf): a directional wave spectrum (JONSWAP wind sea with cos^2 spreading about the wind, plus
	 * a narrow JONSWAP swell) turned into a periodic height field by inverse FFT, in two cascades: long waves on a
	 * 480 m tile (30 m and up) and short ones on a 60 m tile (2 to 30 m), each 64 x 64. Height, vertical velocity and
	 * slopes come from four transforms per cascade, evaluated for any time (deep-water dispersion) and cached. The
	 * boat samples the grids bilinearly; the renderer uploads the same grids as textures and samples them the same
	 * way, so she floats on the waves you see.
	 */
	class SAILINGPHYSICS_API FOcean
	{
	public:
		static constexpr int N = 64;
		static constexpr int NumCascades = 2;
		static constexpr double Tile[NumCascades] = { 480.0, 60.0 };

		struct FGrid
		{
			double Time = -1e30;
			std::vector<float> H, Vz, Sx, Sy; // N x N, row = X (north) index, column = Y (east) index
		};

		FOcean();
		void Configure(const FOceanParams& Params);
		const FOceanParams& GetParams() const { return Params; }
		/** Changes with every Configure (the spectrum and its bands are new). */
		uint64_t GetGeneration() const { return Generation; }

		/** Height (m) at a point and time. */
		double Height(double X, double Y, double T) const;
		/** Height, vertical velocity and slopes (dh/dx, dh/dy) at a point and time. */
		void Sample(double X, double Y, double T, double& OutHeight, double& OutVz, double& OutSlopeX, double& OutSlopeY) const;
		/** The grids of one cascade at a time (for the renderer). */
		const FGrid& Evaluate(int Cascade, double T) const;

		/** Significant wave height (4 sqrt(m0)) of everything, of the wind sea and of the swell. */
		double SignificantHeight() const { return HsTotal; }
		double WindSeaHs() const { return HsWind; }
		double MeanPeriod() const { return Tm01; }
		/** Direction the energy travels toward, radians. */
		double MeanDirection() const { return MeanDir; }
		/**
		 * Where the open sea reaches: 1 in open water exposed to the swell, falling to 0 behind the barrier islands and in
		 * the bays (fetch toward the swell under 3 km), and limited by depth (waves break at a height of about 0.6 times
		 * the depth, so they die away across the shoals to the beach). Built on a grid of Cell meters over the terrain;
		 * without it the sea is everywhere.
		 */
		void BuildMask(const FLakeTerrain& Terrain, double Cell = 100.0);
		double MaskAt(double X, double Y) const;
		struct FMask { int Rows = 0, Cols = 0; double Cell = 100.0, X0 = 0.0, Y0 = 0.0; std::vector<float> Values; };
		const FMask& GetMask() const { return Mask; }

		/** The spectrum in 16 wavelength bins (2 to 500 m, log spaced): variance and mean travel direction of each. */
		const std::vector<struct FWaveBand>& Bands() const { return BandList; }

	private:
		struct FMode
		{
			double Kx = 0.0, Ky = 0.0, Omega = 0.0, Amplitude = 0.0, Phase = 0.0;
		};
		std::array<std::vector<FMode>, NumCascades> Modes; // N x N per cascade, FFT order
		FOceanParams Params;
		double HsTotal = 0.0, HsWind = 0.0, Tm01 = 0.0, MeanDir = 0.0;
		std::vector<struct FWaveBand> BandList;
		FMask Mask;

		uint64_t Generation = 0;
		static constexpr int CacheSize = 8;
		mutable std::array<std::array<FGrid, CacheSize>, NumCascades> Cache;
		mutable std::array<int, NumCascades> CacheNext{};
		mutable std::vector<std::complex<double>> Work[4];
		// Perf 1: boats stepping in parallel share the cache. A slot's time is published (release) once its grid is
		// filled and found without the lock; a miss evaluates under it. A slot is reused only CacheSize grid times later
		// (a quarter second at 30 Hz), long after any step that found it is done with it.
		mutable std::array<std::array<std::atomic<double>, CacheSize>, NumCascades> CacheTime;
		mutable std::mutex CacheLock;
	};
}
