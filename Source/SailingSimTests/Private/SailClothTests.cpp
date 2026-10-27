#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "SailCloth.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags SailClothFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
}

/**
 * docs/sails-1/: the cloth in a seaway. Reaching in a swell the masthead's apparent wind swings with every roll and the
 * upper strips flicker between drawing and luffing; in a breeze the leech flutters. The cloth may flog, but it must not
 * crease at every vertex (the head of the main went to jagged, torn-looking folds) or zigzag row by row along the leech
 * (the jib's dark leech creases) where it draws. The fold is the sharpest angle between neighbouring vertex normals; the zigzag the
 * leech's second difference across the view, row to row.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualSailClothSeawayTest, "SailingSim.Visual.SailClothSeaway", SailClothFlags)
bool FVisualSailClothSeawayTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	const FBoatConfig C = FBoatConfig::J22();
	for (const ESailKind Kind : { ESailKind::Main, ESailKind::Jib })
	{
		const FSailGeometry& Geo = Kind == ESailKind::Main ? C.Main : C.Jib;
		FSailCloth Cloth;
		Cloth.Init(Geo, Kind);
		FSailStripState Strips[kMaxSailStrips];
		FSailClothDrive Drive;
		Drive.ApparentWindKnots = 18.f;
		Drive.Cunningham = 0.f;
		double WorstFoldDeg = 0.0, MeanFoldDeg = 0.0, WorstZigzagCm = 0.0;
		int32 WorstR = 0, WorstC = 0, ZigR = 0;
		TArray<double> RowFold;
		RowFold.Init(0.0, FSailCloth::Rows);
		int32 Samples = 0;
		TArray<FVector> N, Target;
		const int32 Steps = 600;
		for (int32 K = 0; K < Steps; ++K)
		{
			const float T = K / 60.f;
			// The top two strips luff for 0.35 s in every 0.7 s (the roll), the rest draw; the sail is eased (reaching).
			const bool bLuff = FMath::Fmod(T, 0.7f) < 0.35f;
			for (int32 I = 0; I < Geo.NumStrips; ++I)
			{
				Strips[I].Camber = 0.11 + 0.02 * I;
				Strips[I].AngleFromCenterline = (30.0 + 5.0 * I) * kDegToRad;
				Strips[I].Flow = bLuff && I >= Geo.NumStrips - 2 ? ESailFlow::Luffing : ESailFlow::Attached;
			}
			Drive.Time = T;
			Cloth.Step(Strips, 1, Drive);
			if (K < 120) continue;   // after two seconds of settling
			const TArray<FVector>& P = Cloth.Positions();
			Cloth.ComputeNormals(N);
			double Fold = 0.0, Sum = 0.0;
			int32 Pairs = 0;
			for (int32 R = 1; R + 1 < FSailCloth::Rows; ++R)
			{
				for (int32 Col = 1; Col + 1 < FSailCloth::Cols; ++Col)
				{
					const FVector& A = N[R * FSailCloth::Cols + Col];
					for (const int32 J : { R * FSailCloth::Cols + Col + 1, (R + 1) * FSailCloth::Cols + Col })
					{
						const double Deg = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(A, N[J]), -1.0, 1.0)));
						if (Deg > Fold) { Fold = Deg; if (Deg > WorstFoldDeg) { WorstR = R; WorstC = Col; } }
						RowFold[R] = FMath::Max(RowFold[R], Deg);
						Sum += Deg;
						++Pairs;
					}
				}
			}
			WorstFoldDeg = FMath::Max(WorstFoldDeg, Fold);
			MeanFoldDeg += Sum / FMath::Max(Pairs, 1);
			++Samples;
			// The leech (last column): the row-to-row second difference of its position off the luff-to-leech plane.
			// Only where the sail draws (the lower three strips: rows under 55% of the height; a flogging leech whips), and
			// off the target shape (the planform's own curve is not a crease).
			Cloth.ComputeTarget(Strips, 1, Target);
			auto Off = [&](int32 R) { const int32 I = R * FSailCloth::Cols + FSailCloth::Cols - 1; return P[I] - Target[I]; };
			for (int32 R = 1; R + 1 < FSailCloth::Rows * 55 / 100; ++R)
			{
				const FVector L0 = Off(R - 1), L1 = Off(R), L2 = Off(R + 1);
				const double Z = (L0 + L2 - 2.0 * L1).Size();
				if (Z > WorstZigzagCm) { WorstZigzagCm = Z; ZigR = R; }
			}
		}
		MeanFoldDeg /= FMath::Max(Samples, 1);
		const TCHAR* Name = Kind == ESailKind::Main ? TEXT("Main") : TEXT("Jib");
		FString Rows;
		for (int32 R = 0; R < FSailCloth::Rows; ++R) Rows += FString::Printf(TEXT(" %.0f"), RowFold[R]);
		AddInfo(FString::Printf(TEXT("%s: sharpest fold %.1f deg (row %d col %d), mean %.2f deg, leech zigzag %.1f cm (row %d); worst per row:%s"),
			Name, WorstFoldDeg, WorstR, WorstC, MeanFoldDeg, WorstZigzagCm, ZigR, *Rows));
		TestTrue(FString::Printf(TEXT("%s: no fold sharper than 45 deg between neighbours (%.1f)"), Name, WorstFoldDeg), WorstFoldDeg < 45.0);
		TestTrue(FString::Printf(TEXT("%s: mean fold under 6 deg (%.2f)"), Name, MeanFoldDeg), MeanFoldDeg < 6.0);
		TestTrue(FString::Printf(TEXT("%s: drawing leech zigzag under 3 cm (%.1f)"), Name, WorstZigzagCm), WorstZigzagCm < 3.0);
	}
	return true;
}

/**
 * docs/sail-dent/: the main keeps clear of the rig only where it is pressed on it. A J/22-like rig (spreaders 75 cm a side,
 * swept 10 cm aft, at 55% of the luff; shrouds from chainplates 100 cm out and 15 cm aft over the spreader tips to the
 * hounds at 80%) and the main's target shape: close-hauled (TWA 45, boom about 10 deg) and reaching (TWA 90, about 35 deg)
 * it is the undented shape within 1 cm; running (TWA 158, about 80 deg) it is turned and dented, only on its own (the
 * leeward) side, and on the other gybe the same dent mirrored.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualSailDentTest, "SailingSim.Visual.SailDent", SailClothFlags)
bool FVisualSailDentTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	const FBoatConfig C = FBoatConfig::J22();
	const FSailGeometry& Geo = C.Main;
	FSailCloth Raw;
	Raw.Init(Geo, ESailKind::Main);
	FSailStripState Strips[kMaxSailStrips];
	// (The strips' angle carries the gybe's sign, as the physics gives it: negative with the sail to port.)
	auto Trim = [&](double BoomDeg, int32 Side = 1)
	{
		for (int32 I = 0; I < Geo.NumStrips; ++I)
		{
			Strips[I].Camber = 0.10;
			Strips[I].AngleFromCenterline = Side * (BoomDeg + 3.0 * I) * kDegToRad;
			Strips[I].Flow = ESailFlow::Attached;
		}
	};
	// The rig from the main's own luff (boat frame, cm).
	Trim(10.0);
	TArray<FVector> Shape;
	Raw.ComputeTarget(Strips, 1, Shape);
	const FVector Foot = Shape[0], Head = Shape[(FSailCloth::Rows - 1) * FSailCloth::Cols];
	const double Luff = Head.Z - Foot.Z;
	TArray<FSailObstacle> Rig;
	for (const double S : { 1.0, -1.0 })
	{
		const FVector Root(Foot.X + 5.0, 0.0, Foot.Z + 0.55 * Luff), Tip(Foot.X - 10.0, 75.0 * S, Foot.Z + 0.55 * Luff);
		const FVector Chain(Foot.X - 15.0, 100.0 * S, Foot.Z - 80.0), Hounds(Foot.X + 5.0, 0.0, Foot.Z + 0.8 * Luff);
		Rig.Add({ Root, Tip, 1.5f, 0.f, 0.f });
		Rig.Add({ Chain, Tip, 0.4f, 12.f, 0.f });
		Rig.Add({ Tip, Hounds, 0.4f, 0.f, 12.f });
	}
	FSailClothDrive Drive;
	Drive.ApparentWindKnots = 8.f;
	Drive.bSimulate = false;
	auto Kept = [&](double BoomDeg, int32 Side, TArray<FVector>& OutRaw)
	{
		Trim(BoomDeg, Side);
		FSailCloth Cloth;
		Cloth.Init(Geo, ESailKind::Main);
		Cloth.SetObstacles(Rig);
		Cloth.Step(Strips, Side, Drive);
		Raw.ComputeTarget(Strips, Side, OutRaw);
		return Cloth.Positions();
	};
	for (const double Boom : { 10.0, 35.0 })
	{
		TArray<FVector> Free;
		const TArray<FVector> P = Kept(Boom, 1, Free);
		double Most = 0.0;
		for (int32 I = 0; I < P.Num(); ++I) Most = FMath::Max(Most, double(FVector::Dist(P[I], Free[I])));
		AddInfo(FString::Printf(TEXT("Boom %.0f deg: the main within %.2f cm of its undented shape"), Boom, Most));
		TestTrue(FString::Printf(TEXT("Boom %.0f deg: no dent (%.2f cm)"), Boom, Most), Most < 1.0);
	}
	TArray<FVector> FreeS, FreeP;
	const TArray<FVector> S = Kept(80.0, 1, FreeS), Pt = Kept(80.0, -1, FreeP);
	double Most = 0.0, Mirror = 0.0;
	int32 WrongSide = 0;
	for (int32 I = 0; I < S.Num(); ++I)
	{
		const FVector D = S[I] - FreeS[I];
		Most = FMath::Max(Most, double(D.Size()));
		if (D.Size() > 1.0 && S[I].Y < -1.0) ++WrongSide;
		if ((Pt[I] - FreeP[I]).Size() > 1.0 && Pt[I].Y > 1.0) ++WrongSide;
		// The dent itself (kept against undented) on the other gybe, mirrored across the centreline.
		const FVector Dp = Pt[I] - FreeP[I];
		Mirror = FMath::Max(Mirror, double(FVector::Dist(D, FVector(Dp.X, -Dp.Y, Dp.Z))));
	}
	AddInfo(FString::Printf(TEXT("Boom 80 deg (running): moved %.1f cm at most, %d points moved on the windward side, the other gybe mirrors within %.2f cm"),
		Most, WrongSide, Mirror));
	TestTrue(TEXT("Running, the main is kept off the rig"), Most > 5.0);
	TestTrue(TEXT("... only on its own side (the leeward spreader and shroud)"), WrongSide == 0);
	TestTrue(TEXT("... and on the other gybe the same dent, mirrored"), Mirror < 1.0);
	return true;
}

#endif
