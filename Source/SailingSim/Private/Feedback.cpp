#include "Feedback.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformOutputDevices.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "Modules/ModuleManager.h"

void FFeedbackRecorder::Offer(const FFeedbackSample& Sample)
{
	if (Samples.Num() && Sample.T < Samples.Last().T) Samples.Reset();
	if (Samples.Num() && Sample.T - Samples.Last().T < IntervalSeconds) return;
	Samples.Add(Sample);
	int32 Drop = 0;
	while (Drop < Samples.Num() && Sample.T - Samples[Drop].T > KeepSeconds) ++Drop;
	if (Drop) Samples.RemoveAt(0, Drop);
}

FString FFeedbackRecorder::ToJson() const
{
	FString Out = FString::Printf(TEXT("{\"interval_s\": %.1f, \"samples\": ["), IntervalSeconds);
	for (int32 I = 0; I < Samples.Num(); ++I)
	{
		const FFeedbackSample& S = Samples[I];
		Out += FString::Printf(TEXT("%s\n{\"t_s\": %.1f, \"north_m\": %.1f, \"east_m\": %.1f, \"heading_deg\": %.1f, \"speed_kn\": %.2f, \"heel_deg\": %.1f, \"twa_deg\": %.1f, \"tws_kn\": %.1f, \"fps\": %.0f}"),
			I ? TEXT(",") : TEXT(""), S.T, S.North, S.East, S.HeadingDeg, S.SpeedKn, S.HeelDeg, S.TwaDeg, S.TwsKn, S.Fps);
	}
	return Out + TEXT("\n]}\n");
}

double FFeedbackRecorder::MeanFps() const
{
	double Sum = 0.0;
	for (const FFeedbackSample& S : Samples) Sum += S.Fps;
	return Samples.Num() ? Sum / Samples.Num() : 0.0;
}

const TCHAR* SailFeedback::KindId(EFeedbackKind Kind)
{
	return Kind == EFeedbackKind::Idea ? TEXT("idea") : TEXT("bug");
}

FString SailFeedback::ScrubPaths(const FString& Text)
{
	// Each home-folder prefix up to the next separator becomes "~".
	struct FPrefix { const TCHAR* Text; TCHAR Sep; };
	static const FPrefix Prefixes[] = { { TEXT("/Users/"), '/' }, { TEXT("/home/"), '/' }, { TEXT(":\\Users\\"), '\\' }, { TEXT(":/Users/"), '/' } };
	FString Out = Text;
	for (const FPrefix& P : Prefixes)
	{
		const int32 Len = FCString::Strlen(P.Text);
		int32 From = 0;
		for (;;)
		{
			const int32 At = Out.Find(P.Text, ESearchCase::IgnoreCase, ESearchDir::FromStart, From);
			if (At == INDEX_NONE) break;
			// A drive letter belongs to a Windows prefix.
			const int32 Start = (P.Text[0] == ':' && At > 0) ? At - 1 : At;
			int32 End = At + Len;
			// A Windows user name may hold spaces; a Unix path in a sentence ends at one.
			const bool bStopAtSpace = P.Sep == '/';
			while (End < Out.Len() && Out[End] != P.Sep && Out[End] != '\n' && Out[End] != '"' && !(bStopAtSpace && Out[End] == ' ')) ++End;
			if (End == At + Len) { From = End; continue; } // nothing after the prefix: not a home folder
			Out = Out.Left(Start) + TEXT("~") + Out.Mid(End);
			From = Start + 1;
		}
	}
	return Out;
}

FString SailFeedback::ReproArgs(const FString& WorldId, const FString& BoatId, const FFeedbackSample& At, double WindKn)
{
	return FString::Printf(TEXT("-SailingWorld=%s -SailingBoat=%s \"-SailingStartAt=%.0f,%.0f,%.0f\" -SailingWind=%.0f -SailingTWA=%.0f"),
		*WorldId, *BoatId, At.North, At.East, At.HeadingDeg, WindKn, At.TwaDeg);
}

FString SailFeedback::ComposeMessage(const FFeedbackReport& R)
{
	const bool bBug = R.Kind == EFeedbackKind::Bug;
	FString Out = FString::Printf(TEXT("[%s] %s\n\n"), bBug ? TEXT("Bug") : TEXT("Idea"), R.Title.IsEmpty() ? TEXT("(no title)") : *R.Title);
	if (!R.WhatHappened.IsEmpty()) Out += FString::Printf(TEXT("%s\n%s\n\n"), bBug ? TEXT("What happened:") : TEXT("Idea:"), *R.WhatHappened);
	if (bBug && !R.Expected.IsEmpty()) Out += FString::Printf(TEXT("Expected:\n%s\n\n"), *R.Expected);
	for (const TPair<FString, FString>& C : R.Context) Out += FString::Printf(TEXT("%s: %s\n"), *C.Key, *C.Value);
	if (R.CarriesPlace() && !R.Repro.IsEmpty()) Out += FString::Printf(TEXT("Repro: %s\n"), *R.Repro);
	return ScrubPaths(Out);
}

