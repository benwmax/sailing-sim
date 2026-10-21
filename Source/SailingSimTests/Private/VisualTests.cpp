#include "Misc/AutomationTest.h"
#include "SailingAudio.h"
#include "GpuSlices.h"
#include "VisualPipeline.h"
#include "HAL/IConsoleManager.h"
#include "Misc/App.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "BoatModel.h"
#include "AutoTrim.h"
#include "SailCloth.h"
#include "CrewPose.h"
#include "CrewMotion.h"
#include "SailingSim.h"
#include "BoatLivery.h"
#include "Engine/SkeletalMesh.h"
#include "Wind.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshSocket.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialParameterCollection.h"
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
	// Graphics G1: Ultra (a desktop GPU) is High and more: Epic scalability, TSR at native, clouds traced at half
	// resolution with the most samples; the Mac tiers keep the quarter-resolution clouds.
	const TArray<FQualityCVar> Ultra = QualityCVars(ESailingQuality::Ultra);
	TestEqual(TEXT("Ultra: Epic scalability (4)"), QualityScalabilityLevel(ESailingQuality::Ultra), 4);
	TestEqual(TEXT("Ultra: hardware Lumen"), CVarOf(Ultra, TEXT("r.Lumen.HardwareRayTracing")), 1.f);
	TestEqual(TEXT("Ultra: TSR"), CVarOf(Ultra, TEXT("r.AntiAliasingMethod")), 4.f);
	TestEqual(TEXT("Ultra: native resolution"), CVarOf(Ultra, TEXT("r.ScreenPercentage")), 100.f);
	TestEqual(TEXT("Ultra: clouds traced at half resolution"), CVarOf(Ultra, TEXT("r.VolumetricRenderTarget.Mode")), 1.f);
	TestEqual(TEXT("High: clouds at quarter resolution"), CVarOf(High, TEXT("r.VolumetricRenderTarget.Mode")), 0.f);
	TestTrue(TEXT("Ultra has the most cloud samples"), CVarOf(Ultra, TEXT("r.VolumetricCloud.ViewRaySampleMaxCount")) > CVarOf(High, TEXT("r.VolumetricCloud.ViewRaySampleMaxCount")));
	for (const TArray<FQualityCVar>* Tier : { &High, &Ultra })
	{
		for (const FQualityCVar& C : *Tier)
		{
			TestNotNull(FString::Printf(TEXT("%s exists in this engine"), C.Name), IConsoleManager::Get().FindConsoleVariable(C.Name));
		}
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

#if WITH_EDITORONLY_DATA
namespace
{
	/** The canoe body of a hull mesh (the slots IsCanoe accepts) cut at the design waterline Z = 0: its extent, the whole
	 *  mesh's lowest point, and the displaced volume and its centre (m). */
	struct FCanoeMeasure { FBox Canoe = FBox(ForceInit); double MinZ = 1e9, Volume = 0.0; FVector3d CB = FVector3d(0.0); bool bValid = false; };
	FCanoeMeasure MeasureCanoe(UStaticMesh* Mesh, TFunctionRef<bool(FName)> IsCanoe)
	{
		FCanoeMeasure R;
		const FMeshDescription* MD = Mesh ? Mesh->GetMeshDescription(0) : nullptr;
		if (!MD) return R;
		FStaticMeshConstAttributes Attr(*MD);
		const TVertexAttributesConstRef<FVector3f> Pos = Attr.GetVertexPositions();
		const TPolygonGroupAttributesConstRef<FName> Slots = Attr.GetPolygonGroupMaterialSlotNames();
		FVector3d Moment(0.0);
		for (const FTriangleID T : MD->Triangles().GetElementIDs())
		{
			const TArrayView<const FVertexID> V = MD->GetTriangleVertices(T);
			FVector3d P[3];
			for (int32 K = 0; K < 3; ++K)
			{
				P[K] = FVector3d(Pos[V[K]]) / 100.0; // m
				R.MinZ = FMath::Min(R.MinZ, P[K].Z);
			}
			if (!IsCanoe(Slots[MD->GetTrianglePolygonGroup(T)])) continue;
			for (const FVector3d& Q : P) R.Canoe += FVector(Q);
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
				R.Volume += Vol;
				Moment += Vol * (Poly[0] + Poly[K] + Poly[K + 1]) / 4.0;
			}
		}
		R.CB = FMath::Abs(R.Volume) > 1e-9 ? Moment / R.Volume : FVector3d(0.0);
		R.Volume = FMath::Abs(R.Volume);
		R.bValid = true;
		return R;
	}
}
#endif

// Visual V2: the J/22 model is held to the physics: length, beam and draft within 2 cm of FBoatConfig, and the canoe
// body's centre of buoyancy (its triangles cut at the design waterline) within 2 cm of the hydrostatics'.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualJ22MeshTest, "SailingSim.Visual.J22Mesh", VisualFlags)
bool FVisualJ22MeshTest::RunTest(const FString& Parameters)
{
	UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/Boats/J22/SM_J22_Hull.SM_J22_Hull"));
	if (!TestNotNull(TEXT("SM_J22_Hull is in the project (scripts/make-boat-models.sh)"), Mesh)) return false;
#if WITH_EDITORONLY_DATA
	const FCanoeMeasure M = MeasureCanoe(Mesh, [](FName Slot) { return Slot == TEXT("Topsides") || Slot == TEXT("Bootstripe") || Slot == TEXT("CoveStripe") || Slot == TEXT("Antifouling"); });
	if (!TestTrue(TEXT("Source mesh"), M.bValid)) return false;
	const Sailing::FBoatConfig C = Sailing::FBoatConfig::J22();
	const Sailing::FBoatModel Physics(C);
	const Sailing::Vec3 PhysCB = Physics.DesignBuoyancyCentre();
	const double Tol = 0.02;
	TestTrue(FString::Printf(TEXT("Length overall %.3f m (physics %.3f)"), M.Canoe.GetSize().X, C.LengthOverall), FMath::Abs(M.Canoe.GetSize().X - C.LengthOverall) < Tol);
	TestTrue(FString::Printf(TEXT("Beam %.3f m (physics %.3f)"), M.Canoe.GetSize().Y, C.Beam), FMath::Abs(M.Canoe.GetSize().Y - C.Beam) < Tol);
	TestTrue(FString::Printf(TEXT("Draft %.3f m (physics %.3f)"), -M.MinZ, C.Draft), FMath::Abs(-M.MinZ - C.Draft) < Tol);
	TestTrue(FString::Printf(TEXT("Canoe body volume %.3f m^3 within 2%% of the physics %.3f"), M.Volume, Physics.DesignDisplacedVolume()),
		FMath::Abs(M.Volume - Physics.DesignDisplacedVolume()) < 0.02 * Physics.DesignDisplacedVolume());
	TestTrue(FString::Printf(TEXT("Centre of buoyancy (%.3f, %.3f, %.3f) within 2 cm of the physics (%.3f, %.3f, %.3f)"), M.CB.X, M.CB.Y, M.CB.Z, PhysCB.X, PhysCB.Y, PhysCB.Z),
		FVector3d::Dist(M.CB, FVector3d(PhysCB.X, PhysCB.Y, PhysCB.Z)) < Tol);
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
	for (const FStaticMaterial& Mat : Mesh->GetStaticMaterials())
	{
		TestTrue(FString::Printf(TEXT("Slot %s has a boat material"), *Mat.MaterialSlotName.ToString()), Mat.MaterialInterface && Mat.MaterialInterface->GetName().StartsWith(TEXT("MI_Boat_")));
	}
	return true;
}

