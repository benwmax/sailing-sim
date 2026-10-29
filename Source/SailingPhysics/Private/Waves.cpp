#include "Waves.h"
#include "LongWaves.h"
#include "Ocean.h"
#include "SeaState.h"

namespace Sailing
{
	namespace
	{
		/** Bands() entries from the long waves' cascade C carry kLongBandCode + C in BandComponent. */
		constexpr int kLongBandCode = 1000;
		constexpr double kMinFrequency = 0.18; // Hz (wavelength about 48 m)
		constexpr double kMaxFrequency = 2.4;  // Hz (about 0.27 m)
	}

	double FWaveField::BandCentreHz(int B)
	{
		const double Ratio = std::pow(kMaxFrequency / kMinFrequency, 1.0 / kWaveBands);
		const double F0 = kMinFrequency * std::pow(Ratio, B);
		return std::sqrt(F0 * F0 * Ratio);
	}

	double FWaveField::BandWidthHz(int B)
	{
		const double Ratio = std::pow(kMaxFrequency / kMinFrequency, 1.0 / kWaveBands);
		const double F0 = kMinFrequency * std::pow(Ratio, B);
		return F0 * Ratio - F0;
	}

	namespace
	{
		/** The JONSWAP shape of ComputeTargetAmplitudes (gamma 3.3), unscaled. */
		double JonswapShape(double F, double Fp)
		{
			const double Sigma = F <= Fp ? 0.07 : 0.09;
			const double R = std::exp(-(F - Fp) * (F - Fp) / (2.0 * Sigma * Sigma * Fp * Fp));
			return std::pow(F, -5.0) * std::exp(-1.25 * std::pow(Fp / F, 4.0)) * std::pow(3.3, R);
		}

		/** Wavenumber of angular frequency Omega in depth H (omega^2 = g k tanh(k h)); deep water when H <= 0. */
		double WavenumberFor(double Omega, double H)
		{
			const double Deep = Omega * Omega / kGravity;
			if (H <= 0.0) return Deep;
			// Newton from the deep (or the shallow, whichever is longer) wavenumber; it converges in a few steps.
			double K = std::max(Deep, Omega / std::sqrt(kGravity * H));
			for (int I = 0; I < 30; ++I)
			{
				const double T = std::tanh(K * H);
				const double F = kGravity * K * T - Omega * Omega;
				const double D = kGravity * (T + K * H * (1.0 - T * T));
				const double Next = K - F / D;
				if (std::fabs(Next - K) < 1e-12 * K) { K = Next; break; }
				K = Next;
			}
			return K;
		}
	}

	double FWaveField::BandAmplitudeFactor(int Band, double WindMs, double FetchMeters)
	{
		if (WindMs < 0.5) return 0.0;
		const double Hs = TargetSignificantHeight(WindMs, FetchMeters);
		const double Fp = 1.0 / TargetPeakPeriod(WindMs, FetchMeters);
		double Variance = 0.0;
		for (int B = 0; B < kWaveBands; ++B) Variance += JonswapShape(BandCentreHz(B), Fp) * BandWidthHz(B);
		const double Scale = Variance > 1e-12 ? (Hs / 4.0) / std::sqrt(Variance) : 0.0;
		return Scale * std::sqrt(2.0 * JonswapShape(BandCentreHz(Band), Fp) * BandWidthHz(Band));
	}

	FWaveField::FWaveField(uint32_t Seed)
	{
		Params.Seed = Seed;
		uint32_t S = Seed ? Seed * 2654435761u : 1u;
		auto Rand = [&S]()
		{
			S ^= S << 13; S ^= S >> 17; S ^= S << 5;
			return (S % 1000000u) / 1000000.0;
		};

		// Log-spaced frequency bands; in each band a few directions spread around the compass with jitter,
		// so every wind direction finds components close to it and the pattern never looks regular.
		const double Ratio = std::pow(kMaxFrequency / kMinFrequency, 1.0 / kWaveBands);
		for (int B = 0; B < kWaveBands; ++B)
		{
			const double F0 = kMinFrequency * std::pow(Ratio, B);
			const double F1 = F0 * Ratio;
			BandWidth[B] = F1 - F0;
			const double Offset = Rand() * 2.0 * kPi;
			for (int D = 0; D < kWaveDirectionsPerBand; ++D)
			{
				FWaveComponent& C = Components[B * kWaveDirectionsPerBand + D];
				const double F = F0 + (F1 - F0) * (0.2 + 0.6 * Rand());
				const double Omega = 2.0 * kPi * F;
				const double K = Omega * Omega / kGravity;
				const double Dir = Offset + D * 2.0 * kPi / kWaveDirectionsPerBand + (Rand() - 0.5) * 0.6;
				C.Kx = K * std::cos(Dir);
				C.Ky = K * std::sin(Dir);
				C.Omega = Omega;
				C.Phase = Rand() * 2.0 * kPi;
				C.Amplitude = 0.0;
			}
			BandFrequency[B] = std::sqrt(F0 * F1);
		}
		for (double& A : TargetAmplitude) A = 0.0;
	}

