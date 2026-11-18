#include "Misc/AutomationTest.h"
#include "GroundDress.h"
#include "LakeData.h"
#include "Marina.h"

#if WITH_DEV_AUTOMATION_TESTS

/**
 * Shore plan Track A (docs/envloop/ground): what the terrain hands M_Ground. The bank's tone wanders in 20-40 m stretches
 * and matches the test shore's (scene.py `smooth`); the season is straw in January and green in July, ramping through
 * November and April; the mown mask is 1 at a house, 0 past 40 m with a ragged edge, 1 on the club's lawn, and 0 for a
 * commercial or coarse house.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingGroundDressTest, "SailingSim.Visual.GroundDress",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FSailingGroundDressTest::RunTest(const FString& Parameters)
{
	using namespace SailingGround;
	// scene.py: clip(0.5 + 0.5 sin(x/13 + 0.6 sin(y/9)) sin(x/31 + 1.3), 0, 1) at a few points (python3, 6 digits).
	TestTrue(TEXT("Bank tone at (0, 0)"), FMath::IsNearlyEqual(BankTone(0.0, 0.0), 0.5, 1e-6));
	TestTrue(TEXT("Bank tone at (20, 7)"), FMath::IsNearlyEqual(BankTone(20.0, 7.0), 0.930657, 1e-5));
	TestTrue(TEXT("Bank tone at (-45, 120)"), FMath::IsNearlyEqual(BankTone(-45.0, 120.0), 0.507270, 1e-5));
	// It wanders: along 200 m of shore it visits both ends, and neighbouring metres differ by little (no 5 m squares).
	double Lo = 1.0, Hi = 0.0, MaxStep = 0.0, Prev = BankTone(0.0, 3.0);
	for (int32 I = 1; I <= 200; ++I)
	{
		const double V = BankTone(double(I), 3.0);
		Lo = FMath::Min(Lo, V); Hi = FMath::Max(Hi, V); MaxStep = FMath::Max(MaxStep, FMath::Abs(V - Prev)); Prev = V;
	}
	TestTrue(TEXT("Bank tone reaches clay and sand along 200 m"), Lo < 0.1 && Hi > 0.9);
	TestTrue(TEXT("Bank tone changes little per metre"), MaxStep < 0.08);

	TestEqual(TEXT("Dormant in January"), SeasonAmount(15), 1.f);
	TestEqual(TEXT("Green in July"), SeasonAmount(196), 0.f);
	TestEqual(TEXT("Green in October"), SeasonAmount(290), 0.f);
	TestTrue(TEXT("Browning in mid-November"), SeasonAmount(319) > 0.3f && SeasonAmount(319) < 0.7f);
	TestTrue(TEXT("Greening in early April"), SeasonAmount(95) > 0.2f && SeasonAmount(95) < 0.8f);
	TestEqual(TEXT("Dormant on Dec 31 and Jan 1 alike"), SeasonAmount(365), SeasonAmount(1));

	FLakeData Lake;
	FLakeHouse House;
	House.X = 1000.0; House.Y = 2000.0; House.bFullDetail = true;
	Lake.Houses.Add(House);
	FLakeHouse Shop = House; Shop.X = 1300.0; Shop.bCommercial = true;
	Lake.Houses.Add(Shop);
	FLakeHouse Coarse = House; Coarse.X = 1600.0; Coarse.bFullDetail = false;
	Lake.Houses.Add(Coarse);
	FMarinaBuilding Club;
	Club.Kind = TEXT("clubhouse"); Club.Center = FVector2D(-500.0, 300.0); Club.Size = FVector2D(30.0, 20.0);
	Lake.Marina.Buildings.Add(Club);
	FMownSource Mown;
	Mown.Build(Lake);
	TestEqual(TEXT("One house cell"), Mown.Houses.Num(), 1);
	TestEqual(TEXT("One club lawn"), Mown.Lawns.Num(), 1);
	TestEqual(TEXT("Mown at the house"), Mown.At(1000.0, 2000.0), 1.f);
	TestEqual(TEXT("Mown 15 m from the house"), Mown.At(1015.0, 2000.0), 1.f);
	TestEqual(TEXT("Not mown 45 m from the house"), Mown.At(1045.0, 2000.0), 0.f);
	TestEqual(TEXT("Not mown at the shop"), Mown.At(1300.0, 2000.0), 0.f);
	TestEqual(TEXT("Not mown at the coarse house"), Mown.At(1600.0, 2000.0), 0.f);
	TestEqual(TEXT("Mown at the clubhouse"), Mown.At(-500.0, 300.0), 1.f);
	TestEqual(TEXT("Mown 40 m from the clubhouse"), Mown.At(-460.0, 300.0), 1.f);
	TestEqual(TEXT("Not mown 70 m from the clubhouse"), Mown.At(-430.0, 300.0), 0.f);
	// The edge is ragged: round the house at 31 m the mask takes different values with the bearing.
	float EdgeLo = 1.f, EdgeHi = 0.f;
	for (int32 A = 0; A < 36; ++A)
	{
		const double Ang = A * PI / 18.0;
		const float V = Mown.At(1000.0 + 31.0 * FMath::Cos(Ang), 2000.0 + 31.0 * FMath::Sin(Ang));
		EdgeLo = FMath::Min(EdgeLo, V); EdgeHi = FMath::Max(EdgeHi, V);
	}
	TestTrue(TEXT("The mown edge is ragged"), EdgeHi - EdgeLo > 0.3f);
	TestTrue(TEXT("Mown is within 0..1"), EdgeLo >= 0.f && EdgeHi <= 1.f);
	return true;
}
#endif