// Boats 10: the hero J/22 (Inputs/j22-hero, imported to /Game/Boats/J22Hero by scripts/import_j22_hero.py) measured as
// J22Mesh measures the game's J/22. The hero is a candidate, not the game's boat yet: misses against J22Mesh's
// tolerances are warnings with the numbers (docs/boats-10), and only what would break it in the game fails: the rig
// sockets the pawn reads, Nanite, and a material on every slot. Skipped (with a warning) where it isn't imported.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualJ22HeroMeshTest, "SailingSim.Visual.J22HeroMesh", VisualFlags)
bool FVisualJ22HeroMeshTest::RunTest(const FString& Parameters)
{
	UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/Boats/J22Hero/SM_J22H_Hull.SM_J22H_Hull"), nullptr, LOAD_NoWarn | LOAD_Quiet);
	if (!Mesh)
	{
		AddWarning(TEXT("The hero J/22 isn't imported (scripts/import_j22_hero.py); skipped"));
		return true;
	}
#if WITH_EDITORONLY_DATA
	const FCanoeMeasure M = MeasureCanoe(Mesh, [](FName Slot) { return Slot == TEXT("J22H_Hull"); });
	if (!TestTrue(TEXT("Source mesh"), M.bValid)) return false;
	const Sailing::FBoatConfig C = Sailing::FBoatConfig::J22();
	const Sailing::FBoatModel Physics(C);
	const Sailing::Vec3 PhysCB = Physics.DesignBuoyancyCentre();
	const double Tol = 0.02;
	auto Check = [this](bool bOk, const FString& What) { if (bOk) AddInfo(What); else AddWarning(What + TEXT(" (outside J22Mesh's tolerance)")); };
	Check(FMath::Abs(M.Canoe.GetSize().X - C.LengthOverall) < Tol, FString::Printf(TEXT("Length overall %.3f m (physics %.3f)"), M.Canoe.GetSize().X, C.LengthOverall));
	Check(FMath::Abs(M.Canoe.GetSize().Y - C.Beam) < Tol, FString::Printf(TEXT("Beam %.3f m (physics %.3f)"), M.Canoe.GetSize().Y, C.Beam));
	Check(FMath::Abs(-M.MinZ - C.Draft) < Tol, FString::Printf(TEXT("Draft %.3f m (physics %.3f)"), -M.MinZ, C.Draft));
	Check(FMath::Abs(M.Volume - Physics.DesignDisplacedVolume()) < 0.02 * Physics.DesignDisplacedVolume(),
		FString::Printf(TEXT("Canoe body volume %.3f m^3 (physics %.3f)"), M.Volume, Physics.DesignDisplacedVolume()));
	Check(FVector3d::Dist(M.CB, FVector3d(PhysCB.X, PhysCB.Y, PhysCB.Z)) < Tol,
		FString::Printf(TEXT("Centre of buoyancy (%.3f, %.3f, %.3f) (physics %.3f, %.3f, %.3f)"), M.CB.X, M.CB.Y, M.CB.Z, PhysCB.X, PhysCB.Y, PhysCB.Z));
#endif
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
	for (const FStaticMaterial& Mat : Mesh->GetStaticMaterials())
	{
		TestTrue(FString::Printf(TEXT("Slot %s has a material"), *Mat.MaterialSlotName.ToString()), Mat.MaterialInterface && Mat.MaterialInterface->GetName().StartsWith(TEXT("MI_")));
	}
	return true;
}

// Visual V7: the other seven boats (Tools/blender/build_fleet.py) are held to their physics like the J/22: the canoe
// bodies' length and beam to the extent of the physics hulls, the draft (hull, keel or board, and the rudders where a
// beach cat has no board) to FBoatConfig::Draft, and the displaced volume (2%) and centre of buoyancy (2 cm) to the
// hydrostatics. Where the config's published LOA or beam differs from its own hull shapes, that is reported, not failed.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualFleetMeshTest, "SailingSim.Visual.FleetMesh", VisualFlags)
bool FVisualFleetMeshTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	// The prologue's maxi too (the PC's hero, Tools/boats/maxi): her hull is the exported sections, LOA 30.48, beam 7.2.
	static const TCHAR* Tags[] = { TEXT("J22"), TEXT("Sunfish"), TEXT("ILCA7"), TEXT("Catalina22"), TEXT("Catalina30"), TEXT("Hobie16"), TEXT("Corsair880"), TEXT("Lagoon42"), TEXT("Maxi") };
	for (int32 Type = 1; Type < int32(UE_ARRAY_COUNT(Tags)); ++Type)
	{
		const TCHAR* Tag = Tags[Type];
		auto Load = [Tag](const TCHAR* Part) { return LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/Boats/%s/SM_%s_%s.SM_%s_%s"), Tag, Tag, Part, Tag, Part)); };
		UStaticMesh* Hull = Load(TEXT("Hull"));
		UStaticMesh* Rudder = Load(TEXT("Rudder"));
		if (!TestNotNull(FString::Printf(TEXT("SM_%s_Hull (scripts/make-boat-models.sh)"), Tag), Hull) || !Rudder) continue;
		const FBoatConfig C = FBoatConfig::Make(EBoatType(Type));
		const FBoatModel Physics(C);
#if WITH_EDITORONLY_DATA
		const FMeshDescription* MD = Hull->GetMeshDescription(0);
		if (!TestNotNull(TEXT("Source mesh"), MD)) continue;
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
			for (int32 K = 0; K < 3; ++K) { P[K] = FVector3d(Pos[V[K]]) / 100.0; MinZ = FMath::Min(MinZ, P[K].Z); }
			if (!IsCanoe(Slots[MD->GetTrianglePolygonGroup(T)])) continue;
			for (const FVector3d& Q : P) Canoe += FVector(Q);
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
		// The rudders reach down too (a beach cat's draft is its rudders').
		if (const UStaticMeshSocket* Pivot = Hull->FindSocket(TEXT("RudderPivot")))
		{
			MinZ = FMath::Min(MinZ, (Pivot->RelativeLocation.Z + Rudder->GetBoundingBox().Min.Z) / 100.0);
		}
		double Bow = -1e9, Stern = 1e9, Side = 0.0;
		for (const FHullShape& H : C.Hulls)
		{
			Bow = FMath::Max(Bow, H.BowX);
			Stern = FMath::Min(Stern, H.SternX);
			Side = FMath::Max(Side, FMath::Abs(H.CenterY) + H.MaxHalfBeam);
		}
		const FVector3d CB = FMath::Abs(Volume) > 1e-9 ? Moment / Volume : FVector3d(0.0);
		const Vec3 PhysCB = Physics.DesignBuoyancyCentre();
		const double Tol = 0.02;
		const FString Name(C.Name);
		TestTrue(FString::Printf(TEXT("%s: length %.3f m (physics hulls %.3f)"), *Name, Canoe.GetSize().X, Bow - Stern), FMath::Abs(Canoe.GetSize().X - (Bow - Stern)) < Tol);
		TestTrue(FString::Printf(TEXT("%s: beam %.3f m (physics hulls %.3f)"), *Name, Canoe.GetSize().Y, 2.0 * Side), FMath::Abs(Canoe.GetSize().Y - 2.0 * Side) < Tol);
		// Graphics G3: the configs' published LOA (less a fixed bowsprit) and beam match their own hull shapes.
		TestTrue(FString::Printf(TEXT("%s: published LOA %.2f m (less bowsprit %.2f) matches the hulls' %.2f"), *Name, C.LengthOverall, C.Bowsprit, Bow - Stern),
			FMath::Abs((Bow - Stern) - (C.LengthOverall - C.Bowsprit)) < 0.03);
		TestTrue(FString::Printf(TEXT("%s: published beam %.2f m matches the hulls' %.2f"), *Name, C.Beam, 2.0 * Side), FMath::Abs(2.0 * Side - C.Beam) < 0.03);
		TestTrue(FString::Printf(TEXT("%s: draft %.3f m (physics %.3f)"), *Name, -MinZ, C.Draft), FMath::Abs(-MinZ - C.Draft) < Tol);
		TestTrue(FString::Printf(TEXT("%s: canoe volume %.3f m^3 within 2%% of the physics %.3f"), *Name, FMath::Abs(Volume), Physics.DesignDisplacedVolume()),
			FMath::Abs(FMath::Abs(Volume) - Physics.DesignDisplacedVolume()) < 0.02 * Physics.DesignDisplacedVolume());
		TestTrue(FString::Printf(TEXT("%s: centre of buoyancy (%.3f, %.3f, %.3f) within 2 cm of (%.3f, %.3f, %.3f)"), *Name, CB.X, CB.Y, CB.Z, PhysCB.X, PhysCB.Y, PhysCB.Z),
			FVector3d::Dist(CB, FVector3d(PhysCB.X, PhysCB.Y, PhysCB.Z)) < Tol);
#endif
		TestNotNull(FString::Printf(TEXT("%s: MastStep socket"), Tag), Hull->FindSocket(TEXT("MastStep")));
		TestTrue(FString::Printf(TEXT("%s: hull is Nanite"), Tag), Hull->IsNaniteEnabled());
		for (const FStaticMaterial& M : Hull->GetStaticMaterials())
		{
			TestTrue(FString::Printf(TEXT("%s: slot %s has a boat material"), Tag, *M.MaterialSlotName.ToString()), M.MaterialInterface && M.MaterialInterface->GetName().StartsWith(TEXT("MI_Boat_")));
		}
		int32 Rudders = 0;
		for (const FFoilDef& F : C.Foils) Rudders += F.Role == EFoilRole::Rudder;
		TestEqual(FString::Printf(TEXT("%s: a rudder pivot per rudder"), Tag), int32(Hull->FindSocket(TEXT("RudderPivot")) != nullptr) + int32(Hull->FindSocket(TEXT("RudderPivot_1")) != nullptr), Rudders);
	}
	return true;
}

