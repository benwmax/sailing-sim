#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "WakeGrid.h"
#include "WaterSurface.h"
#include "WaveDetail.h"
#include "Waves.h"
#include <random>

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
			Out.J *= J;
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

		std::mt19937 Rng(7);
		std::uniform_real_distribution<double> U(-400.0, 400.0);
		double ExactErr = 0.0, LongDiff2 = 0.0, Diff2 = 0.0, Phys2 = 0.0, Drawn2 = 0.0, LongVar = 0.0;
		int32 Count = 0;
		for (const double T : { 10.0, 37.3, 81.9 })
		{
			FWaveDetail::FGrid Grid;
			Detail.Evaluate(0, T, Grid);
			for (int32 I = 0; I < 1500; ++I)
			{
				const double X = U(Rng), Y = U(Rng);
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
 * Whitecaps from the drawn waves: the share of the surface where the crests fold (the Jacobian under the material's
 * FoamThreshold) against Monahan's whitecap coverage law W = 3.84e-6 U^3.41 (U at 10 m, m/s). The Beaufort scale is
 * the check: almost none at 6 kn, within a factor of three of the law from 10 kn up. W0: the material moves the
 * threshold by the local wind against the mean and by the water body (AWaterSurface::WhitecapThreshold): the lake gets
 * 0.4 of the law and the bay 0.7 at the mean wind, and a puff of 1.3x the mean caps more than the mean, a lull of 0.7x less.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWaterWhitecapsTest, "SailingSim.Visual.Whitecaps", WaterFlags)
bool FWaterWhitecapsTest::RunTest(const FString&)
{
	constexpr double Threshold = AWaterSurface::FoamThreshold;
	const float Lake = AWaterSurface::WhitecapScaleFor(0), Bay = AWaterSurface::WhitecapScaleFor(1), Sea = AWaterSurface::WhitecapScaleFor(2);
	TestTrue(TEXT("The Gulf keeps the sea's law"), Sea == 1.f);
	TestTrue(TEXT("At the mean wind the sea's threshold is the calibrated one"), FMath::IsNearlyEqual(AWaterSurface::WhitecapThreshold(1.f, Sea), float(Threshold)));
	for (const double Knots : { 6.0, 10.0, 14.0, 20.0, 25.0 })
	{
		FWaveField Waves(1);
		FWaveParams WP;
		WP.WindSpeedKnots = Knots;
		WP.FetchMeters = 8000.0;
		Waves.SetWind(WP);
		Waves.SnapToTarget();
		FWaveDetail Detail;
		Detail.Configure(DetailFor(Knots, WP.FetchMeters, WP.WindFromDegrees), { FWaveDetail::ChopCascade() });
		std::mt19937 Rng(11);
		std::uniform_real_distribution<double> U(0.0, 300.0);
		TArray<double> Js;
		for (const double T : { 5.0, 23.0, 61.0, 97.0 })
		{
			FWaveDetail::FGrid Grid;
			Detail.Evaluate(0, T, Grid);
			for (int32 I = 0; I < 10000; ++I)
			{
				Js.Add(RenderedVertex(Waves, &Grid, U(Rng), U(Rng), T, AWaterSurface::Choppiness).J);
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
