#pragma once

#include "SailingPhysicsApi.h"
#include "Fft.h"
#include "Waves.h"
#include <atomic>
#include <cstdint>
#include <functional>
#include <memory>
#include <mutex>
#include <vector>

namespace Sailing
{
	class FSeaFetch;

	/**
	 * Storm water step 5 (docs/long-wave-fft/): one cascade of the long-wave FFT. Each carries one wavelength range of the
	 * spectrum on its own periodic tile, turned against the others so their repeats never line up (nor with the 23 m chop).
	 */
	struct FLongWaveCascadeSpec
	{
		const char* Name;      // seeds the cascade's random amplitudes (HashString), so it is part of the world
		double Tile;           // m
		double RotationDeg;    // the grid's axes against the map's
		double MinWavelength;  // m, inclusive
		double MaxWavelength;  // m, exclusive (the last running cascade takes everything longer, to its tile / 2)
	};

	constexpr int kLongCascades = 3;
	/** L1 "sea", L2 "long", L3 "swell" (runs only when the spectrum reaches past L2's tile / 2: the open sea, never a lake). */
	inline constexpr FLongWaveCascadeSpec kLongCascadeSpecs[kLongCascades] = {
		{ "L1", 97.3, 0.0, 0.0, 12.0 },
		{ "L2", 331.0, 27.4, 12.0, 44.0 },
		{ "L3", 1409.0, 61.9, 44.0, 1e9 },
	};

	/** The 13 real fields of a cascade (map frame: X north, Y east; slopes and velocities along the map's axes). */
	enum class ELongField : int
	{
		H,    // height (m)
		Vz,   // dH/dt (m/s)
		Sx, Sy, // dH/dx, dH/dy
		U, V,   // the surface water's horizontal orbital velocity (m/s)
		Ax, Ay, // its acceleration (m/s^2): the exact -omega^2 terms
		Dx, Dy, // choppy displacement (m, Choppiness x Tessendorf's -i k/|k| h)
		Jxx, Jyy, Jxy, // the fold Jacobian of the displacement less the identity: dDx/dx, dDy/dy, dDx/dy
		Count
	};
	constexpr int kLongFields = static_cast<int>(ELongField::Count);

	struct FLongWaveParams
	{
		double WindMs = 0.0;          // 10 m wind
		double WindFromRad = 0.0;     // where it comes from (map frame, 0 = north)
		double FetchMeters = 15000.0; // the reference fetch the targets grow on (the sea map's)
		/** The spectrum's range: FWaveField's bands 0-7 (0.18 Hz to the renderer's SplitHz, 48 m to 3.6 m deep). */
		double MinHz = 0.18;
		double MaxHz = 0.0;           // 0 = the top of band 7
		double Choppiness = 1.5;      // M_WaterV4's Gerstner factor
	};

	/**
	 * docs/long-wave-fft/: the long waves (FWaveField's components 0-23: 3.6 m to 48 m) as an FFT sea, computed once per
	 * world on the CPU and shared by the physics and (phase 2) the renderer. Tessendorf's Hermitian modes on 128^2 grids,
	 * one cascade per wavelength range (kLongCascadeSpecs), spectrum and growth exactly as the sines': JONSWAP at the
	 * growth laws' Hs and Tp, scaled so each of bands 0-7 carries the variance it has in FWaveField, Donelan-Hamilton-Hui /
	 * Banner sech^2 spreading (nothing upwind), each mode approaching its target over its band's GrowthSeconds.
	 *
	 * Time runs in keys of 1/30 s of world clock. A key's grids are a pure function of the world seed, the cascade's name
	 * and the amplitudes at that key; amplitudes step once per key and their targets are recomputed every 15th key. A
	 * wind shift needs no re-anchoring: the old direction's modes decay while the new one's grow. Mode phases are reduced
	 * mod 2 pi in double before they become floats, so a clock days long keeps millimetre heights.
	 *
	 * Phase 1: nothing in the game calls this yet.
	 */
	class SAILINGPHYSICS_API FLongWaves
	{
	public:
		static constexpr int N = 128;
		static constexpr double KeyHz = 30.0;
		static constexpr int TargetEveryKeys = 15;
		static constexpr int RingKeys = 4;

