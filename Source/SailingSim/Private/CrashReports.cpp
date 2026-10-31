#include "CrashReports.h"
#include "Feedback.h"
#include "SailingSim.h"
#include "Engine/Engine.h"

#if WITH_SAILING_SENTRY
#include "SentrySubsystem.h"
#include "SentryAttachment.h"
#include "SentryFeedback.h"
#include "SentryScope.h"
#include "Misc/FileHelper.h"

namespace SailCrashReportsLocal
{
	USentrySubsystem* Sentry()
	{
		USentrySubsystem* S = GEngine ? GEngine->GetEngineSubsystem<USentrySubsystem>() : nullptr;
		return S && S->IsEnabled() ? S : nullptr;
	}
}
#endif

void SailCrashReports::SetConsent(bool bSend)
{
#if WITH_SAILING_SENTRY
	if (USentrySubsystem* S = SailCrashReportsLocal::Sentry())
	{
		if (!S->IsUserConsentRequired()) return;
		if (bSend) S->GiveUserConsent();
		else S->RevokeUserConsent();
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
		Attach(Report.SamplesCsv, TEXT("samples.csv"), TEXT("text/csv"));
		Attach(SailFeedback::ScrubPaths(Report.LogTail), TEXT("log.txt"), TEXT("text/plain"));
	}
	for (int32 I = 0; I < Report.ShotPaths.Num(); ++I)
	{
		TArray<uint8> Png;
		if (!FFileHelper::LoadFileToArray(Png, *Report.ShotPaths[I])) continue;
		USentryAttachment* A = NewObject<USentryAttachment>();
		A->InitializeWithData(Png, FString::Printf(TEXT("shot%d.png"), I + 1), TEXT("image/png"));
		Feedback->AddAttachment(A);
	}
	const FString Kind = SailFeedback::KindId(Report.Kind);
	S->CaptureFeedbackWithScope(Feedback, FConfigureScopeNativeDelegate::CreateLambda([Kind](USentryScope* Scope)
	{
		Scope->SetTag(TEXT("kind"), Kind);
	}));
	UE_LOG(LogSailing, Log, TEXT("Feedback: sent a %s report"), *Kind);
	return true;
#else
	return false;
#endif
}
