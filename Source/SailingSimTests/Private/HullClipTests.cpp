#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "BoatModel.h"
#include "HullClip.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags HullClipFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
}

/**
 * docs/boat-water-clip/: the water's hull clip map holds every boat's hulls (FHullShape::BottomZ, the maxi's sections,
 * both of a catamaran's hulls, a trimaran's amas): the drawn sea at rest drops below the bottom wherever it is inside a
 * hull, and nowhere outside, between the hulls included.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualHullClipTest, "SailingSim.Visual.HullClip", HullClipFlags)
bool FVisualHullClipTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	for (int32 T = 0; T < int32(EBoatType::Count); ++T)
	{
		const FBoatConfig Cfg = FBoatConfig::Make(EBoatType(T));
		const FBoatModel Model(Cfg);
		const double Depth = Model.HullDepth();
		FHullClipMap Map;
		Map.Build(Cfg.Hulls, Depth);
		const FString Name = UTF8_TO_TCHAR(Cfg.Name);
		if (!TestTrue(FString::Printf(TEXT("%s: map built"), *Name), Map.IsBuilt())) continue;
		const double CellX = Map.SizeX / FHullClipMap::Cols, CellY = Map.SizeY / FHullClipMap::Rows;
		int32 Inside = 0, Outside = 0, BadBottom = 0, Wet = 0, Pits = 0;
		double WorstBottom = 0.0, WorstPit = 0.0;
		TArray<int32> HullsSeen;
		HullsSeen.SetNumZeroed(int32(Cfg.Hulls.size()));
		// Half-cell offsets so the samples fall between texel centres (the bilinear filter's worst case).
		for (double X = Map.X0 + 0.37 * CellX; X < Map.X0 + Map.SizeX; X += 1.5 * CellX)
		{
			for (double Y = Map.Y0 + 0.41 * CellY; Y < Map.Y0 + Map.SizeY; Y += 1.5 * CellY)
			{
				// The hull this point is in, and how far inside it is.
				int32 In = -1;
				double Margin = -1e9, Bottom = 0.0;
				for (int32 H = 0; H < int32(Cfg.Hulls.size()); ++H)
				{
					const FHullShape& S = Cfg.Hulls[H];
					const double Stern = S.HasStations() ? S.Stations.front().X : S.SternX;
					const double Bow = S.HasStations() ? S.Stations.back().X : S.BowX;
					const double M = FMath::Min(S.DeckHalfBeam(X) - FMath::Abs(Y - S.CenterY), FMath::Min(X - Stern, Bow - X));
					if (M > Margin) { Margin = M; In = H; Bottom = S.BottomZ(X, Y - S.CenterY, Depth); }
				}
				// The calm sea's surface (Z = 0 in the body frame, upright).
				const double Drop = Map.Drop(X, Y, 0.0, 1.0);
				if (Margin > 2.0 * FMath::Max(CellX, CellY) + 0.05)
				{
					++Inside;
					// Where the water can reach (the bottom up to 10 cm above the calm sea), the map is the hull.
					const double Err = Bottom < 0.1 ? FMath::Abs(Map.Sample(X, Y).Bottom - Bottom) : 0.0;
					WorstBottom = FMath::Max(WorstBottom, Err);
					BadBottom += Err > 0.03 ? 1 : 0;
					// Where the bottom is under the water, the water must end up under the bottom (5 mm: the filter).
					if (Bottom < -0.02)
					{
						++HullsSeen[In];
						Wet += -Drop > Bottom + 0.005 ? 1 : 0;
					}
				}
				else if (Margin < -FMath::Max(CellX, CellY))
				{
					++Outside;
					Pits += Drop > 1e-4 ? 1 : 0;
					WorstPit = FMath::Max(WorstPit, Drop);
				}
			}
		}
		TestTrue(FString::Printf(TEXT("%s: samples inside (%d) and outside (%d)"), *Name, Inside, Outside), Inside > 100 && Outside > 100);
		TestEqual(FString::Printf(TEXT("%s: map bottom off the hull by > 3 cm (worst %.3f m)"), *Name, WorstBottom), BadBottom, 0);
		TestEqual(FString::Printf(TEXT("%s: water left above the bottom inside a hull"), *Name), Wet, 0);
		TestEqual(FString::Printf(TEXT("%s: water dropped outside the hulls (worst %.3f m)"), *Name, WorstPit), Pits, 0);
		for (int32 H = 0; H < HullsSeen.Num(); ++H)
		{
			const FHullShape& S = Cfg.Hulls[H];
			// Every immersed hull is clipped at rest; an ama clear of the water at rest is clipped once she heels it in
			// (water 10 cm above its keel line amidships drops below its bottom).
			if (S.DepthOffset <= 0.0) TestTrue(FString::Printf(TEXT("%s: hull %d clipped"), *Name, H), HullsSeen[H] > 10);
			const double AmidX = S.HasStations() ? 0.5 * (S.Stations.front().X + S.Stations.back().X) : S.MaxBeamX;
			const double KeelZ = S.BottomZ(AmidX, 0.0, Depth);
			TestTrue(FString::Printf(TEXT("%s: hull %d clipped once immersed"), *Name, H),
				KeelZ + 0.1 - Map.Drop(AmidX, S.CenterY, KeelZ + 0.1, 1.0) < KeelZ);
		}
		// Heeled 25 deg: water up to 15 cm above the lee sheer inside the gunwale still drops below the deck.
		const FHullShape& Main = Cfg.Hulls[0];
		const double MidX = Main.HasStations() ? 0.5 * (Main.Stations.front().X + Main.Stations.back().X) : Main.MaxBeamX;
		const double EdgeY = Main.CenterY + Main.DeckHalfBeam(MidX) - 0.3;
		const double SheerZ = Main.SheerHeight(MidX);
		TestTrue(FString::Printf(TEXT("%s: water over the sheer drops inside the gunwale"), *Name),
			Map.Drop(MidX, EdgeY, SheerZ + 0.1, FMath::Cos(FMath::DegreesToRadians(25.0))) > 0.1);
	}
	// M_WaterV4 mirrors FHullClipMap::Drop (keep them in step).
	FString Script;
	if (FFileHelper::LoadFileToString(Script, *FPaths::Combine(FPaths::ProjectDir(), TEXT("scripts/make_materials.py"))))
	{
		TestTrue(TEXT("M_WaterV4's drop is FHullClipMap::Drop's"), Script.Contains(TEXT("max(0.0, 1.1 * himm + 0.03 * saturate(himm / 0.05)) / max(HullClipD.z, 0.3)) * hedge")));
		TestTrue(TEXT("M_WaterV4's edge fade is FHullClipMap::Drop's"), Script.Contains(TEXT("saturate(min(hc.b, hc.a) / (hbz < hc.g ? 0.05 : 0.15))")));
	}
	return true;
}

#endif
