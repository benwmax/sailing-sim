#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "LensDrops.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags LensFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

	/** The rain layers' drops visible on a 16:9 screen at time T: count, and their draws for the statistics. */
	struct FScreenDrops
	{
		int32 Count = 0;
		TArray<float> Radius, CentreX, CentreY;
		TArray<uint64> Ids;   // cell, layer and epoch: the same drop at two times has the same id
	};

	FScreenDrops DropsOnScreen(float T, float Rain, float Spray, float AirMs, const FVector2f& Wind)
	{
		FScreenDrops Out;
		for (int32 Layer = 0; Layer < SailingLens::SplashLayer; ++Layer)
		{
			const FVector2f WindLayer = SailingLens::TurnToLayer(Layer, Wind.GetSafeNormal());
			// The cells the screen's (aspect 16:9, height 1) lattice covers, with a margin.
			FVector2f Lo(1e9f, 1e9f), Hi(-1e9f, -1e9f);
			for (const FVector2f& Corner : { FVector2f(0, 0), FVector2f(16.f / 9.f, 0), FVector2f(0, 1), FVector2f(16.f / 9.f, 1) })
			{
				const FVector2f P = SailingLens::ToLattice(Layer, Corner);
				Lo = FVector2f(FMath::Min(Lo.X, P.X), FMath::Min(Lo.Y, P.Y));
				Hi = FVector2f(FMath::Max(Hi.X, P.X), FMath::Max(Hi.Y, P.Y));
			}
			for (int32 Y = FMath::FloorToInt(Lo.Y); Y <= FMath::FloorToInt(Hi.Y); ++Y)
			{
				for (int32 X = FMath::FloorToInt(Lo.X); X <= FMath::FloorToInt(Hi.X); ++X)
				{
					const SailingLens::FLensDrop D = SailingLens::DropAt(X, Y, Layer, T, Rain, Spray, AirMs, WindLayer);
					if (D.Present * D.Life < 0.05f) continue;
					// On screen? (Back from the lattice: the inverse turn of the centre.)
					const float A = -SailingLens::LayerAngle(Layer);
					const FVector2f L = (FVector2f(float(X), float(Y)) + D.Centre - SailingLens::LayerShift(Layer)) / SailingLens::LayerScale(Layer);
					const FVector2f S(FMath::Cos(A) * L.X - FMath::Sin(A) * L.Y, FMath::Sin(A) * L.X + FMath::Cos(A) * L.Y);
					if (S.X < 0.f || S.X > 16.f / 9.f || S.Y < 0.f || S.Y > 1.f) continue;
					++Out.Count;
					Out.Radius.Add(D.Radius);
					Out.CentreX.Add(D.Centre.X);
					Out.CentreY.Add(D.Centre.Y);
					Out.Ids.Add((uint64(SailingLens::CellSeed(X, Y, Layer)) << 32) ^ uint64(uint32(D.Epoch)));
				}
			}
		}
		return Out;
	}

	float Mean(const TArray<float>& V)
	{
		double S = 0.0;
		for (const float X : V) S += X;
		return V.Num() ? float(S / V.Num()) : 0.f;
	}
	float StdDev(const TArray<float>& V)
	{
		const float M = Mean(V);
		double S = 0.0;
		for (const float X : V) S += (X - M) * (X - M);
		return V.Num() ? float(FMath::Sqrt(S / V.Num())) : 0.f;
	}
	float Correlation(const TArray<float>& A, const TArray<float>& B)
	{
		const float Ma = Mean(A), Mb = Mean(B);
		double S = 0.0;
		for (int32 I = 0; I < A.Num(); ++I) S += (A[I] - Ma) * (B[I] - Mb);
		const float D = StdDev(A) * StdDev(B) * A.Num();
		return D > 0.f ? float(S / D) : 0.f;
	}

	/** The drop count #707's LENS_CODE drew at full rain: three layers of 9, 18 and 27 cells a screen height holding a drop
	 *  with chance 0.18, 0.24 and 0.30 (a drop never left; it only dimmed). */
	float OldDropCount()
	{
		float N = 0.f;
		for (int32 Layer = 0; Layer < 3; ++Layer)
		{
			const float Scale = 9.f + 9.f * Layer;
			N += (0.18f + 0.06f * Layer) * Scale * Scale * 16.f / 9.f;
		}
		return N;
	}
}

