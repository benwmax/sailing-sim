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
 * short-lived and fewer, that dry faster and run more in a harder air over the glass, and that are always inside the four
 * cells the shader looks in.
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

	// Running: none in still air; in a gale some do, and every drop, running or not, stays where the shader looks for it.
	int32 RunCalm = 0, RunGale = 0, Drops = 0, Outside = 0;
	for (int32 Layer = 0; Layer < SailingLens::NumLayers; ++Layer)
	{
		for (const FVector2f Wind : { FVector2f(0.f, 1.f), FVector2f(1.f, 0.2f), FVector2f(-0.7f, 0.7f), FVector2f(0.3f, -1.f) })
		{
			const FVector2f WL = SailingLens::TurnToLayer(Layer, Wind.GetSafeNormal());
			for (int32 Cell = 0; Cell < 300; ++Cell)
			{
				for (const float T : { 10.f, 13.3f, 17.9f, 25.2f })
				{
					for (const float Air : { StillAir, Gale })
					{
						const SailingLens::FLensDrop D = SailingLens::DropAt(Cell % 17 - 8, Cell / 17 - 9, Layer, T, 1.f, 1.f, Air, WL);
						if (D.Present <= 0.f) continue;
						++Drops;
						(Air == Gale ? RunGale : RunCalm) += D.bRuns ? 1 : 0;
						// Centre 0.2..0.8 into the cell, outline (a 10% wobble) within 0.66 of the centre any way.
						const float Reach = D.Radius * 1.1f * FMath::Max(D.StretchMax, D.Aspect);
						const bool bIn = D.Centre.X >= 0.2f - 1e-4f && D.Centre.X <= 0.8f + 1e-4f && D.Centre.Y >= 0.2f - 1e-4f && D.Centre.Y <= 0.8f + 1e-4f
							&& D.Radius * 1.1f * D.StretchMax <= 0.66f + 1e-4f && D.Radius * 1.1f * D.Aspect <= 0.66f;
						if (!bIn && ++Outside <= 5)
							AddError(FString::Printf(TEXT("Layer %d: a drop at (%.3f, %.3f), reach %.3f, outside the four cells the shader searches"), Layer, D.Centre.X, D.Centre.Y, Reach));
					}
				}
			}
		}
	}
	TestEqual(TEXT("Drops in still air that run"), RunCalm, 0);
	TestTrue(FString::Printf(TEXT("Drops in a gale that run: %d"), RunGale), RunGale > 0);
	TestEqual(FString::Printf(TEXT("Drops outside the shader's four cells (of %d)"), Drops), Outside, 0);

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
					 TEXT("0x846ca68bu"), TEXT("11.0f"), TEXT("17.0f"), TEXT("26.0f"), TEXT("0.16 * rain"), TEXT("0.13 * rain"), TEXT("0.10 * rain"),
					 TEXT("lerp(0.9, 0.4, windShare)"), TEXT("(splash ? 6.0f : 4.5f) * (0.6 + 0.8 * r[0])"), TEXT("0.07 + 0.23 * r[3] * r[3]"),
					 TEXT("r[6] < 0.7 * windShare"), TEXT("0.66 / (rad * 1.1)"), TEXT("float2(0.37, 0.61) * layer"), TEXT("cos(0.7 * layer)") })
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
