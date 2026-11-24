#include "Misc/AutomationTest.h"
#include "FilmMode.h"
#include "ReferenceCapture.h"
#include "VisualPipeline.h"
#include "HAL/FileManager.h"
#include "Misc/App.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace FilmModeTestsLocal
{
	constexpr EAutomationTestFlags FilmFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	FFilmBoatPose TestBoat(double HeadingDeg)
	{
		FFilmBoatPose B;
		B.Origin = FVector(1000.0, 2000.0, 50.0);   // Z: the still water
		B.HeadingDeg = HeadingDeg;
		B.MastheadM = 9.0;
		B.WorldAnchor = FVector(-5000.0, 0.0, 50.0);
		return B;
	}

	double Yaw2D(const FVector& From, const FVector& To)
	{
		return FMath::RadiansToDegrees(FMath::Atan2(To.Y - From.Y, To.X - From.X));
	}
}

// Film mode 1: under a fixed step the recording is counted in frames: 8 s at 1/60 is 480 frames, never 481.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFilmFrameClockTest, "SailingSim.Smoke.FilmMode.FrameClock", FilmModeTestsLocal::FilmFlags)
bool FFilmFrameClockTest::RunTest(const FString& Parameters)
{
	// The reel test's run: -benchmark -fps=60 -SailingBenchWarmup=10 -SailingRecord=8 -SailingRecordInterval=0.0166667.
	const FFilmFrameClock C = FFilmFrameClock::Make(1.0 / 60.0, 10.0, 8.0, 0.0166667);
	TestEqual(TEXT("480 frames for 8 s at 60 fps"), C.Count, 480);
	TestEqual(TEXT("one every frame"), C.Stride, 1);
	TestEqual(TEXT("recording starts after 600 warm-up frames"), C.WarmupFrames, 600);
	int32 Taken = 0, Expected = 0;
	bool bInOrder = true;
	for (int64 F = 0; F < 2000; ++F)
	{
		const int32 I = C.CaptureIndexAt(F);
		if (I < 0) continue;
		bInOrder &= I == Expected++;
		++Taken;
	}
	TestEqual(TEXT("exactly 480 frames come out"), Taken, 480);
	TestTrue(TEXT("numbered 0..479 in order"), bInOrder);
	TestEqual(TEXT("the last is frame 1079"), C.LastFrame(), int64(1079));
	TestEqual(TEXT("nothing in the warm-up"), C.CaptureIndexAt(599), -1);
	TestEqual(TEXT("nothing after the last"), C.CaptureIndexAt(1080), -1);
	TestTrue(TEXT("shot time 0 at the first recorded frame"), FMath::IsNearlyZero(C.ClockAt(600)));
	TestTrue(TEXT("shot time 1 s 60 frames later"), FMath::IsNearlyEqual(C.ClockAt(660), 1.0, 1e-9));
	TestTrue(TEXT("negative in the warm-up"), C.ClockAt(0) < 0.0);

	// 30 fps out of a 60 fps step: every other frame, 240 of them in 8 s.
	const FFilmFrameClock Half = FFilmFrameClock::Make(1.0 / 60.0, 3.0, 8.0, 1.0 / 30.0);
	TestEqual(TEXT("every other frame"), Half.Stride, 2);
	TestEqual(TEXT("240 frames for 8 s at 30"), Half.Count, 240);
	TestEqual(TEXT("frame 181 is between two recorded ones"), Half.CaptureIndexAt(181), -1);
	TestEqual(TEXT("frame 182 is the second"), Half.CaptureIndexAt(182), 1);

	// Slow motion (-SailingSlowMo=0.25): the step is a quarter of the game time, the interval is game time.
	const FFilmFrameClock Slow = FFilmFrameClock::Make(0.25 / 60.0, 1.0, 2.0, 0.25 / 60.0);
	TestEqual(TEXT("slow motion: still one a frame"), Slow.Stride, 1);
	TestEqual(TEXT("slow motion: 480 frames for 2 game seconds"), Slow.Count, 480);
	TestEqual(TEXT("no recording asked, none taken"), FFilmFrameClock::Make(1.0 / 60.0, 3.0, 0.0, 0.1).Count, 0);

	// The game mode counts in frames under -benchmark (the PC's first run: -benchmark -fps=60 leaves UseFixedTimeStep false,
	// so the timed loop ran and wrote 481), and under -UseFixedTimeStep; not in a normal run.
	const bool bWasBenchmarking = FApp::IsBenchmarking(), bWasFixed = FApp::UseFixedTimeStep();
	FApp::SetBenchmarking(false);
	FApp::SetUseFixedTimeStep(false);
	TestFalse(TEXT("a normal run is timed"), FilmUsesFrameClock());
	FApp::SetBenchmarking(true);
	TestTrue(TEXT("-benchmark counts frames"), FilmUsesFrameClock());
	FApp::SetBenchmarking(false);
	FApp::SetUseFixedTimeStep(true);
	TestTrue(TEXT("-UseFixedTimeStep counts frames"), FilmUsesFrameClock());
	FApp::SetBenchmarking(bWasBenchmarking);
	FApp::SetUseFixedTimeStep(bWasFixed);
	return true;
}

