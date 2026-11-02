#include "SessionLog.h"
#include "CrashReports.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformFileManager.h"
#include "HAL/PlatformOutputDevices.h"
#include "Misc/App.h"
#include "Misc/EngineVersion.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/ScopeLock.h"

namespace SailSessionLogLocal
{
	struct FLog
	{
		FCriticalSection Lock;
		FString Directory;
		TUniquePtr<IFileHandle> File;
		int64 Bytes = 0;
		bool bCapped = false;
		bool bTried = false;
		double Start = FPlatformTime::Seconds();
	};

	FLog& Log()
	{
		static FLog L;
		return L;
	}

	FString FileIn(const FString& Directory, int32 Index)
	{
		return Index == 0 ? Directory / TEXT("session.txt") : Directory / FString::Printf(TEXT("session-%d.txt"), Index);
	}

	void Rotate(const FString& Directory)
	{
		IFileManager& FM = IFileManager::Get();
		FM.Delete(*FileIn(Directory, SailSessionLog::KeepLaunches - 1), false, true, true);
		for (int32 I = SailSessionLog::KeepLaunches - 2; I >= 0; --I)
		{
			if (FM.FileExists(*FileIn(Directory, I))) FM.Move(*FileIn(Directory, I + 1), *FileIn(Directory, I), true, true);
		}
	}

	void Raw(FLog& L, const FString& Text)
	{
		if (!L.File || L.bCapped) return;
		const FTCHARToUTF8 Utf8(*Text);
		if (L.Bytes + Utf8.Length() > SailSessionLog::MaxBytes)
		{
			const FTCHARToUTF8 Note(TEXT("[log full: the rest of this launch is not written]\n"));
			L.File->Write(reinterpret_cast<const uint8*>(Note.Get()), Note.Length());
			L.File->Flush();
			L.bCapped = true;
			return;
		}
		L.File->Write(reinterpret_cast<const uint8*>(Utf8.Get()), Utf8.Length());
		L.File->Flush();
		L.Bytes += Utf8.Length();
	}

	/** Opens (or reopens) the log; the caller holds the lock. */
	void Open(FLog& L, const FString& Directory, bool bRotate)
	{
		L.File.Reset();
		L.Directory = Directory;
		L.bCapped = false;
		L.Bytes = 0;
		IFileManager::Get().MakeDirectory(*Directory, true);
		if (bRotate) Rotate(Directory);
		L.File.Reset(FPlatformFileManager::Get().GetPlatformFile().OpenWrite(*FileIn(Directory, 0), !bRotate, true));
		if (!bRotate) return;
		Raw(L, FString::Printf(TEXT("Ready About: Sailing session log, %s UTC\n"), *FDateTime::UtcNow().ToString(TEXT("%Y-%m-%d %H:%M:%S"))));
		FString Stamp;
		if (FFileHelper::LoadFileToString(Stamp, *(FPaths::ProjectContentDir() / TEXT("BuildStamp/version.txt")))) Stamp.TrimStartAndEndInline();
		Raw(L, FString::Printf(TEXT("Build %s, %s, engine %s, %s %s\n"), Stamp.IsEmpty() ? TEXT("dev") : *Stamp, LexToString(FApp::GetBuildConfiguration()),
			*FEngineVersion::Current().ToString(), ANSI_TO_TCHAR(FPlatformProperties::IniPlatformName()), *FPlatformMisc::GetOSVersion()));
	}

	void EnsureOpen(FLog& L)
	{
		if (L.File || L.bTried) return;
		L.bTried = true;
		Open(L, FPaths::ConvertRelativePathToFull(FPaths::ProjectLogDir()), true);
	}
}

FString SailSessionLog::ScrubLine(const FString& Line)
{
	// A word with an @ between a name and a dotted domain is an address.
	FString Out;
	int32 I = 0;
	while (I < Line.Len())
	{
		int32 End = I;
		while (End < Line.Len() && !FChar::IsWhitespace(Line[End]) && Line[End] != '"' && Line[End] != '\'' && Line[End] != ',' && Line[End] != ';') ++End;
		if (End == I) { Out.AppendChar(Line[I++]); continue; }
		const FString Word = Line.Mid(I, End - I);
		int32 At = INDEX_NONE;
		const bool bEmail = Word.FindChar('@', At) && At > 0 && Word.Mid(At + 1).Contains(TEXT(".")) && !Word.Mid(At + 1).StartsWith(TEXT("."));
		Out += bEmail ? FString(TEXT("<email>")) : Word;
		I = End;
	}
	return Out;
}

void SailSessionLog::Write(const TCHAR* Level, const FString& Line)
{
	using namespace SailSessionLogLocal;
	FLog& L = Log();
	FScopeLock Guard(&L.Lock);
	EnsureOpen(L);
	FString Text = ScrubLine(SailCrashReports::ScrubPaths(Line));
	Text.ReplaceInline(TEXT("\r"), TEXT(" "));
	Text.ReplaceInline(TEXT("\n"), TEXT(" "));
	const bool bPlain = FCString::Strcmp(Level, TEXT("Display")) == 0 || FCString::Strcmp(Level, TEXT("Log")) == 0;
	Raw(L, FString::Printf(TEXT("[+%.3f] %s%s%s\n"), FPlatformTime::Seconds() - L.Start, bPlain ? TEXT("") : Level, bPlain ? TEXT("") : TEXT(": "), *Text));
}

FString SailSessionLog::Path()
{
	using namespace SailSessionLogLocal;
	FLog& L = Log();
	FScopeLock Guard(&L.Lock);
	EnsureOpen(L);
	return FileIn(L.Directory, 0);
}

FString SailSessionLog::Tail(int32 MaxLines)
{
	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *Path(), FFileHelper::EHashOptions::None, FILEREAD_AllowWrite)) return FString();
	TArray<FString> Lines;
	Text.ParseIntoArrayLines(Lines, false);
	FString Out;
	for (int32 I = FMath::Max(0, Lines.Num() - MaxLines); I < Lines.Num(); ++I) { Out += Lines[I]; Out += TEXT("\n"); }
	return Out;
}

FString SailSessionLog::ReportLogPath()
{
#if NO_LOGGING
	return Path();
#else
	const FString Engine = FPlatformOutputDevices::GetAbsoluteLogFilename();
	return IFileManager::Get().FileSize(*Engine) > 0 ? Engine : Path();
#endif
}

FString SailSessionLog::OpenIn(const FString& Directory, bool bRotate)
{
	using namespace SailSessionLogLocal;
	FLog& L = Log();
	FScopeLock Guard(&L.Lock);
	EnsureOpen(L);
	const FString Was = L.Directory;
	Open(L, Directory, bRotate);
	return Was;
}

void SailSessionLogLine(const TCHAR* Level, const FString& Line)
{
	SailSessionLog::Write(Level, Line);
}
