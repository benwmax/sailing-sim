#include "WakeGrid.h"
#include "Async/ParallelFor.h"

namespace
{
	constexpr float kAlpha = 0.25f;    // damping (1/s)
	constexpr float kStep = 1.f / 30.f;
	constexpr float kPressure = 0.7f;  // the hull as a pressure on the surface: share of its draft at each cell (rho g d)
	constexpr int32 kSponge = 8;       // cells of absorbing border

	/** In-place radix-2 complex FFT of one line (Sign +1 inverse sense, -1 forward; unnormalized). */
	void Fft(std::complex<float>* A, int32 Count, int32 Stride, float Sign)
	{
		for (int32 I = 1, J = 0; I < Count; ++I)
		{
			int32 Bit = Count >> 1;
			for (; J & Bit; Bit >>= 1) J ^= Bit;
			J ^= Bit;
			if (I < J) Swap(A[I * Stride], A[J * Stride]);
		}
		for (int32 Len = 2; Len <= Count; Len <<= 1)
		{
			const double Ang = Sign * 2.0 * UE_DOUBLE_PI / Len;
			const std::complex<float> W(float(FMath::Cos(Ang)), float(FMath::Sin(Ang)));
			for (int32 I = 0; I < Count; I += Len)
			{
				std::complex<float> Wk(1.f, 0.f);
				for (int32 K = 0; K < Len / 2; ++K)
				{
					const std::complex<float> U = A[(I + K) * Stride], V = A[(I + K + Len / 2) * Stride] * Wk;
					A[(I + K) * Stride] = U + V;
					A[(I + K + Len / 2) * Stride] = U - V;
					Wk *= W;
				}
			}
		}
	}

	void Fft2(TArray<std::complex<float>>& A, int32 N, float Sign)
	{
		ParallelFor(N, [&](int32 R) { Fft(A.GetData() + R * N, N, 1, Sign); });
		ParallelFor(N, [&](int32 C) { Fft(A.GetData() + C, N, N, Sign); });
	}
}

void FWakeGrid::Init(int32 InN, float InCell)
{
	check(FMath::IsPowerOfTwo(InN));
	N = InN;
	Cell = InCell;
	const int32 NN = N * N;
	for (TArray<float>* A : { &H, &Velocity, &Pressure, &Depth, &PrevDepth, &FoamField }) A->Init(0.f, NN);
	Spectrum.SetNumZeroed(NN);
	Omega.SetNumUninitialized(NN);
	const float Dk = 2.f * UE_PI / (N * Cell);
	for (int32 R = 0; R < N; ++R)
	{
		for (int32 C = 0; C < N; ++C)
		{
			const int32 Mr = R < N / 2 ? R : R - N, Mc = C < N / 2 ? C : C - N;
			Omega[R * N + C] = FMath::Sqrt(9.81f * Dk * FMath::Sqrt(float(Mr * Mr + Mc * Mc)));
		}
	}
	bHasDepth = false;
	bPlaced = false;
}

void FWakeGrid::Follow(const FVector2D& Point)
{
	if (!IsValid()) return;
	const float Size = N * Cell;
	if (!bPlaced)
	{
		Corner = FVector2D(FMath::GridSnap(Point.X - 0.5f * Size, Cell), FMath::GridSnap(Point.Y - 0.5f * Size, Cell));
		bPlaced = true;
		return;
	}
	const FVector2D Centre = Corner + FVector2D(0.5f * Size, 0.5f * Size);
	const FVector2D Off = Point - Centre;
	if (FMath::Abs(Off.X) < 0.25f * Size && FMath::Abs(Off.Y) < 0.25f * Size) return;
	// Shift by whole cells: what is still inside the grid keeps its waves.
	const int32 DR = FMath::RoundToInt(Off.X / Cell), DC = FMath::RoundToInt(Off.Y / Cell);
	auto Shift = [&](TArray<float>& A)
	{
		TArray<float> B;
		B.Init(0.f, N * N);
		for (int32 R = 0; R < N; ++R)
		{
			const int32 SR = R + DR;
			if (SR < 0 || SR >= N) continue;
			for (int32 C = 0; C < N; ++C)
			{
				const int32 SC = C + DC;
				if (SC >= 0 && SC < N) B[R * N + C] = A[SR * N + SC];
			}
		}
		A = MoveTemp(B);
	};
	for (TArray<float>* A : { &H, &Velocity, &Depth, &PrevDepth, &FoamField }) Shift(*A);
	Corner += FVector2D(DR * Cell, DC * Cell);
}