FString SailFeedback::LogTail(int32 MaxLines)
{
	FString Text;
	const FString Path = FPlatformOutputDevices::GetAbsoluteLogFilename();
	if (GLog) GLog->Flush();
	if (!FFileHelper::LoadFileToString(Text, *Path, FFileHelper::EHashOptions::None, FILEREAD_AllowWrite)) return FString();
	TArray<FString> Lines;
	Text.ParseIntoArrayLines(Lines, false);
	const int32 First = FMath::Max(0, Lines.Num() - MaxLines);
	FString Out;
	for (int32 I = First; I < Lines.Num(); ++I) { Out += Lines[I]; Out += TEXT("\n"); }
	return ScrubPaths(Out);
}

FString SailFeedback::WriteLocal(const FFeedbackReport& R, const FString& Dir)
{
	const FString Folder = FPaths::Combine(Dir, FString::Printf(TEXT("%s-%s"), *FDateTime::UtcNow().ToString(TEXT("%Y%m%d-%H%M%S")), KindId(R.Kind)));
	if (!IFileManager::Get().MakeDirectory(*Folder, true)) return FString();
	bool bOk = FFileHelper::SaveStringToFile(ComposeMessage(R), *FPaths::Combine(Folder, TEXT("report.txt")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	if (R.CarriesPlace())
	{
		if (!R.TelemetryJson.IsEmpty()) bOk &= FFileHelper::SaveStringToFile(R.TelemetryJson, *FPaths::Combine(Folder, TEXT("telemetry.json")));
		if (!R.LogTail.IsEmpty()) bOk &= FFileHelper::SaveStringToFile(ScrubPaths(R.LogTail), *FPaths::Combine(Folder, TEXT("log.txt")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	}
	if (R.Tags.Num())
	{
		TArray<FString> Keys;
		R.Tags.GetKeys(Keys);
		Keys.Sort();
		FString Json = TEXT("{");
		for (int32 I = 0; I < Keys.Num(); ++I)
			Json += FString::Printf(TEXT("%s\n  \"%s\": \"%s\""), I ? TEXT(",") : TEXT(""), *Keys[I], *R.Tags[Keys[I]].ReplaceCharWithEscapedChar());
		bOk &= FFileHelper::SaveStringToFile(Json + TEXT("\n}\n"), *FPaths::Combine(Folder, TEXT("tags.json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	}
	for (int32 I = 0; I < R.ShotPaths.Num(); ++I)
	{
		if (IFileManager::Get().FileExists(*R.ShotPaths[I]))
			IFileManager::Get().Copy(*FPaths::Combine(Folder, FString::Printf(TEXT("shot%d%s"), I + 1, *FPaths::GetExtension(R.ShotPaths[I], true))), *R.ShotPaths[I]);
	}
	return bOk ? Folder : FString();
}

FString SailFeedback::LocalDir()
{
	return FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Feedback"));
}

bool SailFeedback::ShotToJpeg(const FString& PngPath, const FString& JpegPath, int64 MaxBytes)
{
	TArray<uint8> Png;
	if (!FFileHelper::LoadFileToArray(Png, *PngPath)) return false;
	IImageWrapperModule& Images = FModuleManager::LoadModuleChecked<IImageWrapperModule>(TEXT("ImageWrapper"));
	TSharedPtr<IImageWrapper> In = Images.CreateImageWrapper(EImageFormat::PNG);
	TArray<uint8> Raw;
	if (!In.IsValid() || !In->SetCompressed(Png.GetData(), Png.Num()) || !In->GetRaw(ERGBFormat::BGRA, 8, Raw)) return false;
	int32 W = In->GetWidth(), H = In->GetHeight();
	for (int32 Pass = 0; Pass < 4; ++Pass)
	{
		for (const int32 Quality : { 85, 70, 55 })
		{
			TSharedPtr<IImageWrapper> Out = Images.CreateImageWrapper(EImageFormat::JPEG);
			if (!Out.IsValid() || !Out->SetRaw(Raw.GetData(), Raw.Num(), W, H, ERGBFormat::BGRA, 8)) return false;
			const TArray64<uint8>& Jpeg = Out->GetCompressed(Quality);
			if (Jpeg.Num() > 0 && Jpeg.Num() <= MaxBytes) return FFileHelper::SaveArrayToFile(Jpeg, *JpegPath);
		}
		// Still too big: half the size (box filter).
		const int32 W2 = FMath::Max(1, W / 2), H2 = FMath::Max(1, H / 2);
		TArray<uint8> Half;
		Half.SetNumUninitialized(W2 * H2 * 4);
		for (int32 Y = 0; Y < H2; ++Y)
			for (int32 X = 0; X < W2; ++X)
				for (int32 C = 0; C < 4; ++C)
				{
					const int32 Sx = FMath::Min(2 * X + 1, W - 1), Sy = FMath::Min(2 * Y + 1, H - 1);
					const int32 Sum = Raw[(2 * Y * W + 2 * X) * 4 + C] + Raw[(2 * Y * W + Sx) * 4 + C] + Raw[(Sy * W + 2 * X) * 4 + C] + Raw[(Sy * W + Sx) * 4 + C];
					Half[(Y * W2 + X) * 4 + C] = uint8(Sum / 4);
				}
		Raw = MoveTemp(Half);
		W = W2; H = H2;
	}
	return false;
}
