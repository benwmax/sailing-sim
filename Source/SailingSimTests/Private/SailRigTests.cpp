#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"

namespace
{
	constexpr EAutomationTestFlags SailRigFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
}

// Boat fidelity 4 (docs/boat-fidelity-4): the hero J/22's coiled tails, drawn live by BoatModelVisuals.cpp from
// J22CoilData.inl, which Tools/boats/make_coil_data.py generates from Inputs/j22-hero/J22H_coils.json. The two must agree
// (same coils, same number of points), every coil must lie on the hero hull (inside its bounds, a rope's radius above
// something rather than floating), and M_SailCloth must carry the sailmaker's detail switch and the boat's age and care.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualSailRigTest, "SailingSim.Visual.SailAndRig", SailRigFlags)
bool FVisualSailRigTest::RunTest(const FString& Parameters)
{
	FString Text, Inl;
	if (!TestTrue(TEXT("J22H_coils.json readable"), FFileHelper::LoadFileToString(Text, *FPaths::Combine(FPaths::ProjectDir(), TEXT("Inputs/j22-hero/J22H_coils.json")))))
	{
		return false;
	}
	TSharedPtr<FJsonObject> Root;
	if (!TestTrue(TEXT("J22H_coils.json parses"), FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) && Root.IsValid()))
	{
		return false;
	}
	const TArray<TSharedPtr<FJsonValue>>& Coils = Root->GetArrayField(TEXT("coils"));
	TestTrue(FString::Printf(TEXT("Coiled tails: %d"), Coils.Num()), Coils.Num() >= 4);
	int32 Points = 0;
	UStaticMesh* Hull = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/Boats/J22Hero/SM_J22H_Hull.SM_J22H_Hull"), nullptr, LOAD_NoWarn | LOAD_Quiet);
	const FBox Bounds = Hull ? Hull->GetBoundingBox() : FBox(ForceInit);
	for (const TSharedPtr<FJsonValue>& V : Coils)
	{
		const TSharedPtr<FJsonObject> C = V->AsObject();
		const FString Name = C->GetStringField(TEXT("name"));
		const TArray<TSharedPtr<FJsonValue>>& P = C->GetArrayField(TEXT("points_m"));
		Points += P.Num();
		TestTrue(FString::Printf(TEXT("%s: a tail of a rope, not a dock line (%.1f mm)"), *Name, C->GetNumberField(TEXT("radius_m")) * 1000.0),
			C->GetNumberField(TEXT("radius_m")) > 0.002 && C->GetNumberField(TEXT("radius_m")) < 0.008);
		if (!Hull)
		{
			continue;
		}
		for (const TSharedPtr<FJsonValue>& Q : P)
		{
			const TArray<TSharedPtr<FJsonValue>>& X = Q->AsArray();
			const FVector Cm(X[0]->AsNumber() * 100.0, -X[1]->AsNumber() * 100.0, X[2]->AsNumber() * 100.0);
			if (!Bounds.ExpandBy(1.0).IsInside(Cm))
			{
				AddError(FString::Printf(TEXT("%s: point (%.1f, %.1f, %.1f) cm outside the hero hull"), *Name, Cm.X, Cm.Y, Cm.Z));
				break;
			}
		}
	}
	if (!Hull) AddWarning(TEXT("No hero J/22 imported: bounds not checked"));
	// The generated table must be the JSON's (rerun Tools/boats/make_coil_data.py after build_j22_hero.py).
	if (TestTrue(TEXT("J22CoilData.inl readable"), FFileHelper::LoadFileToString(Inl, *FPaths::Combine(FPaths::ProjectDir(), TEXT("Source/SailingSim/Private/J22CoilData.inl")))))
	{
		TestTrue(FString::Printf(TEXT("J22CoilData.inl holds the JSON's %d points"), Points), Inl.Contains(FString::Printf(TEXT("GJ22CoilPoints[%d]"), Points)));
		TestTrue(FString::Printf(TEXT("J22CoilData.inl holds the JSON's %d coils"), Coils.Num()), Inl.Contains(FString::Printf(TEXT("GJ22Coils[%d]"), Coils.Num())));
	}
	const UMaterialInterface* Main = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/MI_Sail_Main.MI_Sail_Main"), nullptr, LOAD_NoWarn | LOAD_Quiet);
	if (TestNotNull(TEXT("MI_Sail_Main"), Main))
	{
		float Detail = -1.f, Age = 0.f, Care = -1.f;
		TestTrue(TEXT("M_SailCloth has Detail (off unless the pawn turns it on)"), Main->GetScalarParameterValue(TEXT("Detail"), Detail) && Detail == 0.f);
		TestTrue(TEXT("M_SailCloth has Age (unset)"), Main->GetScalarParameterValue(TEXT("Age"), Age) && Age < 0.f);
		TestTrue(TEXT("M_SailCloth has Care"), Main->GetScalarParameterValue(TEXT("Care"), Care) && Care >= 0.f);
	}
	return true;
}