	double FWaveField::AdjustedWindSpeed(double WindMs)
	{
		// The wind-stress factor of the fetch-limited growth laws: U_A = 0.71 U^1.23 (U the 10 m wind in m/s). Stress on
		// the water grows faster than the speed (the drag coefficient rises with the wind), so the same laws written in U_A
		// grow a strong wind's sea faster than in U. Shore Protection Manual (1984) eq. 3-28, the form the Coastal
		// Engineering Manual (EM 1110-2-1100, Part II-2) discusses and keeps for these SPM growth curves. W3's SWAN bake of
		// Ray Hubbard: with U the lake's median Hs was 16% low at 18 kn, 35% at 22 and 61% at 28 (docs/w3-prep).
		return WindMs > 0.0 ? 0.71 * std::pow(WindMs, 1.23) : 0.0;
	}

	double FWaveField::GrowthStressWind(double WindMs)
	{
		// Physics gaps: past 18 kn the lake's sea grows faster than U_A gives. In W3's SWAN bake of Ray Hubbard the median
		// Hs goes as U^1.2 from 5 to 14 kn (U_A's own 1.23) but as U^1.68 from 18 to 22 kn and U^1.66 from 22 to 28, and in
		// U_A the game was 9% low at 22 kn and 18% at 28. It isn't the fetch: the shortfall grows with the wind alike over
		// the lake's short and long fetches (SWAN / game rose 1.50 times at the 10th percentile, 1.49 at the median and 1.65
		// at the 90th from 14 to 28 kn), none of it sits at the 15 km cap, and full development (gF/U_A^2 = 2.3e4) is far
		// off. It's the young, strongly forced end of the growth law: at 28 kn the lake's median effective fetch (1.6 km) is
		// gF/U_A^2 = 45, against 250 at 14 kn, and SWAN's wind input there (Yan 1987, used with the Westhuysen whitecapping
		// the bake ran) grows with (u*/c)^2, faster than the SPM's power law fitted to older seas. So above 18 kn the stress
		// wind steepens by (U / 18 kn)^0.43, which makes Hs go as U^1.66 there, as SWAN's does (docs/physics-gaps). It is
		// continuous at 18 kn and leaves everything below it, the reference checks' 15 kn included, as it was.
		constexpr double KneeMs = 18.0 * kKnot;
		return AdjustedWindSpeed(WindMs) * (WindMs > KneeMs ? std::pow(WindMs / KneeMs, 0.43) : 1.0);
	}

	double FWaveField::GrowthLawHeight(double StressWindMs, double FetchMeters)
	{
		const double U2 = StressWindMs * StressWindMs;
		if (U2 <= 0.0) return 0.0;
		const double Dimensionless = std::min(0.0016 * std::sqrt(kGravity * FetchMeters / U2), 0.243);
		return Dimensionless * U2 / kGravity;
	}

	double FWaveField::GrowthLawPeriod(double StressWindMs, double FetchMeters)
	{
		const double U2 = StressWindMs * StressWindMs;
		if (U2 <= 0.0) return 1.0;
		const double Dimensionless = std::min(0.286 * std::cbrt(kGravity * FetchMeters / U2), 8.13);
		return std::max(Dimensionless * StressWindMs / kGravity, 0.6);
	}

	double FWaveField::TargetSignificantHeight(double WindMs, double FetchMeters)
	{
		if (WindMs < 0.5) return 0.0;
		return GrowthLawHeight(GrowthStressWind(WindMs), FetchMeters);
	}

	double FWaveField::TargetPeakPeriod(double WindMs, double FetchMeters)
	{
		if (WindMs < 0.5) return 1.0;
		// Mac polish: the period of the steepened sea follows Toba's 3/2 law in U_A, not the stress wind. GrowthStressWind
		// stands in for SWAN's faster growth of a young sea above 18 kn, but the air's stress on the water is still U_A's:
		// the extra height comes from the sea being further along its growth (older, in effect a longer fetch), not from a
		// stronger wind. The SPM pair is Toba's law, Hs ~ U_A^(1/2) Tp^(3/2) (Hs ~ U_A F^(1/2), Tp ~ U_A^(1/3) F^(1/3)), so
		// at the same U_A the period goes as Hs^(2/3): (U / 18 kn)^0.29 above 18 kn where the stress wind gave its cube
		// root, (U / 18 kn)^0.14. SWAN's lake medians follow Toba within 3% from 18 to 28 kn (Hs x2.09, Tp x1.41 against
		// x1.37 from the law), and the game's periods there were 7% short at 22 kn and 11% at 28 (docs/mac-polish).
		const double Ua = AdjustedWindSpeed(WindMs);
		const double HsA = GrowthLawHeight(Ua, FetchMeters);
		const double Older = HsA > 0.0 ? TargetSignificantHeight(WindMs, FetchMeters) / HsA : 1.0;
		return GrowthLawPeriod(Ua, FetchMeters) * std::pow(Older, 2.0 / 3.0) * ShortFetchPeriodFactor(WindMs, FetchMeters);
	}

