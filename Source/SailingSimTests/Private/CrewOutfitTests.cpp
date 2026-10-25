#include "Misc/AutomationTest.h"
#include "CrewOutfit.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags CrewOutfitFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
	float Luma(const FLinearColor& C) { return 0.2126f * C.R + 0.7152f * C.G + 0.0722f * C.B; }
	/** Which of the jackets' three colours: 0 yellow, 1 red, 2 light blue. */
	int32 VestFamily(const FLinearColor& C) { return C.B > C.R ? 2 : (C.G > 0.3f * C.R ? 0 : 1); }
}

// pc/crew-colours (docs/crew-colours): Bean's "lighter mix". Light polos and bright jackets, the player's boat a fixed set,
// AI boats varied by seed, a crew of three in three jacket colours.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCrewOutfitTest, "SailingSim.Visual.CrewOutfit", CrewOutfitFlags)
bool FCrewOutfitTest::RunTest(const FString&)
{
	for (int32 I = 0; I < NumCrewPolos(); ++I)
	{
		// Light: none darker than stone (the old navy and maroon polos were 0.03-0.06 and read near-black backlit).
		TestTrue(FString::Printf(TEXT("polo %d is light (luma %.2f)"), I, Luma(CrewPolo(I))), Luma(CrewPolo(I)) > 0.35f);
	}
	for (int32 I = 0; I < NumCrewVests(); ++I)
	{
		const FLinearColor V = CrewVest(I);
		// Bright nylon: a saturated channel well up (the old royal blue school vests peaked at 0.52 in blue, 0.08 luma).
		TestTrue(FString::Printf(TEXT("jacket %d is bright"), I), FMath::Max3(V.R, V.G, V.B) > 0.55f);
	}
	// The player's boat: the same three every time, three jacket colours.
	TSet<int32> PlayerFamilies;
	for (int32 S = 0; S < 3; ++S)
	{
		const FCrewOutfit A = SampleCrewOutfit(0, S), B = SampleCrewOutfit(0, S);
		TestTrue(TEXT("seed 0 is fixed"), A.Polo.Equals(B.Polo) && A.Vest.Equals(B.Vest));
		PlayerFamilies.Add(VestFamily(A.Vest));
	}
	TestEqual(TEXT("the player's crew wear three jacket colours"), PlayerFamilies.Num(), 3);
	// AI boats: deterministic per seed, three colours for a crew of three, polos all different, and varied between boats.
	TSet<uint32> FirstPolos;
	for (uint32 Seed = 1; Seed <= 200; ++Seed)
	{
		TSet<int32> Families;
		TSet<uint32> Polos;
		for (int32 S = 0; S < 3; ++S)
		{
			const FCrewOutfit O = SampleCrewOutfit(Seed, S);
			if (!O.Polo.Equals(SampleCrewOutfit(Seed, S).Polo)) { AddError(TEXT("not deterministic")); return false; }
			Families.Add(VestFamily(O.Vest));
			Polos.Add(GetTypeHash(O.Polo.ToFColor(false)));
		}
		if (Families.Num() != 3 || Polos.Num() != 3) { AddError(FString::Printf(TEXT("seed %u: %d jacket colours, %d polos"), Seed, Families.Num(), Polos.Num())); return false; }
		FirstPolos.Add(GetTypeHash(SampleCrewOutfit(Seed, 0).Polo.ToFColor(false)));
	}
	TestEqual(TEXT("boats differ: every polo comes first on some boat"), FirstPolos.Num(), NumCrewPolos());
	return true;
}

#endif