float FWakeGrid::DisplacedDepth(const FHull& Hull, const FVector2D& P) const
{
	// The point in the hull's body frame, and how deep the hull bottom is there (heeled and heaved).
	const FVector2D D = P - Hull.Position;
	const float Cs = FMath::Cos(Hull.Heading), Sn = FMath::Sin(Hull.Heading);
	const float X = D.X * Cs + D.Y * Sn, Y = -D.X * Sn + D.Y * Cs;
	const Sailing::FHullShape& S = *Hull.Shape;
	if (X < S.SternX || X > S.BowX) return 0.f;
	const float HalfBeam = float(S.DeckHalfBeam(X));
	const float Yc = Y - float(S.CenterY);
	if (FMath::Abs(Yc) > HalfBeam) return 0.f;
	const float Bottom = float(S.BottomZ(X, Yc, Hull.CanoeDepth));
	return FMath::Max(0.f, -Bottom - Yc * FMath::Sin(Hull.Heel) + Hull.Sink);
}

void FWakeGrid::Step(float DeltaSeconds, const TArray<FHull>& Hulls)
{
	if (!IsValid()) return;
	Accumulator = FMath::Min(Accumulator + DeltaSeconds, 4.f * kStep);
	while (Accumulator >= kStep)
	{
		Accumulator -= kStep;
		StepOnce(kStep, Hulls);
	}
}

