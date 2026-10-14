#pragma once

#include "SailingPhysicsApi.h"
#include "Waves.h"
#include <complex>
#include <cstdint>
#include <vector>

namespace Sailing
{
	/**
	 * Visual V4: the short waves the eye reads, as an FFT of the same sea.
	 *
	 * The physics carries the lake chop as 48 wave trains (FWaveField). The boat moves to the long ones; the short ones
	 * are too few and too regular to look like water (three directions per band, the crisscross Bean spotted in the
	 * blind test). So the renderer draws the physics' trains longer than 4 m (below SplitHz) exactly, and the shorter
	 * waves from this: the same fetch-limited JONSWAP spectrum and cos^2 spreading about the wind, at the same
	 * normalization as FWaveField, laid out on an FFT grid of thousands of modes with random phases. Two cascades: chop
	 * from 4 m down to about 0.4 m on a 23 m tile, and capillary-gravity ripples (High) on a 3.1 m tile.
	 *
	 * Each evaluation gives the height, the horizontal (choppy) displacement that sharpens crests and flattens troughs,
	 * the slopes for the normals, and the Jacobian of the choppy map: where it drops toward zero a crest is folding, which
	 * is where foam and whitecaps form. The renderer evaluates it off the game thread at 30 Hz and blends between frames.
	 */
	struct SAILINGPHYSICS_API FWaveDetailParams
	{
		double WindMs = 5.0;
		double TravelDirRad = 0.0;     // direction the waves travel toward (map frame)
		double FetchMeters = 4000.0;
		double SplitHz = 0.62;         // shorter than this (about 4 m) comes from the FFT; longer from the physics trains
		double Development = 1.0;      // the sea's growth toward its target (current / target Hs, as FWaveField)
		double Choppiness = 1.0;       // horizontal displacement factor (Tessendorf's lambda)
		uint32_t Seed = 3;
	};

	class SAILINGPHYSICS_API FWaveDetail
	{
	public:
		struct FCascadeSpec { int N = 128; double Tile = 23.0; double MinWavelength = 0.4, MaxWavelength = 4.0; };
		struct FGrid
		{
			int N = 0;
			double Tile = 0.0, Time = 0.0;
			// N x N, row = X (north) index, column = Y (east): height, choppy displacement, slopes, Jacobian (1 = flat).
			std::vector<float> H, Dx, Dy, Sx, Sy, J;
		};

		/** Default cascades: chop (128^2 over 23 m, 0.4-4 m) and ripples (64^2 over 3.1 m, 0.1-0.4 m). */
		static FCascadeSpec ChopCascade() { return { 128, 23.0, 0.4, 4.0 }; }
		static FCascadeSpec RippleCascade() { return { 64, 3.1, 0.1, 0.4 }; }

		void Configure(const FWaveDetailParams& Params, const std::vector<FCascadeSpec>& Cascades);
		const FWaveDetailParams& GetParams() const { return Params; }
		int NumCascades() const { return int(Cascades.size()); }
		const FCascadeSpec& Spec(int Cascade) const { return Cascades[Cascade].Spec; }

		/** Evaluates a cascade at time T (thread safe: no shared mutable state). Scale multiplies every amplitude (the
		 *  sea growing or dying between reconfigurations). */
		void Evaluate(int Cascade, double T, FGrid& Out, double Scale = 1.0) const;
		/** The spectrum's variance in a cascade (m^2), as configured (the realized grid matches it on average). */
		double Variance(int Cascade) const { return Cascades[Cascade].Variance; }
		/** Bilinear sample of a grid at a map point (periodic). */
		static void Sample(const FGrid& G, double X, double Y, double& OutH, double& OutDx, double& OutDy, double& OutJ);

		/** The physics' spectral density normalization for this sea (the same JONSWAP scale FWaveField uses), m^2 s. */
		static double SpectrumAt(double FrequencyHz, double WindMs, double FetchMeters);

	private:
		/** The JONSWAP scale for this sea (an integral: computed once per Configure) and its peak frequency. */
		static double SpectrumScale(double WindMs, double FetchMeters, double& OutPeakHz);
		static double ShapedSpectrum(double FrequencyHz, double PeakHz, double Scale);

		struct FMode { double Kx = 0.0, Ky = 0.0, K = 0.0, Omega = 0.0; std::complex<double> H0, H0MinusConj; };
		struct FCascade { FCascadeSpec Spec; std::vector<FMode> Modes; double Variance = 0.0; };
		FWaveDetailParams Params;
		std::vector<FCascade> Cascades;
	};
}