// Film mode 2 and 3: motion blur in capture mode when asked; the quality boost names the clouds and reflections.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFilmSwitchesTest, "SailingSim.Smoke.FilmMode.Switches", FilmModeTestsLocal::FilmFlags)
bool FFilmSwitchesTest::RunTest(const FString& Parameters)
{
	TestEqual(TEXT("reference stills keep no blur"), CaptureMotionBlurAmount(TEXT("-SailingCapture=Chase")), 0.f);
	TestEqual(TEXT("film mode: a 180 degree shutter"), CaptureMotionBlurAmount(TEXT("-SailingCapture=Tripod -SailingFilm")), 0.5f);
	TestEqual(TEXT("-SailingMotionBlur wins"), CaptureMotionBlurAmount(TEXT("-SailingFilm -SailingMotionBlur=0.3")), 0.3f);
	TestEqual(TEXT("and is held to 0..1"), CaptureMotionBlurAmount(TEXT("-SailingMotionBlur=4")), 1.f);
	TestEqual(TEXT("-SailingFilmX is not -SailingFilm"), CaptureMotionBlurAmount(TEXT("-SailingFilmX")), 0.f);

	bool bClouds = false, bWater = false;
	for (const FQualityCVar& C : FilmQualityCVars())
	{
		bClouds |= FCString::Strcmp(C.Name, TEXT("r.VolumetricRenderTarget.Mode")) == 0 && C.Value == 0.f;
		bWater |= FCString::Strcmp(C.Name, TEXT("r.Water.SingleLayer.Reflection.DownsampleFactor")) == 0 && C.Value == 1.f;
		TestNotNull(FString::Printf(TEXT("%s exists"), C.Name), IConsoleManager::Get().FindConsoleVariable(C.Name));
	}
	TestTrue(TEXT("clouds rebuilt over frames (mode 0: no stipple in the bases)"), bClouds);
	TestTrue(TEXT("the water's reflections at full resolution"), bWater);

	// The tripod: distance, height and lens from -SailingTripod, defaults for what is left out.
	const FFilmTripod T = FFilmTripod::Parse(TEXT("35,2.5,18,0.3"));
	TestTrue(TEXT("tripod 35 m, 2.5 m up, 18 deg, aimed at 0.3 of the masthead"), T.DistanceM == 35.0 && T.HeightM == 2.5 && T.HFovDeg == 18.0 && T.AimFraction == 0.3);
	const FFilmTripod D = FFilmTripod::Parse(TEXT("60"));
	TestTrue(TEXT("tripod defaults"), D.DistanceM == 60.0 && D.HeightM == 1.6 && D.HFovDeg == 26.0 && D.AimFraction == 0.45);
	{
		// The default frame holds the whole J/22 (waterline to a 9.25 m masthead) at 40 m in 16:9.
		const FFilmTripod Def;
		const double VHalf = FMath::Atan(FMath::Tan(FMath::DegreesToRadians(0.5 * Def.HFovDeg)) * 9.0 / 16.0);
		const double Aim = Def.AimFraction * 9.25, Reach = Def.DistanceM * FMath::Tan(VHalf);
		TestTrue(FString::Printf(TEXT("default frame %.1f..%.1f m holds 0..9.25 m"), Aim - Reach, Aim + Reach), Aim - Reach < 0.0 && Aim + Reach > 9.25);
	}
	TestEqual(TEXT("Tripod by name"), ParseCapturePreset(TEXT("tripod")), ECapturePreset::Tripod);
	TestEqual(TEXT("Path by name"), ParseCapturePreset(TEXT("Path")), ECapturePreset::Path);
	TestFalse(TEXT("film cameras are not onboard"), CapturePresetInfo(ECapturePreset::Tripod).bOnboard || CapturePresetInfo(ECapturePreset::Path).bOnboard);

	// The tripod's stand: the chosen range and height off the boat, aimed at her.
	const FVector Boat(1000.0, 2000.0, 0.0);
	FVector L;
	FRotator R;
	WorldCameraPoseAt(Boat, 0.f, 90.f, 40.f, 1.6f, 0.33f, 9.25f, 0.f, L, R);
	TestTrue(TEXT("40 m off"), FMath::IsNearlyEqual(FVector2D(L - Boat).Size(), 4000.0, 1.0));
	TestTrue(TEXT("1.6 m up"), FMath::IsNearlyEqual(L.Z, 160.0, 0.1));
	TestTrue(TEXT("on her starboard beam"), FMath::IsNearlyEqual(L.Y - Boat.Y, 4000.0, 1.0));
	TestTrue(TEXT("looking at her"), FMath::IsNearlyEqual(R.Yaw, -90.f, 0.1f));
	return true;
}

