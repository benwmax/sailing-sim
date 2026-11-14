#include "SessionLog.h"
#include "SailingSim.h"
#include "CrashReports.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformFileManager.h"
#include "HAL/PlatformOutputDevices.h"
#include "Misc/App.h"
#include "Misc/EngineVersion.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/ScopeLock.h"
#include "Misc/CoreDelegates.h"
#include "HAL/Runnable.h"
#include "HAL/RunnableThread.h"
#include "HAL/Event.h"
#include <atomic>

namespace SailSessionLogLocal
{
	/**
	 * Lines are buffered and written by one writer thread about once a second (Error lines and a report's read at once,
	 * a Warning wakes the writer): a write plus flush to a busy disk took 16-103 ms on the game thread (storm hitches,
	 * docs/session-log/). Two locks: Lock guards the buffer and the counters and is held only to copy bytes; FileLock
	 * guards the file and is held through the disk write, so a slow disk never blocks a caller of Write. Order: FileLock,
	 * then Lock.
	 */
	struct FLog
	{
		FCriticalSection Lock;       // Pending, Bytes, bCapped, bOpen, bWriter
		FCriticalSection FileLock;   // File, Directory
		FString Directory;
		TUniquePtr<IFileHandle> File;
		TArray<uint8> Pending;
		int64 Bytes = 0;
		bool bCapped = false;
		bool bOpen = false;
		bool bWriter = false;        // the writer thread is running (else Write drains itself)
		std::atomic<bool> bTried{ false };   // opened (or tried): Write's fast path
		bool bOpening = false;               // FileLock: a log line written while opening doesn't open again
		double Start = FPlatformTime::Seconds();
	};

