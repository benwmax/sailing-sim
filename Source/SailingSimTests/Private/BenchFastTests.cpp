#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "HAL/IConsoleManager.h"
#include "UObject/UnrealType.h"
#include "Engine/GameInstance.h"
#include "BenchRunner.h"
#include "SailSession.h"
#include "SailingSettings.h"
#include "BoatModel.h"

#if WITH_DEV_AUTOMATION_TESTS

// Bench-fast (docs/bench-fast): a bench list runs many views in one process. Between views everything a fresh process
// starts with must come back, so the saved-settings leak bench-fix (#48) closed cannot return through the list.

namespace
{
	constexpr EAutomationTestFlags BenchFastFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

	/** Every config property of the settings as text, to compare with the class default object's. */
	TMap<FString, FString> ConfigValues(const USailingSettings* Settings)
	{
		TMap<FString, FString> Out;
		for (TFieldIterator<FProperty> It(USailingSettings::StaticClass()); It; ++It)
		{
			if (!It->HasAnyPropertyFlags(CPF_Config)) continue;
			FString Text;
			It->ExportText_InContainer(0, Text, Settings, Settings, nullptr, PPF_None);
			Out.Add(It->GetName(), Text);
		}
		return Out;
	}

	/** Puts the command line back however a test leaves it. */
	struct FCommandLineGuard
	{
		FString Saved = FCommandLine::Get();
		~FCommandLineGuard() { SailingArgs::SetCommandLine(Saved); }
	};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingBenchListParseTest, "SailingSim.Smoke.BenchList.Parse", BenchFastFlags)
