#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "SailingSim.h"
#include "WakeGrid.h"
#include "WaterSurface.h"
#include "WaveDetail.h"
#include "Waves.h"
#include <algorithm>
#include "PortableRandom.h"

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags WaterFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

	void SavePgm(const TArray<float>& Values, int32 N, float Scale, const FString& Name)
	{
		FString Pgm = FString::Printf(TEXT("P2\n%d %d\n255\n"), N, N);
		for (int32 R = N - 1; R >= 0; --R)
		{
			for (int32 C = 0; C < N; ++C) Pgm += FString::Printf(TEXT("%d "), FMath::Clamp(FMath::RoundToInt(128.f + Values[R * N + C] * Scale), 0, 255));
			Pgm += TEXT("\n");
		}
		FFileHelper::SaveStringToFile(Pgm, *(FPaths::ProjectSavedDir() / TEXT("Automation") / Name));
	}
}

/**
 * The wake grid (FWakeGrid, iWave): a J/22 hull at 6 kn in flat water makes a bow wave, a Kelvin wake that stays inside
 * a wedge of about 19.5 degrees each side, and settles when she stops (no blow-up).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWaterWakeGridTest, "SailingSim.Visual.WakeGrid", WaterFlags)
bool FWaterWakeGridTest::RunTest(const FString&)
{
	const FBoatConfig Config;
	const FBoatModel Model(Config);
	FWakeGrid Grid;
	Grid.Init(256, 0.25f);
	const float Speed = 3.1f;
	FWakeGrid::FHull Hull;
	Hull.Shape = &Config.Hulls[0];
	Hull.CanoeDepth = float(Model.HullDepth());
	Hull.Speed = Speed;
	Hull.Position = FVector2D(0.0, 0.0);
	TArray<FWakeGrid::FHull> Hulls = { Hull };
	const float Dt = 1.f / 60.f;
	for (int32 I = 0; I < 20 * 60; ++I)
	{
		Hulls[0].Position.X += Speed * Dt;
		Grid.Follow(Hulls[0].Position);
		Grid.Step(Dt, Hulls);
	}
	const int32 N = Grid.Size();
	const TArray<float>& H = Grid.Heights();
	SavePgm(H, N, 400.f, TEXT("wake.pgm"));
	SavePgm(Grid.Foam(), N, 120.f, TEXT("wake_foam.pgm"));

	const FVector2D Bow = Hulls[0].Position + FVector2D(Config.Hulls[0].BowX, 0.0);
	const FVector2D Stern = Hulls[0].Position + FVector2D(Config.Hulls[0].SternX, 0.0);
	float MaxH = 0.f, BowCrest = -1.f;
	double Inside = 0.0, Total = 0.0;
	for (int32 R = 0; R < N; ++R)
	{
		for (int32 C = 0; C < N; ++C)
		{
			const FVector2D P = Grid.Origin() + FVector2D((R + 0.5) * Grid.CellSize(), (C + 0.5) * Grid.CellSize());
			const float V = H[R * N + C];
			MaxH = FMath::Max(MaxH, FMath::Abs(V));
			const FVector2D FromBow = P - Bow;
			if (FromBow.X > -1.5 && FromBow.X < 0.6 && FMath::Abs(FromBow.Y) < 1.6) BowCrest = FMath::Max(BowCrest, V);
			const FVector2D FromStern = P - Stern;
			if (FromStern.X < -2.0)
			{
				const double Angle = FMath::RadiansToDegrees(FMath::Atan2(FMath::Abs(FromBow.Y), -FromBow.X));
				Total += V * V;
				if (Angle < 24.0) Inside += V * V;
			}
		}
	}
	const double Share = Total > 0.0 ? Inside / Total : 0.0;
	AddInfo(FString::Printf(TEXT("6 kn: largest wave %.3f m, bow crest %.3f m, %.0f%% of the wake's energy inside 24 degrees"), MaxH, BowCrest, 100.0 * Share));
	TestTrue(TEXT("The wake is a few centimetres to a couple of decimetres high"), MaxH > 0.02f && MaxH < 0.35f);
	TestTrue(TEXT("Water rises at the bow"), BowCrest > 0.01f);
	TestTrue(TEXT("Most of the wake lies inside the Kelvin wedge"), Share > 0.7);

	// Stopped, the waves run off and die away.
	Hulls[0].Speed = 0.f;
	for (int32 I = 0; I < 40 * 60; ++I) Grid.Step(Dt, Hulls);
	float After = 0.f;
	for (int32 I = 0; I < N * N; ++I)
	{
		const FVector2D P = Grid.Origin() + FVector2D((I / N + 0.5) * Grid.CellSize(), (I % N + 0.5) * Grid.CellSize());
		if (FVector2D::Distance(P, Hulls[0].Position) > 5.0) After = FMath::Max(After, FMath::Abs(H[I]));
	}
	AddInfo(FString::Printf(TEXT("40 s after stopping: largest wave %.4f m"), After));
	TestTrue(TEXT("The waves die away once she stops"), After < 0.25f * MaxH);
	return true;
}

namespace
{
	/**
	 * M_WaterV4's surface on the CPU (make_materials.py, V4_WPO and V4_SHADE, at full detail near the camera): the
	 * physics' trains under the split frequency with Gerstner choppiness, plus the FFT short waves sampled as the
	 * texture is (bilinear, periodic). Returns the vertex's height and horizontal displacement, and the Jacobian the
	 * foam reads.
	 */
	struct FRendered { double H = 0.0, Dx = 0.0, Dy = 0.0, J = 1.0; };
	FRendered RenderedVertex(const FWaveField& Waves, const FWaveDetail::FGrid* Detail, double X, double Y, double T, double Chop)
	{
		FRendered Out;
		const double Split = 2.0 * UE_DOUBLE_PI * AWaterSurface::SplitHz;
		double Jxx = 1.0, Jyy = 1.0, Jxy = 0.0;
		const FWaveComponent* C = Waves.GetComponents();
		for (int32 I = 0; I < kWaveComponents; ++I)
		{
			const FWaveComponent& W = C[I];
			if (W.Amplitude <= 1e-5 || W.Omega >= Split) continue;
			const double K = FMath::Sqrt(W.Kx * W.Kx + W.Ky * W.Ky);
			const double Arg = W.Kx * X + W.Ky * Y - W.Omega * T + W.Phase;
			const double S = FMath::Sin(Arg), Cs = FMath::Cos(Arg);
			Out.H += W.Amplitude * S;
			Out.Dx += Chop * W.Amplitude * W.Kx / K * Cs;
			Out.Dy += Chop * W.Amplitude * W.Ky / K * Cs;
			Jxx -= Chop * W.Amplitude * W.Kx * W.Kx / K * S;
			Jyy -= Chop * W.Amplitude * W.Ky * W.Ky / K * S;
			Jxy -= Chop * W.Amplitude * W.Kx * W.Ky / K * S;
		}
		Out.J = Jxx * Jyy - Jxy * Jxy;
		if (Detail)
		{
			double H, Dx, Dy, J;
			FWaveDetail::Sample(*Detail, X, Y, H, Dx, Dy, J);
			Out.H += H;
			Out.Dx += Dx;
			Out.Dy += Dy;
			Out.J *= FWaveDetail::SampleCapJ(*Detail, X, Y); // W8: the foam reads the whitecaps' Jacobian
		}
		return Out;
	}

	/** The drawn surface's height at a map point: the vertex whose displaced position lands there (fixed point). */
	double RenderedHeightAt(const FWaveField& Waves, const FWaveDetail::FGrid* Detail, double X, double Y, double T, double Chop)
	{
		double X0 = X, Y0 = Y;
		for (int32 I = 0; I < 8; ++I)
		{
			const FRendered R = RenderedVertex(Waves, Detail, X0, Y0, T, Chop);
			X0 = X - R.Dx;
			Y0 = Y - R.Dy;
		}
		return RenderedVertex(Waves, Detail, X0, Y0, T, Chop).H;
	}

	/** The physics' trains under the split frequency only. */
	double LongHeight(const FWaveField& Waves, double X, double Y, double T)
	{
		double H = 0.0;
		const FWaveComponent* C = Waves.GetComponents();
		for (int32 I = 0; I < kWaveComponents; ++I)
		{
			if (C[I].Omega < 2.0 * UE_DOUBLE_PI * AWaterSurface::SplitHz) H += C[I].Amplitude * FMath::Sin(C[I].Kx * X + C[I].Ky * Y - C[I].Omega * T + C[I].Phase);
		}
		return H;
	}

	FWaveDetailParams DetailFor(double Knots, double Fetch, double FromDeg)
	{
		FWaveDetailParams P;
		P.WindMs = Knots * kKnot;
		P.FetchMeters = Fetch;
		P.TravelDirRad = FMath::DegreesToRadians(FromDeg) + UE_DOUBLE_PI;
		P.SplitHz = AWaterSurface::SplitHz;
		P.Choppiness = AWaterSurface::Choppiness;
		return P;
	}
}

