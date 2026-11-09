#include "Misc/AutomationTest.h"
#include "KitFittings.h"

namespace
{
	constexpr EAutomationTestFlags KitFittingsFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
}

// Hardware fit wave 2 (docs/hardware-fit/README.md): the jib's piston hanks and the halyard's snap shackle sit on the
// cloth the way the kit parts are meant to be worn. A hank's Luff socket lands on the luff point, its stay (local Y) runs
// up the luff, the sail (local -X) lies aft along the chord and the stay's centre is forward of the luff; the snap
// shackle's bail is on the head with its eye (local -Z, 54 mm) above, up the halyard. Kit socket numbers from
// Inputs/boat-kit/kit.json in Unreal's frame (x, -y, z) cm.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualKitFittingsTest, "SailingSim.Visual.KitFittings", KitFittingsFlags)
bool FVisualKitFittingsTest::RunTest(const FString& Parameters)
{
	const FVector LuffSocket(-3.41, 0.0, -0.34);
	// A raked luff (forestay leaning forward going up) and a chord aft and a little to port.
	const FVector Luff(150.0, 3.0, 400.0);
	const FVector Up = FVector(0.25, 0.0, 1.0).GetSafeNormal();
	const FVector Aft = FVector(-1.0, -0.15, 0.1).GetSafeNormal();
	const FTransform H = KitFittings::HankTransform(Luff, Up, Aft, LuffSocket);
	TestTrue(TEXT("The hank's Luff socket is on the luff point"), FVector::Dist(H.TransformPosition(LuffSocket), Luff) < 0.01);
	TestTrue(TEXT("Its stay (local Y) runs up the luff"), FVector::DotProduct(H.TransformVectorNoScale(FVector::YAxisVector), Up) > 0.999);
	TestTrue(TEXT("Its sail (local -X) lies aft along the chord"), FVector::DotProduct(H.TransformVectorNoScale(-FVector::XAxisVector), Aft) > 0.95);
	const FVector Stay = H.GetLocation();
	TestTrue(TEXT("The stay is forward of the luff (3.4 cm)"), FVector::DotProduct(Stay - Luff, -Aft) > 3.0 && FVector::Dist(Stay, Luff) < 4.0);
	TestTrue(TEXT("No scale"), H.GetScale3D().Equals(FVector::OneVector, 1e-4));

	const FVector Head(80.0, 0.0, 780.0);
	const FTransform S = KitFittings::HeadShackleTransform(Head, Up, Aft);
	TestTrue(TEXT("The shackle's bail is on the head"), FVector::Dist(S.GetLocation(), Head) < 0.01);
	const FVector Eye = S.TransformPosition(FVector(-0.54, 0.0, -5.4));
	TestTrue(TEXT("Its eye is above the head, up the halyard"), FVector::DotProduct(Eye - Head, Up) > 5.0);
	TestTrue(TEXT("It lies in the sail's plane (local X forward)"), FVector::DotProduct(S.TransformVectorNoScale(FVector::XAxisVector), -Aft) > 0.95);

	TestTrue(TEXT("Hanks spread from near the tack to near the head"),
		FMath::IsNearlyEqual(KitFittings::HankV(0, 8), 0.0625f) && FMath::IsNearlyEqual(KitFittings::HankV(7, 8), 0.9375f));
	return true;
}
