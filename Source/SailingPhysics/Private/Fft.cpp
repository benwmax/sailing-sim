#include "Fft.h"
#include "SailingMath.h"
#include <cmath>
#include <utility>

// No fused multiply-adds: the same sums on arm64 (clang contracts a * b + c by default) as on x64 MSVC (/fp:precise).
#if defined(__clang__)
#pragma clang fp contract(off)
#endif

namespace Sailing
{
	FFft2D::FFft2D(int Size)
		: N(Size)
	{
		while ((1 << LogN) < N) ++LogN;
		Twiddle.resize(size_t(N / 2 > 0 ? N / 2 : 1));
		for (int K = 0; K < N / 2; ++K)
		{
			const double A = 2.0 * kPi * K / N;
			Twiddle[size_t(K)] = { float(std::cos(A)), float(std::sin(A)) };
		}
		BitReverse.resize(size_t(N));
		for (int I = 0; I < N; ++I)
		{
			int R = 0;
			for (int B = 0; B < LogN; ++B) R |= ((I >> B) & 1) << (LogN - 1 - B);
			BitReverse[size_t(I)] = R;
		}
	}

	void FFft2D::Inverse1D(FComplexF* A) const
	{
		for (int I = 0; I < N; ++I)
		{
			const int J = BitReverse[size_t(I)];
			if (I < J) std::swap(A[I], A[J]);
		}
		for (int Len = 2, Step = N / 2; Len <= N; Len <<= 1, Step >>= 1)
		{
			const int Half = Len / 2;
			for (int I = 0; I < N; I += Len)
			{
				FComplexF* Lo = A + I;
				FComplexF* Hi = A + I + Half;
				for (int J = 0; J < Half; ++J)
				{
					const FComplexF W = Twiddle[size_t(J * Step)];
					const float VRe = Hi[J].Re * W.Re - Hi[J].Im * W.Im;
					const float VIm = Hi[J].Re * W.Im + Hi[J].Im * W.Re;
					const float URe = Lo[J].Re, UIm = Lo[J].Im;
					Lo[J] = { URe + VRe, UIm + VIm };
					Hi[J] = { URe - VRe, UIm - VIm };
				}
			}
		}
	}

	void FFft2D::Transpose(FComplexF* A) const
	{
		for (int R = 0; R < N; ++R)
			for (int C = R + 1; C < N; ++C) std::swap(A[size_t(R) * N + C], A[size_t(C) * N + R]);
	}

	void FFft2D::Inverse(FComplexF* A) const
	{
		for (int R = 0; R < N; ++R) Inverse1D(A + size_t(R) * N);
		Transpose(A);
		for (int R = 0; R < N; ++R) Inverse1D(A + size_t(R) * N);
		Transpose(A);
	}

	void FFft2D::Forward(FComplexF* A) const
	{
		const size_t Count = size_t(N) * N;
		for (size_t I = 0; I < Count; ++I) A[I].Im = -A[I].Im;
		Inverse(A);
		for (size_t I = 0; I < Count; ++I) A[I].Im = -A[I].Im;
	}
}
