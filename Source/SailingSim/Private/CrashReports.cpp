#include "CrashReports.h"
#include "Feedback.h"
#include "SailingSim.h"
#include "Async/Async.h"
#include "Containers/Ticker.h"
#include "Engine/Engine.h"
#include "HAL/PlatformOutputDevices.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include <atomic>

#if WITH_SAILING_SENTRY
#include "SentryAttachment.h"
#include "SentrySubsystem.h"
#include "SentryFeedback.h"
#include "SentryScope.h"
#endif

namespace SailCrashReportsLocal
{
#if WITH_SAILING_SENTRY
	USentrySubsystem* Sentry()
	{
		USentrySubsystem* S = GEngine ? GEngine->GetEngineSubsystem<USentrySubsystem>() : nullptr;
		return S && S->IsEnabled() ? S : nullptr;
	}

	/** Rewrites the scrubbed log on a worker (the whole log is read: never on the game thread). One write at a time. */
	void WriteScrubbedLog()
	{
		static std::atomic<bool> bBusy{ false };
		if (bBusy.exchange(true)) return;
		if (GLog) GLog->Flush();
		Async(EAsyncExecution::ThreadPool, []()
		{
			FString Text;
			const FString Log = FPlatformOutputDevices::GetAbsoluteLogFilename();
			if (FFileHelper::LoadFileToString(Text, *Log, FFileHelper::EHashOptions::None, FILEREAD_AllowWrite))
			{
				TArray<FString> Lines;
				Text.ParseIntoArrayLines(Lines, false);
				const int32 First = FMath::Max(0, Lines.Num() - SailCrashReports::ScrubbedLogLines);
				FString Tail;
				for (int32 I = First; I < Lines.Num(); ++I) Tail += Lines[I] + TEXT("\n");
				FFileHelper::SaveStringToFile(SailCrashReports::ScrubPaths(Tail), *SailCrashReports::ScrubbedLogPath());
			}
			bBusy = false;
		});
	}

	/** After the first yes: the scrubbed file is attached once (the SDK reads it when a report goes out, crashes included)
	 *  and kept fresh. */
	void StartScrubbedLog(USentrySubsystem* S)
	{
		static bool bStarted = false;
		if (bStarted) return;
		bStarted = true;
		WriteScrubbedLog();
		USentryAttachment* A = NewObject<USentryAttachment>();
		A->InitializeWithPath(SailCrashReports::ScrubbedLogPath(), TEXT("log.txt"), TEXT("text/plain"));
		S->AddAttachment(A);
		FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([](float) { WriteScrubbedLog(); return true; }),
			SailCrashReports::ScrubbedLogRefreshSeconds);
	}
#endif
}

void SailCrashReports::SetConsent(bool bSend)
{
#if WITH_SAILING_SENTRY
	if (USentrySubsystem* S = SailCrashReportsLocal::Sentry())
	{
		if (!S->IsUserConsentRequired()) return;
		if (bSend) S->GiveUserConsent();
		else S->RevokeUserConsent();
		if (bSend) SailCrashReportsLocal::StartScrubbedLog(S);
		UE_LOG(LogSailing, Log, TEXT("Crash reports: %s"), bSend ? TEXT("on") : TEXT("off"));
	}
#endif
}

void SailCrashReports::SetPlace(const FString& WorldId, const FString& BoatId)
{
#if WITH_SAILING_SENTRY
	if (USentrySubsystem* S = SailCrashReportsLocal::Sentry())
	{
		S->SetTag(TEXT("world"), WorldId);
		S->SetTag(TEXT("boat"), BoatId);
	}
#endif
}

bool SailCrashReports::IsEnabled()
{
#if WITH_SAILING_SENTRY
	return SailCrashReportsLocal::Sentry() != nullptr;
#else
	return false;
#endif
}

