#include "BenchRunner.h"
#include "SailingSettings.h"
#include "SailSession.h"
#include "VisualPipeline.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformTime.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

DEFINE_LOG_CATEGORY_STATIC(LogSailingBench, Log, All);

namespace SailingArgs
{
	namespace
	{
		std::atomic<uint32> GGeneration{ 0 };
	}

	uint32 Generation()
	{
		return GGeneration.load(std::memory_order_acquire);
	}

	void SetCommandLine(const FString& CommandLine)
	{
		FCommandLine::Set(*CommandLine);
		GGeneration.fetch_add(1, std::memory_order_acq_rel);
	}

	FString ShippingSmokeArgs(const TCHAR* CommandLine)
	{
		if (!CommandLine || !FParse::Param(CommandLine, TEXT("SailingShippingSmoke"))) return FString();
		static const TCHAR* Allowed[] = { TEXT("-SailingUIScript="), TEXT("-SailingWorld="), TEXT("-SailingLaunch="), TEXT("-SailingShot="), TEXT("-SailingBench=") };
		TArray<FString> Tokens;
		FString(CommandLine).ParseIntoArrayWS(Tokens);
		FString Out;
		for (const FString& T : Tokens)
		{
			for (const TCHAR* A : Allowed)
			{
				if (!T.StartsWith(A, ESearchCase::IgnoreCase)) continue;
				FString Kept = T;
				if (FCString::Stricmp(A, TEXT("-SailingBench=")) == 0)
				{
					const float Seconds = FMath::Clamp(FCString::Atof(*T.RightChop(FCString::Strlen(A))), 0.f, 60.f);
					Kept = FString::Printf(TEXT("-SailingBench=%g"), Seconds);
				}
				Out += (Out.IsEmpty() ? TEXT("") : TEXT(" ")) + Kept;
				break;
			}
		}
		return Out;
	}

	const TCHAR* Dev()
	{
#if UE_BUILD_SHIPPING
		// Shipping: only the release smoke's switches, and only with -SailingShippingSmoke (read again after a swap).
		static FString Filtered;
		static uint32 Gen = MAX_uint32;
		if (Gen != Generation())
		{
			Gen = Generation();
			Filtered = ShippingSmokeArgs(FCommandLine::Get());
		}
		return *Filtered;
#else
		return FCommandLine::Get();
#endif
	}

	bool FCachedFlag::Get()
	{
		const uint32 Now = Generation();
		if (Gen != Now)
		{
			bValue = FParse::Param(Dev(), Name);
			Gen = Now;
		}
		return bValue;
	}

	bool FOnce::Take()
	{
		const uint32 Now = Generation();
		if (Gen == Now) return false;
		Gen = Now;
		return true;
	}

	bool FOnce::Taken() const
	{
		return Gen == Generation();
	}
}

bool USailingBenchRunner::ShouldCreateSubsystem(UObject* Outer) const
{
	return FCString::Strifind(SailingArgs::Dev(), TEXT("SailingBenchList=")) != nullptr;
}

USailingBenchRunner* USailingBenchRunner::Get(const UObject* WorldContext)
{
	const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	const UGameInstance* GameInstance = World ? World->GetGameInstance() : nullptr;
	return GameInstance ? GameInstance->GetSubsystem<USailingBenchRunner>() : nullptr;
}

TArray<FSailingBenchView> USailingBenchRunner::ParseList(const FString& Text)
{
	TArray<FString> Lines;
	Text.ParseIntoArrayLines(Lines);
	TArray<FSailingBenchView> Out;
	for (FString Line : Lines)
	{
		Line.TrimStartAndEndInline();
		if (Line.IsEmpty() || Line.StartsWith(TEXT("#"))) continue;
		FSailingBenchView View;
		if (!Line.Split(TEXT("|"), &View.Name, &View.Args))
		{
			View.Name = Line;
		}
		View.Name.TrimStartAndEndInline();
		View.Args.TrimStartAndEndInline();
		if (!View.Name.IsEmpty()) Out.Add(View);
	}
	return Out;
}

FString USailingBenchRunner::ViewCommandLine(const FString& Base, const FSailingBenchView& View)
{
	// The view's own arguments go first: FParse::Value takes the first match, so a view's -SailingWorld or -SailingHour
	// wins over anything the base carries.
	TArray<FString> Tokens;
	Base.ParseIntoArrayWS(Tokens);
	FString Rest;
	for (const FString& Token : Tokens)
	{
		if (Token.StartsWith(TEXT("-SailingBenchList="), ESearchCase::IgnoreCase) || Token.StartsWith(TEXT("-SailingShot="), ESearchCase::IgnoreCase)) continue;
		Rest += TEXT(" ") + Token;
	}
	return FString::Printf(TEXT("-SailingShot=%s %s%s"), *View.Name, *View.Args, *Rest);
}

TMap<FString, FString> USailingBenchRunner::SnapshotCVars()
{
	TMap<FString, FString> Values;
	IConsoleManager::Get().ForEachConsoleObjectThatStartsWith(FConsoleObjectVisitor::CreateLambda([&Values](const TCHAR* Name, IConsoleObject* Object)
	{
		IConsoleVariable* Var = Object ? Object->AsVariable() : nullptr;
		if (Var && !Var->TestFlags(ECVF_ReadOnly)) Values.Add(Name, Var->GetString());
	}), TEXT(""));
	return Values;
}

