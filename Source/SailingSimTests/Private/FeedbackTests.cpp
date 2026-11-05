#include "Misc/AutomationTest.h"
#include "Feedback.h"
#include "CrashReports.h"
#include "SessionLog.h"
#include "SailingSim.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "Modules/ModuleManager.h"
#include "Math/RandomStream.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"

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

// pc/feedback-send (Nov 4: Bean's two bug reports stayed on the PC): a report is sent with Send crash reports off, on its
// own, not through the SDK (which, without consent, caches every envelope and sends the lot on a later yes): the choice,
// the DSN's endpoint and auth, and the envelope (one feedback item with the message and tags, an item per attachment,
// lengths that match). The screen's answer never sends the player to that setting.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailFeedbackSendsWithoutConsentTest, "SailingSim.UI.Feedback.SendsWithCrashReportsOff", SailFeedbackTestsLocal::Flags_)
bool FSailFeedbackSendsWithoutConsentTest::RunTest(const FString&)
{
	TestTrue(TEXT("consent required, crash reports off: on its own"), SailCrashReports::SendsOnItsOwn(true, false));
	TestFalse(TEXT("crash reports on: the SDK"), SailCrashReports::SendsOnItsOwn(true, true));
	TestFalse(TEXT("no consent asked: the SDK"), SailCrashReports::SendsOnItsOwn(false, false));
	// The Feedback screen's gate: with Send crash reports off a build with a crash reporter still sends (it used to keep the
	// report on the PC); a build without one can't.
	TestTrue(TEXT("crash reports off: the report is sent"), SailFeedback::SendsReport(false, true));
	TestTrue(TEXT("crash reports on: sent"), SailFeedback::SendsReport(true, true));
	TestFalse(TEXT("no crash reporter in the build: kept here"), SailFeedback::SendsReport(false, false) || SailFeedback::SendsReport(true, false));
	TestEqual(TEXT("sent"), SailFeedback::ResultLine(EFeedbackSend::Sent), FString(TEXT("Sent. Thank you!")));
	TestTrue(TEXT("sending: says so, and that a copy stays"), SailFeedback::ResultLine(EFeedbackSend::Sending).StartsWith(TEXT("Sending")) && SailFeedback::ResultLine(EFeedbackSend::Sending).Contains(TEXT("copy")));
	TestFalse(TEXT("saved: no pointer to Send crash reports"), SailFeedback::ResultLine(EFeedbackSend::Saved).Contains(TEXT("crash reports")));

	SailFeedback::FSentryDsn D;
	TestTrue(TEXT("a DSN parses"), D.Parse(TEXT("https://abc123@o42.ingest.example.io/7")));
	TestEqual(TEXT("endpoint"), D.EnvelopeUrl(), FString(TEXT("https://o42.ingest.example.io/api/7/envelope/")));
	TestTrue(TEXT("auth carries the key"), D.AuthHeader().Contains(TEXT("sentry_key=abc123")) && D.AuthHeader().StartsWith(TEXT("Sentry sentry_version=7")));
	SailFeedback::FSentryDsn D2;
	TestTrue(TEXT("a path before the project"), D2.Parse(TEXT("http://k:secret@host:9000/sub/12")) && D2.EnvelopeUrl() == TEXT("http://host:9000/sub/api/12/envelope/") && D2.PublicKey == TEXT("k"));
	SailFeedback::FSentryDsn D3;
	TestTrue(TEXT("a trailing slash"), D3.Parse(TEXT("https://k@host/12/")) && D3.EnvelopeUrl() == TEXT("https://host/api/12/envelope/"));
	SailFeedback::FSentryDsn Bad;
	TestFalse(TEXT("\"https:\" is not a DSN"), Bad.Parse(TEXT("https:")));
	TestFalse(TEXT("empty is not a DSN"), Bad.Parse(FString()));

	TMap<FString, FString> Tags;
	Tags.Add(TEXT("feedback_kind"), TEXT("bug"));
	TArray<SailFeedback::FEnvelopeAttachment> Files;
	Files.Add({ TEXT("shot1.jpg"), TEXT("image/jpeg"), TArray<uint8>({ 0xFF, 0xD8, 0x0A, 0xFF, 0xD9 }) });   // a newline inside: lengths, not lines
	const TArray<uint8> Env = SailFeedback::FeedbackEnvelope(TEXT("0123456789abcdef0123456789abcdef"), 1762300000.5, TEXT("[Bug] \"quoted\"\nline two"),
		Tags, TEXT("sailing-sim@abc"), TEXT("tester"), Files);
	// Walk it as Sentry does: a header line, then per item a header line with "length" and that many bytes and a newline.
	int32 At = 0;
	auto Line = [&Env, &At]() { int32 E = At; while (E < Env.Num() && Env[E] != '\n') ++E; const FString S = FString(FUTF8ToTCHAR((const ANSICHAR*)Env.GetData() + At, E - At)); At = E + 1; return S; };
	TSharedPtr<FJsonObject> Head;
	TestTrue(TEXT("envelope header"), FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Line()), Head) && Head->GetStringField(TEXT("event_id")) == TEXT("0123456789abcdef0123456789abcdef"));
	TArray<FString> Types;
	TSharedPtr<FJsonObject> Event;
	while (At < Env.Num())
	{
		TSharedPtr<FJsonObject> ItemHead;
		if (!TestTrue(TEXT("item header"), FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Line()), ItemHead))) break;
		const int32 Len = int32(ItemHead->GetNumberField(TEXT("length")));
		if (!TestTrue(TEXT("length within the envelope"), At + Len <= Env.Num())) break;
		Types.Add(ItemHead->GetStringField(TEXT("type")));
		if (Types.Last() == TEXT("feedback"))
			FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(FString(FUTF8ToTCHAR((const ANSICHAR*)Env.GetData() + At, Len))), Event);
		if (Types.Last() == TEXT("attachment")) TestTrue(TEXT("attachment bytes intact"), FMemory::Memcmp(Env.GetData() + At, Files[0].Bytes.GetData(), Len) == 0 && ItemHead->GetStringField(TEXT("filename")) == TEXT("shot1.jpg"));
		At += Len;
		TestTrue(TEXT("a newline after each item"), At < Env.Num() && Env[At] == '\n');
		++At;
	}
	TestTrue(TEXT("one feedback item, then the attachment"), Types.Num() == 2 && Types[0] == TEXT("feedback") && Types[1] == TEXT("attachment"));
	TestTrue(TEXT("the message survives quoting"), Event.IsValid() && Event->GetObjectField(TEXT("contexts"))->GetObjectField(TEXT("feedback"))->GetStringField(TEXT("message")) == TEXT("[Bug] \"quoted\"\nline two"));
	TestTrue(TEXT("tags, release and environment"), Event.IsValid() && Event->GetObjectField(TEXT("tags"))->GetStringField(TEXT("feedback_kind")) == TEXT("bug")
		&& Event->GetStringField(TEXT("release")) == TEXT("sailing-sim@abc") && Event->GetStringField(TEXT("environment")) == TEXT("tester"));
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

	TestTrue(TEXT("no SDK in the editor's tests: nothing sent"), SailCrashReports::SendFeedback(Bug) == EFeedbackSend::Saved);
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

