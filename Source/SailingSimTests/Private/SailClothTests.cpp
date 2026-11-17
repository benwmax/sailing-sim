#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "SailCloth.h"
#include "SailingSim.h"
#include <limits>

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
		if (IsSquareRigged(EBoatType(B))) continue; // The frigate's square rig, crew and cameras come with the frigate wiring (IsSquareRigged).
		const FBoatConfig C = FBoatConfig::Make(EBoatType(B));
		if (!C.HasSpinnaker()) continue;
		++Boats;
		const FString BoatName = ANSI_TO_TCHAR(BoatTypeName(C.Type));
		const double MastFrontCm = (C.MastX + 0.5 * C.MastDiameter) * CmPerMeter;
		const double SailHeadCm = C.Spinnaker.Strips[C.Spinnaker.NumStrips - 1].ZTop * CmPerMeter;
		// The jib as its cloth draws it: the planform's, and (the hero J/22) its head at the forestay's top.
		FSailCloth PlanJib, HeroJib;
		if (C.HasJib())
		{
			PlanJib.Init(C.Jib, ESailKind::Jib);
			HeroJib.Init(C.Jib, ESailKind::Jib);
			FVector JibHead;
			if (C.Type == EBoatType::J22 && JibHeadCm(C, HeroHounds, JibHead)) HeroJib.SetHeadPoint(JibHead);
		}
		struct FCase { const TCHAR* What; FVector Head; bool bHero; const FSailCloth* Jib; };
		TArray<FCase> Cases;
		const FSailCloth* Plan = C.HasJib() ? &PlanJib : nullptr;
		Cases.Add({ TEXT("no model"), SpinnakerHeadCm(C, nullptr, Plan), false, Plan });
		Cases.Add({ TEXT("no model, no jib cloth"), SpinnakerHeadCm(C, nullptr), false, Plan });
		if (C.Type == EBoatType::J22) Cases.Add({ TEXT("hero Hounds"), SpinnakerHeadCm(C, &HeroHounds, &HeroJib), true, &HeroJib });
		// A model whose socket is on the mast's centre line (the maxi's): the head still outside the mast.
		const FVector OnCentre(C.MastX * CmPerMeter, 0.0, SailHeadCm);
		Cases.Add({ TEXT("socket on the mast's centre"), SpinnakerHeadCm(C, &OnCentre, Plan), false, Plan });

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
			if (K.Jib && K.Head.Z < C.MastheadZ * CmPerMeter - 10.5)
			{
				const double JibTopCm = K.Jib->TopZ() * CmPerMeter;
				TestTrue(FString::Printf(TEXT("%s: the head over the jib's (%.0f cm, jib %.0f)"), *What, K.Head.Z, JibTopCm), K.Head.Z >= JibTopCm + 15.0);
			}
		}

		// The jib's luff as its cloth draws it, cm.
		auto JibLuffXCm = [](const FSailCloth& J, double ZCm) { return J.LuffXAt(ZCm / CmPerMeter, 0) * CmPerMeter; };

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
					Cloth.SetHeadPoint(K.Head, K.Jib);
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
					if (K.Jib)
					{
						double Worst = 1e9, WorstZ = 0.0;
						for (int32 R = 0; R < Rows - 1; ++R)
						{
							const FVector& L = P[R * Cols];
							if (L.Z > K.Jib->TopZ() * CmPerMeter || L.Z < K.Jib->FootZ() * CmPerMeter) continue;
							const double Ahead = L.X - JibLuffXCm(*K.Jib, L.Z);
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
					FVector JibHead;
					if (K.bHero && JibHeadCm(C, HeroHounds, JibHead)) Jib.SetHeadPoint(JibHead);
					Jib.Step(JibStrips, Side, Drawn);
					Spin.Init(C.Spinnaker, ESailKind::Spinnaker);
					Spin.SetHeadPoint(K.Head, &Jib);
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

/**
 * Feedback #25: a J/22 tester on a light-air run (4 kn, TWA -162) saw the spinnaker hang far out ahead off the starboard
 * side, connected to nothing: drawn from the physics' luff on the centreline and turned out by its chord angle, its 6.9 m
 * foot put the clew 5 m and more out over the water. A poled spinnaker is drawn between its corners now (SpinnakerRigCm,
 * FSailCloth::SetCorners): the tack on the pole's end, a J from the mast, to windward; the clew to leeward within reach of
 * its sheet; the whole sail near the boat. Every boat with a symmetric spinnaker, both sides, from a reach to dead downwind,
 * trimmed and eased, drawn (Low) and as cloth with its top collapsing; gennakers get no pole.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualSpinnakerClewTest, "SailingSim.Visual.SpinnakerClew", SailClothFlags)
bool FVisualSpinnakerClewTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	using namespace SpinnakerRigLimits;
	constexpr int32 Rows = FSailCloth::Rows, Cols = FSailCloth::Cols;
	int32 Poled = 0, Gennakers = 0;
	for (int32 B = 0; B < int32(EBoatType::Count); ++B)
	{
		if (IsSquareRigged(EBoatType(B))) continue; // The frigate's square rig, crew and cameras come with the frigate wiring (IsSquareRigged).
		const FBoatConfig C = FBoatConfig::Make(EBoatType(B));
		if (!C.HasSpinnaker()) continue;
		const FString BoatName = ANSI_TO_TCHAR(BoatTypeName(C.Type));
		if (C.bAsymmetricSpinnaker)
		{
			++Gennakers;
			TestFalse(FString::Printf(TEXT("%s: a gennaker has no pole"), *BoatName), SpinnakerRigCm(C, 1, PI, 0.5, 0.0).bValid);
			continue;
		}
		++Poled;
		const FHullShape& H = C.Hulls[0];
		const double MastFront = C.MastX + 0.5 * C.MastDiameter;
		const double JibTack = C.HasJib() ? (C.Jib.NumStrips > 1 ? C.Jib.Strips[0].LuffX - 0.5 * (C.Jib.Strips[1].LuffX - C.Jib.Strips[0].LuffX) : C.Jib.Strips[0].LuffX) : MastFront + 1.0;
		const double JCm = (JibTack - MastFront) * CmPerMeter;
		const double RailOutCm = (H.MaxHalfBeam + ClewOutboardM) * CmPerMeter;
		FSailCloth PlanJib;
		if (C.HasJib()) PlanJib.Init(C.Jib, ESailKind::Jib);
		const FSailCloth* Jib = C.HasJib() ? &PlanJib : nullptr;
		const FVector Head = SpinnakerHeadCm(C, nullptr, Jib);
		FSailCloth Probe;
		Probe.Init(C.Spinnaker, ESailKind::Spinnaker);
		TestFalse(FString::Printf(TEXT("%s: Init leaves no corners"), *BoatName), Probe.HasCorners());
		FSailStripState Strips[kMaxSailStrips];
		// The apparent wind from a beam reach to dead downwind (the repro's run: about 160 deg at the masthead).
		for (const double AwaDeg : { 90.0, 110.0, 135.0, 150.0, 162.0, 175.0, 180.0 })
		{
			for (const int32 Side : { 1, -1 })
			{
				for (const double Ease : { 0.0, 0.5, 1.0 })
				{
					// The wind from the side away from the sail (Sail.h: AWA + = from starboard; the sail lies to leeward).
					const double Awa = -Side * AwaDeg * kDegToRad;
					const FSpinnakerRig Rig = SpinnakerRigCm(C, Side, Awa, Ease, Probe.FootChord());
					const FString Case = FString::Printf(TEXT("%s (AWA %.0f, side %d, sheet %.1f)"), *BoatName, AwaDeg, Side, Ease);
					if (!TestTrue(Case + TEXT(": a poled spinnaker has a rig"), Rig.bValid)) continue;
					// The pole: from the mast's front, a J long, level, to windward, between the forestay and squared back.
					const double PoleLen = FVector::Dist(Rig.PoleHeel, Rig.Tack);
					TestTrue(FString::Printf(TEXT("%s: the pole a J long (%.1f cm, J %.1f)"), *Case, PoleLen, JCm), FMath::Abs(PoleLen - JCm) < 1.0);
					TestTrue(FString::Printf(TEXT("%s: the pole's heel on the mast's front (x %.1f)"), *Case, Rig.PoleHeel.X), FMath::Abs(Rig.PoleHeel.X - MastFront * CmPerMeter) < 6.0 && FMath::Abs(Rig.PoleHeel.Y) < 0.5);
					TestTrue(FString::Printf(TEXT("%s: the pole to windward (tack y %.0f)"), *Case, Rig.Tack.Y), Rig.Tack.Y * Side < 0.0);
					TestTrue(FString::Printf(TEXT("%s: the pole's angle %.0f deg"), *Case, Rig.PoleDeg), Rig.PoleDeg >= PoleMinDeg - 1e-6 && Rig.PoleDeg <= PoleMaxDeg + 1e-6);
					TestTrue(FString::Printf(TEXT("%s: the pole over the deck (%.0f cm up, sheer %.0f)"), *Case, Rig.Tack.Z, H.SheerHeight(C.MastX) * CmPerMeter), Rig.Tack.Z > H.SheerHeight(C.MastX) * CmPerMeter + 50.0);
					// The clew: to leeward, within reach of its sheet, ahead of the main, not ahead of the bow, the foot no longer
					// than the class allows.
					const double ClewOut = Side * (Rig.Clew.Y - H.CenterY * CmPerMeter);
					TestTrue(FString::Printf(TEXT("%s: the clew to leeward (%.0f cm)"), *Case, ClewOut), ClewOut > H.MaxHalfBeam * CmPerMeter * 0.5);
					TestTrue(FString::Printf(TEXT("%s: the clew at most %.1f m outside the rail (%.0f cm from the centreline)"), *Case, ClewOutboardM, ClewOut), ClewOut <= RailOutCm + 0.5);
					TestTrue(FString::Printf(TEXT("%s: the clew ahead of the main and not past the bow (x %.0f)"), *Case, Rig.Clew.X),
						Rig.Clew.X >= (C.MastX + ClewAheadOfMastM) * CmPerMeter - 0.5 && Rig.Clew.X <= H.BowX * CmPerMeter + 0.5);
					TestTrue(FString::Printf(TEXT("%s: the foot within the class's (%.0f cm, J %.0f)"), *Case, FVector::Dist(Rig.Tack, Rig.Clew), JCm),
						FVector::Dist(Rig.Tack, Rig.Clew) <= FootPerJ * JCm + 1.0);
					// The gear: the guy's twing to windward, the sheet's quarter block to leeward and aft, on the deck.
					TestTrue(Case + TEXT(": the twing block to windward"), Rig.GuyBlock.Y * Side < 0.0 && Rig.GuyCleat.Y * Side < 0.0);
					TestTrue(Case + TEXT(": the quarter block to leeward, aft"), Rig.SheetBlock.Y * Side > 0.0 && Rig.SheetCleat.Y * Side > 0.0 && Rig.SheetBlock.X < Rig.SheetCleat.X);
					TestTrue(Case + TEXT(": the gear inside the deck's edge"), FMath::Abs(Rig.GuyBlock.Y) < H.DeckHalfBeam(Rig.GuyBlock.X / CmPerMeter) * CmPerMeter
						&& FMath::Abs(Rig.SheetBlock.Y) < H.DeckHalfBeam(Rig.SheetBlock.X / CmPerMeter) * CmPerMeter);

					// The sail between its corners, drawn and as cloth: the tack and clew pinned there, the head on its halyard,
					// nothing far out over the water or out ahead.
					for (const bool bSimulate : { false, true })
					{
						FSailCloth Cloth;
						Cloth.Init(C.Spinnaker, ESailKind::Spinnaker);
						Cloth.SetHeadPoint(Head, Jib);
						Cloth.SetCorners(Rig.Tack, Rig.Clew);
						if (!TestTrue(Case + TEXT(": the corners are taken"), Cloth.HasCorners())) continue;
						FSailClothDrive Drive;
						Drive.ApparentWindKnots = 4.f;   // the repro's light air
						Drive.bSimulate = bSimulate;
						const int32 Steps = bSimulate ? 180 : 1;
						for (int32 N = 0; N < Steps; ++N)
						{
							for (int32 I = 0; I < C.Spinnaker.NumStrips; ++I)
							{
								Strips[I].Camber = 0.20;
								// The physics' chord angle on a run (SpinTarget, capped at 97 deg): what had swung the clew out.
								Strips[I].AngleFromCenterline = Side * FMath::Min(AwaDeg - 10.0 + 6.0 * I, 97.0) * kDegToRad;
								Strips[I].Flow = bSimulate && (N / 30) % 2 == 1 && I >= C.Spinnaker.NumStrips - 2 ? ESailFlow::Luffing : ESailFlow::Attached;
							}
							Drive.Time = N / 60.f;
							Cloth.Step(Strips, Side, Drive);
						}
						const TArray<FVector>& P = Cloth.Positions();
						const FString Shown = Case + (bSimulate ? TEXT(" cloth") : TEXT(" drawn"));
						bool bFinite = true;
						for (const FVector& V : P) bFinite &= !V.ContainsNaN();
						if (!TestTrue(Shown + TEXT(": the cloth is finite"), bFinite)) continue;
						TestTrue(FString::Printf(TEXT("%s: the tack on the pole's end (%.1f cm off)"), *Shown, FVector::Dist(P[0], Rig.Tack)), FVector::Dist(P[0], Rig.Tack) < 1.0);
						TestTrue(FString::Printf(TEXT("%s: the clew on its sheet (%.1f cm off)"), *Shown, FVector::Dist(P[Cols - 1], Rig.Clew)), FVector::Dist(P[Cols - 1], Rig.Clew) < 1.0);
						TestTrue(FString::Printf(TEXT("%s: the head on its halyard (%.1f cm off)"), *Shown, FVector::Dist(P[(Rows - 1) * Cols], Head)), FVector::Dist(P[(Rows - 1) * Cols], Head) < 1.0);
						// Out to leeward no further than the clew's limit and the belly (0.15 of the luff's height), to windward no
						// further than the pole's end (or the rail) and the belly; ahead no further than a metre and a half past the
						// bow, or a tenth of the luff's height on a big sail. (J-Class 14: Bluebonnet's 15 m pole squared back puts
						// her tack 15 m to windward, and her 43 m spinnaker on a run flies 2.7 m past her stem, 0.06 of its luff;
						// the J/22's flies 0.10 of hers ahead, 0.7 m. Both had been measured against the J/22's numbers.)
						const double Belly = 0.15 * (Head.Z - Rig.Tack.Z);
						const double TackOut = -Side * (Rig.Tack.Y - H.CenterY * CmPerMeter);
						const double AheadCm = (H.BowX + FMath::Max(1.5, 0.1 * (Head.Z - Rig.Tack.Z) / CmPerMeter)) * CmPerMeter;
						double Lee = -1e9, Wind = -1e9, Ahead = -1e9, Low = 1e9;
						for (const FVector& V : P)
						{
							Lee = FMath::Max(Lee, Side * (V.Y - H.CenterY * CmPerMeter));
							Wind = FMath::Max(Wind, -Side * (V.Y - H.CenterY * CmPerMeter));
							Ahead = FMath::Max(Ahead, V.X);
							Low = FMath::Min(Low, V.Z);
						}
						TestTrue(FString::Printf(TEXT("%s: the sail near the boat to leeward (%.0f cm from the centreline, limit %.0f)"), *Shown, Lee, RailOutCm + Belly),
							Lee <= RailOutCm + Belly);
						TestTrue(FString::Printf(TEXT("%s: the sail no further to windward than its pole (%.0f cm, the pole's end %.0f, limit %.0f)"), *Shown, Wind, TackOut,
							FMath::Max(TackOut, RailOutCm) + Belly), Wind <= FMath::Max(TackOut, RailOutCm) + Belly);
						TestTrue(FString::Printf(TEXT("%s: the sail not far ahead (x %.0f, bow %.0f, limit %.0f)"), *Shown, Ahead, H.BowX * CmPerMeter, AheadCm), Ahead <= AheadCm);
						TestTrue(FString::Printf(TEXT("%s: the foot clear of the deck (%.0f cm up, sheer %.0f)"), *Shown, Low, H.SheerHeight(C.MastX) * CmPerMeter),
							Low > H.SheerHeight(C.MastX) * CmPerMeter + 30.0);
						// QA on #728: where the sail's lower body crosses the centreline (the lower four fifths of the jib's luff; above,
						// the leech closes on the head at the mast, behind the forestay by design) it passes ahead of the forestay (the
						// jib's luff), not through it and the jib's tack (squared back on a dead run both corners are aft of it).
						if (Jib && !bSimulate)
						{
							double Worst = 1e9, WorstZ = 0.0;
							const double CheckTopCm = (Jib->FootZ() + 0.8 * (Jib->TopZ() - Jib->FootZ())) * CmPerMeter;
							for (int32 R = 0; R < Rows - 1; ++R)
							{
								for (int32 Col = 1; Col < Cols; ++Col)
								{
									const FVector& V = P[R * Cols + Col];
									if (FMath::Abs(V.Y - H.CenterY * CmPerMeter) > 30.0 || V.Z > CheckTopCm || V.Z < Jib->FootZ() * CmPerMeter) continue;
									const double Fore = V.X - Jib->LuffXAt(V.Z / CmPerMeter, 0) * CmPerMeter;
									if (Fore < Worst) { Worst = Fore; WorstZ = V.Z; }
								}
							}
							TestTrue(FString::Printf(TEXT("%s: the cloth ahead of the forestay at the centreline (worst %.1f cm at %.0f cm up)"), *Shown, Worst, WorstZ), Worst >= 5.0);
						}
					}
				}
			}
		}
		// The drawn sail without its corners (the physics' foot, as in build 40226d1c) on the repro's run.
		{
			FSailCloth Old;
			Old.Init(C.Spinnaker, ESailKind::Spinnaker);
			Old.SetHeadPoint(Head, Jib);
			for (int32 I = 0; I < C.Spinnaker.NumStrips; ++I) { Strips[I].Camber = 0.20; Strips[I].AngleFromCenterline = 97.0 * kDegToRad; Strips[I].Flow = ESailFlow::Attached; }
			FSailClothDrive Drawn;
			Drawn.bSimulate = false;
			Old.Step(Strips, 1, Drawn);
			const FSpinnakerRig Rig = SpinnakerRigCm(C, 1, -162.0 * kDegToRad, 0.5, Old.FootChord());
			// The bug: from the physics' foot the clew was drawn past the sheet's reach; between its corners it is within it.
			TestTrue(FString::Printf(TEXT("%s on a run: the physics' foot drew the clew %.0f cm out to starboard, past the sheet's reach (%.0f)"), *BoatName,
				Old.Positions()[Cols - 1].Y, RailOutCm), Old.Positions()[Cols - 1].Y > RailOutCm + 50.0);
			TestTrue(FString::Printf(TEXT("%s on a run: the clew now %.0f cm out (reach %.0f)"), *BoatName, Rig.Clew.Y, RailOutCm), Rig.Clew.Y <= RailOutCm + 0.5);
			// A model's mast front (the hero J/22's Hounds, 2 cm behind the config's): the pole's heel on it.
			const FVector ModelFront(MastFront * CmPerMeter - 2.0, 0.0, 783.0);
			const FSpinnakerRig OnModel = SpinnakerRigCm(C, 1, -162.0 * kDegToRad, 0.5, Old.FootChord(), &ModelFront);
			TestTrue(FString::Printf(TEXT("%s: the pole's heel on the model mast's front (x %.1f, front %.1f)"), *BoatName, OnModel.PoleHeel.X, ModelFront.X),
				OnModel.bValid && FMath::Abs(OnModel.PoleHeel.X - (ModelFront.X + 3.0)) < 0.5);
		}
	}
	TestTrue(TEXT("Some boats fly a poled spinnaker"), Poled >= 2);
	TestTrue(TEXT("Some boats fly a gennaker"), Gennakers >= 1);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualJibHeadTest, "SailingSim.Visual.JibHead", SailClothFlags)
bool FVisualJibHeadTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	// Feedback #20 follow-up: the hero J/22's forestay runs from ForestayTack to Hounds (Inputs/j22-hero/J22H_sockets.json,
	// boat frame cm); the physics jib's head is 42 cm above the wire's top.
	const FVector HeroHounds(68.06, 0.0, 783.09), HeroTack(343.8, 0.0, 82.44);
	constexpr int32 Rows = FSailCloth::Rows, Cols = FSailCloth::Cols;
	const FBoatConfig C;
	const double JibTopCm = C.Jib.Strips[C.Jib.NumStrips - 1].ZTop * CmPerMeter;
	const double MastFrontCm = (C.MastX + 0.5 * C.MastDiameter) * CmPerMeter;
	FVector Head;
	TestTrue(TEXT("J/22 hero: the jib's head goes to the forestay's top"), JibHeadCm(C, HeroHounds, Head));
	TestTrue(FString::Printf(TEXT("J/22 hero: the head a shackle under the tang (%.1f cm)"), HeroHounds.Z - Head.Z), Head.Z < HeroHounds.Z && Head.Z >= HeroHounds.Z - 8.0);
	TestTrue(FString::Printf(TEXT("J/22 hero: the head just ahead of the tang (x %.1f, tang %.1f)"), Head.X, HeroHounds.X), Head.X > HeroHounds.X + 2.0 && Head.X <= HeroHounds.X + 6.0);
	TestTrue(FString::Printf(TEXT("J/22 hero: the head ahead of the mast's centre (x %.1f)"), Head.X), Head.X > C.MastX * CmPerMeter + 5.0);
	TestEqual(TEXT("J/22 hero: the head on the centreline"), Head.Y, 0.0, 0.01);
	TestTrue(FString::Printf(TEXT("J/22 hero: the head under the physics jib's (%.0f, physics %.0f)"), Head.Z, JibTopCm), Head.Z < JibTopCm - 30.0);

	// A socket that isn't the forestay's top: the planform's head stays.
	FVector Unused;
	TestFalse(TEXT("A tang a metre under the jib's head is not its forestay"), JibHeadCm(C, HeroHounds - FVector(0, 0, 100.0), Unused));
	TestFalse(TEXT("A masthead tang never raises the jib's head"), JibHeadCm(C, FVector(HeroHounds.X, 0.0, C.MastheadZ * CmPerMeter), Unused));
	const FVector Inside(C.MastX * CmPerMeter - 2.0, 0.0, HeroHounds.Z);
	FVector InsideHead;
	TestTrue(TEXT("A tang inside the mast still sets the head"), JibHeadCm(C, Inside, InsideHead));
	TestTrue(FString::Printf(TEXT("A tang inside the mast: the head ahead of the mast's front (x %.1f)"), InsideHead.X), InsideHead.X > MastFrontCm);
	FSailCloth Cleared;
	Cleared.Init(C.Jib, ESailKind::Jib);
	Cleared.SetHeadPoint(Head);
	Cleared.ClearHeadPoint();
	TestFalse(TEXT("ClearHeadPoint goes back to the planform's head"), Cleared.HasHeadPoint());
	TestEqual(TEXT("ClearHeadPoint: the planform's top"), Cleared.TopZ() * CmPerMeter, JibTopCm, 0.01);
	TestFalse(TEXT("A bad socket"), JibHeadCm(C, FVector(std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0), Unused));

	FSailCloth Plan;
	Plan.Init(C.Jib, ESailKind::Jib);
	FSailStripState Strips[kMaxSailStrips];
	for (const int32 Side : { 1, -1 })
	{
		for (const bool bSimulate : { false, true })
		{
			FSailCloth Cloth;
			Cloth.Init(C.Jib, ESailKind::Jib);
			Cloth.SetHeadPoint(Head);
			FSailClothDrive Drive;
			Drive.ApparentWindKnots = 14.f;
			Drive.bSimulate = bSimulate;
			const int32 Steps = bSimulate ? 180 : 1;
			for (int32 N = 0; N < Steps; ++N)
			{
				for (int32 I = 0; I < C.Jib.NumStrips; ++I)
				{
					Strips[I].Camber = 0.13;
					Strips[I].AngleFromCenterline = Side * (20.0 + 3.0 * I) * kDegToRad;
					Strips[I].Flow = (N / 30) % 2 == 1 ? ESailFlow::Luffing : ESailFlow::Attached;
				}
				Drive.Time = N / 60.f;
				Cloth.Step(Strips, Side, Drive);
				if (N == 0) Plan.Step(Strips, Side, Drive);
			}
			const TArray<FVector>& P = Cloth.Positions();
			const FString Case = FString::Printf(TEXT("J/22 hero jib (side %d, %s)"), Side, bSimulate ? TEXT("cloth") : TEXT("drawn"));
			bool bFinite = true;
			for (const FVector& V : P) bFinite &= !V.ContainsNaN();
			TestTrue(Case + TEXT(": the cloth is finite"), bFinite);
			const int32 HeadLuff = (Rows - 1) * Cols;
			TestTrue(FString::Printf(TEXT("%s: the head on the forestay's top (%.1f cm off)"), *Case, FVector::Dist(P[HeadLuff], Head)), FVector::Dist(P[HeadLuff], Head) < 1.0);
			TestTrue(FString::Printf(TEXT("%s: the tack where the physics puts it (%.1f cm off)"), *Case, FVector::Dist(P[0], Plan.Positions()[0])), FVector::Dist(P[0], Plan.Positions()[0]) < 1.0);
			double Highest = -1e9;
			for (const FVector& V : P) Highest = FMath::Max(Highest, V.Z);
			TestTrue(FString::Printf(TEXT("%s: nothing above the tang (%.1f cm)"), *Case, Highest - HeroHounds.Z), Highest <= HeroHounds.Z + 2.0);
			// The luff (column 0) along the wire.
			double Worst = 0.0, WorstZ = 0.0;
			for (int32 R = 0; R < Rows; ++R)
			{
				const FVector& L = P[R * Cols];
				const double StayX = HeroTack.X + (HeroHounds.X - HeroTack.X) * (L.Z - HeroTack.Z) / (HeroHounds.Z - HeroTack.Z);
				if (FMath::Abs(L.X - StayX) > FMath::Abs(Worst)) { Worst = L.X - StayX; WorstZ = L.Z; }
			}
			TestTrue(FString::Printf(TEXT("%s: the luff along the forestay (worst %.1f cm at %.0f cm up)"), *Case, Worst, WorstZ), FMath::Abs(Worst) < 10.0);
		}
	}

	// The other boats' models put Hounds 5 cm over the physics jib's head on fractional rigs and 5 cm under the masthead on
	// masthead rigs (build_fleet.py): neither moves the jib's head (it is only ever lowered to a forestay under it).
	int32 Jibs = 0;
	for (int32 B = 0; B < int32(EBoatType::Count); ++B)
	{
		if (IsSquareRigged(EBoatType(B))) continue; // The frigate's square rig, crew and cameras come with the frigate wiring (IsSquareRigged).
		const FBoatConfig F = FBoatConfig::Make(EBoatType(B));
		if (!F.HasJib()) continue;
		++Jibs;
		const double TopCm = F.Jib.Strips[F.Jib.NumStrips - 1].ZTop * CmPerMeter;
		const double FrontCm = (F.MastX + 0.5 * F.MastDiameter) * CmPerMeter;
		FVector FleetHead;
		const FString Name = ANSI_TO_TCHAR(BoatTypeName(F.Type));
		TestFalse(Name + TEXT(": a fractional model's Hounds leaves the jib's head"), JibHeadCm(F, FVector(FrontCm, 0.0, TopCm + 5.0), FleetHead));
		TestFalse(Name + TEXT(": a masthead model's Hounds leaves the jib's head"), JibHeadCm(F, FVector(FrontCm, 0.0, F.MastheadZ * CmPerMeter - 5.0), FleetHead));
	}
	TestTrue(TEXT("Some boats carry a jib"), Jibs >= 3);
	return true;
}

#endif