	double FWaveField::ShortFetchPeriodFactor(double WindMs, double FetchMeters)
	{
		// docs/lake-periods/: SWAN's peak period on Ray Hubbard (the PC's bake, origin/w3-swan-bake: ten points, 16 directions,
		// seven speeds; scripts/wave-check.sh --map) runs longer than this law at the point's effective fetch, and the
		// shorter the fetch the more: 1.21-1.32 times under 400 m, 1.08-1.31 under 1 km, 1.01-1.11 past it, at 8-28 kn; none
		// at 5 kn. A young sea on a short fetch is driven harder than the SPM law (fitted to older seas) allows, and part of
		// that period is the open lake's sea reaching round into the lee. Fitted to the binned medians, as #41 fitted the
		// height: 1 + (80 m / F) (U / 14 kn)^0.125, blended in from 5 to 10 kn, F floored at 200 m (the bake's floor). The
		// binned bias falls from 0.128 to 0.041 rms in log period (0.037 with (50 m / F)^0.75, which also lengthened the
		// open lake's 8 km sea 2%: the fetch's own power keeps the long fetches the law's).
		const double U = WindMs / 0.514444;
		const double F = std::max(FetchMeters, 200.0);
		const double T = Clamp((U - 5.0) / 5.0, 0.0, 1.0);
		return 1.0 + 80.0 / F * std::pow(std::max(U, 1e-3) / 14.0, 0.125) * T * T * (3.0 - 2.0 * T);
	}

	double FWaveField::SpreadingBeta(double F, double Fp)
	{
		// Donelan, Hamilton and Hui (1985), 0.56 < f/fp < 1.6; Banner (1990) past 1.6; held at 0.56's below it.
		const double R = Fp > 0.0 ? std::max(F / Fp, 0.56) : 1.6;
		if (R < 0.95) return 2.61 * std::pow(R, 1.3);
		if (R < 1.6) return 2.28 * std::pow(R, -1.3);
		return std::pow(10.0, -0.4 + 0.8393 * std::exp(-0.567 * std::log(R * R)));
	}

	double FWaveField::DirectionalSpreading(double F, double Fp, double Theta)
	{
		const double B = SpreadingBeta(F, Fp);
		const double C = 1.0 / std::cosh(B * Theta);
		// Normalized over -pi..pi (tanh(B pi) of the infinite line's integral).
		return 0.5 * B * C * C / std::tanh(B * kPi);
	}

	double FWaveField::SideAngle(double Beta)
	{
		// The spreading's mean cos(theta) over -pi..pi (a sech^2 has no closed form for it).
		constexpr int N = 720;
		double Mean = 0.0, Sum = 0.0;
		for (int I = 0; I < N; ++I)
		{
			const double T = -kPi + (I + 0.5) * 2.0 * kPi / N;
			const double C = 1.0 / std::cosh(Beta * T);
			Mean += C * C * std::cos(T);
			Sum += C * C;
		}
		Mean /= Sum;
		// Three directions weighted 1 : sech^2(beta Delta) : sech^2(beta Delta) have mean cos (1 + 2 r cos Delta) / (1 + 2 r):
		// the first Delta where that falls to the spreading's. It turns back up once r is small, so past its least it is
		// that least's Delta. Solved continuously (golden section for the least, bisection below it), not stepped: a stepped
		// search flips a whole step on a last-bit difference between platforms' maths (docs/short-wave-spreading).
		constexpr double MaxSide = 75.0 * kDegToRad;
		auto G = [Beta](double D)
		{
			const double C = 1.0 / std::cosh(Beta * D);
			const double R = C * C;
			return (1.0 + 2.0 * R * std::cos(D)) / (1.0 + 2.0 * R);
		};
		double Lo = 0.0, Hi = MaxSide;
		const double Golden = 0.5 * (std::sqrt(5.0) - 1.0);
		for (int I = 0; I < 80; ++I)
		{
			const double A = Hi - Golden * (Hi - Lo), B = Lo + Golden * (Hi - Lo);
			if (G(A) < G(B)) Hi = B; else Lo = A;
		}
		const double Least = 0.5 * (Lo + Hi);
		if (G(Least) > Mean) return Least;
		Lo = 0.0; Hi = Least;
		for (int I = 0; I < 60; ++I)
		{
			const double M = 0.5 * (Lo + Hi);
			(G(M) > Mean ? Lo : Hi) = M;
		}
		return 0.5 * (Lo + Hi);
	}

