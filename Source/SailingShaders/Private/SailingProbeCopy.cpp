#include "SailingProbeCopy.h"
#include "GlobalShader.h"
#include "RenderGraphBuilder.h"
#include "RenderGraphUtils.h"
#include "RenderTargetPool.h"
#include "ShaderParameterStruct.h"

class FSailingProbeCopyCS : public FGlobalShader
{
public:
	DECLARE_GLOBAL_SHADER(FSailingProbeCopyCS);
	SHADER_USE_PARAMETER_STRUCT(FSailingProbeCopyCS, FGlobalShader);
	BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
		SHADER_PARAMETER_RDG_TEXTURE(Texture2D<float4>, Source)
		SHADER_PARAMETER_RDG_BUFFER_UAV(RWStructuredBuffer<float4>, Dest)
		SHADER_PARAMETER(uint32, Count)
	END_SHADER_PARAMETER_STRUCT()

	static bool ShouldCompilePermutation(const FGlobalShaderPermutationParameters& Parameters) { return true; }
};

IMPLEMENT_GLOBAL_SHADER(FSailingProbeCopyCS, "/SailingShaders/Private/SailingProbeCopy.usf", "MainCS", SF_Compute);

void SailingCopyTexelsToReadback(FRHICommandListImmediate& RHICmdList, FRHITexture* Source, int32 Count, FRHIGPUBufferReadback& Readback)
{
	check(IsInRenderingThread());
	if (!Source || Count <= 0) return;
	FRDGBuilder GraphBuilder(RHICmdList, RDG_EVENT_NAME("SailingProbeCopy"));
	FRDGTextureRef Src = GraphBuilder.RegisterExternalTexture(CreateRenderTarget(Source, TEXT("SailingProbeSource")));
	FRDGBufferRef Dest = GraphBuilder.CreateBuffer(FRDGBufferDesc::CreateStructuredDesc(sizeof(FVector4f), uint32(Count)), TEXT("SailingProbeTexels"));
	FSailingProbeCopyCS::FParameters* Parameters = GraphBuilder.AllocParameters<FSailingProbeCopyCS::FParameters>();
	Parameters->Source = Src;
	Parameters->Dest = GraphBuilder.CreateUAV(Dest);
	Parameters->Count = uint32(Count);
	TShaderMapRef<FSailingProbeCopyCS> Shader(GetGlobalShaderMap(GMaxRHIFeatureLevel));
	FComputeShaderUtils::AddPass(GraphBuilder, RDG_EVENT_NAME("SailingProbeCopyCS"), Shader, Parameters, FIntVector(1, 1, 1));
	AddEnqueueCopyPass(GraphBuilder, &Readback, Dest, uint32(Count) * sizeof(FVector4f));
	GraphBuilder.Execute();
}
