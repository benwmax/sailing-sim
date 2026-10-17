// Switches the low-level memory tracker (LLM) off before anything else runs in the packaged Mac game.
//
// Why: LLM is compiled into every non-Shipping build and stays on until PreInit reads the command line. Without -llm,
// FLLMGlobals::ProcessCommandLineInner then sets the state to Disabled and Clear()s the trackers. On the Mac,
// GuardedMain runs on its own thread while the main thread pumps NSApplication; launched with `open`, the Apple event
// arrives on the main thread at the same moment. The enable-state lock only covers entering a scope, not an open one:
// the main thread was inside LLM_PLATFORM_SCOPE (FMallocBinned3::PushNewPoolToFront) when Clear() freed the trackers,
// and the scope's destructor crashed in FLLMTracker::PopTag (two Development crash reports, Oct 16 2026).
//
// Here, at static initialization, there is one thread and no NSApplication yet. Flipping the state to Disabled makes
// every later scope bail out on entry, so when PreInit's ProcessCommandLine does its Clear() no scope can be open.
// The engine still runs that ProcessCommandLine (it sees LLM already disabled, clears and logs as usual).
//
// Rejected: passing -llm (turns tracking on, costs memory and time in every run); setting LLM_ENABLED_IN_CONFIG or
// similar through GlobalDefinitions (needs a unique build environment, so a separate engine build for the game target).
// Calling FLowLevelMemTracker::ProcessCommandLine(TEXT("")) here instead: its CSV_METADATA constructs FCsvProfiler
// before its statics exist (it checks IsInGameThread, binds FCoreDelegates and records an empty command line), so
// only the state is set and the engine's own call does the rest. Anything that would turn LLM on (-llm, -llmcsv, a
// -trace channel set) leaves it alone.

#include "CoreMinimal.h"
#include "HAL/LowLevelMemTracker.h"
#include "Misc/DelayedAutoRegister.h"
#include "SailingSim.h"

#if ENABLE_LOW_LEVEL_MEM_TRACKER && PLATFORM_MAC && IS_MONOLITHIC

#include <crt_externs.h>
#include <strings.h>

namespace SailingLLMEarlyOff
{
	// EnabledState is private; an explicit instantiation may name it (access isn't checked there).
	UE::LLMPrivate::EEnabled* StatePtr();
	template <UE::LLMPrivate::EEnabled* Ptr>
	struct TStateAccess
	{
		friend UE::LLMPrivate::EEnabled* StatePtr() { return Ptr; }
	};
	template struct TStateAccess<&FLowLevelMemTracker::EnabledState>;

	static bool WantsLLM()
	{
		const int Argc = *_NSGetArgc();
		char** const Argv = *_NSGetArgv();
		for (int Index = 1; Index < Argc; ++Index)
		{
			const char* Arg = Argv[Index];
			while (*Arg == '-' || *Arg == '/')
			{
				++Arg;
			}
			if (strncasecmp(Arg, "llm", 3) == 0 || strncasecmp(Arg, "trace", 5) == 0)
			{
				return true;
			}
		}
		return false;
	}

	static bool bSwitchedOff = false;

	static const bool bApplied = []
	{
		if (!WantsLLM())
		{
			*StatePtr() = UE::LLMPrivate::EEnabled::Disabled;
			bSwitchedOff = true;
		}
		return true;
	}();

	static FDelayedAutoRegisterHelper LogOnce(EDelayedRegisterRunPhase::EndOfEngineInit, []
	{
		UE_LOG(LogSailing, Log, TEXT("LLM %s before startup"),
			bSwitchedOff ? TEXT("switched off") : TEXT("left to the command line"));
	});
}

#endif