	void FWaveField::AnchorDirections(double TravelDir, double HoldX, double HoldY)
	{
		const double U = Params.WindSpeedKnots * kKnot;
		const double Fp = U < 0.5 ? 1.0 / 2.5 : 1.0 / TargetPeakPeriod(U, ReferenceFetch());
		uint32_t S = (Params.Seed ? Params.Seed : 1u) * 2246822519u + 0x9E3779B9u;
		auto Rand = [&S]()
		{
			S ^= S << 13; S ^= S >> 17; S ^= S << 5;
			return (S % 1000000u) / 1000000.0;
		};
		for (int B = 0; B < kWaveBands; ++B)
		{
			// docs/wave-jitter/ (storm-water step 2): each band's three directions drawn from the measured spreading, one in
			// each third of its probability (stratified, so the band keeps the spreading's width). At
			// -Delta, 0, +Delta in every band (the old layout) the 24 long trains crossed in the same diamond weave at 20 kn
			// and over. The sech^2 spreading's CDF is (tanh(beta theta) / tanh(beta pi) + 1) / 2, inverted in closed form.
			const double Beta = SpreadingBeta(BandFrequency[B], Fp);
			const double TanhPi = std::tanh(Beta * kPi);
			for (int D = 0; D < kWaveDirectionsPerBand; ++D)
			{
				FWaveComponent& C = Components[B * kWaveDirectionsPerBand + D];
				// (About the middle of its third, at random within the middle 60%: drawn across the whole third the outer
				// directions often fell far out and the sea came out wider than the spreading.)
				const double Q = (D + 0.5 + 0.6 * (Rand() - 0.5)) / kWaveDirectionsPerBand;
				const double Rel = Clamp(std::atanh(Clamp((2.0 * Q - 1.0) * TanhPi, -0.999999, 0.999999)) / Beta, -80.0 * kDegToRad, 80.0 * kDegToRad);
				AnchorDensity[B * kWaveDirectionsPerBand + D] = DirectionalSpreading(BandFrequency[B], Fp, Rel);
				const double Dir = TravelDir + Rel;
				const double K = WavenumberFor(C.Omega, Depth);
				const double Kx = K * std::cos(Dir), Ky = K * std::sin(Dir);
				C.Phase = std::fmod(C.Phase + (C.Kx - Kx) * HoldX + (C.Ky - Ky) * HoldY, 2.0 * kPi);
				if (C.Phase < 0.0) C.Phase += 2.0 * kPi;
				C.Kx = Kx;
				C.Ky = Ky;
			}
		}
		bAnchored = true;
		AnchorDir = TravelDir;
		++DirectionGeneration;
		bBandsDirty = true;
	}

	void FWaveField::SetWind(const FWaveParams& InParams)
	{
		const uint32_t Seed = Params.Seed;
		Params = InParams;
		Params.Seed = Seed;
		// The calibration sea keeps the constructor's directions (the fleet's polars were sailed in them).
		const double TravelDir = Params.WindFromDegrees * kDegToRad + kPi;
		if (!Params.bCalibrationSea && (!bAnchored || std::fabs(WrapAngle(TravelDir - AnchorDir)) > kReanchorRadians))
		{
			AnchorDirections(TravelDir, Params.HoldX, Params.HoldY);
		}
		ComputeTargetAmplitudes();
	}