/**
 * The drawn water against the water the boat floats on (FWaveField::Height). The long waves (longer than about 4 m, the
 * ones that lift and pitch the boat) are the physics' own trains: without choppiness they match exactly; with it the
 * crests sharpen and the troughs flatten, a second-order difference that is measured. The short waves are a different
 * random realization of the same spectrum, so the whole surface matches statistically: its significant wave height must
 * lie in the Phase 8 band for the lake's waves (+-20%), and the point-by-point difference is reported.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWaterWaveMatchTest, "SailingSim.Visual.WaveMatch", WaterFlags)
bool FWaterWaveMatchTest::RunTest(const FString&)
{
	for (const double Knots : { 8.0, 15.0, 22.0 })
	{
		FWaveField Waves(1);
		FWaveParams WP;
		WP.WindSpeedKnots = Knots;
		WP.FetchMeters = 12000.0; // Ray Hubbard, 15 kn over about 8 miles (the Phase 8 check)
		WP.WindFromDegrees = 200.0;
		Waves.SetWind(WP);
		Waves.SnapToTarget();
		FWaveDetail Detail;
		Detail.Configure(DetailFor(Knots, WP.FetchMeters, WP.WindFromDegrees), { FWaveDetail::ChopCascade() });
		// The material draws exactly the first LongComponents trains: they must be the ones under the split.
		int32 Matching = 0;
		for (int32 I = 0; I < kWaveComponents; ++I) Matching += (Waves.GetComponents()[I].Omega < 2.0 * UE_DOUBLE_PI * AWaterSurface::SplitHz) == (I < AWaterSurface::LongComponents);
		TestEqual(TEXT("The long trains are the first eight bands"), Matching, kWaveComponents);

		Sailing::FPortableRandom Rng(7);
		auto U = [&Rng]() { return Rng.Uniform(-400.0, 400.0); };
		double ExactErr = 0.0, LongDiff2 = 0.0, Diff2 = 0.0, Phys2 = 0.0, Drawn2 = 0.0, LongVar = 0.0;
		int32 Count = 0;
		for (const double T : { 10.0, 37.3, 81.9 })
		{
			FWaveDetail::FGrid Grid;
			Detail.Evaluate(0, T, Grid);
			for (int32 I = 0; I < 1500; ++I)
			{
				const double X = U(), Y = U();
				const double Phys = Waves.Height(X, Y, T);
				const double Long = LongHeight(Waves, X, Y, T);
				ExactErr = FMath::Max(ExactErr, FMath::Abs(RenderedHeightAt(Waves, nullptr, X, Y, T, 0.0) - Long));
				LongDiff2 += FMath::Square(RenderedHeightAt(Waves, nullptr, X, Y, T, AWaterSurface::Choppiness) - Long);
				const double Drawn = RenderedHeightAt(Waves, &Grid, X, Y, T, AWaterSurface::Choppiness);
				Diff2 += FMath::Square(Drawn - Phys);
				Phys2 += Phys * Phys;
				Drawn2 += Drawn * Drawn;
				LongVar += Long * Long;
				++Count;
			}
		}
		const double HsPhys = 4.0 * FMath::Sqrt(Phys2 / Count), HsDrawn = 4.0 * FMath::Sqrt(Drawn2 / Count);
		const double LongShare = LongVar / Phys2;
		AddInfo(FString::Printf(TEXT("%2.0f kn: Hs physics %.3f m, drawn %.3f m (%+.0f%%); long waves %.0f%% of the variance; long part exact to %.1e m "
			"without choppiness, %.1f cm RMS with it; whole surface %.1f cm RMS point by point"),
			Knots, HsPhys, HsDrawn, 100.0 * (HsDrawn / HsPhys - 1.0), 100.0 * LongShare, ExactErr, 100.0 * FMath::Sqrt(LongDiff2 / Count), 100.0 * FMath::Sqrt(Diff2 / Count)));
		TestTrue(FString::Printf(TEXT("%.0f kn: the long waves are the physics' own"), Knots), ExactErr < 1e-4);
		TestTrue(FString::Printf(TEXT("%.0f kn: drawn Hs within the Phase 8 band"), Knots), HsDrawn > 0.8 * HsPhys && HsDrawn < 1.2 * HsPhys);
		TestTrue(FString::Printf(TEXT("%.0f kn: choppiness changes the long waves only at second order"), Knots), FMath::Sqrt(LongDiff2 / Count) < 0.15 * HsPhys);
	}
	return true;
}

/**
 * W8: whitecaps as the camera sees them (docs/water-8/whitecaps). Farther than a few metres a pixel spans several chop
 * texels, and the GPU reads the texture's mips. A mip of the Jacobian averages toward 1, so thresholding it (M_WaterV4
 * before W8) lost nearly every cap: the lake at 20 kn measured twice its target here and showed almost none. The fold
 * table's mips (AWaterSurface::CapTableEntry, read by CapCover as the material does) average the cover itself, so at
 * every mip level the cover is the grid's own (within 30 %, from mip 1: the table is read from about a texel a pixel).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWaterWhitecapsSeenTest, "SailingSim.Visual.WhitecapsSeen", WaterFlags)
bool FWaterWhitecapsSeenTest::RunTest(const FString&)
{
	// Whitecap mask (docs/water-8/capshape-mac): 12 and 16 kn too, where the drawn cover had drifted from its CPU copy.
	for (const double Knots : { 12.0, 14.0, 16.0, 20.0, 25.0 })
	{
		FWaveField Waves(1);
		FWaveParams WP;
		WP.WindSpeedKnots = Knots;
		WP.FetchMeters = 8000.0;
		Waves.SetWind(WP);
		Waves.SnapToTarget();
		FWaveDetail Detail;
		Detail.Configure(DetailFor(Knots, WP.FetchMeters, WP.WindFromDegrees), { FWaveDetail::ChopCascade() });
		// The chop's own whitecap Jacobian, at thresholds that cap 0.2, 0.5 and 1.5 % of it (the long waves only move the
		// threshold the shader reads it at); the table's entries a slope apart, the threshold between two of them.
		std::vector<float> All;
		for (const double T : { 5.0, 23.0, 61.0, 97.0 })
		{
			FWaveDetail::FGrid Grid;
			Detail.Evaluate(0, T, Grid);
			All.insert(All.end(), Grid.JCap.begin(), Grid.JCap.end());
		}
		std::sort(All.begin(), All.end());
		const float Step = FMath::Max(AWaterSurface::CapSlopeAt(float(Knots)), 0.03f);
		const float Lake = AWaterSurface::WhitecapScaleFor(0);
		for (const double Ratio : { 0.002, 0.005, 0.015 })
		{
		const float Thr = All[size_t(Ratio * All.size())];
		const float First = Thr - 1.4f * Step;
		constexpr int32 Levels = 6;
		double Hard = 0.0, Table[Levels] = {}, Old[Levels] = {};
		int32 Frames = 0;
		for (const double T : { 5.0, 23.0, 61.0, 97.0 })
		{
			FWaveDetail::FGrid Grid;
			Detail.Evaluate(0, T, Grid);
			int32 N = Grid.N;
			std::vector<float> J = Grid.JCap;
			std::vector<float> C(size_t(N) * N * 4);
			for (size_t I = 0; I < J.size(); ++I)
			{
				Hard += J[I] < Thr ? 1.0 / J.size() : 0.0;
				for (int32 K = 0; K < 4; ++K) C[I * 4 + K] = AWaterSurface::CapTableEntry(J[I], K, First, Step);
			}
			for (int32 L = 0; L < Levels; ++L)
			{
				double SumT = 0.0, SumO = 0.0;
				for (size_t I = 0; I < J.size(); ++I)
				{
					SumT += AWaterSurface::CapCover(&C[I * 4], Thr, float(Knots), float(L), First, Step);
					SumO += FMath::Clamp((Thr - J[I]) / 0.05 + 0.5, 0.0, 1.0);
				}
				Table[L] += SumT / J.size();
				Old[L] += SumO / J.size();
				// The next mip: 2x2 box means (as the texture's mips are built, PackMips).
				const int32 M = N / 2;
				std::vector<float> J2(size_t(M) * M), C2(size_t(M) * M * 4);
				for (int32 R = 0; R < M; ++R)
					for (int32 Q = 0; Q < M; ++Q)
					{
						const size_t A = size_t(2 * R) * N + 2 * Q, B = A + 1, Cc = A + N, D = Cc + 1, O = size_t(R) * M + Q;
						J2[O] = 0.25f * (J[A] + J[B] + J[Cc] + J[D]);
						for (int32 K = 0; K < 4; ++K) C2[O * 4 + K] = 0.25f * (C[A * 4 + K] + C[B * 4 + K] + C[Cc * 4 + K] + C[D * 4 + K]);
					}
				J = MoveTemp(J2);
				C = MoveTemp(C2);
				N = M;
			}
			++Frames;
		}
		Hard /= Frames;
		FString Line;
		for (int32 L = 0; L < Levels; ++L) Line += FString::Printf(TEXT(" mip %d: %.2f%% (J mipped %.2f%%);"), L, 100.0 * Table[L] / Frames, 100.0 * Old[L] / Frames);
		AddInfo(FString::Printf(TEXT("%2.0f kn, chop capped %.1f%%: the grid %.3f%%;%s"), Knots, 100.0 * Ratio, 100.0 * Hard, *Line));
		// Mip 0 is drawn from the fold itself (the J mipped column there); the table from about a texel a pixel.
		for (int32 L = 1; L < Levels; ++L)
		{
			const double Seen = Table[L] / Frames;
			// The renderer's bias, not the seeds: at the sparsest cover (25 kn, 0.2%) mip 1 reads about 25% high on every
			// realization measured (0.25% with main's draws, 0.26% with FPortableRandom's, against 0.200% on the grid), so its
			// band is 35% there. Why mip 1 overestimates sparse caps is its own item on the water list.
			const double Band = (L == 1 && Knots >= 24.0 && Ratio <= 0.0025) ? 0.35 : 0.3;
			TestTrue(FString::Printf(TEXT("%.0f kn, %.3f: mip %d sees the grid's cover (within %.0f%%)"), Knots, Ratio, L, 100.0 * Band), Seen > (1.0 - Band) * Hard && Seen < (1.0 + Band) * Hard);
		}
		TestTrue(FString::Printf(TEXT("%.0f kn, %.3f: the fold at mip 0 is the grid's (within 20%%)"), Knots, Ratio), FMath::Abs(Old[0] / Frames - Hard) <= 0.2 * Hard + 1e-5);
		TestTrue(FString::Printf(TEXT("%.0f kn, %.3f: a mipped Jacobian loses the caps (why the table)"), Knots, Ratio), Old[3] / Frames < 0.3 * Hard);
		}

		// The renderer solves the threshold on the sea it draws (FWaveDetail::CapThreshold on the long trains' fold, as
		// the mesh has it, times the chop's): solved on one stretch of time and water, it caps the target on another.
		const double Target = 3.84e-6 * FMath::Pow(Knots * kKnot, 3.41) * Lake;
		const double OmegaMax = 2.0 * UE_DOUBLE_PI * AWaterSurface::SplitHz;
		auto Sea = [&](double T0, double X0)
		{
			std::vector<float> Out;
			for (const double T : { T0, T0 + 7.0, T0 + 19.0 })
			{
				FWaveDetail::FGrid Grid;
				Detail.Evaluate(0, T, Grid);
				for (int32 I = 0; I < Grid.N * Grid.N; ++I)
					Out.push_back(float(FWaveDetail::LongJacobian(Waves.GetComponents(), kWaveComponents, OmegaMax, AWaterSurface::Choppiness,
						X0 + (I / Grid.N) * 1.31, (I % Grid.N) * 1.37, T, 0.5) * Grid.JCap[I]));
			}
			return Out;
		};
		double Thr = 0.0, Slope = 0.0;
		FWaveDetail::CapThreshold(Sea(11.0, 0.0), Target, Thr, Slope);
		const std::vector<float> Other = Sea(140.0, 900.0);
		double Capped = 0.0;
		for (const float V : Other) Capped += V < Thr ? 1.0 / Other.size() : 0.0;
		AddInfo(FString::Printf(TEXT("%2.0f kn, lake: solved threshold %.3f (slope %.3f per e-fold) caps %.3f%% elsewhere, target %.3f%%"),
			Knots, Thr, Slope, 100.0 * Capped, 100.0 * Target));
		TestTrue(FString::Printf(TEXT("%.0f kn: the solved threshold caps the target on other water (within 35%%)"), Knots), Capped > 0.65 * Target && Capped < 1.35 * Target);
		// The CPU's long-wave fold is the test's (and the material's) at full mesh resolution.
		const double Exact = RenderedVertex(Waves, nullptr, 3.7, 8.1, 42.0, AWaterSurface::Choppiness).J;
		TestTrue(TEXT("LongJacobian is the drawn long waves' fold"), FMath::IsNearlyEqual(Exact, FWaveDetail::LongJacobian(Waves.GetComponents(), kWaveComponents, OmegaMax, AWaterSurface::Choppiness, 3.7, 8.1, 42.0), 1e-9));
		// The renderer's four-spacing pass (FLongJacobians, water worker load) is LongJacobian at each spacing.
		const double Spacings[4] = { 0.5, 1.0, 2.0, 4.0 }, Fades[4] = { 1.0, 0.93, 0.86, 0.72 };
		const FWaveDetail::FLongJacobians Four(Waves.GetComponents(), kWaveComponents, OmegaMax, AWaterSurface::Choppiness, Spacings, Fades, 4);
		double MaxErr = 0.0;
		for (int32 P = 0; P < 50; ++P)
		{
			const double X = 13.7 * P, Y = -9.1 * P + 4.0, T = 42.0 + 0.37 * P;
			double J[4];
			Four.Evaluate(X, Y, T, J);
			for (int32 K = 0; K < 4; ++K)
			{
				MaxErr = FMath::Max(MaxErr, FMath::Abs(J[K] - FWaveDetail::LongJacobian(Waves.GetComponents(), kWaveComponents, OmegaMax, AWaterSurface::Choppiness, X, Y, T, Spacings[K], Fades[K])));
			}
		}
		TestTrue(FString::Printf(TEXT("%.0f kn: FLongJacobians matches LongJacobian at four spacings (max error %.1e)"), Knots, MaxErr), MaxErr < 1e-9);
	}
	return true;
}

/**
 * Whitecaps from the drawn waves: the share of the surface where the crests fold (the Jacobian under the material's
 * FoamThreshold) against Monahan's whitecap coverage law W = 3.84e-6 U^3.41 (U at 10 m, m/s). The Beaufort scale is
 * the check: almost none at 6 kn, within a factor of three of the law from 10 kn up. W0: the material moves the
 * threshold by the local wind against the mean and by the water body (AWaterSurface::WhitecapThreshold): the lake gets
 * 0.4 of the law and the bay 0.7 at the mean wind, and a puff of 1.3x the mean caps more than the mean, a lull of 0.7x less.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWaterWhitecapsTest, "SailingSim.Visual.Whitecaps", WaterFlags)
bool FWaterWhitecapsTest::RunTest(const FString&)
{
	const float Lake = AWaterSurface::WhitecapScaleFor(0), Bay = AWaterSurface::WhitecapScaleFor(1), Sea = AWaterSurface::WhitecapScaleFor(2);
	TestTrue(TEXT("The Gulf keeps the sea's law"), Sea == 1.f);
	TestTrue(TEXT("At the mean wind the sea's threshold is the calibrated one"), FMath::IsNearlyEqual(AWaterSurface::WhitecapThreshold(1.f, Sea), AWaterSurface::FoamThresholdAt(14.f)));
	for (const double Knots : { 6.0, 10.0, 12.0, 14.0, 16.0, 20.0, 25.0 })
	{
		const double Threshold = AWaterSurface::FoamThresholdAt(float(Knots));
		FWaveField Waves(1);
		FWaveParams WP;
		WP.WindSpeedKnots = Knots;
		WP.FetchMeters = 8000.0;
		Waves.SetWind(WP);
		Waves.SnapToTarget();
		FWaveDetail Detail;
		Detail.Configure(DetailFor(Knots, WP.FetchMeters, WP.WindFromDegrees), { FWaveDetail::ChopCascade() });
		Sailing::FPortableRandom Rng(11);
		auto U = [&Rng]() { return Rng.Uniform(0.0, 300.0); };
		TArray<double> Js;
		for (const double T : { 5.0, 23.0, 61.0, 97.0 })
		{
			FWaveDetail::FGrid Grid;
			Detail.Evaluate(0, T, Grid);
			for (int32 I = 0; I < 10000; ++I)
			{
				Js.Add(RenderedVertex(Waves, &Grid, U(), U(), T, AWaterSurface::Choppiness).J);
			}
		}
		auto CoverageAt = [&Js](double Thr)
		{
			int32 Folded = 0;
			for (const double J : Js) Folded += J < Thr;
			return double(Folded) / Js.Num();
		};
		const double Coverage = CoverageAt(Threshold);
		const double Monahan = 3.84e-6 * FMath::Pow(Knots * kKnot, 3.41);
		const double LakeMean = CoverageAt(AWaterSurface::WhitecapThreshold(1.f, Lake, float(Knots)));
		const double LakePuff = CoverageAt(AWaterSurface::WhitecapThreshold(1.3f, Lake, float(Knots)));
		const double LakeLull = CoverageAt(AWaterSurface::WhitecapThreshold(0.7f, Lake, float(Knots)));
		const double BayMean = CoverageAt(AWaterSurface::WhitecapThreshold(1.f, Bay, float(Knots)));
		// The threshold shift per e-fold of coverage on these waves: 0.034 at 10 kn to 0.069 at 25 kn (AWaterSurface::CapSlopeAt).
		const double Lo = CoverageAt(Threshold - 0.05), Hi = CoverageAt(Threshold + 0.05);
		const double Slope = Lo > 0.0 && Hi > Lo ? 0.1 / FMath::Loge(Hi / Lo) : 0.0;
		AddInfo(FString::Printf(TEXT("%2.0f kn: whitecaps %.2f%% of the surface, Monahan %.2f%%; lake %.2f%% (puff 1.3x %.2f%%, lull 0.7x %.2f%%), "
			"bay %.2f%%; threshold per e-fold %.3f"), Knots, 100.0 * Coverage, 100.0 * Monahan, 100.0 * LakeMean, 100.0 * LakePuff,
			100.0 * LakeLull, 100.0 * BayMean, Slope));
		if (Knots < 7.0)
		{
			TestTrue(TEXT("Almost no whitecaps at 6 kn (Beaufort 2: crests do not break)"), Coverage < 3e-4);
			TestTrue(TEXT("Almost none on the lake at 6 kn either"), LakeMean < 3e-4);
		}
		else
		{
			TestTrue(FString::Printf(TEXT("%.0f kn: whitecap coverage within a factor of three of Monahan's"), Knots), Coverage > Monahan / 3.0 && Coverage < 3.0 * Monahan);
			// W2: the threshold's slope follows the wind (AWaterSurface::CapSlopeAt), so the lake holds its share in a strong
			// breeze too (it capped 3.3 and 3.6 times 0.4 Monahan at 20 and 25 kn with a fixed slope).
			const bool bLakeInBand = LakeMean > Lake * Monahan / 3.0 && LakeMean < 3.0 * Lake * Monahan;
			TestTrue(FString::Printf(TEXT("%.0f kn: fresh water within a factor of three of 0.4 Monahan (%.1f times)"), Knots, LakeMean / (Lake * Monahan)), bLakeInBand);
			TestTrue(FString::Printf(TEXT("%.0f kn: the bay within a factor of three of 0.7 Monahan"), Knots), BayMean > Bay * Monahan / 3.0 && BayMean < 3.0 * Bay * Monahan);
			TestTrue(FString::Printf(TEXT("%.0f kn: the lake caps less than the sea"), Knots), LakeMean < Coverage);
			TestTrue(FString::Printf(TEXT("%.0f kn: a puff (1.3x the mean) caps more than the mean"), Knots), LakePuff > LakeMean);
			TestTrue(FString::Printf(TEXT("%.0f kn: a lull (0.7x the mean) caps less than the mean"), Knots), LakeLull < LakeMean);
			if (Knots >= 10.0)
			{
				// Monahan's ratio for a 1.3x puff is 1.3^3.41 = 2.45; on the drawn waves within a factor of two of it.
				const double PuffRatio = LakePuff / FMath::Max(LakeMean, 1e-9);
				TestTrue(FString::Printf(TEXT("%.0f kn: puff/mean %.2f near Monahan's 2.45"), Knots, PuffRatio), PuffRatio > 1.25 && PuffRatio < 4.9);
			}
		}
	}
	return true;
}

/**
 * Light air (the PC's 10 kn stills showed metre-long caps): below 12 kn only WhitecapOnset's share of Monahan's cover
 * breaks, and FWaveDetail::CapThreshold reaches a target under eight of its samples by extrapolating down the tail
 * (the quantile floored the cover at the lowest sample's, about 1/N, whatever the target).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWaterWhitecapOnsetTest, "SailingSim.Visual.WhitecapOnset", WaterFlags)
bool FWaterWhitecapOnsetTest::RunTest(const FString&)
{
	TestEqual(TEXT("The full law from 12 kn"), AWaterSurface::WhitecapOnset(12.f), 1.f);
	TestEqual(TEXT("The full law at 20 kn"), AWaterSurface::WhitecapOnset(20.f), 1.f);
	TestEqual(TEXT("Nothing breaks under 7 kn"), AWaterSurface::WhitecapOnset(7.f), 0.f);
	const float At10 = AWaterSurface::WhitecapOnset(10.f);
	TestTrue(FString::Printf(TEXT("A fifth of the law at 10 kn (%.3f)"), At10), At10 > 0.15f && At10 < 0.25f);
	TestTrue(TEXT("Rising with the wind"), AWaterSurface::WhitecapOnset(9.f) < At10 && At10 < AWaterSurface::WhitecapOnset(11.f));
	// W4: a shallow cell (shoal 1, M_WaterV4's shoalBreak) adds no fold at 6 kn, so it can't cap there (the marina's white
	// water); the full fold by 16 kn.
	TestEqual(TEXT("No shoal fold at 6 kn"), AWaterSurface::ShoalFoldScale(6.f), 0.f);
	TestEqual(TEXT("The full shoal fold at 16 kn"), AWaterSurface::ShoalFoldScale(16.f), 1.f);
	TestEqual(TEXT("A shallow cell at 6 kn: no cap (no onset, no shoal fold)"), AWaterSurface::WhitecapOnset(6.f) + 0.25f * AWaterSurface::ShoalFoldScale(6.f), 0.f);

	const double Knots = 10.0;
	FWaveField Waves(1);
	FWaveParams WP;
	WP.WindSpeedKnots = Knots;
	WP.FetchMeters = 8000.0;
	Waves.SetWind(WP);
	Waves.SnapToTarget();
	FWaveDetail Detail;
	Detail.Configure(DetailFor(Knots, WP.FetchMeters, WP.WindFromDegrees), { FWaveDetail::ChopCascade() });
	const double OmegaMax = 2.0 * UE_DOUBLE_PI * AWaterSurface::SplitHz;
	// As the renderer samples it: every other texel of one frame.
	auto Sea = [&](double T, double X0, int32 Stride)
	{
		FWaveDetail::FGrid Grid;
		Detail.Evaluate(0, T, Grid);
		std::vector<float> Out;
		for (int32 R = 0; R < Grid.N; R += Stride)
			for (int32 C = 0; C < Grid.N; C += Stride)
				Out.push_back(float(FWaveDetail::LongJacobian(Waves.GetComponents(), kWaveComponents, OmegaMax, AWaterSurface::Choppiness,
					X0 + R * 1.31, C * 1.37, T, 0.5) * Grid.JCap[R * Grid.N + C]));
		return Out;
	};
	const double Lake = 3.84e-6 * FMath::Pow(Knots * kKnot, 3.41) * AWaterSurface::WhitecapScaleFor(0);
	const double Target = Lake * At10;
	// The renderer eases each frame's solution over a couple of seconds: the mean over frames a few seconds apart.
	double Thr = 0.0, FloorThr = 0.0, AtFloor = 0.0;
	constexpr int32 Frames = 12;
	for (int32 F = 0; F < Frames; ++F)
	{
		const std::vector<float> Solved = Sea(11.0 + 4.3 * F, 37.0 * F, 2);
		TestTrue(TEXT("The 10 kn target is under eight of the renderer's samples"), Target * Solved.size() < 8.0);
		double T1 = 0.0, T2 = 0.0, T3 = 0.0, Slope = 0.0;
		FWaveDetail::CapThreshold(Solved, Target, T1, Slope);
		FWaveDetail::CapThreshold(Solved, 0.2 * Target, T2, Slope);
		FWaveDetail::CapThreshold(Solved, 8.0 / Solved.size(), T3, Slope);
		Thr += T1 / Frames;
		FloorThr += T2 / Frames;
		AtFloor += T3 / Frames;
	}
	std::vector<float> Other;
	for (const double T : { 140.0, 171.0, 203.0, 260.0, 311.0, 367.0, 419.0, 480.0, 533.0, 597.0, 641.0, 709.0 })
	{
		const std::vector<float> More = Sea(T, 900.0 + T, 1);
		Other.insert(Other.end(), More.begin(), More.end());
	}
	double Capped = 0.0, Lowest = 0.0, Eight = 0.0;
	for (const float V : Other)
	{
		Capped += V < Thr ? 1.0 / Other.size() : 0.0;
		Lowest += V < FloorThr ? 1.0 / Other.size() : 0.0;
		Eight += V < AtFloor ? 1.0 / Other.size() : 0.0;
	}
	AddInfo(FString::Printf(TEXT("10 kn, lake: the eighth sample's threshold %.3f caps %.4f%% elsewhere"), AtFloor, 100.0 * Eight));
	AddInfo(FString::Printf(TEXT("10 kn, lake: target %.4f%% (%.4f%% before the onset), threshold %.3f caps %.4f%% elsewhere"),
		100.0 * Target, 100.0 * Lake, Thr, 100.0 * Capped));
	TestTrue(FString::Printf(TEXT("The extrapolated threshold caps the target elsewhere (within a factor of three: %.4f%%)"), 100.0 * Capped),
		Capped > Target / 3.0 && Capped < 3.0 * Target);
	TestTrue(FString::Printf(TEXT("A fifth of the target caps less (%.4f%%)"), 100.0 * Lowest), Lowest < Capped);

	// Whitecap mask (docs/water-8/capshape-mac): the full law from 12 kn, the threshold solved as the renderer solves it
	// (its samples scaled by the drawn fold) capping the target on other water at 12 and 16 kn as at 20.
	for (const double K : { 12.0, 16.0, 20.0 })
	{
		FWaveField W2(1);
		FWaveParams P2;
		P2.WindSpeedKnots = K;
		P2.FetchMeters = 8000.0;
		W2.SetWind(P2);
		W2.SnapToTarget();
		FWaveDetail D2;
		D2.Configure(DetailFor(K, P2.FetchMeters, P2.WindFromDegrees), { FWaveDetail::ChopCascade() });
		const float Fold = AWaterSurface::DrawnFoldScaleAt(float(K));
		auto Drawn = [&](double T, double X0)
		{
			FWaveDetail::FGrid Grid;
			D2.Evaluate(0, T, Grid);
			std::vector<float> Out;
			for (int32 R = 0; R < Grid.N; R += 2)
				for (int32 C = 0; C < Grid.N; C += 2)
					Out.push_back(float(1.0 - Fold * (1.0 - FWaveDetail::LongJacobian(W2.GetComponents(), kWaveComponents, OmegaMax, AWaterSurface::Choppiness,
						X0 + R * 1.31, C * 1.37, T, 0.5) * Grid.JCap[R * Grid.N + C])));
			return Out;
		};
		const double Tgt = 3.84e-6 * FMath::Pow(K * kKnot, 3.41) * AWaterSurface::WhitecapScaleFor(0) * AWaterSurface::WhitecapOnset(float(K));
		double KThr = 0.0;
		for (int32 F = 0; F < Frames; ++F)
		{
			double T1 = 0.0, Slope = 0.0;
			FWaveDetail::CapThreshold(Drawn(11.0 + 4.3 * F, 37.0 * F), Tgt, T1, Slope);
			KThr += T1 / Frames;
		}
		double KCapped = 0.0;
		size_t KCount = 0;
		for (const double T : { 140.0, 203.0, 311.0, 419.0, 533.0, 641.0 })
		{
			const std::vector<float> More = Drawn(T, 900.0 + T);
			for (const float V : More) KCapped += V < KThr ? 1.0 : 0.0;
			KCount += More.size();
		}
		KCapped /= double(KCount);
		AddInfo(FString::Printf(TEXT("%2.0f kn, lake: drawn fold x%.3f, target %.3f%%, threshold %.3f caps %.3f%% elsewhere"), K, Fold, 100.0 * Tgt, KThr, 100.0 * KCapped));
		TestTrue(FString::Printf(TEXT("%.0f kn: the full law (no onset share)"), K), AWaterSurface::WhitecapOnset(float(K)) == 1.f);
		TestTrue(FString::Printf(TEXT("%.0f kn: the solved threshold caps the target elsewhere (within 35%%: %.3f%%)"), K, 100.0 * KCapped),
			KCapped > 0.65 * Tgt && KCapped < 1.35 * Tgt);
	}
	// The drawn fold's scale by wind: W8's 0.85 at its 20 kn fit and above, deeper as the wind falls, held under 12 kn.
	TestTrue(TEXT("The drawn fold scale rises as the wind falls"), AWaterSurface::DrawnFoldScaleAt(20.f) < AWaterSurface::DrawnFoldScaleAt(16.f)
		&& AWaterSurface::DrawnFoldScaleAt(16.f) < AWaterSurface::DrawnFoldScaleAt(12.f));
	TestTrue(TEXT("Held below 12 kn"), AWaterSurface::DrawnFoldScaleAt(8.f) == AWaterSurface::DrawnFoldScaleAt(12.f));
	TestTrue(TEXT("Never under W8's 0.85"), AWaterSurface::DrawnFoldScaleAt(30.f) == 0.85f);
	return true;
}

/**
 * Whitecap size by wind (docs/water-8/capshape-mac): with the cap blur fixed at W8's 0.36 m, 12 kn caps came out as long
 * as 20 kn ones. The blur (FWaveDetail::CapBlurMeters) follows the wind as U^0.85 up to W8's 20 kn fit, so at each
 * wind's own share of Monahan's cover the caps are both smaller and rarer in lighter air.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWaterWhitecapSizeTest, "SailingSim.Visual.WhitecapSize", WaterFlags)
bool FWaterWhitecapSizeTest::RunTest(const FString&)
{
	const double At20 = FWaveDetail::CapBlurMeters(20.0 * kKnot);
	TestTrue(FString::Printf(TEXT("W8's 0.36 m at 20 kn (%.3f m)"), At20), FMath::IsNearlyEqual(At20, 2.0 * 23.0 / 128.0, 1e-6));
	TestTrue(TEXT("The blur grows with the wind"), FWaveDetail::CapBlurMeters(12.0 * kKnot) < FWaveDetail::CapBlurMeters(16.0 * kKnot)
		&& FWaveDetail::CapBlurMeters(16.0 * kKnot) < At20);
	double Area[3] = {}, Count[3] = {};
	int32 Index = 0;
	for (const double Knots : { 12.0, 16.0, 20.0 })
	{
		FWaveDetail Detail;
		Detail.Configure(DetailFor(Knots, 8000.0, 0.0), { FWaveDetail::ChopCascade() });
		// The chop's own fold at the lake's share of Monahan's cover for this wind (the long trains only move where it
		// lands), as connected caps (8-neighbours, periodic).
		const double Share = 3.84e-6 * FMath::Pow(Knots * kKnot, 3.41) * AWaterSurface::WhitecapScaleFor(0);
		std::vector<FWaveDetail::FGrid> Grids;
		std::vector<float> All;
		for (int32 F = 0; F < 24; ++F)
		{
			Grids.emplace_back();
			Detail.Evaluate(0, 5.0 + 7.3 * F, Grids.back());
			All.insert(All.end(), Grids.back().JCap.begin(), Grids.back().JCap.end());
		}
		std::nth_element(All.begin(), All.begin() + size_t(Share * All.size()), All.end());
		const float Thr = All[size_t(Share * All.size())];
		double Cells = 0.0, Caps = 0.0;
		for (const FWaveDetail::FGrid& Grid : Grids)
		{
			const int32 N = Grid.N;
			std::vector<uint8> Seen(size_t(N) * N, 0);
			for (int32 I = 0; I < N * N; ++I)
			{
				if (Seen[I] || Grid.JCap[I] >= Thr) continue;
				Caps += 1.0;
				std::vector<int32> Stack{ I };
				Seen[I] = 1;
				while (!Stack.empty())
				{
					const int32 C = Stack.back();
					Stack.pop_back();
					Cells += 1.0;
					for (int32 Dr = -1; Dr <= 1; ++Dr)
						for (int32 Dc = -1; Dc <= 1; ++Dc)
						{
							const int32 Nb = ((C / N + Dr + N) % N) * N + (C % N + Dc + N) % N;
							if (!Seen[Nb] && Grid.JCap[Nb] < Thr) { Seen[Nb] = 1; Stack.push_back(Nb); }
						}
				}
			}
		}
		const double Cell = 23.0 / 128.0;
		Area[Index] = Cells / FMath::Max(Caps, 1.0) * Cell * Cell;
		Count[Index] = Caps / Grids.size();
		AddInfo(FString::Printf(TEXT("%2.0f kn: blur %.2f m, the lake's cover (%.3f%%): %.2f caps a 23 m tile, %.2f m^2 each"), Knots,
			FWaveDetail::CapBlurMeters(Knots * kKnot), 100.0 * Share, Count[Index], Area[Index]));
		++Index;
	}
	TestTrue(FString::Printf(TEXT("12 kn caps are smaller than 20 kn ones (%.2f against %.2f m^2)"), Area[0], Area[2]), Area[0] < 0.7 * Area[2]);
	TestTrue(TEXT("16 kn caps in between"), Area[0] < Area[1] && Area[1] < Area[2]);
	TestTrue(FString::Printf(TEXT("and rarer (%.2f against %.2f a tile)"), Count[0], Count[2]), Count[0] < Count[1] && Count[1] < Count[2]);
	return true;
}

/**
 * The water edge (docs/water-8/edge-mac): past the rings the far water is a grid whose cells grow with the distance, so the
 * earth's curvature (d^2 / 2R, added per vertex by the materials' CURVATURE_CODE and interpolated across each triangle)
 * stays within a few centimetres of the true drop out to 20 km. The old far plane (one 40 km quad) lay 25 to 50 m down
 * just past the rings, and the shallow bay bed showed above it. Also: the grid starts inside the outer ring and ends at
 * the far edge, with no gaps.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWaterFarGridTest, "SailingSim.Visual.FarWaterCurvature", WaterFlags)
bool FWaterFarGridTest::RunTest(const FString& Parameters)
{
	constexpr double R = 7.433e6; // CURVATURE_CODE: 7/6 of the earth's radius (m)
	auto Drop = [&](const FVector2D& P) { return P.SizeSquared() / (2.0 * R); };
	for (const int32 Rings : { 3, 5, 7 })
	{
		const float Inner = AWaterSurface::FarGridInnerHalfMeters(Rings);
		const float Outer = 20000.f;
		TArray<FVector> Verts;
		TArray<int32> Tris;
		AWaterSurface::BuildFarGrid(Inner, Outer, AWaterSurface::FarGridPerSide, Verts, Tris);
		double WorstErr = 0.0, WorstAt = 0.0, WorstFar = 0.0, MinR = 1e9, MaxR = 0.0;
		int32 Down = 0;
		for (int32 T = 0; T + 2 < Tris.Num(); T += 3)
		{
			const FVector2D A(Verts[Tris[T]] / Sailing::CmPerMeter), B(Verts[Tris[T + 1]] / Sailing::CmPerMeter), C(Verts[Tris[T + 2]] / Sailing::CmPerMeter);
			Down += FVector2D::CrossProduct(B - A, C - A) < 0.0 ? 1 : 0;
			for (const FVector2D& V : { A, B, C })
			{
				MinR = FMath::Min(MinR, FMath::Max(FMath::Abs(V.X), FMath::Abs(V.Y)));
				MaxR = FMath::Max(MaxR, FMath::Max(FMath::Abs(V.X), FMath::Abs(V.Y)));
			}
			// The interpolated drop against the true one at the edge midpoints and the centroid (a quadratic's largest
			// interpolation error over a triangle lies on its longest edge's midpoint).
			const double DA = Drop(A), DB = Drop(B), DC = Drop(C);
			const TPair<FVector2D, double> Probes[] = { { (A + B) / 2, (DA + DB) / 2 }, { (B + C) / 2, (DB + DC) / 2 },
				{ (A + C) / 2, (DA + DC) / 2 }, { (A + B + C) / 3, (DA + DB + DC) / 3 } };
			for (const TPair<FVector2D, double>& Pr : Probes)
			{
				const double Err = FMath::Abs(Pr.Value - Drop(Pr.Key));
				if (Err > WorstErr) { WorstErr = Err; WorstAt = Pr.Key.Size(); }
				if (Pr.Key.Size() > 19000.0) WorstFar = FMath::Max(WorstFar, Err);
			}
		}
		AddInfo(FString::Printf(TEXT("%d rings: far grid from %.0f m to %.0f m, %d vertices, %d triangles; worst curvature error %.1f cm at %.1f km, %.1f cm past 19 km"),
			Rings, MinR, MaxR, Verts.Num(), Tris.Num() / 3, WorstErr * 100.0, WorstAt / 1000.0, WorstFar * 100.0));
		TestTrue(TEXT("Every triangle wound as the rings' (facing up in Unreal's convention)"), Down == Tris.Num() / 3);
		TestTrue(TEXT("Starts inside the outer ring (one ring cell of overlap)"), FMath::IsNearlyEqual(MinR, double(Inner), 1.0)
			&& Inner < 64.f * 0.5f * float(1 << (Rings - 1)));
		TestTrue(TEXT("Reaches 20 km"), FMath::IsNearlyEqual(MaxR, double(Outer), 1.0));
		TestTrue(TEXT("Curvature within 3 cm of the true drop everywhere"), WorstErr < 0.03);
		TestTrue(TEXT("Under 25,000 vertices (the five rings have 83,000)"), Verts.Num() < 25000);
	}
	// What the old far plane did: one quad 40 km across, its centre 27 m above the true drop at 20 km.
	TestTrue(TEXT("The single 40 km quad was metres out (for the record)"), FMath::Abs(Drop(FVector2D(20000.0, 20000.0)) / 2.0 - Drop(FVector2D(0.0, 0.0))) > 10.0);
	return true;
}