FString SailCrashReports::ScrubPaths(const FString& Text)
{
	// Each home-folder prefix, up to the next separator, becomes "~" (a Windows prefix takes its drive letter too, so the
	// drive forms go first: "/Users/" alone would leave "D:~").
	struct FPrefix { const TCHAR* Text; TCHAR Sep; bool bDrive; };
	static const FPrefix Prefixes[] = { { TEXT(":\\Users\\"), '\\', true }, { TEXT(":/Users/"), '/', true },
		{ TEXT("/Users/"), '/', false }, { TEXT("/home/"), '/', false } };
	FString Out = Text;
	for (const FPrefix& P : Prefixes)
	{
		const int32 Len = FCString::Strlen(P.Text);
		int32 From = 0;
		for (;;)
		{
			const int32 At = Out.Find(P.Text, ESearchCase::IgnoreCase, ESearchDir::FromStart, From);
			if (At == INDEX_NONE) break;
			int32 End = At + Len;
			while (End < Out.Len() && Out[End] != P.Sep && Out[End] != '\n' && Out[End] != ' ' && Out[End] != '"' && Out[End] != '\'') ++End;
			if (End == At + Len) { From = End; continue; }   // nothing after the prefix: not a home folder
			const int32 Start = P.bDrive && At > 0 ? At - 1 : At;
			Out = Out.Left(Start) + TEXT("~") + Out.Mid(End);
			From = Start + 1;
		}
	}
	return Out;
}

FString SailCrashReports::ScrubbedLogPath()
{
	return FPaths::ConvertRelativePathToFull(FPaths::ProjectLogDir() / TEXT("SailingSim-scrubbed.log"));
}

bool SailCrashReports::SendFeedback(const FFeedbackReport& Report)
{
#if WITH_SAILING_SENTRY
	USentrySubsystem* S = SailCrashReportsLocal::Sentry();
	if (!S) return false;
	USentryFeedback* Feedback = NewObject<USentryFeedback>();
	Feedback->Initialize(SailFeedback::ComposeMessage(Report));
	auto Attach = [Feedback](const FString& Text, const TCHAR* Name, const TCHAR* Type)
	{
		if (Text.IsEmpty()) return;
		FTCHARToUTF8 Utf8(*Text);
		TArray<uint8> Bytes((const uint8*)Utf8.Get(), Utf8.Length());
		USentryAttachment* A = NewObject<USentryAttachment>();
		A->InitializeWithData(Bytes, Name, Type);
		Feedback->AddAttachment(A);
	};
	if (Report.CarriesPlace())
	{
		Attach(Report.TelemetryJson, TEXT("telemetry.json"), TEXT("application/json"));
		Attach(SailCrashReports::ScrubPaths(Report.LogTail), TEXT("log.txt"), TEXT("text/plain"));
	}
	for (int32 I = 0; I < Report.ShotPaths.Num(); ++I)
	{
		TArray<uint8> Png;
		if (!FFileHelper::LoadFileToArray(Png, *Report.ShotPaths[I])) continue;
		USentryAttachment* A = NewObject<USentryAttachment>();
		const bool bJpeg = Report.ShotPaths[I].EndsWith(TEXT(".jpg"));
		A->InitializeWithData(Png, FString::Printf(TEXT("shot%d.%s"), I + 1, bJpeg ? TEXT("jpg") : TEXT("png")), bJpeg ? TEXT("image/jpeg") : TEXT("image/png"));
		Feedback->AddAttachment(A);
	}
	const FString Kind = SailFeedback::KindId(Report.Kind);
	TMap<FString, FString> Tags = Report.Tags;
	Tags.Add(TEXT("feedback_kind"), Kind);
	// A bug sent after a crash is likely about it: Sentry pairs them by this tag and the time (the SDK gives no event id).
	const ESentryCrashedLastRun Crashed = S->IsCrashedLastRun();
	Tags.Add(TEXT("crashed_last_run"), Crashed == ESentryCrashedLastRun::Crashed ? TEXT("yes") : Crashed == ESentryCrashedLastRun::NotCrashed ? TEXT("no") : TEXT("unknown"));
	S->CaptureFeedbackWithScope(Feedback, FConfigureScopeNativeDelegate::CreateLambda([Tags](USentryScope* Scope)
	{
		Scope->SetTags(Tags);
	}));
	UE_LOG(LogSailing, Log, TEXT("Feedback: sent a %s report"), *Kind);
	return true;
#else
	return false;
#endif
}