	/** Never destroyed: the writer thread and the crash and exit hooks may outlive static destruction's order. */
	FLog& Log()
	{
		static FLog* L = new FLog;
		return *L;
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

	void AppendBytes(FLog& L, const FTCHARToUTF8& Utf8)
	{
		L.Pending.Append(reinterpret_cast<const uint8*>(Utf8.Get()), Utf8.Length());
	}

	/** Buffers one line, counting it against the cap; the caller holds Lock. */
	void Raw(FLog& L, const FString& Text)
	{
		if (!L.bOpen || L.bCapped) return;
		const FTCHARToUTF8 Utf8(*Text);
		if (L.Bytes + Utf8.Length() > SailSessionLog::MaxBytes)
		{
			AppendBytes(L, FTCHARToUTF8(TEXT("[log full: the rest of this launch is not written]\n")));
			L.bCapped = true;
			return;
		}
		AppendBytes(L, Utf8);
		L.Bytes += Utf8.Length();
	}

	void WriteOut(FLog& L, const TArray<uint8>& Out)
	{
		if (!L.File || Out.Num() == 0) return;
		L.File->Write(Out.GetData(), Out.Num());
		L.File->Flush();
	}

	/** Writes what is buffered to the file and flushes it; the caller holds FileLock (not Lock). */
	void DrainHeld(FLog& L)
	{
		TArray<uint8> Out;
		{
			FScopeLock Guard(&L.Lock);
			Swap(Out, L.Pending);
		}
		WriteOut(L, Out);
	}

	void Drain(FLog& L)
	{
		FScopeLock File(&L.FileLock);
		DrainHeld(L);
	}

	/** A crash: whatever is buffered goes out, unless the crashing thread holds a lock (then nothing waits on it). */
	void DrainForCrash()
	{
		FLog& L = Log();
		if (!L.FileLock.TryLock()) return;
		if (L.Lock.TryLock())
		{
			TArray<uint8> Out;
			Swap(Out, L.Pending);
			L.Lock.Unlock();
			WriteOut(L, Out);
		}
		L.FileLock.Unlock();
	}

	class FWriter final : public FRunnable
	{
	public:
		FEvent* Wake = FPlatformProcess::GetSynchEventFromPool(false);
		std::atomic<bool> bStop{ false };

		virtual uint32 Run() override
		{
			while (!bStop.load())
			{
				Wake->Wait(FTimespan::FromSeconds(SailSessionLog::FlushSeconds));
				Drain(Log());
			}
			return 0;
		}
		virtual void Stop() override
		{
			bStop = true;
			Wake->Trigger();
		}
	};

	FWriter* GWriter = nullptr;
	FRunnableThread* GWriterThread = nullptr;

	/** At exit: the writer stops and the buffer is written by the caller (later lines are written as they come). */
	void StopWriter()
	{
		FLog& L = Log();
		{
			FScopeLock Guard(&L.Lock);
			if (!L.bWriter) return;
			L.bWriter = false;
		}
		if (GWriterThread)
		{
			GWriterThread->Kill(true);
			delete GWriterThread;
			GWriterThread = nullptr;
		}
		Drain(L);
	}

	/** Once, on the first open: the writer thread and the hooks that write the buffer at exit and on a crash. */
	void StartWriter(FLog& L)
	{
		FCoreDelegates::OnPreExit.AddStatic(&StopWriter);
		FCoreDelegates::OnHandleSystemError.AddStatic(&DrainForCrash);
		FCoreDelegates::OnShutdownAfterError.AddStatic(&DrainForCrash);
		if (!FPlatformProcess::SupportsMultithreading()) return;
		GWriter = new FWriter;   // never deleted: its event may still be waited on as the process ends
		GWriterThread = FRunnableThread::Create(GWriter, TEXT("SailSessionLog"), 0, TPri_BelowNormal);
		if (!GWriterThread) return;
		FScopeLock Guard(&L.Lock);
		L.bWriter = true;
	}

	/** Opens (or reopens) the log; the caller holds FileLock. What the old file had buffered is written to it first. */
	void Open(FLog& L, const FString& Directory, bool bRotate)
	{
		DrainHeld(L);
		L.File.Reset();
		L.Directory = Directory;
		{
			FScopeLock Guard(&L.Lock);
			L.bOpen = false;
			L.bCapped = false;
			L.Bytes = 0;
		}
		IFileManager::Get().MakeDirectory(*Directory, true);
		if (bRotate) Rotate(Directory);
		L.File.Reset(FPlatformFileManager::Get().GetPlatformFile().OpenWrite(*FileIn(Directory, 0), !bRotate, true));
		{
			FScopeLock Guard(&L.Lock);
			L.bOpen = L.File.IsValid();
		}
		if (!bRotate) return;
		FString Stamp;
		if (FFileHelper::LoadFileToString(Stamp, *(FPaths::ProjectContentDir() / TEXT("BuildStamp/version.txt")))) Stamp.TrimStartAndEndInline();
		{
			FScopeLock Guard(&L.Lock);
			Raw(L, FString::Printf(TEXT("Ready About: Sailing session log, %s UTC\n"), *FDateTime::UtcNow().ToString(TEXT("%Y-%m-%d %H:%M:%S"))));
			Raw(L, FString::Printf(TEXT("Build %s, %s, engine %s, %s %s\n"), Stamp.IsEmpty() ? TEXT("dev") : *Stamp, LexToString(FApp::GetBuildConfiguration()),
				*FEngineVersion::Current().ToString(), ANSI_TO_TCHAR(FPlatformProperties::IniPlatformName()), *FPlatformMisc::GetOSVersion()));
		}
		DrainHeld(L);
	}

	/** The caller holds FileLock. */
	void EnsureOpenHeld(FLog& L)
	{
		if (L.bTried.load() || L.bOpening) return;
		L.bOpening = true;
		Open(L, FPaths::ConvertRelativePathToFull(FPaths::ProjectLogDir()), true);
		StartWriter(L);
		L.bTried = true;
	}

	void EnsureOpen(FLog& L)
	{
		if (L.bTried.load()) return;
		FScopeLock File(&L.FileLock);
		EnsureOpenHeld(L);
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
	EnsureOpen(L);
	FString Text = ScrubLine(SailCrashReports::ScrubPaths(Line));
	Text.ReplaceInline(TEXT("\r"), TEXT(" "));
	Text.ReplaceInline(TEXT("\n"), TEXT(" "));
	const bool bPlain = FCString::Strcmp(Level, TEXT("Display")) == 0 || FCString::Strcmp(Level, TEXT("Log")) == 0;
	const bool bAtOnce = FCString::Strcmp(Level, TEXT("Error")) == 0 || FCString::Strcmp(Level, TEXT("Fatal")) == 0;
	const bool bSoon = FCString::Strcmp(Level, TEXT("Warning")) == 0;
	bool bWriter = false;
	{
		FScopeLock Guard(&L.Lock);
		Raw(L, FString::Printf(TEXT("[+%.3f] %s%s%s\n"), FPlatformTime::Seconds() - L.Start, bPlain ? TEXT("") : Level, bPlain ? TEXT("") : TEXT(": "), *Text));
		bWriter = L.bWriter;
	}
	// An error may be the last thing before a crash: it is on disk before Write returns. Without the writer (no threads,
	// or after exit began) every line is.
	if (bAtOnce || !bWriter) Drain(L);
	else if (bSoon && GWriter) GWriter->Wake->Trigger();
}

void SailSessionLog::Flush()
{
	using namespace SailSessionLogLocal;
	FLog& L = Log();
	EnsureOpen(L);
	Drain(L);
}

FString SailSessionLog::Path()
{
	using namespace SailSessionLogLocal;
	FLog& L = Log();
	EnsureOpen(L);
	FScopeLock File(&L.FileLock);
	return FileIn(L.Directory, 0);
}

FString SailSessionLog::Tail(int32 MaxLines)
{
	Flush();
	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *Path(), FFileHelper::EHashOptions::None, FILEREAD_AllowWrite)) return FString();
	TArray<FString> Lines;
	Text.ParseIntoArrayLines(Lines, true);   // every line ends in a newline: no empty last line
	FString Out;
	for (int32 I = FMath::Max(0, Lines.Num() - MaxLines); I < Lines.Num(); ++I) { Out += Lines[I]; Out += TEXT("\n"); }
	return Out;
}

FString SailSessionLog::ReportLogPath()
{
	Flush();   // a report reads the file next
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
	FScopeLock File(&L.FileLock);
	EnsureOpenHeld(L);
	const FString Was = L.Directory;
	Open(L, Directory, bRotate);
	return Was;
}

void SailSessionLogLine(const TCHAR* Level, const FString& Line)
{
	SailSessionLog::Write(Level, Line);
}
