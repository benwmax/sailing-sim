#include "Misc/AutomationTest.h"
#include "GpuSlices.h"
#include "VisualPipeline.h"
#include "HAL/IConsoleManager.h"
#include "Misc/App.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags VisualFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	float CVarOf(const TArray<FQualityCVar>& Vars, const TCHAR* Name, float Missing = -1.f)
	{
		const FQualityCVar* V = Vars.FindByPredicate([Name](const FQualityCVar& C) { return FCString::Strcmp(C.Name, Name) == 0; });
		return V ? V->Value : Missing;
	}

	// One ProfileGPU row: exclusive and inclusive columns, then the name indented 3 spaces a level.
	FString Row(double InclusiveMs, int32 Depth, const TCHAR* Name)
	{
		return FString::Printf(TEXT("    ┃     0 │ 0.0%% │ 0.000 ms ┃     0 │ 50.0%% │ %.3f ms ┃ %s%s ┃"),
			InclusiveMs, *FString::ChrN(Depth * 3, TEXT(' ')), Name);
	}
}

// Visual V1: each tier sets the pipeline the plan asks for, and Low keeps the Phase 8 renderer.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualTierSettingsTest, "SailingSim.Visual.TierSettings", VisualFlags)
bool FVisualTierSettingsTest::RunTest(const FString& Parameters)
{
	const TArray<FQualityCVar> Low = QualityCVars(ESailingQuality::Low), Med = QualityCVars(ESailingQuality::Medium), High = QualityCVars(ESailingQuality::High);
	TestEqual(TEXT("Scalability levels 1/2/3"), QualityScalabilityLevel(ESailingQuality::Low) * 100 + QualityScalabilityLevel(ESailingQuality::Medium) * 10 + QualityScalabilityLevel(ESailingQuality::High), 123);
	TestEqual(TEXT("Low: shadow maps, no virtual shadow maps"), CVarOf(Low, TEXT("r.Shadow.Virtual.Enable")), 0.f);
	TestEqual(TEXT("Medium: virtual shadow maps"), CVarOf(Med, TEXT("r.Shadow.Virtual.Enable")), 1.f);
	TestEqual(TEXT("High: virtual shadow maps"), CVarOf(High, TEXT("r.Shadow.Virtual.Enable")), 1.f);
	TestEqual(TEXT("Low: no ray tracing"), CVarOf(Low, TEXT("r.RayTracing.Enable")), 0.f);
	TestEqual(TEXT("Medium: Lumen in software"), CVarOf(Med, TEXT("r.Lumen.HardwareRayTracing")), 0.f);
	TestEqual(TEXT("High: Lumen with hardware ray tracing"), CVarOf(High, TEXT("r.Lumen.HardwareRayTracing")) + CVarOf(High, TEXT("r.RayTracing.Enable")), 2.f);
	TestEqual(TEXT("Low keeps the Phase 8 anti-aliasing (no override)"), CVarOf(Low, TEXT("r.AntiAliasingMethod")), -1.f);
	TestEqual(TEXT("Low keeps the Phase 8 resolution (no override)"), CVarOf(Low, TEXT("r.ScreenPercentage")), -1.f);
	TestTrue(TEXT("Medium renders below native and upscales"), CVarOf(Med, TEXT("r.ScreenPercentage")) >= 50.f && CVarOf(Med, TEXT("r.ScreenPercentage")) < 100.f);
	TestEqual(TEXT("High renders at native"), CVarOf(High, TEXT("r.ScreenPercentage")), 100.f);
	TestNotEqual(TEXT("TSR is off on Medium"), CVarOf(Med, TEXT("r.AntiAliasingMethod")), 4.f);
	TestNotEqual(TEXT("TSR is off on High"), CVarOf(High, TEXT("r.AntiAliasingMethod")), 4.f);
	TestTrue(TEXT("Cloud samples rise with the tier"), CVarOf(Low, TEXT("r.VolumetricCloud.ViewRaySampleMaxCount")) <= CVarOf(Med, TEXT("r.VolumetricCloud.ViewRaySampleMaxCount"))
		&& CVarOf(Med, TEXT("r.VolumetricCloud.ViewRaySampleMaxCount")) <= CVarOf(High, TEXT("r.VolumetricCloud.ViewRaySampleMaxCount")));
	TestTrue(TEXT("Physical camera on Medium and High only"), !UsesPhysicalCamera(ESailingQuality::Low) && UsesPhysicalCamera(ESailingQuality::Medium) && UsesPhysicalCamera(ESailingQuality::High));
	for (const FQualityCVar& C : High)
	{
		TestNotNull(FString::Printf(TEXT("%s exists in this engine"), C.Name), IConsoleManager::Get().FindConsoleVariable(C.Name));
	}
	return true;
}

