#include "Feedback.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformOutputDevices.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

void FFeedbackRecorder::Offer(const FFeedbackSample& Sample)
{
	if (Samples.Num() && Sample.T < Samples.Last().T) Samples.Reset();
	if (Samples.Num() && Sample.T - Samples.Last().T < IntervalSeconds) return;
	Samples.Add(Sample);
	int32 Drop = 0;
	while (Drop < Samples.Num() && Sample.T - Samples[Drop].T > KeepSeconds) ++Drop;
	if (Drop) Samples.RemoveAt(0, Drop);
}

FString FFeedbackRecorder::ToCsv() const
{
	FString Out = TEXT("t_s,north_m,east_m,heading_deg,speed_kn,heel_deg,twa_deg,tws_kn,fps\n");
	for (const FFeedbackSample& S : Samples)
	{
		Out += FString::Printf(TEXT("%.1f,%.1f,%.1f,%.1f,%.2f,%.1f,%.1f,%.1f,%.0f\n"),
			S.T, S.North, S.East, S.HeadingDeg, S.SpeedKn, S.HeelDeg, S.TwaDeg, S.TwsKn, S.Fps);
	}
	return Out;
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
		if (!R.SamplesCsv.IsEmpty()) bOk &= FFileHelper::SaveStringToFile(R.SamplesCsv, *FPaths::Combine(Folder, TEXT("samples.csv")));
		if (!R.LogTail.IsEmpty()) bOk &= FFileHelper::SaveStringToFile(ScrubPaths(R.LogTail), *FPaths::Combine(Folder, TEXT("log.txt")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	}
	for (int32 I = 0; I < R.ShotPaths.Num(); ++I)
	{
		if (IFileManager::Get().FileExists(*R.ShotPaths[I]))
			IFileManager::Get().Copy(*FPaths::Combine(Folder, FString::Printf(TEXT("shot%d.png"), I + 1)), *R.ShotPaths[I]);
	}
	return bOk ? Folder : FString();
}

FString SailFeedback::LocalDir()
{
	return FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Feedback"));
}