		/** Runs Count independent jobs (any order, any threads) and returns when all are done. Null = inline. */
		using FParallelFor = std::function<void(int Count, const std::function<void(int)>& Job)>;

		/** One key's grids: per cascade, kLongFields float grids of N x N (row = the cascade's local X index). */
		struct FKeyGrids
		{
			int64_t Key = 0;
			bool bRunning[kLongCascades] = {};
			std::vector<float> F[kLongCascades][kLongFields];
		};

		explicit FLongWaves(uint64_t WorldSeed = 1);

		/** The water's depth for the dispersion (omega^2 = g k tanh(k h)); 0 = deep. Lays the modes again: call before use. */
		void SetDepth(double DepthMeters);
		double GetDepth() const { return Depth; }
		/** The sea's wind and reference fetch. The targets follow at the next target key (or now, before the first). */
		void SetParams(const FLongWaveParams& InParams);
		const FLongWaveParams& GetParams() const { return Params; }

		/** Steps the amplitudes key by key up to Key (targets every TargetEveryKeys-th key). Never goes back. */
		void Advance(int64_t Key);
		int64_t GetKey() const { return StateKey; }
		/** Jumps straight to the targets of the current params. */
		void SnapToTarget();

		/** The grids at Key from the amplitudes as they are now (a pure function of them). Parallel jobs join deterministically. */
		void EvaluateInto(int64_t Key, FKeyGrids& Out, const FParallelFor& Parallel = nullptr) const;
		/** Advance(Key), then its grids into the ring (the producer: a key or two ahead of the clock). */
		void Produce(int64_t Key, const FParallelFor& Parallel = nullptr);
		/**
		 * The 13 fields at a map point and world time: each cascade bilinear at its rotated point, blended linearly between
		 * keys floor(T x 30) and the next, times Ratio[c] (the sea map's cascade channel; null = 1). A key not in the ring is
		 * evaluated here under the lock from the amplitudes as they are (a sync miss: counted, and a hitch in the game; the
		 * producer keeps two keys ahead so there are none). Out[kLongFields].
		 */
		void Sample(double X, double Y, double T, const float* Ratio, double* Out) const;
		uint64_t GetSyncMisses() const { return SyncMisses.load(std::memory_order_relaxed); }

		/** Does the cascade run (has modes, and variance over 1e-6 m^2 now)? */
		bool IsRunning(int Cascade) const;
		bool HasModes(int Cascade) const { return !Cascades[Cascade].Modes.empty(); }
		int ModeCount(int Cascade) const { return int(Cascades[Cascade].Modes.size()); }
		double Cell(int Cascade) const { return kLongCascadeSpecs[Cascade].Tile / N; }

		/** Expected (configured) variance, m^2: of a cascade now, of everything now, and of the targets. */
		double CascadeVariance(int Cascade) const;
		double Variance() const;
		double TargetVariance() const;
		/** The variance of the modes the wind no longer feeds (target 0: upwind of a new wind), m^2. */
		double FadingVariance() const;
		/** The shortest and longest wavelengths among a cascade's modes (m). */
		void WavelengthRange(int Cascade, double& OutMin, double& OutMax) const;
		/** The modes' variance now in Bins equal direction bins about the wind's travel direction: bin B is centred on
		 *  -pi + B x 2 pi / Bins (Bins even: bin Bins / 2 on the wind). */
		void DirectionHistogram(int Bins, double* Out) const;
		/** Each of FWaveField's bands 0..kWaveBands-1: the modes' variance now (m^2; bands past the range are 0), of one
		 *  cascade or (-1) of all. */
		void BandVariance(double* Out, int Cascade = -1) const;
		/** Energy-weighted Tm01 (s) and mean travel direction (rad) of the modes now. */
		double MeanPeriod() const;
		double MeanDirection() const;
		/** A cascade's velocity-weighted mean wavenumber (rad/m): its orbital flow decays with depth at this k. */
		double MeanWavenumber(int Cascade) const;
		/** A cascade's spectrum in 16 wavelength bins (FOcean::Bands' form), for added resistance. */
		void CascadeBands(int Cascade, std::vector<FWaveBand>& Out) const;

