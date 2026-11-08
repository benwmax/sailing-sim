#include "Misc/AutomationTest.h"
#include "CourseMarks.h"
#include "Engine/StaticMesh.h"

// Part detail loop (docs/part-detail-loop/marks.md): the course marks and the crew-overboard buoy that replace the
// drills' and races' engine shapes. Once imported they must be the catalogue sizes (Tools/boatkit/bk_part_marks.py) with
// the origin on the waterline: SailboatPawn::UpdateDrillVisuals and ATrafficManager::StartRace place them at the
// water's height with no offset or scale. Skipped (with a note) before the kit is imported with them.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualCourseMarksTest, "SailingSim.Visual.CourseMarks",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FVisualCourseMarksTest::RunTest(const FString& Parameters)
{
	struct FWant { const TCHAR* Part; double Across; double Above; double BelowMax; };
	// cm: across (the smaller of the X and Y extents: the float, not the flag beside the pin's staff), height above the waterline (to the handle / staff tip), deepest point
	const FWant Wants[] = {
		{ TEXT("RaceMark"), 90.0, 137.0, 40.0 },        // 0.90 x 1.50 m, 0.20 m under, handle on top; anchor ring below
		{ TEXT("LessonMark"), 61.0, 114.0, 35.0 },      // 0.61 x 1.22 m (4 ft), 0.15 m under
		{ TEXT("PinBuoy"), 80.0, 134.0, 85.0 },         // 0.80 m ball, staff tip 1.34 m up, weight on the staff's foot
		{ TEXT("HorseshoeBuoy"), 58.5, 7.0, 5.0 },      // 610 x 585 x 100 mm, floating flat about a third under
	};
	int32 Found = 0;
	for (const FWant& W : Wants)
	{
		UStaticMesh* Mesh = CourseMarks::Load(W.Part);
		if (!Mesh)
		{
			AddInfo(FString::Printf(TEXT("SM_Kit_%s not imported yet: the game draws the engine shape"), W.Part));
			continue;
		}
		++Found;
		const FBox B = Mesh->GetBoundingBox();
		const double Across = FMath::Min(B.GetSize().X, B.GetSize().Y);
		TestTrue(FString::Printf(TEXT("%s: %.1f cm across, want %.0f (-6%% to +20%%: seams and flanges stand proud)"), W.Part, Across, W.Across),
			Across > W.Across * 0.94 && Across < W.Across * 1.20);
		TestTrue(FString::Printf(TEXT("%s: top %.1f cm above the waterline, want %.0f (+-5%%)"), W.Part, B.Max.Z, W.Above),
			FMath::Abs(B.Max.Z - W.Above) < W.Above * 0.05 + 0.5);
		TestTrue(FString::Printf(TEXT("%s: floats (bottom %.1f cm, under the waterline but no deeper than %.0f)"), W.Part, B.Min.Z, W.BelowMax),
			B.Min.Z < 0.0 && B.Min.Z > -W.BelowMax);
	}
	if (Found == 0) AddInfo(TEXT("No course marks imported: run make-boatkit -Import on the PC"));
	return true;
}
