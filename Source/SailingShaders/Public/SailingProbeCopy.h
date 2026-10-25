#pragma once

#include "CoreMinimal.h"
#include "RHIGPUReadback.h"

class FRHICommandListImmediate;
class FRHITexture;

/**
 * docs/sky-probe-readback: copies the first Count texels of a texture's top row into a GPU buffer and enqueues the buffer's
 * readback. Reading a texture back stalls on Metal (FRHIGPUTextureReadback's Lock maps a staging surface, and the Metal RHI
 * submits and waits for the GPU to go idle there, every time); a buffer readback waits only on its own fence, which has
 * signalled once IsReady() says so. Render thread only. The buffer holds Count float4s.
 */
SAILINGSHADERS_API void SailingCopyTexelsToReadback(FRHICommandListImmediate& RHICmdList, FRHITexture* Source, int32 Count, FRHIGPUBufferReadback& Readback);