// Visual V7: the sound layers. Each new voice sounds when its condition holds (a gust's rumble, the halyard and the
// lapping at rest, rain on the water, a squall coming), a cue a recorded sample replaces goes quiet in the synth, the
// shelter hushes the wind in the ears, and every spatialised world source makes sound.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSmokeSoundLayersTest, "SailingSim.Smoke.SoundLayers", VisualFlags)
bool FSmokeSoundLayersTest::RunTest(const FString& Parameters)
{
	auto Rms = [](USoundWaveProcedural* W, int32 N)
	{
		TArray<uint8> Buf;
		double Sum = 0.0;
		for (int32 Block = 0; Block < 8; ++Block)
		{
			W->OnGeneratePCMAudio(Buf, N);
			const int16* S = reinterpret_cast<const int16*>(Buf.GetData());
			for (int32 I = 0; I < N; ++I) Sum += double(S[I]) * S[I];
		}
		return FMath::Sqrt(Sum / (8.0 * N)) / 32768.0;
	};
	auto Fresh = []() { USailingSynthWave* W = NewObject<USailingSynthWave>(); W->Params.Volume = 1.f; return W; };
	{
		USailingSynthWave* Quiet = Fresh();
		const double Base = Rms(Quiet, 24000);
		USailingSynthWave* Gust = Fresh();
		Gust->Params.ApparentWind = 7.f; Gust->Params.GustRatio = 1.6f;
		USailingSynthWave* Calm = Fresh();
		Calm->Params.ApparentWind = 7.f; Calm->Params.GustRatio = 1.0f;
		const double G = Rms(Gust, 24000), C = Rms(Calm, 24000);
		AddInfo(FString::Printf(TEXT("Silence %.4f, wind %.4f, wind in a gust %.4f"), Base, C, G));
		TestTrue(TEXT("A gust adds its rumble"), G > C * 1.05);
		USailingSynthWave* Lee = Fresh();
		Lee->Params.ApparentWind = 7.f; Lee->Params.WindShadow = 1.f;
		TestTrue(TEXT("The wind hushes in a shadow"), Rms(Lee, 24000) < C * 0.8);
		USailingSynthWave* Muted = Fresh();
		Muted->Params.ApparentWind = 7.f; Muted->Params.SampledMask = (1u << uint32(ESailingCue::Wind)) | (1u << uint32(ESailingCue::GustRumble));
		TestTrue(TEXT("A sampled cue is silent in the synth"), Rms(Muted, 24000) < C * 0.2);
	}
	{
		USailingSynthWave* Rain = Fresh();
		Rain->Params.RainWater = 1.f;
		USailingSynthWave* Squall = Fresh();
		Squall->Params.Squall = 1.f;
		USailingSynthWave* Moored = Fresh();
		Moored->Params.Moored = 1.f; Moored->Params.ApparentWind = 8.f;
		USailingSynthWave* Sailing = Fresh();
		Sailing->Params.Moored = 0.f; Sailing->Params.ApparentWind = 8.f;
		TestTrue(TEXT("Rain hisses on the water"), Rms(Rain, 24000) > 0.005);
		TestTrue(TEXT("A squall is heard coming"), Rms(Squall, 24000) > 0.005);
		TestTrue(TEXT("At rest the hull laps and the halyard slaps"), Rms(Moored, 48000) > Rms(Sailing, 48000));
	}
	for (int32 K = 0; K < int32(EWorldSound::Count); ++K)
	{
		USailingWorldSynth* W = NewObject<USailingWorldSynth>();
		W->Kind = EWorldSound(K);
		W->Level = 1.f;
		W->Rate = 1.f;
		const double R = Rms(W, 48000 * 2);
		AddInfo(FString::Printf(TEXT("%s: %.4f"), WorldSoundName(EWorldSound(K)), R));
		TestTrue(FString::Printf(TEXT("%s makes sound"), WorldSoundName(EWorldSound(K))), R > 0.001);
	}
	return true;
}

// Visual V3: the rendered sail is the one the forces came from: depth/chord at each strip's height matches its camber,
// the chord angle its twist, the draft sits forward of mid-chord, and the planform has the sail's area.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualSailShapeTest, "SailingSim.Visual.SailShape", VisualFlags)
bool FVisualSailShapeTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	const FBoatConfig C = FBoatConfig::J22();
	for (const ESailKind Kind : { ESailKind::Main, ESailKind::Jib })
	{
		const FSailGeometry& Geo = Kind == ESailKind::Main ? C.Main : C.Jib;
		FSailCloth Cloth;
		Cloth.Init(Geo, Kind);
		FSailStripState Strips[kMaxSailStrips];
		for (int32 I = 0; I < Geo.NumStrips; ++I)
		{
			Strips[I].Camber = 0.10 + 0.02 * I;                       // fuller aloft
			Strips[I].AngleFromCenterline = (12.0 + 4.0 * I) * kDegToRad; // twist
			Strips[I].Flow = ESailFlow::Attached;
		}
		TArray<FVector> P;
		Cloth.ComputeTarget(Strips, 1, P);
		const TCHAR* Name = Kind == ESailKind::Main ? TEXT("Main") : TEXT("Jib");
		for (int32 I = 0; I < Geo.NumStrips; ++I)
		{
			// The row nearest the strip's mid-height.
			const double Zc = 0.5 * (Geo.Strips[I].ZBottom + Geo.Strips[I].ZTop);
			const int32 R = FMath::RoundToInt((Zc - Geo.Strips[0].ZBottom) / (Geo.Strips[Geo.NumStrips - 1].ZTop - Geo.Strips[0].ZBottom) * (FSailCloth::Rows - 1));
			const FVector Luff = P[R * FSailCloth::Cols], Leech = P[R * FSailCloth::Cols + FSailCloth::Cols - 1];
			const FVector ChordV = Leech - Luff;
			double MaxDepth = 0.0, DraftU = 0.0;
			for (int32 Col = 0; Col < FSailCloth::Cols; ++Col)
			{
				const FVector Q = P[R * FSailCloth::Cols + Col] - Luff;
				const double D = FVector::CrossProduct(ChordV.GetSafeNormal2D(), Q).Z;
				if (FMath::Abs(D) > MaxDepth) { MaxDepth = FMath::Abs(D); DraftU = double(Col) / (FSailCloth::Cols - 1); }
			}
			const double Camber = MaxDepth / ChordV.Size2D();
			const double Angle = FMath::Atan2(ChordV.Y, -ChordV.X);
			TestTrue(FString::Printf(TEXT("%s strip %d: depth/chord %.3f vs camber %.3f"), Name, I, Camber, Strips[I].Camber), FMath::Abs(Camber - Strips[I].Camber) < 0.12 * Strips[I].Camber);
			TestTrue(FString::Printf(TEXT("%s strip %d: chord angle %.1f vs %.1f deg"), Name, I, FMath::RadiansToDegrees(Angle), FMath::RadiansToDegrees(Strips[I].AngleFromCenterline)),
				FMath::Abs(Angle - Strips[I].AngleFromCenterline) < 2.0 * kDegToRad);
			TestTrue(FString::Printf(TEXT("%s strip %d: draft at %.0f%% of the chord"), Name, I, DraftU * 100.0), DraftU > 0.3 && DraftU < 0.5);
		}
		// Planform area (flat): within 8% of the sail's area (the foot and head are extrapolated from the strips).
		FSailStripState Flat[kMaxSailStrips];
		for (int32 I = 0; I < Geo.NumStrips; ++I) Flat[I].Camber = 0.0;
		Cloth.ComputeTarget(Flat, 1, P);
		double Area = 0.0;
		for (int32 R = 0; R + 1 < FSailCloth::Rows; ++R)
		{
			for (int32 Col = 0; Col + 1 < FSailCloth::Cols; ++Col)
			{
				const FVector A = P[R * FSailCloth::Cols + Col], B = P[R * FSailCloth::Cols + Col + 1], D = P[(R + 1) * FSailCloth::Cols + Col], E = P[(R + 1) * FSailCloth::Cols + Col + 1];
				Area += 0.5 * (FVector::CrossProduct(B - A, D - A).Size() + FVector::CrossProduct(E - B, D - B).Size()) / 10000.0;
			}
		}
		TestTrue(FString::Printf(TEXT("%s planform %.2f m^2 vs %.2f"), Name, Area, Geo.TotalArea), FMath::Abs(Area - Geo.TotalArea) < 0.08 * Geo.TotalArea);
	}
	return true;
}