		/**
		 * The sea map's channel for each cascade at a cell (docs/long-wave-fft/ SeaMapSwan): the energy-weighted RMS of
		 * each mode's amplitude ratio at its own direction's fetch pulled kSeaTowardWind toward the wind (as FSeaMap does for
		 * the sines), times the TMA depth factor. Out[kLongCascades]. Also each band's share, OutBand[kLongCascades][kWaveBands]
		 * (variance at the cell / the reference's), when not null.
		 */
		void SeaChannelsAt(const FSeaFetch& Fetch, int Row, int Col, float* Out, double (*OutBand)[kWaveBands] = nullptr) const;

		/** Every field as the straight sum over a cascade's modes, in double (tests). Out[kLongFields]. */
		void DirectSum(int Cascade, double X, double Y, double T, double* Out) const;
		/** A cascade's grid node (I, J) in the map frame. */
		void NodePosition(int Cascade, int I, int J, double& OutX, double& OutY) const;

		/** The top of band 7 (Hz): the renderer's split between the long waves and the chop (AWaterSurface::SplitHz). */
		static double SplitHz();

	private:
		struct FMode
		{
			int Index = 0;       // into the N x N grid
			int Mirror = 0;      // the mode at -k
			int Band = -1;       // FWaveField band, -1 below band 0
			double Kx = 0.0, Ky = 0.0, K = 0.0; // map frame (rad/m)
			double Omega = 0.0;
			double Freq = 0.0;   // Hz
			double Coth = 1.0;   // coth(k h): the surface orbital speed's depth factor (1 deep)
			double XiRe = 0.0, XiIm = 0.0; // the complex Gaussian (unit mean square)
			double Amp = 0.0, Target = 0.0; // sqrt of the mode's variance now and its target
			double Decay = 1.0;  // the amplitude's step toward the target per key: 1 - exp(-1/30 / tau)
		};
		struct FCascade
		{
			double Cos = 1.0, Sin = 0.0;
			double MinK = 0.0, MaxK = 0.0;
			std::vector<FMode> Modes;
		};
		struct FSlot
		{
			std::atomic<int64_t> Key { INT64_MIN };
			FKeyGrids Grids;
		};

		void LayModes();
		void ComputeTargets();
		/** Mode energy density shape at this mode (before the per-band scaling). */
		double ModeShape(const FMode& M, double Fp, double TravelDir) const;
		const FKeyGrids* FindKey(int64_t Key) const;
		const FKeyGrids& GetKeyGrids(int64_t Key) const;
		void ProduceLocked(int64_t Key, const FParallelFor& Parallel) const;

		uint64_t WorldSeed = 1;
		double Depth = 0.0;
		FLongWaveParams Params;
		bool bParamsDirty = true;
		bool bAdvanced = false;
		int64_t StateKey = 0;
		FCascade Cascades[kLongCascades];
		std::unique_ptr<FFft2D> Fft;

		// The ring of keys: a hit is lock-free (a slot's key is stored with release after its grids); a miss produces under
		// the lock. Mutable: readers on the physics threads may produce.
		mutable std::unique_ptr<FSlot[]> Ring;
		mutable std::mutex ProduceLock;
		mutable std::atomic<uint64_t> SyncMisses { 0 };
	};
}