	void FWaveField::ComputeTargetAmplitudes()
	{
		const double U = Params.WindSpeedKnots * kKnot;
		const bool bCalm = U < 0.5;
		const double Fetch = ReferenceFetch();
		const double Hs = bCalm ? 0.0 : Params.bCalibrationSea ? GrowthLawHeight(U, Fetch) : TargetSignificantHeight(U, Fetch);
		const double Tp = bCalm ? 1.0 : Params.bCalibrationSea ? GrowthLawPeriod(U, Fetch) : TargetPeakPeriod(U, Fetch);
		const double Fp = 1.0 / Tp;
		// Waves travel downwind.
		const double TravelDir = Params.WindFromDegrees * kDegToRad + kPi;

		// JONSWAP shape (gamma 3.3), scaled afterwards so the discrete sum has exactly the target Hs.
		auto Jonswap = [Fp](double F) { return JonswapShape(F, Fp); };

		double Variance = 0.0;
		for (int B = 0; B < kWaveBands; ++B)
		{
			const double BandEnergy = Jonswap(BandFrequency[B]) * BandWidth[B];
			// The measured spreading over the band's directions (cos^2 in the calibration sea), normalized within the band;
			// none travels upwind.
			double Weights[kWaveDirectionsPerBand];
			double Sum = 0.0;
			for (int D = 0; D < kWaveDirectionsPerBand; ++D)
			{
				const FWaveComponent& C = Components[B * kWaveDirectionsPerBand + D];
				const double Rel = WrapAngle(std::atan2(C.Ky, C.Kx) - TravelDir);
				// (The anchored sea's directions were drawn from the spreading, a third of the band each: weighted by the
				// spreading now over the density they were drawn at, equal while the wind is where it was.)
				const double Drawn = AnchorDensity[B * kWaveDirectionsPerBand + D];
				const double W = std::fabs(Rel) >= kPi * 0.5 ? 0.0
					: Params.bCalibrationSea ? std::pow(std::cos(Rel), 2.0)
					: DirectionalSpreading(BandFrequency[B], Fp, Rel) / (bAnchored && Drawn > 1e-12 ? Drawn : 1.0);
				Weights[D] = W;
				Sum += W;
			}
			for (int D = 0; D < kWaveDirectionsPerBand; ++D)
			{
				const double E = Sum > 1e-9 ? BandEnergy * Weights[D] / Sum : 0.0;
				TargetAmplitude[B * kWaveDirectionsPerBand + D] = std::sqrt(2.0 * E);
				Variance += E;
			}
		}
		// Scale to the target significant height: Hs = 4 sqrt(variance).
		const double Scale = Variance > 1e-12 ? (Hs / 4.0) / std::sqrt(Variance) : 0.0;
		for (double& A : TargetAmplitude) A *= Scale;
	}

	double FWaveField::GrowthSeconds(double PeriodSeconds)
	{
		return Clamp(8.0 * PeriodSeconds * PeriodSeconds, 5.0, 300.0);
	}

	void FWaveField::Update(double Dt)
	{
		for (int B = 0; B < kWaveBands; ++B)
		{
			// Exponential approach, exact for any step.
			const double T = 1.0 - std::exp(-std::max(Dt, 0.0) / GrowthSeconds(1.0 / BandFrequency[B]));
			for (int D = 0; D < kWaveDirectionsPerBand; ++D)
			{
				const int I = B * kWaveDirectionsPerBand + D;
				Components[I].Amplitude += (TargetAmplitude[I] - Components[I].Amplitude) * T;
			}
		}
		bBandsDirty = true;
	}

	void FWaveField::SnapToTarget()
	{
		for (int I = 0; I < kWaveComponents; ++I)
		{
			Components[I].Amplitude = TargetAmplitude[I];
		}
		bBandsDirty = true;
	}

	void FWaveField::SetSeaMap(std::shared_ptr<const FSeaMap> InMap)
	{
		SeaMap = std::move(InMap);
		++SeaMapGeneration;
		ComputeTargetAmplitudes();
		bBandsDirty = true;
	}

	double FWaveField::ReferenceFetch() const
	{
		return SeaMap ? SeaMap->GetReferenceFetch() : Params.FetchMeters;
	}

	void FWaveField::SeaRatiosAt(double X, double Y, float* Out) const
	{
		if (SeaMap) SeaMap->Sample(X, Y, Out);
		else for (int I = 0; I < kSeaChannels; ++I) Out[I] = 1.f;
	}

	void FWaveField::LongRatiosAt(double X, double Y, float* Out) const
	{
		float Ratio[kSeaChannels];
		SeaRatiosAt(X, Y, Ratio);
		LongRatiosFrom(Ratio, Out);
	}

	void FWaveField::LongRatiosFrom(const float* SeaRatio, float* Out) const
	{
		for (int C = 0; C < kLongCascades; ++C) Out[C] = 1.f;
		if (!SeaMap || !LongWaves) return;
		// A band's channel: its three sines' ratios, weighted by their share of the band's energy (their directions were
		// drawn from the spreading, so this is the band's ratio over directions, as SeaMapSwan's per-mode one).
		auto Weighted = [this, SeaRatio](int First, int Count)
		{
			double E = 0.0, ER = 0.0, Sum = 0.0;
			for (int I = First; I < First + Count; ++I)
			{
				const double W = TargetAmplitude[I] * TargetAmplitude[I];
				E += W;
				ER += W * double(SeaRatio[I]) * SeaRatio[I];
				Sum += SeaRatio[I];
			}
			return float(E > 1e-12 ? std::sqrt(ER / E) : Sum / Count);
		};
		for (int C = 0; C < LongWaves->NumCascades(); ++C)
		{
			const int Band = LongWaves->Spec(C).Band;
			Out[C] = Band >= 0 && Band < kSeaLongComponents / kWaveDirectionsPerBand
				? Weighted(Band * kWaveDirectionsPerBand, kWaveDirectionsPerBand) : Weighted(0, kSeaLongComponents);
		}
	}