namespace
{
	/** Sails the physics J/22 at a true wind angle with the auto-trimmer for a while, then (optionally) holds the sheets
	 *  and turns to a new angle: the jib's mid strip state at the end. */
	Sailing::FSailStripState JibMidStrip(double TwsKnots, double TrimTwa, double SailTwa)
	{
		using namespace Sailing;
		FWindParams WP;
		WP.SpeedKnots = TwsKnots;
		const FWindField Wind(WP);
		FBoatModel Boat(FBoatConfig::J22());
		Boat.Reset(0.0, 0.0, -TrimTwa * kDegToRad, 2.5);
		FAutoTrim Trim;
		FAutopilot Pilot;
		Pilot.TargetTWADeg = TrimTwa;
		FBoatControls Ctl;
		const double Dt = 1.0 / 120.0;
		for (int32 I = 0; I < 40 * 120; ++I)
		{
			Ctl = Trim.Update(Boat, Ctl, Dt);
			Ctl.Tiller = Pilot.Update(Boat);
			Boat.Step(Dt, Ctl, Wind, nullptr);
		}
		Pilot.TargetTWADeg = SailTwa; // sheets stay where they were
		for (int32 I = 0; I < 12 * 120; ++I)
		{
			Ctl.Tiller = Pilot.Update(Boat);
			Boat.Step(Dt, Ctl, Wind, nullptr);
		}
		const FBoatTelemetry& T = Boat.GetTelemetry();
		return T.JibStrips[T.NumJibStrips / 2];
	}
}

// Visual V3: the jib telltales tell the truth: both streaming when trimmed close-hauled, the windward one lifting when
// pinched, the leeward one stalled when the boat bears away with the sheet still hard in.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualTelltalesTest, "SailingSim.Visual.Telltales", VisualFlags)
bool FVisualTelltalesTest::RunTest(const FString& Parameters)
{
	const Sailing::FSailStripState Trimmed = JibMidStrip(10.0, 42.0, 42.0);
	TestEqual(TEXT("Trimmed close-hauled: windward telltale streams"), JibTelltaleState(Trimmed, true), ETelltaleState::Streaming);
	TestEqual(TEXT("Trimmed close-hauled: leeward telltale streams"), JibTelltaleState(Trimmed, false), ETelltaleState::Streaming);
	const Sailing::FSailStripState Pinched = JibMidStrip(10.0, 42.0, 30.0);
	TestEqual(TEXT("Pinched: windward telltale lifts"), JibTelltaleState(Pinched, true), ETelltaleState::Lifting);
	const Sailing::FSailStripState Oversheeted = JibMidStrip(10.0, 42.0, 62.0);
	TestEqual(TEXT("Sheet hard in on a close reach: leeward telltale stalls"), JibTelltaleState(Oversheeted, false), ETelltaleState::Stalled);
	// The leech telltale streams on a drawing main and curls behind a stalled one.
	Sailing::FSailStripState Leech;
	Leech.Flow = Sailing::ESailFlow::Attached;
	TestEqual(TEXT("Leech telltale streams"), LeechTelltaleState(Leech), ETelltaleState::Streaming);
	Leech.Flow = Sailing::ESailFlow::Stalled;
	TestEqual(TEXT("Leech telltale stalls"), LeechTelltaleState(Leech), ETelltaleState::Stalled);
	return true;
}

