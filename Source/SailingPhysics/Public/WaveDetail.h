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
			// W8: JCap, the Jacobian of the displacement low-passed over CapBlurTexels: where the whitecaps form.
			std::vector<float> H, Dx, Dy, Sx, Sy, J, JCap;
		};

		/** Default cascades: chop (128^2 over 23 m, 0.4-4 m) and ripples (64^2 over 3.1 m, 0.1-0.4 m). */
		static FCascadeSpec ChopCascade() { return { 128, 23.0, 0.4, 4.0 }; }
		static FCascadeSpec RippleCascade() { return { 64, 3.1, 0.1, 0.4 }; }
		/** docs/near-water/: the capillary-gravity wavelets (64^2 over 0.64 m: 1 cm texels, 2-10 cm), drawn near the camera. */
		static FCascadeSpec CapillaryCascade() { return { 64, 0.64, 0.02, 0.1 }; }
		/** Angular frequency of a wave of wavenumber K in deep water with surface tension: omega^2 = g k + (sigma / rho) k^3. */
		static double CapillaryOmega(double K);
		/** W8 (docs/water-8/whitecaps): whitecaps break on whole crests, not on the chop's 20 cm wrinkles. The full
		 *  Jacobian folded in specks 0.4 m across (463 in 6350 m^2 at the lake's 20 kn cover, read as glints); folded on
		 *  the displacement box-blurred over 2 texels (0.36 m) either way the same cover comes in 64 caps about 1 m
		 *  across, the size of a 20 kn reservoir's whitecaps. */
		static constexpr int CapBlurTexels = 2;
		/** The whitecaps' size by wind (docs/water-8/capshape-mac): with the blur fixed at W8's 0.36 m, 12 kn caps came
		 *  out as long as 20 kn ones (2-3 m along the wind at every wind). Monahan's cover falls 5.8x from 20 to 12 kn
		 *  (U^3.41); real caps get both rarer and smaller as the breakers slow with the wind (Phillips 1985's breaking
		 *  crests travel at speeds that scale with the wind: Melville and Matusov 2002). Splitting the fall evenly in log
		 *  between the caps' number and their area gives a cap length, and so the blur that sets it, as U^(3.41 / 4) =
		 *  U^0.85 under 20 kn, from W8's 20 kn fit (CapBlurTexels on the chop's 0.18 m texels) down to one texel; held
		 *  from 20 kn up (the fold table and CapSlopeAt are fitted on it: a 0.43 m blur at 25 kn read the table's mip 1
		 *  30-60 % over the grid). */
		static double CapBlurMeters(double WindMs);

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
		/** W8: bilinear sample of the whitecap Jacobian (JCap). */
		static double SampleCapJ(const FGrid& G, double X, double Y);
		/** W8: the long waves' Jacobian (the physics' trains under OmegaMax, Gerstner choppiness Chop) at a point, as
		 *  M_WaterV4's vertex shader has it on a mesh of this Spacing (m): a train shorter than 8 spacings fades out of the
		 *  fold (fully under 4), and Fade (0..1, the distance fade) scales what is left. */
		static double LongJacobian(const FWaveComponent* Components, int Count, double OmegaMax, double Chop, double X, double Y, double T,
			double Spacing = 0.0, double Fade = 1.0);
		/** LongJacobian for several (Spacing, Fade) pairs over many points (the water's four cap thresholds sample the same
		 *  points): each train's terms per pair are worked out once, its sine once per point. Equal to LongJacobian's to
		 *  rounding. */
		struct SAILINGPHYSICS_API FLongJacobians
		{
			static constexpr int MaxPairs = 4;
			struct FTerm { double Kx, Ky, Omega, Phase, Coef[MaxPairs]; };
			std::vector<FTerm> Terms;
			int Pairs = 0;
			FLongJacobians(const FWaveComponent* Components, int Count, double OmegaMax, double Chop, const double* Spacings, const double* Fades, int InPairs);
			void Evaluate(double X, double Y, double T, double* OutJ) const;
		};
		/**
		 * W8 (docs/water-8/whitecaps): the fold threshold that caps a Target share of the drawn sea, from samples of its
		 * whitecap Jacobian (long times chop), and the threshold's shift per e-fold of cover there. The renderer solves it
		 * on the sea it draws: a threshold fitted on one sea (the test's 8 km fetch) capped the lake's shorter-fetch sea at a
		 * fraction of its share, so 20 kn showed three caps in a view where Monahan's fresh-water share gives dozens.
		 * A target under eight samples is extrapolated down the tail (the quantile floored light air's cover at 1/N).
		 */
		static void CapThreshold(std::vector<float> Samples, double Target, double& OutThreshold, double& OutSlope);

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
