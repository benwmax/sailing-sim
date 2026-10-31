#include "CrashReports.h"
#include "SailingSim.h"
#include "Engine/Engine.h"

#if WITH_SAILING_SENTRY
#include "SentrySubsystem.h"

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