void FWakeGrid::StepOnce(float Dt, const TArray<FHull>& Hulls)
{
	// Each hull's draft at every cell (its pressure on the surface).
	Swap(Depth, PrevDepth);
	ParallelFor(N, [&](int32 R)
	{
		for (int32 C = 0; C < N; ++C)
		{
			const FVector2D P = Corner + FVector2D((R + 0.5f) * Cell, (C + 0.5f) * Cell);
			float D = 0.f;
			for (const FHull& Hull : Hulls)
			{
				if (Hull.Shape && FVector2D::DistSquared(P, Hull.Position) < FMath::Square(float(Hull.Shape->BowX - Hull.Shape->SternX) + 2.f))
				{
					D = FMath::Max(D, DisplacedDepth(Hull, P));
				}
			}
			Depth[R * N + C] = D;
		}
	});
	if (!bHasDepth) { PrevDepth = Depth; bHasDepth = true; }
	// Pressure head, softened over a cell so the hull's sharp outline doesn't ring at the grid scale.
	ParallelFor(N, [&](int32 R)
	{
		for (int32 C = 0; C < N; ++C)
		{
			float Sum = 0.f, Weight = 0.f;
			for (int32 Y = -1; Y <= 1; ++Y)
			{
				for (int32 X = -1; X <= 1; ++X)
				{
					const int32 RR = R + Y, CC = C + X;
					if (RR < 0 || RR >= N || CC < 0 || CC >= N) continue;
					const float K = (X == 0 ? 2.f : 1.f) * (Y == 0 ? 2.f : 1.f);
					Sum += K * Depth[RR * N + CC];
					Weight += K;
				}
			}
			Pressure[R * N + C] = kPressure * Sum / Weight;
		}
	});

	// Mode by mode, q = h + p obeys q'' + alpha q' + omega^2 q = 0 over the step (p held): solved exactly. One forward
	// transform carries q and the vertical velocity (packed as real and imaginary parts), one inverse brings both back.
	const int32 NN = N * N;
	for (int32 I = 0; I < NN; ++I) Spectrum[I] = std::complex<float>(H[I] + Pressure[I], Velocity[I]);
	Fft2(Spectrum, N, -1.f);
	const float Decay = FMath::Exp(-0.5f * kAlpha * Dt);
	const float Norm = 1.f / float(NN);
	TArray<std::complex<float>> Out;
	Out.SetNumUninitialized(NN);
	ParallelFor(N, [&](int32 R)
	{
		const int32 Rm = (N - R) % N;
		for (int32 C = 0; C < N; ++C)
		{
			const int32 I = R * N + C, Im = Rm * N + (N - C) % N;
			const std::complex<float> Z = Spectrum[I], Zm = std::conj(Spectrum[Im]);
			const std::complex<float> Q = 0.5f * (Z + Zm);                              // q's spectrum
			const std::complex<float> V = std::complex<float>(0.f, -0.5f) * (Z - Zm);   // the velocity's
			const float W = Omega[I];
			std::complex<float> Q1, V1;
			if (W < 1e-4f)
			{
				Q1 = Q;
				V1 = 0.f;
			}
			else
			{
				const float Wd = FMath::Sqrt(FMath::Max(W * W - 0.25f * kAlpha * kAlpha, 1e-6f));
				const float Cs = FMath::Cos(Wd * Dt), Sn = FMath::Sin(Wd * Dt);
				Q1 = Decay * (Q * Cs + (V + 0.5f * kAlpha * Q) * (Sn / Wd));
				V1 = Decay * (V * Cs - (W * W * Q + 0.5f * kAlpha * V) * (Sn / Wd));
			}
			Out[I] = (Q1 + std::complex<float>(0.f, 1.f) * V1) * Norm;
		}
	});
	Fft2(Out, N, 1.f);

	ParallelFor(N, [&](int32 R)
	{
		for (int32 C = 0; C < N; ++C)
		{
			const int32 I = R * N + C;
			const float Old = H[I];
			float Next = Out[I].real() - Pressure[I];
			float Vel = Out[I].imag();
			// The sponge: waves leave the grid instead of wrapping round.
			const int32 Edge = FMath::Min(FMath::Min(R, N - 1 - R), FMath::Min(C, N - 1 - C));
			if (Edge < kSponge)
			{
				const float K = FMath::Lerp(0.82f, 1.f, float(Edge) / kSponge);
				Next *= K;
				Vel *= K;
			}
			// Foam: where the surface moves fast (a breaking bow wave) and in the turbulence the transom leaves behind; a
			// small boat's is a narrow band of bubbles gone within a couple of lengths (Phase 8 drone references).
			const float Rate = FMath::Abs(Next - Old) / Dt;
			const float Churn = FMath::Max(0.f, Rate - 0.35f) * 1.2f + (PrevDepth[I] > 0.04f && Depth[I] < 0.005f ? 4.f * PrevDepth[I] : 0.f);
			FoamField[I] = FMath::Clamp(FoamField[I] * FMath::Exp(-Dt / 2.5f) + Churn * Dt * 2.f, 0.f, 1.f);
			H[I] = FMath::Clamp(Next, -0.6f, 0.6f);
			Velocity[I] = Vel;
		}
	});
}

float FWakeGrid::HeightAt(const FVector2D& Point) const
{
	if (!IsValid()) return 0.f;
	const FVector2D L = (Point - Corner) / Cell;
	const int32 R = FMath::FloorToInt(L.X), C = FMath::FloorToInt(L.Y);
	if (R < 0 || C < 0 || R >= N - 1 || C >= N - 1) return 0.f;
	const float Tx = L.X - R, Ty = L.Y - C;
	return FMath::Lerp(FMath::Lerp(H[R * N + C], H[R * N + C + 1], Ty), FMath::Lerp(H[(R + 1) * N + C], H[(R + 1) * N + C + 1], Ty), Tx);
}