// Visual V3: the crew's stances put the body where a sailor's is: leaning out over the rail (keelboat, facing out),
// leaning back from the straps (dinghy, facing in), thighs level and knees forward when seated, low when crossing.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualCrewPoseTest, "SailingSim.Visual.CrewPose", VisualFlags)
bool FVisualCrewPoseTest::RunTest(const FString& Parameters)
{
	const USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/Crew/SK_Sailor.SK_Sailor"));
	if (!TestNotNull(TEXT("SK_Sailor is in the project (scripts/make-boat-models.sh)"), Mesh)) return false;
	for (const TCHAR* Bone : { TEXT("pelvis"), TEXT("spine"), TEXT("chest"), TEXT("head"), TEXT("thigh_l"), TEXT("calf_r"), TEXT("upperarm_l"), TEXT("hand_r"), TEXT("foot_l") })
	{
		TestTrue(FString::Printf(TEXT("Bone %s"), Bone), Mesh->GetRefSkeleton().FindBoneIndex(Bone) != INDEX_NONE);
	}
	auto Pose = [&](ECrewStance Stance, float Hike, TMap<FName, FVector>& Out)
	{
		FCrewPoseParams P;
		P.Stance = Stance;
		P.Hike = Hike;
		TMap<FName, FQuat> Joints;
		CrewJointRotations(P, Joints);
		CrewPosedJoints(Mesh, Joints, Out);
	};
	TMap<FName, FVector> Rest, J;
	CrewPosedJoints(Mesh, {}, Rest);
	TestTrue(TEXT("Standing: head about 1.6 m up"), Rest[TEXT("head")].Z > 150.f && Rest[TEXT("head")].Z < 165.f);
	// Character frame: X is the way the sailor faces.
	Pose(ECrewStance::RailHike, 1.f, J);
	// Round 11: facing inboard, the knees forward of the hips (over the cockpit), the lower legs down into it, the trunk
	// leaning back out over the water.
	TestTrue(FString::Printf(TEXT("Hiking on the rail: leaning back (%.0f cm behind the pelvis)"), J[TEXT("pelvis")].X - J[TEXT("neck")].X),
		J[TEXT("pelvis")].X - J[TEXT("neck")].X > 15.f);
	TestTrue(TEXT("Hiking on the rail: knees inboard of the hips"), J[TEXT("calf_l")].X - J[TEXT("thigh_l")].X > 30.f);
	TestTrue(TEXT("Hiking on the rail: lower legs down into the cockpit"), J[TEXT("foot_l")].Z < J[TEXT("calf_l")].Z - 25.f);
	Pose(ECrewStance::DinghyHike, 1.f, J);
	TestTrue(FString::Printf(TEXT("Dinghy hiking: leaning back (%.0f cm behind the pelvis)"), J[TEXT("pelvis")].X - J[TEXT("neck")].X), J[TEXT("pelvis")].X - J[TEXT("neck")].X > 30.f);
	// docs/crew-light-air/: sitting in from the edge (a light-air run) the dinghy sailor sits up, a little forward; leaning
	// back 20 deg there with the face to the sky read as a full hike in 4 kn (the PC's Ultra audit).
	{
		FCrewPoseParams In;
		In.Stance = ECrewStance::DinghyHike;
		In.Inboard = 1.f;
		TMap<FName, FQuat> InJoints;
		CrewJointRotations(In, InJoints);
		CrewPosedJoints(Mesh, InJoints, J);
		const float Back = J[TEXT("pelvis")].X - J[TEXT("neck")].X;
		TestTrue(FString::Printf(TEXT("Dinghy sailor sitting inboard: upright or forward (neck %.0f cm behind the pelvis)"), Back), Back < 3.f);
	}
	Pose(ECrewStance::Cockpit, 0.f, J);
	TestTrue(TEXT("Seated: knees forward of the hips"), J[TEXT("calf_l")].X - J[TEXT("thigh_l")].X > 30.f);
	TestTrue(TEXT("Seated: thighs about level"), FMath::Abs(J[TEXT("calf_l")].Z - J[TEXT("thigh_l")].Z) < 12.f);
	TestTrue(TEXT("Seated: feet below the knees"), J[TEXT("foot_l")].Z < J[TEXT("calf_l")].Z - 30.f);
	Pose(ECrewStance::Crossing, 0.f, J);
	TestTrue(FString::Printf(TEXT("Crossing: crouched, head %.0f cm above the feet (standing %.0f)"), J[TEXT("head")].Z - J[TEXT("foot_l")].Z, Rest[TEXT("head")].Z - Rest[TEXT("foot_l")].Z),
		(J[TEXT("head")].Z - J[TEXT("foot_l")].Z) < (Rest[TEXT("head")].Z - Rest[TEXT("foot_l")].Z) - 35.f);
	FCrewPoseParams Out;
	Out.Stance = ECrewStance::RailHike;
	Out.Side = 1.f;
	TestEqual(TEXT("On the starboard rail the crew face port (inboard, turned a little forward)"), CrewFacingYaw(Out), -80.f);
	Out.Stance = ECrewStance::DinghyHike;
	TestEqual(TEXT("A dinghy sailor on the starboard side faces port (inboard, turned a little forward)"), CrewFacingYaw(Out), -75.f);

	// Graphics G8: the hands. Reach brings the wrist to a point within the arm's reach (the tiller extension, a sheet);
	// Knee rests it on top of that side's knee; the elbow keeps the stance's side.
	FCrewPoseParams Seat;
	Seat.Stance = ECrewStance::Cockpit;
	TMap<FName, FQuat> Joints;
	CrewJointRotations(Seat, Joints);
	TMap<FName, FVector> Free, Held;
	CrewPosedJoints(Mesh, Joints, Free);
	FCrewHands Hands;
	Hands.Mode[0] = FCrewHands::EMode::Reach;
	Hands.Target[0] = Free[TEXT("upperarm_l")] + FVector(35.f, -10.f, -25.f);
	Hands.Mode[1] = FCrewHands::EMode::Knee;
	CrewPosedJoints(Mesh, Joints, Held, nullptr, &Hands);
	TestTrue(FString::Printf(TEXT("Reach: the left wrist %.1f cm from its target"), FVector::Dist(Held[TEXT("hand_l")], Hands.Target[0])),
		FVector::Dist(Held[TEXT("hand_l")], Hands.Target[0]) < 3.f);
	TestTrue(TEXT("Reach: the shoulder stays put"), FVector::Dist(Held[TEXT("upperarm_l")], Free[TEXT("upperarm_l")]) < 0.5f);
	TestTrue(TEXT("Reach: the arm keeps its bones' lengths"),
		FMath::Abs(FVector::Dist(Held[TEXT("upperarm_l")], Held[TEXT("forearm_l")]) - FVector::Dist(Free[TEXT("upperarm_l")], Free[TEXT("forearm_l")])) < 0.5f);
	const FVector Knee = Held[TEXT("calf_r")];
	TestTrue(FString::Printf(TEXT("Knee: the right wrist %.0f cm from the knee, above it"), FVector::Dist(Held[TEXT("hand_r")], Knee)),
		FVector::Dist(Held[TEXT("hand_r")], Knee) < 20.f && Held[TEXT("hand_r")].Z > Knee.Z);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualMetaHumanCrewTest, "SailingSim.Visual.MetaHumanCrew", VisualFlags)
