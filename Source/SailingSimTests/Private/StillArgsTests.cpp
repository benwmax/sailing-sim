#include "Misc/AutomationTest.h"
#include "BenchRunner.h"
#include "UI/SailPhotoPanel.h"

#if WITH_DEV_AUTOMATION_TESTS

// Stills (Nov 2026): a still's own camera arguments, appended after a shared set, must win, and photo mode's panel must
// stay out of a clean still (-SailingNoHud).
namespace
{
	constexpr EAutomationTestFlags StillArgsFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingStillArgsLastWinsTest, "SailingSim.UI.StillArgs.LastValueWins", StillArgsFlags)
bool FSailingStillArgsLastWinsTest::RunTest(const FString& Parameters)
{
	// The shared set first, the still's own close-up after it: FParse::Value read 8 m, the camera ended up 8 m off.
	const TCHAR* Line = TEXT("-SailingWorld=Lake -SailingCamYaw=120 -SailingCamPitch=4 -SailingCamDist=8 \"-SailingStartAt=5864,874,-138\" ")
		TEXT("-SailingCamTarget=0.3,0.6,1.4 -SailingCamDist=1.8 -SailingCamPitch=-30 -SailingCamYaw=210 \"-SailingPhotoCam=4.6,1.0,2.2,205,-35\"");
	float Dist = 0.f, Pitch = 0.f, Yaw = 0.f;
	TestTrue(TEXT("CamDist found"), SailingArgs::LastValue(Line, TEXT("SailingCamDist="), Dist));
	TestEqual(TEXT("the last CamDist wins"), Dist, 1.8f);
	TestTrue(TEXT("CamPitch found"), SailingArgs::LastValue(Line, TEXT("SailingCamPitch="), Pitch));
	TestEqual(TEXT("the last CamPitch wins"), Pitch, -30.f);
	TestTrue(TEXT("CamYaw found"), SailingArgs::LastValue(Line, TEXT("SailingCamYaw="), Yaw));
	TestEqual(TEXT("the last CamYaw wins"), Yaw, 210.f);
	FString Target, Photo, Start;
	TestTrue(TEXT("CamTarget found"), SailingArgs::LastValue(Line, TEXT("SailingCamTarget="), Target));
	TestEqual(TEXT("CamTarget keeps its commas"), Target, FString(TEXT("0.3,0.6,1.4")));
	TestTrue(TEXT("a quoted PhotoCam is found"), SailingArgs::LastValue(Line, TEXT("SailingPhotoCam="), Photo));
	TestEqual(TEXT("the quotes are stripped"), Photo, FString(TEXT("4.6,1.0,2.2,205,-35")));
	TestTrue(TEXT("a quoted StartAt is found"), SailingArgs::LastValue(Line, TEXT("SailingStartAt="), Start));
	TestEqual(TEXT("StartAt keeps its negative"), Start, FString(TEXT("5864,874,-138")));
	FString None;
	TestFalse(TEXT("a missing key is false"), SailingArgs::LastValue(Line, TEXT("SailingCamWorld="), None));
	// A key is a whole prefix: -SailingCamDistX= is not -SailingCamDist=, and a lone value is not a key.
	float Other = 0.f;
	TestFalse(TEXT("a longer key does not match"), SailingArgs::LastValue(TEXT("-SailingCamDistX=5"), TEXT("SailingCamDist="), Other));
	TestTrue(TEXT("one occurrence still reads"), SailingArgs::LastValue(TEXT("-SailingCamDist=12"), TEXT("SailingCamDist="), Other));
	TestEqual(TEXT("one occurrence's value"), Other, 12.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingStillArgsPhotoPanelTest, "SailingSim.UI.StillArgs.PhotoPanelNoHud", StillArgsFlags)
bool FSailingStillArgsPhotoPanelTest::RunTest(const FString& Parameters)
{
	TestTrue(TEXT("in photo mode the panel shows"), SSailPhotoPanel::ShouldShow(true, true, false, false, false));
	TestFalse(TEXT("-SailingNoHud keeps it out of the still"), SSailPhotoPanel::ShouldShow(true, true, false, false, true));
	TestFalse(TEXT("H hides it"), SSailPhotoPanel::ShouldShow(true, true, true, false, false));
	TestFalse(TEXT("an open menu hides it"), SSailPhotoPanel::ShouldShow(true, true, false, true, false));
	TestFalse(TEXT("out of photo mode it is hidden"), SSailPhotoPanel::ShouldShow(false, true, false, false, false));
	TestFalse(TEXT("without the free camera it is hidden"), SSailPhotoPanel::ShouldShow(true, false, false, false, false));
	return true;
}

#endif
