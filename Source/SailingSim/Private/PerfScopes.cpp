// Perf 1: see PerfScopes.h.
#include "PerfScopes.h"
#include "RenderTimer.h"
#include "RHI.h"
#include "ProceduralMeshComponent.h"
#include "Components/SkinnedMeshComponent.h"
#include "GroomComponent.h"

namespace SailingPerf
{
	double GSliceSeconds[int32(ESlice::Count)] = {};

	const TCHAR* SliceName(ESlice Slice)
	{
		static const TCHAR* Names[] = { TEXT("boat_physics"), TEXT("boat_visuals"), TEXT("sails"), TEXT("crew"), TEXT("rig_lines"),
			TEXT("telltales"), TEXT("boat_sound"), TEXT("boat_capture"), TEXT("boat_learning"), TEXT("water"), TEXT("water_uploads"),
			TEXT("terrain"), TEXT("trees"), TEXT("traffic"), TEXT("traffic_step"), TEXT("hud") };
		static_assert(UE_ARRAY_COUNT(Names) == int32(ESlice::Count), "a name per slice");
		return Names[int32(Slice)];
	}

	FString SlicesJson(const double* Start, const double* End, int32 Frames)
	{
		FString Out = TEXT("{");
		for (int32 I = 0; I < int32(ESlice::Count); ++I)
		{
			if (I > 0) Out += TEXT(",");
			Out += FString::Printf(TEXT("\"%s\":%.3f"), SliceName(ESlice(I)), Frames > 0 ? (End[I] - Start[I]) * 1000.0 / Frames : 0.0);
		}
		return Out + TEXT("}");
	}

	void KeepDynamicMeshesOutOfRayTracing(AActor* Actor)
	{
		if (!Actor) return;
		TInlineComponentArray<UPrimitiveComponent*> Parts(Actor);
		for (UPrimitiveComponent* P : Parts)
		{
			const bool bDynamic = (P->IsA<UProceduralMeshComponent>() && P->GetFName() != TEXT("HullMesh")) || P->IsA<USkinnedMeshComponent>() || P->IsA<UGroomComponent>();
			if (bDynamic && P->bVisibleInRayTracing) P->SetVisibleInRayTracing(false);
		}
	}

	void FThreadTimes::Sample()
	{
		const float G = float(FPlatformTime::ToMilliseconds(GGameThreadTime));
		Game.Add(G);
		GameMs += G;
		RenderMs += FPlatformTime::ToMilliseconds(GRenderThreadTime);
		RhiMs += FPlatformTime::ToMilliseconds(GRHIThreadTime);
		GpuMs += FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles(0));
	}

	FString FThreadTimes::JsonFields() const
	{
		const int32 N = Game.Num();
		if (N == 0) return FString();
		TArray<float> Sorted = Game;
		Sorted.Sort();
		const float P99 = Sorted[FMath::Min(N - 1, FMath::FloorToInt(N * 0.99f))];
		return FString::Printf(TEXT("\"game_ms\":%.2f,\"game_p99_ms\":%.2f,\"render_ms\":%.2f,\"rhi_ms\":%.2f,\"gpu_frame_ms\":%.2f"),
			GameMs / N, P99, RenderMs / N, RhiMs / N, GpuMs / N);
	}
}
