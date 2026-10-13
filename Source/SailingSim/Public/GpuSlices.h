#pragma once

#include "CoreMinimal.h"
#include "Misc/OutputDevice.h"

/**
 * GPU time per budget slice (Visual V1): the bench runs `ProfileGPU` a few times after its measured window, captures
 * the pass tree it prints to LogRHI and sums the passes under the visual plan's budget slices (16.7 ms at Medium:
 * base 4.0, Lumen 4.5, water 2.5, clouds and fog 2.5, Niagara and cloth 1.2, post 1.5). The slices go into bench.json.
 *
 *   Base:      depth prepass, velocities, base pass (Nanite included), shadow depths (VSM), direct lighting,
 *              translucency and everything else under Scene not named below
 *   Lumen:     Lumen scene update and lighting, diffuse indirect and AO, reflections
 *   Water:     single layer water passes (none before V4: the water draws in the base pass until then)
 *   CloudsFog: volumetric clouds and their reconstruction and compose, sky atmosphere, height and volumetric fog
 *   Niagara:   Niagara and GPU particles (cloth runs on the CPU)
 *   Post:      post processing and the upscaler
 *   Other:     work outside the scene renderer (distance field updates, ...)
 */
struct SAILINGSIM_API FGpuSlices
{
	double TotalMs = 0.0, BaseMs = 0.0, LumenMs = 0.0, WaterMs = 0.0, CloudsFogMs = 0.0, NiagaraMs = 0.0, PostMs = 0.0, OtherMs = 0.0;
	int32 Frames = 0;

	/** Adds another frame's slices (for averaging). */
	void Accumulate(const FGpuSlices& Frame);
	/** The average of the accumulated frames. */
	FGpuSlices Average() const;
	/** `"gpu":{"frames":3,"total_ms":13.9,"base_ms":...}` (without the braces of an enclosing object). */
	FString ToJsonField() const;
};

/** Which slice a pass directly under Scene belongs to (by its name). */
enum class EGpuSlice : uint8 { Base, Lumen, Water, CloudsFog, Niagara, Post };
SAILINGSIM_API EGpuSlice ClassifyGpuPass(const FString& PassName);

/**
 * Parses the lines one `ProfileGPU` dump prints (the "┃ ... ┃ name ┃" table) into slices. Returns false if the lines
 * hold no Scene pass. A pass's inclusive time is the last "x ms" in its inclusive column; its depth is the name's
 * indent (3 spaces a level). RenderDeferredLighting is split: its Lumen children (diffuse indirect, reflections) go
 * to Lumen, the rest (direct lights) to Base.
 */
SAILINGSIM_API bool ParseProfileGpu(const TArray<FString>& Lines, FGpuSlices& Out);

/** Collects LogRHI lines while attached to GLog; Take() splits them into one dump per profiled frame. */
class SAILINGSIM_API FGpuProfileCapture : public FOutputDevice
{
public:
	virtual void Serialize(const TCHAR* V, ELogVerbosity::Type Verbosity, const FName& Category) override;
	virtual bool CanBeUsedOnAnyThread() const override { return true; }
	virtual bool CanBeUsedOnMultipleThreads() const override { return true; }
	/** The dumps captured so far, one array of lines each. */
	TArray<TArray<FString>> Take();

private:
	FCriticalSection Lock;
	TArray<FString> Lines;
};