// Film mode 5: shot files.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFilmShotParseTest, "SailingSim.Smoke.FilmMode.ShotParse", FilmModeTestsLocal::FilmFlags)
bool FFilmShotParseTest::RunTest(const FString& Parameters)
{
	FFilmShot S;
	FString Err;
	TestTrue(TEXT("a two-key orbit parses"), S.Parse(TEXT(R"({"frame":"boat","fov":35,"keys":[{"t":0,"orbit":[-90,20,2]},{"t":6,"orbit":[0,20,2],"fov":30,"ease":"linear"}]})"), Err));
	TestEqual(TEXT("two keys"), S.Keys.Num(), 2);
	TestTrue(TEXT("the shot's fov is every key's default"), S.Keys.Num() == 2 && S.Keys[0].HFovDeg == 35.0 && S.Keys[1].HFovDeg == 30.0);
	TestTrue(TEXT("ease in-out by default, linear when named"), S.Keys.Num() == 2 && S.Keys[0].Ease == EFilmEase::InOut && S.Keys[1].Ease == EFilmEase::Linear);
	TestTrue(TEXT("six seconds long"), S.Duration() == 6.0);

	TestTrue(TEXT("a world pan parses"), S.Parse(TEXT(R"({"frame":"world","path":"smooth","keys":[{"t":0,"pos":[10,0,3],"look":[-2,90,0]},{"t":4,"pos":[10,0,3],"look":[-2,140,0]}]})"), Err));
	TestTrue(TEXT("world frame, smooth path, fixed look"), S.Frame == EFilmFrame::World && S.bSmooth && !S.Keys[0].bLookAtBoat);

	struct FBad { const TCHAR* Json; const TCHAR* Why; };
	const FBad Bad[] = {
		{ TEXT("not json"), TEXT("not JSON") },
		{ TEXT(R"({"keys":[]})"), TEXT("no keys") },
		{ TEXT(R"({"keys":[{"pos":[0,0,1]}]})"), TEXT("a key without a time") },
		{ TEXT(R"({"keys":[{"t":2,"pos":[0,0,1]},{"t":1,"pos":[0,0,1]}]})"), TEXT("times going back") },
		{ TEXT(R"({"keys":[{"t":0}]})"), TEXT("a key without a place") },
		{ TEXT(R"({"keys":[{"t":0,"pos":[0,1]}]})"), TEXT("a place with two numbers") },
		{ TEXT(R"({"frame":"mount","keys":[{"t":0,"orbit":[0,10,2]}]})"), TEXT("an orbit on a mount") },
		{ TEXT(R"({"frame":"drone","keys":[{"t":0,"pos":[0,0,1]}]})"), TEXT("an unknown frame") },
		{ TEXT(R"({"keys":[{"t":0,"pos":[0,0,1],"ease":"bounce"}]})"), TEXT("an unknown ease") },
		{ TEXT(R"({"keys":[{"t":0,"pos":[0,0,1],"look":"sky"}]})"), TEXT("an unknown look") },
		{ TEXT(R"({"keys":[{"t":0,"pos":[0,0,1],"fov":0}]})"), TEXT("no field of view") },
	};
	for (const FBad& B : Bad)
	{
		FString E;
		TestFalse(FString::Printf(TEXT("refused: %s"), B.Why), S.Parse(B.Json, E));
		TestFalse(FString::Printf(TEXT("with a reason: %s"), B.Why), E.IsEmpty());
	}

	// From a file, as -SailingShotFile reads it.
	const FString Path = FPaths::ProjectSavedDir() / TEXT("Automation/film-shot-test.json");
	FFileHelper::SaveStringToFile(FString(TEXT(R"({"keys":[{"t":0,"pos":[-12,4,2]}]})")), *Path);
	TestTrue(TEXT("loads from a file"), S.Load(Path, Err) && S.Keys.Num() == 1);
	IFileManager::Get().Delete(*Path);
	TestFalse(TEXT("a missing file says so"), S.Load(Path, Err));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFilmShotMovesTest, "SailingSim.Smoke.FilmMode.ShotMoves", FilmModeTestsLocal::FilmFlags)