int32 USailingBenchRunner::RestoreCVars(const TMap<FString, FString>& Snapshot, const TSet<FString>& Keep)
{
	int32 Set = 0;
	for (const TPair<FString, FString>& It : Snapshot)
	{
		IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(*It.Key, /*bTrackFrequentCalls*/ false);
		if (!Var || Var->GetString() == It.Value || Keep.Contains(It.Key)) continue;
		const EConsoleVariableFlags SetBy = EConsoleVariableFlags(Var->GetFlags() & ECVF_SetByMask);
		if (SetBy == ECVF_SetByScalability) continue;   // Scalability::SetQualityLevels sets every one of them again
		// At the priority it now has, so the set always takes.
		Var->Set(*It.Value, SetBy);
		++Set;
	}
	return Set;
}

void USailingBenchRunner::ResetRunState(UGameInstance* GameInstance)
{
	USailingSettings::RestoreClassDefaults();
	if (USailSessionSubsystem* Session = GameInstance ? GameInstance->GetSubsystem<USailSessionSubsystem>() : nullptr)
	{
		Session->ResetForRun();
	}
}

void USailingBenchRunner::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	BaseCommandLine = FCommandLine::Get();
	FString File;
	FParse::Value(*BaseCommandLine, TEXT("SailingBenchList="), File);
	if (FPaths::IsRelative(File)) File = FPaths::ProjectSavedDir() / TEXT("Bench") / File;
	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *File))
	{
		UE_LOG(LogSailingBench, Error, TEXT("Bench list %s not found"), *File);
	}
	Views = ParseList(Text);
	UE_LOG(LogSailingBench, Display, TEXT("Bench list %s: %d views"), *File, Views.Num());
	// The console variables as engine start-up left them, before the first view's tier is applied.
	CVarsAtStart = SnapshotCVars();
	FWorldDelegates::OnPreWorldInitialization.AddWeakLambda(this, [this](UWorld* World, const UWorld::InitializationValues)
	{
		// The last view's world is gone; the next one has not read anything yet.
		if (World && World->IsGameWorld() && Current >= 0 && PendingView == Current + 1) StartView(PendingView);
	});
	if (Views.Num() > 0) StartView(0);
}

void USailingBenchRunner::StartView(int32 Index)
{
	if (Index > 0)
	{
		ResetRunState(GetGameInstance());
		TSet<FString> Keep;
		ESailingQuality Quality = USailingSettings::Get()->Quality;
		FString Tier;
		if (FParse::Value(*BaseCommandLine, TEXT("SailingQuality="), Tier))
		{
			Quality = Tier.Equals(TEXT("Low"), ESearchCase::IgnoreCase) ? ESailingQuality::Low : Tier.Equals(TEXT("Medium"), ESearchCase::IgnoreCase) ? ESailingQuality::Medium
				: Tier.Equals(TEXT("Ultra"), ESearchCase::IgnoreCase) ? ESailingQuality::Ultra : ESailingQuality::High;
		}
		for (const FQualityCVar& C : QualityCVars(Quality)) Keep.Add(C.Name);
		const int32 Restored = RestoreCVars(CVarsAtStart, Keep);
		UE_LOG(LogSailingBench, Display, TEXT("Bench list: view %d reset (%d console variables put back)"), Index, Restored);
	}
	Current = Index;
	PendingView = -1;
	SailingArgs::SetCommandLine(ViewCommandLine(BaseCommandLine, Views[Index]));
	if (Index == 0) ViewStartSeconds = FPlatformTime::Seconds();
	UE_LOG(LogSailingBench, Display, TEXT("Bench list: view %d/%d %s"), Index + 1, Views.Num(), *Views[Index].Name);
}

void USailingBenchRunner::ViewFinished(const FString& Json, UObject* WorldContext)
{
	if (!Views.IsValidIndex(Current)) return;
	// The wall time of the view, load to result, for docs/bench-fast.
	const FString WithWall = Json.LeftChop(1) + FString::Printf(TEXT(",\"view_wall_s\":%.1f}"), FPlatformTime::Seconds() - ViewStartSeconds);
	FFileHelper::SaveStringToFile(WithWall, *(FPaths::ProjectSavedDir() / TEXT("Bench") / (Views[Current].Name + TEXT(".bench.json"))));
	if (Current + 1 >= Views.Num())
	{
		FPlatformMisc::RequestExit(false, TEXT("SailingBench list finished"));
		return;
	}
	PendingView = Current + 1;
	// A fresh process holds nothing of the last view: purge it (and its render resources) before the next loads.
	GEngine->ForceGarbageCollection(true);
	ViewStartSeconds = FPlatformTime::Seconds();   // the next view's time includes taking this world down
	UGameplayStatics::OpenLevel(WorldContext, FName(*UGameplayStatics::GetCurrentLevelName(WorldContext)));
}