	void FWaveField::SetDepth(double DepthMeters)
	{
		Depth = std::max(DepthMeters, 0.0);
		for (FWaveComponent& C : Components)
		{
			const double Dir = std::atan2(C.Ky, C.Kx);
			const double K = WavenumberFor(C.Omega, Depth);
			C.Kx = K * std::cos(Dir);
			C.Ky = K * std::sin(Dir);
		}
		++DirectionGeneration;
		bBandsDirty = true;
	}

	double FWaveField::Height(double X, double Y, double T) const
	{
		float Ratio[kSeaChannels];
		SeaRatiosAt(X, Y, Ratio);
		double H = 0.0;
		const bool bLong = UsesLongWaves();
		for (int I = bLong ? kSeaLongComponents : 0; I < kWaveComponents; ++I)
		{
			const FWaveComponent& C = Components[I];
			if (C.Amplitude > 1e-6)
			{
				H += C.Amplitude * Ratio[std::min(I, kSeaLongComponents)] * std::sin(C.Kx * X + C.Ky * Y - C.Omega * T + C.Phase);
			}
		}
		if (bLong)
		{
			float LongRatio[kLongCascades];
			LongRatiosFrom(Ratio, LongRatio);
			double F[kLongFields];
			LongWaves->Sample(X, Y, T, LongRatio, F);
			H += F[int(ELongField::H)];
		}
		if (Ocean) H += Ocean->Height(X, Y, T);
		return H;
	}

	void FWaveField::Sample(double X, double Y, double T, double& OutHeight, double& OutVerticalVelocity, double& OutSlopeX, double& OutSlopeY) const
	{
		OutHeight = OutVerticalVelocity = OutSlopeX = OutSlopeY = 0.0;
		float Ratio[kSeaChannels];
		SeaRatiosAt(X, Y, Ratio);
		const bool bLong = UsesLongWaves();
		if (bLong)
		{
			float LongRatio[kLongCascades];
			LongRatiosFrom(Ratio, LongRatio);
			double F[kLongFields];
			LongWaves->Sample(X, Y, T, LongRatio, F);
			OutHeight = F[int(ELongField::H)];
			OutVerticalVelocity = F[int(ELongField::Vz)];
			OutSlopeX = F[int(ELongField::Sx)];
			OutSlopeY = F[int(ELongField::Sy)];
		}
		for (int I = bLong ? kSeaLongComponents : 0; I < kWaveComponents; ++I)
		{
			const FWaveComponent& C = Components[I];
			if (C.Amplitude <= 1e-6) continue;
			// (The map varies over tens of metres; its own slope is left out, as the shader leaves it.)
			const double A = C.Amplitude * Ratio[std::min(I, kSeaLongComponents)];
			const double Arg = C.Kx * X + C.Ky * Y - C.Omega * T + C.Phase;
			const double S = std::sin(Arg), Co = std::cos(Arg);
			OutHeight += A * S;
			OutVerticalVelocity += -A * C.Omega * Co;
			OutSlopeX += A * C.Kx * Co;
			OutSlopeY += A * C.Ky * Co;
		}
		if (Ocean)
		{
			double H, Vz, Sx, Sy;
			Ocean->Sample(X, Y, T, H, Vz, Sx, Sy);
			OutHeight += H;
			OutVerticalVelocity += Vz;
			OutSlopeX += Sx;
			OutSlopeY += Sy;
		}
	}

	void FWaveField::OrbitalVelocity(double X, double Y, double T, double Below, double& OutU, double& OutV) const
	{
		double Ax, Ay;
		OrbitalFlow(X, Y, T, Below, OutU, OutV, Ax, Ay);
	}