/**
 * Feedback #28: the storm's lens drops read as a repeating pattern, too steady and constant. Each drop lived for ever on a
 * lattice that scrolled with the wind, and its place and size came from one hash drawn under the rain's chance, so they
 * were alike. SailingLens::DropAt (the CPU twin of LENS_CODE's placement) must give drops that are independent, varied,
 * short-lived and fewer, that dry faster and run more in a harder air over the glass (low-passed, so a camera turn doesn't
 * fade them together), and that are always inside the four cells the shader looks in.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualLensDropsTest, "SailingSim.Visual.LensDrops", LensFlags)
bool FVisualLensDropsTest::RunTest(const FString&)
{
	const FVector2f Still(0.1f, 1.f);   // the WindScreen of a still camera in calm air: gravity down the screen
	const float StillAir = 3.f, Gale = 16.f;

	// Fewer: at full rain 40% of #707's count or less (about a third, 187 of 553), and still plenty to read as rain.
	float Count = 0.f;
	for (int32 I = 0; I < 20; ++I) Count += DropsOnScreen(30.f + 1.7f * I, 1.f, 0.f, StillAir, Still).Count / 20.f;
	TestTrue(FString::Printf(TEXT("Full rain: %.0f drops on the glass, at most 40%% of #707's %.0f and at least 60"), Count, OldDropCount()),
		Count <= 0.4f * OldDropCount() && Count >= 60.f);

	// The rain rate sets how many; dry glass has none.
	float Light = 0.f;
	for (int32 I = 0; I < 20; ++I) Light += DropsOnScreen(30.f + 1.7f * I, 0.3f, 0.f, StillAir, Still).Count / 20.f;
	TestTrue(FString::Printf(TEXT("Light rain (0.3): %.0f drops, under half of full rain's %.0f"), Light, Count), Light < 0.5f * Count && Light > 0.f);
	TestEqual(TEXT("No rain, no spray: no drops"), DropsOnScreen(30.f, 0.f, 0.f, StillAir, Still).Count, 0);

	// Varied and independent: sizes spread, centres spread over their box, and size says nothing about place.
	FScreenDrops Pool;
	for (int32 I = 0; I < 10; ++I)
	{
		const FScreenDrops S = DropsOnScreen(40.f + 9.1f * I, 1.f, 0.f, StillAir, Still);
		Pool.Radius.Append(S.Radius); Pool.CentreX.Append(S.CentreX); Pool.CentreY.Append(S.CentreY);
	}
	const float SizeSpread = StdDev(Pool.Radius) / Mean(Pool.Radius);
	TestTrue(FString::Printf(TEXT("Drop sizes vary (spread %.2f of the mean)"), SizeSpread), SizeSpread > 0.3f);
	// A uniform spread over 0.6 has a standard deviation of 0.173.
	TestTrue(FString::Printf(TEXT("Centres spread over their cell (sd %.3f, %.3f)"), StdDev(Pool.CentreX), StdDev(Pool.CentreY)),
		StdDev(Pool.CentreX) > 0.15f && StdDev(Pool.CentreY) > 0.15f);
	const float RX = Correlation(Pool.Radius, Pool.CentreX), RY = Correlation(Pool.Radius, Pool.CentreY), XY = Correlation(Pool.CentreX, Pool.CentreY);
	TestTrue(FString::Printf(TEXT("Size, x and y are independent (r %.3f, %.3f, %.3f)"), RX, RY, XY),
		FMath::Abs(RX) < 0.08f && FMath::Abs(RY) < 0.08f && FMath::Abs(XY) < 0.08f);

	// Not constant: ten seconds on, almost every drop is a new one (#707's were all the same drops, scrolled).
	{
		const FScreenDrops A = DropsOnScreen(50.f, 1.f, 0.f, StillAir, Still), B = DropsOnScreen(60.f, 1.f, 0.f, StillAir, Still);
		TSet<uint64> Before;
		Before.Append(A.Ids);
		int32 Same = 0;
		for (const uint64 Id : B.Ids) Same += Before.Contains(Id) ? 1 : 0;
		TestTrue(FString::Printf(TEXT("Ten seconds on, %d of %d drops are the same ones"), Same, B.Ids.Num()), Same * 10 < B.Ids.Num());
	}

	// Lives: each cell keeps its own clock, so drops land and dry at different times; harder air, shorter lives.
	auto Lifetimes = [](float AirMs, TArray<float>& Out)
	{
		for (int32 Cell = 0; Cell < 400; ++Cell)
		{
			// Walk one cell's time in 0.05 s steps and time each drop's stay (life over 0.3).
			float On = -1.f; int32 Epoch = -1;
			for (float T = 100.f; T < 160.f; T += 0.05f)
			{
				const SailingLens::FLensDrop D = SailingLens::DropAt(Cell % 20, Cell / 20, 0, T, 1.f, 0.f, AirMs, FVector2f(0.f, 1.f));
				const bool bOn = D.Present * D.Life > 0.3f;
				if (bOn && On < 0.f) { On = T; Epoch = D.Epoch; }
				if (On >= 0.f && (!bOn || D.Epoch != Epoch)) { Out.Add(T - On); On = -1.f; }
			}
		}
	};
	TArray<float> Calm, Windy;
	Lifetimes(StillAir, Calm);
	Lifetimes(Gale, Windy);
	const float CalmSpread = StdDev(Calm) / FMath::Max(Mean(Calm), 1e-3f);
	TestTrue(FString::Printf(TEXT("Still air: drops stay %.1f s on average, spread %.2f of that"), Mean(Calm), CalmSpread),
		Calm.Num() > 100 && Mean(Calm) > 1.5f && Mean(Calm) < 6.f && CalmSpread > 0.2f);
	TestTrue(FString::Printf(TEXT("A gale over the glass (or a fast camera): drops stay %.1f s, under 0.6 of still air's %.1f s"), Mean(Windy), Mean(Calm)),
		Windy.Num() > 100 && Mean(Windy) < 0.6f * Mean(Calm));

	// Running: none in still air; in a gale some do.
	int32 RunCalm = 0, RunGale = 0;
	for (int32 Cell = 0; Cell < 2000; ++Cell)
	{
		for (const float Air : { StillAir, Gale })
		{
			const SailingLens::FLensDrop D = SailingLens::DropAt(Cell % 40, Cell / 40, 1, 33.f, 1.f, 0.f, Air, FVector2f(0.6f, 0.8f));
			if (D.Present > 0.f) (Air == Gale ? RunGale : RunCalm) += D.bRuns ? 1 : 0;
		}
	}
	TestEqual(TEXT("Drops in still air that run"), RunCalm, 0);
	TestTrue(FString::Printf(TEXT("Drops in a gale that run: %d"), RunGale), RunGale > 0);

	// The shader looks for a pixel's drop only in the four cells nearest it (floor(p - 0.5) and the next). Every drop that
	// can reach a point (its outline at its farthest, wobble and tail included) must sit in one of those four cells: walk
	// points over the lattice and check all nine cells around each.
	int32 Covering = 0, Missed = 0;
	FRandomStream Rng(28);
	for (int32 I = 0; I < 20000; ++I)
	{
		const int32 Layer = I % SailingLens::NumLayers;
		const FVector2f P(Rng.FRandRange(-40.f, 40.f), Rng.FRandRange(-40.f, 40.f));
		const FVector2f Wind = FVector2f(Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-1.f, 1.f)).GetSafeNormal();
		const float T = Rng.FRandRange(0.f, 5000.f), Air = Rng.FRandRange(0.f, 30.f);
		const FVector2f WL = SailingLens::TurnToLayer(Layer, Wind);
		const int32 BaseX = FMath::FloorToInt(P.X - 0.5f), BaseY = FMath::FloorToInt(P.Y - 0.5f);
		for (int32 Dy = -1; Dy <= 1; ++Dy)
		{
			for (int32 Dx = -1; Dx <= 1; ++Dx)
			{
				const int32 CX = FMath::FloorToInt(P.X) + Dx, CY = FMath::FloorToInt(P.Y) + Dy;
				const SailingLens::FLensDrop D = SailingLens::DropAt(CX, CY, Layer, T, 1.f, 1.f, Air, WL);
				if (D.Present <= 0.f) continue;
				const FVector2f Off = P - FVector2f(float(CX), float(CY)) - D.Centre;
				if (Off.Size() > D.Reach) continue;
				++Covering;
				const bool bSearched = (CX == BaseX || CX == BaseX + 1) && (CY == BaseY || CY == BaseY + 1);
				if (!bSearched && ++Missed <= 5)
					AddError(FString::Printf(TEXT("Layer %d: the drop of cell (%d, %d) at (%.3f, %.3f), reach %.3f, covers (%.3f, %.3f) outside the four cells searched"),
						Layer, CX, CY, D.Centre.X, D.Centre.Y, D.Reach, P.X, P.Y));
			}
		}
	}
	TestTrue(FString::Printf(TEXT("Points under a drop: %d"), Covering), Covering > 1000);
	TestEqual(TEXT("Drops reaching a point from outside its four searched cells"), Missed, 0);

	// The air over the glass is low-passed, so a gust or a sudden change of camera speed doesn't rewrite every drop's life in
	// one frame (a turn of the camera alone doesn't change the air's whole speed); a cut, teleport or origin rebase brings no air.
	// A drop that starts running as the air builds slides from where it sat: a small rise in the air moves no drop far.
	{
		SailingLens::FLensAir A;
		A.Update(FVector2f(0.f, 3.f), 3.f, 1.f / 60.f);
		TestTrue(TEXT("Lens air: the first frame takes the air as it is"), A.bPrimed && FMath::IsNearlyEqual(A.Speed, 3.f));
		A.Update(FVector2f(15.f, 3.f), 15.f, 1.f / 60.f);
		TestTrue(FString::Printf(TEXT("Lens air: one frame after a jump from 3 to 15 m/s, %.2f m/s"), A.Speed), A.Speed < 3.2f);
		for (int32 F = 0; F < 1200; ++F) A.Update(FVector2f(15.f, 3.f), 15.f, 1.f / 60.f);
		TestTrue(FString::Printf(TEXT("Lens air: twenty seconds on, %.2f m/s"), A.Speed), FMath::IsNearlyEqual(A.Speed, 15.f, 0.1f));
		// Drops whose life changes much in the frame after the jump, with the filter.
		int32 Changed = 0, Seen = 0;
		SailingLens::FLensAir B;
		B.Update(FVector2f(0.f, 3.f), 3.f, 1.f / 60.f);
		const float Before = B.Speed;
		B.Update(FVector2f(15.f, 3.f), 15.f, 1.f / 60.f);
		for (int32 Cell = 0; Cell < 2000; ++Cell)
		{
			const SailingLens::FLensDrop D0 = SailingLens::DropAt(Cell % 40, Cell / 40, 0, 77.f, 1.f, 0.f, Before, FVector2f(0.f, 1.f));
			const SailingLens::FLensDrop D1 = SailingLens::DropAt(Cell % 40, Cell / 40, 0, 77.f + 1.f / 60.f, 1.f, 0.f, B.Speed, FVector2f(0.f, 1.f));
			if (D0.Present * D0.Life < 0.05f && D1.Present * D1.Life < 0.05f) continue;
			++Seen;
			Changed += FMath::Abs(D1.Present * D1.Life - D0.Present * D0.Life) > 0.1f ? 1 : 0;
		}
		TestTrue(FString::Printf(TEXT("The air over the glass jumping from 3 to 15 m/s: %d of %d drops change by over 0.1 in a frame"), Changed, Seen),
			Seen > 50 && Changed * 50 < Seen);
		// Running eases in: across a small step in the air no running drop moves more than 0.02 of a cell.
		float WorstSlide = 0.f;
		for (int32 Cell = 0; Cell < 4000; ++Cell)
		{
			for (float Air = 4.f; Air < 16.f; Air += 0.5f)
			{
				const SailingLens::FLensDrop D0 = SailingLens::DropAt(Cell % 60, Cell / 60, 1, 91.f, 1.f, 0.f, Air, FVector2f(0.6f, 0.8f));
				const SailingLens::FLensDrop D1 = SailingLens::DropAt(Cell % 60, Cell / 60, 1, 91.f, 1.f, 0.f, Air + 0.01f, FVector2f(0.6f, 0.8f));
				if (D0.Present > 0.f) WorstSlide = FMath::Max(WorstSlide, (D1.Centre - D0.Centre).Size());
			}
		}
		TestTrue(FString::Printf(TEXT("0.01 m/s more air moves a drop at most %.4f of a cell"), WorstSlide), WorstSlide < 0.02f);
		TestTrue(TEXT("A camera cut (a 19.2 km origin rebase in a frame) brings no air"),
			SailingLens::LensCameraVelocity(FVector(19200.0, 0.0, 0.0), 1.f / 60.f).IsNearlyZero());
		TestTrue(TEXT("A fast boat's camera (15 m/s) keeps its air"),
			FMath::IsNearlyEqual(SailingLens::LensCameraVelocity(FVector(0.25, 0.0, 0.0), 1.f / 60.f).X, 15.0, 1e-3));
	}

	// LENS_CODE carries the same hash and draws as LensDrops.h.
	FString Script;
	if (FFileHelper::LoadFileToString(Script, *FPaths::Combine(FPaths::ProjectDir(), TEXT("scripts/make_materials.py"))))
	{
		const int32 Start = Script.Find(TEXT("LENS_CODE = \"\"\""));
		if (TestTrue(TEXT("LENS_CODE found"), Start != INDEX_NONE))
		{
			const int32 End = Script.Find(TEXT("\"\"\""), ESearchCase::CaseSensitive, ESearchDir::FromStart, Start + 16);
			const FString Code = Script.Mid(Start, End - Start);
			for (const TCHAR* Must : { TEXT("0x8da6b343u"), TEXT("0xd8163841u"), TEXT("0xcb1ab31fu"), TEXT("0x9e3779b9u"), TEXT("0x7feb352du"),
					 TEXT("0x846ca68bu"), TEXT("uint(epoch + 1.0)"), TEXT("11.0f"), TEXT("17.0f"), TEXT("26.0f"), TEXT("5.0f"),
					 TEXT("splash ? 0.35 * Spray * Spray"), TEXT("0.16 * rain + 0.35 * Spray"), TEXT("0.13 * rain + 0.12 * Spray"),
					 TEXT("0.10 * rain + 0.06 * Spray"), TEXT("chance < 0.002"), TEXT("(chance - r[2]) / 0.05"),
					 TEXT("saturate((Wind.z - 3.0) / 12.0)"), TEXT("splash ? 0.9f : lerp(0.9, 0.4, windShare)"),
					 TEXT("(splash ? 6.0f : 4.5f) * (0.6 + 0.8 * r[0])"), TEXT("float tt = T / period + r[1]"),
					 TEXT("saturate(age / 0.03) * (1.0 - smoothstep(0.6 * visible, visible, age)) * (splash ? Spray : 1.0f)"),
					 TEXT("(splash ? 0.18 + 0.14 * r[3] : 0.07 + 0.23 * r[3] * r[3]) * (1.0 - 0.35 * smoothstep(0.5 * visible, visible, age))"),
					 TEXT("0.8 + 0.25 * r[8]"), TEXT("float2(r[4], r[5]) * 0.6 + 0.2"), TEXT("splash ? 0.0f : saturate((0.7 * windShare - r[6]) / 0.05)"),
					 TEXT("(0.5 + 0.5 * r[7]) * smoothstep(0.15, visible, age) * runW"), TEXT("lerp(0.6 * windShare, 2.0, runW)"),
					 TEXT("0.66 / (rad * 1.1)"), TEXT("float2(0.37, 0.61) * layer"), TEXT("cos(0.7 * layer)"), TEXT("floor(p - 0.5)") })
				TestTrue(FString::Printf(TEXT("LENS_CODE has %s (LensDrops.h's twin)"), Must), Code.Contains(Must, ESearchCase::CaseSensitive));
		}
	}
	else
	{
		AddWarning(TEXT("scripts/make_materials.py not found"));
	}
	return true;
}

#endif
