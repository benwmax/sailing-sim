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

	// On the wire: the J/22's forestay (ForestayTack to Hounds) with the cloth's luff 15 cm ahead of it at mid height.
	const FVector Tack(338.0, 0.0, 85.0), Hounds(68.1, 0.0, 783.1);
	const FVector Mid = Tack + (Hounds - Tack) * 0.5;
	const FVector ClothLuff = Mid + FVector(15.0, 0.0, 0.0);
	const FTransform W = KitFittings::HankOnStay(Tack, Hounds, ClothLuff);
	const FVector WireDir = (Hounds - Tack).GetSafeNormal();
	const FVector OnWire = W.GetLocation() - Tack;
	TestTrue(TEXT("A hank on the stay sits on the wire"), (OnWire - WireDir * FVector::DotProduct(OnWire, WireDir)).Size() < 0.01);
	TestTrue(TEXT("At the luff point's height"), FMath::Abs(W.GetLocation().Z - ClothLuff.Z) < 0.01);
	TestTrue(TEXT("Its Y along the wire"), FMath::Abs(FVector::DotProduct(W.TransformVectorNoScale(FVector::YAxisVector), WireDir)) > 0.999);
	const FVector ToSail = (ClothLuff - W.GetLocation()) - WireDir * FVector::DotProduct(ClothLuff - W.GetLocation(), WireDir);
	TestTrue(TEXT("Its sail (local -X) toward the cloth's luff"), FVector::DotProduct(W.TransformVectorNoScale(-FVector::XAxisVector), ToSail.GetSafeNormal()) > 0.999);
	const FTransform W0 = KitFittings::HankOnStay(Tack, Hounds, Tack + (Hounds - Tack) * 0.3);
	TestTrue(TEXT("A luff on the wire: the sail aft"), FVector::DotProduct(W0.TransformVectorNoScale(-FVector::XAxisVector), FVector(-1.0, 0.0, 0.0)) > 0.9);

	// Degenerate inputs (a boat switching mid-build: the stay's sockets on one point, a collapsed cloth) give a unit,
	// unscaled rotation, never FQuat(FMatrix)'s ensure (the Mac's RigClearance run, Nov 10).
	auto Unit = [](const FTransform& X) { return X.GetRotation().IsNormalized() && !X.ContainsNaN(); };
	TestTrue(TEXT("A zero-length stay"), Unit(KitFittings::HankOnStay(Tack, Tack, ClothLuff)));
	TestTrue(TEXT("A luff along the stay"), Unit(KitFittings::HankOnStay(FVector::ZeroVector, FVector(0.0, 0.0, 500.0), FVector(0.0, 0.0, 250.0))));
	TestTrue(TEXT("A collapsed cloth"), Unit(KitFittings::HankTransform(Luff, FVector::ZeroVector, FVector::ZeroVector, LuffSocket)));
	TestTrue(TEXT("Chord along the luff"), Unit(KitFittings::HankTransform(Luff, Up, Up, LuffSocket)));
	TestTrue(TEXT("Shackle with no frame"), Unit(KitFittings::HeadShackleTransform(Head, FVector::ZeroVector, FVector::ZeroVector)));
	TestTrue(TEXT("Shackle with the chord up the luff"), Unit(KitFittings::HeadShackleTransform(Head, Up, -Up)));

	// A cloth not yet built (NaN points) gives a transform the pawn must not place: Placeable says so, and the pawn hides
	// the part (the Mac's RigClearance run on the rebaked hero, Nov 10). Good frames are placeable.
	const FVector Nan(std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0);
	TestFalse(TEXT("A NaN stay socket isn't placeable"), KitFittings::Placeable(KitFittings::HankOnStay(Nan, Hounds, ClothLuff)));
	TestFalse(TEXT("A NaN luff point isn't placeable (on the luff)"), KitFittings::Placeable(KitFittings::HankTransform(Nan, Up, Aft, LuffSocket)));
	TestFalse(TEXT("A NaN head isn't placeable"), KitFittings::Placeable(KitFittings::HeadShackleTransform(Nan, Up, Aft)));
	TestTrue(TEXT("Good frames are placeable"), KitFittings::Placeable(H) && KitFittings::Placeable(S) && KitFittings::Placeable(W));

	TestTrue(TEXT("Hanks spread from near the tack to near the head"),
		FMath::IsNearlyEqual(KitFittings::HankV(0, 8), 0.0625f) && FMath::IsNearlyEqual(KitFittings::HankV(7, 8), 0.9375f));
	return true;
}