	void FWaveField::OrbitalFlow(double X, double Y, double T, double Below, double& OutU, double& OutV, double& OutAx, double& OutAy) const
	{
		OutU = OutV = OutAx = OutAy = 0.0;
		const double D = std::max(Below, 0.0);
		float Ratio[kSeaChannels];
		SeaRatiosAt(X, Y, Ratio);
		const bool bLong = UsesLongWaves();
		if (bLong)
		{
			// Each cascade's surface flow decays with depth at its velocity-weighted mean wavenumber (a band is narrow).
			float LongRatio[kLongCascades];
			LongRatiosFrom(Ratio, LongRatio);
			double MeanK[kLongCascades], Tm, Dir;
			LongWaves->Moments(nullptr, MeanK, Tm, Dir);
			for (int C = 0; C < kLongCascades; ++C)
			{
				const double K = MeanK[C], KH = K * Depth;
				// The surface field carries coth(k h): below it, cosh(k (h - d)) / cosh(k h); deep, exp(-k d).
				const double Profile = K <= 0.0 ? 1.0 : (Depth > 0.0 && KH < 6.0) ? std::cosh(K * std::max(Depth - D, 0.0)) / std::cosh(KH) : std::exp(-K * D);
				LongRatio[C] = float(LongRatio[C] * Profile);
			}
			double F[kLongFields];
			LongWaves->Sample(X, Y, T, LongRatio, F);
			OutU = F[int(ELongField::U)];
			OutV = F[int(ELongField::V)];
			OutAx = F[int(ELongField::Ax)];
			OutAy = F[int(ELongField::Ay)];
		}
		for (int I = bLong ? kSeaLongComponents : 0; I < kWaveComponents; ++I)
		{
			const FWaveComponent& C = Components[I];
			if (C.Amplitude <= 1e-6) continue;
			const double K = std::sqrt(C.Kx * C.Kx + C.Ky * C.Ky);
			if (K < 1e-9) continue;
			// Finite depth: cosh(k (h - d)) / sinh(k h); deep (kh past 6, where the two agree to 1e-5) exp(-k d).
			const double KH = K * Depth;
			const double Profile = (Depth > 0.0 && KH < 6.0) ? std::cosh(K * std::max(Depth - D, 0.0)) / std::sinh(KH) : std::exp(-K * D);
			const double Arg = C.Kx * X + C.Ky * Y - C.Omega * T + C.Phase;
			const double Along = C.Amplitude * Ratio[std::min(I, kSeaLongComponents)] * C.Omega * Profile / K;
			const double A = Along * std::sin(Arg);
			const double Acc = -Along * C.Omega * std::cos(Arg);
			OutU += A * C.Kx;
			OutV += A * C.Ky;
			OutAx += Acc * C.Kx;
			OutAy += Acc * C.Ky;
		}
		if (Ocean)
		{
			double U, V, Ax, Ay;
			Ocean->OrbitalVelocity(X, Y, T, D, U, V);
			Ocean->OrbitalAcceleration(X, Y, T, D, Ax, Ay);
			OutU += U;
			OutV += V;
			OutAx += Ax;
			OutAy += Ay;
		}
	}

	double FWaveField::SignificantHeight() const
	{
		double Variance = 0.0;
		const bool bLong = UsesLongWaves();
		for (int I = bLong ? kSeaLongComponents : 0; I < kWaveComponents; ++I) Variance += 0.5 * Components[I].Amplitude * Components[I].Amplitude;
		if (bLong)
		{
			double Var[kLongCascades], Tm, Dir;
			LongWaves->Moments(Var, nullptr, Tm, Dir);
			for (const double V : Var) Variance += V;
		}
		if (Ocean) Variance += Ocean->SignificantHeight() * Ocean->SignificantHeight() / 16.0;
		return 4.0 * std::sqrt(Variance);
	}

	double FWaveField::SignificantHeightAt(double X, double Y) const
	{
		float Ratio[kSeaChannels];
		SeaRatiosAt(X, Y, Ratio);
		double Variance = 0.0;
		const bool bLong = UsesLongWaves();
		for (int I = bLong ? kSeaLongComponents : 0; I < kWaveComponents; ++I)
		{
			const double A = Components[I].Amplitude * Ratio[std::min(I, kSeaLongComponents)];
			Variance += 0.5 * A * A;
		}
		if (bLong)
		{
			float LongRatio[kLongCascades];
			LongRatiosFrom(Ratio, LongRatio);
			double Var[kLongCascades], Tm, Dir;
			LongWaves->Moments(Var, nullptr, Tm, Dir);
			for (int C = 0; C < kLongCascades; ++C) Variance += Var[C] * LongRatio[C] * LongRatio[C];
		}
		if (Ocean) Variance += OceanShareAt(X, Y) * Ocean->SignificantHeight() * Ocean->SignificantHeight() / 16.0;
		return 4.0 * std::sqrt(Variance);
	}

	double FWaveField::OceanShareAt(double X, double Y) const
	{
		if (!Ocean) return 0.0;
		const double M = Ocean->MaskAt(X, Y);
		return M * M;
	}

