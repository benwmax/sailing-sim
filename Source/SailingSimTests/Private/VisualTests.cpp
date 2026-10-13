#include "Misc/AutomationTest.h"
#include "GpuSlices.h"
#include "VisualPipeline.h"
#include "HAL/IConsoleManager.h"
#include "Misc/App.h"
#include "BoatModel.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshSocket.h"
#include "MeshDescription.h"
#include "StaticMeshAttributes.h"

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

// Visual V2: the J/22 model is held to the physics: length, beam and draft within 2 cm of FBoatConfig, and the canoe
// body's centre of buoyancy (its triangles cut at the design waterline) within 2 cm of the hydrostatics'.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualJ22MeshTest, "SailingSim.Visual.J22Mesh", VisualFlags)
bool FVisualJ22MeshTest::RunTest(const FString& Parameters)
{
	UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/Boats/J22/SM_J22_Hull.SM_J22_Hull"));
	if (!TestNotNull(TEXT("SM_J22_Hull is in the project (scripts/make-boat-models.sh)"), Mesh)) return false;
#if WITH_EDITORONLY_DATA
	const FMeshDescription* MD = Mesh->GetMeshDescription(0);
	if (!TestNotNull(TEXT("Source mesh"), MD)) return false;
	FStaticMeshConstAttributes Attr(*MD);
	const TVertexAttributesConstRef<FVector3f> Pos = Attr.GetVertexPositions();
	const TPolygonGroupAttributesConstRef<FName> Slots = Attr.GetPolygonGroupMaterialSlotNames();
	auto IsCanoe = [](FName Slot) { return Slot == TEXT("Topsides") || Slot == TEXT("Bootstripe") || Slot == TEXT("CoveStripe") || Slot == TEXT("Antifouling"); };

	FBox Canoe(ForceInit);
	double MinZ = 1e9, Volume = 0.0;
	FVector3d Moment(0.0);
	for (const FTriangleID T : MD->Triangles().GetElementIDs())
	{
		const TArrayView<const FVertexID> V = MD->GetTriangleVertices(T);
		FVector3d P[3];
		for (int32 K = 0; K < 3; ++K)
		{
			P[K] = FVector3d(Pos[V[K]]) / 100.0; // m
			MinZ = FMath::Min(MinZ, P[K].Z);
		}
		if (!IsCanoe(Slots[MD->GetTrianglePolygonGroup(T)])) continue;
		for (const FVector3d& Q : P) Canoe += FVector(Q);
		// Cut at Z = 0 and sum the tetrahedra to the origin (on the cut plane, so the cap adds nothing).
		TArray<FVector3d, TInlineAllocator<4>> Poly;
		for (int32 K = 0; K < 3; ++K)
		{
			const FVector3d& A = P[K], & B = P[(K + 1) % 3];
			if (A.Z <= 0.0) Poly.Add(A);
			if ((A.Z <= 0.0) != (B.Z <= 0.0)) Poly.Add(A + (B - A) * (-A.Z / (B.Z - A.Z)));
		}
		for (int32 K = 1; K + 1 < Poly.Num(); ++K)
		{
			const double Vol = FVector3d::DotProduct(Poly[0], FVector3d::CrossProduct(Poly[K], Poly[K + 1])) / 6.0;
			Volume += Vol;
			Moment += Vol * (Poly[0] + Poly[K] + Poly[K + 1]) / 4.0;
		}
	}
	const FVector3d CB = FMath::Abs(Volume) > 1e-9 ? Moment / Volume : FVector3d(0.0);
	const Sailing::FBoatConfig C = Sailing::FBoatConfig::J22();
	const Sailing::FBoatModel Physics(C);
	const Sailing::Vec3 PhysCB = Physics.DesignBuoyancyCentre();
	const double Tol = 0.02;
	TestTrue(FString::Printf(TEXT("Length overall %.3f m (physics %.3f)"), Canoe.GetSize().X, C.LengthOverall), FMath::Abs(Canoe.GetSize().X - C.LengthOverall) < Tol);
	TestTrue(FString::Printf(TEXT("Beam %.3f m (physics %.3f)"), Canoe.GetSize().Y, C.Beam), FMath::Abs(Canoe.GetSize().Y - C.Beam) < Tol);
	TestTrue(FString::Printf(TEXT("Draft %.3f m (physics %.3f)"), -MinZ, C.Draft), FMath::Abs(-MinZ - C.Draft) < Tol);
	TestTrue(FString::Printf(TEXT("Canoe body volume %.3f m^3 within 2%% of the physics %.3f"), FMath::Abs(Volume), Physics.DesignDisplacedVolume()),
		FMath::Abs(FMath::Abs(Volume) - Physics.DesignDisplacedVolume()) < 0.02 * Physics.DesignDisplacedVolume());
	TestTrue(FString::Printf(TEXT("Centre of buoyancy (%.3f, %.3f, %.3f) within 2 cm of the physics (%.3f, %.3f, %.3f)"), CB.X, CB.Y, CB.Z, PhysCB.X, PhysCB.Y, PhysCB.Z),
		FVector3d::Dist(CB, FVector3d(PhysCB.X, PhysCB.Y, PhysCB.Z)) < Tol);
#endif
	// Starboard is +Y (the FBX import keeps Blender's port-is-+Y space as Unreal's), the mesh is Nanite, every slot has its material.
	const UStaticMeshSocket* Stbd = Mesh->FindSocket(TEXT("ChainplateUpper_S"));
	const UStaticMeshSocket* Port = Mesh->FindSocket(TEXT("ChainplateUpper_P"));
	if (TestNotNull(TEXT("Rig sockets"), Stbd) && TestNotNull(TEXT("Rig sockets (port)"), Port))
	{
		TestTrue(TEXT("Starboard chainplate on +Y"), Stbd->RelativeLocation.Y > 50.f && Port->RelativeLocation.Y < -50.f);
	}
	for (const TCHAR* Name : { TEXT("MastStep"), TEXT("ForestayTack"), TEXT("BackstayPlate"), TEXT("JibLead_S"), TEXT("JibWinch_P"), TEXT("Traveler_C"), TEXT("RudderPivot"), TEXT("LazySheetVia") })
	{
		TestNotNull(FString::Printf(TEXT("Socket %s"), Name), Mesh->FindSocket(Name));
	}
	TestTrue(TEXT("Hull is Nanite"), Mesh->IsNaniteEnabled());
	for (const FStaticMaterial& M : Mesh->GetStaticMaterials())
	{
		TestTrue(FString::Printf(TEXT("Slot %s has a boat material"), *M.MaterialSlotName.ToString()), M.MaterialInterface && M.MaterialInterface->GetName().StartsWith(TEXT("MI_Boat_")));
	}
	return true;
}

#endif
