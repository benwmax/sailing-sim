// docs/mac-autorelease: an experiment against the Mac's memory climb, off unless -SailingMetalPools is given at launch.
//
// The Oct 17 2026 soaks (docs/budget/mac-soak-high-2-2026-10-17.md, mac-soak-parked-2026-10-17.md) found Metal objects that
// pile up one or three a frame and are never freed: CAMetalDrawable (every tier) and the ray-tracing builders
// (AGXG17XFamilyRayTracingGPUBuilder, MTLInstanceAccelerationStructureDescriptor, about 425 MB/h on High). Both fit objects
// autoreleased on a thread whose pool never drains. Every engine thread on Apple has one autorelease pool for its whole life
// (FApplePlatformRunnableThread::PreRun / PostRun), the Metal RHI only wraps some calls in their own scoped pool
// (MetalRayTracing.cpp's acceleration-structure builds have none), and the task graph adds none. So what is autoreleased
// outside those scopes on the render or RHI thread waits for the thread to exit.
//
// With the switch on, each frame gets a pool of its own on two threads:
// - the render thread: made at the start of the frame (FCoreDelegates::OnBeginFrameRT) and released at its end (OnEndFrameRT).
//   Both run at the top of a render command, so no other pool is open above it on that thread.
// - the RHI thread: a lambda on the immediate command list, once a frame, releases that thread's pool from the last frame and
//   makes a new one. Command-list lambdas run between commands, outside the Metal RHI's scoped pools, so this one is the
//   innermost pool open there. A lambda that runs on another thread (inline on the render thread, or a task thread) does
//   nothing and is counted, so the log says where the immediate list really runs.
// The one risk: releasing a pool also releases every pool made above it on the same thread, so if anything ever left a pool
// open across our lambda, its own release would then crash. That is why this is a switch, measured before it is a default.

#include "CoreMinimal.h"
#include "SailingSim.h"

#if PLATFORM_MAC

#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/CoreDelegates.h"
#include "Misc/DelayedAutoRegister.h"
#include "Misc/Parse.h"
#include "RHICommandList.h"
#include "RenderingThread.h"
#include <atomic>

namespace SailingMetalPools
{
	static void* RenderPool = nullptr;                 // render thread only
	static thread_local void* ThreadPool = nullptr;    // the RHI thread's pool for this frame
	static std::atomic<int64> RhiSwaps{ 0 }, RenderThreadRuns{ 0 }, OtherThreadRuns{ 0 };
	static int64 Frames = 0;                           // render thread only

	static void SwapRhiPool(FRHICommandListImmediate&)
	{
		if (IsInRenderingThread()) { ++RenderThreadRuns; return; }   // no RHI thread: the render thread's pool covers it
		if (!IsInRHIThread()) { ++OtherThreadRuns; return; }        // a task thread: not ours to hold a pool open on
		if (ThreadPool) FPlatformMisc::ReleaseAutoreleasePool(ThreadPool);
		ThreadPool = FPlatformMisc::CreateAutoreleasePool();
		++RhiSwaps;
	}

	static void BeginFrameRT()
	{
		if (RenderPool) FPlatformMisc::ReleaseAutoreleasePool(RenderPool);   // a frame whose end didn't come
		RenderPool = FPlatformMisc::CreateAutoreleasePool();
	}

	static void EndFrameRT()
	{
		if (RenderPool)
		{
			FPlatformMisc::ReleaseAutoreleasePool(RenderPool);
			RenderPool = nullptr;
		}
		FRHICommandListImmediate::Get().EnqueueLambda([](FRHICommandListImmediate& RHICmdList) { SwapRhiPool(RHICmdList); });
		if (++Frames % 3600 == 0)
		{
			SAIL_LOG(Display, TEXT("Metal pools: %lld frames; RHI-thread swaps %lld, lambdas on the render thread %lld, on other threads %lld"),
				Frames, RhiSwaps.load(), RenderThreadRuns.load(), OtherThreadRuns.load());
		}
	}

	static FDelayedAutoRegisterHelper Register(EDelayedRegisterRunPhase::EndOfEngineInit, []
	{
		if (!FParse::Param(FCommandLine::Get(), TEXT("SailingMetalPools"))) return;
		// Bound on the render thread, which is the one that broadcasts these (a delegate isn't safe to change mid-broadcast).
		ENQUEUE_RENDER_COMMAND(SailingMetalPoolsBind)([](FRHICommandListImmediate&)
		{
			FCoreDelegates::OnBeginFrameRT.AddStatic(&BeginFrameRT);
			FCoreDelegates::OnEndFrameRT.AddStatic(&EndFrameRT);
		});
		SAIL_LOG(Display, TEXT("Metal pools: on (-SailingMetalPools): a pool a frame on the render and RHI threads (docs/mac-autorelease)"));
	});
}

#endif // PLATFORM_MAC
