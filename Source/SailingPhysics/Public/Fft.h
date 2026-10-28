#pragma once

#include "SailingPhysicsApi.h"
#include <vector>

namespace Sailing
{
	/** A complex value as two floats: the kernel does its own arithmetic (std::complex<float>'s operator* checks for NaNs
	 *  through a library call unless fast maths is on, which this code never uses). Layout-compatible with std::complex<float>. */
	struct FComplexF
	{
		float Re = 0.f, Im = 0.f;
	};

	/**
	 * docs/long-wave-fft/: one float FFT for the sea's grids. Radix-2, iterative, twiddles made in double and stored as
	 * float, a bit-reverse table; a 2D transform is rows, a transpose, rows, a transpose (each pass walks memory in order).
	 * The result depends only on the input (one fixed order of operations, no threads inside): grids made on any worker
	 * agree to the bit. Compiled without fused multiply-adds (`fp contract(off)`), so arm64 does the same arithmetic as
	 * x64 MSVC.
	 */
	class SAILINGPHYSICS_API FFft2D
	{
	public:
		/** Size must be a power of two (2 to 4096). */
		explicit FFft2D(int Size);
		int GetSize() const { return N; }

		/** In place, unnormalized inverse: x[r][c] = sum over (m, n) of X[m][n] e^{+2 pi i (m r + n c) / N}. Row-major N x N. */
		void Inverse(FComplexF* Data) const;
		/** In place, unnormalized forward (e^{-2 pi i ...}): the inverse of the conjugate, conjugated. */
		void Forward(FComplexF* Data) const;
		/** One row of N values in place (inverse sense). */
		void Inverse1D(FComplexF* Row) const;

	private:
		void Transpose(FComplexF* Data) const;

		int N = 0;
		int LogN = 0;
		std::vector<FComplexF> Twiddle; // e^{+2 pi i k / N}, k < N / 2
		std::vector<int> BitReverse;
	};
}
