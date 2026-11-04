#include "CrashReports.h"
#include "SessionLog.h"
#include "Feedback.h"
#include "SailingSim.h"
#include "Async/Async.h"
#include "Containers/Ticker.h"
#include "Engine/Engine.h"
#include "HAL/PlatformOutputDevices.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include <atomic>

#if WITH_SAILING_SENTRY
#include "SentryAttachment.h"
#include "SentrySubsystem.h"
#include "SentryFeedback.h"
#include "SentryScope.h"
#include "SentrySettings.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#endif

namespace SailCrashReportsLocal
{
#if WITH_SAILING_SENTRY
	USentrySubsystem* Sentry()
	{
		USentrySubsystem* S = GEngine ? GEngine->GetEngineSubsystem<USentrySubsystem>() : nullptr;
		return S && S->IsEnabled() ? S : nullptr;
	}

	/** The settings the SDK itself runs with (the plugin's effective values: EditorDsn, SENTRY_DSN, the release it names). */
	bool EffectiveDsn(SailFeedback::FSentryDsn& Out, FString* Release = nullptr, FString* Environment = nullptr)
	{
		const USentrySettings* Settings = GetDefault<USentrySettings>();
		if (!Settings || !Out.Parse(Settings->GetEffectiveDsn())) return false;
		if (Release) *Release = Settings->GetEffectiveRelease();
		if (Environment) *Environment = Settings->GetEffectiveEnvironment();
		return true;
	}