bool FVisualMetaHumanCrewTest::RunTest(const FString& Parameters)
{
	// Visual V7: the MetaHuman crew load (scripts/make-metahumans.sh) and take every stance the way SK_Sailor does: each
	// limb and the trunk point the same way in the character's frame.
	const USkeletalMesh* Sailor = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/Crew/SK_Sailor.SK_Sailor"));
	if (!TestNotNull(TEXT("SK_Sailor"), Sailor)) return false;
	struct FSeg { const TCHAR* A; const TCHAR* B; const TCHAR* MA; const TCHAR* MB; float Tol; };
	const FSeg Segs[] = {
		{ TEXT("thigh_l"), TEXT("calf_l"), TEXT("thigh_l"), TEXT("calf_l"), 15.f }, { TEXT("thigh_r"), TEXT("calf_r"), TEXT("thigh_r"), TEXT("calf_r"), 15.f },
		{ TEXT("calf_l"), TEXT("foot_l"), TEXT("calf_l"), TEXT("foot_l"), 15.f }, { TEXT("calf_r"), TEXT("foot_r"), TEXT("calf_r"), TEXT("foot_r"), 15.f },
		{ TEXT("upperarm_l"), TEXT("forearm_l"), TEXT("upperarm_l"), TEXT("lowerarm_l"), 15.f }, { TEXT("upperarm_r"), TEXT("forearm_r"), TEXT("upperarm_r"), TEXT("lowerarm_r"), 15.f },
		{ TEXT("forearm_l"), TEXT("hand_l"), TEXT("lowerarm_l"), TEXT("hand_l"), 15.f }, { TEXT("forearm_r"), TEXT("hand_r"), TEXT("lowerarm_r"), TEXT("hand_r"), 15.f },
		{ TEXT("pelvis"), TEXT("neck"), TEXT("pelvis"), TEXT("neck_01"), 20.f },
	};
	const ECrewStance Stances[] = { ECrewStance::RailHike, ECrewStance::Helm, ECrewStance::Cockpit, ECrewStance::Crossing, ECrewStance::DinghyHike, ECrewStance::Trapeze, ECrewStance::Righting };
	// The crew is git-ignored and optional on a fresh checkout (the PC without the Mac's zip): the game falls back to
	// SK_Sailor, so only check it where it is installed.
	if (!IFileManager::Get().DirectoryExists(*FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Crew/MetaHumans"))))
	{
		AddWarning(TEXT("Content/Crew/MetaHumans is not installed (scripts/make-metahumans.sh, or the zip on Windows); skipped"));
		return true;
	}
	for (int32 Role = 0; Role < NumMetaHumanRoles; ++Role)
	{
		USkeletalMesh *Body = nullptr, *Face = nullptr, *Outfit = nullptr;
		if (!TestTrue(FString::Printf(TEXT("The %s MetaHuman is built (scripts/make-metahumans.sh)"), MetaHumanRoleName(Role)), LoadMetaHumanCrew(Role, Body, Face, Outfit))) continue;
		TestNotNull(FString::Printf(TEXT("%s: outfit"), MetaHumanRoleName(Role)), Outfit);
		FCrewRig Rig;
		BuildCrewRig(Body, Rig);
		if (!TestTrue(TEXT("Rig built"), Rig.bValid)) continue;
		TestTrue(TEXT("The rig's frame is a turn about the vertical"), Rig.Frame.RotateVector(FVector::UpVector).Z > 0.999);
		TestTrue(FString::Printf(TEXT("%s: pelvis %.0f cm up (SK_Sailor 93)"), MetaHumanRoleName(Role), Rig.Pelvis.Z), Rig.Pelvis.Z > 80.f && Rig.Pelvis.Z < 110.f);
		const FQuat ToChar = Rig.Frame.Inverse();
		for (const ECrewStance Stance : Stances)
		{
			for (const float Hike : { 0.f, 1.f })
			{
				FCrewPoseParams P;
				P.Stance = Stance;
				P.Hike = Hike;
				TMap<FName, FQuat> Joints;
				CrewJointRotations(P, Joints);
				TMap<FName, FVector> S, M;
				CrewPosedJoints(Sailor, Joints, S);
				CrewPosedJoints(Body, Joints, M, &Rig);
				for (const FSeg& G : Segs)
				{
					const FVector Ds = (S[G.B] - S[G.A]).GetSafeNormal();
					const FVector Dm = ToChar.RotateVector(M[G.MB] - M[G.MA]).GetSafeNormal();
					const float Deg = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(Ds, Dm), -1.0, 1.0)));
					if (Deg > G.Tol)
					{
						AddError(FString::Printf(TEXT("%s, stance %d hike %.0f: %s-%s points %.0f deg off SK_Sailor's"), MetaHumanRoleName(Role), int32(Stance), Hike, G.MA, G.MB, Deg));
					}
				}
			}
		}
		// Graphics G8: the grip closes the fingers toward the palm (each fingertip nearer the wrist), and Reach still lands.
		TestTrue(FString::Printf(TEXT("%s: curl axes for the fingers"), MetaHumanRoleName(Role)), Rig.CurlAxis.Num() >= 24);
		FCrewPoseParams P;
		P.Stance = ECrewStance::Helm;
		TMap<FName, FQuat> Joints;
		CrewJointRotations(P, Joints);
		TMap<FName, FVector> Open, Closed;
		FCrewHands OpenHands, Fist;
		OpenHands.Grip[0] = OpenHands.Grip[1] = 0.f;
		Fist.Grip[0] = Fist.Grip[1] = 1.f;
		CrewPosedJoints(Body, Joints, Open, &Rig, &OpenHands);
		CrewPosedJoints(Body, Joints, Closed, &Rig, &Fist);
		// Round 12: the thumb lies over the fingers in a fist (it had stood straight up off the tiller extension).
		for (const TCHAR* Sx : { TEXT("l"), TEXT("r") })
		{
			const FName Thumb(*FString::Printf(TEXT("thumb_03_%s"), Sx)), Index(*FString::Printf(TEXT("index_02_%s"), Sx));
			if (!Open.Contains(Thumb) || !Open.Contains(Index)) continue;
			const float DOpen = FVector::Dist(Open[Thumb], Open[Index]), DClosed = FVector::Dist(Closed[Thumb], Closed[Index]);
			const FQuat* Turns = Rig.ThumbTurn[Sx[0] == TEXT('l') ? 0 : 1];
			AddInfo(FString::Printf(TEXT("%s %s thumb: turns %.0f/%.0f/%.0f deg, thumb_03 to index_02 %.1f -> %.1f cm"), MetaHumanRoleName(Role), Sx,
				FMath::RadiansToDegrees(Turns[0].GetAngle()), FMath::RadiansToDegrees(Turns[1].GetAngle()), FMath::RadiansToDegrees(Turns[2].GetAngle()), DOpen, DClosed));
			TestTrue(FString::Printf(TEXT("%s: the %s thumb closes over the index finger (%.1f -> %.1f cm)"), MetaHumanRoleName(Role), Sx, DOpen, DClosed), DClosed < DOpen - 1.f);
		}
		for (const TCHAR* Tip : { TEXT("index_03_l"), TEXT("middle_03_r"), TEXT("pinky_03_l") })
		{
			const FString Wrist = FString(Tip).EndsWith(TEXT("_l")) ? TEXT("hand_l") : TEXT("hand_r");
			const float DOpen = FVector::Dist(Open[Tip], Open[*Wrist]), DClosed = FVector::Dist(Closed[Tip], Closed[*Wrist]);
			TestTrue(FString::Printf(TEXT("%s: %s closes in a fist (%.1f -> %.1f cm from the wrist)"), MetaHumanRoleName(Role), Tip, DOpen, DClosed), DClosed < DOpen - 2.f);
		}
		FCrewHands Reach;
		Reach.Mode[1] = FCrewHands::EMode::Reach;
		Reach.Target[1] = Open[TEXT("upperarm_r")] + Rig.Frame.RotateVector(FVector(35.f, 5.f, -25.f));
		TMap<FName, FVector> Held;
		CrewPosedJoints(Body, Joints, Held, &Rig, &Reach);
		const FVector Palm = Held[TEXT("hand_r")] + (Held[TEXT("middle_01_r")] - Held[TEXT("hand_r")]) * 0.75;
		TestTrue(FString::Printf(TEXT("%s: the palm closes %.1f cm from the reach target"), MetaHumanRoleName(Role), FVector::Dist(Palm, Reach.Target[1])),
			FVector::Dist(Palm, Reach.Target[1]) < 4.f);
		// Round 12: holding a line (the tiller extension here, rising aft and inboard to the hand), it runs across the
		// palm, knuckle to knuckle, and the palm still closes on the target.
		FCrewHands Line = Reach;
		Line.Along[1] = Rig.Frame.RotateVector(FVector(0.6f, -0.7f, 0.4f).GetSafeNormal());
		TMap<FName, FVector> Gripped;
		CrewPosedJoints(Body, Joints, Gripped, &Rig, &Line);
		const FVector Across = (Gripped[TEXT("index_01_r")] - Gripped[TEXT("pinky_01_r")]).GetSafeNormal();
		const float Off = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FMath::Abs(FVector::DotProduct(Across, Line.Along[1])), 0.0, 1.0)));
		const float Before = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FMath::Abs(FVector::DotProduct(
			(Held[TEXT("index_01_r")] - Held[TEXT("pinky_01_r")]).GetSafeNormal(), Line.Along[1])), 0.0, 1.0)));
		TestTrue(FString::Printf(TEXT("%s: the extension runs across the palm (%.0f deg off the knuckles, %.0f before)"), MetaHumanRoleName(Role), Off, Before),
			Off < 20.f || Off < Before - 40.f);
		const FVector GripPalm = Gripped[TEXT("hand_r")] + (Gripped[TEXT("middle_01_r")] - Gripped[TEXT("hand_r")]) * 0.75;
		TestTrue(FString::Printf(TEXT("%s: gripping, the palm closes %.1f cm from the target"), MetaHumanRoleName(Role), FVector::Dist(GripPalm, Line.Target[1])),
			FVector::Dist(GripPalm, Line.Target[1]) < 5.f);
	}
	return true;
}

