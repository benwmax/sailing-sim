#include "SoundCaptions.h"
#include "SailboatPawn.h"
#include "SailingSettings.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"

double SailingSound::RelativeBearingDeg(const FVector2D& Pos, double HeadingDeg, const FVector2D& Source)
{
	// Map frame: X north, Y east, so atan2(east, north) is the compass bearing.
	const double Bearing = FMath::RadiansToDegrees(FMath::Atan2(Source.Y - Pos.Y, Source.X - Pos.X));
	return FMath::UnwindDegrees(Bearing - HeadingDeg);
}

const TCHAR* SailingSound::RelativeDirection(double RelativeBearingDeg)
{
	const double R = FMath::UnwindDegrees(RelativeBearingDeg);
	const double A = FMath::Abs(R);
	const bool bStarboard = R > 0.0;
	if (A <= 22.5) return TEXT("ahead");
	if (A <= 67.5) return bStarboard ? TEXT("off the starboard bow") : TEXT("off the port bow");
	if (A <= 112.5) return bStarboard ? TEXT("abeam to starboard") : TEXT("abeam to port");
	if (A <= 157.5) return bStarboard ? TEXT("off the starboard quarter") : TEXT("off the port quarter");
	return TEXT("astern");
}

USoundCaptions* USoundCaptions::Get(const UObject* WorldContext)
{
	const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	return World ? World->GetSubsystem<USoundCaptions>() : nullptr;
}

double USoundCaptions::Now() const
{
	return GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
}

void USoundCaptions::Add(const FString& Text, double Seconds)
{
	if (Text.IsEmpty() || !USailingSettings::Get()->bSoundCaptions) return;
	const double T = Now();
	Captions.RemoveAll([T](const FCaption& C) { return C.Until < T; });
	for (FCaption& C : Captions)
	{
		if (C.Text == Text) { C.Until = FMath::Max(C.Until, T + Seconds); return; }
	}
	Captions.Add({ Text, T + Seconds });
	if (Captions.Num() > 4) Captions.RemoveAt(0);
}

void USoundCaptions::AddFrom(const FString& What, const FVector2D& Source, const FString& Detail, double Seconds)
{
	if (!USailingSettings::Get()->bSoundCaptions) return;
	FString Text = What;
	const APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
	if (const ASailboatPawn* P = PC ? Cast<ASailboatPawn>(PC->GetPawn()) : nullptr)
	{
		Text += TEXT(", ");
		Text += SailingSound::RelativeDirection(SailingSound::RelativeBearingDeg(P->GetMapPosition(), P->GetHeadingTrueDeg(), Source));
	}
	if (!Detail.IsEmpty()) Text += TEXT(": ") + Detail;
	Add(Text, Seconds);
}

TArray<FString> USoundCaptions::Active() const
{
	TArray<FString> Out;
	const double T = Now();
	for (const FCaption& C : Captions) if (C.Until >= T) Out.Add(C.Text);
	return Out;
}
