#include "WakeGrid.h"
#include "Async/ParallelFor.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"

namespace
{
	constexpr float kAlpha = 0.25f;    // damping (1/s)
	constexpr float kStep = 1.f / 30.f;
	constexpr float kPressure = 0.7f;  // the hull as a pressure on the surface: share of its draft at each cell (rho g d)
	// The deepest draft the pressure counts (m): Bluebonnet's 2.28 m canoe is the deepest hull the solver was tuned on.
	// The frigate's 5.9 m pressed a 4 m head on the grid: the surface beside her sat past the height clamp and foamed
	// every step, a flat white sheet wider than her beam (docs/frigate-import/).
	constexpr float kMaxDepth = 2.3f;
	constexpr int32 kSponge = 8;       // cells of absorbing border
	// Bow wave 3 (docs/bow-wave/): how far the water moves toward a crest, as a share of the linear wave's own orbit (1: a
	// Gerstner wave's; Tessendorf's lambda). Her waves are a few centimetres high, so it moves a few centimetres and the
	// Jacobian stays above 0.6 in flat water (0.84 at the J/22's bow at 6 kn, 0.68 in her wake): no folds of her own.
	constexpr float kChop = 1.f;

	/** docs/frame-pacing/ (PC Insights, Nov 26 2026): the wake's solve runs on a worker and fans every pass out over all the
	 *  workers. At normal priority a burst filled them just as the render thread's visibility tasks were queued, and those
	 *  frames waited 3-5 ms longer (InitViews -> WaitForVisibilityTasks): the uneven frame pacing Bean saw as a stutter.
	 *  The wake is polled (AWaterSurface takes a step only when it is ready), so it runs at background priority: frame work
	 *  goes first. Named, so a trace shows it. */
	template <typename FBody>
	void WakeParallel(int32 Num, FBody&& Body)
	{
		ParallelFor(Num, [&Body](int32 I) { TRACE_CPUPROFILER_EVENT_SCOPE(Sailing_WakeGridRows); Body(I); }, EParallelForFlags::BackgroundPriority);
	}

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
		WakeParallel(N, [&](int32 R) { Fft(A.GetData() + R * N, N, 1, Sign); });
		// The columns in blocks of 16, copied out to contiguous lines, transformed and copied back. Walked in place at a
		// stride of N, every butterfly of every pass missed the cache (on Ultra's 512 grid the stride is 4 KB, so a column
		// sits in one cache set): the PC's stutter trace (Nov 26) put the column pass at 27-32 ms of worker time a frame
		// against 2 ms for the rows. The same arithmetic in the same order, so the result is bit-identical.
		constexpr int32 kBlock = 16;
		WakeParallel(FMath::DivideAndRoundUp(N, kBlock), [&](int32 B)
		{
			const int32 C0 = B * kBlock, Width = FMath::Min(kBlock, N - C0);
			TArray<std::complex<float>> Lines;
			Lines.SetNumUninitialized(Width * N);
			for (int32 R = 0; R < N; ++R)
			{
				const std::complex<float>* Src = A.GetData() + R * N + C0;
				for (int32 K = 0; K < Width; ++K) Lines[K * N + R] = Src[K];
			}
			for (int32 K = 0; K < Width; ++K) Fft(Lines.GetData() + K * N, N, 1, Sign);
			for (int32 R = 0; R < N; ++R)
			{
				std::complex<float>* Dst = A.GetData() + R * N + C0;
				for (int32 K = 0; K < Width; ++K) Dst[K] = Lines[K * N + R];
			}
		});
	}
}

void FWakeGrid::Init(int32 InN, float InCell)
{
	check(FMath::IsPowerOfTwo(InN));
	N = InN;
	Cell = InCell;
	const int32 NN = N * N;
	for (TArray<float>* A : { &H, &Velocity, &Pressure, &Depth, &PrevDepth, &FoamField, &SlickField, &SlickScratch, &Stir, &PrevStir, &NearStir, &NearFroude, &StirMid, &PrevStirMid }) A->Init(0.f, NN);
	FoldField.Init(1.f, NN);
	Spectrum.SetNumZeroed(NN);
	Displacement.SetNumZeroed(NN);
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
	for (TArray<float>* A : { &H, &Velocity, &Depth, &PrevDepth, &FoamField, &SlickField, &Stir, &StirMid }) Shift(*A);
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
	return FMath::Clamp(-Bottom - Yc * FMath::Sin(Hull.Heel) + Hull.Sink, 0.f, kMaxDepth);
}