// Visual V1: the incident meter gives the photographers' exposures (sunny 16 = EV 15, overcast 12-13, sunset 7-9,
// full moon about -3), and the camera keeps part of the gloom.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualMeteredExposureTest, "SailingSim.Visual.MeteredExposure", VisualFlags)
bool FVisualMeteredExposureTest::RunTest(const FString& Parameters)
{
	auto Ev = [](double El, double Shade, double Dark, double MoonEl = -90.0, double Lit = 0.0) { return MeteredEV100(SceneIlluminanceLux(El, Shade, Dark, MoonEl, Lit)); };
	const double Noon = Ev(75.0, 1.0, 0.0), Overcast = Ev(75.0, 0.18, 0.5), Afternoon = Ev(30.0, 1.0, 0.0), Sunset = Ev(0.0, 1.0, 0.0), Dusk = Ev(-6.0, 1.0, 0.0), Moon = Ev(-30.0, 1.0, 0.0, 60.0, 1.0);
	TestTrue(FString::Printf(TEXT("Clear noon EV %.1f (sunny 16: 15)"), Noon), Noon > 14.5 && Noon < 16.0);
	TestTrue(FString::Printf(TEXT("Mid-afternoon EV %.1f"), Afternoon), Afternoon > 13.5 && Afternoon < Noon);
	TestTrue(FString::Printf(TEXT("Overcast noon EV %.1f (12 to 13.5)"), Overcast), Overcast > 11.5 && Overcast < 13.5);
	TestTrue(FString::Printf(TEXT("Sunset EV %.1f (7 to 9)"), Sunset), Sunset > 6.5 && Sunset < 9.5);
	TestTrue(FString::Printf(TEXT("End of civil twilight EV %.1f (about 0)"), Dusk), Dusk > -1.5 && Dusk < 1.5);
	TestTrue(FString::Printf(TEXT("Full moon high EV %.1f (about -3)"), Moon), Moon > -4.5 && Moon < -2.0);
	const double Floor = -5.0;
	const double StormCam = CameraEV100(60.0, 0.05, 0.9, -90.0, 0.0, Floor), ClearCam = CameraEV100(60.0, 1.0, 0.0, -90.0, 0.0, Floor);
	const double StormMeter = Ev(60.0, 0.05, 0.9) - SceneEVOffset();
	TestTrue(TEXT("A storm is exposed brighter than the clear day (the camera adapts)"), StormCam < ClearCam);
	TestTrue(TEXT("...but not all the way (the gloom stays)"), StormCam > StormMeter + 0.3);
	TestEqual(TEXT("Night holds the floor"), CameraEV100(-40.0, 1.0, 0.0, -10.0, 0.0, Floor), Floor);
	return true;
}