/**
 * The game's session log (docs/session-log/), which Shipping keeps where it has no engine log: SAIL_LOG lines and events
 * land in it with the time since launch, the tail reads them back, paths lose the user's name and e-mail addresses go,
 * each launch rotates the last ones, and a launch's log stops at its cap.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailSessionLogTest, "SailingSim.Feedback.SessionLog", SailFeedbackTestsLocal::Flags_)
bool FSailSessionLogTest::RunTest(const FString&)
{
	const FString Dir = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("Automation/SessionLog"));
	IFileManager::Get().DeleteDirectory(*Dir, false, true);
	const FString Was = SailSessionLog::OpenIn(Dir, true);
	// What SAIL_LOG writes to the session log (its UE_LOG half needs LogSailing, which the game module keeps to itself).
	SailSessionLogLine(TEXT("Display"), FString::Printf(TEXT("Session: world %s, boat %s"), TEXT("ray-hubbard"), TEXT("J22")));
	SailSessionLogLine(TEXT("Warning"), TEXT("Save: could not write /Users/dana/Library/Containers/x/profile.json"));
	SailSessionLog::Write(TEXT("Error"), TEXT("C:\\Users\\Dana Smith\\AppData\\Local\\SailingSim\\Saved for dana.smith@example.com"));
	SailSessionLog::Write(TEXT("Display"), TEXT("Drill: Leave the dock started\nwith a second line"));
	const FString Tail = SailSessionLog::Tail(20);
	AddInfo(Tail);
	TestTrue(TEXT("The header names the game and the build"), Tail.Contains(TEXT("Ready About: Sailing session log")) && Tail.Contains(TEXT("Build ")));
	TestTrue(TEXT("A Display line, no level shown"), Tail.Contains(TEXT("] Session: world ray-hubbard, boat J22")));
	TestTrue(TEXT("A warning says so"), Tail.Contains(TEXT("] Warning: Save: could not write ~/Library")));
	TestTrue(TEXT("An error says so"), Tail.Contains(TEXT("] Error: ~\\AppData")));
	TestFalse(TEXT("No user name"), Tail.Contains(TEXT("dana")) || Tail.Contains(TEXT("Dana")));
	TestTrue(TEXT("No e-mail address"), !Tail.Contains(TEXT("example.com")) && Tail.Contains(TEXT("<email>")));
	TestTrue(TEXT("One line per event"), Tail.Contains(TEXT("started with a second line")));
	TestTrue(TEXT("Times since launch"), Tail.Contains(TEXT("[+")));
	TestTrue(TEXT("The tail is a tail"), SailSessionLog::Tail(2).Contains(TEXT("Drill: Leave the dock")) && !SailSessionLog::Tail(2).Contains(TEXT("Session:")));
	// Each launch rotates: the last KeepLaunches kept.
	for (int32 I = 0; I < SailSessionLog::KeepLaunches + 1; ++I)
	{
		SailSessionLog::OpenIn(Dir, true);
		SailSessionLog::Write(TEXT("Display"), FString::Printf(TEXT("launch %d"), I));
	}
	TestTrue(TEXT("The oldest kept launch is there"), IFileManager::Get().FileExists(*(Dir / FString::Printf(TEXT("session-%d.txt"), SailSessionLog::KeepLaunches - 1))));
	TestFalse(TEXT("... and none older"), IFileManager::Get().FileExists(*(Dir / FString::Printf(TEXT("session-%d.txt"), SailSessionLog::KeepLaunches))));
	FString Prev;
	FFileHelper::LoadFileToString(Prev, *(Dir / TEXT("session-1.txt")));
	TestTrue(TEXT("The previous launch is session-1"), Prev.Contains(FString::Printf(TEXT("launch %d"), SailSessionLog::KeepLaunches - 1)));
	// A launch's log stops at its cap, with a note.
	const FString Big = FString::ChrN(1000, 'x');
	for (int32 I = 0; I < int32(SailSessionLog::MaxBytes / 1000) + 10; ++I) SailSessionLog::Write(TEXT("Display"), Big);
	TestTrue(TEXT("Capped"), IFileManager::Get().FileSize(*SailSessionLog::Path()) <= SailSessionLog::MaxBytes + 200);
	TestTrue(TEXT("... with a note"), SailSessionLog::Tail(1).Contains(TEXT("log full")));
	// The report's log: this build's engine log in the editor (it has one), the session log where it doesn't.
	TestFalse(TEXT("The report has a log"), SailSessionLog::ReportLogPath().IsEmpty());
	SailSessionLog::OpenIn(Was, false);   // the editor's own session log again, appended to
	IFileManager::Get().DeleteDirectory(*Dir, false, true);
	return true;
}