// Crew pose fix (round 8/9): the helm's foot went through the J/22's topsides. Every stance each boat's crew takes, placed
// the way ASailboatPawn::UpdateCrewFigures places it (keep the two in step), on both tacks, sitting up and hiked: no heel
// or toe inside the solid boat (under the deck or through the topsides, outside the cockpit well), and the seated
// stances' feet inside the hull plan, once the feet are planted (FCrewGround). On SK_Sailor and on the MetaHumans where they are installed.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualCrewFeetTest, "SailingSim.Visual.CrewFeet", VisualFlags)
bool FVisualCrewFeetTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	const USkeletalMesh* Sailor = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/Crew/SK_Sailor.SK_Sailor"));
	if (!TestNotNull(TEXT("SK_Sailor"), Sailor)) return false;
	// Round 12: the J/22's traveler bridge (build_j22.py TRAV_X) is a floor, solid down to the sole.
	{
		const FBoatConfig J22;
		TestEqual(TEXT("J/22: the traveler bridge is the floor over it"), CrewFloorZ(J22, -1.75, 0.0), 0.485, 1e-6);
		TestTrue(TEXT("J/22: under the traveler bridge is solid"), CrewInsideBoat(J22, FBoatModel(J22).HullDepth(), FVector(-1.75, 0.0, 0.40)));
		TestEqual(TEXT("J/22: aft of the bridge the floor is the sole"), CrewFloorZ(J22, -2.0, 0.0), 0.30, 1e-6);
		// The hero (the player's boat since round 12) has its own cockpit (build_j22_hero.py, J22H_sockets.json): a sole at
		// 0.136 m with the traveler track on it (no bridge), seats at 0.40 m inboard to 0.40 m.
		TestEqual(TEXT("Hero J/22: no bridge, the floor is the sole"), CrewFloorZ(J22, -1.75, 0.0, false), 0.136, 1e-6);
		TestEqual(TEXT("Hero J/22: the seat outboard of 0.40 m"), CrewFloorZ(J22, -1.73, 0.44, false), 0.40, 1e-6);
		TestFalse(TEXT("Hero J/22: over the sole is open"), CrewInsideBoat(J22, FBoatModel(J22).HullDepth(), FVector(-1.75, 0.0, 0.40), false));
	}
	struct FBody { const USkeletalMesh* Mesh; FCrewRig Rig; FString Name; };
	TArray<FBody> Bodies;
	Bodies.Add({ Sailor, FCrewRig(), TEXT("SK_Sailor") });
	if (IFileManager::Get().DirectoryExists(*FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Crew/MetaHumans"))))
	{
		for (int32 Role = 0; Role < NumMetaHumanRoles; ++Role)
		{
			USkeletalMesh *Body = nullptr, *Face = nullptr, *Outfit = nullptr;
			if (!LoadMetaHumanCrew(Role, Body, Face, Outfit)) continue;
			FBody& B = Bodies.AddDefaulted_GetRef();
			B.Mesh = Body;
			BuildCrewRig(Body, B.Rig);
			B.Name = MetaHumanRoleName(Role);
		}
	}
	else
	{
		AddWarning(TEXT("Content/Crew/MetaHumans is not installed: SK_Sailor only"));
	}
	int32 Checked = 0;
	for (int32 T = 0; T < int32(EBoatType::Count); ++T)
	{
		const FBoatConfig Cfg = FBoatConfig::Make(EBoatType(T));
		const FBoatModel Model(Cfg);
		const int32 N = Cfg.CrewCount;
		for (int32 I = 0; I < N; ++I)
		{
			const bool bHelm = I == N - 1;
			for (const float Side : { 1.f, -1.f })
			{
				for (const float HikeIn : { 0.f, 0.5f, 1.f })
				{
					const double Out = Cfg.CrewSitOut * 0.8 + HikeIn * FMath::Max(Cfg.CrewHikeOut, 0.1);
					// Crew C1: placed by the pawn's own CrewPlacement (it was copied here before).
					FCrewPlaceInput Place;
					Place.Config = &Cfg;
					Place.Index = I;
					Place.CrewOffset = Side * Out;
					Place.WindwardSide = Side > 0.f ? 1 : -1;
					FCrewPlacement Pl;
					CrewPlacement(Place, Pl);
					const FCrewPoseParams& P = Pl.Params;
					const FVector Pelvis = Pl.Pelvis;
					TMap<FName, FQuat> Joints;
					CrewJointRotations(P, Joints);
					const FQuat Facing(FRotator(0.f, Pl.Yaw, Pl.Roll));
					// (Round 11: the rail sitters' feet are in the boat too, never over the side.)
					const bool bInPlan = P.Stance == ECrewStance::Helm || P.Stance == ECrewStance::Cockpit || P.Stance == ECrewStance::DinghyHike
						|| P.Stance == ECrewStance::RailHike;
					for (const FBody& B : Bodies)
					{
						const bool bRig = B.Rig.bValid;
						// MetaHumans crew the player's boat, which on the J/22 is the hero (no traveler bridge); SK_Sailor the light model.
						const bool bBridge = !(bRig && Cfg.Type == EBoatType::J22);
						// A MetaHuman crews the player's boat by role: the helm is the last figure, the trimmer the one before.
						if (bRig && B.Name != MetaHumanRoleName(CrewMetaHumanRole(N, I))) continue;
						const FQuat CompRot = bRig ? Facing * B.Rig.Frame.Inverse() : Facing;
						const FVector Location = bRig ? Pelvis * CmPerMeter - CompRot.RotateVector(B.Rig.Pelvis) : Pelvis * CmPerMeter - FVector(0.f, 0.f, 93.f);
						FCrewGround Ground;
						Ground.Config = &Cfg;
						Ground.HullDepth = Model.HullDepth();
						Ground.ToBoat = FTransform(CompRot, Location);
						Ground.bSeated = P.Stance == ECrewStance::Helm || P.Stance == ECrewStance::Cockpit || P.Stance == ECrewStance::RailHike; // as CrewMotionPose sets it
						Ground.bTravelerBridge = bBridge;
						Ground.bFeetDown = P.Stance == ECrewStance::Helm || P.Stance == ECrewStance::Cockpit;
						Ground.bFlatDeck = P.bFlatDeck;
						FCrewHands Hands;
						Hands.Ground = &Ground;
						FVector Feet[2][2];
						CrewFootPoints(B.Mesh, Joints, Feet, bRig ? &B.Rig : nullptr, &Hands);
						for (int32 S = 0; S < 2; ++S)
						{
							// Round 12: on the J/22 (the round 12 close-ups), a seated foot standing on one floor level lies flat
							// on it, not heel down and toe in the air. (Across a seat's edge or the bridge deck it stays as planted.)
							if (!Ground.bSeated) continue;
							const FVector Heel = (Location + CompRot.RotateVector(Feet[S][0])) / CmPerMeter;
							const FVector Toe = (Location + CompRot.RotateVector(Feet[S][1])) / CmPerMeter;
							const double FloorZ = CrewFloorZ(Cfg, Heel.X, Heel.Y, bBridge);
							if (FloorZ < -1e8 || FMath::Abs(CrewFloorZ(Cfg, Toe.X, Toe.Y, bBridge) - FloorZ) > 0.01 || FMath::Min(Heel.Z, Toe.Z) - FloorZ > 0.02) continue;
							if (FMath::Abs(Heel.Z - Toe.Z) > 0.04)
							{
								AddError(FString::Printf(TEXT("%s, %s crew %d (stance %d, %s tack, hike %.1f): %s foot stands on the floor tilted: heel %.2f m, toe %.2f m"),
									ANSI_TO_TCHAR(BoatTypeName(Cfg.Type)), *B.Name, I, int32(P.Stance), Side > 0.f ? TEXT("starboard") : TEXT("port"), HikeIn, S == 0 ? TEXT("left") : TEXT("right"), Heel.Z, Toe.Z));
							}
						}
						// Round 12, the hero J/22: sitting in the cockpit, no foot hangs in the air over the well's sole or a seat
						// (the helm's forward shoe did, toe up, over the hero's seat). MetaHumans on the J/22 against the hero's plan.
						FCrewCockpitWell Well;
						if (Ground.bFeetDown && CrewCockpitWell(Cfg, Well, bBridge))
						{
							for (int32 S = 0; S < 2; ++S)
							{
								const FVector Heel = (Location + CompRot.RotateVector(Feet[S][0])) / CmPerMeter;
								const FVector Toe = (Location + CompRot.RotateVector(Feet[S][1])) / CmPerMeter;
								const double FootLevel = CrewFloorZ(Cfg, Heel.X, Heel.Y, bBridge);
								const bool bOverSole = (FMath::Abs(FootLevel - Well.SoleZ) <= 0.01 || (Well.SeatZ > 0.0 && FMath::Abs(FootLevel - Well.SeatZ) <= 0.01))
									&& FMath::Abs(CrewFloorZ(Cfg, Toe.X, Toe.Y, bBridge) - FootLevel) <= 0.01;
								const double Hang = FMath::Min(Heel.Z, Toe.Z) - FootLevel;
								// (A foot hanging pointed down, past 35 deg, is left as it is: on the sole it would stand on its toe.)
								const bool bNearLevel = FMath::Abs(Toe.Z - Heel.Z) <= FMath::Sin(FMath::DegreesToRadians(35.0)) * FVector::Dist(Heel, Toe);
								if (bOverSole && bNearLevel && Hang > 0.03 && Hang < 0.25)
								{
									AddError(FString::Printf(TEXT("%s, %s crew %d (stance %d, %s tack, hike %.1f): %s foot hangs %.0f cm over the cockpit floor"),
										ANSI_TO_TCHAR(BoatTypeName(Cfg.Type)), *B.Name, I, int32(P.Stance), Side > 0.f ? TEXT("starboard") : TEXT("port"), HikeIn,
										S == 0 ? TEXT("left") : TEXT("right"), Hang * 100.0));
								}
							}
						}
						for (int32 S = 0; S < 2; ++S)
						{
							for (int32 K = 0; K < 2; ++K)
							{
								const FVector At = (Location + CompRot.RotateVector(Feet[S][K])) / CmPerMeter;
								++Checked;
								const FString What = FString::Printf(TEXT("%s, %s crew %d (stance %d, %s tack, hike %.1f): %s %s at (%.2f, %.2f, %.2f) m"),
									ANSI_TO_TCHAR(BoatTypeName(Cfg.Type)), *B.Name, I, int32(P.Stance), Side > 0.f ? TEXT("starboard") : TEXT("port"), HikeIn,
									S == 0 ? TEXT("left") : TEXT("right"), K == 0 ? TEXT("heel") : TEXT("toe"), At.X, At.Y, At.Z);
								// 1.5 cm of shoe sole may touch the surface it stands on.
								if (CrewInsideBoat(Cfg, Model.HullDepth(), At + FVector(0.0, 0.0, 0.015), bBridge))
								{
									AddError(What + TEXT(" is inside the boat"));
								}
								const FHullShape& Near = Cfg.Hulls[0];
								if (bInPlan && !Cfg.bMultihull && (FMath::Abs(At.Y) > Near.DeckHalfBeam(At.X) || At.X < Near.SternX))
								{
									AddError(What + TEXT(" is outside the hull plan"));
								}
							}
						}
					}
				}
			}
		}
	}
	AddInfo(FString::Printf(TEXT("%d heel and toe points checked"), Checked));
	return true;
}

#endif

// Graphics G3: liveries follow the catalogue's weights, seed 0 is the class's commonest scheme, wear stays in 0..1 and a
// class that requires sail numbers always has one.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualLiveryTest, "SailingSim.Visual.Livery", VisualFlags)
bool FVisualLiveryTest::RunTest(const FString&)
{
	for (int32 T = 0; T < 8; ++T)
	{
		const int32 N = NumLiverySchemes(T);
		TestTrue(FString::Printf(TEXT("class %d has schemes"), T), N > 0);
		TestEqual(FString::Printf(TEXT("class %d seed 0 scheme"), T), SampleBoatLivery(T, 0).Scheme, 0);
		TArray<int32> Count; Count.SetNumZeroed(N);
		const int32 Draws = 4000;
		TArray<uint32> FirstSeed; FirstSeed.Init(0, N);
		for (int32 S = 1; S <= Draws; ++S)
		{
			const FBoatLivery L = SampleBoatLivery(T, uint32(S));
			++Count[L.Scheme];
			if (!FirstSeed[L.Scheme]) FirstSeed[L.Scheme] = uint32(S);
			for (int32 K = 0; K < 4; ++K)
				if (L.Wear[K] < 0.f || L.Wear[K] > 1.f) { AddError(FString::Printf(TEXT("class %d seed %d wear %d = %f"), T, S, K, L.Wear[K])); return false; }
		}
		FString Seeds;
		for (int32 I = 0; I < N; ++I) Seeds += FString::Printf(TEXT(" %u"), FirstSeed[I]);
		AddInfo(FString::Printf(TEXT("class %d: first seed per scheme%s"), T, *Seeds));
	}
	// The J/22 weights from the catalogue: 60 % white factory, 6 % navy.
	int32 White = 0, Navy = 0;
	for (int32 S = 1; S <= 4000; ++S) { const int32 K = SampleBoatLivery(0, uint32(S)).Scheme; White += K == 0; Navy += K == 3; }
	TestTrue(FString::Printf(TEXT("J/22 white share %.3f near 0.60"), White / 4000.f), FMath::Abs(White / 4000.f - 0.60f) < 0.03f);
	TestTrue(FString::Printf(TEXT("J/22 navy share %.3f near 0.06"), Navy / 4000.f), FMath::Abs(Navy / 4000.f - 0.06f) < 0.02f);
	TestFalse(TEXT("J/22 has a sail number"), SampleBoatLivery(0, 77).SailNumber.IsEmpty());
	// The player's boat (seed 0) is 1288, or keeps its last digits inside the class's range (the ILCA read "100000").
	TestEqual(TEXT("player's J/22 number"), SampleBoatLivery(0, 0).SailNumber, FString(TEXT("USA 1288")));
	TestEqual(TEXT("player's ILCA number"), SampleBoatLivery(2, 0).SailNumber, FString(TEXT("161288")));
	return true;
}

// Boat fidelity 1 (docs/boat-fidelity-1): the shared boat library. Each MI_Boat_* slot carries its kind (M_BoatSurface's
// Surface, make_materials.py BOAT_SURFACE), MPC_Boat has the Detail switch the pawn sets per tier, and the hero J/22's
// textured groups take the same wear (Age, Care, Wear) as M_BoatSurface. Skipped (with a warning) before the content is built.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualBoatLibraryTest, "SailingSim.Visual.BoatLibrary", VisualFlags)
bool FVisualBoatLibraryTest::RunTest(const FString& Parameters)
{
	UMaterialParameterCollection* Mpc = LoadObject<UMaterialParameterCollection>(nullptr, TEXT("/Game/Boats/MPC_Boat.MPC_Boat"), nullptr, LOAD_NoWarn | LOAD_Quiet);
	if (!Mpc)
	{
		AddWarning(TEXT("No /Game/Boats/MPC_Boat: run make_materials.py"));
		return true;
	}
	TestNotNull(TEXT("MPC_Boat has Detail"), Mpc->GetScalarParameterByName(TEXT("Detail")));
	const TPair<const TCHAR*, int32> Kinds[] = { { TEXT("Topsides"), 1 }, { TEXT("NonSkid"), 2 }, { TEXT("Stainless"), 3 }, { TEXT("Aluminium"), 4 },
		{ TEXT("PaintedAluminium"), 5 }, { TEXT("Wood"), 6 }, { TEXT("Teak"), 7 }, { TEXT("Rubrail"), 8 }, { TEXT("Rope"), 9 },
		{ TEXT("Sailcloth"), 10 }, { TEXT("SailCover"), 11 }, { TEXT("MastAluminium"), 4 }, { TEXT("CrewSkin"), 0 } };
	for (const TPair<const TCHAR*, int32>& K : Kinds)
	{
		const FString Path = FString::Printf(TEXT("/Game/Boats/Materials/MI_Boat_%s.MI_Boat_%s"), K.Key, K.Key);
		const UMaterialInterface* Mi = LoadObject<UMaterialInterface>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
		float Surface = -1.f;
		if (TestNotNull(FString::Printf(TEXT("MI_Boat_%s"), K.Key), Mi))
		{
			TestTrue(FString::Printf(TEXT("MI_Boat_%s has Surface"), K.Key), Mi->GetScalarParameterValue(TEXT("Surface"), Surface));
			TestEqual(FString::Printf(TEXT("MI_Boat_%s kind"), K.Key), FMath::RoundToInt(Surface), K.Value);
		}
	}
	const UMaterialInterface* Deck = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Boats/J22Hero/MI_J22H_DeckMould.MI_J22H_DeckMould"), nullptr, LOAD_NoWarn | LOAD_Quiet);
	if (!Deck)
	{
		AddWarning(TEXT("No hero J/22 materials: run import_j22_hero.py"));
		return true;
	}
	float Age = 0.f, Care = 0.f;
	FLinearColor Wear;
	TestTrue(TEXT("Hero deck takes Age (unset by default)"), Deck->GetScalarParameterValue(TEXT("Age"), Age) && Age < 0.f);
	TestTrue(TEXT("Hero deck takes Care"), Deck->GetScalarParameterValue(TEXT("Care"), Care));
	TestTrue(TEXT("Hero deck takes Wear"), Deck->GetVectorParameterValue(TEXT("Wear"), Wear));
	return true;
}
