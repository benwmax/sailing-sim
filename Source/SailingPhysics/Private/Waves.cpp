#include "Waves.h"
#include "Ocean.h"
#include "SeaState.h"

namespace Sailing
{
	namespace
	{
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
		return GrowthLawPeriod(Ua, FetchMeters) * std::pow(Older, 2.0 / 3.0);
	}

	void FWaveField::SetWind(const FWaveParams& InParams)
	{
		const uint32_t Seed = Params.Seed;
		Params = InParams;
		Params.Seed = Seed;
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
			// cos^2 spreading over the band's directions, normalized within the band.
			double Weights[kWaveDirectionsPerBand];
			double Sum = 0.0;
			for (int D = 0; D < kWaveDirectionsPerBand; ++D)
			{
				const FWaveComponent& C = Components[B * kWaveDirectionsPerBand + D];
				const double Rel = WrapAngle(std::atan2(C.Ky, C.Kx) - TravelDir);
				const double W = std::fabs(Rel) < kPi * 0.5 ? std::pow(std::cos(Rel), 2.0) : 0.0;
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
		bBandsDirty = true;
	}

	double FWaveField::Height(double X, double Y, double T) const
	{
		float Ratio[kSeaChannels];
		SeaRatiosAt(X, Y, Ratio);
		double H = 0.0;
		for (int I = 0; I < kWaveComponents; ++I)
		{
			const FWaveComponent& C = Components[I];
			if (C.Amplitude > 1e-6)
			{
				H += C.Amplitude * Ratio[std::min(I, kSeaLongComponents)] * std::sin(C.Kx * X + C.Ky * Y - C.Omega * T + C.Phase);
			}
		}
		if (Ocean) H += Ocean->Height(X, Y, T);
		return H;
	}

	void FWaveField::Sample(double X, double Y, double T, double& OutHeight, double& OutVerticalVelocity, double& OutSlopeX, double& OutSlopeY) const
	{
		OutHeight = OutVerticalVelocity = OutSlopeX = OutSlopeY = 0.0;
		float Ratio[kSeaChannels];
		SeaRatiosAt(X, Y, Ratio);
		for (int I = 0; I < kWaveComponents; ++I)
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

	double FWaveField::SignificantHeight() const
	{
		double Variance = 0.0;
		for (const FWaveComponent& C : Components) Variance += 0.5 * C.Amplitude * C.Amplitude;
		if (Ocean) Variance += Ocean->SignificantHeight() * Ocean->SignificantHeight() / 16.0;
		return 4.0 * std::sqrt(Variance);
	}

	double FWaveField::SignificantHeightAt(double X, double Y) const
	{
		float Ratio[kSeaChannels];
		SeaRatiosAt(X, Y, Ratio);
		double Variance = 0.0;
		for (int I = 0; I < kWaveComponents; ++I)
		{
			const double A = Components[I].Amplitude * Ratio[std::min(I, kSeaLongComponents)];
			Variance += 0.5 * A * A;
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
		for (const FWaveComponent& C : Components)
		{
			const double K = std::sqrt(C.Kx * C.Kx + C.Ky * C.Ky);
			const double E = C.Amplitude * C.Amplitude;
			if (K > 0.0) { X += E * C.Kx / K; Y += E * C.Ky / K; }
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
		for (const FWaveComponent& C : Components)
		{
			const double Energy = C.Amplitude * C.Amplitude;
			E += Energy;
			EW += Energy * C.Omega;
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
		if (!bBandsDirty && OceanGeneration == BandOceanGeneration) return BandCache;
		bBandsDirty = false;
		BandOceanGeneration = OceanGeneration;
		BandCache.clear();
		BandComponent.clear();
		for (int I = 0; I < kWaveComponents; ++I)
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
		std::lock_guard<std::mutex> Lock(BandLock.M);
		for (size_t I = 0; I < BandComponent.size() && I < Out.size(); ++I)
		{
			const double R = Ratio[std::min(BandComponent[I], kSeaLongComponents)];
			Out[I].Variance *= R * R;
		}
	}
}