float FWakeGrid::SideRatio(const FHull& Hull, const FVector2D& P) const
{
	// How far out from her centreline a point is, as a share of her half beam there (0 middle, 1 at the deck edge).
	const FVector2D D = P - Hull.Position;
	const float Cs = FMath::Cos(Hull.Heading), Sn = FMath::Sin(Hull.Heading);
	const float X = D.X * Cs + D.Y * Sn, Y = -D.X * Sn + D.Y * Cs;
	const Sailing::FHullShape& S = *Hull.Shape;
	const float HalfBeam = FMath::Max(float(S.DeckHalfBeam(X)), 1e-3f);
	return FMath::Min(FMath::Abs(Y - float(S.CenterY)) / HalfBeam, 1.f);
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
	Swap(Stir, PrevStir);
	Swap(StirMid, PrevStirMid);
	WakeParallel(N, [&](int32 R)
	{
		for (int32 C = 0; C < N; ++C)
		{
			const FVector2D P = Corner + FVector2D((R + 0.5f) * Cell, (C + 0.5f) * Cell);
			float D = 0.f, St = 0.f, Nr = 0.f, Mid = 0.f, Fr = 0.f;
			for (const FHull& Hull : Hulls)
			{
				if (Hull.Shape && FVector2D::DistSquared(P, Hull.Position) < FMath::Square(float(Hull.Shape->BowX - Hull.Shape->SternX) + 2.f))
				{
					const float HullD = DisplacedDepth(Hull, P);
					Nr = FMath::Max(Nr, FMath::Min(FMath::Abs(Hull.Speed) / 2.5f, 1.f));
					// Bow wave 2 (docs/bow-wave/): her speed for her length (the waterline's, or 85% of her overall length).
					const float Lwl = Hull.Shape->WaterlineHalfLength > 0.0 ? 2.f * float(Hull.Shape->WaterlineHalfLength) : 0.85f * float(Hull.Shape->BowX - Hull.Shape->SternX);
					Fr = FMath::Max(Fr, FMath::Abs(Hull.Speed) / FMath::Sqrt(9.81f * FMath::Max(Lwl, 0.5f)));
					D = FMath::Max(D, HullD);
					// sailing-feedback #9: the lane she leaves goes with her speed (full from 2.5 m/s, about 5 kn), so a
					// boat drifting or tied up leaves none.
					if (HullD > 0.02f)
					{
						const float HullSt = FMath::Min(FMath::Abs(Hull.Speed) / 2.5f, 1.f);
						St = FMath::Max(St, HullSt);
						// Her middle (full to 20% of her half beam, none past 65%, inside her wetted width): where the bubble trail starts.
						Mid = FMath::Max(Mid, HullSt * (1.f - FMath::SmoothStep(0.2f, 0.65f, SideRatio(Hull, P))));
					}
				}
			}
			Depth[R * N + C] = D;
			Stir[R * N + C] = St;
			NearStir[R * N + C] = Nr;
			NearFroude[R * N + C] = Fr;
			StirMid[R * N + C] = Mid;
		}
	});
	if (!bHasDepth) { PrevDepth = Depth; bHasDepth = true; }
	// Pressure head, softened over a cell so the hull's sharp outline doesn't ring at the grid scale.
	WakeParallel(N, [&](int32 R)
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
	WakeParallel(N, [&](int32 R)
	{
		const int32 Rm = (N - R) % N;
		const int32 Kr = R < N / 2 ? R : R - N;    // the mode's wavenumber along X, in grid units
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
			// Bow wave 3: the horizontal displacement, i k/|k| q per mode (with this transform's signs, for h = A cos kx it is
			// -A sin kx: toward the crest), X and Y packed as one field's real and imaginary parts, (i kx - ky) / |k| q. None
			// for the mean or the Nyquist rows and columns (no direction to give them).
			if (!bFold) continue;
			const int32 Kc = C < N / 2 ? C : C - N;
			if (W < 1e-4f || R == N / 2 || C == N / 2) Displacement[I] = 0.f;
			else
			{
				const float Kn = FMath::Sqrt(float(Kr * Kr + Kc * Kc));
				Displacement[I] = Q1 * std::complex<float>(-float(Kc) / Kn, float(Kr) / Kn) * Norm;
			}
		}
	});
	Fft2(Out, N, 1.f);
	// Bow wave 3: its Jacobian, by central differences (one-sided at the edges). Off: flat (1).
	if (!bFold) FoldField.Init(1.f, N * N);
	else
	{
		Fft2(Displacement, N, 1.f);
		WakeParallel(N, [&](int32 R)
		{
			const int32 Ru = FMath::Max(R - 1, 0), Rd = FMath::Min(R + 1, N - 1);
			for (int32 C = 0; C < N; ++C)
			{
				const int32 Cl = FMath::Max(C - 1, 0), Cr = FMath::Min(C + 1, N - 1);
				const float Sx = kChop / (float(Rd - Ru) * Cell), Sy = kChop / (float(Cr - Cl) * Cell);
				const std::complex<float> Dn = Displacement[Rd * N + C] - Displacement[Ru * N + C];
				const std::complex<float> De = Displacement[R * N + Cr] - Displacement[R * N + Cl];
				FoldField[R * N + C] = (1.f + Dn.real() * Sx) * (1.f + De.imag() * Sy) - (De.real() * Sy) * (Dn.imag() * Sx);
			}
		});
	}

	WakeParallel(N, [&](int32 R)
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
			// Realism audit 8 (docs/wake-at-speed/): from 0.25 m/s, not 0.35, and lasting 4 s, not 2.5. At 6-7 kn (a J/22
			// near her hull speed) the bow wave's crest broke white only in patches and the transom's lane was gone within
			// a length; in light air (3 kn and under) the surface still moves too slowly to foam.
			// The surface's motion as it is kept (a cell pinned at the height clamp isn't moving, so it doesn't foam).
			const float Kept = FMath::Clamp(Next, -0.6f, 0.6f);
			const float Rate = FMath::Abs(Kept - Old) / Dt;
			constexpr float kFoamRate = 0.25f, kFoamLife = 4.f;
			float Churn = FMath::Max(0.f, Rate - kFoamRate) * 1.2f + (PrevDepth[I] > 0.04f && Depth[I] < 0.005f ? 4.f * PrevDepth[I] : 0.f);
			// Bow wave 2 (docs/bow-wave/): her bow wave's crest standing against her side spills white once she is fast for her
			// length: open water beside a cell under her, raised past 1.5 cm, from a length Froude number of 0.30 (a J/22 at
			// about 4.5 kn) to full by 0.42 (6 kn, her hull speed). The grid's crest at her side is a few centimetres (4 cm at
			// 6 kn on High: the curl, UpdateBowWave, draws the rest), so the rate is scaled to it: up to 0.85 foam on the crest
			// beside her bow at 6 kn (0.1 at 5 kn), a narrow white band that she leaves along her track. M_WaterV4 draws wake
			// foam only past about 0.4 (wakeBreak, over the bubbles' mean): the first rate (25, 0.28 at the most) showed
			// nothing in the PC's bow stills (Nov 26).
			if (bBowFoam && Depth[I] < 0.005f && NearFroude[I] > 0.3f && Kept > 0.015f)
			{
				const int32 Ru = FMath::Max(R - 1, 0), Rd = FMath::Min(R + 1, N - 1), Cl = FMath::Max(C - 1, 0), Cr = FMath::Min(C + 1, N - 1);
				const float Beside = FMath::Max(FMath::Max(Depth[Ru * N + C], Depth[Rd * N + C]), FMath::Max(Depth[R * N + Cl], Depth[R * N + Cr]));
				if (Beside > 0.02f) Churn += 75.f * (Kept - 0.015f) * FMath::SmoothStep(0.3f, 0.42f, NearFroude[I]);
			}
			float Foam = FMath::Clamp(FoamField[I] * FMath::Exp(-Dt / kFoamLife) + Churn * Dt * 2.f, 0.f, 1.f);
			// sailing-feedback #9: the water a moving hull has just left (astern of her, never ahead) is stirred full of
			// bubbles: a white, broken trail, thickest down her middle and thinning to nothing at her sides (StirMid, so the
			// trail has no hard edge and her sides leave little under leeway or in a tack), fading
			// over kFoamLife: the bubbles over two or three lengths, the residue a few more (0.7 down her middle, Bean
			// Nov 5: the first 0.35 was too faint from the chase camera). Only while a hull is still there and moving
			// (NearStir), so a boat that stops dead, is moved or leaves the list leaves no hull-shaped stamp.
			if (PrevStir[I] > 0.f && Stir[I] == 0.f)
			{
				Foam = FMath::Max(Foam, 0.7f * FMath::Min(PrevStirMid[I], NearStir[I]));
			}
			FoamField[I] = Foam;
			H[I] = Kept;
			Velocity[I] = Vel;
		}
	});

	// The wake's smooth lane (docs/wake-slick/): the water a hull has stirred damps the wind's ripples behind her, a
	// smoother track astern. Set where she passes (by her speed), decaying over kSlickSeconds and widening as it goes.
	// sailing-feedback #9: a 40 s life drew it as a long dark ribbon with hard edges out to the grid's end on Ultra (128 m
	// behind a J/22 at 5 kn); now it is mostly gone a few boat lengths astern (about 0.3 of its start 20 m behind her at
	// 6 kn, 0.05 at 40 m), and it spreads twice as fast, so its edges are soft. Not with the sponge's edge (it would show
	// the grid's outline).
	constexpr float kSlickSeconds = 12.f;
	constexpr float kSlickDiffusion = 0.3f; // m^2/s
	const float SlickDecay = FMath::Exp(-Dt / kSlickSeconds);
	const float Mix = FMath::Min(kSlickDiffusion * Dt / (Cell * Cell), 0.2f);
	WakeParallel(N, [&](int32 R)
	{
		for (int32 C = 0; C < N; ++C)
		{
			const int32 I = R * N + C;
			const float Up = R > 0 ? SlickField[I - N] : 0.f, Down = R < N - 1 ? SlickField[I + N] : 0.f;
			const float Left = C > 0 ? SlickField[I - 1] : 0.f, Right = C < N - 1 ? SlickField[I + 1] : 0.f;
			float S = SlickField[I] + Mix * (Up + Down + Left + Right - 4.f * SlickField[I]);
			S *= SlickDecay;
			S = FMath::Max(S, Stir[I]);
			const int32 Edge = FMath::Min(FMath::Min(R, N - 1 - R), FMath::Min(C, N - 1 - C));
			if (Edge < kSponge) S *= float(Edge) / kSponge;
			SlickScratch[I] = S;
		}
	});
	Swap(SlickField, SlickScratch);
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