bool FFilmShotMovesTest::RunTest(const FString& Parameters)
{
	using namespace FilmModeTestsLocal;
	TestTrue(TEXT("ease starts at 0"), FilmEase(EFilmEase::InOut, 0.0) == 0.0 && FilmEase(EFilmEase::In, 0.0) == 0.0);
	TestTrue(TEXT("ease ends at 1"), FilmEase(EFilmEase::InOut, 1.0) == 1.0 && FilmEase(EFilmEase::Out, 1.0) == 1.0);
	TestTrue(TEXT("in-out is half way at half time"), FMath::IsNearlyEqual(FilmEase(EFilmEase::InOut, 0.5), 0.5));
	TestTrue(TEXT("in starts slow, out ends slow"), FilmEase(EFilmEase::In, 0.1) < 0.1 && FilmEase(EFilmEase::Out, 0.9) > 0.9);

	FFilmShot S;
	FString Err;
	// Orbit: from her port beam to dead ahead, 20 m off and 2 m up, round her (not through her).
	S.Parse(TEXT(R"({"frame":"boat","keys":[{"t":0,"orbit":[-90,20,2],"fov":40},{"t":10,"orbit":[0,20,2],"fov":20}]})"), Err);
	const FFilmBoatPose B = TestBoat(30.0);
	const FFilmCameraPose Start = S.Evaluate(0.0, B), Mid = S.Evaluate(5.0, B), End = S.Evaluate(10.0, B);
	TestTrue(TEXT("held before the first key"), S.Evaluate(-3.0, B).Location.Equals(Start.Location, 0.01));
	TestTrue(TEXT("held after the last key"), S.Evaluate(30.0, B).Location.Equals(End.Location, 0.01));
	TestTrue(FString::Printf(TEXT("starts on her port beam (bearing %.1f)"), Yaw2D(B.Origin, Start.Location)), FMath::IsNearlyEqual(Yaw2D(B.Origin, Start.Location), -60.0, 0.1));
	TestTrue(TEXT("ends ahead of her"), FMath::IsNearlyEqual(Yaw2D(B.Origin, End.Location), 30.0, 0.1));
	TestTrue(TEXT("half way round at half time (in-out)"), FMath::IsNearlyEqual(Yaw2D(B.Origin, Mid.Location), -15.0, 0.1));
	TestTrue(TEXT("20 m off all the way"), FMath::IsNearlyEqual(FVector2D(Mid.Location - B.Origin).Size(), 2000.0, 1.0));
	TestTrue(TEXT("2 m over the water"), FMath::IsNearlyEqual(Mid.Location.Z, B.Origin.Z + 200.0, 0.1));
	TestTrue(TEXT("the lens zooms between the keys"), FMath::IsNearlyEqual(Mid.HFovDeg, 30.0, 0.01));
	TestTrue(TEXT("looking at her"), FMath::IsNearlyEqual(Mid.Rotation.Yaw, float(Yaw2D(Mid.Location, B.Origin)), 0.1f));
	TestFalse(TEXT("not on a mount"), Mid.bRelativeToHull);
	// The bearing goes the short way: from 170 to -170 crosses dead astern, not the bow.
	S.Parse(TEXT(R"({"keys":[{"t":0,"orbit":[170,20,2],"ease":"linear"},{"t":2,"orbit":[-170,20,2]}]})"), Err);
	TestTrue(TEXT("round the stern, the short way"), FMath::IsNearlyEqual(FMath::Abs(Yaw2D(B.Origin, S.Evaluate(1.0, TestBoat(0.0)).Location)), 180.0, 0.1));

	// Dolly and crane in her frame: from 15 m astern to 5 m astern and from 1 to 6 m up, turning with her heading.
	S.Parse(TEXT(R"({"frame":"boat","keys":[{"t":0,"pos":[-15,0,1],"ease":"linear"},{"t":2,"pos":[-5,0,6]}]})"), Err);
	const FFilmBoatPose East = TestBoat(90.0);
	const FFilmCameraPose D = S.Evaluate(1.0, East);
	TestTrue(TEXT("dead astern of a boat heading east is west of her"), FMath::IsNearlyEqual(D.Location.Y, East.Origin.Y - 1000.0, 0.1) && FMath::IsNearlyEqual(D.Location.X, East.Origin.X, 0.1));
	TestTrue(TEXT("half way up"), FMath::IsNearlyEqual(D.Location.Z, East.Origin.Z + 350.0, 0.1));

	// A pan from a world stand: the camera stays, the look turns from 090 to 140.
	S.Parse(TEXT(R"({"frame":"world","keys":[{"t":0,"pos":[10,20,3],"look":[-2,90,0],"ease":"linear"},{"t":4,"pos":[10,20,3],"look":[-2,140,0]}]})"), Err);
	const FFilmCameraPose P0 = S.Evaluate(0.0, B), P1 = S.Evaluate(2.0, B);
	TestTrue(TEXT("the stand is the start plus north/east/up"), P0.Location.Equals(B.WorldAnchor + FVector(1000.0, 2000.0, 300.0), 0.01));
	TestTrue(TEXT("the stand doesn't move"), P1.Location.Equals(P0.Location, 0.01));
	TestTrue(FString::Printf(TEXT("pans half way (%.1f)"), P1.Rotation.Yaw), FMath::IsNearlyEqual(P1.Rotation.Yaw, 115.f, 0.1f) && FMath::IsNearlyEqual(P1.Rotation.Pitch, -2.f, 0.1f));
	TestTrue(TEXT("a world look ignores her heading"), FMath::IsNearlyEqual(S.Evaluate(0.0, TestBoat(200.0)).Rotation.Yaw, 90.f, 0.1f));

	// A locked mount: placed and turned in the hull's frame.
	S.Parse(TEXT(R"({"frame":"mount","keys":[{"t":0,"pos":[-3.2,0.4,1.1],"look":[-5,0,0]}]})"), Err);
	const FFilmCameraPose M = S.Evaluate(1.0, B);
	TestTrue(TEXT("relative to the hull"), M.bRelativeToHull);
	TestTrue(TEXT("at the mount (cm)"), M.Location.Equals(FVector(-320.0, 40.0, 110.0), 0.01));
	TestTrue(TEXT("turned as the mount is"), FMath::IsNearlyEqual(M.Rotation.Pitch, -5.f, 0.01f) && FMath::IsNearlyEqual(M.Rotation.Yaw, 0.f, 0.01f));

	// A smooth path goes through every key.
	S.Parse(TEXT(R"({"path":"smooth","keys":[{"t":0,"pos":[-20,10,2]},{"t":2,"pos":[0,15,3]},{"t":4,"pos":[20,10,8]}]})"), Err);
	const FFilmBoatPose N = TestBoat(0.0);
	TestTrue(TEXT("through the middle key"), S.Evaluate(2.0, N).Location.Equals(N.Origin + FVector(0.0, 1500.0, 300.0), 0.01));
	TestTrue(TEXT("through the last"), S.Evaluate(4.0, N).Location.Equals(N.Origin + FVector(2000.0, 1000.0, 800.0), 0.01));
	// Framing off centre: the aim offset turns the look from her.
	S.Parse(TEXT(R"({"keys":[{"t":0,"pos":[0,-20,2],"aim_offset":[0,10,0],"aim_up":2}]})"), Err);
	const FFilmCameraPose O = S.Evaluate(0.0, N);
	TestTrue(FString::Printf(TEXT("aimed 10 deg right of her (%.1f)"), O.Rotation.Yaw), FMath::IsNearlyEqual(O.Rotation.Yaw, 100.f, 0.1f));
	TestTrue(TEXT("level when aimed at her height"), FMath::IsNearlyEqual(O.Rotation.Pitch, 0.f, 0.1f));
	return true;
}

#endif
