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

/**
 * Feedback #20: the spinnaker's head on its halyard. The physics strips put a spinnaker's luff a metre or two ahead of the
 * mast (the J/22's head at x 2.6 m, her mast at 0.65), and the cloth drew the head there, floating short of the mast.
 * On every boat that carries one: the head point is just ahead of the mast's front (the J/22 hero's Hounds socket,
 * J22H_sockets.json, or the config's mast), at the sail's own head height or over the jib's head, under the masthead.
 * Set and flown both sides, drawn and simulated, the head corner sits on it and comes to a point, the tack stays where the
 * physics puts it, and the luff stays ahead of the jib's below the jib's head; drawn, no edge of the spinnaker's cloth
 * passes through the jib's (the first try at this fix drew the J/22's luff aft through the jib's upper cloth).
 */
namespace
{
	// Moller-Trumbore: does the segment P0-P1 cross the triangle (inside both)?
	bool SegmentCrossesTriangle(const FVector& P0, const FVector& P1, const FVector& A, const FVector& B, const FVector& C)
	{
		const FVector E1 = B - A, E2 = C - A, D = P1 - P0;
		const FVector H = FVector::CrossProduct(D, E2);
		const double Det = FVector::DotProduct(E1, H);
		if (FMath::Abs(Det) < 1e-9) return false;
		const double F = 1.0 / Det;
		const FVector Sv = P0 - A;
		const double U = F * FVector::DotProduct(Sv, H);
		if (U < 0.0 || U > 1.0) return false;
		const FVector Q = FVector::CrossProduct(Sv, E1);
		const double V = F * FVector::DotProduct(D, Q);
		if (V < 0.0 || U + V > 1.0) return false;
		const double W = F * FVector::DotProduct(E2, Q);
		return W > 0.0 && W < 1.0;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualSpinnakerHeadTest, "SailingSim.Visual.SpinnakerHead", SailClothFlags)
bool FVisualSpinnakerHeadTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	const FVector HeroHounds(68.06, 0.0, 783.09);   // Inputs/j22-hero/J22H_sockets.json, boat frame cm
	constexpr int32 Rows = FSailCloth::Rows, Cols = FSailCloth::Cols;
	int32 Boats = 0;
	for (int32 B = 0; B < int32(EBoatType::Count); ++B)
	{
		const FBoatConfig C = FBoatConfig::Make(EBoatType(B));
		if (!C.HasSpinnaker()) continue;
		++Boats;
		const FString BoatName = ANSI_TO_TCHAR(BoatTypeName(C.Type));
		const double MastFrontCm = (C.MastX + 0.5 * C.MastDiameter) * CmPerMeter;
		const double SailHeadCm = C.Spinnaker.Strips[C.Spinnaker.NumStrips - 1].ZTop * CmPerMeter;
		const double JibHeadCm = C.HasJib() ? C.Jib.Strips[C.Jib.NumStrips - 1].ZTop * CmPerMeter : -1.0;
		struct FCase { const TCHAR* What; FVector Head; bool bHero; };
		TArray<FCase> Cases;
		Cases.Add({ TEXT("no model"), SpinnakerHeadCm(C, nullptr), false });
		if (C.Type == EBoatType::J22) Cases.Add({ TEXT("hero Hounds"), SpinnakerHeadCm(C, &HeroHounds), true });
		// A model whose socket is on the mast's centre line (the maxi's): the head still outside the mast.
		const FVector OnCentre(C.MastX * CmPerMeter, 0.0, SailHeadCm);
		Cases.Add({ TEXT("socket on the mast's centre"), SpinnakerHeadCm(C, &OnCentre), false });

		// The halyard point: at the mast, not where the physics put the head; high enough; under the masthead.
		for (const FCase& K : Cases)
		{
			const FString What = FString::Printf(TEXT("%s (%s)"), *BoatName, K.What);
			const double Front = K.bHero ? FMath::Max(HeroHounds.X, MastFrontCm) : MastFrontCm;
			TestTrue(FString::Printf(TEXT("%s: the head just ahead of the mast's front, x %.0f cm (front %.0f)"), *What, K.Head.X, Front),
				K.Head.X > Front && K.Head.X <= Front + 10.0);
			TestEqual(FString::Printf(TEXT("%s: the head on the centreline"), *What), K.Head.Y, 0.0, 0.01);
			TestTrue(FString::Printf(TEXT("%s: the head at least at the sail's own head height (%.0f cm, sail %.0f)"), *What, K.Head.Z, SailHeadCm), K.Head.Z >= SailHeadCm - 0.5);
			TestTrue(FString::Printf(TEXT("%s: the head under the masthead (%.0f cm)"), *What, K.Head.Z), K.Head.Z < C.MastheadZ * CmPerMeter);
			if (C.HasJib() && K.Head.Z < C.MastheadZ * CmPerMeter - 10.5)
			{
				TestTrue(FString::Printf(TEXT("%s: the head over the jib's (%.0f cm, jib %.0f)"), *What, K.Head.Z, JibHeadCm), K.Head.Z >= JibHeadCm + 15.0);
			}
		}

		// The jib's luff as its cloth draws it (FSailCloth::Init's luff line), cm.
		auto JibLuffXCm = [&C](double ZCm)
		{
			const FSailGeometry& J = C.Jib;
			const double Z0 = 0.5 * (J.Strips[0].ZBottom + J.Strips[0].ZTop);
			const double Slope = J.NumStrips > 1 ? (J.Strips[J.NumStrips - 1].LuffX - J.Strips[0].LuffX) / (0.5 * (J.Strips[J.NumStrips - 1].ZBottom + J.Strips[J.NumStrips - 1].ZTop) - Z0) : 0.0;
			return (J.Strips[0].LuffX + Slope * (ZCm / CmPerMeter - Z0)) * CmPerMeter;
		};

		FSailCloth Free;
		Free.Init(C.Spinnaker, ESailKind::Spinnaker);
		TestFalse(FString::Printf(TEXT("%s: Init leaves no head point"), *BoatName), Free.HasHeadPoint());
		FSailStripState Strips[kMaxSailStrips], JibStrips[kMaxSailStrips];
		for (const FCase& K : Cases)
		{
			for (const int32 Side : { 1, -1 })
			{
				for (const bool bSimulate : { false, true })
				{
					FSailCloth Cloth;
					Cloth.Init(C.Spinnaker, ESailKind::Spinnaker);
					Cloth.SetHeadPoint(K.Head, C.HasJib() ? &C.Jib : nullptr);
					TestTrue(FString::Printf(TEXT("%s: the head point is taken"), *BoatName), Cloth.HasHeadPoint());
					FSailClothDrive Drive;
					Drive.ApparentWindKnots = 14.f;
					Drive.bSimulate = bSimulate;
					const int32 Steps = bSimulate ? 180 : 1;
					for (int32 N = 0; N < Steps; ++N)
					{
						for (int32 I = 0; I < C.Spinnaker.NumStrips; ++I)
						{
							Strips[I].Camber = 0.20;
							Strips[I].AngleFromCenterline = Side * (55.0 + 6.0 * I) * kDegToRad;   // signed: + = starboard (Sail.h)
							// A blown spinnaker too: the top strips collapse half the time.
							Strips[I].Flow = (N / 30) % 2 == 1 && I >= C.Spinnaker.NumStrips - 2 ? ESailFlow::Luffing : ESailFlow::Attached;
						}
						Drive.Time = N / 60.f;
						Cloth.Step(Strips, Side, Drive);
						if (N == 0) Free.Step(Strips, Side, Drive);
					}
					const TArray<FVector>& P = Cloth.Positions();
					const int32 HeadLuff = (Rows - 1) * Cols, HeadLeech = HeadLuff + Cols - 1;
					const FString Case = FString::Printf(TEXT("%s (%s, side %d, %s)"), *BoatName, K.What, Side, bSimulate ? TEXT("cloth") : TEXT("drawn"));
					bool bFinite = true;
					for (const FVector& V : P) bFinite &= !V.ContainsNaN();
					TestTrue(Case + TEXT(": the cloth is finite"), bFinite);
					TestTrue(FString::Printf(TEXT("%s: the head on the halyard point (%.1f cm off)"), *Case, FVector::Dist(P[HeadLuff], K.Head)),
						FVector::Dist(P[HeadLuff], K.Head) < 1.0);
					TestTrue(FString::Printf(TEXT("%s: the head comes to a point (leech %.1f cm from it)"), *Case, FVector::Dist(P[HeadLeech], K.Head)),
						FVector::Dist(P[HeadLeech], K.Head) < 10.0);
					TestTrue(FString::Printf(TEXT("%s: the tack where the physics puts it (%.1f cm off)"), *Case, FVector::Dist(P[0], Free.Positions()[0])),
						FVector::Dist(P[0], Free.Positions()[0]) < 1.0);
					double Highest = -1e9;
					for (const FVector& V : P) Highest = FMath::Max(Highest, V.Z);
					TestTrue(FString::Printf(TEXT("%s: nothing above the head (%.1f cm over)"), *Case, Highest - K.Head.Z), Highest <= K.Head.Z + 5.0);
					// The luff (column 0, held to its target) ahead of the jib's below the jib's head.
					if (C.HasJib())
					{
						double Worst = 1e9, WorstZ = 0.0;
						for (int32 R = 0; R < Rows - 1; ++R)
						{
							const FVector& L = P[R * Cols];
							if (L.Z > JibHeadCm || L.Z < C.Jib.Strips[0].ZBottom * CmPerMeter) continue;
							const double Ahead = L.X - JibLuffXCm(L.Z);
							if (Ahead < Worst) { Worst = Ahead; WorstZ = L.Z; }
						}
						TestTrue(FString::Printf(TEXT("%s: the luff ahead of the jib's (worst %.1f cm at %.0f cm up)"), *Case, Worst, WorstZ), Worst >= 10.0);
					}
				}
			}
		}

		// Drawn beside the jib on a reach and a run: no edge of the spinnaker's cloth through the jib's.
		if (C.HasJib())
		{
			struct FTrim { double Jib, Spin; };
			for (const FCase& K : Cases)
			for (const FTrim Trim : { FTrim{ 45.0, 70.0 }, FTrim{ 80.0, 60.0 }, FTrim{ 30.0, 20.0 } })
			{
				for (const int32 Side : { 1, -1 })
				{
					for (int32 I = 0; I < C.Jib.NumStrips; ++I)
					{
						JibStrips[I].Camber = 0.13;
						JibStrips[I].AngleFromCenterline = Side * (Trim.Jib + 3.0 * I) * kDegToRad;
						JibStrips[I].Flow = ESailFlow::Attached;
					}
					for (int32 I = 0; I < C.Spinnaker.NumStrips; ++I)
					{
						Strips[I].Camber = 0.20;
						Strips[I].AngleFromCenterline = Side * (Trim.Spin + 6.0 * I) * kDegToRad;
						Strips[I].Flow = ESailFlow::Attached;
					}
					FSailClothDrive Drawn;
					Drawn.bSimulate = false;
					FSailCloth Jib, Spin;
					Jib.Init(C.Jib, ESailKind::Jib);
					Jib.Step(JibStrips, Side, Drawn);
					Spin.Init(C.Spinnaker, ESailKind::Spinnaker);
					Spin.SetHeadPoint(K.Head, &C.Jib);
					Spin.Step(Strips, Side, Drawn);
					const TArray<FVector>& J = Jib.Positions();
					const TArray<FVector>& S = Spin.Positions();
					int32 Crossings = 0;
					FVector First = FVector::ZeroVector;
					for (int32 R = 0; R < Rows; ++R)
					{
						for (int32 Col = 0; Col < Cols; ++Col)
						{
							for (const FIntPoint Dir : { FIntPoint(1, 0), FIntPoint(0, 1) })
							{
								if (R + Dir.X >= Rows || Col + Dir.Y >= Cols) continue;
								const FVector& P0 = S[R * Cols + Col];
								const FVector& P1 = S[(R + Dir.X) * Cols + Col + Dir.Y];
								bool bHit = false;
								for (int32 JR = 0; JR + 1 < Rows && !bHit; ++JR)
								{
									for (int32 JC = 0; JC + 1 < Cols && !bHit; ++JC)
									{
										const FVector& A = J[JR * Cols + JC];
										const FVector& Up = J[(JR + 1) * Cols + JC];
										const FVector& Aft = J[JR * Cols + JC + 1];
										const FVector& Far = J[(JR + 1) * Cols + JC + 1];
										bHit = SegmentCrossesTriangle(P0, P1, A, Up, Aft) || SegmentCrossesTriangle(P0, P1, Up, Far, Aft);
									}
								}
								if (bHit && Crossings++ == 0) First = P0;
							}
						}
					}
					TestEqual(FString::Printf(TEXT("%s (%s): jib %.0f, spinnaker %.0f deg, side %d: spinnaker edges through the jib (first at %s)"),
						*BoatName, K.What, Trim.Jib, Trim.Spin, Side, *First.ToString()), Crossings, 0);
				}
			}
		}
	}
	TestTrue(TEXT("Some boats carry a spinnaker"), Boats >= 3);
	return true;
}

#endif