// Visual V1: a ProfileGPU dump is summed into the budget slices.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualGpuSlicesTest, "SailingSim.Visual.GpuSlices", VisualFlags)
bool FVisualGpuSlicesTest::RunTest(const FString& Parameters)
{
	const TArray<FString> Dump = {
		TEXT("GPU Profile for Frame 426 - Graphics pipeline 0 - GPU 0"),
		Row(14.0, 0, TEXT("<root>")),
		Row(14.0, 1, TEXT("Frame 426")),
		Row(0.3, 4, TEXT("\"DistanceFields\"")),
		Row(13.6, 4, TEXT("Scene")),
		Row(0.5, 5, TEXT("PrePass DDM_AllOpaqueNoVelocity (Forced by Nanite)")),
		Row(0.4, 6, TEXT("DepthPassParallel")),
		Row(1.1, 5, TEXT("BasePass")),
		Row(0.3, 5, TEXT("LumenSceneLighting")),
		Row(3.0, 5, TEXT("RenderDeferredLighting")),
		Row(2.5, 6, TEXT("DiffuseIndirectAndAO")),
		Row(1.5, 7, TEXT("LumenScreenProbeGather")),
		Row(0.4, 6, TEXT("Lights")),
		Row(4.4, 5, TEXT("VolumetricCloud")),
		Row(0.1, 5, TEXT("ExponentialHeightFog")),
		Row(2.5, 5, TEXT("PostProcessing")),
		Row(1.7, 5, TEXT("ShadowDepths")),
	};
	FGpuSlices S;
	TestTrue(TEXT("Parsed"), ParseProfileGpu(Dump, S));
	TestEqual(TEXT("Total is the root"), S.TotalMs, 14.0, 1e-6);
	TestEqual(TEXT("Lumen = scene lighting + diffuse indirect"), S.LumenMs, 0.3 + 2.5, 1e-6);
	TestEqual(TEXT("Base = prepass + base pass + direct lights + shadows"), S.BaseMs, 0.5 + 1.1 + 0.5 + 1.7, 1e-6);
	TestEqual(TEXT("Clouds and fog"), S.CloudsFogMs, 4.5, 1e-6);
	TestEqual(TEXT("Post"), S.PostMs, 2.5, 1e-6);
	TestEqual(TEXT("Other = outside Scene"), S.OtherMs, 14.0 - 13.6 + (13.6 - (0.5 + 1.1 + 0.3 + 3.0 + 4.4 + 0.1 + 2.5 + 1.7)), 1e-6);
	TestEqual(TEXT("Water draws in the base pass until V4"), S.WaterMs, 0.0, 1e-9);
	TestFalse(TEXT("No Scene, no slices"), ParseProfileGpu({ Row(1.0, 0, TEXT("<root>")) }, S));
	FGpuSlices Sum;
	FGpuSlices A; A.TotalMs = 10.0; A.Frames = 1;
	FGpuSlices B; B.TotalMs = 14.0; B.Frames = 1;
	Sum.Accumulate(A); Sum.Accumulate(B);
	TestEqual(TEXT("Averaged over frames"), Sum.Average().TotalMs, 12.0, 1e-9);
	TestTrue(TEXT("JSON field"), Sum.Average().ToJsonField().StartsWith(TEXT("\"gpu\":{\"frames\":2,\"total_ms\":12.00")));
	return true;
}

// Visual V1: the project renders with Substrate, virtual shadow maps and ray tracing compiled in. Needs a renderer.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualPipelineSmokeTest, "SailingSim.Visual.PipelineSmoke", VisualFlags)
bool FVisualPipelineSmokeTest::RunTest(const FString& Parameters)
{
	if (!FApp::CanEverRender())
	{
		AddInfo(TEXT("Skipped: no renderer (-nullrhi)."));
		return true;
	}
	auto Int = [](const TCHAR* Name) { IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(Name); return V ? V->GetInt() : -1; };
	TestEqual(TEXT("Substrate"), Int(TEXT("r.Substrate")), 1);
	TestEqual(TEXT("Ray tracing compiled in"), Int(TEXT("r.RayTracing")), 1);
	TestEqual(TEXT("Ray tracing on demand"), Int(TEXT("r.RayTracing.EnableOnDemand")), 1);
	TestEqual(TEXT("Lumen GI"), Int(TEXT("r.DynamicGlobalIlluminationMethod")), 1);
	return true;
}

#endif
