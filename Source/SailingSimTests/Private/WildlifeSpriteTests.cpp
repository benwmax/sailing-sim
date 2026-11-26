#include "Misc/AutomationTest.h"
#include "WildlifeActor.h"

#if WITH_DEV_AUTOMATION_TESTS

// Wildlife Phase 1 (docs/wildlife-1/README.md): how AWildlifeActor turns a far bird's quad and places a body.
namespace WildlifeSpriteTestsLocal
{
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
}

// The quad faces the camera with its y up the screen; its width is the span as seen (full head-on, a quarter side-on);
// a bird under two pixels keeps a two-pixel quad (both ways) and thins its cover by the same share; a body points where
// it flies.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWildlifeSpritesTest, "SailingSim.Wildlife.Sprites", WildlifeSpriteTestsLocal::Flags)
bool FSailingWildlifeSpritesTest::RunTest(const FString&)
{
	const FVector Camera(0.0, 0.0, 200.0);
	const double PixelAngle = 1.0 / 1000.0;
	// A gull 500 m north, 20 m up, flying straight at the camera (heading south): the whole span seen.
	{
		const FVector Bird(50000.0, 0.0, 2000.0);
		double Seen = 0.0, Cover = 0.0;
		const FTransform Q = AWildlifeActor::FarQuad(Bird, Camera, PI, 0.0, 1.2, PixelAngle, Seen, Cover);
		const FVector Face = Q.GetUnitAxis(EAxis::Z), Up = Q.GetUnitAxis(EAxis::Y);
		TestTrue(TEXT("faces the camera"), FVector::DotProduct(Face, (Camera - Bird).GetSafeNormal()) > 0.999);
		TestTrue(TEXT("its y is up the screen"), Up.Z > 0.9);
		TestEqual(TEXT("head-on, the whole span is seen"), Seen, 1.0, 1e-3);
		TestEqual(TEXT("big enough at 500 m: full cover"), Cover, 1.0, 1e-9);
		TestEqual(TEXT("drawn its own span"), Q.GetScale3D().Y, 1.2, 1e-6);
		TestEqual(TEXT("and as wide"), Q.GetScale3D().X, 1.2, 1e-6);
	}
	// The same gull flying east, across the view: its wings point at the camera, a quarter of the width.
	{
		const FVector Bird(50000.0, 0.0, 2000.0);
		double Seen = 0.0, Cover = 0.0, Widen = 0.0;
		const FTransform Q = AWildlifeActor::FarQuad(Bird, Camera, 0.5 * PI, 0.0, 1.2, PixelAngle, Seen, Cover, &Widen);
		TestEqual(TEXT("side-on, a quarter of the span"), Seen, 0.25, 1e-3);
		// a quarter of 1.2 m at 500 m is 0.6 px: the quad is held two pixels wide and the bird drawn in its middle
		const double Two = AWildlifeActor::MinPixels * PixelAngle * FVector::Dist(Bird, Camera) / 100.0;
		TestEqual(TEXT("side-on, held two pixels wide"), Q.GetScale3D().X, Two, 1e-6);
		TestEqual(TEXT("and widened by as much"), Widen, Two / (0.25 * 1.2), 1e-3);
		TestTrue(TEXT("side-on, still faces the camera"), FVector::DotProduct(Q.GetUnitAxis(EAxis::Z), (Camera - Bird).GetSafeNormal()) > 0.999);
		TestTrue(TEXT("side-on, y still up"), Q.GetUnitAxis(EAxis::Y).Z > 0.9);
	}
	// A swallow 2 km off: 0.33 m is a third of a pixel at 1 mrad: a two-pixel quad (4 m) and a twelfth of the cover.
	{
		const FVector Bird(200000.0, 0.0, 500.0);
		double Seen = 0.0, Cover = 0.0;
		const FTransform Q = AWildlifeActor::FarQuad(Bird, Camera, PI, 0.0, 0.33, PixelAngle, Seen, Cover);
		const double Dist = FVector::Dist(Bird, Camera) / 100.0;
		TestEqual(TEXT("kept at two pixels"), Q.GetScale3D().Y, AWildlifeActor::MinPixels * PixelAngle * Dist, 1e-6);
		TestEqual(TEXT("cover thinned by the same share"), Cover, 0.33 / (AWildlifeActor::MinPixels * PixelAngle * Dist), 1e-6);
	}
	// A body flying east, nose up 10 deg: its +X (the mesh's forward) points east and up; scale is the span.
	{
		const FTransform B = AWildlifeActor::BodyTransform(FVector::ZeroVector, 0.5 * PI, FMath::DegreesToRadians(10.0), 0.0, 1.8);
		const FVector Fwd = B.GetUnitAxis(EAxis::X);
		TestTrue(TEXT("a body heading east points east"), Fwd.Y > 0.98 && FMath::Abs(Fwd.X) < 1e-6);
		TestTrue(TEXT("nose up"), Fwd.Z > 0.17 && Fwd.Z < 0.18);
		TestEqual(TEXT("scaled to the wingspan"), B.GetScale3D().X, 1.8, 1e-9);
	}
	for (int32 S = 0; S < int32(Sailing::EBirdStyle::Count); ++S)
	{
		TestTrue(TEXT("every style names its body"), FCString::Strlen(AWildlifeActor::StyleMeshName(Sailing::EBirdStyle(S))) > 0);
	}
	return true;
}

#endif
