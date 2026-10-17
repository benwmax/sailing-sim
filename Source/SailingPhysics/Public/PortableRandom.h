#pragma once

#include <cmath>
#include <cstdint>

namespace Sailing
{
	// Online readiness (rule 5): seeded things draw from this, never from std:: distributions. std::mt19937 is the same
	// everywhere, but std::normal_distribution and the uniform distributions are implementation-defined (libc++ on the Mac,
	// MSVC's STL on Windows give different numbers from the same engine), so the same seed drew a different sea, ocean and
	// traffic on each machine. The engine is PCG32 (O'Neill 2014) seeded through SplitMix64; the uniform draws use only
	// integer arithmetic and exact conversions, so they agree bit for bit on every platform. Gaussian() goes through
	// std::log and std::sqrt (correctly rounded sqrt; log within an ulp on every libm we build with), the one place a
	// platform can differ, in the last bit. SailingSim.Physics.PortableRandom holds the sequence.

	/** SplitMix64's finaliser: a full-avalanche 64-bit hash. */
	inline uint64_t Hash64(uint64_t X)
	{
		X += 0x9E3779B97F4A7C15ull;
		X = (X ^ (X >> 30)) * 0xBF58476D1CE4E5B9ull;
		X = (X ^ (X >> 27)) * 0x94D049BB133111EBull;
		return X ^ (X >> 31);
	}

	/** Two hashes into one (order matters): seeds from stable ids, e.g. HashCombine(WorldSeed, VesselId). */
	inline uint64_t HashCombine(uint64_t A, uint64_t B)
	{
		return Hash64(A ^ (Hash64(B) + 0x9E3779B97F4A7C15ull + (A << 6) + (A >> 2)));
	}

	/** FNV-1a over a string id (names, slip ids), then hashed: never the address or std::hash (both differ per run). */
	inline uint64_t HashString(const char* S)
	{
		uint64_t H = 0xCBF29CE484222325ull;
		for (; S && *S; ++S) H = (H ^ uint64_t(uint8_t(*S))) * 0x100000001B3ull;
		return Hash64(H);
	}

	class FPortableRandom
	{
	public:
		explicit FPortableRandom(uint64_t Seed = 0) { Reseed(Seed); }

		void Reseed(uint64_t Seed)
		{
			State = 0;
			Inc = (Hash64(Seed ^ 0xDA3E39CB94B95BDBull) << 1) | 1u;
			Next();
			State += Hash64(Seed);
			Next();
			bHaveSpare = false;
		}

		/** 32 uniform bits. */
		uint32_t Next()
		{
			const uint64_t Old = State;
			State = Old * 6364136223846793005ull + Inc;
			const uint32_t Xorshifted = uint32_t(((Old >> 18) ^ Old) >> 27);
			const uint32_t Rot = uint32_t(Old >> 59);
			return (Xorshifted >> Rot) | (Xorshifted << ((32u - Rot) & 31u));
		}

		/** Uniform in [0, 1) with 53 random bits. */
		double Uniform01()
		{
			const uint64_t A = Next(), B = Next();
			return double((A << 21) ^ (B >> 11)) * (1.0 / 9007199254740992.0);
		}

		/** Uniform in [Lo, Hi). */
		double Uniform(double Lo, double Hi) { return Lo + (Hi - Lo) * Uniform01(); }

		/** Uniform integer in [Lo, Hi], inclusive (unbiased: rejection below the largest multiple of the range). */
		int32_t UniformInt(int32_t Lo, int32_t Hi)
		{
			if (Hi <= Lo) return Lo;
			const uint32_t Range = uint32_t(int64_t(Hi) - int64_t(Lo) + 1);
			const uint32_t Threshold = (0u - Range) % Range;
			for (;;)
			{
				const uint32_t R = Next();
				if (R >= Threshold) return int32_t(int64_t(Lo) + int64_t(R % Range));
			}
		}

		/** Standard normal (Marsaglia's polar method: no trigonometry), the second of each pair kept for the next call. */
		double Gaussian()
		{
			if (bHaveSpare)
			{
				bHaveSpare = false;
				return Spare;
			}
			for (;;)
			{
				const double U = 2.0 * Uniform01() - 1.0, V = 2.0 * Uniform01() - 1.0;
				const double S = U * U + V * V;
				if (S > 0.0 && S < 1.0)
				{
					const double M = std::sqrt(-2.0 * std::log(S) / S);
					Spare = V * M;
					bHaveSpare = true;
					return U * M;
				}
			}
		}

	private:
		uint64_t State = 0;
		uint64_t Inc = 1;
		double Spare = 0.0;
		bool bHaveSpare = false;
	};
}