	double FWaveField::MeanDirection() const
	{
		double X = 0.0, Y = 0.0;
		const bool bLong = UsesLongWaves();
		for (int I = bLong ? kSeaLongComponents : 0; I < kWaveComponents; ++I)
		{
			const FWaveComponent& C = Components[I];
			const double K = std::sqrt(C.Kx * C.Kx + C.Ky * C.Ky);
			const double E = C.Amplitude * C.Amplitude;
			if (K > 0.0) { X += E * C.Kx / K; Y += E * C.Ky / K; }
		}
		if (bLong)
		{
			// (Energy as the sines count it: a^2, twice the variance.)
			double Var[kLongCascades], Tm, Dir, E = 0.0;
			LongWaves->Moments(Var, nullptr, Tm, Dir);
			for (const double V : Var) E += 2.0 * V;
			X += E * std::cos(Dir);
			Y += E * std::sin(Dir);
		}
		if (Ocean)
		{
			const double E = 2.0 * Ocean->SignificantHeight() * Ocean->SignificantHeight() / 16.0;
			X += E * std::cos(Ocean->MeanDirection());
			Y += E * std::sin(Ocean->MeanDirection());
		}
		return std::atan2(Y, X);
	}
}

namespace Sailing
{
	double FWaveField::MeanPeriod() const
	{
		double E = 0.0, EW = 0.0;
		const bool bLong = UsesLongWaves();
		for (int I = bLong ? kSeaLongComponents : 0; I < kWaveComponents; ++I)
		{
			const FWaveComponent& C = Components[I];
			const double Energy = C.Amplitude * C.Amplitude;
			E += Energy;
			EW += Energy * C.Omega;
		}
		if (bLong)
		{
			double Var[kLongCascades], Tm, Dir, Energy = 0.0;
			LongWaves->Moments(Var, nullptr, Tm, Dir);
			for (const double V : Var) Energy += 2.0 * V;
			if (Tm > 0.0) { E += Energy; EW += Energy * 2.0 * kPi / Tm; }
		}
		if (Ocean && Ocean->MeanPeriod() > 0.0)
		{
			const double Energy = 2.0 * Ocean->SignificantHeight() * Ocean->SignificantHeight() / 16.0;
			E += Energy;
			EW += Energy * 2.0 * kPi / Ocean->MeanPeriod();
		}
		return EW > 1e-12 ? 2.0 * kPi * E / EW : 1.0;
	}

	const std::vector<FWaveBand>& FWaveField::Bands() const
	{
		std::lock_guard<std::mutex> Lock(BandLock.M);
		const uint64_t OceanGeneration = Ocean ? Ocean->GetGeneration() : ~1ull;
		const bool bLong = UsesLongWaves();
		const uint64_t LongGeneration = bLong ? LongWaves->GetSummaryGeneration() : ~1ull;
		if (!bBandsDirty && OceanGeneration == BandOceanGeneration && LongGeneration == BandLongGeneration) return BandCache;
		bBandsDirty = false;
		BandOceanGeneration = OceanGeneration;
		BandLongGeneration = LongGeneration;
		BandCache.clear();
		BandComponent.clear();
		if (bLong)
		{
			// The long waves' cascades in wavelength bins (kLongBandCode + the cascade: BandsAt scales them by its ratio).
			FLongWaves::FSummary S;
			LongWaves->GetSummary(S);
			for (int C = 0; C < kLongCascades; ++C)
				for (const FWaveBand& B : S.Bands[C])
				{
					if (B.Variance <= 1e-12) continue;
					BandComponent.push_back(kLongBandCode + C);
					BandCache.push_back(B);
				}
		}
		for (int I = bLong ? kSeaLongComponents : 0; I < kWaveComponents; ++I)
		{
			const FWaveComponent& C = Components[I];
			if (C.Amplitude <= 1e-6) continue;
			BandComponent.push_back(I);
			FWaveBand B;
			const double K = std::sqrt(C.Kx * C.Kx + C.Ky * C.Ky);
			B.Wavelength = 2.0 * kPi / std::max(K, 1e-6);
			B.Variance = 0.5 * C.Amplitude * C.Amplitude;
			B.Direction = std::atan2(C.Ky, C.Kx);
			BandCache.push_back(B);
		}
		BandOceanStart = BandCache.size();
		if (Ocean) BandCache.insert(BandCache.end(), Ocean->Bands().begin(), Ocean->Bands().end());
		return BandCache;
	}

	void FWaveField::BandsAt(double X, double Y, std::vector<FWaveBand>& Out) const
	{
		Out = Bands();
		if (!SeaMap) return;
		float Ratio[kSeaChannels];
		SeaMap->Sample(X, Y, Ratio);
		float LongRatio[kLongCascades];
		LongRatiosFrom(Ratio, LongRatio);
		std::lock_guard<std::mutex> Lock(BandLock.M);
		for (size_t I = 0; I < BandComponent.size() && I < Out.size(); ++I)
		{
			const int Code = BandComponent[I];
			const double R = Code >= kLongBandCode ? double(LongRatio[Code - kLongBandCode]) : double(Ratio[std::min(Code, kSeaLongComponents)]);
			Out[I].Variance *= R * R;
		}
	}
}
