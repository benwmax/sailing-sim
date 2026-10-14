// Perf 1: named scopes around the game thread's big ticks. Each is an Unreal Insights CPU event (-trace=cpu) and also adds
// its wall time to a counter the bench reports per frame (bench.json "gt": {"boat_physics": ms, ...}). Scopes nest (the
// sails are inside the boat visuals), so the slices are inclusive and do not sum to the frame.
#pragma once

#include "CoreMinimal.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"

namespace SailingPerf
{
	enum class ESlice : uint8
	{
		BoatPhysics,   // the player's fixed-step loop (with the task: the join's wait)
		BoatVisuals,   // UpdateRigVisuals, every sailboat pawn
		Sails,         // sail cloth and meshes, every sailboat pawn
		Crew,          // crew figures and groom LOD
		RigLines,      // model rig (rig lines, traveler, mast bend)
		Telltales,
		BoatSound,
		BoatCapture,
		BoatLearning,  // drills, learning tips, chart and debrief checks, logbook, replay
		Water,         // AWaterSurface::Tick
		WaterUploads,  // its texture uploads
		Terrain,       // ALakeTerrainActor::Tick
		Trees,         // its tree re-binning
		Traffic,       // ATrafficManager::Tick
		TrafficStep,   // FTrafficSim::Step inside it
		Hud,           // SSailHud::Tick
		Count
	};

	/** Seconds spent in each slice since the start (game thread only). */
	SAILINGSIM_API extern double GSliceSeconds[int32(ESlice::Count)];
	SAILINGSIM_API const TCHAR* SliceName(ESlice Slice);
	/** {"boat_physics":ms,...}: the slices' time per frame between two snapshots of GSliceSeconds, for bench.json. */
	SAILINGSIM_API FString SlicesJson(const double* Start, const double* End, int32 Frames);

	/** stat unit's thread times (game and render thread without their waits, RHI thread, GPU), summed per frame. */
	struct SAILINGSIM_API FThreadTimes
	{
		double GameMs = 0.0, RenderMs = 0.0, RhiMs = 0.0, GpuMs = 0.0;
		TArray<float> Game; // per frame, for the 99th percentile
		void Sample();
		/** "game_ms":..,"game_p99_ms":..,"render_ms":..,"rhi_ms":..,"gpu_frame_ms":.. (no braces). */
		FString JsonFields() const;
	};

	struct FScope
	{
		explicit FScope(ESlice InSlice) : Slice(InSlice), Begin(FPlatformTime::Seconds()) {}
		~FScope() { GSliceSeconds[int32(Slice)] += FPlatformTime::Seconds() - Begin; }
		ESlice Slice;
		double Begin;
	};

	/** A scope that ends before its block does (SAILING_PERF_SCOPE_BEGIN/END), for a loop that keeps its indentation. */
	struct FManualScope
	{
		explicit FManualScope(ESlice InSlice) : Slice(InSlice), Begin(FPlatformTime::Seconds())
		{
#if CPUPROFILERTRACE_ENABLED
			bTraced = UE_TRACE_CHANNELEXPR_IS_ENABLED(CpuChannel);
			if (bTraced) FCpuProfilerTrace::OutputBeginDynamicEvent(SliceName(Slice));
#endif
		}
		~FManualScope() { End(); }
		void End()
		{
			if (Begin < 0.0) return;
			GSliceSeconds[int32(Slice)] += FPlatformTime::Seconds() - Begin;
			Begin = -1.0;
#if CPUPROFILERTRACE_ENABLED
			if (bTraced) FCpuProfilerTrace::OutputEndEvent();
#endif
		}
		ESlice Slice;
		double Begin;
		bool bTraced = false;
	};
}

#define SAILING_PERF_SCOPE_BEGIN(Slice) SailingPerf::FManualScope SailingPerfManual_##Slice(SailingPerf::ESlice::Slice)
#define SAILING_PERF_SCOPE_END(Slice) SailingPerfManual_##Slice.End()
#define SAILING_PERF_SCOPE(Slice) \
	TRACE_CPUPROFILER_EVENT_SCOPE(Sailing_##Slice); \
	SailingPerf::FScope PREPROCESSOR_JOIN(SailingPerfScope_, __LINE__)(SailingPerf::ESlice::Slice)
