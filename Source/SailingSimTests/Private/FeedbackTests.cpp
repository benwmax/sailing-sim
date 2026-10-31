#include "Misc/AutomationTest.h"
#include "Feedback.h"
#include "CrashReports.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "Modules/ModuleManager.h"
#include "Math/RandomStream.h"

// Testers' bug and idea reports (docs/sentry, #410): the recorder keeps the last minute, paths lose the user's name, an
// idea carries no place unless asked, and a report written to disk holds what it should.
namespace SailFeedbackTestsLocal
{
	constexpr EAutomationTestFlags Flags_ = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailFeedbackRecorderTest, "SailingSim.UI.Feedback.Recorder", SailFeedbackTestsLocal::Flags_)
bool FSailFeedbackRecorderTest::RunTest(const FString&)
{
	FFeedbackRecorder R;
	for (int32 I = 0; I <= 1200; ++I) // 120 s at 10 Hz
	{
		FFeedbackSample S;
		S.T = I * 0.1;
		S.SpeedKn = 5.0;
		R.Offer(S);
	}
	const TArray<FFeedbackSample>& Got = R.GetSamples();
	TestTrue(TEXT("about two a second"), Got.Num() >= 119 && Got.Num() <= 122);
	TestTrue(TEXT("the last minute only"), Got.Last().T - Got[0].T <= FFeedbackRecorder::KeepSeconds + 1e-6);
	TestTrue(TEXT("newest kept"), FMath::IsNearlyEqual(Got.Last().T, 120.0, 0.11));
	FFeedbackSample Back;
	Back.T = 1.0; // a restart: the clock went back
	R.Offer(Back);
	TestEqual(TEXT("a restart starts again"), R.GetSamples().Num(), 1);
	TestTrue(TEXT("json"), R.ToJson().StartsWith(TEXT("{\"interval_s\": 0.5, \"samples\": [")) && R.ToJson().Contains(TEXT("\"t_s\": 1.0")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailFeedbackScrubTest, "SailingSim.UI.Feedback.Scrub", SailFeedbackTestsLocal::Flags_)
bool FSailFeedbackScrubTest::RunTest(const FString&)
{
	TestEqual(TEXT("mac"), SailFeedback::ScrubPaths(TEXT("open /Users/dana/Library/Logs/x.log failed")), FString(TEXT("open ~/Library/Logs/x.log failed")));
	TestEqual(TEXT("windows, a space in the name"), SailFeedback::ScrubPaths(TEXT("at C:\\Users\\Dana Smith\\AppData\\x")), FString(TEXT("at ~\\AppData\\x")));
	TestEqual(TEXT("windows, no space"), SailFeedback::ScrubPaths(TEXT("at C:\\Users\\dana\\AppData\\x")), FString(TEXT("at ~\\AppData\\x")));
	TestEqual(TEXT("linux"), SailFeedback::ScrubPaths(TEXT("/home/dana/game")), FString(TEXT("~/game")));
	TestEqual(TEXT("the shared folder stays"), SailFeedback::ScrubPaths(TEXT("/Users/Shared/Epic Games")), FString(TEXT("~/Epic Games")));
	TestEqual(TEXT("nothing to scrub"), SailFeedback::ScrubPaths(TEXT("Saved/Feedback")), FString(TEXT("Saved/Feedback")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailFeedbackReportTest, "SailingSim.UI.Feedback.Report", SailFeedbackTestsLocal::Flags_)
bool FSailFeedbackReportTest::RunTest(const FString&)
{
	FFeedbackSample At;
	At.North = 120.0; At.East = -45.0; At.HeadingDeg = 270.0; At.TwaDeg = 60.0;
	const FString Repro = SailFeedback::ReproArgs(TEXT("ray-hubbard"), TEXT("J22"), At, 9.6);
	TestTrue(TEXT("repro start"), Repro.Contains(TEXT("\"-SailingStartAt=120,-45,270\"")));
	TestTrue(TEXT("repro world and boat"), Repro.Contains(TEXT("-SailingWorld=ray-hubbard")) && Repro.Contains(TEXT("-SailingBoat=J22")));

	FFeedbackReport Idea;
	Idea.Kind = EFeedbackKind::Idea;
	Idea.Title = TEXT("A tide arrow");
	Idea.WhatHappened = TEXT("Show the current on the HUD.");
	Idea.Expected = TEXT("ignored for ideas");
	Idea.Repro = Repro;
	Idea.TelemetryJson = TEXT("{}");
	Idea.LogTail = TEXT("log line\n");
	const FString IdeaText = SailFeedback::ComposeMessage(Idea);
	TestTrue(TEXT("idea header"), IdeaText.StartsWith(TEXT("[Idea] A tide arrow")));
	TestFalse(TEXT("idea: no expected"), IdeaText.Contains(TEXT("Expected:")));
	TestFalse(TEXT("idea: no place unless asked"), IdeaText.Contains(TEXT("Repro:")));
	Idea.bAttachPlace = true;
	TestTrue(TEXT("idea: place when asked"), SailFeedback::ComposeMessage(Idea).Contains(TEXT("Repro:")));

	FFeedbackReport Bug;
	Bug.Title = TEXT("Stuck in irons");
	Bug.WhatHappened = TEXT("The boat stopped at /Users/dana/x");
	Bug.Expected = TEXT("She should bear away");
	Bug.Context.Add({ TEXT("World"), TEXT("ray-hubbard") });
	Bug.TelemetryJson = TEXT("{}");
	Bug.Tags.Add(TEXT("boat"), TEXT("J22"));
	Bug.LogTail = TEXT("LogSailing: /Users/dana/Saved\n");
	const FString BugText = SailFeedback::ComposeMessage(Bug);
	TestTrue(TEXT("bug header"), BugText.StartsWith(TEXT("[Bug] Stuck in irons")));
	TestTrue(TEXT("bug expected"), BugText.Contains(TEXT("Expected:\nShe should bear away")));
	TestTrue(TEXT("bug context"), BugText.Contains(TEXT("World: ray-hubbard")));
	TestFalse(TEXT("bug scrubbed"), BugText.Contains(TEXT("dana")));
	TestEqual(TEXT("kinds"), FString(SailFeedback::KindId(EFeedbackKind::Idea)), FString(TEXT("idea")));

	const FString Dir = FPaths::ConvertRelativePathToFull(FPaths::AutomationTransientDir() / TEXT("SailFeedback"));
	IFileManager::Get().DeleteDirectory(*Dir, false, true);
	const FString Folder = SailFeedback::WriteLocal(Bug, Dir);
	TestFalse(TEXT("written"), Folder.IsEmpty());
	FString Log;
	TestTrue(TEXT("report.txt"), IFileManager::Get().FileExists(*FPaths::Combine(Folder, TEXT("report.txt"))));
	TestTrue(TEXT("telemetry.json"), IFileManager::Get().FileExists(*FPaths::Combine(Folder, TEXT("telemetry.json"))));
	FString TagsJson;
	TestTrue(TEXT("tags.json"), FFileHelper::LoadFileToString(TagsJson, *FPaths::Combine(Folder, TEXT("tags.json"))) && TagsJson.Contains(TEXT("\"boat\": \"J22\"")));
	TestTrue(TEXT("log.txt read"), FFileHelper::LoadFileToString(Log, *FPaths::Combine(Folder, TEXT("log.txt"))));
	TestFalse(TEXT("log scrubbed"), Log.Contains(TEXT("dana")));
	TestTrue(TEXT("folder named for the kind"), Folder.EndsWith(TEXT("-bug")));
	FFeedbackReport Bare;
	Bare.Kind = EFeedbackKind::Idea;
	Bare.Title = TEXT("x");
	Bare.TelemetryJson = TEXT("{}");
	const FString IdeaFolder = SailFeedback::WriteLocal(Bare, Dir);
	TestFalse(TEXT("idea without place: no samples"), IFileManager::Get().FileExists(*FPaths::Combine(IdeaFolder, TEXT("telemetry.json"))));
	IFileManager::Get().DeleteDirectory(*Dir, false, true);

	TestFalse(TEXT("no SDK in the editor's tests: nothing sent"), SailCrashReports::SendFeedback(Bug));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailFeedbackJpegTest, "SailingSim.UI.Feedback.Jpeg", SailFeedbackTestsLocal::Flags_)
bool FSailFeedbackJpegTest::RunTest(const FString&)
{
	// A noisy 512x512 shot: a JPEG under 8 MB at once, and under a tiny cap only after halving.
	IImageWrapperModule& Images = FModuleManager::LoadModuleChecked<IImageWrapperModule>(TEXT("ImageWrapper"));
	const int32 N = 512;
	TArray<uint8> Raw;
	Raw.SetNumUninitialized(N * N * 4);
	FRandomStream Rng(410);
	for (int32 I = 0; I < N * N; ++I)
	{
		Raw[4 * I] = uint8(Rng.RandRange(0, 255)); Raw[4 * I + 1] = uint8((I / N) % 256); Raw[4 * I + 2] = uint8(I % 256); Raw[4 * I + 3] = 255;
	}
	TSharedPtr<IImageWrapper> Png = Images.CreateImageWrapper(EImageFormat::PNG);
	TestTrue(TEXT("png made"), Png->SetRaw(Raw.GetData(), Raw.Num(), N, N, ERGBFormat::BGRA, 8));
	const FString Dir = FPaths::ConvertRelativePathToFull(FPaths::AutomationTransientDir() / TEXT("SailFeedbackJpeg"));
	IFileManager::Get().MakeDirectory(*Dir, true);
	const FString PngPath = Dir / TEXT("shot.png"), JpegPath = Dir / TEXT("shot.jpg");
	TestTrue(TEXT("png saved"), FFileHelper::SaveArrayToFile(Png->GetCompressed(), *PngPath));
	TestTrue(TEXT("jpeg under 8 MB"), SailFeedback::ShotToJpeg(PngPath, JpegPath) && IFileManager::Get().FileSize(*JpegPath) > 0);
	TestTrue(TEXT("jpeg under 40 kB after halving"), SailFeedback::ShotToJpeg(PngPath, JpegPath, 40 * 1024) && IFileManager::Get().FileSize(*JpegPath) <= 40 * 1024);
	TestFalse(TEXT("no png, no jpeg"), SailFeedback::ShotToJpeg(Dir / TEXT("missing.png"), JpegPath));
	IFileManager::Get().DeleteDirectory(*Dir, false, true);
	return true;
}