	/** Posts one report's envelope (pc/feedback-send); its copy in the pending folder goes once the endpoint has taken it or
	 *  refused it for good (4xx but 429), and stays for the next launch otherwise. The URL is never logged: it has the key. */
	void PostEnvelope(const SailFeedback::FSentryDsn& Dsn, TArray<uint8> Body, const FString& PendingFile)
	{
		const TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
		Request->SetURL(Dsn.EnvelopeUrl());
		Request->SetVerb(TEXT("POST"));
		Request->SetHeader(TEXT("Content-Type"), TEXT("application/x-sentry-envelope"));
		Request->SetHeader(TEXT("X-Sentry-Auth"), Dsn.AuthHeader());
		Request->SetContent(MoveTemp(Body));
		Request->OnProcessRequestComplete().BindLambda([PendingFile](FHttpRequestPtr, FHttpResponsePtr Response, bool bOk)
		{
			const int32 Code = bOk && Response.IsValid() ? Response->GetResponseCode() : 0;
			const bool bTaken = Code / 100 == 2, bRefused = Code / 100 == 4 && Code != 429;
			if (bTaken || bRefused) IFileManager::Get().Delete(*PendingFile, false, true, true);
			UE_LOG(LogSailing, Log, TEXT("Feedback: %s's upload %s (HTTP %d)"), *FPaths::GetBaseFilename(PendingFile),
				bTaken ? TEXT("arrived") : (bRefused ? TEXT("was refused; dropped") : TEXT("failed; kept to send again at the next launch")), Code);
		});
		if (!Request->ProcessRequest()) UE_LOG(LogSailing, Log, TEXT("Feedback: %s couldn't start; kept to send again"), *FPaths::GetBaseFilename(PendingFile));
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
			const FString Log = SailSessionLog::ReportLogPath();   // the session log in Shipping (no engine log there)
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
	// The engine log's header names the machine and the account ("LogInit: Computer: …", "LogInit: User: …"): those lines
	// go whole (pc/feedback-send).
	FString Out;
	if (Text.Contains(TEXT("LogInit: Computer:")) || Text.Contains(TEXT("LogInit: User:")))
	{
		TArray<FString> Lines;
		Text.ParseIntoArray(Lines, TEXT("\n"), false);
		for (int32 I = 0; I < Lines.Num(); ++I)
		{
			if (Lines[I].Contains(TEXT("LogInit: Computer:")) || Lines[I].Contains(TEXT("LogInit: User:"))) continue;
			Out += Lines[I];
			if (I + 1 < Lines.Num()) Out += TEXT("\n");
		}
	}
	else Out = Text;
	for (const FPrefix& P : Prefixes)
	{
		const int32 Len = FCString::Strlen(P.Text);
		int32 From = 0;
		for (;;)
		{
			const int32 At = Out.Find(P.Text, ESearchCase::IgnoreCase, ESearchDir::FromStart, From);
			if (At == INDEX_NONE) break;
			// The name runs to the next separator, spaces and all ("C:\Users\Dana Smith\AppData"); with no separator before the
			// line or a quote ends, it stops at the first space instead ("/Users/dana today" reads "~ today").
			int32 End = At + Len;
			while (End < Out.Len() && Out[End] != P.Sep && Out[End] != '\n' && Out[End] != '\r' && Out[End] != '"' && Out[End] != '\'') ++End;
			// A name neither starts nor ends with a space: "/Users/ and /home/" or "/Users/dana today /tmp" is a new path.
			if (End >= Out.Len() || Out[End] != P.Sep || Out[At + Len] == ' ' || Out[End - 1] == ' ')
			{
				End = At + Len;
				while (End < Out.Len() && Out[End] != P.Sep && Out[End] != '\n' && Out[End] != '\r' && Out[End] != ' ' && Out[End] != '"' && Out[End] != '\'') ++End;
			}
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

EFeedbackSend SailCrashReports::SendFeedback(const FFeedbackReport& Report)
{
#if WITH_SAILING_SENTRY
	USentrySubsystem* S = SailCrashReportsLocal::Sentry();
	if (!S) return EFeedbackSend::Saved;
	// What goes with the message: the samples and the log tail when it carries the place, and the shots.
	TArray<SailFeedback::FEnvelopeAttachment> Files;
	auto AddText = [&Files](const FString& Text, const TCHAR* Name, const TCHAR* Type)
	{
		if (Text.IsEmpty()) return;
		FTCHARToUTF8 Utf8(*Text);
		Files.Add({ Name, Type, TArray<uint8>((const uint8*)Utf8.Get(), Utf8.Length()) });
	};
	if (Report.CarriesPlace())
	{
		AddText(Report.TelemetryJson, TEXT("telemetry.json"), TEXT("application/json"));
		AddText(SailCrashReports::ScrubPaths(Report.LogTail), TEXT("log.txt"), TEXT("text/plain"));
	}
	for (int32 I = 0; I < Report.ShotPaths.Num(); ++I)
	{
		TArray<uint8> Bytes;
		if (!FFileHelper::LoadFileToArray(Bytes, *Report.ShotPaths[I])) continue;
		const bool bJpeg = Report.ShotPaths[I].EndsWith(TEXT(".jpg"));
		Files.Add({ FString::Printf(TEXT("shot%d.%s"), I + 1, bJpeg ? TEXT("jpg") : TEXT("png")), bJpeg ? TEXT("image/jpeg") : TEXT("image/png"), MoveTemp(Bytes) });
	}
	const FString Kind = SailFeedback::KindId(Report.Kind);
	TMap<FString, FString> Tags = Report.Tags;
	Tags.Add(TEXT("feedback_kind"), Kind);
	// A bug sent after a crash is likely about it: Sentry pairs them by this tag and the time (the SDK gives no event id).
	const ESentryCrashedLastRun Crashed = S->IsCrashedLastRun();
	Tags.Add(TEXT("crashed_last_run"), Crashed == ESentryCrashedLastRun::Crashed ? TEXT("yes") : Crashed == ESentryCrashedLastRun::NotCrashed ? TEXT("no") : TEXT("unknown"));
	const FString Message = SailFeedback::ComposeMessage(Report);

	// pc/feedback-send: a report is the player's own deliberate send, so it goes with Send crash reports off too, but not
	// through the SDK: without consent the SDK caches every envelope and sends the whole cache once consent is given.
	// Then the report alone goes to the envelope endpoint over HTTP; the SDK's consent and cache are not touched.
	if (SendsOnItsOwn(S->IsUserConsentRequired(), S->GetUserConsent() == EUserConsent::Given))
	{
		SailFeedback::FSentryDsn Dsn;
		FString Release, Environment;
		if (!SailCrashReportsLocal::EffectiveDsn(Dsn, &Release, &Environment)) return EFeedbackSend::Saved;
		const FString EventId = FGuid::NewGuid().ToString(EGuidFormats::Digits).ToLower();
		TArray<uint8> Body = SailFeedback::FeedbackEnvelope(EventId, FDateTime::UtcNow().ToUnixTimestampDecimal(), Message, Tags, Release, Environment, Files);
		const FString Pending = FPaths::Combine(SailFeedback::PendingDir(), EventId + TEXT(".envelope"));
		FFileHelper::SaveArrayToFile(Body, *Pending);   // kept until the endpoint takes it (ResendPendingFeedback)
		UE_LOG(LogSailing, Log, TEXT("Feedback: sending a %s report on its own (%d bytes; crash reports stay off)"), *Kind, Body.Num());
		SailCrashReportsLocal::PostEnvelope(Dsn, MoveTemp(Body), Pending);
		return EFeedbackSend::Sending;
	}
	USentryFeedback* Feedback = NewObject<USentryFeedback>();
	Feedback->Initialize(Message);
	for (const SailFeedback::FEnvelopeAttachment& F : Files)
	{
		USentryAttachment* A = NewObject<USentryAttachment>();
		A->InitializeWithData(F.Bytes, F.Name, F.ContentType);
		Feedback->AddAttachment(A);
	}
	S->CaptureFeedbackWithScope(Feedback, FConfigureScopeNativeDelegate::CreateLambda([Tags](USentryScope* Scope)
	{
		Scope->SetTags(Tags);
	}));
	UE_LOG(LogSailing, Log, TEXT("Feedback: sent a %s report"), *Kind);
	return EFeedbackSend::Sent;
#else
	return EFeedbackSend::Saved;
#endif
}

void SailCrashReports::ResendPendingFeedback()
{
#if WITH_SAILING_SENTRY
	static bool bDone = false;   // once a launch (the game mode starts again on every map load)
	if (bDone || !SailCrashReportsLocal::Sentry()) return;
	bDone = true;
	SailFeedback::FSentryDsn Dsn;
	if (!SailCrashReportsLocal::EffectiveDsn(Dsn)) return;
	TArray<FString> Files;
	IFileManager::Get().FindFiles(Files, *FPaths::Combine(SailFeedback::PendingDir(), TEXT("*.envelope")), true, false);
	for (const FString& Name : Files)
	{
		const FString Path = FPaths::Combine(SailFeedback::PendingDir(), Name);
		const FTimespan Age = FDateTime::UtcNow() - IFileManager::Get().GetTimeStamp(*Path);
		TArray<uint8> Body;
		if (Age.GetTotalDays() > 30.0 || !FFileHelper::LoadFileToArray(Body, *Path))
		{
			IFileManager::Get().Delete(*Path, false, true, true);
			continue;
		}
		UE_LOG(LogSailing, Log, TEXT("Feedback: sending %s again"), *FPaths::GetBaseFilename(Path));
		SailCrashReportsLocal::PostEnvelope(Dsn, MoveTemp(Body), Path);
	}
#endif
}