bool FSailingBenchListParseTest::RunTest(const FString&)
{
	const TArray<FSailingBenchView> Views = USailingBenchRunner::ParseList(TEXT("# views\n\nstorm|-SailingWorld=Lake -SailingWeather=Thunderstorm\r\n  helm-eye | -SailingCapture=HelmEye \nbare\n"));
	if (!TestEqual(TEXT("Three views (comments and blank lines skipped)"), Views.Num(), 3)) return false;
	TestEqual(TEXT("Name"), Views[0].Name, FString(TEXT("storm")));
	TestEqual(TEXT("Args"), Views[0].Args, FString(TEXT("-SailingWorld=Lake -SailingWeather=Thunderstorm")));
	TestEqual(TEXT("Trimmed name"), Views[1].Name, FString(TEXT("helm-eye")));
	TestEqual(TEXT("Trimmed args"), Views[1].Args, FString(TEXT("-SailingCapture=HelmEye")));
	TestTrue(TEXT("A name alone has no args"), Views[2].Name == TEXT("bare") && Views[2].Args.IsEmpty());

	// The view's arguments come first (FParse::Value takes the first match); the list and the base's shot are dropped.
	const FString Line = USailingBenchRunner::ViewCommandLine(TEXT("-SailingBenchList=list.txt -SailingBench=12 -SailingShot=screenshot -SailingQuality=High -SailingWorld=Lake -windowed"), Views[0]);
	FString World, Shot, Quality;
	FParse::Value(*Line, TEXT("SailingWorld="), World);
	FParse::Value(*Line, TEXT("SailingShot="), Shot);
	FParse::Value(*Line, TEXT("SailingQuality="), Quality);
	TestEqual(TEXT("The view's world wins"), World, FString(TEXT("Lake")));
	TestEqual(TEXT("The view names the shot"), Shot, FString(TEXT("storm")));
	TestEqual(TEXT("The base's tier stays"), Quality, FString(TEXT("High")));
	TestFalse(TEXT("No list in a view's command line"), Line.Contains(TEXT("SailingBenchList")));
	TestEqual(TEXT("One shot only"), Line.Find(TEXT("SailingShot=")), Line.Find(TEXT("SailingShot="), ESearchCase::IgnoreCase, ESearchDir::FromEnd));
	TestTrue(TEXT("The base's own arguments stay"), Line.Contains(TEXT("-windowed")) && Line.Contains(TEXT("-SailingBench=12")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingBenchListArgsTest, "SailingSim.Smoke.BenchList.ArgsReread", BenchFastFlags)
bool FSailingBenchListArgsTest::RunTest(const FString&)
{
	FCommandLineGuard Guard;
	static SailingArgs::FCachedFlag Flag(TEXT("SailingBenchFastProbe"));
	static SailingArgs::FOnce Once;
	SailingArgs::SetCommandLine(TEXT("-SailingBenchFastProbe -SailingBench=12"));
	TestTrue(TEXT("A flag on the command line reads true"), Flag.Get());
	TestTrue(TEXT("A measuring run"), USailingSettings::IsMeasuring());
	TestTrue(TEXT("A one-off latch fires once"), Once.Take());
	TestFalse(TEXT("... and not twice"), Once.Take());
	// The next view's command line: a fresh process would read the flag and the latch afresh.
	SailingArgs::SetCommandLine(TEXT("-SailingQuality=High"));
	TestFalse(TEXT("The flag is read again after a swap"), Flag.Get());
	TestFalse(TEXT("Not measuring without -SailingBench="), USailingSettings::IsMeasuring());
	TestTrue(TEXT("The latch fires again in the next view"), Once.Take());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingBenchListResetTest, "SailingSim.Smoke.BenchList.ResetsRunState", BenchFastFlags)
bool FSailingBenchListResetTest::RunTest(const FString&)
{
	USailingSettings* S = USailingSettings::Get();
	const TMap<FString, FString> Before = ConfigValues(S);
	// What a measuring process starts from: the class defaults from before any ini was loaded (bench-fix, #48).
	USailingSettings::RestoreClassDefaults();
	const TMap<FString, FString> Defaults = ConfigValues(S);

	// A view (or a player's ini, as #48 found) leaves Galveston, the Lagoon 42, dusk, Low and a fixed resolution behind.
	S->World = 1; S->LaunchSpot = 3; S->BoatType = int32(Sailing::EBoatType::Lagoon42); S->StartHour = 19.5f;
	S->Quality = ESailingQuality::Low; S->ResolutionScale = 70; S->TrafficLevel = 2;
	S->WeatherPreset = ESailingWeather::Thunderstorm;
	// ...and a session started from the menus, with a UI script still to play.
	USailSessionSubsystem* Session = NewObject<USailSessionSubsystem>(NewObject<UGameInstance>());
	Session->Active = USailSessionSubsystem::MakeDefault();
	Session->Active.World = 1;
	Session->Pending = Session->Active;
	Session->bHasActive = Session->bStarted = Session->bUIScriptRead = true;
	Session->UIScript.Add(TEXT("Enter"));
	Session->ResetForRun();

	USailingBenchRunner::ResetRunState(nullptr);
	const TMap<FString, FString> After = ConfigValues(S);
	int32 Differ = 0;
	for (const TPair<FString, FString>& It : Defaults)
	{
		if (After.FindRef(It.Key) != It.Value)
		{
			AddError(FString::Printf(TEXT("%s is %s after the reset, class default %s"), *It.Key, *After.FindRef(It.Key), *It.Value));
			++Differ;
		}
	}
	TestEqual(TEXT("Every config property is back at its class default"), Differ, 0);

	const FSailSessionConfig Fresh;
	TestFalse(TEXT("No session after the reset"), Session->bHasActive || Session->bStarted || Session->bUIScriptRead);
	TestEqual(TEXT("No UI script"), Session->UIScript.Num(), 0);
	TestTrue(TEXT("The pending config is a new one"), FSailSessionConfig::StaticStruct()->CompareScriptStruct(&Session->Pending, &Fresh, PPF_None));
	TestTrue(TEXT("The active config is a new one"), FSailSessionConfig::StaticStruct()->CompareScriptStruct(&Session->Active, &Fresh, PPF_None));

	for (const TPair<FString, FString>& It : Before)
	{
		if (FProperty* P = USailingSettings::StaticClass()->FindPropertyByName(*It.Key)) P->ImportText_InContainer(*It.Value, S, S, PPF_None);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingBenchListCVarsTest, "SailingSim.Smoke.BenchList.RestoresCVars", BenchFastFlags)
bool FSailingBenchListCVarsTest::RunTest(const FString&)
{
	IConsoleVariable* Pct = IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"));
	IConsoleVariable* Samples = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VolumetricCloud.ViewRaySampleMaxCount"));
	if (!TestNotNull(TEXT("r.ScreenPercentage"), Pct) || !TestNotNull(TEXT("r.VolumetricCloud.ViewRaySampleMaxCount"), Samples)) return false;
	const TMap<FString, FString> Snapshot = USailingBenchRunner::SnapshotCVars();
	TestTrue(TEXT("The snapshot holds the engine's variables"), Snapshot.Num() > 1000 && Snapshot.Contains(TEXT("r.ScreenPercentage")));
	const float Pct0 = Pct->GetFloat(), Samples0 = Samples->GetFloat();

	// High's governor lowers the resolution; a view's -SailingCloudSamples sets the march.
	Pct->Set(Pct0 == 82.f ? 85.f : 82.f, ECVF_SetByCode);
	Samples->Set(Samples0 + 17.f, ECVF_SetByCode);
	TSet<FString> Keep;
	const int32 Restored = USailingBenchRunner::RestoreCVars(Snapshot, Keep);
	TestTrue(TEXT("Both changed variables put back"), Restored >= 2);
	TestEqual(TEXT("Resolution back"), Pct->GetFloat(), Pct0);
	TestEqual(TEXT("Cloud samples back"), Samples->GetFloat(), Samples0);
	TestEqual(TEXT("Nothing else differs, so nothing more is set"), USailingBenchRunner::RestoreCVars(Snapshot, Keep), 0);

	// A variable the next StartPlay sets again (the tier's) is left for it.
	Samples->Set(Samples0 + 5.f, ECVF_SetByCode);
	Keep.Add(TEXT("r.VolumetricCloud.ViewRaySampleMaxCount"));
	USailingBenchRunner::RestoreCVars(Snapshot, Keep);
	TestEqual(TEXT("A kept variable is not touched"), Samples->GetFloat(), Samples0 + 5.f);
	Samples->Set(Samples0, ECVF_SetByCode);
	return true;
}

#endif
